# 스킬 테스팅 가이드

> fz-* 스킬의 품질을 측정 가능하게 보장하는 테스트 방법론.
> **근거**: Anthropic Agent Skills 공식 + 검증 기반 테스트 원칙(verifier oracle · fresh-context 검증).
> **Sources (last audited: 2026-07-25) — Tier 1:** code.claude.com/docs/en/{skills, sub-agents, best-practices, changelog} · platform.claude.com/.../prompting-claude-opus-5 · .../effort. 권위 자료 단일 참조점: `guides/llm-references.md`.

---

## 0. 검증 기반 테스트 원칙 (verified)

스킬 테스트의 신뢰성은 두 원칙에서 나온다:

1. **oracle은 객관 pass/fail로** — "looks done" 자가판정은 환각을 통과시킨다. Functional Test의 합격 판정은 test/build exit code·lint·script diff 같은 **실행 가능한 pass/fail**로 닫는다 [verified: code.claude.com/docs/en/best-practices].
2. **검증자 ≠ 구현자** — 스킬 출력을 그 스킬을 만든 컨텍스트가 채점하면 안 된다. **fresh-context 검증자**(별도 세션/에이전트가 diff+기준만 보고 판정)가 self-critique보다 우월 [verified: code.claude.com/docs/en/sub-agents].

> 이 두 원칙이 아래 §1~§8 전 절차의 바탕이다.

---

## 1. 테스트 3단계 프레임워크

### 1.1 Triggering Test — 트리거 정확도 측정

스킬이 올바른 쿼리에서 트리거되는지 확인한다.

**절차:**
1. should-trigger + should-NOT-trigger 쿼리 목록을 작성한다 (최소 10개)
2. 각 쿼리를 Claude에 입력하고 스킬 트리거 여부를 기록한다
3. 트리거율을 계산한다: `정확 트리거 수 / 전체 테스트 수`
4. 목표: 관련 쿼리의 90% 이상에서 정확 트리거

> ⚠️ 스킬이 많으면 description이 listing budget에 맞춰 자동 축약되어 트리거 정확도가 떨어질 수 있다 — `skillListingBudgetFraction`/`SLASH_COMMAND_TOOL_CHAR_BUDGET` 확인 [verified: code.claude.com/docs/en/skills].

**Few-shot: fz-fix 트리거 테스트**

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "버그 고쳐줘" | trigger | 핵심 유스케이스 |
| "크래시 원인 찾아줘" | trigger | 디버깅 |
| "이 에러 해결해줘" | trigger | 에러 수정 |
| "빌드 실패 고쳐줘" | trigger | 빌드 에러 |
| "새 기능 만들어줘" | NOT trigger | → fz-code |
| "코드 리뷰해줘" | NOT trigger | → fz-review |
| "아키텍처 설계해줘" | NOT trigger | → fz-plan |

**Few-shot: fz-codex 트리거 테스트**

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "코드 교차검증해줘" | trigger | 핵심 유스케이스 |
| "codex로 리뷰해줘" | trigger | 명시적 도구 지정 |
| "PR 전 최종 검증" | trigger | final 서브커맨드 |
| "계획 검증해줘" | trigger | verify 서브커맨드 |
| "코드 직접 고쳐줘" | NOT trigger | → fz-fix |
| "새 스킬 만들어줘" | NOT trigger | → fz-skill |

### 1.2 Functional Test — Given/When/Then 형식

스킬이 유효한 출력을 생성하는지 확인한다.

**테스트 요소:**
- 유효 출력 생성 확인
- 에러 핸들링 동작 확인
- 엣지 케이스 커버리지

> ⭐ **합격 oracle (§0-1)**: "Then"은 가능한 한 객관 pass/fail로 기술한다 — "빌드 통과"(exit code), "lint 0 경고", "Gate 체크리스트 N/N". 주관 판정("잘 동작함")은 fresh-context 검증자(§0-2)에 맡긴다.

**Few-shot: fz-code Functional Test**

| Given | When | Then |
|-------|------|------|
| 계획 문서가 존재 | `/fz-code "Phase 1 구현"` | Phase별 코드 생성 + 빌드 통과 |
| 계획 없이 호출 | `/fz-code "구현해줘"` | 계획 부재 경고 + fz-plan 안내 |
| 빌드 실패 발생 | 구현 중 컴파일 에러 | 에러 분석 + 자동 수정 시도 (최대 3회) |

