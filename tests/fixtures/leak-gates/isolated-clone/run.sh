#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 읽지 않는다. 격리 clone 스크립트를 임시 저장소에서 돌려 종료 코드 · 출력 줄(고정 글자) · git 설정 값 · 커밋의 신원 칸만 본다
# modes: default caller=health
# 격리 clone 스크립트(scripts/isolated_clone.sh) 회귀 — 트리의 스크립트를 직접 실행한다. 원본은 mktemp 아래 임시 저장소(커밋 둘 · 주석
#   태그 · 가벼운 태그 · 커밋한 시험용 커밋 훅)이고 clone 도 그 아래에 만든다. 스크립트는 신원 판정을 트리의 누수 규칙 정본에 넘긴다.
# ⛔ 전역 신원이 회사 메일인 환경은 GIT_CONFIG_GLOBAL 임시 파일로만 흉내 낸다(사용자 전역 설정 · 시스템 설정은 읽지 않는다). 대조: 같은
#    환경에서 스크립트 없이 git clone 한 clone 은 커밋이 전역(회사) 이름 · 메일로 찍히고 원본 태그가 따라와야 한다 — 아니면 흉내가
#    실패해 셀이 판별력을 잃는다(준비 실패)
# ⛔ 신원 환경 변수(GIT_AUTHOR_* · GIT_COMMITTER_* · EMAIL)와 git 설정 주입 변수는 처음에 걷는다 — 저장소 설정보다 앞서서, 남으면 clone
#    의 커밋이 그 값으로 찍혀 셀이 clone 설정을 재지 못한다. 원본 · 음성 커밋을 만드는 git 만 그 명령에 한해 신원을 받는다
# ⛔ 음성 셀은 대조(원본 A · 그 clone)와 한 가지만 다르다 — 환경 변수 하나 · 원본 로컬 설정 하나(돌린 뒤 되돌린다) · 전역 설정 파일 하나 ·
#    clone 커밋의 신원 칸 하나
# ⛔ 음성 토큰(회사 꼴 메일)은 쪼개 적고 실행할 때 잇는다 — 이 파일이 누수 규칙 · 커밋 훅에 걸리지 않게. 비공개 규칙 파일은 원본 밖에 둔다
# 셀(기대 exit):
#   0    corp-global-commit-noreply(clone 커밋의 이름 · author · committer = 원본 로컬 값) · hookspath-clone-githooks(원본 로컬 값이 없으면
#        core.hooksPath=.githooks · 커밋 때 그 clone 의 .githooks 훅이 돈다) · use-config-only-true · maintainer-keys-copied
#        (fz.neutralizeRules 의 상대 경로는 원본 작업 트리 기준 절대 경로) · no-tags-copied(원본 태그 둘 · 태그 추적 끔)
#   0·2  hookspath-origin-mapped(원본 작업 트리 안의 절대 경로 → clone 안의 같은 자리 · 원본이 정한 훅 폴더가 clone 에 없으면 2)
#   2    ident-config-override-exit2(전역 author.email — 설정을 건 clone 의 결과 신원이 원본 로컬 메일이 아니다) ·
#        env-override-corp-exit2(GIT_AUTHOR_EMAIL · GIT_COMMITTER_EMAIL · EMAIL · '@' 든 GIT_COMMITTER_NAME — 만들지 않는다 · 대조:
#        noreply env 는 0) · origin-identity-exit2(원본 로컬 user.email 이 회사 꼴 · 없음 — 전역은 회사 메일) · args-exit2
#   check-fetch  check-fetch-clean-exit0 · check-fetch-corp-author-exit1 · check-fetch-corp-committer-exit1 ·
#        check-fetch-no-origin-identity-exit2(전역은 회사 메일) · check-fetch-empty-range-exit2(새 커밋 없는 clone) — 2 는 끝 줄
#        ISOLATED_CLONE_FETCH_UNRUN 까지 본다
# 출력: 셀마다 `PASS <셀>` 또는 `FAIL <셀> — 사유` + 그 셀이 돌린 스크립트 · git 출력의 끝 20줄(들여씀). 전건 통과면 `ISOLATED_CLONE_OK …`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — 인자 · 도구 · 대상 부재 · 임시 저장소 · 대조 실패)
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 러너가 든 트리 — health-check 는 인자 없이 부른다)
set -u
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "UNRUN: --tree 에 경로가 없다"; exit 2; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "UNRUN: --tree 경로가 없다: $2"; exit 2; }; shift 2 ;;
    *) echo "UNRUN: 알 수 없는 인자: $1 (사용: run.sh [--tree <플러그인 트리>])"; exit 2 ;;
  esac
