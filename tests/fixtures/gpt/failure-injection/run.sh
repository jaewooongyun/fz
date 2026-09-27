#!/bin/bash
# 실패 주입 A — GPT 래퍼(gpt-exec.sh)의 실패가 "완료" 로 보고되지 않는다 (S24a · --scope wrapper).
#
# 가짜 CLI(../_shim/codex)로 세 실패를 주입한다: CLI 비정상 종료 · 빈 출력 · 스키마 위반.
# 판정: 래퍼 exit 가 12 / 13 / 14 이고, 성공 표시(GATE-PASS)를 내지 않으며, stderr 에 GATE-FAIL 이 있다.
# 대조: 주입 없는 호출은 exit 0 + GATE-PASS 여야 한다 — 그래야 실패가 주입 때문임을 안다.
# ⛔ 런처·병합(R-B) 셀은 이 판에 없다 — 다른 scope 는 미실행(exit 2)이다.
set -u
SCOPE="wrapper"
[ "${1:-}" = "--scope" ] && SCOPE="${2:-}"
[ "$SCOPE" = "wrapper" ] || { echo "UNRUN  scope '$SCOPE' 의 셀은 아직 없다 — 이 판은 wrapper 만 구현한다"; exit 2; }

R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
WRAP="${FZ_GPT_EXEC_UNDER_TEST:-$R/scripts/gpt-exec.sh}"
export PATH="$R/tests/fixtures/gpt/_shim:$PATH"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/repo"
echo "과제" > "$T/task.txt"
printf '{"type":"object","required":["verdict"],"properties":{"verdict":{"type":"string"}}}\n' > "$T/schema.json"

fail=0
cell() {   # $1=이름 · $2=기대 exit · $3=FZ_SHIM_OUTPUT · $4=FZ_SHIM_EXIT · 나머지=추가 래퍼 인자
  local name="$1" want="$2" out="$3" ex="$4"; shift 4
  local d="$T/$name"; mkdir -p "$d"
  env FZ_SHIM_OUTPUT="$out" FZ_SHIM_EXIT="$ex" FZ_TELEMETRY_DIR="$d" \
    bash "$WRAP" exec --cd "$T/repo" --out "$d/out.txt" --prompt-file "$T/task.txt" "$@" > "$d/stdout" 2> "$d/stderr"
  local rc=$?
  local pass_shown=0 fail_shown=0
  grep -q "GATE-PASS" "$d/stdout" && pass_shown=1
  grep -q "GATE-FAIL" "$d/stderr" && fail_shown=1
  if [ "$want" -eq 0 ]; then
    [ "$rc" -eq 0 ] && [ "$pass_shown" -eq 1 ] && echo "PASS  $name → exit 0 + GATE-PASS" \
      || { echo "FAIL  $name — exit $rc · GATE-PASS $pass_shown"; fail=1; }
  else
    [ "$rc" -eq "$want" ] && [ "$pass_shown" -eq 0 ] && [ "$fail_shown" -eq 1 ] \
      && echo "PASS  $name → exit $want · GATE-PASS 없음 · GATE-FAIL 있음" \
      || { echo "FAIL  $name — exit $rc(기대 $want) · GATE-PASS $pass_shown · GATE-FAIL $fail_shown"; fail=1; }
  fi
}

cell "대조(주입 없음)"          0  "ok" 0
cell "CLI 비정상 종료(exit 1)"  12 "ok" 1
cell "빈 출력"                  13 ""   0
cell "스키마 위반"              14 "{}" 0 --schema "$T/schema.json"

echo
[ "$fail" -eq 0 ] && echo "실패 주입 A(wrapper) 전건 통과" || echo "실패 주입 A(wrapper) 실패 있음"
exit "$fail"
