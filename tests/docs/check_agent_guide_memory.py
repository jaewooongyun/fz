#!/usr/bin/env python3
"""agent-team-guide §8.1 문서 계약 (S02) — memory 필드 금지의 **이유와 예외**가 가이드에 남아 있는가.

lint #N13 이 agents/·templates/ 의 필드를 막는다면, 이 검사는 그 규칙을 설명하는 문장이 지워지지 않게 한다
(규칙만 남고 이유가 사라지면 다음 편집자가 '학습 효과' 를 이유로 되살린다).
usage: check_agent_guide_memory.py GUIDE_MD | --self-test
exit: 0=충족 · 1=누락 · 2=파일 없음·§8.1 없음
"""
import re
import sys

NEED = (
    ("도구 자동 부여", r"Read/Write/Edit"),
    ("Workflow 쓰기 없음 계약과 충돌", r"쓰기 없음|디스크를 쓰지 않는"),
    ("A/B 입력 오염", r"A/B"),
    ("memory-curator 예외", r"memory-curator"),
    ("재유입 방지 lint", r"#N13"),
)


def section(text):
    m = re.search(r"^### 8\.1 .*$", text, re.M)
    if not m:
        return None
    nxt = re.search(r"^#{2,3} ", text[m.end():], re.M)
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text) - m.end())]


def check(text):
    sec = section(text)
    if sec is None:
        return None
    return [name for name, rx in NEED if not re.search(rx, sec)]


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[-3])
        return 2
    if sys.argv[1] == "--self-test":
        good = "### 8.1 X\n- Read/Write/Edit 자동 부여 · 쓰기 없음 계약 · A/B 오염 · memory-curator 예외 · #N13\n### 8.2 Y\n"
        cases = [(check(good) == []), (check(good.replace("memory-curator", "")) == ["memory-curator 예외"]),
                 (check("### 8.2 only\n") is None)]
        print(f"self-test {sum(cases)}/{len(cases)} passed")
        return 0 if all(cases) else 1
    try:
        text = open(sys.argv[1], encoding="utf-8").read()
    except OSError as e:
        print(f"UNRUN: {e}")
        return 2
    miss = check(text)
    if miss is None:
        print("UNRUN: §8.1 절이 없다")
        return 2
    for m in miss:
        print(f"  MISSING {m}")
    print(f"agent-guide §8.1: 필수 {len(NEED)} · 누락 {len(miss)}")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