done
[ -n "$TREE" ] || { echo "UNRUN: 플러그인 트리를 정하지 못했다"; exit 2; }
for c in git python3; do command -v "$c" >/dev/null 2>&1 || { echo "UNRUN: $c 부재 — 픽스처를 만들 수 없다"; exit 2; }; done
for s in isolated_clone.sh leak_rules.py; do
  [ -f "$TREE/scripts/$s" ] || { echo "UNRUN: 대상 부재 — scripts/$s"; exit 2; }
done
IC="$TREE/scripts/isolated_clone.sh"

# 바깥 git 환경(훅이 건 GIT_DIR 등) · git 설정 주입(-c 가 남긴 env) · 신원 환경 변수 · 비공개 규칙 env 를 끊는다
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE GIT_PREFIX \
  GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT FZ_NEUTRALIZE_RULES GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL EMAIL
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-isoclone.XXXXXX")" && [ -n "$WORK" ] && [ -d "$WORK" ] \
  || { echo "UNRUN: 임시 폴더를 만들지 못했다"; exit 2; }
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/out" "$WORK/tmp" "$WORK/xdg" || { echo "UNRUN: 임시 폴더 준비 실패"; exit 2; }
# 합성 신원(신원 정책의 허용 꼴 noreply)과 회사 꼴 전역 신원 — 회사 꼴 메일은 실행할 때 잇는다. 둘째 전역 파일은 author.email 하나만 더 둔다
SID="0+fz-isoclone@users.noreply.github.com"
CORPN="qziso""corp"; CORPM="dev@${CORPN}.test"
GCORP="$WORK/gitconfig-corp" GAUTH="$WORK/gitconfig-corp-author"
{ printf '[user]\n\tname = %s\n\temail = %s\n' "$CORPN dev" "$CORPM" > "$GCORP" \
    && printf '[user]\n\tname = %s\n\temail = %s\n[author]\n\temail = %s\n' "$CORPN dev" "$CORPM" "$CORPM" > "$GAUTH"; } \
  || { echo "UNRUN: 전역 설정 임시 파일을 만들지 못했다"; exit 2; }
# 이 러너의 git 과 스크립트 · 정본 · 훅이 부르는 git 모두 이 전역 파일만 읽는다(시스템 설정 · 기본 무시 · 속성 파일(XDG)은 끊는다).
#   바이트코드를 쓰지 않는다. 임시 파일도 WORK 안이다
export GIT_CONFIG_GLOBAL="$GCORP" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$WORK" \
  XDG_CONFIG_HOME="$WORK/xdg" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 TMPDIR="$WORK/tmp"

