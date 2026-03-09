# fz

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 기반 AI 개발 워크플로우 오케스트레이션 시스템.

자연어 요청을 분석하여 복잡도 기반으로 스킬 파이프라인을 자동 구성하고, 필요 시 멀티 에이전트 팀을 편성하여 실행합니다.

---

## 전체 구조

```
~/.claude/
├── skills/           # 22개 스킬 — 사용자가 직접 호출하는 워크플로우 단위
│   ├── fz/           # 오케스트레이터 (모든 스킬의 진입점)
│   ├── fz-*/         # 18개 도메인별 스킬
│   ├── arch-critic/  # 아키텍처 비평 (peer review용)
│   ├── code-auditor/ # 코드 품질 감사 (peer review용)
│   └── gitbutler/    # GitButler CLI 통합
├── agents/           # 14개 에이전트 — 팀 모드에서 전문 역할 수행
├── modules/          # 15개 모듈 — 스킬/에이전트가 공유하는 설정과 정책
│   └── patterns/     # 5개 팀 통신 패턴
└── templates/        # 스킬/에이전트/모듈 생성 템플릿
```

### 관계도

```
사용자 → /fz "요청" → 의도 분석 → 복잡도 평가 → 파이프라인 구성 → 실행
                                                          │
                        ┌─────────────────────────────────┤
                        │                                 │
                    SOLO 모드                          TEAM 모드
                  (Lead 단독)                    (Lead + N개 에이전트)
                        │                                 │
                  스킬 순차 실행                     TeamCreate → 협업
                        │                         에이전트 간 직접 대화
                        │                         합의 → Lead 게이트
                        ▼                                 ▼
                      산출물                              산출물
```

---

## Skills (22개)

### 오케스트레이터

| 스킬 | 호출 | 설명 |
|------|------|------|
| **fz** | `/fz "요청"` | 유니버셜 오케스트레이터. 자연어 → 스킬 파이프라인 자동 구성 + 복잡도 기반 SOLO/TEAM 결정 + 모델 승격 |

### 개발 워크플로우

| 스킬 | 호출 | 설명 |
|------|------|------|
| **fz-plan** | `/fz-plan` | 계획 수립 + 요구사항 분석 + 설계. 영향 범위 분석, Anti-Pattern Constraints 정의, 구현 전략 수립 |
| **fz-code** | `/fz-code` | 코드 구현 + 빌드 검증. 계획 기반 점진적 구현, 매 Step마다 빌드 검증 + 마찰 감지 |
| **fz-fix** | `/fz-fix` | 버그 수정. 원인 분석 → 수정 → 빌드 검증의 빠른 사이클 |
| **fz-review** | `/fz-review` | 자기 코드 리뷰. Claude + Codex + sc:analyze 3중 검증, 역방향 검증 |
| **fz-commit** | `/fz-commit` | Conventional Commit 형식 커밋 생성 |
| **fz-pr** | `/fz-pr` | Fork 기반 PR 생성 자동화 (push → PR create) |

### 탐색 & 발견

| 스킬 | 호출 | 설명 |
|------|------|------|
| **fz-discover** | `/fz-discover` | 제약조건 발견 + 요구사항 정제. 소크라테스식 대화로 암묵적 제약을 표면화, Reject-Extract-Propose 프로토콜 |
| **fz-search** | `/fz-search "대상"` | 코드 탐색 + 구조 분석 + 의존성 추적. 병렬 교차 검증으로 정확도 확보 |

### 검증 & 리뷰

| 스킬 | 호출 | 설명 |
|------|------|------|
| **fz-codex** | `/fz-codex` | Codex CLI를 통한 독립적 코드/계획 검증. Cross-model 상호검증 모듈 |
| **fz-peer-review** | `/fz-peer-review` | 동료 PR 리뷰. 3-Model Cross-Review, 9개 관점 독립 분석 |
| **fz-pr-digest** | `/fz-pr-digest` | PR/브랜치 변경 설명. Before/After 비교, 아키텍처 컨텍스트, 기술 학습 포인트 |

### 문서 & 지식

| 스킬 | 호출 | 설명 |
|------|------|------|
| **fz-doc** | `/fz-doc` | 스킬/에이전트/CLAUDE.md 문서 작성 + 개선. 가이드라인 기반 최적화 |
| **fz-memory** | `/fz-memory` | 메모리 관리 + 교훈 회상. L1(Auto Memory) 정리, L2(Serena) GC, topic file 관리 |
| **fz-recording** | `/fz-recording` | 녹음 파일 → 화자 분리 + 회의록 생성. AssemblyAI STT + AI 첨언 |

