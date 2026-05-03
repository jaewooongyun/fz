---
name: fz-plan
description: >-
  계획 수립 + 영향 범위 분석 + 설계. 요구사항 분해와 Serena 기반 코드베이스 탐색.
  예: 계획 세워줘, 설계해줘, 아키텍처 잡아줘, 요구사항 분석
user-invocable: true
argument-hint: "[기능/요구사항 설명]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__find_file,
  mcp__serena__activate_project,
  mcp__serena__read_memory,
  mcp__serena__write_memory,
  mcp__serena__edit_memory,
  mcp__serena__list_memories,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  mcp__sequential-thinking__sequentialthinking,
  mcp__atlassian__get-issue,
  mcp__atlassian__search-issues,
  Read, Grep, Glob
team-agents:
  primary: plan-structure
  supporting: [plan-impact, plan-edge-case, review-arch, review-direction, memory-curator]
composable: true
provides: [planning, architecture-analysis]
needs: [none]
intent-triggers:
  - "계획|설계|아키텍처|요구사항"
  - "plan|design|architect|requirement"
  - "리팩토링|치환|흡수|이전|migration|refactor"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-plan - 계획 + 설계 스킬

> **행동 원칙**: 요구사항을 구조적으로 분해하고, 코드베이스 영향 분석을 통해 정확한 구현 계획을 수립한다.

## 개요

> ⛔ Phase 0 (ASD Pre-flight) → Phase 0b (Context) → Phase 0c (Constraint Probe Pre-flight) → Phase 0.5 (Direction Challenge) → Phase 0.7 (Sprint Contract, TEAM 5+ Step) → Phase 1 (Deep Planning) → Phase 2 (Validation) ↔ Phase 3 (Feedback) → Gate 2 → /fz-code
> 루프 프리미티브: Plan-Execute + Evaluator-Optimizer (H6, Inside the Scaffold)

요구사항 구조 분해 + 영향 범위 분석. Serena 심볼 도구 기반 정밀 탐색.

```bash
/fz-plan "새 기능 계획해줘"        /fz-plan "피드백 반영해서 수정해줘"
/fz-plan "아키텍처를 더 상세하게"   /fz-plan "Gate 2 통과 확인해줘"
```

## Prerequisites

- TEAM 모드 사용 시 환경 변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정 필수 (미설정 시 TeamCreate 실패)
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
| modules/patterns/collaborative.md | Phase 0.5 Collaborative Design (review-direction → plan-structure) (UC-11, v4.7.1) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/context-artifacts.md | ASD 폴더 기반 compact recovery + 비ASD Serena checkpoint |
| modules/rtm.md | Requirements Traceability Matrix — plan이 생성, code가 갱신, review가 검증 |
| modules/code-transform-validation.md | 코드 변환 동등성 — Transformation Spec + 검증 체크리스트 (패턴 변환 시) |
| modules/uncertainty-verification.md | 기술적 주장 → Default-Deny 검증 (하네스 원칙, Transformation Spec Pilot) |
| modules/scope-challenge.md | Phase 3 Codex 이슈 scope_disposition 분류 + Lead 독립 판정 (additive 자동 번역 차단) |
| modules/promotion-ledger.md | P1/P2 조치 eligible session 관측 기록 (학습 승격 금지) |

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| Phase 1 | `/sc:design` | 아키텍처 설계, API 설계 |
| Phase 1 | `/sc:analyze` | 기존 코드 분석, 영향 범위 |
| Phase 1 | `/sc:brainstorm` | 요구사항 탐색 (복잡한 경우) |
| Phase 1 | `/sc:research` | 외부 기술/라이브러리 조사 |
| Phase 1 | `/sc:workflow` | PRD → 구현 워크플로우 자동 생성 (5+ Step 시) |
| Phase 1 | `/sc:spec-panel` | 아키텍처 스펙 전문가 패널 리뷰 (새 모듈 시, --deep 시) |
| Phase 2 | 검증 도구 | 계획 검증 (독립 스킬) |
| Phase 2 | `/sc:estimate` | 공수 추정 (복잡도 4+ 시, 조건부) |
| Phase 3 | `/sc:reflect` | 피드백 반영 후 자체 검증 |

