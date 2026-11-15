#!/bin/bash
# diff-parse: not-a-diff — 이 스크립트는 diff 를 읽지 않는다. git 설정 값 · ref 의 객체 이름 · 커밋의 신원 칸(author · committer 메일)만 읽는다
# isolated_clone.sh — 커밋을 나눠 하나씩 검증할 격리 clone 을 만들고, 그 clone 에서 가져올 커밋의 신원을 단언한다.
#
# 왜: clone 은 원본 저장소의 로컬 설정을 물려받지 않는다 — 손으로 만든 clone 에서 커밋하면 전역 신원(공개하지 않을 메일일 수 있다)으로
#   찍히고 커밋 훅도 돌지 않는다. 신원 환경 변수(GIT_AUTHOR_* · GIT_COMMITTER_*) · 전역 author.email · committer.email · 설정
#   주입(GIT_CONFIG_PARAMETERS)은 저장소 user.email 보다 앞서서 설정만 옮겨서는 막지 못하고, 로컬 저장소를 clone 하면 원본의 옛
#   태그가 따라와 그 clone 에서 새 원격으로 나갈 수 있다.
#
# 사용
#   isolated_clone.sh <원본> <대상>
#     <원본>(저장소 최상위)을 git clone --no-hardlinks --no-tags 로 <대상> 에 만든다(clone 하는 동안 전역 훅을 끈다). 원본의 로컬
#     설정에서 user.email · user.name · fz.maintainer · fz.neutralizeRules 를 있는 만큼 옮기고 user.useConfigOnly=true 를 건다.
#     fz.neutralizeRules 의 상대 경로는 원본 작업 트리 기준 절대 경로로 바꾼다 — 커밋 훅의 누수 규칙 정본이 그 키를 작업 트리
#     기준으로 풀어서, 그대로 옮기면 clone 기준으로 풀린다.
#     core.hooksPath 는 그 clone 안의 훅 폴더를 가리킨다 — 원본 로컬 값이 없으면 .githooks · 상대 경로면 그 값 · 원본 작업 트리
#     안의 절대 경로면 clone 안의 같은 자리 · 원본 밖의 절대 경로면 그 값이다. 원본 로컬 값이 없고 clone 에 .githooks 도 없으면
#     NOTE 한 줄을 낸다(원본의 .git/hooks 는 clone 에 오지 않는다)
#     exit 0 — 끝 줄 `ISOLATED_CLONE_READY dest=<대상> … tags=0`
#     exit 2 — 사유마다 `UNRUN:` 줄 · 끝 줄 `ISOLATED_CLONE_UNRUN …`
#       만들지 않는다: 인자 오류 · 원본이 git 저장소의 최상위가 아니다 · 대상이 이미 있다 · 원본 로컬 설정을 읽지 못했다(경로 값을
#         풀지 못함 포함) · 원본 로컬 user.email 이 없다 · 원본 로컬 신원(user.email · user.name)이 신원 정책을 통과하지 못한다 ·
#         신원 정책을 판정하지 못했다(정본의 판정 불가 — 유지관리자 표지가 있는데 비공개 규칙 파일이 없음 등) · 신원 환경 변수에 신원
#         정책을 통과하지 못하는 메일이 있다(GIT_AUTHOR_EMAIL · GIT_COMMITTER_EMAIL 은 설정돼 있으면 빈 값도 · EMAIL 은 비지
#         않았으면 · GIT_AUTHOR_NAME · GIT_COMMITTER_NAME 은 '@' 가 들었으면 본다 — '@' 없는 이름은 아래 결과 신원에서 잡는다)
#       만들었지만 쓰지 않는다: clone 설정을 걸지 못했다 · clone 에 태그가 남았다(--no-tags 뒤에도 확인한다) · 원본 로컬
#         core.hooksPath 가 가리키는 훅 폴더가 clone 에 없다 · 설정을 건 clone 에서 git 이 쓸 author · committer 메일(git var)이 원본
#         로컬 user.email 이 아니다(저장소 설정보다 앞서는 값을 원인마다 열거하지 않고 결과를 잰다)
#   isolated_clone.sh --check-fetch <clone> <원본>
#     원본에서 닿지 않는 clone 커밋 — clone 의 HEAD · 브랜치에서 닿고, clone 의 추적 ref 와 원본의 브랜치 · 태그 · HEAD 가운데 clone
#     에서 커밋으로 풀리는 tip 에서 닿지 않는 커밋 — 의 author · committer 메일이 원본 로컬 user.email 과 같은지 본다. 원본의 원격
#     추적 ref 는 뺄 끝으로 쓰지 않는다 — clone 을 이름 붙은 원격으로 가져오면 가져온 커밋이 거기서 닿아 범위에서 빠진다.
#     ⛔ 가져와 브랜치를 옮기기(reset) 전에 돌린다 — 옮긴 뒤에는 그 커밋이 원본 브랜치에서 닿아 볼 커밋이 없다
#     exit 0 — 모두 의도한 신원 · 끝 줄 `ISOLATED_CLONE_FETCH_OK commits=N`
#     exit 1 — 아닌 커밋이 있다 · 커밋과 축마다 `  ❌ <해시 12자> author|committer: <메일> — …` · 끝 줄 `ISOLATED_CLONE_FETCH_BAD …`
#     exit 2 — 판정 불가 · `UNRUN:` 줄 · 끝 줄 `ISOLATED_CLONE_FETCH_UNRUN …`(인자 오류 · 원본 로컬 user.email 없음 — 전역 값으로
#       대신하지 않는다 · git 실패 · 볼 커밋이 0개. 0 은 쟀고 깨끗할 때만 낸다)
#     부른 쪽은 종료 코드와 끝 줄을 함께 본다 — 스크립트가 도중에 죽어도 0 아닌 코드는 나지만 끝 줄 표지는 없다
# 신원 정책은 누수 규칙 정본(이 파일 옆 leak_rules.py --identity-mail · --identity-name)이 판정한다 — 메일은 noreply 만 통과하고
#   비공개 규칙은 메일 · 이름 칸에 건다. 비공개 규칙은 원본(-C)에서 커밋 훅 · push 훅과 같은 순서로 푼다(--hook-policy). ⛔ 여기에 메일
#   정규식 사본을 두지 않는다 — 사본은 한 벌만 고쳐진다. 정본은 이 파일 위치 기준으로 찾는다(cwd 기준이 아니다)
# bash 3.2 · BSD 도구에서 돈다
set -u
unset CDPATH
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LEAK="$HERE/leak_rules.py"
# 저장소를 가리키는 바깥 git 환경(훅 · rebase --exec · bisect run 이 건다)은 -C 보다 앞서서, 남으면 clone 설정을 엉뚱한 저장소에 쓴다 —
#   끊는다. ⛔ 신원 환경 변수 · 설정 주입(GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT) · 비공개 규칙 env 는 끊지 않는다 — clone 커밋의
#   신원과 판정에 닿는 값이라 재는 대상이다
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE GIT_PREFIX
NL=$'\n'
US=$'\037'
CFG=""
SRC=""
TOP=""
DST_ABS=""
NBAD=0
r=0

