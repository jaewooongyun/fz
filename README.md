# fz

[![Release](https://img.shields.io/github/v/release/jaewooongyun/fz?label=latest&color=blue)](https://github.com/jaewooongyun/fz/releases/latest) [![License](https://img.shields.io/github/license/jaewooongyun/fz?color=green)](LICENSE) [![Changelog](https://img.shields.io/badge/changelog-md-lightgrey)](CHANGELOG.md)

AI 개발 워크플로우를 오케스트레이션하는 [Claude Code](https://code.claude.com/docs/en/overview) 플러그인이다.

자연어로 요청하면 복잡도를 평가해 스킬 파이프라인을 구성하고 필요하면 여러 에이전트를 붙여 실행한다. 계획, 구현, 리뷰, 커밋이 한 흐름으로 이어지고 단계마다 검증 게이트가 들어간다.

```bash
/fz "로그인 화면 크래시 버그 찾아줘"      # 탐색 → 수정
/fz "새 기능 계획하고 구현해줘" --team      # 계획 → 구현 (멀티에이전트)
/fz-review "내 코드 리뷰해줘"              # 개별 스킬 직접 실행
```

---

## 설치

```bash
claude plugin install fz --marketplace jaewooongyun/fz   # Claude Code 2.1.292+ 한 줄 설치
# 2.1.292 미만이면 위 줄 대신 아래 두 줄
claude plugin marketplace add jaewooongyun/fz   # 최초 1회
claude plugin install fz
claude plugin install fz-compact@fz-orchestrator  # 선택. bg 세션 로컬 마스킹 압축, 기본 꺼짐
claude plugin install fz-guard@fz-orchestrator    # 선택. Phase 4 승인 생략과 보호 경로 아래 Bash 를 막고, 알던 셸 함정은 경고한다

claude
> /fz "안녕"                                     # 응답하면 정상
```

프로젝트 루트에 `CLAUDE.md` 를 둔다. `## Architecture`, `## Build`, `## Code Conventions` 세 섹션이 있어야 하고 템플릿은 `templates/CLAUDE.md.template` 이다.

`python3` 3.9 이상과 `git` 이 필요하다. GPT 단계에는 `perl`(macOS 기본 포함)이, 점검(`/fz-manage check`)에는 `node` 가 더 필요하다. `perl` 이 없으면 GPT 단계만 빠지고, `node` 가 없으면 점검 일부가 돌지 못해 exit 2 로 끝난다.

설치하면 Stop 훅 하나가 켜진다(`hooks/hooks.json`). 서브에이전트를 쓴 세션이 끝날 때(fz 세션이 아니어도) 워커가 심볼 도구를 썼는지 세어 이 머신의 `${FZ_RUN_STATE:-~/.fz/runs}` 에만 기록하고, 의심스러우면 한 줄 알린다. 막지는 않으며 `FZ_MCP_SWEEP_OFF=1` 로 끈다. 미충족 게이트로 세션 종료를 막는 훅은 따로 등록한다(`docs/completion-gates.md`).

### 함께 쓰는 도구

fz 가 번들하는 MCP 는 Serena 하나고 나머지는 골라서 직접 등록한다. 빠진 도구가 있어도 fz 는 깨지지 않는다. 설치 명령과 없을 때 대신하는 방법, 설치 뒤 확인할 것은 [함께 쓰는 도구](docs/tools.md)에 있다.

| 도구 | 쓰는 곳 |
|------|------|
| Serena MCP | 심볼 탐색 |
| GPT CLI | 교차 검증 |
| SuperClaude | 리뷰 셋째 검증과 설명 · 조사 명령 |
| sequential-thinking | 구조화 분해 |
| Context7 MCP | 라이브러리 문서 조회 |
| pr-review-toolkit | fz-review 병렬 검토 |
| `gh` CLI | GitHub 조회와 PR |

### GPT 스킬 연결

GPT CLI 를 쓰면 GPT 역할 스킬을 심볼릭 링크로 연결한다. 링크가 없으면 review 모드 호출이 역할 스킬 없이 돈다.

```bash
bash "$(python3 -c 'import json,os;b=os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude");print(json.load(open(b+"/plugins/installed_plugins.json"))["plugins"]["fz@fz-orchestrator"][0]["installPath"])')/scripts/setup-gpt-skills.sh"
```

로컬 체크아웃이면 그 플러그인 루트에서 `bash scripts/setup-gpt-skills.sh` 를 실행한다. ⛔ 캐시 폴더를 glob 이나 `sort -V` 로 고르지 않는다. 갱신 뒤 캐시에 남은 옛 판 폴더가 골라질 수 있다.

GPT 모델과 effort 는 세션에서 고르고, 고르지 않으면 `~/.codex/config.toml` 값을 쓴다(정본 `modules/gpt-strategy.md` § 모델·effort 선택).

### 업데이트

```bash
claude plugin marketplace update fz-orchestrator
claude plugin update fz@fz-orchestrator
claude plugin update fz-compact@fz-orchestrator   # fz-compact 를 설치했을 때만
claude plugin update fz-guard@fz-orchestrator     # fz-guard 를 설치했을 때만
```

⛔ 접미사 없이 `claude plugin update fz` 를 부르면 `Plugin "fz" not found` 로 실패한다. 설치된 이름은 `fz@fz-orchestrator` 다.

업데이트는 GPT 스킬 연결을 다시 하지 않는다. 위 연결 명령에 `--check` 를 붙이면 지울 옛 링크를 `stale:` 줄로 보여 주고(exit 1), 인자 없이 다시 실행하면 정리한다. 옛 판 캐시가 이미 지워져 끊긴 링크는 `unknown:` 줄로만 나오고 남는다. 이 판이 걷은 역할 스킬 링크 둘은 아래 명령으로 지운다.

```bash
find "${CODEX_HOME:-$HOME/.codex}/skills" -maxdepth 1 -type l \( -name fz-fixer -o -name fz-searcher \) -print -delete
```

---

## Skills

사용자가 직접 부르는 스킬은 19개다. 나머지 3개(`arch-critic` · `code-auditor` · `fz-new-file`)는 다른 스킬이 안에서 쓴다.

| 카테고리 | 스킬 | 설명 |
|---------|------|------|
| **오케스트레이터** | `/fz` | 자연어 요청을 파이프라인으로 자동 구성 |
| **개발** | `/fz-plan` | 요구사항 분석, 영향 범위, RTM |
| | `/fz-code` | 계획에 따른 점진적 구현과 빌드 검증 |
| | `/fz-fix` | 버그 수정 (4-Phase 디버깅) |
| | `/fz-review` | 3중 검증 (Claude + GPT + 셋째 검증) |
| | `/fz-commit`, `/fz-pr` | 커밋, PR |
| | `/fz-rebase` | 롱텀 브랜치 리베이스와 양방향 유실 검사 |
| **탐색** | `/fz-discover` | 풍경 탐색과 경로 매핑 |
| | `/fz-search` | 코드 탐색 (symbolic, pattern) |
| | `/fz-explain` | 코드·구조 설명 |
| **검증** | `/fz-gpt` | GPT CLI 교차 검증 |
| | `/fz-peer-review` | 동료 PR 리뷰 (9개 관점) |
| **문서/시스템** | `/fz-memory` | 메모리 관리 |
| | `/fz-skill` | 스킬 관리와 문서 작성(`write`) |
| | `/fz-manage` | 인벤토리와 건강 체크 |
| | `/fz-modernize` | 가이드 최신화 |
| **보조** | `/fz-recording`, `/fz-pr-digest` | 회의록, PR 요약 |

## Pipelines (주요)

| 파이프라인 | 트리거 | 체인 |
|-----------|-------|------|
| **quick-fix** | "타임아웃 변경" | fz-fix |
| **bug-hunt** | "크래시 버그 찾아줘" | fz-search → fz-fix |
| **plan-to-code** | "계획하고 구현" | fz-plan → fz-code |
| **code-to-review** | "구현하고 리뷰" | fz-code → fz-review |
| **review-to-ship** | "리뷰하고 커밋" | fz-review → fz-commit → fz-pr |
| **full-cycle** | "처음부터 끝까지" | fz-plan → fz-code → fz-review → fz-commit → fz-pr |

빌드와 GPT 교차 검증 게이트는 파이프라인마다 자동으로 들어가서 체인 칸에서는 뺐다. 전체 19개와 게이트 위치는 `modules/pipelines.md` 에 있다.

---

## 문서

| 문서 | 내용 |
|------|------|
| [완료 게이트](docs/completion-gates.md) | 작업 완료를 명령으로 판정하는 계층과 세션 종료 차단 |
| [함께 쓰는 도구](docs/tools.md) | 도구별 설치 명령, 없을 때 대신하는 방법, 설치 뒤 확인할 것 |
| [아키텍처](docs/architecture.md) | 디렉토리 구조, 오케스트레이션 흐름, 에이전트 구성 |
| [개발과 릴리즈](docs/development.md) | fz 자체를 수정할 때의 절차 |
| [CHANGELOG](CHANGELOG.md) · [릴리즈 노트](docs/releases/) | 판별 변경 이력. CHANGELOG 는 맨 위 판만 본문을 둔다 |

스킬, 에이전트, 모듈을 만들거나 고칠 때는 `guides/` 를 본다. 시작점은 [`skill-authoring.md`](guides/skill-authoring.md) 와 [`agent-team-guide.md`](guides/agent-team-guide.md) 다.

---

## What's New — v0.58.0

fz-guard 가 알던 셸 함정(검색 명령 뒤 `| head` · 빈 글롭 · `cd X &&`)을 경고한다. 계획 · 리뷰 검사와 출하 대조가 대조값 · 인용 줄 · 출하 커밋을 직접 잰다.
→ [CHANGELOG](CHANGELOG.md)
