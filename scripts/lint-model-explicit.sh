#!/usr/bin/env bash
#
# scripts/lint-model-explicit.sh
# fz-plugin workflows 모델 배선 lint (deterministic — H1 원칙)
#
# 목적 (experiment-log §5.8 ⑤ 측정 지원 · Anti-Pattern Constraint 감시):
#   ① 전 workflow(workflows/*.js)의 agent 호출 opts 에 model: 명시 강제
#      → AC-6 (model 생략 전환 금지 — 생략 시 agent 정의 기본 model 로 강등)
#   ② repo 전체 model: 'fable' 총계 == EXPECTED_FABLE 고정
#      기대 분포: search-cross-verify.js ×1 + plan-collaborative.js ×2 = 3
#      → AC-1 ("fable 지정은 정확히 3곳") 양방향 강제: 무단 확산(>3) · 무단 제거(<3) 모두 차단
#      ⚠️ AC-5(C안 확산 금지: plan integrate·recheck / discover merge·landscape / review arch)는
#         *부분* 커버만 됨 — 이 검사는 총계 기반이라, 총계가 그대로 유지되는 swap(예: review-arch
#         호출에 fable 추가 + 기존 3곳 중 1곳을 다른 model 로 동시 변경 → 총계 3 유지)은 미탐.
#         단일 편집(총계 2/4 로 변화)은 정상 포착. same-total swap 은 AC-1 생산 스테이지 규칙 +
#         코드리뷰가 backstop (완전 자동 차단은 label-set 검사 필요).
#      ⛔ fable 지정 지점을 의도적으로 늘리거나 줄이면 아래 EXPECTED_FABLE 값도 함께 갱신할 것
#   ③ CLAUDE_CODE_SUBAGENT_MODEL 환경변수 설정 시 경고 (exit 0 유지 — 경고만)
#      → AC-2 (전면 override 금지 — workflow 의 model explicit 지정과 충돌 소지)
#
# 검사 원리: agent 호출 opts 리터럴은 전부 single-line 이며 'agentType:' 를 고유 마커로
#   갖는다 (주석의 destructuring {..model, agentType} 는 콜론이 없어 자동 제외). 따라서
#   'agentType:' 를 포함한 라인은 'model:' 도 같은 라인에 포함해야 한다.
#
# exit: 0=PASS / 1=lint 위반(model 누락 또는 fable≠기대) / 2=설정 오류(대상 미탐)

set -euo pipefail

# ── 대상 workflows 디렉토리: 인자 우선, 없으면 스크립트 위치 기준(scripts/의 부모/workflows) ──
#    (git rev-parse 대신 스크립트 상대 경로 — 임시 사본 디렉토리(비-git repo 포함)에서도 동작)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKFLOWS_DIR="${1:-$(dirname "$SCRIPT_DIR")/workflows}"

if [ ! -d "$WORKFLOWS_DIR" ]; then
  echo "❌ lint-model-explicit: workflows 디렉토리 없음: $WORKFLOWS_DIR" >&2
  exit 2
fi

EXPECTED_FABLE=3

# ── ① model 명시 검사: agentType: 마커 라인은 model: 도 포함해야 함 ──
#    (grep -nH: 대상 .js 가 1개뿐인 $1 디렉토리에서도 'file:line:' 접두 보장 — file/line 파싱 안정)
missing=0
checked=0
while IFS= read -r hit; do
  checked=$((checked + 1))
  if ! printf '%s\n' "$hit" | grep -Eq 'model[[:space:]]*:'; then
    file="${hit%%:*}"
    rest="${hit#*:}"
    lineno="${rest%%:*}"
    echo "❌ model 누락: ${file}:${lineno}" >&2
    missing=$((missing + 1))
  fi
done < <(grep -nHE 'agentType[[:space:]]*:' "$WORKFLOWS_DIR"/*.js)

if [ "$checked" -eq 0 ]; then
  echo "❌ lint-model-explicit: agent 호출(마커 agentType:)을 찾지 못함 — 대상 경로/포맷 확인: $WORKFLOWS_DIR" >&2
  exit 2
fi

# ── ② fable 지정 수 고정 검사 (grep no-match 시 pipefail 회피용 || true) ──
fable_count=$(grep -hoE "model[[:space:]]*:[[:space:]]*'fable'" "$WORKFLOWS_DIR"/*.js | wc -l | tr -d ' ') || true

# ── ③ 환경변수 일괄 override 경고 (AC-2 — exit 0 유지, 경고만) ──
if [ -n "${CLAUDE_CODE_SUBAGENT_MODEL:-}" ]; then
  echo "⚠️  경고: CLAUDE_CODE_SUBAGENT_MODEL='${CLAUDE_CODE_SUBAGENT_MODEL}' 설정됨 — AC-2 (전면 override 금지). workflow 의 model explicit 지정을 무력화할 수 있음."
fi

# ── 판정 ──
fail=0
if [ "$missing" -gt 0 ]; then
  echo "❌ lint-model-explicit: model 누락 ${missing}건 (AC-6 위반)" >&2
  fail=1
fi
if [ "$fable_count" -ne "$EXPECTED_FABLE" ]; then
  echo "❌ lint-model-explicit: fable 지정 수 ${fable_count} ≠ 기대 ${EXPECTED_FABLE} (AC-1 '정확히 3곳' 위반: >3 확산 / <3 제거) — 의도적 변경이면 EXPECTED_FABLE 갱신 필요. 현재 위치:" >&2
  grep -nHE "model[[:space:]]*:[[:space:]]*'fable'" "$WORKFLOWS_DIR"/*.js >&2 || true
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "lint-model-explicit: PASS (${checked} calls checked, fable=${fable_count})"
