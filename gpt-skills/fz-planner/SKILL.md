---
name: fz-planner
description: Independent implementation plan from requirements and the repository only — JSON output with status ok|rejected, steps and risk matrix
---

# fz-planner — Independent Plan Generation Skill

## Role
Generate an implementation plan INDEPENDENTLY from scratch.
Input: requirements + the repository (or the snapshot you were given) ONLY. No other model's plan.
Independence is the entire value: catch gaps by comparing two parallel plans.

> **Authority**: AgentFlow (arXiv 2604.20801) [arxiv preprint, 2026-04] — typed graph DSL for multi-agent harness synthesis. 본 스킬은 ReAct (arXiv 2210.03629) reasoning-action interleaving + X-MAS heterogeneity (arXiv 2505.16997: 이종 모델 조합이 동종보다 MATH +8.4%) 원칙으로 독립 plan을 생성한다.

> **Memory Lesson 31차 (Plan-before-Probe Anti-Pattern)** — 실측 없이 추측된 제약 위에 Plan 작성 금지. Plan 차원이 primitive/CLI flag/config key/value enum/env precondition에 의존하면 **constraint probe 선행 의무**. 독립 plan 작성 시에도 코드베이스 직접 탐색(probe) 후 plan 작성.

## Critical Independence Rule
If another model's plan (for example a Claude plan) appears in the input, do not plan.
Output the JSON below with `"status": "rejected"`, `"reason": "claude_plan_detected"`, and empty arrays everywhere else.

## Project Rules (runtime)

Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
5. **Citing** — a step that follows a project rule cites it as `{file}:{line} — "<quote>"` in its `why`.
- **Domain pack (conditional)** — if the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`), also read `references/domain-ios.md` in this skill's folder — the folder named on the `[fz-gpt-skill-injected]` marker line when this body was injected, otherwise the installed copy `$CODEX_HOME/skills/fz-planner/references/domain-ios.md` (default `~/.codex/skills/fz-planner/…`). A planning decision that rests only on that pack is marked `plugin-default` in its `why`; a project rule overrides the pack.

## Planning Process

### 1. Codebase Exploration
- Find similar existing implementations (match the feature's naming patterns)
- Identify affected files/symbols from the requirements
- Understand the current patterns for the feature area

### 2. Impact Identification
- Map requirements to the components the project architecture defines (create/modify/delete)
- Identify the layers touched and check them against the project's `dependencyDirection`
- Find protocols/interfaces to extend vs create new
- Check owner/parent changes needed (callback interfaces, navigation entry points)

### 2b. Implication Register
For removal/refactoring/migration tasks, generate an Implication Register:
- **Execution Implication**: structural residuals that MUST be addressed for completeness (e.g., an initializer kept only for a removed dependency). Status: `needs_user_confirmation`.
- **Observation Implication**: out-of-scope architectural issues found during exploration (e.g., project-rule violations). Status: `report_only`.

### 3. Implementation Steps
File-level concrete steps:
- `create`/`modify`/`delete` target files
- Dependency wiring changes (new dependencies, construction sites)
- Protocol changes (breaking/non-breaking, new methods)
- Test coverage needs

### 4. Self Stress Test (Q1-Q5)
Apply to own plan before reporting:
- Q1 Multiplicity: does design work for 1 and N instances equally?
- Q2 Consumer Impact: parent layer needs new branch/type/protocol?
- Q3 Complexity Migration: simplification in one layer → added complexity elsewhere?
- Q4 Edge Cases: what does this abstraction not cover? Minimum 1 alternative pattern.
- Q5 Access Boundaries: intended encapsulation actually enforced by access modifiers?

## Output Format

Output **one JSON object and nothing else** — no prose before or after it:

```json
{
  "status": "ok",
  "reason": null,
  "approach": "<one-line summary>",
  "affectedFiles": {"new": 0, "modified": 0},
  "steps": [{"file": "<path>", "action": "create|modify|delete", "why": "<architectural reasoning>"}],
  "riskMatrix": [{"risk": "<risk>", "q": "Q1", "layer": "<layer or module>", "mitigation": "<mitigation>"}],
  "stressTest": [{"q": "Q1", "result": "pass|warn|fail", "note": "<note>"}],
  "implicationRegister": [{"id": "IR-1", "type": "exec|obs", "trigger": "", "locus": "", "reason": "", "policy": "", "status": "needs_user_confirmation|report_only"}],
  "divergencePoints": ["<decision area where another plan may differ — worth explicit comparison>"],
  "projectRules": {"axes": {}, "rules": [], "conflicts": [], "gaps": []}
}
```

- `status` is `"ok"` or `"rejected"`. A rejection sets `reason` (`"claude_plan_detected"` or `"requirements_missing"`) and leaves every array empty.
- `steps[].file` is one path relative to the repository root. A step that touches several files uses `"files": [...]` instead.
- `projectRules` holds your rule records in the Project Rules shape (`axes` · `rules` · `conflicts` · `gaps`).

## When Project Guidelines Are Absent

No guideline file exists, or none applies to the planned paths. Then:
- Plan with general engineering principles only — separation of concerns, dependency inversion, single responsibility — and follow the structure the existing code already shows.
- Do not assume any framework, architecture pattern, layer order or folder convention. Record every architecture axis in `projectRules.gaps`.
- Say in `divergencePoints` which structural choices you made without a project rule.
