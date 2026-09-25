#!/usr/bin/env python3
# lint:no-root-anchor — census 문서 경로는 `--table` 로 받고, 모집단은 부모 상수 기준으로 유도한다.
"""호스트 중복 census 의 계약 검사 (D3).

⛔ **모집단을 손으로 적지 않는다.** 스스로 고른 행과 합계를 맞추면 누락이 통과한다.
   모집단은 `measure_constraint_load.py` 의 **「강등 PoC 후보」** 를 실행해 유도하고,
   census 행 집합과 **양방향** 대조한다.

단언 4개:
  ① 모집단 집합 == census 행 집합 (양방향 — 한쪽만 보면 추가·누락 중 하나를 놓친다)
  ② 각 행의 분류가 **아는 값 정확히 하나** (미지 분류는 거부 — fail-closed)
  ③ 분류별 합 == total
  ④ ⛔ **`확인불가` 가 삭제 목록에 0건** — 확인 불가는 삭제 근거에서 제외된다.
     *공식 권고가 있다* 는 사실은 호스트가 주입한다는 증거가 아니다.

exit: 0=PASS · 1=위반 · 2=측정 실패(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import pathlib
import re
import subprocess
import sys

PASS, VIOLATION, UNRUN = 0, 1, 2
ROOT = pathlib.Path(__file__).resolve().parent.parent
CLASSES = ("중복확인", "확인불가", "고유")
SECTION = re.compile(r"^###\s*D3 census", re.M)
NEXT_H = re.compile(r"^#{1,3}\s", re.M)
ROW = re.compile(r"^\|\s*`(D3-\d+)`\s*\|\s*`([^`]+)`\s*\|[^|]*\|[^|]*\|[^|]*\|\s*`?([^`|]+?)`?\s*\|")
DELETE_LINE = re.compile(r"\*\*삭제 목록\*\*\s*:\s*\*\*(\d+)\s*건", re.M)
POC = re.compile(r"^\s*-\s*([^:]+):\s*justification")


def parse_population(out: str) -> set:
    """측정기 출력 → 모집단. ⛔ **순수 함수로 분리했다** — subprocess 안에 두면 self-test 가
    이 경로를 지나지 않아 가드에 픽스처가 없었다(실측: 어블레이션이 7/7 로 통과했다)."""
    if "강등 PoC 후보" not in out:
        raise ValueError("measure_constraint_load 출력에 「강등 PoC 후보」 절이 없다 — 형식이 바뀌었다")
    tail = out.split("강등 PoC 후보", 1)[1]
    pop = {m.group(1).strip() for m in (POC.match(ln) for ln in tail.splitlines()) if m}
    if not pop:
        raise ValueError("모집단이 0건 — 추출 정규식이 실제 형식을 놓쳤다(0건은 측정 실패다)")
    return pop


def population() -> set:
    """⛔ 실행으로 유도한다. 실패는 **예외** — 빈 집합으로 폴백하면 ① 이 공짜로 통과한다."""
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "measure_constraint_load.py")],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120, cwd=str(ROOT))
    return parse_population((proc.stdout or b"").decode("utf-8", "replace"))


def census(text: str):
    m = SECTION.search(text)
    if not m:
        raise ValueError("### D3 census 절을 찾지 못했다")
    rest = text[m.end():]
    nxt = NEXT_H.search(rest)
    sec = rest[: nxt.start()] if nxt else rest
    rows = []
    for ln in sec.splitlines():
        mm = ROW.match(ln.strip())
        if mm:
            rows.append({"id": mm.group(1), "target": mm.group(2).strip(),
                         "cls": mm.group(3).strip()})
    if not rows:
        raise ValueError("census 에 행이 없다 — 표 형식이 바뀌었거나 정규식이 놓쳤다")
    dm = DELETE_LINE.search(sec)
    if dm is None:
        raise ValueError("삭제 목록 건수 선언을 찾지 못했다 — 없으면 ④ 를 판정할 수 없다")
    return rows, int(dm.group(1))


def audit(pop: set, rows: list, delete_n: int) -> list:
    v = []
    # ① 양방향
    got = {r["target"] for r in rows}
    for x in sorted(pop - got):
        v.append(f"모집단에 있으나 census 에 없다: {x}")
    for x in sorted(got - pop):
        v.append(f"census 에 있으나 모집단에 없다: {x} — 스스로 고른 행이다")
    # ② 분류
    seen, by = set(), {c: 0 for c in CLASSES}
    for r in rows:
        if r["id"] in seen:
            v.append(f"중복 ID `{r['id']}`")
        seen.add(r["id"])
        if r["cls"] not in CLASSES:
            v.append(f"`{r['id']}` 의 분류 `{r['cls']}` 는 알 수 없다 (아는 값: {'·'.join(CLASSES)})")
        else:
            by[r["cls"]] += 1
    # ③ 합계
    if sum(by.values()) != len(rows):
        v.append(f"분류 합 {sum(by.values())} ≠ total {len(rows)}")
    # ④ 확인불가는 삭제 근거가 아니다
    if by["확인불가"] > 0 and delete_n > 0:
        v.append(f"⛔ `확인불가` {by['확인불가']}건이 있는데 삭제 목록이 {delete_n}건이다 — "
                 "확인 불가는 삭제 근거에서 제외된다")
    if by["중복확인"] == 0 and delete_n > 0:
        v.append(f"`중복확인` 이 0인데 삭제 목록이 {delete_n}건 — 근거 없는 삭제다")
    return v, by


def main() -> int:
    ap = argparse.ArgumentParser(description="호스트 중복 census 계약 검사")
    ap.add_argument("--table", type=pathlib.Path, help="census 를 담은 문서")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.table is None:
        print("❌ --table 이 필요하다", file=sys.stderr)
        return UNRUN
    try:
        pop = population()
        rows, dn = census(args.table.read_text(encoding="utf-8"))
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        print(f"UNRUN: {type(e).__name__}: {e} (⛔ 통과 아님)")
        return UNRUN
    v, by = audit(pop, rows, dn)
    print(f"모집단 {len(pop)} · census {len(rows)} · " + " ".join(f"{c}={by[c]}" for c in CLASSES)
          + f" · 삭제목록 {dn}건")
    for x in v:
        print(f"  ⛔ {x}")
    if v:
        print(f"VIOLATION {len(v)}건")
        return VIOLATION
    print("PASS")
    return PASS


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    passed, fails = 0, []
    POP = {"a.md", "b.md"}

    def rows_of(items):
        return [{"id": i, "target": t, "cls": c} for i, t, c in items]

    def case(name, pop, items, dn, want, needle=None):
        nonlocal passed
        v, _ = audit(pop, rows_of(items), dn)
        got = "VIOLATION" if v else "PASS"
        if got != want:
            fails.append(f"{name}: {got} (기대 {want}) · {v[:1]}")
        elif needle and not any(needle in x for x in v):
            fails.append(f"{name}: 사유에 {needle!r} 없음 — {v[:2]}")
        else:
            passed += 1

    GOOD = [("D3-1", "a.md", "확인불가"), ("D3-2", "b.md", "고유")]
    case("valid", POP, GOOD, 0, "PASS")
    # ① 양방향 — 누락
    case("missing-row", POP, [("D3-1", "a.md", "고유")], 0, "VIOLATION", "census 에 없다")
    # ① 양방향 — 추가 (스스로 고른 행)
    case("extra-row", POP, GOOD + [("D3-3", "z.md", "고유")], 0, "VIOLATION", "모집단에 없다")
    # ② 미지 분류 → 거부
    case("unknown-class", POP, [("D3-1", "a.md", "보류"), ("D3-2", "b.md", "고유")], 0,
         "VIOLATION", "알 수 없다")
    # ② 중복 ID
    case("dup-id", POP, [("D3-1", "a.md", "고유"), ("D3-1", "b.md", "고유")], 0,
         "VIOLATION", "중복 ID")
    # ④ ⛔ 확인불가가 있는데 삭제 목록이 비어 있지 않다
    case("delete-with-unverifiable", POP, GOOD, 1, "VIOLATION", "삭제 근거에서 제외")
    # ④ 중복확인 0인데 삭제 제안
    case("delete-without-confirmed", POP, [("D3-1", "a.md", "고유"), ("D3-2", "b.md", "고유")], 2,
         "VIOLATION", "근거 없는 삭제")

    # ⑧~⑩ 모집단 추출 — 가드가 테스트 표면 안에 있는지 확인한다
    def pcase(name, out, want_ok, needle=None):
        nonlocal passed
        try:
            got = parse_population(out)
        except ValueError as e:
            if want_ok:
                fails.append(f"{name}: 예외 {e}")
            elif needle and needle not in str(e):
                fails.append(f"{name}: 예외 문구에 {needle!r} 없음 — {e}")
            else:
                passed += 1
            return
        if not want_ok:
            fails.append(f"{name}: 예외가 나지 않았다 — {sorted(got)}")
        else:
            passed += 1

    OUT = "머리말\n\n■ 강등 PoC 후보 (…)\n  - a.md: justification 43줄 (19.1%), 참조 4개\n  - b.md: justification 38줄 (10.6%), 참조 3개\n"
    pcase("pop-parsed", OUT, True)
    pcase("pop-section-missing", "머리말만 있다\n", False, "절이 없다")
    pcase("pop-zero", "■ 강등 PoC 후보 (…)\n  (없음)\n", False, "0건")

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
