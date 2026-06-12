# fz

[![Release](https://img.shields.io/github/v/release/jaewooongyun/fz?label=latest&color=blue)](https://github.com/jaewooongyun/fz/releases/latest) [![License](https://img.shields.io/github/license/jaewooongyun/fz?color=green)](LICENSE) [![Changelog](https://img.shields.io/badge/changelog-md-lightgrey)](CHANGELOG.md)

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 플러그인 — AI 개발 워크플로우 오케스트레이션 시스템.

자연어 요청 → 복잡도 평가 → 스킬 파이프라인 자동 구성 → 네이티브 Workflow 멀티에이전트 오케스트레이션 → 실행.

---

## 설치

### 1. 사전 요구사항

| 도구 | 필수 | 설치 |
|------|:---:|------|
| **Claude Code** | O | `npm install -g @anthropic-ai/claude-code` |
| **Serena MCP** | O | fz 설치 시 자동 등록 (`.mcp.json` 번들 → [oraios/serena](https://github.com/oraios/serena)). 런타임 `uv` 필수: `brew install uv` |
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
├── skills/          20개 — /fz, /fz-plan, /fz-code, /fz-review, /fz-fix, /fz-modernize ...
├── agents/          13개 — plan-structure, impl-correctness, review-arch ...
├── workflows/       5개 — 네이티브 Workflow 결정적 스크립트 (discover-adversarial, plan-collaborative, code-pair ...)
├── modules/         37개 — team-core, pipelines, cross-validation, lead-action-default, codex-strategy, memory-guide, fz-codex-bash-hygiene, fz-codex-subcommands-core/aux, swift-anti-pattern-preblock ...
│   └── patterns/    5개 — adversarial, collaborative, pair-programming ...
├── guides/          7개 — prompt-optimization, skill-authoring, harness-engineering ...
├── codex-skills/    8개 — Codex 네이티브 스킬 + Authority 인용 + Memory Lesson inline (fz-reviewer, fz-architect ...)
├── schemas/         5개 — Codex JSON 응답 스키마 (MAST/LLM-PeerReview/VeriGuard/CoVe 권위 출처)
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

### 멀티에이전트 실행: 네이티브 Workflow (v4.12)

```
Lead (Opus) ─── Workflow({scriptPath}) 호출 + changeset 적용 + 빌드/Gate 실행
    │
    └── workflows/*.js ─── 결정적 스크립트가 stage 오케스트레이션
        agent(agentType: 'fz:plan-structure', schema) → 스키마 강제 JSON 반환
        데이터는 스크립트 경유 (P2P 통신 유실·팀 정리 실패가 구조적으로 불가능)
```

| 스킬 | 스크립트 | 구조 |
|------|---------|------|
| /fz-discover | discover-adversarial.js | lean 5-call / --deep 렌즈 3 fan-out |
| /fz-search --deep | search-cross-verify.js | 심볼/패턴 독립 병렬 → 교차 FP 제거 → 병합 (5-call) |
| /fz-review | review-live.js | arch/quality 병렬 → id-기반 교차 → counter DA (5-call) |
| /fz-plan | plan-collaborative.js | direction 도전 → 초안 → 3렌즈+CC 교차 → 통합 (9-11 call) |
| /fz-code, /fz-fix | code-pair.js | impl changeset(디스크 미수정) → 조건부 검토 → Lead 적용 (1-3 call) |

> TEAM(TeamCreate+SendMessage P2P) 모드는 legacy — calibration 게이트(G1-G3) 통과 후 일몰 예정. 규약: `guides/skill-authoring.md` §12.

### What's New (v4.14.0) — Claude Fable 5 대응 + 전수 주장 오판 방어 [MINOR]

**Part A — Claude Fable 5 대응** (2026-06-09 GA, Opus 상위 tier):
- **모델 가이드 신설**: `guides/fable-model-guide.md` — 사양($10/$50·1M·thinking 상시)/API 동작 차이/Claude Code 통합(effort frontmatter·안전 분류기 자동 폴백·서브에이전트 fable enum)/공식 효율 권고/fz 모델 전략 4-axes + 스니펫 채택 현황. 기존 가이드 5파일 Fable 갱신.
- **effort 적재적소 배선**: fz-plan·fz-review·fz-discover·fz-search frontmatter `effort: xhigh` (capability-sensitive 4스킬 — max/ultracode는 세션 레벨 운용 가이드로). 배선=가설/측정=검증 — `experiment-log.md` §5.8 측정 큐 4항목 사전등록 동반.
- **grounded progress 채택**: Fable 공식 프롬프팅 스니펫 7종 실측 선별(채택 1/보강 1/비채택 5 — 근거 표) — VD Brief 4번 + team-core + workflows 5파일 OVERRIDE "주장은 도구 결과/입력 근거 지목 가능해야".
- **Codex 공백 운용**: 장기 quota 불능 플래그(기간 조건부 ~6/28, 만료 원복 명시) + fresh-context 검증자 분기(fz-review 검증 2 대체 — 본 사이클 3연속 catch 실증, `[fresh-context: claude]` 이종성 상실 태그).
- **synthesis pilot**: search-cross-verify stage3-merge `model: 'fable'` — A/B probe에서 fable이 opus 미발견 결함 1건 추가 발견(우위 관찰). 동시 fable 상한 1개 거버넌스 신설.
- **TEAM 레거시 정리**: Workflow 전환 4스킬의 'TeamCreate 강제' STALE 문구 교정 (행 삭제 0, canonical 출처 보존).

**Part B — 전수 주장 오판(Exhaustive-Claim) 방어**: `rg|head -5` 잘린 출력을 "사용처 2곳뿐"으로 단정(실제 11곳)한 오판이 4턴 생존한 사고의 재발 방지 — light 모드 검증 경계(F1) + Coverage Gate 산출물 타입 트리거·검산식(F2) + T8 리마인더(F3) + 교훈 실패 클래스 키잉(F4). 기존 방어가 전부 존재했으나 light 경로가 전량 우회 — "방어 부재"가 아닌 "방어 우회"가 근본 원인.

> ⛔ Codex cross-model 미수행(quota ~6/28) — Workflow 다각도(plan 9 agents + review 5 agents ×2회, findings 25 전원 반영) + fresh-context 검증 2회 대체, 회복 시 후행 check. 상세: [docs/releases/v4.14.0.md](docs/releases/v4.14.0.md)

### What's New (v4.13.0) — Template Authority Bias 방어 + 구조 결정 옵션 사용자 배선 [MINOR]

- **구조 결정 3축 Quick-Check** (review-direction): 템플릿/형제 미러링 계획이라도 **DI 출처 · 스레드 가정 · public API 모양**은 결정 대상 — 축별 대안 ≥2 + trade-off 의무. ASD-1802에서 외부 리뷰어가 3축 전부 선행 포착한 실패(파이프라인 0건)의 직접 대응.
- **구조 결정 옵션의 사용자 배선** (G1): PROCEED 판정이어도 옵션 테이블이 plan에 포함되고 **사용자 보고 시 표로 제시** — `directionAlternatives` 반환 패스스루 + Gate 0.5/1 체크. "옵션은 기록이 아니라 제시가 목적".
- **미러링 분류 정정** (G3): 미러링으로 신규 화면·컴포넌트 생성은 '단순 수정' 아님 — Direction Challenge 스킵 불가.
- **감지 보강**: E token `MainActor.assumeIsolated`·`nonisolated` + 생명주기 콜백 역방향 트리거(bridge 3택 trade-off 제시 의무, `Task.immediate` iOS 26+) + boolean trap few-shot.
- **fix**: swift-pattern-detection 내장 self-test 자기참조 매칭(상시 실패) anchoring 수정.

> ⛔ Codex cross-model 검증은 할당량 차단(~6/28)으로 미수행 — Claude 다각도(counter 2회 + Review Squad 2회 + 결정론 oracle 전수) 대체, 회복 시 후행 check. 상세: [docs/releases/v4.13.0.md](docs/releases/v4.13.0.md)

### What's New (v4.12.1) — Serena MCP 번들 + 미노출 도구 참조 정리 [PATCH]

- **Serena MCP 자동 번들**: `.mcp.json` 추가 — `claude plugin install fz` 시 serena 자동 등록(수동 `claude mcp add` 불필요). 공식 oraios/serena + `--context claude-code` + `--project-from-cwd`. 런타임 `uv` 필수.
- **미노출 도구 참조 정리**: serena 1.5.4 `claude-code` 컨텍스트 미노출 3종(`search_for_pattern`/`find_file`/`list_dir`) → `Grep`/`Glob`로 전 스킬·에이전트 정리(24파일 60 edit, 0 잔여). 심볼·메모리 도구는 유지 — 핵심 기능 무손상.
- **README prerequisite 교정**: `AbanteAI`→`oraios/serena`(repo 이전), `uv` 런타임 명시.

> 활성화: push/발행 후 `claude plugin update fz` → `/reload-plugins`. 전체 이력: [CHANGELOG.md](CHANGELOG.md) · [Releases](https://github.com/jaewooongyun/fz/releases)

### What's New (v4.12.0) — TEAM → 네이티브 Workflow 전환 (Wave 0-3) [MINOR]

- **멀티에이전트 실행 전면 전환**: TEAM(TeamCreate+SendMessage P2P) 5개 스킬(discover/search/review/plan/code·fix)을 네이티브 Workflow 결정적 스크립트(`workflows/*.js` 5개, 1094줄)로 대체 — 통신 유실·팀 정리 실패 2대 오류 클래스가 구조적으로 제거(전 invoke 0건). 스키마 강제 JSON + null 명시 분기 + fallback 계약(SOLO 폴백).
- **changeset 책임 재배분** (code-pair): 에이전트는 디스크를 수정하지 않고 changeset JSON(exact syntax + oldAnchor)만 반환 — Lead가 검증 후 적용+빌드. 검증 안 된 Edit이 디스크에 닿지 않는 구조.
- **표준 패턴 3종 문서화** (skill-authoring §12 신설): OVERRIDE 블록(P2P·컨텍스트 로딩 무효화) / args 방어 파싱(scriptPath 호출 시 JSON 문자열 도착 — 실측) / agentType `fz:` namespace 필수.
- **calibration 게이트 사전 등록** (experiment-log §5.7): 스킬별 임계 + G1(패턴별)/G2(품질)/G3(일몰) — TEAM 모듈 일몰(Wave 4)은 게이트 통과 후.

> ⛔ Codex cross-model 검증은 할당량 부재로 미수행 (다각도 Claude 리뷰 대체) — 회복 시 후행 check 예정. 전체 변경 이력: [CHANGELOG.md](CHANGELOG.md) · [Releases](https://github.com/jaewooongyun/fz/releases)

### 근거 연구

fz 가이드(`guides/*.md`)와 스킬이 인용하는 외부 권위 자료입니다. 가이드 본문에 더 자세한 출처 표가 있습니다 — 특히 `guides/harness-engineering.md` §References, `guides/prompt-optimization.md` Tier 1/2.

#### Anthropic 공식

| 출처 | 발표 | fz 적용 |
|------|:---:|------|
| [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) | 2024 | agent-team-guide.md / Codex 네이티브 스킬 권위 베이스 |
| [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 2025-11 | harness-engineering.md Pattern A (Initializer + Coding Agent) |
| [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) | 2025-06 | "Token 80% performance variance" → harness-engineering.md 우선순위 로딩 |
| [Anthropic 32p Skills Guide](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/skill-best-practices) | 2026-01 | skill-authoring.md / skill-testing.md 3단계 테스트 + Under/Over-triggering |
| [Claude 4 Best Practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/claude-4-best-practices) | 2026-02 | prompt-optimization.md §3 과격 지시어 가드 |
| [Harness Design for Long-Running Apps](https://www.anthropic.com/engineering/harness-design-long-running-apps) | 2026-03 | "self-evaluation unreliable" → cross-validation 근거 / Planner-Generator-Evaluator |
| [Scaling Managed Agents](https://www.anthropic.com/engineering/managed-agents) | 2026-04 | Brain/Hands/Session 분리 → context-artifacts.md emitEvent API contract |
| [Introducing Claude Opus 4.8](https://www.anthropic.com/news/claude-opus-4-8) | 2026-05-28 | effort 기본 high + 자기결함 ~4x↓ + tool 효율↑ + 수백 parallel subagents → 가이드 4.8 갱신 |
| [Introducing Claude Fable 5 & Mythos 5](https://platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5) + [Prompting Claude Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5) | 2026-06-09 | Opus 상위 tier·thinking 상시·de-prescription·fresh-context verifier → fable-model-guide.md 신설 + effort/grounded progress 배선 |
| [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 2026 | prompt-optimization.md context 전략 (load-bearing skill of 2026) |
| [Best Practices for Claude Code](https://www.anthropic.com/engineering/claude-code-best-practices) | 2026 | Subagent isolation / filesystem > compaction |

#### OpenAI 공식

| 출처 | 발표 | fz 적용 |
|------|:---:|------|
| [GPT-5 Prompting Guide (Cookbook)](https://cookbook.openai.com/examples/gpt-5/gpt-5_prompting_guide) | 2026 | fz-codex preamble 표준 ("Rephrase → Outline → Narrate") |
| [Introducing GPT-5.5](https://openai.com/index/introducing-gpt-5-5/) + [System Card](https://openai.com/index/gpt-5-5-system-card/) | 2026-04-23 | "literal and thorough manner" → Codex 인용 가드 |
| [Codex CLI Changelog 0.124.0](https://developers.openai.com/codex/changelog) | 2026-04-23 | fz-codex Hybrid Routing + Auto Review Agent + GPT-5.5 통합 |

#### Academic (peer-reviewed / arXiv)

| 출처 | 적용 |
|------|------|
| **NLAH** (Pan et al., Tsinghua/HIT) — [arXiv 2603.25723](https://arxiv.org/abs/2603.25723) | harness-engineering.md C/R/S/A/Σ/F formalism |
| **MAST** (NeurIPS 2025) — [arXiv 2503.13657](https://arxiv.org/abs/2503.13657) | 14 failure modes + FM-2.2 "Fail to ask" 6.8% → lead-action-default.md |
| **GEPA** (Stanford+UCB, ICLR 2026 Oral) — [arXiv 2507.19457](https://arxiv.org/abs/2507.19457) | Reflective prompt evolution (MIPROv2 +10% AIME) → fz-skill optimize |
| **ACE: Agentic Context Engineering v3** (Stanford, ICLR 2026) — [arXiv 2510.04618](https://arxiv.org/abs/2510.04618) | context collapse / brevity bias → context-artifacts.md |
| **CONSENSAGENT** (ACL 2025) | 동적 prompt refinement → sycophancy 런타임 완화 |
| **X-MAS** — [arXiv 2505.16997](https://arxiv.org/abs/2505.16997) | 이종 모델 조합 (MATH +8.4%, AIME +47%) → cross-validation 정량 근거 |
| **VeriGuard** — [arXiv 2510.05156](https://arxiv.org/abs/2510.05156) | dual-stage verification → fz cross-validation + codex_verification_schema |
| **Chain-of-Verification (CoVe)** — [arXiv 2309.11495](https://arxiv.org/abs/2309.11495) | fz-fixer / codex_verification_schema 근거 |
| **MAR** — [arXiv 2512.20845](https://arxiv.org/abs/2512.20845) | 3중 검증 역할 분리 이론 |
| **Drift No More** — [arXiv 2510.07777](https://arxiv.org/abs/2510.07777) | system-reminders 근거 |
| **AgentFlow** — [arXiv 2604.20801](https://arxiv.org/abs/2604.20801) | typed graph DSL → harness-engineering.md / fz-planner |
| **Inside the Scaffold** — [arXiv 2604.03515](https://arxiv.org/abs/2604.03515) | 13개 coding agent 분석 → 5 loop primitives |
| **IFScale** — [arXiv 2507.11538](https://arxiv.org/abs/2507.11538) | 규칙 수 증가 시 정확도 저하 (500규칙→68%) → skill-authoring 슬림화 |
| **Multi-Agent Collaboration Survey** — [arXiv 2501.06322](https://arxiv.org/abs/2501.06322) | peer/centralized/distributed 분류 → TEAM P2P 패턴 분류 |
| **OpenDev: AI Coding Agents for the Terminal** — [arXiv 2603.05344](https://arxiv.org/abs/2603.05344) | terminal harness 참고 |
| **1M context "safety net not strategy"** — [arXiv 2601.15300](https://arxiv.org/abs/2601.15300) + [2510.05381](https://arxiv.org/abs/2510.05381) | filesystem > compaction 근거 |
| **DSPy** (Khattab et al., Stanford NLP) — [dspy.ai](https://dspy.ai/) | optimizer 베이스 (BootstrapFewShot / MIPROv2 / GEPA) |

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
| **검증** | `/fz-codex` | Codex CLI 교차 검증 (GPT-5.5) + `micro-eval` 단일 주장 재평가 |
| | `/fz-peer-review` | 동료 PR 리뷰 (9개 관점 + caller/convention 검증) |
| **문서/시스템** | `/fz-memory`, `/fz-skill`, `/fz-manage`, `/fz-modernize` | 메모리, 스킬 관리 (`write` 서브커맨드 = 문서 작성 + 글쓰기 + 프롬프트 최적화), 가이드 modernization |
| **보조** | `/fz-new-file`, `/fz-recording`, `/fz-pr-digest` | 파일 헤더, 회의록, PR 요약 |

---

## Agents

Workflow 스크립트가 `agentType: 'fz:{name}'`으로 재사용하는 **렌즈 정의** (v4.12). TEAM P2P 스폰은 legacy.

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
| **skill-authoring.md** | 스킬 작성법 (YAML, Progressive Disclosure, 500줄 제한, §12 Workflow 오케스트레이션) |
| **agent-team-guide.md** | 에이전트 팀 (2.5-Turn, Task Brief, 모델 전략) |
| **clean-architecture.md** | Dependency Rule, SOLID |
| **harness-engineering.md** | AI 에이전트 하네스 설계 + NLAH Gap 분석 (1046줄) |

---

> 버전 및 변경 이력은 상단 배지의 Release / Changelog 링크 참조.
