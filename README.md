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

```bash
claude plugin marketplace add jaewooongyun/fz   # 최초 1회
claude plugin install fz

claude
> /fz "안녕"                                     # 응답하면 정상
```

프로젝트 루트에 `CLAUDE.md` 를 둔다 — 필수 섹션 `## Architecture`·`## Build`·`## Code Conventions`, 템플릿은 `templates/CLAUDE.md.template`.
런타임: `python3` **3.9+**(판정기·lint 가 3.9 문법 고정) · `git` · `node`.

### 함께 쓰는 도구

fz 가 번들하는 MCP 는 **Serena 하나**다. 나머지는 직접 등록한다.

| 도구 | 없으면 | 사용처 | 설치 |
|------|--------|:------:|------|
| **Claude Node CLI** | 동작 불가 | 전부 | `npm install -g @anthropic-ai/claude-code` |
| **SuperClaude** | `sc:` 명령 미매칭 (폴백 0) | 15/21 | [GitHub](https://github.com/JeongJaeSoon/superclaude) |
| **Serena MCP** | 심볼 탐색이 Grep 으로 (13 중 7 폴백) | 13/21 | 자동 등록 · `uv` 필수 (`brew install uv`) |
| **Codex CLI** | 교차 검증이 `sc:analyze` 단독 (11 중 3 폴백) | 11/21 | `npm install -g @openai/codex` |
| **sequential-thinking** | 구조화 추론 실패 (폴백 0) | 9/21 | `claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking` |
| **Context7 MCP** | 라이브러리 문서가 WebSearch 로 (8 중 1 폴백) | 8/21 | `claude mcp add context7 -- npx -y @upstash/context7-mcp` |

⛔ `sc:` 는 자체 폴백이 없을 뿐 아니라 다른 도구가 떨어지는 **목적지**(`/sc:analyze 단독`)다 — 없으면 폴백 사슬의 끝이 사라진다.
표 밖에서 특정 기능만 쓰는 MCP 셋: `lsp`(4 스킬, 정의·참조) · `github`(3, PR) · `atlassian`(3, JIRA). **폴백 0건**이라 없으면 그 기능이 멈춘다.
프로젝트별 추가 — iOS 는 XcodeBuildMCP + SwiftUI Expert·Swift Concurrency. 웹은 기본 구성으로 충분하다.

Codex CLI 를 쓰면 네이티브 스킬을 심볼릭으로 연결한다.

```bash
bash ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/setup-codex-skills.sh
```

⛔ Codex 모델·버전 하한은 README 가 고정하지 않는다 — `/fz-codex` 가 `~/.codex/config.toml` 의 `model` 을 SSOT 로 위임한다(구버전이면 에러 대응표가 업데이트를 권고).

> **표의 수치** — **사용처** = 스킬 22개 중 그 도구의 *호출*이 있는 파일 수(MCP 는 `mcp__…`, Codex 는 `fz-codex`, SuperClaude 는 `sc:` 로 센다). 언급만 된 파일은 빠지므로 grep 어휘를 바꾸면 숫자가 달라진다. **폴백** = 각 스킬 `## 에러 대응` 표에 대체 경로가 적힌 스킬 수.

### 업데이트

```bash
claude plugin marketplace update fz-orchestrator
claude plugin update fz@fz-orchestrator
```

⛔ 접미사 없는 `claude plugin update fz` 는 `Plugin "fz" not found` 로 실패한다 — 설치할 땐 `fz` 로 통하지만 **설치된 이름은 `fz@fz-orchestrator`** 다. 버전 문자열이 같으면 캐시를 갱신하지 않으니, 소스만 고치고 버전을 안 올리면 반영되지 않는다.

---

## Skills

사용자가 직접 부르는 스킬 19개. 나머지 3개는 `user-invocable: false` 인 내부 도구다 — `arch-critic` 과 `code-auditor` 는 `/fz-peer-review` 가 렌즈로 쓰고, `fz-new-file` 은 `/fz-code` 가 파일을 만들 때 헤더를 붙이는 데 쓴다.

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

## What's New — v4.28.0

**게이트가 없던 게 아니라 헛돌고 있었다.** 자기 규칙과 자기 코드를 검사하던 자리 여덟 곳이
통과를 인쇄하면서 실제로는 아무것도 재지 않았다. 실패가 빨간불이 아니라 **초록불로 나타난다.**

Coverage Gate 는 분모를 파일로 고정해, 파일 안의 절을 세는 주장이 1/1 = 100% 로 통과했다.
전수 주장이 겨누는 **대상 단위 U** 와 읽어야 할 파일 수 F 를 분리하고 절차 0 을 신설했다.
⛔ 결과 건수("위반 0건")를 단위로 삼지 않는다 — 그러면 violation 이 단위가 되어 같은 붕괴가
재발한다. 외부 채점이 이 대목을 한 번 더 좁혔다.

d6 오라클은 워크플로 함수를 **복사해 두고 복사본을 검사**했다. 원본의 카운터 취소 연산을 지워도
네 케이스가 전부 통과한다. 형제 테스트 둘이 이미 쓰던 `>>> PURE:` 마커 방식으로 바꿔 원본을
런타임 추출한다. 뮤테이션 네 종이 전부 잡힌다.

그리고 그 오라클들은 **어느 자동 경로에도 없었다.** 10개 중 참조가 있는 것은 하나였다. 검사
4.6·4.7 을 신설해 전부 돌린다. 러너를 0개 찾으면 통과가 아니라 미실행이다.

⭐ 정본 둘이 서로를 위반하고 있었다. 매핑 블록 정본은 볼드 라벨 다섯을 한 문단에 두라고
규정하는데 G8 은 볼드 셋 이상을 과잉으로 봤다 — **정본을 지킬수록 게이트에 걸린다.** 줄머리
라벨을 강조에서 빼고, 기대값만 적혀 있던 fixture 를 실행 가능한 검사기로 만들었다.

감사 판정 두 건은 뒤집혔다. "파이프라인 15종 미등재" 는 실제로 선언 한 문장 문제였고, 판정대로
15행을 옮겼다면 트리거가 두 파일에 중복돼 서서히 어긋난다. 배포 가능하도록 개인 경로·티켓·조직
어휘도 걷어냈다.

→ [릴리즈 노트](docs/releases/v4.28.0.md)
