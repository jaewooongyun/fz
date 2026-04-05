# Landscape Exploration (Adversarial)

> fz-discover 전용 패턴. 경로를 만들고 비용/리스크를 탐색하는 adversarial 루프.
> 핵심 전환: "제약으로 탈락" → "비용/리스크로 비교". 어떤 경로도 탈락시키지 않는다.
> 전제: team-core.md 로드 완료.

---

## 역할 배분

| 역할 | 에이전트 | 행동 |
|------|---------|------|
| Primary | plan-structure (O) | 경로 생성 + 각 경로의 전제조건/실현성 평가 |
| Supporting | review-arch (S) | 각 경로의 비용/리스크 탐색 + 조건 불변성(🔒/🔓) 판별 |

## 2.5-Turn 적용 (Mesh, 2명)

### Round 1: 경로 생성 + 비용 탐색
```
plan-structure: 경로 2-4개 생성 (각각의 전제조건 명시)
  → SendMessage(review-arch): "경로입니다. 각 경로의 비용/리스크를 탐색해주세요"

review-arch: 각 경로의 비용/리스크 + 조건 불변성 판별
  → SendMessage(plan-structure): "경로 A: 비용 낮음/리스크 중간. 조건 X는 🔒불변, Y는 🔓가변(관성). 근거: {코드}"
```

### Round 2: 추가 경로 + 조건 도전
```
plan-structure: 🔓가변 조건을 무시하는 새 경로 탐색 + 기존 경로 조건 업데이트
  → SendMessage(review-arch): "조건 Y를 무시한 경로 D입니다. 실현 가능한지 확인해주세요"

review-arch: 경로 D 실현성 + 조건 Y 무시 시 실제 비용 산정
  → SendMessage(plan-structure): "Y 무시 시 비용: {구체적}. 새 조건 Z 발견: {근거}"
```

### Round 0.5: Landscape Map 보고
```
plan-structure → SendMessage(Lead): "경로 A/B/C/D. Trade-off Table. Open Questions 3개"
review-arch → SendMessage(Lead): "조건 불변성 판별 완료. 🔒 3개, 🔓 2개. 비용/리스크 요약"
```

## Lead 역할

- 사용자 대화 관리 (질문 수집 → 새 **조건**으로 변환, 제약이 아님)
- Landscape Map 최종 통합
- 외부 모델 실행 (TEAM --deep 시): Codex에게 "완전히 다른 경로" 탐색 요청
- 교착 시: Trade-off Table 제시 + "plan이 판단합니다" 안내

## 핵심 원칙

- plan-structure가 경로를 만들고, review-arch가 **비용/리스크를 밝힌다** (부수지 않는다)
- 조건은 🔒불변(기술적 불가능)과 🔓가변(관성/비용)으로 구분
- **어떤 경로도 탈락시키지 않는다** — "비용 X를 감수하면 가능"으로 유지
- discover는 결론을 내리지 않는다 — landscape를 그리고 plan에 넘긴다

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-discover | 전용 통신 패턴 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