unrun() { echo "UNRUN: $* (⛔ 통과 아님)"; }

stop() {   # $1=made|none — 만들기를 판정 불가로 끝낸다(exit 2). made 면 만든 clone 을 쓰지 말라고 알린다
  if [ "$1" = made ]; then
    echo "ISOLATED_CLONE_UNRUN dest=$DST_ABS — 만든 clone 을 쓰지 않는다(위 UNRUN 줄 · ⛔ 그 clone 에서 커밋하지 않는다)"
  else
    echo "ISOLATED_CLONE_UNRUN — clone 을 만들지 않았다(위 UNRUN 줄)"
  fi
  exit 2
}

fetch_unrun() {   # --check-fetch 를 판정 불가로 끝낸다(exit 2) — 0 · 1 과 같이 끝 줄 표지를 남긴다
  echo "ISOLATED_CLONE_FETCH_UNRUN — 판정하지 못했다(위 UNRUN 줄 · ⛔ 통과 아님)"
  exit 2
}

# 신원 한 벌 → 정본의 신원 정책. $1=메일 · $2=이름(없으면 빈 값 — 메일만 본다). 비공개 규칙은 원본(-C "$SRC")에서 커밋 훅 · push 훅과
#   같은 순서로 푼다(--hook-policy — env FZ_NEUTRALIZE_RULES > git 설정 fz.neutralizeRules > 유지관리자 표지가 참이면 판정 불가).
#   0 = 통과 · 1 = 통과하지 못함(정본의 ❌ 줄을 낸다) · 2 = 판정 불가(정본 · python3 부재 · 정본 exit 2 · 종료 코드와 끝 줄이 어긋남 —
#   파이썬 예외도 exit 1 이라 끝 줄을 함께 본다. 정본 출력을 함께 낸다)
identity_ok() {
  local out rc=0 last
  if [ ! -f "$LEAK" ]; then
    unrun "누수 규칙 정본을 찾지 못했다($LEAK) — 신원 정책으로 판정할 수 없다"
    return 2
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    unrun "python3 를 찾지 못했다 — 신원 정책으로 판정할 수 없다"
    return 2
  fi
  out="$(PYTHONIOENCODING=utf-8 python3 "$LEAK" -C "$SRC" --hook-policy "--identity-mail=$1" "--identity-name=${2-}" </dev/null 2>&1)" || rc=$?
  last="${out##*$NL}"
  case "$rc:$last" in
    "0:LEAK_CLEAN identity-mail "*) return 0 ;;
    "1:LEAK_HIT identity-mail "*) printf '%s\n' "$out"; return 1 ;;
  esac
  [ -z "$out" ] || printf '%s\n' "$out"
  unrun "신원 정책 판정이 끝나지 않았다(정본 exit $rc)"
  return 2
}

