# fz

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 기반 AI 개발 워크플로우 오케스트레이션 시스템.

자연어 요청을 분석하여 복잡도 기반으로 스킬 파이프라인을 자동 구성하고, 필요 시 멀티 에이전트 팀을 편성하여 실행합니다.

---

## 전체 구조

```
~/.claude/
├── skills/           # 22개 스킬 — 사용자가 직접 호출하는 워크플로우 단위
│   ├── fz/           # 오케스트레이터 (모든 스킬의 진입점)
│   ├── fz-*/         # 19개 도메인별 스킬 (fz-gemini 추가)
│   ├── arch-critic/  # 아키텍처 비평 (peer review용)
│   ├── code-auditor/ # 코드 품질 감사 (peer review용)
├── agents/           # 14개 에이전트 — 팀 모드에서 전문 역할 수행
├── modules/          # 17+2개 모듈 — 스킬/에이전트가 공유하는 설정과 정책 (rtm, native-agents 포함)
│   └── patterns/     # 5개 팀 통신 패턴
├── guides/           # 6개 가이드 — 프롬프트 최적화, 스킬 작성, 테스팅, 트러블슈팅, Clean Architecture
└── templates/        # 스킬/에이전트/모듈 생성 템플릿
```

### 1. 시스템 레이어 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                       사용자 (자연어 요청)                           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Orchestrator          /fz  오케스트레이터                          │
│                        의도 분석 → 복잡도 평가 → 파이프라인 결정          │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Skills (22개)         실행 가능한 워크플로우 단위                      │
│                                                                 │
│  ┌─ 개발 ───────┐ ┌─── 탐색 ─────┐ ┌──── 검증 ────┐  ┌─ 출하 ─────┐  │
│  │ fz-plan     │ │ fz-discover │ │ fz-review   │ │ fz-commit │  │
│  │ fz-code     │ │ fz-search   │ │ fz-codex    │ │ fz-pr     │  │
│  │ fz-fix      │ └─────────────┘ │ fz-peer-rev │ └───────────┘  │
│  └─────────────┘                 └─────────────┘                │
│  ┌─ 문서 ───────┐ ┌── 시스템 ────┐ ┌─ 보조 ─────────────────────┐   │
│  │ fz-doc      │ │ fz-skill   │ │ arch-critic  code-auditor │   │
│  │ fz-memory   │ │ fz-manage  │ │ fz-new-file               │   │
│  │ fz-recording│ │ fz-excalidw│ │ fz-pr-digest              │   │
│  └─────────────┘ └────────────┘ └───────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Agents (14개)         TEAM 모드에서 스킬 내부의 전문 역할               │
│                                                                 │
│  ┌─ 계획 ────────────┐ ┌─ 구현 ───────────┐ ┌─ 탐색 ────────────┐   │
│  │ plan-structure   │ │ impl-correctness│ │ search-pattern  │   │
│  │ plan-impact      │ │ impl-quality    │ │ search-symbolic │   │
│  │ plan-edge-case   │ └─────────────────┘ └────────────────-┘   │
│  │ ~~plan-tradeoff~~│ ┌─ 리뷰 ────────────┐ ┌─ 메모리 ──────────┐  │
│  └──────────────────┘ │ review-arch      │ │ memory-curator  │  │
│                       │ review-quality   │ └─────────────────┘  │
│                       │ review-correct.  │                      │
│                       │ review-direction │                      │
│                       │ review-counter   │                      │
│                       └──────────────────┘                      │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Modules (17개)        스킬/에이전트가 공유하는 설정과 정책               │
│                                                                 │
│  team-core  team-registry  build  session  complexity           │
│  pipelines  intent-registry  execution-modes  governance        │
│  cross-validation  context-artifacts  codex-strategy            │
│  memory-guide  memory-policy  plugin-refs  rtm  native-agents   │
│  └─ patterns/  adversarial  collaborative  pair-programming     │
│                live-review  cross-verify                        │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Infrastructure       MCP 서버 + CLI + 플러그인                     │
│                                                                 │
│  MCP: Serena  Context7  XcodeBuildMCP  Atlassian  GitHub  LSP   │
│  CLI: Codex  Gemini  gh  xcodebuild  uv                        │
│  Plugin: SuperClaude  SwiftUI-Expert  Swift-Concurrency         │
└─────────────────────────────────────────────────────────────────┘
```

### 2. 오케스트레이션 플로우

```
/fz "기능 구현하고 리뷰까지"
 │
 ▼
┌─── Phase 0: Session ──────────────────────────────────────────┐
│  sc:load (이전 세션 복원) → 프로젝트 인덱스 확인 → ASD 폴더 초기화        │
└───────────────────────────────┬───────────────────────────────┘
                                ▼
┌─── Phase 1: Intent ────────────────────────────────────────────┐
│  키워드 추출 → intent-triggers 매칭 → 후보 스킬: fz-code, fz-review   │
│  추가 신호: scope=중간, quality=보통  confidence: High              │
└───────────────────────────────┬────────────────────────────────┘
                                ▼
┌─── Phase 2: Complexity ────────────────────────────────────────┐
│  5차원 평가: Scope(1) Depth(1) Risk(1) Novelty(0) Verify(1)      │
│  합산: 4점 → TEAM 모드 결정                                        │
└───────────────────────────────┬────────────────────────────────┘
                                ▼
┌─── Phase 3: Pipeline + Team ───────────────────────────────────┐
│  매칭: code-to-review 파이프라인                                   │
│  체인: fz-code → ✓build → ✓codex → fz-review → fz-commit        │
│  팀: Lead(O) + ★impl-correctness(O) + review-arch(S)            │
│       + review-quality(S) + impl-quality(S)                    │
│  게이트 주입: build + codex check + friction-detect               │
└───────────────────────────────┬────────────────────────────────┘
                                ▼
┌─── Phase 4: Confirm ───────────────────────────────────────────┐
│  파이프라인 시각화 출력 → 사용자 승인 대기                               │  
│  [이대로 실행] [모드 변경] [단계 추가/축소] [커스텀]                      │
└───────────────────────────────┬────────────────────────────────┘
                                ▼
