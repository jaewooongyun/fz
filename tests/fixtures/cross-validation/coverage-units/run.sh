#!/bin/bash
# Coverage Gate 의 **단위**와 **분모 조달** 회귀 판정 — 합성 입력을 산술로 잰다.
#
# ⛔ 여기서 막는 것은 "부분 측정이 100% 로 통과하는" 경로다. 게이트는 정상 작동하고
#    단위·조달원이 틀린다 — 실패가 숫자로 보이지 않는다.
#
# ⛔ **디스크에 쓰지 않는다.** 이전 판은 `mktemp -d` 로 fixture 를 만들었고, 그 때문에
#    읽기 전용 샌드박스의 외부 채점자가 러너를 실행하지 못해(exit 2) 산술을 손으로
#    재현해야 했다 [외부: codex, 2026-09-01 D-2 채점]. 검증자가 못 돌리는 오라클은
#    오라클이 아니다 — 입력을 전부 here-doc 으로 옮겼다.
#
# 회귀 5종:
#   S  section-claim   파일 1개 안의 항목 N개를 대상으로 하면 파일 단위로 1/1 = 100% 가 된다
#                      (fz-findings F-098: 35절 중 5절 검사 후 "전수 검사·위반 0건" 보고)
#   R  result-noun     ⛔ 결과 명사를 단위로 오인 — "위반 0건" 의 violation 을 단위로 잡으면
#                      0/0 이 되어 공허하게 100% 다. 단위는 감사 **대상**(rule)이어야 한다
#                      [외부: codex — "결과 건수는 커버리지 단위가 아니다"]
#   M  mixed-file      파일 통째 판정이 파일 안의 in-scope site 를 함께 폐기한다
#                      (Coverage Gate 절차 7 "분류 단위 = 사용 site" 와 같은 축)
#   D  denominator     N 과 M 을 같은 정규식이 공급하면 놓친 항목이 분모에서도 사라진다
#                      (F-026: 깨진 열거로 5/5 = 100% green)
#   F  file-claim      ⛔ negative — 주장이 실제로 파일 단위면 파일 분모가 **정답**이다.
#                      '항목 단위' 일괄 강제는 정상 감사를 과구조화한다
#                      (harness-engineering §5 원칙 3: 과도하게 좁힌 구조도 해롭다)
#
# ⛔ 이 러너는 **산술만** 판정한다 — 잘못된 단위가 위음성을 만든다는 반증 자료다.
#    자연어 문구의 **채택 시험**이 아니다: 고친 절차를 읽은 에이전트가 실제로 옳은 U 를
#    고르는지는 여기서 알 수 없다 (§5.5 규율 2 + `guides/prompt-optimization.md` self-eval).
#    미수행 항목은 아래 PENDING 행에 명시한다 — 조용히 빠뜨리지 않는다.
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

FAIL=0
pass() { printf 'PASS  %-40s %s\n' "$1" "$2"; }
fail() { printf 'FAIL  %-40s %s\n' "$1" "$2"; FAIL=1; }
skip() { printf 'PEND  %-40s %s\n' "$1" "$2"; }

# ── S: section-claim — 파일 1개 / 항목 35개 ─────────────────────
# diff-parse: 해당 없음 (diff 를 읽지 않는다 — 합성 마크다운 헤더를 센다)
s_body="$(for i in $(seq 1 35); do echo "## $i. 항목$i"; done)"
s_files=1
s_items=$(printf '%s\n' "$s_body" | command grep -c '^## ' || true); s_items=${s_items:-0}
s_checked=5   # 5절만 검사한 상황

if [ "$s_items" -eq 35 ]; then
  file_pct=$(( 100 * s_files / s_files ))
  item_pct=$(( 100 * s_checked / s_items ))
  if [ "$file_pct" -eq 100 ] && [ "$item_pct" -lt 20 ]; then
    pass "S section-claim 5/35" "파일단위 ${file_pct}% 통과 vs 항목단위 ${item_pct}% — 단위가 판정을 가른다"
  else
    fail "S section-claim 5/35" "기대 file=100 item<20, 실측 file=$file_pct item=$item_pct"
  fi
else
  fail "S 합성 입력" "items=$s_items (기대 35)"
fi

