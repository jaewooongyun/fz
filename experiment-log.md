# Phase 5 Experiment Log

> 생성: 2026-04-16
> 목적: fz 하네스 실험 데이터 수집. 데이터가 충분할 때만 변경 적용.
> 근거: harness-engineering.md §7 Ablation + Anthropic H1 "가정은 스트레스 테스트 대상"

---

## 5.1 JSON Plan 실험

> 목표: plan-final.json이 Markdown 대비 plan 무결성을 개선하는지 확인
> 판단 기준: 3건 (1 기준선 + 2 실험) 후 비교

| # | 날짜 | 방식 | plan 이탈? | 기능 누락? | 비고 |
|---|------|------|:---------:|:---------:|------|
| | | Markdown (기준선) | | | |
| | | JSON (실험) | | | |
| | | JSON (실험) | | | |

---

## 5.2 에이전트 턴 수 관찰

> 목표: Supporting 에이전트의 적정 maxTurns 값 결정
> 판단 기준: 5건 수집 → 평균의 1.5배를 maxTurns로 설정

| # | 날짜 | 스킬 | 에이전트 | 턴 수 | 비고 |
|---|------|------|---------|:-----:|------|
| | | | | | |

---

## 5.3 Gate 증거 동작 관찰

> 목표: fz-plan Gate 1의 Evidence 패턴이 실제로 유용한지 확인
> 판단 기준: 5건 → Evidence 유용 비율 60%+ 이면 다른 Gate로 확대

| # | 날짜 | 스킬 | Gate | Evidence 채워짐? | 유용했나? | 비고 |
|---|------|------|------|:---------------:|:--------:|------|
| | | | | | | |

---

## 5.4 Harness Metrics 누적

> 목표: Gate별 이슈 발견 수 → Load-bearing / Neutral 분류
> 판단 기준: 10건 → 이슈 0건 Gate = Neutral 후보
> 데이터 소스 1 (Markdown table): /fz-review 완료 보고의 ## Harness Metrics 섹션
> 데이터 소스 2 (jsonl): `experiment-log-traces.jsonl` — T1-B Observability 구현으로 도입된 Agents SDK Tracing schema. `workflow_name=fz_tier1g_ensemble` 또는 `fz_review_run` group_id별 누적
> Reflection Rate threshold rule: 참조 `modules/cross-validation.md § Reflection Rate threshold` (N<10 preliminary, gating 보류)

### Codex Unique Findings 추적 (cross-model 가치 정량화)

매 cross-model verify 후 다음 schema로 기록:

```yaml
session: <session-id>
date: YYYY-MM-DD
codex_unique_findings: <int>      # Codex만 catch한 critical/major findings
claude_unique_findings: <int>     # Claude self-review만 catch한 findings  
convergent_findings: <int>        # 양측 일치 findings
total_findings: <int>             # codex_unique + claude_unique + convergent
```

> 목적: Cross-model verify 가치를 정량 evidence로 누적. 본 세션(2026-04-25 codex-utilization)에서 Codex unique 2건 (Step 1 readback, codex-strategy 충돌) 발견 — 활용 가치 정당화.

### T1-G Ensemble Sprint Metrics (2026-04-25 CP-2 Early Qualification)

Sprint Contract 4차원 (Correctness/Coverage/Severity/Actionability) 기반 Multi-angle Codex Ensemble 데이터.
jsonl 상세: `experiment-log-traces.jsonl` group_id `fz_tier1g_cp2_2026_04_25` 4 records.

