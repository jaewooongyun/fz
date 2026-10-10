---
name: fz-gpt
description: >-
  GPT CLI 교차 검증. 코드/계획을 독립 모델로 상호 검증.
  예: codex, 교차검증, GPT로 확인, 상호검증 (비사용: 직접 수정 →fz-fix, 자기 리뷰 →fz-review; GPT는 검증 전용)
user-invocable: true
argument-hint: "[review|verify|verify-gates|validate|check|final|adversarial|drift|plan|micro-eval|independent-plan|independent-review] [대상]"
allowed-tools: >-
  mcp__plugin_fz_serena__find_symbol,
  mcp__plugin_fz_serena__write_memory,
  mcp__plugin_fz_serena__read_memory,
  Bash(codex *), Bash(*/scripts/gpt-exec.sh*), Bash(*/scripts/gpt_independent.sh*), Bash(*/scripts/gpt-choice.sh*), Read, Grep
metadata:
  provides: [verification]
  needs: [none]
  intent-triggers:
    - "gpt|교차검증|GPT"
    - "gpt|cross-validate|verify with gpt"
---

# /fz-gpt - GPT 상호검증 스킬

> **행동 원칙**: GPT CLI 를 래퍼(`scripts/gpt-exec.sh`) 한 경로로 불러 독립적 교차 검증을 수행한다.
> ⛔ **첫 GPT 호출 전**: `modules/gpt-strategy.md § 모델·effort 선택` — 세션에 한 번 모델·effort 를 묻고(`gpt-choice.sh get` → `options` → `set`) 그 값을 모든 서브커맨드에 적용한다. 서브커맨드별 effort 는 없다.

> **Authority**:
> - CLI 버전: OpenAI GPT CLI 공식 docs [verified: official] — 0.124.0+ gpt-5.5 · 0.153.1+ gpt-6-astra(0.153.4가 bundled default로 승격) · 0.157.0+ gpt-6-sol(0.156.1 에서 선택기 추가) · **0.159.0+ gpt-6.1-sol(0.159.1 이 bundled default 로 승격)** — 둘 다 effort 기본값은 medium. 실제 모델은 세션 선택(없으면 `config.toml`)과 CLI 버전에 따른다
> - effort 수준: API `reasoning.effort` 는 **모델별**이다 [verified: developers.openai.com/api/docs/guides/reasoning] — 지원 목록은 문서에 적지 않는다. `gpt-choice.sh options` 가 `models_cache.json`(visibility=list · supported_reasoning_levels)에서 선택지를 만들고 `gpt-choice.sh set` 이 검증한다 (`modules/gpt-strategy.md § 모델·effort 선택`)
>   ⛔ 공식은 xhigh 를 무조건 권하지 않는다 — *"Only use when your evals show a clear benefit that justifies the extra latency and cost."*
> - adversarial 서브커맨드: ICLR 2025 Blogposts [verified: peer-reviewed] — Adversarial debate는 majority voting으로 환원, "Generator≠Evaluator 분리"가 fz의 frame
> - micro-eval 서브커맨드: Chain-of-Verification (CoVe, arXiv 2309.11495) [verified: peer-reviewed] — 단일 주장 재평가 패턴

## 개요

> 서브커맨드: review | verify | verify-gates | validate | check | final | adversarial | drift | plan | micro-eval | independent-plan | independent-review (12개 — 뒤 둘은 fz-peer-review 기본 · fz-review · fz-plan 은 opt-in `--gpt-independent`)

- **래퍼 review** (`gpt-exec.sh review`): git diff + `--out` + 3-Tier 스킬 — review/check/final
- **래퍼 exec** (`gpt-exec.sh exec`): `--prompt-file` + `--schema` — verify/validate/drift/plan
- **공유 모듈**: read-only 가 전 디스크 읽기를 허용해 별도 플래그가 필요 없다. `--add-dir` 는 **쓰기** 디렉토리 플래그라 fz 에서 쓰지 않는다 (2026-09-25 CLI help 실측)
- **GPT 네이티브 스킬**: 3-Tier 디스커버리 (`${CODEX_HOME:-~/.codex}/skills/` → 플러그인 `gpt-skills/`) 역할 기반 매칭

## 사용 시점

