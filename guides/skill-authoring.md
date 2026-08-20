# 스킬 작성 실전 가이드

> **Sources (last audited: 2026-07-25 — 모델 사실 축):** `guides/llm-references.md` §1 정본 대조 완료. 그 외 인용은 개별 `[verified:]` 태그 참조.
>
> fz-* 스킬 생태계에서 새 스킬을 설계하고 작성하기 위한 실무 가이드.
> 이론이 아닌 실행 중심. 모든 예시는 기존 17+ 스킬 생태계 기반.

---

## 1. 스킬 라이프사이클

```
설계 → 작성 → 테스트 → eval → 배포 → 진화
  ↑                                     |
  └──────── 피드백 ────────────────────┘
```

### 설계

- 2-3개 유스케이스를 먼저 식별한다 (Anthropic 권고: 유스케이스 먼저)
- 유스케이스 없이 스킬부터 만들면 범위가 흐려진다
- 기존 스킬과 겹치는지 확인: `/fz-manage check` 실행

#### Single Task First 워크플로우 (공식 권고)

스킬을 작성하기 전에, 스킬 없이 단일 도전적 작업을 반복한다.
성공할 때까지 반복한 후, 성공 패턴을 스킬로 추출한다.

1. 스킬 없이 실제 작업 수행
2. 실패/비효율 지점 기록
3. 성공할 때까지 반복 (Claude의 in-context learning 활용)
4. 성공 패턴을 SKILL.md로 추출
5. 3개 평가 시나리오로 검증 (`guides/skill-testing.md` §1)

### 작성

- `templates/skill-template.md` 기반으로 시작한다
- 템플릿의 모든 필드를 채운 후 불필요한 부분을 제거한다
- 빈 필드를 남기지 않는다 — 명시적으로 `none`을 적는다

### 테스트

- 3개 평가 시나리오를 정의한다 (정상, 경계, 실패)
- 직접 호출로 결과를 확인한다: `/fz-{name} {시나리오}`
- 파이프라인 내에서도 테스트한다: `/fz` 경유 호출
- 상세 테스트 방법론: `guides/skill-testing.md` 참조
- Ask Claude 디버깅: `guides/skill-testing.md` §3 참조
- 트러블슈팅: `guides/skill-troubleshooting.md` 참조

### Eval (품질 평가)

- `/fz-skill eval fz-{name}` → Static Analysis(8항목, 자동) + Triggering Test(반자동) 실행
- 목표: FAIL 0개, WARN ≤2개
- `/skill-creator` Eval 모드로 보완적 평가 (다른 관점의 독립 측정)
- A/B 비교: description 변경 시 `skill-testing.md` §7 프로토콜 적용

### 배포

- `skills/{name}/SKILL.md`에 배치한다
- `/fz-manage check`로 건강 체크 — 전체 통과 필수

### 진화

- ACE 패턴을 따른다:
  - **A**nalyze: 실패 기록을 수집하고 패턴을 찾는다
  - **C**orrect: 점진적으로 편집한다 (대규모 재작성 금지)
  - **E**liminate: 주기적으로 사용하지 않는 지침을 가지치기한다
- 500줄 이하를 유지한다 — 넘으면 모듈로 분리한다
- **⛔ 트리밍 비저하 원칙**: 줄 수 축소가 실행 품질 저하를 일으키면 트리밍 의미가 없다. §3의 "트리밍 비저하 원칙" 참조
- **⛔ DELETE/MERGE-default (편집 operating rule)**: 스킬/가이드/모듈을 *편집*할 때 DELETE 또는 MERGE를 기본값으로 먼저 검토한다. 순수 additive 변경(기존 삭제·병합 없이 추가만)은 삭제/병합 counterpart를 동반하거나 명시적 정당화가 있어야 한다. 이유: 규칙 누적은 adherence tax(IFScale 500규칙→68%)이고, literal-following 모델(Opus 4.8 이후)에서 bloat 비용이 더 크다 — 추가 충동마다 "무엇을 지울 수 있나"를 먼저 묻는 것이 self-correcting 하네스의 조건. (memory 18차 rule(3)의 skill-body 강제)
  - **Opus 5가 이 규칙을 강화한다**: 공식 프롬프팅 가이드가 *제거*를 명시 지시한다 — 검증 지시("include a final verification step" / "use a subagent to verify" / "double-check your answer")를 **삭제**하라, *"removing them reduces wasted tokens **with no loss in quality**"* [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5]. 모델이 내재화한 행동에 지시를 겹치면 중복 실행이 된다. ⚠️ 단 §llm-references §4-2의 *외부 verifier·교차검증 원칙*은 별개 — 삭제 대상은 **모델에게 자기재확인을 시키는 문구**뿐.
- **⚠️ Sibling-Convention Check (편집 operating rule, candidate)**: fz 자산에 candidate·검증·관측 항목을 *추가*할 때, 기존 동류 항목(예: fz-review 검증 4-N/4-O, promotion-ledger L-series)의 표기 템플릿을 먼저 grep해 일치시킨다 — `⚠️` 마커 · 「활성 강제 X」 · 「N sessions 후 결정」 등. 이유: 동류 컨벤션을 안 보고 새 표기를 즉흥 생성하면 일관성 붕괴 + 강제성 오인(candidate가 ⛔/blocking으로 오동작). 결정론 grep이라 즉시 가능. evidence: TVG-1219 환류 세션 ①(fz-review 검증5/Gate) candidate 표기 불일치 catch — `feedback_fz_self_reference_blindspot` 발현1(활용 갭). ⚠️ candidate(1 session) — 활성 강제 X, 5 sessions 후 active(⛔) 재판정.

