#!/bin/bash
# gather.sh 의 base 신선도(원격 대조) 회귀 판정 — 진짜 git 리포 3개(bare 원격 · 시드 · 클론)로 돌린다.
#
# ⛔ 여기서 막는 것은 "stale 한 로컬 ref 로 0커밋 앞섬" 이다. base 가 마지막 fetch 시점에
#    묶여 있으면 diff·Tier 판정이 전부 옛 분기점 기준인데 산출물에는 아무 표시도 없다.
#    실측(F-089): 39커밋 stale 인 base 가 조용히 통과했다.
#
# 회귀 2종:
#   S  stale        원격이 앞서면 review-surface.md 첫머리에 경고가 있고 sha7 이 실제 원격 것이다
#   N  동기 (대조)  로컬 == 원격이면 경고가 **없다** — 오경보는 경고를 노이즈로 만든다
#
# ⛔ `git fetch` 를 쓰지 않는다는 계약이 이 fixture 의 전제다. 시드에서만 push 하고 클론은
#    fetch 하지 않으므로, 클론의 `origin/main` 은 뒤에 남는다.
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATHER="$HERE/../../../../skills/fz-peer-review/scripts/gather.sh"
[ -f "$GATHER" ] || { echo "gather.sh 를 찾을 수 없다: $GATHER" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "git 이 없다" >&2; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-stale-base.XXXXXX")" || exit 2
trap 'rm -rf "$TMP"' EXIT

REMOTE="$TMP/remote.git" SEED="$TMP/seed" CLONE="$TMP/clone"

git init -q --bare -b main "$REMOTE" || exit 2
git init -q -b main "$SEED" || exit 2
git -C "$SEED" config user.email t@t.t
git -C "$SEED" config user.name t
printf 'ORIGINAL\n' > "$SEED/mod.txt"
git -C "$SEED" add -A && git -C "$SEED" commit -qm M1
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push -q origin main || { echo "시드 push 실패" >&2; exit 2; }

git clone -q "$REMOTE" "$CLONE" || { echo "clone 실패" >&2; exit 2; }
git -C "$CLONE" config user.email t@t.t
git -C "$CLONE" config user.name t
git -C "$CLONE" checkout -q -b feature/t
printf 'CHANGED\n' > "$CLONE/mod.txt"
git -C "$CLONE" add -A && git -C "$CLONE" commit -qm F1

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1  — $2"; fail=$((fail+1)); }

run_gather() {   # $1=work-dir — gather.sh 는 클론을 cwd 로 돌아야 한다
  ( cd "$CLONE" && bash "$GATHER" --work-dir "$1" --target feature/t --base origin/main \
      > "$1.out" 2> "$1.err" )
}

# ── N: 로컬 == 원격 (대조군) — 경고가 없어야 한다 ────────────────
W_SYNC="$TMP/w-sync"
run_gather "$W_SYNC"
rc=$?
[ $rc -eq 0 ] || { echo "gather.sh exit $rc (동기 케이스)" >&2; cat "$W_SYNC.err" >&2; exit 2; }
[ -f "$W_SYNC/review-surface.md" ] || { echo "review-surface.md 없음 (동기 케이스)" >&2; exit 2; }
if grep -q '원격보다 뒤' "$W_SYNC/review-surface.md"; then
  no "N 동기 상태 오경보 없음" "$(grep -n '원격보다 뒤' "$W_SYNC/review-surface.md" | head -1)"
else
  ok "N 동기 상태 오경보 없음"
fi

# ── S: 원격만 앞으로 — 클론은 fetch 하지 않으므로 origin/main 이 뒤에 남는다 ──
printf 'BASE MOVED ON\n' > "$SEED/other.txt"
git -C "$SEED" add -A && git -C "$SEED" commit -qm M2
git -C "$SEED" push -q origin main || { echo "원격 전진 실패" >&2; exit 2; }

remote_sha=$(git -C "$SEED" rev-parse HEAD)
local_sha=$(git -C "$CLONE" rev-parse origin/main)
[ -n "$remote_sha" ] && [ -n "$local_sha" ] || { echo "sha 해석 실패" >&2; exit 2; }
[ "$remote_sha" != "$local_sha" ] || { echo "전제 불성립 — 클론이 이미 최신이다" >&2; exit 2; }

W_STALE="$TMP/w-stale"
run_gather "$W_STALE"
rc=$?
[ $rc -eq 0 ] || { echo "gather.sh exit $rc (stale 케이스)" >&2; cat "$W_STALE.err" >&2; exit 2; }
[ -f "$W_STALE/review-surface.md" ] || { echo "review-surface.md 없음 (stale 케이스)" >&2; exit 2; }

if grep -q '원격보다 뒤' "$W_STALE/review-surface.md"; then
  ok "S stale base 경고 출력"
else
  no "S stale base 경고 출력" "review-surface.md 첫머리에 경고가 없다"
fi

# 경고가 값을 실제로 채우는가 — 문구만 있고 sha 가 비면 읽는 사람이 확인할 수 없다
if grep -q "${remote_sha:0:7}" "$W_STALE/review-surface.md" \
   && grep -q "${local_sha:0:7}" "$W_STALE/review-surface.md"; then
  ok "S 경고에 원격·로컬 sha7"
else
  no "S 경고에 원격·로컬 sha7" "기대 원격 ${remote_sha:0:7} · 로컬 ${local_sha:0:7}"
fi

# ⛔ 보조 검사다 — stale 이어도 수집은 성공해야 한다 (fail-closed 아님)
if [ -s "$W_STALE/diff.patch" ]; then ok "S stale 이어도 수집 성공 (exit 0 · diff 유효)"
else no "S stale 이어도 수집 성공" "diff.patch 가 비었다"; fi

# 로컬 ref 를 건드리지 않았는가 — `git fetch` 를 쓰면 이 값이 원격으로 따라간다
if [ "$(git -C "$CLONE" rev-parse origin/main)" = "$local_sha" ]; then
  ok "S 로컬 ref 불변 (fetch 하지 않는다)"
else
  no "S 로컬 ref 불변" "origin/main 이 수집 중에 움직였다"
fi

echo
echo "$fail 건 실패"
exit $((fail ? 1 : 0))
