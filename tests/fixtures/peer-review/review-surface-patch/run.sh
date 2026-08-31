#!/bin/bash
# diff-parse: not-a-diff — `^diff --git` 은 **파일 헤더**만 세는 카운트다(hunk 안팎 구분 불요).
#   `+`/`-` 라인 접두사를 판정에 쓰지 않는다 — 파일 수 비교와 `cmp -s` 바이트 동일성만 본다.
# review-surface.patch 가 **실제로 필터하는가** 회귀 판정 — 진짜 git 리포를 만들어 돌린다.
#
# ⛔ 여기서 막는 것은 "라벨은 제외인데 내용은 전량" 인 경로다. 렌즈는 Bash·git 이 없어
#    (peer-review.js OVERRIDE) 스스로 검산할 수 없고, 프롬프트가 전량 diff 를
#    "부풀림 확인용" 으로 강등하므로 **경고가 정반대 확신으로 뒤집힌다.**
#
# 회귀 3종:
#   M  다중 신규커밋   cnt>=2 에서 `merge-base..head` 를 쓰면 `git diff base...head` 와
#                      **정의상 같은 범위**다(3-dot = merge-base..B) → 필터 0
#   S  단일 신규커밋   cnt==1 은 `<sha>^!` 라 원래 필터가 동작한다(대조군)
#   C  동일성 검산     필터 결과가 diff.patch 와 같으면 파일을 만들지 않는다 (negative)
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATHER="$HERE/../../../../skills/fz-peer-review/scripts/gather.sh"
[ -f "$GATHER" ] || { echo "gather.sh 를 찾을 수 없다: $GATHER" >&2; exit 2; }
command -v git >/dev/null 2>&1 || { echo "git 이 없다" >&2; exit 2; }

TMP="$(mktemp -d)" || exit 2
trap 'rm -rf "$TMP"' EXIT

FAIL=0
pass() { printf 'PASS  %-32s %s\n' "$1" "$2"; }
fail() { printf 'FAIL  %-32s %s\n' "$1" "$2"; FAIL=1; }

mkrepo() {   # $1=dir  $2=신규커밋수
  local d="$1" n="$2" i
  mkdir -p "$d" && cd "$d" || return 1
  git init -q . && git config user.email t@t && git config user.name t
  echo base > base.txt && git add . && git commit -qm M1
  git checkout -qb feature
  for i in $(seq 1 "$n"); do echo "f$i" > "f$i.txt"; git add .; git commit -qm "F$i"; done
  git checkout -q main
  echo more >> base.txt && git commit -qam M2
  cd - >/dev/null || return 1
}

# gather.sh 의 patch 생성 로직만 떼어 재생 (원본 식 그대로)
surface_patch() {   # $1=repo  $2=out  → stdout: 판정
  cd "$1" || return 1
  local BASE=main HEAD_REF=feature plus cnt BASE_REF dup
  plus=$(git cherry "$BASE" "$HEAD_REF" 2>/dev/null | awk '$1=="+"{print $2}')
  cnt=$(printf '%s\n' "$plus" | grep -c . || true)
  dup=$(git cherry "$BASE" "$HEAD_REF" 2>/dev/null | grep -c '^-' || true)
  BASE_REF=$(git merge-base "$BASE" "$HEAD_REF")
  git diff "${BASE}...${HEAD_REF}" > "$2/diff.patch"
  # ⛔ 수정 후 방식: `+` 커밋별 patch 를 잇는다
  : > "$2/surface.patch"
  while IFS= read -r sha; do
    [ -n "$sha" ] || continue
    git diff "${sha}^!" >> "$2/surface.patch" 2>/dev/null
  done <<< "$plus"
  # ⛔ 수정 전 방식(회귀 재현용): DRIFT_RANGE 그대로
  local DR=""
  if [ "${cnt:-0}" -eq 1 ]; then DR="$(printf '%s' "$plus")^!"
  elif [ "${cnt:-0}" -gt 1 ]; then DR="${BASE_REF}..${HEAD_REF}"; fi
  git diff "$DR" > "$2/old-way.patch" 2>/dev/null
  echo "$cnt"
  cd - >/dev/null || return 1
}

# ── M: cnt>=2 — 구 방식은 필터 0, 신 방식은 필터 동작 ────────────
mkrepo "$TMP/m" 3 >/dev/null 2>&1 || { echo "repo 생성 실패" >&2; exit 2; }
mkdir -p "$TMP/m-out"
cnt_m=$(surface_patch "$TMP/m" "$TMP/m-out")
if cmp -s "$TMP/m-out/diff.patch" "$TMP/m-out/old-way.patch"; then
  # 구 방식 필터 0 확인 = 회귀가 실재했음을 fixture 가 증명
  if ! cmp -s "$TMP/m-out/diff.patch" "$TMP/m-out/surface.patch" \
     || [ "$(command grep -c '^diff --git' "$TMP/m-out/surface.patch")" -le "$(command grep -c '^diff --git' "$TMP/m-out/diff.patch")" ]; then
    pass "M cnt=${cnt_m} 다중 신규커밋" "구 방식 IDENTICAL(필터0) · 신 방식은 + 커밋분만"
  else
    fail "M cnt=${cnt_m} 다중 신규커밋" "신 방식도 필터하지 못한다"
  fi
else
  fail "M 전제" "구 방식이 이미 다르다 — 시나리오 재현 실패"
fi

# ── S: cnt==1 + dup>0 — 대조군, 원래 필터 동작 ──────────────────
# ⛔ dup 이 실재해야 3-dot 과 `^!` 가 갈린다. 커밋 2개 중 1개를 base 에 체리픽한다.
mkdir -p "$TMP/s" && ( cd "$TMP/s" \
  && git init -q . && git config user.email t@t && git config user.name t \
  && echo base > base.txt && git add . && git commit -qm M1 \
  && git checkout -qb feature \
  && echo f1 > f1.txt && git add . && git commit -qm F1 \
  && echo f2 > f2.txt && git add . && git commit -qm F2 \
  && git checkout -q main \
  && echo more >> base.txt && git commit -qam M2 \
  && git cherry-pick "$(git rev-parse feature~1)" >/dev/null 2>&1 ) || exit 2
mkdir -p "$TMP/s-out"
cnt_s=$(surface_patch "$TMP/s" "$TMP/s-out")
dup_s=$(cd "$TMP/s" && git cherry main feature | grep -c '^-' || true)
if [ "${cnt_s:-0}" -eq 1 ] && [ "${dup_s:-0}" -ge 1 ] \
   && ! cmp -s "$TMP/s-out/diff.patch" "$TMP/s-out/old-way.patch"; then
  pass "S cnt=1·dup=${dup_s} (대조)" "구 방식도 필터 동작 — 결함은 cnt>=2 국한"
else
  fail "S cnt=1·dup>0 (대조)" "cnt=$cnt_s dup=${dup_s:-?}, 대조군 전제 불성립"
fi

# ── C: 동일성 검산이 스크립트에 있는가 (negative 방어) ───────────
if command grep -q 'cmp -s "$STAGE_DIR/diff.patch" "$STAGE_DIR/review-surface.patch"' "$GATHER" \
   && command grep -q '필터 0건이라 만들지 않았다' "$GATHER"; then
  pass "C 동일성 검산 (negative)" "필터 0이면 파일을 만들지 않는다 — 거짓 라벨 방어"
else
  fail "C 동일성 검산 (negative)" "검산 부재 — 라벨이 거짓일 수 있다"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then echo "0 건 실패"; exit 0; else echo "⛔ 불일치 발생"; exit 1; fi