---

## 2. Description 작성법 (가장 중요)

Claude가 100+ 스킬 중 하나를 선택하는 유일한 근거 = **description**.

### 필수 포함 요소

| 요소 | 설명 | 예시 |
|------|------|------|
| **무엇** | 핵심 기능 1줄 | "코드 구현 + 빌드 검증 스킬" |
| **언제** | 사용 조건 | "Use when implementing new features" |
| **언제 아닌지** | 부정 트리거 + 대안 스킬 | "Do NOT use for bug fixes (use fz-fix)" |
| **키워드** | 한국어 + 영어 혼용 | "구현, 코드, implement, code" |

### 작성 규칙

1. **3인칭 서술**: "I can help you" (X) → "Processes files" (O)
2. **한국어 설명 + 영어 트리거 혼용**: 매칭률 극대화
3. **구체적 키워드**: 일반적인 단어보다 도메인 특화 키워드 사용
4. **1024자 이하**: 시스템 프롬프트 공간 제한

### Few-shot 예시

```
BAD:  "Helps with code"
      → 너무 모호. 모든 코딩 스킬과 충돌.

BAD:  "I help developers write better code and find bugs"
      → 1인칭 사용. 기능 범위 불명확. 부정 트리거 없음.

GOOD: "버그 수정 경량 스킬. 원인 분석 → 수정 → 빌드 검증의 빠른 사이클.
       Use when fixing bugs, resolving crashes, correcting errors.
       Do NOT use for new feature implementation (use fz-code)."
      → 핵심 기능 명확. 긍정/부정 트리거 모두 포함. 대안 스킬 명시.
```

---

## 3. Progressive Disclosure 실전 가이드

스킬 정보를 3단계로 나눠 필요한 시점에만 로드한다.

### Level 1: YAML Frontmatter (항상 로드)

- 시스템 프롬프트에 포함된다 → 스킬 발견 용도
- 최소화: `name` + `description`만으로 Claude가 선택할 수 있어야 한다
- description 1024자 이하 엄수
- 여기서 정보가 과하면 모든 요청에 불필요한 토큰이 소비된다
- 스킬 多 시 description이 listing budget에 맞춰 자동 축약 — `skillListingBudgetFraction` / `SLASH_COMMAND_TOOL_CHAR_BUDGET`로 조정 [verified: code.claude.com/docs/en/skills]
- `disable-model-invocation: true` → 자동 로드 차단(수동 `/name`만 invoke) [verified: 동]

### Level 2: SKILL.md 본문 (관련 시 로드)

- 실행 지침을 담는다 → **500줄 이하** 유지 (Context Rot 과학적 근거)
- 핵심만 포함한다: Phase, Gate, Boundaries
- 부수적 내용은 경로만 명시한다:
  ```
  빌드 검증 세부 절차는 `modules/build.md` 참조.
  ```
- 500줄 초과 시 증상: Claude가 후반부 지침을 무시하기 시작한다

#### ⛔ 트리밍 비저하 원칙

> ⛔ **Single source**: `guides/prompt-optimization.md` §1 보충 3a (UC-7, v4.7.0).
> 본 위치는 reference + 핵심 3 bullet만 유지. 삭제 금지/압축 허용 전체 정의는 single source를 따른다.

**삭제 금지 핵심 3개** (single source 참조):
- Gate 체크리스트 항목 — 삭제하면 검증 단계 스킵
- Few-shot BAD/GOOD 예시 — 삭제하면 행동 정확도 하락
- 절차적 Step (순서 중요한 다단계) — 삭제하면 Step 누락

**500줄 초과 시 우선순위**: 삭제보다 **모듈 분리**(`modules/`)를 먼저 시도한다.

> **모델 전이 강건성** (2026-07 추가 — 위 삭제 금지 3개의 외부 수렴 근거): 절차적 규칙(체크리스트·Gate·Step)이 서술적 prose 조언보다 모델 교체에 강건하다 — "'factual 구조는 전이되나 prose 전략은 전이 안 됨'(2604.25850), AdaCoM의 '유사 능력 에이전트 간 전이가 최선'이 시사하듯, 하네스가 모델·태스크·도메인을 넘어 얼마나 이식되는지가 미해결." [외부: harness-paper §6 미해결과제4 — 원 논문 미대조]. 함의: 스킬 작성 시 절차적 체크리스트 > prose 조언, 모델 교체·재배선(예: Fable 5) 시 스킬 회귀 점검 축으로 활용. ⚠️ 근거 등급 낮음 — 2604.25850은 배경 논문(서베이 CONFIRMED 86편 밖). 기존 원칙 보강이지 신규 규칙 아님.

### Level 3: References (필요 시 Read)

- `modules/*.md`, `guides/*.md` 등 공유 파일
- Claude가 Read 도구로 직접 읽는다 (자동 로딩 아님)
- **1단계 깊이만**: SKILL.md → ref.md (O), ref.md → detail.md (X)
- 100줄 이상 파일에는 목차를 포함한다
- **플러그인 루트 상대 경로**: `modules/build.md` (not `../../modules/build.md`)

