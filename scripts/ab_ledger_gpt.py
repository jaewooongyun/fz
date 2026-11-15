# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
"""ab_ledger_gpt.py — A/B 원장 계측기의 한 부분: GPT 첫 패스 독립성 · 이식성 판정(gpt-pass 행).

진입점 · 설계 · 측정 규약은 ab_ledger.py 머리말에 있다(이 파일은 그 실행 코드를 나눠 담는다).
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import pathlib
import re

from ab_ledger_base import (FAIL, PASS, SCRIPT_DIR, UNRUN, instrument_sha, iter_jsonl, read_json, secs)


# ── S27 — GPT 첫 패스 독립성 · 이식성 (gpt-pass 행) ─────────────────────────────────────────
# ⛔ run 행(Claude Lead 측정)과 판정 경로를 섞지 않는다. 원천 = 런처 한 호출분 `<stem>.json` · `.audit.json` · `.rollouts/`.
#    판정 규칙 정본은 측정 노트 §17(실행 전 등록) — 여기 식이 그 문장을 코드로 옮긴 것이다.
GPT_BAD_INPUT_RE = re.compile(r"^(code-context.*|plan-v\d.*|plan-final.*|.*workflow-result.*|.*-result\.json|review-report\.md"
                              r"|pr-comments\.md|payload\.json|render-preview\.json|self-review\.md|triage\.md)$")   # 런처 사전 검사와 같은 식
GPT_MARKER_RE = re.compile(r"\[fz-gpt-skill-injected\] (fz-[a-z0-9-]+) \(([^)\n]+)\)")
GPT_CMD_STR_RE = re.compile(r"""\bcmd\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)""")
GPT_SKILL_REF_RE = re.compile(r"[~$\w{}./-]*skills/fz-[a-z0-9-]+/[\w./-]*")
GPT_WORKDIR_RE = re.compile(r"""\bworkdir\s*:\s*("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)""")
IOS_VOCAB_RE = re.compile(r"\bRIBs?\b|SwiftUI|UIKit|@StateObject|@ObservedObject|ViewController|\bInteractor\b|\bRouter\b|\bBuilder\b")
RULE_FIXTURES = {"nonios": "review-nonios", "absent": "rules-absent", "conflict": "rules-conflict"}
LABEL_TO_RULE_AXIS = {"ui_structure": "uiStack", "architecture": "architecturePattern"}   # labels.conflicts 축 → projectRules 축
SEV_RANK = {"suggestion": 0, "minor": 1, "major": 2, "critical": 3}
EVIDENCE_KINDS = ("session-log", "input-hash", "gpt-skills-only", "marker", "no-claude-artifacts", "rules-compare")


def _sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_hash(d):
    """런처(gpt_independent.sh 의 tree_hash)와 같은 폴더 해시 — 상대 경로 + 내용 · 링크는 따라가지 않고 링크 값으로.
    ⛔ 규칙을 바꾸지 않는다 — 셀 r3-s14-dir-input-rehash 가 런처 파일의 정의를 꺼내 이 함수와 대조한다."""
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(d)):
        dirs.sort()
        for f in sorted(files) + sorted(x for x in dirs if os.path.islink(os.path.join(root, x))):
            p = os.path.join(root, f)
            body = b"L" + os.readlink(p).encode() if os.path.islink(p) else hashlib.sha256(open(p, "rb").read()).digest()
            h.update(os.path.relpath(p, d).encode() + b"\0" + body)
    return h.hexdigest()


def input_hash_ok(name, path, recorded) -> bool:
    """수집 인자의 입력 원본을 다시 재 감사 기록과 같은가 — 이름이 `/` 로 끝나면 폴더(base/ · head/ · snapshot/<이름>/)다.
    폴더를 파일로 재면 정상 run 이 늘 hash_ok=False 로 거부된다(S14 2차 ISSUE-010 — F-430 --gpt-agents 측정을 막았다)."""
    if not recorded:
        return False
    if name.endswith("/"):
        return os.path.isdir(path) and _tree_hash(path) == recorded
    return os.path.isfile(path) and _sha_file(path) == recorded


def tree_hash(d):
    """폴더 안 파일 전부의 (상대 경로, 내용 해시) → 한 해시. 없는 폴더는 None."""
    if not d or not os.path.isdir(d):
        return None
    h = hashlib.sha256()
    for p in sorted(pathlib.Path(d).rglob("*")):
        if p.is_file() and p.name != ".DS_Store":
            h.update(f"{p.relative_to(d)}\0{_sha_file(p)}\n".encode())
    return h.hexdigest()


def _js_unquote(tok):
    if tok[0] == '"':
        try:
            return json.loads(tok)
        except ValueError:
            return tok[1:-1]
    return tok[1:-1].replace("\\" + tok[0], tok[0]).replace("\\\\", "\\")


