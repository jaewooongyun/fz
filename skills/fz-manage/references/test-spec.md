# 테스트 케이스 (fz-manage)

### Triggering Test

**should-trigger** (description 핵심 어휘·'예:' 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "스킬 목록 보여줘" | trigger | description '예:' — `list` 전체 인벤토리 |
| "건강 체크해줘" | trigger | description '예:' — `check` 통합 건강 체크 |
| "벤치마크 돌려줘" | trigger | description '예:' — `benchmark` 일괄 품질 평가 |
| "의존성 확인해줘" | trigger | description 핵심 어휘 '의존성 확인' — `deps` 그래프 |

**should-NOT-trigger** (Boundaries Will Not·description '비사용:' 기반)

| 쿼리 | 예상 | redirect | 이유 |
|------|------|----------|------|
| "fz-test 스킬 새로 만들어줘" | NOT | `/fz-skill create` | 개별 스킬 생성·수정은 fz-skill 이관 (description 비사용) |
| "fz-plan 스킬 하나만 품질 평가해줘" | NOT | `/fz-skill eval` | 개별 스킬 품질 평가는 Will Not (benchmark는 전체 일괄만) |
| "계획부터 PR까지 워크플로우 구성해줘" | NOT | `/fz` | 워크플로우 가이드는 Will Not |
| "이 버그 코드 고쳐줘" | NOT | `/fz-fix` | 코드 수정은 각 워크플로우 스킬, Will Not |

### Functional Test

| Given | When | Then (pass/fail oracle) | type |
|-------|------|--------------------------|------|
| `skills/*/SKILL.md`에 fz-* 스킬 전부 존재 | `/fz-manage benchmark` | 전체 fz-* Static Analysis 8항목 실행 + 스킬별 점수(80점 만점) 산출·정렬 + 하위 3개 개선 제안 출력 → Gate: Benchmark Complete 3/3 통과 | normal |
| `skills/*/SKILL.md` + `agents/*.md` 존재 | `/fz-manage check` | 17개 검증 항목 전부 판정 출력 + "총 점수: N%" 산출 (YAML 필수 필드·MCP 유효성·provides/needs 체인·크기·깨진 참조 등 각 항목 OK/WARN/FAIL) | normal |
| Relevance Scorer 결과 ≥ 0.70 모듈이 5개 미만 | `/fz-manage reflect-to-module <feedback_file>` | Gate 발동 → "threshold 낮춰서 재실행?" 사용자 확인 요청, 자동 적용 0건 (사용자 명시 승인 전 Edit 차단) | edge-case |
| 한 SKILL.md의 YAML frontmatter 손상 | `/fz-manage list` | YAML 파싱 실패 보고 + 수동 확인 폴백 안내 (에러 대응 테이블) | failure |
