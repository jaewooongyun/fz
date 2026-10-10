#!/bin/bash
# Gather Step 0.5 정본 — PR head 와 base(`baseRefName`)를 base 저장소 원격에서 받는다 (F-253 · DG-11=approve).
#   pr-{N}                        ← <원격> pull/{N}/head      (`git show pr-{N}:{FILE}` · GPT DA sandbox 우회)
#   refs/remotes/<원격>/<base>    ← <원격> refs/heads/<base>  (gather.sh 가 이 원격 추적 ref 로 base 를 모은다)
#
# ⛔ 로컬 브랜치가 뒤처져 있으면 `git show <로컬 base>:<file>` 원본이 낡는다(F-253 실측: 19커밋 뒤 · origin 판정
#    근거 1건 오염). 원격 추적 ref 도 마지막 fetch 시점이라 낡을 수 있다 — 그래서 수집 직전에 base 를 받는다.
# ⛔ **네트워크를 쓴다.** 사용자가 요청한 리뷰 턴의 Gather 에서만 부른다. gather.sh 는 fetch 하지 않는다
#    (이미 뜬 diff 와 수집 대상이 어긋난다 — tests/fixtures/peer-review/stale-base 계약).
# ⛔ 로컬 브랜치 · 작업 트리 · HEAD 를 바꾸지 않는다 — 원격 추적 ref 와 `pr-{N}` 만 쓴다(pull·merge 아님).
# 원격 선택: --remote 가 없으면 upstream → origin 중 처음 있는 것(이름 순). gather.sh 는 PR url 의 owner/repo 와
#   맞는 원격을 먼저 고르므로, upstream 이 fork 인 배치에서는 두 스크립트가 다른 원격을 본다 — 그때는 --remote 로
#   base 저장소 원격을 준다.
# gh 가 없거나 baseRefName 조회가 실패하면 PR head 만 받고 exit 5 — base 원격 추적 ref 는 받지 않는다(이름을 모른다).
#   SKILL.md 의 'gh 실패 → git 폴백' 경로에서도 pr-{N} 은 생긴다.
#
# usage: fetch_pr_refs.sh --target <PR번호> [--remote <원격>]
# exit: 0 성공 / 2 사용법 / 3 원격 없음 / 4 fetch 실패 / 5 head 만 받음(gh 부재 · baseRefName 조회 실패 — base 미갱신)
set -uo pipefail

die() { echo "FETCH-FAIL($1): $2" >&2; exit "$1"; }

PR="" REM=""
while [ $# -gt 0 ]; do
  case "$1" in
    --target) [ $# -ge 2 ] || die 2 "--target 은 값이 필요하다"; PR="$2"; shift 2 ;;
    --remote) [ $# -ge 2 ] || die 2 "--remote 는 값이 필요하다"; REM="$2"; shift 2 ;;
    *) die 2 "알 수 없는 인자: $1" ;;
  esac
done
[[ "$PR" =~ ^[0-9]+$ ]] || die 2 "--target 은 PR 번호다 (받은 값: '${PR}')"

BASE=""
if command -v gh >/dev/null 2>&1; then
  BASE=$(gh pr view "$PR" --json baseRefName 2>/dev/null \
    | python3 -c 'import json,sys;print(json.load(sys.stdin)["baseRefName"])' 2>/dev/null) || BASE=""
fi

if [ -z "$REM" ]; then
  for r in upstream origin; do
    if git remote get-url "$r" >/dev/null 2>&1; then REM="$r"; break; fi
  done
fi
[ -n "$REM" ] && git remote get-url "$REM" >/dev/null 2>&1 || die 3 "원격 없음 — upstream · origin 중 아무것도 없다 (--remote 로 지정)"

if [ -z "$BASE" ]; then
  GIT_TERMINAL_PROMPT=0 git fetch "$REM" "pull/${PR}/head:pr-${PR}" \
    || die 4 "'$REM' 에서 pull/${PR}/head fetch 실패 (base 저장소 원격이 다르면 --remote)"
  echo "FETCH-PARTIAL(5): pr-${PR}=$(git rev-parse --short "pr-${PR}") — gh 로 baseRefName 을 얻지 못해 base 원격 추적 ref 는 받지 않았다(낡았을 수 있다)" >&2
  exit 5
fi
GIT_TERMINAL_PROMPT=0 git fetch "$REM" "pull/${PR}/head:pr-${PR}" "+refs/heads/${BASE}:refs/remotes/${REM}/${BASE}" \
  || die 4 "'$REM' 에서 pull/${PR}/head · ${BASE} 중 하나 이상 fetch 실패 — 어느 쪽인지는 위 git 출력 (base 저장소 원격이 다르면 --remote)"
echo "FETCH-OK: pr-${PR}=$(git rev-parse --short pr-${PR}) · ${REM}/${BASE}=$(git rev-parse --short "refs/remotes/${REM}/${BASE}")"