| # | 날짜 | Gate | 이슈 수 | 상세 |
|---|------|------|:------:|------|
| 1 | 2026-04-25 | T1-G Sprint 1 Contract | 18 (distinct 18, shared 0) | plan meta-review, FP 0%, Coverage 100%, Actionability 100% → pass |
| 2 | 2026-04-25 | T1-G Sprint 2 Contract | 17 (distinct 17, shared 0 agg; manual 1 "6 vs Q8") | fz-codex SKILL.md verify, FP 0%, Coverage 100%, Actionability 100% → pass + fz-plugin bug 1건 교정 |
| 3 | 2026-04-25 | T1-G Sprint 3 Contract | 18 (distinct 12 after F fix, shared 2: micro-eval + reflection-rate) | cross-validation.md Cross-Model, FP 0%, Coverage 83.3%, Actionability 100% → pass + fz-plugin bug 2건 교정 |
| 4 | 2026-04-25 | T1-G Sprint 4 Contract | 19 (distinct 17, shared 1: approval) | harness-engineering.md §기둥2, FP 0%, Coverage 94.1%, Actionability 68.4% warn (H fix 후) → pass |

### 누적 지표 요약 (Sprint 1-4)

- Total findings: 72
- FP Rate: 0/72 = 0% (4 sprint 연속 Correctness pass)
- Avg Divergence/Convergence leverage: 8.3x
- fz-plugin downstream 개선: 3건 (fz-codex Q count + cross-validation consensus timestamp + Reflection N=0)
- Overall pass rate: **4/4 = 100%** ≥ CP-2 threshold 80% → **Early Qualification 달성**
- Finding 도출: A~H (8건, 7 resolved + 1 open)
- 교훈: 23차 확정 + 24-28차 후보 (5건)

### Phase A/B 진입 판정 (T1-G ensemble 근거)

- **Phase A 기준** (분기별 Gate 기여도 분류, 4 sprint 데이터):
  - Sprint Contract Correctness Gate: **Load-bearing** (0/72 FP 실증 → 신뢰할 만함)
  - Coverage Gate: **Load-bearing** (5-8x leverage 측정 → blind-spot 실효성)
  - Severity Calibration Gate: **Neutral 후보** (Sprint 1/2 vacuous, Sprint 4 shared=1 만으로 판정 제한)
  - Actionability Gate: **Load-bearing** (Sprint 4 Finding H fix trigger → 실제 content quality 영향)
- **Phase B 진입 조건**: Neutral/Overhead 후보에 대해 통제된 ablation 필요. Severity Calibration은 5 sprint 누적(Sprint 5 추가 시) 또는 future T1-G 세션 데이터 축적 시 재판정.

### 다음 T1-G 세션 시 누적 위치

- jsonl: `experiment-log-traces.jsonl`에 새 record append (group_id별 구분)
- Markdown: 본 섹션 표에 row 추가 (날짜 + Gate + 이슈 수 + 상세)
- 5 sprint 누적 후 본 섹션에 Phase B ablation 판단 기록

---

## 판단 이력

> 데이터 충분 시 여기에 판단 + 적용 기록

| 날짜 | Step | 판단 | 근거 데이터 | 적용 여부 |
|------|------|------|-----------|:---------:|
| | | | | |

---

## §5.5 Agent Teams Tracing (T1-B)

> Reflection Rate 기준선 + 에이전트 턴 수 자동 수집. T1-B-1 schema 신설 (2026-04-25).
> Hook auto-collection: `~/.claude/hooks/agent-teams.sh` (T1-B-2).
> Reasoning Persistence (`previous_response_id`): Codex CLI 0.124.0 미지원 → Tier 2 drop.

### Schema (YAML, jq/yq 파싱 가능)

```yaml
- team_id: <unique>
  started: ISO8601
  ended: ISO8601
  task: T1-X / Sprint N / Tier1.0-X
  duration_minutes: N
  agents:
    - name: Lead
      model: opus | sonnet
      created: ISO8601
      completed: ISO8601
      turns: N
  reflection_rate:
    issues_total: N
    issues_resolved: N
    rate_pct: NN | null   # null = vacuous (N=0)
  metadata: {}            # task-specific (self_dogfood, sprint_id, etc)
```

### Sample entry (self-dogfood, 본 schema 신설 자체)

