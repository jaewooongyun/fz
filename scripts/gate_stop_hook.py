#!/usr/bin/env python3
"""완료 게이트 Stop hook — 미충족 원장이 있으면 세션 종료를 막는다.

이것이 게이트 계층의 **2차 계층**이다. 1차(배선 1~3)는 SKILL.md 산문이라 Lead가
건너뛰어도 아무 신호가 없다. 그 재귀를 끊는 것은 이 hook 하나뿐이다.

⛔ **자동 배선하지 않는다.** 이 파일은 실행체이고, 등록은 사용자가
`examples/hooks.json.example`을 `.claude/settings.json`으로 복사해야 발동한다.
근거: `modules/governance.md` "Claude는 훅 설치·설정 변경을 명시 합의 없이
지시·실행하지 않는다". 따라서 **기계적 차단은 설치한 머신에만 존재한다.**

## 계약 (실측 출처)

`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/
hook-development/` — 공식 plugin-dev 스킬.

입력 (stdin JSON):
    {"session_id": …, "transcript_path": …, "cwd": …,
     "permission_mode": …, "hook_event_name": "Stop"}

차단 출력 (`references/advanced.md:262`의 command 타입 예시):
    stderr ← {"decision": "block", "reason": "…"}
    exit 2

⛔ `hookSpecificOutput.decision` 도 `{"continue": false}` 도 아니다 — **top-level
`decision`** 이다. 세 후보 중 어느 것인지는 공식 스킬 문서로 확정했다(probe 불요).

## 설계 결정

**원장 발견 = `cwd` 하위 glob (깊이 0~3).** `session_id`가 입력에 오므로
`~/.fz/sessions/<id>.json` 바인딩도 가능하지만 쓰지 않는다 — 바인딩은 **쓰는 쪽
배선**이 필요하고, 그 배선이 빠지면 hook이 원장을 못 찾아 조용히 무력화된다(이
작업에서 다섯 번 만난 실패 모드다). glob은 배선이 0이고, 여러 원장을 전부 보므로
다른 미완 작업을 놓치지 않는다. `STATE: closed`는 판정기가 no-op으로 걸러낸다.

**차단 = 이 세션이 쓴 원장만 (2026-09-11, F-188 2회 재관측).** glob 은 티켓별
워크트리를 한 루트에 두는 환경에서 **병렬 세션의 원장**까지 집어 무관한 세션의
종료를 막았다. 소유 판정은 배선 없이 가능하다 — 입력의 `transcript_path` 가 이 세션의
기록이고, 거기에 그 원장을 `Write`/`Edit` 하거나 `--finalize`·`cp`·`>` 로 쓴
tool_use 가 있으면 이 세션의 원장이다. 남의 미충족 원장은 **경고로만** 인쇄한다.
⛔ transcript 를 못 읽으면 전 원장을 판정한다(fail-closed) — 소유를 모를 때 통과시키면
자기 원장도 놓친다. `FZ_GATES_LEDGER` 명시 지정은 소유 판정을 건너뛴다(명시가 우선).

⛔ **깊이 한계와 그 밖.** 깊이 4 이상, 그리고 `cwd` **밖**(워크트리에서 작업하고
원장이 리포 루트에 있는 경우)은 어떤 glob으로도 찾지 못한다 — hook은 `cwd`만
받으므로 설계 한계다. `FZ_GATES_LEDGER`(경로 목록, `os.pathsep` 구분)로 명시
지정할 수 있다.

⛔ **"찾지 못함"은 조용하지 않다.** `gates/` 디렉토리가 아예 없으면 게이트 미사용
세션이므로 조용히 통과하지만, `gates/`는 있는데 확정 원장이 없으면 그 사실을
stderr로 남긴다. 미사용과 미발견이 같은 침묵이면 놓친 원장이 통과로 보인다.

**판정 = 재실행 없음.** `CHECK`를 다시 돌리면 게이트당 기본 120초여서 hook에
부적합하다. 기록된 증거를 읽어 판정한다 — 증거는 서명으로 oracle에 묶여 있어
"CHECK를 안 돌리고 통과 텍스트만 쓴" 경로를 이미 막는다.

**전면 fail-open.** 어떤 오류든 exit 0이다. `modules/gates.md`의 exit 계약이
"세션 감금이 게이트 누락보다 나쁘다"를 이미 정했고, hook은 그 원칙이 가장
날카롭게 적용되는 자리다 — 여기서 실수하면 사용자가 세션을 끝낼 수 없다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ → 플러그인 루트

HOOK_EVENTS = ("Stop", "SubagentStop")
# ⛔ 원장 발견(glob 깊이·SKIP_DIRS·상한)과 `FZ_GATES_LEDGER` 는 **판정기가 소유한다** —
#    `gate_check.py`의 `find_ledgers`. 여기에 복제하면 두 구현이 갈린다.
LEDGER_ENV = "FZ_GATES_LEDGER"
CHECK_TIMEOUT_S = 20                   # 판정기 1회 호출 상한
TOTAL_BUDGET_S = 45                    # 전체 예산 — 넘으면 통과(진단만)
MAX_BLOCKS = 2                         # 같은 상태로 이 횟수까지만 막는다
STATE_FILE = Path.home() / ".fz" / "stop-hook-state.json"
# 소유 판정 — transcript 의 tool_use 중 원장을 **쓴** 것만 센다. 읽기·grep·hook 피드백
# 인용은 제외(진단 세션이 남의 원장 경로를 출력만 해도 소유가 되면 안 된다).
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
TRANSCRIPT_LINE_HINT = "gates"           # 이 조각이 없는 줄은 파싱하지 않는다(47MB 기록 실측)
# ⛔ "gates/" 로 두면 `cd …/gates⏎cp plan.draft.md plan.md` 줄이 파싱 전에 버려진다 — 실측 #10·#24·#28.
_TOKEN = r"[^\s\"'`;|&<>()]*plan\.md"              # 원장 경로 토큰 — 상대명 `plan.md` 도 허용
# ⛔ 실측(2026-09-11, TVG-6894 세션 4회): Lead 는 `cd …/gates` 뒤 `cp plan.draft.md plan.md` ·
#    `--finalize plan.md` 처럼 **상대명**으로 쓴다. `gates/plan.md` 접미를 요구하면 진짜 소유
#    세션이 전부 "다른 세션" 으로 분류돼 미충족이 통과한다(오라클 exit 0). 세그먼트별 `cd` 와
#    `NAME=/abs` 대입을 추적해 절대경로로 되돌린다.
CD_RE = re.compile(r"^\s*(?:cd|pushd)\s+[\"']?([^\s\"';&|]+)")
ASSIGN_RE = re.compile(r"^\s*(\w+)=[\"']?(/[^\s\"';&|]+)")
SEGMENT_SPLIT_RE = re.compile(r"\n|;|&&|\|\||\|")
# ⛔ heredoc 본문이 **데이터인지 코드인지**는 어디에 먹이는가로 갈린다. `cat`/`tee` 로
#    가는 본문은 데이터라, 명령으로 읽으면 문서에 인용한 경로가 쓰기로 잡힌다(F-193 오탐).
#    반대로 `python3 -`/`bash -` 로 가는 본문은 **실행되는 코드**이고 이 리포가 파일을
#    고치는 관용구가 정확히 그것이다 — 데이터로 보고 지우면 진짜 쓰기를 놓쳐, 자기 원장을
#    그렇게 만든 세션이 소유 0 이 되고 게이트가 통째로 무력해진다(fail-open).
HEREDOC_RE = re.compile(r"<<-?\s*([\"']?)(\w+)\1.*?^\2$", re.S | re.M)
_INTERP = r"python[23]?|bash|sh|zsh|node|ruby|perl"
INTERPRETER_HEREDOC_RE = re.compile(
    r"(?:^|[|&;(]|\s)(?:" + _INTERP + r")\b[^\n]*$")
# heredoc 이 아닌 인터프리터 인자(`python3 -c "…"` · `node -e '…'`)도 **실행되는 코드**다.
# 따옴표는 짝으로 닫고 `\"` 이스케이프를 넘긴다 — 안쪽 반대 따옴표는 그대로 통과한다.
INTERP_ARG_RE = re.compile(
    r"\b(?:" + _INTERP + r")\b[^\n|;&]*?\s-[ce]\s+([\"'])((?:\\.|(?!\1).)*)\1", re.S)
# 인터프리터 코드 안의 쓰기 신호. 어느 변수가 그 경로를 들고 쓰는지 정적으로 못 따지므로
# 신호가 있으면 그 코드에 등장한 원장을 **보수적으로** 소유로 본다. 읽기만 하는 진단
# 스크립트에는 이 신호가 없어 오탐이 되지 않는다.
# ⛔ 인터프리터 목록에 이름만 올리고 신호가 파이썬 전용이면 그 인터프리터는 **무력**하다
#    (실측 2026-09-11: `node -e` 쓰기가 통과했다). 이름을 올렸으면 신호도 채운다.
INTERP_WRITE_SIGNALS = ("write_text(", "writelines(", ".write(", "shutil.copy",
                        "os.replace", "os.rename", "--finalize", "'w'", '"w"',
                        "writeFileSync", "appendFileSync", "createWriteStream",
                        "File.write", "IO.write")
# 쓰기 **대상 자리**에 온 경로만 취한다. "명령 어딘가에 경로가 있다" 는 소유가 아니다.
WRITE_TARGET_RES = tuple(re.compile(pat.replace("TOKEN", _TOKEN)) for pat in (
    r">>?\s*[\"']?(TOKEN)",                                  # 리다이렉션 대상
    r"--(?:finalize|out|output|out-file)[=\s]+[\"']?(TOKEN)",  # 판정기·래퍼의 출력 인자
    r"--confirm\s+\S+\s+[\"']?(TOKEN)",                          # MANUAL 게이트 확인 — 원장에 쓴다
    r"\b(?:cp|mv|tee)\b[^\n;|&]*?[\s\"'](TOKEN)",            # 복사·이동·분기 대상
))

EXIT_PASS, EXIT_BLOCK = 0, 2


def _pass(diagnostic: str = "") -> int:
    """통과. 진단은 stderr로만 — Claude에게 피드백되지만 차단은 아니다."""
    if diagnostic:
        print(f"[gate-stop-hook] {diagnostic}", file=sys.stderr)
    return EXIT_PASS


def _block(reason: str) -> int:
    """차단. ⛔ JSON 은 **stderr** 로, exit 는 **2** — 공식 command 타입 계약."""
    print(json.dumps({"decision": "block", "reason": reason},
                     ensure_ascii=False), file=sys.stderr)
    return EXIT_BLOCK


def sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:12]


def find_checker() -> Path | None:
    """같은 `scripts/` 디렉토리의 판정기."""
    cand = ROOT / "scripts" / "gate_check.py"
    return cand if cand.is_file() else None


def load_checker_module():
    """판정기를 모듈로 불러온다 — **원장 발견 함수를 빌려 쓰기 위해서**.

    ⛔ 자체 구현을 두지 않는다. 두 곳이 각자 원장을 찾으면 한쪽이 놓치는 배치가
       생긴다 — 깊이 2만 보던 결함이 정확히 그것이었다. 린터의 선례와 같은 원칙이다
       (`lint_contracts.py:804` "chk_N6 와 self-test 가 **같은 함수**를 쓴다").

    ⛔ 판정은 여전히 subprocess 다(격리). import 는 부작용 없는 **탐색 함수** 하나만
       빌리기 위한 것이고, 실패하면 통과한다 — hook 은 어떤 오류로도 세션을 감금하지
       않는다.
    """
    checker = find_checker()
    if checker is None:
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("fz_gate_check", checker)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:                                  # noqa: BLE001
        return None


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(state: dict) -> bool:
    """⛔ 실패하면 False. 루프 방어를 못 하므로 호출부는 **통과**를 택한다 —
    상태를 못 쓰는데 막으면 무한 block 이 된다."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
        return True
    except OSError:
        return False


