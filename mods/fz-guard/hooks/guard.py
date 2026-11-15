#!/usr/bin/env python3
"""fz-guard — fz 규칙 셋을 도구 호출 자리에서 기계로 강제하는 classic command 훅 (표준 라이브러리만).

규칙
  P4  F-368 · F-384 · F-451 · F-119 · F-553 — `/fz`(또는 Skill fz) 호출 뒤 Phase 4 승인 전에는 쓰기 도구 · Workflow ·
      쓰는 Bash(리다이렉트 · tee · sed -i · 인터프리터 heredoc)를 deny 한다. 레지스트리 entries/ 와 Phase 0 의
      WORK_DIR 초기화({cwd}/{티켓 · NOTASK-날짜}/index.md)는 막지 않는다.
      승인 = AskUserQuestion 의 header 가 'Phase 4' 인 질문에 제시한 선택지 라벨(커스텀 · 취소류 제외)로 답한 것.
      창은 연 prompt 안에서만 판정한다 — 승인 없이 그 턴을 끝내면 Stop 을 1회 막는다. 셋 다 interactive(entrypoint=cli)에서만 발화한다.
      질문 없이 긴 답(LONG_ANSWER 자 이상)으로 끝낸 턴은 Stop 에 경고를 따로 싣는다(F-451 · 차단 아님).
  AG  F-058 · F-119 — fz 세션 표지(/fz · /fz-* · /fz:* · Skill fz*)가 선 세션에서 Agent · Task 의 subagent_type 이
      native 채택 목록(modules/native-agents.md) 밖이면 ask 한다.
  FR  F-518 · F-565 — 같은 prompt_id 에서 메모리에 fz 교훈을 쓰고 레지스트리 entries/F-*.md 쓰기가 없으면 Stop 을 1회 막는다.
      교훈 토큰은 마크다운 링크 · 백틱을 지운 본문에서 찾는다(링크만 든 MEMORY.md 는 교훈이 아니다).
  GP  F-094 · F-297 — fz-review 를 부른 턴이 GPT 리뷰 호출도 '[외부: GPT]' · '[GPT 미사용 — 사유]' 줄도 없이 끝나면 Stop 을
      1회 막는다(interactive 한정). fz 플러그인 파일에 옛 모델 호칭을 넣는 쓰기는 모드와 무관하게 deny 한다 —
      판별식은 그 저장소의 scripts/check_gpt_surface.py 를 불러 그대로 쓴다(못 부르면 이 판정만 건너뛴다).
      /fz 창이 연 prompt 에서 skills/fz-review/SKILL.md 를 Read 해 도는 fz-review 도 리뷰 턴이다(PostToolUse Read ·
      다른 경로 Read 는 상태를 열기 전에 돌아간다 — 모든 Read 에 훅이 붙는 비용을 잠금 · 저장 0 으로 둔다).
  보호 경로 F-024 — env FZ_GUARD_PROTECTED(os.pathsep 구분) · <상태 폴더>/protected(줄마다 경로 · # 주석) 가 있으면 그 아래에서
      도는 Bash(cwd · `git -C` · 경로 인자)와 대상을 모르는 Bash(못 읽는 명령 · 확장이 든 cd · pushd · git -C 대상)를 ask 한다
      (거부 아님 · 사유 표시 · P4 deny 를 덮지 않는다). 기본은 비어 있어 아무 일도 하지 않는다 · 상태 파일을 열지 않는다.

상태 정리(F-564) — UserPromptSubmit 마다 마지막 기록이 STALE_DAYS 지난 다른 세션의 상태 · 잠금을 지운다(사건 1회에 최대 PRUNE_MAX).

사건은 훅 입력에서 상태로 기록한다 — ⛔ transcript 는 비동기로 기록돼 현재 사건이 아직 없을 수 있다(공식 훅 문서).
transcript 에서는 굳은 사실 하나만 읽는다: 첫 줄들의 entrypoint(cli=interactive · sdk-cli=headless · 그 밖=불명).

상태   ${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/<session_id>.json — 세션별 잠금(<session_id>.lock · fcntl.flock)으로
       읽기 · 병합 · 판정 · 저장을 직렬화하고 mkstemp + os.replace 로 원자 교체한다. 플러그인 폴더 안이면 쓰지 않는다
끄기   env FZ_GUARD_DISABLE=P4,AG,FR,GP|all · 파일 플래그 <상태 폴더>/disable(내용 = 규칙 목록 · 비면 all) — 매 실행 확인
실패   ⛔ 입력 · 의존성 · 잠금 · 상태 오류는 전부 exit 0 · 결정 없음(fail-open). 진단은 stderr `fz-guard diag:` 로만 낸다

모드
  (인자 없음)                훅 — stdin JSON 하나 → stdout 결정 JSON(없으면 빈 출력) · exit 0
  --self-test                합성 입력 92 케이스 — `PASS <case>` 줄
  --check-allowlist FILE     native-agents.md 채택 표 == ALLOW_AGENTS 인가 (0 일치 · 1 불일치 · 2 표 없음)
  --make-synthetic BYTES OUT --with-marker|--no-marker   큰 transcript 합성(첫 줄들에 entrypoint 를 둘지)
  --bench FILE               entrypoint 판정 소요 — `mode=<…> elapsed_ms=<n>`
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:                                               # 공용 토크나이저(F-458) — 설치본은 이 폴더의 사본을 읽는다(-I 로 돌아도)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import shell_tokens
except Exception:                                   # noqa: BLE001 — 권한 · 구문 오류도 같다(ImportError 만 잡으면 훅이 죽는다)
    shell_tokens = None                            # 판정은 보수 쪽(쓰기 대상 미상 · GPT 호출 아님)으로 끝난다 — 정규식으로 돌아가지 않는다

HERE = pathlib.Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
RULES = ("P4", "AG", "FR", "GP")
WRITE_EXACT = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
SERENA_WRITE = re.compile(r"^mcp__.*serena__(replace_symbol_body|insert_after_symbol|insert_before_symbol|replace_content|"
                          r"replace_in_files|rename_symbol|safe_delete_symbol)$")
XCODE_WRITE = re.compile(r"^mcp__xcode__Xcode(Write|Update|MV|RM|MakeDir)$")
AGENT_TOOLS = {"Agent", "Task"}
# modules/native-agents.md 채택 표와 같아야 한다 — `--check-allowlist` 가 대조한다(health-check 5.2)
ALLOW_AGENTS = {"silent-failure-hunter", "type-design-analyzer", "code-simplifier", "deep-research-agent"}
PHASE4_HEADER = "Phase 4"
NOT_APPROVAL = re.compile(r"커스텀|취소|거절|중단|cancel|reject|abort", re.I)
# F-565 — F-ID 는 그 자체로 교훈 기록이다. fz 이름(fz-findings 포함)만 든 본문은 교훈 단서어가 함께 있어야 교훈이다 — 스킬 이름 ·
#   경로를 적은 토픽 파일마다 Stop 을 1회 막던 오탐을 줄인다. ponytail: 단서어 없이 적은 fz 교훈은 놓친다(1회 알림 상실) — 놓친 사례가
#   나오면 그 낱말을 LESSON_CUE 에 더한다(F-518 원래 사례 '교훈 · 미뤘다' 는 셀이 지킨다)
FINDING_ID = re.compile(r"F-\d{3}")
FZ_NAME = re.compile(r"fz-")
LESSON_CUE = re.compile(r"교훈|놓[쳤친치]|결함|실패|오탐|누락|회귀|버그|틀렸|잘못|빠뜨|미뤘|lesson|missed|defect|regress|bug", re.I)
LINK_OR_CODE = re.compile(r"\[[^\]\n]*\]\([^)\n]*\)|`[^`\n]*`")   # F-565 — 링크 · 백틱 안의 스킬 이름은 교훈이 아니다
WORKDIR_NAME = re.compile(r"^(?:[A-Z]{2,6}-\d{2,5}|NOTASK-\d{8})$")   # modules/context-artifacts.md Work Dir Resolution
REVIEW_SKILLS = {"fz-review", "fz:fz-review"}
REVIEW_SKILL_FILE = re.compile(r"(^|/)skills/fz-review/SKILL\.md$")   # F-094 — /fz 안에서 Read 로 도는 fz-review
GPT_MARK = re.compile(r"\[외부:\s*GPT\]|\[GPT 미사용")
# Bash 쓰기 판별(F-119) — 공용 해석기(shell_tokens.commands)가 정한 명령 자리마다 아래 읽기 표(READ)를 대본다(F-458)
WRITE_OPS = {">", ">>", ">|", "&>", "&>>", "<>"}
UNRESOLVED = re.compile(r"[*?\[{~]")                # 글롭 · 중괄호 · 물결 — 셸이 바꾸는 꼴은 경로로 읽지 않는다
QUIET = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"}
MEMORY_PATH = re.compile(r"(^|/)\.claude/projects/[^/]+/memory/[^/]+\.md$")
ENTRY_NAME = re.compile(r"^F-\d{3}[a-z]?[^/]*\.md$")
COMMAND_NAME = re.compile(r"^\s*<command-name>\s*(\S+?)\s*</command-name>")
PATH_KEYS = ("file_path", "notebook_path", "relative_path", "path", "filePath", "sourcePath", "destinationPath")
TEXT_KEYS = ("content", "new_string", "new_source", "body", "repl", "new_content")
PREFIX_BYTES, PREFIX_LINES = 4 << 20, 400        # ⛔ 하드 캡 — 큰 transcript 를 끝까지 읽지 않는다(entrypoint 가 없어도)
LOCK_TIMEOUT = 3.0
KEEP_PROMPTS = 64
STALE_DAYS, PRUNE_MAX = 7, 200                    # F-564 — 이 날수보다 오래 기록이 없는 세션 상태를 지운다
LONG_ANSWER = 1500                                # F-451 — 승인을 묻기 전 답이 이 글자 수 이상이면 경고

WARN_UNDECIDED = "FZ-GUARD-WARN P4-UNDECIDED"
WARN_INCOMPLETE = "FZ-GUARD-WARN STATE-INCOMPLETE"
WARN_LONG = "FZ-GUARD-WARN P4-LONG-ANSWER"
P4_DENY = ("fz-guard P4 (F-368): this session ran /fz and the Phase 4 approval has not been given. Show the pipeline and ask "
           "the user with AskUserQuestion (header 'Phase 4') before writing files or starting a Workflow. Writes to the "
           "fz-findings registry entries/ are allowed. Autonomous runs start the CLI with FZ_AUTONOMY=autonomous.")
P4_STOP = ("fz-guard P4 (F-368): /fz ran in this session but the turn is ending without the Phase 4 approval. Ask the user "
           "with AskUserQuestion (header 'Phase 4' - options = the pipeline choices) before going on.")
FR_STOP = ("fz-guard FR (F-518): this turn wrote an fz lesson to a memory file but wrote no registry entry "
           "(fz-findings/entries/F-*.md). Record the finding in the registry this turn, or state in the reply why it is not one.")
GP_STOP = ("fz-guard GP (F-094): this turn ran fz-review but shows no GPT review - no `gpt-call.sh review` call and no "
           "'[외부: GPT]' or '[GPT 미사용 — <reason>]' line in the reply. Run the GPT review, or write the skip line with its reason.")
PP_ASK = "fz-guard 보호 경로(F-024): 이 명령이 보호 경로에 닿는다 — 분석 작업이 대상 시스템에서 명령을 돌리기 전에 확인한다 · "
GP_DENY = ("fz-guard GP (F-297): this write puts the retired model name into an fz plugin file outside the keep rules of "
           "scripts/check_gpt_surface.py. In fz the model is called GPT. Lines: ")


class LockTimeout(Exception):
    pass


# ── 판정 재료 ──────────────────────────────────────────────────────
def write_tool(name: str) -> bool:
    return name in WRITE_EXACT or bool(SERENA_WRITE.match(name)) or bool(XCODE_WRITE.match(name))


def p4_tool(name: str) -> bool:
    return write_tool(name) or name == "Workflow"


def autonomous(env) -> bool:
    """scripts/autonomy_decide.py normalize_mode 와 같은 정규화(strip · lower) — 표기 차이로 /fz 는 자율 · 가드는 interactive 로 갈리지 않게."""
    return (env.get("FZ_AUTONOMY") or "").strip().lower() == "autonomous"


def first_token(prompt) -> str:
    """사용자 입력의 첫 토큰. 슬래시 명령이 `<command-name>/fz</command-name>` 꼴로 와도 푼다."""
    if not isinstance(prompt, str):
        return ""
    m = COMMAND_NAME.match(prompt)
    if m:
        return m.group(1) if m.group(1).startswith("/") else "/" + m.group(1)
    parts = prompt.strip().split(None, 1)
    return parts[0] if parts else ""


def opens_window(token: str) -> bool:
    return token in ("/fz", "/fz:fz")          # ⛔ /fz-code · /fz:fz-plan 같은 직접 호출은 명시 모드라 Phase 4 를 묻지 않는다


def fz_marker(name: str) -> bool:
    name = name[1:] if name.startswith("/") else name
    return name == "fz" or name.startswith("fz-") or name.startswith("fz:")


def paths_of(ti: dict) -> list:
    return [ti[k] for k in PATH_KEYS if isinstance(ti.get(k), str) and ti[k]]


def text_of(ti: dict) -> str:
    parts = [ti[k] for k in TEXT_KEYS if isinstance(ti.get(k), str)]
    parts += [e["new_string"] for e in ti.get("edits") or [] if isinstance(e, dict) and isinstance(e.get("new_string"), str)]
    return "\n".join(parts)


def in_registry(path: str, env) -> bool:
    """fz-findings 레지스트리 entries/ 아래인가 — FZ_FINDINGS_ROOT 가 있으면 그 아래, 없으면 경로의 `fz-findings/entries/`."""
    # ⛔ 정규화 뒤 판정한다 — `…/fz-findings/entries/../../src/a.js` 가 면제로 새지 않게
    # ponytail: 어휘 정규화(normpath)만 — entries/ 안의 심볼릭 링크가 밖을 가리키는 경우는 못 막는다, 필요하면 realpath 양쪽 대조
    p = os.path.normpath(os.path.abspath(os.path.expanduser(path)))
    root = env.get("FZ_FINDINGS_ROOT")
    if root:
        base = os.path.normpath(os.path.abspath(os.path.expanduser(root))) + "/entries/"
        if p.startswith(base):
            return True
    return "/fz-findings/entries/" in p


def registry_entry(path: str, env) -> bool:
    return in_registry(path, env) and bool(ENTRY_NAME.match(os.path.basename(path)))


def workdir_index(path: str, cwd) -> bool:
    """F-553 — /fz Phase 0 의 WORK_DIR 초기화는 Phase 4 보다 먼저다: {cwd}/{티켓 · NOTASK-날짜}/index.md 만 허용한다."""
    if not isinstance(cwd, str) or not cwd:
        return False
    base = os.path.normpath(os.path.abspath(os.path.expanduser(cwd)))
    p = os.path.normpath(os.path.join(base, os.path.expanduser(path)))   # ⛔ `..` 를 접은 뒤 판정한다
    d = os.path.dirname(p)
    return os.path.basename(p) == "index.md" and bool(WORKDIR_NAME.match(os.path.basename(d))) and os.path.dirname(d) == base


def workdir_dir(path: str, cwd) -> bool:
    """F-553 — Phase 0 의 WORK_DIR 폴더 {cwd}/{티켓 · NOTASK-날짜} 그 자체. mkdir 대상으로만 면제한다(rm 대상은 면제가 아니다)."""
    if not isinstance(cwd, str) or not cwd:
        return False
    base = os.path.normpath(os.path.abspath(os.path.expanduser(cwd)))
    p = os.path.normpath(os.path.join(base, os.path.expanduser(path)))
    return bool(WORKDIR_NAME.match(os.path.basename(p))) and os.path.dirname(p) == base


def exempt(path: str, env, cwd) -> bool:
    return in_registry(path, env) or workdir_index(path, cwd)


def gpt_review_invoked(cmd) -> bool:
    """명령 자리에서 `gpt-call.sh review | independent-review` 를 실행하는가(F-094).

    grep · echo 인자나 heredoc 본문에 든 언급은 호출이 아니다 — 문자열 검색으로 세면 읽기만 한 턴이 GP 계약을 통과한다.
    명령 자리는 공용 해석기(shell_tokens.commands)가 정한다 — 예약어 · 환경 대입 · 래퍼와 그 옵션 · `bash 스크립트` 를 벗기고, 표 밖
    래퍼 옵션(`command -v` · `bash -n` · `bash -c`)이면 명령 자리를 모른다. 치환 안도 본다. 함수 정의 본문 · 함수에 붙은 리다이렉트는
    정의만 되고 실행되지 않는다(호출 아님).
    ⛔ 못 읽으면(표 밖 꼴 · 명령 자리 미상 · 토크나이저 없음) 호출이 아니다 — 문자열 판정으로 돌아가지 않는다(F-458).
    """
    if not isinstance(cmd, str) or "gpt-call" not in cmd or shell_tokens is None:
        return False
    cmds = shell_tokens.commands(shell_tokens.lex(cmd), shells=True)
    return not shell_tokens.is_unknown(cmds) and _gpt_call_in(cmds)


def _gpt_call_in(cmds) -> bool:
    return any(c.name is not None and not c.deferred and not c.unsure and os.path.basename(c.name.text) == "gpt-call.sh"
               and c.args and c.args[0].text in ("review", "independent-review") for c in cmds)


# ── 승인 전 창(P4)의 읽기 표 — 이름: True(어느 꼴이든 읽기) | 판정 함수(인자 → 읽기 꼴인가). ⛔ 표 밖 이름은 전부 대상 미상 쓰기다.
# 인터프리터(python · node · 셸 · perl · ruby)는 표에 없다 — 코드가 무엇을 쓰는지 읽지 않는다(쓰기 신호 표를 두지 않는다 · F-458).
# 판정 함수는 읽기 꼴만 받는다(허용 목록) — 쓰기 모드가 있는 명령(sed -i · sort -o · find -delete · git 쓰기 하위 명령 …)의 표 밖 꼴은 미상이다.
# 옵션은 따옴표와 무관하게 옵션이다(`'-i'` 도 프로그램에는 -i). 펼쳐지는 인자(`"$W/a"` · `$SHA`)는 값(경로 · 리비전 · 줄 번호)으로 본다 —
# ponytail: 펼친 값이 옵션이 되는 꼴(`X=--output=f; git diff $X`)은 만든 꼴이라 보지 않는다. 프로그램 · 하위 명령 자리의 펼침은 거절한다
_EXPANSION = re.compile(r"\$\{[^{}]*\}|\$\((?:[^()]|\([^()]*\))*\)|`[^`]*`|\$[A-Za-z_][A-Za-z0-9_]*|\$[0-9?#@*$!-]")


def _sed_delim_end(s: str, i: int, d: str) -> int:
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == d:
            return i
        if s[i] == "\n":
            return -1
        i += 1
    return -1


def _sed_script_reads(s: str) -> bool:
    """sed 스크립트가 읽기 문법 안인가 — 주소(N · $ · /re/ · N~M · 범위) · ! · { } · p d n N P D q Q = l h H g G x z · s///(플래그 g p i I M 숫자) · y///.
    w · W · e · r · R · a · i · c · 분기 · 표 밖 플래그(s///w · s///e)는 거절한다."""
    i, n, depth = 0, len(s), 0

    def addr(i):
        if i < n and s[i].isdigit():
            while i < n and (s[i].isdigit() or s[i] == "~"):
                i += 1
            return i
        if i < n and s[i] == "$":
            return i + 1
        if i < n and s[i] in "/\\":
            j = _sed_delim_end(s, i + 2, s[i + 1]) if s[i] == "\\" and i + 1 < n else _sed_delim_end(s, i + 1, "/")
            if j < 0:
                return -1
            j += 1
            while j < n and s[j] in "IM":
                j += 1
            return j
        return i
    while True:
        while i < n and s[i] in " \t\n;":
            i += 1
        if i >= n:
            return depth == 0
        j = addr(i)
        if j < 0:
            return False
        if i < j < n and s[j] == ",":
            k = j + 1
            if k < n and s[k] in "+~":
                k += 1
                while k < n and s[k].isdigit():
                    k += 1
                j = k
            else:
                j = addr(k)
                if j <= k:
                    return False
        i = j
        while i < n and s[i] in " \t":
            i += 1
        if i < n and s[i] == "!":
            i += 1
            while i < n and s[i] in " \t":
                i += 1
        if i >= n:
            return False
        c = s[i]
        if c in "{}":
            depth += 1 if c == "{" else -1
            if depth < 0:
                return False
            i += 1
        elif c in "pdnNPDqQ=lhHgGxz":
            i += 1
            while i < n and s[i].isdigit():
                i += 1
        elif c in "sy" and i + 1 < n and s[i + 1] not in "\\\n":
            j = _sed_delim_end(s, i + 2, s[i + 1])
            j = _sed_delim_end(s, j + 1, s[i + 1]) if j >= 0 else -1
            if j < 0:
                return False
            i = j + 1
            while c == "s" and i < n and (s[i] in "gpiIM" or s[i].isdigit()):
                i += 1
        else:
            return False


SED_LONG = {"--quiet", "--silent", "--regexp-extended", "--posix", "--debug", "--sandbox", "--null-data", "--separate", "--unbuffered"}


def _sed_reads(args) -> bool:
    """sed — -i · -f · 표 밖 옵션이 없고 스크립트(-e 값 · 첫 피연산자)가 읽기 문법 안이다."""
    scripts, pos, i = [], [], 0
    while i < len(args):
        t = args[i].text
        if t == "--":
            pos += args[i + 1:]
            break
        if t.startswith("-") and t != "-":
            if t in ("-e", "--expression"):
                if i + 1 >= len(args):
                    return False
                scripts.append(args[i + 1])
                i += 2
                continue
            if not (re.fullmatch(r"-[nErsuz]+", t) or t in SED_LONG):
                return False                       # -i · -f · -l · 표 밖
        else:
            pos.append(args[i])
        i += 1
    scripts = scripts or pos[:1]                   # 스크립트 안 펼침(`"${A},${B}p"`)은 숫자 자리로 읽는다 — 명령 글자 자리면 문법이 거절한다
    return bool(scripts) and all(_sed_script_reads(_EXPANSION.sub("1", w.text) if w.expands else w.text) for w in scripts)


def _awk_reads(args) -> bool:
    """awk — 프로그램이 펼쳐지지 않고 파이프(`|` — `||` 제외) · system( · print/printf 뒤 `>` 가 없다. -f · 표 밖 옵션은 거절."""
    i = 0
    while i < len(args):
        t = args[i].text
        if t in ("-F", "-v"):
            i += 2
        elif t[:2] in ("-F", "-v") or t == "--":
            i += 1
        elif t.startswith("-") and t != "-":
            return False
        else:
            break
    if i >= len(args) or args[i].expands:
        return False
    s = args[i].text.replace("||", "")
    if "|" in s or re.search(r"\bsystem\s*\(", s):
        return False
    return not any(re.search(r"\bprintf?\b[^>]*>", st) for st in re.split(r"[;{}\n]", s))


FIND_OK = frozenset(("-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex", "-lname", "-ilname", "-type",
                     "-maxdepth", "-mindepth", "-mtime", "-mmin", "-atime", "-amin", "-ctime", "-cmin", "-newer", "-newermt", "-size",
                     "-perm", "-user", "-group", "-links", "-inum", "-samefile", "-empty", "-print", "-print0", "-printf", "-ls", "-prune",
                     "-o", "-or", "-a", "-and", "-not", "-depth", "-d", "-xdev", "-mount", "-quit", "-true", "-false", "-follow", "-L",
                     "-H", "-P", "-E", "-s", "-x", "-nouser", "-nogroup", "-readable", "-writable", "-executable", "-regextype"))


def _find_reads(args) -> bool:
    """find — 옵션 단어가 전부 검사 · 출력 표 안이다(-delete · -exec · -ok · -fprint 류는 표 밖)."""
    return all(not w.text.startswith("-") or w.text in FIND_OK or re.fullmatch(r"[-+]\d+[a-zA-Z]?", w.text) for w in args)


SORT_LONG = {"--numeric-sort", "--reverse", "--unique", "--key", "--field-separator", "--ignore-case", "--human-numeric-sort",
             "--version-sort", "--stable", "--general-numeric-sort", "--month-sort", "--random-sort", "--check", "--merge", "--sort",
             "--zero-terminated", "--ignore-leading-blanks", "--dictionary-order", "--temporary-directory", "--buffer-size", "--parallel"}


def _sort_reads(args) -> bool:
    """sort — -o · --output · --compress-program · 표 밖 옵션이 없다."""
    skip = False
    for w in args:
        t = w.text
        if skip or not t.startswith("-") or t == "-":
            skip = False
            continue
        if t == "--":
            break
        if t.startswith("--"):
            if t.split("=", 1)[0] not in SORT_LONG:
                return False
            continue
        for k, ch in enumerate(t[1:]):
            if ch in "ktTS":
                skip = k == len(t) - 2             # 값이 다음 단어다
                break
            if ch not in "nrufbhVsgMRcCmzdi":
                return False                       # -o 와 표 밖
    return True


def _uniq_reads(args) -> bool:
    """uniq — 피연산자가 하나 이하다(둘째 피연산자는 출력 파일이다)."""
    n, skip = 0, False
    for w in args:
        t = w.text
        if skip:
            skip = False
        elif t in ("-f", "-s", "-w"):
            skip = True
        elif t.startswith("-") and t != "-":
            if not re.fullmatch(r"-[cdDuiz]+|-[fsw]\d+|--(?:count|repeated|unique|ignore-case|zero-terminated|all-repeated|skip-fields|"
                                r"skip-chars|check-chars)(?:=\S*)?", t):
                return False
        else:
            n += 2 if w.expands and not w.quoted else 1   # 따옴표 없는 펼침은 낱말이 갈린다 — 둘째 피연산자(출력 파일)가 될 수 있다
    return n <= 1


GIT_READ = frozenset(("status", "log", "show", "diff", "grep", "rev-parse", "ls-tree", "ls-files", "ls-remote", "merge-base", "rev-list",
                      "cat-file", "for-each-ref", "blame", "annotate", "describe", "shortlog", "show-ref", "name-rev", "whatchanged",
                      "range-diff", "cherry", "check-ignore", "check-attr", "count-objects", "var", "version", "help", "diff-tree",
                      "diff-index", "diff-files", "show-branch", "verify-commit", "verify-tag", "--version", "--help"))
GIT_GLOBAL = {"--no-pager", "-P", "--no-optional-locks", "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
              "--icase-pathspecs", "--no-replace-objects", "--bare"}
GIT_LIST_TAKES = {"--contains", "--no-contains", "--merged", "--no-merged", "--points-at", "--sort", "--format"}
GIT_LIST_FLAGS = {"-a", "-r", "-v", "-vv", "--all", "--remotes", "--verbose", "--show-current", "--no-color", "--color", "--column",
                  "--no-column", "-i", "--ignore-case", "--omit-empty", "--list", "-l"}
GIT_CONFIG_GET = {"--get", "--get-all", "--get-regexp", "--list", "-l", "--get-urlmatch", "--get-color", "--get-colorbool"}
GIT_CONFIG_FLAGS = {"--global", "--local", "--system", "--worktree", "--show-origin", "--show-scope", "--name-only", "--null", "-z",
                    "--bool", "--int", "--path", "--includes", "--no-includes", "--bool-or-int", "--expiry-date", "--all", "--regexp"}
GIT_CONFIG_TAKES = {"--file", "-f", "--blob", "--type", "--default"}


def _plain(args) -> list:
    return [w for w in args if not w.text.startswith("-")]


def _git_list_reads(r) -> bool:
    """git branch · tag 의 목록 꼴 — 이름 인자는 --list · -l 과 함께일 때만(아니면 만든다)."""
    listing, i = any(w.text in ("--list", "-l") for w in r), 0
    while i < len(r):
        t = r[i].text
        if t in GIT_LIST_TAKES:
            i += 2
        elif t.split("=", 1)[0] in GIT_LIST_TAKES | {"--color", "--column"} or t in GIT_LIST_FLAGS or re.fullmatch(r"-n\d*", t):
            i += 1
        elif not t.startswith("-") and listing:
            i += 1
        else:
            return False
    return True


def _git_config_reads(r) -> bool:
    """git config 의 조회 꼴 — --get 류 · --list · 새 꼴 `config get|list` · 키 하나만."""
    if r and r[0].text in ("get", "list"):
        r = r[1:]
    elif not (any(w.text in GIT_CONFIG_GET for w in r) or len(_plain(r)) == 1):
        return False
    i = 0
    while i < len(r):
        t = r[i].text
        if t in GIT_CONFIG_TAKES:
            i += 2
        elif t in GIT_CONFIG_GET or t in GIT_CONFIG_FLAGS or t.split("=", 1)[0] in GIT_CONFIG_TAKES or not t.startswith("-"):
            i += 1
        else:
            return False
    return True


GIT_FORMS = {
    "branch": _git_list_reads, "tag": _git_list_reads, "config": _git_config_reads,
    "remote": lambda r: all(w.text in ("-v", "--verbose") for w in r if w.text.startswith("-"))
    and (not _plain(r) or _plain(r)[0].text in ("get-url", "show")),
    "stash": lambda r: bool(r) and r[0].text in ("list", "show"),
    "worktree": lambda r: bool(r) and r[0].text == "list",
    "notes": lambda r: not r or r[0].text in ("list", "show"),
    "reflog": lambda r: not r or r[0].text in ("show", "exists") or r[0].text.startswith("-"),
    "symbolic-ref": lambda r: len(_plain(r)) <= 1 and all(w.text in ("-q", "--quiet", "--short") for w in r if w.text.startswith("-")),
    "archive": lambda r: not any(w.text.startswith("-o") for w in r),
    "apply": lambda r: any(w.text in ("--check", "--stat", "--numstat", "--summary") for w in r) and not any(w.text == "--apply" for w in r),
}


def _git_reads(args) -> bool:
    """git — 전역 옵션(-C 값 · --no-pager …) 뒤 하위 명령이 읽기 표(GIT_READ) 안이거나 GIT_FORMS 의 읽기 꼴이다.
    -c(설정 덮기) · 표 밖 전역 옵션 · 어디든 --output · grep -O(페이저 실행)는 거절한다."""
    i = 0
    while i < len(args) and (args[i].text in GIT_GLOBAL or args[i].text == "-C" or args[i].text.startswith(("--git-dir=", "--work-tree="))):
        i += 2 if args[i].text == "-C" else 1
    if i >= len(args):
        return i == len(args)
    sub, rest = args[i].text, args[i + 1:]
    if args[i].expands or any(w.text == "--output" or w.text.startswith("--output=") for w in rest):
        return False
    if sub in GIT_READ:
        return not (sub == "grep" and any(w.text in ("-O", "--open-files-in-pager") or w.text.startswith("--open-files-in-pager=")
                                          for w in rest))
    return sub in GIT_FORMS and GIT_FORMS[sub](rest)


GH_READ = {"pr": {"view", "list", "diff", "checks", "status"}, "issue": {"view", "list", "status"}, "release": {"view", "list"},
           "repo": {"view"}, "run": {"view", "list"}, "workflow": {"view", "list"}, "auth": {"status"}, "search": None}


def _gh_reads(args) -> bool:
    """gh — 명사 · 동사가 읽기 표 안이거나 `gh api` GET(-X · --method 가 GET 이 아니거나 필드 · --input 을 주면 거절 · graphql 거절)."""
    i = 0
    while i < len(args) and args[i].text in ("-R", "--repo"):
        i += 2
    pos = args[i:]
    if not pos:
        return False
    a = pos[0].text
    if a in ("--version", "version", "--help", "help"):
        return True
    if a == "api":
        r, method, fields, k = pos[1:], None, False, 0
        while k < len(r):
            t = r[k].text
            if t in ("-X", "--method"):
                method, k = (r[k + 1].text if k + 1 < len(r) else ""), k + 2
                continue
            if t.startswith("--method="):
                method = t.split("=", 1)[1]
            elif t.startswith("-X"):
                method = t[2:]
            elif t in ("--field", "--raw-field", "--input") or t.startswith(("-f", "-F", "--field=", "--raw-field=", "--input=")):
                fields = True                      # 필드를 주면 gh 는 POST 로 바꾼다(-X GET 을 밝히면 쿼리 문자열)
            k += 1
        return bool(r) and r[0].text != "graphql" and (method or "GET").upper() == "GET" and (not fields or method is not None)
    return a in GH_READ and (GH_READ[a] is None or (len(pos) > 1 and pos[1].text in GH_READ[a]))


READ = dict.fromkeys((
    "echo", "printf", "cat", "head", "tail", "grep", "egrep", "fgrep", "cut", "wc", "ls", "tr", "diff", "cmp", "comm", "paste", "column",
    "nl", "rev", "tac", "fold", "expand", "seq", "od", "hexdump", "strings", "basename", "dirname", "realpath", "readlink", "stat", "du",
    "df", "ps", "pgrep", "lsof", "which", "type", "pwd", "true", "false", ":", "test", "[", "[[", "jq", "shasum", "md5", "md5sum",
    "sha256sum", "cksum", "sleep", "wait", "cd", "pushd", "popd", "set", "unset", "export", "local", "declare", "typeset", "readonly",
    "read", "shift", "exit", "return", "break", "continue", "env", "printenv", "command", "xargs", "whoami", "id", "uname", "sw_vers",
    "mdfind", "mdls", "tput", "locale"), True)
READ.update({"sed": _sed_reads, "awk": _awk_reads, "find": _find_reads, "sort": _sort_reads, "uniq": _uniq_reads, "git": _git_reads,
             "gh": _gh_reads,
             "rg": lambda a: not any(w.text == "--pre" or w.text.startswith("--pre=") for w in a),
             "date": lambda a: all(w.text.startswith("+") or (w.text.startswith("-") and not w.text.startswith(("-s", "--set"))) for w in a),
             "base64": lambda a: not any(w.text.startswith(("-o", "--output")) for w in a)})
# 승인 전 창에서 /fz 가 부르는 플러그인 스크립트 — 읽기만 하거나 플러그인 자기 상태(~/.fz)만 쓴다. 이름: 받는 하위 명령(None = 전부)
PLUGIN_READ = {"gpt-choice.sh": {"get", "decide", "options"}, "autonomy_decide.py": None, "mode_gate.py": None, "intent_route_probe.py": None}
MOVERS = {"cd", "pushd", "popd"}
# 대상이 보이는 쓰기 명령 — 받는 옵션 글자 묶음(값 받는 옵션 · 긴 옵션 · 표 밖 글자면 대상 미상) · `--` 뒤는 전부 대상
WRITE_ARGS = {"tee": "aip", "rm": "rfRivdPWx", "touch": "acmh", "mkdir": "pv", "cp": "RrfinpvacHLPXx", "mv": "finvh"}


def _plugin_reads(n: str, name, args) -> bool:
    """`bash …/scripts/gpt-choice.sh get` · `python3 …/scripts/mode_gate.py …` 처럼 PLUGIN_READ 의 스크립트를 부르는가 —
    스크립트 경로는 펼쳐져도 된다(`${FZ_PLUGIN_ROOT}`) · 마지막 두 마디(scripts/이름)와 하위 명령 글자로 가린다."""
    if re.fullmatch(r"python[0-9.]*|bash|sh|zsh", n):
        if not args:
            return False
        name, args = args[0], args[1:]
    script = name.text
    base = os.path.basename(script)
    if os.path.basename(os.path.dirname(script)) != "scripts" or base not in PLUGIN_READ:
        return False
    subs = PLUGIN_READ[base]
    return subs is None or (bool(args) and not args[0].expands and args[0].text in subs)


def _write_targets(n: str, args):
    """WRITE_ARGS 명령의 대상 단어 — None 이면 대상을 모른다(표 밖 옵션 · cp · mv 인자 부족)."""
    out, ends = [], False
    for w in args:
        t = w.text
        if not ends and t.startswith("-") and t != "-":
            if t == "--":
                ends = True
            elif not re.fullmatch(f"-[{WRITE_ARGS[n]}]+", t):
                return None
            continue
        out.append(w)
    if n in ("cp", "mv") and len(out) < 2:
        return None
    if n == "mv":
        return out                                 # 원본도 지운다 — 피연산자 전부가 쓰기 대상이다
    if n == "cp":
        rec = any(re.fullmatch(r"-[^-]*[Rra][^-]*", w.text) for w in args if w.text.startswith("-") and w.text != "--")
        return None if rec else out[-1:]           # 재귀 복사는 대상 아래 하위 경로를 만든다 — 그 집합을 모른다
    return out


def defined_functions(toks) -> set:
    """어느 깊이든 이 명령에서 정의한 함수 이름 — 그 호출은 쓰기 자리가 아니다(본문 명령이 따로 판정된다)."""
    out = set()
    for t in toks:
        if isinstance(t, shell_tokens.Func):
            out.add(t.name)
        for sub in shell_tokens.nested(t)[1]:
            out |= defined_functions(sub)
    return out


def write_sites(cmd, fragment=False, known=()):
    """명령의 쓰기 자리 — [(대상 Word | None, Cmd)] · None 이면 못 읽었다(표 밖 꼴 · 토크나이저 없음).
    대상 None = 그 명령이 대상을 모르는 쓰기다(읽기 표 밖 이름 · 명령 자리 미상 · 펼쳐지는 명령 이름 · WRITE_ARGS 의 표 밖 옵션 · xargs 뒤).
    대상 Word 는 리다이렉트(`>` · `>>` · `>|` · `&>` · `<>` · fd 가 아닌 `>&`)와 WRITE_ARGS 명령(tee · rm · touch · mkdir · cp · mv)의 대상이다 —
    펼치지 않은 글자 그대로이고, 그 명령의 깊이 · 지연(함수 본문)은 Cmd 에 있다. 이 명령에서 정의한 함수(와 `known` — 조각만 넘길 때 바깥
    명령이 정의한 함수)의 호출은 자리가 아니다(본문이 따로 나온다).
    ⛔ guard(P4)와 gate_stop_hook(원장 소유)이 같은 판정을 쓴다 — 한쪽만 고치면 두 판정이 갈린다."""
    if not isinstance(cmd, str) or shell_tokens is None:
        return None
    toks = shell_tokens.lex(cmd, fragment)
    cmds = shell_tokens.commands(toks)
    if shell_tokens.is_unknown(cmds):
        return None
    funcs, out = defined_functions(toks) | set(known), []
    for c in cmds:
        out += [(r.target, c) for r in c.redirs if r.op in WRITE_OPS or (r.op == ">&" and not re.fullmatch(r"[0-9]+|-", r.target.text))]
        if c.unsure:
            out.append((None, c))                  # 명령 자리를 모른다(표 밖 래퍼 옵션 · 래퍼 뒤 대입 · 함수 정의 뒤 단어 …)
            continue
        if c.name is None:
            continue
        n = os.path.basename(c.name.text)
        if c.name.text.startswith("((") or _plugin_reads(n, c.name, c.args):
            continue                               # 산술 명령(안의 치환은 토크나이저가 거절한다) · 승인 전 창 플러그인 스크립트
        if c.name.expands:
            out.append((None, c))                  # `$CMD x` — 무엇을 실행하는지 모른다
            continue
        # 함수 조회는 래퍼 없이 경로 없는 이름으로 부를 때만이다 — `command touch` · `env touch` · `/usr/bin/touch` 는 외부 명령을 실행한다
        rule = True if n in funcs and not c.via and "/" not in c.name.text else READ.get(n)
        if rule is True or (rule is not None and rule(c.args)):
            continue
        ws = _write_targets(n, c.args) if n in WRITE_ARGS and "xargs" not in c.via else None
        out += [(None, c)] if ws is None else [(w, c) for w in ws]
    return out


def bash_write(cmd, cwd=None) -> tuple:
    """(쓰는가, 대상 경로 목록). 대상을 모르면 목록이 비어 면제 판정을 하지 않는다.

    ⛔ 계약: 읽기 표(READ · PLUGIN_READ) 밖 이름은 대상 미상 쓰기다 — 쓰기 꼴을 나열해 막지 않는다(차단 목록은 라운드마다 샜다 · F-458).
    쓰기 자리는 write_sites 가 정한다. 대상이 펼쳐지거나(`$X` · 글롭 · 따옴표 든 ~) 치환 · 함수 본문 안이거나, 명령 어딘가에서 폴더를
    옮기면(cd · pushd · popd · `-C`) 상대 대상은 미상이다. Phase 0 의 `mkdir -p {cwd}/{티켓 · NOTASK-날짜}` 는 쓰기로 세지 않는다.
    ⛔ 못 읽으면(표 밖 꼴 · 명령 자리 미상 · 토크나이저 없음) 대상 미상 쓰기다 — P4 창 안에서는 막힌다. 정규식으로 돌아가지 않는다.
    """
    if not isinstance(cmd, str) or not cmd.strip():
        return False, []
    sites = write_sites(cmd)
    if sites is None:
        return True, []                            # 못 읽었다 · 토크나이저가 없다 — 대상 미상 쓰기(정규식으로 돌아가지 않는다)
    moved = any(c.name is not None and os.path.basename(c.name.text) in MOVERS for c in shell_tokens.commands(shell_tokens.lex(cmd))) or any(
        t.startswith(("-C", "--chdir")) for t, _d in shell_tokens.all_words(cmd))   # 붙여 쓴 `-Cmods` 도 옮긴다(`grep -C3` 도 세지만 과차단 쪽이다)
    targets, unknown, by_cmd = [], False, {}
    for w, c in sites:
        by_cmd.setdefault(id(c), (c, []))[1].append(w)
    for c, ws in by_cmd.values():
        redir = [w for w in ws if w is not None and any(w is r.target for r in c.redirs)]
        real = [w for w in ws if (w is None or w.expands or w.text not in QUIET) and not any(w is x for x in redir)]
        if c.name is not None and os.path.basename(c.name.text) == "mkdir" and real and all(
                w is not None and not w.expands and not c.depth and (w.text.startswith("/") or not moved) and workdir_dir(w.text, cwd) for w in real):
            ws = redir                             # Phase 0 WORK_DIR 폴더(F-553) — 면제는 mkdir 피연산자만 · 같은 명령의 리다이렉트는 따로 판정한다
        for w in ws:
            if w is None:
                unknown = True                     # 읽기 표 밖 — 대상 미상 쓰기
                continue
            if w.text in QUIET and not w.expands:
                continue                           # 절대 경로 장치 — 치환 · cd 깊이와 무관하게 쓰기가 아니다(`$(ls x 2>/dev/null)`)
            text = os.path.expanduser(w.text) if w.text.startswith("~/") and not w.quoted else w.text   # 따옴표 없는 앞머리 ~/ 는 셸이 HOME 으로 편다
            if c.depth or c.deferred or w.expands or not text or UNRESOLVED.search(text) or (moved and not text.startswith("/")):
                unknown = True
            else:
                targets.append(text)
    return bool(targets) or unknown, ([] if unknown else targets)


def fz_root(path: str, cwd):
    """경로 위쪽에서 `.claude-plugin/plugin.json` 이름이 fz 인 폴더 — 하위 플러그인(mods/fz-guard)에서 멈추지 않고 끝까지 올라간다."""
    base = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    p = pathlib.Path(os.path.normpath(os.path.join(base, os.path.expanduser(path))))
    for d in p.parents:
        pj = d / ".claude-plugin" / "plugin.json"
        try:
            if pj.is_file() and json.loads(pj.read_text(encoding="utf-8")).get("name") == "fz":
                return d, p
        except (OSError, ValueError, AttributeError):
            continue
    return None, p


def wording_hits(ti: dict, cwd) -> list:
    """F-297 — fz 플러그인 파일에 넣는 줄 중 보존 규칙 밖 옛 모델 호칭. 판별식 · 제외 · 경계 · 보존 행은 그 저장소의
    scripts/check_gpt_surface.py 를 불러 그대로 쓴다(사본을 두면 두 곳이 어긋난다)."""
    text = text_of(ti)
    if not text:
        return []
    hits = []
    for path in paths_of(ti):
        root, p = fz_root(path, cwd)
        if root is None:
            continue
        try:
            spec = importlib.util.spec_from_file_location("fz_gpt_surface", str(root / "scripts" / "check_gpt_surface.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            rel = p.relative_to(root).as_posix()
            if rel.startswith(tuple(mod.EXCLUDE_PREFIX)) or rel in mod.BOUNDARY or not rel.endswith(tuple(mod.SUFFIXES)):
                continue
            keep = set()
            kf = root / "tests" / "fixtures" / "gpt-surface-keep.tsv"
            if kf.is_file():
                keep = {mod.norm(ln.split("\t", 1)[1]) for ln in kf.read_text(encoding="utf-8").split("\n")
                        if "\t" in ln and ln.split("\t", 1)[0] == rel}
            hits += [mod.norm(ln) for ln in text.split("\n") if mod.TOKEN.search(ln) and mod.residual(ln) and mod.norm(ln) not in keep]
        except Exception:                          # noqa: BLE001 — 판별식을 못 부르면 이 규칙만 건너뛴다(fail-open · P4 는 계속 판정)
            continue
    return hits


def turn_of(st: dict, pid) -> dict:
    return st["turns"].setdefault(pid, {"memoryLesson": False, "registryWrite": False, "writes": []})


def prune(sdir: pathlib.Path, sid: str) -> None:
    """F-564 — 상태는 세션마다 생긴다. 마지막 기록(json mtime · 없으면 lock mtime)이 STALE_DAYS 지난 다른 세션의 json · lock 을 지운다.
    ⛔ lock 은 처음 만든 뒤 쓰지 않아 mtime 이 낡는다 — 살아 있는 세션 판정에 lock mtime 을 쓰지 않는다. 플래그 `disable` 은 건드리지 않는다.
    ponytail: 7일 넘게 쉰 세션이 다시 돌며 잡은 잠금을 지울 수 있다 — 그 세션의 다음 사건은 새 잠금 파일을 만든다"""
    cutoff = time.time() - STALE_DAYS * 86400
    stems = sorted({p.stem for p in sdir.iterdir() if p.suffix in (".json", ".lock")} - {sid})
    gone = 0
    for stem in stems:
        if gone >= PRUNE_MAX:
            break
        j, lk = sdir / f"{stem}.json", sdir / f"{stem}.lock"
        try:
            ref = j if j.exists() else lk
            if ref.stat().st_mtime >= cutoff:
                continue
        except OSError:
            continue
        for f in (j, lk):
            with contextlib.suppress(OSError):
                f.unlink()
        gone += 1


def session_mode(transcript) -> str:
    """interactive | headless | unknown — 접두(PREFIX_BYTES · PREFIX_LINES)의 entrypoint 만 본다."""
    try:
        with open(transcript, "rb") as f:
            head = f.read(PREFIX_BYTES)
    except (OSError, TypeError, ValueError):
        return "unknown"
    for line in head.split(b"\n")[:PREFIX_LINES]:
        if b'"entrypoint"' not in line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        ep = row.get("entrypoint") if isinstance(row, dict) else None
        if ep == "cli":
            return "interactive"
        if ep == "sdk-cli":
            return "headless"
        if ep:
            return "unknown"
    return "unknown"


def parse_answers(resp):
    """AskUserQuestion 답 맵(질문 본문 → 라벨). 객체 · 직렬화 문자열 두 꼴 · 알아보지 못하면 None."""
    if isinstance(resp, str):
        try:
            resp = json.loads(resp)
        except ValueError:
            return None
    if isinstance(resp, dict) and isinstance(resp.get("answers"), dict):
        return resp["answers"]
    return None


def disabled_rules(env, sdir: pathlib.Path) -> tuple:
    """(끈 규칙, 진단). ⛔ 끄기는 탈출구다 — 플래그가 있는데 못 읽거나 모르는 값이면 전부 끈다(조용히 켜 두면 사용자가 갇힌다)."""
    raw = env.get("FZ_GUARD_DISABLE", "") or ""
    flag = sdir / "disable"
    try:
        if flag.exists():
            raw += "," + (flag.read_bytes().decode("utf-8").strip() or "all")
    except (OSError, UnicodeDecodeError) as e:
        return set(RULES), f"끄기 플래그 {flag} 를 읽지 못했다({type(e).__name__}) — 전부 끈다"
    tokens = {t.strip().upper() for t in re.split(r"[,\s]+", raw) if t.strip()}
    unknown = sorted(tokens - set(RULES) - {"ALL"})
    if unknown:
        return set(RULES), f"끄기 값 {unknown} 를 모른다(P4 · AG · FR · all) — 전부 끈다"
    return (set(RULES) if "ALL" in tokens else tokens), ""


# ── 상태 ───────────────────────────────────────────────────────────
def state_dir(env) -> pathlib.Path:
    base = env.get("FZ_RUN_STATE") or os.path.join(env.get("HOME") or os.path.expanduser("~"), ".fz", "runs")
    return pathlib.Path(base).expanduser() / "fz-guard"


def inside_plugin(p: pathlib.Path) -> bool:
    try:
        p.resolve().relative_to(PLUGIN_ROOT)
        return True
    except ValueError:
        return False


def protected_roots(env) -> tuple:
    """(보호 경로 목록, 진단) — F-024. 기본 빈 목록 = 무동작. 설정 파일을 못 읽으면 그 파일만 빼고 진단을 낸다(fail-open)."""
    raw = [x for x in (env.get("FZ_GUARD_PROTECTED") or "").split(os.pathsep) if x.strip()]
    why = ""
    try:
        f = state_dir(env) / "protected"
        if f.is_file():
            raw += [ln.strip() for ln in f.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    except (OSError, UnicodeDecodeError, RuntimeError) as e:
        why = f"보호 경로 파일을 읽지 못했다({type(e).__name__})"
    roots = [os.path.normpath(os.path.expanduser(x.strip())) for x in raw]
    return list(dict.fromkeys(q for r in roots for q in (r, os.path.realpath(r)))), why   # 심링크 별칭(/tmp ↔ /private/tmp)도 보호한다


def _under(path: str, roots) -> bool:
    """path 가 보호 경로 아래인가 — 글자 꼴과 심링크를 푼 꼴을 둘 다 대본다(다른 철자로 같은 폴더에 닿는 우회를 막는다)."""
    if not roots:
        return False
    return any(p == r or p.startswith(r.rstrip("/") + "/") for p in {path, os.path.realpath(path)} for r in roots)


def _git_dirs(ws, i) -> list:
    """`git` 전역 옵션의 -C 값(Word) — 하위 명령 앞까지 차례로 · 붙여 쓴 `-C값` 포함. git 은 뒤 -C 를 앞 -C 기준으로 푼다."""
    out, j = [], i + 1
    while j < len(ws) and ws[j].text.startswith("-"):
        t = ws[j].text
        if t == "-C":
            out += ws[j + 1:j + 2]
            j += 2
        elif t.startswith("-C"):
            out.append(ws[j]._replace(text=t[2:]))
            j += 1
        else:
            j += 2 if t in ("-c", "--git-dir", "--work-tree", "--namespace", "--config-env") else 1
    return out


def protected_hit(cmd: str, cwd, roots):
    """보호 경로에 닿는 Bash 의 사유 — None 이면 닿지 않는다. 대상을 모르는 것(못 읽는 명령 · 확장이 든 이동 대상)도 사유다."""
    base = os.path.normpath(cwd) if isinstance(cwd, str) and cwd.startswith("/") else None
    if base and _under(base, roots):
        return f"작업 폴더 {base} 가 보호 경로 아래다"
    toks = shell_tokens.lex(cmd) if shell_tokens is not None else None
    if toks is None or shell_tokens.is_unknown(toks):
        return "명령을 읽지 못했다 — 대상 미상"
    for ws, _rs, _d in shell_tokens.simple_commands(toks):
        names = [os.path.basename(w.text) for w in ws]
        for i, n in enumerate(names):
            for tgt in (ws[i + 1:i + 2] if n in ("cd", "pushd") else _git_dirs(ws, i) if n == "git" else []):
                if tgt.expands or re.search(r"[*?\[{]", tgt.text):
                    return f"이동 대상 {tgt.text} 를 풀 수 없다 — 대상 미상"
    for text, _d in shell_tokens.all_words(cmd):
        for part in {text, text.split("=", 1)[-1]}:
            q = os.path.expanduser(part) if part.startswith("~") else part
            if not q.startswith("/"):
                if not base or not q:
                    continue
                q = os.path.join(base, q)
            if _under(os.path.normpath(q), roots):
                return f"경로 인자 {text} 가 보호 경로 아래다"
    # 앞선 cd · pushd 를 차례로 반영한 작업 폴더로 다시 푼다 — 위 루프는 원래 cwd 기준이라 `cd /srv && git -C live …` 를 놓친다.
    # 서브셸 · 치환 안의 이동도 뒤 명령에 이어 본다(더 묻는 쪽). 이동 대상 `-` 는 셸만 안다 — 대상 미상
    cur = base
    for ws, rs, _d in shell_tokens.simple_commands(toks):
        here = cur
        names = [os.path.basename(w.text) for w in ws]
        for i, n in enumerate(names):
            if n in ("cd", "pushd"):
                args = [w.text for w in ws[i + 1:] if w.text == "-" or not w.text.startswith("-")]
                tgt = args[0] if args else "~"
                if tgt == "-":
                    return "이동 대상 - 를 풀 수 없다 — 대상 미상"
                q = os.path.expanduser(tgt) if tgt.startswith("~") else tgt
                cur = os.path.normpath(q if q.startswith("/") else os.path.join(cur, q)) if (q.startswith("/") or cur) else None
                if cur and _under(cur, roots):
                    return f"이동 뒤 작업 폴더 {cur} 가 보호 경로 아래다"
            elif n == "git":
                g = here
                for d in _git_dirs(ws, i):
                    g = os.path.normpath(os.path.join(g or "/", d.text)) if (d.text.startswith("/") or g) else None
                    if g and _under(g, roots):
                        return f"git -C {d.text} 가 보호 경로 아래다"
        if here and here != base:
            for text in [w.text for w in ws] + [r.target.text for r in rs if r.target is not None]:
                for part in {text, text.split("=", 1)[-1]}:
                    if part and not part.startswith(("/", "~", "-")) and _under(os.path.normpath(os.path.join(here, part)), roots):
                        return f"경로 인자 {text} 가 보호 경로 아래다(앞선 이동 반영)"
    return None


def fresh() -> dict:
    return {"schema": 1, "fzSession": False, "window": None, "prompts": [], "turns": {}, "fingerprints": [], "warned": []}


def load_state(p: pathlib.Path) -> dict:
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return fresh()
    except (OSError, ValueError):
        return fresh()                             # 깨진 상태 = 처음부터(현재 prompt 가 없어 STATE-INCOMPLETE 로 보인다)
    # ⛔ 키 · 형을 본다 — `{"schema": 1}` 처럼 빠진 상태를 그대로 쓰면 사건마다 KeyError 로 저장 전에 실패해 영영 복구되지 않는다
    ok = (isinstance(st, dict) and st.get("schema") == 1 and isinstance(st.get("fzSession"), bool)
          and all(isinstance(st.get(k), list) for k in ("prompts", "fingerprints", "warned"))
          and isinstance(st.get("turns"), dict) and (st.get("window") is None or isinstance(st.get("window"), dict)))
    return st if ok else fresh()


def save_state(p: pathlib.Path, st: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=p.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
        os.replace(tmp, p)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked(sdir: pathlib.Path, sid: str, timeout: float):
    fd = os.open(str(sdir / f"{sid}.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockTimeout()
                time.sleep(0.02)
        yield
    finally:
        os.close(fd)                               # 닫으면 잠금이 풀린다


def trim(st: dict) -> None:
    st["prompts"] = st["prompts"][-KEEP_PROMPTS:]
    for k in list(st["turns"])[:-KEEP_PROMPTS]:
        del st["turns"][k]
    st["fingerprints"] = st["fingerprints"][-4 * KEEP_PROMPTS:]
    st["warned"] = st["warned"][-4 * KEEP_PROMPTS:]


# ── 결정 ───────────────────────────────────────────────────────────
def decision(kind: str, reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind, "permissionDecisionReason": reason}}


def warn_once(st: dict, key: str, text: str):
    if key in st["warned"]:
        return None
    st["warned"].append(key)
    return {"systemMessage": text}


def open_window(st: dict, pid) -> None:
    if pid:
        st["window"] = {"promptId": pid, "approved": False, "unparseable": False}


def p4_pre(inp: dict, env, st: dict, ti: dict, pid, paths=None):
    if autonomous(env):
        return None
    if not pid or pid not in st["prompts"]:        # 이 prompt 의 입력을 못 봤다(설치 전 시작 등) — 창 상태를 모른다
        if session_mode(inp.get("transcript_path")) == "headless":
            return None
        return warn_once(st, f"incomplete:{pid}", f"{WARN_INCOMPLETE} — 이 입력의 시작을 기록하지 못했다(설치 전 시작한 세션 등) · 차단하지 않는다")
    w = st.get("window")
    if not w or w.get("approved") or w.get("promptId") != pid:
        return None                                # ⛔ 창은 연 prompt 범위다 — 승인 없이 접은 /fz 가 다음 요청까지 막지 않는다
    mode = session_mode(inp.get("transcript_path"))
    if mode == "headless":
        return None
    if mode == "unknown":
        return warn_once(st, f"undecided-mode:{pid}", f"{WARN_UNDECIDED} — 실행 모드를 판정하지 못했다(transcript entrypoint 없음) · 차단하지 않는다")
    if w.get("unparseable"):
        return warn_once(st, f"undecided-answer:{pid}", f"{WARN_UNDECIDED} — Phase 4 답을 해석하지 못했다 · 차단하지 않는다")
    paths = paths_of(ti) if paths is None else paths
    if paths and all(exempt(p, env, inp.get("cwd")) for p in paths):
        return None                                # ⛔ 발견 등재(F-518) · Phase 0 WORK_DIR index.md(F-553)는 Phase 0~3 중에도 막지 않는다
    return decision("deny", P4_DENY)


def record_answer(inp: dict, st: dict) -> None:
    w = st.get("window")
    if w:
        w["asked"] = True                          # F-451 — 승인 전 첫 질문(범위 질문 포함)을 냈다 · header 검사보다 먼저 남긴다
    ti = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
    qs = [q for q in ti.get("questions") or [] if isinstance(q, dict) and q.get("header") == PHASE4_HEADER]
    if not w or not qs:
        return                                     # 범위 질문 등 Phase 4 밖 질문은 승인이 아니다
    resp = inp.get("tool_response")
    # 라이브 관측용 — 응답 원본(2KB)과 판정을 창에 남긴다. 실제 모양이 파서와 다르면 verdict 가 unparseable 로 보인다
    raw = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    w["lastResponse"] = {"type": type(resp).__name__, "raw": raw[:2000]}
    answers = parse_answers(resp)
    if answers is None and isinstance(ti.get("answers"), dict):
        answers = ti["answers"]
    if answers is None:
        w["unparseable"] = True
        w["lastResponse"]["verdict"] = "unparseable"
        return
    q = qs[0]
    labels = [o.get("label") for o in q.get("options") or [] if isinstance(o, dict)]
    if answers and q.get("question") not in answers and PHASE4_HEADER not in answers:
        # F-566 — 답은 왔는데 키가 질문 본문 · header 어느 쪽과도 맞지 않는다. 조용히 not-approved 로 떨어뜨리지 않고
        #    해석 불가와 같은 fail-open(경고 후 허용)으로 둔다 — verdict 로 어긋남을 남긴다
        w["unparseable"] = True
        w["lastResponse"]["verdict"] = "mismatch"
        return
    a = answers.get(q.get("question"), answers.get(PHASE4_HEADER))
    w["unparseable"] = False
    w["approved"] = isinstance(a, str) and a in labels and not NOT_APPROVAL.search(a)
    w["lastResponse"]["verdict"] = "approved" if w["approved"] else "not-approved"


def record_write(inp: dict, env, st: dict, ti: dict, pid) -> None:
    if not pid:
        return
    turn = turn_of(st, pid)
    text = LINK_OR_CODE.sub("", text_of(ti))      # F-565 — 링크 · 백틱으로만 든 스킬 이름은 교훈 토큰으로 세지 않는다
    for p in paths_of(ti):
        turn["writes"] = (turn["writes"] + [p])[-200:]
        if MEMORY_PATH.search(p) and (FINDING_ID.search(text) or (FZ_NAME.search(text) and LESSON_CUE.search(text))):
            turn["memoryLesson"] = True
        if registry_entry(p, env):
            turn["registryWrite"] = True


def on_stop(inp: dict, env, st: dict, pid, off: set, sid: str):
    if autonomous(env):
        return None                                # ⛔ 자율 실행은 P4 · FR · GP 모두 막지 않는다
    reasons, warns = [], []
    lam = inp.get("last_assistant_message") if isinstance(inp.get("last_assistant_message"), str) else ""
    w = st.get("window")
    turn = st["turns"].get(pid) or {}
    p4 = "P4" not in off and pid in st["prompts"] and w and w.get("promptId") == pid and not w.get("approved")   # 시작을 못 본 prompt = p4_pre 와 같이 무차단
    fr = "FR" not in off and turn.get("memoryLesson") and not turn.get("registryWrite")
    gp = "GP" not in off and turn.get("review") and not turn.get("gpt") and not GPT_MARK.search(lam)
    long_answer = p4 and not w.get("asked") and len(lam) >= LONG_ANSWER
    mode = session_mode(inp.get("transcript_path")) if (p4 or fr or gp) else ""
    if long_answer and mode != "headless":         # F-451 — 차단(P4)과 별개 축의 경고 · 이어진 Stop(stop_hook_active)에서도 1회 낸다
        m = warn_once(st, f"long-answer:{pid}", f"{WARN_LONG} — Phase 4 승인을 묻기 전에 긴 답({len(lam)}자)으로 턴을 끝냈다(F-451) · 차단하지 않는다")
        if m:
            warns.append(m["systemMessage"])
    if inp.get("stop_hook_active"):
        return {"systemMessage": " · ".join(warns)} if warns else None
    if p4:
        fp = f"{sid}:P4:{pid}"
        if mode == "interactive" and not w.get("unparseable"):
            if fp not in st["fingerprints"]:
                st["fingerprints"].append(fp)
                reasons.append(P4_STOP)
        elif mode == "unknown" or (mode == "interactive" and w.get("unparseable")):
            warns.append(f"{WARN_UNDECIDED} — Phase 4 승인을 판정하지 못했다 · Stop 을 막지 않는다")
    if fr and mode == "interactive":               # ⛔ headless 는 막지 않는다 · 모드 불명은 경고만(판정 불가 = 무차단)
        fp = f"{sid}:FR:{pid}"
        if fp not in st["fingerprints"]:
            st["fingerprints"].append(fp)
            reasons.append(FR_STOP)
    elif fr and mode == "unknown":
        warns.append(f"{WARN_UNDECIDED} — 실행 모드를 판정하지 못했다 · 기록 누락(F-518) Stop 을 막지 않는다")
    if gp and mode == "interactive":               # ⛔ 기존 셋과 같게 interactive 한정 — 자율 run 은 면제다(D-15 트레이드오프)
        fp = f"{sid}:GP:{pid}"
        if fp not in st["fingerprints"]:
            st["fingerprints"].append(fp)
            reasons.append(GP_STOP)
    elif gp and mode == "unknown":
        warns.append(f"{WARN_UNDECIDED} — 실행 모드를 판정하지 못했다 · GPT 리뷰 누락(F-094) Stop 을 막지 않는다")
    out = {}
    if reasons:
        out = {"decision": "block", "reason": " ".join(reasons)}
    if warns:
        out["systemMessage"] = " · ".join(warns)
    return out or None


def handle(inp: dict, env, st: dict, off: set, sid: str):
    ev, pid = inp.get("hook_event_name"), inp.get("prompt_id")
    name = inp.get("tool_name") if isinstance(inp.get("tool_name"), str) else ""
    ti = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
    if ev == "UserPromptSubmit":
        tok = first_token(inp.get("prompt"))
        if pid and pid not in st["prompts"]:
            st["prompts"].append(pid)
        if tok.startswith("/") and fz_marker(tok):
            st["fzSession"] = True
        if opens_window(tok):
            open_window(st, pid)
        if tok.lstrip("/") in REVIEW_SKILLS and pid:
            turn_of(st, pid)["review"] = True     # F-094 — 이 턴은 fz-review 다
        return None
    if ev == "PreToolUse":
        if name == "Skill":
            skill = ti.get("skill") if isinstance(ti.get("skill"), str) else ""
            if fz_marker(skill):
                st["fzSession"] = True
            if skill in ("fz", "fz:fz"):
                open_window(st, pid)
            if skill in REVIEW_SKILLS and pid:
                turn_of(st, pid)["review"] = True
            return None
        if name == "Bash":
            cmd = ti.get("command") if isinstance(ti.get("command"), str) else ""
            if gpt_review_invoked(cmd) and pid:
                turn_of(st, pid)["gpt"] = True     # F-094 — GPT 리뷰를 불렀다(출력은 Bash 라 PostToolUse 로 못 본다)
            writes, targets = bash_write(cmd, inp.get("cwd"))
            if writes and "P4" not in off:
                return p4_pre(inp, env, st, ti, pid, paths=targets)
            return None
        if write_tool(name) and "GP" not in off:
            hits = wording_hits(ti, inp.get("cwd"))
            if hits:
                return decision("deny", GP_DENY + " | ".join(h[:120] for h in hits[:3]))
        if name in AGENT_TOOLS:
            if "AG" in off or not st["fzSession"]:
                return None
            kind = ti.get("subagent_type") if isinstance(ti.get("subagent_type"), str) and ti.get("subagent_type") else "general-purpose"
            if kind.split(":")[-1] in ALLOW_AGENTS or autonomous(env):
                return None
            mode = session_mode(inp.get("transcript_path"))
            if mode == "headless":
                return None                        # ⛔ -p 에는 답할 사람이 없다 — ask 는 사실상 거부다(공식 훅 문서)
            if mode == "unknown":
                return warn_once(st, f"undecided-agent:{pid}", f"{WARN_UNDECIDED} — 실행 모드를 판정하지 못했다 · 에이전트({kind}) 확인을 묻지 않는다")
            return decision("ask", f"fz-guard AG(F-058 · F-119): fz 세션에서 허용 목록 밖 에이전트({kind})를 띄운다. "
                                   "fz 위임은 Workflow 경유가 규칙이다(native 4종만 예외). 그대로 띄울지 확인한다")
        if p4_tool(name) and "P4" not in off:
            return p4_pre(inp, env, st, ti, pid)
        return None
    if ev == "PostToolUse":
        if name == "AskUserQuestion":
            record_answer(inp, st)
        elif name == "Read":                      # run() 이 fz-review SKILL.md 만 들여보낸다
            if pid and (st.get("window") or {}).get("promptId") == pid:
                turn_of(st, pid)["review"] = True  # F-094 — /fz 창 안에서 SKILL.md 를 읽어 도는 fz-review
        elif write_tool(name):
            record_write(inp, env, st, ti, pid)
        return None
    if ev == "Stop":
        return on_stop(inp, env, st, pid, off, sid)
    return None


def run(stdin_text: str, env) -> tuple:
    """훅 한 번 — (stdout, stderr). ⛔ 어떤 오류도 결정으로 새지 않는다(fail-open)."""
    try:
        inp = json.loads(stdin_text)
    except ValueError:
        return "", "fz-guard diag: 입력이 JSON 이 아니다 — 통과(fail-open)"
    if not isinstance(inp, dict):
        return "", "fz-guard diag: 입력이 JSON 객체가 아니다 — 통과(fail-open)"
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", str(inp.get("session_id") or ""))[:128]
    if not sid:
        return "", "fz-guard diag: session_id 가 없다 — 통과(fail-open)"
    pp, diag = None, ""
    if inp.get("hook_event_name") == "PostToolUse" and inp.get("tool_name") == "Read":
        ti = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
        if not (isinstance(ti.get("file_path"), str) and REVIEW_SKILL_FILE.search(ti["file_path"])):
            return "", ""                          # ⛔ 다른 Read 는 상태를 열지 않는다 — 모든 Read 에 훅이 붙는다
    if inp.get("hook_event_name") == "PreToolUse" and inp.get("tool_name") == "Bash":
        ti = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
        cmd = ti.get("command")
        try:                                       # F-024 보호 경로 — 상태 파일 없이 판정한다(설정이 비면 아무 일도 없다)
            roots, diag = protected_roots(env)
            if roots and isinstance(cmd, str) and not disabled_rules(env, state_dir(env))[0] >= set(RULES):
                hit = protected_hit(cmd, inp.get("cwd"), roots)
                pp = decision("ask", PP_ASK + hit) if hit else None
        except Exception as e:                     # noqa: BLE001 — 훅은 세션을 막지 않는다
            diag = f"보호 경로 판정 오류 {type(e).__name__}"
        diag = f"fz-guard diag: {diag} — 통과(fail-open)" if diag else ""
        if not isinstance(cmd, str) or not (bash_write(cmd, inp.get("cwd"))[0] or gpt_review_invoked(cmd)):
            return (json.dumps(pp, ensure_ascii=False) if pp else ""), diag   # ⛔ 읽는 Bash 는 상태를 열지 않는다 — 모든 세션의 모든 Bash 에 잠금 · 저장이 붙지 않게
    try:
        timeout = float(env.get("FZ_GUARD_LOCK_TIMEOUT") or LOCK_TIMEOUT)
    except ValueError:
        timeout = LOCK_TIMEOUT
    try:                                           # ⛔ 상태 폴더 해석 · 끄기 판정도 안쪽 — `~없는사용자/x` 도 exit 0 + 진단
        sdir = state_dir(env)
        if inside_plugin(sdir):
            return "", f"fz-guard diag: 상태 폴더가 플러그인 안이다({sdir}) — 쓰지 않고 통과(fail-open)"
        off, why = disabled_rules(env, sdir)
        if off >= set(RULES):
            return "", (f"fz-guard diag: {why}" if why else "")
        sdir.mkdir(parents=True, exist_ok=True)
        with locked(sdir, sid, timeout):
            if inp.get("hook_event_name") == "UserPromptSubmit":
                prune(sdir, sid)                   # F-564 — 입력마다 한 번(도구 사건마다 돌리지 않는다)
            path = sdir / f"{sid}.json"
            st = load_state(path)
            out = handle(inp, env, st, off, sid)
            trim(st)
            save_state(path, st)
    except LockTimeout:
        return "", f"fz-guard diag: 상태 잠금을 {timeout}s 안에 잡지 못했다 — 통과(fail-open)"
    except OSError as e:
        return "", f"fz-guard diag: 상태를 읽거나 쓰지 못했다({type(e).__name__}) — 통과(fail-open)"
    except Exception as e:                         # noqa: BLE001 — 훅은 세션을 막지 않는다
        return "", f"fz-guard diag: 내부 오류 {type(e).__name__} — 통과(fail-open)"
    if pp and ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecision") != "deny":
        out = {**(out or {}), **pp}               # 보호 경로 ask 는 P4 deny 를 덮지 않는다
    return (json.dumps(out, ensure_ascii=False) if out else ""), ""


# ── 보조 모드 ──────────────────────────────────────────────────────
def allowlist_from(md: str) -> list:
    """채택 표(헤더에 '스폰 방식')의 **굵은** 이름만 — 같은 문서의 불채택 표는 읽지 않는다."""
    names, inside = [], False
    for line in md.splitlines():
        if not inside:
            inside = line.startswith("|") and "스폰 방식" in line
            continue
        if not line.startswith("|"):
            break
        m = re.match(r"^\|\s*\*\*([^*|]+)\*\*\s*\|", line)
        if m:
            names.append(m.group(1).strip())
    return names


def check_allowlist(path: str) -> int:
    try:
        names = allowlist_from(pathlib.Path(path).read_text(encoding="utf-8"))
    except OSError as e:
        print(f"UNRUN: 표를 읽지 못했다 — {e}")
        return 2
    if not names:
        print("UNRUN: 채택 표('스폰 방식' 헤더)를 찾지 못했다")
        return 2
    if set(names) != ALLOW_AGENTS:
        print(f"MISMATCH: 표만 {sorted(set(names) - ALLOW_AGENTS)} · guard 만 {sorted(ALLOW_AGENTS - set(names))}")
        return 1
    print(f"ALLOWLIST OK — {len(names)}종")
    return 0


def make_synthetic(size: int, out: str, marker: bool) -> None:
    head = [{"type": "permission-mode", "permissionMode": "default", "sessionId": "synthetic"},
            dict({"type": "attachment", "sessionId": "synthetic", "cwd": "/srv/demo"}, **({"entrypoint": "cli"} if marker else {}))]
    data = "".join(json.dumps(r) + "\n" for r in head).encode()
    filler = (json.dumps({"type": "assistant", "message": {"content": "x" * 4000}}) + "\n").encode()
    chunk = filler * ((8 << 20) // len(filler))
    with open(out, "wb") as f:
        f.write(data[:size])
        left = size - min(size, len(data))
        while left > 0:
            piece = chunk[:left]
            f.write(piece)
            left -= len(piece)
    print(f"made bytes={size} marker={'yes' if marker else 'no'}")


def bench(path: str) -> None:
    t = time.perf_counter()
    mode = session_mode(path)
    print(f"mode={mode} elapsed_ms={int((time.perf_counter() - t) * 1000)}")


# ── self-test ──────────────────────────────────────────────────────
def self_test() -> int:
    """합성 입력만 쓴다. ⛔ 환경을 상속하지 않는다 — HOME · FZ_RUN_STATE 를 임시 폴더로 새로 짓는다(실제 상태 오염 · 셸 변수 누수 차단)."""
    results = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="fz-guard-test-"))
    fx = PLUGIN_ROOT / "tests" / "fixtures"
    t_cli, t_sdk, t_none = fx / "transcript-cli.jsonl", fx / "transcript-sdk-cli.jsonl", fx / "transcript-no-entrypoint.jsonl"
    mem = "/home/u/.claude/projects/-srv-demo/memory/feedback_lesson.md"
    reg = "/srv/data/fz-findings/entries/F-601-sample.md"

    def case(name, ok, got=""):
        results.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    def env_for(tag, **extra):
        e = {"HOME": str(tmp / tag / "home"), "FZ_RUN_STATE": str(tmp / tag / "runs"), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        e.update(extra)
        return e

    class S:
        def __init__(self, tag, sid="s1", transcript=t_cli, **extra):
            self.env, self.sid, self.tr, self.pid, self.err = env_for(tag, **extra), sid, str(transcript), None, ""

        def send(self, ev, **kw):
            inp = {"session_id": self.sid, "transcript_path": self.tr, "cwd": "/srv/demo", "hook_event_name": ev, **kw}
            if self.pid:
                inp.setdefault("prompt_id", self.pid)
            out, self.err = run(json.dumps(inp), self.env)
            return json.loads(out) if out else None

        def prompt(self, text, pid):
            self.pid = pid
            return self.send("UserPromptSubmit", prompt=text)

        def pre(self, tool, ti=None):
            return self.send("PreToolUse", tool_name=tool, tool_input=ti or {}, tool_use_id="t")

        def post(self, tool, ti=None, resp=None):
            return self.send("PostToolUse", tool_name=tool, tool_input=ti or {}, tool_response=resp if resp is not None else {}, tool_use_id="t")

        def stop(self, active=False, msg=None):
            return self.send("Stop", stop_hook_active=active, **({"last_assistant_message": msg} if msg is not None else {}))

    def kind(o):
        return ((o or {}).get("hookSpecificOutput") or {}).get("permissionDecision")

    def warned(o, tag):
        return tag in ((o or {}).get("systemMessage") or "")

    def blocked(o):
        return (o or {}).get("decision") == "block"

    W = {"file_path": "/srv/demo/a.swift", "content": "x"}

    def last_response(s):
        st = load_state(pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard" / f"{s.sid}.json")
        return (st.get("window") or {}).get("lastResponse") or {}
    Q = "파이프라인을 승인할까?"

    def p4q(header=PHASE4_HEADER, extra=()):
        opts = [{"label": "full (Recommended)", "description": "d"}, {"label": "light", "description": "d"},
                {"label": "커스텀 구성", "description": "d"}] + [{"label": x, "description": "d"} for x in extra]
        return {"questions": [{"question": Q, "header": header, "multiSelect": False, "options": opts}]}

    def answered(s, label, header=PHASE4_HEADER, extra=(), as_text=False):
        ti = p4q(header, extra)
        resp = {"questions": ti["questions"], "answers": {Q: label} if label is not None else {}}
        return s.post("AskUserQuestion", ti, json.dumps(resp, ensure_ascii=False) if as_text else resp)

    def fz(tag, **kw):
        s = S(tag, **kw)
        s.prompt("/fz 계획 세워줘", "p1")
        return s

    cells = []
    cell = cells.append

    @cell
    def c1():
        s = fz("c1")
        o = s.pre("Write", W)
        w = S("c1w")
        w.prompt("<command-name>/fz:fz</command-name>\n<command-args>x</command-args>", "p1")
        case("p4-write-before-approval-denied", kind(o) == "deny" and "Phase 4" in o["hookSpecificOutput"]["permissionDecisionReason"]
             and kind(w.pre("Edit", W)) == "deny", o)

    @cell
    def c2():
        case("p4-serena-write-before-approval-denied", kind(fz("c2").pre("mcp__plugin_fz_serena__replace_symbol_body", {"relative_path": "a.swift"})) == "deny")

    @cell
    def c3():
        case("p4-xcode-write-before-approval-denied", kind(fz("c3").pre("mcp__xcode__XcodeWrite", {"filePath": "/srv/demo/a.swift"})) == "deny")

    @cell
    def c4():
        case("p4-workflow-before-approval-denied", kind(fz("c4").pre("Workflow", {"scriptPath": "/srv/w.js"})) == "deny")

    @cell
    def c5():
        s = S("c5")
        s.prompt("계획부터 해줘", "p1")
        before = s.pre("Write", W)
        s.pre("Skill", {"skill": "fz:fz"})
        case("p4-skill-fz-opens-window", before is None and kind(s.pre("Write", W)) == "deny", before)

    @cell
    def c6():
        s = fz("c6")
        answered(s, "full (Recommended)")
        lr = last_response(s)
        case("p4-after-phase4-approved-allowed", s.pre("Write", W) is None and lr.get("verdict") == "approved" and "answers" in lr.get("raw", ""), lr)

    @cell
    def c7():
        s = fz("c7")
        answered(s, "full (Recommended)", header="범위")
        case("p4-scope-question-not-approval", kind(s.pre("Write", W)) == "deny")

    @cell
    def c8():
        s = fz("c8")
        answered(s, "커스텀 구성")
        case("p4-custom-config-answer-not-approval", kind(s.pre("Write", W)) == "deny")

    @cell
    def c9():
        s = fz("c9")
        answered(s, "그냥 알아서 해줘")
        case("p4-free-text-answer-not-approval", kind(s.pre("Write", W)) == "deny")

    @cell
    def c10():
        s = fz("c10")
        answered(s, None)
        o = s.pre("Write", W)
        case("p4-rejected-question-not-approval", kind(o) == "deny" and not warned(o, WARN_UNDECIDED), o)

    @cell
    def c11():
        s = fz("c11")
        answered(s, "중단", extra=("중단",))
        case("p4-cancel-answer-not-approval", kind(s.pre("Write", W)) == "deny")

    @cell
    def c12():
        s = fz("c12")
        answered(s, "full (Recommended)")
        s.prompt("/fz 다른 일", "p2")
        case("p4-prior-approval-not-reused", kind(s.pre("Write", W)) == "deny")

    @cell
    def c13():
        s = fz("c13", FZ_AUTONOMY="autonomous")
        case("p4-autonomous-allowed", s.pre("Write", W) is None and s.stop() is None)

    @cell
    def c14():
        s = fz("c14", transcript=t_sdk)
        case("p4-headless-entrypoint-allowed", s.pre("Write", W) is None and s.stop() is None)

    @cell
    def c15():
        o = fz("c15", transcript=t_none).pre("Write", W)
        case("p4-mode-unknown-warns", kind(o) is None and warned(o, WARN_UNDECIDED), o)

    @cell
    def c16():
        o = fz("c16", transcript=t_none).stop()
        case("p4-mode-unknown-stop-not-blocked", not blocked(o) and warned(o, WARN_UNDECIDED), o)

    @cell
    def c17():
        s = S("c17")
        s.prompt("버그 고쳐줘", "p1")
        case("p4-no-fz-window-allowed", s.pre("Write", W) is None and s.stop() is None)

    @cell
    def c18():
        s = fz("c18")
        case("p4-finding-write-allowed", s.pre("Write", {"file_path": reg, "content": "x"}) is None and kind(s.pre("Write", W)) == "deny")

    def B(cmd):
        return {"command": cmd, "description": "d"}

    @cell
    def f119a():
        s = fz("f119a")
        got = [kind(s.pre("Bash", B(c))) for c in ("echo x > a.swift", "printf y >> /srv/demo/b.swift", 'make 2>&1 >"$T/o0"', "cmd &> out.log")]
        case("f119-bash-redirect-denied", got == ["deny"] * 4, got)

    @cell
    def f119b():
        s = fz("f119b")
        got = [kind(s.pre("Bash", B(c))) for c in ("sed -i '' 's/a/b/' a.swift", "sed -i.bak -e 's/x/y/' f.md",
                                                     "find . -name '*.md' | xargs sed -i 's/a/b/'")]
        case("f119-bash-sed-i-denied", got == ["deny"] * 3, got)

    @cell
    def f119c():
        s = fz("f119c")
        got = [kind(s.pre("Bash", B(c))) for c in ("echo x | tee a.swift", "echo x | tee -a /srv/demo/log.txt")]
        case("f119-bash-tee-denied", got == ["deny"] * 2, got)

    @cell
    def f119d():
        s = fz("f119d")
        got = [kind(s.pre("Bash", B(c))) for c in ("cat > a.swift <<'EOF'\nlet x = 1\nEOF",
                                                     "python3 - <<'EOF'\nopen('a.swift', 'w').write('x')\nEOF",
                                                     "node <<EOF\nrequire('fs').writeFileSync('a', 'x')\nEOF")]
        case("f119-bash-heredoc-denied", got == ["deny"] * 3, got)

    @cell
    def f119e():
        hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        rx = [re.compile(h["matcher"]) for h in hooks.get("PreToolUse", []) if h.get("matcher")]
        hit = lambda name: any(r.search(name) for r in rx)
        case("f119-hook-routes-bash", bool(rx) and hit("Bash") and hit("Write") and not hit("Read") and not hit("BashOutput"),
             [r.pattern for r in rx])

    @cell
    def f368():
        s = fz("f368")
        reads = ["cat a.swift", 'grep -n "a > b" a.swift 2>/dev/null', "ls -la > /dev/null 2>&1", "git status 2>&1 | head -5",
                 "cat <<'EOF'\nprint(1 > 0)\nEOF", "sed -n 1,5p a.swift", "echo x | tee /dev/null", "jq '.a > 1' f.json",
                 "awk -F'\\t' '$1>3' f.tsv", "git log --format=x 2>&1 | grep -v '=>'"]
        got = [s.pre("Bash", B(c)) for c in reads]
        answered(s, "full (Recommended)")
        after = s.pre("Bash", B("echo x > a.swift"))
        case("f368-bash-read-allowed", got == [None] * len(reads) and after is None, f"{got} · 승인 뒤 {after}")

    @cell
    def f119f():
        s = fz("f119f")
        reads = ['[[ "$a" > "$b" ]] && echo y', "(( count > 0 )) && echo ok", "echo $(( 3 > 2 ))", "[ a \\> b ] && echo y",
                 '[[\n  "$a" > "$b"\n]] && echo y']                          # 여러 줄 비교식
        got = [s.pre("Bash", B(c)) for c in reads]
        real = kind(s.pre("Bash", B("[ $a > $b ] && echo y")))
        # 실제로 쓰는 꼴 — 비교식 안 치환 · 치환 안 서브셸 · 큰따옴표 안 치환 · 역슬래시 짝 뒤 `>`(bash 는 리다이렉트로 본다)
        writes = ["[[ $(printf x > /tmp/p4-example.txt) == x ]]", "[[ $( (printf x) > /tmp/p4-example.txt) == x ]]",
                  '[[ "$(printf x > /tmp/p4-example.txt)" == x ]]', "printf x \\\\> /tmp/p4-example.txt"]
        inner = [kind(s.pre("Bash", B(c))) for c in writes]
        inner = "deny" if inner == ["deny"] * len(writes) else inner
        case("f119-bash-test-comparison-allowed", got == [None] * len(reads) and real == "deny" and inner == "deny",
             f"{got} · 홑대괄호 {real} · 치환 안 쓰기 {inner}")

    @cell
    def f553a():
        s = fz("f553a")
        got = [s.pre("Write", {"file_path": "/srv/demo/TKT-1234/index.md", "content": "x"}),
               s.pre("Write", {"file_path": "/srv/demo/NOTASK-20261109/index.md", "content": "x"}),
               s.pre("Bash", B("mkdir -p /srv/demo/TKT-1234 && cat > /srv/demo/TKT-1234/index.md <<'EOF'\n# x\nEOF"))]
        case("f553-phase0-workdir-allowed", got == [None] * 3, got)

    @cell
    def f553b():
        s = fz("f553b")
        got = [kind(s.pre("Write", {"file_path": p, "content": "x"})) for p in (
            "/srv/demo/TKT-1234/plan.md", "/srv/demo/src/index.md", "/srv/other/TKT-1234/index.md",
            "/srv/demo/TKT-1234/../a.swift", "/srv/demo/x/TKT-1234/index.md")]
        case("f553-outside-workdir-still-denied", got == ["deny"] * 5, got)

    @cell
    def f564():
        s = S("f564")
        sdir = pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard"
        sdir.mkdir(parents=True)
        old = time.time() - 30 * 86400

        def put(name, age=old):
            p = sdir / name
            p.write_text("{}" if name.endswith(".json") else "", encoding="utf-8")
            os.utime(p, (age, age))
        for i in range(12):
            put(f"old{i}.json")
            put(f"old{i}.lock")
        put("orphan.lock")
        put("live.json", time.time())             # 최근 상태 + 오래 전에 만든 잠금 = 살아 있는 세션
        put("live.lock")
        put("disable")
        (sdir / "disable").write_text("AG\n", encoding="utf-8")
        s.prompt("평범한 요청", "p1")
        left = sorted(p.name for p in sdir.iterdir() if p.name.startswith(("old", "orphan")))
        alive = [n for n in ("live.json", "live.lock", "disable", "s1.json", "s1.lock") if not (sdir / n).exists()]
        case("f564-stale-state-pruned", len(left) < 1 and not alive, f"남은 낡은 것 {left} · 지워진 살아 있는 것 {alive}")

    @cell
    def f565a():
        s = S("f565a")
        s.prompt("메모리 정리", "p1")
        s.post("Write", {"file_path": str(pathlib.Path(mem).with_name("MEMORY.md")),
                         "content": "- [fz-code 사용 메모](feedback_fz_code.md) — `fz-code` 링크\n- [fz-findings 경로](reference_x.md)\n"})
        case("f565-skill-link-only-not-lesson", s.stop() is None)

    @cell
    def f565b():
        s = S("f565b")
        s.prompt("회고", "p1")
        s.post("Write", {"file_path": mem, "content": "fz-peer-review 교훈 — 분석만 요청받았다는 예외로 등재를 미뤘다"})
        o = s.stop()
        case("f565-f518-still-caught", blocked(o) and "F-518" in o.get("reason", ""), o)

    @cell
    def r3_f565_topic():
        s = S("r3f565")
        s.prompt("메모리 정리", "p1")
        s.post("Write", {"file_path": mem, "content": "커밋 · PR 은 fz-commit · fz-pr 대신 팀 gc · pr 스킬을 쓴다\n"
                                                     "레지스트리는 ~/dev/gone/fz-findings 아래에 있다\n"})
        case("r3-f565-skill-name-only-topic-passes", s.stop() is None)

    @cell
    def f451():
        long = "분석 결과를 정리한다. " * 200
        a = fz("f451a")
        oa = a.stop(msg=long)
        again = a.stop(active=True, msg=long)
        b = fz("f451b")
        answered(b, "full (Recommended)", header="범위")
        ob = b.stop(msg=long)
        c = fz("f451c")
        oc = c.stop(msg="짧은 답")
        u = fz("f451u", transcript=t_none)
        ou = u.stop(msg=long)
        case("f451-long-answer-before-approval-warn", blocked(oa) and warned(oa, WARN_LONG) and again is None and blocked(ob)
             and not warned(ob, WARN_LONG) and blocked(oc) and not warned(oc, WARN_LONG) and not blocked(ou) and warned(ou, WARN_LONG),
             f"{oa} · {again} · {ob} · {oc} · {ou}")

    @cell
    def f094():
        a = S("f094a")
        a.prompt("/fz-review 내 코드", "p1")
        first, second = a.stop(msg="리뷰 끝"), a.stop(msg="리뷰 끝")
        b = S("f094b")
        b.prompt("/fz:fz-review", "p1")
        b.pre("Bash", B('"$R/scripts/gpt-call.sh" review --cd /srv/demo --out x.md'))
        c = S("f094c")
        c.prompt("리뷰해줘", "p1")
        c.pre("Skill", {"skill": "fz:fz-review"})
        h = S("f094h", transcript=t_sdk)
        h.prompt("/fz-review", "p1")
        n = S("f094n")
        n.prompt("평범한 요청", "p1")
        rest = [b.stop(msg="리뷰 끝"), c.stop(msg="[GPT 미사용 — CLI 없음] 나머지는 통과"), h.stop(msg="리뷰 끝"), n.stop(msg="끝")]
        case("f094-review-without-gpt-blocked", blocked(first) and "F-094" in first.get("reason", "") and second is None
             and rest == [None] * 4, f"{first} · {second} · {rest}")

    @cell
    def f094m():
        calls = ['"${FZ_PLUGIN_ROOT}/scripts/gpt-call.sh" review --cd /srv/demo --out x.md --uncommitted',
                 "cd /srv/demo && FZ_X=1 bash scripts/gpt-call.sh independent-review --diff d.patch > o 2>&1; echo exit=$?",
                 "bash -e scripts/gpt-call.sh review --cd x", "FZ_X=$(pwd) bash scripts/gpt-call.sh review --cd x"]
        mentions = ["grep -n 'gpt-call.sh review' modules/fz-gpt-subcommands-core.md", 'echo "gpt-call.sh review"',
                    "cat > p.md <<'EOF'\n\"$R/gpt-call.sh\" review --cd x\nEOF", 'rg "gpt-call\\.sh review" modules',
                    "printf '%s\\n' ';' gpt-call.sh review",   # 따옴표 안 `;` 는 연산자가 아니다
                    "printf '%s\\n' $(printf x) gpt-call.sh review", "echo ! gpt-call.sh review"]   # 치환 뒤 · 인자 `!` 뒤는 인자 자리
        got = [gpt_review_invoked(c) for c in calls + mentions]
        s = S("f094m")
        s.prompt("/fz-review 내 코드", "p1")
        s.pre("Bash", B(mentions[0] + " > o.txt"))      # 쓰기라 상태 거름망을 지나 기록 줄까지 간다 — 그 줄의 판별을 잰다
        out = s.stop(msg="리뷰 끝")
        case("f094-gpt-mention-not-call — 명령 자리의 실행만 GPT 호출로 센다(grep · echo · heredoc · rg 언급은 아니다)",
             got == [True] * len(calls) + [False] * len(mentions) and blocked(out), f"{got} · {out}")

    # 수정 전 트리(002df3b)의 옛 근사기 판정을 동결한 표 — 쓰기 · 미상이던 꼴과 GPT 호출이 아니던 꼴(fail-open 회귀만 잰다)
    parity_writes = ["echo x > a.swift", "printf y >> /srv/demo/b.swift", 'make 2>&1 >"$T/o0"', "cmd &> out.log",
                     "sed -i '' 's/a/b/' a.swift", "sed -i.bak -e 's/x/y/' f.md", "find . -name '*.md' | xargs sed -i 's/a/b/'",
                     "echo x | tee a.swift", "echo x | tee -a /srv/demo/log.txt", "cat > a.swift <<'EOF'\nlet x = 1\nEOF",
                     "python3 - <<'EOF'\nopen('a.swift', 'w').write('x')\nEOF", "node <<EOF\nrequire('fs').writeFileSync('a', 'x')\nEOF",
                     "[ $a > $b ] && echo y", "[[ $(printf x > /tmp/p4-example.txt) == x ]]", "[[ $( (printf x) > /tmp/p4-example.txt) == x ]]",
                     '[[ "$(printf x > /tmp/p4-example.txt)" == x ]]', "printf x \\\\> /tmp/p4-example.txt",
                     "mkdir -p /srv/demo/TKT-1234 && cat > /srv/demo/TKT-1234/index.md <<'EOF'\n# x\nEOF",
                     "grep -n 'gpt-call.sh review' modules/fz-gpt-subcommands-core.md > o.txt"]
    parity_nocall = ["grep -n 'gpt-call.sh review' modules/fz-gpt-subcommands-core.md", 'echo "gpt-call.sh review"',
                     "cat > p.md <<'EOF'\n\"$R/gpt-call.sh\" review --cd x\nEOF", 'rg "gpt-call\\.sh review" modules',
                     "printf '%s\\n' ';' gpt-call.sh review", "printf '%s\\n' $(printf x) gpt-call.sh review", "echo ! gpt-call.sh review"]

    @cell
    def r3_import():
        dst = tmp / "r3-standalone" / "fz-guard"
        shutil.copytree(PLUGIN_ROOT, dst, ignore=shutil.ignore_patterns("__pycache__"))
        probe = ("import importlib.util, sys; sp = importlib.util.spec_from_file_location('g', sys.argv[1]); "
                 "m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); "
                 "print(m.shell_tokens is not None and m.shell_tokens.__file__); print(m.bash_write('printf x \\\\>> f'))")
        a = subprocess.run([sys.executable, "-I", "-c", probe, str(dst / "hooks" / "guard.py")], capture_output=True, text=True,
                           cwd=str(dst), timeout=60)
        b = subprocess.run([sys.executable, "-I", str(dst / "hooks" / "shell_tokens.py"), "--self-test"], capture_output=True,
                           text=True, cwd=str(dst), timeout=60)
        got = a.stdout.splitlines()
        case("r3-guard-standalone-import — guard 폴더만 복사한 설치본이 -I 로 돌아도 자기 폴더의 토크나이저를 쓰고 그 self-test 가 돈다",
             a.returncode == 0 and got == [str(dst / "hooks" / "shell_tokens.py"), "(True, [])"] and b.returncode == 0,
             f"{got} {a.stderr[-300:]} · 토크나이저 self-test exit {b.returncode} {b.stdout[-200:]}")

    @cell
    def r3_escaped():
        s = fz("r3esc")
        forms = ["printf x \\>> /tmp/fz-out", "printf x \\>>> /tmp/fz-out", '[[ "$(printf "x" > /tmp/fz-out)" == x ]]']
        got = [bash_write(c) for c in forms]
        den = [kind(s.pre("Bash", B(c))) for c in forms]
        case("r3-f119-escaped-redirect-unknown — 이스케이프된 > 에 붙은 연산자 · 중첩 따옴표 치환 안 쓰기는 쓰기 대상 미상이다(ISSUE-202619 · 202623)",
             got == [(True, [])] * 3 and den == ["deny"] * 3, f"{got} · {den}")

    @cell
    def r3_targets():
        forms = ("cp a.swift b.swift", "mv -f x /srv/demo/y.md", "rm -f a.txt b.txt", "touch c.md", "git apply p.patch",
                 "cp -t /srv/demo a b", 'cp a "$D/b"')
        got = [bash_write(c) for c in forms + ("command -v cp", "sudo -k cp a b", "A+=x tee target", "A[0]=x tee target")]
        # mv 는 원본도 지운다 — 두 피연산자 모두 대상이다(r6 ISSUE-004)
        want = [(True, ["b.swift"]), (True, ["x", "/srv/demo/y.md"]), (True, ["a.txt", "b.txt"]), (True, ["c.md"]), (True, []), (True, []), (True, []),
                (False, []), (True, []), (True, ["target"]), (True, ["target"])]   # 조회(command -v)는 쓰기가 아니다 · 표 밖 래퍼 옵션은 대상 미상 · += · [i]= 는 대입(3차 ISSUE-004)
        s = fz("r3tg")
        exempt_ = s.pre("Bash", B(f"cp /tmp/x.md {reg}"))
        other = kind(s.pre("Bash", B("cp /tmp/x.md /srv/demo/a.swift")))
        case("r3-f119-cp-mv-touch-targets — cp · mv · rm · touch · git apply 의 대상을 뽑는다(레지스트리 대상은 면제 · 그 밖은 막힌다)",
             got == want and exempt_ is None and other == "deny", f"{got} · {exempt_} · {other}")

    @cell
    def r3_brace():
        got = [gpt_review_invoked(c) for c in ("echo { } gpt-call.sh review", "echo } gpt-call.sh review",
                                               "{ bash scripts/gpt-call.sh review --cd x; }",
                                               # r3 적대 검토 반례 — 명령 이름 2 · 조회 · 구문 검사 · 따옴표 든 NAME= 는 실행이 아니다
                                               "2&>/dev/null ./scripts/gpt-call.sh review", "command -v ./scripts/gpt-call.sh review",
                                               "bash -n scripts/gpt-call.sh review", "'X=1' ./scripts/gpt-call.sh review",
                                               # r3 3차 ISSUE-005 — 래퍼 뒤 대입 · 예약어는 실행 파일 이름이다
                                               "command A=1 gpt-call.sh review", "env if gpt-call.sh review")]
        s = S("r3br")
        s.prompt("/fz-review 내 코드", "p1")
        s.pre("Bash", B("echo { } gpt-call.sh review > o.txt"))
        out = s.stop(msg="리뷰 끝")
        case("r3-f094-echo-brace-not-call — 인자 자리의 중괄호는 명령 경계가 아니다(ISSUE-202616) · 명령 자리의 { … } 안 호출은 센다",
             got == [False, False, True, False, False, False, False, False, False] and blocked(out), f"{got} · {out}")

    @cell
    def r3_envu():
        got = [gpt_review_invoked(c) for c in ("env -u X gpt-call.sh review", "env -u X bash scripts/gpt-call.sh review --cd x",
                                               "env --unset=X gpt-call.sh review", "env -C /srv/demo gpt-call.sh independent-review",
                                               "bash -o pipefail scripts/gpt-call.sh review", 'X="a b" bash scripts/gpt-call.sh review',
                                               "env A=1 gpt-call.sh review", "time A=1 gpt-call.sh review")]
        s = S("r3eu")
        s.prompt("/fz-review 내 코드", "p1")
        s.pre("Bash", B("env -u X bash scripts/gpt-call.sh review --cd x"))
        out = s.stop(msg="리뷰 끝")
        case("r3-f094-env-u-call — 값을 받는 래퍼 옵션(env -u X)의 값을 건너뛰고 호출을 센다(ISSUE-202616)",
             got == [True] * 8 and out is None, f"{got} · {out}")

    prot = str(tmp / "prot")
    SKILL_READ = {"file_path": "/home/user/.claude/plugins/cache/fz/fz/4.55.0/skills/fz-review/SKILL.md"}

    def bash_at(s, cmd, cwd="/srv/demo"):
        return s.send("PreToolUse", tool_name="Bash", tool_input={"command": cmd}, tool_use_id="t", cwd=cwd)

    @cell
    def r3_pp_asks():
        s = S("r3pp", FZ_GUARD_PROTECTED=prot)
        s.prompt("분석해줘", "p1")
        got = [kind(bash_at(s, "ls", cwd=prot + "/sub")), kind(bash_at(s, f"git -C {prot} status")), kind(bash_at(s, f"cat {prot}/a.txt")),
               kind(bash_at(s, "cat ../prot/x", cwd=str(tmp / "other"))), kind(bash_at(s, "ls /srv/other"))]
        f = S("r3ppf")                                # 상태 폴더의 protected 파일로도 켠다
        (pathlib.Path(f.env["FZ_RUN_STATE"]) / "fz-guard").mkdir(parents=True, exist_ok=True)
        (pathlib.Path(f.env["FZ_RUN_STATE"]) / "fz-guard" / "protected").write_text(f"# 분석 대상\n{prot}\n", encoding="utf-8")
        f.prompt("분석해줘", "p1")
        via_file = kind(bash_at(f, f"cat {prot}/a.txt"))
        w = fz("r3ppw", FZ_GUARD_PROTECTED=prot)       # 승인 전 쓰기 · 보호 경로 — P4 deny 가 남는다
        both = kind(w.pre("Bash", {"command": f"echo x > {prot}/a"}))
        reason = ((bash_at(s, f"cat {prot}/a.txt") or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")
        real, link = tmp / "real", tmp / "link"       # 심링크 별칭 — 설정 철자와 cwd 철자가 달라도 같은 폴더다(r3 8.5 2차)
        (real / "sub").mkdir(parents=True, exist_ok=True)
        if not link.exists():
            link.symlink_to(real)
        a = S("r3ppa", FZ_GUARD_PROTECTED=str(link))
        a.prompt("분석해줘", "p1")
        b = S("r3ppb", FZ_GUARD_PROTECTED=str(real))
        b.prompt("분석해줘", "p1")
        alias = [kind(bash_at(a, "pwd", cwd=str(real.resolve() / "sub"))), kind(bash_at(b, "pwd", cwd=str(link / "sub")))]
        case("r3-f024-protected-path-asks — 보호 경로 아래 cwd · git -C · 경로 인자는 ask(사유 표시) · 밖은 무동작 · 파일 설정 · P4 deny 는 그대로 · 심링크 별칭도 ask",
             got == ["ask"] * 4 + [None] and via_file == "ask" and both == "deny" and "보호 경로" in reason and alias == ["ask", "ask"],
             (got, via_file, both, reason[:60], alias))

    @cell
    def r3_pp_default():
        s = S("r3pe")
        s.prompt("분석해줘", "p1")
        got = [bash_at(s, f"git -C {prot} status"), bash_at(s, "cd $X && ls"), bash_at(s, "echo $[1]")]
        case("r3-f024-default-empty-noop — 보호 경로가 비면(기본) 어떤 Bash 도 묻지 않는다", got == [None, None, None] and not s.err, (got, s.err))

    @cell
    def r3_s4_git_c():
        roots, cwd = ("/srv/live",), "/tmp/elsewhere"
        att = [protected_hit(c, cwd, roots) for c in ("git -C/srv/live status", "git -C$X status", "git -C/srv/other status")]
        case("r3-s4-git-c-attached — 붙여 쓴 git -C값도 보호 경로 대조 · 펼쳐지는 값은 대상 미상 · 밖은 무동작(GPT check r7 P2)",
             att[0] is not None and att[1] is not None and "미상" in att[1] and att[2] is None, att)
        seq = [protected_hit(c, cwd, roots) for c in ("git -C /srv -C live status", "git -c a=b -C /srv/live status", "git -C /srv -C other status")]
        case("r3-s4-git-c-sequence — git -C 를 하위 명령 앞까지 차례로 쌓는다(뒤 -C 는 앞 -C 기준) · -c 뒤 -C 도 본다 · 밖은 무동작(GPT check r7 P2)",
             seq[0] is not None and seq[1] is not None and seq[2] is None, seq)

    @cell
    def r3_pp_unknown():
        s = S("r3pu", FZ_GUARD_PROTECTED=prot)
        s.prompt("분석해줘", "p1")
        got = [kind(bash_at(s, "cd $X && ls")), kind(bash_at(s, "git -C $R status")), kind(bash_at(s, "echo $[1]")), kind(bash_at(s, "ls -la"))]
        case("r3-f024-unknown-target-asks — 대상을 모르는 Bash(확장 든 cd · git -C · 못 읽는 명령)는 ask · 아는 대상은 무동작",
             got == ["ask", "ask", "ask", None], got)

    @cell
    def r3_pp_cd_chain():
        s = S("r3pc", FZ_GUARD_PROTECTED=prot)
        s.prompt("분석해줘", "p1")
        out = str(tmp / "other")                      # 보호 경로 밖 cwd 에서 부모로 옮긴 뒤 상대 경로로 들어간다
        got = [kind(bash_at(s, c, cwd=out)) for c in (f"cd {tmp} && git -C prot status", f"cd {tmp}; ls prot/a.txt",
                                                       f"cd {tmp} && cd prot", f"cd {tmp} && echo x > prot/a", f"cd {tmp} && ls other")]
        case("r3-f024-cd-then-relative-asks — 앞선 cd 를 반영해 상대 경로 · git -C · 리다이렉트 대상을 푼다 · 보호 밖 형제 폴더는 무동작",
             got == ["ask"] * 4 + [None], got)

    @cell
    def r3_read_marks():
        s = fz("r3rd")
        answered(s, "full (Recommended)")             # P4 를 닫아 GP 만 남긴다
        s.post("Read", SKILL_READ, {"type": "text"})
        out = s.stop(msg="리뷰 끝")
        case("r3-f094-skill-read-marks-review — /fz 창 안에서 fz-review SKILL.md 를 읽으면 리뷰 턴이다(GPT 리뷰 없이 끝내면 Stop 차단)",
             blocked(out) and "fz-guard GP" in out.get("reason", ""), out)

    @cell
    def r3_read_outside():
        s = S("r3ro")
        s.prompt("이 스킬 문서 읽어줘", "p1")
        s.post("Read", SKILL_READ, {"type": "text"})
        out = s.stop(msg="끝")
        case("r3-f094-skill-read-outside-window-ignored — /fz 창 밖 Read 는 리뷰 턴이 아니다", not blocked(out), out)

    @cell
    def r3_read_fast():
        s = S("r3fp")
        sdir = pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard"
        o = s.post("Read", {"file_path": "/srv/demo/a.swift"}, {"type": "text"})
        o2 = s.post("Read", {"file_path": "/srv/demo/skills/fz-review/README.md"}, {"type": "text"})
        case("r3-guard-read-fastpath-no-state-io — 다른 경로 Read 는 상태 폴더 · 파일 · 잠금을 만들지 않는다",
             o is None and o2 is None and not sdir.exists(), (o, o2, sdir.exists()))

    @cell
    def r3_unknown():
        s = fz("r3un")
        unread = kind(s.pre("Bash", B(f"printf x \\>> {reg}")))
        plain = s.pre("Bash", B(f"printf x >> {reg}"))
        calls = [gpt_review_invoked(c) for c in ("bash gpt-call.sh review 'unclosed", 'echo "gpt-call.sh review',
                                                 "bash gpt-call.sh review \\>> o")]
        case("r3-unknown-final-guard — 못 읽은 명령은 P4 창 안 쓰기다(레지스트리 면제도 없다) · GPT 호출 증거가 아니다",
             unread == "deny" and plain is None and calls == [False] * 3, f"{unread} · {plain} · {calls}")

    @cell
    def r3_s1_devnull_nested():
        got = [bash_write(c) for c in ("f=$(ls x 2>/dev/null | head -1)", "x=$(cd /tmp && ls 2>/dev/null)", "x=$(echo y > out)")]
        s = fz("r3dn")
        read = s.pre("Bash", B("f=$(ls x 2>/dev/null | head -1)"))
        case("r3-s1-devnull-nested-read — 치환 안 /dev/null 리다이렉트는 읽기다(승인 전 창에서 막지 않는다) · 치환 안 실제 쓰기는 대상 미상",
             got == [(False, []), (False, []), (True, [])] and read is None, f"{got} · {read}")

    @cell
    def r3_s1_tilde_target():
        got = [bash_write(c) for c in ("echo x > ~/a.md", 'echo x > "~/a.md"', "cp a ~/b.md")]
        case("r3-s1-tilde-target-resolved — 따옴표 없는 앞머리 ~/ 대상은 HOME 으로 푼다(레지스트리 · index 면제를 받는다) · 따옴표 든 ~ 는 미상",
             got == [(True, [os.path.expanduser("~/a.md")]), (True, []), (True, [os.path.expanduser("~/b.md")])], got)

    @cell
    def r3_s1_inline_code():
        writes = ("bash -c 'echo x > f'", "sh -c 'cp a b'", 'bash -c "$cmd"', "xargs sh -c 'mv \"$1\" x' _", "bash -c",
                  "bash -o pipefail -c 'echo x > f'", "python3 -c \"open('f','w').write('x')\"",
                  "node -e \"require('fs').writeFileSync('a','b')\"", "perl -pi -e 's/a/b/' f",
                  "python3 -c \"import os; os.remove('f')\"", "node -e \"require('fs').renameSync('a','b')\"",
                  "node -e \"require('fs').mkdirSync('d')\"",
                  # 옛 판정이 읽기로 보던 꼴 — 코드를 읽지 않는다(쓰기 신호 표가 라운드마다 샜다 · r5 005 · 007 · 008)
                  "bash -lc 'ls -la'", "zsh -c 'cat a > /dev/null'", "dash -c 'touch f'", "python3 -c 'print(1>0)'",
                  "python3 -c \"import sys; sys.stdout.write('x')\"", "python3 -m json.tool f", "python3 s.py -c x",
                  "node --require fs -e 'x'", "python3 -c \"$CODE\"", "python3 -c \"import os; os.spawnv(0, 'x', [])\"",
                  'bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" set gpt-x high', 'python3 "$R/scripts/run_metrics.py" start',
                  'bash "$R/other/gpt-choice.sh" get', 'bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" "$SUB"')
        reads = ('bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" get', 'bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" decide plan',
                 'python3 "${FZ_PLUGIN_ROOT}/scripts/autonomy_decide.py" --action mode_select --in-scope --reversible',
                 'python3 "${FZ_PLUGIN_ROOT}/scripts/mode_gate.py" code --no-plan')
        bad = [c for c in writes if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c)[0]]
        case("r3-s1-inline-code-writes — 인터프리터(셸 · python · node · perl · ruby · dash)는 코드와 무관하게 대상 미상 쓰기다(쓰기 신호 표를 두지 "
             "않는다) · 승인 전 창 플러그인 스크립트(PLUGIN_READ 의 scripts/이름 · 하위 명령)만 읽기", not bad, bad)

    @cell
    def r3_s1_funcdef():
        calls = [gpt_review_invoked(c) for c in ("f () { :; gpt-call.sh review; }", "f() { :; gpt-call.sh review; }",
                                                 "f()\n{\n gpt-call.sh review\n}", "f() ( gpt-call.sh review )")]
        got = [bash_write(c) for c in ("g(){ git -C x grep -n y; }; g a", "f(){ echo x > t; }", "f() ( cp a b )")]
        case("r3-s1-funcdef-deferred-guard — 함수 본문의 GPT 호출은 호출 증거가 아니다(4차 006 공백 꼴 포함) · 정의만 하는 명령은 읽기 · "
             "본문 쓰기는 대상 미상", calls == [False] * 4 and got == [(False, []), (True, []), (True, [])], f"{calls} · {got}")

    @cell
    def r3_s1_outside_read():
        names = sorted({k + "x" for k in READ} | {"X" + k for k in READ} | {
            "make", "curl", "xcrun", "swift", "claude", "ln", "chmod", "tar", "rsync", "open", "defaults", "osascript", "dd", "install",
            "patch", "split", "truncate", "eval", "source", ".", "trap", "builtin", "node", "ruby", "perl", "dash", "ksh", "fish", "python3"})
        names = [n for n in names if n not in READ]
        spots = ("{} a", "if true; then {} a; fi", 'for f in b; do {} "$f"; done', "! {} a", "{{ {} a; }}", "time -p {} a", "X=1 {} a",
                 "env -u Y {} a", "nohup {} a", "echo $({} a)", "true && {} a", "while false; do {} a; done", "xargs {} a")
        bad = [s.format(n) for n in names for s in spots if bash_write(s.format(n)) != (True, [])]
        reads = [bash_write(s.format(n)) for n in ("cat", "grep") for s in spots]
        case("r3-s1-outside-read-table-writes — 읽기 표 밖 이름은 어느 명령 자리(맨 앞 · 예약어 · 루프 · { } · ! · time · 대입 · 래퍼 · 치환 · "
             "xargs 뒤)에서든 대상 미상 쓰기다(r5 004) · 표 안 이름은 같은 자리에서 읽기",
             len(names) > 100 and not bad and reads == [(False, [])] * len(reads), (len(names), bad[:5], len(bad), reads))

    @cell
    def r3_s1_mandated():
        sk = PLUGIN_ROOT.parent.parent / "skills" / "fz" / "SKILL.md"
        if not sk.is_file():
            print("SKIP r3-s1-mandated-preapproval-read — 저장소 밖 사본(skills/fz/SKILL.md 가 없다)")
            return
        text = sk.read_text(encoding="utf-8")
        a, b = text.find("## Phase 0"), text.find("## Phase 5")
        spans = re.findall(r"`([^`\n]*scripts/[\w.-]+\.(?:sh|py)[^`\n]*)`", text[a:b]) if 0 <= a < b else []
        cmds = [s if s.startswith(("bash ", "python3 ")) else
                ("bash" if s.split()[0].endswith(".sh") else "python3") + ' "${FZ_PLUGIN_ROOT}/' + " ".join([s.split()[0] + '"'] + s.split()[1:])
                for s in spans]
        bad = [c for c in cmds if bash_write(c, "/srv/demo")[0]]
        s = fz("r3md")
        mk = [s.pre("Bash", B(c)) for c in ("mkdir -p /srv/demo/NOTASK-20261110", "mkdir -p NOTASK-20261110", "mkdir /srv/demo/TKT-1234",
                                            "mkdir -p /srv/demo/NOTASK-20261110 2>/dev/null")]
        den = [kind(s.pre("Bash", B(c))) for c in ("rm -rf /srv/demo/NOTASK-20261110", "mkdir -p /srv/demo/other",
                                                   "cd /tmp && mkdir -p NOTASK-20261110", "mkdir -p /srv/demo/x/NOTASK-20261110", 'mkdir -p "$W"')]
        case("r3-s1-mandated-preapproval-read — /fz Phase 0~4 본문의 플러그인 스크립트 호출(본문에서 뽑는다)과 Phase 0 WORK_DIR mkdir 은 승인 전에 "
             "막히지 않는다 · WORK_DIR 지우기 · 다른 폴더 · 이동 뒤 · 펼친 mkdir 은 막힌다",
             any("gpt-choice.sh" in c for c in cmds) and not bad and mk == [None] * 4 and den == ["deny"] * 5, (cmds, bad, mk, den))

    @cell
    def r3_s1_read_forms():
        reads = ["sed -n '10,20p' f", "sed -n '/a/,/b/p' f", "sed 's/a/b/g; s|c|d|' f", "sed -E -e 's/x/y/' -e '/^#/d' f", "sed '1d;$d' f",
                 "awk 'NR>1 {print $2}' f", "awk -F: '{print $1}' f", "find . -name '*.md' -mtime -1 -print", "sort -u -k2,2 f",
                 "sort -t, -k1n f", "uniq -c f", "git -C /srv/x log --oneline -5", "git show HEAD:a.md", "git branch -a",
                 "git branch --list 'feat*'", "git tag -l", "git config --get core.hooksPath", "git stash list", "git worktree list",
                 "git remote -v", "git diff --stat", "git apply --check p.patch", "gh pr view 12 --json title", "gh api repos/o/r/pulls/1",
                 "gh api -X GET search/issues -f q=x", "gh search code x", "rg -n x src", "date +%F", "base64 -i f",
                 # 펼친 인자는 값이다 — 줄 번호 · 경로 · 리비전 · PR 번호
                 'sed -n "${A},${B}p" "$F"', 'sed -n "$((N+1)),$((N+5))p" f', 'git -C "$W" show "$SHA":a.md', 'gh pr view "$PR" --json body',
                 'find "$W" -name x', 'uniq "$F"']
        writes = ["sed -i '' 's/a/b/' f", "sed '-i' 's/a/b/' f", "sed -n '1w out' f", "sed 's/a/b/w out' f", "sed 's/a/b/e' f",
                  "sed -f s.sed f", 'sed "$S" f', "awk '{print > \"o\"}' f", "awk '{print | \"sh\"}' f", "awk 'BEGIN{system(\"rm x\")}'",
                  "awk -f p.awk f", 'awk "$P" f', "find . -delete", "find . -exec rm {} +", "find . -fprint o", "sort -o out f",
                  "sort -uo out f", "sort --output=o f", "sort --compress-program=x f", "uniq a b", "git commit -m x",
                  "git -c core.pager=x log", "git branch newb", "git tag v1", "git config core.x y", "git stash", "git worktree add w",
                  "git remote add o u", "git diff --output=o", "git grep -O x", "git apply p.patch", "git checkout -- a", 'git "$SUB" x', "uniq $F", 'sed "1${C}" f',
                  "gh pr create", "gh pr checkout 1", "gh api -X POST x", "gh api x -f a=b", "gh api graphql -f query=x", "rg --pre=x y",
                  "date -s 1200", "date 0101", "base64 -o out f"]
        bad = [c for c in reads if bash_write(c)[0]] + [c for c in writes if bash_write(c) != (True, [])]
        case("r3-s1-read-forms — 쓰기 모드가 있는 명령(sed · awk · find · sort · uniq · git · gh · rg · date · base64)은 읽기 꼴만 읽기다 · -i · w · e · "
             "print > · system · -delete · -exec · -o · 쓰기 하위 명령 · -c · --output · POST · 필드 · graphql · 펼친 인자는 대상 미상 쓰기",
             not bad, bad)

    @cell
    def r3_s1_r5_forms():
        got = [bash_write(c, "/srv/demo") for c in ("touch -- -target", "tee -- -x", "cd /tmp; printf x > NOTASK-20261110/index.md",
                                                    "env -C /tmp tee NOTASK-20261110/index.md", "if true; then touch r; fi",
                                                    'for f in a; do rm "$f"; done', "rm -rf /srv/demo/NOTASK-20261110")]
        want = [(True, ["-target"]), (True, ["-x"]), (True, []), (True, []), (True, ["r"]), (True, []), (True, ["/srv/demo/NOTASK-20261110"])]
        s = fz("r3r5")
        den = [kind(s.pre("Bash", B(c))) for c in ("cd /tmp; printf x > NOTASK-20261110/index.md", "rm -rf /srv/demo/NOTASK-20261110")]
        idx = s.pre("Bash", B("printf x > NOTASK-20261110/index.md"))
        calls = [gpt_review_invoked(c) for c in ("f() { :; } > $(gpt-call.sh review)", 'f() { :; } 2> "$(bash scripts/gpt-call.sh review)"')]
        case("r3-s1-r5-forms — 예약어 뒤 명령 · `--` 뒤 대상 · 폴더 이동 뒤 상대 대상(면제 없음) · WORK_DIR 지우기는 막힌다 · 함수에 붙은 리다이렉트 안 "
             "호출은 호출이 아니다(r5 003 · 004 · 009 · 010)",
             got == want and den == ["deny"] * 2 and idx is None and calls == [False, False], (got, den, idx, calls))

    @cell
    def r3_s1_r6_002():
        got = [bash_write(c, "/srv/demo") for c in ("touch() { :; }; command touch gates/plan.md", "touch() { :; }; /usr/bin/touch gates/plan.md",
                                                    "touch() { :; }; env touch gates/plan.md", "touch() { :; }; touch gates/plan.md")]
        case("r3-s1-r6-002-command-bypasses-function — command · 래퍼 · 경로로 부르면 같은 이름 함수가 아니라 외부 명령이다 · 맨 이름 호출만 함수",
             got == [(True, ["gates/plan.md"])] * 3 + [(False, [])], got)

    @cell
    def r3_s1_r6_003():
        got = [bash_write(c, "/srv/demo") for c in ("env -Cmods touch TKT-123/index.md", "env --chdir=mods touch TKT-123/index.md",
                                                    "touch TKT-123/index.md")]
        case("r3-s1-r6-003-attached-chdir — 붙여 쓴 -C값도 폴더를 옮긴다(상대 대상 미상) · 옮기지 않으면 대상이 보인다",
             got == [(True, []), (True, []), (True, ["TKT-123/index.md"])], got)

    @cell
    def r3_s1_r6_004():
        got = [bash_write(c, "/srv/demo") for c in ("mv src.py TKT-123/index.md", "mv -f a b c/")]
        case("r3-s1-r6-004-mv-source — mv 는 원본도 지운다(피연산자 전부가 쓰기 대상)",
             got == [(True, ["src.py", "TKT-123/index.md"]), (True, ["a", "b", "c/"])], got)
        got = [bash_write(c, "/srv/demo") for c in ("cp -R source TKT-123/index.md", "cp -pa s d", "cp -rf s d", "cp a.md TKT-123/index.md")]
        case("r3-s1-r6-004-cp-recursive — 재귀 cp 는 대상 아래 하위 경로를 모른다(대상 미상) · 단일 cp 는 마지막 인자",
             got == [(True, []), (True, []), (True, []), (True, ["TKT-123/index.md"])], got)

    @cell
    def r3_s1_r6_005():
        got = [bash_write(c, "/srv/demo") for c in ("mkdir -p TKT-123 > TKT-123", "mkdir -p TKT-123 2>/dev/null", "mkdir -p TKT-123")]
        case("r3-s1-r6-005-mkdir-redirect — WORK_DIR mkdir 면제는 피연산자만이다(같은 명령의 리다이렉트는 따로 판정) · /dev/null 은 그대로 면제",
             got == [(True, ["TKT-123"]), (False, []), (False, [])], got)

    @cell
    def r3_parity():
        lost = [c for c in parity_writes if not bash_write(c)[0]] + [c for c in parity_nocall if gpt_review_invoked(c)]
        case("r3-replaced-path-parity-guard — 수정 전 옛 판정이 쓰기 · 미상이던 꼴은 쓰기로, GPT 호출이 아니던 꼴은 아닌 채로 남는다"
             "(의도한 오탐 고침 env -u · 인자 중괄호는 자기 셀이 잰다)", not lost, lost)

    @cell
    def f297():
        word = "Co" + "dex"                        # ⛔ 이 파일도 표면 검사 대상이다 — 시험 자료의 옛 호칭은 실행 때 만든다
        root = tmp / "f297" / "plug"
        (root / ".claude-plugin").mkdir(parents=True)
        (root / ".claude-plugin" / "plugin.json").write_text('{"name": "fz"}', encoding="utf-8")
        (root / "mods" / "sub" / ".claude-plugin").mkdir(parents=True)
        (root / "mods" / "sub" / ".claude-plugin" / "plugin.json").write_text('{"name": "fz-guard"}', encoding="utf-8")
        (root / "scripts").mkdir()
        real = PLUGIN_ROOT.parent.parent / "scripts" / "check_gpt_surface.py"
        if real.is_file():
            shutil.copyfile(real, root / "scripts" / "check_gpt_surface.py")
        else:                                      # 설치본(하위 플러그인만 복사)에는 저장소 판별식이 없다 — 같은 API 의 최소판
            (root / "scripts" / "check_gpt_surface.py").write_text(
                "import re\nTOKEN = re.compile('co' 'dex', re.I)\nALLOW_RE = re.compile(r'~/\\.co' r'dex[\\w./-]*', re.I)\n"
                "EXCLUDE_PREFIX = ('tests/fixtures/',)\nBOUNDARY = {'scripts/gpt-exec.sh'}\nSUFFIXES = ('.md', '.sh', '.py')\n"
                "def norm(t):\n    return re.sub(r'\\s+', ' ', t).strip()\n"
                "def residual(line):\n    return bool(TOKEN.search(ALLOW_RE.sub('', line)))\n", encoding="utf-8")
        s = S("f297")
        s.prompt("문서 고쳐줘", "p1")
        bad = s.pre("Write", {"file_path": str(root / "guides" / "a.md"), "content": f"{word} CLI 로 교차 검증"})
        nested = s.pre("Edit", {"file_path": str(root / "mods" / "sub" / "CLAUDE.md"), "old_string": "a", "new_string": f"{word} 리뷰"})
        others = [s.pre("Write", {"file_path": "/srv/demo/notes.md", "content": f"{word} CLI"}),
                  s.pre("Write", {"file_path": str(root / "guides" / "a.md"), "content": "설정은 `~/." + word.lower() + "/config.toml`"}),
                  s.pre("Edit", {"file_path": str(root / "scripts" / "gpt-exec.sh"), "old_string": "a", "new_string": word.lower() + " exec -- x"}),
                  s.pre("Write", {"file_path": str(root / "guides" / "b.md"), "content": "GPT 로 교차 검증"})]
        case("f297-gpt-wording-write-denied", kind(bad) == "deny" and "F-297" in bad["hookSpecificOutput"]["permissionDecisionReason"]
             and kind(nested) == "deny" and others == [None] * 4, f"{bad} · {nested} · {others}")

    @cell
    def c20():
        case("p4-todowrite-not-matched", fz("c20").pre("TodoWrite", {"todos": []}) is None)

    @cell
    def c21():
        s = fz("c21")
        got = [s.pre(t, {"file_path": "/srv/demo/a.swift"}) for t in ("Read", "Grep", "Glob", "mcp__plugin_fz_serena__find_symbol", "mcp__xcode__XcodeRead")]
        case("p4-read-tools-not-matched", got == [None] * 5, got)

    @cell
    def c22():
        o = fz("c22").stop()
        case("p4-text-only-stop-blocked", blocked(o) and "Phase 4" in o.get("reason", ""), o)

    @cell
    def c23():
        s = fz("c23")
        s.post("AskUserQuestion", p4q(), "User answered in some unknown shape")
        o = s.pre("Write", W)
        lr = last_response(s)
        case("p4-answer-unparseable-warn-allow", kind(o) is None and warned(o, WARN_UNDECIDED)
             and lr.get("verdict") == "unparseable" and lr.get("raw") == "User answered in some unknown shape", f"{o} {lr}")

    @cell
    def c23b():
        s = fz("c23b")
        ti = p4q()
        s.post("AskUserQuestion", ti, {"questions": ti["questions"], "answers": {"다른 질문 본문": "full (Recommended)"}})
        o = s.pre("Write", W)
        lr = last_response(s)
        case("f566-guard-answer-key-mismatch", kind(o) is None and warned(o, WARN_UNDECIDED) and lr.get("verdict") == "mismatch",
             f"{o} {lr}")

    @cell
    def c24():
        o = fz("c24").pre("Agent", {"subagent_type": "fz:review-arch", "prompt": "x"})
        case("f058-ad-hoc-agent-asked", kind(o) == "ask", o)

    @cell
    def c25():
        case("task-adhoc-in-fz-ask", kind(fz("c25").pre("Task", {"subagent_type": "general-purpose", "prompt": "x"})) == "ask")

    @cell
    def c26():
        s = fz("c26")
        got = [s.pre("Agent", {"subagent_type": t}) for t in ("pr-review-toolkit:silent-failure-hunter", "deep-research-agent",
                                                              "pr-review-toolkit:code-simplifier", "pr-review-toolkit:type-design-analyzer")]
        case("agent-native-allowlisted", got == [None] * 4, got)

    @cell
    def c27():
        s = S("c27")
        s.prompt("조사해줘", "p1")
        case("agent-no-fz-allowed", s.pre("Agent", {"subagent_type": "Explore"}) is None)

    def lesson(s):
        s.post("Write", {"file_path": mem, "content": "fz-plan 교훈 — F-518 재발"})

    @cell
    def c28():
        s = S("c28")
        s.prompt("분석해줘", "p1")
        lesson(s)
        o = s.stop()
        case("f518-memory-only-lesson-blocked", blocked(o) and "F-518" in o.get("reason", ""), o)

    @cell
    def c29():
        s = S("c29")
        s.prompt("분석해줘", "p1")
        lesson(s)
        s.post("Write", {"file_path": reg, "content": "x"})
        case("stop-registry-written-allowed", s.stop() is None)

    @cell
    def c30():
        s = S("c30")
        s.prompt("분석해줘", "p1")
        lesson(s)
        s.pre("Write", {"file_path": reg, "content": "x"})      # 실패한 쓰기 — PostToolUse 가 오지 않는다(PostToolUseFailure)
        case("stop-registry-write-failed-blocked", blocked(s.stop()))

    @cell
    def c31():
        a, b = S("c31", sid="sa"), S("c31", sid="sb")
        a.prompt("분석해줘", "p1")
        lesson(a)
        b.prompt("다른 세션", "p1")
        case("stop-other-session-ignored", b.stop() is None)

    @cell
    def c32():
        s = S("c32")
        s.prompt("분석해줘", "p1")
        lesson(s)
        first, second = s.stop(), s.stop()
        case("stop-same-fingerprint-second-passes", blocked(first) and second is None, f"{first} · {second}")

    @cell
    def c33():
        s = S("c33")
        s.prompt("분석해줘", "p1")
        lesson(s)
        active = s.stop(active=True)
        case("stop-hook-active-passes", active is None and blocked(s.stop()), active)

    @cell
    def c34():
        s = S("c34")
        s.pid = "p9"                                # UserPromptSubmit 이 기록되지 않은 prompt(설치 전 시작)
        o = s.pre("Write", W)
        case("state-incomplete-warn-not-deny", kind(o) is None and warned(o, WARN_INCOMPLETE), o)

    @cell
    def c35():
        d = state_dir({"HOME": str(tmp / "c35" / "home")})
        bad = PLUGIN_ROOT / ".state-probe"
        out, err = run(json.dumps({"session_id": "s1", "hook_event_name": "Stop"}), {"FZ_RUN_STATE": str(bad), "PATH": "/usr/bin"})
        case("state-outside-plugin-dir", not inside_plugin(d) and out == "" and "플러그인 안" in err and not bad.exists(), err)

    @cell
    def c36():
        a, b = fz("c36", sid="sa"), S("c36", sid="sb")
        b.prompt("평범한 요청", "p1")
        files = sorted(p.name for p in (tmp / "c36" / "runs" / "fz-guard").glob("*.json"))
        case("state-parallel-sessions-isolated", kind(a.pre("Write", W)) == "deny" and b.pre("Write", W) is None and files == ["sa.json", "sb.json"], files)

    @cell
    def c37():
        d = tmp / "c37"
        d.mkdir()
        p = d / "s.json"
        save_state(p, fresh())
        before = p.read_text(encoding="utf-8")
        try:
            save_state(p, {"x": object()})          # 직렬화 도중 실패 — 옛 상태가 남고 임시 파일이 없어야 한다
            raised = False
        except TypeError:
            raised = True
        case("state-write-interrupted-atomic", raised and p.read_text(encoding="utf-8") == before and not list(d.glob("*.tmp")), list(d.iterdir()))

    @cell
    def c38():
        s = fz("c38")                               # transcript 에는 이 /fz 도 승인도 없다(비동기 기록 지연)
        answered(s, "light")
        case("transcript-lag-no-false-deny", s.pre("Write", W) is None and s.stop() is None)

    @cell
    def c39():
        s = fz("c39", FZ_GUARD_DISABLE="P4")
        off_all = S("c39b", FZ_GUARD_DISABLE="all")
        off_all.prompt("/fz x", "p1")
        case("disable-env-passes", s.pre("Write", W) is None and off_all.pre("Write", W) is None
             and not (tmp / "c39b" / "runs" / "fz-guard").exists())

    @cell
    def c40():
        s = fz("c40")
        before = kind(s.pre("Write", W))
        flag = tmp / "c40" / "runs" / "fz-guard" / "disable"
        flag.write_text("P4\n", encoding="utf-8")
        during = s.pre("Write", W)
        flag.unlink()
        case("disable-file-flag-passes", before == "deny" and during is None and kind(s.pre("Write", W)) == "deny", during)

    @cell
    def c41():
        e = env_for("c41")
        got = [run(x, e) for x in ("not json", "[]", json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Write"}))]
        case("malformed-input-fail-open", all(o == "" and err.startswith("fz-guard diag:") for o, err in got), got)

    @cell
    def c42():
        o = fz("c42", transcript=tmp / "없다.jsonl").pre("Write", W)
        case("transcript-missing-fail-open", kind(o) is None, o)

    @cell
    def c43():
        blocker = tmp / "c43-file"
        blocker.write_text("x", encoding="utf-8")
        s = S("c43")
        s.env["FZ_RUN_STATE"] = str(blocker)        # 파일 아래에 폴더를 만들 수 없다
        s.prompt("/fz x", "p1")
        o = s.pre("Write", W)
        case("state-write-failure-fail-open", o is None and s.err.startswith("fz-guard diag:"), s.err)

    @cell
    def c44():
        d = tmp / "c44"
        d.mkdir()
        marker = b'{"type": "attachment", "entrypoint": "cli"}\n'
        late_bytes, late_lines = d / "late-bytes.jsonl", d / "late-lines.jsonl"   # 캡 너머에만 entrypoint — 하드 캡이면 unknown 이다
        late_bytes.write_bytes(b'{"type": "x", "pad": "' + b"y" * (PREFIX_BYTES + 1000) + b'"}\n' + marker)   # 바이트 캡
        late_lines.write_bytes(b'{"type": "x"}\n' * (PREFIX_LINES + 50) + marker)                          # 줄 캡
        make_synthetic(20 << 20, str(d / "big.jsonl"), True)
        t = time.perf_counter()
        modes = [session_mode(str(d / "big.jsonl")), session_mode(str(late_bytes)), session_mode(str(late_lines))]
        ms = (time.perf_counter() - t) * 1000
        case("large-transcript-prefilter", modes == ["interactive", "unknown", "unknown"] and ms < 2000, f"{modes} {ms:.0f}ms")

    for n, (text, tag) in enumerate((("/fz-code light 구현", "p4-direct-fz-code-no-window"), ("/fz:fz-plan 계획", "p4-direct-fz-plan-no-window"),
                                     ("/fz-review full", "p4-direct-fz-review-no-window"))):
        def direct(text=text, tag=tag, n=n):
            s = S(f"d{n}")
            s.prompt(text, "p1")
            # fz-review 턴의 GPT 누락은 GP(F-094)가 따로 본다 — 이 셀은 P4 창만 잰다
            case(tag, s.pre("Write", W) is None and s.stop(msg="[외부: GPT] 확인") is None)
        cells.append(direct)

    @cell
    def c48():
        s = S("c48")
        s.prompt("구현해줘", "p1")
        s.pre("Skill", {"skill": "fz:fz-code"})
        case("p4-skill-fz-code-no-window", s.pre("Write", W) is None)

    @cell
    def c49():
        e = env_for("c49")
        base = {"session_id": "s1", "prompt_id": "p1", "transcript_path": str(t_cli), "hook_event_name": "PostToolUse", "tool_name": "Write"}
        run(json.dumps(dict(base, hook_event_name="UserPromptSubmit", prompt="분석")), e)
        procs = [subprocess.Popen([sys.executable, str(pathlib.Path(__file__).resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, env=e, text=True) for _ in range(8)]
        for i, p in enumerate(procs):
            p.stdin.write(json.dumps(dict(base, tool_input={"file_path": f"/srv/demo/f{i}.swift", "content": "x"}, tool_response={})))
            p.stdin.close()
        for p in procs:
            p.wait(timeout=30)
        st = load_state(pathlib.Path(e["FZ_RUN_STATE"]) / "fz-guard" / "s1.json")
        got = sorted((st["turns"].get("p1") or {}).get("writes", []))
        case("state-concurrent-posttooluse-union", got == sorted(f"/srv/demo/f{i}.swift" for i in range(8)), got)

    @cell
    def c50():
        s = fz("c50")
        sdir = pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard"
        fd = os.open(str(sdir / "s1.lock"), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            e = dict(s.env, FZ_GUARD_LOCK_TIMEOUT="0.3")
            t = time.perf_counter()
            p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve())], input=json.dumps(
                {"session_id": "s1", "prompt_id": "p1", "transcript_path": str(t_cli), "hook_event_name": "PreToolUse", "tool_name": "Write",
                 "tool_input": W}), capture_output=True, text=True, env=e, timeout=30)
            ms = (time.perf_counter() - t) * 1000
        finally:
            os.close(fd)
        case("state-lock-timeout-fail-open", p.returncode == 0 and p.stdout == "" and "잠금" in p.stderr and ms < 5000, f"{p.returncode} {p.stderr} {ms:.0f}ms")

    @cell
    def c51():
        s = fz("c51")
        answered(s, "light")
        case("p4-approval-object-response", s.pre("Write", W) is None)

    @cell
    def c52():
        s = fz("c52")
        answered(s, "full (Recommended)", as_text=True)
        case("p4-approval-string-response", s.pre("Write", W) is None)

    @cell
    def c53():
        s = S("c53")
        s.prompt("/fz-code light", "p1")
        case("agent-adhoc-in-direct-skill-ask", kind(s.pre("Agent", {"subagent_type": "general-purpose"})) == "ask")

    @cell
    def c54():
        s = fz("c54")
        first = s.stop()                           # 승인 없이 /fz 턴을 끝냈다 → 1회 block
        s.prompt("a.swift 오타만 고쳐줘", "p2")
        edit = s.pre("Edit", {"file_path": "/srv/demo/a.swift", "old_string": "a", "new_string": "b"})
        second = s.stop()
        s.prompt("/fz-code light 이어서", "p3")
        direct = s.pre("Write", W)
        case("p4-window-scoped-to-opening-prompt", blocked(first) and edit is None and second is None and direct is None,
             f"{first} · {edit} · {second} · {direct}")

    @cell
    def c55():
        auto = fz("c55", FZ_AUTONOMY="autonomous").pre("Agent", {"subagent_type": "general-purpose"})
        h = S("c55h", transcript=t_sdk)
        h.prompt("/fz 계획", "p1")
        head = h.pre("Agent", {"subagent_type": "general-purpose"})
        u = S("c55u", transcript=t_none)
        u.prompt("/fz 계획", "p1")
        unk = u.pre("Agent", {"subagent_type": "general-purpose"})
        case("agent-adhoc-autonomous-headless-no-ask", auto is None and head is None and kind(unk) is None and warned(unk, WARN_UNDECIDED),
             f"{auto} · {head} · {unk}")

    @cell
    def c56():
        h = S("c56", transcript=t_sdk)
        h.prompt("분석해줘", "p1")
        lesson(h)
        a = S("c56a", FZ_AUTONOMY="autonomous")
        a.prompt("분석해줘", "p1")
        lesson(a)
        case("stop-memory-only-headless-autonomous-not-blocked", h.stop() is None and a.stop() is None)

    @cell
    def c57():
        s = fz("c57", FZ_AUTONOMY=" Autonomous ")
        case("p4-autonomy-value-normalized", s.pre("Write", W) is None and s.stop() is None)

    @cell
    def c58():
        s = fz("c58")
        sneak = s.pre("Write", {"file_path": "/srv/data/fz-findings/entries/../../src/a.js", "content": "x"})
        case("p4-registry-traversal-denied", kind(sneak) == "deny" and s.pre("Write", {"file_path": reg, "content": "x"}) is None, sneak)

    @cell
    def c59():
        s = fz("c59", FZ_GUARD_DISABLE="1")
        o = s.pre("Write", W)
        case("kill-unknown-value-disables-all", o is None and "모른다" in s.err, f"{o} · {s.err}")

    @cell
    def c60():
        s = fz("c60")
        flag = pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard" / "disable"
        flag.write_bytes(b"\xff\xfe")
        bad, bad_err = s.pre("Write", W), s.err
        flag.write_text("all\n")
        os.chmod(flag, 0)
        unread, unread_err = s.pre("Write", W), s.err
        os.chmod(flag, 0o600)
        flag.unlink()
        back = s.pre("Write", W)
        case("kill-flag-unreadable-disables-all", bad is None and unread is None and "읽지 못했다" in bad_err + unread_err
             and bad_err and unread_err and kind(back) == "deny", f"{bad} {bad_err} · {unread} {unread_err} · {back}")

    @cell
    def c61():
        out, err = run(json.dumps({"session_id": "s1", "prompt_id": "p1", "hook_event_name": "PreToolUse", "tool_name": "Write",
                                   "tool_input": W}), {"FZ_RUN_STATE": "~fz-guard-no-such-user-xyz/x", "PATH": "/usr/bin:/bin"})
        case("state-dir-error-fail-open", out == "" and err.startswith("fz-guard diag:"), f"{out!r} {err!r}")

    @cell
    def c62():
        s = S("c62")
        sdir = pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard"
        sdir.mkdir(parents=True)
        (sdir / "s1.json").write_text('{"schema": 1}')
        s.prompt("/fz 계획 세워줘", "p1")
        case("state-missing-keys-recovers", kind(s.pre("Write", W)) == "deny")

    @cell
    def c63():
        s = S("c63")
        s.pid = "p9"                                # UserPromptSubmit 이 기록되지 않은 prompt — Skill fz 만 창을 연다
        s.pre("Skill", {"skill": "fz:fz"})
        o = s.pre("Write", W)
        st = s.stop()
        case("stop-incomplete-start-not-blocked", kind(o) is None and warned(o, WARN_INCOMPLETE) and not blocked(st), f"{o} · {st}")

    try:
        for fn in cells:
            try:
                fn()
            except Exception as e:                 # ⛔ 셀 안 예외는 FAIL 로 센다
                case(f"{fn.__name__}-exception", False, repr(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"self-test {sum(results)}/{len(results)} passed")
    return 0 if results and all(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="fz-guard hook")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--check-allowlist", metavar="FILE")
    ap.add_argument("--make-synthetic", nargs=2, metavar=("BYTES", "OUT"))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--with-marker", action="store_true")
    g.add_argument("--no-marker", action="store_true")
    ap.add_argument("--bench", metavar="FILE")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.check_allowlist:
        return check_allowlist(a.check_allowlist)
    if a.make_synthetic:
        if not (a.with_marker or a.no_marker):
            print("UNRUN: --with-marker 또는 --no-marker 가 필요하다", file=sys.stderr)
            return 2
        make_synthetic(int(a.make_synthetic[0]), a.make_synthetic[1], a.with_marker)
        return 0
    if a.bench:
        bench(a.bench)
        return 0
    try:
        data = sys.stdin.read()
    except (OSError, UnicodeDecodeError):
        return 0
    out, err = run(data, os.environ)
    if out:
        sys.stdout.write(out + "\n")
    if err:
        sys.stderr.write(err + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
