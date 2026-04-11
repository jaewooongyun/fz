# Uncertainty-Aware Verification

> 기술적 주장의 확실성을 평가하고, 불확실하면 검증 도구로 확인하는 하네스 원칙.
> 참조: guides/harness-engineering.md — Adapters, Guardrails, State Semantics
> 적용: v3.8 — Transformation Spec 경로에서만 (Pilot). 효과 확인 후 확장.

## Default-Deny 원칙

Transformation Spec의 기술적 주장에 `[verified: source]` 태그가 **없으면 자동 unverified**.
fz-code BEC에서 [verified] 없는 주장은 구현 전 검증 강제 (fail-closed).
fz-review 4-K에서 "기술적 주장인데 근거 태그 없음" = violation.

> "모르면 보수적으로. 알면 증거와 함께."
> LLM이 "확실하다"고 주장하는 것은 증거가 아님. 검증 도구의 출력만이 증거.

## Verification Cost Tiers

| 등급 | 적용 대상 | 검증 요구 |
|------|----------|----------|
| **Heavy** | 스레드 모델 변경, API 계약 변경 (omit vs default) | 3단계: Context7 + downstream 전수 + 플러그인 |
| **Light** | 일반 기술적 주장 (async 여부, Sendable 등) | 코드 확인 + 1개 신뢰 소스 |
| **Skip** | 코드에서 직접 확인 가능한 사실 | Read/Grep 결과만 |

Heavy 트리거: Transformation Spec의 "실행 스레드" 또는 "요청 파라미터" 항목.

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