┌─── Phase 5: Execute ───────────────────────────────────────────┐
│                                                                │
│  Step 1: /fz-code ─── TeamCreate → 에이전트 스폰                   │
│          ★impl-correctness(O) ↔ review-arch(S) 페어 프로그래밍     │
│          impl-quality(S) 실시간 품질 감시                          │
│          매 Step마다 ✓friction-detect                            │
│                    │                                           │
│  Step 2: ✓build ── Lead가 빌드 검증 (XcodeBuildMCP)               │
│                    │                                           │
│  Step 3: ✓codex ── Lead가 Codex CLI로 교차 검증                    │
│                    │                                           │
│  Step 4: /fz-review ─ review-arch(S) ↔ review-quality(S)       │
│          라이브 리뷰 (서로 다른 렌즈로 동시 분석)                        │        
│                    │                                           │
│  Step 5: /fz-commit ─ Lead가 커밋 생성                            │
│                    │                                           │
│  완료: shutdown_request → TeamDelete → GC → sc:save             │
└────────────────────────────────────────────────────────────────┘
```

### 3. 스킬-에이전트 매핑

```
스킬 (SOLO/TEAM)              TEAM 모드 에이전트 구성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

fz-discover ──────────┬── ★plan-structure (O)    경로 생성 + 실현성
  풍경 탐색 + 경로 매핑    ├── review-arch (S)        비용/리스크 탐색 + 🔒/🔓 판별
  Landscape 패턴        └── memory-curator (S)     과거 교훈

fz-plan ───────────────┬── review-direction (S)   방향 도전 (Phase 0.5)
  6-Agent Plan Team     ├── ★plan-structure (O)    설계 + 문서화
  Parallel Analysis     ├── plan-impact (S)        Exhaustive Impact Scan 전담
                       ├── review-arch (S)        아키텍처 패턴 검증
                       ├── memory-curator (S)     과거 교훈
                       ├── Codex verify (GPT)     독립 계획 검증
                       └── Gemini challenge       Devil's Advocate [--deep]

fz-code ───────────────┬── ★impl-correctness (O)  점진적 구현
  코드 구현               ├── impl-quality (S)       코딩 표준 감시
  Pair Programming     ├── review-arch (S)        아키텍처 검토
                       └── review-correctness (S) 기능 정확성 검증

fz-review ─────────────┬── review-arch (S)        아키텍처 리뷰
  자기 코드 리뷰           ├── review-quality (S)     품질 + 성능 리뷰
  Live Review 패턴      ├── review-correctness (S) 요구사항 충족 검증
                       └── review-counter (S)     반론/Devil's Advocate

fz-search --deep ──────┬── search-symbolic (S)    LSP/Serena 심볼 탐색
  코드 탐색              └── search-pattern (S)     Grep/Glob 패턴 탐색
  Cross-Verify 패턴

fz-fix (복잡) ──────────┬── ★impl-correctness (O)  수정 구현
  버그 수정              └── impl-quality (S)       품질 검증
  Pair Programming

fz-peer-review ────────┬── review-arch (S)        아키텍처 관점
  동료 PR 리뷰           ├── review-quality (S)     품질 관점
                       └── review-counter (S)     반론 관점

★ = Primary Worker (Opus 승격)    (O) = Opus    (S) = Sonnet
```

### 4. 교차 검증 게이트

```
파이프라인 진행 방향 ─────────────────────────────────────────────────────→

  계획 전           계획 후            구현 중           구현 후           출하 전
────┼───────────────┼────────────────┼────────────────┼───────────────┼────
    │               │                │                │               │
    ▼               ▼                ▼                ▼               ▼
┌────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────────┐  ┌──────────┐
│ direction  │  │ stress-test │  │ friction │  │  ✓ build     │  │ ✓ codex  │
│ challenge  │  │  Q1-Q6      │  │ detect   │  │  ✓ codex     │  │  check   │
│            │  │             │  │          │  │  ✓ enforce   │  │          │
│ PROCEED    │  │ Critical    │  │ 매 Step   │  │    (리팩토링)  │  │ Reflect  │
│ RECONSIDER │  │  2+이면      │  │ 자동 실행   │  │  ✓ consumer  │  │ Rate≥80% │
│ REDIRECT   │  │  자동 재작성   │  │          │  │    (모듈화)   │  │          │
└────────────┘  └─────────────┘  └──────────┘  └──────────────┘  └──────────┘
      │               │               │                │               │
   review-         fz-plan         fz-code           build.md        fz-codex
   direction      stress-test    friction-detect   cross-valid.     codex CLI
``` 

### 5. TEAM 모드 통신 구조 (Claude Code API 기반)

> Claude Code의 `TeamCreate` + `Agent` + `SendMessage` 도구를 사용하여
> 에이전트 간 **Peer-to-Peer 직접 통신**을 구현합니다.
> Lead는 중계자가 아닌 퍼실리테이터 역할만 수행합니다.

```
┌───────────────────────────────────────────────────────────────┐
│                        Lead (Opus)                            │
│                       퍼실리테이터 역할                            │
│                 모니터링 + 교착 해소 + Gate 실행                    │
└──────┬──────────────────────┬────────────────────┬────────────┘
       │ Task Brief           │                    │
       │ [Role][Context]      │                    │
       │ [Goal][Constraints]  │                    │
       │ [Deliverable]        │                    │
       ▼                      ▼                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ ★Primary (O) │     │  Agent-B (S) │     │  Agent-C (S) │
│ 핵심 생산자     │     │  검증/보완     │     │  검증/보완      │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                   │                     │
       │◄──────────────────┼─────────────────────┤
       │    Round 1: 각자 독립 분석 (참조 금지)        │
       │                   │                     │
       ├──────────────────►│◄────────────────────┤
       │    Round 2: 피어에게 직접 SendMessage       │
       │    피드백 + 반박 + 보완                     │
       │                   │                     │
       │◄──────────────────┼─────────────────────┤
       │    Round 0.5: [합의] or [불합의] 보고       │
       │                   │                     │
       ▼                   ▼                     ▼
