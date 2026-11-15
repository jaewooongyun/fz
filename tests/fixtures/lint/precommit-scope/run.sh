#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 파싱하지 않는다. 임시 git 저장소에 staged 변경을 만들고 트리의 훅을 돌려 exit 만 본다
# pre-commit 누수 훅의 검사 범위 — 예외 없음: 모든 파일의 추가 줄을 본다 (F-056).
#
# 옛 훅은 화이트리스트(SCOPED_RE)라 tests/ · scripts/ · workflows/ 에 넣은 사용자 경로를 조용히 통과시켰다. 그다음 판은 CHANGELOG.md ·
# docs/releases/ 를 검사에서 뺐다 — 공개 저장소에 실리는 파일인데 그 두 곳으로는 식별자가 검사 없이 나간다.
# ⛔ 훅을 **실제로 돌린다** — 임시 저장소를 cwd 로 트리의 `.githooks/pre-commit` 을 실행한다. 바깥 git 설정(전역 · 시스템)과 비공개 규칙
#   env(FZ_NEUTRALIZE_RULES)를 끊는다. 훅은 판정을 훅 위치 기준의 정본(scripts/leak_rules.py)에 넘긴다.
#   셀 (막혀야 할 경로 = 가짜 사용자 fixture-user 의 홈 경로 `$U` — 정본의 자리표시 이름에 없다 · 실행할 때 이어 붙인다):
#     f056-precommit-exempt-scope     tests/ 아래 파일의 사용자 경로 → 차단(exit 1) — 옛 훅은 통과(범위 밖)
#     f056-scripts-dir-scoped         scripts/ 아래 파일의 사용자 경로 → 차단 — 옛 훅은 통과
#     f056-new-dir-scoped             처음 보는 폴더(newdir/) → 차단 — 새 폴더도 기본 검사 대상이다
#     s-changelog-scoped              CHANGELOG.md → 차단 — 예외가 없다
#     s-releases-scoped               docs/releases/ → 차단 — 같은 이유
#     f056-placeholder-ok             tests/ 의 자리표시자(/Users/example/ · ~/dev/gone/) → 통과 — 픽스처 관례는 오탐이 아니다
#     f056-placeholder-mixed-blocks   한 줄에 자리표시자와 사용자 경로가 함께 → 차단 — 자리표시자가 줄 전체를 풀어 주지 않는다
#     f056-hook-self-clean            트리의 훅 파일 자체를 새 파일로 stage → 통과 — 훅이 자기 자신에게 막히지 않는다
#     sync-checker-missing-declared   버전 선언(.claude-plugin/plugin.json)이 있는데 버전 동기 검사기가 없는 저장소 → 차단 — 배선이 끊겼다
#     sync-checker-missing-declared-index-only  선언이 인덱스에만 있다(stage 한 뒤 작업 트리에서 지웠다) → 차단 — 커밋에는 선언이 들어간다
#     sync-checker-missing-undeclared 버전 선언이 없는 저장소 → 통과 — 맞출 버전이 없다
#     sync-checker-missing-lsfiles-fail  선언이 인덱스에 있는지 git 이 답하지 못한다(git 심이 그 호출만 실패시킨다) → 차단 — 모르는 것을 '선언 없음' 으로 읽지 않는다
#     f056-real-tree-measured         정본(scripts/leak_rules.py -C <트리> --tree)으로 트리 전문의 파일 수 · 적중 수를 기록한다 — 측정
#                                     기록이라 적중이 있어도 통과다(훅은 추가 줄만 본다). 격리 전에 사용자 git 설정(무시 파일)으로 잰다 —
#                                     평소 --tree 와 같은 목록. 정본이 판정 불가(2)를 내거나 끝 줄이 종료 코드와 어긋나면 실패.
#                                     git 저장소가 아닌 트리(내려받은 사본)는 정본이 폴더를 걸어 잰다
#     f056-nongit-tree-measured       git 저장소가 아닌 트리(훅 + 정본만 둔 사본)를 --tree 로 준 자식 실행도 f056-real-tree-measured 가 통과한다
#     host-xdg-attributes-ignored     같은 자식 실행에 호스트의 XDG git 속성 파일(`* binary`)과 부모 git 의 설정 주입(서명 강제 + 실패하는
#                                     서명 프로그램 — GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT)을 준다 — 훅 셀 판정이 바뀌지 않는다
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
for c in git sed grep python3; do command -v "$c" >/dev/null 2>&1 || { echo "SETUP $c 부재"; exit 3; }; done
HOOK="$TREE/.githooks/pre-commit"
[ -f "$HOOK" ] || { echo "SETUP 훅 없음: $HOOK"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-precommit-scope.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home" && : > "$TMP/gitconfig" || exit 3
# 저장소를 가리키는 git env 와 비공개 규칙 env 를 먼저 끊는다 — 아래 실측과 셀 판정이 다른 저장소 · 사용자의 규칙 파일에 끌려가지 않게
# 부모 git 의 설정 주입 두 길(GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT)도 끊는다 — 남으면 임시 저장소의 커밋이 호스트 설정(서명 강제 등)에
#   끌려가 준비가 실패한다(저장소 설정으로는 덮이지 않는다 — 명령줄 설정이 가장 높다)
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CEILING_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE FZ_NEUTRALIZE_RULES GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
# 실측(f056-real-tree-measured)은 격리 전에 잰다 — 사용자의 전역 · 시스템 git 설정(무시 파일)을 따라야 평소 `--tree` 가 보는 목록과
#   같다. 격리 뒤에 재면 전역 무시로만 가려지던 미추적 파일(바이너리 등)이 목록에 들어와 판정 불가가 머신마다 갈린다
#   git 저장소가 아닌 트리도 잰다 — 정본의 --tree 가 폴더를 걷는다(내려받은 사본에서도 이 셀이 돈다)
LEAK="$TREE/scripts/leak_rules.py" TREE_RC=""
if [ -f "$LEAK" ]; then
  python3 "$LEAK" -C "$TREE" --tree > "$TMP/tree.out" 2>&1; TREE_RC=$?
fi
# 셀의 git 은 호스트의 XDG 설정 폴더(기본 속성 · 무시 파일)도 읽지 않는다 — 속성 파일의 `binary` 는 추가 줄을 바이너리로 바꿔 판정을 뒤집는다
mkdir -p "$TMP/xdg" || exit 3
export HOME="$TMP/home" GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 XDG_CONFIG_HOME="$TMP/xdg"
U="/Us""ers/fixture-user"   # 음성 토큰은 실행할 때 이어 붙인다 — 이 파일이 누수 검사에 걸리지 않게

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
cell s-changelog-scoped            CHANGELOG.md                "- moved from $U/dev/x"          1
cell s-releases-scoped             docs/releases/v9.9.9.md     "- moved from $U/dev/x"          1
cell f056-placeholder-ok           tests/fixtures/y/run.sh     "W=/Users/example/w · ~/dev/gone/x" 0
cell f056-placeholder-mixed-blocks tests/fixtures/z/run.sh     "A=/Users/example/a B=$U/b"      1

newrepo f056-hook-self-clean
mkdir -p "$R/.githooks" && cp "$HOOK" "$R/.githooks/pre-commit" && git -C "$R" add -A || { echo "SETUP 훅 사본 stage 실패"; exit 3; }
(cd "$R" && bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -eq 0 ]; then ok f056-hook-self-clean "exit 0"; else no f056-hook-self-clean "exit $rc — 훅 본문이 자기 자신에게 막힌다 · $(grep -m1 -A1 'pre-commit:' "$R.out" | tail -n 1 | cut -c1-120)"; fi

# 버전 동기 검사기가 없는 저장소 — 버전 선언(.claude-plugin/plugin.json)이 있으면 배선이 끊긴 것이라 막고(추가 줄은 깨끗하다 — 막은
#   이유가 누수 쪽이 아니다), 선언이 없으면 맞출 버전이 없어 지나간다. 선언은 작업 트리나 인덱스 어느 쪽에 있어도 선언이다
newrepo sync-checker-missing-declared
mkdir -p "$R/.claude-plugin" && printf '{"version": "1.0.0"}\n' > "$R/.claude-plugin/plugin.json" && git -C "$R" add -A \
  || { echo "SETUP stage 실패 sync-checker-missing-declared"; exit 3; }
(cd "$R" && bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -eq 1 ] && grep -q '버전 선언(.claude-plugin/plugin.json)이 있는데' "$R.out" && ! grep -q '식별자가 있다\|누수 검사 미판정' "$R.out"; then
  ok sync-checker-missing-declared "exit 1 — 버전 동기 검사기 부재"
else no sync-checker-missing-declared "exit $rc (기대 1) · $(grep -m1 -E 'pre-commit' "$R.out" | cut -c1-120)"; fi
newrepo sync-checker-missing-declared-index-only
mkdir -p "$R/.claude-plugin" && printf '{"version": "1.0.0"}\n' > "$R/.claude-plugin/plugin.json" && git -C "$R" add -A \
  && rm "$R/.claude-plugin/plugin.json" || { echo "SETUP stage 실패 sync-checker-missing-declared-index-only"; exit 3; }
(cd "$R" && bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -eq 1 ] && grep -q '버전 선언(.claude-plugin/plugin.json)이 있는데' "$R.out" && ! grep -q '식별자가 있다\|누수 검사 미판정' "$R.out"; then
  ok sync-checker-missing-declared-index-only "exit 1 — 선언이 인덱스에만 있다"
else no sync-checker-missing-declared-index-only "exit $rc (기대 1) · $(grep -m1 -E 'pre-commit' "$R.out" | cut -c1-120)"; fi
newrepo sync-checker-missing-undeclared
printf 'x\n' > "$R/note.md" && git -C "$R" add -A || { echo "SETUP stage 실패 sync-checker-missing-undeclared"; exit 3; }
(cd "$R" && bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -eq 0 ] && grep -q '버전 동기 검사는 해당 없음' "$R.out"; then ok sync-checker-missing-undeclared "exit 0 — 버전 선언 없음"
else no sync-checker-missing-undeclared "exit $rc (기대 0) · $(grep -m1 -E 'pre-commit' "$R.out" | cut -c1-120)"; fi
# 선언이 인덱스에 있는지 git 이 답하지 못하면(추적 안 함 = 1 이 아닌 실패) 선언 여부를 모른다 → 차단. PATH 앞의 git 심이 그 호출
#   (--error-unmatch)만 실패시키고 나머지는 진짜 git 으로 넘긴다 — 막은 이유가 누수 쪽이 아니어야 한다
newrepo sync-checker-missing-lsfiles-fail
REAL_GIT="$(command -v git)" && mkdir -p "$TMP/shim-lsfiles" && printf '%s\n' '#!/bin/sh' 'for a in "$@"; do' \
  '  case "$a" in --error-unmatch) echo "git 심: $a 호출을 실패시킨다" >&2; exit 128 ;; esac' 'done' "exec \"$REAL_GIT\" \"\$@\"" \
  > "$TMP/shim-lsfiles/git" && chmod +x "$TMP/shim-lsfiles/git" && printf 'x\n' > "$R/note.md" && git -C "$R" add -A \
  || { echo "SETUP stage 실패 sync-checker-missing-lsfiles-fail"; exit 3; }
(cd "$R" && PATH="$TMP/shim-lsfiles:$PATH" bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -eq 1 ] && grep -q 'git ls-files 가 답하지 못했다(exit 128)' "$R.out" && ! grep -q '식별자가 있다\|누수 검사 미판정' "$R.out"; then
  ok sync-checker-missing-lsfiles-fail "exit 1 — 선언 여부를 모른다"
else no sync-checker-missing-lsfiles-fail "exit $rc (기대 1) · $(grep -m1 -E 'pre-commit' "$R.out" | cut -c1-120)"; fi

# 측정 기록 — 훅이 판정을 넘기는 정본으로 트리 전문을 잰 결과(위에서 격리 전에 쟀다)를 적는다. 적중은 이미 있는 내용이라 셀 판정에
#   쓰지 않는다 — 훅은 추가 줄만 본다. 판정 불가(2) · 종료 코드와 끝 줄이 어긋남만 실패다(측정하지 못한 것을 기록으로 남기지 않는다)
if [ ! -f "$LEAK" ]; then
  no f056-real-tree-measured "정본(scripts/leak_rules.py)이 없다 — 측정 불가"
else
  last="$(tail -n 1 "$TMP/tree.out")"
  files="$(printf '%s\n' "$last" | sed -nE 's/^LEAK_(CLEAN|HIT) tree:[a-z]+ files=([0-9]+) .*/\2/p')"
  case "$TREE_RC:$last" in
    "0:LEAK_CLEAN "*) hits=0 ;;
    "1:LEAK_HIT "*) hits="$(printf '%s\n' "$last" | sed -nE 's/^LEAK_HIT .* hits=([0-9]+)$/\1/p')" ;;
    *) hits="" ;;
  esac
  if [ -n "$files" ] && [ -n "$hits" ]; then
    ok f056-real-tree-measured "정본 --tree 검사 범위 ${files}파일 · 적중 ${hits}건(기존 내용 — 훅은 추가 줄만 본다)"
  else
    no f056-real-tree-measured "정본 --tree exit $TREE_RC — 판정 불가이거나 끝 줄을 읽지 못했다 · $(printf '%s' "$last" | cut -c1-120)"
  fi