npass=0 nfail=0 WHY="" SHOW="" RUNL="" RC="" OUT="" O="" GX_AMAIL="" GX_CMAIL=""
die() { echo "UNRUN: 픽스처 준비 실패 — $* (⛔ 통과 아님)"; exit 2; }
# 원본 · 음성 커밋을 만드는 git — 훅 · 서명을 끄고 신원은 그 명령에만 준다(GX_AMAIL · GX_CMAIL — 빈 값 = 합성 noreply)
gx() {
  GIT_AUTHOR_NAME=fz-isoclone GIT_AUTHOR_EMAIL="${GX_AMAIL:-$SID}" GIT_COMMITTER_NAME=fz-isoclone GIT_COMMITTER_EMAIL="${GX_CMAIL:-$SID}" \
    git -c core.hooksPath=/dev/null -c commit.gpgsign=false -c tag.gpgsign=false "$@"
}
# 실패면 준비 실패(exit 2). ⛔ $( ) 안에서 부르지 않는다 — exit 가 서브셸에 갇힌다
gi() { gx "$@" >/dev/null 2>&1 || die "git $*"; }
# clone 안의 평범한 git — 신원 env 없이, 훅도 clone 설정 그대로 둔다(clone 의 설정이 정한다). 서명만 끈다
cg() { local d="$1"; shift; git -C "$d" -c commit.gpgsign=false "$@"; }
# 로컬 설정 값 하나(없으면 빈 출력) — $1=저장소 · $2=키 · $3=형식(--bool 등 · 빈 값 = 그대로)
cfgv() { git -C "$1" config --local ${3:-} --get "$2" 2>/dev/null; }
origin_repo() {   # $1=폴더 — 전역 O 에 원본: 시험용 커밋 훅 · 커밋 둘 · 주석 태그 v1.0.0 · 가벼운 태그 v1.1.0. 로컬 신원 · 유지관리자 설정은 셀이 건다
  O="$1"
  gi -c init.defaultBranch=main init -q "$O"
  [ -d "$O/.git" ] || die "원본 저장소가 만들어지지 않았다: ${O#$WORK/}"
  gi -C "$O" config core.fileMode true
  mkdir -p "$O/.githooks" || die "mkdir .githooks"
  # 시험용 커밋 훅 — 이 훅 파일이 든 폴더의 실제 경로를 그 저장소 git 폴더의 표지 파일에 적는다(어느 clone 의 훅이 돌았는지 가른다)
  printf '%s\n' '#!/bin/bash' 'printf "%s\n" "$(cd "$(dirname "$0")" && pwd -P)" >> "$(git rev-parse --git-dir)/fz-hook-ran"' 'exit 0' \
    > "$O/.githooks/pre-commit" && chmod 755 "$O/.githooks/pre-commit" || die "시험용 커밋 훅"
  printf 'a\n' > "$O/a.md" || die "쓰기 a.md"
  gi -C "$O" add -A
  gi -C "$O" commit -qm "첫 커밋"
  gi -C "$O" tag -a -m "v1.0.0 출하" v1.0.0
  printf 'b\n' > "$O/b.md" || die "쓰기 b.md"
  gi -C "$O" add -A
  gi -C "$O" commit -qm "둘째 커밋"
  gi -C "$O" tag v1.1.0
}
ic() {   # $1=출력 이름 · 나머지=스크립트 인자 — 트리의 스크립트를 직접 실행한다(cwd = WORK). 출력 OUT · 종료 코드 RC
  local name="$1"; shift
  OUT="$WORK/out/$name.txt"; SHOW="$SHOW$OUT"$'\n'
  (cd "$WORK" && bash "$IC" "$@") > "$OUT" 2>&1
  RC=$?
}
ic_env() {   # $1=출력 이름 · $2=환경 변수 이름 · $3=값 · 나머지=스크립트 인자 — 그 환경 변수 하나만 더하거나 바꿔 실행한다
  local name="$1" var="$2" val="$3"; shift 3
  OUT="$WORK/out/$name.txt"; SHOW="$SHOW$OUT"$'\n'
  (cd "$WORK" && export "$var=$val" && bash "$IC" "$@") > "$OUT" 2>&1
  RC=$?
}
want() {   # $1=기대 exit · 나머지=출력(OUT)에 있어야 할 글자(앞이 '!' 면 없어야 할 글자) — 어긋남은 WHY 에 덧붙인다
  local rc="$1" n; shift
  [ "$RC" = "$rc" ] || WHY="$WHY · ${RUNL:+$RUNL }exit $RC (기대 $rc)"
  for n in "$@"; do
    case "$n" in
      '!'*) ! /usr/bin/grep -qF -- "${n#!}" "$OUT" || WHY="$WHY · ${RUNL:+$RUNL }없어야 할 줄: ${n#!}" ;;
      *) /usr/bin/grep -qF -- "$n" "$OUT" || WHY="$WHY · ${RUNL:+$RUNL }없는 줄: $n" ;;
    esac
  done
}
verdict() {   # $1=셀 — WHY 가 비었으면 PASS · 아니면 FAIL + 사유 + 그 셀이 돌린 출력의 끝 20줄. WHY · SHOW · RUNL 을 비운다
  if [ -z "$WHY" ]; then
    echo "PASS $1"; npass=$((npass + 1))
  else
    echo "FAIL $1 —${WHY# ·}"; nfail=$((nfail + 1))
    printf '%s' "$SHOW" | while IFS= read -r f; do
      [ -f "$f" ] || continue
      echo "    ── ${f##*/}"; tail -n 20 "$f" | sed 's/^/    /'
    done
  fi
  WHY="" SHOW="" RUNL=""
}

