# fz

[![Release](https://img.shields.io/github/v/release/jaewooongyun/fz?label=latest&color=blue)](https://github.com/jaewooongyun/fz/releases/latest) [![License](https://img.shields.io/github/license/jaewooongyun/fz?color=green)](LICENSE) [![Changelog](https://img.shields.io/badge/changelog-md-lightgrey)](CHANGELOG.md)

AI 개발 워크플로우를 오케스트레이션하는 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 플러그인이다.

자연어로 요청하면 복잡도를 평가해 스킬 파이프라인을 구성하고 필요하면 여러 에이전트를 붙여 실행한다. 계획, 구현, 리뷰, 커밋이 한 흐름으로 이어지고 단계마다 검증 게이트가 들어간다.

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
claude plugin install fz-compact@fz-orchestrator  # 선택. bg 세션 로컬 마스킹 압축, 기본 꺼짐
claude plugin install fz-guard@fz-orchestrator    # 선택. Phase 4 생략 · ad-hoc 에이전트를 훅으로 막는다

claude
> /fz "안녕"                                     # 응답하면 정상
```

프로젝트 루트에 `CLAUDE.md` 를 둔다. `## Architecture`, `## Build`, `## Code Conventions` 세 섹션이 있어야 하고 템플릿은 `templates/CLAUDE.md.template` 이다.

런타임으로 `python3` 3.9 이상, `git`, `node`, `perl` 이 필요하다. 판정기와 lint 는 3.9 문법에 맞춰 있고 `perl` 은 GPT 호출 래퍼가 쓴다(macOS 기본 포함).

### 함께 쓰는 도구

fz 가 번들하는 MCP 는 Serena 하나다. 나머지는 직접 등록한다.

| 도구 | 없으면 | 사용처 | 설치 |
|------|--------|:------:|------|
| **Claude Node CLI** | 동작 불가 | 전부 | `npm install -g @anthropic-ai/claude-code` |
| **SuperClaude** | `sc:` 명령 미매칭 (폴백 0) | 15/22 | `/plugin marketplace add SuperClaude-Org/SuperClaude_Plugin` 다음 `/plugin install sc@superclaude` (설치본 실측: sc 4.3.0, 2026-10-01) |
| **Serena MCP** | 심볼 탐색이 Grep 으로 (14 중 7 폴백) | 14/22 | 자동 등록. `uv` 필수 (`brew install uv`), 첫 기동 전에 캐시를 채운다(아래) |
| **GPT CLI** (`@openai/codex`) | 교차 검증이 `sc:analyze` 단독 (11 중 3 폴백) | 11/22 | `npm install -g @openai/codex` 뒤 CLI 로그인 1회 |
| **sequential-thinking** | 구조화 추론 실패 (폴백 0) | 9/22 | `claude mcp add sequential-thinking -- npx -y @modelcontextprotocol/server-sequential-thinking` |
| **Context7 MCP** | 라이브러리 문서가 WebSearch 로 (9 중 1 폴백) | 9/22 | `claude mcp add context7 -- npx -y @upstash/context7-mcp` |

> 사용처는 스킬 22개 가운데 그 도구를 호출하는 스킬 수다. MCP 는 `mcp__…`, GPT 는 `fz-gpt`, SuperClaude 는 `sc:` 로 센다. 언급만 한 파일은 빠지므로 grep 어휘를 바꾸면 숫자가 달라진다. 폴백은 각 스킬 `## 에러 대응` 표에 대체 경로를 적은 스킬 수다.

⛔ `sc:` 는 자체 폴백이 없고 다른 도구가 실패했을 때 내려가는 자리(`/sc:sc-analyze 단독`)이기도 하다. 그래서 없으면 폴백 사슬의 끝이 사라진다.

표 밖의 도구 셋은 특정 기능에만 쓴다. `lsp` 는 4개 스킬이 정의와 참조 탐색에, `github` 는 3개 스킬이 PR 에, JIRA(`atlassian-jira`)는 3개 스킬이 티켓 조회에 쓴다. `lsp` 는 폴백이 없어 없으면 그 기능이 멈춘다. `github` 는 fz-pr 만 `gh pr create` 안내로 내려가고 JIRA 는 fz-commit 과 fz-pr 이 수동 입력으로 내려간다.

프로젝트에 따라 더 붙인다. iOS 는 XcodeBuildMCP 와 SwiftUI Expert, Swift Concurrency 를 쓰고 웹은 기본 구성으로 충분하다.

#### 설치 뒤 확인할 것

- ⛔ MCP 서버 이름이 계약이다. 위 표의 `claude mcp add <이름>` 그대로 등록한다. 다른 이름으로 등록하거나 공식 마켓플레이스 플러그인으로 깔면 도구 이름이 `mcp__plugin_…` 으로 바뀐다. 그러면 Lead 는 그 도구를 쓰지만 워커 에이전트에는 오류 없이 전달되지 않는다. `github` 와 `XcodeBuildMCP` 도 같다. JIRA 는 `atlassian-jira` 서버의 `jira_get` 을 가정하므로 다른 Jira MCP 면 티켓 정보를 수동 입력으로 받는다
- ⛔ Serena 는 첫 기동에 실패하기 쉽다. 처음에는 약 300MB 를 내려받느라 MCP 연결 한도인 30초를 넘기곤 한다. 한 번 실패하면 Claude Code 가 약 15분 동안 다시 띄우지 않는다(Claude Code 2.1.318 실측). 설치 직후 미리 한 번 받아 둔다.
  ```bash
  uvx --from git+https://github.com/oraios/serena@v2.1.0 serena --help
  ```
- GPT CLI 는 설치만 하면 감지된다. 로그인하지 않으면 호출마다 약 18초 동안 재시도한 뒤 실패하고 대체 경로로 넘어간다
- 빠진 도구가 있어도 fz 는 깨지지 않는다. Grep 이나 자체 판단으로 대신하고 GPT 단계는 `[GPT 미사용]` 으로 표기한다. 다만 빠졌다고 알려 주지 않으니 세션에서 `/mcp` 를 열어 `plugin:fz:serena` 가 connected 인지 확인한다

GPT CLI 를 쓰면 네이티브 스킬을 심볼릭 링크로 연결한다. 링크가 없어도 exec 모드 호출은 번들 스킬 본문을 직접 넣지만 review 모드 호출은 역할 스킬 없이 돈다.

```bash
bash "$(printf '%s\n' ~/.claude/plugins/cache/fz-orchestrator/fz/*/ | sort -V | tail -1)scripts/setup-gpt-skills.sh"
```

⛔ 캐시에 버전이 여럿이면 glob 을 그대로 실행하지 않는다. 사전순으로 첫 경로가 돌아 가장 오래된 판에 링크될 수 있다. 위 명령처럼 `sort -V` 로 최신 하나를 고르거나 로컬 체크아웃이면 그 플러그인 루트에서 `bash scripts/setup-gpt-skills.sh` 를 실행한다. setup 은 `gpt-skills/` 만 링크하고 이 플러그인의 Claude 스킬(`skills/`)을 가리키는 옛 링크는 지운다.

⛔ README 는 GPT 모델과 CLI 버전 하한을 고정하지 않는다. 모델과 effort 는 세션에서 고르고 고르지 않으면 `~/.codex/config.toml` 값을 쓴다. 정본은 `modules/gpt-strategy.md` § 모델·effort 선택이다. CLI 가 구버전이면 에러 대응표가 업데이트를 권한다.

### 업데이트

```bash
claude plugin marketplace update fz-orchestrator
claude plugin update fz@fz-orchestrator
claude plugin update fz-compact@fz-orchestrator   # fz-compact 를 설치했을 때만
claude plugin update fz-guard@fz-orchestrator     # fz-guard 를 설치했을 때만
```

업데이트는 GPT 스킬 setup 을 다시 돌리지 않는다. 링크 상태는 위 setup 명령에 `--check` 를 붙여 확인한다.

- 남은 옛 링크(이 플러그인 Claude 스킬 링크, 끊어진 소유 링크)를 읽기 전용으로 나열하고 stale 이면 exit 1 이다
- 정리하려면 인자 없이 다시 실행한다. 다른 판을 가리키는 GPT 스킬 링크는 살아 있으면 나열하지 않으니 판을 맞출 때도 인자 없이 다시 실행한다
- `/fz-manage check` 도 같은 점검을 경고로 보여 준다

⛔ 접미사 없이 `claude plugin update fz` 를 부르면 `Plugin "fz" not found` 로 실패한다. 설치할 때는 `fz` 로 통하지만 설치된 이름은 `fz@fz-orchestrator` 이다. 버전 문자열이 같으면 캐시를 갱신하지 않으므로 소스만 고치고 버전을 올리지 않으면 반영되지 않는다.

---

## Skills

사용자가 직접 부르는 스킬은 19개다. 나머지 3개는 `user-invocable: false` 인 내부 도구다. `arch-critic` 과 `code-auditor` 는 `/fz-peer-review` 가 렌즈로 쓰고 `fz-new-file` 은 `/fz-code` 가 파일을 만들 때 헤더를 붙이는 데 쓴다.

| 카테고리 | 스킬 | 설명 |
|---------|------|------|
| **오케스트레이터** | `/fz` | 자연어 요청을 파이프라인으로 자동 구성 |
| **개발** | `/fz-plan` | 요구사항 분석, 영향 범위, RTM |
| | `/fz-code` | 계획에 따른 점진적 구현과 빌드 검증 |
| | `/fz-fix` | 버그 수정 (4-Phase 디버깅) |
| | `/fz-review` | 3중 검증 (Claude + GPT + sc:analyze) |
| | `/fz-commit`, `/fz-pr` | 커밋, Fork 기반 PR |
| | `/fz-rebase` | 롱텀 브랜치 리베이스와 양방향 조용한 유실 게이트 (경로 단위 배타 분할, prepush 원격 실측) |
| **탐색** | `/fz-discover` | 풍경 탐색과 경로 매핑 |
| | `/fz-search` | 코드 탐색 (symbolic, pattern) |
| | `/fz-explain` | 코드·구조 설명 (전체 흐름 위에 동작과 코드를 1:1로 매핑) |
| **검증** | `/fz-gpt` | GPT CLI 교차 검증과 `micro-eval` 단일 주장 재평가. 모델과 effort 는 세션에서 고른다(`modules/gpt-strategy.md` § 모델·effort 선택) |
| | `/fz-peer-review` | 동료 PR 리뷰 (9개 관점, caller 와 convention 검증) |
| **문서/시스템** | `/fz-memory` | 메모리 관리 |
| | `/fz-skill` | 스킬 관리. `write` 서브커맨드는 문서 작성과 프롬프트 최적화 |
| | `/fz-manage` | 인벤토리와 건강 체크 |
| | `/fz-modernize` | 가이드 최신화 |
| **보조** | `/fz-recording`, `/fz-pr-digest` | 회의록, PR 요약 |

---

## Agents

Workflow 스크립트가 `agentType: 'fz:{name}'` 으로 불러 쓰는 렌즈 정의다. 리뷰 밖에서 쓰는 아키텍처 렌즈는 `arch-lens` 다. `review-arch` 에서 리뷰 전용 사전 주입(arch-critic)을 뺀 것이다.

모델은 워크플로가 호출마다 정한다(opus 34곳, sonnet 6곳, fable 3곳). 에이전트 정의의 기본값은 sonnet 이다.

| 도메인 | Primary | Supporting |
|--------|:---:|---|
| **계획** | plan-structure | plan-impact, plan-edge-case, plan-merge(병합 전용, 도구 없음). 롤백 경로 plan-collaborative 는 arch-lens 와 review-direction 도 쓴다 |
| **구현** | impl-correctness | arch-lens, impl-quality |
| **리뷰** | review-arch | review-quality, review-correctness, review-counter |
| **탐색** | — | search-symbolic, search-pattern. fz-discover 는 plan-structure 와 arch-lens 를 쓴다 |
| **공통** | — | memory-curator(회상 전용, 워크플로는 부르지 않는다). swarm.js 기본 워커는 review-correctness |

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

체인 칸에는 스킬만 적었다. 빌드와 GPT 교차 검증 게이트는 파이프라인마다 자동으로 끼워 넣어 여기서는 뺐다. 어느 지점에 무엇이 들어가는지는 `modules/pipelines.md` 각 항목의 `게이트` 행에 있다.

전체 19개는 `modules/pipelines.md` 에 있다.

---

## 문서

| 문서 | 내용 |
|------|------|
| [완료 게이트](docs/completion-gates.md) | 작업 완료를 명령으로 판정하는 계층. 원장 문법, 발화 지점, 탈출로, 세션 종료 차단을 다룬다 |
| [아키텍처](docs/architecture.md) | 디렉토리 구조, 오케스트레이션 흐름, 멀티에이전트 실행 방식 |
| [개발과 릴리즈](docs/development.md) | fz 자체를 수정할 때의 절차 |
| [CHANGELOG](CHANGELOG.md) · [릴리즈 노트](docs/releases/) | 버전별 변경 이력 |
| [A/B 끝점 시계](docs/ab-endpoint-clock.md) | `ab_ledger.py collect --endpoint-clock` 이 읽는 러너 시계 줄의 형식과 판정 |

### 작성·설계 가이드

`guides/` 아래 9개가 있다. 스킬, 에이전트, 모듈을 만들거나 고칠 때 본다. 줄 수는 `wc -l` 기준이다.

| 가이드 | 줄 | 내용 |
|--------|---:|------|
| [`llm-references.md`](guides/llm-references.md) | 186 | LLM·AI 권위 자료를 모은 단일 참조점. Tier1 공식, Tier2 arxiv 실증, Tier3 커뮤니티로 나누고 가이드와 스킬을 고칠 때 1차 출처로 쓴다 |
| [`prompt-optimization.md`](guides/prompt-optimization.md) | 753 | 프롬프트 10원칙, Context Rot 대응, Progressive Disclosure |
| [`skill-authoring.md`](guides/skill-authoring.md) | 683 | 스킬 작성. YAML 계약, 500줄 제한, §12 Workflow 오케스트레이션 규약과 실패 복구 사다리 |
| [`skill-testing.md`](guides/skill-testing.md) | 530 | 스킬 테스트. Triggering·Functional 3단계와 테스트 스펙 템플릿 |
| [`skill-troubleshooting.md`](guides/skill-troubleshooting.md) | 295 | 스킬이 발화하지 않거나 잘못 매칭될 때의 진단 절차 |
| [`agent-team-guide.md`](guides/agent-team-guide.md) | 506 | 에이전트와 팀 구성. Task Brief, 모델 전략, §8 Workflow 공식 사양 |
| [`model-guide.md`](guides/model-guide.md) | 325 | 모델 운용. Lead 는 Fable 5.1, 실질 생산 워커는 Opus 5.5 이고 effort 배정 기준을 둔다 |
| [`clean-architecture.md`](guides/clean-architecture.md) | 324 | Dependency Rule 과 SOLID 로 레이어를 판정하는 기준 |
| [`harness-engineering.md`](guides/harness-engineering.md) | 1,373 | AI 에이전트 하네스 설계. 게이트, 오라클, negative control, NLAH Gap 분석 |

---

## What's New — v4.53.0

고친 finding 이 닫히지 않던 출구를 대조기로 막고 기계 강제 fz-guard 를 더했다. 릴리스 노트 `Closes:` 는 이제 `check_release_closes.py` 가 레지스트리의 `applied: full` 전부와 대조하고, 배출은 일부만 고친 엔트리를 거부한다. 게이트 판정기에는 승인 전 기준선(`--baseline-probe`)과 핀 파일을 묶는 `PIN:` 속성이 생겼다.
선택형 하위 플러그인 fz-guard 는 Phase 4 승인 전 쓰기를 막고 허용 목록 밖 ad-hoc 에이전트를 묻는다. 교훈을 메모리에만 쓴 턴은 종료를 한 번 막는다. 기본으로 설치되지 않는다. 이 판은 finding 24건을 닫고 279건은 묶음별 로드맵으로 넘긴다.
→ [릴리즈 노트](docs/releases/v4.53.0.md)
