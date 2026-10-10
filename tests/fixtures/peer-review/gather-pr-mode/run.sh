#!/bin/bash
# gather.sh PR 모드 회귀 판정 — 합성 fork 저장소 + 공용 gh shim(`tests/fixtures/peer-review/_shim/gh`)으로 오프라인 재생한다.
#
# ⛔ 네트워크 0 (EC-31): 원격은 로컬 bare 저장소 **경로** · GIT_ALLOW_PROTOCOL=file · shim 을 PATH 맨 앞 · GH_* env 제거 ·
#    바깥 git 설정(전역 · 시스템) 차단. 셀마다 shim 호출 로그가 비어 있지 않고 거부 0 인지 본다(실 gh 로 새면 로그가 빈다).
# ⛔ gather 는 fetch 하지 않는다(stale-base 계약) — 원격 추적 ref 는 setup 이 로컬 bare 에서 미리 준비한다.
#
# 배치(setup — 모든 셀 공통):
#   base.git  기준 저장소(upstream). main = C2 · experiment = X · refs/pull/<N>/head = P
#   fork.git  갈라진 fork(origin). main = C1 에 멈춤
#   clone     upstream = base.git · origin = fork.git (둘 다 로컬 경로). 로컬 main = C1(stale — 원격보다 1커밋 뒤) ·
#             upstream/main = C2(미리 준비한 원격 추적 ref) · pr-<N> = P(Step 0.5 가 만들었을 ref)
#   C0  루트 커밋 — SHA 앞 4자리가 숫자다(고정 날짜 · 메시지 소금으로 고른다 → 실행마다 같다). main 의 조상
#   X   C0 위 곁가지 — SHA 앞 4자리가 숫자인 둘째 커밋(main 의 조상 아님) · 50줄 추가
#   P   C2 위 PR head — 수정 +2 −1 · 삭제(공백 경로) −3 · 개명+수정 +1 −1 · 순수 개명 · 바이너리 추가 → +3 −5
#       (setup 이 `git diff --numstat C2 P` 합과 대조한다 — 바이너리 `-` 행 · 개명 `=>` 행이 있어야 한다)
# 셀 (--cells numstat):
#   numstat-sha-ancestor   PR 번호 = C0 접두. 기준 gather 의 `git diff --numstat main...<N>` 은 exit 0 · 0바이트(F-135 의 `+0 −0`)
#   numstat-sha-inflated   PR 번호 = X 접두. 기준은 C0..X 범위(+50)를 PR 변경량으로 보고한다(F-350)
#   numstat-meta-mismatch  PR 메타 additions · deletions 가 patch 와 다르다 → GATHER-WARN(F-350 ②). 번호는 충돌 없는 것 —
#                          기준도 합은 맞으므로 이 셀의 기준 실패는 경고 부재 하나로 갈린다
#   numstat-unresolved     대조군 — PR 번호가 어떤 객체 접두도 아니다. 기준도 git 이 exit 128 → awk 폴백으로 통과한다
#                          (기준 실패의 원인이 'PR 번호의 SHA 해석'임을 가른다)
#   numstat-branch-binary-rename  브랜치 모드 회귀 — numstat 출처가 diff.patch 로 바뀌어도 합 = `git diff --numstat` 합(바이너리 · 개명)
# 셀 (--cells base) — F-240: PR 모드 base 는 로컬 존재와 무관하게 base 저장소 원격의 원격 추적 ref 다. PR 번호는 무충돌(N_U)
#   배치: bare 를 `…/base-owner/base-repo.git`(main = C2 · refs/pull/<N>/head = P) · `…/fork-owner/base-repo.git`(main = C1)
#         경로에 둔다 — base 저장소 판별이 원격 URL 의 마지막 두 경로 조각(owner/repo)이라서다. 클론마다 로컬 main = C1(stale) · pr-<N> = P
#   base-stale-local             upstream = base 저장소. 로컬 main(C1)이 있어도 upstream/main(C2)을 고른다 — base/ 원본 · merge-base 가
#                                diff.patch 의 기준과 같다(`git diff <merge-base> pr-<N>` = diff.patch). 기준은 로컬 main 을 써 FAIL
#   base-upstream-not-base-repo  upstream = 멈춘 fork(C1) · origin = base 저장소(C2). PR url 과 URL 이 맞는 origin 을 고른다 —
#                                이름 순(upstream → origin) 만 보는 구현은 upstream/main(C1)을 골라 FAIL
#   base-tracking-stale          base 저장소 원격의 추적 ref 가 원격보다 1커밋 뒤(C1 · 원격 C2 = baseRefOid). 그 ref 를 그대로 쓰고
#                                GATHER-WARN stale(두 sha7) · fetch 0(ref 전체 불변) · ls-remote 대조 '원격보다 뒤' 줄도 함께 난다
#   base-no-match-fallback       PR url 이 어느 원격과도 안 맞는다 → GATHER-NOTE '기준 저장소 대조 실패' + upstream → origin 순회(upstream/main)
#   base-prefixed-remote         `--base upstream/main`(원격 추적 ref 그대로) · 추적 ref 가 1커밋 뒤. 원격을 다시 고르지 않고 사실과 다른
#                                NOTE('upstream/upstream/main 미fetch' · '어느 원격에도') 없이, 브랜치 이름으로 오프라인 신선도를 잰다(GATHER-WARN stale)
# 끝 — 고른 묶음의 기대 셀 집합(expect_of)과 실제로 판정한 셀(RAN)이 정확히 같아야 한다. 셀 블록을 지운 사본은 1(F-408)
# 셀 (--cells shim-fields) — I6: shim 은 gh 2.87.3 `pr view --json` 실제 필드만 받는다
#   shim-fields-real     실제 필드 url · baseRefOid 를 고정 응답 그대로 낸다(--json · -q 둘 다)
#   shim-fields-unknown  실재하지 않는 필드는 실 gh 문구(`Unknown JSON field`)로 거부한다
#   shim-fields-absent   실재 필드라도 고정 응답에 없으면 지어내지 않고 거부한다
#   shim-fields-gather   gather 의 실제 `--json` 요청이 url · baseRefOid 를 포함하고 shim 이 하나도 거부하지 않는다
# exit: 0 전건 통과 · 1 단언 실패(판정 줄 뒤에만) · 3 준비 실패(인자 · 도구 · 저장소 · 전제)
#   ⛔ 판정 줄 없이 끝나면(셸 오류 · 중간 종료) 1 이 아니라 3 으로 낸다 — 1 은 단언 실패만 뜻한다.
# usage: run.sh [--tree <플러그인 트리>] [--cells numstat,base,shim-fields]   (기본: 이 fixture 가 든 트리 · 전 셀 — health-check 는 인자 없이 부른다)
set -u

