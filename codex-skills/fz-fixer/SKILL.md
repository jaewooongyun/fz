---
name: fz-fixer
description: Bug Fix Skill
---

# fz-fixer — Bug Fix Skill

## Role
Diagnose root causes, apply minimal fixes, and prevent regressions.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — identify architecture patterns and layer rules.
3. Guideline files — find and read (paths relative to GIT_ROOT):
   - `AI/ai-guidelines.md` — coding rules and project conventions.
   - `AI/review-guidelines.md` — review standards and criteria.
4. `## Code Conventions` — identify coding rules and error handling patterns.

## Fix Process

### Root Cause Analysis
- Trace execution flow from symptom to root cause.
- Distinguish root cause from symptoms (fix cause, not symptom).
- Document the causal chain clearly.

### Fix Strategy
- Apply the minimal change that resolves the root cause.
- Prefer fixes at the correct abstraction layer; choose the least invasive.
- Do not refactor unrelated code in the same change.

### Side Effect Minimization
- Check all callers of modified functions.
- Verify behavioral contracts and public API are preserved.
- Validate that default values and edge cases still hold.

### Existing Pattern Compliance
- Match the coding style and error handling pattern of surrounding code.
- Follow the project's dependency injection approach.
- Respect layer boundaries and module ownership.

### Regression Prevention
- Identify related code paths that could break.
- Suggest test cases that cover the fix.
- Verify the fix does not mask other latent bugs.

## Linkage
- When invoked via `fz-codex`, results feed into the `check` subcommand for iterative fix-verify cycles.

## Output Format
```
### Bug: "description"
- Root Cause: explanation with file:line
- Fix: description of change
- Files Modified: list
- Side Effects: none|description
- Suggested Tests: test case descriptions
```

## Few-shot Example

```
BAD (증상 수정):
### Bug: "API 응답 후 UI 업데이트 안 됨"
- Root Cause: "응답 처리 코드 문제"   ← 막연한 설명, 파일:라인 없음
- Fix: DispatchQueue.main.async 추가

GOOD:
### Bug: "API 응답 후 UI 업데이트 안 됨"
- Root Cause: ContentInteractor.swift:94 — fetchContent() 완료 핸들러가 background thread에서 presenter.present() 호출
- Fix: ContentInteractor.swift:94 — await MainActor.run { presenter.present(content) }로 교체
- Side Effects: ContentInteractorTests.swift:51 — 기존 테스트 통과 확인
```

## When CLAUDE.md Is Absent
Apply general debugging best practices: isolate root cause, apply minimal fix,
verify no regressions, and follow existing code patterns in the surrounding context.
