---
name: fz-codex
description: >-
  Codex CLI(GPT) 교차 검증. 코드/계획을 독립 모델로 상호 검증.
  예: codex, 교차검증, GPT로 확인, 상호검증
user-invocable: true
argument-hint: "[review|verify|validate|check|final|adversarial] [대상]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__write_memory,
  mcp__serena__read_memory,
  Bash(codex *), Read, Grep
composable: true
provides: [verification]
needs: [none]
intent-triggers:
  - "codex|교차검증|GPT"
  - "codex|cross-validate|verify with codex"
model-strategy:
  main: null
  verifier: sonnet
---

# /fz-codex - Codex 상호검증 스킬 (Hybrid)

> **행동 원칙**: Codex CLI(0.124.0+, gpt-5.5)를 **Hybrid 모드**로 활용하여 독립적 교차 검증을 수행한다.
> CLI(`codex exec`) + Plugin(`/codex:*`, 설치 시) 자동 라우팅. Plugin 미설치 시 CLI 폴백.

> **Authority**:
> - Hybrid Routing: OpenAI Codex CLI 공식 docs [verified: official] — 0.118.0+ Plugin 도입, 0.124.0+ gpt-5.5 지원
> - Effort Routing: GPT-5 Prompting Guide (OpenAI Cookbook 2026) [verified: official] — effort 파라미터 표준 (low/medium/high/xhigh)
> - adversarial 서브커맨드: ICLR 2025 Blogposts [verified: peer-reviewed] — Adversarial debate는 majority voting으로 환원, "Generator≠Evaluator 분리"가 fz의 frame
> - micro-eval 서브커맨드: Chain-of-Verification (CoVe, arXiv 2309.11495) [verified: peer-reviewed] — 단일 주장 재평가 패턴

## 개요

> 서브커맨드: verify | review | validate | check | final | commit | adversarial | drift | plan | micro-eval | config

- **CLI** (`codex exec review`): git diff + `-o`/`--json` + `--add-dir` + 3-Tier 스킬 — review/check/final/commit
- **CLI** (`codex exec`): 프롬프트 + `--output-schema` — verify/validate/drift/plan
- **Plugin** (`/codex:*`): 설치 시 review/check/adversarial에 우선 사용. 백그라운드 Job 관리 (`status`/`result`)
- **`--add-dir`**: 모노레포 공유 모듈 컨텍스트 확장 (TvingUI, tving-common 등)
- **Codex 네이티브 스킬**: 3-Tier 디스커버리 (`~/.codex/skills/`) 역할 기반 매칭

## 사용 시점

```bash
/fz-codex {review|verify|validate|check|final|commit|adversarial|drift|plan|micro-eval|config} [args]
```

자세한 옵션과 컨텍스트는 `## 서브커맨드` 섹션 이하 각 서브섹션 참조.

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/cross-validation.md | 검증 게이트, get_codex_skill() 3-Tier 디스커버리, GIT_ROOT 추출 |

## GIT_ROOT 추출

> CLAUDE.md `## Directory Structure`에서 동적 추출. 상세: modules/cross-validation.md 참조.

## Codex 스킬 3-Tier 디스커버리

> 3-Tier 디스커버리 정의: `modules/cross-validation.md § get_codex_skill()` 참조.

역할 기반 동적 결정: Tier 1(CLAUDE.md `## Codex Skills` 테이블) → Tier 2(글로벌 `fz-*`) → Tier 3(인라인 프롬프트).

### Codex System Skills 활용 (Cnew-4, 2026-05-16)

> Codex self-reflexive verify Q5 단독 발견 — `~/.codex/skills/.system/` 활용.

`~/.codex/skills/.system/` 아래 5개 system skill을 fz-codex 호출 시 보조적으로 활용 가능:

| System Skill | 활용 시점 | fz-codex 통합 |
|------------|---------|------------|
| **openai-docs** | preamble 표준 / GPT-5.5 best practices 참조 | verify/plan 서브커맨드 prompt 작성 시 |
| **skill-creator** | 새 Codex 스킬 생성 (메타 도구) | fz-codex 자체 진화 (별도 사이클) |
| **skill-installer** | Codex 스킬 install 자동화 | 새 fz-codex 스킬 추가 시 |
| **plugin-creator** | Codex plugin 생성 | 별도 영역 |
| **imagegen** | 이미지 생성 | 본 fz 범위 외 |

