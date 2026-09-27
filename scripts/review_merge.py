#!/usr/bin/env python3
# lint:no-root-anchor — 병합 입력(Claude·GPT·diff)과 fixture 폴더를 인자로 받는다(플러그인 루트의 파일을 읽지 않는다).
# diff-parse: hunk-state — `@@ -a,b +c,d @@` 헤더로 hunk 범위를 추적하고, hunk 안에서는 남은 줄 수를 세어
#   `+++`·`---` 로 시작하는 소스 행을 파일 헤더로 오인하지 않는다(증거 재실측의 대상 텍스트를 모은다).
"""리뷰 발견의 결정론 병합 (S20 · 정본 `modules/peer-review-gates.md` § MergeContract).

Lead 가 손으로 하던 기계 작업만 한다 — 판정(`include`·`observation`·`exclude`)은 하지 않는다.

  dedup 키     파일 + line_range 겹침 + 축(§3). 축이 다르면 같은 자리라도 별건. craft 항목은 결함과 섞지 않는다
  보존         ⛔ 후보를 지우지 않는다 — 입력 후보 수 = 출력 후보 수(AC-4). 같은 키는 그룹으로 묶을 뿐이다
  귀속         그룹마다 both · claude_only · gpt_only (GPT 독립 첫 패스와 Claude 렌즈 중 누가 찾았나)
  근거 재실측   증거 속 인용(백틱 구간, 없으면 전문)이 그 파일 hunk 에 공백 정규화 후 **전부** 있으면 evidenceVerified
  게시 등급     post · hold · suggestion — 미확인 근거는 hold(삭제 아님) · craft 는 ruleRef 가 있고 confidence 80 이상일
               때만 post(확신도가 낮으면 suggestion 채널) · pre-existing 은 suggestion 으로 cap(§7) · confidence 80 미만 결함은 hold
  GPT verdict  reverse → disposition question + oracle(§6 — 이종 검증에 삭제 권한을 주지 않는다) · challenge → Lead 확인
  contested    교차 판정이 갈린 항목은 원본 severity 와 crossVerdicts 를 그대로 둔다(스크립트가 고르지 않는다)

모드
  --claude FILE (--gpt FILE | --gpt-unavailable 사유) --diff FILE [--out FILE]   병합
  --check-fixture DIR   tests/fixtures/peer-review/tier2-merge — 전건 보존 · 입력 순서가 바뀌어도 같은 그룹
  --self-test

exit: 0=병합 · 1=거부(오염된 GPT 입력 · 계약 위반) · 2=측정 실패(⛔ 통과 아님 — GPT 입력도 사유도 없을 때 포함)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import subprocess
import sys
import tempfile

OK, REJECT, UNRUN = 0, 1, 2
SEVERITIES = ("critical", "major", "minor", "suggestion")
CONFIDENCE_FLOOR = 80                      # OVERRIDE 의 보고 하한과 같은 값 — 여기서는 삭제가 아니라 hold 로 쓴다
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
QUOTE_RE = re.compile(r"`([^`\n]+)`")


class Unrun(Exception):
    pass


class Reject(Exception):
    pass


# ── diff → 파일별 hunk 텍스트 ──────────────────────────────────────
def hunk_text(diff: str) -> dict:
    """파일 경로 → hunk 안 모든 행(문맥 · 추가 · 삭제)의 내용. 삭제된 파일은 `--- a/` 경로로 귀속한다."""
    files: dict = {}
    cur = old_path = None
    rem_old = rem_new = 0
    for line in diff.split("\n"):
        if rem_old > 0 or rem_new > 0:
            tag = line[:1]
            if tag in ("-", "+", " "):
                if tag in ("-", " "):
                    rem_old -= 1
                if tag in ("+", " "):
                    rem_new -= 1
                if cur is not None:
                    files.setdefault(cur, []).append(line[1:])
            continue                                 # '\ No newline at end of file' 는 세지 않는다
        if line.startswith("diff --git "):
            cur = old_path = None
            continue
        if line.startswith("--- "):
            p = line[4:]
            old_path = None if p == "/dev/null" else (p[2:] if p.startswith("a/") else p)
            continue
        if line.startswith("+++ "):
            p = line[4:]
            cur = old_path if p == "/dev/null" else (p[2:] if p.startswith("b/") else p)
            continue
        m = HUNK_RE.match(line)
        if m and cur is not None:
            rem_old = int(m.group(2)) if m.group(2) is not None else 1
            rem_new = int(m.group(4)) if m.group(4) is not None else 1
    return {f: norm("\n".join(v)) for f, v in files.items()}


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def evidence_verified(cand: dict, texts) -> bool | None:
    """None = 재실측하지 않았다(fixture). 인용 구간이 모두 있어야 true — 하나라도 없으면 false."""
    if texts is None:
        return None
    ev = cand.get("evidence") or ""
    spans = [norm(q) for q in QUOTE_RE.findall(ev)] or [norm(ev)]
    spans = [s for s in spans if len(s) >= 3]
    if not spans:
        return False
    pool = [texts[cand["file"]]] if cand.get("file") in texts else list(texts.values()) if not cand.get("file") else []
    return bool(pool) and all(any(s in t for t in pool) for s in spans)


# ── 입력 정규화 ────────────────────────────────────────────────────
def spans(line_range) -> list:
    out = []
    for part in re.split(r"[,;]", str(line_range or "")):
        nums = [int(n) for n in re.findall(r"\d+", part)]
        if nums:
            out.append((min(nums), max(nums)))
    return out


def gpt_path(p):
    """GPT 독립 첫 패스는 격리 dir 의 `head/` 스냅샷을 본다 — 접두를 벗겨 레포 상대 경로로 맞춘다."""
    if not p:
        return p
    if "/head/" in p:
        return p.split("/head/", 1)[1]
    return p[len("head/"):] if p.startswith("head/") else p


def candidate(item: dict, source: str, lens) -> dict:
    return {
        "id": f"{source}:{item.get('id')}", "source": source, "lens": lens,
        "file": gpt_path(item.get("file")) if source == "gpt" else item.get("file"),
        "line_range": item.get("line_range"),
        "discoveryAxis": item.get("discoveryAxis") or "unknown",
        "craftAxis": item.get("craftAxis"), "ruleRef": item.get("ruleRef"),
        # Tier 3 는 finalSeverity 가 확정값이다. Tier 2 의 crossSeverity 는 제안이라 원본을 쓴다(§9)
        "severity": item.get("finalSeverity") or item.get("severity"),
        "origin": item.get("origin"), "confidence": item.get("confidence"),
        "evidence": item.get("evidence"),
        "title": item.get("title") or item.get("description"),
        "crossVerdict": item.get("crossVerdict"), "crossVerdicts": item.get("crossVerdicts"),
        "counterVerdict": item.get("counterVerdict"),
    }


def claude_candidates(doc: dict) -> list:
    if isinstance(doc.get("issues"), list):
        return [candidate(i, "claude", str(i.get("id", "")).split(":")[0] or None) for i in doc["issues"]]
    if isinstance(doc.get("findings"), list):
        return [candidate(i, "claude", str(i.get("id", "")).split(":")[0] or None) for i in doc["findings"]]
    if isinstance(doc.get("reviews"), list):
        return [candidate(i, "claude", r.get("agent")) for r in doc["reviews"] for i in r.get("issues") or []]
    raise Unrun("Claude 입력에 issues · findings · reviews 가 없다")


def gpt_candidates(doc: dict) -> tuple:
    if doc.get("contaminated") is True or doc.get("contamination"):
        raise Reject(f"GPT 입력에 오염 표시가 있다 — 독립 첫 패스가 아니다: {doc.get('contamination') or 'contaminated: true'}")
    items = doc.get("findings") if isinstance(doc.get("findings"), list) else doc.get("issues") or []
    return [candidate(i, "gpt", "gpt") for i in items], list(doc.get("verdicts") or [])


# ── 병합 ───────────────────────────────────────────────────────────
def axis_key(c):
    return ("craft", c["craftAxis"]) if c.get("craftAxis") else ("defect", c["discoveryAxis"])


def group(cands: list) -> list:
    """union-find — 같은 파일 · 같은 축 · 줄 범위가 겹치면 한 그룹. 위치를 모르면 혼자다."""
    parent = list(range(len(cands)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    sp = [spans(c.get("line_range")) for c in cands]
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            a, b = cands[i], cands[j]
            if not a.get("file") or a.get("file") != b.get("file") or axis_key(a) != axis_key(b) or not sp[i] or not sp[j]:
                continue
            if any(x[0] <= y[1] and y[0] <= x[1] for x in sp[i] for y in sp[j]):
                parent[find(i)] = find(j)
    buckets: dict = {}
    for i in range(len(cands)):
        buckets.setdefault(find(i), []).append(cands[i])
    return list(buckets.values())


def grade(c: dict) -> str:
    sev = c["effectiveSeverity"]
    if c["evidenceVerified"] is False:
        return "hold"
    conf = c.get("confidence")
    low = isinstance(conf, (int, float)) and conf < CONFIDENCE_FLOOR
    if c.get("craftAxis"):
        return "post" if c.get("ruleRef") and sev in ("critical", "major", "minor") and not low else "suggestion"
    if sev == "suggestion":
        return "suggestion"
    return "hold" if low else "post"


def merge(claude: list, gpt: list, verdicts: list, texts, gpt_unavailable) -> dict:
    cands = [dict(c) for c in claude + gpt]
    by_id = {c["id"]: c for c in cands}
    for c in cands:
        c["effectiveSeverity"] = "suggestion" if c.get("origin") == "pre-existing" else c.get("severity")
        c["nonBlocking"] = c.get("origin") == "improvement"
        c["evidenceVerified"] = evidence_verified(c, texts)
        c["disposition"] = None                      # ⛔ exclude 는 매기지 않는다 — include·observation 도 Lead 판정
        c["leadCheck"] = c.get("crossVerdict") == "contested"
        c["foundBy"] = [c["source"]]
    for v in verdicts:
        c = by_id.get(f"claude:{v.get('target')}")
        if c is None:
            continue
        kind = v.get("verdict")
        c["gptVerdict"] = kind
        if kind == "agree":
            c["foundBy"].append("gpt-verdict")
        elif kind == "supplement":
            c["gptNote"] = v.get("note")
        elif kind == "challenge":
            c["leadCheck"] = True
            c["gptNote"] = v.get("note")
        elif kind == "reverse":
            c["disposition"] = "question"
            c["oracle"] = v.get("oracle") or v.get("note") or "판별 방법 미기재 — Lead 가 적는다"
    for c in cands:
        c["grade"] = grade(c)
    groups = sorted(group(cands), key=lambda g: min((m.get("file") or "", (spans(m.get("line_range")) or [(0, 0)])[0][0], m["id"]) for m in g))
    out, gsum = [], []
    for n, g in enumerate(groups, 1):
        srcs = {m["source"] for m in g}
        attr = "both" if {"claude", "gpt"} <= srcs else ("claude_only" if "claude" in srcs else "gpt_only")
        members = sorted(g, key=lambda m: m["id"])
        for m in members:
            m["group"] = n
            m["attribution"] = attr
            out.append(m)
        gsum.append({"group": n, "file": members[0].get("file"), "axis": list(axis_key(members[0])), "attribution": attr,
                     "members": [m["id"] for m in members]})
    if len(out) != len(cands):
        raise Reject(f"후보 보존 위반 — 입력 {len(cands)} ≠ 출력 {len(out)}(AC-4)")
    if any(c.get("disposition") == "exclude" for c in out):
        raise Reject("disposition exclude 는 Lead 전용이다")
    count = lambda key, vals: {v: sum(1 for x in out if x.get(key) == v) for v in vals}  # noqa: E731
    return {
        "schemaVersion": 1,
        "inputs": {"claude": len(claude), "gpt": len(gpt), "gptVerdicts": len(verdicts), "gptUnavailable": gpt_unavailable,
                   "evidenceChecked": texts is not None},
        "candidates": out,
        "groups": gsum,
        "report": {g: [c["id"] for c in out if c["grade"] == g] for g in ("post", "hold", "suggestion")}
                  | {"question": [c["id"] for c in out if c["disposition"] == "question"],
                     "leadCheck": [c["id"] for c in out if c["leadCheck"]]},
        "summary": {"candidatesIn": len(cands), "candidatesOut": len(out), "groups": len(gsum),
                    "attribution": {a: sum(1 for g in gsum if g["attribution"] == a) for a in ("both", "claude_only", "gpt_only")},
                    "grade": count("grade", ("post", "hold", "suggestion")),
                    "contested": sum(1 for c in out if c.get("crossVerdict") == "contested"),
                    "evidenceUnverified": sum(1 for c in out if c["evidenceVerified"] is False)},
    }


def load(path: str):
    try:
        return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Unrun(f"JSON 을 읽을 수 없다 — {path}: {e}")


def run_merge(a) -> int:
    if not a.claude or not a.diff:
        raise Unrun("--claude 와 --diff 가 필요하다(근거 재실측 없이는 게시 등급을 매기지 않는다)")
    if not a.gpt and not (a.gpt_unavailable or "").strip():
        raise Unrun("GPT 독립 입력(--gpt)이 없는데 사유(--gpt-unavailable)도 없다 — 조용히 Claude 단독으로 병합하지 않는다")
    gpt, verdicts = gpt_candidates(load(a.gpt)) if a.gpt else ([], [])
    try:
        texts = hunk_text(pathlib.Path(a.diff).read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        raise Unrun(f"diff 를 읽을 수 없다 — {e}")
    result = merge(claude_candidates(load(a.claude)), gpt, verdicts, texts, None if a.gpt else a.gpt_unavailable.strip())
    text = json.dumps(result, ensure_ascii=False, indent=1) + "\n"
    if a.out:
        pathlib.Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    s = result["summary"]
    print(f"MERGE OK — 후보 {s['candidatesIn']}→{s['candidatesOut']} · 그룹 {s['groups']} · {s['attribution']} · {s['grade']}", file=sys.stderr)
    return OK


def check_fixture(d: pathlib.Path) -> int:
    doc = load(str(d / "stage1-input.json"))
    base = claude_candidates(doc)
    runs = []
    rng = random.Random(20260927)                    # 고정 시드 — 같은 입력이면 같은 섞기
    orders = [list(base), list(reversed(base)), rng.sample(base, len(base))]
    for order in orders:
        r = merge(order, [], [], None, "fixture — GPT 입력 없음")
        runs.append((r["summary"]["candidatesOut"], sorted(tuple(g["members"]) for g in r["groups"])))
    n_in = len(base)
    kept = all(out == n_in for out, _ in runs)
    stable = all(g == runs[0][1] for _, g in runs)
    print(f"{'FIXTURE OK  ' if kept and stable else 'FIXTURE FAIL'} tier2-merge — 입력 {n_in} · 출력 {[o for o, _ in runs]} · "
          f"그룹 {len(runs[0][1])} · 입력 순서 {len(orders)}가지에서 {'같은' if stable else '⛔다른'} 그룹")
    return OK if kept and stable else REJECT


# ── self-test ──────────────────────────────────────────────────────
DIFF = ("diff --git a/src/a.swift b/src/a.swift\n--- a/src/a.swift\n+++ b/src/a.swift\n@@ -10,2 +10,4 @@\n"
        " let service = APIClient.shared\n-let x = 1\n+let  x =   2\n++++ literal plus line\n+func load() { service.fetch() }\n"
        "diff --git a/src/b.swift b/src/b.swift\n--- a/src/b.swift\n+++ b/src/b.swift\n@@ -1 +1 @@\n-old\n+new\n")


def issue(i, file="src/a.swift", lr="10-12", axis="structure", sev="major", origin="regression", conf=90, ev="`APIClient.shared`", **kw):
    d = {"id": i, "file": file, "line_range": lr, "discoveryAxis": axis, "severity": sev, "origin": origin,
         "confidence": conf, "evidence": ev, "description": f"d{i}"}
    d.update(kw)
    return d


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' — {got}'}")

    # ⛔ 예외도 FAIL 줄로 보인다 — 병합 불변식(보존 · exclude 금지)이 던지면 요약 줄 없이 죽어 판정이 안 보였다
    try:
        texts = hunk_text(DIFF)
        M = lambda claude, gpt=(), verdicts=(), t=texts: merge([candidate(c, "claude", "l") for c in claude],  # noqa: E731
                                                              [candidate(g, "gpt", "gpt") for g in gpt], list(verdicts), t, None)
        r = M([issue("A1"), issue("A2", axis="runtime_safety")])
        case("axis-separate — 같은 줄이라도 축이 다르면 별건", r["summary"]["groups"] == 2, r["groups"])
        r = M([issue("A1"), issue("Q1", lr="11")])
        case("same-key-group — 같은 파일·겹침·같은 축은 한 그룹, 둘 다 남는다", r["summary"]["groups"] == 1 and r["summary"]["candidatesOut"] == 2, r["groups"])
        r = M([issue(f"X{i}", lr=str(10 + i % 3)) for i in range(7)])
        case("preserve-count — 입력 후보 수 = 출력 후보 수(AC-4)", r["summary"]["candidatesIn"] == r["summary"]["candidatesOut"] == 7, r["summary"])
        r = M([issue("E1", ev="`let x = 2`"), issue("E2", axis="correctness", ev="`service.missing()`")])
        e1, e2 = (next(c for c in r["candidates"] if c["id"] == f"claude:{k}") for k in ("E1", "E2"))
        case("evidence — 공백이 달라도 인용이 있으면 verified · post", e1["evidenceVerified"] is True and e1["grade"] == "post", e1)
        case("evidence — 인용이 없으면 false · hold 이고 지우지 않는다", e2["evidenceVerified"] is False and e2["grade"] == "hold" and r["summary"]["candidatesOut"] == 2, e2)
        r = M([issue("H1", ev="`+++ literal plus line`")])
        case("hunk-state — hunk 안의 `+++` 행은 헤더가 아니라 내용이다", r["candidates"][0]["evidenceVerified"] is True, r["candidates"][0])
        r = M([issue("A1")], verdicts=[{"target": "A1", "verdict": "reverse", "oracle": "load() 가 main 에서 불리는지 로그로 본다"}])
        c = r["candidates"][0]
        case("gpt-reverse — question 으로 바꾸고 oracle 을 적는다(삭제 아님)", c["disposition"] == "question" and "oracle" in c and r["summary"]["candidatesOut"] == 1, c)
        cv = [{"by": "arch", "verdict": "agree"}, {"by": "quality", "verdict": "false_positive"}]
        r = M([issue("C1", sev="minor", crossVerdict="contested", crossVerdicts=cv)])
        c = r["candidates"][0]
        case("contested — 원본 severity · crossVerdicts 보존 · Lead 확인", c["severity"] == "minor" and c["crossVerdicts"] == cv and c["leadCheck"] and c["disposition"] is None, c)
        r = M([issue("A1"), issue("A2", file="src/b.swift", lr="1", ev="`new`")],
              gpt=[issue("G1", file="/tmp/fz-gpt-iso/head/src/a.swift", lr="12"), issue("G2", file="head/src/c.swift", lr="5")])
        case("attribution — both · claude_only · gpt_only", r["summary"]["attribution"] == {"both": 1, "claude_only": 1, "gpt_only": 1}, r["summary"]["attribution"])
        g1 = next(c for c in r["candidates"] if c["id"] == "gpt:G1")
        case("gpt-path — 격리 dir 의 head/ 접두를 벗겨 레포 경로로 맞춘다", g1["file"] == "src/a.swift" and g1["attribution"] == "both", g1["file"])
        r = M([issue("L1", conf=70), issue("L2", axis="naming", conf=60, craftAxis="naming"), issue("L3", conf=95),
               issue("L4", axis="placement", conf=60, craftAxis="placement", ruleRef="R3")])
        grades = {c["id"]: c["grade"] for c in r["candidates"]}
        case("confidence-grading — 확신도 낮은 결함 hold · 낮은 craft 는 규칙 인용이 있어도 suggestion 채널 · 높은 결함 post(삭제 없음)",
             grades == {"claude:L1": "hold", "claude:L2": "suggestion", "claude:L3": "post", "claude:L4": "suggestion"}, grades)
        r = M([issue("K1", craftAxis="naming", ruleRef="R3"), issue("K2")])
        case("craft-channel — craft 는 같은 자리·축의 결함과 섞지 않는다 · ruleRef 있으면 post",
             r["summary"]["groups"] == 2 and next(c for c in r["candidates"] if c["id"] == "claude:K1")["grade"] == "post", r["groups"])
        r = M([issue("P1", origin="pre-existing")])
        c = r["candidates"][0]
        case("pre-existing — severity 를 suggestion 으로 cap(§7) · 원본 severity 는 남는다", c["effectiveSeverity"] == "suggestion" and c["severity"] == "major" and c["grade"] == "suggestion", c)
        r = M([issue("Z1", disposition="exclude")])
        case("no-exclude — 입력이 무엇이든 exclude 를 매기지 않는다", all(c["disposition"] != "exclude" for c in r["candidates"]), r["candidates"])
        base = [issue(f"S{i}", lr=f"{10 + i}-{11 + i}", axis=("structure", "correctness")[i % 2]) for i in range(6)]
        g_a = sorted(tuple(g["members"]) for g in M(base)["groups"])
        g_b = sorted(tuple(g["members"]) for g in M(list(reversed(base)))["groups"])
        case("order — 입력 순서가 바뀌어도 같은 그룹", g_a == g_b, f"{g_a} ≠ {g_b}")

        me = pathlib.Path(__file__).resolve()
        with tempfile.TemporaryDirectory(prefix="fz-review-merge-") as tmp:
            t = pathlib.Path(tmp)
            (t / "claude.json").write_text(json.dumps({"issues": [issue("A1")]}), encoding="utf-8")
            (t / "diff.patch").write_text(DIFF, encoding="utf-8")
            (t / "gpt-bad.json").write_text(json.dumps({"contaminated": True, "findings": [issue("G1")]}), encoding="utf-8")
            base_args = [sys.executable, str(me), "--claude", str(t / "claude.json"), "--diff", str(t / "diff.patch")]
            rc = subprocess.run(base_args, capture_output=True, text=True).returncode
            case("gpt-missing — GPT 입력도 사유도 없으면 exit 2", rc == UNRUN, f"exit {rc}")
            rc = subprocess.run(base_args + ["--gpt-unavailable", "quota 소진"], capture_output=True, text=True).returncode
            case("gpt-unavailable — 사유가 있으면 Claude 단독으로 병합한다", rc == OK, f"exit {rc}")
            rc = subprocess.run(base_args + ["--gpt", str(t / "gpt-bad.json")], capture_output=True, text=True).returncode
            case("gpt-contaminated — 오염 표시가 붙은 GPT 입력은 거부(exit 1)", rc == REJECT, f"exit {rc}")
    except Exception as e:  # noqa: BLE001
        results.append(False)
        print(f"FAIL  실행 오류 — {type(e).__name__}: {e}")

    print(f"self-test {sum(results)}/{len(results)} passed")
    return OK if all(results) else REJECT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--claude")
    ap.add_argument("--gpt")
    ap.add_argument("--gpt-unavailable", metavar="사유")
    ap.add_argument("--diff")
    ap.add_argument("--out")
    ap.add_argument("--check-fixture", metavar="DIR")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    try:
        if a.self_test:
            return self_test()
        if a.check_fixture:
            return check_fixture(pathlib.Path(a.check_fixture).expanduser())
        return run_merge(a)
    except Reject as e:
        print(f"REJECT: {e}", file=sys.stderr)
        return REJECT
    except Unrun as e:
        print(f"UNRUN: {e}", file=sys.stderr)
        return UNRUN


if __name__ == "__main__":
    sys.exit(main())
