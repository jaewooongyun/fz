---
name: fz-review
description: >-
  자기 코드 3중 검증(Claude+Codex+sc:analyze) + 역방향 검증.
  예: 리뷰해줘, 검증해줘, 품질 확인, 괜찮아?, 내 코드 봐줘 (비사용: 팀원 PR →fz-peer-review, 직접 수정 →fz-fix)
user-invocable: true
argument-hint: "[리뷰 대상 설명] [light]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__find_referencing_symbols,
  mcp__serena__get_symbols_overview,
  mcp__serena__write_memory,
  mcp__serena__read_memory,
  mcp__serena__edit_memory,
  mcp__serena__list_memories,
  mcp__sequential-thinking__sequentialthinking,
  mcp__lsp__diagnostics_delta,
  mcp__lsp__references,
  Read, Grep, Glob, Workflow
team-agents:
  primary: review-arch
  supporting: [review-quality, review-counter, review-correctness, memory-curator]
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
>
> ⛔ **자산 추가/수정 시 가이드 명시 참조 의무**: 본 스킬 또는 메모리에 새 항목을 추가/수정 시 `guides/skill-authoring.md` + `modules/memory-guide.md` 사전 참조. **Decision Tree (evidence ≥ 3 sessions) + 태깅 (`[skill:][status:][priority:]`) + MEMORY.md 200줄 한도** 모두 검증. 사후 catch 방지 (Layer 1+2+3 systematic weakness 차단).

## 개요

