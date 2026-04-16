---
name: fz-code
description: >-
  코드 구현 + 빌드 검증. 계획 기반 점진적 구현과 매 Step 빌드 검증.
  예: 구현해줘, 코드 짜줘, 만들어줘, 개발해줘, 빌드해줘
user-invocable: true
argument-hint: "[구현 대상 설명]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__replace_symbol_body,
  mcp__serena__insert_after_symbol,
  mcp__serena__insert_before_symbol,
  mcp__serena__rename_symbol,
  mcp__serena__find_file,
  mcp__serena__write_memory,
  mcp__serena__read_memory,
  mcp__serena__edit_memory,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  mcp__lsp__diagnostics_delta,
  mcp__lsp__hover,
  Edit, Write, Read, Bash(xcodebuild *), Bash(cd *)
team-agents:
  primary: impl-correctness
  supporting: [review-arch, impl-quality, review-correctness, memory-curator]
composable: true
provides: [code-changes]
needs: [planning]
intent-triggers:
  - "구현|코드|만들어|개발"
  - "implement|code|develop|build"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-code - 구현 + 빌드 검증 스킬

> **행동 원칙**: 검증된 계획을 기반으로 점진적으로 코드를 구현하고, 매 Step마다 빌드 검증을 수행한다. 빌드 성공을 확인한 후 다음 Step으로 진행한다.

## 개요

> ⛔ Phase 0 (ASD Pre-flight) → Step N 구현 → 빌드 검증 → (실패: 에러 수정 → 재빌드) → Gate 3 → /fz-review
> 루프 프리미티브: Generate-Test-Repair + Plan-Execute (H6, Inside the Scaffold)

- 점진적 구현 + 매 Step 빌드 검증
- 프로젝트 빌드 검증
- 리뷰 검증은 `/fz-review`로 위임 가능

## 사용 시점

```bash
/fz-code "검증된 계획대로 구현해줘"
/fz-code "Step 1만 먼저 구현해줘"
/fz-code "빌드 에러 수정해줘"
/fz-code "Gate 3 통과 확인해줘"
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/build.md | 빌드 검증 |
| modules/execution-modes.md | LOOP + SIMPLIFY 실행 모드 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/context-artifacts.md | ASD 폴더 기반 compact recovery + 산출물 전달 |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |
| modules/rtm.md | RTM 상태 갱신 — Step 완료 시 Req-ID를 implemented로 |
| modules/native-agents.md | L3 네이티브 에이전트 통합 정책 (review에서 참조) |
| modules/code-transform-validation.md | 코드 변환 동등성 — BEC 절차 + 마찰 신호 (패턴 변환 시) |
| modules/uncertainty-verification.md | BEC fail-closed — [verified] 없는 주장 구현 전 검증 강제 |
| modules/lead-reasoning.md | Implication Scan — 제거/리팩토링 시 의미론적 완결성 |
| modules/system-reminders.md | Instruction fade-out 대응 — 트리거 기반 리마인더 |

## Plugin 참조 (SwiftUI + Swift Concurrency)

> 참조: `modules/plugin-refs.md` — SwiftUI Expert(구현 시) + Swift Concurrency(구현 시) 섹션
> SwiftUI View 작업 시 `swiftui-expert` 플러그인 패턴 참조
> **최소 타겟 제약**: CLAUDE.md `## Plugins` 참조. 최소 타겟 이상 API 사용 시 availability 가드 필수
> 자동 감지: 코드에 SwiftUI/Concurrency 패턴 발견 시 플러그인 적극 참조 (트리거 목록: `modules/plugin-refs.md`)
> **역방향 트리거**: `modules/plugin-refs.md` "역방향 감지 트리거" 참조. `@MainActor`/`actor` 등이 없어도 싱글톤+가변상태 감지 시 안전성 분석 활성화

## sc: 활용 (SuperClaude 연계)

| 조건 | sc: 명령어 | 자동/수동 |
|------|-----------|----------|
| 빌드 **2회 연속** 실패 | `/sc:troubleshoot --fix` | **자동** |
| 5+ 파일 변경한 Step | `/sc:analyze --focus quality` | **자동 제안** |
| SOLO + 3+ 파일 변경 | `/sc:reflect --type correctness` | **자동** |
| 3+ Step 구현 중간점 | `/sc:reflect --type task` | **필수** |
| 복잡한 다중 파일 구현 | `/sc:implement` | 수동 |
| API 불확실 | Context7 + `/sc:explain` | 수동 |

