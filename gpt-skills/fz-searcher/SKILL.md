---
name: fz-searcher
description: Codebase exploration — structure, symbol relationships, similar patterns and impact scope, read through the target repository's own module rules
---

# fz-searcher — Codebase Exploration Skill

## Role
Explore codebase structure, trace dependencies, and analyze impact scope.

> **Authority**: Anthropic "How we built our multi-agent research system" (2025-06) [verified: official A1] — "Token usage explains 80% of performance variance". 본 스킬은 ReAct (arXiv 2210.03629) reasoning-action-observation 루프로 효율적 검색 + Context Rot (Chroma Research 18 frontier models) 회피 (focused 300 tokens > unfocused 113K tokens) 원칙을 적용한다.

## Project Rules (runtime)

Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
5. **Citing** — module boundaries and naming patterns you rely on come from the rules; cite them as `{file}:{line} — "<quote>"`.

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
- When invoked via `fz-gpt`, results feed into the `search` subcommand for structured codebase exploration.

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
### Search: "OrderService 찾기"
- Found: 3 results
- Key Findings: 파일들이 있음

GOOD:
### Search: "OrderService 의존성 추적"
- Found: 4 results
- Key Findings:
  1. src/orders/order_service.ts:1 — 심볼 정의, OrderStore 의존
  2. src/orders/order_module.ts:28 — 생성 및 OrderStore 주입
  3. src/orders/order_controller.ts:15 — 콜백 수신자로 참조
  4. tests/orders/order_service.test.ts:10 — 테스트 대상
- Dependency Chain: order_module → OrderService → OrderStore → HttpClient
- Impact Scope: OrderService 수정 시 order_module, order_controller, order_service.test 영향
```

## When Project Guidelines Are Absent

No guideline file exists, or none applies to the searched paths. Then:
- Use general exploration techniques: directory traversal, symbol search, reference tracing and dependency analysis with the available tools.
- Do not assume any framework, architecture pattern, layer order or folder convention; describe the structure the code shows. Report every architecture axis as a Probe Coverage Gap.
