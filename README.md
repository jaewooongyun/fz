# fz

[![Release](https://img.shields.io/github/v/release/jaewooongyun/fz?label=latest&color=blue)](https://github.com/jaewooongyun/fz/releases/latest) [![License](https://img.shields.io/github/license/jaewooongyun/fz?color=green)](LICENSE) [![Changelog](https://img.shields.io/badge/changelog-md-lightgrey)](CHANGELOG.md)

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 플러그인 — AI 개발 워크플로우 오케스트레이션 시스템.

자연어로 요청하면 복잡도를 평가해 스킬 파이프라인을 구성하고, 필요하면 여러 에이전트를 붙여 실행한다. 계획·구현·리뷰·커밋이 하나의 흐름으로 이어지고, 각 단계에 검증 게이트가 들어간다.

```bash
/fz "ContentDetail 크래시 버그 찾아줘"    # 탐색 → 수정
/fz "새 기능 계획하고 구현해줘" --team      # 계획 → 구현 (멀티에이전트)
/fz-review "내 코드 리뷰해줘"              # 개별 스킬 직접 실행
```

---

## 설치

| 도구 | 없으면 | 사용처 | 설치 |
|------|--------|:------:|------|
| **Claude Node CLI** | 동작 불가 | 전부 | `npm install -g @anthropic-ai/claude-code` |
| **SuperClaude** | `sc:` 명령이 매칭되지 않는다 (폴백 0) | 15/21 | [GitHub](https://github.com/JeongJaeSoon/superclaude) |
| **Serena MCP** | 심볼 탐색이 Grep 으로 내려간다 (13 중 7 폴백) | 13/21 | fz 가 `.mcp.json` 으로 자동 등록. 런타임 `uv` 필수 — `brew install uv` |
| **Codex CLI** | 교차 검증이 `sc:analyze` 단독이 된다 (11 중 3 폴백) | 11/21 | `npm install -g @openai/codex` |
| **sequential-thinking MCP** | 구조화 추론 호출이 실패한다 (폴백 0) | 9/21 | `claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking` |
| **Context7 MCP** | 라이브러리 문서가 WebSearch 로 대체된다 (8 중 1 폴백) | 8/21 | `claude mcp add context7 -- npx -y @upstash/context7-mcp` |

⛔ 위 판정의 눈금 두 개. **사용처** = 스킬 21개 중 그 도구의 *호출*이 있는 파일 수다 — MCP 는 `mcp__…` 전체 접두사, Codex 는 `fz-codex`, SuperClaude 는 `sc:` 로 센다. 단어가 언급만 된 파일은 빠지므로 grep 어휘를 바꾸면 숫자가 달라진다. **폴백** = 각 스킬 `## 에러 대응` 표에 그 도구가 없을 때의 대체 경로가 적힌 스킬 수다.

`sc:` 는 자체 폴백이 없을 뿐 아니라 다른 도구들이 떨어지는 *목적지*(`/sc:analyze 단독`)이기도 하다. 없으면 폴백 사슬의 끝이 사라진다.

⛔ fz 가 번들하는 MCP 는 Serena 하나다. sequential-thinking 과 Context7 은 위 명령으로 직접 등록해야 한다.

스킬이 호출하지만 위 표에 없는 MCP 가 셋 더 있다. 상시가 아니라 특정 기능에서만 쓰기 때문이다 — `lsp`(4 스킬: fz-code·fz-fix·fz-search·fz-review 의 정의·참조 조회) · `github`(3: fz-pr·fz-peer-review·fz-pr-digest) · `atlassian`(3: fz-commit·fz-plan·fz-pr 의 JIRA 연동). 셋 다 폴백 선언이 0건이라, 없으면 그 기능이 그대로 멈춘다.

런타임 — `python3` **3.9+**(판정기·lint 가 3.9 문법으로 고정), `git`, `node`. `jq` 는 hook 템플릿 예시에서만 쓴다.

```bash
claude plugin marketplace add jaewooongyun/fz   # 최초 1회
claude plugin install fz

claude
> /fz "안녕"                                     # 응답하면 정상
```

프로젝트 루트에 `CLAUDE.md` 를 둔다. 모든 스킬과 에이전트가 이 파일을 참조한다. 필수 섹션은 `## Architecture`·`## Build`·`## Code Conventions` 이고, 템플릿은 `templates/CLAUDE.md.template` 에 있다.

iOS 프로젝트는 XcodeBuildMCP 와 SwiftUI Expert·Swift Concurrency 플러그인을 추가한다. 웹은 기본 구성으로 충분하다.

Codex CLI 는 모델을 README 가 고정하지 않는다. `/fz-codex` 가 `~/.codex/config.toml` 의 `model` 을 SSOT 로 위임하므로 최신 frontier 로 옮기는 것은 그 파일 한 줄이다. 구버전 CLI 가 config 의 모델을 못 읽으면 `/fz-codex` 에러 대응표가 CLI 업데이트를 권고한다 — 그래서 여기에 버전 하한을 적지 않는다.

Codex CLI 를 쓰면 네이티브 스킬을 심볼릭으로 연결한다.

```bash
bash ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/setup-codex-skills.sh
```

### 업데이트

```bash
claude plugin marketplace update fz-orchestrator
claude plugin update fz@fz-orchestrator
```

⛔ 접미사 없는 `claude plugin update fz` 는 `Plugin "fz" not found` 로 실패한다. 설치할 때는 마켓플레이스가 하나뿐이라 `fz` 로 통하지만, 설치된 이름은 `fz@fz-orchestrator` 이고 갱신은 그 이름으로 찾는다. 그리고 버전 문자열이 같으면 캐시를 갱신하지 않으니, 소스만 고치고 버전을 안 올리면 반영되지 않는다.

---

## Skills

사용자가 직접 부르는 스킬 18개. 나머지 3개는 `user-invocable: false` 인 내부 도구다 — `arch-critic` 과 `code-auditor` 는 `/fz-peer-review` 가 렌즈로 쓰고, `fz-new-file` 은 `/fz-code` 가 파일을 만들 때 헤더를 붙이는 데 쓴다.

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
| **보조** | `/fz-recording`, `/fz-pr-digest` | 회의록, PR 요약 |

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
| **quick-fix** | "타임아웃 변경" | fz-fix |
| **bug-hunt** | "크래시 버그 찾아줘" | fz-search → fz-fix |
| **plan-to-code** | "계획하고 구현" | fz-plan → fz-code |
| **code-to-review** | "구현하고 리뷰" | fz-code → fz-review |
| **review-to-ship** | "리뷰하고 커밋" | fz-review → fz-commit → fz-pr |
| **full-cycle** | "처음부터 끝까지" | fz-plan → fz-code → fz-review → fz-commit → fz-pr |

체인 칸에는 스킬만 적었다. 빌드와 Codex 교차 검증 게이트는 파이프라인마다 자동으로 끼워 넣으므로 여기 나오지 않는다 — 어느 지점에 무엇이 들어가는지는 `modules/pipelines.md` 각 항목의 `게이트` 행에 있다.

전체 19개: `modules/pipelines.md`

---

## 문서

| 문서 | 내용 |
|------|------|
| [완료 게이트](docs/completion-gates.md) | 작업 완료를 명령으로 판정하는 계층 — 원장 문법, 발화 지점, 탈출로, 세션 종료 차단 |
| [아키텍처](docs/architecture.md) | 디렉토리 구조, 오케스트레이션 흐름, 멀티에이전트 실행 방식 |
| [개발과 릴리즈](docs/development.md) | fz 자체를 수정할 때의 절차 |
| [CHANGELOG](CHANGELOG.md) · [릴리즈 노트](docs/releases/) | 버전별 변경 이력 |

### 작성·설계 가이드

`guides/` 아래 9개. 스킬·에이전트·모듈을 만들거나 고칠 때 참조한다. 줄 수는 `wc -l` 기준이다.

| 가이드 | 줄 | 내용 |
|--------|---:|------|
| [`llm-references.md`](guides/llm-references.md) | 147 | LLM·AI 권위 자료 단일 참조점 — Tier1 공식 · Tier2 arxiv 실증 · Tier3 커뮤니티. 가이드와 스킬 개선의 1차 출처 |
| [`prompt-optimization.md`](guides/prompt-optimization.md) | 755 | 프롬프트 10원칙 + Context Rot 대응 + Progressive Disclosure |
| [`skill-authoring.md`](guides/skill-authoring.md) | 580 | 스킬 작성 — YAML 계약, 500줄 제한, §12 Workflow 오케스트레이션 규약과 실패 복구 사다리 |
| [`skill-testing.md`](guides/skill-testing.md) | 470 | 스킬 테스팅 — Triggering·Functional 3단계와 테스트 스펙 템플릿 |
| [`skill-troubleshooting.md`](guides/skill-troubleshooting.md) | 292 | 스킬이 발화하지 않거나 잘못 매칭될 때의 진단 절차 |
| [`agent-team-guide.md`](guides/agent-team-guide.md) | 493 | 에이전트와 팀 구성 — Task Brief, 모델 전략, §8 Workflow 공식 사양 |
| [`fable-model-guide.md`](guides/fable-model-guide.md) | 255 | 모델 운용 — Lead 는 Fable 5, 실질 생산 워커는 Opus 5. effort 배정 기준 |
| [`clean-architecture.md`](guides/clean-architecture.md) | 324 | Dependency Rule 과 SOLID — 레이어 판정 기준 |
| [`harness-engineering.md`](guides/harness-engineering.md) | 1,334 | AI 에이전트 하네스 설계 — 게이트·오라클·negative control, NLAH Gap 분석 |

---

## What's New — v4.25.1

**완료 판정을 산문에서 exit code 로.** 완료 기준이 SKILL.md 산문에 있었고 그것을 검사하는 코드는 없었다. 이제 계획의 각 Step 이 실행 가능한 오라클을 갖고, 계획 확정·Step 종료·리뷰 재검증·세션 종료·health-check 다섯 지점에서 판정된다.

통과할 수 없는 게이트는 `ABANDON:` 으로 흔적을 남기고 넘어간다. 세션 종료 차단은 hook 을 설치한 머신에만 적용된다.

→ [완료 게이트 가이드](docs/completion-gates.md) · [릴리즈 노트](docs/releases/v4.25.1.md)
