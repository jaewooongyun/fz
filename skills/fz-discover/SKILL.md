---
name: fz-discover
description: >-
  This skill should be used when the user is unsure about approach and needs guided exploration.
  Make sure to use this skill whenever the user says: "어떻게 하면 좋을까?", "뭐가 좋을까?",
  "트레이드오프 비교", "고민이야", "방식이 여러 개인데", "요구사항이 불명확", "제약 조건 파악",
  "how should I approach this?", "what's the trade-off?", "I'm not sure which way to go",
  "help me figure out requirements", "compare approaches".
  Covers: 어떻게, 뭐가 좋을까, 트레이드오프, 고민, 방식, 제약조건 발견, 소크라테스식 대화.
  Do NOT use when requirements are already clear (use fz-plan) or for code search (use fz-search).
user-invocable: true
argument-hint: "[해결하고 싶은 문제/질문]"
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
  Read, Grep, Glob
team-agents:
  primary: plan-structure
  supporting: [review-arch]
composable: true
provides: [refined-requirements, constraint-matrix, decision-rationale]
needs: [none]
intent-triggers:
  - "어떻게.*좋을까|어디에.*좋을까|뭐가.*맞을까|괜찮을까"
  - "방법.*찾|최적.*찾|요구.*조건|제약|트레이드오프"
  - "이게.*맞아|이렇게.*해도|어떤.*방식|비교.*해줘"
  - "맞는지|차이점|놓치고|어떻게.*생각"
  - "how.*should|where.*should|what.*best|trade.?off|difference|missing|what.*think"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-discover - 제약조건 발견 + 요구사항 정제 스킬

> **행동 원칙**: 문제가 불명확할 때, 대화를 통해 제약조건을 하나씩 발견하고 모든 제약을 만족하는 해로 수렴한다. "거절할 때 즉시 대안을 제시"하는 Reject-Extract-Propose 프로토콜을 적용한다.

## 개요

> ⛔ Phase 0 (ASD Pre-flight) → Phase 1 (Problem Framing) → Phase 2 (Iterative Constraint Discovery) ↔ 사용자 대화 → Phase 3 (Convergence) → Phase 4 (Handoff)

- 발산 후 수렴 (Diamond): 넓게 탐색한 후 제약으로 좁히기
- Reject-Extract-Propose 프로토콜: 거절 → 제약 추출 → 대안 제시를 한 턴에
- 제약 매트릭스: 대화 과정에서 점진적으로 채워지는 핵심 산출물
- 코드 탐색 연동: 제약 검증을 위한 /fz-search 수준의 탐색 수행

## 사용 시점

```bash
/fz-discover "이 기능을 어떻게 구현하면 좋을까?"         # 불명확한 요구사항 정제
/fz-discover "이 두 방법 중 어느게 나을까?"              # 트레이드오프 비교
/fz-discover "이렇게 사용해도 맞는지 확인해줘"          # 검증 요청
/fz-discover "이 방식에 놓치고 있는게 있을까?"          # 맹점 탐지
/fz-discover "A랑 B 차이점이 뭐야?"                    # 비교 질문
/fz-discover "이 설계 어떻게 생각해?"                    # 의견 요청
/fz-discover "팀원이 이런 우려를 제기했는데"              # 우려 기반 제약 발견
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (Adversarial Constraint Discovery 패턴) |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |

## sc: 활용 (SuperClaude 연계)

| Phase | sc: 명령어 | 용도 |
|-------|-----------|------|
| Phase 1 | `/sc:analyze` | 기존 코드/아키텍처 분석으로 암묵적 제약 사전 식별 |
| Phase 2 | `/sc:brainstorm` | 후보 옵션 발산이 필요할 때 |
| Phase 2 | `/sc:explain` | 기존 패턴/규칙의 교육적 설명 |
| Phase 3 | `/sc:reflect` | 수렴된 결과 자체 검증 |
| Phase 4 | `→ /fz-plan` | 정제된 요구사항으로 구현 계획 수립 |

## Plugin 참조

> 참조: `modules/plugin-refs.md` — SwiftUI Expert(상태 관리 결정 시) + Swift Concurrency(동시성 관련 제약 시)

## 팀 에이전트 모드

> 팀 모드 규칙은 `.claude/modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("discover-{topic}")
├── Lead (Opus): 퍼실리테이터 + 사용자 대화 + 제약 매트릭스 관리
├── plan-structure (★Opus): 대안 생성 + 실현성 평가 (Primary Worker)
├── review-arch (Sonnet): 제약 발견 + 아키텍처 위반 감지
└── (선택) Codex CLI: cross-model 제약 교차 검증 (Lead가 /fz-codex verify 실행)
```

> ASD 폴더 활성 시: `{WORK_DIR}/discover/discover-team.md`에 에이전트 간 핵심 통신 요약을 기록한다.

### 통신 패턴: Adversarial Constraint Discovery (Peer-to-Peer)

plan-structure가 **옵션을 만들고** review-arch가 **제약 위반을 찾는** 반복 루프.
Lead는 사용자 대화를 관리하고, 제약 매트릭스를 업데이트한다.

```
Round 1 (옵션 생성 + 제약 발견):
  Lead → 팀에 문제 전파 + 코드 컨텍스트 공유
  plan-structure: 후보 옵션 2-3개 생성
  → SendMessage(review-arch): "후보입니다. 제약 위반 찾아주세요: {옵션들}"

  review-arch: 각 후보의 제약 위반 식별
  → SendMessage(plan-structure): "옵션 A는 C1 위반, 옵션 B는 C2 위반. 근거: {코드 참조}"

