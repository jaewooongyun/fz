# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
"""ab_ledger_collect.py — A/B 원장 계측기의 한 부분: Workflow 폴더 · 상태 · 입력 · 플러그인 · GPT 로그 → 원장 행(build_row) · 원장 쓰기 · 읽기.

진입점 · 설계 · 측정 규약은 ab_ledger.py 머리말에 있다(이 파일은 그 실행 코드를 나눠 담는다).
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import datetime
import hashlib
import json
import os
import pathlib
import re
import shutil
import tempfile

import freeze_baseline as fb  # noqa: E402 — 형제 모듈(트리 파일 목록·해시)
import fz_wf_metrics as wfm   # noqa: E402 — 형제 모듈(Workflow 폴더 집계)
from ab_ledger_base import (MTIME_TOL_S, SCHEMA, STATE_SCHEMA, instrument_sha, iso, iter_jsonl, norm_model, read_json, secs,
    sha_obj)
from ab_ledger_transcript import (_launcher_ok, _same_path, gpt_home_sessions, parse_transcript)


# 반환·하네스 계수가 없을 때의 대체 완주 오라클 — 건강한 run 에서 **항상** 도는 stage (base 트리 실측)
#   peer-review 의 Stage 2 는 트리거·--deep, Stage 3 은 --deep 에서만 돈다 — 필수에 넣지 않는다
# ⛔ 열쇠는 **워크플로 스크립트 이름**(transcript 의 Workflow 결과 `workflowName`)이다 — 스킬 이름이 아니다(F-335 ⑥).
#    stage 는 스크립트가 낸다. 스킬 이름으로 찾으면 스킬이 다른 스크립트를 부른 run(예: 계획 스킬의 다른 변형)에
#    엉뚱한 stage 를 요구하거나, 같은 스크립트를 다른 스킬 이름으로 수집한 run 이 '표 없음' 으로 미완주가 된다.
STAGES_BY_SCRIPT = {
    "plan-lean2": ("L1-full", "L1-edge", "L1-impact", "L2-merge"),
    "review-live": ("R1-arch", "R1-quality", "R2-arch", "R2-quality", "R3-counter"),
    "peer-review": ("R1-arch", "R1-quality", "R1-correct"),
}
# 스킬 → 기본 스크립트 — 표시와 호환 보기(REQUIRED_STAGES · tests/workflows/stage-rules-real.js 가 스킬 배선을 대조)에만 쓴다
SKILL_SCRIPTS = {"fz-plan": "plan-lean2", "fz-review": "review-live", "fz-peer-review": "peer-review"}
REQUIRED_STAGES = {sk: STAGES_BY_SCRIPT[sc] for sk, sc in SKILL_SCRIPTS.items()}


# ── Workflow 폴더 · 상태 · 입력 · 플러그인 · GPT 로그 ─────────────────────────
REQUIRED_WATCH = ("user_agent_memory", "repo_agent_memory", "user_sessions")   # 프로토콜 §2 — 없으면 AC-7 판정 불가
# 이름별 정본 경로 — 이름만 맞고 엉뚱한 곳을 보면 감시가 아니다(repo_agent_memory 는 그 run 의 입력 저장소 안)
CANON_WATCH = {"user_agent_memory": "~/.claude/agent-memory", "user_sessions": "~/.claude/sessions"}
# 폴더에 다른 주체의 파일이 섞인 감시 이름은 파일 패턴도 정본이어야 한다(세션 등록·키 파일은 run 마다 바뀐다)
CANON_PATTERN = {"user_sessions": "SESSION-*_issues.json"}
ALLOWED_PLUGIN_WRITES = ("experiment-log.md",)   # 스킬이 플러그인 루트에 쓰는 지표 파일(RV:103 · PL:139) — 코드 아님


def required_stages(script, stage2_ran, tier=None):
    """건강한 run 에서 반드시 돈 stage — 워크플로 스크립트 이름으로 찾고, 반환이 알려 준 실행 모드(tier·Stage 2)를 따른다."""
    need = list(STAGES_BY_SCRIPT.get(script, ()))
    if script == "review-live" and stage2_ran is False:   # 조건부 Stage 2 arm 이 '안 돌렸다' 고 반환한 경우만 뺀다
        need = [x for x in need if not x.startswith("R2-")]
    if script == "peer-review":
        if stage2_ran:
            need += ["R2-arch", "R2-quality"]
        if tier == 3:
            need += ["R3-counter"]
    return need


def expected_stages_completed(script, stage2_ran, tier=None):
    """반환 metrics.stagesCompleted 의 기대값 — 스크립트 이름으로 찾는다(base 트리 실측 — plan-lean2:231 · review-live:220 ·
    peer-review:385·449·511). 모르는 스크립트는 None(기대 없음 → 반환 metrics 가 있으면 미완주)."""
    if script == "plan-lean2":
        return 2
    if script == "review-live":
        return 2 if stage2_ran is False else 3
    if script == "peer-review":
        if tier == 3:
            return 3
        if tier == 2:
            return 2 if stage2_ran else 1
    return None


def wf_summary(folder):
    if not folder or not os.path.isdir(folder):
        return None
    # ⛔ journal.jsonl · agent-*.jsonl 은 fz_wf_metrics 가 한 번씩만 읽는다 — 여기서 다시 열지 않고 그 판독을 쓴다(F-335 ⑤).
    #    journal started 수 · 빈·오류 결과 수(건수만 세면 빈 결과도 완주로 읽힌다) · 응답별 model · effort 가 그 판독에 있다
    w = wfm.read_wf(folder)
    models, efforts = collections.Counter(), collections.Counter()
    for ag in w["agents"]:
        for m, e in ag["msg_models"]:
            if m and m != "<synthetic>":
                models[norm_model(m)] += 1
                if e:
                    efforts[e] += 1
    return {
        "run_id": w["wf"], "dir": folder, "n_agents": w["n_agents"], "journal_results": w["journal_results"],
        "journal_started": w["journal_started"], "journal_empty_results": w["journal_empty_results"],
        "wall_s": w["wall"], "critical_path_s": w["critical_path"], "advisor": w["advisor"],
        "out_tok": w["out_tok"], "thinking": w["thinking"], "turns": sum(a["turns"] for a in w["agents"]),
        "so_retries": w["so_retries"], "so_errors": w["so_errors"], "stages": w["stages_seen"],
        "tokens_partial": w["tokens_partial"], "errors": w["errors"],
        "bad_lines": sum(a["bad_lines"] for a in w["agents"]),
        "workers": [{"stage": a["stage"], "out_tok": a["out_tok"], "turns": a["turns"], "tools": a["tools"],
                     "dur_s": a["dur"]} for a in w["agents"]],
        "models": dict(models), "efforts": dict(efforts),
    }


def snapshot(watch: dict) -> dict:
    """{이름: 경로[::파일 패턴]} → 존재 여부 + 파일별 sha256. 해시는 **이름·존재·상대 경로·내용**만 본다 — run 마다
    저장소 경로가 달라도 같다(경로는 기록만 한다). `::패턴` 은 폴더 안에서 그 패턴(fnmatch)에 맞는 파일만 본다 —
    `~/.claude/sessions` 처럼 다른 주체의 파일(세션 등록·키)이 섞인 폴더에서 fz 트래커만 감시할 때 쓴다."""
    import fnmatch
    out = {}
    for name, spec in sorted(watch.items()):
        path, _, pattern = spec.partition("::")
        p = pathlib.Path(os.path.expanduser(path))
        files = {}
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                rel = str(f.relative_to(p))
                if f.is_file() and (not pattern or fnmatch.fnmatch(rel, pattern)):
                    files[rel] = fb.hash_file(f)
        elif p.is_file():
            files[p.name] = fb.hash_file(p)
        out[name] = {"path": str(p), "pattern": pattern or None, "exists": p.exists(), "files": files}
    return {"schema": STATE_SCHEMA, "watch": out, "hash": state_hash(out)}


def _state_key(v):
    return [bool((v or {}).get("exists")), (v or {}).get("files", {})]


def state_hash(watch) -> str:
    return sha_obj({k: _state_key(v) for k, v in watch.items()})


def state_diff(a, b):
    """두 스냅샷에서 존재·파일 집합·내용이 다른 이름. 한쪽에만 있는 이름은 '없음' 과 비교한다."""
    return [n for n in sorted(set(a) | set(b)) if _state_key(a.get(n)) != _state_key(b.get(n))]


def state_info(pristine, start, end, input_root=None):
    """→ 해시 · leak(시작 ≠ 기준) · writes(종료 − 시작) · problems(감시 누락·경로 불일치 — AC-7 판정 불가)."""
    try:
        p, s = read_json(pristine), read_json(start)
    except (OSError, ValueError, TypeError):
        return {"start_hash": None, "pristine_hash": None, "end_hash": None, "leak": None, "writes": None,
                "problems": ["스냅샷을 읽지 못했다"]}
    e = None
    try:
        e = read_json(end) if end else None
    except (OSError, ValueError):
        e = None
    snaps = [("pristine", p), ("start", s)] + ([("end", e)] if e else [])
    problems = [f"{which} 에 감시 이름 {n} 없음" for which, snap in snaps
                for n in REQUIRED_WATCH if n not in (snap.get("watch") or {})]
    if not e:
        problems.append("종료 스냅샷 없음")
    for which, snap in snaps:
        for n, canon in CANON_WATCH.items():
            w = (snap.get("watch") or {}).get(n) or {}
            got = w.get("path")
            if got and os.path.expanduser(got) != os.path.expanduser(canon):
                problems.append(f"{which} 의 {n} 경로가 정본({canon})이 아니다: {got}")
            if n in CANON_PATTERN and w and w.get("pattern") != CANON_PATTERN[n]:
                problems.append(f"{which} 의 {n} 파일 패턴이 정본({CANON_PATTERN[n]})이 아니다: {w.get('pattern')}")
    rp = ((s.get("watch") or {}).get("repo_agent_memory") or {}).get("path")
    want = os.path.join(os.path.realpath(input_root), ".claude", "agent-memory") if input_root else None
    if not rp:
        problems.append("start 의 repo_agent_memory 경로가 비었다")
    elif want and os.path.realpath(rp) != want:
        problems.append(f"repo_agent_memory 감시 경로가 입력 저장소의 .claude/agent-memory 가 아니다: {rp}")
    # ⛔ 종료 쪽도 같은 곳을 봐야 한다 — 경로는 해시 키가 아니라서, 둘 다 빈 다른 폴더면 '쓰기 없음' 으로 같게 읽힌다(v4.40.0 리뷰)
    ep = ((e.get("watch") or {}).get("repo_agent_memory") or {}).get("path") if e else None
    if e and rp and (not ep or os.path.realpath(ep) != os.path.realpath(rp)):
        problems.append(f"end 의 repo_agent_memory 경로가 start 와 다르다: {ep}")
    writes = None
    if e:
        writes = {}
        for n in state_diff(s["watch"], e["watch"]):
            a = (s["watch"].get(n) or {}).get("files", {})
            b = (e["watch"].get(n) or {}).get("files", {})
            writes[n] = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return {"start_hash": state_hash(s["watch"]), "pristine_hash": state_hash(p["watch"]),
            "end_hash": state_hash(e["watch"]) if e else None,
            "leak": state_diff(p["watch"], s["watch"]), "writes": writes, "problems": problems}


def input_commits(root):
    commits = {}
    if root and os.path.isdir(root):
        for ref in ("main", "feature"):
            out = fb.git(pathlib.Path(root), "rev-parse", "--verify", "--quiet", ref + "^{commit}")
            if out and out.strip():
                commits[ref] = out.strip()
        if not commits:
            out = fb.git(pathlib.Path(root), "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
            if out and out.strip():
                commits["HEAD"] = out.strip()
    return commits


def tree_digest(root, exclude=()):
    """git 이 보는 작업 트리 파일(추적 + 미추적 비무시)의 내용 해시 — freeze_baseline 헬퍼. exclude 는 루트 상대 경로."""
    files = fb.tree_files(pathlib.Path(root), exclude=exclude) if root and os.path.isdir(root) else None
    if not files:
        return None
    got, unread = fb.collect_hashes(pathlib.Path(root), files)
    return None if unread else sha_obj(got)


def input_hash(fixture, commits, prompt_sha, tree=None):
    if not commits or not prompt_sha:
        return None
    return sha_obj({"fixture": fixture, "commits": commits, "prompt_sha": prompt_sha, "tree": tree})


def plugin_info(root):
    if not root or not os.path.isdir(root):
        return {"root": root, "sha": None, "dirty": None, "tree_hash": None}
    p = pathlib.Path(root)
    sha = (fb.git(p, "rev-parse", "HEAD") or "").strip() or None
    st = fb.git(p, "status", "--porcelain", "--untracked-files=all")
    return {"root": root, "sha": sha, "dirty": (bool(st.strip()) if st is not None else None), "tree_hash": tree_digest(root),
            "code_hash": tree_digest(root, exclude=ALLOWED_PLUGIN_WRITES)}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def parse_gpt_log(path):
    """GPT 스트림 로그 배너 → model·reasoning effort·CLI 버전·session id. 둘째 구분선 전까지만 본다."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = ANSI_RE.sub("", fh.read()).splitlines()
    except (OSError, TypeError):
        return None
    info = {"model": None, "effort": None, "version": None, "session": None}
    seps = 0
    for line in lines[:60]:
        if line.startswith("--------"):
            seps += 1
            if seps >= 2:
                break
            continue
        m = re.match(r"^model:\s*(\S+)", line)
        if m:
            info["model"] = m.group(1)
        m = re.match(r"^reasoning effort:\s*(\S+)", line)
        if m:
            info["effort"] = m.group(1)
        m = re.match(r"^session id:\s*([0-9a-f-]{36})", line)
        if m:
            info["session"] = m.group(1)
        m = re.search(r"\bv(\d+\.\d+\.\d+)\s*$", line)
        if m and seps == 0 and not info["version"]:
            info["version"] = m.group(1)
    return info