> ⛔ Phase 0 (ASD Pre-flight) → Phase 5 (3중 검증: Serena // /fz-codex review // /sc:analyze) → Phase 5.5 (/fz-codex validate) → Rate >= 80%? → Phase 7 완료 | Phase 6 (개선) → 반복
> 루프 프리미티브: Evaluator-Optimizer + Multi-Attempt Retry (H6, Inside the Scaffold)

3중 검증(Claude+Codex+sc:analyze) + 역방향 검증 + Reflection Rate 정량화 (>=80% 통과).

> 이론 근거: MAR — Multi-Agent Reflexion (arxiv 2512.20845) — **acting/diagnosing/critiquing/aggregating 역할 분리**가 단일 에이전트 self-review보다 정확도 높음. fz의 Claude(acting) + Codex(critiquing/diagnosing) + Lead(aggregating) 역할 분리와 구조적 정합.

```bash
/fz-review "구현한 코드 리뷰해줘"     /fz-review "현재 Reflection Rate 얼마야?"
/fz-review "Codex 피드백 반영, 재검증" /fz-review "Gate 5 통과 확인해줘"
```

## Prerequisites

- 팀 에이전트 모드(Workflow pilot)는 네이티브 Workflow 도구 가용 환경 필요 — 미가용 시 SOLO 3중 검증 폴백
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | Workflow 미가용 시 SOLO 폴백 협업 프로토콜 (canonical 패턴 출처) |
| modules/patterns/live-review.md | Live Review (review-arch ↔ review-quality 발견 즉시 공유) (UC-11, v4.7.1) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/build.md | 빌드 검증 |
| modules/execution-modes.md | LOOP + SIMPLIFY 실행 모드 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |
| modules/rtm.md | RTM 검증 — Phase 4.5에서 Req-ID 상태 확인 |
| modules/native-agents.md | L3 에이전트 스폰 — Phase 5 병렬 검증 |
| modules/safety-audit.md | 검증 4-J Concurrency Safety Audit — 역방향 안전성 감사 |
| modules/uncertainty-verification.md | 4-K enforcement — [verified] 없는 주장 violation 판정 |
| modules/cross-validation.md | 검증 게이트 + 외부 피드백 검증 + 런타임 주장 검증 |

## Plugin 참조 (SwiftUI + Swift Concurrency)
> 참조: `modules/plugin-refs.md` — SwiftUI Expert + Swift Concurrency (리뷰 시) 섹션
> diff에 `@MainActor|actor|async|@Observable` 감지 시 해당 플러그인 참조. **역방향 트리거**: 동시성 키워드 없어도 `static let shared` + `var` 등 감지 시 Concurrency Safety 적용
> **iOS 16 minimum target 검증**: diff에 iOS 17+ API (`@Observable`, `@Bindable`, onChange new signature) 사용 시 `#available` 가드 존재 여부 검증 의무.

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| 5 | `/sc:analyze`, `/fz-codex review`, `/sc:spec-panel` | 품질분석, Codex 리뷰, 스펙 패널 |
| 5.5 | `/fz-codex validate` | 역검증 |
| 6 | `/sc:improve`, `/sc:cleanup`, `/sc:reflect` | 개선, 정리, 자체검증 |
| 7 | `/sc:test` | 최종 테스트 검증 |
## 팀 에이전트 모드 (Review Squad)

> 팀 모드 규칙은 `modules/team-core.md` 참조

> TEAM(TeamCreate+SendMessage) 모드를 네이티브 Workflow 결정적 스크립트로 대체한 Wave 1 전환.
> Live Review 패턴 canonical: `modules/patterns/live-review.md` (보존 — 라운드 의미론은 스크립트가 구현).
> 스크립트: `workflows/review-live.js` (플러그인 루트 상대) — agents/의 review-arch·review-quality·review-counter 정의를 agentType(`fz:`)으로 재사용. 규약: `guides/skill-authoring.md` §12.

### 실행 절차 (Lead)

1. **리뷰 대상 기록**: diff를 `{WORK_DIR}/review/diff.patch`로 기록 (untracked 신규 파일은 `git diff --no-index /dev/null {file}` append). **대형 diff는 args가 아닌 파일 경로 전달** (§12)
2. **args 조립**: `diffPath`=diff 파일 절대 경로 / `intentContext`=변경 의도 + 대체 대상 + 참조 가이드 (기존 Intent Context 계약 승계)
3. **Workflow 호출**: `Workflow({ scriptPath: '{플러그인 루트}/workflows/review-live.js', args })`
   - Stage 1 독립 병렬(review-arch opus + review-quality sonnet — opus 동시 1+Lead=2) → Stage 2 id-기반 교차 severity 조정 → Stage 3 review-counter DA(okAreas 도전 포함, 항상 실행 — UC-14 승계) → 병합은 스크립트 binary 규칙. 총 5-call
4. **반환 처리**: `mode:'workflow'` → findings(finalSeverity/crossVerdict/counterVerdict)를 Phase 5 결과로 통합. **false_positive/refute 플래그의 최종 기각은 Lead 판정** (live-review Lead 역할 보존) / `mode:'fallback'` → SOLO 3중 검증 수행 + 사유 experiment-log 기록
5. **Workflow 외부 Lead 책임 (이관 아님 — 회귀 확인 의무)**: L3 에이전트 통합(Phase 5 병렬 4/5) + review-correctness 검증(Phase 4.5, RTM/plan 존재 시) + Codex validate(Phase 5.5) + memory-curator recall은 기존 Phase 절차대로 Lead가 수행 — Workflow는 Phase 5의 [병렬 1] Claude 검증 부분만 대체
6. **지표 기록**: `return.metrics` + wall-clock(Lead 측정) → `experiment-log.md` §5.7 fz-review 테이블
### ASD 컨텍스트 로딩 (ASD 활성 시):
- `{WORK_DIR}/plan/plan-final.md` 읽기 → 승인된 계획 복원
- `{WORK_DIR}/code/progress.md` 읽기 → 구현 진행 상태 복원
- `{WORK_DIR}/code/step-*.md` 읽기 → 전체 구현 Step 상세 (1M context 활용)
- `{WORK_DIR}/discover/discover-review.md` 읽기 → mid-pipeline discover 결과 (있으면)
- `{WORK_DIR}/code/code-team.md` 읽기 → 구현 팀 통신 요약 (있으면)

### ⛔ 모듈화 리뷰 원칙 (Modularization Review Scope)

> **원칙**: 리뷰 범위 = 패키지 코드 + 앱 측 소비자 코드 + 진입점. 경계 양쪽을 모두 검증.

Lead가 리뷰 대상 구성 시 필수 포함:
1. **패키지 내부 코드**
2. **앱 측 소비자 코드**: `Grep("import {모듈명}")` → 소비자 파일 목록. 사용 패턴이 설계 의도와 일치하는지
3. **진입점 코드**: AppDelegate, SceneDelegate, UIWindow extension 등 (글로벌 hook 포함)

TEAM 모드 Intent Context 추가: `[소비자 코드]: {파일 목록}` + `[진입점]: {AppDelegate 등}`

---

## ⛔ Phase 0: ASD Pre-flight (반성 4차)
> 참조: `modules/context-artifacts.md` → "Work Dir Resolution" 섹션. **Phase 1 전에 반드시 실행.**

1. 인자에서 `ASD-\d+` 패턴 추출
2. 패턴 있으면 → `{CWD}/ASD-xxxx/` 폴더 + index.md 생성 (없으면) + WORK_DIR 설정
3. 패턴 없으면 → 브랜치명 확인 → 없으면 AskUserQuestion(저장 여부) → 예: `{CWD}/NOTASK-{YYYYMMDD}/` + index.md 생성 / 아니오: Serena fallback

### Gate 0: Work Dir Ready
- [ ] ⛔ ASD 패턴 또는 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD / NOTASK / Serena fallback)
- [ ] index.md 존재 확인 완료? (없으면 생성)