## Plugin 참조 (Swift Concurrency)
> 참조: `modules/plugin-refs.md` — Swift Concurrency(계획 시) 섹션
> **iOS 16 minimum target 제약**: CLAUDE.md `## Plugins` 참조. 계획에 iOS 17+ API (`@Observable`, `@Bindable`, onChange new signature) 사용 명시 시 `#available` 가드 step 포함 의무.
> **availability 사전 결정**: SwiftUI State 설계 (iOS 16: `ObservableObject + @StateObject` / iOS 17+: `@Observable + @State`) → plan에 `#available` 분기 명시

## 팀 에이전트 모드

> 팀 모드 규칙은 `modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("plan-{feature}")
├── Lead (Opus): 오케스트레이션 + 외부 모델 실행 + 최종 합성
├── plan-structure (★Opus): 설계 + 분해 + 문서화 (Primary Worker)
├── plan-impact (Sonnet): 영향 범위 전담 — Exhaustive Impact Scan (a~g)
├── plan-edge-case (Sonnet): 엣지 케이스 + 실패 시나리오 발굴
├── review-arch (Sonnet): 아키텍처 패턴 검증 (RIBs + Clean Architecture)
├── review-direction (Sonnet): 방향성 비판 + 대안 제시 (Phase 0.5)
├── memory-curator (Sonnet): 관련 교훈 발굴
├── Codex verify (Lead 실행, GPT-5.5): 독립 계획 검증
└── Codex adversarial (Lead 실행, GPT-5.5): Devil's Advocate [--deep 시]
```

### Round 0.5 → Round 1 Sequential Operating Contract (UC-6 + ISSUE-016, v4.8.0)

> Phase 0.5 review-direction(opus) Round 0.5 완료 후에만 Phase 1 plan-structure(opus) Round 1 시작.
> 동시 opus ≤ 2 governance 보장 (review-direction + Lead = 2 → 종료 후 plan-structure + Lead = 2).

```
# Phase 0.5 (Round 0.5 — sequential)
TeamCreate(name="plan-{feature}-round0.5")
Agent(name="review-direction", team_name="plan-{feature}-round0.5", model="opus")
# ... Round 0.5 진행 (direction-challenge 판정)
SendMessage(to="review-direction", content="shutdown_request")
# 종료 확인 (process state polling)
TeamDelete("plan-{feature}-round0.5")

# Phase 1 (Round 1 — sequential, only after Round 0.5 종료 확인)
TeamCreate(name="plan-{feature}-round1")
Agent(name="plan-structure", team_name="plan-{feature}-round1", model="opus")
# ... Round 1 진행 (collaborative design)
```

**Verification**: `grep -A5 "Round 0.5.*Sequential" skills/fz-plan/SKILL.md` → 1건 + grep `model="opus"` (review-direction + plan-structure 각각 1건 이상) + grep `shutdown_request` 1건.

**6개 차별화된 렌즈** (같은 질문 금지 — ICLR 2025 근거):

| 에이전트 | 렌즈 | 핵심 질문 |
|---------|------|----------|
| plan-structure | 설계 + 분해 | "어떻게 나누고 만들 것인가?" |
| plan-impact | 영향 범위 | "이 변경이 어디까지 퍼지는가?" |
| review-arch | 아키텍처 일관성 | "기존 패턴/규칙과 맞는가?" |
| review-direction | 방향성 도전 | "근본적으로 다른 접근은?" |
| Codex verify | 독립 검증 | "이 계획에 빠진 것은?" |
| Codex adversarial | Devil's Advocate | "이 계획이 실패할 가장 큰 위험은?" |

> ASD 폴더 활성 시: `{WORK_DIR}/plan/plan-team.md`에 direction-challenge + collaborative design 핵심 통신을 기록한다.

### 통신 패턴: Parallel Analysis + Cross-Feedback

