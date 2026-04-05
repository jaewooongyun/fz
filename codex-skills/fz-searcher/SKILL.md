---
name: fz-searcher
description: Codebase Exploration Skill
---

# fz-searcher — Codebase Exploration Skill

## Role
Explore codebase structure, trace dependencies, and analyze impact scope.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — identify architecture patterns and module structure.
3. `## Guidelines` — find and read guideline files (paths relative to GIT_ROOT):
   - `AI/ai-guidelines.md` — coding rules and project conventions.
   - `AI/review-guidelines.md` — review standards and criteria.
4. `## Code Conventions` — identify file/folder naming and structure rules.

## Search Capabilities

### Codebase Structure Exploration
- Map directory structure and module boundaries.
- Identify entry points, main components, and their responsibilities.
- Trace the flow from feature entry to data layer.

### Symbol Relationship Tracing
- Find all usages of a type, function, or property.
- Trace protocol conformances and inheritance chains.
- Map dependency injection paths and object creation sites.
- Identify circular dependencies.

### Similar Pattern Search
- Find existing implementations of similar functionality.
- Locate patterns that match a described behavior.
- Identify reusable components for a given requirement.
- Find test examples for similar features.

### Impact Scope Analysis
- Given a change target, list all directly affected files.
- Identify indirect effects through dependency chains.
- Map which tests cover the affected code paths.
- Flag public API surface changes that affect consumers.

## Linkage
- When invoked via `fz-codex`, results feed into the `search` subcommand for structured codebase exploration.

## Output Format
```
### Search: "query description"
- Found: N results
- Key Findings:
  1. file:line — description
  2. file:line — description
- Dependency Chain: A → B → C (if tracing)
- Impact Scope: list of affected modules/files
```

## Few-shot Example

```
BAD:
### Search: "PlayerInteractor 찾기"
- Found: 3 results
- Key Findings: 파일들이 있음

GOOD:
### Search: "PlayerInteractor 의존성 추적"
- Found: 4 results
- Key Findings:
  1. app-iOS/Player/PlayerInteractor.swift:1 — 심볼 정의, VideoRepository 의존
  2. app-iOS/Player/PlayerBuilder.swift:28 — 생성 및 VideoRepository DI 주입
  3. app-iOS/Player/PlayerRouter.swift:15 — listener로 참조
  4. app-iOS/PlayerTests/PlayerInteractorTests.swift:10 — 테스트 대상
- Dependency Chain: PlayerBuilder → PlayerInteractor → VideoRepository → VideoNetworkService
- Impact Scope: PlayerInteractor 수정 시 PlayerBuilder, PlayerRouter, PlayerInteractorTests 영향
```

## When CLAUDE.md Is Absent
Apply general code exploration techniques: directory traversal, symbol search,
reference tracing, and dependency analysis using available tooling.
