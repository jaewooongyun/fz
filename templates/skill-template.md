# Skill Template

> Template for authoring Claude Code skills (`skills/fz-*.md`).
> Each SKILL.md should stay under **500 lines** — focused 300 tokens outperform unfocused 113K tokens.

---

## YAML Frontmatter

Every skill file begins with YAML frontmatter. All 10 fields are listed below.

```yaml
---
name: fz-{name}                          # lowercase+hyphen, required (L1 공식)
description: >-                           # required (L1 공식) — the most important field
  {What it does} + {When to use} + {When NOT to use}.
  Bilingual keywords for matching.
user-invocable: true|false               # required (L1 공식)
argument-hint: "[target] [--options]"     # optional
allowed-tools: >-                         # required (L1 공식) — comma-separated
  mcp__serena__find_symbol,
  Edit, Read, Grep, Glob, Bash(pattern)
provides: [capability-tokens]             # required (L2 fz 정책) — /fz 동적 파이프라인이 소비
needs: [capability-tokens|none]           # required (L2 fz 정책) — 자기완결이면 [none]
intent-triggers:                          # for /fz orchestrator routing
  - "한국어|패턴"
  - "english|pattern"
compatibility: >-                         # optional, 1-500 chars
  iOS 16+, Xcode 16+, Swift 6
disable-model-invocation: false          # true: 사용자 명시 호출만 허용
---
```

> ⛔ **필수 필드 정본은 `modules/governance.md` § 스킬 최소 기준**이다 — L1(Claude Code 공식 4) + L2(fz 정책 2). 이 템플릿은 그 정본을 반영하며 재정의하지 않는다.
> ⛔ **제거된 필드 3종** (2026-08-09): `team-agents` · `composable` · `model-strategy` — 전부 fz 자작 필드로 **런타임 효과가 없었다**. 실효 결정자는 팀 구성·모델 = `workflows/*.js`, 파이프라인 = `provides`/`needs`.

---

## Field Guide

| Field | Req? | Purpose | Tips |
|-------|------|---------|------|
| `name` | required | Unique skill identifier | `fz-` prefix, lowercase+hyphen only |
| `description` | required | LLM selection signal | **The most critical field.** Claude picks skills by reasoning over this text — there is no algorithmic router *for Claude's own skill selection*. ⛔ `/fz` is different: it **does** route algorithmically, by matching `modules/intent-registry.md` patterns in Phase 1. Both paths matter — `description` drives Claude, registry patterns drive `/fz`. Write in 3rd person ("Processes files" not "I can help you"). Include what + when + when-not + bilingual keywords. |
| `user-invocable` | required | Whether users can call directly | `false` for sub-skills called only by orchestrators |
| `argument-hint` | optional | Usage hint shown to user | Keep concise: `"[file] [--strict]"` |
| `allowed-tools` | required (L1) | Tools this skill may use | List only what is needed. Bash can be pattern-restricted: `Bash(xcodebuild *)`, `Bash(git *)` |
| `provides` | **required (L2 fz)** | Capability tokens this skill outputs | See registry below. `/fz` §3.2 동적 파이프라인이 실제 소비한다 |
| `needs` | **required (L2 fz)** | Capability tokens required as input | Use `[none]` if self-contained |
| `intent-triggers` | **required if `user-invocable: true`** (except `fz` itself) | Patterns for `/fz` orchestrator | Korean and English trigger phrases. ⛔ **`/fz` Phase 1 reads `modules/intent-registry.md`, not this field** — add the pattern there too, or `/fz` will never route to this skill. This field documents the skill and feeds `fz-skill eval`. |
| `disable-model-invocation` | optional | Claude의 자동 스킬 호출 방지 | `true` 설정 시 사용자 명시 호출만 허용 |
| `compatibility` | optional | 환경 요구사항 | OS, 패키지, 네트워크 접근 등 |

---

## Capability Token Registry

Tokens used in `provides` / `needs` fields across existing skills:

| Token | Meaning |
|-------|---------|
| `planning` | Structured plan output |
| `architecture-analysis` | Codebase structure understanding |
| `code-changes` | Modified source files |
| `search-results` | Code search / exploration output |
| `review-results` | Code review findings |
| `verification` | Build / test / lint pass confirmation |
| `commit` | Git commit created |
| `pr` | Pull request created |
| `peer-review` | Cross-agent review |
| `file-header` | Standardized file headers |
| `code-quality-analysis` | Quality metrics and findings |
| `documentation` | Generated docs |
| `skill-management` | Skill CRUD operations |
| `pr-digest` | PR summary digest |
| `code-understanding` | Deep code comprehension |
| `refined-requirements` | Clarified requirements |
| `constraint-matrix` | Constraint analysis output |
| `memory-management` | Memory lifecycle operations (audit, gc, organize) |
| `memory-recall` | Context-aware learning retrieval from topic files |

---

## SKILL.md Body Structure

Below is the markdown body that follows the YAML frontmatter.

````markdown
# /fz-{name} — {one-line role}

> **행동 원칙**: {1-2 sentences on how this skill behaves}

## 개요

```
Input → Phase 1 → Phase 2 → ... → Output
```

- Feature 1
- Feature 2
- Feature 3

## 사용 시점

