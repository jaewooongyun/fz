---
name: fz-guardian
description: Post-change verification — every feedback item resolved, the original issue fixed and no regression introduced, judged by the target repository's own rules
---

# fz-guardian — Post-Change Verification Skill

## Role
Verify that feedback has been fully applied and no regressions are introduced.

> **Authority**: VeriGuard (arXiv 2510.05156) [arxiv preprint, 2025-10] — **dual-stage verification** (Pre-action Gate + Runtime Gate) outperforms single-stage. 본 스킬은 feedback completeness (Pre-action) + regression scan (Runtime) 이중 구조로 검증한다 (Chain-of-Verification arXiv 2309.11495 패턴 결합).

## Project Rules (runtime)

Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
5. **Citing** — a verdict that relies on a project rule cites it as `{file}:{line} — "<quote>"`.
- **Domain pack (conditional)** — if the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`), also read `references/domain-ios.md`. A finding that rests only on that pack carries `ruleSource: plugin-default` and severity at most `suggestion`; a project rule overrides the pack.

## Verification Criteria

### Feedback Completeness
- Every review comment or requested change is addressed.
- No feedback item is partially applied or skipped.
- Mark each feedback item: resolved | partially_resolved | unresolved | regressed.

### Original Issue Resolution
- The root cause identified in the original issue is fixed.
- The fix directly addresses the problem (not a workaround).
- Acceptance criteria from the original request are met.

### No New Issues Introduced
- No new compiler errors or warnings.
- No new lint or static analysis violations.
- No unrelated code changes bundled in.
- No TODO/FIXME added without tracking.

### Memory and Concurrency Safety
- Changes do not introduce reference cycles.
- Shared state access remains thread-safe.
- UI-update paths keep the execution context they require (the UI thread) — no path lost it in the change.
- State owned by one execution context is not touched from another without synchronization.
- Resource cleanup paths are intact.

### Implication Gate Compliance
- Verify no inferred changes were executed without user confirmation.
- For removal/refactoring: check that execution implications (structural residuals) were either approved and addressed, or dismissed with reason.
- For observation implications: verify they were reported but NOT auto-fixed.

### Regression Risk
- Identify code paths affected by the change.
- Check that existing behavior is preserved where intended.
- Flag any behavioral changes that were not explicitly requested.

### Transformation Equivalence (피드백에 패턴 변환이 포함될 때)
- 비동기 패턴 변환(promise → async, callback → async 등)이면 원본 API 의 실행 컨텍스트(어느 스레드·큐에서 도는가)를 확인한다
- After 패턴이 스레드/에러 수준에서 원본과 동등한지 검증
- Zero-Exception Thread: 원본이 UI 스레드에서 돌았으면 After 도 UI 스레드를 보장해야 한다
- After 줄 수 > Before 2배 → 추상화 부재 경고

## Output Format

Matches `schemas/gpt_verification_schema.json`. Key enum values:
- `resolution_status`: `resolved` | `partially_resolved` | `unresolved` | `regressed`
- `verdict`: `pass` | `needs_work` | `fail`
- Feedback reflection rate: `(resolved*1.0 + partially_resolved*0.5) / total_issues`

```
### Feedback Item: "description"
- Status: resolved|partially_resolved|unresolved|regressed
- Evidence: file:line or explanation
- Risk: none|low|medium|high
```

## Few-shot Example

```
BAD (검증 누락):
### Feedback Item: "해제 시 구독 정리 요청"
- Status: resolved
- Evidence: "코드 수정함"     ← 파일:라인 없음, 실제 확인 불가
- Risk: none

GOOD:
### Feedback Item: "해제 시 구독 정리 요청"
- Status: resolved
- Evidence: src/sync/sync_job.py:87 — stop() 에서 구독을 해제한다 · tests/test_sync_job.py:40 가 해제 뒤 콜백 0회를 단언한다
- Risk: none
```

## When Project Guidelines Are Absent

No guideline file exists, or none applies to the changed paths. Then:
- Apply general verification practice: confirm each change request is met, check for side effects, and validate no regressions in affected code paths.
- Do not assume any framework, architecture pattern, layer order or folder convention. Report every architecture axis as a Probe Coverage Gap.
- A convention verdict may cite only what the code itself shows (`authority: 관례`, quoting the code).
