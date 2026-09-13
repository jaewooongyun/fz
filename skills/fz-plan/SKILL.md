---
name: fz-plan
description: >-
  계획 수립 + 영향 범위 분석 + 설계. 요구사항 분해와 Serena 기반 코드베이스 탐색.
  예: 계획 세워줘, 설계해줘, 아키텍처 잡아줘, 요구사항 분석 (비사용: 접근 불명확 시 →fz-discover, 구현 →fz-code)
user-invocable: true
argument-hint: "[기능/요구사항 설명] [light]"
allowed-tools: >-
  mcp__plugin_fz_serena__find_symbol,
  mcp__plugin_fz_serena__get_symbols_overview,
  mcp__plugin_fz_serena__find_referencing_symbols,
  mcp__plugin_fz_serena__activate_project,
  mcp__plugin_fz_serena__read_memory,
  mcp__plugin_fz_serena__write_memory,
  mcp__plugin_fz_serena__edit_memory,
  mcp__plugin_fz_serena__list_memories,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  mcp__sequential-thinking__sequentialthinking,
  mcp__atlassian-jira__jira_get,
  Bash(grep *), Bash(cp *), Read, Grep, Glob, Workflow
metadata:
  provides: [planning, architecture-analysis]
  needs: [none]
  intent-triggers:
    - "계획|설계|아키텍처|요구사항"
    - "plan|design|architect|requirement"
    - "리팩토링|치환|흡수|이전|migration|refactor"
---

# /fz-plan - 계획 + 설계 스킬

> **행동 원칙**: 요구사항을 구조적으로 분해하고, 코드베이스 영향 분석을 통해 정확한 구현 계획을 수립한다.

## 개요

> ⛔ Phase 0 (Work Dir Pre-flight) → Phase 0b (Context) → Phase 0c (Constraint Probe Pre-flight) → Phase 0.5 (Direction Challenge) → Phase 0.7 (Sprint Contract, TEAM 5+ Step) → Phase 1 (Deep Planning) → Phase 2 (Validation) ↔ Phase 3 (Feedback) → Gate 2 → /fz-code
> 루프 프리미티브: Plan-Execute + Evaluator-Optimizer (H6, Inside the Scaffold)

요구사항 구조 분해 + 영향 범위 분석. Serena 심볼 도구 기반 정밀 탐색.

```bash
/fz-plan "새 기능 계획해줘"        /fz-plan "피드백 반영해서 수정해줘"
/fz-plan "아키텍처를 더 상세하게"   /fz-plan "Gate 2 통과 확인해줘"
```

## Prerequisites

- 팀 에이전트 모드(Workflow pilot)는 네이티브 Workflow 도구 가용 환경 필요 — 미가용 시 SOLO 계획 수립 폴백
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/patterns/ | 라운드 의미론의 **역사적 출처** (⛔ 폴백 실행 절차 아님 — 실패 복구는 `guides/skill-authoring.md` §12 실패 복구 사다리) |
| modules/patterns/collaborative.md | Phase 0.5 Collaborative Design (review-direction → plan-structure) (UC-11, v4.7.1) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/context-artifacts.md | 티켓 폴더 기반 compact recovery + 비-티켓 세션 Serena checkpoint |
| modules/rtm.md | Requirements Traceability Matrix — plan이 생성, code가 갱신, review가 검증 |
| modules/code-transform-validation.md | 코드 변환 동등성 — Transformation Spec + 검증 체크리스트 (패턴 변환 시) |
| modules/uncertainty-verification.md | 기술적 주장 → Default-Deny 검증 (하네스 원칙, Transformation Spec Pilot) |
| modules/scope-challenge.md | Phase 3 GPT 이슈 scope_disposition 분류 + Lead 독립 판정 (additive 자동 번역 차단) |
| modules/promotion-ledger.md | P1/P2 조치 eligible session 관측 기록 (학습 승격 금지) |
| modules/plan-direction-preflight.md | Phase 0c·0.5 절차 본문 (Phase 0c·0.5 진입 시 Read — 조건부) |

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| Phase 1 | `/sc:sc-design` | 아키텍처 설계, API 설계 |
| Phase 1 | `/sc:sc-analyze` | 기존 코드 분석, 영향 범위 |
| Phase 1 | `/sc:sc-brainstorm` | 요구사항 탐색 (복잡한 경우) |
| Phase 1 | `/sc:sc-research` | 외부 기술/라이브러리 조사 |
| Phase 1 | `/sc:sc-workflow` | PRD → 구현 워크플로우 자동 생성 (5+ Step 시) |
| Phase 1 | `/sc:sc-spec-panel` | 아키텍처 스펙 전문가 패널 리뷰 (새 모듈 시, --deep 시) |
| Phase 2 | `/fz-gpt verify` | 계획 검증 (독립 스킬 — GPT 교차 검증, `modules/fz-gpt-subcommands-core.md § verify`) |
| Phase 2 | `/sc:sc-estimate` | 공수 추정 (복잡도 4+ 시, 조건부) |
| Phase 3 | `/sc:sc-reflect` | 피드백 반영 후 자체 검증 |