### 시스템 관리

| 스킬 | 호출 | 설명 |
|------|------|------|
| **fz-skill** | `/fz-skill` | 스킬/에이전트 CRUD + eval 품질 평가. L3/L2/L1 지능형 생성 |
| **fz-manage** | `/fz-manage` | 생태계 관리. 인벤토리, 의존성, 헬스체크, 배치 벤치마크 |
| **fz-new-file** | `/fz-new-file` | 새 파일 생성 시 헤더 서명 규칙 적용 |
| **fz-excalidraw** | `/fz-excalidraw` | Excalidraw 다이어그램 생성/수정. 아키텍처, 워크플로우, 데이터 플로우 시각화 |

### 보조 스킬

| 스킬 | 호출 | 설명 |
|------|------|------|
| **arch-critic** | (팀 내부용) | 아키텍처 비평. 설계 결정과 확장성 평가 |
| **code-auditor** | (팀 내부용) | 코드 품질 감사. 기능 분해, API 사용, 의존성 영향 평가 |
| **gitbutler** | `but` | GitButler CLI 통합. `git` 대신 `but` 사용 |

---

## Agents (14개)

TEAM 모드에서 에이전트는 Lead(오케스트레이터)가 스폰하며, **에이전트 간 직접 대화(Peer-to-Peer)**로 협업합니다.

### 계획 에이전트

| 에이전트 | 역할 |
|---------|------|
| **plan-structure** | 구현 구조 + Step 순서 설계. 요구사항 분해, 영향 범위 분석 |
| **plan-impact** | 영향 범위 + 소비자 변경 추적. 변경의 파급 효과 분석 |
| **plan-edge-case** | 엣지 케이스 + 실패 시나리오 발굴. 계획의 약점과 누락 탐지 |
| **plan-tradeoff** | 트레이드오프 + 대안 비교 평가. 설계 선택지의 장단점 분석 |

### 구현 에이전트

| 에이전트 | 역할 |
|---------|------|
| **impl-correctness** | 구현 정확성 + 테스트 작성. 계획 기반 점진적 구현과 기능 정확성 보장 |
| **impl-quality** | 코딩 표준 + 패턴 일관성 감시. 구현 중 실시간 품질 피드백 |

### 리뷰 에이전트

| 에이전트 | 역할 |
|---------|------|
| **review-arch** | 아키텍처 결정 + 레이어 위반 리뷰. 설계 결정과 확장성 평가 |
| **review-correctness** | 기능 정확성 + 요구사항 충족 리뷰. 구현이 계획과 일치하는지 검증 |
| **review-quality** | 코드 품질 + Dead Code + 성능 리뷰. 기능 분리, API 사용, 성능 평가 |
| **review-direction** | 방향성 적합성 + 대안 제시. 접근 방향 자체가 최선인지 도전 (PROCEED/RECONSIDER/REDIRECT) |
| **review-counter** | 반론 + Devil's Advocate. 다른 리뷰어의 판단에 의도적으로 반박 |

### 탐색 에이전트

| 에이전트 | 역할 |
|---------|------|
| **search-pattern** | 패턴 기반 코드 탐색. Grep/Glob으로 넓은 범위 텍스트/파일 패턴 검색 |
| **search-symbolic** | 심볼 기반 코드 탐색. LSP/Serena로 심볼 정의/참조/타입 정밀 탐색 |

### 메모리 에이전트

| 에이전트 | 역할 |
|---------|------|
| **memory-curator** | 메모리 큐레이션. topic file + Serena Memory에서 관련 교훈/패턴/결정사항 발굴 |

---

## Modules (15개)

스킬과 에이전트가 공유하는 설정, 정책, 프로토콜.

### 핵심 인프라

| 모듈 | 설명 |
|------|------|
| **team-core.md** | TEAM 공통 프로토콜. 2.5-Turn 통신, 절대 규칙, 모델 전략 |
| **team-registry.md** | 역량 기반 동적 팀 구성. 도메인 지정 시 에이전트 자동 수집 |
| **build.md** | 빌드 검증 공통 모듈 |
| **session.md** | 세션 자동 감지 + 이슈 트래커 연동 |

### 정책 & 전략

