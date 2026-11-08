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
# usage: health-check.sh [--strict-freshness] [--realmode-only] [--changed <경로>]... [--changed-from <파일>] [--ship] [--select-only]
#   --strict-freshness : 최신성 findings 가 있으면 실패로 취급 (기본: 경고)
#   --realmode-only    : 0.5 실모드 블록만 돌리고 멈춘다 — 배선 fixture 전용, 초록으로 끝나지 않는다(실패 1 · 그 외 2)
#   --changed <경로>   : 바뀐 경로(반복 가능) — scripts/health_select.py 가 검사를 고른다. 전부 문서면 부분 실행, 아니면 전체
#   --changed-from <파일> : 바뀐 경로 목록 파일(한 줄에 하나 — `git diff --name-only` 출력 그대로)
#   --ship             : 출하 — 경로와 무관하게 전체 실행(출하 게이트는 언제나 전체다)
#   --select-only      : 선택 결과(HEALTH-SELECT 줄)만 출력하고 exit 0 — 검사를 돌리지 않는다
#   ⛔ 네 인자가 없으면 이전과 같은 전체 실행이다. 부분 실행은 출하 게이트가 아니다 — 표 아래 `⛔ 부분 실행(PARTIAL)` 줄이 표시다
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
REALMODE_ONLY=0
SELECT=0 SELECT_ONLY=0 SEL_ARGS=() CHANGED=()   # 경로별 선택(H2-9) — 네 인자 중 하나라도 있어야 SELECT=1 이 된다
USAGE="health-check.sh [--strict-freshness] [--realmode-only] [--changed <경로>]... [--changed-from <파일>] [--ship] [--select-only]"
while [ $# -gt 0 ]; do
  case "$1" in
    --strict-freshness) STRICT_FRESHNESS=1; shift ;;
    --realmode-only) REALMODE_ONLY=1; shift ;;
    --changed) [ $# -ge 2 ] || { echo "⛔ --changed 에 경로가 없다 (사용법: $USAGE)" >&2; exit 2; }
               SELECT=1; CHANGED+=("$2"); shift 2 ;;
    --changed-from) [ $# -ge 2 ] || { echo "⛔ --changed-from 에 파일이 없다 (사용법: $USAGE)" >&2; exit 2; }
                    SELECT=1; SEL_ARGS+=(--from-file "$2"); shift 2 ;;
    --ship) SELECT=1; SEL_ARGS+=(--ship); shift ;;
    --select-only) SELECT=1; SELECT_ONLY=1; shift ;;
    *) echo "⛔ 알 수 없는 인자: $1 (사용법: $USAGE)" >&2; exit 2 ;;
  esac
done
# ⛔ 실모드 단독 실행은 배선 fixture 전용이다 — 경로 선택과 섞으면 어느 쪽이 도는지 호출자가 알 수 없다
if [ "$REALMODE_ONLY" -eq 1 ] && [ "$SELECT" -eq 1 ]; then
  echo "⛔ --realmode-only 는 --changed · --changed-from · --ship · --select-only 와 함께 쓰지 않는다 (사용법: $USAGE)" >&2; exit 2
fi

NAMES=() CODES=() NOTES=()
LINT_OUT="" SKIP_N=0   # 보고 꼬리가 읽는다 — 부분 실행이 계약 lint 를 건너뛰어도 set -u 에 걸리지 않게
UNRUN=0     # 실행되지 못한 검사 수 — ⛔ 0이 아니면 "전 검사 통과"라 말하지 않는다
record() { NAMES+=("$1"); CODES+=("$2"); NOTES+=("$3"); }
# ⛔ 3분 판정 (F-335 ⑬): exit 2 이면서 줄 맨 앞 `UNRUN` 표지가 있을 때만 미실행이다. 표지 없는 exit 2 와
#    traceback 은 실패다 — 검사기가 죽은 것을 미실행으로 세탁하지 않는다. 이전 판은 이분(0 · 그 외 1)이라
#    검사기가 정의한 측정 불가(exit 2 · `UNRUN:`)까지 실패로 적었다.
# return: 0 통과 · 1 실패 · 2 미실행
classify() {
  [ "$1" -eq 0 ] && return 0
  [ "$1" -eq 2 ] || return 1
  printf '%s\n' "$2" | grep -qF 'Traceback (most recent call last)' && return 1
  printf '%s\n' "$2" | grep -qE '^UNRUN[: ]' && return 2
  return 1
}
# record3 <이름> <exit> <출력> <통과 비고> <실패 비고> — classify 결과대로 기록한다(미실행은 UNRUN 을 센다)
record3() {
  classify "$2" "$3"
  case $? in
    0) record "$1" 0 "$4" ;;
    2) UNRUN=$((UNRUN + 1))
       record "$1" UNRUN "미실행 — $(printf '%s\n' "$3" | grep -E '^UNRUN[: ]' | head -1) (⛔ PASS 아님)" ;;
    *) local why=""
       if [ "$2" -eq 2 ]; then
         printf '%s\n' "$3" | grep -qF 'Traceback (most recent call last)' && why=' · exit 2 + traceback — 실패로 센다' || why=' · UNRUN 표지 없는 exit 2 — 실패로 센다'
       fi
       record "$1" 1 "$5$why" ;;
  esac
}