DONE=0 fail=0 TMP=""
finish() {
  local rc=$?
  [ -n "$TMP" ] && rm -rf "${TMP:?}"
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ] && [ "$DONE" -ne 1 ]; then
    echo "SETUP 판정 줄 없이 끝났다(exit $rc) — 단언 실패(1)가 아니라 준비 실패 3 으로 낸다"
    exit 3
  fi
  exit "$rc"
}
trap finish EXIT
setup_fail() { echo "SETUP $*"; exit 3; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || setup_fail "fixture 경로 해석 실패"
TREE="$(cd "$HERE/../../../.." && pwd)" || setup_fail "기본 트리 해석 실패"
ALL_GROUPS="numstat base shim-fields"
CELLS="$(printf '%s' "$ALL_GROUPS" | tr ' ' ',')"   # ⛔ 쉼표로 잇는다 — want() 가 `,<묶음>,` 으로 찾는다(공백으로 이으면 인자 없는 실행이 0셀)
# 묶음마다 판정해야 하는 셀 — 끝에서 RAN 과 대조한다(원장 CHECK 는 exit 만 보므로 셀 하나를 지워도 통과하던 구멍 · F-408)
expect_of() {
  case "$1" in
    numstat) echo "numstat-sha-ancestor numstat-sha-inflated numstat-meta-mismatch numstat-unresolved numstat-branch-binary-rename" ;;
    base) echo "base-stale-local base-upstream-not-base-repo base-tracking-stale base-no-match-fallback base-prefixed-remote" ;;
    shim-fields) echo "shim-fields-real shim-fields-unknown shim-fields-absent shim-fields-gather" ;;
  esac
}
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || setup_fail "--tree 에 경로가 없다"
            TREE="$(cd "$2" 2>/dev/null && pwd)" || setup_fail "--tree 경로 없음: $2"; shift 2 ;;
    --cells) [ $# -ge 2 ] || setup_fail "--cells 에 값이 없다"; CELLS="$2"; shift 2 ;;
    *) setup_fail "알 수 없는 인자: $1" ;;
  esac
done
for g in $(printf '%s' "$CELLS" | tr ',' ' '); do
  case " $ALL_GROUPS " in *" $g "*) ;; *) setup_fail "알 수 없는 셀 묶음: $g (지원: $ALL_GROUPS)" ;; esac
done
want() { case ",$CELLS," in *",$1,"*) return 0 ;; esac; return 1; }

for c in git python3 awk sed; do command -v "$c" >/dev/null 2>&1 || setup_fail "$c 부재"; done
GATHER="$TREE/skills/fz-peer-review/scripts/gather.sh"
SHIM="$HERE/../_shim"
[ -f "$GATHER" ] || setup_fail "gather.sh 없음: $GATHER"
[ -x "$SHIM/gh" ] || setup_fail "gh shim 없음(실행 불가): $SHIM/gh"
SHIM="$(cd "$SHIM" && pwd)"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-gather-pr-mode.XXXXXX")" || setup_fail "임시 폴더 실패"
mkdir -p "$TMP/home" "$TMP/t" "$TMP/cells" || setup_fail "임시 하위 폴더 실패"
: > "$TMP/gitconfig" || setup_fail "임시 gitconfig 실패"

# ── 격리 (EC-31) ─────────────────────────────────────────────
for v in $(env | sed -n 's/^\(GH_[A-Za-z0-9_]*\)=.*/\1/p'); do unset "$v"; done
unset GITHUB_TOKEN GITHUB_ENTERPRISE_TOKEN GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY \
      GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CEILING_DIRECTORIES
export HOME="$TMP/home" GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 \
       GIT_ALLOW_PROTOCOL=file TMPDIR="$TMP/t" PATH="$SHIM:$PATH"
export GIT_AUTHOR_NAME=f GIT_AUTHOR_EMAIL=f@f.f GIT_COMMITTER_NAME=f GIT_COMMITTER_EMAIL=f@f.f \
       GIT_AUTHOR_DATE="@1767225600 +0000" GIT_COMMITTER_DATE="@1767225600 +0000"
[ "$(command -v gh)" = "$SHIM/gh" ] || setup_fail "PATH 맨 앞 gh 가 shim 이 아니다: $(command -v gh)"
[ -z "$(env | sed -n '/^GH_/p')" ] || setup_fail "GH_* env 가 남았다"

g() { git -C "$1" "${@:2}"; }
SEED="$TMP/seed" BASEG="$TMP/base.git" FORKG="$TMP/fork.git" CL="$TMP/clone"

