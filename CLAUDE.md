# CLAUDE.md — fz Plugin

> **Sources (last audited: 2026-07-25 — 모델 사실 축):** `guides/llm-references.md` §1 정본 대조 완료. 그 외 인용은 개별 `[verified:]` 태그 참조. 최신성 검사: `python3 scripts/lint_doc_freshness.py`

## Build
- 빌드 없음 (마크다운 프로젝트)
- 검증: `claude plugin validate .`

## Git Workflow

### 릴리즈 (변경사항 배포)
1. `.claude-plugin/plugin.json` version bump — **변경 성격에 따른다**
   - `[MINOR]` = 새 검사·스킬·모듈 추가 등 기능 증가 (실측: v4.15.0~v4.23.0 전부 MINOR)
   - `[PATCH]` = 배선 복구·문구 정정 등 (예: v4.23.1)
   - ⛔ 구판은 "semver patch: +0.0.1" 고정이라 적었으나 **실제 이력과 어긋났다** (2026-08-20 실측 정정)
2. `.claude-plugin/marketplace.json` version bump (동일 버전)
3. `git commit` + `git push origin main`
4. `git tag vX.Y.Z` + `git push origin --tags`
5. (선택) `gh release create vX.Y.Z`

> **version bump 누락 시 `plugin update`가 "already at latest"로 스킵됨. 반드시 올릴 것.**

### 사용자 업데이트
```bash
claude plugin update fz@fz-orchestrator
```

### Pre-commit Hooks (H1 원칙 — deterministic check)

본 repo는 `.githooks/pre-commit`으로 user-specific 절대 경로 commit을 차단한다.

**최초 1회 등록**:
```bash
bash scripts/setup-hooks.sh
```

이 명령은 `git config core.hooksPath .githooks`를 설정하여 hook이 활성화된다. clone 후 사용자마다 1회 실행 필요.

**차단 패턴**: `/Users/{user}/`, `~/dev/{user}/`
**In-scope**: README.md, CLAUDE.md, skills/, agents/, modules/, gpt-skills/, schemas/, templates/, guides/, .claude-plugin/
**예외**: CHANGELOG.md, docs/releases/ (historical reference 보존)
**검사 범위**: staged diff의 추가된 라인만 (기존 잔존 reference 무시)

**Bypass** (정당 사유 시): `git commit --no-verify` (권장 안 함, commit message에 사유 명시)

**근거**: v4.5.0 release 시 README/CHANGELOG/SKILL에 user-specific 절대 경로 노출 → v4.5.1로 retroactive cleanup 후 재발 방지 mechanism 추가 (v4.6.0).

## Directory Structure
> ⛔ 아래 카운트는 `scripts/lint_contracts.py` **#N2가 실측과 대조**한다 — 손으로 세지 말고 lint를 돌려라 (2026-08-09까지 modules 20/guides 7로 stale했다).
> ⛔ **형식 고정**: `` - `dir/` — 설명 (N개) `` — #N2는 백틱 경로 뒤의 `(N개` 를 찾는다. 형식이 다르면 **그 카테고리가 조용히 검사에서 빠진다** (2026-08-09 감사 ISSUE-002: `agents/`는 괄호 없어 미검사, `workflows/`는 선언 자체가 없었다).
- `skills/` — fz 스킬 SKILL.md (22개)
- `agents/` — fz 에이전트 (13개)
- `modules/` — 공유 모듈 (45개). ⛔ **실행 절차만** 둔다 — 라운드 의미론의 *역사적 출처*(TEAM 사료 6종)는 2026-09-21 `docs/history/` 로 옮겼다가(B9/S13) 2026-09-25 삭제했다(결정: `modules/promotion-ledger.md` § TEAM 일몰). 사료를 실행 절차와 같은 자리에 두면 읽는 사람이 절차로 오독한다
- `guides/` — 가이드 문서 (9개)
- `workflows/` — 결정적 멀티에이전트 스크립트 (8개)
- `templates/` — 스킬/에이전트/모듈/CLAUDE.md 템플릿
- `gpt-skills/` — GPT 네이티브 스킬 (8개)
- `schemas/` — GPT JSON 스키마 (6개)
- `scripts/` — lint·설치·호출·검증·계측 스크립트 (42개). ⛔ diff 라인 접두사(`+`/`-`)로 판정하는 새 파일은 `# diff-parse: hunk-state | not-a-diff | waived` 선언 1줄이 없으면 `health-check` 가 막는다 (`lint_diff_parsers.py` — hunk 안팎에서 접두사 뜻이 달라 같은 결함이 4회 재발했다). ⛔ `setup-gpt-skills.sh`는 **load-bearing** — `~/.codex/skills/` 심볼릭이 `get_gpt_skill_path()` Tier 2a를 성립시킨다. ⛔ gpt 호출은 `gpt-exec.sh` 경유 의무 (`modules/fz-gpt-bash-hygiene.md` §8) · `FZ_PLUGIN_ROOT`는 `resolve-plugin-root.sh`로 해석 (Tier 2b 전제)
- `.claude-plugin/` — plugin.json + marketplace.json

