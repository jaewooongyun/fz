---
name: fz-plan
description: >-
  계획 수립 + 요구사항 분석 + 설계 스킬. 영향 범위 분석과 구현 전략 수립.
  Use when planning features, analyzing requirements, designing architecture, or breaking down tasks.
  Do NOT use for actual code implementation (use fz-code) or code search (use fz-search).
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
  supporting: [review-arch, review-direction, memory-curator]
composable: true
provides: [planning, architecture-analysis]
needs: [refined-requirements]
intent-triggers:
  - "계획|설계|아키텍처|요구사항"
  - "plan|design|architect|requirement"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-plan - 계획 + 설계 스킬

> **행동 원칙**: 요구사항을 구조적으로 분해하고, 코드베이스 영향 분석을 통해 정확한 구현 계획을 수립한다.

## 개요

> ⛔ Phase 0 (ASD Pre-flight) → Phase 0 (Context) → Phase 0.5 (Direction Challenge) → Phase 1 (Deep Planning) → Phase 2 (Validation) ↔ Phase 3 (Feedback) → Gate 2 → /fz-code

- 요구사항 구조 분해 + 영향 범위 분석
- Serena 심볼 도구 기반 정밀 탐색

## 사용 시점

```bash
/fz-plan "새 기능 계획해줘"
/fz-plan "아키텍처를 더 상세하게 해줘"
/fz-plan "피드백 반영해서 수정해줘"
/fz-plan "Gate 2 통과 확인해줘"
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/context-artifacts.md | ASD 폴더 기반 compact recovery + 비ASD Serena checkpoint |

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
| Phase 3 | `/sc:reflect` | 피드백 반영 후 자체 검증 |

## Plugin 참조 (Swift Concurrency)

> 참조: `modules/plugin-refs.md` — Swift Concurrency(계획 시) 섹션

## 팀 에이전트 모드

> 팀 모드 규칙은 `.claude/modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("plan-{feature}")
├── Lead (Opus): 오케스트레이션 + 최종 판단
├── plan-structure (★Opus): 핵심 계획 수립 (Primary Worker)
├── review-arch (Sonnet): 아키텍처 실현성 검증
├── review-direction (Sonnet): 방향성 비판 + 대안 제시 (Phase 0.5)
├── memory-curator (Sonnet): 관련 교훈 발굴 + plan-structure에 직접 전달 [선택적: --deep 또는 복잡도 4+]
└── Cross-model 독립 검증 (Lead가 검증 실행)
```

> ASD 폴더 활성 시: `{WORK_DIR}/plan/plan-team.md`에 direction-challenge + collaborative design 핵심 통신을 기록한다.

### 통신 패턴: Collaborative Design (Peer-to-Peer)

plan-structure와 review-arch가 **만들면서 직접 토론**하여 설계를 고도화하는 패턴.
Lead를 거치지 않고 직접 SendMessage로 대화한다.

```
Round 1: plan-structure → 초안 작성 → SendMessage(review-arch): "초안입니다. 실현성 검토해주세요"
         review-arch → SendMessage(plan-structure): "Module X 의존성 역전. 대안: {제안}"
Round 2: plan-structure → 피드백 반영 + 질문 → SendMessage(review-arch): "수정했는데 Y 영향은?"
         review-arch → SendMessage(plan-structure): "Y는 OK. Z 프로토콜 변경 필요"
