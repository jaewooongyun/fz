#!/bin/bash
# 원장 `ENV:` 미판정 · `TOOLS:` 환경 드리프트 회귀 판정 (F-342 · F-291).
#
# F-342: `${NAME:?}` 로 막아 둔 CHECK 를 변수 없이 다시 돌리면 셸이 exit 127 을 내고 판정기가 그것을 FAIL 로 기록해 통과 증거를
#   강등했다. → `ENV:` 로 선언한 변수가 없거나 비면 CHECK 를 돌리지 않고 UNRUN(exit 1 · 원장 무변경).
# F-291: 통과한 게이트의 선언 도구가 사라지면 `--reverify` 는 UNMET 인데 `--status` 는 ALL MET 이라 Stop hook 이 보지 못했다.
#   → `--status` · `--discover` 가 '환경 드리프트' 로 미충족 처리하고 Stop hook 사유에 싣는다(원장 무변경).
# 셀 (--cells env):
#   env-absent-unrun   내부 CHECK 가 맨 앞에서 표식 파일을 만든다. 변수 있음 PASS → 표식 지움 → 변수 없이 --reverify →
#                      UNRUN · exit 1 · 표식 없음(실행 안 함) · 원장 바이트 무변경
#   env-empty-unrun    변수가 빈 값 → 같은 결과
#   env-present-pass   변수 있음 → --reverify PASS(대조)
#   env-from-plan      steps verify.env → 원장 `ENV:` 줄 · 잘못된 이름(`1X`)은 from_plan 이 거부
#   env-verifyspec     두 Workflow VerifySpec 스키마에 env(문자열 배열) — 생산자 배선
#   env-rollback       `ENV:` 줄을 지운 원장이 --status 에서 종전 그대로 met(승인 해시 · 증거 밖)
# 셀 (--cells status):
#   status-tools-drift   통과 게이트 · PATH 에서 선언 도구 제거 → --status UNMET · DRIFT 줄 · exit 1 · 원장 바이트 무변경
#   discover-tools-drift 같은 상태에서 --discover 요약 '미충족 1'
#   hook-drift-reason    같은 원장만 판정하는 Stop hook → 차단 · 사유에 '환경 드리프트' · 도구 이름
#   status-tools-present 도구 있음 → ALL MET(대조)
#   status-no-tools      TOOLS 없는 게이트는 PATH 와 무관하게 ALL MET(대조)
#   planned-no-drift     planned 원장은 --status no-op(exit 0 · DRIFT 없음 · 대조)
# 끝 — 판정한 셀 집합 = 고른 묶음의 기대 셀 집합(F-408)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패 — ⛔ 기준 판정기가 기능을 모르는 것(미지 속성 · 드리프트 없음)은 셀 실패(1)다
# usage: run.sh [--tree <플러그인 트리>] [--cells env,status]
set -u

DONE=0 fail=0 TMP=""
finish() {
  local rc=$?
  [ -n "$TMP" ] && rm -rf "${TMP:?}"
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ] && [ "$DONE" -ne 1 ]; then echo "SETUP 판정 줄 없이 끝났다(exit $rc)"; exit 3; fi
  exit "$rc"
}
trap finish EXIT
setup_fail() { echo "SETUP $*"; exit 3; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || setup_fail "fixture 경로 해석 실패"
TREE="$(cd "$HERE/../../../.." && pwd)" || setup_fail "기본 트리 해석 실패"
CELLS="env,status"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || setup_fail "--tree 에 경로가 없다"; TREE="$(cd "$2" 2>/dev/null && pwd)" || setup_fail "--tree 경로 없음: $2"; shift 2 ;;
    --cells) [ $# -ge 2 ] || setup_fail "--cells 에 값이 없다"; CELLS="$2"; shift 2 ;;
    *) setup_fail "알 수 없는 인자: $1" ;;
  esac
