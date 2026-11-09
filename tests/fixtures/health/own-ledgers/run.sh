#!/bin/bash
# gpt-cli: none — health-check 를 --block ledgers 로만 부른다(§4.5 에 닿지 않는다)
# health-check 2.7 원장 범위 회귀 판정 (F-265) — 다른 티켓 원장의 계약 위반이 플러그인 health-check 를 빨갛게 하지 않는다.
#
# health-check 는 호출 CWD 아래 원장을 찾는다(hook 미설치 머신의 노출 경로). 그 아래 다른 티켓의 원장이 계약을 어기면
# 플러그인 결함이 아닌데도 실패로 표시됐다. 이 플러그인 트리 · 이 세션 WORK_DIR(FZ_WORK_DIR) 밖의 위반은 제외 수로만 낸다.
# 셀:
#   f265-foreign-ledger-skipped  위반 원장이 FZ_WORK_DIR 밖뿐 → 원장 상태 0 · 비고에 '제외 1'
#   f265-own-ledger-fails        위반 원장이 FZ_WORK_DIR 안에 있다 → 원장 상태 1(짝 — 제외가 소유 위반을 숨기지 않는다)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(cd "$HERE/../../../.." && pwd)"
HC="$TREE/scripts/health-check.sh"
[ -f "$HC" ] || { echo "SETUP health-check.sh 없음: $HC"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-own-ledgers.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT
broken() {   # ROOT 헤더 없는 원장 — 계약 위반(exit 3)
  mkdir -p "$1/gates" && printf '# Gates: 깨진 원장\nSTATE: active\n\n- [ ] G1: x\n  CHECK: echo ok\n  EXPECT: ok\n  EVIDENCE: pending\n' > "$1/gates/plan.md"
}
broken "$TMP/work/other" || { echo "SETUP 원장 준비 실패"; exit 3; }
mkdir -p "$TMP/work/own" || exit 3

fail=0
row() { printf '%s\n' "$1" | grep -F '게이트 원장 상태 |' | head -1; }

out="$(cd "$TMP/work" && FZ_WORK_DIR="$TMP/work/own" bash "$HC" --block ledgers 2>&1)"
r="$(row "$out")"
if printf '%s' "$r" | grep -q '^✅ 게이트 원장 상태 | 0 |' && printf '%s' "$r" | grep -q '제외 1'; then
  echo "PASS  f265-foreign-ledger-skipped"
else
  echo "FAIL  f265-foreign-ledger-skipped  — 행: ${r:-(없음)} · 출력: $(printf '%s' "$out" | tr '\n' '|' | cut -c1-200)"; fail=$((fail + 1))
fi

broken "$TMP/work/own" || { echo "SETUP 소유 원장 준비 실패"; exit 3; }
out="$(cd "$TMP/work" && FZ_WORK_DIR="$TMP/work/own" bash "$HC" --block ledgers 2>&1)"
r="$(row "$out")"
if printf '%s' "$r" | grep -q '^⛔ 게이트 원장 상태 | 1 |' && printf '%s' "$r" | grep -q '소유 1'; then
  echo "PASS  f265-own-ledger-fails"
else
  echo "FAIL  f265-own-ledger-fails  — 행: ${r:-(없음)}"; fail=$((fail + 1))
fi

echo "$fail 건 실패"
[ "$fail" -eq 0 ] || exit 1
echo "OWN_LEDGERS_OK"
