#!/usr/bin/env python3
# lint:no-root-anchor — 루트를 `--root` 인자로 받는다(기본값은 이 파일 기준 부모, 아래 상수).
"""Workflow 실패 처방 표의 계약 검사 (C2 / N9-a·N9-b).

정본은 `guides/skill-authoring.md` § 실패 복구 사다리의 **판별 표**다. 그 표가 상태마다
고유 행을 갖고, 각 행에 *판별 근거* 와 *처방* 이 있고, **승인 없는 SOLO 전환이 0** 인지 본다.

⛔ 왜 기계로 재는가: 이 표는 *"스폰 실패를 SOLO 폴백으로 직행시켰는데 사다리에는 그 상태가
   없었다"* 는 실패에서 태어났다. 상태 하나가 조용히 빠지면 그 경로가 다시 SOLO 로 새고,
   산문만으로는 빠진 것을 세지 못한다.

축 4개:
  ① 상태 6종이 각각 **고유 행**을 갖는가 (중복·누락 없음)
  ② 각 행에 판별 근거와 처방이 **둘 다** 있는가 (빈 칸은 판정 불가다)
  ③ 표의 처방에 **SOLO 전환이 0건** 인가 · L4 행동에 **승인 요구**가 명시됐는가
  ④ 소비자(`skills/fz/SKILL.md`)의 `SOLO 폴백`/`SOLO 직행` 언급이 전부
     **판별 표 참조** 또는 **도구 부재 축 명시**를 동반하는가 (N9-a)

exit: 0=충족 · 1=위반 · 2=측정 실패(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

OK, VIOLATION, UNRUN = 0, 1, 2
DEFAULT_ROOT = pathlib.Path(__file__).resolve().parent.parent

GUIDE = "guides/skill-authoring.md"
CONSUMER = "skills/fz/SKILL.md"
SECTION = re.compile(r"^###\s*⛔?\s*실패 복구 사다리", re.M)
NEXT_H = re.compile(r"^#{1,3}\s", re.M)

# 상태는 **표기가 아니라 의미**로 찾는다 — 제목 문구가 조금 바뀌어도 걸리게 별칭을 둔다.
STATES = {
    "scriptPath 거부": ("scriptpath", "거부"),
    "분할 요구":       ("분할",),
    "입력 오류":       ("입력 오류", "입력오류"),
    "일시 장애":       ("일시 장애", "일시장애"),
    "스폰 실패":       ("스폰",),
    "알 수 없는 반환": ("알 수 없는", "미지 반환"),
}
SOLO_IN_ROW = re.compile(r"SOLO")
# ⛔ 표 안에서 SOLO 가 **금지 문구와 함께** 나오는 것은 위반이 아니다 — 그것이 계약 서술이다.
SOLO_NEGATED = re.compile(r"(아님|금지|않는다|안\s*된다|승인 후)")


def read(root: pathlib.Path, rel: str) -> str:
    q = root / rel
    if not q.is_file():
        raise FileNotFoundError(f"{rel} 이 없다 ({q})")
    return q.read_text(encoding="utf-8", errors="replace")


def section_of(text: str) -> str:
    m = SECTION.search(text)
    if not m:
        raise ValueError("§ 실패 복구 사다리 절을 찾지 못했다")
    rest = text[m.end():]
    nxt = NEXT_H.search(rest)
    return rest[: nxt.start()] if nxt else rest


def split_tables(sec: str) -> list:
    """연속한 `|` 줄을 표 단위로 묶는다. ⛔ 절 안에 표가 **둘 이상** 있다 —
    판별 표와 L1~L4 사다리가 같은 상태 이름을 쓰므로, 섞어 세면 전부 '중복' 으로 읽힌다
    (실측: 6종 중 4종이 중복으로 인쇄됐다)."""
    tables, cur = [], []
    for ln in sec.splitlines():
        if ln.strip().startswith("|"):
            cur.append(ln.strip())
        elif cur:
            tables.append(cur); cur = []
    if cur:
        tables.append(cur)
    return tables


def table_rows(sec: str) -> list:
    """**판별 표**의 데이터 행. 표를 위치가 아니라 **헤더 내용**으로 고른다 —
    표 순서가 바뀌어도 같은 표를 집는다."""
    chosen = None
    for tb in split_tables(sec):
        head = tb[0]
        if "상태" in head and "처방" in head:
            if chosen is not None:
                raise ValueError("판별 표(헤더에 상태·처방)가 둘 이상이다 — 정본이 갈린다")
            chosen = tb
    if chosen is None:
        raise ValueError("판별 표를 찾지 못했다 (헤더에 `상태` 와 `처방` 이 있는 표)")
    out = []
    for t in chosen[1:]:
        cells = [c.strip() for c in t.strip("|").split("|")]
        if not cells or set("".join(cells)) <= set("-: "):
            continue                      # 구분선
        out.append(cells)
    return out


def audit(root: pathlib.Path) -> dict:
    guide = read(root, GUIDE)
    sec = section_of(guide)
    rows = table_rows(sec)
    v = []

    # ① 상태별 고유 행
    matched, validated = {}, 0
    for name, aliases in STATES.items():
        # ⛔ **상태 칸만** 본다. 행 전체를 보면 다른 행의 *처방* 문구에 걸린다 —
        #    실측: 5행의 "L3 우선(일시 장애 의심)" 이 4행 `일시 장애` 와 중복으로 읽혔다.
        hits = [r for r in rows
                if len(r) > 1 and any(a in r[1].lower() or a in r[1] for a in aliases)]
        matched[name] = hits
        if not hits:
            v.append(f"① 상태 `{name}` 의 행이 없다 — 빠진 상태는 다시 SOLO 로 샌다")
        elif len(hits) > 1:
            v.append(f"① 상태 `{name}` 이 {len(hits)}행에 중복 — 처방이 갈리면 어느 쪽인지 알 수 없다")
        else:
            validated += 1
            # ② 판별 근거 + 처방이 둘 다 있는가
            cells = hits[0]
            if len(cells) < 4 or not cells[2] or not cells[3]:
                v.append(f"② 상태 `{name}` 행에 판별 근거 또는 처방이 비었다 — 빈 칸은 판정 불가다")

    # ③ 표의 처방에 SOLO 전환 0건 (금지 문구 동반은 계약 서술이므로 제외)
    for r in rows:
        joined = " ".join(r)
        if SOLO_IN_ROW.search(joined) and not SOLO_NEGATED.search(joined):
            v.append(f"③ 표 행이 SOLO 전환을 처방한다(금지 문구 없음): {joined[:110]}")
    if "승인" not in sec:
        v.append("③ 절 안에 **승인** 요구가 없다 — L4 의 SOLO 는 사용자 승인 후에만 성립한다")

    # ④ 소비자 정합 (N9-a)
    try:
        cons = read(root, CONSUMER)
    except FileNotFoundError as e:
        raise ValueError(f"소비자 문서를 읽지 못했다 — {e}")
    for i, ln in enumerate(cons.splitlines(), 1):
        if "SOLO 폴백" in ln or "SOLO 직행" in ln:
            if ("판별 표" not in ln) and ("도구 부재" not in ln) and ("우회 계약" not in ln):
                v.append(f"④ {CONSUMER}:{i} 의 SOLO 언급이 판별 표·도구 부재 축을 참조하지 않는다: {ln.strip()[:90]}")
    return {"violations": v, "expected": len(STATES), "validated": validated, "rows": len(rows)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Workflow 실패 처방 표 계약 검사")
    ap.add_argument("--root", type=pathlib.Path, default=DEFAULT_ROOT)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    try:
        r = audit(args.root)
    except (OSError, ValueError) as e:
        # ⛔ 절·표를 못 찾은 것을 "위반 0건" 으로 인쇄하지 않는다
        print(f"UNRUN: {type(e).__name__}: {e} (⛔ 통과 아님)")
        return UNRUN
    print(f"expected={r['expected']}/validated={r['validated']} · 표 행 {r['rows']}건")
    for x in r["violations"]:
        print(f"  ⛔ {x}")
    if r["violations"] or r["validated"] != r["expected"]:
        print(f"VIOLATION {len(r['violations'])}건")
        return VIOLATION
    print("PASS")
    return OK


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []
    real = read(DEFAULT_ROOT, GUIDE)
    cons = read(DEFAULT_ROOT, CONSUMER)

    def case(name, guide_text, cons_text, want_violation: bool, needle=None):
        nonlocal passed
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-ft-"))
        try:
            (d / "guides").mkdir(); (d / "skills" / "fz").mkdir(parents=True)
            (d / GUIDE).write_text(guide_text, encoding="utf-8")
            (d / CONSUMER).write_text(cons_text, encoding="utf-8")
            try:
                r = audit(d)
            except (OSError, ValueError) as e:
                # ⛔ 메시지까지 본다. UNRUN 가드가 둘이고 둘 다 같은 예외형을 내므로,
                #    형만 보면 한쪽을 지워도 다른 쪽이 잡아 통과한다(실측: 어블레이션 6 이 7/7).
                want_msg = needle[6:] if isinstance(needle, str) and needle.startswith("UNRUN:") else None
                if want_violation and (needle == "UNRUN" or want_msg):
                    if want_msg and want_msg not in str(e):
                        fails.append(f"{name}: 예외 문구에 {want_msg!r} 없음 — {e}")
                    else:
                        passed += 1
                else:
                    fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
                return
            got = bool(r["violations"]) or r["validated"] != r["expected"]
            # ⛔ **미판정과 위반을 구별한다.** 둘 다 `want_violation=True` 를 만족하므로
            #    needle 이 "UNRUN" 이면 **예외가 났어야** 한다 — 구별하지 않으면 UNRUN 가드를
            #    지워도 위반으로 떨어져 통과한다(실측: 어블레이션 5 가 7/7 이었다).
            if isinstance(needle, str) and needle.startswith("UNRUN"):
                fails.append(f"{name}: 예외가 나지 않았다 — 미판정이어야 하는데 위반으로 떨어졌다 ({r['violations'][:1]})")
                return
            if got != want_violation:
                fails.append(f"{name}: 위반 {got} (기대 {want_violation}) · {r['violations'][:1]}")
            elif needle and not needle.startswith("UNRUN") and not any(needle in x for x in r["violations"]):
                fails.append(f"{name}: 위반 사유에 {needle!r} 없음 — {r['violations'][:2]}")
            else:
                passed += 1
        finally:
            shutil.rmtree(d, ignore_errors=True)

    # ① 실제 문서 = 통과 (양성 대조)
    case("real-passes", real, cons, False)
    # ② 상태 1행 삭제 → ① 발화
    case("state-removed", re.sub(r"^\| 5 \| \*\*스폰 실패\*\*.*\n", "", real, flags=re.M), cons, True, "① 상태")
    # ③ 처방 칸 비움 → ② 발화
    case("prescription-empty",
         re.sub(r"(^\| 6 \| \*\*알 수 없는 반환\*\* \| [^|]*\|)[^|]*\|", r"\1  |", real, flags=re.M),
         cons, True, "② 상태")
    # ④ 표 행이 SOLO 를 금지 문구 없이 처방 → ③ 발화
    case("solo-in-row",
         re.sub(r"^\| 4 \| \*\*일시 장애\*\* \| ([^|]*)\|[^|]*\|",
                r"| 4 | **일시 장애** | \1| SOLO 로 전환한다 |", real, flags=re.M),
         cons, True, "③ 표 행"),
    # ⑤ 소비자가 판별 표를 참조하지 않는 SOLO 언급 → ④ 발화
    case("consumer-unqualified", real, cons + "\n- 실패하면 SOLO 폴백으로 간다\n", True, "④")
    # ⑥ ⛔ 절이 없으면 **미판정** — 위반 0건으로 인쇄하지 않는다
    case("section-missing", "# guide\n\n본문만 있다\n", cons, True, "UNRUN:절을 찾지 못했다")
    # ⑦ ⛔ 절은 있는데 **판별 표만** 없다 — ⑥ 과 다른 가드다.
    #    ⑥ 은 `section_of` 가 잡고 이것은 `table_rows` 가 잡는다. 픽스처를 나누지 않으면
    #    한쪽을 지워도 다른 쪽이 같은 예외를 내서 통과한다(실측: 어블레이션 5 가 6/6 이었다).
    case("table-missing",
         "# guide\n\n### ⛔ 실패 복구 사다리\n\n| 단계 | 조건 | 행동 |\n|---|---|---|\n| L1 | x | y |\n\n승인\n",
         cons, True, "UNRUN:판별 표를 찾지 못했다")

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
