# Mode Gate — 무거운 경로 앞에서 light / full 을 묻는다

> Workflow(멀티 에이전트)를 띄우기 직전에 작업 크기를 재서 추천을 달고 사용자에게 고르게 한다. 언제 묻고 무엇을 보이며 무엇을 넘기는지의 정본이다. 추천 임계 숫자는 `scripts/mode_gate.py` 가 정본이다.

> 신설 정당화 (DELETE/MERGE-default): 스킬마다 다르던 light 절 · 신호어 목록 네 벌 · "full 모드 강제" 세 줄 · peer-review 자동 Tier 경계를 이 모듈과 `scripts/mode_gate.py` 로 합친다. 소비 문서는 가리키기만 한다.

## 목차

- [참조 스킬](#참조-스킬)
- [언제 묻나](#언제-묻나)
- [신호어](#신호어)
- [측정](#측정)
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
| fz | Phase 4 에서 스킬별 모드를 정해 인자로 넘긴다 |

## 언제 묻나

스킬이 Workflow 를 띄우기 **직전**에 묻는다. 아래 순서로 먼저 걸리는 것이 이기고, 걸리면 묻지 않는다.

1. **명시 인자** — `light` · `full` · `--solo`(= light) · `--team`(= full) · `--deep`(= full, 그 스킬의 deep 경로) · peer-review `--tier N`
2. **`/fz` 경유** — Phase 4 에서 사용자가 고른 모드를 인자로 받는다. 같은 질문을 두 번 하지 않는다
3. **신호어** — 아래 정본 목록의 말이 요청에 있으면 light
4. **자율 모드 또는 질문 도구를 쓸 수 없는 실행** — `scripts/autonomy_decide.py --action mode_select --in-scope --reversible` 가 `PROCEED` 이거나, AskUserQuestion 이 도구 목록에 없거나 거부·오류면 추천대로 진행하고 결과에 `자동 선택: 추천 {모드} — {사유}` 를 남긴다. 측정 실패로 추천이 없으면 light 로 진행한다(기본값 진행이지 추천이 아니다). GPT 선택 질문도 같은 규칙이다 — 기존 선택(off 포함)은 그대로, 선택이 없으면 config(`modules/gpt-strategy.md` § 모델·effort 선택의 exit 4 동작)
5. **그 밖** — 아래 형식으로 묻는다

⛔ 묻는 이유는 "사용자만 줄 수 있는 입력"(시간·비용 선호)이다(`modules/lead-action-default.md` Genuine-Need Pause 셋째 조건). 묻지 않는 경로(1~4)가 승인 피로를 막는다.

## 신호어

**정본 목록**: 그냥 · 가볍게 · 단순 · 빠르게 · light · 확인해줘 · 해도 돼? · 맞아? · 한 번 봐줘

- `--deep` · `--team` 이 함께 있으면 신호어는 무력하다(명시 인자가 이긴다)
- `--seq` 단독은 신호어가 아니다(`modules/lead-action-default.md`)
- light 는 절차 축소이지 검증 생략이 아니다 — Coverage · Negative-Result · External Feedback Gate 와 빌드 · 원장은 그대로다

## 측정

`python3 "${FZ_PLUGIN_ROOT}/scripts/mode_gate.py" <하위 명령> … [--estimate <workflow>]` — stdout JSON 한 덩이. 추천 임계는 스크립트 상수가 정본이다(문서에 숫자를 다시 쓰지 않는다).

| 스킬 | 하위 명령 · 입력 | 묻는 자리 |
|---|---|---|
| fz-review | `review --diff {WORK_DIR}/review/diff.patch` | diff.patch 작성 직후 · Workflow 준비 앞 |
| fz-peer-review | `peer --numstat {WORK_DIR}/numstat.txt --risk-json {risk.json}` | Gather Step 5.5 |
| fz-plan | `plan --read-scope {WORK_DIR}/plan/read-scope.txt --new-arch yes\|no` (한 줄 1경로) | code-context 기록 직후 · cp 앞 |
| fz-code | `code --steps {WORK_DIR}/plan/steps.json` (없으면 `--plan-doc` · `--no-plan`) | Phase 0.4 직후 |
| fz-fix | `fix --files N` | code-pair 를 부르기 직전 |
| fz-discover | `discover --complexity N` (`modules/complexity.md` 점수) | Workflow 준비 앞 |

결과 계약:

| 결과 | exit | 대화형 | 비대화형 |
|---|---|---|---|
| 성공 | 0 | 추천을 달고 묻는다 | 추천대로 + 기록 |
| 측정 불가(git 실패 · 빈 diff) | 2 | 추천 없이 "측정 불가" 를 보이고 묻는다 | light + 기록 |
| 입력 오류(인자 · 파일 없음) | 10 | 입력을 고쳐 1회 재실행, 또 실패면 측정 불가와 같게 | 같음 |

`--estimate` 는 full 이 더하는 Workflow 구간의 이 환경 기록 중앙값과 N 이다(`scripts/fz_telemetry_report.py` · 근사 · 20초 상한). 실패하거나 N 이 0 이면 "실측 없음" 으로 보인다.

## 질문 형식

AskUserQuestion 한 번. 모드 질문 하나에 GPT 선택이 필요하면 모델 · effort 두 질문을 붙인다(합계 4 이하 — `modules/gpt-strategy.md` § 모델·effort 선택).

```
질문: {스킬} 을 어느 모드로 할까요? 크기 {metrics 요약} · {reasons} · 워커 effort {effort.value}({effort.source})
선택지:
  1. {추천 모드} (Recommended) — {그 모드가 하는 일} · full 이면 "Workflow 구간 이 환경 중앙 {estimate.wall_median_min}분(N={estimate.n}, 근사)"
  2. {다른 모드} — {그 모드가 하는 일}
```

- 측정 불가(exit 2)면 `(Recommended)` 를 달지 않는다
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
- fz-discover 의 `--deep` GPT verify · fz-fix 의 `--gpt` 는 명시 플래그라 두 모드에서 같다

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

## 설계 원칙

- Progressive Disclosure Level 3 — 무거운 경로를 띄우는 스킬이 그 직전에 Read
- 숫자는 `scripts/mode_gate.py`, 계약은 이 모듈 — 둘을 섞지 않는다
- 추천은 라벨이다 — 사용자가 고르므로 임계는 실사용으로 고친다
- 500줄 이하 유지
