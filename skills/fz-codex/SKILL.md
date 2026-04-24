---
name: fz-codex
description: >-
  Codex CLI(GPT) 교차 검증. 코드/계획을 독립 모델로 상호 검증.
  예: codex, 교차검증, GPT로 확인, 상호검증
user-invocable: true
argument-hint: "[review|verify|validate|check|final|adversarial] [대상]"
allowed-tools: >-
  mcp__serena__search_for_pattern,
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

## Codex 네이티브 스킬 (3-Tier 디스커버리)

| 서브커맨드 | 역할 | 스킬 | 연결 방식 |
|-----------|------|------|----------|
| review, check, final, commit | reviewer | fz-reviewer | `codex exec review` — 스킬 자동 트리거 + `--json`/`-o` 구조화 출력 |
| verify | architect | fz-architect | `codex exec` + `get_codex_skill("architect")` |
| validate | guardian | fz-guardian | `codex exec` + `get_codex_skill("guardian")` |
| final (DA 패스) | challenger | fz-challenger | `codex exec` + `get_codex_skill("challenger")` — major 이상 이슈 발견 시 |
| verify/validate (탐색 보조) | searcher | fz-searcher | `codex exec` + `get_codex_skill("searcher")` — 심볼 탐색 필요 시 |
| check (수정 제안) | fixer | fz-fixer | `codex exec` + `get_codex_skill("fixer")` — fixable 이슈 존재 시 |
| drift | drift-detector | fz-drift | `codex exec` + `get_codex_skill("drift-detector")` — 전체 스캔 |
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

> Plugin 감지: `codex mcp list 2>/dev/null | grep -q plugin`. 오류 시에도 CLI 자동 폴백.

---

## 서브커맨드

### review -- 코드 리뷰 (주력)

fz-review의 Phase 5 Codex 부분. **Plugin 우선 → CLI 폴백.**

```bash
# Plugin 모드 (우선 — --add-dir 불필요 시)
/codex:review --base "$BASE_BRANCH" -m gpt-5.5 --json

# CLI 모드 (폴백 — --add-dir 필요 시 또는 Plugin 미설치)
cd "$GIT_ROOT" && codex exec review \
  --base "$BASE_BRANCH" \
  -m gpt-5.5 \
  -c model_reasoning_effort=high \
  --add-dir "$SHARED_MODULES" \
  -o "$REVIEW_FILE"
```

**CLI 주요 플래그**: `-m`(모델), `-o`(파일 캡처), `--json`(JSONL), `--add-dir`(모노레포), `--ephemeral`(일회성)

**`--add-dir` 패턴**: `SHARED_MODULES="$GIT_ROOT/TvingUI $GIT_ROOT/tving-common $GIT_ROOT/Managers"`. 모듈화 시 소비자 디렉토리도 포함: `$GIT_ROOT/Apps/Sources`.

### verify -- 계획 검증

fz-plan의 Phase 2. **`codex exec` + `--output-schema` 사용.**

