# fz

[![Release](https://img.shields.io/github/v/release/jaewooongyun/fz?label=latest&color=blue)](https://github.com/jaewooongyun/fz/releases/latest) [![License](https://img.shields.io/github/license/jaewooongyun/fz?color=green)](LICENSE) [![Changelog](https://img.shields.io/badge/changelog-md-lightgrey)](CHANGELOG.md)

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 플러그인 — AI 개발 워크플로우 오케스트레이션 시스템.

자연어 요청 → 복잡도 평가 → 스킬 파이프라인 자동 구성 → 멀티 에이전트 팀 편성 → 실행.

---

## 설치

### 1. 사전 요구사항

| 도구 | 필수 | 설치 |
|------|:---:|------|
| **Claude Code** | O | `npm install -g @anthropic-ai/claude-code` |
| **Serena MCP** | O | [GitHub](https://github.com/AbanteAI/serena) — settings.json에 MCP 등록 |
| Context7 | 권장 | [GitHub](https://github.com/upstash/context7) — 라이브러리 문서 조회 |
| Codex CLI | 권장 | `npm install -g @openai/codex` — GPT 교차 검증 |
| SuperClaude | 선택 | [GitHub](https://github.com/JeongJaeSoon/superclaude) — sc: 명령어 |

프로젝트별 추가:
- **iOS**: XcodeBuildMCP, SwiftUI Expert 플러그인, Swift Concurrency 플러그인
- **Web**: 기본 구성으로 충분

### 2. fz 플러그인 설치

```bash
# 마켓플레이스 등록 (최초 1회)
claude plugin marketplace add jaewooongyun/fz

# 플러그인 설치
claude plugin install fz
```

### 3. 설치 확인

```bash
claude
> /fz "안녕"   # → fz 오케스트레이터가 응답하면 정상
```

### 4. 프로젝트 CLAUDE.md 설정

프로젝트 루트에 `CLAUDE.md`를 작성합니다. fz의 모든 스킬/에이전트가 이 파일을 참조합니다.

필수 섹션: `## Architecture`, `## Build`, `## Code Conventions`
선택 섹션: `## Git Workflow`, `## Plugins`, `## External Models`

> 템플릿: `templates/CLAUDE.md.template` 참조

### 5. Codex 네이티브 스킬 (선택 — Codex CLI 사용 시)

```bash
bash ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/setup-codex-skills.sh
```

---

## 업데이트

```bash
claude plugin update fz@fz-orchestrator
```

> 업데이트가 안 되면 마켓플레이스 캐시를 갱신:
> ```bash
> claude plugin marketplace remove fz-orchestrator
> claude plugin marketplace add jaewooongyun/fz
> claude plugin install fz
> ```

---

## 개발 (fz 자체를 수정할 때)

```bash
# 소스코드 클론
git clone https://github.com/jaewooongyun/fz.git ~/dev/fz-plugin

# 로컬 개발 모드로 실행 (수정 즉시 반영)
claude --plugin-dir ~/dev/fz-plugin

# alias 설정 (선택)
echo 'alias cfz="claude --plugin-dir ~/dev/fz-plugin"' >> ~/.zshrc
```

### 릴리즈

1. `plugin.json` + `marketplace.json` **version bump** (필수)
2. `git commit` + `git push`
3. `git tag vX.Y.Z` + `git push --tags`

> version bump 누락 시 `plugin update`가 "already at latest"로 스킵됨.

---

## 사용법

### /fz 오케스트레이터 (자연어 → 자동 파이프라인)

```bash
/fz "버그 찾아서 고쳐줘"              # bug-hunt → fz-search → fz-fix
/fz "새 기능 계획하고 구현해줘" --team  # plan-to-code (TEAM 모드)
/fz "코드 리뷰하고 커밋해줘"           # review-to-ship
/fz "이걸 어떻게 구현하면 좋을까?"      # discover → 풍경 탐색
```

### 개별 스킬 직접 실행

```bash
/fz-plan "로그인 기능 설계해줘"        # 계획만 수립
/fz-code "계획대로 구현해줘"           # 구현만 실행
/fz-review "내 코드 리뷰해줘"          # 3중 검증 리뷰
/fz-fix "이 크래시 고쳐줘"             # 버그 수정
/fz-search "UserRepository 찾아줘"    # 코드 탐색
/fz-codex review                      # GPT 교차 검증
```

### 옵션

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
fz-plugin/
├── .claude-plugin/  plugin.json + marketplace.json
├── skills/          21개 — /fz, /fz-plan, /fz-code, /fz-review, /fz-fix ...
├── agents/          13개 — plan-structure, impl-correctness, review-arch ...
├── modules/         25개 — team-core, pipelines, cross-validation, lead-action-default, memory-guide, sprint-contract, swift-anti-pattern-preblock, swift-pattern-detection ...
│   └── patterns/    5개 — adversarial, collaborative, pair-programming ...
├── guides/          7개 — prompt-optimization, skill-authoring ...
├── codex-skills/    8개 — Codex 네이티브 스킬 (fz-reviewer, fz-architect ...)
├── schemas/         5개 — Codex JSON 응답 스키마
├── scripts/         setup-codex-skills.sh
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
    └── External: Codex(GPT-5.5)
```

### Verification Discipline 4-way Chain (v4.0+)

**추정을 사실로 단정 금지** 원칙이 생태계 전체에 4-way 체인으로 구조화됨. v4.0에서 단일 선형 체인을 4개 독립 체인으로 재설계 + 템플릿 레이어 자동 상속으로 재발 방지 메커니즘 확보.

```
답변 생성 시
    ↓
Fail-Closed 키워드 가드 (T6/T7 트리거 — modules/team-core.md TEAM boot 자동 주입)
    ├── 과거 상태 키워드 ("원본은", "이전은") 감지
    │   → 직전 5턴 검증 도구 호출 흔적 없으면 [미검증] 자동 태그
    │
    └── 아티팩트 인용 (follow-up-tasks.md 등) 감지
        → 현재 시점 재실측 강제 또는 [아카이브] 태그
    ↓
Lead Reasoning §1.5 Fallacy 체크
    ├── Partial-to-Whole (부분→전체)
    ├── Contingent-to-Inherent (현재→본질)
    ├── Operation Classification (연산 분류)
    └── Speculation-to-Fact (추정→사실)
    ↓
fz-codex micro-eval 서브커맨드 (단일 주장 독립 재평가)
    → verdict: agree | disagree | partial | needs_verification
    → needs_verification ⇔ uncertainty-verification.md Default-Deny (의미론적 결합, v4.0)
    ↓
fz-review Phase 4.5 B3 체크리스트 + experiment-log.md §5.4 canonical sink (v4.0)
    → 5개 지표 자동 수집 → 누적 → B1/B2 진입 판정
```

### V.D. 4-way Chain (v4.0 아키텍처)

```
① 기본 fail-closed:  uncertainty-verification → fz-plan / fz-code
② 보조 micro-eval:   fz-codex micro-eval → needs_verification → Default-Deny 차단
③ TEAM 주입:         system-reminders → team-core → fz/SKILL.md Task Brief → agents (templates/ 상속)
④ 운영 피드백:       Phase 4.5 측정 → experiment-log.md §5.4 canonical sink → B1/B2 판정
```

### Lead Action Default Principle (v4.3 통합)

```
Lead default = action with proportional verification
```

31차/32차/33차 메타 교훈을 단일 원칙으로 통합. **verify는 명시적 risk signal에서만**.

| Manifestation | Trigger | Action |
|---------------|---------|--------|
| 31차 (Plan-before-Probe) | primitive 의존 가정 | constraint probe 선행 |
| 32차 (Probe Coverage) | enumeration 누락 | 3-axes sub-checklist |
| 33차 (Recommendation Default) | implementation-ready | default = implementation |

상세: `modules/lead-action-default.md` (≤30 lines thin reference) + `modules/memory-guide.md` § Lesson Intake Decision Tree.

### Sprint Contract Pattern (T2-B, v4.3)

cross-skill + 5+ Step plan 시 발동: **Codex가 success criteria를 사전 commit → Lead가 plan 작성** → Codex verify. Self-preference bias 우회 + Generator≠Evaluator 시간 분리.

상세: `modules/sprint-contract.md` + `fz-plan` Phase 0.7.

### Swift/iOS Quality Framework — 3-Layer Evidence (v4.5)

Plan/Code/Review 각 단계에서 Claude + Codex가 **evidence-based clear Swift/iOS coding**을 수행하도록 fz framework에 3-Layer Evidence 정합 통합. plan-structure agent + Phase 1.5 (Plan) + Phase 0.5 (Code) + Swift/iOS Domain Tier (Meta) 4축 강화.

```
Layer 1 PLAN   ─── plan-structure Swift Awareness + Phase 1.5 (Anti-Pattern Pre-block) + iOS 16 명시
Layer 2 CODE   ─── impl-quality context7 + Phase 0.5 (Pattern Pre-detection) + Codex Repair Checklist
Layer 3 REVIEW ─── fz-fix supporting (impl-quality + review-quality) + 역방향 트리거 + drift routing fix
Meta           ─── Swift/iOS Domain Tier (additive layer) + §5.6 Plugin Trigger Activation + Load-bearing 절차
```

- `modules/swift-anti-pattern-preblock.md` (신규) — 3 원칙 (P1/P2/P3) + token + Few-shot
- `modules/swift-pattern-detection.md` (신규) — 4 원칙 (D/E/F/G) + Phase 1.5 P3 ↔ G mirror
- `modules/uncertainty-verification.md` Swift/iOS Domain Tier — 7개 주장 유형 × Heavy/Light × Mandatory Sources (additive, non-overriding 일반 Heavy 정책)
- `experiment-log.md` §5.6 — Plugin trigger activation 측정 schema + 원칙별 ablation 절차

5-cycle Cross-Validation (Claude + Codex GPT-5.5): Codex unique 16 + Claude deep-review unique 5 → Reflection Rate 90% (strict) / 95% (lenient).

### Mapping Layer SPOF Defense (v4.4)

refactoring PR의 evidence 매핑이 ground truth와 atom-level 동등인지 검증. 6-Layer LLM 검증이 같은 매핑 base를 공유하면 매핑 오류는 layer 수와 무관하게 통과 — **Mapping Layer Single-Point-of-Failure** 방어. 검증 신뢰도 = `min(매핑 정확성, layer 정확성)` (multiplicative 아님).

- `evidence/semantic-mapping.md` — atom-level mapping table + `[verified: source]` 의무 (`OldAPI → NewAPI` 한 줄 매핑 금지)
- **Gate 4.4-A Mapping Fidelity Gate** — refactoring PR + artifact 부재 → fail-closed Critical / `mapping_status=lossy` → auto-include
- Default-Deny 좁은 확장 — peer-review mapping/equivalence claim에 한정 (전역 확대 X)
- Layer Diversity 통합 — deterministic source(`git show / Read / grep`) + LLM 판단 조합

상세: `modules/peer-review-gates.md` Gate 4.4-A + `modules/evidence-collection.md` a2. Semantic Mapping Ground Truth.

**재발 방지 메커니즘 (v4.0)**:
- `templates/agent-template.md` + `templates/skill-template.md`에 `## Verification` 섹션 자동 상속
- `templates/skill-template.md`의 `## If TeamCreate is used` 조건부 체크리스트로 env flag 누락 차단
- `modules/team-core.md` TEAM 생성 절차에 T6/T7 트리거 주입 명시
- TeamCreate 사용 9 skills (fz, fz-plan, fz-code, fz-discover, fz-fix, fz-review, fz-peer-review, fz-search, fz-pr-digest) 모두 `## Prerequisites` 섹션 필수

### 근거 연구 (v4.0 공식 인용)

| 출처 | 적용 |
|------|------|
| Anthropic: Harness Design for Long-Running Applications (2026-03) | harness-engineering.md 원칙 2-3 |
| Anthropic: Scaling Managed Agents (2026-04) | §1.3 infrastructure vs application 레이어 구분 |
| arxiv 2603.25723 NLAH | C, R, S, A, Σ, F formalism |
| arxiv 2505.16997 X-MAS | 이종 모델 조합 (MATH +8.4%, AIME +47%) |
| arxiv 2510.07777 Drift No More | system-reminders 근거 |
| arxiv 2510.05156 VeriGuard | dual-stage verification (fz cross-validation) |
| arxiv 2512.20845 MAR | 3중 검증 역할 분리 이론 |
| arxiv 2601.15300 + 2510.05381 | 1M context "safety net not strategy" |

---

## Skills

| 카테고리 | 스킬 | 설명 |
|---------|------|------|
| **오케스트레이터** | `/fz` | 자연어 → 파이프라인 자동 구성 |
| **개발** | `/fz-plan` | 요구사항 분석 + 영향 범위 + RTM |
| | `/fz-code` | 계획 기반 점진적 구현 + 빌드 검증 |
| | `/fz-fix` | 버그 수정 (4-Phase 디버깅) |
| | `/fz-review` | 3중 검증 (Claude + Codex + sc:analyze) |
| | `/fz-commit`, `/fz-pr` | 커밋 + Fork 기반 PR |
| **탐색** | `/fz-discover` | 풍경 탐색 + 경로 매핑 |
| | `/fz-search` | 코드 탐색 (symbolic + pattern) |
| **검증** | `/fz-codex` | Codex CLI 교차 검증 (GPT-5.5) + `micro-eval` 단일 주장 재평가 (needs_verification ⇔ Default-Deny 결합, v4.0) |
| | `/fz-peer-review` | 동료 PR 리뷰 (9개 관점 + caller/convention 검증) |
| **문서/시스템** | `/fz-doc`, `/fz-memory`, `/fz-skill`, `/fz-manage` | 문서, 메모리, 스킬 관리 |
| **보조** | `/fz-new-file`, `/fz-excalidraw`, `/fz-recording`, `/fz-pr-digest` | 파일 헤더, 다이어그램, 회의록, PR 요약 |

---

## Agents

TEAM 모드에서 Lead가 스폰. **에이전트 간 Peer-to-Peer 직접 통신**으로 협업.

| 도메인 | Primary (Opus) | Supporting (Sonnet) |
|--------|:---:|---|
| **계획** | plan-structure | plan-impact, plan-edge-case, review-arch, review-direction |
| **구현** | impl-correctness | review-arch, impl-quality, review-correctness |
| **리뷰** | review-arch | review-quality, review-correctness, review-counter |
| **탐색** | — | search-symbolic, search-pattern |
| **공통** | — | memory-curator (모든 TEAM 참여) |

---

## Pipelines (주요)

| 파이프라인 | 트리거 | 체인 |
|-----------|-------|------|
| **quick-fix** | "타임아웃 변경" | fz-fix → build |
| **bug-hunt** | "크래시 버그 찾아줘" | fz-search → fz-fix |
| **plan-to-code** | "계획하고 구현" | fz-plan → fz-code → build |
| **code-to-review** | "구현하고 리뷰" | fz-code → build → fz-review |
| **review-to-ship** | "리뷰하고 커밋" | fz-review → fz-commit |
| **full-cycle** | "처음부터 끝까지" | fz-plan → fz-code → fz-review → fz-commit |

전체 19개: `modules/pipelines.md`

---

## Guides

| 가이드 | 설명 |
|--------|------|
| **prompt-optimization.md** | 10대 프롬프트 원칙 + Context Rot 대응 |
| **skill-authoring.md** | 스킬 작성법 (YAML, Progressive Disclosure, 500줄 제한) |
| **agent-team-guide.md** | 에이전트 팀 (2.5-Turn, Task Brief, 모델 전략) |
| **clean-architecture.md** | Dependency Rule, SOLID |
| **harness-engineering.md** | AI 에이전트 하네스 설계 + NLAH Gap 분석 (1046줄) |

---

> 버전 및 변경 이력은 상단 배지의 Release / Changelog 링크 참조.
