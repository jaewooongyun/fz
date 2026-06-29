# 테스트 케이스 (fz)

### Triggering Test

#### should-trigger (트리거되어야 함)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "계획부터 PR까지 해줘" | trigger | description 예시 — 다단계 멀티스킬 파이프라인 |
| "버그 찾아서 고쳐줘" | trigger | description 예시 — 탐색+수정 2스킬 조합 |
| "리뷰하고 커밋해줘" | trigger | description 예시 — 리뷰+커밋 조합 |
| "기능 구현하고 리뷰까지 --team" | trigger | argument-hint 예 — 멀티스킬 조합 + 모드 override |
| "뭘 써야 할지 모르겠는데 이거 처리해줘" | trigger | description "when unsure which specific skill to use" |

#### should-NOT-trigger (트리거되면 안 됨)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 함수 어디서 쓰여?" | NOT trigger | → fz-search | 단일 탐색 — 오케스트레이션 불필요 (description "Do NOT use for single-skill tasks") |
| "내 코드 리뷰만 해줘" | NOT trigger | → fz-review | 단일 리뷰 — 체이닝 없음 |
| "메모리 정리해줘" | NOT trigger | → fz-memory | 단일 메모리 관리 |
| "녹음 파일 회의록으로 변환" | NOT trigger | → fz-recording | 단일 작업 — 코드/스킬 조합 아님 |

### Functional Test (Given / When / Then)

| Given | When | Then | type |
|-------|------|------|------|
| intent-triggers에 2개 스킬이 매칭되는 멀티스킬 요청 | /fz "버그 찾아서 고쳐줘" | Gate 1 통과(스킬 ≥1 매칭) → Phase 4에서 파이프라인+팀 시각화 출력 + 사용자 승인 후 Phase 5 실행 시작 (Gate 4 통과) | normal |
| 5차원 복잡도 합산 4+로 평가되는 멀티스킬 요청 | /fz "새 기능 계획부터 구현·리뷰까지" | Gate 2 모드 판정 = TEAM(합산 4+) + Gate 3에서 Primary Worker opus 승격 + 나머지 에이전트 sonnet 배정 완료 | normal |
| 의도가 모호해 Confidence Low로 판정되는 요청 | /fz "안됨" | Gate 1에서 Confidence Low 판정 → AskUserQuestion 먼저 실행, 파이프라인 자동 실행 0건 | edge-case |
| 파이프라인 결정 완료, Phase 4에서 사용자가 승인 거부 | /fz "리뷰하고 커밋해줘" (확인 단계에서 거부) | Gate 4 미통과 → 스킬 로직/코드 수정 실행 0건 (Boundaries: 사용자 승인 없이 실행 안 함) | edge-case |
| intent-triggers 매칭 결과 0개인 입력 | /fz "{매칭 불가 입력}" | 에러 대응대로 AskUserQuestion 실행 + 사용자에게 스킬 직접 선택 요청, 임의 파이프라인 구성·실행 0건 | failure |
| TEAM 모드 결정됨, TeamCreate/에이전트 스폰 실패 | /fz "구현하고 리뷰" --team (스폰 실패) | 에러 대응대로 SOLO 폴백으로 전환 실행 (파이프라인 중단 아님) | failure |
