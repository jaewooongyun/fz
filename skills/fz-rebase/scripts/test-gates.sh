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

# 정상 케이스에 WARN이 붙지 않아야 한다.
# ⛔ assert()는 exit code만 본다 — warn()은 HALT_COUNT를 올리지 않으므로 새 WARN 경로가
#    아무리 늘어도 OK 기대 assertion은 전부 초록으로 남는다. 오경보 회귀를 잡으려면
#    등급 문자열을 직접 세야 한다.
assert_no_warn() {  # $1=시나리오 $2=출력
  local name="$1" out="$2" cnt
  cnt=$(printf '%s\n' "$out" | grep -c '^WARN:' || true)
  if [ "${cnt:-0}" -eq 0 ]; then
    PASS=$((PASS+1)); echo "  PASS  $name  (WARN 0건)"
  else
    FAIL=$((FAIL+1)); echo "  FAIL  $name  (WARN ${cnt}건 — 오경보)"
    printf '%s\n' "$out" | grep '^WARN:' | sed 's/^/        /'
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
assert_no_warn "S3n 흡수에 WARN 없음" "$OUT"

echo "── S25: snapshot 이후 base가 이동 → HALT (기준선 혼재 차단)"
# renames·manual-merges는 옛 base 기준, base.map은 현재 base 기준이라 섞이면 판정이 무의미하다.
newrepo s25
g checkout -q feature
printf 'line1\nline2\nMY_CHANGE_S25\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: change"
g checkout -q develop
printf 'other25\n' > src/Other25.swift
g add -A; g commit -qm "team: unrelated"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
# snapshot 이후 base에 커밋이 추가된 상황을 만든다
g checkout -q develop
printf 'moved25\n' > src/Moved25.swift
g add -A; g commit -qm "team: base moved after snapshot"
g checkout -q feature
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S25 base 이동 시 판정 중단" HALT "$?" "$OUT"

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
assert_no_warn "S4n rename에 WARN 없음" "$OUT"

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

echo "── S24: 수동해결 머지의 해결이 리베이스 후에도 살아있음 → 무경보 (오탐 방지)"
# S5의 대조군. 같은 evil merge를 만들되 리베이스 중 해결을 **다시 적용**한다.
# 이것이 무경보여야 머지 대조가 "보존을 유실로 오판하지 않는다"가 성립한다.
newrepo s24
g checkout -q feature
printf 'line1\nline2\nFEATURE_SIDE_S24\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "feature: line3 = feature"
g checkout -q -b side develop
printf 'line1\nline2\nSIDE_BRANCH_S24\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm "side: line3 = side"
g checkout -q feature
g merge --no-ff side >/dev/null 2>&1
printf 'line1\nline2\nEVIL_MERGE_RESOLUTION_S24\nline4\nline5\n' > src/A.swift
g add -A; g -c core.editor=true commit -qm "merge side into feature"
g checkout -q develop
printf 'other\n' > src/Other.swift
g add -A; g commit -qm "team: unrelated file"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ]; then
  # 해결을 다시 적용한다 (사용자가 수동 재적용한 상황)
  printf 'line1\nline2\nEVIL_MERGE_RESOLUTION_S24\nline4\nline5\n' > src/A.swift
  g add -A; finish_rebase >/dev/null 2>&1
fi
OUT=$(bash "$VR" audit develop feature 2>&1); assert "S24 머지 해결 보존은 무경보" OK "$?" "$OUT"
assert_no_warn "S24n 보존 케이스에 WARN 없음" "$OUT"