```bash
SKILL_NAME=$(get_codex_skill "architect")
if [ -n "$SKILL_NAME" ]; then
  SKILL_PROMPT="$(cat ~/.codex/skills/${SKILL_NAME}/SKILL.md)"
else
  SKILL_PROMPT="프로젝트 CLAUDE.md를 읽고 아키텍처/가이드라인을 파악한 후 검증하라."
fi

codex exec \
  -m "$(config.toml 모델)" \
  -c model_reasoning_effort=high \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  --output-schema schemas/codex_review_schema.json \
  -o "$REVIEW_FILE" \
  -C "$GIT_ROOT" \
  "${SKILL_PROMPT}

   이 구현 계획을 검증하라.
   CLAUDE.md ## Code Conventions 섹션의 가이드라인을 참조하라.

   ## 계획
   $PLAN_CONTENT

   ## 영향 심볼
   $AFFECTED_SYMBOLS

   ## 설계 스트레스 테스트 독립 검증 (필수)
   계획의 핵심 설계 결정에 대해 아래 6가지 질문을 독립적으로 평가하라.
   계획에 이미 리스크 매트릭스가 있더라도, 동의 여부와 무관하게 자체 판단하라.

   Q1 다중성: 제안된 설계가 1개일 때와 N개일 때 동일하게 작동하는가?
   Q2 소비자 영향: 변경의 소비자(상위 레이어)에 새 분기/타입/프로토콜이 필요한가?
   Q3 복잡도 이동: 한 레이어의 단순화가 다른 레이어의 복잡도 증가로 이어지는가?
   Q4 경계 케이스: 이 추상화가 커버하지 못하는 케이스는 무엇이고, 대안은?
   Q5 접근 경계: '차단/제거/캡슐화'를 의도한 접근 경로가 실제로 차단되는가? access modifier(public/internal/private)가 의도와 일치하는가? 기존 코드가 이벤트 채널을 우회하여 직접 호출하는 경로가 남아있지 않은가?
   Q6 이벤트 스코프: 이벤트/로그 전송 설계가 포함되어 있다면, 각 이벤트가 측정 목적에 부합하는가? 이벤트 발화 위치의 컨텍스트가 측정 대상과 일치하는가?
   Q7 소비자 코드 품질: 모듈화/캡슐화 작업인 경우, 앱 측 소비자 코드가 모듈의 public API를 올바르게 사용하는가? 앱 생명주기 진입점(AppDelegate, SceneDelegate, UIWindow extension)의 모듈 연동이 정상인가? 모듈화 이전의 레거시 패턴이 앱에 남아있지 않은가?
   Q8 함의 커버리지: 계획이 지시의 "문자적 범위"뿐 아니라 "의미론적 범위"를 커버하는가? 제거/변경 대상이 존재하게 된 이유(원인 코드)까지 범위에 포함됐는가? 지시로 인해 무효화되는 코드(결과 코드)가 처리됐는가? verdict: pass/warn/fail + reasoning. (참조: modules/lead-reasoning.md)

   각 질문에 대해 verdict(pass/warn/fail)와 reasoning을 제시하라.
   계획의 리스크 매트릭스가 빈약하거나 누락된 경우 반드시 지적하라.
   Anti-Pattern Constraints가 있으면 각 금지 패턴의 실효성을 검증하라."
```

### validate -- 피드백 역검증

fz-review의 Phase 5.5. **`codex exec` + `--output-schema` 사용.**

```bash
SKILL_NAME=$(get_codex_skill "guardian")
if [ -n "$SKILL_NAME" ]; then
  SKILL_PROMPT="$(cat ~/.codex/skills/${SKILL_NAME}/SKILL.md)"
else
  SKILL_PROMPT="프로젝트 CLAUDE.md를 읽고 아키텍처/가이드라인을 파악한 후 검증하라."
fi

codex exec \
  -m "$(config.toml 모델)" \
  -c model_reasoning_effort=high \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  --output-schema schemas/codex_verification_schema.json \
  -o "$VERIFICATION_FILE" \
  -C "$GIT_ROOT" \
  "${SKILL_PROMPT}

   피드백 반영 여부를 검증하라.
   CLAUDE.md ## Code Conventions 섹션의 리뷰 가이드라인을 참조하라.

   ## 원본 이슈
   $ORIGINAL_ISSUES

   ## 적용된 수정
   $FIXES_APPLIED"
```

**Critical 자동 에스컬레이션**: 이전 검증에서 critical 이슈가 있었으면 자동으로 `xhigh`로 전환.

**/fz-searcher 연결**: verify/validate 중 심볼 탐색이 필요할 때(계획에 영향 심볼이 명시되지 않은 경우) /fz-searcher 스킬을 사전 단계로 실행하여 영향 범위를 파악한다.

```bash
SEARCHER_SKILL=$(get_codex_skill "searcher")
if [ -n "$SEARCHER_SKILL" ] && [ -z "$AFFECTED_SYMBOLS" ]; then
  codex exec \
    -c model_reasoning_effort=high \
    --sandbox read-only \
    -C "$GIT_ROOT" \
    "$(cat ~/.codex/skills/${SEARCHER_SKILL}/SKILL.md)

     아래 변경 대상의 영향 심볼과 의존성 체인을 탐색하라.
     ## 변경 대상
     $PLAN_CONTENT"
fi
```

### check -- 커밋 전 빠른 검증

스테이징/언스테이징 변경을 커밋 전에 빠르게 검증합니다.

```bash
cd "$GIT_ROOT" && codex exec review \
  --uncommitted \
  -m gpt-5.5 \
  -c model_reasoning_effort=high \
  --ephemeral \
  -o "$REVIEW_FILE"
```

> `--ephemeral`: 일회성 검증이므로 세션 미저장. 3-Tier 스킬 자동 트리거.

**/fz-fixer 연결**: 리뷰 결과에 수정 제안이 포함된 경우(issues with suggestion 필드 비어있지 않음), /fz-fixer 스킬을 참조하여 수정 전략을 제시한다.