## 팀 에이전트 모드

> 팀 모드 규칙은 `modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("code-{feature}")
├── Lead (Opus): 오케스트레이션 + 빌드 검증
├── impl-correctness (★Opus): 점진적 구현 (Primary Worker)
├── review-arch (Sonnet): 구현 중 아키텍처 감시
├── impl-quality (Sonnet): 코딩 표준 + 패턴 일관성 실시간 피드백 [supporting]
├── review-correctness (Sonnet): 기능 정확성 + 요구사항 충족 검증 [supporting]
├── memory-curator (Sonnet): 관련 교훈 발굴 + impl-correctness에 직접 전달 [기본 포함, lightweight recall]
└── Cross-model 검증 (Lead가 검증 실행)
```

> impl-quality는 각 Step 완료 시 impl-correctness에게 패턴 일관성 피드백. Lead에게 보고하지 않고 impl-correctness와 직접 통신.

> ASD 폴더 활성 시: `{WORK_DIR}/code/code-team.md`에 pair programming 핵심 통신을 기록한다.

### 통신 패턴: Pair Programming (Peer-to-Peer)

impl-correctness와 review-arch가 **직접 대화하며** 코드를 만드는 패턴.
Lead를 거치지 않고 직접 SendMessage로 소통한다.

```
구현 중:
  impl-correctness → SendMessage(review-arch): "UseCase에서 두 Repo 조합, Workflow로 빼야 할까요?"
  review-arch → SendMessage(impl-correctness): "네, Workflow가 맞습니다. 기존 패턴: {참고}"
  impl-correctness → 구현 → SendMessage(review-arch): "Workflow 완료. 검토해주세요"
  review-arch → SendMessage(impl-correctness): "LGTM"
  양쪽 → SendMessage(team-lead): "Step N 완료"
  Lead: 빌드 검증 → 다음 Step
```

**핵심**: 구현 **중간에** 아키텍처 질문을 바로 해결. 다 만들고 뒤집기가 아니라 만들면서 확인.

> impl-correctness 에이전트가 이 스킬의 워크플로우를 활용합니다.

---

## ⛔ Phase 0: ASD Pre-flight

> 참조: `modules/context-artifacts.md` → "Work Dir Resolution" 섹션

**Phase 1 시작 전에 반드시 실행:**

1. 인자에서 `ASD-\d+` 패턴 추출
2. 패턴 있으면 → `{CWD}/ASD-xxxx/` 폴더 + index.md 생성 (없으면) + WORK_DIR 설정
3. 패턴 없으면 → 브랜치명 확인 → 없으면 AskUserQuestion(저장 여부) → 예: `{CWD}/NOTASK-{YYYYMMDD}/` + index.md 생성 / 아니오: Serena fallback

### Gate 0: Work Dir Ready
- [ ] ⛔ ASD 패턴 또는 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD / NOTASK / Serena fallback)
- [ ] index.md 존재 확인 완료? (없으면 생성)

---

> **임의 판단 금지**: 구현 중 "이게 맞겠지"라는 추측이 필요한 상황에서는 코드를 작성하지 않고 AskUserQuestion으로 사용자에게 확인한다.
> 이유: 추측 기반 판단은 리뷰에서도 잡히지 않는 미묘한 동작 변경을 만든다.

## 구현 도구 선택 기준

| 상황 | 도구 | 비고 |
|------|------|------|
| 기존 함수/메서드 수정 | `mcp__serena__replace_symbol_body` | 심볼 단위 정밀 수정 |
| 새 메서드/프로퍼티 추가 | `mcp__serena__insert_after_symbol` | 기존 심볼 뒤에 삽입 |
| 파일 시작에 코드 추가 | `mcp__serena__insert_before_symbol` | import 등 |
| 심볼 이름 변경 | `mcp__serena__rename_symbol` | 참조 자동 업데이트 |
| 새 파일 생성 | `Write` + `/fz-new-file` | 헤더 규칙 준수 |
| 복잡한 다중 파일 | `/sc:implement` | SuperClaude 위임 |
| 단순 텍스트 수정 | `Edit` | 간단한 인라인 수정 |

---

## 구현 절차

> **프로젝트 규칙**: CLAUDE.md `## Architecture` 섹션을 따른다.

1. **세션 감지**: 참조 `modules/session.md`

