---
name: fz-pr
description: >-
  PR 생성. Fork 기반 푸시 + 티켓 연동 + 리뷰어 자동 지정.
  예: PR 만들어, 풀리퀘스트, PR 생성 (비사용: 커밋만 →fz-commit)
user-invocable: true
disable-model-invocation: true
argument-hint: "[TICKET-ID]"
allowed-tools: >-
  mcp__github__create_pull_request,
  mcp__github__get_pull_request,
  mcp__github__list_pull_requests,
  mcp__atlassian-jira__jira_get,
  mcp__atlassian-jira__jira_post,
  Bash(git *)
metadata:
  provides: [pr]
  needs: [commit]
  intent-triggers:
    - "(?<![A-Za-z])PR(?![A-Za-z])|풀리퀘스트"
    - "(?<![A-Za-z])PR(?![A-Za-z])|pull.?request"
---

# PR Creation Skill

## 규칙 참조

**팀 PR 스킬**: CLAUDE.md 에 팀 PR 스킬이 선언되어 있으면(절 제목과 무관 — 스킬 경로나 이름) 그 스킬의 워크플로우 전체를 실행한다 (리뷰어 자동 지정 포함).
선언이 없으면 기본 `gh pr create` 워크플로우를 사용한다. 정본: `modules/governance.md` § 팀 스킬 위임.

---

## 사용법

```bash
/fz-pr              # 브랜치 목록에서 선택
/fz-pr develop      # develop 브랜치로 PR
/fz-pr main         # main 브랜치로 PR (명시적 지정 필요)
```

---

## 사용 도구

`/sc:sc-git` 스킬을 사용하여 푸시 및 PR 생성을 실행합니다.

---

## 워크플로우 요약

| Step | 설명 |
|------|------|
| 0 | 현재 상태 감지 (PR 존재 여부, unpushed 커밋 확인) |
| 1 | Target Branch 결정 (인자 또는 선택) |
| 2 | Push |
| 3 | PR 생성 (템플릿 기반 — 본문 어조 `modules/team-facing-writing.md`) |
| 4 | Assignee 설정 |
| 5 | Reviewer 설정 (`AI/teams.json` 기반) |

---

## 주의사항

- **커밋이 없으면** PR 생성 불가 → `/fz-commit` 먼저 실행
- **PR이 이미 존재하면** 기존 PR URL 안내 후 종료

---

## Git Remote 안전 규칙

CLAUDE.md 에 fork 기반 워크플로우가 정의되어 있으면(절 제목 무관):
- `origin`(fork)에만 push
- `upstream`에 직접 push 절대 금지 (PR 리뷰 프로세스 스킵됨)

해당 규칙이 없으면 기본 `origin`에 push.

---

> 테스트 케이스 · 시나리오: `references/test-spec.md` (§ SKILL.md 에서 옮긴 테스트 케이스)

## Boundaries

**Will**:
- origin(fork)에 push 후 upstream으로 PR 생성
- JIRA 티켓 ID 기반 PR 제목 및 설명 자동 생성
- PR 중복 여부 확인 후 기존 PR URL 안내
- Assignee 자동 설정

**Will Not**:
- upstream에 직접 push → fork 기반 PR만 허용
- 코드 수정 → `/fz-code` 또는 `/fz-fix` 사용
- 커밋 생성 → `/fz-commit` 먼저 실행
- PR 머지 또는 PR 승인

---

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| unpushed 커밋 없음 | 커밋 없음 안내 | `/fz-commit` 먼저 실행하도록 안내 |
| PR 이미 존재 | 기존 PR URL 출력 후 종료 | 사용자에게 기존 PR 확인 요청 |
| GitHub MCP 실패 | MCP 오류 안내 | `gh pr create` 명령어 수동 실행 안내 |
| JIRA 티켓 조회 실패 | 티켓 정보 없이 PR 생성 | 사용자에게 제목/설명 직접 입력 요청 |
| Target 브랜치 선택 불명확 | 브랜치 목록 출력 후 사용자 선택 | 기본 develop 브랜치 제안 |

---

## Completion → Next

- PR 생성 성공 시: PR URL 출력 → JIRA 티켓 상태 전환(In Review) 수행
- PR 이미 존재 시: 기존 PR URL 안내 → 필요 시 내용 업데이트 여부 확인
- 실패 시: 원인 분석 안내 → 수동 PR 생성 방법 제시