# ── 공용 검사 블록 (H2-9) — 전체 실행은 각 절 자리에서, 부분 실행(--changed)은 0.1 선택 블록에서 **같은 함수**를 부른다.
#    ⛔ 본문을 두 벌로 두지 않는다 — 한 벌만 고치면 부분 실행의 표가 전체 실행과 다르게 읽힌다.
#    절의 신설 근거 주석은 호출 자리에 남아 있다.
chk_contract_lint() {
  LINT_OUT="$(python3 "$ROOT/scripts/lint_contracts.py" 2>&1)"; LINT_CODE=$?
  SKIP_N="$(printf '%s\n' "$LINT_OUT" | grep -c '^   ⏸' || true)"
  case "$LINT_CODE" in
    0) record "계약 lint"      0 "위반 0건 · SKIP ${SKIP_N}항목" ;;
    1) record "계약 lint"      1 "위반 있음 — 아래 상세" ;;
    *) record "계약 lint" "$LINT_CODE" "⛔ configuration/parse error — 검사기 자체 고장 (PASS도 SKIP도 아님)" ;;
  esac
}
chk_doc_freshness() {
  FRESH_OUT="$(cd "$ROOT" && python3 scripts/lint_doc_freshness.py 2>&1)"; FRESH_CODE=$?
  FRESH_N="$(printf '%s\n' "$FRESH_OUT" | grep -oE '총 [0-9]+건' | grep -oE '[0-9]+' || echo 0)"
  if [ "$STRICT_FRESHNESS" -eq 1 ] && [ "${FRESH_N:-0}" -gt 0 ]; then
    record "출처 최신성" 1 "findings ${FRESH_N}건 (--strict-freshness)"
  else
    record "출처 최신성" "$FRESH_CODE" "findings ${FRESH_N}건 (경고 — exit 에 미반영)"
  fi
}
chk_runners() {   # 인자: 러너 경로들 — 0개면 미실행(전체 실행의 글롭 오타 감지). 부분 실행은 1개 이상일 때만 부른다
  if command -v node >/dev/null 2>&1; then
    T_TOTAL=0 T_FAIL=0 T_BAD="" T_UN=0 T_UNLIST=""
    # 러너 하나를 3분 판정한다 — 출력을 버리면 UNRUN 표지를 볼 수 없다(F-335 ⑬)
    t_one() {
      T_TOTAL=$((T_TOTAL + 1))
      classify "$1" "$2"
      case $? in
        0) ;;
        2) T_UN=$((T_UN + 1)); T_UNLIST="$T_UNLIST $3" ;;
        *) T_FAIL=$((T_FAIL + 1)); T_BAD="$T_BAD $3" ;;
      esac
    }
    # 인자 = 러너 경로(전체 실행은 4.6 의 세 글롭 · 부분 실행은 선택된 러너). .js 먼저 · run.sh 다음 — 전체 실행의 순서와 같다
    for f in "$@"; do
      case "$f" in *.js) ;; *) continue ;; esac
      [ -f "$f" ] || continue
      t_out="$(cd "$ROOT" && node "$f" 2>&1)"; t_one $? "$t_out" "$(basename "$f")"
    done
    # run.sh — scripts/run_runners.py 가 FZ_HEALTH_JOBS(기본 4 · 1 = 옛 직렬) 묶음으로 병렬 실행하고 결과를 입력 순서 파일로 남긴다.
    #   판정 · 보고는 여기서 순서대로 한다(표 형식 불변). ⛔ 결과 파일이 없으면 UNRUN 으로 센다 — 통과로 읽지 않는다.
    #   러너는 자기 임시 공간에서만 쓴다(2026-11-05 실측: 공유 HOME · 고정 임시 경로 · 대상 저장소 git 쓰기 0) — 병렬 전제가 깨지면 FZ_HEALTH_JOBS=1
    local RS=() RR rs_i=0 t_rc
    for r in "$@"; do case "$r" in */run.sh) [ -f "$r" ] && RS+=("$r") ;; esac; done
    if [ ${#RS[@]} -gt 0 ]; then
      RR="$(mktemp -d)"
      python3 "$ROOT/scripts/run_runners.py" --jobs "${FZ_HEALTH_JOBS:-4}" --cwd "$ROOT" --out-dir "$RR" -- "${RS[@]}" >/dev/null 2>&1
      for r in "${RS[@]}"; do
        t_out="$(cat "$RR/$rs_i.out" 2>/dev/null || echo 'UNRUN: 러너 결과 없음 — 병렬 실행기가 기록하지 못했다')"
        t_rc="$(cat "$RR/$rs_i.rc" 2>/dev/null || echo 2)"
        t_one "$t_rc" "$t_out" "$(basename "$(dirname "$r")")"; rs_i=$((rs_i + 1))
      done
      rm -rf "$RR"
    fi
    # ⛔ 실패와 미실행이 함께 있으면 둘 다 보고한다 — 한 행은 ⛔ 와 ⏸ 를 함께 표시할 수 없어 미실행 행을 따로 둔다
    if [ "$T_TOTAL" -eq 0 ]; then
      UNRUN=$((UNRUN + 1))
      record "회귀 오라클" UNRUN "미실행 — 러너 0개 발견 (경로 오타 의심, ⛔ PASS 아님)"
    else
      [ "$T_FAIL" -gt 0 ] && record "회귀 오라클" 1 "⛔ ${T_FAIL}/${T_TOTAL} 실패 —$T_BAD"
      if [ "$T_UN" -gt 0 ]; then
        UNRUN=$((UNRUN + 1))
        record "회귀 오라클 미실행" UNRUN "UNRUN 표지 exit 2 ${T_UN}/${T_TOTAL} —$T_UNLIST · 통과 $((T_TOTAL - T_FAIL - T_UN)) (⛔ PASS 아님)"
      fi
      [ "$T_FAIL" -eq 0 ] && [ "$T_UN" -eq 0 ] && record "회귀 오라클" 0 "${T_TOTAL}개 전건 통과"
    fi
  else
    UNRUN=$((UNRUN + 1))
    record "회귀 오라클" UNRUN "미실행 — node 부재 (⛔ PASS 아님)"
  fi
}
chk_single_source() {
  SS="$(cd "$ROOT" && python3 scripts/check_single_source.py 2>&1)"; SS_CODE=$?
  record3 "단일 출처 계약" "$SS_CODE" "$SS" \
    "$(printf '%s\n' "$SS" | grep -E 'canonical=' | tail -1)" \
    "⛔ $(printf '%s\n' "$SS" | grep -E 'VIOLATION|UNRUN|⛔' | tail -1)"
}
chk_recurrence() {
  LR_OUT="$( (python3 "$ROOT/scripts/lint_recurrence.py" --self-test && python3 "$ROOT/scripts/lint_recurrence.py" --root "$ROOT") 2>&1)"; LR_CODE=$?
  record3 "재발 방지 lint" "$LR_CODE" "$LR_OUT" \
    "$(printf '%s\n' "$LR_OUT" | grep -E '^lint_recurrence: ' | tail -1) · $(printf '%s\n' "$LR_OUT" | grep -E 'self-test: PASS')" \
    "⛔ $(printf '%s\n' "$LR_OUT" | grep -E ': FAIL|: UNRUN|self-test: FAIL' | head -3 | tr '\n' ' ')"
}
# 퇴역 slash command 참조(H1-3) — 설치 · 활성화되지 않은 명령을 산문 · 표 · 코드 블록이 부르면 실패. 전체 실행에만 있다
chk_retired_commands() {
  RC_OUT="$(python3 "$ROOT/scripts/check_retired_commands.py" --root "$ROOT" 2>&1)"; RC_CODE=$?
  record3 "퇴역 명령 참조" "$RC_CODE" "$RC_OUT" "$(printf '%s\n' "$RC_OUT" | tail -1)" \
    "⛔ $(printf '%s\n' "$RC_OUT" | grep -E ' → ' | head -2 | tr '\n' ' ')"
}
report_and_exit() {   # $1 = 부분 실행 표지 줄 — 비면 전체 실행이다(이전 판과 같은 출력)
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
  # 부분 실행 표지는 총평 **앞**에 둔다 — 초록 총평만 읽고 출하 게이트로 오인하지 않게
  if [ -n "${1:-}" ]; then echo; echo "$1"; fi
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
}

echo "══════════════════════════════════════════════════════════════"
echo "fz 건강 체크 — root $ROOT"
echo "══════════════════════════════════════════════════════════════"

# ── 0. 사전조건 — ⛔ 4R ISSUE-001: python3·lint 스크립트 부재가 "일반 실패"로 분류됐다.
#    도구·자산 부재는 **미실행**이며 실패와 구별해야 한다.
for dep in python3 git; do
  command -v "$dep" >/dev/null 2>&1 || { echo "⛔ 사전조건 부재: $dep" >&2; exit 2; }
done
for f in lint_contracts.py lint-model-explicit.sh lint_doc_freshness.py gate_check.py gate_stop_hook.py lint_diff_parsers.py check-gpt-flags.sh check_g8_style.py eject_findings.py check_findings_hygiene.py check_release_closes.py freeze_baseline.py migrate_findings_frontmatter.py check_symptom_anchor.py check_external_commands.py check_global_budget.py check_asset_census.py check_release_sync.sh fz_wf_metrics.py report_stale_findings.py autonomy_decide.py check_failure_table.py check_single_source.py candidate_expiry.py check_wf_advisor_ban.py check_gpt_surface.py check_quality_fixtures.py ab_ledger.py check_ab_protocol.py check_wf_syntax.js check_wf_text.js plugin_validate.sh check_release_notes.py extract_project_rules.py check_project_rules.py review_merge.py plan_apply_delta.py plan_divergence.py plan_resolve_impact_requests.py check_gpt_skill_portability.py review_snapshot.sh md_section.py ab_ledger_base.py ab_ledger_transcript.py ab_ledger_collect.py ab_ledger_judge.py ab_ledger_gpt.py ab_ledger_selftest.py gpt_kinds.py gpt-call.sh gpt_rounds.py mode_gate.py check_loaded_version.py harness_census.py measure_runtime_load.py check_report_regen.py lint_recurrence.py counter_adapter.py health_select.py check_retired_commands.py run_runners.py check_evidence_slots.py gpt_ab_decide.py gpt_merge.py plan_integrity_check.py check_health_wiring.py fz_snapshot.py fz_stop_telemetry.py fz_telemetry_report.py run_metrics.py check_synthesized.py check_comment_worthy.py intent_route_probe.py; do
  [ -f "$ROOT/scripts/$f" ] || { echo "⛔ 검사 스크립트 부재: scripts/$f" >&2; exit 2; }
done

# ── 0.1 경로별 검사 선택 (H2-9 · GPT H-015) — `--changed*` · `--ship` · `--select-only` 가 있을 때만 돈다(없으면 이 블록을 통째로 건너뛴다)
#    선택은 scripts/health_select.py 가 러너 원문에서 매번 계산한다 — 손으로 고치는 '경로 → 검사' 표가 없다(표는 러너가 새 경로를
#    읽기 시작해도 그대로라 조용히 낡는다). mode=full 이면 선택 머리줄만 찍고 아래 전체 실행으로 내려간다. mode=subset 이면
#    고른 검사만 위 공용 함수로 돌리고 같은 표로 보고한 뒤 같은 규칙(0 · 1 · 2)으로 끝난다.
#    ⛔ 부분 실행은 출하 게이트가 아니다 — 총평 앞 PARTIAL 줄이 표시다. 출하는 --ship(= 전체)이다.
#    ⛔ 선택기 출력이 계약(첫 줄 mode · 아는 검사 이름 · 실재 러너 · full 이면 check 줄 0 · subset 이면 1+)을 어기면 exit 2 다 —
#       깨진 선택을 조용히 전체나 부분으로 바꿔 돌리지 않는다.
if [ "$SELECT" -eq 1 ]; then
  SEL_OUT="$(python3 "$ROOT/scripts/health_select.py" ${SEL_ARGS[@]+"${SEL_ARGS[@]}"} -- ${CHANGED[@]+"${CHANGED[@]}"})"; SEL_CODE=$?
  [ "$SEL_CODE" -eq 0 ] || { echo "⛔ 검사 선택기 실패 exit $SEL_CODE — 판정 불가" >&2; exit 2; }
  printf '%s\n' "$SEL_OUT"
  SEL_MODE="$(printf '%s\n' "$SEL_OUT" | sed -n '1s/^HEALTH-SELECT mode=\([a-z]*\) reason=.*/\1/p')"
  SEL_LIST=()
  while IFS= read -r c; do
    [ -n "$c" ] || continue
    case "$c" in
      lint_contracts.py|lint_recurrence.py|lint_doc_freshness.py|check_single_source.py) ;;
      tests/workflows/*.js|tests/lib/*.test.js|tests/fixtures/*/*/run.sh)
        [ -f "$ROOT/$c" ] || { echo "⛔ 선택기 출력 계약 위반 — 없는 러너: $c" >&2; exit 2; } ;;
      *) echo "⛔ 선택기 출력 계약 위반 — 모르는 검사: $c" >&2; exit 2 ;;
    esac
    SEL_LIST+=("$c")
  done < <(printf '%s\n' "$SEL_OUT" | sed -n 's/^HEALTH-SELECT check=\([^ ]*\).*/\1/p')
  case "$SEL_MODE" in
    full)   [ "${#SEL_LIST[@]}" -eq 0 ] || { echo "⛔ 선택기 출력 계약 위반 — mode=full 인데 check 줄이 있다" >&2; exit 2; } ;;
    subset) [ "${#SEL_LIST[@]}" -gt 0 ] || { echo "⛔ 선택기 출력 계약 위반 — mode=subset 인데 check 줄이 없다" >&2; exit 2; } ;;
    *) echo "⛔ 선택기 출력 계약 위반 — 첫 줄에 HEALTH-SELECT mode=full|subset 이 없다" >&2; exit 2 ;;
  esac
  [ "$SELECT_ONLY" -eq 1 ] && exit 0
  if [ "$SEL_MODE" = subset ]; then
    want() { local c; for c in "${SEL_LIST[@]}"; do [ "$c" = "$1" ] && return 0; done; return 1; }
    SEL_RUNNERS=()
    for c in "${SEL_LIST[@]}"; do case "$c" in tests/*) SEL_RUNNERS+=("$ROOT/$c") ;; esac; done
    # 표 순서는 전체 실행과 같다 — 1 계약 lint · 3 출처 최신성 · 4.6 회귀 오라클 · 단일 출처 · 4.8j 재발 방지.
    # ⛔ 고른 러너가 0개면 회귀 오라클 행을 두지 않는다 — '러너 0개 = 미실행' 은 전체 실행의 글롭 오타 감지다
    want lint_contracts.py && chk_contract_lint
    want lint_doc_freshness.py && chk_doc_freshness
    [ "${#SEL_RUNNERS[@]}" -gt 0 ] && chk_runners "${SEL_RUNNERS[@]}"
    want check_single_source.py && chk_single_source
    want lint_recurrence.py && chk_recurrence
    report_and_exit "⛔ 부분 실행(PARTIAL) — 출하 게이트 아님 · 선택 ${#SEL_LIST[@]}개"
  fi
fi

# ── 0.5 실모드 불변식 (A5-01·A5-03) ───────────────────────────────
# ⛔ self-test 는 **검사기**가 멀쩡한지만 본다 — 트리를 보지 않으면 값 강등이 그대로 통과한다.
#    실측: effort 를 xhigh→high 로 낮추거나 재시도 래퍼 안에 opus 를 늘려도 이전 판 health-check 는 exit 0 이었다.
#    그래서 여섯 검사를 이 트리에 **실모드**로 돌린다(합산 1~2s).
# ⛔ 워크플로 문법은 check_wf_syntax.js(AsyncFunction 파싱)로 본다 — 워크플로 파일은 async 함수 본문이라
#    일반 JS 파서 검사로는 판별력이 0 이다(Node v26 에서 심은 문법 오류도 rc=0).
# ⛔ `node` 부재는 **문법 실패가 아니라 미실행**이다 (ISSUE-001과 동일 클래스) — 실패로 적으면 "문법이 깨졌다"고
#    오귀속하고, 통과로 적으면 SKIP을 PASS로 만든다.
# ⛔ `--realmode-only` 는 이 블록만 돌리고 멈춘다 — 배선 fixture(tests/fixtures/health/wiring-failure) 전용이며
#    나머지를 안 돌렸으므로 **초록으로 끝나지 않는다**(실패 1 · 그 외 2).
if command -v node >/dev/null 2>&1; then
  WS_SELF="$(node "$ROOT/scripts/check_wf_syntax.js" --self-test 2>&1)"; WS_SELF_CODE=$?
  WS_OUT="$(node "$ROOT/scripts/check_wf_syntax.js" --root "$ROOT" 2>&1)"; WS_CODE=$?
  if [ "$WS_SELF_CODE" -ne 0 ]; then
    record "workflow 문법" 1 "⛔ 검사기 self-test 실패 — $(printf '%s\n' "$WS_SELF" | grep -E 'FAIL|self-test' | head -2 | tr '\n' ' ')"
  elif [ "$WS_CODE" -eq 0 ]; then
    record "workflow 문법" 0 "$(printf '%s\n' "$WS_OUT" | tail -1) · $(printf '%s\n' "$WS_SELF" | tail -1)"
  else
    record "workflow 문법" "$WS_CODE" "⛔ $(printf '%s\n' "$WS_OUT" | grep -E 'FAIL|UNRUN' | head -2 | tr '\n' ' ')"
  fi
  WT_SELF="$(node "$ROOT/scripts/check_wf_text.js" --self-test 2>&1)"; WT_SELF_CODE=$?
  WT_PAR="$(node "$ROOT/scripts/check_wf_text.js" --section-has 'Phase 2: Plan Validation' '불변 입력' '별도 출력' '양쪽 완료' 'schema' "$ROOT/skills/fz-plan/SKILL.md" 2>&1)"; WT_PAR_CODE=$?
  WT_ORD="$(node "$ROOT/scripts/check_wf_text.js" --order-in-section '실행 절차 (Lead)' 'cp {플러그인 루트}/workflows/plan-lean2.js' 'Workflow({ scriptPath' "$ROOT/skills/fz-plan/SKILL.md" 2>&1)"; WT_ORD_CODE=$?
  # ⛔ 준비 순서(cp → cmp -s → 복사본 호출)는 fz-plan 하나가 아니라 소비자 10곳(skills 7 · modules 2 · guides 1 — swarm 정본 사이트)을 다 본다 — modules 사이트가 자동 배선 검사 밖이었다
  WT_SITE="$(bash "$ROOT/tests/fixtures/workflow-prep/copy-cmp/run.sh" --tree "$ROOT" --cells sites 2>&1)"; WT_SITE_CODE=$?; WT_SITE_N=$(printf '%s\n' "$WT_SITE" | grep -c '^SITE-OK ')
  if [ "$WT_SELF_CODE" -eq 0 ] && [ "$WT_PAR_CODE" -eq 0 ] && [ "$WT_ORD_CODE" -eq 0 ] && [ "$WT_SITE_CODE" -eq 0 ] && [ "$WT_SITE_N" -eq 10 ]; then
    record "문구 배선" 0 "fz-plan ${WT_PAR%% *} · ${WT_ORD%% *} · 준비 사이트 ${WT_SITE_N}/10 · $(printf '%s\n' "$WT_SELF" | tail -1)"
  else
    record "문구 배선" 1 "⛔ $(printf '%s\n' "$WT_SELF" "$WT_PAR" "$WT_ORD" "$WT_SITE" | grep -E 'FAIL' | head -2 | tr '\n' ' ') (준비 사이트 ${WT_SITE_N}/10)"
  fi
else
  UNRUN=$((UNRUN + 2))
  record "workflow 문법" UNRUN "미실행 — node 부재 (⛔ PASS 아님)"
  record "문구 배선" UNRUN "미실행 — node 부재 (⛔ PASS 아님)"
fi
MB_OUT="$(bash "$ROOT/scripts/lint-model-explicit.sh" --baseline 2>&1)"; MB_CODE=$?
if [ "$MB_CODE" -eq 0 ]; then
  record "모델·effort 기준선" 0 "$(printf '%s\n' "$MB_OUT" | tail -1)"
else
  record "모델·effort 기준선" "$MB_CODE" "⛔ $(printf '%s\n' "$MB_OUT" | grep -E '❌' | head -2 | tr '\n' ' ')"
fi
GB_OUT="$(python3 "$ROOT/scripts/check_global_budget.py" --root "$ROOT" 2>&1)"; GB_CODE=$?
if [ "$GB_CODE" -eq 0 ]; then
  record "동시 스폰 예산" 0 "$(printf '%s\n' "$GB_OUT" | grep -E '^분모' | tail -1)"
else
  record "동시 스폰 예산" "$GB_CODE" "⛔ $(printf '%s\n' "$GB_OUT" | grep -E '^      |UNRUN' | head -2 | tr '\n' ' ')"
fi
AC_OUT="$(python3 "$ROOT/scripts/check_asset_census.py" --root "$ROOT" 2>&1)"; AC_CODE=$?
if [ "$AC_CODE" -eq 0 ]; then
  record "자산 census" 0 "$(printf '%s\n' "$AC_OUT" | grep -E '^분모' | tail -1)"
else
  record "자산 census" "$AC_CODE" "⛔ $(printf '%s\n' "$AC_OUT" | grep -E '^      |UNRUN' | head -2 | tr '\n' ' ')"
fi
EC_OUT="$(python3 "$ROOT/scripts/check_external_commands.py" --root "$ROOT" 2>&1)"; EC_CODE=$?
if [ "$EC_CODE" -eq 0 ]; then
  record "외부 명령 실존" 0 "$(printf '%s\n' "$EC_OUT" | grep -E '^분모' | tail -1)"
else
  record "외부 명령 실존" "$EC_CODE" "⛔ $(printf '%s\n' "$EC_OUT" | grep -E '^      |UNRUN|⛔' | head -2 | tr '\n' ' ')"
fi
if [ "$REALMODE_ONLY" -eq 1 ]; then
  RM_FAILED=0
  for i in "${!NAMES[@]}"; do
    code="${CODES[$i]}"
    if [ "$code" = "UNRUN" ]; then mark="⏸"; elif [ "$code" -ne 0 ]; then mark="⛔"; RM_FAILED=1; else mark="✅"; fi
    printf '%s %s | %s | %s\n' "$mark" "${NAMES[$i]}" "$code" "${NOTES[$i]}"
  done
  echo "⛔ 부분 실행(--realmode-only) — 나머지 검사를 돌리지 않았다 (PASS 아님)"
  [ "$RM_FAILED" -eq 1 ] && exit 1
  exit 2
fi

# ── 1. 계약 lint (양성 대조 + 통합 fixture 선행 → exit 2 = 검사기 고장)
chk_contract_lint

# ── 1.5 diff 파서 hunk 상태 선언
#    ⛔ 신설 근거: 같은 결함이 한 세션에 4번 났다 — hunk 안팎에서 뜻이 다른 `+`/`-` 접두사를
#       상태 없이 판정. 정답이 같은 디렉터리에 이미 있었는데 3곳이 각자 다시 틀렸다.
#       변경 규모가 auto-tier 입력이라 유실은 **낮은 Tier 로 기우는** 형태로 조용히 나타난다.
#    ⛔ self-test 선행 — 검사기 고장(exit≠0)을 "위반 0건"으로 읽지 않는다.
DP_SELF="$(python3 "$ROOT/scripts/lint_diff_parsers.py" --self-test 2>&1)"; DP_SELF_CODE=$?
if [ "$DP_SELF_CODE" -ne 0 ]; then
  record "diff 파서 선언" 2 "⛔ 검사기 self-test 실패 — 판정 불가 ($(printf '%s\n' "$DP_SELF" | tail -1))"
  UNRUN=$((UNRUN+1))
else
  DP_OUT="$(python3 "$ROOT/scripts/lint_diff_parsers.py" 2>&1)"; DP_CODE=$?
  DP_N="$(printf '%s\n' "$DP_OUT" | grep -c '  ⛔ ' || true)"
  case "$DP_CODE" in
    0) record "diff 파서 선언" 0 "선언 누락 0건 · self-test $(printf '%s\n' "$DP_SELF" | tail -1)" ;;
    1) record "diff 파서 선언" 1 "⛔ 선언 누락 ${DP_N}건 — 첫 40행에 \`# diff-parse:\` 1줄" ;;
    *) record "diff 파서 선언" "$DP_CODE" "⛔ UNKNOWN(읽기 실패) 포함 — 통과로 읽지 않는다" ;;
  esac
fi

# ── 2. workflow model·effort 명시
MODEL_OUT="$(bash "$ROOT/scripts/lint-model-explicit.sh" 2>&1)"; MODEL_CODE=$?
record "model·effort 명시" "$MODEL_CODE" "$(printf '%s\n' "$MODEL_OUT" | tail -1)"

# ── 2.5 게이트 판정기 self-test (⛔ 0/1/2 구분 — 2는 매니페스트·fixture 부재)
#    이 검사가 없으면 gate_check.py 가 회귀해도 통합 건강 체크가 통과한다.
#    ⛔ 루트 **밖**에서 돌린다 — self-test 결과는 호출 위치와 무관해야 한다. `cd "$ROOT"` 로 돌리던
#       시절에는 루트 기준 상대 경로가 cwd 로 풀리는 결함(F-338 — 루트 밖이면 verdict-* 11개 FAIL)이 보이지 않았다.
GATE_OUT="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/scripts/gate_check.py" --self-test 2>&1)"; GATE_CODE=$?
GATE_LAST="$(printf '%s\n' "$GATE_OUT" | tail -1)"
case "$GATE_CODE" in
  0) record "게이트 self-test"      0 "$GATE_LAST" ;;

  1) record "게이트 self-test"      1 "$GATE_LAST — 아래 상세" ;;
  *) record "게이트 self-test" "$GATE_CODE" "⛔ 매니페스트·fixture 부재 (PASS도 SKIP도 아님)" ;;
esac

# ── 2.6 Stop hook 계약 (게이트 2차 계층) ─────────────────────────────
# ⛔ hook 은 등록해야 발동하지만 계약(stdin JSON → exit + stderr)은 **등록 없이**
#    검증된다. 등록은 사용자 소관이므로 여기까지가 닫을 수 있는 경계다.
HOOK_OUT="$(cd "$ROOT" && python3 scripts/gate_stop_hook.py --self-test 2>&1)"; HOOK_CODE=$?
HOOK_LAST="$(printf '%s\n' "$HOOK_OUT" | tail -1)"
case "$HOOK_CODE" in
  0) record "Stop hook 계약"      0 "$HOOK_LAST" ;;
  1) record "Stop hook 계약"      1 "$HOOK_LAST — 차단이 발화하지 않을 수 있다" ;;
  *) record "Stop hook 계약" "$HOOK_CODE" "⛔ self-test 실행 불가 (PASS도 SKIP도 아님)" ;;
esac

# ── 2.7 게이트 원장 상태 (hook 미설치 머신의 유일한 노출 경로) ──────────
# ⛔ 미충족은 **실패가 아니다** — 작업 중 원장이 미충족인 것은 정상 상태다. exit 에
#    반영하면 원장 있는 모든 세션에서 이 검사가 빨개져 사람이 health-check 를 안 돌리게
#    된다(`lint_doc_freshness` 선례: findings 가 있어도 exit 0, 건수만 보고).
#    ⛔ 원장 **계약 위반**(exit 3)만 실패다 — fz 가 만든 원장이 자기 계약을 어긴 것은
#    plugin 자산 결함이고 그것이 health-check 의 관심사다.
# ⛔ 탐색 기준은 호출 CWD 다(플러그인 루트가 아니다) — 작업 트리에 원장이 있다.
LEDGER_OUT="$(python3 "$ROOT/scripts/gate_check.py" --discover "$PWD" 2>&1)"; LEDGER_CODE=$?
LEDGER_LAST="$(printf '%s\n' "$LEDGER_OUT" | tail -1)"
case "$LEDGER_CODE" in
  0) record "게이트 원장 상태"      0 "$LEDGER_LAST" ;;
  3) record "게이트 원장 상태"      1 "$LEDGER_LAST — 원장이 계약을 위반한다" ;;
  *) record "게이트 원장 상태" "$LEDGER_CODE" "⛔ 탐색 실행 불가 (PASS도 SKIP도 아님)" ;;
esac

# ── 3. 외부 출처 최신성 (⛔ 기본은 경고 — findings 가 있어도 exit 0 이므로 건수를 따로 본다)
chk_doc_freshness

# ── 4.5 gpt 플래그 호환성
# ⛔ 신설 근거: `check-gpt-flags.sh` 는 review 경로가 거부하는 플래그를 잡는 회귀 게이트인데
#    어느 자동 실행 경로에도 없었다(health-check 참조 0건 · gpt-exec.sh 는 주석만).
#    막으려던 실패 = 공용 인자 배열이 GPT CLI review 모드에 거부돼 exit 2 를 내고
#    호출부가 그것을 "이슈 0건" 으로 읽는 것. CLI 가 플래그 집합을 바꾸면 침묵한다.
# ⛔ exit 2(GPT CLI 부재·help 파싱 실패)는 **PASS 가 아니라 미실행**이다 — §4 와 같은 클래스.
CF_OUT="$(bash "$ROOT/scripts/check-gpt-flags.sh" 2>&1)"; CF_CODE=$?
case "$CF_CODE" in
  0) record "gpt 플래그 호환성" 0 "review 미지원 플래그 0건" ;;
  1) record "gpt 플래그 호환성" 1 "⛔ review 경로에 미지원 플래그 — $(printf '%s\n' "$CF_OUT" | tail -1)" ;;
  *) UNRUN=$((UNRUN + 1))
     record "gpt 플래그 호환성" UNRUN "미실행 — GPT CLI 부재·help 파싱 실패 (⛔ PASS 아님)" ;;
esac

# ── 4.5b GPT 스킬 링크 stale (경고 전용 — F-353)
# ⛔ 신설 근거: 플러그인 업데이트는 setup 을 다시 돌리지 않는다 — 옛 setup 이 남긴 이 플러그인 Claude 스킬 링크·끊어진 소유 링크가
#    사용자 스킬 폴더에 그대로 남아도 알릴 경로가 없었다(실측 22개). 점검은 읽기 전용 `setup-gpt-skills.sh --check` 가 맡는다.
# ⛔ 실패가 아니다 — 대상은 이 트리가 아니라 사용자 홈 상태다(§4.8 과 같은 클래스). 그래서 record 는 늘 0 이고 비고만 다르다:
#    stale 이면 건수·이름과 정리 명령, 점검이 정해진 요약 줄 없이 끝나면 판정 불가(⛔ 깨끗하다는 뜻이 아니다).
#    스크립트 자체의 판정은 §4.6 회귀 오라클의 setup-links 셀이 임시 홈에서 본다.
# ⛔ 판정 불가도 record 0(경고) 이다 — 계획 문언 '경고 행(FAIL 아님)'. 대상이 사용자 홈이라 UNRUN 으로 올리면 이 트리와 무관하게
#    health-check 가 exit 2 가 된다. 스크립트가 깨진 경우는 setup-links 셀이 실패로 잡는다. 소유 판정 불가 링크(unknown)는 건수만 비고에.
SL_OUT="$(bash "$ROOT/scripts/setup-gpt-skills.sh" --check 2>&1)"; SL_CODE=$?
SL_N="$(printf '%s\n' "$SL_OUT" | grep -E '^Check: [0-9]+ stale' | tail -1 | grep -oE '[0-9]+' | head -1)"
SL_U="$(printf '%s\n' "$SL_OUT" | grep -c '^  unknown: ')"; SL_UN=""; [ "$SL_U" -gt 0 ] && SL_UN=" · ⚠️ 소유 판정 불가 ${SL_U}건(끊긴 링크 — setup 이 보존)"
if [ "$SL_CODE" -eq 0 ] && [ "${SL_N:-x}" = 0 ]; then
  record "GPT 스킬 링크" 0 "stale 0건${SL_UN}"
elif [ "$SL_CODE" -eq 1 ] && [ "${SL_N:-0}" -gt 0 ]; then
  SL_NAMES="$(printf '%s\n' "$SL_OUT" | sed -n 's/^  stale: \([^ ]*\) .*/\1/p' | head -3 | tr '\n' ' ')"
  [ "$SL_N" -gt 3 ] && SL_NAMES="${SL_NAMES}…"
  record "GPT 스킬 링크" 0 "⚠️ stale ${SL_N}건 (${SL_NAMES% })${SL_UN} — 정리: bash scripts/setup-gpt-skills.sh (경고 — exit 에 미반영)"
