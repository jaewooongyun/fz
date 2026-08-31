---
name: fz-explain
description: >-
  코드·구조·기능 설명. 전체 흐름 위에 동작↔코드를 1:1로 매핑하고, 낯선 타입은 정의부터 보인다.
  예: 구조 설명해줘, 이거 어떻게 동작해?, 어떤 역할이야?, 과외하듯 설명해줘, 처음 보는 사람도 알게
  (비사용: 위치만 찾기 →fz-search, 변경사항 해설 →fz-pr-digest, 문제 지적 →fz-review, 원인 찾아 수정 →fz-fix)
  explain structure, how does it work, walkthrough, onboarding, code comprehension
user-invocable: true
argument-hint: "[기능·모듈·심볼 이름 또는 상황] [--light]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__find_referencing_symbols,
  mcp__serena__get_symbols_overview,
  mcp__serena__activate_project,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  Read, Grep, Glob
provides: [structure-explanation, code-understanding]
needs: [none]
intent-triggers:
  - "구조.*설명|코드.*설명|어떻게.*동작|어떤.*역할|전체.*흐름|과외|처음.*보는.*사람"
  - "explain.*structure|how.*work|walkthrough|tutor|onboard"
---

# /fz-explain — 코드·구조를 처음 보는 사람에게 설명한다

> **행동 원칙**: 기능을 축으로 삼는다. 흐름을 먼저 세우고, 등장하는 것을 정의하고,
> 동작 하나에 코드 하나를 붙인다. 근거를 못 대는 문장은 등급을 낮추거나 쓰지 않는다.

## 개요

```
대상 이름 → seed 산출 → 폐포 탐색(5축) → 어휘 등급 → 층위 배치 → 게이트 → 문서
```

- 규칙 정본은 `modules/explanation-protocol.md` — 이 스킬은 **seed 산출**과 **호출**만 맡는다
- PR·diff 가 없어도 동작한다. 입력은 이름이거나 상황이다
- 산출은 마크다운 문서 하나 + 대화 요약

## 사용 시점

```bash
/fz-explain "결제 플로우"                  # 기능 이름
/fz-explain "PaymentInteractor"           # 심볼 이름
/fz-explain "장바구니가 가끔 비는 상황"        # 상황·현상
/fz-explain "인증 모듈" --light             # 흐름 + 매핑만 (구조 근거 생략)
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| `modules/explanation-protocol.md` | 폐포 5축 · 어휘 등급 · 게이트 G1~G8 · 층위의 **정본** |
| `modules/explanation-output.md` | 출력 섹션 A~E 형식 (정본 §7 에서 분리) |

⛔ 이 스킬은 위 모듈의 규칙을 **재정의하지 않는다**. 아래 Phase 1 만 스킬 고유분이다.

---

## Phase 1: Seed 산출

입력이 셋 중 무엇인지 판별하고 seed 심볼 집합을 만든다.

### 절차

```
(a) 심볼 이름     find_symbol 직접 조회 → 그 심볼이 seed
(b) 기능 이름     Grep 으로 후보 → get_symbols_overview → **핵심 도메인 심볼**을 seed
                 ⛔ 진입점을 seed 로 잡지 않는다 — 진입점은 R1 의 **도착지**이지 출발지가 아니다.
                    진입점에서 시작하면 아래로 R2 한 홉뿐이라 흐름의 하단이 끊긴다.
                    중간 계층(요청을 처리하는 쪽)을 잡아야 R1 이 위로, R2·R5 가 아래로 편다
(c) 상황·현상     현상에 관여하는 심볼을 역추적 → seed
                 ⛔ "왜 잘못됐나" 를 찾는 것이 아니라 "어떻게 동작하나" 를 설명한다