Round 2 (대안 생성 + 재검증):
  plan-structure: 위반 안 하는 새 옵션 생성
  → SendMessage(review-arch): "새 옵션 D입니다. 기존 제약 C1, C2 모두 회피. 확인해주세요"

  review-arch: 새 옵션 검증 + 새 제약 발견 시 추가
  → SendMessage(plan-structure): "C1, C2는 OK. 새 제약 C3 발견: {근거}"

Round 3 (수렴):
  plan-structure + review-arch: 합의
  → SendMessage(team-lead): "옵션 D + 제약 매트릭스. C3은 트레이드오프로 수용"
```

핵심: plan-structure가 만들고, review-arch가 부순다. 이 adversarial 루프에서 제약이 드러난다.

> plan-structure 에이전트가 이 스킬의 워크플로우를 활용합니다.

---

## 핵심 추론 프로토콜: Reject-Extract-Propose (REP)

모든 Phase에서 적용하는 3가지 추론 규칙:

### 규칙 1: 거절할 때 즉시 대안 제시

```
BAD:  "proxy에 @Published는 안 됩니다."
GOOD: "proxy에 @Published는 안 됩니다.
       이유: objectWillChange가 모든 관찰 뷰를 재렌더링 (제약 C1).
       대안: plain Dictionary로 비반응형 저장 → @State에서 반응형 미러링."
```

한 턴에 세 가지를 모두 포함: (1) 거절 (2) 왜 안 되는지 제약 추출 (3) 그 제약을 피하는 대안.

### 규칙 2: 본질이 같은 옵션은 합치기

```
BAD:  "방법 A: init 파라미터, 방법 B: Environment. 어떤 걸 선택하시겠어요?"
GOOD: "두 방법 모두 BandScope가 외부 Binding을 받는 것이므로 본질적으로 같습니다.
       기존 패턴(selectedBandItem, isVisible)은 init 파라미터를 사용하므로 일관성상 파라미터."