## Plugin 참조 (Swift Concurrency)
> 참조: `modules/plugin-refs.md` — Swift Concurrency(계획 시) 섹션
> **iOS 16 minimum target 제약**: CLAUDE.md `## Plugins` 참조. 계획에 iOS 17+ API (`@Observable`, `@Bindable`, onChange new signature) 사용 명시 시 `#available` 가드 step 포함 의무.
> **availability 사전 결정**: SwiftUI State 설계 (iOS 16: `ObservableObject + @StateObject` / iOS 17+: `@Observable + @State`) → plan에 `#available` 분기 명시

## 팀 에이전트 모드

> 팀 모드 규칙 정본: `guides/skill-authoring.md` §12 (Workflow 규약 + 실패 복구 사다리 L1~L4). ⛔ `modules/team-core.md`는 역사적 출처 — 실행 절차로 참조하지 않는다

> TEAM(TeamCreate+SendMessage) 모드를 네이티브 Workflow 결정적 스크립트로 대체한 Wave 2 전환.
> Collaborative Design 패턴 canonical: `modules/patterns/collaborative.md` (보존 — 라운드 의미론의 역사적 출처).
> **스크립트: `workflows/plan-lean2.js`** (플러그인 루트 상대) — **4콜 2단계**: 전체 플랜 ∥ edge 적대 ∥ impact+arch(동시 3) → 델타 병합.
> agents/의 plan-structure·plan-edge-case·plan-impact 정의를 agentType(`fz:`)으로 재사용. 규약: `guides/skill-authoring.md` §12.
> 동시 opus ≤3(Lead 세션 fable은 별도)는 Stage 1 의 3-병렬이 상한을 **정확히** 채워 구조적으로 보장한다. rate-limit 시 순차화 폴백(governance.md).
>
> ⛔ **2026-09-12 배선 전환 (6단계 9콜 → 2단계 4콜)** — 근거는 `experiment-log.md` §5.9 (구조 ablation · 노이즈 교정 · 채택 판정):
> · wall **3,492s → 1,344s (-61.5%)** · 요구 3축 양쪽 closed · 실행 가능 command verify **4 → 5**
> · ⭐ **노이즈 바닥 교정**: 같은 9콜 구조를 동일 입력·트리로 2회 실행하니 상호 고유 major **5건** · overall `Q-superior`(동등 아님) ·
>   채택 기전까지 갈렸다. 즉 **run-to-run 분산이 구조 간 차이보다 크다**. D1b 가 9콜과 갈리는 정도(**3**)는 그 바닥(**5**) **이하**다.
> · ⛔ 근거는 전부 **N=1** 이다. 실사용 3회 관찰 후 재평가한다(`experiment-log.md` §5.9).
> · **롤백**: 아래 절차 2.5·3 의 스크립트명을 `plan-collaborative.js` 로 되돌리면 끝이다 — 파일은 그대로 남겨 둔다.

### 실행 절차 (Lead)

1. **codeContext 선행 기록**: 심볼 탐색 산출 요약을 `{WORK_DIR}/plan/code-context.md`로 기록 (대형 입력은 파일 경로 전달 — §12)
1.5. **아키텍처 제약 추출** (아키텍처 민감 과제 해당 시 — args 조립보다 **먼저**):
   프로젝트 지침 전체(CLAUDE.md·AGENTS.md 등 peer 파일 **모두**)에서 4축을 추출한다 — `architecturePattern` / `uiStack` / `dependencyDirection` / `naming`.
   - 미확정 축 → `null`. 코드 실측(grep) 1회로 보완 시도하고, 실패하면 **null 유지 + 그 축 제약 미적용** (중단·재질문 아님)
   - ⛔ **소스 간 모순 축은 자동 승자를 선정하지 않는다** — 축을 `null`로 두고 `conflicts[{axis, sources, claim_a, claim_b}]`에 보존 + 사용자 **1회** 보고. 이유: 현재 런타임(Claude Code / GPT)을 판별할 결정론적 입력이 없어 peer 지침 간 precedence를 세울 근거가 없다