```

판별이 애매하면 묻는다. ⛔ 추측으로 seed 를 잡으면 이후 전부가 어긋난다.

### Gate 1: Seed Ready

- [ ] seed 가 파일이 아니라 **심볼** 단위인가
- [ ] 입력 유형 (a)(b)(c) 중 하나로 판별됐는가
- [ ] (c) 상황 입력이면 설명 목적임을 확인했는가 (수정 목적이면 fz-fix 로 넘긴다)

---

## Phase 2: 프로토콜 실행

`modules/explanation-protocol.md` 를 Read 한 뒤 §9 실행 절차 T2~T6 을 수행한다.

### 스킬이 채우는 값

정본이 비워 둔 두 자리를 이 스킬이 정한다.

| 자리 | 값 |
|------|-----|
| 매핑 블록 `상태` 슬롯 | `핵심` 또는 `보조` — 이 동작이 설명 대상의 중심인지 |
| 출력 §7-A 좌표 표시 | 생략한다 — 변경 개념이 없다 |

### Gate 2: Protocol Applied

- [ ] 정본 모듈을 Read 했는가
- [ ] R1~R5 다섯 축을 전부 시도했는가
- [ ] 0건이 나온 축을 성질이 다른 도구로 교차 확인했는가
- [ ] 게이트 G1~G8 을 적용했는가 (정본 §10 체크리스트)
- [ ] 탐색 경계(§7-E)를 작성했는가 — 잘린 것이 없어도

---

## Phase 3: 산출

```
문서   {WORK_DIR}/explain-{대상}.md   — 층 0~3 + 부록
대화   한 줄 요약 · 흐름 단계 제목 · 다룬 범위 · 문서 경로
```

⛔ 매핑 블록 전문 · 구조 근거 본문 · 탐색 경계는 대화에 내지 않는다.
⛔ 마크다운으로 끝낸다. 다른 출력 형식은 범위 밖이다.

### Gate 3: Delivered

- [ ] 문서가 층 0~3 순서인가
- [ ] §7-A 의 각 단계가 §7-C 에 블록으로 존재하는가
- [ ] 대화 출력이 네 요소만 담았는가

---

## Verification Discipline

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 를 붙인다
- 외부 도구 판정을 인용할 때는 원문 + `[외부: name]` — 재포장하지 않는다
- 채택자·호출자 수가 0건이나 1건이면 측정 실패를 먼저 의심하고 다른 도구로 교차 확인한다

---

## Few-shot 예시

```
BAD (낯선 타입을 정의 없이 씀):
  "BaseNavigationController 가 flush() 를 묻고, 그 라우터가 자식을 detach 한다"
  → 세 이름 다 이 저장소 고유인데 정의가 없다. 독자는 문장을 읽어도 뜻을 못 잡는다

GOOD:
  BaseNavigationController [A]
  선언:  `class BaseNavigationController: UINavigationController` — Nav/Base.swift:12
  하는 일: 화면이 pop 될 때 드러난 화면의 라우터에게 정리를 요청한다
  왜 지금 나오나: 3단계에서 이 요청이 시작된다
```

```
BAD (주체만 있고 경로가 없음):
  "실제로 화면을 올리는 건 RootTab 이었다"
  → 누가 하는지는 알겠는데 어느 코드인지 못 찾아간다

GOOD:
  탭 → `MyPage.onTapSettings()` → `listener?.wantsSettings()`
      → `Home.wantsSettings()` (전달만 한다)
      → `RootTab.wantsSettings()` → `router?.routeToSettings()` ← 여기서 처음 push
  ⭐ "전달만 한다" 도 정보다 — 부모마다 한 줄 함수가 필요하다는 비용이 여기서 보인다
```

```
BAD (근거 종류가 섞임):
  "이 구조는 확장에 유리하다. 채택자가 여럿이고 테스트도 쉽다"
  → 어느 것이 확인된 사실이고 어느 것이 짐작인지 구분되지 않는다

GOOD:
  채택자: `A`, `B`, `StubC` [실측: 채택자 3]
  주입 지점: `Component.swift:31`
  만약 직접 생성했다면 → [기계적] 상위 테스트가 하위 전체를 함께 만들어야 한다