### 디렉토리 구조 예시

```
skills/fz-code/
├── SKILL.md          ← Level 2 (500줄 이하)
└── (단순 스킬은 하위 디렉토리 없음)

modules/      ← Level 3 (공유 모듈)
├── team-core.md
├── team-registry.md
├── patterns/
└── ...

guides/       ← Level 3 (공유 가이드)
├── prompt-optimization.md
├── agent-team-guide.md
└── ...
```

---

## 4. 프롬프트 작성 최적화 원칙

§2(Description), §3(Progressive Disclosure)에서 다루지 않은 핵심 원칙.
상세 Before/After 예시와 이론: `guides/prompt-optimization.md` 참조.

### 원칙 1: Claude가 모르는 것만 추가

일반 지식을 반복하면 토큰만 소비하고 Context Rot을 가속한다.
프로젝트 고유 정보(네이밍 규칙, 아키텍처 결정, 내부 API 사용법)만 포함한다.

```
BAD:  "Swift의 struct는 값 타입이고 class는 참조 타입입니다..."
GOOD: "이 프로젝트에서 ViewModel은 class (RIBs Interactor 내장), View 데이터 모델은 struct"
```

### 원칙 4: 자유도를 작업 위험도에 맞춰라

| 위험도 | 자유도 | 지시 방식 |
|--------|--------|-----------|
| 높음 (DB, API breaking) | 낮음 | 정확한 스크립트, 명령어 그대로 실행 |
| 중간 (기능 구현) | 중간 | 패턴 제시 + 변형 허용 |
| 낮음 (탐색, 문서화) | 높음 | 가이드라인만 제시, 판단 위임 |

### 원칙 4a: 원칙+이유로 프레이밍

"X이면 Y를 하라" 대신 "Z를 추구하라. 이유: W"로 작성한다.
Claude는 이유에서 유사 상황으로 일반화한다. 체크리스트 행 추가 충동이 들면, 원칙 하나로 대체한다.

```
BAD:  "continuation bridge가 있고 native async가 있으면 → bridge를 제거하라"
GOOD: "동일 동작을 가장 적은 코드로 표현하는 것이 진짜 최소 변경이다."
```

### 원칙 5: Few-shot 예시 > 장문 설명

3줄의 BAD/GOOD 대비 예시가 30줄의 설명보다 효과적이다.

- `## Few-shot 예시` 섹션에 BAD/GOOD 대비 쌍 ≥3개 포함
- BAD: 잘못된 접근 + 왜 나쁜지 (→ 주석)
- GOOD: 올바른 접근 + 왜 좋은지 (→ 주석)
- 엣지 케이스 최소 1개 포함
- `<example>` 태그 또는 코드 블록으로 구분

```
BAD (구조 분해 부족):
Step 1: ContentDetailRIB 만들기
→ 영향 분석 없음, Step이 막연

GOOD:
Step 1: ContentDetailBuilder 생성 (DI: ContentRepository, ImageCacheUseCase)
→ 의존성 명시, 생성 대상 구체적
```

### 원칙 6: 피드백 루프 내장

생성만 하고 검증하지 않으면 오류가 누적된다.

- Gate 조건을 체크리스트 형태로 명시한다
- 실패 시 구체적 행동을 명시한다 (재시도/스킵/에스컬레이션)
- "validate → fix → repeat" 패턴을 적용한다
- 최대 반복 횟수를 설정한다 (무한 루프 방지)
- **Gate는 절차적 강제**: 스킵 불가. 실패 시 해당 단계를 "완료"로 표시할 수 없다 (`modules/cross-validation.md` 참조)
- **Evaluator-Optimizer 패턴**: stress-test 등에서 Critical 2개+ 발견 시 자동 재작성 (최대 2회). 초과 시 사용자 에스컬레이션

### 원칙 8: 과격 표현 제거 (instruction-following 일관성)

Claude 4.8은 지시를 일관되게 따른다 ("follows instructions with the consistency our autonomous engineering workloads need" [verified: anthropic.com/news/claude-opus-4-8]) → 과격·모호한 지시가 그대로 적용될 위험. **GPT-5.5 (2026-04-23 GA)** 도 "literal and thorough manner" 동일 방향 [verified: developers.openai.com/api/docs/guides/latest-model]. **Fable 5 (2026-06-09 GA)** 는 한층 더 — 짧은 지시로 대부분 행동 조향 가능하며, 이전 모델용 과잉 절차 지시는 출력 품질을 저하시킬 수 있다 ("often too prescriptive... can degrade output quality" [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5]). **Opus 5 (2026-07-24 GA)** 는 여기에 **스코프 확장** 경향이 더해진다 — 요청하지 않은 단계를 추가하거나 과제 자체를 재해석할 수 있어, 좁은 과제에는 범위를 명시 제약할 것 [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5].

```
BAD:  "CRITICAL: You MUST ALWAYS use this tool"
GOOD: "Use this tool when reading or modifying files"
```

- "CRITICAL", "MUST ALWAYS", "NEVER EVER" → 자연스러운 표현으로 대체
- Anti-laziness가 필요하면 SKILL.md가 아닌 user prompt 쪽에 배치
- 참조: `guides/prompt-optimization.md` 동일 원칙 8 (instruction-following 일관성 상세)

---

## 5. provides/needs 체인 설계

