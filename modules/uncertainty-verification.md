# Uncertainty-Aware Verification

> 기술적 주장의 확실성을 평가하고, 불확실하면 검증 도구로 확인하는 하네스 원칙.
> 참조: guides/harness-engineering.md — Adapters, Guardrails, State Semantics
> 적용: v3.8 — Transformation Spec 경로에서만 (Pilot). 효과 확인 후 확장.

## Default-Deny 원칙

다음 영역의 기술적 주장에 `[verified: source]` 태그가 **없으면 자동 unverified**:

1. **Transformation Spec 기술적 주장** (v3.8 도입)
2. **Peer-review mapping/equivalence claim** (v4.4.0 도입 — 좁은 확장)
   - 적용 대상 문장 패턴: `"A는 B와 동일"`, `"X가 Y로 대체됨"`, `"기존 조건 보존"`, `"behavior equivalent"`
   - 태그 형식: `[verified: semantic-mapping.md M-XXX + source lines]`
   - 적용 범위: `${WORK_DIR}/evidence/semantic-mapping.md`의 mapping row + agent finding의 동등성 주장
   - 전역 확대 금지 — 본 좁은 영역에만 적용

fz-code BEC에서 [verified] 없는 주장은 구현 전 검증 강제 (fail-closed).
fz-review 4-K에서 "기술적 주장인데 근거 태그 없음" = violation.
fz-peer-review Gate 4.4-A에서 mapping claim의 [verified] 부재 = `mapping_status=unverified` (v4.4.0).

> "모르면 보수적으로. 알면 증거와 함께."
> LLM이 "확실하다"고 주장하는 것은 증거가 아님. 검증 도구의 출력만이 증거.

## Verification Cost Tiers

| 등급 | 적용 대상 | 검증 요구 |
|------|----------|----------|
| **Heavy** | 스레드 모델 변경, API 계약 변경 (omit vs default) | 3단계: Context7 + downstream 전수 + 플러그인 |
| **Light** | 일반 기술적 주장 (async 여부, Sendable 등) | 코드 확인 + 1개 신뢰 소스 |
| **Skip** | 코드에서 직접 확인 가능한 사실 | Read/Grep 결과만 |

Heavy 트리거: Transformation Spec의 "실행 스레드" 또는 "요청 파라미터" 항목.

## Swift/iOS Domain Tier (도메인 specific 강화)

> 발동: CLAUDE.md `## Architecture`가 Swift/iOS를 지정하는 프로젝트에서 Swift/iOS 관련 기술 주장 시. 일반 Heavy/Light/Skip Tier 위에 도메인 강제 layer 추가.
>
> ⛔ **Heavy Tier semantics 명확화 (F4 fix)**: 본 Domain Tier는 일반 Heavy Tier 정의를 **약화하지 않음(non-overriding)** + **추가 layer로 동작(additive)**. 일반 Heavy Tier(스레드 모델/API 계약)는 여전히 "3단계: Context7 + downstream 전수 + 플러그인" 모두 충족 의무. Swift/iOS Domain Tier는 그 위에 Mandatory Sources 인용을 추가 의무화한다 (택1이 아님).
>
> 일반 Heavy 트리거 충돌 시: 일반 Heavy(3단계 모두 충족) + Domain Tier(Mandatory Source 인용 의무) 둘 다 충족.

다음 7개 주장 유형은 도메인 specific Mandatory Sources를 의무화한다. `[verified: ...]` 태그가 명시 sources 중 하나라도 인용하지 않으면 Default-Deny 적용 (해당 주장은 unverified로 간주, 구현/리뷰 차단).

