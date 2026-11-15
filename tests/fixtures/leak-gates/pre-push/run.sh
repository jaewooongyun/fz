#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 읽지 않는다. 트리의 push 훅을 임시 저장소에서 돌려 종료 코드와 출력 줄(고정 글자)만 본다
# modes: default caller=health
# push 훅(.githooks/pre-push) 회귀 — 훅 파일을 직접 실행한다: 임시 로컬 저장소를 cwd 로 인자(원격 이름 · 원격 URL)와 stdin 의 ref 갱신
#   줄(`<로컬 ref> <로컬 sha> <원격 ref> <원격 sha>`)을 넣는다. 원격은 mktemp 아래 임시 bare 저장소다. 훅은 판정을 훅 위치 기준의
#   정본(트리의 scripts/leak_rules.py)에 넘긴다. 실제 플러그인 저장소에는 태그 · ref 를 만들지 않는다.
# ⛔ exit 1 셀은 실패한 축의 줄 글자도 단언한다 — 종료 코드만 보면 다른 축의 실패(판정 불가 등)로도 통과한다.
# ⛔ 검사한 커밋 집합 — unresolved-remote-tip-coverage · multiple-ref-coverage 는 훅이 검사한 커밋 집합을 러너가 따로 계산한 기대
#    집합과 대조한다. 훅 쪽은 정본 끝 줄의 commits=N(ref 마다 `commits:<로컬 sha>`)과 적중 줄의 해시, 기대 쪽은 러너의 git rev-list 다(원격
#    tip 은 러너가 ls-remote 하고 cat-file -e 로 풀리는 것만 뺀다 — 훅의 일괄 확인과 다른 길). 풀 수 없는 tip 을 제외 근거로 쓰면 정본이
#    판정 불가로 끝나 끝 줄 수가 0 이 되고, tip 을 모두 버리면 수가 늘어난다. 깨끗한 ref 의 앞 · 뒤에 오염된 ref 를 둬 둘 다 보는지 본다.
# ⛔ 음성 토큰(회사 꼴 메일 · 키 꼴 · 홈 경로)은 쪼개 적고 실행할 때 잇는다 — 이 파일이 누수 규칙 · 커밋 훅에 걸리지 않게. 비공개 규칙
#    파일(합성 회사 이름 한 줄)은 저장소 밖에 둔다.
# ⛔ git 은 격리한다 — 전역 · 시스템 설정과 기본 무시 · 속성 파일을 끊고(훅 · 정본이 부르는 git 도) 이 러너의 git 은 훅 · 서명을 끄며
#    신원은 합성 noreply 다. 유지관리자 표지 · 비공개 규칙 경로는 셀 저장소의 로컬 설정에만 둔다 — 사용자 전역 설정의 표지가 셀을 바꾸지
#    않게. 커밋 · 태그 · ref 는 mktemp 임시 저장소에만 만든다.
# 셀(기대 훅 exit):
#   0   clean-exit0 · contributor-identity-off-exit0(표지 없음 — 회사 꼴 메일 신원도 통과하고 안내 줄이 나온다) · delete-only-exit0 ·
#       lightweight-tag-clean · orphan-force-push-missing-obj(원격 tip 객체가 로컬에 없다 — 막지 않고 로컬에서 닿는 커밋 전부를 본다) ·
#       empty-remote-first-push(원격에 ref 가 없다 — 루트부터 전부) · hook-exec-bit(훅 파일의 실행 비트) ·
#       host-config-params-ignored(부모 git 의 -c 설정을 물려받은 자식 실행도 같은 결과)
#   1   maintainer-corp-identity-exit1 · intermediate-home-path-exit1(중간 커밋이 더하고 다음 커밋이 지운 줄) · message-ticket-key-exit1 ·
#       tag-only-corp-tagger-exit1(커밋 범위가 비고 태그만 민다) · stale-tracking-ref(origin/* 가 원격에 없는 옛 커밋을 가리켜도 그
#       커밋을 본다) · git-fail-blocks(로컬에 없는 객체 — 정본 exit 2) · maintainer-no-rules-exit1 · ls-remote-fail-blocks ·
#       url-credentials-redacted(훅이 내는 줄에 원격 URL 의 사용자 정보가 없다) · unresolved-remote-tip-coverage · multiple-ref-coverage ·
#       dest-ref-name-exit1(깨끗한 커밋을 티켓 키 꼴 이름의 목적지로) · tag-name-exit1(태그 이름) ·
#       tag-oid-under-branch-ref-exit1(태그 객체를 태그 ref 가 아닌 이름으로) · malformed-ref-line-exit1(형식 밖 갱신 줄) ·
#       replaced-remote-tag-exit1(원격에 있는 태그 객체를 로컬에서 미공개 커밋 쪽으로 바꿔치기 — replace ref)
# 출력: 셀마다 `PASS <셀>` 또는 `FAIL <셀> — 사유` + 그 셀이 돌린 훅 출력의 끝 30줄(들여씀). 전건 통과면 `PRE_PUSH_OK …`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — 인자 · 도구 · 대상 부재 · 임시 저장소)
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
HOOK="$TREE/.githooks/pre-push"
[ -f "$HOOK" ] || { echo "UNRUN: 대상 부재 — .githooks/pre-push"; exit 2; }

