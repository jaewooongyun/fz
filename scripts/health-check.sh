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
for f in lint_contracts.py lint-model-explicit.sh lint_doc_freshness.py gate_check.py gate_stop_hook.py lint_diff_parsers.py check-gpt-flags.sh check_codegraph_fresh.py check_g8_style.py eject_findings.py check_findings_hygiene.py freeze_baseline.py migrate_findings_frontmatter.py check_symptom_anchor.py check_external_commands.py check_global_budget.py check_asset_census.py check_release_sync.sh fz_wf_metrics.py report_stale_findings.py autonomy_decide.py check_failure_table.py check_single_source.py check_k_cluster.py check_host_census.py candidate_expiry.py; do
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
GATE_OUT="$(cd "$ROOT" && python3 scripts/gate_check.py --self-test 2>&1)"; GATE_CODE=$?
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

# ── 4.5 gpt 플래그 호환성
# ⛔ 신설 근거: `check-gpt-flags.sh` 는 review 경로가 거부하는 플래그를 잡는 회귀 게이트인데
#    어느 자동 실행 경로에도 없었다(health-check 참조 0건 · gpt-exec.sh 는 주석만).
#    막으려던 실패 = 공용 인자 배열이 `codex exec review` 에 거부돼 exit 2 를 내고
#    호출부가 그것을 "이슈 0건" 으로 읽는 것. CLI 가 플래그 집합을 바꾸면 침묵한다.
# ⛔ exit 2(codex CLI 부재·help 파싱 실패)는 **PASS 가 아니라 미실행**이다 — §4 와 같은 클래스.
CF_OUT="$(bash "$ROOT/scripts/check-gpt-flags.sh" 2>&1)"; CF_CODE=$?
case "$CF_CODE" in
  0) record "gpt 플래그 호환성" 0 "review 미지원 플래그 0건" ;;
  1) record "gpt 플래그 호환성" 1 "⛔ review 경로에 미지원 플래그 — $(printf '%s\n' "$CF_OUT" | tail -1)" ;;
  *) UNRUN=$((UNRUN + 1))
     record "gpt 플래그 호환성" UNRUN "미실행 — codex CLI 부재·help 파싱 실패 (⛔ PASS 아님)" ;;
esac

# ── 4.6 회귀 오라클 실행 (tests/) ─────────────────────────────────
# ⛔ 신설 근거: 오라클이 **아무 자동 경로에도 없었다**. `tests/workflows/*.js` 3종 중
#    참조 1곳(s2-cross-merge)뿐이고 d6·s2-stage2-trigger 는 0곳, `tests/fixtures/*/run.sh`
#    7종도 health-check 가 보지 않았다. 아무도 안 돌리는 오라클은 오라클이 아니다 —
#    회귀가 나도 통합 건강 체크가 초록으로 통과한다.
# ⛔ 러너를 **0개 발견**한 경우는 PASS 가 아니라 미실행이다: 경로 오타·디렉터리 이동이
#    "전건 통과" 로 인쇄되는 것이 정확히 막으려는 실패다(0건은 측정 실패를 먼저 의심).
if command -v node >/dev/null 2>&1; then
  T_TOTAL=0 T_FAIL=0 T_BAD=""
  for f in "$ROOT"/tests/workflows/*.js; do
    [ -f "$f" ] || continue
    T_TOTAL=$((T_TOTAL + 1))
    (cd "$ROOT" && node "$f" >/dev/null 2>&1) || { T_FAIL=$((T_FAIL + 1)); T_BAD="$T_BAD $(basename "$f")"; }
  done
  for r in "$ROOT"/tests/fixtures/*/*/run.sh; do
    [ -f "$r" ] || continue
    T_TOTAL=$((T_TOTAL + 1))
    (cd "$ROOT" && bash "$r" >/dev/null 2>&1) || { T_FAIL=$((T_FAIL + 1)); T_BAD="$T_BAD $(basename "$(dirname "$r")")"; }
  done
  if [ "$T_TOTAL" -eq 0 ]; then
    UNRUN=$((UNRUN + 1))
    record "회귀 오라클" UNRUN "미실행 — 러너 0개 발견 (경로 오타 의심, ⛔ PASS 아님)"
  elif [ "$T_FAIL" -eq 0 ]; then
    record "회귀 오라클" 0 "${T_TOTAL}개 전건 통과"
  else
    record "회귀 오라클" 1 "⛔ ${T_FAIL}/${T_TOTAL} 실패 —$T_BAD"
  fi