┌──────────────────────────────────────────────────────────────┐
│  합의 결과 → Lead에게 보고 → Lead가 Gate 실행 (build/codex)         │
└──────────────────────────────────────────────────────────────┘
```

### 5-1. TEAM 도구 호출 상세 (Claude Code API)

위 2.5-Turn Protocol을 Claude Code API 도구로 구현하는 실제 흐름:

```
Step 1: TeamCreate ─── 팀 생성
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lead (Opus) ──── TeamCreate("code-to-review-login") ────→ 팀 생성됨
                 config: ~/.claude/teams/{team-name}/config.json
                 tasks:  ~/.claude/tasks/{team-name}/


Step 2: Agent 스폰 ─── 에이전트 생성 + Task Brief 전달
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lead ─┬── Agent(name:"impl-correctness", model:opus, team_name:...)
      │   prompt: "[Role] Primary 구현자  [Context] 로그인 리팩토링
      │            [Goal] 점진적 구현      [Constraints] RIBs 패턴 준수
      │            [Deliverable] 빌드 통과 코드
      │            피어: review-arch, impl-quality"
      │
      ├── Agent(name:"review-arch", model:sonnet, team_name:...)
      │   prompt: "[Role] 아키텍처 검토자 ... 피어: impl-correctness"
      │
      └── Agent(name:"impl-quality", model:sonnet, team_name:...)
          prompt: "[Role] 품질 감시자 ... 피어: impl-correctness"


Step 3: Peer-to-Peer 통신 ─── SendMessage로 직접 대화
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ★impl-correctness (O)          review-arch (S)          impl-quality (S)
          │                            │                         │
          │     Round 1: 독립 분석 (다른 에이전트 초안 참조 금지)   │
          │                            │                         │
          │ ①──── SendMessage ────────►│                         │
          │                            │                         │
          │                            │ ②── SendMessage ───────►│
          │                            │                         │
          │ ③◄─── SendMessage ─────────│                         │
          │                            │                         │
          │     Round 2: 피드백 반영 + 재작성                      │
          │                            │                         │
          │     Round 0.5: 합의 보고                              │
          │ ④──── SendMessage ────────►│ → Lead                  │
          │                            │                         │
          ▼                            ▼                         ▼

  메시지 상세:
  ┌────┬──────────────────┬──────────────────────────────────────┐
  │ #  │ recipient        │ content                              │
  ├────┼──────────────────┼──────────────────────────────────────┤
  │ ①  │ "review-arch"    │ "Step 1 구현 완료, 시그니처 검토 부탁"  │
  │ ②  │ "impl-quality"   │ "레이어 위반 발견, 확인 부탁"           │
  │ ③  │ "impl-correct"   │ "Router 직접 API 호출 금지.            │
  │    │                  │  UseCase 경유 필요"                    │
  │ ④  │ "lead"           │ "[합의] 3인 동의. 구현 완료, 빌드 요청"  │
  └────┴──────────────────┴──────────────────────────────────────┘


Step 4: Lead 게이트 실행
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lead ─── ✓ build gate (XcodeBuildMCP)
     ─── ✓ codex check (Codex CLI)
     ─── Reflection Rate 계산 (≥80% 통과)


Step 5: 종료
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Lead ─┬── SendMessage(type:"shutdown_request", recipient:"impl-correctness")
      ├── SendMessage(type:"shutdown_request", recipient:"review-arch")
      ├── SendMessage(type:"shutdown_request", recipient:"impl-quality")
      │       ↓ 각 에이전트가 shutdown_response(approve:true) 응답
      └── TeamDelete ─── 팀 + 태스크 리소스 정리
```

### 6. 파이프라인 예시: full-cycle

```
/fz "로그인 화면 리팩토링해줘" --deep

  ┌─────────────┐    ✓direction     ┌─────────┐    ✓stress    ┌─────────┐
  │ fz-discover │──── challenge ────│ fz-plan │──── test ─────│ fz-code │
  │ 제약 발견     │                   │ 설계      │               │ 구현     │
  └─────────────┘                   └─────────┘               └────┬────┘
                                                                   │
            ✓friction-detect (매 Step)                              │
                                                                   ▼
  ┌───────────┐     ✓codex      ┌───────────┐    ✓build        ┌──────────┐
  │ fz-commit │◄──── check ─────│ fz-review │◄──── gate ─────  │ ✓enforce │
  │ 커밋       │                 │ 리뷰       │                  │ 금지패턴    │
  └────┬──────┘                 └───────────┘                  └──────────┘
       │
       ▼
  ┌─────────┐
  │ fz-pr   │   → PR 생성 → 완료
  │ PR      │
  └─────────┘
