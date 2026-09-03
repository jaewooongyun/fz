# Code Evidence Collection

> Gather Phase에서 에이전트에게 전달할 실제 코드를 수집하는 모듈.
> 에이전트는 Bash/git show 접근 불가이므로 Orchestrator가 사전 수집한다.
> 관측 사례: diff만으로는 producer site 와 삭제 심볼의 잔존 여부를 확인할 수 없어 추론이 환각으로 이어지고 오탐이 났다.

## 목차

- [Module Role (UC-12, v4.7.1)](#module-role-uc-12-v471)
- [산출물 경로](#산출물-경로)
- [수집 절차](#수집-절차)
- [참조 스킬](#참조-스킬)
- [설계 원칙](#설계-원칙)

---

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

⛔ **evidence 의 기본 대상은 ref 다** — `git grep <pattern> ${HEAD_REF} -- <glob>`. **작업 트리는 PR이 아니다**: 리뷰어의 트리가 PR base 와 같을 이유가 없고, 트리에 파일 자체가 없으면 grep 은 조용히 0건을 돌려준다(0건 = "없다"가 아니라 **대상 불일치**). ⛔ **ref 이름을 하드코딩하지 않는다 — Gather 가 해석한 값을 쓴다**: `${HEAD_REF}` 는 PR 리뷰면 `skills/fz-peer-review/SKILL.md` §0.5 가 fetch 한 `pr-{PR}`, 브랜치 리뷰면 그 브랜치 자체다 — `skills/fz-peer-review/scripts/gather.sh` 는 `--target (PR번호|브랜치)` 를 받고 **브랜치 모드에는 `pr-{PR}` 이 없다**. ⛔ **head 해석값은 산출물에 기록되지 않는다** — `${WORK_DIR}/base-behavior.md` 는 **base 전용**이라 거기에 head 는 없다. head 는 **Lead 가 Gather 에 넘긴 target 그 자체**이므로 호출 시점에 이미 아는 값이다 — 산출물에서 읽는 것이 아니라 그 이름을 그대로 쓴다. `${BASE_REF}` 도 `upstream/` 고정이 아니다 — `--base` 인자·PR `baseRefName`·브랜치 폴백(`feature/*`→`develop`·`hotfix/*`→`main`)으로 정해지고, PR 경로에서 로컬에 없으면 `upstream`→`origin` 순 접두가 붙고, 해석되면 merge-base 로 대체된다. **base 해석값**은 `${WORK_DIR}/base-behavior.md` 첫머리(`대상 base: …`)에 남으니 추측하지 말고 거기서 읽는다 — **merge-base 가 병기돼 있으면 그쪽**이 diff 가 비교한 원본이다(팁을 읽으면 regression↔pre-existing 이 뒤집힌다). base 대조·관례 표본이 필요한 §a·§d·§f 는 `${BASE_REF}`, 잔존 참조·호출자를 보는 §c·§e 는 `${HEAD_REF}` 다 — 아래 블록의 `pr-${PR_NUMBER}`·`upstream/${BASE_BRANCH}` 표기는 그 **자리표시자**이지 문자 그대로 쓰는 이름이 아니다. ⛔ **`${HEAD_REF}`·`${BASE_REF}` 표기 자체도 글로 쓴 자리표시자다 — 셸 변수가 아니다**: Bash 도구는 호출 사이에 셸 상태를 유지하지 않으므로 그대로 붙여넣으면 **빈 문자열로 전개**된다. ⛔ **넣을 이름이 없으면 grep 하지 않는다(fail-closed)** — 빈 ref 는 fatal 이 아니라 **작업 트리를 grep 하고 exit 0** 을 내므로 exit code 로는 잡히지 않는다(Gather 스크립트도 빈 `HEAD_REF` 를 실재하는 상태로 다뤄 `[ -n "$HEAD_REF" ]` 가드를 세 곳에 둔다). 실제 이름으로 치환한 뒤 `git rev-parse --verify <ref>` 가 통과할 때만 돌리고, 통과 못 하면 §0.5 fetch 를 먼저 하거나 사용자 에스컬레이션(`guides/skill-authoring.md` §12 L4) — 미해석 ref 로 얻은 0건은 증거가 아니다. 치환한 뒤에도 미fetch 이름은 `git grep` 이 fatal 로 0건을 내므로 **exit code 도 함께 본다** — 어느 쪽이든 **ref** 이고 작업 트리가 아니다.

⛔ **glob 은 따옴표로 감싼다** — `git grep … -- '*.swift'` · GNU `grep -r … --include="*.swift"`. zsh 는 unquoted glob 을 셸이 먼저 확장하고, 매칭 파일이 없으면 `no matches found` 로 **명령 실행 전에 중단**한다 — 출력이 비어 "0건"으로 읽히지만 grep 은 돌지도 않았다. 함정 표 정본은 `modules/cross-validation.md` § Negative-Result Gate 다.

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

> 관측 사례: UseCase init 선언만 보고 "올바른 패턴" 판정. 실제 caller(ViewModel)가
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

> 관측 사례: 3/3 모델이 "UseCase default param = DIP 위반"을 major로 판정.
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
2. 각 패턴에 대해 `git grep <pattern> ${BASE_REF} -- '*.swift'` → 같은 프로젝트의 다른 모듈에서 동일 패턴 2-3개 수집 (⛔ PR head 가 아니라 **base** 다 — PR 이 바꾼 파일이 표본에 들어가면 PR 이 자기 관례의 증거가 된다. `${BASE_REF}` 는 Gather 가 해석한 base 이고 `upstream/` 접두를 고정하지 않는다)
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


---

## InputHygiene — 무엇을 전달하지 않는가

> `skills/fz-peer-review/SKILL.md` § Orchestrator Bias 방지 규칙의 상세. 수집한 것을 **어떻게 포장하는가**를 정한다.

**보장**: Lead 의 가설이 판정 근거로 되돌아오지 않는다.

### `intentContext` 허용/금지

| ✅ 넣는다 | ⛔ 넣지 않는다 |
|---|---|
| PR 제목·본문·티켓 수용 기준 | 결함 가설 ("~가 빠진 것 같다") |
| 변경 대상과 대체 관계 (무엇이 무엇을 대체하는가) | 예상 영향 파일·화면 목록 |
| 참조할 가이드·컨벤션 경로 | 심각도 예단 ("이건 major 일 것") |

⛔ **가운데 열이 가장 새기 쉽다.** 영향 범위를 목록으로 적어 주면 렌즈가 그 목록을 되돌려주고, Lead 는 그것을 합의로 읽는다. 관측에서 렌즈 둘이 브리프에 있던 후보를 그대로 반환했고 3렌즈 동의처럼 집계될 뻔했다.

### 경로별 구현

| 경로 | 무엇을 하는가 |
|---|---|
| **Tier 2/3** | 위 표로 브리프를 검사한다. 금지 항목이 있으면 다시 쓴다 |
| **Tier 0/1** | 렌즈가 없어 오염을 *막을* 수단이 없다 → **탐지·표시**로 낮춘다 |

### Tier 0/1 — 탐지·표시

Lead 혼자 분석하므로 파일을 나눠 적어도 **같은 사람이 기억한 채 본다**. 분리는 blind holdout 이 아니라 **출처 기록**이다. 막는 대신 표시한다.

1. 분석 **전** 자신의 가설을 `${WORK_DIR}/lead-hypotheses.md` 에 적는다
2. 분석 **후** 각 발견을 그 파일과 대조한다
3. ⛔ **강등 결정식** — 가설과 겹치는 발견은 **독립 코드 증거가 없으면** `include` 로 올리지 않는다. `question` 또는 `observation` 으로 내린다

> 독립 코드 증거 = 가설에 없던 파일·심볼을 직접 읽어 확인한 것. 가설이 지목한 자리를 확인한 것은 해당하지 않는다.

### 회귀 fixture 예외

`tests/fixtures/peer-review/tier2-merge/` 는 오염된 브리프로 실행된 자료다. 병합 계약 회귀 검증에 원본 입력이 필요하므로 **이 게이트의 명시적 예외**로 둔다.

⛔ 예외는 그 하나뿐이다. 늘면 게이트가 무력해진다. fixture 의 seed 파생 항목은 `include` 가 아니라 `question`/`observation` 이 기대값이다.
