#!/bin/bash
# mode-gate fixture 공용 — 셀마다 env 를 격리한다(health-check 는 Lead 세션 env 를 물려받는다: 세션 id · effort · 자율 모드)
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MG="$R/scripts/mode_gate.py"
T="$(mktemp -d)" || { echo "UNRUN  mktemp 실패"; exit 2; }
[ -d "$T" ] || { echo "UNRUN  임시 폴더 없음"; exit 2; }
trap 'rm -rf "$T"' EXIT
gate() { env -u CLAUDE_CODE_EFFORT_LEVEL HOME="$T" CLAUDE_CODE_SESSION_ID="" CLAUDE_EFFORT="" FZ_AUTONOMY="" python3 "$MG" "$@"; }
# 실제 git 패치를 만든다 — $1 = 파일 수, $2 = 파일당 추가 줄 수
mkpatch() {
  local d="$T/repo"; rm -rf "$d"; mkdir -p "$d" && git -C "$d" init -q \
    && git -C "$d" -c user.email=t@example.invalid -c user.name=t commit -q --allow-empty -m base
  local i j; for i in $(seq 1 "$1"); do for j in $(seq 1 "$2"); do echo "line $j" ; done > "$d/f$i.txt"; done
  git -C "$d" add -A && git -C "$d" diff --cached > "$T/change.patch"
}
field() { python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(eval(sys.argv[2],{},{'d':d}))" "$1" "$2"; }
