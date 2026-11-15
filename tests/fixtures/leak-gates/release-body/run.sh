#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 읽지 않는다. 누수 규칙 정본을 가짜 gh 와 돌려 종료 코드 · 출력 줄(고정 글자) · 가짜가 받은 호출만 본다
# modes: default caller=health
# 릴리스 본문 검사(scripts/leak_rules.py --release-body) 회귀 — 발행된 릴리스의 제목 · 본문을 노트 파일 검사(--text-file)와 같은 판정으로
#   보는지, 본문을 읽지 못하면(gh 부재 · gh 실패 · JSON 아닌 출력 · 빈 본문) 판정 불가(2)로 끝나는지 트리의 정본을 직접 실행해 단언한다.
# ⛔ gh 는 가짜(_shim/gh)다 — 임시 폴더에 gh 로 복사해 PATH 맨 앞에 둔다(네트워크 · 실제 GitHub 에 닿지 않는다). 가짜는 받은 호출을
#    실행마다 기록하고 러너는 그 기록이 `release view <태그> --json name,body` 한 줄인지 단언한다 — 가짜가 아닌 gh 가 불리면 기록이 비어
#    실패한다. GitHub 인증 env 는 걷고 gh 설정 폴더는 빈 임시 폴더로 둔다(가짜가 가려져도 진짜 gh 가 인증해 닿지 않게)
# ⛔ gh 부재 셀은 PATH 를 빈 폴더 하나로 좁힌다 — 진짜 gh 가 깔린 머신에서도 부재다(그 PATH 에서 gh 가 보이면 준비 실패). 그래서 파이썬은
#    PATH 가 아니라 실제 실행 파일 경로로 부른다
# ⛔ 음성 토큰(홈 경로 · 키 꼴 · 합성 회사 이름)은 쪼개 적고 실행할 때 잇는다 — 이 파일이 누수 규칙 · 커밋 훅에 걸리지 않게. 비공개 규칙
#    파일(합성 회사 이름 한 줄)은 임시 폴더에 둔다. exit 1 셀은 적중 줄(자리 · 라벨 · 토큰)과 적중 수까지 단언한다(종료 코드만 보면 다른
#    적중으로도 통과한다)
# 셀(기대 exit):
#   0    body-clean-exit0(자리표시 경로 · 예약 번호만 든 제목 · 본문 — 가짜가 받은 호출 한 줄)
#   1    body-home-exit1 · body-private-rule-exit1(임시 규칙 파일 — 대조: 같은 본문을 규칙 없이 보면 0) · title-home-exit1(본문은 깨끗하고
#        제목에만 위반) · notes-file-same-rules-exit1(같은 글자를 노트 파일로 --text-file — 같은 줄 · 라벨 · 토큰 · 적중 수) ·
#        published-body-differs-exit1(발행 전 노트 파일은 0 · 가짜 gh 가 돌려주는 발행 본문에만 위반 → 발행 뒤 검사 1) · shim-body-ticket-exit1
#   2    gh-absent-exit2 · shim-gh-exit1-unrun(gh 가 0 이 아닌 값으로 끝남 — 인증 만료 · 오프라인 · 그 태그의 릴리스 없음) ·
#        shim-empty-body-unrun(빈 본문 · 공백 줄만) · shim-not-json-unrun — 가짜의 본문에 위반이 있어도 읽지 못했으면 2 이고, 끝 줄
#        `LEAK_UNRUN release-body:<태그> files=0` 까지 본다
# 출력: 셀마다 `PASS <셀>` 또는 `FAIL <셀> — 사유` + 그 셀이 돌린 정본 출력과 가짜 gh 호출 기록의 끝 20줄씩(들여씀). 전건 통과면
#   `RELEASE_BODY_OK …`
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — 인자 · 도구 · 대상 부재 · 임시 폴더 · 가짜 gh 배치 · gh 부재 환경)
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
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 부재 — 정본을 돌릴 수 없다"; exit 2; }
LR="$TREE/scripts/leak_rules.py" SHIM="$TREE/tests/fixtures/leak-gates/release-body/_shim/gh"
for f in "$LR" "$SHIM"; do [ -f "$f" ] || { echo "UNRUN: 대상 부재 — ${f#$TREE/}"; exit 2; }; done
# 파이썬은 실제 실행 파일 경로로 부른다 — gh 부재 셀이 PATH 를 빈 폴더로 좁혀도 정본이 돈다
PY="$(python3 -c 'import sys; print(sys.executable)' 2>/dev/null)"
{ [ -n "$PY" ] && [ -x "$PY" ]; } || { echo "UNRUN: 파이썬 실행 파일 경로를 얻지 못했다"; exit 2; }

