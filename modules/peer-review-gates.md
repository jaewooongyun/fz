# Peer Review Verification Gates

Synthesize 단계에서 실행하는 9가지 검증 게이트.
4.4 → 4.4-A → 4.5 → 4.6 → 4.6.5 → 4.7 → 4.7-A (+ Origin Verification) → 4.8 → 4.9 순서로 적용. 게이트 통과 후 CHECKPOINT 저장.

> Gate 4.4 (Factual Claim Verification)는 PR #3639에서 발견된 3건의 오탐을 방지하기 위해 추가.
> 에이전트의 사실적 주장(existence/source/behavior/origin)을 Orchestrator가 기계적으로 검증한다.
> Gate 4.4-A (Mapping Fidelity Gate, v4.4.0)는 Mapping Layer SPOF 방어. evidence 매핑이 ground truth와 atom-level 동등인지 검증한다.

---

## Gate 4.4: Factual Claim Verification (Major+ 이슈)

> **핵심 원칙**: 에이전트의 "파일 X에 심볼 Y가 있다/없다" 주장은 empirical fact이다.
> Orchestrator가 git grep/git show로 기계적으로 확인한다. 에이전트 합의(3/3)는 사실을 보장하지 않는다.
>
> PR #3639 교훈 3건:
> - Sonnet "ChromecastManager.swift (L365)에서 BDCustomAlertView 호출" 주장 → git grep 결과 0건 (환각)
> - 2/3 모델 "서버 제공 타이틀 무시" 주장 → throw site 확인 시 클라이언트 하드코딩 (부분 코드 읽기)
> - 3/3 모델 "새로운 continuation hang 위험" 주장 → base 코드에도 동일 패턴 (origin 오판)

**대상**: INCLUDE 이슈 중 severity **Major 이상** 전체. Minor는 선택적.

**처리 절차**:
```
1. 이슈의 핵심 주장(claim) 추출 + 유형 분류:

   | 주장 유형 | 예시 | 검증 방법 |
   |----------|------|----------|
   | Existence | "파일 X에 심볼 Y가 잔존" | git grep {Y} pr-{PR} -- '*.swift' '*.m' |
   | Source | "이 값이 서버에서 온다" | git show pr-{PR}:{file} → 값 생성 site 확인 |
   | Behavior | "새 코드에서 W 동작이 누락" | git show pr-{PR}:{file} + base:{file} → 비교 |
   | Origin | "이것은 regression이다" | git show base:{file} → old 코드에 동일 패턴? |

2. 주장 유형별 기계적 검증 (Orchestrator가 Bash로 직접 실행):

   Existence Claim:
     git grep {symbol} pr-{PR} -- '*.swift' '*.m' '*.h'
     → 0건: 주장 반증 → EXCLUDE
     → 1건+: 주장 확인 → INCLUDE 유지

   Source Claim:
     git show pr-{PR}:{file} | grep -A5 '{context}'
     → evidence/producer-consumer.md와 대조
     → 불일치: 주장 반증 → EXCLUDE

   Behavior Claim:
     git show base:{file} vs git show pr-{PR}:{file}
     → evidence/old-new-pairs.md와 대조
     → 동일 동작: 주장 반증 → severity 하향 or EXCLUDE

   Origin Claim (regression 주장):
     git show base:{file} | grep '{pattern}'
     → base에도 동일 패턴 존재: origin을 pre-existing으로 재분류
     → severity cap: suggestion

3. 검증 결과 기록:
   ├─ 주장 확인 → INCLUDE 유지, claim_verified: true
   ├─ 주장 반증 → EXCLUDE, claim_verified: false, reason: {증거}
   └─ 검증 불가 → confidence ceiling 65 + [검증 필요] 태그
```

**비용**: Major 이슈당 ~10초 (git grep/show 1-2회). 전체 리뷰에 30-60초 추가.

---

## Gate 4.4-A: Mapping Fidelity Gate (refactoring PR, v4.4.0)

> **핵심 원칙**: refactoring PR의 API/condition mapping이 ground truth와 atom-level 동등인지 검증한다.
> Mapping Layer SPOF 방어 — 6-Layer LLM 검증이 같은 evidence 매핑 base를 공유하면 매핑 오류는 layer 수와 무관하게 통과한다.
>
> PR #3796 교훈 `[미검증: 사용자 제공]`:
> - `ReachabilityManager.isReachableViaWWAN() = (Reachable AND IsWWAN)` 이중 게이트
> - evidence 매핑이 `→ isReachableViaCellular`로 simplify되어 reachable 게이트 누락
> - 6-Layer 검증 (boolean equiv + Opus + Sonnet + Codex + Lead self + DA) 모두 통과 → CodeRabbit (rule-based) 단독 발견