Round 3: 양쪽 합의 → SendMessage(team-lead): "합의 완료. 최종 설계안: {결과}"
```

**핵심**: 설계하는 **도중에** 실현성 검증이 들어오므로 완성 후 뒤집는 일이 없다.

> plan-structure 에이전트가 이 스킬의 워크플로우를 활용합니다.

---

## Phase 0: Context Loading

이전 세션 컨텍스트와 프로젝트 상태를 로드합니다.

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
   - `{WORK_DIR}/discover/constraints.md` 읽기 → 제약 매트릭스 복원
   - 있으면 Phase 1의 "요구사항 구조 분해" 스킵 가능 → 영향 분석부터

### Gate 0: Context Ready
- [ ] 프로젝트 활성화 완료?
- [ ] 대상 심볼 구조 파악?
- [ ] 이전 컨텍스트 로드? (해당 시)

---

## Phase 0.5: Direction Challenge

계획 수립 전, 요구사항의 접근 방향 자체가 최선인지 비판적으로 검토합니다.

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

## ⛔ Phase 0: ASD Pre-flight (반성 4차 — 누락 방지)

> 반성 교훈: /fz 없이 직접 호출 시 ASD 폴더가 초기화되지 않아 아티팩트가 전부 누락됨.
> 참조: `modules/context-artifacts.md` → "ASD Pre-flight" 섹션

**Phase 1 시작 전에 반드시 실행:**

1. 인자에서 `ASD-\d+` 패턴 추출
2. 패턴 있으면: `TVING/ASD-xxxx/` 폴더 존재 확인 → 없으면 `mkdir -p` + index.md 생성
3. 패턴 없으면: 비ASD 모드 (Serena Memory fallback)

### Gate 0: ASD Ready
- [ ] ⛔ 인자에서 ASD 패턴 체크 완료?
- [ ] ⛔ ASD 패턴 있으면 폴더 + index.md 존재 확인?
- [ ] WORK_DIR 결정됨?

---

## Phase 1: Deep Planning

요구사항을 구조적으로 분해하고, 영향 범위를 분석합니다.

> **프로젝트 규칙**: CLAUDE.md `## Architecture` 섹션을 따른다.

### 절차

1. **요구사항 구조 분해**:
   - /fz-discover의 `refined-requirements`가 있으면 → 이미 정제된 요구사항이므로 구조 분해 단계 생략, 바로 영향 분석으로
   - /fz-discover의 `constraint-matrix`가 있으면 → 설계 스트레스 테스트(Q1-Q6)에서 이미 발견된 제약은 재검증 생략
   - 없으면 → `mcp__sequential-thinking__sequentialthinking` → 단계별 분해 (기존 절차)

2. **코드베이스 영향 분석**:
   - `mcp__serena__find_symbol` → 변경 대상 심볼 확인
   - `mcp__serena__find_referencing_symbols` → 영향받는 심볼/파일
   - `mcp__serena__search_for_pattern` → 기존 유사 구현 패턴

   **⛔ Exhaustive Impact Scan** (반성 5차 — 누락 방지):
   > 반성 교훈: 심볼 기반 탐색만으로는 글로벌 패턴(UIWindow.motionBegan 등), 런타임 비활성 경로, 사이드이펙트 순서를 놓친다.

   심볼 기반 탐색 후 반드시 아래 4단계를 수행한다:

   a. **텍스트 전수 검색**: 대상 타입/클래스명으로 `Grep` 전수 검색.
      심볼 기반에서 찾은 참조와 대조하여 **빠진 참조**가 없는지 확인.
      특히 문자열 참조, 글로벌 hook, extension 내 사용을 잡는다.
   b. **런타임 도달성 검증**: 발견된 각 진입점(호출부)에 대해 실제 런타임에 도달 가능한지 확인.
      코드 경로가 존재해도 UI 바인딩(gesture/button)이 없거나, feature flag로 비활성이면 "latent(잠재)" 표기.
      검증 방법: 진입점의 view layer까지 추적하여 trigger가 존재하는지 확인.
   c. **사이드이펙트/순서 분석**: 리팩토링 대상의 기존 액션 패턴에서 순서 의존성 식별.
      예: `dismiss(animated:) completion → action` 패턴은 순서가 바뀌면 동작이 달라짐.
      각 액션의 전제조건(pre-condition)과 부작용(side-effect)을 나열.
   d. **Dead code 감지**: 변경 대상과 관련된 파일에서 미사용 헬퍼/메서드 식별.
      `find_referencing_symbols` 결과가 0이면 dead code 후보 → 이관 대상에서 제외 + 삭제 후보로 기록.
   e. **⛔ 소비자 코드 품질 스캔** (모듈화/캡슐화 작업 시 필수):
      모듈 경계를 만드는 작업에서는 경계 양쪽을 모두 분석해야 한다.
      `Grep(pattern="import {모듈명}", path=앱 소스 루트)` → 앱 측 소비자 파일 전수 수집.
      각 소비자의 사용 패턴이 모듈 설계 의도와 일치하는지 확인.
      앱 생명주기 진입점(AppDelegate, SceneDelegate, UIWindow extension 등)의 모듈 연동 코드 확인.
      계획에 소비자 코드 변경 Step을 명시적으로 포함.

