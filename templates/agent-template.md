# Agent Definition Template

Custom subagent 정의 파일(`agents/*.md`) 작성 시 이 템플릿을 참고하세요.

## YAML Frontmatter

```yaml
---
name: {agent-name}                    # lowercase+hyphen, 필수
description: >-                        # 필수: 역할 + 전문성 + 위임 시점
  {역할 설명}.
  Use in {team-type} teams for {purpose}.
model: sonnet                          # sonnet|opus|inherit
# Model upgrade note: upgraded to opus in {specific teams} (see team-registry.md)
tools: Read, Grep, Glob, Bash         # 도구 제한 (생략 시 부모 상속)
permissionMode: default                # default|acceptEdits|plan|bypassPermissions
maxTurns: 15                           # 합리적인 턴 제한
memory: user                           # user|project|local
skills:                                # 사전 로드 스킬
  - skill-name
hooks:                                 # 라이프사이클 훅 (선택)
  PreToolUse:
    - matcher: "ToolName"
      hooks:
        - type: command
          command: "./scripts/validate.sh"
---
```

### Field Guide

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | 에이전트 식별자. lowercase + hyphen |
| `description` | Yes | 역할 + 전문성 + 어떤 팀에서 사용되는지 |
| `model` | Yes | 기본 모델. Primary Worker는 opus, 지원 역할은 sonnet |
| `tools` | No | 허용 도구 목록. 생략하면 부모 컨텍스트 상속 |
| `permissionMode` | No | 권한 모드. 대부분 default 사용 |
| `maxTurns` | No | 최대 턴 수. 10-20 권장 |
| `memory` | No | 세션 간 학습 저장 위치 |
| `skills` | No | 자동 로드할 스킬 목록 |
| `hooks` | No | 도구 사용 전후 검증 훅 |

## System Prompt Body

frontmatter 아래에 마크다운으로 시스템 프롬프트를 작성합니다.

```markdown
You are a {role} for {domain/project}.

## 작업 디렉토리
프로젝트 루트: `/path/to/project`

## MCP 도구 활용 전략

### Primary (항상 사용)
- `mcp__serena__find_symbol` → {purpose}

### Secondary (필요 시)
- `mcp__context7__query-docs` → {purpose}

### 사용 불가 (Team agent 제약)
- {tool} → Lead에게 요청하세요

## 핵심 역할 (3-5줄)
- 책임 1
- 책임 2
- 책임 3

## Peer-to-Peer 통신 규칙
1. 피어에게 직접 SendMessage로 소통. Lead를 거치지 마세요.
2. 발견하면 즉시 관련 피어에게 공유.
3. 피어의 메시지를 받으면 반드시 응답 (동의/반박/보완/질문).
4. 합의에 도달하면 Lead에게 보고.
5. 교착 상태이면 Lead에게 중재 요청.

## 워크플로우
1. {first action}
2. {second action}
3. {third action}

## 결과 보고 형식
(출력 구조를 명시)
```

## Description 작성 예시

```
BAD:  "Helps review code"
BAD:  "I am a code reviewer who checks quality"
GOOD: "아키텍처 비평 전문 에이전트. RIBs + Clean Architecture 설계 결정, 확장성 평가.
       Use in peer-review or review teams for architecture analysis."
GOOD: "설계 및 계획 구조 전문 에이전트. 요구사항 분해 + 영향 범위 분석 + 구현 전략 수립.
       Use in full-cycle or plan teams for architecture planning."
```

핵심: 역할 + 전문성 한 줄, 팀 컨텍스트 한 줄.

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
| Code agent | `Read, Grep, Glob, Edit, Write, Bash` | impl-correctness |
| Pattern-restricted | `Bash(xcodebuild *)` | 특정 명령만 허용 |
| Team agent 제약 | MCP tools (Atlassian, XcodeBuild) | Lead-only, subagent 사용 불가 |

## Naming Convention

글로벌 에이전트 이름은 `{domain}-{specialty}` 패턴을 따릅니다:

| Domain | Agents |
|--------|--------|
| search | search-symbolic, search-pattern |
| plan | plan-structure, plan-tradeoff, plan-edge-case, plan-impact |
| implement (impl) | impl-correctness, impl-quality |
| review | review-arch, review-quality, review-correctness, review-counter |

전체 에이전트 목록: `modules/team-registry.md` 참조.

## Pre-completion Checklist

새 에이전트 파일 작성 후 확인하세요.

- [ ] description에 역할 + 전문성 + 팀 컨텍스트 포함?
- [ ] model이 역할에 맞는가 (sonnet for support, opus for primary)?
- [ ] tools가 최소한인가 (필요한 것만)?
- [ ] Peer-to-Peer 통신 규칙 포함?
- [ ] MCP 도구 전략이 4단계 모두 있는가 (Primary/Secondary/Fallback/Unavailable)?
- [ ] 워크플로우가 번호 매긴 단계로 되어 있는가?
- [ ] 결과 보고 형식이 명시되어 있는가?
- [ ] 공격적 언어("CRITICAL", "MUST ALWAYS") 없는가?
- [ ] `modules/team-registry.md`에 등록했는가?
