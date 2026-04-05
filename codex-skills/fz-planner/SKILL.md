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
3. `## Guidelines` — read `AI/ai-guidelines.md` + `AI/review-guidelines.md` (paths relative to GIT_ROOT).
4. `## Code Conventions`

## iOS Domain Knowledge

### RIBs Planning
- New Feature set: Builder (DI) + Router (nav) + Interactor (logic) + ViewController
- New entry point: parent Router needs `attach`/`detach` methods + `buildXxx()` call
- Cross-RIB event: Listener protocol defines child→parent event interface

### SwiftUI Planning (iOS 16 minimum target)
- State design: `ObservableObject + @StateObject` (iOS 16) vs `@Observable + @State` (iOS 17+, `#available`)
- View decomposition: extract subviews when `body` > ~30 lines
- Lifecycle: prefer `.task {}` modifier over `onAppear + Task {}`

### Concurrency Planning
- 2+ independent async calls → design as `async let` for parallelism
- Actor isolation: minimize `@MainActor` scope to actual UI update code
- Task lifecycle: store `Task` in property + cancel in `deinit`

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
