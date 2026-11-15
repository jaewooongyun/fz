# fz-memory 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "메모리 정리해줘" | trigger | audit 또는 gc |
| "교훈 떠올려줘" | trigger | recall |
| "memory audit" | trigger | audit |
| "코드 리뷰해줘" | NOT trigger | → fz-review |
| "버그 고쳐줘" | NOT trigger | → fz-fix |

### Functional

| Given | When | Then |
|-------|------|------|
| topic file에 [status: pending] 2건 | /fz-memory remind | 미반영 2건 보고 |
| MEMORY.md 250줄 | /fz-memory audit | 200줄 초과 경고 |
| L2에 stale artifact 키 3개 | /fz-memory gc | 3개 삭제 |
