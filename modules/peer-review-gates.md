# Peer Review Verification Gates

Synthesize 단계에서 실행하는 4가지 검증 게이트.
4.5 → 4.6 → 4.7 → 4.8 순서로 적용. 게이트 통과 후 CHECKPOINT 저장.

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

## Checkpoint (Gates 완료 후)

게이트 실행 완료 후 반드시 파일로 저장:

```
${WORK_DIR}/synthesized-issues.json  — 병합된 이슈 (Dedup+투표+게이트 검증 결과)
${WORK_DIR}/confidence-matrix.md     — 최종 Confidence Matrix
${WORK_DIR}/review-index.md          — Compact Recovery 엔트리포인트
```