## Phase 4.5: Requirements Alignment (요구사항 부합)
### 절차

```
1. ⛔ RTM 기반 기계적 확인 (참조: modules/rtm.md):
   - plan-final.md 또는 Serena memory에서 RTM 로드
   - 모든 Req-ID가 implemented 상태인지 확인
   - pending 잔존 → requirements_gap 이슈
2. 요구사항 목록화 → 체크리스트
   - 세션 내 task/plan에서 구현 대상 추출
   - 커밋 메시지에서 의도 추출
3. diff에서 각 요구사항 구현 여부 확인
   - Serena find_symbol → 신규 심볼이 요구사항에 매핑되는지
4. 미구현/부분구현 → 이슈 (category: requirements_gap)
5. 범위 외 변경 → 이슈 (category: scope_creep). **⛔ plan-final.md §Y Write Scope 존재 시 diff 파일 ⊆ §Y 검증 필수** (없으면 plan 기반 소프트 판정)
```

### 체크리스트

- [ ] 세션 task/plan의 모든 요구사항이 구현되었는가?
- [ ] 커밋 메시지에 명시된 변경이 실제 diff에 반영되었는가?
- [ ] 범위 외 변경 (scope creep)이 포함되어 있지 않은가? (§Y Write Scope 정의 시 diff ⊆ §Y 검증)

### ⛔ B3: Follow-up 아티팩트 재검증 + Phase A 효과 측정 (v3.2.2)

**Follow-up 재검증** (follow-up-tasks.md / codex-review*.md / plan-v*.md 인용 시):
- [ ] 판단 날짜 + 근거 유형(실측/추정/외부 리뷰) 분류
- [ ] 추정/외부 리뷰 기반 → 현재 시점 재실측 (`git show`/`Read`/`grep`)
- [ ] 재실측 결과 ≠ 아티팩트 → 업데이트 이슈 생성 (category: artifact_stale)
- [ ] 참조: `${CLAUDE_PROJECT_DIR}/memory/feedback_followup_artifact_reaudit.md`, `cross-validation.md § Follow-up Re-audit Gate` (Phase B1/B2 후 활성)