# 저장소 로컬 설정 값 하나 → CFG. $1=저장소 · $2=키 · $3=형식(빈 값 = 그대로 · --path = `~` 를 푼다). 0 = 있음(빈 값일 수 있다) ·
#   1 = 없음 · 2 = 읽기 실패(설정 파일 오류 등 — '없음' 으로 읽으면 옮겨야 할 키가 조용히 빠진다)
cfg_local() {
  local rc=0 err=""
  CFG="$(git -C "$1" config --local ${3:-} --get "$2" 2>/dev/null)" || rc=$?
  [ "$rc" -ne 0 ] || return 0
  CFG=""
  if [ "$rc" -eq 1 ]; then
    err="$(git -C "$1" config --local ${3:-} --get "$2" 2>&1 >/dev/null)"
    [ -n "$err" ] || return 1
  fi
  err="${err%%$NL*}"
  unrun "로컬 설정 $2 를 읽지 못했다(git exit $rc${err:+ — $err})"
  return 2
}

# 신원 환경 변수 하나. 통과하지 못하면 NBAD 를 센다(사유를 모두 낸 뒤 끝낸다). $1=이름 · $2=값 · $3=볼 때(set = 설정됐으면 빈 값도 ·
#   nonempty = 비지 않았으면 · at = '@' 가 들었으면) · $4=그 변수가 커밋 신원에 닿는 길
env_check() {
  local r
  case "$3" in
    nonempty) [ -n "$2" ] || return 0 ;;
    at) case "$2" in *@*) ;; *) return 0 ;; esac ;;
  esac
  identity_ok "$2"; r=$?
  case "$r" in
    0) return 0 ;;
    1) unrun "환경 변수 $1 에 신원 정책(noreply 만 통과 · 비공개 규칙)을 통과하지 못하는 메일이 있다 — $4(unset $1)"
       NBAD=$((NBAD + 1))
       return 0 ;;
  esac
  stop none
}

setc() {   # $1=키 · $2=값 — clone 로컬 설정. 걸지 못하면 만든 clone 을 쓰지 않는다
  git -C "$DST_ABS" config --local "$1" "$2" || { unrun "clone 설정을 걸지 못했다: $1"; stop made; }
}

