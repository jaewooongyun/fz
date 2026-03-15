# Prompt & Skill Optimization Guide

> 실전 최적화 체크리스트. 이론이 아닌 즉시 적용 가능한 가이드.
>
> **Sources:**
> - Anthropic Claude 4 Best Practices (2026-02-24)
> - Anthropic Skill Authoring Best Practices
> - Anthropic 32-page Skills Guide (2026-01-29)
> - ACE: Agentic Context Engineering (Stanford, arXiv 2510.04618)
> - Context Rot (Chroma Research, 18 frontier models)
> - Building Effective Agents (Anthropic 2024-12)
> - Agents at Work: 2026 Playbook
> - S10: Anthropic Platform Best Practices (2026) — Long context tips, State management (structured+unstructured), Context awareness, Multi-context window workflows
> - S11: Anthropic Claude Code Best Practices (2026) — /btw ephemeral pattern, Kitchen sink 방지, Subagent isolation, Compaction instructions in CLAUDE.md, filesystem > compaction

---

## 1. 10대 원칙 체크리스트

---

### 원칙 1: Claude가 모르는 것만 추가

**근거:** Anthropic — "Claude is already very smart." 일반 지식을 반복하면 토큰만 소비하고 성능은 올라가지 않는다.

**체크리스트:**
- [ ] Claude가 이미 아는 일반 지식을 설명하고 있지 않은가?
- [ ] 프로젝트 고유 정보만 포함하고 있는가?
- [ ] 언어/프레임워크 기본 문법을 다시 가르치고 있지 않은가?
- [ ] 외부 라이브러리의 공식 문서 내용을 복사하고 있지 않은가?

**Before / After:**
```
BAD:  "PDF는 Portable Document Format의 약자로, Adobe가 만든 문서 형식입니다..."
GOOD: "pdfplumber로 추출: pdf.pages[0].extract_text() — 레이아웃 깨지면 extract_table() 사용"

BAD:  "Python의 리스트는 순서가 있는 자료구조입니다..."
GOOD: "이 프로젝트에서 리스트 직렬화는 orjson.dumps()를 사용한다 (json.dumps 금지)"
```

---

### 원칙 2: Description이 곧 성능

**근거:** Skills Deep Dive — "no algorithmic skill selection." Claude는 description 텍스트 매칭으로 스킬을 선택한다. description이 부정확하면 스킬이 호출되지 않거나 잘못 호출된다.

**체크리스트:**
- [ ] 무엇을 하는지 (what) 포함?
- [ ] 언제 사용하는지 (when to use) 포함?
- [ ] 언제 사용하지 않는지 (when NOT to use) + 대안 명시?
- [ ] 한국어 + 영어 키워드 모두 포함?
- [ ] 3인칭 서술 (Claude 시점)?

**Before / After:**
```
BAD:
  "Helps with documents"

GOOD:
  "프로젝트 코드 탐색 + 구조 분석 스킬 (code exploration, structure analysis).
   Use when exploring code structure, understanding architecture, or finding patterns.
   Do NOT use for code modification (use fz-fix instead) or test execution (use fz-test)."
```

**Tip:** 사용자가 실제로 입력할 자연어 표현을 상상하고, 그 키워드를 description에 포함시켜라.

---

### 원칙 3: 500줄 이하 + Progressive Disclosure

**근거:**
- Context Rot (Chroma) — "focused 300 tokens > unfocused 113K tokens"
- Anthropic 32p Guide — 3-level progressive disclosure

**체크리스트:**
- [ ] SKILL.md 본문 500줄 이하?
- [ ] 상세 내용은 별도 파일로 분리 (Read로 참조)?
- [ ] 참조 파일은 1단계 깊이만? (SKILL.md -> ref.md OK, ref.md -> detail.md NO)
- [ ] 100줄 이상 참조 파일에 목차 포함?
- [ ] 핵심 지시가 문서 앞부분 또는 끝부분에 배치되어 있는가?
- [ ] ⛔ **트리밍으로 실행 품질이 저하되지 않았는가?** (보충 3a 참조)

