# Phase 5 Experiment Log

> 생성: 2026-04-16
> 목적: fz 하네스 실험 데이터 수집. 데이터가 충분할 때만 변경 적용.
> 근거: harness-engineering.md §7 Ablation + Anthropic H1 "가정은 스트레스 테스트 대상"

---

## Phase B 시작점 정의 (cross-experiment 통합 표)

> 모든 §5.X 실험의 Phase B 진입 N 값을 단일 표로 명시. UC-17 fz v4.7.0 통일.
> 본 표 + cross-validation.md `Reflection Rate threshold` 가 Phase B 정의의 single source.

| 실험 | Phase B 진입 N | 표현 (본문에서 사용) | 출처 모듈 정합 |
|------|:---:|---|---|
| §5.1 JSON Plan 무결성 | 3건 (1 기준선 + 2 실험) | "3건 누적" | (자체 정의) |
| §5.2 에이전트 턴 수 | 5건 | "5 sessions 누적" | (자체 정의) |
| §5.3 Gate 증거 동작 | 5건 + 60% catch rate | "5건 누적, 60%+" | (자체 정의) |
| §5.4 Harness Metrics (Severity Calibration) | 5 sprint | "5 sprint 누적" | (자체 정의) |
| §5.5 Agent Teams Tracing (Reflection Rate) | **N≥10** | "N≥10 (preliminary if N<10)" | **cross-validation.md `§ Reflection Rate threshold`** |
| §5.6 Plugin Trigger Activation | 10건 | "10건 누적" | (자체 정의) |
| §5.7 Workflow Tracing (TEAM→Workflow) | 5건 전수 (discover) / 3건 (search·review) | "null률 0% + 완주율 100% + fallback 0건" — **확산/롤백 게이트 (Phase B 진입 N 아님)** | **experiment-log.md §5.7 확산 판정 임계 (freeze)** |
| §5.8 Fable 5 효율 배선 측정 큐 | ①effort **철회(frontmatter 제거)** / ②fresh-context N=5 / ③절차밀도 A/B쌍 1 / ④synthesis **동결(fable 제재 — 해제 시 재개)** | "§5.8 사전등록 임계 참조" | **experiment-log.md §5.8 사전등록 임계 (freeze)** |

**§5.5 특별 사항**: cross-validation.md "N<10이면 preliminary, gating 보류"를 single source로 사용. UC-1 (Reflection Rate CP-3) gating은 N≥10에서만 발화.

**§5.7 특별 사항**: §5.7의 N은 Phase B 진입 semantics가 아니라 TEAM→Workflow **확산/롤백 게이트**다 — 본 표에는 가시성 목적으로만 등재 (canonical은 §5.7 freeze 블록, 이중 정의 아님).

**fz-review/SKILL.md "Phase B1/B2 후 활성"**: §5.6 (Phase A 효과 측정) → Phase B (Load-bearing Test) → B1/B2 ablation 단계 abstraction. 본 표 §5.6 row 참조.

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
| 1 | 2026-06-11 | fz-plan (SOLO --deep) | Gate 1 Exhaustive Impact Scan | ✅ 앵커 4/4 grep + pre-state 0 hit + 내장 self-test 비파괴 | ✅ F4 앵커 이중 후보를 Tuning History 자체 게이트 실측으로 해소 → counter approve | ASD-1802 fz gap fix plan-v2 |

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
    rate_pct: NN | null            # null = vacuous (N=0). LEGACY (호환성 유지)
    headline_rate_pct: NN | null   # UC-5 (v4.8.0): 이종 모델 only (canonical exclusion). DP3v2 정합
    weighted_rate_pct: NN | null   # UC-5 (v4.8.0): 동종 모델 0.5 가중 포함 (auxiliary 별도 보고)
  cost_proxy:                       # UC-6 (v4.8.0) cost_blast 측정. DP3v2-4 deterministic formula:
    opus_turns: <int>               # = sum(agents[].turns where agents[].model == "opus")
    opus_minutes: <float>            # = sum(agents[].completed - agents[].created where agents[].model == "opus") in minutes
    total_agent_turns: <int>        # = sum(agents[].turns)  — baseline 비교용
    total_agent_minutes: <float>    # = sum(agents[].completed - agents[].created) in minutes
    # missing timestamp 처리: agents[].created 또는 agents[].completed null 시 해당 agent skip + metadata.skipped_agents 기록
  metadata: {}            # task-specific (self_dogfood, sprint_id, skipped_agents, etc)
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
  # UC-9 (v4.7.1): swift-anti-pattern-preblock P1/P2/P3 원칙별 catch_rate
  catch_rate_p1: <float>                # P1 SwiftUI 결정 — caught/(caught+missed). 임계: >30% 강화 / <5% 비활성화
  catch_rate_p2: <float>                # P2 Concurrency isolation 범위
  catch_rate_p3: <float>                # P3 패턴 변환 보존
  metadata: {}                          # task-specific (e.g., layer-affected, severity-distribution)
