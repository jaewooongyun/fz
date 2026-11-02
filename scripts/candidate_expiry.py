#!/usr/bin/env python3
# lint:no-root-anchor — 순수 판정 함수 + 원장 경로를 인자로 받는다(루트 해석 없음).
"""candidate 만료 판정 (D4 / SG5 · S14 흡수).

⛔ **공통 만료로 바꾸지 않는다.** 원장은 트랙·상태별로 자격과 임계가 다르다 —
   `eligible session 없이 **3개월** 경과 시 재평가` · `DEFERRED 는 **6개월** 후 재평가`.
   19건(실측)을 한 임계로 묶으면 의미가 달라진다.

입력 5축 · 출력 3값 — 섞으면 "판정 불가"가 "유지"로 새어 나간다.

| 입력 | 뜻 |
|---|---|
| `track` | A(신호 활성 · 5세션) · B(메모리 · 비권장) · C(외부 catch · A 준용) |
| `state` | `candidate` · `DEFERRED` · `implemented` · `REMOVED` |
| `base_date` | 등록일 |
| `last_eligible` | **마지막 유효 세션 관측일**(없으면 None) |
| `now` | 현재 시각(고정 주입 가능 — 시험은 고정 시각으로 한다) |

출력: `재평가필요` · `유지` · `판정불가`

규칙 (위에서부터):
  ① `base_date` 없음 → **판정불가**. ⛔ 날짜 부재는 *유지* 가 아니다 — 시계가 없으면 셀 수 없다.
  ② `state == REMOVED` → **유지**(폐기 완료 — 재평가 대상이 아니다)
  ③ `state == implemented` → **재평가필요**. ⛔ 실측 선례(2026-08-24): 5건 중 **3건이 이미 구현돼**
     있었고 원장이 현실을 반영하지 못했다. 처분(종결)은 사용자 결정이다.
  ④ `state == DEFERRED` → 기준일 + **6개월** 경과 시 재평가필요
  ⑤ 그 외 → 기준일 + **3개월** 경과 시 재평가필요

⛔ **시계는 `max(base_date, last_eligible)`** 다. 정책이 *"eligible session **없이** 3개월"* 이라
   했으므로 유효 관측이 시계를 **갱신**한다. ⛔ 같은 세션의 중복 관측은 1회로 센다(원장 규약) —
   호출부가 session id 로 중복을 제거해 `last_eligible` 을 넘긴다.

⛔ **3개월은 90일이 아니다.** 월 연산으로 더한다(월말은 그 달의 마지막 날로 clamp).
   S16(레지스트리 stale)은 **일수** 를 쓰는데 대상이 다르다 — 저쪽은 *엔트리 신선도*, 이쪽은
   *승격 시계* 다. 단위를 통일하지 않고 각 대상의 정책 문구를 따른다.

원장 모드 `--ledger FILE` 은 승격 원장(modules/promotion-ledger.md)의 `### L-N:` 항목을 전부 판정해 보고한다.
  기준일 = 가장 이른 관측일 · 마지막 유효 관측일 = 카운트 보류 · 제외 · 관측 후보가 아닌 관측 중 가장 늦은 날.
  ⛔ 같은 OBS 세션은 1회로 센다 — 나중에 다시 적어도 그 세션의 첫 날짜만 쓴다(재기록이 시계를 되돌리지 않는다).
  ⛔ 보고만 한다 — 원장을 쓰거나 지우지 않는다. 처분(종결 · 연장)은 사용자 결정이다.

exit: 0=재평가 0건 · 1=재평가 필요 있음 · 2=판정 불가 있음(⛔ 통과 아님)
"""
from __future__ import annotations

import argparse
import calendar
import datetime
import re
import sys

RE_EVAL, KEEP, UNDECIDABLE = "재평가필요", "유지", "판정불가"
EXIT = {RE_EVAL: 1, KEEP: 0, UNDECIDABLE: 2}
MONTHS = {"DEFERRED": 6}
DEFAULT_MONTHS = 3
KNOWN_STATES = ("candidate", "DEFERRED", "implemented", "REMOVED")


