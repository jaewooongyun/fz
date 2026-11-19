# 완료 게이트

작업이 끝났는지를 모델의 자기보고 대신 **실제로 돌아가는 명령**으로 판정한다. v4.25.0 에서 도입했다.

> 내부 SSOT(원장 문법·수명주기·배선 계약)는 `modules/gates.md` 다. 이 문서는 **쓰는 사람**을 위한 것이다.

작업이 끝났는지를 모델의 자기보고 대신 **실제로 돌아가는 명령**으로 판정한다.

## 어떻게 생겼나

`/fz-plan` 이 계획을 세우면 `{WORK_DIR}/gates/plan.md` 가 만들어진다.

```
# Gates: 사용자 이력 API 재정비
ROOT: {WORK_DIR}
STATE: active
APPROVED: yes

- [ ] S1: 빌드가 통과한다
  CRITERION: 시뮬레이터 빌드가 성공해야 한다
  CHECK: xcodebuild -workspace App.xcworkspace -scheme App build
  EXPECT: BUILD SUCCEEDED
  CWD: {GIT_ROOT}
  APPROVED_ORACLE_HASH: 4e7e65bdc54c
  EVIDENCE: pending

- [ ] S2: 시트 마진이 48pt 다
  MANUAL: 시뮬레이터에서 마진을 눈으로 확인
  CRITERION_HASH: 37378c7a4cc3
  EVIDENCE: pending
```

`CHECK` 가 실제로 도는 명령이고 `EXPECT` 는 그 출력에 있어야 하는 문자열이다. **둘 다** 만족해야 통과다. 종료 코드만 보면 "실행됐다"만 증명하고, 출력만 보면 실패한 프로세스가 에러 메시지에 성공 토큰을 담고 있을 때 통과한다.

눈으로 봐야 하는 항목은 `MANUAL:` 로 적는다. 명령으로 억지로 판정하지 않는다.

## 어디서 발화하나

| 시점 | 하는 일 |
|------|--------|
| `/fz-plan` | 계획의 Step 에서 원장을 만들고, GPT 판정을 받아 확정한 뒤 착수 전(`STATE: planned`)으로 남긴다 |
| `/fz-code` | 시작할 때 착수 전 원장을 `active` 로 연다. Step 완료 선언 전에 그 Step 게이트만 실행. 실패하면 다음 Step 으로 안 간다 |
| `/fz-review` | 기록된 증거를 믿지 않고 다시 돌린다. 통과 못 하면 체크를 푼다 |
| 세션 종료 | 미충족 원장이 있으면 종료를 막는다 (차단 항목을 설정에 추가한 머신만) · 플러그인만 설치해도 워커 심볼 도구 사용을 훑어 기록하고, 상태 기록을 남긴 세션에서 '의심' 이면 알린다(막지 않는다 — 아래 '종료 훅 훑기') |
| `/fz-manage check` | 원장 상태를 보여준다. 차단 항목이 없는 머신의 노출 경로 |

원장이 없는 세션에는 아무 영향이 없다. 게이트를 쓰지 않던 흐름은 그대로 돈다.

## 통과할 수 없을 때

게이트를 만족시킬 수 없으면 원장에 이렇게 적는다.

```
ABANDON: S3 시각 확인은 비대화형 세션에서 불가
```

그러면 통과로 처리되고 포기 사실이 원장에 남는다. 최종 보고에도 표면화된다. 조용히 사라지지 않는다.

계획만 승인하고 구현은 시작하지 않았다면 포기가 아니다. `ABANDON` 대신 `--set-state planned` 로 착수 전을 남긴다(`/fz-plan` 이 확정 직후 이렇게 하고, `/fz-code` 가 시작할 때 `--set-state active` 로 연다). 착수 전 원장은 세션 종료를 막지 않는다.

진행 기록(통과 증거 · 재실행에서 떨어진 기록 · MANUAL 확인)이 있는 원장은 착수 전으로 되돌릴 수 없다. 착수 전 원장은 판정(`--status`)에서만 통과로 보고, 실행은 `active` 로 연 뒤에 한다.

