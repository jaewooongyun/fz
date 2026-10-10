#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 트랜스크립트 루트는 `--root`(기본 `~/.claude/projects`),
#   fixture 경로는 호출자가 넘긴다. 문서 경로 인용은 주석뿐이며 파일을 열지 않는다 (lint #N6 면제 형태 c).
"""fz_wf_metrics.py — Workflow 실행 1건을 stage 단위로 집계한다. 새로 기록하지 않는다.

왜 신설인가 (plan-final S0a): `experiment-log.md` §5.8 의 사전등록 표가 두 달간 **데이터행 0** 이었다.
임계는 등록됐으나 **재는 주체가 없었다**. `fz_telemetry_report.py` 는 워크플로 wall 을
`agent-*.jsonl` mtime 차분으로 **근사**할 뿐 stage·advisor·재시도를 보지 않는다.

입력 (전부 다른 주체가 이미 쓴 것):
  · `…/subagents/workflows/wf_*/agent-*.jsonl`      — Workflow 도구가 쓴다 (턴·usage·도구)
  · `…/subagents/workflows/wf_*/agent-*.meta.json`  — 같음 (agentType·model)
  · `…/subagents/workflows/wf_*/journal.jsonl`      — 같음 (반환값)

측정 규약 (⛔ 오측정 재발 방지 — 2026-09-11 정정 이력):
  · **advisor 는 content block `type == "advisor_tool_result"` 를 `tool_use_id` 로 중복 제거해 센다.**
    ⛔ `usage.iterations[].type == "advisor_message"` 로 세면 **과소 집계**된다 — iterations 가
    없는 세션이 있다(실측: 20cc838f 를 2회로 세었으나 실제 8회. GPT verify #1 이 지적).
  · **advisor_calls · advisor_stalled** — 호출은 `type == "server_tool_use"`(name=advisor, id=srvtoolu_…)를
    id 로 중복 제거해 세고, 트랜스크립트 끝까지 결과가 오지 않은 호출을 advisor_stalled 로 센다.
    ⛔ advisor 는 결과 기반이라 스톨(결과 없는 호출)이 0 으로 사라진다 — 스톨은 이 열로만 보인다.
    결과는 있는데 그 호출 블록이 없으면(호출 기록 누락) 스톨 수를 0 이 아니라 `unavailable` 로 둔다.
    진행 중인 run 은 아직 결과를 기다리는 호출도 스톨로 센다.
  · dur 은 그 agent 의 첫·끝 timestamp 차분이다. wall 은 **마지막 시도** agent 의 min~max 다.
    시도는 journal.jsonl 의 started·failed·result 순서로 가른다(journal 에 시각이 없다 — 순서만이 근거):
    경계 = 마지막 failed 뒤 첫 started. 경계 앞에서 결과를 내고 경계 뒤에 다시 시작하지 않은 key 의
    agent 는 재사용(reused)으로 wall · 크리티컬 패스 밖에 따로 적는다. failed 가 없으면 단일 시도다(전 agent).
    ⛔ 같은 runId 의 실패 시도와 재개 시도를 합치면 재개 run 2,216s 가 57,767s 로 찍힌다.
    경계를 순서로 정할 수 없으면 wall · 크리티컬 패스를 0 도 전 agent 값도 아닌 UNRUN 으로 둔다(`split_attempts`).
  · 크리티컬 패스 = 직렬 stage 합 + 병렬 그룹별 max. 병렬 그룹은 stage 라벨로 정한다
    (S2 3렌즈 · S3 CC 2콜) — plan-final §1 시간 모델의 분모다. 마지막 시도 agent 만 센다.
  · usage 합산은 `stop_reason` 이 있는 **완결 턴**만 센다(부분 턴 중복 방지).
    ⛔ 완결 턴이 하나도 없는데 journal 에 반환값이 있는 agent 가 있다 — 그 트랜스크립트는
    `stop_reason:None` + `output_tokens:2` 플레이스홀더만 남는다(실측 2026-09-11 wf_5e280968-ffd
    S3-edge: 6,342자 반환인데 합산은 0). 그 경우 `out_tok` 을 **0 이 아니라 `unavailable`** 로 두고
    journal 반환 길이(`result_chars`)를 병기한다. 0 으로 인쇄하면 산출이 있는 스테이지가 빈 것으로 보인다.
  · 값을 얻지 못하면 `unavailable` 로 표기하고 **0 으로 쓰지 않는다**.

⛔ 환경 의존: 트랜스크립트는 머신·사용자별 로컬 기록이다. `--expect` fixture 의 run 은
   이 머신의 기록을 가리키며, 기록이 없으면 `unavailable` + **exit 1**(측정 실패)이다 —
   "값이 맞았다" 와 "볼 수 없었다" 를 같은 성공으로 인쇄하지 않는다.

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import glob
import json
import os
import re
import sys
import tempfile

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")

# 역할 문구 → stage 라벨. Workflow meta 에는 label 이 없어 프롬프트 [역할] 로 판별한다.
# ⛔ 첫 일치가 이긴다(부분 문자열). 현행 배선 규칙을 **일반 규칙보다 앞에** 둔다:
#    · lean2 "영향 범위 + 아키텍처 검증자" 는 아래 "아키텍처 검증자"(S2-arch) 에도 걸린다
#    · 리뷰 Stage 2 "… 리뷰어 — 교차" 는 Stage 1 "… 리뷰어(" 와 앞부분이 같다 — 교차를 먼저 본다
#    · "설계자" 단독은 sweep probe 의 "구조 설계자" 에 걸린다 — "설계자 — 이 과제" 로 좁힌다
#    라벨 공간(L*·R*)을 plan-collaborative 의 S* 와 나눈다 — 섞으면 임계 경로가 이중 합산된다.
STAGE_RULES = (
    ("설계자 — 이 과제", "L1-full"),
    ("경계 케이스 적대자", "L1-edge"),
    ("영향 범위 + 아키텍처 검증자", "L1-impact"),
    ("통합자 —", "L2-merge"),
    ("아키텍처 리뷰어 — 교차", "R2-arch"),
    ("품질 리뷰어 — 교차", "R2-quality"),
    ("아키텍처 리뷰어(review-arch", "R1-arch"),
    ("품질 리뷰어(review-quality", "R1-quality"),
    ("정확성 리뷰어(review-correctness", "R1-correct"),
    ("반론자(review-counter", "R3-counter"),
    ("방향 반박", "S0-reb"),
    ("최종 판정", "S0-fin"),
    ("방향성 도전자", "S0"),
    ("구조 분해", "S1"),
    ("영향 범위 분석가 — CC", "S3-imp"),
    ("경계 케이스 발굴자 — CC", "S3-edge"),
    ("영향 범위 분석가", "S2-impact"),
    ("경계 케이스 발굴자", "S2-edge"),
    ("최종 통합", "S4"),
    ("재검증", "S5"),
    ("아키텍처 검증자", "S2-arch"),
)
SERIAL_STAGES = ("S0", "S0-reb", "S0-fin", "S1", "S4", "S5", "L2-merge", "R3-counter")
PARALLEL_GROUPS = (("S2-impact", "S2-edge", "S2-arch"), ("S3-imp", "S3-edge"),
                   ("L1-full", "L1-edge", "L1-impact"),
                   ("R1-arch", "R1-quality", "R1-correct"), ("R2-arch", "R2-quality"))


def _ts(raw):
    try:
        return datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _stage_of(role: str) -> str:
    for needle, label in STAGE_RULES:
        if needle in role:
            return label
    return "?"


def read_agent(path: str) -> dict:
    """agent-*.jsonl 1개 → 지표. 파싱 불가 줄은 세고 버린다(조용히 넘기지 않는다).

    - Important: 파일은 **이 함수에서 한 번만** 연다(F-335 ⑤). 소비자(ab_ledger wf_summary · --sweep-row)가 쓰는
      메시지별 model · effort(`msg_models`)와 raw `"effort"` 계수(`effort_raw`)도 여기서 함께 낸다 — 소비자가 파일을
      다시 열면 두 판독이 다른 시점의 내용을 볼 수 있다.
    """
    first = last = None
    tools = 0
    usage_by_id = {}
    advisor_ids = set()
    advisor_calls = set()
    tool_names = {}
    so_calls = 0
    so_errors = 0
    pending = {}
    role = ""
    role_found = False
    bad_lines = 0
    total_lines = 0
    msg_models = {}
    effort_raw = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            # raw `"effort"` 계수는 JSON 경로를 추측하지 않는다 — 파싱 불가 줄까지 모든 줄에서 센다(--sweep-row)
            for v in EFFORT_RE.findall(line):
                effort_raw[v] = effort_raw.get(v, 0) + 1
            if not line.strip():
                continue
            total_lines += 1
            try:
                ev = json.loads(line)
            except ValueError:
                bad_lines += 1
                continue
            if not isinstance(ev, dict):
                bad_lines += 1
                continue
            ts = _ts(ev.get("timestamp"))
            if ts is not None:
                if first is None:
                    first = ts
                last = ts
            msg = ev.get("message")
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if ev.get("type") == "user":
                # ⛔ 첫 user 메시지만 보면 안 된다 — 현행 하네스는 `[Workflow harness — user request]` 래퍼를
                #    먼저 쓰고 [역할] 은 다음 메시지(`… computed task`)에 온다(실측 2026-09-26: 전 stage 가 '?').
                #    [역할] 을 찾을 때까지 본다. 끝내 없으면 첫 메시지 앞부분을 남긴다.
                if not role_found:
                    text = content if isinstance(content, str) else ""
                    if isinstance(content, list):
                        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                    m = re.search(r"\[역할\]\s*([^\n]{0,60})", text)
                    if m:
                        role, role_found = m.group(1), True
                    elif not role:
                        role = text[:60]
                if isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict) or b.get("type") != "tool_result":
                            continue
                        name = pending.pop(b.get("tool_use_id"), None)
                        if name == "StructuredOutput":
                            body = json.dumps(b.get("content", ""), ensure_ascii=False)
                            if b.get("is_error") or "InputValidationError" in body:
                                so_errors += 1
            elif ev.get("type") == "assistant":
                # 응답(id)마다 마지막 줄의 model · effort — 같은 id 가 content block 마다 반복된다
                msg_models[msg.get("id") or f"anon-{total_lines}"] = (msg.get("model"), ev.get("effort"))
                usage = msg.get("usage") or {}
                if msg.get("stop_reason"):
                    # ⛔ 응답 1건이 content block 마다 한 줄로 기록되고 **같은 id 에 같은 usage 가 반복**된다.
                    #    줄마다 더하면 과대 집계다(실측 2026-09-26 wf_5717b0f9-6a1 한 워커: 119,597 → 74,518 tok,
                    #    턴 62 → 39). id 별로 한 번만 센다. id 가 없는 줄은 각각 별개 응답으로 본다.
                    usage_by_id[msg.get("id") or f"anon-{total_lines}"] = usage
                if isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "advisor_tool_result":
                            # ⛔ tool_use_id 로 중복 제거 — 같은 응답이 두 줄에 걸쳐 기록될 수 있다
                            advisor_ids.add(b.get("tool_use_id") or f"anon-{len(advisor_ids)}")
                        elif b.get("type") == "server_tool_use" and b.get("name") == "advisor":
                            # 호출 블록 — 결과는 별도 줄(advisor_tool_result.tool_use_id)로 온다. tools 에는 세지 않는다
                            advisor_calls.add(b.get("id") or f"anon-call-{len(advisor_calls)}")
                        elif b.get("type") == "tool_use":
                            tools += 1
                            pending[b.get("id")] = b.get("name")
                            # ⛔ 이름별로 센다 — 총 건수만으로는 *어느* 도구가 안 불렸는지 모른다
                            nm = b.get("name") or "(unnamed)"
                            tool_names[nm] = tool_names.get(nm, 0) + 1
                            if b.get("name") == "StructuredOutput":
                                so_calls += 1
    dur = (last - first).total_seconds() if first and last else None
    turns = len(usage_by_id)
    out_tok = sum(u.get("output_tokens") or 0 for u in usage_by_id.values())
    think = sum((u.get("output_tokens_details") or {}).get("thinking_tokens") or 0 for u in usage_by_id.values())
    cache_r = sum(u.get("cache_read_input_tokens") or 0 for u in usage_by_id.values())
    cache_w = sum(u.get("cache_creation_input_tokens") or 0 for u in usage_by_id.values())
    # ⛔ 호출 블록 없는 결과가 있으면 호출 기록이 빠진 것이다 — 보이는 호출만으로 낸 스톨 수는 0 이 아니라 unavailable
    stalled = None if advisor_ids - advisor_calls else len(advisor_calls - advisor_ids)
    return {
        "complete_turns": turns,
        "file": os.path.basename(path),
        "role": role,
        "stage": _stage_of(role),
        "first": first,
        "last": last,
        "dur": dur,
        "turns": turns,
        "tools": tools,
        "tool_names": tool_names,
        "out_tok": out_tok,
        "thinking": think,
        "cache_read": cache_r,
        "cache_write": cache_w,
        "advisor": len(advisor_ids),
        "advisor_calls": len(advisor_calls),
        "advisor_stalled": stalled,
        "so_calls": so_calls,
        "so_retries": max(0, so_calls - 1),
        "so_errors": so_errors,
        "bad_lines": bad_lines,
        "total_lines": total_lines,
        "msg_models": list(msg_models.values()),
        "effort_raw": effort_raw,
    }


def _empty_result(r) -> bool:
    """journal 결과가 비었거나 오류인가 — 건수만 세면 빈 결과·오류 결과도 완주로 읽힌다."""
    if isinstance(r, str) and r.strip().startswith("{"):
        try:   # JSON 문자열로 기록된 결과도 구조로 본다(오류 필드를 놓치지 않게)
            r = json.loads(r)
        except ValueError:
            pass
    return bool(r in (None, "", {}, []) or (isinstance(r, dict) and (
        set(r) <= {"error"} or r.get("ok") is False or r.get("error") or r.get("isError"))))


def read_journal(folder: str) -> dict:
    """journal.jsonl 을 **한 번** 읽는다(F-335 ⑤) → 반환 길이 · 시도 이벤트 · 결과 줄 수 · started 수 · 빈 결과 수.

    - `result_chars`: agentId → 반환값 길이. 완결 턴 usage 가 없는 agent 의 산출 유무를 가리는 유일한 증거다.
    - `events`: 순서대로 [(type, key, agentId)] (started·failed·result 만). 파일이 없거나 못 읽으면 None.
    - `results`: `"type": "result"` 가 든 **줄** 수(파싱하지 않는다 — 기존 journal_results 열의 정의).
    - `started` · `empty`: 파싱된 started 이벤트 수 · 빈·오류 결과 수(ab_ledger 완주 오라클 입력).
    - Note: 읽기 실패(OSError)는 `read_error` 로 남기고 읽은 데까지의 값을 돌려준다(예외로 죽지 않는다).
    """
    out = {"exists": False, "read_error": False, "result_chars": {}, "events": None, "results": 0, "started": 0,
           "empty": 0}
    path = os.path.join(folder, "journal.jsonl")
    if not os.path.isfile(path):
        return out
    out["exists"] = True
    evs = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"type": "result"' in line or '"type":"result"' in line:
                    out["results"] += 1
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                t = ev.get("type")
                if t in ("started", "failed", "result"):
                    evs.append((t, ev.get("key"), ev.get("agentId")))
                if t == "started":
                    out["started"] += 1
                elif t == "result":
                    r = ev.get("result")
                    txt = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                    out["result_chars"][ev.get("agentId")] = len(txt or "")
                    out["empty"] += _empty_result(r)
    except OSError:
        out["read_error"] = True
        return out
    out["events"] = evs
    return out


def split_attempts(events, agent_ids) -> dict:
    """같은 runId 의 시도를 journal 순서로 가른다 (F-387). journal 에 시각이 없다 — 이벤트 순서만이 근거다.

    경계 = 마지막 failed 뒤 첫 started. 반환 `last` 는 마지막 시도 agentId 집합(None = 단일 시도 — 전 agent),
    `reused` 는 경계 앞에서 결과를 냈고 그 key 가 경계 뒤에 다시 시작하지 않은 agent(결과 재사용),
    `earlier` 는 그 밖의 경계 앞 agent(실패 시도), `failed_attempts` 는 재개 경계 수(마지막 시도 앞의 실패 시도 수 —
    마지막 시도 자신의 완주는 `--expect-agents`·journal_results 가 본다).
    ⛔ 경계를 순서로 정할 수 없으면 `ambiguous` 에 `코드 — 사유` 를 담는다 — wall 을 0 도 전 agent 값도 아닌 UNRUN 으로 둔다:
       resume-unproven        failed 뒤 첫 started 가 실패한 key 의 재기동이 아니다(실패를 넘기고 다음 stage 로 간 것과 재개를 못 가른다)
       no-resume              마지막 failed 뒤 started 가 없다(재개 기록 없이 실패로 끝났다 — 시도의 시작점을 정할 경계가 없다)
       restart-after-boundary 경계 뒤에 같은 key 가 두 번 이상 시작한다(failed 없는 재기동 — 하네스 재시도인지 기록 없는 재개인지 모른다)
       unplaced               트랜스크립트와 journal started 가 짝이 맞지 않는다(시도에 배치할 수 없는 agent)
       key-missing            started · failed 에 key · agentId 가 없다
    failed 가 없으면 단일 시도다 — 기존 정의(전 agent min~max)와 같다. failed 없는 재기동은 이 함수가 보지 못한다.
    """
    single = {"last": None, "reused": [], "earlier": [], "failed_attempts": None if events is None else 0,
              "ambiguous": None}
    if events is None or not any(t == "failed" for t, _, _ in events):
        return single

    def amb(code, why):
        return dict(single, failed_attempts=None, ambiguous=f"{code} — {why}")

    if any(k is None or a is None for t, k, a in events if t in ("started", "failed")):
        return amb("key-missing", "started·failed 이벤트에 key·agentId 가 없다")
    last_ev = {}
    fail_since_start = False
    boundaries = []
    for i, (t, k, a) in enumerate(events):
        if t == "started":
            if fail_since_start:
                if last_ev.get(k) != "failed":
                    return amb("resume-unproven", f"failed 뒤 첫 started(agent {a})가 실패한 key 의 재기동이 아니다 — 시도 안 진행과 재개를 순서로 못 가른다")
                boundaries.append(i)
            fail_since_start = False
        elif t == "failed":
            fail_since_start = True
        if k is not None:
            last_ev[k] = t
    if fail_since_start:
        return amb("no-resume", "마지막 failed 뒤 started 가 없다 — 재개 기록 없이 실패로 끝나 시도 경계를 정할 수 없다")
    b = boundaries[-1]
    after_starts = [(k, a) for t, k, a in events[b:] if t == "started"]
    keys_after = [k for k, _ in after_starts]
    dup = sorted({k for k in keys_after if keys_after.count(k) > 1})
    if dup:
        return amb("restart-after-boundary", f"경계 뒤 같은 key 가 다시 시작한다({len(dup)}개) — failed 없는 재기동이 어느 시도인지 모른다")
    started_ids = {a for t, _, a in events if t == "started"}
    last = {a for _, a in after_starts}
    unplaced = sorted(set(agent_ids) - started_ids)
    missing = sorted(last - set(agent_ids))
    if unplaced or missing:
        return amb("unplaced", f"트랜스크립트와 journal started 가 짝이 맞지 않는다(배치 불가 {len(unplaced)} · 트랜스크립트 없음 {len(missing)})")
    reused = sorted({a for t, k, a in events[:b] if t == "result" and k not in set(keys_after)})
    earlier = sorted({a for t, _, a in events[:b] if t == "started"} - set(reused))
    return {"last": last, "reused": reused, "earlier": earlier, "failed_attempts": len(boundaries), "ambiguous": None}


def _span(agents):
    timed = [a for a in agents if a["first"] and a["last"]]
    if not timed:
        return None
    return (max(a["last"] for a in timed) - min(a["first"] for a in timed)).total_seconds()


def read_wf(folder: str) -> dict:
    """wf_* 폴더 1개 → 집계. 실패 사유는 `errors` 로 반환한다(예외로 죽지 않는다)."""
    errors = []
    files = sorted(glob.glob(os.path.join(folder, "agent-*.jsonl")))
    if not files:
        errors.append("agent-*.jsonl 0건")
    agents = []
    for f in files:
        try:
            agents.append(read_agent(f))
        except OSError as exc:
            errors.append(f"{os.path.basename(f)}: {type(exc).__name__}")
    # journal 반환 길이 — 완결 턴이 없는 agent 의 산출 유무 판정 근거. ⛔ journal 은 여기서 한 번만 읽는다(F-335 ⑤)
    jn = read_journal(folder)
    jr = jn["result_chars"]
    for a in agents:
        aid = a["file"].replace("agent-", "").replace(".jsonl", "")
        a["result_chars"] = jr.get(aid)
        if a["complete_turns"] == 0 and a["result_chars"]:
            # ⛔ 반환은 있는데 완결 턴 usage 가 없다 → 0 이 아니라 unavailable
            a["out_tok"] = None
            a["thinking"] = None
    # meta 에서 model 보강
    for a in agents:
        meta = os.path.join(folder, a["file"].replace(".jsonl", ".meta.json"))
        a["model"] = "unavailable"
        a["agentType"] = "unavailable"
        if os.path.isfile(meta):
            try:
                with open(meta, "r", encoding="utf-8") as fh:
                    m = json.load(fh)
                a["model"] = m.get("model") or "unavailable"
                a["agentType"] = m.get("agentType") or "unavailable"
            except (OSError, ValueError):
                errors.append(f"{os.path.basename(meta)} 파싱 실패")
    # 시도 구분 (F-387) — wall · 크리티컬 패스는 마지막 시도 agent 만으로 잰다
    att = split_attempts(jn["events"],
                         [a["file"].replace("agent-", "").replace(".jsonl", "") for a in agents])
    for a in agents:
        aid = a["file"].replace("agent-", "").replace(".jsonl", "")
        a["attempt"] = (None if att["last"] is None else "last" if aid in att["last"]
                        else "reused" if aid in att["reused"] else "earlier")
    measured = [a for a in agents if att["last"] is None or a["attempt"] == "last"]
    timed = [a for a in measured if a["first"] and a["last"]]
    wall = _span(measured)
    if att["ambiguous"]:
        wall = None
        errors.append(f"UNRUN: 시도 경계 모호 — {att['ambiguous']} · wall · critical_path 미판정")
    elif measured and not timed:
        errors.append("timestamp 있는 agent 0건 — wall unavailable")
    unavail = [a["stage"] for a in agents if a["out_tok"] is None]
    if unavail:
        errors.append(f"토큰 unavailable {len(unavail)}건({', '.join(unavail)}) — 반환은 있으나 완결 턴 usage 없음. 합계는 **하한**이다")
    bad = sum(a["bad_lines"] for a in agents)
    if bad:
        errors.append(f"파싱 불가 줄 {bad}건")
    by_stage = collections.defaultdict(list)
    for a in agents:
        by_stage[a["stage"]].append(a)
    # ⛔ 크리티컬 패스는 마지막 시도만 — stages_seen(필수 stage 대조)은 재사용 stage 를 잃지 않게 전 agent 로 둔다
    crit_stage = collections.defaultdict(list)
    for a in measured:
        crit_stage[a["stage"]].append(a)
    crit = 0.0
    crit_known = not att["ambiguous"]
    for s in SERIAL_STAGES:
        for a in crit_stage.get(s, []):
            if a["dur"] is None:
                crit_known = False
            else:
                crit += a["dur"]
    for group in PARALLEL_GROUPS:
        durs = [a["dur"] for s in group for a in crit_stage.get(s, []) if a["dur"] is not None]
        if durs:
            crit += max(durs)
    results = jn["results"]
    if not jn["exists"]:
        errors.append("journal.jsonl 없음")
    elif jn["read_error"]:
        errors.append("journal.jsonl 읽기 실패")
    effort_raw = {}
    for a in agents:
        for k, v in a["effort_raw"].items():
            effort_raw[k] = effort_raw.get(k, 0) + v
    return {
        "folder": folder,
        "wf": os.path.basename(folder),
        "agents": agents,
        "n_agents": len(agents),
        "wall": wall,
        "critical_path": crit if crit_known and crit > 0 else None,
        "advisor": sum(a["advisor"] for a in agents),
        "advisor_calls": sum(a["advisor_calls"] for a in agents),
        "advisor_stalled": (None if any(a["advisor_stalled"] is None for a in agents)
                            else sum(a["advisor_stalled"] for a in agents)),
        "failed_attempts": att["failed_attempts"],
        "attempt_ambiguous": att["ambiguous"],
        "last_attempt_agents": len(measured) if not att["ambiguous"] else None,
        "failed_span": _span([a for a in agents if a["attempt"] in ("earlier", "reused")]),
        "reused_agents": att["reused"],
        "reused_span": _span([a for a in agents if a["attempt"] == "reused"]),
        "out_tok": sum(a["out_tok"] or 0 for a in agents),
        "thinking": sum(a["thinking"] or 0 for a in agents),
        "cache_read": sum(a["cache_read"] or 0 for a in agents),
        "cache_write": sum(a["cache_write"] or 0 for a in agents),
        "so_retries": sum(a["so_retries"] for a in agents),
        "so_errors": sum(a["so_errors"] for a in agents),
        "journal_results": results,
        "journal_started": jn["started"],
        "journal_empty_results": jn["empty"],
        # --sweep-row 의 effort 칸 — agent 트랜스크립트 raw 줄의 `"effort"` 계수 · 파일 수(못 연 파일 포함)
        "effort_raw": {"counts": effort_raw, "files": len(files)},
        "tokens_partial": bool(unavail),
        "stages_seen": sorted(by_stage.keys()),
        "errors": errors,
    }


def fmt(v, unit=""):
    return "unavailable" if v is None else f"{v}{unit}"


def _secs(wf: dict, key: str, nd=None) -> str:
    """wall · critical_path 칸. 시도 경계가 모호하면 unavailable 이 아니라 UNRUN(미판정)으로 적는다."""
    if wf.get("attempt_ambiguous"):
        return "UNRUN"
    v = wf[key]
    return fmt(None if v is None else (round(v) if nd is None else round(v, nd)), "s")


def _attempt_note(wf: dict) -> str:
    """실패 시도 · 재사용 구간 — wall 과 섞지 않고 따로 적는다. 단일 시도면 빈 문자열."""
    if wf.get("attempt_ambiguous"):
        return f"attempts=UNRUN — 시도 경계 모호: {wf['attempt_ambiguous']}"
    if not wf.get("failed_attempts"):
        return ""
    sp = lambda v: fmt(None if v is None else round(v, 1), "s")
    note = (f"failed_attempts={wf['failed_attempts']}  failed_span={sp(wf['failed_span'])}"
            f"  last_attempt_agents={wf['last_attempt_agents']}/{wf['n_agents']}")
    if wf["reused_agents"]:
        note += f"  reused_agents={','.join(wf['reused_agents'])}  reused_span={sp(wf['reused_span'])}"
    return note + "  (wall · critical_path = 마지막 시도)"


def print_detail(wf: dict) -> None:
    print(f"wf {wf['wf']}  agents={wf['n_agents']}  wall={_secs(wf, 'wall', 1)}"
          f"  critical_path={_secs(wf, 'critical_path', 1)}")
    lb = "≥" if wf["tokens_partial"] else ""
    print(f"  advisor={wf['advisor']}  advisor_calls={wf['advisor_calls']}  advisor_stalled={fmt(wf['advisor_stalled'])}"
          f"  out_tok={lb}{wf['out_tok']:,}  thinking={lb}{wf['thinking']:,}"
          f"  cache_r={wf['cache_read']:,}  cache_w={wf['cache_write']:,}  so_retries={wf['so_retries']}  so_errors={wf['so_errors']}"
          f"  journal_results={wf['journal_results']}")
    if _attempt_note(wf):
        print(f"  {_attempt_note(wf)}")
    order = {s: i for i, s in enumerate(["S0", "S0-reb", "S0-fin", "S1", "S2-impact", "S2-edge", "S2-arch",
                                         "S3-imp", "S3-edge", "S4", "S5",
                                         "L1-full", "L1-edge", "L1-impact", "L2-merge",
                                         "R1-arch", "R1-quality", "R1-correct", "R2-arch", "R2-quality",
                                         "R3-counter", "?"])}
    for a in sorted(wf["agents"], key=lambda x: (order.get(x["stage"], 99), x["file"])):
        ot = "unavail" if a["out_tok"] is None else f"{a['out_tok']:,}"
        th = "unavail" if a["thinking"] is None else f"{a['thinking']:,}"
        rc = f" ret={a['result_chars']:,}자" if a.get("result_chars") else ""
        st = f" stall={fmt(a['advisor_stalled'])}" if a["advisor_stalled"] != 0 else ""
        at = {"earlier": " [failed-attempt]", "reused": " [reused]"}.get(a.get("attempt"), "")
        print(f"    {a['stage']:9} {a['model']:8} dur={fmt(round(a['dur'], 1) if a['dur'] is not None else None, 's'):>9}"
              f" turns={a['turns']:>3} tools={a['tools']:>3} out={ot:>9} think={th:>9}"
              f" adv={a['advisor']}{st} so={a['so_calls']}/{a['so_errors']}{rc}{at}")
    for e in wf["errors"]:
        print(f"  ⚠️ {e}")


def print_row(wf: dict) -> None:
    """experiment-log §5.7 fz-plan 테이블 행 형식 (agentCalls·nullCount·stages·fallback·wall-clock)."""
    stages = len([s for s in wf["stages_seen"] if s != "?"])
    lb = "≥" if wf["tokens_partial"] else ""
    # ⛔ 열은 늘리지 않는다 — 스톨 · 실패 시도는 마지막 비고 칸에 덧붙인다(wall 칸은 마지막 시도 값)
    sec = lambda v: fmt(None if v is None else round(v), "s")
    att = ""
    if wf.get("attempt_ambiguous"):
        att = " · 시도 경계 모호(wall UNRUN)"
    elif wf.get("failed_attempts"):
        att = f" · failed_attempts {wf['failed_attempts']} (실패 구간 {sec(wf['failed_span'])})"
        if wf["reused_agents"]:
            att += f" · reused {len(wf['reused_agents'])} ({sec(wf['reused_span'])})"
    print(f"| N | DATE | {wf['n_agents']} | {max(0, wf['n_agents'] - wf['journal_results'])} | "
          f"{stages} | 0 | {_secs(wf, 'wall')} | "
          f"advisor {wf['advisor']} · advisor_stalled {fmt(wf['advisor_stalled'])} · so_retries {wf['so_retries']} · out_tok {lb}{wf['out_tok']:,} "
          f"(thinking {wf['thinking']:,}) · critical_path {_secs(wf, 'critical_path')}{att} |")


def resolve(root: str, session_glob: str, wf: str):
    hits = sorted(glob.glob(os.path.join(root, "*", session_glob, "subagents", "workflows", wf)))
    hits = [h for h in hits if os.path.isdir(h)]
    return hits[0] if hits else None


def cmd_expect(args) -> int:
    try:
        with open(args.expect, "r", encoding="utf-8") as fh:
            spec = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"FAIL: fixture 를 읽을 수 없다: {args.expect} ({type(exc).__name__})")
        return 1
    tol = float(spec.get("tolerance_seconds", 1.0))
    fails, checked = [], 0
    for run in spec.get("runs", []):
        folder = resolve(args.root, run["session_glob"], run["wf"])
        if folder is None:
            fails.append(f"{run['id']}: unavailable (기록 없음 — 측정 실패, 0 으로 쓰지 않는다)")
            continue
        wf = read_wf(folder)
        checked += 1
        if wf["wall"] is None:
            fails.append(f"{run['id']}: wall unavailable")
        elif abs(wf["wall"] - run["wall_s"]) > tol:
            fails.append(f"{run['id']}: wall {wf['wall']:.1f}s ≠ {run['wall_s']}s (±{tol})")
        if wf["n_agents"] != run["agents"]:
            fails.append(f"{run['id']}: agents {wf['n_agents']} ≠ {run['agents']}")
        if wf["advisor"] != run["advisor"]:
            fails.append(f"{run['id']}: advisor {wf['advisor']} ≠ {run['advisor']}")
        # 스톨 · 시도 열은 fixture 가 값을 적었을 때 비교한다 — 적힌 값을 읽지 않고 METRICS_OK 를 내지 않게
        for key in ("advisor_calls", "advisor_stalled", "failed_attempts"):
            if key in run and wf.get(key) != run[key]:
                fails.append(f"{run['id']}: {key} {fmt(wf.get(key))} ≠ {run[key]}")
        if args.verbose:
            print_detail(wf)
    if not spec.get("runs"):
        print("FAIL: fixture 에 runs 가 없다 (0/0 통과 금지)")
        return 1
    for f in fails:
        print(f"  FAIL {f}")
    if fails:
        print(f"측정 불일치 {len(fails)}건 / run {len(spec['runs'])}개 중 {checked}개 판정")
        return 1
    print(f"METRICS_OK ({checked}/{len(spec['runs'])} run 재현 — wall ±{tol}s · agents · advisor)")
    return 0


def _write_probe(root: str, kind: str) -> None:
    """self-test fixture — 정상 1건 + 고장 2건(빈 폴더·손상 jsonl)."""
    folder = os.path.join(root, "proj", "sess-probe", "subagents", "workflows", "wf_probe")
    os.makedirs(folder, exist_ok=True)
    if kind == "empty":
        return
    p = os.path.join(folder, "agent-a1.jsonl")
    if kind == "corrupt":
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("{not json at all\n")
        return
    if kind == "no-turns":
        # 완결 턴 0 — stop_reason 없음 + output_tokens 플레이스홀더. 반환은 journal 에만 있다.
        rows = [
            {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
             "message": {"content": "[역할] 경계 케이스 발굴자 — CC 교차"}},
            {"type": "assistant", "timestamp": "2026-09-11T00:07:00Z",
             "message": {"content": [{"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": {}}],
                         "usage": {"output_tokens": 2}}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:plan-edge-case", "model": "opus"}, fh)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "result", "agentId": "a1", "result": {"links": [{"sourceId": "E:E1", "finding": "x" * 500}], "additions": []}}, ensure_ascii=False) + "\n")
        return
    if kind == "sweep-effort":
        rows = [
            {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
             "message": {"content": "[역할] 구조 설계자"}},
            {"type": "assistant", "timestamp": "2026-09-11T00:02:00Z",
             "message": {"stop_reason": "tool_use", "effort": "xhigh",
                         "content": [{"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": {}}],
                         "usage": {"output_tokens": 70, "output_tokens_details": {"thinking_tokens": 20}}}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:plan-structure", "model": "opus"}, fh)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write('{"type": "result", "agentId": "a1", "result": "x"}\n')
        return
    if kind in ("stall", "resume", "no-resume"):
        # stall: advisor 호출 2(srvtoolu_A1 결과 2줄 중복 · srvtoolu_A2 결과 없음) — 실 블록 꼴(server_tool_use + 별도 줄 결과)
        # resume · no-resume: 같은 key 의 실패 시도(0~6000s) 뒤 재개 시도(50000~50600s) / 재개 없이 실패로 끝남
        def agent(name, rows, meta="fz:plan-structure"):
            with open(os.path.join(folder, f"agent-{name}.jsonl"), "w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            with open(os.path.join(folder, f"agent-{name}.meta.json"), "w", encoding="utf-8") as fh:
                json.dump({"agentType": meta, "model": "opus"}, fh)
        t = lambda sec: (datetime.datetime(2026, 10, 1) + datetime.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
        role = {"type": "user", "timestamp": t(0), "message": {"content": "[역할] 설계자 — 이 과제의 계획"}}
        if kind == "stall":
            call = lambda i: {"type": "server_tool_use", "id": f"srvtoolu_{i}", "name": "advisor", "input": {}}
            res = {"type": "advisor_tool_result", "tool_use_id": "srvtoolu_A1", "content": {"type": "advisor_result"}}
            agent("a1", [role] + [{"type": "assistant", "timestamp": t(sec), "message": {"id": "m1", "content": [b]}}
                                  for sec, b in ((10, call("A1")), (60, res), (60, res), (90, call("A2")))])
            journal = [{"type": "started", "key": "k1", "agentId": "a1"}]
        else:
            done = {"type": "assistant", "timestamp": t(50600),
                    "message": {"id": "m2", "stop_reason": "end_turn", "usage": {"output_tokens": 9}, "content": []}}
            agent("a1", [role, {"type": "assistant", "timestamp": t(6000), "message": {"id": "m1", "content": []}}])
            journal = [{"type": "started", "key": "k1", "agentId": "a1"}, {"type": "failed", "key": "k1", "agentId": "a1"}]
            if kind == "resume":
                agent("a2", [dict(role, timestamp=t(50000)), done])
                journal += [{"type": "started", "key": "k1", "agentId": "a2"},
                            {"type": "result", "key": "k1", "agentId": "a2", "result": "x"}]
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            for ev in journal:
                fh.write(json.dumps(ev) + "\n")
        return
    if kind in ("mcp-ok", "mcp-dead", "mcp-unrun", "mcp-nocontrol"):
        # ⛔ 세 픽스처는 **도구 호출 조합만** 다르다 — 판정이 그 조합에서만 갈리는지 보기 위해서다.
        calls = {"mcp-ok": [("mcp__plugin_fz_serena__find_symbol", "s1"), ("Read", "r1")],
                 "mcp-dead": [("Read", "r1"), ("Grep", "g1")],
                 "mcp-unrun": [],
                 # ⛔ 작업은 했지만 **대조 심볼이 없다** — 부재를 주장할 근거가 없는 경로
                 "mcp-nocontrol": [("Grep", "g1")]}[kind]
        blocks = [{"type": "tool_use", "id": i, "name": nm, "input": {}} for nm, i in calls]
        blocks.append({"type": "tool_use", "id": "so1", "name": "StructuredOutput", "input": {}})
        rows = [
            {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
             "message": {"content": "[역할] 심볼 탐색자"}},
            {"type": "assistant", "timestamp": "2026-09-11T00:01:00Z",
             "message": {"stop_reason": "tool_use", "content": blocks,
                         "usage": {"output_tokens": 50}}},
        ]
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
            json.dump({"agentType": "fz:search-symbolic", "model": "opus"}, fh)
        with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
            fh.write('{"type": "result", "agentId": "a1", "result": "x"}\n')
        return
    rows = [
        {"type": "user", "timestamp": "2026-09-11T00:00:00Z",
         "message": {"content": "[역할] 방향성 도전자(review-direction 렌즈)"}},
        {"type": "assistant", "timestamp": "2026-09-11T00:01:00Z",
         "message": {"stop_reason": "tool_use", "content": [
             {"type": "advisor_tool_result", "tool_use_id": "adv1"},
             {"type": "tool_use", "id": "t1", "name": "StructuredOutput", "input": {}}],
             "usage": {"output_tokens": 100, "output_tokens_details": {"thinking_tokens": 40},
                       "cache_read_input_tokens": 10, "cache_creation_input_tokens": 5}}},
        {"type": "assistant", "timestamp": "2026-09-11T00:01:30Z",
         "message": {"content": [{"type": "advisor_tool_result", "tool_use_id": "adv1"}]}},
    ]
    with open(p, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(os.path.join(folder, "agent-a1.meta.json"), "w", encoding="utf-8") as fh:
        json.dump({"agentType": "fz:review-direction", "model": "fable"}, fh)
    with open(os.path.join(folder, "journal.jsonl"), "w", encoding="utf-8") as fh:
        fh.write('{"type": "started", "agentId": "a1"}\n{"type": "result", "agentId": "a1", "result": "x"}\n')



# ── --sweep-row (S15) ───────────────────────────────────────────────────────
#  `experiment-log.md` §5.8 ⑥ 의 행을 **측정값으로** 만든다.
#  ⛔ 이 표가 두 달간 비어 있던 원인이 *재는 주체 부재* 였다 — 손으로 옮기면 안 옮긴다.
#  ⛔ 사람이 판정하는 칸(arm·G2 5축·채점자 판정·판정)은 **채우지 않는다.** 플레이스홀더로 남겨
#     측정값과 판단을 섞지 않는다. 섞으면 어느 칸이 실측인지 구별되지 않는다.
# 트랜스크립트 raw 라인의 `effort` 값 — ⛔ JSON 경로를 **추측하지 않는다**(키 위치가 바뀌어도 잡히게). 0건이면 값을 지어내지
#   않고 `unavailable` 로 보고한다(부재 주장에 근거를 남긴다). 계수는 read_agent 가 파일을 읽을 때 함께 낸다(F-335 ⑤)
EFFORT_RE = re.compile(r'"effort"\s*:\s*"([A-Za-z]+)"')


def cmd_sweep_row(args) -> int:
    folder = args.wf if (args.wf and os.path.isdir(args.wf)) else (
        resolve(args.root, args.session, args.wf) if args.wf else None)
    if folder is None:
        print(f"UNRUN: wf 폴더를 찾지 못했다 (wf={args.wf} root={args.root}) — 미판정")
        return 2
    wf = read_wf(folder)
    if not wf["agents"]:
        print("UNRUN: agent 트랜스크립트 0건 — 측정 실패 (⛔ 통과 아님)")
        return 2
    eff = wf["effort_raw"]
    if eff["counts"]:
        top = sorted(eff["counts"].items(), key=lambda kv: -kv[1])
        effort = " · ".join(f"`{k}`×{v}" for k, v in top)
    else:
        effort = f"unavailable (raw `\"effort\"` 0건 · 파일 {eff['files']}개 — ⛔ 0 으로 쓰지 않는다)"
    lb = "≥" if wf["tokens_partial"] else ""
    ot = f"{lb}{wf['out_tok']:,}" if wf["out_tok"] is not None else "unavailable"
    th = f"{wf['thinking']:,}" if wf["thinking"] is not None else "unavailable"
    print("| N | DATE | ARM(사람) | " + effort + " | "
          + _secs(wf, "wall") + " | "
          + _secs(wf, "critical_path") + " | "
          + ot + " | " + th + " | " + str(wf["advisor"]) + " | "
          "G2 5축(사람) | 채점자 판정(사람) | 판정(사람) |")
    # 스톨 · 시도 정보는 표 밖 주석 줄에만 — §5.8 표 열은 그대로 둔다
    print(f"# wf={os.path.basename(folder)} · agents={len(wf['agents'])} · journal_results={wf['journal_results']}"
          f" · advisor_stalled={fmt(wf['advisor_stalled'])} · failed_attempts={fmt(wf['failed_attempts'])}")
    if wf["errors"]:
        print("# ⛔ errors: " + " · ".join(wf["errors"]))
    return 0


# ── --mcp-audit (S5) ────────────────────────────────────────────────────────
#  워커가 **선언된 MCP 도구를 실제로 불렀는가**. 배선이 죽으면 호출이 0이 되는데,
#  산출물에는 표시가 없다(실측: serena 배선 2곳이 죽은 채로 리포트가 정상으로 읽혔다).
#
#  ⛔ **0건을 그대로 경보로 쓰지 않는다.** 0건은 「배선 죽음」과 「그 워커가 원래 안 쓸 일」을
#     구별하지 못한다. 그래서 **대조 심볼**(positive control)을 요구한다 — 같은 런에서
#     `Read` 가 불렸다면 워커는 파일 작업을 했고, 그런데도 serena 가 0이면 배선을 의심한다.
#     대조가 없으면 경보가 아니라 **미판정**이다.
MCP_PREFIXES = ("mcp__plugin_fz_serena__", "mcp__serena__")
CONTROL_TOOL = "Read"
NOT_WORK = ("StructuredOutput",)   # 산출 제출은 "도구 작업"이 아니다


def audit_counts(agents) -> dict:
    serena = 0
    control = 0
    work = 0
    names = {}
    for a in agents:
        for nm, c in (a.get("tool_names") or {}).items():
            names[nm] = names.get(nm, 0) + c
            if nm.startswith(MCP_PREFIXES):
                serena += c
            if nm == CONTROL_TOOL:
                control += c
            if nm not in NOT_WORK:
                work += c
    return {"serena": serena, "control": control, "work": work, "names": names}


def cmd_mcp_audit(args) -> int:
    folder = args.wf if (args.wf and os.path.isdir(args.wf)) else (
        resolve(args.root, args.session, args.wf) if args.wf else None)
    if folder is None:
        # ⛔ 대상이 없는 것은 통과가 아니다
        print(f"UNRUN: wf 폴더를 찾지 못했다 (wf={args.wf} root={args.root}) — 미판정")
        return 2
    wf = read_wf(folder)
    c = audit_counts(wf["agents"])
    top = ", ".join(f"{k}={v}" for k, v in sorted(c["names"].items(), key=lambda kv: -kv[1])[:6]) or "(없음)"
    print(f"wf={os.path.basename(folder)} · agents={len(wf['agents'])}")
    print(f"  serena 호출 {c['serena']} · 대조({CONTROL_TOOL}) {c['control']} · 도구작업 {c['work']}")
    print(f"  도구 분포: {top}")

    if c["work"] == 0:
        print("UNRUN: 도구 작업이 0건이다 — 배선 죽음과 '할 일이 없었음'을 구별할 수 없다 (⛔ 통과 아님)")
        return 2
    if c["serena"] == 0 and c["control"] == 0:
        print(f"UNRUN: serena 0건이지만 대조 심볼({CONTROL_TOOL})도 0건이다 — "
              "부재를 주장할 근거가 없다 (⛔ 통과 아님)")
        return 2
    if c["serena"] == 0:
        print(f"MCP_WIRING_SUSPECT: serena 0건인데 {CONTROL_TOOL} {c['control']}건 — "
              "워커는 파일 작업을 했다. 배선을 확인하라")
        return 1
    print(f"MCP_AUDIT_OK (serena {c['serena']}건 · 대조 {c['control']}건)")
    return 0


def cmd_self_test(args) -> int:
    import shutil
    import subprocess
    me = os.path.abspath(__file__)
    passed, fails = 0, []

    def run(kind, spec_runs, want_exit, want_text=None):
        nonlocal passed
        root = tempfile.mkdtemp(prefix="fzwf-")
        try:
            _write_probe(root, kind)
            fx = os.path.join(root, "expected.json")
            with open(fx, "w", encoding="utf-8") as fh:
                json.dump({"tolerance_seconds": 1.0, "runs": spec_runs}, fh)
            proc = subprocess.run([sys.executable, me, "--expect", fx, "--root", root],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            out = (proc.stdout or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_text and want_text not in out:
                why.append(f"출력에 {want_text!r} 없음: {out.strip()[:120]}")
            if why:
                fails.append(f"{kind}/{want_exit}: {'; '.join(why)}")
            else:
                passed += 1
        finally:
            shutil.rmtree(root, ignore_errors=True)

    good = [{"id": "probe", "session_glob": "sess-probe", "wf": "wf_probe",
             "wall_s": 90.0, "agents": 1, "advisor": 1}]
    # ① 정상: 값 일치 → METRICS_OK (advisor 는 중복 id 를 1로 센다 — 블록 2개, 고유 1개)
    run("good", good, 0, "METRICS_OK")
    # ② 값 불일치 → 실패 (조용한 통과 금지)
    run("good", [dict(good[0], wall_s=1.0)], 1, "wall")
    run("good", [dict(good[0], advisor=7)], 1, "advisor")
    # ③ 기록 없음 → unavailable + exit 1 (측정 실패를 0 으로 쓰지 않는다)
    run("good", [{"id": "missing", "session_glob": "nope*", "wf": "wf_none",
                  "wall_s": 1.0, "agents": 1, "advisor": 0}], 1, "unavailable")
    # ④ 빈 폴더 → agent 0건 → wall unavailable + exit 1
    run("empty", good, 1, "unavailable")
    # ⑤ 손상 jsonl → 파싱 불가 → exit 1
    run("corrupt", good, 1, None)
    # ⑥ runs 빈 배열 → 0/0 통과 금지
    run("good", [], 1, "runs 가 없다")
    # ⑦ ⛔ 완결 턴 없는 agent — 반환은 있는데 usage 가 플레이스홀더뿐이면 0 이 아니라 unavailable
    #    (실측 wf_5e280968-ffd S3-edge: 6,342자 반환 · out_tok 0 으로 인쇄됐다)
    root = tempfile.mkdtemp(prefix="fzwf-nt-")
    try:
        _write_probe(root, "no-turns")
        folder = os.path.join(root, "proj", "sess-probe", "subagents", "workflows", "wf_probe")
        wf = read_wf(folder)
        a = wf["agents"][0]
        if a["out_tok"] is None and a["result_chars"] and wf["tokens_partial"]:
            passed += 1
        else:
            fails.append(f"no-turns: out_tok={a['out_tok']} (기대 None) · result_chars={a.get('result_chars')} · partial={wf['tokens_partial']}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    # ⑧~⑩ --mcp-audit 3분 판정 — 도구 조합만 바꿔 세 판정을 각각 확인한다
    def audit(kind, want_exit, want_text):
        nonlocal passed
        r2 = tempfile.mkdtemp(prefix="fzwf-mcp-")
        try:
            _write_probe(r2, kind)
            proc = subprocess.run([sys.executable, me, "--mcp-audit", "--root", r2,
                                   "--wf", "wf_probe", "--session", "*"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            out = (proc.stdout or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_text not in out:
                why.append(f"출력에 {want_text!r} 없음: {out.strip()[:140]}")
            if why:
                fails.append(f"mcp-audit/{kind}: " + " · ".join(why))
            else:
                passed += 1
        finally:
            shutil.rmtree(r2, ignore_errors=True)

    audit("mcp-ok", 0, "MCP_AUDIT_OK")
    audit("mcp-dead", 1, "MCP_WIRING_SUSPECT")
    audit("mcp-unrun", 2, "도구 작업이 0건")
    audit("mcp-nocontrol", 2, "대조 심볼")

    # ⑪~⑬ --sweep-row — 측정값과 사람 판정 칸이 섞이지 않는지, 부재를 0 으로 쓰지 않는지
    def sweep(kind, want_exit, want_text):
        nonlocal passed
        r3 = tempfile.mkdtemp(prefix="fzwf-sw-")
        try:
            _write_probe(r3, kind)
            proc = subprocess.run([sys.executable, me, "--sweep-row", "--root", r3,
                                   "--wf", "wf_probe", "--session", "*"],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            out = (proc.stdout or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_text not in out:
                why.append(f"출력에 {want_text!r} 없음: {out.strip()[:140]}")
            if why:
                fails.append(f"sweep-row/{kind}: " + " · ".join(why))
            else:
                passed += 1
        finally:
            shutil.rmtree(r3, ignore_errors=True)

    sweep("sweep-effort", 0, "`xhigh`×1")     # 실측된 effort 가 행에 들어간다
    sweep("mcp-ok", 0, "unavailable (raw")    # ⛔ 부재를 0 으로 쓰지 않는다
    sweep("empty", 2, "UNRUN")                # agent 0건은 통과가 아니다

    # ⑭ stage 규칙 — 현행 워크플로의 실제 [역할] 문구(앞 60자 이내)가 기대 라벨로 가는가.
    #    ⛔ 첫 일치 규칙이라 순서가 틀리면 조용히 다른 라벨이 붙는다(교차 콜이 Stage 1 로 읽힌다).
    stage_cases = (
        ("설계자 — 이 과제의 계획을 **혼자** 끝낸다. 방향 판정·영향 범위·", "L1-full"),
        ("경계 케이스 적대자 — 이 접근이 **어디서 깨지는가**만 판다.", "L1-edge"),
        ("영향 범위 + 아키텍처 검증자 — **이 변경이 어디까지 퍼지는가**와", "L1-impact"),
        ("통합자 — 적대 렌즈와 영향·아키 렌즈의 발견을 기존 계획에", "L2-merge"),
        ("아키텍처 리뷰어(review-arch 렌즈) — 설계 결정·레이어 위반·확장성", "R1-arch"),
        ("품질 리뷰어(review-quality 렌즈) — 코드 품질·dead code·성능", "R1-quality"),
        ("정확성 리뷰어(review-correctness 렌즈) — 요구사항 충족·로직", "R1-correct"),
        ("아키텍처 리뷰어 — 교차 조정", "R2-arch"),
        ("품질 리뷰어 — 교차 보충", "R2-quality"),
        ("반론자(review-counter 렌즈) — Devil's Advocate", "R3-counter"),
        ("아키텍처 검증자(review-arch 렌즈)", "S2-arch"),          # 옛 배선 — 라벨 불변
        ("설계자(plan-structure 렌즈) — 방향 반박", "S0-reb"),
        ("구조 설계자", "?"),                                        # sweep probe — 새 규칙에 걸리면 안 된다
    )
    bad_stage = [f"{r[:18]}…→{_stage_of(r)}(기대 {want})" for r, want in stage_cases if _stage_of(r) != want]
    if bad_stage:
        fails.append("stage 규칙: " + " · ".join(bad_stage))
    else:
        passed += 1

    # ⑮ ⛔ usage 중복 — 같은 id 의 content block 줄 3개가 usage 를 반복해도 응답 1건으로 센다.
    #    같은 fixture 로 하네스 래퍼 뒤의 [역할] 도 본다(첫 메시지만 보면 stage 가 '?').
    root = tempfile.mkdtemp(prefix="fzwf-dup-")
    try:
        p = os.path.join(root, "agent-d1.jsonl")
        u = {"output_tokens": 100, "output_tokens_details": {"thinking_tokens": 40}}
        rows = [{"type": "user", "timestamp": "2026-09-26T00:00:00Z",
                 "message": {"content": "[Workflow harness — user request] relayed"}},
                {"type": "user", "timestamp": "2026-09-26T00:00:00Z",
                 "message": {"content": "[Workflow harness — computed task]\n[역할] 통합자 — x"}}]
        rows += [{"type": "assistant", "timestamp": f"2026-09-26T00:00:0{i}Z",
                  "message": {"id": "msg_1", "stop_reason": "tool_use", "usage": u,
                              "content": [{"type": kind}]}} for i, kind in enumerate(("thinking", "text", "tool_use"), 1)]
        rows.append({"type": "assistant", "timestamp": "2026-09-26T00:00:09Z",
                     "message": {"id": "msg_2", "stop_reason": "end_turn", "usage": {"output_tokens": 7}, "content": []}})
        with open(p, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        a = read_agent(p)
        if (a["turns"], a["out_tok"], a["thinking"], a["stage"]) == (2, 107, 40, "L2-merge"):
            passed += 1
        else:
            fails.append(f"usage 중복: turns={a['turns']} out_tok={a['out_tok']} thinking={a['thinking']} "
                         f"stage={a['stage']} (기대 2·107·40·L2-merge)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ⑯ advisor 스톨 (F-382) — 호출 2 · 결과 1(2줄 중복) → advisor 1(결과 기반 불변) · calls 2 · stalled 1.
    #    결과만 있고 호출 블록이 없는 ① probe 는 스톨 수를 0 이 아니라 unavailable(None)로 둔다.
    #    --expect 가 적힌 advisor_stalled 를 비교하는가(틀린 값 0 → exit 1)
    def wf_of(kind):
        r = tempfile.mkdtemp(prefix="fzwf-at-")
        _write_probe(r, kind)
        return r, read_wf(os.path.join(r, "proj", "sess-probe", "subagents", "workflows", "wf_probe"))

    r4, wf = wf_of("stall")
    try:
        got = (wf["advisor"], wf["advisor_calls"], wf["advisor_stalled"])
        r5, wg = wf_of("good")
        shutil.rmtree(r5, ignore_errors=True)
        if got == (1, 2, 1) and wg["advisor_stalled"] is None and wg["advisor"] == 1:
            passed += 1
        else:
            fails.append(f"advisor 스톨: (advisor, calls, stalled)={got} (기대 1·2·1) · 호출 블록 없는 probe stalled={wg['advisor_stalled']} (기대 None)")
    finally:
        shutil.rmtree(r4, ignore_errors=True)
    st_run = {"id": "probe", "session_glob": "sess-probe", "wf": "wf_probe", "wall_s": 90.0, "agents": 1,
              "advisor": 1, "advisor_calls": 2, "advisor_stalled": 1}
    run("stall", [st_run], 0, "METRICS_OK")
    run("stall", [dict(st_run, advisor_stalled=0)], 1, "advisor_stalled 1 ≠ 0")

    # ⑰ 시도 구분 (F-387) — 실패 시도 + 재개: wall · critical_path 는 마지막 시도(600s) · failed_attempts 1 ·
    #    재개 없이 실패로 끝난 run 은 경계를 정할 수 없어 wall · critical_path UNRUN(None) — 0 도 전 agent 값도 아니다
    r6, wr = wf_of("resume")
    r7, wn = wf_of("no-resume")
    try:
        got = (wr["wall"], wr["critical_path"], wr["failed_attempts"], wr["attempt_ambiguous"],
               wn["wall"], wn["critical_path"], bool(wn["attempt_ambiguous"]))
        if got == (600.0, 600.0, 1, None, None, None, True):
            passed += 1
        else:
            fails.append(f"시도 구분: (wall, crit, failed_attempts, ambiguous | 무재개 wall, crit, ambiguous)={got} "
                         f"(기대 600·600·1·None | None·None·True)")
    finally:
        shutil.rmtree(r6, ignore_errors=True)
        shutil.rmtree(r7, ignore_errors=True)

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    if fails:
        print(f"fz_wf_metrics self-test {passed}/{total} passed")
        return 1
    print(f"SELFTEST_OK (fz_wf_metrics self-test {passed}/{total} — 양성 1 · 음성 5 · mcp-audit 4 · sweep-row 3"
          f" · stage 규칙 1 · usage 중복 1 · advisor 스톨 3 · 시도 구분 1)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Workflow 실행 stage 집계 (읽기 전용)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="트랜스크립트 루트 (기본 ~/.claude/projects)")
    ap.add_argument("--wf", help="wf_* 폴더명 또는 절대경로 — 1건 상세")
    ap.add_argument("--session", default="*", help="--wf 와 함께 쓰는 세션 glob")
    ap.add_argument("--expect", help="fixture JSON 과 대조 (성공 시 METRICS_OK)")
    ap.add_argument("--self-test", action="store_true", help="양성·음성 self-test")
    ap.add_argument("--sweep-row", action="store_true",
                    help="experiment-log §5.8 ⑥ 행을 측정값으로 출력 (사람 판정 칸은 플레이스홀더)")
    ap.add_argument("--mcp-audit", action="store_true",
                    help="선언된 MCP 도구를 워커가 실제로 불렀는가 (0=OK · 1=배선 의심 · 2=미판정)")
    ap.add_argument("--row", action="store_true", help="experiment-log §5.7 행 형식 출력")
    ap.add_argument("--summary", action="store_true", help="stage 상세 출력")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--expect-agents", type=int, metavar="N",
                    help="완주 오라클 — agents 와 journal_results 가 둘 다 N 이 아니면 exit 1 "
                         "(⛔ 잘린 run 은 오류 없이 그럴듯한 wall 을 낸다 — F-203)")
    args = ap.parse_args()

    if args.self_test:
        return cmd_self_test(args)
    if args.expect:
        return cmd_expect(args)
    if args.mcp_audit:
        return cmd_mcp_audit(args)
    if args.sweep_row:
        return cmd_sweep_row(args)
    if args.wf:
        folder = args.wf if os.path.isdir(args.wf) else resolve(args.root, args.session, args.wf)
        if folder is None:
            print(f"FAIL: wf 폴더를 찾지 못했다: {args.wf} (root={args.root})")
            return 1
        wf = read_wf(folder)
        if args.row:
            print_row(wf)
        else:
            print_detail(wf)
        if args.expect_agents is not None:
            # ⛔ 완주 오라클. 스크립트가 선언한 콜 수와 대조하지 않으면 잘린 run 이
            #    정상으로 읽힌다 — 2026-09-13 실측: `claude -p` 가 600s 에서 끊은 run 이
            #    exit 0 · 오류 키워드 0건 · wall=621.9s(baseline 의 -54%) 로 인쇄됐다.
            n_res = wf["journal_results"]
            bad = []
            if wf["n_agents"] != args.expect_agents:
                bad.append(f"agents={wf['n_agents']}")
            if n_res != args.expect_agents:
                bad.append(f"journal_results={n_res}")
            if bad:
                print(f"INCOMPLETE: 기대 {args.expect_agents} — " + " · ".join(bad)
                      + " ⛔ 이 run 의 wall 을 기록하지 말 것")
                return 1
            print(f"COMPLETE: agents={wf['n_agents']} journal_results={n_res} (기대 {args.expect_agents})")
        return 1 if wf["errors"] and args.summary is False and wf["wall"] is None else 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