**Few-shot: fz-codex Functional Test**

| Given | When | Then |
|-------|------|------|
| Git diff 존재 | `/fz-codex review` | `codex review --base` 실행 + 이슈 보고 |
| Codex CLI 미설치 | `/fz-codex review` | 에러 감지 + sc:analyze 폴백 |
| Critical 이슈 발견 | `/fz-codex final` | xhigh 에스컬레이션 + DA 패스 자동 실행 |
| 3-Tier 스킬 부재 | `/fz-codex verify` | Tier 3 인라인 프롬프트로 폴백 |

### 1.3 Performance Comparison — Before/After 비교

스킬 없이 vs 스킬 있을 때를 비교 측정한다.

**측정 항목:**
- 메시지 수 (API 라운드트립)
- 토큰 소비량
- 작업 완료율
- 사용자 개입 횟수

**비교 테이블 템플릿:**

| 항목 | 스킬 없이 | 스킬 있을 때 | 개선율 |
|------|----------|-------------|--------|
| 메시지 수 | {N} | {M} | {%} |
| 토큰 소비 | {X}K | {Y}K | {%} |
| 작업 완료 | {성공/실패/부분} | {성공/실패/부분} | — |
| 사용자 개입 | {N}회 | {M}회 | {%} |
| API 실패율 | {N}% | {M}% | {%} |

---

## 2. 성공 기준 템플릿

### 2.1 정량 기준

| 기준 | 목표 | 측정 방법 |
|------|------|----------|
| 트리거 정확도 | ≥90% | §1.1 Triggering Test |
| 도구 호출 효율 | 불필요 호출 ≤2개 | 실행 로그 분석 |
| 실패율 | ≤10% | 10회 반복 실행 |
| Gate 통과율 | 100% (필수 Gate) | Phase별 체크리스트 확인 |

### 2.2 정성 기준

| 기준 | 확인 방법 |
|------|----------|
| 사용자 개입 불필요 | 정상 케이스에서 추가 질문 없이 완료 |
| 세션 간 일관성 | 동일 입력에 대해 3회 실행 시 동일 결과 구조 |
| 올바른 스킬 위임 | Will Not 영역 요청 시 정확한 대안 스킬 안내 |
| Codex 검증 일관성 | fz-codex 교차검증 결과와 fz-review 결과 일치도 ≥80% |

---

## 3. "Ask Claude" 디버깅 기법

스킬이 기대대로 작동하지 않을 때, Claude 자체를 디버깅 도구로 활용한다.

### 방법

1. Claude에게 질문한다:
   ```
   "fz-{name} 스킬은 언제 쓰는 거야?"
   ```

2. Claude의 응답을 분석한다:
   - description을 정확히 인용하는가?
   - 핵심 유스케이스를 올바르게 설명하는가?
   - 부정 트리거(Do NOT use)를 정확히 인식하는가?

3. 누락된 트리거 키워드를 발견한다:
   - Claude가 특정 유스케이스를 언급하지 않으면 → description에 해당 키워드 부재
   - Claude가 잘못된 유스케이스를 언급하면 → description이 모호함

4. description을 조정하고 재테스트한다

### Few-shot: fz-codex Ask Claude 디버깅

```
Q: "fz-codex 스킬은 언제 쓰는 거야?"
A (기대): "Codex CLI를 통한 독립적 코드/계획 검증... codex review, codex exec..."
A (문제): "코드를 수정할 때 쓰는 스킬입니다" ← 잘못된 인식!
→ description에 "검증만 수행, 코드 수정 안 함" 강화 필요
```

### 반복 루프

```
description 조정 → "Ask Claude" 질문 → 인식 확인 → 트리거 테스트 → 반복
```

---

## 4. 스킬별 테스트 스펙 템플릿

YAML 기반으로 테스트 케이스를 정의한다. SKILL.md에 직접 포함하거나 별도 파일로 관리한다.

> 표(markdown table) 형식도 허용 — §1.1/§1.2 예시 및 기존 스킬(fz-memory·fz-recording) 컨벤션. 필드(triggering should/should-NOT · functional Given/When/Then · type · oracle) 충족이 기준.

### 형식