**Phase A 효과 측정** (B1/B2 진입 조건 5개 지표 1:1 매핑):
- [ ] 지표①: T6/T7 발동 건수 + Speculation-to-Fact Fallacy 차단 사례 (세션당)
- [ ] 지표②: 실제 사전 차단 사례 (발동 후 실측으로 뒤집기 방지된 실증)
- [ ] 지표③: `[verified]` / `[미검증]` 태그 빈도 + 무태그 과거 주장("원본/기존/이전/D{N} 이전") 위반 건수
- [ ] 지표④: 세션 reversal 횟수 (사용자 판정 뒤집기 — 기준선 4회)
- [ ] 지표⑤: A5 micro-eval 호출 건수 N + confirmed C + false positive F → precision = C/N
- [ ] 결과 → `{WORK_DIR}/review/phase-a-metrics.md` (ASD 세션 임시) 또는 Serena `fz:metrics:phase-a-session-{N}` (비ASD 세션 임시). 최종 보고 "## Phase A Metrics" 섹션 포함 + plan-v3.2 §4.3 5개 지표 업데이트
- [ ] **canonical sink**: 세션 결과를 `experiment-log.md §5.4 Harness Metrics 누적`에 누적 (5 세션 누적 후 B1/B2 진입 판정). 다른 sink는 backlink만 허용 (3중화 금지).

## Phase 5: Cross-Review (3중 검증)
> **프로젝트 규칙**: CLAUDE.md `## Code Conventions` 섹션을 따른다.

### 병렬 검증 전략

```
Phase 5: Cross-Review (5+2 검증)
├─ [병렬 1] Claude + Serena: 참조 무결성 검증
├─ [병렬 2] → /fz-codex review: Codex 코드 리뷰
├─ [병렬 3] /sc:analyze: 정적 분석
├─ [병렬 4] L3 silent-failure-hunter: 에러 처리 스캔 (조건부 — modules/native-agents.md)
└─ [병렬 5] L3 type-design-analyzer: 타입 설계 평가 (조건부 — modules/native-agents.md)

    ↓ 모든 결과 수집

Results Merge & Dedup → Issue Tracker 통합
```

### 검증 1: Claude + Serena (참조 무결성)

```
mcp__serena__find_referencing_symbols → 변경된 심볼의 모든 참조 확인
Grep → 변경 후 패턴 일관성
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

> **Codex 불능 분기** (통신 실패 재시도 1회 후, 또는 장기 quota 불능 기간 — 에러 대응 표 참조): Agent tool 가용 시 **fresh-context Agent 1-spawn**(review-correctness 관점, `model` **명시** — 기본 `opus`(검증 깊이 우선), 소규모 diff(<100 LOC·5파일 미만)는 `sonnet`. 미지정 시 부모 세션 모델(Opus 4.8) 상속 — 소규모 diff에 opus는 과투자)으로 검증 2를 대체한다. 결과 인용 태그는 `[외부: codex]` 대신 `[fresh-context: claude]` — **이종 안전망 상실 명시** (동종 Claude 검증, 15/23차). Workflow 가용 여부와 무관한 직교 조건 (Workflow 폴백 ≠ Codex 폴백). Agent 미가용 시 /sc:analyze 폴백. 근거: "Separate, fresh-context verifier subagents tend to outperform self-critique" [verified: code.claude.com/docs/en/best-practices, code.claude.com/docs/en/sub-agents]
>
> **⛔ retain cycle 점검 (rank3b, 2026-06-18)**: fresh-context 검증자는 retain cycle 검사 시 `codex-skills/fz-reviewer/SKILL.md` Memory Management(closures capturing `self` without `[weak self]`)를 명시 적용한다 — Codex 부재 시 이종 parity 복원. 저장 프로퍼티 보유 closure·completion handler·Rx subscription 포함 (View 파일 한정 아님).
> **보조 이종 소스 (rank6)**: PR이 열려 있으면 `/fz` pr-comment-review로 CodeRabbit 코멘트를 보조 이종 소스로 활용 가능 (강제 아닌 Lead 판단).

### 검증 3: SuperClaude 정적 분석

```
/sc:analyze → 코드 품질, 보안, 성능, 아키텍처 종합 분석
```

### 검증 4: Refactoring Completeness (리팩토링 완성도)

> 3중 리뷰가 모두 diff 기반이므로 "안 바뀐 dead code"를 놓침. 이 검증이 유일하게 diff **밖**을 봄.

```
절차: 새 심볼 식별→대체 의도 추론→대상 사용처 역추적(find_referencing_symbols)→deprecated 검색→사용처 0이면 "삭제 권고"