# $1=폴더 $2=트리 $3=부모(빈 값이면 루트) $4=소금 접두 $5=피할 접두 — SHA 앞 4자리가 숫자([1-9]…)인 커밋을 고른다
pick_numeric() {
  local i=0 c p
  while [ "$i" -lt 400 ]; do
    if [ -n "$3" ]; then c=$(printf '%s %d\n' "$4" "$i" | g "$1" commit-tree "$2" -p "$3") || return 1
    else c=$(printf '%s %d\n' "$4" "$i" | g "$1" commit-tree "$2") || return 1; fi
    p=${c:0:4}
    case "$p" in [1-9][0-9][0-9][0-9]) [ "$p" != "$5" ] && { echo "$c"; return 0; } ;; esac
    i=$((i + 1))
  done
  return 1
}

# ── setup: 시드 → base.git · fork.git → 클론 ──────────────────
{ git init -q -b main "$SEED" && mkdir -p "$SEED/Sources" "$SEED/old" "$SEED/docs"; } || setup_fail "시드 초기화 실패"
printf 'v1\nkeep\n' > "$SEED/f.txt"
printf 'final class LegacyCache {\n    var items: [String] = []\n}\n' > "$SEED/Sources/Legacy Cache.swift"
for i in 1 2 3 4 5 6 7 8 9 10; do printf 'name line %d\n' "$i"; done > "$SEED/old/name.txt"
for i in 1 2 3 4 5; do printf 'doc line %d\n' "$i"; done > "$SEED/docs/a.txt"
g "$SEED" add -A && T0=$(g "$SEED" write-tree) || setup_fail "C0 트리 실패"
C0=$(pick_numeric "$SEED" "$T0" "" "C0 seed" "") || setup_fail "숫자 접두 C0 를 400회 안에 못 골랐다"
N_A=${C0:0:4}
g "$SEED" update-ref refs/heads/main "$C0" || setup_fail "main=C0 실패"
{ printf 'c1\n' > "$SEED/c1.txt" && g "$SEED" add -A && g "$SEED" commit -qm C1; } || setup_fail "C1 실패"
C1=$(g "$SEED" rev-parse HEAD)
{ printf 'v2\nkeep\n' > "$SEED/f.txt" && g "$SEED" commit -qam C2; } || setup_fail "C2 실패"
C2=$(g "$SEED" rev-parse HEAD)
# X — C0 위 곁가지(50줄)
{ g "$SEED" checkout -q -b experiment "$C0" \
  && for i in $(seq 1 50); do printf 'legacy %d\n' "$i"; done > "$SEED/legacy.txt" \
  && g "$SEED" add -A; } || setup_fail "곁가지 준비 실패"
TX=$(g "$SEED" write-tree) || setup_fail "X 트리 실패"
X=$(pick_numeric "$SEED" "$TX" "$C0" "X seed" "$N_A") || setup_fail "숫자 접두 X 를 400회 안에 못 골랐다"
N_B=${X:0:4}
{ g "$SEED" update-ref refs/heads/experiment "$X" && g "$SEED" checkout -q main; } || setup_fail "곁가지 확정 실패"
# P — C2 위 PR head
{ g "$SEED" checkout -q -b pr main \
  && printf 'v3\nkeep\nadded\n' > "$SEED/f.txt" \
  && g "$SEED" rm -q "Sources/Legacy Cache.swift" \
  && mkdir -p "$SEED/new" && g "$SEED" mv old/name.txt new/name.txt \
  && sed -e 's/^name line 5$/name line five/' "$SEED/new/name.txt" > "$SEED/new/name.tmp" && mv "$SEED/new/name.tmp" "$SEED/new/name.txt" \
  && g "$SEED" mv docs/a.txt docs/b.txt \
  && mkdir -p "$SEED/assets" && printf 'PNG\000\001\002bin\000' > "$SEED/assets/logo.bin" \
  && g "$SEED" add -A && g "$SEED" commit -qm P; } || setup_fail "PR head 실패"
P=$(g "$SEED" rev-parse HEAD)
g "$SEED" diff "$C2" "$P" > "$TMP/pr.diff" || setup_fail "pr.diff 생성 실패"
ns=$(g "$SEED" diff --numstat "$C2" "$P") || setup_fail "git numstat 실패"
[ "$(printf '%s\n' "$ns" | awk -F'\t' '{a+=$1; d+=$2} END{print a+0, d+0}')" = "3 5" ] \
  || setup_fail "PR patch 합이 +3 −5 가 아니다(fixture 작성 오류): $(printf '%s' "$ns" | tr '\n\t' '; ')"
printf '%s\n' "$ns" | awk -F'\t' '$1=="-" && $2=="-"{b=1} $3 ~ /=>/{r=1} END{exit !(b && r)}' \
  || setup_fail "PR patch 에 바이너리 · 개명 행이 없다(전제 불성립): $(printf '%s' "$ns" | tr '\n\t' '; ')"

{ git init -q --bare -b main "$BASEG" && git init -q --bare -b main "$FORKG" \
  && g "$SEED" push -q "$BASEG" main experiment \
  && g "$SEED" push -q "$FORKG" "$C1:refs/heads/main"; } || setup_fail "bare 원격 준비 실패"
{ git clone -q -o upstream "$BASEG" "$CL" && g "$CL" remote add origin "$FORKG" && g "$CL" fetch -q origin; } \
  || setup_fail "클론 · fork 원격 실패"
# 충돌 없는 번호 — 클론의 어떤 객체 접두도 아닌 4자리(기준 git 은 exit 128 → 폴백)
N_U=""
for n in 9999 9998 9997 9996 9995 9994 9993 9992 9991 9990; do
  [ -z "$(g "$CL" rev-parse --disambiguate="$n" 2>/dev/null)" ] && { N_U=$n; break; }
done
[ -n "$N_U" ] || setup_fail "충돌 없는 PR 번호를 못 찾았다"
for n in "$N_A" "$N_B" "$N_U"; do
  g "$SEED" push -q "$BASEG" "$P:refs/pull/$n/head" && g "$CL" fetch -q upstream "refs/pull/$n/head:pr-$n" \
    || setup_fail "PR $n ref 준비 실패"