def add_months(d: datetime.date, n: int) -> datetime.date:
    """월 연산. ⛔ 월말은 clamp — 11/30 + 3개월 = 2/28(윤년 2/29). 90일 더하기와 다르다."""
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return datetime.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def decide(track, state, base_date, last_eligible, now) -> tuple:
    """(판정, 사유). ⛔ 순서를 바꾸면 날짜 부재가 유지로 새어 나간다."""
    if state not in KNOWN_STATES:
        return UNDECIDABLE, f"상태 `{state}` 를 모른다 (아는 값: {'·'.join(KNOWN_STATES)})"
    if base_date is None:
        return UNDECIDABLE, "기준일이 없다 — 시계가 없으면 셀 수 없다(⛔ 유지 아님)"
    if state == "REMOVED":
        return KEEP, "폐기 완료 — 재평가 대상이 아니다"
    if state == "implemented":
        return RE_EVAL, "이미 구현됨 — 원장이 현실과 어긋난다(처분은 사용자 결정)"
    clock = max(d for d in (base_date, last_eligible) if d is not None)
    months = MONTHS.get(state, DEFAULT_MONTHS)
    due = add_months(clock, months)
    if now >= due:
        src = "마지막 유효 관측일" if last_eligible and last_eligible > base_date else "등록일"
        return RE_EVAL, f"{src} {clock} + {months}개월 = {due} 경과 (now {now})"
    return KEEP, f"시계 {clock} + {months}개월 = {due} 미도달 (now {now})"


ENTRY_RE = re.compile(r"^### (L-\d+):")
OBS_HEAD_RE = re.compile(r"^### (L-\d+) 관측")
DATE_RE = re.compile(r"(?:Date:\s*|,\s*)(\d{4}-\d{2}-\d{2})")
NOT_COUNTED = ("카운트 보류", "카운트 제외", "카운트 미반영", "관측 후보")
NOTE_RE = re.compile(r"^\s*-\s")                      # 관측 아래 하위 글머리 — 날짜 없는 제외 표지가 앞 관측을 세지 않게 한다
STATE_RE = re.compile(r"^\s*-\s*\**상태\**\s*[:：]\s*\**DEFERRED", re.M)   # 항목 상태 줄만 — 하위 조치 문장의 DEFERRED 는 상태가 아니다


def parse_ledger(text):
    """-> [{id, track, state, base, last, n_obs, n_counted}] — `### L-N:` 항목 + `### L-N 관측 …` 보강 절."""
    entries, order, cur, cur_counted, last = {}, [], None, True, None
    for line in text.splitlines():
        m, mo = ENTRY_RE.match(line), OBS_HEAD_RE.match(line)
        if line.startswith("### ") and not m and not mo:
            cur, last = None, None                       # REJECTED · 다른 절 — 항목 밖
            continue
        if m or mo:
            cur = (m or mo).group(1)
            if cur not in entries:
                entries[cur] = {"id": cur, "text": [], "recs": []}
                order.append(cur)
            cur_counted = not (mo and any(k in line for k in NOT_COUNTED))
            last = _add_obs(entries[cur], line, cur_counted) if mo else None
            entries[cur]["text"].append(line)
            continue
        if cur is None:
            continue
        entries[cur]["text"].append(line)
        dated = DATE_RE.search(line)
        if "관측 #" in line and dated:
            last = _add_obs(entries[cur], line, cur_counted and not any(k in line for k in NOT_COUNTED))
        elif dated:
            last = None                                  # 날짜 있는 다른 기록(관측 후보 등) — 아래 표지는 그 기록 몫이다
        elif last and NOTE_RE.match(line) and any(k in line for k in NOT_COUNTED):
            last[2] = False                              # 아래 줄의 '카운트 미반영' · '카운트 보류' — 그 기록 한 줄만
    out = []
    for k in order:
        e, body = entries[k], "\n".join(entries[k]["text"])
        e["obs"] = _merge(e["recs"])
        dates = [d for d, _ in e["obs"].values()]
        counted = [d for d, c in e["obs"].values() if c]
        tm = re.search(r"트랙 ([A-D])", body)
        state = ("REMOVED" if re.search(r"^### ~~", body, re.M) or "폐기" in body.splitlines()[0]
                 else "implemented" if "구현됨" in body
                 else "DEFERRED" if STATE_RE.search(body) else "candidate")
        out.append({"id": k, "track": tm.group(1) if tm else "A", "state": state,
                    "base": min(dates) if dates else None, "last": max(counted) if counted else None,
                    "n_obs": len(e["obs"]), "n_counted": len(counted)})
    return out


def _add_obs(entry, line, counted):
    """-> 관측 기록 [키, 날짜, 셈](날짜 없으면 None). 셈은 아래 표지가 바꿀 수 있어 OBS 병합은 끝에서 한다(_merge)."""
    dm = DATE_RE.search(line)
    if not dm:
        return None
    sm = re.search(r"OBS-\d+", line)
    rec = [sm.group(0) if sm else f"line:{len(entry['recs'])}", datetime.date.fromisoformat(dm.group(1)), counted]
    entry["recs"].append(rec)
    return rec


def _merge(recs):
    """-> {키: (첫 날짜, 셈)} — 같은 OBS 재기록은 한 관측이다. 한 기록이라도 세면 센다(재기록의 '미반영'이 원 관측을 지우지 않는다)."""
    obs = {}
    for key, d, counted in recs:
        first, was = obs.get(key, (d, False))
        obs[key] = (min(first, d), was or counted)
    return obs


