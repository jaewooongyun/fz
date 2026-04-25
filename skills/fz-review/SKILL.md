---
name: fz-review
description: >-
  자기 코드 3중 검증(Claude+Codex+sc:analyze) + 역방향 검증.
  예: 리뷰해줘, 검증해줘, 품질 확인, 괜찮아?, 내 코드 봐줘
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

- TEAM 모드 사용 시 환경 변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정 필수 (미설정 시 TeamCreate 실패)
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
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

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| 5 | `/sc:analyze`, `/fz-codex review`, `/sc:spec-panel` | 품질분석, Codex 리뷰, 스펙 패널 |
| 5.5 | `/fz-codex validate` | 역검증 |
| 6 | `/sc:improve`, `/sc:cleanup`, `/sc:reflect` | 개선, 정리, 자체검증 |
| 7 | `/sc:test` | 최종 테스트 검증 |
## 팀 에이전트 모드 (Review Squad)

> 팀 모드 규칙은 `modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("review-{feature}")
├── Lead (Opus): 4중 검증 오케스트레이션 + 수정 수행
├── review-arch (★Opus): 아키텍처 리뷰 — agents/review-arch.md
├── review-quality (Sonnet): 코드 품질 리뷰 — agents/review-quality.md
├── review-correctness (Sonnet): Phase 4.5 요구사항 충족 검증 [RTM/plan 존재 시만 활성]
├── review-counter (Sonnet): DA 패스 — review-arch/review-quality "OK" 판정에 반론 [선택]
├── memory-curator (Sonnet): 관련 교훈 발굴 + review-arch에 직접 전달 [기본 포함, lightweight recall]
└── Codex CLI: 역검증 (Lead가 /fz-codex validate 실행)
```

> review-counter는 선택적 DA 패스. review-correctness는 Phase 4.5에서만 활성 (RTM/plan 존재 시).
> ASD 폴더 활성 시: `{WORK_DIR}/review/review-team.md`에 live review 핵심 통신을 기록한다.
### 통신 패턴: Live Review (Peer-to-Peer)

리뷰어들이 **분석하면서 서로 발견을 직접 공유** (Lead 거치지 않고 SendMessage 직접 대화).

```
Round 1: review-arch ↔ review-quality 실시간 발견 공유
Round 2: 상호 피드백 → 수정
Round 3: 합의 → Lead 보고
```

### MCP 제약 + Intent Context
- review-arch/review-quality는 serena, context7만 접근. Atlassian/LSP → Lead가 조회 후 전달.
- **Intent Context 전달 (필수)**: diff + `[변경 의도]: {새 심볼}이 {기존 심볼}을 대체` + `[대체 대상]: {기존 심볼, 파일}`
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

> 3중 리뷰가 모두 diff 기반이므로 "안 바뀐 dead code"를 놓침. 이 검증이 유일하게 diff **밖**을 봄.

```
절차: 새 심볼 식별→대체 의도 추론→대상 사용처 역추적(find_referencing_symbols)→deprecated 검색→사용처 0이면 "삭제 권고"

체크리스트:
- [ ] 이전 심볼 사용처 0 → 삭제 대상?
- [ ] deprecated 코드 중 사용처 0?
- [ ] 삭제 대상의 의존 코드도 정리?
```

### 검증 4-D: Constraint Matrix Compliance (조건부: /fz-discover 산출물 있을 때)

```
1. 제약 매트릭스 → 각 제약 추출 → diff에서 구현 부합 확인 (find_symbol + Grep)
2. 위반 → "constraint_violation" 이슈. 탈락 옵션 패턴 잔존 → 이슈
```

### 검증 4-E: Module Boundary + Consumer Quality (모듈화 작업 시)

```
1. access modifier: public/open 노출이 의도적인지 (find_symbol)
2. API surface: internal 세부사항이 public으로 노출되지 않았는지
3. 의존 방향: 하위→상위 역방향 참조 없는지 (find_referencing_symbols)
4. ⛔ 소비자 검증: Grep("import {모듈}") → 소비자 전수 수집
   - public API만 사용하는지, 설계 의도와 일치하는지
   - 앱 진입점(AppDelegate/SceneDelegate/UIWindow) 연동 정상인지
   - 모듈화 이전 레거시 패턴 잔존 여부
5. ⛔ SPM Chore 검증 (새 패키지 생성 시 필수):
   - .gitignore에 `Packages/{name}/.build` 등록 확인
   - `Package.resolved` 커밋 여부 (외부 의존성 있으면 필수)
   - pbxproj에 `XCLocalSwiftPackageReference` 등록 확인
  6. ⛔ 타입 소속 검증 (모듈화 작업 시): 각 public type에 대해 "이 타입의 관심사 = 이 모듈의 관심사?" 도메인 특화 필드/비즈니스 로직/하드코딩 UI 문자열 포함 시 모듈 경계 위반
  7. ⛔ Symbol Coverage 검증 (import 제거 작업 시): diff에서 `import X` → `import Y`로 변경된 파일에서 X 모듈의 심볼(typealias, utility 타입 등)이 잔존하는지 grep. 잔존 시 → "symbol_orphan" 이슈
```

### 검증 4-F: Anti-Pattern Enforcement (잔존 금지 패턴 검증)