체크리스트:
- [ ] 이전 심볼 사용처 0 → 삭제 대상?
- [ ] deprecated 코드 중 사용처 0?
- [ ] 삭제 대상의 의존 코드도 정리?
```

### 검증 4-D~4-H: 조건부 정밀 검증 → `modules/review-checks.md`

> 모듈화/리팩토링/마이그레이션 시 실행. 상세 절차+체크리스트는 `modules/review-checks.md` 참조.
> 4-D Constraint Matrix · 4-E Module Boundary+Consumer · 4-F Anti-Pattern Enforcement · 4-G Protocol Conformance · 4-H Source Fidelity

### 검증 4-I: Implication Coverage (함의 커버리지) — `modules/lead-reasoning.md` 참조. 제거/리팩토링 시 실행. 검증 4는 diff 안(judge), 4-I는 지시→diff 밖(auditor). 완료 보고에 "관찰 사항" 추가(§5).

### 검증 4-J: Concurrency Safety Audit (역방향 — 항상 실행) — `modules/safety-audit.md` 참조. diff에 동시성 키워드가 없어도 실행. 싱글톤 가변 상태 동기화+비대칭 동기화(L1 필수) + 콜백 스레드/@Published/기본값/SDK 래퍼/Task 프로퍼티 쓰기/check-then-act(L2 권장) 검사.

### 검증 4-N/4-O: candidate self-check → `modules/review-checks.md`

> ⚠️ candidate (evidence 1 session, 활성 강제 X — 5 sessions 후 결정). 상세 절차+체크리스트는 `modules/review-checks.md` 참조.
> 4-N Swift Naming Compliance · 4-O Session-added Assets Application

### 검증 4-K: Transformation Equivalence (코드 변환 동등성 — Plan에 Transformation Spec 있을 때)

Plan에 Transformation Spec이 포함된 경우, diff가 Spec 요구사항을 준수하는지 검증. 참조: `modules/code-transform-validation.md`

```
1. Plan Transformation Spec 로드
2. diff 변환 ↔ Spec 대조:
   - 스레드: Spec "@MainActor 필수" → diff에 @MainActor 존재?
   - 에러: Spec "분기 N개" → diff catch 분기 = N?
   - 추상화: Spec "protocol extension" → diff에 extension?
   - 인스턴스: Spec "stored property" → diff에 선언?
   - ⛔ Zero-Exception Thread: diff에서 Transformation Spec "실행 스레드"가 main queue인 변환이 @MainActor 없이 구현되었으면 → "thread_violation" (Critical)
   - ⛔ Wrapper Scope Minimality: @MainActor 블록 내 각 문장이 MainActor 컨텍스트를 필요로 하는지 확인. 불필요 문장 포함 → "wrapper_overscope" (Major) [ablation: scope-min-v1]
   - ⛔ Parameter Presence: 원본 대비 키 추가 → "parameter_addition" (Major)
   - ⛔ Default-Deny enforcement: Spec의 기술적 주장에 [verified] 태그 없음 → violation
3. 불일치 → "transformation_deviation" (severity: Major)
```

### 검증 5: UI/UX Refactoring Safety

View 파일 변경 포함 시 추가 검증:

```
View 파일 패턴: *View.swift, *Screen.swift, *Cell.swift

