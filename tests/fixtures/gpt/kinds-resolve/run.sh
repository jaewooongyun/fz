#!/bin/bash
# kinds-resolve — GPT 호출 kind 22개를 정문(scripts/gpt-call.sh)으로 가짜 CLI(../_shim/codex)에 돌려, 래퍼 · 런처가 받은 argv 와
#   CLI 가 받은 argv 가 golden/(bf318a7 의 손조립 레시피를 같은 방식으로 포착한 S0 기준선)과 바이트 단위로 같은지 본다.
#   이어서 동작 셀(capture.py cells): 정책 플래그 거부 · 사용법 10 / 레지스트리 11 · R1-R4 선택 상태 · exit 10~17 통과 ·
#   같은 --out 동시 · 잠금 소유자만 정리 · --session-file 보존 · TERM/INT · verify-cross 환경 · Tier 1 cwd · 판별력.
# ⛔ 실제 GPT CLI · 사용자 홈을 건드리지 않는다 — PATH 앞에 shim, HOME 은 임시 폴더, 플러그인 루트는 진입 argv 를 적는 대역 루트다.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }; T="$(cd "$T0" && pwd -P)"; trap 'rm -rf "$T"' EXIT

fail=0
n="$(find "$HERE/golden" -name '*.json' | wc -l | tr -d ' ')"
[ "$n" = 22 ] && echo "PASS  golden kind 22" || { echo "FAIL  golden kind $n (22 기대)"; fail=1; }
if python3 "$HERE/capture.py" golden "$T/golden" > "$T/capture.log" 2>&1; then
  if diff -r "$HERE/golden" "$T/golden" > "$T/diff.txt"; then echo "PASS  정문 경유 argv == S0 golden (22 kind)"
  else echo "FAIL  정문 경유 argv 가 S0 golden 과 다르다"; head -60 "$T/diff.txt"; fail=1; fi
else
  echo "FAIL  포착 실패"; tail -20 "$T/capture.log"; fail=1
fi
python3 "$HERE/capture.py" cells || fail=1
[ "$fail" = 0 ] && { echo "kinds-resolve: 전건 통과"; exit 0; }
echo "kinds-resolve: FAIL"; exit 1
