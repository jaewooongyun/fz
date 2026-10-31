#!/bin/bash
# lint:no-root-anchor — 검사 대상 저장소를 --repo 인자로 받는다(플러그인 루트의 파일을 읽지 않는다).
# scope_census.sh — 같은 패턴을 좁힌 범위와 저장소 전체에서 함께 세어 범위 밖 적중을 한 번에 인쇄한다 (F-030 · F-452).
#
# 왜: "언급 0건" · "N건" 같은 부재 · 개수 주장이 고른 범위(문서 폴더 등)에서만 잰 값이었다 — F-452 는 문서 경로만 세어
#   '언급 없음 253건' 을 냈고 전체로 세자 202건 · 코드 인용 70건이었다. 범위를 좁히는 것 자체가 아니라 **좁혔다는 사실이
#   숫자 옆에 없는 것**이 실패였다. 이 스크립트는 두 숫자와 차이를 같은 출력에 둔다.
#
# usage: scope_census.sh (--fixed|--regex) <패턴> --scope <경로> [--scope <경로>…] [--expect <경로>] [--repo <저장소>]
#   · 저장소 전체 = 작업 트리 루트에서 `git grep --untracked` — 추적 + 미추적 파일, `.gitignore` 는 존중한다(무시 폴더는 세지 않는다).
#     --repo 가 하위 폴더면 --scope 는 그 폴더 기준이고, 인쇄 경로는 루트 기준이다
#   · 줄 수 = 패턴이 나온 줄의 수(한 줄에 여러 번 나와도 1줄) · 파일 수 = 적중 파일 수
#   · scope 경로가 겹치면 한 번만 센다(`git grep` pathspec 합집합) — 인쇄도 정렬 · 중복 제거한 목록
#   · --expect <경로>: 그 경로에 적중이 0이면 exit 2 — 양성 대조(패턴 · 범위가 살아 있는지)
# exit: 0 인쇄 · 2 --expect 미적중 · 3 사용법 · 저장소 아님 · git 실패(⛔ 0건으로 읽지 않는다)
set -u

die() { echo "SCOPE-CENSUS-FAIL($1): $2" >&2; exit "$1"; }

MODE="" PAT="" REPO="." EXPECT="" SCOPES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --fixed|--regex) [ $# -ge 2 ] || die 3 "$1 에 패턴이 없다"; [ -z "$MODE" ] || die 3 "--fixed · --regex 는 하나만"; MODE="$1"; PAT="$2"; shift 2 ;;
    --scope)  [ $# -ge 2 ] || die 3 "--scope 에 경로가 없다"; SCOPES+=("${2%/}"); shift 2 ;;
    --expect) [ $# -ge 2 ] || die 3 "--expect 에 경로가 없다"; EXPECT="${2%/}"; shift 2 ;;
    --repo)   [ $# -ge 2 ] || die 3 "--repo 에 경로가 없다"; REPO="$2"; shift 2 ;;
    *) die 3 "알 수 없는 인자: $1" ;;
  esac
done
[ -n "$MODE" ] || die 3 "--fixed 또는 --regex 필수"
[ -n "$PAT" ] || die 3 "빈 패턴"
[ "${#SCOPES[@]}" -gt 0 ] || die 3 "--scope 를 하나 이상 준다(전체만 세려면 --scope .)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die 3 "git 작업 트리가 아니다: $REPO"
[ "$MODE" = "--fixed" ] && GF=-F || GF=-E

# $@ = pathspec — 적중 파일별 줄 수(`작업 트리 루트 기준 경로:줄수`). git grep 은 적중 0이면 exit 1 이다(실패 아님)
# ⛔ 명령 치환 안의 die 는 그 서브셸만 끝낸다 — 호출부가 `|| exit $?` 로 실패를 올린다(잘못된 정규식이 '0 파일' 로 인쇄되던 결함)
count() {
  local out rc
  out=$(git -C "$REPO" grep --full-name --untracked -I -c "$GF" -e "$PAT" -- "$@" 2>&1); rc=$?
  [ "$rc" -le 1 ] || die 3 "git grep 실패(exit $rc): $(printf '%s' "$out" | head -1)"
  [ "$rc" -eq 0 ] && printf '%s\n' "$out"
  return 0
}
summ() { awk -F: 'NF{f++; l+=$NF} END{printf "%d 파일 · %d 줄", f, l}'; }

SC=$(printf '%s\n' "${SCOPES[@]}" | LC_ALL=C sort -u)
IN=$(count $(printf '%s\n' "$SC")) || exit $?   # ponytail: 공백 든 scope 경로는 지원하지 않는다 — 필요하면 배열로 넘긴다
# 저장소 전체 = 작업 트리 루트(`:/`) — --repo 가 하위 폴더여도 그 밖 적중이 빠지지 않는다. scope 는 --repo 기준 상대 경로다
ALL=$(count ':/') || exit $?
OUT=$(comm -23 <(printf '%s\n' "$ALL" | sed 's/:[0-9]*$//' | grep . | LC_ALL=C sort -u) \
                <(printf '%s\n' "$IN" | sed 's/:[0-9]*$//' | grep . | LC_ALL=C sort -u))

echo "패턴: ${MODE#--} '$PAT'"
echo "범위: $(printf '%s ' $SC)"
echo "좁힌 범위   : $(printf '%s\n' "$IN" | summ)"
echo "저장소 전체 : $(printf '%s\n' "$ALL" | summ)  (git grep --untracked · .gitignore 존중)"
if [ -n "$OUT" ]; then
  echo "범위 밖 적중: $(printf '%s\n' "$OUT" | grep -c .) 파일"
  printf '%s\n' "$OUT" | sed 's/^/  - /'
else
  echo "범위 밖 적중: 0 파일"
fi
if [ -n "$EXPECT" ]; then
  EX=$(count "$EXPECT") || exit $?
  if [ -z "$EX" ]; then
    echo "⛔ --expect '$EXPECT' 적중 0 — 패턴이나 범위가 죽었다(0건 결론에 쓰지 않는다)"
    exit 2
  fi
  echo "양성 대조: '$EXPECT' 적중 있음"
fi
