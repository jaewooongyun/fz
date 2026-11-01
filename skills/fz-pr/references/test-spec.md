# fz-pr 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering Test

**should-trigger** (description '예:' 트리거 어휘 + intent-triggers 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "PR 만들어줘" | trigger | description 예 "PR 만들어" / 핵심 유스케이스 |
| "풀리퀘스트 생성해줘" | trigger | description 예 + intent-trigger "풀리퀘스트" |
| "PR 생성해줘" | trigger | description 예 "PR 생성" |
| "pull request 올려줘" | trigger | intent-trigger "PR\|pull.?request" |

**should-NOT-trigger** (Boundaries Will Not / description '비사용:' 대안 스킬 기반)

| 쿼리 | 예상 | redirect / 근거 |
|------|------|------|
| "커밋만 해줘" | NOT trigger | → fz-commit (description 비사용 "커밋만 →fz-commit" + Will Not "커밋 생성") |
| "이 코드 고쳐줘" | NOT trigger | → fz-fix (Will Not "코드 수정 → /fz-code 또는 /fz-fix") |
| "새 기능 구현해줘" | NOT trigger | → fz-code (Will Not "코드 수정 → /fz-code") |
| "이 PR 머지해줘" | NOT trigger | 스킬 범위 밖 — Will Not "PR 머지 또는 PR 승인" 미수행 (GitHub에서 직접) |

### Functional Test (Given/When/Then)

| Given | When | Then (pass/fail oracle) | type |
|-------|------|------|------|
| unpushed 커밋 존재 + origin(fork) remote 설정 + JIRA 티켓 ID 식별 가능 | `/fz-pr develop` | origin(fork)에 push(Step 2) → 템플릿 기반 create_pull_request 호출(Step 3) → Assignee(Step 4)·Reviewer(`AI/teams.json`, Step 5) 지정 → PR URL 출력 + JIRA 상태 In Review 전환 = **Step 5까지 완료** | normal |
| 대상 브랜치에 동일 PR 이미 존재 (Step 0 감지) | `/fz-pr develop` | create_pull_request **미호출** + 기존 PR URL 출력 후 종료 | edge-case |
| Target 브랜치 인자 없음 + 후보 브랜치 복수 (Step 1) | `/fz-pr` | 브랜치 목록 출력 후 사용자 선택 대기 (기본 develop 제안), 선택 전 push/PR **미실행** | edge-case |
| unpushed 커밋 없음 | `/fz-pr` | PR 생성 중단 + "커밋 없음" 안내 + `/fz-commit` 먼저 실행 폴백 안내 (create_pull_request **미호출**) | failure |
| unpushed 커밋 존재하나 GitHub MCP 호출 실패 | `/fz-pr develop` | MCP 오류 안내 + `gh pr create` 수동 실행 폴백 안내 출력 | failure |
