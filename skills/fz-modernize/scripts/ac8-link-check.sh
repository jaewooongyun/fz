#!/bin/bash
# AC8 Link Validity Auto-Check (xargs 병렬 패턴)
# 본 스크립트는 fz-modernize Phase 6-1 게이트.
#
# ⛔ feedback_bash_background_redirect_capture.md (2026-05-02 교훈):
#    bash while loop + redirect를 background로 실행하면 결과 0 bytes.
#    반드시 xargs -P N 병렬 패턴 사용.
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

# 1. URL 추출 (Rust regex 호환, POSIX class 회피)
echo "[1/3] Extracting URLs from $GUIDES_DIR..."
rg -o 'https?://[^\]\[)<>"\s]+' "$GUIDES_DIR"/*.md \
  | cut -d: -f2- \
  | sed 's/[.,;|]*$//' \
  | sort -u > "$URLS_FILE"

URL_COUNT=$(wc -l < "$URLS_FILE" | tr -d ' ')
echo "    Extracted: $URL_COUNT unique URLs"

# 2. 병렬 검증 (xargs -P 5)
echo "[2/3] Validating links (parallel=$PARALLEL, timeout=${TIMEOUT_SEC}s)..."
cat "$URLS_FILE" | xargs -I {} -P "$PARALLEL" sh -c \
  'echo "$(curl -I -s -L --max-time '"$TIMEOUT_SEC"' -o /dev/null -w %{http_code} "$1") $1"' _ {} \
  > "$RESULTS_FILE" 2>&1

# 3. 결과 분류
echo "[3/3] Analyzing results..."
TOTAL=$(wc -l < "$RESULTS_FILE" | tr -d ' ')
OK=$(grep -cE "^(2|3)" "$RESULTS_FILE" || echo 0)
FORBIDDEN_403=$(grep -cE "^403" "$RESULTS_FILE" || echo 0)
BROKEN=$(grep -cvE "^(2|3|403)" "$RESULTS_FILE" || echo 0)

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
