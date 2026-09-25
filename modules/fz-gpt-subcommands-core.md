# fz-gpt 서브커맨드 (Core 4개) — review / verify / validate / check

> **Scope of Applicability**: `fz-gpt` SKILL.md의 주력 서브커맨드 4개. fz-review Phase 5 (review/check), fz-plan Phase 2 (verify), fz-review Phase 5.5 (validate) 위임 시 본 모듈 참조.
>
> **Purpose**: 가장 자주 사용되는 4개 서브커맨드(주력) 정의 + verdict contract + 후속 fz-fixer 연결. 보조 7개는 `modules/fz-gpt-subcommands-aux.md` 참조.

## 목차

**review** (주력, fz-review P5) · **verify** (Q1-Q8, fz-plan P2) · **verify-gates** (게이트 원장 판정, fz-plan P2 **추가** 호출) · **validate** (역검증, fz-review P5.5) · **check** (verdict contract: pass/warn/fail)

> ⛔ **아래 예시는 전부 래퍼(`scripts/gpt-exec.sh`) 호출이다** — 서브커맨드별 *차이점*(모드·effort·schema·프롬프트)만 보인다. ⛔ GPT CLI 를 직접 부르지 않는다.
> 래퍼가 `modules/fz-gpt-bash-hygiene.md` 의 교훈을 대신 처리한다: `< /dev/null` (29차 hang 방지) + trust check (30차) + skip flag + `--out` readback + `--` 구분자 + (review 모드) §5.5 Base Verification Gate.
> 프롬프트는 `--prompt-file` 로만 받는다 — 아래 `P_*` 는 앞 줄에서 heredoc 으로 쓴 임시 파일이다. 읽기 전용은 래퍼가 모든 호출에 `-c sandbox_mode="read-only"` 로 **강제**한다(사용자 config 보다 우선) — 옛 `--sandbox read-only` 플래그는 쓰지 않는다.

## review -- 코드 리뷰 (주력)

fz-review의 Phase 5 GPT 부분. **Plugin 우선 → CLI 폴백.**

```bash
# Plugin 모드 (우선)
/codex:review --base "$BASE_BRANCH" --json

# 래퍼 모드 (폴백 — Plugin 미설치). 공유 모듈도 읽는다(read-only 는 전 디스크 읽기 허용)
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" review --cd "$GIT_ROOT" --out "$REVIEW_FILE" --base "$BASE_BRANCH" --effort high \
  --gpt-skill reviewer --gpt-skill-path unknown   # 자동 트리거 — 로드 확인 불가
```

**래퍼 주요 옵션**: `--out`(파일 캡처) · `--effort` · `--schema` · `--ephemeral`(일회성). ⛔ 모델은 넘기지 않는다(`config.toml` SSOT)

**공유 모듈**: `--add-dir` 는 **쓰기 가능 디렉토리**를 늘리는 플래그다(CLI help: *"Additional directories that should be writable"*). fz GPT 호출은 read-only 강제라 쓰지 않는다 — read-only 도 전 디스크를 **읽을 수** 있어 공유 모듈을 읽는 데 필요 없다 (2026-09-25 실측). 모듈화 리뷰에서 공유 모듈·소비자 코드를 꼭 보게 하려면 프로젝트 `CLAUDE.md` `## Shared Modules` 경로를 exec 프롬프트에 적는다 — review 모드는 diff 를 기준으로 필요한 파일을 스스로 연다.

