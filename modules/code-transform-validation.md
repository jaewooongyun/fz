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

## Transformation Spec

Plan의 각 패턴 변환 Step에 작성. fz-code/fz-review가 참조.

```markdown
### Transformation Spec

| 항목 | 원본 분석 | After 요구사항 |
|------|----------|--------------|
| 실행 스레드 | {원본 API의 스레드 특성} | {After 스레드 보장 방법} |
| 에러 처리 | {원본 에러 분기 수 + 패턴} | {After 에러 보존 방법} |
| 실행 보장 | {finally/ensure/defer 패턴} | {After 동등 패턴} |
| 추상화 수준 | {원본 helper/struct/extension} | {After 추상화 — 줄 수 비교} |
| 인스턴스 관리 | {원본 static/인스턴스 패턴} | {After 인스턴스 전략} |
| 디코딩 경로 | {원본 응답 파싱 방법} | {After 디코딩 패턴} |
```

---

## 검증 체크리스트

### fz-plan (Spec 작성 시)

```
- [ ] 원본 API의 스레드 특성을 Context7 또는 코드로 확인했는가?
- [ ] 에러 분기가 원본과 1:1 매핑되는가?
- [ ] After 줄 수가 Before의 2배 이상이면 추상화를 제안했는가?
- [ ] 언어 런타임 제약을 확인했는가?
```

### fz-code (구현 시 — Behavioral Equivalence Check)

```
Transformation Spec이 있는 Step 완료 후:
1. Spec 로드
2. 원본 코드 Read (git show 또는 Plan Before)
3. 대조:
   - Spec "실행 스레드" ↔ After Task/@MainActor
   - Spec "에러 처리" ↔ After catch 분기 수 + 패턴
   - Spec "추상화 수준" ↔ After 줄 수
4. 불일치 → 마찰 보고 → 사용자 확인
```

### fz-review (diff 검증 시 — 검증 4-K)

```
1. Plan Transformation Spec 로드
2. diff 변환 ↔ Spec 대조:
   - 스레드: @MainActor 명시 → diff에 존재?
   - 에러: 분기 N개 → diff catch N개?
   - 추상화: extension 명시 → diff에 존재?
3. 불일치 → "transformation_deviation" 이슈
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

---

## 설계 원칙

- Progressive Disclosure Level 3
- 트리거 기반: 패턴 변환 감지 시에만 활성. 단순 치환은 생략
- 3중 검증: Plan(Spec) → Code(BEC) → Review(4-J)
