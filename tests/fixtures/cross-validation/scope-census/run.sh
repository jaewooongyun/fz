#!/bin/bash
# scope_census.sh 회귀 판정 (F-030 · F-452) — 좁힌 범위의 수와 저장소 전체의 수를 한 출력에 둔다.
#
# F-452: 플러그인 참조를 문서 경로로만 세어 '언급 없음 253건' 을 냈다(전체 202 · 코드 인용 70). F-030 이 같은 축의 앞 사례다.
# 배치: 합성 git 저장소 — docs/ 에 2파일(a.md 는 적중 2줄 · 그중 한 줄에 패턴 두 번) · scripts/ 에 1파일(범위 밖) ·
#       미추적 scripts/new.py(무시 안 됨) · 무시된 build/ 에 1파일(세지 않는다)
# 셀:
#   out-of-scope      --scope docs → 좁힌 범위 2 파일 · 3 줄 · 저장소 전체 4 파일 · 5 줄 · 범위 밖 적중에 scripts/tool.py · scripts/new.py
#   overlap-scope     --scope docs --scope docs/sub(겹침) → 좁힌 범위 파일 수가 docs 단독과 같다 · 범위 줄에 docs 한 번
#   multi-occurrence  docs/a.md 의 세 출현(한 줄에 두 번 + 다른 줄 한 번) = 2줄 — 파일 수 · 출현 수와 줄 수가 모두 다르다
#   untracked         미추적 파일은 센다 · .gitignore 무시 파일은 세지 않는다
#   expect-miss       --expect <적중 없는 경로> → exit 2 · 적중 있는 경로 → exit 0
#   census-failure    잘못된 정규식('[') → exit 3 · '0 파일' 줄 없음 — 측정 실패를 0건으로 인쇄하지 않는다(GPT check P1)
#   subdir-repo-wide  --repo 가 하위 폴더(docs)여도 '저장소 전체' 는 루트 기준 4 파일 · 5 줄 · 범위 밖에 scripts/tool.py
# 끝 — 판정한 셀 집합 = 기대 셀 집합(F-408)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패 — ⛔ scope_census.sh 부재는 셀 실패(기준 트리 되돌림이 1 로 끝난다)
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
EXPECT_CELLS="out-of-scope overlap-scope multi-occurrence untracked expect-miss census-failure subdir-repo-wide"
command -v git >/dev/null 2>&1 || setup_fail "git 부재"
SC="$TREE/scripts/scope_census.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-scope-census.XXXXXX")" || setup_fail "임시 폴더 실패"
export GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1
: > "$GIT_CONFIG_GLOBAL"
Rp="$TMP/repo"
{ git init -q "$Rp" && mkdir -p "$Rp/docs/sub" "$Rp/scripts" "$Rp/build" \
  && printf 'fz-plugin 참조 · fz-plugin 다시\n그 밖\nfz-plugin 셋째 줄\n' > "$Rp/docs/a.md" \
  && printf 'fz-plugin 한 번\n' > "$Rp/docs/sub/b.md" \
  && printf 'ROOT = "fz-plugin"\n' > "$Rp/scripts/tool.py" \
  && printf 'build/\n' > "$Rp/.gitignore" \
  && git -C "$Rp" add -A \
  && printf 'NEW = "fz-plugin"\n' > "$Rp/scripts/new.py" \
  && printf 'fz-plugin 무시\n' > "$Rp/build/out.txt"; } || setup_fail "합성 저장소 준비 실패"
[ "$(git -C "$Rp" status --porcelain --untracked-files=all | grep -c '^??')" -eq 1 ] || setup_fail "미추적 1 · 무시 1 배치 전제 불성립"

RAN=""
ran() { case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }
census() { if [ -f "$SC" ]; then bash "$SC" --repo "$Rp" "$@" 2>&1; else echo "(scope_census.sh 없음)"; return 127; fi; }

