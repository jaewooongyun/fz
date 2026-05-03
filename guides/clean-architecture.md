# Clean Architecture Guide

> **Persona: Robert C. Martin (Uncle Bob)**
> "The architecture of a software system is the shape given to that system by those who build it. The purpose of that shape is to facilitate the development, deployment, operation, and maintenance of the software system contained within it."

이 가이드는 Robert C. Martin의 Clean Architecture 원칙을 코드 생성·리뷰·설계의 기조로 삼는다. 모든 아키텍처 결정에서 이 원칙을 먼저 확인한다.

---

## The Dependency Rule

> "Source code dependencies must point only inward, toward higher-level policies."

이것이 Clean Architecture의 **유일하고 절대적인 규칙**이다.

```
          ┌─────────────────────────────┐
          │       Entities              │  ← 가장 안쪽: 엔터프라이즈 비즈니스 규칙
          │  (Enterprise Business Rules)│
          ├─────────────────────────────┤
          │       Use Cases             │  ← 애플리케이션 비즈니스 규칙
          │  (Application Business Rules│
          ├─────────────────────────────┤
          │   Interface Adapters        │  ← 컨트롤러, 프레젠터, 게이트웨이
          │  (Controllers, Presenters,  │
          │   Gateways)                 │
          ├─────────────────────────────┤
          │   Frameworks & Drivers      │  ← 가장 바깥: DB, UI, Web, 디바이스
          │  (UI, DB, Web, Devices)     │
          └─────────────────────────────┘

          의존성 방향: 바깥 → 안쪽 (ONLY)
```

**안쪽 원은 바깥 원에 대해 아무것도 모른다.** 바깥 원의 이름(함수, 클래스, 변수 등)이 안쪽 원의 코드에 언급되어서는 안 된다.

---

## SOLID Principles

Uncle Bob이 명명한 5가지 설계 원칙. Clean Architecture의 기반이다.

### S — Single Responsibility Principle (SRP)

> "A module should have one, and only one, reason to change."

- 하나의 클래스는 **하나의 액터(actor)** 에게만 책임진다
- "한 가지 일을 한다"가 아니라 **"한 명의 이해관계자만 변경을 요구할 수 있다"**
- 위반 신호: 클래스가 서로 다른 팀/기능의 요구사항으로 동시에 변경될 때

### O — Open-Closed Principle (OCP)

> "Software entities should be open for extension, but closed for modification."

- 새 기능 추가 시 **기존 코드를 수정하지 않고** 확장할 수 있어야 한다
- 프로토콜(인터페이스)과 다형성으로 달성
- 위반 신호: 새 타입 추가마다 기존 switch/if-else에 case 추가

### L — Liskov Substitution Principle (LSP)

> "Objects of a supertype shall be replaceable with objects of its subtypes without altering the correctness of the program."

- 서브타입은 상위 타입의 **계약(contract)** 을 깨지 않아야 한다
- Swift에서: 프로토콜 conformance가 의미적으로도 올바른가
- 위반 신호: 서브클래스에서 상위 메서드를 `fatalError()`로 오버라이드

### I — Interface Segregation Principle (ISP)

> "Clients should not be forced to depend on interfaces they do not use."

- 큰 인터페이스보다 **작고 구체적인 인터페이스** 여러 개
- Swift에서: 프로토콜 분리 — `protocol Readable`, `protocol Writable` vs `protocol ReadWritable`
- 위반 신호: 프로토콜 conformance에서 대부분의 메서드가 빈 구현

### D — Dependency Inversion Principle (DIP)

> "High-level modules should not depend on low-level modules. Both should depend on abstractions."

- **이것이 Clean Architecture의 핵심 메커니즘이다**
- 상위 정책(UseCase)이 하위 세부사항(DB, Network)에 의존하지 않는다
- 프로토콜(추상화)에 의존하고, 구체 구현은 바깥에서 주입한다
- 위반 신호: UseCase가 URLSession, CoreData, Alamofire를 직접 import

---

## The Four Layers

### 1. Entities (Enterprise Business Rules)