# ── 원본 A(대조) — 로컬 신원(합성 noreply · 이름) · 유지관리자 표지 · 비공개 규칙(원본 밖 · 원본 작업 트리 기준 상대 경로) ──
mkdir -p "$WORK/a" || die "mkdir a"
RULES_A="$WORK/a/rules-corp.txt"
printf '%s\n' '# 합성 비공개 규칙(시험용) — 한 줄 한 정규식' "(?i)$CORPN" > "$RULES_A" || die "규칙 파일"
origin_repo "$WORK/a/orig"; OA="$O"
gi -C "$OA" config user.name fz-isoclone
gi -C "$OA" config user.email "$SID"
gi -C "$OA" config fz.maintainer true
gi -C "$OA" config fz.neutralizeRules ../rules-corp.txt
OT="$(git -C "$OA" tag -l | wc -l | tr -d ' ')"
[ "$OT" = 2 ] || die "원본 태그가 2개가 아니다(${OT})"

# 대조 — 같은 환경에서 스크립트 없이 만든 clone: 커밋이 전역(회사) 이름 · 메일로 찍히고 원본 태그가 따라온다
PL="$WORK/a/plain"
git -c core.hooksPath=/dev/null clone -q --no-hardlinks "$OA" "$PL" >/dev/null 2>&1 || die "대조 clone"
printf 'p\n' > "$PL/p.md" || die "쓰기 p.md"
git -C "$PL" add -A >/dev/null 2>&1 || die "대조 add"
git -C "$PL" -c core.hooksPath=/dev/null -c commit.gpgsign=false commit -qm "대조 커밋" >/dev/null 2>&1 || die "대조 커밋"
PL_ID="$(git -C "$PL" log -1 --format='%an|%ae|%ce' 2>/dev/null)"
[ "$PL_ID" = "$CORPN dev|$CORPM|$CORPM" ] \
  || die "대조 실패 — 스크립트 없이 만든 clone 의 커밋이 전역(회사) 신원으로 찍히지 않았다: 전역 신원이 회사 메일인 환경을 흉내 내지 못했다"
PL_T="$(git -C "$PL" tag -l | wc -l | tr -d ' ')"
[ "$PL_T" = 2 ] || die "대조 실패 — 스크립트 없이 만든 clone 에 원본 태그가 따라오지 않았다(${PL_T}개) — 태그 셀이 판별력을 잃는다"

# ── 만들기 — 전역 신원이 회사 메일인 환경 · 신원 env 없음. clone 에서 신원 env 없이 커밋한다 ──
CA="$WORK/a/dest/clone"
ic a.make "$OA" "$CA"; A_OUT="$OUT"; A_RC="$RC"
CA_OK=0 CLEAN1=""
want 0 "ISOLATED_CLONE_READY dest=" " core.hooksPath=.githooks fz-keys=2 tags=0" "!UNRUN:" "!NOTE:"
if [ "$A_RC" = 0 ] && [ -d "$CA/.git" ]; then
  CA_OK=1
  printf 'c\n' > "$CA/c.md" || die "쓰기 c.md"
  cg "$CA" add c.md >/dev/null 2>&1 || die "clone add"
  SHOW="$SHOW$WORK/out/a.commit.txt"$'\n'
  if cg "$CA" commit -qm "clone 커밋" > "$WORK/out/a.commit.txt" 2>&1; then
    CLEAN1="$(cg "$CA" rev-parse HEAD 2>/dev/null)"
    ID="$(cg "$CA" log -1 --format='%an|%ae|%ce' 2>/dev/null)"
    [ "$ID" = "fz-isoclone|$SID|$SID" ] || WHY="$WHY · clone 커밋의 이름 · author · committer 가 원본 로컬 값이 아니다($ID)"
  else
    WHY="$WHY · clone 에서 신원 env 없이 한 커밋이 실패했다"
  fi