```bash
/fz-{name} "example 1"    # explanation
/fz-{name} "example 2"    # explanation
/fz-{name} "example 3"    # explanation
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| `guides/skill-authoring.md` §12 | 팀 모드 정본 — Workflow 규약 + 실패 복구 사다리 L1~L4. ⛔ `modules/team-core.md`를 팀 프로토콜로 지목하지 말 것 (역사적 출처) |
| `modules/team-registry.md` | 에이전트 동적 구성 |

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| 분석 | `sc:analyze` | 코드 분석 |
| 검증 | `sc:reflect` | 자체 검증 |

## 팀 에이전트 모드

- **Workflow**: `workflows/{skill}-{pattern}.js` 결정적 스크립트가 fan-out/수렴 소유 (§12)
- **Agents**: agentType(`fz:`)으로 재사용 — 구조화 출력 반환, Lead 통합
- **Communication**: P2P SendMessage 없음 — 스크립트가 라운드 구현

---

## Phase 1: {Name}

### 절차
1. Step one
2. Step two

### Gate 1: {Condition}
- [ ] Check 1 passes
- [ ] Check 2 passes

---

## Phase 2: {Name}

### 절차
1. Step one
2. Step two

### Gate 2: {Condition}
- [ ] Check 1 passes
- [ ] Check 2 passes

---

## 테스트 케이스 (선택)

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "{트리거 쿼리 1}" | trigger | 일반 케이스 |
| "{트리거 쿼리 2}" | trigger | 보조 케이스 |
| "{비관련 쿼리}" | NOT trigger | → fz-{other} |

### Functional

| Given | When | Then |
|-------|------|------|
| {초기 조건} | /fz-{name} "{입력}" | {예상 결과} |
| {엣지 조건} | /fz-{name} "{입력}" | {예상 결과} |
| {실패 조건} | /fz-{name} "{입력}" | {에러 핸들링} |

상세: `guides/skill-testing.md`

## Boundaries

**Will**:
- Thing this skill does
- Another thing it does

**Will Not**:
- Out-of-scope task -> use `fz-other`
- Another out-of-scope task -> use `fz-another`

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| Build failure | Retry with clean | Report to user |
| File not found | Search alternatives | Ask user for path |

## Completion -> Next

- On success: proceed to `fz-next-skill` or report results
- On partial: list remaining items, suggest retry
- On failure: rollback changes, report root cause
````

---

## Few-shot Examples for `description`

The `description` field determines whether Claude selects this skill. Quality matters.

```
BAD:  "Helps with documents"
       (too vague, no when/when-not, no keywords)

BAD:  "I can help you search code"
       (1st person, no scope boundaries)

GOOD: "프로젝트 코드 탐색 + 구조 분석 + 의존성 추적 스킬. 병렬 교차 검증으로 정확도 확보.
       Use when exploring code structure, tracing symbol dependencies.
       Do NOT use for code modification (use fz-fix or fz-code)."

GOOD: "버그 수정 경량 스킬. 원인 분석 → 수정 → 빌드 검증의 빠른 사이클.
       Use when fixing bugs, resolving crashes, correcting errors.
       Do NOT use for new feature implementation (use fz-code)."
```

---

## Pre-completion Checklist

Before finalizing a new skill, verify:

- [ ] `description` includes what + when + when-not?
- [ ] `description` has bilingual keywords?
- [ ] SKILL.md body under 500 lines?
- [ ] Boundaries section has Will and Will Not (with alternatives)?
- [ ] At least 3 usage examples?
- [ ] Gate conditions are checklistable?
- [ ] Error handling table present?
- [ ] Completion -> Next section present?
- [ ] No aggressive language (avoid CRITICAL, MUST ALWAYS, etc.)?
- [ ] References use explicit paths (`modules/X.md` not just `X.md`)?
- [ ] Triggering test cases 최소 3개 (should + should-NOT)?
- [ ] compatibility 필드 작성? (환경 의존성 있을 때)

---

## Design Principles

| Principle | Application |
|-----------|-------------|
| Action > Role | "Analyze code structure" not "You are an analyzer" |
| Structure > Length | Tables, checklists over prose paragraphs |
| Few-shot > Explanation | 1 example outweighs 50 lines of explanation |
| Will/Won't boundaries | Prevent scope creep with redirect alternatives |
| Gate checklists | Verifiable completion conditions at each phase |
| < 500 lines | Progressive Disclosure — YAML always loaded, body on relevance, refs on demand |
| Explicit paths | `templates/X.md` not just `templates/X.md` |
| Natural language | "Use when..." not "CRITICAL: You MUST..." |

---

## Verification

모든 스킬은 다음 Verification Discipline 규약을 따른다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델/도구 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
- T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 후 계속

관련 modules: `modules/uncertainty-verification.md` (Default-Deny), `modules/system-reminders.md` (T6/T7), `modules/lead-reasoning.md §1.5` (Speculation-to-Fact Fallacy).

---

## If Workflow is used (조건부 필수)

Workflow(멀티에이전트 오케스트레이션)를 호출하는 스킬이면 다음 필수 (`guides/skill-authoring.md` §12):

- [ ] frontmatter `allowed-tools`에 `Workflow` 추가 (누락 시 호출 불가 dead code)
- [ ] 표준 3종 (OVERRIDE 블록 / args 방어 파싱+fail-fast / agentType `fz:`)
- [ ] 반환 `{mode, metrics{...}}` 계약 + 검증 oracle (래핑 syntax + 실 invoke ≥1 + §5.7 기록)
