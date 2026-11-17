#!/bin/bash
# 모델 환경 변수 경고 fixture — `lint-model-explicit.sh` ③ 이 workflow 의 model 명시를 실제로 덮을 수 있는 변수에만 경고하는지 동작으로 본다.
#   현행 결정 순서(guides/model-guide.md § 서브에이전트 · 워크플로)에서 CLAUDE_CODE_SUBAGENT_MODEL 단독은 기본값이라 호출별 model 보다 아래다.
#   덮을 수 있는 쪽은 CLAUDE_CODE_SUBAGENT_MODEL_FORCE · CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL 이다.
#   unset          세 변수 모두 없음 → exit 0 · 경고(⚠️) 0 · 정보(ℹ️) 0 · 마지막 줄 PASS
#   subagent-only  CLAUDE_CODE_SUBAGENT_MODEL 만 → exit 0 · 경고 0 · 정보 1 · 마지막 줄 PASS
#   force          CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1 만 → exit 0 · 그 변수를 짚는 경고 1 · 마지막 줄 PASS
#   workflow       CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL 만 → exit 0 · 그 변수를 짚는 경고 1 · 마지막 줄 PASS
# 기준 트리는 CLAUDE_CODE_SUBAGENT_MODEL 하나만 보고 경고한다 → force · workflow 셀(경고 0)과 subagent-only 셀(경고 1)이 실패한다 → 이 fixture exit 1.
# ⛔ 셀마다 `env -u` 로 세 변수를 지운 뒤 그 셀의 변수만 둔다 — lint 는 자기를 돌린 프로세스의 env 만 읽는다. 격리하지 않으면 개발자 셸에 따라
#    결과가 갈린다. 그래서 이 러너는 시작할 때 세 변수를 일부러 채워 둔다 — 한 셀이라도 격리를 빠뜨리면 unset 셀이 실패한다.
# ⛔ 마지막 줄 PASS 를 셀마다 본다 — health-check 는 lint 출력의 마지막 줄만 기록한다. 경고가 PASS 뒤에 찍히면 요약이 경고를 숨긴다.
# 기대 셀 집합(F-408): 판정한 셀이 EXPECTED 와 정확히 같지 않으면 단언 실패 — 끝 줄에 실제로 돈 셀 목록 · 수를 찍는다.
# ⛔ 트리 · 레지스트리에 쓰지 않는다(lint 는 workflows 를 읽기만 한다).
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(인자 · 트리 · env -u 부재)
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
[ -f "$LINT" ] || { echo "SETUP 없음: $LINT"; exit 3; }
[ -d "$R/workflows" ] || { echo "SETUP workflows 없음: $R"; exit 3; }
env -u CLAUDE_CODE_SUBAGENT_MODEL true 2>/dev/null || { echo "SETUP env -u 를 쓸 수 없다"; exit 3; }

# 뒤섞인 개발자 셸을 흉내 낸다 — 셀의 `env -u` 가 이것을 지워야 한다
export CLAUDE_CODE_SUBAGENT_MODEL=opus CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1 CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=sonnet

EXPECTED="unset subagent-only force workflow"
RAN="" FAILS=0 N=0

check() {   # $1 셀 · $2 0/1(참) · $3 단언 · $4 실패 상세
  N=$((N + 1))
  case " $RAN " in *" $1 "*) ;; *) RAN="${RAN:+$RAN }$1" ;; esac
  if [ "$2" = 0 ]; then echo "PASS  $1: $3"; else echo "FAIL  $1: $3 · $4"; FAILS=$((FAILS + 1)); fi
}

measure() {  # OUT · RC 에서 경고 수 W · 정보 수 I · 마지막 줄 LAST 를 뽑는다
  W="$(printf '%s\n' "$OUT" | /usr/bin/grep -c '⚠️')"
  I="$(printf '%s\n' "$OUT" | /usr/bin/grep -c 'ℹ️')"
  LAST="$(printf '%s\n' "$OUT" | tail -1)"
}