**3-Level Structure:**
```
Level 1: YAML frontmatter    -> 항상 로드 (스킬 발견 + 매칭)
         - name, description, allowed-tools
         - 이 단계에서 스킬 선택 여부가 결정됨

Level 2: SKILL.md 본문       -> 관련 시 로드 (실행 지침)
         - 핵심 워크플로우, 규칙, 예시
         - 500줄 이내로 유지

Level 3: 참조 파일            -> 필요 시 Read (상세 레퍼런스)
         - API 스펙, 코드 템플릿, 설정 파일
         - SKILL.md에서 "Read /path/to/ref.md for details" 형태로 연결
```

**Before / After:**
```
BAD:  하나의 SKILL.md에 API 스펙, 예시, 설정, 트러블슈팅 모두 포함 (1200줄)
GOOD: SKILL.md (200줄 핵심) + api-spec.md (참조) + troubleshooting.md (참조)
```

#### 보충 3a: 트리밍 비저하 원칙

500줄 달성을 위한 트리밍이 **프롬프트 실행 품질(= 스킬·에이전트 성능)**을 저하시키면 본말전도.

| 삭제 금지 (실행 핵심) | 압축 허용 (영향 적음) |
|----------------------|---------------------|
| Gate 체크리스트 항목 | 서식·포맷팅 (코드블록→인라인) |
| Few-shot BAD/GOOD 예시 | 반복 설명 (동일 원칙의 재언급) |
| 절차적 Step (순서 중요) | 도구 호출 예시 (Claude가 아는 것) |
| 에이전트 Task Brief 포맷 | 설명적 주석·배경 설명 |

**500줄 초과 시**: 삭제보다 **모듈 분리**(`modules/`)를 먼저 시도. 줄 수는 줄이되 정보는 보존.

```
BAD:  Gate 체크리스트 5개 항목을 1줄로 요약 → 3개 검증 단계 스킵됨
GOOD: Gate 체크리스트 유지, 대신 Phase 설명 서문을 삭제하여 줄 수 확보

BAD:  Tier 2 실행 시퀀스 코드 블록 삭제 → 에이전트가 TeamCreate 순서 무시
GOOD: 코드 블록을 인라인 설명으로 전환, 핵심 순서 (TeamCreate→Task→Agent) 보존
```

---

### 원칙 4: 자유도를 작업 위험도에 맞춰라

**근거:** Anthropic — "degrees of freedom." 위험한 작업에는 정확한 스크립트를, 안전한 작업에는 방향만 제시하라.

**Decision Table:**

| 위험도 | 자유도 | 지시 방식 | 예시 |
|--------|--------|-----------|------|
| 높음 (DB migration, API breaking change) | 낮음 | 정확한 스크립트, 명령어 그대로 실행 | `alembic upgrade head` 실행 후 `SELECT count(*) FROM users` 검증 |
| 중간 (리포트 생성, 일반 기능 구현) | 중간 | 슈도코드 + 패턴 제시, 변형 허용 | "pagination은 cursor 방식으로 구현. 예시 참조" |
| 낮음 (코드 리뷰, 탐색, 문서화) | 높음 | 가이드라인만 제시, 판단 위임 | "코드 품질 이슈를 찾아 개선안을 제시하라" |

**체크리스트:**
- [ ] 각 작업의 위험도를 명확히 분류했는가?
- [ ] 고위험 작업에 정확한 명령어/스크립트가 포함되어 있는가?
- [ ] 저위험 작업에 불필요하게 상세한 지시를 하고 있지 않은가?

---

### 보충 4a: 원칙+이유로 프레이밍하라

**근거:** Anthropic Claude 4 Best Practices — "Prefer general instructions over prescriptive steps.
Claude's reasoning frequently exceeds what a human would prescribe."
+ IFScale (arXiv:2507.11538) — 규칙 수 증가 시 정확도 저하 (500규칙→68%).

행동 가이드를 작성할 때, "X이면 Y를 하라" 대신 "Z를 추구하라. 이유: W" 형태를 사용한다.
Claude는 이유에서 유사한 모든 상황으로 일반화한다.

**Before / After:**

