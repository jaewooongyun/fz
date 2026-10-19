#!/bin/bash
# 큰 실제 패치(유효 600줄) → exit 0 · full 추천 · 근거에 줄 임계
. "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
mkpatch 2 300
gate review --diff "$T/change.patch" > "$T/out.json"; rc=$?
[ "$rc" -eq 0 ] && [ "$(field "$T/out.json" "d['recommend']")" = full ] && field "$T/out.json" "d['reasons'][0]" | grep -q '600줄' \
  && { echo "MODE_GATE_BIG_OK"; exit 0; }
echo "FAIL  big-diff rc=$rc $(cat "$T/out.json")"; exit 1
