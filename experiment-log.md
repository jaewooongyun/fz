# Phase 5 Experiment Log

> 생성: 2026-04-16
> 목적: fz 하네스 실험 데이터 수집. 데이터가 충분할 때만 변경 적용.
> 근거: harness-engineering.md §7 Ablation + Anthropic H1 "가정은 스트레스 테스트 대상"

> ⛔ **이 파일은 프로토콜만 싣는다** — 임계 · 스키마 · 기록 형식 · 빈 템플릿 · 절차. 측정 기록(실행 행 · 표본 항목 · 누적 통계 · 판정 요약 · 동결 행 · 결과 행 · 기준선 이동 기록 · 판단 이력)은 저장소 밖 로그 `${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md` 의 같은 절에 쓴다 — 두 파일의 절 번호와 제목은 같다.
> ⛔ **목적지가 저장소 안으로 풀리면 쓰지 않는다** — `FZ_RUN_STATE` 가 플러그인 저장소 안의 경로로 풀리면 기록하지 않고 그 사실을 알린다. 추적 파일에 실행 행이 다시 들어오면 `scripts/check_ab_protocol.py` 가 실패한다(health-check).

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
> ⏸️ **DEFERRED (2026-07-18 사용자 결정)**: 측정 대상이 의도적 A/B 실험 필요(자연 발생 없음)라 0행. 2027-01 재평가 + Codex 복구 후 재확인. H5(JSON feature list) 연동 근거 보존 — 삭제 아님.

| # | 날짜 | 방식 | plan 이탈? | 기능 누락? | 비고 |
|---|------|------|:---------:|:---------:|------|
| | | Markdown (기준선) | | | |
| | | JSON (실험) | | | |
| | | JSON (실험) | | | |

---

## 5.2 에이전트 턴 수 관찰

> 목표: Supporting 에이전트의 적정 maxTurns 값 결정
> 판단 기준: 5건 수집 → 평균의 1.5배를 maxTurns로 설정
> 🗑️ **Wave 4 릴리스 시 REMOVED 예정 (2026-07-18 사용자 결정)**: 측정 대상(TEAM Supporting maxTurns)이 TEAM 일몰(Workflow one-shot 전환)로 소멸 — 릴리스 전까지 동결, 릴리스 시 본 섹션 삭제.

| # | 날짜 | 스킬 | 에이전트 | 턴 수 | 비고 |
|---|------|------|---------|:-----:|------|
| | | | | | |

---

## 5.3 Gate 증거 동작 관찰

> 목표: fz-plan Gate 1의 Evidence 패턴이 실제로 유용한지 확인
> 판단 기준: 5건 → Evidence 유용 비율 60%+ 이면 다른 Gate로 확대
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | 날짜 | 스킬 | Gate | Evidence 채워짐? | 유용했나? | 비고 |
|---|------|------|------|:---------------:|:--------:|------|
| | | | | | | |

---

## 5.4 Harness Metrics 누적

> 목표: Gate별 이슈 발견 수 → Load-bearing / Neutral 분류
> 판단 기준: 10건 → 이슈 0건 Gate = Neutral 후보
> 데이터 소스 1 (Markdown table): /fz-review 완료 보고의 ## Harness Metrics 섹션
> 데이터 소스 2 (jsonl): `${FZ_RUN_STATE:-~/.fz/runs}/experiment-log-traces.jsonl` — T1-B Observability 구현으로 도입된 Agents SDK Tracing schema. `workflow_name=fz_tier1g_ensemble` 또는 `fz_review_run` group_id별 누적
> Reflection Rate threshold rule: 참조 `modules/cross-validation.md § Reflection Rate threshold` (N<10 preliminary, gating 보류)

### Codex Unique Findings 추적 (cross-model 가치 정량화)

매 cross-model verify 후 다음 schema로 기록:

```yaml
session: <session-id>
date: YYYY-MM-DD
gpt_unique_findings: <int>        # GPT만 catch한 critical/major findings
claude_unique_findings: <int>     # Claude self-review만 catch한 findings  
convergent_findings: <int>        # 양측 일치 findings
total_findings: <int>             # gpt_unique + claude_unique + convergent
```

> 목적: Cross-model verify 가치를 정량 evidence로 누적.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### T1-G Ensemble Sprint Metrics (2026-04-25 CP-2 Early Qualification)

Sprint Contract 4차원 (Correctness/Coverage/Severity/Actionability) 기반 Multi-angle Codex Ensemble 데이터.

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | 날짜 | Gate | 이슈 수 | 상세 |
|---|------|------|:------:|------|

### 누적 지표 요약 (Sprint 1-4)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### Phase A/B 진입 판정 (T1-G ensemble 근거)

- **Phase B 진입 조건**: Neutral/Overhead 후보에 대해 통제된 ablation 필요.

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### 다음 T1-G 세션 시 누적 위치

- jsonl: `${FZ_RUN_STATE:-~/.fz/runs}/experiment-log-traces.jsonl`에 새 record append (group_id별 구분)
- Markdown: 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 `### T1-G Ensemble Sprint Metrics` 절 표에 row 추가 (날짜 + Gate + 이슈 수 + 상세)
- 5 sprint 누적 후 저장소 밖 로그의 `## 5.4` 절에 Phase B ablation 판단 기록
- ⛔ 목적지가 플러그인 저장소 안으로 풀리면(`FZ_RUN_STATE` 가 저장소 안 경로) 쓰지 않고 알린다

---

## 판단 이력

> 데이터 충분 시 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 판단 + 적용 기록

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

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### Auto-collection (T1-B-2)

`~/.claude/hooks.json` 등록 → `~/.claude/hooks/agent-teams.sh` 실행:
- 이벤트: `TaskCreated` / `TaskCompleted` / `TeammateIdle` / `TeamDeleted`
- per-team buffer: `~/.claude/agent-teams-buffer/{team_id}.yaml`
- `TeamDeleted` 시 buffer를 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 §5.5에 append — 목적지가 플러그인 저장소 안이면 쓰지 않는다

### Validation

- `bash -n ~/.claude/hooks/agent-teams.sh` — syntax check
- `jq . ~/.claude/hooks.json` — hooks.json valid
- Hook event 실재 (TaskCreated 등): 미검증 (32차 axis c) — 첫 TeamCreate 시 동작 검증

### 32차 dogfooding 1차 효과 (Probe Coverage Gap 방어)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### Reflection Rate Entries (T1-D 사이클, 2026-04-25)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### 누적 통계 (3 entries)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### CP-3 진단

- **Threshold**: Rate ≥ 80% (TEAM review, Plan v3.1.3 §CP-3) — **gating는 N≥10에서만** (참조: `modules/cross-validation.md § Reflection Rate threshold`)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### 32차 Probe Coverage 효과 (별도 측정)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

---

## §5.6 Plugin Trigger Activation (Phase A 효과 측정)

> 신설: 2026-04-26 (fz-ios-utilization Plan v2.2 M-2)
> 목표: SwiftUI Expert + Swift Concurrency 플러그인의 자동 감지 트리거 + v3.6 역방향 트리거가 실제 iOS 코드 세션에서 발동되는 빈도 + 효과 측정
> 판단 기준: 10건 누적 → trigger pattern 효과성 검토 (Load-bearing/Neutral/Overhead 분류)
> 데이터 소스: /fz-code, /fz-fix, /fz-review 세션 종료 시 수동 또는 hook 자동 기록
> ✅ **유지 + 바인딩 (2026-07-18 사용자 결정)**: 유일한 '집행 갭' 큐(iOS 세션은 발생하나 기록 미실행) — fz-code·fz-review 지표 기록 절차에 append 상기 추가(Wave 1-2). 2~3세션 후에도 0행이면 DEFERRED 재판정.

