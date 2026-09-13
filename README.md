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
| **SuperClaude** | `sc:` 명령 미매칭 (폴백 0) | 15/22 | [GitHub](https://github.com/JeongJaeSoon/superclaude) |
| **Serena MCP** | 심볼 탐색이 Grep 으로 (14 중 7 폴백) | 14/22 | 자동 등록 · `uv` 필수 (`brew install uv`) |
| **Codex CLI** | 교차 검증이 `sc:analyze` 단독 (11 중 3 폴백) | 11/22 | `npm install -g @openai/codex` |
| **sequential-thinking** | 구조화 추론 실패 (폴백 0) | 10/22 | `claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking` |
| **Context7 MCP** | 라이브러리 문서가 WebSearch 로 (10 중 1 폴백) | 10/22 | `claude mcp add context7 -- npx -y @upstash/context7-mcp` |

⛔ `sc:` 는 자체 폴백이 없을 뿐 아니라 다른 도구가 떨어지는 **목적지**(`/sc:sc-analyze 단독`)다 — 없으면 폴백 사슬의 끝이 사라진다.
표 밖에서 특정 기능만 쓰는 MCP 셋: `lsp`(4 스킬, 정의·참조) · `github`(3, PR) · `atlassian`(4, JIRA). **폴백 0건**이라 없으면 그 기능이 멈춘다.
프로젝트별 추가 — iOS 는 XcodeBuildMCP + SwiftUI Expert·Swift Concurrency. 웹은 기본 구성으로 충분하다.

Codex CLI 를 쓰면 네이티브 스킬을 심볼릭으로 연결한다.

```bash
bash ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/setup-gpt-skills.sh
```

⛔ GPT 모델·버전 하한은 README 가 고정하지 않는다 — `/fz-gpt` 가 `~/.codex/config.toml` 의 `model` 을 SSOT 로 위임한다(구버전이면 에러 대응표가 업데이트를 권고).

> **표의 수치** — **사용처** = 스킬 22개 중 그 도구의 *호출*이 있는 파일 수(MCP 는 `mcp__…`, GPT 는 `fz-gpt`, SuperClaude 는 `sc:` 로 센다). 언급만 된 파일은 빠지므로 grep 어휘를 바꾸면 숫자가 달라진다. **폴백** = 각 스킬 `## 에러 대응` 표에 대체 경로가 적힌 스킬 수.

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
| | `/fz-review` | 3중 검증 (Claude + GPT + sc:analyze) |
| | `/fz-commit`, `/fz-pr` | 커밋 + Fork 기반 PR |
| | `/fz-rebase` | 리베이스 조용한 유실 게이트 (경로 단위 배타 분할 + prepush 원격 실측) |
| **탐색** | `/fz-discover` | 풍경 탐색 + 경로 매핑 |
| | `/fz-search` | 코드 탐색 (symbolic + pattern) |
| **검증** | `/fz-gpt` | Codex CLI 교차 검증 (모델은 `config.toml` SSOT 위임 = 항상 최신 frontier) + `micro-eval` 단일 주장 재평가 |
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

체인 칸에는 스킬만 적었다. 빌드와 GPT 교차 검증 게이트는 파이프라인마다 자동으로 끼워 넣으므로 여기 나오지 않는다 — 어느 지점에 무엇이 들어가는지는 `modules/pipelines.md` 각 항목의 `게이트` 행에 있다.

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
| [`llm-references.md`](guides/llm-references.md) | 159 | LLM·AI 권위 자료 단일 참조점 — Tier1 공식 · Tier2 arxiv 실증 · Tier3 커뮤니티. 가이드와 스킬 개선의 1차 출처 |
| [`prompt-optimization.md`](guides/prompt-optimization.md) | 758 | 프롬프트 10원칙 + Context Rot 대응 + Progressive Disclosure |
| [`skill-authoring.md`](guides/skill-authoring.md) | 632 | 스킬 작성 — YAML 계약, 500줄 제한, §12 Workflow 오케스트레이션 규약과 실패 복구 사다리 |
| [`skill-testing.md`](guides/skill-testing.md) | 500 | 스킬 테스팅 — Triggering·Functional 3단계와 테스트 스펙 템플릿 |
| [`skill-troubleshooting.md`](guides/skill-troubleshooting.md) | 292 | 스킬이 발화하지 않거나 잘못 매칭될 때의 진단 절차 |
| [`agent-team-guide.md`](guides/agent-team-guide.md) | 493 | 에이전트와 팀 구성 — Task Brief, 모델 전략, §8 Workflow 공식 사양 |
| [`model-guide.md`](guides/model-guide.md) | 304 | 모델 운용 — Lead 는 Fable 5.1, 실질 생산 워커는 Opus 5. effort 배정 기준 |
| [`clean-architecture.md`](guides/clean-architecture.md) | 324 | Dependency Rule 과 SOLID — 레이어 판정 기준 |
| [`harness-engineering.md`](guides/harness-engineering.md) | 1,346 | AI 에이전트 하네스 설계 — 게이트·오라클·negative control, NLAH Gap 분석 |

---

## What's New — v4.35.0

**고친 검사가 같은 방식으로 다시 샜다.** 자체 검사 13종이 전부 초록인데 통합 배선 두 곳이
몇 달째 죽어 있었다. 그것을 고쳤고, **고치는 과정에서 같은 종류의 결함을 다시 만들었다.**
이 릴리즈에서 가장 값이 나간 것은 수리가 아니라 그 재발을 적대적 검증 셋이 잡아낸 기록이다.

**이름이 어긋난 배선은 오류를 내지 않는다.** 외부 명령 20종이 설치본에서는 `sc-` 접두를 갖고,
에이전트 `tools:` 의 MCP 도구 이름은 런타임 규격 `mcp__plugin_<plugin>_<server>__<tool>` 와
어긋나 있었다. **86곳 · 148곳**을 고쳤다. ⛔ **왜 오류가 안 났나**가 핵심이다 — `tools:` 는 목록이
**전부** 미해결일 때만 launch 가 실패한다. `Read, Grep, Glob` 이 살아 있으면 그 항목만 조용히
빠진다. 워커 251회 실행에서 해당 호출이 0건이었던 이유다.

**배선을 교체하면 계약이 따라오지 않는다.** 기본 플랜 워크플로를 바꿀 때 반환 계약 넷이 함께
사라졌고 소비처는 남아 영구 no-op 이었다. 복구하며 **스키마에 필드가 있는데 프롬프트가 요청하지
않아 죽어 있던** 다섯 번째를 찾았다 — 필드 존재와 계약 작동은 다르다. ⛔ 콜은 늘지 않는다.

**검증기 일곱 곳이 스스로 통과를 인쇄했다.** `NaN` 을 받아들여 범위 비교가 둘 다 거짓이 되던 것,
미지원 키워드 검사가 데이터를 따라가 빈 배열 아래에 도달하지 않던 것, 렌즈 하나가 죽어도
`pass` + 완주 3/3 을 인쇄하던 것, 위반을 인쇄하고 `exit 0` 하던 것.
⛔ **negative fixture 를 함께 넣었다** — fail-open 은 정상 입력으로 검출되지 않는다.

⭐ **그런데 고친 세 자리가 같은 클래스를 재생산했다.** `awk` 의 `END` 는 입력이 비어도 0 을 찍어
git 실패가 "변경 0줄" 로 번역됐고, `set -e` 는 **도구 셸에서 무효**라 실패해도 성공 토큰이 찍혔고,
`rg` 는 이 환경에서 셸 함수라 bash 에 없었다. **공통 형태 하나다 — 측정 실패와 위반 0 이 같은
출력이다.** 셋 다 positive control 이 없었다. 적대적 검증이 확정 결함 **9건**을 냈고 전건 고쳤다.
⛔ 이 릴리즈의 제목이 변경 자신에게 그대로 성립한다 — 초록 13개 중 이것들을 잡는 검사가 없었다.

**두 수치를 정정한다.** `⛔` 총량 2,227 은 하네스 부하로 **약 57% 과대**다 — 상위 10 중 6개가
모델이 읽지 않는 파일이고 스크립트의 `⛔` 는 검사 항목 표의 문자열이다(적재분 약 1,070).
"floor +89%/6주" 는 **근거가 성립하지 않는다** — 그 지표 개념을 도입한 커밋이 07-31 인데
기준선이 07-25 다. 깨끗한 것은 09-06→09-13 의 **+8.3%** 뿐이다.

**하지 않은 것**: effort 일괄 하향(45곳을 한 번에 내리는 것은 방향만 반대인 미측정 결정) ·
마커 감량(적대 판정은 *"규칙 내용이 아니라 싣는 구조가 과하다"* 이고, 죽은 것으로 분류된 것들은
조건 소멸이 아니라 **애초에 지시가 아닌 제목 장식**이었다 — 처방은 삭제가 아니라 어휘 정리다).

**검증**: health-check 13검사 exit 0 · 게이트 self-test 67/67 · **회귀 오라클 12 → 13** ·
릴리즈 동기 DOCS_SYNC_OK · workflow 문법 2/2 · fail-open 러너 3/3 · 기능단위 4커밋.

→ [릴리즈 노트](docs/releases/v4.35.0.md)
