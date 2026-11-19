# Agent Definition Template

Custom subagent 정의 파일(`agents/*.md`) 작성 시 이 템플릿을 참고하세요.

## YAML Frontmatter

```yaml
---
name: {agent-name}                    # lowercase+hyphen, 필수
description: >-                        # 필수: 반환물 한 줄 + 호출 계약 한 줄
  {역할} — {무엇을 반환하는가}.
  fz 워크플로 내부 워커({호출 워크플로}) — 직접 쓰지 않는다.
model: sonnet                          # sonnet|opus|inherit
# Model upgrade note: upgraded to opus in {specific teams} (see team-registry.md)
tools: Read, Grep, Glob, Bash         # 도구 제한 (생략 시 부모 상속)
# permissionMode: 필드를 넣지 않는다 — 플러그인 에이전트는 이 필드를 지원하지 않아 불러올 때 무시된다(guides/agent-team-guide.md §8.5)
maxTurns: 15                           # 합리적인 턴 제한
# memory: 필드를 넣지 않는다 — Read/Write/Edit 가 자동 부여돼 Workflow 에이전트의 '쓰기 없음' 계약과 충돌하고
#   세션 간 기록이 A/B 입력을 오염시킨다(guides/agent-team-guide.md §8.1). 예외는 워크플로 밖 memory-curator 뿐이다
skills:                                # 사전 로드 스킬
  - skill-name
# hooks: · mcpServers: 필드를 넣지 않는다 — 플러그인 에이전트는 두 필드를 지원하지 않아 불러올 때 무시된다(guides/agent-team-guide.md §8.3 · §8.5)
---
```