echo "── S23: 같은 subject의 수동해결 머지 2건 중 1건 유실 → HALT (subject 마스킹 방지)"
# subject 문자열만 대조하면 한 건이 살아남을 때 나머지 유실이 가려진다.
# 롱텀 브랜치는 자동 생성 subject가 반복되므로 이 마스킹이 기본 상황이다.
newrepo s23
g checkout -q feature
printf 'a1\na2\na3\n' > src/A.swift
printf 'b1\nb2\nb3\n' > src/B.swift
g add -A; g commit -qm "feature: two files"
# 첫 번째 evil merge
g checkout -q -b side1 develop
printf 'a1\nSIDE1_S23\na3\n' > src/A.swift
g add -A; g commit -qm "side1"
g checkout -q feature
g merge --no-ff side1 >/dev/null 2>&1
printf 'a1\nEVIL_ONE_S23\na3\n' > src/A.swift
g add -A; g -c core.editor=true commit -qm "Merge branch into feature"
# 두 번째 evil merge — subject를 **같게** 한다
g checkout -q -b side2 develop
printf 'b1\nSIDE2_S23\nb3\n' > src/B.swift
g add -A; g commit -qm "side2"
g checkout -q feature
g merge --no-ff side2 >/dev/null 2>&1
printf 'b1\nEVIL_TWO_S23\nb3\n' > src/B.swift
g add -A; g -c core.editor=true commit -qm "Merge branch into feature"
g checkout -q develop
printf 'unrelated\n' > src/Other23.swift
g add -A; g commit -qm "team: unrelated"
g checkout -q feature
PRE_DUP=$(g log --merges --format=%s develop..feature | sort | uniq -d | wc -l | tr -d ' ')
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
# 첫 머지의 해결만 재적용하고 두 번째는 버린다 → 건수 2 → 1
while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
  if [ -f src/A.swift ] && g diff --name-only --diff-filter=U | grep -q 'A.swift'; then
    printf 'a1\nEVIL_ONE_S23\na3\n' > src/A.swift; g add -A
  else
    g checkout --ours . >/dev/null 2>&1; g add -A >/dev/null 2>&1
  fi
  g -c core.editor=true rebase --continue >/dev/null 2>&1 || g rebase --skip >/dev/null 2>&1 || break
done
OUT=$(bash "$VR" audit develop feature 2>&1); CODE=$?
# ⛔ fixture가 중복 subject를 못 만들면 그 자체가 실패다 (self-skip으로 PASS 처리 금지).
if [ "$PRE_DUP" -ge 1 ]; then
  PASS=$((PASS+1)); echo "  PASS  S23a fixture가 중복 subject 생성 (${PRE_DUP}종)"
else
  FAIL=$((FAIL+1)); echo "  FAIL  S23a fixture가 중복 subject를 만들지 못함 — 검사 무효"
fi
assert "S23b 중복 subject 머지 감소 검출" HALT "$CODE" "$OUT"
# ⛔ 다른 이유의 HALT(리베이스 미완료 등)를 감소 검출로 오인하지 않도록 사유를 확인한다.
assert_has "S23c HALT 사유가 머지 유실/변경" "사라졌거나 내용이 바뀌었다" "$OUT"
assert_has "S23d PRE→POST 건수 명시" "PRE 2건 → POST 1건" "$OUT"

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

echo "── S20: 팀원이 지운 파일의 내 라인이 다른 곳에도 존재 → WARN + 목적지 (거짓 음성 방지)"
# S1의 대조군. 유일한 차이는 같은 문자열이 리포 다른 곳에 있느냐다.
# 전역 대조만 하면 이 케이스가 무경보로 통과한다(내 변경은 실제로 사라졌는데도).
# ⛔ 양쪽이 같은 파일을 만져야 OVERLAP이다. 한쪽만 만지면 버킷①/②가 먼저 잡아
#    라인 검사까지 오지 않는다.
newrepo s20
printf 'struct Legacy { let p = "x" }\n' > src/Legacy.swift
printf 'enum Decoy {\n    static let sharedTimeoutSecondsS20 = 30\n}\n' > src/Decoy.swift
g add -A; g commit -qm "base: Legacy + decoy holding the same line"
g branch -f feature develop
g checkout -q feature
printf 'struct Legacy { let p = "x" }\n    static let sharedTimeoutSecondsS20 = 30\n' > src/Legacy.swift
g add -A; g commit -qm "feature: add a line that also exists in Decoy"
g checkout -q develop
g rm -q src/Legacy.swift; g commit -qm "team: remove Legacy.swift"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  g rm -q src/Legacy.swift >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
fi
OUT=$(bash "$VR" audit develop feature 2>&1); CODE=$?
# ⛔ 제목 문자열만 보면 "틀린 이유로 난 WARN"도 통과한다. 등급·출발지·목적지를 함께 본다.
assert "S20a 위치 후보는 HALT가 아니다" OK "$CODE" "$OUT"
assert_has "S20b 위치 후보 발화" "동일 라인 위치 후보" "$OUT"
assert_has "S20c 출발지가 Legacy.swift" "src/Legacy.swift에서" "$OUT"
assert_has "S20d 목적지로 Decoy.swift 지목" "src/Decoy.swift" "$OUT"