| Swift/iOS 주장 유형 | Required Tier | Mandatory Sources |
|---|:---:|---|
| **API 시그니처** (signature, parameters, return type) | Heavy | Context7 `query-docs` OR Read 실 코드 OR Apple 공식 문서 |
| **콜백 실행 스레드** ("이 콜백은 main에서 호출됨") | Heavy | Context7 `query-docs` OR `modules/plugin-refs.md` "역방향 트리거" 섹션 OR 빌드 + 런타임 측정 |
| **availability** ("이 API는 iOS 16에서 사용 가능") | Heavy | Apple 공식 문서 (`@available` 헤더 인용) OR Xcode 빌드 결과 |
| **`@MainActor` / actor isolation 동작** | Heavy | swift-concurrency 플러그인 OR Apple Concurrency 가이드 |
| **Sendable conformance 안전성** | Heavy | Swift 컴파일러 경고/에러 OR 컴파일러 진단 (strict concurrency check) |
| **SwiftUI re-render 동작** | Light | swiftui-expert 플러그인 OR Apple SwiftUI 가이드 |
| **RIBs 역할 위반** (Router/Interactor 책임) | Light | CLAUDE.md `## Architecture` OR `app-iOS/AI/ai-guidelines.md` |

**Heavy** = `[verified: Context7]` 또는 `[verified: 빌드]` 또는 `[verified: 코드 L{N}]` 태그 의무 (Mandatory Source 인용 포함).
**Light** = 1개 신뢰 소스 인용 (Mandatory Source 중 하나).
**태그 없음** = Default-Deny → 해당 주장 unverified, fz-code BEC에서 차단.

### 발동 예시

- "이 콜백은 main에서 호출됩니다" → Heavy. Context7 query-docs로 SDK 문서 확인 + plugin-refs.md 역방향 트리거 매칭 의무. 둘 다 부재면 `[미검증: 콜백 스레드 미확인]` 태그 후 default `@MainActor` 보호 적용.
- "@Observable은 iOS 17+ 필수" → Heavy (iOS 버전 가드 검증). Apple 공식 `@available(iOS 17.0, *)` 헤더 인용 의무.
- "RIBs Router는 navigation만" → Light. `app-iOS/AI/ai-guidelines.md` 또는 CLAUDE.md `## Architecture` 인용.

## Evidence Source Priority

| 우선순위 | 소스 | 태그 | 신뢰도 |
|:--------:|------|------|:------:|
| 1 | 실제 코드 (Read, Grep, Serena) | `[verified: 코드 L{N}]` | 최고 |
| 2 | 테스트/빌드 결과 (XcodeBuildMCP) | `[verified: 빌드]` | 높음 |
| 3 | 공식 문서 (Context7, 플러그인) | `[verified: Context7]` | 중간 |
| 4 | 훈련 데이터 | **태그 없음 = unverified** | 최저 |

> 우선순위 1-2는 직접 인정. 3은 문서 내용에 따라 판단. 4는 항상 unverified.

## Verification Protocol (Heavy)

예외를 주장하려면 3가지 모두 충족:

1. **Context7 조회**: `query-docs("{프레임워크} {API} observer thread")` — 공식 문서에서 스레드 보장 확인
2. **Downstream 전수 확인**: Grep → subscriber/observer 수집 → 모든 consumer thread-independent
3. **플러그인 참조**: `swift-concurrency` 또는 `swiftui-expert`에서 패턴 스레드 특성 확인

하나라도 미확인 → Zero-Exception 기본값 유지.

## Context7 활용 (확장)

| 상황 | 조회 | 목적 |
|------|------|------|
| (기존) 원본 API 확인 | `query-docs("PromiseKit done thread")` | 원본 동작 |
| ⛔ (신규) After API 예외 주장 | `query-docs("RxSwift BehaviorRelay accept observer thread")` | downstream 스레드 |
| ⛔ (신규) 파라미터 omit 의미 | `query-docs("{API} optional parameter omit behavior")` | omit vs default |

## Memory Feedback Loop

검증에서 [disproved] 발견 시:
1. topic file 기록 (memory-guide.md 태깅): `[skill: {X}] [domain: {Y}] [status: active] [priority: high]`
2. 다음 세션: memory-curator가 관련 키워드로 교훈 로드
3. 2건+ 관측: 해당 모듈/스킬에 규칙 승격 검토

## 설계 원칙

- Progressive Disclosure Level 3 (Transformation Spec 트리거 시에만 활성)
- Pilot-first: v3.8은 Transformation Spec 경로만. 효과 확인 후 확장
- Default-Deny > Self-tagging: LLM의 자기 인식에 의존하지 않음