else
  UNRUN=$((UNRUN + 1))
  record "회귀 오라클" UNRUN "미실행 — node 부재 (⛔ PASS 아님)"
fi

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

# ── 4.9 발견 레지스트리 도구 self-test ────────────────────────────
# ⛔ 신설 근거: `chk_12` 는 lint_contracts 에 배선했으면서 **새 스크립트 2종의 self-test 는
#    통합 검사에서 한 번도 돌지 않았다**(비대칭). 배선 안 된 검사는 회귀를 못 잡는다.
# ⛔ 스크립트가 없으면 UNRUN 이 아니다 — 위 사전조건이 이미 부재를 exit 2 로 잡는다.
for FS in eject_findings check_findings_hygiene migrate_findings_frontmatter check_symptom_anchor check_external_commands check_global_budget check_asset_census report_stale_findings autonomy_decide check_failure_table check_single_source check_k_cluster check_host_census candidate_expiry; do
  FS_OUT="$(cd "$ROOT" && python3 "scripts/$FS.py" --self-test 2>&1)"; FS_CODE=$?
  if [ "$FS_CODE" -eq 0 ]; then
    record "레지스트리 도구 self-test ($FS)" 0 "$(printf '%s\n' "$FS_OUT" | grep -E '^self-test' | tail -1)"
  else
    record "레지스트리 도구 self-test ($FS)" 1 "⛔ $(printf '%s\n' "$FS_OUT" | grep -E 'FAIL|self-test' | tail -1)"
  fi
done

# ── Workflow 계측기 self-test (B6/S5) ─────────────────────────
# ⛔ 12케이스가 통합 검사에서 **한 번도 돌지 않았다**(§4.9 가 경고한 비대칭 그대로).
#    `--mcp-audit` 3분 판정도 여기서만 회귀가 잡힌다.
WM="$(cd "$ROOT" && python3 scripts/fz_wf_metrics.py --self-test 2>&1)"; WM_CODE=$?
if [ "$WM_CODE" -eq 0 ]; then
  record "Workflow 계측기 self-test" 0 "$(printf '%s\n' "$WM" | grep -E 'SELFTEST_OK' | tail -1)"
else
  record "Workflow 계측기 self-test" 1 "⛔ $(printf '%s\n' "$WM" | grep -E 'FAIL|self-test' | tail -1)"
fi

# ── Workflow 실패 처방 표 계약 (C2) ───────────────────────────
# ⛔ self-test 와 별도로 **실제 표**를 검사한다 — self-test 는 검사기가 살아 있는지만 본다.
FT="$(cd "$ROOT" && python3 scripts/check_failure_table.py 2>&1)"; FT_CODE=$?
if [ "$FT_CODE" -eq 0 ]; then
  record "실패 처방 표 계약" 0 "$(printf '%s\n' "$FT" | grep -E 'expected=' | tail -1)"
else
  record "실패 처방 표 계약" 1 "⛔ $(printf '%s\n' "$FT" | grep -E 'VIOLATION|UNRUN|⛔' | tail -1)"
fi

# ── plan 계약 왕복 (B14 / SC1~SC2) ────────────────────────────
# ⛔ **파일 존재는 계약 복구의 증거가 아니다.** v7 의 done 판정 오라클이
#    `plan_integrity_check.py` **존재**였고, 그것은 왕복이 도는지를 말해주지 않는다.
#    이 검사기는 self-test 가 있는데 통합 검사에서 **한 번도 돌지 않았다**(실측 0건 참조).
PI="$(cd "$ROOT" && python3 scripts/plan_integrity_check.py --self-test tests/fixtures/plan-integrity 2>&1)"; PI_CODE=$?
if [ "$PI_CODE" -eq 0 ]; then
  record "plan 계약 왕복" 0 "$(printf '%s\n' "$PI" | grep -E 'INTEGRITY_SELFTEST_OK' | tail -1)"