1.5. **ASD 컨텍스트 로딩** (ASD 폴더 활성 시):
   - `{WORK_DIR}/plan/plan-final.md` 읽기 → 승인된 계획 복원
   - `{WORK_DIR}/plan/direction-challenge.md` 읽기 → 방향 판정 + 대안 비교 (있으면)
   - `{WORK_DIR}/discover/discover-journal.md` 읽기 → 제약 조건 복원 (있으면)
   - `{WORK_DIR}/discover/discover-code.md` 읽기 → mid-pipeline discover 결과 (있으면)
   - `{WORK_DIR}/code/progress.md` 읽기 → 진행 상태 복원 (있으면)
   - 최신 `{WORK_DIR}/code/step-N.md` 읽기 → 마지막 구현 상세 (있으면)

1.6. **⛔ Scope Expansion 확인** (discover 결과 + plan-final.md 모두 존재 시):
   - plan-final.md의 영향 범위 파일 목록 vs discover journal의 언급 범위 비교
   - plan 영향 범위가 discover 범위보다 **좁으면** → ⚠️ 마찰 신호 "시야 축소 위험" 보고
   - plan이 discover보다 넓거나 같으면 → OK (Scope Expansion 작동 확인)

2. **계획의 각 Step을 순서대로 구현**
   - 각 Step 완료 시 확인 (다음 Step 전제조건):
     - □ 빌드 성공 (modules/build.md)
     - □ 시그니처 변경 시: conformance 보존 확인 (`find_referencing_symbols`)
     - □ 타입 변경 시: caller 1개 샘플 확인 (의도대로 호출되는지)
   - /simplify 자동 트리거: 새 함수 3개+ 또는 100줄+ 추가 시 (modules/execution-modes.md)
   - ⛔ RTM 갱신: 해당 Step의 Req-ID를 `implemented`로 갱신 (참조: modules/rtm.md)