`/fz` 오케스트레이터가 provides/needs로 동적 파이프라인을 구성한다.

### 기존 토큰 레지스트리

전체 목록은 `templates/skill-template.md`의 레지스트리 섹션 참조.

### 설계 규칙

| 규칙 | 설명 | 예시 |
|------|------|------|
| `needs: [none]` | 진입점 스킬 | fz-plan, fz-search, fz-fix |
| `needs: [planning]` | 선행 스킬 필요 | fz-code (fz-plan 이후) |
| 새 토큰 추가 시 | 레지스트리에도 반드시 추가 | `templates/skill-template.md` |
| 순환 금지 | A→B→A 형태 불가 | provides/needs 그래프 DAG 유지 |

### 파이프라인 매칭 흐름

```
사용자 요청
  → /fz intent 분석
  → intent-triggers 매칭
  → 사전 정의 파이프라인 (modules/pipelines.md) 매칭
  → 미매칭 시 provides/needs 그래프로 동적 구성
```

---

## 6. intent-triggers 작성법

### 규칙

1. 한국어 + 영어 각각 1줄 이상 작성한다
2. 정규식 패턴을 사용한다 (`|` 구분)
3. 다른 스킬과 중복을 최소화한다
4. 구체적 키워드를 우선한다 (일반적인 단어는 충돌 위험)

### 예시

```yaml
intent-triggers:
  - "계획|설계|아키텍처|요구사항"     # 한국어
  - "plan|design|architect"            # 영어
```

### 나쁜 예시

```yaml
intent-triggers:
  - "코드|개발"        # 너무 광범위 — fz-code, fz-fix, fz-review 모두 해당
  - "help|do"          # 의미 없음 — 모든 요청에 매칭
```

### 중복 체크 방법

```bash
/fz-manage check   # intent-triggers 중복 검증 (항목 #4)
```

---

## 7. 팀 에이전트 모드 설계

### 언제 팀을 구성하는가?

| SOLO | TEAM |
|------|------|
| 단순 작업 (1 파일, 명확한 지시) | 복잡 작업 (여러 모듈, 설계 결정) |
| 빠른 피드백 필요 | 다관점 검증 필요 |
| fz-fix (대부분), fz-search (기본) | fz-plan, fz-code, fz-review |

SOLO가 기본이다. 팀이 필요한 근거가 없으면 SOLO로 실행한다.

### 팀 구성 패턴

⛔ **스킬 YAML `team-agents`는 2026-08-09 제거됐다** — Wave 4 전환 후 팀 구성을 결정하지 않는 선언이었다. 구성은 **스크립트가 소유**한다 (정본: `modules/governance.md` § Truth-of-Source):

```js
// workflows/{skill}-{pattern}.js
await agent(prompt, { label: 'stage1-impl', agentType: 'fz:impl-correctness',
                      model: 'opus', effort: 'xhigh', schema: ChangesetSchema })
```

- Primary Worker는 1명만 지정한다
- Supporting은 필요한 만큼 추가하되 3명 이하를 권장한다
- 에이전트 파일은 `agents/`에 존재해야 한다
- 에이전트 목록: `modules/team-registry.md` 참조

### 통신 패턴 선택

| 패턴 | 적용 스킬 | 핵심 동작 | 패턴 파일 |
|------|-----------|-----------|----------|
| Collaborative Design | fz-plan | 만들면서 토론 | `modules/patterns/collaborative.md` |
| Pair Programming | fz-code | 구현 중 실시간 피드백 | `modules/patterns/pair-programming.md` |
| Live Review | fz-review | 분석하면서 발견 공유 | `modules/patterns/live-review.md` |
| Adversarial Discovery | fz-discover | 만들고 부수며 제약 발견 | `modules/patterns/adversarial.md` |
| Cross-Verify | fz-search | 발견 즉시 교차 확인 | `modules/patterns/cross-verify.md` |

자세한 내용: `guides/agent-team-guide.md`

---

## 8. 모델 전략

| 역할 | 모델 | 근거 |
|------|------|------|
| Lead (오케스트레이터) | fable | 최종 판단, 게이트 실행 |
| 판단 지점 (workflow merge·direction) | fable | capability-sensitive 단일 호출 (정적 3지점, lint `EXPECTED_FABLE=3`) |
| 실질 분석·생산 워커 | opus | 계획·코드·설계·리뷰·비평 품질 |
| 단순 (retrieval·breadth) 워커 | sonnet | 비용 효율, 충분한 품질 |
| haiku | **미사용** | 프로젝트 정책 |

### 승격 규칙

- SOLO 모드: Lead(세션 모델, 보통 fable) 직접 수행 — 재배선 정책 비적용
- 워커 모델은 **작업 실질 기준** 배정: 실질 분석·생산 = opus / 단순 retrieval·breadth = sonnet — "Supporting은 항상 sonnet"은 폐기(검증·비평도 실질이면 opus, 예: peer-review CC·review-live counter)
- 판단 지점(workflow merge·direction)만 fable (정적 3지점 고정, lint `EXPECTED_FABLE=3`)
- 상세·근거: `guides/fable-model-guide.md` § 5 (fz 생태계 적용 전략)

---

## 9. fz 생태계 통합 체크리스트

새 스킬을 추가할 때 아래 항목을 모두 확인한다.

### 필수 항목

