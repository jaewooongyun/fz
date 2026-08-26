#!/usr/bin/env python3
# diff-parse: hunk-state — `in_hunk` 로 hunk 안팎을 가른다.
"""이동 리팩토링에서 **동등성이 못 보는 드리프트**를 데이터로 만든다.

⛔ 동등성과 드리프트는 다른 축이다. 추가·삭제 라인의 다중집합 차가 "값 표현식 변화 0" 을
보여도, 이동이 만든 **문서·구조 드리프트**는 거기 나타나지 않는다.

실측 근거 (PR #4774): 동등성 대조를 통과한 뒤 Lead 단독 리뷰가 이슈 **0건**을 냈으나
3렌즈가 `origin: regression` 3건을 찾았다. 아래 3축은 그 3건을 역산한 것이다.

  A. 헤더 주석이 가리키는 심볼이 그 파일에 있는가   (렌즈 A4)
  B. 이동 후 원본에 남은 같은 기능의 조각            (렌즈 Q2)
  C. 접근수준이 완화된 선언                          (렌즈 Q1)

⛔ 이 스크립트는 **판정하지 않는다.** 데이터를 만들고, 판정은 렌즈·Lead 가 한다 —
   렌즈는 데이터가 있으면 본다(#4774 에서 evidence-brief 를 주니 인용했다).

usage: move_drift.py DIFF_PATH RANGE_LABEL
exit: 0 = 이동 감지 + 산출 / 1 = 이동 아님(산출 없음) / 2 = 입력 오류
  ⛔ exit 1 은 실패가 아니다 — "이 PR 은 이동이 아니다" 라는 판정이다.
"""
import re
import sys

# 접근수준 완화: 삭제 라인에 있던 private/fileprivate 가 추가 라인에서 사라진 선언
ACCESS = re.compile(r"^\s*(?:private|fileprivate)(?:\(set\))?\s+(.*)$")
DECL = re.compile(r"^\s*(?:@\w+\s+)*(?:static\s+|class\s+|weak\s+|lazy\s+)*(?:var|let|func)\s+(\w+)")
# 헤더 주석이 언급하는 심볼 후보 — 백틱 인용 또는 대문자 시작 식별자
CITED = re.compile(r"`([A-Za-z_][\w.]*)`|\b([A-Z][A-Za-z0-9]{3,})\b")


def parse(text):
    """(신규 파일 → 추가 라인, 기존 파일 → (추가, 삭제))"""
    new_files, add, rem = {}, {}, {}
    cur, in_hunk, is_new = None, False, False
    for line in text.splitlines():
        if line.startswith("diff --git "):
            cur, in_hunk, is_new = None, False, False
        elif line.startswith("new file mode"):
            is_new = True
        elif not in_hunk and line.startswith("+++ "):
            p = line[4:].strip()
            cur = p[2:] if p.startswith("b/") else p
            if cur == "/dev/null":
                cur = None
            else:
                (new_files if is_new else add).setdefault(cur, [])
                rem.setdefault(cur, [])
        elif line.startswith("@@"):
            in_hunk = True
        elif in_hunk and cur is not None:
            if line.startswith("+"):
                (new_files if is_new else add)[cur].append(line[1:])
            elif line.startswith("-"):
                rem[cur].append(line[1:])
    return new_files, add, rem


# ⛔ Xcode 표준 헤더는 설명이 아니라 **양식**이다. 걸러내지 않으면
#    `Copyright`·`Created`·작성자명이 전부 "본문에 없는 심볼" 로 잡혀 노이즈가 된다.
BOILERPLATE = re.compile(r"Created by|Copyright|All rights reserved|^\s*//\s*$|\.swift\s*$")
# ⛔ `MARK`·`TODO` 는 Xcode 지시자이지 심볼이 아니다.
NOISE_WORDS = {"Copyright", "Created", "TVING", "Release", "Debug", "MARK", "TODO", "FIXME", "NOTE"}


# ⛔ 첫 **선언** 전까지가 서문이다. "파일 최상단" 으로 잡으면 안 된다 —
#    실측(#4774): 설명 주석이 `import` **뒤**(19행)에 있어서 최상단만 보면 놓친다.
#    그 주석이 정확히 렌즈 A4 가 잡은 결함의 자리였다.
DECL_START = re.compile(r"^\s*(?:#if|extension|final\s+class|class|struct|enum|protocol|actor)\b")


def header_block(lines):
    """첫 선언 전까지의 주석 — Xcode 양식 줄은 뺀다."""
    out = []
    for l in lines:
        if DECL_START.match(l):
            break
        s = l.strip()
        if (s.startswith("//") or s.startswith("*")) and not BOILERPLATE.search(s):
            out.append(s)
    return out


