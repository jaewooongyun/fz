# Phase 0c·0.5 Direction Pre-flight 본문

> 본 모듈은 fz-plan SKILL.md Phase 0c(Constraint Probe Pre-flight) + Phase 0.5(Direction Challenge)의 절차 본문을 담는다. SKILL은 Phase 헤딩 + 발동 요약 + Gate 체크리스트만 유지 (Progressive Disclosure Level 3).
> 발동: fz-plan Phase 0c / Phase 0.5 진입 시 조건부 Read. Phase 0c 는 외부 primitive 의존 시, Phase 0.5 는 4분기 — Workflow 모드는 `workflows/plan-collaborative.js` Stage 0이 수행(escalation 시 본 모듈 Phase 0.5 절차 3 준용) / SOLO + 새 아키텍처 결정 시 필수 / discover 방향 명확 시 스킵 가능 / 단순 수정 스킵(⛔ 미러링 신규 생성은 스킵 불가 — 45차).

---

## ⛔ Phase 0c·0.5 Gate는 SKILL.md에 보존 (트리밍 비저하 원칙 — single source: `guides/prompt-optimization.md` §1 보충 3a)

본 module은 **본문(절차)만** 담는다. Gate 0c / Gate 0.5 체크리스트와 발동 요약 1줄은 `skills/fz-plan/SKILL.md`에 남는다 (실행 핵심).

---

## Phase 0c: Constraint Probe Pre-flight (31차 방어)

### 절차

1. **가정 추출**: 요구사항/discover 결과에서 primitive 의존 가정 식별
   - **가정의 3 axes 점검** (32차 방어 — Probe Coverage Gap):
     - (a) **존재 가정**: primitive가 작동하는가? (existence)
     - (b) **권한/경계 가정**: 호출 측 SKILL.md `allowed-tools` / `Bash(*)` 패턴이 호출 허용? (boundary)
     - (c) **결과 contract 가정**: 결과 형식/verdict가 호출자 해석과 일치? (contract)
   - 3 axes 모두 점검. 어느 하나라도 미검증이면 차원에서 제외 또는 explicit assumption tag.
2. **검증 분류** (각 가정 × 3 axes 별):
   - 이미 verified → `[verified: source]` 태그 보유 (코드/문서/명령어 출력)
   - 미검증 → `[미검증: 이유]` 태그 + Plan 차원에서 제외
   - probe 필요 → `/fz-discover` Phase 1.5 (Constraint Probe) 호출
   - **Codex Micro-Eval Assist (optional)**: 핵심 가정 + `[verified: source]` 부재 + primitive/contract 확인 비용 높음 시 → `/fz-gpt micro-eval "이 가정 검증"` (effort=medium, 1-shot). Lead 판단으로 호출, 자동 발동 ❌ — 새 Phase/Gate 신설 ❌ (33차 default = action 정합).
3. **probe 결과 통합**: discover 산출물에서 3 axes 모두 verified 가정만 Plan 차원에 포함

---

## Phase 0.5: Direction Challenge

### 발동 조건

| 조건 | Direction Challenge | 근거 |
|------|:------------------:|------|
| Workflow 모드 (plan-to-code, plan-only) | **Stage 0이 수행** | workflows/plan-collaborative.js Stage 0 direction (escalation 시 본 절차 3 준용) |
| SOLO 모드 + 새로운 아키텍처 결정 | **필수** | Lead가 직접 6관점 검토 |
| discover 결과에 명확한 방향 존재 | **스킵 가능** | 이미 제약 기반 방향이 결정됨 |
| 단순 수정 (기존 패턴 따르기) | **스킵** | 방향성 검토가 과잉. ⛔ 템플릿/형제 **미러링으로 신규 화면·컴포넌트를 생성**하는 작업은 단순 수정 아님 — 3축 결정 포함, 스킵 불가 (45차) |

### 절차

1. **요구사항 + 현재 아키텍처 대조**:
   - `Grep` → 기존 유사 구현 탐색
   - `mcp__serena__get_symbols_overview` → 대상 영역 구조 파악
   - CLAUDE.md `## Architecture` 기준으로 접근 방향 평가

2. **6개 관점 비판적 검토** (TEAM: review-direction, SOLO: Lead 직접):
   - Structural Fit: 현재 구조에 자연스러운가?
   - Alternative Paths: 근본적으로 다른 접근은? (**대안 최소 2개**)
   - Extensibility: N배 확장 시 유지 가능한가?
   - Existing Pattern Reuse (41차 Reuse-First): 기존 패턴을 재활용할 수 있는가? **신호 기준**: `universal*/extensible*/generic*/common*` 명명 + 5+ 사용처 + URL-agnostic API 시그니처 → 신규 작성 default 차단. **예외**: 레거시 (마지막 수정 6개월+ 또는 deprecated 태그) 시 신규 작성 정당
   - Maintenance Cost: 장기 유지보수 비용은 합리적인가?
   - Over-Engineering Risk: 현재 요구 대비 과하지 않은가?

3. **방향 판정**:
   - PROCEED → Phase 1 진입
   - RECONSIDER → 대안 비교표 + 사용자 확인 후 진입
   - REDIRECT → 대안 강력 권고 + 사용자 확인 필수

4. **⛔ 방향 판정 기록** (항상):
   - 티켓 폴더(WORK_DIR) 활성: `{WORK_DIR}/plan/direction-challenge.md`에 판정 결과 + 대안 비교 기록
   - 비-티켓 세션: `write_memory("fz:checkpoint:plan-direction", "판정: {PROCEED/RECONSIDER/REDIRECT}. 대안: {요약}. 선택근거: {1줄}")`
   형식 참조: `modules/context-artifacts.md`
