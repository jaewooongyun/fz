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

<!-- shared:project-rules begin -->
Rules come from the target repository at run time — never from this skill.

1. **Sources** — read every guideline file in the repository: `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` (in any folder) and `.github/copilot-instructions.md`. Skip `.git` and `node_modules`. If the caller hands you a raw index of these files (file · line · heading · quote), work from it instead of searching.
2. **Rule records** — build your own records; never reuse another model's interpretation. One record per rule: `axis` (`architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions`) · `authority` (`지침` = a rule sentence in a guideline file · `관례` = observed in code, quote the code · `예시` = an example inside a guideline) · `appliesTo` (languages · paths) · `condition` · `expectedResult` · `source` (file · line · verbatim quote).
3. **Examples are not rules** — text under an `Example(s)` / `예시` heading, inside a code fence, or in `(e.g. …)` / `(예: …)` is `authority: 예시`. Never raise an example to a rule.
4. **Unknown and conflicting axes** — an axis you cannot confirm stays `null` and is reported as a Probe Coverage Gap. When two sources disagree, keep both claims as a **rule conflict** item and do not pick a winner.
<!-- shared:project-rules end -->
5. **Citing** — a fix shaped by a project rule cites it as `{file}:{line} — "<quote>"`.
- **Domain pack (conditional)** — if the repository is an iOS/Swift project (`*.swift` sources, a `Package.swift` or an `.xcodeproj`), also read `references/domain-ios.md` in this skill's folder — the folder named on the `[fz-gpt-skill-injected]` marker line when this body was injected, otherwise the installed copy `$CODEX_HOME/skills/fz-fixer/references/domain-ios.md` (default `~/.codex/skills/fz-fixer/…`). A repair choice that rests only on that pack is marked `plugin-default`; a project rule overrides the pack.

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

## Check Catalog

Before you finish, check each question below against what you were given (plan and requirement · diff · fix). Skip rows that do not apply. When the output schema has `catalogHits`, record each row that applies as `catalogId` · `target` (file:line or subject) · `verdict` (`hit` = problem found · `clear` = checked, no problem · `unchecked` = could not judge — say why in `target`), report every hit as a finding too, and return an empty array when no row applies.

<!-- shared:catalog-code begin -->
| id | 묻는 것 |
|---|---|
| F-173 | 사용 위치 · 방식을 바꾼 심볼은 diff 밖이어도 선언부 `///` 문서 주석을 열어 새 사용과 맞는지 대조했는가 |
| F-280 | 새 호출 지점이 대상과 다른 파일이면 대상의 접근 수준을 실측했는가 — private 이면 완화를 Step 에 적는다 · 정의 파일과 편집 파일이 다른 모듈 · 타깃 · 조건부 컴파일 블록이면 import · 가시성 · 컴파일 조건도 실측한다(F-129) |
| F-365 | 표현식을 다른 표현식으로 바꾼 자리 — 제거된 표현식의 암묵 효과(초기화 · 부수효과 · 평가 순서 · 옵셔널 단락)가 새 표현식에도 있는가 |
| F-371 | 기존 술어를 재사용하면 같은 타입의 형제 술어를 열거해 본문을 대조했는가 · 경쟁 후보가 갈리는 표본 1건(없으면 [판별 불가]) |
| F-521 | 바꾼 사실을 다른 표현으로 함께 쓰던 코드가 있는가 — 특히 기준 · 좌표계 · 단위를 바꿀 때 |
| F-556 | 함수를 다시 쓴 수정 — 옛 조건식의 항(and · or 피연산자)이 새 본문에 남았는가, 빠진 항마다 그 항을 단언하는 테스트가 있는가 |
<!-- shared:catalog-code end -->

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
