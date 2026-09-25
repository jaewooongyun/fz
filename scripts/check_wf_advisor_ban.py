#!/usr/bin/env python3
# lint:no-root-anchor — 루트를 `--root` 로 받는다(기본값은 이 파일 기준 부모 상수).
"""모든 워크플로의 `OVERRIDE` 상수에 advisor 금지 문구가 들어 있는지 검사한다 (A-ADV).

⛔ 왜 필요한가: 워커(서브에이전트)는 세션 `advisorModel` 을 **상속**하고, 끄는 네이티브 수단이
   없다 — 공식: *"Subagents inherit the configured advisor and apply the same pairing check
   against their own model"* (code.claude.com/docs/en/advisor, 2026-09-22 대조). 억제 수단은
   각 워크플로 프롬프트의 문구뿐인데, `guides/skill-authoring.md` §12 표준에 문구가 없던 동안
   워크플로 8개 중 4개가 누락했다(2026-09-25 실측). 표준을 고쳐도 새 워크플로가 다시 빠뜨릴
   수 있으므로 **재발을 막는 것은 절차가 아니라 검사**다.

⛔ 이 검사는 문구 **누락** 검사다 — 억제 **효과**는 `fz_wf_metrics.py --wf <runId>` 의 advisor 카운트로 본다(관측 요약: modules/governance.md 운용 규칙 5).

판정은 **블록 단위**다 — 파일 어디에든 문구가 있으면 통과시키지 않는다. 주석이나 쓰이지 않는
문자열에 있으면 워커 프롬프트에 실리지 않는다.

  `const OVERRIDE` 로 시작해 `+`·`=` 로 끝나는 줄이 이어지는 동안을 한 블록으로 본다
  블록 안에 금지 문구가 있어야 한다 · 블록이 없는 워크플로도 위반이다

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님 — 워크플로 0개는 "위반 0건" 이 아니다)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PHRASE = "advisor 도 호출하지 않는다"


def override_block(text: str) -> str | None:
    """`const OVERRIDE` 상수의 소스 블록을 돌려준다. 없으면 None."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("const OVERRIDE"):
            block = [line]
            j = i
            while block[-1].rstrip().endswith(("+", "=")) and j + 1 < len(lines):
                j += 1
                block.append(lines[j])
            return "\n".join(block)
    return None


STRING = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`")


def literal_text(block: str) -> str:
    """블록의 **문자열 리터럴 내용**만 잇는다 — 연결(+) 사이에 낀 주석은 워커 프롬프트에 실리지 않는다."""
    return "".join(next(g for g in m.groups() if g is not None) for m in STRING.finditer(block))


def check(root: pathlib.Path) -> tuple[int, list[str], int]:
    files = sorted((root / "workflows").glob("*.js"))
    if not files:
        return UNRUN, [f"워크플로 0개 — {root / 'workflows'} (경로 확인)"], 0
    bad = []
    for f in files:
        block = override_block(f.read_text(encoding="utf-8"))
        if block is None:
            bad.append(f"{f.name}: OVERRIDE 상수 없음")
        elif PHRASE not in literal_text(block):
            bad.append(f"{f.name}: OVERRIDE 블록에 금지 문구 없음")
    return (VIOLATION if bad else OK), bad, len(files)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    code, bad, n = check(a.root)
    if code == UNRUN:
        print(f"UNRUN: {bad[0]}")
    elif code == VIOLATION:
        for b in bad:
            print(f"VIOLATION {b}")
        print(f"advisor-ban: {n - len(bad)}/{n} workflows")
    else:
        print(f"advisor-ban: {n}/{n} workflows")
    return code


def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []

    def case(name, sources, want):
        nonlocal passed
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-adv-"))
        try:
            if sources is not None:
                (d / "workflows").mkdir()
                for fname, body in sources.items():
                    (d / "workflows" / fname).write_text(body, encoding="utf-8")
            got, _, _ = check(d)
            if got == want:
                passed += 1
            else:
                fails.append(f"{name}: want {want} got {got}")
        finally:
            shutil.rmtree(d)

    inside = "const OVERRIDE =\n  'a. ' +\n  'b. ⛔ advisor 도 호출하지 않는다. 끝.'\nconst X = 1\n"
    comment = "// ⛔ advisor 도 호출하지 않는다\nconst OVERRIDE =\n  'a. ' +\n  'b. 끝.'\n"
    after = "const OVERRIDE =\n  'a. ' +\n  'b. 끝.'\nconst NOTE = '⛔ advisor 도 호출하지 않는다'\n"
    # ① 블록 안 → 충족
    case("inside-block", {"a.js": inside}, OK)
    # ② ⛔ 주석에만 → 위반 (파일 단위 grep 이면 통과했을 경우)
    case("comment-only", {"a.js": comment}, VIOLATION)
    # ③ ⛔ 블록 뒤의 다른 문자열 → 위반
    case("other-string", {"a.js": after}, VIOLATION)
    # ④ ⛔ OVERRIDE 상수 부재 → 위반
    case("no-override", {"a.js": "const X = 1\n"}, VIOLATION)
    # ⑤ ⛔ 하나라도 빠지면 위반 (나머지가 충족해도)
    case("one-missing", {"a.js": inside, "b.js": comment}, VIOLATION)
    # ⑦ ⛔ 연결 줄 사이에 낀 주석에만 → 위반 (블록 원문을 보면 통과했을 경우 — 외부 리뷰 지적)
    interleaved = "const OVERRIDE =\n  'a. ' +\n  // ⛔ advisor 도 호출하지 않는다\n  'b. 끝.'\n"
    case("comment-inside-block", {"a.js": interleaved}, VIOLATION)
    # ⑥ ⛔ 워크플로 0개 → **측정 실패**. 위반 0건으로 인쇄하지 않는다
    case("no-workflows", None, UNRUN)

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