3개 Claude 에이전트가 **다른 렌즈로 병렬 분석** 후 교차 피드백. Lead는 Codex를 실행하여 이종 검증 확보.

```
[Round 1 — 병렬] plan-structure: 분해+설계 / plan-impact: Impact Scan(a~g) / review-arch: 패턴 매칭 / Lead: Codex verify
[Round 2 — 교차] plan-impact→structure: 영향+의존+dead / review-arch→structure: 위반+대안 / Lead→structure: GPT이슈 / structure: 통합수정
[Round 3 — 보고] structure→Lead: 최종계획+합의표 / Lead: 6렌즈 통합
```

> plan-structure 에이전트가 이 스킬의 워크플로우를 활용합니다.

---

## ⛔ Phase 0: ASD Pre-flight
> 참조: `modules/context-artifacts.md` → "Work Dir Resolution" 섹션. **Phase 0b 전에 반드시 실행.**

1. 인자에서 `ASD-\d+` 패턴 추출
2. 패턴 있으면 → `{CWD}/ASD-xxxx/` 폴더 + index.md 생성 (없으면) + WORK_DIR 설정
3. 패턴 없으면 → 브랜치명 확인 → 없으면 AskUserQuestion(저장 여부) → 예: `{CWD}/NOTASK-{YYYYMMDD}/` + index.md 생성 / 아니오: Serena fallback

### Gate 0: Work Dir Ready
- [ ] ⛔ ASD 패턴 또는 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD / NOTASK / Serena fallback)
- [ ] index.md 존재 확인 완료? (없으면 생성)

---

## Phase 0b: Context Loading
### 절차

1. **세션 감지**: 참조 `modules/session.md`
2. **이전 세션 복원**:
   - `mcp__serena__list_memories` → 관련 이전 세션 검색
   - `mcp__serena__read_memory` → 결정사항, 잔여 이슈 로드
3. **프로젝트 활성화**:
   - `mcp__serena__activate_project` → LSP 서버 활성화
4. **대상 모듈 심볼 파악**:
   - `mcp__serena__get_symbols_overview` → 작업 대상 파일 심볼 구조
   - `mcp__serena__find_symbol` → 컴포넌트 탐색

5. **이전 Discover 결과 로드** (ASD 폴더 활성 시):
   - `{WORK_DIR}/discover/discover-journal.md` 읽기 → Landscape Map + Trade-off Table + Open Questions 복원
   - `{WORK_DIR}/discover/discover-plan.md` 읽기 → mid-pipeline discover 결과 (있으면)
   - **⛔ discover 결과는 "전제"가 아닌 "참고"**: plan은 discover의 경로 중 하나를 선택하거나, 새 경로를 설계할 수 있음
   - 🔒불변 조건만 plan의 제약으로 채택. 🔓가변 조건은 비용 비교 대상으로만 활용
   - Open Questions는 plan Phase 1에서 추가 탐색 대상
   - ⛔ **Scope Expansion**: discover 변경 대상의 상위 모듈/프로토콜에서 `get_symbols_overview` → 놓친 형제 타입/간접 소비자를 탐색 범위에 추가

### Gate 0b: Context Ready
- [ ] 프로젝트 활성화 완료?
- [ ] 대상 심볼 구조 파악?
- [ ] 이전 컨텍스트 로드? (해당 시)

---

## Phase 0c: Constraint Probe Pre-flight (31차 방어)

> Plan 핵심 차원이 primitive(CLI flag / config key / value enum / env precondition)에 의존하면 추측 위에 작성하지 않는다. 실측으로 가정 검증 후 차원 포함. 참조: `feedback_plan_before_probe.md`.

발동: 외부 primitive 의존 시 필수. 코드베이스 내부 패턴만 의존하면 스킵.

### 절차

