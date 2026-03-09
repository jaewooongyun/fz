# Adversarial Constraint Discovery

> fz-discover 전용 패턴. 옵션을 만들고 부수는 adversarial 루프로 제약을 드러낸다.
> 전제: team-core.md 로드 완료.

---

## 역할 배분

| 역할 | 에이전트 | 행동 |
|------|---------|------|
| Primary | plan-structure (O) | 후보 옵션 생성 + 제약 회피 대안 설계 |
| Supporting | review-arch (S) | 아키텍처 관점 제약 발견 (트레이드오프 + 엣지 케이스 + 레이어 위반) |

## 2.5-Turn 적용 (Mesh, 2명)

### Round 1: 옵션 생성 + 제약 발견
```
plan-structure: 후보 옵션 2-3개 생성
  → SendMessage(review-arch): "후보입니다. 제약 위반 찾아주세요: {옵션들}"

review-arch: 각 후보의 아키텍처 제약 식별 (트레이드오프 + 엣지 케이스 + 레이어 위반)
  → SendMessage(plan-structure): "옵션 A는 C1 위반, 옵션 B는 C2 위반. 근거: {코드 참조}"
```

### Round 2: 대안 생성 + 재검증
```
plan-structure: 제약 회피하는 새 옵션 D 생성
  → SendMessage(review-arch): "새 옵션 D입니다. 기존 제약 C1, C2 모두 회피. 확인해주세요"

review-arch: 새 옵션 검증 + 새 제약 발견 시 추가
  → SendMessage(plan-structure): "C1, C2 OK. 새 제약 C3 발견: {근거}"
```

### Round 0.5: 최종 보고
```
plan-structure → SendMessage(Lead): "옵션 D 채택. 제약 매트릭스 최종본: {C1-C5}"
review-arch → SendMessage(Lead): "아키텍처 검증 완료. 트레이드오프 + 엣지 케이스 커버리지: {내용}"
```

## Lead 역할

- 사용자 대화 관리 (질문 수집 → 새 제약으로 변환)
- 제약 매트릭스 최종 통합
- 교착 시: 트레이드오프 명시 + 사용자 선택 요청

## 핵심 원칙

- plan-structure가 만들고, review-arch가 부순다
- 이 adversarial 루프에서 암묵적 제약이 드러난다
- Reject-Extract-Propose: 거절 시 즉시 제약 추출 + 대안 제시

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-discover | 전용 통신 패턴 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
