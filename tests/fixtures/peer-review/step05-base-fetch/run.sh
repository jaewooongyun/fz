#!/bin/bash
# fz-peer-review Gather Step 0.5 → Step 1 재생 — base(baseRefName)를 받은 뒤 gather 가 원격 쪽 커밋으로 모으는가 (F-253 · DG-11=approve).
#
# ⛔ 네트워크를 쓰지 않는다. 원격은 로컬 bare 저장소(file 경로)이고 `GIT_ALLOW_PROTOCOL=file` 로 다른 전송을 막는다.
#    gh 는 PATH 앞 fixture 고정 응답 shim(이 러너가 임시 폴더에 쓴다 — 미지원 호출 · 필드는 거부하고 기록한다).
#    바깥 git 설정(전역 · 시스템)을 끊는다.
# ⛔ Step 0.5 는 **문서 블록을 그대로 재생**한다 — 트리의 skills/fz-peer-review/SKILL.md `### 0.5.` 절 첫 bash 블록에
#    {PR_NUMBER} 를 넣어 클론 cwd 에서 돈다(FZ_PLUGIN_ROOT=트리). 문서와 실행체가 어긋나면 여기서 드러난다.
#    이어 Step 1 은 트리의 gather.sh 를 PR 모드(--target 7, --base 없음)로 부른다.
# 배치 — 둘 다 로컬 main 이 원격보다 1커밋 뒤(C1)이고 원격 추적 ref 도 C1(마지막 fetch 시점), 원격 main 은 C2,
#      PR 7 head 는 C2 위 커밋 P (원격의 refs/pull/7/head):
#   origin  원격이 origin 하나(bare = base 저장소)
#   fork    upstream = base 저장소 · origin = 갈라진 fork(main 이 C1 에 멈춤) — base 는 upstream 쪽이어야 한다
# 셀:
#   origin · fork              §0.5 블록 → gather PR 모드
#     §0.5 직후 · gather 전: Step 0.5 exit 0 · <원격>/main = C2 · pr-7 = P · 로컬 main = C1 그대로 · HEAD · 작업 트리 불변
#       ⛔ gather 전에 잰다 — §0.5 가 head 만 받고 gather 가 base 를 받는 구현을 gather 뒤 단언은 구별하지 못한다
#     gather 뒤: base/f.txt = C2 내용(로컬 C1 내용 아님) · gather 전후 ref 전체 불변 · gh shim 미지원 호출 0
#   stale-origin · stale-fork  §0.5 없이 gather PR 모드만 — gather 는 fetch 하지 않는다(stale-base 계약)
#     gather exit 0 · ref 전체 불변(<원격>/main = C1 그대로 · pr-7 없음) · 로컬 main · HEAD · 작업 트리 불변 ·
#     stale 경고 유지(review-surface.md '원격보다 뒤' 줄에 원격 C2 · 로컬 C1 sha7 — stale-base fixture 와 같은 줄) · gh shim 미지원 호출 0
#   gh-fail                    fork 배치 · gh 인증 실패(shim 이 `pr view` 에 exit 4) — SKILL.md 'gh 실패 → git 폴백' 경로
#     §0.5 블록 exit 5 · FETCH-PARTIAL(5) · pr-7 = P(head 는 받는다 — 이전 §0.5 와 같다) · upstream/main = C1 그대로(base 이름을
#     모르니 받지 않는다) · 로컬 main · HEAD · 작업 트리 불변
# 끝 — 판정한 셀 집합이 기대 집합(EXPECT)과 정확히 같아야 한다. 셀을 지운 사본은 1(F-408 — 원장 CHECK 는 exit 만 본다)
# 기준 트리(be8c871)는 Step 0.5 가 PR head 만 upstream 에서 받고 gather 가 로컬 main 을 쓰므로(stale 경고도 없다) exit 1.
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 도구 · 임시 저장소)
#   ⛔ 기능 부재(블록이 base 를 안 받음 · gather 가 로컬을 씀)는 단언 실패(1)다 — 준비 실패(3)와 섞지 않는다.
# ⛔ 중첩 가드: 도는 동안 FZ_STEP05_FIXTURE=1. 안에서 다시 불리면 `UNRUN:` 을 내고 exit 2.
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
set -u
if [ -n "${FZ_STEP05_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 step05-base-fetch 가 도는 중"
  exit 2
fi
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
for c in git python3 awk sed; do command -v "$c" >/dev/null 2>&1 || { echo "SETUP $c 부재"; exit 3; }; done
SKILL="$TREE/skills/fz-peer-review/SKILL.md" GATHER="$TREE/skills/fz-peer-review/scripts/gather.sh"
[ -f "$SKILL" ] && [ -f "$GATHER" ] || { echo "SETUP SKILL.md 또는 gather.sh 없음: $TREE"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-step05.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home" "$TMP/shim" || exit 3
: > "$TMP/gitconfig" || exit 3
export HOME="$TMP/home" GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 \
       GIT_ALLOW_PROTOCOL=file FZ_STEP05_FIXTURE=1 FZ_STEP05_PR=7
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CEILING_DIRECTORIES
PR=7

# ── gh shim — 고정 응답. 지원: `pr view 7 --json <필드,…> [-q|--jq .<필드>]` · `pr diff 7` ──
cat > "$TMP/shim/gh" <<'SHIM'
#!/usr/bin/env python3
import json, os, sys
d, pr = os.environ["FZ_STEP05_CELL"], os.environ["FZ_STEP05_PR"]
log = open(os.path.join(d, "gh-calls.log"), "a", encoding="utf-8")
a = sys.argv[1:]
log.write("CALL " + " ".join(a) + "\n")
if os.environ.get("FZ_STEP05_GH_FAIL") and a[:2] == ["pr", "view"]:
    print("To get started with GitHub CLI, please run:  gh auth login", file=sys.stderr)
    sys.exit(4)
# gh pr view --json 이 받는 필드 이름(실재 필드만 — 없는 이름은 실 gh 처럼 거부한다)
KNOWN = set("additions assignees author autoMergeRequest baseRefName baseRefOid body changedFiles closed closedAt "
            "closingIssuesReferences comments commits createdAt deletions files fullDatabaseId headRefName headRefOid "
            "headRepository headRepositoryOwner id isCrossRepository isDraft labels latestReviews maintainerCanModify "
            "mergeCommit mergeStateStatus mergeable mergedAt mergedBy milestone number potentialMergeCommit projectCards "
            "projectItems reactionGroups reviewDecision reviewRequests reviews state statusCheckRollup title updatedAt url".split())


def bad(msg, code=1):
    log.write("UNSUPPORTED " + msg + "\n")
    print("gh-shim: " + msg, file=sys.stderr)
    sys.exit(code)


if a == ["pr", "diff", pr]:
    sys.stdout.write(open(os.path.join(d, "pr.diff"), encoding="utf-8").read())
    sys.exit(0)
if a[:3] == ["pr", "view", pr]:
    fields, jq, i, rest = None, None, 0, a[3:]
    while i < len(rest):
        if rest[i] == "--json" and i + 1 < len(rest):
            fields, i = rest[i + 1].split(","), i + 2
        elif rest[i] in ("-q", "--jq") and i + 1 < len(rest):
            jq, i = rest[i + 1], i + 2
        else:
            bad("미지원 인자 " + rest[i])
    if not fields:
        bad("--json 없음")
    unknown = [f for f in fields if f not in KNOWN]
    if unknown:
        bad('Unknown JSON field: "%s"' % unknown[0])
    vals = json.load(open(os.path.join(d, "pr.json"), encoding="utf-8"))
    out = {f: vals.get(f) for f in fields}
    if jq is None:
        print(json.dumps(out))
        sys.exit(0)
    key = jq[1:] if jq.startswith(".") else ""
    if key in out:
        v = out[key]
        print(v if isinstance(v, str) else json.dumps(v))
        sys.exit(0)
    bad("미지원 --jq " + jq)
bad("미지원 호출 " + " ".join(a))
SHIM
chmod +x "$TMP/shim/gh" || exit 3

# Step 0.5 문서 블록 — `### 0.5.` 절의 첫 ```bash 블록 (없으면 빈 문자열 → 단언 실패)
BLOCK="$(awk '/^### 0\.5\./{s=1;next} s&&/^### /{exit} s&&/^```bash/{f=1;next} s&&f&&/^```/{exit} s&&f' "$SKILL" \
  | sed -e "s/{PR_NUMBER}/$PR/g" -e "s/{PR}/$PR/g")"

fail=0 RAN="" ASSERTS=0
EXPECT="origin fork stale-origin stale-fork gh-fail"
ran() { ASSERTS=$((ASSERTS + 1)); case " $RAN " in *" ${1%%:*} "*) ;; *) RAN="${RAN:+$RAN }${1%%:*}" ;; esac; }
ok() { ran "$1"; echo "PASS  $1"; }
no() { ran "$1"; echo "FAIL  $1  — $2"; fail=$((fail + 1)); }