echo "── S22: 매치가 많은 라인 이동 → 비정상 종료 없음 (SIGPIPE 회귀 방지)"
# ⛔ 파이프 버퍼를 넘겨야 발동한다. 파일 수를 늘리는 대신 경로를 길게 해 250개로 도달한다
#    [실측: 6매치=exit 0 / 250매치·50KB=exit 141 / 4000매치=exit 141].
newrepo s22
DEEPDIR="src/a_rather_long_directory_segment_name/another_long_segment/third_level"
mkdir -p "$DEEPDIR"
i=1; while [ "$i" -le 250 ]; do
  printf 'let sharedConstantValueForPipeTestS22 = 42\n' > "$DEEPDIR/a_file_with_quite_a_long_basename_number_${i}.swift"
  i=$((i+1))
done
printf 'struct TargetS22 { let a = 1 }\n' > src/TargetS22.swift
g add -A; g commit -qm "base: many files share one line + target"
g branch -f feature develop
g checkout -q feature
printf 'struct TargetS22 { let a = 1 }\nlet sharedConstantValueForPipeTestS22 = 42\n' > src/TargetS22.swift
g add -A; g commit -qm "feature: add the same line to target"
g checkout -q develop
g rm -q src/TargetS22.swift; g commit -qm "team: remove target"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  g rm -q src/TargetS22.swift >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
fi
OUT=$(bash "$VR" audit develop feature 2>&1); CODE=$?
# exit 141 = SIGPIPE. HALT(1)도 OK(0)도 아닌 값이면 비정상 종료다.
if [ "$CODE" -eq 0 ] || [ "$CODE" -eq 1 ]; then
  PASS=$((PASS+1)); echo "  PASS  S22 대량 매치에서 비정상 종료 없음  (exit $CODE)"
else
  FAIL=$((FAIL+1)); echo "  FAIL  S22 비정상 종료  (exit $CODE — 141이면 SIGPIPE)"; echo "$OUT" | sed 's/^/        /'
fi

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
assert_no_warn "S9n 바이너리 MINE-only에 WARN 없음" "$OUT"

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
assert_no_warn "S11n mode 보존에 WARN 없음" "$OUT"
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
assert_no_warn "S15n 정상 리베이스에 WARN 없음" "$OUT"
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
echo "── S38: 추가 라인 없는 해결이 있어도 머지 스캔이 잘리지 않는다"
# grep '^+' 0매치가 set -e 하에서 파이프라인을 죽이면 호출부 `|| true`가 삼켜
# 이후 머지가 통째로 누락된다. 삭제로 해소한 머지 뒤에 정상 evil merge를 둬서 확인한다.
newrepo s38
g checkout -q feature
printf 'x1\nx2\nx3\n' > src/C38.swift; g add -A; g commit -qm "add C38"
g checkout -q -b side38a feature
printf 'x1\nSIDE\nx3\n' > src/C38.swift; g add -A; g commit -qm side38a
g checkout -q feature; printf 'x1\nFEAT\nx3\n' > src/C38.swift; g add -A; g commit -qm featchg38
g merge --no-ff side38a >/dev/null 2>&1 || true
g rm -q src/C38.swift >/dev/null 2>&1; g -c core.editor=true commit -qm "Merge side38a (delete)" >/dev/null 2>&1
g checkout -q -b side38b feature
printf 'y1\nSIDE2\ny3\n' > src/D38.swift; g add -A; g commit -qm side38b
g checkout -q feature; printf 'y1\nFEAT2\ny3\n' > src/D38.swift; g add -A; g commit -qm featchg38b
g merge --no-ff side38b >/dev/null 2>&1 || true
printf 'y1\nRESOLVED2\ny3\n' > src/D38.swift; g add -A
g -c core.editor=true commit -qm "Merge side38b" >/dev/null 2>&1
g checkout -q develop; printf 'u38\n' > src/U38.swift; g add -A; g commit -qm team38
g checkout -q feature
OUT=$(bash "$VR" snapshot develop feature 2>&1)
assert_has "S38 스캔이 잘리지 않아 머지 2건 모두 기록" "머지 2건" "$OUT"
assert_has "S38b 추가 라인 없는 해결은 NOPLUS로 표기" "NOPLUS" "$OUT"