**활용 예** (openai-docs):
```bash
# verify prompt 작성 전 openai-docs 호출하여 최신 GPT-5.5 prompting 가이드 확인
codex exec --skill openai-docs "GPT-5.5 prompting guide의 preamble 패턴 핵심"
# 결과를 verify prompt template에 반영
```

## Codex 네이티브 스킬 (3-Tier 디스커버리)

| 서브커맨드 | 역할 | 스킬 | 연결 방식 |
|-----------|------|------|----------|
| review, check, final, commit | reviewer | fz-reviewer | `codex exec review` — 스킬 자동 트리거 + `--json`/`-o` 구조화 출력 |
| verify | architect | fz-architect | `codex exec` + `get_codex_skill("architect")` |
| validate | guardian | fz-guardian | `codex exec` + `get_codex_skill("guardian")` |
| final (DA 패스) | challenger | fz-challenger | `codex exec` + `get_codex_skill("challenger")` — major 이상 이슈 발견 시 |
| verify/validate (탐색 보조) | searcher | fz-searcher | `codex exec` + `get_codex_skill("searcher")` — 심볼 탐색 필요 시 |
| check (수정 제안) | fixer | fz-fixer | `codex exec` + `get_codex_skill("fixer")` — fixable 이슈 존재 시 |
| drift | drift | fz-drift | `codex exec` + `get_codex_skill("drift")` — 전체 스캔 |
| plan | planner | fz-planner | `codex exec` + `get_codex_skill("planner")` — 독립 플랜, xhigh effort |

스킬 위치: `~/.codex/skills/` (3-Tier 디스커버리로 결정)

## 팀 에이전트 모드

참조: `modules/team-core.md` -- Sub Agent 프로토콜 (`composable: true`)

---

> 공통 설정 (Base Branch / Effort / Diff 크기 / CLI 모드): `modules/codex-strategy.md`

## Hybrid Routing (0.118.0+; gpt-5.5 requires 0.124.0+)

서브커맨드별 최적 실행 경로. Plugin 미설치 시 경고 없이 CLI 폴백.
> 버전 플로어: Hybrid 라우팅 자체는 0.118.0부터 동작한다. 아래 `-m gpt-5.5` 예시는 0.124.0 이상이 필요하며, 그 이전 CLI에서는 `-m` 없이 config 기본값으로 폴백하거나 `-m gpt-5.4`를 사용한다.

| 서브커맨드 | Plugin 우선 | CLI (폴백/전용) | Plugin 불가 이유 |
|-----------|------------|----------------|----------------|
| review | `/codex:review --base` | `codex exec review -o` | — |
| check | `/codex:review --scope working-tree` | `codex exec review --uncommitted` | — |
| adversarial | `/codex:adversarial-review` | challenger 프롬프트 | — |
| final/commit | — | CLI only | `--add-dir`, `--commit`, `resume` |
| verify/validate | — | CLI only | `--output-schema` |
| drift/plan | — | CLI only | 커스텀 스킬 + 구조화 출력 |
| micro-eval | — | CLI only | 경량 단일 주장 재평가, `--ephemeral` |

> **Plugin 감지** (Cbug-1 수정, 2026-05-16): `codex mcp list`는 MCP server 목록이라 plugin과 다른 계층 — config.toml 기반 감지가 정확하다. 오류 시에도 CLI 자동 폴백.
> ```bash
> # Plugin enabled detection (config.toml + cache 동시 확인)
> grep -q '^\[plugins\.' ~/.codex/config.toml 2>/dev/null && \
>   ls ~/.codex/plugins/cache/*/  2>/dev/null | head -1 >/dev/null && \
>   PLUGIN_AVAILABLE=true || PLUGIN_AVAILABLE=false
> ```
> 이전 `codex mcp list | grep -q plugin`은 plugin enabled 상태에서도 항상 false 반환 (MCP server ≠ plugin) → Plugin 모드 영원히 미사용 위험 있었음.

---

## ⛔ Bash 호출 Hygiene (29차/30차 교훈, 필수)

