#!/usr/bin/env python3
# diff-parse: not-a-diff — `startswith("-")` 는 판정기 호출 셸 단어의 플래그 판별이다(--only · --set-state · env 옵션).
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
다른 미완 작업을 놓치지 않는다. `STATE: closed`와 승인·미착수 `STATE: planned`는 판정기 `--status`가
no-op으로 걸러낸다.

**차단 = 이 세션이 쓴 원장만 (2026-09-11, F-188 2회 재관측).** glob 은 티켓별
워크트리를 한 루트에 두는 환경에서 **병렬 세션의 원장**까지 집어 무관한 세션의
종료를 막았다. 소유 판정은 배선 없이 가능하다 — 입력의 `transcript_path` 가 이 세션의
기록이고, 거기에 그 원장을 `Write`/`Edit` 하거나 `cp`·`>` 로, 또는 원장을 쓰는 판정기 호출
(`--finalize` · `--confirm` · `--set-state` · `--only` · `--reverify` · 플래그 없는 기본 실행 — F-377)로 쓴
tool_use 가 있으면 이 세션의 원장이다. `--status`(`--only` 와 함께여도) · `--discover` 같은 읽기는 소유가 아니다.
원장 인자가 변수면 같은 명령의 대입과 그 명령이 source 한 파일의 대입으로 푼다(F-422). 남의 미충족 원장은
**경고로만** 인쇄한다.
⛔ transcript 를 못 읽으면 전 원장을 판정한다(fail-closed) — 소유를 모를 때 통과시키면 자기 원장도 놓친다. 원장을 쓰는
판정기 호출인데 원장 인자를 풀지 못하면('대상 미상 쓰기') 그 쓰기가 돌던 폴더(transcript 줄의 cwd) 아래 원장과, 그 명령
글자에 적힌 원장 경로 리터럴(`L=$(realpath ../w/gates/plan.md)` 의 `../w/gates/plan.md`)을 그 폴더 기준으로 푼 원장을 판정한다 —
글자에 원장 경로가 없는 밖의 원장은 막지 않는다(F-554 · 잔존: `$(find ..)` 처럼 경로를 글자로 쓰지 않은 폴더 밖 쓰기). `FZ_GATES_LEDGER` 명시 지정은 소유 판정을
건너뛴다(명시가 우선).

**발견 상한 없음 · 소유 원장 먼저 (F-378 · F-404).** 발견한 원장 전부에 소유 판정을 하고, 소유 원장을 예산(45초)
안에서 먼저 판정한다. 상한(`FOREIGN_JUDGED_MAX`)은 남의 원장 판정에만 둔다. 예산이 다해 판정하지 못한 소유 원장이
남으면 통과하지 않고 그 수 · 이유를 사유로 막는다(루프 방어 `MAX_BLOCKS` 는 같다).

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

try:                                    # 공용 토크나이저(F-458) — 없으면 None 이고 Bash 원장 쓰기 판정은 '대상 미상' 으로 끝난다
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import shell_tokens
except Exception:                       # noqa: BLE001 — 권한 · 구문 오류도 같다(ImportError 만 잡으면 훅이 죽는다)
    shell_tokens = None

ROOT = Path(__file__).resolve().parent.parent  # scripts/ → 플러그인 루트

