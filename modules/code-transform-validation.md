# Code Transformation Validation

> 코드 변환(Before→After)이 포함된 작업에서 **동작 동등성 + 구조 품질**을 검증하는 공유 모듈.
> 참조: fz-plan(Spec 작성), fz-code(BEC 검증), fz-review(Spec 준수), fz-fix(패턴 변환), fz-peer-review(외부 PR)

## 트리거 조건

- 비동기 패턴 변환 (PromiseKit→async/await, Combine→async, callback→async)
- 네트워크 레이어 전환 (Alamofire→URLSession, NetRequest→Repository)
- UI 프레임워크 전환 (UIKit→SwiftUI, RxSwift→Combine)
- 스레드 모델 변경 (GCD→Swift Concurrency, DispatchQueue→Actor)

> 단순 이름 변경, 1:1 텍스트 치환에는 적용하지 않는다.

---

## Transformation Spec (v3.8)

Plan의 각 패턴 변환 Step에 작성. fz-code/fz-review가 참조.
`spec-version` 필드 필수. v3.7 Spec(필드 없음)은 하위 호환 — 새 항목 검증 면제.

```markdown
### Transformation Spec
spec-version: 3.8

| 항목 | 원본 분석 | After 요구사항 | 검증 |
|------|----------|--------------|------|
| 실행 스레드 | {원본 API의 스레드 특성} [verified: source] | {After 스레드 보장 방법} | Heavy |
| 에러 처리 | {원본 에러 분기 수 + 패턴} [verified: source] | {After 에러 보존 방법} | Light |
| 실행 보장 | {finally/ensure/defer 패턴} [verified: source] | {After 동등 패턴} | Light |
| 추상화 수준 | {원본 helper/struct/extension} | {After 추상화 — 줄 수 비교} | Skip |
| 인스턴스 관리 | {원본 static/인스턴스 패턴} | {After 인스턴스 전략} | Skip |
| 디코딩 경로 | {원본 응답 파싱 방법} [verified: source] | {After 디코딩 패턴} | Light |
| 요청 파라미터 | {원본 키 목록 + nil/omit 처리} [verified: source] | {After 키 동일 보존. nil → 키 제외} | Heavy |
```

> `[verified: source]` 태그가 없는 기술적 주장은 **자동 unverified** (Default-Deny).
> 참조: `modules/uncertainty-verification.md`

---

## Zero-Exception Thread Rule (기본값)

원본이 특정 스레드에서 실행되면 After도 동일 스레드.

| 원본 스레드 | After 기본값 |
|------------|------------|
| `.done { }` (main queue) | `Task { @MainActor in }` |
| `observe(on: MainScheduler)` | `@MainActor` |
| `DispatchQueue.main.async` | `@MainActor` |
| completion handler (main) | `@MainActor` |

예외 허용: `modules/uncertainty-verification.md`의 Heavy 검증 3단계 충족 시만.

> "thread-safe"는 예외 근거가 될 수 없다. mutation safety ≠ downstream observer 실행 스레드.

## 검증 체크리스트

### fz-plan (Spec 작성 시)

```
- [ ] 원본 API의 스레드 특성을 Context7 또는 코드로 확인했는가?
- [ ] 에러 분기가 원본과 1:1 매핑되는가?
- [ ] After 줄 수가 Before의 2배 이상이면 추상화를 제안했는가?
- [ ] 언어 런타임 제약을 확인했는가?
- [ ] ⛔ 각 기술적 주장에 [verified: source] 태그가 있는가? (Default-Deny)
- [ ] ⛔ 요청 파라미터 키 목록이 원본과 일치하는가? (omit ≠ default)
- [ ] ⛔ "실행 스레드" 항목이 Zero-Exception 규칙을 준수하는가?
```

### fz-code (구현 시 — Behavioral Equivalence Check)

