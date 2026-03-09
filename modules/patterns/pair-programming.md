# Pair Programming

> fz-code 전용 패턴. 구현하면서 실시간으로 품질을 확인한다.
> 전제: team-core.md 로드 완료.

---

## 역할 배분

| 역할 | 에이전트 | 행동 |
|------|---------|------|
| Primary | impl-correctness (O) | 코드 구현 + 테스트 작성 |
| Supporting | review-arch (S) | 아키텍처 실현성 + 패턴 일관성 검증 |

## 2.5-Turn 적용 (Mesh, 2명)

### Round 1: 구현 + 검증
```
impl-correctness: Step N 구현 완료
  → SendMessage(review-arch): "Step N 구현 완료. 아키텍처 관점에서 검토해주세요: {변경 요약}"

review-arch: 구현 코드를 아키텍처/패턴 관점에서 검토
  → SendMessage(impl-correctness): "아키텍처 피드백: {이슈 목록}. 수정 제안: {내용}"
```

### Round 2: 피드백 반영 + 재확인
```
impl-correctness: 피드백 반영하여 코드 수정
  → SendMessage(review-arch): "피드백 반영 완료. 재확인해주세요"

review-arch: 수정 확인 + 잔여 이슈
  → SendMessage(impl-correctness): "LGTM" 또는 "잔여 이슈 {N}건: {내용}"
```

### Round 0.5: 최종 보고
```
impl-correctness → SendMessage(Lead): "Step N 구현 완료. 아키텍처 피드백 반영됨."
review-arch → SendMessage(Lead): "아키텍처 검증 완료. 잔여 이슈: 없음/있음"
```

## 구현 중 질문 패턴

2.5-Turn 외에, 구현 중간에 즉석 질문이 가능:
```
impl-correctness → SendMessage(review-arch):
  "이 UseCase에서 두 Repository를 조합하는데, Workflow로 빼야 할까요?"

review-arch → SendMessage(impl-correctness):
  "네, 기존 패턴상 Workflow가 맞습니다. 참고: {파일 경로}"
```
이 즉석 질문은 2.5-Turn 메시지 카운트에 포함하지 않는다.
다만 Round 0.5 이전까지만 허용.

## Lead 역할

- 계획(Step 목록) 전달 → 에이전트에 구현 지시
- 매 Step 완료 후 빌드 검증 수행
- 빌드 실패 시 에러 정보를 impl-correctness에 전달
- Codex 검증 위임 (fz-codex check)

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-code | 전용 통신 패턴 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