else
  record "GPT 스킬 링크" 0 "⚠️ 점검 판정 불가 exit $SL_CODE — $(printf '%s\n' "$SL_OUT" | tail -1) (⛔ 깨끗하다는 뜻 아님 · exit 에 미반영)"
fi

# ── 4.6 회귀 오라클 실행 (tests/) ─────────────────────────────────
# ⛔ 신설 근거: 오라클이 **아무 자동 경로에도 없었다**. `tests/workflows/*.js` 3종 중
#    참조 1곳(s2-cross-merge)뿐이고 d6·s2-stage2-trigger 는 0곳, `tests/fixtures/*/run.sh`
#    7종도 health-check 가 보지 않았다. 아무도 안 돌리는 오라클은 오라클이 아니다 —
#    회귀가 나도 통합 건강 체크가 초록으로 통과한다.
# ⛔ 러너를 **0개 발견**한 경우는 PASS 가 아니라 미실행이다: 경로 오타·디렉터리 이동이
#    "전건 통과" 로 인쇄되는 것이 정확히 막으려는 실패다(0건은 측정 실패를 먼저 의심).
# tests/lib/*.test.js — 라이브러리(가짜 런타임 로더)의 테스트. 라이브러리 파일 자체는 이 글롭 밖이다
# ⛔ 세 글롭은 scripts/health_select.py 의 RUNNER_GLOBS 와 같아야 한다 — 다르면 선택기가 고른 러너를 여기서 모른다
chk_runners "$ROOT"/tests/workflows/*.js "$ROOT"/tests/lib/*.test.js "$ROOT"/tests/fixtures/*/*/run.sh

