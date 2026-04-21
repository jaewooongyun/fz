# RELEASE NOTES v4.0.0 — V.D. 4-way Chain 아키텍처 + 생태계 정합성

> Release Date: 2026-04-21
> Previous: v3.11.0 (2026-04-20)
> Bump Type: **MAJOR** (Breaking Changes — 레이어 정의 변경 + 에이전트/템플릿 구조 변경)

---

## 🎯 핵심 요약

v3.11.0에서 도입한 **Verification Discipline**을 생태계 전체에 체계적으로 확산하여 **4-way Chain 아키텍처**로 완성. 3-Model 9 검증 라운드를 거친 정합성 감사로 22 Gap을 해소.

단순 기능 추가가 아닌 **생태계 아키텍처 전환**:
- Brain/Hands 레이어 정의 breaking change
- 12 agents + 2 templates + 9 skills 구조 변경
- V.D. 체인이 단일 선형 → 4-way 독립 체인으로 재설계

---

## 🏗 V.D. 4-way Chain 아키텍처

v3.11에서는 "uncertainty-verification.md의 원칙"만 있었고, 체인 구조는 개별 skill에 분산돼 있었습니다. v4.0에서는 4개 독립 체인으로 명시화 + 재발 방지 메커니즘 추가.

```
① 기본 fail-closed:  uncertainty-verification → fz-plan / fz-code
                    (기존 — BEC fail-closed [verified] 태그 게이트)

② 보조 micro-eval:   fz-codex micro-eval → needs_verification → Default-Deny
                    (의미론적 결합 신설 — needs_verification ⇔ Default-Deny 동의어)

③ TEAM 주입:         system-reminders → team-core → fz/SKILL.md Task Brief → agents
                    (TEAM boot 시 T6/T7 트리거 자동 주입, templates/ 자동 상속)

④ 운영 피드백:       Phase 4.5 측정 → experiment-log.md §5.4 canonical sink
                    (5 세션 누적 → B1/B2 진입 판정)
```

**한 곳만 깨져도 무력화되는 5-link 인프라가 다층 방어로 배치.**

---

## ⚠️ Breaking Changes

### 1. Brain/Hands ↔ Lead/Teammate 레이어 경계 정정

**Before (v3.11 이하)**: `modules/team-core.md` L110-118 + `guides/prompt-optimization.md` L608-616이 다음 1:1 매핑 유지:

```
| Brain | 추론 + 계획 + 판단 | Lead (오케스트레이터) |
| Hands | 도구 실행 + 코드 수정 | Primary/Supporting 에이전트 |
```

**After (v4.0)**: 1:1 매핑 테이블 **제거**. Session 계층 관리 전략만 유지 + 경고 박스 추가:

```
⛔ Brain/Hands(infrastructure)와 Lead/Teammate(application)는 서로 다른 레이어. 혼용 금지.
— Brain/Hands: Anthropic "many brains, many hands" 인프라 추상화
— Lead/Teammate: fz의 TeamCreate + Task(N) 애플리케이션 역할 협업 패턴
```

**영향**: 에이전트 설계자가 두 레이어 혼동 방지. `guides/harness-engineering.md §1.3` 참조로 상세 구분.

### 2. agents/ 12개 파일 구조 변경

모든 에이전트 (memory-curator 제외) 하단에 `## Verification` 섹션 자동 추가.

```markdown
## Verification

모든 에이전트는 다음 Verification Discipline 규약을 따른다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델/도구 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
- T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 후 계속

관련 modules: modules/uncertainty-verification.md, modules/system-reminders.md, modules/lead-reasoning.md §1.5
```

**영향**: 에이전트 프롬프트가 VD 규약을 자동 인지. 과거에는 modules 참조만 있었고 규약 자체 전달 경로가 없었음.

### 3. templates/ 자동 상속 (재발 방지 메커니즘)

`templates/agent-template.md` + `templates/skill-template.md`에 `## Verification` 섹션 + skill-template에 `## If TeamCreate is used` 조건부 체크리스트 추가.

**영향**: 신규 에이전트/스킬 생성 시 VD 규약 + env flag 전제조건이 자동 상속. 과거 v3.11의 "12 agents 수동 수정"이 재발하지 않도록 구조적 방어.

### 4. 9 Skills Prerequisites 필수

TeamCreate 사용 모든 skills에 `## Prerequisites` 섹션 필수:

- `/fz`, `/fz-plan`, `/fz-code`, `/fz-discover`, `/fz-fix`, `/fz-review`, `/fz-peer-review`, `/fz-search`, `/fz-pr-digest`

```markdown
## Prerequisites

- TEAM 모드 사용 시 환경 변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정 필수 (미설정 시 TeamCreate 실패)
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)
```

