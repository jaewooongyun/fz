# Review Checks — 조건부 정밀 검증 (fz-review Phase 5)

> `skills/fz-review/SKILL.md` Phase 5에서 분리 (SKILL.md 500줄 한도 준수, 2026-06-27). 조건부 검증 본문 (4-D~4-H, 4-N/4-O candidate).
> 발동: fz-review가 모듈화/리팩토링/마이그레이션/패턴변환 작업일 때 해당 검증 Read. 항상 실행 검증(1~3)·Gate 4·검증5는 SKILL.md 잔존.

### 검증 4-D: Constraint Matrix Compliance (조건부: /fz-discover 산출물 있을 때)

```
1. 제약 매트릭스 → 각 제약 추출 → diff에서 구현 부합 확인 (find_symbol + Grep)
2. 위반 → "constraint_violation" 이슈. 탈락 옵션 패턴 잔존 → 이슈
```

### 검증 4-E: Module Boundary + Consumer Quality (모듈화 작업 시)

```
1. access modifier: public/open 노출이 의도적인지 (find_symbol)
2. API surface: internal 세부사항이 public으로 노출되지 않았는지
3. 의존 방향: 하위→상위 역방향 참조 없는지 (find_referencing_symbols)
4. ⛔ 소비자 검증: Grep("import {모듈}") → 소비자 전수 수집
   - public API만 사용하는지, 설계 의도와 일치하는지
   - 앱 진입점(AppDelegate/SceneDelegate/UIWindow) 연동 정상인지
   - 모듈화 이전 레거시 패턴 잔존 여부
5. ⛔ SPM Chore 검증 (새 패키지 생성 시 필수):
   - .gitignore에 `Packages/{name}/.build` 등록 확인
   - `Package.resolved` 커밋 여부 (외부 의존성 있으면 필수)
   - pbxproj에 `XCLocalSwiftPackageReference` 등록 확인
  6. ⛔ 타입 소속 검증 (모듈화 작업 시): 각 public type에 대해 "이 타입의 관심사 = 이 모듈의 관심사?" 도메인 특화 필드/비즈니스 로직/하드코딩 UI 문자열 포함 시 모듈 경계 위반
  7. ⛔ Symbol Coverage 검증 (양방향):
     - **제거 방향** (import 변경 작업): diff에서 `import X` → `import Y`로 변경된 파일에서 X 모듈의 심볼(typealias, utility 타입 등)이 잔존하는지 grep. 잔존 시 → "symbol_orphan" 이슈
     - **추가 방향** (신규 import 추가 작업, P1 A2 추가 — cargo-cult 방어): 새로 추가된 `import X`에 대해 X 모듈의 알려진 심볼이 파일에서 사용되는지 grep. 0건이면 → "redundant_import" 이슈 (severity: minor — false positive 가능: typealias 간접 참조 등. 사용자/Codex 최종 판정)
```

### 검증 4-F: Anti-Pattern Enforcement (잔존 금지 패턴 검증)

```
Plan에 Anti-Pattern Constraints 있는 경우 실행. 절차:
1. Plan의 Anti-Pattern Constraints 테이블에서 "검증 Grep 패턴" 추출
2. 각 패턴에 대해 전체 코드베이스 Grep 실행
3. 매칭 발견 시:
   - 위치 + 컨텍스트 기록
   - "enforcement_violation" 카테고리로 이슈 생성
   - severity: Critical (리팩토링 목표 무력화)
4. 모든 금지 패턴이 0 매칭이어야 통과

체크리스트:
- [ ] Anti-Pattern Constraints의 모든 금지 패턴이 코드베이스에서 0건인가?
- [ ] 금지 패턴의 변형(alias, 간접 참조 등)도 검사했는가?
```

### 검증 4-G: Protocol Conformance (프로토콜 적합성 검증)
```
절차:
1. diff에서 시그니처가 변경된 메서드 식별
   - 파라미터 추가/제거/타입 변경/이름 변경
2. 각 메서드에 대해 프로토콜 요구사항 여부 확인
   - mcp__serena__find_referencing_symbols → 해당 메서드가 프로토콜에 선언되어 있는지
3. 프로토콜 요구사항인 경우:
   - 프로토콜 선언부가 diff에 포함되어 동일하게 변경되었는지 확인
   - 선언부가 diff에 없으면 → "conformance_break" (severity: Critical)
4. Swift 디폴트 파라미터 함정:
   - `func foo(bar: Bool = false)`는 `func foo()` 요구사항을 만족시키지 않음
   - 의도적 호환이면 → 파라미터 없는 오버로드 래퍼 추가 필요

체크리스트:
- [ ] 시그니처가 변경된 메서드 중 프로토콜 요구사항인 것이 있는가?
- [ ] 프로토콜 선언부가 새 시그니처와 일치하도록 함께 변경되었는가?
- [ ] 디폴트 파라미터만으로 적합성을 유지하려는 시도가 없는가?
```

