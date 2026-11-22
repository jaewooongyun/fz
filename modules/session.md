# 세션 자동 감지 + Issue Tracker

> fz- 스킬의 세션 관리 및 Issue Tracker 공통 모듈. 프로젝트 무관 범용.

## 목차

- [세션 자동 감지](#세션-자동-감지)
- [이슈 상태 머신](#이슈-상태-머신)
- [이슈 관리 (Bash)](#이슈-관리-bash)
- [관련 스키마](#관련-스키마)
- [참조 스킬](#참조-스킬)
- [설계 원칙](#설계-원칙)

---

## 세션 자동 감지

Issue Tracker 의 저장소는 아래 세션 파일(`TRACKER_FILE`) 하나다. 1시간 이내 기존 세션을 자동 감지합니다. 다른 세션이 만든 파일은 이어받지 않는다(이번 호출과 파일의 세션 id(`CLAUDE_CODE_SESSION_ID`) 중 하나라도 모르면 나이만 본다) · 읽을 수 없는 파일은 건너뛴다 · 새 파일은 있는 파일을 덮어쓰지 않는다(같은 초에 이름이 겹치면 1초 뒤 새 시각으로 다시) · 파일을 쓰지 못하면 변수를 내보내지 않고 1 로 끝난다.

```bash
TRACKER_DIR="$HOME/.claude/sessions"
mkdir -p "$TRACKER_DIR"

# -exec … + 는 찾은 파일이 없으면 ls 를 돌리지 않는다(xargs 는 GNU 에서 빈 입력에도 ls 를 돌려 현재 폴더를 나열한다)
find_recent_session() {
  find "$TRACKER_DIR" -name "SESSION-*_issues.json" -mmin -60 -exec ls -t {} + 2>/dev/null | \
    while IFS= read -r f; do
      THEIRS=$(jq -er '.claude_session_id // ""' "$f" 2>/dev/null) || continue
      if [ -z "${CLAUDE_CODE_SESSION_ID:-}" ] || [ -z "$THEIRS" ] || [ "$THEIRS" = "$CLAUDE_CODE_SESSION_ID" ]; then
        echo "$f"; break
      fi
    done
}

init_or_use_session() {
  EXISTING_SESSION=$(find_recent_session)

  if [ -n "$EXISTING_SESSION" ] && [ -f "$EXISTING_SESSION" ]; then
    TRACKER_FILE="$EXISTING_SESSION"
    SESSION_ID=$(jq -r '.session_id' "$TRACKER_FILE")
  else
    # set -C: 이름이 이미 있으면(같은 초에 시작한 다른 세션) 덮어쓰지 않고 실패한다 → 1초 뒤 새 시각으로 다시(모두 3번)
    TRY=1
    while :; do
      TIMESTAMP=$(date +%Y%m%d_%H%M%S)
      SESSION_ID="SESSION-${TIMESTAMP}"
      TRACKER_FILE="${TRACKER_DIR}/${SESSION_ID}_issues.json"

      ( set -C; cat > "$TRACKER_FILE" ) << EOF && break
{
  "session_id": "${SESSION_ID}",
  "claude_session_id": "${CLAUDE_CODE_SESSION_ID:-}",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "task_description": "",
  "issues": [],
  "iterations": [],
  "metrics": { "total_issues_discovered": 0, "total_issues_resolved": 0, "average_reflection_rate": 0 },
  "final_status": "in_progress"
}
EOF
      if [ ! -e "$TRACKER_FILE" ] || [ "$TRY" -ge 3 ]; then
        echo "트래커 파일을 쓸 수 없다: $TRACKER_FILE" >&2; return 1
      fi
      TRY=$((TRY + 1)); sleep 1
    done
  fi

  export GPT_SESSION_ID="$SESSION_ID"
  export GPT_TRACKER_FILE="$TRACKER_FILE"
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

- `schemas/issue_tracker_schema.json`

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-gpt | Issue Tracker 연동 (검증 결과 기록) |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
