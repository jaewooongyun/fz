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

## 완료 게이트 (v4.25.0+)

작업이 끝났는지를 모델의 자기보고 대신 **실제로 돌아가는 명령**으로 판정한다.

### 어떻게 생겼나

`/fz-plan` 이 계획을 세우면 `{WORK_DIR}/gates/plan.md` 가 만들어진다.

```
# Gates: 시청내역 서버 재정비
ROOT: {WORK_DIR}
STATE: active
APPROVED: yes

- [ ] S1: 빌드가 통과한다
  CRITERION: 시뮬레이터 빌드가 성공해야 한다
  CHECK: xcodebuild -workspace app-iOS/tving.xcworkspace -scheme tving build
  EXPECT: BUILD SUCCEEDED
  CWD: {GIT_ROOT}
  APPROVED_ORACLE_HASH: 4e7e65bdc54c
  EVIDENCE: pending

- [ ] S2: 시트 마진이 48pt 다
  MANUAL: 시뮬레이터에서 마진을 눈으로 확인
  CRITERION_HASH: 37378c7a4cc3
  EVIDENCE: pending
```

`CHECK` 가 실제로 도는 명령이고 `EXPECT` 는 그 출력에 있어야 하는 문자열이다. **둘 다** 만족해야 통과다. 종료 코드만 보면 "실행됐다"만 증명하고, 출력만 보면 실패한 프로세스가 에러 메시지에 성공 토큰을 담고 있을 때 통과한다.

눈으로 봐야 하는 항목은 `MANUAL:` 로 적는다. 명령으로 억지로 판정하지 않는다.

### 어디서 발화하나

| 시점 | 하는 일 |
|------|--------|
| `/fz-plan` | 계획의 Step 에서 원장을 만들고, Codex 판정을 받아 확정 |
| `/fz-code` | Step 완료 선언 전에 그 Step 게이트만 실행. 실패하면 다음 Step 으로 안 간다 |
| `/fz-review` | 기록된 증거를 믿지 않고 다시 돌린다. 통과 못 하면 체크를 푼다 |
| 세션 종료 | 미충족 원장이 있으면 종료를 막는다 (hook 설치한 머신만) |
| `/fz-manage check` | 원장 상태를 보여준다. hook 없는 머신의 노출 경로 |

원장이 없는 세션에는 아무 영향이 없다. 게이트를 쓰지 않던 흐름은 그대로 돈다.

### 통과할 수 없을 때

게이트를 만족시킬 수 없으면 원장에 이렇게 적는다.

```
ABANDON: S3 시각 확인은 비대화형 세션에서 불가
```

그러면 통과로 처리되고 포기 사실이 원장에 남는다. 최종 보고에도 표면화된다. 조용히 사라지지 않는다.

세션 전체를 끄려면 환경변수를 쓴다.

```bash
FZ_GATES_OFF=1 claude
```

⛔ 이것은 **세션 단위**다. 원장의 `STATE` 는 바뀌지 않으므로 다음 세션에서 다시 판정한다.

### 직접 돌려보기

```bash
G="$(bash scripts/resolve-plugin-root.sh)/scripts/gate_check.py"

python3 "$G" --status  {WORK_DIR}/gates/plan.md   # 파싱만, 명령 미실행
python3 "$G" --only S1 {WORK_DIR}/gates/plan.md   # S1 게이트만 실행
python3 "$G" --reverify {WORK_DIR}/gates/plan.md  # 통과한 것도 다시 실행
python3 "$G" --confirm S2 {WORK_DIR}/gates/plan.md # MANUAL 확인 (터미널에서만)
python3 "$G" --discover .                          # 하위 원장 상태 요약
```

종료 코드는 네 갈래다.

| 코드 | 뜻 | 어떻게 읽나 |
|-----:|------|------------|
| 0 | 충족 | 통과 |
| 1 | 미충족 | 판정 결과다. 시간이 없었다는 것은 통과가 아니다 |
| 3 | 원장 계약 위반 | fz 가 만든 원장이 자기 문법을 어겼다. 평가 불가는 통과가 아니다 |
| 2 | 인프라 | python 부재나 파일시스템 오류. 세션 감금이 게이트 누락보다 나쁘다 |

### 세션 종료 차단 (선택 설치)

기계적 차단은 hook 을 설치한 머신에만 있다. 원장과 판정기, 그리고 위 배선 중 넷은 어디서나 돈다.

`examples/hooks.json.example` 의 `Stop` 항목을 `.claude/settings.json` 으로 복사하고 `{PLUGIN_ROOT}` 를 실제 경로로 바꾼다.

```bash
bash scripts/resolve-plugin-root.sh          # 경로 확인
python3 scripts/gate_stop_hook.py --self-test # 계약 검증 (14케이스)
```

