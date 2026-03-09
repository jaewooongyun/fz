---
name: fz-review
description: >-
  자기 코드 리뷰 + 품질 보증 스킬. 3중 검증(Claude+Codex+sc:analyze)과 역방향 검증.
  Use when reviewing YOUR OWN code changes after implementation, validating quality, or running verification cycles.
  Do NOT use for reviewing teammate's PR (use fz-peer-review).
user-invocable: true
argument-hint: "[리뷰 대상 설명]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__get_symbols_overview,
  mcp__serena__write_memory,
  mcp__serena__read_memory,
  mcp__serena__edit_memory,
  mcp__serena__list_memories,
  mcp__sequential-thinking__sequentialthinking,
  mcp__lsp__diagnostics_delta,
  mcp__lsp__references,
  Read, Grep, Glob
team-agents:
  primary: review-arch
  supporting: [review-quality, review-counter, memory-curator]
composable: true
provides: [review-results]
needs: [code-changes]
intent-triggers:
  - "리뷰|검증|품질|검토"
  - "review|validate|quality|check"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-review - 리뷰 + 품질 보증 스킬

> **행동 원칙**: 3중 검증(Claude+Codex+sc:analyze)으로 코드 품질을 확보하고, Codex 역방향 검증으로 피드백 반영을 정량화한다. 검증 결과가 기준 미달이면 반복 개선한다.

## 개요