- [ ] `templates/skill-template.md` 기반으로 작성했는가?
- [ ] description에 무엇/언제/언제 아닌지/키워드가 모두 포함되었는가?
- [ ] provides/needs가 기존 체인과 정합하는가?
- [ ] intent-triggers가 기존 스킬과 중복이 없는가?
- [ ] `/fz-manage check` 전체 통과하는가?

### 품질 평가 항목

- [ ] `/fz-skill eval fz-{name}` Static Analysis FAIL 0개인가?
- [ ] Triggering Test 정확도 ≥90%인가?
- [ ] `/skill-creator` Eval로 보완 평가를 수행했는가? (권장)

### Utility 스킬 예외

Query/Utility 스킬(fz-commit, fz-pr, fz-new-file 등)은 Phase/Gate/Few-shot 면제.
단, 아래 항목은 필수: Description 4요소, Boundaries, 에러 대응 테이블.
상세: `modules/governance.md` — Utility 스킬 예외 섹션.

### 상황별 항목

- [ ] 파이프라인에 포함되는 스킬이면 `modules/pipelines.md`에 추가했는가?
- [ ] 팀 에이전트가 필요하면 `agents/`에 에이전트 파일이 존재하는가?
- [ ] 새 provides 토큰을 정의했으면 `templates/skill-template.md` 레지스트리에 추가했는가?
- [ ] 500줄을 초과하면 공유 모듈(`modules/`)로 분리했는가?
- [ ] ⛔ Phase 0 ASD Pre-flight가 포함되어 있는가? (`modules/context-artifacts.md` → Work Dir Resolution)
- [ ] ASD 컨텍스트 로딩(Hydration Set)이 `modules/context-artifacts.md` Upstream Hydration Sets와 일치하는가?

### 프롬프트 최적화 (§4 기반)

- [ ] Claude가 이미 아는 일반 지식을 설명하고 있지 않은가? (원칙 1)
- [ ] 위험도에 맞는 자유도를 설정했는가? (원칙 4)
- [ ] 행동 가이드가 "원칙+이유" 형태인가? if-then 테이블이 아닌가? (원칙 4a)
- [ ] Few-shot BAD/GOOD 대비 쌍이 3개 이상 포함되어 있는가? (원칙 5)
- [ ] 에러 대응 테이블이 포함되어 있는가?
- [ ] 검증 Gate가 내장되어 있는가? (원칙 6)
- [ ] 과격한 표현("CRITICAL", "MUST ALWAYS")을 자연어로 대체했는가? (원칙 8)

### 문서 구조

- [ ] SKILL.md 본문이 500줄 이하인가?
- [ ] Level 3 참조가 1단계 깊이를 넘지 않는가?
- [ ] 모든 파일 참조 경로가 플러그인 루트 상대 경로인가? (`.claude/` prefix 금지)

> 상세 Before/After 예시와 이론: `guides/prompt-optimization.md` 참조.

---

## 10. 스킬 설계 패턴 5가지 (Anthropic 공식)

스킬이 **무엇을** 하는가의 아키타입. §7의 팀 통신 패턴(에이전트가 **어떻게** 협업하는가)과 구별된다.

| 패턴 | 적용 시점 | fz 적용 예시 |
|------|----------|-------------|
| Sequential Workflow | 순서 중요한 다단계 | fz-code (Phase별 순차 구현) |
| Multi-MCP Coordination | 여러 MCP 서비스 조율 | fz-plan (Serena+Context7+sequential-thinking) |
| Iterative Refinement | 품질 개선 반복 | fz-review (3중 검증 루프) |
| Context-Aware Tool Selection | 상황별 도구 선택 | fz-search (symbolic vs pattern 자동 선택) |
| Domain-Specific Intelligence | 도메인 지식 임베딩 | fz-peer-review (리뷰 가이드라인 임베딩) |

### Cross-Model Verification (fz 확장 패턴)

기존 5패턴에 추가되는 fz 고유 패턴:

| 패턴 | 적용 시점 | fz 적용 예시 |
|------|----------|-------------|
| Cross-Model Verification | 독립 모델 교차검증 | fz-codex (Codex CLI로 독립 검증) |

fz-codex는 Codex CLI의 네이티브 기능(`codex review`, `codex exec --output-schema`)과
3-Tier 디스커버리 스킬 체인(fz-reviewer, fz-architect, fz-guardian, fz-challenger, fz-searcher, fz-fixer)을
결합하여 Main Agent와 독립된 교차검증을 수행한다.

### 패턴 구분 정리

```
스킬 설계 패턴 (§10)    = "스킬이 무엇을 하는가"의 아키타입
팀 통신 패턴 (§7)       = "에이전트가 어떻게 협업하는가"의 프로토콜
교차모델 검증 (fz-codex) = "독립 모델이 어떻게 상호검증하는가"의 프로토콜
```

---

## 11. Deterministic Script 활용

> "Code is deterministic; language interpretation isn't." — Anthropic 공식

검증이 중요한 스킬에서는 언어 지시 대신 스크립트를 번들한다.

| 사용 시점 | 예시 |
|----------|------|
| 데이터 형식 검증 | `scripts/validate.py --input {file}` |
| 빌드 결과 파싱 | `scripts/parse_build_log.sh` |
| 패턴 검증 (Anti-Pattern Constraints) | `scripts/check_patterns.sh` |
| Codex 응답 스키마 검증 | `schemas/codex_review_schema.json` |