else
  WHY="$WHY · 스크립트가 clone 을 만들지 못했다"
fi
verdict corp-global-commit-noreply

# core.hooksPath 는 상대 경로 .githooks — 위 커밋에서 그 clone 자신의 .githooks 훅이 돌았다(원본 쪽 훅이 아니다)
SHOW="$A_OUT"$'\n'
HP="$(cfgv "$CA" core.hooksPath)"
[ "$HP" = .githooks ] || WHY="$WHY · clone 의 core.hooksPath 가 .githooks 가 아니다(${HP:-(없음)})"
WANT_HD="$(cd "$CA/.githooks" 2>/dev/null && pwd -P)"
GOT_HD="$(head -n 1 "$CA/.git/fz-hook-ran" 2>/dev/null)"
[ -n "$WANT_HD" ] && [ "$GOT_HD" = "$WANT_HD" ] \
  || WHY="$WHY · 커밋 때 그 clone 의 .githooks 훅이 돌지 않았다(표지 ${GOT_HD:-(없음)} · 기대 ${WANT_HD:-(clone 에 .githooks 없음)})"
verdict hookspath-clone-githooks

SHOW="$A_OUT"$'\n'
UC="$(cfgv "$CA" user.useConfigOnly --bool)"
[ "$UC" = true ] || WHY="$WHY · clone 의 user.useConfigOnly 가 참이 아니다(${UC:-(없음)})"
verdict use-config-only-true

