#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. census 대상은 `--repo`, 입력은 위치 인자로
#   받는다. 문서 경로는 주석 인용뿐이다 (lint #N6 면제 형태 c).
"""plan_resolve_impact_requests.py — impact 렌즈가 못 얻은 요청을 census 로 해소한다.

배경: `agents/plan-impact.md` 는 **Bash 가 없다**(스키마 수준). 그래서 base 원본 호출자 수 같은
git·grep 질문을 직접 못 얻고 `originBodyRequests` 로 되돌려 보낸다. `skills/fz-plan/SKILL.md` 는
*"impactRequests 가 비어 있지 않으면 Lead 가 resolve 한다"* 고만 적혀 있어 **수동 의존**이었다 —
무시되면 영향 분석이 그만큼 비어 있는 채로 plan 에 들어간다(GPT verify #11: R2 품질 oracle 부재).

이 스크립트는 요청에서 **심볼 후보를 추출해 census 를 돌리고**, 못 푼 것은 남긴다.
⛔ 자동 해소는 "심볼 등장 횟수" 까지다 — 책임 비교·설계 판단은 Lead 몫이며 그 경계를 출력에 적는다.

⛔ **0건은 측정 실패를 먼저 의심한다** (Negative-Result Gate): 심볼 census 가 0 이면
   같은 명령으로 **positive control**(레포에 반드시 있는 토큰)을 함께 돌려 도구가 살아 있음을
   보인다. control 이 0 이면 그 census 는 `unavailable` 이다 — 부재로 쓰지 않는다.

exit: 0=전건 판정(해소 또는 미해소로 분류 완료) / 1=측정 실패·입력 결함 / 2=사용법
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

# 요청 문장에서 census 가능한 심볼 후보: 백틱 인용 · 함수 호출형 · CamelCase 식별자
SYMBOL_RES = (
    re.compile(r"`([A-Za-z_][A-Za-z0-9_.:]{2,})`"),
    re.compile(r"\b([A-Za-z_][A-Za-z0-9_]{2,})\s*\("),
    re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b"),
)
CONTROL_TOKEN = "func "          # Swift 레포 기준 positive control. --control 로 교체 가능


def extract_symbols(text: str) -> list:
    out = []
    for rx in SYMBOL_RES:
        for m in rx.findall(text or ""):
            if m not in out:
                out.append(m)
    return out[:3]          # 요청당 상위 3개까지 — census 폭발 방지(상한을 인쇄한다)


def census(repo: str, needle: str) -> tuple:
    """(건수, 진단). ⛔ grep 실패(exit≥2)는 0 이 아니라 None 이다."""
    try:
        proc = subprocess.run(
            ["grep", "-rIn", "--exclude-dir=.git", "--exclude-dir=.build", "-F", needle, repo],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"grep 호출 실패({type(exc).__name__})"
    if proc.returncode >= 2:
        return None, f"grep exit {proc.returncode} (측정 실패)"
    return len((proc.stdout or b"").decode("utf-8", "replace").splitlines()), ""


def resolve(doc: dict, repo: str, control: str) -> tuple:
    reqs = doc.get("impactRequests")
    if reqs is None:
        lens = doc.get("lensOutputs") or {}
        reqs = ((lens.get("impact") or {}).get("originBodyRequests")) or []
    if not isinstance(reqs, list):
        return [], [], ["impactRequests 가 배열이 아니다 (입력 결함)"]
    ctrl, ctrl_note = census(repo, control)
    errors = []
    if ctrl is None:
        errors.append(f"positive control 실패: {ctrl_note} — 모든 census 를 unavailable 로 둔다")
    elif ctrl == 0:
        errors.append(f"positive control {control!r} 가 0건 — 도구·경로가 틀렸다. census 를 부재로 읽지 않는다")
    resolved, unresolved = [], []
    for req in reqs:
        text = req if isinstance(req, str) else json.dumps(req, ensure_ascii=False)
        syms = extract_symbols(text)
        if not syms:
            unresolved.append((text, "census 가능한 심볼을 추출하지 못했다 — Lead 판단 필요"))
            continue
        if errors:
            unresolved.append((text, "census unavailable (positive control 실패)"))
            continue
        counts = []
        for sym in syms:
            n, note = census(repo, sym)
            counts.append((sym, n, note))
        if all(n is None for _, n, _ in counts):
            unresolved.append((text, "census 전건 실패"))
        else:
            resolved.append((text, counts))
    return resolved, unresolved, errors


def report(resolved, unresolved, errors, control, ctrl_n=None) -> int:
    for e in errors:
        print(f"  ⚠️ {e}")
    for text, counts in resolved:
        print(f"  RESOLVED {text[:90]}")
        for sym, n, note in counts:
            shown = "unavailable" if n is None else f"{n}건"
            print(f"      census `{sym}` = {shown}{f' ({note})' if note else ''}")
    for text, why in unresolved:
        print(f"  UNRESOLVED {text[:90]}\n      사유: {why}")
    total = len(resolved) + len(unresolved)
    if errors:
        print(f"측정 실패 — 요청 {total}건 중 해소 0 (positive control: {control!r})")
        return 1
    print(f"RESOLVE_OK (요청 {total}건 — 해소 {len(resolved)} · 미해소 {len(unresolved)}"
          f" · 심볼 상한 요청당 3 · 판단 경계: 책임 비교는 Lead)")
    return 0


def self_test() -> int:
    """양성(심볼 존재) · 경계(심볼 부재 0건 + control 통과) · 음성(control 실패) · 미추출."""
    import shutil
    passed, fails = 0, []
    root = tempfile.mkdtemp(prefix="fzri-")
    try:
        repo = os.path.join(root, "repo")
        os.makedirs(repo)
        with open(os.path.join(repo, "a.swift"), "w", encoding="utf-8") as fh:
            fh.write("func extractBody() {}\nfunc caller() { extractBody() }\n")
        doc = {"impactRequests": [
            "base 원본의 `extractBody` 호출자 수 확인 필요",          # 존재 → 해소
            "`missingSymbolXyz` 의 이전 호출자 수",                  # 부재 → 0건(control 통과 하에)
            "설계 판단이 필요하다",                                   # 심볼 미추출 → 미해소
        ]}
        r, u, e = resolve(doc, repo, CONTROL_TOKEN)
        if len(r) == 2 and len(u) == 1 and not e:
            passed += 1
        else:
            fails.append(f"정상: resolved {len(r)} (기대 2) · unresolved {len(u)} (기대 1) · errors {e}")
        # control 이 없는 레포 → 전건 unavailable + exit 1 경로
        empty = os.path.join(root, "empty")
        os.makedirs(empty)
        with open(os.path.join(empty, "x.txt"), "w", encoding="utf-8") as fh:
            fh.write("nothing here\n")
        r2, u2, e2 = resolve(doc, empty, CONTROL_TOKEN)
        if e2 and len(r2) == 0:
            passed += 1
        else:
            fails.append(f"control 실패 경로: errors={e2} resolved={len(r2)} (기대 errors 있음 · resolved 0)")
        # 입력 결함
        r3, u3, e3 = resolve({"impactRequests": "문자열"}, repo, CONTROL_TOKEN)
        if e3:
            passed += 1
        else:
            fails.append("입력 결함(배열 아님)을 잡지 못했다")
        # 빈 배열 → 요청 0건은 정상 통과(해소할 것이 없다)
        r4, u4, e4 = resolve({"impactRequests": []}, repo, CONTROL_TOKEN)
        if not e4 and not r4 and not u4:
            passed += 1
        else:
            fails.append("빈 요청 배열 처리 이상")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    if fails:
        print(f"plan_resolve_impact_requests self-test {passed}/{total} passed")
        return 1
    print(f"RESOLVE_OK (self-test {passed}/{total} — 양성 1 · 경계 1 · 음성 2)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="impactRequests 를 grep census 로 해소")
    ap.add_argument("target", nargs="?", help="workflow-result.json")
    ap.add_argument("--repo", help="census 대상 레포 루트")
    ap.add_argument("--control", default=CONTROL_TOKEN, help=f"positive control 토큰 (기본 {CONTROL_TOKEN!r})")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.target or not args.repo:
        ap.print_help()
        return 2
    try:
        with open(args.target, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"FAIL: 입력을 읽을 수 없다: {args.target} ({type(exc).__name__})")
        return 1
    if not os.path.isdir(args.repo):
        print(f"FAIL: --repo 가 디렉토리가 아니다: {args.repo}")
        return 1
    r, u, e = resolve(doc, args.repo, args.control)
    return report(r, u, e, args.control)


if __name__ == "__main__":
    sys.exit(main())
