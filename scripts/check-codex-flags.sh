#!/usr/bin/env bash
# check-codex-flags.sh — `codex exec` 와 `codex exec review` 의 플래그 집합 차이를 실측하고
# codex-exec.sh 가 review 경로로 넘기는 플래그가 그 차집합에 들어 있지 않은지 검사한다.
#
# 왜 필요한가 (F-015): 두 서브커맨드는 플래그 집합이 다르다. 공용 배열로 넘기면
# review 가 `-C`/`--add-dir` 를 거부해 exit 2 를 내는데, 호출부는 이를 "이슈 0건"으로 오독하기 쉽다.
# `-C` 하나만 보고 고치면 `--add-dir` 가 남는다 — 그래서 **한 플래그가 아니라 집합을 검사**한다.
#
# exit: 0=통과 / 1=review 미지원 플래그가 review 경로에 있음 / 2=codex CLI 없음·help 파싱 실패
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-$SCRIPT_DIR/codex-exec.sh}"

command -v codex >/dev/null 2>&1 || { echo "SKIP: codex CLI 없음 (검사 불가 — PASS 아님)" >&2; exit 2; }

flags_of() {  # $1 = 'exec' | 'exec review'
  # shellcheck disable=SC2086
  codex $1 --help 2>&1 | grep -oE '^[[:space:]]+(-[a-zA-Z], )?--[a-z-]+' \
    | grep -oE '\-\-[a-z-]+' | sort -u
}

EXEC_F="$(flags_of 'exec')"
REVIEW_F="$(flags_of 'exec review')"

# positive control — 파싱이 살아 있는지 먼저 증명한다 (0건은 "차이 없음"이 아니라 "측정 실패"일 수 있다)
EXEC_N=$(printf '%s\n' "$EXEC_F" | grep -c . || true)
REVIEW_N=$(printf '%s\n' "$REVIEW_F" | grep -c . || true)
[ "$EXEC_N" -ge 5 ] && [ "$REVIEW_N" -ge 5 ] \
  || { echo "GATE-FAIL(2): help 파싱 실패 (exec=$EXEC_N review=$REVIEW_N) — 측정 실패다" >&2; exit 2; }

ONLY_EXEC="$(comm -23 <(printf '%s\n' "$EXEC_F") <(printf '%s\n' "$REVIEW_F"))"

echo "▶ exec 전용 (review 가 거부하는) 플래그 $(printf '%s\n' "$ONLY_EXEC" | grep -c . || true)개:"
printf '   %s\n' $ONLY_EXEC

# codex-exec.sh 의 review 호출 경로가 넘기는 플래그 추출:
#   공용 ARGS 블록 + review 분기에서 ARGS 에 추가되는 것
#   ⛔ 주석 라인은 제외한다 — 설명문에 등장하는 플래그 이름을 코드로 오인하면
#      수정이 끝난 파일도 위반으로 찍힌다 (본 스크립트 최초판의 실제 위양성).
#   ⛔ 검사 대상은 **codex 에 전달되는 ARGS 배열**로 한정한다.
#      파일 전체를 훑으면 `git -C "$CD"` 같은 *다른 명령의* 동명 플래그가 섞여 위양성이 된다
#      (본 스크립트 2차판의 실제 오류 — `MODE" = "review"` 가 5곳에 매치해 79줄을 삼켰다).
REVIEW_PATH_FLAGS="$(
  {
    awk '/^ARGS=\(/,/^ARGS\+=\(-o/' "$TARGET"
    awk '/^if \[ "\$MODE" = "review" \]; then$/,/^else$/' "$TARGET" | grep 'ARGS+='
  } | sed 's/#.*$//'
)"

VIOLATIONS=""
for f in $ONLY_EXEC; do
  if printf '%s' "$REVIEW_PATH_FLAGS" | grep -qE -- "(^|[[:space:](])${f}([[:space:]\"]|$)"; then
    VIOLATIONS="$VIOLATIONS $f"
  fi
done
# 단축형도 검사 — `--cd` 는 `-C` 로 쓰인다
printf '%s' "$ONLY_EXEC" | grep -q -- '--cd' \
  && printf '%s' "$REVIEW_PATH_FLAGS" | grep -qE -- '(^|[[:space:](])-C([[:space:]"]|$)' \
  && VIOLATIONS="$VIOLATIONS -C"

if [ -n "$VIOLATIONS" ]; then
  echo "GATE-FAIL(1): review 경로가 미지원 플래그를 전달한다 →$VIOLATIONS" >&2
  echo "  → 해당 플래그를 exec 전용 배열로 분리하라 ($TARGET)" >&2
  exit 1
fi

echo "✅ review 경로에 미지원 플래그 없음"
exit 0
