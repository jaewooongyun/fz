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

## SwiftUI Repair Patterns (iOS 16 minimum target)

Apply these patterns when fixing SwiftUI-related bugs. Each pattern names the **correct** repair, not the symptom-suppression repair.

- **`@State` missing `private`**: add `private` keyword. Do NOT change to `@StateObject` (different ownership semantics).
- **`@Observable` (iOS 17+) without `#available`**: wrap call site in `if #available(iOS 17, *)` + provide iOS 16 fallback (`ObservableObject + @StateObject`). Do NOT downgrade to `ObservableObject` if iOS 17+ is the actual minimum target.
- **`onChange` signature mismatch**: match minimum target — iOS 16 = `{ newValue in }`, iOS 17+ = `{ old, new in }`. Do NOT introduce iOS 17+ syntax without `#available`.
- **Passive View violation**: View body calling repository/service directly. Move call to Interactor/UseCase. Do NOT just wrap in `Task { ... }` inside View body — that masks the architectural violation.

## Concurrency Repair Patterns

- **`@MainActor` on whole class for non-UI logic**: narrow scope to UI-update method only (per-method `@MainActor`). Do NOT remove all `@MainActor` — UI paths still need isolation.
- **2+ sequential `await` for independent calls**: convert to `async let` for parallelism. Do NOT add manual TaskGroup unless cancellation is needed.
- **`group.addTask` + `@MainActor` closure (Swift 5.10+)**: addTask signature is `sending @escaping @Sendable`. `@MainActor`-isolated closure as `sending` parameter triggers warning. **Correct**: non-isolated closure + `await MainActor.run { /* UI */ }` inside. **Wrong**: `group.addTask { @MainActor [weak self] in }` (causes warning, not removes it).
- **`withCheckedContinuation` when native async exists**: replace with native async API. Do NOT keep continuation as fallback when context7 confirms a native async overload.

## Anti-Repair Patterns (DO NOT do these as fixes)

These look like fixes but introduce new violations or suppress symptoms without resolving root cause.

- ❌ Adding `@MainActor` to addTask closure to silence "sending parameter" warning — fix the closure isolation pattern instead (see Concurrency Repair §3).
- ❌ Changing Interactor `@Published var` to `@MainActor var` to silence isolation warnings — annotate the class or method properly with `@MainActor`.
- ❌ Removing `private` from `@State` to silence access warnings — restructure binding flow (use `@Binding` or `@ObservedObject`).
- ❌ Wrapping main-thread-required code in plain `Task { }` (no `@MainActor`) — original main-queue guarantees broken. Use `Task { @MainActor in }`.
- ❌ Adding `try?` to swallow errors that the original code propagated — preserve original error semantics (catch + handle, not silence).

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
