# Lead Implication Reasoning

> Lead가 작업 결과를 보고하기 전에 "표면 처리를 넘는 추론"을 수행하는 공통 모듈.
> 참조: fz-code(마찰 감지), fz-review(검증 4-I), fz-plan(Register 출력), fz-codex(Q8), cross-validation.md(게이트 삽입)

## 1. 추론 원칙: Literal vs Semantic Scope

- **Literal Scope**: 지시에 등장한 키워드를 직접 처리
  - 예: "networkService 제거" → `networkService` 포함 코드 삭제
- **Semantic Scope**: 지시의 의도가 달성되기 위해 필연적으로 따라오는 작업
  - 예: "DI 제거" → DI를 위해 추가된 `override init`, stored property, convenience init도 제거 대상

**원칙**: Literal 실행은 최소 조건, Semantic 실행은 완전 조건. 차이가 잔존 코드를 만든다.

---

## 1.5. 추론 원칙: Conclusion Scope Verification

**결론 범위 불일치**: "안전하다/문제없다/OK" 결론에 도달했을 때, 그 결론의 범위가 원래 질문의 범위와 일치하는지 검증한다.

### 부분 → 전체 오류 (Partial-to-Whole Fallacy)

한 측면의 긍정적 결론이 전체 평가를 대체하는 오류.

```
BAD:  hackleApp?.variation() → nil → 기본값 "A" → "안전" → 분석 종료
      → setUserId() nil 동작(userId 유실) 미분석

GOOD: hackleApp?.variation() → nil → 클라이언트 기본값 "A"
      hackleApp?.setUserId() → nil → 서버 IDENTIFIER_NOT_FOUND
      hackleApp?.track() → nil → 이벤트 유실
      → 클라이언트 안전 / 서버 데이터 유실 → 부분적 안전
```

**원칙**: "안전하다" 결론 도달 시 → "이 결론이 다루지 않는 측면은?" 자문. 같은 객체/모듈의 다른 메서드, 다른 이해관계자(클라이언트/서버/대시보드)를 명시적으로 나열.

### 현재 → 본질 오류 (Contingent-to-Inherent Fallacy)

현재 조건에서의 안전을 본질적 안전으로 취급하는 오류.

```
BAD:  "현재 호출부 1곳 → 동시 접근 없음 → thread-safe"
      → public 싱글톤 메서드에 호출부가 추가되면 즉시 unsafe

GOOD: "public 싱글톤 메서드 → 누구든 어디서든 호출 가능 → 본질적으로 thread-safe 구조 필수"
```

**원칙**: 안전성 판단은 "현재 사용 방식"이 아닌 "이 코드의 접근성과 설계"로. public = 미래 호출부 가정 필수. 싱글톤 = 다중 스레드 접근 가정 필수.

### 연산 분류 오류 (Operation Classification Fallacy)

한 블록 내의 "순수 연산"과 "side effect"를 같은 스레드 안전성 범주로 취급하는 오류.

```
BAD:  "JSON 파싱은 순수 연산 → 프로퍼티 할당도 MainActor 불필요"
      → 파싱(순수: 입력→출력, 외부 상태 변경 없음)과 할당(side effect: self.property 변경)은 다른 범주
      → 프로퍼티 할당을 background에서 실행하면 Main thread 소비자와 data race

GOOD: "JSON 파싱은 background OK. 프로퍼티 할당은 소비자 스레드를 확인 후 결정"
      → 파싱: let json = try JSONSerialization... (순수 → 어디서든 OK)
      → 할당: self.requestId = value (side effect → 소비자가 Main이면 MainActor 필요)
```

**원칙**: 코드 블록을 "MainActor 밖으로 이동"할 때, 블록 내 각 문장을 순수 연산(외부 상태 무변경)과 side effect(프로퍼티 할당, UI 갱신, 알림 발송)로 분류. side effect는 소비자 스레드를 확인 후 배치.

### 복합 오류 (Compound Fallacy) — 엣지 케이스

두 오류가 결합되면 검출이 더 어려워진다.

