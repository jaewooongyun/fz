# iOS / Swift domain pack — fz-fixer

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A repair choice that rests only on this pack is marked `plugin-default`; as a review finding it would be at most `suggestion`.** A project rule (`ruleSource: project`) always wins — when it says otherwise, follow it.
> A framework subsection applies only when the repository actually uses that framework (an import or a dependency manifest entry).
> Availability: read the project's minimum deployment target from its settings or guidelines. An API newer than that target needs an `#available` guard.
> Team-shared areas in Swift projects typically include `.swiftlint.yml`, `Package.swift`, `*.xcconfig` and the Xcode project file — do not change them without the user's explicit agreement.

Each pattern names the **correct** repair, not the symptom-suppressing one.

## SwiftUI repair patterns
- **`@State` missing `private`**: add `private`. Do NOT change it to `@StateObject` (different ownership semantics).
- **`@Observable` (iOS 17+) without `#available`**: when the minimum target is lower, wrap the call site in `if #available(iOS 17, *)` and provide a fallback (`ObservableObject` + `@StateObject`). Do NOT downgrade to `ObservableObject` if iOS 17+ is the actual minimum target.
- **`onChange` signature mismatch**: match the minimum target — `{ newValue in }` before iOS 17, `{ old, new in }` from iOS 17. Do NOT introduce iOS 17+ syntax without `#available`.
- **Passive View violation**: a view body calling a repository/service directly. Move the call to the component that owns data loading. Do NOT just wrap it in `Task { ... }` inside the view body — that masks the violation.

## Concurrency repair patterns
- **`@MainActor` on a whole class for non-UI logic**: narrow it to the UI-update methods. Do NOT remove all `@MainActor` — UI paths still need isolation.
- **Sequential `await` for independent calls**: convert to `async let`. Do NOT add a manual TaskGroup unless cancellation is needed.
- **`group.addTask` + `@MainActor` closure (Swift 5.10+)**: the signature is `sending @escaping @Sendable`, so a `@MainActor`-isolated closure triggers a warning. **Correct**: a non-isolated closure + `await MainActor.run { /* UI */ }` inside. **Wrong**: `group.addTask { @MainActor [weak self] in }`.
- **`withCheckedContinuation` when a native async API exists**: replace it with the native API. Do NOT keep the continuation as a fallback once a native async overload is confirmed.

## Anti-repair patterns (Swift specifics)
- ❌ Adding `@MainActor` to an addTask closure to silence the "sending parameter" warning — fix the closure isolation instead
- ❌ Changing an `@Published var` to `@MainActor var` to silence isolation warnings — annotate the type or method properly
- ❌ Removing `private` from `@State` to silence access warnings — restructure the binding flow (`@Binding` or `@ObservedObject`)
- ❌ Wrapping main-thread-required code in a plain `Task { }` — the original main-queue guarantee breaks; use `Task { @MainActor in }`
- ❌ Adding `try?` to swallow errors the original code propagated
