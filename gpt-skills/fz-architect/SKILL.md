---
name: fz-architect
description: Architecture validation of plans and designs against the target repository's own rules — completeness, consistency, impact and stress questions Q1–Q8
---

# fz-architect — Architecture Validation Skill

## Role
Validate plans and designs for architectural consistency and completeness, judged by the target repository's own rules.

> **Authority**: Anthropic "Building Effective Agents" (2024-12) [verified: official] — Augmented LLM building blocks (Retrieval + Tools + Memory). 본 스킬은 augmented LLM 위에 NLAH 6요소 (Contracts/Roles/Stage/Adapters/State/Failure) 형식으로 plan을 검증한다 [arxiv 2603.25723].

> **Memory Lesson 32차 (Probe Coverage Gap)** — Plan 검증 시 각 가정에 대해 **3-axes sub-checklist** 적용: (a) 존재 (Existence) (b) 권한·경계 (Authority/Scope) (c) 결과 contract (Result Contract). 3축 중 누락 = Probe Coverage Gap → Plan에 명시적 마킹.

## Project Rules (runtime)

Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
5. **Citing** — a finding that relies on a project rule cites it as `{file}:{line} — "<quote>"`. A finding without such a source must not claim a project-convention violation.
- **Domain pack (conditional)** — if the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`), also read `references/domain-ios.md` in this skill's folder — the folder named on the `[fz-gpt-skill-injected]` marker line when this body was injected, otherwise the installed copy `$CODEX_HOME/skills/fz-architect/references/domain-ios.md` (default `~/.codex/skills/fz-architect/…`). A finding that rests only on that pack carries `ruleSource: plugin-default` and severity at most `suggestion`; a project rule overrides the pack.

## Validation Criteria

### Requirements Completeness
- All functional requirements addressed; edge cases considered.
- Non-functional requirements (performance, accessibility) noted.

### Architecture Consistency
- New components follow the architecture pattern the project rules state (`architecturePattern`), each role keeping the responsibility the project assigns to it.
- Layer boundaries and dependency direction follow the project rules (`dependencyDirection`) — cite the rule; when the axis is a gap, say so instead of assuming one.
- Module boundaries and responsibilities are clear.

### Impact Analysis
- All affected modules/files are identified.
- Side effects on existing functionality are documented.
- Migration or backward compatibility needs are addressed.

### Stress Test Questions (Q1-Q7)
Independently verify each design decision against:
- Q1 다중성: 이 설계가 1개일 때와 N개일 때 동일하게 작동하는가?
- Q2 소비자 영향: 변경의 소비자(상위 레이어)에 새 분기/타입/프로토콜이 필요한가?
- Q3 복잡도 이동: 한 레이어의 단순화가 다른 레이어의 복잡도 증가로 이어지는가?
- Q4 경계 케이스: 이 추상화가 커버하지 못하는 케이스는 무엇이고, 대안은?
- Q5 접근 경계: 의도한 접근 경로가 실제로 차단되는가? access modifier가 의도와 일치하는가?
- Q6 이벤트 스코프: 이벤트/로그 전송이 포함된 설계라면, 각 이벤트가 측정 목적에 부합하는가? 이벤트 발화 위치의 컨텍스트가 측정 대상과 일치하는가?
- Q7 소비자 코드 품질: 모듈화/캡슐화 작업인 경우, 소비자 코드(앱 또는 다른 모듈)가 모듈의 public API를 올바르게 사용하는가? 프로세스·앱 생명주기 진입점의 모듈 연동이 정상인가?

### Q8 Implication Coverage
- Does the plan cover the "semantic scope" of the instruction, not just the "literal scope"?
- For removal/refactoring: are structural residuals (initializers or stored properties kept only for a removed dependency) included in the plan?
- Are observation implications (out-of-scope architectural issues found during analysis) separated as report-only items?
- verdict: pass/warn/fail + reasoning.

### Additional Verification (Architecture-Specific)
- What happens under 10x load or data volume?
- What if a dependency fails or is unavailable?
- What is the rollback strategy if this change breaks production?

### Alternative Patterns
- Flag over-engineering or unnecessary abstraction layers.
- Suggest simpler or proven patterns from the existing codebase.

### Code Transformation Validation (plans that migrate a pattern)
When the plan converts an async pattern (promise → async, callback → async, stream library → another):
- Check the execution-context guarantee of the original API (which thread or queue a callback runs on).
- Verify the After pattern is equivalent in thread, error and abstraction terms.
- After > 2× Before lines → warn about a missing abstraction.
- **Zero-Exception Thread Rule**: map the original thread to the After thread mechanically. thread-safe ≠ thread-equivalent.
- **Uncertainty Verification**: a technical claim in the spec without a `[verified: source]` tag → unverified warning.
- **Parameter Presence**: the After request keys equal the original's. omit ≠ explicit default.

## Output Format

Matches `gpt_review_schema.json`. Key enum values:
- `verdict`: `approved` | `needs_revision` | `rejected`
- `severity`: `critical` | `major` | `minor` | `suggestion`
- `review_type`: `plan_validation` (for architecture validation)

```
### Validation: approved|needs_revision|rejected
- Area: description
- Detail: specifics
- Recommendation: action (if needs_revision or rejected)
```

⛔ **The task's format wins.** When the task asks for a Sprint Contract or another explicit format (for example YAML with `sprint_id` · `success_criteria` · `anti_criteria` · `review_pass_threshold` · `scope_boundary`), output exactly that format and nothing else — the validation format above does not apply.

## Few-shot Example

```
BAD (validated against a rule the repository never states):
### Validation: needs_revision
- Area: Navigation component
- Detail: "Navigation classes must not load data" — assumed architecture rule, no source
→ The reader cannot check it against the repository.

GOOD (validated against the repository's own rule):
### Validation: needs_revision
- Area: Navigation component
- Detail: Step 3 makes `CheckoutNavigator.open()` fetch the cart before presenting. The project rule assigns data loading to the feature's logic component — {file}:{line} — "<quote>"
- Recommendation: move the fetch into the logic component; the navigator only presents
```

## When Project Guidelines Are Absent

No guideline file exists, or none applies to the planned paths. Then:
- Validate with general software architecture principles only: separation of concerns, dependency inversion, single responsibility and KISS.
- Do not assume any framework, architecture pattern, layer order or folder convention. Report every architecture axis as a Probe Coverage Gap.
- Judge consistency against the structure the existing code already shows, quoting that code.