# ── 4.7 G8 문체 게이트 fixture 계약 ────────────────────────────
# ⛔ 신설 근거: `negative-clean.md` 가 "오검출 0/8" 을 기대값으로 적어 두고 **한 번도
#    실행된 적이 없었다**. 기대값은 실행돼야 오라클이다.
# ⛔ 원시 위반 수가 아니라 **계약**을 본다: clean 은 0, defect 는 1건 이상.
#    defect 가 0 이면 검사기가 죽은 것이므로 그것도 실패다(positive control).
G8_SELF="$(cd "$ROOT" && python3 scripts/check_g8_style.py --self-test 2>&1)"; G8_SELF_CODE=$?
if [ "$G8_SELF_CODE" -ne 0 ]; then
  UNRUN=$((UNRUN + 1))
  record "G8 문체 fixture" UNRUN "⛔ 검사기 self-test 실패 — 판정 불가 (PASS 아님)"
else
  G8_OUT="$(cd "$ROOT" && python3 scripts/check_g8_style.py --fixture-check 2>&1)"; G8_CODE=$?
  case "$G8_CODE" in
    0) record "G8 문체 fixture" 0 "$(printf '%s\n' "$G8_OUT" | tail -1) · self-test $(printf '%s\n' "$G8_SELF" | tail -1)" ;;
    1) record "G8 문체 fixture" 1 "⛔ $(printf '%s\n' "$G8_OUT" | tail -1)" ;;
    *) UNRUN=$((UNRUN + 1))
       record "G8 문체 fixture" UNRUN "미실행 — fixture 부재 (⛔ PASS 아님)" ;;
  esac