**영향**: TEAM 모드 실패의 환경 요인(env flag 미설정)을 사용 시점에 즉시 인지. 과거에는 `guides/agent-team-guide.md`에만 명시되어 있어 간접 경로.

---

## ✨ New Features

### 새 모듈 섹션

- **`modules/cross-validation.md`**:
  - `## Follow-up Re-audit Gate (Phase B1/B2 활성 시)` — T7 트리거 연계 + `${CLAUDE_PROJECT_DIR}/memory/` 절대 변수 경로 단일 정책
  - `### micro-eval 호출 트리거 (공통)` — Claim-Type 라우팅 호출 조건 명시
  - MAR (arxiv 2512.20845) + VeriGuard dual-stage verification 이론 근거 교차 인용

- **`modules/memory-guide.md`**:
  - `## Claude Memory tool과의 관계` — fz L1 auto memory vs Anthropic client-side Memory tool 구분

- **`modules/team-core.md`**:
  - 팀 생성 절차에 `### Verification Discipline 트리거 주입 (TEAM boot)` 섹션 신설 — T6/T7 자동 전파

- **`CLAUDE.md` (root)**:
  - `## Verification Discipline` / `## Opus 4.7 Adaptation` / `## Agent Teams Environment Flag` 3섹션 추가 (개발자 온보딩)

- **`CHANGELOG.md`**:
  - `## Retired Citation Policy` 섹션 — active citations 8편 + retired citations (ICLR MAD, MAST) 정책 명시

### Progressive Disclosure 준수

- `skills/fz-codex/SKILL.md` 541줄 → 498줄 (≤500 기준 준수). 사용 시점 섹션 압축 + Few-shot 간결화 + micro-eval bash를 패턴 인용으로 trim.

### 논문 인용 확장

- MAR (arxiv 2512.20845) 역할 분리 이론 — `modules/team-core.md` + `modules/cross-validation.md` 교차 인용
- NLAH (2603.25723) 위치 `harness-engineering.md` L41/L1042 정정 (baseline.md S19 일방향 정정)

---

## 🔧 Bug Fixes / Improvements

### Stale Line Anchor 제거

Progressive Disclosure 원칙으로 줄 번호가 변동되는 파일에서 라인 앵커가 stale해지는 문제:
- `skills/fz-codex/SKILL.md` L46 `L115+` → `## 서브커맨드 섹션 이하`
- `modules/cross-validation.md` L145 `L436-444` → `skills/fz-codex/SKILL.md § micro-eval 섹션`

### Canonical 선언 일관성

- `skills/fz-codex/SKILL.md` L61 "canonical 정의" 문구 → "3-Tier 디스커버리 정의: `modules/cross-validation.md § get_codex_skill()` 참조"로 정정 (참조 대상과 실제 섹션 이름 일치)

### Gap 감사 범위 확장

- v3에서 TeamCreate 사용 7 skills 대상 → v4에서 **9 skills** (fz-search + fz-pr-digest 추가 — Codex final check에서 발견한 drift)

### 스킬 간 V.D. 모듈 참조 추가

- `skills/fz-discover/SKILL.md` + `skills/fz-peer-review/SKILL.md` 모듈 참조 표에 `lead-reasoning.md` + `uncertainty-verification.md` 행 추가 (탐색·피어 리뷰 주장도 VD 대상)

### 가이드 4.6/4.7 병기

- `guides/skill-authoring.md` 원칙 8 — "Claude 4.6/4.7 과격 표현 제거" + Opus 4.7 literal interpretation 경고
- `guides/skill-troubleshooting.md` + `guides/agent-team-guide.md` + `guides/prompt-optimization.md` — "4.6 경향" → "4.6/4.7 경향" 병기

### 레거시 정리

- `guides/agent-team-guide.md` L292/L354/L386의 `plan-tradeoff` 3건 참조 모두 `ARCHIVED` 인라인 태그 (에이전트는 `plan-tradeoff.md.archived`)

---

## 📊 Audit Methodology (3-Model 9 Round)

### Round 구조

| Round | 주체 | Gap / 판정 |
|-------|------|-----------|
| R1 | Claude Discover (plan-structure + arch-critic + memory-curator + impact-scan) | 22 Gap (Critical 5 / High 7 / Medium 7 / Low 3) |
| R2 | Codex verify-v1 | needs_revision (Critical 1 / Major 4 / Minor 4) |
| R3 | Claude meta-analysis (Lead 실측) | 재분류 + G22 Critical 승격 |
| R4 | Codex review-v2 | needs_revision (Reflection 6/9 = 67%) |
| R5 | Plan v3 작성 (7 actionable 전부 반영) | 24 Gap 단일화 |
| R6 | Wave 1 구현 | 17 파일 수정 |
| R7 | Codex check Wave 1 | approved (0/0/0) |
| R8 | Wave 2+2.5+3 구현 | 16 파일 추가 수정 |
| R9 | Codex final v2 | **approved (0/0/0)** ✅ |

