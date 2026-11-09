# Sprint Contract — GPT 사전 성공 기준 (T2-B)

> Plan v3.1.3 §T2-B + harness-engineering.md 패턴 B 구현. GPT가 구현 시작 **전** "성공 기준"을 작성 → Claude 동의/수정 → 구현 진입. 사후 수정 비용 감소.

## 발동 조건

**발동 = full 모드 AND (잠정 플랜이 5+ Step OR 둘 이상의 스킬 · 모듈 계열에 걸침 — Cross-skill 변경)**. 그 밖(light · 단순 수정 · 탐색만 · 문서만)은 미발동이다. 조건은 이것 하나이고 이 절이 정본이다 — fz-plan Phase 0.7 · `modules/gpt-strategy.md` § 단계 실행 판정(정책 표의 "이 표 밖" 행)이 여기를 가리킨다.

- 판정 시점 · 입력: 아래 § 절차 ④ 직전에, Phase 1 을 마친 **잠정 플랜**(fz-plan 실행 절차 4 · 4.5 · 5 · Gate 1 · 1.5 뒤)의 `steps` · `writeScope` 로 센다 — Step 수는 Workflow 가 돌아온 뒤에야 안다
- 이 조건은 단계가 **있는지**를 정하고 GPT 를 부를지는 정하지 않는다(입력인 Workflow 잠정 플랜이 full 에만 있다 — `modules/gpt-strategy.md` § 단계 실행 판정의 '모드로 GPT 단계를 돌리거나 건너뛰지 않는다' 와 부딪치지 않는다). GPT 실행은 직전 `gpt-choice.sh decide` 줄만 정한다 — `run`·`config` 면 ④ · `skip` 이면 `[GPT 미사용 — 사유]` 를 남기고 Contract 없이 fz-plan Phase 2 로 · `ask` 면 질문 → `set` → 다시 decide
- light 에는 이 단계가 없다 — 입력인 Workflow 잠정 플랜이 없다

## 절차 (fz-plan Phase 0.7 — 실행 절차 5.5 · 5.7)

> 위치: ① GPT 독립 플랜(full 기본 — fz-plan `--no-gpt-independent` 면 없다) ∥ Workflow → ② 잠정 플랜 · 방향 정지(RECONSIDER/REDIRECT · `degraded` 면 fz-plan 실행 절차 4 대로 멈춘다) → ③ 합치기 → Lead 의 Phase 1 몫(Gate 1 · 1.5) **뒤**, ⑥ Phase 2 verify ∥ verify-gates **앞**. 계획 단계의 첫 GPT 호출은 ① 이고 Contract 는 그 뒤의 호출이다. "Phase 0.7" 은 이력상 이름으로 남은 번호다.

④ **Sprint Contract** (발동 시 · 직전 decide — fz-plan 실행 절차 5.5):

1. **입력**: 잠정 플랜(Phase 1 을 마친 plan-v{N} — `steps` · `acceptanceCriteria` · `writeScope`) + `directionVerdict`(② 를 통과한 방향 판정) + 요구사항 원문 (+ discover 산출물 있으면) → GPT

2. **GPT Sprint Contract 작성** (kind `sprint-contract` — `FZ_GPT_ARTIFACT=plan FZ_WORK_DIR={WORK_DIR} scripts/gpt-call.sh sprint-contract` · architect 본문 주입 · 계약 계열 — 횟수 · 거부(exit 19)는 `modules/cross-validation.md` § 재검증 라운드 상한):
   - 출력: `{WORK_DIR}/plan/sprint-contract-gpt.md` 또는 `fz:checkpoint:sprint-contract`
   - 형식: 아래 schema 참조

3. **Claude 동의/수정** (Lead):
   - **agree** → ⑤
   - **modify** → Sprint Contract 수정안 작성 + GPT re-verify 1회 (한도 — 2 와 같은 정문 줄 · 같은 `FZ_GPT_ARTIFACT=plan` · `FZ_WORK_DIR` 라 계약 계열의 두 번째 라운드로 든다) → ⑤
   - **reject** → ② 로 돌아간다 — 거부 사유를 방향 정지 규칙(사용자 확인)에 실어 보고한다

