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
Lead (Fable 5) ─── Workflow({scriptPath}) 호출 + changeset 적용 + 빌드/Gate 실행
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

### What's New (v4.19.0 ~ v4.21.0) — 하네스 서베이 2026 반영 (Wave A/B/C) [MINOR ×3]

외부 서베이 "Harness Engineering 2026"(arXiv 86편 메타분석)을 3층 검증(추출 인용 81건 환각 0 · fz사실 45/47 · Codex 교차)으로 분석 → 개선 13주제 → 3-Wave 실행. 전 편집 add-only(삭제 0), 서베이 인용은 `[외부: … 원 논문 미대조]` + census 단서 의무. 생산=opus Workflow, Lead(fable)=적용·게이트.

- **v4.19.0 Wave A — 가이드 개정**: `harness-engineering.md` 18편집 (§5.5 자기진화+회귀 게이트 신설 · 서브시스템7 Constraint Pinning·Governance Decay · 결정론적 안전 강제 원칙 · §8/§10 멀티에이전트 역방향 게이트 C_min · §2.2 정량 앵커 최신화 · §12 6책임 격자+하네스 홀 외부근거 표 · 참고문헌 2606 wave 21편) + skill-authoring 전이성 원칙 + governance T8. 상세: [docs/releases/v4.19.0.md](docs/releases/v4.19.0.md)
- **v4.20.0 Wave B — 메커니즘/모듈 정합 + Governance Decay 실측**: B1 실측 gate(워커 OVERRIDE 경로 ⛔ 규칙 유실 **unpinned 2/2 위반 → pinned 0/2**, 서베이 2606.22528 재현) → OVERRIDE 6워크플로 거버넌스 방어 · 승격 임계 canonical 통일(`active:≥3`→5세션 promotion-ledger, 잔존 0) · memory-guide GC 망각축 · hygiene §7(clap `--`). 상세: [docs/releases/v4.20.0.md](docs/releases/v4.20.0.md)
- **v4.21.0 Wave C — code-pair pre-flight 크기 가드 (하네스 홀 H5)**: 과거 실사고(~800줄 changeset → StructuredOutput 재시도 소진·27분·206K 토큰) 재발 방지. C1 캘리브레이션(임계 SPLIT_THRESHOLD=600 provisional — 하한 500 실측) → pre-flight `split_required`(하드 차단 아닌 Lead 판단 요구) + 소비처 4곳. **하네스 홀 H1~H5/F5/F6 중 유일 미구현이던 H5 조치 완료**. 상세: [docs/releases/v4.21.0.md](docs/releases/v4.21.0.md)

> ✅ 자체리뷰(fz-review 2축: Claude 4렌즈 + Codex 이종): positive 11·critical 0·major 4(→confirmed 2+하향 2). 확정 결함(C1 "확정"→provisional 과대표현 정정, 헤더 계약 갭)은 dismiss 없이 수정(`591775a`). self-review blind spot을 이종 검증이 메운 사례.
> ⛔ Deferred: C1 다축 캘리브레이션(실패 경계·다파일 조합)은 관측 실패에서 재조정 · Fable C안 확산 · Wave 4 TEAM 일몰은 [Unreleased] 존치.

> 📦 이전 릴리즈 노트: [docs/releases/](docs/releases/) · 전체 변경 이력 [CHANGELOG.md](CHANGELOG.md)

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
| **llm-references.md** | LLM·AI 권위 자료 단일 참조점 (Tier1 공식 / Tier2 arxiv 16 실증 / Tier3 커뮤니티) — 가이드·스킬 개선 1차 출처 |
| **prompt-optimization.md** | 10대 프롬프트 원칙 + Context Rot 대응 |
| **skill-authoring.md** | 스킬 작성법 (YAML, Progressive Disclosure, 500줄 제한, §12 Workflow 오케스트레이션) |
| **agent-team-guide.md** | 에이전트 팀 (2.5-Turn, Task Brief, 모델 전략) |
| **clean-architecture.md** | Dependency Rule, SOLID |
| **harness-engineering.md** | AI 에이전트 하네스 설계 + NLAH Gap 분석 (1046줄) |

---

> 버전 및 변경 이력은 상단 배지의 Release / Changelog 링크 참조.
