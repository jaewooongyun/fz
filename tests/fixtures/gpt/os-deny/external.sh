#!/bin/bash
# 권한 프로필 OS 차단 실증 (F-348 오라클 (b) · E1-9) — 실 GPT CLI 의 로컬 샌드박스 하위 명령(`sandbox`, macOS seatbelt)으로
# 격리 프로필이 금지 경로 읽기와 쓰기를 OS 수준에서 막는지 4셀로 잰다. 모델을 부르지 않는다(로그인 · 네트워크 불필요).
#
# ⛔ health-check 글롭(tests/fixtures/*/*/run.sh) 밖 러너다 — 실 CLI 가 필요하므로 인자 없이 도는 휴대 회귀 셀이 될 수 없다.
#    게이트만 `bash external.sh --tree <플러그인 루트>` 로 부른다. 환경이 안 되면 UNRUN 이고, UNRUN 은 PASS 가 아니다.
# ⛔ 프로필은 config-permissions/run.sh 의 good 모양 그대로다(첫 table 앞 default_permissions · extends = ":read-only" ·
#    filesystem deny). 래퍼 `gpt-exec.sh --config-permissions` 의 사전 게이트가 통과시키는 모양이고, 그 경로는 sandbox_mode 를
#    넘기지 않는다. 그래서 셀은 `-c` · `-P` · `-C` 없이 임시 CODEX_HOME 의 default_permissions 만으로 돈다.
#    (`-c sandbox_mode=…` 를 함께 주면 이 프로필의 deny 가 사라진다 — F-348 이 래퍼 기본 경로에서 본 덮어쓰기)
#
# 셀
#   allow-read          프로필 · 작업 폴더 파일 읽기 → exit 0 · 내용 마커 있음(선택적 차단의 양성 대조)
#   deny-read           프로필 · 금지 폴더 파일 읽기 → exit≠0 · `<그 경로>: Operation not permitted` · 비밀 마커 없음
#   write-block         프로필 · 작업 폴더 안 · 금지 폴더 쓰기 → 각각 exit≠0 · `<그 경로>: Operation not permitted` · 파일 없음
#   no-profile-control  프로필 없는 CODEX_HOME · 같은 금지 파일 읽기 → exit 0 · 비밀 마커 있음(차단이 프로필에서 온다)
# 증거: 셀마다 명령 · exit · 매칭 줄. 대상 경로가 든 거부 줄만 증거다 — 다른 경로의 거부(xcrun 캐시 등)는 세지 않는다(AC-11).
#    명령은 /bin/cat · /bin/sh 절대경로다(샌드박스 안 PATH 가 바뀐다). 경로는 `pwd -P` 값이다(/var → /private/var 심볼릭).
# 승인 프롬프트: `sandbox` 하위 명령에는 승인 흐름이 없다(--help 의 approval 언급 수를 찍는다). stdin 은 늘 </dev/null 이다.
# 상한: 호출마다 FZ_OS_DENY_CAP 초(기본 20). macOS 에 timeout 이 없어 감시 서브셸이 재고, 넘으면 프로세스 트리
#    (node 래퍼 → 네이티브 → sandbox-exec → 명령)를 죽이고 그 셀을 FAIL 로 센다.
# UNRUN(exit 2 · 줄 맨 앞 `UNRUN:`): 비 macOS · CLI 부재 · 중첩 샌드박스(CODEX_SANDBOX 설정 · `sandbox_apply` 거부) ·
#    `--version` 실패 · `sandbox` 하위 명령 없음(남는 실증 경로는 모델 호출뿐). 그 밖의 어긋남은 FAIL 이다 — UNRUN 으로 세탁하지 않는다.
# 출력: `EVIDENCE-CLASS=live` 는 4셀을 실 CLI 로 돌렸을 때만(FAIL 포함) · `OS-DENY-CELLS=<PASS 수>/4`.
# exit: 0 4/4 PASS · 1 셀 FAIL · 2 UNRUN · 3 준비 실패(인자 · 상한 값 · 임시 폴더)
# usage: external.sh [--tree <플러그인 루트>]   (기본: 이 파일이 든 트리. 셀은 트리 코드를 부르지 않는다 — 기록용)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
CAP="${FZ_OS_DENY_CAP:-20}"
case "$CAP" in ''|*[!0-9]*|0) echo "SETUP FZ_OS_DENY_CAP 는 양의 정수(초)다: '$CAP'"; exit 3 ;; esac

unrun() { echo "UNRUN: $*"; echo "EVIDENCE-CLASS=none"; exit 2; }

