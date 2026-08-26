# Peer Review Verification Gates

Synthesize 단계에서 실행하는 9가지 검증 게이트.
4.4 → 4.4-A → 4.5 → 4.6 → 4.6.5 → 4.7 → 4.7-A (+ Origin Verification) → 4.8 → 4.9 순서로 적용. 게이트 통과 후 CHECKPOINT 저장.

## 목차

- [Module Role (UC-12, v4.7.1)](#module-role-uc-12-v471)
- [Gate 4.4: Factual Claim Verification (Major+ 이슈)](#gate-44-factual-claim-verification-major-이슈)
- [Gate 4.4-A: Mapping Fidelity Gate (refactoring PR, v4.4.0)](#gate-44-a-mapping-fidelity-gate-refactoring-pr-v440)
- [Gate 4.5: Line Verification (Major 이슈만)](#gate-45-line-verification-major-이슈만)
- [Gate 4.6: Compiler-Verifiable Claim Gate](#gate-46-compiler-verifiable-claim-gate)
- [Gate 4.6.5: Inheritance Chain Impact Gate](#gate-465-inheritance-chain-impact-gate)
- [Gate 4.7: Behavior-Verifiable Claim Gate](#gate-47-behavior-verifiable-claim-gate)
- [Gate 4.7-A: Deleted Logic Migration Check](#gate-47-a-deleted-logic-migration-check)
- [Gate 4.8: Reactive Error Path Gate (RxSwift/Combine)](#gate-48-reactive-error-path-gate-rxswiftcombine)
- [Gate 4.9: Call-site & Convention Verification](#gate-49-call-site--convention-verification)
- [Session-added Assets Application (Checkpoint 직전)](#session-added-assets-application-checkpoint-직전)
- [Checkpoint (Gates 완료 후)](#checkpoint-gates-완료-후)

---

## Module Role (UC-12, v4.7.1)

- **Role**: **Consumer** (evidence 기반 gate 운영)
- **Consumes**: `modules/evidence-collection.md` raw evidence rows (Gate 4.4-A, 4.7-A에서 evidence 파일 소비)
- **Direction**: producer ← consumer
- **Note**: a2 절차에서 evidence-collection을 참조하는 것은 procedure cross-reference (dependency edge 아님). 합병 ❌ (Progressive Disclosure 보호).

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

**참조**: `modules/evidence-collection.md` a2 절차, `modules/uncertainty-verification.md` Default-Deny mapping claim, `agents/review-quality.md` §7 Source Fidelity (mapping atom 검증).

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

⛔ **`symbols.json` 부재 시 조용히 스킵하지 않는다.** Gather Step 2(Serena pre-caching)를 생략했으면 이 게이트와 **관점 6(Dependency Impact) 전체**가 무력화된다(`protocol_conformers`·`base_class_hierarchy`·`import_graph` 의존). 부재를 확인하면 리포트에 **"관점 6·Gate 4.6.5 부분 수행 — symbols.json 미생성"**을 명시하고, INCLUDE 이슈 키워드 경로로 Grep 폴백 + confidence ceiling 70을 적용한다.

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

## Session-added Assets Application (Checkpoint 직전)

> `modules/review-checks.md` 검증 4-O(fz-review)에서 이식. ⛔ 새 게이트가 아니다 — Checkpoint 절차의 한 항목이다.
> ⚠️ *[candidate: evidence 1 session. 활성 강제 X — 5 sessions 후 결정]*

**발동**: 이 세션에서 메모리·스킬·가이드·모듈을 **추가 또는 수정**한 경우.

```
1. 본 세션에서 추가/수정한 자산 목록화 (memory/feedback_*.md · SKILL.md · modules/*.md · guides/*.md)
2. 각 자산이 명시하는 검증 항목을 이번 리뷰에 실제 적용했는지 확인
3. 미적용 → **관찰 기록** `missed_session_asset` — ⛔ **severity를 부여하지 않는다.** Lead가 작성만 하고 적용 안 한 사실을 리포트 "관찰 사항"에 남긴다
```

⛔ **severity 미부여 이유**: 이 항목은 표본 1건 candidate다. severity를 붙이면 `major`가 verdict에 반영되어 **"활성 강제 X"라고 선언한 규칙이 즉시 판정을 바꾼다** — `guides/prompt-optimization.md §4`의 "체크리스트 행 추가 반사" 안티패턴이다. 5 sessions 관측 후 승격 시 비로소 severity를 논한다.

왜: 자산을 만드는 것과 그 자산으로 자기 작업을 검증하는 것은 **비대칭**이다. 작성이 적용을 보장하지 않는다.
⛔ 이 검사는 *이번 세션에 추가된* 자산만 본다 — 이전 세션의 자산 미적용은 대상이 아니다(그건 해당 자산 자체의 트리거 소관).

## Checkpoint (Gates 완료 후)

게이트 실행 완료 후 반드시 파일로 저장:

```
${WORK_DIR}/synthesized-issues.json  — 병합된 이슈 (Dedup+투표+게이트 검증 결과)
${WORK_DIR}/confidence-matrix.md     — 최종 Confidence Matrix
${WORK_DIR}/review-index.md          — Compact Recovery 엔트리포인트
```


---

## MergeContract — 발견을 어떻게 병합·판정하는가

**보장**: 최종 판정 규칙이 문서에 있고 Lead 의 즉흥 판단에 의존하지 않는다.

⛔ **이 절이 병합의 SSOT 다.** 다른 문서와 어긋나면 여기가 이긴다 — 특히 두 지점:
- `SKILL.md` § Synthesize 의 dedup·투표 서술은 **Tier 3 전용**이다. 전 경로 dedup 키는 §3(`discoveryAxis` 포함)을 따른다
- Codex `reverse` 는 §6 대로 **`question` 전환**이다 — 이종 검증에 삭제 권한을 주지 않는다. `peer-review-tiers.md` § Codex Devil's Advocate 도 같은 규칙을 적고 여기를 가리킨다

> 배경: 한 Tier 2 실행에서 Lead 가 문서에 없는 `[L실측] 우선` 규칙을 그 자리에서 만들어 썼다. 그것으로 3건이 살아났고 렌즈가 못 찾아 Lead 가 직접 발굴한 2건도 들어갔다 — 최종 14건 중 5건이 **문서화되지 않은 판단**에 의존했다. 계약을 세우는 목적은 그 5건을 죽이는 것이 아니라 **정식 경로로 살리는 것**이다.

### 1. 입력원

| 입력원 | Tier 0 | Tier 1 | Tier 2 | Tier 3 |
|---|:---:|:---:|:---:|:---:|
| 렌즈 (arch·quality·correctness) | — | — | 3 | 3 |
| Codex challenger | `--codex` 시 | ✓ | ✓ | ✓✓ |
| Lead 실측 | ✓ | ✓ | ✓ | ✓ |

⛔ SSOT 는 `modules/peer-review-tiers.md` § Tier 구성 표다. 여기 표는 그것을 병합 관점으로 다시 쓴 것이며 **수치가 어긋나면 tiers 표가 이긴다**.

### 2. 렌즈 상태 — 3분한다

`scheduled`(예정대로 실행) · `skipped`(Tier 설계상 없음) · `failed`(실행 실패)

⛔ **`skipped` 와 `failed` 를 같은 "결측"으로 묶지 않는다.** Tier 0 에 렌즈가 없는 것은 설계이고, Tier 2 에서 렌즈가 null 인 것은 장애다. 판정이 달라야 한다 — 전자는 정상 경로, 후자는 신뢰도 감쇠 대상이다.

### 3. dedup 키

`파일` + `line_range 겹침` + `discoveryAxis`. 축이 다르면 같은 자리라도 별건이다 — 한 줄이 구조 문제이면서 동시성 문제일 수 있다.

⛔ **같은 키를 `stage2Trigger` 의 `severityConflicts` 도 쓴다**(`peer-review.js` 의 `sameAxis`) — 트리거가 축을 무시하면
이 규칙과 모순된다. 실측(PR #4774): 축 미반영 시 충돌 7건 중 **5건이 교차축 별건**이었다(세 렌즈가 신규 파일
헤더 라인에 서로 다른 주제를 앵커해 위치만 겹쳤다).
⚠️ 단 `unpairedMajor` 는 축을 보지 않는다 — 단독 major 는 축과 무관하게 교차가 필요하다.

### 4. Lead 실측의 자격

Lead 발견이 렌즈 판정을 이기려면 **증거 형식**을 갖춰야 한다.

| 요건 | 내용 |
|---|---|
| 대상 | 렌즈가 받은 입력 **밖**의 파일·심볼 |
| 방법 | 직접 Read 또는 결정론 명령(grep·git show)의 실제 출력 |
| 기록 | 리포트에 `[L실측]` 표기 + 무엇을 어떻게 확인했는지 1줄 |

⛔ 렌즈가 이미 본 자리를 다시 본 것은 자격이 없다. 그것은 재확인이지 독립 증거가 아니다.

### 5. Lead 단독 발견 (렌즈 0건)

§4 자격을 갖추면 **입장한다**. 렌즈가 못 찾았다는 사실은 기각 사유가 아니다 — 렌즈에 없는 축이거나 입력 밖이었을 수 있다.

⚠️ 단 `discoveryAxis` 를 반드시 부여한다. 그래야 "어느 축이 렌즈에서 비어 있었나"가 집계에 남는다.

### 6. Codex verdict 처리

| verdict | 처리 |
|---|---|
| `agree` | found_by 에 추가 |
| `supplement` | 근거 보강, 판정 유지 |
| `challenge` | Lead 가 실측으로 판정. 기각하면 사유 기록 |
| `reverse` | ⛔ 자동 제거 금지 — **`question` 으로 전환**하고 판별 방법(oracle)을 적는다 |

⛔ `reverse` 를 자동 제거로 만들면 이종 검증이 **삭제 권한**을 갖는다. 코드로 결판나지 않는 사안이 조용히 사라진다.

### 7. origin·severity 보정 순서

`origin 판정` → `pre-existing 이면 suggestion 으로 cap` → `improvement 는 cap 없이 non-blocking 표기` → `Codex verdict 반영` → `disposition 결정`

순서를 지킨다. severity 를 먼저 정하면 origin 이 그것을 못 내린다.

### 8. disposition

`include` · `question` · `observation` · `exclude`

| 값 | 언제 |
|---|---|
| `include` | 코드 증거로 확정. 수정 요청 |
| `question` | 코드로 결판나지 않음. 판별 oracle 을 함께 적는다 |
| `observation` | 사실이나 이 PR 의 책임이 아님 |
| `exclude` | 실측으로 기각. 사유 기록 |

### 9. confidence 산식 — ⛔ Tier 별로 다르다

| Tier | 산식 |
|---|---|
| 0 | 투표 없음 (렌즈 0) — Lead 판정 + §4 자격 |
| 1 | **2-vote** (Lead + Codex) |
| **2** | ⛔ **투표 없음 — 단순 병합.** Matrix 를 만들지 않는다 |
| 3 | **3-vote** + Stage2 교차 + Stage3 DA 반영 |

⛔ **"미투표"는 Tier 2 에만 해당한다.** Tier 1 은 2-vote 를, Tier 3 은 3-vote 를 쓴다. 전역 미투표로 구현하면 그 둘이 깨진다.

⛔ **Tier 2 반환 필드는 트리거 발화 여부로 갈린다** (D1 조건부 Stage 2):

| 필드 | 미발화 | 발화 | Tier 3 |
|---|:---:|:---:|:---:|
| `crossVerdict`·`crossSeverity` | 없음 | **있음** | 있음 |
| `finalSeverity`·`counterVerdict` | 없음 | **없음** | 있음 |

발화 시 `crossSeverity` 는 **조정 제안**이지 확정이 아니다 — Tier 2 는 투표하지 않으므로 최종 판정은 이 계약이 한다. 필드 유무는 반환 `stage2Ran` 으로 판별한다(하드코딩 아님 — 실제 응답 존재로 계산).

⛔ 미발화 경로에서는 원본 `severity` 를 쓰고 교차·DA 열을 "미수행"으로 표기한다. 필드를 찾다 실패하면 병합이 멈춘다.

⛔ **한 finding 이 판정을 두 개 받을 수 있다** — `correctness` issue 는 arch·quality **양쪽**
교차 입력에 들어간다(발화 원인이 검증을 받게 하려고). 그래서 판정 개수는 finding 종류에 따라 다르다.

| 판정 수 | `crossVerdict` | `crossSeverity` | `crossVerdicts[]` |
|---|---|---|---|
| 0 | `unreviewed` | 없음 | 없음 |
| 1 | 그 verdict | `adjust` 일 때만 | 없음 |
| 2 · 판정 일치 | 그 verdict | 제안 중 **더 심한 쪽** | 없음 |
| 2 · 판정 갈림 | **`contested`** | **없음** (원본 severity 유지) | **있음** — 렌즈별 원본 판정 |

⛔ **갈렸을 때 스크립트가 고르지 않는다.** § 9 가 "Tier 2 는 투표하지 않는다"고 한 이상,
승자를 정하는 코드는 계약 밖에서 투표하는 것이다. `contested` 는 **판정 유보**이지 기각이 아니다 —
Lead 가 `crossVerdicts[]` 를 읽고 § 4(Lead 실측의 자격)로 판정한다.

⛔ id 로 덮어쓰지 않는다. 덮어쓰면 **concat 순서가 판정을 정한다** — 뒤에 온 렌즈가
앞의 판정을 조용히 지우고, 같은 입력이 순서만 달라도 결과가 바뀐다.
(`correctness` 를 교차 입력에 넣기 전에는 두 렌즈가 서로 다른 id 만 봐서 충돌이 없었다.)

⛔ `contested` 는 `distribution.fpFlagged` 에 **안 들어간다.** 한 렌즈가 `false_positive` 라 해도
다른 렌즈가 갈렸으면 깨끗한 오탐이 아니다. 대신 `distribution.contested` 로 건수가 보인다 —
0 이 아니면 `crossVerdicts[]` 를 읽어야 한다는 신호다.

회귀: `tests/workflows/s2-cross-merge.js` (원본 `>>> PURE:cross-merge` 블록 추출 실행)

### 회귀 검증

`tests/fixtures/peer-review/tier2-merge/` — 24건 입력 → 14건 기대. 계약을 바꿀 때 이 입력으로 같은 disposition 이 나오는지 본다.

⛔ 그 fixture 는 **오염된 브리프**로 실행된 자료다. seed 파생 항목의 기대값은 `include` 가 아니라 `question`/`observation` 이다 (`modules/evidence-collection.md` § InputHygiene 참조).

---

## 경량 경로에서 무엇이 살아남는가 (Tier 0/1)

⛔ **경량은 절차 생략이지 검증 생략이 아니다** — 형제 4스킬(`fz-plan`·`fz-review`·`fz-code`·`fz-modernize`)이 쓰는 같은 규율이다.

> 신설 근거(S8 파일럿): Coverage Gate 가 `### 4. Confidence Matrix 출력` 안에 있는데 Tier 0 은 그
> Matrix 를 건너뛴다 — **게이트가 경량 경로가 지나가지 않는 자리에 있었다.** 실제로 미발화해 이슈 2건이 분모 없이 나갔다("형제 2곳"→실제 4:1 · "PR 구성 문제"→최근 20건 중 16건 동일).

| 게이트 | Tier 0/1 | 근거 |
|---|:---:|---|
| **Coverage Gate** | **생존** | 전수·카운트·부정 주장의 분모는 경로와 무관하게 필요하다 |
| **Negative-Result Gate** | **생존** | "0건" 이 도구 고장인지 대상 부재인지는 경로와 무관 |
| **InputHygiene (C3)** | **생존 — 형태 변경** | Tier 0/1 은 차단이 아니라 **탐지·표시 + 강등**(§ InputHygiene 이 규정) |
| **MergeContract (C1)** | **생존** | § MergeContract 가 전 경로 SSOT |
| **Reflection Rate** | **조건부** | Codex 호출이 있을 때만(Tier 1). `N<10` 은 preliminary — verdict 보류 |
| Confidence Matrix | **미적용** | Tier 0 은 simple checklist · Tier 2 는 미투표 — **설계상 부재** |
| Stage 2 교차 조정 | **미적용** | Workflow 미사용 경로 |

⛔ **"미적용"과 "생략"을 구분한다** — 전자는 설계, 후자는 누락(§ MergeContract § 2 `skipped`/`failed` 와 같은 규율). "미수행" 으로 뭉뚱그리면 빠뜨린 것인지 원래 없는 것인지 알 수 없다.

**값싼 자가 점검** — 리포트 전에 자기 서술을 훑는다. 아래가 있으면 분모를 댄다:
`N곳` · `N개` · `전부` · `나머지는` · `~뿐` · `0건` · `형제 N/N` · `유일` · `이것만`
⚠️ `cross-validation.md` § Coverage Gate 트리거 어휘의 **미러** — 재정의하지 않는다.