```
BAD:  "continuation bridge가 있고 native async가 있으면 → bridge를 제거하라"
GOOD: "동일 동작을 가장 적은 코드로 표현하는 것이 진짜 최소 변경이다.
       라이브러리가 native API를 제공하면 bridge보다 직접 호출이 코드가 적다."

BAD:  "독립 비동기 호출 2+개가 순차이면 → 병렬화 마찰 신호를 보고하라"
GOOD: "독립적인 작업이 순차로 되어 있으면 성능 기회를 놓친 것이다."
```

**3-Tier 콘텐츠 분류:**

| Tier | 내용 | 예시 |
|------|------|------|
| Tier 1: 원칙+이유 | Claude의 행동 방향 (일반화 가능) | "최소 코드 = 최소 변경" |
| Tier 2: 프로젝트 사실 | Claude가 발견할 수 없는 정보 | iOS 16 최소 타겟, RIBs 네이밍 |
| Tier 3: 아키텍처 경계 | 훅/권한으로 강제하는 것 | build 명령, allowed-tools |

**체크리스트:**
- [ ] 규칙에 "이유"가 함께 있는가?
- [ ] 체크리스트 행을 추가하려는 충동이 들 때, 원칙 하나로 대체할 수 있는가?
- [ ] Claude가 이미 아는 프로그래밍 판단을 if-then 테이블로 만들고 있지 않은가?

---

### 원칙 5: Few-shot 예시 > 장문 설명

**근거:** Anthropic + academic survey consensus. 3줄의 BAD/GOOD 대비 예시가 30줄의 설명보다 효과적이다.

**체크리스트:**
- [ ] BAD/GOOD 대비 쌍 예시 3-5개 포함? (잘못된 접근 vs 올바른 접근)
- [ ] `<example>` 태그 또는 코드 블록으로 명확히 구분?
- [ ] 엣지 케이스 최소 1개 포함?
- [ ] 예시가 실제 프로젝트 데이터를 반영하는가?

**Template:**
```xml
<example>
User: 사용자 목록을 가져와줘
Steps:
1. Read /src/api/users.ts to understand the endpoint
2. Check /src/types/user.ts for the User type
3. Return summary with endpoint, params, response shape
Output: GET /api/v2/users — params: {page, limit} — returns: User[]
</example>

<example type="edge-case">
User: 빈 응답이 와요
Steps:
1. Check if the endpoint returns 200 with empty array vs 404
2. Verify database connection and query
Output: 빈 배열 []은 정상 응답. 404와 구분 필요 → /src/api/errorHandler.ts 참조
</example>
```

---

### 원칙 6: 피드백 루프 내장

**근거:** Anthropic + Building Effective Agents. 생성만 하고 검증하지 않으면 오류가 누적된다.

**Pattern:** 생성 -> 검증 -> 수정 -> 재검증

**체크리스트:**
- [ ] Gate 조건을 체크리스트 형태로 명시했는가?
- [ ] 실패 시 구체적 행동이 명시되어 있는가?
- [ ] "validate -> fix -> repeat" 패턴이 적용되어 있는가?
- [ ] 최대 반복 횟수가 설정되어 있는가?

**Before / After:**
```
BAD:  "코드를 작성하라"
GOOD: "코드를 작성하라. 완료 후 typecheck를 실행하고, 실패 시 수정하라. 3회 반복 후에도 실패하면 보고하라."
```

---

### 원칙 7: 도구 설명에 프롬프트만큼 공 들이기

**근거:** Building Effective Agents — "Tool descriptions deserve as much prompt engineering as the prompt itself."

**체크리스트:**
- [ ] `allowed-tools`에 필요한 도구만 포함되어 있는가?
- [ ] 불필요한 도구가 목록에 없는가? (도구가 많을수록 혼란 증가)
- [ ] MCP 도구 활용 전략이 계층화되어 있는가?
- [ ] Bash 패턴 제한이 필요한 경우 적용되어 있는가?

**MCP Tool Layering:**
```
Primary:    작업에 직접 필요한 도구 (항상 포함)
Secondary:  조건부로 필요한 도구 (상황에 따라 포함)
Fallback:   대안 도구 (Primary 실패 시 사용)
```

---

### 원칙 8: Claude 4.6 과격 표현 제거

**근거:** Anthropic Claude 4 Best Practices (2026-02-24). Claude 4.6은 이전 모델보다 훨씬 proactive하다. 과격한 지시어는 overtriggering을 유발한다.