```bash
/fz-gpt {review|verify|verify-gates|validate|check|final|adversarial|drift|plan|micro-eval} [args]
```

자세한 옵션과 컨텍스트는 `## 서브커맨드` 섹션 이하 각 서브섹션 참조.

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/cross-validation.md | 검증 게이트, get_gpt_skill_path() 3-Tier 디스커버리, GIT_ROOT 추출 |

## GIT_ROOT 추출

> CLAUDE.md `## Directory Structure`에서 동적 추출. 상세: modules/cross-validation.md 참조.

## GPT 스킬 3-Tier 디스커버리

> 3-Tier 디스커버리 정의: `modules/cross-validation.md § get_gpt_skill_path()` 참조.

역할 기반 동적 결정: Tier 1(CLAUDE.md `## GPT Skills` 테이블) → Tier 2(글로벌 `fz-*`) → Tier 3(인라인 프롬프트).

### GPT System Skills 활용 (Cnew-4, 2026-05-16)

> GPT self-reflexive verify Q5 단독 발견 — `${CODEX_HOME:-~/.codex}/skills/.system/` 활용.

`${CODEX_HOME:-~/.codex}/skills/.system/` 아래 5개 system skill을 fz-gpt 호출 시 보조적으로 활용 가능:

| System Skill | 활용 시점 | fz-gpt 통합 |
|------------|---------|------------|
| **openai-docs** | preamble 표준 / GPT-6 best practices 참조 | verify/plan 서브커맨드 prompt 작성 시 |
| **skill-creator** | 새 GPT 스킬 생성 (메타 도구) | fz-gpt 자체 진화 (별도 사이클) |
| **skill-installer** | GPT 스킬 install 자동화 | 새 fz-gpt 스킬 추가 시 |
| **plugin-creator** | GPT plugin 생성 | 별도 영역 |
| **imagegen** | 이미지 생성 | 본 fz 범위 외 |

**활용 예** (openai-docs):
```bash
# verify prompt 작성 전 openai-docs 로 최신 GPT-6 prompting 가이드 확인 — 래퍼 exec, 스킬은 프롬프트에서 이름으로 지정
echo 'openai-docs 스킬로 GPT-6 prompting guide 의 preamble 패턴 핵심을 요약하라' > "$P_DOCS"
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$WORK_DIR" --out "$DOCS_FILE" --prompt-file "$P_DOCS" --gpt-skill openai-docs   # 경로 없음 = 텔레메트리 fallback=1 (스킬 본문을 싣지 않으므로 정직하게)
# 결과를 verify prompt template에 반영 — ⚠️ 이름 지정으로 system skill 이 로드되는지는 [미검증] (래퍼는 CLI 스킬 플래그를 넘기지 않는다)
```

## GPT 네이티브 스킬 (3-Tier 디스커버리)

| 서브커맨드 | 역할 | 스킬 | 연결 방식 |
|-----------|------|------|----------|
| review, check, final | reviewer | fz-reviewer | `gpt-exec.sh review` — 스킬 자동 트리거 + `--out` 구조화 출력 |
| verify | architect | fz-architect | `gpt-exec.sh exec` + `get_gpt_skill_path("architect")` |
| validate | guardian | fz-guardian | `gpt-exec.sh exec` + `get_gpt_skill_path("guardian")` |
| final (DA 패스) | challenger | fz-challenger | `gpt-exec.sh exec` + `get_gpt_skill_path("challenger")` — major 이상 이슈 발견 시 |
| verify/validate (탐색 보조) | searcher | fz-searcher | `gpt-exec.sh exec` + `get_gpt_skill_path("searcher")` — 심볼 탐색 필요 시 |
| check (수정 제안) | fixer | fz-fixer | `gpt-exec.sh exec` + `get_gpt_skill_path("fixer")` — fixable 이슈 존재 시 |
| drift | drift | fz-drift | `gpt-exec.sh exec` + `get_gpt_skill_path("drift")` — 전체 스캔 |
| plan | planner | fz-planner | `gpt-exec.sh exec` + `get_gpt_skill_path("planner")` — 독립 플랜 |

