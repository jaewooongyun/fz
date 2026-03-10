# 실행 모드 확장 (Execution Modes)

> /batch, /simplify, /ralph-loop 통합 정책. 스킬에서 참조.

## 3가지 실행 모드

| 모드 | 도구 | 트리거 | 용도 |
|------|------|--------|------|
| BATCH | /batch | 독립 작업 3개+, --batch 플래그 | worktree 격리 병렬 실행 |
| LOOP | /ralph-loop | Gate 반복 예상, --loop 플래그 | 자동 반복 + 에스컬레이션 |
| SIMPLIFY | /simplify | Step 완료 후 (선택) | 코드 정리 + 과잉 설계 감지 |

## BATCH 모드 상세

- /batch 호출 시 `--no-pr` 필수 (PR은 fz-pr로)
- 각 worktree = 독립 SOLO 실행 (TeamCreate 미사용)
- Lead가 N개 worktree 오케스트레이션 → 결과 merge
- TEAM과 배타적: BATCH일 때 TeamCreate 불필요

### BATCH 적합 조건

| 조건 | 예시 |
|------|------|
| 독립 파일 수정 3개+ | 에이전트/모듈 12개 일괄 수정 |
| 동일 패턴 반복 적용 | 용어 통일, 섹션 추가 등 |
| 파일 간 의존성 없음 | 각 파일이 독립적으로 수정 가능 |

### BATCH 부적합 조건

- 파일 간 의존성 있음 (A 수정이 B에 영향)
- 2개 이하 파일 변경
- 코드 생성 (빌드 검증 필요)

## LOOP 모드 상세

- /ralph-loop 파라미터: `--max-iterations N --completion-promise "GATE_PASSED"`
- 에스컬레이션 래더 (각 반복마다 전략 상승):

### 에스컬레이션 래더 (공통)

| Level | 전략 | 적용 |
|-------|------|------|
| L1 | 에러 직접 분석 → 수정 | 모든 Gate |
| L2 | /sc:troubleshoot → 자동 진단 | 빌드 Gate |
| L3 | /simplify → 복잡도 감소 | 코드 Gate |
| L4 | AskUserQuestion → 사용자 에스컬레이션 | 최종 |

### 스킬별 LOOP 파라미터

| 스킬 | completion-promise | max-iterations | 대상 Gate |
|------|-------------------|----------------|----------|
| fz-plan | STRESS_TEST_PASS | 2 | 설계 스트레스 테스트 (Critical < 2) |
| fz-code | BUILD_SUCCESS | 3 | 빌드 검증 |
| fz-fix | FIX_VERIFIED | 3 | 빌드 검증 |
| fz-review | REFLECTION_80 | 3 | Reflection Rate ≥ 80% |

## SIMPLIFY 게이트 상세

- /simplify는 선택적 게이트 (필수 아님)
- 트리거 조건:
  1. fz-code Step 완료 후 (코드 변경이 있을 때)
  2. fz-review 시작 전 (pre-review cleanup)
- `focus` 파라미터: 현재 Step의 관심사로 좁힘
- 결과: 수정 적용 → 빌드 Gate 재확인

## 모드 결정 플로우

| 합산 | 기본 모드 | 실행 모드 | 조건 |
|------|----------|----------|------|
| 0-3 | SOLO | STANDARD | 기본 |
| 0-3 | SOLO | BATCH | --batch 또는 독립 작업 3개+ |
| 4+ | TEAM | STANDARD | 기본 |
| 4+ | TEAM | LOOP | --loop 또는 Gate 반복 예상 |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | 모드 결정 + 실행 오케스트레이션 |
| /fz-code | LOOP(빌드 Gate) + SIMPLIFY(Step 후) |
| /fz-fix | LOOP(빌드 Gate) |
| /fz-review | LOOP(Reflection Rate) + SIMPLIFY(pre-review) |

## 설계 원칙

- Progressive Disclosure Level 3 (BATCH/LOOP 트리거 시에만 로드)
- 500줄 이하 유지