def _bash_write_targets(cmd: str) -> list:
    """Bash 명령이 **쓰기 대상으로 지목한** 원장 경로들.

    ⛔ "명령에 쓰기 마커가 있다 + 어딘가에 원장 경로가 있다" 로 판정하면 안 된다.
       실측(2026-09-11): 발견 레지스트리에 사건을 기록하는 `cat > "$F" <<EOF` 가
       **본문에 인용한** TVG 원장 2개의 소유로 잡혔다 — 3건 전수 오탐이었고,
       그 결과 무관한 세션이 다시 종료 불가가 됐다. **기록하는 행위가 기록 대상의
       소유를 만들면 안 된다.**
    두 겹으로 막는다 — **데이터** heredoc 본문을 지우고, 남은 명령에서 리다이렉션·
    출력 인자·복사 대상 **자리**에 온 경로만 취한다.
    ⛔ 인터프리터로 가는 heredoc 은 지우지 않는다 — 그 본문은 실행되는 코드이고,
    지우면 `python3 - <<PY … write_text … PY` 로 자기 원장을 만든 세션이 소유 0 이
    되어 게이트가 전부 통과한다(fail-open).
    ⛔ 종료 태그가 없는 heredoc 은 지워지지 않는다(정규식 미매칭) — 그 경우 오탐이
    남을 뿐 누락은 생기지 않는다(fail-closed 방향).
    """
    if not cmd or "plan.md" not in cmd:
        return []

    # heredoc 본문은 둘 다 셸 문법 스캔에서 **뺀다**(데이터든 코드든 셸 인자가 아니다).
    # 인터프리터 본문만 따로 모아 코드 규칙으로 본다 — 본문 **안**에 쓰기 신호와 경로가
    # 함께 있어야 소유다. 명령 전체에 신호가 있으면 소유로 보던 초안은, 본문 밖에 인용된
    # 경로까지 끌어와 F-193 오탐을 되살렸다(2026-09-11 실측).
    interp_bodies = []

    def _split_heredoc(m):
        line_start = cmd.rfind("\n", 0, m.start()) + 1
        if INTERPRETER_HEREDOC_RE.search(cmd[line_start:m.start()]):
            interp_bodies.append(m.group(0))
        return " "

    body = HEREDOC_RE.sub(_split_heredoc, cmd)
    # ⛔ `body` 에서 찾는다 — 원본이 아니다. 데이터 heredoc 은 이미 지워졌으므로, 문서에
    #    **인용된** `python3 -c …` 한 줄이 소유를 만들지 않는다(F-193 과 같은 축).
    interp_bodies.extend(m.group(2) for m in INTERP_ARG_RE.finditer(body))
    out = []
    cur_dir = None
    env = {}
    for seg in SEGMENT_SPLIT_RE.split(body):
        mcd = CD_RE.match(seg)
        if mcd:
            cur_dir = _expand(mcd.group(1), env)
            continue
        masg = ASSIGN_RE.match(seg)
        if masg:
            env[masg.group(1)] = masg.group(2)
        for rx in WRITE_TARGET_RES:
            for tok in rx.findall(seg):
                tok = _expand(tok, env)
                if not tok.startswith("/") and cur_dir:
                    tok = f"{cur_dir}/{tok}"
                out.append(tok)
    # 인터프리터 heredoc 이 파일을 쓰면, **그 본문 안에** 등장한 원장을 이 세션이 쓴
    # 것으로 본다. 쓰기 대상 **자리** 규칙은 셸 문법용이라 코드에는 맞지 않으므로,
    # 코드에서는 신호와 경로의 동거를 근거로 삼는다(보수적 — 어느 변수가 그 경로를 들고
    # 쓰는지 정적으로 못 따진다).
    # heredoc 본문과 `-c`/`-e` 인자를 같은 규칙으로 본다 — 둘 다 실행되는 코드다.
    # ⛔ 남은 한계: 따옴표로 감싸지 않은 `-c` 인자, 그리고 코드가 경로를 조각으로 조립하면
    #    (`base + "/gates/plan.md"`) 토큰이 잡히지 않는다. 둘 다 소유를 **놓치는** 방향이다.
    for code in interp_bodies:
        if not any(sig in code for sig in INTERP_WRITE_SIGNALS):
            continue
        for tok in re.findall(_TOKEN, code):
            tok = _expand(tok, env)
            if not tok.startswith("/") and cur_dir:
                tok = f"{cur_dir}/{tok}"
            out.append(tok)
    return out


