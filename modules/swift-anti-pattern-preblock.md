# Swift Anti-Pattern Pre-block (Plan 단계)

> Plan 단계에서 Swift/iOS 안티패턴을 사전 차단하는 inventory.
> fz-plan Phase 1.5에서 참조한다 (Level 3 — 필요 시 Read).

## 발동 조건

CLAUDE.md `## Architecture`가 Swift/iOS 프로젝트 + Plan에 다음 중 하나 포함 시 필수:
- SwiftUI/Concurrency 패턴 신규 도입
- 패턴 변환 (PromiseKit→async, callback→async, RxSwift→Combine 등)

비Swift/iOS 프로젝트는 스킵.

## 행동 원칙 (원칙+이유 형태)

> 본 모듈은 9개 if-then 체크리스트가 아닌 **3개 원칙**으로 구성된다.
> 각 원칙은 구체적 token (Claude/Codex가 검색해 사전 차단할 패턴)을 제공한다.
> 출처: `guides/prompt-optimization.md` 원칙 4a (원칙+이유 > if-then 테이블).

---

### 원칙 P1: SwiftUI 결정은 Plan에 명시

**이유**: Plan에 데이터 소유자/availability/View 책임이 명시되지 않으면 implementation 단계에서 추측 기반 판단으로 변환되어 안티패턴 도입 위험. iOS 16 minimum target 환경에서 iOS 17+ API는 #available 가드 부재 시 빌드 실패.

**Plan에 명시할 결정 (3 token)**:

- 데이터 소유자: 새 View가 ViewModel을 소유하는가(`@StateObject`) vs 외부 주입받는가(`@ObservedObject`). plan에 owner 항목 명시.
- availability 분기: iOS 17+ 전용 API (`@Observable`, `@Bindable`, onChange 신 시그니처) 사용 시 `#available(iOS 17, *)` 분기 step 의무. iOS 16 fallback도 plan에 명시.
- View 책임: View body에서 직접 repository/service 호출은 Passive View 위반. plan에 Interactor/UseCase 위임 step 추가 의무.

**Few-shot**:

```
BAD:
  Step 3: ContentDetailView 추가
  → 데이터 소유자 누구인가? @State로 충분한가? iOS 17+ API 쓰는가? 명시 부재.

GOOD:
  Step 3: ContentDetailView 추가
    - Owner: @StateObject ContentDetailViewModel (View가 ViewModel 소유)
    - State: ObservableObject (iOS 16) — iOS 17+ 미사용
    - View body: ContentDetailViewModel.fetchContent() 호출 (Interactor 위임)
```

---

### 원칙 P2: Concurrency isolation 범위는 최소화

**이유**: `@MainActor`를 클래스 전체에 적용하면 UI 무관 메서드까지 main thread에 묶여 성능 저하 + actor isolation의 본래 목적(UI 보호) 약화. 독립 비동기 호출의 sequential `await`는 성능 기회 손실. continuation은 native async API 부재 시에만 정당화.

**Plan에 명시할 결정 (3 token)**:

- isolation scope: `@MainActor`를 클래스 전체에 적용할 vs UI-update 메서드만 격리할지 plan에 결정 명시. 메서드 격리가 가능하면 메서드 단위 우선.
- 병렬화: 2+ 독립 `await` 발견 시 `async let` 변환 검토 결정 plan에 명시. cancellation/dynamic count 필요 시에만 TaskGroup.
- continuation 정당화: `withCheckedContinuation` 계획 시 — context7 query-docs로 native async API 부재 확인. 결과 plan에 인용 의무.

**Few-shot**:

```
BAD:
  Step 5: PlayerInteractor에 @MainActor 적용
  → 클래스 전체? 메서드 일부? 미명시. UI 무관 메서드까지 isolation 위험.

GOOD:
  Step 5: PlayerInteractor.didActivate() + .updateUI()에만 @MainActor 적용
    - 비-UI 메서드 (fetchVideo, calculateProgress)는 nonisolated 유지
    - 근거: UI-update 경로만 isolation, 비즈니스 로직은 별도 actor에서
```

---

### 원칙 P3: 패턴 변환은 원본 동작을 보존

**이유**: PromiseKit `.done`은 main queue 보장. 일반 Task로 변환하면 main queue 보장 손실 → UI 갱신 시 런타임 경고. Swift는 `defer` 안에 `await` 사용 불가 (컴파일 에러). enum catch에 `==` 비교는 associated value 무시.

**Plan에 명시할 결정 (3 token)**:

- 원본 스레드 보존: `.done` / `.then(on: .main)` 변환 시 After에 `Task { @MainActor in }` 명시 의무. 일반 `Task {}`는 Zero-Exception 위반. plan에 main queue 보존 명시.
- defer + await 조합 금지: plan에 `defer { await ... }`이 있으면 reject. 대안 (try? + 순차 실행) plan에 명시.
- enum catch 패턴 매칭: associated value 있는 enum은 `if case let` 사용. `==` 비교는 plan에서 reject.

**Few-shot**:

```
BAD:
  Step 4: networkClient.fetch().done { data in updateUI() }
       → Task { let data = try await networkClient.fetch(); updateUI() }
  → 원본 main queue → After 일반 Task. UI 업데이트가 background thread에서 발생.

GOOD:
  Step 4: networkClient.fetch().done { data in updateUI() }
       → Task { @MainActor in let data = try await networkClient.fetch(); updateUI() }
  → 원본 main queue 보존 (@MainActor 명시)
```

---

## Gate (fz-plan Phase 1.5에서 사용)

본 inventory를 plan이 모두 통과해야 Phase 2 진입 가능.

- [ ] P1 SwiftUI 결정 명시? (owner / availability / View 책임)
- [ ] P2 Concurrency isolation 범위 결정? (scope / 병렬화 / continuation 정당화)
- [ ] P3 패턴 변환 시 원본 동작 보존? (스레드 / defer-await / enum catch)
- 1건 미해결 → ⛔ Phase 2 차단

## 검증 명령 (외부 grep용)

```bash
F=~/dev/fz-plugin/skills/fz-plan/SKILL.md
# Phase 1.5 reference 존재
grep -q 'Phase 1\.5.*Swift Anti-Pattern Pre-block' "$F"
grep -q 'modules/swift-anti-pattern-preblock\.md' "$F"
# Gate 1.5 존재
grep -q 'Gate 1\.5' "$F"
# 본 모듈 자체에 3 원칙 + Few-shot 존재
M=~/dev/fz-plugin/modules/swift-anti-pattern-preblock.md
test "$(grep -Ec '원칙 P1|원칙 P2|원칙 P3' "$M")" -ge 3
grep -q 'BAD:' "$M" && grep -q 'GOOD:' "$M"
```

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 가이드 문서이므로 줄 수 제한 없음
- 9 if-then 항목 → 3 원칙+이유로 압축 (출처: prompt-optimization.md 원칙 4a)
- 각 원칙당 구체적 token (Claude/Codex가 검색해 차단할 패턴) 제공
- BAD/GOOD Few-shot 1쌍 의무 (출처: prompt-optimization.md 원칙 5)
