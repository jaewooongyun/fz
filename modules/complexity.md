# 5차원 복잡도 평가

> /fz Phase 2에서 참조. 5차원 점수 합산 → SOLO/TEAM 모드 결정.

## 5차원 점수 계산

각 차원 0-2점, 합산 0-10점:

| 차원 | 0점 | 1점 | 2점 |
|------|-----|-----|-----|
| Scope | 단일 파일/함수 | 모듈/패키지 단위 | 시스템/다중 서비스 |
| Depth | 단순 변경 (값, 텍스트) | 로직/알고리즘 변경 | 아키텍처/패턴 변경 |
| Risk | 독립적, 롤백 쉬움 | 일부 컴포넌트 영향 | 광범위 영향, 롤백 어려움 |
| Novelty | 기존 패턴 재사용 | 부분 새 패턴 도입 | 완전 새 설계/도입 |
| Verification | 눈으로 확인 가능 | 빌드/테스트 필요 | 다중 검증/Cross-model 필요 |

## 모드 결정

| 합산 | 모드 | 실행 방식 |
|------|------|---------|
| 0-3 | SOLO | Lead(O) 단독, 순차 실행 |
| 4+ | TEAM | Lead(O) + Primary(O) + N×Sonnet |

> **SOLO + Supporting 하이브리드**: SOLO 모드(0-3)에서도 특정 스킬은 조건부 Supporting 에이전트를 1명 추가할 수 있다.
> 이 경우 TeamCreate는 사용하지 않고, Lead가 Supporting을 Agent로 직접 스폰한다.
> 예: fz-fix (복잡도 3+) → impl-correctness + review-arch (team-registry.md 참조)

## Override 플래그 우선순위

점수 무관 강제 적용.

| 플래그 | 모드 | 실행 모드 |
|-------|------|---------|
| `--solo` | SOLO 강제 | STANDARD |
| `--team` | TEAM 강제 | STANDARD |
| `--deep` | TEAM 강제 | STANDARD + 교차 검증 강화 |
| `--batch` | SOLO 유지 | BATCH (worktree 병렬) |
| `--loop` | TEAM 유지 | LOOP (자동 반복 + 에스컬레이션) |

## 실행 모드 자동 분기

| 조건 | 실행 모드 |
|------|---------|
| SOLO + `--batch` | BATCH |
| SOLO + 독립 대상 3개+ | BATCH |
| TEAM + `--loop` | LOOP |
| TEAM + Gate 반복 예상 | LOOP |

> 상세: `modules/execution-modes.md`
