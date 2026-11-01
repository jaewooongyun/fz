# fz-code 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering

**should-trigger** (description '예:' 트리거 어휘 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "구현해줘" | trigger | description 예 — 핵심 유스케이스(코드 구현) |
| "코드 짜줘" | trigger | description 예 — 코드 작성 |
| "만들어줘" | trigger | description 예 + intent-trigger "만들어" |
| "개발해줘" | trigger | description 예 + intent-trigger "개발" |
| "빌드해줘" | trigger | description 예 — 매 Step 빌드 검증 |

**should-NOT-trigger** (description '비사용:' / Boundaries Will Not의 대안 스킬)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 버그 고쳐줘" | NOT trigger | /fz-fix | description 비사용 "버그 수정 →fz-fix" |
| "아키텍처 설계해줘" | NOT trigger | /fz-plan | description 비사용 "계획·설계 →fz-plan" + Will Not "계획 없이 대규모 코드 생성 (→/fz-plan)" |
| "구현한 코드 리뷰해줘" | NOT trigger | /fz-review | Boundaries Will Not "코드 리뷰/검증 (→/fz-review)" |

### Functional

| Given | When | Then | type |
|-------|------|------|------|
| 승인된 `{WORK_DIR}/plan/plan-final.md`가 존재 | `/fz-code "검증된 계획대로 구현해줘"` | Plan의 모든 Step을 순차 구현 + 매 Step 빌드 성공 + Gate 3 체크리스트 전 항목 통과(모든 Step 완료·빌드 성공·아티팩트 기록 완료) | normal |
| 구현 중 같은 대상에 switch/if/enum case 3개+ 발생 | Step N 구현 진행 | "분기 폭증" 마찰 신호를 보고 형식(신호/위치/현상/플랜 재검토)으로 출력 + 사용자 "계속" 응답 전까지 구현 진행 중단(무시 강행 없음) | edge-case |
| Plan 존재 + 모드 게이트에서 light 선택(또는 `light` 인자 · 신호어) | `/fz-code light "가볍게 구현해줘"` | code-pair 미기동 · Plan 의 모든 Step 을 Lead 가 직접 구현 + 매 Step 빌드 성공 · 원장 게이트 + GPT 교차 검증(8.5) 그대로(끈 세션이면 `[GPT 미사용]`) | edge-case |
| Step 구현 중 컴파일 에러로 빌드 2회 연속 실패 | Step N 빌드 검증 | 직접 수정 후 재빌드(`/sc:sc-troubleshoot --fix` 는 선택), 반복 실패 시 `/ralph-loop` 래더로 에스컬레이션 — 빌드 성공 확인 전 다음 Step 진입 안 함(silent fail 없음) | failure |