### Pre-Trigger (fail-closed)

**조건**: refactoring PR 감지 시 (diff에 API rename, 패턴 변환, type substitution 1건+)

**Action**:
1. `${WORK_DIR}/evidence/semantic-mapping.md` 존재 확인
2. **부재** → ❌ Critical 이슈 자동 생성 ("Mapping artifact missing for refactoring PR")
3. **존재** + row 0건 → ⚠️ Major 이슈 ("Refactoring PR with empty mapping")
4. **존재** + row 1+ → 기본 Gate 4.4-A 발동

→ Mapping artifact 자체 누락 시 SPOF 재발 가능성 차단.

### 절차

1. `semantic-mapping.md`의 모든 mapping row 추출
2. 각 row 검증:
   - `mapping_status=verified` → 통과
   - `mapping_status=lossy` → ❌ candidate issue 자동 승격 (agent 투표와 무관)
   - `mapping_status=unverified` + agent가 "동등/OK/문제없음" 결론 → ⚠️ confidence ceiling 65 + `[mapping 검증 필요]` 태그
   - `mapping_status=over-mapped` → ⚠️ Major 이슈 (intentional? 사용자 확인)
3. 3/3 agent 동의여도 Basis가 `IO`이고 mapping evidence가 unverified → ❌ INCLUDE 금지 (기존 Basis CV/IO 구조 재사용)

### Failure 시 동작

- `lossy` → Critical 이슈로 보고. Synthesize 단계에서 자동 INCLUDE.
- `unverified` + 동등 결론 → confidence ceiling + 사용자 검토 요청.
- `over-mapped` → Major 이슈 (사용자 확인).

### 효과

"모든 LLM이 같은 mapping을 믿고 OK"인 경우에도 deterministic evidence (`mapping_status=lossy`)가 우선 → Synthesize 단계에서 이슈 자동 생성. Layer Diversity 본 게이트 안에서 통합 해결 (deterministic source + LLM 판단).

**비용**: mapping row당 ~10초 (git show + atom 비교). 전체 리뷰에 N×10초 추가.

**참조**: `modules/evidence-collection.md` a2 절차, `modules/uncertainty-verification.md` Default-Deny mapping claim, `agents/review-quality.md:60-64` Source Fidelity (mapping atom 검증).

---

## Gate 4.5: Line Verification (Major 이슈만)

Major 이상 이슈의 line_range를 실제 PR 브랜치 코드로 검증:
1. `git show pr-{PR_NUMBER}:{FILE}` 로 실제 코드 확인
2. 에이전트가 보고한 line_range와 실제 위치 대조
3. 불일치 시 실제 라인 번호로 업데이트 → `verified_line_range` 필드 추가
4. evidence_trace의 코드 블록에 `file:line` 주석 보강

---

## Gate 4.6: Compiler-Verifiable Claim Gate

> **핵심 원칙**: "컴파일러 경고/에러가 발생한다/않는다"는 에이전트가 추론할 수 없는 empirical fact. 컴파일러가 final judge.
>
> PR #3434 교훈: 3/3 에이전트 "UITabBarItem Sendable 경고 발생" 주장 → 실제: 경고 없음, 제안 코드(@MainActor 추가) 오히려 경고 발생. Swift 5.10 sending semantics를 아무도 컴파일러로 확인하지 않았음.

**4.6 gate 실행 전**: 현재 Synthesize 중간 상태를 `synthesized-issues-partial.json`으로 저장할 것.

**감지 조건** (하나라도 해당하면):
- perspective: `concurrency` 또는 `sendable`
- 설명에 `경고`, `warning`, `Sendable`, `sending`, `actor isolation`, `@MainActor` 포함
- 클레임이 "이 코드가 컴파일러 경고를 발생시킨다/않는다"

**처리 절차**:
```
1. INCLUDE 이슈 중 Compiler-Verifiable 이슈 식별
2. swiftc -strict-concurrency=complete -swift-version 5 minimal_repro.swift 실행
   - minimal_repro: git show pr-{PR}:{FILE}에서 해당 함수/클로저 추출
   - swiftc 경로: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swiftc
3. 결과 해석:
   ├─ "경고 발생한다" 주장 + 실제 경고 없음 → EXCLUDE (이슈 DROP)
   ├─ "경고 발생한다" 주장 + 실제 경고 있음 → INCLUDE 유지
   └─ Swift 6 모드도 추가 확인: -swift-version 6
4. confidence-matrix.md에 기록: compiler_verified: true/false + result
```