```
BAD:  "현재 호출부 1곳 → 동시 접근 없음" + "앱 크래시 안 함 → 안전"
      → Contingent-to-Inherent + Partial-to-Whole 복합
      → 미래 호출부 미고려 + 서버 데이터 유실 미분석

GOOD: "public 싱글톤 → 다중 접근 가정" + "클라이언트/서버/대시보드 각각 평가"
      → 본질적 안전성 기준 적용 + 이해관계자별 독립 평가
```

---

## 2. 카테고리 분류

### Execution Implication (실행 함의)

빠지면 작업이 절반만 완료된 상태.

- 지시된 작업의 논리적 완결을 위해 필수
- 리터럴 범위 밖이지만 같은 의도 범위 안
- 빠지면 dead code / 불일관성 / 빌드 경고가 남음
- **정책**: 사용자 확인 후 포함 (status: `needs_user_confirmation` → `approved`)

판별: "이것 없이 '완료'라고 할 수 있는가?" → **No**이면 실행 함의

### Observation Implication (관찰 함의)

범위 외 독립적 개선 기회.

- 지시 범위와 직접 연결되지 않음
- 독립적으로 판단이 필요한 설계/아키텍처 이슈
- 현재 지시에서 건드리지 않아도 지시가 완결됨
- **정책**: 보고만. 실행 금지 (status: `report_only`)

판별: "이것 없이 '완료'라고 할 수 있는가?" → **Yes**이면 관찰 함의

### 경계 판단

- 의심스러우면 **관찰 함의로 분류** (과잉 실행 방지)
- 함의 확신 불가 → **AskUserQuestion** (임의 판단 금지 원칙)
- 함의 2건+ 확인 필요 → 일괄 보고 (개별 질문 남발 금지)

---

## 3. 자문 체크리스트

### 전체 모드 (1차/2차 트리거 해당 시)

```
[Q-WHY]      이 코드가 존재하게 된 이유는? 그 이유가 해소되면 이 코드도 불필요한가?
[Q-COMPLETE]  이것 없이 "완료"라고 할 수 있는가?
[Q-EFFECT]    이 변경으로 역할을 잃은 코드가 있는가?
             → find_referencing_symbols로 참조자 확인. "이 변경을 위해 추가된" 코드가 있으면 실행 함의.
```

### 상시 경량 (모든 코드 변경)

```
[Q-OBSERVE]   지시와 무관하게, 탐색 중 설계 문제를 발견했는가?
             → 발견 시 [함의-B] 형식 기록. 실행 금지. 보고 상한: 최대 2건.
[Q-SCOPE]     "안전/OK" 결론의 범위가 질문 전체를 커버하는가?
             → 같은 객체의 다른 메서드, 다른 이해관계자(클라이언트/서버)를 분석했는가?
             → "이 결론이 다루지 않는 측면은?" 명시. 빈 답변 = 분석 부족 의심.
[Q-INHERENT]  이 판단은 본질적 속성인가, 현재 조건인가?
             → "현재 N곳/현재 단일 스레드/현재 사용하지 않음" = 현재 조건 (불안정)
             → "private/actor/lock 보호/프로토콜 제약" = 본질적 속성 (안정)
[Q-COVERAGE]  분석 범위가 "전체/모든"인데, 실제로 전체를 다뤘는가?
             → Glob/find 결과 N개 중 분석한 M개. M/N < 100%면 누락 목록 명시.
             → "분석하지 않은 영역"이 빈 목록이면 분석 부족 의심.
```

---

## 4. Implication Register (plan artifact)

plan 출력에 포함하여 code→review까지 cross-phase 전달.

| ID | Type | Trigger | Locus | Reason | Policy | Status |
|----|------|---------|-------|--------|--------|--------|
| IMP-1 | exec | DI 제거 | SearchBuilder.override init | DI를 위해 추가된 구조 | confirm | pending |
| IMP-2 | obs | 작업 중 발견 | AuthUseCase.maxRetries | caller 주입 = DIP 위반 | report | report_only |