2. **args 조립**: `requirement`(필수)=요구사항 원문 / `codeContextPath`(필수)=요약 파일 절대 경로 / `constraintsKnown`=수집 제약 / `archConstraints`=절차 1.5 산출(있으면 — 미전달 시 워커 프롬프트 무변화) / `discoverJournalPath`=discover 산출물 경로(있으면 — 전제 아닌 참고)
2.5. **호출 경로 선결정** (⛔ 사전 복사 — 거부 왕복을 없앤다):
   실측(2026-09-11, 3건 전부): 플러그인 루트 경로로 첫 호출이 거부되고 WORK_DIR 복사본으로 재호출해 성공했다 — 거부 1회가 매번 낭비된다(텔레메트리 `n_workflow=2` 의 정체).
   `{플러그인 루트}`가 세션 working directory(또는 additional directory) **하위가 아니면** `guides/skill-authoring.md` §12 우회 계약의 2·3단계를 **선행**한다:
   `grep -c '^import\|require(' {플러그인 루트}/workflows/plan-lean2.js` 가 `0` 임을 확인(⛔ 무출력은 0이 아니라 경로 오류) → 복사 → 그 경로로 **1회** 호출:
   ```bash
   cp {플러그인 루트}/workflows/plan-lean2.js {WORK_DIR}/plan-lean2.js
   ```
   ⛔ 판별이 불확정이면 **원본 경로로 호출한다**(기존 동작) — 미확정을 '하위 아님' 으로 읽어 불필요한 복사를 만들지 않는다. ⛔ 복사본은 산출물이 아니다(원본 변경 시 stale — §12).
3. **Workflow 호출**: `Workflow({ scriptPath: '{2.5에서 정한 경로}', args })` — ⛔ 거부 시 SOLO 폴백 아님: `guides/skill-authoring.md` §12 우회 계약
   - **Stage 1 (동시 3, opus)**: 전체 플랜(방향 판정·readScope/writeScope·steps·rtm·antiPattern 포함) ∥ edge 적대 렌즈 ∥ impact+arch 렌즈
     → **Stage 2 (opus)**: 델타 병합 — ⛔ 병합 콜의 schema 는 **델타 전용**(`stepAmendments`·`addedEdgeCases`·`addedImpact`)이라 본문을 다시 쓸 수 없다. **4 call**
   - ⛔ 반환의 `delta` 는 plan 에 **자동 병합되지 않는다** — Lead 가 적용 판정을 한다(병합 콜이 본문을 못 쓰게 한 것과 같은 이유)
4. **반환 처리**:
   - `mode:'workflow'` → plan(§X readScope/§Y writeScope/§Z acceptanceCriteria + RTM 5필드 + implicationRegister + unresolvedPeerIssues[archVerdict])을 Phase 1 산출물로 통합 → plan-v{N}.md 기록 + top-level `directionAlternatives`(plan 객체 밖 — PlanSchema에 없음)를 plan 문서 '구조 결정 옵션 테이블' 섹션으로 **별도 병합** (병합 누락 시 옵션이 사용자에게 미도달)
   - ⛔ `delta`(있으면) 처리: `stepAmendments` 를 해당 Step 에 반영하고 `addedEdgeCases`·`addedImpact` 를 plan 에 편입한다. `unresolved` 는 사용자 보고 대상 — 조용히 버리지 않는다
   - ⛔ **반환 전체를 `{WORK_DIR}/plan/workflow-result.json` 으로 먼저 기록한다** — 아래 resolve 스크립트와 `plan_integrity_check.py` 가 그 파일을 읽는다. 기록하지 않으면 두 스크립트가 읽을 입력이 없어 계약이 no-op 이 된다(읽는 곳 3 · 쓰는 지시 0 이었다).
   - ⛔ `impactRequests` 가 비어 있지 않으면 **Lead 가 resolve 한다** — impact 렌즈는 Bash 가 없어 base 원본·이전 호출자 수를 직접 못 얻는다(`agents/plan-impact.md`). 요청을 무시하면 영향 분석이 그만큼 비어 있는 채로 plan 에 들어간다
     ```bash
     python3 "${FZ_PLUGIN_ROOT}/scripts/plan_resolve_impact_requests.py" {WORK_DIR}/plan/workflow-result.json --repo {대상 레포}
     ```
     심볼 census 는 자동으로 붙고(요청당 상위 3개 · positive control 동반), `UNRESOLVED` 로 남은 항목만 Lead 가 판단한다. ⛔ 미해소 항목은 plan 에 **그 사실을 적는다** — 조용히 비워두지 않는다
   - ⛔ `directionEscalation` 이 **null 이 아니면** → 대안 비교표 제시 + 사용자 확인 (Phase 0.5 RECONSIDER/REDIRECT 절차 준용).
     `{ verdict, alternatives }` 형태이며 `directionVerdict` 가 `RECONSIDER`·`REDIRECT` 일 때만 실린다.
     ⛔ **필드다, 반환 모드가 아니다** — 현행 배선(`plan-lean2.js`)은 방향 판정을 full 콜 안에서 하므로 정상 경로와 반환 형태를 가르지 않는다.
     (롤백해 `plan-collaborative.js` 를 쓰면 그쪽은 `mode:'direction_escalation'` 으로 온다 — 두 형태를 모두 받는다.)
   - `mode:'fallback'` → SOLO 계획 수립 수행 + 사유 experiment-log 기록 (두 배선 모두 반환한다)
