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
        ⛔ 이 면제가 없던 1차 판에서 실제 플랜(TKT-6894)의 신규 3파일이 위반으로 뜨는 오탐이 있었다
        (2026-09-11 실데이터 대조로 발견 — fixture 만으로는 드러나지 않았다). 면제 조건은
        rationale·file 에 `신규`/`new` 표기가 있는 것이며, 표기 없는 범위 밖 파일은 여전히 위반이다.
    · `steps[].verify` 가 VerifySpec 계약을 지키는가   (command=criterion+command+expect · manual=criterion)
    · id 가 유일한가                                    (중복은 개수 검사를 무력화한다)
  `--plan-doc` (plan 마크다운 — plan-v{N} · plan-final) 에서 재는 것(round 2 S17):
    · `경로:줄` 바로 뒤 따옴표 인용이 그 원문 줄과 같은가(F-432 — 렌즈가 규칙을 반대로 인용했다 · `--root` 가 있을 때)
    · "F-NNN 이 기록한" 꼴 근거 문장의 문단에 엔트리 원문 줄 포인터(`entries/F-NNN-*.md:줄`)가 있는가(F-453 — 기억으로 인용했다)
    · 보강 표지 `⊕` 가 남았는가 · Step 제목 id 가 겹치는가(F-315 — 중간본도 단일 최신 상태로 접는다)
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


# ── plan 문서(마크다운) 검사 — round 2 S17 ────────────────────────────────
QUOTE_AFTER_REF = re.compile(r"`?([\w./-]+\.[A-Za-z]\w{0,5}):(\d+)`?[\s—–:·-]{0,4}[\"“「]([^\"”」\n]{4,})[\"”」]")
FINDING_CLAIM = re.compile(r"F-(\d{3})\s*(?:이|가|은|는|의)?\s*(?:기록한|지목한|적은|보고한|남긴|에 따르면|에 기록된)")
STEP_HEADING = re.compile(r"^#{2,4}\s+(S\d+[a-z]?)\b", re.M)
AMEND_MARK = "⊕"
COUNT_CLAIM = re.compile(r"(?<![\w.-])\d[\d,.]*\s?(?:건|개(?!월)|곳|줄|행|파일|회|번|배|초|%|토큰|케이스|셀)")   # 단위 뒤 조사 · 서술어는 붙는다(12개다)
PATH_LINE_CLAIM = re.compile(r"[\w./-]+\.[A-Za-z]\w{0,5}:\d+")
CLAIM_EVIDENCE = re.compile(r"\[verified:|code-context(?:\.md)?(?::\d+|#[\w-]+)")


def _flat(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\*\*|`", "", s)).strip()


def _lines_of(path: str):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().split("\n")
    except (OSError, UnicodeDecodeError):
        return None


def check_doc(text: str, root=None, findings=None) -> tuple:
    """plan 마크다운 — (violations, notes). root · findings 가 없으면 그 대조는 unavailable 로 남긴다(통과가 아니다)."""
    v, notes = [], []
    quoted = 0
    for m in QUOTE_AFTER_REF.finditer(text):           # F-432 — 인용은 원문 줄과 글자가 같아야 한다(의역은 따옴표에 넣지 않는다)
        path, line, quote = m.group(1), int(m.group(2)), m.group(3)
        quoted += 1
        reg = re.match(r"(?:.*/)?entries/(F-\d{3}.*)$", path)   # 레지스트리 포인터는 --findings-dir 기준이다
        base, rel = (findings, reg.group(1)) if reg else (root, path)
        if not base:
            continue
        lines = _lines_of(os.path.join(base, rel))
        if lines is None:
            v.append(f"인용 대상을 열 수 없다: {path}:{line}")
            continue
        window = _flat(" ".join(lines[max(0, line - 1):line + 2]))
        if _flat(quote) not in window:
            src = _flat(lines[line - 1]) if 0 < line <= len(lines) else "(줄 없음)"
            v.append(f"{path}:{line} 인용이 원문과 다르다 — 인용 {quote[:60]!r} · 원문 {src[:80]!r}")
    if quoted and not (root and findings):
        notes.append(f"따옴표 인용 {quoted}건 — --root · --findings-dir 중 없는 쪽의 원문 대조 unavailable")
    for para in re.split(r"\n\s*\n", text):           # F-453 — finding 을 근거로 쓴 문장은 같은 문단에 원문 줄 포인터
        for m in FINDING_CLAIM.finditer(para):
            fid = m.group(1)
            ptr = re.search(r"entries/(F-%s[^\s:`)\"]*\.md):(\d+)" % fid, para)
            if not ptr:
                v.append(f"F-{fid} 을 근거로 쓴 문장에 엔트리 원문 줄 인용(entries/F-{fid}-*.md:줄)이 없다 — 기억으로 인용하지 않는다")
                continue
            if findings:
                lines = _lines_of(os.path.join(findings, ptr.group(1)))
                if lines is None or not (0 < int(ptr.group(2)) <= len(lines)):
                    v.append(f"F-{fid} 포인터 {ptr.group(1)}:{ptr.group(2)} 가 레지스트리에서 열리지 않는다")
    if FINDING_CLAIM.search(text) and not findings:
        notes.append("--findings-dir 가 없어 finding 포인터의 실재 대조 unavailable")
    amend = [i + 1 for i, ln in enumerate(text.split("\n")) if AMEND_MARK in ln]
    if amend:                                          # F-315 — 중간본에 보강 표지가 남으면 옛 문구와 새 문구가 함께 산다
        v.append(f"보강 표지 ⊕ 가 {len(amend)}줄 남았다(줄 {amend[:5]}) — plan-v{{N}} 도 단일 최신 상태로 접는다")
    ids = STEP_HEADING.findall(text)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        v.append(f"Step 제목 id 중복: {dup}")
    return v, notes