def _expand(token: str, env: dict) -> str:
    """같은 명령 안의 `NAME=/abs` 대입만 푼다 — `$W/gates/plan.md` 형태(실측 #14·#21)."""
    for name, val in env.items():
        token = token.replace("${" + name + "}", val).replace("$" + name, val)
    return token


def _same_ledger(token: str, ledger_resolved: Path, cwd: Path) -> bool:
    """transcript 의 경로 토큰이 원장을 가리키는가 — **해석 후** 비교.

    ⛔ 문자열 포함 비교는 심볼릭 링크에서 갈린다 — `find_ledgers` 는 `resolve()` 한
       경로를 주는데 Lead 가 쓴 경로는 미해석이다(macOS `/var` → `/private/var`, 워크트리
       심볼릭). self-test 가 정확히 그 축에서 2/2 실패했다(2026-09-11).
    상대경로는 hook 이 받은 `cwd` 기준으로 푼다 — Lead 의 Bash 는 그 cwd 에서 돈다.
    """
    if not token:
        return False
    try:
        cand = Path(token)
        if not cand.is_absolute():
            cand = cwd / cand
        return cand.resolve() == ledger_resolved
    except (OSError, RuntimeError, ValueError):
        return False


def owned_ledgers(transcript_path, ledgers: list, cwd: Path):
    """이 세션의 transcript 가 **쓴** 원장 집합.

    반환 `(owned:set[Path], note:str)`. transcript 가 없거나 읽을 수 없으면
    `(None, 진단)` — 호출부는 **전 원장을 판정**한다(fail-closed). 소유를 모른다고
    통과시키면 자기 원장의 미충족도 함께 통과한다.

    ⛔ 소유의 정의는 "경로가 등장했다"가 아니라 "그 경로에 썼다"다. 진단 세션이
       `grep` 결과나 hook 피드백으로 남의 원장 경로를 출력하는 것은 흔하다.
    """
    if not transcript_path:
        return None, "transcript_path 없음 — 소유 판정 불가, 전 원장 판정"
    tp = Path(str(transcript_path))
    if not tp.is_file():
        return None, f"transcript 를 찾을 수 없다({tp.name}) — 전 원장 판정"
    resolved = {}
    for led in ledgers:
        try:
            resolved[led] = led.resolve()
        except (OSError, RuntimeError):
            resolved[led] = led
    owned = set()
    try:
        with tp.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if TRANSCRIPT_LINE_HINT not in line or '"tool_use"' not in line:
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(ev, dict) or ev.get("type") != "assistant":
                    continue
                msg = ev.get("message") or {}
                content = msg.get("content") if isinstance(msg, dict) else None
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if not (isinstance(blk, dict) and blk.get("type") == "tool_use"):
                        continue
                    name = blk.get("name")
                    inp = blk.get("input") or {}
                    if not isinstance(inp, dict):
                        continue
                    if name in WRITE_TOOLS:
                        target = str(inp.get("file_path") or "")
                        for led, res in resolved.items():
                            if _same_ledger(target, res, cwd):
                                owned.add(led)
                    elif name == "Bash":
                        tokens = _bash_write_targets(str(inp.get("command") or ""))
                        for led, res in resolved.items():
                            if any(_same_ledger(t, res, cwd) for t in tokens):
                                owned.add(led)
                if len(owned) == len(ledgers):
                    break
    except OSError as exc:
        return None, f"transcript 읽기 실패({type(exc).__name__}) — 전 원장 판정"
    return owned, ""