check_fetch() {   # $1=clone · $2=원본 → 0 · 1 · 2(사유는 UNRUN 줄 — 끝 줄 표지는 부른 쪽이 낸다)
  local cl og want tips hd ck oid kind rest excl="" log sha ae ce n=0 bad=0 r
  cl="$(cd "$1" 2>/dev/null && pwd -P)" || cl=""
  if [ -z "$cl" ] || ! git -C "$cl" rev-parse --git-dir >/dev/null 2>&1; then
    unrun "clone 이 git 저장소가 아니다: $1"; return 2
  fi
  og="$(cd "$2" 2>/dev/null && pwd -P)" || og=""
  if [ -z "$og" ] || ! git -C "$og" rev-parse --git-dir >/dev/null 2>&1; then
    unrun "원본이 git 저장소가 아니다: $2"; return 2
  fi
  cfg_local "$og" user.email ""; r=$?
  [ "$r" -le 1 ] || return 2
  want="$CFG"
  if [ -z "$want" ]; then
    unrun "원본 로컬 user.email 이 없다 — 의도한 신원을 정하지 못했다(전역 값으로 대신하지 않는다)"; return 2
  fi
  # 뺄 끝 — clone 의 추적 ref(--remotes)와, 원본의 브랜치 · 태그 · HEAD 가운데 clone 에서 커밋으로 풀리는 tip(태그는 가리키는 커밋으로
  #   벗긴다). ⛔ 원본의 원격 추적 ref 는 쓰지 않는다 — clone 을 이름 붙은 원격으로 가져오면 가져온 커밋이 거기서 닿아 범위에서 빠진다.
  #   ⛔ 풀리지 않는 tip 은 넘기지 않는다 — git 이 범위를 풀지 못해 판정 불가로 끝난다
  tips="$(git -C "$og" for-each-ref --format='%(objectname)' refs/heads refs/tags)" || { unrun "원본 ref 를 읽지 못했다"; return 2; }
  hd="$(git -C "$og" rev-parse -q --verify HEAD 2>/dev/null)" && tips="$tips$NL$hd"
  if [ -n "$tips" ]; then
    ck="$(printf '%s^{commit}\n' $tips | git -C "$cl" cat-file --batch-check)" \
      || { unrun "clone 에서 원본 tip 을 풀지 못했다(git cat-file 실패)"; return 2; }
    while read -r oid kind rest; do
      if [ "$kind" = commit ]; then excl="$excl $oid"; fi
    done <<< "$ck"
  fi
  log="$(git -C "$cl" -c log.showSignature=false log --no-color --format='%H%x1f%ae%x1f%ce' HEAD --branches --not --remotes $excl --)" \
    || { unrun "clone 의 커밋 범위를 읽지 못했다(git log 실패)"; return 2; }
  while IFS="$US" read -r sha ae ce; do
    [ -n "$sha" ] || continue
    n=$((n + 1))
    if [ "$ae" != "$want" ]; then
      echo "  ❌ ${sha:0:12} author: ${ae:-(빈 값)} — 의도한 신원(원본 로컬 user.email)이 아니다"; bad=$((bad + 1))
    fi
    if [ "$ce" != "$want" ]; then
      echo "  ❌ ${sha:0:12} committer: ${ce:-(빈 값)} — 의도한 신원(원본 로컬 user.email)이 아니다"; bad=$((bad + 1))
    fi
  done <<< "$log"
  if [ "$n" -eq 0 ]; then
    unrun "볼 커밋이 0개다 — clone 에 원본에서 닿지 않는 커밋이 없다(이미 원본 브랜치로 옮겼거나 clone 에서 커밋하지 않았다)"
    return 2
  fi
  if [ "$bad" -gt 0 ]; then
    echo "ISOLATED_CLONE_FETCH_BAD commits=$n bad=$bad — 가져오지 않는다(위 ❌ 줄 — 커밋과 축)"
    return 1
  fi
  echo "ISOLATED_CLONE_FETCH_OK commits=$n — author · committer 메일이 모두 원본 로컬 user.email 이다"
  return 0
}

if ! command -v git >/dev/null 2>&1; then
  unrun "git 을 찾지 못했다"
  [ "${1:-}" != --check-fetch ] || fetch_unrun
  stop none
fi