**검증 불가 시** (XcodeBuildMCP 없음, SDK 미확인 등):
- confidence ceiling → 65
- 이슈에 `[컴파일러 검증 필요]` 태그 추가

---

## Gate 4.6.5: Inheritance Chain Impact Gate

> PR #3478 교훈: Base class init에 optional DI 파라미터 추가 시, 3/3 Claude 에이전트가 미탐지. Codex(gpt-5.4)만 발견.
> 원인: diff에 subclass init 변경이 없어 분석 대상에서 제외됨. 컴파일러도 default value 존재로 미탐지.

**감지 조건** (하나라도):
- `symbols.json.base_class_hierarchy` 존재
- INCLUDE 이슈 중 "DI 변경", "init 시그니처", "optional", "willSet/didSet" 키워드

**처리 절차**:
```
1. base_class_hierarchy에서 변경된 base class 추출
2. 각 subclass init 패턴 검증:
   ├─ super.init(newParam: value) 명시 전달 → OK
   └─ default init (newParam = nil) → Step 3으로
3. 화면 기능 교차 검증:
   ├─ subclass가 사용되는 View 파일 Read
   ├─ 해당 dependency를 활성 사용하는 UI 컴포넌트 존재? (preview, player, network 등)
   └─ 존재 → severity major (silent regression)
4. 결과:
   ├─ 모든 subclass 확인 + 필요한 곳 주입됨 → confidence 유지
   ├─ 미주입 + 화면에서 dependency 미사용 → 안전 (기록만)
   └─ 미주입 + 화면에서 dependency 활성 사용 → INCLUDE severity major
```

**Functional Test**:
- Given: Base init에 optional param 추가, 16개 subclass → When: Gate 실행 → Then: 미주입+활성 2개 major 보고
- Given: Base init 변경 없음 → When: 조건 체크 → Then: Gate 스킵
- Given: Serena 실패 → When: Gate 실행 → Then: Grep 폴백 + confidence ceiling 70

---

## Gate 4.7: Behavior-Verifiable Claim Gate

> **핵심 원칙**: "이 상태가 런타임에 실제로 발생할 수 있다"는 에이전트가 패턴으로 추론할 수 없는 empirical fact. 상태 할당 경로를 추적해야 한다.
>
> PR #3449 교훈: 3/3 에이전트가 `isTimeMachineAvailable` guard 누락을 major로 판정(confidence 90). 실제: `isAtLiveEdge = false`는 `setTimeShift()` 안에서만 할당되고, 모든 `setTimeShift()` 호출부는 이미 가드를 갖고 있음 → 불변식 성립 → false positive. 3/3 동의가 false confidence를 증폭.

**감지 조건** (하나라도 해당하면):
- 이슈 유형: "missing guard condition"
- 이슈 유형: "기존 패턴 X가 있는데 새 코드에 없음" (Pattern-Consistency)
- 설명에 `guard 누락`, `조건 없음`, `발생할 수 있다`, `될 수 있다` 포함
- perspective: `architecture`, `state-management`, `guard`

**처리 절차**:
```
1. INCLUDE 이슈 중 Behavior-Verifiable 이슈 식별
2. 핵심 상태 변수(guarded variable) 식별
3. 해당 변수의 ALL assignment 위치를 Grep으로 "{variable} = " 검색
4. 각 setter에서 논쟁 중인 guard가 이미 상위에서 적용되는지 확인
5. 결과 해석:
   ├─ 모든 setter가 이미 guard에 의해 보호됨 → 불변식 성립
   │   → confidence ceiling 65 + "[불변식 확인 필요]" 태그 + severity 하향 검토
   ├─ guard 없는 setter 경로 존재 → 불변식 불성립 → INCLUDE 유지
   └─ 추적 불가 → confidence ceiling 70 + "[런타임 검증 필요]" 태그
6. confidence-matrix.md에 기록: behavior_verified: true/false + trace
```

Pattern-Consistency 이슈: 패턴 불일치가 functional difference를 만드는지 확인. 아니라면 confidence ceiling 75.

---

## Gate 4.7-A: Deleted Logic Migration Check