- **exec** 항목: plan의 Step에 명시. code에서 승인 후 구현. review에서 누락 검증.
- **obs** 항목: plan의 별도 "관찰 사항" 섹션. code에서 수정 금지. review에서 보고 존재 확인.
- Status: `pending` → `approved` (사용자 확인) / `dismissed` (사용자 거부) / `report_only` (관찰)

---

## 5. 보고 템플릿

### [함의-A] 실행 함의

```
[함의-A] 실행 함의 발견

목적 코드: {파일:심볼}
함의 이유: "{지시}"가 완료되면 이 코드의 존재 이유({이유})가 해소됨.
제안 행동: {삭제/수정} 필요
포함 여부: 사용자 확인 요청
```

### [함의-B] 관찰 함의

```
[함의-B] 관찰 함의 (현재 작업 범위 외)

발견 위치: {파일:심볼}
관찰 내용: {구체적 현상}
아키텍처 의미: {왜 문제인지}
권장 행동: 별도 티켓 권장
현재 작업 영향: 없음 (진행 계속 가능)
```

---

## 6. 모드

| 모드 | 조건 | 실행 범위 |
|------|------|----------|
| **전체** | 1차/2차 트리거 해당 | Q-WHY + Q-COMPLETE + Q-EFFECT + 상시(Q-OBSERVE, Q-SCOPE, Q-INHERENT) |
| **최소** | urgency 신호 ("빠르게", "급해") | 실행 함의(컴파일 직결)만. 관찰은 파일 저장만, 출력 안 함 |
| **revert** | revert/되돌리기 작업 | 실행 함의 비활성. 관찰만 선택적 허용. "원본에도 존재하던 패턴" 제외 |

---

## 7. 변경 유형별 구조적 잔존물 체크리스트

plan의 Anti-Pattern Constraints 작성 시 참조.

| 변경 유형 | 확인할 잔존물 | Grep 패턴 예시 |
|----------|-------------|---------------|
| DI 제거 | override init, stored property, convenience init, DI용 protocol | `override init` |
| 프로토콜 삭제 | conformance 선언, extension, 메서드 구현 | `: {Protocol}` |
| 클래스 계층 변경 | override 메서드, super 호출, 하위 init | `override func`, `super.` |
| import 제거 | typealias, utility 타입 잔존 사용 | (Symbol Inventory) |
| 싱글톤 → DI | .shared 호출, 글로벌 접근 경로 | `.shared` |

---

## 8. 트리거 조건

### 1차 트리거 (전체 Implication Scan)

지시 키워드: `제거`, `삭제`, `이동`, `이관`, `마이그레이션`, `리팩토링`, `DI 변경`, `revert`

### 2차 트리거 (전체 Implication Scan)

변경 유형: `프로토콜 변경`, `access control 변경`, `init/signature 변경`, `모듈 경계 변경`

### 상시 (Q-OBSERVE + Q-SCOPE + Q-INHERENT)

모든 코드 변경 + 문서/파일 전체 분석에서 경량 스캔. 안전성 결론의 범위 검증(§1.5) + 분석 커버리지 검증(Q-COVERAGE)을 포함.

---

## 9. 검증 4 vs 4-I 경계

> **검증 4 (Refactoring Completeness)**: diff 기준 — "새 심볼이 기존을 대체했는가? deprecated dead code?" → **구조적 완결성** (judge)
> **검증 4-I (Implication Coverage)**: 지시 기준 — "지시의 의미론적 범위 전체가 diff에 포함됐는가?" → **의미론적 완결성** (auditor)
> 검증 4는 diff **안**을 보고, 4-I는 지시에서 diff **밖**으로 시야를 확장한다.

## 참조 스킬

| 스킬/모듈 | 참조 이유 |
|----------|----------|
| fz-code | 마찰 감지 테이블 — 구조적 잔존물 + 관찰 보고 의무 |
| fz-review | 검증 4-I + 완료 보고 관찰 섹션 |
| fz-plan | Implication Register 출력 + Anti-Pattern 가이드 참조 |
| fz-codex | Q8 함의 커버리지 |
| cross-validation.md | Implication Scan 게이트 + origin-equivalence |