3. **구현 마찰 감지** (Implementation Friction Detection):
   각 Step 구현 중 아래 신호 감지 시 멈추고 사용자에게 보고:

   | 마찰 신호 | 감지 기준 | 의미 |
   |----------|----------|------|
   | 분기 폭증 | 같은 대상에 대한 switch/if/enum case 3개+ | 추상화가 변형을 통합하지 못함 |
   | 코드 반복 | 유사 구조의 코드를 복사-수정 3회+ | 공통 추상화 필요 |
   | 소비자 판별 로직 | ViewModel/Listener에 "어떤 X인지" 판별 코드 발생 | 하위 복잡도가 상위로 전이됨 |
   | workaround | 계획에 없던 우회 코드 작성 | 설계와 현실의 불일치 |
   | 잔존 패턴 | Plan의 Anti-Pattern Constraints에 명시된 금지 패턴이 기존 코드에 여전히 존재 | 리팩토링 미완성 — 해당 패턴 제거/대체 필요 |
   | 불필요한 영속화 | UserDefaults/Keychain/CoreData에 저장하는 코드 작성 시, 해당 상태가 컴포넌트 라이프사이클(RIBs Interactor 생존 기간)로 충분한데 영속 저장소에 중복 저장 | 앱 재시작 후에도 유지해야 하는지 먼저 확인. A/B 테스트 배정값 등 외부 시스템 관리 값은 로컬 캐싱 금지 |
   | 파라미터 미전달 | 래퍼 함수 시그니처에 파라미터가 있지만, 내부 SDK/라이브러리 호출에 해당 파라미터를 전달하지 않음 | 파라미터가 무시되어 기능이 무효화됨 — SDK API의 해당 오버로드 존재 여부 확인 필수 |
   | 검증 유보 | TODO/FIXME로 "나중에 전환", "추후 적용" 등 검증 없이 현재 구현을 정당화하는 주석 작성 | 이미 가능한 작업을 지연시킴 — 주석 작성 전에 실제로 불가능한지 SDK/API 확인 필수 |
   | 주석-추상화 불일치 | 범용 유틸/래퍼 클래스에 특정 기능 맥락의 주석 작성 (예: 범용 A/B 테스트 래퍼에 "카드형 Default" 주석) | 주석의 추상화 수준이 코드의 추상화 수준과 일치해야 함 — 범용 코드엔 범용 주석 |
   | 프로토콜 시그니처 불일치 | 메서드 시그니처 변경(파라미터 추가/제거/타입 변경) 시, `find_referencing_symbols`로 해당 메서드가 프로토콜 요구사항인지 자동 확인. 프로토콜 요구사항이면 선언부도 함께 변경되는지 검증. Swift 디폴트 파라미터(`= value`)는 프로토콜 적합성을 만족시키지 않음 — 별도 오버로드 필요 | RIBs에서 ViewController가 PresentableListener를 선언하고 Interactor가 구현하므로 파일이 분리됨. 시그니처만 변경하면 clean build에서 실패 |
   | 모듈 경계 위반 | 모듈에 추가하는 타입이 도메인 특화 필드(비즈니스명), 하드코딩 UI 문자열, 또는 모듈 미사용 pass-through를 포함 | 도메인 로직이 인프라 모듈에 침투 — Plan의 Concern Classification과 대조. "이 타입이 여기 맞나?" 질문 |
   | Import Orphan | import 제거 후 해당 모듈의 타입/typealias가 코드에 잔존 (빌드 시 "cannot find type" 에러 예정) | 치환 패턴 테이블 누락 — Plan의 Symbol Inventory와 대조하여 해당 심볼의 대체 방법 확인 |
   | 원본 미존재 추가 | 리팩토링/마이그레이션에서 원본에 없던 파라미터, 로직, 타입을 추가하려 할 때. optional 파라미터에 기본값(nil)이 있는데 명시적으로 채우는 행위 포함 | 원본 동작 변경 위험 — AskUserQuestion 필수 |
   | 원본 버그 발견 | 모듈화/리팩토링 중 원본 코드의 버그를 발견 (dead code, 도달 불가 분기, 잘못된 순서 등) | "원본과 동일"로 방치 금지 — AskUserQuestion으로 수정 여부 확인. 혼자 판단하여 dismiss 금지 |
   | 파라미터 키 불일치 | 원본 API에 없던 키 추가 또는 삭제. nil → default value 전송 포함 | omit ≠ explicit default — 서버 동작 변경 가능. AskUserQuestion: "이 키 추가가 의도적인가?" |
   | 구조적 잔존물 | 제거/DI 변경에서, 제거 대상이 존재하기 위해 추가된 구조(override init, stored property, convenience init, DI용 protocol)가 잔존 | [Q-WHY] "이 구조가 추가된 이유가 해소됐는가?" find_referencing_symbols로 확인. 참조: modules/lead-reasoning.md §7 |
   | 스레드 컨텍스트 불일치 | Plan Transformation Spec에 "@MainActor 필수" → 구현이 일반 Task. 원본이 main queue(PromiseKit .done 등)인데 After가 background Task | 원본 main queue 미보존 — `@MainActor Task` 필요. 참조: `modules/code-transform-validation.md` |
   | 래퍼 범위 과잉 | @MainActor/do-catch/Task 블록 내에 해당 컨텍스트 불필요 문장 포함. 원본 `.done { UI업데이트; 데이터변환 }` → After `MainActor.run { UI업데이트; 데이터변환 }` 전체 래핑 | 기계적 1:1 변환 — 문장별 컨텍스트 필요성 판단 후 최소 범위 분리. 참조: `modules/code-transform-validation.md` [ablation: scope-min-v1] |
   | 에러 경로 축소 | 원본 switch/catch 분기 N개 → After catch < N개. `== .case(value)` 비교 사용 | enum associated value 무시. `if case` 패턴 매칭 필수 |
   | 퀄리티 역행 | After 줄 수 > Before 2배. 원본 추상화(struct/helper/extension)가 인라인 해체 | 리팩토링이 코드 악화. protocol extension/convenience 검토 |
   | 관찰 보고 의무 | 구현 중 지시 범위 외 설계 문제(Clean Architecture 위반, dead code, 위험한 패턴) 발견 | [함의-B] 형식으로 기록(modules/lead-reasoning.md §5). 실행 금지. Gate 3 전 일괄 보고 |
   | 동기화 부재 | singleton/shared 타입에 `var` 추가/수정 시, `@MainActor`/`actor`/lock/serial queue 보호 없음 | data race 위험 — plugin-refs.md 역방향 트리거 참조. 동시성 보호 메커니즘 추가 필요 |
   | 싱글톤 deinit | `static let shared` 타입에 `deinit` 작성 시 | deinit은 호출되지 않음 — 정리가 필요하면 명시적 `tearDown()` 메서드 사용 |
   | 기본값 소비자 영향 | 비동기 채워지는 property에 기본값(`= false`, `= nil`) 설정 시 | 소비자가 첫 콜백 전에 읽으면 기본값으로 분기 — guard/if 패턴 영향 확인 |
   | 외부 피드백 무검증 수긍 | 외부 도구/리뷰어의 "파라미터 누락" 등 지적에 함수 시그니처 확인 없이 동의 | Read(시그니처) + 기존 패턴 대조 필수 — cross-validation.md § External Feedback Gate |
   | SDK 래퍼 부분 분석 | 외부 SDK 객체의 `?.` 메서드 중 일부만 nil 동작 분석하고 나머지 건너뜀. "안전" 결론으로 추가 분석 중단 | 같은 객체의 모든 `?.` 메서드 nil 동작 + 서버 관점 전수 분석. 참조: `modules/lead-reasoning.md` §1.5 |
   | Task 내부 프로퍼티 쓰기 | `Task { }` 블록 내에서 `self.property = value`를 `MainActor.run` 밖에서 실행. 특히 리뷰어 조언으로 MainActor 범위를 줄일 때 순수 연산과 side effect를 분류하지 않고 함께 밖으로 이동 | 각 문장을 순수 연산(파싱, 변환)과 side effect(프로퍼티 할당, UI)로 분류. side effect는 소비자 스레드 확인 후 배치. 참조: `modules/lead-reasoning.md` §1.5 |
   | 핵심 시나리오 보류 | PR이 해결하려는 원래 문제(버그, 크래시)의 재현 시나리오 중 하나가 "다음 PR에서 수정"으로 보류됨. 특히 race condition 수정에서 경합 시나리오 일부만 해결 | PR 목표와 보류 시나리오를 대조. 원래 버그가 보류 시나리오에서 재현 가능하면 → 현재 PR에서 해결 필수 또는 AskUserQuestion |

   보고 형식:
   ```
   ⚠️ 구현 마찰 감지

   **신호**: {감지된 마찰 유형}
   **위치**: {파일:심볼}
   **현상**: {구체적 현상}
   **플랜 재검토 추천**: 예/아니오
   ```

   > 사용자가 "계속"이라고 해야 진행. 마찰 감지 시 무시 강행 금지.

   **잔존 패턴 사전 검사** (Anti-Pattern Constraints가 있는 Plan에서만):
   Plan에 Anti-Pattern Constraints 테이블이 포함된 경우, 구현 시작 전 + 각 Step 완료 후에
   해당 Grep 패턴으로 코드베이스를 검사합니다.

   ```
   절차:
   1. Plan의 Anti-Pattern Constraints 테이블에서 "검증 Grep 패턴" 컬럼 추출
   2. 각 패턴에 대해 Grep 실행 (대상: 변경 파일 + 관련 모듈)
   3. 매칭 발견 시 → "잔존 패턴" 마찰 신호로 보고
   4. 모든 잔존 패턴이 제거/대체될 때까지 해당 Step 완료 불가
   ```