1. **가정 추출**: 요구사항/discover 결과에서 primitive 의존 가정 식별
   - **가정의 3 axes 점검** (32차 방어 — Probe Coverage Gap):
     - (a) **존재 가정**: primitive가 작동하는가? (existence)
     - (b) **권한/경계 가정**: 호출 측 SKILL.md `allowed-tools` / `Bash(*)` 패턴이 호출 허용? (boundary)
     - (c) **결과 contract 가정**: 결과 형식/verdict가 호출자 해석과 일치? (contract)
   - 3 axes 모두 점검. 어느 하나라도 미검증이면 차원에서 제외 또는 explicit assumption tag.
2. **검증 분류** (각 가정 × 3 axes 별):
   - 이미 verified → `[verified: source]` 태그 보유 (코드/문서/명령어 출력)
   - 미검증 → `[미검증: 이유]` 태그 + Plan 차원에서 제외
   - probe 필요 → `/fz-discover` Phase 1.5 (Constraint Probe) 호출
   - **Codex Micro-Eval Assist (optional)**: 핵심 가정 + `[verified: source]` 부재 + primitive/contract 확인 비용 높음 시 → `/fz-codex micro-eval "이 가정 검증"` (effort=medium, 1-shot). Lead 판단으로 호출, 자동 발동 ❌ — 새 Phase/Gate 신설 ❌ (33차 default = action 정합).
3. **probe 결과 통합**: discover 산출물에서 3 axes 모두 verified 가정만 Plan 차원에 포함

### Gate 0c: Constraints Verified for Plan
- [ ] primitive 의존 가정 모두 식별?
- [ ] 각 가정의 **3 axes** (존재 / 권한·경계 / 결과 contract) 모두 분류 완료? (32차 방어)
- [ ] 미검증 axis는 Plan 차원에서 제외 또는 explicit assumption tag?
- [ ] probe 필요 시 `/fz-discover` 선행 완료?
- 미통과 시 → ⛔ Plan 작성 차단

---

## Phase 0.5: Direction Challenge

> **Default = action with proportional verification** (참조: `modules/lead-action-default.md`). verification escalation은 명시적 risk signal 발생 시에만.

### 발동 조건

| 조건 | Direction Challenge | 근거 |
|------|:------------------:|------|
| TEAM 모드 (plan-to-code, plan-only) | **필수** | review-direction 에이전트 활용 |
| SOLO 모드 + 새로운 아키텍처 결정 | **필수** | Lead가 직접 6관점 검토 |
| discover 결과에 명확한 방향 존재 | **스킵 가능** | 이미 제약 기반 방향이 결정됨 |
| 단순 수정 (기존 패턴 따르기) | **스킵** | 방향성 검토가 과잉 |

### 절차

1. **요구사항 + 현재 아키텍처 대조**:
   - `mcp__serena__search_for_pattern` → 기존 유사 구현 탐색
   - `mcp__serena__get_symbols_overview` → 대상 영역 구조 파악
   - CLAUDE.md `## Architecture` 기준으로 접근 방향 평가

2. **6개 관점 비판적 검토** (TEAM: review-direction, SOLO: Lead 직접):
   - Structural Fit: 현재 구조에 자연스러운가?
   - Alternative Paths: 근본적으로 다른 접근은? (**대안 최소 2개**)
   - Extensibility: N배 확장 시 유지 가능한가?
   - Existing Pattern Reuse: 기존 패턴을 재활용할 수 있는가?
   - Maintenance Cost: 장기 유지보수 비용은 합리적인가?
   - Over-Engineering Risk: 현재 요구 대비 과하지 않은가?

3. **방향 판정**:
   - PROCEED → Phase 1 진입
   - RECONSIDER → 대안 비교표 + 사용자 확인 후 진입
   - REDIRECT → 대안 강력 권고 + 사용자 확인 필수

4. **⛔ 방향 판정 기록** (항상):
   - ASD 활성: `{WORK_DIR}/plan/direction-challenge.md`에 판정 결과 + 대안 비교 기록
   - 비ASD: `write_memory("fz:checkpoint:plan-direction", "판정: {PROCEED/RECONSIDER/REDIRECT}. 대안: {요약}. 선택근거: {1줄}")`
   형식 참조: `modules/context-artifacts.md`