5. **Workflow 외부 Lead 책임 (이관 아님 — 회귀 확인 의무, 15차)**: 설계 스트레스 테스트 Q1-Q6 + RTM 검증 + Phase 0.7 Sprint Contract(GPT 회복 시) + GPT verify(Phase 2) + memory-curator recall + plan 파일 기록은 기존 Phase 절차대로 Lead가 **반환 후 실수행** — Workflow는 Phase 1의 협업 분석 부분만 대체
6. **지표 기록**: `return.metrics` + **자동 계측** → `experiment-log.md` §5.7 fz-plan 테이블
   ```bash
   python3 "${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py" --wf {runId 폴더명} --row      # §5.7 행 형식
   python3 "${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py" --wf {runId 폴더명}            # stage 상세(advisor·so_retries·cache)
   python3 "${FZ_PLUGIN_ROOT}/scripts/fz_telemetry_report.py" --plan-segments {세션 id 앞 8자}   # Lead·GPT 층 분리
   ```
   ⛔ wall-clock 을 손으로 적지 않는다 — `§5.8` 사전등록 표가 두 달간 비어 있던 이유가 **재는 주체 부재**였다. 값을 못 얻으면 `unavailable` 로 적고 0 으로 쓰지 않는다

**6개 차별화된 렌즈** (같은 질문 금지 — ICLR 2025 근거. Workflow stage에 동일 적용):

| 렌즈 | 스크립트 위치 | 핵심 질문 |
|------|--------------|----------|
| plan-structure (설계+분해) | Stage 1 전체 플랜 + Stage 2 병합 | "어떻게 나누고 만들 것인가?" · 방향 판정도 이 콜이 함께 낸다 |
| plan-edge-case (경계) | Stage 1 적대 렌즈 | "어디서 깨지는가?" — ⭐ 측정상 고유 기여가 가장 큰 렌즈 |
| plan-impact (영향+아키) | Stage 1 통합 렌즈 | "어디까지 퍼지는가 · 기존 패턴과 맞는가?" — `secondaryHosts`·`existingTestSuites` 를 schema 로 명시 요구 |
| GPT verify (독립 검증) | Workflow 외부 — Lead가 /fz-gpt verify (Phase 2) | "이 계획에 빠진 것은?" |

> 통신 기록: plan-team.md 미생성 — Workflow transcript(runId)가 대체. TEAM 메커니즘 일몰은 확산 판정 시 결정.

---

## ⛔ Phase 0: Work Dir Pre-flight
> 참조: `modules/context-artifacts.md` → "Work Dir Resolution" 섹션. **Phase 0b 전에 반드시 실행.**

1. 인자에서 `[A-Z]{2,6}-\d{2,5}` 패턴 추출
2. 패턴 있으면 → `{CWD}/{TICKET}/` 폴더 + index.md 생성 (없으면) + WORK_DIR 설정
3. 패턴 없으면 → 브랜치명 확인 → 없으면 AskUserQuestion(저장 여부) → 예: `{CWD}/NOTASK-{YYYYMMDD}/` + index.md 생성 / 아니오: Serena fallback

### Gate 0: Work Dir Ready
- [ ] ⛔ 티켓 패턴 또는 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (티켓 폴더 경로 / NOTASK 경로 / Serena fallback)
- [ ] index.md 존재 확인 완료? (없으면 생성)

---

## Phase 0b: Context Loading
### 절차

1. **세션 감지**: 참조 `modules/session.md`
2. **이전 세션 복원**:
   - `mcp__plugin_fz_serena__list_memories` → 관련 이전 세션 검색
   - `mcp__plugin_fz_serena__read_memory` → 결정사항, 잔여 이슈 로드
3. **프로젝트 활성화**:
   - `mcp__plugin_fz_serena__activate_project` → LSP 서버 활성화