```yaml
test-spec:
  name: fz-{name}
  version: 1.0

  triggering:
    should-trigger:
      - query: "{트리거 쿼리 1}"
        reason: "핵심 유스케이스"
      - query: "{트리거 쿼리 2}"
        reason: "보조 유스케이스"
    should-not-trigger:
      - query: "{비관련 쿼리}"
        redirect: "fz-{other}"
        reason: "스킬 범위 밖"

  functional:
    - given: "{초기 조건}"
      when: "/fz-{name} \"{입력}\""
      then: "{예상 결과 — 가능하면 pass/fail oracle}"
      type: normal

    - given: "{엣지 조건}"
      when: "/fz-{name} \"{입력}\""
      then: "{예상 결과}"
      type: edge-case

    - given: "{실패 조건}"
      when: "/fz-{name} \"{입력}\""
      then: "{에러 핸들링}"
      type: failure

  performance:
    baseline:
      messages: null      # 스킬 없이 측정
      tokens: null
    with-skill:
      messages: null      # 스킬 있을 때 측정
      tokens: null

  success-criteria:
    trigger-accuracy: "≥90%"
    gate-pass-rate: "100%"
    failure-rate: "≤10%"
```

### Codex 스킬 테스트 스펙 예시

```yaml
test-spec:
  name: fz-codex
  version: 1.0

  triggering:
    should-trigger:
      - query: "codex로 리뷰해줘"
        reason: "명시적 도구 호출"
      - query: "교차검증 실행"
        reason: "핵심 기능"
      - query: "PR 전 최종 검증해줘"
        reason: "final 서브커맨드"
    should-not-trigger:
      - query: "코드 직접 수정해줘"
        redirect: "fz-fix"
        reason: "검증만 수행"

  functional:
    - given: "Git diff 존재, Codex CLI 설치됨"
      when: "/fz-codex review"
      then: "codex review 실행 + 이슈 리포트 생성"
      type: normal

    - given: "Codex CLI 미설치"
      when: "/fz-codex review"
      then: "에러 메시지 + sc:analyze 폴백"
      type: failure

    - given: "3-Tier 디스커버리에서 Tier 1 부재"
      when: "/fz-codex verify"
      then: "Tier 2 → Tier 3 순차 폴백"
      type: edge-case
```

---

## 5. 테스트 실행 가이드

### 단계별 실행

```
1. Triggering Test 먼저 실행
   → 트리거 정확도 <90% → description 수정 후 재테스트

2. Functional Test 실행
   → 실패 케이스 → Phase/Gate 로직 검토

3. Performance Comparison 실행
   → 개선 미달 → 스킬 구조 재검토

4. Codex 교차검증 (fz-codex 대상 스킬인 경우)
   → /fz-codex verify로 스킬 로직 독립 검증
```

### 회귀 테스트

스킬 수정 후 반드시 기존 테스트를 재실행한다:
- description 변경 → Triggering Test 재실행
- Phase/Gate 변경 → Functional Test 재실행
- 모듈 참조 변경 → 참조 무결성 확인 (`/fz-manage check`)

---

## 6. Eval 자동화 — `/fz-skill eval` 연계

`/fz-skill eval`과 `/fz-manage benchmark`가 이 가이드의 테스트 프레임워크를 자동화합니다.

### 6.1 Static Analysis (자동)

YAML + 본문 구조를 자동 검증합니다. `/fz-skill eval`의 8항목 체크리스트가 이것을 실행합니다.

| 검증 항목 | 기준 | 대응 테스트 |
|----------|------|------------|
| Description 품질 | what+when+when-not+한영 | §3 Ask Claude 기법의 자동화 |
| YAML 완전성 | 필수 필드 존재 | §4 test-spec의 전제조건 |
| 크기 제한 | ≤500줄 | Progressive Disclosure 준수 |
| Few-shot 예시 | ≥3개 (BAD/GOOD 쌍) | §1.2 Functional Test 커버리지 |
| Gate 체크리스트 | Phase별 Gate 존재 | §2.1 Gate 통과율 |
| Boundaries | Will/Will Not + 대안 | §1.1 should-NOT-trigger 근거 |
| 과격 표현 | CRITICAL 등 부재 | 프롬프트 최적화 원칙 #8 |
| 에러 대응 | 테이블 존재 | §1.2 failure type 커버리지 |

### 6.2 Triggering Test 자동화 (반자동)

`/fz-skill eval`이 description에서 쿼리를 자동 생성하고 자체 판단합니다.

