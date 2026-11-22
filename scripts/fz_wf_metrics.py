#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트(이 파일의 `scripts/` 위 폴더)는 기본 에이전트 정의 폴더와 훑기의 설치 시각에만 쓰고, 못 읽으면
#   그 규칙 없이 센다. 트랜스크립트 루트는 `--root`(기본 `~/.claude/projects`),
#   fixture 경로는 호출자가 넘긴다. 문서 경로 인용은 주석뿐이며 파일을 열지 않는다 (lint #N6 면제 형태 c). 에이전트 정의 폴더는
#   `--agents-dir`(기본 = 이 파일이 든 플러그인의 `agents/` · 종료 훅은 자기 플러그인의 것을 넘긴다)이다.
"""fz_wf_metrics.py — Workflow 실행 1건을 stage 단위로 집계한다. 새로 기록하지 않는다 — 종료 훅 훑기(`--mcp-audit --sweep`)만
저장소 밖 기록(`--record`)에 한 줄을 덧붙이고 그 옆 열쇠 파일을 고친다.

왜 신설인가 (plan-final S0a): `experiment-log.md` §5.8 의 사전등록 표가 두 달간 **데이터행 0** 이었다.
임계는 등록됐으나 **재는 주체가 없었다**. `fz_telemetry_report.py` 는 워크플로 wall 을
`agent-*.jsonl` mtime 차분으로 **근사**할 뿐 stage·advisor·재시도를 보지 않는다.

입력 (전부 다른 주체가 이미 쓴 것):
  · `…/subagents/workflows/wf_*/agent-*.jsonl`      — Workflow 도구가 쓴다 (턴·usage·도구)
  · `…/subagents/workflows/wf_*/agent-*.meta.json`  — 같음 (agentType·model)
  · `…/subagents/workflows/wf_*/journal.jsonl`      — 같음 (반환값 · 시작 사건의 단계 라벨)
  · `…/subagents/agent-*.jsonl` · `.meta.json`       — 워크플로 밖 직접 호출(`--mcp-audit --direct`)
  · `evidence/tools.md` 첫 줄                       — 세션 시작 상태 기록(`--mcp-audit --tools-md` · `--state` · Lead 가 쓴다)
  · 세션 기록 폴더 `…/<세션>/` · 본 대화 기록 `…/<세션>.jsonl` — 종료 훅 훑기(`--mcp-audit --sweep`)
  · `agents/*.md` 의 `tools:` 줄                      — 심볼 도구를 가진 에이전트 종류(훑기가 세는 워커 · 일반 모드가 빼는 워커)
  · 플러그인 루트의 `.claude-plugin/plugin.json` 수정 시각 — 설치 시각(훑기는 그보다 먼저 끝난 실행을 판정하지 않는다)

측정 규약 (⛔ 오측정 재발 방지 — 2026-09-11 정정 이력):
  · **advisor 는 content block `type == "advisor_tool_result"` 를 `tool_use_id` 로 중복 제거해 센다.**
    ⛔ `usage.iterations[].type == "advisor_message"` 로 세면 **과소 집계**된다 — iterations 가
    없는 세션이 있다(실측: 한 세션을 2회로 세었으나 실제 8회. GPT verify #1 이 지적).
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
    `stop_reason:None` + `output_tokens:2` 플레이스홀더만 남는다(실측 2026-09-11 wf_00000000-006
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

DEFAULT_ROOT = os.path.expanduser("~/.claude/projects")
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 이 파일이 든 플러그인의 루트(`scripts/` 위)

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


FZ_MCP_PREFIX = "mcp__plugin_fz_"   # 플러그인이 띄우는 MCP — 측정 대상의 일부다(외부 MCP 가 아니다)


def is_external_mcp(name) -> bool:
    return str(name or "").startswith("mcp__") and not str(name).startswith(FZ_MCP_PREFIX)


def mcp_result_kind(is_error, content) -> str:
    """외부 MCP 결과 종류(F-325) — 오류 · 본문(content) · 빈 결과. Lead · 워커 판독이 함께 쓴다(한 곳에서만 판정).
    본문의 뜻은 판독하지 않는다(권한 없음 문구도 본문 — 보수 쪽). ⛔ 텍스트가 아닌 블록(이미지 · 리소스 …)도 본문이다 —
    텍스트만 보면 스크린숏 결과가 빈 결과로 읽혀 외부 입력 유입이 0 이 된다. 결과가 아예 없는 호출은 이 함수 밖 — unresolved."""
    if is_error:
        return "error"
    if isinstance(content, str):
        return "content" if content.strip() else "empty"
    for b in content or []:
        if not isinstance(b, dict):
            return "content"
        if b.get("type", "text") != "text" or str(b.get("text") or "").strip():
            return "content"
    return "empty"


# 심볼 도구(Serena) 오류 표지 — Serena 는 도구 오류를 is_error 없이 보통 글로 돌려준다
#   (`Error executing tool: <예외> - …` · `Error: No active project …` · `RuntimeError while …`).
SYMBOL_ERROR = re.compile(r"^(?:Error(?: executing tool)?:|RuntimeError while )")
# 워커가 돌려준 결과의 다른 트리 표지 — 심볼 서버가 받은 트리와 다른 트리에 떠 있었다(그 워커의 호출은 쓴 것으로 세지 않는다)
OTHER_TREE_MARK = "[symbol tools: unavailable - not on the target tree]"


def symbol_result_kind(is_error, content) -> str:
    """심볼 도구 결과 종류 — error · empty · ok. 외부 MCP 판독기(`mcp_result_kind`)와 따로 둔다 — 그 판독기는 본문의 뜻을 읽지
    않아 `[]` 도 본문이다. 오류 표지(is_error · Serena 의 오류 머리말)면 오류, 본문이 빈 글이거나 빈 JSON(`[]` · `{}`)이면 빈 결과,
    그 밖은 성공이다. 글이 아닌 블록은 본문이다(빈 결과가 아니다) — 다만 곁의 글 블록 하나가 같은 블록 규칙으로 오류면 결과는 오류다.
    결과가 아예 없는 호출은 이 함수 밖 — 어느 쪽에도 세지 않는다.
    글 블록이 여럿이면 블록마다 같은 규칙으로 판정해 합친다 — 오류 블록이 하나라도 있으면 오류, 아니면 전부 빈 결과일 때 빈 결과, 그 밖은
    성공이다(이어 붙이면 `[]` · `{}` 가 JSON 이 아닌 글이 되고, 빈 블록 뒤의 오류 머리말이 글 맨 앞에서 밀려난다)."""
    blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
    if any(not isinstance(b, dict) or b.get("type", "text") != "text" for b in blocks):
        texts = [str(b.get("text") or "").strip() for b in blocks if isinstance(b, dict) and b.get("type", "text") == "text"]
        return "error" if is_error or any(symbol_result_kind(False, t) == "error" for t in texts) else "ok"
    texts = [str(b.get("text") or "").strip() for b in blocks]
    if len(texts) > 1:
        kinds = {symbol_result_kind(is_error, t) for t in texts}
        return "error" if "error" in kinds else "empty" if kinds == {"empty"} else "ok"
    text = texts[0] if texts else ""
    if is_error or SYMBOL_ERROR.match(text):
        return "error"
    try:
        body = json.loads(text) if text else []
    except ValueError:
        return "ok"
    return "empty" if body in ([], {}) else "ok"


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
    ext_mcp = {}   # (세션, 호출 id) → [도구, 결과 종류] — 결과가 오지 않은 호출은 unresolved(미측정 — 유입 없음으로 읽지 않는다)
    sym = {}       # (세션, 호출 id) → [도구, 지목한 파일(relative_path), 결과 종류, 결과 글 앞부분] — 심볼 읽기 도구(`is_symbol_call` · --mcp-audit)
    other_tree = False   # 워커가 돌려준 글 · 산출에 다른 트리 표지가 있다
    skills = collections.Counter()   # Skill 호출의 스킬 이름별 횟수(종료 훅 훑기의 기록)
    last_stop = None                 # 마지막 완결 응답의 stop_reason — 직접 호출이 끝났는가(`tool_use` · 없음 = 아직 돈다)
    resolved, orphans = set(), 0   # 이을 호출 기록이 없는 결과 — 어느 도구인지 모르므로 외부 MCP 를 미측정으로 만든다(S14 2차 ISSUE-004)
    fmt = collections.Counter()    # 형식 위반 — 빠지거나 형이 틀린 칸을 기본값으로 메우지 않는다(S14 구조 전환 · 결함 주입 tests/ab/faults.py)
    uuids, parents = set(), []
    present = collections.defaultdict(set)   # 비합성 stop 줄의 model · effort · content 유무 — 한 파일 안에서 섞이면 칸이 빠진 것이다
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
            fmt.update(event_format(ev, uuids, parents, present))
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
                        tid = b.get("tool_use_id")
                        name = pending.pop(tid, None)
                        if name is None and tid not in resolved:
                            orphans += 1           # 호출 줄이 빠진 결과 · 이미 이은 결과의 중복 사본은 세지 않는다
                        resolved.add(tid)
                        key = (ev.get("sessionId") or "", tid)
                        if is_external_mcp(name) and key in ext_mcp:
                            ext_mcp[key][1] = mcp_result_kind(b.get("is_error"), b.get("content"))
                        if key in sym:
                            body = b.get("content")
                            text = body if isinstance(body, str) else " ".join(
                                str(x.get("text") or "") for x in body or [] if isinstance(x, dict))
                            sym[key][2:] = [symbol_result_kind(b.get("is_error"), body), text.strip()[:160]]
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
                    #    줄마다 더하면 과대 집계다(실측 2026-09-26 wf_00000000-007 한 워커: 119,597 → 74,518 tok,
                    #    턴 62 → 39). id 별로 한 번만 센다. id 가 없는 줄은 각각 별개 응답으로 본다.
                    usage_by_id[msg.get("id") or f"anon-{total_lines}"] = usage
                    last_stop = msg.get("stop_reason")
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
                            if is_external_mcp(nm):
                                ext_mcp.setdefault((ev.get("sessionId") or "", b.get("id") or f"anon-{total_lines}"), [nm, "unresolved"])
                            if is_symbol_call(nm):
                                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                                sym.setdefault((ev.get("sessionId") or "", b.get("id") or f"anon-{total_lines}"),
                                               [nm, inp.get("relative_path"), "unresolved", ""])
                            if nm == "Skill" and isinstance(b.get("input"), dict):
                                skills[str(b["input"].get("skill") or "")] += 1
                            if b.get("name") == "StructuredOutput":
                                so_calls += 1
                                other_tree |= OTHER_TREE_MARK in json.dumps(b.get("input"), ensure_ascii=False)
                        elif b.get("type") == "text" and OTHER_TREE_MARK in str(b.get("text") or ""):
                            other_tree = True
    fmt.update(file_format(uuids, parents, present))
    if orphans:
        fmt["orphan_result"] = orphans   # 호출 줄이 빠진 결과 — 실측(워커 3,151파일) 0
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
        "mcp_external": [{"session": k[0], "id": k[1], "name": v[0], "kind": v[1]} for k, v in ext_mcp.items()],
        "symbol_calls": [{"name": v[0], "target": v[1], "kind": v[2], "text": v[3]} for v in sym.values()],
        "other_tree": other_tree,
        "skills": dict(skills),
        "last_stop": last_stop,
        "orphan_results": orphans,
        "format_problems": dict(fmt),
    }


def event_format(ev, uuids, parents, present) -> list:
    """이벤트 한 줄의 형식 위반 이름들 — 계측기가 읽는 칸이 빠졌거나 형이 틀렸다. 규칙은 실제 로그(워커 3,151파일 · 응답 76,208줄)에서
    위반 0 인 것만 둔다. ⛔ 빈 객체(`{}` — 실측 2건)는 형식이 아니다."""
    if not ev:
        return []
    out = []
    t = ev.get("type")
    if not isinstance(t, str):
        return ["type"]
    if isinstance(ev.get("uuid"), str):
        uuids.add(ev["uuid"])
    if ev.get("parentUuid") is not None:
        parents.append(ev.get("parentUuid"))
    if t not in ("user", "assistant"):
        return out
    msg = ev.get("message")
    if not isinstance(msg, dict):
        return [t + ".message"]
    if _ts(ev.get("timestamp")) is None:
        out.append(t + ".timestamp")
    content = msg.get("content")
    if t == "user":
        if not isinstance(content, (str, list)):
            out.append("user.content")
        for b in content if isinstance(content, list) else []:
            if not isinstance(b, dict) or not isinstance(b.get("type"), str):
                out.append("user.block")
            elif b["type"] == "tool_result":
                if not isinstance(b.get("tool_use_id"), str):
                    out.append("tool_result.tool_use_id")
                # 본문이 없거나 is_error 형이 틀린 결과를 빈 결과 · 오류로 읽지 않는다(실측 tool_result 95,678 위반 0)
                if not isinstance(b.get("content"), (str, list)) or not isinstance(b.get("is_error", False), bool):
                    out.append("tool_result.content")
        return out
    if not isinstance(msg.get("id"), str):
        out.append("assistant.id")
    if content is not None and not isinstance(content, list):
        out.append("assistant.content")
    if content == []:   # 블록 없는 응답 줄 — 실측 0(워커 3,028파일 · 대화 기록 460파일) · 끝 블록(StructuredOutput)만 지운 꼴
        out.append("assistant.content-empty")
    for b in content if isinstance(content, list) else []:
        if not isinstance(b, dict) or not isinstance(b.get("type"), str):
            out.append("assistant.block")
        elif b["type"] == "tool_use" and not (isinstance(b.get("id"), str) and isinstance(b.get("name"), str)
                                             and isinstance(b.get("input"), dict)):
            out.append("tool_use")
    if msg.get("stop_reason") is not None:
        u = msg.get("usage")
        if not isinstance(msg.get("stop_reason"), str) or not isinstance(u, dict) or type(u.get("output_tokens")) is not int:
            out.append("assistant.usage")
        if msg.get("model") != "<synthetic>":
            for k, v in (("model", msg.get("model")), ("effort", ev.get("effort")), ("content", content)):
                present[k].add(v is not None)
                if v is not None and not isinstance(v, str if k != "content" else list):
                    out.append("assistant." + k)
    return out


def file_format(uuids, parents, present) -> list:
    """파일 단위 형식 위반 — 이은 부모 uuid 가 파일에 없다(줄이 빠졌다) · 비합성 stop 줄의 model · effort · content 유무가 섞였다
    (실측 섞임 0 · 백그라운드 세션 로그는 셋 다 없는 압축 형식이다). ⛔ uuid 가 없는 형식에서 줄째 삭제 · 마지막 줄 삭제는 못 잡는다."""
    out = ["parentUuid"] * sum(1 for p in parents if p not in uuids)
    out += [k + "-mixed" for k, v in present.items() if v == {True, False}]
    return out


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
    - `labels`: agentId → started 이벤트의 label(단계 라벨 — 같은 에이전트 종류의 첫 탐색과 교차 단계를 가른다).
    - Note: 읽기 실패(OSError)는 `read_error` 로 남기고 읽은 데까지의 값을 돌려준다(예외로 죽지 않는다).
    """
    out = {"exists": False, "read_error": False, "result_chars": {}, "events": None, "results": 0, "started": 0,
           "empty": 0, "bad_lines": 0, "labels": {}}
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
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    ev = None
                t = ev.get("type") if isinstance(ev, dict) else None
                if not isinstance(t, str) or (t in ("started", "failed", "result") and not isinstance(ev.get("agentId"), str)):
                    out["bad_lines"] += 1   # ⛔ 못 읽은 줄은 버리지 않는다 — 실패 기록이었을 수 있다(S14 r3 ISSUE-004)
                    continue
                if t in ("started", "failed", "result"):
                    evs.append((t, ev.get("key"), ev.get("agentId")))
                if t == "started":
                    out["started"] += 1
                    if isinstance(ev.get("label"), str):
                        out["labels"][ev["agentId"]] = ev["label"]
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


