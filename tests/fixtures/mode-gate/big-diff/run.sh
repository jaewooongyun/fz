#!/bin/bash
# 큰 실제 패치 — 큼 AND 복잡: 20파일 · 유효 1000줄 → full · 2파일 · 1200줄(큼만) → light · 근거에 두 절
. "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
mkpatch 20 50
gate review --diff "$T/change.patch" > "$T/out.json"; rc=$?
mkpatch 2 600
gate review --diff "$T/change.patch" > "$T/out2.json"; rc2=$?
[ "$rc" -eq 0 ] && [ "$(field "$T/out.json" "d['recommend']")" = full ] && field "$T/out.json" "d['reasons'][0]" | grep -q '1000줄' \
  && [ "$rc2" -eq 0 ] && [ "$(field "$T/out2.json" "d['recommend']")" = light ] && field "$T/out2.json" "d['reasons'][1]" | grep -q '복잡 미충족' \
  && { echo "MODE_GATE_BIG_OK"; exit 0; }
echo "FAIL  big-diff rc=$rc/$rc2 $(cat "$T/out.json") $(cat "$T/out2.json")"; exit 1
