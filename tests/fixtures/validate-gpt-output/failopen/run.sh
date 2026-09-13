#!/bin/bash
# validate-gpt-output.py 의 **fail-open 회귀** 판정 — 위반 입력이 실제로 막히는지 잰다.
#
# ⛔ 여기서 막는 것은 "검증기가 통과를 인쇄하는데 그 통과가 아무것도 보장하지 않는" 경로다(F-216).
#    정상 입력만으로는 원리적으로 검출되지 않는다 — **위반 입력이 FAIL 을 내는 것을 본 뒤에야** 고쳤다고 말한다.
#
# 회귀 3종:
#   N  nan          `json.loads` 가 표준 밖 리터럴 NaN 을 받아들이면 이후 범위 비교가 **둘 다 False** 라
#                   minimum/maximum 위반이 검출되지 않고 GATE-PASS 가 인쇄된다
#   E  empty-array  미지원 키워드 검사가 **데이터를 따라가면** 빈 배열 아래 스키마에 도달하지 않는다 —
#                   `issues: []` 인 출력에서는 스키마가 깨져 있어도 통과한다
#   V  valid        ⛔ positive control. 이것이 막히면 반대 고장(정상 입력 차단)이고 그쪽도 결함이다
set -u
D="$(cd "$(dirname "$0")" && pwd)"
R="$(cd "$D/../../../.." && pwd)"
V="$R/scripts/validate-gpt-output.py"
[ -f "$V" ] || { echo "UNRUN — 검증기 없음: $V"; exit 2; }

fail=0
for c in nan empty-array; do
  [ -f "$D/$c.json" ] || { echo "UNRUN — fixture 없음: $c"; exit 2; }
  if python3 "$V" "$D/$c.json" "$D/$c.schema.json" >/dev/null 2>&1; then
    echo "FAIL($c): 위반 입력이 통과했다 — fail-open 잔존"; fail=1
  fi
done
if ! python3 "$V" "$D/valid.json" "$D/valid.schema.json" >/dev/null 2>&1; then
  echo "FAIL(valid): positive control 이 막혔다 — 정상 입력을 거부한다"; fail=1
fi
test "$fail" -eq 0 || exit 1
echo "VALIDATE_FAILOPEN_OK 3/3 (nan 차단 · empty-array 차단 · valid 통과)"