```

겉보기 다른 옵션이 같은 메커니즘이면 하나로 합치고, 진짜 다른 축만 분리.

### 규칙 3: 새 제약 발견 시 기존 옵션 재평가

```
새 제약 "BoardViewModel이 없다" 발견
→ 기존 옵션 중 "ViewModel에 @Published" 방안 즉시 탈락
→ 제약 매트릭스에 추가
→ 남은 후보만으로 재수렴
```

---

## ⛔ Phase 0: Work Dir Resolution

> 참조: `modules/context-artifacts.md` → "Work Dir Resolution" 섹션

**Phase 1 시작 전에 반드시 실행:**

1. 인자에서 `ASD-\d+` 패턴 추출 (예: `[ASD-542]`)
2. 패턴 있으면 → **무조건 자동 저장**:
   - `{CWD}/ASD-xxxx/` 폴더 존재 확인 → 없으면 `mkdir -p` + index.md 생성
   - `{CWD}/ASD-xxxx/discover/` 서브폴더 생성
   - WORK_DIR 설정
2b. index.md 존재 시 → Active Phase 읽기 → DISCOVER_TAG 설정 (없으면 "journal")
   - Active Phase = "plan" → DISCOVER_TAG = "plan"
   - Active Phase = "code" → DISCOVER_TAG = "code"
   - Active Phase = "review" → DISCOVER_TAG = "review"
   - Active Phase = "discover" 또는 없음 → DISCOVER_TAG = "journal"
3. 패턴 없으면:
   a. 브랜치명에서 `ASD-\d+` 추출 시도 → 있으면 2번과 동일
   b. 없으면 → **AskUserQuestion**: "이 작업의 산출물을 파일로 저장할까요?"
      - 예 → `{CWD}/NOTASK-{YYYYMMDD}/discover/` 생성 + WORK_DIR 설정
      - 아니오 → Serena Memory fallback (경량)

### Gate 0: Work Dir Ready
- [ ] ⛔ 인자/브랜치에서 ASD 패턴 체크 완료?
- [ ] ASD 패턴 있으면 폴더 자동 생성 완료?
- [ ] 패턴 없으면 사용자에게 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD / NOTASK / Serena fallback)
- [ ] DISCOVER_TAG 설정됨? (index.md Active Phase 기반)

---

## Phase 1: Problem Framing

사용자 질문에서 핵심 문제를 추출하고, 코드 탐색으로 암묵적 제약을 사전 식별합니다.

### 절차

1. **문제 추출**:
   - 사용자 질문에서 핵심 결정 사항(decision point) 식별
   - "어디에 저장?" → 상태 관리 결정
   - "어떤 방식?" → 패턴 선택 결정

2. **관련 코드 탐색**:
   - `mcp__serena__find_symbol` → 언급된 타입/심볼 구조 확인
   - `mcp__serena__get_symbols_overview` → 주변 심볼 컨텍스트
   - `mcp__serena__find_referencing_symbols` → 영향 범위 파악
   - `mcp__serena__search_for_pattern` → 기존 유사 패턴 검색

3. **암묵적 제약 사전 식별**:
   - CLAUDE.md `## Architecture` 섹션에서 오는 제약
   - 아키텍처 패턴에서 오는 제약
   - 기존 코드 패턴에서 오는 일관성 제약

4. **초기 제약 매트릭스 구성**:

   ```markdown
   | # | 제약 | 출처 | 확신도 |
   |---|------|------|--------|
   | C1 | ... | 아키텍처 원칙 | 높음 |
   | C2 | ... | 코드 탐색 | 중간 |
   ```

### Gate 1: Problem Framed
- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 핵심 결정 사항이 명확하게 식별되었는가?
- [ ] 관련 코드 구조를 탐색했는가?
- [ ] 초기 제약이 1개 이상 식별되었는가?

---

## Phase 2: Iterative Constraint Discovery

후보 옵션을 제시하고, 사용자 대화를 통해 제약을 발견하며, 제약 매트릭스를 갱신합니다.

### 절차 (매 라운드)

1. **후보 옵션 제시** (2-3개):
   - 각 옵션의 작동 방식 간결 설명
   - 각 옵션이 만족/위반하는 제약 명시
   - REP 규칙 2 적용: 본질이 같은 옵션은 합침

2. **사용자 피드백 수집**:
   - 직접 질문 또는 팀원 우려 → 새 제약으로 변환
   - "보일러플레이트가 너무 많지 않을까?" → C5: caller 보일러플레이트 최소화
   - "모든 화면에서 해야 하나?" → C6: 범용성 요구

3. **제약 검증 (필요 시)**:
   - 코드 탐색으로 제약의 실재 여부 확인
   - `mcp__serena__find_symbol` → "정말 BoardViewModel이 없는지?"
   - `Grep` → "기존에 이 패턴을 쓰는 곳이 몇 개인지?"

4. **제약 매트릭스 갱신**:
   - 새 제약 추가
   - REP 규칙 3 적용: 기존 옵션 재평가
   - 탈락 옵션은 탈락 사유와 함께 기록

5. **수렴 판단**:
   - 모든 제약을 만족하는 후보가 1개 → Phase 3으로
   - 모든 후보가 1개 이상 제약 위반 → 트레이드오프 명시 + 사용자 선택
   - 새 제약이 계속 나옴 → 라운드 계속 (사용자가 plan 전환을 결정할 때까지)