def report_ledger(path, now):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError as e:
        print(f"❌ 원장을 읽지 못했다: {e}", file=sys.stderr)
        return 2
    rows = parse_ledger(text)
    if not rows:
        print("❌ 원장에 `### L-N:` 항목이 없다 — 판정 불가", file=sys.stderr)
        return 2
    n = dict.fromkeys(EXIT, 0)
    for r in rows:
        verdict, why = decide(r["track"], r["state"], r["base"], r["last"], now)
        n[verdict] += 1
        print(f"{r['id']}\ttrack={r['track']}\tstate={r['state']}\tbase={r['base']}\tlast={r['last']}\t"
              f"obs={r['n_obs']}(counted {r['n_counted']})\t→ {verdict} · {why}")
    print(f"ledger: {len(rows)} entries · {RE_EVAL} {n[RE_EVAL]} · {UNDECIDABLE} {n[UNDECIDABLE]} · {KEEP} {n[KEEP]} (보고만 — 원장은 바꾸지 않는다)")
    return 2 if n[UNDECIDABLE] else 1 if n[RE_EVAL] else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="candidate 만료 판정")
    ap.add_argument("--track", default="A")
    ap.add_argument("--state", default="candidate")
    ap.add_argument("--base-date")
    ap.add_argument("--last-eligible")
    ap.add_argument("--now", help="고정 시각 YYYY-MM-DD (미지정 시 오늘)")
    ap.add_argument("--ledger", help="승격 원장 파일 — 항목 전부를 판정해 보고(쓰지 않는다)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    def pd(v):
        if not v:
            return None
        try:
            return datetime.date.fromisoformat(v)
        except ValueError:
            print(f"❌ 날짜 형식 오류: {v}", file=sys.stderr)
            raise SystemExit(2)

    now = pd(args.now) or datetime.date.today()
    if args.ledger:
        return report_ledger(args.ledger, now)
    verdict, why = decide(args.track, args.state, pd(args.base_date), pd(args.last_eligible), now)
    print(f"track={args.track} state={args.state} → {verdict}")
    print(f"  {why}")
    return EXIT[verdict]


# ── self-test — 계획이 요구한 5종 + 경계 ────────────────────────────────────
def self_test() -> int:
    D = datetime.date.fromisoformat
    passed, fails = 0, []

    def case(name, want, track="A", state="candidate", base=None, last=None, now="2026-09-22", needle=None):
        nonlocal passed
        got, why = decide(track, state, D(base) if base else None,
                          D(last) if last else None, D(now))
        if got != want:
            fails.append(f"{name}: {got} (기대 {want}) · {why}")
        elif needle and needle not in why:
            fails.append(f"{name}: 사유에 {needle!r} 없음 — {why}")
        else:
            passed += 1

    # ① 경계 날짜 — 3개월 되는 날은 **경과**로 본다(>=)
    case("boundary-exact", RE_EVAL, base="2026-06-22", now="2026-09-22")
    case("boundary-minus1", KEEP, base="2026-06-22", now="2026-09-21")
    # ⛔ 월말 clamp — 90일 더하기와 다르다
    case("month-end-clamp", RE_EVAL, base="2025-11-30", now="2026-02-28")
    case("month-end-clamp-minus1", KEEP, base="2025-11-30", now="2026-02-27")
    # ② 날짜 누락 → 판정불가 (⛔ 유지 아님)
    case("no-base-date", UNDECIDABLE, base=None, needle="시계가 없으면")
    # ③ 같은 세션 중복 관측 — 호출부가 dedup 하므로 last_eligible 이 같으면 시계도 같다
    case("eligible-resets-clock", KEEP, base="2026-01-01", last="2026-09-01")
    case("duplicate-same-day-no-double-reset", KEEP, base="2026-01-01", last="2026-09-01",
         needle="2026-09-01")
    # ④ DEFERRED → 6개월
    case("deferred-3mo-keeps", KEEP, state="DEFERRED", base="2026-06-22", now="2026-09-22")
    case("deferred-6mo-reeval", RE_EVAL, state="DEFERRED", base="2026-03-22", now="2026-09-22",
         needle="6개월")
    # ⑤ 이미 구현된 항목 → 날짜와 무관하게 재평가
    case("implemented-reeval", RE_EVAL, state="implemented", base="2026-09-21",
         needle="원장이 현실과 어긋난다")
    # 보강 — REMOVED 는 유지 · 미지 상태는 판정불가
    case("removed-keeps", KEEP, state="REMOVED", base="2020-01-01")
    case("unknown-state", UNDECIDABLE, state="보류", base="2026-01-01", needle="모른다")

    for f in fails:
        print(f"  FAIL {f}")
    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