스킬 위치: `get_gpt_skill_path()` 가 정한다 — `${CODEX_HOME:-~/.codex}/skills/` → 플러그인 `gpt-skills/` (3-Tier 디스커버리). ⛔ `~/.codex/skills/` 를 경로에 직접 쓰지 않는다 — 격리 `CODEX_HOME` 을 우회해 설치된 다른 판의 스킬을 읽는다

## 팀 에이전트 모드

⛔ `composable` frontmatter는 2026-08-09 제거(소비처 0) — 파이프라인 연결은 `provides`/`needs`가 결정한다

---

> 공통 설정 (Base Branch / 모델·effort 선택 / Diff 크기 / CLI 모드): `modules/gpt-strategy.md`

---

## ⛔ Bash 호출 Hygiene (29차/30차 교훈, 필수)

> 상세: `modules/fz-gpt-bash-hygiene.md` — Stdin 닫기 (§1) / Trusted Dir (§2) / `-o` 버퍼링 (§3) / Background Task (§4) / Trust Level (§5) / Base Verification Gate (§5.5) / Wrapper 참조 (§6) / `--` 구분자 (§7) / **정본 호출 경로 `scripts/gpt-exec.sh` (§8)**

⛔ **`${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh`를 경유한다** (§8 — 경로 기준은 플러그인 루트) — 손 조립 금지. 스크립트가 사전 게이트(플래그 상호 배타·필수 인자·경로 실재)와 **사후 게이트(exit≠0 / 빈 출력 / **스키마 계약 위반** → 측정 실패)**를 강제한다.

```bash
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" review --cd "$GIT_ROOT" --out "$F" --uncommitted   # 대상=플래그만
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec   --cd "$GIT_ROOT" --out "$F" --prompt-file P --schema S     # 커스텀 지시
```

⛔ **exit 10~14 = 측정 실패**이며 "이슈 0건"이 아니다. ⛔ 게이트 3은 **스키마 계약**(required·type·enum·재귀)을 본다 — `{}`는 통과하지 못한다. ⛔ 스크립트 exit을 뒤 명령이 덮지 않게 하라. 미준수 시 무한 hang / trusted directory 에러 / sandbox 무효화 / base mismatch / **인자 충돌 exit 2를 정상 결과로 오독**.

---

## 서브커맨드

> **상세 정의**:
> - **Core (review/verify/validate/check)**: `modules/fz-gpt-subcommands-core.md`
> - **Aux (final/adversarial/drift/plan/micro-eval/independent-plan/independent-review)**: `modules/fz-gpt-subcommands-aux.md`

| 명령 | 용도 | 호출 스킬 |
|------|------|----------|
| **review** | 코드 리뷰 (주력) | /fz-review Phase 5 |
| **verify** | 계획 검증 (Q1-Q8 stress-test) | /fz-plan Phase 2 |
| **validate** | 피드백 역검증 | /fz-review Phase 5.5 |
| **check** | 커밋 전 빠른 검증 (verdict contract) | /fz-fix |
| **final** | PR 전 최종 리뷰 (resume --session-file 심화) | /fz-pr 전 |
| **adversarial** | Devil's Advocate 리뷰 | /fz-review DA 패스 |
| **drift** | 아키텍처 드리프트 전체 스캔 | /fz-manage drift |
| **plan** | 독립 플랜 (Claude와 교차 비교, C4 원칙) | /fz-plan cross-check |
| **micro-eval** | 단일 주장 독립 재평가 (claim-type 라우팅) | cross-validation Gate |
| **independent-plan** | 격리 첫 패스 플랜 — `scripts/gpt_independent.sh plan` (opt-in `--gpt-independent`) | /fz-plan cross-check |
| **independent-review** | 격리 첫 패스 리뷰 — `scripts/gpt_independent.sh review` (/fz-peer-review 기본 · /fz-review 는 opt-in `--gpt-independent`) | /fz-review · /fz-peer-review |

> independent-review 는 호출 스킬이 Workflow 와 **동시에** 띄우고 `scripts/review_merge.py` 로 합친다 — 순서 정본 `modules/fz-gpt-subcommands-aux.md` § review — Lead 순서

⛔ **Bash 호출 시 의무**: 모든 서브커맨드 호출은 `modules/fz-gpt-bash-hygiene.md` 준수 (stdin close / trusted dir / Base Verification Gate / Wrapper Template).

