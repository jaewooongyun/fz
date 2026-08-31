#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 exit code 만 본다. diff 파싱은 move_drift.py 소관.
# move_drift.py 회귀 판정 — 이동 감지 + 드리프트 3축.
#
# ⛔ 여기서 막는 것은 **오탐**이다. 개명 PR 에 발동하면 리뷰어가 무관한 데이터를 읽는다.
#    실측: 첫 조건식(`신규파일>0 && 삭제/추가>=0.5`)이 #4766(개명)을 "이동" 으로 잡았다 —
#    그 신규 파일은 **이미 base 에 머지된 중복 커밋분**이었다. 판정 대상을
#    `git cherry` 의 `+` 커밋분으로 좁혀 해소했고, 이 fixture 가 그것을 고정한다.
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MD="$HERE/../../../../skills/fz-peer-review/scripts/move_drift.py"
[ -f "$MD" ] || { echo "move_drift.py 없음: $MD" >&2; exit 2; }

fail=0
check() {
  local name="$1" patch="$2" want="$3"
  python3 "$MD" "$HERE/$patch" "test" > "$HERE/.out" 2>/dev/null
  local got=$?
  if [ "$got" = "$want" ]; then echo "PASS  $(printf '%-34s' "$name") exit=$got"
  else echo "FAIL  $(printf '%-34s' "$name") exit=$got, 기대 $want"; fail=$((fail+1)); fi
}
# 이동(파일 분리) → 발동
check "파일 분리 → 발동" positive-file-split.patch 0
# ⛔ 개명 → 미발동 (오탐 방어)
check "개명 → 미발동(오탐 방어)" negative-rename-only.patch 1

# A축이 실제로 드리프트를 잡는가 — 헤더가 그 파일에 없는 심볼을 가리킨다
python3 "$MD" "$HERE/positive-file-split.patch" test 2>/dev/null > "$HERE/.out"
if grep -q 'DetailPresentable' "$HERE/.out" && grep -q '못 찾음' "$HERE/.out"; then
  echo "PASS  $(printf '%-34s' "A축: 헤더가 없는 심볼 지목") DetailPresentable 포착"
else
  echo "FAIL  A축: 헤더 심볼 미포착 — 렌즈 A4 와 같은 자리를 놓쳤다"; fail=$((fail+1))
fi
# ⛔ 노이즈 방어 — Xcode 양식·지시자가 심볼로 잡히면 리포트가 쓸모없어진다
for w in Copyright Created MARK; do
  if grep -q "\`$w\`" "$HERE/.out"; then
    echo "FAIL  노이즈 '$w' 가 심볼로 잡혔다"; fail=$((fail+1))
  else echo "PASS  $(printf '%-34s' "노이즈 제외: $w") 없음"; fi
done
rm -f "$HERE/.out"
echo; echo "$fail 건 실패"; exit $((fail ? 1 : 0))