> Phase 5 (3중 검증: Serena // /fz-codex review // /sc:analyze) → Phase 5.5 (/fz-codex validate) → Rate >= 80%? → Phase 7 완료 | Phase 6 (개선) → 반복

- 3중 검증: Claude(Serena) + Codex(/fz-codex) + SuperClaude(sc:analyze)
- 역방향 검증: Codex가 Claude의 수정 사항을 검증
- Reflection Rate 정량화 (>= 80% 통과)
- /ralph-loop 한도 후 사용자 에스컬레이션

## 사용 시점

```bash
/fz-review "구현한 코드 리뷰해줘"
/fz-review "Codex 피드백 반영했어, 재검증해줘"
/fz-review "현재 Reflection Rate 얼마야?"
/fz-review "Gate 5 통과 확인해줘"
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/build.md | 빌드 검증 |
| modules/execution-modes.md | LOOP + SIMPLIFY 실행 모드 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |

## Plugin 참조 (SwiftUI + Swift Concurrency)

> 참조: `modules/plugin-refs.md` — SwiftUI Expert(리뷰 시) + Swift Concurrency(리뷰 시) 섹션
> diff에 `@MainActor|actor|async|@Observable` 패턴 감지 시 해당 플러그인 참조

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| Phase 5 | `/sc:analyze` | 코드 품질/보안/성능 분석 |
| Phase 5 | `→ /fz-codex review` | Codex 코드 리뷰 (독립 스킬) |
| Phase 5 | `/sc:spec-panel` | 스펙 부합 전문가 패널 리뷰 (새 모듈 변경 시) |
| Phase 5.5 | `→ /fz-codex validate` | 역검증 (독립 스킬) |
| Phase 6 | `/sc:improve` | 발견 이슈 기반 코드 개선 |
| Phase 6 | `/sc:cleanup` | dead code, unused import 정리 (삭제 권고 이슈 시) |
| Phase 6 | `/sc:reflect` | 수정 후 자체 검증 |
| Phase 7 | `/sc:test` | 최종 테스트 검증 |

## 팀 에이전트 모드 (Review Squad)

> 팀 모드 규칙은 `.claude/modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("review-{feature}")
├── Lead (Opus): 4중 검증 오케스트레이션 + 수정 수행
├── review-arch (★Opus): 아키텍처 리뷰 — .claude/agents/review-arch.md
├── review-quality (Sonnet): 코드 품질 리뷰 — .claude/agents/review-quality.md
├── review-counter (Sonnet): DA 패스 — review-arch/review-quality "OK" 판정에 반론 [선택]
├── memory-curator (Sonnet): 관련 교훈 발굴 + review-arch에 직접 전달 [선택적: --deep 또는 복잡도 4+]
└── Codex CLI: 역검증 (Lead가 /fz-codex validate 실행)
```

> review-counter는 선택적 DA 패스. review-arch/review-quality 초안 완성 후 SendMessage로 결과 전달 → review-counter가 "OK" 판정 영역을 집중 반론 → 합의 후 Lead 보고.

> ASD 폴더 활성 시: `{WORK_DIR}/review/review-team.md`에 live review 핵심 통신을 기록한다.

### 통신 패턴: Live Review (Peer-to-Peer)

리뷰어들이 **분석하면서 서로 발견을 직접 공유**하고 교차 검증하는 패턴.
Lead를 거치지 않고 직접 SendMessage로 대화한다.

```
Round 1: review-arch ↔ review-quality 실시간 발견 공유
Round 2: 상호 피드백 → 수정
Round 3: 합의 → Lead 보고
```

**핵심**: 한쪽의 발견이 다른 쪽의 분석을 **실시간 안내**. 서로의 발견이 연쇄적으로 더 깊은 이슈를 드러냄.

### MCP 제약 + Intent Context

```
MCP 제약: review-arch/review-quality는 serena, context7만 접근 가능.
Atlassian/LSP 정보 필요 시 Lead가 조회 후 SendMessage로 전달.

Intent Context 전달 (필수):
에이전트에게 diff만 전달하지 마세요. 반드시 "변경 의도 요약"을 함께 전달합니다.

포맷:
---
[변경 의도]: {새 심볼}이 {기존 심볼}을 대체. {기존 심볼}의 사용처가 0이면 삭제 대상.
[대체 대상]: {기존 심볼 이름}, {기존 파일}
---
```

---

### (선택) Pre-review /simplify

- /simplify 사전 정리로 일반 품질 이슈 사전 해소 (참조: modules/execution-modes.md)

---

### ASD 컨텍스트 로딩 (ASD 폴더 활성 시)

- `{WORK_DIR}/code/progress.md` 읽기 → 구현 진행 상태 복원
- `{WORK_DIR}/plan/plan-final.md` 읽기 → 계획 대비 검증

---

## Phase 4.5: Requirements Alignment (요구사항 부합)

세션 task/plan과 diff를 대조하여 요구사항 부합 여부를 확인합니다.

### 절차

```
1. 요구사항 목록화 → 체크리스트
   - 세션 내 task/plan에서 구현 대상 추출
   - 커밋 메시지에서 의도 추출
2. diff에서 각 요구사항 구현 여부 확인
   - Serena find_symbol → 신규 심볼이 요구사항에 매핑되는지
3. 미구현/부분구현 → 이슈 (category: requirements_gap)
4. 범위 외 변경 → 이슈 (category: scope_creep)
```

### 체크리스트

- [ ] 세션 task/plan의 모든 요구사항이 구현되었는가?
- [ ] 커밋 메시지에 명시된 변경이 실제 diff에 반영되었는가?
- [ ] 범위 외 변경 (scope creep)이 포함되어 있지 않은가?

---

## Phase 5: Cross-Review (3중 검증)

Claude(Serena), Codex, SuperClaude 3중 검증으로 코드 품질을 확보합니다.

> **프로젝트 규칙**: CLAUDE.md `## Guidelines` 섹션을 따른다.

### 병렬 검증 전략

```
Phase 5: Cross-Review
├─ [병렬 1] Claude + Serena: 참조 무결성 검증
├─ [병렬 2] → /fz-codex review: Codex 코드 리뷰
└─ [병렬 3] /sc:analyze: 정적 분석

    ↓ 모든 결과 수집

Results Merge & Dedup → Issue Tracker 통합
```

### 검증 1: Claude + Serena (참조 무결성)

```
mcp__serena__find_referencing_symbols → 변경된 심볼의 모든 참조 확인
mcp__serena__search_for_pattern → 변경 후 패턴 일관성
mcp__sequential-thinking__sequentialthinking → diff↔요구사항 매핑 분석 (요구사항별 충족 여부 단계별 검증)
```

### ⛔ 검증 2: Codex 코드 리뷰 (필수 — 생략 금지)

```bash
# 독립 스킬로 위임
/fz-codex review "코드 리뷰"
```

fz-codex가 수행하는 작업:
- Codex CLI에 변경 심볼 + diff 전송 (effort: high)
- JSON 응답 파싱 → Issue Tracker 자동 기록
- 이슈 요약 반환

### 검증 3: SuperClaude 정적 분석

```
/sc:analyze → 코드 품질, 보안, 성능, 아키텍처 종합 분석
```

### 검증 4: Refactoring Completeness (리팩토링 완성도)

diff 기반 검증만으로는 **"변경되지 않았지만 삭제/수정되어야 할 코드"**를 놓칩니다.
이 검증은 diff **밖**으로 시야를 확장하여 리팩토링 의도가 완전히 달성되었는지 확인합니다.

```
절차:
1. diff에서 새 심볼 식별 → 대체 의도 추론
2. 대체 대상의 사용처 역추적 (Serena find_referencing_symbols)
3. deprecated 코드 검색 (search_for_pattern)
4. 사용처 0인 deprecated → "삭제 권고" 이슈

체크리스트:
- [ ] 이전 심볼 사용처 0 → 삭제 대상?
- [ ] deprecated 코드 중 사용처 0?
- [ ] 삭제 대상의 의존 코드도 정리?
```

> **왜 필요한가**: 3중 리뷰가 모두 diff 기반이므로, "안 바뀐 dead code"는 전부 놓침.
> 이 검증이 유일하게 diff **밖**을 보는 단계. 리팩토링 작업에서 특히 중요.

### 검증 4-D: Constraint Matrix Compliance (제약 매트릭스 부합, 조건부)

/fz-discover의 `constraint-matrix`가 있는 경우, 구현이 발견된 제약을 실제로 준수하는지 검증합니다.

```
전제조건: 세션 내 /fz-discover 산출물(제약 매트릭스 + 결정 근거)이 존재

절차:
1. 제약 매트릭스에서 각 제약 추출
2. diff에서 채택된 옵션의 구현이 각 제약을 만족하는지 확인
   - mcp__serena__find_symbol → 구현체가 제약을 준수하는 구조인지
   - Grep → 탈락된 옵션의 패턴이 코드에 없는지
3. 위반 발견 시 → "constraint_violation" 카테고리로 이슈 생성

체크리스트:
- [ ] 채택된 옵션이 모든 제약을 만족하는 방식으로 구현되었는가?
- [ ] 탈락된 옵션의 패턴이 코드에 남아있지 않은가?
- [ ] 결정 근거에 명시된 트레이드오프가 의도대로 수용되었는가?
```

> 이 검증은 /fz-discover → /fz-plan → /fz-code 파이프라인에서만 활성화.
> /fz-discover 없이 직접 코딩한 경우에는 생략.

### 검증 4-E: Module Boundary (접근 제어 검증)

모듈 경계에서의 access control이 설계 의도와 일치하는지 검증합니다.

```
절차:
1. diff에서 변경된 심볼의 access modifier 확인
   - public/open으로 노출된 심볼이 의도적인지 검증
   - mcp__serena__find_symbol → access level 확인
2. 변경 모듈의 public API surface 검사
   - 내부 구현 세부사항이 public으로 노출되지 않았는지
   - Grep(pattern="public (var|let|func)", path="변경 모듈")
3. 모듈 간 의존 방향 확인
   - 하위 모듈이 상위 모듈에 의존하지 않는지
   - mcp__serena__find_referencing_symbols → 역방향 참조 탐지

체크리스트:
- [ ] public API가 의도적으로 노출된 것인가? (internal이어야 할 심볼이 public이 아닌가?)
- [ ] 모듈 내부 구현 세부사항(proxy, internal state 등)이 외부에 노출되지 않았는가?
- [ ] 의존 방향이 아키텍처 규칙(상위→하위만)을 준수하는가?
```

### 검증 4-F: Anti-Pattern Enforcement (잔존 금지 패턴 검증)

Plan에 Anti-Pattern Constraints가 있는 경우, 리팩토링 후 코드베이스에 금지 패턴이 남아있지 않은지 검증합니다.

```
절차:
1. Plan의 Anti-Pattern Constraints 테이블에서 "검증 Grep 패턴" 추출
2. 각 패턴에 대해 전체 코드베이스 Grep 실행
3. 매칭 발견 시:
   - 위치 + 컨텍스트 기록
   - "enforcement_violation" 카테고리로 이슈 생성
   - severity: Critical (리팩토링 목표 무력화)
4. 모든 금지 패턴이 0 매칭이어야 통과

체크리스트:
- [ ] Anti-Pattern Constraints의 모든 금지 패턴이 코드베이스에서 0건인가?
- [ ] 금지 패턴의 변형(alias, 간접 참조 등)도 검사했는가?
```

### 검증 5: UI/UX Refactoring Safety

View 파일 변경 포함 시 추가 검증:

```
View 파일 패턴: *View.swift, *Screen.swift, *Cell.swift

검증 항목:
- SwiftUI View body 구조 변경 → 레이아웃 영향
- @State/@Binding 변경 → 데이터 흐름 무결성
- Listener/Delegate 변경 → 메모리 누수 패턴 (CLAUDE.md 금지 패턴)
- 권고: launch_app_sim + screenshot으로 UI 시각 검증
```

### 검증 6: Spec Panel 스펙 부합 (조건부)

새 모듈 생성이 포함된 변경사항에서만 실행:

```
/sc:spec-panel --mode critique --focus requirements|architecture
```

- 트리거: diff에 새 Router/Interactor/Builder 파일 포함 시
- 전문가 패널이 스펙 부합 여부, 아키텍처 결정의 타당성 리뷰
- 결과: Issue Tracker에 spec_concern 카테고리로 기록

### Gate 4: Review Passed
- [ ] 참조 무결성 확인? (Serena)
- [ ] ⛔ Codex 리뷰 통과? (Critical/Major 이슈 없음 — Codex 실행 자체가 필수)
- [ ] /sc:analyze 통과? (심각한 문제 없음)
- [ ] Constraint Matrix Compliance 통과? (제약 매트릭스 부합, /fz-discover 산출물 있을 때)
- [ ] Refactoring Completeness 통과? (deprecated dead code 없음)
- [ ] Module Boundary 통과? (access control이 의도와 일치)
- [ ] Anti-Pattern Enforcement 통과? (금지 패턴 0건, Plan에 Constraints 있을 때)
- [ ] UI/UX Safety 통과? (View 변경 시 시각 검증 권고)
- [ ] Spec Panel 통과? (새 모듈 시, 스펙 부합 확인)

---

## Phase 5.5: Feedback Verification (역방향 검증)

**Codex가 "내 피드백을 Claude가 제대로 반영했는지" 직접 검증합니다.**

### 절차

```bash
# 독립 스킬로 위임
/fz-codex validate "피드백 반영 검증"
```

fz-codex validate가 수행하는 작업:
- 이전 이슈 목록 + Claude 수정 내용 → Codex에 전송
- 이슈별 해결 상태 검증 (resolved / partially_resolved / unresolved / regressed)
- Reflection Rate 계산
- Issue Tracker 상태 업데이트

### Gate 4.5: Feedback Verified
- [ ] Codex가 이전 이슈들의 해결 상태를 검증했는가?
- [ ] Feedback Reflection Rate >= 80%?
- [ ] 새로 발견된 Critical 이슈가 없는가?
- [ ] Regressed 이슈가 없는가?

### 판정 기준

| Reflection Rate | Verdict | 다음 단계 |
|-----------------|---------|----------|
| >= 80% | `pass` | Gate 5 통과 → Phase 7 완료 |
| 60% - 79% | `needs_work` | Phase 6 (재수정) |
| < 60% | `fail` | Phase 6 (재수정, 2회 후 에스컬레이션) |

---

## Phase 6: Iterative Improvement

Cross-Review에서 발견된 이슈를 수정하고 재검증합니다.

### 반복 조건

```
Reflection Rate >= 80%?
├─ YES → Gate 5 통과 (완료)
└─ NO → /ralph-loop 에스컬레이션 래더 적용 (참조: modules/execution-modes.md)
```

### 절차

1. **미해결 이슈 로드**: Issue Tracker에서 미해결 이슈 추출
2. **이슈 수정** (TEAM 모드: impl-correctness에게 위임):
   - SOLO: `mcp__serena__replace_symbol_body` → 심볼 단위 수정, `/sc:improve` → 복잡한 개선
   - TEAM: SendMessage(impl-correctness): "미해결 이슈 목록 + 수정 요청" → impl-correctness가 수정 후 Lead 보고
3. **빌드 재검증**: 참조 `modules/build.md` — 빌드 검증 절차
4. **Issue Tracker 상태 업데이트**: addressed로 변경
5. **Phase 5.5로 돌아가 재검증**: `/fz-codex validate`

### 사용자 에스컬레이션 (/ralph-loop 한도 후)

```markdown
반복 개선 한도 도달

**현재 상태**:
- 총 이슈: N개, 해결: X개, 미해결: Y개
- 최종 Reflection Rate: ZZ%

**선택지**:
1. 미해결 이슈를 DEFERRED로 마킹하고 완료
2. 추가 N회 반복 시도
3. 수동 해결 후 재검증
4. 작업 중단
```

### Gate 5: Final Quality
- [ ] 모든 Critical 이슈 수정 완료?
- [ ] 최종 빌드 성공? (modules/build.md 절차)
- [ ] Reflection Rate >= 80%?
- [ ] 최대 반복 횟수 미초과?
- [ ] ⛔ 아티팩트 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)