4. **대상 모듈 심볼 파악**:
   - `mcp__plugin_fz_serena__get_symbols_overview` → 작업 대상 파일 심볼 구조
   - `mcp__plugin_fz_serena__find_symbol` → 컴포넌트 탐색

5. **이전 Discover 결과 로드** (티켓 폴더(WORK_DIR) 활성 시):
   - `{WORK_DIR}/discover/discover-journal.md` 읽기 → Landscape Map + Trade-off Table + Open Questions 복원
   - `{WORK_DIR}/discover/discover-plan.md` 읽기 → mid-pipeline discover 결과 (있으면)
   - **⛔ discover 결과는 "전제"가 아닌 "참고"**: plan은 discover의 경로 중 하나를 선택하거나, 새 경로를 설계할 수 있음
   - 🔒불변 조건만 plan의 제약으로 채택. 🔓가변 조건은 비용 비교 대상으로만 활용
   - Open Questions는 plan Phase 1에서 추가 탐색 대상
   - ⛔ **Scope Expansion**: discover 변경 대상의 상위 모듈/프로토콜에서 `get_symbols_overview` → 놓친 형제 타입/간접 소비자를 탐색 범위에 추가

### Gate 0b: Context Ready
- [ ] 프로젝트 활성화 완료?
- [ ] 대상 심볼 구조 파악?
- [ ] 이전 컨텍스트 로드 + 아키텍처 제약 추출·conflict 상태 확인? (각각 해당 시)

---

## Phase 0c: Constraint Probe Pre-flight (31차 방어)

> Plan 핵심 차원이 primitive(CLI flag / config key / value enum / env precondition)에 의존하면 추측 위에 작성하지 않는다. 실측으로 가정 검증 후 차원 포함. 참조: `Plan-before-Probe 교훈`.

발동: 외부 primitive 의존 시 필수. 코드베이스 내부 패턴만 의존하면 스킵.

> **절차 본문**: `modules/plan-direction-preflight.md` Phase 0c 절 참조 (Level 3) — 3 절차(가정 추출 3 axes · 검증 분류 · probe 결과 통합). Phase 0c 발동 시 Read.

### Gate 0c: Constraints Verified for Plan
- [ ] primitive 의존 가정 모두 식별?
- [ ] 각 가정의 **3 axes** (존재 / 권한·경계 / 결과 contract) 모두 분류 완료? (32차 방어)
- [ ] 미검증 axis는 Plan 차원에서 제외 또는 explicit assumption tag?
- [ ] probe 필요 시 `/fz-discover` 선행 완료?
- 미통과 시 → ⛔ Plan 작성 차단

---

## Phase 0.5: Direction Challenge

> **Default = action with proportional verification** (참조: `modules/lead-action-default.md`). verification escalation은 명시적 risk signal 발생 시에만.

발동: Workflow 모드는 Stage 0이 수행 / SOLO + 새 아키텍처 결정 시 필수 / discover 방향 명확 시 스킵 가능 / 단순 수정 스킵 (⛔ 미러링으로 신규 화면·컴포넌트 생성은 스킵 불가 — 45차).

> **절차 본문**: `modules/plan-direction-preflight.md` Phase 0.5 절 참조 (Level 3) — 발동 조건표 4행 + 4 절차(아키텍처 대조 · 6관점 검토 · 방향 판정 · 판정 기록). Phase 0.5 발동 시 Read.

### Gate 0.5: Direction Validated
- [ ] 6개 관점 검토 완료?
- [ ] 대안 최소 2개 제시?
- [ ] 구조 결정별 대안 ≥2 + trade-off 기록? (SOLO 조기 체크 — Workflow 모드의 병합 확인은 Gate 1 담당. 답습/미러링이면 3축 — 45차)
- [ ] 방향 판정 (PROCEED/RECONSIDER/REDIRECT)?
- [ ] RECONSIDER/REDIRECT 시 사용자 확인?
- [ ] 구조/경계 포크 결단 시 유형 분류 — (가) 코드 read/grep으로 정답이 1개로 좁혀지는 엔지니어링 판단 → 확신 권고+근거+"이의 없으면 진행"(옵션 메뉴화 금지) / (나) 제품·디자인·팀 컨벤션 소유 → AskUserQuestion. ⛔ 경계(PR/커밋): plan 분할 제안=판단 입력≠경계 권위 (1커밋=1관심사+컴파일+1결정 trace). *[candidate: 2 session evidence]* (`modules/promotion-ledger.md` **L-14**, active:5세션(트랙 A — 원장이 canonical). 경계 애매(엔지니어링+제품 혼합) 구간 참고 어휘: 위험도 티어 L1-L4 [외부: harness-paper, NOVA 2606.27243 — 참고 축, 게이트화 금지])

