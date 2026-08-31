#!/usr/bin/env python3
# G8 문체 게이트 — `modules/explanation-protocol.md` §8.2 기계 검사의 **실행 가능한 부분**만 센다.
#
# ⛔ 4종 중 2종만 기계 판정한다. 나머지 둘("명사형 제목 — 서술어 없는 제목의 연속",
#    "장식 이모지 — 의미 없는 이모지")은 임계가 없는 **의미 판정**이라 여기서 SKIP 이다.
#    SKIP 은 PASS 가 아니다 — `lint_contracts.py` 와 같은 규약이다.
#
# ⛔ 신설 근거: fixture `negative-clean.md` 가 "오검출 0/8" 을 기대값으로 적어 두고
#    **한 번도 실행된 적이 없었다**. 실측하니 과잉 볼드가 3건 발화한다 — 기대값이 거짓이었다.
#    원인은 fixture 결함이 아니라 정본 충돌이었다(아래 라벨 볼드 예외 참조).
#
# ⛔ 라벨 볼드 예외: `modules/explanation-output.md` 의 매핑 블록 정본은 `**담당 코드**:`
#    형태의 볼드 라벨 5개를 한 문단에 두라고 규정한다. 그것을 강조로 세면 **정본을 지킬수록
#    게이트에 걸린다**. 줄머리 `**라벨**:` 은 구조 표시이지 강조가 아니므로 세지 않는다.
#
# diff-parse: not-a-diff — 이 파일의 `startswith("-")` 는 argv 플래그 판별이다.
#   diff 를 읽지 않으므로 hunk 안팎 구분이 필요 없다.
#
# 사용: check_g8_style.py [--self-test] [--fixture-check] [파일...]
# exit: 0 위반 0 / 1 위반 있음 / 2 실행 오류(파일 없음·읽기 실패)

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BOLD = re.compile(r"\*\*[^*\n]+\*\*")
LABEL_LINE = re.compile(r"^\s*\*\*[^*\n]+\*\*\s*:")   # 줄머리 라벨 — 강조 아님
DASH = "—"                                        # 줄표(em dash)

BOLD_MAX = 2      # "셋 이상" 이 위반 → 2 까지 허용
DASH_MAX = 1      # "둘 이상" 이 위반 → 1 까지 허용


def paragraphs(text):
    """코드펜스 밖의 문단을 (시작줄, [줄...]) 로 낸다."""
    out, buf, start, fence = [], [], 1, False
    for i, line in enumerate(text.split("\n"), 1):
        if line.lstrip().startswith("```"):
            if buf:
                out.append((start, buf))
            buf, start, fence = [], i + 1, not fence
            continue
        if fence:
            continue
        if not line.strip():
            if buf:
                out.append((start, buf))
            buf, start = [], i + 1
            continue
        if not buf:
            start = i
        buf.append(line)
    if buf:
        out.append((start, buf))
    return out


def check(path):
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    hits = []
    for start, buf in paragraphs(text):
        emphasis = 0
        for line in buf:
            n = len(BOLD.findall(line))
            if LABEL_LINE.match(line):
                n -= 1            # 줄머리 라벨 1개는 구조 표시로 제외
            emphasis += max(n, 0)
        if emphasis > BOLD_MAX:
            hits.append((start, "과잉 볼드", "%d개(강조 기준)" % emphasis))
        dashes = sum(line.count(DASH) for line in buf)
        if dashes > DASH_MAX:
            hits.append((start, "줄표 남용", "%d개" % dashes))
    return hits


