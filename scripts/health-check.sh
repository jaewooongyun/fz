#!/bin/bash
# fz 플러그인 통합 건강 체크 — `/fz-manage check` 의 실행체
#
# ⛔ 신설 근거 (2026-08-09 감사 ISSUE-010, CRITICAL):
#   `skills/fz-manage/SKILL.md` 의 인라인 블록이 ①`FZ_ROOT` 를 `$0` 에서 유도했고(인라인 블록에서
#   `$0` 은 **셸**이라 `/` 또는 호출자 CWD로 해석) ②세 명령을 status 캡처 없이 순차 실행해
#   **마지막 명령의 exit 이 앞의 실패를 덮었다**. 특히 freshness 는 `--strict` 없이 findings 를
#   출력하며 exit 0 을 내므로 lint 실패가 사라졌다.
#   ⛔ 같은 파일이 "exit code를 판정에 포함한다"고 규정하면서 그 규칙을 위반하고 있었다.
#
# 설계:
#   · 루트는 **자기 위치**에서 해석한다 (`BASH_SOURCE[0]` — `$0` 는 source 시 호출자를 가리킨다)
#   · 각 검사의 exit 을 **개별 캡처**해 표로 보고하고, 하나라도 실패면 **비0**으로 종료한다
#   · lint 의 SKIP(THRESHOLD·SEMANTIC) 건수를 **따로 표기**한다 — ⛔ SKIP 은 PASS 가 아니다
#
# usage: health-check.sh [--strict-freshness]
#   --strict-freshness : 최신성 findings 가 있으면 실패로 취급 (기본: 경고)
# exit: 0=전 검사 통과 / 1=검사 실패 있음 / 2=사전조건 실패
set -u

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SELF_DIR/.." && pwd)"
if [ ! -d "$ROOT/guides" ] || [ ! -d "$ROOT/skills" ]; then
  echo "⛔ 플러그인 루트가 아님: $ROOT" >&2
  exit 2
fi

# ⛔ 인자 루프 — `$1`만 보면 `--bogus --strict-freshness` 가 조용히 non-strict 로 돈다 (ISSUE-010)
STRICT_FRESHNESS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --strict-freshness) STRICT_FRESHNESS=1; shift ;;
    *) echo "⛔ 알 수 없는 인자: $1 (사용법: health-check.sh [--strict-freshness])" >&2; exit 2 ;;
  esac
done

NAMES=() CODES=() NOTES=()
UNRUN=0     # 실행되지 못한 검사 수 — ⛔ 0이 아니면 "전 검사 통과"라 말하지 않는다
record() { NAMES+=("$1"); CODES+=("$2"); NOTES+=("$3"); }

echo "══════════════════════════════════════════════════════════════"
echo "fz 건강 체크 — root $ROOT"
echo "══════════════════════════════════════════════════════════════"

# ── 0. 사전조건 — ⛔ 4R ISSUE-001: python3·lint 스크립트 부재가 "일반 실패"로 분류됐다.
#    도구·자산 부재는 **미실행**이며 실패와 구별해야 한다.
for dep in python3 git; do
  command -v "$dep" >/dev/null 2>&1 || { echo "⛔ 사전조건 부재: $dep" >&2; exit 2; }
done
for f in lint_contracts.py lint-model-explicit.sh lint_doc_freshness.py; do
  [ -f "$ROOT/scripts/$f" ] || { echo "⛔ 검사 스크립트 부재: scripts/$f" >&2; exit 2; }
done

# ── 1. 계약 lint (양성 대조 + 통합 fixture 선행 → exit 2 = 검사기 고장)
LINT_OUT="$(python3 "$ROOT/scripts/lint_contracts.py" 2>&1)"; LINT_CODE=$?
SKIP_N="$(printf '%s\n' "$LINT_OUT" | grep -c '^   ⏸' || true)"
case "$LINT_CODE" in
  0) record "계약 lint"      0 "위반 0건 · SKIP ${SKIP_N}항목" ;;
  1) record "계약 lint"      1 "위반 있음 — 아래 상세" ;;
  *) record "계약 lint" "$LINT_CODE" "⛔ configuration/parse error — 검사기 자체 고장 (PASS도 SKIP도 아님)" ;;
esac

# ── 2. workflow model·effort 명시
MODEL_OUT="$(bash "$ROOT/scripts/lint-model-explicit.sh" 2>&1)"; MODEL_CODE=$?
record "model·effort 명시" "$MODEL_CODE" "$(printf '%s\n' "$MODEL_OUT" | tail -1)"

# ── 3. 외부 출처 최신성 (⛔ 기본은 경고 — findings 가 있어도 exit 0 이므로 건수를 따로 본다)
FRESH_OUT="$(cd "$ROOT" && python3 scripts/lint_doc_freshness.py 2>&1)"; FRESH_CODE=$?
FRESH_N="$(printf '%s\n' "$FRESH_OUT" | grep -oE '총 [0-9]+건' | grep -oE '[0-9]+' || echo 0)"
if [ "$STRICT_FRESHNESS" -eq 1 ] && [ "${FRESH_N:-0}" -gt 0 ]; then
  record "출처 최신성" 1 "findings ${FRESH_N}건 (--strict-freshness)"