**체크리스트:**
- [ ] "CRITICAL", "MUST ALWAYS", "NEVER EVER" 등의 표현이 없는가?
- [ ] "ABSOLUTELY ESSENTIAL", "UNDER ANY CIRCUMSTANCES" 등의 표현이 없는가?
- [ ] Anti-laziness 프롬프팅 ("be thorough", "don't be lazy")이 없는가?
- [ ] 모든 대문자 강조가 자연스러운 표현으로 대체되었는가?

**Before / After:**
```
BAD:  "CRITICAL: You MUST ALWAYS use this tool for EVERY file operation"
GOOD: "Use this tool when reading or modifying files"

BAD:  "NEVER skip this step under ANY circumstances"
GOOD: "Complete this step before proceeding"

BAD:  "This is ABSOLUTELY ESSENTIAL and you MUST NOT forget"
GOOD: "This step ensures output quality"

BAD:  "Be thorough and don't be lazy. Check EVERYTHING."
GOOD: "Check the relevant files before making changes"
```

**Why this matters:**
- Claude 4.6은 지시를 충실히 따르려는 경향이 강함
- 과격한 표현은 불필요한 상황에서도 해당 행동을 트리거함
- 결과: 과도한 도구 호출, 불필요한 검증 반복, 서브에이전트 남용
- 자연스럽고 구체적인 표현이 더 정확한 행동을 유도함

#### 보충 8a: Anti-laziness 배치 전략

과격 표현을 제거한 후 모델이 검증을 건너뛰는 경우:
- SKILL.md에 다시 넣지 않는다 (overtriggering 위험)
- **user prompt** 쪽에 격려 문구를 배치한다
  - "Take your time to do this thoroughly"
  - "Quality is more important than speed"
  - "Do not skip validation steps"
- 공식 가이드: "Adding this to user prompts is more effective than in SKILL.md"

---

### 원칙 9: Boundaries 명확히 명시

**근거:** 명확한 경계 설정이 스킬 간 충돌을 방지하고 예측 가능한 행동을 보장한다.

**체크리스트:**
- [ ] Will 목록 (하는 것)이 구체적으로 정의되어 있는가?
- [ ] Will Not 목록 (하지 않는 것)이 명시되어 있는가?
- [ ] Will Not 항목마다 대안이 명시되어 있는가?
- [ ] 다른 스킬과의 경계가 명확한가?

**Template:**
```markdown
## Scope

**Will:**
- 코드 구조 분석 및 아키텍처 설명
- 파일 간 의존성 추적
- 리팩토링 방향 제안

**Will Not:**
- 코드 직접 수정 -> use `fz-fix` skill
- 테스트 실행 -> use `fz-test` skill
- 새 파일 생성 -> use `fz-scaffold` skill
```

---

### 원칙 10: 평가 먼저, 문서 나중

**근거:** Anthropic — "evaluation-driven development." 평가 없이 작성한 프롬프트는 실제 효과를 알 수 없다.

**Process:**
```
1. 스킬 없이 실제 작업 수행
   -> 어디서 실패하는지 기록
   -> 어디서 잘못된 판단을 하는지 기록

2. 3개 이상 평가 시나리오 작성
   -> 정상 케이스 1개
   -> 엣지 케이스 1개
   -> 실패 유도 케이스 1개

3. 베이스라인 측정
   -> 스킬 없이 각 시나리오 실행
   -> 성공/실패/부분성공 기록

4. 최소한의 지시문 작성
   -> 실패 지점만 해결하는 최소 프롬프트
   -> 평가 시나리오 재실행
   -> 통과 여부 확인

5. 반복 개선
   -> 실패 시나리오 추가
   -> 프롬프트 수정
   -> 다시 평가
```

**체크리스트:**
- [ ] 스킬 작성 전에 실패 지점을 파악했는가?
- [ ] 최소 3개의 평가 시나리오가 있는가?
- [ ] 베이스라인 대비 개선이 측정 가능한가?
- [ ] 불필요한 지시문을 제거하고도 평가를 통과하는가?

#### 보충 10a: Single Task First