| 모듈 | 설명 |
|------|------|
| **complexity.md** | 5차원 복잡도 평가 (Scope, Depth, Risk, Novelty, Verification) → SOLO/TEAM 결정 |
| **intent-registry.md** | 의도 트리거 패턴 + confidence 판정 규칙 |
| **pipelines.md** | 14개 사전 정의 파이프라인 (트리거 + 체인 + 게이트 + 팀 구성) |
| **execution-modes.md** | 실행 모드 확장 (BATCH, LOOP, SIMPLIFY) |
| **governance.md** | 거버넌스 프레임워크. 변경 통제, 품질 게이트, 긴급 정지 |
| **codex-strategy.md** | Codex 실행 전략. Base Branch, Effort, Diff Size, CLI Mode 설정 |

### 메모리 관리

| 모듈 | 설명 |
|------|------|
| **memory-guide.md** | L1 Auto Memory 관리 정책. MEMORY.md + topic file 관리 |
| **memory-policy.md** | L2 Serena Memory 관리. 키 네이밍(`fz:*`) + GC 정책 |

### 컨텍스트 & 산출물

| 모듈 | 설명 |
|------|------|
| **context-artifacts.md** | Context Artifact 관리. 파일 기반 산출물 기록, compact 복원 전략 |
| **cross-validation.md** | 교차 검증 게이트 자동 삽입. Codex + 빌드 + enforcement |
| **plugin-refs.md** | 플러그인 참조 가이드. 스킬-역할별 플러그인 매칭 |

### 팀 통신 패턴 (patterns/)

| 패턴 | 적용 스킬 | 설명 |
|------|----------|------|
| **adversarial.md** | fz-discover | 선택지를 만들고 부수며 제약 발견 |
| **collaborative.md** | fz-plan | 만들면서 동시에 토론하여 설계 개선 |
| **pair-programming.md** | fz-code | 구현 중 실시간 품질 검증 |
| **live-review.md** | fz-review, fz-peer-review | 2인이 다른 렌즈로 동시 리뷰 |
| **cross-verify.md** | fz-search | 독립 탐색 전략 2개 → 교차 검증 |

---

## 실행 모드

### SOLO vs TEAM

| | SOLO | TEAM |
|---|------|------|
| **판단 기준** | 복잡도 점수 0-3 | 복잡도 점수 4+ |
| **실행자** | Lead(Opus) 단독 | Lead(Opus) + Primary(Opus) + N x Sonnet |
| **통신** | 없음 (순차 실행) | 에이전트 간 Peer-to-Peer 직접 대화 |
| **교차 검증** | 선택적 | Codex 필수 참여 |
| **강제 옵션** | `--solo` | `--team`, `--deep` |

### 실행 모드 확장

| 모드 | 옵션 | 설명 |
|------|------|------|
| **STANDARD** | (기본) | 일반 순차/병렬 실행 |
| **BATCH** | `--batch` | worktree 격리 병렬 실행. 독립 3개+ 대상 |
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
| **drift-check** | "드리프트 체크" | fz-codex drift |
| **peer-review** | "PR 리뷰해줘" | fz-peer-review |

---

## 외부 의존성

### 필수

- **Claude Code** CLI

### 선택 (있으면 강화됨, 없으면 graceful degradation)

| 도구 | 용도 | 없을 때 |
|------|------|--------|
| Serena MCP | 심볼릭 서치, L2 메모리, 세션 | Grep/Glob 폴백 |
| Codex CLI | Cross-model 교차 검증 (TEAM) | 검증 단계 스킵 |
| SuperClaude (sc:*) | 분석, 인덱싱, 세션 저장 | 해당 기능 비활성 |
| Context7 MCP | API 문서 조회 | 수동 참조 |
| XcodeBuildMCP | iOS 빌드 검증 | xcodebuild 폴백 |
| GitButler CLI | git 작업 | 표준 git 사용 |

---

## 메모리 시스템

3계층 메모리로 세션 간 지식을 유지합니다.

| 계층 | 저장소 | 용도 | 관리 |
|------|--------|------|------|
| **L1** | `~/.claude/projects/*/memory/` | 프로젝트별 교훈, 패턴, 규칙 | fz-memory (topic file + 태깅) |
| **L2** | Serena Memory (`fz:*` 키) | 세션 상태, 산출물, 체크포인트 | fz-memory GC (세션 종료 시 정리) |
| **L3** | ASD 폴더 (파일) | 장기 작업 산출물, compact 복원용 | context-artifacts.md 정책 |
