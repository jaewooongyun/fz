# 스킬 테스팅 가이드

> fz-* 스킬의 품질을 측정 가능하게 보장하는 테스트 방법론.
> Anthropic 32p Skills Guide(2026-01-29)의 3단계 테스트 프레임워크 기반.

---

## 1. 테스트 3단계 프레임워크

### 1.1 Triggering Test — 트리거 정확도 측정

스킬이 올바른 쿼리에서 트리거되는지 확인한다.

**절차:**
1. should-trigger + should-NOT-trigger 쿼리 목록을 작성한다 (최소 10개)
2. 각 쿼리를 Claude에 입력하고 스킬 트리거 여부를 기록한다
3. 트리거율을 계산한다: `정확 트리거 수 / 전체 테스트 수`
4. 목표: 관련 쿼리의 90% 이상에서 정확 트리거

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
      then: "{예상 결과}"
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

## 참조

- 스킬 작성법: `guides/skill-authoring.md`
- 트러블슈팅: `guides/skill-troubleshooting.md`
- 프롬프트 최적화: `guides/prompt-optimization.md`
- Codex 교차검증: `skills/fz-codex/SKILL.md`
- 스킬 품질 평가: `/fz-skill eval` (`fz-skill/SKILL.md`)
- 일괄 벤치마크: `/fz-manage benchmark` (`fz-manage/SKILL.md`)
- Anthropic 공식 평가: `/skill-creator` (Eval/Improve/Benchmark 모드)