fi

# 자식 실행 — git 저장소가 아닌 트리(훅 + 정본만 둔 사본)와 호스트의 XDG git 속성 파일(`* binary`)을 함께 준다. 자식은 이 블록을 돌지 않는다
if [ -z "${FZ_PRECOMMIT_SCOPE_CHILD:-}" ] && [ -f "$LEAK" ]; then
  NG="$TMP/nogit" HX="$TMP/host-xdg"
  mkdir -p "$NG/.githooks" "$NG/scripts" "$HX/git" && cp "$HOOK" "$NG/.githooks/pre-commit" && cp "$LEAK" "$NG/scripts/leak_rules.py" \
    && printf '* binary\n' > "$HX/git/attributes" || { echo "SETUP 자식 실행 준비 실패"; exit 3; }
  FZ_PRECOMMIT_SCOPE_CHILD=1 XDG_CONFIG_HOME="$HX" GIT_CONFIG_PARAMETERS="'commit.gpgsign=true' 'gpg.program=false'" GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=true GIT_CONFIG_KEY_1=gpg.program GIT_CONFIG_VALUE_1=false \
    bash "${BASH_SOURCE[0]}" --tree "$NG" > "$TMP/child.out" 2>&1
  if grep -q '^PASS  f056-real-tree-measured' "$TMP/child.out"; then ok f056-nongit-tree-measured "git 저장소가 아닌 트리도 정본으로 쟀다"
  else no f056-nongit-tree-measured "$(grep -m1 'f056-real-tree-measured' "$TMP/child.out" | cut -c1-160)"; fi
  # 훅을 돌리는 셀 전부를 본다 — 버전 동기 검사기 부재 셀(sync-checker-*)도 훅 셀이다(넷 다 돌아 통과해야 한다)
  bad="$(grep -E '^FAIL  (f056-(precommit|scripts|new-dir|placeholder|hook)|s-|sync-)' "$TMP/child.out" | head -n 3 | tr '\n' ' ' | cut -c1-300)"
  if [ -z "$bad" ] && grep -q '^PASS  f056-placeholder-ok' "$TMP/child.out" && [ "$(grep -c '^PASS  sync-checker-' "$TMP/child.out")" -eq 4 ]; then
    ok host-xdg-attributes-ignored "자식 실행의 훅 셀 전건 통과"
  else no host-xdg-attributes-ignored "${bad:-자식 실행의 훅 셀이 돌지 않았다}"; fi
fi

echo ""
echo "$fail 건 실패"
[ "$fail" -eq 0 ] && echo "PRECOMMIT_SCOPE_OK ${n}셀"
[ "$fail" -eq 0 ]
