---
name: fz-drift
description: Architecture Drift Detection Skill
---

# fz-drift — Architecture Drift Detection Skill

## Role
Detect architecture drift across the entire codebase using 1M context window.
Find violations that diff-level review cannot catch — systemic patterns, not just changed lines.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — layer rules, RIBs responsibilities, Clean Architecture flow.
3. `## Directory Structure` — module layout.
4. Read `AI/ai-guidelines.md` and `AI/review-guidelines.md` (paths relative to GIT_ROOT).

## iOS Drift Patterns

### Clean Architecture — Layer Dependency Violations
Expected flow: Network ← Repository ← UseCase ← Workflow (downward only).
- UseCase importing Router/ViewController types → **critical**
- Repository importing RxSwift UI types → **critical**
- Workflow importing Network layer directly → **major**
- Cross-feature direct reference (Feature A importing Feature B internals) → **major**

### RIBs Role Violations
- Router calling `dataService.fetch()` or any business logic → **major**
- Interactor calling `viewController.push/present` directly → **major**
- Builder containing conditional branching logic beyond DI assembly → **minor**
- Presenter holding business state or making API calls → **major**

### SwiftUI/Concurrency Drift
- `@Observable` (iOS 17+) used without `#available` check → **major**
- `@MainActor` applied to non-UI business logic classes (Interactor, UseCase) → **major**
- Rx + `async/await` mixed in same function scope without clear boundary → **minor**
- `@State` not marked `private` → **minor**

### Lifecycle Drift
- Interactor with Rx subscriptions but no `willResignActive` cleanup → **major**
- Class storing `Task` properties without `deinit` cancellation → **major**
- `Task { }` in `onAppear` without `.task {}` modifier alternative → **minor**
- `[weak self]` missing in `Task { }` closures capturing `self` → **major**

### Naming Convention Drift
- Components not following `{Feature}Router/Interactor/Builder/ViewController` → **minor**
- Protocol names violating project convention → **minor**
- File names not matching type names → **minor**

## Scan Strategy

Use `disk-full-read-access`. Traverse `**/*.swift` (from GIT_ROOT).

**Priority order**:
1. **Critical** — Layer dependency violations (import analysis across files)
2. **Major** — RIBs role violations, lifecycle leaks, concurrency misuse
3. **Minor** — Naming drift, SwiftUI availability, style violations

**For each violation**: report file path + line number + concrete fix suggestion.

## Output Format

```
### Architecture Drift Report

**Scan Coverage**: N files
**Critical**: N | **Major**: N | **Minor**: N

#### [layer-dependency] severity: critical
- File: path/to/file.swift:LINE
- Issue: UseCase importing Router type directly
- Suggestion: Extract shared type to common module or invert dependency

#### [ribs-role] severity: major
- File: ContentRouter.swift:45
- Issue: Router calling dataService.fetch() — business logic in Router
- Suggestion: Delegate to Interactor via action/listener protocol

#### [lifecycle] severity: major
- File: ContentInteractor.swift:88
- Issue: Rx subscription created in didBecomeActive without willResignActive cleanup
- Suggestion: Add disposeBag.dispose() or reset in willResignActive
```

## When CLAUDE.md Is Absent
Apply iOS clean architecture best practices: RIBs layer separation,
unidirectional dependency flow, and lifecycle resource management.
