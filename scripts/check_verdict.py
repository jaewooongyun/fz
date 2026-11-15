#!/usr/bin/env python3
"""check verdict contract 판정 — GPT check(리뷰 모드 자유 서식) 출력 → pass · warn · fail · unrun (F-581).

  fail   `[P0]` · `[P1]` 머리, 또는 한 줄에 severity 와 critical · major
  warn   `[P2]` · `[P3]` 머리, 또는 한 줄에 severity 와 minor · suggestion
  pass   위가 하나도 없고, 지적이 없다는 문장이 있을 때만
  unrun  그 밖 — 파일 없음 · 빈 파일 · 판정 신호가 없는 본문. 못 읽은 출력을 지적 0 으로 읽지 않는다(호출자는 본문을 읽는다)
severity 낱말만 보던 옛 판정 grep 은 리뷰 모드의 `[P2]` 머리를 보지 못해 지적 6건이 든 출력을 pass 로 읽었다(F-581).

사용: check_verdict.py FILE   (stdout 한 줄 = verdict — 호출자는 이 글자로 분기한다 · exit 0 · 사용법 오류만 exit 2)
      check_verdict.py --self-test
"""
# lint:no-root-anchor — 판정할 파일은 인자로 받는다(플러그인 루트를 추론하지 않는다)
from __future__ import annotations

import pathlib
import re
import sys
import tempfile

P_TAG = re.compile(r"(?m)^\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*)?\[P([0-3])\]")   # 지적 머리 자리만 — 요약 · 설명 속 `[P0]` 언급은 지적이 아니다
SEV_FAIL = re.compile(r"severity.*\b(critical|major)\b", re.I)
SEV_WARN = re.compile(r"severity.*\b(minor|suggestion)\b", re.I)
NO_FINDINGS = re.compile(r"\bno (?:issues|findings|problems|defects)\b|\bdid(?: not|n't) find\b|\bnothing to (?:report|flag)\b"
                         r"|지적(?:이|할 것이|사항이)? 없|문제(?:가|를)? (?:발견하지 못|없)|발견(?:된|한) (?:문제|이슈|지적)(?:가|이|는)? 없", re.I)


def verdict(text) -> str:
    if not isinstance(text, str) or not text.strip():
        return "unrun"
    tags = {int(m.group(1)) for m in P_TAG.finditer(text)}
    if tags & {0, 1} or any(SEV_FAIL.search(ln) for ln in text.splitlines()):
        return "fail"
    if tags & {2, 3} or any(SEV_WARN.search(ln) for ln in text.splitlines()):
        return "warn"
    return "pass" if NO_FINDINGS.search(text) else "unrun"


def judge_file(path) -> str:
    try:
        return verdict(pathlib.Path(path).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return "unrun"


def self_test() -> int:
    res = []

    def case(name, ok, got=""):
        res.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    p2 = "".join(f"- [P2] 제목 {i} — scripts/a.py:{i}\n  설명\n" for i in range(6))   # F-581 원사건 꼴(지적 6 · severity 낱말 0)
    got = [verdict(p2), verdict("- [P1] 막는 지적 — a.py:1\n" + p2), verdict("issue: x\nseverity: major\n"),
           verdict("severity: suggestion\n")]
    case("r3-f581-p-tags-not-pass — 리뷰 모드 [P0]~[P3] 머리를 센다([P0] · [P1] = fail · [P2] · [P3] = warn) · severity 낱말 판정은 그대로",
         got == ["warn", "fail", "fail", "warn"], got)
    with tempfile.TemporaryDirectory() as t:
        empty = pathlib.Path(t) / "e.md"
        empty.write_text("", encoding="utf-8")
        got = [judge_file(pathlib.Path(t) / "none.md"), judge_file(empty), verdict("The change looks reasonable overall.\n"),
               verdict("No issues found.\n"), verdict("검토 결과 지적할 것이 없습니다.\n")]
    case("r3-f581-unreadable-unrun — 파일 없음 · 빈 파일 · 판정 신호 없는 본문은 unrun(지적 0 으로 읽지 않는다) · 지적 없음 문장만 pass",
         got == ["unrun", "unrun", "unrun", "pass", "pass"], got)
    got = [verdict("No findings. No [P0] or [P1] issues were found.\n"), verdict("Summary: no [P0] or [P1].\n- [P2] 제목 — a.py:1\n"),
           verdict("1. [P1] 제목 — a.py:1\n"), verdict("- **[P0]** 제목 — a.py:1\n"), verdict("  - [P3] 제목\n")]
    case("r3-f581-p-tag-header-only — [P0]~[P3] 는 지적 머리 자리(줄머리 · 목록 표지 뒤)만 센다 · 요약 · 설명 속 언급은 지적이 아니다(GPT check r7 P2)",
         got == ["pass", "warn", "fail", "fail", "warn"], got)
    print(f"self-test {sum(res)}/{len(res)} passed (check_verdict)")
    return 0 if all(res) else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--self-test"]:
        return self_test()
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[-2].strip())
        return 2
    print(judge_file(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
