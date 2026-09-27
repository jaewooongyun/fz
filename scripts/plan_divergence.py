#!/usr/bin/env python3
# lint:no-root-anchor — 비교할 두 플랜 JSON 을 인자로 받는다(플러그인 루트의 파일을 읽지 않는다).
# diff-parse: not-a-diff — startswith("-") 는 파일 칸에 섞인 `--flag` 같은 값을 버리는 검사다(diff 줄 접두가 아니다).
"""Claude ↔ GPT 독립 플랜 차이표 (S21) — 두 플랜을 나란히 놓고 한쪽에만 있는 것을 표로 만든다.

판정은 하지 않는다 — 어느 쪽이 옳은지는 Lead 가 정한다. 스크립트가 하는 일은 기계 대조뿐이다.

  파일       변경 대상 가운데 한쪽에만 있는 것. Claude = steps[].files ∪ writeScope[].file · GPT = steps[].file ∪ steps[].files.
             경로의 접두(./ · 격리 dir 의 head/)와 뒤의 설명(공백 뒤 · 괄호 · :줄)을 벗기고 `{a,b}` 를 펼친다. 한쪽이 다른 쪽의
             경로 꼬리면 같은 파일이고, 디렉터리 항목(`dir/`)은 그 아래 파일을 덮는다. 경로 모양이 아닌 값(`--flag` · 버전)은 버린다
  요구(RTM)  Claude RTM 의 요구마다 그 Step 의 파일을 GPT 플랜이 하나라도 건드리는가 — 하나도 없으면 미커버다.
             Step 이 없거나 Step 에 파일이 없으면 판정 불가로 적는다(⛔ 미커버 0 으로 세지 않는다).
             Claude 플랜 안의 RTM ↔ Step 참조 무결성은 plan_integrity_check.py 가 본다
  위험       riskMatrix[].risk 를 글자 bigram 겹침(Jaccard)으로 짝짓는다 — 임계 미만은 짝 없는 한쪽 위험이다

입력
  --claude FILE  plan-lean2 반환(workflow-result.json — plan 을 읽는다) 또는 plan 객체
  --gpt FILE     GPT 독립 플랜 JSON — steps[{file | files, action?, why?}] · riskMatrix[{risk}]
                 (gpt-skills/fz-planner 출력 형식의 Steps · Risk Matrix 두 절을 옮긴 모양이다)
                 ⛔ contaminated: true 이거나 contamination 사유가 있으면 거부한다 — 독립 첫 패스가 아니다(AC-2)
                 ⛔ planner 마크다운은 받지 않는다 — 오염 표시를 실을 곳이 없다
  --out FILE     차이표 마크다운(없으면 stdout) · --json FILE 행 단위 JSON
  --self-test

exit: 0=차이표 · 1=거부(오염 표시) · 2=입력 불가(⛔ 통과 아님 — 한쪽 입력 없음 · JSON 객체 아님 · steps 나 파일 없음)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

OK, REJECT, UNRUN = 0, 1, 2
# ponytail: 글자 bigram Jaccard 한 값 — 표현이 많이 다른 같은 위험은 양쪽에 한쪽 위험으로 뜬다(숨기지 않는 쪽으로 틀린다).
#   짝지은 쌍과 유사도를 표에 함께 적어 Lead 가 근거를 본다. 오짝이 보이면 임계를 올린다
RISK_MATCH = 0.45
STEP_SPLIT = re.compile(r"[,·/]| and ")    # plan_integrity_check.py 와 같은 stepId 표기


class InputError(Exception):
    """입력 불가 — exit 2."""


class Reject(Exception):
    """독립이 아닌 GPT 입력 — exit 1."""


def norm(path) -> str:
    p = str(path or "").strip().strip("`")
    p = re.split(r"[\s(（]", p, maxsplit=1)[0] if p else ""
    p = re.sub(r":\d+(?:[-,]\d+)*$", "", p)
    if "/head/" in p:                         # review_merge.gpt_path 와 같은 규칙
        p = p.split("/head/", 1)[1]
    elif p.startswith("head/"):
        p = p[len("head/"):]
    p = re.sub(r"^(?:\./)+", "", p)            # ⛔ a/ · b/ 는 벗기지 않는다 — diff 헤더 접두가 아니라 실제 디렉터리일 수 있다
    return p.strip("/")


def expand(raw) -> list:
    """`a/{b,c}.json` 을 펼친다 — 실제 플랜이 이 표기를 쓴다."""
    m = re.search(r"\{([^{}]*)\}", raw)
    return [raw] if not m else [x for alt in m.group(1).split(",") for x in expand(raw[:m.start()] + alt.strip() + raw[m.end():])]


def entries(raw) -> list:
    """파일 칸 하나 → [(경로, 디렉터리인가)]. 경로 모양이 아닌 값(`--flag` · 버전 번호)은 버린다."""
    out = []
    for x in expand(str(raw or "").strip().strip("`")):
        is_dir = bool(re.search(r"/\**$", x.split()[0] if x.split() else ""))
        p = norm(x).rstrip("*").rstrip("/")
        if p and not p.startswith("-") and not re.fullmatch(r"[\d.]+", p) and ("/" in p or re.search(r"\.[A-Za-z][\w-]{0,9}$", p)):
            out.append((p, is_dir))
    return out


def same(a: str, b: str, a_dir: bool = False, b_dir: bool = False) -> bool:
    """경로 꼬리가 같으면 같은 파일 · 디렉터리 항목은 그 아래 파일을 덮는다."""
    if a == b or a.endswith("/" + b) or b.endswith("/" + a):
        return True
    return (a_dir and f"/{a}/" in f"/{b}/") or (b_dir and f"/{b}/" in f"/{a}/")


def claude_plan(doc) -> dict:
    if not isinstance(doc, dict):
        raise InputError("Claude 입력이 JSON 객체가 아니다")
    plan = doc["plan"] if isinstance(doc.get("plan"), dict) else doc
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise InputError("Claude 플랜에 steps 가 없다 — plan-lean2 반환이나 plan 객체를 준다")
    return plan


def gpt_plan(doc) -> dict:
    if not isinstance(doc, dict):
        raise InputError("GPT 입력이 JSON 객체가 아니다 — planner 마크다운은 받지 않는다(오염 표시를 실을 곳이 없다)")
    if doc.get("contaminated") is True or doc.get("contamination"):
        raise Reject(f"GPT 플랜에 오염 표시가 있다 — 독립 첫 패스가 아니다: {doc.get('contamination') or 'contaminated: true'}")
    if not isinstance(doc.get("steps"), list) or not doc["steps"]:
        raise InputError("GPT 플랜에 steps 가 없다 — 대조할 수 없다")
    return doc


def collect(pairs) -> dict:
    """[(파일 칸, 출처)] → {경로: {where, dir}}."""
    out = {}
    for raw, where in pairs:
        for p, is_dir in entries(raw):
            e = out.setdefault(p, {"where": [], "dir": False})
            e["dir"] = e["dir"] or is_dir
            if where not in e["where"]:
                e["where"].append(where)
    return out


def claude_files(plan: dict) -> dict:
    return collect([(f, str(s.get("id", "?"))) for s in plan["steps"] if isinstance(s, dict) for f in s.get("files") or []]
                   + [(w.get("file"), "writeScope") for w in plan.get("writeScope") or [] if isinstance(w, dict)])


def gpt_files(plan: dict) -> dict:
    return collect([(f, f"{k}번 단계") for k, s in enumerate(plan["steps"], 1) if isinstance(s, dict)
                    for f in ([s["file"]] if isinstance(s.get("file"), str) else []) + [x for x in s.get("files") or [] if isinstance(x, str)]])


def hit(path: str, is_dir: bool, other: dict) -> bool:
    return any(same(path, q, is_dir, other[q]["dir"]) for q in other)


def risks(plan: dict) -> list:
    out = []
    for r in plan.get("riskMatrix") or []:
        t = r.get("risk") if isinstance(r, dict) else r
        if isinstance(t, str) and t.strip():
            out.append(" ".join(t.split()))
    return out


def grams(t: str) -> set:
    s = re.sub(r"[\W_]+", "", t.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def similarity(a: str, b: str) -> float:
    x, y = grams(a), grams(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def pair_risks(cr: list, gr: list) -> tuple:
    cands = sorted(((similarity(a, b), i, j) for i, a in enumerate(cr) for j, b in enumerate(gr)), key=lambda t: (-t[0], t[1], t[2]))
    used_c, used_g, pairs = set(), set(), []
    for s, i, j in cands:
        if s < RISK_MATCH:
            break
        if i in used_c or j in used_g:
            continue
        used_c.add(i)
        used_g.add(j)
        pairs.append({"claude": cr[i], "gpt": gr[j], "similarity": round(s, 2)})
    return pairs, [a for i, a in enumerate(cr) if i not in used_c], [b for j, b in enumerate(gr) if j not in used_g]


def requirement_rows(plan: dict, gfiles: dict) -> list:
    steps = {s.get("id"): s for s in plan["steps"] if isinstance(s, dict)}
    rows = []
    for r in plan.get("rtm") or []:
        if not isinstance(r, dict):
            continue
        refs = [t.strip() for t in STEP_SPLIT.split(str(r.get("stepId") or "")) if t.strip()]
        found = [steps[x] for x in refs if x in steps]
        req = " ".join(f"{r.get('reqId', '?')} {r.get('requirement', '')}".split())
        base = {"req": req, "steps": refs}
        if not found:
            rows.append(dict(base, files=[], verdict="판정 불가 — 없는 Step"))
            continue
        fs = sorted({e for s in found for f in (s.get("files") or []) for e in entries(f)})
        if not fs:
            rows.append(dict(base, files=[], verdict="판정 불가 — Step 에 파일이 없다"))
        elif not any(hit(p, d, gfiles) for p, d in fs):
            rows.append(dict(base, files=[p + ("/" if d else "") for p, d in fs], verdict="미커버 — GPT 플랜이 이 요구의 구현 파일을 건드리지 않는다"))
    return rows


def diverge(claude_doc, gpt_doc) -> dict:
    cp, gp = claude_plan(claude_doc), gpt_plan(gpt_doc)
    cf, gf = claude_files(cp), gpt_files(gp)
    if not cf:
        raise InputError("Claude 플랜의 steps · writeScope 에 파일이 하나도 없다 — 대조할 수 없다")
    if not gf:
        raise InputError("GPT 플랜의 steps 에 파일이 하나도 없다 — 대조할 수 없다")
    c_only = [{"file": f + ("/" if cf[f]["dir"] else ""), "where": cf[f]["where"]} for f in sorted(cf) if not hit(f, cf[f]["dir"], gf)]
    g_only = [{"file": g + ("/" if gf[g]["dir"] else ""), "where": gf[g]["where"]} for g in sorted(gf) if not hit(g, gf[g]["dir"], cf)]
    reqs = requirement_rows(cp, gf)
    pairs, c_risk, g_risk = pair_risks(risks(cp), risks(gp))
    return {"files": {"claudeOnly": c_only, "gptOnly": g_only}, "requirements": reqs, "rtmPresent": bool(cp.get("rtm")),
            "risks": {"claudeOnly": c_risk, "gptOnly": g_risk, "paired": pairs},
            "summary": {"filesClaudeOnly": len(c_only), "filesGptOnly": len(g_only),
                        "requirementsUncovered": sum(r["verdict"].startswith("미커버") for r in reqs),
                        "requirementsUndetermined": sum(r["verdict"].startswith("판정 불가") for r in reqs),
                        "risksClaudeOnly": len(c_risk), "risksGptOnly": len(g_risk), "risksPaired": len(pairs)}}


def cell(text) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def render(d: dict) -> str:
    s = d["summary"]
    lines = ["# Claude ↔ GPT 독립 플랜 차이표", "",
             f"파일 한쪽 {s['filesClaudeOnly'] + s['filesGptOnly']}(Claude {s['filesClaudeOnly']} · GPT {s['filesGptOnly']}) · "
             f"요구 미커버 {s['requirementsUncovered']} · 판정 불가 {s['requirementsUndetermined']} · "
             f"위험 한쪽 {s['risksClaudeOnly'] + s['risksGptOnly']}(Claude {s['risksClaudeOnly']} · GPT {s['risksGptOnly']}) — "
             "어느 쪽이 옳은지는 Lead 가 정한다", "", "## 파일 — 한쪽에만 있는 변경 대상", ""]
    rows = [(x["file"], " · ".join(x["where"]), "—") for x in d["files"]["claudeOnly"]] + \
           [(x["file"], "—", " · ".join(x["where"])) for x in d["files"]["gptOnly"]]
    if rows:
        lines += ["| 파일 | Claude | GPT |", "|---|---|---|"] + [f"| `{f}` | {c} | {g} |" for f, c, g in sorted(rows)]
    else:
        lines.append("없음 — 두 플랜의 변경 대상이 같다.")
    lines += ["", "## 요구(RTM) — GPT 플랜이 구현 파일을 건드리지 않는 요구", ""]
    if not d["rtmPresent"]:
        lines.append("Claude RTM 이 없다 — 요구 대조는 판정 불가다(⛔ 미커버 0 이 아니다).")
    elif d["requirements"]:
        lines += ["| 요구 | Claude Step | 판정 |", "|---|---|---|"]
        lines += [f"| {cell(r['req'])} | {' · '.join(r['steps']) or '—'}" + (f" (`{'` · `'.join(r['files'])}`)" if r["files"] else "")
                  + f" | {r['verdict']} |" for r in d["requirements"]]
    else:
        lines.append("없음 — Claude RTM 의 요구마다 GPT 플랜이 구현 파일을 하나 이상 건드린다.")
    lines += ["", "## 위험 — 글자 겹침으로 짝을 찾지 못한 것", "",
              "⛔ 짝이 없다는 것은 **표현이 달랐다**는 뜻일 뿐이다 — 같은 위험을 다르게 썼을 수 있으니 Lead 가 의미로 대조한다.", ""]
    one = [(cell(t), "Claude") for t in d["risks"]["claudeOnly"]] + [(cell(t), "GPT") for t in d["risks"]["gptOnly"]]
    lines += (["| 위험 | 쪽 |", "|---|---|"] + [f"| {t} | {side} |" for t, side in one]) if one else ["없음 — 모든 위험이 짝지어졌다."]
    if d["risks"]["paired"]:
        lines += ["", f"## 짝지은 위험 — 글자 bigram 유사도 {RISK_MATCH} 이상", "", "| Claude | GPT | 유사도 |", "|---|---|---|"]
        lines += [f"| {cell(p['claude'])} | {cell(p['gpt'])} | {p['similarity']} |" for p in d["risks"]["paired"]]
    return "\n".join(lines).rstrip() + "\n"


def run(a) -> int:
    if not (a.claude and a.gpt):
        print("UNRUN: --claude 와 --gpt 가 모두 필요하다 — 한쪽만으로는 차이를 만들 수 없다", file=sys.stderr)
        return UNRUN
    try:
        docs = [json.loads(pathlib.Path(p).read_text(encoding="utf-8")) for p in (a.claude, a.gpt)]
    except (OSError, ValueError) as e:
        print(f"UNRUN: 입력을 읽지 못했다(JSON 이어야 한다) — {e}", file=sys.stderr)
        return UNRUN
    try:
        d = diverge(*docs)
    except InputError as e:
        print(f"UNRUN: {e}", file=sys.stderr)
        return UNRUN
    except Reject as e:
        print(f"REJECT: {e}", file=sys.stderr)
        return REJECT
    text = render(d)
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return OK


# ── self-test ──────────────────────────────────────────────────────────────
def samples():
    claude = {"mode": "workflow", "plan": {
        "steps": [{"id": "S1", "title": "t", "files": ["Sources/App/Model.swift (신규)"]},
                  {"id": "S2", "title": "t", "files": ["./Sources/App/View.swift:40-52"]},
                  {"id": "S3", "title": "t", "files": ["Sources/App/Only.swift"]},
                  {"id": "S4", "title": "t", "files": []}],
        "writeScope": [{"file": "Sources/App/Model.swift", "rationale": "r"}],
        "riskMatrix": [{"risk": "캐시 무효화가 늦으면 목록이 옛 값을 보여 준다", "mitigation": "m"},
                       {"risk": "권한 거부 시 빈 화면", "mitigation": "m"}],
        "rtm": [{"reqId": "R1", "requirement": "모델 추가", "stepId": "S1"},
                {"reqId": "R2", "requirement": "전용 화면", "stepId": "S3"},
                {"reqId": "R3", "requirement": "없는 단계", "stepId": "S9"},
                {"reqId": "R4", "requirement": "파일 없는 단계", "stepId": "S4"},
                {"reqId": "R5", "requirement": "두 단계", "stepId": "S2,S3"}]}}
    # ⛔ 짝 없는 GPT 파일(Extra)에 격리 dir 전체 경로를 준다 — 경로 꼬리 대조는 head/ 를 안 벗겨도 짝을 찾으므로
    #    접두 규칙은 짝 없는 파일의 표시에서만 드러난다(변이 검증에서 발견)
    gpt = {"steps": [{"file": "head/Sources/App/Model.swift", "action": "create", "why": "w"},
                     {"file": "View.swift", "action": "modify", "why": "w"},
                     {"files": ["/tmp/fz-gpt-iso/head/Sources/App/Extra.swift"], "action": "create", "why": "w"}],
           "riskMatrix": [{"risk": "캐시 무효화가 늦으면 목록이 옛 값을 보여준다", "mitigation": "m"},
                          {"risk": "동시 편집 충돌", "mitigation": "m"}]}
    return claude, gpt


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" — {detail}"))

    def raises(fn, exc):
        try:
            fn()
        except exc:
            return True
        return False

    def t_files():
        d = diverge(*samples())
        case("files — 한쪽에만 있는 변경 대상(접두 head/ · ./ · 뒤 설명 · :줄을 벗기고 경로 꼬리로 맞춘다)",
             [x["file"] for x in d["files"]["claudeOnly"]] == ["Sources/App/Only.swift"]
             and [x["file"] for x in d["files"]["gptOnly"]] == ["Sources/App/Extra.swift"]
             and d["files"]["gptOnly"][0]["where"] == ["3번 단계"], d["files"])

    def t_paths():
        c = {"plan": {"steps": [{"id": "S1", "files": [".claude-plugin/{plugin,marketplace}.json", "tests/fixtures/x/run.sh", "--flag", "0.157.0"]}],
                      "rtm": [{"reqId": "R1", "requirement": "r", "stepId": "S1"}]}}
        g = {"steps": [{"files": [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "tests/fixtures/x/"]}]}
        d = diverge(c, g)
        case("paths — 중괄호를 펼치고 · 경로 아닌 값(--flag · 버전 번호)은 버리고 · 디렉터리 항목은 그 아래 파일을 덮는다",
             entries("--gpt-skill") == [] and entries("0.157.0") == [] and entries("tests/x/") == [("tests/x", True)]
             and entries("head/tests/x/") == [("tests/x", True)] and entries("/tmp/iso/head/a/b.swift") == [("a/b.swift", False)]
             and entries("a/{b,c}.json") == [("a/b.json", False), ("a/c.json", False)]
             and d["files"] == {"claudeOnly": [], "gptOnly": []} and d["requirements"] == [], d["files"])

    def t_rtm():
        rows = {r["req"].split()[0]: r["verdict"] for r in diverge(*samples())["requirements"]}
        case("rtm — GPT 가 구현 파일을 안 건드리는 요구는 미커버 · 없는 Step · 파일 없는 Step 은 판정 불가 · 덮은 요구는 표에 없다",
             rows == {"R2": "미커버 — GPT 플랜이 이 요구의 구현 파일을 건드리지 않는다",
                      "R3": "판정 불가 — 없는 Step", "R4": "판정 불가 — Step 에 파일이 없다"}, rows)

    def t_multi():
        rows = [r["req"] for r in diverge(*samples())["requirements"]]
        case("rtm-multi — stepId 'S2,S3' 은 두 Step 의 파일을 합쳐 본다(S2 를 GPT 가 건드려 커버)", not any(r.startswith("R5") for r in rows), rows)

    def t_risks():
        r = diverge(*samples())["risks"]
        case("risks — 거의 같은 위험은 짝짓고(유사도 표기) 나머지는 한쪽 위험이다",
             len(r["paired"]) == 1 and r["paired"][0]["similarity"] >= RISK_MATCH
             and r["claudeOnly"] == ["권한 거부 시 빈 화면"] and r["gptOnly"] == ["동시 편집 충돌"], r)

    def t_contam():
        c, g = samples()
        a = dict(g, contaminated=True)
        b = dict(g, contamination="rollout 감사가 ~/.claude/projects 읽기를 찾았다")
        case("contaminated — 오염 표시(contaminated · contamination)가 붙은 GPT 입력은 거부", raises(lambda: diverge(c, a), Reject) and raises(lambda: diverge(c, b), Reject))

    def t_inputs():
        c, g = samples()
        bad = [(c, "### Independent Plan: 마크다운"), (c, {"steps": []}), (c, {"steps": [{"action": "modify"}]}),
               ({"plan": {"steps": []}}, g), ([], g)]
        case("inputs — 마크다운 · 빈 steps · 파일 없는 steps · 객체 아님은 입력 불가", all(raises(lambda x=x: diverge(*x), InputError) for x in bad))

    def t_no_rtm():
        c, g = samples()
        del c["plan"]["rtm"]
        d = diverge(c, g)
        case("no-rtm — Claude RTM 이 없으면 요구 대조를 판정 불가로 적는다(미커버 0 이 아니다)",
             not d["rtmPresent"] and "판정 불가다" in render(d), render(d))

    def t_bare():
        c, g = samples()
        case("bare-plan — lean2 반환 대신 plan 객체만 줘도 같다", diverge(c["plan"], g) == diverge(c, g))

    def t_render():
        t = render(diverge(*samples()))
        case("render — 요약 · 파일 · 요구 · 위험 · 짝 표가 모두 나온다",
             "파일 한쪽 2(Claude 1 · GPT 1)" in t and "| `Sources/App/Extra.swift` | — | 3번 단계 |" in t
             and "| R2 전용 화면 | S3 (`Sources/App/Only.swift`) | 미커버" in t and "| 동시 편집 충돌 | GPT |" in t and "## 짝지은 위험" in t, t)

    def t_det():
        c, g = samples()
        case("deterministic — 같은 입력은 같은 표", render(diverge(c, g)) == render(diverge(*samples())))

    def t_cli():
        tmp = pathlib.Path(tempfile.mkdtemp(prefix="plan-divergence-"))
        try:
            c, g = samples()
            (tmp / "c.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
            (tmp / "g.json").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
            (tmp / "bad.json").write_text(json.dumps(dict(g, contaminated=True)), encoding="utf-8")
            (tmp / "g.md").write_text("### Independent Plan: x\n", encoding="utf-8")

            def cli(*args):
                for p in ("out.md", "rows.json"):
                    (tmp / p).unlink(missing_ok=True)
                r = subprocess.run([sys.executable, __file__, *args, "--out", str(tmp / "out.md"), "--json", str(tmp / "rows.json")],
                                   capture_output=True, text=True)
                return r.returncode, sorted(p.name for p in tmp.glob("*") if p.name in ("out.md", "rows.json"))
            got = (cli("--claude", str(tmp / "c.json"), "--gpt", str(tmp / "g.json")),
                   cli("--claude", str(tmp / "c.json")),
                   cli("--claude", str(tmp / "c.json"), "--gpt", str(tmp / "bad.json")),
                   cli("--claude", str(tmp / "c.json"), "--gpt", str(tmp / "g.md")))
            case("cli-exit — 차이표 0 · 한쪽 입력 없음 2 · 오염 1 · 마크다운 2 · 실패하면 파일 0개",
                 got == ((0, ["out.md", "rows.json"]), (2, []), (1, []), (2, [])), got)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    for t in (t_files, t_paths, t_rtm, t_multi, t_risks, t_contam, t_inputs, t_no_rtm, t_bare, t_render, t_det, t_cli):
        try:
            t()
        except Exception as e:   # ⛔ 케이스 안의 예외는 FAIL 로 센다 — 크래시로 끝나면 몇 건이 안 돌았는지 모른다
            case(f"{t.__name__} — 예외", False, repr(e))
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else REJECT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--claude")
    ap.add_argument("--gpt")
    ap.add_argument("--out")
    ap.add_argument("--json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    return run(a)


if __name__ == "__main__":
    sys.exit(main())
