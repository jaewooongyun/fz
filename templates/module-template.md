# Module Template

> Progressive Disclosure Level 3 template for creating shared module files in `modules/`

## Overview

Modules are reusable knowledge resources loaded by Claude via Read tool only when needed. They follow consistent structure, naming conventions, and sizing constraints to optimize Progressive Disclosure.

---

## Module Structure Template

```markdown
# {Module Name}

> {One-line purpose describing what this module provides}

## 참조 스킬
| 스킬 | 참조 이유 |
|------|----------|
| fz-{name} | {why this skill references this module} |
| fz-{name} | {why this skill references this module} |

## {Core Content Section 1}
{Tables, procedures, patterns, or reference data}

## {Core Content Section 2}
{Additional structured content as needed}

## 설계 원칙
- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
- 100줄+ 시 목차 포함
```

---

## Module Naming Convention

| Pattern | Example | Use |
|---------|---------|-----|
| `{domain}-core.md` | team-core.md | Core protocols, absolute rules |
| `{domain}-registry.md` | team-registry.md | Agent/capability registries |
| `{domain}-policy.md` | memory-policy.md | Policies, rules, constraints |
| `{function}.md` | complexity.md, pipelines.md | Functional modules, domain knowledge |
| `{reference}-refs.md` | plugin-refs.md | Reference collections, lookup tables |
| `patterns/{name}.md` | patterns/collaborative.md | Communication pattern definitions |

---

## Pre-completion Checklist

- [ ] 참조 스킬 table includes all skills that reference this module?
- [ ] Module content under 500 lines?
- [ ] Table of contents included if content is 100+ lines?
- [ ] Explicit absolute paths when referencing other files?
- [ ] One-line purpose clearly states module value?
- [ ] Each section has clear, descriptive heading?
- [ ] No skill-specific implementation details (only shared reference)?

---

## Guidelines

**When to Create a Module:**
- Knowledge needed across multiple skills
- Reference data larger than inline documentation
- Shared procedures or design patterns
- Domain-specific policies or constraints

**When NOT to Create a Module:**
- Skill-specific implementation details
- Content used by only one skill
- Frequently changing operational data
- Integration-specific configurations

**Best Practices:**
- Keep modules focused and single-purpose
- Use Korean for 참조 스킬 and 설계 원칙 sections
- Structure with tables for lookup efficiency
- Reference modules by their full path: `modules/{module-name}.md`