평가 시나리오 작성 전에:
1. 스킬 없이 단일 도전적 작업을 수행한다
2. 실패/비효율 지점을 기록한다
3. 성공 패턴을 추출하여 스킬 초안으로 만든다
→ 이것이 가장 빠른 스킬 개발 경로이다 (공식 가이드 Pro Tip)

---

## 1b. TEAM 모드 추론 품질 3원칙 (2026-03-10 추가)

> Sources: MAST 프레임워크 (arXiv 2503.13657), DyLAN (COLM 2024), Addy Osmani Agent Teams
> 참고: `fz-enhancement/references.md`

TEAM 모드에서 고성능 추론을 보장하는 3축:

### 측정 (Measurement)

**Reflection Rate**: Codex가 제기한 이슈 N개 중 Claude가 수정 반영한 수 / N × 100%
- Gate: ≥80% (TEAM review). SOLO는 추적 없음.
- 정량 계산식이 있어야 "얼마나 잘 반영했는가"를 측정할 수 있다.

**체크리스트:**
- [ ] Codex 교차검증 결과에 이슈 수와 반영 수가 명시되어 있는가?
- [ ] Reflection Rate가 Gate 조건으로 적용되고 있는가?

### 강제 (Enforcement)

**Gate 절차적 강제**: 검증 게이트는 "권고"가 아닌 **절차적 강제**. 스킵 불가.
- build, codex check, stress-test, Reflection Rate — 각각 스킵 조건이 정의됨
- Gate 실패 시 해당 단계를 "완료"로 표시할 수 없다

**Evaluator-Optimizer 패턴**: fz-plan stress-test에서 Critical 리스크 2개+ 발견 시 자동 재작성 (최대 2회).
- 2회 후에도 실패 → 사용자 에스컬레이션

**체크리스트:**
- [ ] 스킬에 Gate가 있을 때 "스킵 불가" 조건이 명시되어 있는가?
- [ ] 반복 루프에 max-iterations가 설정되어 있는가?

### 다양성 (Diversity)

**Sycophancy 방어 — Round 1 독립성**: 에이전트가 서로의 초안을 보기 전에 독립 분석을 완료해야 한다.
- MAST: 67% 오류는 에이전트 간 상호작용에서 발생. "false consensus"가 핵심 실패 모드.
- Round 1에서 독립성을 보장하면 동조 편향을 차단한다.

**Task Brief 5요소**: 에이전트에게 작업 전달 시 `[Role] [Context] [Goal] [Constraints] [Deliverable]` 형식.
- 구조화된 전달이 역할 경계 모호 → 중복/누락 작업 방지

**합의/불합의 명시**: Round 0.5에서 `[합의]` 또는 `[불합의]` 마커로 최종 보고.
- 의견 차이가 묻히는 것을 방지. Lead가 판단 근거를 확보.

**체크리스트:**
- [ ] TEAM 모드 에이전트에 Task Brief 5요소 형식을 사용하고 있는가?
- [ ] 에이전트 간 독립 분석 → 피드백 → 최종 보고 순서가 지켜지는가?
- [ ] 합의/불합의가 명시적으로 보고되는가?

---

## 2. Context Rot 대응 (핵심 수치)

> Source: Context Rot (Chroma Research, 18 frontier models 대상 실험)

| 발견 | 수치 | 대응 |
|------|------|------|
| 집중된 300토큰이 비집중 113K토큰보다 우수 | 대화 기반 작업 기준 | 핵심만 포함하고 불필요한 내용 제거 |
| 중간 위치 정보 검색률 하락 | 30%+ 성능 하락 (Lost-in-the-Middle) | 핵심 지시를 문서 앞부분 또는 끝부분에 배치 |
| 64K 토큰 이상에서 전 모델 성능 저하 | Context Rot 발생 구간 | Progressive Disclosure 필수 적용 |
| 주제 관련 오답이 무관 콘텐츠보다 해로움 | Distractor Interference 효과 | 부정확하거나 오래된 정보는 삭제 |

**실전 적용 규칙:**