### Gate 0.5: Direction Validated
- [ ] 6개 관점 검토 완료?
- [ ] 대안 최소 2개 제시?
- [ ] 방향 판정 (PROCEED/RECONSIDER/REDIRECT)?
- [ ] RECONSIDER/REDIRECT 시 사용자 확인?

---

## Phase 0.7: Sprint Contract (T2-B, TEAM mode)

> 발동: **TEAM mode + (5+ Step Plan 또는 Cross-skill 변경)**. 단순 수정/탐색 스킵.

Codex가 구현 시작 **전** "성공 기준" Sprint Contract 작성 → Claude 동의/수정 → Phase 1 진입. 사후 수정 비용 감소.

- 절차: `modules/sprint-contract.md` §절차 (4-step)
- Schema: `modules/sprint-contract.md` §Schema (yaml: success_criteria + anti_criteria + scope_boundary)
- Lead Decision: **agree** → Phase 1 / **modify** → Codex re-verify 1회 (한도) / **reject** → Phase 0.5 재진입

### Gate 0.7: Sprint Contract Agreed

- [ ] Codex Sprint Contract 작성 완료? (`sprint-contract-codex.md` 또는 `fz:checkpoint:sprint-contract`)
- [ ] 모든 SC가 measurable + binary 판정 가능?
- [ ] anti_criteria 명시? (제거/리팩토링 작업 시)
- [ ] Lead 동의 (agree) 또는 modify 후 합의?
- 미통과 시 → ⛔ Phase 1 작성 차단

> Phase 0.7 출처: Anthropic Harness Engineering 패턴 B (2026-03) + Plan v3.1.3 §T2-B. 학술 근거: `modules/cross-validation.md` §이론 근거 (Generator≠Evaluator + MoA collaborativeness).

---

## Phase 1: Deep Planning

> **프로젝트 규칙**: CLAUDE.md `## Architecture` 섹션을 따른다.
> **본문**: `modules/plan-deep-planning.md` 참조 (Level 3) — 9 절차 (요구사항 분해, Exhaustive Impact Scan a-f, API 확인, Clean Architecture, SuperClaude, 설계 스트레스 테스트 Q1-Q6, RTM, 계획 출력, Transformation Spec, 계획 파일 기록).

### 절차 요약

1. 요구사항 구조 분해 (discover 산출물 활용)
2. 코드베이스 영향 분석 + ⛔ Exhaustive Impact Scan a-f (텍스트 검색/런타임 도달성/사이드이펙트/Dead code/소비자 스캔/Symbol Inventory)
3. API/라이브러리 문서 확인 (Context7)
4. Clean Architecture 원칙 확인
5a. SuperClaude 연계 (sc: 명령어)
5b. 설계 스트레스 테스트 Q1-Q6 (Evaluator-Optimizer 패턴, max 2회 반복)
6. ⛔ RTM 작성
7. 구조화된 계획 출력 (리스크 매트릭스 + Anti-Pattern Constraints + Implication Register)
8. ⛔ Transformation Spec 작성 (패턴 변환 Step 시)
9. ⛔ 계획 파일 기록 (compact recovery)

> 각 절차 상세는 `modules/plan-deep-planning.md` 참조. 트리밍 비저하 원칙(single source: `guides/prompt-optimization.md` §1 보충 3a)으로 Gate 1 + Why(H1)는 본 SKILL에 보존.

### Gate 1: Plan Ready
> **Why (H1)**: 영향 범위가 불완전하면 구현 시 예상 외 파일을 건드리게 되고, 리뷰에서도 범위 밖 변경을 놓친다.
- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 영향 범위 분석 완료?
- [ ] ⛔ Exhaustive Impact Scan 4단계 수행 완료? (반성 5차)
  - [ ] 텍스트 전수 검색(Grep)으로 심볼 기반 결과와 대조했는가?
        Evidence: Grep("{타입명}") → {N}건 vs find_referencing_symbols → {M}건
  - [ ] 각 진입점의 런타임 도달성을 검증했는가? (latent 표기 포함)
  - [ ] 기존 액션 패턴의 사이드이펙트/순서 의존성을 분석했는가?
  - [ ] 관련 파일의 dead code를 감지했는가?
  - [ ] ⛔ 모듈화 작업이면 소비자 코드 품질 스캔(e단계)을 수행했는가?
  - [ ] ⛔ import 제거 작업이면 Symbol Inventory(f단계)를 수행했는가?
