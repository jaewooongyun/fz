#!/bin/bash
# risk_scan.py 회귀 판정 — expected.json 과 실제 출력을 대조한다.
#
# ⛔ 눈으로 보지 않는다. 표를 읽고 "맞네" 하는 것은 판정이 아니다 —
#    다음 사람이 같은 표를 다시 읽어야 하고, 기대값이 어디에도 고정되지 않는다.
#
# exit: 0 전건 일치 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAN="$HERE/../../../../skills/fz-peer-review/scripts/risk_scan.py"
EXPECTED="$HERE/expected.json"

[ -f "$SCAN" ] || { echo "risk_scan.py 를 찾을 수 없다: $SCAN" >&2; exit 2; }
[ -f "$EXPECTED" ] || { echo "expected.json 이 없다" >&2; exit 2; }

python3 - "$SCAN" "$EXPECTED" "$HERE" <<'PY'
import json, subprocess, sys, os
scan, expected_path, here = sys.argv[1], sys.argv[2], sys.argv[3]
cases = json.load(open(expected_path, encoding="utf-8"))["cases"]

fail = 0
for name in sorted(cases):
    patch = os.path.join(here, name + ".patch")
    if not os.path.exists(patch):
        print("FAIL  %-32s fixture 파일 없음" % name); fail += 1; continue
    r = subprocess.run([sys.executable, scan, patch, "--json"], capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL  %-32s exit %d" % (name, r.returncode)); fail += 1; continue
    got = json.loads(r.stdout)
    exp = cases[name]
    bad = [k for k in ("risk", "added_lines") if k in exp and got.get(k) != exp[k]]
    if bad:
        detail = ", ".join("%s: %s≠%s" % (k, got.get(k), exp[k]) for k in bad)
        print("FAIL  %-32s %s" % (name, detail)); fail += 1
    else:
        print("PASS  %-32s risk=%d added=%d" % (name, got["risk"], got["added_lines"]))

print()
print("%d/%d 통과" % (len(cases) - fail, len(cases)))
sys.exit(1 if fail else 0)
PY