# ── 가져올 커밋의 신원 단언 ──
if [ "${1:-}" = --check-fetch ]; then
  shift
  if [ $# -ne 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
    unrun "인자 오류 — 사용: isolated_clone.sh --check-fetch <clone> <원본>"
    fetch_unrun
  fi
  rc=0
  check_fetch "$1" "$2" || rc=$?
  [ "$rc" -ne 2 ] || fetch_unrun
  exit "$rc"
fi

# ── 만들기 — 구조 오류는 바로 끝낸다(만들지 않는다) ──
case "${1:-}" in
  -*) unrun "알 수 없는 인자: $1 — 사용: isolated_clone.sh <원본> <대상> | isolated_clone.sh --check-fetch <clone> <원본>"; stop none ;;
esac
if [ $# -ne 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
  unrun "인자 오류 — 원본과 대상 두 개를 준다(사용: isolated_clone.sh <원본> <대상>)"; stop none
fi
case "$2" in
  -*) unrun "대상이 '-' 로 시작한다: $2 — 경로로 준다(./$2)"; stop none ;;
esac
SRC="$(cd "$1" 2>/dev/null && pwd -P)" || SRC=""
if [ -z "$SRC" ] || ! git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1; then
  unrun "원본이 git 저장소가 아니다: $1"; stop none
fi
if [ "$(git -C "$SRC" rev-parse --is-bare-repository 2>/dev/null)" != true ]; then
  TOP="$(git -C "$SRC" rev-parse --show-toplevel 2>/dev/null)" && TOP="$(cd "$TOP" 2>/dev/null && pwd -P)" || TOP=""
  if [ "$TOP" != "$SRC" ]; then
    unrun "원본이 저장소 최상위가 아니다: $1 — 최상위 경로를 준다(clone 은 저장소 전체다)"; stop none
  fi
fi
DST="$2"
if [ -e "$DST" ] || [ -L "$DST" ]; then
  unrun "대상이 이미 있다: $DST — 없는 경로를 준다(있는 폴더에 clone 하지 않는다)"; stop none
fi