def unverified_claims(text: str) -> list:
    """F-185 — 수치 · 건수(`12건`) · 경로 줄(`a.py:30`) 주장 중 같은 줄에 `[verified:` 나 code-context 행 참조가 없는 것 → [(줄, 원문)].
    위반이 아니라 WARN 이다 — 주장마다 출처를 달라는 신호이고, 판정(사실인가)은 Lead · GPT 몫이다. 코드 블록 · 인라인 코드 안 숫자는 주장이 아니다."""
    out, fence = [], False
    for i, ln in enumerate(text.split("\n"), 1):
        if ln.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence or CLAIM_EVIDENCE.search(ln):
            continue
        if COUNT_CLAIM.search(re.sub(r"`[^`]*`", "", ln)) or PATH_LINE_CLAIM.search(ln):
            out.append((i, ln.strip()))
    return out


def run_doc(path: str, root=None, findings=None, quiet: bool = False) -> int:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        if not quiet:
            print(f"FAIL: plan 문서를 읽을 수 없다: {path} ({type(exc).__name__})")
        return 1
    v, notes = check_doc(text, root, findings)
    if not quiet:
        for n in notes:
            print(f"  ⚠️ {n}")
        claims = unverified_claims(text)
        for ln, s in claims:
            print(f"  WARN 미검증 주장 줄 {ln}: {s[:100]}")
        if claims:
            print(f"  WARN 미검증 주장 {len(claims)}건 — 같은 줄에 [verified: 출처] 나 code-context 행 참조를 단다(위반 아님 · exit 무관)")
        for x in v:
            print(f"  VIOLATION {x}")
        print((f"integrity=FAIL ({len(v)} 위반) " if v else "INTEGRITY_PASS ") + os.path.basename(path))
    return 1 if v else 0


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
    doc = os.path.join(fixture_dir, "doc")
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    if os.path.isdir(doc):                              # plan 문서 셀(round 2 S17) — 셀마다 양성(good.md) 대조를 함께 본다
        root, ents = os.path.join(doc, "root"), os.path.join(doc, "entries")

        def doc_v(name):
            with open(os.path.join(doc, name), "r", encoding="utf-8") as fh:
                return check_doc(fh.read(), root, ents)[0]
        good_v = doc_v("good.md")
        for cell, name, need in (("f432-plan-quote-mismatch", "bad-quote.md", ("인용이 원문과 다르다",)),
                                 ("f453-finding-claim-unquoted", "bad-finding.md", ("엔트리 원문 줄 인용", "레지스트리에서 열리지 않는다")),
                                 ("f315-amend-marker-left", "bad-amend.md", ("보강 표지 ⊕", "Step 제목 id 중복"))):
            got = doc_v(name)
            ok = not good_v and all(any(n in x for x in got) for n in need)
            if ok:
                passed += 1
                if listing:
                    print(f"PASS {cell}")
            else:
                fails.append(f"{cell} — 위반 {got} · good.md {good_v}")
                print(f"FAIL {cell}: 위반 {got} · good.md {good_v}")
        with open(os.path.join(doc, "claims.md"), "r", encoding="utf-8") as fh:   # F-185 — 경고 줄 집합이 정확히 근거 없는 두 줄
            text = fh.read()
        got = [ln for ln, _s in unverified_claims(text)]
        cell = "r3-f185-prose-claim-unverified-warn"
        if got == [5, 8] and check_doc(text)[0] == []:
            passed += 1
            if listing:
                print(f"PASS {cell}")
        else:
            fails.append(f"{cell} — 경고 줄 {got} (기대 [5, 8])")
            print(f"FAIL {cell}: 경고 줄 {got} (기대 [5, 8])")
    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    if fails:
        print(f"plan_integrity self-test {passed}/{total} passed")
        return 1
    print(f"INTEGRITY_SELFTEST_OK (양성 1 · 음성 {len(bads)} · 문서 셀 {4 if os.path.isdir(doc) else 0} — {passed}/{total})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="plan 반환의 참조 무결성 검사")
    ap.add_argument("target", nargs="?", help="workflow-result.json 경로")
    ap.add_argument("--self-test", metavar="FIXTURE_DIR", help="fixture 디렉토리로 양성·음성 self-test")
    ap.add_argument("--plan-doc", metavar="MD", help="plan 마크다운(plan-v{N} · plan-final) 검사 — 인용 · finding 근거 · 단일 최신 상태")
    ap.add_argument("--root", help="--plan-doc 의 `경로:줄` 인용을 대조할 저장소 루트")
    ap.add_argument("--findings-dir", help="--plan-doc 의 finding 포인터를 대조할 레지스트리 entries/")
    args = ap.parse_args()
    if args.self_test:
        return self_test(args.self_test)
    if args.plan_doc:
        return run_doc(args.plan_doc, args.root, args.findings_dir)
    if not args.target:
        ap.print_help()
        return 2
    return run_one(args.target)


if __name__ == "__main__":
    sys.exit(main())
