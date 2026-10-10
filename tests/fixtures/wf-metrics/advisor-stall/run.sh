#!/bin/bash
# advisor 스톨 · 재시도 시도 구분 fixture (F-382 · F-387) — 합성 트랜스크립트 · journal 을 대상 트리의 fz_wf_metrics 로
# 모듈(read_wf)과 CLI(--wf 상세 · --row) 둘 다 판독해, 셀 정의에서 직접 센 정답과 대조한다(cells.py).
#   stall     호출 2 · 결과 1 / 결과 중복(1회로) / 결과 없음 / advisor 없음 / 대조(1 · 1) — advisor_calls · advisor_stalled 가
#             호출 수와 무결과 수를 가르고, 기존 advisor(결과 기반 · tool_use_id 중복 제거)는 그대로인가
#   attempts  같은 key 실패 1 + 재개 1 / 여러 key 일부 성공 · 일부 실패 뒤 재개(결과 재사용 key 는 wall · 크리티컬 패스 밖
#             reused_agents · reused_span) / failed 없는 단일 시도 대조(전 agent min~max) / 모호 경계 4종 — 각 셀이 조건 하나만 친다:
#             resume-unproven(failed 뒤 첫 started 가 실패 key 재기동 아님) · no-resume(마지막 failed 뒤 started 없음) ·
#             restart-after-boundary(경계 뒤 같은 key 재기동) · unplaced(journal 에 없는 트랜스크립트) → wall · critical_path UNRUN
#   경계 = 마지막 failed 뒤 첫 started — journal 에 시각이 없어 이벤트 순서만이 근거다.
# 실패 태그(줄 머리 METRICS-FAIL:): advisor_stalled-missing · advisor_stalled-mismatch · advisor_calls-missing · advisor_calls-mismatch ·
#   advisor-changed · attempt-wall-mismatch(모듈 · 상세 · --row 의 wall 이 마지막 시도 값이 아니거나 모호인데 값을 냄) ·
#   attempt-critical-path-mismatch · attempt-fields-missing · attempt-failed-attempts-mismatch · attempt-reused-mismatch ·
#   attempt-failed-span-mismatch · attempt-unrun-reason-mismatch · agents-changed ·
#   cell-set-mismatch(판정한 셀 이름이 고정 집합 — stall 5 · attempts 7 — 과 다르다, F-408). 끝 줄 `CELLS n=<수> ran=<…>`
# ⛔ --expect 로는 이 판정이 안 된다 — 기준 트리의 --expect 는 wall_s · agents · advisor 만 비교해 새 키를 모르고 METRICS_OK 를 낸다.
# exit: 0 전건 통과(인자 없이 = 전 셀이면 마지막 줄 ADVISOR-STALL-ATTEMPTS-OK) · 1 METRICS-FAIL 태그 1건 이상 ·
#       2 준비 실패(줄 머리 UNRUN:) 또는 traceback — 인프라 고장을 단언 실패(1)와 섞지 않는다
# ⛔ 대상 트리에는 쓰지 않는다(python -B — __pycache__ 도 남기지 않는다). 셀은 기본 TMPDIR 의 임시 폴더에 만들고 지운다.
# usage: run.sh [--tree <플러그인 트리>] [--cells stall|attempts]   (기본: 이 fixture 가 든 트리 · 전 셀 — health-check 글롭이 인자 없이 부른다)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
TREE="$(cd "$HERE/../../../.." 2>/dev/null && pwd)"
CELLS=all
while [ $# -gt 0 ]; do
  case "$1" in
    --tree)  [ $# -ge 2 ] || { echo "UNRUN: --tree 에 경로가 없다"; exit 2; }
             TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "UNRUN: --tree 경로 없음: $2"; exit 2; }; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "UNRUN: --cells 에 값이 없다"; exit 2; }
             case "$2" in stall|attempts) CELLS="$2" ;; *) echo "UNRUN: --cells 는 stall|attempts — 받은 값 $2"; exit 2 ;; esac
             shift 2 ;;
    *) echo "UNRUN: 알 수 없는 인자: $1"; exit 2 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 부재"; exit 2; }
[ -n "$TREE" ] && [ -f "$TREE/scripts/fz_wf_metrics.py" ] || { echo "UNRUN: 대상 계측기 없음: ${TREE:-?}/scripts/fz_wf_metrics.py"; exit 2; }
[ -f "$HERE/cells.py" ] || { echo "UNRUN: cells.py 없음: $HERE"; exit 2; }
PYTHONDONTWRITEBYTECODE=1 python3 -B "$HERE/cells.py" "$TREE" "$CELLS"
