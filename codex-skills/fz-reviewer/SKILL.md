---
name: fz-reviewer
description: Code Review Skill
---

# fz-reviewer — Code Review Skill

## Role
Perform thorough code review based on project conventions and architecture rules.

## Context Collection (Required)
1. Find and read CLAUDE.md (`../CLAUDE.md` from GIT_ROOT, or `CLAUDE.md` in current dir).
2. `## Architecture` — identify architecture patterns and layer rules.
3. `## Guidelines` — find and read guideline files (paths relative to GIT_ROOT):
   - `AI/ai-guidelines.md` — coding rules and project conventions.
   - `AI/review-guidelines.md` — review standards and criteria.
4. `## Code Conventions` — identify coding rules and naming conventions.

## Review Criteria

### Architecture Compliance
- Verify layer dependency rules (no upward or cross-layer violations).
- Clean Architecture layers: Network → Repository → UseCase → Workflow (only downward references allowed).
- RIBs: Router=navigation, Interactor=business logic, Builder=DI. Verify each component stays in its role.
- Confirm new types placed in correct module; DI follows project pattern.

### Coding Convention Compliance
- Naming conventions: `{Feature}Router`, `{Feature}Interactor`, `{Feature}Builder`.
- File/folder structure, import ordering, access control rules.

### Memory Management
- Detect retain cycles: closures capturing `self` without `[weak self]`.
- `weak var`는 `if let`/`guard let` 대신 `?.` optional chaining으로 사용한다 (CLAUDE.md Code Conventions 참조).
- Verify proper cleanup in `deinit` or disposal.

### Concurrency Safety
- Verify thread-safe access to shared mutable state.
- Check async/await usage patterns and actor isolation.
- Detect potential data races and deadlocks.

### Error Handling
- Ensure errors are propagated, not silently swallowed.
- Verify user-facing error messages are appropriate.
- Check edge cases and boundary conditions.

### Implication Coverage (Removal/Refactoring)
- For removal/migration tasks: check if structural residuals remain (override init after DI removal, stored properties for deleted dependencies, conformance declarations for deleted protocols).
- Ask: "Why does this code exist? If the reason is eliminated by this change, the code should be too."
- Check if out-of-scope architectural issues (Clean Architecture violations, dead code) were observed but unreported.

### Build Warnings
- Flag any code that would produce compiler warnings.
- Detect unused variables, unreachable code, deprecated API usage.

## Output Format

Matches `codex_review_schema.json`. Key enum values:
- `severity`: `critical` | `major` | `minor` | `suggestion`
- `verdict`: `approved` | `needs_revision` | `rejected`
- `category`: one of `architecture`, `extensibility`, `over_engineering`, `decomposition`, `modern_api`, `dependency`, `performance`, `refactoring_completeness`, `concurrency_safety`, `requirements_alignment`, `logic_error`, `security`, `memory`, `thread_safety`, `style`, `documentation`, `testing`, `scope_creep`, `other`

```
### [Category] severity: critical|major|minor|suggestion
- File: path/to/file.swift:LINE
- Issue: description
- Suggestion: fix
```

## Few-shot Example

```
BAD (retain cycle + weak var convention violation):
// ProfileInteractor.swift:42
observable.subscribe(onNext: { [self] data in
    self.presenter.update(data)
})

// ProfileInteractor.swift:58
if let listener = listener {   // guard let on weak var
    listener.didFinish()
}

GOOD:
// ProfileInteractor.swift:42
observable.subscribe(onNext: { [weak self] data in
    self?.presenter.update(data)   // optional chaining
})

// ProfileInteractor.swift:58
listener?.didFinish()              // optional chaining directly

Review Output:
### [memory] severity: critical
- File: ProfileInteractor.swift:42
- Issue: Closure captures self strongly, causing retain cycle with Rx subscription
- Suggestion: Add [weak self] and use optional chaining

### [style] severity: minor
- File: ProfileInteractor.swift:58
- Issue: weak var uses guard let instead of optional chaining
- Suggestion: Replace with listener?.didFinish() per CLAUDE.md convention
```

## iOS Domain Knowledge (SwiftUI + RIBs + Concurrency)

> CLAUDE.md Plugins: iOS 16 최소 타겟. iOS 17+ API는 `#available` 필수.

### SwiftUI Checks
- `@State` must be `private`; `@StateObject` when view **owns**, `@ObservedObject` when injected
- iOS 16: `ObservableObject + @StateObject` | iOS 17+: `@Observable + @State` (`#available` required)
- `body` must be pure: no side effects, no network calls, no direct state mutation
- `ForEach` requires stable identity (`Identifiable` or explicit `id:`)
- `onChange` iOS 16 = `{ newValue in }` | iOS 17+ = `{ old, new in }` (`#available` required)

### RIBs Lifecycle Checks
- `didBecomeActive`: start Rx subscriptions, load initial data
- `willResignActive`: `disposeBag` must be disposed/reset; timers stopped
- `deinit`: confirm no active `Task` holding strong self
- Router `attach`/`detach` must be balanced (every attach has matching detach path)
- Interactor must NOT call `viewController.push/present` directly (Presenter bridge only)

