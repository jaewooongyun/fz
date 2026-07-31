#!/usr/bin/env bash
# test-gates.sh — verify-rebase.sh 게이트의 회귀 검증
#
# 조용한 유실/덮어쓰기를 픽스처 리포에서 실제로 재현하고, 게이트가
#   ① 유실은 HALT로 잡는지                  (S1 S2 S5 S6 S7 S8 S10 S11b S14 S15)
#   ② 정상 케이스는 무경보로 통과하는지        (S3 S4 S9 S11 S12 S13 S6b)
# 를 검사한다. ②가 깨지면 게이트는 노이즈가 되어 결국 무시된다 — 유실 검출과 동등하게 중요하다.
#
# [개조]로 표시된 시나리오는 리베이스가 자연히 만들지 않는 상태를 인위적으로 만들어
# **불변식이 실제로 강제되는지**를 확인한다 (바이너리·mode·무관파일 커버리지 실증).
#
# 사용: bash skills/fz-rebase/scripts/test-gates.sh
# 종료: 0 = 전부 PASS

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
VR="$HERE/verify-rebase.sh"
# PWD 비교로 가드하므로 경로를 정규화한다 (macOS TMPDIR의 trailing slash → `//` 방지, symlink 해소)
ROOT="$(cd "$(mktemp -d)" && pwd -P)"
trap 'rm -rf "$ROOT"' EXIT
PASS=0; FAIL=0
D=""