> RIBs 아키텍처: ViewController에서 PresentableListener 프로토콜을 선언하고 Interactor가 구현.
> 시그니처 변경 시 두 파일 모두 diff에 포함되어야 한다. Interactor만 변경 시 incremental build 성공 → clean build 실패.

### 검증 4-H: Source Fidelity (원본 준수 — 리팩토링/마이그레이션 시)
```
절차:
1. diff에서 함수 호출 변경점 식별 (Before → After 패턴)
2. 변경 후 코드에 원본에 없던 파라미터/인자가 추가되었는지 확인
   - git show로 원본 코드 비교
   - optional 파라미터에 기본값(nil)이 있는데 명시적 값으로 채워졌는지
3. 추가 발견 시 → "source_deviation" 이슈 (severity: Major)

체크리스트:
- [ ] 리팩토링 diff에서 원본에 없던 파라미터가 추가되지 않았는가?
- [ ] optional 파라미터가 불필요하게 명시적 값으로 채워지지 않았는가?
- [ ] ⛔ 원본 버그 발견 시: "원본과 동일"이 이슈 dismiss 근거가 되지 않았는가? 원본 버그 발견 → 사용자에게 보고 + 수정/후속 분리 판단 요청
```

### 검증 4-N: Swift Naming Compliance (Swift/iOS 프로젝트 한정) — **CANDIDATE (Lesson Intake Decision Tree)**

> ⚠️ **Candidate 상태**: evidence 1 session (ASD-1366). `modules/memory-guide.md` Lesson Intake Decision Tree 명시 — *evidence < 3 sessions → candidate*. 활성 강제 X. 본 검증은 *권장 self-check*이지 *Gate 차단*이 아님. 5 sessions 관측 후 활성화 결정.
> 발동: Swift/iOS 프로젝트 + diff에 새 식별자(helper/method/type/property) 발견 시 권장.
> 참조: 메모리 `feedback_swift_naming_conventions.md` — Apple Swift API Design Guidelines 5축 self-check.

```
절차:
1. diff에서 새 식별자 전수 추출 (Grep "^(\+\s*)?(func|private func|fileprivate func|public func|class|struct|enum|let|var) ")
2. 각 식별자에 대해 5축 self-check:
   (a) 반환값 있는데 동사형 → 위반 (예: getApp(), checkApp())
   (b) `X or Y` 형태 → 위반 (예: appOrLog, getOrCreate)
   (c) 부수 효과(log/persist/dispatch) 이름에 포함 → 위반
   (d) `-ed/-ing` rule 위반 (mutating ↔ non-mutating 짝 부재) → 위반
   (e) 사용자 표현 어휘 무시 → 위반
3. 위반 발견 시 "naming_violation" 이슈 (severity: minor — 단 systematic하면 major)
4. 권고: Apple 정합 이름 제시 (예: appOrLog → verifiedApp)

체크리스트:
- [ ] 새 식별자 전수 추출 완료?
- [ ] 각 식별자에 5축 self-check 실행?
- [ ] 위반 발견 시 권고 대안 명시?
```

> ASD-1366 사례: helper naming 4회 iteration(`withApp` → `appOrLog` → `verifiedApp`) — 사용자 지적으로 catch. fz-review 자체 검증으로 *사전 catch 가능*해야 함.

### 검증 4-O: Session-added Assets Application (세션 중 추가 자산 적용) — **CANDIDATE (Lesson Intake Decision Tree)**

> ⚠️ **Candidate 상태**: evidence 1 session (ASD-1366). `modules/memory-guide.md` Lesson Intake Decision Tree 명시. 활성 강제 X. 5 sessions 관측 후 활성화 결정. 또한 *기존 principle (메모리 41차 External Authority Bias)와 same failure mode 가능* — merge 후보로도 검토.
> 발동: 본 세션에서 메모리/스킬/가이드를 *추가 또는 수정*한 경우 권장.
> 목적: 추가 자산이 *현재 작업 검증에 적용*되었는지 명시 확인.

```
절차:
1. 본 세션에서 추가/수정한 자산 목록화
   - 메모리 파일 (~/.claude/projects/*/memory/feedback_*.md 신설/수정)
   - 스킬 SKILL.md 수정
   - 가이드 (modules/*.md, guides/*.md) 수정
2. 각 자산에 대해 self-review 적용 확인:
   - 자산이 명시하는 검증 항목 → self-review 절차에 명시 적용했는가?
   - 검증 결과를 보고에 명시했는가?
3. 미적용 자산 발견 시 → "missed_session_asset" 이슈 (severity: major)
   - Lead가 작성만 하고 적용 안 한 경우 systematic weakness 표시

체크리스트:
- [ ] 본 세션 추가/수정 자산 목록 작성?
- [ ] 각 자산이 self-review에 명시 적용?
- [ ] 보고에 "어떤 자산을 어떻게 적용했는가" 명시?
```

> ASD-1366 사례: `feedback_swift_naming_conventions.md` + fz-code "Swift Naming 위반" 신호 추가 후 *self-review에서 미적용* — 사용자 지적으로 catch. *작성 + 적용이 비대칭*인 메타 패턴 (메모리 41차 재현).
