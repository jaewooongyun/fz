#!/usr/bin/env python3
"""TEAM 실행 절차의 'Workflow 먼저 기동' 규칙 (S30) — Workflow 입력이 확정되면 곧바로 띄우라는 지침이 호출 단계보다 앞에 있는가.

Workflow 는 백그라운드로 돈다. 그런데 Lead 가 입력이 아닌 일(외부 자문 · 참조 확인)을 기동 앞에 하면 그만큼 Workflow 가 늦게 시작한다
(R-C 18 run 중 16 run 에서 기동 앞 자문이 102~283s). 이 검사는 그 지침이 지워지거나 호출 뒤로 밀리지 않게 한다.
⛔ 지침의 존재만 본다 — Lead 가 실제로 따르는지는 측정(앞 구간 분해)이 본다.
usage: check_workflow_first.py SKILL_MD... | --self-test
exit: 0=충족 · 1=위반(VIOLATION 줄) · 2=입력 오류(파일 없음 · 실행 절차 블록 없음 · Workflow 호출 줄 없음)
"""
import re
import sys

MARKER = "**Workflow 먼저 기동**"
HEADING = re.compile(r"^### 실행 절차 \(Lead\)\s*$", re.M)
CALL = ("**Workflow 호출**", "Workflow({ scriptPath:")


def block(text):
    m = HEADING.search(text)
    if not m:
        return None
    nxt = re.search(r"^#{2,3} ", text[m.end():], re.M)
    return text[m.end(): m.end() + (nxt.start() if nxt else len(text) - m.end())].split("\n")


def check(text):
    """(오류, 위반) — 오류는 판정 불가(exit 2), 위반은 규칙 위반(exit 1)."""
    lines = block(text)
    if lines is None:
        return "실행 절차 (Lead) 블록 없음", None
    call = next((i for i, l in enumerate(lines) if all(c in l for c in CALL)), None)
    if call is None:
        return "Workflow 호출 줄 없음", None
    marker = next((i for i, l in enumerate(lines) if MARKER in l), None)
    if marker is None:
        return None, "마커 없음"
    if marker > call:
        return None, "마커가 Workflow 호출 뒤에 있다"
    return None, None


def self_test():
    head = "# s\n\n### 실행 절차 (Lead)\n\n"
    call = "3. **Workflow 호출**: `Workflow({ scriptPath: 'x.js', args })`\n"
    rule = f"> ⛔ {MARKER} — 규칙\n"
    cases = [
        ("good", head + rule + "1. a\n" + call + "\n## 다음\n", (None, None)),
        ("marker-missing", head + "1. a\n" + call, (None, "마커 없음")),
        ("marker-after-call", head + "1. a\n" + call + rule, (None, "마커가 Workflow 호출 뒤에 있다")),
        ("marker-outside-block", rule + head + "1. a\n" + call, (None, "마커 없음")),
        ("marker-in-next-section", head + call + "\n### 다른 절\n" + rule, (None, "마커 없음")),
        ("no-block", "# s\n" + rule + call, ("실행 절차 (Lead) 블록 없음", None)),
        ("no-call", head + rule + "1. a\n", ("Workflow 호출 줄 없음", None)),
    ]
    bad = 0
    for name, text, want in cases:
        got = check(text)
        ok = got == want
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {name} — {got}")
    print(f"self-test {len(cases) - bad}/{len(cases)} passed")
    return 1 if bad else 0


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__.strip().splitlines()[-2])
        return 2
    if args == ["--self-test"]:
        return self_test()
    err_n = viol_n = 0
    for path in args:
        try:
            text = open(path, encoding="utf-8").read()
        except OSError as e:
            print(f"ERROR {path}: {e}")
            err_n += 1
            continue
        err, viol = check(text)
        if err:
            print(f"ERROR {path}: {err}")
            err_n += 1
        elif viol:
            print(f"VIOLATION {path}: {viol}")
            viol_n += 1
        else:
            print(f"OK {path}: Workflow 먼저 기동 규칙이 호출 단계 앞에 있다")
    return 2 if err_n else (1 if viol_n else 0)


if __name__ == "__main__":
    sys.exit(main())