done
expect_of() {
  case "$1" in
    env) echo "env-absent-unrun env-empty-unrun env-present-pass env-from-plan env-verifyspec env-rollback" ;;
    status) echo "status-tools-drift discover-tools-drift hook-drift-reason status-tools-present status-no-tools planned-no-drift" ;;
    *) setup_fail "알 수 없는 셀 묶음: $1 (지원: env status)" ;;
  esac
}
want() { case ",$CELLS," in *",$1,"*) return 0 ;; esac; return 1; }
for g in $(printf '%s' "$CELLS" | tr ',' ' '); do expect_of "$g" >/dev/null; done
G="$TREE/scripts/gate_check.py" H="$TREE/scripts/gate_stop_hook.py"
[ -f "$G" ] && [ -f "$H" ] || setup_fail "gate_check.py · gate_stop_hook.py 없음: $TREE"
PY="$(command -v python3)" || setup_fail "python3 부재"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-env-drift.XXXXXX")" || setup_fail "임시 폴더 실패"
mkdir -p "$TMP/bin" "$TMP/home" || setup_fail "임시 하위 폴더 실패"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/fzprobetool" && chmod +x "$TMP/bin/fzprobetool" || setup_fail "가짜 도구 실패"
for v in FZ_GATES_LEDGER FZ_GATES_OFF FZ_GATES_TRACE FZ_GATES_HOOK_BUDGET_S FZPROBE_ENV; do unset "$v"; done
BARE="/usr/bin:/bin:$(dirname "$PY")"          # 가짜 도구가 없는 PATH
WITH="$TMP/bin:$BARE"