---

## Phase 0.7: Sprint Contract (T2-B, TEAM mode)

> 발동: **TEAM mode + (5+ Step Plan 또는 Cross-skill 변경)**. 단순 수정/탐색 스킵.

GPT가 구현 시작 **전** "성공 기준" Sprint Contract 작성 → Claude 동의/수정 → Phase 1 진입. 사후 수정 비용 감소.

- 절차: `modules/sprint-contract.md` §절차 (4-step)
- Schema: `modules/sprint-contract.md` §Schema (yaml: success_criteria + anti_criteria + scope_boundary)
- Lead Decision: **agree** → Phase 1 / **modify** → GPT re-verify 1회 (한도) / **reject** → Phase 0.5 재진입

### Gate 0.7: Sprint Contract Agreed

- [ ] GPT Sprint Contract 작성 완료? (`sprint-contract-gpt.md` 또는 `fz:checkpoint:sprint-contract`)
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
- [ ] ⛔ Gate 0 (Work Dir Pre-flight) 통과했는가?
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
- [ ] 구조 결정 옵션 테이블 포함 + 사용자 보고 제시? (Workflow 모드면 `directionAlternatives` 병합 확인. 답습/미러링이면 3축 필수 — 45차)
- [ ] ⛔ 계획 기록 완료? (티켓 폴더: 파일, 비-티켓 세션: Serena checkpoint)

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

> **병렬 실행 계약** (⛔ `verify` 와 `verify-gates` 는 서로를 기다리지 않는다 — 실측: 순차 호출 시 고 tier 8~10분/회가 직렬로 누적된다):
> 1. **불변 입력** — 두 호출은 같은 plan·같은 원장 스냅샷을 읽고 서로의 산출을 입력으로 쓰지 않는다. 입력이 바뀌면 병렬 전제가 깨지므로 호출 전에 파일을 확정한다.
> 2. **별도 출력** — `plan/gpt-verify.json` · `plan/gpt-verify-gates.json` 으로 파일을 분리한다(같은 파일에 쓰면 뒤 호출이 앞을 덮는다).
> 3. **양쪽 완료 대기** — 두 로그에 종료 표시가 모두 나온 뒤 판정한다. 한쪽만 보고 진행하면 나머지가 조용히 버려진다.
> 4. **schema 검증 후 사용** — 각 응답을 `--output-schema` 계약으로 받고, `verify-gates` 는 `gate_check.py --verdict-check` 사후 대조까지 통과해야 판정으로 인정한다(⛔ 게이트 수 ≠ 판정 수이면 미판정).
> ⛔ 버전 불일치(호출 사이에 plan 이 수정됨) 시 **재검증**한다 — 옛 plan 에 대한 판정을 새 plan 의 승인 근거로 쓰지 않는다.

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

3.1. **⛔ draft 원장 생성** (WORK_DIR 존재 + full 모드 — `modules/gates.md` 배선 1):
   Phase 1 반환의 `steps[]`를 JSON으로 임시 기록한 뒤 변환한다. ⛔ **이 단계가 없으면 원장이 생기지 않아 배선 2·3이 전부 no-op이다.**
   ```bash
   python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py" \
     --from-plan {WORK_DIR}/plan/steps.json --root {WORK_DIR} --out {WORK_DIR}/gates/plan.draft.md
   ```
   `FZ_PLUGIN_ROOT`는 `scripts/resolve-plugin-root.sh`로 해석한다 — ⛔ 상대 경로(`scripts/…`)는 대상 레포에 그 파일이 없어 exit 2(인프라 통과)로 **조용히 강제력이 사라진다**.

3.2. **⛔ 게이트 판정** (draft 원장이 있을 때 — `modules/gates.md` 배선 1):
   Phase 1에서 만든 `{WORK_DIR}/gates/plan.draft.md`를 검증 입력에 **포함**한다. 원장이 Phase 3에서 만들어지면 Phase 2 평가자가 볼 `CHECK:`가 없다 — draft가 먼저인 이유다.
   ⛔ **기존 계획 검증(`verify`)을 대체하지 않는다** — `verify-gates`를 **추가 호출**한다. gate_verdict 스키마엔 `issues`·`verdict`가 없어 교체하면 Issue Tracker·scope challenge·Gate 2 입력이 사라진다. 절차: `modules/fz-gpt-subcommands-core.md` § verify-gates
   - 요구: 게이트마다 판정 1행. ⛔ **통과한 게이트도 표현**해야 N/N 대조가 성립한다
   - ⛔ **사후 대조 의무** — 눈으로 하지 않는다: `python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py" --verdict-check {응답.json} {WORK_DIR}/gates/plan.draft.md`
     게이트 수·id 집합·중복·summary 합계를 판정한다. exit 1이면 재호출 1회 후 **미판정으로 기록** — 조용히 통과시키지 않는다
   - 판정 축: measurement_fit(제목이 말하는 걸 측정하나) · noninteractive · rerunnable · determinism · side_effects
   - `verdict: revise`는 CHECK/EXPECT 수정, `demote_to_manual`은 명령 판정 불가 — 억지 command보다 정직하다
   - 게이트 수 ≠ 판정 수이면 **미판정**이며 통과가 아니다