ends_pass() {  # $1 셀 — exit 0 이고 마지막 줄이 PASS 판정 줄이다
  [ "$RC" = 0 ] && case "$LAST" in "lint-model-explicit: PASS"*) true ;; *) false ;; esac
  check "$1" $? "exit 0 · 마지막 줄 PASS" "rc=$RC last=$LAST"
}

# ── unset — 세 변수 모두 없음 ───────────────────────────────────
OUT="$(env -u CLAUDE_CODE_SUBAGENT_MODEL -u CLAUDE_CODE_SUBAGENT_MODEL_FORCE -u CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL bash "$LINT" 2>&1)"; RC=$?
measure
ends_pass unset
[ "$W" = 0 ] && [ "$I" = 0 ]; check unset $? "경고 0 · 정보 0" "warn=$W info=$I"

# ── subagent-only — 기본값 변수만: 명시 model 을 덮지 않는다 → 정보 줄 ─────
OUT="$(env -u CLAUDE_CODE_SUBAGENT_MODEL -u CLAUDE_CODE_SUBAGENT_MODEL_FORCE -u CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL CLAUDE_CODE_SUBAGENT_MODEL=haiku bash "$LINT" 2>&1)"; RC=$?
measure
ends_pass subagent-only
[ "$W" = 0 ]; check subagent-only $? "경고 0 (기본값은 호출별 model 보다 아래다)" "warn=$W"
[ "$I" = 1 ] && printf '%s\n' "$OUT" | /usr/bin/grep 'ℹ️' | /usr/bin/grep -qF "CLAUDE_CODE_SUBAGENT_MODEL='haiku'"; check subagent-only $? "정보 1 · 값을 짚는다" "info=$I"

# ── force — FORCE 만: 메인 대화 모델로 일괄 → 경고 ──────────────────
OUT="$(env -u CLAUDE_CODE_SUBAGENT_MODEL -u CLAUDE_CODE_SUBAGENT_MODEL_FORCE -u CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1 bash "$LINT" 2>&1)"; RC=$?
measure
ends_pass force
[ "$W" = 1 ] && printf '%s\n' "$OUT" | /usr/bin/grep '⚠️' | /usr/bin/grep -qF 'CLAUDE_CODE_SUBAGENT_MODEL_FORCE'; check force $? "경고 1 · CLAUDE_CODE_SUBAGENT_MODEL_FORCE 를 짚는다" "warn=$W"
[ "$I" = 0 ]; check force $? "정보 0" "info=$I"

# ── workflow — WORKFLOW 변수만: 워크플로 에이전트를 한 모델로 → 경고 ─────────
OUT="$(env -u CLAUDE_CODE_SUBAGENT_MODEL -u CLAUDE_CODE_SUBAGENT_MODEL_FORCE -u CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL=haiku bash "$LINT" 2>&1)"; RC=$?
measure
ends_pass workflow
[ "$W" = 1 ] && printf '%s\n' "$OUT" | /usr/bin/grep '⚠️' | /usr/bin/grep -qF "CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL='haiku'"; check workflow $? "경고 1 · CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL 값을 짚는다" "warn=$W"
[ "$I" = 0 ]; check workflow $? "정보 0" "info=$I"

# ── F-408 — 판정한 셀 = 기대 셀 ───────────────────────────────────
miss="" extra=""
for c in $EXPECTED; do case " $RAN " in *" $c "*) ;; *) miss="$miss $c" ;; esac; done
for c in $RAN; do case " $EXPECTED " in *" $c "*) ;; *) extra="$extra $c" ;; esac; done
if [ -n "$miss$extra" ]; then echo "FAIL  기대 셀 집합 — 빠짐[${miss# }] · 더함[${extra# }]"; FAILS=$((FAILS + 1)); fi
echo
set -- $RAN
if [ "$FAILS" -gt 0 ]; then
  echo "MODEL_EXPLICIT_ENV_FAIL fail=$FAILS ran=$#($RAN) checks=$N"
  exit 1
fi
echo "MODEL_EXPLICIT_ENV_OK ran=$#($RAN) checks=$N"
exit 0
