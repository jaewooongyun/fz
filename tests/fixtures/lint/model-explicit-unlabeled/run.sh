#!/bin/bash
# label 없는 agentType 호출 fixture (F-335 ⑲) — `lint-model-explicit.sh --baseline` 이 label 없는 호출을 비교에 넣는지 동작으로 본다.
#   clean      이 트리 workflows 사본 그대로 → exit 0 · '전건 일치' (현 트리 오탐 0)
#   unlabeled  사본 끝에 label 없는 agentType 호출 1줄(model 'sonnet' · effort 'low') → exit 1 · `추가된 호출: <파일>::line<N>`
#   labeled    같은 줄에 baseline 에 없는 label 을 붙인다 → exit 1 · `추가된 호출: <파일>::<label>` (심은 자리가 lint 에 닿는다는 양성 대조)
#   comment    label 없는 agentType 을 주석 줄로만 둔다 → exit 0 (주석은 호출이 아니다 — 고친 뒤에도 유지)
# 기준 트리는 label 없는 줄을 `continue` 로 건너뛰어 unlabeled 셀이 exit 0 으로 통과한다 → 이 fixture exit 1.
# 기대 셀 집합(F-408): 판정한 셀이 EXPECTED 와 정확히 같지 않으면 단언 실패 — 끝 줄에 실제로 돈 셀 목록 · 수를 찍는다.
# ⛔ 임시 폴더만 쓴다(트리 · 레지스트리 쓰기 없음).
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · 임시 폴더 · 심을 자리 없음)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 결함 재현 없이 통과한다 — 그래서 3 이다.
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 fixture 가 든 트리)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
LINT="$R/scripts/lint-model-explicit.sh"
BASE="$R/tests/fixtures/model-effort-baseline.json"
for f in "$LINT" "$BASE"; do [ -f "$f" ] || { echo "SETUP 없음: $f"; exit 3; }; done
[ -d "$R/workflows" ] || { echo "SETUP workflows 없음: $R"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "SETUP mktemp 실패"; exit 3; }; T="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 해석 실패"; exit 3; }
trap 'rm -rf "${T:?}"' EXIT

EXPECTED="clean unlabeled labeled comment"
TARGET="code-pair.js"          # 심을 워크플로 — 사본 끝에 붙인다
RAN="" FAILS=0 N=0

check() {   # $1 셀 · $2 0/1(참) · $3 단언 · $4 실패 상세
  N=$((N + 1))
  case " $RAN " in *" $1 "*) ;; *) RAN="${RAN:+$RAN }$1" ;; esac
  if [ "$2" = 0 ]; then echo "PASS  $1: $3"; else echo "FAIL  $1: $3 · $4"; FAILS=$((FAILS + 1)); fi
}

mkcopy() {  # $1 셀 이름 → 사본 경로 출력. 심을 파일이 없으면 준비 실패
  local d="$T/$1"
  cp -R "$R/workflows" "$d" || { echo "SETUP 워크플로 사본 실패" >&2; return 3; }
  [ -f "$d/$TARGET" ] || { echo "SETUP 심을 파일 없음: workflows/$TARGET" >&2; return 3; }
  printf '%s' "$d"
}

run_lint() {  # $1 사본 → OUT · RC
  OUT="$(bash "$LINT" --baseline "$BASE" "$1" 2>&1)"; RC=$?
}

# ── clean — 사본 그대로 ─────────────────────────────────────────
d="$(mkcopy clean)" || exit 3
run_lint "$d"
[ "$RC" = 0 ] && printf '%s\n' "$OUT" | /usr/bin/grep -q '전건 일치'; check clean $? "--baseline exit 0 · 전건 일치(현 트리 오탐 0)" "rc=$RC $(printf '%s' "$OUT" | tail -2 | tr '\n' ' ')"

# ── unlabeled — label 없는 호출 1줄 ──────────────────────────────
d="$(mkcopy unlabeled)" || exit 3
printf '%s\n' "  await agent('fixture', { agentType: 'fz:plan-structure', model: 'sonnet', effort: 'low' })" >> "$d/$TARGET"
n="$(wc -l < "$d/$TARGET" | tr -d ' ')"
run_lint "$d"
[ "$RC" = 1 ]; check unlabeled $? "--baseline exit 1" "rc=$RC"
printf '%s\n' "$OUT" | /usr/bin/grep -qF "추가된 호출: $TARGET::line$n "; check unlabeled $? "위반이 심은 줄의 키 $TARGET::line$n 이다" "$(printf '%s' "$OUT" | tail -3 | tr '\n' ' ')"

# ── labeled — 같은 줄에 baseline 에 없는 label ────────────────────
d="$(mkcopy labeled)" || exit 3
printf '%s\n' "  await agent('fixture', { label: 'fixture-planted', agentType: 'fz:plan-structure', model: 'sonnet', effort: 'low' })" >> "$d/$TARGET"
run_lint "$d"
[ "$RC" = 1 ] && printf '%s\n' "$OUT" | /usr/bin/grep -qF "추가된 호출: $TARGET::fixture-planted "; check labeled $? "exit 1 · 추가된 호출 $TARGET::fixture-planted (심은 자리가 lint 에 닿는다)" "rc=$RC $(printf '%s' "$OUT" | tail -2 | tr '\n' ' ')"

# ── comment — 주석 줄의 agentType 은 호출이 아니다 ──────────────────
d="$(mkcopy comment)" || exit 3
printf '%s\n' "  // agent('fixture', { agentType: 'fz:plan-structure', model: 'sonnet', effort: 'low' })" >> "$d/$TARGET"
run_lint "$d"
[ "$RC" = 0 ]; check comment $? "--baseline exit 0 (주석 줄은 세지 않는다)" "rc=$RC $(printf '%s' "$OUT" | tail -2 | tr '\n' ' ')"

# ── F-408 — 판정한 셀 = 기대 셀 ───────────────────────────────────
miss="" extra=""
for c in $EXPECTED; do case " $RAN " in *" $c "*) ;; *) miss="$miss $c" ;; esac; done
for c in $RAN; do case " $EXPECTED " in *" $c "*) ;; *) extra="$extra $c" ;; esac; done
if [ -n "$miss$extra" ]; then echo "FAIL  기대 셀 집합 — 빠짐[${miss# }] · 더함[${extra# }]"; FAILS=$((FAILS + 1)); fi
echo
set -- $RAN
if [ "$FAILS" -gt 0 ]; then
  echo "MODEL_EXPLICIT_UNLABELED_FAIL fail=$FAILS ran=$#($RAN) checks=$N"
  exit 1
fi
echo "MODEL_EXPLICIT_UNLABELED_OK ran=$#($RAN) checks=$N"
exit 0
