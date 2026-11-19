# Plugin 참조 가이드

> 이 모듈은 프로젝트 언어/프레임워크에 따라 **해당 섹션만** 적용한다.
> CLAUDE.md `## Architecture` 또는 코드베이스에서 감지된 기준으로 판단.
> 플러그인은 글로벌 설치 (`~/.claude/plugins/`). 프로젝트에 해당 플러그인이 있을 때만 참조.

## 목차

- [활용 원칙](#활용-원칙)
- [알려진 짝](#알려진-짝)
- [스킬별 Swift 기준](#스킬별-swift-기준)
- [iOS/Swift (Swift, SwiftUI, RIBs 프로젝트)](#iosswift-swift-swiftui-ribs-프로젝트)
- [자동 감지 트리거](#자동-감지-트리거)
- [역방향 감지 트리거 (부재 패턴)](#역방향-감지-트리거-부재-패턴)
- [SwiftUI Expert](#swiftui-expert)
- [Swift Concurrency](#swift-concurrency)
- [참조 스킬](#참조-스킬)
- [GPT 스킬의 프레임워크 지식 — 조건부 도메인 팩](#gpt-스킬의-프레임워크-지식--조건부-도메인-팩)
- [설계 원칙](#설계-원칙)

---

## 활용 원칙

1. 플러그인 스킬은 Skill 도구로 불러야 읽힌다 — 스킬에서 플러그인 내용을 반복하지 않는다
2. 스킬은 "어떤 상황에서 플러그인 참조를 활용할지" 가이드만 제공한다
3. 프로젝트가 해당 언어/프레임워크를 사용하는지는 CLAUDE.md `## Architecture`에서 확인한다
4. 최소 타겟 제약 — CLAUDE.md `## Plugins` 참조. 최소 타겟 이상 API는 availability 가드 필수

## 알려진 짝

스킬의 `## 스택 스킬` 절은 상태 줄의 `스택 스킬` 에 적힌 스킬을 부른다. 아래는 이 저장소가 아는 짝이다 — 다른 스택의 짝은 그 개발자 환경의 스킬 설명으로 찾는다(표에 없어도 쓴다).

| 대상 코드 | 스킬(호출명) | 다루는 것 |
|---|---|---|
| Swift — SwiftUI 화면 · 상태 | `swiftui-expert:swiftui-expert-skill`(플러그인 `swiftui-expert`) | 상태 관리 · 뷰 구조 · 성능 · 최신 API — 아래 SwiftUI Expert |
| Swift — 동시성(async · actor · Sendable) | `swift-concurrency:swift-concurrency`(플러그인 `swift-concurrency`) | isolation · Sendable · Task · 마이그레이션 — 아래 Swift Concurrency |

## 스킬별 Swift 기준

Swift 파일을 다룰 때만 적용한다. 각 스킬의 `## 스택 스킬` 절은 이 모듈을 가리키는 한 줄만 둔다.

- **fz-plan** — Swift Concurrency(계획 시) 섹션. **iOS 16 minimum target 제약**: CLAUDE.md `## Plugins` 참조. 계획에 iOS 17+ API (`@Observable`, `@Bindable`, onChange new signature) 사용 명시 시 `#available` 가드 step 포함 의무. **availability 사전 결정**: SwiftUI State 설계 (iOS 16: `ObservableObject + @StateObject` / iOS 17+: `@Observable + @State`) → plan에 `#available` 분기 명시
- **fz-code · fz-fix** — SwiftUI Expert(구현 · 수정 시) + Swift Concurrency(구현 · 수정 시) 섹션. SwiftUI View 작업 시 `swiftui-expert` 플러그인 패턴 참조. **최소 타겟 제약**: CLAUDE.md `## Plugins` 참조. 최소 타겟 이상 API 사용 시 availability 가드 필수. 자동 감지: 코드에 SwiftUI/Concurrency 패턴 발견 시 플러그인 적극 참조(트리거 목록: 아래 자동 감지 트리거). **역방향 트리거**: 아래 역방향 감지 트리거 — `@MainActor`/`actor` 등이 없어도 싱글톤+가변상태 감지 시 안전성 분석 활성화(fz-fix 는 수정 전 3 패턴 점검을 스킬 본문의 역방향 트리거 절에 둔다)
- **fz-review** — SwiftUI Expert + Swift Concurrency (리뷰 시) 섹션. diff에 `@MainActor|actor|async|@Observable` 감지 시 해당 플러그인 참조. **역방향 트리거**: 동시성 키워드 없어도 `static let shared` + `var` 등 감지 시 Concurrency Safety 적용. **iOS 16 minimum target 검증**: diff에 iOS 17+ API (`@Observable`, `@Bindable`, onChange new signature) 사용 시 `#available` 가드 존재 여부 검증 의무
- **fz-discover** — SwiftUI Expert(상태 관리 결정 시) + Swift Concurrency(동시성 관련 제약 시)
- **fz-search** — SwiftUI Expert 섹션 (탐색 시 View 구조/패턴 판단 기준)

## iOS/Swift (Swift, SwiftUI, RIBs 프로젝트)

## 자동 감지 트리거

코드에 아래 패턴이 포함되면 해당 플러그인을 적극 참조한다.

| 패턴 | 플러그인 | 참조 항목 |
|------|---------|----------|
| `SwiftUI`, `View`, `@State`, `@Binding`, `@StateObject`, `@ObservedObject` | SwiftUI Expert | state-management, view-structure |
| `@Observable`, `@Bindable`, `@Environment` | SwiftUI Expert | state-management, latest-apis |
| `body: some View`, `.modifier`, `ViewModifier` | SwiftUI Expert | view-structure, performance-patterns |
| `Text("리터럴")`, `String(localized:)`, `LocalizedStringKey`, 로컬라이즈 문자열 변경 | SwiftUI Expert | localization, view-structure (⚠️ 오버로드: 리터럴=`LocalizedStringKey` 로컬라이즈 vs 변수:String=`StringProtocol` 미로컬라이즈) |
| `withAnimation`, `.animation(`, `.transition(`, `Animatable`, `animatableData` | SwiftUI Expert | animation-basics, animation-transitions, animation-advanced |
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
| 프레임워크 생명주기 콜백(RIBs `didBecomeActive`/`willResignActive` 등) 내 `@MainActor` 멤버 접근 또는 `MainActor.assumeIsolated` | 콜백 자체 nonisolated — 프레임워크가 호출 스레드 비보장 (RIBs activate()는 동기 직접 호출) | **bridge 선택을 결정으로 취급**: assumeIsolated(main 가정, 위반 시 crash=조기 탐지 덫) / `Task { @MainActor }`(무조건 보장, 생명주기 async화) / `Task.immediate`(iOS 26+ [verified], main이면 동기 실행) — trade-off 1회 제시 의무. 기존 Interactor 패턴 답습도 면제 아님 |

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
> **호출**: `/swiftui-expert:swiftui-expert-skill` — ⛔ 설치 식별자(`@마켓플레이스`)와 슬래시 호출명은 다르다. 부를 때는 이 이름이다.

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

### 계획 시 (fz-plan)

| 참조 항목 | 적용 시점 |
|----------|----------|
| state-management | 상태 소유자(owner) 결정 — 어느 View 가 source of truth 인가 |
| view-structure | 화면 분할 경계 설계 · 재사용 단위 판별 |
| latest-apis | 최소 타깃에서 쓸 수 있는 API 확정 (availability 가드 필요 여부) |

### 탐색 시 (fz-discover)

| 참조 항목 | 적용 시점 |
|----------|----------|
| state-management | 기존 화면의 상태 흐름 파악 — 제약으로 굳힐 것과 바꿀 수 있는 것 구분 |
| view-structure | 건드릴 View 의 책임 경계 — 어디까지가 이 화면의 것인가 |

### 교차 리뷰 시 (fz-peer-review)

| 참조 항목 | 체크 항목 |
|----------|----------|
| state-management | 상태 소유가 레이어를 넘지 않는가 (View 가 도메인 상태를 들고 있지 않은가) |
| performance-patterns | diff 가 만든 재렌더 경로 — body 안에서 계산이 늘지 않았는가 |

## Swift Concurrency

> Plugin: `swift-concurrency@swift-concurrency-agent-skill`
> **호출**: `/swift-concurrency:swift-concurrency` — ⛔ 마켓플레이스는 `swift-concurrency-agent-skill` 이지만 스킬 이름은 `swift-concurrency` 다.

### 구현 시 (fz-code)

| 참조 항목 | 적용 시점 |
|----------|----------|
| async-await-basics | async 함수 작성, async let 사용, **continuation bridge → native async 전환 판별** |
| actors | @MainActor, actor 정의, isolation 설계, **패턴 변환 시 래퍼 범위 최소성 판단** |
| tasks | Task 생성, TaskGroup 사용, cancellation 처리, **독립 비동기 호출 2+개 → async let 병렬화 검토** |
| sendable | Sendable conformance, 경계 넘기 |
| memory-management | Task 내 retain cycle 방지 |

### 계획 시 (fz-plan)

| 참조 항목 | 적용 시점 |
|----------|----------|
| actors | 새 actor 설계 시 isolation 전략 |
| migration | Swift 6 마이그레이션 작업 계획 시 |
| performance | 동시성 성능 요구사항 분석 |

### 리뷰 시 (fz-review)

| 참조 항목 | 체크 항목 |
|----------|----------|
| actors | isolation 이 선언과 실제 접근 경로에서 일치하는가 |
| sendable | 경계를 넘는 타입이 Sendable 을 실제로 만족하는가 (컴파일 경고가 아니라 의미로) |
| tasks | Task 취소 경로가 있는가 · 소유자가 사라질 때 누수하지 않는가 |
| memory-management | Task 클로저의 self 캡처 — retain cycle |

### 탐색 시 (fz-discover)

| 참조 항목 | 적용 시점 |
|----------|----------|
| actors | 건드릴 코드의 현재 isolation — 🔒 불변 제약으로 굳힐 대상 판별 |
| migration | 이 영역이 Swift 6 mode 인가 5 mode 인가 (제약의 강도가 달라진다) |

### 교차 리뷰 시 (fz-peer-review)

| 참조 항목 | 체크 항목 |
|----------|----------|
| actors | diff 가 isolation 경계를 옮겼는가 — 옮겼으면 소비자 전부가 그 경계를 아는가 |
| sendable | 새로 경계를 넘게 된 타입이 있는가 |

### 리뷰 시 (fz-review, review-quality)

- Structured concurrency 우선? (TaskGroup > 단독 Task)
- @MainActor가 진정 필요한 곳에만 적용?
- @MainActor 블록 범위가 최소인가? (불필요 문장 포함 여부) [ablation: scope-min-v1]
- Sendable 경계에서 안전한 데이터 전달?
- Task cancellation 적절히 처리?
- retain cycle 방지? (Task 내 self 캡처)

### 피어 리뷰 트리거 (fz-peer-review)

diff의 Swift 파일에 `@MainActor`, `actor`, `async`, `await`, `Task`, `Sendable`, `AsyncStream` 패턴 감지 시 활성화.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-code | SwiftUI View 구현, Concurrency 패턴 참조 |
| /fz-fix | SwiftUI/Concurrency 관련 버그 수정 |
| /fz-review | SwiftUI/Concurrency 코드 리뷰 |
| /fz-peer-review | SwiftUI/Concurrency 피어 리뷰 |
| /fz-search | Swift 심볼 탐색 |

## GPT 스킬의 프레임워크 지식 — 조건부 도메인 팩

> GPT 는 Claude 플러그인(swiftui-expert · swift-concurrency)에 접근하지 못한다. 그렇다고 스택 지식을 스킬 본문에 박으면 비-iOS 저장소나 지침이 없는 저장소에서도 그 규칙이 적용된다(AC-3). 그래서 본문과 스택 지식을 나눈다.

### 원칙
1. **본문은 프레임워크를 전제하지 않는다** — `gpt-skills/*/SKILL.md` 의 규칙은 대상 저장소 지침에서 런타임에 뽑는다(`## Project Rules (runtime)` 절 · 정본 `modules/project-rules.md`). 지침이 없으면 `## When Project Guidelines Are Absent` 절대로 일반 원칙만 쓰고 아키텍처 축을 Probe Coverage Gap 으로 보고한다
2. **스택 지식은 조건부 팩에 둔다** — `gpt-skills/<스킬>/references/domain-<스택>.md`. 본문의 로더 줄 한 줄이 조건(예: `*.swift` 소스 · `Package.swift` · `.xcodeproj`)이 맞을 때만 팩을 읽게 한다. 팩 안의 프레임워크 절(RIBs 등)은 그 프레임워크를 실제로 쓸 때만 적용된다
3. **팩에서만 나온 발견은 `ruleSource: plugin-default` · 상한 `suggestion` 이다** — 같은 내용을 프로젝트 지침이 말하면 그 규칙(`ruleSource: project`)과 규칙 기반 severity 로 낸다. 코드로 보일 수 있는 결함(누수 · 경합 · 크래시)은 상한 대상이 아니다 — 팩은 찾는 것을 돕기만 한다
4. **작성자 프로젝트의 관례는 팩에도 싣지 않는다** — 고정 레이어 순서 · 명명 템플릿 · 호출 관례는 그 저장소 지침이 말할 때 런타임 추출이 가져온다. 최소 배포 타겟도 고정값을 쓰지 않고 프로젝트 설정에서 읽는다
5. **검사** — `scripts/check_gpt_skill_portability.py`(health-check 배선): 본문 프레임워크 토큰(로더 줄 제외) · `AI/*guidelines` 경로 · 고정 레이어 순서 사슬 · 작성자 관례 표지 · 두 절 · 지침 파일 집합 · fz-reviewer 6축 · fz-architect Q1~Q8 · fz-planner JSON · `agents/openai.yaml` 정책. `--claude-docs` 모드(health-check 배선)는 Swift 기준 줄에 조건 문구 `CLAUDE.md 아키텍처 절이 Swift/iOS 프로젝트를 지정하는 경우` 를 실은 Claude 문서 8개(agents/ 다섯 · fz-code · code-auditor · arch-critic — 스크립트의 `CLAUDE_DOCS` 계약)를 본다: 조건이 덮지 않는 프레임워크 토큰 · 작성자 관례 표지(덮는 범위 = 문구를 실은 줄 · 문구를 실은 제목 줄이나 제목 바로 아래 첫 줄의 절) · `AI/*guidelines` 경로 · 레이어 사슬. 계약이 읽지 않는다고 적은 절만 건너뛰고 새 절은 읽는다. GPT 스킬 구조 규칙(두 절 이하)은 돌리지 않는다

### 팩 현황
팩이 있는 스킬은 architect · challenger · drift · fixer · guardian · planner · reviewer 일곱이다(`references/domain-ios.md`). fz-searcher 는 탐색 전용이라 팩이 없다.

### 암묵 호출 정책
`gpt-skills/*/agents/openai.yaml` 의 `policy.allow_implicit_invocation` 은 fz-reviewer 만 `true` 이고 나머지 7개는 `false` 다. 프롬프트가 없는 review 모드 호출(`gpt-exec.sh review`)에서 CLI 가 암묵으로 고를 수 있는 fz 스킬이 fz-reviewer 하나가 된다. 나머지 스킬은 래퍼(`--inject-skill`)가 본문을 프롬프트에 넣어서만 쓴다(`modules/cross-validation.md` 호출 계약).

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