원장 탐색은 세션 CWD 하위 깊이 3까지다. 워크트리에서 작업하고 원장이 리포 루트에 있으면 찾지 못하므로 경로를 명시한다.

```bash
export FZ_GATES_LEDGER=/path/to/ASD-1234/gates/plan.md
```

같은 상태로 두 번 막은 뒤에는 통과시킨다. 원장이 그대로면 같은 이유로 계속 막혀 세션이 끝나지 않기 때문이다.

### 원장이 지키는 것

증거에는 서명이 붙는다. 그 게이트의 명령, 종료 코드, 출력에 묶여 있어서 판정기가 다시 계산해 대조한다. 원장을 쓰는 것도 모델이므로 `- [x]` 로 바꾸고 통과 텍스트만 적는 경로를 막는다.

⛔ 암호학적 위조 방지는 아니다. 알고리즘이 공개돼 있어 작정하면 재계산할 수 있다. 막는 것은 실수로 생기는 통과다.

승인 도장(`APPROVED_ORACLE_HASH`)은 Codex 가 "이 `CHECK` 가 제목이 말하는 것을 재는가"를 판정한 뒤 `--finalize` 가 찍는다. 그 뒤 `CHECK`·`EXPECT`·`CWD`·`TIMEOUT`·`CRITERION`·제목 중 하나라도 바뀌면 실행이 거부된다.

상세는 `modules/gates.md` 를 본다.

---

## Architecture

```
fz-plugin/
├── .claude-plugin/  plugin.json + marketplace.json
├── skills/          21개 — /fz, /fz-plan, /fz-code, /fz-review, /fz-fix, /fz-modernize ...
├── agents/          13개 — plan-structure, impl-correctness, review-arch ...
├── workflows/       6개 — 네이티브 Workflow 결정적 스크립트 (discover-adversarial, plan-collaborative, code-pair ...)
├── modules/         42개 — gates(완료 게이트 SSOT), team-core, pipelines, cross-validation, lead-action-default, codex-strategy, memory-guide, fz-codex-bash-hygiene, fz-codex-subcommands-core/aux ...
│   └── patterns/    5개 — adversarial, collaborative, pair-programming ...
├── guides/          9개 — prompt-optimization, skill-authoring, harness-engineering, agent-team-guide, skill-testing, fable-model-guide, llm-references ...
├── codex-skills/    8개 — Codex 네이티브 스킬 + Authority 인용 + Memory Lesson inline (fz-reviewer, fz-architect ...)
├── schemas/         6개 — Codex JSON 응답 스키마 (review, verification, gate_verdict, peer_review ...)
├── scripts/         13개 — gate_check(완료 판정기) · gate_stop_hook(종료 차단) · lint 3 · codex-exec · health-check ...
├── tests/           fixtures/gates/ — 판정기 회귀 66케이스 (16범주, 기대 exit·산출물·시간·stdout·stderr)
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

### What's New (v4.25.0) — 완료 판정을 산문에서 exit code 로

완료 기준이 SKILL.md 산문 1,723줄에 적혀 있었고 그것을 검사하는 코드는 0줄이었다. 모델이 "다 했습니다"라고 말하면 그게 곧 완료였다.

이제 `/fz-plan` 이 계획의 Step 에서 원장을 만들고, `CHECK` 명령이 실제로 돌고 `EXPECT` 문자열이 출력에 있어야 통과한다. 다섯 지점에서 발화한다 — 계획 확정, Step 종료, 리뷰 재검증, 세션 종료 차단(hook 설치 시), health-check 노출. 통과할 수 없으면 `ABANDON:` 으로 흔적을 남기고 넘어간다.

⛔ **만드는 동안 열다섯 번 만난 실패가 하나 있었다: 코드는 있는데 발화하지 않는다.** 새 스키마를 세 문서가 요구하는데 넘기는 호출부가 없었고, 승인 도장을 대조하는 코드가 세 곳에 있는데 발급하는 코드가 없었고, Stop hook 의 차단 함수는 정확한데 `except BaseException` 이 자기 `sys.exit()` 을 삼켜 종료 코드가 늘 0이었다. 세 경우 다 문법이 정상이고 테스트도 통과했다. **한 번 실행해 보니** 드러났다.

두 번째는 테스트가 자기 이름의 축을 못 보는 것이었다(열 번). `writeback-sibling-edited` 는 이름이 "형제 편집"인데 `sed` 패턴이 자기 명령 줄에도 있어 자기를 고쳤다. 그래서 방어를 하나씩 지워 보고 어느 테스트가 실패하는지 확인하는 절차를 세웠다 — 전부 한꺼번에 지우면 총계만 보이고 "여섯 종 중 두 종만 관측된다"가 숨는다.

사용법은 [완료 게이트](#완료-게이트-v4250) 절을 본다.

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