> **핵심 원칙**: "diff에서 코드 삭제 = 로직 누락"이라고 단정할 수 없다. 모듈화/리팩토링 PR에서는 로직이 다른 파일로 이동하는 것이 일반적이다. 삭제를 발견하면 "PR 전체에서 동일 로직이 다른 위치로 이동했는지"를 먼저 확인해야 한다.
>
> PR #3473 교훈: review-quality가 Interactor의 `guard getConnectState() != .open` 삭제를 "연결 상태 체크 누락 (minor regression)"으로 판정. 실제: guard가 `SendbirdTvingTalkChatUseCase.connect()` 내부로 이동한 것. diff는 파일 A의 `-guard`와 파일 B의 `+guard`를 별개 이벤트로 보여주므로 이동을 자동 연결하지 않는다.

**감지 조건** (하나라도 해당하면):
- origin이 `regression`이고 설명에 `삭제`, `누락`, `제거`, `없음`, `빠짐`, `removed`, `missing`, `deleted` 포함
- "기존에 있던 X가 새 코드에 없다" 유형의 이슈
- PR이 모듈화/리팩토링 목적 (레이어 간 코드 이동이 빈번한 컨텍스트)

**처리 절차**:
```
1. INCLUDE 이슈 중 "삭제/누락" 키워드가 포함된 regression 이슈 식별
2. 삭제된 로직의 핵심 패턴 추출 (함수명, guard 조건식, 핵심 키워드)
3. PR 브랜치 전체에서 해당 패턴을 Grep 검색:
   - `git show pr-{PR}:{FILE}` 로 변경 파일 직접 확인
   - 또는 Grep으로 PR에서 변경된 파일 전체 스캔
4. 결과 해석:
   ├─ 동일/유사 로직이 다른 파일에 존재 → "relocated" 판정
   │   → EXCLUDE (이슈 DROP) + confidence-matrix에 relocated: true 기록
   ├─ 유사하지만 조건/범위가 다름 → confidence ceiling 70 + "[이동 확인 필요]" 태그
   └─ 어디에도 없음 → INCLUDE 유지 (진짜 삭제)
```

**Few-shot 예시**:
```swift
// BAD: diff에서 삭제만 보고 즉단
// Interactor diff: -guard SendbirdChat.getConnectState() != .open else { return }
// → "연결 상태 체크 누락 (regression)" 판정
// (UseCase에 이동한 것을 확인하지 않음)

// GOOD: 삭제 발견 → PR 전체에서 핵심 패턴 검색
// 1. 삭제된 패턴: "getConnectState() != .open"
// 2. Grep 검색: git show pr-3473 전체에서 "getConnectState" 검색
// 3. 발견: SendbirdTvingTalkChatUseCase.swift:57에 동일 guard
// 4. 판정: relocated → 이슈 DROP
```

### Gate 4.7-A 확장: Origin Verification (모든 regression 이슈)

> PR #3639 교훈: 3/3 모델이 "새로운 continuation hang 위험" → regression 판정(confidence 88).
> 실제: base 코드의 `BDCustomAlertView.instantiateAlert()` guard에서도 동일한 continuation leak 패턴 존재.
> base 코드와 비교하지 않고 새 코드만 분석하면 pre-existing 패턴을 regression으로 오판한다.

**대상**: 기존 4.7-A 대상(삭제/누락) + **모든 regression 판정 이슈**

**추가 절차** (기존 4.7-A 이후):
```
모든 origin: regression 이슈에 대해:
1. evidence/base-patterns.md에서 해당 코드 패턴의 base 버전 확인
2. evidence/old-new-pairs.md에서 old/new 코드 비교
3. base에 동일/유사 취약점 패턴이 존재하면:
   ├─ 동일 패턴 (코드 구조 같음) → origin: pre-existing, severity cap: suggestion
   ├─ 유사 패턴 (다른 메커니즘 같은 효과) → origin 유지, "[base에도 유사 패턴]" 태그
   └─ base에 없는 새 패턴 → origin: regression 확인 (severity 유지)
4. confidence-matrix.md에 기록: origin_verified: true/false + base_evidence

⛔ evidence 파일이 없으면 (Gather에서 미수집):
  Orchestrator가 즉석에서 git show base:{file} 실행하여 확인.
  "확인 불가" 상태로 INCLUDE하지 않는다.
```

---

## Gate 4.8: Reactive Error Path Gate (RxSwift/Combine)

