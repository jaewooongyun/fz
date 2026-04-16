# Concurrency Safety Audit (검증 4-J)

> fz-review Phase 5에서 참조. diff에 동시성 키워드가 **없어도** 실행하는 역방향 안전성 감사.
> 트리거: `plugin-refs.md` "역방향 감지 트리거" Level 1 + Level 2 기반.

## 절차

1. diff에서 수정된 모든 타입 식별
2. 각 타입: `static let shared` / `static let instance` 패턴 확인 (싱글톤 여부)
3. **싱글톤이면 (Level 1 — 필수)**:
   a. 모든 stored `var` property에 동기화 보호 확인 (`@MainActor` / `actor` / `NSLock` / `os_unfair_lock` / `OSAllocatedUnfairLock` / `DispatchQueue` serial)
   b. 보호 없으면 → `find_referencing_symbols`로 읽기 사이트 추적 → 다른 스레드에서 읽는지 확인 → **"data_race_risk" (severity: Critical)**

   > ⛔ 판단 기준 (Inherent Safety 원칙 — `lead-reasoning.md` §1.5 참조):
   > "현재 호출부 N곳이라 안전" 금지. public 싱글톤 메서드 = 미래에 누구든 호출 가능 → 호출부 수와 무관하게 본질적으로 thread-safe한 구조 필수.

   > ⛔ 비대칭 동기화 검사: 싱글톤 타입 내에 lock으로 보호된 프로퍼티와 보호되지 않은 프로퍼티가 공존하면 → **"asymmetric_synchronization" (severity: Major)**. 일부 프로퍼티의 lock이 "전체가 thread-safe"라는 인상을 주어 나머지의 위험을 가림.

   c. `deinit` 존재 → **"singleton_deinit_dead_code" (severity: Minor)**
4. **콜백/클로저 패턴이면 (Level 2 — 권장)**:
   a. 콜백 내부 property 쓰기의 실행 스레드 분석
   b. `context7 query-docs`로 API 콜백 스레드 확인
   c. 쓰기 스레드 ≠ 주 소비자 읽기 스레드 → **"thread_mismatch" (severity: Major)**
5. **@Published property이면 (Level 2 — 권장)**:
   a. 쓰기 경로가 main thread인지 확인
   b. background 쓰기 → **"published_background_mutation" (severity: Major)**
6. **비동기 기본값이면 (Level 2 — 권장)**:
   a. 소비자 guard/if 패턴 샘플링 (`find_referencing_symbols` → 2~3개)
   b. 기본값으로 잘못된 분기 진입 가능 → **"default_value_impact" (severity: Major)**
7. **API 내부 retention (Level 2 — 권장)**:
   a. `context7 query-docs`로 API 파라미터 내부 retention 확인
   b. 중복 멤버변수 → **"redundant_state" (severity: Minor)**
8. **SDK 래퍼 전수 분석 (Level 2 — 권장)** (Conclusion Scope 원칙 — `lead-reasoning.md` §1.5 참조):
   a. 외부 SDK 객체를 `?.` optional chaining으로 호출하는 패턴 식별
   b. 한 메서드의 nil 동작만 분석하고 나머지를 건너뛰지 않았는지 확인 — 같은 객체의 **모든** `?.` 메서드 nil 동작 전수 분석
   c. 각 nil fallback이 **서버/대시보드에서도 유효한지** 분석 (클라이언트 안전 ≠ 서버 데이터 유효성)
   d. 위반 시 → **"sdk_partial_analysis" (severity: Major)**
9. **Task 내부 프로퍼티 쓰기 (Level 2 — 권장)** (Operation Classification 원칙 — `lead-reasoning.md` §1.5 참조):
   a. `Task { }` 또는 `Task.detached { }` 블록 내에서 `self.property = value` 패턴 식별 (싱글톤 여부 불문)
   b. 해당 프로퍼티의 소비자(읽기 사이트)가 Main thread인지 확인
   c. Main thread 소비자 존재 + `MainActor.run` 밖에서 쓰기 → **"task_property_write_race" (severity: Major)**
   d. 특히 "리뷰어 조언으로 MainActor 범위를 줄이는" 상황에서 발생 — 순수 연산만 밖으로, side effect는 안에 유지
10. **Check-then-act 비원자적 (Level 2 — 권장)**:
    a. lock 보호된 컬렉션/캐시에 대한 "읽기 → 없으면 생성 → 쓰기" 패턴에서, 읽기와 쓰기가 **별도 lock 구간**인지 확인
    b. 별도 구간이면 동시 2스레드가 둘 다 miss → 중복 생성 가능 → **"check_then_act_race" (severity: Minor)**
    c. 특히 flush/removeAll 직후 이전 결과가 재주입되는 시나리오 확인 — 캐시 무효화와 캐시 쓰기의 순서 경합
    d. 기능상 무해(같은 값 중복 쓰기)더라도 "사용자 전환 시 이전 사용자 데이터 재주입" 가능성 → severity 승격(Major)

## 체크리스트

- [ ] 싱글톤 타입의 모든 가변 상태에 동기화 보호 확인?
- [ ] 싱글톤 deinit 존재 시 dead code 확인?
- [ ] 콜백 쓰기 스레드와 소비자 읽기 스레드 일치?
- [ ] @Published 쓰기가 main thread에서 발생?
- [ ] 비동기 기본값의 소비자 영향 평가?
- [ ] API 내부 retention으로 인한 중복 멤버변수 확인?
- [ ] SDK 래퍼의 모든 `?.` 메서드 nil 동작을 전수 분석했는가? (서버 관점 포함)
- [ ] "현재 호출부 N곳이라 안전" 판단을 하지 않았는가?
- [ ] 싱글톤 내 lock 보호 프로퍼티와 비보호 프로퍼티가 공존하지 않는가? (비대칭 동기화)
- [ ] Task 내부에서 self.property 쓰기가 MainActor.run 밖에 있지 않은가? (소비자가 Main thread인 경우)
- [ ] 캐시/컬렉션의 check-then-act가 원자적인가? (특히 flush 직후 재주입 가능성)

## 참조

| 모듈 | 용도 |
|------|------|
| plugin-refs.md "역방향 감지 트리거" | L1/L2 트리거 테이블 |
| review-quality.md Library Semantics | 싱글톤 가변 상태, deinit, 비동기 기본값 판정 기준 |
| review-arch.md Library Semantics | 싱글톤 lifecycle, NWPathMonitor 콜백 스레드 |