def _journal_ids_match(events, agents) -> bool:
    if events is None:
        return False
    ids = sorted(a["file"].replace("agent-", "").replace(".jsonl", "") for a in agents)
    st = sorted(str(e[2]) for e in events if e[0] == "started")
    rs = sorted(str(e[2]) for e in events if e[0] == "result")
    return bool(ids) and st == ids and rs == ids


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
    if jn["read_error"]:
        errors.append("journal 읽기 실패")
    if jn["bad_lines"]:
        errors.append(f"journal 파싱 불가 · 형식 위반 줄 {jn['bad_lines']}건")
    jr = jn["result_chars"]
    for a in agents:
        aid = a["file"].replace("agent-", "").replace(".jsonl", "")
        a["result_chars"] = jr.get(aid)
        a["label"] = jn["labels"].get(aid)
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
    for a in agents:
        if a["format_problems"]:
            errors.append(f"{a['file']}: 형식 위반 {a['format_problems']}")
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
        # agentId 대응 — started · result 이벤트의 agentId 가 로그 파일 agent 집합과 각각 한 번씩 같은가. 건수만 보면 같은 agent 의
        # 중복 result 가 다른 agent 의 누락을 메운다(S14 2차 ISSUE-003). journal 을 못 읽으면 False(대응을 모른다)
        "journal_ids_match": _journal_ids_match(jn["events"], agents),
        # 끝나지 않은 워커 수 — 시작했으나 결과도 실패도 없는 agentId(종료 훅 훑기는 0 인 실행만 판정한다) · journal 을 못 읽으면 None
        "journal_pending": None if jn["events"] is None else len(
            {e[2] for e in jn["events"] if e[0] == "started"} - {e[2] for e in jn["events"] if e[0] in ("result", "failed")}),
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
    """self-test · 단언 fixture — kind 별 합성 기록(정상 · 고장 · advisor 스톨 · 시도 · `--mcp-audit` 판정마다의 꼴).

    - Important: 본문은 fz_wf_metrics_selftest.py 에 있다. 이 함수가 불릴 때만 그 모듈을 싣는다 — 모듈 머리에서 실으면
      측정 경로(collect · judge …)에 계측기 지문 밖 코드가 섞인다.
    """
    import fz_wf_metrics_selftest   # ⛔ 부를 때만 싣는다
    fz_wf_metrics_selftest._write_probe(root, kind)



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
#  호출 1 이상이면 호출 수가 아니라 **결과를 돌려준 호출 수**로 판정한다(`judge_symbol_calls`) — 전부 오류인 실행이
#  "사용함" 으로 통과하지 않게. 상태 기록(`--tools-md`)이 미사용이면 0회는 폴백이고 호출은 모순이다. 상태 기록이 없으면 0회는
#  의심이 아니라 미판정(UNRUN)이다 — 심볼 서버가 없는 머신과 배선 끊김을 가를 수 없다(의심은 활성 기록이 있을 때만).
#  심볼 호출은 Serena 의 심볼 읽기 도구(`SYMBOL_READ_TOOLS`)뿐이다 — 메모리 · 프로젝트 활성 · 설정 · 안내와 목록이 모르는 Serena 도구는
#  판정에 세지 않고 정보 줄로만 찍는다. 일반 모드(`--wf` · `--only-agent` 없음)는 정의 폴더에 정의돼 있고 심볼 도구가 없는 종류의 워커를 뺀다.
#  탐색 팔(`--only-label`)은 보고 모드 · 직접 호출(`--direct --only-agent`)은 그 종류의 가장 최근 호출 하나를 판정한다.
MCP_PREFIXES = ("mcp__plugin_fz_serena__", "mcp__serena__")
SYMBOL_READ_TOOLS = ("find_symbol", "find_referencing_symbols", "get_symbols_overview", "find_implementations", "find_declaration")
CONTROL_TOOL = "Read"
NOT_WORK = ("StructuredOutput",)   # 산출 제출은 "도구 작업"이 아니다