# ⛔ 중첩 판정은 임시 폴더보다 먼저 — 바깥 샌드박스가 read-only 면 mktemp 가 먼저 죽어 UNRUN 이 준비 실패로 보인다
OS="$(uname -s)"
[ "$OS" = Darwin ] || unrun "비 macOS ($OS) — seatbelt 샌드박스가 없다"
[ -z "${CODEX_SANDBOX:-}" ] || unrun "중첩 샌드박스 — CODEX_SANDBOX=${CODEX_SANDBOX} (이미 GPT CLI 샌드박스 안이다)"
# 다른 도구의 바깥 seatbelt(CODEX_SANDBOX 없음)도 같은 이유로 판정 불가다 — 아무것도 막지 않는 정책을 한 번 걸어 본다
# (바깥 정책이 `(allow default)` 처럼 느슨하면 이 선검사는 통과한다 — 그때는 run() 의 `sandbox_apply` 검사가 첫 셀에서 잡는다)
if [ -x /usr/bin/sandbox-exec ]; then
  nest_="$(/usr/bin/sandbox-exec -p '(version 1)(allow default)' /usr/bin/true </dev/null 2>&1)"
  case "$nest_" in *sandbox_apply*) unrun "중첩 샌드박스 — 바깥 seatbelt 안이다 (${nest_})" ;; esac
fi
CLI="$(command -v codex)" || unrun "GPT CLI 부재 — PATH 에 codex 가 없다"

# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 mktemp 가 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-os-deny.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
T="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }
WORK="$T/work"; OUTSIDE="$T/outside"; HP="$T/home-profile"; HN="$T/home-none"
mkdir -p "$WORK" "$OUTSIDE" "$HP" "$HN" || { echo "SETUP 임시 폴더 생성 실패: $T"; exit 3; }
ALLOWED="$WORK/allowed.txt"; SECRET="$OUTSIDE/secret.txt"
printf 'OS-DENY-ALLOWED-MARK-7\n' > "$ALLOWED"; printf 'OS-DENY-SECRET-MARK-7\n' > "$SECRET"
cat > "$HP/config.toml" <<EOF
default_permissions = "iso"

[permissions.iso]
extends = ":read-only"

[permissions.iso.filesystem]
"$OUTSIDE" = "deny"
EOF
: > "$HN/config.toml"

tree_pids() {   # $1=pid — 자손부터 자기까지
  local c
  for c in $(pgrep -P "$1" 2>/dev/null); do tree_pids "$c"; done
  echo "$1"
}
# run <이름> <CODEX_HOME> <명령…> — 작업 폴더에서 · stdin </dev/null · 상한 CAP 초. 결과: RC · CAPPED · OUTF
run() {
  local name="$1" home="$2"; shift 2
  local flag="$T/$name.capped" pid w
  OUTF="$T/$name.out"
  ( cd "$WORK" && exec env CODEX_HOME="$home" "$@" ) </dev/null >"$OUTF" 2>&1 &
  pid=$!
  ( i=0
    while kill -0 "$pid" 2>/dev/null; do
      if [ "$i" -ge $((CAP * 10)) ]; then
        : > "$flag"; ps_="$(tree_pids "$pid")"
        kill -TERM $ps_ 2>/dev/null; sleep 1; kill -KILL $ps_ 2>/dev/null; exit 0
      fi
      sleep 0.1; i=$((i + 1))
    done ) >/dev/null 2>&1 &
  w=$!
  wait "$pid"; RC=$?
  # 상한에 걸렸으면 감시 서브셸이 KILL 까지 마치게 기다린다 — TERM 으로 직속 자식이 먼저 끝나 여기로 돌아와도
  # 감시를 먼저 죽이면 TERM 을 무시한 자손이 남는다
  if [ -e "$flag" ]; then wait "$w" 2>/dev/null; else kill "$w" 2>/dev/null; wait "$w" 2>/dev/null; fi
  CAPPED=0; [ -e "$flag" ] && CAPPED=1
  # 바깥 seatbelt 안에서는 sandbox-exec 가 정책을 걸지 못한다 — 셀 판정이 아니라 환경 문제다
  if grep -q 'sandbox_apply' "$OUTF"; then unrun "중첩 샌드박스 — ${name}: $(grep -m1 'sandbox_apply' "$OUTF")"; fi
  return 0
}
show() {   # $1=이름 · $2=명령 표기 — 경로별 증거
  echo "  [$1] cmd: $2"
  echo "  [$1] exit=$RC · 상한 ${CAP}s$([ "$CAPPED" = 1 ] && echo ' 초과')"
  # CODEX_HOME 이 임시 폴더 아래라 CLI 가 'WARNING: proceeding … PATH aliases' 를 찍는다 — 판정과 무관해 줄 수만 남긴다
  echo "  [$1] CLI 경고 줄 $(grep -c '^WARNING: ' "$OUTF")"
  grep -v '^WARNING: ' "$OUTF" | sed -n '1,3p' | sed "s/^/  [$1] out: /"
}
denied() {   # $1=출력 파일 · $2=대상 경로 → 그 경로의 거부 줄
  grep -F -- "$2: Operation not permitted" "$1" | head -1
}

run version "$HN" "$CLI" --version
[ "$RC" = 0 ] && [ "$CAPPED" = 0 ] || unrun "GPT CLI --version 실패(exit $RC) — 실행할 수 없다"
VER="$(grep -v '^WARNING: ' "$OUTF" | head -1)"
run help "$HN" "$CLI" sandbox --help
[ "$RC" = 0 ] && [ "$CAPPED" = 0 ] || unrun "로컬 샌드박스 하위 명령 없음(sandbox --help exit $RC) — 남는 실증 경로는 모델 호출이다"
APPROVAL="$(grep -ci 'approval' "$OUTF")"
echo "OS-DENY external — CLI=$CLI · $VER · $(uname -sr) · 상한 ${CAP}s/호출 · stdin=/dev/null · 승인 흐름 언급 ${APPROVAL} · TREE=$R"

