# CLAUDE.md — fz Plugin

> **Sources (last audited: 2026-07-25 — 모델 사실 축):** `guides/llm-references.md` §1 정본 대조 완료. 그 외 인용은 개별 `[verified:]` 태그 참조. 최신성 검사: `python3 scripts/lint_doc_freshness.py`

## Build
- 빌드 없음 (마크다운 프로젝트)
- 검증: `claude plugin validate .`

## Git Workflow

### 릴리즈 (변경사항 배포)
1. `.claude-plugin/plugin.json` version bump (semver patch: +0.0.1)
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
**In-scope**: README.md, CLAUDE.md, skills/, agents/, modules/, codex-skills/, schemas/, templates/, guides/, .claude-plugin/
**예외**: CHANGELOG.md, docs/releases/ (historical reference 보존)
**검사 범위**: staged diff의 추가된 라인만 (기존 잔존 reference 무시)

**Bypass** (정당 사유 시): `git commit --no-verify` (권장 안 함, commit message에 사유 명시)

**근거**: v4.5.0 release 시 README/CHANGELOG/SKILL에 user-specific 절대 경로 노출 → v4.5.1로 retroactive cleanup 후 재발 방지 mechanism 추가 (v4.6.0).

## Directory Structure
> ⛔ 아래 카운트는 `scripts/lint_contracts.py` **#N2가 실측과 대조**한다 — 손으로 세지 말고 lint를 돌려라 (2026-08-09까지 modules 20/guides 7로 stale했다).
> ⛔ **형식 고정**: `` - `dir/` — 설명 (N개) `` — #N2는 백틱 경로 뒤의 `(N개` 를 찾는다. 형식이 다르면 **그 카테고리가 조용히 검사에서 빠진다** (2026-08-09 감사 ISSUE-002: `agents/`는 괄호 없어 미검사, `workflows/`는 선언 자체가 없었다).
- `skills/` — fz 스킬 SKILL.md (21개)
- `agents/` — fz 에이전트 (13개)
- `modules/` — 공유 모듈 (46개 — 루트 41 + patterns/ 5)
- `guides/` — 가이드 문서 (9개)
- `workflows/` — 결정적 멀티에이전트 스크립트 (6개)
- `templates/` — 스킬/에이전트/모듈/CLAUDE.md 템플릿
- `codex-skills/` — Codex 네이티브 스킬 (8개)
- `schemas/` — Codex JSON 스키마 (5개)
- `scripts/` — lint·설치·호출·검증 스크립트 (10개). ⛔ `setup-codex-skills.sh`는 **load-bearing** — `~/.codex/skills/` 심볼릭이 `get_codex_skill_path()` Tier 2a를 성립시킨다. ⛔ codex 호출은 `codex-exec.sh` 경유 의무 (`modules/fz-codex-bash-hygiene.md` §8) · `FZ_PLUGIN_ROOT`는 `resolve-plugin-root.sh`로 해석 (Tier 2b 전제)
- `.claude-plugin/` — plugin.json + marketplace.json

## Verification Discipline (v3.11+)

모든 스킬/에이전트는 다음 규약을 따른다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
- T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 후 계속

상세: `modules/uncertainty-verification.md` (Default-Deny), `modules/system-reminders.md` (T6/T7), `modules/lead-reasoning.md §1.5` (Speculation-to-Fact Fallacy), `templates/agent-template.md` + `templates/skill-template.md` (자동 상속 섹션).

## Opus 5 Adaptation (현행 기본 모델)

- **GA**: 2026-07-24, `claude-opus-5`. **$5/$25 = Opus 4.8과 동일** [verified: platform.claude.com/docs/en/about-claude/models/whats-new-opus-5]
- **Tokenizer**: Opus 4.7 도입분과 동일 → 4.7/4.8 대비 토큰 수 거의 불변. (pre-4.7 대비 1.00-1.35x 증가는 유지, fz 자체 실측 미완료) [미검증: count_tokens 측정 필요]
- **Breaking 2**: ① **thinking 기본 ON** (4.8은 생략 시 OFF) — `max_tokens`는 thinking+응답 **합산** 하드캡이라 4.8 기준 타이트한 값은 **응답 절단** 위험 ② `thinking:{"type":"disabled"}`는 **effort ≤ `high`에서만**, `xhigh`/`max`와 조합 시 **400**
- **effort**: 출발점 **`high`(기본)**, **`low`/`medium`이 비용·지연의 1차 레버**, demanding coding/agentic만 `xhigh`. ⛔ 이전 모델 effort 값 재사용 금지 → **fresh sweep** [verified: platform.claude.com/docs/en/build-with-claude/effort]
- **Behavior** [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5]: **자체검증 내장 → 검증 지시 삭제**(over-verification) / **subagent 위임 과다 → 캡**(4.8과 역방향) / 응답·산출물 장문화 → **길이는 프롬프트로**(effort로 안 됨) / 스코프 확장·자기정정 서술 과다 → 명시 제약
- **Context window**: 1M 유지 (기본값이자 최대값). safety net 원칙, Intelligence Degradation + Context Length Hurts 논문 근거

상세: `guides/llm-references.md` §1.2·§5 (정본), `modules/context-artifacts.md` (1M context 정책), `guides/harness-engineering.md` §1.3 (세대 전환 테이블), `guides/prompt-optimization.md` 원칙 8 (literal interpretation 대응), `guides/fable-model-guide.md` (Fable 5 대비).

## Agent Teams Environment Flag — ⛔ 현행 경로에 불필요 (역사적 기록)

⛔ **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`을 설정하지 말 것.** 이 플래그는 `TeamCreate` 경로 전용이고, **`TeamCreate`는 Claude Code v2.1.178부터 부재**하다. 멀티에이전트 실행은 v4.22.0(Wave 4)에서 `workflows/*.js` 결정적 Workflow로 전면 이관됐다 — Workflow 도구는 이 플래그를 요구하지 않는다.

- 팀 모드 정본: `guides/skill-authoring.md` §12 (Workflow 규약 + 실패 복구 사다리 L1~L4)
- 역사적 사양(TEAM P2P 시절): `guides/agent-team-guide.md` §8 — ⛔ 실행 절차로 참조하지 않는다

> 정정 근거(2026-08-09 외부 감사 ISSUE-011): 본 절이 "설정 필수"라 지시하는 동안 같은 리포가 `TeamCreate` 부재를 선언하고 있었다 — **런타임 진입 문서가 존재하지 않는 실행 경로를 활성화하라고 지시**하는 모순이었다.
