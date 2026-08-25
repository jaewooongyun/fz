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
| **Serena MCP** | 심볼 탐색이 Grep 폴백으로 내려간다 | 13/21 스킬 | fz 설치 시 `.mcp.json` 으로 자동 등록. 런타임 `uv` 필수 — `brew install uv` |
| **Codex CLI** | 교차 검증 스킬이 `sc:analyze` 단독으로 폴백 | 11/21 스킬 | `npm install -g @openai/codex` · **0.124.0+** (gpt-5.5 지원) |
| **SuperClaude** | `sc:` 명령이 매칭되지 않는다 | 15/21 스킬 | [GitHub](https://github.com/JeongJaeSoon/superclaude) |
| Context7 MCP | 라이브러리 문서를 WebSearch 로 대체 | 8/21 스킬 | [GitHub](https://github.com/upstash/context7) |

⛔ 위 판정은 **사용처 수와 폴백 선언 유무**로 실측했다. Serena·Codex·Context7 은 에러 대응표에 폴백이 있어 없어도 돌아가고(각 10·6·1건), `sc:` 는 폴백이 2건뿐이라 15개 스킬에서 명령이 그냥 매칭되지 않는다.

런타임 — `python3` **3.9+**(판정기·lint 가 3.9 문법으로 고정), `git`, `node`. `jq` 는 hook 템플릿 예시에서만 쓴다.

```bash
claude plugin marketplace add jaewooongyun/fz   # 최초 1회
claude plugin install fz

claude
> /fz "안녕"                                     # 응답하면 정상
```

프로젝트 루트에 `CLAUDE.md` 를 둔다. 모든 스킬과 에이전트가 이 파일을 참조한다. 필수 섹션은 `## Architecture`·`## Build`·`## Code Conventions` 이고, 템플릿은 `templates/CLAUDE.md.template` 에 있다.

iOS 프로젝트는 XcodeBuildMCP 와 SwiftUI Expert·Swift Concurrency 플러그인을 추가한다. 웹은 기본 구성으로 충분하다.

Codex CLI 를 쓰면 네이티브 스킬을 심볼릭으로 연결한다.

```bash
bash ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/setup-codex-skills.sh
```

### 업데이트

```bash
claude plugin marketplace update fz-orchestrator
claude plugin update fz
```

---

## Skills

사용자가 직접 부르는 스킬 18개. 나머지 3개(`arch-critic`, `code-auditor`, `fz-new-file`)는 `user-invocable: false` 인 내부 도구로, `/fz-peer-review` 가 렌즈로 쓴다.

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

## 문서

| 문서 | 내용 |
|------|------|
| [완료 게이트](docs/completion-gates.md) | 작업 완료를 명령으로 판정하는 계층 — 원장 문법, 발화 지점, 탈출로, 세션 종료 차단 |
| [아키텍처](docs/architecture.md) | 디렉토리 구조, 오케스트레이션 흐름, 멀티에이전트 실행 방식 |
| [개발과 릴리즈](docs/development.md) | fz 자체를 수정할 때의 절차 |
| [CHANGELOG](CHANGELOG.md) · [릴리즈 노트](docs/releases/) | 버전별 변경 이력 |

### 작성·설계 가이드

`guides/` 아래 9개. 스킬·에이전트·모듈을 만들거나 고칠 때 참조한다.

| 가이드 | 줄 | 내용 |
|--------|---:|------|
| [`llm-references.md`](guides/llm-references.md) | 148 | LLM·AI 권위 자료 단일 참조점 — Tier1 공식 · Tier2 arxiv 실증 · Tier3 커뮤니티. 가이드와 스킬 개선의 1차 출처 |
| [`prompt-optimization.md`](guides/prompt-optimization.md) | 756 | 프롬프트 10원칙 + Context Rot 대응 + Progressive Disclosure |
| [`skill-authoring.md`](guides/skill-authoring.md) | 581 | 스킬 작성 — YAML 계약, 500줄 제한, §12 Workflow 오케스트레이션 규약과 실패 복구 사다리 |
| [`skill-testing.md`](guides/skill-testing.md) | 471 | 스킬 테스팅 — Triggering·Functional 3단계와 테스트 스펙 템플릿 |
| [`skill-troubleshooting.md`](guides/skill-troubleshooting.md) | 293 | 스킬이 발화하지 않거나 잘못 매칭될 때의 진단 절차 |
| [`agent-team-guide.md`](guides/agent-team-guide.md) | 494 | 에이전트와 팀 구성 — Task Brief, 모델 전략, §8 Workflow 공식 사양 |
| [`fable-model-guide.md`](guides/fable-model-guide.md) | 256 | 모델 운용 — Lead 는 Fable 5, 실질 생산 워커는 Opus 5. effort 배정 기준 |
| [`clean-architecture.md`](guides/clean-architecture.md) | 325 | Dependency Rule 과 SOLID — 레이어 판정 기준 |
| [`harness-engineering.md`](guides/harness-engineering.md) | 1,335 | AI 에이전트 하네스 설계 — 게이트·오라클·negative control, NLAH Gap 분석 |

| **prompt-optimization.md** | 10대 프롬프트 원칙 + Context Rot 대응 |
| **agent-team-guide.md** | 에이전트 팀 (2.5-Turn, Task Brief, 모델 전략) |
| **harness-engineering.md** | AI 에이전트 하네스 설계 + NLAH Gap 분석 (1046줄) |

---

## What's New — v4.25.0

**완료 판정을 산문에서 exit code 로.** 완료 기준이 SKILL.md 산문에 있었고 그것을 검사하는 코드는 없었다. 이제 계획의 각 Step 이 실행 가능한 오라클을 갖고, 계획 확정·Step 종료·리뷰 재검증·세션 종료·health-check 다섯 지점에서 판정된다.

통과할 수 없는 게이트는 `ABANDON:` 으로 흔적을 남기고 넘어간다. 세션 종료 차단은 hook 을 설치한 머신에만 적용된다.

→ [완료 게이트 가이드](docs/completion-gates.md) · [릴리즈 노트](docs/releases/v4.25.0.md)