### scripts/ 디렉토리 규칙

- `skills/{name}/scripts/`에 배치한다
- 스크립트 자체는 토큰을 소비하지 않는다 (실행 결과만 소비)
- SKILL.md에서 명시적 경로로 참조한다
- JSON 스키마는 `schemas/`에 배치한다 (fz-codex의 `--output-schema` 활용)

### 스크립트 vs 언어 지시 판단 기준

```
결과가 binary(pass/fail)인가? → 스크립트
결과가 해석이 필요한가?       → 언어 지시
결과가 구조화된 JSON인가?     → --output-schema (fz-codex 패턴)
```

> §12와의 경계: 본 §11은 *스킬 내부 binary 검증 보조* 스크립트를 다룬다. 에이전트를 스폰하는 *오케스트레이션* 스크립트는 §12 참조.

## 12. Workflow 오케스트레이션 (TEAM 대체 — 결정적 멀티에이전트)

> 신설 정당화 (additive — DELETE/MERGE-default §3 충족): §7(팀 통신 패턴)은 TEAM 일몰 경로로 deprecated 예정이고, §11은 binary 검증 보조로 관심사가 다름(오케스트레이션 아님) — 기존 섹션 흡수 불가. pilot(fz-discover, 2026-06-05) 실측으로 검증된 계약만 수록.

네이티브 Workflow 도구(결정적 JS 스크립트가 에이전트 fan-out/수렴을 소유)로 TEAM(TeamCreate+SendMessage)을 대체할 때의 규약.

### 표준 패턴 3종 (전 스크립트 의무 — pilot 실측 검증)