fi

# ── 4.8 합성 품질 fixture 계약 ────────────────────────────────
# ⛔ A/B 의 정답 라벨이 diff 밖 줄·축 오타·평문 지침을 품으면 채점이 틀린다.
#    self-test(축 오타·hunk 밖·축 누락 검출)가 먼저 통과해야 실제 세트 판정을 믿는다.
QF_SELF="$(cd "$ROOT" && python3 scripts/check_quality_fixtures.py --self-test 2>&1)"; QF_SELF_CODE=$?
if [ "$QF_SELF_CODE" -ne 0 ]; then
  UNRUN=$((UNRUN + 1))
  record "품질 fixture 계약" UNRUN "⛔ 검사기 self-test 실패 — 판정 불가 ($(printf '%s\n' "$QF_SELF" | tail -1))"
else
  QF_OUT="$(cd "$ROOT" && python3 scripts/check_quality_fixtures.py --root "$ROOT" 2>&1)"; QF_CODE=$?
  case "$QF_CODE" in
    0) record "품질 fixture 계약" 0 "$(printf '%s\n' "$QF_OUT" | tail -1) · $(printf '%s\n' "$QF_SELF" | tail -1)" ;;
    1) record "품질 fixture 계약" 1 "⛔ $(printf '%s\n' "$QF_OUT" | grep -E 'VIOLATION' | head -1)" ;;
    *) UNRUN=$((UNRUN + 1))
       record "품질 fixture 계약" UNRUN "미실행 — $(printf '%s\n' "$QF_OUT" | tail -1) (⛔ PASS 아님)" ;;
  esac
fi

# ── 4.8a 프로젝트 규칙 원문 색인 (S15) ────────────────────────────
# ⛔ 두 도구의 self-test 가 먼저 통과해야 golden 대조를 믿는다. golden 대조는 fixture 저장소를 복원해
#    추출기를 실제로 돌린다 — 추출기가 바뀌어 golden 이 깨지는 것을 게이트 재실행 전에 본다.
#    루트 밖에서 돌린다(F-338 — 결과가 호출 위치와 무관해야 한다).
PR_SELF="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/scripts/extract_project_rules.py" --self-test 2>&1 && python3 "$ROOT/scripts/check_project_rules.py" --self-test 2>&1)"; PR_SELF_CODE=$?
if [ "$PR_SELF_CODE" -ne 0 ]; then
  UNRUN=$((UNRUN + 1))
  record "프로젝트 규칙 색인" UNRUN "⛔ 도구 self-test 실패 — 판정 불가 ($(printf '%s\n' "$PR_SELF" | grep -E '^FAIL|^self-test' | tail -1))"
else
  PR_OUT="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/scripts/check_project_rules.py" --fixtures "$ROOT/tests/fixtures/quality" 2>&1)"; PR_CODE=$?
  case "$PR_CODE" in
    0) record "프로젝트 규칙 색인" 0 "$(printf '%s\n' "$PR_OUT" | tail -1) · $(printf '%s\n' "$PR_SELF" | grep -E '^self-test' | tr '\n' ' ')" ;;
    1) record "프로젝트 규칙 색인" 1 "⛔ $(printf '%s\n' "$PR_OUT" | grep -E 'FIXTURE FAIL' | head -1)" ;;
    *) UNRUN=$((UNRUN + 1))
       record "프로젝트 규칙 색인" UNRUN "미실행 — $(printf '%s\n' "$PR_OUT" | tail -1) (⛔ PASS 아님)" ;;
  esac
fi

# ── 4.8c 텔레메트리 스테이지 서명 (S16) ──────────────────────────
# ⛔ craft 옵션이 arch 결과에 키(axisCoverage)를 더해도 스테이지 분류가 그대로여야 한다. 서명 표를 고치다
#    기존 서명이 빠지면 과거 run 이 조용히 other 로 집계된다. self-test 가 먼저 통과해야 실제 판정을 믿는다.
TS_BASE="$ROOT/tests/fixtures/telemetry/stage-signatures-base.json"
TS_SELF="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/tests/telemetry/stage_signatures_keys.py" --baseline "$TS_BASE" --self-test 2>&1)"; TS_SELF_CODE=$?
if [ "$TS_SELF_CODE" -ne 0 ]; then
  UNRUN=$((UNRUN + 1))
  record "텔레메트리 스테이지 서명" UNRUN "⛔ self-test 실패 — 판정 불가 ($(printf '%s\n' "$TS_SELF" | tail -1))"
else
  TS_OUT="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/tests/telemetry/stage_signatures_keys.py" --baseline "$TS_BASE" 2>&1)"; TS_CODE=$?
  case "$TS_CODE" in
    0) record "텔레메트리 스테이지 서명" 0 "$(printf '%s\n' "$TS_OUT" | tail -1) · $(printf '%s\n' "$TS_SELF" | tail -1)" ;;
    1) record "텔레메트리 스테이지 서명" 1 "$(printf '%s\n' "$TS_OUT" | grep -E '⛔' | head -1 | sed 's/^[[:space:]]*//')" ;;
    *) UNRUN=$((UNRUN + 1))
       record "텔레메트리 스테이지 서명" UNRUN "미실행 — $(printf '%s\n' "$TS_OUT" | tail -1) (⛔ PASS 아님)" ;;
  esac
fi

# ── 4.8d 결정론 병합 review_merge (S20) ──────────────────────────
# ⛔ self-test(축 분리 · 후보 보존 · 근거 재실측 · reverse→question · GPT 입력 계약)가 먼저 통과해야 fixture 대조를 믿는다.
RM_SELF="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/scripts/review_merge.py" --self-test 2>&1)"; RM_SELF_CODE=$?
if [ "$RM_SELF_CODE" -ne 0 ]; then
  UNRUN=$((UNRUN + 1))
  record "결정론 병합 review_merge" UNRUN "⛔ self-test 실패 — 판정 불가 ($(printf '%s\n' "$RM_SELF" | tail -1))"