**⚠️ `review`는 flag-only** (G7/#7 회고 #8): GPT CLI review 모드는 PROMPT positional을 받지 않는다 — 리뷰 대상 선택은 플래그(`--base`/`--uncommitted`/`--commit`)로만. 프롬프트 주입이 필요하면 review 모드가 아니라 `gpt-exec.sh exec --prompt-file`(verify 형식, §verify) 사용. 래퍼는 review 에 프롬프트를 넘기지 않아 이 충돌을 구조적으로 막는다.

## verify -- 계획 검증

fz-plan의 Phase 2. **`gpt-exec.sh exec` + `--schema` 사용.**

```bash
SKILL_PATH=$(get_gpt_skill_path "architect" "$FZ_PLUGIN_ROOT")
if [ -n "$SKILL_PATH" ]; then
  SKILL_PROMPT="$(cat "$SKILL_PATH")"
else
  SKILL_PROMPT="프로젝트 CLAUDE.md를 읽고 아키텍처/가이드라인을 파악한 후 검증하라."
fi

cat > "$P_VERIFY" <<EOF
${SKILL_PROMPT}

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
Q8 함의 커버리지: 계획이 지시의 "문자적 범위"뿐 아니라 "의미론적 범위"를 커버하는가? 제거/변경 대상이 존재하게 된 이유(원인 코드)까지 범위에 포함됐는가? 지시로 인해 무효화되는 코드(결과 코드)가 처리됐는가? verdict: pass/warn/fail + reasoning. (참조: modules/lead-reasoning.md)

각 질문에 대해 verdict(pass/warn/fail)와 reasoning을 제시하라.
계획의 리스크 매트릭스가 빈약하거나 누락된 경우 반드시 지적하라.
Anti-Pattern Constraints가 있으면 각 금지 패턴의 실효성을 검증하라.
EOF
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$GIT_ROOT" --out "$REVIEW_FILE" --prompt-file "$P_VERIFY" \
  --effort high --schema "${FZ_PLUGIN_ROOT}/schemas/gpt_review_schema.json" \
  --gpt-skill architect --gpt-skill-path "$SKILL_PATH"
```

## verify-gates -- 게이트 원장 판정 (fz-plan Phase 2 추가 호출)

⛔ **`verify`를 대체하지 않는다 — 별도 호출로 추가한다.** `gpt_gate_verdict_schema`에는 `issues`·`verdict`가 없어, 교체하면 fz-plan의 Issue Tracker 기록·scope challenge·Gate 2 승인 입력이 사라진다.

발동: 원장이 있을 때만. 원장이 없으면 게이트 판정이 무의미하다.

⛔ **대상 원장은 호출자가 정한다** — 특정 파일명에 묶지 않는다.

| 호출자 | 원장 | 시점 |
|---|---|---|
| fz-plan Phase 2 | `{WORK_DIR}/gates/plan.draft.md` | 확정 **전** — 판정을 반영해 확정한다 |
| fz-review Phase 5.5 | `{WORK_DIR}/gates/plan.md` | 확정 **후** — 변경된 코드 기준 재판정 |

```bash
LEDGER="{호출자가 정한 원장}"          # plan: gates/plan.draft.md · review: gates/plan.md
[ -f "$LEDGER" ] || exit 0   # 원장 없으면 이 호출 자체를 생략

# ⛔ 정본 경로로 부른다 — 상대 경로는 cwd 가 플러그인 루트가 아닐 때 조용히 깨진다
#    (`FZ_PLUGIN_ROOT` 는 `scripts/resolve-plugin-root.sh` 로 해석한다)
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec \
  --cd "$GIT_ROOT" \
  --out "$GATE_VERDICT_FILE" \
  --prompt-file "$PROMPT" \
  --schema "${FZ_PLUGIN_ROOT}/schemas/gpt_gate_verdict_schema.json" \
  --effort high
```

프롬프트에 **원장 경로와 내용을 함께** 넣는다. 현재 `verify` 템플릿에는 WORK_DIR·ledger 변수가 없어 그대로는 게이트를 볼 수 없다.

```
[원장 경로] {LEDGER 절대경로}
[원장 내용]
{cat "$LEDGER"}

각 게이트마다 판정 1행. ⛔ 통과한 게이트도 표현하라 — 누락은 미판정이며 통과가 아니다.
id·title·kind 는 원장 줄과 **글자 그대로** 복사하라(축약·요약 금지 — `--verdict-check` 가 stale 응답으로 거부한다). title 이 100자를 넘어도 그대로 쓴다.
축: measurement_fit(CHECK 가 제목이 말하는 것을 측정하는가) · noninteractive · rerunnable ·
    determinism · side_effects(서술)
```

### ⛔ 사후 검증 (스키마만으로는 보장되지 않는다)

`gpt_gate_verdict_schema`는 `gates: []`(빈 배열)·중복 id·원장에 없는 id·거짓 `summary` 합계를 **전부 통과시킨다.** 호출자가 대조한다.

이 대조는 **눈으로 하지 않는다** — 판정기가 한다.

```bash
python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py" --verdict-check "$GATE_VERDICT_FILE" "$LEDGER"
```

| 검사 | 왜 필요한가 |
|------|------------|
| 게이트 수 == 원장 게이트 수 | 빈 배열이 "문제 없음"으로 읽히면 판정 자체가 사라진다 |
| id 집합 일치 + 중복 없음 | ⛔ 개수만 세면 중복이 누락을 가린다 — `G1` 두 번 + `G3` 없음이 3개로 보인다 |
| `(id, title, kind)` 일치 | ⛔ id 만 보면 **stale 응답**이 통과한다. 제목이 바뀌어도 id 는 그대로여서 옛 oracle 판정이 새 oracle 에 붙는다 |
| `summary` 를 배열에서 **재계산**해 비교 | 신고값을 믿으면 보고가 거짓이 된다. 음수끼리 상쇄해 합계만 맞추는 것도 막는다 |

exit 1 이면 재호출 1회 후 **미판정으로 기록**하고 Lead가 판단한다 — 조용히 통과시키지 않는다.

## validate -- 피드백 역검증

fz-review의 Phase 5.5. **`gpt-exec.sh exec` + `--schema` 사용.**

```bash
SKILL_PATH=$(get_gpt_skill_path "guardian" "$FZ_PLUGIN_ROOT")
if [ -n "$SKILL_PATH" ]; then
  SKILL_PROMPT="$(cat "$SKILL_PATH")"
else
  SKILL_PROMPT="프로젝트 CLAUDE.md를 읽고 아키텍처/가이드라인을 파악한 후 검증하라."
fi

cat > "$P_VALIDATE" <<EOF
${SKILL_PROMPT}

피드백 반영 여부를 검증하라.
CLAUDE.md ## Code Conventions 섹션의 리뷰 가이드라인을 참조하라.

## 원본 이슈
$ORIGINAL_ISSUES

## 적용된 수정
$FIXES_APPLIED
EOF
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$GIT_ROOT" --out "$VERIFICATION_FILE" --prompt-file "$P_VALIDATE" \
  --effort high --schema "${FZ_PLUGIN_ROOT}/schemas/gpt_verification_schema.json" \
  --gpt-skill guardian --gpt-skill-path "$SKILL_PATH"
```

**Critical 자동 에스컬레이션**: 이전 검증에서 critical 이슈가 있었으면 자동으로 `xhigh`로 전환.

**/fz-searcher 연결**: verify/validate 중 심볼 탐색이 필요할 때(계획에 영향 심볼이 명시되지 않은 경우) /fz-searcher 스킬을 사전 단계로 실행하여 영향 범위를 파악한다.

```bash
SEARCHER_SKILL_PATH=$(get_gpt_skill_path "searcher" "$FZ_PLUGIN_ROOT")
if [ -n "$SEARCHER_SKILL_PATH" ] && [ -z "$AFFECTED_SYMBOLS" ]; then
  { cat "${SEARCHER_SKILL_PATH}"; cat <<EOF

아래 변경 대상의 영향 심볼과 의존성 체인을 탐색하라.
## 변경 대상
$PLAN_CONTENT
파일을 수정하지 마라(읽기 전용 분석).
EOF
  } > "$P_SEARCH"
  "${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$GIT_ROOT" --out "$SEARCH_FILE" --prompt-file "$P_SEARCH" --effort high \
    --gpt-skill searcher --gpt-skill-path "$SEARCHER_SKILL_PATH"
fi
```

## check -- 커밋 전 빠른 검증

스테이징/언스테이징 변경을 커밋 전에 빠르게 검증합니다.

```bash
"${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" review --cd "$GIT_ROOT" --out "$REVIEW_FILE" --uncommitted --effort high --ephemeral \
  --gpt-skill reviewer --gpt-skill-path unknown   # 자동 트리거 — 로드 확인 불가
```

> `--ephemeral`: 일회성 검증이므로 세션 미저장. 3-Tier 스킬 자동 트리거.

### check verdict contract (호출자 분기 규칙)

`/fz-gpt check` 결과는 다음 verdict 중 하나로 분류 (호출자 SKILL — fz-fix 등 — 이 분기 처리):

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
FIXER_SKILL_PATH=$(get_gpt_skill_path "fixer" "$FZ_PLUGIN_ROOT")
if [ -n "$FIXER_SKILL_PATH" ] && [ "$HAS_FIXABLE_ISSUES" = "true" ]; then
  { cat "${FIXER_SKILL_PATH}"; cat <<EOF

위 리뷰 결과에서 수정이 필요한 이슈에 대해 Root Cause와 Fix Strategy를 제시하라.
## 이슈 목록
$FIXABLE_ISSUES
파일을 수정하지 마라(읽기 전용 분석).
EOF
  } > "$P_FIX"
  "${FZ_PLUGIN_ROOT}/scripts/gpt-exec.sh" exec --cd "$GIT_ROOT" --out "$FIXER_FILE" --prompt-file "$P_FIX" --effort high \
    --gpt-skill fixer --gpt-skill-path "$FIXER_SKILL_PATH"
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

- Progressive Disclosure Level 3 (fz-gpt 호출 시 *명시 Read*. 자동 로드 X — GPT 검증 §추가 발견 정정)
- 200줄 한도 — 본 모듈은 verify Q1-Q8 + verdict contract 포함으로 약간 초과 가능
