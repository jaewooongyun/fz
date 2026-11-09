#!/bin/bash
# gather.sh 의 merge-base 실패 사유 회귀 판정 (F-566) — 공통 조상이 없는 두 갈래를 만들어 돌린다.
#
# 세 점 diff(`BASE...TARGET`)는 merge-base 가 없으면 실패한다. stderr 를 버리면 사유가 'diff 실패' 로만 남아
# 이력 재작성 · 얕은 클론 · 다른 저장소를 가를 수 없었다. die 사유에 merge-base 가 있어야 한다.
# 셀:
#   f566-gather-merge-base-reason  공통 조상 없음 → exit 3 · stderr 에 `merge-base`
# exit: 0 통과 · 1 단언 실패 · 3 준비 실패
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATHER="$HERE/../../../../skills/fz-peer-review/scripts/gather.sh"
[ -f "$GATHER" ] || { echo "SETUP gather.sh 를 찾을 수 없다: $GATHER"; exit 3; }
command -v git >/dev/null 2>&1 || { echo "SETUP git 이 없다"; exit 3; }

REPO="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather-mb.XXXXXX")" || exit 3
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather-mb-work.XXXXXX")" || exit 3
trap 'rm -rf "$REPO" "$WORK"' EXIT

cd "$REPO" || exit 3
git init -q -b main . && git config user.email t@t.t && git config user.name t || { echo "SETUP git init 실패"; exit 3; }
printf 'base\n' > a.txt && git add -A && git commit -qm base || { echo "SETUP base 커밋 실패"; exit 3; }
git checkout -q --orphan feature/unrelated && git rm -rqf . >/dev/null \
  && printf 'other\n' > b.txt && git add -A && git commit -qm other || { echo "SETUP 고아 갈래 실패"; exit 3; }

bash "$GATHER" --work-dir "$WORK" --target feature/unrelated --base main >/dev/null 2>"$REPO/err.txt"
rc=$?
err="$(tr '\n' ' ' < "$REPO/err.txt" | cut -c1-200)"
if [ "$rc" -eq 3 ] && grep -q 'merge-base' "$REPO/err.txt"; then
  echo "PASS  f566-gather-merge-base-reason"
  echo "GATHER_MERGE_BASE_OK"
  exit 0
fi
echo "FAIL  f566-gather-merge-base-reason  — exit $rc · stderr: $err"
exit 1
