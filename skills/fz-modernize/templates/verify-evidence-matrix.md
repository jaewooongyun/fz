# Verify Evidence Matrix Template (Phase 6)

> **사용법**: 본 템플릿을 `{WORK_DIR}/verify/verify-evidence-matrix.md`로 복사.
> **목적**: 각 verified 인용의 직접 근거를 자동 검증.
> **트리거**: Phase 5d-3 (직접 근거 grep) + Phase 6-1 (AC8 link 검증) 결합.

## 매트릭스 (25+ row 권장)

| # | source_id | claim | required_terms | url | verification_command |
|---|-----------|-------|----------------|-----|---------------------|
| 1 | A1 | (release notes 본문) | "..." | (URL) | `curl -s "$url" \| grep -iE "..."` |
| 2 | A1 | (release date) | "YYYY-MM-DD" | (동일) | (동일) |
| 3 | A2 | | | | |
| ... | | | | | |
| 25+ | | | | | |

## 자동 실행 스크립트

> ⛔ Bash background + while loop + redirect 금지 (feedback_bash_background_redirect_capture.md). xargs -P 5 패턴 사용.

```bash
#!/bin/bash
# verify-evidence-matrix-runner.sh
MATRIX="{WORK_DIR}/verify/verify-evidence-matrix.md"
LOG="{WORK_DIR}/verify/evidence-check.log"

# 매트릭스에서 row 추출 (예: awk 또는 명시 배열)
declare -a rows=(
  "A1|Opus 4.8|https://example.com|Opus 4\.8"
  "A2|...|...|..."
  # ... 25 row
)

failures=0
for row in "${rows[@]}"; do
  IFS='|' read -r src claim url terms <<< "$row"
  content=$(curl -s -L --max-time 30 "$url")
  if ! echo "$content" | grep -qiE "$terms"; then
    failures=$((failures+1))
    echo "FAIL: $src — $url (missing: $terms)" >> "$LOG"
  fi
done

if [ $failures -eq 0 ]; then
  echo "ALL PASS"
else
  echo "FAILURES: $failures"
fi
```

## AC8 Link Validity 결과 (Phase 6-1)

> `scripts/ac8-link-check.sh` 실행 후 결과 기록.

| 항목 | 결과 |
|------|-----|
| 총 URL | N |
| OK (2xx/3xx) | N |
| 403 Forbidden (bot-blocked, 사람 접근 정상) | N |
| 진짜 broken link | N |

### 403 URL 처리 (broken 아님 케이스)

| URL | curl status | 사람 브라우저 | 결정 |
|-----|------------|------------|-----|
| (URL) | 403 (Cloudflare) | 정상 | 유지 (Probe에서 WebSearch 정상 fetch 확인) |

### Broken URL 처리 (있을 경우)

| URL | 결정 | 폴백 |
|-----|-----|-----|
| (URL) | archive.org 폴백 / 인용 제거 / 사용자 결정 | (대체 URL) |

## 폴백 전략

| 시나리오 | 대응 |
|---------|------|
| URL 일시 다운 (5xx) | 30분 후 재시도 → archive.org 폴백 |
| 인증 필요 (login wall) | required_terms를 URL preview metadata에서 검증 |
| Pay wall | 수동 검증 후 매트릭스에 기록 |
| arxiv abs 페이지 변경 | arxiv.org/pdf/{ID} fallback |

## 미완 항목

> 모든 미완 항목은 Plan v{N+1}에서 해소되어야 함.

- (없음, 또는 명시)