⛔ **3-Tier 디스커버리**: 각 서브커맨드는 `get_gpt_skill_path()` (cross-validation.md)로 GPT System Skill 우선 사용 → 폴백 인라인 프롬프트.

---

## Issue Tracker 연동

검증 결과를 자동으로 Issue Tracker에 기록 (참조: modules/session.md). `-o` 파일을 jq로 파싱하여 phase/status 태그 후 통합.

---

## Gate: GPT Verification Complete
- [ ] 서브커맨드 실행 완료?
- [ ] Issue Tracker에 결과 기록?
- [ ] verdict 판정 (approved/rejected/conditional)?

---

## Few-shot 예시

```
예시 1 — review: BAD gpt "LGTM" 자체판단없이 approved / GOOD gpt 3 issues + Claude 독립 1 = 4 issues + verdict
예시 2 — verify: BAD gpt "승인" → 단일모델 Phase 2 통과 / GOOD gpt가 plan 독립재작성 → Claude와 diff → "divergence" 기록
예시 3 — validate: BAD Rate 85% 수치만 보고 pass (regressed 놓침) / GOOD resolved/partial/unresolved/regressed 4축 → regressed 0 + Rate 80+ 동시
```

서브커맨드: 리뷰→`gpt-exec.sh review --out`, 검증→`gpt-exec.sh exec --schema`, 심화→`gpt-exec.sh resume --session-file`. Schema version: `--schema …gpt_review_schema.json` 출력은 `"1.1"` 만 통과한다(다른 값·`scope_disposition` null 은 validate-gpt-output 이 거부 → exit 14) → `scope_disposition` read. `schemaVersion` 미존재면 Lead가 `modules/scope-challenge.md` 수동 실행 (`jq '.schemaVersion // empty'`).

---

## 테스트 케이스

### Triggering Test