```

---

## 테스트 케이스

> 상세: `references/test-spec.md`
> fixture: `references/fixtures/positive-defects.md` (검출) · `negative-clean.md` (과잉 검출)

---

## Boundaries

**Will**:
- 기능·모듈·심볼·상황을 대상으로 전체 흐름과 동작↔코드 1:1 매핑을 산출
- 등장하는 저장소 고유 타입과 프레임워크 개념을 정의와 함께 소개
- 구조가 왜 이렇게 됐는지, 없으면 무엇이 깨지는지를 근거 등급과 함께 서술

**Will Not**:
- 코드 위치만 찾기 → `fz-search`
- 변경사항 해설 (PR·diff 축) → `fz-pr-digest`
- 품질 문제 지적 → `fz-review` · `fz-peer-review`
- 원인 진단과 수정 → `fz-fix`
- 코드 수정 — 쓰기 도구를 갖지 않는다

### 도구 경계

```
⛔ Write · Edit · Bash 미부여
   설명 스킬이 코드를 고칠 이유가 없다. 도구가 있으면 언젠가 쓴다.
   PR·diff 도 다루지 않으므로 git 접근이 필요 없다.

⛔ Skill 도 미부여
   정본 §8.1 의 문체 교정 호출은 **Lead 가 수행한다** — 스킬은 무엇을 언제 부를지 정하고
   실행은 호출자 몫이다. 문서 저장(Write)과 같은 축이다.
   실측: 외부 스킬을 본문에서 호출하는 형제 스킬 다섯 중 넷이 선언 없이 동작한다
   (fz-review 13건 · fz-code 12건 · fz-plan 10건 · fz-fix 9건 — 전부 선언 0).
```

### 깊이 옵션 — `--light` 하나만 둔다

⛔ 플랜은 `--light | --deep` 둘을 뒀으나 `--light` 만 채택했다. 근거 셋: 기본 경로가 이미
층 0~3 전부를 담아 `--deep` 이 더할 것이 없고, 티어가 늘면 경량 경로 검증 계약 표면이 함께
늘며, 요구가 "처음 보는 사람도"여서 깊이 선택 자체가 목표가 아니다.

### light 모드

`--light` 또는 "가볍게·간단히" 신호 시:

- 층 0~2 만 산출 (흐름 + 어휘 + 매핑). 층 3 구조 근거는 생략
- 폐포는 R1·R2·R5 만 (계약·배선 축 생략)
- 탐색 예산 40 → 15

⛔ **G1 인용 게이트와 §7-E 탐색 경계는 경량 경로에서도 생략 불가.** 인용 없는 매핑은
짐작이고, 조용한 절단은 "이게 전부"로 읽힌다 — 분량을 줄이는 것과 근거를 빼는 것은 다르다.

---

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| 심볼 조회 실패 | Grep 으로 후보 탐색 후 재시도 | 대상 이름을 사용자에게 되묻는다 |
| 탐색 축 결과 0건 | 성질이 다른 도구로 재확인 | 재확인 후에도 0건이면 그 사실을 §7-E 에 기록 |
| 예산 40 초과 | seed 를 중요도 상위로 절단 | 절단 목록을 §7-E 에 기록 |
| 진입점 5홉 미도달 | 도달 지점부터 서술 | "진입점 미도달"을 §7-E 에 기록 |
| 문체 교정 스킬 미설치 | 기계 검사 4종 + 내장 산문 3종 | 부분 충족임을 문서에 명시 |
| 대상이 수정 요청 | 설명만 산출 | `fz-fix` 로 안내 |

---

## Completion → Next

```bash
/fz-review "이 구조 검토해줘"        # 설명하다 문제를 발견했을 때
/fz-plan "이 구조 개선 계획"          # 구조를 바꾸려 할 때
/fz-search "관련 코드 더 찾아줘"      # 범위를 넓힐 때
```