else
  RM_OUT="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/scripts/review_merge.py" --check-fixture "$ROOT/tests/fixtures/peer-review/tier2-merge" 2>&1)"; RM_CODE=$?
  case "$RM_CODE" in
    0) record "결정론 병합 review_merge" 0 "$(printf '%s\n' "$RM_OUT" | tail -1) · $(printf '%s\n' "$RM_SELF" | tail -1)" ;;
    1) record "결정론 병합 review_merge" 1 "$(printf '%s\n' "$RM_OUT" | grep -E 'FIXTURE FAIL' | head -1)" ;;
    *) UNRUN=$((UNRUN + 1))
       record "결정론 병합 review_merge" UNRUN "미실행 — $(printf '%s\n' "$RM_OUT" | tail -1) (⛔ PASS 아님)" ;;
  esac
fi

# ── 4.8e fz-plan 기계 작업 — 델타 반영 plan_apply_delta · 독립 플랜 차이표 plan_divergence (S21) · impact 요청 해소 plan_resolve_impact_requests ──
# ⛔ self-test 만 돈다 — 실데이터(lean2 반환 · GPT 독립 플랜)는 저장소에 없고 fz-plan 배선은 뒤 스텝이다. 질문형 impact 요청 셀은 tests/fixtures/plan-impact/question-form 이 아래 4.6 글롭에서 돈다.
for PS in plan_apply_delta plan_divergence plan_resolve_impact_requests; do
  PS_OUT="$(cd "${TMPDIR:-/tmp}" && python3 "$ROOT/scripts/$PS.py" --self-test 2>&1)"; PS_CODE=$?
  case "$PS_CODE" in
    0) record "fz-plan 기계 작업 $PS" 0 "$(printf '%s\n' "$PS_OUT" | tail -1)" ;;
    1) record "fz-plan 기계 작업 $PS" 1 "⛔ $(printf '%s\n' "$PS_OUT" | grep -E '^FAIL' | head -1) · $(printf '%s\n' "$PS_OUT" | tail -1)" ;;
    *) UNRUN=$((UNRUN + 1))   # ⛔ exit 2 는 측정 불가다 — 실패로도 통과로도 세지 않는다(4.8c 와 같은 규약)
       record "fz-plan 기계 작업 $PS" UNRUN "미실행 exit $PS_CODE — $(printf '%s\n' "$PS_OUT" | tail -1) (⛔ PASS 아님)" ;;
  esac
done

# ── 4.8f fz-review 사전 수집 스냅샷 review_snapshot (S22b) ──────────
# ⛔ self-test 만 돈다 — 임시 git 저장소로 수정 · 삭제 · rename · 바이너리 · 공백 든 미추적 새 파일 · 종료 코드를 본다.
RS_OUT="$(cd "${TMPDIR:-/tmp}" && bash "$ROOT/scripts/review_snapshot.sh" --self-test 2>&1)"; RS_CODE=$?
case "$RS_CODE" in
  0) record "사전 수집 스냅샷 review_snapshot" 0 "$(printf '%s\n' "$RS_OUT" | tail -1)" ;;
  *) record "사전 수집 스냅샷 review_snapshot" 1 "⛔ $(printf '%s\n' "$RS_OUT" | grep -E '^FAIL' | head -1) · $(printf '%s\n' "$RS_OUT" | tail -1)" ;;
esac

# ── 4.8b A/B 원장 판정기 + 프로토콜 절 ──────────────────────────
# ⛔ 판정기 self-test(SC-3·SC-6·교차 순서·AC-1·AC-5·AC-7·SC-4·SC-7·입력 해시)가 판정을 믿을 전제다.
#    collect→score→judge 통합(원천 파서·증거 사본·원천 재대조·측정값 고정)은
#    tests/fixtures/ab/mini-ledger/run.sh 가 회귀 오라클로 돈다.
ABL_SELF="$(cd "$ROOT" && python3 scripts/ab_ledger.py --self-test 2>&1)"; ABL_CODE=$?
if [ "$ABL_CODE" -eq 0 ]; then
  record "A/B 원장 판정기" 0 "$(printf '%s\n' "$ABL_SELF" | tail -1)"
else
  UNRUN=$((UNRUN + 1))
  record "A/B 원장 판정기" UNRUN "⛔ self-test 실패 — 판정 불가 ($(printf '%s\n' "$ABL_SELF" | tail -1))"
fi
ABP_SELF="$(cd "$ROOT" && python3 scripts/check_ab_protocol.py --self-test 2>&1)"; ABP_SELF_CODE=$?
if [ "$ABP_SELF_CODE" -ne 0 ]; then
  UNRUN=$((UNRUN + 1))
  record "A/B 프로토콜 절" UNRUN "⛔ 검사기 self-test 실패 — 판정 불가 ($(printf '%s\n' "$ABP_SELF" | tail -1))"
else
  ABP_OUT="$(cd "$ROOT" && python3 scripts/check_ab_protocol.py experiment-log.md 2>&1)"; ABP_CODE=$?
  case "$ABP_CODE" in
    0) record "A/B 프로토콜 절" 0 "$(printf '%s\n' "$ABP_OUT" | tail -1) · $(printf '%s\n' "$ABP_SELF" | tail -1)" ;;
    1) record "A/B 프로토콜 절" 1 "⛔ $(printf '%s\n' "$ABP_OUT" | grep -E 'MISSING' | head -1)" ;;
    *) UNRUN=$((UNRUN + 1))
       record "A/B 프로토콜 절" UNRUN "미실행 — $(printf '%s\n' "$ABP_OUT" | tail -1) (⛔ PASS 아님)" ;;
  esac
fi

# ── 4.9 발견 레지스트리 도구 self-test ────────────────────────────
# ⛔ 신설 근거: `chk_12` 는 lint_contracts 에 배선했으면서 **새 스크립트 2종의 self-test 는
#    통합 검사에서 한 번도 돌지 않았다**(비대칭). 배선 안 된 검사는 회귀를 못 잡는다.
# ⛔ 스크립트가 없으면 UNRUN 이 아니다 — 위 사전조건이 이미 부재를 exit 2 로 잡는다.
for FS in check_release_notes check_report_regen eject_findings check_findings_hygiene check_release_closes migrate_findings_frontmatter check_symptom_anchor check_external_commands check_global_budget check_asset_census report_stale_findings autonomy_decide check_failure_table check_single_source candidate_expiry check_wf_advisor_ban check_gpt_surface check_gpt_skill_portability gpt_kinds gpt_merge gpt_ab_decide mode_gate counter_adapter gpt_rounds health_select check_retired_commands run_runners check_evidence_slots fz_snapshot fz_stop_telemetry fz_telemetry_report lint_contracts lint_doc_freshness run_metrics check_health_wiring check_synthesized check_comment_worthy intent_route_probe; do
  FS_OUT="$(cd "$ROOT" && python3 "scripts/$FS.py" --self-test 2>&1)"; FS_CODE=$?
  record3 "레지스트리 도구 self-test ($FS)" "$FS_CODE" "$FS_OUT" \
    "$(printf '%s\n' "$FS_OUT" | grep -E '^self-test' | tail -1)" \
    "⛔ $(printf '%s\n' "$FS_OUT" | grep -E 'FAIL|self-test' | tail -1)"
done

# ── 4.9a health-check 배선 대조 (F-529) ─────────────────────────
# ⛔ 위 등록 목록(존재 확인 · self-test 루프)은 손으로 관리한다 — `--self-test` 를 가진 스크립트가 어디서도 안 돌거나
#    루프가 부르는 스크립트가 존재 목록에 없으면 여기서 걸린다. 감지기가 이미 배선된 스크립트를 못 보면 UNRUN 이다(PASS 아님).
HW_OUT="$(cd "$ROOT" && python3 scripts/check_health_wiring.py 2>&1)"; HW_CODE=$?
record3 "health-check 배선 대조" "$HW_CODE" "$HW_OUT" \
  "$(printf '%s\n' "$HW_OUT" | head -1)" \
  "⛔ $(printf '%s\n' "$HW_OUT" | grep -E '✗' | head -2 | tr '\n' ' ')"

# ── 4.9b GPT kind 레지스트리 lint (R-G1 S3) ───────────────────
# ⛔ self-test 는 검사기만 본다 — 실제 레지스트리(scripts/gpt-kinds.json)와 역할 파일(gpt-agents · gpt-skills/*/agents)의
#    model · effort 핀은 lint 로 따로 본다. 레지스트리 손상은 exit 11 이다(PASS 아님).
GKL="$(cd "$ROOT" && python3 scripts/gpt_kinds.py lint --root "$ROOT" 2>&1)"; GKL_CODE=$?
record3 "GPT kind 레지스트리 lint" "$GKL_CODE" "$GKL" \
  "$(printf '%s\n' "$GKL" | grep -E '^GPT-KINDS-LINT' | tail -1)" \
  "⛔ $(printf '%s\n' "$GKL" | grep -E '^LINT|^GPT-KINDS-LINT' | head -1)"