# 가드: 픽스처 디렉토리 밖에서는 git을 실행하지 않는다 (실 레포 오염 방지).
g() {
  case "$PWD" in
    "$ROOT"/*) ;;
    *) echo "FATAL: cwd가 픽스처 밖이다 ($PWD) — git 실행 중단"; exit 9 ;;
  esac
  git -c user.email=t@t.io -c user.name=Tester -c commit.gpgsign=false -c core.hooksPath=/dev/null "$@"
}

newrepo() {   # 서브셸 금지 — 메인 셸에서 cd 해야 한다
  D="$ROOT/$1"
  mkdir -p "$D/src"
  cd "$D" || exit 1
  git -c init.defaultBranch=develop init -q .
  printf 'line1\nline2\nline3\nline4\nline5\n' > src/A.swift
  g add -A; g commit -qm "base: initial"
  g branch feature
}

finish_rebase() {
  local i=0
  while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
    i=$((i+1)); [ "$i" -gt 12 ] && return 1
    if ! g -c core.editor=true rebase --continue >/dev/null 2>&1; then
      g rebase --skip >/dev/null 2>&1 || return 1
    fi
  done
  return 0
}

assert() {  # $1=시나리오 $2=기대(HALT|OK) $3=실제exit $4=출력
  local name="$1" expect="$2" code="$3" out="$4" actual
  [ "$code" -eq 0 ] && actual=OK || actual=HALT
  if [ "$actual" = "$expect" ]; then
    PASS=$((PASS+1)); echo "  PASS  $name  (기대 $expect)"
  else
    FAIL=$((FAIL+1)); echo "  FAIL  $name  (기대 $expect ≠ 실제 $actual)"; echo "$out" | sed 's/^/        /'
  fi
}

assert_has() {  # 출력에 특정 문자열이 있어야 함 (WARN 등급 검사)
  local name="$1" needle="$2" out="$3"
  if printf '%s' "$out" | grep -q -- "$needle"; then
    PASS=$((PASS+1)); echo "  PASS  $name  ('$needle' 포함)"
  else
    FAIL=$((FAIL+1)); echo "  FAIL  $name  ('$needle' 없음)"; echo "$out" | sed 's/^/        /'
  fi
}

echo "── S1: 팀원이 파일 삭제 + 내 수정 → 삭제 수용으로 해소 → 내 변경 소실"
newrepo s1
g checkout -q feature
printf 'line1\nline2\nline3\nMY_UNIQUE_FEATURE_FLAG_S1 = true\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: add flag"
g checkout -q develop
g rm -q src/A.swift; g commit -qm "team: remove A.swift"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then g rm -q src/A.swift >/dev/null 2>&1; finish_rebase >/dev/null 2>&1; fi
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S1 내 변경 소실" HALT "$?" "$OUT"

echo "── S2: 충돌을 --theirs(내 커밋)로 해소 → 팀원 변경 소실"
newrepo s2
g checkout -q feature
printf 'line1\nline2\nMY_VERSION_S2\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: change line3"
g checkout -q develop
printf 'line1\nline2\nTEAM_NEW_LINE_S2\nline4\nline5\nTEAM_APPENDED_S2\n' > src/A.swift
g add -A; g commit -qm "team: change line3 + append"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then
  g checkout --theirs src/A.swift >/dev/null 2>&1; g add src/A.swift; finish_rebase >/dev/null 2>&1
fi
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S2 팀원 변경 소실" HALT "$?" "$OUT"

echo "── S3: base가 내 패치를 이미 흡수(커밋 드롭) → 무경보 (오탐 방지)"
newrepo s3
g checkout -q feature
printf 'line1\nline2\nline3\nABSORBED_LINE_S3 = 1\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: add absorbed line"
g checkout -q develop
printf 'line1\nline2\nline3\nABSORBED_LINE_S3 = 1\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "team: same change landed upstream"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S3 흡수는 무경보" OK "$?" "$OUT"

echo "── S4: 팀원 rename → 내 hunk가 새 경로 착지 → 무경보 (파티션 rename 매핑)"
newrepo s4
g checkout -q feature
printf 'line1\nline2\nline3\nMY_LINE_AFTER_RENAME_S4 = 1\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: add line"
g checkout -q develop
mkdir -p src/Moved; g mv src/A.swift src/Moved/A.swift
printf 'line1\nline2\nline3\nline4\nline5\nTEAM_TAIL_S4\n' > src/Moved/A.swift
g add -A; g commit -qm "team: move A.swift + append"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S4 정당한 rename 무경보" OK "$?" "$OUT"

echo "── S5: 머지 커밋의 수동 해결(evil merge) 유실"
newrepo s5
g checkout -q feature
printf 'line1\nline2\nFEATURE_SIDE_S5\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: line3 = feature"
g checkout -q -b side develop
printf 'line1\nline2\nSIDE_BRANCH_S5\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "side: line3 = side"
g checkout -q feature
g merge --no-ff side >/dev/null 2>&1
printf 'line1\nline2\nEVIL_MERGE_RESOLUTION_S5\nline4\nline5\n' > src/A.swift
g add -A; g -c core.editor=true commit -qm "merge side into feature"
g checkout -q develop
printf 'other\n' > src/Other.swift
g add -A; g commit -qm "team: unrelated file"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then g checkout --ours src/A.swift >/dev/null 2>&1; g add -A; finish_rebase >/dev/null 2>&1; fi
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S5 머지 수동해결 유실" HALT "$?" "$OUT"

echo "── S7: 내가 지운 파일 + 팀원이 수정 → 팀원 것 유지로 해소 → 내 삭제 유실"
newrepo s7
g checkout -q feature
g rm -q src/A.swift; g commit -qm "feature: delete A.swift"
g checkout -q develop
printf 'line1\nline2\nTEAM_EDIT_S7\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "team: edit A.swift"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then g add src/A.swift >/dev/null 2>&1; finish_rebase >/dev/null 2>&1; fi
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S7 내 삭제 유실" HALT "$?" "$OUT"

echo "── S8: 팀원이 지운 파일 + 내가 수정 → 내 것 유지로 해소 → 팀원 삭제 유실"
newrepo s8
g checkout -q feature
printf 'line1\nline2\nMY_EDIT_S8\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: edit A.swift"
g checkout -q develop
g rm -q src/A.swift; g commit -qm "team: delete A.swift"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then g add src/A.swift >/dev/null 2>&1; finish_rebase >/dev/null 2>&1; fi
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S8 팀원 삭제 유실" HALT "$?" "$OUT"

echo "── S9: 내가 변경한 바이너리(base 미변경) → 무경보 (바이너리 오탐 방지)"
newrepo s9
printf 'bin\000ORIGINAL\n' > src/asset.bin; g add -A; g commit -qm "base: add binary"
g branch -f feature HEAD
g checkout -q feature
printf 'bin\000MINE_S9\n' > src/asset.bin; g add -A; g commit -qm "feature: change binary"
g checkout -q develop
printf 'unrelated\n' > src/Other.swift; g add -A; g commit -qm "team: unrelated"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S9 바이너리 MINE-only 무경보" OK "$?" "$OUT"

echo "── S10 [개조]: 바이너리 내용이 리베이스 후 되돌려짐 → HALT (바이너리 커버리지 실증)"
printf 'bin\000ORIGINAL\n' > src/asset.bin; g add -A; g commit -qm "tamper: revert binary"
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S10 바이너리 유실 검출" HALT "$?" "$OUT"

echo "── S11: mode 변경(chmod +x) 보존 → 무경보 / 되돌리면 → HALT (mode 커버리지)"
newrepo s11
printf '#!/bin/sh\necho hi\n' > src/run.sh; g add -A; g commit -qm "base: add script"
g branch -f feature HEAD
g checkout -q feature
chmod +x src/run.sh; g add -A; g commit -qm "feature: chmod +x"
g checkout -q develop
printf 'unrelated\n' > src/Other.swift; g add -A; g commit -qm "team: unrelated"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S11 mode 보존 무경보" OK "$?" "$OUT"
chmod -x src/run.sh; g add -A; g commit -qm "tamper: chmod -x"
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S11b [개조] mode 유실 검출" HALT "$?" "$OUT"

echo "── S12: 바이너리 OVERLAP(양쪽 변경) → WARN, auto-HALT 아님"
newrepo s12
printf 'bin\000ORIGINAL\n' > src/asset.bin; g add -A; g commit -qm "base: add binary"
g branch -f feature HEAD
g checkout -q feature
printf 'bin\000MINE_S12\n' > src/asset.bin; g add -A; g commit -qm "feature: change binary"
g checkout -q develop
printf 'bin\000TEAM_S12\n' > src/asset.bin; g add -A; g commit -qm "team: change binary"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then g checkout --theirs src/asset.bin >/dev/null 2>&1; g add -A; finish_rebase >/dev/null 2>&1; fi
OUT=$(bash "$VR" audit develop feature 2>&1); CODE=$?
assert "S12 바이너리 OVERLAP은 HALT 아님" OK "$CODE" "$OUT"
assert_has "S12b 바이너리 OVERLAP WARN 발화" "OVERLAP 바이너리" "$OUT"

echo "── S15 [개조]: 내가 손대지 않은 팀원 파일이 오염 → HALT (버킷② 실증)"
newrepo s15
g checkout -q feature
printf 'line1\nline2\nline3\nMINE_S15\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: my change"
g checkout -q develop
printf 'team content\n' > src/TeamOnly.swift; g add -A; g commit -qm "team: add TeamOnly"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S15a 정상 리베이스 무경보" OK "$?" "$OUT"
printf 'clobbered\n' > src/TeamOnly.swift; g add -A; g commit -qm "tamper: clobber team file"
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S15b [개조] 팀원 파일 오염 검출" HALT "$?" "$OUT"

echo "── S6: ff-pull 이후 팀원이 원격에 push → force-push 파괴"
D="$ROOT/s6"; mkdir -p "$D"; cd "$D" || exit 1
git init -q --bare remote.git
git clone -q remote.git work >/dev/null 2>&1
cd work || exit 1
mkdir -p src; printf 'line1\nline2\n' > src/A.swift
g add -A; g commit -qm "base: initial"; g branch -M develop; g push -q -u origin develop
g checkout -q -b feature; printf 'line1\nline2\nMINE_S6\n' > src/A.swift
g add -A; g commit -qm "feature: mine"; g push -q -u origin feature
cd "$D" || exit 1; git clone -q remote.git mate >/dev/null 2>&1; cd mate || exit 1
g checkout -q feature; printf 'line1\nline2\nMINE_S6\nMATE_COMMIT_S6\n' > src/A.swift
g add -A; g commit -qm "mate: teammate work"; g push -q origin feature
cd "$D/work" || exit 1; g fetch -q origin
OUT=$(bash "$VR" prepush feature origin feature 2>&1); assert "S6 force-push 파괴 검출" HALT "$?" "$OUT"
g merge -q --ff-only origin/feature >/dev/null 2>&1
OUT=$(bash "$VR" prepush feature origin feature 2>&1); assert "S6b 팀원 커밋 반영 후 통과" OK "$?" "$OUT"

echo "── S13: 원격에 평범한 PR 머지(내용 없음) → prepush WARN, HALT 아님"
D="$ROOT/s13"; mkdir -p "$D"; cd "$D" || exit 1
git init -q --bare remote.git; git clone -q remote.git work >/dev/null 2>&1
cd work || exit 1
mkdir -p src; printf 'l1\n' > src/A.swift; g add -A; g commit -qm "base"; g branch -M develop; g push -q -u origin develop
g checkout -q -b feature; printf 'l1\nmine\n' > src/A.swift; g add -A; g commit -qm "feature: mine"
g push -q -u origin feature
# 팀원: side 브랜치를 충돌 없이 머지 (평범한 PR 머지)
cd "$D" || exit 1; git clone -q remote.git mate >/dev/null 2>&1; cd mate || exit 1
g checkout -q feature; g checkout -q -b side
printf 'side content\n' > src/Side.swift; g add -A; g commit -qm "mate: side work"
g checkout -q feature; g merge -q --no-ff side -m "mate: Merge pull request side"
g push -q origin feature
cd "$D/work" || exit 1; g fetch -q origin
# 팀원 non-merge 커밋을 내 브랜치에 등가로 반영(cherry-pick) → 남는 것은 머지 커밋뿐
g cherry-pick "$(git rev-list origin/feature --no-merges -1 --grep='side work')" >/dev/null 2>&1
OUT=$(bash "$VR" prepush feature origin feature 2>&1); CODE=$?
assert "S13 평범한 머지는 HALT 아님" OK "$CODE" "$OUT"
assert_has "S13b 머지 소실 WARN 발화" "히스토리 구조만" "$OUT"

echo "── S14: 원격에 수동해결 머지(evil) → prepush HALT"
D="$ROOT/s14"; mkdir -p "$D"; cd "$D" || exit 1
git init -q --bare remote.git; git clone -q remote.git work >/dev/null 2>&1
cd work || exit 1
mkdir -p src; printf 'l1\nl2\nl3\n' > src/A.swift; g add -A; g commit -qm "base"; g branch -M develop; g push -q -u origin develop
g checkout -q -b feature; printf 'l1\nMINE\nl3\n' > src/A.swift; g add -A; g commit -qm "feature: mine"
g push -q -u origin feature
cd "$D" || exit 1; git clone -q remote.git mate >/dev/null 2>&1; cd mate || exit 1
g checkout -q feature; g checkout -q -b side origin/develop
printf 'l1\nSIDE\nl3\n' > src/A.swift; g add -A; g commit -qm "mate: side edit"
g checkout -q feature; g merge --no-ff side >/dev/null 2>&1
printf 'l1\nEVIL_REMOTE_RESOLUTION\nl3\n' > src/A.swift   # 어느 부모에도 없는 내용
g add -A; g -c core.editor=true commit -qm "mate: Merge side (manual resolve)"
g push -q origin feature
cd "$D/work" || exit 1; g fetch -q origin
OUT=$(bash "$VR" prepush feature origin feature 2>&1); assert "S14 원격 evil merge 파괴 검출" HALT "$?" "$OUT"

echo ""
echo "════ 결과: PASS=${PASS} FAIL=${FAIL} ════"
[ "$FAIL" -eq 0 ]
