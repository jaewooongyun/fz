# 완료 게이트

작업이 끝났는지를 모델의 자기보고 대신 **실제로 돌아가는 명령**으로 판정한다. v4.25.0 에서 도입했다.

> 내부 SSOT(원장 문법·수명주기·배선 계약)는 `modules/gates.md` 다. 이 문서는 **쓰는 사람**을 위한 것이다.

작업이 끝났는지를 모델의 자기보고 대신 **실제로 돌아가는 명령**으로 판정한다.

## 어떻게 생겼나

`/fz-plan` 이 계획을 세우면 `{WORK_DIR}/gates/plan.md` 가 만들어진다.

```
# Gates: 시청내역 서버 재정비
ROOT: {WORK_DIR}
STATE: active
APPROVED: yes

- [ ] S1: 빌드가 통과한다
  CRITERION: 시뮬레이터 빌드가 성공해야 한다
  CHECK: xcodebuild -workspace app-iOS/tving.xcworkspace -scheme tving build
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
| `/fz-plan` | 계획의 Step 에서 원장을 만들고, Codex 판정을 받아 확정 |
| `/fz-code` | Step 완료 선언 전에 그 Step 게이트만 실행. 실패하면 다음 Step 으로 안 간다 |
| `/fz-review` | 기록된 증거를 믿지 않고 다시 돌린다. 통과 못 하면 체크를 푼다 |
| 세션 종료 | 미충족 원장이 있으면 종료를 막는다 (hook 설치한 머신만) |
| `/fz-manage check` | 원장 상태를 보여준다. hook 없는 머신의 노출 경로 |

원장이 없는 세션에는 아무 영향이 없다. 게이트를 쓰지 않던 흐름은 그대로 돈다.

## 통과할 수 없을 때

게이트를 만족시킬 수 없으면 원장에 이렇게 적는다.

```
ABANDON: S3 시각 확인은 비대화형 세션에서 불가
```

그러면 통과로 처리되고 포기 사실이 원장에 남는다. 최종 보고에도 표면화된다. 조용히 사라지지 않는다.

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

기계적 차단은 hook 을 설치한 머신에만 있다. 원장과 판정기, 그리고 나머지 배선 넷은 어디서나 돈다.

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

### 3. 플러그인 캐시 경로에 **버전이 들어간다**

```
~/.claude/plugins/cache/fz-orchestrator/fz/4.25.0/scripts/gate_stop_hook.py
                                           ^^^^^^ 업데이트마다 바뀐다
```

⛔ 이 경로를 하드코딩하면 **다음 업데이트에 hook 이 조용히 꺼진다.** 파일이 없으면 hook 이 fail-open 으로 통과하므로 에러도 안 난다.

아래 형태를 쓴다. 캐시에서 최신 하나를 고르고, 없으면 통과한다.

```bash
H="$(ls -d ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/gate_stop_hook.py 2>/dev/null | tail -1)"
[ -n "$H" ] || exit 0
exec python3 "$H"
```

⛔ **개발 모드(`claude --plugin-dir …`)를 쓰면 위 형태로는 hook 이 절대 돌지 않는다.** 캐시에는 옛 버전이 남아 있고 새 스크립트가 없기 때문이다 — 실측: 캐시가 `fz/4.12.0` 인데 소스는 4.25.0 이고, `gate_stop_hook.py` 는 캐시에 존재하지 않는다. glob 이 빈 값이 되어 `exit 0` 으로 조용히 통과한다.

개발 모드에서는 소스를 먼저 보고 캐시로 폴백한다.

```bash
H="$HOME/dev/fz-plugin/scripts/gate_stop_hook.py"
[ -f "$H" ] || H="$(ls -d "$HOME"/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/gate_stop_hook.py 2>/dev/null | tail -1)"
[ -n "$H" ] || exit 0
exec python3 "$H"
```

⚠️ `~/dev/fz-plugin` 은 각자의 클론 경로로 바꾼다. 이 형태는 소스가 있으면 소스를, 없으면 캐시 최신을 쓴다.

### 4. `python3` 3.9+ 가 PATH 에 있어야 한다

없으면 hook 이 통과한다(fail-open). 차단이 조용히 사라지므로 설치 후 한 번 확인한다.

```bash
python3 --version
python3 <플러그인>/scripts/gate_stop_hook.py --self-test   # 14/14 passed
```

### 5. 상태 파일을 홈에 만든다

`~/.fz/stop-hook-state.json` — 무한 루프 방어용 카운터다. 같은 원장 상태로 두 번 막은 뒤에는 통과시킨다. 쓰기에 실패하면 즉시 통과한다(방어 없이 막으면 무한 block 이 된다).

### 6. 원장을 못 찾으면 차단도 없다

탐색은 세션 CWD 하위 **깊이 3까지**다. 워크트리에서 작업하고 원장이 리포 루트에 있으면 찾지 못한다.

```bash
export FZ_GATES_LEDGER=/path/to/ASD-1234/gates/plan.md    # 여러 개는 : 로 구분
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
            "command": "H=\"$(ls -d ~/.claude/plugins/cache/fz-orchestrator/fz/*/scripts/gate_stop_hook.py 2>/dev/null | tail -1)\"; [ -n \"$H\" ] || exit 0; exec python3 \"$H\""
          }
        ]
      }
    ]
  }
}
```

끄려면 그 항목을 지우거나 세션에서 `FZ_GATES_OFF=1` 을 쓴다.

## 원장이 지키는 것

증거에는 서명이 붙는다. 그 게이트의 명령, 종료 코드, 출력에 묶여 있어서 판정기가 다시 계산해 대조한다. 원장을 쓰는 것도 모델이므로 `- [x]` 로 바꾸고 통과 텍스트만 적는 경로를 막는다.

⛔ 암호학적 위조 방지는 아니다. 알고리즘이 공개돼 있어 작정하면 재계산할 수 있다. 막는 것은 실수로 생기는 통과다.

승인 도장(`APPROVED_ORACLE_HASH`)은 Codex 가 "이 `CHECK` 가 제목이 말하는 것을 재는가"를 판정한 뒤 `--finalize` 가 찍는다. 그 뒤 `CHECK`·`EXPECT`·`CWD`·`TIMEOUT`·`CRITERION`·제목 중 하나라도 바뀌면 실행이 거부된다.

상세는 `modules/gates.md` 를 본다.

---