o=$(census --fixed fz-plugin --scope docs); rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$o" | grep -q '^좁힌 범위   : 2 파일 · 3 줄' && printf '%s\n' "$o" | grep -q '^저장소 전체 : 4 파일 · 5 줄' \
   && printf '%s\n' "$o" | grep -q '^  - scripts/tool.py$' && printf '%s\n' "$o" | grep -q '^  - scripts/new.py$'; then
  ok "out-of-scope: 좁힌 범위 2 파일 · 3 줄 · 전체 4 파일 · 5 줄 · 범위 밖 scripts/tool.py · scripts/new.py"
else no "out-of-scope: 좁힌 범위 · 전체 · 범위 밖 경로" "rc=$rc · $(printf '%s' "$o" | tr '\n' '|' | cut -c1-200)"; fi

o2=$(census --fixed fz-plugin --scope docs --scope docs/sub --scope docs/); rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$o2" | grep -q '^좁힌 범위   : 2 파일 · 3 줄' && printf '%s\n' "$o2" | grep -qx '범위: docs docs/sub '; then
  ok "overlap-scope: 겹친 scope(docs · docs/sub · docs/) → 2 파일 · 3 줄 · 범위 목록 중복 제거"
else no "overlap-scope: 겹친 scope 중복 제거" "rc=$rc · $(printf '%s' "$o2" | tr '\n' '|' | cut -c1-200)"; fi

o3=$(census --fixed fz-plugin --scope docs/a.md); rc=$?
printf '%s\n' "$o3" | grep -q '^좁힌 범위   : 1 파일 · 2 줄' && [ "$rc" -eq 0 ] \
  && ok "multi-occurrence: 세 번 출현 · 두 줄(한 줄에 두 번) → 1 파일 · 2 줄" || no "multi-occurrence: 한 줄 다중 출현 = 1 줄" "rc=$rc · $(printf '%s' "$o3" | grep '^좁힌')"

o4=$(census --fixed fz-plugin --scope scripts); rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$o4" | grep -q '^좁힌 범위   : 2 파일 · 2 줄' && ! printf '%s\n' "$o4" | grep -q 'build/out.txt'; then
  ok "untracked: 미추적 scripts/new.py 를 센다 · 무시된 build/out.txt 는 세지 않는다"
else no "untracked: 미추적 포함 · 무시 제외" "rc=$rc · $(printf '%s' "$o4" | tr '\n' '|' | cut -c1-200)"; fi

census --fixed fz-plugin --scope docs --expect build >/dev/null; r1=$?
census --fixed fz-plugin --scope docs --expect scripts >/dev/null; r2=$?
[ "$r1" -eq 2 ] && [ "$r2" -eq 0 ] && ok "expect-miss: 적중 없는 --expect → exit 2 · 적중 있는 --expect → exit 0" \
  || no "expect-miss: exit 2 · 0" "미적중 exit $r1 · 적중 exit $r2"

o5=$(census --regex '[' --scope docs); rc=$?
if [ "$rc" -eq 3 ] && ! printf '%s\n' "$o5" | grep -q '0 파일'; then ok "census-failure: 잘못된 정규식 → exit 3 · '0 파일' 줄 없음"
else no "census-failure: exit 3 · 0건 인쇄 없음" "rc=$rc · $(printf '%s' "$o5" | grep -m1 '파일')"; fi

o6=$(if [ -f "$SC" ]; then bash "$SC" --repo "$Rp/docs" --fixed fz-plugin --scope . 2>&1; else echo "(scope_census.sh 없음)"; exit 127; fi); rc=$?
if [ "$rc" -eq 0 ] && printf '%s\n' "$o6" | grep -q '^좁힌 범위   : 2 파일 · 3 줄' && printf '%s\n' "$o6" | grep -q '^저장소 전체 : 4 파일 · 5 줄' \
   && printf '%s\n' "$o6" | grep -q '^  - scripts/tool.py$'; then ok "subdir-repo-wide: --repo docs 에서도 저장소 전체 4 파일 · 5 줄 · 범위 밖 scripts/tool.py"
else no "subdir-repo-wide: 저장소 전체는 루트 기준" "rc=$rc · $(printf '%s' "$o6" | tr '\n' '|' | cut -c1-200)"; fi

want=$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u); got=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want" = "$got" ]; then echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "SCOPE_CENSUS_OK ran=$(printf '%s\n' $RAN | grep -c .)"