## Verification Discipline (v3.11+)

모든 스킬/에이전트는 다음 규약을 따른다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
- T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 후 계속

상세: `modules/uncertainty-verification.md` (Default-Deny), `modules/system-reminders.md` (T6/T7), `modules/lead-reasoning.md §1.5` (Speculation-to-Fact Fallacy), `templates/agent-template.md` + `templates/skill-template.md` (자동 상속 섹션).

## Opus 5.5 Adaptation (현행 기본 모델)

- **GA**: 2026-09-22, `claude-opus-5-5`. **$4/$20**(캐시 읽기 $0.20) — Opus 5($5/$25)보다 낮다 [verified: platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5]
- **Tokenizer**: Opus 5 기준 — Opus 4.7 도입분과 동일 → 4.7/4.8 대비 토큰 수 거의 불변. (pre-4.7 대비 1.00-1.35x 증가는 유지, fz 자체 실측 미완료) — 5.5 공식 진술 미확인 [미검증: 5.5 tokenizer 진술 없음 · count_tokens 측정 필요]
- **Breaking 4** (정본 `guides/llm-references.md` whats-new-opus-5-5 행): ① **thinking 상시 ON — 끄기 불가**: `thinking:{"type":"disabled"}`·manual `budget_tokens` 는 effort 와 무관하게 **400** (Opus 5 는 effort ≤ `high` 에서 끌 수 있었다) — `max_tokens`는 thinking+응답 **합산** 하드캡이라 타이트한 값은 **응답 절단** 위험 ② forced `tool_choice`(`any`·`tool`) → **400** — `auto` + strict tool use 또는 structured outputs 로 대체 ③ thinking block 이 모델·대화 prefix 에 묶인다(prefix 를 바꿔 재생하면 400) ④ `computer_20251124` 거부. 동작 변화: 도구 호출 사이 진행 텍스트가 `text` 가 아니라 **progress-update `thinking` 블록**으로 온다 — 기본 `display: "omitted"` 에서는 스트리밍 UI 가 조용해진다 [verified: whats-new-opus-5-5]
- **effort**: 기본 **`medium`**(Opus 5 는 `high`) + **같은 effort 에서 사고량 증가**(`xhigh`·`max` 에서 가장 크다) [verified: whats-new-opus-5-5]. 공식은 이전 모델 값 재사용 대신 **fresh sweep** 을 권한다 — fz 는 워크플로 콜 명시 `xhigh` 유지(사용자 결정 2026-09-25, 하향 sweep 종결) [verified: platform.claude.com/docs/en/build-with-claude/effort]
- **Behavior** [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5]: **자체검증 내장 → 검증 지시 삭제**(over-verification) / **subagent 위임 과다 → 캡**(4.8과 역방향) / 응답·산출물 장문화 → **길이는 프롬프트로**(effort로 안 됨) / 스코프 확장·자기정정 서술 과다 → 명시 제약
- **Behavior (5.5 — 위 Opus 5 패턴 상속)**: "Existing Claude Opus 5 prompts should perform well without changes, and the patterns in Prompting Claude Opus 5 remain a reasonable starting point." 보강 3가지: **elapsed 시간 신호**(매 메시지 끝에 경과 시간 1줄) / text-only 턴 종료는 완료 증거가 아니라 **보고** / **premature stopping** 대응 자동 continuation 은 같은 작업에 **2~3회 상한** [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5]. ⛔ 5.5 페이지에 subagent 캡 절이 없는 것은 위 캡의 폐기 근거가 아니다(상속)
- **Context window**: 1M 유지 (기본값이자 최대값). safety net 원칙, Intelligence Degradation + Context Length Hurts 논문 근거

상세: `guides/llm-references.md` §1.2·§5 (정본), `modules/context-artifacts.md` (1M context 정책), `guides/harness-engineering.md` §1.3 (세대 전환 테이블), `guides/prompt-optimization.md` 원칙 8 (literal interpretation 대응), `guides/model-guide.md` (Fable 5 대비).

## Agent Teams Environment Flag — ⛔ 현행 경로에 불필요 (역사적 기록)

⛔ **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`을 설정하지 말 것.** 이 플래그는 `TeamCreate` 경로 전용이고, **`TeamCreate`는 Claude Code v2.1.178부터 부재**하다. 멀티에이전트 실행은 v4.22.0(Wave 4)에서 `workflows/*.js` 결정적 Workflow로 전면 이관됐다 — Workflow 도구는 이 플래그를 요구하지 않는다.

- 팀 모드 정본: `guides/skill-authoring.md` §12 (Workflow 규약 + 실패 복구 사다리 L1~L4)
- 역사적 사양(TEAM P2P 시절): `guides/agent-team-guide.md` §8 — ⛔ 실행 절차로 참조하지 않는다

> 정정 근거(2026-08-09 외부 감사 ISSUE-011): 본 절이 "설정 필수"라 지시하는 동안 같은 리포가 `TeamCreate` 부재를 선언하고 있었다 — **런타임 진입 문서가 존재하지 않는 실행 경로를 활성화하라고 지시**하는 모순이었다.
