# Skill Template

> Template for authoring Claude Code skills (`.claude/skills/fz-*.md`).
> Each SKILL.md should stay under **500 lines** — focused 300 tokens outperform unfocused 113K tokens.

---

## YAML Frontmatter

Every skill file begins with YAML frontmatter. All 13 fields are listed below.

```yaml
---
name: fz-{name}                          # lowercase+hyphen, required
description: >-                           # required — the most important field
  {What it does} + {When to use} + {When NOT to use}.
  Bilingual keywords for matching.
user-invocable: true|false               # required
argument-hint: "[target] [--options]"     # optional
allowed-tools: >-                         # required — comma-separated
  mcp__serena__find_symbol,
  Edit, Read, Grep, Glob, Bash(pattern)
team-agents:                              # optional
  primary: agent-name|null
  supporting: [agent-list]
composable: true|false                    # optional
provides: [capability-tokens]             # for pipeline composition
needs: [capability-tokens|none]           # dependencies
intent-triggers:                          # for /fz orchestrator routing
  - "한국어|패턴"
  - "english|pattern"
model-strategy:                           # optional
  main: opus|sonnet
  verifier: sonnet|null
compatibility: >-                         # optional, 1-500 chars
  iOS 16+, Xcode 16+, Swift 6
disable-model-invocation: false          # true: 사용자 명시 호출만 허용
---
```

---

## Field Guide

| Field | Req? | Purpose | Tips |
|-------|------|---------|------|
| `name` | required | Unique skill identifier | `fz-` prefix, lowercase+hyphen only |
| `description` | required | LLM selection signal | **The most critical field.** Claude picks skills by reasoning over this text — there is no algorithmic router. Write in 3rd person ("Processes files" not "I can help you"). Include what + when + when-not + bilingual keywords. |
| `user-invocable` | required | Whether users can call directly | `false` for sub-skills called only by orchestrators |
| `argument-hint` | optional | Usage hint shown to user | Keep concise: `"[file] [--strict]"` |
| `allowed-tools` | required | Tools this skill may use | List only what is needed. Bash can be pattern-restricted: `Bash(xcodebuild *)`, `Bash(git *)` |
| `team-agents` | optional | Multi-agent configuration | `primary` runs the main loop; `supporting` agents assist. See `.claude/modules/team-registry.md` for agent list. |
| `composable` | optional | Can be chained in pipelines | Set `true` if output feeds another skill |
| `provides` | optional | Capability tokens this skill outputs | See registry below |
| `needs` | optional | Capability tokens required as input | Use `[none]` if self-contained |
| `intent-triggers` | optional | Patterns for `/fz` orchestrator | Korean and English trigger phrases |
| `model-strategy` | optional | Model selection per phase | `opus` for reasoning-heavy, `sonnet` for verification |
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
| `.claude/modules/team-core.md` | 팀 프로토콜 |
| `.claude/modules/team-registry.md` | 에이전트 동적 구성 |

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| 분석 | `sc:analyze` | 코드 분석 |
| 검증 | `sc:reflect` | 자체 검증 |

## 팀 에이전트 모드

- **Primary**: {agent role and responsibility}
- **Supporting**: {agent roles}
- **Communication**: TeamCreate → parallel work → merge results

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

상세: `.claude/guides/skill-testing.md`

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
- [ ] References use explicit paths (`.claude/modules/X.md` not just `X.md`)?
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
| Explicit paths | `.claude/templates/X.md` not just `templates/X.md` |
| Natural language | "Use when..." not "CRITICAL: You MUST..." |