def scan_gpt_rollouts(rdir):
    """런처 `<stem>.rollouts/` 의 세션 jsonl 전부 → 주입 마커 · 주입 본문 · 실행 명령 · host 스킬 목록 · 스킬 루트.
    ⛔ session_meta 의 계정 식별자(creator_*)는 읽지도 싣지도 않는다 — 판정에 쓰지 않고 원장에 남기면 안 되는 값이다."""
    files = sorted(pathlib.Path(rdir).rglob("*.jsonl")) if rdir and os.path.isdir(rdir) else []
    out = {"files": [str(f) for f in files], "markers": [], "bodies": {}, "cmds": [], "workdirs": [], "host_skills": [],
           "skill_roots": [], "spawn": 0, "turn_contexts": 0, "calls": 0}
    # 형식 위반 — 못 읽은 줄 · 형이 틀린 칸을 버리거나 기본값으로 메우지 않는다. 규칙은 실제 rollout(71파일 · 11,109줄)에서 위반 0 인 것만
    fmt = collections.Counter()
    bodies = 0
    for f in files:
        metas = 0
        with open(f, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                if not ln.strip():
                    continue
                try:
                    r = json.loads(ln)
                except ValueError:
                    r = None
                if not isinstance(r, dict) or not isinstance(r.get("type"), str) or not isinstance(r.get("payload"), dict):
                    fmt["line"] += 1
                    continue
                typ, p = r["type"], r["payload"]
                metas += typ == "session_meta"
                if typ == "response_item" and not isinstance(p.get("type"), str):
                    fmt["response_item.type"] += 1
                if typ == "response_item" and p.get("type") == "message" and not (
                        isinstance(p.get("role"), str) and isinstance(p.get("content"), list)):
                    fmt["message"] += 1
                if typ == "response_item" and p.get("type") == "custom_tool_call" and not isinstance(p.get("input"), str):
                    fmt["custom_tool_call.input"] += 1
                # 다른 호출 꼴도 판정에 쓰는 칸이 있어야 한다 — 인자를 잃은 호출을 명령 0 건으로 읽지 않는다(S14 r4 ISSUE-006 · 실측 978 위반 0)
                if typ == "response_item" and p.get("type") == "function_call" and not (
                        isinstance(p.get("name"), str) and isinstance(p.get("arguments"), str)):
                    fmt["function_call.arguments"] += 1
                if typ == "response_item" and p.get("type") == "local_shell_call" and not isinstance(p.get("action"), dict):
                    fmt["local_shell_call.action"] += 1
                if typ == "world_state" and isinstance(p.get("state"), dict) and isinstance(p["state"].get("host_skills"), dict) \
                        and isinstance(p["state"]["host_skills"].get("body"), str):
                    bodies += 1
                if typ == "turn_context":
                    out["turn_contexts"] += 1
                elif typ == "world_state":
                    body = ((((p.get("state") or {}) if isinstance(p.get("state"), dict) else {}).get("host_skills") or {})
                            .get("body") or "")
                    out["host_skills"] += re.findall(r"^- ([A-Za-z0-9_.:-]+):", body, re.M)
                    out["skill_roots"] += re.findall(r"^- `r\d+` = `([^`]+)`", body, re.M)
                elif typ == "response_item" and p.get("type") == "message":
                    for c in p.get("content") or []:
                        t = c.get("text") if isinstance(c, dict) else None
                        if t and "[fz-gpt-skill-injected]" in t:
                            m = GPT_MARKER_RE.search(t)
                            if m:
                                out["markers"].append({"skill": m.group(1), "path": m.group(2), "role": p.get("role")})
                                rest = t[t.index("[fz-gpt-skill-injected]"):].split("\n", 1)
                                out["bodies"].setdefault(m.group(1), rest[1] if len(rest) > 1 else "")
                elif typ == "response_item" and p.get("type") in ("custom_tool_call", "function_call", "local_shell_call"):
                    out["calls"] += 1
                    if p.get("name") == "spawn_agent":
                        out["spawn"] += 1
                    raw = p.get("input") if p.get("input") is not None else (p.get("arguments") or p.get("action") or "")
                    raw = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
                    got, wds = [], []
                    ms = list(GPT_CMD_STR_RE.finditer(raw))
                    for i, mm in enumerate(ms):
                        got.append(_js_unquote(mm.group(1)))
                        # 같은 exec_command 객체의 workdir — 명령 뒤(다음 cmd 전)를 먼저, 없으면 앞(이전 cmd 뒤)을 본다
                        hi = ms[i + 1].start() if i + 1 < len(ms) else len(raw)
                        lo = ms[i - 1].end() if i else 0
                        w = GPT_WORKDIR_RE.search(raw, mm.end(), hi) or GPT_WORKDIR_RE.search(raw, lo, mm.start())
                        wds.append(_js_unquote(w.group(1)) if w else None)
                    if not got:
                        try:
                            j = json.loads(raw)
                        except ValueError:
                            j = None
                        c = (j.get("cmd") or j.get("command")) if isinstance(j, dict) else None
                        got = [" ".join(map(str, c)) if isinstance(c, list) else str(c)] if c else []
                        wds = [j.get("workdir") if isinstance(j, dict) else None] * len(got)
                    out["cmds"] += got
                    out["workdirs"] += wds
        if not metas:
            fmt["session_meta"] += 1     # 파일마다 하나(실측 71/71)
    if files and not bodies:
        fmt["world_state.host_skills"] += 1   # host 스킬 목록을 든 world_state 가 없다(실측 71/71 파일에 있다)
    out["host_skills"] = sorted(set(out["host_skills"]))
    out["skill_roots"] = sorted(set(out["skill_roots"]))
    out["format_problems"] = dict(fmt)
    return out


# 런처 감사(gpt_independent.sh) 칸 — 실측 현재 형식 감사 71/71 에 모두 있고 형이 같다. 계수 셋은 rollout 을 다시 센 값과 같다(71/71)
AUDIT_FIELDS = {"mode": str, "exit": int, "note": str, "timedOut": bool, "isolationApplied": bool, "spawnAgent": int, "hits": list,
                "inputs": dict, "toolCalls": int, "rollouts": int, "turnContexts": int, "wrapperExit": int}
# 첫 패스 출력 항목에서 판정이 읽는 칸(스키마 required 의 부분집합 · schemas/gpt_independent_review_schema.json)
OUTPUT_ITEM_KEYS = {"issues": ("id", "severity", "ruleSource"), "craft": ("id", "severity", "ruleSource", "craftAxis", "ruleRef"),
                    "axis_coverage": ("axis", "status")}


def gpt_source_problems(audit, doc, scan) -> dict:
    """감사 · 첫 패스 출력 · rollout 판독의 형식 위반과 감사 계수 ↔ 재계수 불일치 → {이름: 수}. 빈 dict 면 형식대로다."""
    p = collections.Counter(scan.get("format_problems") or {})
    if not isinstance(audit, dict):
        return dict(p, audit=1)
    for k, t in AUDIT_FIELDS.items():
        v = audit.get(k)
        if not isinstance(v, t) or (t is int and isinstance(v, bool)):
            p["audit." + k] += 1
    for k, got in (("rollouts", len(scan["files"])), ("turnContexts", scan["turn_contexts"]), ("toolCalls", scan["calls"]),
                   ("spawnAgent", scan["spawn"])):   # S14 r4 ISSUE-008 · 실측 감사 65 일치
        if isinstance(audit.get(k), int) and audit[k] != got:
            p["audit." + k + "≠rollout"] += 1   # rollout 줄이 빠졌거나 다른 run 의 사본이다
    if doc is not None:
        pr = doc.get("projectRules") if isinstance(doc, dict) else None
        if not isinstance(doc, dict) or not isinstance(doc.get("verdict", doc.get("status")), str) or not (
                isinstance(pr, dict) and all(isinstance(pr.get(k), list) for k in ("rules", "conflicts", "gaps"))) or any(
                doc.get(k) is not None and not isinstance(doc.get(k), list) for k in ("issues", "craft", "axis_coverage")):
            p["output"] += 1
        # 판정이 읽는 항목 칸 — 스키마 required 중 summarize_gpt_output 이 쓰는 것. 빠진 칸을 '규칙 근거 없음' 으로 읽지 않는다(S14 r4 ISSUE-007 · 실측 417항목 위반 0)
        for kind, req in OUTPUT_ITEM_KEYS.items():
            items = doc.get(kind) if isinstance(doc, dict) else None
            n = sum(1 for x in items or [] if not (isinstance(x, dict) and all(k in x for k in req)))
            if n:
                p["output." + kind] += n
    return dict(p)


def classify_skill_refs(scan, tree_root):
    """명령이 가리킨 스킬 파일 경로 · host 스킬 목록 → 격리 홈 밖 참조 · Claude 스킬 노출."""
    iso_roots = sorted({m["path"].split("/gpt-home/skills/")[0] + "/gpt-home/skills"
                        for m in scan["markers"] if "/gpt-home/skills/" in m["path"]})
    names = lambda sub: sorted(n for n in os.listdir(os.path.join(tree_root, sub))
                               if os.path.isdir(os.path.join(tree_root, sub, n))) if os.path.isdir(os.path.join(tree_root, sub)) else []
    claude_names, gpt_names = set(names("skills")), set(names("gpt-skills"))
    refs = set()
    for c, wd in zip(scan["cmds"], scan.get("workdirs") or [None] * len(scan["cmds"])):
        for m in GPT_SKILL_REF_RE.finditer(c):
            r = m.group(0)
            if wd and not r.startswith(("/", "~", "$")):
                r = os.path.normpath(os.path.join(wd, r))   # ⛔ 상대 참조는 그 명령의 workdir 기준 — 격리 폴더면 사본 읽기다
            refs.add(r)
    refs = sorted(refs)
    bad = []
    for r in refs:
        if any(r.startswith(x + "/") for x in iso_roots) or re.match(r"\$\{?CODEX_HOME\}?/skills/", r):
            continue       # 격리 홈 사본 — 런처 안에서 CODEX_HOME 은 격리 홈이다
        if re.search(r"(^|/)\.codex/skills/", r) or r.startswith(("~/", "$HOME/", "${HOME}/")):
            bad.append(f"실제 GPT 홈 경로 {r}")
        elif "/gpt-home/skills/" in r:
            bad.append(f"다른 격리 홈 {r}")
        elif re.search(r"(^|/)skills/fz-[a-z0-9-]+/", r) and not re.search(r"(^|/)gpt-skills/", r):
            bad.append(f"Claude 스킬 폴더 {r}")
    claude_listed = sorted(n for n in scan["host_skills"] if n in claude_names and n not in gpt_names)
    return {"iso_roots": iso_roots, "refs": refs, "bad": bad, "claude_listed": claude_listed}


def _body_matches(tree_root, skill, body):
    try:
        with open(os.path.join(tree_root, "gpt-skills", skill, "SKILL.md"), encoding="utf-8") as fh:
            return fh.read().strip() in body
    except OSError:
        return False


def summarize_gpt_output(doc, mode):
    """첫 패스 출력(스키마 JSON) → 판정에 쓰는 필드만."""
    doc = doc if isinstance(doc, dict) else {}
    pr = doc.get("projectRules") or {}
    rules = [{"id": x.get("id"), "axis": x.get("axis"), "file": (x.get("source") or {}).get("file"),
              "line": (x.get("source") or {}).get("line")}
             for x in pr.get("rules") or [] if isinstance(x, dict)]
    conflicts = [{"axis": x.get("axis"), "sources": x.get("sources")} for x in pr.get("conflicts") or [] if isinstance(x, dict)]
    items = []
    for kind in ("issues", "craft"):
        for x in doc.get(kind) or []:
            if isinstance(x, dict):
                items.append({"kind": kind, "id": x.get("id"), "ruleSource": x.get("ruleSource"), "ruleRef": x.get("ruleRef"),
                              "severity": x.get("severity"), "craftAxis": x.get("craftAxis"), "file": x.get("file"),
                              "text": f"{x.get('title') or ''} {x.get('detail') or ''}"[:600]})
    cov = {x.get("axis"): x.get("status") for x in doc.get("axis_coverage") or [] if isinstance(x, dict)}
    return {"mode": mode, "status": doc.get("status") or doc.get("verdict"), "rules": rules, "conflicts": conflicts,
            "gaps": list(pr.get("gaps") or []), "items": items, "axis_coverage": cov}


def rules_compare(summ, lead):
    """GPT 추출(projectRules) vs Lead 추출(규칙 레코드 · check_project_rules 통과본) — 기록용(합격 조건 아님)."""
    key = lambda axis, f: [str(axis), str(f)]
    g = {tuple(key(r.get("axis"), r.get("file"))) for r in summ.get("rules") or []}
    lr = [r for r in (lead or {}).get("rules") or [] if isinstance(r, dict)]
    l_ = {tuple(key(r.get("axis"), (r.get("source") or {}).get("file"))) for r in lr}
    return {"both": len(g & l_), "gpt_only": sorted(list(x) for x in g - l_), "lead_only": sorted(list(x) for x in l_ - g),
            "conflict_axes": {"gpt": sorted({str(c.get("axis")) for c in summ.get("conflicts") or []}),
                              "lead": sorted({str(c.get("axis")) for c in (lead or {}).get("conflicts") or [] if isinstance(c, dict)})}}


def build_gpt_row(args, tree_root=None):
    """collect-gpt 인자(dict) → gpt-pass 행. verify-evidence 가 같은 인자로 다시 부른다(두 번째 자)."""
    tree = tree_root or os.path.dirname(SCRIPT_DIR)
    out = args["out"]
    stem = out[:-len(".json")] if out.endswith(".json") else out
    audit = read_json(stem + ".audit.json")
    doc = read_json(out) if os.path.isfile(out) else None
    scan = scan_gpt_rollouts(stem + ".rollouts")
    problems = gpt_source_problems(audit, doc, scan)
    if not isinstance(audit, dict):
        raise ValueError("감사 파일이 객체가 아니다")
    cls = classify_skill_refs(scan, tree)
    inputs = audit.get("inputs") if isinstance(audit.get("inputs"), dict) else {}
    given = dict(args.get("inputs") or {})
    hash_ok = {n: input_hash_ok(n, p, inputs.get(n)) for n, p in given.items()}
    plugin_root = os.path.realpath(args["plugin_root"])
    summ = summarize_gpt_output(doc, args["mode"]) if doc is not None else None
    lead = read_json(args["lead_rules"]) if args.get("lead_rules") else None
    return {"type": "gpt-pass", "schema": 1, "run_id": args["run_id"], "env": args["env"], "mode": args["mode"],
            "fixture": args["fixture"], "plugin_root": plugin_root, "instrument_sha": instrument_sha(),
            "skills": {"tree_hash": tree_hash(os.path.join(tree, "gpt-skills")),
                       "plugin_hash": tree_hash(os.path.join(plugin_root, "gpt-skills")),
                       "body_matches_tree": {sk: _body_matches(tree, sk, b) for sk, b in scan["bodies"].items()}},
            "audit": dict({k: audit.get(k) for k in ("mode", "exit", "note", "timedOut", "isolationApplied", "spawnAgent",
                                                       "toolCalls", "rollouts", "turnContexts", "wrapperExit")},
                          hits=len(audit.get("hits") or [])),
            "inputs": {"names": sorted(inputs), "claude_named": sorted(n for n in inputs if GPT_BAD_INPUT_RE.match(n)),
                       "given": sorted(given), "hash_ok": hash_ok},
            "scan": {"rollout_files": len(scan["files"]), "markers": scan["markers"], "host_skills": scan["host_skills"],
                     "skill_roots": scan["skill_roots"], "refs": cls["refs"], "bad_refs": cls["bad"],
                     "claude_listed": cls["claude_listed"], "spawn": scan["spawn"], "cmd_count": len(scan["cmds"]),
                     "turn_contexts": scan["turn_contexts"]},
            "agents": agents_record(args, scan, audit),
            "format_problems": problems,
            "output": summ,
            "rules_compare": rules_compare(summ, lead) if (summ is not None and lead is not None) else None,
            "collect_args": dict(args)}


def agents_record(args, scan, audit):
    """다렌즈 처치(--gpt-agents)의 요청과 실제 spawn 을 따로 남긴다(F-356) — 요청했는데 spawn 0 이면 처치가 일어나지 않은 행이다."""
    return {"requested": bool(args.get("gpt_agents")), "spawned": int(scan.get("spawn") or 0)}   # 재계수만 — 감사 값으로 메우지 않는다(S14 r4 ISSUE-008)


def gpt_audit_problems(g):
    """감사 · 격리 · 입력(이름 집합 · 재해시) — 매트릭스 셀(SC-1)과 규칙 fixture 행(SC-2)이 함께 쓴다(F-356 SFH-4).
    ⛔ 빈 hash_ok 는 통과가 아니다 — 입력을 재해시하지 않은 행이다(all({}.values()) 는 참이다)."""
    au, ip = g.get("audit") or {}, g.get("inputs") or {}
    p = []
    if g.get("format_problems"):
        p.append(("SC-1", f"원천 형식 위반 {g['format_problems']} — 빠지거나 형이 틀린 칸 · 감사 계수 ≠ rollout 재계수"))
    if au.get("mode") != g.get("mode"):
        # ⛔ 감사가 기록한 실제 mode 와 수집 --mode 가 다르면 그 셀의 첫 패스가 아니다(S14 r3 ISSUE-005)
        p.append(("SC-1", f"감사 mode {au.get('mode')} ≠ 수집 mode {g.get('mode')}"))
    if au.get("exit") != 0:
        p.append(("SC-1", f"감사 exit {au.get('exit')} ({au.get('note')})"))
    if au.get("timedOut"):
        p.append(("SC-1", "시간 초과"))
    if not au.get("isolationApplied"):
        p.append(("SC-1", "격리 미적용"))
    if ip.get("claude_named"):
        p.append(("AC-2", f"Claude 산출물 이름 입력 {ip['claude_named']}"))
    if sorted(ip.get("names") or []) != sorted(ip.get("given") or []):
        p.append(("SC-1", f"입력 이름 집합 불일치 — 감사 {sorted(ip.get('names') or [])} · 수집 {sorted(ip.get('given') or [])}"))
    hok = ip.get("hash_ok")
    if not isinstance(hok, dict) or not hok:
        p.append(("SC-1", "입력 재해시 기록 없음(hash_ok 빈 칸)"))
    else:
        bad_hash = sorted(n for n, ok in hok.items() if not ok)
        if bad_hash:
            p.append(("SC-1", f"입력 해시 불일치 {bad_hash}"))
    return p


def gpt_sc1_problems(g):
    """SC-1 · AC-2 셀 조건(노트 §17 ①~⑤) — 행 하나의 위반 목록. (종류, 문장) — 종류 AC-2 는 Claude 쪽 유입."""
    au, sc, sk = g.get("audit") or {}, g.get("scan") or {}, g.get("skills") or {}
    p = gpt_audit_problems(g)
    if au.get("hits"):
        p.append(("AC-2", f"rollout 금지 참조 {au['hits']}건(Claude 산출물)"))
    if (sc.get("spawn") or au.get("spawnAgent") or 0) and not (g.get("collect_args") or {}).get("gpt_agents"):
        p.append(("SC-1", f"하위 에이전트 spawn {sc.get('spawn') or au.get('spawnAgent')}"))
    if not sc.get("rollout_files"):
        p.append(("SC-1", "rollout 없음"))
    mk = sc.get("markers") or []
    if not mk:
        p.append(("SC-1", "주입 마커 없음"))
    elif not all("/gpt-home/skills/" in m["path"] for m in mk):
        p.append(("SC-1", "마커 경로가 격리 홈 밖"))
    for b in sc.get("bad_refs") or []:
        p.append(("AC-2" if b.startswith("Claude") else "SC-1", f"격리 홈 밖 스킬 참조 — {b}"))
    if sc.get("claude_listed"):
        p.append(("AC-2", f"Claude 스킬이 GPT 스킬 목록에 {sc['claude_listed']}"))
    bm = sk.get("body_matches_tree") or {}
    if not bm or not all(bm.values()):
        p.append(("SC-1", f"주입 본문 ≠ 검증 트리 gpt-skills {bm}"))
    if not sk.get("tree_hash") or sk.get("plugin_hash") != sk.get("tree_hash"):
        p.append(("SC-1", "런처 PLUGIN_ROOT 의 gpt-skills ≠ 검증 트리"))
    return p


def _rule_src(ref, rules):
    """ruleRef → (파일, 줄 | None, 절 이름 | None) · 풀 수 없으면 None.
    ⛔ GPT 는 ruleRef 에 자기 projectRules id(R1 …)를 적는다(S27 실측) — id 면 그 규칙의 출처로 푼다. 아니면 `파일:줄` · `파일#절`."""
    if not ref or not isinstance(ref, str):
        return None
    for r in rules or []:
        if r.get("id") and ref.strip() == str(r["id"]):
            return (r.get("file"), r.get("line"), None)
    m = re.match(r"\s*([^\s:#]+\.[A-Za-z]+)\s*(?:[:#]\s*L?(\d+)\b|#\s*(.+))?", ref)
    if not m:
        return None
    return (m.group(1), int(m.group(2)) if m.group(2) else None, (m.group(3) or "").strip() or None)


def _src_in_section(src, sec, sections):
    """풀린 출처가 상충 절(`CLAUDE.md#Naming`) 안인가 — 절 이름 또는 색인 절의 줄 범위."""
    if not src or "#" not in sec:
        return False
    f, head = sec.split("#", 1)
    if src[0] != f and not (src[0] or "").endswith("/" + f):
        return False
    if src[2] and src[2].lower().startswith(head.lower()):
        return True
    n = src[1]
    return bool(n) and any(s.get("file") == f and (s.get("heading") or "").lower().startswith(head.lower())
                           and (s.get("line") or 0) <= n <= (s.get("endLine") or s.get("line") or 0) for s in sections)


def _index_sections(index):
    return [s for s in (index or {}).get("sections") or [] if isinstance(s, dict)]


def gpt_sc2_problems(g, labels, index):
    """SC-2 · AC-3(노트 §17 규칙 fixture 절) → (위반 [(종류, 문장)], Probe Coverage Gap 문장)."""
    o = g.get("output") or {}
    items = o.get("items") or []
    fx = g.get("fixture")
    probs, gaps = [], []
    ids = lambda xs: [x.get("id") for x in xs]
    proj = [x for x in items if x.get("ruleSource") == "project"]
    pdef = [x for x in items if x.get("ruleSource") == "plugin-default"
            and SEV_RANK.get(x.get("severity"), 9) > SEV_RANK["suggestion"]]
    if pdef:
        probs.append(("AC-3", f"plugin-default 인데 severity > suggestion {ids(pdef)}"))
    if fx == "rules-absent":
        if o.get("rules"):
            probs.append(("SC-2", f"지침 파일이 없는데 projectRules.rules {len(o['rules'])}건"))
        if o.get("conflicts"):
            probs.append(("SC-2", f"지침 파일이 없는데 conflicts {len(o['conflicts'])}건"))
        if proj:
            probs.append(("SC-2", f"없는 규칙의 추정 적용(ruleSource=project) {ids(proj)}"))
    elif fx == "rules-conflict":
        want = {LABEL_TO_RULE_AXIS.get(c.get("axis"), c.get("axis")) for c in labels.get("conflicts") or []}
        got = {c.get("axis") for c in o.get("conflicts") or []}
        if want - got:
            probs.append(("SC-2", f"상충 축 미표시 {sorted(want - got)}(표시 {sorted(got)})"))
        secs = [s for c in labels.get("conflicts") or [] for s in c.get("sources") or []]
        picks = [x for x in proj if any(_src_in_section(_rule_src(x.get("ruleRef"), o.get("rules")), s, _index_sections(index))
                                        for s in secs)]
        if picks:
            probs.append(("SC-2", f"상충 규칙 임의 선택(ruleRef 가 상충 절) {ids(picks)}"))
        targets = {c.get("target") for c in labels.get("conflicts") or []}
        vague = [x for x in proj if x.get("file") in targets and not x.get("ruleRef")]
        if vague:
            gaps.append(f"상충 대상 파일에 ruleRef 없는 project 인용 {ids(vague)}(어느 절인지 판정 불가)")
    elif fx == "review-nonios":
        files = list(labels.get("guidelines") or [])
        craft_proj = [x for x in proj if x.get("kind") == "craft"]
        srcs = {x.get("id"): _rule_src(x.get("ruleRef"), o.get("rules")) for x in craft_proj}
        unknown = [x for x in craft_proj if x.get("ruleRef") and srcs[x.get("id")] is None]
        outside = [x for x in craft_proj if srcs[x.get("id")] is not None and srcs[x.get("id")][0] not in files]
        if unknown:
            probs.append(("SC-2", f"풀 수 없는 규칙 인용(projectRules 에 없는 id · 형식 밖) {ids(unknown)}"))
        if outside:
            probs.append(("SC-2", f"지침({files}) 밖 규칙 인용 {ids(outside)}"))
        noref = [x for x in craft_proj if not x.get("ruleRef")]
        if noref:
            gaps.append(f"craft ruleSource=project 인데 ruleRef 없음 {ids(noref)}(출처 판정 불가)")
        na = set(labels.get("not_applicable_axes") or [])
        na_items = [x for x in items if x.get("craftAxis") in na]
        if na_items:
            probs.append(("AC-3", f"해당 없음 축 craft {sorted(na)} {ids(na_items)}"))
        found = sorted(a for a in na if (o.get("axis_coverage") or {}).get(a) == "found")
        if found:
            probs.append(("AC-3", f"axis_coverage 해당 없음 축이 found {found}"))
        ios = [x for x in items if IOS_VOCAB_RE.search(x.get("text") or "")]
        if ios:
            probs.append(("AC-3", f"비-iOS 저장소에 iOS 도메인 어휘 {ids(ios)}"))
    issue_proj = [x for x in proj if x.get("kind") == "issues"]
    if issue_proj and fx != "rules-absent":
        gaps.append(f"issues 의 ruleSource=project {ids(issue_proj)} — 스키마에 ruleRef 가 없어 출처 판정 불가")
    return probs, gaps


def load_gpt(ledger):
    """→ gpt-pass 행 {run_id: 마지막 행}."""
    evs, bad = iter_jsonl(ledger)
    if bad:
        raise ValueError(f"원장 파싱 불가 줄 {bad}")
    return {r["run_id"]: r for r in evs if r.get("type") == "gpt-pass"}


def _fixture_docs(fixtures_root, fx):
    """규칙 fixture 오라클(labels.json · expected-index.json) → (labels, index, 읽지 못한 사유 | None).
    ⛔ 없거나 읽지 못한 오라클을 빈 dict 로 두지 않는다 — 기대가 비면 위반을 못 찾아 PASS 가 된다(미판정이어야 한다)."""
    d, docs = os.path.join(fixtures_root or "", fx), []
    for name in ("labels.json", "expected-index.json"):
        try:
            v = read_json(os.path.join(d, name))
        except (OSError, ValueError) as e:
            return None, None, f"{name} 를 읽지 못했다 ({type(e).__name__})"
        if not isinstance(v, dict) or not v:
            return None, None, f"{name} 가 비었거나 객체가 아니다"
        docs.append(v)
    return docs[0], docs[1], None


def judge_gpt(gpts, req, envs, fixtures_root):
    """SC-1 · AC-2(매트릭스 셀) · SC-2 · AC-3(규칙 fixture) → (exit, 줄)."""
    out, worst = [], PASS

    def bump(rc):
        nonlocal worst
        worst = max(worst, rc)
    rows = sorted(gpts.values(), key=lambda g: g["run_id"])
    # ⛔ 다른 계측기(또는 지문 없이)로 모은 행은 이 계측기로 판정하지 않는다 — 빼고 센다. 칸이 비면 아래 '행 없음' UNRUN(S14 2차 ISSUE-007)
    cur = instrument_sha()
    stale = sorted(g["run_id"] for g in rows if g.get("instrument_sha") != cur)
    if stale:
        out.append(f"  제외 {len(stale)}: 계측기 지문이 현재({cur})와 다르거나 없다 {stale[:5]} — 다시 collect-gpt")
        rows = [g for g in rows if g.get("instrument_sha") == cur]
    rule_fx = set(RULE_FIXTURES.values())
    if {"SC-1", "AC-2"} & set(req):
        if not envs:
            return UNRUN, ["UNRUN: SC-1 · AC-2 는 --envs(예: isolated,installed)가 필요하다 — 매트릭스를 정하지 않으면 한 환경만 보고 통과한다"]
        ac2, ac2_unjudged = [], []
        for env in envs:
            for mode in ("plan", "review"):
                cell = [g for g in rows if g.get("env") == env and g.get("mode") == mode and g.get("fixture") not in rule_fx]
                label = f"{env}×{mode}"
                if not cell:
                    out.append(f"UNRUN SC-1 [{label}]: gpt-pass 행 없음 — collect-gpt 로 첫 패스 산출을 싣는다")
                    bump(UNRUN)
                    ac2_unjudged.append(label)
                    continue
                no_out = sorted(g["run_id"] for g in cell if g.get("output") is None)
                if no_out:
                    # ⛔ 첫 패스 출력이 없는 행을 통과시키지 않는다 — 규칙 fixture 행과 같은 규칙(출력 없음 = 미판정)
                    out.append(f"UNRUN SC-1 [{label}]: 출력 없음(스키마 JSON 을 읽지 못했다) {no_out}")
                    bump(UNRUN)
                    ac2_unjudged.append(label)
                    continue
                probs = {g["run_id"]: gpt_sc1_problems(g) for g in cell}
                ac2 += [f"{k}: {t}" for k, ps in probs.items() for c, t in ps if c == "AC-2"]
                # 감사 · 격리 · 입력 이름 집합 · 재해시가 틀린 행은 AC-2 도 판정할 수 없다 — SC-1 을 안 물어도 막는다
                ac2 += [f"{g['run_id']}: 감사 — {t}" for g in cell for c, t in gpt_audit_problems(g) if c == "SC-1"]
                bad = {k: [t for c, t in ps if c == "SC-1"] for k, ps in probs.items()}
                bad = {k: v for k, v in bad.items() if v}
                if "SC-1" in req:
                    good = not bad and not any(c == "AC-2" for ps in probs.values() for c, _ in ps)
                    bump(PASS if good else FAIL)
                    out.append(f"{'PASS' if good else 'FAIL'} SC-1 [{label}]: " + (" | ".join(
                        f"{k} — {'; '.join(v)}" for k, v in bad.items()) if bad else
                        f"{len(cell)} 행 · 감사 exit 0 · 격리 · hits 0 · 마커 · 격리 홈 사본 · 주입 본문 = 트리 gpt-skills — "
                        + ", ".join(sorted(probs))))
        if "AC-2" in req:
            if ac2:
                bump(FAIL)
                out.append("FAIL AC-2: " + " | ".join(ac2))
            elif ac2_unjudged:
                bump(UNRUN)
                out.append(f"UNRUN AC-2: 판정하지 못한 셀 {ac2_unjudged} — 빈 셀은 'Claude 유입 0' 의 증거가 아니다")
            else:
                bump(PASS)
                out.append("PASS AC-2: Claude 스킬 노출 · 참조 0 · Claude 산출물 입력 · 참조 0")
    if {"SC-2", "AC-3"} & set(req):
        for short, fx in RULE_FIXTURES.items():
            cell = [g for g in rows if g.get("fixture") == fx and g.get("mode") == "review"]
            if not cell:
                out.append(f"UNRUN SC-2 [{fx}]: gpt-pass 행 없음 — 규칙 fixture 의 review 첫 패스를 싣는다")
                bump(UNRUN)
                continue
            lab, idx, why = _fixture_docs(fixtures_root, fx)
            if why:
                out.append(f"UNRUN SC-2 [{fx}]: fixture 오라클 없음 — {why}")
                bump(UNRUN)
                continue
            for g in cell:
                if g.get("output") is None:
                    out.append(f"UNRUN SC-2 [{fx}] {g['run_id']}: 출력 없음(스키마 JSON 을 읽지 못했다)")
                    bump(UNRUN)
                    continue
                probs, gaps = gpt_sc2_problems(g, lab, idx)
                aud = [f"감사 — {t}" for _, t in gpt_audit_problems(g)]   # F-356 — 규칙 fixture 행도 감사 · 격리 · 입력을 본다
                for crit in ("SC-2", "AC-3"):
                    if crit not in req:
                        continue
                    mine = aud + [t for c, t in probs if c == crit]
                    bump(FAIL if mine else PASS)
                    out.append(f"{'FAIL' if mine else 'PASS'} {crit} [{fx}] {g['run_id']}: "
                               + ("; ".join(mine) if mine else "위반 0"))
                for x in gaps:
                    out.append(f"  Probe Coverage Gap [{fx}] {g['run_id']}: {x}")
                rc_ = g.get("rules_compare")
                if rc_ is not None:
                    out.append(f"  rules-compare [{fx}] {g['run_id']}: 일치 {rc_['both']} · GPT 만 {len(rc_['gpt_only'])} · "
                               f"Lead 만 {len(rc_['lead_only'])} · 상충 축 GPT {rc_['conflict_axes']['gpt']} / Lead {rc_['conflict_axes']['lead']}")
    return worst, out


def verify_gpt_row(g, kinds, tree_root=None):
    """두 번째 자 — 행의 원천(감사 · rollout · 입력 · 출력)을 다시 읽어 행과 대조한다. → 어긋남 목록."""
    try:
        fresh = build_gpt_row(g.get("collect_args") or {}, tree_root)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return [f"원천을 다시 읽지 못했다 — {e}"]
    bad = []
    same = lambda k: json.dumps(fresh.get(k), sort_keys=True, ensure_ascii=False) == json.dumps(g.get(k), sort_keys=True, ensure_ascii=False)
    if "session-log" in kinds:
        if not (fresh["scan"]["rollout_files"] and same("scan")):
            bad.append("session-log: rollout 이 없거나 재스캔 결과가 행과 다르다")
    if "input-hash" in kinds:
        if not fresh["inputs"]["hash_ok"] or not all(fresh["inputs"]["hash_ok"].values()) or not same("inputs"):
            bad.append(f"input-hash: 입력 재해시 불일치 {fresh['inputs']['hash_ok']}")
    if "gpt-skills-only" in kinds:
        sk = fresh["skills"]
        if (fresh["scan"]["bad_refs"] or fresh["scan"]["claude_listed"] or not sk["body_matches_tree"]
                or not all(sk["body_matches_tree"].values()) or sk["plugin_hash"] != sk["tree_hash"] or not same("skills")):
            bad.append("gpt-skills-only: 격리 홈 밖 참조 · Claude 스킬 노출 · 주입 본문 · 스킬 해시 중 어긋남")
    if "marker" in kinds:
        mk = fresh["scan"]["markers"]
        if not mk or not all("/gpt-home/skills/" in m["path"] for m in mk):
            bad.append("marker: 주입 마커가 없거나 격리 홈 밖")
    if "no-claude-artifacts" in kinds:
        if fresh["audit"]["hits"] or fresh["inputs"]["claude_named"] or not same("audit"):
            bad.append(f"no-claude-artifacts: 감사 hits {fresh['audit']['hits']} · 이름 {fresh['inputs']['claude_named']}")
    if "rules-compare" in kinds and g.get("fixture") in RULE_FIXTURES.values():
        if fresh.get("rules_compare") is None or not same("rules_compare"):
            bad.append("rules-compare: 비교 기록이 없거나 원천과 다르다")
    return bad
