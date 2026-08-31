# Review Checks — 조건부 정밀 검증 (fz-review Phase 5)

> `skills/fz-review/SKILL.md` Phase 5에서 분리 (SKILL.md 500줄 한도 준수, 2026-06-27). 조건부 검증 본문 (4-D~4-H, 4-N/4-O/4-P candidate).
> 발동: fz-review가 모듈화/리팩토링/마이그레이션/패턴변환 작업일 때 해당 검증 Read. 항상 실행 검증(1~3)·Gate 4·검증5는 SKILL.md 잔존.

## 목차

- [검증 4-D: Constraint Matrix Compliance](#검증-4-d-constraint-matrix-compliance-조건부-fz-discover-산출물-있을-때)
- [검증 4-E: Module Boundary + Consumer Quality](#검증-4-e-module-boundary--consumer-quality-모듈화-작업-시)
- [검증 4-F: Anti-Pattern Enforcement](#검증-4-f-anti-pattern-enforcement-잔존-금지-패턴-검증)
- [검증 4-G: Protocol Conformance](#검증-4-g-protocol-conformance-프로토콜-적합성-검증)
- [검증 4-H: Source Fidelity](#검증-4-h-source-fidelity-원본-준수--리팩토링마이그레이션-시)
- [검증 4-N: Swift Naming Compliance ⚠️ candidate](#검증-4-n-swift-naming-compliance-swiftios-프로젝트-한정--candidate-lesson-intake-decision-tree)
- [검증 4-O: Session-added Assets Application ⚠️ candidate](#검증-4-o-session-added-assets-application-세션-중-추가-자산-적용--candidate-lesson-intake-decision-tree)
- [검증 4-P: Post-State Consistency ⚠️ candidate](#검증-4-p-post-state-consistency-편집-지점-일관성-candidate-1-session-evidence)

---

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
  8. ⛔ 형제 샘플(convention) 수집 — 4번 소비자 전수 수집과 같은 Grep 패스에서 함께 한다:
     - diff의 각 구조 결정(DI 획득 방식·상태 보관 위치·public API 모양)에 대해 **같은 역할의 형제 심볼**을 Grep으로 수집한다. 예: `Grep("BookmarkUseCaseImpl(")` → 형제 Interactor N곳이 어떤 방식을 쓰는지
     - 수집 결과는 판정의 **양방향 입력**이다:
       · 관례와 **같음**(3+ 형제 동일) → severity 하향 (교과서 기준만으로 위반 판정 금지)
       · 관례와 **다름** → *"형제 N곳이 X 형태"*를 근거로 제시. ⚠️ N의 강도 임계(N≥? → 어느 severity)는 **미정**이므로 현재는 **관찰 보고까지만** — 처방 severity는 부여하지 않는다 *[candidate: 표본 1건 — PR I3, N=5. 3 표본 후 임계 결정]*
     - ⛔ 수집 없이 관례를 논하지 않는다. `arch-critic`이 review-arch에 함께 로드되어 "Convention 3+ 모듈은 suggestion 이하" 억제 규칙을 주입하므로, **수집이 없으면 억제 기준만 있고 근거가 없는 상태**가 된다
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

> ⚠️ **Candidate 상태**: 축(a~e) evidence 1 session (OBS-06). 축(f) evidence 1 session (OBS-11, promotion-ledger L-8) — **축별 evidence 분리, 카운트 혼합 금지**. `modules/memory-guide.md` Lesson Intake Decision Tree 명시 — *evidence < 3 sessions → candidate*. 활성 강제 X. 본 검증은 *권장 self-check*이지 *Gate 차단*이 아님. 각 축 5 sessions 관측 후 활성화 결정.
> 발동: Swift/iOS 프로젝트 + diff에 새 식별자(helper/method/type/property) 발견 시 권장. 축(f)는 주석도 대상.
> 참조: 메모리 `Swift API Design Guidelines 교훈` — Apple Swift API Design Guidelines 5축 self-check.

```
절차:
1. diff에서 새 식별자 전수 추출 (Grep "^(\+\s*)?(func|private func|fileprivate func|public func|class|struct|enum|let|var) ")
2. 각 식별자에 대해 5축 self-check:
   (a) 반환값 있는데 동사형 → 위반 (예: getApp(), checkApp())
   (b) `X or Y` 형태 → 위반 (예: appOrLog, getOrCreate)
   (c) 부수 효과(log/persist/dispatch) 이름에 포함 → 위반
   (d) `-ed/-ing` rule 위반 (mutating ↔ non-mutating 짝 부재) → 위반
   (e) 사용자 표현 어휘 무시 → 위반
   (f) 도메인 타입/메서드/주석에 API 버전(v2/v3) 또는 transport 세부 박힘 → 위반 (버전 공존은 파라미터 오버로드로, 도메인 심볼은 무버전. 예: `WatchHistoryV3Response`·`watchedHistoryV3Page`·"v3" 주석)
   ⤷ 축(f)는 주석도 대상: step 1 grep(선언)에 더해 변경 hunk 주석에 `Grep "[vV][0-9]"`(transport 버전 토큰) 병행
3. 위반 발견 시 "naming_violation" 이슈 (severity: minor — 단 systematic하면 major)
4. 권고: Apple 정합 이름 제시 (예: appOrLog → verifiedApp)

체크리스트:
- [ ] 새 식별자 전수 추출 완료?
- [ ] 각 식별자에 5축 self-check 실행?
- [ ] 위반 발견 시 권고 대안 명시?
```

> OBS-06 사례: helper naming 4회 iteration(`withApp` → `appOrLog` → `verifiedApp`) — 사용자 지적으로 catch. fz-review 자체 검증으로 *사전 catch 가능*해야 함.

### 검증 4-O: Session-added Assets Application (세션 중 추가 자산 적용) — **CANDIDATE (Lesson Intake Decision Tree)**

> ⚠️ **Candidate 상태**: evidence 1 session (OBS-06). `modules/memory-guide.md` Lesson Intake Decision Tree 명시. 활성 강제 X. 5 sessions 관측 후 활성화 결정. 또한 *기존 principle (메모리 41차 External Authority Bias)와 same failure mode 가능* — merge 후보로도 검토.
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

> OBS-06 사례: `Swift API Design Guidelines 교훈` + fz-code "Swift Naming 위반" 신호 추가 후 *self-review에서 미적용* — 사용자 지적으로 catch. *작성 + 적용이 비대칭*인 메타 패턴 (메모리 41차 재현).

---

### 검증 4-P: Post-State Consistency (편집 지점 일관성) *[candidate: 1 session evidence]*

> ⚠️ **Candidate 상태**: evidence 1 session (OBS-24, `promotion-ledger` **L-13**). `modules/memory-guide.md` Lesson Intake Decision Tree 명시. **활성 강제 X.** 5 sessions 관측 + 외부 채점 1회 후 활성화 결정.
> **발동**: 편집이 **동종 슬롯이 열거된 구조**(아래 peer slot taxonomy)에 닿을 때만. 전 hunk 상시 적용 아님.
>
> ⛔ **진단 정정 (2026-08-10, 외부 검증 반영)**: 최초 서술은 *"post-state 축이 부재"* 였으나 **오진**이다 — 형제 렌즈가 실재한다: `skill-authoring.md` §1 **Sibling-Convention Check**(동류 항목 표기 grep — **본 검사와 같은 실패 모드**) · `fz-review` §검증 1("Grep → 변경 후 패턴 일관성") · `agents/impl-quality.md`("Codebase Pattern Consistency"). 정확한 진술은 **"존재하는 축의 (a) 입도 부족(같은 블록 형제 단위 없음) + (b) 소유자 미배선(`workflows/code-pair.js`가 impl-quality를 '미포함 기본값'으로 둠)"**.
> ⇒ 본 검사를 확정하기 전에 **대안 A(impl-quality 배선 복구)** · **대안 B(Lead 책임 체크리스트 1줄)** 와의 비용·발화율 비교가 선행돼야 한다(`harness-engineering` 원칙 1 — 가장 단순한 해결책 먼저).
>
> ⛔ **오탐 실측 (표본 소, 일반화 금지)**: OBS-24 워크트리 peer slot 11곳 적용 → emit 9곳 중 **진짜 결함 1곳**. 오탐의 공통 형태 = *표현 비대칭이 **의미 비대칭**(소비처 범위·값 결정 규칙·조건부 포함)을 정확히 반영*하는데 본 검사에 그 구분 축이 없음.
> ⛔ **"비용 0" 주장 철회**: 접근 수준·상수 소유권은 **정의상 소비처가 결정**하므로 in-block 판정 불가 [실측: `liveIcon` non-private 근거가 `BandCell.swift` 프로토콜에 있음 / `Metric` public 정당성 판정에 리포 grep 4회 필요].
> ⛔ **diff 앵커링 상속**: 절차가 "편집 hunk"에서 출발하므로 **편집이 닿지 않은 기존 비대칭은 보이지 않는다** — 본 검사가 극복하려던 한계를 그대로 물려받았다.
>
> 개념 정본: `guides/harness-engineering.md` §12 **R8-A**(delta-oracle vs post-state-oracle) — 단 그 원칙도 candidate·가설 상태.
>
> ⚠️ **현행 fz 게이트(빌드·테스트·swift-format)로는 침묵**한다 — post-state 불일치는 문법 정상 + 동작 불변인 경우가 많다. 단 *"기계 검증이 **원리적으로** 불가"* 는 과장이며(magic-number 계열 lint가 결정론적으로 잡는 부류), **lint 룰 대안 검토가 선행 과제로 남아 있다**.

```
절차: diff의 각 편집 hunk에 대해
1. 그 라인이 peer slot 집합에 속하는가?
   peer slot(결정론적) = 같은 switch의 case 절 · 리터럴 컬렉션 항목
   peer slot(판단 개입) = 구조체 초기화 목록 · 같은 레벨 분기 · 연속된 동종 프로퍼티 선언
     ⚠️ "동종" 판정은 의미 판단이라 결정론이 아니다 — 경계가 모호하면 2번으로 진행하지 말 것

2. ⭐ 형제 균일성 게이트 (오탐 억제 — 실측 기반 필수 관문):
   비교 축에 대해 **형제가 이미 균일한가?**
   - 균일(예: 형제 2/2가 전부 상수 참조) → 3번 진행
   - 불균일(형제가 애초에 여러 형태) → ⛔ **중단, 보고 금지**
     [실측 근거: `BannerMainCell+LayoutConstant.swift` 형제 15개가 adapted/iPadOrNot/인라인산술/stored 4형태 →
      게이트 없으면 전량 오탐. snp 제약 블록도 `$0` vs `make in` 혼재라 다수결 불가]

3. 형제 슬롯 Read + 표현 방식 대조 — ⛔ **in-block 판정 가능한 축만**:
   ✅ 상수 참조 vs 리터럴 하드코딩 · 헬퍼 호출 vs 인라인 구현 · 네이밍 컨벤션
   ⛔ **제외(소비처 의존 — in-block 판정 원리적 불가)**: 접근 수준(public/internal) · 상수 소유권
      [실측: `liveIcon` non-private 근거는 다른 파일의 프로토콜 요구 / `Metric` public 정당성은 리포 grep 4회 필요]
      이 축을 보려면 소비처 grep이 필요하며 그 비용은 0이 아니다 → 4-E(access modifier 의도성) 소관

4. 의미 비대칭 면제: 표현 차이가 **의미 차이를 반영**하면 보고 금지
   - 값 결정 규칙이 다름(연속 스케일 vs 브레이크포인트 선택) · 조건부 포함 vs 단순 옵셔널
   - 타입상 강제(`nil` 반환, `.zero` 관용 표기)
   - 형제 3개 이상 + 과반이 동일 표현일 때만 발화

5. 잔여 불일치 → "post_state_inconsistency" (severity: Minor, origin: defect)
   ⛔ 처방은 "국소 되돌리기"가 아니라 **전체를 보고 알맞은 형태 선택**
   ⛔ **tie-break 규칙 (검출 ≠ 처방)**: 비대칭을 감지해도 "계획서에 그렇게 썼으니 둔다"로 합리화 가능하다
      (= 사건 당시와 같은 결론). 판정은 **provenance 랭킹**을 따른다 — 코드 현실 > 자작 초안 문서
      (`harness-engineering` §12 R8-A 파생규율 · `promotion-ledger` L-11 관측 #3)
   ⛔ 형제 다수가 안티패턴이면 → 마찰 보고만, 일괄 변경은 별도 티켓 (Surgical Changes)
   ⛔ 형제와 맞추려 신규 추상화를 도입하는 것은 조기 추상화 — 사용자 확인 후에만

체크리스트:
- [ ] 편집 hunk가 peer slot에 속하는지 판정? (결정론적 축인지 확인)
- [ ] ⭐ 형제가 비교 축에 대해 **균일**한가? (불균일이면 중단)
- [ ] in-block 판정 가능한 축만 대조? (접근 수준·소유권 제외)
- [ ] 표현 차이가 의미 차이를 반영하는지 확인? (반영하면 면제)
- [ ] 불일치 시 provenance 랭킹으로 tie-break?
```

**Few-shot**:
```
BAD (delta만 검증):
  요청: "meta 상수화를 되돌려라"
  편집: Metric에서 3줄 삭제 + switch 3곳 리터럴화 → delta는 정확
  결과: case .poster: Metric.posterHeight / case .meta: 15 / case .mainBanner: Metric.mainBannerHeight
  → 같은 switch에서 한 절만 리터럴. 빌드 OK·값 동일이라 자동 oracle 전부 통과. 사용자 육안 발견.

GOOD (post-state 검증):
  편집 후 그 switch 블록 전체 Read → 형제 절은 전부 Metric 참조
  → "내 편집만 표현이 다르다" 감지 → 되돌리기 대신 계획서를 갱신
```

> ⚠️ **표면 churn과 별개** (`fz-code` friction-detect): 표면 churn은 *시간축*(동일 대상 2회+ 변경), 4-P는 *공간축*(형제 슬롯 비대칭). `memory-guide` "same failure mode → merge" 기준상 병합 부적합.
> OBS-24 사례: 세션 오류 6건 중 4건이 "대상을 격리해 보고 그것이 속한 구조를 안 봄"이라는 동일 뿌리. 관측 기록 = `modules/promotion-ledger.md` **L-13** (세션 회고 원문은 ledger에서 링크).
