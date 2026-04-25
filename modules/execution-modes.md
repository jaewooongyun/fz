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
- 새 코드 생성 (RIB, 모듈 등 아키텍처 판단 필요)
- review-arch 검증이 필요한 구조적 변경

### BATCH merge 후 통합 게이트 (필수)

모든 worktree merge 완료 후 반드시 수행:
1. 프로젝트 전체 빌드 (modules/build.md)
2. 빌드 실패 시: 충돌 파일 식별 → 수동 해결 → 재빌드
3. 빌드 성공 → 파이프라인 다음 스킬 진행
4. (선택) /sc:analyze → merge 후 정적 분석

### BATCH 자동 제안

fz-plan 또는 fz-code에서 아래 조건 감지 시 제안 (강제 아님):

| 조건 | 제안 |
|------|------|
| plan에 독립 Step 3개+ | "/batch 병렬 실행 가능" 제안 |
| 동일 패턴 반복 3회+ | "/batch 전환" 제안 |

## LOOP 모드 상세

- /ralph-loop 파라미터: `--max-iterations N --completion-promise "GATE_PASSED"`
- 에스컬레이션 래더 (각 반복마다 전략 상승):

### 에스컬레이션 래더 (스킬별 구체화)

| 스킬 | Gate | 1회 실패 | 2회 실패 | 3회 실패 |
|------|------|---------|---------|---------|
| fz-code | build | 에러 직접 수정 | /sc:troubleshoot | /simplify → AskUser |
| fz-fix | build | 에러 직접 수정 | /sc:troubleshoot | /fz-codex check 보조 진단 1회 → AskUser |
| fz-review | Reflection | 이슈 재확인 | Codex 검증 | AskUser |
| fz-plan | Stress Test | 계획 수정 | 계획 재작성 | AskUser |

### 스킬별 LOOP 파라미터

| 스킬 | completion-promise | max-iterations | 대상 Gate |
|------|-------------------|----------------|----------|
| fz-plan | STRESS_TEST_PASS | 2 | 설계 스트레스 테스트 (Critical < 2) |
| fz-code | BUILD_SUCCESS | 3 | 빌드 검증 |
| fz-fix | FIX_VERIFIED | 3 | 빌드 검증 |
| fz-review | REFLECTION_80 | 3 | Reflection Rate ≥ 80% (N≥10에서만 gating — 참조: `modules/cross-validation.md § Reflection Rate threshold`) |

## SIMPLIFY 게이트 상세

- /simplify는 **2단계 트리거** 시스템

### 필수 gate (스킵 불가, 자동 실행)
1. Step에서 새 함수/메서드 3개+ 생성 → 과잉 추상화 감지
2. Step에서 100줄+ 코드 추가 → 복잡도 감소 필요
3. 3회 빌드 실패 후 성공 → 패치 누적 품질 저하

### 선택 suggestion (사용자 스킵 가능)
1. fz-code Step 완료 후 (위 조건 미해당 시)
2. fz-review 시작 전 (pre-review cleanup)

### 설계 의도 보존
- `focus` 파라미터에 Plan의 핵심 설계 결정을 포함한다
- 예: `/simplify focus on "Strategy 패턴 유지, UseCase 분리 보존"`
- Plan의 Anti-Pattern Constraints에 명시된 구조는 simplify가 변경하지 않는다
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
