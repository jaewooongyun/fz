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
  · dur 은 그 agent 의 첫·끝 timestamp 차분이다. wall 은 전 agent 의 min~max 다.
  · 크리티컬 패스 = 직렬 stage 합 + 병렬 그룹별 max. 병렬 그룹은 stage 라벨로 정한다
    (S2 3렌즈 · S3 CC 2콜) — plan-final §1 시간 모델의 분모다.
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
STAGE_RULES = (
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
SERIAL_STAGES = ("S0", "S0-reb", "S0-fin", "S1", "S4", "S5")
PARALLEL_GROUPS = (("S2-impact", "S2-edge", "S2-arch"), ("S3-imp", "S3-edge"))


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
    """agent-*.jsonl 1개 → 지표. 파싱 불가 줄은 세고 버린다(조용히 넘기지 않는다)."""
    first = last = None
    turns = tools = out_tok = think = 0
    cache_r = cache_w = 0
    advisor_ids = set()
    so_calls = 0
    so_errors = 0
    pending = {}
    role = ""
    bad_lines = 0
    total_lines = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
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
                if not role:
                    text = content if isinstance(content, str) else ""
                    if isinstance(content, list):
                        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                    m = re.search(r"\[역할\]\s*([^\n]{0,60})", text)
                    role = m.group(1) if m else text[:60]
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
                usage = msg.get("usage") or {}
                if msg.get("stop_reason"):
                    turns += 1
                    out_tok += usage.get("output_tokens") or 0
                    think += (usage.get("output_tokens_details") or {}).get("thinking_tokens") or 0
                    cache_r += usage.get("cache_read_input_tokens") or 0
                    cache_w += usage.get("cache_creation_input_tokens") or 0
                if isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "advisor_tool_result":
                            # ⛔ tool_use_id 로 중복 제거 — 같은 응답이 두 줄에 걸쳐 기록될 수 있다
                            advisor_ids.add(b.get("tool_use_id") or f"anon-{len(advisor_ids)}")
                        elif b.get("type") == "tool_use":
                            tools += 1
                            pending[b.get("id")] = b.get("name")
                            if b.get("name") == "StructuredOutput":
                                so_calls += 1
    dur = (last - first).total_seconds() if first and last else None
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
        "out_tok": out_tok,
        "thinking": think,
        "cache_read": cache_r,
        "cache_write": cache_w,
        "advisor": len(advisor_ids),
        "so_calls": so_calls,
        "so_retries": max(0, so_calls - 1),
        "so_errors": so_errors,
        "bad_lines": bad_lines,
        "total_lines": total_lines,
    }