```

> P1/P2/P3 catch_rate 정의의 single source: `modules/swift-anti-pattern-preblock.md` § Catch Rate Threshold (UC-9, v4.7.1).

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

## §5.7 Workflow Tracing (TEAM→Workflow pilot, fz-discover)

> Lead가 invoke마다 수동 append (hook 비의존 — §5.5 hook은 TaskCreated/TeammateIdle/TeamDeleted 의존, Workflow 모드 미발생).
> 계획: TVING 워크스페이스 `fz-teams-workflow-migration/plan/plan-final.md` (계획 표기 §5.8은 실측 §5.6 다음 번호인 §5.7로 교정).

### 확산 판정 임계 (사전 등록 — 변경 금지, 확증 편향 방어)

- **신뢰성 (확산 판정 유일 기준)**: fz-discover 5건 전수 null률 0% + 완주율 100% + fallback 0건. 미달 → rollback 트리거.
- **다양성 (--deep fan-out 유지/제거 판정 전용)**: **정의 (b) — mergedFrom 원천 렌즈 경로 수 > default lean 최종 경로 수** (탐색 폭 기준. 2026-06-05 사용자 확정 — invoke #4가 발견한 양의적 문구의 *명확화*이며 임계 이동 아님. 보조 질적 확인: lean 미발견 신규 경로 계열 ≥1). 미충족 → --deep도 lean 회귀 (확산 판정엔 불사용).
  - 소급 판정 (정의 확정 시점): #4 = 12>6 **충족** (+D계열 신규) / #5 = 15>6 **충족** (+E계열 신규) → --deep fan-out 유지 방향, 5건 시점 최종
- **확산 3게이트**: G1 패턴별 적합성 (adversarial 성공 ≠ 타 패턴 자동 확산 — collaborative/pair-programming 개별 검토) / G2 Landscape 품질 관찰 (비정량 기록, 게이트 아님) / G3 TEAM 폴백 일몰 명시 결정.

> 스킬별 분리 테이블 (2026-06-05 확산 Wave 1): 칼럼·임계가 스킬마다 다름 — discover 표·임계는 무변경 보존 (사전등록 분모 보호).

### fz-discover (adversarial) — 기록 형식 (invoke당 1행)

| # | date | mode | agentCalls | nullCount | rounds | fallback | wall-clock | G2 품질 관찰 (경로수/evidence/openQ) |
|---|------|------|-----------|-----------|--------|----------|-----------|--------------------------------------|

### fz-discover 누적 데이터 (시작: 2026-06-05)

| # | date | mode | agentCalls | nullCount | rounds | fallback | wall-clock | G2 품질 관찰 (경로수/evidence/openQ) |
|---|------|------|-----------|-----------|--------|----------|-----------|--------------------------------------|
| 1 | 2026-06-05 | lean | 5 | 0 | 2 | 0 | 446s | ⛔ **품질 실패** — agentType 시스템 프롬프트의 ASD 컨텍스트 로딩이 args 압도, 무관한 TVOD 작업 폴더 anchoring (기계 지표 전부 통과 — G2 게이트 존재 이유 실증). OVERRIDE 강화로 교정 → #2 재실행 |
| 2 | 2026-06-05 | lean | 5 | 0 | 2 | 0 | 411s | ⛔ **품질 실패 2** — 근본 원인 격리: scriptPath 호출 시 args가 JSON 문자열 도착(probe wf_89418b73 실측, typeof=string) → args.problem=undefined → 에이전트 입력 부재 상태로 무관 폴더(peer-review-4182) 탐색. r1은 OVERRIDE 강화 효과로 undefined를 정직 보고. 수정: 스크립트 방어 파싱(JSON.parse) + fail-fast 가드 → #3 재실행 |
| 3 | 2026-06-05 | lean | 5 | 0 | 2 | 0 | 492s | ✅ **첫 clean 통과** — 정주제 6경로 landscape, §5.7 기존재 실측 발견 + Phase B 표 semantics 충돌 발견 + traces.jsonl 선례 반박(L69). evidence [verified Lxx] 인용 준수, 결론 미산출 ✓. G2: 경로 6/evidence 충실/openQ 5건 실질 |
| 4 | 2026-06-05 | **deep** | 9 | 0 | 2 | 0 | 404s | ✅ clean — 렌즈 12 원천→4 병합그룹(mergedFrom 추적 정상), lean 미발견 D경로 발굴 + false prereq 실측 반박 2건. **다양성 지표 판정 보류**: 사전등록 문구 "merged 고유 경로 수 > default 단일 생성 경로 수"가 양의적 — (a) 병합그룹 4 vs lean 최종 6 → 미충족 / (b) 원천 렌즈경로 12 vs lean 6 → 충족. 지표 정의 모호 자체가 calibration 발견 — 5건 시점 판정 전 정의 확정 필요. wall-clock은 deep(404s) < lean#3(492s) — 병렬 효과 |
| 5 | 2026-06-05 | **deep** | 10 | 0 | 2 | 0 | 482s | ✅ clean — **merge 수정 검증**: MergedPathSetSchema(maxItems 12) 적용 후 병합 5그룹 (이전 상한 4 돌파 — 스키마 탈락 강제 해소 실증). 신규: 입력 경로 오류를 Grep 실측으로 자가 교정 + freeze 블록 canonical 식별. ts 제거 계약 정상 동작 |

### fz-search (cross-verify) — Wave 1 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주 + fallback 0건. G2-search 품질 관찰 = 등급 분포 합리성 / FP 제거 실증 / 누락 보완 실증.

| # | date | agentCalls | nullCount | stages | fallback | wall-clock | G2-search (등급분포/FP제거/보완) |
|---|------|-----------|-----------|--------|----------|-----------|----------------------------------|
| 1 | 2026-06-05 | 5 | 0 | 3 | 0 | 264s | ✅ clean — discover-journal.md 참조처 27건 (★★★18/★★9/★0), ground truth 2/2 적중(fz-plan L191·fz-code L222), 라인 정밀 + 맥락 note 충실. 전환 직후 검증 invoke (실사용 표본 아님 — 임계 3건 중 1) |

### fz-review (live-review) — Wave 1 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주 + fallback 0건. G2-review 품질 관찰 = finding 유효성 / counter 조정 실증 / severity 근거 충실.

| # | date | agentCalls | nullCount | stages | fallback | wall-clock | G2-review (finding/counter/severity) |
|---|------|-----------|-----------|--------|----------|-----------|--------------------------------------|
| 1 | 2026-06-05 | 5 | 0 | 3 | 0 | 661s | ✅ clean — Wave 1 변경분 self-review: findings 11(실질 8, critical/major 0), okAreas 18, counter가 3건 추가 발견(C-1 okArea도전 소실/C-2 하드코딩/C-3 id중복=실버그) — DA 가치 실증. 8건 전부 즉시 수정 반영. 전환 직후 검증 invoke (임계 3건 중 1) |
| 2 | 2026-06-11 | 5 | 0 | 3 | 0 | 728s | ✅ clean — ASD-1889 미러 리팩토링 리뷰 (실사용): findings 8 (critical/major 0), counter가 XQ:Q-1 refute(현 브랜치에 없는 중복을 ASD-1802 워크트리 cross-worktree 혼동으로 주장 — FP 실증 기각) + okArea 1건 반박(미러 비교 기준 라벨 명확화) + C-1/C-2 추가 발견. cross가 [verified] 실측 인용 충실. Lead 판정: 코드 변경 0건(전부 pre-existing/미러 의도), 후속 후보 2건. 임계 3건 중 2 |
| 3 | 2026-06-11 | 5 | 0 | 3 | 0 | 715s | ✅ clean — **plan 문서 리뷰 (비-diff 신규 사용례)**: fz-gap-fix-plan-final(v3.1) 사용자 3축(가이드 준수/과적합/일반화). findings 14 (critical 0/major 2/minor 12, FP 0), counter가 okArea 4건 도전(완화 편향 1건 적발) + C-1~C-3 추가. 전 finding [verified] 인용. Lead 처분: 15건(Lead 자체 발견 L1 §12 oracle 포함) → plan v3.2 반영 13 + 의도 유지·O7 기록 2. Codex 차단 대체 한계(RC4) 명시. **임계 3건 전수 달성 — null 0%·완주 100%·fallback 0** |
| 4 | 2026-06-11 | 5 | 0 | 3 | 0 | 920s | ✅ clean — gap fix **적용 diff 리뷰** (8파일 179줄+메모리 3): findings 11 (critical/major 0, FP 0) — 9건은 O1·O7 기록 완비/의도 결정 재확인, 1건 즉시 반영(Gate 0.5 SOLO 맥락 명시), counter가 okArea refute 1건("§12 정확히 일치" 과장 — full-path 미검증 사실 재명시) + 리뷰어 evidence 라인 오류 1건(C-1) 적발. okAreas 25 — F1~F4·G1·G3 발화 체인 정적 도달 전부 확인. 4-F 7/7 기계 PASS |
| 5 | 2026-06-12 | 5 | 0 | 3 | 0 | 724s | ✅ clean — **plan 문서 리뷰** (전수 주장 오판 방어 plan-v1, #3 선례 동형·적용 전): findings 18 (critical 0/major 8/minor 10, FP 0) — 적용 전 리뷰가 plan 구조 결함 2건 포착(:436 트리거 요청 어휘 잔존=RC1 미해소 / 에이전트 행동 규율 행 T8=dead rule 12곳 재생산 위험). counter가 okArea 2건 refute(S7 verify 과잉 교체 미탐지 / 줄번호 신뢰 과대) + C-1~C-3. Lead 처분: 18건 전원 수용 → plan-v2 + 적용 반영. 실사용 표본 |
| 6 | 2026-06-13 | 5 | 0 | 3 | 0 | 743s | ✅ clean — **Fable 5 대응(v4.14.0 Part A) diff 리뷰** (28 path, 실사용·Fable 세션): findings 7 (critical 0/major 2/minor 5, FP 0) — 두 major가 동일 실패 클래스(사후 사용자 피드백 반영 시 승계 문서 미동기화: effort 4스킬 3곳 stale + ④ 활성/비활성 3곳 이진 상충). counter 전건 uphold + finding 정확도 보완 노트 2건([verified: Read/Grep] 인용 충실 — grounded progress OVERRIDE 첫 적용 invoke). okAreas 13 + okArea 도전 4건 전부 uphold. Lead 처분: 7건 전원 수용 즉시 반영 → Reflection 7/7 grep 검증 100%. Codex validate 불능 — 결정론적 grep 대체 |

### fz-plan (collaborative) — Wave 2 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주(5/5 또는 direction_escalation 정상 반환) + fallback 0건. G2-plan 품질 관찰 = direction 판정 합리성 / CC 교차 신규 발견 / steps verify 존재 / §Y writeScope가 §X 자동 복사 아님 / Lead 이관 책임(stress-test·RTM) 실수행 여부.

| # | date | agentCalls | nullCount | stages | fallback | wall-clock | G2-plan (direction/CC/verify/§Y/Lead회귀) |
|---|------|-----------|-----------|--------|----------|-----------|--------------------------------------------|
| 1 | 2026-06-05 | 9 | 0 | 5 | 0 | 1101s | ✅ clean — Wave 3 계획 생산(dogfooding). G2 5축 전부 PASS: direction PROCEED 1-call(dead-call 제거 경로 첫 작동)/CC 신규 발견 2건 S8 반영/verify 9·9/§Y 6≠§X 15 rationale 분리/Lead 회귀(stress-test Q1-Q6+RTM 12행) 실수행. 특기: S0 책임 재배분을 자가 도출 + canonical 충돌을 OQ1 에스컬레이션 표시(임의 판단 금지 자발 준수). 전환 직후 검증 invoke (임계 3건 중 1) |
| 2 | 2026-06-12 | 9 | 0 | 5 | 0 | 1327s | ✅ clean — 전수 주장 오판 재발 방지 plan(자가 개선 dogfooding 2, G1 배선 후 첫 실사용). G2 5축 PASS: direction PROCEED+`directionAlternatives` 3건 실반환(G1 full-path 확인 — A채택/B·C 부분 흡수)/렌즈·CC 실측 신규 발견 4건(fz SKILL :136 사문화·Q-COVERAGE 이중 진입점·12에이전트 T8 dead rule·memory-guide :30 충돌)→S3/S5/S7/S8 신설/verify 11·11/§Y 19 rationale 분리/Lead 회귀(Q1-Q6+RTM 11+peer issue 실측 해소 1건) 실수행. 임계 3건 중 2 |
| 3 | 2026-06-12 | 9 | 0 | 5 | 0 | 1300s | ✅ clean — Fable 5 고도화 플랜(v4.14.0 대상, Fable 세션 첫 invoke). G2 5축 PASS: direction PROCEED+directionAlternatives 3건(A채택/C S6흡수)/렌즈·CC 신규 발견 3건(STALE 6→4 정정·R8 검증지시 86→12 over-count 정정·S7 비용 baseline 3-state 의무)/verify 8 Steps 전부/§Y 13 rationale 분리/Lead 회귀(Q1-Q6+RTM 12) 실수행. 특기: Phase 2 fresh-context 검증(Codex quota 폴백)이 M1(S3 직교 폴백 혼동 — Workflow 산출 결함)+L2(docs/releases Glob 오측, "[verified]" 표기 포함) 추가 발견 → plan-v2 정정. Workflow [verified] 태그 신뢰 한계 관찰(16차 레이어 재현). 임계 3건 중 3 |

> 2026-06-11 **G1 배선 적용** (반환 `directionAlternatives` + 헤더 계약 주석 동기화, ASD-1802 gap fix): §12 oracle — ①래핑 node --check PASS ②스모크 invoke 1회 = fail-fast 경로 정상(`mode:'fallback'`, 0 agent, 3ms — 위 누적 테이블 분모 **비포함**, 스모크는 실사용 아님) ③full-path 필드 실반환은 다음 실사용 invoke에서 확인.

### fz-code (pair-programming full) — Wave 3 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3세션 전수 — changeset 적용 성공률 100%(의사코드/생략 0건) + 빌드 통과(Lead 검증) + fallback 0. **행 단위 = 세션당 1행 (N-Step 누적 집계 — invoke당 N행 발산 방지)**. G2-code = changeset exact syntax 충실도 / review 이슈 유효성 / residualIssues 처리.

| # | date | steps | invokes | agentCalls(계) | nullCount | fallback | stage2-null steps | G2-code |
|---|------|-------|---------|----------------|-----------|----------|-------------------|---------|
| 1 | 2026-06-05 | 1 (SYNC-1) | 1 | 2 | 0 | 0 | 0 | ✅ clean — review pass→Stage3 생략(조건부 분기 첫 작동, 2-call). changeset 4 edits 전부 oldAnchor 정확(에이전트 자가 grep 유일성 검증) + compound 주석 부분 갱신 정밀. Lead 적용 4/4 + buildExpectation 검증 통과. 전환 직후 검증 세션 (임계 3세션 중 1) |

### fz-fix (pair-programming light) — Wave 3 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3세션 전수 동일. complexity 계약(Lead 재평가) 작동 여부를 G2에 포함.

| # | date | steps | invokes | agentCalls(계) | nullCount | fallback | complexity 분기 | G2-fix |
|---|------|-------|---------|----------------|-----------|----------|------------------|--------|
| 1 | 2026-06-05 | 1 (FIX-1) | 1 | 1 | 0 | 0 | c=1→review 생략 (정상) | ✅ clean — 1-call, oldAnchor 정확(Lead 의심을 실측이 기각 — 에이전트가 실파일 Read 증거), 적용+검증 통과. 전환 직후 검증 세션 (임계 3세션 중 1) |

---

## §5.8 Fable 5 효율 배선 측정 큐 (시작: 2026-06-12)

> 출처: `~/dev/TVING/fz-fable-enhancement/plan/plan-final.md` S4 — 배선=가설/측정=검증 (31/35차). **사전등록 임계 변경 금지** (확증편향 방어).
> freeze 범위 주석 (§5.7 동형): §5.7 freeze는 §5.7 데이터행+확산임계만 대상 — 본 §5.8 신설은 별도 허용. §5.8 ② N=5 = 표준 Phase B 진입 / ①effort·④synthesis는 **2026-06-14 fable 제재 롤백으로 측정 중단** (①철회: frontmatter 4건 제거 → 측정 대상 소멸 / ④동결: pilot opus 롤백, 제재 해제 시 재개 — ①④ 헤더 참조. **canonical 상태 = 각 헤더**, CHANGELOG·release 노트는 cross-ref).
> **공통 필드 의무**: 각 행에 `session_model`(fable|opus) + `env_subagent_model`(CLAUDE_CODE_SUBAGENT_MODEL 설정 유무) 기록 — effort 효과의 3-way 혼합(세션 모델×서브에이전트 모델×effort) 방지.

### ① effort frontmatter 효과 — **철회 (2026-06-14 fable 제재 롤백)**

> **철회 사유 (2026-06-14)**: 사용자 effort 운용 = 세션 레벨 max(기본)/ultracode 확정 → 4스킬 `effort: xhigh` frontmatter 제거(B1). 측정 대상(frontmatter 효과)이 소멸하여 철회 — 동결 아님(fable 복귀와 무관, 세션 운용 방식이라 frontmatter 재도입 없음). 아래는 철회 전 설계 — 사료 보존.

> `[미검증: 스킬 frontmatter→Workflow agent() 전파 여부 — 공식 docs 미기술]` → 첫 측정에서 적용 범위(스킬 Lead 단계 한정 vs Workflow 단계 포함) 판별 기록.
> 임계 (사전등록): N=5 누적 — xhigh의 G2 품질이 high 대비 동등+ AND 토큰 증가 ≤30% → 유지. 미달 → frontmatter 제거 (배선 롤백).
> **비교군(high baseline) 수집 설계** (2026-06-12 probe 발견 결함 보수 — 임계 불변, 방법 보완): 4스킬 전부 xhigh 고정이라 자연 high 데이터 생성 불가 → **retro-baseline** = §5.7 누적표의 배선 전(2026-06-12 이전) 행들(fz-plan #1-2·fz-review·fz-discover — effort 기본 high 시절)의 wall-clock/G2 관찰을 비교군으로 사용. [fable probe 발견: "high 대비 측정의 분모 수집 설계 부재"]

| # | date | skill | session_model | env_subagent_model | effort 적용 범위 확인 | 토큰(상대) | G2 품질 |
|---|------|-------|---------------|--------------------|---------------------|-----------|---------|

### ② fresh-context 검증자 catch (S3 배선: fz-review 검증 2 불능 분기)

> 임계 (사전등록): N=5 누적 — Lead self-review 미발견 이슈 평균 ≥1건/세션 → 유지 (Codex 회복 후 병행 검토). 0건 수렴 → Codex 회복 시 원경로 단독 복귀.
> 배선 전 실증 3건 (2026-06-12, 본 세션 — 분모 비포함 참고): 가이드 검증 23건 / plan-v1 M1+L2 (Workflow [verified] 오측 포함) / plan-v3 M1+L2 (승계 Step 교차 모순).

| # | date | 대상 | session_model | catch (M/L) | self-review 미발견분 | 비고 |
|---|------|------|---------------|-------------|---------------------|------|

### ③ 절차 밀도(de-prescription) A/B — R8 확산 게이트 (fz-search 384줄 pilot)

> 방법: 작업 폴더에 슬림 변형(절차 지시 축약 — **Gate·Few-shot·⛔ 가드레일 보존**) → 동일 쿼리 스킬 파일 swap 2-invoke → G2 + 토큰 비교.
> 임계 (사전등록): 품질 비저하(G2 동등) AND 토큰 ≥10% 절감 → R8 확산 게이트 오픈 (fz-review·fz-plan 절차 슬림, 별도 사이클). 미달 → 현행 유지 + Fable de-prescription 가설("too prescriptive → degrade")의 fz 반례로 기록.

| # | date | variant | session_model | 토큰 | G2 품질 | 판정 |
|---|------|---------|---------------|------|---------|------|

### ④ synthesis fable vs opus — **동결 (2026-06-14 fable 제재: pilot opus 롤백, 제재 해제 시 재개)**

> **동결 사유 (2026-06-14)**: Fable 5가 미국 제재로 외국인 사용 금지 → 세션 모델 opus 4.8 운용. synthesis pilot은 `model: 'opus'`로 롤백(search-cross-verify.js:166 — `model` 생략 시 agent 정의 `model: sonnet` 강등 위험이라 explicit opus). 측정 동결 — **사전등록 임계/baseline 설계 보존**, 제재 해제 + fable 세션 재개 시 `'opus'→'fable'` 1줄 전환으로 측정 재개. 아래는 동결 전 활성 근거 — 사료.
> 활성 근거(사료): 사용자 발화 "생각이 깊어야 되는 부분은 plan, review, discover, search 이런 부분은 fable5로 하면 좋고" + A/B probe 정상 작동 확인. pilot 1차 자동 적용 권한 거부(06-12) → "반영해줘" 인가 적용(06-13) → 06-14 제재로 롤백.
> 선행 baseline 3-state: Lead=opus/syn=opus(구) · Lead=fable/syn=opus(직전) · Lead=fable/syn=fable(pilot). "승격=비용 2배" 단정은 baseline 실측 후.
> 임계 (사전등록): pilot N=3 — fable synthesis의 G2 품질이 opus 대비 우위 신호(교차 병합 누락↓ 또는 FP 판정 정확도↑) ≥2/3 AND wall-clock 비악화 → plan-collaborative integrate 확산 검토. 미달 → opus 롤백.

| # | date | 단계 | syn model | 토큰 | 품질 관찰 | 비고 |
|---|------|------|-----------|------|----------|------|
| 0 | 2026-06-12 | (probe — workflows 외 A/B) | fable vs opus | [미검증: per-agent 토큰 미분리] | **fable 우위 관찰**: 동일 synthesis 과제(§5.8 우선순위 판정, 동일 입력 2파일)에서 양측 동일 결론 도달하나 fable이 의존 관계 6 vs 4 + opus 미발견 결함 1건(① high baseline 분모 수집 불가) 추가 발견. opus 고유 발견(② 분모 오염 경고)도 유효 — 상호 보완 관찰. null/refusal 폴백 0 | wf_6de8db1d (2 agents, 190s). pilot 적용 근거 |