# 바깥 git 환경(훅이 건 GIT_DIR · GIT_INDEX_FILE 등)이 임시 저장소의 git 을 바깥 저장소로 돌리지 않게 끊는다. 비공개 규칙은 셀 저장소의
#    git 설정으로만 준다
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_COMMON_DIR GIT_NAMESPACE GIT_PREFIX FZ_NEUTRALIZE_RULES
# 부모 git 이 `-c` 로 넘긴 설정도 끊는다 — 남으면 셀 저장소의 로컬 설정(유지관리자 표지 · 규칙 경로)을 덮는다
unset GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-prepush.XXXXXX")" && [ -n "$WORK" ] && [ -d "$WORK" ] \
  || { echo "UNRUN: 임시 폴더를 만들지 못했다"; exit 2; }
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/out" "$WORK/tmp" "$WORK/xdg" || { echo "UNRUN: 임시 폴더 준비 실패"; exit 2; }
# 이 러너의 git 과 훅 · 정본이 부르는 git 모두 전역 · 시스템 설정과 기본 무시 · 속성 파일(XDG)을 읽지 않는다 — 사용자 전역의 유지관리자
#    표지 · 규칙 경로 · 색 · 외부 diff 가 판정을 바꾸지 않게. 바이트코드를 쓰지 않는다. 임시 파일도 WORK 안이다
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 GIT_CEILING_DIRECTORIES="$WORK" \
  XDG_CONFIG_HOME="$WORK/xdg" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 TMPDIR="$WORK/tmp"

# 합성 신원 — 신원 축의 허용 꼴(noreply)이다. 셀의 적중은 주입한 것에서만 나온다
SID="0+fz-prepush@users.noreply.github.com"
# 음성 토큰 — 쪼개 적고 실행할 때 잇는다. 비공개 규칙은 합성 회사 이름 하나다
CORPN="qzpush""corp"; CORPM="dev@${CORPN}.test"; HOMEP="/Us""ers/alice"; KEYP="AB""C-4821"
Z40="0000000000000000000000000000000000000000"; MISS="ffffffffffffffffffffffffffffffffffffffff"; TAB=$'\t'
RULES_CORP="$WORK/rules-corp.txt"
printf '%s\n' '# 합성 비공개 규칙(시험용) — 한 줄 한 정규식' "(?i)$CORPN" > "$RULES_CORP" || { echo "UNRUN: 규칙 파일을 만들지 못했다"; exit 2; }

