# fz v3.6.0 Release Notes

**Release Date**: 2026-04-11
**Codename**: Reverse Diagnostic Triggers

---

## Summary

플러그인 트리거 시스템의 구조적 맹점을 해소합니다. 기존에는 코드에 `@MainActor`, `actor`, `async` 등의 동시성 키워드가 **존재할 때만** Swift Concurrency 플러그인이 활성화되었습니다. 이번 업데이트로 키워드가 **없어도** 싱글톤 + 가변 상태 등 위험 패턴이 감지되면 안전성 분석이 자동으로 활성화됩니다.

**배경**: PR #3665 (NetworkMonitor.swift) 코드 리뷰에서 팀원이 4가지 이슈(data race, 싱글톤 deinit dead code, 기본값 부팅 실패, 불필요한 멤버변수)를 발견했지만 fz 시스템은 하나도 선제 감지하지 못했습니다.

**근본 원인**: 트리거가 패턴 **존재**만 감지 → 보호가 필요하지만 없는 코드가 가장 적은 검토를 받는 구조적 맹점.

**해결**: 82행 추가 (7파일 수정 + 1파일 신규)로 역방향 트리거 + 안전성 감사 도입.

---

## New Features

### 1. Reverse Detection Triggers (`plugin-refs.md`)

기존 7개 존재 트리거에 더해 **부재 트리거** 섹션을 신설했습니다.

| Level | 트리거 | 감지하는 것 |
|-------|--------|-----------|
| L1 구문 | `static let shared` + `var` + 동기화 없음 | 싱글톤 가변 상태 동기화 누락 |
| L1 구문 | `static let shared` + `deinit` | 싱글톤 deinit dead code |
| L2 의미론 | 콜백 + main dispatch 없음 | 콜백 스레드 != 소비자 스레드 |
| L2 의미론 | 비동기 API + 기본값 | 첫 콜백 전 기본값 소비자 영향 |
| L2 의미론 | `@Published var` + `@MainActor` 없음 | background @Published 쓰기 |

이 트리거들은 **Swift Concurrency 플러그인 활성 여부와 무관하게 항상 동작**합니다.

### 2. Concurrency Safety Audit (`modules/safety-audit.md`)

fz-review Phase 5에 새로운 검증 단계 4-J를 추가했습니다. **모든 리뷰에서 실행**되며, diff에 싱글톤 타입이 포함되면 자동으로 7단계 안전성 검사를 수행합니다.

Progressive Disclosure Level 3 적용: 500줄 한도 대응으로 별도 모듈로 분리, 필요 시에만 Read.

### 3. Agent Semantics Enrichment

3개 에이전트의 Library Semantics에 iOS/Swift 도메인 지식을 추가했습니다.

- **review-quality**: 싱글톤 가변 상태, deinit, 비동기 기본값, API 내부 retention. Concurrency Safety 활성 조건에 "역방향 트리거" 추가
- **review-arch**: 싱글톤 스레드 접근성, NWPathMonitor 콜백 스레드, 싱글톤 lifecycle
- **impl-quality**: Memory Safety에 싱글톤 동기화 누락 감지

### 4. Implementation Friction Detection

fz-code의 마찰 감지 테이블에 3개 안전성 신호를 추가했습니다. 코드 **작성 중**에 위험 패턴을 감지합니다.

| 신호 | 감지 시점 |
|------|----------|
| 동기화 부재 | 싱글톤에 `var` 추가 시 보호 없음 |
| 싱글톤 deinit | `static let shared` + `deinit` 작성 시 |
| 기본값 소비자 영향 | 비동기 property에 기본값 설정 시 |

### 5. System Reminder T5

diff에 `static let shared` 타입의 `var` 변경이 감지되면 자동 리마인더를 주입합니다.

---

## Design Decisions

### Direction Challenge: RECONSIDER

원래 방향(5곳 동시 변경 + 200행 신규 모듈)에서 **"기존 에이전트 관점의 활성화 조건 수정"**으로 전환했습니다.

- **근거**: PR#3665의 4가지 실패 중 3가지는 기존 에이전트(review-quality, review-arch)가 이미 담당 관점을 보유. 문제는 "지식 부재"가 아니라 "트리거 부재"
- **효과**: 82행으로 원래 200+ 행 계획과 동일한 커버리지 달성

### 3-Level Detection Framework

감지 난이도별 3계층으로 분류하여 단계적 적용:

- **L1 구문** (Phase 1, 즉시): false positive 거의 없음
- **L2 의미론** (Phase 2, 검증 4-J): context 필요, 권장
- **L3 도메인** (Phase 3, 대기): API 지식 필요, 사례 축적 후

### Phase 3 대기

`swift-safety-patterns.md` (~200행) 모듈은 Phase 1+2 적용 후 유사 실패 **2건 이상** 추가 관측 시 실행 예정. "단일 사례로 규칙 만들지 않는다" 원칙 준수.

---

## Files Changed

| 파일 | 변경 |
|------|------|
| `modules/plugin-refs.md` | +20행 (역방향 트리거 섹션) |
| `modules/safety-audit.md` | +43행 (신규 — 검증 4-J) |
| `agents/review-quality.md` | +5행 (Library Semantics + Concurrency Safety 조건) |
| `agents/review-arch.md` | +3행 (State Lifecycle + Library Semantics) |
| `agents/impl-quality.md` | +1행 (Memory Safety) |
| `skills/fz-code/SKILL.md` | +4행 (역방향 참조 + Friction 3행) |
| `skills/fz-review/SKILL.md` | +5행 (모듈 참조 + 검증 4-J + Gate 4) |
| `modules/system-reminders.md` | +1행 (T5) |
| **합계** | **+82행 (7수정 + 1신규)** |

---

## Migration

이 버전은 **Breaking Change가 없습니다**. 기존 존재 트리거는 그대로 유지되며, 역방향 트리거는 추가 활성화 경로입니다.

- 기존 fz 사용자: `claude plugin update fz` 후 즉시 사용 가능
- CLAUDE.md 변경 불필요
- 에이전트/스킬 커스터마이징 없이 자동 적용

---

## Acknowledgments

이 업데이트는 PR #3665 코드 리뷰에서 minhyeok-tving이 발견한 이슈들을 기반으로 합니다. 팀원의 리뷰가 fz 시스템의 구조적 맹점을 드러냈고, 이를 체계적으로 해소하는 계기가 되었습니다.
