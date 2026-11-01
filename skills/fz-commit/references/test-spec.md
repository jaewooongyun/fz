# fz-commit 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

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
| staged 변경 존재 + 티켓 ID 인자 전달 (또는 CLAUDE.md 에 팀 커밋 규칙 · 스킬 선언 존재) | `/fz-commit "<TICKET-ID>"` | Conventional Commit 형식 + 티켓 prefix 포함 커밋 생성 성공(git commit exit 0) + 커밋 해시·메시지 요약 출력 | normal |
| 서로 무관한 여러 기능 변경이 함께 staged | `/fz-commit` | 변경 파일 목록 출력 + 커밋 단위 분리 제안 제시 + 사용자 확인 대기(자동 커밋 0건) | edge-case |
| staged 목록에 `.swiftlint.yml`/`.github/`/`Package.swift`/`*.xcconfig` 등 보호 파일 포함 | `/fz-commit` | PROTECTED_PATTERN grep으로 보호 파일 감지 → 자동 커밋 차단 + 사용자 승인(AskUserQuestion) 요청(승인 전 커밋 0건) | edge-case |
| staged 파일 없음(`git diff --cached` 비어 있음) | `/fz-commit` | "staged 파일 없음" 안내 + `git status` 확인 요청, 커밋 미실행(커밋 0건) | failure |
| `commit-msg` 훅이 메시지 형식 거부 | `/fz-commit` | 훅 오류 메시지 안내 + 커밋 미생성(commit-msg exit≠0) → 메시지 형식 수정 후 재시도 안내 | failure |
| 나눈 커밋 하나가 단독으로 저장소 검사에 실패(개수 선언이 다른 커밋에 있음) | `/fz-commit` 기능 단위 분할 | 격리 clone 검증에서 실패 커밋과 원인 출력 + 경계·순서 조정 제안, 실제 저장소 커밋 0건 | edge-case |

---
