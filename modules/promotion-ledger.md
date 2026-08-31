# Promotion Ledger — P1/P2 조치 관측 기록

> 참조: `modules/scope-challenge.md`, OBS-03 v2.2 Patch-4
> 목적: P1 → P0 및 P2 → P1 승격을 위한 eligible session 관측 누적
> 원칙: 학습 승격 (자동 확장) 금지. AskUserQuestion + 기록만

## 목차

- [Eligible Session 정의](#eligible-session-정의)
- [관측 기록 형식](#관측-기록-형식)
- [P1 → P0 승격 조건](#p1--p0-승격-조건)
- [P2 → P1 승격 조건](#p2--p1-승격-조건)
- [현재 관측 대상 (v2.2 기준)](#현재-관측-대상-v22-기준)
- [OBS-08 회고 후보 (P2, 관측 #1)](#obs-08-회고-후보-p2-관측-1)
- [OBS-11 회고 후보 (이력 v3 마이그레이션, 관측 #1)](#obs-11-회고-후보-이력-v3-마이그레이션-관측-1)
- [OBS-19 + fz-improvement 회고 후보 (2026-07-18)](#obs-19--fz-improvement-회고-후보-2026-07-18)
- [fz-findings 진입](#fz-findings-진입-2026-08-24-신설)
- [미달 조치 정책](#미달-조치-정책)

---

## Eligible Session 정의

다음 두 조건을 모두 충족하는 ASD-{번호} 세션:

(a) `/fz-plan` Phase 0.5 ~ Phase 3 중 하나 이상 실행
(b) `/fz-codex verify` 또는 `/fz-review --deep` 실행

**또는 트랙 C (외부 리뷰어 catch — 별도 경로, a+b와 무관)**:

(c) 외부 도구(CodeRabbit/팀원/Codex)가 `/fz-review --deep` 이후에도 actionable Major+ 이슈를 1건 이상 발견한 세션. 단 4-classify(`feedback_review_trust_verification`)에서 `project-rule`/`valid-suggestion`으로 분류된 항목만 카운트 — `preference`/`needs-review`는 제외 (CodeRabbit precision ~55% 대응).

## 관측 기록 형식

각 eligible session 종료 시 해당 P1/P2 항목에 1건 append:

```markdown
### {P-ID}: {조치 이름} — 관측 #{N}
- Session: ASD-{번호}
- Date: YYYY-MM-DD
- 관측 내용: {발동 여부 + 상황}
- finding-source: internal | external({tool}) — 미기재 시 internal 간주 (기존 L-1~L-4 등). external이면 4-classify 분류 명시 (project-rule|valid-suggestion만 카운트)
- disposition 결과: {채택된 disposition}
- 근거: [verified: {file}:{line}] 인용
- Lead/Codex 일치 여부: agreed | user_decided
```

## P1 → P0 승격 조건

1. Eligible session 2건 누적 (동일 P-ID)
2. 2건 모두 [verified] 근거 첨부
3. 2건 누적 후 `/fz-codex adversarial` 실행 → approved
4. 사용자 최종 승인 → v{N+1} 릴리스에 P0 반영

## P2 → P1 승격 조건

1. Eligible session 1건 누적 (동일 P-ID)
2. [verified] 근거 첨부
3. `/fz-codex verify` 실행 → approved
4. 사용자 최종 승인 → v{N+1} 릴리스에 P1 반영

## 현재 관측 대상 (v2.2 기준)

### ~~P1-B: Generator≠Evaluator Lead 독립 절차~~ — ✅ **구현 완료 종결 (2026-08-24)**
- 관측 #0: OBS-03 (원본, 3차 설계 반영)
- ⛔ **승격 절차를 거치지 않고 구현이 먼저 됐다** — `modules/scope-challenge.md:78` *"Phase 3.2 Lead 독립 판정"* + `skills/fz-plan/SKILL.md:64` 참조. 관측 2건 대기는 무의미해졌다
- 처분: **종결** (REMOVED 아님 — 폐기가 아니라 반영 확인). 사용자 결정 2026-08-24

### ~~P1-C: Drift telemetry (AskUserQuestion)~~ — ⛔ **REMOVED (2026-08-24)**
- 관측 #0: OBS-03 (원본) · 이후 eligible session **0건 / 4개월**
- 실측: 본 파일 밖 참조 **0건** — 제안이 어디에도 반영되지 않았고 재부상 신호도 없다
- 처분: **REMOVED** (미달 조치 정책 — 제안 폐기). 사용자 결정 2026-08-24

### ~~P1-D: Q4 재구성 + rule 11차 컴파일 가능 기준~~ — ⛔ **REMOVED (2026-08-24)**
- 관측 #0: OBS-03 (원본) · 이후 eligible session **0건 / 4개월**
- 실측: 본 파일 밖 참조 **0건**
- 처분: **REMOVED** (미달 조치 정책 — 제안 폐기). 사용자 결정 2026-08-24

### ~~P2-A: Q-S5 Decision Re-open Gate~~ — ✅ **구현 완료 종결 (2026-08-24)**
- 관측 #0: OBS-03 (Decision-Lock 패턴 단독 관측)
- ⛔ 구현이 먼저 됐다 — `modules/scope-challenge.md:104` Appendix + `:56` `parent-reopen` 배선 + `skills/fz-plan/SKILL.md` § Phase 3 절차 5 `Refactoring Mode 감지` 발동 조건
- 처분: **종결**. 사용자 결정 2026-08-24

### ~~P2-B: fz-fix 자동 전환 + complexity.md 보정~~ — ✅ **구현 완료 종결 (2026-08-24)**
- 관측 #0: OBS-03 (plan-impact 단독 지적)
- ⛔ 구현이 먼저 됐다 — `skills/fz-fix/SKILL.md:41 · 216 · 299`(테스트 케이스 포함)
- 처분: **종결**. 사용자 결정 2026-08-24

### P2-C: general closure-capture retain cycle lens (Claude 경로) — 트랙 C
- 관측 #0: OBS-10 (CodeRabbit Major1 — sheetRef 강한 캡처 cycle, fz-review 6-Layer 통과)
- finding-source: external(CodeRabbit) — 4-classify: valid-suggestion
- 내용: Claude 검증 경로에 일반 closure-capture retain cycle lens 부재 — `safety-audit.md`(4-J)는 동시성 전용(retain cycle 미언급), fz-review 검증 5는 listener/delegate 누수만 다룸 → 일반 "저장 프로퍼티 보유 closure가 self 강한 캡처" 미커버. Codex `codex-skills/fz-reviewer/SKILL.md:35-36`엔 일반 retain cycle lens 존재 (Claude/Codex 비대칭).
- generalize: narrow (Swift closure) | 과적합 위험: 中 (Grep 패턴 FP — 패턴 정교화 선행)
- ⛔ 활성 차단: evidence 1세션 [memory-guide:45] → candidate. safety-audit Grep 검출 lens active 전환은 트랙 A 기준 **5세션+** 누적 후 (트랙 C 정의 = 트랙 A 준용과 일치). memory-guide:44의 `≥3 sessions`는 별도 모듈 분리 자격이지 active 임계값 아님.
- ⚡ 앵커 배선 (2026-08-31): `skills/fz-review/SKILL.md:213` retain cycle 점검 문구에 **P2-C candidate `active=false`** 를 부착했다. ⛔ **새 게이트를 만들지 않았다** — 그 방어는 이미 있었고(Codex 부재 시 이종 parity 복원) 원장 항목만 자산에서 도달 불가였다. 앵커가 없으면 관측 #1 이 발생해도 카운트를 올릴 지점이 없다
- 승격 목표 (트랙 C → 트랙 A): 별개 세션 추가 관측 후 safety-audit §확장 active 전환.

## OBS-08 회고 후보 (P2, 관측 #1)

> 출처: 내부 회고 기록 (20 catches) + 개선 분석 (분류)
> Eligible session 확인: OBS-08 = fz-plan Phase 0.5~3 (plan v1~v5) + fz-codex verify 2건 → 기준 (a)+(b) 충족 [verified: plan/codex-verify-output.md, codex-verify-v3-output.md 존재]
> ⛔ **승격 차단**: 2026-06-01 세션 Codex 한도 초과 → P2→P1 조건의 "Codex verify → approved" 미충족. 관측 #1 등록까지만. cross-model 검증 PENDING.
>
> **⛔ 2-트랙 구분 (모순 해소 2026-06-01)**: L-1~L-3은 friction 신호를 보유 → 두 lifecycle이 분리된다.
> - **트랙 A (신호 활성 — ⛔ 본 항이 임계의 canonical)**: candidate friction 신호 → active 전환. 기준 = **독립 세션 5회 관측**. `modules/memory-guide.md` § Lesson Intake는 본 항을 링크하며 값을 재정의하지 않는다. Codex verify = 활성 전 *권장 품질 게이트*(복구 시).
>   - ⛔ 이전 판은 *"기준 = memory-guide line 43"* 이라 적었다 — (a) **순환**(memory-guide는 여기를 canonical로 지목) (b) 줄번호가 실제와 2~4행 어긋남. heading anchor로 교체(2026-08-09).
> - **트랙 B (메모리 승격)**: lesson → MEMORY.md 항목/별도 모듈. ⛔ MEMORY.md 252줄 한도초과로 **현재 비권장**.
> - L-1~L-3 1차 경로 = **트랙 A**. L-4(friction 신호 없음) = 트랙 B(ledger-only).
> - **트랙 C (외부 리뷰어 catch, 2026-06-18 신설)**: 외부 도구(CodeRabbit/팀원/Codex)가 fz 미탐 이슈를 발견 → ledger 관측 진입. finding-source: external. 입구 = `pipelines.md` #19 pr-comment-review 절차 4(import-to-ledger). 활성(active) 전환은 트랙 A 기준(5 sessions) 준용 + 4-classify 통과분만 카운트.

### L-1: figma 토큰 테이블 exhaustiveness (23차 강화)
- 관측 #1: OBS-08 (catch #1,2,4,8,17,19,20 — figma 토큰 7건)
- 관측 #2: OBS-09, 2026-06-02 (catch #1~#9 + self-catch — figma 측정 미실시·color/style-run/정렬·data>render). 트랙 A 2/5 (figma 작업 세션, memory-guide:43). active 미전환: 5세션 미달 + Codex 활성 게이트 PENDING. 근거: [verified: retrospective:9,28,53,130 + ledger:81 트랙 A 카운트 기준]. Lead/Codex 일치 여부: user_decided (cross-model PENDING — 2026-06-01 한도초과)
- 관측 #3: OBS-23 | Date: 2026-07-29 | finding-source: internal (사용자 시각확인)
  - 관측 내용: 1:1 문의 화면 — 최초 구현 후 Figma 정정 커밋 4건. **그중 수치 정정은 3건**(`825d4e9ee` 여백·폰트 / `ccab43059` 동의항목 간격 / `33a5bf2bf` 닷 크기·색·간격), `bbdd88f29`는 **문구·노출 분기**(수치 아님) [verified: `git show bbdd88f29` — `showsContentWritingGuideNotice` 분기 추가 + 문구 텍스트 변경, spacing/size 변경 0건]
  - disposition 결과: 신호 확장 채택 (direct/composed 축 분리)
  - 근거: [verified: 내부 figma 대조 기록]
  - Lead/Codex 일치 여부: user_decided
  - **트랙 A 3/5**. 카운트 근거: `memory-guide.md` §Evidence 출처 *"동일 failure mode가 **별개 세션**에서 관찰돼야 1 count"* + 본 파일 §"카운트 기준 (본 세션 채택)" (Eligible `(a)+(b)`는 **P-track 승격 전용** — 트랙 A friction 신호에 비적용). ⚠️ heading 앵커로 인용 — 줄번호는 본 엔트리 추가로 이동함
- ⚠️ **관측 후보 (카운트 제외)**: OBS-22 | Date: 2026-07-30 | finding-source: **external**(QA 팀원 + CodeRabbit 2건) — 이력/구매 화면 디자인 검수 버그 티켓(Highest), M1~M7·P1~P3 중 P3 철회·M3 3차 전환. ⛔ **트랙 C 진입 조건 3개 중 어느 것도 미증명**: ① `/fz-review --deep` **이후** 발견인가 — QA 티켓은 작업을 *시작시킨 선행 입력*이라 아님 ② actionable Major+ 근거 미기재 ③ **4-classify 분류 미실행**(`project-rule|valid-suggestion`만 카운트, `:16`). → **카운트 제외**. CodeRabbit 건만 분리해 review 실행 시점·Major+ 근거·4-classify를 명시하면 별도 트랙 C 관측으로 재등록 가능. [외부: Codex review — `fz-h11-design-coverage/review/codex-review-out.md:10038-10048`]
- 내용: figma 토큰 테이블 작성 시 변경 코드의 *모든 수치* enumerate 또는 non-exhaustive 마킹 + code 시점 per-value MCP 측정. **⊕ 확장 축 2개 (2026-08-03)**: (i) **합성 실효값** — 요소 간 렌더 간격은 단일 노드의 padding/gap이 아니라 **두 요소 경계 사이를 실제로 통과하는 gap·padding의 합**이다(⚠️ flexible spacer·절대배치·음수 간격·modifier 순서 개재 시 단순 합 불성립 → 렌더 판정. 상세 `swift-pattern-detection.md` 원칙 H) [verified: 내부 figma 대조 기록 — `root gap 12 + section padding 24 = 36`인데 코드 24] (ii) **표 값의 정확성** — 표 작성은 *완전성*만 보증하고 채워진 *값의 정확성*은 보증하지 않는다 (빈 칸 카운터가 원리적으로 미탐지하는 영역)
- generalize: **narrow** (figma/UI 전용) | 과적합 위험: 中
- 근거: [verified: index.md — 23차로 figma-tokens.md 작성됐으나 §5 갭 테이블이 간격/마진 누락 → exhaustiveness 보증 부재]
- ⚡ 조치 (2026-06-01): *code 시점* 부분(개별 수치 figma 대조)을 fz-code friction-detect에 **candidate 마찰 신호 추가** (active). *plan 시점* 부분(토큰 테이블 exhaustiveness, fz-plan §F) + broad CLAUDE.md 1줄은 **보류** (narrow + 42차 frame 한계 + 23차 중복 → Codex/사용자 판단)
- ⚡ 조치 (2026-06-02, OBS-09 관측 #2): fz-code:277 신호에 **색/style-run/정렬 enumeration + data>render(childOrder) clause 확장** + **`figma 텍스트 미대조` candidate 신호 신설**(text-content 2세션, candidate 유지). plan 시점 Node Inventory(회고 §5-A)는 **DEFERRED 유지** — code 시점 enumeration gap은 277의 '사전 토큰 테이블 exhaustive 신뢰 → 누락 항목 답습' clause로 cover. 42차 caveat는 *구조 데이터 부재(flattened IMAGE)* 한정으로 재범위화 (구조 데이터 존재 노드값 읽기는 결정론적). 적용: TVOD/OBS-09/fz-enhancement/plan.md (TEAM plan+review)
- ⚡ 조치 (2026-08-03, 관측 #3): ① fz-code:276의 blanket 문장("raw 노드값 그대로 적용")을 **축별 분기로 대체** — direct property는 raw 직접 / 요소 간 실효 거리는 경계 사이 gap·padding 합산(⚠️ spacer·절대배치·음수간격·modifier 순서 개재 시 단순 합 불성립 → 렌더 판정) / raw 미표현 축은 렌더 스냅샷. ② **측정 아티팩트 provenance 3필드 표준** — figma 측정 산출물 헤더에 `file key` + `node ID` + `실측일` 고정. 선례 `OBS-23-work/figma-code-diff-01:3`은 기재, `OBS-18-work/figma-measure-exhaustive.md:3`은 미기재 → **후속 세션이 동일 스냅샷 여부를 판정 불가**(본 세션 실측 실패로 확인). ③ **Adapter(합성값 자동 diff)는 미착수** — figma node ↔ SwiftUI expression 매핑 계약 부재 [외부: Codex verify rejected — `내부 Codex 검증 기록`]. 재설계(figma calculator + mapping manifest 2단 분리) 후 재제안.
- ⚠️ **경합 가설 미해소 (2026-08-03)**: `figma-measure-exhaustive.md`(07-24 16:08)가 정정(07-29 04:10)보다 앞서 존재했으나, 두 산출물의 node 집합이 다르다(`114292…` vs file `6T8hjmMGw8xKd95NC32yKg` node `6725-121653`). **(가) 표가 stale 스펙 / (나) 합성 누락** 중 판정 불가 — provenance 부재가 원인. Figma `/design/` URL 확보 시 결판 가능. ⛔ 어느 쪽도 확정 서술 금지.
- 승격 목표 (트랙 A): figma 작업 세션 5회 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트. **현재 3/5 — 2건 남음.** ⛔ **활성 전 필수**: 회귀 fixture 1개(`parent gap 12 + child padding 24 → effective 36` 검출 / direct property는 직접 비교 / raw 미표현 축은 render-required / external 관측에 4-classify 없으면 lint 실패) — `harness-engineering.md:799` 규율1(회귀·반증 게이트 통과분만 수용). 현재 **oracle 0개** [외부: Codex review `codex-review-out.md:10091-10100`].

### L-2: fz-code 구현시점 reuse 게이트 (41차 enforcement plan→code 이동)
- 관측 #1: OBS-08 (catch #3,6,7 — helper 중복 작성)
- 내용: fz-code 구현 *전* **공유 인프라 영역**(`CLAUDE.md ## Shared Modules`) grep 게이트 (현재 41차는 fz-plan에만 enforce)
- generalize: **broad** (모든 helper 작성) | 과적합 위험: 低 (기존 방어 이동, 신규 규칙 아님)
- 근거: [verified: fz-code/SKILL.md friction-detect에 reuse 항목 0건 — grep "reuse|코드반복|기존 helper" 결과]
- ⚡ 조치 (2026-06-01): fz-code friction-detect에 **candidate 마찰 신호 추가**. candidate *추가*엔 Codex 불요 (41차 구조적 grep 검증 + 사용자 catch #3/#7 권위). 단 candidate→active *전환*엔 Codex verify 권장 (트랙 A). ledger=메모리 승격(트랙 B) 추적, friction 신호=code 시점 발화 (별개 레이어)
- 승격 목표 (트랙 A): 5 sessions 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-3: analysis-deferred-churning (31/33/40차 복합 신규 트리거)
- 관측 #1: OBS-08 (catch #13 — 위치 정렬 11-iteration churn)
- 내용: 단일 UI/설계 문제 *2회+ 변경* 시 self-stop + trade-off table 먼저 + 사용자 결정 후 1회 구현
- generalize: **broad (강)** (모든 반복 수정 상황) | 과적합 위험: 低
- 근거: [verified: retrospective §7-8 — 11회 변경 기록 + 사용자 "계속 바꾸지 말고 객관 분석하라"]
- ⚡ 조치 (2026-06-01): fz-code friction-detect에 **candidate 마찰 신호 추가** (memory-guide 5-session intake 대상). 사용자 catch #13 권위. broad. ⚠️ 단 churn은 31/33/40 *파생 new-trigger*(순수 enforcement-gap 아님) — 트랙 A 활성 전 Codex 재검토 권장 (#4 교정)
- 승격 목표 (트랙 A): 5 sessions 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-4: skill-procedure-default (team-core 보강)
- 관측 #1: OBS-08 (catch #9,11 — 팀 gc 스킬 미사용 + index 갱신 누락)
- 내용: 스킬 호출 시 본문 절차 따르기 + CLAUDE.md 권장 팀 스킬(gc/pr 등) 우선
- generalize: **broad** | 과적합 위험: 中
- 근거: [verified: retrospective catch #9 — fz-commit 본문 /sc:git 미사용 + Bash git commit 직접]
- 승격 목표 (트랙 B, ledger-only — friction 신호 없음): P2→P1 = 세션 1건 + Codex verify + 사용자 승인.

### L-5: 대칭/짝 경로 동시 수정 (③ OBS-16 메타패턴)
- 관측 #1: OBS-16 (Date: 2026-06-27, fz 환류 세션) | finding-source: internal (사용자 catch)
- 내용: fz-code/fz-plan에서 상보적 연산 쌍(expand↔collapse, container↔preview, add↔remove, open↔close 등) 중 한쪽만 수정 시 짝 경로 누락 — friction 신호 후보. 자동 grep 불가(설계 지식 필요)라 "짝 경로 확인했나?" 체크리스트 *질문* 형태로만.
- generalize: broad (상보 연산 쌍은 SW 편재) | 과적합 위험: 中 (자동 grep 불가 → 질문 형태 한정, 과탐 피로 주의)
- 근거: [verified: OBS-16 retrospective T1 — container↔preview 비대칭 5건+ + CodeRabbit Major D1-D3 전부 T1] + [verified: 본 세션 MEMORY.md L45 harness-holes 짝 누락 실시간 재현 1건]
- ⛔ 활성 차단: evidence 1 session [memory-guide:45] → candidate. active 전환 = 트랙 A **5 sessions** 누적 후. 같은 세션 다발(메타패턴 ~3 + 실시간 1)은 **1 count**.
- finding-source: internal (사용자 catch — 활용 갭 세션) | 관련: [[feedback_fz_self_reference_blindspot]]
- 승격 목표 (트랙 A): 5 sessions 관측 후 fz-plan 스트레스테스트Q 또는 fz-review 체크 신설 판정.

### REJECTED (subsumed — 등록 안 함, 재제안 방지용 기록)
- ~~codebase-helper-3area-grep~~: 41차(Reuse-First) + fz-plan/fz-review reuse가 이미 포섭. 새 규칙 = 중복. (발화 지점 결함은 L-2로 분리 등록)
- ~~asset-rename-impact-grep~~: 17차(Pre-Gate Failure 영향 범위 사전 grep)에 포섭. 별도 규칙 불요.
- ~~delimiter-collect-then-interpose (OBS-20 H-C2)~~: **rejected-as-tradeoff**(subsumed 아님, 재제안 방지 기록) — surgical-changes 정당 트레이드오프이며 잔여 경계(genre 이하 leading sep)는 개봉예정에서 releaseDate 상시 존재로 도달 불가. 별도 규칙 불요.

## OBS-11 회고 후보 (이력 v3 마이그레이션, 관측 #1)

> 출처: 내부 마이그레이션 회고 (실수 10건 + G1~G8) + 계획 문서
> ⛔ **회고 자체 오류 정정**: 회고 §6/§9 "evidence ≥ 3 sessions"는 오류 — Track A 활성 임계 = **5 sessions** [verified: promotion-ledger.md 트랙 A 정의 + memory-guide.md:45]. ≥3은 별도 모듈 분리 자격이지 active 임계 아님. (P-track P2→P1=1 / P1→P0=2는 별도 — ledger:33-45.)
> **카운트 기준** (본 세션 채택): Track A friction 신호 = memory-guide:47 "별개 세션 관측" (L-1 #2 선례 ledger:91). Eligible (a)+(b)는 P-track 승격 전용으로 구분.
> **dedup**: 회고 G6→기존 L-3(표면 churn), G8→기존 L-2(helper reuse). 신규 = G1·G2·G3·G4·G5 → L-6~L-10. G7(툴링 문서)은 friction 신호 아님 → ledger 미등록.
> ⛔ **소급 카운트 불인정**: 회고 §5 "45차 근접"은 과거 세션 소급 아님 — L-6~L-10 전부 관측 #1부터 보수 시작.

### L-6: DTO/Entity 미러링 시 서버 실필드 검증 (G1)
- 관측 #1: OBS-11 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: 형제 DTO/Entity 미러링·필드 추가/제거 시 "이 필드를 서버가 실제 payload로 주는가?(apidog/실 응답)" 미확인. (a) 형제 필드 이식(#3 stored `id` — 서버 payload에 없음) (b) 서버 실필드 제거(#6 `lastPlayTime`).
- generalize: narrow (DTO/Entity 미러링) | 과적합 위험: 中
- 근거: [verified: README.md:19,22 #3·#6]. ⚠️ 경계: fz-code:227 "파라미터 키 불일치"는 *요청* 키 대상 — 본 신호는 *응답* DTO 필드로 구분.
- ⛔ 활성 차단: evidence 1 session → candidate. 축2(계약 지식) 성격 — 순수 friction 질문만으론 약함, apidog OAS 주입(Track3 pilot S6)이 진짜 레버.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-7: canonical 값-매핑 전량 복사 (G2)
- 관측 #1: OBS-11 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: canonical/형제의 값 매핑(코드접두→타입 등) 통째 복사 → 미확정·불일치 값을 사실화(#4 mediaType P/SB/A/L). 각 항목이 현 도메인에서 실제 발생하는지·소스 일치하는지 미검증. 규칙: 미확정 값은 default(nil/else)로 확장점만.
- generalize: narrow (값 매핑 복사) | 과적합 위험: 中 | 트리거=축1(복사 감지 코드판정)/해소=축2(값 유효성 도메인 지식) 하이브리드
- 근거: [verified: README.md:20 #4] + [verified: 템플릿 권위 편향 교훈 — 4th vector].
- ⛔ 활성 차단: evidence 1 session → candidate.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-8: 도메인 심볼에 API 버전/transport (G3)
- 관측 #1: OBS-11 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: 도메인 타입/메서드/주석에 API 버전(v2/v3) 또는 transport 세부가 박힘(#1 `WatchHistoryV3Response`·`watchedHistoryV3Page`·"v3" 주석). 버전 공존은 파라미터 오버로드로, 도메인 심볼은 무버전.
- generalize: narrow (Swift 심볼 네이밍) | 과적합 위험: 中 (grep FP — 버전 토큰 정교화)
- 근거: [verified: README.md:17 #1] + [verified: 도메인 심볼 API 버전 금지 교훈 — 신규 생성].
- ⛔ 활성 차단: evidence 1 session → candidate. 기존 fz-code "Swift Naming"(축a~e, OBS-06) + 4-N에 축(f)로 추가 — ⚠️ **evidence 카운트 분리**(축f=ASD-1794는 축a~e=ASD-1366과 이질).
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-9: DTO(계약 미러) vs Entity(사용분) 레이어 책임 (G4)
- 관측 #1: OBS-11 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: "미사용/dead" 판정을 레이어별로 구분: DTO(Decodable payload 미러)에서 서버 실필드 제거 = 갭(#6 lastPlayTime), Entity(화면 사용분)에서 미사용 필드 제거 = OK. 한 레이어 판정을 다른 레이어에 오투영.
- generalize: narrow (DTO/Entity 레이어) | 과적합 위험: 中 | 트리거=축1(레이어 식별)/해소=축2(서버 계약) 하이브리드. G1(#6)과 관점 공유.
- 근거: [verified: OBS-11 리뷰 README #6·§2 P2].
- ⛔ 활성 차단: evidence 1 session → candidate.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-10: 신규 엔드포인트 prefix/컨벤션 사전 체크 (G5)
- 관측 #1: OBS-11 | Date: 2026-07-02 | finding-source: internal (사용자 런타임 catch)
- 내용: 새 Repository 메서드 작성 시 동일 host 형제 엔드포인트의 path prefix(`/bff/app` 등) 실측 대조 없이 apidog 경로만 사용 → 실기기 404(#5). apidog 경로 ≠ 앱 게이트웨이 경로.
- generalize: narrow (신규 엔드포인트) | 과적합 위험: 中 | 축2(계약 지식). 13차 server-contract 강화.
- 근거: [verified: README.md:21 #5].
- ⛔ 활성 차단: evidence 1 session → candidate. fz-plan Phase 0c Constraint Probe 확장(Track3 pilot S6, 별도 세션).
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-2 관측 #2 (G8 — OBS-11, ⚠️ 카운트 보류)
- 관측: OBS-11 (#10 WatchLabel 자작 — 공용 `ContentLabelDTO`→`ContentLabel` 미탐색) | finding-source: internal (사용자 2턴 지적)
- ⚠️ **카운트 보류**: eligible session (a)fz-plan Phase0.5~3 형식 증거 0건 + (b)Codex quota 생략 [verified: OBS-11-work/review/self-review.md:3] → 둘 다 미확증. 관측만 등록, 5-session 카운트 미반영.
- 확장 관측: L-2 검출법=util 3영역 grep이나 G8 실패(`ContentLabelDTO` 도메인 모델)는 3영역 밖 → **사용처 기반** 보강 필요(S3). memory-guide "same failure mode → merge"로 L-2 흡수 판정.
- 근거: [verified: OBS-11 리뷰 README #10].

### L-3 관측 #2 (G6 — OBS-11, ⚠️ 카운트 보류)
- 관측: OBS-11 (#9 flip-flop: mediaType 확장→축소→재확장, lastPlayTime 유지→제거→복원) | finding-source: internal (사용자 매 flip)
- ⚠️ **카운트 보류**: L-2와 동일 사유 (eligible 미확증).
- 확장 관측: L-3 내용 문구는 이미 "UI/설계 문제" 포함(ledger:109) → ledger 편집 불요. fz-code 신호 문구("UI 속성값")만 설계원칙 flip으로 확장(S4).

### L-3 관측 #3 (OBS-20 H-X1 reversal-guard, ⚠️ 카운트 보류)
- 관측: OBS-20 (#1 구매우선순위 판정 flip: 🟡제품결정→🔴유효+구현→철회) | Date: 2026-07-20 | finding-source: external(CodeRabbit 프레임 + 사용자 통찰 catch)
- 내용: 재검토 압박("빠진 게 있다") 하에 well-grounded 판정을 뒤집음 — L-3 principle-lock("새 증거인가, 국소 재판단인가")의 **review/analysis 턴 미전파** 갭. principle-lock은 현재 fz-code:245 단독(code-stage) → 분석 턴 판정 flip 무방비. 홀 문서 §5가 G3(=H-X1)를 재발방지 top-3로 지목.
- ⚠️ **카운트 보류**: L-12와 동일 (OBS-20 eligibility 미확증). L-3 same-failure-mode(원칙 flip)라 신규 L-entry 아닌 L-3 관측 등재 — 리뷰 A:A1(H-X1이 L-3 principle-lock 스코프 갭 확정, cross+counter agree).
- ⛔ 게이트 편집 보류 (구현 diff에 없음): principle-lock을 cross-validation SOLO 게이트 요약표에 추가하는 건 대응 §reversal-guard 섹션 부재로 dangling 참조 → 신규 § 생성은 scope-creep(OQ-d). 활성 전파는 Track A 5세션 후 판정.
- 승격 목표 (Track A): 5 sessions 관측 후 principle-lock의 review/analysis 전파 판정.
- 근거: [verified: README.md:25 #9].

## OBS-19 + fz-improvement 회고 후보 (2026-07-18)

### L-11: 검증자 premise-challenge (전제 도전 지시)
- 관측 #1: OBS-19 (Date: 2026-07-15~16) | finding-source: internal (사용자 catch → 회고 E3/INC-9 — 미포함 실패 관측)
- 관측 #2: fz-improvement-strategy plan 검증 (Date: 2026-07-18) | finding-source: internal (포함 실효 관측 — 지시가 작동)
- 관측 #3: OBS-24 R8 (Date: 2026-08-10) | finding-source: internal (사용자 catch) — **발동 지점이 다름**: #1·#2는 *검증자 프롬프트*, 본 관측은 **Lead의 외부 피드백 수용 시점**. Codex가 "plan Descope 위반"(자작 초안 문서 근거)을 지적하자 Lead가 코드 근거(같은 switch 내 형제 비대칭)보다 **문서 권위를 위에 두고** 수용 → 국소 되돌리기로 결함 유발. 처방은 provenance 랭킹((i)코드/런타임 (ii)사용자·팀 승인(권한) > (iii)자작 문서 > (iv)선호)이며 `fz-code` External Feedback Gate 행 + `harness-engineering` §12 R8-A 파생규율에 반영 [[L-13]]
- 내용: adversarial/fresh-context 검증자 프롬프트에 "발견의 결론뿐 아니라 **전제**(위반 대상 문서/규칙/계획 자체의 결함 가능성)를 반증 범위에 명시 포함". 미포함 시 동종 검증자가 finder와 같은 권위 전제를 공유해 오판을 CONFIRMED(#1: plan-authority 오판 유지). 포함 시 검증자가 플랜의 핵심 전제 오진단("관측 수집 병목")을 반증(#2).
- generalize: broad (모든 검증자 프롬프트) | 과적합 위험: 低 (프롬프트 1문장 — Gate/절차 신설 아님)
- 근거: [verified: 내부 오류 분류 기록 E3 + 인시던트 INC-9] + [verified: 내부 개선 계획 검증 결과 특기]
- ⛔ 활성 차단: evidence **3 sessions** (#3 OBS-24 추가 2026-08-10) → candidate 유지. active 전환 = 트랙 A **5 sessions**.
- 승격 목표 (트랙 A): 5 sessions 관측 후 fz-review 검증 2 불능 분기(fresh-context 폴백) + cross-validation 검증자 지시에 활성 반영 판정.

### L-12: 규칙/패턴 이식 시 근거(레이아웃/정책/데이터) 태깅 (OBS-20 H-P2)
- 관측 #1: OBS-20 | Date: 2026-07-20 | finding-source: external(CodeRabbit) — 4-classify: **valid-suggestion** (CodeRabbit #2/#3 로컬라이즈·규칙 지적이 실제 유효, 사용자 통찰이 근거 축 정교화). track-C(외부 catch) 카운트 대상 분류.
- 내용: 규칙/패턴을 A화면→B화면 이식 시 "그 규칙의 근거가 레이아웃 제약/콘텐츠 정책/서버 데이터 중 무엇인가" 미검증 → 레이아웃 제약을 정책으로 오인해 이식(#1 밴드 좌상단 겹침 규칙을 인라인 헤더에 이식 후 철회). 규칙: 이식 전 근거 태그(레이아웃/정책/데이터) 명시 — 근거가 레이아웃이면 다른 레이아웃엔 미적용.
- generalize: narrow (규칙 이식) | 과적합 위험: 中 | 트리거=이식 감지(코드)/해소=근거 분류(도메인 지식) 하이브리드
- 근거: [verified: 내부 홀 인벤토리 I3·H-P2·G6("종류: 신규")]
- ⛔ 활성 차단: evidence 1 session → candidate. ⚠️ **L-7과 별개**: 상위 축(template-authority-bias)은 공유하나 해소 방식 상이(L-7=값 발생 여부 확인/default, L-12=근거 축 분류) + 홀 문서 G6가 "신규" 자체분류 → same-failure-mode 미성립으로 독립 등재. cross-link: [[L-7]]
- ⚠️ **카운트 보류** (OQ-c): OBS-20 회고 세션의 eligibility (a)fz-plan Phase0.5~3 + (b)fz-codex verify/fz-review --deep 미확증(§meta light/solo 라우팅) → L-2/L-3 관측#2 선례대로 5-session 카운트 미반영. ⚠️ **근본 모순**: 본 파일 "별개 세션 관측 카운트"(§카운트 기준) vs L-2/L-3/L-12 보류 관행이 상충 — Wave 3-1 ledger 재평가에서 reconcile 대상.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-13: post-state 일관성 (peer slot 비대칭 — OBS-24 R8)
- 관측 #1: OBS-24 | Date: 2026-08-10 | finding-source: **internal(사용자 catch)** — "상수로 해야지 거기만 하드코딩으로 하면 어떻게 해"
- 내용: fz 검증이 **diff 안**(3중 리뷰)·**diff 밖**(검증 4·4-I) 두 축뿐이고, **"편집 라인이 놓인 자리가 일관적인가"(post-state)** 를 묻는 축이 부재. 편집한 라인이 peer slot 집합(같은 switch case 절·리터럴 컬렉션·초기화 목록·같은 레벨 분기)에 속하면 형제 슬롯을 읽고 표현 방식(상수 vs 리터럴·헬퍼 vs 인라인·네이밍) 대조 필요. ⛔ **빌드·테스트가 원리적으로 침묵**(문법 정상 + 값 동일)하는 구간이라 절차로만 검출.
- 발현: `Style` enum 계산 프로퍼티 switch에서 `.poster`/`.mainBanner`는 `Metric` 상수, `.meta`만 리터럴 15/4/3. 외부 리뷰(Codex)의 "plan Descope 위반" 지적을 수용해 국소 되돌리기를 하며 발생.
- generalize: **broad** (언어·도메인 무관 — 동종 슬롯이 열거된 모든 구조) | 과적합 위험: 低~中 (체크 절차 1개, 같은 블록 Read라 비용 0)
- 근거: [verified: 내부 회고 R8 — 세션 오류 6건 중 **4건이 "대상을 격리해 보고 그것이 속한 구조를 안 봄"** 동일 뿌리] + [verified: `fz-review:224` "3중 리뷰가 모두 diff 기반" 자인 · `fz-review:240` "검증 4는 diff 안, 4-I는 diff 밖" 축 명시 → 세 번째 축 공백 확인]
- ⚠️ **표면 churn(L-3)과 별개**: L-3=*시간축*(동일 대상 2회+ 변경), L-13=*공간축*(형제 슬롯 비대칭). `memory-guide` "same failure mode → merge" 미성립. cross-link: [[L-3]]
- ⚠️ **파생 규율은 L-11과 동축**: 본 사건의 2차 원인(외부 지적의 provenance 미분류 — 자작 계획서 권위를 코드 근거 위에 둠)은 L-11(검증자가 finder와 **권위 전제** 공유 → plan-authority 오판)과 같은 축이며 **발동 지점만 다름**(L-11=검증자 프롬프트 / 본건=Lead의 피드백 수용). ⇒ provenance 랭킹은 **독립 등재하지 않고** `fz-code` External Feedback Gate 행 보강 + `harness-engineering` §12 R8-A 파생규율로 흡수. cross-link: [[L-11]]
- ⛔ 활성 차단: evidence 1 session → **candidate**. active 전환 = 트랙 A **5 sessions**.
- ⛔ **외부 채점 미이행 (§5.5 규율 2 미충족)**: 본 항목은 등재 세션에 Codex 한도 소진으로 **cross-model 채점 없이** 자기 관측만으로 기술됐다. `harness-engineering.md` §5.5 규율 2("self-preference 단독 채택 금지 — 외부 채점 병행")상 **승격 조건에 5 sessions + 외부 채점 1회를 함께 요구**한다. 개념 정본 `§12 R8-A`에도 동일 경고 병기(출처 성격이 원칙 1~7과 다름 — 외부 권위 vs 자체 관측).
- ⛔ **진단 정정 (2026-08-10, 3-렌즈 외부 검증)**: 최초 "post-state 축 부재" 판정은 **오진**. 형제 렌즈 6개 실재 [verified: `skill-authoring.md` §1 Sibling-Convention Check(**동일 실패 모드**) · `fz-review` §검증 1 "Grep → 변경 후 패턴 일관성" · `agents/impl-quality.md` "Codebase Pattern Consistency" · `codex-skills/fz-reviewer` · `evidence-collection.md` · `agents/review-direction.md`]. 정확한 진술 = **입도 부족(같은 블록 형제 단위 없음) + 소유자 미배선(`workflows/code-pair.js`가 impl-quality를 "미포함 기본값")**. ⇒ **선행 과제**: 대안 A(impl-quality 배선 복구)·B(Lead 체크리스트 1줄) vs C(현행 신설) 비용·발화율 비교 **미수행**.
- ⛔ **실효성 실측 (오탐 8/9)**: OBS-24 워크트리 peer slot 11곳 적용 → emit 9곳 중 진짜 1곳. "in-block 비용 0" 주장 **철회**(접근 수준·소유권은 소비처 결정 → 타 파일 Read + 리포 grep 필요). diff 앵커링 상속으로 **기존 비대칭 불가시**. ⇒ 4-P에 **형제 균일성 게이트 + 의미 비대칭 면제 + 소비처 의존 축 제외** 반영. 표본 소 — 일반화 금지.
- ⛔ **활성 전 필수 (§5.5 규율 1 — 회귀·반증 게이트)**: 회귀 fixture 2개 — ① 형제 3절 중 1절만 리터럴인 switch에서 **검출**(TP) ② 형제가 정당한 의미 비대칭인 블록에서 **미검출**(FP=0). **현재 oracle 0개** [L-1 선례 형식 차용].
- ⚡ 조치 (2026-08-10): `harness-engineering` §12 R8-A 신설(candidate) + 진단 정정 · `review-checks` 검증 4-P 신설 + 균일성 게이트 · `fz-code` friction-detect "peer slot 비대칭" 신호 + External Feedback Gate 행 provenance 보강 · `fz-review` 4-P 참조/체크리스트.
- 승격 목표 (트랙 A): **5 sessions 관측 + Codex(또는 이종) 교차 채점 1회 + 회귀 fixture 2개** 후 `fz-code` friction-detect "peer slot 비대칭" + `fz-review` 4-P 활성 판정. ⚠️ 그 전에 **대안 A/B 비교** 결론이 선행돼야 한다(원칙 1).
- ⚠️ **등재 절차 하자 (자기고발)**: 본 항목은 `fz-plan` 미경유 즉시 구현으로 작성됐다(`설계 답변 ≠ 구현 승인 교훈` "설계 결정 답변 ≠ 구현 승인" 위반). 사용자에게 "전체 재설계" 선택지를 제시할 때 **§5.5 규율 3("현행 유지가 정답 — 재설계 유발 금지")과 충돌한다는 사실을 고지하지 않았다.** 내용 자체의 타당성과 별개로 절차 하자를 기록에 남긴다. (세션 회고 원문 = OBS-24 워크스페이스 `fz-retrospective/R8-review/`)

### L-14: Decision-Type + Boundary (구조/경계 포크 결단 — 구 F5·F6)

- 관측 #1·#2: 구 `F5`(Decision-Type)·`F6`(Boundary-Sizing) | finding-source: **internal(사용자 catch)** — 구조/경계 포크에서 (가) 코드로 좁혀지는 엔지니어링 판단을 (나) 제품·팀 소유처럼 과잉 위임 · plan 분할 제안을 경계 권위로 답습
- 내용: 구조/경계 결단 시 유형 분류가 없어 두 방향으로 어긋난다 — (가) `read`/`grep` 으로 정답이 1개로 좁혀지는 엔지니어링 판단인데 옵션 메뉴로 위임(확신 권고+근거+"이의 없으면 진행"이 맞음) (나) 제품·디자인·팀 컨벤션 소유인데 임의 결정. 경계(PR/커밋)에서는 **plan 분할 제안 = 판단 입력이지 경계 권위가 아니다**(1커밋 = 1관심사 + 컴파일 + 1결정 trace)
- generalize: broad (언어·도메인 무관 — 모든 구조/경계 포크) | 과적합 위험: 中 (판정이 사람 해석에 의존)
- 근거: [verified: `skills/fz-plan/SKILL.md:243` Gate 0.5 체크 항목 · `modules/lead-action-default.md:16` Trigger Matrix 행 — 두 소비자가 같은 신호를 참조]
- ⛔ **활성 차단: evidence 2 sessions → candidate.** active 전환 = 트랙 A **5 sessions**
- ⛔ **본 항목 신설 사유는 새 규칙이 아니라 카운터 귀속 복구다.** 이전에는 두 소비자가 임계 권위를 본 원장으로 지목하면서 실제 관측 카운터는 **플러그인 밖 작성자 로컬 메모리**를 참조했다 — 배포본만 가진 사용자는 그 카운터를 읽을 수 없다. `guides/skill-authoring.md:393-410`(작성자 환경의 개인 메모리 내용은 배포물에 넣지 않는다) 위반이며, 권위와 카운터가 다른 경계에 있으면 관측이 발생해도 카운트가 오르지 않는다
- ⚠️ 관측 요약만 옮겼다 — 개인 경로·파일명은 옮기지 않는다(같은 규약)
- ⛔ **외부 채점 미이행**: 본 항목은 카운터 귀속 복구이며 새 판정 규칙을 도입하지 않으므로 §5.5 규율 2의 대상이 아니다. 단 5 sessions 도달 시 활성 판정에는 외부 채점 1회를 요구한다(트랙 A 준용)
- ⛔ **활성 전 필수 (§5.5 규율 1)**: 회귀 fixture 0개. 설계 = (가)/(나) 오분류 사례에서 검출되고 정당한 위임에서 미검출되는 쌍
- 승격 목표 (트랙 A): **5 sessions 관측 + 외부 채점 1회 + 회귀 fixture 1개** 후 `fz-plan` Gate 0.5 · `lead-action-default` Trigger Matrix 활성 판정

### L-1 관측 #4 (R8-C — OBS-24 figma 타이밍 갭, ⚠️ 카운트 보류)
- 관측: OBS-24 | Date: 2026-08-10 | finding-source: internal(사용자 catch)
- 내용: 원칙 H(figma 대조)는 `fz-code` **Phase 0.5 게이트**라 code 단계에만 발화 → **최초 실측이 일어나는 discover/plan 단계는 무방비**. 본 세션에서 H를 읽고 축 분류까지 수행했으나(`code/phase-0.5-detection.md`), 그 전 단계에 작성한 `figma-spec.md` v1이 이미 (a)컴포넌트 정의만 보고 인스턴스 미확인 (b)iPad 가로 `(16,12)`를 부모 체인 확인 없이 "배너 내 오프셋"으로 단정 — 2건 오류 포함.
- 처방 후보: 원칙 H **발동 시점을 "figma 노드를 조회하는 모든 단계"로 확장** (code 게이트 → 작업 성격 기반). ⚠️ 이미 `swift-pattern-detection.md` 원칙 H가 "발동 token은 plan 어휘가 아니라 **작업 성격**"이라 명시 — 즉 규칙 문구상으로는 커버되나 **fz-code Phase 0.5에만 Gate가 걸려 있어 실효 미발화**. 문구/배치 불일치.
- ⚠️ **카운트 보류**: L-1은 이미 evidence 3 sessions이며 본 관측은 *발동 시점* 갭으로 기존 내용(측정 정확도)과 축이 다름 → 별도 항목 승격 vs L-1 확장 축 편입 판정을 Wave 재평가로 이월.

## fz-findings 진입 (2026-08-24 신설)

> **신설 정당화 (DELETE/MERGE-default)**: 순수 additive 가 아니라 **끊어진 연결의 정의**다. 실측 — 본 파일과 `modules/memory-guide.md` 에서 `fz-findings` 를 찾으면 **0건**이고(positive control: 본 파일은 다른 자산을 17회 참조), findings 쪽은 본 파일을 *선례*로만 인용한다. 발견을 쌓는 큐와 승격을 판정하는 원장이 **서로의 존재를 모른 채** 각자 대기열을 쌓아 왔다. 그 결과가 findings 27건 축적 / `APPLIED.md` 0행(11일)이다.

**fz-findings 레지스트리**(세션 관측을 쌓는 사용자 로컬 대기열 — 위치는 사용자별로 다르며 플러그인 밖이다)의 엔트리가 본 원장으로 오는 경로를 정의한다.

### 판별 — 엔트리 성격별 귀속

| 성격 | 예 | 귀속 | ledger 등재 |
|---|---|---|:--:|
| **A. 작동하지 않는 코드 / 외부 상태 오염** | 공용 인자 배열이 서브커맨드에 거부됨 · fail-open 카운터 · 위임 프로세스가 팀 repo에 쓰기 | **즉시 조치** (승격 정책 비적용 — 규칙이 아니라 버그) | ⛔ 불요 |
| **B. 기존 게이트의 배선 누락** | 게이트가 N곳에서 발화하나 특정 스킬에만 미연결 | **배선 복구** (새 규칙 0개) | ⛔ 불요 |
| **C. 구현 마찰 신호** | 편집 중 감지 가능한 코드 패턴 (분기 폭증·형제 비대칭·reuse 미확인) | **트랙 A** — 5 sessions | ✅ candidate |
| **D. 외부 도구가 `/fz-review --deep` 이후 잡은 Major+** | CodeRabbit·팀원·Codex catch | **트랙 C** — 4-classify 통과분만 | ✅ 관측 |
| **E. 그 외** | 하네스 결함 · 측정 실패 · 판정 오류 · 게이트 위음성 | **트랙 D** — 2 sessions + 회귀 fixture + 외부 채점 | ✅ candidate |

### 트랙 D — 하네스 결함 (2026-08-24 신설, 사용자 결정)

E 성격(하네스 결함 · 측정 실패 · 판정 오류 · 게이트 위음성)을 받는 트랙. **findings 18건 대다수가 여기 속한다.**

| 항목 | 값 | 근거 |
|---|---|---|
| **승격 조건** | 별개 세션 **2건** + **회귀 fixture 1개** + 외부 채점 1회 | 아래 |
| 등재 단위 | `failure_class` (엔트리 ID 아님) | 같은 실패가 다른 증상으로 나타나므로 |
| 미달 처리 | findings 에 `open` 유지. 3개월 경과 시 § 미달 조치 정책 준용 | 기존 정책 재사용 |

**임계값 근거 (⚠️ 잠정 — 실측 누적 후 재조정)**

- **2세션**: 트랙 A 의 5세션은 *friction 신호*(편집 중 감지되는 코드 패턴)를 전제로 정해졌다. 하네스 결함은 성격이 다르다 — **재발 자체가 구조적 신호**이고, 같은 게이트가 두 번 뚫리면 그 게이트의 가정이 틀렸다는 뜻이다. P1→P0 의 2건과 값을 맞춰 정합성을 둔다.
- **회귀 fixture 1개**: `guides/harness-engineering.md` §5.5 규율 1 — *"자기수정 제안은 회귀 테스트·반증 게이트를 통과한 것만 채택"*. 본 원장 실측에서 **활성 차단 사유 1위가 회귀 fixture 부재(3건)** 였다. 세션 수보다 이쪽이 실질 게이트다.
  - ⭐ 실증: 2026-08-24 `scripts/check-codex-flags.sh` 가 뮤테이션 테스트에서 **자기 위양성을 2회 검출**했다(주석 오인 · awk 범위 과다). fixture 없이 "게이트가 잘 잡네"로 통과할 뻔했다.
- **외부 채점 1회**: `prompt-optimization.md` §3b H2 — self-evaluation 은 unreliable.

⛔ **이 임계값은 실측 근거가 아직 얇다.** 트랙 A 의 5세션처럼 누적 관측에서 도출된 값이 아니라 인접 트랙과의 정합성으로 정했다. **트랙 D 승격이 3건 누적되면 값을 재검토**한다 — 너무 헐거우면 게이트가 단조 증가하고(IFScale), 너무 빡빡하면 지금과 같은 적체가 재현된다.

### D-1: evidence-insufficient-confirmation (트랙 D 관측 #1·#2)

- 관측 #1: `fz-findings` **F-009** (2026-08-13, detector `external:advisor`) — `throws` **시그니처**를 전파 **동작**의 증거로 오용. 체인 5층 중 2층만 읽고 silent failure "확정" 표기
- 관측 #2: `fz-findings` **F-017** (2026-08-14, detector `user`) — `do` 블록만 읽고 `catch { adDidSkip() }` 미독 → 메커니즘을 정반대로 단정. 그 위에 C13 신설 + M1 격상으로 **사용자 결정을 오도**
- 세션: 별개 (OBS-26 discover Round 4 / 그 이전) — **2 sessions 충족**
- 값싼 검출: 실패 경로를 주장할 때 `catch` 본문 **코드 인용 강제**(요약 금지)
- ⛔ **활성 차단: 회귀 fixture 0개.** 트랙 D 조건 3개 중 세션 수만 충족했다. fixture 설계 = "catch 본문 미인용 상태로 전파 주장이 통과하는가"를 검출
- 승격 목표: 회귀 fixture 1개 + 외부 채점 1회 → active 판정

### ⛔ 트랙 D 신설 전 상태 (2026-08-24 실측 — 신설 근거)

findings 22건 전수 분류 결과 **대다수가 E**다. 현행 4트랙 어디에도 자연스럽게 들어가지 않는다:

- **트랙 A**는 *"candidate **friction 신호**"* 전용이다(본 파일 § 2-트랙 구분). 하네스 결함은 fz-code 편집 중 감지되는 마찰이 아니다.
- **트랙 B**(ledger-only → MEMORY.md)는 *"252줄 한도초과로 현재 비권장"*.
- **트랙 C**는 *"`/fz-review --deep` **이후에도**"* 를 요구한다 — 대부분의 관측이 그 단계를 거치지 않은 세션에서 나온다.
- **P-track**은 Eligible `(a)+(b)` 를 요구하고, 관측이 나온 세션은 `/fz-peer-review`·`/fz:fz`·`/fz-discover` 라 미충족이다.

→ 이 상태를 해소하려고 **트랙 D 를 신설했다**(위). ⛔ 임의로 기존 트랙에 밀어 넣지 않은 이유는 트랙마다 임계값이 그 트랙의 신호 성격을 전제로 정해졌기 때문이다 — 성격이 다른 항목을 넣으면 임계값의 근거가 사라진다.

**현재 트랙 D 후보 중 2세션 도달분**: `evidence-insufficient-confirmation` (F-009 · F-017) **1건뿐**. 나머지는 1세션이므로 관측 유지다.

### 배출 기록

A·B 로 처리한 엔트리는 findings 에서 삭제하고 `fz-findings/APPLIED.md` 에 1행을 남긴다(반영처 = 파일:섹션 + 버전 + oracle 결과). 본 원장에는 등재하지 않는다 — 승격이 아니라 수리이기 때문이다.

### D-2: coverage-unit-mismatch (트랙 D 관측 #1~#3)

- 관측 #1: `fz-findings` **F-022** — 패리티 표 항목을 "눈에 띈 것" 으로 만들어 6/6 = 100%, 이틀 뒤 7번째 값 출현. 자체 기록 2세션
- 관측 #2: **F-045** — 표본을 `cost-log.json` 존재로 잡아 3/10 만 봄. 본문이 *"F-022 와 같은 형태, 3회째"* 라 기록
- 관측 #3: **F-098** — 35절 중 5절(14%) 검사하고 산출물에 "전수 검사·총 위반 0건" 으로 적음. 사용자 지적이 오라클
- 내용(수정 전 상태): `modules/cross-validation.md` § Coverage Gate 절차 1이 *"대상 **파일** 전수 목록"* 이라 단위를 파일로 고정했다. 주장이 파일 안의 항목을 수량화하면 파일 1/1 = 100% 로 통과했다
- generalize: broad (문서·코드 무관) | 과적합 위험: 中 — ⛔ **'항목 단위' 일괄 강제는 과구조화**다(§5 원칙 3). 단위는 **전수 주장이 겨누는 대상**이어야 한다 — ⛔ 결과 건수("위반 0건")를 단위로 읽으면 violation 이 단위가 되어 같은 붕괴가 재발한다 [외부: codex — "결과 명사를 단위로 오인 가능"]
- 근거: [verified: 회귀 fixture `tests/fixtures/cross-validation/coverage-units/run.sh` 케이스 S — 파일 100% 대 항목 14%]
- ⚠️ negative 케이스 병기 — 러너의 `F file-claim 2/2` 는 발화하지 **않아야** 하는 케이스다(파일 단위 주장에는 파일 분모가 정답). 과잉 교정 방어이며 F-050(works) 과 같은 축
- ✅ **승격 완료 (2026-09-01)**: 세션 3건 + 회귀 fixture 1개 + **외부 채점 1회** 전부 충족. 반영처 = `modules/cross-validation.md` § Coverage Gate 절차 0~4 · Gate 조건 4행 · SOLO 요약 행
- **외부 채점 결과** `verdict: revise` [외부: codex]: 문제 실재 True · 제안이 해결 False · 과잉교정 위험 medium · fixture 충분 False. 원문 요지 — *"제안된 두 문장만 바꾸면 주변 계약과 모순된다"*, *"`:501,522-529,541-545` 의 요약·전략 변수·출력 형식·체크리스트를 함께 바꾸지 않으면 새 절차 1과 충돌한다"*
- ⛔ **채점자가 요구한 연동 범위를 그대로 반영**했다 — 단위 `U`(전수 주장 대상)와 실행 비용 `F`(읽을 파일 수)를 **분리**하고, 절차 2 임계값을 F 기준으로, 절차 3 출력 형식·Gate 조건·SOLO 요약을 `U` 기준으로 동기화. ⛔ 채점자 지시대로 **임계값 없는 '컨텍스트 부피' 기준은 넣지 않았다**(판정이 비결정적으로 바뀐다)
- ⛔ **채점자가 fixture 를 직접 실행하지 못했다** — 원문: *"읽기 전용 환경에서 `mktemp -d` 가 거부되어 exit 2 로 끝났으므로 제시된 PASS 를 실행 성공으로 인정하지 않았다"*. 산술만 쓰기 없이 재현해 확인했다고 명시. 러너의 로컬 PASS 는 별도 증거로 남는다

### D-3: denominator-from-same-source (트랙 D 관측 #1)

- 관측 #1: `fz-findings` **F-026** — Coverage Gate 의 분모 N 을 M 과 **같은 정규식**이 공급해 5/5 = 100% green. `^#+ *5\.[0-9]` 가 `## §5.5` 의 `§` 접두 때문에 4/8 만 잡았고 놓친 4개는 분모에서도 사라졌다
- 내용: 절차 6이 *"정규식/쿼리 불완전로 인한 가짜 교차확인도 검산 불일치로 탐지 — 본 항이 담당"* 이라 **자기 담당을 선언**하면서 처방은 *"단순 단일 카운트는 head 없는 **재실행**"* 이다. 같은 명령을 다시 돌리면 같은 값이 나오므로 붕괴가 보이지 않는다
- generalize: broad | 과적합 위험: 低 (조치가 문구 한 줄)
- 근거: [verified: 회귀 fixture 케이스 D — 재실행 100% 대 독립조달 50%]
- ⛔ 활성 차단: **세션 1건**(F-026) → 트랙 D 2세션 미달. 회귀 fixture 는 충족
- ⚠️ **D-2 와 분리한다** — 단위 불일치와 조달원 동일은 다른 기전이고, 합치면 어느 수정이 효과를 냈는지 사라진다
- ⛔ **2026-09-01 D-2 외부 채점이 본 항의 보류를 독립 확인**했다 [외부: codex]: *"`promotion-ledger.md:370-372` 는 별개 세션 2건에 도달해야 한다고 규정하지만 현재 1건이라고 기록한다. 외부 채점만으로 이 내부 승격 조건을 충족할 수 없으므로 교체 2는 아직 보류 대상이다."* → D-2 를 적용하면서 본 항 문구는 **건드리지 않았다**
- **채점자가 승격 목표를 보강**했다 — 교체 문구에 세 조건을 추가로 요구: ① *"'다른 조달원' 의 독립성 정의"* (명령만 달라도 같은 정규식·파서·후보 목록이면 같은 누락을 공유한다) ② *"`Σ부분=전체` 는 전체 N 이 부분합과 **독립적으로** 확보된 경우에만 검산"* (아니면 항등식) ③ **fail-closed** — *"독립 분모를 얻지 못하면 100% 로 통과시키지 말고 '커버리지 미검증' 으로 보고"*
- 승격 목표 (트랙 D): 별개 세션 1건 추가 후 절차 6 처방 교체("재실행" → "실패 모드가 다른 조달원, 또는 독립 조달된 전체와의 `Σ부분=전체`") + 위 ①②③ 포함. 외부 채점은 D-2 회차에서 이미 수행됨

### ⛔ 역방향 고아 — 앵커 배선 실측 (2026-08-31)

> **신설 정당화 (DELETE/MERGE-default)**: 순수 additive 가 아니라 **판별 기준의 정의**다. 실측 — 기존 § 미달 조치 정책은 *제거·보류* 방향(DEFERRED/REMOVED)만 다루고 그 반대편(앵커를 달 것인가 보류할 것인가)의 기준이 **0건**이었다(positive control: 같은 파일이 `배출 기록`·`미달 조치 정책`으로 다른 처분 축을 17회 규정한다). 판별 없이 5건을 일괄 처리하면 방어가 없는 4건에 **신규 행을 신설**하게 되고 그것은 `guides/prompt-optimization.md` § Anti-Patterns(체크리스트 행 추가 반사 금지) 대상이다.

원장에 항목이 있는데 자산에 앵커가 없어 관측이 카운트되지 못하는 항목을 실측했다. **MERGE 대상 존재 여부가 갈렸다.**

| 항목 | 자산의 기존 방어 | 조치 |
|---|---|---|
| **P2-C** | ✅ `fz-review/SKILL.md:213` retain cycle 점검 | 앵커 부착 완료 |
| D-1 | ⛔ **0건** — `catch` 본문 인용 강제 방어 없음(`modules/evidence-collection.md:117` 은 base 대조 축) | **보류** |
| L-5 | ⛔ **0건** — 상보 연산 쌍(expand↔collapse) 방어 없음 | **보류** |
| L-10 | ⛔ **0건** — path prefix 실측 대조 방어 없음 | **보류** |
| L-12 | ⛔ **0건** — 규칙 이식 근거 태깅 방어 없음(`pre-existing` origin 은 다른 축) | **보류** |

⛔ **보류 4건은 앵커를 달 자리가 없다.** 자산에 방어가 아예 없어서 역방향 고아가 된 것이고, 앵커를 만들려면 **신규 행을 신설**해야 한다 — 그것은 관측이 아니라 규칙 추가이며 `guides/prompt-optimization.md:719`(체크리스트 행 추가 반사 금지) 대상이다.

⭐ 판별 기준: **기존 방어가 있으면 앵커(배선 복구), 없으면 보류(규칙 신설은 별개 판정)**. P2-C 는 전자이고 4건은 후자다. 4건의 승격 조건은 그대로 유지되며, 관측이 발생하면 그때 "신규 행이 정당한가" 를 별도로 묻는다.

⚠️ **ID 기반 검사는 이 원장에서 위양성을 낸다** — `D-1` 이 `ASD-1234` 류 문자열에 부분 매치한다(fz-findings F-032 가 예고한 번호 충돌의 실현). 앵커 존재 확인은 **단어 경계**(`(^|[^A-Za-z0-9-])ID([^0-9]|$)`) 또는 문맥 문구로 검사한다.

---

## 미달 조치 정책

### ⛔ 재평가 실측 (2026-08-24) — 5건 중 3건은 **이미 구현돼 있었다**

관측 #0(OBS-03) 이후 eligible session 0건으로 4개월 경과한 P1-B/C/D · P2-A/B 를 재평가한 결과, **관측을 기다리는 사이 구현이 다른 경로로 먼저 진행된 항목**이 셋이다. 원장이 현실을 반영하지 못한 상태였다.

| 항목 | 구현 상태 | 근거 |
|---|:--:|---|
| **P1-B** Generator≠Evaluator Lead 독립 절차 | ✅ **구현됨** | `modules/scope-challenge.md:78` *"Phase 3.2 Lead 독립 판정"* + `skills/fz-plan/SKILL.md:64` 참조 |
| **P2-A** Q-S5 Decision Re-open Gate | ✅ **구현됨** | `modules/scope-challenge.md:104` Appendix + `:56` `parent-reopen` 배선 + `skills/fz-plan/SKILL.md` § Phase 3 절차 5 `Refactoring Mode 감지` 발동 조건 |
| **P2-B** fz-fix 자동 전환 + complexity 보정 | ✅ **구현됨** | `skills/fz-fix/SKILL.md:41 · 216 · 299`(테스트 케이스 포함) |
| **P1-C** Drift telemetry (AskUserQuestion) | ⛔ **미구현** | 본 파일 밖 참조 **0건** |
| **P1-D** Q4 재구성 + rule 11차 컴파일 가능 기준 | ⛔ **미구현** | 본 파일 밖 참조 **0건** |

⚠️ **함의**: "P-track 적체"의 절반 이상은 *집행 실패*가 아니라 **원장 갱신 누락**이었다. 승격 절차(관측 2건 → adversarial → 승인)와 실제 구현 경로가 분리돼 있어, 구현이 먼저 되어도 원장은 계속 "관측 대기"로 남는다. ⛔ 이 비대칭 자체가 재검토 대상이다 — 관측 카운트가 구현 여부를 추적하지 못하면 원장은 현실의 지표가 아니다.

⛔ 처분(구현 3건의 종결 / 미구현 2건의 DEFERRED·REMOVED)은 **사용자 결정**이다. 아래 정책이 그것을 요구한다.

### ⚠️ 관측 트리거 — 에이전트 정의 축 (2026-08-24 등록)

`agents/*.md` 13개는 2026-08-09 4중 선언 수렴(주석·registry·model-strategy·스크립트 → 스크립트 단일 정본) 이후 결함 관측이 거의 없다. findings 27건 전수 분류에서 **에이전트 정의 변경을 요구하는 건은 1건**(F-019 — 렌즈가 Bash 미보유라 재측정 불가)뿐이었다.

⛔ **관측 부재는 결함 부재의 증거가 아니다** [미검증]. 다만 현재 조치할 근거도 없으므로 트리거만 남긴다 — **에이전트 정의 결함이 별개 세션 2건 누적되면** 축을 재검토한다.

### 정책

eligible session 없이 3개월 경과 시:
- 해당 P1/P2 항목 재평가
- 사용자 문의 → DEFERRED 또는 REMOVED
- DEFERRED는 6개월 후 재평가. REMOVED는 제안 폐기.
