---
name: fz-codex
description: >-
  Codex CLI를 통한 독립적 코드/계획 검증 및 상호검증 모듈.
  Use when verifying plans, reviewing code, or cross-validating changes with Codex.
user-invocable: true
argument-hint: "[review|verify|validate|check|final] [대상]"
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
  - "codex|교차검증"
  - "codex|cross-validate|verify"
model-strategy:
  main: null
  verifier: sonnet
---

# /fz-codex - Codex CLI 상호검증 스킬

> **행동 원칙**: Codex CLI(0.111.0+, gpt-5.4)의 `codex exec review`(구조화 출력 + git diff 통합)와 `codex exec`(`--output-schema`)를 활용하여 독립적 교차 검증을 수행한다.

## 개요

> 서브커맨드: verify | review | validate | check | final | commit | config

- **`codex exec review`**: git diff + 구조화 출력(`--json`, `-o`) + 모델 명시(`-m`) — review/check/final/commit
- **`codex exec`**: 프롬프트 기반 검증 + `--output-schema` — verify/validate
- **`--add-dir`**: 모노레포 공유 모듈 컨텍스트 확장 (TvingUI, tving-common 등)
- **Codex 네이티브 스킬**: 3-Tier 디스커버리로 역할 기반 매칭
- **Workspace memory**: 프로젝트별 리뷰 패턴 학습 → 반복 이슈 감지 정확도 향상

## 사용 시점

```bash
/fz-codex review                    # 코드 리뷰 (develop 대비)
/fz-codex review --base main        # 특정 브랜치 대비 리뷰
/fz-codex verify "계획 검증해줘"     # 구현 계획 검증
/fz-codex validate "피드백 확인해줘"  # 피드백 반영 역검증
/fz-codex check                     # 커밋 전 빠른 검증 (uncommitted)
/fz-codex final                     # PR 전 최종 종합 리뷰
/fz-codex commit                    # 최근 커밋 검증
/fz-codex drift                     # 전체 코드베이스 아키텍처 드리프트 스캔
/fz-codex plan "요구사항"            # Claude와 독립적인 플랜 생성 (교차 비교용)
/fz-codex config                    # 설정 조회
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/cross-validation.md | 검증 게이트, get_codex_skill() 3-Tier 디스커버리, GIT_ROOT 추출 |

## GIT_ROOT 추출

> CLAUDE.md `## Directory Structure`에서 동적 추출. 상세: modules/cross-validation.md 참조.

## Codex 스킬 3-Tier 디스커버리

> canonical 정의: modules/cross-validation.md 참조.

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

---

## 서브커맨드

### review -- 코드 리뷰 (주력)

fz-review의 Phase 5 Codex 부분. **`codex exec review` 사용 (0.111.0+).**

```bash
cd "$GIT_ROOT" && codex exec review \
  --base "$BASE_BRANCH" \
  -m gpt-5.4 \
  -c model_reasoning_effort=high \
  --add-dir "$SHARED_MODULES" \
  --title "[TICKET] 코드 리뷰" \
  -o "$REVIEW_FILE"
```

**`codex exec review` 장점 (기존 `codex review` 대비)**:
- `-m`: 호출별 모델 명시 → config.toml 의존 제거
- `-o`: 최종 리뷰 텍스트 파일 캡처 (tee 파이핑 불필요, 누락 방지)
- `--json`: JSONL 이벤트 스트림 (디버깅/파싱용, 선택)
- `--add-dir`: 모노레포 공유 모듈(TvingUI, tving-common) 접근 → cross-module 분석
- Git 변경 자동 인식 + 3-Tier 스킬 자동 트리거 유지
- `--ephemeral`: 일회성 검증 시 세션 잔류 방지 (선택)

**`--add-dir` 패턴** (TVING 모노레포):
```bash
SHARED_MODULES="$GIT_ROOT/TvingUI $GIT_ROOT/tving-common $GIT_ROOT/Managers"
# --add-dir는 반복 가능: --add-dir dir1 --add-dir dir2
```

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
  --output-schema ~/.claude/schemas/codex_review_schema.json \
  -o "$REVIEW_FILE" \
  -C "$GIT_ROOT" \
  "${SKILL_PROMPT}

   이 구현 계획을 검증하라.
   CLAUDE.md ## Guidelines 섹션의 가이드라인을 참조하라.

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
  --output-schema ~/.claude/schemas/codex_verification_schema.json \
  -o "$VERIFICATION_FILE" \
  -C "$GIT_ROOT" \
  "${SKILL_PROMPT}

   피드백 반영 여부를 검증하라.
   CLAUDE.md ## Guidelines 섹션의 리뷰 가이드라인을 참조하라.

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
  -m gpt-5.4 \
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
  -m gpt-5.4 \
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
    --output-schema ~/.claude/schemas/codex_peer_review_schema.json \
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
  -m gpt-5.4 \
  -c model_reasoning_effort=high \
  --ephemeral \
  -o "$REVIEW_FILE"
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
  -m gpt-5.4 \
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
  -m gpt-5.4 \
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