def journal_results(folder: str) -> dict:
    """agentId → 반환값 길이. 완결 턴 usage 가 없는 agent 의 산출 유무를 가리는 유일한 증거다."""
    out = {}
    path = os.path.join(folder, "journal.jsonl")
    if not os.path.isfile(path):
        return out
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if isinstance(ev, dict) and ev.get("type") == "result":
                    r = ev.get("result")
                    txt = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
                    out[ev.get("agentId")] = len(txt or "")
    except OSError:
        pass
    return out


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
    # journal 반환 길이 — 완결 턴이 없는 agent 의 산출 유무 판정 근거
    jr = journal_results(folder)
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
    timed = [a for a in agents if a["first"] and a["last"]]
    wall = None
    if timed:
        wall = (max(a["last"] for a in timed) - min(a["first"] for a in timed)).total_seconds()
    if agents and not timed:
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
    crit = 0.0
    crit_known = True
    for s in SERIAL_STAGES:
        for a in by_stage.get(s, []):
            if a["dur"] is None:
                crit_known = False
            else:
                crit += a["dur"]
    for group in PARALLEL_GROUPS:
        durs = [a["dur"] for s in group for a in by_stage.get(s, []) if a["dur"] is not None]
        if durs:
            crit += max(durs)
    journal = os.path.join(folder, "journal.jsonl")
    results = 0
    if os.path.isfile(journal):
        try:
            with open(journal, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if '"type": "result"' in line or '"type":"result"' in line:
                        results += 1
        except OSError:
            errors.append("journal.jsonl 읽기 실패")
    else:
        errors.append("journal.jsonl 없음")
    return {
        "folder": folder,
        "wf": os.path.basename(folder),
        "agents": agents,
        "n_agents": len(agents),
        "wall": wall,
        "critical_path": crit if crit_known and crit > 0 else None,
        "advisor": sum(a["advisor"] for a in agents),
        "out_tok": sum(a["out_tok"] or 0 for a in agents),
        "thinking": sum(a["thinking"] or 0 for a in agents),
        "cache_read": sum(a["cache_read"] or 0 for a in agents),
        "cache_write": sum(a["cache_write"] or 0 for a in agents),
        "so_retries": sum(a["so_retries"] for a in agents),
        "so_errors": sum(a["so_errors"] for a in agents),
        "journal_results": results,
        "tokens_partial": bool(unavail),
        "stages_seen": sorted(by_stage.keys()),
        "errors": errors,
    }


def fmt(v, unit=""):
    return "unavailable" if v is None else f"{v}{unit}"


def print_detail(wf: dict) -> None:
    print(f"wf {wf['wf']}  agents={wf['n_agents']}  wall={fmt(round(wf['wall'], 1) if wf['wall'] is not None else None, 's')}"
          f"  critical_path={fmt(round(wf['critical_path'], 1) if wf['critical_path'] is not None else None, 's')}")
    lb = "≥" if wf["tokens_partial"] else ""
    print(f"  advisor={wf['advisor']}  out_tok={lb}{wf['out_tok']:,}  thinking={lb}{wf['thinking']:,}"
          f"  cache_r={wf['cache_read']:,}  cache_w={wf['cache_write']:,}  so_retries={wf['so_retries']}  so_errors={wf['so_errors']}"
          f"  journal_results={wf['journal_results']}")
    order = {s: i for i, s in enumerate(["S0", "S0-reb", "S0-fin", "S1", "S2-impact", "S2-edge", "S2-arch",
                                         "S3-imp", "S3-edge", "S4", "S5", "?"])}
    for a in sorted(wf["agents"], key=lambda x: (order.get(x["stage"], 99), x["file"])):
        ot = "unavail" if a["out_tok"] is None else f"{a['out_tok']:,}"
        th = "unavail" if a["thinking"] is None else f"{a['thinking']:,}"
        rc = f" ret={a['result_chars']:,}자" if a.get("result_chars") else ""
        print(f"    {a['stage']:9} {a['model']:8} dur={fmt(round(a['dur'], 1) if a['dur'] is not None else None, 's'):>9}"
              f" turns={a['turns']:>3} tools={a['tools']:>3} out={ot:>9} think={th:>9}"
              f" adv={a['advisor']} so={a['so_calls']}/{a['so_errors']}{rc}")
    for e in wf["errors"]:
        print(f"  ⚠️ {e}")


def print_row(wf: dict) -> None:
    """experiment-log §5.7 fz-plan 테이블 행 형식 (agentCalls·nullCount·stages·fallback·wall-clock)."""
    stages = len([s for s in wf["stages_seen"] if s != "?"])
    lb = "≥" if wf["tokens_partial"] else ""
    print(f"| N | DATE | {wf['n_agents']} | {max(0, wf['n_agents'] - wf['journal_results'])} | "
          f"{stages} | 0 | {fmt(round(wf['wall']) if wf['wall'] is not None else None, 's')} | "
          f"advisor {wf['advisor']} · so_retries {wf['so_retries']} · out_tok {lb}{wf['out_tok']:,} "
          f"(thinking {wf['thinking']:,}) · critical_path {fmt(round(wf['critical_path']) if wf['critical_path'] is not None else None, 's')} |")


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
    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    if fails:
        print(f"fz_wf_metrics self-test {passed}/{total} passed")
        return 1
    print(f"SELFTEST_OK (fz_wf_metrics self-test {passed}/{total} — 양성 1 · 음성 5)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Workflow 실행 stage 집계 (읽기 전용)")
    ap.add_argument("--root", default=DEFAULT_ROOT, help="트랜스크립트 루트 (기본 ~/.claude/projects)")
    ap.add_argument("--wf", help="wf_* 폴더명 또는 절대경로 — 1건 상세")
    ap.add_argument("--session", default="*", help="--wf 와 함께 쓰는 세션 glob")
    ap.add_argument("--expect", help="fixture JSON 과 대조 (성공 시 METRICS_OK)")
    ap.add_argument("--self-test", action="store_true", help="양성·음성 self-test")
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