g() { git -C "$1" "${@:2}"; }
# 클론의 ref 전체(이름 · 객체) — gather 전후 대조용. gather 가 fetch 하면 원격 추적 ref 나 pr-{N} 이 달라진다
refs() { g "$1" for-each-ref --format='%(refname) %(objectname)'; }
# $1=셀 폴더 $2=배치(origin|fork) — 저장소를 만들고 D · CL · REM · C1 · C2 · P · head0 을 정한다
setup() {
  D="$1"; CL="$1/clone" REM=origin
  local lay="$2" BARE="$1/base.git" SEED="$1/seed"
  mkdir -p "$D" || exit 3
  { git init -q --bare -b main "$BARE" && git init -q -b main "$SEED" \
    && g "$SEED" config user.email f@f.f && g "$SEED" config user.name f && g "$SEED" config commit.gpgsign false \
    && printf 'v1\n' > "$SEED/f.txt" && g "$SEED" add -A && g "$SEED" commit -qm C1 && g "$SEED" push -q "$BARE" main \
    && git clone -q "$BARE" "$CL"; } || { echo "SETUP $D 시드 · 클론 실패"; exit 3; }
  if [ "$lay" = fork ]; then
    REM=upstream
    { git clone -q --bare "$BARE" "$D/fork.git" && g "$CL" remote rename origin upstream \
      && g "$CL" remote add origin "$D/fork.git" && g "$CL" fetch -q origin; } || { echo "SETUP $D fork 원격 실패"; exit 3; }
  fi
  { printf 'v2\n' > "$SEED/f.txt" && g "$SEED" commit -qam C2 && g "$SEED" push -q "$BARE" main \
    && g "$SEED" checkout -q -b pr && printf 'v2\npr\n' > "$SEED/f.txt" && g "$SEED" commit -qam P \
    && g "$SEED" push -q "$BARE" "pr:refs/pull/$PR/head" && g "$SEED" diff main pr > "$D/pr.diff"; } \
    || { echo "SETUP $D 원격 전진 실패"; exit 3; }
  C1=$(g "$CL" rev-parse main) && C2=$(g "$SEED" rev-parse main) && P=$(g "$SEED" rev-parse pr) || exit 3
  [ "$(g "$CL" rev-parse "$REM/main")" = "$C1" ] && [ "$C1" != "$C2" ] || { echo "SETUP $D 전제 불성립 — 클론이 이미 최신"; exit 3; }
  printf '{"baseRefName":"main","baseRefOid":"%s","headRefName":"feature/pr-%s","headRefOid":"%s","number":%s,"title":"fixture PR","body":"fixture","additions":1,"deletions":0,"files":[{"path":"f.txt","additions":1,"deletions":0}],"url":"https://github.com/fixture-owner/fixture-repo/pull/%s","isCrossRepository":false}\n' \
    "$C2" "$PR" "$P" "$PR" "$PR" > "$D/pr.json" || exit 3
  head0=$(g "$CL" symbolic-ref -q HEAD) || exit 3
}
# $1=셀 이름 $2=기대 로컬 main — 로컬 main · HEAD · 작업 트리 불변 (pull·merge 아님)
local_same() {
  if [ "$(g "$CL" rev-parse main)" = "$2" ] && [ "$(g "$CL" symbolic-ref -q HEAD)" = "$head0" ] && [ -z "$(g "$CL" status --porcelain)" ]; then
    ok "$1"
  else
    no "$1" "main=$(g "$CL" rev-parse --short main) · HEAD=$(g "$CL" symbolic-ref -q HEAD) · 작업 트리 $(g "$CL" status --porcelain | wc -l | tr -d ' ')줄"
  fi
}
gather() { (cd "$CL" && FZ_STEP05_CELL="$D" PATH="$TMP/shim:$PATH" bash "$GATHER" --work-dir "$D/wd" --target "$PR") > "$D/gather.out" 2>&1; }
shim_clean() {
  if grep -q '^UNSUPPORTED' "$D/gh-calls.log" 2>/dev/null; then
    no "$1: gh shim 미지원 호출 0" "$(grep -m1 '^UNSUPPORTED' "$D/gh-calls.log")"
  else
    ok "$1: gh shim 미지원 호출 0"
  fi
}