# 비공개 규칙은 --rules 로만 준다. GitHub 인증 · 대상 env 는 걷는다 — 가짜가 가려져 진짜 gh 가 불려도 인증해 닿지 않게
unset FZ_NEUTRALIZE_RULES GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN GH_HOST GH_REPO
WORK="$(mktemp -d "${TMPDIR:-/tmp}/fz-relbody.XXXXXX")" && [ -n "$WORK" ] && [ -d "$WORK" ] \
  || { echo "UNRUN: 임시 폴더를 만들지 못했다"; exit 2; }
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/out" "$WORK/tmp" "$WORK/bin" "$WORK/bare" "$WORK/ghcfg" "$WORK/c" || { echo "UNRUN: 임시 폴더 준비 실패"; exit 2; }
# 바이트코드를 쓰지 않는다. 임시 파일도 WORK 안이다. gh 설정 폴더는 빈 임시 폴더다
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 TMPDIR="$WORK/tmp" GH_CONFIG_DIR="$WORK/ghcfg"
# 가짜 gh — 임시 폴더에 gh 로 두고 PATH 맨 앞에 붙인다. 대조: 그 PATH 에서 `gh` 가 가짜다 · 빈 폴더만 든 PATH 에서는 gh 가 없다
{ cp "$SHIM" "$WORK/bin/gh" && chmod 755 "$WORK/bin/gh"; } || { echo "UNRUN: 가짜 gh 를 임시 폴더에 두지 못했다"; exit 2; }
( PATH="$WORK/bin:$PATH"; gh --version ) 2>/dev/null | /usr/bin/grep -qF "(fixture shim)" \
  || { echo "UNRUN: 가짜 gh 가 PATH 맨 앞에서 불리지 않는다 — 셀이 진짜 gh 에 닿을 수 있다"; exit 2; }
if ( PATH="$WORK/bare"; command -v gh ) >/dev/null 2>&1; then
  echo "UNRUN: 빈 폴더만 든 PATH 에서도 gh 가 보인다 — gh 부재 환경을 만들지 못했다"; exit 2
fi

TAG=v1.0.0
# 음성 토큰 — 쪼개 적고 실행할 때 잇는다. 비공개 규칙은 합성 회사 이름 하나다
CORPN="qzbody""corp"; HOMEP="/Us""ers/alice"; KEYP="AB""C-4821"
RULES="$WORK/rules-corp.txt"
printf '%s\n' '# 합성 비공개 규칙(시험용) — 한 줄 한 정규식' "(?i)$CORPN" > "$RULES" || { echo "UNRUN: 규칙 파일을 만들지 못했다"; exit 2; }