```
Transformation Spec이 있는 Step 완료 후:
1. Spec 로드 (spec-version 확인)
2. 원본 코드 Read (git show 또는 Plan Before)
3. 대조:
   - Spec "실행 스레드" ↔ After @MainActor — Zero-Exception 기계적 확인
   - Spec "에러 처리" ↔ After catch 분기 수 + 패턴
   - Spec "추상화 수준" ↔ After 줄 수
   - ⛔ Spec "요청 파라미터" ↔ After 파라미터 키 — 추가/삭제 0건 확인
4. ⛔ [verified] 태그 확인 (fail-closed):
   - Spec의 기술적 주장 중 [verified] 없는 항목 → 구현 전 검증 강제
   - 검증 방법: uncertainty-verification.md의 Cost Tiers 참조
5. 불일치 → 마찰 보고 → 사용자 확인
```

### fz-review (diff 검증 시 — 검증 4-K)

```
1. Plan Transformation Spec 로드 (spec-version 확인)
2. diff 변환 ↔ Spec 대조:
   - 스레드: @MainActor 명시 → diff에 존재?
   - 에러: 분기 N개 → diff catch N개?
   - 추상화: extension 명시 → diff에 존재?
   - ⛔ 요청 파라미터: 원본 키 목록 → diff에 키 추가/삭제?
3. ⛔ Zero-Exception Thread: main queue 변환에 @MainActor 누락 → "thread_violation" (Critical)
4. ⛔ Parameter Presence: 원본 대비 키 추가 → "parameter_addition" (Major)
5. ⛔ Default-Deny: "기술적 주장인데 [verified] 태그 없음" → violation
6. 불일치 → "transformation_deviation" 이슈
```

---

## Swift 변환 규칙

> `swift-concurrency@swift-concurrency-agent-skill` 플러그인 연계

| 원본 패턴 | After 패턴 | 주의사항 |
|----------|-----------|---------|
| `.done { }` (PromiseKit) | `Task { @MainActor in }` | .done은 main queue. 일반 Task는 아님 |
| `.catch { switch case }` | `catch { if case ... }` | enum associated value: `==` 비교 금지, `if case` 필수 |
| `.ensure { }` / `.finally { }` | `try?` 후 순차 실행 | `defer { await }` 컴파일 에러 |
| `.cauterize()` | `try?` | fire-and-forget 동등 |
| `Promise { seal in }` | `async throws -> T` | Promise wrapping 완전 제거 |
| `observe(on: MainScheduler)` | `@MainActor` | RxSwift 스케줄러 → Actor |
| callback `completion:` | `async throws` | continuation bridge 불필요 시 native |

### Context7 활용

| 상황 | 조회 | 목적 |
|------|------|------|
| PromiseKit 변환 | `query-docs("PromiseKit done ensure thread")` | .done 스레드 확인 |
| RxSwift 변환 | `query-docs("RxSwift observe scheduler")` | 스케줄러 동작 확인 |
| Alamofire 제거 | `query-docs("Alamofire NetworkReachabilityManager")` | 동기/비동기 특성 |
| Network.framework | `query-docs("NWPathMonitor pathUpdateHandler")` | 비동기 콜백 타이밍 |

---

## 마찰 신호 (fz-code, fz-fix 공통)

| 마찰 신호 | 감지 기준 | 의미 |
|----------|----------|------|
| 스레드 컨텍스트 불일치 | Spec에 "@MainActor 필수" → 구현이 일반 Task | 원본 main queue 미보존 |
| 에러 경로 축소 | 원본 catch 분기 N개 → After < N개. `== .case` 사용 | enum case 합침. 동작 변경 |
| 퀄리티 역행 | After 줄 수 > Before 2배, 추상화 인라인 해체 | 리팩토링이 코드를 악화 |
| 파라미터 키 불일치 | 원본 API에 없던 키 추가 또는 있던 키 제거. nil → default value 전송도 "추가"에 해당 | omit ≠ explicit default — 서버 동작 변경 가능 |

---

## 설계 원칙

- Progressive Disclosure Level 3
- 트리거 기반: 패턴 변환 감지 시에만 활성. 단순 치환은 생략
- 3중 검증: Plan(Spec) → Code(BEC) → Review(4-J)
