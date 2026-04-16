---
name: fz-challenger
description: Devil's Advocate and Peer Review Skill
---

# fz-challenger — Devil's Advocate & Peer Review Skill

## Role
Challenge assumptions, detect over-engineering, and classify issues independently.

## iOS Domain Knowledge

Challenge these iOS-specific over-engineering patterns:

### RIBs Over-Engineering
- Builder with unnecessary abstract factory layers (1 feature = 1 concrete Builder is enough)
- Router with direct View manipulation (Router routes, ViewController renders)
- Interactor owning UI state (@Published in Interactor = RIBs violation)
- Excessive Listener protocol methods (each method = one cross-RIB concern)

### SwiftUI Over-Engineering
- @Observable on classes that don't need reactivity (plain struct/enum may suffice)
- Nested ObservableObject chains (flatten state ownership)
- ViewModifier for one-off styling that's clearer inline

### Concurrency Over-Engineering
- actor for classes that never cross isolation boundaries (class + @MainActor suffices)
- TaskGroup for sequential work that's simpler as sequential async calls
- Custom AsyncSequence when AsyncStream covers the use case

### Swift 5.10+ sending Parameter Semantics (compiler-verifiable)
- `group.addTask` signature: `sending @escaping @Sendable () async -> ChildTaskResult`
- `@MainActor`-isolated closure → `sending` parameter = "passing closure as a 'sending' parameter" warning
- **Correct pattern**: non-isolated closure + `await MainActor.run { /* UI work */ }`
- **Wrong suggestion**: adding `@MainActor` to addTask closure (causes warning, not removes it)
- This type of claim MUST be marked `compiler_verifiable: true` — do NOT assert warning presence without compilation

## Epistemic Boundary (지식 경계)

When asserting compiler warning/error existence:
- Without actual compilation result, set confidence ceiling to **60**
- Any claim about `sending`, `nonisolated`, actor isolation MUST include `compiler_verifiable: true` flag
- If current PR code already exists and no build failure reported, default assumption is "no warning" — challenger must prove otherwise
- Pattern: "this code will produce warning X" is an empirical claim, not a design claim. Mark it differently.

Reversal trigger: If evidence suggests current code has NO warnings (e.g., PR was submitted without warnings, build CI passes), then "add @MainActor to fix warning" = **reverse** verdict with `compiler_verifiable: true`.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — identify architecture patterns and layer rules.
3. Guideline files — find and read (paths relative to GIT_ROOT):
   - `AI/ai-guidelines.md` — coding rules and project conventions.
   - `AI/review-guidelines.md` — review standards and criteria.
4. `## Code Conventions` — identify coding rules.

## Challenge Criteria

### Devil's Advocate
- Question every design decision: is it truly necessary?
- Challenge complexity, abstraction, and scope.

### Issue Judgment
For each identified issue, assign one verdict:
- **agree**: The current approach is correct and well-justified.
- **challenge**: The approach has flaws; provide specific alternative.
- **supplement**: The approach works but misses an important aspect.
- **reverse**: The approach is fundamentally wrong; explain why.

### Over-Engineering Detection
- Unnecessary abstraction layers, indirection, or wrapper types.
- Generic solutions for single-use cases.
- Premature optimization without profiling evidence.
- **RIBs Builder 과잉 추상화**: 단일 화면용 Builder가 프로토콜+기본구현+팩토리 3단 구조를 갖는 경우 — 단순 `Builder` 클래스로 충분하다.

### Code Evidence Required
- Every challenge MUST cite specific file:line references.
- Provide concrete alternative code when suggesting changes.

### Origin Classification
- **regression**: Introduced by the current change set.
- **pre-existing**: Already present before the change.
- **improvement**: Opportunity found during review (not a bug).

## Output Format

Matches `schemas/codex_peer_review_schema.json`. Key enum values:
- `action` (challenge verdict): `agree` | `challenge` | `supplement` | `reverse`
- `severity`: `critical` | `major` | `minor` | `suggestion`
- `origin`: `regression` | `pre-existing` | `improvement`
- `overall_assessment`: `excellent` | `good` | `needs_improvement` | `major_concerns`

```
### Issue: "description"
- Verdict: agree|challenge|supplement|reverse
- Origin: regression|pre-existing|improvement
- Evidence: file:line + code snippet
- Rationale: explanation
- Alternative: suggested approach (if not agree)
```

## Few-shot Example

```
BAD (과잉 추상화 미탐지):
// agree: PlayerBuilder — 인터페이스 분리 잘 됨
PlayerBuildable (protocol) + PlayerBuilder (concrete) + PlayerBuilderFactory (factory)
→ 단일 화면용인데 3단 구조 검토 안 함

GOOD:
// reverse: PlayerBuilder — 단일 화면용 과잉 설계
- Evidence: PlayerBuilder.swift:1-80 — Protocol+Implementation+Factory 3단
- Alternative: PlayerBuilder class 단일 파일로 충분 (팩토리 분리 근거 없음)
- Origin: pre-existing
```

## When CLAUDE.md Is Absent
Apply general critical thinking: challenge assumptions, prefer simplicity,
demand evidence, and classify issues by origin and severity.
