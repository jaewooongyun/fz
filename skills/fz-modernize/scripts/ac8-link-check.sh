#!/bin/bash
# AC8 Link Validity Auto-Check (xargs 병렬 패턴)
# 본 스크립트는 fz-modernize Phase 6-1 게이트. SKILL.md §AC8 은 이 파일을 부르기만 한다(단일 출처).
#
# ⛔ Bash background+redirect 교훈 (2026-05-02 교훈):
#    bash while loop + redirect를 background로 실행하면 결과 0 bytes.
#    반드시 xargs -P N 병렬 패턴 사용.
# ⛔ URL 추출은 POSIX 도구만 쓴다(F-224) — 예전 `rg -o` 는 rg 가 없는 bash · /bin/sh 에서
#    exit 127 로 죽으며 0바이트 urls-to-check.txt 를 남겼다(측정 실패가 'URL 0건' 으로 읽힌다).
#
# exit: 0 broken 0건 · 1 broken 있음 · 2 UNRUN(URL 0건 — 경로·도구 확인, ⛔ 통과 아님)
#       · 3 입력 오류(가이드 폴더 없음 · *.md 읽기 실패 · 출력 폴더 쓰기 불가)
#   산출물은 출력 폴더 안 임시 파일에 쓰고 그 단계가 성공했을 때만 mv 로 바꾼다 —
#   실패(2 · 3 · 도구 사망)하면 기존 urls-to-check.txt · link-check-results.txt 는 그대로 남는다.
# 회귀: tests/fixtures/modernize/ac8-links/run.sh (고정 가이드 스냅샷 · curl shim · env -i sh)
#
# 사용법:
#   ./ac8-link-check.sh <guides_dir> <output_dir>
# 예 (fz-plugin 루트에서):
#   ./skills/fz-modernize/scripts/ac8-link-check.sh ./guides /tmp
#   또는 git 루트 자동 감지:
#   ./skills/fz-modernize/scripts/ac8-link-check.sh "$(git rev-parse --show-toplevel)/guides" /tmp

set -euo pipefail

# Default: 현재 git 루트의 guides/. CI/CD 환경 호환 (user-specific 경로 회피)
GUIDES_DIR="${1:-$(git rev-parse --show-toplevel 2>/dev/null || echo ".")/guides}"
OUTPUT_DIR="${2:-/tmp}"

URLS_FILE="$OUTPUT_DIR/urls-to-check.txt"
RESULTS_FILE="$OUTPUT_DIR/link-check-results.txt"
TIMEOUT_SEC=15
PARALLEL=5

[ -d "$GUIDES_DIR" ] || { echo "AC8 입력 오류 — 가이드 폴더 없음: $GUIDES_DIR" >&2; exit 3; }
[ -d "$OUTPUT_DIR" ] && [ -w "$OUTPUT_DIR" ] || { echo "AC8 입력 오류 — 출력 폴더 없음·쓰기 불가: $OUTPUT_DIR" >&2; exit 3; }
# 임시 파일은 출력 폴더 안에 둔다 — 같은 파일시스템이어야 mv 가 원자적이다
TMP_URLS=$(mktemp "$OUTPUT_DIR/.urls-to-check.XXXXXX") || exit 3
TMP_RESULTS=$(mktemp "$OUTPUT_DIR/.link-check-results.XXXXXX") || { rm -f "$TMP_URLS"; exit 3; }
trap 'rm -f "$TMP_URLS" "$TMP_RESULTS"' EXIT

# 1. URL 추출 (POSIX ERE — 대괄호 안 공백은 [:space:]: BSD grep 에서 [] 안 \s 는 '\' 와 's' 라
#    URL 이 첫 's' 에서 끊긴다(be8c871 guides 실측 49 → 24건). -h 가 파일명을 떼므로 cut 은 없다 —
#    cut -d: -f2- 를 남기면 'https:' 가 잘린다)
# ⛔ 무매치(grep exit 1)만 삼킨다 — set -euo pipefail 에서 무매치가 파이프를 죽이면 'URL 0 → UNRUN' 에 닿지 못하고,
#    읽기 오류(exit 2)까지 삼키면 측정 실패가 'URL 0건' 으로 읽힌다
echo "[1/3] Extracting URLs from $GUIDES_DIR..."
{ grep -hoE 'https?://[^][)<>"[:space:]]+' "$GUIDES_DIR"/*.md || {
    rc=$?; [ "$rc" -eq 1 ] || { echo "AC8 입력 오류 — $GUIDES_DIR/*.md 읽기 실패 (grep exit $rc)" >&2; exit 3; }; }; } \
  | sed 's/[.,;|]*$//' \
  | sort -u > "$TMP_URLS" || exit $?

URL_COUNT=$(wc -l < "$TMP_URLS" | tr -d ' ')
echo "    Extracted: $URL_COUNT unique URLs"
if [ "$URL_COUNT" -eq 0 ]; then
  echo "UNRUN: AC8 — $GUIDES_DIR/*.md 에서 URL 0건 (경로·도구 확인, ⛔ 통과 아님 · 기존 $URLS_FILE 보존)"
  exit 2
fi
mv -f "$TMP_URLS" "$URLS_FILE"

# 2. 병렬 검증 (xargs -P 5)
echo "[2/3] Validating links (parallel=$PARALLEL, timeout=${TIMEOUT_SEC}s)..."
cat "$URLS_FILE" | xargs -I {} -P "$PARALLEL" sh -c \
  'echo "$(curl -I -s -L --max-time '"$TIMEOUT_SEC"' -o /dev/null -w %{http_code} "$1") $1"' _ {} \
  > "$TMP_RESULTS" 2>&1
mv -f "$TMP_RESULTS" "$RESULTS_FILE"

# 3. 결과 분류
echo "[3/3] Analyzing results..."
TOTAL=$(wc -l < "$RESULTS_FILE" | tr -d ' ')
OK=$(grep -cE "^(2|3)" "$RESULTS_FILE" || true)
FORBIDDEN_403=$(grep -cE "^403" "$RESULTS_FILE" || true)
BROKEN=$(grep -cvE "^(2|3|403)" "$RESULTS_FILE" || true)

echo ""
echo "============================================"
echo "  AC8 Link Validity Results"
echo "============================================"
echo "  Total URLs:         $TOTAL"
echo "  OK (2xx/3xx):       $OK"
echo "  403 (bot-blocked):  $FORBIDDEN_403  (사람 접근 정상 가능)"
echo "  Broken:             $BROKEN"
echo "============================================"

# 4. Broken/403 상세
if [ "$BROKEN" -gt 0 ]; then
  echo ""
  echo "BROKEN URLs (decision required):"
  grep -vE "^(2|3|403)" "$RESULTS_FILE"
  echo ""
  echo "  → Decision: archive.org fallback / 인용 제거 / 사용자 확인"
fi

if [ "$FORBIDDEN_403" -gt 0 ]; then
  echo ""
  echo "403 Forbidden URLs (Cloudflare bot detection — usually OK for humans):"
  grep -E "^403" "$RESULTS_FILE"
  echo ""
  echo "  → Verification: WebSearch fetch (Phase 1 Probe) 결과로 사람 접근 가능 확인"
fi

# 5. Exit code
if [ "$BROKEN" -gt 0 ]; then
  exit 1
fi
exit 0