- [ ] API 문서 확인 완료? (새 API 사용 시)
- [ ] 기존 패턴과 일관성 확인?
- [ ] 구현 단계가 명확하게 정의?
- [ ] 설계 스트레스 테스트(Q1-Q6) 수행 완료?
- [ ] 소비자 영향이 식별되었으면 계획에 반영?
- [ ] 대안 패턴 최소 1개 제시?
- [ ] 리팩토링 작업이면 Anti-Pattern Constraints 작성?
- [ ] ⛔ 새 SPM 패키지 생성이면 Chore Step 포함? (.gitignore .build, Package.resolved, pbxproj 등록)
- [ ] ⛔ 모듈화 작업이면 Concern Classification 수행? (각 public type의 관심사가 모듈 책임에 부합)
- [ ] ⛔ 패턴 변환 Step에 Transformation Spec 작성? (원본 스레드/에러/추상화/언어 제약 확인)
- [ ] ⛔ Transformation Spec의 기술적 주장에 [verified: source] 태그가 있는가? (Default-Deny)
- [ ] ⛔ "실행 스레드"가 Zero-Exception 규칙을 준수하는가?
- [ ] ⛔ 요청 파라미터 키 목록이 원본과 일치하는가?
- [ ] ⛔ 계획 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)

> **Gate 증거 첨부** (H2 원칙 — self-check 보완): 결정론적 도구 출력이 있는 Gate 항목은
> `Evidence:` 행에 도구 결과 요약을 기록한다. self-check "완료?"보다 도구 출력이 신뢰할 수 있다.

---

## Phase 1.5: Swift Anti-Pattern Pre-block (Swift/iOS 프로젝트 한정)

> 발동: CLAUDE.md `## Architecture`가 Swift/iOS 지정 + Plan에 SwiftUI/Concurrency/패턴 변환 포함 시 필수. 비Swift/iOS는 스킵.
> 본문: `modules/swift-anti-pattern-preblock.md` 참조 (Level 3) — 3 원칙(P1 SwiftUI 결정 / P2 Concurrency isolation / P3 패턴 변환 보존) + 각 원칙 token + Few-shot.

### Gate 1.5: Swift Anti-Pattern Pre-block 통과
- [ ] Swift/iOS 프로젝트 + SwiftUI/Concurrency/패턴 변환 plan? (해당 시 `modules/swift-anti-pattern-preblock.md` Read 후 진입)
- [ ] P1 SwiftUI 결정 명시? (owner / availability / View 책임)
- [ ] P2 Concurrency isolation 범위 결정? (scope / 병렬화 / continuation 정당화)
- [ ] P3 패턴 변환 시 원본 동작 보존? (스레드 / defer-await / enum catch)
- 1건 미해결 → ⛔ Phase 2 차단

> 발동 시 행동: `modules/swift-anti-pattern-preblock.md` Read + `modules/plugin-refs.md` 역방향 트리거 섹션 강제 참조 + 3 원칙 점검표 통과 후 Phase 2 진입.

---

## Phase 2: Plan Validation
### 절차

```bash
# 계획 검증 실행
검증 도구로 계획 검증 위임
```

검증이 수행하는 작업:
- 계획 전송 (cross-model 검증, effort: high)
- 응답 파싱
- Issue Tracker에 이슈 자동 기록
- 이슈 요약 반환

3.5. **⛔ 검증 결과 기록** (항상):
   - ASD 활성: `{WORK_DIR}/plan/verify-result.md`에 verdict + 이슈 요약 기록
   - 비ASD: `write_memory("fz:checkpoint:plan-verify", "verdict: {approved/rejected}. 이슈: {N}개. Critical: {요약}")`

