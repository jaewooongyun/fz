# Context Artifact 관리

> **Sources (last audited: 2026-09-25 — 모델 사실 축: Opus 5.5 1M 기본값·캐시 최소 prefix 두 줄만 대조, tokenizer 줄은 5.5 진술 부재로 2026-07-25 판 그대로):** `guides/llm-references.md` §1 정본 대조 완료 (Opus 5 1M context·tokenizer·프롬프트 캐시 최소 512 반영).
>
> 아티팩트를 파일로 기록한다. 대화 컨텍스트는 compact 시 손실되지만 파일은 남는다.

## 목차

- [핵심 원칙](#핵심-원칙)
- [폴더 구조](#폴더-구조)
- [Work Dir 결정](#work-dir-결정)
- [index.md 프로토콜](#indexmd-프로토콜)
- [Compact Recovery Protocol](#compact-recovery-protocol)
- [Proactive Context Protocol](#proactive-context-protocol)
- [Upstream Hydration Sets](#upstream-hydration-sets)
- [Phase-Tagged Discover](#phase-tagged-discover)
- [Ephemeral vs Persistent (/btw 통합)](#ephemeral-vs-persistent-btw-통합)
- [파이프라인 길이별 저장](#파이프라인-길이별-저장)
- [Artifact Token Budget](#artifact-token-budget)
- [실행 기록](#실행-기록)
- [Few-shot 예시](#few-shot-예시)
- [Edge Case 대응](#edge-case-대응)
- [참조 스킬](#참조-스킬)
- [⛔ Work Dir Resolution (모든 fz-* 스킬 필수)](#-work-dir-resolution-모든-fz--스킬-필수)
- [사전 예방적 Context 관리](#사전-예방적-context-관리)
- [설계 원칙](#설계-원칙)

---

## 핵심 원칙

- 아티팩트를 파일로 기록하는 이유: compact 후에도 Read로 복원할 수 있다.
- index.md를 유지하는 이유: 새 세션에서 한 파일만 읽으면 전체 맥락을 파악할 수 있다.
- artifact 로드 합계를 제한하는 이유: 과도한 파일은 context re-explosion을 유발한다.

## 폴더 구조

```
{CWD}/{TICKET}/          # 예: TKT-1234/ · 또는 {CWD}/NOTASK-{YYYYMMDD}/
├── index.md              # Compact recovery 엔트리 포인트 (Essential Context=덮어쓰기, Artifacts=append)
├── discover/
│   ├── discover-journal.md  # plan 전 discover (canonical)
│   ├── discover-plan.md     # plan 실행 중 ad-hoc (Phase-Tagged)
│   ├── discover-code.md     # code 실행 중 ad-hoc (Phase-Tagged)
│   └── discover-review.md   # review 실행 중 ad-hoc (Phase-Tagged)
├── plan/
│   ├── plan-v1.md ~ plan-vN.md
│   ├── plan-final.md
│   ├── direction-challenge.md  # Phase 0.5 방향성 도전 결과 (PROCEED/RECONSIDER/REDIRECT)
│   └── verify-result.md        # Phase 2 검증 verdict + 이슈 요약
├── code/
│   ├── step-1.md ~ step-N.md
│   └── progress.md       # 전체 진행 상태 (누적형 — 이전 Step 핵심 결정 한 줄씩 유지)
├── fix/
│   └── fix-analysis.md   # fz-fix 원인 분석 + 수정 기록
├── search/
│   └── search-result.md  # fz-search 탐색 결과
└── review/
    └── self-review.md     # fz-review 자기 리뷰 결과
```

### Standalone Work Dir (peer-review)

fz-peer-review는 티켓 폴더와 별도 WORK_DIR을 사용:

```
{PROJECT_ROOT}/peer-review-{PR_NUMBER}/
├── review-index.md
├── synthesized-issues.json
├── merged.json                # review_merge.py 병합본 — Curate 후보 원본
├── merged-prethread.json      # 같은 diff 의 첫 병합본(스레드 읽기 전 고정 · '기존 스레드 대비 독립 발견' 표 근거 — F-643)
├── existing-threads.json      # gather 가 모은 기존 스레드(status ok · unavailable · not-a-pr)
├── target.json                # 리뷰 대상 {kind, ref, sha} — evidence · Serena 트리 @sha 대조 기준
├── review.json                # 판정 · 코멘트(issues) · 제외(excluded) — 렌더러 단일 출처
├── review-report.md
├── pr-comments.md
└── {agent}-result.json        # raw 에이전트 결과 (arch, quality, gpt)
```

> 티켓 폴더 트리 내 중첩하지 않는 이유: peer-review는 PR 단위로 독립 실행되며, 티켓 작업과 무관할 수 있다.

> `{CWD}` = PROJECT_ROOT (CLAUDE.md가 위치한 디렉토리). GIT_ROOT 와 다를 수 있음. 개인 산출물은 PROJECT_ROOT에만 생성.

## Work Dir 결정

우선순위: 명시적 인자 {TICKET} > 브랜치명 (`[A-Z]{2,6}-\d{2,5}` 추출) > AskUserQuestion(저장 여부) > fallback: 저장 없이 진행(이어받기 없음)

## index.md 프로토콜

index.md는 두 섹션으로 구성: `## Essential Context`(덮어쓰기)와 `## Artifacts`(append-only).

```markdown
# {TICKET} Context Index

## Active Phase: code

## Essential Context (매 Phase 완료 시 /fz가 덮어쓰기)
- Mode: TEAM
- Key Decisions:
  - [plan] ObservableObject 채택 (iOS 16 호환)
  - [code] Step 1/3 완료, Repository 구현
- Constraints: C1(RIBs), C2(Combine), C4(iOS 16)
- Pending: Step 2 ViewModel 구현

## Artifacts (append-only — 기존 Phase 엔트리 유지)
- [discover] discover-journal.md — Round 2 기준
- [discover-code] discover-code.md — code 중 ad-hoc (Phase-Tagged)
- [plan] plan-final.md — 사용자 승인
- [code] step-1.md — Repository 완료
```

> **핵심**: `## Essential Context`는 /fz가 단독 관리하는 **덮어쓰기** 섹션. 서브스킬은 Essential 항목을 반환하고 /fz가 기록한다. /fz 없이 직접 호출된 스킬은 그 스킬의 Lead 가 완료할 때 Essential Context(Active Phase · Key Decisions · Constraints · Pending)를 덮어쓴다 — /fz 파이프라인 안에서는 덮어쓰지 않고 항목만 /fz 에 돌려준다.

### plan-final.md 템플릿 (OBS-03 v2.2 P0-A)

`plan-final.md`는 다음 3개 섹션을 분리 명시 (scope creep 차단):

- **§X Read Scope (Impact Scan)**: plan-impact Exhaustive Impact Scan 결과 전체. 탐색 범위를 좁히지 않는다.
- **§Y Write Scope (Implementation)**: §X 중 실제 변경하는 항목만 (`write-in` 판정). 각 항목에 근거 명시 — (1) 요구사항 직접 충족 / (2) obstacle 해제 / (3) Q0 Behavior Preservation 예외.
- **§Z Acceptance Criteria**: §Y 각 항목의 검증 가능한 완료 기준 (컴파일 가능 / test 통과 / grep 패턴 매칭). criteria 미명시 항목은 §Y 포함 불가 (→ §X 이동 + 후속 ticket).

**handoff 계약**: fz-code는 §Y + §Z만 참조 (Read Scope 무관). fz-review Phase 4.5는 §Y 기준으로 scope_creep 판정. 이 구조로 "Read Scope = Write Scope" 자동 번역 차단 (OBS-03 RC4 해소).

## Compact Recovery Protocol

1. WORK_DIR 를 찾는다 — 인자 · 브랜치의 티켓, 없으면 `Glob("**/{TICKET_PREFIX}-*/index.md")` · `Glob("**/NOTASK-*/index.md")`. 후보가 여럿이면(같은 날 NOTASK 폴더가 여럿이면 접미 이름으로 가른다 · 티켓 폴더 여럿) Active Phase 가 끝나지 않은 폴더 가운데 `index.md` 를 가장 최근에 고친 것을 고르고, 그래도 하나로 좁혀지지 않으면 사용자에게 묻는다
2. `{WORK_DIR}/index.md` 읽기 → `## Essential Context` 섹션으로 상세 복원
3. Active Phase의 최신 아티팩트 로드
4. 상위 Phase 핵심 산출물 로드 (discover→discover-journal.md Current State, plan→plan-final.md)
5. 컨텍스트 복원 완료 알림

> **추상화 참조**: Anthropic "Scaling Managed Agents: Decoupling the Brain from the Hands" (2026-04) — `emitEvent`/`getEvents` 같은 API contract가 파일 기반 영속화보다 일관성·queryability 우수 [verified: A3]. 현재 fz는 **파일 기반** (index.md)이고 향후 API 추상화 도입 가능. fz의 티켓 폴더 + Essential Context = Anthropic의 Session event log 개념의 **filesystem 구현체**.

## Proactive Context Protocol

> 기존: Write(저장)만 하고 Read(로드) 없음 → compact 후 복원 불가
> 개선: Write + Read. /fz가 중앙에서 Essential Context를 관리

```
[기존] Phase A → Write(artifact) → (compact?) → Phase B → (복원 시도)
[개선] Phase A → Write(artifact) → /fz가 Essential Context 업데이트 → Phase B → /fz가 Read → 서브스킬 실행
```

### Essential vs Disposable

| Essential (보존) | Disposable (자연 소멸 OK) |
|-----------------|-------------------------|
| 사용자 결정/승인 | 탐색 중간 결과 |
| 제약 조건 | raw MCP 출력 · 개별 도구 결과 로그 |
| 아키텍처 선택 근거 | 에이전트 간 토론 과정 |
| Gate 통과/실패 이력 | 코드 diff 상세 |
| Active Phase + Step 진행률 | 빌드 로그 |
| mid-pipeline discover 결정 | /btw로 물어본 일회성 질문 |
| Implication Register + 관찰 함의 | Implication Scan 중간 로그 |

```
Essential: "[plan] Step 3개 계획 확정. RIBs 패턴. OrderDetail{Builder,Router,Interactor,VC}."
Disposable: "Grep 결과 42개 파일 매칭. find_referencing_symbols 호출 3회."
```

## Upstream Hydration Sets

각 스킬 SKILL.md 의 Phase 0 · 티켓 폴더 컨텍스트 로딩 목록이 정본이다(이 모듈은 사본을 두지 않는다).

> ⛔ `constraints.md` 참조 금지 — canonical은 `discover-journal.md`

## Phase-Tagged Discover

> mid-pipeline 질문 context 보존. 어느 Phase에서 발생한 질문인지 추적.

### 프로토콜

```
1. /fz-discover 호출 시:
   a. index.md 존재 확인 → 없으면 기본 모드 (discover-journal.md)
   b. 있으면 → Active Phase 읽기
   c. Active Phase가 discover 또는 없음 → discover-journal.md (기본)
   d. Active Phase가 plan/code/review → discover-{phase}.md에 저장
   e. index.md Artifacts에 [discover-{phase}] 엔트리 추가

2. Upstream 스킬이 자기 discover 파일을 Read:
   - /fz-plan → discover-plan.md (있으면)
   - /fz-code → discover-code.md (있으면)
   - /fz-review → discover-review.md (있으면)
```

### 동일 Phase 내 다중 Discover 규칙

```
discover-journal.md (DISCOVER_TAG=journal): 전체 덮어쓰기 (매 라운드) · 10K tokens 이내
discover-{phase}.md (DISCOVER_TAG=plan|code|review): APPEND + topic header
- topic header로 분리: ## Topic: {질문 요약} (YYYY-MM-DD HH:MM)
- 파일 크기 5K tokens 초과 시 → 이전 topic 요약 압축 (최신 topic 상세 유지)
```

## Ephemeral vs Persistent (/btw 통합)

> Anthropic: "/btw — dismissible overlay, never enters conversation history"

| 질문 유형 | 도구 | 저장 | 예시 |
|----------|------|------|------|
| 일회성 지식 질문 | `/btw` | ❌ | "CurrentValueSubject와 @Published 차이?" |
| 결정/제약 발견 | `/fz-discover` | ✅ | "이 패턴을 쓸지 말지 결정해야 해" |
| 중간 확인 | `/fz-discover` | ✅ | "지금 구현 방향이 맞나 확인" |

**판별 규칙**: 답변이 향후 Phase에 영향을 미치면 persistent (/fz-discover), 아니면 ephemeral (/btw).

## 파이프라인 길이별 저장

| 파이프라인 길이 | 전략 | 이유 |
|---------------|------|------|
| 1-5 스텝 | 티켓 폴더가 있으면 파일, 없으면 대화 컨텍스트만(이어받기 없음) | compact 위험 낮음. context-heavy 스킬 포함 시 티켓 폴더 권장 |
| 6+ 스텝 또는 context-heavy | 티켓 폴더 파일 기반 (이 모듈) | compact 후 Read로 복원 <!-- 기존: 4+ 스텝 --> |
| 10+ 스텝 | 티켓 폴더 필수 + compact 주의 안내 | 장기 파이프라인 |

> **context-heavy 스킬**: discover, search --deep, peer-review (대량 context 생산)

## Artifact Token Budget

> 현재 환경: **Lead = `fable` alias(Claude Code v2.1.321 부터 Fable 5.2 — fz 운용 선택)** · 워커(수행 에이전트)는 opus(=Opus 5.5, 2026-09-22~)/sonnet. 이전 Lead Fable 5.1·**Opus 5.5** 는 모두 1M context(Fable 5.2 의 컨텍스트 창은 2026-11-16 대조 범위 밖) — "The 1M token context window is the default, and a header sent for older models has no effect." [verified: platform.claude.com/docs/en/models/opus-5-5/migration-guide]. 티켓 폴더 파일 전략은 모델 무관 유지
> ⚠️ **tokenizer**: 1.00-1.35x 토큰 증가 (pre-4.7 baseline, fz 자체 실측 미완료) `[미검증: fz 자체 count_tokens 측정 대기]`. **Opus 4.7/4.8/5 · Fable 5는 동일 tokenizer** → 이들 간 이전 시 토큰 수 거의 불변 [verified: claude-api 번들 스킬 — "same tokenizer as Opus 4.8"].
> ℹ️ **프롬프트 캐시 최소 prefix**: Opus 5.5 = **512 tokens**, Opus 4.8 = 1024 — "The minimum cacheable prompt length on Claude Opus 5.5 is 512 tokens, down from 1,024 tokens on Claude Opus 4.8." [verified: platform.claude.com/docs/en/models/opus-5-5/migration-guide]. 짧은 artifact도 캐시 대상이 되므로 분할 전략 재검토 여지 있음.
> 원칙: 전체 artifact 로드 합계 ≤ 100K tokens. 나머지는 실행 working memory.
> Context Rot 원칙(집중 > 분산)은 context 크기와 무관하게 동일 적용.

## 실행 기록

멀티에이전트 실행 기록은 Workflow transcript(runId)와 Lead 가 쓰는 `{WORK_DIR}/{phase}/workflow-result.json` 이다 — 에이전트 간 통신을 따로 요약하는 파일은 만들지 않는다(TEAM 일몰 · P2P 없음, F-482).

## Few-shot 예시

### 예시 1: index.md

```markdown
# TKT-1234 Context Index

## Active Phase: code

## Artifacts
- [discover] discover-journal.md — Round 2 기준, 제약 5개(C1-C5), 생존 후보 1개
- [plan] plan-v1.md — 3-Step 계획 초안
- [plan] plan-final.md — 사용자 승인 계획
- [code] step-1.md — Repository 구현 완료, 빌드 성공
- [code] progress.md — Step 1/3 완료
```

### 예시 2: discover-journal.md (discover-journal 형식)

```markdown
# Discover Journal — 상태 관리 패턴 선택

## Current State (Round 3 기준)

### 제약 매트릭스
| # | 제약 | 출처 | 확신도 |
|---|------|------|--------|
| C1 | RIBs Interactor가 비즈니스 로직 담당 | 아키텍처 원칙 | 높음 |
| C2 | 기존 Combine 기반 (@Published + sink) | 코드 탐색 | 높음 |
| C3 | 보일러플레이트 최소화 (caller 부담 적게) | 사용자 | 중간 |
| C4 | iOS 16 호환 필요 (@Observable 사용 불가) | 사용자 | 높음 |
| C5 | 기존 RIBs Router와 동일 패턴 유지 | 코드 탐색 | 높음 |

### 생존 후보
| 후보 | 모든 제약 | 비고 |
|------|----------|------|
| D: ObservableObject + @StateObject | O | Combine 친화, iOS 16 호환 |

### 탈락 후보 (사유)
- A: @Observable 직접 사용 — C4 위반 (iOS 16 미지원)
- B: Interactor→ViewModel 브릿지 — C3 위반 (브릿지 보일러플레이트 과다)
- C: 직접 @State — C1 위반 (비즈니스 로직이 View에 노출)

### 정제된 요구사항
1. ObservableObject 프로토콜 채택 + @Published 프로퍼티
2. View에서 @StateObject로 소유, init 파라미터로 주입
3. Interactor는 Combine sink로 ViewModel 구독
```

### 최종 산출물 확장 (Phase 3 수렴 시)

기본 discover-journal 형식에 아래 섹션을 추가:
- `### 채택된 해` — 최종 선택 + 한 줄 설명
- `### 수용한 트레이드오프` — 있다면
- `### 정제된 요구사항` — 구현 가능한 구체적 항목 목록
- `### 결정 근거` — 채택 이유 + 코드 참조

### 예시 3: compact recovery

```
[Compact 감지] 대화 컨텍스트 손실됨.
1. 브랜치의 티켓 TKT-1234 → work_dir: "{CWD}/TKT-1234"
2. TKT-1234/index.md 읽기 → Active Phase: code, Step 1/3 완료
3. code/progress.md 로드 → Step 1-2 완료 이력 + Step 3 진행 중
4. plan/plan-final.md 로드 → 3-Step 계획 확인
5. 컨텍스트 복원 완료. Step 2부터 재개.
```

## Edge Case 대응

| 상황 | 대응 |
|------|------|
| 세션 전환 | 다음 세션은 `index.md` 로 복원 — 위치는 인자 · 브랜치의 티켓, 없으면 직접 검색 (`Glob("**/{TICKET_PREFIX}-*/index.md")` — 예: `TKT-*` — 또는 `Glob("**/NOTASK-*/index.md")`) |
| /fz 없이 직접 스킬 호출 | ⛔ Work Dir Resolution 실행: 티켓 패턴 → 자동 생성, 없으면 → 사용자 질문 |
| 단일 티켓 제약 | 동시 작업은 1개 티켓만 허용 |
| Compact 중 파일 쓰기 | Write 완료 후 index.md 업데이트 (atomic ordering) |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | Work Dir Resolution |
| /fz-discover | discover-journal.md 누적 기록 |
| /fz-plan | plan 버전 기록 |
| /fz-code | step/progress 기록 |
| /fz-review | self-review 기록 |
| /fz-peer-review | review-index.md + 파일 산출물 (synthesized-issues.json, pr-comments.md, tier.txt) — Serena checkpoint 미사용. |

## ⛔ Work Dir Resolution (모든 fz-* 스킬 필수)

> 반성 4차 교훈 + 5차 교훈: 직접 호출 시에도 폴더가 초기화되어야 하며, 비-티켓 세션에서도 파일 저장이 가능해야 한다.

**모든 fz-* 스킬은 Phase 1 시작 전에 이 체크를 실행한다:**

```
1. 인자에서 [A-Z]{2,6}-\d{2,5} 패턴 추출
2. 패턴 있으면 → 무조건 자동 저장:
   a. {CWD}/{TICKET}/ 폴더 존재 확인
   b. 없으면 즉시 mkdir -p + index.md 생성
   c. WORK_DIR = {CWD}/{TICKET}/
3. 패턴 없으면:
   a. 브랜치명에서 [A-Z]{2,6}-\d{2,5} 추출 시도 → 있으면 2번과 동일
   b. 없으면 → AskUserQuestion: "이 작업의 산출물을 파일로 저장할까요?"
      - 예 → {CWD}/NOTASK-{YYYYMMDD}/ 폴더 생성 + index.md + WORK_DIR 설정(같은 날 다른 작업이면 `NOTASK-{YYYYMMDD}-{짧은 이름}`)
      - 아니오 → 저장 없이 진행(이어받기 없음) — 선택지에 "이 세션 밖으로 계획 · 탐색을 넘기지 못한다" 를 적는다
```

**Gate 0 (Work Dir Resolution):**
- [ ] 인자/브랜치에서 티켓 패턴 체크 완료?
- [ ] 티켓 패턴 있으면 폴더 자동 생성 완료?
- [ ] 패턴 없으면 사용자에게 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (티켓 폴더 경로 / NOTASK 경로 / 저장 없이 진행)

## 사전 예방적 Context 관리

> compact recovery는 사후 대응이다. 아래는 compact를 **지연/방지**하기 위한 사전 전략.

### 원칙: Context 여유 = 실행 품질

auto-compact는 맥락 손실을 수반한다. 그래서 컨텍스트를 덜 채워 발동 자체를 줄인다. 1M까지 채우라는 뜻이 아니다.

### Filesystem Discovery > Compaction (Anthropic 공식)

> "Claude is effective at discovering state from filesystem. Sometimes better than relying on compacted context."
> — Anthropic Claude Code Best Practices (2026)

compact 후 복원은 context summary보다 **파일 Read가 더 정확**하다. 따라서:
- L3(파일)가 canonical — 위치는 `index.md` 가 가리킨다
- compact 발생 시: `index.md` 읽기 → L3 파일 경로 파악 → L3 Read로 상세 복원

### Context Decay 방어 (4유형 — 프로젝트 자체 분류)

| 유형 | 설명 | 방어 |
|------|------|------|
| Poisoning | 잘못된 정보가 context에 잔류 | 결정 변경 시 Essential Context 즉시 덮어쓰기 |
| Distraction | 불필요한 정보가 주의 분산 | MCP 출력 격리, Disposable 정보 미축적 |
| Confusion | 상충하는 정보 공존 | Essential Context가 single source of truth |
| Clash | 지시 간 충돌 | /fz 중앙 관리로 일관성 유지 |

### 적용 규칙

1. **MCP 출력 격리**: 대용량 결과(Grep, 심볼 분석, GPT)는 파일로 저장 후 Read 참조. context에 raw 출력 남기지 않음
2. **중간 산출물 즉시 기록**: 분석 결과가 나오면 대화에 축적하지 말고 티켓 폴더 파일에 즉시 기록 → compact 시 Read로 복원
3. **에이전트 스폰 최소화**: 스폰마다 토큰이 든다(스폰당 양은 재지 않았다). 단순 작업은 직접 실행
4. **참조 파일 선택적 로드**: 전체 파일 Read 대신 필요 섹션만 (offset/limit). 500줄+ 파일은 분할 읽기

> 상세: `guides/prompt-optimization.md` §2.5 (Context Budget 관리)

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
- Context 여유 = 실행 품질 (사전 예방 > 사후 복구)
