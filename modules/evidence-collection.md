# Code Evidence Collection

> Gather Phase에서 에이전트에게 전달할 실제 코드를 수집하는 모듈.
> 에이전트는 Bash/git show 접근 불가이므로 Orchestrator가 사전 수집한다.
> PR #3639 교훈: diff만으로는 producer site, 삭제 심볼 잔존 여부를 확인할 수 없어 추론→환각→오탐 발생.

## Module Role (UC-12, v4.7.1)

- **Role**: **Producer** (raw evidence 수집 정책)
- **Consumed by**: `modules/peer-review-gates.md` Gate 4.4-A, 4.7-A (evidence 파일 소비)
- **Direction**: producer → consumer
- **Note**: peer-review-gates의 Gate 4.4-A를 trigger 조건 인용은 procedure cross-reference (dependency edge 아님). acyclic 보장.

## 산출물 경로

```
${WORK_DIR}/evidence/
├── old-new-pairs.md         — 변경 함수의 before/after 코드
├── semantic-mapping.md      — API/condition mapping의 atom-level ground truth (v4.4.0 신규)
├── producer-consumer.md     — enum/struct의 생성-소비 매핑
├── deletion-verification.md — 삭제 심볼의 잔존 참조 확인
├── base-patterns.md         — regression 판정용 base 코드 패턴
├── caller-analysis.md       — 신규/변경 init의 호출자 코드 + 참조 타입
└── convention-samples.md    — 프로젝트 내 동일 패턴 샘플 (convention 판정)
```

## 수집 절차

```bash
mkdir -p ${WORK_DIR}/evidence
```

### a. 변경 함수의 old/new 코드 페어 → `evidence/old-new-pairs.md`

diff hunk에서 변경된 함수/메서드 식별 (최대 20개, diff 크기 비례).
각 함수에 대해:

```
git show upstream/${BASE_BRANCH}:${FILE} | 해당 함수 추출  → ## OLD
git show pr-${PR_NUMBER}:${FILE} | 해당 함수 추출           → ## NEW
```

함수당 최대 50줄, 총 최대 1000줄 제한.

### a2. Semantic Mapping Ground Truth → `evidence/semantic-mapping.md` (v4.4.0)

> Mapping Layer SPOF 방어. old/new mapping claim을 단순 `OldAPI → NewAPI` 한 줄로 작성하지 않고 atom-level decomposition + ground truth source 인용 의무.
> 적용 조건: refactoring PR (API rename, 패턴 변환, type substitution 등) 감지 시 **의무 작성**. row 0건 또는 artifact 부재 시 fail-closed pre-trigger 발동 — `modules/peer-review-gates.md` Gate 4.4-A 참조.

각 mapping마다 atom-level table 작성:

| # | Old API | New API | old_definition (file:line) | new_definition / callsite | normalized_atoms (old) | normalized_atoms (new) | lossy_atoms | mapping_status |
|---|---------|---------|---------------------------|---------------------------|------------------------|------------------------|-------------|----------------|
| M-001 | `OldType.method()` | `NewType.method` | `[verified: source-file:line]` | `[verified: source-file:line]` | `[A, B]` | `[B]` | `[A]` | `lossy` |

**필드 정의**:
- `old_definition` / `new_definition`: ground truth source code 인용. `[verified: file:line]` 태그 의무.
- `normalized_atoms`: boolean/composed predicate를 atom 단위로 분해 (예: `Reachable && IsWWAN` → `[Reachable, IsWWAN]`).
- `lossy_atoms`: old에 있지만 new에 표현되지 않은 atom (있으면 lossy).
- `mapping_status`:
  - `verified` — atom 1:1 일치
  - `lossy` — atom 누락 (new가 old의 일부 component 표현 못함)
  - `over-mapped` — new가 old에 없는 atom 추가
  - `unverified` — source 인용 부재 또는 contract 불명

**Verify Discipline (의무)**:
- [ ] 각 mapping row에 `[verified: file:line]` 태그?
- [ ] normalized_atoms 분해 완료?
- [ ] lossy_atoms 산출 완료 (빈 list여도 명시)?
- [ ] mapping_status 분류 완료?

**효과**: refactoring PR에서 API 의미 component 누락 (e.g., `isReachableViaWWAN() = Reachable AND WWAN` → 매핑이 `→ Cellular`로 simplified되어 Reachable 게이트 누락) 을 atom-level로 즉시 catch.

**참조**: Gate 4.4-A Mapping Fidelity Gate (`modules/peer-review-gates.md`).