3. **API/라이브러리 문서 확인**:
   - `mcp__context7__resolve-library-id` → 라이브러리 ID
   - `mcp__context7__query-docs` → 최신 API 문서, 호환성
   - **라이브러리 버전업 시**: Context7로 새 버전 API 확인. 동일 동작을 가장 적은 코드로 표현하는 것이 진짜 최소 변경이다 (bridge 유지보다 native 직접 호출이 코드가 적으면 전환). 단, 동작 변경(프로토콜 시그니처, 실행 순서)은 최소 변경의 범위 밖이다.

4. **SuperClaude 연계** (필요 시):
   - `/sc:design` → 새 아키텍처 설계
   - `/sc:brainstorm` → 요구사항 탐색
   - `/sc:analyze` → 기존 코드 심층 분석
   - `/sc:research` → 외부 기술 조사
   - `/sc:workflow` → PRD/요구사항 → 구현 워크플로우 자동 생성
     (트리거: 구현 Step이 5개 이상 예상될 때)
   - `/sc:spec-panel` → 아키텍처 스펙 전문가 패널 리뷰
     (트리거: 새 모듈 생성 시, --deep 옵션 시)
     (모드: `--mode critique --focus architecture`)

5. **설계 스트레스 테스트** (Design Stress Test):
   계획의 핵심 설계 결정(새 타입, 패턴 변경, 추상화 도입 등)에 대해 6가지 질문으로 스트레스 테스트.
   - `mcp__sequential-thinking__sequentialthinking` → 설계 결정별 순차 검증

   | 질문 | 내용 | 실패 시 행동 |
   |------|------|-------------|
   | Q1 다중성 | 이 설계가 1개일 때와 N개일 때 동일하게 작동하는가? | 다중 시나리오에서 소비자 영향 추가 분석 |
   | Q2 소비자 영향 | 변경의 소비자(상위 레이어)에 새 분기/타입/프로토콜이 필요한가? | 소비자 변경을 계획에 포함 |
   | Q3 복잡도 이동 | 한 레이어의 단순화가 다른 레이어의 복잡도 증가로 이어지는가? | 이동 대상 레이어의 변경도 계획에 포함 |
   | Q4 경계 케이스 | 이 추상화가 커버하지 못하는 케이스는 무엇이고, 대안은? 상태 저장이 포함된 설계라면: 이 상태가 컴포넌트 라이프사이클 밖(앱 재시작)에서도 유지되어야 하는가? RIBs Interactor/VC가 살아있는 동안 인메모리(Subject/State)로 충분하지 않은가? A/B 테스트 등 외부 시스템이 관리하는 값을 앱 로컬에 캐싱하면 실험 왜곡 위험. | 대안 패턴 제시 + 하이브리드 가능성 검토. 영속화 불필요 판정 시 인메모리 대안 제시 |
   | Q5 접근 경계 | "차단/제거/캡슐화"를 의도한 접근 경로가 실제로 차단되는가? access modifier(public/internal/private)가 의도와 일치하는가? 기존 코드가 이벤트 채널을 우회하여 직접 호출하는 경로가 남아있지 않은가? | 접근 제어 변경을 계획에 포함 + Anti-Pattern Constraints에 금지 패턴 기록 |
   | Q6 이벤트 스코프 | 이벤트/로그 전송이 포함된 설계라면: 각 이벤트가 명시된 측정 목적에 부합하는가? 모든 사용자에게 동일하게 발화하는 이벤트(impression 등)가 A/B 분류 목적에 포함되어 있지 않은가? 이벤트 발화 위치의 컨텍스트가 측정 대상과 일치하는가? (예: 전체 콘텐츠 재생 이벤트에 라이브 전용 A/B 프로퍼티 추가는 스코프 불일치) | 불필요한 이벤트 제거 + 이벤트별 측정 목적 명시 |

   - 각 질문에서 리스크 발견 → 리스크 매트릭스에 기록
   - Q4에서 대안 패턴 최소 1개 필수 제시
   - Q5는 리팩토링/캡슐화 작업에서 특히 중요 — 기존 코드의 잔존 접근 경로를 Grep으로 사전 검색
   - 6가지 질문 모두 "문제없음"이면 → 그 판단 근거를 명시 (빈 리스크 = 분석 부족 의심)
   - **Evaluator-Optimizer**: Q1-Q6에서 Critical 리스크 2개+ 발견 시 → 계획 자동 재작성 (최대 2회 반복)
     - 1회차: Critical 리스크를 계획에 반영하여 재작성 → 스트레스 테스트 재실행
     - 2회차: 여전히 Critical 2개+ → 사용자 에스컬레이션 (AskUserQuestion: "리스크 수용/계획 변경/중단")
     - LOOP 모드 파라미터: `completion-promise: STRESS_TEST_PASS`, `max-iterations: 2`