3.5. **⛔ 검증 결과 기록** (항상):
   - 티켓 폴더(WORK_DIR) 활성: `{WORK_DIR}/plan/verify-result.md`에 verdict + 이슈 요약 기록
   - 비-티켓 세션: `write_memory("fz:checkpoint:plan-verify", "verdict: {approved/rejected}. 이슈: {N}개. Critical: {요약}")`

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

1b. **⛔ Scope Challenge (이슈당 필수)**: 각 GPT 이슈를 플랜에 반영 전 `modules/scope-challenge.md` Q-S1~S4 실행 → `scope_disposition` 분류. Lead는 GPT 결과를 **읽기 전** 독립 판정 후 비교 (Generator≠Evaluator).

2. **요구사항 일치 검증**:
   - `mcp__sequential-thinking__sequentialthinking` → 수정 전후 요구사항 부합도 단계별 비교
   - `/sc:sc-reflect` → 자체 검증

3. **사용자 의사결정** (AskUserQuestion):
   - 수정 후 Phase 2 재검증
   - 현재 계획으로 구현 진행
   - 추가 논의

4. **⛔ 계획 기록** (항상 — compact recovery 필수 + `/fz-code` Phase 0.4 핸드오프 소스):
   ⛔ **이슈 0건 승인이어도 이 기록은 발화한다.** `### Gate 2 전제조건`이 본 Phase보다 앞에 있어, 피드백이 없으면 본 Phase를 건너뛰어 `plan-final`이 생성되지 않는 경로가 생긴다.
   - **WORK_DIR 존재(티켓 폴더 또는 NOTASK)**: `plan-v{N+1}.md` 생성 + 최종 승인 시 `plan-final.md` + `index.md` 업데이트
     ⛔ **`plan-v{N}` 은 변경 이력이고 `plan-final.md` 는 승인본이다 — 승인 시 `plan-final.md`·`plan/steps.json`·`gates/plan.md` 를 같은 버전으로 완전 재생성한다**(해당 구역만 고쳐 쓰는 것도 허용 — 요구는 *결과가 단일 최신 상태*라는 것).
     이유: `/fz-code` Phase 0.4 는 `plan-final.md` **하나만** 복원하고 RTM 도 그 문서 안에서 갱신된다(`modules/rtm.md`). 이전 본문과 수정 delta 를 나란히 남기면 폐기된 Step·verify 가 함께 복원돼 구현이 무엇을 따라야 할지 갈린다.
   - **Serena fallback**: `write_memory("fz:checkpoint:plan-final", …)` — ⛔ 요약 문자열이 아니라 **계약 필드**를 담는다:
     `{steps:[{id,title,files,verify}], swiftDecisions:{swiftUI,isolation,transform}, rtm:[…], verdict}`
     — `verify`는 **VerifySpec 객체**다: `{kind:'command', criterion, command, expect, cwd?}` 또는 `{kind:'manual', criterion}` (정의: `workflows/plan-lean2.js` VerifySpec · 배선: `modules/gates.md`)
     (요약만 저장하면 `/fz-code` Phase 0.4의 구조 검사가 판정 불가)

4.5. **⛔ 원장 확정** (draft 원장이 있을 때): Phase 2 판정(3.2)을 반영해 `gates/plan.draft.md` → `gates/plan.md` 로 복사한 뒤 **`--finalize`** 를 돌린다 — 실행 게이트마다 `APPROVED_ORACLE_HASH` 도장을 찍고 `APPROVED: yes` 를 남긴다. ⛔ 도장이 없으면 승인 계약이 존재하지 않는다(검사는 있으나 발급이 없어 한 번도 발화하지 않았다). `revise`는 CHECK/EXPECT 수정, `demote_to_manual`은 `MANUAL:`로 전환. 확정 후 `python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py" --status {WORK_DIR}/gates/plan.md`.
   exit별 행동 — `0` 진행 · `1` 미충족 보고 후 진행(작업 중 정상 상태) · `2` **인프라 경고 후 진행**(경로·인터프리터 문제이지 원장 결함이 아니다) · `3` **미통과 차단**(확정 원장이 계약을 위반하면 안 된다).
   ⛔ 상대 경로 금지 — 설치된 플러그인에서 대상 레포에 파일이 없어 exit 2로 떨어지고, exit 3만 차단하는 규칙 하에서 **invalid ledger 검증이 fail-open** 된다. 절차 정본: `modules/gates.md`

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

