# 사전 정의 파이프라인 (Pipelines)

> /fz Phase 3에서 의도 키워드와 매칭하는 사전 정의 파이프라인 14개.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | Phase 3 파이프라인 해결 |
| /fz-manage | 파이프라인 의존성 그래프 조회 |
| /fz-skill | provides/needs 체인 검증 |

## 파이프라인 목록

### 1. explore

| 항목 | 값 |
|------|---|
| 트리거 | `찾아, 탐색, 구조, 영향, 의존성` |
| 체인 | fz-search |
| 기본 모드 | SOLO |
| TEAM 모드 | search-symbolic + search-pattern (cross-verify) |

### 2. explore-plan

| 항목 | 값 |
|------|---|
| 트리거 | `찾아.*계획, 분석.*설계, 탐색.*후.*계획` |
| 체인 | fz-search → fz-plan |
| 기본 모드 | SOLO |
| TEAM 모드 | search 팀 → plan 팀 (순차) |

### 3. discover

| 항목 | 값 |
|------|---|
| 트리거 | `어떻게.*좋을까, 트레이드오프, 뭐가.*맞을까` |
| 체인 | fz-discover |
| 기본 모드 | SOLO |
| TEAM 모드 | plan-structure(★O) + review-arch (adversarial) |

### 4. bug-hunt

| 항목 | 값 |
|------|---|
| 트리거 | `버그.*찾아, 크래시.*원인, 에러.*추적` |
| 체인 | fz-search → fz-fix |
| 기본 모드 | SOLO |
| 게이트 | ✓ build (fz-fix 후) |

### 5. quick-fix

| 항목 | 값 |
|------|---|
| 트리거 | `수정, 고쳐, 변경해줘, 바꿔줘` |
| 체인 | fz-fix |
| 기본 모드 | SOLO |
| 게이트 | ✓ build |

### 6. plan-only

| 항목 | 값 |
|------|---|
| 트리거 | `계획, 설계, 아키텍처` |
| 체인 | fz-plan |
| 기본 모드 | SOLO |
| TEAM 모드 | plan-structure(★O) + plan-tradeoff + plan-edge-case + plan-impact (collaborative) |
| 게이트 | ✓ direction-challenge (Phase 0.5) + ✓ stress-test(Q1-Q5) |

### 7. plan-to-code

| 항목 | 값 |
|------|---|
| 트리거 | `계획.*구현, 설계.*개발, 만들어줘` |
| 체인 | fz-plan → fz-code |
| 기본 모드 | TEAM |
| TEAM 모드 | plan 팀 → impl-correctness(★O) + review-arch |
| 게이트 | ✓ direction-challenge + ✓ stress-test + ✓ build + ✓ codex check |

### 8. code-only

| 항목 | 값 |
|------|---|
| 트리거 | `구현, 코드, 개발` (계획 이미 있을 때) |
| 체인 | fz-code |
| 기본 모드 | SOLO |
| TEAM 모드 | impl-correctness(★O) + review-arch (pair-programming) |
| 게이트 | ✓ build + ✓ friction-detect |

### 9. code-to-review

| 항목 | 값 |
|------|---|
| 트리거 | `구현.*리뷰, 만들고.*검토` |
| 체인 | fz-code → fz-review |
| 기본 모드 | TEAM |
| TEAM 모드 | impl-correctness(★O) → review-arch(★O) + review-quality (live-review) |
| 게이트 | ✓ build + ✓ codex check |

### 10. review-only

| 항목 | 값 |
|------|---|
| 트리거 | `리뷰, 검증, 품질` |
| 체인 | fz-review |
| 기본 모드 | SOLO |
| TEAM 모드 | review-arch(★O) + review-quality (live-review) |

### 11. review-to-ship

| 항목 | 값 |
|------|---|
| 트리거 | `리뷰.*커밋, 검토.*PR` |
| 체인 | fz-review → fz-commit → fz-pr |
| 기본 모드 | TEAM |
| TEAM 모드 | review 팀 → Lead 커밋/PR |
| 게이트 | ✓ codex check (커밋 전) |

### 12. fix-to-ship

| 항목 | 값 |
|------|---|
| 트리거 | `고쳐서.*커밋, 수정.*PR` |
| 체인 | fz-fix → fz-review → fz-commit |
| 기본 모드 | SOLO |
| 게이트 | ✓ build + ✓ codex check |

### 13. full-cycle

| 항목 | 값 |
|------|---|
| 트리거 | `처음부터.*끝까지, 계획부터.*PR` |
| 체인 | fz-plan → fz-code → fz-review → fz-commit → fz-pr |
| 기본 모드 | TEAM |
| TEAM 모드 | 각 단계별 Primary 승격 (plan-structure → impl-correctness → review-arch) |
| 게이트 | 전체 게이트 자동 삽입 |
| 특수 | opus Primary 2개 원칙 예외 (단계별 순차이므로 동시 아님) |

### 14. peer-review

| 항목 | 값 |
|------|---|
| 트리거 | `피어리뷰, PR.*리뷰, 팀원.*코드` |
| 체인 | fz-peer-review |
| 기본 모드 | SOLO |
| TEAM 모드 | review-arch(★O) + review-quality (live-review) |

### 15. drift-check

| 항목 | 값 |
|------|---|
| 트리거 | `드리프트\|아키텍처.*점검\|레이어.*위반\|전체.*스캔\|점검해줘\|훑어봐\|전체.*봐줘\|전체.*확인해줘` |
| 체인 | fz-codex drift |
| 기본 모드 | SOLO |
| 실행자 | Lead → Codex drift (fz-drift 스킬) |
| 권장 시점 | PR 전, 대규모 리팩토링 후 |

### 16. plan-parallel

| 항목 | 값 |
|------|---|
| 트리거 | `독립.*플랜\|GPT.*계획\|교차.*플랜\|플랜.*검증\|병렬.*플랜\|독립.*계획` |
| 체인 | fz-codex plan |
| 기본 모드 | SOLO |
| 실행자 | Lead → Codex plan (fz-planner 스킬) |
| 주의 | **C4 원칙**: Claude 계획 텍스트 전달 금지. 요구사항만 공유 |
| 출력 | Claude 계획과 교차 비교용 독립 계획서 |

### 17. memory-audit

| 항목 | 값 |
|------|---|
| 트리거 | `메모리.*정리\|메모리.*관리\|메모리.*감사\|교훈.*회상\|memory.*audit\|memory.*gc` |
| 체인 | fz-memory audit → (선택) fz-memory gc |
| 기본 모드 | SOLO |
| 게이트 | 없음 |

---

## 동적 파이프라인 구성

사전 정의 17개에 매칭되지 않을 때 provides/needs 그래프로 자동 구성:

```
provides/needs 체인:
needs=none (진입점): fz-plan, fz-search, fz-fix, fz-discover
needs=planning:      fz-code
needs=code-changes:  fz-review, fz-commit
needs=commit:        fz-pr
```

알고리즘:
1. 최종 목표 스킬의 needs 확인
2. needs를 provides하는 스킬 역추적 (재귀)
3. 토폴로지 정렬 → 선형 파이프라인
4. 끊어진 체인 → AskUserQuestion

## 설계 원칙

- Progressive Disclosure Level 3 (/fz Phase 3에서만 로드)
- 500줄 이하 유지
- 파이프라인 추가/수정 시 fz SKILL.md 사용 예시와 동기화
