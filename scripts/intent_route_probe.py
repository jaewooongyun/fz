#!/usr/bin/env python3
"""intent_route_probe.py — 요청 문장이 /fz 의 트리거 표 어느 행에 걸리는지 잰다 (F-528).

왜: /fz 실제 요청 281건 중 매칭 0 이 33.5% · 2행 이상이 39.5% 였다(2026-11-05 실측). 레지스트리 트리거를 실제 문장으로 재는 검사가 없었고,
lint #4(과도한 겹침)는 임계 미정이라 SKIP 이었다. 이 프로브가 표를 **그대로 파싱해** 문장마다 걸린 행을 낸다(정규식을 여기 베끼지 않는다).

읽는 표:
  modules/intent-registry.md   `## 스킬별 …` 부터 `## Confidence` 앞까지의 모든 표 — 첫 칸 = 라벨 · 나머지 칸의 백틱 = 정규식(`\\|` 는 |)
  modules/pipelines.md          `### N. <이름>` 아래 `| 트리거 | \\`…\\` |` — 쉼표 목록 또는 정규식(Phase 3.1 resolver 와 같은 표)
라벨 = 스킬 이름(fz-…) · 파이프라인 이름 · 특수 행(괄호 이름 — 예: `(이어 하기)`). total-miss = 어느 행에도 안 걸린 문장.

사용:
  intent_route_probe.py --sentence "…" [--sentence …]           문장마다 걸린 라벨
  intent_route_probe.py --corpus FILE [--json]                   FILE = [{request, …}] JSON 또는 한 줄 한 문장 — --json 은 {rows:[{request, matched}]}
  intent_route_probe.py --cases TSV                              합성 corpus 단언(문장 \\t 반드시 걸릴 라벨 \\t 걸리면 안 될 라벨 \\t 메모) — lint #4 가 쓴다
  intent_route_probe.py --check-skill-example skills/fz/SKILL.md "실측 예 `<문장>` 은 <파이프라인> 트리거에 있으나 스킬 매칭은 0" 문장이 지금 참인가
exit: 0 PASS · 1 단언 실패(cases · check-skill-example) · 2 UNRUN(표 파싱 실패 · 정규식 오류 · 입력 없음 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import tempfile

OK, FAIL, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
START, STOP = "## 스킬별", "## Confidence"
EXAMPLE_RE = re.compile(r"실측 예 `([^`]+)` (?:은|는) ([A-Za-z0-9-]+) 트리거에 있으나 스킬 매칭은 0")


class Unrun(Exception):
    pass


def _pats(cell: str):
    return [m.replace("\\|", "|") for m in re.findall(r"`([^`]+)`", cell)]


def rows_of(root: pathlib.Path):
    """[(라벨, 출처, [compiled])] — 표가 없거나 정규식이 깨지면 Unrun."""
    reg = (root / "modules" / "intent-registry.md").read_text(encoding="utf-8")
    a, b = reg.find(START), reg.find(STOP)
    if a < 0 or b < a:
        raise Unrun("intent-registry.md 의 트리거 절(## 스킬별 … ## Confidence)을 찾지 못했다")
    rows = []
    for ln in reg[a:b].splitlines():
        if not ln.startswith("| ") or set(ln.replace("|", "").strip()) <= set("-: "):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
        pats = [p for c in cells[1:] for p in _pats(c)]
        if pats:
            rows.append((cells[0].strip("`"), "registry", pats))
    pipe = (root / "modules" / "pipelines.md").read_text(encoding="utf-8")
    name = None
    for ln in pipe.splitlines():
        m = re.match(r"^### \d+\. ([A-Za-z0-9-]+)", ln)
        if m:
            name = m.group(1)
            continue
        if name and ln.startswith("| 트리거 |"):
            alts = [x.strip() for p in _pats(ln) for x in p.split(", ") if x.strip()]
            if alts:
                rows.append((name, "pipelines", ["|".join(alts)]))
            name = None
    if not rows:
        raise Unrun("트리거 행을 하나도 읽지 못했다 — 표 형식이 바뀌었을 수 있다")
    out = []
    for label, src, pats in rows:
        try:
            out.append((label, src, [re.compile(p, re.I) for p in pats]))
        except re.error as e:
            raise Unrun(f"{src} `{label}` 정규식 오류 — {e}")
    return out


def match(sentence: str, rows) -> list:
    return sorted({label for label, _, ps in rows if any(p.search(sentence) for p in ps)})


def load_corpus(path: pathlib.Path):
    t = path.read_text(encoding="utf-8")
    try:
        d = json.loads(t)
        return [x["request"] if isinstance(x, dict) else str(x) for x in d]
    except ValueError:
        return [ln for ln in t.splitlines() if ln.strip()]


def run_cases(path: pathlib.Path, rows):
    """(위반 목록, 케이스 수)."""
    bad, n = [], 0
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip() or ln.startswith("#"):
            continue
        parts = ln.split("\t")
        if len(parts) < 3:
            bad.append(f"cases:{i} 칸이 3개 미만 — 문장 \\t 필수 \\t 금지 \\t 메모")
            continue
        n += 1
        s, need, forbid = parts[0], [x for x in parts[1].split(",") if x.strip() and x != "-"], [x for x in parts[2].split(",") if x.strip() and x != "-"]
        got = set(match(s, rows))
        if need == ["∅"]:
            if got:
                bad.append(f"cases:{i} `{s}` — 어느 행에도 안 걸려야 하는데 {sorted(got)}")
            continue
        miss = [x for x in need if x not in got]
        hit = [x for x in forbid if x in got]
        if miss or hit:
            bad.append(f"cases:{i} `{s}` — 빠짐 {miss} · 걸리면 안 되는데 {hit} · 실제 {sorted(got)}")
    return bad, n


def check_example(skill_md: pathlib.Path, rows):
    m = EXAMPLE_RE.search(skill_md.read_text(encoding="utf-8"))
    if not m:
        raise Unrun(f"{skill_md} 에 '실측 예 `…` 은 <파이프라인> 트리거에 있으나 스킬 매칭은 0' 문장이 없다")
    s, pipe = m.group(1), m.group(2)
    got = match(s, rows)
    skills = [g for g in got if g.startswith("fz-")]
    return (pipe in got and not skills), s, pipe, got


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" — {detail}"))

    with tempfile.TemporaryDirectory() as t:
        r = pathlib.Path(t)
        (r / "modules").mkdir()
        (r / "modules" / "intent-registry.md").write_text(
            "# x\n## 스킬별 레지스트리\n| 스킬 | 한 | 영 |\n|---|---|---|\n| fz-fix | `고쳐\\|버그` | `fix` |\n| fz-pr | `(?<![A-Za-z])PR(?![A-Za-z])` | — |\n"
            "## 구어체\n| 스킬 | 추가 |\n|---|---|\n| fz-fix | `안 돼` |\n| (이어 하기) | `^계속` |\n## Confidence 판정\n| 예 | `고쳐` |\n", encoding="utf-8")
        (r / "modules" / "pipelines.md").write_text("### 3. quick-fix\n| 항목 | 값 |\n|---|---|\n| 트리거 | `타임아웃.*변경, 값.*바꿔` |\n", encoding="utf-8")
        rows = rows_of(r)
        case("parse-registry-and-pipelines", sorted({x[0] for x in rows}) == ["(이어 하기)", "fz-fix", "fz-pr", "quick-fix"], rows)
        case("escaped-bar-is-alternation", match("버그 있어", rows) == ["fz-fix"])
        case("confidence-section-not-trigger", len([x for x in rows if x[0] == "예"]) == 0)
        case("pipeline-comma-list", match("타임아웃 30초로 변경", rows) == ["quick-fix"])
        case("token-boundary", match("PRD 정리", rows) == [] and match("PR 올려", rows) == ["fz-pr"])
        case("special-row", match("계속 진행해", rows) == ["(이어 하기)"])
        case("total-miss-empty", match("안녕", rows) == [])
        tsv = r / "cases.tsv"
        tsv.write_text("버그 고쳐\tfz-fix\tfz-pr\t-\n안녕\t∅\t-\t-\nPRD 문서\t-\tfz-pr\t경계\n", encoding="utf-8")
        case("cases-pass", run_cases(tsv, rows) == ([], 3), run_cases(tsv, rows))
        tsv.write_text("버그 고쳐\tfz-pr\t-\t-\n", encoding="utf-8")
        case("cases-fail", len(run_cases(tsv, rows)[0]) == 1)
        sk = r / "SKILL.md"
        sk.write_text("실측 예 `타임아웃 30초로 변경` 은 quick-fix 트리거에 있으나 스킬 매칭은 0이었다\n", encoding="utf-8")
        case("skill-example-true", check_example(sk, rows)[0] is True)
        sk.write_text("실측 예 `버그 타임아웃 30초로 변경` 은 quick-fix 트리거에 있으나 스킬 매칭은 0이었다\n", encoding="utf-8")
        case("skill-example-false", check_example(sk, rows)[0] is False)
        (r / "modules" / "pipelines.md").write_text("### 3. quick-fix\n| 트리거 | `(` |\n", encoding="utf-8")
        try:
            rows_of(r)
            case("bad-regex-unrun", False, "예외 없음")
        except Unrun:
            case("bad-regex-unrun", True)
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else FAIL


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--root", default=os.path.join(SCRIPT_DIR, ".."))
    ap.add_argument("--sentence", action="append", default=[])
    ap.add_argument("--corpus")
    ap.add_argument("--cases")
    ap.add_argument("--check-skill-example", metavar="SKILL_MD")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    root = pathlib.Path(a.root).resolve()
    try:
        rows = rows_of(root)
        if a.check_skill_example:
            ok, s, pipe, got = check_example(root / a.check_skill_example if not os.path.isabs(a.check_skill_example) else pathlib.Path(a.check_skill_example), rows)
            print(f"{'OK' if ok else 'FALSE'}: `{s}` → {got or '(매칭 0)'} — {pipe} 매칭 · 스킬 매칭 0 이어야 한다")
            return OK if ok else FAIL
        if a.cases:
            bad, n = run_cases(pathlib.Path(a.cases), rows)
            print(f"라우팅 corpus — 케이스 {n} · 위반 {len(bad)}")
            for b in bad:
                print(f"  ✗ {b}")
            return FAIL if bad else (OK if n else UNRUN)
        sents = list(a.sentence) + (load_corpus(pathlib.Path(a.corpus)) if a.corpus else [])
        if not sents:
            raise Unrun("문장이 없다 — --sentence · --corpus · --cases 중 하나")
    except (Unrun, OSError) as e:
        print(f"UNRUN: {e}", file=sys.stderr)
        return UNRUN
    res = [{"request": s, "matched": match(s, rows)} for s in sents]
    if a.json:
        print(json.dumps({"rows": res, "total": len(res), "totalMiss": sum(not r["matched"] for r in res),
                          "multi": sum(len(r["matched"]) >= 2 for r in res)}, ensure_ascii=False))
    else:
        for r in res:
            print(f"{len(r['matched'])}  {r['request'][:90]}\n     -> {', '.join(r['matched']) or '(매칭 0)'}")
        print(f"총 {len(res)} · 매칭 0 {sum(not r['matched'] for r in res)} · 2행 이상 {sum(len(r['matched']) >= 2 for r in res)}")
    return OK


if __name__ == "__main__":
    sys.exit(main())