```
1. 문서 구조: 핵심 지시 (앞) -> 세부 사항 (중간) -> 요약/체크리스트 (끝)
2. SKILL.md 본문: 500줄 이하 유지
3. 참조 파일: 필요할 때만 Read로 로드
4. 오래된 정보: 정기적으로 감사하여 제거
5. 유사 내용 중복: 하나로 통합
```

---

## 2.5. Context Budget 관리 (실행 품질 보호)

> **1순위: 성능** — context 여유가 추론 품질을 결정한다. 토큰 절약은 수단이지 목적이 아니다.
> Source: Context Mode (mksg.lu), Cloudflare Code Mode, 서브에이전트 토큰 연구 (dev.to), hyperdev 컨텍스트 보호

### 왜 중요한가

- 1M context에서는 auto-compact가 200K 대비 훨씬 늦게 발동하므로 context 여유가 크다 <!-- 기존: 200K 토큰 중 사용 가능량 ~150K -->
- auto-compact 발동 = 맥락 손실 = 실행 품질 하락
- **집중된 300 토큰 > 비집중 113K 토큰** (§2 Context Rot 수치)
- 따라서 context를 절약하는 모든 기법은 **성능 보호**를 위한 것

### 원칙

**A. MCP 도구 출력 최소화** — context 소비의 최대 원인
```
BAD:  서브에이전트가 MCP 결과를 그대로 대화 context에 남김 (수만 토큰)
GOOD: 대용량 결과 → 파일로 저장 (-o 옵션, Write) → 필요 시 Read로 참조

BAD:  Grep 결과를 제한 없이 출력 (수천 줄)
GOOD: head_limit 설정 + 필요한 파일만 선별 Read
```

**B. 중간 데이터 격리** — "결과만 context에, 과정은 파일로"
- Codex 결과: `-o` 옵션으로 파일 출력 (ASD 폴더 또는 WORK_DIR)
- 에이전트 분석 결과: JSON 파일로 저장 후 Lead가 Read
- 긴 diff/심볼 데이터: 파일로 저장 후 참조

**C. 도구 정의 최소화** — 등록만으로 context 소비
- 에이전트 스폰 시 `tools` 필드에 필요한 도구만 명시
- defer_loading 활용: 필요 시에만 ToolSearch로 로드
- 통합 가능한 도구는 통합 (20개→8개 = 60% 감소 사례)

**D. 서브에이전트 효율** — 스폰마다 ~50K 토큰 재주입
- 단순 작업은 서브에이전트 대신 직접 실행
- TEAM 모드에서만 에이전트 스폰 (standalone Agent 남발 금지)
- governance.md 에이전트 상한 준수

**E. Proactive Context Protocol** — compact 전 선제 기록
- Upstream Hydration Sets + Essential Context 패턴 적용: `modules/context-artifacts.md` 참조
- Filesystem discovery > compaction (Anthropic 공식): compact 후 파일 Read가 context summary보다 정확
- Ephemeral vs Persistent 질문 판별: `/btw`(일회성, 향후 Phase에 영향 없음) vs `/fz-discover`(persistent, 향후 Phase 영향 시)

**체크리스트:**
- [ ] 대용량 MCP 결과를 파일로 격리했는가? (context에 raw 출력 남기지 않음)
- [ ] 에이전트 tools 필드가 최소한으로 설정되어 있는가?
- [ ] 서브에이전트 없이 직접 해결할 수 있는 작업을 위임하고 있지 않은가?
- [ ] 4+ 스텝 파이프라인에서 ASD 파일 기반 전략을 사용하고 있는가?

---

## 3. ACE 패턴: 진화하는 플레이북

> Source: ACE - Agentic Context Engineering (Stanford, arXiv 2510.04618)

프롬프트를 정적 문서가 아닌 **진화하는 플레이북**으로 관리하라.

### Delta Updates
- 전체 재작성이 아닌 점진적 편집
- 변경 이력을 추적 가능하게 유지
- 한 번에 하나의 변수만 변경하여 효과를 측정

### Grow-and-Refine
```
Phase 1 (Grow):   새로운 실패 패턴 발견 시 지침 추가
Phase 2 (Refine): 의미적으로 유사한 지침을 병합
Phase 3 (Prune):  효과가 없는 지침을 제거
```

### 실패 패턴 기록
- 실패한 작업의 패턴을 명시적으로 기록
- 다음 실행에 해당 패턴을 회피하도록 반영

