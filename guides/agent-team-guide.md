# Agent & Team Configuration Guide

> fz-* 스킬 생태계에서 에이전트 작성 및 팀 구성을 위한 종합 가이드.
> 에이전트는 `.claude/agents/*.md`에 위치하며, 팀은 TeamCreate + SendMessage로 Peer-to-Peer 통신한다.

---

## 1. 에이전트 작성법

### 역할 선언 패턴

1줄로 시작한다: `"You are a {role} for {domain/project}."`

구체적 역할 + 도메인을 명시해야 한다.

```
BAD:  "You are a helpful assistant."
GOOD: "You are an architecture critic for a RIBs + Clean Architecture iOS project."
```

- 역할이 모호하면 에이전트가 범용 응답을 생성한다.
- 도메인을 명시하면 MCP 도구 선택과 분석 깊이가 달라진다.

### MCP 도구 계층화

에이전트가 사용하는 도구는 4-tier로 계층화한다.

| Tier | 용도 | 예시 |
|------|------|------|
| Primary (항상 사용) | 핵심 분석 도구 | serena find_symbol, get_symbols_overview |
| Secondary (필요 시) | 보조 도구 | context7 query-docs |
| Unavailable (Team 제약) | Lead 전용 | Atlassian, XcodeBuild, LSP (일부) |

> Fallback은 명시하지 않는다. `tools:` YAML이 사용 가능한 도구를 선언하므로 Claude가 자연스럽게 폴백한다.

에이전트 파일에 Primary, Secondary, Unavailable만 선언한다:

```markdown
## Tools Strategy
- **Primary**: serena find_symbol, serena get_symbols_overview
- **Secondary**: context7 query-docs (외부 문서 참조 시)
- **Unavailable**: 빌드 MCP 도구, Atlassian (Lead에게 요청)
```

### 중요: Team Agent 도구 제약

Team 에이전트는 일부 MCP 도구를 직접 호출할 수 없다:

- **Atlassian (JIRA)** -- Lead에게 요청하여 이슈 조회/생성
- **빌드 MCP 도구** -- Lead에게 요청하여 빌드/테스트 실행
- **일부 LSP 도구** -- Lead가 빌드 검증 후 결과 공유

에이전트가 이 도구들이 필요한 경우 SendMessage로 Lead에게 요청한다:

```
SendMessage(lead): "빌드 검증 필요합니다. 대상: TVINGApp scheme, 변경 파일: {list}"
```

### 모델 선택 기준

| 역할 | 기본 모델 | 승격 조건 | 승격 모델 |
|------|----------|----------|----------|
| Lead | opus | -- | -- |
| Primary Worker | sonnet | 특정 팀에서 핵심 생산자 | opus |
| Supporting | sonnet | -- | -- |

승격 예시:

- **plan-structure**: plan / plan-to-code / full-cycle 팀에서 opus로 승격
- **impl-correctness**: code / code-to-review / full-cycle 팀에서 opus로 승격
- **review-arch**: review-only / peer-review 팀에서 opus로 승격

승격은 팀 정의에서 선언하며, 에이전트 파일 자체는 기본 모델(sonnet)을 유지한다.
승격 조건은 에이전트 파일에 주석으로 남긴다:

```markdown
<!-- model-upgrade: opus when Primary in plan/code/full-cycle teams -->
```

### Agent 파일 체크리스트

- [ ] name: `{domain}-{specialty}` (예: `plan-structure`, `review-arch`)
- [ ] description: role + expertise + team context
- [ ] model: 기본 sonnet (승격 조건 주석으로)
- [ ] tools: 최소 필요 도구만 (4-tier 전략 포함)
- [ ] Peer-to-Peer 통신 규칙 포함
- [ ] MCP 도구 4-tier 전략 포함
- [ ] 워크플로우 번호 매김 (Step 1, 2, 3...)
- [ ] 결과 보고 형식 명시 (Markdown 구조)

Agent 템플릿: `.claude/templates/agent-template.md`를 기반으로 작성한다.

---

## 2. 팀 설계법

### TeamCreate 패턴

```
TeamCreate("{skill}-{feature}")
+-- Lead (Opus): 오케스트레이션 + 게이트 실행 + 중재
+-- Primary Worker (Opus): 핵심 생산 (plan-structure 또는 impl-correctness)
+-- Supporting N (Sonnet): 검증/비평 (review-arch, review-quality 등)
+-- Codex CLI: cross-model 검증 (Lead가 fz-codex 실행)
```

팀 이름은 `{skill}-{feature}` 형식을 따른다 (예: `plan-auth-refactor`, `code-player-fix`).