PASS=0; BAD=""
cell() {   # $1=셀 · $2=PASS|FAIL · $3=근거
  echo "CELL $1 $2 — $3"
  if [ "$2" = PASS ]; then PASS=$((PASS + 1)); else BAD="$BAD $1"; fi
}

# 1 allow-read — 프로필이 허용 경로까지 막지 않는다(선택적 차단)
run allow-read "$HP" "$CLI" sandbox -- /bin/cat "$ALLOWED"
show allow-read "CODEX_HOME=<profile> sandbox -- /bin/cat $ALLOWED"
if [ "$CAPPED" = 1 ]; then cell allow-read FAIL "상한 ${CAP}s 초과"
elif [ "$RC" = 0 ] && grep -qx 'OS-DENY-ALLOWED-MARK-7' "$OUTF"; then cell allow-read PASS "exit 0 · 마커 읽힘 · $ALLOWED"
else cell allow-read FAIL "exit $RC · 마커 $(grep -c 'OS-DENY-ALLOWED-MARK-7' "$OUTF")건 — 허용 경로가 막혔다"; fi

# 2 deny-read — 금지 경로 읽기가 OS 수준에서 막힌다
run deny-read "$HP" "$CLI" sandbox -- /bin/cat "$SECRET"
show deny-read "CODEX_HOME=<profile> sandbox -- /bin/cat $SECRET"
ln_="$(denied "$OUTF" "$SECRET")"
if [ "$CAPPED" = 1 ]; then cell deny-read FAIL "상한 ${CAP}s 초과"
elif [ "$RC" != 0 ] && [ -n "$ln_" ] && [ "$(grep -c 'OS-DENY-SECRET-MARK-7' "$OUTF")" = 0 ]; then cell deny-read PASS "exit $RC · '$ln_' · 비밀 마커 0"
else cell deny-read FAIL "exit $RC · 거부 줄 '${ln_:-없음}' · 비밀 마커 $(grep -c 'OS-DENY-SECRET-MARK-7' "$OUTF")건"; fi

# 3 write-block — 작업 폴더 안 · 금지 폴더 쓰기가 둘 다 막힌다(extends = ":read-only")
wok=1; wnote=""
for tgt in "$WORK/written.txt" "$OUTSIDE/written.txt"; do
  nm="write-$(basename "$(dirname "$tgt")")"
  run "$nm" "$HP" "$CLI" sandbox -- /bin/sh -c 'printf W > "$1"' sh "$tgt"
  show "$nm" "CODEX_HOME=<profile> sandbox -- /bin/sh -c 'printf W > \"\$1\"' sh $tgt"
  ln_="$(denied "$OUTF" "$tgt")"
  if [ "$CAPPED" = 0 ] && [ "$RC" != 0 ] && [ -n "$ln_" ] && [ ! -e "$tgt" ]; then
    wnote="$wnote · $nm exit $RC '$ln_'"
  else
    wok=0; wnote="$wnote · $nm exit $RC 거부 줄 '${ln_:-없음}' 파일 $([ -e "$tgt" ] && echo 생김 || echo 없음)$([ "$CAPPED" = 1 ] && echo " 상한 ${CAP}s 초과")"
  fi
done
if [ "$wok" = 1 ]; then cell write-block PASS "${wnote# · }"; else cell write-block FAIL "${wnote# · }"; fi

# 4 no-profile-control — 같은 금지 파일이 프로필 없이는 읽힌다(셀 2 의 차단이 프로필에서 온다는 대조)
#   ⛔ 프로필 있음/없음 대조다 — deny 항목만 뺀 프로필은 재지 않는다. `:read-only` 가 읽기 루트를 좁히는 CLI 라면
#      deny 가 무시돼도 셀 2 · 4 가 함께 통과한다(0.159.2 실측: deny 를 뺀 프로필로는 금지 파일이 읽힌다)
run no-profile "$HN" "$CLI" sandbox -- /bin/cat "$SECRET"
show no-profile "CODEX_HOME=<no profile> sandbox -- /bin/cat $SECRET"
if [ "$CAPPED" = 1 ]; then cell no-profile-control FAIL "상한 ${CAP}s 초과"
elif [ "$RC" = 0 ] && grep -qx 'OS-DENY-SECRET-MARK-7' "$OUTF"; then cell no-profile-control PASS "exit 0 · 비밀 마커 읽힘 — 차단은 프로필에서 온다"
else cell no-profile-control FAIL "exit $RC · 비밀 마커 $(grep -c 'OS-DENY-SECRET-MARK-7' "$OUTF")건 — 대조가 안 선다(프로필 밖 차단)"; fi

echo "EVIDENCE-CLASS=live"
echo "OS-DENY-CELLS=$PASS/4"
[ "$PASS" -eq 4 ] && exit 0
echo "FAIL:$BAD"
exit 1
