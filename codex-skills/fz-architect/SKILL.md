---
name: fz-architect
description: Architecture Validation Skill
---

# fz-architect — Architecture Validation Skill

## Role
Validate plans and designs for architectural consistency and completeness.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — identify architecture patterns and layer rules.
3. `## Guidelines` — find and read guideline files (paths relative to GIT_ROOT):
   - `AI/ai-guidelines.md` — coding rules and project conventions.
   - `AI/review-guidelines.md` — review standards and criteria.
4. `## Code Conventions` — identify coding rules and structural conventions.

## Validation Criteria

### Requirements Completeness
- All functional requirements addressed; edge cases considered.
- Non-functional requirements (performance, accessibility) noted.

### Architecture Consistency
- New components follow the established architecture pattern.
- Layer boundaries are respected (no upward/cross-layer violations).
- Dependency direction is correct per project rules.
- Module boundaries and responsibilities are clear.
- **RIBs**: Router=네비게이션, Interactor=비즈니스로직, Builder=DI 역할을 준수한다.
- **Clean Architecture 레이어**: Network→Repository→UseCase→Workflow 방향만 허용 (상위 레이어 참조 금지).

### Impact Analysis
- All affected modules/files are identified.
- Side effects on existing functionality are documented.
- Migration or backward compatibility needs are addressed.

### Stress Test Questions (Q1-Q5)
Independently verify each design decision against:
- Q1 다중성: 이 설계가 1개일 때와 N개일 때 동일하게 작동하는가?
- Q2 소비자 영향: 변경의 소비자(상위 레이어)에 새 분기/타입/프로토콜이 필요한가?
- Q3 복잡도 이동: 한 레이어의 단순화가 다른 레이어의 복잡도 증가로 이어지는가?
- Q4 경계 케이스: 이 추상화가 커버하지 못하는 케이스는 무엇이고, 대안은?
- Q5 접근 경계: 의도한 접근 경로가 실제로 차단되는가? access modifier가 의도와 일치하는가?

### Q8 Implication Coverage
- Does the plan cover the "semantic scope" of the instruction, not just the "literal scope"?
- For removal/refactoring: are structural residuals (override init, stored properties, convenience init) included in the plan?
- Are observation implications (out-of-scope architectural issues found during analysis) separated as report-only items?
- verdict: pass/warn/fail + reasoning.

### Additional Verification (Architecture-Specific)
- What happens under 10x load or data volume?
- What if a dependency fails or is unavailable?
- What is the rollback strategy if this change breaks production?

### Alternative Patterns
- Flag over-engineering or unnecessary abstraction layers.
- Suggest simpler or proven patterns from the existing codebase.

## Output Format

Matches `codex_review_schema.json`. Key enum values:
- `verdict`: `approved` | `needs_revision` | `rejected`
- `severity`: `critical` | `major` | `minor` | `suggestion`
- `review_type`: `plan_validation` (for architecture validation)

```
### Validation: approved|needs_revision|rejected
- Area: description
- Detail: specifics
- Recommendation: action (if needs_revision or rejected)
```

## Few-shot Example

```
BAD (RIBs 위반):
// ContentRouter.swift:30
func routeToPlayer() {
    let vc = PlayerViewController()
    vc.fetchData()   // Interactor 역할을 Router가 수행 — 레이어 위반
    viewController.push(vc)
}

GOOD:
// ContentRouter.swift:30
func routeToPlayer() {
    // Router는 네비게이션만 담당. 데이터 로딩은 PlayerInteractor 책임.
    attachChild(playerBuilder.build(withListener: interactable))
}
```

## Code Transformation Validation (패턴 변환 포함 계획 시)

계획에 비동기 패턴 변환(PromiseKit→async, callback→async 등)이 포함될 때:
- 원본 API 스레드 특성 확인 (PromiseKit .done = main queue, RxSwift observe(on:) 등)
- After 패턴이 스레드/에러/추상화 수준에서 원본과 동등한지 검증
- Swift: `defer { await }` 컴파일 에러, enum catch `==` 비교 금지 (`if case` 필수)
- After 줄 수 > Before 2배 → 추상화 부재 경고

## When CLAUDE.md Is Absent
Apply general software architecture best practices: separation of concerns,
dependency inversion, single responsibility, and KISS principle for validation.
