# 세션 자동 감지 + Issue Tracker

> fz- 스킬의 세션 관리 및 Issue Tracker 공통 모듈. 프로젝트 무관 범용.

## 세션 관리 — Serena Memory 활용 (Primary)

> MCP First: Serena memory를 세션 저장소로 사용.

### 키 네이밍

> 키 정의 및 GC 정책: `modules/memory-policy.md` 참조. 아래는 이 모듈에서 사용하는 주요 키만 기재.

### 세션 시작
```
mcp__serena__write_memory("fz:session:current", {
  session_id: "SESSION-{YYYYMMDD_HHMMSS}",
  task_description: "",
  issues: [],
  iterations: [],
  metrics: { total_issues: 0, resolved: 0, reflection_rate: 0 },
  status: "in_progress"
})
```

### 세션 복원
```
mcp__serena__read_memory("fz:session:current") → 기존 세션 데이터 로드
```

### 이슈 기록/업데이트
```
mcp__serena__edit_memory("fz:session:current", { issues: [...updated] })
```

---

## 세션 자동 감지 (Bash Fallback)

Serena 불가 시 사용. 1시간 이내 기존 세션을 자동 감지합니다.

```bash
TRACKER_DIR="$HOME/.claude/sessions"
mkdir -p "$TRACKER_DIR"

find_recent_session() {
  RECENT=$(find "$TRACKER_DIR" -name "SESSION-*_issues.json" -mmin -60 2>/dev/null | \
           xargs ls -t 2>/dev/null | head -1)
  echo "$RECENT"
}

init_or_use_session() {
  EXISTING_SESSION=$(find_recent_session)

  if [ -n "$EXISTING_SESSION" ] && [ -f "$EXISTING_SESSION" ]; then
    TRACKER_FILE="$EXISTING_SESSION"
    SESSION_ID=$(jq -r '.session_id' "$TRACKER_FILE")
  else
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    SESSION_ID="SESSION-${TIMESTAMP}"
    TRACKER_FILE="${TRACKER_DIR}/${SESSION_ID}_issues.json"

    cat > "$TRACKER_FILE" << EOF
{
  "session_id": "${SESSION_ID}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "task_description": "",
  "issues": [],
  "iterations": [],
  "metrics": { "total_issues_discovered": 0, "total_issues_resolved": 0, "average_reflection_rate": 0 },
  "final_status": "in_progress"
}
EOF
  fi

  export CODEX_SESSION_ID="$SESSION_ID"
  export CODEX_TRACKER_FILE="$TRACKER_FILE"
}

init_or_use_session
```

## 이슈 상태 머신

```
OPEN ──fix──> ADDRESSED ──verify──> RESOLVED
  │               │
  │               │ fail
  │               v
  │           REOPENED ──fix──> ADDRESSED
  │
  └──won't fix──> DEFERRED
```

## 이슈 관리 (Bash)

```bash
# 이슈 추가
jq --arg phase "$PHASE" --slurpfile review "$REVIEW_FILE" '
  .issues += ($review[0].issues | map(. + {"discovered_in": $phase, "status": "open"})) |
  .metrics.total_issues_discovered += ($review[0].issues | length)
' "$TRACKER_FILE" > "${TRACKER_FILE}.tmp" && mv "${TRACKER_FILE}.tmp" "$TRACKER_FILE"

# 이슈 상태 업데이트
jq --arg id "$ISSUE_ID" --arg status "$NEW_STATUS" '
  .issues |= map(if .id == $id then . + {"status": $status} else . end)
' "$TRACKER_FILE" > "${TRACKER_FILE}.tmp" && mv "${TRACKER_FILE}.tmp" "$TRACKER_FILE"

# 미해결 이슈 조회
jq '[.issues[] | select(.status != "resolved" and .status != "deferred")]' "$TRACKER_FILE"
```

## 관련 스키마

- `~/.claude/schemas/issue_tracker_schema.json`

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | 세션 초기화 + 복원 |
| /fz-codex | Issue Tracker 연동 (검증 결과 기록) |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
