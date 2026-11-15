# fz-skill 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering Test

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "스킬 만들어줘" | trigger | create 서브커맨드 (description '예:' 핵심) |
| "에이전트 만들어줘" | trigger | new-agent 서브커맨드 (description '예:') |
| "스킬 평가해줘" | trigger | eval 서브커맨드 (description '예:') |
| "fz-plan description 최적화해줘" | trigger | optimize 서브커맨드 (description "최적화") |
| "fz-old 스킬 삭제해줘" | trigger | delete 서브커맨드 (description "삭제") |
| "가이드 문서 최신화해줘" | NOT trigger | → fz-modernize (description '비사용: 가이드·문서 갱신') |
| "스킬 목록 보여줘" | NOT trigger | → fz-manage list/deps (Will Not: 목록/의존성 조회) |
| "전체 스킬 일괄 평가해줘" | NOT trigger | → fz-manage benchmark (Will Not: 일괄 평가) |
| "이 코드 수정해줘" | NOT trigger | → fz-code / fz-fix (Will Not: 코드 수정) |

### Functional Test

| Given | When | Then | type |
|-------|------|------|------|
| 스킬 이름+목적이 명확 (L3 자동 조건 충족) | `/fz-skill create fz-test "테스트 자동화 스킬"` | Gate "Skill Created" 체크리스트 8/8 통과 + 생성 파일 경로 출력 | normal |
| 대상 스킬 SKILL.md 존재 | `/fz-skill eval fz-plan` | Static Analysis 8항목 전부 실행 + Triggering 정확도 ≥90% → Gate "Eval Complete" 통과 (비리뷰형이라 §6.4 N/A — 4항목 중 3항목 적용) | normal |
| skill-creator 플러그인 미설치 | `/fz-skill eval fz-plan --runtime` | Runtime Trigger Eval = SKIP(WARN) + 설치 안내, 정적 eval만 중단 없이 계속 | edge-case |
| 삭제 대상이 타 스킬/모듈/에이전트에서 참조됨 | `/fz-skill delete fz-old` | Grep 역참조 탐지 → 영향 보고 테이블 + 경고 + AskUserQuestion, 사용자 미확인 시 삭제 미실행 | failure |
| 존재하지 않는 스킬명 지정 | `/fz-skill eval fz-nonexistent` | "eval 대상 스킬 없음" 에러 → 스킬 목록 출력 + AskUserQuestion (에러 대응 테이블) | failure |