# ── collect ────────────────────────────────────────────────────────────
# CollectSpec — 원장 행의 collect_args 에 저장하는 수집 인자(F-335 ④). ⛔ 저장 키는 **이 필드 이름**이다 — CLI 의 전역 플래그
#   (--self-test · --case)나 argparse 내부 키(func · cmd)가 영속 스키마에 새지 않는다. recollect · 원천 대조는 이 필드만 읽고
#   (collect_spec_args), 옛 형식 행(버전 없음 · vars(a) 그대로)도 모르는 키를 버리고 없는 필드를 기본값으로 읽는다.
#   필드를 더하는 것은 호환 변경이다(기본값). 필드의 뜻을 바꾸면 버전을 올린다.
COLLECT_SPEC_VERSION = "collect/1"
COLLECT_SPEC = (("ledger", None), ("workflow", None), ("arm", None), ("run", None), ("order", None), ("phase", None),
                ("release", None), ("run_id", None), ("fixture", None), ("transcript", None), ("artifact", None),
                ("input_root", None), ("input_json", None), ("state_pristine", None), ("state_start", None),
                ("state_end", None), ("gpt_log", None), ("gpt_log_dir", None), ("evidence_dir", None), ("tasks_dir", None),
                ("endpoint_clock", None), ("endpoint_clock_source", None))


