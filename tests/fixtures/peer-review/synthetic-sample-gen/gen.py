#!/usr/bin/env python3
# diff-parse: not-a-diff — diff 를 만들기만 한다(좌표 표 → patch 글자). 줄 접두사를 읽어 판정하지 않는다. --check 는 바이트 비교다
"""gen.py — 리뷰 앵커 러너가 쓰는 합성 patch 를 좌표 표에서 만든다.

정본은 아래 좌표 표(FILES)다. patch(`skills/fz-peer-review/references/fixtures/synthetic-sample.patch`)는 이 표의
출력이고, 러너의 기대값(`tests/fixtures/peer-review/anchors-synthetic` · `render-single-source`)은 이 표에서 산술로
유도한다. 표에는 hunk 의 **옛 시작 줄과 줄 구성만** 둔다 — 새 시작 줄과 `@@` 의 길이는 앞 hunk 들의 증감을 더해
계산한다(둘을 따로 적으면 머리줄과 본문이 어긋나도 러너가 잡지 못한다).

결정적이다 — 난수 · 시각 · 환경을 쓰지 않는다. 같은 표는 언제나 같은 바이트를 낸다. 좌표는 어느 실제 PR 에서도
가져오지 않았다(합성 도메인 '주문 앱').

사용: gen.py            patch 를 표준 출력으로 낸다
      gen.py --write    저장소의 patch 자리에 쓴다
      gen.py --check    다시 만든 바이트와 저장소의 patch 를 비교한다
exit: 0 같다(또는 출력 · 쓰기 성공) · 1 다르다(첫 차이 줄을 stderr 로) · 2 patch 를 읽지 못함 · 모르는 인자
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]
PATCH = ROOT / "skills/fz-peer-review/references/fixtures/synthetic-sample.patch"
FLOW = "Packages/CheckoutKit/Sources/CheckoutKit/Flow"

# (경로, 타입 이름, hunk 들) — hunk = (옛 시작 줄, 줄 구성). 줄 구성의 낱말은 종류 한 글자 + 줄 수다: c 문맥 · d 삭제 · a 추가.
# 러너가 기대는 자리(바꾸면 러너 기대값을 표에서 다시 유도한다):
#   CheckoutEngine 41    두 자리 추가 줄(새 44 · 45)
#   CheckoutEngine 133   삭제가 있는 hunk — 옛 좌표(LEFT) 133 ~ 156
#   CheckoutEngine 171   추가 30줄 — 새 좌표 170 ~ 206 안에 구간 하나가 통째로 든다
#   CheckoutContext      hunk 가 둘뿐이다(새 9 ~ 15 · 37 ~ 43) — 그 밖은 diff 밖
#   CartSummaryView 88 · 99   미변경 줄(새 97 ~ 100)을 사이에 둔 두 hunk(새 89 ~ 96 · 101 ~ 109)
FILES = (
    (FLOW + "/CheckoutEngine.swift", "CheckoutEngine", (
        (22, "c3 d1 a1 c3"), (41, "c3 a2 c3"), (58, "c3 d3 c2"), (97, "c3 d1 a1 c2 d1 a1 c3"),
        (133, "c3 d2 a2 c5 d1 a1 c6 d2 a2 c5"), (171, "c3 a30 c4"), (221, "c3 d1 c3"))),
    (FLOW + "/CheckoutContext.swift", "CheckoutContext", (
        (9, "c3 d1 a1 c3"), (37, "c3 a1 c3"))),
    (FLOW + "/Views/CartSummaryView.swift", "CartSummaryView", (
        (18, "c3 a3 c3"), (52, "c3 d2 c4"), (88, "c3 d1 a2 c3"), (99, "c3 d2 a3 c3"), (127, "c3 d1 c3"), (160, "c3 a4 c3"))),
)


def render() -> str:
    out = []
    for index, (path, name, hunks) in enumerate(FILES, 1):
        out += [f"diff --git a/{path} b/{path}", f"index {index:07d}..{100 + index:07d} 100644", f"--- a/{path}", f"+++ b/{path}"]
        shift, last_old = 0, 0          # shift = 앞 hunk 들이 만든 줄 수 증감(새 시작 = 옛 시작 + shift)
        for old_start, shape in hunks:
            ops = [(word[0], int(word[1:])) for word in shape.split()]
            if any(kind not in "cda" or count < 1 for kind, count in ops) or old_start <= last_old:
                raise ValueError(f"{name} hunk {old_start}: 줄 구성이 틀렸거나 앞 hunk 와 겹친다")
            old_len = sum(count for kind, count in ops if kind in "cd")
            new_len = sum(count for kind, count in ops if kind in "ca")
            old, new = old_start, old_start + shift
            out.append(f"@@ -{old},{old_len} +{new},{new_len} @@ // {name} 합성 hunk")
            for kind, count in ops:
                for _ in range(count):
                    if kind == "c":
                        out.append(f"     // {name}: 문맥 L{old}→L{new} — 합성 fixture 본문")
                        old, new = old + 1, new + 1
                    elif kind == "d":
                        out.append(f"-    let legacy{name}Value{old} = legacyCompute(step: {old})")
                        old += 1
                    else:
                        out.append(f"+    let next{name}Value{new} = compute(step: {new}, mode: .synthetic)")
                        new += 1
            shift += new_len - old_len
            last_old = old_start + old_len - 1
    return "\n".join(out) + "\n"


def main(argv) -> int:
    if argv not in ([], ["--write"], ["--check"]):
        print(__doc__, file=sys.stderr)
        return 2
    made = render()
    if not argv:
        sys.stdout.write(made)
        return 0
    if argv == ["--write"]:
        PATCH.write_text(made, encoding="utf-8")
        return 0
    try:
        have = PATCH.read_bytes()   # ⛔ 글자로 읽지 않는다 — 줄 끝 변환(CRLF → LF)이 바이트 차이를 지운다
    except OSError as err:
        print(f"UNRUN: patch 를 읽지 못했다 — {err}", file=sys.stderr)
        return 2
    if have == made.encode("utf-8"):
        return 0
    a, b = made.split("\n"), have.decode("utf-8", "replace").split("\n")
    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    # 줄은 repr 로 낸다 — 줄 끝(\r)만 다른 차이가 눈에 보인다
    print(f"DIFF: {PATCH.relative_to(ROOT)}:{at + 1} — 생성기 출력과 다르다\n  생성기: {a[at] if at < len(a) else '(끝)'!r}\n"
          f"  patch : {b[at] if at < len(b) else '(끝)'!r}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