4. **API 문법 확인** (불확실할 때 + SDK 래퍼 작성 시 필수):
   - `mcp__context7__query-docs` → 정확한 문법/시그니처
   - `/sc:explain` → API 사용법 설명
   - **SDK 래퍼 원칙**: 래퍼 함수의 모든 파라미터가 내부 SDK 호출에 전달되는지 확인. SDK에 해당 파라미터를 받는 오버로드가 있는지 반드시 검증

5. **(선택) /simplify 게이트**: 코드 변경이 있을 때 `/simplify focus on {step-context}` (참조: modules/execution-modes.md)

6. **매 Step 완료 후 빌드 검증**: 참조 `modules/build.md`

6.3. **⛔ Behavioral Equivalence Check** (Transformation Spec이 있는 Step 완료 후):
   - Plan의 Transformation Spec 로드 → 원본 코드 Read
   - Spec "실행 스레드" ↔ 구현의 Task/@MainActor 대조
   - Spec "에러 처리" ↔ 구현의 catch 분기 수 + 패턴 대조
   - Spec "추상화 수준" ↔ 구현 줄 수 대조
   - 불일치 → 마찰 보고 → 사용자 확인. 참조: `modules/code-transform-validation.md`
   - ⛔ Spec "실행 스레드" ↔ @MainActor: Zero-Exception 기계적 확인. 원본 main queue → After @MainActor 보장 (범위는 필요 문장에만 한정 — `code-transform-validation.md` Scope Minimality 단서)
   - ⛔ Spec "요청 파라미터" ↔ 키 목록: 추가/삭제 0건 확인
   - ⛔ [verified] 태그 확인 (fail-closed): Spec에 [verified] 없는 주장 → 구현 전 검증 강제 (uncertainty-verification.md)