HOOK_EVENTS = ("Stop", "SubagentStop")
# ⛔ 원장 발견(glob 깊이·SKIP_DIRS)과 `FZ_GATES_LEDGER` 는 **판정기가 소유한다** —
#    `gate_check.py`의 `find_ledgers` · `LEDGER_ENV`. 여기에 복제하면 두 구현이 갈린다(이름도 판정기 상수를 읽는다).
CHECK_TIMEOUT_S = 20                   # 판정기 1회 호출 상한
TOTAL_BUDGET_S = 45                    # 전체 예산 — 소유 원장을 먼저 쓰고, 남는 만큼 남의 원장을 본다
# 예산을 **줄이기만** 하는 시험 노브(0 ≤ 값 < TOTAL_BUDGET_S 일 때만 쓴다). 느린 판정기에서 미판정 소유 원장 처리를 재려고 둔다
BUDGET_ENV = "FZ_GATES_HOOK_BUDGET_S"
FOREIGN_JUDGED_MAX = 8                 # 남의 원장 판정 상한 — 막지 않는 원장에 예산을 다 쓰지 않게. ⛔ 소유 원장에는 상한이 없다
MAX_BLOCKS = 2                         # 같은 상태로 이 횟수까지만 막는다
# 사유 크기 — 차단 사유는 막을 때마다 Claude 컨텍스트에 실린다(F-360 · EC-07).
# 한 줄 ≈ 접두 + 원장 경로(~100) + 요약(≤400) ≈ 500자 → 전체 상한 4000 ≈ 8줄. 원장 발견에 상한이 없으므로(F-378) 소유
# 원장이 많으면 이 상한이 사유를 묶는다 — 자를 때는 본문 끝(진단 · 남의 원장 경고)부터 빼고 `…외 N줄 생략` 으로 수를 남기며,
# 소유 원장 줄이 가장 늦게 빠진다. 남의 원장 경고는 3줄(≈1500자)을 넘으면 한 줄로 접는다 — 없으면 원장 수만큼 수십 KB 가 실린다.
SUMMARY_MAX_CHARS = 400                # 원장 하나의 판정 요약 상한
MANUAL_HINT_MAX_CHARS = 600            # MANUAL 안내 줄의 원장 · id 목록 상한 — 넘는 원장은 `…외 N개 원장` (안내 문장 자리를 남긴다)
UNMET_IDS_SHOWN = 8                    # 요약에 싣는 미충족 id 상한 — 넘으면 `…외 N건`
FOREIGN_NOTES_FOLD = 3                 # 남의 원장 경고가 이보다 많으면 한 줄로 접는다
REASON_MAX_CHARS = 4000                # 차단 사유 전체 상한 — 넘는 본문 줄은 `…외 N줄 생략`
STATE_FILE = Path.home() / ".fz" / "stop-hook-state.json"
# 소유 판정 — transcript 의 tool_use 중 원장을 **쓴** 것만 센다. 읽기·grep·hook 피드백
# 인용은 제외(진단 세션이 남의 원장 경로를 출력만 해도 소유가 되면 안 된다).
WRITE_TOOLS = ("Write", "Edit", "MultiEdit")
# 선필터 — 이 조각이 하나도 없는 줄은 파싱하지 않는다(47MB 기록 실측).
# ⛔ "gates/" 로 두면 `cd …/gates⏎cp plan.draft.md plan.md` 줄이 파싱 전에 버려진다 — 실측 #10·#24·#28.
# ⛔ "gates" 하나로 두면 원장 경로를 source 한 env 파일에서 받는 쓰기(`. env.sh && python3 "$G" --only S1 "$L"`)가
#    파싱 전에 버려진다(F-422) — 판정기 · 원장 이름에 더해 Bash 줄의 `.`/`source` 도 본다.
TRANSCRIPT_LINE_HINTS = ("gates", "gate_check", "plan.md", "$'")   # `$'…'` 는 경로 글자를 이스케이프로 감출 수 있다(F-458)
SOURCE_LINE_RE = re.compile(r'(?:^|[\s;&|("]|\\n)(?:\.|source)\s+[^\s;&|]')   # JSON 으로 인코딩된 줄 위에서 본다
_TOKEN = r"[^\s\"'`;|&<>()]*plan\.md"              # 원장 경로 토큰 — 상대명 `plan.md` 도 허용
# ⛔ 실측(2026-09-11, TKT-6894 세션 4회): Lead 는 `cd …/gates` 뒤 `cp plan.draft.md plan.md` ·
#    `--finalize plan.md` 처럼 **상대명**으로 쓴다. `gates/plan.md` 접미를 요구하면 진짜 소유
#    세션이 전부 "다른 세션" 으로 분류돼 미충족이 통과한다(오라클 exit 0). 세그먼트별 `cd` 와
#    `NAME=/abs` 대입을 추적해 절대경로로 되돌린다.
# `( cd …/gates && …` · `{ cd …; …` 처럼 서브셸 · 묶음 여는 괄호 뒤의 cd 도 본다
CD_RE = re.compile(r"^\s*[({]?\s*(?:cd|pushd)\s+[\"']?([^\s\"';&|()]+)")
# `NAME=값` · `export NAME=값` — 값은 대입 시점의 env 로 풀어 둔다(`L=$W/gates/plan.md` · `G="${FZ_PLUGIN_ROOT}/…/gate_check.py"`)
ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?(\w+)=[\"']?([^\s\"';&|]+)")
# 따옴표 값에 공백이 있으면 ASSIGN_RE 는 첫 단어만 잡는다 — 그 변수는 미상으로 둔다(`LIST="A B"` 를 A 로 믿지 않는다)
MULTIWORD_ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?\w+=([\"'])[^\"']*\s")
# 세그먼트 앞머리의 `NAME=값` 하나 — 따옴표 값 · `$( )` · 백틱 값을 한 단어로 본다(셸 단어 규칙의 근사)
_PREFIX_ASSIGN_RE = re.compile(r"""\s*\w+=(?:"(?:\\.|[^"\\])*"|'[^']*'|\$\([^)]*\)|`[^`]*`|[^\s;&|"'`])*""")


def _temp_env_prefix(seg: str) -> bool:
    """`NAME=값 명령 …` 인가 — 앞머리 대입 뒤에 명령 단어가 오면 그 대입은 그 명령의 환경일 뿐 셸 변수가 아니다.
    셸은 인자(`"$NAME"`)를 대입 **전** 값으로 편다 — env 에 먼저 넣으면 다른 원장을 소유로 읽는다(F-554 리뷰).
    `export` 뒤 단어는 전부 이름 · 대입이라 명령이 아니다."""
    if re.match(r"\s*export\s", seg):
        return False
    pos = 0
    while True:
        m = _PREFIX_ASSIGN_RE.match(seg, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
    rest = seg[pos:].strip()
    return bool(rest) and not rest.startswith("#")
# `for NAME in …` 루프(F-457) — 몸체 조각에서만 값을 대입한다. 지원 밖(몸체 재대입 · break · continue · 중첩 · done 없음)과
# done 뒤는 미상이다 — 실제 값은 셸만 안다(break 뒤 값 · 몸체 재대입이 마지막 값 추정을 틀리게 한다).
FOR_RE = re.compile(r"^\s*for\s+([A-Za-z_]\w*)\s+in\s+(.*?)\s*$")
LOOP_DO_RE = re.compile(r"^\s*do\b\s*")
LOOP_OPEN_RE = re.compile(r"^\s*(?:for|while|until)\b")
LOOP_DONE_RE = re.compile(r"^\s*done\b")
FUNC_DEF_RE = re.compile(r"(?:^|\s)(?:function\s+\w+|\w+\s*\(\s*\))\s*\{")
LOOP_COMPOUND_RE = re.compile(r"^\s*(?:(?:if|then|elif|else|fi|case|esac|while|until|select|function|\[\[|!)(?:\s|$)|[(){}])")
LOOP_BODY_BANNED = frozenset((".", "source", "eval", "exec", "break", "continue"))
# 셸 상태(변수 · 작업 폴더 · 위치 인자 · 옵션)를 바꾸는 내장 명령 — 몸체에 있으면 반복마다 env 가 달라 같은 env 로 펼칠 수 없다.
# bash 내장 목록에서 닫힌 집합이다. 대입 단어(`D=…` · `D+=…`)와 `printf -v` 도 같다
LOOP_STATEFUL = frozenset(("cd", "pushd", "popd", "export", "unset", "read", "declare", "typeset", "local", "readonly",
                           "let", "shift", "getopts", "mapfile", "readarray", "set", "shopt", "alias", "unalias", "trap",
                           "umask", "hash", "enable", "builtin"))
# 인자 자리에서도 셸 상태를 바꾸는 확장 — 산술(`$((D+=1))`) · 기본값 대입(`${X:=…}` · `${X=…}`). 명령 머리가 변수(`"$C" …`)인
# 몸체는 무엇을 부르는지 모르므로 위 목록과 대조할 수 없다 — 둘 다 지원 밖(리뷰 R2)
LOOP_SIDE_EFFECT_RE = re.compile(r"\$\(\(|\$\{\w+:?=")
# `. FILE` · `source FILE` — 그 파일의 대입을 env 에 더한다(F-422). 파일은 훅이 도는 **지금** 의 내용이다
SOURCE_RE = re.compile(r"^\s*(?:\.|source)\s+[\"']?([^\s\"';&|]+)")
SOURCE_ANY_RE = re.compile(r"(?:^|[;&|(])\s*(?:\.|source)\s+\S", re.M)
SOURCE_MAX_BYTES = 65536
# `${N:-…}` · `${N:=…}` · `${N:?…}` 는 N 이 있으면 N 의 값이다. `${N:+…}` · `${N+…}` 는 다른 값이라 풀지 않는다(미상)
_VAR_RE = re.compile(r"\$\{(\w+)(?::?[-?=][^}]*)?\}|\$(\w+)")
# 판정기 호출 — 원장을 쓰는 플래그(F-377). 이름은 판정기 파일명. 옵션 어휘(`GATE_OPTS` — argparse 의 `--help` 포함)와 값을 받는
# 옵션은 `gate_check._dispatch` 의 add_argument 와 같다 — self-test 가 판정기 소스와 두 집합을 대조한다(갈리면 새 쓰기 옵션을 놓친다)
GATE_CHECK_NAME = "gate_check.py"
GATE_OPTS = frozenset(("--status", "--reverify", "--confirm", "--set-state", "--self-test", "--from-plan", "--root", "--out", "--impl-root",
                       "--discover", "--cross-session", "--oracle-fields", "--finalize", "--verdict-check", "--affected-by",
                       "--criterion-drift", "--only", "--scenario-check", "--manifest-sha",
                       "--budget", "--baseline-probe", "--allow-pass", "--no-baseline", "--help"))
GATE_VALUE_OPTS = frozenset(("--confirm", "--set-state", "--from-plan", "--root", "--out", "--impl-root", "--discover",
                             "--verdict-check", "--affected-by", "--criterion-drift", "--only", "--budget", "--allow-pass",
                             "--no-baseline", "--scenario-check", "--manifest-sha"))
GATE_WRITE_FLAGS = frozenset(("--finalize", "--confirm", "--set-state", "--only", "--reverify"))
_PY_RE = re.compile(r"^python[0-9.]*$")
_ASSIGN_WORD_RE = re.compile(r"^\w+=")
# 명령 자리 앞에 올 수 있는 단어 — 감싸개(`env -i` 포함)와 셸 예약어(`for …; do <명령>` 의 `do`)
_CMD_PREFIX_WORDS = frozenset(("env", "command", "exec", "time", "nohup", "-i", "-", "do", "then", "else", "elif", "!"))
_REDIR_ONLY_RE = re.compile(r"^(?:[0-9]*>>?|<|&>>?)$")           # 대상이 다음 단어인 리다이렉션
_REDIR_RE = re.compile(r"^(?:[0-9]*>>?|<|&>>?|[0-9]*>&)")           # 대상이 붙은 리다이렉션(`>/dev/null` · `2>&1`)
_UNRESOLVED_RE = re.compile(r"[$`*]")                          # 풀리지 않은 변수 · 치환 · 글롭
# 원장 인자 · 루프 값은 이 글자만으로 된 경로일 때만 '풀렸다' 로 본다 — 허용 목록이다(F-458). 차단 목록은 `~` · `[…]` ·
# `{a,b}` · `?` 처럼 셸이 바꾸는 꼴을 하나 빠뜨릴 때마다 남의 원장으로 판정해 Stop 을 통과시켰다(fail-open)
# 공백은 따옴표로 묶은 한 단어 안에서만 온다(따옴표 값에 공백이 있는 대입은 미상 표식 — `_assign`) — 공백 든 원장 경로를 받는다(리뷰 R6)
_RESOLVED_PATH_RE = re.compile(r"^(?!-)[\w./@%+=:, -]+$")         # `-` 로 시작하면 변수로 들어온 옵션이다(`"$OPT"`)
# ⛔ heredoc 본문이 **데이터인지 코드인지**는 어디에 먹이는가로 갈린다. `cat`/`tee` 로
#    가는 본문은 데이터라, 명령으로 읽으면 문서에 인용한 경로가 쓰기로 잡힌다(F-193 오탐).
#    반대로 `python3 -`/`bash -` 로 가는 본문은 **실행되는 코드**이고 이 리포가 파일을
#    고치는 관용구가 정확히 그것이다 — 데이터로 보고 지우면 진짜 쓰기를 놓쳐, 자기 원장을
#    그렇게 만든 세션이 소유 0 이 되고 게이트가 통째로 무력해진다(fail-open).
LEDGER_TAIL_RE = re.compile(r"plan(?:\.draft)?\.md$")
# 쓰기 자리 판정은 fz-guard 의 write_sites 를 빌린다(P4 와 같은 판정 — 한쪽만 고치면 갈린다). 대상 **자리**에 온 경로만 소유다 —
# "명령 어딘가에 경로가 있다" 는 소유가 아니다(F-193). ⛔ 읽기 표 밖 이름(인터프리터 · 표 밖 명령)은 대상 미상 쓰기다 — 코드 안
# 쓰기 신호를 나열하던 판(INTERP_WRITE_SIGNALS)은 `dash -c` · `bash -c 'cd …'` 를 놓쳤다(r5 006 · 012). 판정기 호출은 _gate_call 이 맡는다
UNKNOWN_NAME_WRITES = True
GUARD_PATH = ROOT / "mods" / "fz-guard" / "hooks" / "guard.py"
_GUARD = []

EXIT_PASS, EXIT_BLOCK = 0, 2
JUDGE_TIMEOUT = "timeout"              # judge() 의 시간 초과 표지 — 판정기 exit 코드와 겹치지 않는 값
# 판정기 `--status` 의 요약 줄 — 미충족 id 는 이 줄 **아래**에 한 줄씩 온다(`gate_check.py` evaluate 끝).
# 게이트별 줄은 `  UNMET <id>: …` 라 콜론이 id 뒤에 와서 이 꼴과 겹치지 않는다.
UNMET_LINE_RE = re.compile(r"^UNMET: (\d+) \(")
# 그 아래 id 줄 — 판정기 게이트 id 문자 집합(`gate_check.GATE_RE`) 그대로. 이 꼴이 끊기면 목록 끝이다
UNMET_ID_RE = re.compile(r"^\s+([A-Za-z0-9_.-]+)$")


def _pass(diagnostic: str = "") -> int:
    """통과. 진단은 stderr로만 — Claude에게 피드백되지만 차단은 아니다."""
    if diagnostic:
        print(f"[gate-stop-hook] {diagnostic}", file=sys.stderr)
    return EXIT_PASS


def _manual_unmet(led) -> list:
    """확인을 기다리는 MANUAL 게이트 id — 원장에서 `MANUAL:` 줄이 있고 `CONFIRMED:` 가 없으며 ABANDON · DEFER 되지 않은 게이트(F-202).
    ⛔ 판정기 꼬리(`… — G1, G2 …외 N건`)를 파싱하지 않는다 — id 상한(UNMET_IDS_SHOWN)에 잘린 MANUAL 게이트를 놓친다.
    안내 문구용이다 — 읽지 못하면 빈 목록(안내 줄을 더하지 않을 뿐 차단은 그대로)."""
    try:
        text = Path(str(led)).read_text(encoding="utf-8")
    except OSError:
        return []
    gone = set(re.findall(r"^(?:ABANDON|DEFER): ([A-Za-z0-9_.-]+)", text, re.M))
    out = []
    for m in re.finditer(r"^- \[[ x]\] ([A-Za-z0-9_.-]+):.*\n((?:[ \t]+.*\n?)*)", text, re.M):
        body = m.group(2)
        if (re.search(r"^[ \t]+MANUAL:", body, re.M) and not re.search(r"^[ \t]+CONFIRMED:", body, re.M)
                and m.group(1) not in gone):
            out.append(m.group(1))
    return out


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


def _write_sites(cmd: str, fragment: bool = False, known=()):
    """fz-guard write_sites — 못 불러오거나 못 읽으면 None(호출부가 '대상 미상' 으로 본다 · 정규식으로 돌아가지 않는다)."""
    if not _GUARD:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("fz_guard_sites", GUARD_PATH)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _GUARD.append(mod if callable(getattr(mod, "write_sites", None)) and mod.shell_tokens is not None else None)
        except Exception:                                  # noqa: BLE001 — 훅은 어떤 오류로도 세션을 감금하지 않는다
            _GUARD.append(None)
    return _GUARD[0].write_sites(cmd, fragment, known) if _GUARD[0] is not None else None


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


def _gate_call_writes(flags: set) -> bool:
    """판정기 호출이 원장을 쓰는가 — `gate_check._dispatch` 의 분기 순서를 그대로 따른다(F-377).

    ⛔ `--status` 는 `--only` 와 함께여도 읽기다(`--status --only` 는 판정만). 반대로 `--finalize` · `--confirm` ·
       `--set-state` 는 `--status` 보다 먼저 분기하므로 같이 있어도 쓰기다. 플래그 없는 기본 실행 · `--only` ·
       `--reverify` 는 CHECK 를 돌려 증거를 쓴다.
    """
    if flags & {"-h", "--help", "--self-test", "--discover", "--from-plan", "--cross-session", "--oracle-fields",
                 "--baseline-probe", "--scenario-check"}:
        return False                      # `--from-plan` 이 쓰는 `--out` 은 호출부가 쓰기 대상으로 본다(_gate_out) · 기준선은 옆 파일만 쓴다 · 시나리오 대조는 manifest 를 읽기만 한다
    if "--finalize" in flags:
        return True
    if "--verdict-check" in flags:
        return False
    if flags & {"--confirm", "--set-state"}:
        return True
    return "--status" not in flags


def _gate_opt(name: str):
    """`--xxx` → 판정기 옵션 이름. argparse(`allow_abbrev` 기본)처럼 정확 일치, 다음은 유일한 접두 일치로 푼다(`--set` →
    `--set-state` · `--stat` → `--status`). 못 풀면(어휘 밖 · 모호) None — argparse 가 그 호출을 거부하므로 원장을 쓰지 못한다."""
    if name in GATE_OPTS:
        return name
    hits = [o for o in GATE_OPTS if o.startswith(name)]
    return hits[0] if len(hits) == 1 else None


def _gate_call(words: list, env: dict, unresolved_prog: bool = False):
    """한 세그먼트의 단어열이 판정기 호출이면 `(쓰기 여부, 원장 인자 | None, 판정기 이름 확인 여부)`, 아니면 None.

    판정기는 **명령 자리**에 와야 한다 — 맨 앞(`NAME=값` 접두 · `env`/`exec` 등 감싸개 · `do`/`then` 같은 셸 예약어 뒤) 또는
    `python3` 의 첫 인자. `python3 -` · `-c` · `-m` 이면 뒤의 단어는 stdin 스크립트 · 코드 · 모듈의 인자라 호출이 아니다.
    `grep … gate_check.py plan.md` 처럼 인자로 지나가는 이름은 호출이 아니다. 판정기 경로는 변수(`"$G"`)여도 대입을
    풀어 파일명으로 가린다. 옵션은 판정기 argparse 처럼 푼다(`_gate_opt`) — 하나라도 못 풀면 argparse 가 거부할 호출이라 None.
    `unresolved_prog` 면 파일명 자리가 풀리지 않은 변수(`"$G"` — 같은 명령이 source 한 파일을 못 읽었다)인 단어도 후보로
    보되, 쓰기 플래그나 원장꼴(`plan.md`) 인자가 있을 때만이다 — 호출부가 그 쓰기를 '대상 미상' 으로 보낸다.
    ⛔ 좁힌 이유: 못 읽은 source 뒤의 무관한 명령(`python3 $X/tool.py --arm B …`)까지 후보로 보면 원장을 안 쓴 세션이
       fail-closed 로 남의 원장에 막힌다(실 transcript 1건에서 '대상 미상 쓰기' 293건). 남는 한계: source 를 못 읽은 뒤의
       플래그 없는 기본 실행(`python3 "$G" "$L"`)은 후보가 아니다.
    """
    i = 0
    while i < len(words):
        w = words[i]
        if _ASSIGN_WORD_RE.match(w) or w in _CMD_PREFIX_WORDS:
            i += 1
        elif w == "-u":                    # env -u NAME
            i += 2
        else:
            break
    if i >= len(words):
        return None
    if _PY_RE.match(os.path.basename(words[i])):
        i += 1
        while i < len(words) and words[i].startswith("-"):
            if words[i] in ("-", "-c", "-m"):
                return None               # stdin 스크립트 · 코드 문자열 · 모듈 — 뒤의 단어는 그 프로그램의 sys.argv 다
            i += 2 if words[i] in ("-X", "-W") else 1
        if i >= len(words):
            return None
    prog = _expand(words[i], env)
    known = os.path.basename(prog) == GATE_CHECK_NAME
    if not known and not (unresolved_prog and _UNRESOLVED_RE.search(os.path.basename(prog))):
        return None                       # 파일명이 풀린 다른 스크립트(`$X/tool.py`)는 판정기가 아니다
    flags, positional, rest, k, opts_done = set(), [], words[i + 1:], 0, False
    while k < len(rest):
        a = rest[k]
        if _REDIR_ONLY_RE.match(a):
            k += 2
        elif _REDIR_RE.match(a):
            k += 1
        elif a == "--" and not opts_done:
            opts_done = True              # argparse — 뒤는 전부 위치 인자
            k += 1
        elif a.startswith("--") and not opts_done:
            name = _gate_opt(a.split("=", 1)[0])
            if name is None:
                return None               # argparse 가 거부한다(exit 2) — 원장을 쓰지 못한다
            flags.add(name)
            k += 2 if (name in GATE_VALUE_OPTS and "=" not in a) else 1
        elif a.startswith("-") and len(a) > 1 and not opts_done:
            if a != "-h":
                return None               # 판정기의 짧은 옵션은 -h 뿐 — 나머지는 argparse 가 거부한다
            flags.add(a)
            k += 1
        else:
            positional.append(a)
            k += 1
    led = positional[0] if positional else None
    if not known and not (flags & GATE_WRITE_FLAGS or (led and re.search(_TOKEN, _expand(led, env)))):
        return None
    return _gate_call_writes(flags), led, known


def _words(seg: str):
    """셸 단어 — 공용 토크나이저(F-458)가 따옴표를 벗긴다. 못 읽으면(표 밖 꼴 · 토크나이저 없음) None — 호출부가 '대상 미상' 으로 본다.
    ⛔ 공백 분리로 물러서지 않는다 — 예전 근사기는 따옴표 안에서 잘린 조각을 글자 그대로 읽었다."""
    if shell_tokens is None:
        return None
    ws = shell_tokens.words(seg, fragment=True)
    return None if shell_tokens.is_unknown(ws) else ws


def _source_env(path_tok: str, env: dict, cur_dir, cwd) -> bool:
    """`. FILE` · `source FILE` — 그 파일의 `NAME=값` · `export NAME=값` 줄을 env 에 더한다(F-422).

    ⛔ 훅이 도는 **지금** 의 파일 내용이다 — 세션 뒤 파일이 바뀌거나 지워지면 그 대입은 풀리지 않고, 그 변수를 원장
       인자로 쓴 판정기 쓰기는 '대상 미상 쓰기' 로 간다(그 쓰기가 돌던 폴더 아래 원장 판정). 한 단계만 따라가고 크기 상한을 둔다.
    경로는 같은 명령의 대입 → 남은 `$HOME` 등은 훅 환경(Bash 도구 셸과 HOME 이 같다) → `~` 순으로 푼다. ⛔ 훅 환경 · `~` 는
    source 경로에만 쓴다 — 원장 인자에 훅 환경을 섞으면 명령 밖 변수(셸 프로필)를 '풀린 것' 으로 읽는다.
    반환: 파일을 읽었는가.
    """
    p = Path(os.path.expanduser(_expand(_expand(path_tok, env), os.environ)))
    if not p.is_absolute():
        base = Path(cur_dir) if cur_dir else Path(".")
        if not base.is_absolute():
            if not cwd:
                return False
            base = Path(cwd) / base
        p = base / p
    try:
        if not p.is_file() or p.stat().st_size > SOURCE_MAX_BYTES:
            return False
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        m = ASSIGN_RE.match(line)
        if m:
            _assign(line, m, env)
    return True


def _assign(line: str, m, env: dict) -> None:
    env[m.group(1)] = "$" + m.group(1) if MULTIWORD_ASSIGN_RE.match(line) else _tilde(_expand(m.group(2), env), env)


def _tilde(path: str, env: dict) -> str:
    """앞머리 `~` · `~/` 를 셸처럼 HOME 으로 푼다 — 같은 명령이 HOME 을 대입했으면 그 값, 아니면 훅의 HOME(Bash 도구와 같은
    사용자 · HOME — `_source_env` 와 같은 전제). 대입한 HOME 이 미상이면 `~` 도 풀지 않는다(미상).

    풀지 않으면 `cd ~/x` · `W=~/x` 뒤의 경로가 어떤 원장과도 안 맞아 소유를 놓치거나(fail-open) 대상 미상(과차단)이 된다.
    `~user` 는 풀지 않는다(미상). ponytail: 따옴표 안 `"~/x"` 도 푼다 — 셸은 글자 그대로 두지만 그런 원장 경로는 실측 0건이다.
    """
    if not (path == "~" or path.startswith("~/")):
        return path
    home = env.get("HOME")
    if home is None:
        return os.path.expanduser(path)
    return path if "$" in home else home + path[1:]


def _in_quotes(seg: str, pos: int) -> bool:
    """`seg[pos]` 가 따옴표 · 이스케이프 구간 안인가 — 공용 토크나이저가 정한다(치환 `$( )` 안은 실행되는 코드라 밖이다).
    못 읽으면 밖으로 본다 — 쓰기 연산자를 데이터로 접어 '대상 미상' 을 빠뜨리지 않는다(fail-closed · F-458)."""
    return shell_tokens is not None and shell_tokens.in_quotes(seg, pos, fragment=True) is True


def _loop_spans(segs: list) -> dict:
    """`for NAME in …` 조각 index → (이름, 짝 done 조각 index | None, 지원 여부).

    - Important: 근사기의 전제 — 단어 분리는 기본 IFS 이고, 변수 값은 같은 명령의 대입 · source 한 파일에서만 안다.
      명령이 IFS 를 건드리거나 함수를 정의하면 루프는 지원 밖(미상)이다. 명령 밖에서 물려받은 IFS 는 보지 못한다.
    """
    spans = {}
    # 함수는 몸체 밖에서 루프 변수를 바꿀 수 있고, IFS 대입은 `$LIST` 의 단어 경계를 바꾼다
    funcs = any(FUNC_DEF_RE.search(s) or re.search(r"(?<![\w$])IFS\b", s) for s in segs)
    for i, seg in enumerate(segs):
        m = FOR_RE.match(seg)
        if not m:
            continue
        name, depth, ok, end = m.group(1), 0, not funcs, None
        for j in range(i + 1, len(segs)):
            body = LOOP_DO_RE.sub("", segs[j])
            if LOOP_DONE_RE.match(body):
                if depth == 0:
                    end = j
                    break
                depth -= 1
                continue
            if LOOP_OPEN_RE.match(body):
                depth, ok = depth + 1, False
            # 몸체는 평범한 명령만 지원한다(허용 목록 — F-458): 복합 구문 · 흐름 제어 · 같은 셸에서 코드를 읽는 명령이 있거나,
            # 루프 변수 이름이 확장(`$NAME` · `${NAME…}`) 밖에서 나오면(`X=` · `read X` · `printf -v X`) 지원 밖이다
            bare = re.sub(r"\$\{?%s(?![A-Za-z0-9_])" % re.escape(name), "", body)
            ws = _words(body)
            if ws is None:
                ok = False                 # 못 읽은 몸체 — 지원 밖(미상)
                continue
            cmd_ws = list(ws)
            while len(cmd_ws) > 1 and re.match(r"^\w+=", cmd_ws[0]):
                cmd_ws.pop(0)              # `VAR=값 명령` 의 앞머리는 그 명령에만 붙는 환경이다 — 셸 상태가 아니다(대입만 있는 몸체는 남는다)
            head = next((w for w in cmd_ws if w not in _CMD_PREFIX_WORDS and not w.startswith("-")), "")   # `command -- "$C"`
            if (LOOP_COMPOUND_RE.match(body) or LOOP_BODY_BANNED & set(ws)
                    or re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(name), bare)
                    or re.match(r"^\w+\+?=", head) or head in LOOP_STATEFUL or (head == "printf" and "-v" in ws)
                    or "$" in head or "`" in head or LOOP_SIDE_EFFECT_RE.search(body)):
                ok = False                 # 상태를 바꾸는 몸체 — 다음 반복의 값 · 폴더가 달라진다(GPT check 후속 5 · 리뷰 R2)
        spans[i] = (name, end, ok and end is not None)
    return spans


def _bind_expand(token: str, env: dict, bind) -> list:
    """루프 몸체 안이면 `$NAME` 을 루프 값마다 펼친다 — 진입 전 같은 이름의 값보다 우선한다(F-457)."""
    if bind and re.search(r"\$\{?%s(?![A-Za-z0-9_])" % re.escape(bind[0]), token):
        return [_expand(token, dict(env, **{bind[0]: v})) for v in bind[1]]
    return [_expand(token, env)]


def _bash_write_targets(cmd: str, cwd=None, unknown=None) -> list:
    """Bash 명령이 **쓰기 대상으로 지목한** 원장 경로들.

    `unknown` 에 list 를 주면 원장을 쓰는 판정기 호출인데 원장 인자를 풀지 못한 것(`"$L"` 의 L 미상)을 `(인자, 그 시점의 cd
    대상 | None)` 으로 모은다 — 호출부가 그 세션을 '대상 미상 쓰기' 로 보고 그 명령이 돌던 폴더 아래 원장을 판정한다
    (fail-closed · F-554). `cwd` 는 상대
    경로 `source` 의 기준이다(transcript 줄의 cwd — 없으면 훅의 cwd).

    - Important: 근사기의 전제(F-458) — 이 밖의 정보가 필요한 꼴은 받아들인 한계다:
      단어 분리는 기본 IFS(명령 · source 한 파일이 IFS 를 바꾸면 루프는 미상) · 변수 값은 같은 명령의 대입과 source 한
      파일(훅이 도는 지금의 내용), 그리고 훅 프로세스의 환경에서 안다(셸 프로필 · alias 는 모른다) · 함수 · eval 은 따라가지 않는다 ·
      판정기는 파일명으로 가린다(PATH 가림 · 링크 이름은 모른다) · 앞머리 `~` 는 훅의 HOME 으로 푼다(`_tilde`). 원장 인자 ·
      루프 값 · 리다이렉트와 cp · mv 대상은 허용 목록(`_RESOLVED_PATH_RE`)에 맞는 최종 경로일 때만 '풀렸다' 이고, 그 밖은
      '대상 미상' 이다.

    ⛔ "명령에 쓰기 마커가 있다 + 어딘가에 원장 경로가 있다" 로 판정하면 안 된다.
       실측(2026-09-11): 발견 레지스트리에 사건을 기록하는 `cat > "$F" <<EOF` 가
       **본문에 인용한** TKT 원장 2개의 소유로 잡혔다 — 3건 전수 오탐이었고,
       그 결과 무관한 세션이 다시 종료 불가가 됐다. **기록하는 행위가 기록 대상의
       소유를 만들면 안 된다.**
    두 겹으로 막는다 — **데이터** heredoc 본문은 조각에 들지 않고, 남은 명령에서 쓰기 **자리**(fz-guard write_sites —
    리다이렉트 · tee · rm · touch · mkdir · cp · mv 대상 · 판정기 `--from-plan` 의 `--out`)에 온 경로만 취한다.
    ⛔ 인터프리터(python · bash -c · node …)와 읽기 표 밖 명령은 코드를 읽지 않고 '대상 미상' 이다(UNKNOWN_NAME_WRITES) —
    `python3 - <<PY … write_text … PY` 로 자기 원장을 만든 세션도 그 쓰기가 돌던 폴더 아래 원장 후보로 막힌다.
    ⛔ 종료 태그가 없는 heredoc 은 토크나이저가 못 읽는다(Unknown) — 그 명령은 '대상 미상' 이다(fail-closed 방향).
    ⛔ `plan.md` 리터럴만으로 조기 반환하지 않는다 — 원장 경로가 변수(`"$L"`)나 source 한 파일에서 오면 명령에
       그 낱말이 없다(F-377 · F-422). 판정기 이름 · `source` 가 하나도 없을 때만 돌아간다.
    """
    if not cmd:
        return []
    # 원문 전체를 먼저 읽는다(F-458) — 글자 사전 필터보다 앞이다. 못 읽은 명령은 글자 단서가 이스케이프로 감춰졌을 수 있다
    # (`$'gates/pl\141n.md'`) — 그 명령이 돌던 폴더의 '대상 미상' 이다(fail-closed). ⛔ transcript 줄 사전 필터(TRANSCRIPT_LINE_HINTS)까지 감춘 꼴은 보지 않는다
    full = _write_sites(cmd) if shell_tokens is not None else None
    if full is None:
        if unknown is not None:
            unknown.append((cmd.strip()[:80] or "?", None))
        return []
    if not ("plan.md" in cmd or "gates" in cmd or GATE_CHECK_NAME[:-3] in cmd or SOURCE_ANY_RE.search(cmd) or _hint_env_in(cmd)):
        return []
    # 조각 스캔이 못 보는 자리 — 따옴표 없는 heredoc 본문의 치환은 셸이 실행하고(`cat <<EOF⏎$(printf x > plan.md)⏎EOF`), 함수 본문은 이름으로
    # 불릴 때 돈다(그 안의 cd 를 따라가지 않는다). 그 안의 원장 꼴 · 펼쳐지는 대상은 '대상 미상' · 읽기 표 밖 명령은 '이름 미상'(좁은 후보)이다
    nested_sites = [w for w, c in full if (c.depth or c.deferred) and _risky_site(w)]
    if unknown is not None and any(w is not None for w in nested_sites):
        unknown.append((cmd.strip()[:80] or "?", None))

    segs = shell_tokens.segments(cmd)                  # 맨 바깥 연산자로만 나눈다 — heredoc 본문은 조각에 들지 않는다
    funcs = _GUARD[0].defined_functions(shell_tokens.lex(cmd))   # 정의와 호출이 다른 조각에 있다(`g() {…}; g`)
    out = []
    cur_dir, cd_next, stack = None, None, []
    marks = _subshell_marks(cmd, len(segs))
    env = {}
    source_missing = False                 # 이 명령이 source 한 파일 중 못 읽은 것이 있다 — 그 뒤 `"$G"` 는 판정기일 수 있다
    spans = _loop_spans(segs)
    # 지원 밖 루프의 몸체 — 반복마다 상태(폴더 · 변수)가 달라질 수 있어 루프 변수를 안 쓰는 원장 인자도 한 값으로 못 정한다(리뷰 R2)
    unbound = {j for s, (_n, e, ok) in spans.items() if not ok for j in range(s + 1, len(segs) if e is None else e)}
    bind = None                            # (이름, 값들, 짝 done index) — 지원 루프의 몸체 안에서만
    for i, seg in enumerate(segs):
        if cd_next is not None:            # 앞 조각의 cd — 그 조각의 리다이렉트는 cd 전 폴더에서 열렸다
            cur_dir, cd_next = cd_next, None
        for _ in range(marks[i - 1][1] if i else 0):
            if stack:
                cur_dir = stack.pop()      # 닫힌 서브셸 — 그 안의 cd 는 뒤로 이어지지 않는다(`(cd a && x); (cd b && …)`)
        stack += [cur_dir] * marks[i][0]
        if bind and i >= bind[2]:
            bind = None
        if i in spans:
            name, end, ok = spans[i]
            vals = [_tilde(_expand(w, env), env) for w in (_words(FOR_RE.match(seg).group(2)) or [])]
            # 원장 모양(`.md`) 값만 · IFS 를 바꾼 명령(source 한 파일 포함 — env 에 남는다)은 단어 경계를 모른다
            if ok and vals and "IFS" not in env and all(_RESOLVED_PATH_RE.match(v) and v.endswith(".md") for v in vals):
                bind = (name, vals, end)
            env[name] = "$" + name             # ⛔ 미상 표식 — 지원 밖 몸체 · done 뒤는 대상 미상(fail-closed)
            continue
        seg = LOOP_DO_RE.sub("", seg) if bind or any(s < i for s in spans) else seg
        mcd = CD_RE.match(seg)
        if mcd:
            d = _tilde(_expand(mcd.group(1), env), env)
            cd_next = d if d.startswith("/") or cur_dir is None else f"{cur_dir}/{d}"   # 상대 cd 는 앞 위치에 쌓인다
        msrc = None if mcd else SOURCE_RE.match(seg)   # cd 조각도 아래 쓰기 자리를 본다(`cd X > 원장` 은 cd 전 폴더에 쓴다)
        if msrc:
            source_missing |= not _source_env(msrc.group(1), env, cur_dir, cwd)
            continue
        masg = ASSIGN_RE.match(seg)
        if masg and not _temp_env_prefix(seg):
            body, pos = re.sub(r"^\s*export\s+", "", seg), 0
            while True:                    # 대입만 있는 명령의 대입을 차례로 — 뒤 대입이 앞 값을 본다(`A=x B=$A/gates`)
                m = _PREFIX_ASSIGN_RE.match(body, pos)
                if not m or m.end() == pos:
                    break
                piece = body[pos:m.end()]
                ma = ASSIGN_RE.match(piece)
                if ma:
                    _assign(piece, ma, env)
                pos = m.end()
        # 단어를 전부 푼 뒤 판정기 인자를 가른다 — 변수로 들어온 옵션(`"$OPT"`)이 원장 자리로 잡히지 않는다. 루프 몸체면 값마다
        words, missed, gate = _words(seg), None, False
        if words is None:
            if unknown is not None and seg.strip():
                unknown.append((seg.strip()[:80], cur_dir))   # 못 읽은 조각 — 판정기를 부르는지 모른다(fail-closed)
            words = []
        for env_v in ([dict(env, **{bind[0]: v}) for v in bind[1]] if bind else [env]):
            call = _gate_call([_tilde(_expand(w, env_v), env_v) for w in words], env_v, unresolved_prog=source_missing)
            gate = gate or call is not None
            if call is None or not call[0] or call[1] is None:
                continue
            path = call[1] if call[1].startswith("/") or not cur_dir else f"{cur_dir}/{call[1]}"
            if not _RESOLVED_PATH_RE.match(path) or not call[2] or i in unbound:   # 허용 목록은 `cd` 접두를 붙인 최종 경로에 건다
                missed = call[1]
            else:
                out.append(path)
        if missed is not None and unknown is not None:
            unknown.append((missed, cur_dir))
        # 쓰기 자리(fz-guard write_sites) — 대상 글자는 따옴표를 벗긴 그대로이고 펼침은 펼쳐지는 단어(`expands`)만 한다(작은따옴표 `'$W'` 는 글자다)
        sites = _write_sites(seg, fragment=True, known=funcs) or []
        # 판정기 호출은 위 _gate_call 이 맡는다(쓰기 여부 · 원장 인자) — 맨 바깥 명령의 미상 자리로 세지 않는다 · `--from-plan` 의 `--out` 값은 쓰기 대상이다
        found = [(w.text, w.expands, w.quoted, bool(c.depth or c.deferred)) for w, c in sites if w is not None]
        if gate:
            found += [(v, bool(re.search(r"[$`]", v)), False, False) for v in _gate_out(words)]
        if UNKNOWN_NAME_WRITES and unknown is not None:
            for w, c in sites:
                if w is None and not (gate and not (c.depth or c.deferred)):   # 읽기 표 밖 — 이름 미상 쓰기(명령에 적힌 원장 글자만 후보)
                    unknown.append(((c.name.text if c.name is not None else seg.strip())[:80], cur_dir, _ledger_lits(cmd, env)))
        for raw, expands, quoted, inner in found:
            for tok in ([_tilde(t, env) for t in _bind_expand(raw, env, bind)] if expands else [raw if quoted else _tilde(raw, env)]):
                if not tok.startswith("/") and cur_dir:
                    tok = f"{cur_dir}/{tok}"
                if not LEDGER_TAIL_RE.search(tok):
                    continue                   # 펼친 뒤에도 원장 모양이 아니다 — 원장 쓰기가 아니다(과차단 금지)
                if _RESOLVED_PATH_RE.match(tok) and i not in unbound and not inner:
                    out.append(tok)
                elif unknown is not None:
                    unknown.append((raw, cur_dir))   # 못 푼 원장 꼴 · 치환 · 함수 본문 안(그 안의 cd 를 모른다)
    if unknown is not None and any(w is None for w in nested_sites):
        unknown.append((cmd.strip()[:80] or "?", None, _ledger_lits(cmd, env)))   # 치환 · 함수 본문 안 읽기 표 밖 명령 — 이름 미상
    return out


def _ledger_lits(cmd: str, env: dict) -> tuple:
    """명령 글자의 원장 경로 토큰을 같은 명령의 대입 · 환경으로 편 것 — 이름 미상 쓰기의 후보는 이 글자가 가리키는 원장뿐이다.

    원문과 토크나이저 단어(따옴표를 벗긴 글자 · 모든 깊이) 둘 다에서 뽑는다 — 따옴표를 이어 붙인 글자(`'…"'$W'/gates/plan.md"…'` ·
    `"$W"/gates/plan.md`)는 원문 정규식이 따옴표에서 끊겨 `/gates/plan.md` 만 남긴다. heredoc 본문은 원문 글자에 그대로 있다.
    """
    ws = shell_tokens.all_words(cmd) if shell_tokens is not None else None
    srcs = [cmd] + ([t for t, _d in ws] if ws is not None and not shell_tokens.is_unknown(ws) else [])
    return tuple(dict.fromkeys(_tilde(_expand(m, env), env) for src in srcs for m in re.findall(_TOKEN, src) + re.findall(_TOKEN, _expand(src, env))))


def _hint_env_in(text: str) -> bool:
    """글자가 값에 원장 단서가 든 훅 환경 변수를 부르는가 — `printf x > "$LEDGER"` 는 펼치기 전 글자에 단서가 없다(r6 ISSUE-008).
    그런 변수가 없으면 늘 False 다(선필터 동작이 그대로다)."""
    if "$" not in text:
        return False
    names = [k for k, v in os.environ.items() if any(h in v for h in TRANSCRIPT_LINE_HINTS[:3])]
    return any(re.search(r"\$\{?" + re.escape(k) + r"\b", text) for k in names)


def _subshell_marks(cmd: str, n: int) -> list:
    """조각(segments)마다 [여는 서브셸 수, 닫는 서브셸 수] — 맨 바깥 `(` · `)` 연산자를 센다(`$(…)` 는 단어 안이라 들지 않는다)."""
    marks, k = [[0, 0] for _ in range(n)], 0
    for t in shell_tokens.lex(cmd):
        if isinstance(t, shell_tokens.Op):
            if t.text in ("(", ")"):
                marks[min(k, n - 1)][t.text == ")"] += 1
            else:
                k += 1
    return marks


def _risky_site(w) -> bool:
    """치환 · 함수 본문 안 쓰기 자리가 원장 소유 후보인가 — 읽기 표 밖 명령 · 펼쳐지는 대상 · 원장 꼴 대상. 장치(/dev/…)와 그 밖 고정 경로는 아니다."""
    if w is None:
        return UNKNOWN_NAME_WRITES
    return (w.expands or bool(LEDGER_TAIL_RE.search(w.text))) and not w.text.startswith("/dev/")


def _gate_out(words: list) -> list:
    """판정기 호출 단어열의 `--out` 값(`--from-plan` 이 쓰는 파일)."""
    return [words[k + 1] if a == "--out" and k + 1 < len(words) else a.split("=", 1)[1]
            for k, a in enumerate(words) if a == "--out" and k + 1 < len(words) or a.startswith("--out=")]


def _expand(token: str, env: dict) -> str:
    """같은 명령(과 그 명령이 source 한 파일) 안의 대입만 푼다 — `$W/gates/plan.md` 형태(실측 #14·#21).

    `$NAME` · `${NAME}` · `${NAME:?…}` 꼴. 명령 안에서 대입하지 않은 이름은 훅 프로세스의 환경(세션이 물려받은 HOME ·
    TMPDIR · 설정 env)에서 찾는다(F-458 — `D="$HOME/…"; cd "$D" && … "$D/gates/plan.md"` 가 대상 미상으로 과차단됐다).
    비었거나 모르는 이름은 그대로 둔다(호출부가 '풀리지 않음' 으로 본다).
    """
    def _one(m):
        name = m.group(1) or m.group(2)
        return env[name] if name in env else (os.environ.get(name) or m.group(0))
    return _VAR_RE.sub(_one, token)


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
    owned, unknown = set(), []
    try:
        with tp.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not _line_may_write(line):
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
                # F-554 — 상대 경로는 그 명령이 돌던 폴더(transcript 줄의 `cwd` — Bash 작업 폴더는 호출 사이에 이어진다)로 푼다.
                #    훅이 받은 cwd 로 풀면 앞 호출에서 `cd` 한 뒤의 `gates/plan.md` 가 엉뚱한 원장을 가리킨다
                ev_cwd = ev.get("cwd")
                base = Path(ev_cwd) if isinstance(ev_cwd, str) and ev_cwd.startswith("/") else cwd
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
                            if _same_ledger(target, res, base):
                                owned.add(led)
                    elif name == "Bash":
                        unk, cmd_s = [], str(inp.get("command") or "")
                        tokens = _bash_write_targets(cmd_s, base, unk)
                        for t, d, *lits in unk:
                            # 같은 명령의 cd 를 반영한 폴더를 기준에 더한다(원래 폴더는 남긴다 — 후보를 줄이지 않는다).
                            # cd 대상을 못 풀었으면 그 쓰기가 어디서 돌았는지 모른다 — None 은 전 원장(fail-closed)
                            bs = (base,) if d is None else None if re.search(r"[$`*?\[]", d) else \
                                (base, Path(d) if d.startswith("/") else base / d)
                            unknown.append((t, bs, cmd_s, lits[0] if lits else None))
                        for led, res in resolved.items():
                            if any(_same_ledger(t, res, base) for t in tokens):
                                owned.add(led)
                if len(owned) == len(ledgers):
                    break
    except OSError as exc:
        return None, f"transcript 읽기 실패({type(exc).__name__}) — 전 원장 판정"
    if unknown and len(owned) < len(ledgers):
        # ⛔ 원장을 쓰는 판정기 호출인데 어느 원장인지 모른다 — 조용히 '다른 세션의 원장' 으로 보내면 그 쓰기의 미충족이
        #    통과한다(F-377 · F-422 — fail-open 의 비용은 한도가 없고, fail-closed 의 비용은 루프 방어가 2회로 묶는다).
        #    F-554 — 후보는 **그 쓰기가 돌던 폴더 아래 원장** + **그 명령 글자에 적힌 원장 경로 리터럴을 그 폴더 기준으로 푼 원장**
        #    (`L=$(realpath ../w/gates/plan.md)` 처럼 `..` 이나 명령 치환으로 폴더 밖을 가리켜도 글자가 남는다). 둘 다 아닌 원장은
        #    막지 않는다 — 남의 원장으로 종료를 막지 않는다. 잔존: 경로를 글자로 쓰지 않은 폴더 밖 쓰기(`$(find ..)`)
        #    F-554 리뷰 — 폴더는 같은 명령의 `cd` 를 반영하고(못 푼 cd · 글롭 cd 는 전 원장), 명령에 적힌 폴더 경로
        #    (`..` · 절대 · `~/` — `$(find ../w …)` · `$(find /abs/w …)`) 아래 원장도 후보다(`./../w` 도 — 정규화한 경로). 폴더를 변수로만 넘긴 검색(`$(find "$X" …)`)은 전 원장 후보다(F-554 r3)
        cand = {led for led, res in resolved.items() for _t, bs, c, lits in unknown if _unknown_hits(res, bs, c, lits)}
        sample = ", ".join(sorted({t for t, _b, _c, _l in unknown})[:3])
        return owned | cand, (f"대상 미상 쓰기 {len(unknown)}건(원장 인자 {sample} 를 풀지 못했다) — 그 쓰기가 돌던 폴더(cd 반영) 아래 · "
                              f"명령에 적힌 원장 경로 · 폴더 아래로 원장 {len(cand)}개를 이 세션 원장으로 판정한다(그 밖의 원장은 막지 않는다)")
    return owned, ""


# 명령 글자 속 원장 경로 리터럴 — 변수 · 따옴표 · 명령 치환 경계에서 끊는다(`$D/gates/plan.md` 의 `$D` 는 들어오지 않는다)
LEDGER_LITERAL = re.compile(r"[^\s'\"=;&|()<>`$]*plan(?:\.draft)?\.md")


def _unknown_hits(res: Path, bases, cmd: str, lits=None) -> bool:
    """미상 쓰기 한 건이 원장 `res` 를 후보로 만드는가 — `bases` None 은 어디서 돌았는지 모르는 쓰기(전 원장).

    폴더 후보는 명령의 모든 깊이 단어(공용 토크나이저 — 치환 안 포함 · `--root=../w` 의 `=` 뒤 포함 · 단어 안 절대 · `..` 조각 —
    `bash -c 'cd /tmp; …'`)를 정규화한 경로가 `..` 로 시작하거나 절대 · `~/` 인 것이다 — `./../w` 처럼 `..` 이 첫 마디가 아니어도
    같다(ISSUE-202601). 치환 안 단어가 풀리지 않은 변수 · 치환이면(`$(find "$X" …)`) 그 폴더를 모르므로 전 원장이 후보다. 명령을
    못 읽어도 전 원장이다(fail-closed · F-458).
    `lits` 가 있으면 이름 미상 쓰기(읽기 표 밖 명령 — 인터프리터 · 표 밖 명령)다 — 폴더 아래 전부가 아니라 원장 경로 글자(`lits` ·
    리터럴)를 그 쓰기의 폴더(cwd · cd 대상 · 명령에 적힌 폴더)에 붙여 `res` 와 같아질 때만 후보다. 폴더 아래 전부로 넓히면 작업 폴더의
    부모에서 도는 세션이 무관한 원장 전부에 막힌다(소유 재생 실측 — 17세션 중 5세션이 원장 31개 전부).
    ponytail: 같은 명령의 대입(`X=../w; $(find "$X" …)`)은 따라가지 않는다 — 전 원장 쪽으로 넓게 막는다 · 이름 미상 쓰기가 원장 경로를
    글자로 쓰지 않으면(스크립트 안에서 조립) 후보가 없다
    """
    named = lits is not None
    if bases is None:
        if not named or any(not os.path.isabs(x) for x in lits):
            return True                            # 어디서 돌았는지 모르는데 상대 원장 글자가 있다 — 어느 원장인지 모른다
        bases = ()
    ws = shell_tokens.all_words(cmd) if shell_tokens is not None else None
    if ws is None or shell_tokens.is_unknown(ws):
        return True
    ups = []
    for text, depth in ws:
        if depth and re.search(r"[$`]", _expand(text, {})) and not named:
            return True
        parts = {text, text.split("=", 1)[-1]} | set(re.findall(r"(?:^|[\s;&|(=:'\"])((?:/|\.\./|~/)[^\s;&|()<>'\"]*)", text))
        for part in parts:
            p = os.path.normpath(os.path.expanduser(part)) if part else ""
            if p == ".." or p.startswith("../") or (p.startswith("/") and p != "/"):
                ups.append(p)
    all_lits = LEDGER_LITERAL.findall(cmd) + list(lits or ())
    if named:
        return any(_same_ledger(x, res, f) for x in all_lits for f in list(bases) + [b / u for b in bases or (Path("/"),) for u in ups])
    return any(_under(res, b) or any(_same_ledger(x, res, b) for x in all_lits) or any(_under(res, b / u) for u in ups)
               for b in bases)


def _under(path: Path, base: Path) -> bool:
    """`path` 가 `base` 폴더 아래인가 — 둘 다 해석 후 비교(심볼릭 · `/var` → `/private/var`)."""
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _line_may_write(line: str) -> bool:
    """transcript 한 줄이 원장 쓰기 tool_use 일 수 있는가 — JSON 파싱 전 값싼 선필터."""
    if '"tool_use"' not in line:
        return False
    if any(h in line for h in TRANSCRIPT_LINE_HINTS):
        return True
    return '"Bash"' in line and (SOURCE_LINE_RE.search(line) is not None or _hint_env_in(line))


DRIFT_LINE_RE = re.compile(r"^\s*DRIFT (\S+): 도구 부재 — (.+?) \(")


def _ids_line(head: str, shown: list, rest: int) -> str:
    text = f"{head} — {', '.join(shown)}" if shown else head
    if rest > 0:
        text += (" " if shown else " — ") + f"…외 {rest}건"
    return text


def _unmet_summary(out: list) -> str:
    """`--status` 의 마지막 `UNMET: n (…)` 줄과 그 아래 미충족 id 목록을 한 줄로 만든다.

    ⛔ 마지막 줄만 싣던 구판은 미충족이 둘 이상이면 앞의 id 를 사유에서 뺐다(F-360).
    id 는 `UNMET_IDS_SHOWN` 개까지, 그리고 요약이 `SUMMARY_MAX_CHARS` 안에 드는 만큼만 싣고
    나머지는 `…외 N건` 으로 센다 — 자르기 뒤에도 표시 id 수 + N = n 이 맞는다.
    `UNMET:` 줄이 없으면(충족 · 인프라 · 계약 위반 · 판정기 고장) 빈 문자열 — 호출부가 끝 줄로 간다.
    """
    idx = next((i for i in range(len(out) - 1, -1, -1) if UNMET_LINE_RE.match(out[i])), None)
    if idx is None:
        return ""
    head = out[idx].strip()
    total = int(UNMET_LINE_RE.match(out[idx]).group(1))
    ids = []
    for l in out[idx + 1:]:   # 연속된 id 줄만 — 판정기가 목록 뒤에 다른 줄을 더해도 id 로 섞지 않는다
        m = UNMET_ID_RE.match(l)
        if not m or len(ids) >= total:
            break
        ids.append(m.group(1))
    # 환경 드리프트(F-291) — 기록은 met 인데 선언 도구가 없는 게이트. 일반 미충족과 할 일이 다르다(도구를 되살린다)
    drift = [m for m in (DRIFT_LINE_RE.match(l) for l in out) if m]
    tail = ""
    if drift:
        tools = list(dict.fromkeys(t.strip() for m in drift for t in m.group(2).split(",")))
        tail = f" · 환경 드리프트 {len(drift)}(도구 부재: {', '.join(tools[:3])}{' …' if len(tools) > 3 else ''})"
    shown = []
    for gid in ids[:UNMET_IDS_SHOWN]:
        if len(_ids_line(head, shown + [gid], total - len(shown) - 1)) + len(tail) > SUMMARY_MAX_CHARS:
            break
        shown.append(gid)
    return _ids_line(head, shown, total - len(shown)) + tail


def judge(checker: Path, ledger: Path, budget_left: float):
    """판정기를 `--status` 로 부른다 — CHECK 재실행 없음.

    반환: (exit_code, 요약 한 줄). 미충족이면 `UNMET:` 줄 + id 목록, 아니면 출력의 끝 줄.
    exit 는 판정기 계약을 그대로 쓴다 (0 충족 · 1 미충족 · 2 인프라 · 3 원장 계약 위반).
    시간 초과는 `JUDGE_TIMEOUT` — 호출부가 예산이 끊은 것(미판정)과 판정기 자체 상한(인프라)을 가른다.
    """
    timeout = min(CHECK_TIMEOUT_S, max(1.0, budget_left))
    try:
        proc = subprocess.run(
            [sys.executable, str(checker), "--status", str(ledger)],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return JUDGE_TIMEOUT, f"판정기 시간 초과({timeout:.1f}초)"
    except (OSError, subprocess.SubprocessError):
        return None, "판정기 호출 실패"
    out = (proc.stdout or b"").decode("utf-8", "replace").strip().splitlines()
    err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
    tail = _unmet_summary(out) or (out[-1] if out else "") or (err[-1] if err else "")
    return proc.returncode, tail[:SUMMARY_MAX_CHARS]


def _cap_reason(body: list, footer: list, more: str) -> str:
    """차단 사유를 `REASON_MAX_CHARS` 안으로 — 넘치면 본문 끝 줄부터 빼고 `…외 N줄 생략` 한 줄을 남긴다.

    ⛔ 안내(footer — ABANDON 출구 · 판정 명령)는 빼지 않는다. 길어도 다음 행동은 보여야 한다.
    본문은 계약 위반 → 미충족 → 진단 순이라 끝에서 빼면 진단이 먼저 빠진다.
    """
    text = "\n".join(body + footer)
    if len(text) <= REASON_MAX_CHARS:
        return text
    for keep in range(len(body) - 1, -1, -1):
        text = "\n".join(body[:keep] + [f"…외 {len(body) - keep}줄 생략 {more}"] + footer)
        if len(text) <= REASON_MAX_CHARS:
            return text
    return text[:REASON_MAX_CHARS]


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
    if gcmod is None or not hasattr(gcmod, "find_ledgers") or not hasattr(gcmod, "LEDGER_ENV"):
        return _pass("판정기 모듈을 불러올 수 없어 원장 탐색을 건너뛴다")
    ledger_env = gcmod.LEDGER_ENV
    env_ledgers = os.environ.get(ledger_env, "")
    # ⛔ 발견 수에 상한이 없다(F-378) — 판정기가 발견한 원장 **전부**에 소유 판정을 먼저 한다. 상한은 아래에서 남의 원장
    #    판정에만 둔다. 8개에서 자르던 구판은 사전순 뒤(최신 티켓)의 소유 원장을 말없이 빼고 통과했다.
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

    budget = TOTAL_BUDGET_S
    try:
        knob = float(os.environ.get(BUDGET_ENV, ""))
        if 0 <= knob < TOTAL_BUDGET_S:
            budget = knob
    except ValueError:
        pass
    unmet, invalid, undecided, notes = [], [], [], ([discovery_note] if discovery_note else [])
    if owner_note:
        notes.append(owner_note)
    # ── 소유 원장 먼저(F-404) — 예산을 막지 않는 원장에 먼저 쓰면 이 세션의 미충족이 판정 없이 통과한다 ──
    for led in ledgers:
        left = budget - (time.monotonic() - started)
        if left <= 1.0:
            undecided.append(led)
            continue
        code, tail = judge(checker, led, left)
        if code == JUDGE_TIMEOUT and left < CHECK_TIMEOUT_S:
            undecided.append(led)                    # 예산이 끊은 판정 — 판정기 자체 상한(20초)이 아니다
        elif code in (None, 2, JUDGE_TIMEOUT):
            notes.append(f"{led}: 인프라 — {tail}")
        elif code == 1:
            unmet.append((led, tail))
        elif code == 3:
            invalid.append((led, tail))
    # 남의 원장 — 판정은 하되 **막지 않는다**. 충족도 ABANDON 도 이 세션이 할 일이 아니다. 남은 예산 · 상한 안에서만 본다.
    # ⛔ 경고가 `FOREIGN_NOTES_FOLD` 개를 넘으면 건수 한 줄로 접는다(EC-07) — 원장마다 요약
    #    한 줄씩이면 원장 수만큼 사유가 자란다. 원장별 목록은 `--discover` 가 준다.
    foreign_notes, foreign_invalid, foreign_skipped = [], 0, 0
    for idx, led in enumerate(foreign):
        left = budget - (time.monotonic() - started)
        if idx >= FOREIGN_JUDGED_MAX or left <= 1.0:
            foreign_skipped += 1
            continue
        code, tail = judge(checker, led, left)
        if code in (1, 3):
            foreign_notes.append(f"다른 세션의 원장(막지 않음): {led} — {tail}")
            foreign_invalid += code == 3
    if len(foreign_notes) > FOREIGN_NOTES_FOLD:
        n = len(foreign_notes)
        foreign_notes = [f"다른 세션의 원장(막지 않음) {n}개 — 미충족 {n - foreign_invalid} · "
                         f"계약 위반 {foreign_invalid} (목록: python3 {checker} --discover {cwd})"]
    notes += foreign_notes
    if foreign_skipped:
        notes.append(f"다른 세션의 원장 {foreign_skipped}개 미판정(남의 원장 판정 상한 {FOREIGN_JUDGED_MAX} · 예산) — "
                     f"막지 않는다 (목록: python3 {checker} --discover {cwd})")

    if not unmet and not invalid and not undecided:
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
    #    exit 계약(1=미충족 / 3=계약위반)이라 옆 세션의 편집이 건드릴 수 없다. 예산으로 판정하지 못한 소유 원장은
    #    `:undecided` 로 같은 지문에 든다 — 이 차단도 같은 루프 방어(MAX_BLOCKS)를 받는다.
    #    의도 보존: 이 세션이 원장을 충족시키면 그 원장이 목록에서 빠져 지문이 바뀌고
    #    다시 막는다. sorted 는 탐색 순서가 흔들려도 지문이 같도록 고정한다.
    fingerprint = sha12("|".join(sorted(
        [f"{p}:unmet" for p, _ in unmet] + [f"{p}:invalid" for p, _ in invalid]
        + [f"{p}:undecided" for p in undecided]
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
            f"미충족 {len(unmet)}건 · 계약 위반 {len(invalid)}건 · 미판정 {len(undecided)}건 (수동 확인 필요)")

    body = []
    for led, tail in invalid:
        body.append(f"⛔ 원장 계약 위반: {led} — {tail}")
    for led, tail in unmet:
        body.append(f"미충족 게이트: {led} — {tail}")
    if undecided:
        # ⛔ 판정하지 못한 소유 원장은 통과가 아니다(F-378 · F-404) — 수와 이유, 원장 경로(이름만이면 늘 plan.md 다)를 싣는다
        shown = ", ".join(str(p) for p in undecided[:3]) + (f" …외 {len(undecided) - 3}개" if len(undecided) > 3 else "")
        body.append(f"⏳ 소유 원장 {len(undecided)}개 미판정(예산 소진 — 훅 예산 {budget:g}초 · 판정기 1회 상한 "
                    f"{CHECK_TIMEOUT_S}초 안에 판정을 끝내지 못했다 · 판정하지 못한 원장은 통과가 아니다): {shown}")
    body += notes
    lines = [""]
    # ⛔ MANUAL 게이트는 사용자 확인(`--confirm` · TTY)으로만 충족된다 — '충족 or ABANDON' 만 보이면 에이전트가 EVIDENCE 를
    #    직접 쓰거나(F-202) 기다리는 확인을 포기로 바꾼다. 그래서 ABANDON 안내보다 먼저 둔다.
    manual = [(led, ids) for led, _ in unmet for ids in [_manual_unmet(led)] if ids]
    if manual:
        # ⛔ 원장을 조용히 자르지 않는다 — 앞 3개만 보이면 이 세션의 원장이 뒤에 있을 때 그 확인 대기가 사라진다(2026-11-01 실측).
        #    ⛔ 목록이 사유 예산을 다 먹어도 안 된다 — _cap_reason 이 꼬리(--confirm · 판정 명령)를 자른다. 그래서 글자 수로 묶는다:
        #    원장마다 id 는 UNMET_IDS_SHOWN 까지 · 원장 이름은 폴더(전체 경로는 위 미충족 줄) · 넘는 원장은 수만 남긴다
        parts = []
        for led, ids in manual:
            more = f" …외 {len(ids) - UNMET_IDS_SHOWN}건" if len(ids) > UNMET_IDS_SHOWN else ""
            part = f"{', '.join(ids[:UNMET_IDS_SHOWN])}{more} ({Path(str(led)).parent.parent.name})"
            if parts and len(" · ".join(parts + [part])) > MANUAL_HINT_MAX_CHARS:
                break
            parts.append(part)
        shown = " · ".join(parts) + (f" …외 {len(manual) - len(parts)}개 원장" if len(parts) < len(manual) else "")
        lines.append(f"⛔ MANUAL 게이트 {shown} 는 사용자 확인으로만 충족된다 — 사용자가 별도 터미널에서 "
                     f"`python3 {checker} --confirm <게이트ID> <원장>` 을 실행한다(TTY 필요). 에이전트는 EVIDENCE 를 "
                     "쓰지 않고 ABANDON 하지도 않는다 — 사용자에게 요청하고 기다린다.")
    lines.append("게이트를 충족시키거나, 할 수 없으면 원장에 "
                 "`ABANDON: <게이트ID> <이유>` 를 남긴다 (포기 사실이 원장에 보존된다).")
    # ⛔ 셋째 선택지(F-190) — '충족 or ABANDON' 2지선다는 계획만 승인한 원장에 거짓 ABANDON 을 유도한다. 착수 전
    #    원장은 포기가 아니다. 진행 기록이 있으면 판정기가 이 전이를 거부하므로 진행 중 작업의 우회로가 되지 않는다.
    lines.append(f"아직 착수 전(계획만 승인)이면 ABANDON 이 아니다 — `python3 {checker} --set-state planned <원장>` "
                 "(진행 기록이 있으면 거부된다 · 착수는 `--set-state active`).")
    # 위 목록은 **이 세션의 transcript 가 쓴 원장**만이다(소유 판정). transcript 를 못 읽어
    # 전 원장을 판정한 경우에만 남의 원장이 섞일 수 있어, 그 경우의 출구를 함께 준다.
    if owner_note:
        lines.append(f"소유 판정을 못 했다({owner_note}). 이 세션의 작업이 아닌 원장이 섞였다면 "
                     f"{ledger_env} 에 판정할 원장 경로만 나열해 범위를 좁힌다 (여러 개는 "
                     f"'{os.pathsep}' 로 구분). 남의 원장에 ABANDON 을 쓰면 그 작업의 수용 기준이 사라진다.")
    lines.append(f"판정: python3 {checker} --status <원장>")
    return _block(_cap_reason(body, lines, f"(전체: python3 {checker} --discover {cwd})"))


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
    # ⛔ **승인·미착수(F-190)** — 확정 뒤 `--set-state planned` 한 원장은 이 세션이 썼어도 막지 않는다(판정기
    #    `--status` no-op). 짝: 미충족 active 를 막는 사유에 셋째 선택지(착수 전이면 ABANDON 아님)가 있는가.
    ("planned-passes", "planned",          {"transcript": "bash"}, {}, 0, None),
    ("planned-reason", "unmet",            {}, {}, 2, "--set-state planned"),
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
    #    게이트가 통째로 통과한다(2026-09-11 실측 fail-open).
    ("owned-py-c",       "unmet",          {"transcript": "py-c"}, {}, 2, '"decision": "block"'),
    # 읽기 표 밖 명령(인터프리터)은 코드를 읽지 않는다 — 원장 경로를 글자로 든 `python3 -c` 는 읽기만 해도 그 원장이 후보다(쓰기 신호 표를 두지 않는다 · r5)
    ("named-py-c-read-candidate", "unmet", {"transcript": "py-c-read"}, {}, 2, "대상 미상 쓰기"),
    # r5 013 · 006 · 012 — touch 대상 · dash -c · `bash -c 'cd 폴더; … > gates/plan.md'`(문자열 안 폴더 + 원장 글자) · r5 015 짝: 읽기만 하는 함수 정의는 남의 원장
    ("r3-s1-touch-ledger-owned", "unmet",  {"transcript": "r3-touch"}, {}, 2, '"decision": "block"'),
    ("r3-s1-dash-c-named", "unmet",        {"transcript": "r3-dash-c"}, {}, 2, "대상 미상 쓰기"),
    ("r3-s1-bash-c-cd-named", "unmet",     {"transcript": "r3-bash-c-cd"}, {}, 2, "대상 미상 쓰기"),
    # 따옴표를 이어 붙인 원장 글자(`'…"'$W'/gates/plan.md"…'`)는 원문 정규식이 `/gates/plan.md` 만 본다 — 토크나이저 단어에서도 뽑는다
    ("r3-s1-spliced-quote-named", "unmet", {"transcript": "r3-spliced-quote"}, {}, 2, "대상 미상 쓰기"),
    ("r3-s1-funcdef-read-foreign", "unmet", {"transcript": "r3-funcdef-read"}, {}, 0, "다른 세션의 원장"),
    # 이름 미상 쓰기가 원장 글자 없이 작업 폴더의 부모만 가리키면 후보가 없다 — 폴더 아래 전부로 넓히지 않는다(소유 재생 실측)
    ("r3-s1-named-no-literal-foreign", "unmet", {"transcript": "r3-named-no-literal"}, {}, 0, "다른 세션의 원장"),
    # r6 — 상대 cd 누적(006) · 서브셸 뒤 복원(006 짝) · cd 에 붙은 리다이렉트(007) · 훅 환경 변수 원장(008) · 대입만 있는 명령의 둘째 대입(009)
    ("r3-s1-r6-006-cd-chain", "unmet",     {"transcript": "r6-cd-chain"}, {}, 2, '"decision": "block"'),
    ("r3-s1-r6-006-subshell-cd-restored", "unmet", {"transcript": "r6-subshell-cd"}, {}, 2, '"decision": "block"'),
    ("r3-s1-r6-007-cd-redirect", "unmet",  {"transcript": "r6-cd-redirect"}, {}, 2, '"decision": "block"'),
    ("r3-s1-r6-008-env-ledger", "unmet",   {"transcript": "r6-env-ledger"}, {}, 2, '"decision": "block"'),
    ("r3-s1-r6-008-env-ledger-named", "unmet", {"transcript": "r6-env-ledger-named"}, {}, 2, "대상 미상 쓰기"),
    ("r3-s1-r6-009-second-assign", "unmet", {"transcript": "r6-second-assign"}, {}, 2, "대상 미상 쓰기"),
    # ⛔ **사유의 미충족 목록** (F-360) — 판정기 끝 줄만 실으면 `G11` 하나만 보인다. 이 케이스가
    #    없으면 판정기 `UNMET:` 출력 형식이 바뀔 때 사유가 조용히 한 줄로 퇴화한다. 상한 8 + 생략 수.
    ("multi-unmet",      "multi",          {}, {}, 2, "— G1, G2, G3, G4, G5, G6, G7, G8 …외 3건"),
    # ⛔ **판정기 쓰기 호출도 소유다** (F-377) — `--only` · 기본 실행 · `$L` 변수 경로 · source 한 env 파일(F-422, 명령
    #    줄에 'gates' · 'plan.md' · 판정기 이름이 없다 — 선필터가 줄을 버리면 이 케이스가 통과한다). 짝: `--status --only`
    #    는 읽기라 소유가 아니다. 원장 인자를 못 풀면 '대상 미상 쓰기' 로 그 쓰기가 돌던 폴더 아래 원장 판정(fail-closed · F-554).
    ("owned-only",       "unmet",          {"transcript": "only"}, {}, 2, '"decision": "block"'),
    ("owned-default",    "unmet",          {"transcript": "default"}, {}, 2, '"decision": "block"'),
    ("owned-var-L",      "unmet",          {"transcript": "var-L"}, {}, 2, '"decision": "block"'),
    ("owned-sourced",    "unmet",          {"transcript": "sourced"}, {}, 2, '"decision": "block"'),
    ("foreign-status-only", "unmet",       {"transcript": "status-only"}, {}, 0, "다른 세션의 원장"),
    # 원장 인자를 못 푼 쓰기 — 그 쓰기가 돌던 폴더 아래 원장은 이 세션 원장으로 판정한다(fail-closed · F-377)
    ("unknown-target",   "unmet",          {"transcript": "unknown"}, {}, 2, "대상 미상 쓰기"),
    # F-554 — 그 쓰기가 원장 밖 폴더에서 돌았으면 후보가 없다: 남의 원장으로 막지 않는다(사유만) · 상대 경로는 transcript 줄의 cwd 로 푼다
    ("f554-unresolvable-not-blocking", "unmet", {"transcript": "unknown-elsewhere"}, {}, 0, "대상 미상 쓰기"),
    ("f554-var-ledger-resolved", "unmet",  {"transcript": "rel-evcwd"}, {}, 2, '"decision": "block"'),
    # 루프 몸체가 환경 접두(`VAR=1 python3 gate_check.py …`)로 시작해도 지원 루프다 — 다른 폴더에서 `cd 티켓 &&` 로 돈 자기 원장을 소유로 막는다
    ("loop-env-prefix-owned", "unmet",     {"transcript": "loop-env-prefix"}, {}, 2, '"decision": "block"'),
    # 미상 쓰기가 폴더 밖 원장을 글자로 가리킨다(`../TICKET-0000/gates/plan.md`) — 그 원장은 후보다(막는다)
    ("f554-unknown-literal-outside-cwd", "unmet", {"transcript": "unknown-literal-outside"}, {}, 2, "대상 미상 쓰기"),
    # 미상 쓰기가 `..` 폴더를 뒤져 원장을 찾는다(`$(find ../TICKET-0000 -name plan.md)`) — 글자에 원장 경로가 없어도 그 폴더 아래는 후보다
    ("f554-unknown-find-parent", "unmet",  {"transcript": "unknown-find-parent"}, {}, 2, "대상 미상 쓰기"),
    # 같은 명령에서 cd 한 뒤의 상대 경로(`cd 티켓 && L=$(realpath gates/plan.md)`) — cd 대상 아래도 후보다
    ("f554-unknown-after-cd", "unmet",     {"transcript": "unknown-after-cd"}, {}, 2, "대상 미상 쓰기"),
    # cd 대상을 못 풀었다 — 그 쓰기가 어디서 돌았는지 모르므로 전 원장(fail-closed)
    ("f554-unknown-cd-unresolved", "unmet", {"transcript": "unknown-cd-unresolved"}, {}, 2, "대상 미상 쓰기"),
    # 절대 경로로 폴더 밖을 뒤진다(`$(find /abs/TICKET-0000 …)`) — 그 폴더 아래도 후보다
    ("f554-unknown-find-abs", "unmet",     {"transcript": "unknown-find-abs"}, {}, 2, "대상 미상 쓰기"),
    # ISSUE-202601 — `..` 이 첫 마디가 아닌 상대 폴더(`find ./../TICKET-0000`)도 정규화하면 폴더 밖 후보다
    ("r3-f554-dotdot-mid-unknown", "unmet", {"transcript": "r3-find-dotdot-mid"}, {}, 2, "대상 미상 쓰기"),
    # 폴더를 변수로만 넘긴 검색(`$(find "$X" …)`) — 그 폴더를 모르므로 전 원장이 후보다
    ("r3-f554-find-var-unknown", "unmet", {"transcript": "r3-find-var"}, {}, 2, "대상 미상 쓰기"),
    # 표 밖 꼴(이스케이프된 > 에 붙은 연산자)로 원장을 쓴다 — 못 읽은 명령은 통과가 아니라 원장 쓰기 후보다(F-458)
    ("r3-unknown-final-stop-hook", "unmet", {"transcript": "r3-unlexable"}, {}, 2, "대상 미상 쓰기"),
    # 함수 정의는 토크나이저가 읽지만(Func) 본문의 판정기 호출은 이름으로 불릴 때 돈다 — 함수를 따라가지 않으므로 대상 미상이다(공백 꼴 포함)
    ("r3-s1-funcdef-stop-hook-unknown", "unmet", {"transcript": "r3-funcdef"}, {}, 2, "대상 미상 쓰기"),
    # r3 적대 검토 ISSUE-003 — heredoc 을 정규식으로 지우기 전에 원문을 읽는다: 본문의 표 밖 꼴 · 실행되는 본문 치환의 쓰기
    ("r3-f458-heredoc-unknown-stop-hook", "unmet", {"transcript": "r3-heredoc-unknown"}, {}, 2, "대상 미상 쓰기"),
    ("r3-f458-heredoc-exec-stop-hook", "unmet", {"transcript": "r3-heredoc-exec"}, {}, 2, "대상 미상 쓰기"),
    # r3 적대 검토 2차 — 글자 사전 필터보다 토크나이저가 먼저다(`$'…\141…'` 로 감춘 원장 경로) · 따옴표가 낀 원장 경로(`pl""an.md`) ·
    # 따옴표 안 `<<EOF` 가 뒤 명령을 heredoc 본문으로 삼키지 않는다
    ("r3-f458-ansi-hidden-stop-hook", "unmet", {"transcript": "r3-ansi-hidden"}, {}, 2, "대상 미상 쓰기"),
    ("r3-f458-quoted-ledger-stop-hook", "unmet", {"transcript": "r3-quoted-ledger"}, {}, 2, '"decision": "block"'),
    ("r3-f458-heredoc-quote-marker-stop-hook", "unmet", {"transcript": "r3-heredoc-quote-marker"}, {}, 2, '"decision": "block"'),
    # 글롭 cd(`cd …/TICKET-000?`) — 어느 폴더인지 확정되지 않았다(전 원장)
    ("f554-unknown-cd-glob", "unmet",      {"transcript": "unknown-cd-glob"}, {}, 2, "대상 미상 쓰기"),
    # `L=값 명령 "$L"` — 앞머리 대입은 그 명령의 환경이라 인자는 대입 전 값으로 편다(셸 규칙). 먼저 반영하면 남의 경로를 소유로 읽고 자기 원장을 놓친다
    ("temp-prefix-arg",  "unmet",          {"transcript": "temp-prefix-arg"}, {}, 2, '"decision": "block"'),
    # F-458 — 값이 물려받은 환경 변수에서 오는 `D=…; cd "$D" && … "$D/gates/plan.md"` 꼴도 소유다
    ("f458-cd-var-ledger-owned", "unmet",  {"transcript": "cd-env-var"}, {}, 2, '"decision": "block"'),
    # ⛔ **예산 소진은 통과가 아니다** (F-378 · F-404) — 소유 원장을 판정하지 못하면 미판정 수를 사유로 막는다.
    ("budget-undecided", "unmet",          {"transcript": "write"}, {"FZ_GATES_HOOK_BUDGET_S": "0"}, 2, "소유 원장 1개 미판정"),
)
# 반복 발사가 필요한 케이스 — 이름 → 발사 횟수
REPEAT_CASES = {"loop-guard": MAX_BLOCKS + 1, "loop-guard-churn": MAX_BLOCKS + 1}
# 발사 사이에 원장을 변조하는 케이스 — 판정은 그대로 두고 내용만 바꾼다
MUTATE_CASES = {"loop-guard-churn"}


PROBE_LAYOUT = {
    "d1": "gates", "d3": "a/b/gates", "d4": "a/b/c/gates", "git": ".git/gates",
}


def _write_probe_ledger(root, spec):
    """`spec` = `[배치:]종류`. 배치 미지정이면 깊이 2(`TICKET-0000/gates`). `multi` 는 미충족 11개."""
    layout, _, kind = spec.rpartition(":")
    rel = PROBE_LAYOUT.get(layout, "TICKET-0000/gates")
    gates = root / rel
    gates.mkdir(parents=True, exist_ok=True)
    name = "plan.draft.md" if kind == "draft" else "plan.md"
    state = "closed" if kind == "closed" else "active"
    approved = "APPROVED: yes\n" if kind in ("approved", "planned") else ""
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
    if kind == "multi":
        body += "".join(f"\n- [ ] G{i}: 판정 대상\n"
                        "  CRITERION: 사람이 읽는 합격 조건\n"
                        "  CHECK: echo ok\n"
                        "  EXPECT: ok\n"
                        "  CWD: /usr\n"
                        "  EVIDENCE: pending\n" for i in range(2, 12))
    target = gates / name
    target.write_text(body, encoding="utf-8")
    if kind in ("approved", "planned"):
        # ⛔ 닭-달걀: 도장을 계산하려면 파싱해야 하는데 `APPROVED: yes` 면 파싱이
        #    전수 도장을 요구한다. `--finalize` 가 정확히 그 순서를 아는 유일한 경로다
        #    — draft 로 쓰고 확정을 맡긴다. (직접 계산하려다 LedgerError 를 봤다)
        #    `planned` 는 확정 뒤 착수 전 전이까지 판정기에 맡긴다(fz-plan 4.5 순서).
        target.write_text(body.replace("APPROVED: yes\n", ""), encoding="utf-8")
        steps = [["--finalize"]] + ([["--set-state", "planned"]] if kind == "planned" else [])
        for step in steps:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "gate_check.py"), *step, str(target)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, timeout=30, check=False)


def _write_probe_transcript(root, kind: str, ledger: Path) -> Path:
    """세션 기록 흉내 — `none` 은 원장 경로를 **출력만** 한 줄(grep 결과 인용), `write` 는
    `Write` tool_use, `bash` 는 `--finalize` Bash tool_use. 진단 세션이 남의 원장 경로를
    인용하는 것이 소유로 잡히면 안 되므로 `none` 에도 경로를 넣는다."""
    tp = root / "transcript.jsonl"
    def tool_use(name, inp, cwd=None):
        ev = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name, "input": inp}]}}
        if cwd is not None:
            ev["cwd"] = str(cwd)
        return json.dumps(ev, ensure_ascii=False)
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
    elif kind == "only":
        lines.append(tool_use("Bash", {"command": f"python3 gate_check.py --only G1 {ledger}"}))
    elif kind == "default":
        lines.append(tool_use("Bash", {"command": f"python3 -B gate_check.py {ledger} 2>&1"}))
    elif kind == "var-L":
        lines.append(tool_use("Bash", {"command": 'G="${FZ_PLUGIN_ROOT}/scripts/gate_check.py"\n'
                                                  f'L={ledger}\npython3 "$G" --reverify "$L"'}))
    elif kind == "sourced":
        # 원장 경로 · 판정기 경로를 env 파일이 준다 — 명령 줄에는 'gates' · 'plan.md' · 'gate_check' 가 없다
        envf = root / "probe-env.sh"
        envf.write_text(f'export G="${{FZ_PLUGIN_ROOT}}/scripts/gate_check.py"\nexport L={ledger}\n', encoding="utf-8")
        lines.append(tool_use("Bash", {"command": f'. {envf} && python3 "$G" --set-state active "$L"'}))
    elif kind == "status-only":
        lines.append(tool_use("Bash", {"command": f"python3 gate_check.py --status --only G1 {ledger}"}))
    elif kind == "unknown":
        lines.append(tool_use("Bash", {"command": 'python3 gate_check.py --only G1 "$LEDGER_FROM_PROFILE"'}))
    elif kind == "unknown-elsewhere":
        lines.append(tool_use("Bash", {"command": 'python3 gate_check.py --only G1 "$LEDGER_FROM_PROFILE"'}, cwd=root / "elsewhere"))
    elif kind == "loop-env-prefix":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent.parent} && for s in G1 G2; do FZ_X=1 python3 gate_check.py --only $s gates/plan.md; done"},
                              cwd=root / "elsewhere"))
    elif kind == "unknown-literal-outside":
        lines.append(tool_use("Bash", {"command": 'L=$(realpath ../TICKET-0000/gates/plan.md) && python3 gate_check.py --finalize "$L"'},
                              cwd=root / "elsewhere"))
    elif kind == "unknown-find-parent":
        lines.append(tool_use("Bash", {"command": 'L=$(find ../TICKET-0000 -name plan.md -print -quit) && python3 gate_check.py --finalize "$L"'},
                              cwd=root / "elsewhere"))
    elif kind == "unknown-after-cd":
        lines.append(tool_use("Bash", {"command": f'cd {ledger.parent.parent} && L=$(realpath gates/plan.md) && python3 gate_check.py --finalize "$L"'},
                              cwd=root / "elsewhere"))
    elif kind == "unknown-find-abs":
        lines.append(tool_use("Bash", {"command": f'L=$(find {ledger.parent.parent} -name plan.md -print -quit) && python3 gate_check.py --finalize "$L"'},
                              cwd=root / "elsewhere"))
    elif kind == "r3-find-dotdot-mid":
        lines.append(tool_use("Bash", {"command": 'L=$(find ./../TICKET-0000 -name plan.md -print -quit) && python3 gate_check.py --finalize "$L"'},
                              cwd=root / "elsewhere"))
    elif kind == "r3-find-var":
        lines.append(tool_use("Bash", {"command": 'L=$(find "$FZ_PROBE_UNSET_DIR" -name plan.md -print -quit) && python3 gate_check.py --finalize "$L"'},
                              cwd=root / "elsewhere"))
    elif kind == "r3-heredoc-unknown":
        lines.append(tool_use("Bash", {"command": f'cd {ledger.parent} && cat <<EOF\n$(printf x > ${{L:-"plan.md"}})\nEOF\n'},
                              cwd=root / "elsewhere"))
    elif kind == "r3-heredoc-exec":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent} && cat <<EOF\n$(printf x > plan.md)\nEOF\n"}, cwd=root / "elsewhere"))
    elif kind == "r3-ansi-hidden":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent.parent} && printf x > $'gates/pl\\141n.md'"}, cwd=root / "elsewhere"))
    elif kind == "r3-quoted-ledger":
        lines.append(tool_use("Bash", {"command": f'cd {ledger.parent} && printf x > pl""an.md'}, cwd=root / "elsewhere"))
    elif kind == "r3-heredoc-quote-marker":
        lines.append(tool_use("Bash", {"command": f'cd {ledger.parent} && echo "<<EOF"\nprintf x > plan.md\nEOF\n'}, cwd=root / "elsewhere"))
    elif kind == "r3-unlexable":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent} && printf x \\>> plan.md"}, cwd=root / "elsewhere"))
    elif kind == "r3-funcdef":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent} && f () {{ printf x > plan.md; }}; f"}, cwd=root / "elsewhere"))
    elif kind == "r3-touch":
        lines.append(tool_use("Bash", {"command": f"cd {ledger.parent} && touch plan.md"}, cwd=root / "elsewhere"))
    elif kind == "r3-dash-c":
        lines.append(tool_use("Bash", {"command": f"dash -c 'touch {ledger}'"}, cwd=root / "elsewhere"))
    elif kind == "r3-bash-c-cd":
        lines.append(tool_use("Bash", {"command": f"bash -c 'cd {ledger.parent.parent}; printf x > gates/plan.md'"}, cwd=root / "elsewhere"))
    elif kind == "r3-spliced-quote":
        lines.append(tool_use("Bash", {"command": f"W={ledger.parent.parent}; python3 -c 'open(\"'$W'/gates/plan.md\",\"w\")'"}, cwd=root / "elsewhere"))
    elif kind == "r3-funcdef-read":
        lines.append(tool_use("Bash", {"command": f"g() {{ grep -n STATE {ledger}; }}; g"}, cwd=root / "elsewhere"))
    elif kind == "r3-named-no-literal":
        lines.append(tool_use("Bash", {"command": f"python3 tool.py --root {root} --gates-report"}, cwd=root))
    elif kind == "r6-cd-chain":
        lines.append(tool_use("Bash", {"command": "cd TICKET-0000; cd gates; printf x > plan.md"}, cwd=root))
    elif kind == "r6-subshell-cd":
        lines.append(tool_use("Bash", {"command": "(cd elsewhere && true); (cd TICKET-0000 && printf x > gates/plan.md)"}, cwd=root))
    elif kind == "r6-cd-redirect":
        lines.append(tool_use("Bash", {"command": "cd /tmp > TICKET-0000/gates/plan.md"}, cwd=root))
    elif kind == "r6-env-ledger":
        lines.append(tool_use("Bash", {"command": 'printf x > "$FZ_HOOK_PROBE_LEDGER"'}, cwd=root / "elsewhere"))
    elif kind == "r6-env-ledger-named":
        lines.append(tool_use("Bash", {"command": 'python3 edit.py "$FZ_HOOK_PROBE_LEDGER"'}, cwd=root / "elsewhere"))
    elif kind == "r6-second-assign":
        lines.append(tool_use("Bash", {"command": "A=unused B=TICKET-0000; python3 -c 'import sys; open(sys.argv[1], \"w\")' \"$B/gates/plan.md\""},
                              cwd=root))
    elif kind == "unknown-cd-glob":
        lines.append(tool_use("Bash", {"command": f'cd {str(ledger.parent.parent)[:-1]}? && python3 gate_check.py --finalize gates/plan.md'},
                              cwd=root / "elsewhere"))
    elif kind == "unknown-cd-unresolved":
        lines.append(tool_use("Bash", {"command": 'cd "$FZ_PROBE_UNSET_DIR" && python3 gate_check.py --finalize gates/plan.md'},
                              cwd=root / "elsewhere"))
    elif kind == "temp-prefix-arg":
        lines.append(tool_use("Bash", {"command": 'L=../TICKET-0000/gates/plan.md; for s in G1 G2; do '
                                                  'L=../OTHER/gates/plan.md python3 gate_check.py --only "$s" "$L"; done'},
                              cwd=root / "elsewhere"))
    elif kind == "rel-evcwd":
        # 앞 호출에서 `cd …/TICKET-0000` 한 뒤의 상대명 — 명령 안에 cd 가 없고 transcript 줄의 cwd 만 그 폴더다
        lines.append(tool_use("Bash", {"command": "python3 gate_check.py --finalize gates/plan.md"}, cwd=ledger.parent.parent))
    elif kind == "cd-env-var":
        # 줄의 cwd 는 원장 밖 — 환경으로 풀지 못하면 대상 미상이 되고 후보도 0 이라(F-554) 막지 않는다. 풀어야 소유로 막는다
        lines.append(tool_use("Bash", {"command": 'D="$FZ_HOOK_PROBE_ROOT/TICKET-0000"; cd "$D" && '
                                                  'python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py" --finalize "$D/gates/plan.md"'},
                              cwd=root / "elsewhere"))
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
    gcmod = load_checker_module()
    ledger_env = getattr(gcmod, "LEDGER_ENV", "FZ_GATES_LEDGER")
    # ⛔ 상태 파일을 격리한다 — 사용자 실 상태를 오염시키면 안 되고,
    #    이전 회차 카운트가 남으면 unmet-blocks 가 통과로 뒤집힌다.
    home = Path(tempfile.mkdtemp(prefix="fz-hook-home-"))
    passed, failed, passed_names = 0, [], set()
    # ⛔ 판정기 옵션 어휘 — `GATE_OPTS` · `GATE_VALUE_OPTS` 가 판정기 add_argument 와 갈리면 새 쓰기 옵션을 쓴 호출이
    #    '어휘 밖 → argparse 거부' 로 읽혀 소유에서 빠진다(fail-open). 판정기 소스에서 직접 긁어 두 집합을 대조한다.
    try:
        src = (ROOT / "scripts" / GATE_CHECK_NAME).read_text(encoding="utf-8")
    except OSError:
        src = ""
    decl = re.findall(r'add_argument\(\s*"(--[\w-]+)"([^)]*)', src)
    opts = {n for n, _ in decl} | {"--help"}
    vals = {n for n, rest in decl if 'action="store_true"' not in rest}
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    if decl and opts == GATE_OPTS and vals == GATE_VALUE_OPTS:
        passed += 1
        if listing:
            print("  ok   gate-vocab")
    else:
        failed.append(f"gate-vocab: 판정기 어휘 불일치 — 없음 {sorted(opts - GATE_OPTS)} · 뜻밖 {sorted(GATE_OPTS - opts)} · "
                      f"값 옵션 없음 {sorted(vals - GATE_VALUE_OPTS)} · 뜻밖 {sorted(GATE_VALUE_OPTS - vals)}")
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
            # ⛔ 바깥 셸의 원장 지정 · 추적 · 예산 노브를 넘기지 않는다 — 넘기면 바깥 원장을 판정하거나 케이스가 흔들린다
            for var in (ledger_env, "FZ_GATES_OFF", "FZ_GATES_TRACE", BUDGET_ENV):
                child.pop(var, None)
            child.update(env)
            child["FZ_HOOK_PROBE_ROOT"] = str(d)        # cd-env-var — 물려받은 환경 변수로 원장 폴더를 준다(F-458)
            child["FZ_HOOK_PROBE_LEDGER"] = str(d / "TICKET-0000" / "gates" / "plan.md")   # r6-env-ledger — 값이 원장 경로인 환경 변수
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
                passed_names.add(name)
                if listing:
                    print(f"  ok   {name}")
        finally:
            shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(home, ignore_errors=True)
    # 대체 경로 parity(F-458) — 수정 전 트리(002df3b)에서 차단(exit 2)이던 케이스는 같은 이름 · 같은 기대로 남아 이번에도 차단돼야
    # 한다. 공용 토크나이저로 옮긴 조각 나누기 · 단어 · 따옴표 판정이 그 케이스들의 소유 · 미상 판정을 지나간다
    blocked_before = frozenset(("approved-unmet", "budget-undecided", "depth1", "depth2", "depth3", "depth4", "f458-cd-var-ledger-owned", "f554-unknown-after-cd", "f554-unknown-cd-glob", "f554-unknown-cd-unresolved", "f554-unknown-find-abs", "f554-unknown-find-parent", "f554-unknown-literal-outside-cwd", "f554-var-ledger-resolved", "loop-env-prefix-owned", "multi-unmet", "owned-bash", "owned-bash-cd", "owned-bash-var", "owned-default", "owned-ledger", "owned-only", "owned-py-c", "owned-py-heredoc", "owned-redirect", "owned-sourced", "owned-var-L", "planned-reason", "temp-prefix-arg", "transcript-missing", "unknown-target"))
    still = {n for n, _k, _o, _e, want, _w in SELF_TEST_CASES if want == EXIT_BLOCK} & passed_names
    if blocked_before <= still:
        passed += 1
        if listing:
            print("  ok   r3-replaced-path-parity-stop-hook")
    else:
        failed.append(f"r3-replaced-path-parity-stop-hook: 수정 전 차단이던 케이스가 빠졌거나 통과로 바뀌었다 — {sorted(blocked_before - still)}")

    for f in failed:
        print(f"  FAIL {f}", file=sys.stderr)
    total = len(SELF_TEST_CASES) + 2            # + gate-vocab · parity
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