6. **⛔ 저널 갱신** (항상 — compact recovery 필수):
   `discover-{DISCOVER_TAG}.md` 갱신:
   - DISCOVER_TAG = "journal" → **전체 덮어쓰기** (매 라운드). compact 후 이 파일 하나만 Read하면 전체 복원.
   - DISCOVER_TAG = plan|code|review → **APPEND** + topic header (동일 phase 다중 discover 지원)
   - ASD 활성: `{WORK_DIR}/discover/discover-{DISCOVER_TAG}.md` + `{WORK_DIR}/index.md` 업데이트
     - journal: 파일 전체를 매 라운드 갱신 (~2K tokens). 상세하게 기록: 제약 매트릭스, 생존/탈락 후보, 핵심 결정 흐름, 미결 질문.
     - phase: APPEND + `## Topic: {질문 요약}` header. 1K tokens 초과 시 이전 topic 압축.
     - Round History는 유지하지 않음 — 탈락 후보 사유가 롤백 근거 역할.
   - 비ASD: `write_memory("fz:checkpoint:discover-{DISCOVER_TAG}", "제약 {N}개: {C1~CN}. 생존: {후보}. 핵심 추론: {요약}")` (매 라운드 덮어쓰기)
   형식 참조: `modules/context-artifacts.md` → "예시 2: discover-journal.md (discover-journal 형식)"

### discover-journal 형식

> 형식 상세 + 예시: `modules/context-artifacts.md` → "예시 2: discover-journal.md (discover-journal 형식)" 참조.
> 원칙: "이것만 읽으면 대화 없이도 판단할 수 있는" 수준의 상세도 유지.
> 필수 섹션: 제약 매트릭스, 생존 후보, 탈락 후보(사유), 미결 질문.

### 라운드 대화 출력 (사용자에게 보여주는 형식)

매 라운드: 새 제약 테이블 + 후보 평가 매트릭스(C1~CN × 후보) + 다음 질문.

### Gate 2: Constraints Sufficient
- [ ] 핵심 제약이 3개 이상 식별되었는가?
- [ ] 생존 후보가 1-2개로 좁혀졌는가?
- [ ] 사용자가 추가 우려를 제기하지 않았는가?

---

## Phase 3: Convergence

모든 제약을 만족하는 최종 해를 도출하고, 결정 근거를 정리합니다.

### 절차

1. **최종 해 도출**:
   - `mcp__sequential-thinking__sequentialthinking` → 최종 후보가 모든 제약을 만족하는지 단계별 검증
   - 만족 불가능 시: 어떤 제약을 완화할지 사용자에게 선택권 제시

2. **결정 근거 정리**:
   - 왜 이 해가 선택되었는지 (다른 후보가 탈락한 제약 명시)
   - 수용한 트레이드오프 (있다면)
   - 관련 코드 참조 (기존 패턴과의 일관성 근거)

3. **최종 산출물 생성**:
   - 제약 매트릭스 최종본
   - 정제된 요구사항 (구현에 필요한 구체적 사항)
   - 결정 근거 요약

4. **⛔ 저널 최종 갱신** (항상 — compact recovery 필수):
   `discover-{DISCOVER_TAG}.md`의 Current State를 최종본으로 갱신하고, 정제된 요구사항 섹션을 추가한다.
   - ASD 활성: `{WORK_DIR}/discover/discover-{DISCOVER_TAG}.md` Current State 최종 갱신 + `{WORK_DIR}/index.md` 업데이트
   - 비ASD: `write_memory("fz:checkpoint:discover-{DISCOVER_TAG}-final", "제약 {N}개. 채택: {옵션}. 정제 요구사항: {요약}")`

### 최종 산출물 형식

> 형식 참조: `modules/context-artifacts.md` → "최종 산출물 확장 (Phase 3 수렴 시)"

### Gate 3: Converged
- [ ] 최종 해가 모든 제약을 만족하는가? (또는 트레이드오프가 명시되었는가?)
- [ ] 결정 근거가 명확한가?
- [ ] 정제된 요구사항이 구현 가능한 수준으로 구체적인가?
- [ ] ⛔ 아티팩트 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)

---

## Phase 4: Handoff

산출물을 다음 스킬로 전달하거나, 독립적으로 완료합니다.

### 핸드오프 경로

| 상황 | 다음 스킬 | 전달 내용 |
|------|----------|----------|
| 구현 계획 필요 | `/fz-plan` | 정제된 요구사항 + 제약 매트릭스 |
| 즉시 구현 가능 | `/fz-code` | 결정 근거 + 요구사항 (단순한 경우) |
| PR 코멘트 작성 | 직접 출력 | 결정 근거를 코멘트 형식으로 가공 |
| 토론 결과 기록 | Serena memory | 결정사항 + 제약 영속화 |

> ASD 폴더 활성 시: 다음 스킬이 `{WORK_DIR}/discover/discover-{DISCOVER_TAG}.md`의 Current State 섹션을 읽어 컨텍스트를 복원한다. (DISCOVER_TAG = index.md Active Phase 기반: journal|plan|code|review)

### 절차

1. **상황 판단**: 사용자 의도에 따라 핸드오프 경로 결정