# ── 4.9c GPT 소비자 lint · 생성 표 drift (R-G1) ───────────────
# ⛔ 정문 하나(AC-1)를 막는 것은 소비자 lint 다 — 스텝 verify 에서 한 번 돌고 끝나면 그 뒤 회귀를 못 잡는다(아무도 안 돌리는 oracle).
#    생성 표(skills/fz-gpt/SKILL.md)도 레지스트리와 어긋나면 손으로 고친 표가 정본처럼 남는다
GKC="$(cd "$ROOT" && python3 scripts/gpt_kinds.py lint --consumers --allowed-tools --root "$ROOT" 2>&1)"; GKC_CODE=$?
record3 "GPT 소비자 lint (정문 경유 · allowed-tools)" "$GKC_CODE" "$GKC" \
  "$(printf '%s\n' "$GKC" | grep -E '^GPT-KINDS-CONSUMERS' | tail -1)" \
  "⛔ $(printf '%s\n' "$GKC" | grep -E '^LINT|^GPT-KINDS-CONSUMERS' | head -1)"
GKT="$(cd "$ROOT" && python3 scripts/gpt_kinds.py table --check --root "$ROOT" 2>&1)"; GKT_CODE=$?
record3 "GPT kind 생성 표 drift" "$GKT_CODE" "$GKT" \
  "$(printf '%s\n' "$GKT" | grep -E '^GPT-KINDS-TABLE' | tail -1)" \
  "⛔ $(printf '%s\n' "$GKT" | grep -E '^TABLE|^GPT-KINDS-TABLE' | head -1)"

# ── Workflow 계측기 self-test (B6/S5) ─────────────────────────
# ⛔ 12케이스가 통합 검사에서 **한 번도 돌지 않았다**(§4.9 가 경고한 비대칭 그대로).
#    `--mcp-audit` 3분 판정도 여기서만 회귀가 잡힌다.
WM="$(cd "$ROOT" && python3 scripts/fz_wf_metrics.py --self-test 2>&1)"; WM_CODE=$?
record3 "Workflow 계측기 self-test" "$WM_CODE" "$WM" \
  "$(printf '%s\n' "$WM" | grep -E 'SELFTEST_OK' | tail -1)" \
  "⛔ $(printf '%s\n' "$WM" | grep -E 'FAIL|self-test' | tail -1)"

# ── Workflow 실패 처방 표 계약 (C2) ───────────────────────────
# ⛔ self-test 와 별도로 **실제 표**를 검사한다 — self-test 는 검사기가 살아 있는지만 본다.
FT="$(cd "$ROOT" && python3 scripts/check_failure_table.py 2>&1)"; FT_CODE=$?
record3 "실패 처방 표 계약" "$FT_CODE" "$FT" \
  "$(printf '%s\n' "$FT" | grep -E 'expected=' | tail -1)" \
  "⛔ $(printf '%s\n' "$FT" | grep -E 'VIOLATION|UNRUN|⛔' | tail -1)"

# ── plan 계약 왕복 (B14 / SC1~SC2) ────────────────────────────
# ⛔ **파일 존재는 계약 복구의 증거가 아니다.** v7 의 done 판정 오라클이
#    `plan_integrity_check.py` **존재**였고, 그것은 왕복이 도는지를 말해주지 않는다.
#    이 검사기는 self-test 가 있는데 통합 검사에서 **한 번도 돌지 않았다**(실측 0건 참조).
PI="$(cd "$ROOT" && python3 scripts/plan_integrity_check.py --self-test tests/fixtures/plan-integrity 2>&1)"; PI_CODE=$?
record3 "plan 계약 왕복" "$PI_CODE" "$PI" \
  "$(printf '%s\n' "$PI" | grep -E 'INTEGRITY_SELFTEST_OK' | tail -1)" \
  "⛔ $(printf '%s\n' "$PI" | grep -E 'FAIL|SELFTEST' | tail -1)"

# ── 단일 출처 계약 (C4) ───────────────────────────────────────
# ⛔ 정수 단언이다 — "있다/없다" 는 두 벌로 늘어난 것을 놓친다.
chk_single_source

# ── 워크플로 advisor 억제 계약 (A-ADV) ─────────────────────────
# ⛔ 워커는 세션 advisorModel 을 상속하고 끌 수단이 없다 — OVERRIDE 상수의 금지 문구가 유일한 억제다.
#    파일 단위가 아니라 OVERRIDE **블록 단위**로 본다(주석·다른 문자열은 워커에게 안 실린다).
AB="$(cd "$ROOT" && python3 scripts/check_wf_advisor_ban.py 2>&1)"; AB_CODE=$?
record3 "워크플로 advisor 억제" "$AB_CODE" "$AB" \
  "$(printf '%s\n' "$AB" | grep -E '^advisor-ban' | tail -1)" \
  "⛔ $(printf '%s\n' "$AB" | grep -E 'VIOLATION|UNRUN' | head -1)"

# ── GPT 표면 계약 (Track C) ──────────────────────────────────
# ⛔ 보존 규칙 밖 옛 CLI 호칭(Track C)의 **재유입**을 막는다. 허용은 범주 토큰 + `tests/fixtures/gpt-surface-keep.tsv` 뿐이다.
GS="$(cd "$ROOT" && python3 scripts/check_gpt_surface.py 2>&1)"; GS_CODE=$?
record3 "GPT 표면 계약" "$GS_CODE" "$GS" \
  "$(printf '%s\n' "$GS" | grep -E '^gpt-surface' | tail -1)" \
  "⛔ $(printf '%s\n' "$GS" | grep -E 'VIOLATION|UNRUN' | head -1)"

# ── GPT 스킬 이식성 (S12 · AC-3) ─────────────────────────────
# ⛔ 번들 GPT 스킬이 특정 프레임워크·작성자 관례를 보편 규칙으로 박지 않는다 — 규칙은 런타임 추출, 스택 지식은 조건부 팩.
GP="$(cd "$ROOT" && python3 scripts/check_gpt_skill_portability.py 2>&1)"; GP_CODE=$?
record3 "GPT 스킬 이식성" "$GP_CODE" "$GP" \
  "$(printf '%s\n' "$GP" | grep -E '^gpt-skill-portability' | tail -1)" \
  "⛔ $(printf '%s\n' "$GP" | grep -E 'VIOLATION|UNRUN' | head -1)"

# ── 릴리즈 동기 검사기 self-test (B1/S7) ──────────────────────
# ⛔ **`--self-test` 만 부른다.** 기본·`--release` 모드는 health-check 를 **자기가 호출하므로**
#    여기서 부르면 무한 재귀가 된다. self-test 경로는 그보다 앞에서 exit 하므로 안전하다.
RS="$(cd "$ROOT" && bash scripts/check_release_sync.sh --self-test 2>&1)"; RS_CODE=$?
record3 "릴리즈 동기 self-test" "$RS_CODE" "$RS" \
  "$(printf '%s\n' "$RS" | grep -E '^self-test' | tail -1)" \
  "⛔ $(printf '%s\n' "$RS" | grep -E 'FAIL|self-test|픽스처' | tail -1)"

# ── 4.10 baseline 기준점 (B15) ────────────────────────────────
# ⛔ self-test 만 돌린다. `--verify` 를 여기 넣으면 **트리를 고칠 때마다 빨개진다** —
#    baseline 은 "바뀌면 안 되는 것" 이 아니라 "무엇과 비교하는지" 의 기준점이다
#    (§3 freshness·§4.8 부하추세와 같은 클래스). 실제 대조는 감량·측정 작업이 명시적으로 부른다.
FB="$(cd "$ROOT" && python3 scripts/freeze_baseline.py --self-test 2>&1)"; FB_CODE=$?
record3 "baseline 동결기 self-test" "$FB_CODE" "$FB" \
  "$(printf '%s\n' "$FB" | grep -E '^self-test' | tail -1)" \
  "⛔ $(printf '%s\n' "$FB" | grep -E 'FAIL|self-test' | tail -1)"
if [ -f "$ROOT/tests/fixtures/baseline-manifest.json" ]; then
  record "baseline manifest 실재" 0 "$(python3 -c "
import json;d=json.load(open('$ROOT/tests/fixtures/baseline-manifest.json'))
print(f\"{d['date']} · 파일 {d['file_count']}건 · HEAD {str(d.get('git_head'))[:8]}\")" 2>/dev/null)"
else
  UNRUN=$((UNRUN + 1))
  record "baseline manifest 실재" UNRUN "미동결 — \`freeze_baseline.py --freeze\` (⛔ PASS 아님)"
fi

