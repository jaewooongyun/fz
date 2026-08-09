# Promotion Ledger — P1/P2 조치 관측 기록

> 참조: `modules/scope-challenge.md`, ASD-1136 v2.2 Patch-4
> 목적: P1 → P0 및 P2 → P1 승격을 위한 eligible session 관측 누적
> 원칙: 학습 승격 (자동 확장) 금지. AskUserQuestion + 기록만

## 목차

- [Eligible Session 정의](#eligible-session-정의)
- [관측 기록 형식](#관측-기록-형식)
- [P1 → P0 승격 조건](#p1--p0-승격-조건)
- [P2 → P1 승격 조건](#p2--p1-승격-조건)
- [현재 관측 대상 (v2.2 기준)](#현재-관측-대상-v22-기준)
- [ASD-1674 회고 후보 (P2, 관측 #1)](#asd-1674-회고-후보-p2-관측-1)
- [ASD-1794 회고 후보 (시청내역 v3 마이그레이션, 관측 #1)](#asd-1794-회고-후보-시청내역-v3-마이그레이션-관측-1)
- [TVG-2739 + fz-improvement 회고 후보 (2026-07-18)](#tvg-2739--fz-improvement-회고-후보-2026-07-18)
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

### P1-B: Generator≠Evaluator Lead 독립 절차
- 관측 #0: ASD-1136 (원본, 3차 설계 반영)
- 승격 목표: ASD-1137+ 2건

### P1-C: Drift telemetry (AskUserQuestion)
- 관측 #0: ASD-1136 (원본)
- 승격 목표: ASD-1137+ 2건

### P1-D: Q4 재구성 + rule 11차 컴파일 가능 기준
- 관측 #0: ASD-1136 (원본)
- 승격 목표: ASD-1137+ 2건

### P2-A: Q-S5 Decision Re-open Gate
- 관측 #0: ASD-1136 (Decision-Lock 패턴 단독 관측)
- 승격 목표: ASD-1137+ 1건 (P1 승격), 이후 1건 추가 (P0 승격)

### P2-B: fz-fix 자동 전환 + complexity.md 보정
- 관측 #0: ASD-1136 (plan-impact 단독 지적)
- 승격 목표: ASD-1137+ 1건 (P1 승격)

### P2-C: general closure-capture retain cycle lens (Claude 경로) — 트랙 C
- 관측 #0: ASD-1793 (CodeRabbit Major1 — sheetRef 강한 캡처 cycle, fz-review 6-Layer 통과)
- finding-source: external(CodeRabbit) — 4-classify: valid-suggestion
- 내용: Claude 검증 경로에 일반 closure-capture retain cycle lens 부재 — `safety-audit.md`(4-J)는 동시성 전용(retain cycle 미언급), fz-review 검증 5는 listener/delegate 누수만 다룸 → 일반 "저장 프로퍼티 보유 closure가 self 강한 캡처" 미커버. Codex `codex-skills/fz-reviewer/SKILL.md:35-36`엔 일반 retain cycle lens 존재 (Claude/Codex 비대칭).
- generalize: narrow (Swift closure) | 과적합 위험: 中 (Grep 패턴 FP — 패턴 정교화 선행)
- ⛔ 활성 차단: evidence 1세션 [memory-guide:45] → candidate. safety-audit Grep 검출 lens active 전환은 트랙 A 기준 **5세션+** 누적 후 (트랙 C 정의 = 트랙 A 준용과 일치). memory-guide:44의 `≥3 sessions`는 별도 모듈 분리 자격이지 active 임계값 아님.
- 승격 목표 (트랙 C → 트랙 A): 별개 세션 추가 관측 후 safety-audit §확장 active 전환.

## ASD-1674 회고 후보 (P2, 관측 #1)

> 출처: `TVING/TVOD/ASD-1674/retrospective/session-mistakes-2026-05-29.md` (20 catches) + `fz-improvement-analysis.md` (분류)
> Eligible session 확인: ASD-1674 = fz-plan Phase 0.5~3 (plan v1~v5) + fz-codex verify 2건 → 기준 (a)+(b) 충족 [verified: plan/codex-verify-output.md, codex-verify-v3-output.md 존재]
> ⛔ **승격 차단**: 2026-06-01 세션 Codex 한도 초과 → P2→P1 조건의 "Codex verify → approved" 미충족. 관측 #1 등록까지만. cross-model 검증 PENDING.
>
> **⛔ 2-트랙 구분 (모순 해소 2026-06-01)**: L-1~L-3은 friction 신호를 보유 → 두 lifecycle이 분리된다.
> - **트랙 A (신호 활성 — ⛔ 본 항이 임계의 canonical)**: candidate friction 신호 → active 전환. 기준 = **독립 세션 5회 관측**. `modules/memory-guide.md` § Lesson Intake는 본 항을 링크하며 값을 재정의하지 않는다. Codex verify = 활성 전 *권장 품질 게이트*(복구 시).
>   - ⛔ 이전 판은 *"기준 = memory-guide line 43"* 이라 적었다 — (a) **순환**(memory-guide는 여기를 canonical로 지목) (b) 줄번호가 실제와 2~4행 어긋남. heading anchor로 교체(2026-08-09).
> - **트랙 B (메모리 승격)**: lesson → MEMORY.md 항목/별도 모듈. ⛔ MEMORY.md 252줄 한도초과로 **현재 비권장**.
> - L-1~L-3 1차 경로 = **트랙 A**. L-4(friction 신호 없음) = 트랙 B(ledger-only).
> - **트랙 C (외부 리뷰어 catch, 2026-06-18 신설)**: 외부 도구(CodeRabbit/팀원/Codex)가 fz 미탐 이슈를 발견 → ledger 관측 진입. finding-source: external. 입구 = `pipelines.md` #19 pr-comment-review 절차 4(import-to-ledger). 활성(active) 전환은 트랙 A 기준(5 sessions) 준용 + 4-classify 통과분만 카운트.

### L-1: figma 토큰 테이블 exhaustiveness (23차 강화)
- 관측 #1: ASD-1674 (catch #1,2,4,8,17,19,20 — figma 토큰 7건)
- 관측 #2: ASD-1718, 2026-06-02 (catch #1~#9 + self-catch — figma 측정 미실시·color/style-run/정렬·data>render). 트랙 A 2/5 (figma 작업 세션, memory-guide:43). active 미전환: 5세션 미달 + Codex 활성 게이트 PENDING. 근거: [verified: retrospective:9,28,53,130 + ledger:81 트랙 A 카운트 기준]. Lead/Codex 일치 여부: user_decided (cross-model PENDING — 2026-06-01 한도초과)
- 관측 #3: TVG-3554 | Date: 2026-07-29 | finding-source: internal (사용자 시각확인)
  - 관측 내용: 1:1 문의 화면 — 최초 구현 후 Figma 정정 커밋 4건. **그중 수치 정정은 3건**(`825d4e9ee` 여백·폰트 / `ccab43059` 동의항목 간격 / `33a5bf2bf` 닷 크기·색·간격), `bbdd88f29`는 **문구·노출 분기**(수치 아님) [verified: `git show bbdd88f29` — `showsContentWritingGuideNotice` 분기 추가 + 문구 텍스트 변경, spacing/size 변경 0건]
  - disposition 결과: 신호 확장 채택 (direct/composed 축 분리)
  - 근거: [verified: `TVOD/TVG-3554-work/figma-code-diff-01-사이트이용.md:98-100`]
  - Lead/Codex 일치 여부: user_decided
  - **트랙 A 3/5**. 카운트 근거: `memory-guide.md` §Evidence 출처 *"동일 failure mode가 **별개 세션**에서 관찰돼야 1 count"* + 본 파일 §"카운트 기준 (본 세션 채택)" (Eligible `(a)+(b)`는 **P-track 승격 전용** — 트랙 A friction 신호에 비적용). ⚠️ heading 앵커로 인용 — 줄번호는 본 엔트리 추가로 이동함
- ⚠️ **관측 후보 (카운트 제외)**: TVG-3406 | Date: 2026-07-30 | finding-source: **external**(QA 팀원 + CodeRabbit 2건) — 시청내역/구매내역 디자인 검수 버그 티켓(Highest), M1~M7·P1~P3 중 P3 철회·M3 3차 전환. ⛔ **트랙 C 진입 조건 3개 중 어느 것도 미증명**: ① `/fz-review --deep` **이후** 발견인가 — QA 티켓은 작업을 *시작시킨 선행 입력*이라 아님 ② actionable Major+ 근거 미기재 ③ **4-classify 분류 미실행**(`project-rule|valid-suggestion`만 카운트, `:16`). → **카운트 제외**. CodeRabbit 건만 분리해 review 실행 시점·Major+ 근거·4-classify를 명시하면 별도 트랙 C 관측으로 재등록 가능. [외부: Codex review — `fz-h11-design-coverage/review/codex-review-out.md:10038-10048`]
- 내용: figma 토큰 테이블 작성 시 변경 코드의 *모든 수치* enumerate 또는 non-exhaustive 마킹 + code 시점 per-value MCP 측정. **⊕ 확장 축 2개 (2026-08-03)**: (i) **합성 실효값** — 요소 간 렌더 간격은 단일 노드의 padding/gap이 아니라 **두 요소 경계 사이를 실제로 통과하는 gap·padding의 합**이다(⚠️ flexible spacer·절대배치·음수 간격·modifier 순서 개재 시 단순 합 불성립 → 렌더 판정. 상세 `swift-pattern-detection.md` 원칙 H) [verified: `TVOD/TVG-3554-work/figma-code-diff-01-사이트이용.md:98-100` — `root gap 12 + section padding 24 = 36`인데 코드 24] (ii) **표 값의 정확성** — 표 작성은 *완전성*만 보증하고 채워진 *값의 정확성*은 보증하지 않는다 (빈 칸 카운터가 원리적으로 미탐지하는 영역)
- generalize: **narrow** (figma/UI 전용) | 과적합 위험: 中
- 근거: [verified: index.md — 23차로 figma-tokens.md 작성됐으나 §5 갭 테이블이 간격/마진 누락 → exhaustiveness 보증 부재]
- ⚡ 조치 (2026-06-01): *code 시점* 부분(개별 수치 figma 대조)을 fz-code friction-detect에 **candidate 마찰 신호 추가** (active). *plan 시점* 부분(토큰 테이블 exhaustiveness, fz-plan §F) + broad CLAUDE.md 1줄은 **보류** (narrow + 42차 frame 한계 + 23차 중복 → Codex/사용자 판단)
- ⚡ 조치 (2026-06-02, ASD-1718 관측 #2): fz-code:277 신호에 **색/style-run/정렬 enumeration + data>render(childOrder) clause 확장** + **`figma 텍스트 미대조` candidate 신호 신설**(text-content 2세션, candidate 유지). plan 시점 Node Inventory(회고 §5-A)는 **DEFERRED 유지** — code 시점 enumeration gap은 277의 '사전 토큰 테이블 exhaustive 신뢰 → 누락 항목 답습' clause로 cover. 42차 caveat는 *구조 데이터 부재(flattened IMAGE)* 한정으로 재범위화 (구조 데이터 존재 노드값 읽기는 결정론적). 적용: TVOD/ASD-1718/fz-enhancement/plan.md (TEAM plan+review)
- ⚡ 조치 (2026-08-03, 관측 #3): ① fz-code:276의 blanket 문장("raw 노드값 그대로 적용")을 **축별 분기로 대체** — direct property는 raw 직접 / 요소 간 실효 거리는 경계 사이 gap·padding 합산(⚠️ spacer·절대배치·음수간격·modifier 순서 개재 시 단순 합 불성립 → 렌더 판정) / raw 미표현 축은 렌더 스냅샷. ② **측정 아티팩트 provenance 3필드 표준** — figma 측정 산출물 헤더에 `file key` + `node ID` + `실측일` 고정. 선례 `TVG-3554-work/figma-code-diff-01:3`은 기재, `TVG-2520-work/figma-measure-exhaustive.md:3`은 미기재 → **후속 세션이 동일 스냅샷 여부를 판정 불가**(본 세션 실측 실패로 확인). ③ **Adapter(합성값 자동 diff)는 미착수** — figma node ↔ SwiftUI expression 매핑 계약 부재 [외부: Codex verify rejected — `TVING/fz-h11-design-coverage/codex-verify-out.md:3437-3441`]. 재설계(figma calculator + mapping manifest 2단 분리) 후 재제안.
- ⚠️ **경합 가설 미해소 (2026-08-03)**: `figma-measure-exhaustive.md`(07-24 16:08)가 정정(07-29 04:10)보다 앞서 존재했으나, 두 산출물의 node 집합이 다르다(`114292…` vs file `6T8hjmMGw8xKd95NC32yKg` node `6725-121653`). **(가) 표가 stale 스펙 / (나) 합성 누락** 중 판정 불가 — provenance 부재가 원인. Figma `/design/` URL 확보 시 결판 가능. ⛔ 어느 쪽도 확정 서술 금지.
- 승격 목표 (트랙 A): figma 작업 세션 5회 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트. **현재 3/5 — 2건 남음.** ⛔ **활성 전 필수**: 회귀 fixture 1개(`parent gap 12 + child padding 24 → effective 36` 검출 / direct property는 직접 비교 / raw 미표현 축은 render-required / external 관측에 4-classify 없으면 lint 실패) — `harness-engineering.md:799` 규율1(회귀·반증 게이트 통과분만 수용). 현재 **oracle 0개** [외부: Codex review `codex-review-out.md:10091-10100`].

### L-2: fz-code 구현시점 reuse 게이트 (41차 enforcement plan→code 이동)
- 관측 #1: ASD-1674 (catch #3,6,7 — helper 중복 작성)
- 내용: fz-code 구현 *전* **공유 인프라 영역**(`CLAUDE.md ## Shared Modules`) grep 게이트 (현재 41차는 fz-plan에만 enforce)
- generalize: **broad** (모든 helper 작성) | 과적합 위험: 低 (기존 방어 이동, 신규 규칙 아님)
- 근거: [verified: fz-code/SKILL.md friction-detect에 reuse 항목 0건 — grep "reuse|코드반복|기존 helper" 결과]
- ⚡ 조치 (2026-06-01): fz-code friction-detect에 **candidate 마찰 신호 추가**. candidate *추가*엔 Codex 불요 (41차 구조적 grep 검증 + 사용자 catch #3/#7 권위). 단 candidate→active *전환*엔 Codex verify 권장 (트랙 A). ledger=메모리 승격(트랙 B) 추적, friction 신호=code 시점 발화 (별개 레이어)
- 승격 목표 (트랙 A): 5 sessions 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-3: analysis-deferred-churning (31/33/40차 복합 신규 트리거)
- 관측 #1: ASD-1674 (catch #13 — 위치 정렬 11-iteration churn)
- 내용: 단일 UI/설계 문제 *2회+ 변경* 시 self-stop + trade-off table 먼저 + 사용자 결정 후 1회 구현
- generalize: **broad (강)** (모든 반복 수정 상황) | 과적합 위험: 低
- 근거: [verified: retrospective §7-8 — 11회 변경 기록 + 사용자 "계속 바꾸지 말고 객관 분석하라"]
- ⚡ 조치 (2026-06-01): fz-code friction-detect에 **candidate 마찰 신호 추가** (memory-guide 5-session intake 대상). 사용자 catch #13 권위. broad. ⚠️ 단 churn은 31/33/40 *파생 new-trigger*(순수 enforcement-gap 아님) — 트랙 A 활성 전 Codex 재검토 권장 (#4 교정)
- 승격 목표 (트랙 A): 5 sessions 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-4: skill-procedure-default (team-core 보강)
- 관측 #1: ASD-1674 (catch #9,11 — 팀 gc 스킬 미사용 + index 갱신 누락)
- 내용: 스킬 호출 시 본문 절차 따르기 + CLAUDE.md 권장 팀 스킬(gc/pr 등) 우선
- generalize: **broad** | 과적합 위험: 中
- 근거: [verified: retrospective catch #9 — fz-commit 본문 /sc:git 미사용 + Bash git commit 직접]
- 승격 목표 (트랙 B, ledger-only — friction 신호 없음): P2→P1 = 세션 1건 + Codex verify + 사용자 승인.

### L-5: 대칭/짝 경로 동시 수정 (③ TVG-1219 메타패턴)
- 관측 #1: TVG-1219 (Date: 2026-06-27, fz 환류 세션) | finding-source: internal (사용자 catch)
- 내용: fz-code/fz-plan에서 상보적 연산 쌍(expand↔collapse, container↔preview, add↔remove, open↔close 등) 중 한쪽만 수정 시 짝 경로 누락 — friction 신호 후보. 자동 grep 불가(설계 지식 필요)라 "짝 경로 확인했나?" 체크리스트 *질문* 형태로만.
- generalize: broad (상보 연산 쌍은 SW 편재) | 과적합 위험: 中 (자동 grep 불가 → 질문 형태 한정, 과탐 피로 주의)
- 근거: [verified: TVG-1219 retrospective T1 — container↔preview 비대칭 5건+ + CodeRabbit Major D1-D3 전부 T1] + [verified: 본 세션 MEMORY.md L45 harness-holes 짝 누락 실시간 재현 1건]
- ⛔ 활성 차단: evidence 1 session [memory-guide:45] → candidate. active 전환 = 트랙 A **5 sessions** 누적 후. 같은 세션 다발(메타패턴 ~3 + 실시간 1)은 **1 count**.
- finding-source: internal (사용자 catch — 활용 갭 세션) | 관련: [[feedback_fz_self_reference_blindspot]]
- 승격 목표 (트랙 A): 5 sessions 관측 후 fz-plan 스트레스테스트Q 또는 fz-review 체크 신설 판정.

### REJECTED (subsumed — 등록 안 함, 재제안 방지용 기록)
- ~~codebase-helper-3area-grep~~: 41차(Reuse-First) + fz-plan/fz-review reuse가 이미 포섭. 새 규칙 = 중복. (발화 지점 결함은 L-2로 분리 등록)
- ~~asset-rename-impact-grep~~: 17차(Pre-Gate Failure 영향 범위 사전 grep)에 포섭. 별도 규칙 불요.
- ~~delimiter-collect-then-interpose (TVG-2906 H-C2)~~: **rejected-as-tradeoff**(subsumed 아님, 재제안 방지 기록) — surgical-changes 정당 트레이드오프이며 잔여 경계(genre 이하 leading sep)는 개봉예정에서 releaseDate 상시 존재로 도달 불가. 별도 규칙 불요.

## ASD-1794 회고 후보 (시청내역 v3 마이그레이션, 관측 #1)

> 출처: `TVING/fz-asd1794-migration-retro/README.md` (실수 10건 + G1~G8) + `plan/plan-v2.md`
> ⛔ **회고 자체 오류 정정**: 회고 §6/§9 "evidence ≥ 3 sessions"는 오류 — Track A 활성 임계 = **5 sessions** [verified: promotion-ledger.md:74 + memory-guide.md:45]. ≥3은 별도 모듈 분리 자격이지 active 임계 아님. (P-track P2→P1=1 / P1→P0=2는 별도 — ledger:33-45.)
> **카운트 기준** (본 세션 채택): Track A friction 신호 = memory-guide:47 "별개 세션 관측" (L-1 #2 선례 ledger:91). Eligible (a)+(b)는 P-track 승격 전용으로 구분.
> **dedup**: 회고 G6→기존 L-3(표면 churn), G8→기존 L-2(helper reuse). 신규 = G1·G2·G3·G4·G5 → L-6~L-10. G7(툴링 문서)은 friction 신호 아님 → ledger 미등록.
> ⛔ **소급 카운트 불인정**: 회고 §5 "45차 근접"은 과거 세션 소급 아님 — L-6~L-10 전부 관측 #1부터 보수 시작.

### L-6: DTO/Entity 미러링 시 서버 실필드 검증 (G1)
- 관측 #1: ASD-1794 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: 형제 DTO/Entity 미러링·필드 추가/제거 시 "이 필드를 서버가 실제 payload로 주는가?(apidog/실 응답)" 미확인. (a) 형제 필드 이식(#3 stored `id` — 서버 payload에 없음) (b) 서버 실필드 제거(#6 `lastPlayTime`).
- generalize: narrow (DTO/Entity 미러링) | 과적합 위험: 中
- 근거: [verified: README.md:19,22 #3·#6]. ⚠️ 경계: fz-code:227 "파라미터 키 불일치"는 *요청* 키 대상 — 본 신호는 *응답* DTO 필드로 구분.
- ⛔ 활성 차단: evidence 1 session → candidate. 축2(계약 지식) 성격 — 순수 friction 질문만으론 약함, apidog OAS 주입(Track3 pilot S6)이 진짜 레버.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-7: canonical 값-매핑 전량 복사 (G2)
- 관측 #1: ASD-1794 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: canonical/형제의 값 매핑(코드접두→타입 등) 통째 복사 → 미확정·불일치 값을 사실화(#4 mediaType P/SB/A/L). 각 항목이 현 도메인에서 실제 발생하는지·소스 일치하는지 미검증. 규칙: 미확정 값은 default(nil/else)로 확장점만.
- generalize: narrow (값 매핑 복사) | 과적합 위험: 中 | 트리거=축1(복사 감지 코드판정)/해소=축2(값 유효성 도메인 지식) 하이브리드
- 근거: [verified: README.md:20 #4] + [verified: feedback_template_authority_bias.md — 4th vector].
- ⛔ 활성 차단: evidence 1 session → candidate.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-8: 도메인 심볼에 API 버전/transport (G3)
- 관측 #1: ASD-1794 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: 도메인 타입/메서드/주석에 API 버전(v2/v3) 또는 transport 세부가 박힘(#1 `WatchHistoryV3Response`·`watchedHistoryV3Page`·"v3" 주석). 버전 공존은 파라미터 오버로드로, 도메인 심볼은 무버전.
- generalize: narrow (Swift 심볼 네이밍) | 과적합 위험: 中 (grep FP — 버전 토큰 정교화)
- 근거: [verified: README.md:17 #1] + [verified: feedback_no_api_version_in_domain_names.md — 신규 생성].
- ⛔ 활성 차단: evidence 1 session → candidate. 기존 fz-code "Swift Naming"(축a~e, ASD-1366) + 4-N에 축(f)로 추가 — ⚠️ **evidence 카운트 분리**(축f=ASD-1794는 축a~e=ASD-1366과 이질).
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-9: DTO(계약 미러) vs Entity(사용분) 레이어 책임 (G4)
- 관측 #1: ASD-1794 | Date: 2026-07-02 | finding-source: internal (사용자 catch)
- 내용: "미사용/dead" 판정을 레이어별로 구분: DTO(Decodable payload 미러)에서 서버 실필드 제거 = 갭(#6 lastPlayTime), Entity(화면 사용분)에서 미사용 필드 제거 = OK. 한 레이어 판정을 다른 레이어에 오투영.
- generalize: narrow (DTO/Entity 레이어) | 과적합 위험: 中 | 트리거=축1(레이어 식별)/해소=축2(서버 계약) 하이브리드. G1(#6)과 관점 공유.
- 근거: [verified: README.md:22 #6·§2 P2].
- ⛔ 활성 차단: evidence 1 session → candidate.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-10: 신규 엔드포인트 prefix/컨벤션 사전 체크 (G5)
- 관측 #1: ASD-1794 | Date: 2026-07-02 | finding-source: internal (사용자 런타임 catch)
- 내용: 새 Repository 메서드 작성 시 동일 host 형제 엔드포인트의 path prefix(`/bff/app` 등) 실측 대조 없이 apidog 경로만 사용 → 실기기 404(#5). apidog 경로 ≠ 앱 게이트웨이 경로.
- generalize: narrow (신규 엔드포인트) | 과적합 위험: 中 | 축2(계약 지식). 13차 server-contract 강화.
- 근거: [verified: README.md:21 #5].
- ⛔ 활성 차단: evidence 1 session → candidate. fz-plan Phase 0c Constraint Probe 확장(Track3 pilot S6, 별도 세션).
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-2 관측 #2 (G8 — ASD-1794, ⚠️ 카운트 보류)
- 관측: ASD-1794 (#10 WatchLabel 자작 — 공용 `ContentLabelDTO`→`ContentLabel` 미탐색) | finding-source: internal (사용자 2턴 지적)
- ⚠️ **카운트 보류**: eligible session (a)fz-plan Phase0.5~3 형식 증거 0건 + (b)Codex quota 생략 [verified: ASD-1794-work/review/self-review.md:3] → 둘 다 미확증. 관측만 등록, 5-session 카운트 미반영.
- 확장 관측: L-2 검출법=util 3영역 grep이나 G8 실패(`ContentLabelDTO` 도메인 모델)는 3영역 밖 → **사용처 기반** 보강 필요(S3). memory-guide "same failure mode → merge"로 L-2 흡수 판정.
- 근거: [verified: README.md:26 #10].

### L-3 관측 #2 (G6 — ASD-1794, ⚠️ 카운트 보류)
- 관측: ASD-1794 (#9 flip-flop: mediaType 확장→축소→재확장, lastPlayTime 유지→제거→복원) | finding-source: internal (사용자 매 flip)
- ⚠️ **카운트 보류**: L-2와 동일 사유 (eligible 미확증).
- 확장 관측: L-3 내용 문구는 이미 "UI/설계 문제" 포함(ledger:109) → ledger 편집 불요. fz-code 신호 문구("UI 속성값")만 설계원칙 flip으로 확장(S4).

### L-3 관측 #3 (TVG-2906 H-X1 reversal-guard, ⚠️ 카운트 보류)
- 관측: TVG-2906 (#1 구매우선순위 판정 flip: 🟡제품결정→🔴유효+구현→철회) | Date: 2026-07-20 | finding-source: external(CodeRabbit 프레임 + 사용자 통찰 catch)
- 내용: 재검토 압박("빠진 게 있다") 하에 well-grounded 판정을 뒤집음 — L-3 principle-lock("새 증거인가, 국소 재판단인가")의 **review/analysis 턴 미전파** 갭. principle-lock은 현재 fz-code:245 단독(code-stage) → 분석 턴 판정 flip 무방비. 홀 문서 §5가 G3(=H-X1)를 재발방지 top-3로 지목.
- ⚠️ **카운트 보류**: L-12와 동일 (TVG-2906 eligibility 미확증). L-3 same-failure-mode(원칙 flip)라 신규 L-entry 아닌 L-3 관측 등재 — 리뷰 A:A1(H-X1이 L-3 principle-lock 스코프 갭 확정, cross+counter agree).
- ⛔ 게이트 편집 보류 (구현 diff에 없음): principle-lock을 cross-validation SOLO 게이트 요약표에 추가하는 건 대응 §reversal-guard 섹션 부재로 dangling 참조 → 신규 § 생성은 scope-creep(OQ-d). 활성 전파는 Track A 5세션 후 판정.
- 승격 목표 (Track A): 5 sessions 관측 후 principle-lock의 review/analysis 전파 판정.
- 근거: [verified: README.md:25 #9].

## TVG-2739 + fz-improvement 회고 후보 (2026-07-18)

### L-11: 검증자 premise-challenge (전제 도전 지시)
- 관측 #1: TVG-2739 (Date: 2026-07-15~16) | finding-source: internal (사용자 catch → 회고 E3/INC-9 — 미포함 실패 관측)
- 관측 #2: fz-improvement-strategy plan 검증 (Date: 2026-07-18) | finding-source: internal (포함 실효 관측 — 지시가 작동)
- 관측 #3: TVG-4099 R8 (Date: 2026-08-10) | finding-source: internal (사용자 catch) — **발동 지점이 다름**: #1·#2는 *검증자 프롬프트*, 본 관측은 **Lead의 외부 피드백 수용 시점**. Codex가 "plan Descope 위반"(자작 초안 문서 근거)을 지적하자 Lead가 코드 근거(같은 switch 내 형제 비대칭)보다 **문서 권위를 위에 두고** 수용 → 국소 되돌리기로 결함 유발. 처방은 provenance 랭킹((i)코드/런타임 (ii)사용자·팀 승인(권한) > (iii)자작 문서 > (iv)선호)이며 `fz-code` External Feedback Gate 행 + `harness-engineering` §12 R8-A 파생규율에 반영 [[L-13]]
- 내용: adversarial/fresh-context 검증자 프롬프트에 "발견의 결론뿐 아니라 **전제**(위반 대상 문서/규칙/계획 자체의 결함 가능성)를 반증 범위에 명시 포함". 미포함 시 동종 검증자가 finder와 같은 권위 전제를 공유해 오판을 CONFIRMED(#1: plan-authority 오판 유지). 포함 시 검증자가 플랜의 핵심 전제 오진단("관측 수집 병목")을 반증(#2).
- generalize: broad (모든 검증자 프롬프트) | 과적합 위험: 低 (프롬프트 1문장 — Gate/절차 신설 아님)
- 근거: [verified: TVING/tvod/retrospective-TVG-2739/error-taxonomy.md E3 + incidents.md INC-9] + [verified: TVING/fz-improvement-strategy/plan/verify-result.md 특기]
- ⛔ 활성 차단: evidence **3 sessions** (#3 TVG-4099 추가 2026-08-10) → candidate 유지. active 전환 = 트랙 A **5 sessions**.
- 승격 목표 (트랙 A): 5 sessions 관측 후 fz-review 검증 2 불능 분기(fresh-context 폴백) + cross-validation 검증자 지시에 활성 반영 판정.

### L-12: 규칙/패턴 이식 시 근거(레이아웃/정책/데이터) 태깅 (TVG-2906 H-P2)
- 관측 #1: TVG-2906 | Date: 2026-07-20 | finding-source: external(CodeRabbit) — 4-classify: **valid-suggestion** (CodeRabbit #2/#3 로컬라이즈·규칙 지적이 실제 유효, 사용자 통찰이 근거 축 정교화). track-C(외부 catch) 카운트 대상 분류.
- 내용: 규칙/패턴을 A화면→B화면 이식 시 "그 규칙의 근거가 레이아웃 제약/콘텐츠 정책/서버 데이터 중 무엇인가" 미검증 → 레이아웃 제약을 정책으로 오인해 이식(#1 밴드 좌상단 겹침 규칙을 인라인 헤더에 이식 후 철회). 규칙: 이식 전 근거 태그(레이아웃/정책/데이터) 명시 — 근거가 레이아웃이면 다른 레이아웃엔 미적용.
- generalize: narrow (규칙 이식) | 과적합 위험: 中 | 트리거=이식 감지(코드)/해소=근거 분류(도메인 지식) 하이브리드
- 근거: [verified: TVING/tvod/retrospective-TVG-2906/fz-plugin-holes.md I3·H-P2·G6("종류: 신규")]
- ⛔ 활성 차단: evidence 1 session → candidate. ⚠️ **L-7과 별개**: 상위 축(template-authority-bias)은 공유하나 해소 방식 상이(L-7=값 발생 여부 확인/default, L-12=근거 축 분류) + 홀 문서 G6가 "신규" 자체분류 → same-failure-mode 미성립으로 독립 등재. cross-link: [[L-7]]
- ⚠️ **카운트 보류** (OQ-c): TVG-2906 회고 세션의 eligibility (a)fz-plan Phase0.5~3 + (b)fz-codex verify/fz-review --deep 미확증(§meta light/solo 라우팅) → L-2/L-3 관측#2 선례대로 5-session 카운트 미반영. ⚠️ **근본 모순**: 본 파일 "별개 세션 관측 카운트"(§카운트 기준) vs L-2/L-3/L-12 보류 관행이 상충 — Wave 3-1 ledger 재평가에서 reconcile 대상.
- 승격 목표 (Track A): 5 sessions + Codex verify.

### L-13: post-state 일관성 (peer slot 비대칭 — TVG-4099 R8)
- 관측 #1: TVG-4099 | Date: 2026-08-10 | finding-source: **internal(사용자 catch)** — "상수로 해야지 거기만 하드코딩으로 하면 어떻게 해"
- 내용: fz 검증이 **diff 안**(3중 리뷰)·**diff 밖**(검증 4·4-I) 두 축뿐이고, **"편집 라인이 놓인 자리가 일관적인가"(post-state)** 를 묻는 축이 부재. 편집한 라인이 peer slot 집합(같은 switch case 절·리터럴 컬렉션·초기화 목록·같은 레벨 분기)에 속하면 형제 슬롯을 읽고 표현 방식(상수 vs 리터럴·헬퍼 vs 인라인·네이밍) 대조 필요. ⛔ **빌드·테스트가 원리적으로 침묵**(문법 정상 + 값 동일)하는 구간이라 절차로만 검출.
- 발현: `Style` enum 계산 프로퍼티 switch에서 `.poster`/`.mainBanner`는 `Metric` 상수, `.meta`만 리터럴 15/4/3. 외부 리뷰(Codex)의 "plan Descope 위반" 지적을 수용해 국소 되돌리기를 하며 발생.
- generalize: **broad** (언어·도메인 무관 — 동종 슬롯이 열거된 모든 구조) | 과적합 위험: 低~中 (체크 절차 1개, 같은 블록 Read라 비용 0)
- 근거: [verified: TVING/tvod/fz-retrospective/R8-local-edit-blindness.md — 세션 오류 6건 중 **4건이 "대상을 격리해 보고 그것이 속한 구조를 안 봄"** 동일 뿌리] + [verified: `fz-review:224` "3중 리뷰가 모두 diff 기반" 자인 · `fz-review:240` "검증 4는 diff 안, 4-I는 diff 밖" 축 명시 → 세 번째 축 공백 확인]
- ⚠️ **표면 churn(L-3)과 별개**: L-3=*시간축*(동일 대상 2회+ 변경), L-13=*공간축*(형제 슬롯 비대칭). `memory-guide` "same failure mode → merge" 미성립. cross-link: [[L-3]]
- ⚠️ **파생 규율은 L-11과 동축**: 본 사건의 2차 원인(외부 지적의 provenance 미분류 — 자작 계획서 권위를 코드 근거 위에 둠)은 L-11(검증자가 finder와 **권위 전제** 공유 → plan-authority 오판)과 같은 축이며 **발동 지점만 다름**(L-11=검증자 프롬프트 / 본건=Lead의 피드백 수용). ⇒ provenance 랭킹은 **독립 등재하지 않고** `fz-code` External Feedback Gate 행 보강 + `harness-engineering` §12 R8-A 파생규율로 흡수. cross-link: [[L-11]]
- ⛔ 활성 차단: evidence 1 session → **candidate**. active 전환 = 트랙 A **5 sessions**.
- ⛔ **외부 채점 미이행 (§5.5 규율 2 미충족)**: 본 항목은 등재 세션에 Codex 한도 소진으로 **cross-model 채점 없이** 자기 관측만으로 기술됐다. `harness-engineering.md` §5.5 규율 2("self-preference 단독 채택 금지 — 외부 채점 병행")상 **승격 조건에 5 sessions + 외부 채점 1회를 함께 요구**한다. 개념 정본 `§12 R8-A`에도 동일 경고 병기(출처 성격이 원칙 1~7과 다름 — 외부 권위 vs 자체 관측).
- ⛔ **진단 정정 (2026-08-10, 3-렌즈 외부 검증)**: 최초 "post-state 축 부재" 판정은 **오진**. 형제 렌즈 6개 실재 [verified: `skill-authoring.md` §1 Sibling-Convention Check(**동일 실패 모드**) · `fz-review` §검증 1 "Grep → 변경 후 패턴 일관성" · `agents/impl-quality.md` "Codebase Pattern Consistency" · `codex-skills/fz-reviewer` · `evidence-collection.md` · `agents/review-direction.md`]. 정확한 진술 = **입도 부족(같은 블록 형제 단위 없음) + 소유자 미배선(`workflows/code-pair.js`가 impl-quality를 "미포함 기본값")**. ⇒ **선행 과제**: 대안 A(impl-quality 배선 복구)·B(Lead 체크리스트 1줄) vs C(현행 신설) 비용·발화율 비교 **미수행**.
- ⛔ **실효성 실측 (오탐 8/9)**: TVG-4099 워크트리 peer slot 11곳 적용 → emit 9곳 중 진짜 1곳. "in-block 비용 0" 주장 **철회**(접근 수준·소유권은 소비처 결정 → 타 파일 Read + 리포 grep 필요). diff 앵커링 상속으로 **기존 비대칭 불가시**. ⇒ 4-P에 **형제 균일성 게이트 + 의미 비대칭 면제 + 소비처 의존 축 제외** 반영. 표본 소 — 일반화 금지.
- ⛔ **활성 전 필수 (§5.5 규율 1 — 회귀·반증 게이트)**: 회귀 fixture 2개 — ① 형제 3절 중 1절만 리터럴인 switch에서 **검출**(TP) ② 형제가 정당한 의미 비대칭인 블록에서 **미검출**(FP=0). **현재 oracle 0개** [L-1 선례 형식 차용].
- ⚡ 조치 (2026-08-10): `harness-engineering` §12 R8-A 신설(candidate) + 진단 정정 · `review-checks` 검증 4-P 신설 + 균일성 게이트 · `fz-code` friction-detect "peer slot 비대칭" 신호 + External Feedback Gate 행 provenance 보강 · `fz-review` 4-P 참조/체크리스트.
- 승격 목표 (트랙 A): **5 sessions 관측 + Codex(또는 이종) 교차 채점 1회 + 회귀 fixture 2개** 후 `fz-code` friction-detect "peer slot 비대칭" + `fz-review` 4-P 활성 판정. ⚠️ 그 전에 **대안 A/B 비교** 결론이 선행돼야 한다(원칙 1).
- ⚠️ **등재 절차 하자 (자기고발)**: 본 항목은 `fz-plan` 미경유 즉시 구현으로 작성됐다(`feedback_design_answers_not_impl_approval.md` "설계 결정 답변 ≠ 구현 승인" 위반). 사용자에게 "전체 재설계" 선택지를 제시할 때 **§5.5 규율 3("현행 유지가 정답 — 재설계 유발 금지")과 충돌한다는 사실을 고지하지 않았다.** 내용 자체의 타당성과 별개로 절차 하자를 기록에 남긴다. (세션 회고 원문 = TVG-4099 워크스페이스 `fz-retrospective/R8-review/`)

### L-1 관측 #4 (R8-C — TVG-4099 figma 타이밍 갭, ⚠️ 카운트 보류)
- 관측: TVG-4099 | Date: 2026-08-10 | finding-source: internal(사용자 catch)
- 내용: 원칙 H(figma 대조)는 `fz-code` **Phase 0.5 게이트**라 code 단계에만 발화 → **최초 실측이 일어나는 discover/plan 단계는 무방비**. 본 세션에서 H를 읽고 축 분류까지 수행했으나(`code/phase-0.5-detection.md`), 그 전 단계에 작성한 `figma-spec.md` v1이 이미 (a)컴포넌트 정의만 보고 인스턴스 미확인 (b)iPad 가로 `(16,12)`를 부모 체인 확인 없이 "배너 내 오프셋"으로 단정 — 2건 오류 포함.
- 처방 후보: 원칙 H **발동 시점을 "figma 노드를 조회하는 모든 단계"로 확장** (code 게이트 → 작업 성격 기반). ⚠️ 이미 `swift-pattern-detection.md` 원칙 H가 "발동 token은 plan 어휘가 아니라 **작업 성격**"이라 명시 — 즉 규칙 문구상으로는 커버되나 **fz-code Phase 0.5에만 Gate가 걸려 있어 실효 미발화**. 문구/배치 불일치.
- ⚠️ **카운트 보류**: L-1은 이미 evidence 3 sessions이며 본 관측은 *발동 시점* 갭으로 기존 내용(측정 정확도)과 축이 다름 → 별도 항목 승격 vs L-1 확장 축 편입 판정을 Wave 재평가로 이월.

## 미달 조치 정책

eligible session 없이 3개월 경과 시:
- 해당 P1/P2 항목 재평가
- 사용자 문의 → DEFERRED 또는 REMOVED
- DEFERRED는 6개월 후 재평가. REMOVED는 제안 폐기.