# $1=셀 이름 $2=배치 — Step 0.5 문서 블록 → (gather 전 단언) → gather PR 모드 → (gather 후 단언)
cell() {
  local c="$1" rc5 rcg r0
  setup "$TMP/$1" "$2"
  if [ -n "$BLOCK" ]; then
    (cd "$CL" && FZ_STEP05_CELL="$D" FZ_PLUGIN_ROOT="$TREE" PATH="$TMP/shim:$PATH" bash -c "$BLOCK") > "$D/step05.out" 2>&1
    rc5=$?
  else
    rc5=127; echo "(### 0.5. 절에 bash 블록 없음)" > "$D/step05.out"
  fi
  # ── §0.5 직후 · gather 전 — base 를 받는 책임은 §0.5 에 있다. §0.5 가 head 만 받고 gather 가 base 를 받는
  #    구현은 여기서 <원격>/main = C1 로 드러난다(gather 뒤에 재면 둘을 구별하지 못한다)
  [ "$rc5" -eq 0 ] && ok "$c: Step 0.5 블록 exit 0" || no "$c: Step 0.5 블록 exit 0" "exit $rc5 · $(tail -1 "$D/step05.out" | cut -c1-120)"
  [ "$(g "$CL" rev-parse -q --verify "$REM/main")" = "$C2" ] && ok "$c: §0.5 직후(gather 전) $REM/main = 원격 C2" \
    || no "$c: §0.5 직후(gather 전) $REM/main = 원격 C2" "$(g "$CL" rev-parse --short "$REM/main" 2>/dev/null) · 기대 ${C2:0:7}"
  [ "$(g "$CL" rev-parse -q --verify "pr-$PR")" = "$P" ] && ok "$c: §0.5 직후(gather 전) pr-$PR = PR head" \
    || no "$c: §0.5 직후(gather 전) pr-$PR = PR head" "$(g "$CL" rev-parse --short "pr-$PR" 2>/dev/null || echo 없음)"
  local_same "$c: §0.5 직후(gather 전) 로컬 main · HEAD · 작업 트리 불변 (pull·merge 아님)" "$C1"
  r0=$(refs "$CL")
  gather; rcg=$?
  if [ "$rcg" -eq 0 ] && [ "$(cat "$D/wd/base/f.txt" 2>/dev/null)" = "v2" ]; then
    ok "$c: gather base/f.txt = 원격 쪽 C2 내용"
  else
    no "$c: gather base/f.txt = 원격 쪽 C2 내용" "gather exit $rcg · base/f.txt=$(tr '\n' '|' 2>/dev/null < "$D/wd/base/f.txt" || echo 없음) · $(grep -m1 -E 'GATHER-(NOTE|WARN|FAIL)' "$D/gather.out" | cut -c1-100)"
  fi
  [ "$(refs "$CL")" = "$r0" ] && ok "$c: gather 전후 ref 전체 불변" || no "$c: gather 전후 ref 전체 불변" "gather 가 ref 를 바꿨다"
  shim_clean "$c"
}