검증 항목:
- SwiftUI View body 구조 변경 → 레이아웃 영향
- @State/@Binding 변경 → 데이터 흐름 무결성
- Listener/Delegate 변경 → 메모리 누수 패턴 (CLAUDE.md 금지 패턴)
- **완료기준 (UI/제스처/애니메이션 동작 변경 시)**: 빌드 통과 ≠ 완료. visual oracle(launch_app_sim + screenshot · 실기기 시각 확인) 미충족 시 "완료" 선언 지양 — fz는 런타임 동작을 정적으로 못 봄(자동 실행 불가 = 사람 영역, 🔒 강제 게이트 불가). 기존 'screenshot 권고'를 evidence 3 sessions(38차 ASD-1398 · user_spec ASD-1793 · TVG-1219) 기반으로 강화.
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
- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 참조 무결성 확인? (Serena)
- [ ] ⛔ Codex 리뷰 통과? (Critical/Major 이슈 없음 — Codex 실행 자체가 필수)
- [ ] /sc:analyze 통과? (심각한 문제 없음)
- [ ] Constraint Matrix Compliance 통과? (제약 매트릭스 부합, /fz-discover 산출물 있을 때)
- [ ] Refactoring Completeness 통과? (deprecated dead code 없음)
- [ ] Module Boundary 통과? (access control이 의도와 일치)
- [ ] ⛔ 타입 소속 검증 통과? (각 public type의 관심사가 모듈 책임에 부합)
- [ ] Anti-Pattern Enforcement 통과? (금지 패턴 0건, Plan에 Constraints 있을 때)
- [ ] UI/UX Safety 통과? (UI/제스처/애니메이션 변경 시 visual oracle 권장 — 빌드통과≠완료, fz 자동 불가=사람 영역. evidence 3 sessions 강화)
- [ ] Spec Panel 통과? (새 모듈 시, 스펙 부합 확인)
- [ ] Protocol Conformance 통과? (시그니처 변경 시, 프로토콜 선언부 동기화 확인)
- [ ] Source Fidelity 통과? (리팩토링 시, 원본 대비 추가된 파라미터/로직 없음)
- [ ] Transformation Equivalence 통과? (Spec 있을 때, 스레드/에러/추상화 요구사항 준수)
- [ ] Concurrency Safety Audit 통과? (싱글톤 가변 상태 동기화, 콜백 스레드, @Published 스레드 — modules/safety-audit.md)
- [ ] ⛔ Concurrency Safety Audit **실행 여부** 확인? (diff에 class/struct 타입 변경이 포함되면 safety-audit.md 절차 실행 필수 — "해당 없음" 판정에도 판정 근거 명시)
- [ ] ⛔ Zero-Exception Thread Rule 통과? (main queue 변환에 @MainActor 누락 없음)
- [ ] ⛔ Wrapper Scope Minimality 통과? (@MainActor 블록 내 불필요 문장 없음) [ablation: scope-min-v1]
- [ ] ⛔ 요청 파라미터 키 동등성 통과? (원본 대비 추가/삭제 키 없음)
- [ ] ⛔ Default-Deny 통과? (Spec 기술적 주장에 [verified] 태그 존재)
- [ ] ⚠️ Swift Naming Compliance 권장 통과? (검증 4-N **candidate** — 활성 강제 X, 5 sessions 관측 후 결정)
- [ ] ⚠️ Session-added Assets Application 권장 통과? (검증 4-O **candidate** — 활성 강제 X, 5 sessions 관측 후 결정)

## Phase 5.5: Feedback Verification (역방향 검증)

> **Default = action with proportional verification** (참조: `modules/lead-action-default.md`). 추가 verify round는 명시적 critical 발견 시에만.
>
> 상세 절차·Gate 4.5·판정 기준: `modules/feedback-verification.md` 참조
>
> 요약: `/fz-codex validate "피드백 반영 검증"` 실행 → Reflection Rate 계산 → N≥10에서만 threshold gating (참조: `modules/cross-validation.md` § Reflection Rate threshold).

## Phase 6: Iterative Improvement
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

### 사용자 에스컬레이션
반복 한도 도달 시: 상태 보고(총/해결/미해결/Rate) + 선택지(DEFERRED / 추가 반복 / 수동 해결 / 중단)

### Gate 5: Final Quality
- [ ] 모든 Critical 이슈 수정 완료?
- [ ] 최종 빌드 성공? (modules/build.md 절차)
- [ ] Reflection Rate >= 80%?
- [ ] 최대 반복 횟수 미초과?
- [ ] ⛔ 아티팩트 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)

### 비ASD Checkpoint (Phase 5 완료 후)
- 비ASD 모드: `write_memory("fz:checkpoint:review-issues", "이슈 {N}개. Critical: {요약}. Reflection Rate: {X}%")`

