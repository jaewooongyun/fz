# Lesson Intake Decision Rule

> 새 교훈 후보 발생 시 기존 principle에 manifestation 추가 vs 새 principle 분리 결정 트리.
> 목적: 단일 principle에 무관한 manifestation 강제 stuffing 차단 (Codex Q1).

## Decision Tree

| 신규 교훈 후보 | 판정 | 행동 |
|--------------|------|------|
| Same failure mode as existing principle | **merge** | manifestation row 추가 (예: `lead-action-default.md` Trigger Matrix) |
| Different mode + evidence ≥ 3 sessions | **new principle** | 별도 모듈 생성. **Moratorium 종료 후에만** (참조: `health-plan/plan-v2.md §5`) |
| Different mode + evidence < 3 sessions | **candidate** | 5 sessions 관측 후 재판정. **활성 rule 등록 ❌** |

**Evidence 출처**: `experiment-log.md §5.4` 또는 `fz:checkpoint:*` memory keys. 동일 failure mode가 **별개 세션**에서 관찰돼야 1 count.

**예시**: 31/32/33 = same mode (Lead risk-aversion) → 단일 `lead-action-default.md` merge. 34차+ 후보 시 본 decision tree 먼저 실행.