```yaml
- team_id: T1-B-1-self
  started: 2026-04-25
  ended: 2026-04-25
  task: T1-B-1 §5.5 Tracing schema 신설
  duration_minutes: 5
  agents:
    - name: Lead
      model: opus
      turns: 1
  reflection_rate:
    issues_total: 0
    issues_resolved: 0
    rate_pct: null  # vacuous
  metadata:
    self_dogfood: true
    triggered_by: "T1-B Implementation"
```

### Auto-collection (T1-B-2)

`~/.claude/hooks.json` 등록 → `~/.claude/hooks/agent-teams.sh` 실행:
- 이벤트: `TaskCreated` / `TaskCompleted` / `TeammateIdle` / `TeamDeleted`
- per-team buffer: `~/.claude/agent-teams-buffer/{team_id}.yaml`
- `TeamDeleted` 시 buffer를 본 §5.5에 append

### Validation

- `bash -n ~/.claude/hooks/agent-teams.sh` — syntax check
- `jq . ~/.claude/hooks.json` — hooks.json valid
- Hook event 실재 (TaskCreated 등): 미검증 (32차 axis c) — 첫 TeamCreate 시 동작 검증

### 32차 dogfooding 1차 효과 (Probe Coverage Gap 방어)

- T1-B Phase 0c probe 결과: T1-B-3 (`previous_response_id`) DROP — Codex CLI 미지원 단독 catch
- Patch 사전 회피: 2건 (T1-B-3 drop + §5.x 신설 명확화)
- Hook event contract (axis c) 미검증 → 동작 검증 시점 명시

<!-- Auto-appended by ~/.claude/hooks/agent-teams.sh on 2026-04-25T12:01:00Z -->
- team_id: test-dummy-1
  started: 2026-04-25T12:00:00Z
  agents:
    - name: test-agent
      model: sonnet
      created: 2026-04-25T12:00:00Z
  ended: 2026-04-25T12:01:00Z

### Reflection Rate Entries (T1-D 사이클, 2026-04-25)

```yaml
- team_id: T1-D-verify-v1
  date: 2026-04-25
  task: T1-D Plan v1 Codex verify (직접 호출 설계)
  agents:
    - name: Lead
      model: opus
      turns: 1
    - name: codex-architect
      model: gpt-5.5
      turns: 1
      effort: high
  reflection_rate:
    issues_total: 5
    issues_resolved_strict: 2     # P0#1 allowed-tools, P2 measurement criteria
    issues_resolved_partial: 3    # P0#2 false PASS, P1#1 LOOP regression, P1#2 cross-skill drift
    rate_pct_strict: 40           # RESOLVED only / total
    rate_pct_lenient: 70          # RESOLVED + (PARTIAL × 0.5) / total
  metadata:
    verdict: needs_revision
    follow_up: "Plan v2 (위임형 재설계)"
    self_dogfood: false

- team_id: T1-D-verify-v2
  date: 2026-04-25
  task: T1-D Plan v2 Codex verify (위임형 재설계 후)
  agents:
    - name: Lead
      model: opus
      turns: 1
    - name: codex-architect
      model: gpt-5.5
      turns: 1
      effort: high
  reflection_rate:
    issues_total: 4               # new issues in v2 (P0×1, P1×2, P2×1)
    issues_resolved: 4            # all fixed via split implementation (T1-D1/D2/D3)
    rate_pct: 100
  metadata:
    verdict: needs_revision
    follow_up: "T1-D 분할 (D2 fz-codex contract + D3 execution-modes + D1 fz-fix --codex)"
    escalation: "21차 18-한도 적용 → C 에스컬레이션 → 분할 결정"
    self_dogfood: false

- team_id: T1-D-self-dogfood
  date: 2026-04-25
  task: T1-D commit fe2ee8a Codex check (자기 검증)
  agents:
    - name: Lead
      model: opus
      turns: 1
    - name: codex-reviewer
      model: gpt-5.5
      turns: 1
      effort: high
  reflection_rate:
    issues_total: 2               # grep PCRE + severity enum mismatch
    issues_resolved: 2            # both fixed in cfcaf91
    rate_pct: 100
  metadata:
    verdict: needs_revision
    follow_up: "cfcaf91 immediate patch (33차 implementation default 적용)"
    self_dogfood: true
    cross_model_solo_catch: 1     # 15차 패턴 — Codex 단독 발견
```