# ── R: result-noun — "총 위반 0건" 의 단위 오인 ──────────────────
# 감사 대상 = rule 12개. 그 중 4개만 검사했고 위반은 0건 나왔다.
r_rules=12
r_checked=4
r_violations=0
# (가) 결과 명사를 단위로: 발견 0 / 분모 0 → 나눌 것이 없어 공허하게 "전수" 로 읽힌다
r_vacuous=$([ "$r_violations" -eq 0 ] && echo 100 || echo 0)
# (나) 감사 대상을 단위로: 4/12
r_true_pct=$(( 100 * r_checked / r_rules ))
if [ "$r_vacuous" -eq 100 ] && [ "$r_true_pct" -lt 40 ]; then
  pass "R result-noun 0-violation" "결과명사 ${r_vacuous}% (공허) vs 대상단위 ${r_true_pct}% — 0건은 전수의 근거가 아니다"
else
  fail "R result-noun 0-violation" "기대 vacuous=100 true<40, 실측 $r_vacuous / $r_true_pct"
fi

# ── M: mixed-file — 파일 통째 판정이 in-scope site 를 폐기 ────────
# 3파일 / site 총 9개. file3 을 파일 단위로 out 판정하면 그 안의 in-scope site 2개가 사라진다
m_files=3
m_sites_total=9
m_sites_checked=5      # file1(5) 검사, file2(0), file3(4) 은 파일 통째 out
m_discarded_inscope=2  # file3 안에 있던 in-scope site
m_file_pct=$(( 100 * m_files / m_files ))
m_site_pct=$(( 100 * m_sites_checked / m_sites_total ))
if [ "$m_file_pct" -eq 100 ] && [ "$m_site_pct" -lt 60 ] && [ "$m_discarded_inscope" -gt 0 ]; then
  pass "M mixed-file site-loss" "파일단위 ${m_file_pct}% vs site단위 ${m_site_pct}% — in-scope site ${m_discarded_inscope}개 폐기"
else
  fail "M mixed-file site-loss" "기대 file=100 site<60 discarded>0, 실측 $m_file_pct / $m_site_pct / $m_discarded_inscope"
fi

# ── D: denominator — 같은 정규식 대 독립 조달 ────────────────────
d_body='## 5.1 절
## §5.2 절
## 5.3 절
## §5.4 절'
# 깨진 정규식(§ 접두 미고려)이 M 과 N 을 함께 공급
broken_m=$(printf '%s\n' "$d_body" | command grep -cE '^## 5\.[0-9]' || true); broken_m=${broken_m:-0}
broken_n=$broken_m                       # 절차 6 "같은 명령 재실행"
indep_n=$(printf '%s\n' "$d_body" | command grep -c '^## ' || true); indep_n=${indep_n:-0}

if [ "$broken_m" -eq 2 ] && [ "$indep_n" -eq 4 ]; then
  same_pct=$(( 100 * broken_m / broken_n ))
  indep_pct=$(( 100 * broken_m / indep_n ))
  if [ "$same_pct" -eq 100 ] && [ "$indep_pct" -eq 50 ]; then
    pass "D same-source denominator" "재실행 ${same_pct}% 통과 vs 독립조달 ${indep_pct}% — 조달원이 판정을 가른다"
  else
    fail "D same-source denominator" "기대 same=100 indep=50, 실측 same=$same_pct indep=$indep_pct"
  fi
else
  fail "D 합성 입력" "broken_m=$broken_m indep_n=$indep_n (기대 2 / 4)"
fi

# ── F: file-claim (negative — 파일 분모가 정답) ──────────────────
# ⛔ 발화하지 **않아야** 하는 케이스. 주장이 "파일 2개를 다 읽었다" 면 파일 분모가 옳다.
f_total=2
f_read=2
f_pct=$(( 100 * f_read / f_total ))
if [ "$f_pct" -eq 100 ]; then
  pass "F file-claim 2/2 (negative)" "파일 단위 주장에는 파일 분모가 정답 — 항목 강제는 과구조화"
else
  fail "F file-claim 2/2 (negative)" "기대 100% of 2, 실측 ${f_pct}%"
fi

# ── 미수행 항목 (조용히 빠뜨리지 않는다) ─────────────────────────
skip "5 fail-closed 미검증 처리" "독립 분모 부재 시 '커버리지 미검증' — D-3 미승격(세션 1/2)이라 오라클화 보류"
skip "6 동일 실패모드 쿼리 거부" "정규식·파서 공유 쿼리를 독립으로 인정 금지 — 동 D-3 범위"
skip "자연어 채택 시험" "변경 전/후 fresh-context 가 U 를 옳게 고르는지 — 산술로 대체 불가, 외부 평가자 몫"

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "0 건 실패 (5 케이스 판정 · 3 항목 미수행)"
  echo "⛔ 이 통과는 **산술 재현**만 보증한다 — 자연어 Gate 준수는 외부 채점이 별도 필수(§5.5 규율 2)"
  exit 0
else
  echo "⛔ 불일치 발생"
  exit 1
fi
