# 테스트 케이스 (fz-discover)

### Triggering Test

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "이 기능을 어떻게 구현하면 좋을까?" | trigger | 불명확한 요구사항 정제 (핵심 유스케이스) |
| "이 두 방법 중 어느게 나을까?" | trigger | 트레이드오프 비교 |
| "A랑 B 차이점이 뭐야?" | trigger | 비교 질문 |
| "이 방식에 놓치고 있는게 있을까?" | trigger | 맹점 탐지 |
| "이 설계 어떻게 생각해?" | trigger | 의견 요청 |
| "방향 정해졌으니 구현 계획 세워줘" | NOT trigger | → fz-plan (방향 확정 후 계획 수립) |
| "이 함수 어디서 쓰는지 찾아줘" | NOT trigger | → fz-search (코드 위치 탐색) |
| "이 버그 고쳐줘" | NOT trigger | → fz-fix (코드 직접 수정) |
| "이 코드 빌드해줘" | NOT trigger | → fz-code (빌드 실행) |
| "명확한 요구사항이니 단순 설계만 해줘" | NOT trigger | → fz-plan (명확한 요구사항의 단순 설계) |

### Functional Test

| Given | When | Then | type |
|-------|------|------|------|
| 인자에 `ASD-\d+` 패턴 포함 + 불명확한 상태 저장 위치 질문, Serena 가용 | `/fz-discover "ASD-100 이 상태를 어디에 저장할까?"` | Phase 0에서 `{CWD}/ASD-100/discover/` 자동 생성으로 Gate 0(Work Dir Ready) 통과 → Gate 1·2·3 체크리스트 전부 통과 → 산출물에 경로 ≥2개(전제조건/비용/리스크 열 채워짐) + Open Questions 포함 | normal |
| 한 경로가 우세해 보이는 비교 질문 (Few-shot BAD 유발 조건) | `/fz-discover "A랑 B 중 뭐가 나아?"` | Phase 3 산출물이 단일 "유일한 해"로 수렴하지 않음 — Trade-off Table에 경로 ≥2개 유지 + 🔒/🔓 구분, 경로 "선택/결론" 문장 부재 (Gate 3 통과, 결론은 plan 위임) | edge-case |
| Phase 1 제약 매트릭스에 primitive 의존 가정(CLI flag 등) 존재, 3 axes(존재 / 권한·경계 / 결과 contract) 중 일부 미검증 | `/fz-discover "이렇게 flag 하나로 처리해도 괜찮을까?"` | Gate 1.5(Constraints Verified) 미통과 → Phase 2 Landscape 진입 차단, 또는 미검증 axis 가정을 explicit assumption tag 처리 후 Phase 2 차원에서 제외 | edge-case |
| Serena MCP 연결 실패 | `/fz-discover "이 모듈 구조를 어떻게 잡을까?"` | Serena 도구 에러 감지 → Grep+Glob 폴백으로 코드 탐색 지속해 Gate 1(Problem Framed) 통과(스킬 중단 없음), 둘 다 불가 시 코드 없이 원칙 기반 추론으로 진행 | failure |