```bash
FIXER_SKILL=$(get_codex_skill "fixer")
if [ -n "$FIXER_SKILL" ] && [ "$HAS_FIXABLE_ISSUES" = "true" ]; then
  codex exec \
    -c model_reasoning_effort=high \
    --sandbox read-only \
    -C "$GIT_ROOT" \
    "$(cat ~/.codex/skills/${FIXER_SKILL}/SKILL.md)

     위 리뷰 결과에서 수정이 필요한 이슈에 대해 Root Cause와 Fix Strategy를 제시하라.
     ## 이슈 목록
     $FIXABLE_ISSUES"
fi
```

### final -- PR 전 최종 리뷰

모든 커밋의 누적 변경을 최고 정밀도로 종합 리뷰합니다.

```bash
# 1차: 전체 리뷰
cd "$GIT_ROOT" && codex exec review \
  --base "$BASE_BRANCH" \
  -m gpt-5.5 \
  -c model_reasoning_effort=xhigh \
  --add-dir "$SHARED_MODULES" \
  --title "[TICKET] PR 전 최종 리뷰" \
  -o "$REVIEW_FILE"

# 2차 (major+ 이슈 존재 시): resume로 심화 검증
if [ "$MAJOR_ISSUES_COUNT" -gt 0 ]; then
  codex exec resume --last \
    "위 리뷰에서 발견된 major 이슈 $MAJOR_ISSUES_COUNT건을 심화 검증하라.
     각 이슈에 대해: 1) 재현 가능성 2) 영향 범위 3) false positive 여부를 판단하라."
fi
```

> `codex exec resume --last`: 1차 리뷰 컨텍스트를 유지한 채 심화 검증. false positive 감소.