### Gate 2 전제조건
- 검증 verdict가 `approved` 또는 사용자 승인

---

## Phase 3: Feedback Integration
### 절차

1. **피드백 심화 분석**:
   - `mcp__sequential-thinking__sequentialthinking` → 이슈별 심각도 분류
     - **Critical**: 즉시 수정 필수
     - **Major**: 수정 권장
     - **Minor**: 선택적 수정

1b. **⛔ Scope Challenge (이슈당 필수)**: 각 Codex 이슈를 플랜에 반영 전 `modules/scope-challenge.md` Q-S1~S4 실행 → `scope_disposition` 분류. Lead는 Codex 결과를 **읽기 전** 독립 판정 후 비교 (Generator≠Evaluator).

2. **요구사항 일치 검증**:
   - `mcp__sequential-thinking__sequentialthinking` → 수정 전후 요구사항 부합도 단계별 비교
   - `/sc:reflect` → 자체 검증

3. **사용자 의사결정** (AskUserQuestion):
   - 수정 후 Phase 2 재검증
   - 현재 계획으로 구현 진행
   - 추가 논의

4. **⛔ 수정 계획 기록** (항상 — compact recovery 필수):
   - ASD 활성: `plan-v{N+1}.md` 생성 + 최종 승인 시 `plan-final.md` 복사 + `index.md` 업데이트
   - 비ASD: `write_memory("fz:checkpoint:plan-final", "최종 계획: Steps {N}개. 피드백 반영: {요약}. verdict: approved")`

5. **Refactoring Mode 감지 (P0-light)**: intent-triggers에 리팩토링/치환/흡수/migration 매칭 시 AskUserQuestion 1회 — "이 작업은 리팩토링 감지. refactoring-aware 분류(Q-S5 Appendix 활성)를 적용할까요?" 사용자 예 시 Q-S5 활성, 아니오 시 기존 flow.

### Gate 2: Validation Passed
- [ ] Critical 이슈 모두 해결?
- [ ] 사용자 승인 완료?
- [ ] 수정된 계획이 요구사항과 일치?

---

## Few-shot 예시

```
BAD (구조 분해 부족):
## 계획: 새 ContentDetail 화면 추가
Step 1: ContentDetailRIB 만들기
Step 2: API 연동
Step 3: UI 구현
→ 영향 분석 없음, Step이 막연

GOOD:
## 계획: 새 ContentDetail 화면 추가
### 영향 분석
- 변경: HomeInteractor (라우팅), HomeRouter (child 추가)
- 생성: ContentDetail{Builder,Router,Interactor,ViewController}
- 참조: ContentRepository (기존), ContentUseCase (기존)
### Steps
Step 1: ContentDetailBuilder 생성 (DI: ContentRepository, ImageCacheUseCase)
Step 2: HomeRouter에 ContentDetail attach/detach 추가
Step 3: ContentDetailInteractor → ContentUseCase → ContentDetailPresenter 데이터 흐름
Step 4: ContentDetailViewController SwiftUI 기반 UI
### 리스크 매트릭스
| Q1 다중성 | ContentDetail이 여러 진입점(Home/Search/MyPage)에서 호출 | listener 프로토콜 통일 필요 |
```

## Boundaries

**Will**: 요구사항 분해, 영향 분석, Serena 탐색, 구현 계획 출력, 계획 검증
**Will Not**: 코드 수정 (→ /fz-code), 빌드 실행 (→ /fz-code)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| Serena 연결 실패 | Grep + Glob 폴백 | 수동 탐색 |
| Context7 실패 | WebSearch 폴백 | 문서 직접 검색 |
| 검증 실패 | /sc:analyze 단독 검증 | Claude 자체 판단 |

## Completion → Next

Gate 2 통과 후:
```bash
/fz-code "검증된 계획대로 구현해줘"
```

아키텍처/모듈 구조 계획이면 다이어그램 시각화 제안:
```bash
/fz-excalidraw "방금 수립한 계획을 아키텍처 다이어그램으로 그려줘"
```
