# iOS / Swift domain pack — fz-challenger

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A challenge that rests only on this pack: `ruleSource: plugin-default`, severity at most `suggestion`.** A project rule (`ruleSource: project`) always wins — when it says otherwise, follow it and drop the pack item.
> A framework subsection applies only when the repository actually uses that framework (an import or a dependency manifest entry).

Challenge these stack-specific over-engineering patterns:

## RIBs over-engineering (only with `import RIBs`)
- A Builder with abstract factory layers it does not need (one feature = one concrete Builder is enough)
- A Router that manipulates views directly (the Router routes, the ViewController renders)
- An Interactor that owns UI state (`@Published` in an Interactor = RIBs role violation)
- Too many Listener methods (each method = one cross-RIB concern)
- A single-screen Builder with protocol + default implementation + factory — a plain `Builder` class suffices

## SwiftUI over-engineering
- `@Observable` on types that need no reactivity (a plain struct or enum may do)
- Nested `ObservableObject` chains (flatten state ownership)
- A `ViewModifier` for one-off styling that reads clearer inline

## Concurrency over-engineering
- An actor for a class that never crosses an isolation boundary (`class` + `@MainActor` suffices)
- A TaskGroup for sequential work that is simpler as sequential async calls
- A custom AsyncSequence where `AsyncStream` covers the use case

## Swift 5.10+ `sending` parameter semantics (compiler-verifiable)
- `group.addTask` signature: `sending @escaping @Sendable () async -> ChildTaskResult`
- A `@MainActor`-isolated closure as a `sending` parameter = "passing closure as a 'sending' parameter" warning
- **Correct pattern**: a non-isolated closure + `await MainActor.run { /* UI work */ }`
- **Wrong suggestion**: adding `@MainActor` to the addTask closure (causes the warning, does not remove it)
- Claims about `sending`, `nonisolated` or actor isolation MUST carry `compiler_verifiable: true` — do not assert a warning without compiling
