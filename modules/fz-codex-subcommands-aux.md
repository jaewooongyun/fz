# fz-codex 서브커맨드 (Aux 7개) — final / commit / adversarial / drift / plan / micro-eval / config

> **Scope of Applicability**: `fz-codex` SKILL.md의 보조 서브커맨드 7개. PR 전 최종 리뷰 (final), 단일 커밋 검증 (commit), Devil's Advocate (adversarial), 아키텍처 드리프트 (drift), 독립 플랜 (plan), 단일 주장 재평가 (micro-eval), 설정 조회 (config).
>
> **Purpose**: Core 4개(`modules/fz-codex-subcommands-core.md` — review/verify/validate/check) 외의 보조 서브커맨드 정의.

## 목차

- **final** — PR 전 최종 리뷰 (resume --last 심화)
- **commit** — 특정 커밋 검증
- **adversarial** — Devil's Advocate 리뷰
- **drift** — 아키텍처 드리프트 전체 스캔
- **plan** — 독립 플랜 생성 (C4 원칙)
- **micro-eval** — 단일 주장 독립 재평가 (claim-type 라우팅)
- **config** — 설정 조회

> ⛔ **아래 codex exec 예시는 축약형** (서브커맨드별 *차이점*만 표시 — 가독성 우선). **raw 복붙 금지**.
> 실제 실행 시 반드시 `modules/fz-codex-bash-hygiene.md` §6 Standard Wrapper Template 적용:
> `< /dev/null` (29차 hang 방지) + trust check (30차) + skip flag + `-o` readback + (git diff 분석 시) §5.5 Base Verification Gate.
> 예시의 `codex exec ...`는 *wrapper의 §3 표준 호출 부분*에 해당하는 차이점만 보여준다 (29/30차 hang/sandbox 재발 차단 — Codex 검증 §Blind Spot 1).

## final -- PR 전 최종 리뷰

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

## commit -- 특정 커밋 검증

```bash
cd "$GIT_ROOT" && codex exec review \
  --commit "${COMMIT_SHA:-HEAD}" \
  -m gpt-5.5 \
  -c model_reasoning_effort=high \
  --ephemeral \
  -o "$REVIEW_FILE"
```

## adversarial -- Devil's Advocate 리뷰

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

## drift -- 아키텍처 드리프트 전체 스캔

전체 코드베이스를 1M context로 스캔하여 아키텍처 드리프트를 감지합니다.

```bash
SKILL_NAME=$(get_codex_skill "drift")
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

## plan -- 독립 플랜 생성 (Claude와 교차 비교)

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

## micro-eval -- 단일 주장 독립 재평가 (Claim-Type 라우팅)

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

## config -- 설정 조회

`codex --version`, `~/.codex/config.toml`, `codex features list`, `ls ~/.codex/skills/`, `codex mcp list` 조회.
Plugin 상태 (Cbug-1 수정): `grep '^\[plugins\.' ~/.codex/config.toml && ls ~/.codex/plugins/cache/*/`. MCP server (`codex mcp list`)는 plugin과 다른 계층이므로 config.toml + cache 동시 확인.

---

## 참조 스킬

| 스킬 | 사용 서브커맨드 |
|------|----------------|
| /fz-review | Phase 5 → final (PR 전), commit (단일 커밋) |
| /fz-pr | PR 생성 전 → final |
| /fz-plan | TEAM 모드 → plan (독립 비교), micro-eval (claim 재평가) |
| /fz-manage | drift (전체 스캔), config (설정 조회) |

## 설계 원칙

- Progressive Disclosure Level 3 (fz-codex 호출 시 *명시 Read*. 자동 로드 X — Codex 검증 §추가 발견 정정)
- 200줄 한도 — 본 모듈은 7개 서브커맨드 + 보조 자료로 한도 약간 초과 가능
