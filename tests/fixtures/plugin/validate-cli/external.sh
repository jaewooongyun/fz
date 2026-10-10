#!/bin/bash
# plugin_validate 실 CLI 음성 대조 러너 (F-335 ⑭) — 대상 트리의 `scripts/plugin_validate.sh --self-test-cli` 를 실 claude CLI 로 돌려
#   합성 플러그인 4종의 판정 exit 를 이 러너의 기대 표와 대조한다.
#   cli-clean 0 · cli-broken-frontmatter 1 · cli-broken-manifest 1 · cli-no-canary 2
# ⛔ 게이트 전용 — 실 CLI 가 필요한 외부 실증이라 health-check 글롭(run.sh)에 두지 않는다. 모델 호출 · 네트워크 없이 도는 로컬 검증
#    (`claude --version` · `claude plugin validate`)만 한다.
# ⛔ 사용자 설정을 건드리지 않는다 — 버전 조회와 검증을 모두 임시 CLAUDE_CONFIG_DIR · HOME 에서 한다(관찰: CLI 2.1.292 에서 HOME 격리 유무가
#    보고서를 바꾸지 않았다). 그 밖의 쓰기는 임시 폴더뿐이다.
# 출력: `MODE live claude=<버전>`(fixture 결과를 실 CLI 검증으로 승격하지 않게 모드와 도구 버전을 적는다) · 셀마다
#   `CELL <이름> F PASS|FAIL [태그]` · 끝 줄 `CELLS ran=N pass=P fail=K failed=<정렬 목록|-> names=<정렬 목록>`.
#   대상 트리에 --self-test-cli 모드가 없으면(머리 줄 `SELF-TEST-CLI` 없음) 셀 0 — 기대 셀 집합과 달라 단언 실패(exit 1)다(F-408).
# exit: 0 4/4 · 1 단언 실패 · 2 UNRUN(claude CLI 부재 · 버전 판독 불가 · 대상의 CLI 전제 부재) · 3 준비 실패(인자 · 트리 · 임시 폴더)
# usage: external.sh --tree <플러그인 루트>
set -u
R=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
[ -n "$R" ] || { echo "SETUP --tree 가 필요하다"; exit 3; }
[ -f "$R/scripts/plugin_validate.sh" ] || { echo "SETUP 대상 스크립트 없음 $R/scripts/plugin_validate.sh"; exit 3; }
command -v claude >/dev/null 2>&1 || { echo "UNRUN: claude CLI 부재"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 부재(판정기가 쓴다)"; exit 2; }
# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-validate-cli.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
mkdir -p "$T0/config" "$T0/home" || { echo "SETUP 임시 설정 폴더 실패"; exit 3; }
export CLAUDE_CONFIG_DIR="$T0/config" HOME="$T0/home"
VER="$(claude --version 2>/dev/null | sed -n '1s/^\([0-9][0-9]*\.[0-9][0-9.]*\).*/\1/p')"
[ -n "$VER" ] || { echo "UNRUN: claude --version 을 읽지 못했다(임시 CLAUDE_CONFIG_DIR) — CLI 가 로그인 · 네트워크를 요구할 수 있다"; exit 2; }
echo "MODE live claude=$VER"
O="$(bash "$R/scripts/plugin_validate.sh" --self-test-cli 2>&1)"; C=$?
printf '%s\n' "$O" | sed 's/^/  | /'
EXPECTED="cli-broken-frontmatter:1 cli-broken-manifest:1 cli-clean:0 cli-no-canary:2"
if printf '%s\n' "$O" | grep -q '^SELF-TEST-CLI '; then
  if [ "$C" = 2 ]; then echo "UNRUN: 대상의 --self-test-cli 가 CLI 전제 부재로 끝났다(exit 2)"; exit 2; fi
  HAS=1
else
  echo "FAIL 대상 트리에 --self-test-cli 모드가 없다(머리 줄 SELF-TEST-CLI 없음 · exit $C) — 셀 0"
  HAS=0
fi
RAN="" PASSN=0 FAILED=""
for e in $EXPECTED; do
  name="${e%%:*}" want="${e##*:}"
  [ "$HAS" = 1 ] || continue
  line="$(printf '%s\n' "$O" | grep -E "^CELL $name exit=[0-9]+ " | tail -1)"
  [ -n "$line" ] || { echo "CELL $name F FAIL [missing] — 대상 출력에 셀 줄이 없다"; RAN="$RAN $name"; FAILED="$FAILED $name"; continue; }
  got="$(printf '%s' "$line" | sed -n 's/^CELL [^ ]* exit=\([0-9][0-9]*\) .*/\1/p')"
  RAN="$RAN $name"
  # ⛔ 대상의 PASS 표시만 믿지 않는다 — 판정 exit 를 이 러너의 기대 표와 다시 대조한다
  if [ "$got" = "$want" ] && printf '%s' "$line" | grep -q ' PASS$'; then
    echo "CELL $name F PASS — exit $got (기대 $want)"; PASSN=$((PASSN + 1))
  else
    echo "CELL $name F FAIL [exit] — exit $got (기대 $want) · $line"; FAILED="$FAILED $name"
  fi
done
sorted() { printf '%s\n' $1 | LC_ALL=C sort | paste -sd, -; }
N=0; for x in $RAN; do N=$((N + 1)); done
K=0; for x in $FAILED; do K=$((K + 1)); done
NAMES="$(sorted "$RAN")"; FL="$(sorted "$FAILED")"
WANT="$(sorted "$(printf '%s\n' $EXPECTED | sed 's/:.*//')")"
RC=0
[ "$NAMES" = "$WANT" ] || { echo "FAIL 기대 셀 집합 — 돈 셀 [${NAMES:--}] · 기대 [$WANT]"; RC=1; }
[ "$K" -eq 0 ] || RC=1
echo "CELLS ran=$N pass=$PASSN fail=$K failed=${FL:--} names=${NAMES:--}"
exit $RC