done
g "$CL" reset -q --hard "$C1" || setup_fail "로컬 main 을 stale(C1)로 되돌리기 실패"
# 전제 — 클론에서 N_A · N_B 가 각각 하나의 객체(커밋) 접두이고, 로컬 main 은 원격 추적 ref 보다 뒤다
[ "$(g "$CL" rev-parse --disambiguate="$N_A" 2>/dev/null)" = "$C0" ] || setup_fail "PR 번호 $N_A 가 C0 하나로 풀리지 않는다"
[ "$(g "$CL" rev-parse --disambiguate="$N_B" 2>/dev/null)" = "$X" ] || setup_fail "PR 번호 $N_B 가 X 하나로 풀리지 않는다"
[ -z "$(g "$CL" rev-parse --disambiguate="$N_U" 2>/dev/null)" ] || setup_fail "무충돌 PR 번호 $N_U 가 PR ref 준비 뒤 객체 접두가 됐다"
g "$CL" merge-base --is-ancestor "$C0" main && ! g "$CL" merge-base --is-ancestor "$X" main || setup_fail "C0 조상 · X 비조상 전제 불성립"
[ "$(g "$CL" rev-parse main)" = "$C1" ] && [ "$(g "$CL" rev-parse upstream/main)" = "$C2" ] && [ "$(g "$CL" rev-parse origin/main)" = "$C1" ] \
  || setup_fail "stale 로컬 · 원격 추적 ref 전제 불성립"
