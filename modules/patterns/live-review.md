# Live Review

> fz-review, fz-peer-review 전용 패턴. 2명이 각자 다른 Lens로 동시 리뷰.
> 전제: team-core.md 로드 완료.

---

## 역할 배분

| 역할 | 에이전트 | Lens |
|------|---------|------|
| Primary | review-arch (O) | 아키텍처 결정 + 레이어 위반 |
| Supporting | review-quality (S) | 코드 품질 + Dead Code + 성능 + 리팩토링 완성도 |
| Supporting | review-correctness (S) | 요구사항 충족 (Phase 4.5만, RTM/plan 존재 시) |
| Supporting | memory-curator (S) | 관련 교훈 발굴 (기본 포함, lightweight recall) |
| Supporting | review-counter (S) | 역방향 검증 — 다른 에이전트 판단에 반론 (선택적 DA 패스) |

review-arch가 Primary (opus 승격). 나머지 Supporting (sonnet). Lead가 통합.
/fz-peer-review는 review-correctness, memory-curator 미포함.

## 2.5-Turn 적용 (Mesh, 2명)

### Round 1: 독립 분석 + 공유

각 리뷰어: 자기 Lens로 코드 변경사항 독립 분석
```
review-arch → SendMessage(review-quality): "아키텍처 이슈 {N}건 발견: {요약}"
review-quality → SendMessage(review-arch): "품질 이슈 {N}건 발견: {요약}"
```

### Round 2: 교차 피드백 + 수정

상대 Lens의 발견에 대해 자기 관점에서 피드백:
```
review-arch: quality 이슈 중 아키텍처 관련 부분에 추가 의견
  → SendMessage(review-quality): "이슈 Q3은 레이어 위반이기도 합니다. severity 상향 제안"

review-quality: arch 이슈 중 성능 영향 부분 보충
  → SendMessage(review-arch): "A2 이슈는 성능 영향 없음 확인. severity 유지 OK"
```

### L3 Integration (Round 2 이후, L3 결과 도착 시)

L3 에이전트 발견을 L1 리뷰어가 재분석하는 연쇄 패턴. (참조: team-core.md L3-to-L1 Feedback)

```
Lead → SendMessage(review-arch):
  "[L3 피드백] silent-failure-hunter: {N}건. 아키텍처 관점에서 에러 전파 설계 재확인해주세요"

review-arch → SendMessage(review-quality):
  "L3가 잡은 에러 처리 누락 중 {M}건은 dead code 연관. 확인해주세요"

review-quality → SendMessage(review-arch):
  "확인. {X}건 dead code 내부 (severity 하향), {Y}건 활성 코드 (severity 유지)"

양쪽 → SendMessage(Lead): "L3 피드백 통합 완료. 최종 조정: {내용}"
```

핵심: L3가 범용 탐지 → L1이 iOS 특화 판단 → 피어 간 교차로 false positive 제거.
조건: L3 이슈 0건이면 이 라운드 전체 스킵.

### Round 0.5: 최종 보고
```
review-arch → SendMessage(Lead):
  - 아키텍처 + 정확성 최종 이슈 목록 + severity 조정 근거 + L3 반영 사항

review-quality → SendMessage(Lead):
  - 품질 + 성능 최종 이슈 목록 + 피어 피드백 반영 사항 + L3 반영 사항
```

## Lead 역할

- 리뷰 대상(diff, symbols) 사전 수집 → 에이전트에 전달
- 2명의 최종 보고 통합 → severity 기반 우선순위 정렬
- 중복 이슈 병합 + false positive 최종 판정
- Codex 검증 위임 (fz-codex validate)
- 이슈 목록 확정 → 수정 또는 리포트 출력

## fz-review vs fz-peer-review

| | fz-review | fz-peer-review |
|---|----------|---------------|
| 대상 | 자기 코드 | 팀원 PR |
| Lead 후속 | 이슈 직접 수정 | 리뷰 코멘트 작성 |
| 통신 패턴 | 동일 (live-review) | 동일 |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-review | 자기 코드 리뷰 통신 패턴 |
| /fz-peer-review | 팀원 PR 리뷰 통신 패턴 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