# ── 원본 로컬 설정 — 신원 판정 전에 모두 읽는다. 읽기 실패면 만들지 않는다('없음' 으로 읽으면 옮겨야 할 키가 조용히 빠진다) ──
EMAIL_SRC="" NAME_SRC="" MAINT_SRC="" RULES_SRC="" HOOKS_SRC=""
NAME_SET=0 MAINT_SET=0 RULES_SET=0 HOOKS_SET=0
cfg_local "$SRC" user.email ""; r=$?
case "$r" in 0) EMAIL_SRC="$CFG" ;; 1) ;; *) stop none ;; esac
cfg_local "$SRC" user.name ""; r=$?
case "$r" in 0) NAME_SET=1; NAME_SRC="$CFG" ;; 1) ;; *) stop none ;; esac
cfg_local "$SRC" fz.maintainer ""; r=$?
case "$r" in 0) MAINT_SET=1; MAINT_SRC="$CFG" ;; 1) ;; *) stop none ;; esac
cfg_local "$SRC" fz.neutralizeRules --path; r=$?
case "$r" in 0) RULES_SET=1; RULES_SRC="$CFG" ;; 1) ;; *) stop none ;; esac
cfg_local "$SRC" core.hooksPath --path; r=$?
case "$r" in 0) HOOKS_SET=1; HOOKS_SRC="$CFG" ;; 1) ;; *) stop none ;; esac
if [ "$RULES_SET" -eq 1 ] && [ -n "$RULES_SRC" ]; then
  case "$RULES_SRC" in
    /*) ;;
    *) if [ -z "$TOP" ]; then
         unrun "원본 로컬 fz.neutralizeRules 가 상대 경로인데 원본에 작업 트리가 없다 — 절대 경로로 둔다"; stop none
       fi
       RULES_SRC="$TOP/$RULES_SRC" ;;
  esac
fi
# 훅 경로 — 원본이 정했으면 그 자리를 clone 에서도 쓴다(상대 경로는 그대로 · 원본 작업 트리 안의 절대 경로는 clone 안의 같은 자리 ·
#   원본 밖의 절대 경로는 그대로). 정하지 않았으면 .githooks(그 clone 자신의 폴더) — 원본의 .git/hooks 는 clone 에 오지 않는다
HOOKS=.githooks
if [ "$HOOKS_SET" -eq 1 ]; then
  HOOKS="$HOOKS_SRC"
  case "$HOOKS_SRC" in
    "") unrun "원본 로컬 core.hooksPath 가 비었다 — clone 의 훅 경로를 정하지 못했다"; stop none ;;
    /*) HP_REAL="$(cd "$HOOKS_SRC" 2>/dev/null && pwd -P)" || HP_REAL=""
        if [ -n "$TOP" ] && [ -n "$HP_REAL" ]; then
          case "$HP_REAL" in "$TOP"/?*) HOOKS=${HP_REAL#"$TOP"/} ;; esac
        fi ;;
  esac
fi

# ── 신원 — 원본 로컬 user.email · user.name 이 clone 커밋의 신원이 된다. 신원 환경 변수는 그보다 앞선다. 사유를 모두 낸 뒤 끝낸다 ──
if [ -z "$EMAIL_SRC" ]; then
  unrun "원본 로컬 user.email 이 없다 — clone 의 커밋 신원을 정할 수 없다(원본에 noreply 메일을 git config user.email 로 둔다 · 전역 값으로 대신하지 않는다)"
  NBAD=$((NBAD + 1))
else
  identity_ok "$EMAIL_SRC" "$NAME_SRC"; r=$?
  case "$r" in
    0) ;;
    1) unrun "원본 로컬 신원이 신원 정책(메일은 noreply 만 통과 · 비공개 규칙은 메일 · 이름 칸)을 통과하지 못한다 — 옮기면 clone 의 커밋이 그 신원으로 찍힌다(위 ❌ 줄)"
       NBAD=$((NBAD + 1)) ;;
    *) stop none ;;
  esac
fi
[ -z "${GIT_AUTHOR_EMAIL+x}" ] || env_check GIT_AUTHOR_EMAIL "${GIT_AUTHOR_EMAIL-}" set "저장소 설정보다 앞서서 clone 커밋의 author 메일이 된다"
[ -z "${GIT_COMMITTER_EMAIL+x}" ] || env_check GIT_COMMITTER_EMAIL "${GIT_COMMITTER_EMAIL-}" set "저장소 설정보다 앞서서 clone 커밋의 committer 메일이 된다"
env_check EMAIL "${EMAIL-}" nonempty "user.email 이 없는 저장소에서 커밋 메일이 된다(clone 에는 user.email 을 걸지만 같은 셸의 다른 커밋에 남는다)"
env_check GIT_AUTHOR_NAME "${GIT_AUTHOR_NAME-}" at "저장소 설정보다 앞서서 clone 커밋의 author 이름이 된다"
env_check GIT_COMMITTER_NAME "${GIT_COMMITTER_NAME-}" at "저장소 설정보다 앞서서 clone 커밋의 committer 이름이 된다"
[ "$NBAD" -eq 0 ] || stop none

# ── clone — 전역 훅(core.hooksPath)이 clone 하는 동안 post-checkout 으로 돌지 않게 이 명령에만 끈다(설정에 남지 않는다) ──
if ! git -c core.hooksPath=/dev/null clone -q --no-hardlinks --no-tags -- "$SRC" "$DST"; then
  unrun "git clone 이 실패했다($SRC → $DST)"; stop none
fi
DST_ABS="$(cd "$DST" 2>/dev/null && pwd -P)" || DST_ABS=""
if [ -z "$DST_ABS" ]; then
  DST_ABS="$DST"; unrun "만든 clone 폴더를 찾지 못했다: $DST"; stop made
fi
setc user.email "$EMAIL_SRC"
[ "$NAME_SET" -eq 0 ] || setc user.name "$NAME_SRC"
setc user.useConfigOnly true
setc core.hooksPath "$HOOKS"
NKEYS=0
if [ "$MAINT_SET" -eq 1 ]; then setc fz.maintainer "$MAINT_SRC"; NKEYS=$((NKEYS + 1)); fi
if [ "$RULES_SET" -eq 1 ]; then setc fz.neutralizeRules "$RULES_SRC"; NKEYS=$((NKEYS + 1)); fi

# ── 태그 — --no-tags 뒤에도 남았으면 쓰지 않는다(옛 태그가 이 clone 에서 새 원격으로 나가는 통로) ──
TAGS="$(git -C "$DST_ABS" for-each-ref --format='%(refname)' refs/tags)" || { unrun "clone 의 태그를 읽지 못했다"; stop made; }
if [ -n "$TAGS" ]; then
  NT="$(printf '%s\n' "$TAGS" | wc -l | tr -d ' ')"
  unrun "clone 에 태그가 ${NT}개 남았다 — 옛 태그가 이 clone 에서 새 원격으로 나갈 수 있다"; stop made
fi

# ── 훅 폴더 — 원본이 정한 훅 폴더가 clone 에 없으면 그 clone 의 커밋에 원본과 같은 훅이 돌지 않는다 ──
case "$HOOKS" in /*) HD="$HOOKS" ;; *) HD="$DST_ABS/$HOOKS" ;; esac
if [ ! -d "$HD" ]; then
  if [ "$HOOKS_SET" -eq 1 ]; then
    unrun "clone 에 커밋 훅 폴더가 없다($HOOKS — 원본 로컬 core.hooksPath 를 옮긴 자리) — 그 clone 의 커밋에 원본과 같은 훅이 돌지 않는다"
    stop made
  fi
  echo "NOTE: clone 에 .githooks 폴더가 없다 — 원본은 core.hooksPath 없이 .git/hooks 를 쓰고 그 훅은 clone 에 오지 않는다(그 clone 의 커밋에 돌 훅이 없다)"
fi

# ── 결과 신원 — 설정을 건 clone 에서 git 이 쓸 author · committer 메일을 잰다. 저장소 user.email 보다 앞서는 값(신원 환경 변수 · 전역
#   author.email · committer.email · 설정 주입)을 원인마다 열거하지 않고 결과를 원본 로컬 user.email 과 대조한다. 이름 칸은 대조할 원본
#   값이 없을 수 있어(로컬 user.name 이 없으면 전역 이름을 물려받는다) 결과 이름을 신원 정책(비공개 규칙)에 통과시킨다 ──
for AX in author committer; do
  case "$AX" in author) VAR=GIT_AUTHOR_IDENT ;; *) VAR=GIT_COMMITTER_IDENT ;; esac
  IDENT="$(git -C "$DST_ABS" var "$VAR" 2>/dev/null)" || { unrun "clone 의 커밋 $AX 신원을 재지 못했다(git var $VAR 실패)"; stop made; }
  case "$IDENT" in
    *"<"*">"*) M="${IDENT#*<}"; M="${M%%>*}" ;;
    *) unrun "clone 의 커밋 $AX 신원에서 메일 칸을 찾지 못했다(git var $VAR)"; stop made ;;
  esac
  if [ "$M" != "$EMAIL_SRC" ]; then
    unrun "clone 의 커밋 $AX 메일이 원본 로컬 user.email 이 아니다(${M:-(빈 값)}) — 저장소 설정보다 앞서는 값(신원 환경 변수 · 전역 $AX.email · 설정 주입 GIT_CONFIG_PARAMETERS)이 있다"
    stop made
  fi
  identity_ok "$M" "${IDENT%% <*}"; IRC=$?
  if [ "$IRC" -ne 0 ]; then
    [ "$IRC" -ne 1 ] || unrun "clone 의 커밋 $AX 이름이 신원 정책(비공개 규칙)을 통과하지 못한다 — 원본에 로컬 user.name 이 없어 전역 이름을 물려받았거나 앞서는 값(GIT_AUTHOR_NAME · GIT_COMMITTER_NAME · 전역 $AX.name)이 있다"
    stop made
  fi
done
echo "ISOLATED_CLONE_READY dest=$DST_ABS user.email=$EMAIL_SRC user.useConfigOnly=true core.hooksPath=$HOOKS fz-keys=$NKEYS tags=0"
exit 0
