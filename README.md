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
| /fz-peer-review | peer-review.js | arch/quality/correctness 3-병렬 → (deep) 교차 + counter DA (3 or 6-call) |

> TEAM(TeamCreate+SendMessage P2P) 모드는 v4.22.0에서 **일몰 완료** — 실제 TeamCreate 호출부 0건. `patterns/*.md`는 canonical 라운드 의미론으로 보존. 규약: `guides/skill-authoring.md` §12.

### What's New (v4.23.0) — 누적 통합: 계약 lint 결정화 · 리뷰 구조 판정 축 · llm-references §1.1b [MINOR]

v4.22.0 이후 누적된 23커밋(**138자산 전수 자기 감사** 기반)을 하나로 발행. 초안 번호 4.23.0~4.25.0은 태그·Release 어디에도 없어 폐기하고 v4.23.0으로 통합했다(구간 `[MAJOR]` 0건 → semver 정합).

- ⭐ **`scripts/lint_contracts.py` 신설 — `/fz-manage check` 17항목의 결정화**: 항목이 **전부 언어 지시**였고 check용 스크립트가 0개였다 → 정의된 검사(깨진 참조·모듈 목차)가 있는데도 위반이 생존했다. 현재 **24항목**(DETERMINISTIC 15 / THRESHOLD 3 / SEMANTIC 6, ⛔ 손으로 세지 말고 `--list` 전사). 첫 실행 129건 → 탐지기 교정 4회 → 위반 0건
- ⭐ **계측기가 자기 유효성을 증명한다 — 양성 대조 하네스**: `hits`는 *본 후보 수*라 패턴이 고장나도 0이 아니다 → "위반 0건 exit 0"이 깨끗함의 증거가 아니었다. fixture **46건 + 통합 5검사(9 위치)** 가 매 실행 선행하고, 실패는 **exit 2(configuration error)** 로 분리된다(PASS·SKIP 아님). 의도적 회귀 5종(무조건 `[]`·판정 반전·확장자 오필터·디렉토리 오제외·그럴듯한 가짜 히트) 전부 exit 2로 검출
- **inert frontmatter 3종 51선언 제거**: `team-agents`(9)·`composable`(21)·`model-strategy`(21) — 전부 **런타임 효과 0**인 fz 자작 필드였고 형제 간 불일치가 stale 위험을 실증했다. 실효 결정자(`workflows/*.js` / `provides`·`needs`)를 `governance.md §Truth-of-Source`에 **4항목 정본 지정**
- ⭐ **`cross-validation.md` §Negative-Result Gate 신설**: 신규 규칙이 아니라 **수신처에 구현이 없던 위임**을 채운 것. positive control · 신호 보존(`>/dev/null` 금지) · 귀속 라벨. 근거는 단일 세션 **12 인스턴스** 실측 — 그중 *0건 자체를 의심해서* 잡은 건 **0건**
- ⭐ **리뷰의 구조 판정 축 신설**(`review-structural-axes.md`, peer-review ↔ fz-review 공유): 리뷰가 결함은 잘 찾고 **더 나은 구조는 못 찾던** 문제. **통제 A/B**(스키마·cap·에이전트·모델 고정, 브리프만 교체)에서 1콜이 대안 9/10 · 기존 3-렌즈 24건 미포착 **신규 6건** · 삭제가능 95줄을 냈다 — 능력이 아니라 **하네스가 묻지 않았다**
- **실패 복구 사다리 L1~L4 정본화**(`skill-authoring.md` §12): 5개 스킬이 `fallback` 절차로 679줄을 지목했으나 내용은 **부재 도구**(`TeamCreate`·`SendMessage`) 기반이었다 — 가장 필요한 순간의 지침이 실행 불가. 실측(실패 2회 전부 재invoke·resume으로 복구, `team-core` 사용 0건)이 처방을 바꿨다. 동반: `impl-correctness`에서 **쓰기 7종 제거**(프롬프트 금지만이 방어였던 것 → 시도 자체 불가)
- **codex 호출 정본 경로 신설**(`scripts/codex-exec.sh`): 사전 게이트 8종 + **사후 게이트**(exit≠0 → 12 / 빈 출력 → 13 / JSON 실패 → 14). ⛔ 10~14는 전부 **측정 실패**이며 "이슈 0건"이 아니다 — 래퍼 마지막 문장의 exit이 codex exit 2를 0으로 보고한 실측 실패가 신설을 유발했다
- 상세: [docs/releases/v4.23.0.md](docs/releases/v4.23.0.md)

> ⛔ **4라운드 자기 감사 → `NOT CONVERGING` 판정 → 감산 전환**: 교차검증이 R1=15(critical 3) → R2=15(**11건이 R1 수정에서 발생**) → R3=14 → R4=10으로 줄지 않았고, 외부 판정이 원인을 *"독자 부분 해석기의 반응적 확장 + 같은 가정에서 파생된 self-test"* 로 지목했다. 그래서 패치를 멈추고 **삭제·비일반화**했다 — 검사 1개 삭제 · 출력 검증기 전면 재작성(실측: 스키마가 `$ref` **0건**·`pattern` **7건**인데 가장 어려운 `$ref` 해소를 자작하고 있었다) · `ast` 일반 분석 → 줄 화이트리스트. **순감 −132줄**로 예산 초과를 되돌렸다.
>
> ⛔ **기계 검사 사각지대 (다음 사이클)**: CHANGELOG의 **레지스트리 항목 카운트**는 어떤 lint도 보지 않는다(`#N2`는 디렉토리 *파일 수*만). 이번 사이클에 두 번 stale했다 — 항목 추가·삭제 시 `--list` 수동 전사 의무. 검증 라운드 직전에 새 표면을 만들지 않기 위해 신설을 보류했다.

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
| | `/fz-rebase` | 리베이스 조용한 유실 게이트 (경로 단위 배타 분할 + prepush 원격 실측) |
| **탐색** | `/fz-discover` | 풍경 탐색 + 경로 매핑 |
| | `/fz-search` | 코드 탐색 (symbolic + pattern) |
| **검증** | `/fz-codex` | Codex CLI 교차 검증 (모델은 `config.toml` SSOT 위임 = 항상 최신 frontier) + `micro-eval` 단일 주장 재평가 |
| | `/fz-peer-review` | 동료 PR 리뷰 (9개 관점 + caller/convention 검증) |
| **문서/시스템** | `/fz-memory`, `/fz-skill`, `/fz-manage`, `/fz-modernize` | 메모리, 스킬 관리 (`write` 서브커맨드 = 문서 작성 + 글쓰기 + 프롬프트 최적화), 가이드 modernization |
| **보조** | `/fz-new-file`, `/fz-recording`, `/fz-pr-digest` | 파일 헤더, 회의록, PR 요약 |

---

## Agents

Workflow 스크립트가 `agentType: 'fz:{name}'`으로 재사용하는 **렌즈 정의** (v4.12). TEAM P2P 스폰은 v4.22.0에서 일몰 완료.

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
