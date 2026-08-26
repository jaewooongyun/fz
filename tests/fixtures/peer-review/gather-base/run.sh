#!/bin/bash
# gather.sh 의 base 원본 수집 회귀 판정 — 실제 git 리포를 만들어 돌린다.
#
# ⛔ 여기서 막는 것은 "조용한 공백"이다. base 원본이 안 모이면 스크립트는 성공하고
#    origin(regression / pre-existing) 판정만 근거를 잃는다 — 실패가 안 보인다.
#
# 회귀 4종:
#   D  삭제 파일        `+++ b/…` 로 잡으면 `+++ /dev/null` 이라 통째로 빠진다
#   R  rename          새 경로는 base 에 없어 `git show` 가 조용히 실패한다
#   C  경로 충돌       `/`→`_` 평탄화는 `a_b/c` 와 `a/b_c` 를 한 파일로 만든다
#   M  merge-base      `A...B` 는 merge-base 기준인데 BASE 팁 내용을 읽으면 원본이 아니다
#   H  hunk 안의 `--- a/x` 를 파일 헤더로 오인하면 남의 경로를 수집한다
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATHER="$HERE/../../../../skills/fz-peer-review/scripts/gather.sh"
[ -f "$GATHER" ] || { echo "gather.sh 를 찾을 수 없다: $GATHER" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "git 이 없다" >&2; exit 2; }

REPO="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather-test.XXXXXX")" || exit 2
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather-work.XXXXXX")" || exit 2
cleanup() { rm -rf "$REPO" "$WORK"; }
trap cleanup EXIT

cd "$REPO" || exit 2
git init -q -b main .
git config user.email t@t.t; git config user.name t

mkdir -p old a_b a nested/deep
printf 'ORIGINAL\n' > mod.txt
printf 'bye\n' > gone.txt
printf 'renamed body\n' > old/name.txt
printf 'A_B slash C\n' > a_b/c.txt          # C: 평탄화하면 a/b_c.txt 와 같은 이름이 된다
printf 'A slash B_C\n' > a/b_c.txt
printf 'deep\n' > nested/deep/file.txt
printf 'keep\n-- a/evil/injected.txt\nkeep2\n' > patchdoc.txt   # H: 지우면 diff 에 `--- a/evil/…` 가 나온다
git add -A && git commit -qm base

git checkout -q -b feature/t
printf 'CHANGED\n' > mod.txt
rm gone.txt
git mv old/name.txt new/name.txt 2>/dev/null || { mkdir -p new; git mv old/name.txt new/name.txt; }
printf 'A_B slash C v2\n' > a_b/c.txt
printf 'A slash B_C v2\n' > a/b_c.txt
printf 'deep v2\n' > nested/deep/file.txt
printf 'keep\nkeep2\n' > patchdoc.txt
printf 'brand new\n' > fresh.txt
git add -A && git commit -qm feature

# M: base 팁을 앞으로 보낸다 — merge-base 를 안 쓰면 여기 내용을 읽는다
git checkout -q main
printf 'BASE MOVED ON\n' > mod.txt
git add -A && git commit -qm "base advanced"
git checkout -q feature/t

bash "$GATHER" --work-dir "$WORK" --target feature/t --base main >/dev/null 2>"$WORK/err.txt"
rc=$?
[ $rc -eq 0 ] || { echo "gather.sh exit $rc" >&2; cat "$WORK/err.txt" >&2; exit 2; }

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1  — $2"; fail=$((fail+1)); }

has() { [ -f "$WORK/base/$1" ]; }
body() { cat "$WORK/base/$1" 2>/dev/null; }

# D 삭제 파일
if has gone.txt && [ "$(body gone.txt)" = "bye" ]; then ok "D 삭제 파일 원본 수집"
else no "D 삭제 파일 원본 수집" "base/gone.txt 없음 또는 내용 불일치"; fi

# R rename — base 에는 **옛 경로**로 있다
if has old/name.txt; then ok "R rename 원본을 옛 경로로 수집"
else no "R rename 원본을 옛 경로로 수집" "base/old/name.txt 없음"; fi
if has new/name.txt; then no "R 새 경로를 조회하지 않음" "base/new/name.txt 가 생겼다"
else ok "R 새 경로를 조회하지 않음"; fi

