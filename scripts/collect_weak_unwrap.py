#!/usr/bin/env python3
# lint:no-root-anchor — 인자로 받은 Swift 파일만 읽는다(플러그인 루트를 참조하지 않는다)
"""collect_weak_unwrap.py — weak 프로퍼티를 옵셔널 바인딩으로 푸는 자리의 **후보 전수**(F-004).

왜: 'weak unwrap 금지' 규칙을 이름 grep(`if let sheet`)으로 검사하니 `else if cond, let sheet = context.coordinator.sheet` 가
0건으로 빠졌고, 0건을 '위반 없음' 으로 읽었다. 규칙 검사는 **문법 형태로 넓히고 이름으로 좁힌다**.

수집   받은 파일 전체에서 `weak var|let NAME` 을 모으고, 바인딩 절마다 오른쪽 식(축약형이면 그 이름)이 NAME · self.NAME ·
       x.y.NAME · x?.NAME 으로 끝나면 후보다. 선언과 바인딩이 다른 파일이어도 받은 파일끼리는 교차한다.
형태   if let · guard let · while let · `cond, let`(조건 뒤 바인딩) · `else if cond, let` · 축약 `if let NAME` · var 바인딩 ·
       `case let NAME? = e` — 이 목록 밖 형태(switch 패턴 · for case 등)는 보지 않는다
⛔ 판정하지 않는다 — 후보다. 0건이면 '이 형태 목록에서 0건' 이라고 형태를 함께 찍는다(0건 ≠ 위반 없음 — 목록 밖은 모른다).
⛔ 프로젝트 규칙이 weak unwrap 금지를 선언할 때만 부른다(modules/review-checks.md 검증 4-F).

usage: collect_weak_unwrap.py FILE... [--json] | --self-test
exit: 0 수집(후보 0건 포함) · 2 입력 불가(파일 없음 · 읽기 실패 · 인자 없음)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

OK, UNRUN = 0, 2
FORMS = ("if let", "guard let", "while let", "cond, let", "else if cond, let", "축약 if let NAME", "var 바인딩", "case let NAME?")
WEAK_RE = re.compile(r"\bweak\s+(?:var|let)\s+(\w+)")
BIND_RE = re.compile(r"(?:\b(if|guard|while)\b|,)\s*(case\s+)?(let|var)\s+(\w+)\??\s*(?:=\s*([^,{]+?))?\s*(?=,|\{|\belse\b|$)")


def form_of(line: str, m) -> str:
    head, case, kw = m.group(1), m.group(2), m.group(3)
    if case:
        return "case let NAME?"
    if head is None:
        return "else if cond, let" if re.search(r"\belse\s+if\b", line[:m.start()]) else "cond, let"
    if m.group(5) is None:
        return "축약 if let NAME"
    return "var 바인딩" if kw == "var" else f"{head} let"


def collect(paths: list) -> tuple:
    texts = {p: open(p, encoding="utf-8", errors="replace").read().splitlines() for p in paths}
    weak = {}
    for p, lines in texts.items():
        for n, ln in enumerate(lines, 1):
            for m in WEAK_RE.finditer(ln):
                weak.setdefault(m.group(1), f"{p}:{n}")
    out = []
    for p, lines in texts.items():
        for n, ln in enumerate(lines, 1):
            for m in BIND_RE.finditer(ln):
                expr = (m.group(5) or m.group(4)).strip()
                for name, decl in weak.items():
                    if re.search(r"(?:^|[.?])" + re.escape(name) + r"$", expr):
                        out.append({"path": p, "line": n, "form": form_of(ln, m), "weak": name, "decl": decl, "code": ln.strip()[:120]})
    return weak, out


def main(argv: list) -> int:
    if "--self-test" in argv:
        return self_test()
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        print("UNRUN: Swift 파일 경로가 필요하다", file=sys.stderr)
        return UNRUN
    try:
        weak, cands = collect(paths)
    except OSError as e:
        print(f"UNRUN: 읽기 실패 — {e}", file=sys.stderr)
        return UNRUN
    if "--json" in argv:
        print(json.dumps({"weak": weak, "candidates": cands, "forms": FORMS}, ensure_ascii=False, indent=1))
        return OK
    for c in cands:
        print(f"{c['path']}:{c['line']}: {c['form']} · weak {c['weak']}(선언 {c['decl']}) · {c['code']}")
    print(f"weak unwrap 후보 {len(cands)}건 · weak 선언 {len(weak)}개 — 형태: {' · '.join(FORMS)}"
          + (" (이 형태 목록에서 0건 — 목록 밖 형태는 보지 않았다)" if not cands else ""))
    return OK


SAMPLE_A = """final class Coordinator {
    weak var sheet: Sheet?
    var other: Sheet?
}
"""
SAMPLE_B = """func update(context: Context) {
    if let sheet { sheet.show() }
    if let s = sheet { s.show() }
    guard let s = self.sheet else { return }
    while let s = context.coordinator.sheet { s.pop() }
    if ready, let s = sheet { s.show() }
    } else if !isPresented, let sheet = context.coordinator.sheet {
    if case let s? = coordinator?.sheet { s.show() }
    if let o = model.other { o.show() }
}
"""


def self_test() -> int:
    passed = total = 0

    def case(name, ok, detail=""):
        nonlocal passed, total
        total += 1
        passed += bool(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f" — {detail}"))

    with tempfile.TemporaryDirectory() as t:
        a, b = os.path.join(t, "A.swift"), os.path.join(t, "B.swift")
        open(a, "w", encoding="utf-8").write(SAMPLE_A)
        open(b, "w", encoding="utf-8").write(SAMPLE_B)
        weak, cands = collect([a, b])
        forms = sorted({c["form"] for c in cands})
        want = sorted(["축약 if let NAME", "if let", "guard let", "while let", "cond, let", "else if cond, let", "case let NAME?"])
        case("f004-variant-forms-collected — 일곱 형태 전부 후보 · weak 아닌 바인딩(model.other)은 빠진다 · 선언이 다른 파일이어도 교차",
             forms == want and len(cands) == 7 and all(c["weak"] == "sheet" and c["decl"].endswith("A.swift:2") for c in cands)
             and not any("model.other" in c["code"] for c in cands), (forms, len(cands)))
        r = subprocess.run([sys.executable, os.path.abspath(__file__), a], capture_output=True, text=True)
        case("f004-zero-reports-forms — 후보 0건이면 형태 목록과 '목록 밖은 보지 않았다' 를 함께 찍는다",
             r.returncode == OK and "후보 0건" in r.stdout and "if let · guard let" in r.stdout and "목록 밖" in r.stdout, r.stdout[-200:])
        r = subprocess.run([sys.executable, os.path.abspath(__file__), os.path.join(t, "none.swift")], capture_output=True, text=True)
        case("f004-missing-file-unrun — 없는 파일은 exit 2(0건으로 읽지 않는다)", r.returncode == UNRUN, (r.returncode, r.stderr[-120:]))
    print(f"self-test {passed}/{total} passed")
    return OK if passed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