npass=0 nfail=0 WHY="" SHOW="" RUNL="" HRC="" OUT="" R="" B="" HEADC="" C0="" RONLY="" EXP="" GX_MAIL=""
die() { echo "UNRUN: 픽스처 준비 실패 — $* (⛔ 통과 아님)"; exit 2; }
# 격리 git — 훅 · 서명을 끈다. author · committer 메일은 GX_MAIL(빈 값 = 합성 noreply). 주석 태그의 tagger 는 committer 값이다
gx() {
  GIT_AUTHOR_NAME=fz-prepush GIT_AUTHOR_EMAIL="${GX_MAIL:-$SID}" GIT_COMMITTER_NAME=fz-prepush GIT_COMMITTER_EMAIL="${GX_MAIL:-$SID}" \
    git -c core.hooksPath=/dev/null -c commit.gpgsign=false -c tag.gpgsign=false "$@"
}
# 실패면 준비 실패(exit 2). ⛔ $( ) 안에서 부르지 않는다 — exit 가 서브셸에 갇힌다
gi() { gx "$@" >/dev/null 2>&1 || die "git $*"; }
put() {   # $1=저장소 안 경로 · 나머지=줄 — 폴더를 만들고 줄마다 개행으로 쓴다
  local rel="$1" p="$R/$1"; shift
  mkdir -p "$(dirname "$p")" && printf '%s\n' "$@" > "$p" || die "쓰기 $rel"
}
new_cell() {   # $1=셀 — 전역 R(로컬 저장소 · 원격 이름 origin = B) · B(빈 임시 bare 원격)
  R="$WORK/$1/local" B="$WORK/$1/remote.git"
  mkdir -p "$WORK/$1" || die "mkdir $1"
  gi -c init.defaultBranch=main init -q "$R"
  gi -c init.defaultBranch=main init -q --bare "$B"
  [ -d "$R/.git" ] && [ -f "$B/HEAD" ] || die "$1 저장소가 만들어지지 않았다"
  gi -C "$R" remote add origin "$B"
}
commit() {   # $1=메시지 · $2=author · committer 메일(빈 값 = 합성 noreply) — 작업 트리 전부를 커밋. 전역 HEADC
  GX_MAIL="${2:-}"
  gi -C "$R" add -A
  gi -C "$R" commit -qm "$1"
  GX_MAIL=""
  HEADC="$(gx -C "$R" rev-parse HEAD)" && [ -n "$HEADC" ] || die "커밋 이름"
}
published_base() {   # 깨끗한 첫 커밋(전역 C0)을 원격 main 에 둔다 — 훅을 끈 push 라 이 러너가 시험하는 훅이 여기서 돌지 않는다
  put a.md "깨끗"; commit "base"; C0="$HEADC"
  gi -C "$R" push -q "$B" "$C0:refs/heads/main"
}
remote_only() {   # $1=원격 ref — 원격에만 있는 커밋(전역 RONLY · 로컬에 객체가 없다)을 그 ref 에 둔다
  local t
  t="$(gx --git-dir="$B" hash-object -t tree -w /dev/null)" && [ -n "$t" ] || die "원격 빈 트리"
  RONLY="$(gx --git-dir="$B" commit-tree "$t" -m "원격에만 있는 커밋")" && [ -n "$RONLY" ] || die "원격 전용 커밋"
  gi --git-dir="$B" update-ref "$1" "$RONLY"
}
maintainer() {   # 셀 저장소의 로컬 설정에 유지관리자 표지 — $1=rules 면 비공개 규칙 파일(저장소 밖)도 준다
  gi -C "$R" config fz.maintainer true
  [ "${1:-}" != rules ] || gi -C "$R" config fz.neutralizeRules "$RULES_CORP"
}
hook() {   # $1=출력 이름 · $2=원격 URL · 나머지=stdin 의 ref 갱신 줄 — 전역 R 을 cwd 로 트리의 훅을 직접 실행한다. 출력 OUT · 종료 코드 HRC
  local name="$1" url="$2"; shift 2
  OUT="$WORK/out/$name.txt"; SHOW="$SHOW$OUT"$'\n'
  (cd "$R" && printf '%s\n' "$@" | bash "$HOOK" origin "$url") > "$OUT" 2>&1
  HRC=$?
}
want() {   # $1=기대 exit · 나머지=출력(OUT)에 있어야 할 글자(앞이 '!' 면 없어야 할 글자) — 어긋남은 WHY 에 덧붙인다
  local rc="$1" n; shift
  [ "$HRC" = "$rc" ] || WHY="$WHY · ${RUNL:+$RUNL }exit $HRC (기대 $rc)"
  for n in "$@"; do
    case "$n" in
      '!'*) ! /usr/bin/grep -qF -- "${n#!}" "$OUT" || WHY="$WHY · ${RUNL:+$RUNL }없어야 할 줄: ${n#!}" ;;
      *) /usr/bin/grep -qF -- "$n" "$OUT" || WHY="$WHY · ${RUNL:+$RUNL }없는 줄: $n" ;;
    esac
  done
}
expect() {   # $1=원격 URL · $2=로컬 sha — 러너가 따로 센 기대 커밋 수(전역 EXP). 원격 tip 은 ls-remote, 그 가운데 로컬에서 커밋으로
             #    풀리는 것(cat-file -e)만 뺀다 — 훅의 일괄 확인(cat-file --batch-check)과 다른 길로 센다
  local sha ref lsr ex=""
  EXP=""
  lsr="$(gx ls-remote "$1")" || { WHY="$WHY · ${RUNL:+$RUNL }기대 집합: ls-remote 실패"; return; }
  while IFS="$TAB" read -r sha ref; do
    [ -n "$sha" ] || continue
    if gx -C "$R" cat-file -e "$sha^{commit}" 2>/dev/null; then ex="$ex ^$sha"; fi
  done <<< "$lsr"
  EXP="$(gx -C "$R" rev-list --count "$2" $ex)" || { WHY="$WHY · ${RUNL:+$RUNL }기대 집합: rev-list 실패"; EXP=""; }
}
cover() {   # $1=로컬 sha — 훅 출력(OUT)에서 그 ref 의 정본 끝 줄이 센 commits=N 을 기대(EXP)와 대조한다
  local got
  got="$(sed -nE "s/^LEAK_[A-Z]+ commits:$1 commits=([0-9]+) .*/\1/p" "$OUT" | head -n 1)"
  [ -n "$EXP" ] && [ "$got" = "$EXP" ] \
    || WHY="$WHY · ${RUNL:+$RUNL }${1:0:12} 검사 커밋 ${got:-(끝 줄 없음)}개 ≠ 기대 ${EXP:-(없음)}개(rev-list)"
}
verdict() {   # $1=셀 — WHY 가 비었으면 PASS · 아니면 FAIL + 사유 + 그 셀이 돌린 훅 출력의 끝 30줄. WHY · SHOW · RUNL 을 비운다
  if [ -z "$WHY" ]; then
    echo "PASS $1"; npass=$((npass + 1))
  else
    echo "FAIL $1 —${WHY# ·}"; nfail=$((nfail + 1))
    printf '%s' "$SHOW" | while IFS= read -r f; do
      [ -f "$f" ] || continue
      echo "    ── ${f##*/}"; tail -n 30 "$f" | sed 's/^/    /'
    done
  fi
  WHY="" SHOW="" RUNL=""
}