# C 경로 충돌 — 둘 다 있고 내용이 서로 다르다
if [ "$(body a_b/c.txt)" = "A_B slash C" ] && [ "$(body a/b_c.txt)" = "A slash B_C" ]; then
  ok "C 경로 충돌 없음 (a_b/c.txt ≠ a/b_c.txt)"
else no "C 경로 충돌 없음" "한쪽이 다른 쪽을 덮었다: [$(body a_b/c.txt)] / [$(body a/b_c.txt)]"; fi

# M merge-base — BASE 팁이 아니라 분기점 내용
if [ "$(body mod.txt)" = "ORIGINAL" ]; then ok "M merge-base 기준 원본"
else no "M merge-base 기준 원본" "기대 ORIGINAL, 실제 [$(body mod.txt)]"; fi

# H hunk 안의 `--- a/…` 를 헤더로 오인하지 않는다
if has evil/injected.txt; then no "H hunk 내 --- 를 헤더로 오인 안 함" "base/evil/injected.txt 가 생겼다"
else ok "H hunk 내 --- 를 헤더로 오인 안 함"; fi

# 신규 파일은 base 에 없다
if has fresh.txt; then no "added 파일 제외" "base/fresh.txt 가 생겼다"; else ok "added 파일 제외"; fi

# 매니페스트 상태 표기
m="$WORK/base-manifest.tsv"
check_status() {
  if grep -qE "^$1"$'\t'"$2"$'\t' "$m"; then ok "manifest: $2 → $1"
  else no "manifest: $2 → $1" "실제 [$(grep -F "$2" "$m" | head -1)]"; fi
}
[ -f "$m" ] || { no "manifest 생성" "base-manifest.tsv 없음"; }
if [ -f "$m" ]; then
  check_status deleted gone.txt
  check_status renamed old/name.txt
  grep -qE '^added'$'\t\t''fresh.txt$' "$m" && ok "manifest: fresh.txt → added (old 칸 빈칸)" \
    || no "manifest: fresh.txt → added" "실제 [$(grep -F fresh.txt "$m" | head -1)]"
fi

# 수집 실패 0건이면 경고 섹션이 없어야 한다 (오경보 방지)
if grep -q '수집 실패' "$WORK/base-behavior.md"; then
  no "전건 수집 시 경고 없음" "$(grep -A3 '수집 실패' "$WORK/base-behavior.md" | head -5)"
else ok "전건 수집 시 경고 없음"; fi

# 이전 실행 잔여물 — 재실행이 지워야 한다. 안 지우면 옛 파일이 이번 수집 결과로 읽힌다.
mkdir -p "$WORK/base/ghost"
printf 'from a previous run\n' > "$WORK/base/ghost/leftover.txt"
printf 'user note\n' > "$WORK/my-notes.md"        # 이 스크립트 소유가 아닌 파일
bash "$GATHER" --work-dir "$WORK" --target feature/t --base main >/dev/null 2>&1 || \
  { echo "재실행 실패" >&2; exit 2; }
if [ -f "$WORK/base/ghost/leftover.txt" ]; then
  no "재실행이 이전 base/ 잔여물 제거" "base/ghost/leftover.txt 가 살아남았다"
else ok "재실행이 이전 base/ 잔여물 제거"; fi
if [ -f "$WORK/my-notes.md" ]; then ok "소유 아닌 파일은 보존"
else no "소유 아닌 파일은 보존" "my-notes.md 가 지워졌다"; fi
if [ -f "$WORK/base/mod.txt" ]; then ok "재실행 후에도 산출물 정상"
else no "재실행 후에도 산출물 정상" "base/mod.txt 없음"; fi
# 커밋 실패 시 부분 산출물 0 — 수신 디렉터리가 남아 있으면 안 된다
if compgen -G "$WORK/.gather-incoming.*" >/dev/null; then
  no "수신 디렉터리 정리" "$(echo "$WORK"/.gather-incoming.*)"
else ok "수신 디렉터리 정리"; fi

echo
echo "$fail 건 실패"
exit $((fail ? 1 : 0))
