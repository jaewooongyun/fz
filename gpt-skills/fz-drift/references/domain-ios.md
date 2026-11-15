# iOS / Swift domain pack — fz-drift

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A finding that rests only on this pack: `ruleSource: plugin-default`, severity at most `suggestion`.** The severities below order the scan; a pack-only finding is still reported at `suggestion`. When a project rule states the same constraint, report it under that rule with the rule-based severity.
> A framework subsection applies only when the repository actually uses that framework (an import or a dependency manifest entry).
> Scan scope: `**/*.swift` from GIT_ROOT.

## RIBs role violations (only with `import RIBs`)
- Router calling `dataService.fetch()` or any business logic → major
- Interactor calling `viewController.push/present` directly → major
- Builder containing branching logic beyond DI assembly → minor
- Presenter holding business state or making API calls → major

## SwiftUI / Concurrency drift
- `@Observable` (iOS 17+) used without `#available` while the minimum target is lower → major
- `@MainActor` on non-UI business logic types → major
- Rx and `async/await` mixed in one function scope without a clear boundary → minor
- `@State` not marked `private` → minor

## Lifecycle drift
- RIBs Interactor with Rx subscriptions but no `willResignActive` cleanup → major
- Class storing `Task` properties without cancellation in `deinit` → major
- `Task { }` in `onAppear` where the `.task {}` modifier would auto-cancel → minor
- `[weak self]` missing in long-lived `Task { }` closures capturing `self` → major