### 핵심 원칙: Mesh Topology (Hub-and-Spoke 아님)

```
BAD (Hub-and-Spoke):
  Agent A --> Lead --> Agent B --> Lead --> Agent A
  (모든 메시지가 Lead를 거침 --> 병목 + 컨텍스트 손실)

GOOD (Mesh / Peer-to-Peer):
  Agent A <--> Agent B (직접 SendMessage)
  Agent B <--> Agent C (직접 SendMessage)
  합의 --> Lead에게 보고
  (Lead는 퍼실리테이터, 중재자, 게이트 실행자)
```

에이전트 간 직접 통신이 기본이다. Lead를 거치지 않는다.

### 2.5-Turn Protocol 핵심 규칙

| 규칙 | 내용 | 근거 |
|------|------|------|
| **Round 1 독립성** | 피어 초안을 보기 전에 자기 분석을 완성해야 함 | Sycophancy(동조) 방어 |
| **Round 0.5 보고** | [합의 항목] + [불합의 항목]을 반드시 분리 기재 | Lead가 교차 검증 상태 파악 |
| **Primary 전달 의무** | Supporting 발견을 중계 시 원문 핵심을 그대로 인용 | 요약/축소로 인한 정보 손실 방지 |
| **CC 옵션** | Supporting이 Primary에게 보내는 메시지를 다른 Supporting에게 동시 CC 가능 | 정보 전파 지연 방지 |

### Task Brief 5요소 (에이전트에게 작업 배정 시 필수)

```
[Role] 당신의 역할은 {역할}입니다
[Context] {작업 배경 + 이전 단계 결과}
[Goal] {구체적 목표 + 측정 가능한 완료 조건}
[Constraints] {건드리지 말 것 + 규칙}
[Deliverable] {기대 산출물 형식}
```

### Lead의 역할

1. **퍼실리테이터**: 문제 전파, 컨텍스트 공유, 작업 시작 지시
2. **모니터링**: 에이전트 진행 상황 추적
3. **중재**: 교착 상태 해소 (3라운드 초과 시 개입)
4. **게이트 실행**: 빌드 검증, Codex 검증 등 Lead-only 작업
5. **사용자 소통**: 결과 보고, 승인 요청

### Lead가 하지 않는 것

- 모든 메시지의 중계자 역할 (에이전트끼리 직접 SendMessage)
- 직접 코드 작성 (Primary Worker에 위임)
- 상세 분석 수행 (Supporting 에이전트에 위임)

---

## 3. 통신 패턴 5가지

> 각 패턴의 상세 구현은 `.claude/modules/patterns/` 디렉토리 참조.

### 3.1 Collaborative Design (fz-plan)

설계하는 도중에 실현성 검증하는 패턴.

```
plan-structure --> 초안 작성
  --> SendMessage(review-arch): "초안입니다. {설계 내용}"
review-arch --> 검토
  --> SendMessage(plan-structure): "의존성 역전 발견. 대안: {제안}"
plan-structure --> 반영
  --> SendMessage(review-arch): "수정했습니다. Y 영향은?"
review-arch --> 확인
  --> 양쪽 합의
  --> SendMessage(lead): "최종 설계안"
```

- plan-structure가 설계를 만들면 review-arch가 즉시 검토한다.
- 합의에 도달할 때까지 직접 대화한다.
- 합의 후 Lead에게 최종 결과를 보고한다.

### 3.2 Pair Programming (fz-code)

구현 중 실시간 질문/검토하는 패턴.

```
impl-correctness: Step N 구현 중
  --> SendMessage(review-arch): "이 패턴으로 구현 중인데 맞나요? {코드 스니펫}"
review-arch: 즉시 피드백
  --> SendMessage(impl-correctness): "OK" 또는 "다른 패턴 추천: {이유}"
impl-correctness: 반영 후 계속
```

- impl-correctness가 불확실한 지점에서 review-arch에게 질문한다.
- 완성 후 전체 리뷰가 아니라, 구현 도중 실시간 피드백이다.
- 빈도: Step 단위 또는 패턴 결정 시점.

### 3.3 Live Review (fz-review)

분석하면서 발견을 공유하는 패턴.

```
review-arch: 아키텍처 분석 중 --> 발견 즉시 공유
  --> SendMessage(review-quality): "레이어 위반 발견. 위치: {file}:{line}"
review-quality: 품질 분석 + 교차 확인
  --> SendMessage(review-arch): "동의. 추가로 dead code 발견: {file}"
양쪽 합의
  --> SendMessage(lead): "통합 리뷰 결과"
```

