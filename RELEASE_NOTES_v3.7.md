# fz v3.7.0 Release Notes

> **Code Transformation Validation** — 코드 변환 동등성 검증 (세 번째 검증축)
> 2026-04-12

---

## 배경

PR-D1 플랜 작성 중 7개 코드 품질 이슈가 fz 생태계의 어떤 스킬/게이트에서도 잡히지 않음을 발견:
- `defer { await }` Swift 컴파일 에러 (문법)
- PromiseKit `.done` main queue → 일반 `Task` 변환 시 스레드 불일치 (동작)
- enum catch `==` 비교 → associated value 무시 (동작)
- AppPreferences 프로토콜 오염 (구조)
- 3줄 → 10줄 보일러플레이트 양산 (구조)
- Repository 매번 인스턴스 생성 (구조)
- CommonModel 디코딩 경로 미정의 (구조)

**근본 원인**: 기존 fz는 아키텍처(수직축) + 영향 범위(수평축)만 검증. **코드 변환 정확성**(변환축)이 빠져있음.

---

## 신규

### `modules/code-transform-validation.md` (112줄)

코드 변환(Before→After) 시 동작 동등성 + 구조 품질을 검증하는 공유 모듈.

핵심 개념:
- **Transformation Spec**: Plan에서 각 패턴 변환 Step에 작성하는 명세 (실행 스레드, 에러 처리, 실행 보장, 추상화 수준, 인스턴스 관리, 디코딩 경로)
- **Behavioral Equivalence Check (BEC)**: Code에서 Spec 대비 구현을 대조하는 절차
- **검증 4-K**: Review에서 Spec 대비 diff를 대조하는 게이트
- **Swift 변환 규칙 테이블**: PromiseKit, RxSwift, callback 패턴별 변환 규칙
- **Context7 활용 가이드**: 원본 API 동작 확인 조회 패턴

트리거 조건:
- 비동기 패턴 변환 (PromiseKit→async/await, Combine→async, callback→async)
- 네트워크 레이어 전환 (Alamofire→URLSession)
- UI 프레임워크 전환 (UIKit→SwiftUI, RxSwift→Combine)
- 스레드 모델 변경 (GCD→Swift Concurrency)

> 단순 이름 변경, 1:1 텍스트 치환에는 적용되지 않음.

---

## 변경

### 스킬 개선 (6개)

| 스킬 | 변경 | 줄 |
|------|------|:--:|
| `fz-plan` | Phase 1에 Transformation Spec 작성 절차 + Gate 1 체크리스트 | +10 |
| `fz-code` | friction-detect 마찰 신호 3개 (스레드 불일치, 에러 경로 축소, 퀄리티 역행) + BEC 절차(6.3) | +11 |
| `fz-review` | 검증 4-K (Transformation Equivalence) + Gate 4 체크리스트 | +15 |
| `fz-fix` | Step 2에 패턴 변환 감지 + 모듈 참조 | +5 |
| `fz-peer-review` | Gather 4.5 패턴 변환 감지 | +8 |
| `fz-codex` reviewer/architect | Code Transformation Equivalence 섹션 (Swift 변환 규칙 임베딩) | +17 |

### 모듈 개선 (1개)

| 모듈 | 변경 |
|------|------|
| `cross-validation.md` | 게이트 삽입 테이블에 transformation 3행 추가 |

---

## 3중 검증 파이프라인 (신규)

```
fz-plan                    fz-code                    fz-review
  │                          │                          │
  ├─ Transformation Spec     ├─ Spec 로드               ├─ Spec 로드
  │  (스레드/에러/추상화)      ├─ 원본 Read               ├─ diff ↔ Spec 대조
  │                          ├─ BEC 대조                │
  ├─ Context7 API 확인       ├─ 마찰 감지 3개            ├─ 검증 4-K
  │                          │                          │
  └─ Gate 1 ✅               └─ Gate 3 ✅               └─ Gate 4 ✅
```

---

## 검증: PR-D1 7개 이슈 잡히는가

| # | 이슈 | Plan | Code | Review |
|---|------|:---:|:---:|:---:|
| 1 | `defer { await }` | ✅ | ✅ | ✅ |
| 2 | MainActor 불일치 | ✅ | ✅ | ✅ |
| 3 | 에러 패턴 매칭 | ✅ | ✅ | ✅ |
| 4 | 프로토콜 오염 | ✅ | ⚠️ | ✅ |
| 5 | 보일러플레이트 | ✅ | ✅ | ✅ |
| 6 | Repository 매번 생성 | ✅ | ✅ | ✅ |
| 7 | CommonModel 미정의 | ✅ | ✅ | ✅ |

**7/7 모두 최소 2곳에서 잡힘.**

---

## 마이그레이션

추가 설정 불필요. 플러그인 업데이트 시 자동 적용.

기존 프로젝트:
- 패턴 변환이 포함된 Plan 작성 시 Transformation Spec이 자동 요구됨
- 단순 치환/이름 변경 작업에는 영향 없음