6.5. **⛔ 아티팩트 기록** (항상 — compact recovery 필수):
   각 구현 Step 완료 후 진행 상태를 기록한다.
   - ASD 활성: `{WORK_DIR}/code/step-{N}.md` + `progress.md` + `index.md` 업데이트
   - 비ASD: `write_memory("fz:checkpoint:code-step{N}", "Step {N}/{M}: {변경 파일}. 빌드: OK/FAIL. 결정: {요약}")`
   형식 참조: `modules/context-artifacts.md`

7. **요구사항 부합 검증** (3+ Step 구현에서만):
   - `/sc:reflect --type task` → 현재까지의 구현이 계획에 부합하는지 확인
   - 조건: 전체 Step이 3개 이상인 구현의 중간 지점에서 실행
   - 목적: 방향 이탈 조기 발견 → 토큰 낭비 방지

8. **Issue Tracker에 빌드 이슈 기록** (실패 시)

8.5. **⛔ Codex 교차 검증** (TEAM 모드 — 생략 금지):
   모든 Step 구현 완료 후, Gate 3 진입 전에 Lead가 실행한다.
   ```bash
   /fz-codex check "구현 코드 교차 검증"
   ```
   - 에이전트 구현 결과를 cross-model로 검증
   - 실패 시: 재시도 1회 → 실패 사실 기록 후 /sc:analyze 폴백
   - SOLO 모드에서는 선택 (TEAM에서는 필수)

### 빌드 실패 대응

참조: `modules/build.md` — 에러 유형별 대응표, 빌드-수정 반복 패턴

/ralph-loop 에스컬레이션 래더 적용 (참조: modules/execution-modes.md)

---

## Gate 3: Implementation Complete

- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 모든 Step 구현 완료?
- [ ] 빌드 성공? (프로젝트 빌드 검증 통과)
- [ ] 빌드 경고 최소화?
- [ ] 아키텍처 패턴 준수?
- [ ] ⛔ 아티팩트 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)
- [ ] ⛔ 새 SPM 패키지 생성이면 Chore 완료? (.gitignore .build 등록, Package.resolved 커밋, pbxproj 등록)
- [ ] 트리거 해당 시 Implication Scan 실행? (modules/lead-reasoning.md + cross-validation.md 참조)
- [ ] 관찰 함의(카테고리 B)가 있으면 사용자에게 보고했는가?
- [ ] SOLO + 3+ 파일 변경이면 `/sc:reflect` 실행했는가? (하네스 원칙 4 + Gap G-R1, 관찰 중)
- [ ] ⛔ Codex 교차 검증 완료? (TEAM 모드 — Lead가 /fz-codex check 실행)

---

## Few-shot 예시

```
BAD (마찰 무시):
Step 3 완료. if-else 5개 추가.
→ 분기 폭증 감지 안 함

GOOD:
Step 3 마찰 감지: ContentType 분기 5개 → Strategy 패턴 검토 필요
- 현재: switch contentType { case .movie: ... case .series: ... case .live: ... }
- 원인: ContentDetailInteractor가 모든 타입을 직접 처리
- 제안: ContentDetailStrategy 프로토콜 + 타입별 구현 분리
- 판단: Step 4에서 분리 진행 (3개 이상 분기는 전략 패턴)

BAD (원본 미존재 추가):
// 원본: multipartFormData.append(fileURL, withName: "file")
.init(data: try Data(contentsOf: fileURL), name: "file",
      fileName: "file", mimeType: "application/octet-stream")
→ 원본에 fileName/mimeType 없음. 임의 추가.

GOOD:
.init(data: try Data(contentsOf: fileURL), name: "file")
→ optional 파라미터는 원본에 없으면 생략. 추가 필요 시 AskUserQuestion.
```

## Boundaries

빌드 성공을 확인한 후 다음 Step으로 진행한다.

**Will**:
- 검증된 계획 기반 점진적 코드 구현
- Serena 심볼 도구 활용 정밀 편집
- 프로젝트 빌드 검증
- 빌드 에러 자동 수정

**Will Not**:
- 계획 없이 대규모 코드 생성 (→ /fz-plan)
- 코드 리뷰/검증 (→ /fz-review)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| XcodeBuildMCP 실패 | Bash로 xcodebuild 직접 | 수동 빌드 |
| Serena 연결 실패 | Edit + Write 직접 수정 | 수동 편집 |
| 빌드 반복 실패 | /ralph-loop 래더 (modules/execution-modes.md) | 사용자 에스컬레이션 |

## Completion → Next

Gate 3 통과 후:
```bash
/fz-review "구현한 코드 리뷰해줘"
```