# $1=셀 이름 $2=배치 — §0.5 없이 gather PR 모드만. gather 는 fetch 하지 않는다(stale-base 계약) —
#   원격 추적 ref 는 1커밋 뒤 그대로 남고, gather 는 그 stale 을 review-surface.md 경고로 알린다
stale_cell() {
  local c="$1" rcg r0 line
  setup "$TMP/$1" "$2"
  r0=$(refs "$CL")
  gather; rcg=$?
  [ "$rcg" -eq 0 ] && ok "$c: §0.5 없이 gather exit 0" || no "$c: §0.5 없이 gather exit 0" "exit $rcg · $(grep -m1 -E 'GATHER-(NOTE|WARN|FAIL)' "$D/gather.out" | cut -c1-100)"
  if [ "$(refs "$CL")" = "$r0" ] && [ "$(g "$CL" rev-parse -q --verify "$REM/main")" = "$C1" ] && ! g "$CL" rev-parse -q --verify "pr-$PR" >/dev/null; then
    ok "$c: gather 뒤 ref 전체 불변 ($REM/main = C1 그대로 · pr-$PR 없음)"
  else
    no "$c: gather 뒤 ref 전체 불변" "$REM/main=$(g "$CL" rev-parse --short "$REM/main" 2>/dev/null) · 기대 ${C1:0:7} · pr-$PR=$(g "$CL" rev-parse --short "pr-$PR" 2>/dev/null || echo 없음)"
  fi
  local_same "$c: gather 뒤 로컬 main · HEAD · 작업 트리 불변" "$C1"
  line=$(grep -m1 '원격보다 뒤' "$D/wd/review-surface.md" 2>/dev/null)
  case "$line" in
    *"${C2:0:7}"*"${C1:0:7}"*) ok "$c: stale 경고 유지 (review-surface.md '원격보다 뒤' · 원격 ${C2:0:7} · 로컬 ${C1:0:7})" ;;
    *) no "$c: stale 경고 유지 (review-surface.md '원격보다 뒤' · 원격 C2 · 로컬 C1 sha7)" "${line:-경고 없음}" ;;
  esac
  shim_clean "$c"
}

