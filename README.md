# fz

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 기반 AI 개발 워크플로우 오케스트레이션 시스템.

자연어 요청 → 복잡도 평가 → 스킬 파이프라인 자동 구성 → 멀티 에이전트 팀 편성 → 실행.

---

## Quick Start

```bash
/fz "버그 찾아서 고쳐줘"              # bug-hunt → fz-search → fz-fix
/fz "새 기능 계획하고 구현해줘" --team  # plan-to-code (TEAM 모드)
/fz "코드 리뷰하고 커밋해줘"           # review-to-ship
/fz "이걸 어떻게 구현하면 좋을까?"      # discover → 풍경 탐색
```

| 옵션 | 설명 |
|------|------|
| `--solo` | Lead 단독 실행 |
| `--team` | 멀티 에이전트 팀 |
| `--deep` | --team + 교차 검증 강화 |
| `--batch` | worktree 병렬 실행 |
| `--loop` | 자동 반복 + 에스컬레이션 |

---

## Architecture

```
~/.claude/
├── skills/          21개 — /fz, /fz-plan, /fz-code, /fz-review, /fz-fix ...
├── agents/          14개 — plan-structure, impl-correctness, review-arch ...
├── modules/         20개 — team-core, pipelines, cross-validation, lead-reasoning, system-reminders ...
│   └── patterns/    5개 — adversarial, collaborative, pair-programming ...
├── guides/          7개 — prompt-optimization, skill-authoring, harness-engineering ...
├── codex-skills/    8개 — Codex 네이티브 스킬 (fz-reviewer, fz-architect ...)
├── scripts/         설치/설정 스크립트 (setup-codex-skills.sh)
└── templates/       스킬/에이전트/CLAUDE.md 생성 템플릿
```

### 오케스트레이션 플로우

```
자연어 요청
    ↓
Phase 0  Session Bootstrap ─── sc:load, 인덱스, ASD 폴더
Phase 1  Intent Analysis ───── 키워드 → intent-triggers 매칭
Phase 2  Complexity ─────────── 5차원 평가 → SOLO(0-3) / TEAM(4+)
Phase 3  Pipeline + Team ────── 19개 파이프라인 매칭 + 에이전트 배정
Phase 4  User Confirmation ─── 시각화 → 승인
Phase 5  Execute ────────────── 스킬 체인 실행 + Gate 검증
    ↓
완료: GC → sc:save → 다음 행동 안내
```

### TEAM 모드: 2.5-Turn Protocol

```
Lead (Opus) ─── 퍼실리테이터: 모니터링 + Gate 실행
    │
    ├── ★Primary (Opus) ←→ Supporting (Sonnet)
    │   Round 1: 독립 분석 (피어 참조 금지)
    │   Round 2: 피드백 + 반박 (직접 SendMessage)
    │   Round 0.5: [합의/불합의] Lead에 보고
    │
    └── External: Codex(GPT-5.4)
```

---

## Skills

| 카테고리 | 스킬 | 설명 |
|---------|------|------|
| **오케스트레이터** | `/fz` | 자연어 → 파이프라인 자동 구성 |
| **개발** | `/fz-plan` | 요구사항 분석 + 영향 범위 + RTM |
| | `/fz-code` | 계획 기반 점진적 구현 + 빌드 검증 |
| | `/fz-fix` | 버그 수정 (4-Phase 디버깅) |
| | `/fz-review` | 3중 검증 (Claude + Codex + sc:analyze) + L3 에이전트 |
| | `/fz-commit`, `/fz-pr` | 커밋 + Fork 기반 PR |
| **탐색** | `/fz-discover` | 풍경 탐색 + 경로 매핑 (결론 없이 plan에 전달) |
| | `/fz-search` | 코드 탐색 (symbolic + pattern 이중 경로) |
| **검증** | `/fz-codex` | Codex CLI 교차 검증 + `--consensus` 3모델 합의 |
| | `/fz-gemini` | Gemini CLI Devil's Advocate |
| | `/fz-peer-review` | 동료 PR 리뷰 (9개 관점) |
| **문서/시스템** | `/fz-doc`, `/fz-memory`, `/fz-skill`, `/fz-manage` | 문서, 메모리, 스킬 관리, 생태계 점검 |
| **보조** | `/fz-new-file`, `/fz-excalidraw`, `/fz-recording`, `/fz-pr-digest` | 파일 헤더, 다이어그램, 회의록, PR 요약 |

---

## Agents

TEAM 모드에서 Lead가 스폰. **에이전트 간 Peer-to-Peer 직접 통신**으로 협업.

| 도메인 | Primary (Opus 승격) | Supporting (Sonnet) |
|--------|:---:|---|
| **계획** | plan-structure | plan-impact, plan-edge-case, review-arch, review-direction |
| **구현** | impl-correctness | review-arch, impl-quality, review-correctness |
| **리뷰** | review-arch | review-quality, review-counter |
| **탐색** | — | search-symbolic, search-pattern |
| **공통** | — | memory-curator (모든 TEAM 참여) |

### 통신 패턴 (5가지)

