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
