# 테스트 케이스 (fz-plan)

> fz-plan(계획 수립 + 영향 범위 분석 + 설계)의 트리거 정확도와 Phase/Gate 동작을 검증한다.

### Triggering Test

#### should-trigger (description '예:' 트리거 어휘 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "새 기능 계획 세워줘" | trigger | 예: "계획 세워줘" — 핵심 유스케이스 |
| "이 화면 설계해줘" | trigger | 예: "설계해줘" |
| "아키텍처 잡아줘" | trigger | 예: "아키텍처 잡아줘" |
| "이 요구사항 분석해줘" | trigger | 예: "요구사항 분석" |
| "이 모듈 리팩토링 계획 세워줘" | trigger | intent-triggers: 리팩토링/refactor |

#### should-NOT-trigger (Boundaries Will Not / description '비사용' 기반)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이거 구현해줘" | NOT trigger | → /fz-code | 비사용: 구현 →fz-code |
| "어떻게 접근할지 모르겠어, 방식이 여러 개야" | NOT trigger | → /fz-discover | 비사용: 접근 불명확 시 →fz-discover |
| "이 코드 수정해줘" | NOT trigger | → /fz-code | Boundaries Will Not: 코드 수정 |
| "빌드 돌려줘" | NOT trigger | → /fz-code | Boundaries Will Not: 빌드 실행 |

### Functional Test (Given/When/Then)

| Given | When | Then | type |
|-------|------|------|------|
| 인자에 `ASD-\d+` 패턴이 포함된 요구사항 + Serena 활성 가능 | `/fz-plan "ASD-\d+ 새 화면 계획 세워줘"` | Phase 0에서 `{CWD}/ASD-xxxx/` 폴더 + index.md 생성 → Gate 0(Work Dir Ready) 3/3 통과 → Phase 1 영향 분석 후 Gate 1(Plan Ready) 통과 + plan-v1.md 기록 | normal |
| SOLO 모드 + 새 아키텍처 결정 요구 | `/fz-plan "새 결제 모듈 설계해줘"` | Phase 0.5에서 6개 관점 검토 + 대안 ≥2 제시 → Gate 0.5(Direction Validated) 통과(판정 PROCEED) + direction-challenge.md 기록 | normal |
| 계획 핵심 차원이 외부 primitive(CLI flag/config key)에 의존 + 미검증 상태 | `/fz-plan "외부 CLI 옵션 기반으로 계획 세워줘"` | Phase 0c에서 3 axes(존재/권한·경계/결과 contract) 분류 → 미검증 axis는 차원 제외 또는 explicit assumption tag, probe 필요 시 /fz-discover 선행 → Gate 0c 미통과 시 Plan 작성 차단 | edge-case |
| "그냥/가볍게" 신호 + 단순 추가 작업 | `/fz-plan light "버튼 추가 계획 가볍게"` | Phase 1만 실행, Phase 0.5/2/3 미호출 → plan-light.md 산출 (단 산출물에 전수/카운트/부정 주장 포함 시 Coverage Gate 생략 불가) | edge-case |
| Serena MCP 연결 실패 | `/fz-plan "이 기능 영향 범위 분석해줘"` | 에러 대응에 따라 Grep + Glob 폴백으로 심볼 탐색 전환(Serena 미사용) → Phase 0b 계속 진행 | failure |
| 네이티브 Workflow 도구 미가용 (팀 에이전트 모드 불가) | `/fz-plan "5+ Step 대규모 기능 계획해줘"` | SOLO 계획 수립으로 폴백 + 폴백 사유 experiment-log 기록 → Phase 1 산출물 정상 생성 | failure |