def judge(checker: Path, ledger: Path, budget_left: float):
    """판정기를 `--status` 로 부른다 — CHECK 재실행 없음.

    반환: (exit_code, 요약 한 줄). exit 는 판정기 계약을 그대로 쓴다
    (0 충족 · 1 미충족 · 2 인프라 · 3 원장 계약 위반).
    """
    timeout = min(CHECK_TIMEOUT_S, max(1.0, budget_left))
    try:
        proc = subprocess.run(
            [sys.executable, str(checker), "--status", str(ledger)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None, "판정기 호출 실패"
    out = (proc.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    tail = (out[-1] if out else "") or (err[-1] if err else "")
    return proc.returncode, tail[:200]


def main() -> int:
    started = time.monotonic()
    try:
        raw = sys.stdin.read()
    except OSError:
        return _pass("stdin 읽기 실패")
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return _pass("입력이 JSON 이 아니다")
    if not isinstance(payload, dict):
        return _pass("입력이 객체가 아니다")

    event = payload.get("hook_event_name")
    if event is not None and event not in HOOK_EVENTS:
        return _pass()          # 다른 이벤트에 잘못 배선됐다 — 조용히 통과

    if os.environ.get("FZ_GATES_OFF") == "1":
        return _pass("FZ_GATES_OFF=1 — 판정 생략")

    checker = find_checker()
    if checker is None:
        return _pass("판정기를 찾지 못했다 (설치 손상?)")

    cwd_raw = payload.get("cwd") or os.getcwd()
    try:
        cwd = Path(cwd_raw).resolve()
    except (OSError, RuntimeError):
        return _pass(f"cwd 해석 실패: {cwd_raw!r}")
    if not cwd.is_dir():
        return _pass(f"cwd 가 디렉토리가 아니다: {cwd}")

    gcmod = load_checker_module()
    if gcmod is None or not hasattr(gcmod, "find_ledgers"):
        return _pass("판정기 모듈을 불러올 수 없어 원장 탐색을 건너뛴다")
    env_ledgers = os.environ.get(LEDGER_ENV, "")
    ledgers, discovery_note = gcmod.find_ledgers(cwd, env_ledgers)
    if not ledgers:
        # 진단이 있으면 남긴다 — "찾지 못함"이 조용한 통과로 보이면 안 된다.
        return _pass(discovery_note)

    # ── 소유 분리 — 명시 지정(FZ_GATES_LEDGER)은 그대로, glob 발견분만 transcript 로 가른다 ──
    foreign = []
    owner_note = ""
    if not env_ledgers.strip():
        owned, owner_note = owned_ledgers(payload.get("transcript_path"), ledgers, cwd)
        if owned is not None:
            foreign = [led for led in ledgers if led not in owned]
            ledgers = [led for led in ledgers if led in owned]

    unmet, invalid, notes = [], [], ([discovery_note] if discovery_note else [])
    if owner_note:
        notes.append(owner_note)
    # 남의 원장 — 판정은 하되 **막지 않는다**. 충족도 ABANDON 도 이 세션이 할 일이 아니다.
    for led in foreign:
        left = TOTAL_BUDGET_S - (time.monotonic() - started)
        if left <= 1.0:
            notes.append(f"예산 소진 — {led.name} 미판정")
            break
        code, tail = judge(checker, led, left)
        if code in (1, 3):
            notes.append(f"다른 세션의 원장(막지 않음): {led} — {tail}")
    for led in ledgers:
        left = TOTAL_BUDGET_S - (time.monotonic() - started)
        if left <= 1.0:
            notes.append(f"예산 소진 — {led.name} 미판정")
            break
        code, tail = judge(checker, led, left)
        if code is None or code == 2:
            notes.append(f"{led}: 인프라 — {tail}")
        elif code == 1:
            unmet.append((led, tail))
        elif code == 3:
            invalid.append((led, tail))

    if not unmet and not invalid:
        return _pass("; ".join(notes) if notes else "")

    # ── 무한 루프 방어 ──
    # Stop 을 막으면 Claude 가 계속하고 다시 Stop 에 도달한다. 원장 상태가 그대로면
    # 같은 이유로 또 막히므로 세션이 끝나지 않는다. ⛔ 문서에 `stop_hook_active`
    # 같은 필드가 없어(실측 grep 0건) 스크립트가 직접 방어한다.
    # ⛔ 지문에 **원장 내용도 게이트 요약(`tail`)도 넣지 않는다**. 둘 다 옆 세션이
    #    바꿀 수 있는 값이고, 바뀌면 카운터가 1 로 리셋되어 방어가 발화하지 못한다.
    #    실측(2026-09-11): cwd 하위에서 병렬 세션이 자기 원장을 고치는 동안 한 세션에
    #    지문 4종이 누적되고 8회 차단됐다 — 종료 불가. `tail` 로 바꿔도 같은 결함이
    #    느려질 뿐이다(옆 세션이 게이트를 하나씩 통과할 때마다 tail 이 바뀐다).
    #    ⛔ `tail` 은 계약 위반(exit 3) 일 때 원장 내용에서 온 문자열이기도 하다.
    #    남기는 것은 **어떤 원장이 어떤 종류로 막혔는가** 뿐 — 판정 종류는 판정기
    #    exit 계약(1=미충족 / 3=계약위반)이라 옆 세션의 편집이 건드릴 수 없다.
    #    의도 보존: 이 세션이 원장을 충족시키면 그 원장이 목록에서 빠져 지문이 바뀌고
    #    다시 막는다. sorted 는 탐색 순서가 흔들려도 지문이 같도록 고정한다.
    fingerprint = sha12("|".join(sorted(
        [f"{p}:unmet" for p, _ in unmet] + [f"{p}:invalid" for p, _ in invalid]
    )))
    session = str(payload.get("session_id") or "no-session")
    key = f"{session}|{fingerprint}"
    state = load_state()
    count = int(state.get(key) or 0) + 1

    # 오래된 항목 정리 — 상태 파일이 무한히 자라지 않게
    if len(state) > 200:
        state = {}
    state[key] = count
    if not save_state(state):
        return _pass("루프 방어 상태를 쓸 수 없어 통과 — 무한 block 을 만들지 않는다")

    if count > MAX_BLOCKS:
        return _pass(
            f"같은 상태로 {MAX_BLOCKS}회 막았다 — 통과시킨다. "
            f"미충족 {len(unmet)}건 · 계약 위반 {len(invalid)}건 (수동 확인 필요)")

    lines = []
    for led, tail in invalid:
        lines.append(f"⛔ 원장 계약 위반: {led} — {tail}")
    for led, tail in unmet:
        lines.append(f"미충족 게이트: {led} — {tail}")
    lines += notes
    lines.append("")
    lines.append("게이트를 충족시키거나, 할 수 없으면 원장에 "
                 "`ABANDON: <게이트ID> <이유>` 를 남긴다 (포기 사실이 원장에 보존된다).")
    # 위 목록은 **이 세션의 transcript 가 쓴 원장**만이다(소유 판정). transcript 를 못 읽어
    # 전 원장을 판정한 경우에만 남의 원장이 섞일 수 있어, 그 경우의 출구를 함께 준다.
    if owner_note:
        lines.append(f"소유 판정을 못 했다({owner_note}). 이 세션의 작업이 아닌 원장이 섞였다면 "
                     f"{LEDGER_ENV} 에 판정할 원장 경로만 나열해 범위를 좁힌다 (여러 개는 "
                     f"'{os.pathsep}' 로 구분). 남의 원장에 ABANDON 을 쓰면 그 작업의 수용 기준이 사라진다.")
    lines.append(f"판정: python3 {checker} --status <원장>")
    return _block("\n".join(lines))


# ── self-test ───────────────────────────────────────────────────────────
# ⛔ hook 은 등록해야 발동하지만, 계약(stdin JSON → exit + stderr)은 **등록 없이**
#    검증할 수 있다. 등록 자체는 사용자 소관이므로 여기까지가 우리가 닫을 수 있는
#    경계다 — 그 경계를 실행 가능한 형태로 남긴다(F-040: 1회 실행이 완료 조건).
# (이름, 원장 배치, payload 덮어쓰기, env, 기대 exit, 기대 stderr 조각)
#
# ⛔ **깊이 케이스가 핵심이다.** glob 을 `*/gates/plan.md` 하나로 두면 깊이 1·3·4 를
#    놓치고 **조용히 통과**한다 (2026-08-25 실측: 4종 중 1종만 발견). fixture 가
#    정확히 깊이 2 로만 원장을 만들면 그 결함이 관측되지 않는다 — 이 작업에서
#    "fixture 가 자기 이름의 축을 못 본다"를 여덟 번 만났다.
SELF_TEST_CASES = (
    ("no-gates-dir",   None,               {}, {}, 0, None),
    ("depth1",         "d1:unmet",         {}, {}, 2, '"decision": "block"'),
    ("depth2",         "unmet",            {}, {}, 2, '"decision": "block"'),
    ("depth3",         "d3:unmet",         {}, {}, 2, '"decision": "block"'),
    ("depth4",         "d4:unmet",         {}, {}, 2, '"decision": "block"'),
    ("draft-only",     "draft",            {}, {}, 0, "확정 원장(plan.md)이 없다"),
    ("skip-git",       "git:unmet",        {}, {}, 0, None),
    ("closed-passes",  "closed",           {}, {}, 0, None),
    ("approved-unmet", "approved",         {}, {}, 2, '"decision": "block"'),
    ("kill-switch",    "unmet",            {}, {"FZ_GATES_OFF": "1"}, 0, "FZ_GATES_OFF"),
    ("wrong-event",    "unmet",            {"hook_event_name": "PreToolUse"}, {}, 0, None),
    ("bad-cwd",        "unmet",            {"cwd": "/nonexistent/xyz"}, {}, 0, "디렉토리가 아니다"),
    ("env-missing",    None,               {}, {"FZ_GATES_LEDGER": "/nonexistent/x.md"},
                                              0, "찾을 수 없다"),
    # ⛔ 무한 루프 방어 — 같은 상태로 MAX_BLOCKS 회까지 막고 그 다음엔 통과한다.
    #    `repeat` 은 같은 session_id·같은 원장으로 N 회 발사한 뒤 **마지막** 결과를 본다.
    #    이 케이스가 없으면 방어를 제거해도 self-test 가 통과한다(2026-08-25 실측).
    ("loop-guard",     "unmet",            {}, {}, 0, "회 막았다"),
    # ⛔ **병렬 세션 churn** — 발사 사이에 원장이 진행돼 내용과 게이트 요약이 둘 다
    #    바뀌어도, 판정 종류가 그대로면 카운터가 리셋되면 안 된다. 지문이 내용이나
    #    `tail` 에 기대면 이 케이스가 영원히 block 이고 세션이 끝나지 않는다
    #    (2026-09-11 실측: 한 세션에 지문 4종 누적·8회 차단).
    ("loop-guard-churn", "unmet",          {}, {}, 0, "회 막았다"),
    # ⛔ **소유 판정** — 병렬 세션의 원장이 무관한 세션을 막던 결함(F-188 2회 재관측).
    #    foreign: transcript 에 그 원장을 쓴 tool_use 가 없다 → 경고만, 통과.
    #    owned: Write 로 썼다 → 종전대로 block.  owned-bash: `--finalize` 로 썼다 → block.
    #    transcript-missing: 경로가 없다 → 소유 불명, 전 원장 판정(fail-closed) → block.
    ("foreign-ledger",   "unmet",          {"transcript": "none"}, {}, 0, "다른 세션의 원장"),
    ("owned-ledger",     "unmet",          {"transcript": "write"}, {}, 2, '"decision": "block"'),
    ("owned-bash",       "unmet",          {"transcript": "bash"}, {}, 2, '"decision": "block"'),
    ("transcript-missing", "unmet",        {"transcript_path": "/nonexistent/t.jsonl"}, {}, 2, "전 원장 판정"),
    # ⛔ **기록이 소유를 만들면 안 된다** (2026-09-11 실측 오탐 3건). 레지스트리에 사건을
    #    적는 heredoc 이 본문에 인용한 원장의 소유로 잡혀, 고친 직후의 hook 이 무관한
    #    세션을 다시 막았다. 짝 케이스 `owned-redirect` 는 **진짜 쓰기**가 여전히 잡히는지 본다.
    ("foreign-heredoc-cite", "unmet",      {"transcript": "heredoc-cite"}, {}, 0, "다른 세션의 원장"),
    ("owned-redirect",   "unmet",          {"transcript": "redirect"}, {}, 2, '"decision": "block"'),
    #    owned-bash-cd / owned-bash-var: 실제 Lead 형태 — `cd …/gates` 뒤 상대명, `W=/abs` 뒤 `$W/…`.
    ("owned-bash-cd",    "unmet",          {"transcript": "bash-cd"}, {}, 2, '"decision": "block"'),
    ("owned-bash-var",   "unmet",          {"transcript": "bash-var"}, {}, 2, '"decision": "block"'),
    # ⛔ **fail-open 방어** — 인터프리터 heredoc 을 데이터로 보고 지우면 이 케이스가
    #    exit 0 으로 통과한다. 즉 자기 원장을 파이썬 heredoc 으로 만든 세션은 미충족
    #    게이트를 남긴 채 조용히 끝난다. 오탐 케이스(`foreign-heredoc-cite`)와 짝이다.
    ("owned-py-heredoc", "unmet",          {"transcript": "py-heredoc"}, {}, 2, '"decision": "block"'),
    # ⛔ `-c` 인자도 **코드**다. 이 짝이 없으면 인터프리터 인자로 원장을 만든 세션의
    #    게이트가 통째로 통과한다(2026-09-11 실측 fail-open). 읽기 전용 짝으로 오탐도 함께 막는다.
    ("owned-py-c",       "unmet",          {"transcript": "py-c"}, {}, 2, '"decision": "block"'),
    ("foreign-py-c-read", "unmet",         {"transcript": "py-c-read"}, {}, 0, "다른 세션의 원장"),
)
# 반복 발사가 필요한 케이스 — 이름 → 발사 횟수
REPEAT_CASES = {"loop-guard": MAX_BLOCKS + 1, "loop-guard-churn": MAX_BLOCKS + 1}
# 발사 사이에 원장을 변조하는 케이스 — 판정은 그대로 두고 내용만 바꾼다
MUTATE_CASES = {"loop-guard-churn"}


PROBE_LAYOUT = {
    "d1": "gates", "d3": "a/b/gates", "d4": "a/b/c/gates", "git": ".git/gates",
}


def _write_probe_ledger(root, spec):
    """`spec` = `[배치:]종류`. 배치 미지정이면 깊이 2(`TICKET-0000/gates`)."""
    layout, _, kind = spec.rpartition(":")
    rel = PROBE_LAYOUT.get(layout, "TICKET-0000/gates")
    gates = root / rel
    gates.mkdir(parents=True, exist_ok=True)
    name = "plan.draft.md" if kind == "draft" else "plan.md"
    state = "closed" if kind == "closed" else "active"
    approved = "APPROVED: yes\n" if kind == "approved" else ""
    body = ("# Gates: self-test\n"
            f"ROOT: {gates.parent}\n"
            f"STATE: {state}\n"
            f"{approved}"
            "Scope: hook 계약 검증\n\n"
            "- [ ] G1: 판정 대상\n"
            "  CRITERION: 사람이 읽는 합격 조건\n"
            "  CHECK: echo ok\n"
            "  EXPECT: ok\n"
            "  CWD: /usr\n"
            "  EVIDENCE: pending\n")
    target = gates / name
    target.write_text(body, encoding="utf-8")
    if kind == "approved":
        # ⛔ 닭-달걀: 도장을 계산하려면 파싱해야 하는데 `APPROVED: yes` 면 파싱이
        #    전수 도장을 요구한다. `--finalize` 가 정확히 그 순서를 아는 유일한 경로다
        #    — draft 로 쓰고 확정을 맡긴다. (직접 계산하려다 LedgerError 를 봤다)
        target.write_text(body.replace("APPROVED: yes\n", ""), encoding="utf-8")
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "gate_check.py"),
             "--finalize", str(target)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, timeout=30, check=False)


def _write_probe_transcript(root, kind: str, ledger: Path) -> Path:
    """세션 기록 흉내 — `none` 은 원장 경로를 **출력만** 한 줄(grep 결과 인용), `write` 는
    `Write` tool_use, `bash` 는 `--finalize` Bash tool_use. 진단 세션이 남의 원장 경로를
    인용하는 것이 소유로 잡히면 안 되므로 `none` 에도 경로를 넣는다."""
    tp = root / "transcript.jsonl"
    def tool_use(name, inp):
        return json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": name, "input": inp}]}}, ensure_ascii=False)
    lines = [json.dumps({"type": "user", "message": {"content": f"미충족 게이트: {ledger}"}},
                        ensure_ascii=False),
             tool_use("Bash", {"command": f"grep -n STATE {ledger}"})]
    if kind == "write":
        lines.append(tool_use("Write", {"file_path": str(ledger), "content": "x"}))
    elif kind == "bash":
        lines.append(tool_use("Bash", {"command": f"python3 gate_check.py --finalize {ledger}"}))
    elif kind == "bash-cd":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent}\ncp plan.draft.md plan.md\n"
                                                  f"python3 gate_check.py --finalize plan.md"}))
    elif kind == "bash-var":
        lines.append(tool_use("Bash", {"command": f"W={ledger.parent.parent}\n"
                                                  f"python3 gate_check.py --confirm G1 \"$W/gates/plan.md\""}))
    elif kind == "heredoc-cite":
        # ⛔ 발견 레지스트리에 사건을 기록하는 모양 — 원장 경로는 **본문에 인용**될 뿐이고
        #    리다이렉션 대상은 다른 파일이다. 이것이 소유로 잡히면 기록이 소유를 만든다.
        # ⛔ 본문에 **코드 인용**을 넣는다. 실제 레지스트리 항목은 수정안을 코드로 인용하므로
        #    `write_text(` 같은 쓰기 신호가 문서 안에 들어온다 — 신호만 보고 코드로 판정하면
        #    이 케이스가 소유로 잡힌다(2026-09-11 실측 오탐의 정확한 모양).
        lines.append(tool_use("Bash", {"command":
            f"cat > {root}/finding.md <<'EOF'\n막은 원장: {ledger}\n판정: {ledger} — G1\n"
            "수정안: p.write_text(s) 로 원장을 갱신했다\nEOF"}))
    elif kind == "redirect":
        lines.append(tool_use("Bash", {"command": f"echo 'ABANDON: G1 사유' >> {ledger}"}))
    elif kind == "py-c":
        # ⛔ heredoc 이 아닌 인터프리터 인자. 이 형태를 놓치면 자기 원장을 이렇게 만든
        #    세션이 소유 0 이 되어 미충족 게이트를 남긴 채 끝난다(fail-open).
        lines.append(tool_use("Bash", {"command":
            f"""python3 -c "import pathlib; pathlib.Path('{ledger}').write_text('x')" """.strip()}))
    elif kind == "py-c-read":
        # 짝 케이스 — 같은 `-c` 형태인데 **읽기만** 한다. 소유가 되면 안 된다.
        lines.append(tool_use("Bash", {"command":
            f"""python3 -c "print(open('{ledger}').read())" """.strip()}))
    elif kind == "py-heredoc":
        # ⛔ 이 리포가 파일을 고치는 관용구. heredoc 본문을 데이터로 보고 지우면 이 쓰기가
        #    사라지고, 자기 원장을 이렇게 만든 세션의 게이트가 전부 통과한다(fail-open).
        lines.append(tool_use("Bash", {"command":
            "python3 - <<'PY'\nimport pathlib\n"
            f"pathlib.Path('{ledger}').write_text('x')\nPY"}))
    tp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tp


