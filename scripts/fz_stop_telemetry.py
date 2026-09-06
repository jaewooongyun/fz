#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 입력은 Stop 훅 stdin JSON(transcript_path)이고 출력은 FZ_TELEMETRY_DIR 이다
"""fz_stop_telemetry.py — Stop 훅. 턴 1건을 `events.jsonl` 에 1줄 남기고 끝난다.

⛔ **로그 전용이다.** stdout 은 항상 빈 문자열, exit 은 항상 0이다. 계측이 컨텍스트에
   1토큰이라도 넣으면 피측정량이 바뀐다 — 이 훅이 재려는 것이 바로 "하네스가 컨텍스트를
   얼마나 먹는가"이므로, 자기 자신이 그 값을 오염시키면 측정 전체가 무의미해진다.
   `gate_stop_hook.py` 와 exit 계약이 **다르다**: 저쪽은 미충족이면 exit 2 로 막는다.
   이쪽은 어떤 경우에도 막지 않는다.

⛔ 저장 금지 항목: 메시지 본문·경로 원문. `cwd` 는 sha1 앞 8자만 남긴다(개인정보·용량).
   트랜스크립트에 이미 있는 필드를 다시 쓰지 않는다 — 결합 키(`session_id`·`prompt_id`)만
   겹치고, 나머지는 **트랜스크립트에 없는 파생값**(문구 발화 수·정정 신호)이다.

예산: 정규식만 쓰고 트랜스크립트는 **tail 200KB** 만 읽는다(전체 파싱 금지).

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import time

TAIL_BYTES = 200 * 1024
DEFAULT_TELEMETRY_DIR = "~/.fz/telemetry"  # 사용자 중립 기본값 — 개인 경로는 env FZ_TELEMETRY_DIR 로 (governance:146)
EVENTS_FILE = "events.jsonl"

RE_GATE = re.compile(r"Gate \d")
RE_VERIFY = re.compile(r"verify:")
RE_BAN = re.compile("⛔")
# fz 결과 줄 관례 — 본문은 저장하지 않고 **어느 표식이 났는지**만 남긴다.
RESULT_MARKERS = (("result", re.compile(r"result:")),
                  ("needs input", re.compile(r"needs input:")),
                  ("failed", re.compile(r"failed:")))
# ⚠️ 약한 신호다. 어휘가 겹치는 정상 발화("다시 확인해줘")를 잡는다 — 필드명에 `_signal`.
RE_CORRECTION = re.compile(r"(아니|틀렸|왜 .{0,12}(했|한)|하지 말|되돌|취소|다시)")


TAIL_MAX_BYTES = 4 * 1024 * 1024  # 적응형 확장 상한 — 이 너머는 귀속을 포기하고 0을 낸다


def tail_text(path, limit=TAIL_BYTES, needle=None, max_limit=TAIL_MAX_BYTES):
    """파일 끝 limit 바이트. 첫 줄은 잘려 있을 수 있어 호출부가 파싱 실패를 흘린다.

    ⛔ 고정 200KB 창은 귀속 키를 놓친다 — 실측(2026-09-06): 4.2MB 트랜스크립트의 마지막 200KB 가
    assistant 169줄뿐이고 user 엔트리 0. 도구 출력이 큰 턴에서는 마지막 사람 프롬프트가 창 밖으로
    밀린다. `needle`(예: `"promptId"` 를 가진 user 줄)이 창에 없으면 창을 2배씩 넓힌다(상한 max_limit).
    """
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        while True:
            handle.seek(max(0, size - limit))
            text = handle.read().decode("utf-8", "replace")
            if needle is None or needle(text) or limit >= size or limit >= max_limit:
                return text
            limit = min(limit * 2, max_limit)


def _has_human_prompt(prompt_id):
    """목표 prompt_id 의 **사람 프롬프트**(tool_result 아님) 줄이 창 안에 있는가.

    ⛔ Codex 리뷰(2026-09-06): "아무 user+promptId" 로 멈추면 tool_result 도 promptId 를 갖고 있어
    긴 턴 중간에서 확장이 멈추고 앞선 도구 호출·사람의 정정 문장이 누락된다(220KB fixture 재현).
    prompt_id 가 없으면 경계를 정의할 수 없으므로 확장하지 않는다(호출부가 측정 불가로 표시).
    """
    if not prompt_id:
        return lambda text: True
    needle = '"promptId": "%s"' % prompt_id
    needle2 = '"promptId":"%s"' % prompt_id

    def check(text):
        for line in text.split("\n")[1:]:
            if not line.startswith("{") or (needle not in line and needle2 not in line):
                continue
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            if obj.get("type") != "user":
                continue
            content = (obj.get("message") or {}).get("content")
            is_tool_result = isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            )
            if not is_tool_result:
                return True
        return False

    return check


def scan_transcript(path, prompt_id):
    """tail 구간에서 이번 prompt 의 assistant 활동을 센다.

    ⛔ assistant 엔트리에는 `promptId` 가 없다(실측 2026-09-06: 0/415). `promptId` 는 user
    엔트리(사람 프롬프트·tool_result 둘 다, 389/392)에만 있다. 그래서 파일 순서로 "가장 최근
    user 의 promptId" 를 상태로 들고 가 그 뒤의 assistant 를 귀속한다(실측 415/415).
    parentUuid 체인 추적은 3/415 라 쓰지 않는다. prompt_id 를 못 받으면 구간 판별이 안 되므로
    이전 턴이 섞인 값을 내는 것보다 0으로 두고 `matched` 로 분모를 밝힌다.
    """
    out = {
        "boundary_found": False,  # 목표 prompt_id 의 사람 프롬프트 줄을 창 안에서 봤는가
        "skill": None,
        "n_assistant": 0,
        "n_tool_use": 0,
        "n_ask": 0,
        "n_workflow": 0,
        "last_user_text": "",
        "matched": 0,
    }
    seen_msg_ids = set()
    current_prompt = None  # 가장 최근 user 엔트리의 promptId — assistant 귀속 키
    for line in tail_text(path, needle=_has_human_prompt(prompt_id)).splitlines():
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        kind = obj.get("type")
        if kind == "user":
            if obj.get("promptId"):
                current_prompt = obj.get("promptId")
                if prompt_id and current_prompt == prompt_id:
                    content_probe = (obj.get("message") or {}).get("content")
                    if not (isinstance(content_probe, list) and any(
                            isinstance(b, dict) and b.get("type") == "tool_result" for b in content_probe)):
                        out["boundary_found"] = True
            content = (obj.get("message") or {}).get("content")
            is_tool_result = isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            )
            # 사람이 친 프롬프트만 정정 신호 대상 — tool_result 는 도구 출력이다
            if not is_tool_result and (not prompt_id or current_prompt == prompt_id):
                if isinstance(content, str):
                    out["last_user_text"] = content
                elif isinstance(content, list):
                    texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                    if texts:
                        out["last_user_text"] = "\n".join(texts)
            continue
        if kind != "assistant":
            continue
        if not prompt_id or current_prompt != prompt_id:
            # ⛔ prompt_id 부재는 "전부 센다"가 아니라 "귀속 불가"다 — 이전 턴이 섞인 값을 턴 측정으로
            #    내는 것보다 0 + measurement="unattributable" 이 낫다 (Codex 리뷰 2026-09-06)
            continue
        out["matched"] += 1
        # ⛔ 한 메시지가 content 블록마다 한 줄씩 기록된다(같은 `message.id` 공유) —
        #    줄을 세면 메시지 수가 2~4배로 부풀고, tool_use 는 줄마다 다른 블록이라
        #    반대로 줄 단위로 세야 맞는다. 축마다 dedup 키가 다르다.
        message_id = (obj.get("message") or {}).get("id")
        if message_id is None or message_id not in seen_msg_ids:
            if message_id is not None:
                seen_msg_ids.add(message_id)
            out["n_assistant"] += 1
        skill = obj.get("attributionSkill")
        if skill:
            out["skill"] = skill
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            out["n_tool_use"] += 1
            name = block.get("name")
            if name == "AskUserQuestion":
                out["n_ask"] += 1
            elif name == "Workflow":
                out["n_workflow"] += 1
    return out


def build_event(payload):
    transcript = payload.get("transcript_path") or ""
    prompt_id = payload.get("prompt_id")
    scan = {"boundary_found": False, "skill": None, "n_assistant": 0, "n_tool_use": 0, "n_ask": 0, "n_workflow": 0, "last_user_text": "", "matched": 0}
    if transcript and os.path.isfile(transcript):
        try:
            scan = scan_transcript(transcript, prompt_id)
        except OSError:
            pass

    last = payload.get("last_assistant_message") or ""
    result_line = None
    for label, pattern in RESULT_MARKERS:
        if pattern.search(last):
            result_line = label
            break

    effort = payload.get("effort")
    if isinstance(effort, dict):
        effort = effort.get("level")

    cwd = payload.get("cwd") or ""
    cwd_hash = hashlib.sha1(cwd.encode("utf-8")).hexdigest()[:8] if cwd else None

    return {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session_id": payload.get("session_id"),
        "prompt_id": prompt_id,
        "cwd_hash": cwd_hash,
        "skill": scan["skill"],
        "effort": effort,
        "permission_mode": payload.get("permission_mode"),
        "stop_reason": payload.get("stop_reason"),
        # 측정 상태 — 0 이 "저부하"인지 "못 잼"인지 소비자가 구분할 수 있게 (⛔ 0건은 측정 실패를 먼저 의심)
        "matched": scan["matched"],
        "measurement": ("unattributable" if not prompt_id
                        else "no_transcript" if not (transcript and os.path.isfile(transcript))
                        else "complete" if scan["boundary_found"]
                        else "incomplete"),
        "n_assistant": scan["n_assistant"],
        "n_tool_use": scan["n_tool_use"],
        "n_ask": scan["n_ask"],
        "n_workflow": scan["n_workflow"],
        "gate_mentions": len(RE_GATE.findall(last)),
        "verify_mentions": len(RE_VERIFY.findall(last)),
        "ban_mentions": len(RE_BAN.findall(last)),
        "result_line": result_line,
        "user_correction_signal": bool(RE_CORRECTION.search(scan["last_user_text"])),
    }


def _prior_attempts(path, session_id, prompt_id):
    """같은 (session_id, prompt_id) 로 이미 기록된 행 수 — 파일 끝 64KB 만 본다(같은 턴은 끝에 몰린다)."""
    if not (session_id and prompt_id) or not os.path.isfile(path):
        return 0
    needle_s = '"session_id": "%s"' % session_id
    needle_p = '"prompt_id": "%s"' % prompt_id
    count = 0
    text = tail_text(path, limit=64 * 1024)
    # ⛔ 첫 줄은 창이 파일 중간에서 시작했을 때만 잘린 줄이다 — 파일이 창보다 작으면 첫 줄이 곧 첫 이벤트라
    #    버리면 한 건을 놓친다(실측: 3회 호출이 attempt 1,1,2). 파일 크기로 분기한다.
    lines = text.split("\n")
    if os.path.getsize(path) > 64 * 1024:
        lines = lines[1:]
    for line in lines:
        if needle_s in line and needle_p in line:
            count += 1
    return count


def append_event(event, telemetry_dir):
    directory = os.path.expanduser(telemetry_dir)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, EVENTS_FILE)
    # ⛔ Stop 은 한 턴에 여러 번 불릴 수 있다 — gate_stop_hook 이 block 하면 Claude 가 이어가고 Stop 이 다시
    #    발화한다(Codex 리뷰 2026-09-06). 무조건 append 는 한 턴을 N행으로 부풀린다. append-only 를 지키되
    #    `attempt` 를 붙여 소비자가 턴당 **마지막 attempt 만** 읽게 한다(각 행은 그 시점까지의 누적치).
    event["attempt"] = _prior_attempts(path, event.get("session_id"), event.get("prompt_id")) + 1
    with open(path, "a") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def run_hook(stream, telemetry_dir):
    """⛔ 전면 fail-open. 어떤 예외도 stderr 1줄로 끝내고 exit 0 을 낸다."""
    try:
        raw = stream.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        append_event(build_event(payload), telemetry_dir)
    except Exception as exc:  # noqa: BLE001 — 세션 감금 금지가 최우선 계약
        sys.stderr.write("fz_stop_telemetry: %s: %s\n" % (type(exc).__name__, exc))
    return 0


# ── self-test ───────────────────────────────────────────────────────────────
def _fixture_transcript(path, prompt_id):
    # ⛔ 실데이터 형태를 그대로 따른다 — assistant 엔트리에 promptId 없음, user(사람·tool_result)에만 있음.
    #    이전 fixture 는 assistant 에 promptId 를 넣어 실데이터에서 5필드 전부 0 이 되는 결함을 25/25 로 가렸다.
    entries = [
        {  # 이전 턴의 프롬프트 — 이번 구간이 아니므로 그 뒤 assistant 는 세지 않는다
            "type": "user", "promptId": "other", "timestamp": "2026-09-06T00:00:00Z",
            "message": {"content": "이전 요청"},
        },
        {
            "type": "assistant",
            "message": {"id": "m0", "content": [{"type": "tool_use", "id": "t0", "name": "Read", "input": {}}]},
        },
        {  # 이번 턴의 사람 프롬프트 — 정정 신호 대상
            "type": "user", "promptId": prompt_id, "timestamp": "2026-09-06T00:01:00Z",
            "message": {"content": "아니 다시 해줘"},
        },
        {
            "type": "assistant",
            "attributionSkill": "fz:fz-code",
            "message": {"id": "m1", "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {}}]},
        },
        {  # tool_result user 엔트리 — promptId 는 같고, 정정 신호 대상은 아니다
            "type": "user", "promptId": prompt_id,
            "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "content": "아니 이건 도구 출력"}]},
        },
        {
            "type": "assistant",
            "message": {"id": "m2", "content": [
                {"type": "tool_use", "id": "t2", "name": "AskUserQuestion", "input": {}},
                {"type": "tool_use", "id": "t3", "name": "Workflow", "input": {}},
            ]},
        },
        {  # ⛔ m2 의 두 번째 줄 — 같은 message.id, 다른 블록.
            #    메시지 수는 그대로 2, tool_use 는 4로 늘어야 한다.
            "type": "assistant",
            "message": {"id": "m2", "content": [{"type": "tool_use", "id": "t5", "name": "Read", "input": {}}]},
        },
    ]
    with open(path, "w") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


class _CaptureOut(object):
    def __init__(self):
        self.buf = ""

    def write(self, text):
        self.buf += text

    def flush(self):
        pass


def self_test():
    checks = []

    def check(name, got, want):
        checks.append((name, got == want, got, want))

    base = tempfile.mkdtemp(prefix="fz-stop-selftest-")
    telemetry = os.path.join(base, "telemetry")
    events = os.path.join(telemetry, EVENTS_FILE)
    transcript = os.path.join(base, "t.jsonl")
    _fixture_transcript(transcript, "p1")

    cases = [
        ("정상", json.dumps({
            "session_id": "s1", "prompt_id": "p1", "transcript_path": transcript,
            "cwd": "/Users/x/proj", "permission_mode": "acceptEdits",
            "effort": {"level": "xhigh"}, "hook_event_name": "Stop",
            "last_assistant_message": "Gate 1 통과. verify: 빌드 성공\n⛔ 주의 ⛔\nresult: 완료",
            "stop_reason": "end_turn",
        })),
        ("transcript 없음", json.dumps({
            "session_id": "s2", "prompt_id": "p2", "transcript_path": os.path.join(base, "nope.jsonl"),
            "cwd": "/tmp", "hook_event_name": "Stop", "last_assistant_message": "failed: 빌드 실패",
        })),
        ("JSON 깨짐", "{not json"),
    ]
    for label, stdin_text in cases:
        captured = _CaptureOut()
        real_stdout = sys.stdout
        sys.stdout = captured
        try:
            code = run_hook(_StringReader(stdin_text), telemetry)
        finally:
            sys.stdout = real_stdout
        check("%s — exit 0" % label, code, 0)
        check("%s — stdout 길이 0" % label, len(captured.buf), 0)

    with open(events) as handle:
        rows = [json.loads(ln) for ln in handle if ln.strip()]
    check("정상 케이스 2건만 기록 (깨진 JSON 은 0줄)", len(rows), 2)

    first = rows[0]
    check("skill", first["skill"], "fz:fz-code")
    check("effort 평탄화", first["effort"], "xhigh")
    check("assistant 메시지 2건 (⛔ 줄 수 3이 아니다)", first["n_assistant"], 2)
    check("tool_use 4건 (블록 단위 — 메시지 dedup 과 독립)", first["n_tool_use"], 4)
    check("AskUserQuestion 1건", first["n_ask"], 1)
    check("Workflow 1건", first["n_workflow"], 1)
    check("Gate 발화", first["gate_mentions"], 1)
    check("verify 발화", first["verify_mentions"], 1)
    check("⛔ 발화", first["ban_mentions"], 2)
    check("result_line", first["result_line"], "result")
    check("정정 신호", first["user_correction_signal"], True)
    check("cwd 는 해시 8자만", len(first["cwd_hash"]), 8)
    check("cwd 원문 미저장", "TVING" in json.dumps(first, ensure_ascii=False), False)
    check("메시지 본문 미저장", "빌드 성공" in json.dumps(first, ensure_ascii=False), False)

    second = rows[1]
    check("transcript 없음 — 카운트 0", (second["n_assistant"], second["n_tool_use"]), (0, 0))
    check("transcript 없음 — result_line", second["result_line"], "failed")
    check("transcript 없음 — 정정 신호 False", second["user_correction_signal"], False)

    # ⛔ Stop 재호출(gate block 후 이어가기) — 같은 (session, prompt) 3회 → attempt 1,2,3 (Codex 리뷰 2026-09-06)
    rep_dir = tempfile.mkdtemp(prefix="fz-hook-attempt-")
    for _ in range(3):
        run_hook(io.StringIO(json.dumps({"session_id": "S", "prompt_id": "P", "cwd": "/x", "hook_event_name": "Stop"})), rep_dir)
    attempts = [json.loads(l)["attempt"] for l in open(os.path.join(rep_dir, EVENTS_FILE)) if l.strip()]
    check("Stop 재호출 3회 → attempt 1,2,3", attempts, [1, 2, 3])
    check("events 는 telemetry 디렉토리에만", os.path.isfile(events), True)

    failed = [c for c in checks if not c[1]]
    for name, ok, got, want in checks:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "  got=%r want=%r" % (got, want)))
    print("%d/%d passed" % (len(checks) - len(failed), len(checks)))
    return 1 if failed else 0


class _StringReader(object):
    def __init__(self, text):
        self.text = text

    def read(self):
        return self.text


def main(argv):
    parser = argparse.ArgumentParser(description="fz Stop 훅 — 로그 전용, exit 항상 0")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--telemetry-dir", default=os.environ.get("FZ_TELEMETRY_DIR", DEFAULT_TELEMETRY_DIR)
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # ⛔ argparse 의 exit 2 조차 훅 경로로 새면 안 된다.
        return 0
    if args.self_test:
        return self_test()
    return run_hook(sys.stdin, args.telemetry_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
