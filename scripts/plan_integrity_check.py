#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 검사 대상 JSON 과 fixture 디렉토리를 인자로
#   받고, 문서 경로는 주석 인용뿐이다 (lint #N6 면제 형태 c).
"""plan_integrity_check.py — plan-collaborative 반환의 **참조 무결성**을 본다. 구조 검사다.

⛔ 이 스크립트가 재는 것과 아닌 것 (이름이 과대 주장하지 않도록 명시 — GPT verify #7):
  재는 것: 문서 **내부 참조**가 서로를 가리키는가 —
    · `rtm[].stepId` 가 `steps[].id` 에 있는가        (계획이 자기 Step 을 가리키는가)
    · CC `links[].sourceId` 가 `edgeCases[].id` 에 있는가 (교차가 실재하는 케이스를 가리키는가)
    · `writeScope[].file` 이 `readScope` 안에 있는가   (⛔ 읽지도 않은 파일을 고치기로 하지 않았는가)
      — 단 **신규 생성 파일은 면제**한다. 존재하지 않는 파일은 읽을 수 없으므로 readScope 에 있을 수 없다.
        ⛔ 이 면제가 없던 1차 판에서 실제 플랜(TVG-6894)의 신규 3파일이 위반으로 뜨는 오탐이 있었다
        (2026-09-11 실데이터 대조로 발견 — fixture 만으로는 드러나지 않았다). 면제 조건은
        rationale·file 에 `신규`/`new` 표기가 있는 것이며, 표기 없는 범위 밖 파일은 여전히 위반이다.
    · `steps[].verify` 가 VerifySpec 계약을 지키는가   (command=criterion+command+expect · manual=criterion)
    · id 가 유일한가                                    (중복은 개수 검사를 무력화한다)
  ⛔ 재지 못하는 것: 계획이 **요구사항을 충족하는가** · 그 파일이 실제로 존재하는가 ·
     verify 가 제목이 말하는 것을 측정하는가. 앞의 둘은 Lead·GPT 판정이고, 마지막은
     `gpt-exec.sh verify-gates` 의 measurement_fit 축이다.

입력: `plan-collaborative.js` 반환 JSON (`plan` + `lensOutputs`). ⛔ `lensOutputs` 가 없으면
  CC 참조 검사는 **skip 이 아니라 'unavailable' 로 보고**한다 — 볼 수 없었던 것을 통과로 쓰지 않는다.

exit: 0=전부 충족 / 1=위반 또는 입력 결함(측정 실패) / 2=사용법
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

VERIFY_REQUIRED = {"command": ("criterion", "command", "expect"), "manual": ("criterion",)}
# 신규 생성 표기 — 이 표기가 있으면 readScope 포함 검사를 면제하고 note 로만 남긴다.
NEW_FILE_MARKERS = ("신규", "new file", "New file", "(new)", "생성")


def norm_path(raw: str) -> str:
    """readScope 항목은 순수 경로가 아니다 — `경로 — 설명`·`§X 경로`·백틱 포함 형태가 섞인다.
    ⛔ 문자열 동일성으로 비교하면 전부 위반으로 뜬다(GPT verify #7). 경로 토큰만 뽑아 정규화한다."""
    t = str(raw).strip().strip("`")
    t = re.split(r"\s+[—–-]\s+|\s+\(", t)[0].strip().strip("`")
    t = re.sub(r"^§\S+\s*", "", t).strip()
    t = t.lstrip("./").rstrip("/")
    return os.path.normpath(t) if t else ""


def check(doc: dict) -> tuple:
    """반환 (violations, notes). notes 는 'unavailable' 류 관측(통과가 아니다)."""
    v, notes = [], []
    plan = doc.get("plan")
    if not isinstance(plan, dict):
        return ["plan 객체가 없다 (입력 결함 — 측정 실패)"], notes

    steps = plan.get("steps") or []
    ids = [s.get("id") for s in steps if isinstance(s, dict)]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        v.append(f"steps.id 중복: {sorted(dup)}")
    id_set = {i for i in ids if i}
    if not id_set:
        v.append("steps.id 가 하나도 없다 (0/0 통과 금지)")

    # ① verify 계약
    for s in steps:
        if not isinstance(s, dict):
            v.append("steps 항목이 객체가 아니다")
            continue
        ver = s.get("verify")
        sid = s.get("id", "?")
        if not isinstance(ver, dict):
            v.append(f"{sid}: verify 객체 없음")
            continue
        kind = ver.get("kind")
        if kind not in VERIFY_REQUIRED:
            v.append(f"{sid}: verify.kind 가 command|manual 이 아니다 ({kind!r})")
            continue
        for key in VERIFY_REQUIRED[kind]:
            if not str(ver.get(key) or "").strip():
                v.append(f"{sid}: verify({kind}) 에 {key} 누락")

    # ② rtm → steps
    rtm = plan.get("rtm") or []
    for row in rtm:
        if not isinstance(row, dict):
            v.append("rtm 항목이 객체가 아니다")
            continue
        sid = row.get("stepId")
        # 한 행이 여러 Step 을 가리키는 표기(`S1,S2` · `S1·S2`)를 허용한다 — 실측 형태다
        refs = [t.strip() for t in re.split(r"[,·/]| and ", str(sid or "")) if t.strip()]
        if not refs:
            v.append(f"rtm({row.get('reqId', '?')}): stepId 비어 있음")
        for r in refs:
            if r not in id_set:
                v.append(f"rtm({row.get('reqId', '?')}): stepId {r!r} 가 steps.id 에 없다")

    # ③ writeScope ⊆ readScope
    read = {norm_path(x) for x in (plan.get("readScope") or []) if norm_path(x)}
    new_exempt = []
    for w in plan.get("writeScope") or []:
        if not isinstance(w, dict):
            v.append("writeScope 항목이 객체가 아니다")
            continue
        f = norm_path(w.get("file"))
        blob = f"{w.get('file') or ''} {w.get('rationale') or ''}"
        is_new = any(m in blob for m in NEW_FILE_MARKERS)
        if not f:
            v.append("writeScope 에 file 이 비어 있다")
        elif read and f not in read:
            if is_new:
                new_exempt.append(os.path.basename(f) or f)
            else:
                v.append(f"writeScope {f!r} 가 readScope 에 없다 (읽지 않은 파일을 변경 대상으로 둠 — 신규면 rationale 에 '신규' 를 표기하라)")
    if new_exempt:
        notes.append(f"신규 생성 표기로 readScope 포함 검사 면제 {len(new_exempt)}건: {', '.join(new_exempt[:5])}")
    if not read:
        notes.append("readScope 가 비어 있어 writeScope 포함 관계는 unavailable")

    # ④ CC links → edgeCases.id  (lensOutputs 필요)
    lens = doc.get("lensOutputs")
    if not isinstance(lens, dict):
        notes.append("lensOutputs 없음 — CC 참조 검사 unavailable (plan-collaborative S5a 이전 산출)")
    else:
        edge = (lens.get("edge") or {}).get("edgeCases") or []
        case_ids = {e.get("id") for e in edge if isinstance(e, dict) and e.get("id")}
        if not case_ids:
            notes.append("edgeCases 가 비어 있어 CC 참조는 unavailable")
        for tag in ("impactOnEdge", "edgeOnImpact"):
            cc = lens.get(tag)
            if not isinstance(cc, dict):
                continue
            for l in cc.get("links") or []:
                if not isinstance(l, dict):
                    v.append(f"{tag}.links 항목이 객체가 아니다")
                    continue
                src = l.get("sourceId")
                if case_ids and src not in case_ids:
                    v.append(f"{tag}: sourceId {src!r} 가 edgeCases.id 에 없다")
    return v, notes


def run_one(path: str, quiet: bool = False) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        if not quiet:
            print(f"FAIL: 입력을 읽을 수 없다: {path} ({type(exc).__name__}: {exc})")
        return 1
    if not isinstance(doc, dict):
        if not quiet:
            print(f"FAIL: 최상위가 객체가 아니다: {path}")
        return 1
    v, notes = check(doc)
    if not quiet:
        for n in notes:
            print(f"  ⚠️ {n}")
        for x in v:
            print(f"  VIOLATION {x}")
    if v:
        if not quiet:
            print(f"integrity=FAIL ({len(v)} 위반) {os.path.basename(path)}")
        return 1
    if not quiet:
        print(f"INTEGRITY_PASS ({os.path.basename(path)} — 위반 0"
              + (f" · unavailable {len(notes)}건" if notes else "") + ")")
    return 0


def self_test(fixture_dir: str) -> int:
    """양성 1 + 음성 N. ⛔ 음성이 없으면 '검사기가 살아 있는가' 를 못 본다."""
    good = os.path.join(fixture_dir, "good.json")
    bads = sorted(glob.glob(os.path.join(fixture_dir, "bad-*.json")))
    if not os.path.isfile(good) or not bads:
        print(f"FAIL: fixture 부족 — good.json {os.path.isfile(good)} · bad-*.json {len(bads)}건")
        return 1
    passed, fails = 0, []
    if run_one(good, quiet=True) == 0:
        passed += 1
    else:
        fails.append("good.json 이 통과하지 않았다 (양성 실패)")
    for b in bads:
        if run_one(b, quiet=True) == 1:
            passed += 1
        else:
            fails.append(f"{os.path.basename(b)} 가 통과했다 (음성 실패 — 위반을 못 잡는다)")
    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    if fails:
        print(f"plan_integrity self-test {passed}/{total} passed")
        return 1
    print(f"INTEGRITY_SELFTEST_OK (양성 1 · 음성 {len(bads)} — {passed}/{total})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="plan 반환의 참조 무결성 검사")
    ap.add_argument("target", nargs="?", help="workflow-result.json 경로")
    ap.add_argument("--self-test", metavar="FIXTURE_DIR", help="fixture 디렉토리로 양성·음성 self-test")
    args = ap.parse_args()
    if args.self_test:
        return self_test(args.self_test)
    if not args.target:
        ap.print_help()
        return 2
    return run_one(args.target)


if __name__ == "__main__":
    sys.exit(main())
