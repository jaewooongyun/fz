# Plugin 참조 가이드

> 이 모듈은 프로젝트 언어/프레임워크에 따라 **해당 섹션만** 적용한다.
> CLAUDE.md `## Architecture` 또는 코드베이스에서 감지된 기준으로 판단.
> 플러그인은 글로벌 설치 (`~/.claude/plugins/`). 프로젝트에 해당 플러그인이 있을 때만 참조.

## 활용 원칙

1. 플러그인은 Claude가 자동 로드 — 스킬에서 플러그인 내용을 반복하지 않는다
2. 스킬은 "어떤 상황에서 플러그인 참조를 활용할지" 가이드만 제공한다
3. 프로젝트가 해당 언어/프레임워크를 사용하는지는 CLAUDE.md `## Architecture`에서 확인한다
4. 최소 타겟 제약 — CLAUDE.md `## Plugins` 참조. 최소 타겟 이상 API는 availability 가드 필수

## iOS/Swift (Swift, SwiftUI, RIBs 프로젝트)

## 자동 감지 트리거

코드에 아래 패턴이 포함되면 해당 플러그인을 적극 참조한다.

| 패턴 | 플러그인 | 참조 항목 |
|------|---------|----------|
| `SwiftUI`, `View`, `@State`, `@Binding`, `@StateObject`, `@ObservedObject` | SwiftUI Expert | state-management, view-structure |
| `@Observable`, `@Bindable`, `@Environment` | SwiftUI Expert | state-management, latest-apis |
| `body: some View`, `.modifier`, `ViewModifier` | SwiftUI Expert | view-structure, performance-patterns |
| `async`, `await`, `Task {`, `Task.detached` | Swift Concurrency | async-await-basics, tasks |
| `@MainActor`, `actor `, `nonisolated` | Swift Concurrency | actors |
| `Sendable`, `@Sendable`, `sending` | Swift Concurrency | sendable |
| `AsyncStream`, `AsyncSequence`, `TaskGroup` | Swift Concurrency | tasks, performance |

## 역방향 감지 트리거 (부재 패턴)

코드에 아래 **존재 패턴**이 있으면서 **부재 패턴**에 해당하면, 해당 관점을 활성화한다.
Swift Concurrency/SwiftUI 플러그인 활성 여부와 **무관하게** 항상 동작한다.

### Level 1 (구문 — 항상 적용)

| 존재 패턴 | 부재 패턴 | 진단 |
|----------|----------|------|
| `static let shared` + `var` (가변 stored property) | `@MainActor` / `actor` / `NSLock` / `os_unfair_lock` / `OSAllocatedUnfairLock` / `DispatchQueue` 동기화 없음 | **싱글톤 가변 상태 동기화 누락**. 쓰기/읽기 스레드 분석 필요 |
| `static let shared` + `deinit` | — | **싱글톤 deinit dead code**. 프로세스 종료 시에만 호출 → 정리 로직 미실행 |

### Level 2 (의미론 — 검증 4-J에서 사용)

| 존재 패턴 | 부재 패턴 | 진단 |
|----------|----------|------|
| completion handler / `pathUpdateHandler` / delegate callback | callback 내부에 `DispatchQueue.main` / `@MainActor` 없음 | **콜백 실행 스레드 ≠ 소비자 스레드 가능성**. context7로 API 콜백 스레드 확인 |
| 비동기 API 초기화 + stored property 기본값 | — | **첫 콜백 전 기본값의 소비자 영향**. guard/if 분기에서 잘못된 분기 진입 가능 |
| `ObservableObject` + `@Published var` | `@MainActor` 없음 | **@Published background 쓰기 시 UI 스레드 위반**. 런타임 경고 발생 |

### iOS 16 기본 패턴 (최소 타겟 준수)

| API | iOS 16 기본 | iOS 17+ 대안 | 조건 |
|-----|-----------|-------------|------|
| State 관리 | `ObservableObject` + `@StateObject` | `@Observable` + `@State` | `#available(iOS 17, *)` |
| 바인딩 | `@Binding` + `@ObservedObject` | `@Bindable` | `#available(iOS 17, *)` |
| onChange | `.onChange(of:) { newValue in }` | `.onChange(of:) { old, new in }` | `#available(iOS 17, *)` |
| Animation | `withAnimation` | `withAnimation(.spring)` 간소화 | iOS 16 호환 |
| Navigation | `NavigationStack` | 동일 (iOS 16+) | — |