# $1=셀 이름 $2=배치 — gh 인증 실패에서 §0.5 블록만. head 는 받고 base 는 받지 않았다고 exit 5 로 알린다
gh_fail_cell() {
  local c="$1" rc5
  setup "$TMP/$1" "$2"
  (cd "$CL" && FZ_STEP05_CELL="$D" FZ_STEP05_GH_FAIL=1 FZ_PLUGIN_ROOT="$TREE" PATH="$TMP/shim:$PATH" bash -c "${BLOCK:-exit 127}") > "$D/step05.out" 2>&1
  rc5=$?
  [ "$rc5" -eq 5 ] && grep -q '^FETCH-PARTIAL(5)' "$D/step05.out" && ok "$c: gh 실패 → Step 0.5 exit 5 · FETCH-PARTIAL(5)" \
    || no "$c: gh 실패 → Step 0.5 exit 5 · FETCH-PARTIAL(5)" "exit $rc5 · $(tail -1 "$D/step05.out" | cut -c1-120)"
  [ "$(g "$CL" rev-parse -q --verify "pr-$PR")" = "$P" ] && ok "$c: gh 실패여도 pr-$PR = PR head (git 폴백 경로)" \
    || no "$c: gh 실패여도 pr-$PR = PR head (git 폴백 경로)" "$(g "$CL" rev-parse --short "pr-$PR" 2>/dev/null || echo 없음)"
  [ "$(g "$CL" rev-parse -q --verify "$REM/main")" = "$C1" ] && ok "$c: $REM/main = C1 그대로 (base 이름을 모르니 받지 않는다)" \
    || no "$c: $REM/main = C1 그대로" "$(g "$CL" rev-parse --short "$REM/main" 2>/dev/null) · 기대 ${C1:0:7}"
  local_same "$c: 로컬 main · HEAD · 작업 트리 불변 (pull·merge 아님)" "$C1"
}

cell origin origin
cell fork fork
stale_cell stale-origin origin
stale_cell stale-fork fork
gh_fail_cell gh-fail fork

want_set=$(printf '%s\n' $EXPECT | LC_ALL=C sort -u) got_set=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ -n "$RAN" ] && [ "$want_set" = "$got_set" ]; then
  echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' $EXPECT | grep -c .)개)"
else
  echo "FAIL  셀 집합: 판정한 셀 [${RAN:-없음}] ≠ 기대 셀 [$EXPECT]"; fail=$((fail + 1))
fi
echo
echo "$fail 건 실패"
[ "$fail" -eq 0 ] || exit 1
echo "STEP05_BASE_FETCH_OK cells=$(printf '%s\n' $RAN | grep -c .)($RAN) · 단언 $ASSERTS"