---

## Phase 7: Completion (완료 처리)

Gate 5 통과 후 작업을 최종 완료합니다.

### 절차

1. **잔여 작업 확인**:
   - `mcp__sequential-thinking__sequentialthinking` → 완료 체크리스트 단계별 검토 (Gate 통과 여부, 미해결 이슈, 범위 외 변경)

2. **Final Issue Report 생성**: 참조 `modules/session.md` — Final Report 섹션

3. **세션 결과 저장**:
   - `mcp__serena__write_memory` → 작업 요약, 결정사항, 변경 심볼

3.5. **아티팩트 기록** (ASD 폴더 활성 시):
   - `{WORK_DIR}/review/self-review.md` — 리뷰 결과 + 발견 이슈 + 권고사항
   - `{WORK_DIR}/index.md`에 항목 추가

4. **Git 연계** (사용자 확인 후):
   - `/fz-commit` → 커밋 생성
   - `/fz-pr` → PR 생성

### 완료 보고 형식

```markdown
작업 완료

**세션**: SESSION-YYYYMMDD_HHMMSS
**총 이슈**: N개 발견 → X개 해결, Y개 보류
**최종 Reflection Rate**: ZZ%
**반복 횟수**: N회

**변경 파일**:
- file1.swift (심볼: A, B, C)

**다음 단계**:
- /fz-commit으로 커밋 생성
- /fz-pr로 PR 생성
```

---

## Few-shot 예시

```
BAD: 리뷰 완료. 문제 없음. → 근거 없음, Rate 없음
GOOD: 발견 이슈 N개 + Reflection Rate: X/Y (ZZ%) + Codex 교차 검증 결과
```

## Boundaries

3중 검증을 모두 완료한 후 판정한다. Phase 5.5 역방향 검증을 포함한다.

**Will**:
- 3중 검증 (Claude + Codex + sc:analyze)
- 역방향 검증 (Codex가 피드백 반영 확인)
- Reflection Rate 정량화 및 반복 개선
- 완료 처리 (Final Report + 세션 저장)

**Will Not**:
- 대규모 코드 구현 (→ /fz-code)
- Codex 직접 호출 (→ /fz-codex)
- 계획 수립 (→ /fz-plan)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| fz-codex 통신 실패 | 재시도 1회 → 실패 사실 기록 후 /sc:analyze 폴백 | Claude 자체 판단 |
| Rate < 60% 3회 | 사용자 에스컬레이션 | DEFERRED 마킹 |
| Issue Tracker 손상 | 새 세션 시작 | 수동 관리 |

## Completion → Next

Gate 5 통과 후: `/fz-commit` → `/fz-pr`