case "$(g "$CL" remote get-url upstream) $(g "$CL" remote get-url origin)" in
  /*" "/*) ;; *) setup_fail "원격 URL 이 로컬 경로가 아니다" ;;
esac
# shim 전제(I6) — 실재하지 않는 필드는 거부한다
mkdir -p "$TMP/cells/_probe" && printf '{}\n' > "$TMP/cells/_probe/pr.json"
FZ_GH_SHIM_DIR="$TMP/cells/_probe" FZ_GH_SHIM_PR=1 gh pr view 1 --json baseRepository >/dev/null 2>"$TMP/cells/_probe/err" \
  && setup_fail "shim 이 미지원 필드 baseRepository 를 받았다(I6)"
grep -q 'Unknown JSON field: "baseRepository"' "$TMP/cells/_probe/err" || setup_fail "shim 거부 문구가 실 gh 와 다르다"

echo "INFO  C0=${C0:0:10}(PR $N_A) · X=${X:0:10}(PR $N_B) · 무충돌 PR $N_U · main=${C1:0:7}(stale) · upstream/main=${C2:0:7} · P=${P:0:7}"
echo "INFO  gather: $GATHER"

RAN=""   # 실제로 판정한 셀 이름(판정 줄 `<셀>: …` 의 앞부분) — 끝 줄이 상수가 아니라 돈 셀을 찍는다(F-408)
ran() { case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }
sum_of() { awk -F'\t' '{a+=$1; d+=$2} END{print a+0, d+0}' "$1" 2>/dev/null || echo "? ?"; }

# $1=셀 $2=PR 번호 $3=메타 additions $4=메타 deletions — 셀 폴더에 고정 응답을 쓰고 gather PR 모드를 부른다
run_pr() {
  D="$TMP/cells/$1"
  mkdir -p "$D" && cp "$TMP/pr.diff" "$D/pr.diff" || setup_fail "$1 응답 폴더 실패"
  python3 - "$D/pr.json" "$2" "$3" "$4" "$C2" "$P" <<'PY' || setup_fail "$1 pr.json 실패"
import json, sys
out, n, add, dele, base_oid, head_oid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]
json.dump({
    "number": n, "title": "fixture PR %d" % n, "body": "fixture", "baseRefName": "main", "baseRefOid": base_oid,
    "headRefName": "feature/pr", "headRefOid": head_oid, "isCrossRepository": True,
    "headRepositoryOwner": {"login": "fork-owner"}, "url": "https://github.com/base-owner/base-repo/pull/%d" % n,
    "additions": add, "deletions": dele,
    "files": [
        {"path": "f.txt", "additions": 2, "deletions": 1},
        {"path": "Sources/Legacy Cache.swift", "additions": 0, "deletions": 3},
        {"path": "new/name.txt", "additions": 1, "deletions": 1},
        {"path": "docs/b.txt", "additions": 0, "deletions": 0},
        {"path": "assets/logo.bin", "additions": 0, "deletions": 0},
    ],
}, open(out, "w", encoding="utf-8"))
PY
  (cd "$CL" && FZ_GH_SHIM_DIR="$D" FZ_GH_SHIM_PR="$2" bash "$GATHER" --work-dir "$D/wd" --target "$2") > "$D/out" 2> "$D/err"
  RC=$?
}
assert_gather() {   # $1=셀 — exit 0 · numstat 합 · 완료 줄
  local c="$1" s
  [ "$RC" -eq 0 ] && ok "$c: gather exit 0" || no "$c: gather exit 0" "exit $RC · $(grep -m1 'GATHER-FAIL' "$D/err" | cut -c1-120)"
  s=$(sum_of "$D/wd/numstat.txt")
  if [ -s "$D/wd/numstat.txt" ] && [ "$s" = "3 5" ]; then ok "$c: numstat 합 = patch 계산값 +3 −5"
  else no "$c: numstat 합 = patch 계산값 +3 −5" "numstat.txt $(wc -c < "$D/wd/numstat.txt" 2>/dev/null | tr -d ' ')바이트 · 합 +${s% *} −${s#* }"; fi
  grep -q '^수집 완료 .* / +3 −5 / ' "$D/out" && ok "$c: 완료 줄 +3 −5" \
    || no "$c: 완료 줄 +3 −5" "$(grep -m1 '^수집 완료' "$D/out" | cut -c1-100)"
}
assert_paths() {   # $1=셀 — 삭제 파일 행이 실제 경로로 귀속된다(F-381 · awk 헤더 키잉)
  if awk -F'\t' '$3=="b/Sources/Legacy Cache.swift" && $1=="0" && $2=="3"{h=1} $3=="/dev/null"{n=1} END{exit !(h && !n)}' "$D/wd/numstat.txt" 2>/dev/null; then
    ok "$1: 삭제 파일 행 = 실제 경로 (b/Sources/Legacy Cache.swift 0 3 · '/dev/null' 행 없음)"
  else
    no "$1: 삭제 파일 행 = 실제 경로" "$(tr '\n\t' '; ' < "$D/wd/numstat.txt" 2>/dev/null | cut -c1-160)"
  fi
}
assert_no_warn() {
  if grep -q '^GATHER-WARN: numstat' "$D/err"; then no "$1: 메타 일치 — numstat GATHER-WARN 없음" "$(grep -m1 '^GATHER-WARN: numstat' "$D/err")"
  else ok "$1: 메타 일치 — numstat GATHER-WARN 없음"; fi
}
assert_shim() {
  if [ ! -s "$D/gh-calls.log" ]; then no "$1: gh shim 경유 (호출 ≥1 · 거부 0)" "shim 호출 0 — 다른 gh 로 샜거나 gh 를 안 불렀다"
  elif grep -q '^UNSUPPORTED' "$D/gh-calls.log"; then no "$1: gh shim 경유 (호출 ≥1 · 거부 0)" "$(grep -m1 '^UNSUPPORTED' "$D/gh-calls.log")"
  else ok "$1: gh shim 경유 (호출 $(grep -c '^CALL' "$D/gh-calls.log") · 거부 0)"; fi
}

if want numstat; then
  run_pr numstat-sha-ancestor "$N_A" 3 5
  assert_gather numstat-sha-ancestor; assert_paths numstat-sha-ancestor; assert_no_warn numstat-sha-ancestor; assert_shim numstat-sha-ancestor

  run_pr numstat-sha-inflated "$N_B" 3 5
  assert_gather numstat-sha-inflated; assert_paths numstat-sha-inflated; assert_no_warn numstat-sha-inflated; assert_shim numstat-sha-inflated

  run_pr numstat-meta-mismatch "$N_U" 99 1
  assert_gather numstat-meta-mismatch
  if grep -q '^GATHER-WARN: numstat(+3 −5) ≠ PR 메타(+99 −1)' "$D/err"; then ok "numstat-meta-mismatch: 메타 불일치 → GATHER-WARN (numstat +3 −5 · 메타 +99 −1)"
  else no "numstat-meta-mismatch: 메타 불일치 → GATHER-WARN" "경고 없음 · $(grep -m1 'GATHER-' "$D/err" | cut -c1-100)"; fi
  assert_shim numstat-meta-mismatch

  run_pr numstat-unresolved "$N_U" 3 5
  assert_gather numstat-unresolved; assert_no_warn numstat-unresolved; assert_shim numstat-unresolved

  # 브랜치 모드 — numstat 출처가 diff.patch(awk)로 바뀌어도 git 의 --numstat 과 합이 같다(바이너리 `-` · 개명 `=>`)
  D="$TMP/cells/numstat-branch-binary-rename"; mkdir -p "$D" || setup_fail "branch 셀 폴더 실패"
  g "$CL" branch -q -f feature/pr "$P" || setup_fail "feature/pr 브랜치 실패"
  bns=$(g "$CL" diff --numstat main...feature/pr) || setup_fail "브랜치 git numstat 실패"
  printf '%s\n' "$bns" | awk -F'\t' '$1=="-" && $2=="-"{b=1} $3 ~ /=>/{r=1} END{exit !(b && r)}' \
    || setup_fail "브랜치 diff 에 바이너리 · 개명 행이 없다(전제 불성립)"
  want_b=$(printf '%s\n' "$bns" | awk -F'\t' '{a+=$1; d+=$2} END{print a+0, d+0}')
  (cd "$CL" && bash "$GATHER" --work-dir "$D/wd" --target feature/pr --base main) > "$D/out" 2> "$D/err"
  RC=$?
  [ "$RC" -eq 0 ] && ok "numstat-branch-binary-rename: gather exit 0" \
    || no "numstat-branch-binary-rename: gather exit 0" "exit $RC · $(grep -m1 'GATHER-FAIL' "$D/err" | cut -c1-120)"
  s=$(sum_of "$D/wd/numstat.txt")
  [ "$s" = "$want_b" ] && ok "numstat-branch-binary-rename: numstat 합 = git diff --numstat 합 (+${s% *} −${s#* } · 바이너리 · 개명 포함)" \
    || no "numstat-branch-binary-rename: numstat 합 = git diff --numstat 합" "numstat +${s% *} −${s#* } · git +${want_b% *} −${want_b#* }"
fi

refs_of() { g "$1" for-each-ref --format='%(refname) %(objectname)'; }

if want base; then
  # ── base 묶음 setup — owner/repo 꼴 경로의 bare 2개 · 클론 3개 (전부 준비 실패는 3) ──
  RB="$TMP/b/base-owner/base-repo.git" RF="$TMP/b/fork-owner/base-repo.git"
  { mkdir -p "$TMP/b/base-owner" "$TMP/b/fork-owner" \
    && git init -q --bare -b main "$RB" && git init -q --bare -b main "$RF" \
    && g "$SEED" push -q "$RB" "$C2:refs/heads/main" "$P:refs/pull/$N_U/head" \
    && g "$SEED" push -q "$RF" "$C1:refs/heads/main"; } || setup_fail "base 묶음 bare 원격 실패"
  # $1=클론 $2=upstream URL $3=origin URL $4=refs/pull 을 가진 원격 이름 — 로컬 main = C1(stale) · pr-<N> = P
  mk_clone() {
    git clone -q -o upstream "$2" "$1" && g "$1" remote add origin "$3" && g "$1" fetch -q origin \
      && g "$1" fetch -q "$4" "refs/pull/$N_U/head:pr-$N_U" && g "$1" reset -q --hard "$C1"
  }
  CU="$TMP/b/clone-up" CS="$TMP/b/clone-swap" CT="$TMP/b/clone-stale"
  mk_clone "$CU" "$RB" "$RF" upstream || setup_fail "클론 clone-up 실패"
  mk_clone "$CS" "$RF" "$RB" origin || setup_fail "클론 clone-swap 실패"
  { mk_clone "$CT" "$RB" "$RF" upstream && g "$CT" update-ref refs/remotes/upstream/main "$C1"; } || setup_fail "클론 clone-stale 실패"
  # 전제 — 원격 추적 ref 배치 · 로컬 stale · PR ref · 무충돌 번호 · 원격 URL 이 owner/repo 꼴 로컬 경로
  # $1=클론 $2=기대 upstream/main $3=기대 origin/main
  chk_clone() {
    [ "$(g "$1" rev-parse main)" = "$C1" ] && [ "$(g "$1" rev-parse "pr-$N_U")" = "$P" ] \
      && [ "$(g "$1" rev-parse upstream/main)" = "$2" ] && [ "$(g "$1" rev-parse origin/main)" = "$3" ] \
      && [ -z "$(g "$1" rev-parse --disambiguate="$N_U" 2>/dev/null)" ] || setup_fail "전제 불성립: $(basename "$1")"
  }
  chk_clone "$CU" "$C2" "$C1"; chk_clone "$CS" "$C1" "$C2"; chk_clone "$CT" "$C1" "$C1"
  case "$(g "$CU" remote get-url upstream) $(g "$CS" remote get-url origin) $(g "$CS" remote get-url upstream)" in
    /*/base-owner/base-repo.git" "/*/base-owner/base-repo.git" "/*/fork-owner/base-repo.git) ;;
    *) setup_fail "원격 URL 이 owner/repo 꼴 로컬 경로가 아니다" ;;
  esac
  [ "$(g "$CT" ls-remote --heads upstream main | awk '{print $1}')" = "$C2" ] || setup_fail "clone-stale 의 원격 main 이 C2 가 아니다"
  BASE_URL="https://github.com/base-owner/base-repo/pull/$N_U"

  # $1=셀 $2=클론 $3=PR url $4=baseRefOid [$5…=gather 추가 인자] — 고정 응답(메타 = patch 합 +3 −5)을 쓰고 그 클론에서 gather PR 모드를 부른다
  run_base() {
    D="$TMP/cells/$1" BCL="$2"
    mkdir -p "$D" && cp "$TMP/pr.diff" "$D/pr.diff" || setup_fail "$1 응답 폴더 실패"
    python3 - "$D/pr.json" "$N_U" "$3" "$4" "$P" <<'PY' || setup_fail "$1 pr.json 실패"
import json, sys
out, n, url, base_oid, head_oid = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4], sys.argv[5]
json.dump({
    "number": n, "title": "fixture PR %d" % n, "body": "fixture", "baseRefName": "main", "baseRefOid": base_oid,
    "headRefName": "feature/pr", "headRefOid": head_oid, "isCrossRepository": True,
    "headRepositoryOwner": {"login": "fork-owner"}, "url": url, "additions": 3, "deletions": 5, "files": [],
}, open(out, "w", encoding="utf-8"))
PY
    REFS0=$(refs_of "$BCL") || setup_fail "$1 ref 목록 실패"
    (cd "$BCL" && FZ_GH_SHIM_DIR="$D" FZ_GH_SHIM_PR="$N_U" bash "$GATHER" --work-dir "$D/wd" --target "$N_U" "${@:5}") > "$D/out" 2> "$D/err"
    RC=$?
  }
  # $1=셀 $2=기대 base 이름 $3=기대 merge-base — exit 0 · base-behavior.md 의 선택 · base/ 원본이 그 merge-base 의 내용
  assert_base() {
    local c="$1" got mb n=0 bad="" old
    [ "$RC" -eq 0 ] && ok "$c: gather exit 0" || no "$c: gather exit 0" "exit $RC · $(grep -m1 'GATHER-FAIL' "$D/err" | cut -c1-120)"
    got=$(sed -n 's/^대상 base: `\([^`]*\)`.*/\1/p' "$D/wd/base-behavior.md" 2>/dev/null)
    mb=$(sed -n 's/^대상 base: `[^`]*` (merge-base `\([0-9a-f]*\)`).*/\1/p' "$D/wd/base-behavior.md" 2>/dev/null)
    BMB="$mb"
    [ "$got" = "$2" ] && [ "$mb" = "$3" ] && ok "$c: 선택 base = $2 (merge-base ${3:0:7})" \
      || no "$c: 선택 base = $2 (merge-base ${3:0:7})" "base-behavior.md 대상 base '${got:-없음}' · merge-base '${mb:0:7}'"
    while IFS= read -r old; do
      n=$((n + 1))
      g "$BCL" show "$3:$old" 2>/dev/null | cmp -s - "$D/wd/base/$old" || bad="${bad:+$bad · }$old"
    done < <(awk -F'\t' '$2 != "" {print $2}' "$D/wd/base-manifest.tsv" 2>/dev/null)
    if [ "$n" -gt 0 ] && [ -z "$bad" ]; then ok "$c: base/ 원본 ${n}개 = ${3:0:7} 의 내용"
    else no "$c: base/ 원본 = ${3:0:7} 의 내용" "대상 ${n}개 · 다른 파일: ${bad:-없음} · base/f.txt=$(tr '\n' '|' < "$D/wd/base/f.txt" 2>/dev/null)"; fi
  }
  assert_diff_same_base() {   # base/ 를 뜬 merge-base 와 diff.patch(gh 계산)의 기준이 같다 — F-240 의 증상은 둘이 갈리는 것
    if [ -n "$BMB" ] && g "$BCL" diff "$BMB" "pr-$N_U" 2>/dev/null | cmp -s - "$D/wd/diff.patch"; then
      ok "$1: diff.patch = git diff <base/ 의 merge-base> pr-$N_U (기준 리비전 일치)"
    else
      no "$1: diff.patch = git diff <base/ 의 merge-base> pr-$N_U (기준 리비전 일치)" "merge-base '${BMB:0:7}' 로 계산한 diff 가 gh diff 와 다르다"
    fi
  }
  assert_no_stale_warn() {
    if grep -q '^GATHER-WARN: stale' "$D/err"; then no "$1: baseRefOid 일치 — stale GATHER-WARN 없음" "$(grep -m1 '^GATHER-WARN: stale' "$D/err" | cut -c1-120)"
    else ok "$1: baseRefOid 일치 — stale GATHER-WARN 없음"; fi
  }
  assert_refs_same() {   # gather 는 fetch 하지 않는다 — ref 전체(이름 · 객체)가 전후 같다
    [ "$(refs_of "$BCL")" = "$REFS0" ] && ok "$1: gather 전후 ref 전체 불변 (fetch 0)" || no "$1: gather 전후 ref 전체 불변 (fetch 0)" "gather 가 ref 를 바꿨다"
  }
  assert_note() {   # $1=셀 $2=설명 $3=고정 문자열
    grep -F -q -- "$3" "$D/err" && ok "$1: $2" || no "$1: $2" "기대 '$3' · $(grep -m1 'GATHER-NOTE' "$D/err" | cut -c1-120)"
  }

  run_base base-stale-local "$CU" "$BASE_URL" "$C2"
  assert_base base-stale-local upstream/main "$C2"; assert_diff_same_base base-stale-local
  assert_note base-stale-local "GATHER-NOTE — 기준 저장소 원격 upstream 선택" "원격 'upstream' 이 PR 기준 저장소(base-owner/base-repo)다"
  assert_no_stale_warn base-stale-local; assert_refs_same base-stale-local; assert_shim base-stale-local

  run_base base-upstream-not-base-repo "$CS" "$BASE_URL" "$C2"
  assert_base base-upstream-not-base-repo origin/main "$C2"; assert_diff_same_base base-upstream-not-base-repo
  assert_note base-upstream-not-base-repo "GATHER-NOTE — upstream 이 아니라 URL 이 맞는 origin 선택" "원격 'origin' 이 PR 기준 저장소(base-owner/base-repo)다"
  assert_no_stale_warn base-upstream-not-base-repo; assert_refs_same base-upstream-not-base-repo; assert_shim base-upstream-not-base-repo

  run_base base-tracking-stale "$CT" "$BASE_URL" "$C2"
  assert_base base-tracking-stale upstream/main "$C1"
  w=$(grep -m1 '^GATHER-WARN: stale' "$D/err")
  case "$w" in
    *"upstream/main"*"${C1:0:7}"*"${C2:0:7}"*) ok "base-tracking-stale: GATHER-WARN stale (upstream/main ${C1:0:7} ≠ baseRefOid ${C2:0:7})" ;;
    *) no "base-tracking-stale: GATHER-WARN stale (upstream/main ${C1:0:7} ≠ baseRefOid ${C2:0:7})" "${w:-경고 없음}" ;;
  esac
  assert_refs_same base-tracking-stale
  [ "$(g "$CT" rev-parse upstream/main)" = "$C1" ] && ok "base-tracking-stale: upstream/main = C1 그대로 (fetch 하지 않는다)" \
    || no "base-tracking-stale: upstream/main = C1 그대로" "$(g "$CT" rev-parse --short upstream/main)"
  line=$(grep -m1 '원격보다 뒤' "$D/wd/review-surface.md" 2>/dev/null)
  case "$line" in
    *"${C2:0:7}"*"${C1:0:7}"*) ok "base-tracking-stale: ls-remote 대조 공존 — review-surface.md '원격보다 뒤' (원격 ${C2:0:7} · 로컬 ${C1:0:7})" ;;
    *) no "base-tracking-stale: ls-remote 대조 공존 — review-surface.md '원격보다 뒤'" "${line:-줄 없음}" ;;
  esac
  assert_shim base-tracking-stale

  run_base base-no-match-fallback "$CU" "https://github.com/other-owner/other-repo/pull/$N_U" "$C2"
  assert_base base-no-match-fallback upstream/main "$C2"; assert_diff_same_base base-no-match-fallback
  assert_note base-no-match-fallback "GATHER-NOTE '기준 저장소 대조 실패' → upstream → origin 순회" "GATHER-NOTE: 기준 저장소 대조 실패"
  assert_no_stale_warn base-no-match-fallback; assert_refs_same base-no-match-fallback; assert_shim base-no-match-fallback

  run_base base-prefixed-remote "$CT" "$BASE_URL" "$C2" --base upstream/main
  assert_base base-prefixed-remote upstream/main "$C1"
  assert_note base-prefixed-remote "GATHER-NOTE — 원격 추적 ref 는 원격 선택 생략" "base 'upstream/main' 는 원격 추적 ref 다"
  if grep -qE 'upstream/upstream/main|어느 원격에도' "$D/err"; then
    no "base-prefixed-remote: 사실과 다른 NOTE 없음" "$(grep -m1 -E 'upstream/upstream/main|어느 원격에도' "$D/err" | cut -c1-120)"
  else
    ok "base-prefixed-remote: 사실과 다른 NOTE 없음 ('upstream/upstream/main 미fetch' · '어느 원격에도' 0줄)"
  fi
  w=$(grep -m1 '^GATHER-WARN: stale' "$D/err")
  case "$w" in
    *"upstream/main"*"${C1:0:7}"*"${C2:0:7}"*) ok "base-prefixed-remote: 브랜치 이름으로 오프라인 신선도 대조 — GATHER-WARN stale (${C1:0:7} ≠ ${C2:0:7})" ;;
    *) no "base-prefixed-remote: 브랜치 이름으로 오프라인 신선도 대조 — GATHER-WARN stale" "${w:-경고 없음}" ;;
  esac
  assert_refs_same base-prefixed-remote; assert_shim base-prefixed-remote
