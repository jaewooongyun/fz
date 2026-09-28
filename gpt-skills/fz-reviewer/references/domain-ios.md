# iOS / Swift domain pack — fz-reviewer

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A finding that rests only on this pack: `ruleSource: plugin-default`, severity at most `suggestion`.** A project rule (`ruleSource: project`) always wins — when it says otherwise, follow it and drop the pack item.
> The cap applies to idiom and convention items that exist only because of this pack. A concrete defect you can show in the code (a leak, a race, a crash) is reported under the general criteria with its own evidence and severity — the pack only helps you find it.
> A framework subsection applies only when the repository actually uses that framework (an import or a dependency manifest entry).
> Availability: read the project's minimum deployment target from its settings or guidelines. An API newer than that target needs an `#available` guard.

## SwiftUI
- `@State` is `private`; `@StateObject` when the view **owns** the object, `@ObservedObject` when it is injected
- Below iOS 17: `ObservableObject` + `@StateObject` · iOS 17+: `@Observable` + `@State` (`#available` when the target is lower)
- `body` is pure: no side effects, no network calls, no direct state mutation
- `ForEach` needs stable identity (`Identifiable` or an explicit `id:`)
- `onChange`: `{ newValue in }` before iOS 17 · `{ old, new in }` from iOS 17 (`#available` when the target is lower)

## RIBs (only with `import RIBs`)
- `didBecomeActive`: start Rx subscriptions, load initial data
- `willResignActive`: the `disposeBag` is disposed or reset; timers stopped
- `deinit`: no active `Task` holding a strong `self`
- Router `attach`/`detach` are balanced — every attach has a matching detach path
- An Interactor does not call `viewController.push/present` directly (Presenter bridge only)
- Context scope: read the whole RIB set (Router · Interactor · Builder · ViewController · Presenter) and the parent Router's attach/detach pair

## Swift Concurrency
- `@MainActor`: only on UI-update code; avoid blanket `@MainActor` on a whole class
- A `Task { }` that captures `self` uses `[weak self]` when it can outlive the owner
- Two or more independent async calls → `async let` rather than sequential `await`
- `withCheckedContinuation`: justified only when no native async API exists
- A `Task` stored in a property is cancelled in `deinit`
- **`group.addTask` + `@MainActor` (Swift 5.10+)**: the signature is `sending @escaping @Sendable`. A `@MainActor`-isolated closure passed as a `sending` parameter raises "passing closure as a 'sending' parameter".
  ✅ `group.addTask { [weak self] in ... await MainActor.run { /* UI */ } }`
  ❌ `group.addTask { @MainActor [weak self] in }` — causes the warning instead of removing it

## Memory
- Closures that capture `self` in long-lived subscriptions or stored handlers use `[weak self]`; how the weak reference is then unwrapped is the project's rule, not this pack's

## Code Transformation Equivalence (pattern migrations in the diff)
When the diff converts PromiseKit→async/await, callback→async or RxSwift→Combine:
- PromiseKit `.done { }` runs on the main queue → the async version needs `Task { @MainActor in }`; a plain `Task` breaks the guarantee
- `.catch { switch case }` → `catch { if case }`; do not compare enum associated values with `==`
- `.ensure { }` / `.finally { }` → sequential code after `try?`; **`await` inside `defer` does not compile**
- `.cauterize()` → `try?` (fire-and-forget)
- After > 2× Before lines → a missing abstraction (protocol extension, convenience method)
- A repository object is created once as a stored property, not per call

## Zero-Exception Thread
- Original on the main queue → the After code has `@MainActor`. "Thread-safe API" is not an exception by default
- An exception claim needs a `[verified: <tool>]` tag
- `BehaviorRelay.accept()`'s mutation lock ≠ the subscriber's execution thread — thread-safe ≠ thread-equivalent

## Entry points (modularization reviews)
- Application lifecycle entry points: `AppDelegate` · `SceneDelegate` · `UIWindow` extensions
- Global hooks: `motionBegan` · `userActivity` handlers
