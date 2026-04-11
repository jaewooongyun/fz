# Concurrency Safety Audit (검증 4-J)

> fz-review Phase 5에서 참조. diff에 동시성 키워드가 **없어도** 실행하는 역방향 안전성 감사.
> 트리거: `plugin-refs.md` "역방향 감지 트리거" Level 1 + Level 2 기반.

## 절차

1. diff에서 수정된 모든 타입 식별
2. 각 타입: `static let shared` / `static let instance` 패턴 확인 (싱글톤 여부)
3. **싱글톤이면 (Level 1 — 필수)**:
   a. 모든 stored `var` property에 동기화 보호 확인 (`@MainActor` / `actor` / `NSLock` / `os_unfair_lock` / `OSAllocatedUnfairLock` / `DispatchQueue` serial)
   b. 보호 없으면 → `find_referencing_symbols`로 읽기 사이트 추적 → 다른 스레드에서 읽는지 확인 → **"data_race_risk" (severity: Critical)**
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

## 체크리스트

- [ ] 싱글톤 타입의 모든 가변 상태에 동기화 보호 확인?
- [ ] 싱글톤 deinit 존재 시 dead code 확인?
- [ ] 콜백 쓰기 스레드와 소비자 읽기 스레드 일치?
- [ ] @Published 쓰기가 main thread에서 발생?
- [ ] 비동기 기본값의 소비자 영향 평가?
- [ ] API 내부 retention으로 인한 중복 멤버변수 확인?

## 참조

| 모듈 | 용도 |
|------|------|
| plugin-refs.md "역방향 감지 트리거" | L1/L2 트리거 테이블 |
| review-quality.md Library Semantics | 싱글톤 가변 상태, deinit, 비동기 기본값 판정 기준 |
| review-arch.md Library Semantics | 싱글톤 lifecycle, NWPathMonitor 콜백 스레드 |