### config -- 설정 조회

```bash
echo "=== Codex CLI $(codex --version) ==="
cat ~/.codex/config.toml

echo "=== Codex Features ==="
codex features list 2>/dev/null | grep -E "stable|experimental"

echo "=== Codex Skills ==="
ls ~/.codex/skills/ | grep -v "^\."

echo "=== Codex MCP ==="
codex mcp list 2>/dev/null || echo "MCP 미설정"
```

---

## Issue Tracker 연동

검증 결과를 자동으로 Issue Tracker에 기록합니다 (참조: modules/session.md).

```bash
# --output-schema (codex exec) 사용 시: 이미 JSON이므로 직접 jq 처리
# codex exec review -o 사용 시: 최종 리뷰 텍스트 파일 → Claude가 파싱하여 Issue Tracker에 기록

jq --arg phase "$PHASE" --slurpfile review "$REVIEW_FILE" '
  .issues += ($review[0].issues | map(. + {
    "discovered_in": $phase, "status": "open"
  }))
' "$TRACKER_FILE" > "${TRACKER_FILE}.tmp" && mv "${TRACKER_FILE}.tmp" "$TRACKER_FILE"
```

---

## Gate: Codex Verification Complete
- [ ] 서브커맨드 실행 완료?
- [ ] Issue Tracker에 결과 기록?
- [ ] verdict 판정 (approved/rejected/conditional)?

---

## Few-shot 예시

```
BAD (Codex 출력 무비판 수용):
codex exec review → "LGTM" → 그대로 approved 판정
→ Claude 독립 판단 없이 Codex 결과만 전달. 교차 검증 아님.

GOOD (교차 검증):
codex exec review → Issue 3개 발견
Claude 독립 분석 → Issue 2개 중복 + 1개 새 Issue 발견
→ 합산: 4개 Issue (Codex 3 + Claude 1, 중복 2 제외)
→ 구조화된 보고 + verdict 판정
```

```
BAD: 계획 검증에 `codex exec review` 사용 → review는 코드 리뷰용.
GOOD: 코드 리뷰→`codex exec review -o`, 계획 검증→`codex exec --output-schema`, 심화→`codex exec resume --last`
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
| Codex CLI 통신 실패 | 컨텍스트 축소 후 재시도 | /sc:analyze 단독 |
| `codex exec review` 실패 | `codex exec` + diff 인라인 | 수동 분석 |
| JSON 파싱 실패 | `-o` 파일 캡처 폴백 | Claude 분석 |
| 모델 미지원 (`gpt-5.4`) | config.toml 모델로 폴백 (`-m` 제거) | -- |
| 3회 연속 실패 | 사용자 에스컬레이션 | -- |

## Completion → Next

검증 완료 후 호출 스킬로 결과를 반환한다:
- verify → /fz-plan
- review/check/final/commit → /fz-review
- validate → /fz-review

## 관련 스키마

- `~/.claude/schemas/codex_base_issue_schema.json` -- 공통 issue 정의 (severity, confidence, unified_category, alternatives)
- `~/.claude/schemas/codex_review_schema.json` -- review/verify/validate/check/final/commit 응답
- `~/.claude/schemas/codex_verification_schema.json` -- validate 역검증 응답
- `~/.claude/schemas/codex_peer_review_schema.json` -- peer-review 에이전트 응답

## 관련 Codex 스킬

- 3-Tier 디스커버리로 결정 (Tier 1: CLAUDE.md ## Codex Skills, Tier 2: fz-*, Tier 3: 인라인)

## sc: 활용 (SuperClaude 연계)

- `sc:reflect`: Codex 결과 교차 검증
- `sc:analyze`: 코드 분석 보조 (Codex 결과 보완)
- `sc:troubleshoot`: Codex CLI 통신 문제 대응
