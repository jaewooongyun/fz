#!/bin/bash
# Coverage Gate 의 **단위**와 **분모 조달** 회귀 판정 — 합성 fixture 를 만들어 산술로 잰다.
#
# ⛔ 여기서 막는 것은 "부분 측정이 100% 로 통과하는" 경로다. 게이트는 정상 작동하고
#    단위·조달원이 틀린다 — 실패가 숫자로 보이지 않는다.
#
# 회귀 3종:
#   S  section-claim   파일 1개 안의 항목 N개를 대상으로 하면 파일 단위로 1/1 = 100% 가 된다
#                      (fz-findings F-098: 35절 중 5절 검사 후 "전수 검사·위반 0건" 보고)
#   D  denominator     N 과 M 을 같은 정규식이 공급하면 놓친 항목이 분모에서도 사라진다
#                      (F-026: 깨진 열거로 5/5 = 100% green)
#   F  file-claim      ⛔ negative — 주장이 실제로 파일 단위면 파일 분모가 **정답**이다.
#                      '항목 단위' 일괄 강제는 정상 감사를 과구조화한다
#                      (harness-engineering §5 원칙 3: 과도하게 좁힌 구조도 해롭다)
#
# ⛔ 이 러너는 **산술만** 판정한다. 자연어 Gate 의 실제 준수는 fresh-context 외부 평가자가
#    이 시나리오를 재실행해 기대 단위·분모를 출력하는지로 판정한다 (§5.5 규율 2).
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "python3 이 없다" >&2; exit 2; }

TMP="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }
trap 'rm -rf "$TMP"' EXIT

FAIL=0
pass() { printf 'PASS  %-40s %s\n' "$1" "$2"; }
fail() { printf 'FAIL  %-40s %s\n' "$1" "$2"; FAIL=1; }

# ── S: section-claim — 파일 1개 / 항목 35개 ─────────────────────
mkdir -p "$TMP/s"
{ for i in $(seq 1 35); do echo "## $i. 항목$i"; done; } > "$TMP/s/target.md"

s_files=$(find "$TMP/s" -name '*.md' | wc -l | tr -d ' ')
s_items=$(command grep -c '^## ' "$TMP/s/target.md")
s_checked=5   # 5절만 검사한 상황

if [ "$s_files" -eq 1 ] && [ "$s_items" -eq 35 ]; then
  # 파일 단위 분모: 1/1 = 100% (통과) / 항목 단위: 5/35 = 14% (미달)
  file_pct=$(( 100 * s_files / s_files ))
  item_pct=$(( 100 * s_checked / s_items ))
  if [ "$file_pct" -eq 100 ] && [ "$item_pct" -lt 20 ]; then
    pass "S section-claim 5/35" "파일단위 ${file_pct}% 통과 vs 항목단위 ${item_pct}% — 단위가 판정을 가른다"
  else
    fail "S section-claim 5/35" "기대 file=100 item<20, 실측 file=$file_pct item=$item_pct"
  fi
else
  fail "S fixture 생성" "files=$s_files items=$s_items (기대 1 / 35)"
fi

# ── D: denominator — 같은 정규식 대 독립 조달 ────────────────────
mkdir -p "$TMP/d"
printf '## 5.1 절\n## §5.2 절\n## 5.3 절\n## §5.4 절\n' > "$TMP/d/target.md"

# 깨진 정규식(§ 접두 미고려)이 M 과 N 을 함께 공급
broken_m=$(command grep -cE '^## 5\.[0-9]' "$TMP/d/target.md" || true); broken_m=${broken_m:-0}
broken_n=$broken_m                       # 절차 6 "같은 명령 재실행"
# 독립 조달 — 필터 없는 전량 열거
indep_n=$(command grep -c '^## ' "$TMP/d/target.md")

if [ "$broken_m" -eq 2 ] && [ "$indep_n" -eq 4 ]; then
  same_pct=$(( 100 * broken_m / broken_n ))
  indep_pct=$(( 100 * broken_m / indep_n ))
  if [ "$same_pct" -eq 100 ] && [ "$indep_pct" -eq 50 ]; then
    pass "D same-source denominator" "재실행 ${same_pct}% 통과 vs 독립조달 ${indep_pct}% — 조달원이 판정을 가른다"
  else
    fail "D same-source denominator" "기대 same=100 indep=50, 실측 same=$same_pct indep=$indep_pct"
  fi
else
  fail "D fixture 생성" "broken_m=$broken_m indep_n=$indep_n (기대 2 / 4)"
fi

# ── F: file-claim (negative — 파일 분모가 정답) ──────────────────
# ⛔ 발화하지 **않아야** 하는 케이스. 주장이 "파일 2개를 다 읽었다" 면 파일 분모가 옳다.
mkdir -p "$TMP/f"
printf 'a\n' > "$TMP/f/one.md"; printf 'b\n' > "$TMP/f/two.md"
f_total=$(find "$TMP/f" -name '*.md' | wc -l | tr -d ' ')
f_read=2
f_pct=$(( 100 * f_read / f_total ))
if [ "$f_pct" -eq 100 ] && [ "$f_total" -eq 2 ]; then
  pass "F file-claim 2/2 (negative)" "파일 단위 주장에는 파일 분모가 정답 — 항목 강제는 과구조화"
else
  fail "F file-claim 2/2 (negative)" "기대 100% of 2, 실측 ${f_pct}% of $f_total"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "0 건 실패"
  echo "⛔ 이 통과는 **산술 재현**만 보증한다 — 자연어 Gate 준수는 외부 채점 1회가 별도 필수(§5.5 규율 2)"
  exit 0
else
  echo "⛔ 불일치 발생"
  exit 1
fi
