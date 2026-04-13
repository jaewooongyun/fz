# fz

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
├── modules/         22개 — team-core, pipelines, cross-validation, code-transform-validation, uncertainty-verification ...
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
| | `/fz-review` | 3중 검증 (Claude + Codex + sc:analyze) |
| | `/fz-commit`, `/fz-pr` | 커밋 + Fork 기반 PR |
| **탐색** | `/fz-discover` | 풍경 탐색 + 경로 매핑 |
| | `/fz-search` | 코드 탐색 (symbolic + pattern) |
| **검증** | `/fz-codex` | Codex CLI 교차 검증 (GPT-5.4) |
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

## Changelog

**현재 버전: v3.9.0** (2026-04-14)

- v3.9.0 — Harness Engineering Enhancement (SOLO G≠E 결정론적 검증 + PR 코멘트 파이프라인 + NLAH Gap 분석)
- v3.8.0 — Uncertainty-Aware Harness (Default-Deny 검증 + Zero-Exception Thread + Harness Metrics)
- v3.7.0 — Code Transformation Validation (코드 변환 동등성 검증 — 3중 검증축 추가)
- v3.6.0 — iOS/Swift 역방향 진단 트리거 + Concurrency Safety Audit (PR #3665 교훈 반영)
- v3.5.0 — Peer Review false positive 감소 (Gather Verification Gate + Quality Gate)
- v3.4.0 — Peer Review 호출 구조 분석 + Convention 검증 (PR #3646 교훈 반영)
- v3.3.2 — 플러그인 중심으로 README 전면 개편
- v3.3.0 — Claude Code 플러그인 전환

전체 변경 이력: [CHANGELOG.md](CHANGELOG.md)
