# iOS / Swift domain pack — fz-planner

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A planning decision that rests only on this pack is marked `plugin-default` in its `why`; as a review finding it would be at most `suggestion`.** A project rule (`ruleSource: project`) always wins — when it says otherwise, follow it.
> A framework subsection applies only when the repository actually uses that framework (an import or a dependency manifest entry).
> Availability: read the project's minimum deployment target from its settings or guidelines. An API newer than that target needs an `#available` guard and a fallback path.

## RIBs Planning (only with `import RIBs`)
- A new feature set: Builder (DI) + Router (navigation) + Interactor (logic) + ViewController
- A new entry point: the parent Router needs `attach`/`detach` methods and a `build…()` call
- A cross-RIB event: a Listener protocol defines the child→parent event interface

## SwiftUI Planning Checklist

**State design (planning decisions)**
- New screen: who owns the data? `@StateObject` (the view owns the model object) vs `@ObservedObject` (injected) — specify per model object
- Below iOS 17: `ObservableObject` + `@StateObject` · iOS 17+: `@Observable` + `@State` (`#available(iOS 17, *)` guard + fallback when the target is lower)
- `onChange`: `{ newValue in }` before iOS 17 · `{ old, new in }` from iOS 17 — match the minimum target
- Two-way binding: `@Binding` vs `@Bindable` (iOS 17+, `#available` when the target is lower)

**View structure planning**
- Single responsibility: extract subviews when `body` exceeds ~30 lines or holds 5+ child views
- View ↔ model coupling: with RIBs, prefer a separate `ViewState` value type over making the Interactor an `ObservableObject`
- Lifecycle: prefer the `.task {}` modifier (auto-cancels on disappear) over `onAppear` + `Task {}` (manual cancel)

## Swift Concurrency Planning Checklist

**Actor isolation design**
- A new actor: what data does it protect? `class` + `@MainActor` often suffices for UI-bound data
- `@MainActor` scope: per method or per block rather than the whole class; only on UI-update paths
- Cross-actor data must be `Sendable` — plan the conformance before implementation

**Async patterns**
- Two or more independent async calls → `async let` for parallelism (not sequential `await`)
- TaskGroup only when cancellation logic or a dynamic task count is needed; otherwise `async let`
- Continuation: verify that no native async API exists before `withCheckedContinuation`/`withUnsafeContinuation`
- Task lifecycle: store a long-running `Task` in a property and cancel it in `deinit`; prefer `.task {}` for view-bound work

**Pattern migration planning**
- PromiseKit → async/await: `.done` runs on the main queue → `Task { @MainActor in }` is mandatory; a plain `Task {}` breaks the thread guarantee
- Combine → async: subject patterns map to `AsyncStream`; plan the `AsyncStream.Continuation` lifecycle (finish in `deinit`)
- Closure callback → async: the continuation resumes exactly once — plan the error path so it cannot resume twice

## Sendable Boundary Planning
- Data crossing an actor boundary needs `Sendable`: plan value types (struct) or a `final class` with an `@unchecked Sendable` justification
- `@Sendable` closures: analyse captures; a long-lived Task captures `self` weakly
- Plan to enable strict concurrency checking on the target module before merging concurrency-heavy changes
- `sending` parameters (Swift 5.10+) for one-shot ownership transfer instead of `@Sendable` when a value moves between actors
- `nonisolated` for stateless methods on actor-isolated types that must be reachable from any context