def main(argv):
    if len(argv) < 3:
        sys.stderr.write("usage: move_drift.py DIFF_PATH RANGE_LABEL\n")
        return 2
    try:
        text = open(argv[1], encoding="utf-8", errors="replace").read()
    except OSError as exc:
        sys.stderr.write("diff 를 읽을 수 없다: %s\n" % exc)
        return 2

    new_files, add, rem = parse(text)
    # ⛔ 이동 판정: **신규 파일이 실제로 생겼고** 기존 파일에서 그만큼 지워졌다.
    #    비율만 쓰면 개명 PR 이 걸린다 — 신규 파일 존재를 필수 조건으로 둔다.
    deleted = sum(len(v) for v in rem.values())
    added_new = sum(len(v) for v in new_files.values())
    if not new_files or added_new == 0 or deleted < added_new * 0.5:
        return 1

    print("# 이동 리팩토링 드리프트 — 동등성과 **별개 축**\n")
    print("> 판정 대상: `%s` (⛔ `git cherry` 의 `+` 커밋분 — 중복 커밋 제외)" % argv[2])
    print("> ⛔ 이 문서는 **데이터**다. 판정은 렌즈·Lead 가 한다.\n")
    print("신규 파일 %d개(추가 %d줄) · 기존 파일 삭제 %d줄\n" % (len(new_files), added_new, deleted))

    print("## A. 헤더 주석이 가리키는 심볼이 그 파일에 있는가\n")
    print("⚠️ base 에서 같은 파일이라 성립하던 문장이 이동으로 어긋날 수 있다.\n")
    any_a = False
    for f, lines in new_files.items():
        hdr = header_block(lines)
        if not hdr:
            continue
        # ⛔ **주석 줄을 통째로 뺀다.** `//` 기호만 지우면 헤더가 **자기 자신**을 근거로
        #    "본문에 있음" 판정을 받는다 — 실측(#4774): `Presentable`·`Listener` 의 유일한
        #    등장이 헤더 19행이었고 그래서 A4(렌즈가 잡은 진짜 결함)를 놓쳤다.
        code = "\n".join(l for l in lines
                         if not (l.strip().startswith("//") or l.strip().startswith("*")))
        cited = {m.group(1) or m.group(2) for h in hdr for m in CITED.finditer(h)}
        # 파일명 유래 토큰과 작성자명은 심볼이 아니다 — 파일 basename 조각도 뺀다
        stem = f.split("/")[-1].rsplit(".", 1)[0]
        parts = set(re.split(r"[+._-]", stem))
        cited = {c for c in cited if c and c not in NOISE_WORDS and c not in parts}
        missing = sorted(c for c in cited if c not in code)
        if missing:
            any_a = True
            print("- `%s`" % f.split("/")[-1])
            print("  - 헤더가 언급: %s" % ", ".join("`%s`" % c for c in sorted(cited)))
            print("  - ⚠️ **본문에서 못 찾음**: %s" % ", ".join("`%s`" % m for m in missing))
    if not any_a:
        print("(헤더가 언급한 심볼이 모두 본문에 있다.)")

    print("\n## B. 이동 후 원본에 남은 같은 기능의 조각\n")
    print("⚠️ 기능이 몇 지점에 흩어졌는지는 렌즈가 판단한다 — 아래는 위치 목록이다.\n")
    residual = {f: v for f, v in add.items() if v}
    if residual:
        for f, lines in residual.items():
            kinds = []
            if any(l.strip().startswith("#if") for l in lines):
                kinds.append("조건부 컴파일")
            if any(DECL.match(l) for l in lines):
                kinds.append("선언")
            print("- `%s` — 추가 %d줄%s" % (f.split("/")[-1], len(lines),
                                           (" (" + " · ".join(kinds) + ")") if kinds else ""))
    else:
        print("(기존 파일에 추가된 라인이 없다 — 순수 삭제 이동.)")

    print("\n## C. 접근수준이 완화된 선언\n")
    gone = {}
    for f, lines in rem.items():
        for l in lines:
            m = ACCESS.match(l)
            if m:
                d = DECL.match("  " + m.group(1))
                if d:
                    gone[d.group(1)] = f
    relaxed = []
    allnew = "\n".join(l for v in list(new_files.values()) + list(add.values()) for l in v)
    for name, f in gone.items():
        for l in allnew.splitlines():
            d = DECL.match(l)
            if d and d.group(1) == name and not ACCESS.match(l):
                relaxed.append((name, f))
                break
    if relaxed:
        for name, f in sorted(set(relaxed)):
            print("- `%s` — `private` 제거 (원본 `%s`)" % (name, f.split("/")[-1]))
        print("\n⚠️ Swift 에서 다른 파일의 확장은 `private` 에 접근할 수 없다 — 완화가 **강제**일 수 있다.")
        print("판단 축: 완화 범위가 최소인가 · `#if` 로 빌드 구성이 한정되는가 · 프로젝트 관례와 맞는가.")
    else:
        print("(접근수준이 완화된 선언을 찾지 못했다.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