else
  record "출처 최신성" "$FRESH_CODE" "findings ${FRESH_N}건 (경고 — exit 에 미반영)"
fi

# ── 4. workflow 문법
# ⛔ `node` 부재는 **문법 실패가 아니라 미실행**이다 (ISSUE-001과 동일 클래스 — Lead 자체 발견).
#    도구 부재를 실패로 기록하면 "문법이 깨졌다"고 오귀속하고, 통과로 기록하면 SKIP을 PASS로 만든다.
if command -v node >/dev/null 2>&1; then
  JS_FAIL=0 JS_BAD=""
  for f in "$ROOT"/workflows/*.js; do
    node --check "$f" >/dev/null 2>&1 || { JS_FAIL=1; JS_BAD="$JS_BAD $(basename "$f")"; }
  done
  record "workflow 문법" "$JS_FAIL" "$([ "$JS_FAIL" -eq 0 ] && echo "$(ls "$ROOT"/workflows/*.js | wc -l | tr -d ' ')개 통과" || echo "실패:$JS_BAD")"
else
  UNRUN=$((UNRUN + 1))
  record "workflow 문법" UNRUN "미실행 — node 부재 (⛔ PASS 아님)"
fi

# ── 5. 플러그인 매니페스트
# ⛔ ISSUE-001 (CRITICAL) 정정: 이전 판은 `claude` 부재를 **exit 0으로 기록**해
#    표에 ✅가 찍히고 총평이 "전 검사 통과"로 나왔다 — 플러그인 로딩이 **검증되지 않았는데도**.
#    주석으로 "PASS 아님"이라 적어도 **기계 판정이 PASS라면 그게 판정**이다.
#    이 스크립트가 다른 곳에서 강제하는 "SKIP ≠ PASS"를 스스로 위반하고 있었다.
if command -v claude >/dev/null 2>&1; then
  (cd "$ROOT" && claude plugin validate . >/dev/null 2>&1); VAL_CODE=$?
  record "plugin validate" "$VAL_CODE" "$([ "$VAL_CODE" -eq 0 ] && echo "OK" || echo "실패")"
else
  UNRUN=$((UNRUN + 1))
  record "plugin validate" UNRUN "미실행 — claude CLI 부재 (⛔ PASS 아님)"
fi

# ── 보고
echo
printf "%-22s %-6s %s\n" "검사" "exit" "비고"
printf "%-22s %-6s %s\n" "──────────────────────" "─────" "────────────────────────────"
# ⛔ 4R ISSUE-001: UNRUN 행을 exit 0 으로 기록해 **✅ 가 찍혔다**. 미실행은 `-` 로 표기하고
#    ✅(통과)·⛔(실패)와 **3분** 한다. 총평은 실패·미실행 **양쪽**을 반영한다.
FAILED=0
for i in "${!NAMES[@]}"; do
  code="${CODES[$i]}"
  if [ "$code" = "UNRUN" ]; then mark="⏸"
  elif [ "$code" -ne 0 ]; then mark="⛔"; FAILED=1
  else mark="✅"; fi
  printf "%s %-20s %-6s %s\n" "$mark" "${NAMES[$i]}" "$code" "${NOTES[$i]}"
done

echo
echo "⛔ SKIP(THRESHOLD·SEMANTIC) ${SKIP_N}항목은 **PASS가 아니다** — Lead가 별도 판정하고 보고에 남긴다."
# ⛔ 4R ISSUE-001: FAILED 분기가 먼저 exit 1 을 반환해 UNRUN 총평이 보고되지 않았다.
#    미실행이 있으면 **먼저** 알린다 — "일부 검사를 못 돌렸다"가 더 근본적인 상태다.
if [ "$UNRUN" -ne 0 ]; then
  echo
  echo "⛔ 실행되지 못한 검사 ${UNRUN}건 — **전 검사 통과라고 말할 수 없다**"
  [ "$FAILED" -ne 0 ] && { echo "── 계약 lint 전체 출력 ──"; printf '%s\n' "$LINT_OUT"; \
                           echo; echo "⛔ 추가로 실패한 검사도 있다"; }
  echo "(exit 2: 사전조건 미충족)"
  exit 2
fi
if [ "$FAILED" -ne 0 ]; then
  echo
  echo "── 계약 lint 전체 출력 ──"
  # ⛔ ISSUE-010: 이전 판은 `── 위반` 마커부터만 출력해 **configuration error·traceback 을 숨겼다**
  #    (마커가 없는 실패는 상세 구획이 빈칸으로 나왔다). 전체를 낸다.
  printf '%s\n' "$LINT_OUT"
  echo
  echo "⛔ 실패한 검사가 있다 (exit 1)"
  exit 1
fi
echo "✅ 전 검사 통과 (exit 0)"
exit 0
