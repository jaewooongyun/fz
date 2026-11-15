#!/bin/bash
# 품질 fixture 를 임시 git 저장소로 복원한다.
#   base/ → main 커밋 → feature 브랜치에서 head/ 덮어쓰기 + deleted.txt 삭제 → feature 커밋
#   *.fixture 파일은 원래 이름으로 복원한다(지침 파일 자동 로드 방지 규약 — README).
# 커밋 신원·날짜를 고정해 같은 fixture 는 항상 같은 커밋 해시를 낸다(A/B 입력 해시).
# usage: build_repo.sh FIXTURE_DIR DEST   — DEST 는 존재하지 않아야 한다
# exit: 0=성공 · 2=입력/환경 오류(⛔ 부분 저장소를 남기지 않는다)
set -u
FX="${1:?FIXTURE_DIR 필요}"; DEST="${2:?DEST 필요}"
[ -d "$FX/base" ] || { echo "BUILD-FAIL: $FX/base 없음" >&2; exit 2; }
[ -e "$DEST" ] && { echo "BUILD-FAIL: $DEST 이미 존재" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "BUILD-FAIL: git 없음" >&2; exit 2; }
fail() { echo "BUILD-FAIL: $1" >&2; rm -rf "$DEST"; exit 2; }
export GIT_AUTHOR_NAME=fixture GIT_COMMITTER_NAME=fixture
export GIT_AUTHOR_EMAIL=fixture@example.invalid GIT_COMMITTER_EMAIL=fixture@example.invalid
export GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" GIT_COMMITTER_DATE="2026-01-01T00:00:00Z"
restore() {
  find "$DEST" -name '*.fixture' -type f -not -path '*/.git/*' | while IFS= read -r f; do
    mv "$f" "${f%.fixture}" || exit 1
  done
}
mkdir -p "$DEST" || fail "mkdir"
cp -R "$FX/base/." "$DEST/" || fail "base 복사"
restore || fail "fixture 복원(base)"
git -C "$DEST" init -q || fail "git init"
git -C "$DEST" checkout -q -b main 2>/dev/null || git -C "$DEST" symbolic-ref HEAD refs/heads/main || fail "main 브랜치"
git -C "$DEST" add -A && git -C "$DEST" -c commit.gpgsign=false commit -q -m "base" || fail "base 커밋"
if [ -d "$FX/head" ] || [ -f "$FX/deleted.txt" ]; then
  git -C "$DEST" checkout -q -b feature || fail "feature 브랜치"
  if [ -d "$FX/head" ]; then cp -R "$FX/head/." "$DEST/" || fail "head 복사"; fi
  if [ -f "$FX/deleted.txt" ]; then
    while IFS= read -r p; do
      [ -z "$p" ] && continue
      git -C "$DEST" rm -q -- "$p" || fail "삭제 $p"
    done < "$FX/deleted.txt"
  fi
  restore || fail "fixture 복원(head)"
  git -C "$DEST" add -A && git -C "$DEST" -c commit.gpgsign=false commit -q -m "feature" || fail "feature 커밋"
fi
echo "BUILD-OK $DEST"