**/fz-challenger DA 모드**: `final` 완료 후 major 이상 이슈가 발견되면 DA(Devil's Advocate) 패스를 추가 실행하여 false positive를 제거한다.

```bash
CHALLENGER_SKILL=$(get_codex_skill "challenger")
if [ -n "$CHALLENGER_SKILL" ] && [ "$MAJOR_ISSUES_COUNT" -gt 0 ]; then
  codex exec \
    --output-schema schemas/codex_peer_review_schema.json \
    -c model_reasoning_effort=xhigh \
    --sandbox read-only \
    -o "$DA_REVIEW_FILE" \
    -C "$GIT_ROOT" \
    "$(cat ~/.codex/skills/${CHALLENGER_SKILL}/SKILL.md)

     아래 리뷰 이슈 목록에 대해 Devil's Advocate 분석을 수행하라.
     각 이슈에 agree|challenge|supplement|reverse 판정과 근거를 제시하라.
     ## 이슈 목록
     $MAJOR_ISSUES"
fi
```

### commit -- 특정 커밋 검증

```bash
cd "$GIT_ROOT" && codex exec review \
  --commit "${COMMIT_SHA:-HEAD}" \
  -m gpt-5.5 \
  -c model_reasoning_effort=high \
  --ephemeral \
  -o "$REVIEW_FILE"
```

### adversarial -- Devil's Advocate 리뷰

설계 결정에 도전하는 적대적 리뷰. final의 DA 패스를 독립 실행 가능.

```bash
# Plugin 모드 (우선)
/codex:adversarial-review --base "$BASE_BRANCH" -m gpt-5.5 --json

# CLI 폴백
SKILL_NAME=$(get_codex_skill "challenger")
codex exec -m gpt-5.5 -c model_reasoning_effort=xhigh \
  --sandbox read-only -o "$DA_REVIEW_FILE" -C "$GIT_ROOT" \
  "$(cat ~/.codex/skills/${SKILL_NAME}/SKILL.md)
   현재 변경사항의 설계 결정에 Devil's Advocate 분석을 수행하라."
```

### drift -- 아키텍처 드리프트 전체 스캔

전체 코드베이스를 1M context로 스캔하여 아키텍처 드리프트를 감지합니다.

```bash
SKILL_NAME=$(get_codex_skill "drift-detector")
if [ -n "$SKILL_NAME" ]; then
  SKILL_PROMPT="$(cat ~/.codex/skills/${SKILL_NAME}/SKILL.md)"
else
  SKILL_PROMPT="CLAUDE.md를 읽고 아키텍처 규칙을 파악한 후, 전체 코드베이스의 레이어 위반과 RIBs 역할 위반을 감지하라."
fi

codex exec \
  -m gpt-5.5 \
  -c model_reasoning_effort=high \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  -o "$DRIFT_REPORT_FILE" \
  -C "$GIT_ROOT" \
  "${SKILL_PROMPT}

   전체 코드베이스를 스캔하여 아키텍처 드리프트를 감지하라.
   Critical → Major → Minor 순으로 보고하라."
```

> **권장 실행 시점**: PR 전, 대규모 리팩토링 후.
> **effort**: `high` (기본). xhigh 불필요 — 패턴 탐지는 고추론 불필요.

### plan -- 독립 플랜 생성 (Claude와 교차 비교)

요구사항을 기반으로 Claude 계획과 독립적으로 플랜을 생성합니다.

```bash
REQUIREMENTS="$1"
SKILL_NAME=$(get_codex_skill "planner")
if [ -n "$SKILL_NAME" ]; then
  SKILL_PROMPT="$(cat ~/.codex/skills/${SKILL_NAME}/SKILL.md)"
else
  SKILL_PROMPT="CLAUDE.md를 읽고 프로젝트 패턴을 파악한 후, 요구사항에 대한 독립 구현 계획을 수립하라."
fi

codex exec \
  -m gpt-5.5 \
  -c model_reasoning_effort=xhigh \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  -o "$PLAN_FILE" \
  -C "$GIT_ROOT" \
  "${SKILL_PROMPT}

   ## 요구사항
   ${REQUIREMENTS}

   위 요구사항에 대해 독립적으로 구현 계획을 수립하라.
   Claude 계획을 전달받지 않았으므로 코드베이스를 직접 탐색하여 계획하라."
```

> **C4 원칙**: Claude의 중간 작업물(계획 텍스트)을 전달하지 않는다. 요구사항만 공유.
> **effort**: `xhigh` — 독립 설계이므로 최고 추론력 활용.
> **비교**: 결과를 Claude 계획과 나란히 놓고 `Divergence Points` 섹션 검토.

### micro-eval -- 단일 주장 독립 재평가 (Claim-Type 라우팅)

단일 주장(severity 판단, 분류, 사실 주장 등)을 Codex로 빠르게 독립 재평가합니다.
Full verify/validate보다 **경량** — 수백 토큰 단위 호출로 Claim-Type 라우팅의 "분류/심각도 판단" 카테고리를 처리.

**사용 시점**:
- Claude가 Critical/Major로 판정한 이슈가 실제 그 심각도인지 재확인
- 외부(팀원/Codex 이전 응답) 지적의 유효성 빠른 확인
- "이 주장이 맞는가?" 형태의 단일 이슈 검증
- cross-validation.md Claim-Type 라우팅에서 분류/심각도 판단 → micro-eval로 흐름

**호출**: `codex exec` 공통 패턴 + 다음 차이:
- skill: `challenger` (3-Tier 디스커버리), 폴백: "단일 주장을 독립 판정하라"
- effort: `medium` + `--ephemeral` (경량)
- 입력: `${CLAIM}` + `${CONTEXT_HINT}`
- 출력: `verdict (agree | disagree | partial | needs_verification) + reasoning (1-3문장) + missing_evidence`

**verdict 의미**:
- `agree` / `disagree` / `partial`: 주장 정확/틀림/일부
- `needs_verification`: 증거 부족 — 답변 차단 (Anti-Pattern #6, BEC fail-closed)

> **의미론적 결합**: `needs_verification` verdict = `modules/uncertainty-verification.md` Default-Deny 조건(증거 부족). BEC fail-closed 차단 의미와 동일. micro-eval 결과가 `needs_verification`이면 해당 주장은 fz-plan/fz-code의 `[verified]` 태그 게이트에서 자동 차단된다.

> **effort**: `medium` (기본). 경량 호출 — 수백 토큰 단위.
> **사용 시점**: 단일 심각도/분류 주장 → full review 대신 경량 호출로 교차 검증.
> **비용**: `[미검증: 운영 초기 호출 후 기준선 설정]` — Phase A 운영 후 실측.

### config -- 설정 조회

`codex --version`, `~/.codex/config.toml`, `codex features list`, `ls ~/.codex/skills/`, `codex mcp list` 조회.
Plugin 상태: `codex mcp list 2>/dev/null | grep plugin` (설치 시 `/codex:setup --json`).

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
BAD: codex exec review → "LGTM" → 그대로 approved (Claude 독립 판단 없음, 교차 검증 아님)
GOOD: codex 3 issues + Claude 독립 1 신규 = 4 issues 합산 + verdict 판정
```

```
서브커맨드 매핑: 코드 리뷰→`codex exec review -o`, 계획 검증→`codex exec --output-schema`, 심화→`codex exec resume --last`
```

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
