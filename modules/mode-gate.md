# Mode Gate — 무거운 경로 앞에서 light / full 을 정한다

> Workflow(멀티 에이전트)를 띄우기 직전에 작업 크기를 잰다. 추천이 full(큼 AND 복잡)일 때만 사용자에게 묻고, 그 밖은 묻지 않고 light 로 진행한다. 언제 묻고 무엇을 보이며 무엇을 넘기는지의 정본이다. 추천 임계 숫자는 `scripts/mode_gate.py` 가 정본이다.

> 신설 정당화 (DELETE/MERGE-default): 스킬마다 다르던 light 절 · 신호어 목록 네 벌 · "full 모드 강제" 세 줄 · peer-review 자동 Tier 경계를 이 모듈과 `scripts/mode_gate.py` 로 합친다. 소비 문서는 가리키기만 한다.

## 목차

- [참조 스킬](#참조-스킬)
- [언제 묻나](#언제-묻나)
- [신호어](#신호어)
- [측정](#측정)
- [기록](#기록)
- [질문 형식](#질문-형식)
- [스킬별 light · full](#스킬별-light--full)
- [GPT 는 모드와 독립](#gpt-는-모드와-독립)
- [effort](#effort)
- [사용자 결정](#사용자-결정)
- [설계 원칙](#설계-원칙)

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| fz-plan | plan-lean2 기동 전 모드 게이트 |
| fz-review | review-live 기동 전 모드 게이트 |
| fz-peer-review | Gather 5.5 — Tier 1 / Tier 2 선택 |
| fz-code | code-pair 기동 전 모드 게이트 |
| fz-fix | code-pair 를 부를 상황에서 모드 게이트 |
| fz-discover | discover-adversarial 기동 전 모드 게이트 |
| fz-search · fz-pr-digest | `--deep` 명시 opt-in — 질문 없음, Workflow args 의 effort 만 |
| fz | Phase 4 에서 사용자가 **명시로 고른** 모드만 인자로 넘긴다 — 그 밖은 각 스킬 게이트가 잰다 |

## 언제 묻나

스킬이 Workflow 를 띄우기 **직전**에 정한다. 1~3 은 측정 전에 정해지고, 걸리면 재지 않는다. 그 밖은 측정 뒤 추천으로 갈린다 — 추천 light · 측정 불가는 5, 추천 full 은 6(6 이 4 인지 판정한다). **묻는 것은 6 뿐이다.**

1. **명시 인자** — `light` · `full` · `--solo`(= light) · `--team`(= full) · `--deep`(= full, 그 스킬의 deep 경로) · peer-review `--tier N`
2. **`/fz` 경유** — Phase 4 에서 사용자가 **명시로 고른** 모드만 인자로 받는다. 고르지 않았으면 인자가 없고 이 스킬 게이트가 재서 정한다(Phase 3 의 SOLO/TEAM 은 모드를 정하지 않는다)
3. **신호어** — 아래 정본 목록의 말이 요청에 있으면 light
4. **자율 모드 또는 질문 도구를 쓸 수 없는 실행** — 질문할 사람이 없다. 추천이 full 이어도 **light 로 진행**하고 결과에 `light 로 진행 — 추천 full · {reasons} · 질문 불가({사유})` 를 남긴다. 원래 추천은 [기록](#기록) `--recommended full` 로 보존한다. GPT 선택 질문도 같은 규칙이다 — 기존 선택(off 포함)은 그대로, 선택이 없으면 config(`modules/gpt-strategy.md` § 모델·effort 선택의 exit 4 동작)
5. **추천 light · 측정 불가** — 묻지 않고 light 로 진행하고 한 줄 통보한다: `light 로 진행 — 추천 {light | 없음(측정 불가)} · {reasons} · 위험 {risk categories | 없음}`. 측정 불가는 추천이 아니다 — "추천 light" 로 적지 않는다
6. **추천 full** — 질문 **전에** `python3 "${FZ_PLUGIN_ROOT}/scripts/autonomy_decide.py" --action mode_select --in-scope --reversible` 로 4 인지 본다. exit 0(PROCEED)만 자율 → 4. exit 1(ASK) · 2(측정 실패) · 3(BLOCK)은 대화형으로 보고 [질문 형식](#질문-형식)대로 묻는다. 질문 도구가 없거나 거부 · 오류 · 빈 답이면 4 와 같다

⛔ 묻는 이유는 "사용자만 줄 수 있는 입력"(시간·비용 선호)이다(`modules/lead-action-default.md` Genuine-Need Pause 셋째 조건). full 은 몇 배 느리므로 그 비용을 쓸지 묻는 자리는 큼 AND 복잡일 때뿐이다 — light 를 확인받는 질문은 승인 피로만 쌓는다.
⛔ "백그라운드 실행" 자체는 4 의 신호가 아니다 — bg 세션에서도 사용자가 답한다. 신호는 6 의 판정과 질문 도구 부재 · 거부 · 오류 · 빈 답이다.

## 신호어

**정본 목록**: 그냥 · 가볍게 · 단순 · 빠르게 · light · 확인해줘 · 해도 돼? · 맞아? · 한 번 봐줘

- `--deep` · `--team` 이 함께 있으면 신호어는 무력하다(명시 인자가 이긴다)
- `--seq` 단독은 신호어가 아니다(`modules/lead-action-default.md`)
- light 는 절차 축소이지 검증 생략이 아니다 — Coverage · Negative-Result · External Feedback Gate 와 빌드 · 원장은 그대로다

## 측정

`python3 "${FZ_PLUGIN_ROOT}/scripts/mode_gate.py" <하위 명령> … [--estimate <workflow>]` — stdout JSON 한 덩이. 추천 임계는 스크립트 상수가 정본이다(문서에 숫자를 다시 쓰지 않는다).

| 스킬 | 하위 명령 · 입력 | 재는 자리 |
|---|---|---|
| fz-review | `review --diff {WORK_DIR}/review/diff.patch` | diff.patch 작성 직후 · Workflow 준비 앞 |
| fz-peer-review | `peer --numstat {WORK_DIR}/numstat.txt --risk-json {risk.json}` | Gather Step 5.5 |
| fz-plan | `plan --read-scope {WORK_DIR}/plan/read-scope.txt --new-arch yes\|no` (한 줄 1경로) | code-context 기록 직후 · cp 앞 |
| fz-code | `code --steps {WORK_DIR}/plan/steps.json` (없으면 `--plan-doc` · `--no-plan`) | Phase 0.4 직후 |
| fz-fix | `fix --files N` | code-pair 를 부르기 직전 |
| fz-discover | `discover --complexity N` (`modules/complexity.md` 점수) | Workflow 준비 앞 |

결과 계약:

| 결과 | exit | 대화형 | 비대화형(§ 언제 묻나 4) |
|---|---|---|---|
| 추천 full | 0 | 자율 판정(§ 언제 묻나 6) 뒤 묻는다 → 고른 모드로 [기록](#기록) `gate` · 빈 답 · 오류는 light | light + 통보 + [기록](#기록) `autonomous` · 추천 full 보존 |
| 추천 light | 0 | 묻지 않고 light + 통보 → [기록](#기록) `default` | 같음 |
| 측정 불가(git 실패 · 빈 diff) | 2 | 묻지 않고 light + "측정 불가" 통보 → [기록](#기록) `default` · 추천 `none` | 같음 |
| 입력 오류(인자 · 파일 없음) | 10 | 입력을 고쳐 1회 재실행, 또 실패면 측정 불가와 같게 | 같음 |

`--estimate` 는 full 이 더하는 Workflow 구간의 이 환경 기록 중앙값과 N 이다(`scripts/fz_telemetry_report.py` · 근사 · 20초 상한). 실패하거나 N 이 0 이면 "실측 없음" 으로 보인다.

## 기록

모드가 정해지면 그 실행을 `scripts/run_metrics.py` 로 남긴다 — 위 결과 계약의 "기록" 이 이것이다. 저장은 `${FZ_RUN_STATE:-~/.fz/runs}/<pipeline>/runs.jsonl` 한 곳이고 시도 1회가 1행이다(스킬 · 모드 · 추천 · 상태 · 실효 model · effort · 시각). 프롬프트 · 본문 · 토큰은 담지 않는다.

| 시점 | 명령 |
|---|---|
| 모드가 정해진 직후 — 질문(6)으로 정했든 묻지 않는 경로(1~5)로 정했든 | `python3 "${FZ_PLUGIN_ROOT}/scripts/run_metrics.py" start --skill {스킬} --mode light\|full --recommended light\|full\|none --source arg\|fz\|signal\|autonomous\|default\|gate [--work-dir {WORK_DIR}]` |
| 완료 보고 직전 | `python3 "${FZ_PLUGIN_ROOT}/scripts/run_metrics.py" end --skill {스킬} [--work-dir {WORK_DIR}] --status completed\|interrupted\|failed [--workflow-run-id wf_…] [--gate-issues {Gate}={N} …] [--findings gpt={N},claude={N},convergent={N}]` |

- `--gate-issues` · `--findings` 는 리뷰 계열이 Gate 별 이슈 수와 cross-model 고유 · 일치 발견 수를 남기는 선택 인자다 — 리포터(`fz_telemetry_report.py`)가 Gate 를 10회 기록부터 neutral-candidate · load-bearing 으로 판정한다(그 전은 preliminary · experiment-log §5.4 손 기록을 대체). 없으면 그 키를 남기지 않는다(0 이 아니다)
- `--source` 는 위 「언제 묻나」 의 순번이다 — 1 명시 인자 `arg` · 2 `/fz` 경유 `fz` · 3 신호어 `signal` · 4 자율 · 질문 도구 없음 `autonomous` · 5 추천 light · 측정 불가로 묻지 않음 `default` · 6 질문 `gate`. `default` 와 `gate` 를 나눠야 "실제로 몇 번 물었나" 를 잰다. `--recommended` 는 `mode_gate.py` 결과의 `recommend` 그대로다 — 4 로 light 진행해도 `full` 로 적는다. 게이트를 돌리지 않았거나 측정 불가(exit 2)면 `none`
- fz-peer-review 는 Tier 0 · 1 을 `light`, Tier 2 · 3 을 `full` 로 적는다
- fz-fix 는 게이트(팀 에이전트 모드 0)가 모든 실행의 경로에 있지 않다 — 게이트 없이 Mode A 로 시작하면 Mode A 첫 줄에서 `--mode light --recommended none` 으로 `start` 하고(`--source` 없음), 게이트를 거쳤으면 게이트 줄에서만 `start` 한다
- `--work-dir` 는 WORK_DIR 이 있을 때만, `start` 와 `end` 에 같은 값으로 준다(없으면 세션 단위로 묶인다). `--workflow-run-id` 는 full 경로 Workflow 결과의 `Transcript dir` 끝 `wf_…` 다(여럿이면 마지막)
- 재개: 같은 WORK_DIR 에서 같은 스킬을 다시 `start` 하면 같은 run_id 의 다음 attempt 가 되고, `end` 없이 남은 앞 시도는 `interrupted` 1행으로 닫힌다. 같은 실행 안에서 모드를 바꿔 다시 `start` 해도(예: fz-fix Mode A 에서 팀 모드 게이트로 넘어감) 같다 — 앞 시도는 `interrupted`, 바꾼 모드는 다음 attempt
- 완료 보고 없이 끝나면(포기 · 실패 보고 · 사용자 중단) 그 보고 직전에 `--status failed` 또는 `interrupted` 로 `end` 한다. `end` 가 끝내 불리지 않은 시도는 리포트에 「열린 채 남은 시도」로 따로 센다(완료 · 중단 · 실패 어디에도 넣지 않는다)
- 기록 실패(쓰기 불가 · 디스크 오류)는 stderr 에 `RUN_METRICS_UNAVAILABLE <사유>` 를 남기고 exit 0 이다 — 스킬 진행을 막지 않는다. 같은 시도에 `end` 를 두 번 불러도 1행이다(두 번째는 `already ended`)
- 집계: `scripts/fz_telemetry_report.py` 리포트의 「실행 기록」 절(스킬 · 모드별 실행 · 완료 · 중단 · 실패 · wall 중앙값 · 열린 채 남은 시도) · 행 목록은 `--runs-json`

## 질문 형식

추천이 full 일 때만(§ 언제 묻나 6) AskUserQuestion 한 번. 모드 질문 하나에 GPT 선택이 필요하면 모델 · effort 두 질문을 붙인다(합계 4 이하 — `modules/gpt-strategy.md` § 모델·effort 선택).

```
질문: {스킬} 을 full 로 할까요? 크기 {metrics 요약} · {reasons — 큼 · 복잡 두 절} · 워커 effort {effort.value}({effort.source})
선택지:
  1. full (Recommended) — {full 이 하는 일} · "Workflow 구간 이 환경 중앙 {estimate.wall_median_min}분(N={estimate.n}, 근사)"
  2. light — {light 가 하는 일}
```

- 추천 light · 측정 불가는 묻지 않는다 — 통보 형식은 § 언제 묻나 5
- peer-review 는 위험 카테고리(`risk.json` categories)를 질문에 보인다 — 위험한 PR 을 가볍게 보내는 선택이 보이게
- `effort.override` 가 있으면 "워커 실효 effort = {override}(CLAUDE_CODE_EFFORT_LEVEL)" 를 덧붙인다

## 스킬별 light · full

light 는 새 모드가 아니라 각 스킬이 이미 가진 **Workflow 없는 Lead 경로**다.

| 스킬 | light | full |
|---|---|---|
| fz-plan | Phase 1 을 Lead 가 수행 → Phase 2 · 3 · 원장 그대로 | `workflows/plan-lean2.js` |
| fz-review | Phase 5 Lead 3중 검증(GPT review · 5.5 validate 포함) | `workflows/review-live.js` |
| fz-peer-review | Tier 1 (`--tier 0` 은 명시할 때만 — GPT 없음) | Tier 2 · `--deep` 은 Tier 3 |
| fz-code | Lead 가 Step 마다 직접 구현 · Step 마다 빌드 · 원장 게이트 | `workflows/code-pair.js` `mode:'full'` Step 마다 |
| fz-fix | Lead 직접 수정 | `workflows/code-pair.js` `mode:'light'` (code-pair 의 내부 인자 이름이다 — 모드 이름과 별개) |
| fz-discover | Lead 탐색 | `workflows/discover-adversarial.js` |

## GPT 는 모드와 독립

- GPT 를 켠 세션이면 light · full 이 **같은** GPT 단계를 갖는다. 실행 조건은 모드가 아니라 GPT 사용 여부다
- 끈 세션(`off`) · CLI 미설치면 두 모드 모두 `[GPT 미사용 — 사유]` 를 남기고 이어간다 — 정본 `modules/gpt-strategy.md` § GPT 미사용
- 단계마다 실행 여부는 직전 `gpt-choice.sh decide` 한 줄이 정한다 — 켬이면 필수 · 명시 플래그 구분은 `modules/gpt-strategy.md` § 단계 실행 판정. fz-fix 의 GPT check 는 켬이면 필수(플래그 없음 — 2026-11-01)이고, fz-discover 의 `--deep` GPT verify 는 명시 플래그라 두 모드에서 같다

## effort

- Workflow 를 부르는 모든 곳의 args 에 `effort` = `mode_gate.py lead-effort` 의 `effort.value` 를 넣는다. `value` 가 null 이면 넣지 않는다(워크플로 미지정 = `'xhigh'`)
- 출처 순서: 세션 id 에 묶인 transcript 의 최신 assistant `effort` → env `CLAUDE_EFFORT`. 둘이 다르면 transcript 를 쓰고 결과 `note` 에 남는다
- ⛔ effort 를 생략하면 워커는 세션 값이 아니라 모델 기본(Opus 5.5 = medium)으로 돈다 — 그래서 명시로 넘긴다(`guides/skill-authoring.md` §12)
- `CLAUDE_CODE_EFFORT_LEVEL` 이 설정돼 있으면 콜 명시값보다 그것이 우선한다 — 결과 `override` 로 보인다(`guides/skill-testing.md`)
- 한계: Lead 와 워커의 모델이 다르면 같은 수준 이름이 같은 사고량은 아니다(`guides/model-guide.md`). 세션 중 `/effort` 변경이 env `CLAUDE_EFFORT` 에 반영되는지는 확인하지 못했다 — transcript 를 1순위로 두는 이유다(최신성 미확인)
- Lead 를 `xhigh` 아래로 내리면 워커도 내려간다. `experiment-log.md` §5.8 ⑥ 에 `high` 가 plan 에서 major 손실을 낸 기록이 있다

## 사용자 결정

2026-10-19 사용자 결정으로 아래가 이전 규칙을 갈음한다.

| 결정 | 갈음한 것 |
|---|---|
| 무거운 경로 앞에서 **매번** 묻고 Lead 가 크기로 추천한다 | 직접 호출은 Lead 판단으로 Workflow · 비용은 통보(2026-09 선택) |
| GPT 는 light · full 에 같다 · 사용자가 끌 수 있다 | light 는 GPT 를 부르지 않는다 |
| 워커 effort = Lead 세션 effort | 워크플로 콜마다 `xhigh` 고정 |
| 품질은 현재 effort 로 담보 · 기본값 전환 검증은 실행 스모크 | 기본값 전환 전 사전등록 짝 측정(`experiment-log.md` 재등록 행) |

2026-11-12 사용자 결정으로 아래가 위 첫 행과 2026-10-19 의 추천 결합을 갈음한다. 근거는 full 이 몇 배 느린데 품질 차이가 작았다는 사용 경험과, 질문 대부분이 light 확인이었다는 실측이다.

| 결정 | 갈음한 것 |
|---|---|
| 추천이 full 일 때만 묻는다 · 추천 light · 측정 불가는 묻지 않고 light + 통보 | 무거운 경로 앞에서 매번 묻는다 |
| full 추천 = 큼 AND 복잡(review · peer · plan · code — 숫자 정본 `scripts/mode_gate.py`) | 한 조건만 넘어도 full 추천(OR) |
| 질문할 사람이 없으면 추천 full 이어도 light · 원래 추천은 기록에 보존 | 질문 불가면 추천 모드 그대로 진행 |
| `/fz` 는 사용자가 명시로 고른 모드만 넘긴다 — 그 밖은 스킬 게이트가 잰다 | Phase 4 에서 고른(추천 포함) 모드를 인자로 넘긴다 |

## 설계 원칙

- Progressive Disclosure Level 3 — 무거운 경로를 띄우는 스킬이 그 직전에 Read
- 숫자는 `scripts/mode_gate.py`, 계약은 이 모듈 — 둘을 섞지 않는다
- full 추천은 질문이다 — 임계는 실사용으로 고친다(run_metrics `default` · `gate` 행이 묻지 않은 수와 물은 수를 잰다)
- 500줄 이하 유지