```
Plan에 Anti-Pattern Constraints 있는 경우 실행. 절차:
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

### 검증 4-G: Protocol Conformance (프로토콜 적합성 검증)
```
절차:
1. diff에서 시그니처가 변경된 메서드 식별
   - 파라미터 추가/제거/타입 변경/이름 변경
2. 각 메서드에 대해 프로토콜 요구사항 여부 확인
   - mcp__serena__find_referencing_symbols → 해당 메서드가 프로토콜에 선언되어 있는지
3. 프로토콜 요구사항인 경우:
   - 프로토콜 선언부가 diff에 포함되어 동일하게 변경되었는지 확인
   - 선언부가 diff에 없으면 → "conformance_break" (severity: Critical)
4. Swift 디폴트 파라미터 함정:
   - `func foo(bar: Bool = false)`는 `func foo()` 요구사항을 만족시키지 않음
   - 의도적 호환이면 → 파라미터 없는 오버로드 래퍼 추가 필요

체크리스트:
- [ ] 시그니처가 변경된 메서드 중 프로토콜 요구사항인 것이 있는가?
- [ ] 프로토콜 선언부가 새 시그니처와 일치하도록 함께 변경되었는가?
- [ ] 디폴트 파라미터만으로 적합성을 유지하려는 시도가 없는가?
```

> RIBs 아키텍처: ViewController에서 PresentableListener 프로토콜을 선언하고 Interactor가 구현.
> 시그니처 변경 시 두 파일 모두 diff에 포함되어야 한다. Interactor만 변경 시 incremental build 성공 → clean build 실패.

### 검증 4-H: Source Fidelity (원본 준수 — 리팩토링/마이그레이션 시)
```
절차:
1. diff에서 함수 호출 변경점 식별 (Before → After 패턴)
2. 변경 후 코드에 원본에 없던 파라미터/인자가 추가되었는지 확인
   - git show로 원본 코드 비교
   - optional 파라미터에 기본값(nil)이 있는데 명시적 값으로 채워졌는지
3. 추가 발견 시 → "source_deviation" 이슈 (severity: Major)

체크리스트:
- [ ] 리팩토링 diff에서 원본에 없던 파라미터가 추가되지 않았는가?
- [ ] optional 파라미터가 불필요하게 명시적 값으로 채워지지 않았는가?
- [ ] ⛔ 원본 버그 발견 시: "원본과 동일"이 이슈 dismiss 근거가 되지 않았는가? 원본 버그 발견 → 사용자에게 보고 + 수정/후속 분리 판단 요청
```

### 검증 4-I: Implication Coverage (함의 커버리지) — `modules/lead-reasoning.md` 참조. 제거/리팩토링 시 실행. 검증 4는 diff 안(judge), 4-I는 지시→diff 밖(auditor). 완료 보고에 "관찰 사항" 추가(§5).

### 검증 4-J: Concurrency Safety Audit (역방향 — 항상 실행) — `modules/safety-audit.md` 참조. diff에 동시성 키워드가 없어도 실행. 싱글톤 가변 상태 동기화+비대칭 동기화(L1 필수) + 콜백 스레드/@Published/기본값/SDK 래퍼/Task 프로퍼티 쓰기/check-then-act(L2 권장) 검사.

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
- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 참조 무결성 확인? (Serena)
- [ ] ⛔ Codex 리뷰 통과? (Critical/Major 이슈 없음 — Codex 실행 자체가 필수)
- [ ] /sc:analyze 통과? (심각한 문제 없음)
- [ ] Constraint Matrix Compliance 통과? (제약 매트릭스 부합, /fz-discover 산출물 있을 때)
- [ ] Refactoring Completeness 통과? (deprecated dead code 없음)
- [ ] Module Boundary 통과? (access control이 의도와 일치)
- [ ] ⛔ 타입 소속 검증 통과? (각 public type의 관심사가 모듈 책임에 부합)
- [ ] Anti-Pattern Enforcement 통과? (금지 패턴 0건, Plan에 Constraints 있을 때)
- [ ] UI/UX Safety 통과? (View 변경 시 시각 검증 권고)
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

예시 2 — Anti-Pattern 잔존 검증 (검증 4-F):
  BAD:  diff 삭제 라인만 확인 → "패턴 제거" 판정 (다른 파일에 잔존)
  GOOD: Plan의 Anti-Pattern Constraints Grep 패턴으로 변경 파일 + 관련 모듈 전수 검색 → 매칭 0 확인

예시 3 — Source Fidelity (검증 4-H, 리팩토링/마이그레이션):
  BAD:  컴파일+테스트 통과 → "동작 유지" 판정 (`.done` main queue → 일반 Task 미감지)
  GOOD: Transformation Spec의 실행 스레드/에러 경로/파라미터 키 3축 모두 일치 확인
```

## Boundaries

**Will**: 3중 검증(Claude+Codex+sc:analyze), 역방향 검증, Reflection Rate 정량화, 반복 개선, 완료 처리
**Will Not**: 대규모 구현 (→ /fz-code), Codex 직접 호출 (→ /fz-codex), 계획 수립 (→ /fz-plan)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| fz-codex 통신 실패 | 재시도 1회 → 실패 사실 기록 후 /sc:analyze 폴백 | Claude 자체 판단 |
| Rate < 60% 3회 | 사용자 에스컬레이션 | DEFERRED 마킹 |
| Issue Tracker 손상 | 새 세션 시작 | 수동 관리 |

## Completion → Next
Gate 5 통과 후: `/fz-commit` → `/fz-pr`
