#!/usr/bin/env python3
# diff-parse: not-a-diff — `startswith("-")` 는 mktemp 인자의 옵션 토큰(-t · -p)을 가르는 데만 쓴다. diff 를 파싱하지 않는다
"""check_external_commands.py — 문서가 호출을 지시하는 **외부 명령이 실재하는가** (B4 / v7 S3).

왜: 스킬·모듈이 GPT CLI 호출 같은 외부 명령을 절차로 적어 두는데, 그 명령이 설치돼
있지 않으면 절차 전체가 런타임에 죽는다. 그런데 문서는 초록으로 보인다 — 문서가 도구의
실재를 아는 방법이 없기 때문이다.

⛔ **술어를 좁힌다.** 코드블록 첫 토큰을 전부 명령으로 보면 오탐이 쏟아진다 —
실측(2026-09-21): `import`(Python) · `elif`(셸 키워드) · `init_or_use_session`(문서 내 함수)이
후보 15종 중 3종을 차지했다. 그래서 **선언 목록**(`DECLARED`)을 정본으로 두고,
문서 스캔은 *선언에 없는 새 명령이 등장했는지* 만 본다(fail-closed).

셸 위험 두 축 (운영 스크립트 scripts/ · skills/*/scripts/ · .githooks/ + 문서 bash 블록 — 위반이면 exit 1):
  awk-nonascii     awk 프로그램이 비ASCII 문자열 리터럴을 == · != 로 비교하는데 그 줄에 `LC_ALL=C` 가 없다(F-389 —
                   macOS BSD awk 가 UTF-8 로캘에서 서로 다른 한글 문자열을 같다고 판정한다. 정규식 `~ /^…$/` 은 바르다)
  mktemp-template  `mktemp -d` 에 템플릿(위치 인자)도 `-p` 도 없다(F-403 — Darwin 은 TMPDIR 을 무시하고 /var/folders 에
                   만든다. `-t` 만 줘도 같다). 명시 템플릿 `mktemp -d "${TMPDIR:-/tmp}/<이름>.XXXXXX"` 을 쓴다
  tests/fixtures 의 `mktemp -d` 는 개수만 보고한다(격리를 TMPDIR 에 맡기는 주장이 없는 시험 자료)

exit code:
  0  PASS — 선언된 필수 명령이 전부 실재 · 미선언 신규 명령 0
  1  VIOLATION — 필수 명령 부재 또는 미선언 명령 등장
  2  UNRUN — 스캔 대상 0건 등 판정 불가. ⛔ 통과로 읽지 않는다

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
# ⛔ N6 루트 앵커 — lint_contracts ANCHOR_LINES 허용 형태와 정확히 일치
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT_DIR_PARENT = pathlib.Path(__file__).resolve().parent.parent   # scripts/ → 플러그인 루트

# ⛔ **선언 목록이 정본이다.** 새 외부 명령을 문서에 쓰면 여기에 먼저 추가한다.
#    required=True 는 부재 시 절차가 죽는 것, False 는 있으면 좋은 것.
# ⛔ **하드코딩하지 않는다** — 목록이 소비자마다 흩어지면 한 곳만 고쳐진다(N4).
#    단일 출처: `schemas/tool-inventory.json` (`lint_contracts` #12 · S6 · S20 이 같은 파일을 읽는다).
def _declared() -> dict:
    """{명령: required}. ⛔ 부재·파싱 실패는 **예외**다 — 빈 dict 로 폴백하면
    선언이 0건이 되어 '미선언 명령 0건' 으로 조용히 통과한다."""
    import json
    q = SCRIPT_DIR_PARENT / "schemas" / "tool-inventory.json"
    try:
        with open(q, "r", encoding="utf-8") as fh:
            inv = json.load(fh)
        return {k: bool(vv.get("required", False)) for k, vv in inv["external_commands"].items()}
    except (OSError, ValueError, KeyError) as e:
        # ⛔ exit 2 = 측정 실패. 빈 선언으로 넘기면 '미선언 0건' 으로 조용히 통과한다.
        print(f"⛔ 도구 인벤토리를 읽지 못했다 — {q}: {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(2)


DECLARED = _declared()
# ⛔ 명령이 아닌 것 — 언어 키워드·문서 내 함수. 스캔 오탐의 실측 원인이다.
NOT_A_COMMAND = {
    "import", "from", "elif", "else", "return", "print", "def", "class", "with", "try",
    "except", "raise", "assert", "lambda", "yield", "await", "async", "pass", "break",
    "continue", "global", "nonlocal", "for", "while", "if", "then", "fi", "done", "case",
    "esac", "export", "set", "read", "local", "exit", "source", "echo", "function", "eval",
    "do",
}
# ⛔ POSIX 기본 유틸 — 명령이지만 선언·실존 확인 대상이 아니다. 인벤토리에 넣으면 `shutil.which` 를 거치는데
#    `cd` 는 셸 내장이라 실행 파일이 없는 환경(Linux)에서 필수 부재로 FAIL 한다(EC-33). 그래서 스캔에서 걷는다.
POSIX_UTILS = {"cd", "ls", "cp", "mv", "rm", "wc", "tr", "sh"}
CODE_BLOCK = re.compile(r"```(?:bash|sh|shell)\n(.*?)```", re.S)
# ⛔ 2글자 명령도 본다(F-379). `{2,}`(3글자 이상)는 `rg`·`fd`·`ag`·`gh` 를 구조적으로 못 봤다 —
#    AC8 의 `rg` 의존(F-224)이 이 사각으로 통과했다. 2글자 셸 키워드(`if`·`fi`·`do`)는 NOT_A_COMMAND 가 걷는다
FIRST_TOKEN = re.compile(r"^\s*(?:\$ )?([a-z][a-z0-9_.-]{1,})\s", re.M)
SCAN_GLOBS = ("skills/*/SKILL.md", "modules/*.md", "guides/*.md")
SHELL_GLOBS = ("scripts/*.sh", "skills/*/scripts/*.sh", ".githooks/*")
FIXTURE_SHELL_GLOB = "tests/fixtures/**/*.sh"
FIXTURE_SKIP = {"tests/fixtures/lint/empty-cd-mktemp/run.sh"}   # N14 lint 시험 자료 — mktemp 꼴을 일부러 담는다
AWK_WORD = re.compile(r"\bawk\b")
NONASCII_CMP = re.compile(r'(?:==|!=)\s*"[^"\n]*[^\x00-\x7f][^"\n]*"|"[^"\n]*[^\x00-\x7f][^"\n]*"\s*(?:==|!=)')
MKTEMP = re.compile(r"\bmktemp\b([^)\n;|&`]*)")


def log(*a):
    print(*a, file=sys.stderr)


def scan_commands(root: pathlib.Path):
    """문서 코드블록의 첫 토큰 중 **명령일 수 있는 것**만. (집합, 스캔 파일 수)"""
    found, n = set(), 0
    for g in SCAN_GLOBS:
        for q in sorted(root.glob(g)):
            n += 1
            for blk in CODE_BLOCK.findall(q.read_text(encoding="utf-8")):
                for m in FIRST_TOKEN.finditer(blk):
                    tok = m.group(1)
                    if tok in NOT_A_COMMAND or tok in POSIX_UTILS:
                        continue
                    if "_" in tok:          # 문서 내 함수 관례 (init_or_use_session)
                        continue
                    found.add(tok)
    return found, n


def _strip_comments(text: str) -> str:
    """줄 전체가 주석인 줄을 빈 줄로 — 줄 번호는 지킨다. 주석 속 예시(템플릿 없는 `mktemp -d` 경고문)는 호출이 아니다."""
    return "\n".join("" if ln.lstrip().startswith("#") else ln for ln in text.split("\n"))


def shell_hazards(text: str):
    """(awk 위반 줄들, mktemp 위반 줄들) — 줄 번호 목록."""
    awk, mk = [], []
    for m in AWK_WORD.finditer(text):
        # 같은 명령(따옴표 밖 줄바꿈까지)의 작은따옴표 구간을 모두 본다 — `-F'\t'` 같은 옵션 인자도 따옴표를 쓴다
        i, segs = m.end(), []
        while i < len(text) and text[i] != "\n":
            if text[i] == "'":
                j = text.find("'", i + 1)
                if j < 0:
                    break
                segs.append(text[i + 1:j])
                i = j + 1
                continue
            i += 1
        head = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
        if any(NONASCII_CMP.search(s) for s in segs) and "LC_ALL=C" not in head:
            awk.append(text.count("\n", 0, m.start()) + 1)
    for m in MKTEMP.finditer(text):
        toks = m.group(1).split()
        if not any(re.fullmatch(r"-[a-zA-Z]*d[a-zA-Z]*", t) for t in toks):
            continue
        rest, skip = [], False
        for t in toks:
            if skip:
                skip = False
                continue
            if t in ("-t", "-p"):
                skip = t == "-t"
                if t == "-p":
                    rest.append("-p")
                continue
            if not t.startswith("-"):
                rest.append(t)
        if not rest:
            mk.append(text.count("\n", 0, m.start()) + 1)
    return awk, mk


def scan_shell(root: pathlib.Path):
    """(위반 목록, fixture mktemp 보고 수). 운영 스크립트 + 문서 bash 블록은 위반 · fixture 는 보고만."""
    viol, n_fixture = [], 0
    targets = []
    for g in SHELL_GLOBS:
        targets += [q for q in sorted(root.glob(g)) if q.is_file()]
    for q in targets:
        rel = q.relative_to(root).as_posix()
        awk, mk = shell_hazards(_strip_comments(q.read_text(encoding="utf-8", errors="replace")))
        viol += [f"{rel}:{n}: awk-nonascii" for n in awk] + [f"{rel}:{n}: mktemp-template" for n in mk]
    for g in SCAN_GLOBS:
        for q in sorted(root.glob(g)):
            rel = q.relative_to(root).as_posix()
            for blk in CODE_BLOCK.findall(q.read_text(encoding="utf-8")):
                awk, mk = shell_hazards(_strip_comments(blk))
                viol += [f"{rel}(bash 블록): awk-nonascii" for _ in awk] + [f"{rel}(bash 블록): mktemp-template" for _ in mk]
    for q in sorted(root.glob(FIXTURE_SHELL_GLOB)):
        if q.relative_to(root).as_posix() not in FIXTURE_SKIP:
            n_fixture += len(shell_hazards(_strip_comments(q.read_text(encoding="utf-8", errors="replace")))[1])
    return viol, n_fixture


def check(root: pathlib.Path):
    found, nfiles = scan_commands(root)
    if nfiles == 0:
        log(f"UNRUN: 스캔 대상 문서가 0건 — {root} (측정 실패를 먼저 의심한다)")
        return UNRUN

    missing_required = [c for c, req in DECLARED.items() if req and not shutil.which(c)]
    missing_optional = [c for c, req in DECLARED.items() if not req and not shutil.which(c)]
    undeclared = sorted(found - set(DECLARED))

    print(f"분모: 문서 {nfiles}개 · 선언 명령 {len(DECLARED)}종 · 문서 등장 {len(found)}종")
    print(f"  필수 부재                          : {len(missing_required)}")
    for c in missing_required:
        print(f"      {c}")
    print(f"  선택 부재(폴백 있음)                 : {len(missing_optional)}  {missing_optional or ''}")
    print(f"  미선언 명령(문서에만 등장)            : {len(undeclared)}")
    for c in undeclared:
        print(f"      {c} — DECLARED 에 추가하거나 NOT_A_COMMAND 로 분류하라")
    hazards, n_fixture = scan_shell(root)
    print(f"  셸 위험(awk 비ASCII 비교 · 템플릿 없는 mktemp -d) : {len(hazards)}")
    for h in hazards:
        print(f"      {h}")
    print(f"  (보고) fixture 의 템플릿 없는 mktemp -d      : {n_fixture}")

    if missing_required or undeclared or hazards:
        log(f"VIOLATION: 필수 부재 {len(missing_required)} · 미선언 {len(undeclared)} · 셸 위험 {len(hazards)}")
        return VIOLATION
    print("OK: 선언된 필수 명령이 전부 실재하고 미선언 명령이 없다")
    return OK


def self_test():
    """행동 fixture — 결함 상태에서 **실패**하고 수정 후 **통과**하는 쌍 (플랜 verify #5)."""
    import tempfile
    passed, failed, cases = [], [], 0

    def case(name, fn):
        nonlocal cases
        cases += 1
        with tempfile.TemporaryDirectory() as tmp:
            try:
                fn(pathlib.Path(tmp)); passed.append(name)
            except AssertionError as e:
                failed.append(f"{name}: {e}")
            except Exception as e:
                failed.append(f"{name}: ⛔ 예외 {type(e).__name__}: {e}")

    def mk(root, body, rel="skills/x/SKILL.md"):
        p2 = root / rel
        p2.parent.mkdir(parents=True, exist_ok=True)
        p2.write_text(body, encoding="utf-8")
        return root

    def c_clean_passes(tmp):
        r = mk(tmp / "r", "# x\n\n```bash\npython3 scripts/a.py\ngit status\n```\n")
        assert check(r) == OK, "선언된 명령만 쓰는데 실패했다"

    def c_undeclared_detected(tmp):
        r = mk(tmp / "r", "# x\n\n```bash\nkubectl apply -f a.yaml\n```\n")
        assert check(r) == VIOLATION, "⛔ 미선언 명령을 놓쳤다"

    def c_keyword_not_flagged(tmp):
        """⛔ 오탐 방어 — 실측 3종(`import`·`elif`·함수명)이 명령으로 잡히면 안 된다."""
        r = mk(tmp / "r", "# x\n\n```bash\nimport json\nelif true; then :; fi\n"
                          "init_or_use_session arg\n```\n")
        rc = check(r)
        assert rc == OK, f"⛔ 언어 키워드·함수명을 명령으로 오탐했다 (rc={rc})"

    def c_missing_required_detected(tmp):
        r = mk(tmp / "r", "# x\n\n```bash\npython3 a.py\n```\n")
        real = shutil.which

        def gone(c, *a, **k):
            return None if c == "git" else real(c, *a, **k)

        g = globals(); g["shutil"].which = gone
        try:
            rc = check(r)
        finally:
            g["shutil"].which = real
        assert rc == VIOLATION, f"⛔ 필수 명령 부재인데 rc={rc}"

    def c_optional_missing_is_not_violation(tmp):
        """⛔ `codex` 는 부재 시 폴백이 정의돼 있다 — 차단하면 안 된다."""
        r = mk(tmp / "r", "# x\n\n```bash\ncodex exec review\n```\n")
        real = shutil.which

        def gone(c, *a, **k):
            return None if c == "codex" else real(c, *a, **k)

        g = globals(); g["shutil"].which = gone
        try:
            rc = check(r)
        finally:
            g["shutil"].which = real
        assert rc == OK, f"⛔ 폴백 있는 선택 명령 부재를 차단했다 (rc={rc})"

    def c_no_docs_unrun(tmp):
        r = tmp / "empty"
        r.mkdir()
        assert check(r) == UNRUN, "⛔ 스캔 대상 0건이 통과했다 — 0건은 측정 실패를 먼저 의심"

    def c_non_bash_block_ignored(tmp):
        """bash 가 아닌 코드블록은 명령 스캔 대상이 아니다."""
        r = mk(tmp / "r", "# x\n\n```python\nkubectl_like_name = 1\n```\n\n```bash\ngit log\n```\n")
        assert check(r) == OK, "python 블록을 명령으로 읽었다"

    def c_two_letter_undeclared_detected(tmp):
        """⛔ F-379 — 2글자 미선언 명령(`fd`)을 놓치면 AC8 의 `rg` 의존 같은 사각이 다시 열린다."""
        r = mk(tmp / "r", "# x\n\n```bash\nfd -e md .\n```\n")
        assert check(r) == VIOLATION, "⛔ 2글자 미선언 명령을 놓쳤다"

    def c_two_letter_rg_reported(tmp):
        """⛔ F-379 오라클 — `rg foo` 한 줄짜리 bash 블록은 미설치(미선언) 명령으로 보고한다. rg 는 인벤토리에 넣지 않는다(넣으면 재유입이 통과한다)."""
        r = mk(tmp / "r", "# x\n\n```bash\nrg foo\n```\n")
        assert check(r) == VIOLATION, "⛔ rg 재유입을 놓쳤다"

    def c_posix_util_and_keyword_not_flagged(tmp):
        """⛔ 오탐 방어 — 2글자를 열면 POSIX 유틸·셸 키워드 `do` 가 미선언으로 잡힌다(EC-33)."""
        r = mk(tmp / "r", "# x\n\n```bash\ncd /tmp\nls -l\ncp a b\nfor f in a; do\n  rm -f \"$f\"\ndone\n```\n")
        rc = check(r)
        assert rc == OK, f"⛔ POSIX 유틸·셸 키워드를 미선언 명령으로 오탐했다 (rc={rc})"

    def c_awk_nonascii(tmp):
        r = mk(tmp / "r", "# x\n")
        mk(r, "#!/bin/bash\nawk -F'\\t' '$3 == \"연기\" {print}' f.tsv\n", "scripts/a.sh")
        assert check(r) == VIOLATION, "⛔ LC_ALL=C 없는 비ASCII awk 비교를 놓쳤다"

    def c_awk_lc_all_ok(tmp):
        r = mk(tmp / "r", "# x\n")
        mk(r, "#!/bin/bash\nLC_ALL=C awk -F'\\t' '$3 == \"연기\" {print}' f.tsv\nawk '$3 ~ /^연기$/' f.tsv\n", "scripts/a.sh")
        assert check(r) == OK, "LC_ALL=C 접두 · 정규식 비교를 위반으로 읽었다"

    def c_mktemp_no_template(tmp):
        r = mk(tmp / "r", "# x\n")
        mk(r, "#!/bin/bash\nT=\"$(mktemp -d)\" || exit 1\n", "skills/s/scripts/a.sh")
        assert check(r) == VIOLATION, "⛔ 템플릿 없는 mktemp -d 를 놓쳤다"

    def c_mktemp_template_ok(tmp):
        r = mk(tmp / "r", "# x\n")
        mk(r, '#!/bin/bash\n# 주석: 템플릿 없는 mktemp -d 는 쓰지 않는다\nT="$(mktemp -d "${TMPDIR:-/tmp}/x.XXXXXX")"\nU="$(mktemp -d -p "$TMPDIR")"\n', "scripts/a.sh")
        assert check(r) == OK, "명시 템플릿 · -p · 주석을 위반으로 읽었다"

    def c_mktemp_t_only(tmp):
        r = mk(tmp / "r", "# x\n")
        mk(r, "#!/bin/bash\nT=\"$(mktemp -d -t fz)\"\n", "scripts/a.sh")
        assert check(r) == VIOLATION, "⛔ -t 만 준 mktemp -d 를 놓쳤다(Darwin 은 TMPDIR 을 무시한다)"

    def c_fixture_reported_only(tmp):
        r = mk(tmp / "r", "# x\n")
        mk(r, "#!/bin/bash\nT=\"$(mktemp -d)\"\n", "tests/fixtures/x/run.sh")
        assert check(r) == OK, "fixture 의 mktemp 는 보고만 한다"

    for n, f in [("f389-awk-nonascii", c_awk_nonascii), ("f389-awk-lc-all-ok", c_awk_lc_all_ok),
                 ("f403-mktemp-no-template", c_mktemp_no_template), ("f403-mktemp-template-ok", c_mktemp_template_ok),
                 ("f403-mktemp-t-only", c_mktemp_t_only), ("f403-fixture-reported-only", c_fixture_reported_only),
                 ("clean-passes", c_clean_passes),
                 ("undeclared-detected", c_undeclared_detected),
                 ("keyword-not-flagged", c_keyword_not_flagged),
                 ("missing-required-detected", c_missing_required_detected),
                 ("optional-missing-ok", c_optional_missing_is_not_violation),
                 ("no-docs-unrun", c_no_docs_unrun),
                 ("non-bash-block-ignored", c_non_bash_block_ignored),
                 ("two-letter-undeclared-detected", c_two_letter_undeclared_detected),
                 ("two-letter-rg-reported", c_two_letter_rg_reported),
                 ("posix-util-keyword-not-flagged", c_posix_util_and_keyword_not_flagged)]:
        case(n, f)

    print(f"self-test {len(passed)}/{cases} 통과")
    for x in passed:
        print(f"  ok   {x}")
    for x in failed:
        print(f"  FAIL {x}")
    return OK if not failed else VIOLATION


def main():
    ap = argparse.ArgumentParser(description="외부 명령 실존 검사 (B4 / S3)")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(SCRIPT_DIR).parent)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else check(a.root)


if __name__ == "__main__":
    sys.exit(main())