1. **OVERRIDE 블록**: agentType 재사용 시 모든 agent() 프롬프트 선두에 — "P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시 미적용. 에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 미적용 — 이 프롬프트의 입력만이 과제 전부. 무관 작업 폴더 읽기 금지. 최종 텍스트가 반환값(1-shot raw data)." [근거: pilot invoke #1 — 에이전트 정의의 컨텍스트 로딩이 args를 압도해 무관 폴더 anchoring]
2. **args 방어 파싱 + fail-fast**: scriptPath 호출 시 args가 JSON **문자열**로 도착한다 [실측: probe wf_89418b73, typeof=string] → `typeof args === 'string' ? JSON.parse(args) : args` + 필수 키 누락 시 에이전트 스폰 전 `{mode:'fallback'}` 즉시 반환 (fabrication 방지)
3. **agentType 네임스페이스**: 플러그인 에이전트는 `fz:` prefix 필수 [실측: S0 — 'plan-structure' not found / 'fz:plan-structure' 동작]

### 배치·호출 규약

- 스크립트: 플러그인 루트 `workflows/{skill}-{pattern}.js` (§11 `scripts/`와 목적 분리 — 루트 오케스트레이션 vs 스킬 binary 검증)
- 호출(Lead): `Workflow({ scriptPath: '{플러그인 루트}/workflows/....js', args })`. ⚠️ `{플러그인 루트}`는 **절대경로** — 스킬 디렉토리(`skills/{skill}/`) 상대경로 아님 (G7/#7). 설치본 예: `~/.claude/plugins/fz*/workflows/plan-collaborative.js` (dev 체크아웃은 해당 repo 루트로 치환). SKILL.md frontmatter `allowed-tools`에 **Workflow 추가 의무** (누락 시 호출 불가 dead code)
- 대형 입력(diff 등)은 args가 아닌 **파일 경로 전달** — Lead가 파일 기록 후 경로+요약만 args로, 에이전트가 Read (args 직렬화 한계 미검증 regime 회피)
- agent() 호출 시 `opts.model` + `opts.effort` **모두 명시 의무** — model 생략 시 세션 모델(fable) 상속(생산 워커가 fable로 스폰돼 비용 2배 함정), effort 생략 시 세션 effort 상속. 특정 콜이 effort를 거부하면 그 콜만 effort 제거(model 유지) — 폴백 계약. `scripts/lint-model-explicit.sh`가 model·effort 둘 다 기계 검증 — ⛔ **차단이 아니라 "요청 시 검출"이다.** `/fz-manage check`가 호출할 때만 돌고, 실제 차단은 훅 설치 시에만 성립한다(훅은 `settings.json` = 사용자 소관, `modules/governance.md` § Hook 최소 강제 권고)
- **effort 값 선택 (2026-07-25 Opus 5 갱신)**: 현행 워크플로는 전 호출 `'xhigh'` 단일값. Opus 5 공식 권장은 **출발점 `high`(기본)**, **`low`/`medium`을 비용·지연의 1차 레버**, demanding coding/agentic만 `xhigh` [verified: platform.claude.com/docs/en/build-with-claude/effort]. `'xhigh'`는 **여전히 유효 범위**라 현행 배선이 깨진 것은 아니나, 그 근거였던 Opus 4.7/4.8의 *"Start with `xhigh` for coding and agentic use cases"* 문장은 **Opus 5 페이지에 없다**.
  - ⛔ **상수 일괄 교체 금지**: 공식이 *"If you carried effort settings over from an earlier model, **run a fresh effort sweep on your evals** rather than reusing them"* 을 요구. 측정 없이 `xhigh`→`high`로 치환하는 건 근거 없는 값을 근거 없는 값으로 바꾸는 것. **워크로드별 sweep 후** 스테이지 성격(생산/판정/탐색)에 맞춰 차등 배정. 미측정 상태의 기본값 = **현행 유지**.
  - ⚠️ **세션 레벨과 한 세트**: `.js`의 per-call `opts.effort`만 바꿔도 `~/.claude/settings.json`의 `effortLevel`이 남아 있으면 효과가 반감된다 — 두 곳을 함께 검토. [미검증: per-call `opts.effort` vs settings.json `effortLevel` 우선순위. 문서화된 체인은 `env var > frontmatter > 세션`이며 per-call opts는 미명시]
  - ⛔ **effort로 응답 길이를 줄이려 하지 말 것** — Opus 5에서 effort는 사고량을 조절할 뿐 가시 응답 길이를 신뢰성 있게 줄이지 못한다. 길이는 프롬프트로. [verified: 동 effort 문서]

### resume 계약 + advisor 상속 (2026-08-08 신설)

> 신설 정당화 (DELETE/MERGE-default): 본 §12는 배치·호출·model/effort·산출물·intentContext를 이미 소유하나 **중단 후 재개**와 **워커가 상속하는 세션 설정**을 다루지 않았다 — 기존 하위절 흡수 불가. 둘 다 실측으로 확인된 계약만 수록.

**resume** [verified: code.claude.com/docs/en/workflows]
- `Workflow({ scriptPath, resumeFromRunId })` — 변경되지 않은 `agent()` 호출의 **최장 prefix가 캐시로 즉시 반환**되고 첫 변경 지점부터 재실행된다. 같은 스크립트 + 같은 args = 100% 캐시 히트.
- ⛔ **재생 순서 규칙**: *"Cached results stop at the first agent that didn't finish, and **every agent that started after that one runs again, even if it completed**."* → 팬아웃 중간에 멈추면 뒤에 시작된 완료분까지 전부 재실행된다.
- ⚠️ **설계 함의**: 공식 결론은 *"**다수의 작은 에이전트가 하나의 큰 에이전트보다 진행을 더 보존한다**"* 이다. fz의 현행 워크플로는 **소수의 큰 에이전트 + 스테이지 배리어** 구조라 이 방향과 반대다 — 스테이지 세분화의 이득은 **미측정**이며 재검토 대상으로 남긴다.
- **경계**: resume은 **동일 Claude Code 세션 내에서만** 동작한다. CC를 종료하면 다음 세션은 워크플로를 처음부터 시작한다 → 장기 워크플로는 ASD 아티팩트가 여전히 1차 복원 수단이다.
- **진단**: `<transcriptDir>/journal.jsonl`이 agent별 **실제 반환값**을 1줄씩 기록한다. ⛔ 빈 결과·이상 결과 원인 규명 시 **추측 금지, journal 먼저 Read**.
- ⛔ 스크립트 결정성 요구와 한 세트다 — `Date.now()`/`Math.random()`/무인자 `new Date()`는 **throw**된다(resume을 깨뜨리므로).

**세션 설정 상속** [verified: 프로브 `wf_e7136199-140`, 2026-08-08]
- ⛔ **워커는 세션 `advisorModel`을 상속한다.** 1-agent 프로브(`model:'opus'`)가 advisor를 실제 호출해 응답을 받았다 — `{"advisor_tool_available":true,"call_succeeded":true}`. 즉 fz의 opus 워커 전부가 advisor를 호출할 수 있다.
  - **비용 계측 불가**: advisor 호출은 `usage.server_tool_use`에 기록되지 않는다(워커 트랜스크립트 `agent-*.jsonl`에서도 동일). `governance.md §사각지대` 참조 — `opus 동시 ≤3` envelope이 advisor 지출을 bound하지 않는다.
  - ⛔ **ad-hoc 프로브 작성 시 advisor 호출을 유도하는 지시를 넣지 말 것** — 계측되지 않는 지출이 된다(도구 가용성 실증 같은 명시적 목적 제외).
- ⛔ **`CLAUDE_CODE_SUBAGENT_MODEL`은 `opts.model`을 override한다** — *"the model Claude Code uses for all subagents, agent teams, and **agents in a workflow** … overrides the per-invocation `model` parameter and the subagent definition's `model` frontmatter"* [verified: /model-config]. 즉 **본 §12의 "model 명시 의무"를 무력화할 수 있는 유일한 변수**다. 워커 모델이 예상과 다르면 **1순위로 이 env var를 확인**하고, `inherit`로 정상 해석에 복귀시킨다.

### 산출물·거버넌스 계약

- 반환: `{ mode: 'workflow'|'fallback', ..., metrics: { agentCalls, nullCount, fallbackCount, 완주지표 } }` — 완주지표는 구조에 맞는 명칭(`roundsCompleted` 라운드형 / `stagesCompleted` 스테이지형 = **완전 완주 stage 수**), experiment-log §5.7 해당 스킬 칼럼명과 일치 의무 — mode='fallback'이면 Lead가 SOLO 폴백. wall-clock은 Lead 측정 (스크립트 내 시각 API 불가)
- 거버넌스: 동시 실행 ≤4 chunk (governance.md "5개+ 동시 차단" 정합) / **opus 동시 ≤3** (워커 기준 — Lead는 fable, fan-out은 sonnet. **정본 = `guides/fable-model-guide.md` §5** — ⛔ 여기서 값을 재정의하지 않는다) · fable 동시 1 (Lead 제외) / budget 가드는 prose 금지·코드 배선 (`budget.total && budget.remaining() < ...`) — **가변 fan-out 스크립트 의무**, 고정-call 스크립트는 '해당 없음' 헤더 명시로 갈음
- 해석 작업(병합·동일성 판정)은 **agent 언어 지시**, binary 규칙(등급 부여·집계)은 **스크립트 코드** — §11 판단 기준을 단계별로 적용
- 검증 oracle: 래핑 syntax 검사(`async function wrap(...){...본문...}` 후 node --check — 직접 node --check는 CJS 관대 파싱으로 무효) + **실 invoke ≥1** + experiment-log §5.7 지표 기록

### ⛔ 실패 복구 사다리 (`mode:'fallback'` · 스톨 — **본 절이 정본**)

> 신설 근거(2026-08-09): 이전에는 5개 스킬이 폴백 절차로 `modules/team-core.md` + `modules/patterns/`(679줄)를 지목했으나 그 내용은 `TeamCreate`/`SendMessage` **P2P 절차**였다 — SOLO에는 에이전트가 없어 **실행 자체가 불가능**했다. 그런데 실측상 실패는 2회 발생하고 **두 번 다 아래 사다리로 복구**됐다(`experiment-log.md` §5.7 fz-code #1 · fz-review #8). `team-core` 사용 이력은 **0건**이다.
> 즉 본 절은 새 프로토콜을 발명하는 것이 아니라 **이미 작동한 복구 경로를 성문화**한다.

| 단계 | 조건 | 행동 | 실측 선례 |
|:--:|---|---|---|
| **L1** | `mode:'split_required'` 또는 `mode:'fallback'`+`splitSuggested:true` | **Step 분할 후 재invoke** (과대 changeset scaffold collapse 방어 — H5) | — |
| **L2** | `mode:'fallback'` + 입력 오류 (args 파싱·필수 키 누락) | **입력 수정 후 재invoke.** ⛔ 워크플로 실패가 아니라 **설계된 fail-fast**다 | §5.7 fz-code #1 (2026-07-10, args 유니코드 이스케이프 깨짐 → 수정 후 회복) |
| **L3** | 스테이지 스톨·일시 장애(세션/rate limit) | **`resume` 우선** — `Workflow({ scriptPath, resumeFromRunId })`. 변경 없는 agent()의 최장 prefix가 캐시 재생된다 | §5.7 fz-review #8 (2026-07-20, 초회 7287s 스톨 → resume 부분 재시도 성공) |
| **L4** | L1~L3 미해소 | **사용자 에스컬레이션** — 선택지(재시도/범위축소/중단) 제시. ⛔ **Lead 단독 SOLO 수행은 사용자 승인 후에만** (Lead=fable 자동 SOLO 금지) | — |

- ⛔ **`resume`은 동일 Claude Code 세션 내에서만** 동작한다 — 세션이 끝났으면 L3를 건너뛰고 ASD 아티팩트로 복원한다
- ⛔ **재시도는 `buildFeedback` 등을 args에 넣어 캐시 키를 바꾼다** (resume 비의존 경로)
- ⛔ **진단은 추측 금지** — `<transcriptDir>/journal.jsonl`이 agent별 실제 반환값을 기록한다. 빈 결과·이상 결과는 journal을 먼저 Read
- `modules/team-core.md` + `modules/patterns/*.md`는 **라운드 의미론의 역사적 출처**다 — 폴백 실행 절차로 참조하지 않는다

### intentContext 규약 (과제 목적 전달)

워커 프롬프트/args에 과제 목적 3요소를 전달하는 것을 권장한다 — 목적을 알면 워커가 관련 정보를 스스로 연결하고 의도를 오추론하지 않는다 (공식 Fable 5 Intent context: "Give the reason, not only the request").

- **3요소**: (1) larger task — 지금 과제가 속한 상위 작업 · (2) 누구를 위한 것 — 수요자 · (3) 산출물이 가능하게 하는 것 — 이 산출물로 다음에 무엇을 하는가
- **구현 선례**: review-live·peer-review는 `intentContext`를 **필수 args**로 받아(둘 다 누락 시 fail-fast `mode:'fallback'`) TARGET 문자열에 주입; plan-collaborative는 **선택 args**로 받아 CTX 목적 축에 조건부 주입 (`input.intentContext ? '[과제 목적] …' : ''`)
- **OVERRIDE 오염 방어와의 관계**: intentContext는 **프롬프트 내부에 포함되는 정보**이지 외부 컨텍스트 pull이 아니다. OVERRIDE 블록(§ 표준 패턴 3종 1)이 금지하는 것은 에이전트 정의의 ASD 폴더·이전 세션·메모리 자동 로딩이며, Lead가 args로 명시 전달한 목적은 이에 해당하지 않는다 — 오염원이 아니라 과제 정의의 일부

### TEAM 추론 품질 3원칙 보존 매핑 (prompt-optimization §다양성)

| 원칙 | Workflow 보존 |
|------|--------------|
| Round 1 독립성 | 초기 생성 호출에 피어 데이터 미주입 (구조적 보장) |
| Task Brief 5요소 | [역할][문제/컨텍스트][목표] + schema(=Deliverable) + OVERRIDE(=Constraints) |
| 합의/불합의 명시 | schema 필드로 표현 (예: mutability/severity + evidence) |
