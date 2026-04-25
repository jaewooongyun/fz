# Sprint Contract — Codex 사전 성공 기준 (T2-B)

> Plan v3.1.3 §T2-B + harness-engineering.md 패턴 B 구현. Codex가 구현 시작 **전** "성공 기준"을 작성 → Claude 동의/수정 → 구현 진입. 사후 수정 비용 감소.

## 발동 조건

| 조건 | Sprint Contract |
|------|:-------------:|
| TEAM 모드 + 코드/계획 생산 작업 | **권장** |
| 5+ Step Plan + Cross-skill 변경 | **필수** |
| 단순 수정 (1-2 Step) | 스킵 |
| 탐색만 / 문서만 변경 | 스킵 |

## 절차 (fz-plan Phase 0.7)

> 위치: Phase 0.5 (Direction Challenge) 이후, Phase 1 (Deep Planning) 이전.

1. **Lead 컨텍스트 전달**: Phase 0.5 verdict (PROCEED/RECONSIDER) + discover 산출물 + 요구사항 → Codex (`/fz-codex` plan 또는 verify pre-mode)

2. **Codex Sprint Contract 작성** (`codex exec` skill: `architect`):
   - 출력: `{WORK_DIR}/plan/sprint-contract-codex.md` 또는 `fz:checkpoint:sprint-contract`
   - 형식: 아래 schema 참조

3. **Claude 동의/수정** (Lead):
   - **agree** → Phase 1 진입
   - **modify** → Sprint Contract 수정안 작성 + Codex re-verify 1회 (한도)
   - **reject** → Phase 0.5 재진입 (RECONSIDER 다시) 또는 사용자 에스컬레이션

4. **Phase 1 진입**: 합의된 Sprint Contract가 Plan v1의 Success Criteria로 직접 import

## Sprint Contract Schema

```yaml
sprint_id: <task-id or T1-X / T2-X>
date: YYYY-MM-DD
contract_owner: codex_architect
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
  reflection_rate_min: 80
  required_resolutions: [SC-1, SC-2]  # 부분 해결 불허 항목

scope_boundary:
  in_scope: <명시 포함>
  out_of_scope: <명시 제외, 향후 작업으로>
  deferred: <조건부 deferred 항목>
```

## Lead Decision Matrix

| Codex Sprint Contract 평가 | Lead 결정 |
|--------------------------|----------|
| 모든 SC가 measurable + binary | **agree** → Phase 1 진입 |
| SC 1개+ ambiguous (e.g., "잘 작동") | **modify** → 측정 가능하게 재작성 |
| anti_criteria 누락 (제거/리팩 작업인데) | **modify** → AC 추가 |
| out_of_scope 너무 광범위 | **modify** → scope 명시 |
| 의도 자체가 Phase 0.5 verdict와 불일치 | **reject** → Phase 0.5 재진입 |

## 자기 적용 규칙 (T2-B 자체에도)

본 modules/sprint-contract.md 작성 시점의 Sprint Contract:
- SC-1: Phase 0.7 절차 4-step 명시 (measurable: 본 파일 §"절차" 섹션 존재)
- SC-2: Schema yaml 형식 정의 (measurable: 본 파일 §"Schema" yaml block 존재)
- SC-3: Lead Decision Matrix 4 row (measurable: 본 파일 §"Decision Matrix" 표 4 행)
- AC-1: harness-engineering.md 패턴 B와 모순 (detection: 본 파일이 사후 검증 형식이면 fail)

## 학술 근거

- Anthropic Harness Engineering 패턴 B (2026-03): "Sprint Contract" — 구현 전 성공 기준 작성
- LLM-as-Judge self-preference: Codex contract 작성 → Claude (Generator) 미리 commit하면 self-preference 우회
- MoA collaborativeness (Wang 2024): 이종 모델이 서로의 출력을 보완 — Codex contract + Claude implementation의 분리

## fz 통합

- `fz-plan` Phase 0.7로 진입 (TEAM mode + 5+ Step or Cross-skill)
- `fz-codex plan` (또는 `verify pre-mode`)에서 Codex Sprint Contract 작성 호출
- `experiment-log.md §5.5`에 sprint_contract 메타 기록 (Reflection Rate 측정의 baseline)