def is_symbol_call(name) -> bool:
    """Serena 접두 뒤 이름이 심볼 읽기 도구 목록(`SYMBOL_READ_TOOLS`)에 있는가 — 허용 목록이다. 목록이 모르는 Serena 도구는 심볼 호출이
    아니다(모르는 도구가 실행을 통과시키지 않게)."""
    nm = str(name or "")
    return any(nm.startswith(p) and nm[len(p):] in SYMBOL_READ_TOOLS for p in MCP_PREFIXES)


def audit_counts(agents) -> dict:
    """도구 이름별 수 → serena(심볼 호출) · 대조 · 도구 작업 · 이름별 분포 · other(심볼 읽기가 아닌 Serena 호출 — 도구 작업에도 세지 않고
    정보로만 찍는다)."""
    serena = 0
    control = 0
    work = 0
    names = {}
    other = {}
    for a in agents:
        for nm, c in (a.get("tool_names") or {}).items():
            names[nm] = names.get(nm, 0) + c
            if is_symbol_call(nm):
                serena += c
            elif nm.startswith(MCP_PREFIXES):
                other[nm] = other.get(nm, 0) + c
                continue                       # 심볼 읽기가 아닌 Serena 호출은 도구 작업이 아니다
            if nm == CONTROL_TOOL:
                control += c
            if nm not in NOT_WORK:
                work += c
    return {"serena": serena, "control": control, "work": work, "names": names, "other": other}


# 상태 기록(세션 시작 때 Lead 가 적는 `evidence/tools.md` 첫 줄)의 Serena 부분만 읽는다 — 꼬리(선택 도구 · 스택 스킬)의
#   옛 형식 · 새 형식과 무관하다. 형식 · 대상 트리 · sha 검사는 check_evidence_slots.py 의 몫이다.
STATE_ACTIVE = re.compile(r"^Serena: active \S.*? @[0-9a-f]{7,40} \(languages: ([^)]*)\)(?=$| · )")
STATE_UNUSED = re.compile(r"^\[Serena 미사용 — (\S[^\]]*)\](?=$| · )")
STATE_STACK = re.compile(r" · 스택 스킬 ([^\s,]+(?:, [^\s,]+)*)")   # 꼬리의 스택 스킬 — 종료 훅 훑기의 기록에만 싣는다(판정에 쓰지 않는다)
# 켜진 언어 이름 → 그 언어 서버가 다루는 확장자(Serena 의 언어별 파일 규칙에서 옮겼다). ⛔ 표에 없는 이름이면 판정하지 않는다(exit 2)
LANG_EXTS = {
    "bash": (".sh", ".bash"),
    "python": (".py", ".pyi"),
    "typescript": tuple(f".{p}{b}{x}" for p in ("", "c", "m") for b in ("ts", "js") for x in ("", "x")),
    "swift": (".swift",),
    "go": (".go",),
    "rust": (".rs",),
    "java": (".java",),
    "kotlin": (".kt", ".kts"),
    "csharp": (".cs",),
    "ruby": (".rb", ".erb"),
    "php": (".php",),
    "dart": (".dart",),
}
KNOWN_EXTS = {e for v in LANG_EXTS.values() for e in v}   # 표의 모든 확장자 — 이 밖의 확장자(문서 · 설정 · 점이 든 폴더 이름)는 언어를 모른다