> **핵심 원칙**: "Observable/Single이 에러를 emit한다"는 에이전트가 시그니처만으로 추론할 수 없다. 에러 경로를 추적해야 한다.
>
> PR #3457 교훈: 3/3 에이전트가 "flatMapLatest onError 누락 → 스트림 영구 종료" 주장(confidence 88). 실제: `updateTabBarItem`이 `async`(non-throws)이고 내부 모든 에러를 `try?`로 흡수 → Single은 error emit 불가 → false positive.

**감지 조건** (하나라도 해당하면):
- perspective: `rx-error-propagation`, `stream-lifecycle`
- 설명에 `subscribe onError 누락`, `스트림 종료`, `에러 전파`, `onError 핸들러` 포함
- 에이전트가 "에러 시 스트림이 종료된다"고 주장

**처리 절차**:
```
1. INCLUDE 이슈 중 Reactive Error Path 이슈 식별
2. 문제 Observable/Single의 실제 에러 emit 가능성 확인:
   a. 소스 함수 시그니처 — `async throws` 여부 확인
      └─ throws 없으면 Single<Void>는 error emit 불가 → EXCLUDE
   b. 내부 `try?` / `.catch` / `.catchErrorJustReturn` 등 에러 흡수 여부 검색
   c. Kingfisher/URLSession 콜백에서 에러가 실제로 Single error로 전달되는지 확인
3. 결과 해석:
   ├─ 에러 emit 불가로 확인 → EXCLUDE + confidence-matrix에 error_path_verified: false
   └─ 에러 emit 가능 → INCLUDE 유지, evidence_trace에 에러 경로 명시
```

**Library 시맨틱 참고**:
- `Single.create { callback in callback(.success(...)) }` 안의 async closure가 `async`(non-throws)면 error emit 불가
- Kingfisher 8 `retrieveImage` 자체는 throws이지만, 호출부에서 `try?`로 감싸면 Single에게 에러 전달 안 됨
- RxSwift `flatMapLatest` + `subscribe()` (onError 없음): 업스트림이 error emit 불가면 안전

---

## Gate 4.9: Call-site & Convention Verification

> PR #3646 교훈: 3/3 모델이 "UseCase default param이 DIP 위반"을 major로 판정.
> 실제: (1) AppComponent가 이미 같은 패턴 사용 (convention), (2) default 없는 UseCase의
> caller(ViewModel)가 오히려 더 많은 concrete 타입을 참조 (역방향 문제).
> 선언부 분석만으로는 실제 영향을 알 수 없다.

**대상**: INCLUDE 이슈 중 init/DI/API 설계 관련 전체

**처리 절차**:
```
1. evidence/caller-analysis.md에서 해당 이슈의 caller 코드 확인:
   ├─ 이슈가 "X를 수정하라"고 제안 → 수정 후 caller가 더 많은 타입을 알아야 함?
   │   YES → 역효과 (confidence -30 + "[caller 역효과]" 태그)
   │   NO → 통과
   └─ caller 데이터 없음 → Orchestrator가 즉석 수집 후 판단

2. evidence/convention-samples.md에서 동일 패턴 확인:
   ├─ Convention (3+ 모듈) → severity cap: suggestion + "[프로젝트 convention]"
   ├─ Minority (1-2 모듈) → confidence 유지
   └─ Novel (0 모듈) → confidence 유지

3. 복합 판정:
   ├─ caller 역효과 + convention → EXCLUDE (이슈 DROP)
   ├─ caller 역효과만 → confidence -30
   ├─ convention만 → severity cap: suggestion
   └─ 둘 다 아님 → INCLUDE 유지
```

**Few-shot**:
```
BAD (Gate 4.9 미적용):
  "UseCase default param 제거하라" (major) → 그대로 리포트에 포함
  실제: 프로젝트 convention + 제거 시 caller(ViewModel)가 Repository까지 참조

GOOD (Gate 4.9 적용):
  Step 1: caller-analysis → ViewModel이 full chain 참조 발견 → 역효과
  Step 2: convention-samples → AppComponent, Builder 3곳에 동일 패턴 → Convention
  결과: EXCLUDE (caller 역효과 + convention)
  대안 발견: "오히려 누락된 UseCase에 default 추가" (caller 개선 방향)
```

---

## Checkpoint (Gates 완료 후)

게이트 실행 완료 후 반드시 파일로 저장:

```
${WORK_DIR}/synthesized-issues.json  — 병합된 이슈 (Dedup+투표+게이트 검증 결과)
${WORK_DIR}/confidence-matrix.md     — 최종 Confidence Matrix
${WORK_DIR}/review-index.md          — Compact Recovery 엔트리포인트
```
