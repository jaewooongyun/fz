---
name: fz-fixer
description: Bug fix — root cause, minimal fix and regression prevention, following the target repository's own rules and existing patterns
---

# fz-fixer — Bug Fix Skill

## Role
Diagnose root causes, apply minimal fixes, and prevent regressions.

> **Authority**: Chain-of-Verification (CoVe, arXiv 2309.11495) [verified: peer-reviewed] — Generate verification questions before applying fix, then verify each independently. 본 스킬은 수정 전 root cause 가설을 verification chain으로 검증한다 (Reflexion arXiv 2303.11366의 self-refinement 패턴과 결합).

> **Memory Lesson 36차 (Team-Shared Boundary)** — Bug fix 시에도 팀 공유 영역(lint 설정 · `.github/` · 패키지 매니페스트 · 빌드 설정 · pre-commit hook 등) 자동 변경 금지. 사용자 명시 합의 의무. 대상 저장소 지침이 "팀 공유 영역"을 정의하면 그 정의가 우선.

## Project Rules (runtime)

Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
5. **Citing** — a fix shaped by a project rule cites it as `{file}:{line} — "<quote>"`.
- **Domain pack (conditional)** — if the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`), also read `references/domain-ios.md`. A repair choice that rests only on that pack is marked `plugin-default`; a project rule overrides the pack.

## Fix Process

### Root Cause Analysis
- Trace execution flow from symptom to root cause.
- Distinguish root cause from symptoms (fix cause, not symptom).
- Document the causal chain clearly.

### Fix Strategy
- Apply the minimal change that resolves the root cause.
- Prefer fixes at the correct abstraction layer; choose the least invasive.
- Do not refactor unrelated code in the same change.

### Side Effect Minimization
- Check all callers of modified functions.
- Verify behavioral contracts and public API are preserved.
- Validate that default values and edge cases still hold.

### Existing Pattern Compliance
- Match the coding style and error handling pattern of surrounding code.
- Follow the project's dependency injection approach.
- Respect layer boundaries and module ownership as the project rules state them.

### Regression Prevention
- Identify related code paths that could break.
- Suggest test cases that cover the fix.
- Verify the fix does not mask other latent bugs.

## Anti-Repair Patterns (DO NOT do these as fixes)

These look like fixes but introduce new violations or suppress symptoms without resolving the root cause.

- ❌ Weakening isolation or thread annotations only to silence a warning — fix the pattern that caused it.
- ❌ Loosening access control only to silence an access error — restructure the data flow instead.
- ❌ Moving work off the thread or queue the original code guaranteed (for example UI updates off the UI thread).
- ❌ Swallowing errors that the original code propagated — preserve the original error semantics (catch + handle, not silence).
- ❌ Wrapping a layer violation in an async block instead of moving the call to the layer that owns it.

## Linkage
- When invoked via `fz-gpt`, results feed into the `check` subcommand for iterative fix-verify cycles.

## Output Format
```
### Bug: "description"
- Root Cause: explanation with file:line
- Fix: description of change
- Files Modified: list
- Side Effects: none|description
- Suggested Tests: test case descriptions
```

## Few-shot Example

```
BAD (증상 수정):
### Bug: "API 응답 후 화면 갱신 안 됨"
- Root Cause: "응답 처리 코드 문제"   ← 막연한 설명, 파일:라인 없음
- Fix: 갱신 호출에 지연(delay) 추가

GOOD:
### Bug: "API 응답 후 화면 갱신 안 됨"
- Root Cause: src/feed/feed_loader.js:94 — fetchFeed() 완료 콜백이 워커 스레드에서 render() 를 호출한다(원본 콜백은 UI 스레드였다)
- Fix: src/feed/feed_loader.js:94 — render() 를 UI 스레드로 디스패치
- Side Effects: tests/feed_loader.test.js:51 — 기존 테스트 통과 확인
```

## When Project Guidelines Are Absent

No guideline file exists, or none applies to the changed paths. Then:
- Apply general debugging practice: isolate the root cause, apply the minimal fix, verify no regressions, and follow the patterns of the surrounding code.
- Do not assume any framework, architecture pattern, layer order or folder convention. Report every architecture axis as a Probe Coverage Gap.
- A convention-driven fix choice may cite only what the code itself shows (`authority: 관례`, quoting the code).