## SwiftUI Expert

> Plugin: `swiftui-expert@swiftui-expert-skill`

### 구현 시 (fz-code, fz-fix)

| 참조 항목 | 적용 시점 |
|----------|----------|
| state-management | 프로퍼티 래퍼 선택 (@State, @Observable 등) |
| view-structure | View 분리, 서브뷰 추출 기준 |
| performance-patterns | 렌더링 최적화, 불필요한 재평가 방지 |
| latest-apis | deprecated API 대신 최신 API 사용 |

### 리뷰 시 (fz-review, review-quality)

| 참조 항목 | 체크 항목 |
|----------|----------|
| state-management | @Observable vs ObservableObject 올바른 선택 |
| latest-apis | deprecated API 사용 여부 |
| view-structure | View body 복잡도, 서브뷰 추출 필요성 |
| performance-patterns | 불필요한 재렌더링, 과도한 state 변경 |

## Swift Concurrency

> Plugin: `swift-concurrency@swift-concurrency-agent-skill`

### 구현 시 (fz-code)

| 참조 항목 | 적용 시점 |
|----------|----------|
| async-await-basics | async 함수 작성, async let 사용, **continuation bridge → native async 전환 판별** |
| actors | @MainActor, actor 정의, isolation 설계 |
| tasks | Task 생성, TaskGroup 사용, cancellation 처리, **독립 비동기 호출 2+개 → async let 병렬화 검토** |
| sendable | Sendable conformance, 경계 넘기 |
| memory-management | Task 내 retain cycle 방지 |

### 계획 시 (fz-plan)

| 참조 항목 | 적용 시점 |
|----------|----------|
| actors | 새 actor 설계 시 isolation 전략 |
| migration | Swift 6 마이그레이션 작업 계획 시 |
| performance | 동시성 성능 요구사항 분석 |

### 리뷰 시 (fz-review, review-quality)

- Structured concurrency 우선? (TaskGroup > 단독 Task)
- @MainActor가 진정 필요한 곳에만 적용?
- Sendable 경계에서 안전한 데이터 전달?
- Task cancellation 적절히 처리?
- retain cycle 방지? (Task 내 self 캡처)

### 피어 리뷰 트리거 (fz-peer-review)

diff에 `@MainActor`, `actor`, `async`, `await`, `Task`, `Sendable`, `AsyncStream` 패턴 감지 시 활성화.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-code | SwiftUI View 구현, Concurrency 패턴 참조 |
| /fz-fix | SwiftUI/Concurrency 관련 버그 수정 |
| /fz-review | SwiftUI/Concurrency 코드 리뷰 |
| /fz-peer-review | SwiftUI/Concurrency 피어 리뷰 |
| /fz-search | Swift 심볼 탐색 |

## Codex 스킬용 iOS 지식 임베딩 원칙

> GPT Codex는 Claude 플러그인(swiftui-expert, swift-concurrency)에 직접 접근 불가.
> 대신, 핵심 iOS 지식을 각 Codex 스킬 SKILL.md에 직접 임베딩한다.

### 임베딩 원칙
1. **핵심 체크포인트만** — 상세 설명이 아닌 체크 항목 형식으로 작성
2. **iOS 16 최소 타겟 명시** — 모든 Codex 스킬에 `#available` 규칙 포함
3. **중복 최소화** — Codex 스킬에는 GPT가 즉시 판단 가능한 패턴만 기술
4. **업데이트 연동** — SwiftUI Expert/Concurrency 플러그인 버전업 시 Codex 스킬도 검토

### 현재 임베딩 현황

| Codex 스킬 | SwiftUI | Concurrency | RIBs Lifecycle |
|-----------|:-------:|:-----------:|:--------------:|
| fz-reviewer | ✅ | ✅ | ✅ |
| fz-architect | 부분 | 부분 | ✅ (Q1-Q5) |
| fz-drift | ✅ | ✅ | ✅ |
| fz-planner | ✅ | ✅ | ✅ |
| fz-guardian | — | ✅ | — |
| fz-challenger | — | 부분 | — |
| fz-fixer | — | 부분 | — |

> 부분: 주요 패턴만 포함. 추후 확장 필요 시 해당 스킬 SKILL.md에 섹션 추가.
> fz-challenger Concurrency(부분): sending parameter semantics 추가 (2026-03-09). SwiftUI/RIBs는 미추가.

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