def self_test() -> int:
    import shutil
    import tempfile
    me = str(Path(__file__).resolve())
    # ⛔ 상태 파일을 격리한다 — 사용자 실 상태를 오염시키면 안 되고,
    #    이전 회차 카운트가 남으면 unmet-blocks 가 통과로 뒤집힌다.
    home = Path(tempfile.mkdtemp(prefix="fz-hook-home-"))
    passed, failed = 0, []
    for name, kind, override, env, want_exit, want_err in SELF_TEST_CASES:
        d = Path(tempfile.mkdtemp(prefix="fz-hook-cwd-"))
        try:
            if kind is not None:
                _write_probe_ledger(d, kind)
            payload = {"hook_event_name": "Stop", "cwd": str(d),
                       "session_id": f"selftest-{name}"}
            override = dict(override)
            transcript_kind = override.pop("transcript", None)
            if transcript_kind is not None:
                led = d / "TICKET-0000" / "gates" / "plan.md"
                payload["transcript_path"] = str(_write_probe_transcript(d, transcript_kind, led))
            payload.update(override)
            child = dict(os.environ)
            child["HOME"] = str(home)
            child.pop("FZ_GATES_OFF", None)
            child.update(env)
            shots = REPEAT_CASES.get(name, 1)
            for shot in range(shots):
                if name in MUTATE_CASES and shot > 0:
                    # 병렬 세션이 자기 원장을 진행시키는 것을 흉내낸다. 게이트를 하나
                    # 더하면 **내용 해시도 `tail`(마지막 게이트 id)도** 바뀌지만 판정
                    # 종류는 미충족 그대로다 — 지문이 둘 중 무엇에라도 기대면 카운터가
                    # 리셋되어 이 케이스가 영원히 block 된다.
                    for led in d.glob("**/gates/plan*.md"):
                        led.write_text(
                            led.read_text()
                            + f"\n- [ ] CHURN{shot}: 옆 세션이 더한 게이트\n"
                              "  CRITERION: 판정 종류는 미충족 그대로\n"
                              "  CHECK: echo ok\n"
                              "  EXPECT: ok\n"
                              "  CWD: /usr\n"
                              "  EVIDENCE: pending\n",
                            encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, me], input=json.dumps(payload).encode(),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=child, timeout=60)
            err = (proc.stderr or b"").decode("utf-8", "replace")
            why = []
            if proc.returncode != want_exit:
                why.append(f"exit {proc.returncode} (기대 {want_exit})")
            if want_err and want_err not in err:
                why.append(f"stderr 에 {want_err!r} 없음")
            if why:
                failed.append(f"{name}: {'; '.join(why)}")
            else:
                passed += 1
        finally:
            shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)

    for f in failed:
        print(f"  FAIL {f}", file=sys.stderr)
    total = len(SELF_TEST_CASES)
    print(f"stop-hook self-test {passed}/{total} passed")
    return EXIT_PASS if not failed else 1


if __name__ == "__main__":
    # ⛔ `sys.exit()` 를 try 안에 두면 안 된다. `SystemExit` 은 `BaseException` 이라
    #    최후 방어가 그것을 잡아 exit 0 으로 바꾼다 — **차단이 영원히 발화하지 않는다.**
    #    실측(2026-08-25): `decision=block` JSON 은 stderr 로 나갔는데 exit 은 0 이었다.
    #    차단 코드가 있는데 발화하지 않는 것, 이 작업에서 다섯 번째로 만난 축이다.
    if "--self-test" in sys.argv[1:]:
        sys.exit(self_test())
    try:
        _code = main()
    except Exception as exc:                           # noqa: BLE001
        # 최후 방어 — 예상 외 오류로 세션을 감금하지 않는다. `SystemExit` 은 여기 안 온다.
        print(f"[gate-stop-hook] 예상 외 오류로 통과: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        _code = EXIT_PASS
    sys.exit(_code)
