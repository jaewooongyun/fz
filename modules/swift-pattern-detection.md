# Swift Pattern Pre-detection (Code 단계)

> Code 구현 시작 전 plan을 스캔하여 Swift/iOS 안티패턴 trigger를 사전 감지하는 모듈.
> fz-code Phase 0.5에서 참조한다 (Level 3 — 필요 시 Read).

## 발동 조건

CLAUDE.md `## Architecture`가 Swift/iOS 프로젝트 + plan-final.md / plan-v*.md에 다음 trigger 중 하나 발견 시 활성:
- SwiftUI / Concurrency 키워드 신규 도입
- 위험 패턴 (싱글톤 가변 / 콜백 / @Published)
- 패턴 변환 (PromiseKit / defer-await / enum catch)

비Swift/iOS 프로젝트는 스킵.

## 행동 원칙 (원칙+이유 형태)

> 본 모듈은 9개 if-then trigger가 아닌 **4개 원칙**으로 구성된다.
> 각 원칙은 plan에서 검색할 token + 발동 시 행동을 제공한다.
> 출처: `guides/prompt-optimization.md` 원칙 4a + Phase 1.5 mirror 원칙.

---

### 원칙 D: SwiftUI 패턴 도입 감지 → swiftui-expert 플러그인 적극 참조

**이유**: SwiftUI 패턴 신규 도입 시 state ownership / View 책임 / 렌더링 영향 분석이 누락되면 Passive View 위반, 불필요한 재렌더링, deprecated API 사용 같은 안티패턴이 implementation에 박힌다.

**plan 검색 token**: `@State`, `@Observable`, `@StateObject`, `@ObservedObject`, `@Binding`, `@Bindable`, `body: some View`, `View 변경`, `SwiftUI/UIKit`, `UIKit/SwiftUI`

**발동 시 행동**:
- `modules/plugin-refs.md` "SwiftUI Expert" 섹션 적극 참조
- state ownership / iOS 16/17 분기 / Passive View 위반 사전 검증
- 변환 작업이면 UIViewRepresentable / UIHostingController 경계 검증

---

### 원칙 E: Concurrency 패턴 도입 감지 → swift-concurrency 플러그인 적극 참조

**이유**: 동시성 키워드 신규 도입은 isolation 설계 + cancellation + Sendable 경계의 동시 결정을 요구. 일부만 결정하면 컴파일러 경고 또는 런타임 data race.

**plan 검색 token**: `@MainActor`, `actor`, `Sendable`, `@Sendable`, `sending`, `async let`, `TaskGroup`, `AsyncStream`, `AsyncSequence`, `thread model`, `GCD.*Concurrency`, `DispatchQueue.*Actor`

**발동 시 행동**:
- `modules/plugin-refs.md` "Swift Concurrency" 섹션 적극 참조
- isolation scope 검증 (메서드 단위 vs 클래스 단위)
- cancellation / 결과 합성 / Sendable 경계 검증
- thread model 변경이면 원본 스레드 보장 추적 + Zero-Exception 적용

---

### 원칙 F: 위험 패턴 (역방향 — 키워드 부재해도 발동)

**이유**: 동시성 키워드가 plan에 명시 안 됐어도 위험 패턴(싱글톤 가변, 콜백, @Published)이 추가되면 data race / UI 스레드 위반 가능. v3.6 역방향 트리거의 implementation 단계 적용.

**plan 검색 token**: `static let shared`, completion handler 추가, delegate callback 추가, `ObservableObject`, `@Published var` (특히 `@MainActor` 부재)

**발동 시 행동**:
- 싱글톤 + 가변 stored property → 동기화(@MainActor / actor / lock / serial queue) step 의무
- 콜백 패턴 추가 → 콜백 실행 스레드 보호(`DispatchQueue.main` 또는 `@MainActor`) 의무
- `@Published` 추가 + 클래스 `@MainActor` 부재 → @MainActor 추가 step 의무

**Few-shot**:

```
BAD:
  Plan: NetworkMonitor 싱글톤에 currentNetworkStatus: NetworkStatus 추가
  Code 시작 → NetworkMonitor.shared.currentNetworkStatus = .connected (background thread)
  → data race. plan에서 동기화 step 누락.

GOOD:
  Plan: NetworkMonitor 싱글톤에 currentNetworkStatus 추가
    - Step N: NetworkMonitor.swift에 @MainActor 적용 (또는 actor 전환)
    - Step N+1: 모든 readers/writers를 main thread context로 이동 (역방향 트리거 발동)
  Code 시작 → @MainActor 보호된 currentNetworkStatus 안전 갱신
```

---

### 원칙 G: 패턴 변환 (Phase 1.5 P3와 mirror)

**이유**: Plan 단계에서 P3로 차단했어도 Code 단계에서 동일 패턴이 재발견될 수 있음. Phase 0.5는 Phase 1.5의 정합성 보장 layer.

**plan 검색 token**: `.done`, `.then(on: .main)`, `defer { ... await ... }`, `defer.*await`, enum catch에 `== .case(`, `withCheckedContinuation`

**발동 시 행동**:
- PromiseKit `.done` 변환 → `Task { @MainActor in }` 사용 검증 (일반 Task 반려)
- `defer { await ... }` 시도 발견 → 컴파일 에러 사전 차단 + 대안(try? + 순차 실행) 적용
- enum catch `==` 비교 → `if case let` 패턴 매칭으로 변경
- continuation 사용 → context7로 native async API 부재 확인 후 정당화

**Few-shot**:

```
BAD:
  Plan: PromiseKit firstly { ... }.done { updateUI() } → async/await 변환
  Code: Task { let data = try await fetch(); updateUI() }
  → 원본 main queue → After 일반 Task. main queue 보장 손실.

GOOD:
  Plan: PromiseKit firstly { ... }.done { updateUI() } → async/await 변환
  Code: Task { @MainActor in let data = try await fetch(); updateUI() }
  → 원본 main queue 보존
```

---

## Gate (fz-code Phase 0.5에서 사용)

본 trigger가 plan에 1건 이상 발견되면 plugin-refs.md 강제 참조 + 안티패턴 점검 후 구현 절차 진입.

- [ ] Swift/iOS 프로젝트? (아니면 skip)
- [ ] D/E/F/G token plan 스캔 완료?
- [ ] 발견된 trigger 모두 plugin-refs.md 매칭 + 대응 명시?
- [ ] F (위험 패턴) 발견 시 안전성 메커니즘이 step에 포함?
- [ ] G (패턴 변환) 발견 시 원본 동작 보존이 step에 명시?
- 미통과 시 → ⛔ 구현 절차 진입 차단

## 발동 결과 기록

- ASD 활성: `{WORK_DIR}/code/phase-0.5-detection.md`에 발견된 token + 대응 step 매핑
- 비ASD: `write_memory("fz:checkpoint:phase-0.5", "trigger: {tokens}. 대응: {steps}")`

## 검증 명령 (외부 grep용)

```bash
F=~/dev/fz-plugin/skills/fz-code/SKILL.md
# Phase 0.5 reference 존재
grep -q 'Phase 0\.5.*Swift Pattern Pre-detection' "$F"
grep -q 'modules/swift-pattern-detection\.md' "$F"
# Gate 0.5 존재
grep -q 'Gate 0\.5' "$F"
# 본 모듈에 4 원칙 (D/E/F/G) + Few-shot 존재
M=~/dev/fz-plugin/modules/swift-pattern-detection.md
test "$(grep -Ec '원칙 D|원칙 E|원칙 F|원칙 G' "$M")" -eq 4
grep -q 'BAD:' "$M" && grep -q 'GOOD:' "$M"
# Phase 1.5 P3와 mirror — 패턴 변환 trigger 명시 (F3 fix)
grep -qE 'PromiseKit|defer.*await|enum catch' "$M"
```

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 9 if-then trigger → 4 원칙+이유로 압축
- 원칙 G가 Phase 1.5 P3와 explicit mirror — Cross-skill consistency 보장 (F3 fix)
- BAD/GOOD Few-shot 의무 (원칙 F + G 각각 1쌍)
