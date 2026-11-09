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

상태 정리(F-564) — UserPromptSubmit 마다 마지막 기록이 STALE_DAYS 지난 다른 세션의 상태 · 잠금을 지운다(사건 1회에 최대 PRUNE_MAX).

사건은 훅 입력에서 상태로 기록한다 — ⛔ transcript 는 비동기로 기록돼 현재 사건이 아직 없을 수 있다(공식 훅 문서).
transcript 에서는 굳은 사실 하나만 읽는다: 첫 줄들의 entrypoint(cli=interactive · sdk-cli=headless · 그 밖=불명).

상태   ${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/<session_id>.json — 세션별 잠금(<session_id>.lock · fcntl.flock)으로
       읽기 · 병합 · 판정 · 저장을 직렬화하고 mkstemp + os.replace 로 원자 교체한다. 플러그인 폴더 안이면 쓰지 않는다
끄기   env FZ_GUARD_DISABLE=P4,AG,FR,GP|all · 파일 플래그 <상태 폴더>/disable(내용 = 규칙 목록 · 비면 all) — 매 실행 확인
실패   ⛔ 입력 · 의존성 · 잠금 · 상태 오류는 전부 exit 0 · 결정 없음(fail-open). 진단은 stderr `fz-guard diag:` 로만 낸다

모드
  (인자 없음)                훅 — stdin JSON 하나 → stdout 결정 JSON(없으면 빈 출력) · exit 0
  --self-test                합성 입력 77 케이스 — `PASS <case>` 줄
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
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

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
LESSON = re.compile(r"fz-|F-\d{3}")                # fz-findings 는 fz- 에 든다(F-565 — 셋째 대안은 죽은 대안이었다)
LINK_OR_CODE = re.compile(r"\[[^\]\n]*\]\([^)\n]*\)|`[^`\n]*`")   # F-565 — 링크 · 백틱 안의 스킬 이름은 교훈이 아니다
WORKDIR_NAME = re.compile(r"^(?:[A-Z]{2,6}-\d{2,5}|NOTASK-\d{8})$")   # modules/context-artifacts.md Work Dir Resolution
REVIEW_SKILLS = {"fz-review", "fz:fz-review"}
GPT_CALL = re.compile(r"gpt-call\.sh['\"]?\s+(?:independent-)?review\b")
GPT_MARK = re.compile(r"\[외부:\s*GPT\]|\[GPT 미사용")
# Bash 쓰기 판별(F-119) — 따옴표 문자열 · heredoc 본문은 데이터라 지우고 본다
QUOTED = re.compile(r"'[^'\n]*'|\"(?:\\.|[^\"\\\n])*\"")
HEREDOC = re.compile(r"(?<!<)<<-?\s*(['\"]?)([A-Za-z_][\w-]*)\1")
INTERP_HEREDOC = re.compile(r"(?:^|[|;&(\s])(?:python3?|node|bash|sh|zsh|perl|ruby)\b[^|;&\n]*(?<!<)<<-?(?!<)")
REDIRECT = re.compile(r"(?<![<>&=\\-])(?:\d|&)?>>?\|?[ \t]*([^\s;&|()<>]+)")    # `\>` 는 test 의 문자열 비교다
# `[[ a > b ]]`(문자열 비교) · `(( n > 0 ))` · `$(( … ))`(산술) 안의 `>` 는 리다이렉트가 아니다 — 지우고 본다.
# ⛔ 홑대괄호 `[ $a > $b ]` 는 bash 에서 진짜 리다이렉트(파일 $b 생성)라 지우지 않는다
TEST_EXPR = re.compile(r"\[\[.*?\]\]|\$?\(\(.*?\)\)", re.S)   # 여러 줄 `[[ … ]]` 도 한 덩어리다


def _neutral_test(m) -> str:
    """비교식 · 산술식 안의 `<` `>` 만 지운다 — 그 안에서 **실행되는** 명령 치환(`$(…)` · 백틱)의 리다이렉트는 남긴다
    (`[[ $(printf x > f) == x ]]` 는 파일을 만든다)."""
    s = m.group(0)
    k = 3 if s.startswith("$((") else 2            # 여는 `[[` · `((` · `$((` 자체는 치환이 아니다
    out, depth, tick, i = [s[:k]], 0, False, k
    while i < len(s):
        ch = s[i]
        if s.startswith("$(", i) and not s.startswith("$((", i):
            depth += 1
            out.append("$(")
            i += 2
            continue
        if ch == "`":
            tick = not tick
        elif ch == "(" and depth:
            depth += 1                             # 치환 안의 서브셸 `$( (…) > f)` — 닫는 괄호를 짝지어 센다
        elif ch == ")" and depth:
            depth -= 1
        elif ch in "<>" and not depth and not tick:
            ch = " "
        out.append(ch)
        i += 1
    return "".join(out)
TEE = re.compile(r"(?:^|[|;&(])\s*tee\b([^|;&\n]*)")
SED = re.compile(r"(?:^|[|;&(\s])sed\s+([^|;&\n]*)")
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


def exempt(path: str, env, cwd) -> bool:
    return in_registry(path, env) or workdir_index(path, cwd)


def _keep_subs(m) -> str:
    """따옴표 문자열은 데이터라 지운다 — 단 큰따옴표 안의 `$( )` · 백틱은 실행되는 코드라 남긴다(`"$(printf x > f)"` 는 파일을 만든다)."""
    s = m.group(0)
    if s[0] != '"':
        return "''"
    subs, i = [], 0
    while i < len(s):
        if s.startswith("$(", i):
            depth, j = 1, i + 2
            while j < len(s) and depth:
                depth += {"(": 1, ")": -1}.get(s[j], 0)
                j += 1
            subs.append(s[i:j])
            i = j
        elif s[i] == "`":
            j = s.find("`", i + 1)
            j = len(s) if j < 0 else j + 1
            subs.append(s[i:j])
            i = j
        else:
            i += 1
    return "''" + "".join(" " + x for x in subs)


def _command_lines(cmd: str) -> list:
    """heredoc 본문을 뺀 명령 줄 — 본문은 데이터라 '>' 가 있어도 리다이렉트가 아니다."""
    lines, out, i = cmd.split("\n"), [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC.finditer(line):
            while i < len(lines) and lines[i].strip() != m.group(2):
                i += 1
            i += 1
    return out


GPT_WRAPPERS = {"bash", "sh", "zsh", "exec", "command", "env", "nohup", "time"}
SHELL_OPS = {";", "&&", "||", "|", "&", "(", ")", "{", "}", "!", "|&"}


def gpt_review_invoked(cmd) -> bool:
    """명령 자리에서 `gpt-call.sh review | independent-review` 를 실행하는가(F-094).

    grep · echo 인자나 heredoc 본문에 든 언급은 호출이 아니다 — 문자열 검색으로 세면 읽기만 한 턴이 GP 계약을 통과한다.
    셸 토큰으로 나눠 명령 시작 자리(맨 앞 · 연산자 뒤)의 첫 단어만 본다. 환경 접두(`VAR=값`)와 래퍼(bash · env …) · 래퍼 옵션은 건너뛴다.
    `( … )` · `$( … )` 이 닫히면 열기 전 자리로 돌아간다(`printf x $(…) gpt-call.sh` 의 gpt-call.sh 는 인자) · 인자 자리의 `!` 는 단어다.
    토큰화가 실패하면(짝 안 맞는 따옴표) 예전 문자열 판정으로 돌아간다.
    """
    if not isinstance(cmd, str) or "gpt-call" not in cmd:
        return False
    quoted = []                                    # 따옴표 문자열은 자리표시로 가린다 — 안의 `;` · `|` 는 연산자가 아니다

    def hide(m):
        quoted.append(m.group(0)[1:-1])
        return f"__fzq{len(quoted) - 1}__"

    text = QUOTED.sub(hide, "\n".join(_command_lines(cmd))).replace("\n", " ; ")
    try:
        lx = shlex.shlex(text, posix=True, punctuation_chars=True)
        lx.whitespace_split = True
        toks = list(lx)
    except ValueError:
        return bool(GPT_CALL.search(cmd))
    word = lambda tok: re.sub(r"__fzq(\d+)__", lambda q: quoted[int(q.group(1))], tok)
    start, wrapped, stack = True, False, []
    for i, tok in enumerate(toks):
        if tok == "(":                             # 서브셸 · 치환 안은 명령 자리 — 닫히면 열기 전 자리로 돌아간다
            stack.append(start)
            start, wrapped = True, False
            continue
        if tok == ")":
            start, wrapped = (stack.pop() if stack else False), False
            continue
        if tok == "!":                             # 명령 자리의 `!` 만 부정 연산자 — 인자 자리면 그냥 단어다(자리를 바꾸지 않는다)
            continue
        if tok in SHELL_OPS:
            start, wrapped = True, False
            continue
        if not start:
            continue
        if wrapped and tok.startswith("-"):
            continue                               # 래퍼 옵션(`bash -e` · `time -p`)
        if re.match(r"^\w+=", tok) or os.path.basename(word(tok)) in GPT_WRAPPERS:
            wrapped = wrapped or not re.match(r"^\w+=", tok)
            continue                               # 접두 · 래퍼 — 다음 단어가 아직 명령 자리다
        start = False
        if os.path.basename(word(tok)) == "gpt-call.sh" and i + 1 < len(toks) and word(toks[i + 1]) in ("review", "independent-review"):
            return True
    return False


def bash_write(cmd) -> tuple:
    """(쓰는가, 대상 경로 목록). 대상을 모르면(인터프리터 heredoc · sed -i · 따옴표 경로) 목록이 비어 면제 판정을 하지 않는다.

    보는 꼴(F-119): 리다이렉트(`>` · `>>` · `&>` — fd 복제 `2>&1` 과 /dev/null 류 제외) · tee · sed -i ·
    인터프리터(python · node · 셸 · perl · ruby)에 먹인 heredoc — 이 세션들이 승인 전 쓰기에 실제로 쓴 모양이다.
    ponytail: cp · mv · rm · touch · git apply · `python3 -c` 안의 쓰기는 보지 않는다 — 재발이 관측되면 꼴을 더한다
    """
    if not isinstance(cmd, str) or not cmd.strip():
        return False, []
    # 비교식은 줄을 넘을 수 있어 이어 붙인 뒤 본다 · `\\` 짝은 글자 하나라 먼저 지운다(`\\>` 는 진짜 리다이렉트, `\>` 는 글자)
    text = TEST_EXPR.sub(_neutral_test, "\n".join(QUOTED.sub(_keep_subs, ln) for ln in _command_lines(cmd))).replace("\\\\", "  ")
    lines = text.split("\n")
    targets, unknown = [], any(INTERP_HEREDOC.search(ln) for ln in lines)
    for m in REDIRECT.finditer(text):
        targets.append(m.group(1))
    for m in TEE.finditer(text):
        targets += [a for a in m.group(1).split() if not a.startswith("-")]
    for m in SED.finditer(text):
        if any(re.match(r"^-[A-Za-z]*i|^--in-place", a) for a in m.group(1).split()):
            unknown = True
    targets = [t for t in targets if t not in QUIET]
    if "''" in targets:                            # 따옴표로 준 경로 — 무엇인지 모른다
        unknown = True
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
        if MEMORY_PATH.search(p) and LESSON.search(text):
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
            writes, targets = bash_write(cmd)
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
    if inp.get("hook_event_name") == "PreToolUse" and inp.get("tool_name") == "Bash":
        ti = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
        cmd = ti.get("command")
        if not isinstance(cmd, str) or not (bash_write(cmd)[0] or gpt_review_invoked(cmd)):
            return "", ""                          # ⛔ 읽는 Bash 는 상태를 열지 않는다 — 모든 세션의 모든 Bash 에 잠금 · 저장이 붙지 않게
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
                 "cat <<'EOF'\nprint(1 > 0)\nEOF", "sed -n 1,5p a.swift", "echo x | tee /dev/null", "python3 -c 'print(1>0)'",
                 "awk -F'\\t' '$1>3' f.tsv", "cmd --flag=x 2>&1 | grep -v '=>'"]
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
