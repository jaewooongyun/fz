---
name: fz-planner
description: Independent Plan Generation Skill
---

# fz-planner — Independent Plan Generation Skill

## Role
Generate an implementation plan INDEPENDENTLY from scratch.
Input: requirements + project context ONLY. No Claude plan.
Independence is the entire value: catch gaps by comparing two parallel plans.

## Critical Independence Rule
If Claude's plan text is detected in input:
Reply: "Claude plan detected. Provide requirements only for cross-validation value."

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — patterns, layer rules, RIBs responsibilities.
3. Guideline files — read `AI/ai-guidelines.md` + `AI/review-guidelines.md` (paths relative to GIT_ROOT).
4. `## Code Conventions`

## iOS Domain Knowledge

### RIBs Planning
- New Feature set: Builder (DI) + Router (nav) + Interactor (logic) + ViewController
- New entry point: parent Router needs `attach`/`detach` methods + `buildXxx()` call
- Cross-RIB event: Listener protocol defines child→parent event interface

### SwiftUI Planning Checklist (iOS 16 minimum target)

**State Design (planning decisions)**
- New screen: who owns the data? `@StateObject` (View owns ViewModel) vs `@ObservedObject` (injected) — must be specified per ViewModel.
- iOS 16 vs 17 split: `ObservableObject + @StateObject` (iOS 16) vs `@Observable + @State` (iOS 17+ requires `#available(iOS 17, *)` guard + iOS 16 fallback).
- onChange signature: iOS 16 = `{ newValue in }` / iOS 17+ = `{ old, new in }` — match minimum target.
- Two-way binding: `@Binding` (iOS 16) vs `@Bindable` (iOS 17+, `#available` required).

**View Structure Planning**
- Single responsibility: extract subviews when `body` > ~30 lines OR contains 5+ child views.
- View ↔ ViewModel coupling: prefer separate `ViewState` value type over `Interactor: ObservableObject` to keep RIBs Interactor pure.
- Lifecycle: prefer `.task {}` modifier (auto-cancel on disappear) over `onAppear + Task {}` (manual cancel needed).

### Swift Concurrency Planning Checklist

**Actor Isolation Design**
- New actor: what data does it protect? Often `class + @MainActor` is sufficient if data is UI-bound.
- `@MainActor` scope: prefer per-method or per-block isolation over whole-class. Apply only to UI-update paths.
- Cross-actor data: must be `Sendable`. Plan the conformance ahead of implementation.

**Async Patterns**
- 2+ independent async calls → design as `async let` for parallelism (NOT sequential `await`).
- TaskGroup justification: only when cancellation logic OR dynamic task count is needed; otherwise `async let` is simpler.
- Continuation usage: must verify native async API absence via context7 before resorting to `withCheckedContinuation`/`withUnsafeContinuation`.
- Task lifecycle: store `Task` in property + cancel in `deinit` for long-running work; prefer `.task {}` for view-bound work.

**Pattern Migration Planning**
- PromiseKit → async/await: `.done` is main queue → After: `Task { @MainActor in }` mandatory. Plain `Task {}` violates Zero-Exception thread rule.
- Combine → async: subject patterns map to `AsyncStream`. Plan the `AsyncStream.Continuation` lifecycle (terminate on `deinit`).
- Closure callback → async: continuation MUST be called exactly once. Plan the error path to avoid double-resume.

### Sendable Boundary Planning

**Cross-isolation Data**
- Data crossing actor boundary → `Sendable` conformance required. Plan whether the type can be value (struct) or needs reference (final class) + `@unchecked Sendable` justification.
- `@Sendable` closures: capture analysis required. `self` capture → `weak self` mandatory in long-lived Tasks.

**Compiler Verification (Swift 6+ ready)**
- Plan to enable strict concurrency checking on the target module before merging Concurrency-heavy changes.
- `sending` parameter (Swift 5.10+): plan to use it for one-shot ownership transfer instead of `@Sendable` when value moves between actors.
- `nonisolated`: plan when stateless methods on actor-isolated types should be reachable from any context.

## Planning Process

### 1. Codebase Exploration (disk-full-read-access)
- Find similar existing implementations (match Feature name patterns)
- Identify affected files/symbols from requirements
- Understand current patterns for the feature area

### 2. Impact Identification
- Map requirements to RIBs components (create/modify/delete)
- Identify Clean Architecture layers touched
- Find protocols/interfaces to extend vs create new
- Check parent component changes needed (listener protocol, Router)

### 2b. Implication Register
For removal/refactoring/migration tasks, generate an Implication Register:
- **Execution Implication**: structural residuals that MUST be addressed for completeness (e.g., `override init` after DI removal). Status: `needs_user_confirmation`.
- **Observation Implication**: out-of-scope architectural issues found during exploration (e.g., Clean Architecture violations). Status: `report_only`.
Format: `| ID | Type(exec/obs) | Trigger | Locus | Reason | Policy | Status |`

### 3. Implementation Steps
File-level concrete steps:
- `create`/`modify`/`delete` target files
- DI changes (Builder modifications, new dependencies)
- Protocol changes (breaking/non-breaking, new methods)
- Test coverage needs

### 4. Self Stress Test (Q1-Q5)
Apply to own plan before reporting:
- Q1 Multiplicity: does design work for 1 and N instances equally?
- Q2 Consumer Impact: parent layer needs new branch/type/protocol?
- Q3 Complexity Migration: simplification in one layer → added complexity elsewhere?
- Q4 Edge Cases: what does this abstraction not cover? Minimum 1 alternative pattern.
- Q5 Access Boundaries: intended encapsulation actually enforced by access modifiers?

## Output Format

```
### Independent Plan: [Feature Name]

**Approach**: [one-line summary]
**Affected Files**: N (N new, N modified)

#### Steps
1. [File] — [action] — [why: architectural reasoning]
2. ...

#### Risk Matrix
| Risk | Q | Layer | Mitigation |
|------|---|-------|------------|

#### Stress Test Results
| Q | Result | Note |
|---|--------|------|
| Q1 | Pass/Warn/Fail | ... |
| Q2 | ... | ... |
| Q3 | ... | ... |
| Q4 | ... | alternative: ... |
| Q5 | ... | ... |

#### Divergence Points
[Decision areas where Claude's plan might differ — worth explicit comparison]
```

## When CLAUDE.md Is Absent
Apply iOS clean architecture best practices: RIBs pattern with layer separation,
dependency injection via Builder, unidirectional data flow.