fi

if want shim-fields; then
  # $1=셀 — 셀마다 응답 폴더를 따로 둔다(거부 셀의 UNSUPPORTED 기록이 다른 셀로 번지지 않게)
  shim_dir() {
    D="$TMP/cells/$1"
    mkdir -p "$D" && python3 - "$D/pr.json" "$N_U" "$C2" <<'PY' || setup_fail "$1 응답 폴더 실패"
import json, sys
json.dump({"number": int(sys.argv[2]), "baseRefName": "main", "baseRefOid": sys.argv[3],
           "url": "https://github.com/base-owner/base-repo/pull/%s" % sys.argv[2]}, open(sys.argv[1], "w", encoding="utf-8"))
PY
  }
  shim() { FZ_GH_SHIM_DIR="$D" FZ_GH_SHIM_PR="$N_U" gh "$@"; }

  shim_dir shim-fields-real
  out=$(shim pr view "$N_U" --json url,baseRefOid 2>"$D/err"); rc=$?
  q=$(shim pr view "$N_U" --json baseRefOid -q .baseRefOid 2>>"$D/err"); rcq=$?
  if [ "$rc" -eq 0 ] && [ "$rcq" -eq 0 ] && [ "$q" = "$C2" ] \
     && printf '%s' "$out" | python3 -c "import json,sys;d=json.load(sys.stdin);sys.exit(0 if d=={'url':'https://github.com/base-owner/base-repo/pull/$N_U','baseRefOid':'$C2'} else 1)"; then
    ok "shim-fields-real: url · baseRefOid 를 고정 응답 그대로 (--json · -q)"
  else
    no "shim-fields-real: url · baseRefOid 를 고정 응답 그대로 (--json · -q)" "exit $rc/$rcq · $(printf '%s' "$out" | cut -c1-100) · -q=$q · $(head -1 "$D/err")"
  fi
  grep -q '^UNSUPPORTED' "$D/gh-calls.log" && no "shim-fields-real: 실제 필드 요청 거부 0" "$(grep -m1 '^UNSUPPORTED' "$D/gh-calls.log")" \
    || ok "shim-fields-real: 실제 필드 요청 거부 0"

  shim_dir shim-fields-unknown
  shim pr view "$N_U" --json url,baseRepository >/dev/null 2>"$D/err"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q '^Unknown JSON field: "baseRepository"' "$D/err" && grep -q '^UNSUPPORTED Unknown JSON field: "baseRepository"' "$D/gh-calls.log"; then
    ok "shim-fields-unknown: 실재하지 않는 필드 거부 (exit $rc · Unknown JSON field)"
  else
    no "shim-fields-unknown: 실재하지 않는 필드 거부" "exit $rc · $(head -1 "$D/err")"
  fi

  shim_dir shim-fields-absent
  shim pr view "$N_U" --json url,headRefOid >/dev/null 2>"$D/err"; rc=$?
  if [ "$rc" -ne 0 ] && grep -q '지어내지 않는다' "$D/err"; then ok "shim-fields-absent: 고정 응답에 없는 실재 필드는 지어내지 않고 거부 (exit $rc)"
  else no "shim-fields-absent: 고정 응답에 없는 실재 필드는 거부" "exit $rc · $(head -1 "$D/err")"; fi

  run_pr shim-fields-gather "$N_U" 3 5
  req=$(sed -n "s/^CALL pr view $N_U --json \([^ ]*\).*/\1/p" "$D/gh-calls.log" 2>/dev/null | head -1)
  case ",$req," in
    *,url,*) case ",$req," in *,baseRefOid,*) has=1 ;; *) has=0 ;; esac ;;
    *) has=0 ;;
  esac
  [ "$RC" -eq 0 ] && [ "$has" -eq 1 ] && ok "shim-fields-gather: gather --json 요청에 url · baseRefOid ($req)" \
    || no "shim-fields-gather: gather --json 요청에 url · baseRefOid" "exit $RC · 요청 '${req:-없음}'"
  assert_shim shim-fields-gather
fi

[ -n "$RAN" ] || setup_fail "판정한 셀이 0개 — 셀 선택이 아무것도 고르지 않았다(통과로 읽지 않는다)"
want_set=$(for gr in $(printf '%s' "$CELLS" | tr ',' ' '); do expect_of "$gr"; done | tr ' ' '\n' | grep . | LC_ALL=C sort -u)
got_set=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want_set" = "$got_set" ]; then
  echo "PASS  셀 집합: 판정한 셀 = 고른 묶음의 기대 셀 ($(printf '%s\n' "$want_set" | grep -c .)개)"
else
  echo "FAIL  셀 집합: 판정한 셀 ≠ 고른 묶음의 기대 셀  — 빠짐 [$(comm -23 <(printf '%s\n' "$want_set") <(printf '%s\n' "$got_set") | tr '\n' ' ')] · 남음 [$(comm -13 <(printf '%s\n' "$want_set") <(printf '%s\n' "$got_set") | tr '\n' ' ')]"
  fail=$((fail + 1))
fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "GATHER_PR_MODE_OK cells=$CELLS ran=$(printf '%s\n' $RAN | grep -c .)($RAN)"