- 분석 완료 후 공유가 아니라, 분석 중 발견 즉시 공유한다.
- 교차 확인으로 false positive를 줄인다.
- 통합 결과를 Lead에게 보고한다.

### 3.4 Adversarial Constraint Discovery (fz-discover)

만들고 부수며 제약을 발견하는 패턴.

```
plan-structure: 후보 옵션 2-3개 생성
  --> SendMessage(review-arch): "후보입니다. 제약 위반 찾아주세요"
review-arch: 각 후보의 제약 위반 식별
  --> SendMessage(plan-structure): "옵션 A는 C1 위반. 근거: {코드 참조}"
plan-structure: 위반 안 하는 새 옵션 생성
  --> 반복 (수렴할 때까지)
  --> 합의
  --> SendMessage(lead): "옵션 D + 제약 매트릭스"
```

- plan-structure는 생성자, review-arch는 파괴자 역할이다.
- 반복을 통해 숨겨진 제약을 표면화한다.
- 최종 결과에 제약 매트릭스를 포함한다.

### 3.5 Cross-Verify Search (fz-search --deep)

발견 즉시 교차 확인하는 패턴.

```
search-symbolic: Serena 기반 탐색 결과
  --> SendMessage(search-pattern): "이 심볼 찾았는데 확인해주세요: {symbol}"
search-pattern: Grep 기반 교차 확인
  --> SendMessage(search-symbolic): "확인. 추가로 2개 더 발견: {locations}"
양쪽 합의
  --> SendMessage(lead): "교차 검증된 탐색 결과"
```

- search-symbolic은 AST/LSP 기반, search-pattern은 텍스트 패턴 기반이다.
- 서로 다른 방법론으로 교차 확인하여 누락을 방지한다.
- 양쪽 모두 sonnet으로 동작한다 (비용 효율).

---

## 4. 모델 전략

### 2-Tier 원칙

| Tier | 모델 | 역할 | 비용 |
|------|------|------|------|
| Tier 1 | opus | Lead + Primary Worker | 높음 |
| Tier 2 | sonnet | Supporting agents | 중간 |

- **haiku**: 이 프로젝트에서 미사용. 고성능 추론이 목표이므로 품질 저하 불가.
- **Lead + Primary 동시 최대 2개 opus 원칙**: 팀당 동시 opus 인스턴스를 2개 이하로 유지한다.
  - **순차 승격** 허용: review-direction은 Direction Challenge(Round 0.5)에서 opus로 순차 승격 가능. Round 0.5 완료 후 Round 1이 시작되므로 동시 opus는 2개를 초과하지 않음.
  - 예외: full-cycle / plan-to-code 파이프라인에서 plan과 code 각각 Primary가 다르므로 순차적으로 opus를 사용한다.
- **sonnet 상한**: 명시적 제한 없음. 단, 거버넌스 리소스 초과(5개+ 동시 실행) 시 추가 스폰 차단.

### 모델 승격 매트릭스

상세 내용은 `.claude/modules/team-registry.md` 참조.

| 파이프라인 | Primary Worker (opus) | Supporting (sonnet) |
|-----------|----------------------|---------------------|
| plan-* | plan-structure | review-arch, plan-tradeoff, plan-edge-case |
| code-* | impl-correctness | review-arch, impl-quality |
| review-* | review-arch | review-quality, review-correctness |
| search --deep | (both sonnet) | search-symbolic + search-pattern |
| bug-hunt | impl-correctness | search-symbolic |

Primary Worker는 해당 파이프라인에서 opus로 승격된다.
Supporting은 항상 sonnet을 유지한다.

---

## 5. Codex 통합

### cross-model 상호검증 원칙

- 모든 TEAM 구성에 Codex CLI가 포함된다.
- **Lead가 직접** `/fz-codex`를 실행한다 (에이전트가 Codex를 직접 호출하지 않음).
- Claude (opus/sonnet) + Codex (다른 모델)의 교차 검증으로 blind spot을 보완한다.

### 검증 게이트 삽입 위치

| 시점 | Codex 명령 | 대상 |
|------|-----------|------|
| plan 완료 후 | `/fz-codex verify` | 설계 검증: 제약 위반, 누락 확인 |
| code 완료 후 | `/fz-codex check` | 코드 검증: 구현 품질, 패턴 준수 |
| commit 전 | `/fz-codex check` | 최종 검증: 빌드 가능성, 회귀 위험 |

### Codex 결과 처리 흐름

```
Lead --> /fz-codex verify --> Codex 결과 수신
  결과가 PASS --> 다음 단계 진행
  결과가 FAIL --> 관련 에이전트에 SendMessage로 수정 지시
    --> 수정 후 재검증
```

