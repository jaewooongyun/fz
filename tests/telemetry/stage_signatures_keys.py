#!/usr/bin/env python3
# lint:no-root-anchor — 대상은 이 파일 기준 `../../scripts/fz_telemetry_report.py` 이고 기준 파일은 `--baseline` 으로 받는다.
"""텔레메트리 스테이지 서명 보존 (S16).

`scripts/fz_telemetry_report.py` 는 워커 결과의 키 집합으로 스테이지를 가른다(`STAGE_SIGNATURES` — 첫 부분집합 일치).
⛔ 왜: craft 옵션이 arch 결과에 `axisCoverage` 를 더한다. 서명 표를 고치다 기존 서명이 빠지거나 더한 키 때문에 분류가
   바뀌면, 과거·현재 run 이 조용히 다른 스테이지로 집계된다.

검사
  ① 기준 파일의 서명(키 튜플 → 스테이지)이 현재 표에 전부 있고 상대 순서도 같다 — 첫 일치가 분류를 정한다
  ② craft 가 켜진 결과(axisCoverage 포함)의 분류가 꺼진 결과와 같다 — peer-review(review1) · review-live
     분류는 실제 분류기(`classify_result`)로 한다. 꺼짐 결과가 어느 서명에도 안 맞는 쌍은 둘 다 other 일 뿐이라
     '동일'로 세지 않고 판별 불가로 따로 적는다(판별한 쌍이 0 이면 exit 2)

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
REPORT = pathlib.Path(__file__).resolve().parent.parent.parent / "scripts" / "fz_telemetry_report.py"

AXIS_ROWS = [{"axis": a, "status": "none", "note": "n"} for a in
             ("idiom", "naming", "architecture", "ui_structure", "placement", "design_alternative")]
# (이름, craft 꺼짐 결과, craft 켜짐 결과) — 최상위 키만 분류에 쓰인다
PAIRS = [
    ("peer-review stage1-arch", {"issues": [], "strengths": [], "overall_assessment": "o"},
     {"issues": [], "strengths": [], "overall_assessment": "o", "axisCoverage": AXIS_ROWS}),
    ("review-live stage1-arch", {"findings": [], "okAreas": []},
     {"findings": [], "okAreas": [], "axisCoverage": AXIS_ROWS}),
]


def load_report():
    spec = importlib.util.spec_from_file_location("fz_telemetry_report", REPORT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def classifier(mod, table):
    """실제 분류기(fz_telemetry_report.classify_result)를 이 표로 돌린다 — 분류 논리를 여기 다시 짜지 않는다."""
    def run(result):
        saved = mod.STAGE_SIGNATURES
        mod.STAGE_SIGNATURES = tuple(table)
        try:
            return mod.classify_result(result)[0]
        finally:
            mod.STAGE_SIGNATURES = saved
    return run


def check(table, baseline, classify) -> tuple:
    """(위반, 판별 불가 쌍)."""
    v, blind = [], []
    cur = [(tuple(r), s) for r, s in table]
    base = [(tuple(r), s) for r, s in baseline]
    missing = [b for b in base if b not in cur]
    for b in missing:
        v.append(f"서명이 빠졌다 — {b[0]} → {b[1]}")
    kept = [c for c in cur if c in base]
    if not missing and kept != base:
        v.append(f"기존 서명의 상대 순서가 바뀌었다 — 첫 일치가 분류를 정한다: {kept} ≠ {base}")
    for name, off, on in PAIRS:
        a, b = classify(off), classify(on)
        if a != b:
            v.append(f"{name}: craft 켜짐 결과의 분류가 다르다 — 꺼짐 {a} · 켜짐 {b}")
        elif a == "other":
            blind.append(name)                       # ⛔ 서명이 없어 둘 다 other — 같다는 판정이 아니다
    return v, blind


# ⛔ self-test 는 **합성 표**로 검사기 논리만 본다 — 실제 표·기준을 쓰면 진짜 위반이 "self-test 실패(판정 불가)" 로
#    뒤바뀐다(실측 2026-09-27: 기준에 가짜 서명을 넣은 사본에서 health-check 가 VIOLATION 대신 UNRUN 을 냈다).
SYN_TABLE = [(("issues", "overall_assessment", "strengths"), "review1"), (("adjustments", "additions"), "cross"),
             (("challenges", "missedIssues"), "counter")]
SYN_BASE = [[list(r), s] for r, s in SYN_TABLE]


def self_test() -> int:
    results = []

    def case(name, ok):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}")

    try:
        mod = load_report()
    except (OSError, AttributeError, ImportError) as e:
        print(f"FAIL  실제 분류기를 불러오지 못했다 — {e}")
        return VIOLATION
    run = lambda t: check(t, SYN_BASE, classifier(mod, t))  # noqa: E731
    case("⛔ 합성 표 · 합성 기준 → 위반 0(양성 대조)", run(SYN_TABLE)[0] == [])
    case("거부: 기존 서명이 빠졌다", any("빠졌다" in x for x in run(SYN_TABLE[1:])[0]))
    case("거부: 기존 서명 순서가 바뀌었다", any("순서" in x for x in run(list(reversed(SYN_TABLE)))[0]))
    stealer = [(("axisCoverage",), "craft")] + SYN_TABLE
    case("거부: axisCoverage 를 가로채는 서명이 앞에 섰다", any("분류가 다르다" in x for x in run(stealer)[0]))
    case("판별 불가: 꺼짐 결과가 어느 서명에도 안 맞는 쌍은 '동일'로 세지 않는다", run(SYN_TABLE)[1] == ["review-live stage1-arch"])
    case("거부: 서명 없는 결과가 craft 로 서명에 걸리면(other → craft) 판별 불가가 아니라 분류 변경",
         any(x.startswith("review-live stage1-arch: craft 켜짐") for x in run(stealer)[0]))
    print(f"self-test {sum(results)}/{len(results)} passed")
    return OK if all(results) else VIOLATION


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--baseline", required=True, help="기준 서명 JSON(tests/fixtures/telemetry/stage-signatures-base.json)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    try:
        mod = load_report()
        table = list(mod.STAGE_SIGNATURES)
        baseline = json.loads(pathlib.Path(a.baseline).read_text(encoding="utf-8"))
    except (OSError, ValueError, AttributeError) as e:
        print(f"UNRUN: 표나 기준을 읽지 못했다 — {e}")
        return UNRUN
    if not baseline:
        print("UNRUN: 기준 서명이 0개다(비교 대상 0 은 통과가 아니다)")
        return UNRUN
    v, blind = check(table, baseline, classifier(mod, table))
    for x in v:
        print(f"  ⛔ {x}")
    if v:
        print(f"VIOLATION {len(v)}건")
        return VIOLATION
    tail = f" · 판별 불가 {len(blind)}쌍(서명 없음 — {', '.join(blind)})" if blind else ""
    if len(blind) == len(PAIRS):
        print(f"UNRUN: 판별한 쌍이 0 이다{tail}")
        return UNRUN
    print(f"stage-signatures: 기준 {len(baseline)}개 보존 · craft 켜짐 분류 {len(PAIRS) - len(blind)}쌍 동일{tail}")
    return OK


if __name__ == "__main__":
    sys.exit(main())