### 누적 통계 (3 entries)

| 측정 | 값 | 해석 |
|------|---:|------|
| Total verify/check 사이클 | 3 | T1-D 단일 작업 사이클 |
| Total issues raised | 11 | 5 + 4 + 2 |
| Issues resolved (strict, RESOLVED only) | 8 | 2 + 4 + 2 |
| Issues resolved (lenient, PARTIAL × 0.5) | 9.5 | (2 + 1.5) + 4 + 2 |
| **Reflection Rate (strict)** | **73%** | 8/11 |
| **Reflection Rate (lenient)** | **86%** | 9.5/11 |

### CP-3 진단

- **Threshold**: Rate ≥ 80% (TEAM review, Plan v3.1.3 §CP-3) — **gating는 N≥10에서만** (참조: `modules/cross-validation.md § Reflection Rate threshold`)
- **Strict 73%**: BELOW threshold (PARTIAL을 미반영으로 셈 시)
- **Lenient 86%**: ABOVE threshold (PARTIAL을 부분 반영으로 셈 시)
- **Sample size**: 3 / 5 (CP-3는 5건+ 누적 필요)
- **결론**: **3건만으로는 CP-3 미충족**. 2건 추가 데이터 필요. Tier 2 작업의 자연 verify cycle (T2-A discover/verify, T2-B Sprint Contract verify)에서 누적 → CP-3 재판정.

### 32차 Probe Coverage 효과 (별도 측정)

| 지표 | 값 |
|------|---:|
| Phase 0c probe 회피 patch (T1-B-3 drop + §5.x 신설 명확화) | 2 |
| Phase 0c probe 회피 patch (T1-D primitive enumerate) | (verify v1에서 catch됐으므로 0) |
| 32차 dogfooding 1차 효과 | 2건 사전 회피 |

---

## §5.6 Plugin Trigger Activation (Phase A 효과 측정)

> 신설: 2026-04-26 (fz-ios-utilization Plan v2.2 M-2)
> 목표: SwiftUI Expert + Swift Concurrency 플러그인의 자동 감지 트리거 + v3.6 역방향 트리거가 실제 iOS 코드 세션에서 발동되는 빈도 + 효과 측정
> 판단 기준: 10건 누적 → trigger pattern 효과성 검토 (Load-bearing/Neutral/Overhead 분류)
> 데이터 소스: /fz-code, /fz-fix, /fz-review 세션 종료 시 수동 또는 hook 자동 기록

### Schema (per session, YAML)

```yaml
- session_id: <ASD-xxxx 또는 NOTASK-yyyymmdd>
  date: YYYY-MM-DD
  pipeline: <fz-code | fz-fix | fz-review | fz-plan | ...>
  swiftui_triggers_detected: <int>      # 감지된 SwiftUI 패턴 수 (@State, @Observable, body: some View 등)
  concurrency_triggers_detected: <int>  # 감지된 Concurrency 패턴 수 (@MainActor, async, Sendable 등)
  reverse_triggers_fired: <int>         # v3.6 역방향 트리거 발동 수 (싱글톤+var, 콜백 스레드 모호 등)
  plugin_consulted_swiftui: <bool>      # swiftui-expert 플러그인 실제 참조 여부 (의식적 참조)
  plugin_consulted_concurrency: <bool>  # swift-concurrency 플러그인 실제 참조 여부
  context7_called_count: <int>          # context7 query-docs 호출 수 (API 검증용)
  issues_caught_by_plugin: <int>        # 플러그인 참조로 발견한 안티패턴/이슈 수
  issues_missed_without_plugin: <int>   # 플러그인 미참조로 놓쳤을 이슈 수 (사후 분석/리뷰에서 확인)
  metadata: {}                          # task-specific (e.g., layer-affected, severity-distribution)
```

