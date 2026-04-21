# CLAUDE.md — fz Plugin

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

## Directory Structure
- `skills/` — 21개 fz 스킬 (SKILL.md)
- `agents/` — 13개 fz 에이전트
- `modules/` — 공유 모듈 (20개 + patterns/)
- `guides/` — 가이드 문서 (7개)
- `templates/` — 스킬/에이전트/모듈/CLAUDE.md 템플릿
- `codex-skills/` — Codex 네이티브 스킬 (8개)
- `schemas/` — Codex JSON 스키마 (5개)
- `.claude-plugin/` — plugin.json + marketplace.json

## Verification Discipline (v3.11+)

모든 스킬/에이전트는 다음 규약을 따른다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
- T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 후 계속

상세: `modules/uncertainty-verification.md` (Default-Deny), `modules/system-reminders.md` (T6/T7), `modules/lead-reasoning.md §1.5` (Speculation-to-Fact Fallacy), `templates/agent-template.md` + `templates/skill-template.md` (자동 상속 섹션).

## Opus 4.7 Adaptation

- **GA**: 2026-04-16
- **Tokenizer**: 1.00-1.35x 증가 (Korean 실측 [미검증: count_tokens 측정 필요])
- **Behavior**: "more literal instruction following" — overtriggering 위험 증가
- **Context window**: 1M 유지 (safety net 원칙, Intelligence Degradation + Context Length Hurts 논문 근거)

상세: `modules/context-artifacts.md` (1M context 정책), `guides/harness-engineering.md` §1.3 (세대 전환 테이블), `guides/prompt-optimization.md` 원칙 8 (literal interpretation 대응).

## Agent Teams Environment Flag

TeamCreate 사용 스킬 실행 시 환경 변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정 필수 (Claude Code v2.1.32+). 미설정 시 TeamCreate 호출이 실패한다.

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

상세: `guides/agent-team-guide.md` §8 (공식 사양, hooks 연계, 권장 teammate 수).