> 상세: `modules/fz-codex-bash-hygiene.md` — Stdin 닫기 (§1) / Trusted Dir (§2) / `-o` 버퍼링 (§3) / Background Task (§4) / Trust Level (§5) / Base Verification Gate (§5.5) / Standard Wrapper Template (§6)

⛔ `codex exec` / `codex review`를 Bash로 호출할 때 본 모듈 *전체 준수* 의무. 미적용 시 무한 hang / trusted directory 에러 / sandbox 무효화 / base mismatch.

---

## Effort Routing (δ-2)

`-c model_reasoning_effort=<medium|high|xhigh>` 매핑. 단순 호출에 xhigh 낭비 + 심화 호출에 medium 부족 방지.

| 서브커맨드 | effort | 근거 |
|----------|:------:|------|
| `micro-eval` | **medium** | 단일 주장 재평가, 수백 토큰 단위 |
| `review`, `check`, `verify`, `validate`, `commit`, `drift` | **high** | 리뷰/검증 표준 |
| `final` (1차+resume 2차), `adversarial`, `plan` | **xhigh** | 종합 리뷰 + 독립 설계 + DA 패스 |

**Critical 자동 에스컬레이션**: 이전 검증에서 critical 이슈 발견 시 → high → xhigh 자동 전환 (validate/verify에 명시).

**원칙**: effort는 호출 종류 기준 (단순/표준/심화), 모델 가용성 기준 아님. gpt-5.5 high가 gpt-5.4 xhigh보다 빠르고 정확하면 default = gpt-5.5 high.

> δ-2 출처: plan v3.1.3 §Tier 1 row 5. 32차 axis (a) probe: `plan_mode_reasoning_effort` direct flag 미존재 → `-c model_reasoning_effort=...` config override 형식이 정식 primitive.

---

## 서브커맨드

> **상세 정의**:
> - **Core (review/verify/validate/check)**: `modules/fz-codex-subcommands-core.md`
> - **Aux (final/commit/adversarial/drift/plan/micro-eval/config)**: `modules/fz-codex-subcommands-aux.md`

| 명령 | 용도 | 호출 스킬 | effort |
|------|------|----------|:------:|
| **review** | 코드 리뷰 (주력) | /fz-review Phase 5 | high |
| **verify** | 계획 검증 (Q1-Q8 stress-test) | /fz-plan Phase 2 | high |
| **validate** | 피드백 역검증 | /fz-review Phase 5.5 | high |
| **check** | 커밋 전 빠른 검증 (verdict contract) | /fz-fix | high |
| **final** | PR 전 최종 리뷰 (resume --last 심화) | /fz-pr 전 | xhigh |
| **commit** | 특정 커밋 검증 | 단일 SHA 분석 | high |
| **adversarial** | Devil's Advocate 리뷰 | /fz-review DA 패스 | xhigh |
| **drift** | 아키텍처 드리프트 전체 스캔 | /fz-manage drift | high |
| **plan** | 독립 플랜 (Claude와 교차 비교, C4 원칙) | /fz-plan cross-check | xhigh |
| **micro-eval** | 단일 주장 독립 재평가 (claim-type 라우팅) | cross-validation Gate | medium |
| **config** | 설정 조회 (config.toml + plugin/MCP 상태) | /fz-manage config | - |

⛔ **Bash 호출 시 의무**: 모든 서브커맨드 호출은 `modules/fz-codex-bash-hygiene.md` 준수 (stdin close / trusted dir / Base Verification Gate / Wrapper Template).

⛔ **3-Tier 디스커버리**: 각 서브커맨드는 `get_codex_skill()` (cross-validation.md)로 Codex System Skill 우선 사용 → 폴백 인라인 프롬프트.

---

## Issue Tracker 연동

검증 결과를 자동으로 Issue Tracker에 기록 (참조: modules/session.md). `-o` 파일을 jq로 파싱하여 phase/status 태그 후 통합.

---

## Gate: Codex Verification Complete
- [ ] 서브커맨드 실행 완료?
- [ ] Issue Tracker에 결과 기록?
- [ ] verdict 판정 (approved/rejected/conditional)?

---

## Few-shot 예시