```
자동 생성 로직:
1. description에서 핵심 키워드 추출 → should-trigger 5개 생성
2. Boundaries Will Not에서 → should-NOT-trigger 3개 생성
3. Claude가 각 쿼리에 대해 "이 스킬이 트리거되어야 하는가?" 자체 판단
4. 결과를 사용자에게 확인 요청
```

이 방식은 §3 "Ask Claude" 기법을 체계적으로 자동화한 것입니다.

### 6.3 Diff Eval

`/fz-skill eval --diff`가 수정 전/후를 비교합니다.

| 비교 항목 | 측정 방법 |
|----------|----------|
| Description 키워드 커버리지 | 수정 전/후 키워드 수 비교 |
| 크기 변화 | 줄 수 증감 |
| 섹션 추가/제거 | 헤딩 기반 diff |
| Static Analysis 점수 변화 | 수정 전/후 8항목 점수 비교 |

### 6.4 리뷰형 스킬 Eval — coverage / verification 2단계 분리 (verified)

fz-review·fz-codex처럼 *스스로 finding을 내는* 스킬은 단일 점수로 평가하면 recall과 precision이 뒤섞인다. 2단계로 분리한다 [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-4-8 — "Code review harnesses" 섹션 · **Opus 5에서도 동일 유지**: "If your review prompt says 'only report high-severity issues' or 'be conservative,' the model may follow that instruction literally and report less; ask it to report everything and filter in a separate pass instead" — prompting-claude-opus-5]:

1. **coverage 단계**: 스킬이 *모든* 후보 finding을 보고하는지 (불확실·저severity 포함). "be conservative/don't nitpick" 지시를 너무 충실히 따르면 recall이 떨어진다 — coverage 단계에선 필터링 금지.
2. **verification 단계**: 별도 fresh-context 검증자(§0-2)가 각 finding의 실재성·severity를 판정해 선별. recall(coverage)과 precision(verification)을 *다른 단계*에서 측정.

> 측정: coverage = 알려진 결함 N개 중 보고된 수 / verification = 보고 중 실재 비율. 단일 "정확도"로 합치지 않는다.

---

## 7. A/B 비교 프로토콜 — Description 최적화

### 목적

description 변경이 실제 트리거 정확도에 미치는 영향을 측정합니다.

### 절차

```
1. 현재 description 스냅샷 (A 버전)
2. description 수정 (B 버전)
3. 동일 쿼리 세트로 A/B 각각 Triggering Test 실행
4. 정확도 비교 → B가 높으면 채택, 아니면 롤백
```

### 비교 테이블

```markdown
## A/B 비교: fz-{name} description

| 쿼리 | A (현재) | B (수정) | 변화 |
|------|---------|---------|------|
| "{쿼리 1}" | trigger (O) | trigger (O) | 동일 |
| "{쿼리 2}" | NOT (X) | trigger (O) | 개선 |
| "{쿼리 3}" | trigger (O) | NOT (X) | 퇴보 |

A 정확도: 7/8 (87%)
B 정확도: 8/8 (100%)
판정: B 채택
```

### `/skill-creator` 연계

Anthropic 내장 `/skill-creator`의 Improve 모드가 description 최적화를 제안할 수 있습니다.
A/B 비교 시 `/skill-creator`의 제안을 B 버전으로 테스트하면 효과적입니다.

```bash
/skill-creator   # Improve 모드로 description 최적화 제안 받기
# → 제안된 description을 B 버전으로 A/B 비교 실행
```

---

## 8. Task-Outcome Benchmark (실제 repo·실행 검증)

스킬이 트리거되느냐(§1)·description이 정확하냐(§7)를 넘어, **스킬이 실제 코딩 결과를 개선하는가**(VALUE 축)를 측정하는 프로토콜. §0의 두 원칙(객관 oracle + fresh-context 검증자)을 실제 과제에 적용한다.

### 왜 별도 절차인가

- `scripts/measure_constraint_load.py`는 COST(무엇이 비싼가)만 측정하고, "제거해도 에러가 안 느는가"(VALUE)는 **paired A/B + 회귀 라벨링이 필요하다**고 스스로 명시한다. §8이 그 VALUE 축이다.
- §6.4(리뷰형 eval)의 coverage/verification은 리뷰 finding의 recall/precision 계약이지 **생성 코드의 task-success oracle이 아니다** — 대체 불가한 별도 갭.

