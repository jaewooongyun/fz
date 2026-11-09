#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 파싱하지 않는다. 임시 git 저장소에 staged 변경을 만들고 트리의 훅을 돌려 exit 만 본다
# pre-commit 개인 경로 훅의 검사 범위 — 예외 나열(EXEMPT_RE) 방식 (F-056).
#
# 옛 훅은 화이트리스트(SCOPED_RE)라 tests/ · scripts/ · workflows/ 에 넣은 사용자 경로를 조용히 통과시켰다.
# ⛔ 훅을 **실제로 돌린다** — 임시 저장소를 cwd 로 트리의 `.githooks/pre-commit` 을 실행한다. 바깥 git 설정(전역 · 시스템)을 끊는다.
#   셀 (막혀야 할 경로 = 가짜 사용자 fixture-user 의 홈 경로 `$U` — 훅의 자리표시자 마스크에 없는 이름):
#     f056-precommit-exempt-scope     tests/ 아래 파일의 사용자 경로 → 차단(exit 1) — 옛 훅은 통과(범위 밖)
#     f056-scripts-dir-scoped         scripts/ 아래 파일의 사용자 경로 → 차단 — 옛 훅은 통과
#     f056-new-dir-scoped             처음 보는 폴더(newdir/) → 차단 — 예외 나열이면 새 폴더가 기본 검사 대상이다
#     f056-exempt-changelog-ok        CHANGELOG.md → 통과 — historical reference 예외
#     f056-exempt-releases-ok         docs/releases/ → 통과 — 같은 예외
#     f056-placeholder-ok             tests/ 의 자리표시자(/Users/example/ · ~/dev/gone/) → 통과 — 픽스처 관례는 오탐이 아니다
#     f056-placeholder-mixed-blocks   한 줄에 자리표시자와 사용자 경로가 함께 → 차단 — 마스크가 줄 전체를 풀어 주지 않는다
#     f056-hook-self-clean            트리의 훅 파일 자체를 새 파일로 stage → 통과 — 훅이 이제 자기 자신도 검사 범위다
#     f056-real-tree-measured         트리의 추적 파일 중 예외가 아닌 것에서 차단 패턴 매치를 세고, 자리표시자 마스크 뒤 남는 줄을 낸다(오탐 수 기록)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(도구 · 임시 저장소)
# usage: run.sh [--tree <플러그인 트리>]
set -u
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
for c in git sed grep; do command -v "$c" >/dev/null 2>&1 || { echo "SETUP $c 부재"; exit 3; }; done
HOOK="$TREE/.githooks/pre-commit"
[ -f "$HOOK" ] || { echo "SETUP 훅 없음: $HOOK"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-precommit-scope.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home" && : > "$TMP/gitconfig" || exit 3
export HOME="$TMP/home" GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CEILING_DIRECTORIES
U="/Users/fixture-user"

fail=0; n=0
ok() { n=$((n + 1)); echo "PASS  $1  ($2)"; }
no() { n=$((n + 1)); fail=$((fail + 1)); echo "FAIL  $1  — $2"; }

# $1=셀 — 빈 기준선 커밋 하나(훅 경유 아님)
newrepo() {
  R="$TMP/$1"
  git init -q "$R" && git -C "$R" config user.email f@f.f && git -C "$R" config user.name f \
    && git -C "$R" config commit.gpgsign false && printf 'base\n' > "$R/README.md" \
    && git -C "$R" add -A && git -C "$R" commit -qm base \
    || { echo "SETUP 임시 저장소 $1 실패"; exit 3; }
}
# $1=셀 $2=상대경로 $3=추가할 줄 $4=기대 exit
cell() {
  newrepo "$1"
  mkdir -p "$(dirname "$R/$2")" && printf '%s\n' "$3" > "$R/$2" && git -C "$R" add -A || { echo "SETUP stage 실패 $1"; exit 3; }
  (cd "$R" && bash "$HOOK") > "$R.out" 2>&1
  local rc=$?
  if [ "$rc" -eq "$4" ]; then ok "$1" "exit $rc"; else no "$1" "exit $rc (기대 $4) · $(grep -m1 -E 'pre-commit' "$R.out" | cut -c1-120)"; fi
}

cell f056-precommit-exempt-scope   tests/fixtures/x/run.sh     "cd $U/dev/x"                    1
cell f056-scripts-dir-scoped       scripts/tool.py             "ROOT = '$U/dev/x'"              1
cell f056-new-dir-scoped           newdir/note.md              "see $U/dev/x"                   1
cell f056-exempt-changelog-ok      CHANGELOG.md                "- moved from $U/dev/x"          0
cell f056-exempt-releases-ok       docs/releases/v9.9.9.md     "- moved from $U/dev/x"          0
cell f056-placeholder-ok           tests/fixtures/y/run.sh     "W=/Users/example/w · ~/dev/gone/x" 0
cell f056-placeholder-mixed-blocks tests/fixtures/z/run.sh     "A=/Users/example/a B=$U/b"      1

newrepo f056-hook-self-clean
mkdir -p "$R/.githooks" && cp "$HOOK" "$R/.githooks/pre-commit" && git -C "$R" add -A || { echo "SETUP 훅 사본 stage 실패"; exit 3; }
(cd "$R" && bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -eq 0 ]; then ok f056-hook-self-clean "exit 0"; else no f056-hook-self-clean "exit $rc — 훅 본문이 자기 자신에게 막힌다 · $(grep -m1 -A1 'pre-commit:' "$R.out" | tail -n 1 | cut -c1-120)"; fi

# 오탐 수 기록 — 훅이 정한 정규식을 훅에서 읽는다(사본을 여기 두지 않는다)
rx() { sed -n "s/^$1='\\(.*\\)'\$/\\1/p" "$HOOK" | head -n 1; }
EX="$(rx EXEMPT_RE)" PH="$(rx PLACEHOLDER_RE)" UP="$(rx USER_PATH_RE)"
if [ -z "$EX" ] || [ -z "$PH" ] || [ -z "$UP" ]; then
  no f056-real-tree-measured "훅에서 EXEMPT_RE · PLACEHOLDER_RE · USER_PATH_RE 를 읽지 못했다"
elif ! git -C "$TREE" rev-parse --git-dir >/dev/null 2>&1; then
  no f056-real-tree-measured "트리가 git 저장소가 아니다 — 측정 불가"
else
  LIST="$TMP/scope.txt"
  git -C "$TREE" -c core.quotePath=false ls-files | grep -Ev "$EX" > "$LIST"
  files=$(wc -l < "$LIST" | tr -d ' ')
  raw=$(cd "$TREE" && tr '\n' '\0' < "$LIST" | xargs -0 grep -IhE "$UP" 2>/dev/null | wc -l | tr -d ' ')
  left=$(cd "$TREE" && tr '\n' '\0' < "$LIST" | xargs -0 grep -IhE "$UP" 2>/dev/null | sed -E "s#${PH}#<placeholder>/#g" | grep -cE "$UP")
  ok f056-real-tree-measured "검사 범위 ${files}파일 · 차단 패턴 매치 ${raw}줄 · 자리표시자 마스크 뒤 ${left}줄(기존 줄 — 훅은 추가 줄만 본다)"
fi

echo ""
echo "$fail 건 실패"
[ "$fail" -eq 0 ] && echo "PRECOMMIT_SCOPE_OK ${n}셀"
[ "$fail" -eq 0 ]