### 방법론적 발견

- **동종 모델 blind spot 실증**: memory-curator 3-E 경고대로 Claude 4명이 G22(템플릿 상속) + fz-search/fz-pr-digest env flag drift + 카운트 regression 3건을 놓침 → Codex가 모두 발견.
- **라운드마다 심화**: 각 라운드가 이전이 놓친 것을 포착. 단일 검증은 불충분 — iterative + cross-model이 결정적.
- **V.D. 4-way 재모델링**: Claude 팀이 "단일 선형 6링크"로 모델링 → Codex가 "4개 독립 체인"으로 재해석. 구조 이해 정확성 확보.

---

## 📁 File Changes Summary

**수정 파일 34개** (git 기준):
- `modules/` 4개: team-core, cross-validation, memory-guide, system-reminders
- `guides/` 5개: agent-team-guide, skill-authoring, skill-troubleshooting, prompt-optimization, harness-engineering (v3.11 유지 + v4.0 context)
- `skills/` 10개: fz, fz-plan, fz-code, fz-discover, fz-fix, fz-review, fz-peer-review, fz-search, fz-pr-digest, fz-codex
- `agents/` 12개: impl-correctness, impl-quality, plan-structure, plan-edge-case, plan-impact, review-arch, review-correctness, review-counter, review-direction, review-quality, search-pattern, search-symbolic
- `templates/` 2개: agent-template, skill-template
- `meta/` 3개: README, CLAUDE.md, CHANGELOG

**Net**: +388 insertions / -81 deletions

**Commits** (기능 단위):
1. `83a804f` — feat(verification): V.D. 인프라 + 레이어 경계 + Task Brief 자동 상속
2. `83e0f6b` — feat(env-flag): TeamCreate 사용 9 skills Prerequisites + VD 모듈 확산
3. `77eb73b` — feat(guides): Opus 4.7 literal interpretation + Memory tool + plan-tradeoff ARCHIVED
4. `1046465` — feat(chain-closure): V.D. 체인 논리 링크 + Follow-up Re-audit Gate + micro-eval 트리거
5. `6f104ec` — docs: CHANGELOG Retired Citation Policy + Plan v3 audit 요약
6. (v4.0.0 릴리즈 commit) — chore(release): README v4.0 + plugin.json bump + RELEASE_NOTES

---

## 🔄 Migration Guide

### 사용자 (fz 사용자)

```bash
# 업데이트
claude plugin update fz@fz-orchestrator

# 환경 변수 설정 (TEAM 모드 사용 시 필수)
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1

# 설치 확인
/fz "안녕"
```

**영향**:
- 기존 SKILL.md 직접 커스텀한 경우: `## Verification` 섹션이 자동 상속되므로 충돌 가능. 사용자 커스텀 섹션과 병합 필요.
- TEAM 모드 사용 시: env flag 미설정 이슈 명확한 에러 메시지로 개선됨.

### 기여자 (fz 소스 수정자)

- 신규 에이전트 생성 시: `templates/agent-template.md` 그대로 복사 → `## Verification` 섹션 자동 포함.
- 신규 TeamCreate 스킬 생성 시: `templates/skill-template.md` `## If TeamCreate is used` 체크리스트 항목 필수 (env flag + team-core 참조 + Task Brief 경로).
- 외부 메모리 경로 참조 시: `${CLAUDE_PROJECT_DIR}/memory/...` 변수형만 허용 (glob `*` 금지).

---

## 🔗 References

- **Plan v3** (최종 구현 계획): `TVING/NOTASK-20260421-fz-audit/plan/plan-v3.md`
- **Landscape Map** (22 Gap 상세): `TVING/NOTASK-20260421-fz-audit/discover/landscape-map.md`
- **Codex final v2** (approved 증거): `TVING/NOTASK-20260421-fz-audit/code/codex-final-v2.md`
- **V.D. 4-way Chain 다이어그램**: README.md § Verification Discipline 4-way Chain

---

## 🙏 Credits

- **Claude Opus 4.7** (1M context): Primary implementation + Lead orchestrator
- **Codex GPT-5.4**: Cross-model verification (9 rounds)
- **Anthropic Agent Teams** (v2.1.32+): TeamCreate + SendMessage peer-to-peer 통신 기반

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
