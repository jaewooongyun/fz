# iOS / Swift domain pack — fz-guardian

> Read only when the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`).
> **A finding that rests only on this pack: `ruleSource: plugin-default`, severity at most `suggestion`.** A project rule (`ruleSource: project`) always wins — when it says otherwise, follow it and drop the pack item.
> The cap applies to idiom and convention items that exist only because of this pack. A concrete regression you can show in the code is reported under the general criteria with its own evidence and severity.

## Concurrency
- `@MainActor` isolation is not lost on UI-update paths
- No actor-isolated property is accessed from a non-isolated context (data race risk)

## Transformation equivalence (Swift specifics)
- PromiseKit `.done` runs on the main queue → the After code has `@MainActor` (Zero-Exception Thread)
- `.catch { switch case }` → `catch { if case }`; no `==` on enum associated values