### 지표 계층 (⛔ LOC-primary 금지)

| 계층 | 지표 | 판정 |
|------|------|------|
| **1차 (VALUE)** | task acceptance assertion/test 통과 = 생성 코드 실행 검증 | 객관 pass/fail (§0 원칙 1) |
| **결과** | 회귀 라벨(resolved/regressed) + 완료율 | — |
| **2차 (효율)** | LOC(git diff added-lines) · 토큰 · 시간 | 1차 통과분에 한해 비교 |

> ⛔ 1차 oracle 없이 LOC만 비교하면 "task-outcome"이 아니라 "코드량 비교"다 — 그럴 땐 이름을 낮춰라.

### same-agent A/B 격리 프로토콜 (수동)

- **동일 에이전트**를 skill 유/무로 real public repo @고정커밋에 실제 티켓 수행. **baseline arm 정의 (canonical)**: skill 미적용 동일 에이전트 — 신규 스킬은 without-skill, 기존 스킬 개선은 old-skill(이전 버전); chatty bare 모델 아님
- arm×run마다: 동일 고정 커밋의 **독립 worktree/clone** · 고정 model/effort/tool-budget · 빌드·의존성 캐시 정책 · timeout · **비신뢰 코드 실행 sandbox(safety tier)**
- **오염 탐지 (canonical)**: baseline arm이 skill·always-on 룰셋에 접근 안 했는지 확인 — 플러그인의 SessionStart/SubagentStart 훅이 baseline arm에도 발화해 gap이 0으로 수렴한 오염 사례 있음 (arm 격리 필수). in-session 서브에이전트 A/B(예: skill-creator `--full`)의 오염 판정도 본 절이 single source.
- **채점·집계 계약**: (a) **fresh-context 채점자** — 별도 세션/에이전트가 diff + acceptance test만 보고 판정(§0 원칙 2), (b) 오염 감지된 pair = `invalid/exploratory`로 **제외**, (c) task별 (with-skill, baseline) **paired 2×2**: (with pass, baseline fail)=resolved · (with fail, baseline pass)=regressed · 동일 결과=neutral, (d) 완료율 = with-skill pass task 수 / **오염 제외 후 유효 task 수**, (e) `n≥4 → median`은 **2차 효율 지표(LOC·토큰·시간)에만** 적용 — 1차 성공률·회귀는 비율/카운트로 집계. 워크스페이스 보존 → 오프라인 rescore

> ⛔ **이건 방법론이다** — 실측이 필요할 때 이렇게 하라. clone/worktree/sandbox 자동 조립 러너 구축은 `guides/harness-engineering.md` §6 AP1(과잉구조화) 대상이며, 실제 스킬 회귀가 반복 관측된 뒤 사용자 결정으로 착수한다.

### 8.1 effort sweep (§8의 특화 — arm 설정만 다름)

**발동 조건**: 새 모델 전환 시. Opus 5 공식이 요구한다 — *"If you carried effort settings over from an earlier model, **run a fresh effort sweep on your evals** rather than reusing them"* [verified: platform.claude.com/docs/en/build-with-claude/effort]. 채점·집계·오염 탐지는 §8 계약을 그대로 상속하고, **arm 설정 방법만** 아래로 대체한다.

**⛔ arm은 세션 레벨로 설정한다 — `workflows/*.js`의 per-call `opts.effort`를 수정하지 말 것**

| 레이어 | 우선순위 | 근거 |
|---|---|---|
| `CLAUDE_CODE_EFFORT_LEVEL` env var | **최상위** | *"The environment variable takes precedence over all other methods"* [verified: code.claude.com/docs/en/model-config] |
| skill/subagent frontmatter `effort` | 세션 위 | *"Frontmatter effort … overriding the session level but not the environment variable"* [verified: 동] |
| Workflow `agent()` per-call `opts.effort` | **`[미검증]`** | 공식이 per-invocation **`model`** 파라미터는 실재 레이어로 명시하나(`CLAUDE_CODE_SUBAGENT_MODEL`이 "overrides the per-invocation `model` parameter"), **effort는 동일 서술이 없다** |
| `settings.json` `effortLevel` (세션) | 기본 | *"a starting default, not enforcement"* [verified: 동] |