Codex 결과와 Claude 에이전트 결과가 충돌하면 Lead가 판단하고 사용자에게 보고한다.

---

## 6. Anti-Patterns

| Anti-Pattern | 이유 | 대안 |
|-------------|------|------|
| Hub-and-Spoke | 병목 + 컨텍스트 손실 | Mesh (Peer-to-Peer) |
| 서브에이전트 과다 | Claude 4.6 경향, 비용 폭증 | SOLO for simple tasks |
| standalone Task | 통신 불가, 고립된 작업 | TeamCreate 필수 |
| Lead가 직접 생산 | 역할 혼재, 오케스트레이션 품질 저하 | Primary Worker에 위임 |
| 모든 에이전트 opus | 비용 초과, 불필요한 자원 사용 | 2-Tier (Lead+Primary=opus, rest=sonnet) |
| 에이전트 간 Lead 중계 | 지연 + 컨텍스트 손실 | 직접 SendMessage |
| MCP 도구 무분별 사용 | 실패 시 복구 불가 | 4-tier 도구 전략 |
| 승격 조건 미명시 | 팀마다 모델이 달라 혼란 | 에이전트 파일에 주석 |

---

## 7. 새 에이전트 추가 체크리스트

새 에이전트를 추가할 때 다음을 확인한다:

- [ ] `.claude/templates/agent-template.md` 기반으로 작성했는가?
- [ ] 기존 에이전트와 역할 중복이 없는가?
  - plan-structure: 설계/계획 구조
  - plan-tradeoff: 트레이드오프 분석
  - plan-edge-case: 경계 케이스 분석
  - plan-impact: 영향 범위 분석
  - review-arch: 아키텍처 비평
  - review-quality: 코드 품질 감사
  - review-correctness: 정확성 검증
  - review-counter: 역방향 검증
  - review-direction: 방향성 도전, PROCEED/RECONSIDER/REDIRECT 판정
  - impl-correctness: 코드 구현
  - impl-quality: 구현 품질
  - search-symbolic: AST/LSP 기반 탐색
  - search-pattern: 텍스트 패턴 기반 탐색