```

---

## Skills (22개)

| 카테고리 | 스킬 | 호출 | 설명 |
|---------|------|------|------|
| **오케스트레이터** | fz | `/fz "요청"` | 자연어 → 파이프라인 자동 구성 + SOLO/TEAM 결정 |
| **개발** | fz-plan | `/fz-plan` | 계획 수립 + 요구사항 분석 + 영향 범위 분석 |
| | fz-code | `/fz-code` | 계획 기반 점진적 구현 + 매 Step 빌드 검증 + Step 완료 조건 3개 |
| | fz-fix | `/fz-fix` | 버그 수정. 4-Phase (Reproduce→Isolate→Root-Cause→Verify) |
| | fz-review | `/fz-review` | 자기 코드 리뷰. Claude + Codex + sc:analyze 3중 검증 |
| | fz-commit | `/fz-commit` | Conventional Commit 형식 커밋 |
| | fz-pr | `/fz-pr` | Fork 기반 PR 생성 (push → PR create) |
| **탐색** | fz-discover | `/fz-discover` | 풍경 탐색 + 경로 매핑. 결론 없이 landscape를 그려 plan에 전달 |
| | fz-search | `/fz-search` | 코드 탐색 + 구조 분석 + 의존성 추적 |
| **검증** | fz-codex | `/fz-codex` | Codex CLI(GPT) 교차 검증 + --consensus (3-Model 합의) |
| | fz-gemini | `/fz-gemini` | Gemini CLI Devil's Advocate. 대안 관점 + 위험 분석 |
| | fz-peer-review | `/fz-peer-review` | 동료 PR 리뷰. 9개 관점 독립 분석 + TeamCreate 프로토콜 |
| | fz-pr-digest | `/fz-pr-digest` | PR 변경 설명. Before/After + 학습 포인트 |
| **문서** | fz-doc | `/fz-doc` | 스킬/에이전트/CLAUDE.md 문서 작성 |
| | fz-memory | `/fz-memory` | 메모리 관리 (L1 정리, L2 GC, 교훈 회상) |
| | fz-recording | `/fz-recording` | 녹음 → 화자 분리 + 회의록 (AssemblyAI) |
| **시스템** | fz-skill | `/fz-skill` | 스킬/에이전트 CRUD + eval 품질 평가 |
| | fz-manage | `/fz-manage` | 생태계 인벤토리, 헬스체크, 벤치마크 |
| | fz-new-file | `/fz-new-file` | 새 파일 헤더 서명 규칙 |
| | fz-excalidraw | `/fz-excalidraw` | Excalidraw 다이어그램 생성/수정 |
| **보조** | arch-critic | (팀 내부용) | 아키텍처 비평 (Truth-of-Source) |
| | code-auditor | (팀 내부용) | 코드 품질 감사 (Truth-of-Source) |

---

## Agents (14개)

TEAM 모드에서 Lead가 스폰하며, **에이전트 간 직접 대화(Peer-to-Peer)**로 협업합니다.

| 도메인 | 에이전트 | 역할 | 참여 스킬 |
|--------|---------|------|----------|
| **계획** | plan-structure | 구현 구조 + Step 순서 설계 | fz-plan★, fz-discover★ |
| | plan-impact | Exhaustive Impact Scan 전담 (영향 범위 + 숨겨진 의존성) | fz-plan |
| | plan-edge-case | 엣지 케이스 + 실패 시나리오 발굴 | fz-plan |
| | ~~plan-tradeoff~~ | ~~트레이드오프 + 대안 비교~~ | **ARCHIVED** (discover가 대체) |
| **구현** | impl-correctness | 점진적 구현 + 기능 정확성 보장 | fz-code★, fz-fix★ |
| | impl-quality | 코딩 표준 + 패턴 일관성 감시 | fz-code, fz-fix |
| **리뷰** | review-arch | 아키텍처 결정 + 레이어 위반 + Consumer Integration | fz-code, fz-review, fz-peer-review, fz-discover |
| | review-correctness | 기능 정확성 + 요구사항 충족 | fz-code, fz-review |
| | review-quality | 코드 품질 + Dead Code + 성능 | fz-review, fz-peer-review |
| | review-direction | 방향 도전 (PROCEED/RECONSIDER/REDIRECT) | fz-plan (Phase 0.5) |
| | review-counter | 반론 + Devil's Advocate | fz-review, fz-peer-review |
| **탐색** | search-pattern | Grep/Glob 넓은 범위 패턴 검색 | fz-search |
| | search-symbolic | LSP/Serena 심볼 정밀 탐색 | fz-search |
| **메모리** | memory-curator | 교훈/패턴/결정사항 발굴 | 모든 TEAM (fz-plan, fz-code, fz-review, fz-discover) |

> ★ = 해당 스킬에서 Primary Worker (Opus 승격)

---

## Modules (15개)

스킬과 에이전트가 공유하는 설정, 정책, 프로토콜.

| 카테고리 | 모듈 | 설명 |
|---------|------|------|
| **핵심 인프라** | team-core.md | TEAM 프로토콜. 2.5-Turn, 절대 규칙, 모델 전략 |
| | team-registry.md | 역량 기반 동적 팀 구성 + 모델 자동 배정 |
| | build.md | 빌드 검증 공통 모듈 |
| | session.md | 세션 자동 감지 + 이슈 트래커 연동 |
| **정책** | complexity.md | 5차원 복잡도 → SOLO/TEAM 결정 |
| | intent-registry.md | 의도 트리거 패턴 + confidence 판정 |
| | pipelines.md | 19개 사전 정의 파이프라인 |
| | execution-modes.md | BATCH, LOOP, SIMPLIFY 확장 모드 |
| | governance.md | 거버넌스. 변경 통제 + 긴급 정지 |
| | codex-strategy.md | Codex 실행 전략 (Branch, Effort, Mode) |
| **메모리** | memory-guide.md | L1 Auto Memory (MEMORY.md + topic file) |
| | memory-policy.md | L2 Serena Memory (`fz:*` 키 + GC) |
| **컨텍스트** | context-artifacts.md | 파일 기반 산출물 + compact 복원 |
| | cross-validation.md | 교차 검증 게이트 + Reflection Rate + Consumer Quality |
| | plugin-refs.md | 스킬-역할별 플러그인 매칭 |
| | cross-validation.md | + Selective Consensus (3-Model: Claude+GPT+Gemini) |
| **추적성** | rtm.md | Requirements Traceability Matrix (plan→code→review ID 추적) |
| **L3 통합** | native-agents.md | 네이티브 에이전트 통합 정책 (silent-failure-hunter, type-design-analyzer) |
| **통신 패턴** | patterns/adversarial.md | fz-discover: 경로 생성 + 비용/리스크 탐색 (Landscape) |
| | patterns/collaborative.md | fz-plan: 6-Agent 병렬 분석 + 교차 피드백 |
| | patterns/pair-programming.md | fz-code: 구현 중 실시간 검증 |
| | patterns/live-review.md | fz-review: 다른 렌즈로 동시 리뷰 |
| | patterns/cross-verify.md | fz-search: 독립 탐색 교차 검증 |

---

## 실행 모드

| | SOLO | TEAM |
|---|------|------|
| **판단** | 복잡도 0-3 | 복잡도 4+ |
| **실행자** | Lead(Opus) 단독 | Lead(O) + ★Primary(O) + N×Sonnet |
| **통신** | 순차 실행 | Peer-to-Peer 2.5-Turn Protocol |
| **검증** | 선택적 | Codex 필수 + Reflection Rate ≥80% |
| **옵션** | `--solo` | `--team`, `--deep` |

### 품질 보장

| 축 | 메커니즘 | 설명 |
|---|---------|------|
| **측정** | Reflection Rate | Codex 이슈 반영률 ≥80% Gate |
| **강제** | Gate 절차적 강제 | build, codex, stress-test, consumer quality — 스킵 불가 |
| **다양성** | Sycophancy 방어 | Round 1 독립 → Round 2 피드백 → Round 0.5 합의/불합의 |
| **프로토콜** | TeamCreate 필수 | Tier 2+ peer-review: standalone Agent() 금지, team_name 필수 |

- **Task Brief**: `[Role] [Context] [Goal] [Constraints] [Deliverable]`
- **Evaluator-Optimizer**: stress-test Critical 2+이면 자동 재작성 (최대 2회)
- **Truth-of-Source**: arch-critic/code-auditor가 분석 기준의 단일 출처

### 확장 모드

| 모드 | 옵션 | 설명 |
|------|------|------|
| **STANDARD** | (기본) | 일반 순차/병렬 실행 |
| **BATCH** | `--batch` | worktree 격리 병렬. 독립 3개+ |
| **LOOP** | `--loop` | 자동 반복 + 에스컬레이션 래더 |

---

## 사용법

### 기본 — /fz에 자연어로 요청

```bash
/fz "버그 찾아서 고쳐줘"              # 탐색 → 수정 → 빌드 검증
/fz "새 기능 계획 세워줘"             # 요구사항 분석 → 설계
/fz "코드 리뷰하고 커밋해줘"           # 리뷰 → 커밋
/fz "기능 구현하고 리뷰까지"           # 구현 → 빌드 → 리뷰
```

### 개별 스킬 직접 호출

```bash
/fz-plan                             # 계획 수립
/fz-code                             # 코드 구현
/fz-review                           # 코드 리뷰
/fz-fix                              # 버그 수정
/fz-search "PlayerInteractor 구조"    # 코드 탐색
/fz-discover                         # 요구사항 정제 대화
/fz-commit                           # 커밋
/fz-pr                               # PR 생성
/fz-peer-review feature/ASD-456      # 동료 PR 리뷰
/fz-pr-digest feature/ASD-465        # PR 요약
/fz-codex drift                      # 아키텍처 드리프트 감지
/fz-memory audit                     # 메모리 건강 점검
/fz-skill eval                       # 스킬 품질 평가
/fz-manage benchmark                 # 생태계 벤치마크
/fz-excalidraw "모듈 의존성 시각화"    # 다이어그램 생성
```

### 옵션

| 옵션 | 설명 | 예시 |
|------|------|------|
| `--solo` | Lead 단독 실행 강제 | `/fz "타임아웃 변경" --solo` |
| `--team` | 멀티 에이전트 강제 | `/fz "새 기능" --team` |
| `--deep` | --team + 교차 검증 강화 | `/fz "리팩토링" --deep` |
| `--batch` | worktree 병렬 실행 | `/fz "12개 모듈 통일" --batch` |
| `--loop` | 자동 반복 실행 | `/fz "빌드 실패 해결" --loop` |

---

## 파이프라인 (주요)

/fz가 자연어를 분석하여 자동 매칭하는 사전 정의 워크플로우:

| 파이프라인 | 트리거 예시 | 체인 |
|-----------|-----------|------|
| **quick-fix** | "타임아웃 30초로 변경" | fz-fix → build |
| **bug-hunt** | "크래시 버그 찾아줘" | fz-search → fz-fix → build |
| **explore** | "구조 분석해줘" | fz-search |
| **plan-only** | "계획 세워줘" | fz-plan |
| **plan-to-code** | "계획하고 구현해줘" | fz-plan → fz-code → build |
| **code-to-review** | "구현하고 리뷰" | fz-code → build → fz-review |
| **review-to-ship** | "리뷰하고 커밋" | fz-review → fz-commit |
| **full-cycle** | "처음부터 끝까지" | fz-plan → fz-code → build → fz-review → fz-commit |
| **discover** | "어떻게 구현할까?" | fz-discover → fz-plan |
| **fix-ship** | "고치고 커밋" | fz-fix → build → fz-commit |
| **explore-plan** | "분석하고 계획" | fz-search → fz-plan |
| **drift-check** | "드리프트 체크" | fz-codex drift |
| **plan-parallel** | "독립 플랜" | fz-codex plan |
| **peer-review** | "PR 리뷰해줘" | fz-peer-review |
| **pr-digest** | "PR 요약" | fz-pr-digest |
| **consensus-verify** | "3모델 합의 검증" | fz-codex + fz-gemini (병렬) |
| **doc-update** | "문서 업데이트" | fz-doc |

---

## 외부 의존성

### 필수

| 도구 | 설명 | 설치 |
|------|------|------|
| **Claude Code** | CLI 런타임. 모든 스킬의 실행 환경 | `npm i -g @anthropic-ai/claude-code` |

### MCP 서버

| MCP 서버 | 용도 | 사용 스킬 | 없을 때 |
|----------|------|----------|--------|
| **Serena** | 심볼릭 코드 탐색 + L2 메모리 + 세션 상태 | fz-code, fz-fix, fz-plan, fz-search, fz-review, fz-discover, fz-memory, fz-codex 등 거의 전체 | Grep/Glob/Read 폴백 |
| **Context7** | 라이브러리/프레임워크 최신 문서 조회 | fz-code, fz-fix, fz-plan, fz-search + 대부분 에이전트 | 수동 API 문서 참조 |
| **Sequential Thinking** | 복잡한 추론 체인 분해 | fz-fix, fz-plan, fz-discover, fz-review, fz-skill, fz-doc | Claude 네이티브 추론 |
| **XcodeBuildMCP** | iOS 시뮬레이터 빌드/실행/테스트 | modules/build.md (fz-code, fz-fix 경유) | `xcodebuild` CLI 폴백 |
| **Atlassian** | Jira 이슈 조회/전환/코멘트 | fz-plan, fz-commit, fz-pr | 수동 Jira 확인 |
| **GitHub** | PR 생성/리뷰/코멘트 | fz-pr, fz-peer-review, fz-pr-digest | `gh` CLI 폴백 |
| **LSP** | 타입 정보, 진단, 정의 이동 | fz-code, fz-fix, fz-search, fz-review | Serena/Grep 폴백 |

### CLI 도구

| CLI | 용도 | 사용 스킬 | 설치 | 없을 때 |
|-----|------|----------|------|--------|
| **Codex CLI** | Cross-model 교차 검증 (GPT 기반) | fz-codex, fz-review, fz-code, fz-plan, fz-peer-review | `npm i -g @openai/codex` + `~/.codex/config.toml` | 검증 단계 스킵 or `/sc:analyze` 폴백 |
| **Gemini CLI** | Devil's Advocate + 장문 분석 (1M context) | fz-gemini, consensus-verify | `npm i -g @google/gemini-cli` + OAuth GCA 인증 | Gemini 검증 스킵 |
| **GitHub CLI** (`gh`) | PR, 이슈, 인증 | fz-pr, fz-peer-review, fz-pr-digest | `brew install gh` | GitHub MCP 폴백 |
| **xcodebuild** | iOS 빌드 (XcodeBuildMCP 폴백) | modules/build.md | Xcode 설치 시 포함 | — |
| **uv + Python** | Excalidraw PNG 렌더링 | fz-excalidraw | `brew install uv` | JSON만 출력 (렌더 불가) |
| **jq** | JSON 파싱 (회의록 처리) | fz-recording | `brew install jq` | `python -m json.tool` 폴백 |

### 플러그인 / 외부 스킬

| 플러그인 | 용도 | 사용처 | 없을 때 |
|---------|------|--------|--------|
| **SuperClaude** (`/sc:*`) | 분석, 인덱싱, 세션 저장/복원, 빌드, 테스트 등 20+ 커맨드 | fz 전체 (Phase 0 세션 부트스트랩, 빌드, 리뷰 3중 검증 등) | 해당 기능 비활성 |
| **SwiftUI Expert** | SwiftUI 베스트 프랙티스, 성능 패턴 | fz-code, fz-fix + impl-*, review-* 에이전트 | iOS 전용 지식 미적용 |
| **Swift Concurrency** | async/await, actor, Sendable 패턴 | fz-code, fz-fix + impl-*, review-quality 에이전트 | 동시성 전문 지식 미적용 |
| **Skill Creator** | 스킬 eval/벤치마크 | fz-skill, fz-manage | `/fz-skill eval` 단독 사용 |

### API 키 / 외부 서비스

| 서비스 | 용도 | 필요 스킬 | 설정 |
|--------|------|----------|------|
| **OpenAI API** | Codex CLI 실행 | fz-codex + Codex 연동 전체 | `OPENAI_API_KEY` 환경변수 or `~/.codex/config.toml` |
| **AssemblyAI** | 음성 STT + 화자 분리 | fz-recording (오디오 모드) | `ASSEMBLYAI_API_KEY` 환경변수 |
| **Atlassian** | Jira/Confluence 접근 | fz-plan, fz-pr | Atlassian MCP 서버 설정 |
| **GitHub** | 레포/PR 접근 | fz-pr, fz-peer-review | `gh auth login` or GitHub MCP 설정 |

### Codex 스킬 (선택)

Codex CLI 사용 시 `~/.codex/skills/`에 8개 전용 스킬 배치:

| Codex 스킬 | 역할 |
|-----------|------|
| `fz-reviewer` | 코드 리뷰 |
| `fz-architect` | 아키텍처 분석 |
| `fz-guardian` | 안전성 검증 |
| `fz-challenger` | 반론/도전 |
| `fz-searcher` | 코드 탐색 |
| `fz-fixer` | 버그 수정 |
| `fz-drift` | 아키텍처 드리프트 감지 |
| `fz-planner` | 독립 계획 수립 |

### 최소 설치 vs 전체 설치

**최소 설치** (코어 기능만):
```
Claude Code + Serena MCP
```
→ 코드 탐색, 구현, 리뷰의 기본 워크플로우 가능

**권장 설치** (TEAM 교차 검증 포함):
```
Claude Code + Serena MCP + Context7 MCP + Codex CLI + SuperClaude
```
→ Cross-model 검증, 세션 관리, 문서 조회까지 활성화

**전체 설치** (iOS 프로젝트 풀 스택):
```
+ XcodeBuildMCP + GitHub MCP/CLI + Atlassian MCP
+ SwiftUI Expert + Swift Concurrency + Sequential Thinking + LSP
+ AssemblyAI (회의록) + uv/Python (다이어그램)
```

---

## Changelog

### v3.1 (2026-04-02) — RTM + Teams v2 + Scope Expansion + L3 에이전트

**RTM (Requirements Traceability Matrix)**
- modules/rtm.md 신규 — plan이 Req-ID 생성 → code가 implemented 갱신 → review가 기계적 확인
- 산문 매칭 → ID 기반 추적으로 요구사항 누락 방어

**L3 네이티브 에이전트 통합**
- modules/native-agents.md 신규 — silent-failure-hunter + type-design-analyzer를 review Phase 5에 background 스폰
- L1(fz커스텀) > L3(네이티브) 원칙: L3는 보강만, TeamCreate 참여 금지

**Teams v2 — 팀 내부 통신 강화**
- L3→L1 피드백: L3 발견을 Lead가 Primary에 SendMessage → iOS 특화 재분석
- Supporting 활성화: impl-quality 매 Step 피드백, review-correctness 50%+마지막 RTM 체크
- Handoff Brief: plan→code 팀 전환 시 Key Decisions+Risks+Watch Points 구조화 전달
- plan-edge-case↔plan-impact CC: Supporting 간 교차로 연쇄 발견
- 5명+ 토폴로지: team-core.md에 Star-enhanced+CC 행 추가

**Scope Expansion — discover 시야 제한 4겹 방어**
- plan-impact: 변경 대상의 프로토콜/부모/같은 모듈까지 확장 탐색
- fz-plan Phase 0b: discover 로드 후 상위 수준 get_symbols_overview
- fz-code Phase 1.6: plan 영향 범위 < discover 범위이면 "시야 축소 위험" 마찰 신호
- cross-validation: review 시작 전 plan⊇discover 범위 확인

**네이티브 기능 강화**
- BATCH: merge 후 통합 빌드 gate 필수 + 부적합 조건 강화 (RIB/모듈 생성 금지)
- SIMPLIFY: 필수 gate 3가지 + 선택 suggestion 2가지 명확 분리 + 설계 의도 보존
- SC 조건 기반 자동 트리거: 빌드2실패→sc:troubleshoot, 3+Step 중간→sc:reflect, 복잡도4+→sc:estimate
- sc:save 모든 파이프라인 종료 시 (이전: 코드 변경만)

**정합성 개선**
- plan-edge-case: fz-plan YAML+registry+pipelines+pattern 4-way 동기화
- memory-curator: 모든 TEAM 참여 (이전: --deep/복잡도4+)
- plan-tradeoff: ARCHIVED (discover가 대체)
- 변경 파일 22개, RTM 19/19 verified, 리뷰 이슈 0건

### v3.0 (2026-03-30) — 3-Model Triad + 6-Agent Team + Landscape Discover

**3-Model Triad Architecture (연구 기반: X-MAS 47% 향상, ICLR 2025)**
- Claude(생산) + GPT/Codex(검증) + Gemini(Devil's Advocate) 3모델 체계
- fz-gemini 스킬 신규 생성 — Gemini CLI 전용 (review, verify, challenge)
- fz-codex에 --consensus 옵션 — 3모델 합의 모드
- cross-validation.md: Selective Consensus (불일치 시에만 Gemini 호출)
- team-core.md: 2-Tier → 3-Tier 모델 전략 (opus/sonnet/external)
- consensus-verify 파이프라인 신규 (#19)

**6-Agent Plan Team**
- fz-plan: 4 Claude + 1 GPT + 1 Gemini = 6개 차별화된 렌즈
- plan-impact 에이전트를 Impact Scanner로 강화 (Exhaustive Impact Scan 전담)
- Parallel Analysis + Cross-Feedback 통신 패턴
- 각 에이전트가 다른 질문을 던짐 (같은 질문 금지)

**Landscape Discover (discover 패러다임 전환)**
- "제약 발견 + 수렴" → "풍경 탐색 + 경로 매핑"
- provides: constraint-matrix → landscape-map + trade-off-table + open-questions
- 조건 불변성 구분: 🔒 hard constraint vs 🔓 soft preference
- discover는 결론을 내리지 않음 — plan이 경로를 선택
- adversarial 패턴: "부수기" → "비용/리스크 밝히기"

**Native Commands 활성화**
- /simplify: 선택 → 조건부 필수 (새 함수 3개+, 100줄+, 3회 빌드 실패)
- /batch: 독립 Step 3개+ 감지 시 자동 제안
- LOOP: 스킬별 에스컬레이션 래더 구체화

**Skill Refinement**
- fz-fix: 4-Phase 디버깅 (Reproduce → Isolate → Root-Cause → Verify Fix)
- fz-code: Step 완료 조건 3개 명시 (빌드 + conformance + caller 확인)
- Hooks 기반 물리적 강제: git commit 차단, platformFilter 자동 검사

**De-overfit**
- 반성 마커 제거 (규칙 유지, 출처만 삭제)
- Gate 체크리스트 경량화 (공통/조건부 분리)

### v2.5 (2026-03-20) — skill-creator Integration + Description Overhaul + Clean Architecture

**skill-creator 통합 (Runtime Trigger Eval + Description Optimization)**
- fz-skill에 `optimize` 서브커맨드 추가 — skill-creator `run_loop.py` 활용, train/test split 기반 description 자동 최적화
- fz-skill eval에 `Runtime Trigger Eval` phase 추가 — `run_eval.py`로 실제 `claude -p` 호출하여 트리거율 실측
- fz-skill create에 Phase 5 (Description Optimization 제안) 추가
- fz-manage benchmark에 `--with-trigger` 옵션 — 하위 3개 스킬 Quick Trigger Eval
- fz-manage check에 #11 skill-creator 설치 확인 항목 추가
- 신규 파일: `skills/fz-skill/references/skill-creator-integration.md` (L3 연동 가이드 + 실증 결과)
- 신규 파이프라인: #18 `skill-optimize` (pipelines.md)
- intent-registry.md에 fz-skill/fz-manage 자연어 트리거 보강

**실증 테스트 결과 및 교훈**
- 13개 스킬 전체 Runtime Trigger Eval 실행: 35/81 (43%)
- 핵심 발견: `claude -p` 자동 트리거는 슬래시 커맨드 스킬에 제한적 — should-NOT-trigger 100% 정확, should-trigger 0%
- description을 pushy 패턴으로 변경해도 트리거율 변화 없음 (43%→44%)
- 근본 원인: Claude가 간단한 요청을 스킬 참조 없이 직접 처리하는 경향
- 교훈 메모리 저장: `feedback_skill_creator_trigger_eval.md`

**전체 스킬 Description 고도화 (18/18)**
- skill-creator best practice 패턴 전면 적용:
  - Third-person: "This skill should be used when..."
  - Pushy triggers: "Make sure to use this skill whenever the user says: ..."
  - Keyword coverage: "Covers: ..." (Korean + English)
  - Boundary: "Do NOT use for..."
- 누락 5개 스킬 추가 적용: fz-codex, fz-new-file, fz-pr-digest, fz-pr, fz-recording

**500줄 제한 준수**
- fz-review: 513 → 492줄 (redundant separators 제거)
- fz-peer-review: 503 → 497줄 (redundant separators 제거)

**Clean Architecture 가이드 (Uncle Bob 페르소나)**
- 신규 파일: `guides/clean-architecture.md`
- 내용: Dependency Rule, SOLID 5원칙, 4 Layers 정의, Boundary Crossing 규칙, Architecture Smells, Uncle Bob's Decision Rules, Pragmatic 균형
- review-arch 에이전트: Architecture Decision에 Dependency Rule + SOLID 위반 감지 연결
- impl-quality 에이전트: Architecture Consistency에 DIP 위반 감지 연결
- fz-plan 스킬: 영향 분석 Step 4 "Clean Architecture 원칙 확인" 추가

**생태계 건강 체크**
- 전체 13개 항목 건강 체크 실행: 12.5/13 PASSING
- YAML 필수 필드 100%, provides/needs 체인 완전, 깨진 참조 0개
- 에이전트 14개 전부 유효, 모듈 17개 전부 존재

### v2.4 (2026-03-18) — Remove GitButler + Git Workflow Simplification

**GitButler 제거**
- GitButler 스킬 삭제 (`skills/gitbutler/` — SKILL.md + 3 reference files, -1,551줄)
- README.md 스킬 목록, CLI 도구, Infrastructure 다이어그램에서 제거 (22→21 스킬)
- 이유: Claude Code와 함께 사용 시 이점 없음 — 단일 working directory 공유로 Agent 병렬 작업 시 상호 오염 발생

**Git 워크플로우 전환**
- GitButler CLI(`but`) → 표준 `git` 명령으로 전환
- 병렬 브랜치 작업: `git worktree`로 독립 디렉토리 생성 권장
- 세션 시작: `but pull` → `git pull upstream develop`

### v2.3 (2026-03-15) — 1M Context Optimization + Ecosystem Health Fix

**1M Context Infrastructure (Opus 4.6 1M)**
- Artifact Token Budget 신설 — 100K cap + eviction 우선순위 (context-artifacts.md)
- ASD 임계값 hybrid: `6+ step 또는 context-heavy` (기존 4+)
- Essential Context 500자→3,000자 (memory-policy.md, fz/SKILL.md)
- Proactive Module Loading — /fz Phase 0에서 핵심 모듈 선로드
- Compact 경고 6+→12+ step, 4-tier 파이프라인 전략
- prompt-optimization.md: 200K 하드코딩 → 상대 서술

**Ecosystem Health Check Fix (86→95점)**
- fz-plan: `needs: [refined-requirements]` → `[none]` (standalone 실행)
- Phase 0 index.md 생성 — 5개 스킬에 compact recovery 추가
- Discover 프로토콜: DISCOVER_TAG 기반 journal=덮어쓰기, phase=APPEND
- fz-peer-review: Serena memory 도구 추가 + 2개 CHECKPOINT fallback
- fz-excalidraw: 에러 대응 섹션 (18/18 일관성)
- memory-policy.md: 4개 테이블 전면 수정 (stale → actual write_memory)
- context-artifacts.md: CWD=PROJECT_ROOT 정의, standalone peer-review workdir

**Agent Tier-1 Enrichment**
- BAD/GOOD 예시: review-direction, review-arch, review-quality, memory-curator
- Escalation Criteria: 5개 review 에이전트
- Input Format (Task Brief): review-direction, memory-curator
- Cross-skill wiring: fz-code direction-challenge, fz-review step files hydration

**Cross-skill Context**
- team-core.md: 통신 기록 요약 기본 + 원본 drill-down (*-team-full.md)
- cross-validation.md: Codex transcript 요약/원본 분리 정책

### v2.2 (2026-03-12) — Agent Teams + Context Budget + Peer Review Gate

**Agent Teams Frontmatter 적용 (Phase 1-4)**
- `memory: project|user` — 5개 에이전트에 세션 간 영속 학습 적용 (review-arch, impl-correctness, plan-structure, review-quality, memory-curator)
- `skills: [name]` — review-arch(arch-critic), review-quality(code-auditor)에 스킬 사전 주입
- `isolation: worktree` — impl-correctness에 코드 수정 격리
- `TaskCompleted` hook — 에이전트 완료 시 산출물 존재 검증 (settings.json 팀 레벨)
- team-registry.md 모델 컬럼을 `default`/`promoted`로 분리 (거버넌스 명확화)
- agent-team-guide.md §8 전체 문서화

**Context Budget 관리**
- prompt-optimization.md §2.5 — MCP 출력 격리, 도구 정의 최소화, 서브에이전트 효율
- 트리밍 비저하 원칙 — Gate/Few-shot/Step 삭제 금지 (prompt-optimization.md + skill-authoring.md)
- context-artifacts.md — 사전 예방적 Context 관리 섹션 추가

**Peer Review Deleted Logic Migration Gate**
- Gate 4.7-A — 모듈화/리팩토링 PR에서 "삭제 = 누락" 오탐 방지
- arch-critic, code-auditor, review-quality에 "삭제 vs 이동 판별" 원칙 추가
- fz-peer-review, fz-review 토큰 최적화 (-230줄, 정보 보존)

---

## Guides (5개)

스킬/에이전트 작성과 운영을 위한 실전 가이드.

| 가이드 | 설명 |
|--------|------|
| **prompt-optimization.md** | 10대 프롬프트 원칙 + TEAM 추론 품질 3원칙 + Context Rot 대응 + ACE 패턴 |
| **skill-authoring.md** | 스킬 작성 7원칙. YAML 설계, Progressive Disclosure, Gate, Evaluator-Optimizer |
| **skill-testing.md** | 3단계 테스트 프레임워크 (Triggering, Functional, Performance) + eval 자동화 |
| **skill-troubleshooting.md** | Triggering 문제, 지시 미준수, MCP 에러, TEAM 프로토콜 위반 진단 |
| **agent-team-guide.md** | 에이전트 팀 운영 가이드. 2.5-Turn Protocol, Task Brief, 모델 전략 |

---

## 메모리 시스템

3계층 메모리로 세션 간 지식을 유지합니다.

| 계층 | 저장소 | 용도 | 관리 |
|------|--------|------|------|
| **L1** | `~/.claude/projects/*/memory/` | 프로젝트별 교훈, 패턴, 규칙 | fz-memory (topic file + 태깅) |
| **L2** | Serena Memory (`fz:*` 키) | 세션 상태, 산출물, 체크포인트 | fz-memory GC (세션 종료 시 정리) |
| **L3** | ASD 폴더 (파일) | 장기 작업 산출물, compact 복원용 | context-artifacts.md 정책 |