### b. Producer/Consumer 매핑 → `evidence/producer-consumer.md`

diff에서 아래 패턴 감지 시 producer site 수집:
- enum case destructuring에서 `_` 사용 → throw/init site의 실제 값 수집
- 파라미터 이름 변경/제거 → 생성 site에서 해당 값의 출처 확인
- 콜백/클로저 이동 (old: cancelCallback → new: onConfirm) → 1:1 매핑 기록

형식:

| Consumer (file:line) | Pattern | Producer (file:line) | Actual Value |
|---------------------|---------|---------------------|-------------|

### c. 삭제 대상 잔존 참조 확인 → `evidence/deletion-verification.md`

diff에서 삭제된 파일/심볼 목록 추출. 각 심볼에 대해:

```bash
git grep {symbol} pr-${PR_NUMBER} -- '*.swift' '*.m' '*.h'
```

형식:

| Symbol | Deleted In | Remaining References | Count |
|--------|-----------|---------------------|-------|

Count == 0이면 "✅ 완전 제거", > 0이면 "⚠️ 잔존 {N}건"

### d. regression 이슈 base 비교용 → `evidence/base-patterns.md`

에이전트가 regression으로 판정할 가능성이 높은 변경 패턴:
- guard/validation 제거 → base에서 동일 guard 존재 여부
- void return (silent failure) → base에서도 동일 패턴 존재 여부
- withCheckedContinuation + callback → base의 동일 함수 전체 코드

형식:

| Pattern | Base Code (file:line) | PR Code (file:line) | Same? |
|---------|---------------------|--------------------|----|

### e. Caller Analysis → `evidence/caller-analysis.md`

> PR #3646 교훈: EpisodeUseCase init 선언만 보고 "올바른 패턴" 판정. 실제 caller(ViewModel)가
> `DefaultEpisodeUseCase(repository: DefaultEpisodeRepository())` full chain을 하드코딩하는 것을 3개 모델 모두 놓침.

PR에서 새로 생성/변경된 init, protocol, public API의 **호출자 코드**를 수집한다.
에이전트는 "선언이 올바른가"만 판단하므로, "사용처에서 어떤 타입을 알아야 하는가"를
Orchestrator가 사전에 제공해야 한다.

대상:
- 새로 추가된 init/factory (UseCase, Repository, ViewModel, Builder)
- protocol 시그니처 변경
- public/internal API 시그니처 변경

수집:
1. diff에서 신규/변경 init 식별 (함수 시그니처 추출)
2. `git grep "TypeName(" pr-{PR} -- '*.swift'` → 호출자 파일:라인
3. 각 호출자의 해당 라인 ±5줄 추출 (default param이 있으면 호출자의 default 값도 포함)
4. 호출자가 참조하는 concrete 타입 목록 추출

형식:

| Declaration (file:line) | Caller (file:line) | Caller Layer | Types Caller Must Know |
|------------------------|-------------------|-------------|----------------------|

### f. Convention Sampling → `evidence/convention-samples.md`

> PR #3646 교훈: 3/3 모델이 "UseCase default param = DIP 위반"을 major로 판정.
> 실제: AppComponent, Event/Notice/Favorites Builder 등 프로젝트 전체에 같은 패턴.

PR의 핵심 패턴과 **같은 패턴의 다른 모듈** 코드를 수집한다.
"교과서적으로 틀렸다"보다 "이 프로젝트에서 어떻게 하고 있는가"가 리뷰의 기준이다.

대상 (diff에서 식별, 최대 3개):
- UseCase/Repository init 패턴 (default param 유무)
- Builder/Component DI 패턴
- 데이터 변환 위치 (Repository vs Interactor vs DTO.toEntity())
- 에러 처리 패턴 (try? vs do-catch vs Result)

수집:
1. PR의 핵심 아키텍처 패턴 식별 (max 3)
2. 각 패턴에 대해 Grep → 같은 프로젝트의 다른 모듈에서 동일 패턴 2-3개 수집
3. 패턴 일관성 판정:
   - 3+ 모듈이 동일 → "Convention" (에이전트에 전달)
   - 1-2 모듈만 → "Minority"
   - 0 모듈 → "Novel"

형식:

| Pattern | PR Code | Module A | Module B | Module C | Convention? |
|---------|---------|----------|----------|----------|------------|

---

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-peer-review | Gather Phase 2.6에서 호출 |
| modules/peer-review-gates.md | Gate 4.4, 4.7-A에서 evidence 파일 소비 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