else
  record "plan 계약 왕복" 1 "⛔ $(printf '%s\n' "$PI" | grep -E 'FAIL|SELFTEST' | tail -1)"
fi

# ── 단일 출처 계약 (C4) ───────────────────────────────────────
# ⛔ 정수 단언이다 — "있다/없다" 는 두 벌로 늘어난 것을 놓친다.
SS="$(cd "$ROOT" && python3 scripts/check_single_source.py 2>&1)"; SS_CODE=$?
if [ "$SS_CODE" -eq 0 ]; then
  record "단일 출처 계약" 0 "$(printf '%s\n' "$SS" | grep -E 'canonical=' | tail -1)"
else
  record "단일 출처 계약" 1 "⛔ $(printf '%s\n' "$SS" | grep -E 'VIOLATION|UNRUN|⛔' | tail -1)"
fi

# ── 릴리즈 동기 검사기 self-test (B1/S7) ──────────────────────
# ⛔ **`--self-test` 만 부른다.** 기본·`--release` 모드는 health-check 를 **자기가 호출하므로**
#    여기서 부르면 무한 재귀가 된다. self-test 경로는 그보다 앞에서 exit 하므로 안전하다.
RS="$(cd "$ROOT" && bash scripts/check_release_sync.sh --self-test 2>&1)"; RS_CODE=$?
if [ "$RS_CODE" -eq 0 ]; then
  record "릴리즈 동기 self-test" 0 "$(printf '%s\n' "$RS" | grep -E '^self-test' | tail -1)"
else
  record "릴리즈 동기 self-test" 1 "⛔ $(printf '%s\n' "$RS" | grep -E 'FAIL|self-test|픽스처' | tail -1)"
fi

# ── 4.10 baseline 기준점 (B15) ────────────────────────────────
# ⛔ self-test 만 돌린다. `--verify` 를 여기 넣으면 **트리를 고칠 때마다 빨개진다** —
#    baseline 은 "바뀌면 안 되는 것" 이 아니라 "무엇과 비교하는지" 의 기준점이다
#    (§3 freshness·§4.8 부하추세와 같은 클래스). 실제 대조는 감량·측정 작업이 명시적으로 부른다.
FB="$(cd "$ROOT" && python3 scripts/freeze_baseline.py --self-test 2>&1)"; FB_CODE=$?
if [ "$FB_CODE" -eq 0 ]; then
  record "baseline 동결기 self-test" 0 "$(printf '%s\n' "$FB" | grep -E '^self-test' | tail -1)"
else
  record "baseline 동결기 self-test" 1 "⛔ $(printf '%s\n' "$FB" | grep -E 'FAIL|self-test' | tail -1)"
fi
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
  # ⛔ "비교 대상 없음"(정상, exit 0 + 안내문)과 "검사기 고장"(exit≠0)은 다른 것이다 — Codex 리뷰(2026-09-06)가
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

# ── 4.9 codegraph stale 검사기 self-test ──────────────────────────
#    ⛔ 여기서 재는 것은 **검사기의 건강성**이지 인덱스 신선도가 아니다.
#       인덱스 신선도는 대상 레포에서 `--repo <path>` 로 돌린다 — 플러그인 루트에는
#       .codegraph/ 가 없어 여기서 돌리면 항상 UNRUN 이고, UNRUN 은 health-check 를
#       exit 2 로 만들어 릴리즈 경로를 막는다(부재를 실패로 오귀속하는 형태).
#    ⛔ 등재만으로는 실행되지 않는다 — 0번 사전조건 루프는 `[ -f ]` 존재 확인이다.
CG_OUT="$(python3 "$ROOT/scripts/check_codegraph_fresh.py" --self-test 2>&1)"; CG_CODE=$?
case "$CG_CODE" in
  0) record "codegraph stale 검사기" 0 "$(printf '%s\n' "$CG_OUT" | tail -1) · 인덱스 신선도는 --repo 로 별도" ;;
  *) record "codegraph stale 검사기" "$CG_CODE" "⛔ self-test 실패 — 판정 불가 ($(printf '%s\n' "$CG_OUT" | tail -1))" ;;
esac

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