def read_tools_md(path):
    """상태 기록 → {"state": "active", "langs": [...]} · {"state": "unused", "reason": 사유} · None(못 읽음 · 첫 줄이 두 꼴 밖).
    둘 다 `stack`(꼬리의 스택 스킬 이름 · `없음` 이면 빈 목록 · 꼬리가 없거나 옛 꼬리면 None)을 함께 담는다."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            first = fh.readline().strip()
    except (OSError, UnicodeDecodeError):
        return None
    st = STATE_STACK.search(first)
    stack = None if st is None else [] if st.group(1) == "없음" else st.group(1).split(", ")
    m = STATE_ACTIVE.match(first)
    if m:
        return {"state": "active", "langs": [x.strip().lower() for x in m.group(1).split(",") if x.strip()], "stack": stack}
    m = STATE_UNUSED.match(first)
    return {"state": "unused", "reason": m.group(1), "stack": stack} if m else None


def target_side(target, exts) -> str:
    """호출이 지목한 파일 → covered(켜진 언어) · uncovered(확장자 표의 다른 언어) · unknown(파일을 지정하지 않았다 · 폴더 · 확장자 없는
    경로 · 확장자 표에 없는 확장자 — 문서 · 설정 파일 · 점이 든 폴더 이름 `vendor/gopkg.in/yaml.v3`). 확장자는 대소문자를 가리지 않는다.
    ⛔ 알려진 한계: 끝에 `/` 가 없고 표 안 확장자로 끝나는 폴더 이름(`lib/x.go`)만 파일로 읽힌다."""
    if not isinstance(target, str) or not target.strip() or target.rstrip().endswith("/"):
        return "unknown"
    ext = os.path.splitext(target.strip())[1].lower()
    if ext not in exts and ext not in KNOWN_EXTS:      # 확장자 없는 경로(빈 확장자)도 표 밖이다
        return "unknown"
    return "covered" if ext in exts else "uncovered"


def judge_symbol_calls(calls, langs):
    """심볼 도구 호출이 1 이상인 실행의 판정 — 호출 수가 아니라 결과를 돌려준 호출 수로 낸다. 일반 · 직접 호출 · 훑기가 이 함수 하나를 부른다.

    - Parameters:
      - calls: 센 워커의 심볼 도구 호출 `[{"target", "kind", "text"}]` — 결과가 아직 없는 호출(unresolved)은 성공 · 오류 · 빈 결과 수에
        세지 않지만, 켜진 언어 밖 폴백 판정에는 넣는다.
      - langs: 상태 기록의 켜진 언어 목록 · None = 상태 기록이 없거나 미사용이다(켜진 언어를 모른다).
    - Returns: (낱말, 종료 코드, 설명).
    - Important: 성공 0 일 때 우선순위 — 켜진 언어의 파일을 물은 호출에 오류 → `MCP_CALLED_NO_RESULT` · 결과가 온 호출이 있고
      결과가 없는 호출까지 전부 켜진 언어 밖 → `MCP_FALLBACK_UNCOVERED` · 나머지(불명이 섞였거나 켜진 언어 파일의 빈 결과뿐 · 결과 없이
      남은 호출이 켜진 언어 파일이나 불명 대상을 물었다 · 결과가 온 호출이 없다) → `MCP_UNDECIDED`. 가르는 기준은 오류 글자가
      아니라 지목한 파일의 확장자다 — 파일을 지정하지 않은 빈 찾기는 서버가 엉뚱한 프로젝트를 볼 때도 나온다. 확장자 표 밖 대상은 불명이다
      (켜진 언어 밖 폴백이 되지 않는다).
    """
    done = [c for c in calls if c["kind"] in ("ok", "error", "empty")]
    n = collections.Counter(c["kind"] for c in done)
    counts = f"성공 {n['ok']} · 오류 {n['error']} · 빈 결과 {n['empty']}"
    if n["ok"]:
        return "MCP_AUDIT_OK", 0, counts
    if langs is None:
        return "UNRUN", 2, f"성공 0 인데 상태 기록이 없어 켜진 언어를 모른다 ({counts}) — --tools-md 를 넘겨라 (⛔ 통과 아님)"
    if not langs or any(x not in LANG_EXTS for x in langs):
        return "UNRUN", 2, f"상태 기록의 언어 이름이 확장자 표에 없다 ({', '.join(langs) or '빈 목록'}) — 판정하지 않는다 (⛔ 통과 아님)"
    exts = {e for x in langs for e in LANG_EXTS[x]}
    side = [(target_side(c["target"], exts), c) for c in done]
    err = [c for s, c in side if s == "covered" and c["kind"] == "error"]
    if err:
        return "MCP_CALLED_NO_RESULT", 1, f"{counts} — 켜진 언어의 파일을 물었는데 결과가 없다(배선 의심): {err[0]['text']}"
    if side and all(s == "uncovered" for s, _ in side):
        if all(target_side(c["target"], exts) == "uncovered" for c in calls):
            return "MCP_FALLBACK_UNCOVERED", 0, f"{counts} — 물은 파일이 전부 켜진 언어({', '.join(langs)}) 밖이다 · 글자 검색 폴백"
        return "MCP_UNDECIDED", 2, (f"{counts} — 결과가 온 호출은 전부 켜진 언어 밖인데 결과 없이 남은 호출이 켜진 언어 파일이나 "
                                    "불명 대상을 물었다 (⛔ 통과 아님)")
    if not done:
        return "MCP_UNDECIDED", 2, f"{counts} — 심볼 호출 {len(calls)}건이 전부 아직 결과가 없다(기록이 중간에 끊겼다) (⛔ 통과 아님)"
    return "MCP_UNDECIDED", 2, f"{counts} — 파일을 지정하지 않은 찾기 · 폴더 · 켜진 언어 파일의 빈 결과가 남았다 (⛔ 통과 아님)"


def _audit_arm(agents, prefix) -> int:
    """탐색 팔(`--only-label`) — 보고 모드라 판정 셋(과 다른 트리) 모두 exit 0 · 라벨을 못 읽은 워커가 있거나 그 라벨의 워커가 없으면 2.
    라벨은 journal 시작 사건에서 읽는다 — 첫 탐색과 교차 단계가 같은 에이전트 종류라 종류로는 못 가른다."""
    if any(not a.get("label") for a in agents):
        print("UNRUN: 라벨을 못 읽은 워커가 있다 — journal.jsonl 시작 사건에 label 이 없다 (⛔ 통과 아님)")
        return 2
    arm = [a for a in agents if a["label"].startswith(prefix)]
    if not arm:
        print(f"UNRUN: 라벨이 `{prefix}` 로 시작하는 워커가 없다 (⛔ 통과 아님)")
        return 2
    calls = [s for a in arm for s in a["symbol_calls"]]
    n = collections.Counter(s["kind"] for s in calls)
    print(f"label={prefix} · 워커 {len(arm)} · serena 호출 {len(calls)}")
    print(f"  serena 결과: 성공 {n['ok']} · 오류 {n['error']} · 빈 결과 {n['empty']}")
    if any(a["other_tree"] for a in arm):
        print("ARM_OTHER_TREE: 워커가 다른 트리 표지를 남겼다 — 그 호출은 쓴 것으로 세지 않는다")
    elif not calls:
        print("ARM_TEXT_ONLY: serena 호출 0 — 글자 검색만 했다")
    elif n["ok"]:
        print(f"ARM_SYMBOL_USED: serena 성공 {n['ok']}회")
    else:
        print("ARM_CALLED_NO_RESULT: serena 를 불렀으나 결과가 없었다(전부 오류 · 빈 결과)")
    return 0


def cmd_mcp_audit(args) -> int:
    tools_md = None
    if args.tools_md:
        tools_md = read_tools_md(args.tools_md)
        if tools_md is None:
            print(f"UNRUN: 상태 기록을 읽지 못했다 — {args.tools_md} 첫 줄이 `Serena: active …` · `[Serena 미사용 — 사유]` 꼴이 아니다"
                  " (⛔ 통과 아님)")
            return 2
    if args.direct:
        # 직접 호출 기록 = 그 세션의 subagents/ 바로 아래(워크플로 워커는 workflows/wf_*/ 에 따로 쌓인다)
        if not args.only_agent:
            print("UNRUN: --direct 는 --only-agent 가 필요하다 — 세션 폴더에는 무관한 에이전트가 섞인다 (⛔ 통과 아님)")
            return 2
        hits = [h for h in sorted(glob.glob(os.path.join(args.root, "*", args.session, "subagents"))) if os.path.isdir(h)]
        if len(hits) != 1:
            print(f"UNRUN: 직접 호출 기록 폴더가 {len(hits)}개다 (session={args.session} root={args.root}) — 세션 하나로 좁혀라 — 미판정")
            return 2
        folder = hits[0]
    else:
        folder = args.wf if (args.wf and os.path.isdir(args.wf)) else (
            resolve(args.root, args.session, args.wf) if args.wf else None)
        if folder is None:
            # ⛔ 대상이 없는 것은 통과가 아니다
            print(f"UNRUN: wf 폴더를 찾지 못했다 (wf={args.wf} root={args.root}) — 미판정")
            return 2
    wf = read_wf(folder)
    agents = wf["agents"]
    if args.only_agent:
        if any(a["agentType"] == "unavailable" for a in agents):
            print("UNRUN: 에이전트 종류를 못 읽은 기록이 있다 — 그 워커가 세는 종류인지 모른다 (⛔ 통과 아님)")
            return 2
        agents = [a for a in agents if a["agentType"] == args.only_agent]
    if args.only_label is not None:
        return _audit_arm(agents, args.only_label)
    left = collections.Counter()
    if not args.only_agent:
        # 일반 모드 — 정의 폴더에 정의돼 있고 심볼 도구가 없는 종류의 워커는 세지 않는다(정의에 없는 종류는 센다 · 정의를 못 읽으면 전부 센다)
        defs = args.agents_dir or os.path.join(PLUGIN_ROOT, "agents")
        holders = symbol_holders(defs)
        try:
            defined = {"fz:" + nm[:-3] for nm in os.listdir(defs) if nm.endswith(".md")}
        except OSError:
            defined = set()
        if holders is not None:
            left = collections.Counter(a["agentType"] for a in agents if a["agentType"] in defined - holders)
            agents = [a for a in agents if a["agentType"] not in left]
        if left and not agents:
            print("MCP_NOT_APPLICABLE: 심볼 도구를 가진 종류의 워커가 없다(뺀 종류: "
                  + ", ".join(f"{k} {v}" for k, v in sorted(left.items())) + ") — 판정할 것이 없다")
            return 0
    if args.only_agent and not agents:
        print(f"UNRUN: {args.only_agent} 워커가 없다 — 미판정")
        return 2
    earlier = []
    if args.direct:
        # ⛔ 합쳐 세면 앞 호출의 사용이 뒤 호출의 0회를 가린다 — 가장 최근 호출 하나만 판정하고 앞선 호출은 정보 줄로만 찍는다
        if any(a["first"] is None for a in agents):
            print("UNRUN: 시각이 없는 직접 호출 기록이 있다 — 가장 최근 호출을 고를 수 없다 (⛔ 통과 아님)")
            return 2
        agents = sorted(agents, key=lambda a: a["first"])
        earlier, agents = agents[:-1], agents[-1:]
    c = audit_counts(agents)
    calls = [s for a in agents for s in a["symbol_calls"]]
    n = collections.Counter(s["kind"] for s in calls)
    top = ", ".join(f"{k}={v}" for k, v in sorted(c["names"].items(), key=lambda kv: -kv[1])[:6]) or "(없음)"
    name = os.path.basename(os.path.dirname(folder) if args.direct else folder)
    print(f"{'session' if args.direct else 'wf'}={name} · agents={len(wf['agents'])}")
    if args.only_agent:
        print(f"  센 워커: {args.only_agent} {len(agents)}" + (f" (가장 최근 호출 {agents[0]['file']})" if args.direct else ""))
    if left:
        print("  뺀 워커(심볼 도구가 없는 종류 — 세지 않는다): " + ", ".join(f"{k} {v}" for k, v in sorted(left.items())))
    for a in earlier:
        k = collections.Counter(s["kind"] for s in a["symbol_calls"])
        print(f"  앞선 직접 호출(정보 — 판정하지 않는다): {a['file']} serena {len(a['symbol_calls'])}"
              f" · 성공 {k['ok']} · 오류 {k['error']} · 빈 결과 {k['empty']}")
    print(f"  serena 호출 {c['serena']} · 대조({CONTROL_TOOL}) {c['control']} · 도구작업 {c['work']}")
    if c["other"]:
        print("  심볼 읽기가 아닌 serena 호출(정보 — 판정에 세지 않는다): " + ", ".join(f"{k}={v}" for k, v in sorted(c["other"].items())))
    print(f"  도구 분포: {top}")
    print(f"  serena 결과: 성공 {n['ok']} · 오류 {n['error']} · 빈 결과 {n['empty']}"
          + (f" · 결과 없음 {n['unresolved']}" if n["unresolved"] else ""))

    _word, code, line = audit_verdict(agents, tools_md)
    print(line)
    return code


def audit_verdict(agents, tools_md):
    """센 워커의 심볼 도구 점검 판정 하나 — 일반 · 직접 호출 모드(`cmd_mcp_audit`)와 종료 훅 훑기(`cmd_mcp_sweep`)가 이 함수를 부른다.

    - Parameters:
      - agents: 센 워커(`read_agent` 결과 — `read_wf` 가 agentType 을 더한다).
      - tools_md: `read_tools_md` 결과 · None = 상태 기록이 없다(훑기는 상태를 모르는 실행도 None 으로 넘긴다).
    - Returns: (낱말, 종료 코드, 출력 줄). 0회 규칙(도구 작업 · 다른 트리 · 미사용 기록 · 대조 심볼 · 상태 기록 없음)을 먼저 보고,
      호출 1 이상은 `judge_symbol_calls` 의 성공 수 판정이다. `MCP_WIRING_SUSPECT` 는 활성 상태 기록이 있을 때만 낸다. 다른 트리 표지를 낸
      워커가 Serena 를 불렀으면(안내 호출뿐이어도 — 표지가 서버 관찰에서 나올 수 있다) 도구 작업 0 보다 다른 트리를 먼저 본다.
    """
    unused = tools_md is not None and tools_md["state"] == "unused"
    c = audit_counts(agents)
    calls = [s for a in agents for s in a["symbol_calls"]]
    if c["work"] == 0 and not any(a["other_tree"] and any(nm.startswith(MCP_PREFIXES) for nm in a.get("tool_names") or {}) for a in agents):
        return "UNRUN", 2, "UNRUN: 도구 작업이 0건이다 — 배선 죽음과 '할 일이 없었음'을 구별할 수 없다 (⛔ 통과 아님)"
    if any(a["other_tree"] for a in agents):
        return "MCP_OTHER_TREE", 1, ("MCP_OTHER_TREE: 워커가 다른 트리 표지를 남겼다 — 그 호출은 쓴 것으로 세지 않는다. "
                                     "Lead 가 대상 트리에서 심볼 서버를 다시 켠다")
    if c["serena"] == 0 and unused:
        return "MCP_FALLBACK", 0, f"MCP_FALLBACK (사유: {tools_md['reason']}) — serena 0건 · 상태 기록이 미사용이다"
    if c["serena"] == 0 and c["control"] == 0:
        return "UNRUN", 2, (f"UNRUN: serena 0건이지만 대조 심볼({CONTROL_TOOL})도 0건이다 — "
                            "부재를 주장할 근거가 없다 (⛔ 통과 아님)")
    if c["serena"] == 0 and tools_md is None:
        return "UNRUN", 2, (f"UNRUN: serena 0건 · {CONTROL_TOOL} {c['control']}건인데 상태 기록이 없다 — 상태 기록 없이는 '이 머신에 심볼 서버가 "
                            "없다' 와 '배선이 끊겼다' 를 가를 수 없다. 세션의 상태를 상태 기록 꼴로 파일에 적어 --tools-md 로 넘겨라 (⛔ 통과 아님)")
    if c["serena"] == 0:
        return "MCP_WIRING_SUSPECT", 1, (f"MCP_WIRING_SUSPECT: serena 0건인데 {CONTROL_TOOL} {c['control']}건 — "
                                         "워커는 파일 작업을 했다. 배선을 확인하라")
    if unused:
        return "MCP_STATE_MISMATCH", 1, (f"MCP_STATE_MISMATCH: 상태 기록은 미사용(사유: {tools_md['reason']})인데 serena {c['serena']}건 — "
                                         "못 쓴다고 적은 대상에 워커가 물었다")
    word, code, detail = judge_symbol_calls(calls, tools_md["langs"] if tools_md else None)
    if word == "MCP_AUDIT_OK":
        return word, code, f"MCP_AUDIT_OK (serena {c['serena']}건 · 대조 {c['control']}건 · {detail})"
    return word, code, f"{word}: {detail}"


# ── --mcp-audit --sweep (종료 훅 훑기) ──────────────────────────────────────
#  세션 하나의 끝난 워크플로 실행과 직접 호출을 실행마다 `audit_verdict` 로 판정한다 — 심볼 도구를 가진 에이전트 종류의 워커만 센다
#  (에이전트 정의 머리의 `tools:` 줄 · 그런 워커가 없는 실행은 해당 없음). 상태 기록(`--state`)이 하나가 아니거나 실행이 시작된 뒤에
#  고쳐졌으면 그 실행의 0회 · 성공 0 은 의심이 아니라 미판정이다 — 틀린 상태로 판정하느니 판정하지 않는다.
#  판정한 실행의 열쇠(실행 id + 워커 기록 수)는 기록 옆 `<기록 이름>.keys.json` 에 둔다 — 기록 줄을 먼저 쓰고 열쇠를 나중에 쓴다
#  (임시 파일에 쓴 뒤 이름 바꾸기). 워커 기록이 늘어난 실행(재개 · 다음 시도)은 다시 판정한다. 열쇠가 맞지 않는 실행이 있으면 먼저 기록
#  (돌린 `.1` 포함)의 이 세션 줄에서 열쇠를 되살린다 — 열쇠 쓰기만 실패한 종료 뒤에 같은 실행의 기록 줄이 둘 되지 않게. 그 종료가 알리지 못한
#  의심은 되살린 훑기가 `앞선 훑기의 판정` 표시로 한 번 찍는다(기록 줄은 새로 쓰지 않는다 · 요약 줄은 이번에 판정한 실행만 센다). 끝나지 않은 실행과
#  예산(`--budget`)에 걸려 못 본 실행은 열쇠를 적지 않고 다음 훑기에서 본다 — 다만 기록 파일이 `SWEEP_STALE_HOURS` 넘게 멈춘 실행은 미판정(설치 전 ·
#  센 워커가 없으면 해당 없음)으로 적고 열쇠(워커 기록 수 + 기록 크기 — 재개가 기존 워커 기록에 덧붙여도 맞지 않게 된다)를 적는다. 기록의 어느
#  값도 `fz:` 로 시작하지 않는다(에이전트 종류 · fz 스킬 이름을 싣지 않는다).
#  새로 판정한 실행이 전부 해당 없음이면 열쇠만 쓰고 기록 줄은 쓰지 않는다 — 아무도 기록을 보지 않는 머신(심볼 도구를 가진 에이전트를
#  쓰지 않는 세션뿐)에서 기록이 자라지 않게. 기록 파일이 `SWEEP_RECORD_MAX` 바이트에 이르면 덧붙이기 전에 `<기록>.1` 로 한 번 돌린다(옛 파일은 하나만).
#  이 플러그인이 설치되기 전(루트의 `.claude-plugin/plugin.json` 수정 시각)에 끝난 실행은 판정하지 않고 해당 없음으로 적는다(사유 칸 · 열쇠를
#  적는다) — 업데이트 뒤 옛 정의로 돈 실행이 고칠 수 없는 경보를 내지 않게. 그 파일을 못 읽거나 시각이 미래면 경계가 없다.
#  기록 · 열쇠를 쓰지 못하면 `MCP_SWEEP_UNRUN` 줄 하나만 찍는다 — 기록하지 못한 판정은 알리지 않는다(열쇠가 없으니 다음 훑기가 기록 줄에서
#  열쇠를 되살리거나 다시 판정한다).
#  언제나 exit 0 — 판정은 요약 줄 `MCP_SWEEP runs=… used=… suspect=… fallback=… undecided=… n/a=…` 과 기록에만 남는다.
SWEEP_SKIP_AGENTS = ("memory-curator",)   # 메모리 회상이 일이라 심볼 호출 0 이 정상이다 — 재지 않는다
SWEEP_KEYS_MAX = 5000                     # 열쇠 파일 상한 — 넘으면 가장 오래 고치지 않은 열쇠부터 버린다
SWEEP_RECORD_MAX = 1_000_000              # 기록 파일 돌림 크기(바이트) — 돌린 옛 파일 하나까지 이 머신에 남는 기록은 약 2MB 다
SWEEP_VERDICTS = ("used", "suspect", "fallback", "undecided", "n/a")
SWEEP_STALE_HOURS = 24.0                  # 끝나지 않은 채 이 시간 넘게 기록이 없으면 멈춘 실행 — run_metrics.py RUN_OPEN_STALE_HOURS(버려진 시도)와 같은 값 · 같은 뜻


def symbol_holders(agents_dir):
    """에이전트 정의 폴더 → 머리(frontmatter)의 `tools:` 줄에 심볼 읽기 도구(`SYMBOL_READ_TOOLS` — 호출을 세는 목록과 같다)가 있는
    종류(`fz:<파일 이름>`) 집합 · 못 읽거나 비었으면 None."""
    try:
        names = sorted(n for n in os.listdir(agents_dir) if n.endswith(".md"))
    except OSError:
        return None
    out = set()
    for n in names:
        try:
            with open(os.path.join(agents_dir, n), "r", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            return None
        m = re.search(r"^tools:(.*)$", text.split("\n---", 1)[0] if text.startswith("---") else "", re.M)
        tools = {t.strip() for t in m.group(1).split(",")} if m else set()
        if n[:-3] not in SWEEP_SKIP_AGENTS and any(p + t in tools for p in MCP_PREFIXES for t in SYMBOL_READ_TOOLS):
            out.add("fz:" + n[:-3])
    return out if names else None


def _session_skills(path):
    """본 대화 기록의 Skill 호출 → 이름별 횟수(못 읽으면 빈 Counter). `"Skill"` 이 없는 줄은 파싱하지 않는다."""
    out = collections.Counter()
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"Skill"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                msg = ev.get("message") if isinstance(ev, dict) else None
                for b in msg.get("content") if isinstance(msg, dict) and isinstance(msg.get("content"), list) else []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill" and isinstance(b.get("input"), dict):
                        out[str(b["input"].get("skill") or "")] += 1
    except OSError:
        pass
    return out


def _install_time(now):
    """이 파일이 든 플러그인의 설치 시각 — 루트의 `.claude-plugin/plugin.json` 수정 시각 · 못 읽거나 `now` 보다 뒤면 None(경계 없음)."""
    try:
        t = os.path.getmtime(os.path.join(PLUGIN_ROOT, ".claude-plugin", "plugin.json"))
    except OSError:
        return None
    return t if t <= now else None


def _run_files(path):
    """훑기가 끝남 · 멈춤을 가르는 실행 기록 파일 — 워크플로: `journal.jsonl` · `agent-*.jsonl` / 직접 호출: 그 `agent-*.jsonl`."""
    return glob.glob(os.path.join(path, "agent-*.jsonl")) + [os.path.join(path, "journal.jsonl")] if os.path.isdir(path) else [path]


def _run_ended(path):
    """실행이 끝난 때 — 실행 기록 파일(`_run_files`)의 가장 늦은 수정 시각 · 못 읽으면 None."""
    try:
        return max(os.path.getmtime(f) for f in _run_files(path) if os.path.isfile(f))
    except (OSError, ValueError):
        return None


def _run_bytes(path):
    """멈춘 실행 열쇠의 둘째 칸 — 실행 기록 파일 크기의 합(재개가 기존 워커 기록에 덧붙여도 바뀐다) · 못 읽으면 None."""
    try:
        return sum(os.path.getsize(f) for f in _run_files(path) if os.path.isfile(f))
    except OSError:
        return None


def _stall_hit(v, path, n) -> bool:
    """멈춘 채 적은 실행의 열쇠([워커 기록 수, 기록 크기])가 지금 기록과 같은가 — 같으면 다시 읽지 않는다."""
    return isinstance(v, list) and v == [n, _run_bytes(path)]


def _recover_keys(record, sess, keys, runs) -> dict:
    """열쇠가 맞지 않는 실행이 있을 때만 기록 · 돌린 기록(`.1`)의 이 세션 줄에서 그 실행마다 마지막 열쇠를 `keys` 에 되살리고 {열쇠: 그 기록 줄의 실행 칸}
    을 돌려준다 — 기록 줄은 썼는데 열쇠를 쓰지 못한 종료 뒤에 같은 실행을 다시 판정하지 않게(워커 기록이 그 뒤에 늘었으면 되살린 열쇠도 맞지 않는다)."""
    want = {f"{sess}/{rid}" for rid, path, n in runs if keys.get(f"{sess}/{rid}") != n and not _stall_hit(keys.get(f"{sess}/{rid}"), path, n)}
    found, row_of, needle = {}, {}, '"session": ' + json.dumps(sess, ensure_ascii=False)
    for p in (record + ".1", record) if want else ():  # 옛 파일부터 — 뒤 줄이 앞 줄을 덮는다
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        ev = json.loads(line) if needle in line else None
                    except ValueError:
                        continue
                    rows = ev.get("runs") if isinstance(ev, dict) and ev.get("session") == sess else None
                    for r in rows if isinstance(rows, list) else ():
                        k = f"{sess}/{r.get('run')}" if isinstance(r, dict) else None
                        if k in want and isinstance(r.get("workers"), int):
                            found[k] = [r["workers"], r["bytes"]] if isinstance(r.get("bytes"), int) else r["workers"]
                            row_of[k] = r
        except OSError:
            continue
    found = {k: v for k, v in found.items() if keys.get(k) != v}
    for k in found:
        keys.pop(k, None)                              # 되살린 열쇠는 새로 고친 열쇠다(상한을 넘으면 가장 늦게 버린다)
    keys.update(found)
    return {k: row_of[k] for k in found}


def cmd_mcp_sweep(args) -> int:
    """종료 훅 훑기 — 위 머리 주석의 규칙. 예상 밖 오류도 exit 0(판정하지 않았다는 줄만 남긴다)."""
    try:
        return _sweep_session(args)
    except Exception as exc:                            # noqa: BLE001 — 훑기는 부른 쪽(종료 훅)의 결과를 바꾸지 않는다
        print(f"MCP_SWEEP_UNRUN: 예상 밖 오류({type(exc).__name__}) — 판정하지 않았다")
        return 0


def _sweep_session(args) -> int:
    import time                                        # 훑기만 쓴다(--budget)
    t0 = time.monotonic()
    folder = os.path.normpath(args.sweep)
    sub = os.path.join(folder, "subagents")
    runs = [(os.path.basename(d), d, len(glob.glob(os.path.join(d, "agent-*.jsonl"))))
            for d in sorted(glob.glob(os.path.join(sub, "workflows", "wf_*"))) if os.path.isdir(d)]
    runs += [(os.path.basename(p)[:-len(".jsonl")], p, 1) for p in sorted(glob.glob(os.path.join(sub, "agent-*.jsonl")))]
    if not runs:
        print("MCP_SWEEP runs=0 used=0 suspect=0 fallback=0 undecided=0 n/a=0 — 워크플로 실행 · 직접 호출 기록이 없다(파일을 만들지 않는다)")
        return 0
    agents_dir = args.agents_dir or os.path.join(PLUGIN_ROOT, "agents")
    holders = symbol_holders(agents_dir)
    if not args.record or holders is None:
        why = "--record 가 없다" if not args.record else f"에이전트 정의를 못 읽었다({agents_dir})"
        print(f"MCP_SWEEP_UNRUN: {why} — 판정하지 않는다")
        return 0
    keys_path = os.path.splitext(args.record)[0] + ".keys.json"
    try:
        with open(keys_path, "r", encoding="utf-8") as fh:
            keys = json.load(fh)
    except (OSError, ValueError):
        keys = {}
    keys = keys if isinstance(keys, dict) else {}
    states = args.state or []
    st = read_tools_md(states[0]) if len(states) == 1 else None
    st_time = datetime.datetime.fromtimestamp(os.path.getmtime(states[0]), datetime.timezone.utc) if st else None
    sess = os.path.basename(folder)
    now = time.time()
    cutoff = _install_time(now)
    tally, out_runs, new_keys, skills = collections.Counter(), [], {}, collections.Counter()
    seen = pending = left = predated = stalled = 0
    recovered = _recover_keys(args.record, sess, keys, runs)
    earlier = [r for r in recovered.values() if r.get("verdict") == "suspect"]   # 열쇠를 되살린 의심 실행 — 알리지 못한 앞선 판정
    for rid, path, n in runs:
        key = f"{sess}/{rid}"
        if keys.get(key) == n:
            continue                                   # 이미 판정한 실행 — 워커 기록 수가 같다
        if _stall_hit(keys.get(key), path, n):
            continue                                   # 멈춘 채 적은 실행 — 워커 기록 수 · 기록 크기가 그대로다
        if seen and args.budget is not None and time.monotonic() - t0 > args.budget:
            left += 1                                  # 예산 소진 — 열쇠를 적지 않는다(실행 하나는 언제나 본다)
            continue
        seen += 1
        if os.path.isdir(path):
            wf = read_wf(path)
            agents, done = wf["agents"], wf["journal_pending"] == 0 and bool(wf["agents"])
        else:
            a = read_agent(path)
            try:
                with open(path[:-len(".jsonl")] + ".meta.json", "r", encoding="utf-8") as fh:
                    a["agentType"] = json.load(fh).get("agentType") or "unavailable"
            except (OSError, ValueError, AttributeError):
                a["agentType"] = "unavailable"
            agents, done = [a], a["last_stop"] not in (None, "tool_use")
        last = None if done else _run_ended(path)
        size = _run_bytes(path) if last is not None and now - last > SWEEP_STALE_HOURS * 3600 else None   # 멈춘 실행의 기록 크기
        if not done and size is None:
            pending += 1                               # 끝나지 않은 실행 — 열쇠를 적지 않는다
            continue
        counted = [a for a in agents if a["agentType"] in holders]
        start = min((a["first"] if a["first"].tzinfo else a["first"].replace(tzinfo=datetime.timezone.utc)
                     for a in agents if a["first"]), default=None)
        use = st if st and start is not None and st_time <= start else None   # 실행이 시작된 뒤에 고친 상태 기록은 쓰지 않는다
        ended = _run_ended(path) if cutoff is not None else None
        before_install = ended is not None and ended < cutoff
        if before_install:
            counted, verdict, word = [], "n/a", "N/A"   # 이 플러그인보다 먼저 끝난 실행 — 옛 정의로 돈 워커다(판정하지 않는다)
            predated += 1
        elif "unavailable" in {a["agentType"] for a in agents}:
            verdict, word = "undecided", "UNRUN"       # 종류를 못 읽은 워커 — 세는 종류인지 모른다
        elif not counted:
            verdict, word = "n/a", "N/A"
        elif size is not None:
            verdict, word = "undecided", "UNRUN"       # 끝나지 않은 채 멈춘 실행 — 판정하지 않는다
        else:
            word, code, _line = audit_verdict(counted, use)
            verdict = {0: "used" if word == "MCP_AUDIT_OK" else "fallback", 1: "suspect"}.get(code, "undecided")
        k = collections.Counter(s["kind"] for a in counted for s in a["symbol_calls"])
        c7 = collections.Counter(m["kind"] for a in agents for m in a["mcp_external"] if "context7" in m["name"])
        out_runs.append({"run": rid, "workers": n, "counted": len(counted), "verdict": verdict, "word": word,
                         "ok": k["ok"], "error": k["error"], "empty": k["empty"], "state": use["state"] if use else None,
                         "languages": use.get("langs") if use else None, "context7": dict(c7)})
        if before_install:
            out_runs[-1]["reason"] = "설치된 플러그인보다 먼저 끝난 실행 — 판정하지 않는다"
        elif size is not None and verdict == "undecided":
            out_runs[-1]["reason"] = f"끝나지 않은 채 {SWEEP_STALE_HOURS:g}시간 넘게 멈춘 실행 — 판정하지 않는다"
            stalled += 1
        if size is not None:
            out_runs[-1]["bytes"] = size               # 기록에서 열쇠를 되살릴 때 쓴다
        tally[verdict] += 1
        for a in agents:
            skills.update(a["skills"])
        new_keys[key] = n if size is None else [n, size]
    if out_runs or recovered:                          # 되살린 열쇠만 있어도 열쇠 파일을 다시 쓴다(기록 줄은 새 판정이 있을 때만)
        main_log = folder + ".jsonl"                   # 본 대화 기록 — 세션 폴더와 같은 이름의 형제 파일
        if os.path.isfile(main_log) and os.path.abspath(main_log) != os.path.abspath(args.record):
            skills.update(_session_skills(main_log))
        line = {"at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "session": sess,
                "summary": {v: tally[v] for v in SWEEP_VERDICTS},
                "stack_skills": None if not st or st["stack"] is None else [x for x in st["stack"] if not x.startswith("fz:")],
                "skills": {nm: c for nm, c in sorted(skills.items()) if nm and not nm.startswith("fz:")}, "runs": out_runs}
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.record)), exist_ok=True)
            if tally["n/a"] < len(out_runs):           # 전부 해당 없음이면 열쇠만 쓴다(기록 줄 없음)
                if os.path.isfile(args.record) and os.path.getsize(args.record) >= SWEEP_RECORD_MAX:
                    os.replace(args.record, args.record + ".1")   # 한 번 돌린다 — 옛 파일은 하나만 남는다
                with open(args.record, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            for key, n in new_keys.items():
                keys.pop(key, None)
                keys[key] = n
            while len(keys) > SWEEP_KEYS_MAX:
                del keys[next(iter(keys))]
            with open(keys_path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(keys, fh, ensure_ascii=False)
            os.replace(keys_path + ".tmp", keys_path)
        except OSError as exc:
            print(f"MCP_SWEEP_UNRUN: 기록 · 열쇠를 쓰지 못했다({type(exc).__name__}) — 열쇠가 없는 실행은 다음 훑기에서 다시 본다")
            return 0                                   # 기록하지 못한 판정은 알리지 않는다(요약 · 의심 줄 없음)
    print(f"MCP_SWEEP runs={len(out_runs)} " + " ".join(f"{v}={tally[v]}" for v in SWEEP_VERDICTS))
    for r in out_runs:
        if r["verdict"] == "suspect":
            print(f"  의심: {r['run']} {r['word']} (성공 {r['ok']} · 오류 {r['error']} · 빈 결과 {r['empty']})")
    for r in earlier:                                  # 열쇠를 이제 썼다 — 다음 훑기는 되살리지 않으니 한 번뿐이다
        print(f"  의심: {r['run']} {r.get('word')} (성공 {r.get('ok')} · 오류 {r.get('error')} · 빈 결과 {r.get('empty')}) — 앞선 훑기의 판정(요약 줄에 세지 않는다)")
    if predated:
        print(f"  설치 전 실행 {predated} — 해당 없음(이 플러그인이 설치되기 전에 끝났다 · 판정하지 않는다)")
    if stalled:
        print(f"  멈춘 실행 {stalled} — 미판정({SWEEP_STALE_HOURS:g}시간 넘게 기록이 없다 · 기록이 늘면 다시 본다)")
    if pending:
        print(f"  끝나지 않은 실행 {pending} — 열쇠를 적지 않는다(다음 훑기에서 본다)")
    if left:
        print(f"  예산 소진 — 못 본 실행 {left} (다음 훑기에서 본다)")
    return 0


def cmd_self_test(args) -> int:
    import fz_wf_metrics_selftest   # ⛔ self-test 일 때만 싣는다 — 측정 경로에 들이면 지문 밖 코드가 판정에 섞인다
    return fz_wf_metrics_selftest.self_test()


def main() -> int:
    ap = argparse.ArgumentParser(description="Workflow 실행 stage 집계 (읽기 전용)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="트랜스크립트 루트 (기본 ~/.claude/projects)")
    ap.add_argument("--wf", help="wf_* 폴더명 또는 절대경로 — 1건 상세")
    ap.add_argument("--session", default="*", help="--wf · --direct 와 함께 쓰는 세션 glob (--direct 는 세션 하나에 맞아야 한다)")
    ap.add_argument("--expect", help="fixture JSON 과 대조 (성공 시 METRICS_OK)")
    ap.add_argument("--self-test", action="store_true", help="양성·음성 self-test")
    ap.add_argument("--sweep-row", action="store_true",
                    help="experiment-log §5.8 ⑥ 행을 측정값으로 출력 (사람 판정 칸은 플레이스홀더)")
    ap.add_argument("--mcp-audit", action="store_true",
                    help="선언된 MCP 도구를 워커가 실제로 불렀는가 (0=OK · 1=배선 의심 · 2=미판정)")
    ap.add_argument("--tools-md", metavar="FILE",
                    help="--mcp-audit: 세션 시작 상태 기록(evidence/tools.md) — 첫 줄의 Serena 부분만 읽는다")
    ap.add_argument("--only-label", metavar="PREFIX",
                    help="--mcp-audit: journal 라벨이 이 접두로 시작하는 워커만 센다 (탐색 팔 보고 모드 — 판정은 exit 0 · 못 정하면 2)")
    ap.add_argument("--only-agent", metavar="TYPE", help="--mcp-audit: 이 에이전트 종류의 워커만 센다")
    ap.add_argument("--direct", action="store_true",
                    help="--mcp-audit: 워크플로 폴더 대신 세션의 직접 호출 기록(subagents/)에서 --only-agent 의 가장 최근 호출 하나를 판정")
    ap.add_argument("--sweep", metavar="SESSION_DIR",
                    help="--mcp-audit: 세션 기록 폴더의 끝난 워크플로 실행 · 직접 호출을 실행마다 판정하고 --record 에 한 줄을 덧붙인다"
                         " (종료 훅 훑기 · 언제나 exit 0)")
    ap.add_argument("--record", metavar="FILE", help="--sweep: 판정 기록(JSONL · 저장소 밖) — 판정한 실행의 열쇠는 옆의 <이름>.keys.json")
    ap.add_argument("--state", metavar="FILE", action="append",
                    help="--sweep: 그 세션이 쓴 상태 기록(evidence/tools.md) — 찾은 수만큼 준다(하나가 아니면 0회 · 성공 0 은 미판정)")
    ap.add_argument("--agents-dir", help="--mcp-audit: 에이전트 정의 폴더 — 일반 모드는 심볼 도구가 없는 정의된 종류의 워커를 빼고 · --sweep 은"
                                         " 심볼 도구를 가진 종류만 센다 (기본 이 파일이 든 플러그인의 agents/)")
    ap.add_argument("--budget", type=float, metavar="SEC", help="--sweep: 이 초가 지나면 다음 실행을 보지 않는다(실행 하나는 언제나 본다)")
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
        return cmd_mcp_sweep(args) if args.sweep else cmd_mcp_audit(args)
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
