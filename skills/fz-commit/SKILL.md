---
name: fz-commit
description: >-
  Git 커밋 생성. Conventional Commit 형식 + 티켓 참조 자동 포함.
  예: 커밋해줘, 저장해줘, 변경사항 커밋
user-invocable: true
disable-model-invocation: true
argument-hint: "[TICKET-ID]"
allowed-tools: >-
  mcp__atlassian__get-issue,
  mcp__atlassian__search-issues,
  Bash(git *)
composable: false
provides: [commit]
needs: [code-changes]
intent-triggers:
  - "커밋"
  - "commit"
model-strategy:
  main: null
  verifier: null
---

# Git Commit Skill

## 규칙 참조

CLAUDE.md `## Git Workflow` 섹션에 커밋 규칙이 정의되어 있으면 해당 규칙을 따른다.
없으면 Conventional Commits 표준을 따른다.

---

## 사용 도구

`/sc:git` 스킬을 사용하여 커밋을 실행합니다.

---

## 커밋 단위 가이드

**원칙**: 기능 단위로 커밋하되, 작업 흐름이 끊어지지 않을 정도의 크기 유지

| 판단 | 예시 |
|------|------|
| 너무 작음 | import 한 줄 추가, 변수명 하나 변경 |
| 너무 큼 | 여러 기능 혼합, 관련 없는 파일들 묶음 |
| 적절함 | 하나의 기능/버그픽스가 완결되는 단위 |

**좋은 커밋 단위 예시**:
- UI 컴포넌트 하나 추가 + 관련 스타일
- API 호출 로직 수정 + 에러 처리
- 버그 수정 + 관련 테스트 코드

---

## Boundaries

**Will**:
- Conventional Commits 형식으로 커밋 메시지 생성
- JIRA 티켓 ID를 커밋 prefix에 포함
- CLAUDE.md `## Git Workflow` 규칙 우선 적용
- 커밋 단위 판단 및 분리 제안

**Will Not**:
- 코드 수정 → `/fz-code` 또는 `/fz-fix` 사용
- PR 생성 → `/fz-pr` 사용
- 브랜치 생성/전환 → `git` CLI 사용
- force push 또는 커밋 이력 변경

---

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| nothing to commit | staged 파일 없음 안내 | `git status` 확인 후 스테이징 요청 |
| commit-msg hook 실패 | 훅 오류 메시지 안내 | 메시지 형식 수정 후 재시도 |
| JIRA 티켓 조회 실패 | MCP 없이 수동 입력 안내 | 인자로 전달받은 티켓 ID 직접 사용 |
| 커밋 단위 판단 불명확 | 변경 파일 목록 출력 후 사용자 확인 | 사용자 지시에 따라 분리 |

---

## Completion → Next

- 커밋 성공 시: 커밋 해시와 메시지 요약 출력 → `/fz-pr`로 PR 생성 가능
- 커밋 단위 분리 제안 시: 분리 계획 제시 후 사용자 확인 대기
- 훅 실패 시: 오류 원인 안내 → 메시지 수정 후 재시도