세션 전체를 끄려면 환경변수를 쓴다.

```bash
FZ_GATES_OFF=1 claude
```

⛔ 이것은 **세션 단위**다. 원장의 `STATE` 는 바뀌지 않으므로 다음 세션에서 다시 판정한다.

## 직접 돌려보기

```bash
G="$(bash scripts/resolve-plugin-root.sh)/scripts/gate_check.py"

python3 "$G" --status  {WORK_DIR}/gates/plan.md   # 파싱만, 명령 미실행
python3 "$G" --only S1 {WORK_DIR}/gates/plan.md   # S1 게이트만 실행
python3 "$G" --reverify {WORK_DIR}/gates/plan.md  # 통과한 것도 다시 실행
python3 "$G" --confirm S2 {WORK_DIR}/gates/plan.md # MANUAL 확인 (터미널에서만)
python3 "$G" --set-state planned {WORK_DIR}/gates/plan.md # 승인·미착수로 남김 (진행 기록이 있으면 거부)
python3 "$G" --set-state active  {WORK_DIR}/gates/plan.md # 착수
python3 "$G" --discover .                          # 하위 원장 상태 요약
```

종료 코드는 네 갈래다.

| 코드 | 뜻 | 어떻게 읽나 |
|-----:|------|------------|
| 0 | 충족 | 통과 |
| 1 | 미충족 | 판정 결과다. 시간이 없었다는 것은 통과가 아니다 |
| 3 | 원장 계약 위반 | fz 가 만든 원장이 자기 문법을 어겼다. 평가 불가는 통과가 아니다 |
| 2 | 인프라 | python 부재나 파일시스템 오류. 세션 감금이 게이트 누락보다 나쁘다 |

## 세션 종료 차단 (선택 설치)

기계적 차단은 아래 Stop 항목을 설정에 추가한 머신에만 있다. 원장과 판정기, 그리고 나머지 배선 넷은 어디서나 돈다.

플러그인을 설치하면 같은 스크립트가 감사 전용(`--audit-only`)으로 스스로 등록된다(`hooks/hooks.json`). 그 항목은 아래 '종료 훅 훑기' 만 돈다 — 게이트를 판정하지 않고 막지 않는다. 차단 항목을 더하는 법은 아래 그대로이고, 더한 머신은 막는 판정을 그대로 받으면서 훑기는 실행마다 한 번이다.

⛔ **설치 전에 읽어야 하는 것 여섯 가지가 있다.** 잘못 넣으면 기존 hook 이 사라지거나, 플러그인을 업데이트한 뒤 조용히 꺼진다.

### 1. 기존 `Stop` 항목을 덮어쓰지 않는다

`.claude/settings.json` 의 `hooks.Stop` 은 **배열**이다. 이미 항목이 있으면 거기에 **추가**한다. 템플릿을 통째로 복사하면 기존 것이 사라진다.

```bash
python3 -c "
import json, pathlib
p = pathlib.Path.home()/'.claude/settings.json'
d = json.loads(p.read_text())
print('현재 Stop 항목:', len(d.get('hooks', {}).get('Stop', [])))"
```

### 2. hook 은 **병렬**로 돈다

공식 문서가 "hooks run in parallel" 이라 명시한다. 기존 `Stop` hook 이 알림이나 기록 용도면 충돌하지 않지만, **서로의 결과에 의존하는 hook 을 만들지 않는다.**

⚠️ 여러 `Stop` hook 중 하나가 `block` 을 냈을 때 어떻게 합산되는지는 공식 문서에 명시가 없다 `[미검증]`. 이 hook 은 자기 판정만 낸다.

플러그인의 감사 항목도 같은 `Stop` 에 함께 돈다. 두 항목의 훑기는 기록 폴더의 잠금으로 한 번만 판정 · 기록 · 알린다.