npass=0 nfail=0 WHY="" SHOW="" RUNL="" RC="" OUT="" CALLS="" CELL=""
die() { echo "UNRUN: 픽스처 준비 실패 — $* (⛔ 통과 아님)"; exit 2; }
use_cell() {   # $1=셀 — 셀 폴더 CELL(정본의 cwd)과 가짜 gh 의 응답 env 를 새로 둔다: 아는 태그 TAG · 제목 '<TAG> 출하' · 본문 파일
               #    CELL/body.md · 종료 0 · JSON 출력. 음성 셀은 이 가운데 하나만 바꾼다
  CELL="$WORK/c/$1"
  mkdir -p "$CELL" || die "mkdir c/$1"
  export FZ_GH_SHIM_TAG="$TAG" FZ_GH_SHIM_TITLE="$TAG 출하" FZ_GH_SHIM_BODY="$CELL/body.md" FZ_GH_SHIM_EXIT=0 FZ_GH_SHIM_RAW=0
}
put() {   # $1=파일 · 나머지=줄 — 줄마다 개행으로 쓴다(줄을 주지 않으면 빈 파일)
  local p="$1"; shift
  if [ $# -eq 0 ]; then
    : > "$p" || die "쓰기 ${p#$WORK/}"
  else
    printf '%s\n' "$@" > "$p" || die "쓰기 ${p#$WORK/}"
  fi
}
run_lr() {   # $1=PATH · $2=출력 이름 · 나머지=정본 인자 — 셀 폴더를 cwd 로 트리의 정본을 돌린다. 출력 OUT · 종료 코드 RC ·
             #    가짜 gh 의 호출 기록 CALLS(실행마다 새 파일 — 가짜가 불리지 않으면 없다)
  local path="$1" name="$2"; shift 2
  OUT="$WORK/out/$name.txt" CALLS="$WORK/out/$name.calls"; SHOW="$SHOW$OUT"$'\n'"$CALLS"$'\n'
  (cd "$CELL" && FZ_GH_SHIM_LOG="$CALLS" PATH="$path" "$PY" "$LR" "$@") > "$OUT" 2>&1
  RC=$?
}
lr() { run_lr "$WORK/bin:$PATH" "$@"; }   # 가짜 gh 가 PATH 맨 앞이다
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
called() {   # $1=기대 수 · $2=태그(빈 값 = TAG) — 이 실행의 가짜 gh 기록(CALLS)에 `CALL release view <태그> --json name,body` 가 그 수만큼
             #    있고 다른 줄(다른 호출 · 거부한 호출 UNSUPPORTED)이 없는가 — 정본이 gh 를 무엇으로 몇 번 불렀는지 본다
  local line="CALL release view ${2:-$TAG} --json name,body" n=0 other=0
  if [ -f "$CALLS" ]; then
    n="$(/usr/bin/grep -cxF -- "$line" "$CALLS")"
    other="$(/usr/bin/grep -cvxF -- "$line" "$CALLS")"
  fi
  [ "$n" = "$1" ] || WHY="$WHY · ${RUNL:+$RUNL }가짜 gh 가 받은 호출 ${n}번(기대 ${1}번 — $line)"
  [ "$other" = 0 ] || WHY="$WHY · ${RUNL:+$RUNL }가짜 gh 기록의 다른 줄 ${other}개(다른 호출 · 거부)"
}
verdict() {   # $1=셀 — WHY 가 비었으면 PASS · 아니면 FAIL + 사유 + 그 셀이 돌린 정본 출력 · 가짜 gh 호출 기록의 끝 20줄. WHY · SHOW · RUNL 을 비운다
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

# ── 대조(0) — 자리표시 경로 · 예약 번호만 든 제목과 본문은 깨끗하고, 정본은 gh 를 `release view <태그> --json name,body` 로 한 번 부른다 ──
use_cell body-clean-exit0
put "$FZ_GH_SHIM_BODY" "# $TAG — 출하 노트" '' "- 자리표시 경로 /Us""ers/example/work 만 남겼다" "- 예약 번호 TK""T-0123 은 통과한다"
lr body-clean-exit0 --release-body "$TAG"
want 0 "LEAK_CLEAN release-body:$TAG files=1 rules=0(없음)" "!  ❌ " "!UNRUN:"
called 1
verdict body-clean-exit0

# ── 위반(1) — 발행된 제목 · 본문의 적중 줄(자리 · 라벨 · 토큰)과 적중 수 ──
use_cell body-home-exit1
put "$FZ_GH_SHIM_BODY" "# $TAG — 출하 노트" "작업 경로 $HOMEP/notes"
lr body-home-exit1 --release-body "$TAG"
want 1 "  ❌ $TAG 본문:2: 개인 홈 경로 — $HOMEP/" "LEAK_HIT release-body:$TAG files=1 rules=0(없음) hits=1"
called 1
verdict body-home-exit1

# 비공개 규칙 토큰 — 임시 규칙 파일로 잡힌다. 대조: 같은 본문을 규칙 없이 보면 0 이다(적중이 규칙 파일에서 온다)
use_cell body-private-rule-exit1
put "$FZ_GH_SHIM_BODY" "# $TAG — 출하 노트" '' "문의는 $CORPN 팀으로"
RUNL="규칙 파일:"; lr body-private-rule-exit1.rules --release-body "$TAG" --rules "$RULES"
want 1 "  ❌ $TAG 본문:3: 비공개 규칙 2 — $CORPN" "LEAK_HIT release-body:$TAG files=1 rules=1(--rules) hits=1"
called 1
RUNL="규칙 없음:"; lr body-private-rule-exit1.none --release-body "$TAG"
want 0 "LEAK_CLEAN release-body:$TAG files=1 rules=0(없음)"
called 1
RUNL=""; verdict body-private-rule-exit1

# 제목도 본다 — 본문은 깨끗하고 제목에만 위반이 있다
use_cell title-home-exit1
FZ_GH_SHIM_TITLE="$TAG — $HOMEP/release 에서 정리"
put "$FZ_GH_SHIM_BODY" "# $TAG — 출하 노트" '' "- 정리했다"
lr title-home-exit1 --release-body "$TAG"
want 1 "  ❌ $TAG 제목:1: 개인 홈 경로 — $HOMEP/" "!$TAG 본문:" "LEAK_HIT release-body:$TAG files=1 rules=0(없음) hits=1"
called 1
verdict title-home-exit1

# 같은 규칙 — 같은 글자를 노트 파일(--text-file)과 발행 본문(--release-body)으로 보면 적중 줄 · 라벨 · 토큰 · 수가 같다
use_cell notes-file-same-rules-exit1
put "$CELL/note.md" "# $TAG — 출하 노트" "작업 경로 $HOMEP/notes" "문의는 $CORPN 팀으로" "정리 $KEYP"
cp "$CELL/note.md" "$FZ_GH_SHIM_BODY" || die "복사 note.md"
RUNL="노트 파일:"; lr notes-file-same-rules-exit1.text --text-file note.md --rules "$RULES"
want 1 "  ❌ note.md:2: 개인 홈 경로 — $HOMEP/" "  ❌ note.md:3: 비공개 규칙 2 — $CORPN" "  ❌ note.md:4: 티켓 키 꼴 — $KEYP" \
  "LEAK_HIT text-file files=1 rules=1(--rules) hits=3"
called 0
RUNL="발행 본문:"; lr notes-file-same-rules-exit1.body --release-body "$TAG" --rules "$RULES"
want 1 "  ❌ $TAG 본문:2: 개인 홈 경로 — $HOMEP/" "  ❌ $TAG 본문:3: 비공개 규칙 2 — $CORPN" "  ❌ $TAG 본문:4: 티켓 키 꼴 — $KEYP" \
  "LEAK_HIT release-body:$TAG files=1 rules=1(--rules) hits=3"
called 1
RUNL=""; verdict notes-file-same-rules-exit1

# 발행 본문만 다르다 — 발행 전 노트 파일은 깨끗하다(발행 전 검사 0). 가짜 gh 가 돌려주는 발행 본문은 노트에 없던 줄(커밋 메시지에서
#    지은 본문처럼)을 더 담는다 — 발행 뒤 검사만 잡는다(1)
use_cell published-body-differs-exit1
put "$CELL/note.md" "# $TAG — 출하 노트" '' "- 정리했다"
put "$FZ_GH_SHIM_BODY" "# $TAG — 출하 노트" '' "- 정리했다" "- 커밋에서 온 줄: $HOMEP/scratch 정리"
RUNL="발행 전:"; lr published-body-differs-exit1.pre --text-file note.md --rules "$RULES"
want 0 "LEAK_CLEAN text-file files=1 rules=1(--rules)"
called 0
RUNL="발행 뒤:"; lr published-body-differs-exit1.post --release-body "$TAG" --rules "$RULES"
want 1 "  ❌ $TAG 본문:4: 개인 홈 경로 — $HOMEP/" "LEAK_HIT release-body:$TAG files=1 rules=1(--rules) hits=1"
called 1
RUNL=""; verdict published-body-differs-exit1

# 티켓 키 꼴 — 발행 본문의 키 꼴 토큰
use_cell shim-body-ticket-exit1
put "$FZ_GH_SHIM_BODY" "# $TAG — 출하 노트" '' "- $KEYP 대응"
lr shim-body-ticket-exit1 --release-body "$TAG" --rules "$RULES"
want 1 "  ❌ $TAG 본문:3: 티켓 키 꼴 — $KEYP" "LEAK_HIT release-body:$TAG files=1 rules=1(--rules) hits=1"
called 1
verdict shim-body-ticket-exit1

# ── 판정 불가(2) — 본문을 읽지 못하면 위반이 든 본문이어도 적중을 내지 않고 2 다 ──
# gh 부재 — PATH 를 빈 폴더 하나로 좁힌다(진짜 gh 가 깔린 머신에서도 부재)
use_cell gh-absent-exit2
put "$FZ_GH_SHIM_BODY" "작업 경로 $HOMEP/notes"
run_lr "$WORK/bare" gh-absent-exit2 --release-body "$TAG" --rules "$RULES"
want 2 "UNRUN: gh 가 없다" "LEAK_UNRUN release-body:$TAG files=0 rules=1(--rules) unrun=1 hits=0" "!  ❌ "
called 0
verdict gh-absent-exit2

# gh 가 0 이 아닌 값으로 끝난다 — 인증 만료 · 오프라인(가짜가 실패 코드로 끝난다) · 그 태그의 릴리스 없음(가짜가 모르는 태그)
use_cell shim-gh-exit1-unrun
put "$FZ_GH_SHIM_BODY" "작업 경로 $HOMEP/notes"
FZ_GH_SHIM_EXIT=1
RUNL="인증 만료 · 오프라인:"; lr shim-gh-exit1-unrun.fail --release-body "$TAG"
want 2 "UNRUN: gh release view $TAG 실패(exit 1) — HTTP 401" "LEAK_UNRUN release-body:$TAG files=0 " "!  ❌ "
called 1
FZ_GH_SHIM_EXIT=0
RUNL="릴리스 없음:"; lr shim-gh-exit1-unrun.missing --release-body v9.9.9
want 2 "UNRUN: gh release view v9.9.9 실패(exit 1) — release not found" "LEAK_UNRUN release-body:v9.9.9 files=0 " "!  ❌ "
called 1 v9.9.9
RUNL=""; verdict shim-gh-exit1-unrun

# 빈 본문 — 빈 파일 · 공백 줄만. '본문 없음 = 통과' 로 읽지 않는다
use_cell shim-empty-body-unrun
put "$FZ_GH_SHIM_BODY"
RUNL="빈 본문:"; lr shim-empty-body-unrun.empty --release-body "$TAG"
want 2 "UNRUN: gh release view $TAG 의 본문이 비었다" "LEAK_UNRUN release-body:$TAG files=0 "
called 1
put "$FZ_GH_SHIM_BODY" '' '   ' ''
RUNL="공백 줄만:"; lr shim-empty-body-unrun.blank --release-body "$TAG"
want 2 "UNRUN: gh release view $TAG 의 본문이 비었다" "LEAK_UNRUN release-body:$TAG files=0 "
called 1
RUNL=""; verdict shim-empty-body-unrun

# JSON 이 아닌 출력 — 가짜가 본문 파일을 그대로 낸다
use_cell shim-not-json-unrun
put "$FZ_GH_SHIM_BODY" "작업 경로 $HOMEP/notes"
FZ_GH_SHIM_RAW=1
lr shim-not-json-unrun --release-body "$TAG"
want 2 "UNRUN: gh release view $TAG 의 출력이 JSON 이 아니다" "LEAK_UNRUN release-body:$TAG files=0 " "!  ❌ "
called 1
verdict shim-not-json-unrun

if [ "$nfail" -eq 0 ] && [ "$npass" -gt 0 ]; then
  echo "RELEASE_BODY_OK (셀 ${npass}개 — 발행된 릴리스 본문 검사(--release-body)의 종료 코드 · 적중 줄 · 가짜 gh 호출 · 노트 파일 검사와 같은 판정)"
  exit 0
fi
echo "release-body: 실패 ${nfail}건 · 통과 ${npass}건"
exit 1
