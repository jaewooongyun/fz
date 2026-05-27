# fz-codex 서브커맨드 (Core 4개) — review / verify / validate / check

> **Scope of Applicability**: `fz-codex` SKILL.md의 주력 서브커맨드 4개. fz-review Phase 5 (review/check), fz-plan Phase 2 (verify), fz-review Phase 5.5 (validate) 위임 시 본 모듈 참조.
>
> **Purpose**: 가장 자주 사용되는 4개 서브커맨드(주력) 정의 + verdict contract + 후속 fz-fixer 연결. 보조 7개는 `modules/fz-codex-subcommands-aux.md` 참조.

## 목차

**review** (주력, fz-review P5) · **verify** (Q1-Q8, fz-plan P2) · **validate** (역검증, fz-review P5.5) · **check** (verdict contract: pass/warn/fail)

> ⛔ **아래 codex exec 예시는 축약형** (서브커맨드별 *차이점*만 표시 — 가독성 우선). **raw 복붙 금지**.
> 실제 실행 시 반드시 `modules/fz-codex-bash-hygiene.md` §6 Standard Wrapper Template 적용:
> `< /dev/null` (29차 hang 방지) + trust check (30차) + skip flag + `-o` readback + (git diff 분석 시) §5.5 Base Verification Gate.
> 예시의 `codex exec ...`는 *wrapper의 §3 표준 호출 부분*에 해당하는 차이점만 보여준다 (29/30차 hang/sandbox 재발 차단 — Codex 검증 §Blind Spot 1).

## review -- 코드 리뷰 (주력)

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

## verify -- 계획 검증

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
   계획의 핵심 설계 결정에 대해 아래 8가지 질문을 독립적으로 평가하라.
   계획에 이미 리스크 매트릭스가 있더라도, 동의 여부와 무관하게 자체 판단하라.

   Q1 다중성: 제안된 설계가 1개일 때와 N개일 때 동일하게 작동하는가?
   Q2 소비자 영향: 변경의 소비자(상위 레이어)에 새 분기/타입/프로토콜이 필요한가?
   Q3 복잡도 이동: 한 레이어의 단순화가 다른 레이어의 복잡도 증가로 이어지는가?
   Q4 경계 케이스: 이 추상화가 커버하지 못하는 케이스는 무엇이고, 대안은?
   Q5 접근 경계: '차단/제거/캡슐화'를 의도한 접근 경로가 실제로 차단되는가? access modifier(public/internal/private)가 의도와 일치하는가? 기존 코드가 이벤트 채널을 우회하여 직접 호출하는 경로가 남아있지 않은가?
   Q6 이벤트 스코프: 이벤트/로그 전송 설계가 포함되어 있다면, 각 이벤트가 측정 목적에 부합하는가? 이벤트 발화 위치의 컨텍스트가 측정 대상과 일치하는가?
   Q7 소비자 코드 품질: 모듈화/캡슐화 작업인 경우, 앱 측 소비자 코드가 모듈의 public API를 올바르게 사용하는가? 앱 생명주기 진입점(AppDelegate, SceneDelegate, UIWindow extension)의 모듈 연동이 정상인가? 모듈화 이전의 레거시 패턴이 앱에 남아있지 않은가?
   Q8 함의 커버리지: 계획이 지시의 \"문자적 범위\"뿐 아니라 \"의미론적 범위\"를 커버하는가? 제거/변경 대상이 존재하게 된 이유(원인 코드)까지 범위에 포함됐는가? 지시로 인해 무효화되는 코드(결과 코드)가 처리됐는가? verdict: pass/warn/fail + reasoning. (참조: modules/lead-reasoning.md)

   각 질문에 대해 verdict(pass/warn/fail)와 reasoning을 제시하라.
   계획의 리스크 매트릭스가 빈약하거나 누락된 경우 반드시 지적하라.
   Anti-Pattern Constraints가 있으면 각 금지 패턴의 실효성을 검증하라."
```

## validate -- 피드백 역검증

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

## check -- 커밋 전 빠른 검증

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

### check verdict contract (호출자 분기 규칙)

`/fz-codex check` 결과는 다음 verdict 중 하나로 분류 (호출자 SKILL — fz-fix 등 — 이 분기 처리):

| verdict | 조건 | 호출자 권장 행동 |
|---------|------|----------------|
| `pass` | critical/major issue 0건 | 다음 단계 진행 |
| `warn` | warning issue 1건+ but critical/major 0건 | 사용자 보고 + 진행 옵션 |
| `fail` | critical/major issue 1건+ | 차단, 사용자 결정 필수 |

**판정 grep** (`$REVIEW_FILE`에 적용, `grep -Eiq`로 case-insensitive 강제):
- `grep -Eiq 'severity.*(critical|major)' "$REVIEW_FILE"` 매칭 → `fail`
- 위 매칭 0건 + `grep -Eiq 'severity.*(minor|suggestion)' "$REVIEW_FILE"` 매칭 → `warn`
- 둘 다 0건 + 파일 존재 + 비어있지 않음 → `pass`
- 파일 없음 또는 빈 파일 → `warn` (false PASS 방지)

> severity enum: `critical | major | minor | suggestion` (review schemas 정의). `warn`/`warning`은 매칭 대상 아님.

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

---

## 참조 스킬

| 스킬 | 사용 서브커맨드 |
|------|----------------|
| /fz-review | Phase 5 → review/check, Phase 5.5 → validate |
| /fz-plan | Phase 2 → verify |
| /fz-fix | check verdict contract 분기 처리 |
| /fz | TEAM 모드 cross-validation 게이트 주입 시 verify/validate |

## 설계 원칙

- Progressive Disclosure Level 3 (fz-codex 호출 시 *명시 Read*. 자동 로드 X — Codex 검증 §추가 발견 정정)
- 200줄 한도 — 본 모듈은 verify Q1-Q8 + verdict contract 포함으로 약간 초과 가능