| 패턴 | 스킬 | 핵심 |
|------|------|------|
| **Adversarial** | fz-discover | 경로 생성 ↔ 비용/리스크 탐색 |
| **Collaborative** | fz-plan | 6-Agent 병렬 분석 + CC 교차 |
| **Pair Programming** | fz-code | 구현 중 실시간 아키텍처 질문 |
| **Live Review** | fz-review | 다른 렌즈로 동시 분석 + L3 연쇄 |
| **Cross-Verify** | fz-search | symbolic ↔ pattern 교차 검증 |

---

## 검증 게이트

```
계획 전          계획 후           구현 중           구현 후           출하 전
──┼──────────────┼────────────────┼────────────────┼───────────────┼──
  │              │                │                │               │
  direction      stress-test      friction         build           codex
  challenge      Q1-Q6            detect           implication     Reflection
  (방향 도전)     (설계 스트레스)    (마찰 감지)       -scan           Rate ≥80%
                                                   enforcement
                                                   L3 에이전트
```

---

## 파이프라인 (주요)

| 파이프라인 | 트리거 | 체인 |
|-----------|-------|------|
| **quick-fix** | "타임아웃 변경" | fz-fix → build |
| **bug-hunt** | "크래시 버그 찾아줘" | fz-search → fz-fix |
| **plan-to-code** | "계획하고 구현" | fz-plan → fz-code → build |
| **code-to-review** | "구현하고 리뷰" | fz-code → build → fz-review |
| **review-to-ship** | "리뷰하고 커밋" | fz-review → fz-commit |
| **full-cycle** | "처음부터 끝까지" | fz-plan → fz-code → fz-review → fz-commit |
| **discover** | "어떻게 구현할까?" | fz-discover → fz-plan |

전체 19개 파이프라인: `modules/pipelines.md`

---

## 실행 모드

| | SOLO | TEAM |
|---|------|------|
| **판단** | 복잡도 0-3 | 복잡도 4+ |
| **실행** | Lead(Opus) 단독 | Lead(O) + ★Primary(O) + N×Sonnet |
| **통신** | 순차 실행 | 2.5-Turn Peer-to-Peer |
| **검증** | 선택적 | Codex 필수 + Reflection Rate ≥80% |

| 확장 모드 | 트리거 | 설명 |
|----------|-------|------|
| **BATCH** | `--batch` / 독립 3개+ | worktree 격리 병렬 + merge 후 빌드 gate |
| **LOOP** | `--loop` / Gate 반복 | 자동 반복 + 에스컬레이션 래더 |
| **SIMPLIFY** | 함수3+ / 100줄+ / 빌드3실패 | 필수 gate + 설계 의도 보존 |

---

## 품질 보장 체계

| 체계 | 설명 |
|------|------|
| **RTM** | plan→code→review 요구사항 ID 추적 (`modules/rtm.md`) |
| **Implication Scan** | 제거/리팩토링 시 의미론적 완결성 검사 (`modules/lead-reasoning.md`) |
| **System Reminders** | Instruction fade-out 대응 트리거 기반 리마인더 (`modules/system-reminders.md`) |
| **Scope Expansion** | discover 시야 제한 4겹 방어 |
| **L3 에이전트** | silent-failure-hunter + type-design-analyzer review 보강 |
| **Evaluator Tuning** | 피드백 검증 프로토콜 4단계 — 과적합 방지 (preference 학습 금지) |
| **Harness Ablation** | 분기별 Gate 기여도 측정 → 불필요 컴포넌트 식별 |
| **Sycophancy 방어** | Round 1 독립 → Round 2 피드백 → Round 0.5 합의/불합의 |

---

## 메모리 시스템

| 계층 | 저장소 | 용도 |
|------|--------|------|
| **L1** | `~/.claude/projects/*/memory/` | 프로젝트별 교훈, 패턴 |
| **L2** | Serena Memory (`fz:*` 키) | 세션 상태, 체크포인트 |
| **L3** | ASD 폴더 (파일) | 장기 작업 산출물, compact 복원 |

---

## 외부 의존성

**필수**: Claude Code + Serena MCP

**권장**: + Context7 MCP + Codex CLI + SuperClaude

**전체 (iOS)**: + XcodeBuildMCP + GitHub MCP/CLI + Atlassian MCP + SwiftUI Expert + Swift Concurrency + Sequential Thinking + LSP

상세: `guides/` 디렉토리의 각 가이드 참조

---

## Guides

| 가이드 | 설명 |
|--------|------|
| **prompt-optimization.md** | 10대 프롬프트 원칙 + Context Rot 대응 |
| **skill-authoring.md** | 스킬 작성 (YAML, Progressive Disclosure, 500줄 제한) |
| **skill-testing.md** | 3단계 테스트 (Triggering, Functional, Performance) |
| **skill-troubleshooting.md** | 트리거 문제, MCP 에러, TEAM 위반 진단 |
| **agent-team-guide.md** | 에이전트 팀 (2.5-Turn, Task Brief, 모델 전략) |
| **clean-architecture.md** | Dependency Rule, SOLID, Uncle Bob's Decision Rules |
| **harness-engineering.md** | AI 에이전트 하네스 설계 (Anthropic 공식 + NLAH 논문 기반, 1035줄) |

---

## Changelog

**현재 버전: v3.2.1** (2026-04-05) — Dependency Decoupling (로컬 경로/iOS 의존성 제거)

전체 변경 이력: [CHANGELOG.md](CHANGELOG.md)
