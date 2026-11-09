#!/bin/bash
# gpt-cli: none — health-check 를 --block gate-selftest 로만 부른다(§4.5 에 닿지 않는다)
# health-check 2.5 게이트 self-test 실패 상세 판정 (F-394) — 실패하면 '아래 상세' 가 가리키는 FAIL 줄이 실제로 찍힌다.
#
# 이전 판은 비고에 '아래 상세' 라고 적고 report_and_exit 는 계약 lint 출력만 찍었다 — 어느 케이스가 깨졌는지 보려면
# gate_check --self-test 를 따로 다시 돌려야 했다. 트리 사본의 manifest 를 두 케이스로 줄이고(빨리 돈다) 한쪽 기대값을 틀리게 바꾼다.
# 셀:
#   f394-gate-fail-lines-shown   기대값이 틀린 사본 → exit 1 · '── 실패 상세 ──' 아래에 그 케이스의 FAIL 줄
#   f394-gate-pass-no-detail     그대로인 사본 → 실패 상세 절이 없다(짝 — 상세가 늘 찍히면 위 셀이 헛돈다)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(cd "$HERE/../../../.." && pwd)"
[ -f "$TREE/scripts/health-check.sh" ] || { echo "SETUP health-check.sh 없음: $TREE"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-gate-fail-detail.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT

copy() {   # $1=사본 폴더 · $2=틀리게 바꿀지(1/0)
  mkdir -p "$1/tests/fixtures" "$1/guides" "$1/skills" || return 1
  cp -R "$TREE/scripts" "$1/scripts" && cp -R "$TREE/tests/fixtures/gates" "$1/tests/fixtures/gates" || return 1
  python3 - "$1/tests/fixtures/gates/manifest.json" "$2" <<'PY'
import json, sys
p, broken = sys.argv[1], sys.argv[2] == "1"
d = json.load(open(p, encoding="utf-8"))
d["cases"] = d["cases"][:2]
if broken:
    d["cases"][0]["expect"]["exit"] = 0 if d["cases"][0]["expect"]["exit"] != 0 else 1
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(d["cases"][0]["id"])
PY
}

fail=0
BAD_ID="$(copy "$TMP/bad" 1)" || { echo "SETUP 사본 준비 실패(bad)"; exit 3; }
copy "$TMP/good" 0 >/dev/null || { echo "SETUP 사본 준비 실패(good)"; exit 3; }

out="$(bash "$TMP/bad/scripts/health-check.sh" --block gate-selftest 2>&1)"; rc=$?
detail="$(printf '%s\n' "$out" | sed -n '/^── 실패 상세 ──$/,$p')"
if [ "$rc" -eq 1 ] && printf '%s\n' "$detail" | grep -Eq "^ *FAIL $BAD_ID"; then
  echo "PASS  f394-gate-fail-lines-shown"
else
  echo "FAIL  f394-gate-fail-lines-shown  — exit $rc · 상세: $(printf '%s' "$detail" | tr '\n' '|' | cut -c1-200) · 출력 끝: $(printf '%s' "$out" | tail -2 | tr '\n' '|')"; fail=$((fail + 1))
fi

out="$(bash "$TMP/good/scripts/health-check.sh" --block gate-selftest 2>&1)"; rc=$?
if [ "$rc" -eq 2 ] && ! printf '%s\n' "$out" | grep -q '^── 실패 상세 ──$'; then
  echo "PASS  f394-gate-pass-no-detail"
else
  echo "FAIL  f394-gate-pass-no-detail  — exit $rc · 출력 끝: $(printf '%s' "$out" | tail -3 | tr '\n' '|')"; fail=$((fail + 1))
fi

echo "$fail 건 실패"
[ "$fail" -eq 0 ] || exit 1
echo "GATE_FAIL_DETAIL_OK"