# ── 통과(0) ──
new_cell clean-exit0; published_base
put b.md "둘째"; commit "다음 1"; put c.md "셋째"; commit "다음 2"
hook clean-exit0 "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 0 "── fz pre-push: refs/heads/main → refs/heads/main (" "뺀 원격 tip 1개" \
  "LEAK_CLEAN commits:$HEADC commits=2 annotated=0 lightweight=0 "
verdict clean-exit0

# 유지관리자 표지가 없다(공개 기여자) — 회사 꼴 메일 신원도 신원 메일 규칙을 끄므로 통과한다. 안내 줄이 그 사실을 알린다
#    (대조: maintainer-corp-identity-exit1 은 같은 꼴 신원을 표지가 있는 저장소에서 막는다)
new_cell contributor-identity-off-exit0; published_base
put b.md "둘째"; commit "개인 메일" "$CORPM"
hook contributor-identity-off-exit0 "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 0 "신원 메일 규칙(noreply 만 통과)을 보지 않는다" "LEAK_CLEAN commits:$HEADC commits=1 " "!: 신원 메일 — "
verdict contributor-identity-off-exit0

# 삭제만 — 내보내는 커밋이 없다. 정본을 부르지 않는다
new_cell delete-only-exit0; published_base
hook delete-only-exit0 "$B" "(delete) $Z40 refs/heads/main $C0"
want 0 "삭제만 있다" "!LEAK_"
verdict delete-only-exit0

# 가벼운 태그 — tagger · 주석 칸이 없다. 가리키는 커밋은 커밋 범위가 본다
new_cell lightweight-tag-clean; published_base
put b.md "둘째"; commit "다음"; gi -C "$R" tag v2
hook lightweight-tag-clean "$B" "refs/tags/v2 $HEADC refs/tags/v2 $Z40"
want 0 "LEAK_CLEAN commits:$HEADC commits=1 annotated=0 lightweight=1 "
verdict lightweight-tag-clean

# 고아 루트 강제 push — 원격 main 이 가리키는 객체가 로컬에 없다. 막지 않고 로컬 sha 에서 닿는 커밋 전부를 본다
new_cell orphan-force-push-missing-obj; remote_only refs/heads/main
put a.md "새 루트"; commit "고아 루트"; put b.md "둘째"; commit "다음"; LT="$HEADC"
hook orphan-force-push-missing-obj "$B" "refs/heads/main $LT refs/heads/main $RONLY"
! gx -C "$R" cat-file -e "$RONLY" 2>/dev/null || WHY="$WHY · 대조 실패: 원격 tip 객체가 로컬에 있다"
expect "$B" "$LT"; [ "$EXP" = 2 ] || WHY="$WHY · 대조 실패: 기대 커밋 수 ${EXP:-(없음)} ≠ 2(로컬에서 닿는 전부)"
want 0 "LEAK_CLEAN commits:$LT commits=2 " "풀리지 않아 빼지 않은 tip 1개" "!UNRUN:"
cover "$LT"
verdict orphan-force-push-missing-obj

# ── 적중 · 미판정(1) — exit 와 실패한 축의 줄 ──
new_cell maintainer-corp-identity-exit1; maintainer rules; published_base
put b.md "둘째"; commit "회사 신원" "$CORPM"; S12="${HEADC:0:12}"
hook maintainer-corp-identity-exit1 "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 1 "  ❌ 신원 $S12 author: 신원 메일 — " "  ❌ 신원 $S12 author: 비공개 규칙" "  ❌ 신원 $S12 committer: 신원 메일 — " \
  "LEAK_HIT commits:$HEADC commits=1 " "공개 저장소에 두면 안 되는 식별자가 있다" "!신원 메일 규칙(noreply 만 통과)을 보지 않는다"
verdict maintainer-corp-identity-exit1

# 중간 커밋 — 첫 커밋이 더한 줄을 다음 커밋이 지웠다. 범위 두 끝(tip 대비)은 깨끗하다 — 커밋마다 봐야 잡힌다
new_cell intermediate-home-path-exit1; published_base
put notes.md "작업 경로 $HOMEP/notes"; commit "작업"; CA="$HEADC"
rm -f "$R/notes.md" || die "rm notes.md"; commit "정리"; CB="$HEADC"
hook intermediate-home-path-exit1 "$B" "refs/heads/main $CB refs/heads/main $C0"
want 1 "  ❌ 추가 줄 ${CA:0:12} notes.md:1: 개인 홈 경로 — " "!추가 줄 ${CB:0:12} " "LEAK_HIT commits:$CB commits=2 "
verdict intermediate-home-path-exit1

new_cell message-ticket-key-exit1; published_base
put b.md "둘째"; commit "정리 $KEYP"; S12="${HEADC:0:12}"
hook message-ticket-key-exit1 "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 1 "  ❌ 메시지 $S12:1: 티켓 키 꼴 — " "LEAK_HIT commits:$HEADC commits=1 "
verdict message-ticket-key-exit1

# 태그만 민다 — 가리키는 커밋은 이미 원격에 있어 커밋 범위가 비고, 주석 태그의 tagger 만 걸린다
new_cell tag-only-corp-tagger-exit1; maintainer rules; published_base
GX_MAIL="$CORPM"; gi -C "$R" tag -a -m "v1 출하" v1 "$C0"; GX_MAIL=""
TAGO="$(gx -C "$R" rev-parse refs/tags/v1)" && [ -n "$TAGO" ] || die "태그 객체 이름"
hook tag-only-corp-tagger-exit1 "$B" "refs/tags/v1 $TAGO refs/tags/v1 $Z40"
want 1 "  ❌ tagger refs/tags/v1: 신원 메일 — " "  ❌ tagger refs/tags/v1: 비공개 규칙" \
  "LEAK_HIT commits:$TAGO commits=0 annotated=1 lightweight=0 "
verdict tag-only-corp-tagger-exit1

# 낡은 추적 ref — origin/main 이 원격에 없는 옛 커밋(X1)을 가리킨다(강제 push 뒤 prune 전). 추적 ref 로 범위를 빼면 X1 이 빠진다
#    (대조: rev-list --not --remotes 가 1개) — 훅은 ls-remote 의 원격 tip 으로 빼서 X1 을 본다
new_cell stale-tracking-ref; published_base
put notes.md "작업 경로 $HOMEP/notes"; commit "옛 작업"; X1="$HEADC"
gi -C "$R" update-ref refs/remotes/origin/main "$X1"
put b.md "둘째"; commit "새 작업"
NR="$(gx -C "$R" rev-list --count HEAD --not --remotes)"
[ "$NR" = 1 ] || WHY="$WHY · 대조 실패: 추적 ref 기준 범위가 ${NR:-(없음)}개 — origin/* 가 옛 커밋을 가리키지 않는다"
hook stale-tracking-ref "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 1 "  ❌ 추가 줄 ${X1:0:12} notes.md:1: 개인 홈 경로 — " "LEAK_HIT commits:$HEADC commits=2 "
verdict stale-tracking-ref

# git 실패 — 로컬에 없는 객체를 민다고 적은 줄. 정본이 범위를 풀지 못해 exit 2 · 훅은 미판정으로 막는다
new_cell git-fail-blocks; published_base
hook git-fail-blocks "$B" "refs/heads/main $MISS refs/heads/main $C0"
want 1 "UNRUN: 기준 ref 를 풀지 못했다: $MISS" "누수 검사 미판정(" "정본 exit 2"
verdict git-fail-blocks

new_cell maintainer-no-rules-exit1; maintainer; published_base
put b.md "둘째"; commit "다음"
hook maintainer-no-rules-exit1 "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 1 "UNRUN: 유지관리자 표지가 있는데 비공개 규칙 파일이 없다" "누수 검사 미판정("
verdict maintainer-no-rules-exit1

# ls-remote 실패 — 원격 tip 을 모르면 원격에 없는 커밋의 범위를 정할 수 없다. 내용이 깨끗해도 막고 정본을 부르지 않는다
new_cell ls-remote-fail-blocks; put a.md "깨끗"; commit "base"
hook ls-remote-fail-blocks "$WORK/ls-remote-fail-blocks/absent.git" "refs/heads/main $HEADC refs/heads/main $Z40"
want 1 "원격 tip 을 읽지 못했다" "누수 검사 미판정" "!LEAK_"
verdict ls-remote-fail-blocks

# 원격 URL 의 사용자 정보(자격 증명)는 훅이 내는 줄에 싣지 않는다 — 터미널 · CI 로그에 토큰이 찍히지 않게. '-' 로 시작하는 URL 은
#    git 을 부르지 않고 막는 길이라 훅 자신의 출력만 본다(git 이 내는 오류 줄은 이 셀 밖이다)
new_cell url-credentials-redacted; put a.md "깨끗"; commit "base"
TOKP="s3cr3t-tok"
hook url-credentials-redacted "-https://fz-user:$TOKP@127.0.0.1/x.git" "refs/heads/main $HEADC refs/heads/main $Z40"
want 1 "원격 URL 이 비었거나 '-' 로 시작한다('-https://(사용자 정보 걷음)@127.0.0.1/x.git')" \
  "원격 tip 을 읽지 못했다(git exit 2 — -https://(사용자 정보 걷음)@127.0.0.1/x.git)" "!$TOKP" "!fz-user" "!LEAK_"
verdict url-credentials-redacted

# ── 검사한 커밋 집합 ↔ 러너가 따로 계산한 기대 집합 ──
# 원격 tip 둘 — main(C0 · 로컬에서 풀린다)과 other(원격에만 있는 커밋 · 풀리지 않는다). 풀리는 tip 만 빼야 한다: 풀리지 않는 tip 을
#    넘기면 정본이 판정 불가로 끝나고(끝 줄 수 없음 · UNRUN), 모든 tip 을 버리면 C0 까지 세어 3개가 된다
new_cell unresolved-remote-tip-coverage; published_base; remote_only refs/heads/other
put notes.md "작업 경로 $HOMEP/notes"; commit "작업"; CA="$HEADC"
put b.md "둘째"; commit "다음"; LT="$HEADC"
hook unresolved-remote-tip-coverage "$B" "refs/heads/main $LT refs/heads/main $C0"
! gx -C "$R" cat-file -e "$RONLY" 2>/dev/null || WHY="$WHY · 대조 실패: 원격 전용 tip 객체가 로컬에 있다"
expect "$B" "$LT"; [ "$EXP" = 2 ] || WHY="$WHY · 대조 실패: 기대 커밋 수 ${EXP:-(없음)} ≠ 2"
want 1 "  ❌ 추가 줄 ${CA:0:12} notes.md:1: 개인 홈 경로 — " "뺀 원격 tip 1개 · 풀리지 않아 빼지 않은 tip 1개" "!UNRUN:"
cover "$LT"
verdict unresolved-remote-tip-coverage

# ref 둘 — 깨끗한 가지(clean)와 오염된 가지(dirty). 두 순서 모두 두 ref 를 다 본다(첫 줄에서 끝내지 않는다 · 적중 뒤에도 계속)
new_cell multiple-ref-coverage; published_base
gi -C "$R" checkout -q -b clean; put c.md "깨끗한 가지"; commit "깨끗"; LC="$HEADC"
gi -C "$R" checkout -q -b dirty main; put d.md "작업 경로 $HOMEP/d"; commit "오염"; LD="$HEADC"
RUNL="깨끗 → 오염:"
hook multiple-ref-coverage.clean-first "$B" "refs/heads/clean $LC refs/heads/clean $Z40" "refs/heads/dirty $LD refs/heads/dirty $Z40"
want 1 "LEAK_CLEAN commits:$LC commits=1 " "  ❌ 추가 줄 ${LD:0:12} d.md:1: 개인 홈 경로 — " "LEAK_HIT commits:$LD commits=1 " "!UNRUN:"
expect "$B" "$LC"; cover "$LC"; expect "$B" "$LD"; cover "$LD"
RUNL="오염 → 깨끗:"
hook multiple-ref-coverage.dirty-first "$B" "refs/heads/dirty $LD refs/heads/dirty $Z40" "refs/heads/clean $LC refs/heads/clean $Z40"
want 1 "LEAK_HIT commits:$LD commits=1 " "LEAK_CLEAN commits:$LC commits=1 " "!UNRUN:"
expect "$B" "$LC"; cover "$LC"; expect "$B" "$LD"; cover "$LD"
verdict multiple-ref-coverage

# 원격에 ref 가 하나도 없다(첫 push) — 뺄 tip 이 없어 루트부터 전부 본다
new_cell empty-remote-first-push
put a.md "깨끗"; commit "첫"; put b.md "둘째"; commit "둘째"
hook empty-remote-first-push "$B" "refs/heads/main $HEADC refs/heads/main $Z40"
want 0 "LEAK_CLEAN commits:$HEADC commits=2 " "!UNRUN:"
expect "$B" "$HEADC"; [ "$EXP" = 2 ] || WHY="$WHY · 대조 실패: 기대 커밋 수 ${EXP:-(없음)} ≠ 2"; cover "$HEADC"
verdict empty-remote-first-push

# 목적지 ref 이름 — 깨끗한 커밋을 티켓 키 꼴 이름의 브랜치로 밀면 그 이름이 공개된다. 로컬 이름이 깨끗해도 목적지 이름을 본다.
#    우회 안내는 출하 게이트가 무엇을 다시 보는지 그대로 적는다('마지막 관문' 이라 적지 않는다)
new_cell dest-ref-name-exit1; published_base
put b.md "둘째"; commit "다음"
hook dest-ref-name-exit1 "$B" "refs/heads/main $HEADC refs/heads/feature/$KEYP $Z40"
want 1 "  ❌ ref 이름 feature/$KEYP: 티켓 키 꼴 — $KEYP" "LEAK_HIT commits:$HEADC commits=1 " "!마지막 관문" \
  "출하하지 않는 브랜치를 우회해 밀면 어느 검사도 보지 않는다"
verdict dest-ref-name-exit1

# 태그 이름 — 가벼운 태그는 tagger · 주석 칸이 없지만 이름은 그대로 공개된다
new_cell tag-name-exit1; published_base
put b.md "둘째"; commit "다음"; gi -C "$R" tag "$KEYP"
hook tag-name-exit1 "$B" "refs/tags/$KEYP $HEADC refs/tags/$KEYP $Z40"
want 1 "  ❌ 태그 이름 $KEYP: 티켓 키 꼴 — $KEYP" "lightweight=1 "
verdict tag-name-exit1

# 태그 객체를 태그 ref 가 아닌 이름으로 민다 — --tag 로 넘길 이름이 없어 tagger · 주석을 볼 수 없다. 통과시키지 않는다
new_cell tag-oid-under-branch-ref-exit1; published_base; maintainer rules
put b.md "둘째"; commit "다음"
GX_MAIL="$CORPM"; gi -C "$R" tag -a v9 -m "주석"; GX_MAIL=""
TOID="$(gx -C "$R" rev-parse refs/tags/v9)" && [ -n "$TOID" ] || die "태그 객체 이름"
hook tag-oid-under-branch-ref-exit1 "$B" "$TOID $TOID refs/heads/x $Z40"
want 1 "태그 객체를 태그 ref 가 아닌 이름" "누수 검사 미판정 1건" "!LEAK_CLEAN"
verdict tag-oid-under-branch-ref-exit1

# 형식 밖 갱신 줄(칸 셋) — 범위를 정하지 못한 것이라 건너뛰지 않고 막는다
new_cell malformed-ref-line-exit1; published_base
put b.md "둘째"; commit "다음"
hook malformed-ref-line-exit1 "$B" "refs/heads/main $HEADC refs/heads/main"
want 1 "ref 갱신 줄을 읽지 못했다" "!LEAK_CLEAN"
verdict malformed-ref-line-exit1

# 원격에 있는 주석 태그 객체를 로컬에서 '미공개 커밋을 가리키는 태그 객체' 로 바꿔치기(replace ref)한다. 훅이 replace 를 따르면
#    그 태그를 벗긴 결과가 미공개 커밋이 되어 '원격이 가진 tip' 으로 빠진다 — 범위가 비어 commits=0 으로 통과한다
new_cell replaced-remote-tag-exit1; published_base
gi -C "$R" tag -a -m "v1" v1 "$C0"; gi -C "$R" push -q "$B" refs/tags/v1
TOLD="$(gx -C "$R" rev-parse refs/tags/v1)" && [ -n "$TOLD" ] || die "원격 태그 객체 이름"
put notes.md "작업 경로 $HOMEP/notes"; commit "다음"
gi -C "$R" tag -a -m "x" tmp-x "$HEADC"
TNEW="$(gx -C "$R" rev-parse refs/tags/tmp-x)" && [ -n "$TNEW" ] || die "바꿔치기 태그 객체 이름"
gi -C "$R" tag -d tmp-x; gi -C "$R" replace "$TOLD" "$TNEW"
hook replaced-remote-tag-exit1 "$B" "refs/heads/main $HEADC refs/heads/main $C0"
want 1 "  ❌ 추가 줄 ${HEADC:0:12} notes.md:1: 개인 홈 경로 — " "LEAK_HIT commits:$HEADC commits=1 "
verdict replaced-remote-tag-exit1

# 훅의 실행 비트 — 이 러너는 훅을 `bash "$HOOK"` 로 부르므로 0644 여도 다른 셀은 통과한다. git 은 실행 비트 없는 훅을 건너뛴다
[ -x "$HOOK" ] || WHY="$WHY · .githooks/pre-push 에 실행 비트가 없다 — git 이 이 훅을 건너뛴다"
verdict hook-exec-bit

# 부모 git 의 `-c` 설정을 물려받은 실행 — 유지관리자 표지를 env 로 밀어 넣어도 셀 결과가 같아야 한다(끊지 않으면 표지 없는 셀이 막힌다).
#    자식은 이 셀을 다시 돌지 않는다
if [ -z "${FZ_PREPUSH_CHILD:-}" ]; then
  CH_OUT="$(FZ_PREPUSH_CHILD=1 GIT_CONFIG_PARAMETERS="'fz.maintainer=true'" bash "${BASH_SOURCE[0]}" --tree "$TREE" 2>&1)"; CH_RC=$?
  [ "$CH_RC" = 0 ] || WHY="$WHY · 부모 git 설정을 물려받은 자식 실행이 exit $CH_RC (기대 0) — $(printf '%s' "$CH_OUT" | /usr/bin/grep -m 3 '^FAIL' | tr '\n' ' ' | cut -c1-300)"
  verdict host-config-params-ignored
fi

if [ "$nfail" -eq 0 ] && [ "$npass" -gt 0 ]; then
  echo "PRE_PUSH_OK (셀 ${npass}개 — 트리의 push 훅을 직접 실행한 종료 코드 · 실패한 축의 줄 · 검사 커밋 집합)"
  exit 0
fi
echo "pre-push: 실패 ${nfail}건 · 통과 ${npass}건"
exit 1
