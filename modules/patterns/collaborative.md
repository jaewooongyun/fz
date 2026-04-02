# Collaborative Design

> fz-plan 전용 패턴. 만들면서 직접 토론하여 설계를 고도화한다.
> 전제: team-core.md 로드 완료.

---

## 역할 배분

| 역할 | 에이전트 | 행동 |
|------|---------|------|
| Primary | plan-structure (O) | 구현 구조 설계 + Step 순서 결정 |
| Supporting | plan-impact (S) | 영향 범위 전담 (Exhaustive Impact Scan a~f) |
| Supporting | plan-edge-case (S) | 경계 케이스 + 실패 시나리오 발굴 |
| Supporting | review-arch (S) | 아키텍처 실현성 + 패턴 검증 |
| Supporting | review-direction (S) | 방향성 도전 + 대안 제시 (Round 0.5) |
| Supporting | memory-curator (S) | 관련 교훈 발굴 + plan-structure에 전달 |

## 2.5-Turn 적용 (Star-enhanced, 5명+)

### Round 0.5: 방향성 도전 (Direction Challenge)
```
review-direction: 접근 방향 분석 (6 perspectives)
  → SendMessage(plan-structure): "방향 도전: {현재 접근 요약}.
     Structural Fit: {판정}, Alternative Paths: {대안 2개+},
     Extensibility: {판정}. 방향 판정: PROCEED/RECONSIDER/REDIRECT"

plan-structure → SendMessage(review-direction):
  "반박: {대안 X 대비 현재 방향의 근거}. {추가 제약 설명}"

review-direction → SendMessage(plan-structure):
  "최종 판정: PROCEED — 현재 방향 유지. 의문점: {남은 질문}"
  또는 "최종 판정: RECONSIDER — 대안 B 재고 권고. 근거: {내용}"

review-direction → SendMessage(Lead): "방향 판정 완료: {PROCEED/RECONSIDER/REDIRECT}"
```

> RECONSIDER/REDIRECT 시 Lead가 사용자에게 보고 후 진행 여부 확인.

### Round 1: 초안 + 병렬 분석 (Star-enhanced, 5명)
```
plan-structure: 구현 계획 초안 작성 (Step 순서 + 변경 대상)
  → SendMessage(review-arch): "계획 초안입니다. 아키텍처 패턴 검토해주세요"
  → SendMessage(plan-impact): "계획 초안입니다. 영향 범위 분석해주세요"
  → SendMessage(plan-edge-case): "계획 초안입니다. 경계 케이스 찾아주세요"

[병렬 실행]
review-arch → SendMessage(plan-structure): "패턴 A vs B: A 레이어 위반, B 추천"
plan-impact → SendMessage(plan-structure): "영향 범위 {N}개 파일. 숨겨진 의존성: {내용}"
  → CC(plan-edge-case): "영향 범위에서 경계 케이스 확인 필요: {2-3건}"
plan-edge-case → SendMessage(plan-structure): "경계 케이스 {M}건: {요약}"
  → CC(plan-impact): "경계 케이스 중 영향 범위 확인 필요: {내용}"
```

핵심: plan-edge-case↔plan-impact CC 교차로 "경계 케이스가 영향 범위에서 발생" 연쇄 발견.

### Round 2: 피드백 반영 + 재검증
```
plan-structure: 피드백 반영하여 계획 수정
  → SendMessage(review-arch): "B 패턴으로 변경 + 방어 Step 추가. 재검증해주세요"

review-arch → SendMessage(plan-structure): 재검증 결과 + 잔여 이슈
```

### Round 0.5: 최종 보고
```
plan-structure → SendMessage(Lead):
  "최종 구현 계획: {N}개 Step. 피어 피드백 모두 반영 완료."

review-arch → SendMessage(Lead):
  "아키텍처 검증 완료. 리스크 매트릭스 + 영향 파일 + 엣지 케이스 커버리지: {내용}"
```

## Lead 역할

- Direction Challenge 결과 확인 (RECONSIDER/REDIRECT 시 사용자 에스컬레이션)
- 설계 스트레스 테스트 (Q1-Q5) 수행
- Codex 검증 위임 (fz-codex verify)
- 최종 계획 통합 + 구조화된 출력 생성

## adversarial과의 차이

- adversarial: 만들고 부수는 대립 → 제약 발견이 목적
- collaborative: 함께 만드는 협력 → 계획 완성이 목적
- collaborative에서도 각 Supporting이 고유 Lens로 문제를 발견하지만, 목적은 계획 개선

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-plan | 전용 통신 패턴 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