### Field Guide

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | 에이전트 식별자. lowercase + hyphen |
| `description` | Yes | 두 줄 — 반환물 한 줄 + 호출 계약 한 줄. 워크플로 내부 워커는 `fz 워크플로 내부 워커({호출 워크플로}) — 직접 쓰지 않는다`, Lead 가 직접 부르는 에이전트는 그 호출처를 적고 '내부 워커' 문구를 쓰지 않는다 |
| `model` | Yes | 기본 모델. Primary Worker는 opus, 지원 역할은 sonnet |
| `tools` | No | 허용 도구 목록. 생략하면 부모 컨텍스트 상속 |
| `permissionMode` | ⛔ 넣지 않음 | 플러그인 에이전트는 이 필드를 지원하지 않아 불러올 때 무시된다. 권한 방어는 `tools` 허용 목록이 맡는다(guides/agent-team-guide.md §8.5) |
| `maxTurns` | No | 최대 턴 수. 10-20 권장 |
| `memory` | ⛔ 넣지 않음 | Read/Write/Edit 가 자동 부여돼 Workflow '쓰기 없음' 계약과 충돌하고 A/B 입력을 오염시킨다(guides/agent-team-guide.md §8.1 · lint #N13). 예외는 워크플로 밖 memory-curator 뿐 |
| `skills` | No | 자동 로드할 스킬 목록 |
| `hooks` | ⛔ 넣지 않음 | 플러그인 에이전트는 이 필드를 지원하지 않아 불러올 때 무시된다. fz 본체는 훅을 등록하지 않는다(guides/agent-team-guide.md §8.3) |
| `mcpServers` | ⛔ 넣지 않음 | 플러그인 에이전트는 이 필드를 지원하지 않아 불러올 때 무시된다. MCP 도구는 `tools` 에 직접 나열한다(`agents/review-arch.md` · guides/agent-team-guide.md §8.5) |

## System Prompt Body

frontmatter 아래에 마크다운으로 시스템 프롬프트를 작성합니다.

```markdown
You are a {role} for {domain/project}.

## 작업 디렉토리
프로젝트 루트: `/path/to/project`

## MCP 도구 활용 전략

### Primary (항상 사용)
- `mcp__plugin_fz_serena__find_symbol` → {purpose}

### Secondary (필요 시)
- `mcp__context7__query-docs` → {purpose}

### 사용 불가 (Team agent 제약)
- {tool} → 필요 시 **반환 구조에 명시**한다 (Lead가 재주입 — ⛔ 1-shot이므로 중간 요청 채널은 없다)

## Symbol tools — use them whenever they are in your tool list

If any `mcp__plugin_fz_serena__` tool is in your tool list, the lead session has a symbol server running. Use the ones you have for every code file, scripts included (shell, Python, JavaScript, Swift and so on). Do not guess whether the server covers a file type: call the tool on the first file of that type and see. A line below that names a tool you do not have does not apply to you: do that part with Grep and Read, and do not report it as a fallback.
- `find_symbol` — where a named function, type or method is defined: call it first, not Grep.
- `find_referencing_symbols` — who calls or uses it: call it first. It returns real references only (no comments, no strings). It does not return protocol or interface implementations, so never treat a short or empty result as proof of absence.
- `get_symbols_overview` — the shape of an unfamiliar code file: call it before reading the whole file.
Then run one Grep for the same name and reconcile the two: report the references the symbol tool found, and separately the text-only hits (comments, docs, strings, dynamic uses).

When not to call them.
- The task text for this call tells you to reason only from the input it gives you, or contains a line starting `[symbol tools: off`: call no symbol tool. The caller's limit wins over this section.
- The symbol server reads one tree: the one the lead activated. If its answer disagrees with what Read or Grep shows in the tree you were given (the file is missing, the line or body differs), it is on another tree. Stop using it for this task, answer from Read and Grep, and write `[symbol tools: unavailable - not on the target tree]`.

Fallback, and say so.
- The tools are not in your tool list, or a call returns an error: use Grep, Read and Glob for that target and write `[symbol tools: unavailable - <reason>]` once. Do not retry the same target. If the error names the active language servers, that file type is not covered: stop calling the symbol tools for every file of that type in this task. If it says the path is ignored, fall back for that file only; when a second file of the same type gets the same error, treat the type as not covered.
- A call returns an empty result: that is not evidence of absence. A search that names no file returns nothing, with no error, for every file type the server does not cover. Confirm with Grep and write `[symbol tools: empty for <target> - grep used]`.
- Report once: `symbol tools: used <n> calls` or `symbol tools: not used - <reason>`.
Where these lines go: in a free-text answer, write them as lines of the answer. When the output is bound to a schema, put them in a free-text field (note, evidence, detail, rationale, summary) of an item you are already returning. Never add a finding, issue or item only to carry them, and never change a verdict for them. If the schema has no such place, leave them out: the lead counts your tool calls from the run record.

## 핵심 역할 (3-5줄)
- 책임 1
- 책임 2
- 책임 3

## 통신 규칙 (Workflow)
1. 이 에이전트는 `workflows/*.js` 결정적 스크립트가 라운드를 소유한다 — P2P SendMessage 없음.
2. 발견은 구조화 출력(schema)으로 반환하고, Lead/스크립트가 통합한다.
3. 브리프 명시 채널이 에이전트 기본 지시보다 우선한다.

## 워크플로우
1. {first action}
2. {second action}
3. {third action}

## 결과 보고 형식
(출력 구조를 명시)
```

`## Symbol tools` 블록은 `tools:` 에 Serena 심볼 도구(`find_symbol` · `find_referencing_symbols` · `get_symbols_overview`)가 하나라도 있는 에이전트에만 넣고, 도구 전략 절 바로 아래에 글자 그대로 둔다 — 그 도구를 가진 에이전트는 모두 바이트까지 같은 블록을 쓴다. Serena 를 Secondary · Fallback 등급 줄로 따로 적지 않는다. 워커를 띄우기 전의 끔 신호 줄은 `modules/tool-status.md` § 워커 심볼 도구, 점검 낱말마다 Lead 가 할 일은 `modules/symbol-tools-audit.md` 가 정본이다.

## Description 작성 예시

```
BAD:  "Helps review code"
BAD:  "I am a code reviewer who checks quality"
GOOD: "아키텍처 리뷰 렌즈 — 설계 결정 · 레이어 위반 · 확장성 발견을 리뷰 스키마로 반환한다.
       fz 워크플로 내부 워커(review-live · peer-review) — 직접 쓰지 않는다."
GOOD: "교훈 큐레이터 — 지금 작업에 맞는 교훈 · 결정을 검증 상태와 출처를 붙여 반환한다.
       Lead 가 워크플로 밖에서 직접 부른다."
```

핵심: 반환물 한 줄, 호출 계약 한 줄 — 워크플로 내부 워커는 '직접 쓰지 않는다', Lead 가 직접 부르는 에이전트는 그 호출처를 적는다('내부 워커' 문구를 쓰지 않는다).

## Model Selection Guide

| Model | When to use | Examples |
|-------|------------|---------|
| opus | Primary Worker로서 핵심 산출물 생성 (설계, 코드) | plan-structure (plan teams), impl-correctness (code teams) |
| sonnet | 지원 역할 (비평, 검증, 탐색) | review-arch, review-quality, search-symbolic |
| inherit | 부모 컨텍스트에서 상속 | -- |

기본값은 sonnet이며, 특정 팀 구성에서 Primary Worker로 동작할 때 opus로 승격됩니다 (`modules/team-registry.md` 참조).

## Tool Restriction Patterns

| Pattern | tools 값 | Use case |
|---------|----------|----------|
| Read-only | `Read, Grep, Glob` | search-symbolic, review-quality |
| **Changeset producer** | `Read, Grep, Glob` + Serena **읽기** 도구 | **impl-correctness** — ⛔ 쓰기 도구 없음 |
| Pattern-restricted | `Bash(xcodebuild *)` | 특정 명령만 허용 |
| Team agent 제약 | MCP tools (Atlassian, XcodeBuild) | Lead-only, subagent 사용 불가 |

⛔ **구현 에이전트에 쓰기 도구를 주지 않는다** (2026-08-09, 외부 감사 ISSUE-013로 본 표가 정정됐다). 산출물은 **changeset JSON**이고 **적용은 Lead**다(`workflows/code-pair.js`) — 워커는 디스크에 닿을 필요가 없다. 근거: `guides/harness-engineering.md` "에이전트가 시도할 수 없는 것은 실패할 수 없다 — 런타임 체크가 아닌 스키마 수준 필터링" + "capability ≠ authorization". ⛔ 이전 판이 `Code agent | Read, Grep, Glob, Edit, Write, Bash | impl-correctness`로 제시해, 본 템플릿으로 에이전트를 새로 만들면 **제거된 capability가 되살아났다.**

## Naming Convention

글로벌 에이전트 이름은 `{domain}-{specialty}` 패턴을 따릅니다:

| Domain | Agents |
|--------|--------|
| search | search-symbolic, search-pattern |
| plan | plan-structure, plan-edge-case, plan-impact |
| implement (impl) | impl-correctness, impl-quality |
| review | review-arch, review-quality, review-correctness, review-counter |

전체 에이전트 목록: `modules/team-registry.md` 참조.

## Pre-completion Checklist

새 에이전트 파일 작성 후 확인하세요.

- [ ] description이 반환물 한 줄 + 호출 계약 한 줄인가?
- [ ] model이 역할에 맞는가 (sonnet for support, opus for primary)?
- [ ] tools가 최소한인가 (필요한 것만)?
- [ ] 반환 규칙(호출 워크플로 스키마가 정본 · enum 값 복사 금지) 포함?
- [ ] MCP 도구 전략이 4단계 모두 있는가 (Primary/Secondary/Fallback/Unavailable)?
- [ ] 워크플로우가 번호 매긴 단계로 되어 있는가?
- [ ] 결과 보고 형식이 명시되어 있는가?
- [ ] 공격적 언어("CRITICAL", "MUST ALWAYS") 없는가?
- [ ] `modules/team-registry.md`에 등록했는가?

---

## Verification

모든 에이전트는 다음 Verification Discipline 규약을 따른다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델/도구 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
