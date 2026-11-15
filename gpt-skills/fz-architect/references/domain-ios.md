# iOS / Swift domain pack — fz-architect

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A finding that rests only on this pack: `ruleSource: plugin-default`, severity at most `suggestion`.** A project rule (`ruleSource: project`) always wins — when it says otherwise, follow it and drop the pack item.
> A framework subsection applies only when the repository actually uses that framework (an import or a dependency manifest entry).
> Availability: read the project's minimum deployment target from its settings or guidelines. An API newer than that target needs an `#available` guard.

## Architecture focus
- **RIBs** (only with `import RIBs`): Router = navigation, Interactor = business logic, Builder = DI — check that the plan keeps each role
- **SwiftUI state**: below iOS 17 `ObservableObject` + `@StateObject` · iOS 17+ `@Observable` + `@State` (`#available` when the target is lower)
- **Concurrency**: keep `@MainActor` scope minimal. When the plan switches threads, confirm the original thread characteristics first
- **Module boundaries**: public types belong to the module's responsibility; domain-specific fields do not leak into infrastructure modules

## Code transformation (Swift specifics)
- PromiseKit `.done` runs on the main queue; RxSwift `observe(on:)` sets the observer's scheduler — the After code keeps the same thread (`@MainActor` for main-queue work)
- `defer { await … }` does not compile
- enum catch: no `==` on associated values — use `if case`
