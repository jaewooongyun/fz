---
name: fz-commit
description: >-
  Git 커밋 생성. Conventional Commit 형식 + 티켓 참조 자동 포함.
  예: 커밋해줘, 저장해줘, 변경사항 커밋 (비사용: PR 생성 →fz-pr)
user-invocable: true
disable-model-invocation: true
argument-hint: "[TICKET-ID]"
allowed-tools: >-
  mcp__atlassian-jira__jira_get,
  Bash(git *)
metadata:
  provides: [commit]
  needs: [code-changes]
  intent-triggers:
    - "커밋"
    - "commit"
---

# Git Commit Skill

## 규칙 참조

CLAUDE.md `## Git Workflow` 섹션에 커밋 규칙이 정의되어 있으면 해당 규칙을 따른다.
없으면 Conventional Commits 표준을 따른다.

---

## 사용 도구

`/sc:sc-git` 스킬을 사용하여 커밋을 실행합니다.

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

### ⛔ 나눈 뒤 커밋마다 단독 검증 (F-310)

기능 단위 분할의 값은 커밋을 하나씩 되돌리거나 bisect 할 수 있다는 데 있다. 파일 배정만 보고 나누면 이 값이 조용히 깨진다 — 실측 10커밋 중 5개가 단독으로 저장소 검사를 통과하지 못했고, 다음 판에서 같은 원인으로 재발했다.

1. **개수·목록 선언을 먼저 센다** — 디렉터리의 파일 수나 목록을 문서에 적고 대조하는 검사가 있으면(fz: `lint_contracts` #N2 가 `CLAUDE.md`·`docs/architecture.md` 의 `scripts/` 개수를 본다), 그 디렉터리에 파일을 더하는 커밋마다 선언을 **같은 커밋에서** 그 시점 값으로 맞춘다
2. **검사기는 검사 대상 뒤에** — 전체 검사가 부르는 새 검사기의 배선은 검사기와 그 대상이 모두 들어간 뒤의 커밋에 둔다
3. **커밋마다 격리 clone 에서 돌린다** — clone 에도 커밋 훅(`core.hooksPath`)과 커밋 신원(`user.name` · `user.email`)을 건다. clone 은 원본 저장소의 로컬 설정을 물려받지 않아서, 빠뜨리면 전역 신원으로 커밋된다. 커밋마다 저장소 전체 검사(fz: `scripts/health-check.sh`)를 실행한다. ⛔ 파일 배정 dry-run 은 단독 실패를 보지 못한다
4. **검증한 객체를 그대로 쓴다** — 1번처럼 작업 트리에 없던 중간 상태가 있으면 실제 저장소에서 같은 묶음으로 다시 커밋하지 않는다. 격리 clone 의 검증된 커밋을 `git fetch` 로 가져와 `git reset --mixed <검증한 끝 커밋>` 으로 브랜치만 앞으로 옮긴다(작업 파일 불변 · fast-forward 와 같은 방향). 옮긴 뒤 `git status` 가 비어야 하고, 가져온 커밋의 작성자·커밋터 메일이 의도한 신원이어야 한다

---

## 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "커밋해줘" | trigger | 핵심 유스케이스 (description 예시) |
| "저장해줘" | trigger | description 예시 |
| "변경사항 커밋" | trigger | description 예시 |
| "commit" | trigger | intent-trigger 어휘 |
| "PR 만들어줘" | NOT trigger | → fz-pr (description 비사용 / Boundaries Will Not) |
| "이 버그 고쳐줘" | NOT trigger | → fz-fix (Boundaries Will Not: 코드 수정) |
| "새 기능 구현해줘" | NOT trigger | → fz-code (Boundaries Will Not: 코드 수정) |
| "브랜치 새로 만들어줘" | NOT trigger | → git CLI (Boundaries Will Not: 브랜치 생성/전환) |
| "마지막 커밋 amend 해줘" | NOT trigger | → git CLI (Boundaries Will Not: 커밋 이력 변경 미수행) |

### Functional

| Given | When | Then | 유형 |
|-------|------|------|------|
| staged 변경 존재 + 티켓 ID 인자 전달 (또는 CLAUDE.md `## Git Workflow` 규칙 존재) | `/fz-commit "<TICKET-ID>"` | Conventional Commit 형식 + 티켓 prefix 포함 커밋 생성 성공(git commit exit 0) + 커밋 해시·메시지 요약 출력 | normal |
| 서로 무관한 여러 기능 변경이 함께 staged | `/fz-commit` | 변경 파일 목록 출력 + 커밋 단위 분리 제안 제시 + 사용자 확인 대기(자동 커밋 0건) | edge-case |
| staged 목록에 `.swiftlint.yml`/`.github/`/`Package.swift`/`*.xcconfig` 등 보호 파일 포함 | `/fz-commit` | PROTECTED_PATTERN grep으로 보호 파일 감지 → 자동 커밋 차단 + 사용자 승인(AskUserQuestion) 요청(승인 전 커밋 0건) | edge-case |
| staged 파일 없음(`git diff --cached` 비어 있음) | `/fz-commit` | "staged 파일 없음" 안내 + `git status` 확인 요청, 커밋 미실행(커밋 0건) | failure |
| `commit-msg` 훅이 메시지 형식 거부 | `/fz-commit` | 훅 오류 메시지 안내 + 커밋 미생성(commit-msg exit≠0) → 메시지 형식 수정 후 재시도 안내 | failure |
| 나눈 커밋 하나가 단독으로 저장소 검사에 실패(개수 선언이 다른 커밋에 있음) | `/fz-commit` 기능 단위 분할 | 격리 clone 검증에서 실패 커밋과 원인 출력 + 경계·순서 조정 제안, 실제 저장소 커밋 0건 | edge-case |

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
- **팀 공유 영역 자동 커밋 (36차)**: staged 파일에 `.swiftlint.yml` / `.github/` / `Package.swift` / `*.xcconfig` / pre-commit hook 등 보호 파일 감지 시 자동 커밋 금지. 사용자 명시 승인(ASR) 후 진행. 검증 grep:
  ```bash
  PROTECTED_PATTERN='\.swiftlint\.yml|\.github/|Package\.swift|.*\.xcconfig|.*Podfile|\.pre-commit'
  PROTECTED_FILES=$(git diff --cached --name-only | grep -E "$PROTECTED_PATTERN")
  [ -n "$PROTECTED_FILES" ] && AskUserQuestion("36차: 보호 파일 변경 — $PROTECTED_FILES 커밋 승인?")
  ```

---

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| nothing to commit | staged 파일 없음 안내 | `git status` 확인 후 스테이징 요청 |
| commit-msg hook 실패 | 훅 오류 메시지 안내 | 메시지 형식 수정 후 재시도 |
| JIRA 티켓 조회 실패 | MCP 없이 수동 입력 안내 | 인자로 전달받은 티켓 ID 직접 사용 |
| 커밋 단위 판단 불명확 | 변경 파일 목록 출력 후 사용자 확인 | 사용자 지시에 따라 분리 |
| 분할 커밋 단독 검증 실패 | 실패 커밋의 검사 로그 끝과 원인을 보인다 | 묶음·순서를 고쳐 격리 검증부터 다시 — 실제 저장소에는 커밋하지 않는다 |

---

## Completion → Next

- 커밋 성공 시: 커밋 해시와 메시지 요약 출력 → `/fz-pr`로 PR 생성 가능
- 커밋 단위 분리 제안 시: 분리 계획 제시 후 사용자 확인 대기
- 훅 실패 시: 오류 원인 안내 → 메시지 수정 후 재시도