### 3. 플러그인 캐시 경로에 **버전이 들어간다**

```
~/.claude/plugins/cache/fz-orchestrator/fz/4.25.0/scripts/gate_stop_hook.py
                                           ^^^^^^ 업데이트마다 바뀐다
```

⛔ 이 경로를 하드코딩하면 **다음 업데이트에 hook 이 조용히 꺼진다.** 파일이 없으면 hook 이 fail-open 으로 통과하므로 에러도 안 난다.

아래 형태를 쓴다. 캐시에서 최신 하나를 고르고, 없으면 통과한다.

```bash
H="$(ls -d ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/gate_stop_hook.py 2>/dev/null | sort -V | tail -1)"
[ -n "$H" ] || exit 0
exec python3 "$H"
```

⛔ **개발 모드(`claude --plugin-dir …`)를 쓰면 위 형태로는 hook 이 절대 돌지 않는다.** 캐시에는 옛 버전이 남아 있고 새 스크립트가 없기 때문이다 — 실측: 캐시가 `fz/4.12.0` 인데 소스는 4.25.0 이고, `gate_stop_hook.py` 는 캐시에 존재하지 않는다. glob 이 빈 값이 되어 `exit 0` 으로 조용히 통과한다.

개발 모드에서는 소스를 먼저 보고 캐시로 폴백한다.

```bash
H="/path/to/fz/scripts/gate_stop_hook.py"
[ -f "$H" ] || H="$(ls -d "$HOME"/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/gate_stop_hook.py 2>/dev/null | sort -V | tail -1)"
[ -n "$H" ] || exit 0
exec python3 "$H"
```

⚠️ `/path/to/fz` 는 각자의 클론 경로로 바꾼다. 이 형태는 소스가 있으면 소스를, 없으면 캐시 최신을 쓴다.

### 4. `python3` 3.9+ 가 PATH 에 있어야 한다

없으면 hook 이 통과한다(fail-open). 차단이 조용히 사라지므로 설치 후 한 번 확인한다.

```bash
python3 --version
python3 <플러그인>/scripts/gate_stop_hook.py --self-test   # 85/85 passed
```

### 5. 상태 파일을 홈에 만든다

`~/.fz/stop-hook-state.json` — 무한 루프 방어용 카운터다. 같은 원장 상태로 두 번 막은 뒤에는 통과시킨다. 쓰기에 실패하면 즉시 통과한다(방어 없이 막으면 무한 block 이 된다).

워크플로 실행이나 직접 호출 기록이 있는 세션에서는 아래 훑기가 `${FZ_RUN_STATE:-~/.fz/runs}/mcp-sweep.jsonl`(판정 기록) · `mcp-sweep.keys.json`(판정한 실행의 열쇠) · `mcp-sweep.lock`(두 항목이 함께 돌 때의 잠금) · `mcp-sweep.held.json`(막는 종료에서 미룬 알림)도 만든다. 플러그인만 설치한 머신도 같다 — 상태 파일(`stop-hook-state.json`)은 차단 항목만 만든다.

### 6. 원장을 못 찾으면 차단도 없다

탐색은 세션 CWD 하위 **깊이 3까지**다. 워크트리에서 작업하고 원장이 리포 루트에 있으면 찾지 못한다.

```bash
export FZ_GATES_LEDGER=/path/to/PRJ-1234/gates/plan.md    # 여러 개는 : 로 구분
```

`gates/` 디렉토리는 있는데 확정 원장(`plan.md`)이 없으면 그 사실을 stderr 로 알린다. `gates/` 자체가 없으면 게이트 미사용 세션이므로 조용히 통과한다.

### 설치