## Phase 7: Completion (완료 처리)

Gate 5 통과 후:
1. **잔여 작업 확인**: sequential-thinking → 완료 체크리스트 (Gate 통과, 미해결 이슈, 범위 외 변경)
2. **Final Issue Report 생성**: `modules/session.md` 참조
3. **세션 저장**: `write_memory` (작업 요약 + 결정사항 + 변경 심볼)
4. **아티팩트 기록** (ASD 활성 시): `{WORK_DIR}/review/self-review.md` + `index.md` 업데이트
5. **Git 연계** (사용자 확인 후): `/fz-commit` → `/fz-pr`

완료 보고: 세션ID, 총이슈→해결/보류, Reflection Rate, 반복횟수, 변경파일, 다음단계

### Harness Metrics (v3.8+)

> **Canonical sink**: 누적 데이터는 `experiment-log.md §5.4`에 기록한다 (B1/B2 진입 판정용). 본 섹션은 세션 보고 형식만 정의하고, 누적은 canonical sink로 backlink.

리뷰 완료 보고에 Gate별 이슈 수를 기록한다:

```markdown
## Harness Metrics
| Gate | 이슈 발견 | 상세 |
|------|:---------:|------|
| 4-K Transformation | {N} | {요약} |
| Zero-Exception Thread | {N} | {요약} |
| Parameter Presence | {N} | {요약} |
| Wrapper Scope Minimality | {N} | {요약} |
| Default-Deny violation | {N} | {요약} |
| Confident Error (cross-model 불일치) | {N} | Claude {판정} vs Codex {판정} |
```

---

## Few-shot 예시

```
예시 1 — 리뷰 완료 보고:
  BAD:  "리뷰 완료. 문제 없음." → 근거 없음, Rate 없음
  GOOD: 이슈 N개 + Reflection Rate: X/Y (ZZ%) + Codex 교차 검증 결과

예시 2 — Anti-Pattern 잔존 검증 (검증 4-F → 절차: modules/review-checks.md):
  BAD:  diff 삭제 라인만 확인 → "패턴 제거" 판정 (다른 파일에 잔존)
  GOOD: Plan의 Anti-Pattern Constraints Grep 패턴으로 변경 파일 + 관련 모듈 전수 검색 → 매칭 0 확인

예시 3 — Source Fidelity (검증 4-H → 절차: modules/review-checks.md, 리팩토링/마이그레이션):
  BAD:  컴파일+테스트 통과 → "동작 유지" 판정 (`.done` main queue → 일반 Task 미감지)
  GOOD: Transformation Spec의 실행 스레드/에러 경로/파라미터 키 3축 모두 일치 확인
```

## 테스트 케이스

> 근거: `guides/skill-testing.md` §1(테스트 3단계) + §4(테스트 스펙 템플릿). Then은 객관 pass/fail oracle로 기술.

### Triggering Test

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "구현한 코드 리뷰해줘" | trigger | 핵심 유스케이스 ('예: 리뷰해줘') |
| "내가 짠 코드 검증해줘" | trigger | 자기 코드 검증 ('예: 검증해줘') |
| "이 코드 품질 확인해줘" | trigger | 품질 분석 ('예: 품질 확인') |
| "내 코드 괜찮아?" | trigger | 품질 자문 ('예: 괜찮아?') |
| "내 코드 좀 봐줘" | trigger | 자기 코드 리뷰 ('예: 내 코드 봐줘') |
| "팀원 PR 리뷰해줘" | NOT trigger | → fz-peer-review ('리뷰' 겹쳐도 팀원 PR은 범위 밖, '비사용:') |
| "이 버그 직접 고쳐줘" | NOT trigger | → fz-fix (직접 수정, '비사용:') |
| "이 기능 새로 구현해줘" | NOT trigger | → fz-code (대규모 구현, Will Not) |
| "codex로 검증해줘" | NOT trigger | → fz-codex ('검증' 겹쳐도 Codex 직접 호출은 Will Not) |
| "아키텍처 계획 세워줘" | NOT trigger | → fz-plan (계획 수립, Will Not) |

