---
name: fz-drift
description: Architecture drift detection across the whole codebase — systemic violations of the target repository's own rules that diff-level review cannot catch
---

# fz-drift — Architecture Drift Detection Skill

## Role
Detect architecture drift across the entire codebase using 1M context window.
Find violations that diff-level review cannot catch — systemic patterns, not just changed lines.

> **Authority**: DSPy "Programming, not prompting" (Stanford NLP, dspy.ai) [verified: official framework] — Architecture as code rather than ad-hoc prompts. 본 스킬은 대상 저장소 지침에서 런타임에 뽑은 규칙을 ground truth로, MAST 14 failure modes의 "System Design Issues" 카테고리 (arXiv 2503.13657) 기반으로 drift를 분류한다.

## Project Rules (runtime)

Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
5. **Citing** — every drift finding cites the rule it violates as `{file}:{line} — "<quote>"`. A pattern no rule states is not drift — report it as an observation at most.
- **Domain pack (conditional)** — if the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`), also read `references/domain-ios.md`. A finding that rests only on that pack carries `ruleSource: plugin-default` and severity at most `suggestion`; a project rule overrides the pack.

## Drift Patterns (driven by the rule records)

### Layer dependency violations — `dependencyDirection`
- An import that runs against the stated direction → **critical**
- A feature reaching into another feature's internals, when the rules separate features → **major**
- Axis is a gap → do not invent a direction. Report only import cycles between modules (**major**), as observations

### Role violations — `architecturePattern`
- A component doing work the pattern assigns to another role (navigation code loading data, view code holding business logic) → **major**
- Assembly/wiring code containing branching logic beyond construction → **minor**

### Lifecycle drift
- Resources acquired without release on teardown (subscriptions, timers, background tasks) → **major**
- Long-lived tasks stored without cancellation → **major**

### Naming drift — `naming`
- Components that break the stated naming rule → **minor**
- File names that do not match the type they define, when the rules tie them → **minor**

### Placement drift — `placement`
- Types living outside the module or folder the rules assign to them → **minor**

## Scan Strategy

Traverse the source files of the languages the repository actually uses (its manifests and file-extension census decide), from GIT_ROOT.

**Priority order**:
1. **Critical** — Layer dependency violations (import analysis across files)
2. **Major** — Role violations, lifecycle leaks, concurrency misuse
3. **Minor** — Naming and placement drift, style violations

**For each violation**: report file path + line number + the violated rule's citation + a concrete fix suggestion.

## Output Format

```
### Architecture Drift Report

**Scan Coverage**: N files
**Critical**: N | **Major**: N | **Minor**: N
**Rule gaps**: <axes that could not be confirmed>

#### [layer-dependency] severity: critical
- File: src/billing/domain/charge.ts:3
- Rule: {file}:{line} — "<quote>"
- Issue: The domain module imports the HTTP client module, against the stated dependency direction
- Suggestion: Depend on an interface in the domain module and inject the client from the outer layer

#### [role] severity: major
- File: src/checkout/checkout_navigator.ts:45
- Rule: {file}:{line} — "<quote>"
- Issue: Navigation code calls the cart service — data loading belongs to the logic component
- Suggestion: Move the call into the logic component and pass the result in

#### [lifecycle] severity: major
- File: src/sync/sync_job.ts:88
- Issue: Subscription created in start() is never released in stop()
- Suggestion: Dispose the subscription in stop()
```

## When Project Guidelines Are Absent

No guideline file exists, or none applies to the scanned paths. Then:
- Report only drift that needs no project rule: import cycles, lifecycle leaks, and files that contradict the structure the rest of the codebase shows (quote that structure).
- Do not assume any framework, architecture pattern, layer order or folder convention. Report every architecture axis as a Probe Coverage Gap.
- Put `Rule gaps: all` at the top of the report so the reader knows no rule-based drift was checked.