RAN=""
ran() { case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }
sha() { "$PY" -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1" 2>/dev/null; }

# $1=폴더 $2=steps JSON $3=마지막 상태(active|planned) — from_plan → finalize → planned(→ active). 실패는 RC 로 돌려준다(기준의 미지 속성 흡수)
mkled() {
  mkdir -p "$1" && printf '%s' "$2" > "$1/steps.json" || setup_fail "steps 쓰기 실패"
  PATH="$WITH" "$PY" "$G" --from-plan "$1/steps.json" --root "$1" --out "$1/gates/plan.md" > "$1/mk.out" 2>&1 || { MKRC=1; return; }
  PATH="$WITH" "$PY" "$G" --finalize "$1/gates/plan.md" >> "$1/mk.out" 2>&1 || { MKRC=1; return; }
  PATH="$WITH" "$PY" "$G" --set-state planned "$1/gates/plan.md" >> "$1/mk.out" 2>&1
  [ "${3:-active}" = active ] && { PATH="$WITH" "$PY" "$G" --set-state active "$1/gates/plan.md" >> "$1/mk.out" 2>&1 || { MKRC=1; return; }; }
  MKRC=0
}
# 판정기 1회 — $1=PATH $2=env 지정(FZPROBE_ENV=… 또는 -) 나머지=인자 → OUT · RC
gc() {
  local p="$1" e="$2"; shift 2
  if [ "$e" = "-" ]; then OUT=$(env -u FZPROBE_ENV PATH="$p" "$PY" "$G" "$@" 2>&1); RC=$?
  else OUT=$(env "$e" PATH="$p" "$PY" "$G" "$@" 2>&1); RC=$?; fi
}

if want env; then
  MARK="$TMP/mark"
  STEP_ENV=$(printf '{"title":"env","steps":[{"id":"G1","title":"환경 전제가 있는 CHECK","verify":{"kind":"command","criterion":"c","command":"touch %s && R=\\"${FZPROBE_ENV:?unset}\\" && echo E_OK","expect":"E_OK","env":["FZPROBE_ENV"]}}]}' "$MARK")
  for cell in env-absent-unrun env-empty-unrun; do
    d="$TMP/$cell"; mkled "$d" "$STEP_ENV"
    L="$d/gates/plan.md"
    if [ "$MKRC" -ne 0 ]; then no "$cell: 원장 준비" "from_plan · finalize 실패 — $(tail -1 "$d/mk.out" | cut -c1-120)"; continue; fi
    gc "$WITH" FZPROBE_ENV=x --only G1 "$L"
    if [ "$RC" -ne 0 ] || [ ! -e "$MARK" ]; then no "$cell: 준비 — 변수 있음 PASS · 표식" "rc=$RC · $(printf '%s' "$OUT" | tail -1 | cut -c1-100)"; continue; fi
    rm -f "$MARK"; before=$(sha "$L")
    if [ "$cell" = env-absent-unrun ]; then gc "$WITH" - --reverify "$L"; else gc "$WITH" FZPROBE_ENV= --reverify "$L"; fi
    if [ "$RC" -eq 1 ] && printf '%s' "$OUT" | grep -q 'UNRUN G1: 필요 환경 변수 부재' && [ ! -e "$MARK" ] && [ "$(sha "$L")" = "$before" ]; then
      ok "$cell: CHECK 를 돌리지 않았다(표식 없음) · UNRUN · exit 1 · 원장 바이트 무변경"
    else
      no "$cell: 미판정 · 무실행 · 무강등" "rc=$RC · 표식 $([ -e "$MARK" ] && echo 생김 || echo 없음) · 원장 $([ "$(sha "$L")" = "$before" ] && echo 무변경 || echo 바뀜) · $(printf '%s' "$OUT" | grep -m1 -E 'UNRUN|FAIL|PASS' | cut -c1-100)"
    fi
  done
  d="$TMP/present"; mkled "$d" "$STEP_ENV"; L="$d/gates/plan.md"
  gc "$WITH" FZPROBE_ENV=x --reverify "$L"
  [ "$MKRC" -eq 0 ] && [ "$RC" -eq 0 ] && printf '%s' "$OUT" | grep -q 'PASS  G1' && ok "env-present-pass: 변수 있음 → PASS" \
    || no "env-present-pass: PASS" "mk=$MKRC rc=$RC · $(printf '%s' "$OUT" | tail -1 | cut -c1-100)"
  d="$TMP/plan"; mkled "$d" "$STEP_ENV"; L="$d/gates/plan.md"
  mkdir -p "$TMP/bad" && printf '%s' '{"title":"b","steps":[{"id":"G1","title":"t","verify":{"kind":"command","criterion":"c","command":"echo X","expect":"X","env":["1X"]}}]}' > "$TMP/bad/s.json"
  "$PY" "$G" --from-plan "$TMP/bad/s.json" --root "$TMP/bad" --out "$TMP/bad/gates/plan.md" >/dev/null 2>&1; brc=$?
  if grep -q '^  ENV: FZPROBE_ENV$' "$L" 2>/dev/null && [ "$brc" -ne 0 ]; then ok "env-from-plan: verify.env → 'ENV: FZPROBE_ENV' 줄 · 잘못된 이름 1X 거부(exit $brc)"
  else no "env-from-plan: ENV 줄 · 이름 검사" "ENV 줄 $(grep -c '^  ENV:' "$L" 2>/dev/null) · 1X exit $brc"; fi
  miss=""; for wf in plan-lean2 plan-collaborative; do grep -q "env: { type: 'array', items: { type: 'string' }" "$TREE/workflows/$wf.js" || miss="$miss $wf"; done
  [ -z "$miss" ] && ok "env-verifyspec: 두 Workflow VerifySpec 에 env(문자열 배열)" || no "env-verifyspec: VerifySpec env" "없음:$miss"
  d="$TMP/rollback"; mkled "$d" "$STEP_ENV"; L="$d/gates/plan.md"
  gc "$WITH" FZPROBE_ENV=x --only G1 "$L"; r1=$RC
  "$PY" - "$L" <<'PYX'
import sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
open(p, "w", encoding="utf-8").write("".join(l for l in s.splitlines(True) if not l.startswith("  ENV: ")))
PYX
  gc "$WITH" - --status "$L"
  if [ "$r1" -eq 0 ] && [ "$RC" -eq 0 ] && printf '%s' "$OUT" | grep -q 'ALL MET' && ! grep -q '^  ENV:' "$L"; then ok "env-rollback: ENV 줄을 지워도 도장 · 증거 유효(--status ALL MET)"
  else no "env-rollback: ENV 삭제 뒤 met" "통과 rc=$r1 · status rc=$RC · $(printf '%s' "$OUT" | tail -2 | tr '\n' '|' | cut -c1-120)"; fi
fi

if want status; then
  STEP_T='{"title":"tools","steps":[{"id":"T1","title":"도구가 필요한 CHECK","verify":{"kind":"command","criterion":"c","command":"fzprobetool && echo T_OK","expect":"T_OK","tools":["fzprobetool"]}}]}'
  STEP_N='{"title":"plain","steps":[{"id":"N1","title":"도구 선언 없는 CHECK","verify":{"kind":"command","criterion":"c","command":"echo N_OK","expect":"N_OK"}}]}'
  d="$TMP/drift"; mkled "$d" "$STEP_T"; L="$d/gates/plan.md"
  gc "$WITH" - --only T1 "$L"; [ "$RC" -eq 0 ] || setup_fail "드리프트 원장 준비 — 도구 있음 통과 실패 rc=$RC"
  before=$(sha "$L")
  gc "$BARE" - --status "$L"
  if [ "$RC" -eq 1 ] && printf '%s' "$OUT" | grep -q 'DRIFT T1: 도구 부재 — fzprobetool' && [ "$(sha "$L")" = "$before" ]; then ok "status-tools-drift: 도구 없음 → UNMET · DRIFT 줄 · exit 1 · 원장 무변경"
  else no "status-tools-drift: 드리프트 미충족" "rc=$RC · $(printf '%s' "$OUT" | tail -2 | tr '\n' '|' | cut -c1-120)"; fi
  gc "$BARE" - --discover "$d"
  printf '%s' "$OUT" | grep -q '미충족 1' && ok "discover-tools-drift: --discover 요약 '미충족 1'" \
    || no "discover-tools-drift: discover 미충족" "$(printf '%s' "$OUT" | tail -1 | cut -c1-120)"
  : > "$TMP/t.jsonl"
  HOUT=$(printf '{"hook_event_name":"Stop","cwd":"%s","session_id":"env-drift","transcript_path":"%s"}' "$d" "$TMP/t.jsonl" \
         | env -u FZPROBE_ENV HOME="$TMP/home" FZ_GATES_LEDGER="$L" PATH="$BARE" "$PY" -B "$H" 2>&1); HRC=$?
  if [ "$HRC" -eq 2 ] && printf '%s' "$HOUT" | grep -q '환경 드리프트' && printf '%s' "$HOUT" | grep -q 'fzprobetool'; then ok "hook-drift-reason: Stop hook 차단 · 사유에 '환경 드리프트' · fzprobetool"
  else no "hook-drift-reason: 훅 사유" "exit $HRC · $(printf '%s' "$HOUT" | grep -m1 decision | cut -c1-140)"; fi
  gc "$WITH" - --status "$L"
  [ "$RC" -eq 0 ] && printf '%s' "$OUT" | grep -q 'ALL MET' && ok "status-tools-present: 도구 있음 → ALL MET" || no "status-tools-present: ALL MET" "rc=$RC"
  d="$TMP/plain"; mkled "$d" "$STEP_N"; L="$d/gates/plan.md"; gc "$WITH" - --only N1 "$L"
  gc "$BARE" - --status "$L"
  [ "$RC" -eq 0 ] && printf '%s' "$OUT" | grep -q 'ALL MET' && ok "status-no-tools: TOOLS 없는 게이트 → ALL MET" || no "status-no-tools: ALL MET" "rc=$RC"
  d="$TMP/planned"; mkled "$d" "$STEP_T" planned; L="$d/gates/plan.md"
  gc "$BARE" - --status "$L"
  [ "$RC" -eq 0 ] && ! printf '%s' "$OUT" | grep -q 'DRIFT' && ok "planned-no-drift: planned 원장 --status no-op · DRIFT 없음" \
    || no "planned-no-drift: planned no-op" "rc=$RC · $(printf '%s' "$OUT" | tail -1 | cut -c1-100)"
fi

want_set=$(for gr in $(printf '%s' "$CELLS" | tr ',' ' '); do expect_of "$gr"; done | tr ' ' '\n' | grep . | LC_ALL=C sort -u)
got_set=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want_set" = "$got_set" ]; then echo "PASS  셀 집합: 판정한 셀 = 고른 묶음의 기대 셀 ($(printf '%s\n' "$want_set" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want_set") <(printf '%s\n' "$got_set") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "ENV_DRIFT_OK cells=$CELLS ran=$(printf '%s\n' $RAN | grep -c .)"