echo "── S36: 머지 해결이 다른 해결로 대체되면 검출 (subject·건수 근사가 놓치던 것)"
# subject도 같고 머지 수도 같은데 해결 내용만 바뀐 경우. 해결 결과(+ 라인) 해시로 구분한다.
newrepo s36
g checkout -q feature
printf 'x1\nx2\nx3\n' > src/B36.swift; g add -A; g commit -qm "feature: add B36"
g checkout -q -b side36 feature
printf 'x1\nSIDE36\nx3\n' > src/B36.swift; g add -A; g commit -qm side36
g checkout -q feature
printf 'x1\nFEAT36\nx3\n' > src/B36.swift; g add -A; g commit -qm "feature change 36"
g merge --no-ff side36 >/dev/null 2>&1 || true
printf 'x1\nRESOLUTION_ORIGINAL\nx3\n' > src/B36.swift; g add -A
g -c core.editor=true commit -qm "Merge side36 into feature" >/dev/null 2>&1
g checkout -q develop; printf 'u36\n' > src/U36.swift; g add -A; g commit -qm "team: unrelated"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
g rebase --rebase-merges develop >/dev/null 2>&1
i=0
while { [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; } && [ "$i" -lt 12 ]; do
  i=$((i+1))
  printf 'x1\nRESOLUTION_DIFFERENT\nx3\n' > src/B36.swift 2>/dev/null; g add -A >/dev/null 2>&1
  g -c core.editor=true rebase --continue >/dev/null 2>&1 || g rebase --skip >/dev/null 2>&1 || break
done
OUT=$(bash "$VR" audit develop feature 2>&1)
assert_has "S36 해결 내용 대체를 검출" "해결 내용이 다르다" "$OUT"

echo "── S26: ref 이름에 든 셸 메타문자가 audit에서 실행되지 않는다 (인젝션 방어)"
# git은 ref 이름에 `$(...)`·백틱·`|`·`&`를 허용한다(`;`만 거부 — 실측).
# meta.env를 source하면 그 이름이 audit 시점에 명령으로 실행된다.
newrepo s26
EVIL_BR='feat$(id>pwned_s26.txt)x'
if g checkout -qb "$EVIL_BR" 2>/dev/null; then
  printf 'line1\nline2\nMINE_S26\nline4\nline5\n' > src/A.swift
  g add -A; g commit -qm "mine"
  g checkout -q develop
  printf 'other26\n' > src/Other26.swift
  g add -A; g commit -qm "team"
  g checkout -q "$EVIL_BR"
  # ⛔ rm은 snapshot **전**에 둔다. audit 직전에 지우면 snapshot이나 rebase 단계의
  #    인젝션을 놓친다 (전 구간을 덮어야 한다).
  rm -f pwned_s26.txt
  bash "$VR" snapshot develop "$EVIL_BR" >/dev/null 2>&1
  g rebase --rebase-merges develop >/dev/null 2>&1; finish_rebase >/dev/null 2>&1
  bash "$VR" audit develop "$EVIL_BR" >/dev/null 2>&1 || true
  if [ -f pwned_s26.txt ]; then
    FAIL=$((FAIL+1)); echo "  FAIL  S26 ref 인젝션 — snapshot~audit 구간에서 ref 이름이 실행됐다"
  else
    PASS=$((PASS+1)); echo "  PASS  S26 ref 인젝션 방어 (전 구간 미실행)"
  fi
  # 대조군: 이 fixture가 실제로 인젝션을 일으킬 수 있음을 증명한다.
  # 증명이 없으면 "방어됐다"가 아니라 "페이로드가 애초에 무해했다"일 수 있다.
  rm -f pwned_s26.txt
  ( . "$(g rev-parse --git-dir)/fz-rebase-state/meta.env" ) >/dev/null 2>&1 || true
  if [ -f pwned_s26.txt ]; then
    PASS=$((PASS+1)); echo "  PASS  S26b 대조군 — source 방식은 실행됨 (검사가 실패할 수 있음을 증명)"
  else
    FAIL=$((FAIL+1)); echo "  FAIL  S26b 대조군 미성립 — 페이로드가 무해해 S26이 vacuous pass다"
  fi
  rm -f pwned_s26.txt
else
  FAIL=$((FAIL+1)); echo "  FAIL  S26 fixture가 악성 ref 브랜치를 만들지 못함 — 검사 무효"
fi

echo "── S27~S28: rename 후보 등급 분리 (판정 무오염)"
# 기본 -M(50%)에서 놓친 이동을 -M30%로 후보에만 담는다. renames.tsv는 판정에 직접
# 쓰이므로(경로 분할) 후보가 섞이면 버킷이 흔들린다.
newrepo s27
# ⛔ 유사도를 30~50% 대역으로 맞춘다. 50%를 넘으면 기본 -M이 잡아 후보 대역이 아니게 된다
#    [실측: 겹침이 많으면 R051로 확정 대역에 들어간다].
printf 'final class V {\n    private let store: S\n    init(store: S) { self.store = store }\n    func validate(_ r: String) -> Bool {\n        return r.isEmpty == false\n    }\n    func logAttempt(_ r: String) { print("attempt", r) }\n    func auditTrail() -> [String] { return [] }\n    func reset() { store.clear() }\n}\n' > src/V.swift
g add -A; g commit -qm "base: V"
g branch -f feature develop; g checkout -q feature
printf 'final class V {\n    private let store: S\n    init(store: S) { self.store = store }\n    func validate(_ r: String) -> Bool {\n        guard r.hasPrefix("x") else { return false }\n        return r.isEmpty == false\n    }\n    func logAttempt(_ r: String) { print("attempt", r) }\n    func auditTrail() -> [String] { return [] }\n    func reset() { store.clear() }\n}\n' > src/V.swift
g add -A; g commit -qm "mine: guard"
g checkout -q develop
g rm -q src/V.swift; mkdir -p src
printf 'struct Svc {\n    private let store: S\n    init(store: S) { self.store = store }\n    func verify(_ r: String) async throws -> R {\n        let p = try P.parse(r)\n        return r.isEmpty == false ? p : p\n    }\n    func reset() { store.clear() }\n}\n' > src/Svc.swift
g add -A; g commit -qm "team: V -> Svc"
g checkout -q feature
bash "$VR" snapshot develop feature >/dev/null 2>&1
SD27="$(g rev-parse --git-dir)/fz-rebase-state"
if [ -s "$SD27/rename-candidates.tsv" ]; then
  PASS=$((PASS+1)); echo "  PASS  S27 낮은 유사도 이동이 후보 파일에 기록"
else
  FAIL=$((FAIL+1)); echo "  FAIL  S27 후보 파일이 비어 있음"
fi
if [ ! -s "$SD27/renames.tsv" ]; then
  PASS=$((PASS+1)); echo "  PASS  S28 확정 매핑(renames.tsv)은 오염되지 않음"
else
  FAIL=$((FAIL+1)); echo "  FAIL  S28 후보가 확정 매핑에 섞였다"; cat "$SD27/renames.tsv" | sed 's/^/        /'
fi

echo "── S29~S32: 삭제 파일의 대체 후보"
newrepo s29
printf 'final class V { func v(_ r: String) -> Bool { return r.isEmpty == false } }\n' > src/V.swift
g add -A; g commit -qm "base"
g branch -f feature develop; g checkout -q feature
printf 'final class V { func v(_ r: String) -> Bool { guard r.hasPrefix("x") else { return false }\n  return r.isEmpty == false } }\n' > src/V.swift
g add -A; g commit -qm "mine"
g checkout -q develop; g rm -q src/V.swift; mkdir -p src
printf 'enum Policy { static func check(_ r: String) -> Bool { return r.isEmpty == false } }\n' > src/Policy.swift
g add -A; g commit -qm "team: replace V with Policy"
g checkout -q feature
OUT=$(bash "$VR" snapshot develop feature 2>&1)
assert_has "S29 재작성 시 동시 추가를 후보로 제시" "대체 후보일 수 있으나 확정 아님" "$OUT"
assert_has "S29b 후보 파일명 노출" "src/Policy.swift" "$OUT"
# ⛔ 확정 어휘 금지 — provenance이지 대체의 증거가 아니다
if printf '%s' "$OUT" | grep -qE '대체됨|이동함|replaced by'; then
  FAIL=$((FAIL+1)); echo "  FAIL  S29c 후보를 확정 어휘로 표기했다"
else
  PASS=$((PASS+1)); echo "  PASS  S29c 확정 어휘 미사용"
fi
# 헤더 건수는 표시 줄이 아니라 unique 원본 경로 수
HDR=$(printf '%s' "$OUT" | grep -oE '내가 만진 것 [0-9]+건' | grep -oE '[0-9]+' | head -1)
if [ "${HDR:-0}" = "1" ]; then
  PASS=$((PASS+1)); echo "  PASS  S34 헤더가 원본 1건으로 집계 (표시 줄 수 아님)"
else
  FAIL=$((FAIL+1)); echo "  FAIL  S34 헤더 건수 ${HDR} — 표시 줄을 센 것으로 보인다"
fi

echo "── S30: 추가 파일이 많으면 표시만 자른다"
newrepo s30
printf 'final class V { func v() {} }\n' > src/V.swift
g add -A; g commit -qm base
g branch -f feature develop; g checkout -q feature
printf 'final class V { func v() { let x = 1; _ = x } }\n' > src/V.swift
g add -A; g commit -qm mine
g checkout -q develop; g rm -q src/V.swift; mkdir -p src/mod
i=1; while [ "$i" -le 12 ]; do printf 'struct N%d {}\n' $i > "src/mod/N$i.swift"; i=$((i+1)); done
g add -A; g commit -qm "team: squashed refactor"
g checkout -q feature
OUT=$(bash "$VR" snapshot develop feature 2>&1)
assert_has "S30 전체 개수를 밝힌다" "추가된 파일 12개" "$OUT"
assert_has "S30b 표시 상한 초과분을 알린다" "외 7개" "$OUT"

echo "── S31: 삭제가 없으면 후보 줄이 늘지 않는다"
newrepo s31
g checkout -q feature
printf 'line1\nline2\nMINE_S31\nline4\nline5\n' > src/A.swift
g add -A; g commit -qm mine
g checkout -q develop; printf 'other\n' > src/Other31.swift; g add -A; g commit -qm team
g checkout -q feature
OUT=$(bash "$VR" snapshot develop feature 2>&1)
if printf '%s' "$OUT" | grep -q '대체 후보'; then
  FAIL=$((FAIL+1)); echo "  FAIL  S31 삭제가 없는데 후보를 냈다"
else
  PASS=$((PASS+1)); echo "  PASS  S31 삭제 없으면 후보 줄 0개"
fi

echo "── S32: 삭제 커밋이 여럿이면 후보를 특정하지 않는다"
newrepo s32
g checkout -q feature
printf 'v1\nmine\n' > src/A.swift; g add -A; g commit -qm mine
g checkout -q develop
g rm -q src/A.swift; g commit -qm "del 1"
mkdir -p src; printf 'v2\n' > src/A.swift; g add -A; g commit -qm "re-add"
g rm -q src/A.swift; mkdir -p src; printf 'new\n' > src/New32.swift; g add -A; g commit -qm "del 2 + add"
g checkout -q feature
OUT=$(bash "$VR" snapshot develop feature 2>&1)
assert_has "S32 삭제 커밋 복수면 특정하지 않음" "후보를 특정하지 않는다" "$OUT"

echo "── S33·S35: 경로 인코딩과 환경변수 방어"
newrepo s33
g checkout -q feature
printf 'x\n' > 'src/wei"rd\path.txt'
g add -A; g commit -qm "mine: odd path"
g checkout -q develop; printf 'o\n' > src/O33.swift; g add -A; g commit -qm team
g checkout -q feature
set +e; OUT=$(bash "$VR" snapshot develop feature 2>&1); CODE=$?; set -e
if [ "$CODE" -eq 0 ]; then
  PASS=$((PASS+1)); echo "  PASS  S33 큰따옴표·역슬래시 경로에서 snapshot 정상 종료"
else
  FAIL=$((FAIL+1)); echo "  FAIL  S33 특수문자 경로에서 exit ${CODE}"; echo "$OUT" | tail -3 | sed 's/^/        /'
fi
for badv in foo 0 -1; do
  set +e
  OUT=$(FZ_REBASE_RELOCATE_SHOW="$badv" bash "$VR" snapshot develop feature 2>&1); CODE=$?
  set -e
  if [ "$CODE" -eq 0 ]; then
    PASS=$((PASS+1)); echo "  PASS  S35 FZ_REBASE_RELOCATE_SHOW=${badv} 폴백"
  else
    FAIL=$((FAIL+1)); echo "  FAIL  S35 ${badv} 에서 exit ${CODE}"
  fi
done

echo "── SKILL: 충돌 확인 절차의 정적 계약 (프롬프트 변경 회귀 방지)"
# ⛔ 이 절차는 스크립트가 아니라 SKILL.md 문장이라 동작 oracle이 없다.
#    최소한 문서에서 사라지는 것은 기계적으로 잡는다.
SK="$HERE/../SKILL.md"
skill_has() {  # $1=라벨 $2=grep 패턴
  if grep -q -- "$2" "$SK"; then
    PASS=$((PASS+1)); echo "  PASS  $1"
  else
    FAIL=$((FAIL+1)); echo "  FAIL  $1  (SKILL.md에서 '$2' 없음)"
  fi
}
skill_has "K1 충돌 해결에 AskUserQuestion 지시 존재" "AskUserQuestion.*으로 방향을 받는다"
skill_has "K2 응답 전 상태 변경 금지 문장 존재"      "답을 받기 전에는"
skill_has "K3 귀속을 조회로 확정"                     "git ls-files --unmerged"
# ⛔ 존재 검사만으로는 모순 상태(새 지시 + 옛 고정 라벨 병존)를 놓친다. 부재도 본다.
skill_lacks() {  # $1=라벨 $2=있으면 안 되는 패턴
  if grep -q -- "$2" "$SK"; then
    FAIL=$((FAIL+1)); echo "  FAIL  $1  (SKILL.md에 '$2' 잔존)"
  else
    PASS=$((PASS+1)); echo "  PASS  $1"
  fi
}
skill_lacks "K3b 고정 귀속 라벨 부재"                 "ours   = 리베이스된 base 측"
skill_has "K9 대체 후보 안내 존재"                    "대체의 증거가 아니다"
skill_has "K9c 후보와 확정 매핑의 분리 명시"           "판정에는 쓰지 않는다"
skill_has "K10 머지 대조가 해결 내용 해시 기반"         "해결내용 해시"
skill_has "K11 base 신선도 확인 명시"                 "base 신선도"
# ⛔ F-025: 존재만 검사하면 확정 어휘가 병존해도 통과한다. 금지 literal을 함께 본다.
skill_lacks "K9b 후보를 확정으로 쓰는 어휘 부재"        "대체됨"
skill_has "K4 배치 상한 4개 명시"                    "한 번에 질문 4개가 상한"
skill_has "K5 git-path로 리베이스 상태 해석"          "git rev-parse --git-path rebase-merge"
skill_has "K6 continue가 종료가 아님을 명시"          "continue는 종료가 아니다"
skill_has "K7 soft gate임을 명시"                    "soft gate"
skill_has "K8 pbxproj 지시가 확인 절차와 정합"        "3-C의 확인 절차를 건너뛰지 않는다"

echo "════ 결과: PASS=${PASS} FAIL=${FAIL} ════"
[ "$FAIL" -eq 0 ]