6. **구조화된 계획 출력**:
   - 구현 단계 목록 (Step별 변경 대상, 방법)
   - 영향받는 심볼/파일 목록
   - 필요한 API/라이브러리 정보
   - **리스크 매트릭스**: 설계 스트레스 테스트에서 발견된 리스크
     | 리스크 | 발생 조건 | 영향 레이어 | 대응 |
     |--------|----------|-----------|------|
   - **소비자 변경 요약**: Q2에서 식별된 상위 레이어 변경사항
   - **대안 패턴**: Q4에서 제시된 대안 + 현재 선택의 근거
   - **Anti-Pattern Constraints** (리팩토링 후 금지 패턴):
     리팩토링/캡슐화 작업에서 필수. 리팩토링 후 코드베이스에 존재하면 안 되는 패턴 목록.
     /fz-code의 잔존 패턴 검사와 /fz-review의 enforcement 검증에서 이 목록을 사용한다.
     | # | 금지 패턴 | 검증 Grep 패턴 | 위반 시 영향 |
     |---|----------|---------------|-------------|
     예시: `| 1 | proxy 외부 접근 | \.proxy\. | 식별 가능 → 목표 무력화 |`

7. **⛔ 계획 파일 기록** (항상 — compact recovery 필수):
   - ASD 활성: `{WORK_DIR}/plan/plan-v{N}.md` + `{WORK_DIR}/index.md` 업데이트
   - 비ASD: `write_memory("fz:checkpoint:plan-v{N}", "Steps: {N}개. 핵심결정: {요약}. 리스크: {요약}")`
   형식 참조: `modules/context-artifacts.md`

### Gate 1: Plan Ready
- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 영향 범위 분석 완료?
- [ ] ⛔ Exhaustive Impact Scan 4단계 수행 완료? (반성 5차)
  - [ ] 텍스트 전수 검색(Grep)으로 심볼 기반 결과와 대조했는가?
  - [ ] 각 진입점의 런타임 도달성을 검증했는가? (latent 표기 포함)
  - [ ] 기존 액션 패턴의 사이드이펙트/순서 의존성을 분석했는가?
  - [ ] 관련 파일의 dead code를 감지했는가?
  - [ ] ⛔ 모듈화 작업이면 소비자 코드 품질 스캔(e단계)을 수행했는가?
- [ ] API 문서 확인 완료? (새 API 사용 시)
- [ ] 기존 패턴과 일관성 확인?
- [ ] 구현 단계가 명확하게 정의?
- [ ] 설계 스트레스 테스트(Q1-Q6) 수행 완료?
- [ ] 소비자 영향이 식별되었으면 계획에 반영?
- [ ] 대안 패턴 최소 1개 제시?
- [ ] 리팩토링 작업이면 Anti-Pattern Constraints 작성?
- [ ] ⛔ 계획 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)

---

## Phase 2: Plan Validation

계획을 검증합니다. **독립 검증 도구를 활용합니다.**

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

검증 피드백을 분석하고 계획을 수정합니다.

### 절차

1. **피드백 심화 분석**:
   - `mcp__sequential-thinking__sequentialthinking` → 이슈별 심각도 분류
     - **Critical**: 즉시 수정 필수
     - **Major**: 수정 권장
     - **Minor**: 선택적 수정

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

코드 수정은 /fz-code 또는 /fz-fix에 위임한다. 이 스킬은 계획 수립과 검증만 수행한다.

**Will**:
- 요구사항 구조 분해 및 영향 분석
- Serena 기반 코드베이스 탐색
- 구조화된 구현 계획 출력
- 계획 검증

**Will Not**:
- 코드 직접 수정 (→ /fz-code)
- 빌드 실행 (→ /fz-code)

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
