#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 저장소 · 파일만 읽는다.
"""call_set_diff.py — 레거시 파일 대비 신규 파일의 외부 호출 집합 차를 낸다.

왜(F-126): 레거시를 대체하는 신규 구현이 레거시가 하던 일 3건을 빠뜨렸고, 그 코드가 옆 파일에 살아 있었다. 대체 Step 은
'새 파일이 돈다' 만 보고 '옛 파일이 하던 호출을 다 하는가' 를 보지 않았다. fixture: A 가 `x.foo()` `x.bar()` 를 부르고
B 가 `x.foo()` 만 부르면 `bar` 를 가리켜야 한다.

외부 호출 = 멤버 호출 `.name(` 과 그 파일에서 정의하지 않은 자유 함수 호출 `name(`. 주석 · 문자열 안은 뺀다.
⛔ 범위: 두 파일의 호출 집합만 본다. 대체 대상의 분기 · 형제 진입점(기기 · 상태 분기) 대조는 범위 밖이다 — 사람이 본다.

사용: call_set_diff.py OLD NEW | --self-test
출력: `LEGACY-ONLY <이름>` · `NEW-ONLY <이름>` · 끝 줄 `call-set: legacy=<n> new=<n> legacy-only=<n> new-only=<n>`
exit: 0 레거시 호출이 신규에 다 있다 · 1 LEGACY-ONLY 있음(옮겼는지 · 일부러 뺐는지 Step 기록에 적는다) · 2 UNRUN(파일 없음)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

OK, DIFF, UNRUN = 0, 1, 2
KEYWORDS = {"if", "for", "while", "switch", "guard", "return", "catch", "elif", "print", "func", "def", "function", "fun",
            "init", "super", "self", "new", "typeof", "sizeof", "await", "try", "with", "assert", "lambda", "case", "when",
            "repeat", "defer", "throw", "throws", "rethrows", "in", "is", "as", "not", "and", "or", "let", "var", "val",
            "const", "class", "struct", "enum", "protocol", "extension", "import", "where", "some", "any"}
STRING = r'"""[\s\S]*?"""|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'|`(?:\\.|[^`\\])*`'
COMMENT = r"/\*[\s\S]*?\*/|//[^\n]*|^\s*#[^\n]*"
# 문자열과 주석을 한 번에 훑는다 — 먼저 시작한 쪽이 이긴다. 주석을 먼저 지우면 문자열 속 `//`(URL)가 뒤 호출까지 지운다
LEXEME = re.compile(f"(?P<s>{STRING})|(?P<c>{COMMENT})", re.M)
MEMBER = re.compile(r"\.([A-Za-z_]\w*)\s*(?:\(|\{)")
FREE = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*\(")
DEF = re.compile(r"\b(?:func|def|function|fun|fn)\s+([A-Za-z_]\w*)")


def calls(src: str) -> set[str]:
    body = LEXEME.sub(lambda m: '""' if m.group("s") else "", src)
    defined = set(DEF.findall(body))
    out = {f".{m}" for m in MEMBER.findall(body)}
    out |= {m for m in FREE.findall(body) if m not in KEYWORDS and m not in defined and not m[0].isupper()}
    return out


def run(old: Path, new: Path) -> int:
    for p in (old, new):
        if not p.is_file():
            print(f"UNRUN: 파일이 없다 — {p} (⛔ 통과 아님)")
            return UNRUN
    a = calls(old.read_text(encoding="utf-8", errors="replace"))
    b = calls(new.read_text(encoding="utf-8", errors="replace"))
    for x in sorted(a - b):
        print(f"LEGACY-ONLY {x}")
    for x in sorted(b - a):
        print(f"NEW-ONLY {x}")
    print(f"call-set: legacy={len(a)} new={len(b)} legacy-only={len(a - b)} new-only={len(b - a)}")
    return DIFF if a - b else OK


def self_test() -> int:
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    def case(name, old_src, new_src, want_rc, want_only=None):
        nonlocal passed
        with tempfile.TemporaryDirectory() as d:
            o, n = Path(d) / "Old.swift", Path(d) / "New.swift"
            o.write_text(old_src, encoding="utf-8")
            n.write_text(new_src, encoding="utf-8")
            with open(os.devnull, "w") as null:
                keep, sys.stdout = sys.stdout, null
                try:
                    rc = run(o, n)
                finally:
                    sys.stdout = keep
            only = sorted(calls(old_src) - calls(new_src))
        if rc == want_rc and (want_only is None or only == want_only):
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(f"{name}: exit {rc} (기대 {want_rc}) · legacy-only {only} (기대 {want_only})")

    legacy = "func run(x: X) {\n  x.foo()\n  x.bar()\n  log(\"done\")\n}\n"
    case("f126-call-set-diff", legacy, "func run(x: X) {\n  x.foo()\n  log(\"done\")\n}\n", DIFF, [".bar"])
    case("f126-same-calls-ok", legacy, "func start(x: X) {\n  log(\"done\")\n  x.bar()\n  x.foo()\n}\n", OK, [])
    case("f126-comment-string-ignored", legacy, "func run(x: X) {\n  x.foo()\n  // x.bar() 는 아래에서\n  let s = \"x.qux()\"\n  x.bar()\n  log(\"done\")\n}\n", OK, [])
    case("f126-url-string-not-comment", "func run(c: C) {\n  c.foo(\"https://host\"); c.bar()\n}\n", "func run(c: C) {\n  c.foo(\"https://host\")\n}\n", DIFF, [".bar"])
    case("f126-local-def-not-external", "func helper() {}\nfunc run() {\n  helper()\n}\n", "func run() {\n}\n", OK, [])
    with tempfile.TemporaryDirectory() as d:
        with open(os.devnull, "w") as null:
            keep, sys.stdout = sys.stdout, null
            try:
                rc = run(Path(d) / "absent.swift", Path(d) / "absent2.swift")
            finally:
                sys.stdout = keep
    if rc == UNRUN:
        passed += 1
        if listing:
            print("PASS f126-missing-file-unrun")
    else:
        fails.append(f"f126-missing-file-unrun: exit {rc}")

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("old", nargs="?", type=Path)
    ap.add_argument("new", nargs="?", type=Path)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.old or not a.new:
        print("UNRUN: OLD NEW 두 파일이 필요하다 (⛔ 통과 아님)")
        return UNRUN
    return run(a.old, a.new)


if __name__ == "__main__":
    sys.exit(main())