```
예시 1 — review: BAD codex "LGTM" 자체판단없이 approved / GOOD codex 3 issues + Claude 독립 1 = 4 issues + verdict
예시 2 — verify: BAD codex "승인" → 단일모델 Phase 2 통과 / GOOD codex가 plan 독립재작성 → Claude와 diff → "divergence" 기록
예시 3 — validate: BAD Rate 85% 수치만 보고 pass (regressed 놓침) / GOOD resolved/partial/unresolved/regressed 4축 → regressed 0 + Rate 80+ 동시
```

서브커맨드: 리뷰→`codex exec review -o`, 검증→`--output-schema`, 심화→`resume --last`. Schema version: `"1.1"`이면 `scope_disposition` read, 미존재/`"1.0"`이면 Lead가 `modules/scope-challenge.md` 수동 실행 (`jq '.schemaVersion // "1.0"'`).

---

## Boundaries

Codex CLI 응답 실패 시에도 Issue Tracker에 기록하고 폴백을 실행한다.

**Will**:
- `codex exec review` + `-o`/`--json`으로 구조화된 리뷰 캡처
- `codex exec` + `--output-schema`로 구조화된 검증
- `--add-dir`로 모노레포 공유 모듈 컨텍스트 확장
- `codex exec resume`로 multi-pass 심화 검증 (final)
- Codex 네이티브 스킬(3-Tier 디스커버리로 결정) 자동 활용
- Base branch 자동 결정 (불확실 시 사용자 질문)
- Critical 이슈 감지 시 xhigh 자동 에스컬레이션

**Will Not**:
- 코드를 직접 수정하지 않음 (검증만 수행)
- Main Agent의 역할을 대신하지 않음
- Base branch를 추측하지 않음 (불확실 시 반드시 질문)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| CLAUDE.md 미발견 | `../CLAUDE.md` → `CLAUDE.md` → `find .. -maxdepth 2` | 경고 후 계속 |
| Guidelines 미발견 | CLAUDE.md `## Code Conventions` 참조 | 일반 규칙 적용 |
| Plugin 명령 실패 | CLI 자동 폴백 (`codex exec`) | 경고 없이 진행 |
| Codex CLI 통신 실패 | 컨텍스트 축소 후 재시도 | /sc:analyze 단독 |
| `codex exec review` 실패 | `codex exec` + diff 인라인 | 수동 분석 |
| JSON 파싱 실패 | `-o` 파일 캡처 폴백 | Claude 분석 |
| 모델 미지원 (`gpt-5.5`) | config.toml 모델로 폴백 (`-m` 제거) | -- |
| 3회 연속 실패 | 사용자 에스컬레이션 | -- |
| **`Reading additional input from stdin...` hang** (29차) | `< /dev/null` 추가하여 stdin 명시 close (`modules/fz-codex-bash-hygiene.md` § 1) | 프로세스 kill + 재시도 |
| **`Not inside a trusted directory` 에러** (29차) | `--skip-git-repo-check` 추가 또는 git repo 내부에서 실행 (`modules/fz-codex-bash-hygiene.md` § 2) | working dir을 GIT_ROOT로 변경 |
| **`--profile` 사용 시 sandbox가 read-only로 force** (30차, Critical) | `[projects.<path>] trust_level = "trusted"` 추가 (`modules/fz-codex-bash-hygiene.md` § 5) | `-c 'sandbox_permissions=...'` inline override |

## Completion → Next

검증 완료 후 호출 스킬로 결과를 반환한다:
- verify → /fz-plan
- review/check/final/commit → /fz-review
- validate → /fz-review

## 관련 스키마

- `schemas/codex_base_issue_schema.json` -- 공통 issue 정의 (severity, confidence, unified_category, alternatives)
- `schemas/codex_review_schema.json` -- review/verify/validate/check/final/commit 응답
- `schemas/codex_verification_schema.json` -- validate 역검증 응답
- `schemas/codex_peer_review_schema.json` -- peer-review 에이전트 응답

## 관련 Codex 스킬

3-Tier 디스커버리로 결정. sc: `sc:reflect`(교차검증), `sc:analyze`(보완), `sc:troubleshoot`(통신 문제).