### 주기적 Redundancy 감사
- [ ] 월 1회 전체 스킬 문서 검토
- [ ] 중복 지침 병합
- [ ] 더 이상 유효하지 않은 지침 제거
- [ ] 새로운 실패 패턴 반영 여부 확인

---

## 4. Anti-Patterns

| Anti-Pattern | 이유 | 대안 |
|-------------|------|------|
| Windows 경로 (`\`) | Unix 환경에서 에러 발생 | `/` 사용 (POSIX 경로) |
| 너무 많은 선택지 제시 | 판단 혼란, 결정 지연 | 기본값 1개 + 대안 1개 |
| 시간 의존 정보 ("2026년 3월 기준") | 곧 오래된 정보가 됨 | 상대 표현 또는 버전 기반 표현 사용 |
| 비일관적 용어 사용 | 같은 개념에 다른 이름 -> 혼동 | 용어를 하나로 통일, 용어집 관리 |
| 깊은 참조 중첩 (A -> B -> C -> D) | Context Rot 가속, 정보 손실 | 최대 1단계 깊이만 허용 |
| "CRITICAL / MUST ALWAYS" 남용 | Claude 4.6에서 overtriggering 유발 | 자연스럽고 구체적인 표현 사용 |
| 과도한 서브에이전트 위임 | Claude 4.6의 과잉 위임 경향 강화 | 단순 작업은 직접 실행하도록 지시 |
| Claude가 아는 것을 다시 설명 | 토큰 낭비, Context Rot 가속 | 프로젝트 고유 정보만 포함 |
| 실패에서 체크리스트 행 추가 반사 | 규칙 수 증가→준수율 저하, Claude 추론 억압 | 원칙+이유 한 줄로 대체 (보충 4a) |
| 예시 없이 장문으로 설명 | 모호함, 해석 편차 | Few-shot 예시 3-5개로 대체 |
| 검증 단계 없이 생성만 지시 | 오류 누적, 품질 저하 | validate -> fix -> repeat 루프 내장 |
| 모든 도구를 allowed-tools에 포함 | 불필요한 도구 호출 증가 | 필요한 도구만 선별 |
| 스킬 간 책임 범위 중복 | 충돌, 예측 불가 행동 | Will / Will Not 경계 명확히 설정 |
| TEAM에서 Gate를 "권고"로 취급 | 검증 누락, 품질 저하 | Gate 절차적 강제 (스킵 불가 조건 명시) |
| 에이전트 간 초안 공유 후 분석 | Sycophancy/동조 수렴 | Round 1 독립 분석 → Round 2 피드백 순서 강제 |
| 비구조화 Task 전달 | 역할 혼동, 중복/누락 작업 | Task Brief 5요소 형식 사용 |

---

## Quick Reference: 스킬 작성 전 최종 점검

```
[ ] 1. Claude가 이미 아는 내용을 제거했는가?
[ ] 2. Description에 what / when / when-not이 포함되어 있는가?
[ ] 3. 본문 500줄 이하인가? (트리밍 시 Gate/Few-shot/Step 삭제 금지 — 보충 3a)
[ ] 4. 위험도에 맞는 자유도를 설정했는가?
[ ] 4a. 행동 가이드가 "원칙+이유" 형태인가? (if-then 테이블이 아닌가?)
[ ] 5. Few-shot BAD/GOOD 대비 쌍이 3개 이상 포함되어 있는가?
[ ] 6. 검증 Gate가 내장되어 있는가? (절차적 강제: 스킵 불가 조건 명시)
[ ] 7. 도구 목록이 최소한으로 설정되어 있는가?
[ ] 8. 과격한 표현을 자연스럽게 대체했는가?
[ ] 9. Will / Will Not 경계가 명확한가?
[ ] 10. 평가 시나리오로 효과를 검증했는가?
[ ] 11. TEAM 모드: Task Brief 5요소 형식 사용? (§1b)
[ ] 12. TEAM 모드: Round 1 독립성 + 합의/불합의 보고? (§1b)
[ ] 13. 대용량 MCP 결과를 파일로 격리했는가? (§2.5 Context Budget)
```