# 유지관리자 설정 — 표지는 값 그대로, 비공개 규칙 경로는 원본 작업 트리 기준 절대 경로(clone 기준 상대 경로 자리에는 파일이 없다)
SHOW="$A_OUT"$'\n'
[ ! -e "$WORK/a/dest/rules-corp.txt" ] || die "대조 실패 — clone 기준 상대 경로에도 규칙 파일이 있어 경로 변환을 가르지 못한다"
MK="$(cfgv "$CA" fz.maintainer)"
NR="$(cfgv "$CA" fz.neutralizeRules)"
[ "$MK" = true ] || WHY="$WHY · clone 의 fz.maintainer 가 원본 값이 아니다(${MK:-(없음)})"
case "$NR" in
  /*) cmp -s "$NR" "$RULES_A" || WHY="$WHY · clone 의 fz.neutralizeRules 가 원본의 비공개 규칙 파일을 가리키지 않는다($NR)" ;;
  *) WHY="$WHY · clone 의 fz.neutralizeRules 가 절대 경로가 아니다(${NR:-(없음)}) — 원본 작업 트리 기준 상대 경로를 그대로 옮기면 clone 기준으로 풀린다" ;;
esac
verdict maintainer-keys-copied

# 태그 — 원본 태그 둘이 clone 에 없고(대조: 스크립트 없는 clone 에는 따라왔다) 다음 fetch 도 태그를 따라 받지 않는다
OUT="$A_OUT" RC="$A_RC"; SHOW="$A_OUT"$'\n'
want 0 " tags=0"
CT="$(git -C "$CA" for-each-ref --format='%(refname)' refs/tags 2>/dev/null | wc -l | tr -d ' ')"
[ "$CT" = 0 ] || WHY="$WHY · clone 에 태그가 ${CT}개 남았다(원본 ${OT}개)"
TO="$(cfgv "$CA" remote.origin.tagOpt)"
[ "$TO" = "--no-tags" ] || WHY="$WHY · clone 의 remote.origin.tagOpt 가 --no-tags 가 아니다(${TO:-(없음)}) — 다음 fetch 가 태그를 따라 받는다"
verdict no-tags-copied

# ── 원본 로컬 core.hooksPath — 원본 작업 트리 안의 절대 경로(심볼릭 링크를 풀기 전 꼴)는 clone 안의 같은 자리로 옮긴다 · 원본이 정한
#    훅 폴더가 clone 에 없으면 만든 clone 을 쓰지 않는다. 원본 A 의 그 키 하나만 바꿔 돌리고 되돌린다 ──
mkdir -p "$WORK/h" || die "mkdir h"
gi -C "$OA" config core.hooksPath "$OA/.githooks"
RUNL="원본 절대 경로:"; ic h.abs "$OA" "$WORK/h/abs"
want 0 "ISOLATED_CLONE_READY dest=" " core.hooksPath=.githooks " "!UNRUN:"
HPA="$(cfgv "$WORK/h/abs" core.hooksPath)"
[ "$HPA" = .githooks ] || WHY="$WHY · 원본 절대 경로: clone 의 core.hooksPath 가 그 clone 안의 .githooks 가 아니다(${HPA:-(없음)})"
gi -C "$OA" config core.hooksPath hooks-alt
RUNL="원본 상대 경로 · clone 에 그 폴더 없음:"; ic h.missing "$OA" "$WORK/h/missing"
gi -C "$OA" config --unset core.hooksPath
want 2 "UNRUN: clone 에 커밋 훅 폴더가 없다" "ISOLATED_CLONE_UNRUN dest=" "!ISOLATED_CLONE_READY"
RUNL=""; verdict hookspath-origin-mapped

# ── 결과 신원 — 전역 설정의 author.email 은 저장소 user.email 보다 앞선다. 신원 env 검사로는 보이지 않아 설정을 건 clone 의 결과 신원을
#    잰다(만든 clone 을 쓰지 않는다). 대조: author.email 만 없는 같은 전역에서 만든 위 clone 은 0 이다 ──
mkdir -p "$WORK/ident" || die "mkdir ident"
RUNL="전역 author.email:"; ic_env ident.author GIT_CONFIG_GLOBAL "$GAUTH" "$OA" "$WORK/ident/author"
want 2 "UNRUN: clone 의 커밋 author 메일이 원본 로컬 user.email 이 아니다" "ISOLATED_CLONE_UNRUN dest=" "!ISOLATED_CLONE_READY"
RUNL=""; verdict ident-config-override-exit2

# ── 신원 환경 변수 — 저장소 설정보다 앞선다. 회사 꼴이면 만들지 않는다 · 대조: noreply env 는 만든다 ──
mkdir -p "$WORK/env" || die "mkdir env"
for v in GIT_AUTHOR_EMAIL GIT_COMMITTER_EMAIL EMAIL; do
  RUNL="$v:"; ic_env "env.$v" "$v" "$CORPM" "$OA" "$WORK/env/$v"
  want 2 "UNRUN: 환경 변수 $v " "ISOLATED_CLONE_UNRUN — clone 을 만들지 않았다" "!ISOLATED_CLONE_READY"
  [ ! -e "$WORK/env/$v" ] || WHY="$WHY · $v: 막는다면서 clone 을 만들었다"
done
RUNL="GIT_COMMITTER_NAME:"; ic_env env.name GIT_COMMITTER_NAME "$CORPN dev <$CORPM>" "$OA" "$WORK/env/name"
want 2 "UNRUN: 환경 변수 GIT_COMMITTER_NAME " "!ISOLATED_CLONE_READY"
[ ! -e "$WORK/env/name" ] || WHY="$WHY · GIT_COMMITTER_NAME: 막는다면서 clone 을 만들었다"
# 대조 — env 가 있다는 것만으로 막지 않는다. 이 clone(새 커밋 없음)은 아래 빈 범위 셀이 쓴다
RUNL="noreply env:"; ic_env env.noreply GIT_AUTHOR_EMAIL "$SID" "$OA" "$WORK/env/noreply"
want 0 "ISOLATED_CLONE_READY dest="
RUNL=""; verdict env-override-corp-exit2

# ── 결과 신원의 이름 칸 — 메일만 대조하면 이름이 빠진다. 원본에 로컬 user.name 이 없으면 clone 은 전역 이름(회사 꼴)을 물려받고,
#    GIT_AUTHOR_NAME 은 '@' 가 없으면 사전 검사를 지난다. 둘 다 설정을 건 clone 의 결과 신원(git var)에서 비공개 규칙으로 잡는다 ──
ONAME="$(gx -C "$OA" config --local --get user.name)" && [ -n "$ONAME" ] || die "원본 A 의 로컬 user.name"
gi -C "$OA" config --unset user.name
RUNL="로컬 이름 없음:"; ic ident.noname "$OA" "$WORK/ident/noname"
gi -C "$OA" config user.name "$ONAME"
want 2 "UNRUN: clone 의 커밋 author 이름이 신원 정책" "ISOLATED_CLONE_UNRUN dest=" "!ISOLATED_CLONE_READY"
RUNL="GIT_AUTHOR_NAME:"; ic_env ident.envname GIT_AUTHOR_NAME "$CORPN dev" "$OA" "$WORK/ident/envname"
want 2 "UNRUN: clone 의 커밋 author 이름이 신원 정책" "ISOLATED_CLONE_UNRUN dest=" "!ISOLATED_CLONE_READY"
RUNL=""; verdict ident-name-private-rule-exit2

# ── 원본 로컬 신원 — 원본 A 의 user.email 하나만 바꿔 돌리고 되돌린다(전역은 회사 메일이다 — 로컬이 없을 때 전역으로 대신하지 않는다) ──
gi -C "$OA" config user.email "$CORPM"
RUNL="회사 꼴 로컬 메일:"; ic b.corp "$OA" "$WORK/b/corp"
gi -C "$OA" config user.email "$SID"
want 2 "UNRUN: 원본 로컬 신원이 신원 정책" "!ISOLATED_CLONE_READY"
[ ! -e "$WORK/b/corp" ] || WHY="$WHY · 회사 꼴 로컬 메일: 막는다면서 clone 을 만들었다"
gi -C "$OA" config --unset user.email
RUNL="로컬 메일 없음:"; ic b.none "$OA" "$WORK/b/none"
gi -C "$OA" config user.email "$SID"
want 2 "UNRUN: 원본 로컬 user.email 이 없다" "!ISOLATED_CLONE_READY"
[ ! -e "$WORK/b/none" ] || WHY="$WHY · 로컬 메일 없음: 막는다면서 clone 을 만들었다"
RUNL=""; verdict origin-identity-exit2

# ── 인자 · 원본 · 대상 — 만들기 전에 2 로 끝난다 ──
mkdir -p "$WORK/args/plain-dir" "$WORK/args/exists" || die "mkdir args"
RUNL="인자 없음:"; ic args.none
want 2 "UNRUN: 인자 오류"
RUNL="모르는 인자:"; ic args.unknown --bogus "$OA" "$WORK/args/x"
want 2 "UNRUN: 알 수 없는 인자: --bogus"
RUNL="대상이 있다:"; ic args.dest-exists "$OA" "$WORK/args/exists"
want 2 "UNRUN: 대상이 이미 있다"
RUNL="원본이 저장소가 아니다:"; ic args.not-repo "$WORK/args/plain-dir" "$WORK/args/y"
want 2 "UNRUN: 원본이 git 저장소가 아니다"
[ ! -e "$WORK/args/y" ] || WHY="$WHY · 원본이 저장소가 아닌데 clone 을 만들었다"
RUNL="check-fetch 대상이 저장소가 아니다:"; ic args.cf-not-repo --check-fetch "$WORK/args/plain-dir" "$OA"
want 2 "UNRUN: clone 이 git 저장소가 아니다" "ISOLATED_CLONE_FETCH_UNRUN"
RUNL=""; verdict args-exit2

# ── --check-fetch — 원본에서 닿지 않는 clone 커밋의 author · committer = 원본 로컬 user.email ──
if [ "$CA_OK" = 1 ] && [ -n "$CLEAN1" ]; then
  ic cf.clean --check-fetch "$CA" "$OA"
  want 0 "ISOLATED_CLONE_FETCH_OK commits=1 " "!  ❌ "
else
  WHY="$WHY · 대조 clone 또는 그 커밋이 없다(앞 셀 실패)"
fi
verdict check-fetch-clean-exit0

BADA=""
if [ "$CA_OK" = 1 ] && [ -n "$CLEAN1" ]; then
  printf 'd\n' > "$CA/d.md" || die "쓰기 d.md"
  gi -C "$CA" add -A
  GX_AMAIL="$CORPM"; gi -C "$CA" commit -qm "회사 신원 author"; GX_AMAIL=""
  BADA="$(git -C "$CA" rev-parse HEAD 2>/dev/null)"
  ic cf.corp-author --check-fetch "$CA" "$OA"
  want 1 "  ❌ ${BADA:0:12} author: $CORPM " "!  ❌ ${BADA:0:12} committer: " "!  ❌ ${CLEAN1:0:12} " \
    "ISOLATED_CLONE_FETCH_BAD commits=2 bad=1"
else
  WHY="$WHY · 대조 clone 또는 그 커밋이 없다(앞 셀 실패)"
fi
verdict check-fetch-corp-author-exit1

# 회사 신원 author 커밋을 브랜치에서 빼고(reset) committer 만 회사 꼴인 커밋을 올린다 — 뺀 커밋은 범위 밖이다
BADC=""
if [ "$CA_OK" = 1 ] && [ -n "$CLEAN1" ]; then
  gi -C "$CA" reset -q --hard "$CLEAN1"
  printf 'e\n' > "$CA/e.md" || die "쓰기 e.md"
  gi -C "$CA" add -A
  GX_CMAIL="$CORPM"; gi -C "$CA" commit -qm "회사 신원 committer"; GX_CMAIL=""
  BADC="$(git -C "$CA" rev-parse HEAD 2>/dev/null)"
  ic cf.corp-committer --check-fetch "$CA" "$OA"
  want 1 "  ❌ ${BADC:0:12} committer: $CORPM " "!  ❌ ${BADC:0:12} author: " "ISOLATED_CLONE_FETCH_BAD commits=2 bad=1"
  [ -z "$BADA" ] || ! /usr/bin/grep -qF -- "${BADA:0:12}" "$OUT" || WHY="$WHY · 브랜치에서 뺀 회사 신원 author 커밋을 셌다"
else
  WHY="$WHY · 대조 clone 또는 그 커밋이 없다(앞 셀 실패)"
fi
verdict check-fetch-corp-committer-exit1

# 원본 로컬 user.email 이 없다 — 전역(회사 메일)으로 대신하지 않고 판정 불가다(끝 줄 표지까지). 원본 A 의 그 키 하나만 빼고 되돌린다
if [ "$CA_OK" = 1 ]; then
  gi -C "$OA" config --unset user.email
  ic cf.no-identity --check-fetch "$CA" "$OA"
  gi -C "$OA" config user.email "$SID"
  want 2 "UNRUN: 원본 로컬 user.email 이 없다" "ISOLATED_CLONE_FETCH_UNRUN" "!ISOLATED_CLONE_FETCH_OK" "!ISOLATED_CLONE_FETCH_BAD"
else
  WHY="$WHY · 대조 clone 이 없다(앞 셀 실패)"
fi
verdict check-fetch-no-origin-identity-exit2

# 새 커밋 없는 clone — 볼 커밋이 0개면 0(쟀고 깨끗하다)이 아니라 판정 불가다(끝 줄 표지까지)
if [ -d "$WORK/env/noreply/.git" ]; then
  ic cf.empty --check-fetch "$WORK/env/noreply" "$OA"
  want 2 "UNRUN: 볼 커밋이 0개다" "ISOLATED_CLONE_FETCH_UNRUN" "!ISOLATED_CLONE_FETCH_OK" "!ISOLATED_CLONE_FETCH_BAD"
else
  WHY="$WHY · 새 커밋 없는 대조 clone 이 없다(env-override 셀의 noreply 대조 실패)"
fi
verdict check-fetch-empty-range-exit2

if [ "$nfail" -eq 0 ] && [ "$npass" -gt 0 ]; then
  echo "ISOLATED_CLONE_OK (셀 ${npass}개 — 격리 clone 스크립트의 종료 코드 · clone 설정 · clone 커밋의 신원 · 결과 신원 · --check-fetch 판정)"
  exit 0
fi
echo "isolated-clone: 실패 ${nfail}건 · 통과 ${npass}건"
exit 1
