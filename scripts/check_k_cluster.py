#!/usr/bin/env python3
# lint:no-root-anchor — 판정표 경로를 `--table` 인자로만 받는다(플러그인 밖 계획 문서다).
"""K 클러스터 판정표의 산술·식별자 계약 검사 (B0).

⛔ **왜 검사가 필요한가**: v8 은 클러스터 **제목과 건수만** 남겼고 항목 목록이 없었다.
   그래서 "몇 개를 판정했는가" 가 문서 안에서 닫히지 않았다. 이 검사는 판정표가
   *스스로 셈이 맞는지* 만 본다 — 판정의 옳음은 검사하지 않는다(그것은 증거 열의 일이다).

단언 4개:
  ① 판정표가 **있다** — 부재·읽기 실패는 ⛔ **실패**다(미판정 아님). 없는 표는 0건이 아니다.
  ② ID 가 **고유**하다 — 중복 ID 는 같은 항목을 두 번 세거나 처방이 갈린다
  ③ `total >= 31` — v8 이 남긴 33건보다 적으면 항목이 조용히 빠진 것이다
  ④ `done + pending + unknown + closed == total` — 상태 합이 총계와 같아야 분모가 맞는다.
     ⛔ 미지 상태값은 **거부**한다(fail-closed) — 오타 하나가 분모에서 빠지면 합이 맞아 보인다.

exit: 0=PASS · 1=계약 위반 · 2=인자 오류
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

PASS, VIOLATION, BADARG = 0, 1, 2
# ⛔ `closed` 는 B0-P2 가 만든 상태다 — **복원 불가로 판정해 닫은** 항목이다.
#    `unknown` 과 다르다: unknown 은 "아직 안 봤다", closed 는 "보았고 복원이 불가하다".
#    ⛔ 닫는 것도 판정이므로 무한 보류하지 않는다.
STATES = ("done", "pending", "unknown", "closed")
MIN_TOTAL = 31
# 표 행: | `ID` | 클러스터 | 건수 | 상태 | … |
ROW = re.compile(r"^\|\s*`(B0-[^`]+)`\s*\|([^|]*)\|\s*(\d+)\s*\|\s*\**([A-Za-z`]+)\**\s*\|")
SECTION = re.compile(r"^###\s*B0 판정표", re.M)
NEXT_H = re.compile(r"^#{1,3}\s", re.M)


def parse(text: str) -> list:
    m = SECTION.search(text)
    if not m:
        raise ValueError("### B0 판정표 절을 찾지 못했다")
    rest = text[m.end():]
    nxt = NEXT_H.search(rest)
    sec = rest[: nxt.start()] if nxt else rest
    rows = []
    for ln in sec.splitlines():
        mm = ROW.match(ln.strip())
        if mm:
            rows.append({"id": mm.group(1), "cluster": mm.group(2).strip(),
                         "n": int(mm.group(3)), "state": mm.group(4).strip("`").lower()})
    if not rows:
        raise ValueError("판정표에 행이 없다 — 표 형식이 바뀌었거나 정규식이 놓쳤다")
    return rows


def audit(rows: list) -> list:
    v = []
    # ② 고유 ID
    seen = {}
    for r in rows:
        if r["id"] in seen:
            v.append(f"중복 ID `{r['id']}` — 같은 항목을 두 번 세거나 처방이 갈린다")
        seen[r["id"]] = True
    # ⛔ 미지 상태는 거부 — fail-closed
    by = {s: 0 for s in STATES}
    for r in rows:
        if r["state"] not in STATES:
            v.append(f"`{r['id']}` 의 상태 `{r['state']}` 는 알 수 없다 (아는 값: {'·'.join(STATES)})")
        else:
            by[r["state"]] += r["n"]
    total = sum(r["n"] for r in rows)
    # ③ 하한
    if total < MIN_TOTAL:
        v.append(f"total {total} < {MIN_TOTAL} — v8 이 남긴 33건보다 적다(항목이 빠졌다)")
    # ④ 분모
    if sum(by.values()) != total:
        v.append(f"상태 합 {sum(by.values())} ≠ total {total} — 분모가 맞지 않는다")
    return v, total, by


def main() -> int:
    ap = argparse.ArgumentParser(description="K 클러스터 판정표 계약 검사")
    ap.add_argument("--table", type=pathlib.Path, help="판정표를 담은 문서")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.table is None:
        print("❌ --table 이 필요하다", file=sys.stderr)
        return BADARG
    # ① 부재·읽기 실패는 **실패**다 (미판정 아님 — 없는 표는 0건이 아니다)
    try:
        text = args.table.read_text(encoding="utf-8")
        rows = parse(text)
    except (OSError, ValueError) as e:
        print(f"VIOLATION: 판정표를 읽지 못했다 — {type(e).__name__}: {e} "
              "(⛔ 없는 표는 0건이 아니다)")
        return VIOLATION
    v, total, by = audit(rows)
    print(f"행 {len(rows)} · total={total} · " + " ".join(f"{s}={by[s]}" for s in STATES))
    for x in v:
        print(f"  ⛔ {x}")
    if v:
        print(f"VIOLATION {len(v)}건")
        return VIOLATION
    print("PASS")
    return PASS


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []
    HEAD = "### B0 판정표 — x\n\n| ID | 클러스터 | 건수 | 상태 | 축 | 증거 |\n|---|---|---:|:---:|---|---|\n"

    def rows_md(items):
        return "".join(f"| `{i}` | c | {n} | {st} | a | e |\n" for i, n, st in items)

    def case(name, body, want, needle=None):
        nonlocal passed
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-k-"))
        try:
            q = d / "plan.md"
            q.write_text(body, encoding="utf-8")
            try:
                rows = parse(q.read_text(encoding="utf-8"))
            except ValueError as e:
                got, pool = "VIOLATION", [str(e)]
            else:
                v, _, _ = audit(rows)
                got, pool = ("VIOLATION" if v else "PASS"), v
            if got != want:
                fails.append(f"{name}: {got} (기대 {want}) · {pool[:1]}")
            elif needle and not any(needle in x for x in pool):
                fails.append(f"{name}: 사유에 {needle!r} 없음 — {pool[:2]}")
            else:
                passed += 1
        finally:
            shutil.rmtree(d, ignore_errors=True)

    GOOD = [("B0-A", 20, "done"), ("B0-B", 8, "pending"), ("B0-C", 5, "unknown")]   # 33
    case("valid", HEAD + rows_md(GOOD), "PASS")
    # closed 포함도 분모에 든다 (B0-P2 가 만든 상태)
    case("valid-with-closed",
         HEAD + rows_md([("B0-A", 20, "done"), ("B0-B", 8, "closed"), ("B0-C", 5, "unknown")]), "PASS")
    # ⛔ 절 부재 → 실패 (미판정 아님)
    case("section-missing", "# p\n\n본문만\n", "VIOLATION", "절을 찾지 못했다")
    # ⛔ 행 0건 → 실패 (형식이 바뀌면 조용히 0건이 된다)
    case("no-rows", HEAD, "VIOLATION", "행이 없다")
    # ⛔ 중복 ID
    case("dup-id", HEAD + rows_md([("B0-A", 20, "done"), ("B0-A", 13, "pending")]),
         "VIOLATION", "중복 ID")
    # ⛔ 하한 미달
    case("below-min", HEAD + rows_md([("B0-A", 10, "done"), ("B0-B", 10, "unknown")]),
         "VIOLATION", f"< {MIN_TOTAL}")
    # ⛔ 미지 상태 → 거부. 분모에서 빠져 합이 어긋나는 것까지 함께 잡힌다
    case("unknown-state", HEAD + rows_md([("B0-A", 20, "done"), ("B0-B", 13, "defered")]),
         "VIOLATION", "알 수 없다")

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