SELF_TESTS = (
    ("강조 볼드 3개 → 위반", "**a** **b** **c** 문장\n", 1),
    ("강조 볼드 2개 → 통과", "**a** **b** 문장\n", 0),
    ("라벨 볼드 5줄 → 통과(정본 매핑 블록)",
     "**담당 코드**: x\n**하는 일**: y\n**없으면**: z\n**왜 여기인가**: w\n**상태**: s\n", 0),
    ("라벨 4줄 + 본문 강조 3개 → 위반",
     "**담당 코드**: x\n**하는 일**: y\n**없으면**: z\n본문 **a** **b** **c**\n", 1),
    ("코드펜스 안은 세지 않는다",
     "```\n**a** **b** **c** **d**\n```\n", 0),
    ("줄표 2개 → 위반", "문장 — 다음 — 또\n", 1),
    ("줄표 1개 → 통과", "문장 — 다음\n", 0),
    ("빈 줄이 문단을 가른다",
     "**a** **b**\n\n**c** **d**\n", 0),
)


def self_test():
    import tempfile
    bad = 0
    for name, body, expect in SELF_TESTS:
        fd, p = tempfile.mkstemp(suffix=".md")
        try:
            with io.open(fd, "w", encoding="utf-8") as fh:
                fh.write(body)
            got = len(check(p))
            ok = (got > 0) == (expect > 0)
            print("%s  %s (기대 %s / 실측 %d)" % ("PASS" if ok else "FAIL", name, "위반" if expect else "통과", got))
            if not ok:
                bad += 1
        finally:
            os.unlink(p)
    print("")
    print("self-test %d/%d passed" % (len(SELF_TESTS) - bad, len(SELF_TESTS)))
    return 1 if bad else 0


def fixture_check(root):
    """기대값 대조 — 원시 위반 수가 아니라 **fixture 계약**을 판정한다.

    ⛔ 원시 exit 을 그대로 쓰면 결함 fixture 가 발화할 때마다 빨개진다. 오라클은
       "clean 은 0, defect 는 1건 이상" 이다. defect 가 0 이면 검사기가 죽은 것이므로
       그것도 실패다(positive control).
    """
    base = os.path.join(root, "skills", "fz-explain", "references", "fixtures")
    spec = (("negative-clean.md", "eq0"), ("positive-defects.md", "ge1"))
    bad = 0
    for name, rule in spec:
        f = os.path.join(base, name)
        if not os.path.isfile(f):
            sys.stderr.write("⛔ fixture 부재: %s\n" % name)
            return 2
        n = len(check(f))
        ok = (n == 0) if rule == "eq0" else (n >= 1)
        print("%s  %-22s %d건 (기대 %s)" % ("PASS" if ok else "FAIL", name, n,
                                            "0" if rule == "eq0" else "1건 이상"))
        if not ok:
            bad += 1
    print("")
    print("⏸ SKIP(의미 판정) 2항목: 명사형 제목 · 장식 이모지 — PASS 아님")
    print("fixture 계약 %d/%d 충족" % (len(spec) - bad, len(spec)))
    return 1 if bad else 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    root = ROOT
    if "--fixture-check" in argv:
        return fixture_check(root)
    files = [a for a in argv if not a.startswith("-")]
    if not files:
        base = os.path.join(root, "skills", "fz-explain", "references", "fixtures")
        files = [os.path.join(base, f) for f in ("negative-clean.md", "positive-defects.md")]
    # ⛔ 대상 0개는 통과가 아니라 실행 오류다 — 경로가 어긋나면 "위반 0건" 으로 인쇄된다
    missing = [f for f in files if not os.path.isfile(f)]
    if missing or not files:
        sys.stderr.write("⛔ 대상 파일 부재: %s\n" % (", ".join(missing) or "(목록 비어 있음)"))
        return 2

    total = 0
    for f in files:
        rel = os.path.relpath(f, root)
        hits = check(f)
        total += len(hits)
        print("%s: %d건" % (rel, len(hits)))
        for line, kind, detail in hits:
            print("   L%d  %s  %s" % (line, kind, detail))
    print("")
    print("⏸ SKIP(의미 판정) 2항목: 명사형 제목 · 장식 이모지 — PASS 아님")
    print("기계 판정 2항목 위반 총 %d건" % total)
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