### Swift Concurrency Checks
- `@MainActor`: apply only to UI-update code; avoid blanket `@MainActor` on whole class
- `Task { }` capturing `self`: must use `[weak self]` to avoid retain cycles
- 2+ independent async calls → prefer `async let` over sequential `await`
- `withCheckedContinuation`: only justified when no native async API exists
- `Task` stored in property: `deinit` must cancel it
- **`group.addTask` + `@MainActor` (Swift 5.10+)**: addTask signature is `sending @escaping @Sendable`.
  `@MainActor`-isolated closure as `sending` parameter → "passing closure as a 'sending' parameter" warning.
  ✅ Correct: `group.addTask { [weak self] in ... await MainActor.run { /* UI */ } }`
  ❌ Wrong suggestion: `group.addTask { @MainActor [weak self] in }` — causes warning, not removes it

### Code Transformation Equivalence (패턴 변환 검증)
diff에 PromiseKit→async/await, callback→async, RxSwift→Combine 등 패턴 변환이 포함될 때:
- PromiseKit `.done { }` = main queue → After는 `Task { @MainActor in }` 필수. 일반 Task는 오류
- `.catch { switch case }` → `catch { if case }`. enum associated value `==` 비교 금지
- `.ensure { }` / `.finally { }` → `try?` 후 순차 실행. **defer 내 await 컴파일 에러**
- `.cauterize()` → `try?` (fire-and-forget)
- After 줄 수 > Before 2배 → 추상화 부재 (protocol extension, convenience method 검토)
- Repository 인스턴스: stored property 1회 생성 (매 호출마다 Default*Repository() 금지)

## Context Scope (1M Context — diff is insufficient)

diff만 보는 것은 불충분하다. 다음 순서로 컨텍스트를 확장한다.

### 1. Feature Layer Traversal
변경 파일이 속한 Feature 전체 컴포넌트 읽기:
Router / Interactor / Builder / ViewController / Presenter — 같은 Feature 세트 전부.

### 2. Lifecycle Paths
- `didBecomeActive` / `willResignActive` / `deinit` 블록 확인
- SwiftUI: `.task {}` / `onAppear` / `onDisappear` modifier 확인
- Rx `subscribe` → `disposeBag` 연결 쌍 확인
- Router `attach` → `detach` 쌍 확인

### 3. Consumer Layer (상위)
변경된 프로토콜/타입을 사용하는 부모 Interactor, 부모 Router, listener 확인.
새 분기/타입/메서드가 소비자에 전파되는지 검토.

### 4. UI State Flow
SwiftUI: 상태 변경 → `body` 재평가 경로 추적 (불필요한 재렌더링 발견).
Presenter → ViewController → View 데이터 전달 흐름 확인.
화면 전환(push/pop/modal) 시 데이터 보존/초기화 동작.

### 5. Dependency Layer (하위)
변경 컴포넌트가 의존하는 UseCase / Repository / Service 확인.
레이어 의존 방향 위반 여부 (상향 참조 = violation).

### 6. Convention Consistency
같은 레이어 다른 Feature의 유사 구현과 패턴 일관성.
명명 규칙: `{Feature}Router/Interactor/Builder/ViewController`.
import 순서, access control 수준.

## Modularization Review Guide

모듈화/캡슐화 작업을 리뷰할 때는 패키지 내부뿐 아니라 **앱 측 소비자 코드**를 반드시 포함하여 리뷰한다.

### Consumer Code Checks
- `import {ModuleName}` 으로 앱 소스를 검색하여 소비자 파일 전수 수집
- 각 소비자가 public API만 사용하는지 확인 (internal 심볼 직접 접근 없는지)
- 앱 생명주기 진입점(AppDelegate, SceneDelegate, UIWindow extension)에서 모듈 연동이 올바른지
- 모듈화 이전의 레거시 패턴(직접 참조, 중복 로직, 인라인 구현)이 앱에 남아있지 않은지

### Entry Point Checks
- 글로벌 hook (motionBegan, userActivity 등)이 모듈과 올바르게 연동되는지
- 중복 modal 방지 등 앱 측 guard 로직이 존재하는지
- 모듈 API 호출 전 필요한 초기화가 수행되는지

### Few-shot Example (Modularization)
```
BAD (패키지만 리뷰):
Package TvingDebugTools: LGTM — 내부 구현 깔끔함.
→ 앱 측 shake handler에서 중복 modal 가능성 놓침.

GOOD (패키지 + 소비자):
Package TvingDebugTools: LGTM.
Consumer (Extensions.swift:343): UIWindow.motionBegan에 isShowing guard 필요.
  - Issue: TvingDebugMenuPresenter.makeController() 호출 시 이미 표시 중인 모달 체크 없음.
  - Suggestion: guard !TvingDebugMenuPresenter.isShowing 추가.
```

## When CLAUDE.md Is Absent
Apply general software engineering best practices: SOLID, clean code,
defensive programming, and language-specific idioms.
