# 스킬 작성 실전 가이드

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

### 원칙 8: Claude 4.6/4.7 과격 표현 제거

Claude 4.6은 과격한 지시어에 overtriggering을 일으킨다. **Opus 4.7 (2026-04-16 GA)** 부터는 "more literal instruction following" 변화로 인해 과격 지시가 더욱 literal하게 적용될 위험이 증가했다 [verified: anthropic.com/news/claude-opus-4-7]. **GPT-5.5 (2026-04-23 GA)** 도 동일 방향 변화 ("literal and thorough manner") [verified: developers.openai.com/api/docs/guides/latest-model] — frontier 트렌드.

```
BAD:  "CRITICAL: You MUST ALWAYS use this tool"
GOOD: "Use this tool when reading or modifying files"
```

- "CRITICAL", "MUST ALWAYS", "NEVER EVER" → 자연스러운 표현으로 대체
- Anti-laziness가 필요하면 SKILL.md가 아닌 user prompt 쪽에 배치
- 참조: `guides/prompt-optimization.md` 동일 원칙 8 (Opus 4.7 literal interpretation 상세)

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

```yaml
team-agents:
  primary: impl-correctness         # Primary Worker → 팀에서 opus로 승격
  supporting: [review-arch]          # Supporting → sonnet 유지
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
| Lead (오케스트레이터) | opus | 최종 판단, 게이트 실행 |
| Primary Worker (핵심 생산) | opus (승격) | 계획, 코드, 설계 품질 |
| Supporting (검증, 비평) | sonnet | 비용 효율, 충분한 품질 |
| haiku | **미사용** | 프로젝트 정책 |

### 승격 규칙

- SOLO 모드: 스킬 기본 모델 사용 (보통 sonnet)
- TEAM 모드: Primary Worker가 opus로 자동 승격
- Supporting은 항상 sonnet 유지 — opus 승격 금지

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
