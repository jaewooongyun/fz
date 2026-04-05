---
name: fz-guardian
description: Post-Change Verification Skill
---

# fz-guardian — Post-Change Verification Skill

## Role
Verify that feedback has been fully applied and no regressions are introduced.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — identify architecture patterns and layer rules.
3. `## Guidelines` — find and read guideline files (paths relative to GIT_ROOT):
   - `AI/ai-guidelines.md` — coding rules and project conventions.
   - `AI/review-guidelines.md` — review standards and criteria.
4. `## Code Conventions` — identify coding rules.

## Verification Criteria

### Feedback Completeness
- Every review comment or requested change is addressed.
- No feedback item is partially applied or skipped.
- Mark each feedback item: resolved | partially_resolved | unresolved | regressed.

### Original Issue Resolution
- The root cause identified in the original issue is fixed.
- The fix directly addresses the problem (not a workaround).
- Acceptance criteria from the original request are met.

### No New Issues Introduced
- No new compiler errors or warnings.
- No new lint or static analysis violations.
- No unrelated code changes bundled in.
- No TODO/FIXME added without tracking.

### Memory and Concurrency Safety
- Changes do not introduce retain cycles.
- `weak var`는 `?.` optional chaining으로 사용한다 (CLAUDE.md Code Conventions 참조).
- Shared state access remains thread-safe.
- `@MainActor` isolation은 UI 업데이트 경로에서 누락되지 않는지 확인한다.
- actor-isolated 프로퍼티에 non-isolated 컨텍스트에서 접근하는 데이터 레이스 위험을 점검한다.
- Resource cleanup paths are intact.

### Implication Gate Compliance
- Verify no inferred changes were executed without user confirmation.
- For removal/refactoring: check that execution implications (structural residuals) were either approved and addressed, or dismissed with reason.
- For observation implications: verify they were reported but NOT auto-fixed.

### Regression Risk
- Identify code paths affected by the change.
- Check that existing behavior is preserved where intended.
- Flag any behavioral changes that were not explicitly requested.

## Output Format

Matches `codex_verification_schema.json`. Key enum values:
- `resolution_status`: `resolved` | `partially_resolved` | `unresolved` | `regressed`
- `verdict`: `pass` | `needs_work` | `fail`
- Feedback reflection rate: `(resolved*1.0 + partially_resolved*0.5) / total_issues`

```
### Feedback Item: "description"
- Status: resolved|partially_resolved|unresolved|regressed
- Evidence: file:line or explanation
- Risk: none|low|medium|high
```

## Few-shot Example

```
BAD (검증 누락):
### Feedback Item: "weak self 추가 요청"
- Status: resolved
- Evidence: "코드 수정함"     ← 파일:라인 없음, 실제 확인 불가
- Risk: none

GOOD:
### Feedback Item: "weak self 추가 요청"
- Status: resolved
- Evidence: ProfileInteractor.swift:87 — [weak self] 추가, self?.presenter.update(data) optional chaining 확인
- Risk: none
```

## When CLAUDE.md Is Absent
Apply general verification best practices: confirm each change request is met,
check for side effects, and validate no regressions in affected code paths.