> **이유**: per-call `opts.effort`의 지위가 미확정이므로, 그것으로 arm을 가르면 **arm이 실제로 갈렸는지 알 수 없다**. 미검증 메커니즘 위에 측정을 세우지 않는다. 현행 fz는 `.js` 36곳과 `settings.json:409`가 **모두 `xhigh`** 라 어느 쪽이 이기든 결과가 같아 이 모호성이 드러나지 않았다.

**⛔ arm 적용 검증 (필수 — 매 run)**: Claude Code는 트랜스크립트 최상위에 `effort` 필드를 기록한다(v2.1.212+). run 직후 확인해 **의도한 arm이 실제 적용됐는지** 대조한다. 불일치 pair는 §8 오염 규칙에 따라 `invalid`로 **제외**.

> **왜 형식이 아닌가** [verified: 실측 CC 2.1.220 · opus-5]: **무효 effort 값은 에러를 내지 않고 조용히 무시된다.** `CLAUDE_CODE_EFFORT_LEVEL=bogus`가 통과하며 하위 층 값이 그대로 남는다 — 검증 없이 env var만 세팅하면 **arm이 갈리지 않은 채 측정이 진행된다.** 기준선을 바꿔 확인함: settings 기본 `medium` + env `bogus` → `medium` 잔존, env `high` → `high` 적용.
> 부수: `--settings`는 사용자 `settings.json`과 **병합**된다(미지정 키는 사용자 값 유지) — A/B 격리 시 의도한 키를 명시할 것. `{}`를 줘도 사용자 effortLevel이 살아남는다.
> ⚠️ 재현 함정: 자기 세션 transcript는 계속 쓰이므로 `ls -t | head -1`은 headless run 파일을 못 찾는다 → **파일 집합 diff + 자기 세션 ID 제외**로 신규 파일을 특정할 것.

**⛔ `ultracode`는 arm 값이 아니다** [verified: 실측 CC 2.1.220]: env var·`settings.json` **양 층에서 무효값과 구별 불가하게 무시된다**(기본 `medium`에 `ultracode` 주면 `medium` 잔존 — xhigh 아님). 따라서 `ultracode` on/off를 **비대화식 paired arm으로 만들 수 없다**. 대화식 세션 토글 전용이며, 그 상태를 headless run에 물려주는 경로는 확인되지 않았다.

```bash
# arm 설정 (택1) — .js 미변경
CLAUDE_CODE_EFFORT_LEVEL=medium claude ...   # env var (최상위, 비대화식에 적합)
/effort medium                                # 대화식 세션

# arm 적용 검증 (run 직후)
python3 - <<'PY'
import json,glob,os,collections
p=max(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")), key=os.path.getmtime)
c=collections.Counter(json.loads(l).get("effort") for l in open(p,errors="replace")
                      if '"effort"' in l)
print(p, dict(c))   # 의도한 arm 값만 나와야 정상
PY
```

**arm 선정**: Opus 5 공식 출발점이 `high`(기본)이고 `low`/`medium`이 비용·지연의 1차 레버이므로 최소 `{low, medium, high}` 3-arm. `xhigh`는 demanding coding/agentic 대조군으로 추가.

**대상 스킬 우선순위**: `measure_constraint_load.py` 의 **floor 큰 순** — `fz`(31,259) · `fz-review`(29,264) · `fz-code`(26,837). floor가 큰 스킬일수록 effort 변화의 절대 효과가 크다.

⛔ **sweep 결과로 곧바로 `.js`를 고치지 말 것**: arm이 세션 레벨이었으므로 결론도 세션/frontmatter 레벨에 적용한다. per-call 배선 변경은 위 `[미검증]` 해소가 **선행**이다.

---

## 참조

- 권위 자료 단일 참조점: `guides/llm-references.md` (Tier 1/2/3)
- 스킬 작성법: `guides/skill-authoring.md`
- 트러블슈팅: `guides/skill-troubleshooting.md`
- 프롬프트 최적화: `guides/prompt-optimization.md`
- Codex 교차검증: `skills/fz-codex/SKILL.md`
- 스킬 품질 평가: `/fz-skill eval` (`skills/fz-skill/SKILL.md`)
- 일괄 벤치마크: `/fz-manage benchmark` (`skills/fz-manage/SKILL.md`)
- Anthropic 공식 평가: `/skill-creator` (Eval/Improve/Benchmark 모드)
- Tier 1 출처: code.claude.com/docs/en/{skills, sub-agents, best-practices}