# ── 4.8 하네스 정적 부하 추세 (경고 전용) ─────────────────────────
# ⛔ 실패가 아니다. floor 성장은 "고쳐야 할 위반"이 아니라 **관측**이고, exit 에 반영하면
#    릴리즈마다 빨개져 사람이 health-check 자체를 안 돌리게 된다(§3 freshness 와 같은 클래스).
# ⛔ 스크립트 부재·행 2개 미만은 미실행이 아니라 **비교 대상 없음**이다 — 아직 스냅샷을
#    안 찍은 정상 상태이므로 UNRUN 으로 세지 않는다.
if [ -f "$ROOT/scripts/fz_snapshot.py" ]; then
  SNAP_OUT="$(python3 "$ROOT/scripts/fz_snapshot.py" --diff 2>&1)"; SNAP_CODE=$?
  SNAP_WARN="$(printf '%s\n' "$SNAP_OUT" | grep -c '⚠️' || true)"
  # ⛔ "비교 대상 없음"(정상, exit 0 + 안내문)과 "검사기 고장"(exit≠0)은 다른 것이다 — GPT 리뷰(2026-09-06)가
  #    exit 7 이 record 0 으로 덮이는 것을 재현했다. 고장은 §diff 파서와 같은 규약(record 2 + UNRUN)으로 기록한다.
  if [ "$SNAP_CODE" -ne 0 ]; then
    record "정적 부하 추세" 2 "⛔ 검사기 비정상 종료 exit $SNAP_CODE — 판정 불가 ($(printf '%s\n' "$SNAP_OUT" | tail -1))"
    UNRUN=$((UNRUN+1))
  elif printf '%s\n' "$SNAP_OUT" | grep -q '비교 불가'; then
    record "정적 부하 추세" 0 "비교 대상 없음 — $(printf '%s\n' "$SNAP_OUT" | tail -1) (스냅샷 2행 미만, 정상)"
  elif [ "${SNAP_WARN:-0}" -gt 0 ]; then
    record "정적 부하 추세" 0 "⚠️ floor 10% 이상 증가 ${SNAP_WARN}건 — $(printf '%s\n' "$SNAP_OUT" | tail -1)"
  else
    record "정적 부하 추세" 0 "$(printf '%s\n' "$SNAP_OUT" | tail -1)"
  fi
else
  UNRUN=$((UNRUN+1))
  record "정적 부하 추세" UNRUN "미실행 — fz_snapshot.py 부재 (⛔ PASS 아님)"
fi

# ── 4.8h 로드 체크아웃 대조 (경고 전용 · F-507) ───────────────────
# ⛔ 로드본이 뒤처진 것은 이 트리의 결함이 아니라 **배포 상태**다 — exit 에 반영하지 않는다(4.8 과 같은 이유).
#    검사기 고장(self-test 실패)만 판정 불가로 센다. 로드 루트는 사용자마다 달라 env FZ_LOADED_ROOT 로만 받는다.
LV_SELF="$(python3 "$ROOT/scripts/check_loaded_version.py" --self-test 2>&1)"; LV_SELF_CODE=$?
if [ "$LV_SELF_CODE" -ne 0 ]; then
  record "로드본 대조" 2 "⛔ 검사기 self-test 실패 — 판정 불가 ($(printf '%s\n' "$LV_SELF" | tail -1))"
  UNRUN=$((UNRUN+1))
elif [ -n "${FZ_LOADED_ROOT:-}" ]; then
  LV_OUT="$(python3 "$ROOT/scripts/check_loaded_version.py" 2>&1 | head -1)"
  case "$LV_OUT" in
    LOADED_OK*|LOADED_AHEAD*) record "로드본 대조" 0 "$LV_OUT" ;;
    *) record "로드본 대조" 0 "⚠️ $LV_OUT (경고, 실패 아님)" ;;
  esac
else
  record "로드본 대조" 0 "FZ_LOADED_ROOT 미지정 — 대조 생략 · $(printf '%s\n' "$LV_SELF" | tail -1)"
fi

# ── 4.8i 하네스 계측기 self-test (H0) ─────────────────────────────
# ⛔ 모집단 대조기 · 런타임 로드 계측기는 원장과 트랜스크립트를 인자로 받는다 — 여기서는 검사기만 본다(원장 대조는 계획 단계 몫).
HM_OUT="$( (python3 "$ROOT/scripts/harness_census.py" --self-test && python3 "$ROOT/scripts/measure_runtime_load.py" --self-test) 2>&1)"; HM_CODE=$?
record3 "하네스 계측기 self-test" "$HM_CODE" "$HM_OUT" \
  "$(printf '%s\n' "$HM_OUT" | grep -E 'self-test: PASS' | tr '\n' ' ')" \
  "⛔ $(printf '%s\n' "$HM_OUT" | grep -E 'FAIL' | head -2 | tr '\n' ' ')"

# ── 4.8j 재발 방지 lint 7종 (B6) ──────────────────────────────────
# ⛔ self-test 먼저 — 검사기 고장을 "위반 0"으로 읽지 않는다. 트리 실행의 UNRUN(대상 0개)은 PASS 가 아니다(exit 2).
#    모듈 500줄 초과는 경고(WARN)라 exit 0 이다(F-485) — 실패는 SKILL 500줄 · 사본 불일치 · TEAM 지시 · 끊긴 참조 · 개수 불일치.
chk_recurrence
chk_retired_commands

# ── 5. 플러그인 매니페스트
# ⛔ ISSUE-001 (CRITICAL) 정정: 이전 판은 `claude` 부재를 **exit 0으로 기록**해
#    표에 ✅가 찍히고 총평이 "전 검사 통과"로 나왔다 — 플러그인 로딩이 **검증되지 않았는데도**.
#    주석으로 "PASS 아님"이라 적어도 **기계 판정이 PASS라면 그게 판정**이다.
#    이 스크립트가 다른 곳에서 강제하는 "SKIP ≠ PASS"를 스스로 위반하고 있었다.
# ⛔ A5-02: 루트 디렉터리를 대상으로 주면 CLI 가 marketplace 매니페스트만 검증해 스킬·에이전트 frontmatter 가
#    깨져도 통과했다. 대상 선택·경고 판정은 단일 지점 scripts/plugin_validate.sh 가 정한다 — 여기서 CLI 를 직접 부르지 않는다.
if command -v claude >/dev/null 2>&1; then
  VAL_SELF="$(bash "$ROOT/scripts/plugin_validate.sh" --self-test 2>&1)"; VAL_SELF_CODE=$?
  VAL_OUT="$(bash "$ROOT/scripts/plugin_validate.sh" "$ROOT" 2>&1)"; VAL_CODE=$?
  if [ "$VAL_SELF_CODE" -ne 0 ]; then
    record "plugin validate" 1 "⛔ 판정기 self-test 실패 — $(printf '%s\n' "$VAL_SELF" | grep -E 'FAIL|self-test' | head -2 | tr '\n' ' ')"
  elif [ "$VAL_CODE" -eq 0 ]; then
    record "plugin validate" 0 "$(printf '%s\n' "$VAL_OUT" | tail -1) · $(printf '%s\n' "$VAL_SELF" | tail -1)"
  else
    record "plugin validate" "$VAL_CODE" "⛔ $(printf '%s\n' "$VAL_OUT" | grep -E 'FAIL|UNRUN' | head -2 | tr '\n' ' ')"
  fi
else
  UNRUN=$((UNRUN + 1))
  record "plugin validate" UNRUN "미실행 — claude CLI 부재 (⛔ PASS 아님)"
fi

# ── 5.1 fz-compact 하위 플러그인 (mods/fz-compact) — 루트 plugin.json 검증은 하위 매니페스트를 보지 않으므로 따로 돈다.
#    plugin test: rc 0 = 통과 · `(fail)` 줄이 있으면 실패 · 그 밖(하위 명령이 없는 옛 CLI 등)은 미실행(⛔ PASS 아님).
if command -v claude >/dev/null 2>&1; then
  FC_VAL="$(bash "$ROOT/scripts/plugin_validate.sh" "$ROOT/mods/fz-compact" 2>&1)"; FC_VAL_CODE=$?
  record3 "fz-compact validate" "$FC_VAL_CODE" "$FC_VAL" "$(printf '%s\n' "$FC_VAL" | tail -1)" "⛔ $(printf '%s\n' "$FC_VAL" | grep -E 'FAIL|UNRUN' | head -2 | tr '\n' ' ')"
  FC_TEST="$(cd "$ROOT" && claude plugin test "$ROOT/mods/fz-compact" 2>&1)"; FC_TEST_CODE=$?
  FC_FAIL="$(printf '%s\n' "$FC_TEST" | grep '^(fail) ' | head -2 | tr '\n' ' ')"
  if [ "$FC_TEST_CODE" -ne 0 ] && [ -z "$FC_FAIL" ]; then
    UNRUN=$((UNRUN + 1)); record "fz-compact test" UNRUN "미실행 — plugin test 가 돌지 않았다 (rc $FC_TEST_CODE · ⛔ PASS 아님)"
  elif [ "$FC_TEST_CODE" -eq 0 ]; then
    record "fz-compact test" 0 "$(printf '%s\n' "$FC_TEST" | grep -E '^ *[0-9]+ pass' | head -1 | tr -s ' ')"
  else
    record "fz-compact test" 1 "⛔ $FC_FAIL"
  fi
else
  UNRUN=$((UNRUN + 2))
  record "fz-compact validate" UNRUN "미실행 — claude CLI 부재 (⛔ PASS 아님)"
  record "fz-compact test" UNRUN "미실행 — claude CLI 부재 (⛔ PASS 아님)"
fi
# fz-compact guard — hooks/guard.sh(classic PreCompact 차단 훅) 판정 시험 + guard.sh 가 마커 모양을 베낀 register.ts 줄 대조.
#    POSIX sh 만 쓰고 claude CLI 가 필요 없어 위 분기 밖에서 돈다. 0 = 통과(요약 줄) · 그 밖 = 실패(출력 앞 두 줄).
FC_GUARD="$(sh "$ROOT/mods/fz-compact/tests/guard_test.sh" 2>&1)"; FC_GUARD_CODE=$?
if [ "$FC_GUARD_CODE" -eq 0 ]; then
  record "fz-compact guard" 0 "$(printf '%s\n' "$FC_GUARD" | tail -1)"
else
  record "fz-compact guard" 1 "⛔ $(printf '%s\n' "$FC_GUARD" | head -2 | tr '\n' ' ')"
fi

# ── 보고
report_and_exit