- [ ] MCP 도구 4-tier 전략을 명시했는가?
- [ ] Peer-to-Peer 통신 규칙을 포함했는가?
- [ ] 모델 승격 조건을 주석으로 명시했는가?
- [ ] `/fz-manage check` 통과 (에이전트 건강 체크 #7, #8)?
- [ ] `.claude/guides/prompt-optimization.md` 10대 원칙을 준수하는가?

### 추가 시 업데이트 필요 항목

새 에이전트가 기존 팀에 참여하는 경우:

1. `.claude/modules/team-registry.md`에 에이전트 1줄 추가
2. 관련 스킬 파일에서 TeamCreate 구성 업데이트
3. 통신 대상 에이전트의 Peer-to-Peer 규칙 업데이트
4. 모델 승격 매트릭스 업데이트 (Section 4 참조)

### 현재 에이전트 요약

| 에이전트 | Domain | 기본 모델 | 전문 영역 |
|---------|--------|----------|----------|
| plan-structure | plan | sonnet (opus 승격) | 설계, 계획, 구조화 |
| plan-tradeoff | plan | sonnet | 트레이드오프 분석 |
| plan-edge-case | plan | sonnet | 경계 케이스 발견 |
| plan-impact | plan | sonnet | 영향 범위 분석 |
| review-arch | review | sonnet (opus 승격) | 아키텍처 비평, 설계 검증 |
| review-quality | review | sonnet | 코드 품질, 컨벤션 감사 |
| review-correctness | review, implement | sonnet | 정확성, 로직 검증 (fz-code TEAM 배정) |
| review-counter    | review    | sonnet             | 역방향 검증, 반박 |
| review-direction  | review    | sonnet (opus 승격) | 방향성 도전, PROCEED/RECONSIDER/REDIRECT 판정 |
| impl-correctness | implement | sonnet (opus 승격) | 코드 구현, 리팩토링 |
| impl-quality | implement | sonnet | 구현 품질, 최적화 |
| search-symbolic | search | sonnet | AST/LSP 심볼 탐색 |
| search-pattern | search | sonnet | 텍스트 패턴 탐색 |
| memory-curator | memory | sonnet | 교훈 발굴, 컨텍스트 매칭 |

전체 에이전트 capabilities: `.claude/modules/team-registry.md` 참조.

---

## 8. Agent Frontmatter 고급 기능 (v2.1+)

> Source: Claude Code 공식 Sub-agents/Agent Teams 문서 (2026-03). 기존 fz 에이전트에 점진적으로 적용.

### 8.1 Persistent Memory (`memory` 필드)

에이전트가 세션 간 학습 내용을 영속 저장한다. `~/.claude/agent-memory/{name}/` (user) 또는 `.claude/agent-memory/{name}/` (project).

```yaml
---
name: review-arch
memory: project
---
```

- 에이전트가 MEMORY.md를 자동 관리 (200줄 제한, 자동 큐레이션)
- 코드베이스 패턴, 아키텍처 결정, 반복 이슈를 세션 간 축적
- **적용 우선순위**: review-arch (아키텍처 패턴) > impl-correctness (버그 패턴) > review-quality (품질 패턴)

### 8.2 Skills Preloading (`skills` 필드)

에이전트 context에 스킬 내용을 사전 주입한다. Read(SKILL.md) 턴이 불필요해진다.

```yaml
---
name: impl-correctness
skills:
  - fz-code
---
```

- 스킬 전체 내용이 시스템 프롬프트에 포함됨
- 부모 대화의 스킬을 상속하지 않음 — 명시적 선언 필요
- **주의**: 스킬 내용이 context를 소비하므로 필요한 스킬만 선별

### 8.3 Per-Agent Hooks (`hooks` 필드)

에이전트별 라이프사이클 훅으로 자동 품질 게이트를 구현한다.

```yaml
---
name: impl-correctness
hooks:
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/lint-check.sh"
---
```

| 이벤트 | 용도 | 예시 |
|--------|------|------|
| PreToolUse | 도구 사용 전 검증 | Bash 명령 화이트리스트 |
| PostToolUse | 도구 사용 후 검증 | 편집 후 린트 실행 |
| Stop | 에이전트 완료 시 | 최종 출력 형식 검증 |

- **팀 훅**: `TeammateIdle` (exit 2=계속 작업), `TaskCompleted` (exit 2=완료 차단)은 settings.json에서 정의

### 8.4 Worktree Isolation (`isolation` 필드)

에이전트가 격리된 git worktree에서 실행된다. 파일 충돌 방지.

```yaml
---
name: impl-correctness
isolation: worktree
---
```

- 변경 없으면 worktree 자동 정리
- **적용**: TEAM code에서 impl-correctness가 코드 수정 시 안전한 격리 환경

### 8.5 기타 유용한 필드

| 필드 | 용도 | fz 활용 |
|------|------|---------|
| `maxTurns` | 에이전트 턴 수 제한 | Supporting 에이전트의 과도한 분석 방지 |
| `disallowedTools` | 도구 차단 (denylist) | `tools` allowlist의 보완 |
| `permissionMode` | 에이전트별 권한 | review → `plan` (read-only), impl → `acceptEdits` |
| `mcpServers` | 에이전트별 MCP | review-arch → serena만, review-quality → serena + context7 |
| `background: true` | 항상 백그라운드 | 탐색/캐싱 에이전트에 적합 |

### 8.6 도입 로드맵

| 단계 | 적용 | 대상 에이전트 | 상태 |
|------|------|-------------|------|
| Phase 1 | `memory: project\|user` | review-arch, impl-correctness, plan-structure, review-quality(project), memory-curator(user) | ✅ 적용 |
| Phase 2 | `skills:` | review-arch(arch-critic), review-quality(code-auditor) | ✅ 적용 |
| Phase 3 | `TaskCompleted` hook | settings.json (팀 레벨) | ✅ 적용 (산출물 미작성 방지) |
| Phase 4 | `isolation: worktree` | impl-correctness | ✅ 적용 |

---

## Quick Reference

```
에이전트 작성:
  1. agent-template.md 복사
  2. 역할 1줄 선언
  3. 도구 4-tier 명시
  4. 통신 규칙 추가
  5. 체크리스트 확인
  6. team-registry.md에 등록

팀 구성:
  1. TeamCreate("{skill}-{feature}")
  2. Lead(opus) + Primary(opus) + Supporting(sonnet) + Codex
  3. Mesh topology (Peer-to-Peer)
  4. Lead = 퍼실리테이터/게이트/중재자

통신:
  에이전트 --> SendMessage(에이전트)  (직접)
  합의 --> SendMessage(lead)          (보고)
  Lead --> /fz-codex                  (검증 게이트)

고급 (§8):
  memory: project → 세션 간 학습
  skills: [fz-code] → 스킬 사전 주입
  hooks: PostToolUse → 자동 품질 게이트
  isolation: worktree → 코드 수정 격리
```