```
BAD (실측 없는 제약 가정):
CLI flag 존재를 가정하고 Plan 차원에 포함 → probe마다 Plan 무력화·재작성 사이클.

GOOD:
Phase 0c에서 3 axes(존재 / 권한·경계 / 결과 contract) 분류 → 미검증은 /fz-discover 선행 후 차원 포함.
```

```
BAD (변환 스레드 미명시):
PromiseKit .done → async Task 변환에 스레드 명시 없음 → 원본 main queue 유실, UI regression.

GOOD:
Transformation Spec "실행 스레드: main(@MainActor)" + [verified] 태그 → 구현이 @MainActor 보장.
```

## 테스트 케이스

> 상세: `references/test-spec.md` (Triggering + Functional)

## Boundaries

**Will**: 요구사항 분해, 영향 분석, Serena 탐색, 구현 계획 출력, 계획 검증
**Will Not**: 코드 수정 (→ /fz-code), 빌드 실행 (→ /fz-code)

### light 모드 (40차 simplified mode)

사용자 신호 "그냥/가볍게/단순/빠르게" 감지 또는 `/fz-plan light "..."` 호출 시:
- Phase 1 (Deep Planning)만 실행 — 구조 분해 + 영향 분석 + Step 출력
- Phase 0.5 (Direction Challenge) 생략 (단순 수정 patterns 대상)
- Phase 2 (Validation) + Phase 3 (Feedback) 생략 (GPT verify 미호출)
- Stress Test Q1-Q6 생략, 리스크 매트릭스 간소화
- Anti-Pattern Constraints 작성 생략 (리팩토링 작업 외)
- 단 산출물이 전수/카운트/부정 주장 포함 시 Coverage Gate(cross-validation.md §Coverage Gate) 적용 — light에서도 생략 불가 (검증 경계) ⛔ **그중 부정 주장(0건·부재·"~뿐")은 §Negative-Result Gate 도 함께 적용**(positive control + exit code) — Coverage Gate 는 *범위*(N 중 M)를 보고 Negative-Result Gate 가 *도구 유효성*을 본다. **N 자체가 오측정이면 0/0 으로 통과한다**(`skills/fz-peer-review/SKILL.md` Synthesize 인용)
- 산출물: `{WORK_DIR}/plan/plan-light.md` (간소화 형식)

조건: 메모리 40차 trigger 키워드 + 단순 수정/추가 작업에만. 새 아키텍처 결정 시 full 모드 강제.

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| Serena 연결 실패 | Grep + Glob 폴백 | 수동 탐색 |
| Context7 실패 | WebSearch 폴백 | 문서 직접 검색 |
| 검증 실패 | /sc:sc-analyze 단독 검증 | Claude 자체 판단 |
| Workflow scriptPath 거부 | `guides/skill-authoring.md` §12 우회 계약(self-contained 확인 → WORK_DIR 복사 → 재시도) | 사용자 에스컬레이션(L4) — ⛔ **SOLO 폴백 아님** |
| **advisor 스톨** (워커가 advisor 호출 → 3분 무진행 × 런타임 6회 재시도) | ⛔ **결정론 차단 불가** — `agent()` 에 도구 제외·타임아웃 옵션이 없고 `agentType` 의 `tools:` 도 advisor 를 막지 못한다 [verified: 프로브 `wf_54f2f1d3-8c5`]. OVERRIDE 문구가 유일한 완화이고 **잔여 위험을 수용한 상태다**(실측 최악 117분). ⛔ **문구의 효과는 미측정** — 문구 삽입 전 실행에서 advisor 8/8/10회가 관측됐으나 그것은 기준선이지 대조군이 아니다(F-161·F-191). 든 상태의 실행과 비교해 줄지 않으면 **문구를 삭제한다** | 세션 `advisorModel` 해제 — ⛔ Lead 의 advisor 도 함께 사라진다 |

## Completion → Next

Gate 2 통과 후:
```bash
/fz-code "검증된 계획대로 구현해줘"
```
