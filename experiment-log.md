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