should-trigger (description '예:' 어휘 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "이 변경분 codex로 리뷰해줘" | trigger | '예: codex' + review 서브커맨드 (래퍼 `gpt-exec.sh review --base`) |
| "코드 교차검증 돌려줘" | trigger | '예: 교차검증' — 핵심 유스케이스 (독립 모델 상호 검증) |
| "GPT로 한 번 더 확인해줘" | trigger | '예: GPT로 확인' |
| "이 계획 상호검증해줘" | trigger | '예: 상호검증' + verify 서브커맨드 (계획 검증) |
| "PR 올리기 전 최종 검증해줘" | trigger | final 서브커맨드 (argument-hint, resume 심화) |

should-NOT-trigger (Boundaries Will Not / '비사용:' 대안 스킬)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 버그 직접 고쳐줘" | NOT trigger | fz-fix | '비사용: 직접 수정 →fz-fix' + Will Not "코드를 직접 수정하지 않음 (검증만 수행)" |
| "이 컴파일 에러 수정해줘" | NOT trigger | fz-fix | Will Not "코드 직접 수정 안 함" — GPT는 검증 전용 |
| "내 코드 자체적으로 검증해줘" | NOT trigger | fz-review | '비사용: 자기 리뷰 →fz-review' (gpt/교차검증 미언급 = 자기 3중 검증) |

### Functional Test (Given/When/Then)

| Given | When | Then (pass/fail oracle) | type |
|-------|------|--------------------------|------|
| Git diff 존재, GPT CLI 설치 | `/fz-gpt review` | 래퍼(`gpt-exec.sh review --out`) 실행 → 구조화 이슈 캡처 + verdict(approved/rejected/conditional) 판정 → Gate "GPT Verification Complete" 3항목 전부 통과 | normal |
| Claude 계획 초안 존재 | `/fz-gpt verify` | gpt가 plan을 `--output-schema`로 독립 재작성 → Claude 계획과 diff → divergence 기록 + verdict 판정 후 /fz-plan으로 반환 (Gate 3/3 통과) | normal |
| base branch 후보 불확실(자동 결정 불가) | `/fz-gpt review` | Will Not "Base branch를 추측하지 않음" — 추측 base 실행 0건, 사용자에게 질문 → 확정 후 실행 | edge-case |
| CLAUDE.md `## GPT Skills` 테이블(Tier 1) 부재 | `/fz-gpt verify` | Tier 2(글로벌 fz-*) → Tier 3(인라인 프롬프트) 순차 폴백으로 서브커맨드 실행 완료 (Gate "서브커맨드 실행 완료" 통과) | edge-case |
| GPT CLI 통신 실패 | `/fz-gpt review` | 컨텍스트 축소 후 재시도 → 실패 시 Issue Tracker에 기록 + /sc:sc-analyze 단독 폴백 실행 (3회 연속 실패 시 사용자 에스컬레이션) | failure |

## Boundaries

GPT CLI 응답 실패 시에도 Issue Tracker에 기록하고 폴백을 실행한다.

**Will**:
- `gpt-exec.sh review` + `--out`으로 구조화된 리뷰 캡처
- `gpt-exec.sh exec` + `--schema`로 구조화된 검증
- `gpt-exec.sh resume --session-file`로 multi-pass 심화 검증 (final)
- GPT 네이티브 스킬(3-Tier 디스커버리로 결정) 자동 활용
- Base branch 자동 결정 (불확실 시 사용자 질문)

**Will Not**:
- 코드를 직접 수정하지 않음 (검증만 수행)
- Main Agent의 역할을 대신하지 않음
- Base branch를 추측하지 않음 (불확실 시 반드시 질문)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| CLAUDE.md 미발견 | `../CLAUDE.md` → `CLAUDE.md` → `find .. -maxdepth 2` | 경고 후 계속 |
| Guidelines 미발견 | CLAUDE.md `## Code Conventions` 참조 | 일반 규칙 적용 |
| GPT CLI 통신 실패 | 컨텍스트 축소 후 재시도 | /sc:sc-analyze 단독 |
| `gpt-exec.sh review` 실패 | `gpt-exec.sh exec` + diff 인라인 프롬프트 | 수동 분석 |
| JSON 파싱 실패 | `-o` 파일 캡처 폴백 | Claude 분석 |
| 모델 미지원 (구버전 CLI가 config 모델·세션 선택 모델 미인식) | CLI 업데이트 권장, 불가 시 세션 선택을 다시 묻거나(`modules/gpt-strategy.md § 모델·effort 선택`) config `model`을 호환 모델로 조정 (사용자 소관 — 호출부에 모델을 적지 않는다) | -- |
| 3회 연속 실패 | 사용자 에스컬레이션 | -- |
| **`Reading additional input from stdin...` hang** (29차) | `< /dev/null` 추가하여 stdin 명시 close (`modules/fz-gpt-bash-hygiene.md` § 1) | 프로세스 kill + 재시도 |
| **`Not inside a trusted directory` 에러** (29차) | `--skip-git-repo-check` 추가 또는 git repo 내부에서 실행 (`modules/fz-gpt-bash-hygiene.md` § 2) | working dir을 GIT_ROOT로 변경 |
| **`--profile` 사용 시 sandbox가 read-only로 force** (30차, Critical) | `[projects.<path>] trust_level = "trusted"` 추가 (`modules/fz-gpt-bash-hygiene.md` § 5) | 래퍼 경유(`gpt-exec.sh` 가 read-only 강제 — `--profile` 불사용) |

## Completion → Next

검증 완료 후 호출 스킬로 결과를 반환한다:
- verify → /fz-plan
- review/check/final → /fz-review
- validate → /fz-review

## 관련 스키마

- `schemas/gpt_base_issue_schema.json` -- 공통 issue 정의 (severity, confidence, unified_category, alternatives)
- `schemas/gpt_review_schema.json` -- review/verify/validate/check/final 응답
- `schemas/gpt_verification_schema.json` -- validate 역검증 응답
- `schemas/gpt_peer_review_schema.json` -- peer-review 에이전트 응답
- `schemas/gpt_gate_verdict_schema.json` -- 게이트 원장의 게이트별 판정 (fz-plan Phase 2 architect · fz-review Phase 5.5 guardian). ⛔ 게이트 수 = 판정 수 대조용 — `gpt_review_schema` 의 issues 배열은 문제만 담아 전수 확인 불가

## 관련 GPT 스킬

3-Tier 디스커버리로 결정. sc: `sc:reflect`(교차검증), `sc:analyze`(보완), `sc:troubleshoot`(통신 문제).
