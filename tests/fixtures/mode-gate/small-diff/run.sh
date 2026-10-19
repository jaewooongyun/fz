#!/bin/bash
# 작은 실제 패치 → exit 0 · light 추천 · 유효 줄 = 추가 줄 합
. "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
mkpatch 3 10
gate review --diff "$T/change.patch" > "$T/out.json"; rc=$?
[ "$rc" -eq 0 ] && [ "$(field "$T/out.json" "d['recommend']")" = light ] && [ "$(field "$T/out.json" "d['metrics']['lines']")" = 30 ] \
  && { echo "MODE_GATE_SMALL_OK"; exit 0; }
echo "FAIL  small-diff rc=$rc $(cat "$T/out.json")"; exit 1
