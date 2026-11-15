#!/bin/bash
# fz-plan Gate 1 산문 주장 배선 러너(F-185) — SKILL.md Gate 1 의 Evidence 호출 줄(백틱 안 명령)을 그대로 뽑아 fixture 에 돌린다.
#   근거 없는 수치가 든 문서(../doc/claims.md)에는 WARN 이 나오고, 근거를 단 문서에는 나오지 않아야 한다 — 둘 다 exit 0(WARN 은 차단이 아니다).
# ⛔ 호출 줄을 지우거나 플래그 · 경로 자리표시를 바꾸면 여기서 걸린다. `grep plan_integrity_check SKILL.md` 는 다른 언급(Phase 1 의
#    workflow-result.json 문단)으로 수정 전에도 참이라 배선을 재지 못했다.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공한다(bash 3.2)
T0="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }; T="$(cd "$T0" && pwd -P)"; trap 'rm -rf "$T"' EXIT
CELL=r3-f185-gate1-invocation-warns

run() {   # $1 = plan 문서 → Gate 1 Evidence 명령을 {WORK_DIR}=임시 폴더 · {N}=1 로 채워 실행한 출력(명령 줄이 없으면 exit 3)
  mkdir -p "$T/wd/plan" && cp "$1" "$T/wd/plan/plan-v1.md" || return 2
  local cmd
  cmd="$(python3 - "$R/skills/fz-plan/SKILL.md" "$T/wd" <<'PY'
import re, sys
for ln in open(sys.argv[1], encoding="utf-8"):
    m = re.search(r"Evidence: `([^`]*plan_integrity_check\.py[^`]*)`", ln)
    if m and "{WORK_DIR}/plan/plan-v{N}.md" in m.group(1):
        print(m.group(1).replace("{WORK_DIR}", sys.argv[2]).replace("{N}", "1"))
        break
PY
)"
  [ -n "$cmd" ] || return 3
  FZ_PLUGIN_ROOT="$R" bash -c "$cmd" 2>&1
}

pos="$(run "$HERE/../doc/claims.md")"; pc=$?
printf '%s\n' "## 근거를 단 문서" "호출처는 4곳이다 [verified: git grep -c foo → 4]" > "$T/verified.md"
neg="$(run "$T/verified.md")"; nc=$?
if [ "$pc" -eq 3 ]; then
  echo "FAIL  $CELL — skills/fz-plan/SKILL.md 에 Gate 1 Evidence 호출 줄(plan_integrity_check.py --plan-doc {WORK_DIR}/plan/plan-v{N}.md)이 없다"
  exit 1
fi
if [ "$pc" -eq 0 ] && [ "$nc" -eq 0 ] && printf '%s\n' "$pos" | grep -q "WARN 미검증 주장" && ! printf '%s\n' "$neg" | grep -q "WARN 미검증 주장"; then
  echo "PASS  $CELL"
  exit 0
fi
echo "FAIL  $CELL — 근거 없는 문서 exit $pc · 근거 단 문서 exit $nc"
printf '%s\n' "$pos" "$neg" | head -8
exit 1