`examples/hooks.json.example` 의 `Stop` 항목을 참고해 `.claude/settings.json` 의 `hooks.Stop` 배열에 추가한다.

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "H=\"$(ls -d ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/gate_stop_hook.py 2>/dev/null | sort -V | tail -1)\"; [ -n \"$H\" ] || exit 0; exec python3 \"$H\""
          }
        ]
      }
    ]
  }
}
```

차단을 끄려면 그 항목을 지운다 — 플러그인의 감사 항목은 남아 아래 훑기는 계속 돈다. 세션에서 `FZ_GATES_OFF=1` 을 쓰면 차단과 훑기(두 항목 모두)가 함께 꺼진다.

### 종료 훅 훑기 — 워커 심볼 도구 사용 점검

플러그인이 `hooks/hooks.json` 으로 스스로 등록한 Stop 항목(`gate_stop_hook.py --audit-only` — `python3` 가 PATH 에 없으면 조용히 끝난다)이 이 세션의 끝난 워크플로 실행과 직접 호출을 센다(`fz_wf_metrics.py --mcp-audit --sweep`). 설치만 한 머신에서도 돈다 — 세고 · 기록하고 · '의심' 이면 알린다. 막지 않고, 원장을 찾지도 판정하지도 않으며, 상태 파일(`stop-hook-state.json`)을 읽지도 쓰지도 않는다. 어떤 경로에서도 exit 0 이고 stderr 에 아무것도 쓰지 않는다. 스킬 문서의 점검 줄은 Lead 가 건너뛰면 돌지 않으므로 훅이 직접 센다.

위 차단 항목을 더한 머신에서는 그 항목도 게이트 판정 뒤에 같은 훑기를 한다(원장이 없어도 · 전부 충족이어도 · 막을 때도). 두 항목이 같은 종료에 함께 돌아도 기록 폴더의 잠금(`mcp-sweep.lock`)으로 실행마다 한 번만 판정 · 기록 · 알린다 — 잠금을 못 얻은 쪽은 아래 시간 안에서만 기다리고 조용히 끝난다.

- **세는 워커**: 에이전트 정의의 `tools:` 줄에 심볼 도구(`find_symbol` · `find_referencing_symbols` · `get_symbols_overview`)가 있는 종류만 센다 — 메모리 큐레이터는 재지 않는다(메모리 회상이 일이라 호출 0 이 정상이다). 그런 워커가 없는 실행은 '해당 없음' 이다. 판정은 호출 수가 아니라 결과를 돌려준 호출 수다(일반 점검과 같은 판정 함수).
- **상태 기록**: 원장을 찾는 방식 그대로 작업 폴더 아래 깊이 3까지에서 이 세션이 쓴 `evidence/tools.md` 를 찾는다. 하나가 아니거나 실행이 시작된 뒤에 고쳐졌으면 그 실행의 0회 · 성공 0 은 '의심' 이 아니라 '미판정' 이다 — 틀린 상태로 판정하지 않고, Serena 가 없는 환경에서 매번 알리지 않는다.
- **알림**: '의심' 이 하나라도 있으면 훅 출력의 알림 칸(`systemMessage`)에 한 줄을 싣는다. 막지 않는다. 그 줄은 낱말마다 할 일을 적은 `modules/symbol-tools-audit.md` 를 훅이 자기 플러그인 루트에서 찾은 경로로 함께 적는다. ⛔ 알림에는 상태 기록이 있어야 한다 — 작업 폴더가 없어 `evidence/tools.md` 를 쓰지 않은 세션의 0회 · 성공 0 은 설계상 '미판정' 이라 조용하다(기록 줄은 남는다). 그러니 설치만 한 머신에서 알림이 뜨는 것은 fz 스킬이 상태 기록을 남긴 세션의 실행이다(예외는 워커가 다른 트리 표지를 남긴 실행 하나다). 막는 판정일 때는 기록만 하고 알리지 않는다(막는 사유가 먼저다) — 그 의심은 `mcp-sweep.held.json` 에 미뤘다가 같은 세션의 다음 막지 않는 종료(어느 항목이든)가 한 번 알린다(기록 줄은 다시 쓰지 않는다). 감사 항목은 게이트를 판정하지 않으므로, 두 항목이 다 있는 머신에서 막는 종료에 감사 항목이 먼저 잠금을 쥐면 그 종료에 알림이 실릴 수 있다. 그 줄이 사용자 화면에 보이는지는 아직 사람이 확인하지 않았다.
- **기록**: 새로 판정한 실행이 있을 때만 `${FZ_RUN_STATE:-~/.fz/runs}/mcp-sweep.jsonl` 에 한 줄(JSON)을 덧붙인다 — 실행마다 성공 · 오류 · 빈 결과 수 · 상태 · 켜진 언어 · context7 결과 종류, 그리고 상태 줄의 스택 스킬과 fz 밖 스킬 호출 횟수. 에이전트 종류 이름과 fz 자신의 스킬은 싣지 않는다. 기록은 이 머신 안에만 있다 — fz 는 그 파일을 어디에도 보내지 않는다. 새로 판정한 실행이 전부 '해당 없음'(심볼 도구를 가진 에이전트를 쓰지 않은 세션 — 다른 에이전트만 쓰는 세션)이면 열쇠만 쓰고 기록 줄은 쓰지 않는다. 기록 파일이 1MB 에 이르면 덧붙이기 전에 `mcp-sweep.jsonl.1` 로 한 번 돌린다(옛 파일은 하나만 남는다). 판정한 실행의 열쇠(실행 id + 워커 기록 수)는 옆의 `mcp-sweep.keys.json` 이다 — 같은 실행을 두 번 세지 않고, 워커 기록이 늘어난 실행(재개 · 다음 시도)은 다시 본다. 워크플로의 두 단계 사이(앞 단계 워커가 다 끝나고 다음 단계가 아직 뜨지 않은 때)에 판정한 실행도 워커가 더 끝나면 다시 판정한다 — 그 실행의 기록 줄이 하나 더 생긴다.
- **시간**: 훅 예산(45초)의 남은 몫 안에서 최대 5초다(잠금을 기다리는 시간 포함). 끝나지 않은 실행과 시간 안에 못 본 실행은 열쇠를 적지 않고 다음 종료 때 본다 — 다음 종료가 없는 지연 완료(세션의 마지막 턴 뒤에 끝난 실행)는 보장 밖이다. 워크플로 실행 · 직접 호출 기록이 없는 세션은 파일을 만들지 않고 곧장 끝난다 — 감사 항목 한 번에 약 0.06초다(`python3` 기동 포함 · 2026-11-18 실측).
- **오류**: 자기 예외 경계 안에서 돈다 — 훑기의 오류와 시간 초과는 게이트의 종료 코드 · 막는 횟수 · 사유를 바꾸지 못한다.
- **끄기**: 세션에서 `FZ_GATES_OFF=1`(감사와 게이트 판정이 함께 꺼진다) · 늘 끄려면 플러그인의 훅(`hooks/hooks.json` 의 Stop 항목)을 끈다. 설정의 차단 항목만 지우면 차단만 꺼지고 감사는 남는다.

## 원장이 지키는 것

증거에는 서명이 붙는다. 그 게이트의 명령, 종료 코드, 출력에 묶여 있어서 판정기가 다시 계산해 대조한다. 원장을 쓰는 것도 모델이므로 `- [x]` 로 바꾸고 통과 텍스트만 적는 경로를 막는다.

⛔ 암호학적 위조 방지는 아니다. 알고리즘이 공개돼 있어 작정하면 재계산할 수 있다. 막는 것은 실수로 생기는 통과다.

승인 도장(`APPROVED_ORACLE_HASH`)은 GPT 가 "이 `CHECK` 가 제목이 말하는 것을 재는가"를 판정한 뒤 `--finalize` 가 찍는다. 그 뒤 `CHECK`·`EXPECT`·`CWD`·`TIMEOUT`·`CRITERION`·제목 중 하나라도 바뀌면 실행이 거부된다.

상세는 `modules/gates.md` 를 본다.

---