⑤ **반영 · 재생성** (fz-plan 실행 절차 5.7 — 이 규칙은 여기 한 곳에만 적는다): 합의본을 plan 의 Success Criteria 로 import 하고, 그 결과 기준 · 범위 · 금지 기준(`success_criteria` · `scope_boundary` · `anti_criteria`) 중 하나라도 잠정 플랜과 달라지면 plan-v{N+1} · RTM · draft 원장(고친 `{WORK_DIR}/plan/steps.json` → `gate_check.py --from-plan` → `{WORK_DIR}/gates/plan.draft.md`)을 같은 합의본에서 **다시 만든다**. ⑥ verify ∥ verify-gates 는 이 스냅샷을 읽는다(fz-plan Phase 2 3.1 은 다시 만든 원장을 덮어쓰지 않는다) — 옛 plan 에 대한 판정을 새 plan 의 승인 근거로 쓰지 않는다.

## Sprint Contract Schema

```yaml
sprint_id: <task-id or T1-X / T2-X>
date: YYYY-MM-DD
contract_owner: gpt_architect
context:
  intent: <Phase 0.5 verdict 채택 의도 1줄>
  scope: <변경 대상 파일/모듈 목록>
  constraints: <반드시 보존할 invariants>

success_criteria:
  - id: SC-1
    measurable: true
    description: <단일 명제. 빌드/grep/test 등으로 binary 판정 가능>
    verification: <verify 방법 (build / grep pattern / test name)>
  - id: SC-2
    ...

anti_criteria:
  - id: AC-1
    description: <반드시 발생하면 안 되는 패턴>
    detection: <탐지 방법>

review_pass_threshold:
  reflection_rate_min: 80  # N<10이면 preliminary, gating 보류 — 참조: modules/cross-validation.md § Reflection Rate threshold
  required_resolutions: [SC-1, SC-2]  # 부분 해결 불허 항목

scope_boundary:
  in_scope: <명시 포함>
  out_of_scope: <명시 제외, 향후 작업으로>
  deferred: <조건부 deferred 항목>
```

## Lead Decision Matrix

| GPT Sprint Contract 평가 | Lead 결정 |
|--------------------------|----------|
| 모든 SC가 measurable + binary | **agree** → ⑤ 반영 · 재생성 |
| SC 1개+ ambiguous (e.g., "잘 작동") | **modify** → 측정 가능하게 재작성 |
| anti_criteria 누락 (제거/리팩 작업인데) | **modify** → AC 추가 |
| out_of_scope 너무 광범위 | **modify** → scope 명시 |
| 의도 자체가 `directionVerdict`(② 방향 판정)와 불일치 | **reject** → ② 재진입 (거부 사유로 사용자 확인) |

⛔ **방어 항목**(지금은 안 깨지지만 대비로 넣는 코드 — nil 초기화 · 가드 · 재시도)을 SC 로 올리려면 실패 경로를 함께 적는다 — 어떤 호출 순서에서 무엇이 틀어지나 + 그 순서가 실제로 도달하는 호출처 근거(파일:줄). 못 적으면 success_criteria 가 아니라 suggestion 으로 내린다(F-438 — 도달 근거 없는 방어가 Step 요구로 굳으면 구현 · 리뷰가 그것을 지키느라 비용을 쓴다). plan-lean2 `defenseFailurePath` 가 같은 규칙을 적대 렌즈 출력에 건다.

## 자기 적용 규칙 (T2-B 자체에도)

본 modules/sprint-contract.md 작성 시점의 Sprint Contract:
- SC-1: Phase 0.7 절차 ④ · ⑤ 명시 (measurable: 본 파일 §"절차" 섹션 존재)
- SC-2: Schema yaml 형식 정의 (measurable: 본 파일 §"Schema" yaml block 존재)
- SC-3: Lead Decision Matrix 4 row (measurable: 본 파일 §"Decision Matrix" 표 4 행)
- AC-1: harness-engineering.md 패턴 B와 모순 (detection: 본 파일이 사후 검증 형식이면 fail)

## 학술 근거

- Anthropic Harness Engineering 패턴 B (2026-03): "Sprint Contract" — 구현 전 성공 기준 작성
- LLM-as-Judge self-preference: GPT contract 작성 → Claude (Generator) 미리 commit하면 self-preference 우회
- MoA collaborativeness (Wang 2024): 이종 모델이 서로의 출력을 보완 — GPT contract + Claude implementation의 분리

## fz 통합

- `fz-plan` Phase 0.7 = 실행 절차 5.5 · 5.7 (발동 조건은 위 § 발동 조건 한 곳)
- GPT Sprint Contract 는 §절차 2 대로 kind `sprint-contract`(`scripts/gpt-call.sh sprint-contract` — architect)로 작성한다 — 형식은 `tests/fixtures/gpt/sprint-contract-format/run.sh` 가 본다
- `experiment-log.md §5.5`에 sprint_contract 메타 기록 (Reflection Rate 측정의 baseline)