가장 안쪽. 비즈니스의 핵심 규칙을 캡슐화한다.

- 앱이 아닌 **비즈니스** 의 규칙
- 가장 변경될 가능성이 낮다
- 외부의 어떤 것에도 의존하지 않는다
- 예: `Content`, `User`, `Subscription` 같은 도메인 모델 + 비즈니스 검증 규칙

```swift
// Entity — 외부 프레임워크 의존 ZERO
struct Content {
    let id: String
    let title: String
    let type: ContentType

    var isPlayable: Bool {
        // 비즈니스 규칙: 재생 가능 조건
        type != .upcoming && !isRegionBlocked
    }
}
```

### 2. Use Cases (Application Business Rules)

애플리케이션 고유의 비즈니스 규칙. Entity를 사용하여 시스템의 의도를 표현한다.

- **애플리케이션의 행동** 을 정의
- Entity에만 의존, 바깥 레이어에 대해 모른다
- 데이터가 어디서 오는지 모른다 (Repository 프로토콜만 안다)

```swift
// UseCase — Repository 프로토콜에 의존, 구체 구현 모름
protocol ContentRepository {
    func fetchContent(id: String) async throws -> Content
}

struct GetPlayableContentUseCase {
    private let repository: ContentRepository  // 추상화에 의존

    func execute(id: String) async throws -> Content {
        let content = try await repository.fetchContent(id: id)
        guard content.isPlayable else { throw ContentError.notPlayable }
        return content
    }
}
```

### 3. Interface Adapters (Controllers, Presenters, Gateways)

바깥 세계의 데이터 형식을 UseCase/Entity가 사용하는 형식으로 변환한다.

- **Presenter**: UseCase 출력 → View가 표시할 ViewModel로 변환
- **Controller/Interactor**: 사용자 입력 → UseCase 호출로 변환
- **Gateway/Repository 구현**: 외부 데이터 → Entity로 변환

```swift
// Repository 구현 — Interface Adapter 레이어
struct ContentRepositoryImpl: ContentRepository {
    private let network: NetworkService  // 바깥 레이어의 추상화

    func fetchContent(id: String) async throws -> Content {
        let dto = try await network.request(ContentDTO.self, endpoint: .content(id))
        return dto.toDomain()  // DTO → Entity 변환
    }
}
```

### 4. Frameworks & Drivers (UI, DB, External)

가장 바깥. 프레임워크와 도구로 구성된다.

- UIKit, SwiftUI, Alamofire, CoreData, UserDefaults
- **세부사항(detail)** 이다 — 정책(policy)이 아니다
- 가장 쉽게 교체 가능해야 한다
- "프레임워크는 도구이지, 아키텍처가 아니다"

---

## Crossing Boundaries

> "When we pass data across a boundary, it is always in the form that is most convenient for the inner circle."

레이어 경계를 넘을 때의 규칙:

### Dependency Inversion으로 경계 넘기

```
UseCase ──depends on──▶ Repository Protocol (안쪽에 정의)
                              ▲
                              │ implements
Repository Impl (바깥에 정의) ─┘
```

- 프로토콜은 **안쪽 레이어** 에 선언한다
- 구체 구현은 **바깥 레이어** 에 작성한다
- 의존성 주입(DI)으로 런타임에 연결한다

### Data Transfer Objects

- 바깥 레이어의 데이터 구조(DTO, JSON)를 안쪽으로 그대로 전달하지 않는다
- 경계에서 **안쪽 레이어가 편한 형태** 로 변환한다
- Entity가 JSON 파싱 로직을 알 필요 없다

---

## Architecture Smells (위반 신호)

Uncle Bob이 경고하는 아키텍처 악취:

### 1. The Database is a Detail

> "The database is a detail. It is not the architecture."

- Entity가 `@NSManaged`나 `RealmObject`를 상속하면 위반
- DB 스키마가 Entity 구조를 결정하면 위반
- DB는 교체 가능한 플러그인이어야 한다

### 2. The UI is a Detail

> "The UI is a detail. It is not the architecture."

