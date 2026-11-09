#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 보고 파일만 읽는다.
"""check_unmeasured_handoff.py — 자동화하지 못해 남긴 시나리오가 사람 손 확인으로 넘어갔는지 대조한다(F-524).

왜: 자동 조작이 안 되는 화면의 시나리오를 `[미측정: 자동화 불가]` 로만 두고 PR 전에 사람에게 확인을 요청하지 않았다 —
팀원이 바로 그 구역에서 결함을 찾았다. '측정 못 함' 은 끝이 아니라 넘길 일이다.

판정: 보고 안 `[미측정: 자동화 불가 …]` 항목마다 같은 항목(같은 목록 항목 · 문단) 안에 수동 이관 줄이 있어야 한다 —
  `수동 이관: 요청 <누구에게 · 언제>` · `수동 이관: 결과 <통과|실패 — 근거>` · `수동 이관: 거절 <사유>` 중 하나.
  `[미측정:` 의 다른 사유(측정 도구 없음 등)는 이 검사 밖이다.

사용: check_unmeasured_handoff.py FILE... | --self-test
exit: 0 전부 이관됨(또는 대상 0) · 1 이관 없는 항목 있음 · 2 파일을 못 읽음(⛔ 통과 아님)
"""
import os
import re
import sys
import tempfile

UNMEASURED = re.compile(r"\[미측정:\s*자동화 불가")
HANDOFF = re.compile(r"수동 이관\s*[:：]\s*(요청|결과|거절)\s*\S")


def items(text):
    """목록 항목(줄머리 `-` · `*` · `N.`)과 그 들여쓴 이어짐 줄, 빈 줄로 끊긴 문단을 한 항목으로 묶는다."""
    out, cur, start = [], [], 0
    for i, line in enumerate(text.split("\n"), 1):
        head = re.match(r"^\s{0,3}(?:[-*+]|\d+[.)])\s", line)
        if not line.strip() or (head and cur):
            if cur:
                out.append((start, "\n".join(cur)))
            cur = []
            if not line.strip():
                continue
        if not cur:
            start = i
        cur.append(line)
    if cur:
        out.append((start, "\n".join(cur)))
    return out


def scan(files, out=sys.stdout):
    total, bad, unread = 0, [], []
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            unread.append(f"{f}: {type(e).__name__}")
            continue
        for start, block in items(text):
            if UNMEASURED.search(block):
                total += 1
                if not HANDOFF.search(block):
                    bad.append(f"{f}:{start}: {block.strip().splitlines()[0][:100]}")
    for b in bad:
        print(f"NO-HANDOFF {b} — 수동 이관(요청 · 결과 · 거절) 줄이 없다", file=out)
    for u in unread:
        print(f"UNRUN {u} (⛔ 통과 아님)", file=out)
    print(f"unmeasured-handoff: unmeasured={total} without-handoff={len(bad)}", file=out)
    if unread:
        return 2
    return 1 if bad else 0


def self_test():
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    class Sink:
        def __init__(self):
            self.text = ""

        def write(self, s):
            self.text += s

    def check(name, cond, got):
        nonlocal passed
        if cond:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(name)
            print(f"FAIL {name}: {got}")

    with tempfile.TemporaryDirectory(prefix="fz-unmeasured-") as d:
        def put(name, body):
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            return p

        left = put("left.md", "## 시나리오\n- V4 접힌 상태 끌기 — 통과\n- V5 펼친 상태 회전 + 탭 [미측정: 자동화 불가 — 안쪽 화면 탭 불가]\n"
                              "- V6 반접 [미측정: 자동화 불가 — 각도 고정 불가]\n  수동 이관: 요청 리뷰어에게 · 11-09\n")
        done = put("done.md", "- V5 [미측정: 자동화 불가 — 탭 불가]\n  수동 이관: 결과 통과 — 사람 녹화 확인\n\n"
                              "- V6 [미측정: 자동화 불가]\n  수동 이관: 거절 기기 없음 — 다음 판\n\n"
                              "- V7 [미측정: 측정 도구 없음]\n")
        s1, s2, s3 = Sink(), Sink(), Sink()
        rc1, rc2 = scan([left], s1), scan([done], s2)
        check("f524-unmeasured-without-handoff", rc1 == 1 and "V5 펼친 상태" in s1.text and "V6 반접" not in s1.text and rc2 == 0
              and "unmeasured=2 without-handoff=0" in s2.text, f"{rc1} {rc2} {s1.text.strip()} | {s2.text.strip()}")
        check("unreadable-unrun", scan([os.path.join(d, "none.md")], s3) == 2, s3.text)
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    if not argv:
        print("usage: check_unmeasured_handoff.py FILE... | --self-test", file=sys.stderr)
        return 2
    return scan(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