### Functional Test

| Given | When | Then | type |
|-------|------|------|------|
| 구현된 코드 diff 존재 + Codex CLI 가용 + 소규모 아님(리팩토링 포함) | `/fz-review "구현한 코드 리뷰해줘"` | 검증 1/2/3(Serena 참조 무결성 + `/fz-codex review` + `/sc:analyze`) 모두 실행(Codex 리뷰 생략 0건) → Gate 4(Review Passed) 체크리스트 통과 → Phase 5.5 역방향 검증 후 Gate 5(Reflection Rate ≥ 80%) 통과; 완료 보고에 총이슈→해결/보류 + Reflection Rate 명시 | normal |
| "그냥/가볍게" 신호 + 소규모 변경(5파일 미만 & 100 LOC 미만, 리팩토링/시그니처 변경 아님) | `/fz-review light "그냥 가볍게 봐줘"` | review-arch 단독 실행 + Codex 교차검증/Phase 5.5 역방향/Reflection Rate 추적 생략 + `review-light.md` 산출; 단 산출물에 전수/카운트/부정 주장 포함 시 Coverage Gate 적용(light에서도 생략 불가) | edge-case |
| 인자에 `ASD-\d+` 패턴 없음 + 브랜치명 없음 | `/fz-review "내 코드 봐줘"` | Phase 0에서 저장 여부 AskUserQuestion 발생 → '예' 시 `NOTASK-{YYYYMMDD}/` + index.md 생성 / '아니오' 시 Serena fallback → WORK_DIR 결정 → Gate 0(Work Dir Ready) 3개 항목 통과 | edge-case |
| 코드 diff 존재 + 검증 2에서 fz-codex 통신 실패 | `/fz-review "리뷰해줘"` | 재시도 1회 후 fresh-context Agent(review-correctness 관점)로 검증 2 대체 + 인용 태그 `[fresh-context: claude]` + 이종 안전망 상실 명시 (Agent 미가용 시 `/sc:analyze` 폴백); 검증 2 미생략 상태로 Gate 4 진행 | failure |

## Boundaries

**Will**: 3중 검증(Claude+Codex+sc:analyze), 역방향 검증, Reflection Rate 정량화, 반복 개선, 완료 처리
**Will Not**: 대규모 구현 (→ /fz-code), Codex 직접 호출 (→ /fz-codex), 계획 수립 (→ /fz-plan)

### light 모드 (40차 simplified mode)

사용자 신호 "그냥/가볍게/단순/빠르게" 감지 또는 `/fz-review light "..."` 호출 시:
- review-arch 단독 (review-quality 생략) — 아키텍처 적합성만 평가
- Codex 교차 검증 생략 (3중 → 1중)
- 역방향 검증 (Phase 5.5) 생략
- Reflection Rate 추적 생략
- 단 산출물이 전수/카운트/부정 주장 포함 시 Coverage Gate(cross-validation.md §Coverage Gate) 적용 — light에서도 생략 불가 (검증 경계)
- 산출물: `{WORK_DIR}/review/review-light.md` (간소화)

조건: 메모리 40차 trigger 키워드 + 소규모 변경(5 파일 미만 + 100 LOC 미만)에만. 리팩토링/모듈화/시그니처 변경 시 full 모드 강제.

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| fz-codex 통신 실패 | 재시도 1회 → 실패 사실 기록 후 /sc:analyze 폴백 | Claude 자체 판단 |
| fz-codex 장기 quota 불능 (기간 알려진 경우, 예: ~2026-06-28) | 재시도 생략 → 검증 2 불능 분기(Phase 5) 직행 — 매 검증 재시도 낭비 방지. **기간 만료 시 이 행 삭제 + 원복** (MEMORY.md Codex quota 줄과 동기화) | fresh-context Claude 검증자 |
| Rate < 60% 3회 | 사용자 에스컬레이션 | DEFERRED 마킹 |
| Issue Tracker 손상 | 새 세션 시작 | 수동 관리 |

## Completion → Next
Gate 5 통과 후: `/fz-commit` → `/fz-pr`