- 비즈니스 규칙이 ViewController/View 안에 있으면 위반
- UI 프레임워크(UIKit→SwiftUI) 교체 시 비즈니스 로직이 영향받으면 위반
- View는 데이터를 **표시만** 한다

### 3. The Web/Network is a Detail

> "The web is a delivery mechanism. It is not the architecture."

- UseCase가 URLSession, Alamofire를 직접 참조하면 위반
- API 변경이 비즈니스 로직에 영향주면 위반
- 네트워크는 Repository 구현 뒤에 숨겨져야 한다

### 4. Frameworks are Details

> "Don't marry the framework."

- 프레임워크에 코드를 맞추지 말고, 프레임워크가 코드에 봉사하게 하라
- 프레임워크 의존을 가능한 한 바깥 레이어에 제한
- 프레임워크를 교체해도 비즈니스 로직은 살아남아야 한다

---

## The Screaming Architecture

> "Your architecture should scream the intent of the system, not the framework."

프로젝트 폴더 구조를 보면 **무엇을 하는 시스템인지** 알 수 있어야 한다.

```
BAD (프레임워크가 소리친다):
├── Controllers/
├── Models/
├── Views/
├── Services/
└── Helpers/

GOOD (의도가 소리친다):
├── ContentDetail/
├── Player/
├── Subscription/
├── Download/
└── Authentication/
```

---

## Testing Implications

> "If the architecture is clean, then the system is testable by design."

- UseCase는 **Mock Repository 주입** 만으로 테스트 가능
- Entity는 **의존성 없이** 단독 테스트 가능
- UI 테스트 없이도 비즈니스 규칙의 80%를 검증 가능
- "테스트하기 어렵다"는 아키텍처가 오염되었다는 신호

---

## Uncle Bob's Decision Rules

설계 결정 시 자문할 질문들:

1. **"이 코드를 다른 프레임워크로 옮기면 무엇이 깨지는가?"**
   → 깨지는 것이 비즈니스 로직이면 의존성 방향 위반

2. **"DB를 교체하면 UseCase가 변경되는가?"**
   → 변경된다면 DIP 위반

3. **"UI를 교체하면 비즈니스 규칙 테스트가 실패하는가?"**
   → 실패한다면 경계가 무너진 것

4. **"이 클래스가 변경되는 이유가 두 가지 이상인가?"**
   → SRP 위반

5. **"새 타입을 추가할 때 기존 코드를 수정해야 하는가?"**
   → OCP 위반

6. **"안쪽 레이어가 바깥 레이어의 이름을 알고 있는가?"**
   → Dependency Rule 위반

---

## Pragmatic Clean Architecture

> "Architecture is about intent, not about frameworks, tools, or specific patterns."

### 과도한 추상화 경계

모든 레이어에 엄격한 경계를 두면 **과잉 엔지니어링** 이 된다.
Uncle Bob 자신도 인정한다: "아키텍처는 상황에 맞게 적용해야 한다."

- 작은 기능에 4개 레이어 전부 필요하지 않을 수 있다
- 핵심은 **의존성 방향** — 레이어 수가 아니다
- Repository 패턴이 과하면 UseCase가 직접 프로토콜에 의존해도 된다
- 단, **안쪽이 바깥을 모르는 것** 은 절대 양보하지 않는다

### 언제 엄격해야 하는가

| 상황 | 엄격도 |
|------|--------|
| 비즈니스 핵심 도메인 | 최대 — 4레이어 완전 분리 |
| 자주 변경되는 기능 | 높음 — 경계 명확히 |
| 단순 CRUD | 중간 — 과잉 추상화 피함 |
| 프로토타입/실험 | 낮음 — 나중에 리팩토링 |

---

## 참조

- Robert C. Martin, *Clean Architecture* (2017)
- Robert C. Martin, *Clean Code* (2008)
- Robert C. Martin, *Agile Software Development: Principles, Patterns, and Practices* (2002)
- https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- OpenAI Codex CLI: https://developers.openai.com/codex/cli — fz cross-model verification 도구 (0.124.0, 2026-04-23)