def collect_spec_args(src):
    """collect 인자(argparse Namespace · 원장 행의 collect_args dict) → CollectSpec 필드만 담은 Namespace."""
    d = vars(src) if isinstance(src, argparse.Namespace) else dict(src or {})
    return argparse.Namespace(**{k: d.get(k, v) for k, v in COLLECT_SPEC})


def _evidence_dir(a):
    return a.evidence_dir or os.path.join(os.path.dirname(os.path.abspath(a.ledger)), "evidence")


def _clock_time(v):
    """시계 줄의 t → aware datetime(UTC). 숫자는 epoch 초, 문자열은 시간대가 있는 ISO-8601 — 그 밖은 None."""
    if type(v) in (int, float):
        return datetime.datetime.fromtimestamp(v, datetime.timezone.utc)
    t = wfm._ts(v) if isinstance(v, str) else None
    return t if t is not None and t.tzinfo is not None else None


def read_endpoint_clock(path):
    """러너 끝점 시계(JSONL) → (관측 목록, 문제). 줄 = {t, path, size, mtime, sha256} — 형식: docs/ab-endpoint-clock.md.
    ⛔ 형식 위반 줄을 건너뛰고 나머지로 끝점을 정하지 않는다 — 위반이 있으면 문제로 남겨 run 이 미완주가 된다."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, TypeError, UnicodeDecodeError) as e:
        return [], [f"끝점 시계를 읽지 못했다 {path} ({type(e).__name__})"]
    rows, bad = [], []
    for i, ln in enumerate(lines, 1):
        if not ln.strip():
            continue
        try:
            o = json.loads(ln)
        except ValueError:
            o = None
        t = _clock_time(o.get("t")) if isinstance(o, dict) else None
        if not (t is not None and isinstance(o.get("path"), str) and os.path.isabs(o["path"]) and type(o.get("size")) is int
                and type(o.get("mtime")) in (int, float) and isinstance(o.get("sha256"), str)
                and re.fullmatch(r"[0-9a-f]{64}", o["sha256"])):
            bad.append(i)
            continue
        rows.append(dict(o, _t=t))
    probs = [f"끝점 시계 형식 위반 줄 {bad[:5]}{' …' if len(bad) > 5 else ''} ({path})"] if bad else []
    if not rows and not bad:
        probs.append(f"끝점 시계가 비었다 ({path})")
    return rows, probs


def apply_endpoint_clock(tp, rows):
    """러너 시계로 끝점을 정한다 → 문제 목록. 산출물마다 그 경로의 **마지막 관측**(t 최대)이 기록 시각이다 — transcript 파서가
    더 이른 쓰기를 봤어도 시계가 이긴다(파서는 명령 문자열만 본다).
    ⛔ 끝점 근거는 러너 관측 시각 t 다. mtime 은 교차 대조에만 쓴다(AC-12) — 시계에 적힌 mtime 과 파일 mtime 이 MTIME_TOL_S 를
       넘게 어긋나거나 sha256 이 다르면 마지막 관측 뒤 파일이 바뀐 것이라 미완주로 둔다. mtime_delta_s 는 (파일 − 시계 기록) mtime 이다."""
    probs, writes, deltas = [], [], []
    for x in tp["artifacts"]:
        mine = [r for r in rows if _same_path(r["path"], x["path"])]
        if not mine:
            probs.append(f"끝점 시계에 산출물 관측 없음 {x['path']}")
            continue
        last = max(mine, key=lambda r: r["_t"])
        writes.append(last["_t"])
        if x["mtime"] is not None:
            d = x["mtime"] - last["mtime"]
            deltas.append(d)
            if abs(d) > MTIME_TOL_S:
                probs.append(f"끝점 시계 mtime 불일치 {x['path']}: 시계 {last['mtime']} · 파일 {x['mtime']} "
                             f"(Δ={round(d, 3)}s · 허용 {MTIME_TOL_S}s) — 마지막 관측 뒤 파일이 바뀌었다")
        if x["sha256"] is not None and last["sha256"] != x["sha256"]:
            probs.append(f"끝점 시계의 마지막 관측과 산출물 내용이 다르다(sha256) {x['path']}")
    tp["end"] = max(writes) if writes and len(writes) == len(tp["artifacts"]) else None
    tp["mtime_delta_s"] = round(max(deltas, key=abs), 3) if deltas and len(deltas) == len(tp["artifacts"]) else None
    return probs


def _endpoint_clock_evidence(a, evdir, dry):
    """--endpoint-clock 파일 → (읽을 경로, 원본 경로, sha256). collect 는 증거 폴더에 내용 해시 이름으로 사본을 남기고 **사본을** 읽는다 —
    recollect · 원천 대조가 원본 시계의 변조 · 삭제와 무관하게 같은 끝점을 다시 만든다. dry(원천 대조)는 사본을 쓰지 않는다."""
    src = os.path.abspath(a.endpoint_clock)
    orig = getattr(a, "endpoint_clock_source", None) or src
    try:
        with open(src, "rb") as fh:
            data = fh.read()
    except OSError:
        return src, orig, None
    sha = hashlib.sha256(data).hexdigest()
    copy = os.path.join(evdir, f"endpoint-clock.{sha[:16]}.jsonl")
    if not dry and not _same_path(src, copy):
        os.makedirs(evdir, exist_ok=True)
        with open(copy, "wb") as fh:
            fh.write(data)
    return (src if dry else copy), orig, sha


def build_row(a, dry=False) -> dict:
    """원천 → 원장 행. dry=True 는 원천 대조용 재구성이다(증거 사본을 쓰지 않는다).
    - Important: 인자는 CollectSpec 필드로 읽는다 — 옛 행의 collect_args 를 그대로 Namespace 로 넘겨도 없는 필드는 기본값이다."""
    evdir = _evidence_dir(a)
    tp = parse_transcript(a.transcript, a.artifact or [], list(a.tasks_dir or []) + [evdir])
    why = []
    clock = None
    if getattr(a, "endpoint_clock", None):
        # 러너 끝점 시계(F-335 ⑫) — 명령 문자열 파서(동결)가 모르는 쓰기도 러너가 본 시각으로 끝점을 정한다
        path, orig, sha = _endpoint_clock_evidence(a, evdir, dry)
        rows_, probs = read_endpoint_clock(path)
        parser_end, parser_delta = tp["end"], tp["mtime_delta_s"]
        if rows_ and not probs:
            probs = apply_endpoint_clock(tp, rows_)
        else:   # ⛔ 읽지 못한 · 형식 위반 시계로 파서 끝점에 물러서지 않는다(시계를 준 run 의 끝점 근거는 시계다)
            tp["end"], tp["mtime_delta_s"] = None, None
        why += probs
        clock = {"path": path, "original": orig, "sha256": sha, "observations": len(rows_),
                 "parser_end": iso(parser_end), "parser_mtime_delta_s": parser_delta}
    if tp["bad_lines"]:
        why.append(f"transcript 파싱 불가 줄 {tp['bad_lines']}")
    if not tp["start"]:
        why.append("첫 사람 발화 없음")
    wf_runs, walls = [], []
    for w in tp["workflows"]:
        if w["rejected"]:
            continue
        s = wf_summary(w["dir"])
        entry = {k: w[k] for k in ("run_id", "name", "launch", "done", "status", "lead_s", "return_mode",
                                   "metrics", "stage2_ran", "return_source", "agent_count")}
        entry["summary"] = s
        if w["return_source"] == "output-file":
            # ⛔ /tmp 의 하네스 산출은 지워질 수 있다 — 같은 파일명으로 사본을 남겨 재구성 대조가 찾게 한다
            entry["return_file"] = os.path.join(evdir, os.path.basename(w["output_file"]))
            if not dry and not _same_path(w["output_file"], entry["return_file"]):
                os.makedirs(evdir, exist_ok=True)
                shutil.copyfile(w["output_file"], entry["return_file"])
        wf_runs.append(entry)
        if w["status"] != "completed":
            why.append(f"{w['run_id']}: 완료 알림 없음·상태 {w['status']}")
        if s is None:
            why.append(f"{w['run_id']}: Workflow 폴더 없음 ({w['dir']})")
            walls.append({"run_id": w["run_id"], "wf_s": None, "lead_s": w["lead_s"], "delta_pct": None})
            continue
        if s["bad_lines"] or s["errors"]:
            why.append(f"{w['run_id']}: 폴더 오류 {s['errors'][:2]}")
        if s["journal_empty_results"]:
            why.append(f"{w['run_id']}: 빈·오류 결과 {s['journal_empty_results']}건")
        script = w["name"]   # 워크플로 스크립트 이름 — 완주 오라클의 열쇠(스킬 이름 a.workflow 는 표시만)
        lost = [x for x in required_stages(script, w["stage2_ran"], w["tier"]) if x not in s["stages"]]
        if lost or script not in STAGES_BY_SCRIPT:
            why.append(f"{w['run_id']}: 필수 stage 누락 {lost or f'(필수 stage 표 없음 — 워크플로 스크립트 {script!r})'}")
        exp_sc = expected_stages_completed(script, w["stage2_ran"], w["tier"])
        got_sc = (w["metrics"] or {}).get("stagesCompleted")
        if w["metrics"] is not None and (exp_sc is None or got_sc != exp_sc):
            why.append(f"{w['run_id']}: stagesCompleted={got_sc} ≠ 기대 {exp_sc} (tier={w['tier']} stage2={w['stage2_ran']})")
        mt = w["metrics"]
        if w.get("return_conflict"):
            why.append(f"{w['run_id']}: 알림의 반환과 하네스 래퍼의 반환이 다르다(metrics·mode)")
        if mt is not None:
            # 주 오라클 — 스크립트 자기 계수 · 하네스 계수 · 폴더 계수가 모두 같아야 한다
            entry["oracle"] = "return-metrics" + ("+harness" if w["agent_count"] is not None else "")
            if w["return_mode"] != "workflow":
                why.append(f"{w['run_id']}: 반환 mode={w['return_mode']}")
            miss = [k for k in ("agentCalls", "nullCount", "fallbackCount") if not isinstance(mt.get(k), int)]
            if miss:
                why.append(f"{w['run_id']}: 반환 metrics 필드 누락 {miss} — 0 으로 읽지 않는다")
            elif mt["nullCount"] > 0 or mt["fallbackCount"] > 0:
                why.append(f"{w['run_id']}: nullCount={mt['nullCount']} fallbackCount={mt['fallbackCount']}")
            exp = mt.get("agentCalls")
            if not (s["n_agents"] == s["journal_results"] == s["journal_started"] == exp) or \
                    (w["agent_count"] is not None and w["agent_count"] != exp):
                why.append(f"{w['run_id']}: agents={s['n_agents']} started={s['journal_started']} "
                           f"results={s['journal_results']} agentCalls={exp} harness={w['agent_count']} — 완주 오라클 불일치")
        else:
            # 대체 오라클 — 반환을 못 읽었다(알림 잘림 + output-file 소실). 시작=결과=폴더 + 필수 stage(위)
            entry["oracle"] = "journal+stages"
            if script == "peer-review":
                why.append(f"{w['run_id']}: 반환 없이는 실행 모드(tier·Stage 2)를 확인할 수 없다 — peer-review 는 대체 오라클 불가")
            if not (s["journal_started"] == s["journal_results"] == s["n_agents"]) or not s["n_agents"]:
                why.append(f"{w['run_id']}: 반환 없음 · started={s['journal_started']} results={s['journal_results']} "
                           f"agents={s['n_agents']} — 대체 오라클 불충족")
        wf_s, lead_s = s["wall_s"], w["lead_s"]
        delta = round(abs(wf_s - lead_s) / max(wf_s, lead_s) * 100, 2) if wf_s and lead_s else None
        walls.append({"run_id": w["run_id"], "wf_s": wf_s, "lead_s": lead_s, "delta_pct": delta})
    if not wf_runs:
        why.append("Workflow 미기동")
    if not a.artifact:
        why.append("--artifact 없음")
    elif not tp["end"]:
        why.append("최종 산출물 기록 이벤트 없음")
    for x in tp["artifacts"]:
        if x["sha256"] is None:
            why.append(f"산출물 없음 {x['path']}")
        elif x["blank"]:
            why.append(f"빈 산출물(공백뿐) {x['path']}")
    roots = tp["roots"]
    plugin = plugin_info(roots[0] if len(roots) == 1 else None)
    plugin["roots"] = roots
    if len(roots) != 1:
        why.append(f"플러그인 경로 {len(roots)}개(1개여야 한다): {roots}")
    inp = read_json(a.input_json) if a.input_json and os.path.isfile(a.input_json) else None
    if inp is None:
        # ⛔ 증거 부재 = 위반 — run 전 입력 신원(clean·트리 해시·플러그인)이 없으면 입력을 증명하지 못한다
        why.append(f"입력 기록 없음 {a.input_json}")
    root = os.path.realpath((inp or {}).get("root") or a.input_root) if ((inp or {}).get("root") or a.input_root) else None
    commits = (inp or {}).get("commits") if inp else input_commits(a.input_root)
    if inp:
        if inp.get("fixture") != a.fixture:
            why.append(f"입력 기록의 fixture {inp.get('fixture')} ≠ {a.fixture}")
        if inp.get("clean") is not True:
            why.append("입력 저장소가 run 전에 깨끗하지 않았다(미커밋·미추적 파일)")
        if not inp.get("tree_hash"):
            why.append("입력 트리 해시 없음 — 입력 신원을 증명하지 못한다")
    if root and tp["cwd"] and not (os.path.realpath(tp["cwd"]) + os.sep).startswith(root + os.sep):
        why.append(f"Lead 작업 폴더 {tp['cwd']} 가 입력 저장소 {root} 밖이다")
    pstart = (inp or {}).get("plugin")
    if not pstart:
        why.append("run 전 플러그인 신원 없음(input --plugin-root) — 실행 중 코드 변경을 판정하지 못한다")
    elif not pstart.get("source_tree_hash"):
        why.append("플러그인 원본 해시 없음(input --plugin-source) — 사본의 원본을 증명하지 못한다")
    if not a.state_end or not os.path.isfile(a.state_end):
        why.append("종료 스냅샷 없음 — run 중 상태 변화 기록이 없다")
    if pstart:
        # run 전에 잰 신원을 쓴다. 이 run 이 사본에 쓴 흔적(experiment-log 등)은 changed_during_run 으로만 남긴다
        if len(roots) == 1 and not _same_path(pstart.get("root"), roots[0]):
            why.append(f"transcript 의 플러그인 경로 {roots[0]} ≠ run 전 기록 {pstart.get('root')}")
        plugin = dict(pstart, roots=roots, changed_during_run=plugin.get("tree_hash") != pstart.get("tree_hash"),
                      code_changed_during_run=plugin.get("code_hash") != pstart.get("code_hash"))
        if plugin["code_changed_during_run"]:
            why.append("실행 중 플러그인 코드가 바뀌었다(허용 출력 " + ",".join(ALLOWED_PLUGIN_WRITES) + " 제외) — 측정 대상이 바뀐 run")
    else:
        plugin["at"] = "collect"
    gpt_logs = list(a.gpt_log or []) + [p for g in tp["gpt"] for p in [g.get("log") or (g["out"] + ".stream.log" if g["out"] else None)]
                                        if p and os.path.isfile(p)]
    # `--out "$W/…"` 처럼 변수로 쓴 호출은 경로를 풀 수 없다 — 지정 폴더에서 run 구간에 쓰인 로그를 찾는다
    lo = tp["start"].timestamp() - 5 if tp["start"] else None
    hi = tp["end"].timestamp() + 60 if tp["end"] else None
    for d in a.gpt_log_dir or []:
        for p in sorted(pathlib.Path(d).rglob("*.stream.log")):
            mt = p.stat().st_mtime
            if (lo is None or mt >= lo) and (hi is None or mt <= hi):
                gpt_logs.append(str(p))
    # ⛔ 호출마다 **자기** 배너를 1:1 로 붙인다 — 폴더의 로그 수만 세면 다른 run 의 로그가 빈자리를 채운다
    logs = []
    for pth in dict.fromkeys(gpt_logs):
        b = parse_gpt_log(pth)
        try:
            mt = os.path.getmtime(pth)
        except OSError:
            mt = None
        if b and b["model"] and b["effort"]:
            logs.append((pth, mt, b))
    used, banners, unlinked = set(), [], 0
    for g in tp["gpt"]:
        if not g["ok"]:
            continue
        direct = g.get("log") or (g["out"] + ".stream.log" if g["out"] and "$" not in g["out"] else None)
        in_win = lambda x: x[1] is not None and g["t0"] is not None and g["t1"] is not None and g["t0"] - 2 <= x[1] <= g["t1"] + 30
        # ⛔ 직접 경로도 시간창 안이어야 한다(같은 경로에 남은 이전 run 로그) · 변수 경로는 후보가 **하나**일 때만
        cand = [x for x in logs if x[0] not in used and in_win(x) and (x[0] == direct if direct else True)]
        if len(cand) != 1:
            unlinked += 1
            continue
        used.add(cand[0][0])
        banners.append(dict(cand[0][2], explicit=g.get("explicit_effort", False)))
    # ② 런처(gpt_independent.sh) — 격리 폴더에서 돌아 arm 홈에 rollout 이 없다. 감사 옆 스트림 로그 배너로 model · effort 를 본다.
    #    effort 는 런처가 정한다(명시) — F-333 의 환경 기본값 비교에 넣지 않는다
    launched = launched_ok = 0
    for d in a.gpt_log_dir or []:
        for au in sorted(pathlib.Path(d).rglob("*.audit.json")):
            mt = au.stat().st_mtime
            if (lo is None or mt >= lo) and (hi is None or mt <= hi):
                b = parse_gpt_log(str(au)[:-len(".audit.json")] + ".json.stream.log")
                if b and b["model"] and b["effort"]:
                    banners.append(dict(b, explicit=True, launcher=True))
                    launched += 1
                    if _launcher_ok(au):
                        launched_ok += 1
    # ③ arm 별 GPT 홈 rollout 과 대조 — 명령과 연결되지 않은 세션(nohup 으로 떼어 띄운 호출)은 model · 버전만 비교에 넣고 수를 남긴다
    run_dir = os.path.dirname(os.path.realpath(a.input_json)) if a.input_json else None
    sessions = gpt_home_sessions(os.path.join(run_dir, "gpt-home")) if run_dir else None
    linked = {b.get("session") for b in banners if b.get("session")}
    invisible = [x for x in (sessions or []) if x["session"] not in linked]
    gw = [g["wall_s"] for g in tp["gpt"] if g["wall_s"] is not None]
    wsum = [s for s in (r["summary"] for r in wf_runs) if s]
    stages_completed = [(r["metrics"] or {}).get("stagesCompleted") for r in wf_runs]
    row = {
        "type": "run", "schema": SCHEMA, "run_id": a.run_id or f"{a.workflow}:{a.arm}:{a.run}:{a.phase}",
        "workflow": a.workflow, "arm": a.arm, "run": a.run, "order": a.order, "phase": a.phase,
        "release": a.release, "fixture": a.fixture,
        "lead": tp["lead"], "plugin": plugin, "injected": tp["injected"], "instrument_sha": instrument_sha(),
        "input": {"hash": input_hash(a.fixture, commits, tp["prompt_sha"], (inp or {}).get("tree_hash")),
                  "fixture": a.fixture, "root": root, "commits": commits, "prompt_sha": tp["prompt_sha"],
                  "tree_hash": (inp or {}).get("tree_hash")},
        "wall": {"total_s": secs(tp["start"], tp["end"]), "start": iso(tp["start"]), "end": iso(tp["end"]),
                 "mtime_delta_s": tp["mtime_delta_s"], "workflows": walls, "gpt_s": round(sum(gw), 3) if gw else None},
        "artifacts": [{"path": x["path"], "sha256": x["sha256"], "bytes": x["bytes"]} for x in tp["artifacts"]],
        "wf": {"runs": wf_runs, "agents": sum(s["n_agents"] for s in wsum),
               "out_tok": sum(s["out_tok"] for s in wsum) if wsum else None,
               "turns": sum(s["turns"] for s in wsum) if wsum else None,
               "so_retries": sum(s["so_retries"] for s in wsum) if wsum else None,
               "so_errors": sum(s["so_errors"] for s in wsum) if wsum else None,
               "advisor": sum(s["advisor"] for s in wsum),
               "models": dict(sum((collections.Counter(s["models"]) for s in wsum), collections.Counter())),
               "efforts": dict(sum((collections.Counter(s["efforts"]) for s in wsum), collections.Counter())),
               "stages": sorted({st for s in wsum for st in s["stages"]}),
               "stage2_ran": next((r["stage2_ran"] for r in wf_runs if r["stage2_ran"] is not None),
                                  any(st.startswith("R2-") for s in wsum for st in s["stages"]) if wsum else None),
               "stages_completed": (min(stages_completed) if stages_completed and None not in stages_completed else None),
               "rejections": sum(1 for w in tp["workflows"] if w["rejected"])},
        "gpt": {"calls": len(tp["gpt"]), "ok": sum(1 for g in tp["gpt"] if g["ok"]),
                "failed": sum(1 for g in tp["gpt"] if not g["ok"]), "banners": len(banners), "unlinked": unlinked,
                "models": sorted({b["model"] for b in banners} | {x["model"] for x in invisible}),
                "efforts": sorted({b["effort"] for b in banners}),
                "efforts_default": sorted({b["effort"] for b in banners if not b.get("explicit")}),
                "versions": sorted({b["version"] for b in banners if b["version"]} | {x["version"] for x in invisible if x["version"]}),
                "logs": sorted(set(gpt_logs)), "launcher": launched, "launcher_ok": launched_ok,
                "real_home_skill_refs": sum(1 for g in tp["gpt"] if g.get("real_home_skill")),
                "sessions": None if sessions is None else len(sessions), "invisible": len(invisible)},
        "state": state_info(a.state_pristine, a.state_start, a.state_end, root),
        "sources": {"transcript": os.path.abspath(a.transcript), "artifacts": [os.path.abspath(x) for x in a.artifact or []],
                    "wf_dirs": [w["dir"] for w in tp["workflows"] if not w["rejected"]],
                    "state_pristine": a.state_pristine, "state_start": a.state_start, "state_end": a.state_end,
                    "input_root": a.input_root, "input_json": a.input_json, "tasks_dirs": list(a.tasks_dir or []),
                    # ⛔ 재구성은 run 별 플러그인 사본이 디스크에 있어야 한다(roots 는 실재 경로만 · plugin_info 해시) — 원천으로 적는다(F-335 ⑨)
                    "plugin_roots": roots or ([pstart["root"]] if (pstart or {}).get("root") else [])},
        "collect_args": dict({k: getattr(a, k, v) for k, v in COLLECT_SPEC}, spec=COLLECT_SPEC_VERSION),
    }
    if clock is not None:
        # 시계는 사본으로 저장한다 — recollect 가 원본 대신 사본을 읽는다(CollectSpec 필드 endpoint_clock · endpoint_clock_source)
        row["collect_args"].update(endpoint_clock=clock["path"], endpoint_clock_source=clock["original"])
        row["sources"]["endpoint_clock"] = {k: clock[k] for k in ("path", "original", "sha256")}
        row["wall"]["clock"] = {k: clock[k] for k in ("observations", "parser_end", "parser_mtime_delta_s")}
    row["merge"] = tp.get("merge")
    # S26 — GPT 독립 플랜 wall 이 Workflow wall 을 넘으면 임계 경로가 GPT 로 바뀐 것이다(계획 S26: 기록형 판정)
    lp = [x["wall_s"] for x in tp.get("launcher") or [] if x["mode"] == "plan" and x["wall_s"] is not None]
    ws = [w["lead_s"] for w in tp.get("workflows") or [] if w.get("lead_s") is not None and not w.get("rejected")]
    row["critical"] = {"gpt_plan_s": round(max(lp), 1) if lp else None, "wf_s": round(max(ws), 1) if ws else None,
                       "launchers": tp.get("launcher") or [],
                       "path": None if not (lp and ws) else ("gpt" if max(lp) > max(ws) else "workflow")}
    row["lead"]["queued_followups"] = tp.get("queued_followups", 0)
    if tp.get("queued_followups"):
        why.append(f"후속 턴이 모델 작업 중에 끼어들었다 {tp['queued_followups']}회(queued_command) — 표준 후속 턴 계약 위반")
    if a.workflow == "fz-plan" and not tp.get("plan_phase2"):
        why.append("plan Phase 2 GPT 검증 흔적 없음(verify · resume 교차 미실행) — 절차 미완주")
    row["complete"] = {"ok": not why, "why": why}
    return row


import contextlib   # noqa: E402 — 원장 쓰기 잠금에만 쓴다


@contextlib.contextmanager
def _ledger_lock(ledger):
    """원장 쓰기 잠금 — `원장.lock` 에 배타 flock. ⛔ append_many 는 읽고 바꿔 끼우므로, 잠그지 않으면 그 사이 다른 프로세스의
    append 행이 사라진다(v4.40.0 validate 2차). 모든 쓰기 경로가 이 잠금을 거친다.
    ⛔ POSIX 전용(`fcntl`) — 이 원장은 macOS·Linux 에서만 쓴다. import 를 여기 두어 쓰기가 아닌 판정·수집은 다른 환경에서도 싣는다."""
    import fcntl
    os.makedirs(os.path.dirname(os.path.abspath(ledger)), exist_ok=True)
    with open(ledger + ".lock", "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def append(ledger, rec):
    line = json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"   # 잠그기 전에 직렬화한다 — 실패가 잠금 안에서 나지 않게
    with _ledger_lock(ledger), open(ledger, "a", encoding="utf-8") as fh:
        fh.write(line)


def append_many(ledger, recs):
    """여러 행을 한 번에 덧붙인다 — 기존 내용 + 새 행을 임시 파일에 쓰고 원자적으로 바꾼다(중간 실패로 일부만 남지 않게).
    ⛔ 읽기부터 바꿔 끼우기까지 `_ledger_lock` 안에서 한다 — 다른 쓰기(append)가 그 사이에 끼면 그 행을 잃는다."""
    d = os.path.dirname(os.path.abspath(ledger))
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in recs).encode("utf-8")   # 직렬화 실패는 원장을 건드리기 전에
    with _ledger_lock(ledger):
        old = b""
        if os.path.exists(ledger):
            with open(ledger, "rb") as fh:
                old = fh.read()
        if old and not old.endswith(b"\n"):
            old += b"\n"
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".ledger-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(old + body)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, ledger)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def row_origin(r):
    """run 행의 출처 — collect · recollect, origin 이 없는 옛 행은 legacy(recollect 흔적 recollected_from 이 있으면 legacy-recollect)."""
    return r.get("origin") or ("legacy-recollect" if "recollected_from" in r else "legacy")


def append_collect(ledger, rec):
    """collect 행을 덧붙인다 → 기록한 행(F-335 ⑦). 출처 origin=collect 와 같은 run_id 의 측정 순번 measure_seq 를 싣는다.
    측정 = collect 행 · 옛 collect 행(legacy). recollect 는 같은 측정을 다시 만든 것이라 세지 않는다.
    - Important: 순번은 원장 잠금 **안에서** 센다 — 밖에서 세면 동시 collect 가 같은 번호를 받는다.
    - Note: 같은 run_id 의 두 번째 collect 를 거부하지 않는다(밖의 러너가 재시도에 collect 를 다시 부를 수 있다). load() 는
      지금처럼 마지막 행을 쓰고, 재측정 여부는 `show --history` 로 본다."""
    json.dumps(rec, ensure_ascii=False, sort_keys=True)   # 직렬화 실패는 원장을 건드리기 전에
    with _ledger_lock(ledger):
        prior = iter_jsonl(ledger)[0] if os.path.exists(ledger) else []
        n = sum(1 for r in prior if r.get("type") == "run" and r.get("run_id") == rec["run_id"]
                and row_origin(r) in ("collect", "legacy"))
        rec = dict(rec, origin="collect", measure_seq=n + 1)
        line = json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"
        with open(ledger, "a", encoding="utf-8") as fh:
            fh.write(line)
    return rec


def load(ledger):
    """→ (run 행, score 행) — run_id 마다 마지막 행."""
    runs, scores = {}, {}
    evs, bad = iter_jsonl(ledger)
    if bad:
        raise ValueError(f"원장 파싱 불가 줄 {bad}")
    for r in evs:
        if r.get("type") == "run":
            runs[r["run_id"]] = r
        elif r.get("type") == "score":
            scores[r["run_id"]] = r
    return runs, scores