### Auto-collection (선택)

본 섹션은 **수동 기록 우선**. 자동화는 §5.5 hook 패턴 확장 시 검토 (`~/.claude/hooks/agent-teams.sh` 변형으로 plugin trigger 빈도 capture 가능).

### 누적 데이터 (시작 시점: 2026-04-26)

| # | 날짜 | 세션 | swiftui/concurrency triggers | reverse fired | plugin consulted (UI/Cnc) | context7 calls | 이슈 catch | 비고 |
|---|------|------|:-:|:-:|:-:|:-:|:-:|------|
| | | | | | | | | |

### Load-bearing Test 절차 (F9 — 원칙별 ablation)

> 출처: `guides/harness-engineering.md` §3 원칙 1 (Q1 load-bearing test) + §5 원칙 2 (모델 변경 시 하네스 재검토).
> 목표: Phase 1.5 P1/P2/P3 + Phase 0.5 D/E/F/G 원칙 7개 각각의 기여도 측정 → Load-bearing / Neutral / Overhead 분류.

**측정 schema (per principle, per session)**:
```yaml
- session_id: <ASD-xxxx 또는 NOTASK-yyyymmdd>
  date: YYYY-MM-DD
  pipeline: <fz-plan | fz-code>
  principle_evaluated: <P1 | P2 | P3 | D | E | F | G>
  trigger_token_matched: <int>          # 해당 원칙의 token 매칭 빈도
  issue_caught_with_principle: <int>    # 원칙 활성화로 발견한 안티패턴 수
  issue_missed_without_principle: <int> # 원칙 비활성화 시 놓친 안티패턴 수 (counterfactual, 사후 추정)
  catch_rate: <float>                   # issue_caught / trigger_token_matched
  ablation_classification: <load-bearing | neutral | overhead | pending>
```

**Ablation 절차**:
1. 5+ 세션 누적 후 원칙별 catch_rate 산출
2. catch_rate > 30% → Load-bearing (강화 대상)
3. catch_rate < 5% AND trigger_token_matched > 10 → Neutral 후보
4. issue_missed > issue_caught → Overhead (정의 재검토)
5. Phase B 진입 시 Neutral 후보를 통제된 ablation으로 검증 (해당 원칙 비활성 세션 vs 활성 세션 비교)

### Phase B 진입 조건

10건 누적 후 다음 분류 기준 적용:

| 분류 | 기준 | 행동 |
|------|------|------|
| **Load-bearing** | catch rate > 30% (issues_caught / total_triggers_detected) | 강화 대상 — plugin 참조 가이드 보강 |
| **Neutral 후보** | catch rate < 5% AND plugin_consulted = false 다수 | ablation 검토 — 트리거 패턴 활성화 비용 대비 효과 미흡 |
| **Overhead** | issues_missed > issues_caught | 트리거 정의 재검토 — 패턴 매칭 정확도 개선 |

### 31/32/33차 메타 패턴 측정 (반성 기반 메타 인덱스)

각 세션의 reverse_triggers_fired 값은 v3.6 역방향 트리거의 실증 효과 데이터. 본 §5.6 누적이 plugin-refs.md "역방향 감지 트리거" 섹션의 Phase A 효과 측정 (uncertainty-verification.md `## Phase A/B 진입 판정` 모듈) sink로 작동.

5건 누적 후: reverse_triggers_fired AVG < 1 → 역방향 트리거 정의 재검토. AVG > 3 → 트리거 강화 (추가 패턴 발굴).
