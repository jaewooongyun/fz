#!/usr/bin/env python3
# lint:no-root-anchor — 루트를 `--root` 인자로만 받는다(자기 위치에서 해석하지 않는다).
#   레지스트리는 플러그인 트리 밖에 있어 고정할 앵커가 없다.
"""레지스트리의 stale 엔트리를 **판정**한다 (S16).

정책 — 세 가지를 분리해서 정의한다. 섞으면 같은 엔트리가 날마다 다르게 판정된다.

  ① 시계의 기준  : `last_observed:` 가 있으면 그것, 없으면 `date:` (등록일).
                    ⛔ 등록일과 마지막 관측일은 다르다 — 관측이 쌓인 엔트리는 늙지 않는다.
  ② 시계 갱신    : **명시 필드로만** 갱신된다. 본문에 관측을 덧붙였다고 자동 갱신되지 않는다.
                    ⛔ 본문에서 관측일을 추론하지 않는다 — 형식이 자유라 추론은 오판을 만든다.
  ③ 임계         : 기본 **90일**. `--days` 로 바꾼다. 3개월(월 경계)이 아니라 일수다 —
                    월 경계는 달마다 임계가 달라져 재현되지 않는다.

⛔ **이 스크립트는 파일을 옮기지 않는다.** 이동은 `entries/` 집합을 바꿔
   `check_findings_hygiene.py` 의 「INDEX 고아 행」 불변식을 깨뜨리고, 목적지 의미가
   `.archive/`(= 릴리즈가 닫은 배출)와 섞인다. 이동 정책은 같은 시계를 정의하는
   **D4(candidate 만료)** 와 `fz-findings/` 쓰기 소유자에게 속한다.
   여기서는 **무엇이 대상인가**만 기계로 답한다.

exit: 0=stale 0건 · 1=stale 있음(--strict 일 때만) · 2=측정 실패(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

OK, FOUND, UNRUN = 0, 1, 2
DEFAULT_DAYS = 90
DATE_RE = re.compile(r"^(date|last_observed):\s*(\d{4})-(\d{2})-(\d{2})\s*$", re.M)
STATUS_RE = re.compile(r"^status:\s*(\S+)\s*$", re.M)
FRONT_LIMIT = 4000   # frontmatter 는 앞부분에 있다 — 본문 전체를 읽지 않는다


def list_entries(d: pathlib.Path):
    """⛔ `glob` 을 쓰지 않는다 — 권한 오류를 예외 없이 빈 목록으로 돌려준다(F-271).
    `iterdir` 은 PermissionError 를 던지므로 측정 실패를 부재와 구별할 수 있다."""
    if not d.is_dir():
        raise FileNotFoundError(f"entries 디렉토리가 없다: {d}")
    return sorted(q for q in d.iterdir() if q.suffix == ".md" and q.name.startswith("F-"))


def clock_of(text: str):
    """(기준일, 출처) — `last_observed:` 가 `date:` 를 이긴다. 둘 다 없으면 (None, None)."""
    found = {}
    for m in DATE_RE.finditer(text):
        key = m.group(1)
        if key not in found:      # 첫 등장만 — 중복 선언은 아래에서 드러난다
            found[key] = datetime.date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
    if "last_observed" in found:
        return found["last_observed"], "last_observed"
    if "date" in found:
        return found["date"], "date"
    return None, None


def audit(root: pathlib.Path, days: int, today: datetime.date) -> dict:
    entries = list_entries(root / "entries")
    stale, fresh, undated = [], 0, []
    for p in entries:
        head = p.read_text(encoding="utf-8", errors="replace")[:FRONT_LIMIT]
        when, src = clock_of(head)
        if when is None:
            # ⛔ 날짜 없음은 "신선" 이 아니다 — 판정 불가로 따로 센다
            undated.append(p.name)
            continue
        age = (today - when).days
        if age > days:
            sm = STATUS_RE.search(head)
            stale.append({"file": p.name, "age": age, "clock": src,
                          "status": sm.group(1) if sm else "(없음)"})
        else:
            fresh += 1
    stale.sort(key=lambda r: -r["age"])
    return {"total": len(entries), "stale": stale, "fresh": fresh, "undated": undated, "days": days}


def main() -> int:
    ap = argparse.ArgumentParser(description="레지스트리 stale 엔트리 판정 (읽기 전용)")
    ap.add_argument("--root", type=pathlib.Path, help="레지스트리 루트 (entries/ 보유)")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"임계 일수 (기본 {DEFAULT_DAYS})")
    ap.add_argument("--today", help="기준일 YYYY-MM-DD (시험용 — 없으면 오늘)")
    ap.add_argument("--strict", action="store_true", help="stale 이 있으면 exit 1")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.root is None:
        print("❌ --root 가 필요하다 (측정 실패)", file=sys.stderr)
        return UNRUN
    try:
        today = (datetime.date.fromisoformat(args.today) if args.today
                 else datetime.date.today())
    except ValueError:
        print(f"❌ --today 형식 오류: {args.today}", file=sys.stderr)
        return UNRUN
    try:
        r = audit(args.root, args.days, today)
    except (OSError, FileNotFoundError) as e:
        # ⛔ 열거 실패를 "stale 0건" 으로 인쇄하지 않는다
        print(f"UNRUN: 레지스트리를 읽지 못했다 — {type(e).__name__}: {e} (⛔ 통과 아님)")
        return UNRUN

    print(f"기준일 {today} · 임계 {r['days']}일 · 엔트리 {r['total']}건")
    print(f"  신선 {r['fresh']} · stale {len(r['stale'])} · 날짜없음 {len(r['undated'])}")
    for row in r["stale"]:
        print(f"    {row['file']} — {row['age']}일 (시계: {row['clock']} · status: {row['status']})")
    if r["undated"]:
        # ⛔ 판정 불가를 신선으로 세지 않는다 — 셋을 함께 인쇄해야 분모가 맞는다
        print(f"  ⚠️ 날짜 없어 판정 불가 {len(r['undated'])}건: {', '.join(r['undated'][:5])}"
              + (" …" if len(r["undated"]) > 5 else ""))
    if not r["stale"]:
        print("STALE_NONE (임계 초과 0건)")
        return OK
    print(f"STALE_FOUND {len(r['stale'])}건 — ⛔ 이동은 이 스크립트가 하지 않는다 "
          "(D4 · fz-findings 쓰기 소유자 소관)")
    return FOUND if args.strict else OK


# ── self-test ───────────────────────────────────────────────────────────────
def self_test() -> int:
    import shutil
    import tempfile
    passed, fails = 0, []

    def mk(rows):
        d = pathlib.Path(tempfile.mkdtemp(prefix="fz-stale-"))
        (d / "entries").mkdir()
        for name, front in rows:
            (d / "entries" / name).write_text("---\n" + front + "---\n\n# x\n", encoding="utf-8")
        return d

    def case(name, rows, days, today, want_stale, want_undated=0, want_exit=OK, strict=False):
        nonlocal passed
        d = mk(rows)
        try:
            r = audit(d, days, datetime.date.fromisoformat(today))
            why = []
            if len(r["stale"]) != want_stale:
                why.append(f"stale {len(r['stale'])} (기대 {want_stale})")
            if len(r["undated"]) != want_undated:
                why.append(f"undated {len(r['undated'])} (기대 {want_undated})")
            if why:
                fails.append(f"{name}: " + " · ".join(why))
            else:
                passed += 1
        except Exception as e:      # noqa: BLE001 — 크래시를 FAIL 로 보고한다(요약 줄 보존)
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    T = "2026-09-22"
    # ① 임계 이내 → stale 0
    case("fresh", [("F-001-a.md", "id: F-001\ndate: 2026-09-01\nstatus: open\n")], 90, T, 0)
    # ② 임계 초과 → stale 1
    case("aged", [("F-002-b.md", "id: F-002\ndate: 2026-01-01\nstatus: open\n")], 90, T, 1)
    # ③ ⛔ last_observed 가 date 를 이긴다 — 관측이 쌓인 엔트리는 늙지 않는다
    case("observed-resets", [("F-003-c.md",
         "id: F-003\ndate: 2026-01-01\nlast_observed: 2026-09-10\nstatus: open\n")], 90, T, 0)
    # ④ ⛔ last_observed 도 낡으면 stale — 필드 존재만으로 면제되지 않는다
    case("observed-also-aged", [("F-004-d.md",
         "id: F-004\ndate: 2026-08-01\nlast_observed: 2026-02-01\nstatus: open\n")], 90, T, 1)
    # ⑤ ⛔ 날짜 없음은 신선이 아니라 **판정 불가**
    case("undated", [("F-005-e.md", "id: F-005\nstatus: open\n")], 90, T, 0, want_undated=1)
    # ⑥ 임계는 인자로 움직인다 (하드코딩이 아님)
    case("threshold-moves", [("F-006-f.md", "id: F-006\ndate: 2026-08-01\nstatus: open\n")], 30, T, 1)
    # ⑦ ⛔ 열거 실패를 0건으로 인쇄하지 않는다
    d = pathlib.Path(tempfile.mkdtemp(prefix="fz-stale-noent-"))
    try:
        try:
            audit(d, 90, datetime.date.fromisoformat(T))
            fails.append("missing-entries: 예외가 나지 않았다 — 부재를 0건으로 읽는다")
        except FileNotFoundError:
            passed += 1
    finally:
        shutil.rmtree(d, ignore_errors=True)

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
