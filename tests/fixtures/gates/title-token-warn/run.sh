#!/bin/bash
# diff-parse: not-a-diff — 원장 줄(`- [ ] ID:`)을 세고 판정기 출력을 grep 한다. diff 를 파싱하지 않는다
# gate_check --from-plan 제목 토큰 경고 회귀 판정 (F-245 · F-294) — 제목의 백틱 토큰이 command 에 없으면 경고한다.
#
# F-294: plan 개정이 Step 제목에만 새 요구(`base.sha` 기록 등)를 붙이고 verify 명령은 그대로 둬, 승인된 게이트가 그 요구를 재지
#   않았다(F-245 재발). 제목 · criterion 은 사람이 읽고, 기계는 command 만 돈다 — 그 차이를 원장 생성 때 드러낸다.
# 셀:
#   token-criterion-only  제목 `bar_check` 가 criterion 에만 있다 → 그 Step id 와 토큰을 담은 경고 줄
#   token-in-command      제목 `foo.sh` 가 command 에 있다 → 그 Step 의 경고 없음
#   manual-skipped        manual Step 의 제목 토큰은 보지 않는다 → 경고 없음
#   ledger-created        경고가 있어도 원장은 만든다(exit 0 · 게이트 3개) — 경고는 차단이 아니다
# 끝 — 판정한 셀 집합 = 기대 셀 집합(F-408)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
# usage: run.sh [--tree <플러그인 트리>]
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
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || setup_fail "--tree 에 경로가 없다"; TREE="$(cd "$2" 2>/dev/null && pwd)" || setup_fail "--tree 경로 없음: $2"; shift 2 ;;
    *) setup_fail "알 수 없는 인자: $1" ;;
  esac
done
EXPECT_CELLS="token-criterion-only token-in-command manual-skipped ledger-created"
G="$TREE/scripts/gate_check.py"
[ -f "$G" ] || setup_fail "gate_check.py 없음: $G"
command -v python3 >/dev/null 2>&1 || setup_fail "python3 부재"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-title-token.XXXXXX")" || setup_fail "임시 폴더 실패"
mkdir -p "$TMP/work" || setup_fail "작업 폴더 실패"
python3 - "$TMP/steps.json" <<'PY' || setup_fail "steps.json 준비 실패"
import json, sys
json.dump({"title": "fixture", "scope": "title-token", "steps": [
    {"id": "S1", "title": "`foo.sh` 가 결과를 낸다", "files": ["foo.sh"],
     "verify": {"kind": "command", "criterion": "foo.sh exit 0", "command": "bash foo.sh && echo S1_OK", "expect": "S1_OK"}},
    {"id": "S2", "title": "`bar_check` 로 base.sha 를 기록한다", "files": ["x"],
     "verify": {"kind": "command", "criterion": "bar_check 가 base.sha 를 쓴다", "command": "git diff --stat && echo S2_OK", "expect": "S2_OK"}},
    {"id": "S3", "title": "`manual_tok` 을 사람이 본다", "files": ["y"],
     "verify": {"kind": "manual", "criterion": "사람이 manual_tok 을 확인한다"}}]},
    open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False)
PY

RAN=""
ran() { case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }

out=$(python3 "$G" --from-plan "$TMP/steps.json" --root "$TMP/work" --out "$TMP/work/gates/plan.draft.md" 2>&1); rc=$?
w2=$(printf '%s\n' "$out" | grep -E 'S2: .*`bar_check`.*command 에 없다' | head -1)
[ -n "$w2" ] && ok "token-criterion-only: S2 제목 \`bar_check\` 가 command 에 없다는 경고" \
  || no "token-criterion-only: S2 경고" "경고 줄 없음 · 출력: $(printf '%s' "$out" | tr '\n' '|' | cut -c1-160)"
printf '%s\n' "$out" | grep -qE '(^|[^A-Za-z0-9])S1: .*command 에 없다' \
  && no "token-in-command: S1 경고 없음" "S1 이 command 에 있는 토큰으로 경고됐다" || ok "token-in-command: command 에 있는 \`foo.sh\` 는 경고하지 않는다"
printf '%s\n' "$out" | grep -qE 'S3: .*command 에 없다' \
  && no "manual-skipped: S3 경고 없음" "manual Step 을 경고했다" || ok "manual-skipped: manual Step 은 보지 않는다"
n=$(grep -c '^- \[ \] ' "$TMP/work/gates/plan.draft.md" 2>/dev/null || echo 0)
[ "$rc" -eq 0 ] && [ "$n" -eq 3 ] && ok "ledger-created: 경고가 있어도 exit 0 · 게이트 3개" || no "ledger-created: exit 0 · 게이트 3개" "exit $rc · 게이트 $n"

want=$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u); got=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want" = "$got" ]; then echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "TITLE_TOKEN_WARN_OK ran=$(printf '%s\n' $RAN | grep -c .)"