### Schema (per session, YAML)

```yaml
- session_id: <PRJ-xxxx 또는 NOTASK-yyyymmdd>
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
> **컴포넌트 slice 분리 추적** (2026-07-09 추가): 집계 지표가 가리는 국소 회귀 감지를 위해 게이트별 catch rate·워크플로별 fallback/null rate를 세션 행에 분리 기록 (원천: workflow `metrics` — 기수집) [외부: harness-paper §4-D, Layer-Isolated 2606.11686 — 원 논문 미대조].

**측정 schema (per principle, per session)**:
```yaml
- session_id: <PRJ-xxxx 또는 NOTASK-yyyymmdd>
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
> 계획: TEAM→Workflow 전환 계획의 plan-final (계획 표기 §5.8은 실측 §5.6 다음 번호인 §5.7로 교정).

### 확산 판정 임계 (사전 등록 — 변경 금지, 확증 편향 방어)

- **신뢰성 (확산 판정 유일 기준)**: fz-discover 5건 전수 null률 0% + 완주율 100% + fallback 0건. 미달 → rollback 트리거.
- **다양성 (--deep fan-out 유지/제거 판정 전용)**: **정의 (b) — mergedFrom 원천 렌즈 경로 수 > default lean 최종 경로 수** (탐색 폭 기준. 2026-06-05 사용자 확정 — invoke #4가 발견한 양의적 문구의 *명확화*이며 임계 이동 아님. 보조 질적 확인: lean 미발견 신규 경로 계열 ≥1). 미충족 → --deep도 lean 회귀 (확산 판정엔 불사용).
- **확산 3게이트**: G1 패턴별 적합성 (adversarial 성공 ≠ 타 패턴 자동 확산 — collaborative/pair-programming 개별 검토) / G2 Landscape 품질 관찰 (비정량 기록, 게이트 아님) / G3 TEAM 폴백 일몰 명시 결정.

> 스킬별 분리 테이블 (2026-06-05 확산 Wave 1): 칼럼·임계가 스킬마다 다름 — discover 표·임계는 무변경 보존 (사전등록 분모 보호).
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

### fz-discover (adversarial) — 기록 형식 (invoke당 1행)

| # | date | mode | agentCalls | nullCount | rounds | fallback | wall-clock | G2 품질 관찰 (경로수/evidence/openQ) |
|---|------|------|-----------|-----------|--------|----------|-----------|--------------------------------------|

### fz-discover 누적 데이터 (시작: 2026-06-05)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | mode | agentCalls | nullCount | rounds | fallback | wall-clock | G2 품질 관찰 (경로수/evidence/openQ) |
|---|------|------|-----------|-----------|--------|----------|-----------|--------------------------------------|

### fz-search (cross-verify) — Wave 1 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주 + fallback 0건. G2-search 품질 관찰 = 등급 분포 합리성 / FP 제거 실증 / 누락 보완 실증.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | agentCalls | nullCount | stages | fallback | wall-clock | G2-search (등급분포/FP제거/보완) |
|---|------|-----------|-----------|--------|----------|-----------|----------------------------------|

### fz-review (live-review) — Wave 1 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주 + fallback 0건. G2-review 품질 관찰 = finding 유효성 / counter 조정 실증 / severity 근거 충실.
> `stage2: 'conditional'` 로 돈 행은 stages 칸에 `3(S2 생략)` 처럼 적는다 — 반환에 `stage2Skipped` 가 있으면 트리거 생략(완주로 센다), 없는데 2 면 교차 콜 결손이다.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | agentCalls | nullCount | stages | fallback | wall-clock | G2-review (finding/counter/severity) |
|---|------|-----------|-----------|--------|----------|-----------|--------------------------------------|

### fz-plan (collaborative) — Wave 2 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주(5/5 또는 direction_escalation 정상 반환) + fallback 0건. G2-plan 품질 관찰 = direction 판정 합리성 / CC 교차 신규 발견 / steps verify 존재 / §Y writeScope가 §X 자동 복사 아님 / Lead 이관 책임(stress-test·RTM) 실수행 여부.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | agentCalls | nullCount | stages | fallback | wall-clock | G2-plan (direction/CC/verify/§Y/Lead회귀) |
|---|------|-----------|-----------|--------|----------|-----------|--------------------------------------------|

### fz-code (pair-programming full) — Wave 3 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3세션 전수 — changeset 적용 성공률 100%(의사코드/생략 0건) + 빌드 통과(Lead 검증) + fallback 0. **행 단위 = 세션당 1행 (N-Step 누적 집계 — invoke당 N행 발산 방지)**. G2-code = changeset exact syntax 충실도 / review 이슈 유효성 / residualIssues 처리.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | steps | invokes | agentCalls(계) | nullCount | fallback | stage2-null steps | G2-code |
|---|------|-------|---------|----------------|-----------|----------|-------------------|---------|

### fz-fix (pair-programming light) — Wave 3 전환 (시작: 2026-06-05)

> 임계 (사전 등록): 3세션 전수 동일. complexity 계약(Lead 재평가) 작동 여부를 G2에 포함.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | steps | invokes | agentCalls(계) | nullCount | fallback | complexity 분기 | G2-fix |
|---|------|-------|---------|----------------|-----------|----------|------------------|--------|

---

### fz-code (pair-programming) — Wave 3 전환 (시작: 2026-07-10)

> 임계 (사전 등록): 3건 전수 null률 0% + stage 완주 + fallback 0건(입력 오류 제외). G2-code 품질 관찰 = changeset 적용성(anchor 정합) / 리뷰 실효성 / 빌드 1회 통과율. 세션당 1행(N-Step 누적).
> ⚠️ **승계 노트 (2026-07-18, 리뷰 C-1 반영)**: 본 표는 위 2026-06-05 표(pair-programming full)의 **신규 시리즈 재기준선**이다 — v4.21.0 H5 크기 가드(2026-07-09) 도입으로 fallback 의미론이 변경(입력 오류 fail-fast = 설계된 가드 정상 동작, 워크플로 실패 아님)되어 '입력 오류 제외'는 그 반영이지 구 frozen 임계의 사후 완화가 아님. 구 표(2/3 세션)의 행은 저장소 밖 로그에 사료로 보존. fz-code SKILL 지표 라우팅은 본 표(현행)를 가리킨다.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | steps | invokes | agentCalls | nullCount | fallback | 빌드 1회 통과 | G2-code 관찰 |
|---|------|-------|---------|-----------|-----------|----------|--------------|--------------|

### fz-peer-review (live-review) — Wave 4 전환 (시작: 2026-08-09)

> ⛔ **신설 사유**: `skills/fz-peer-review/SKILL.md`가 *"metrics는 Lead가 `experiment-log.md` §5.7 fz-peer-review 테이블에 기록"* 이라 지시하는데 **테이블이 존재하지 않았다**(F-12). 지시가 없는 대상을 가리키고 있었다.
> ⛔ 기존 §5.7 freeze 블록(확산 판정 임계)은 **불가침** — `experiment-log.md` §5.8 "freeze 범위 주석" 선례대로 **신설만** 허용한다.
>
> **임계 (사전 등록 — 변경 금지)**: 3건 전수 · `nullCount` 0 · stage 완주(**tier별 기대값 다름**: Tier 2 = Stage1 + **(트리거 발화 시 Stage2)**, Tier 3 = Stage1+Stage2+Stage3) · fallback 0 **단 `invalid-args`는 제외**(스크립트 fail-fast = 설계된 가드이지 워크플로 실패가 아님 — fz-code 2026-07-10 시리즈 선례 승계).
> ⛔ **임계 개정 이력 (2026-08-25, 사용자 승인 D4)**: `Tier 2 = Stage1+Stage2` → `Tier 2 = Stage1 + (트리거 발화 시 Stage2)`. 사유 = Stage 2 조건부 실행(D1) 도입으로 미발화 실행이 전부 '미완주'로 집계되던 문제. ⛔ **개정 범위는 이 조항 1곳** — `3건 전수`·`nullCount 0`·`fallback 0`은 불변이다. `nullCount`는 임계가 아니라 **코드(카운터 시점)**를 고쳐 의미를 맞췄다(D6, `peer-review.js` parallelWithRetry).
> **G2-peer 품질 관찰축**: 렌즈별 발견 실효성 / cross severity 조정 근거 인용 / counter refute의 실측 근거 / Origin 보정 작동 / 구조 축(structuralAxes) 발견 신규성.
> ⚠️ **열 설계 근거**: 단순 `null률·완주·fallback`만으로는 **신뢰성 실패와 입력 오류를 구별할 수 없다** — Tier·mode·fallback 사유를 분리 기록한다(Codex verify ISSUE-008).

> ⛔ **없는 값은 추정하지 않고 `unavailable`로 둔다** — 추정치를 실측 자리에 넣으면 이 표가 baseline 구실을 못 한다.
> ⛔ Tier 0/1은 Workflow를 호출하지 않으므로 `nullCount`·`stages`·`fallback`이 **개념상 부재**다(`n/a`). 실패해서 0인 것과 구분한다.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | tier | mode | agentCalls | nullCount | stages(기대/실제) | fallback (사유) | wall-clock | structuralAxes | G2-peer 관찰 |
|---|------|:----:|------|-----------:|----------:|-------------------|-----------------|-----------:|:--------------:|--------------|

## §5.8 Fable 5 효율 배선 측정 큐 (시작: 2026-06-12)

> 출처: Fable 5 고도화 계획 S4 — 배선=가설/측정=검증 (31/35차). **사전등록 임계 변경 금지** (확증편향 방어).
> freeze 범위 주석 (§5.7 동형): §5.7 freeze는 §5.7 데이터행+확산임계만 대상 — 본 §5.8 신설은 별도 허용. §5.8 ② N=5 = 표준 Phase B 진입 / ①effort는 **철회**(2026-06-14 fable 제재 롤백) · ④synthesis는 **재개**(2026-07-06 제재 해제) (①철회: frontmatter 4건 제거 → 측정 대상 소멸 / ④재개: pilot fable 복원 — search-cross-verify.js:166 `'opus'→'fable'` 1줄 전환, ①④ 헤더 참조. **canonical 상태 = 각 헤더**, CHANGELOG·release 노트는 cross-ref).
> **공통 필드 의무**: 각 행에 `session_model`(fable|opus) + `env_subagent_model`(CLAUDE_CODE_SUBAGENT_MODEL 설정 유무) 기록 — effort 효과의 3-way 혼합(세션 모델×서브에이전트 모델×effort) 방지.

### 워커 재배선 baseline (2026-07-07)

> 워커 3-tier 재배선(판단=fable / 실질 워커=opus / 단순=sonnet) 적용일 — ④·⑤ 측정의 새 기준점.

- **(i) 새 baseline**: §5.8 ④·⑤(fable 판단 지점) 측정은 **2026-07-07부터 새 baseline**. 재배선 이전 관측과 **비교 금지** — 다수 sonnet 워커가 opus로 승격돼 세션 비용·품질 지형이 이동(confound). 이전 행/관측은 사료로만 보존.
- **(ii) 신규 관측 컬럼**:
  - **워크플로별 비용** — 정적 콜 수 vs 런타임 인스턴스 수를 **분리 계상**(정적 1콜 = 런타임 N인스턴스, 예: discover lens fan-out); 비용·동시성 계산은 런타임 기준.
  - **캐시 히트** — opus 프롬프트 캐시 **최소 prefix 4096 tok 주의**(미달 시 캐시 미형성 → `cache_read_input_tokens=0`; 모델별 상이: Fable 5·Sonnet 4.6=2048).
  - **xhigh 품질** — effort=xhigh 산출 품질 정성 관찰(high 대비 동등+ 여부).
- **(iii) 상쇄 가설 검증 계획**: sonnet→opus 재배정은 콜당 +67%(입력 단가 opus≈1.67×sonnet)이나 세션 effort max→xhigh 하향이 추론 토큰을 감소시켜 세션 총비용 순증 < +67% — N=5 누적 후 정적콜 단가 × 실측 토큰(캐시 read/write 분리)으로 검증.

### ① effort frontmatter 효과 — **철회 (2026-06-14 fable 제재 롤백)**

> **철회 사유 (2026-06-14)**: 사용자 effort 운용 = 세션 레벨 max(기본)/ultracode 확정 → 4스킬 `effort: xhigh` frontmatter 제거(B1). 측정 대상(frontmatter 효과)이 소멸하여 철회 — 동결 아님(fable 복귀와 무관, 세션 운용 방식이라 frontmatter 재도입 없음). 아래는 철회 전 설계 — 사료 보존.

> `[미검증: 스킬 frontmatter→Workflow agent() 전파 여부 — 공식 docs 미기술]` → 첫 측정에서 적용 범위(스킬 Lead 단계 한정 vs Workflow 단계 포함) 판별 기록.
> 임계 (사전등록): N=5 누적 — xhigh의 G2 품질이 high 대비 동등+ AND 토큰 증가 ≤30% → 유지. 미달 → frontmatter 제거 (배선 롤백).
> **비교군(high baseline) 수집 설계** (2026-06-12 probe 발견 결함 보수 — 임계 불변, 방법 보완): 4스킬 전부 xhigh 고정이라 자연 high 데이터 생성 불가 → **retro-baseline** = 저장소 밖 로그의 §5.7 누적표의 배선 전(2026-06-12 이전) 행들(fz-plan #1-2·fz-review·fz-discover — effort 기본 high 시절)의 wall-clock/G2 관찰을 비교군으로 사용. [fable probe 발견: "high 대비 측정의 분모 수집 설계 부재"]

| # | date | skill | session_model | env_subagent_model | effort 적용 범위 확인 | 토큰(상대) | G2 품질 |
|---|------|-------|---------------|--------------------|---------------------|-----------|---------|

### ② fresh-context 검증자 catch (S3 배선: fz-review 검증 2 불능 분기)

> 임계 (사전등록): N=5 누적 — Lead self-review 미발견 이슈 평균 ≥1건/세션 → 유지 (Codex 회복 후 병행 검토). 0건 수렴 → Codex 회복 시 원경로 단독 복귀.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | 대상 | session_model | catch (M/L) | self-review 미발견분 | 비고 |
|---|------|------|---------------|-------------|---------------------|------|

### ③ 절차 밀도(de-prescription) A/B — R8 확산 게이트 (fz-search 384줄 pilot)

> 방법: 작업 폴더에 슬림 변형(절차 지시 축약 — **Gate·Few-shot·⛔ 가드레일 보존**) → 동일 쿼리 스킬 파일 swap 2-invoke → G2 + 토큰 비교.
> 임계 (사전등록): 품질 비저하(G2 동등) AND 토큰 ≥10% 절감 → R8 확산 게이트 오픈 (fz-review·fz-plan 절차 슬림, 별도 사이클). 미달 → 현행 유지 + Fable de-prescription 가설("too prescriptive → degrade")의 fz 반례로 기록.

| # | date | variant | session_model | 토큰 | G2 품질 | 판정 |
|---|------|---------|---------------|------|---------|------|

### ④ synthesis fable vs opus — **재개 (2026-07-06 제재 해제 — pilot 복원: search-cross-verify.js:166 fable)**

> **동결 사유 (2026-06-14)**: Fable 5가 미국 제재로 외국인 사용 금지 → 세션 모델 opus 4.8 운용. synthesis pilot은 `model: 'opus'`로 롤백(search-cross-verify.js:166 — `model` 생략 시 agent 정의 `model: sonnet` 강등 위험이라 explicit opus). 측정 동결 — **사전등록 임계/baseline 설계 보존**, 제재 해제 + fable 세션 재개 시 `'opus'→'fable'` 1줄 전환으로 측정 재개. 아래는 동결 전 활성 근거 — 사료.
> 활성 근거(사료): 사용자 발화 "생각이 깊어야 되는 부분은 plan, review, discover, search 이런 부분은 fable5로 하면 좋고" + A/B probe 정상 작동 확인. pilot 1차 자동 적용 권한 거부(06-12) → "반영해줘" 인가 적용(06-13) → 06-14 제재로 롤백.
> 선행 baseline 3-state: Lead=opus/syn=opus(구) · Lead=fable/syn=opus(직전) · Lead=fable/syn=fable(pilot). "승격=비용 2배" 단정은 baseline 실측 후.
> 임계 (사전등록): pilot N=3 — fable synthesis의 G2 품질이 opus 대비 우위 신호(교차 병합 누락↓ 또는 FP 판정 정확도↑) ≥2/3 AND wall-clock 비악화 → plan-collaborative integrate 확산 검토. 미달 → opus 롤백.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | 단계 | syn model | 토큰 | 품질 관찰 | 비고 |
|---|------|------|-----------|------|----------|------|

### ⑥ 세션 effort sweep — plan Workflow (신설 2026-09-11)

> ⛔ **① 과 별개다.** ①(effort frontmatter)은 2026-06-14 **철회된 사료**이며 임계도 N=5·토큰 ≤30% 로 다르다 — 새 실험을 그 표에 쓰면 철회 기록을 덮는다 (GPT verify #2 지적).
> 배선 근거: `plan-collaborative.js` 11콜이 `effort: 'xhigh'` 고정. 공식 default 는 `high` 이고 *"run a fresh effort sweep"* 을 요구한다 [verified: platform.claude.com/docs/en/build-with-claude/effort]. ⛔ arm 은 **세션 레벨**로 설정한다 (`guides/skill-testing.md` §8.1 — per-call `opts.effort` 수정 금지, 실효는 `[미검증]`).
> 격리 요구 (GPT verify #3): 코드 상태(S1~S6 적용분) 고정 · 같은 requirement·codeContext · advisor 상태 동일 · control(xhigh)·treatment(high) **둘 다 fresh 실행**(과거 실행과 대조 금지 — 프롬프트·스키마가 이미 다르다) · run 별 세션 effort 실측 기록 · per-call 1콜 프로브 병행.
> 임계 (사전등록): **독립 채점자**(fresh-context) 판정 critical·major 손실 0 AND G2 5축 보존 → high 채택 근거. 시간·토큰은 같은 행에 함께 기록한다(품질만 보면 R1 을 못 잰다). **N=1 은 탐색**이며 확산은 N=3 누적 후.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | arm | session_effort | wall | critical_path | out_tok | thinking | advisor | G2 5축 | 채점자 판정(critical/major 손실) | 판정 |
|---|------|-----|----------------|------|---------------|---------|----------|---------|--------|------------------------------|------|

> 2026-10-19: 워커 effort 는 Lead 세션 effort 를 따른다(`modules/mode-gate.md` § effort — 워크플로는 args.effort 로 받는다 · 미지정 `xhigh`). 이 sweep 의 arm 은 이제 Lead 세션 effort 하나이고, 저장소 밖 로그의 같은 절 행 2(`high` 기각)는 Lead 를 `xhigh` 아래로 내릴 때의 위험 근거로 남는다.

## §5.9 구조 ablation — plan Workflow (신설 2026-09-11)

> ⛔ `§5.7` freeze 와 `§5.8` ①~⑤ 는 불가침 — 본 절은 **신설만** 이다(`§5.8` 신설 선례 계승).
> 측정 계약: `modules/peer-review-tiers.md` § 수집 축소의 검증 계약(ablation) 준용 — 같은 입력 2회(전량 control + 변형), 사전등록 기준, 사후 변경 금지.
> ⛔ **S8a(모델)와 S8b(구조)를 분리 평가한다** (GPT verify #4·#13): 한 번에 바꾸면 어느 것이 효과인지 갈리지 않는다. S8b 는 (i) S3 CC 제거와 (ii) S5→fresh-context refute 교체를 **다시 분리**한다.
> ⛔ "최종 생존 0" 은 무가치의 증거가 아니다 — 통합 단계 유실일 수 있다. must-fix **개수**가 같아도 고유 발견이 바뀔 수 있으므로 독립 채점자가 **동일성·정확성·축 커버리지**를 판정한다.
> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| # | date | 변형 | control | wall Δ | 고유 발견(control/변형) | 동일성 판정 | G2 커버리지 | null·병합 | 판정 |
|---|------|------|---------|--------|------------------------|------------|------------|-----------|------|

### ⑤ direction verdict fable vs opus (신설 2026-07-06)

> 배선 근거: `plan-collaborative.js:241` stage0-direction · `:254` stage0-final을 fable로 승격(판정문 출력 — 생산 스테이지 대비 출력량 작아 비용 할증 최소). rebuttal·draft·integrate 등 생산 스테이지는 opus 유지.
> 주 측정 대상: **stage0-direction**(상시 실행) · **stage0-final**은 비-PROCEED 시만 보너스 기록.
> control (비교군): **retro-baseline** 기본 — 저장소 밖 로그의 §5.7 fz-plan **#1-2**(opus 세션; #3은 Fable 세션 첫 invoke라 제외 — ① retro-baseline 선례 계승, session_model=fable 오염 방지)의 stage0 direction 판정 관찰(근거 재현성·대안 품질·escalation 정확성)을 fable 판정과 대조. 불충분 시 **shadow-opus 3회 한정**(동일 case를 opus로 재판정해 직접 대조).
> 임계 (사전등록): N=3 누적 — 판정 품질(근거 재현성·대안 품질·escalation 정확성)이 opus 대비 비열화 ≥2/3 AND wall-clock 비악화 → 유지 / 미달 → opus 롤백(2줄 원복).

| # | date | case | verdict | retro_baseline_same? | evidence_citations | alternatives_count | escalation_correct? | 품질 관찰 | wall_clock | session_model | env_subagent_model |
|---|------|------|---------|---------------------|--------------------|--------------------|--------------------|----------|-----------|---------------|--------------------|

## §5.10 A/B 원장 프로토콜 (S05 — 신설 2026-09-26)

> 판정기 `scripts/ab_ledger.py`(수집·채점·판정) · 통합 테스트 `tests/ab/integration.py` · 이 절의 필수 항목은 `scripts/check_ab_protocol.py` 가 검사한다(health-check).
> ⛔ 이 절은 **측정 절차**다. 수치는 원장(`{FZ_WORK}/ab/ledger.jsonl`)에 쌓고 여기에 옮겨 적지 않는다 — 손으로 옮긴 수치는 조건 검사를 건너뛴다.
> ⛔ 2026-09-26 이전 `fz_wf_metrics` 의 out_tok·turns 는 **과대**다. 응답 1건이 content block 마다 한 줄로 기록되며 같은 usage 를 반복하는데, 줄마다 더했다(실측 1.35~1.6배). 같은 날 워커 역할 추출도 고쳤다(하네스 래퍼 뒤의 [역할] 을 못 읽어 stage 가 전부 '?' 였다). 저장소 밖 로그의 §5.7·§5.8 토큰·턴 수치와 새 원장 수치를 직접 비교하지 않는다.
> 판정기는 2026-09-26 GPT 적대 검토(critical 3·major 17)를 반영했다 — 위치 매칭 채점 폐기(가린 검증자 필수)·재구성 대조·arm 별 트리 검사 등.

### 1. arm 과 트리
- **B(기준선)** = `FZ_BASE_TREE`(FZ_BASE_SHA 의 불변 worktree). **C(변경안)** = `FZ_TREE`(작업 worktree). ⛔ 두 트리를 `--plugin-dir` 로 **직접 쓰지 않는다** — fz-review·fz-plan 이 플러그인 루트의 experiment-log 에 지표를 쓰므로 불변 트리가 오염된다. run 마다 **플러그인 사본**을 만든다: B 는 base 저장소를 clone 해 FZ_BASE_SHA 를 checkout, C 는 작업 트리를 rsync 한 사본.
- `claude -p --input-format stream-json --output-format stream-json --verbose --plugin-dir <사본> --add-dir <사본>` **한 프로세스 세션**으로 띄운다(플러그인 루트가 추가 폴더면 Workflow scriptPath 거부와 사전 복사가 생기지 않는다). run 이 어느 트리를 썼는지는 transcript 의 `Base directory for this skill:` 로 판정한다(collect 가 `plugin.roots` 로 기록 — 1개가 아니면 미완주).
- ⛔ 턴이 끝나도 stdin 을 열어 두고, **유휴**일 때만 후속 턴을 보내거나 stdin 을 닫는다. 유휴 = 이번 발화 뒤 `result` 가 왔고 · `background_tasks_changed` 의 실행 중 작업이 0 이고 · 그 뒤 온 `task_notification` 이 다음 `result` 로 소화됐고 · 5s 동안 이벤트가 없다(빈 작업 목록이 완료 알림보다 먼저 온다). `claude -p` 는 입력이 닫히면 local_bash 백그라운드 작업을 **기다리지 않는다** — 턴마다 새 프로세스(`--resume`)를 쓰면 Lead 가 알림을 기다리며 턴을 끝낼 때 GPT 셸이 죽는다(2026-09-27 실측: plan 3/3 run 의 GPT 검증 · peer-review 3/3 run 의 DA, F-332).
- 플러그인 신원은 **run 전에** 잰다: `input --plugin-root <사본> --plugin-source <원본>`(B 원본 = FZ_BASE_TREE · C 원본 = FZ_TREE). 사본의 트리 해시가 원본과 같아야 하고(충실한 사본), 트리 해시가 없으면 무효다. run 뒤에는 사본이 experiment-log 로 dirty 가 되므로 **코드 해시**(허용 출력 `experiment-log.md` 제외)를 전후로 비교한다 — 실행 중 코드가 바뀌면 무효다. B 는 `judge --plugin-sha` 로 SHA 를, 묶음 검사로 arm 별 트리 일치와 **C 트리 ≠ B 트리**를 본다. C 사본은 git 저장소여야 한다(rsync 뒤 `git init` + 커밋 — 트리 목록을 git 이 정한다).
- 모델·effort 는 `--model claude-opus-5-5 --effort xhigh` 로 고정한다. 판정은 transcript 의 `message.model` 과 최상위 `effort` 로 한다(AC-1 — 불일치 run 은 무효). 워커도 같은 두 필드로 본다.
- `FZ_AUTONOMY` 는 세 스킬(fz-plan·fz-review·fz-peer-review)이 **읽지 않는다** — `/fz` Phase 4 에만 배선돼 있다(`modules/governance.md` · 2026-09-26 base 트리 전수 grep). 설정해도 사람 대기 지점은 그대로이므로 대기 회피는 아래 §3 의 입력 설계로 한다. 두 arm 에 같은 값(`FZ_AUTONOMY=autonomous`)을 두는 것은 기록용이다.
- `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` — `claude -p` 의 백그라운드 대기 600s 천장을 끈다. 켜 두면 긴 Workflow 가 600s 에서 잘린 채 오류 없이 끝난다(2026-09-13 실측, F-203). ⛔ 이 천장은 에이전트·Workflow 작업에만 걸린다 — 셸(local_bash)은 값과 무관하게 기다리지 않으므로 위의 세션 유지가 따로 필요하다.
- `FZ_GATES_OFF=1` — 사용자 전역 Stop hook 이 **main 트리**의 gate_stop_hook 을 부른다. finalize 된 원장이 미충족이면 종료를 막아 run 을 바꾼다 — 검사 대상이 아닌 트리의 hook 이 두 arm 에 끼어들지 않게 끈다.

### 2. 격리와 시작 상태 (AC-7)
- run 마다 fixture 저장소를 **새 경로**에 복원한다(`tests/fixtures/quality/<fixture>/build-repo.sh <run 폴더>/repo`). 같은 경로를 두 run 이 쓰면 judge 가 '재사용' 으로 무효 처리한다. 경로가 새로우면 프로젝트 auto-memory 와 프로젝트 범위 에이전트 메모리(`<repo>/.claude/agent-memory/`)가 run 마다 비어서 시작한다. base 트리의 plan-structure·review-arch·review-quality 는 `memory: project` 다.
- 저장소 `.git/info/exclude` 에 `/ABT-*/`·`/NOTASK-*/`·`/peer-review-*/`·`/.claude/`·`/.serena/` 를 넣는다(입력 기록 전). 작업 폴더가 untracked 로 리뷰 diff 에 섞이지 않게 한다.
- 사용자 범위 에이전트 메모리(`~/.claude/agent-memory/`)와 이슈 트래커(`~/.claude/sessions/` — 60분 안이면 재사용된다)는 run 사이에 공유된다. A/B 동안 memory-curator recall 을 쓰지 않는다(`memory: user`). 시작·종료 스냅샷으로 감시한다 — 감시 이름 `user_agent_memory`·`repo_agent_memory`·`user_sessions` 는 **필수**이고 경로는 정본이어야 한다(`~/.claude/agent-memory` · `<repo>/.claude/agent-memory` · `~/.claude/sessions` 의 `SESSION-*_issues.json` — 이름만 맞고 다른 곳을 보면 무효). ⛔ `~/.claude/sessions` 폴더 전체를 보면 안 된다 — Claude Code 세션 등록 파일(`<pid>.json`·`.key`)이 세션마다 바뀌어 모든 run 이 거짓 무효가 된다(2026-09-26 실측):
  ```
  python3 scripts/ab_ledger.py snapshot --out <ab>/state/pristine.json --watch user_agent_memory=~/.claude/agent-memory --watch repo_agent_memory=/nonexistent --watch 'user_sessions=~/.claude/sessions::SESSION-*_issues.json'
  python3 scripts/ab_ledger.py snapshot --out <run>/start.json --watch user_agent_memory=~/.claude/agent-memory --watch repo_agent_memory=<repo>/.claude/agent-memory --watch 'user_sessions=~/.claude/sessions::SESSION-*_issues.json'
  (run)
  python3 scripts/ab_ledger.py snapshot --out <run>/end.json --watch …(시작과 같은 watch)
  ```
  pristine 은 A/B 전에 1회 찍는다. 시작 스냅샷이 pristine 과 다르면 그 run 은 무효다(다른 run 의 상태 유입). 이전 A/B run 이 만든 트래커 파일은 run 전에 그 run 증거 폴더로 옮긴다. 종료와 시작의 차이는 `state.writes` 로 남는다 — memory 필드가 무엇을 썼는지의 원인 기록이며 무효 사유는 아니다.
- 입력: run 전에 `python3 scripts/ab_ledger.py input --root <repo> --fixture <이름> --plugin-root <플러그인 사본> --plugin-source <원본 트리> --out <run>/input.json` 을 남긴다. 저장소가 깨끗해야 한다(미커밋·미추적 0). 입력 해시 = sha256(fixture 이름 · main/feature 커밋 · 작업 트리 해시 · 첫 사람 발화). build-repo.sh 가 커밋 신원·시각을 고정하므로 같은 fixture 는 같은 SHA 다. collect 는 Lead 의 작업 폴더가 이 저장소 안인지 대조한다. 프롬프트에는 경로를 넣지 않는다(run 마다 경로가 달라 해시가 갈린다).

- ⛔ **증거 부재 = 위반**: `input` 의 `--plugin-root`·`--plugin-source`, `collect` 의 `--input-json`·`--state-end` 는 필수 인자다. "있으면 대조" 는 fail-open 이다 — 증거를 안 주면 그 검사가 조용히 빠진다(GPT 검토 3라운드, F-317).

### 3. 사람 대기 회피 (입력 설계)
- 작업 폴더: 티켓 패턴이 있으면 질문 없이 `{PROJECT_ROOT}/{TICKET}/` 를 만든다 → 저장소에 `hotfix/ABT-1001-<이름>` 브랜치(= feature 커밋)를 만들어 checkout 한다. `hotfix/*` 는 base=main 으로 gather·Tier·GPT review 세 곳이 모두 질문 없이 풀린다.
- fz-review: fixture 지침에 `## Build` 절(빌드 대상 없음)을 둔다 — 없으면 빌드 명령을 묻는다. 최종 산출물 = `{WORK_DIR}/review/self-review.md`.
- fz-peer-review: `--tier 3` 고정(작은 diff 는 Tier 0 으로 떨어져 Workflow·GPT 를 부르지 않는다). 슬래시 명령을 그대로 프롬프트로 준다. `--post` 는 쓰지 않는다.
- fz-plan: plan-final.md 는 Gate 2 승인 뒤에만 쓴다 → **표준 승인 턴** 1회를 같은 세션에 보낸다(같은 프로세스의 stdin — 첫 턴이 유휴가 된 뒤, §1): "Gate 2 승인·확정 — 추가 질문 없이 plan-final.md 를 기록해줘". wall 은 plan-final.md 기록에서 끝난다. 두 arm 이 같은 문구를 쓴다. 요구사항에서 리팩토링 어휘를 뺀다(추가 질문 트리거).

### 4. 순서 (교차)
- 워크플로마다 B1 → C1 → B2 → C2(또는 C1 → B1 → C2 → B2) 순서로 `--order` 를 준다. 기준선을 먼저 재면 C 자리를 비워 두고 번호를 예약한다(S08: B1=1 · B2=3). `judge --require crossover-order` 가 교차를 판정한다.
- 정식 비교는 arm 별 유효 run 이 **정확히 2개**여야 한다. 모자라면 무효 run 을 다시 재고, 넘치면 FAIL 이다(골라 쓰지 않는다). smoke 는 C 가 `--runs` 와 정확히 같아야 한다.

### 5. wall 자
- **wall_total** = Lead transcript 의 첫 사람 발화 → 최종 산출물 기록 이벤트의 결과 시각이다. 기록 이벤트는 **완료된** Write·Edit, 또는 쓰기 근거(리다이렉트·쓰기 동사)가 있는 Bash 뿐이다(읽기는 후보가 아니다). 셸 변수·`for` 값·`python3 - ARG` 의 argv 로 넘긴 경로는 펴서 대상과 맞춘다(argv 는 위치까지 — F-331). 모르는 쓰기 형태는 mtime 교차 실패로 run 이 무효가 된다. SC-6 은 이것으로만 판정한다. 파일 mtime 은 끝점 이벤트를 고르고 **교차 검사**(허용 5s)에만 쓴다 — ⛔ mtime 자로 wall 을 재지 않는다(`fz_telemetry_report` 의 mtime wall 은 -36% 편향).
- **wall_workflow** = 에이전트 timestamp(`fz_wf_metrics`) 와 Lead 의 Workflow 기동 → 완료 알림. 이 두 자끼리만 교차하고 5% 를 넘으면 run 무효다(judge 가 두 값과 차이를 함께 인쇄한다). 실측 교차 차이는 0.12~0.27% 였다(2026-09-25 run 5건).
- **wall_gpt** = GPT 래퍼 기동 → 완료. 성공은 **GATE-PASS 증거**로만 인정한다 — 백그라운드면 알림의 상태·종료 코드 + 작업 출력 파일의 GATE-PASS, 포그라운드면 도구 결과의 GATE-PASS(래퍼는 비지 않은 출력을 확인한 뒤에만 찍는다), 출력 경로를 풀 수 있으면 그 파일도 비어 있지 않아야 한다. 실행 위치에서 래퍼를 부른 명령만 호출로 센다(검색·읽기는 제외). 성공한 호출마다 **자기** 배너(model·reasoning effort)를 1:1 로 붙인다 — 출력 경로의 `.stream.log`, 변수 경로면 그 호출의 시간창 안 로그 하나. 연결되지 않은 성공 호출이 있으면 AC-1 판정 불가로 무효, 실패한 호출이 하나라도 있으면 무효다. 묶음 비교에서 GPT effort 는 Lead 가 `--effort` 를 **명시하지 않은** 호출끼리만 맞춘다 — 명시 플래그는 측정 대상의 행동이고, 기본값 effort 가 다르면 환경 차이로 무효다(F-333). 변수 경로로 호출한 run 은 `collect --gpt-log-dir <run 폴더>` 를 준다.

### 6. 완주 오라클 (AC-5)
- 주 오라클: Workflow 반환의 `metrics.agentCalls` = 하네스 `agentCount`(알림 결과가 온전해도 output-file 이 있으면 함께 대조) = Workflow 폴더 agent 수 = journal started 수 = journal result 수 · `mode:'workflow'` · nullCount·fallbackCount 0(필드가 없으면 0 으로 읽지 않고 미완주) · 빈·실패 결과(`ok:false`·`error`) 0 · 실행 모드별 필수 stage 전부(peer-review 는 Stage 2 발화 시 R2, Tier 3 이면 R3 까지) · `stagesCompleted` 기대값(fz-plan 2 · fz-review 3(조건부 Stage 2 미발화면 2) · peer-review Tier 3 이면 3 · Tier 2 는 Stage 2 여부로 2/1). 수동 교차는 `python3 scripts/fz_wf_metrics.py --wf <runId> --expect-agents <agentCalls>` 가 COMPLETE 를 내는지로 한다.
- 완료 알림의 `<result>` 는 8,000자에서 잘린다(실측) — collect 는 `<output-file>`(하네스 래퍼 JSON)을 읽고 원장 옆 `evidence/` 에 같은 파일명으로 사본을 남긴다(`/tmp` 는 지워질 수 있다). 러너가 run 직후 tasks 폴더를 복사했으면 `collect --tasks-dir` 로 준다.
- 대체 오라클(반환을 못 읽은 경우): journal started = result = agent 수 + 필수 stage 전부. 어느 오라클을 썼는지 `wf.runs[].oracle` 에 남는다. ⛔ peer-review 는 실행 모드(tier·Stage 2)를 반환으로만 알 수 있어 대체 오라클을 쓰지 않는다(미완주). 알림의 반환과 하네스 래퍼의 반환이 둘 다 있는데 다르면 미완주다. JSON 문자열로 기록된 journal 결과의 오류(`ok:false`·`error`)도 실패로 센다.
- 미완주 run 은 **0건이 아니라 무효**다 — 비교에서 빼고, 남은 유효 run 이 모자라면 FAIL 이다. 공백뿐인 산출물도 미완주다.

### 7. 채점과 가린 검증자
- ⛔ 진성 여부는 **가린 검증자**만 정한다. 인용 위치가 라벨과 겹친다는 것만으로 세지 않는다('정상' 언급도 위치는 겹친다 — GPT 검토 ISSUE-001).
  ```
  python3 scripts/ab_ledger.py blind-pack --ledger <ab>/ledger.jsonl --out <ab>/blind-<n>      # pack.json(검증자용) · key.json(열쇠)
  (fresh-context 검증자에게 pack.json 만 준다 — key.json·원장·arm 정보 금지 → verdicts-anon.json)
  python3 scripts/ab_ledger.py blind-unpack --pack <ab>/blind-<n> --verdicts verdicts-anon.json --out <ab>/verdicts-<n>.json
  python3 scripts/ab_ledger.py score --ledger <ab>/ledger.jsonl --verdicts <ab>/verdicts-<n>.json
  ```
  꾸러미에는 run_id·arm·순서·절대 경로가 없다(anon id 는 소금 해시). 리뷰는 인용 후보마다 **지적 문단 전체**와 위치 힌트(near_labels)를, fixture 마다 **diff 와 인용된 파일 본문**을 준다 — 검증자는 **코드로 확인한** 결함만 real 로 판정한다(주장만으로는 false). 계획은 본문·요구사항·채점표 항목을 준다. 검증자는 어느 arm 의 산출물인지 알 수 없어야 한다. 판정 값은 JSON boolean 이다(`"false"` 같은 문자열은 미검증).
- 판정은 꾸러미를 만들 때의 **산출물 해시**에 묶인다. 산출물이 바뀌었거나 recollect 로 행이 바뀌었으면 옛 판정은 쓰이지 않고(score 가 미검증으로 채점), judge 는 점수의 산출물 해시가 현재 행과 다르면 낡은 점수로 보고 UNRUN 한다.
- 리뷰: 검증자가 후보마다 {real, label_ids, severity, axis} 를 낸다. 라벨로 매핑된 발견은 **라벨의** severity·axis 로, 라벨 밖 진성 발견은 판정 값으로 센다. 한 라벨은 한 번만 센다. real=true 인데 유효한 라벨 매핑도, 허용된 severity·axis 도 없거나, 없는 라벨·다른 파일의 라벨로 매핑하면 그 후보는 **미검증**이다(세지 않고 넘어가면 발견이 사라진다). 인용 파일은 fixture 파일로 풀어 대조한다 — 경로 성분 끝이 맞는 파일, 없으면 basename 이 fixture 파일 basename 의 접미인 파일이 정확히 하나일 때 그 파일(약칭 — 실측: B 의 Lead 보고서는 `EditRow.swift` · `VC.swift` 를 쓴다). 못 푼 인용(0 · 2개 이상)의 라벨 매핑은 받고 `mapping_unchecked` 로 센다(SC-3 · SC-4 판정 줄에 인쇄). 후보 문맥은 인용이 든 문단이다 — 인용 행이 1행짜리 위치 표(렌더러 보고서의 지적 머리)면 다음 제목 · 마커 전까지 뒤 문단(What · Suggestion)을 붙인다(상한 1,600자). fixture 가 규칙 출처를 선언하면(`expected-index.json` files) 그 파일을 가리키는 인용(`CLAUDE.md:12`)은 후보가 아니다 — 지적의 근거 참조라 검증 비율 분모에 넣지 않는다. 판정 단위는 지적이다 — 렌더러 지적 절(1행 위치 표 · What · Suggestion) 안의 인용은 절 문맥을 함께 쓰고, 라벨 파일이 후보 파일이 아니어도 같은 절이 그 파일을 `파일:줄` 로 인용하면 매핑을 받아 `mapping_context` 로 센다(판정 줄에 인쇄). 그 밖의 교차 파일 매핑은 미검증이다. 점수에는 채점기(계측기) 버전이 남고, 현재 버전과 다르면 judge 가 낡은 점수로 본다. 계획: 채점표 항목마다 {covered} — 절·질문·10배 부하·의존성 장애·롤백은 major, 잔재·소비자 심볼은 critical 이다(키워드는 힌트뿐).
- 판정이 빠진 후보·항목이 하나라도 있으면 그 점수는 미검증이며 SC-3·SC-3-smoke·SC-4 는 UNRUN 이다.

### 8. peer-review B arm 의 표준 후속 필터 턴
- 실측: peer-review 호출 다음 발화의 63% 가 "코멘트 달 가치·근거 재실측" 요청이고, 그 턴에 호출 시간의 +35% 가 든다(감사 REPORT §3 — 호출 구간 측정 밖이었다). SC-6 의 peer-review 끝점은 **게시 가치·근거 확인까지**다.
- 그래서 B arm 은 첫 응답 뒤 **고정 문구 1턴**을 같은 세션에 보낸다(같은 프로세스의 stdin — 첫 턴이 유휴가 된 뒤, §1): "코멘트로 달 가치가 있는 항목만 근거를 다시 실측해 추리고, 게시할 코멘트를 pr-comments.md 로 저장해줘". wall 은 그 턴의 산출물에서 끝난다. C arm 이 같은 산출물을 첫 턴에 내면 후속 턴을 보내지 않고, 못 내면 같은 문구를 보낸다. 어느 쪽이든 `lead.followup_prompts` 에 남는다.

### 9. 원장 명령과 판정식
```
python3 scripts/ab_ledger.py collect --ledger <ab>/ledger.jsonl --workflow fz-review --arm B --run 1 --order 1 --phase baseline \
  --fixture review-ios-ribs --transcript <session>.jsonl --artifact <repo>/ABT-1001/review/self-review.md \
  --input-json <run>/input.json --state-pristine <ab>/state/pristine.json --state-start <run>/start.json --state-end <run>/end.json
python3 scripts/ab_ledger.py judge --ledger <ab>/ledger.jsonl --phase baseline --workflows fz-plan,fz-review,fz-peer-review \
  --min-runs 2 --plugin-sha <FZ_BASE_SHA> --verify-sources transcript,wf-metrics,start-state,input-hash,instrument-sha
python3 scripts/ab_ledger.py show --ledger <ab>/ledger.jsonl
```
- 계측기(ab_ledger.py 와 실행 모듈 ab_ledger_*.py · fz_wf_metrics · freeze_baseline — 목록 정본은 `INSTRUMENTS`, self-test 모듈은 밖)의 내용 해시가 `instrument_sha` 로 남는다. B 와 C 는 같은 계측기로 수집해야 한다 — 다르면 judge 가 무효로 두고, `recollect` 로 원천에서 다시 모은다.
- judge 는 `--verify-sources` 로 기록된 collect 인자를 써서 행을 원천(transcript · Workflow 폴더 · 반환 사본 · 스냅샷 · 입력 기록 · 산출물 해시 · run 별 플러그인 사본 — 행 `sources.plugin_roots`)에서 **다시 만들고** 판정 필드 전체를 대조한다. 행을 손으로 고치거나 원천이 사라지면 무효가 된다(통합 테스트 `tampered-*`).
- 판정식:
  - SC-3 = critical·major 각각 max(0, mean(B) − mean(C)) ≤ |B1 − B2|
  - SC-3-smoke = 같은 식에 C 1회(R-A 출하 전용 — 재실행 이력이 있으면 골라 쓰지 않고 FAIL)
  - SC-4 = C run 마다 6축 각 1건 이상 + 검증 비율 ≥ mean(B) − |B1 − B2|
  - SC-6 = median(B) − median(C) > max(|B1 − B2|, |C1 − C2|)
  - SC-7 = Lead out_tok·messages·tool_errors·followup_prompts 와 워커 out_tok·turns·so_retries 존재 + B 공통 stage·성공한 GPT 호출 수 보존
- ⛔ 구현한 기준의 정본은 판정 표 `CRITERIA`(`scripts/ab_ledger_judge.py` — `IMPLEMENTED` 는 그 키)다 — 여기에 목록을 옮겨 적지 않는다(옮긴 사본이 코드와 어긋났다, v4.40.0 리뷰). 그 밖의 기준과, 받지만 구현하지 않은 옵션(`--envs` 등 — `judge_rows` 입구가 막는다)은 **exit 2** 다. baseline phase 에 다른 기준을 주어도 exit 2 다. 받고 무시하면 그것이 AC-5 의 '빠른 성공'이다.

### 10. 기준선 이동 기록

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| 시점 | 변경 | 영향 받는 측정 | 비교 규칙 |
|---|---|---|---|

## §5.11 GPT 다각도 원장 프로토콜 (R-G2 S9 — 신설 2026-10-13)

> GPT 를 질문 틀이 다른 별도 호출(frame)로 더 부르는 것이 결함을 더 찾는지 재는 절차다. 정본 계획: fz GPT 다각도·통합 플랜 rev2(R-G3 S11~S13).
> ⛔ 이 절은 측정 **전** 동결된다 — 임계 · 표본 · 예산은 사용자가 승인하고(S11) 그 prereg sha256 을 저장소 밖 로그의 같은 절 동결 행에 적은 뒤에만 첫 run 을 돈다.
> ⛔ 기본값은 바꾸지 않는다 — 판정 KEEP 은 승격을 제안할 자격일 뿐이다(별도 계획 · 버전 · 사용자 승인).

### 사전등록 템플릿 (prereg.json — S11 에서 사용자가 값을 정하고 status 를 approved 로 바꾼다)

```json
{
  "instrument_sha": "<사용자가 요청한 커밋 — 계측기 gpt_merge · gpt_ab_decide · gpt-call · gpt_kinds · gpt_independent · frame>",
  "n_min": 6, "n_max": 12,
  "corpus": ["K 층 — 정답 라벨 fixture 2종 + 결함 도입 커밋(major 이상 1 · 도입/수정 SHA · diff 2000줄 이하)"],
  "arms": {"A0": 2, "A2": 2, "A3": "P4 runnable 일 때 1 · 아니면 deferred", "A4": "예산이 남을 때 1"},
  "arm_budget": "과제당 핵심 4호출(A0×2 · A2×2) + 선택 2", "daily_cap": 12,
  "arm_timeout": {"value": "<제안 — 런처 기본 1800 보다 길게>", "status": "requires_user_approval"},
  "grader": "fresh-context Claude Opus 5.5 xhigh 또는 사용자 — gpt_merge --blind-pack 으로 가린 채 채점",
  "window": "사용자 실세션 GPT 사용과 분리 · 창 안 quota 실패율 따로 기록", "concurrency": 1,
  "record": "arm 마다 배너 model · effort · CLI 와 정규화 유효 설정 해시(원시 해시는 provenance) · 감사 promptSha256",
  "frame_aggregation": {"value": "<제안 — frame 마다 따로 판정(decide --frame-arm A2 · A3 · A4), 여러 frame 을 합친 판정은 내지 않는다>", "status": "requires_user_approval"},
  "thresholds": {
    "delta_keep": {"value": 1.0, "status": "requires_user_approval"},
    "positive_share": {"value": "2/3", "status": "requires_user_approval"},
    "fp_keep": {"value": 0.15, "status": "requires_user_approval"},
    "fp_rollback": {"value": 0.30, "status": "requires_user_approval"},
    "tokens_ratio": {"value": 1.5, "status": "requires_user_approval"},
    "fail_max": {"value": 0.10, "status": "requires_user_approval"}
  }
}
```

- 노이즈는 과제마다 A0r1 대 A0r2 로 잰다 — 상수(예: 과거 노이즈 바닥 5)를 쓰는 prereg 는 판정기가 거부한다
- 임계는 숫자 또는 정확한 분수 `"a/b"` 다 — 0.667 은 2/3 이 아니다(n=6 에서 ceil(0.667×6)=5 · ceil(2/3×6)=4). `instrument_sha` 가 비어 있으면 판정기가 거부한다
- 판정 순서(Z-14): INVALID(prereg · 계측기 SHA 불일치) → n_valid < n_min DEFER → ROLLBACK → KEEP → 그 밖 DEFER. 과제 안 arm 의 model · effort · CLI · 정규화 설정이 다르면 그 과제는 비교에서 빠진다

### 근거 레코드 (조회 · 논문 탐색은 계획 research.md · 상세는 계획 Z-15)

| ID | 결정 | 근거 | 한계 |
|---|---|---|---|
| D1 | 정문 하나로 호출을 모은다 | A5 · census · CLAUDE.md:61 | A5 는 Astra 대상 · Sol 미검증 |
| D2 | 모델 · effort 는 래퍼가 소유, 레지스트리 금지 | A2 · A5 · gpt-strategy | — |
| D3 | spawn 은 감사 먼저 | A1 · A4 · S1 실측(끄는 키 `[agents] enabled`) | 일반 경로 끄기는 측정 뒤 |
| D4 | 질문 틀이 다른 별도 fresh 호출 | C4 · C3 · C6 · C5 · C1 · B1 · A5 | 초록 수준 · fz 효과로 환산 금지 |
| D5 | 같은 질문 반복 대조군(A0r2) | C2 · C8 · 기존 측정 행(N=1) | 과제별 노이즈 |
| D6 | 정확성 기준 + 출처 보존 | B1 | — |
| D7 | 재현은 read-only 안에서만 | C6 · A5 · F-258 | 쓰기 차단(P4) — repro 팔은 조건부 |
| D8 | 측정 뒤 채택 · 비용 지표 | A3 · B2 | 단일 벤치마크 |
| D9 | 측정 경로 = 격리 런처 | 런처 격리 · F-348 | — |
| D10 | 소수 · 위치 없음 보존 | C3 · C8 · review_merge 다중집합 | — |
| D11 | 하위 에이전트 렌즈는 arm 으로만 | A3 · --gpt-agents | 자식은 부모 이력 상속 |
| D12 | 생성 표 + --check | CLAUDE.md 카운트 규칙 | — |
| D13 | frame 은 스킬로 설치하지 않는다 | plugin-refs · cross-validation | — |
| D14 | 가린 채점 | C7 자기선호 | 모든 arm 이 GPT 라 대칭이지만 라벨은 가린다 |

- 재조회 기준일: 2026-10-12

### 판정 · 동결 도구

- `python3 scripts/gpt_ab_decide.py verify-freeze --prereg <prereg.json> --log ${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md --runs <runs.jsonl>` — 동결 행 해시 일치 · 동결 시각 이전 run 없음 · 계측기 커밋 일치
- `python3 scripts/gpt_ab_decide.py decide --prereg <prereg.json> --log ${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md --runs <runs.jsonl> --verdicts <judged.json> [--verdicts …] [--frame-arm A2|A3|A4] --out <decision.json>` — 동결 확인을 먼저 하고 판정한다
- 채점 입력은 `scripts/gpt_merge.py --blind-pack` → 채점 → `--blind-unpack` 으로 만든다(라벨 · 출처를 가린다). unpack 출력(`gpt-merge-judged/1`)을 그대로 `--verdicts` 로 넘긴다 — 모르는 형식 · 판정이 빠진 후보는 거부된다

### 동결 행 (S11 — 사용자가 승인한 prereg 만)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다. 판정 도구에는 그 파일을 `--log` 로 넘긴다.

| prereg_sha256 | approved_by | time | instrument |
|---|---|---|---|

### 결과 행 (S13 — 판정 · 사용자 선택)

> 측정 기록은 저장소 밖 로그(`${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md`)의 같은 절에 있다.

| 판정 | prereg_sha256 | n_valid | meanΔ | FP 차이 | tokens 비율 | A2 실패율 | 사용자 선택 | 시각 |
|---|---|---|---|---|---|---|---|---|
