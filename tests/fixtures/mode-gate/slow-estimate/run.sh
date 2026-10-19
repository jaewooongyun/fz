#!/bin/bash
# 추정: 가짜 보고서는 중앙값·N 을 싣고, 느린 보고서는 상한 뒤 estimate null 로 계속한다(추천은 그대로)
# 느린 보고서 30초 · 단언 20초 미만 — 상한이 고장 나면 30초를 기다려 FAIL, 부하가 있어도 상한 1초 + 기동 시간은 20초 안이다
. "$(dirname "${BASH_SOURCE[0]}")/../_lib.sh"
printf '1\t0\ta.txt\n' > "$T/n.txt"
cat > "$T/fake.py" <<'PY'
import json, sys
json.dump({"workflows": [{"workflow": "review-live", "wall_median_min": 19.5, "wall_n": 22}]}, open(sys.argv[sys.argv.index("--out") + 1], "w"))
PY
printf 'import time\ntime.sleep(30)\n' > "$T/slow.py"
FZ_MODE_GATE_REPORTER="$T/fake.py" gate review --numstat "$T/n.txt" --estimate review-live > "$T/a.json"; a=$?
S=$(date +%s); FZ_MODE_GATE_REPORTER="$T/slow.py" FZ_MODE_GATE_ESTIMATE_SEC=1 gate review --numstat "$T/n.txt" --estimate review-live > "$T/b.json"; b=$?; E=$(( $(date +%s) - S ))
[ "$a" -eq 0 ] && [ "$(field "$T/a.json" "d['estimate']['n']")" = 22 ] && [ "$b" -eq 0 ] && [ "$(field "$T/b.json" "d['estimate']")" = None ] \
  && [ "$(field "$T/b.json" "d['recommend']")" = light ] && [ "$E" -lt 20 ] && { echo "MODE_GATE_ESTIMATE_OK"; exit 0; }
echo "FAIL  slow-estimate a=$a b=$b elapsed=${E}s"; exit 1