2. **산출물 전달**:
   - `/fz-plan`으로 전환 시: 정제된 요구사항이 /fz-plan Phase 1의 입력이 됨
     - /fz-plan은 "요구사항 구조 분해" 단계를 건너뛰고 "영향 분석"부터 시작
   - PR 코멘트 시: 제약 매트릭스 + 결정 근거를 읽기 쉬운 형태로 가공
   - 기록 시: `mcp__serena__write_memory` → 결정사항 영속화

3. **완료 보고**:

   ```markdown
   /fz-discover 완료

   **문제**: {원래 질문 요약}
   **제약**: {N}개 발견 (Phase 1: {X}개, 대화: {Y}개)
   **결론**: {채택된 해 한 줄 요약}
   **라운드**: {N}회

   **다음 단계**:
   - /fz-plan → 구현 계획 수립
   - /fz-code → 직접 구현 (단순한 경우)
   ```

---

## SOLO vs TEAM 판단

| 기준 | SOLO | TEAM |
|------|------|------|
| 예상 제약 수 | 2-3개 | 5개+ |
| 범위 | 단일 모듈/파일 | 여러 모듈/레이어 |
| 아키텍처 판단 | 불필요 | 필요 |
| 사용자 즉시 피드백 | 가능 | 사용자 대기 가능 |
| 예시 | "이 함수를 어떻게 리팩토링?" | "상태 관리를 어떻게?" |

---

## Few-shot 예시

```
BAD (제약 없이 바로 추천):
사용자: "상태 관리를 어떻게 하면 좋을까?"
답변: "@StateObject를 쓰세요."
→ 제약 탐색 없이 단일 정답 제시. 코드 구조/기존 패턴 미확인.

GOOD (REP 프로토콜 + 제약 발견):
사용자: "상태 관리를 어떻게 하면 좋을까?"
Phase 1: find_symbol → 기존 ViewModel 구조 확인, 기존 패턴(@Published + Combine) 식별
→ 초기 제약: C1(RIBs Interactor가 비즈니스 로직 담당), C2(기존 Combine 기반)
Round 1: 후보 A(@StateObject), B(Interactor→ViewModel), C(직접 @State)
→ 각 후보가 C1, C2 만족/위반 여부 명시
→ 사용자 피드백으로 C3(보일러플레이트 최소화) 발견
Round 2: 후보 B 탈락(C3 위반), 새 후보 D 생성
→ 제약 매트릭스 갱신 → 수렴
```

```
BAD (본질 같은 옵션 분리):
"방법 1: init 파라미터 주입, 방법 2: Environment 주입. 어떤 걸 선택?"
→ 두 방법 모두 외부 주입이라는 동일 메커니즘. 진짜 다른 축 없이 분리.

GOOD (본질 같은 옵션 합치기):
"두 방법 모두 외부 주입이므로 본질적으로 동일합니다.
기존 패턴(init 파라미터)과 일관성 유지 → init 파라미터 채택.
진짜 다른 축은 '외부 주입 vs 내부 생성'입니다."
```

---

## Boundaries

**Will**:
- 대화를 통한 제약조건 발견 + 요구사항 정제
- Reject-Extract-Propose 프로토콜 적용
- 제약 매트릭스 점진적 구축
- 코드 탐색 기반 제약 검증
- 정제된 요구사항 → /fz-plan, /fz-code 핸드오프
- PR 코멘트 형태의 결정 근거 출력

**Will Not**:
- 코드 직접 수정 (→ /fz-fix 또는 /fz-code)
- 구현 계획 수립 (→ /fz-plan)
- 빌드 실행 (→ /fz-code)
- 명확한 요구사항의 단순 설계 (→ /fz-plan)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| 사용자 응답 없이 수렴 불가 | 현재까지의 제약 매트릭스 출력 + 판단 보류 | AskUserQuestion |
| 장기 대화 (5라운드+) | context budget 상태 안내 + 아티팩트 기록 확인 | 계속 진행 |
| Serena 연결 실패 | Grep + Glob 폴백 | 코드 없이 원칙 기반 추론 |
| TEAM 에이전트 스폰 실패 | SOLO 폴백 | Lead 단독 REP 실행 |
| 모든 후보 탈락 | 제약 완화 제안 | 사용자에게 제약 우선순위 질문 |

## Completion → Next

수렴 완료 후:
```bash
/fz-plan "정제된 요구사항대로 계획 세워줘"   # 구현 계획으로 전환
/fz-code "결정대로 구현해줘"                 # 단순한 경우 직접 구현
```
