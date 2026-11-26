#!/usr/bin/env python3
"""fz-guard — fz 규칙 셋을 도구 호출 자리에서 기계로 강제하는 classic command 훅 (표준 라이브러리만).

규칙
  P4  F-368 · F-384 · F-451 · F-119 · F-553 — `/fz`(또는 Skill fz) 호출 뒤 Phase 4 승인 전에는 쓰기 도구 · Workflow ·
      쓰는 Bash(리다이렉트 · tee · sed -i · 인터프리터 heredoc)를 deny 한다. 레지스트리 entries/ 와 Phase 0 의
      WORK_DIR 초기화({cwd}/{티켓 · NOTASK-날짜[-이름]}/index.md)는 막지 않는다.
      승인 = AskUserQuestion 의 header 가 'Phase 4' 인 질문에 제시한 선택지 라벨(커스텀 · 취소류 제외)로 답한 것.
      창은 연 prompt 안에서만 판정한다 — 승인 없이 그 턴을 끝내면 Stop 을 1회 막는다. 셋 다 interactive(entrypoint=cli)에서만 발화한다.
      질문 없이 긴 답(LONG_ANSWER 자 이상)으로 끝낸 턴은 Stop 에 경고를 따로 싣는다(F-451 · 차단 아님).
  AG  F-058 · F-119 — fz 세션 표지(/fz · /fz-* · /fz:* · Skill fz*)가 선 세션에서 Agent · Task 의 subagent_type 이
      채택 목록 · Lead 가 직접 띄우는 fz 에이전트 목록(modules/native-agents.md 두 표 — 접두 포함 이름 완전 일치) 밖이면 경고한다
      (systemMessage · 막지 않는다 · prompt · 에이전트 종류마다 1회).
  FR  F-518 · F-565 — 같은 prompt_id 에서 메모리에 fz 교훈을 쓰고 레지스트리 entries/F-*.md 가 이 턴에 쓰이지 않았으면 Stop 을
      1회 막는다. 쓰기 도구의 성공 기록이 없으면 FZ_FINDINGS_ROOT/entries/ 항목의 파일 시각(턴 시작 이후)으로 한 번 더 본다 — 스크립트 ·
      Bash 리다이렉트로 쓴 항목도 센다. FZ_FINDINGS_ROOT 가 없으면 FR 은 돌지 않는다(레지스트리를 가진 머신만 켠다).
      ponytail: 다른 세션이 같은 때 쓴 항목도 이 턴 기록으로 센다.
      교훈 토큰은 마크다운 링크 · 백틱을 지운 본문에서 찾는다(링크만 든 MEMORY.md 는 교훈이 아니다).
      F-708 — fz 세션에서 PR 코멘트 · 리뷰를 가져온 턴(`gh api …/pulls|issues/N/comments|reviews` · `gh pr view --comments` ·
      GitHub MCP 코멘트 · 리뷰 읽기)이 레지스트리 쓰기도 'finding 해당 없음' 줄도 없이 끝나도 같은 조건으로 1회 막는다.
  GP  F-094 · F-297 — fz-review 를 부른 턴이 GPT 리뷰 호출도 '[외부: GPT]' · '[GPT 미사용 — 사유]' 줄도 없이 끝나면 Stop 을
      1회 막는다(interactive 한정). fz 플러그인 파일에 옛 모델 호칭을 넣는 쓰기는 모드와 무관하게 deny 한다 —
      판별식은 그 저장소의 scripts/check_gpt_surface.py 를 불러 그대로 쓴다(못 부르면 이 판정만 건너뛴다).
      /fz 창이 연 prompt 에서 skills/fz-review/SKILL.md 를 Read 해 도는 fz-review 도 리뷰 턴이다(PostToolUse Read ·
      다른 경로 Read 는 상태를 열기 전에 돌아간다 — 모든 Read 에 훅이 붙는 비용을 잠금 · 저장 0 으로 둔다).
  보호 경로 F-024 — env FZ_GUARD_PROTECTED(os.pathsep 구분) · <상태 폴더>/protected(줄마다 경로 · # 주석) 가 있으면 그 아래에서
      도는 Bash(cwd · `git -C` · 경로 인자)와 대상을 모르는 Bash(못 읽는 명령 · 확장이 든 cd · pushd · git -C 대상)를 ask 한다
      (거부 아님 · 사유 표시 · P4 deny 를 덮지 않는다). 기본은 비어 있어 아무 일도 하지 않는다 · 상태 파일을 열지 않는다.
  T-pitfall F-610 · F-654 · F-673 · F-727 — 적어 둔 셸 함정 꼴이 든 Bash 에 경고한다(systemMessage · 막지 않는다 · prompt · 꼴마다 1회):
      근거 명령(grep 류 · rg · find · git grep) 뒤 칸의 `| head` · 지금 아무것도 맞추지 않거나 펼침을 품은 따옴표 밖 글롭(zsh 는 무매칭이면
      명령 전체를 끊는다) · 서브셸 밖 `cd X &&`(세션 작업 폴더가 바뀐다). 꼴 판정(pitfall_hits)은 상태 · 잠금 없이 읽기 Bash 조기 반환 앞에서
      돌고, 맞은 명령만 끄기 판정 · 잠금 · 상태 경로로 간다. 규칙 이름이 따로 없다 — FZ_GUARD_DISABLE=all(네 규칙 전부)일 때 꺼진다.
      못 읽는 명령은 판정 불가 = 경고 없이 통과다.

상태 정리(F-564) — UserPromptSubmit 마다 마지막 기록이 STALE_DAYS 지난 다른 세션의 상태 · 잠금을 지운다(사건 1회에 최대 PRUNE_MAX).

사건은 훅 입력에서 상태로 기록한다 — ⛔ transcript 는 비동기로 기록돼 현재 사건이 아직 없을 수 있다(공식 훅 문서).
transcript 에서는 굳은 사실 하나만 읽는다: 첫 줄들의 entrypoint(cli=interactive · sdk-cli=headless · 그 밖=불명).

상태   ${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/<session_id>.json — 세션별 잠금(<session_id>.lock · fcntl.flock)으로
       읽기 · 병합 · 판정 · 저장을 직렬화하고 mkstemp + os.replace 로 원자 교체한다. 플러그인 폴더 안이면 쓰지 않는다
끄기   env FZ_GUARD_DISABLE=P4,AG,FR,GP|all · 파일 플래그 <상태 폴더>/disable(내용 = 규칙 목록 · 비면 all) — 매 실행 확인
실패   ⛔ 입력 · 의존성 · 잠금 · 상태 오류는 전부 exit 0 · 결정 없음(fail-open). 진단은 stderr `fz-guard diag:` 로만 낸다

모드
  (인자 없음)                훅 — stdin JSON 하나 → stdout 결정 JSON(없으면 빈 출력) · exit 0
  --self-test                합성 입력 153 케이스 — `PASS <case>` 줄
  --check-allowlist FILE     native-agents.md 채택 표 == ALLOW_AGENTS · Lead 직접 표 == LEAD_DIRECT_AGENTS 인가
                             (0 일치 · 1 불일치 — Lead 직접 표 없음 포함 · 2 채택 표 없음)
  --make-synthetic BYTES OUT --with-marker|--no-marker   큰 transcript 합성(첫 줄들에 entrypoint 를 둘지)
  --bench FILE               entrypoint 판정 소요 — `mode=<…> elapsed_ms=<n>`
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import glob
import importlib.util
import io
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
# 서버 이름은 사용자가 등록한 이름이라(xcode · Xcode · plugin_<이름>_<서버> …) 묻지 않고 도구 이름으로 판정한다.
#   hooks.json 두 matcher 도 같은 꼴이다 — 가변 자리는 `.*` 만 쓴다(scripts/check_rule_copies.py `_expand` 가 펼친다)
XCODE_WRITE = re.compile(r"^mcp__.*__Xcode(Write|Update|MV|RM|MakeDir)$")
AGENT_TOOLS = {"Agent", "Task"}
# modules/native-agents.md 채택 표와 같아야 한다 — `--check-allowlist` 가 대조한다(health-check 5.2)
ALLOW_AGENTS = {"pr-review-toolkit:silent-failure-hunter", "pr-review-toolkit:type-design-analyzer", "pr-review-toolkit:code-simplifier"}
# 스킬이 Lead 에게 Agent 도구로 직접 띄우라고 적은 읽기 전용 fz 에이전트(정의의 tools: 에 쓰기 도구가 없다) —
#   modules/native-agents.md 「fz 에이전트 — Lead 가 직접 띄우는 셋」 표와 같아야 한다(`--check-allowlist` 가 대조한다)
LEAD_DIRECT_AGENTS = {"fz:review-correctness", "fz:search-pattern", "fz:memory-curator"}
LEAD_TABLE_HEADER = "Lead 가 띄우는 때"
PHASE4_HEADER = "Phase 4"
NOT_APPROVAL = re.compile(r"커스텀|취소|거절|중단|cancel|reject|abort", re.I)
# F-565 — F-ID 는 그 자체로 교훈 기록이다. fz 이름(fz-findings 포함)만 든 본문은 교훈 단서어가 함께 있어야 교훈이다 — 스킬 이름 ·
#   경로를 적은 토픽 파일마다 Stop 을 1회 막던 오탐을 줄인다. ponytail: 단서어 없이 적은 fz 교훈은 놓친다(1회 알림 상실) — 놓친 사례가
#   나오면 그 낱말을 LESSON_CUE 에 더한다(F-518 원래 사례 '교훈 · 미뤘다' 는 셀이 지킨다)
FINDING_ID = re.compile(r"F-\d{3}")
FZ_NAME = re.compile(r"fz-")
LESSON_CUE = re.compile(r"교훈|놓[쳤친치]|결함|실패|오탐|누락|회귀|버그|틀렸|잘못|빠뜨|미뤘|lesson|missed|defect|regress|bug", re.I)
LINK_OR_CODE = re.compile(r"\[[^\]\n]*\]\([^)\n]*\)|`[^`\n]*`")   # F-565 — 링크 · 백틱 안의 스킬 이름은 교훈이 아니다
# modules/context-artifacts.md Work Dir Resolution — 같은 날 다른 작업은 NOTASK-날짜 뒤에 짧은 이름을 붙인다(빈 접미 · 하이픈 머리는 아니다)
WORKDIR_NAME = re.compile(r"^(?:[A-Z]{2,6}-\d{2,5}|NOTASK-\d{8}(?:-[A-Za-z0-9][A-Za-z0-9._-]{0,63})?)$")
REVIEW_SKILLS = {"fz-review", "fz:fz-review"}
PEER_SKILLS = {"fz-peer-review", "fz:fz-peer-review"}   # F-708 면제 — 기존 스레드 대비 독립 발견은 렌더러 표(F-643)가 잰다
REVIEW_SKILL_FILE = re.compile(r"(^|/)skills/fz-review/SKILL\.md$")   # F-094 — /fz 안에서 Read 로 도는 fz-review
PEER_SKILL_FILE = re.compile(r"(^|/)skills/fz-peer-review/SKILL\.md$")   # F-708 면제 — /fz 안에서 Read 로 도는 fz-peer-review(리뷰 M4)
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
ENTRY_SCAN = 5000                                 # F-518 — Stop 이 entries/ 에서 보는 이름 수 상한(훅 시간 제한 10초)
MTIME_SLACK = 1.0                                 # F-518 — 초 단위로 잘리는 파일 시각을 턴 시작과 견줄 때의 여유(초)

WARN_UNDECIDED = "FZ-GUARD-WARN P4-UNDECIDED"
WARN_INCOMPLETE = "FZ-GUARD-WARN STATE-INCOMPLETE"
WARN_LONG = "FZ-GUARD-WARN P4-LONG-ANSWER"
WARN_PITFALL = "FZ-GUARD-WARN T-PITFALL"
PITFALL_EVIDENCE = frozenset(("grep", "egrep", "fgrep", "rg", "ag", "ack", "find"))   # 근거를 찾는 명령 — `git grep` 은 하위 명령으로 본다
PITFALL_GLOB = re.compile(r"[*?\[]")
PITFALL_TEXT = {   # 꼴 → 경고 한 마디(%s = 그 명령의 근거 낱말) — 처방은 Coverage Gate 5항 · F-673 · F-654 와 같다
    "head": "`%s … | head` 는 근거 목록을 잘라 전수로 읽힌다 — 자르지 말고 개수(`wc -l`)를 먼저 본다(F-727 ②)",
    "glob": "글롭 `%s` 가 맞출 파일이 없을 수 있다 — zsh 는 무매칭이면 명령 전체를 끊는다 · 있을지 모르는 경로는 `find … -name` 으로 찾는다(F-673 · F-727 ③)",
    "cd": "`%s &&` 는 세션 작업 폴더를 바꾼다 — 절대 경로 · 도구의 폴더 인자(`git -C`) · `( cd … && … )` 로 쓴다(F-610 · F-654)",
    "shared-rm": "`rm … %s` 는 공용 임시 폴더를 글롭으로 지운다 — 다른 세션이 쓰는 같은 이름 폴더까지 지운다 · 내가 만든 경로(mktemp 가 돌려준 값)만 지우고, GPT 격리 폴더는 `gpt_independent.sh cleanup --iso <폴더>` 로 지운다(F-640)",
    "tracked-census": "`%s` 의 개수 · 파일 목록은 추적 파일만 센다 — 커밋하지 않은 새 파일이 있는 트리면 `--untracked` 를 붙이고, 수를 알릴 때 센 집합(추적만 · 미추적 포함)을 함께 적는다(F-611)",
    "subscript": "zsh 는 `%s[` 를 배열 첨자로 읽는다(`\"$f[^0-9]\"` → bad math expression · 0건처럼 보인다) — 변수 뒤에 글자를 붙일 때는 `${…}` 로 감싼다(F-745 ①)",
}
SHARED_TMP = re.compile(r"""^["']?(?:/tmp/|/private/tmp/|/var/folders/|\$\{?TMPDIR\}?/?)""")   # F-640 — 여러 세션이 함께 쓰는 임시 폴더
# F-745 ① — 작은따옴표 밖 `$이름[` (중괄호 없는 변수 바로 뒤 `[`) — zsh 배열 첨자. `${이름}[` · `${a[1]}` · `$((…))` 는 걸리지 않는다
ZSH_SUBSCRIPT = re.compile(r"(?<!\\)\$[A-Za-z_][A-Za-z0-9_]*\[")
P4_DENY = ("fz-guard P4 (F-368): this session ran /fz and the Phase 4 approval has not been given. Show the pipeline and ask "
           "the user with AskUserQuestion (header 'Phase 4') before writing files or starting a Workflow. Writes to the "
           "fz-findings registry entries/ are allowed. Autonomous runs start the CLI with FZ_AUTONOMY=autonomous.")
P4_STOP = ("fz-guard P4 (F-368): /fz ran in this session but the turn is ending without the Phase 4 approval. Ask the user "
           "with AskUserQuestion (header 'Phase 4' - options = the pipeline choices) before going on.")
FR_STOP = ("fz-guard FR (F-518): this turn wrote an fz lesson to a memory file but wrote no registry entry "
           "(fz-findings/entries/F-*.md). Record the finding in the registry this turn, or state in the reply why it is not one.")
PC_STOP = ("fz-guard FR (F-708): this fz turn read PR comments or reviews but wrote no registry entry (fz-findings/entries/F-*.md). "
           "A comment you judged correct that your own checks missed is a finding - record it this turn, or write the line "
           "'finding 해당 없음 — <reason>' in the reply.")
# F-708 — PR 코멘트 · 리뷰를 읽는 명령 · 도구(읽기만 — 같은 경로의 게시(-X POST · --input · 필드)는 pr_comment_reads 가 뺀다)
PR_COMMENTS = re.compile(r"\bgh\b[^|;&\n]*?\b(?:api\b[^|;&\n]*?(?:pulls|issues)/\d+/(?:comments|reviews)\b"
                         r"|pr\s+view\b[^|;&\n]*(?:--comments\b|--json\b[^|;&\n]*\b(?:comments|reviews)\b))")   # 1차 거르기 — 판정은 pr_comment_reads
PR_COMMENT_TOOLS = re.compile(r"^mcp__.*github.*__get_pull_request_(?:comments|reviews)$")
NO_FINDING = re.compile(r"finding\s*해당\s*없음")


def peer_prs(st: dict, sid: str, text) -> None:
    """피어 리뷰 명령 인자(`/fz-peer-review 1234` · Skill args)의 PR 번호를 지문에 미리 올린다 — 남의 PR 이라 F-708 이 묻지 않는다."""
    if not isinstance(text, str):
        return
    m = re.search(r"<command-args>(.*?)</command-args>", text, re.S)
    for n in re.findall(r"(?:^|[\s#/])(\d{1,6})(?=$|[\s,])", m.group(1) if m else text):
        fp = f"{sid}:PC:pr{n}"
        if fp not in st["fingerprints"]:
            st["fingerprints"].append(fp)


def mark_pr_comments(turn: dict, nums) -> None:
    """F-708 — 이 턴이 읽은 PR 번호를 모은다. 번호를 못 읽으면 "?" — Stop 이 (세션, PR) 마다 한 번만 묻는다(같은 PR 을 다시 읽는 턴은 묻지 않는다)."""
    have = turn.get("prComments") if isinstance(turn.get("prComments"), list) else []
    turn["prComments"] = sorted(set(have) | ({str(n) for n in nums if n} or {"?"}))
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


def entry_since(env, since, limit=ENTRY_SCAN) -> bool:
    """FR(F-518) — FZ_FINDINGS_ROOT/entries/ 에 턴 시작(since) 뒤 고쳐진 항목(F-NNN….md)이 있는가. 쓰기 방법(쓰기 도구 · 스크립트 ·
    Bash 리다이렉트)과 무관하게 파일 시각으로 본다. 턴 시작을 모르거나 entries/ 를 못 열면 False — 기록을 볼 수 없으니 막는다(루트가 없으면
    on_stop 이 FR 을 돌리지 않는다 — 여기 루트 검사는 직접 부를 때의 방어다).
    시각을 못 읽는 항목(깨진 링크 등) 하나는 건너뛰고 뒤 항목을 계속 본다 — 그 항목 때문에 이 턴에 쓴 항목을 놓치지 않는다.
    ponytail: 다른 세션이 같은 때 쓴 항목도 이 턴의 기록으로 센다(거짓 통과 — FR 은 1회 알림이라 거짓 차단이 더 방해된다) ·
    앞 limit 개 이름만 본다(넘으면 못 본 항목은 기록 없음 — 거짓 차단 1회)"""
    root = env.get("FZ_FINDINGS_ROOT")
    if not root or not isinstance(since, (int, float)):
        return False
    try:
        with os.scandir(os.path.join(os.path.expanduser(root), "entries")) as it:
            for i, e in enumerate(it):
                if i >= limit:
                    break
                try:
                    if ENTRY_NAME.match(e.name) and e.stat().st_mtime >= since - MTIME_SLACK:
                        return True
                except OSError:
                    continue
    except OSError:
        return False
    return False


def workdir_index(path: str, cwd) -> bool:
    """F-553 — /fz Phase 0 의 WORK_DIR 초기화는 Phase 4 보다 먼저다: {cwd}/{티켓 · NOTASK-날짜[-이름]}/index.md 만 허용한다."""
    if not isinstance(cwd, str) or not cwd:
        return False
    base = os.path.normpath(os.path.abspath(os.path.expanduser(cwd)))
    p = os.path.normpath(os.path.join(base, os.path.expanduser(path)))   # ⛔ `..` 를 접은 뒤 판정한다
    d = os.path.dirname(p)
    return os.path.basename(p) == "index.md" and bool(WORKDIR_NAME.match(os.path.basename(d))) and os.path.dirname(d) == base


def workdir_dir(path: str, cwd) -> bool:
    """F-553 — Phase 0 의 WORK_DIR 폴더 {cwd}/{티켓 · NOTASK-날짜[-이름]} 그 자체. mkdir 대상으로만 면제한다(rm 대상은 면제가 아니다)."""
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


PR_ENDPOINT = re.compile(r"(?:^|/)(?:pulls|issues)/(\d+)/(?:comments|reviews)(?:$|[/?])")


def pr_comment_reads(cmd):
    """명령 자리에서 PR 코멘트 · 리뷰를 읽는 gh 호출의 PR 번호 목록(번호를 못 읽으면 "?") · 없으면 None (F-708).
    `gh api …/pulls|issues/N/comments|reviews` · `gh pr view [N] … --comments` 만 센다 — echo · grep 인자나 heredoc 본문의 언급은 읽기가 아니다
    (GPT 리뷰 P2). ⛔ 못 읽으면(표 밖 꼴 · 토크나이저 없음) 읽기가 아니다 — 막는 규칙이라 보수 쪽은 '안 막음' 이다."""
    if not isinstance(cmd, str) or "gh" not in cmd or shell_tokens is None or not PR_COMMENTS.search(cmd):
        return None
    cmds = shell_tokens.commands(shell_tokens.lex(cmd), shells=True)
    if shell_tokens.is_unknown(cmds):
        return None
    got = []
    for c in cmds:
        if c.name is None or c.deferred or c.unsure or os.path.basename(c.name.text) != "gh":
            continue
        a = [w.text for w in c.args]
        while len(a) >= 2 and a[0] in ("-R", "--repo"):
            a = a[2:]
        if a[:1] == ["api"]:
            writes = any(w in ("--input", "-f", "-F", "--field", "--raw-field") or w.startswith(("--field=", "--raw-field=", "--input="))
                         for w in a) or any(x in ("-X", "--method") and y.upper() != "GET" for x, y in zip(a, a[1:])) \
                or any(w.startswith("--method=") and w.split("=", 1)[1].upper() != "GET" for w in a)
            m = next((PR_ENDPOINT.search(w) for w in a[1:] if not w.startswith("-") and PR_ENDPOINT.search(w)), None)
            if m and not writes:                   # 게시(-X POST · --input · 필드)는 읽기가 아니다(리뷰 M4)
                got.append(m.group(1))
        elif a[:2] == ["pr", "view"] and ("--comments" in a or any(
                x == "--json" and re.search(r"\b(?:comments|reviews)\b", y) for x, y in zip(a, a[1:]))):
            got.append(next((w for w in a[2:] if w.isdigit()), "?"))
    return got or None


def _gpt_call_in(cmds) -> bool:
    return any(c.name is not None and not c.deferred and not c.unsure and os.path.basename(c.name.text) == "gpt-call.sh"
               and c.args and c.args[0].text in ("review", "independent-review") for c in cmds)


# ── 승인 전 창(P4)의 읽기 표 — 이름: True(어느 꼴이든 읽기) | 판정 함수(인자 → 읽기 꼴인가). ⛔ 표 밖 이름은 전부 대상 미상 쓰기다.
# 인터프리터(python · node · 셸 · perl · ruby)는 표에 없다 — 코드가 무엇을 쓰는지 읽지 않는다(쓰기 신호 표를 두지 않는다 · F-458).
# 판정 함수는 읽기 꼴만 받는다(허용 목록) — 쓰기 모드가 있는 명령(sed -i · sort -o · find -delete · git 쓰기 하위 명령 …)의 표 밖 꼴은 미상이다.
# 옵션은 따옴표와 무관하게 옵션이다(`'-i'` 도 프로그램에는 -i). 펼쳐지는 인자(`"$W/a"` · `$SHA`)는 값(경로 · 리비전 · 줄 번호)으로 본다 —
# ponytail: 펼친 값이 옵션이 되는 꼴(`X=--output=f; git diff $X`)은 만든 꼴이라 보지 않는다. 프로그램 · 하위 명령 자리의 펼침은 거절한다.
# 이 값 규칙은 print · PLUGIN_READ 의 gate_check.py 판정에는 없다 — 그 둘은 옵션이 설 수 있는 자리(print 는 `--` · 첫 글자 그대로의
# 피연산자 앞, gate_check.py 는 `--status` 뒤 원장 자리)의 펼침(따옴표 밖 중괄호 펼침 · 글롭 포함 — _literal_view)을 거절한다
_EXPANSION = re.compile(r"\$\{[^{}]*\}|\$\((?:[^()]|\([^()]*\))*\)|`[^`]*`|\$[A-Za-z_][A-Za-z0-9_]*|\$[0-9?#@*$!-]")


def _glob_pattern(raw: str):
    """단어 원문에서 따옴표 · 이스케이프 밖 글롭 문자가 있으면 glob 패턴(따옴표 안 글자는 escape), 없으면 None.
    `Word.quoted` 는 단어 일부만 따옴표여도 참이라(`"./dir/"*.md`) 단어 단위로는 따옴표 밖 글롭을 가르지 못한다."""
    out, q, i, live = [], None, 0, False
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw) and (q is None or (q == '"' and raw[i + 1] in '"\\$`')):
            out.append(glob.escape(raw[i + 1]))
            i += 2
            continue
        if q is None and ch in "'\"":
            q = ch
        elif q == ch:
            q = None
        elif q is None and ch in "*?[":
            live = True
            out.append(ch)
        else:
            out.append(glob.escape(ch))
        i += 1
    return "".join(out) if live else None


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


_AWK_RE_LEAD = frozenset("(,{};!~&|?:=\n")         # 이 글자(공백 제외) 뒤 '/' 는 정규식 리터럴의 시작이다 — 그 밖(나눗셈 · print 뒤)은 리터럴로 보지 않는다
                                                   # (그 '/' 뒤에 리터럴이 다시 열리면 경계를 정하지 못한다 — _awk_bare 가 원문을 돌려준다)


def _awk_open_class(body: str) -> bool:
    """정규식 본문(닫는 '/' 앞까지)이 대괄호 표현 안에서 끝나는가 — gawk 는 `[/]` 의 '/' 에서 정규식을 닫지 않는다. `[` 바로 뒤(`^` 다음 포함)의
    `]` 는 글자이고, 안의 `[:이름:]` · `[.x.]` · `[=x=]` 는 짝까지 건너뛴다(짝이 없으면 열린 것으로 본다)."""
    k, n, cls = 0, len(body), False
    while k < n:
        ch = body[k]
        if ch == "\\":
            k += 2
            continue
        if not cls:
            if ch == "[":
                cls, k = True, k + 1
                k += 1 if body[k:k + 1] == "^" else 0
                k += 1 if body[k:k + 1] == "]" else 0
                continue
        elif ch == "[" and body[k + 1:k + 2] in (":", ".", "="):
            e = body.find(body[k + 1] + "]", k + 2)
            if e < 0:
                return True
            k = e + 2
            continue
        elif ch == "]":
            cls = False
        k += 1
    return cls


def _awk_bare(s: str) -> str:
    """awk 프로그램에서 문자열 "…" 과 정규식 자리의 /…/ 를 `_` 하나로 바꾼 글 — `|` 판정만 이 글에 한다(system( · print > 는 원문에 한다).
    한 번의 왼→오 훑기다. 리터럴 안 역슬래시는 다음 글자를 감싸고, 닫는 따옴표 · '/' 가 같은 줄에 없으면 그 뒤를 지우지 않는다. 리터럴 밖
    역슬래시는 다음 글자와 함께 넘긴다(줄 이음 · 앞 글자를 바꾸지 않는다).
    ⛔ 경계를 정하지 못하면 원문을 그대로 돌려준다(옛 판정 — 원문의 `|` 하나라도 파이프): 나눗셈으로 본 '/' 뒤에 리터럴이 다시 열린다(그 '/' 가
    print · printf · return · 연산자 뒤 등 훑기가 모르는 자리의 정규식이면 안의 따옴표 · '/' 가 뒤의 진짜 파이프를 지운다) · 정규식 본문이
    대괄호 표현 안에서 끝난다(_awk_open_class — 구현마다 그 '/' 에서 닫는지가 다르다)."""
    out, prev, i, n, div = [], "", 0, len(s), False
    while i < n:
        c = s[i]
        if c == "\\":
            out.append(s[i:i + 2])
            i += 2
            continue
        if c == '"' or (c == "/" and (not prev or prev in _AWK_RE_LEAD)):
            if div:
                return s                           # 앞의 나눗셈 '/' 가 정규식이었다면 이 리터럴 경계는 틀린다
            j = i + 1
            while j < n and s[j] not in (c, "\n"):
                j += 2 if s[j] == "\\" else 1
            if j >= n or s[j] != c:
                return "".join(out) + s[i:]
            if c == "/" and _awk_open_class(s[i + 1:j]):
                return s                           # `[/]` — gawk 는 이 '/' 에서 닫지 않는다
            out.append("_")
            prev, i = "_", j + 1
            continue
        div = div or c == "/"
        out.append(c)
        prev = prev if c in " \t" else c
        i += 1
    return "".join(out)


def _awk_reads(args) -> bool:
    """awk — 프로그램이 펼쳐지지 않고 파이프(`|` — `||` · 문자열 · 정규식 자리 /…/ 안은 제외 · _awk_bare) · system( · print/printf 뒤 `>` 가 없다.
    -f · 표 밖 옵션은 거절."""
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
    s = args[i].text
    if "|" in _awk_bare(s).replace("||", "") or re.search(r"\bsystem\s*\(", s):
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


# 따옴표 · 이스케이프 밖이면 셸이 프로그램을 띄우기 전에 한 단어를 여러 낱말로 펴는 글자 — 중괄호 펼침(`{a,b}` · `{1..3}`)과 글롭(`*` · `?` · `[`).
#   토크나이저의 expands 는 매개변수 · 명령 · 산술 · 프로세스 치환만 센다
SPLITS = re.compile(r"[{*?\[]")


def _splits(w, src: str) -> bool:
    """단어에 따옴표 · 이스케이프 밖 SPLITS 글자가 있는가. 따옴표가 없는 단어는 글자로 바로 판정한다. 토크나이저의 quoted 는 단어 어딘가에
    따옴표가 있다는 표시뿐이라(`""{a,b}` 도 quoted) 따옴표가 든 단어는 원문 조각(src[start:end])을 인자 자리에서 다시 읽어 그 글자마다 따옴표
    구간인지 본다(shell_tokens.in_quotes). 원문 조각이 같은 단어로 다시 읽히지 않으면 편다고 본다 — 백틱 · heredoc 본문 안 단어의 좌표는 그 안 글
    기준이다."""
    if not SPLITS.search(w.text):
        return False
    if not w.quoted:
        return True
    raw = ": " + src[w.start:w.end]
    toks = shell_tokens.lex(raw)
    if shell_tokens.is_unknown(toks) or len(toks) != 2 or not isinstance(toks[1], shell_tokens.Word) or toks[1].text != w.text:
        return True
    return any(shell_tokens.in_quotes(raw, m.start()) is not True for m in SPLITS.finditer(raw))


def _literal_view(args, src: str) -> list:
    """옵션이 설 수 있는 자리에 글자 그대로의 단어만 받는 판정(zsh print · PLUGIN_READ 의 gate_check.py)에 넘길 인자 — 따옴표 밖 중괄호 ·
    글롭 단어(_splits)는 펼치는 단어(expands)로 바꾼다. 셸이 그 단어를 여러 낱말로 펴면 옵션 · 인자 수가 바뀐다(`print {-v,answer,hi}` →
    print -v answer hi · `--status {--set-state,active,gates/plan.md}` → 원장 대신 --set-state). PLUGIN_READ 의 하위 명령 글자 비교도 이것을
    받지만 표의 글자에 그 글자가 없어 결과가 같다. READ 의 다른 판정은 c.args 를 그대로 받는다(펼친 인자는 값이다 — 위 읽기 표 머리)."""
    return [w._replace(expands=True) if not w.expands and _splits(w, src) else w for w in args]


def _print_reads(args) -> bool:
    """zsh print — 옵션이 -r · -n · -l(묶음 포함) · -- 뿐이다. `--` 뒤 · 첫 글자 그대로의 피연산자부터는 값이다(뒤 펼침도 값).
    그 앞의 펼쳐지는 단어(`"$O"` · `${O}` · `$(…)` · 백틱 · `-$O` · 따옴표 밖 중괄호 · 글롭 `{-v,a}` · `*` — _literal_view)는 옵션이 될 수 있어
    거절한다(`O=-v` → 변수에 쓴다 · 빈 값은 사라진다).
    -s · -z · -u · -p · -S · -v 같은 표 밖 옵션 · 홀로 선 `-` 는 거절한다(히스토리 · 편집 버퍼 · 다른 fd 에 쓴다).
    세션 셸이 zsh 일 때만 읽기다 — 훅이 보는 신호는 SHELL 환경 변수의 basename 하나다(휴리스틱: Bash 도구가 실제로 띄우는 셸은 보지 못한다).
    그 밖(bash · sh · 빈 값 · 없음)이면 print 는 PATH 의 다른 프로그램일 수 있어(mailcap 의 print 동작 등) 표 밖 이름처럼 거절한다."""
    if os.path.basename(os.environ.get("SHELL") or "") != "zsh":
        return False
    for w in args:
        t = w.text
        if w.expands:
            return False
        if t == "--" or not t.startswith("-"):
            return True
        if not re.fullmatch(r"-[rnl]+", t):
            return False
    return True


READ = dict.fromkeys((
    "echo", "printf", "cat", "head", "tail", "grep", "egrep", "fgrep", "cut", "wc", "ls", "tr", "diff", "cmp", "comm", "paste", "column",
    "nl", "rev", "tac", "fold", "expand", "seq", "od", "hexdump", "strings", "basename", "dirname", "realpath", "readlink", "stat", "du",
    "df", "ps", "pgrep", "lsof", "which", "type", "pwd", "true", "false", ":", "test", "[", "[[", "jq", "shasum", "md5", "md5sum",
    "sha256sum", "cksum", "sleep", "wait", "cd", "pushd", "popd", "set", "unset", "export", "local", "declare", "typeset", "readonly",
    "read", "shift", "exit", "return", "break", "continue", "env", "printenv", "command", "xargs", "whoami", "id", "uname", "sw_vers",
    "mdfind", "mdls", "tput", "locale"), True)
READ.update({"sed": _sed_reads, "awk": _awk_reads, "find": _find_reads, "sort": _sort_reads, "uniq": _uniq_reads, "git": _git_reads,
             "gh": _gh_reads, "print": _print_reads,
             "rg": lambda a: not any(w.text == "--pre" or w.text.startswith("--pre=") for w in a),
             "date": lambda a: all(w.text.startswith("+") or (w.text.startswith("-") and not w.text.startswith(("-s", "--set"))) for w in a),
             "base64": lambda a: not any(w.text.startswith(("-o", "--output")) for w in a)})


# F-583 — 승인 전 창의 읽기 전용 Apple 도구(시뮬 · 빌드 요청의 사실 확인). 하위 명령 단위로만 받는다 — create · boot · install ·
#   io(스크린숏 파일) · -convert · -output 같은 쓰기 꼴은 표 밖이라 대상 미상 쓰기로 남는다. 인터프리터(python -c)는 그대로 막는다
SIMCTL_READ = {"list", "getenv", "get_app_container", "listapps"}


def _xcrun_reads(a) -> bool:
    if len(a) < 2 or a[0].expands or a[1].expands:
        return False
    if a[0].text == "devicectl":                  # list 도 -j/--json-output · -l/--log-output 이면 파일을 쓴다(GPT 리뷰 P1)
        return a[1].text == "list" and not any(w.expands or w.text in ("-j", "-l") or w.text.startswith(("--json-output", "--log-output"))
                                               for w in a[2:])
    return a[0].text == "simctl" and a[1].text in SIMCTL_READ


READ.update({"xcrun": _xcrun_reads,
             # 엔트리 제안 꼴만 받는다 — 꼴마다 실행 전후 무쓰기 대조를 남겼다(작업 폴더 fixwave/f583-nowrite.txt)
             "plutil": lambda a: len(a) == 2 and a[0].text == "-p",
             "vtool": lambda a: len(a) == 2 and a[0].text == "-show-build",
             "xcode-select": lambda a: len(a) == 1 and a[0].text == "-p",
             "xcodebuild": lambda a: len(a) == 1 and a[0].text == "-version"})
# 승인 전 창에서 부르는 플러그인 스크립트 — 읽기만 하거나 플러그인 자기 상태(~/.fz)만 쓴다. 이름: 받는 하위 명령(None = 전부) |
#   판정 함수(인자 → 읽기 꼴인가). gate_check.py 는 `--status <원장>`(파싱만 · CHECK 미실행)만 읽기다 — 다른 인자는 원장을 쓸 수 있다.
#   원장은 펼침(따옴표 밖 중괄호 펼침 · 글롭 포함) 없는 글자 그대로다(펼친 값은 옵션 하나 · 여럿이 될 수 있다) · 판정 함수 꼴은 앞에 환경 대입 · env 래퍼가 없을 때만(_plugin_reads)
PLUGIN_READ = {"gpt-choice.sh": {"get", "decide", "options"}, "autonomy_decide.py": None, "mode_gate.py": None, "intent_route_probe.py": None,
               "gate_check.py": lambda a: len(a) == 2 and a[0].text == "--status" and not a[1].expands and not a[1].text.startswith("-")}
MOVERS = {"cd", "pushd", "popd"}
# 대상이 보이는 쓰기 명령 — 받는 옵션 글자 묶음(값 받는 옵션 · 긴 옵션 · 표 밖 글자면 대상 미상) · `--` 뒤는 전부 대상
WRITE_ARGS = {"tee": "aip", "rm": "rfRivdPWx", "touch": "acmh", "mkdir": "pv", "cp": "RrfinpvacHLPXx", "mv": "finvh"}


def _plugin_reads(n: str, name, args, env_prefix=False) -> bool:
    """`bash …/scripts/gpt-choice.sh get` · `python3 …/scripts/mode_gate.py …` 처럼 PLUGIN_READ 의 스크립트를 부르는가 —
    스크립트 경로는 펼쳐져도 된다(`${FZ_PLUGIN_ROOT}`) · 마지막 두 마디(scripts/이름)와 하위 명령 글자(또는 그 이름의 판정 함수)로 가린다.
    판정 함수가 있는 이름(gate_check.py)은 env_prefix(앞에 `NAME=값` 대입 · env 래퍼)가 없을 때만 읽기다 — 그 스크립트는 환경 값
    `FZ_GATES_TRACE` 가 가리키는 파일에 호출 기록을 덧붙인다."""
    if re.fullmatch(r"python[0-9.]*|bash|sh|zsh", n):
        if not args:
            return False
        name, args = args[0], args[1:]
    script = name.text
    base = os.path.basename(script)
    if os.path.basename(os.path.dirname(script)) != "scripts" or base not in PLUGIN_READ:
        return False
    subs = PLUGIN_READ[base]
    if callable(subs):
        return not env_prefix and subs(args)
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


# 복합 명령을 여는 명령 자리 예약어 → 닫는 말 · 뒤가 아직 명령 자리인 예약어(shell_tokens 렉서의 명령 자리 규칙과 같은 표 — 렉서는 함수
# 정의를 이 자리에서만 읽는다). defined_functions 가 파이프라인 한 칸 · 목록의 범위를 가르는 데 쓴다(`( … )` 는 연산자 괄호다)
_SCOPE_OPEN = {"{": "}", "if": "fi", "while": "done", "until": "done", "for": "done", "select": "done"}
_SCOPE_LEAD = frozenset(("!", "{", "if", "then", "else", "elif", "do", "while", "until", "time"))


def defined_functions(toks) -> dict:
    """맨 바깥 셸에서 정의한 함수 — 이름 → 가장 이른 정의가 끝나는 위치(toks 와 같은 좌표). 이름만 필요하면 키를 쓴다.
    맨 바깥 = toks 에 바로 놓인 정의 중 bash 가 서브셸에서 돌리지 않는 자리다. 서브셸 자리는 셋이다 — `( … )` 괄호 안 · 두 명령 이상
    파이프라인(`|` · `|&`)의 한 칸 · `&` 로 끝난 목록(`a && b &` 는 목록 전체). 그 칸이 묶음 `{ …; }` · if · while · until · for 면 그 안
    전부가 서브셸이다. 치환(`$(…)` · 백틱 · heredoc 본문 치환 · `<(…)`) · 서브셸 안 정의는 그 셸이 끝나면 사라져 밖의 호출에 닿지 않고,
    함수 본문 안 정의는 그 함수가 불려야 생긴다 — 모두 넣지 않는다(보수 판정: 같은 치환 · 서브셸 · 파이프라인 칸 · 본문 안 호출도 면제하지
    않는다). 지금 셸의 정의도 늘 도는 자리 — `&&` · `||` 목록의 첫 명령과 묶음 `{ …; }` 안 — 만 넣는다. `&&` · `||` 뒤와 if · while ·
    until · for 안(조건 목록 포함) 정의는 조건 · 반복 수에 따라 생기지 않을 수 있어 조건이 참이어도 넣지 않는다(과차단 쪽 — if · while
    조건 목록 안 정의는 늘 돌지만 넣지 않고, 같은 갈래 안 뒤 호출도 면제하지 않는다: `true && rm() { :; }; rm -rf build` ·
    `if true; then rm() { :; }; fi; rm -rf build` 는 쓰기다).
    예약어 짝이 맞지 않으면(닫는 말 없음 · 다른 닫는 말 · 짝 없는 `)`) 범위를 모르므로 아무것도 넣지 않는다."""
    # 칸마다 [닫는 말, 끝난 목록의 정의, 이 목록의 정의, 이 파이프라인의 정의, 파이프라인이 두 칸 이상, 이 목록이 `&&` · `||` 를 지났다]
    frames = [[None, [], [], [], False, False]]
    cmd_pos, after_time, joined = True, False, False

    def end_pipe(f):
        if not f[4] and not f[5]:
            f[2] += f[3]                       # 한 칸 파이프라인은 지금 셸에서 돈다 — `&&` · `||` 뒤 파이프라인은 조건이 돌지 않으면 돌지 않는다
        f[3], f[4] = [], False

    def end_list(f, background=False):
        end_pipe(f)
        if not background:
            f[1] += f[2]                       # `&` 로 끝난 목록은 서브셸이다 — 그 정의를 버린다
        f[2], f[5] = [], False

    def close(word):
        if frames[-1][0] != word:
            return False
        f = frames.pop()
        end_list(f)
        if word in ("fi", "done"):
            return True                        # if · 루프 — 조건 · 반복 수에 따라 돌지 않을 수 있어 그 안 정의를 버린다
        if word != ")":
            frames[-1][3] += f[1]              # 지금 셸에서 끝난 묶음 — 그 정의는 바깥 파이프라인의 한 칸에 놓인다
        return True
    for t in toks:
        if isinstance(t, shell_tokens.Op):
            if t.text == "\n" and joined:
                continue                       # `|` · `&&` · `||` 뒤 줄바꿈은 같은 명령을 잇는다
            if t.text in ("|", "|&"):
                frames[-1][4] = True
            elif t.text in ("&&", "||"):
                end_pipe(frames[-1])
                frames[-1][5] = True
            elif t.text == "(":
                frames.append([")", [], [], [], False, False])
            elif t.text == ")":
                if not close(")"):
                    return {}
            else:
                end_list(frames[-1], t.text == "&")   # ; ;; & 줄바꿈
            cmd_pos, after_time, joined = t.text != ")", False, t.text in ("|", "|&", "&&", "||")
            continue
        joined = False
        if isinstance(t, shell_tokens.Func):
            frames[-1][3].append(t)
            cmd_pos = after_time = False
        elif isinstance(t, shell_tokens.Word) and cmd_pos and not t.quoted:
            if t.text in _SCOPE_OPEN:
                frames.append([_SCOPE_OPEN[t.text], [], [], [], False, False])
            elif t.text in ("}", "fi", "done") and not close(t.text):
                return {}
            elif t.text in ("then", "else", "elif", "do"):
                end_list(frames[-1])
            keep = after_time and t.text.startswith("-")   # `time -p` 뒤는 아직 명령 자리다
            after_time, cmd_pos = t.text == "time" or keep, t.text in _SCOPE_LEAD or keep
        elif isinstance(t, shell_tokens.Word):
            cmd_pos = after_time = False
    if len(frames) > 1:
        return {}
    end_list(frames[0])
    kept, out = {id(t) for t in frames[0][1]}, {}
    for t in toks:
        if id(t) in kept:
            out[t.name] = min(out.get(t.name, t.end), t.end)
    return out


def _runs_at(toks) -> dict:
    """치환 안 단어(id) → 그 치환을 품은 맨 바깥 토큰의 시작 위치(toks 와 같은 좌표). 치환은 그 토큰의 명령이 돌 때 돌고 그 앞의 맨 바깥
    정의를 물려받는다 — 백틱 · heredoc 본문 치환 안 단어의 위치는 그 안 글자 기준이라 맨 바깥 정의 위치와 견줄 수 없다."""
    out = {}

    def walk(ts, at):
        for t in ts:
            ws, subs = shell_tokens.nested(t)
            out.update((id(w), at) for w in ws)
            for sub in subs:
                walk(sub, at)
    for t in toks:
        for sub in shell_tokens.nested(t)[1]:
            walk(sub, t.start)
    return out


def _deep(toks):
    """모든 깊이의 토큰 — 치환 · 리다이렉트 대상과 heredoc 본문 치환 · 함수 본문까지(shell_tokens.nested 를 따라 내려간다)."""
    for t in toks:
        yield t
        for sub in shell_tokens.nested(t)[1]:
            yield from _deep(sub)


def _self_calls(toks) -> set:
    """함수 F 의 본문(치환 · 중첩 함수 본문 포함) 안에서 글자가 F 의 이름인 단어(id) — 본문 안 맨 이름 자기 호출(재귀)은 F 가 불릴 때만 돌고
    그때 이름은 F 다. 명령 어딘가에 unset 단어가 있으면 빈 집합이다(정의를 지우면 자기 호출이 외부 명령이 된다)."""
    if any(isinstance(t, shell_tokens.Word) and t.text == "unset" for t in _deep(toks)):
        return set()
    return {id(t) for f in _deep(toks) if isinstance(f, shell_tokens.Func)
            for t in _deep(f.body) if isinstance(t, shell_tokens.Word) and t.text == f.name}


def _assigned(toks) -> set:
    """대입(`NAME=값`)을 앞에 둔 단어(id) — 같은 단순 명령(연산자 · 함수 정의 사이) 안에서 대입 단어 뒤에 오는 단어 · 모든 깊이."""
    out = set()

    def walk(ts):
        seen = False
        for t in ts:
            if isinstance(t, (shell_tokens.Op, shell_tokens.Func)):
                seen = False
            elif isinstance(t, shell_tokens.Word):
                if seen:
                    out.add(id(t))
                seen = seen or t.assign
            for sub in shell_tokens.nested(t)[1]:
                walk(sub)
    walk(toks)
    return out


def write_sites(cmd, fragment=False, known=()):
    """명령의 쓰기 자리 — [(대상 Word | None, Cmd)] · None 이면 못 읽었다(표 밖 꼴 · 토크나이저 없음).
    대상 None = 그 명령이 대상을 모르는 쓰기다(읽기 표 밖 이름 · 명령 자리 미상 · 펼쳐지는 명령 이름 · WRITE_ARGS 의 표 밖 옵션 · xargs 뒤).
    대상 Word 는 리다이렉트(`>` · `>>` · `>|` · `&>` · `<>` · fd 가 아닌 `>&`)와 WRITE_ARGS 명령(tee · rm · touch · mkdir · cp · mv)의 대상이다 —
    펼치지 않은 글자 그대로이고, 그 명령의 깊이 · 지연(함수 본문)은 Cmd 에 있다. 이 명령의 맨 바깥 셸에서 정의한 함수(defined_functions)의
    호출은 **정의 뒤에 있을 때만** 자리가 아니다(본문이 따로 나온다) — 정의보다 앞선 맨 이름 호출은 외부 명령이다(`rm -rf build; rm() { :; }`).
    치환 · 서브셸(파이프라인 칸 · `&` 목록 포함) 안 호출은 그 앞의 맨 바깥 정의를 물려받고(치환은 품은 맨 바깥 토큰 자리에서 돈다), 치환 ·
    서브셸 안 정의는 아무 호출도 면제하지 않는다(`(rm() { :; }); rm -rf build` · `rm() { :; } | rm -rf build` 는 쓰기다). 함수 본문 안 호출도
    이름과 무관하게(WRITE_ARGS 명령 · 그 밖 이름) 맨 바깥 호출과 같은 규칙이라 본문보다 앞의 맨 바깥 정의만 면제한다(`f() { rm -rf build; }; f; rm() { :; }`
    의 본문 rm 은 외부 명령이다). 뒤 정의는 감싼 함수를 그 뒤에 불러도 쓰기로 읽는다(과차단: `f() { g; }; g() { :; }; f`).
    본문 안 맨 이름 자기 호출(재귀)은 함수다 — 명령에 unset 이 있거나 command · 래퍼 · 경로로 부르면 외부 명령이다(_self_calls).
    조각만 넘길 때 `known` 은 그 조각 **앞에서** 맨 바깥 셸이 정의한 함수다 — 넘긴 쪽이 순서 · 범위를 걸렀다.
    ⛔ guard(P4)와 gate_stop_hook(원장 소유)이 같은 판정을 쓴다 — 한쪽만 고치면 두 판정이 갈린다."""
    if not isinstance(cmd, str) or shell_tokens is None:
        return None
    toks = shell_tokens.lex(cmd, fragment)
    cmds = shell_tokens.commands(toks)
    if shell_tokens.is_unknown(cmds):
        return None
    ends, runs_at, known, out = defined_functions(toks), _runs_at(toks), set(known), []
    selfc, assigned = _self_calls(toks), _assigned(toks)
    for c in cmds:
        out += [(r.target, c) for r in c.redirs if r.op in WRITE_OPS or (r.op == ">&" and not re.fullmatch(r"[0-9]+|-", r.target.text))]
        if c.unsure:
            out.append((None, c))                  # 명령 자리를 모른다(표 밖 래퍼 옵션 · 래퍼 뒤 대입 · 함수 정의 뒤 단어 …)
            continue
        if c.name is None:
            continue
        n = os.path.basename(c.name.text)
        lit = _literal_view(c.args, cmd)           # PLUGIN_READ · print 판정이 받는다 — 따옴표 밖 중괄호 · 글롭 단어도 펼침이다
        if c.name.text.startswith("((") or _plugin_reads(n, c.name, lit, "env" in c.via or id(c.name) in assigned):
            continue                               # 산술 명령(안의 치환은 토크나이저가 거절한다) · 승인 전 창 플러그인 스크립트
        if c.name.expands:
            out.append((None, c))                  # `$CMD x` — 무엇을 실행하는지 모른다
            continue
        # 함수 조회는 래퍼 없이 경로 없는 이름으로 부를 때만이다 — `command touch` · `env touch` · `/usr/bin/touch` 는 외부 명령을 실행한다
        after = n in known or (n in ends and runs_at.get(id(c.name), c.name.start) >= ends[n])
        after = after or id(c.name) in selfc       # 본문 안 맨 이름 자기 호출 — 정의가 끝나기 전 자리지만 그 함수가 불릴 때만 돈다
        rule = True if after and not c.via and "/" not in c.name.text else READ.get(n)
        if rule is True or (rule is not None and rule(lit if rule is _print_reads else c.args)):
            continue
        ws = _write_targets(n, c.args) if n in WRITE_ARGS and "xargs" not in c.via else None
        out += [(None, c)] if ws is None else [(w, c) for w in ws]
    return out


CASE_MAX = 8                                       # 한 명령에서 펴는 case 복합문 수 상한 — 넘으면 원문 그대로(Unknown → 대상 미상 쓰기)


def _case_flat(s: str, p: int):
    """s[p:] 에서 시작하는 case 복합문 하나를 if 갈래로 편 글 — `case` → `if :` · `in` → `; then :;` · 패턴 머리 → `: 패턴 …;` · `;;` → ` ;` ·
    `esac` → `fi`. 본문 글자는 그대로 둔다(본문 명령은 다시 읽혀 각자 판정된다). 못 읽으면(뒤 글이 표 밖 꼴 · 패턴이 단어가 아니다 · 명령 자리의
    esac · 맨 바깥 `;;` 가 없다) None."""
    if s[p:p + 4] != "case" or s[p + 4:p + 5] not in (" ", "\t"):
        return None
    base, W, Op = p + 4, shell_tokens.Word, shell_tokens.Op
    toks = shell_tokens.lex(s[base:])
    if shell_tokens.is_unknown(toks) and toks.why == "case":
        toks = shell_tokens.lex(s[base:base + toks.pos])   # 다음 case 는 다음 차례 — 이 복합문의 esac 가 그 앞에 있어야 한다
    if shell_tokens.is_unknown(toks) or len(toks) < 2 or not isinstance(toks[0], W) or not (
            isinstance(toks[1], W) and toks[1].text == "in" and not toks[1].quoted):
        return None
    edits, k = [(p, base, "if :"), (base + toks[1].start, base + toks[1].end, "; then :;")], 2   # 빈 then 은 `fi` 를 명령으로 읽는다

    def at(t, text):
        edits.append((base + t.start, base + t.end, text))
    while True:
        while k < len(toks) and isinstance(toks[k], Op) and toks[k].text == "\n":
            k += 1
        if k >= len(toks):
            return None
        if isinstance(toks[k], W) and toks[k].text == "esac" and not toks[k].quoted:
            at(toks[k], "fi")
            break
        if isinstance(toks[k], Op) and toks[k].text == "(":
            at(toks[k], " ")
            k += 1
        if k >= len(toks) or not isinstance(toks[k], W):
            return None
        edits.append((base + toks[k].start, base + toks[k].start, ": "))
        k += 1
        while k + 1 < len(toks) and isinstance(toks[k], Op) and toks[k].text == "|" and isinstance(toks[k + 1], W):
            at(toks[k], " ")
            k += 2
        if k >= len(toks) or not (isinstance(toks[k], Op) and toks[k].text == ")"):
            return None
        at(toks[k], ";")
        k, depth, lead = k + 1, 0, True                # 본문 — 맨 바깥 `;;` 또는 명령 자리의 esac 까지
        while True:
            if k >= len(toks):
                return None
            t = toks[k]
            if isinstance(t, Op) and t.text == ";;" and depth == 0:
                at(t, " ;")
                k += 1
                break
            if isinstance(t, Op):
                depth += {"(": 1, ")": -1}.get(t.text, 0)
                lead = t.text != ")"
            elif isinstance(t, W) and lead and depth == 0 and t.text == "esac" and not t.quoted:
                break                                  # 마지막 갈래의 `;;` 없음 — 바깥 고리가 esac 를 닫는다
            else:
                lead = isinstance(t, W) and lead and not t.quoted and t.text in _SCOPE_LEAD
            k += 1
    for a, b, text in sorted(edits, reverse=True):
        s = s[:a] + text + s[b:]
    return s


def _uncase(cmd: str) -> str:
    """P4 만의 읽기 — `case 단어 in 패턴) 명령;; … esac` 를 if 갈래로 편 글(_case_flat). 토크나이저는 case 를 Unknown 으로 둔다(패턴의 `|` ·
    `)` 는 파이프 · 닫는 괄호가 아니다). 복합문 자체는 쓰기가 아니고 갈래 본문 명령은 제자리에서 각자 판정을 받는다 — 어느 갈래의 쓰기든 쓰기 ·
    갈래 안 정의는 if 안 정의처럼 면제 근거가 아니다 · 단어 · 패턴의 치환도 판정한다. 펴지 못하면(백틱 · heredoc 이 든 명령 — 그 안 위치는
    원문 좌표가 아니다 · `;&` · `;;&` · 중첩 case · 본문 첫 자리 함수 정의 · esac 없음) 원문을 돌려준다 → Unknown → 대상 미상 쓰기.
    ⛔ write_sites 는 원문을 받는다 — gate_stop_hook 의 원장 소유 판정은 case 를 지금처럼 Unknown(대상 미상)으로 읽는다."""
    if shell_tokens is None or "case" not in cmd or "`" in cmd or "<<" in cmd:
        return cmd
    out = cmd
    for _ in range(CASE_MAX + 1):                  # 마지막 차례는 CASE_MAX 개를 편 뒤 남은 case 가 없는지 본다 — 남았으면 상한 밖
        toks = shell_tokens.lex(out)
        if not (shell_tokens.is_unknown(toks) and toks.why == "case"):
            return out
        out = _case_flat(out, toks.pos)
        if out is None:
            return cmd
    return cmd


def bash_write(cmd, cwd=None) -> tuple:
    """(쓰는가, 대상 경로 목록). 대상을 모르면 목록이 비어 면제 판정을 하지 않는다.

    ⛔ 계약: 읽기 표(READ · PLUGIN_READ) 밖 이름은 대상 미상 쓰기다 — 쓰기 꼴을 나열해 막지 않는다(차단 목록은 라운드마다 샜다 · F-458).
    쓰기 자리는 write_sites 가 정한다. 대상이 펼쳐지거나(`$X` · 글롭 · 따옴표 든 ~) 치환 · 함수 본문 안이거나, 명령 어딘가에서 폴더를
    옮기면(cd · pushd · popd · `-C`) 상대 대상은 미상이다. Phase 0 의 `mkdir -p {cwd}/{티켓 · NOTASK-날짜[-이름]}` 는 쓰기로 세지 않는다.
    `case … esac` 복합문은 if 갈래로 펴서 본문 명령을 각자 판정한다(_uncase).
    ⛔ 못 읽으면(표 밖 꼴 · 명령 자리 미상 · 토크나이저 없음) 대상 미상 쓰기다 — P4 창 안에서는 막힌다. 정규식으로 돌아가지 않는다.
    """
    if not isinstance(cmd, str) or not cmd.strip():
        return False, []
    cmd = _uncase(cmd)
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
        return set(RULES), f"끄기 값 {unknown} 를 모른다(P4 · AG · FR · GP · all) — 전부 끈다"
    return (set(RULES) if "ALL" in tokens else tokens), ""


def _git_sub(args) -> str:
    """`git [전역 옵션] 하위 명령` 의 하위 명령 글자 — 값을 받는 전역 옵션은 값까지 건너뛴다(_git_dirs 와 같은 표)."""
    i = 0
    while i < len(args):
        t = args[i].text
        if not t.startswith("-"):
            return t
        i += 2 if t in ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env") else 1
    return ""


GREP_COUNT_LONG = frozenset(("--count", "--files-with-matches", "--files-without-match", "--name-only"))
GREP_VALUE_LONG = frozenset(("--max-depth", "--max-count", "--context", "--after-context", "--before-context", "--threads",
                             "--regexp", "--file"))       # `=` 없이 쓰면 다음 단어가 값
GREP_ALL_FILES = frozenset(("--untracked", "--no-index", "--cached"))   # 미추적까지 보거나 · 일부러 인덱스만 본다
REV_LIKE = re.compile(r"^(?:HEAD|FETCH_HEAD|ORIG_HEAD|@|[0-9a-f]{7,40}|refs/\S+|origin/\S+|v\d\S*|\S*(?:\.\.|[~^]|@\{)\S*)$")


def _tracked_census(args) -> bool:
    """`git … grep` 인자가 개수 · 파일 목록(-c · -l · -L · --count · --name-only …)을 내는데 작업 트리를 추적 파일만으로 본다 (F-611).
    `--untracked` · `--no-index` · `--cached` · 리비전(패턴 뒤 `--` 앞 위치 인자 · 리비전 꼴 낱말)이면 아니다. 짧은 옵션 묶음은 글자마다 읽고
    값을 받는 글자(e f m A B C)는 남은 글자 · 없으면 다음 단어를 값으로 먹는다 — `-O` 의 값은 붙여 쓰는 선택값이다.
    ponytail: 긴 옵션 축약(`--cou`)은 보지 않는다 — git 이 받지만 드물다."""
    a = [x.text for x in args]
    i = next((k for k, w in enumerate(a) if w == "grep"), len(a)) + 1
    count, pattern_given, pos, dashdash = False, False, [], False
    while i < len(a):
        w = a[i]
        i += 1
        if w == "--":
            dashdash = True
            break
        if w in GREP_ALL_FILES:
            return False
        if w.startswith("--"):
            name = w.split("=", 1)[0]
            count = count or name in GREP_COUNT_LONG
            pattern_given = pattern_given or name in ("--regexp", "--file")
            if name in GREP_VALUE_LONG and "=" not in w:
                i += 1
            continue
        if w.startswith("-") and len(w) > 1:
            for k, ch in enumerate(w[1:]):
                count = count or ch in "clL"
                if ch in "efmABCO":
                    pattern_given = pattern_given or ch in "ef"
                    if ch != "O" and k == len(w) - 2:
                        i += 1                     # 묶음 끝의 값 글자 — 다음 단어가 값
                    break
            continue
        pos.append(w)
    trees = pos[0 if pattern_given else 1:]
    if trees and (dashdash or any(REV_LIKE.match(x) for x in trees)):
        return False                               # 리비전을 읽는 grep — 추적 파일만이 의도다
    return count


def _pitfall_hits(cmd: str, cwd) -> list:
    toks = shell_tokens.lex(cmd)
    if shell_tokens.is_unknown(toks):
        return []                                  # 판정 불가 = 통과(경고 없음)
    segs, cur, depth, at = [], [], 0, 0            # 맨 바깥 단순 명령마다 (토큰, 뒤 연산자, 서브셸 깊이) — commands() 는 `( … )` 안도 깊이 0 으로 낸다
    for t in toks:
        if isinstance(t, shell_tokens.Op):
            if cur:
                segs.append((cur, t.text, at))
            cur = []
            depth = depth + 1 if t.text == "(" else max(0, depth - 1) if t.text == ")" else depth
        else:
            if not cur:
                at = depth
            cur.append(t)
    if cur:
        segs.append((cur, "", at))
    hits, pipe, moved = [], [], False
    for ts, op, at in segs:
        top = [c for c in shell_tokens.commands(ts) if c.depth == 0][:1]
        c = top[0] if top and top[0].name is not None and not top[0].unsure else None
        name = os.path.basename(c.name.text) if c and not c.name.expands else ""
        pipe.append("git grep" if name == "git" and _git_sub(c.args) == "grep" else name if name in PITFALL_EVIDENCE else "")
        if name == "head" and any(pipe[:-1]):
            hits.append(("head", next(x for x in pipe[:-1] if x)))
        if op not in ("|", "|&"):
            pipe = []
        if name == "rm":                           # F-640 — 공용 임시 폴더 아래 따옴표 밖 글롭(펼침 앞머리 포함)
            for a in c.args:
                raw = cmd[a.start:a.end] if isinstance(a.start, int) and isinstance(a.end, int) else a.text
                if SHARED_TMP.match(raw) and _glob_pattern(_EXPANSION.sub("", raw)) is not None:
                    hits.append(("shared-rm", raw))
                    break
        if name in ("cd", "pushd") and op == "&&" and at == 0:
            hits.append(("cd", " ".join([name] + [a.text for a in c.args])))
        # F-751 — 글롭 축은 치환 안 단순 명령의 인자도 본다(zsh 무매칭은 치환만 끊어 변수가 조용히 빈다) · head 축의 치환 제외는 그대로
        inner = [x for x in shell_tokens.commands(ts) if x.depth > 0 and x.name is not None and not x.unsure
                 and os.path.basename(x.name.text) != "[["]
        for w in [a for cc in ([c] if c and name != "[[" else []) + inner for a in cc.args]:
            bare = _EXPANSION.sub("", w.text)
            raw = cmd[w.start:w.end] if isinstance(w.start, int) and isinstance(w.end, int) else w.text
            pat = _glob_pattern(_EXPANSION.sub("", raw))
            if pat is None or "{" in bare or w.text.startswith("~"):
                continue                           # 따옴표 · 이스케이프 안 글롭 · 중괄호 펼침 · 물결은 보지 않는다(셸이 다르게 푼다)
            if w.expands:
                hits.append(("glob", w.text))      # 펼친 값을 모른다 — 맞출 파일이 있는지 잴 수 없다
                continue
            base = None if moved else cwd if isinstance(cwd, str) and cwd.startswith("/") else None
            path = pat if pat.startswith("/") else os.path.join(glob.escape(base), pat) if base else None
            if path is not None and next(glob.iglob(path), None) is None:
                hits.append(("glob", w.text))
        moved = moved or name in ("cd", "pushd", "popd")   # 이동 뒤 상대 글롭은 어디서 풀리는지 모른다 — 재지 않는다
        # F-611 — 추적 파일만 보는 집계(맨 바깥 · 명령 치환 안 — `n=$(git grep -l x | wc -l)` 이 흔한 꼴이다)
        if not any(k == "tracked-census" for k, _ in hits) and any(
                os.path.basename(x.name.text) == "git" and _git_sub(x.args) == "grep" and _tracked_census(x.args)
                for x in ([c] if c else []) + inner):
            hits.append(("tracked-census", "git grep"))
    for t in _deep(toks):                          # 모든 깊이 — 치환 안 단어도 원문 좌표를 쓴다
        if isinstance(t, shell_tokens.Word) and isinstance(t.start, int) and isinstance(t.end, int):
            m = ZSH_SUBSCRIPT.search(re.sub(r"'[^']*'", "", cmd[t.start:t.end]))
            if m:
                hits.append(("subscript", m.group(0)[:-1]))
                break
    return hits


def pitfall_hits(cmd, cwd) -> list:
    """T-pitfall — 적어 둔 셸 함정 꼴 [(꼴, 근거 낱말)]. ⛔ 상태 · 잠금 없는 순수 판정이다(읽기 Bash 조기 반환 앞에서 모든 Bash 에 돈다).
    꼴: head — 맨 바깥 파이프라인에서 근거 명령 뒤 칸의 head(치환 안 `$(… | head -1)` 은 고르기라 보지 않는다) ·
        glob — 따옴표 밖 글롭이 지금 아무것도 맞추지 않거나 펼침을 품었다 · cd — 서브셸 밖 cd · pushd 바로 뒤 `&&` ·
        shared-rm — 맨 바깥 rm 이 공용 임시 폴더(/tmp · /private/tmp · /var/folders · $TMPDIR) 아래를 따옴표 밖 글롭으로 지운다(F-640) ·
        tracked-census — 맨 바깥 `git grep` 이 개수 · 파일 목록을 내는데 `--untracked` · `--no-index` 가 없다(F-611).
    ⛔ 못 읽은 명령 · 판정 중 오류는 빈 목록이다 — 판정 불가 = 통과(이 판정은 무엇도 막지 않는다)."""
    if shell_tokens is None or not isinstance(cmd, str):
        return []
    try:
        return _pitfall_hits(cmd, cwd)
    except Exception:                              # noqa: BLE001 — 훅은 세션을 막지 않는다
        return []


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


def pitfall_warn(out, st: dict, pid, hits):
    """T-pitfall 경고를 결정에 붙인다 — prompt · 꼴마다 1회(warn_once). 기존 systemMessage 는 뒤에 잇고 결정(deny · ask)은 그대로 둔다."""
    msgs = []
    for k, w in dict.fromkeys(hits):
        m = warn_once(st, f"pitfall:{pid}:{k}", PITFALL_TEXT[k] % w)
        if m and m["systemMessage"] not in msgs:
            msgs.append(m["systemMessage"])
    if not msgs:
        return out
    text = f"{WARN_PITFALL} — " + " · ".join(msgs) + " · 막지 않는다"
    out = dict(out or {})
    out["systemMessage"] = " · ".join(x for x in (out.get("systemMessage"), text) if x)
    return out


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
    if turn.get("peer") and isinstance(turn.get("prComments"), list):   # 피어 리뷰 턴이 읽은 PR 은 이 세션에서 다시 묻지 않는다(이어지는 턴)
        st["fingerprints"].extend(fp for fp in (f"{sid}:PC:pr{n}" for n in turn["prComments"] if n != "?") if fp not in st["fingerprints"])
    p4 = "P4" not in off and pid in st["prompts"] and w and w.get("promptId") == pid and not w.get("approved")   # 시작을 못 본 prompt = p4_pre 와 같이 무차단
    fr_base = "FR" not in off and env.get("FZ_FINDINGS_ROOT") and not turn.get("registryWrite")
    fr = fr_base and turn.get("memoryLesson") and not entry_since(env, turn.get("start"))
    pc = (fr_base and not fr and turn.get("prComments") and not turn.get("peer") and not NO_FINDING.search(lam)
          and not entry_since(env, turn.get("start")))     # F-708 — 교훈 축(F-518)이 이미 막으면 한 사유만 낸다
    gp = "GP" not in off and turn.get("review") and not turn.get("gpt") and not GPT_MARK.search(lam)
    long_answer = p4 and not w.get("asked") and len(lam) >= LONG_ANSWER
    mode = session_mode(inp.get("transcript_path")) if (p4 or fr or pc or gp) else ""
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
    if pc and mode == "interactive":
        prs = turn["prComments"] if isinstance(turn["prComments"], list) else ["?"]
        fps = [f"{sid}:PC:{pid}" if n == "?" else f"{sid}:PC:pr{n}" for n in prs]   # 번호가 있으면 (세션, PR) 마다 한 번
        new = [fp for fp in fps if fp not in st["fingerprints"]]
        if new:
            st["fingerprints"].extend(new)
            reasons.append(PC_STOP)
    elif pc and mode == "unknown":
        warns.append(f"{WARN_UNDECIDED} — 실행 모드를 판정하지 못했다 · PR 코멘트 기록 누락(F-708) Stop 을 막지 않는다")
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
        if pid:
            turn_of(st, pid)["start"] = time.time()   # F-518 — FR 이 이 턴에 쓰인 레지스트리 항목을 파일 시각으로 가린다(entry_since)
        if tok.startswith("/") and fz_marker(tok):
            st["fzSession"] = True
        if opens_window(tok):
            open_window(st, pid)
        if tok.lstrip("/") in REVIEW_SKILLS and pid:
            turn_of(st, pid)["review"] = True     # F-094 — 이 턴은 fz-review 다
        if tok.lstrip("/") in PEER_SKILLS and pid:
            turn_of(st, pid)["peer"] = True       # F-708 면제 — 피어 리뷰 턴
            peer_prs(st, sid, inp.get("prompt"))  # 명령 인자의 PR 은 이 세션에서 묻지 않는다(첫 읽기가 다음 턴이어도)
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
            if skill in PEER_SKILLS and pid:
                turn_of(st, pid)["peer"] = True
                peer_prs(st, sid, ti.get("args"))
            return None
        if name == "Bash":
            cmd = ti.get("command") if isinstance(ti.get("command"), str) else ""
            if gpt_review_invoked(cmd) and pid:
                turn_of(st, pid)["gpt"] = True     # F-094 — GPT 리뷰를 불렀다(출력은 Bash 라 PostToolUse 로 못 본다)
            prs = pr_comment_reads(cmd) if pid and st["fzSession"] else None
            if prs:
                mark_pr_comments(turn_of(st, pid), prs)   # F-708 — fz 턴이 PR 코멘트 · 리뷰를 읽었다(명령 자리의 gh 만)
            writes, targets = bash_write(cmd, inp.get("cwd"))
            if writes and "P4" not in off:
                return p4_pre(inp, env, st, ti, pid, paths=targets)
            return None
        if write_tool(name) and "GP" not in off:
            hits = wording_hits(ti, inp.get("cwd"))
            if hits:
                return decision("deny", GP_DENY + " | ".join(h[:120] for h in hits[:3]))
        if pid and st["fzSession"] and PR_COMMENT_TOOLS.match(name):
            mark_pr_comments(turn_of(st, pid), [ti.get("pull_number") or ti.get("pullNumber")])   # F-708 — GitHub MCP 로 읽은 코멘트 · 리뷰
        if name in AGENT_TOOLS:
            if "AG" in off or not st["fzSession"]:
                return None
            kind = ti.get("subagent_type") if isinstance(ti.get("subagent_type"), str) and ti.get("subagent_type") else "general-purpose"
            if kind in LEAD_DIRECT_AGENTS:
                return None
            if kind in ALLOW_AGENTS or autonomous(env):
                return None
            mode = session_mode(inp.get("transcript_path"))
            if mode == "headless":
                return None                        # ⛔ -p 에는 답할 사람이 없다 — ask 는 사실상 거부다(공식 훅 문서)
            if mode == "unknown":
                return warn_once(st, f"undecided-agent:{pid}", f"{WARN_UNDECIDED} — 실행 모드를 판정하지 못했다 · 에이전트({kind}) 확인을 묻지 않는다")
            return warn_once(st, f"ag:{pid}:{kind}", f"fz-guard AG(F-058 · F-119): fz 세션에서 허용 목록 밖 에이전트({kind})를 띄운다. "
                                                     f"fz 위임은 Workflow 경유가 규칙이다(선택 플러그인 에이전트 {len(ALLOW_AGENTS)}종 · "
                                                     f"Lead 가 직접 띄우는 fz 에이전트 {len(LEAD_DIRECT_AGENTS)}종만 예외) · 막지 않는다")
        if p4_tool(name) and "P4" not in off:
            return p4_pre(inp, env, st, ti, pid)
        return None
    if ev == "PostToolUse":
        if name == "AskUserQuestion":
            record_answer(inp, st)
        elif name == "Read":                      # run() 이 fz-review · fz-peer-review SKILL.md 만 들여보낸다
            fp = ti.get("file_path") if isinstance(ti.get("file_path"), str) else ""
            if pid and PEER_SKILL_FILE.search(fp) and st["fzSession"]:
                turn_of(st, pid)["peer"] = True    # F-708 면제 — /fz 가 Read 로 도는 피어 리뷰 턴
            elif pid and (st.get("window") or {}).get("promptId") == pid:
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
    pp, diag, tp, fast = None, "", [], None
    if inp.get("hook_event_name") == "PostToolUse" and inp.get("tool_name") == "Read":
        ti = inp.get("tool_input") if isinstance(inp.get("tool_input"), dict) else {}
        if not (isinstance(ti.get("file_path"), str) and (REVIEW_SKILL_FILE.search(ti["file_path"]) or PEER_SKILL_FILE.search(ti["file_path"]))):
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
        tp = pitfall_hits(cmd, inp.get("cwd"))    # T-pitfall — 상태 · 잠금 없는 순수 판정(아래 조기 반환 앞)
        if not isinstance(cmd, str) or not (bash_write(cmd, inp.get("cwd"))[0] or gpt_review_invoked(cmd) or PR_COMMENTS.search(cmd)):
            fast = json.dumps(pp, ensure_ascii=False) if pp else ""
            if not tp:
                return fast, diag                  # ⛔ 읽는 Bash 는 상태를 열지 않는다 — 모든 세션의 모든 Bash 에 잠금 · 저장이 붙지 않게
            # 함정 꼴이 든 읽기만 상태 경로로 간다(경고 1회 판정). 상태 경로가 실패해도 보호 경로 ask(fast)는 그대로 낸다
    try:
        timeout = float(env.get("FZ_GUARD_LOCK_TIMEOUT") or LOCK_TIMEOUT)
    except ValueError:
        timeout = LOCK_TIMEOUT
    try:                                           # ⛔ 상태 폴더 해석 · 끄기 판정도 안쪽 — `~없는사용자/x` 도 exit 0 + 진단
        sdir = state_dir(env)
        if inside_plugin(sdir):
            return fast or "", f"fz-guard diag: 상태 폴더가 플러그인 안이다({sdir}) — 쓰지 않고 통과(fail-open)"
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
            if tp:
                out = pitfall_warn(out, st, inp.get("prompt_id"), tp)
            trim(st)
            save_state(path, st)
    except LockTimeout:
        return fast or "", f"fz-guard diag: 상태 잠금을 {timeout}s 안에 잡지 못했다 — 통과(fail-open)"
    except OSError as e:
        return fast or "", f"fz-guard diag: 상태를 읽거나 쓰지 못했다({type(e).__name__}) — 통과(fail-open)"
    except Exception as e:                         # noqa: BLE001 — 훅은 세션을 막지 않는다
        return fast or "", f"fz-guard diag: 내부 오류 {type(e).__name__} — 통과(fail-open)"
    if pp and ((out or {}).get("hookSpecificOutput") or {}).get("permissionDecision") != "deny":
        out = {**(out or {}), **pp}               # 보호 경로 ask 는 P4 deny 를 덮지 않는다
    return (json.dumps(out, ensure_ascii=False) if out else ""), (diag if fast is not None else "")


# ── 보조 모드 ──────────────────────────────────────────────────────
def allowlist_from(md: str, header: str = "스폰 방식") -> list:
    """헤더 줄에 header 가 든 첫 표의 **굵은** 이름만 — 채택 표('스폰 방식') · Lead 직접 표(LEAD_TABLE_HEADER). 같은 문서의 불채택 표는 읽지 않는다."""
    names, inside = [], False
    for line in md.splitlines():
        if not inside:
            inside = line.startswith("|") and header in line
            continue
        if not line.startswith("|"):
            break
        m = re.match(r"^\|\s*\*\*([^*|]+)\*\*\s*\|", line)
        if m:
            names.append(m.group(1).strip())
    return names


def check_allowlist(path: str) -> int:
    try:
        md = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"UNRUN: 표를 읽지 못했다 — {e}")
        return 2
    names, lead = allowlist_from(md), allowlist_from(md, LEAD_TABLE_HEADER)
    if not names:
        print("UNRUN: 채택 표('스폰 방식' 헤더)를 찾지 못했다")
        return 2
    bad = set(names) != ALLOW_AGENTS
    if bad:
        print(f"MISMATCH: 표만 {sorted(set(names) - ALLOW_AGENTS)} · guard 만 {sorted(ALLOW_AGENTS - set(names))}")
    if set(lead) != LEAD_DIRECT_AGENTS:            # Lead 직접 표가 없어도 불일치다(표 없음 = guard 만 쪽에 이름이 남는다)
        print(f"MISMATCH: Lead 직접 표만 {sorted(set(lead) - LEAD_DIRECT_AGENTS)} · guard 만 {sorted(LEAD_DIRECT_AGENTS - set(lead))}")
        bad = True
    if bad:
        return 1
    print(f"ALLOWLIST OK — {len(names)}종 · Lead 직접 {len(lead)}종")
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

    @contextlib.contextmanager
    def login_shell(path):                          # print 판정은 SHELL 을 본다 — 셀이 값을 정하고 끝나면 되돌린다(None = 지운다)
        old = os.environ.get("SHELL")
        if path is None:
            os.environ.pop("SHELL", None)
        else:
            os.environ["SHELL"] = path
        try:
            yield
        finally:
            if old is None:
                os.environ.pop("SHELL", None)
            else:
                os.environ["SHELL"] = old

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
    def c3b():                                     # 서버 등록명이 xcode 가 아니어도(다른 이름 · 플러그인 접두 · 대문자) 같은 쓰기 도구다
        s = fz("c3b")
        got = [kind(s.pre(t, {"filePath": "/srv/demo/a.swift"})) for t in
               ("mcp__xcodemcp__XcodeWrite", "mcp__plugin_xcode_xcode__XcodeWrite", "mcp__Xcode__XcodeUpdate")]
        case("p4-xcode-other-server-name-write-denied", got == ["deny"] * 3, got)

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
               s.pre("Bash", B("mkdir -p /srv/demo/TKT-1234 && cat > /srv/demo/TKT-1234/index.md <<'EOF'\n# x\nEOF")),
               s.pre("Write", {"file_path": "/srv/demo/NOTASK-20261110-wave3/index.md", "content": "x"})]   # 같은 날 다른 작업(접미 이름)
        case("f553-phase0-workdir-allowed", got == [None] * 4, got)

    @cell
    def f553b():
        s = fz("f553b")
        got = [kind(s.pre("Write", {"file_path": p, "content": "x"})) for p in (
            "/srv/demo/TKT-1234/plan.md", "/srv/demo/src/index.md", "/srv/other/TKT-1234/index.md",
            "/srv/demo/TKT-1234/../a.swift", "/srv/demo/x/TKT-1234/index.md", "/srv/demo/NOTASK-20261110-/index.md",
            "/srv/demo/x/NOTASK-20261110-a/index.md", "/srv/other/NOTASK-20261110-a/index.md")]
        case("f553-outside-workdir-still-denied", got == ["deny"] * 8, got)

    @cell
    def r4_workdir_grid():
        names = {"TKT-1234": True, "NOTASK-20261110": True, "NOTASK-20261110-wave3": True, "NOTASK-20261110-": False, "NOTASK-2026111": False,
                 "notask-20261110": False}
        spots = {"/srv/demo": True, "/srv/demo/x": False, "/srv/other": False}
        s, bad = fz("r4wd"), []
        for n, name_ok in names.items():
            for base, spot_ok in spots.items():
                d = f"{base}/{n}"
                acts = (("index", s.pre("Write", {"file_path": f"{d}/index.md", "content": "x"}), True),
                        ("other-file", s.pre("Write", {"file_path": f"{d}/plan.md", "content": "x"}), False),
                        ("mkdir", s.pre("Bash", B(f"mkdir -p {d}")), True), ("rm", s.pre("Bash", B(f"rm -rf {d}")), False),
                        ("cd-relative", s.pre("Bash", B(f"cd {base} && mkdir -p {n}")), False))
                bad += [(d, act, kind(o)) for act, o, act_ok in acts if kind(o) != (None if name_ok and spot_ok and act_ok else "deny")]
        case("r4-workdir-name-grid — WORK_DIR 이름 꼴(티켓 · NOTASK-날짜 · NOTASK-날짜-이름 · 빈 접미 · 7자리 날짜 · 소문자) × 자리(cwd 바로 아래 · 중첩 · "
             "다른 루트) × 동작(index.md · 다른 파일 Write · mkdir · rm · cd 뒤 상대 mkdir) — 맞는 이름의 cwd 바로 아래 index.md · mkdir 만 허용",
             not bad, bad)

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
        s = fr_on("f565a")
        s.prompt("메모리 정리", "p1")
        s.post("Write", {"file_path": str(pathlib.Path(mem).with_name("MEMORY.md")),
                         "content": "- [fz-code 사용 메모](feedback_fz_code.md) — `fz-code` 링크\n- [fz-findings 경로](reference_x.md)\n"})
        case("f565-skill-link-only-not-lesson", s.stop() is None)

    @cell
    def f565b():
        s = fr_on("f565b")
        s.prompt("회고", "p1")
        s.post("Write", {"file_path": mem, "content": "fz-peer-review 교훈 — 분석만 요청받았다는 예외로 등재를 미뤘다"})
        o = s.stop()
        case("f565-f518-still-caught", blocked(o) and "F-518" in o.get("reason", ""), o)

    @cell
    def r3_f565_topic():
        s = fr_on("r3f565")
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
        # `cd $X &&` 는 T-pitfall 경고(systemMessage)를 받는다 — 여기서 재는 것은 묻지 않음(결정 없음)이다
        case("r3-f024-default-empty-noop — 보호 경로가 비면(기본) 어떤 Bash 도 묻지 않는다",
             got[0::2] == [None, None] and kind(got[1]) is None and not s.err, (got, s.err))

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

    tp_root = tmp / "tpit"                          # T-pitfall 글롭 판정용 실제 폴더 — 맞는 글롭(entries/) · 무매칭 글롭(.archive/ 없음)
    (tp_root / "entries").mkdir(parents=True)
    (tp_root / "sub").mkdir()
    (tp_root / "entries" / "F-594-x.md").write_text("# F-594\n", encoding="utf-8")

    def pit(o):
        return ((o or {}).get("systemMessage") or "") if WARN_PITFALL in ((o or {}).get("systemMessage") or "") else ""

    @cell
    def tpit_pos():
        s = S("tpp")
        # 양성 = 엔트리에 적힌 실제 명령(F-727 ② ③ · F-673 · F-654 ③ ④ · F-610) — prompt 마다 하나라 1회 경고가 가리지 않는다
        rows = [("F-727-2", "grep -lE '0e7f5ce|applied_ref_era' entries/*.md .archive/*.md | head", ("grep … | head", "`.archive/*.md`")),
                ("F-727-3", "for id in F-594 F-600; do ls entries/$id-*.md .archive/$id-*.md; done", ("`entries/$id-*.md`",)),
                ("F-673", "grep -rn 'hooks/' entries docs/*.md", ("`docs/*.md`",)),
                ("F-654-3", "cd sub && ls", ("`cd sub &&`",)),
                ("F-654-4", "ls .archive/F-7*.md", ("`.archive/F-7*.md`",)),
                ("F-610", "cd sub && python3 gen.py", ("`cd sub &&`",)),
                ("F-727-3q", 'ls "./.archive/"*.md', ("`./.archive/*.md`",)),          # 경로만 따옴표 · 글롭은 밖(채점 2차 ISSUE-002)
                ("F-727-3r", 'ls "$ROOT"/.archive/*.md', ("`$ROOT/.archive/*.md`",))]   # 따옴표 친 펼침 + 밖 글롭
        bad = []
        for i, (fid, cmd, needles) in enumerate(rows):
            s.prompt("근거를 찾아 줘", f"p{i}")
            o = bash_at(s, cmd, cwd=str(tp_root))
            if kind(o) is not None or not all(n in pit(o) for n in needles):
                bad.append((fid, o))
        st = load_state(pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard" / "s1.json")
        case("t-pitfall-positive-warns — 일곱 엔트리 중 셸 꼴이 적힌 명령(| head · 무매칭 · 펼침 글롭 · cd X &&)은 막지 않고 경고한다 · "
             "경고는 상태 경로(st['warned'])를 지난다", not bad and sum(k.startswith("pitfall:") for k in st["warned"]) >= len(rows), bad)

    @cell
    def tpit_neg():
        s = S("tpn")                               # prompt 없이 — 읽기 Bash 만으로 상태 폴더가 생기면 빠른 반환이 깨진 것이다
        neg = [f"git -C {tp_root} status --porcelain", "grep -n -E 'def |owner' entries/F-594-x.md",
               "find entries .archive -maxdepth 1 -name 'F-727-*.md'",   # 있을지 모르는 경로의 처방(F-727 ③)
               "( cd sub && ls )",                    # cd 의 처방(F-610) — 서브셸 안 이동은 세션 폴더를 바꾸지 않는다
               "ls entries/*.md",                     # 맞는 글롭
               "f=$(ls entries | head -1)",           # 치환 안 head 는 고르기다
               "git log --oneline | head -5",         # 근접 음성 — 근거 명령이 아닌 칸 뒤 head
               "grep -c x entries/F-594-x.md | sort",  # 근접 음성 — 근거 명령 뒤지만 head 가 아니다
               "echo $(( 3 * 2 ))", "(( 3 * 2 )) && echo y", '[[ $a == *.md ]] && echo y',   # 산술 · 패턴 비교
               "find entries -name \\*.md",          # 역슬래시로 막은 글롭(F-727 ③ 처방의 다른 철자)
               'ls "./.archive/*.md"', 'ls "entries/"*.md']   # 글롭까지 따옴표(셸이 글자로 넘긴다) · 경로만 따옴표지만 맞는 글롭
        got = [(c, run(json.dumps({"session_id": s.sid, "transcript_path": s.tr, "cwd": str(tp_root), "hook_event_name": "PreToolUse",
                                   "prompt_id": "p1", "tool_name": "Bash", "tool_input": B(c), "tool_use_id": "t"}), s.env)) for c in neg]
        noisy = [(c, o) for c, o in got if o != ("", "")]
        # 못 읽는 명령은 꼴 판정 불가 = 경고 없음(그 명령의 상태 경로는 쓰기 판정 몫 — 대상 미상 쓰기)
        undecided = [pitfall_hits(c, str(tp_root)) for c in ("echo $[1] | head", "cd $'\\x41' && ls *.none")]
        case("t-pitfall-negative-quiet — 처방 꼴 · 맞는 글롭 · 치환 안 head · 근접 음성은 결정 · 경고 · 상태 폴더 없이 빠르게 돌아간다 · 못 읽는 명령은 꼴 없음",
             not noisy and not (pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard").exists() and undecided == [[], []], (noisy, undecided))

    @cell
    def tpit_subst():
        # F-751 — 치환 안 '파일 집기' 꼴(엔트리 D4 표본) · 음성은 맞는 글롭 · 치환 안 head · 따옴표 친 글롭
        pos = ["f=$(grep -l x /nonexistent-fz-751-*)", "f=$(ls $R/F-1-*)", "x=$(grep -l x $(dirname a)/F-1-*)",
               'echo "$(ls /nonexistent-fz-751-*)"']
        neg = ["f=$(ls entries/*.md)", "f=$(ls entries | head -1)", "f=$(find entries -name '*.md')"]
        got_pos = [(c, pitfall_hits(c, str(tp_root))) for c in pos]
        got_neg = [(c, pitfall_hits(c, str(tp_root))) for c in neg]
        case("t-pitfall-substitution-glob — 치환 안 명령의 무매칭 · 펼침 글롭도 경고한다 · 맞는 글롭 · 치환 안 head · 따옴표 글롭은 조용하다(F-751)",
             all(any(k == "glob" for k, _ in h) for _, h in got_pos) and all(h == [] for _, h in got_neg), (got_pos, got_neg))

    @cell
    def tpit_zsh_subscript():
        # F-745 ① — 엔트리 D1 의 실제 꼴 · 음성은 중괄호 · 작은따옴표 · 첨자 펼침 · 산술
        pos = ['grep -E "$f[^0-9]" a.txt', "echo $name[1]", 'x=$(grep -c "$id[a-z]" b)']
        neg = ['grep -E "${f}[^0-9]" a.txt', "grep -E '$f[^0-9]' a.txt", "echo ${arr[1]}", "echo $(( a[1] + 1 ))", "echo $f [x]"]
        got_pos = [(c, pitfall_hits(c, str(tp_root))) for c in pos]
        got_neg = [(c, pitfall_hits(c, str(tp_root))) for c in neg]
        case("t-pitfall-zsh-subscript — 작은따옴표 밖 `$이름[` 는 zsh 배열 첨자라 경고한다 · `${…}` · 작은따옴표 · 산술은 조용하다(F-745 ①)",
             all(any(k == "subscript" for k, _ in h) for _, h in got_pos)
             and all(not any(k == "subscript" for k, _ in h) for _, h in got_neg), (got_pos, got_neg))

    @cell
    def tpit_shared_rm():
        # F-640 — 엔트리의 실제 꼴(`/tmp/fz-gpt-iso.*`) · 음성은 정확한 경로 · 변수 하나 · 공용 밖 글롭 · rm 아닌 명령 · 따옴표 친 글롭
        pos = ["rm -rf /tmp/fz-gpt-iso.*", "rm -rf $TMPDIR/fz-gpt-iso.*", "rm -f /private/tmp/claude-*/scratch*"]
        neg = ["rm -rf /tmp/fz-gpt-iso.Ab12Cd", 'rm -rf "$D"', "rm -rf ./build/*", "ls /tmp/fz-gpt-iso.*", "rm -rf '/tmp/fz-gpt-iso.*'"]
        got_pos = [(c, pitfall_hits(c, str(tp_root))) for c in pos]
        got_neg = [(c, pitfall_hits(c, str(tp_root))) for c in neg]
        case("t-pitfall-shared-tmp-rm — 공용 임시 폴더 아래 따옴표 밖 글롭 rm 은 경고한다 · 정확한 경로 · 변수 · 공용 밖 · 따옴표 글롭은 조용하다(F-640)",
             all(any(k == "shared-rm" for k, _ in h) for _, h in got_pos)
             and all(not any(k == "shared-rm" for k, _ in h) for _, h in got_neg), (got_pos, got_neg))

    @cell
    def tpit_tracked_census():
        # F-611 — 엔트리의 꼴(추적 파일만 보는 집계 → 미추적 새 파일 40개가 빠짐) · 음성은 --untracked · --no-index · 집계 아닌 grep · 값 자리 · 따옴표 안
        pos = ["git grep -c foo", "git -C /x grep -l foo -- '*.md' | wc -l", "git grep -ic foo", "git grep --count foo", "git grep --name-only foo",
               "n=$(git grep -l foo | wc -l)", "git grep -lC3 foo", "git grep -cA2 foo", "git grep -O -c foo", "git grep -l -e foo docs"]
        neg = ["git grep --untracked -c foo", "git grep -c --untracked foo", "git grep --no-index -l foo", "git grep -n foo",
               "git grep -e -cool x", "echo 'git grep -c foo'", "grep -c foo a.txt", "git grep -c foo --untracked -- x",
               "git grep -c foo HEAD", "git grep -l foo v1.0 -- docs", "git grep --cached -c foo", "git grep -nec foo",
               "git grep -ie -clean x", "git grep -l foo main -- docs", "git grep -c foo HEAD~3"]
        got_pos = [(c, pitfall_hits(c, str(tp_root))) for c in pos]
        got_neg = [(c, pitfall_hits(c, str(tp_root))) for c in neg]
        case("t-pitfall-tracked-census — 개수 · 파일 목록을 내는 git grep 에 --untracked · --no-index 가 없으면 경고한다 · 집계 아닌 grep · 값 자리 · 따옴표 안은 조용하다(F-611)",
             all(any(k == "tracked-census" for k, _ in h) for _, h in got_pos)
             and all(not any(k == "tracked-census" for k, _ in h) for _, h in got_neg), (got_pos, got_neg))

    @cell
    def tpit_cells():
        import threading
        cmd = "grep -rn 'def run' scripts | head -5"
        a = S("tpc")
        a.prompt("hello", "p1")
        outs = []
        ths = [threading.Thread(target=lambda: outs.append(a.pre("Bash", B(cmd)))) for _ in range(4)]
        [t.start() for t in ths]
        [t.join() for t in ths]
        same = sum(bool(pit(o)) for o in outs) + bool(pit(a.pre("Bash", B(cmd))))
        a.prompt("next", "p2")
        nxt = sum(bool(pit(a.pre("Bash", B(cmd)))) for _ in range(2))
        off = S("tpo", FZ_GUARD_DISABLE="all")
        off.prompt("hello", "p1")
        quiet = off.pre("Bash", B(cmd)) is None
        pp = S("tpa", FZ_GUARD_PROTECTED=prot)
        pp.prompt("hello", "p1")
        asked = pp.pre("Bash", B(f"grep -rn x {prot} | head -3"))
        w = fz("tpw")                              # P4 창 안 쓰기 — deny 는 그대로 · 경고는 덧붙는다
        denied = w.pre("Bash", B("cd /srv/demo && mkdir -p out"))
        lk = S("tpl", FZ_GUARD_PROTECTED=prot, FZ_GUARD_LOCK_TIMEOUT="0.05")
        lk.prompt("hello", "p1")
        fd = os.open(str(pathlib.Path(lk.env["FZ_RUN_STATE"]) / "fz-guard" / "s1.lock"), os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)         # 잠금을 쥔 채 — 상태 경로가 실패해도 보호 경로 ask 는 남는다
            held = lk.pre("Bash", B(f"grep -rn x {prot} | head -3"))
            held_err = lk.err
        finally:
            os.close(fd)
        got = (same, nxt, quiet, kind(asked), bool(pit(asked)), kind(denied), bool(pit(denied)), kind(held), "잠금" in held_err)
        case("t-pitfall-once-per-prompt-composes — 같은 prompt 병렬 4 + 재호출 → 경고 1 · 다음 prompt → 다시 1 · disable=all → 0 · "
             "보호 경로 ask · P4 deny 는 그대로 + 경고 · 상태 잠금 실패에도 ask 유지",
             got == (1, 1, True, "ask", True, "deny", True, "ask", True), got)

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
    def apple_read_forms():
        # F-583 — 엔트리 §2 표의 읽기 행은 읽기 · 같은 도구의 쓰기 꼴은 대상 미상 쓰기 그대로 · 인터프리터 읽기는 여전히 막는다
        reads = ["xcrun simctl list devices", "xcrun simctl getenv booted HOME", "xcrun simctl get_app_container booted com.x.app data",
                 "xcrun simctl listapps booted", "plutil -p Info.plist", "vtool -show-build App", "xcrun devicectl list devices",
                 "xcode-select -p", "xcodebuild -version"]
        writes = ["xcrun simctl create a b c", "xcrun simctl boot X", "xcrun simctl install booted A.app",
                  "xcrun simctl io booted screenshot a.png", "plutil -convert xml1 a.plist", "plutil -p a -o b",
                  "vtool -set-build-version 1 a -output b", "xcodebuild -scheme A build", "xcrun $T list", "python3 -c 'print(1)'",
                  "plutil -lint a.plist", "xcodebuild -showsdks",
                  "xcrun devicectl list devices --json-output p.json", "xcrun devicectl list devices -j p.json",
                  "xcrun devicectl list devices --log-output=l.txt", "xcrun devicectl list devices -l l.txt"]   # 무쓰기 대조를 남기지 않은 꼴은 표 밖이다
        got_r = [(c, bash_write(c)) for c in reads]
        got_w = [(c, bash_write(c)) for c in writes]
        case("apple-read-forms — 승인 전 창의 읽기 전용 iOS 도구는 읽기 · 같은 도구의 쓰기 꼴과 인터프리터는 대상 미상 쓰기(F-583)",
             all(g == (False, []) for _, g in got_r) and all(g == (True, []) for _, g in got_w),
             ([x for x in got_r if x[1] != (False, [])], [x for x in got_w if x[1] != (True, [])]))

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
                                            "mkdir -p /srv/demo/NOTASK-20261110 2>/dev/null", "mkdir -p /srv/demo/NOTASK-20261110-wave3")]
        den = [kind(s.pre("Bash", B(c))) for c in ("rm -rf /srv/demo/NOTASK-20261110", "mkdir -p /srv/demo/other",
                                                   "cd /tmp && mkdir -p NOTASK-20261110", "mkdir -p /srv/demo/x/NOTASK-20261110", 'mkdir -p "$W"',
                                                   "rm -rf /srv/demo/NOTASK-20261110-wave3")]
        case("r3-s1-mandated-preapproval-read — /fz Phase 0~4 본문의 플러그인 스크립트 호출(본문에서 뽑는다)과 Phase 0 WORK_DIR mkdir 은 승인 전에 "
             "막히지 않는다 · WORK_DIR 지우기 · 다른 폴더 · 이동 뒤 · 펼친 mkdir 은 막힌다",
             any("gpt-choice.sh" in c for c in cmds) and not bad and mk == [None] * 5 and den == ["deny"] * 6, (cmds, bad, mk, den))

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
    def r4_awk_grid():
        # 리터럴 종류 → (프로그램 꼴 · 리터럴 종류) — {c} = 리터럴 안 글자 · {act} = 같은 동작 안 뒤 문장. 정규식 자리 = '/' 앞의 공백 아닌 글자가
        #   없거나 ( , { } ; ! ~ & | ? : = 줄바꿈이다 — 나눗셈 · print 뒤 '/' 는 리터럴로 보지 않고, 그 뒤에 리터럴이 열리면 원문 판정이다
        kinds = {"head": ("/{c}/ {{ print $1{act} }}", "regex"), "tilde": ("$1 ~ /{c}/ {{ print $2{act} }}", "regex"),
                 "not-tilde": ("$1 !~ /{c}/ {{ print $2{act} }}", "regex"), "arg": ("{{ if (match($0, /{c}/)) print RSTART{act} }}", "regex"),
                 "string": ('{{ print "{c}"{act} }}', "string"), "division": ("{{ x = $1 /{c}/ 2; print x{act} }}", None),
                 "after-print": ("{{ print /{c}/{act} }}", None)}
        pipes = {"inside": "", "print-cmd": '; print $0 | "sort"', "cmd-getline": '; "date" | getline d', "coproc": '; print $0 |& "sort"',
                 "or": "; if ($1 || $2) n++"}
        escapes = {"none": "", "slash": "\\/", "quote": '\\"', "bracket": "[/]"}
        marks = {"none": "", "print-redirect": '; print $0 > "out.txt"', "system": '; system("date")'}

        def dq(p):                                  # 펼쳐지는 프로그램 — 큰따옴표 안 앞머리 ${P}
            return '"${P}' + p.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`") + '"'
        bad, n = [], 0
        for kn, (shape, lit) in kinds.items():
            for pn, act in pipes.items():
                for en, esc in escapes.items():
                    for mn, mark in marks.items():
                        prog = shape.format(c="a" + esc + ("|" if pn == "inside" else "") + "b", act=act + mark)
                        for form, word in (("literal", "'" + prog + "'"), ("expanded", dq(prog))):
                            # 판정이 바뀌는 칸: `|` 가 정규식 자리 /…/ · 문자열 안에만 있다(대괄호 안 '/' 에서 끝나는 정규식은 원문 판정)
                            lit_pipe = pn == "inside" and (lit == "string" or (lit == "regex" and en != "bracket"))
                            want = not (form == "literal" and mn == "none" and (pn == "or" or lit_pipe))
                            got, n = bash_write(f"awk {word} f"), n + 1
                            if got != (want, []):
                                bad.append((f"awk {word} f", got))
        # 닫히지 않은 리터럴(같은 줄에 닫는 글자 없음)은 지우지 않는다 · 리터럴 뒤 '/' 는 나눗셈이다 · 줄 이음(역슬래시 줄바꿈) 뒤 '/' 도 그 앞 글자로
        #   가린다 — 뒤의 진짜 파이프가 남는다
        bad += [c for c in ("awk '/a|b { print | \"sh\" }' f", "awk '{ print \"a|b }' f", "awk '/a\n|b/ { print }' f",
                            "awk '{ x = \"10\" / 2; print x | \"sh\"; y = z / 3 }' f", "awk '{ x = $1 \\\n/ 2; print x | \"sh\"; y = z / 3 }' f")
                if bash_write(c) != (True, [])]
        case(f"r4-awk-literal-pipe-grid — awk 프로그램의 리터럴 종류 × `|` 자리 × 이스케이프 × 다른 쓰기 표지 × 펼침({n}칸): 정규식 자리 /…/ · 문자열 "
             "안 `|` 만 파이프가 아니다 · print | · | getline · |& · print > · system( · 펼친 프로그램 · 나눗셈 뒤 '/' · 닫히지 않은 리터럴은 쓰기 그대로",
             n == 840 and not bad, (len(bad), bad[:3]))

    @cell
    def rp_g03_awk_unsettled():
        # 리터럴 경계를 정하지 못하는 꼴 — 훑기가 나눗셈으로 본 '/'(print · printf · return · + 뒤)가 awk 에서는 정규식이고 그 안 따옴표 · '/' 가
        #   뒤의 진짜 파이프를 지운다 · 대괄호 안 '/'(gawk 는 거기서 닫지 않는다) → 원문의 `|` 로 판정한다
        writes = ["awk '{ print /a\"b/; print | \"sh\" }' f.txt", "awk '/[/]\"/ { print | \"sh\" }' f.txt", "awk '{ print | \"sh\" }' f.txt",
                  "awk 'BEGIN { print /\"/ | \"touch out.txt\" }'", "awk '{ printf /a\"b/; print | \"sh\" }' f.txt",
                  "awk 'function f() { return /a\"b/ } { print | \"sh\" }' f.txt", "awk '{ x = 1 + /a\"b/; print | \"sh\" }' f.txt",
                  "awk '{ print /a=/; print | \"sh\"; y = /c/ }' f.txt", "awk '/[[:alpha:]/]\"/ { print | \"sh\" }' f.txt"]
        reads = ["awk '{ print $1 }' f.txt", "awk '/a|b/ { print $1 }' f.txt", "awk '$1 ~ /x\"|y/ { print }' f.txt", "awk '/[a-z]|x/ { n++ }' f.txt",
                 "awk '{ print \"a|b\", $1 / 2 }' f.txt", "awk '/a|b/ { x = $1 / 2 }' f.txt"]   # 경계가 정해진 꼴 · 리터럴 뒤 나눗셈
        bad = [c for c in writes if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c) != (False, [])]
        case("rp-g03-awk-unsettled-literal — awk 프로그램에서 나눗셈으로 본 '/' 뒤에 리터럴이 다시 열리거나 정규식 안 대괄호가 닫히기 전에 '/' 를 만나면 "
             "원문의 `|` 로 판정한다(print · printf · return · 연산자 뒤 정규식 · [/] 의 따옴표가 진짜 파이프를 숨기지 못한다) · 경계가 정해진 꼴은 읽기",
             not bad, bad)

    @cell
    def r4_print_grid():
        opts = {"": True, "-r": True, "-n": True, "-l": True, "--": True, "-rn": True, "-r --": True, "-s": False, "-z": False, "-u 2": False,
                "-p": False, "-S": False, "-v out": False, "-": False, "-$O": False}
        tails = {"": True, " 2>/dev/null": True, " > /w/work/out.txt": False, " >> /w/work/out.txt": False}
        bad, n = [], 0
        with login_shell("/bin/zsh"):
            for o, o_ok in opts.items():
                for a in ("hello", '"$x"', "-s"):
                    for t, t_ok in tails.items():
                        cmd = " ".join(x for x in ("print", o, a) if x) + t
                        read = o_ok and t_ok and (a == "hello" or "--" in o.split())   # 옵션 뒤 `-s` · 펼침은 `--` 뒤에서만 값이다
                        got, n = bash_write(cmd), n + 1
                        if got[0] == read:
                            bad.append((cmd, got))
        case(f"r4-zsh-print-grid — zsh print 의 옵션 × 인자 × 리다이렉트({n}칸): -r · -n · -l · -- 만 든 꼴은 읽기 · -s · -z · -u · -p · -S · -v · - · "
             "펼친 옵션 · `--` 앞 -s · 펼친 인자 · 진짜 리다이렉트는 쓰기", not bad, (len(bad), bad[:3]))

    @cell
    def rp_g01_print():
        # 옵션이 설 수 있는 자리(`--` · 첫 글자 그대로의 피연산자 앞)의 펼침은 옵션이 될 수 있다(`O=-v` → print -v 는 변수에 쓴다 · 빈 값은 사라진다)
        writes = ['O=-v; print "$O" answer hi', "print ${O} hi", "print -r $(printf %s -s) x", "print -n `echo -z` x", 'print -l "$O" -- x',
                  "print -v answer hi"]
        reads = ['print -- "$O" answer', "print -r -- ${O} x", 'print hello "$O"', "print -rn -- $(date +%F)"]   # `--` · 첫 피연산자 뒤는 값
        with login_shell("/bin/zsh"):
            bad = [c for c in writes if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c) != (False, [])]
        case("rp-g01-print-expansion-option — zsh print 의 `--` · 첫 글자 그대로의 피연산자 앞 펼침(\"$O\" · ${O} · $(…) · 백틱)은 옵션이 될 수 있어 "
             "쓰기 · `--` 뒤 · 첫 피연산자 뒤 펼침은 값이라 읽기", not bad, bad)

    @cell
    def rp_k01_print_brace_glob():
        # 따옴표 밖 중괄호 · 글롭은 셸이 print 를 띄우기 전에 여러 낱말로 편다(`print {-v,answer,hi}` → print -v answer hi — 변수에 쓴다).
        #   토크나이저의 quoted 는 단어 어딘가에 따옴표가 있다는 표시라 `""{…}` 처럼 일부만 따옴표인 단어도 편다
        brace = ["print {-v,answer,hi}", 'print ""{-v,answer,hi}', "print -r {-v,x}", "print {1..3}", 'echo $(print ""{-v,a,b})',
                 'echo `print ""{-v,a,b}`']
        glob = ["print *", "print -n gates/*.md", "print ?", "print [-]v x", 'print "gates/"*.md']
        reads = ["print '{-v,a}'", 'print "{-v,a}"', "print \\{-v,a\\}", "print '{'-v,a'}'", 'print "hello"', "print '*'", 'print "gates/*.md"',
                 "print \\*", "print hello {-v,x}", "print -- {-v,x}", "print -r -- gates/*.md"]   # 따옴표 · 이스케이프 안 · `--` · 첫 피연산자 뒤는 값
        with login_shell("/bin/zsh"):
            bad = [c for c in brace + glob if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c) != (False, [])]
        case("rp-k01-print-brace-glob — zsh print 의 `--` · 첫 글자 그대로의 피연산자 앞 따옴표 밖 중괄호 펼침 · 글롭(일부만 따옴표인 단어 · 치환 안 포함)은 "
             "옵션이 될 수 있어 쓰기 · 따옴표 · 이스케이프 안 글자 · `--` 뒤 · 첫 피연산자 뒤는 읽기", not bad, bad)

    @cell
    def rp_g05_print_zsh_only():
        got = []
        for sh in ("/bin/zsh", "/usr/local/bin/zsh", "/bin/bash", "/bin/sh", "", None):
            with login_shell(sh):
                got.append(bash_write("print -r -- x"))
        case("rp-g05-print-zsh-session-only — print 읽기 꼴은 SHELL 의 basename 이 zsh 일 때만 읽기다 · bash · sh · 빈 값 · 없음이면 print 는 PATH 의 "
             "다른 프로그램일 수 있어 대상 미상 쓰기", got == [(False, [])] * 2 + [(True, [])] * 4, got)

    @cell
    def r4_case_grid():
        bodies = {"echo a": False, "ls -la /w/work": False, "grep -c x /w/work/a.md 2>/dev/null": False, "touch /w/work/flag": True,
                  "echo x > /w/work/out.txt": True, "python3 -c 'print(1)'": True}
        shapes = {"first": "{p} {b};; b) echo b;; *) echo c;;", "second": "{p} echo a;; b) {b};; *) echo c;;",
                  "default": "{p} echo a;; b) echo b;; *) {b};;", "no-last-semi": "{p} echo a;; *) {b}\n", "lines": "\n  {p}\n    {b}\n    ;;\n"}
        ctx = {"alone": ("{c}", False), "for": ("for m in a b; do {c}; done", False), "subst": ('r=$({c}); echo "$r"', False),
               "pipe": ("{c} | grep a", False), "then": ("{c}; ls /w/work", False), "if": ("if true; then {c}; fi", False),
               "esac-redirect": ("{c} > /w/work/o.txt", True)}
        bad, n = [], 0
        for b, b_w in bodies.items():
            for p in ("a)", "a|b)", "(a)", "*.md)", '"$k")'):
                for sh in shapes.values():
                    c = 'case "$m" in ' + sh.format(p=p, b=b) + " esac"
                    for shape, c_w in ctx.values():
                        cmd = shape.format(c=c)
                        got, n = bash_write(cmd), n + 1
                        if got[0] != (b_w or c_w):
                            bad.append((cmd, got))
        # 펴지 않는 꼴(Unknown → 쓰기) · 갈래 안 정의(if 안 정의처럼 면제 근거가 아니다) · 여러 복합문
        unknown = ["case $m in a) echo a;& b) echo b;; esac", "case $m in a) echo a;;& b) echo b;; esac",
                   "case $m in a) case $n in b) echo b;; esac;; esac", "case $m in a) echo a; case $n in b) echo b;; esac;; esac",
                   "echo `case $m in a) echo a;; esac`", "case $m in a) cat <<EOF\nx\nEOF\n;; esac", "case $m in @(a|b)) echo a;; esac",
                   "case $m in a) f() { :; };; esac", "case $m in a) echo a;;", "case $m\nin a) echo a;; esac"]
        writes = ["case $m in a) echo a; rm() { :; };; esac; rm -rf /w/work/build", "case $m in a) echo a;; esac; case $n in b) touch /w/work/f;; esac"]
        reads = ["case $m in a) echo a;; esac; case $n in b) ls;; esac", "rm() { :; }; case $m in a) rm -rf /w/work/build;; esac", "case $m in esac",
                 "case $m in a) echo esac;; b) ls;; esac"]                      # 인자 자리 esac 는 복합문을 닫지 않는다
        bad += ([c for c in unknown if bash_write(c) != (True, [])] + [c for c in writes if not bash_write(c)[0]]
                + [c for c in reads if bash_write(c)[0]])
        case(f"r4-case-compound-grid — case 복합문(갈래 본문 × 패턴 꼴 × 갈래 자리 × 배치 × 문맥 {n}칸)은 복합문 자체가 쓰기가 아니고 갈래 본문을 각자 "
             "판정한다(어느 갈래의 쓰기든 쓰기 · esac 뒤 리다이렉트는 쓰기) · ;& · ;;& · 중첩 · 백틱 · heredoc · extglob · 본문 첫 정의 · esac 없음은 쓰기",
             not bad, (len(bad), bad[:3]))

    @cell
    def rp_g02_case_bound():
        one = 'case "$x" in a) echo 0;; esac'
        got = [bash_write("; ".join([one] * k)) for k in (CASE_MAX - 1, CASE_MAX, CASE_MAX + 1)]
        case(f"rp-g02-case-bound — 읽기만 든 case 복합문 {CASE_MAX - 1} · {CASE_MAX}개(CASE_MAX)는 읽기 · {CASE_MAX + 1}개는 상한 밖이라 대상 미상 쓰기",
             got == [(False, [])] * 2 + [(True, [])], got)

    @cell
    def r4_gate_status_grid():
        heads = {"python3 scripts/gate_check.py": True, 'python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py"': True,
                 "python3 /x/plugin/scripts/gate_check.py": True, "scripts/gate_check.py": True, "python3 other/gate_check.py": False,
                 'python3 "$G"': False, "python3 -B scripts/gate_check.py": False}
        tails = {"--status gates/plan.md": True, '--status "$L"': False, "--status gates/plan.md 2>&1": True, "--status": False,
                 "--status --only S1 gates/plan.md": False, "--confirm G1 gates/plan.md": False, "--set-state active gates/plan.md": False,
                 "gates/plan.md": False, "--stat gates/plan.md": False, "--finalize gates/plan.md": False, "--status gates/plan.md gates/b.md": False,
                 "gates/plan.md --status": False, '"$SUB" gates/plan.md': False, "--status gates/plan.md > /w/work/o.txt": False,
                 "--status --reverify": False}
        got = {f"{h} {t}": bash_write(f"{h} {t}") for h in heads for t in tails}
        bad = [(f"{h} {t}", got[f"{h} {t}"]) for h, h_ok in heads.items() for t, t_ok in tails.items() if got[f"{h} {t}"][0] == (h_ok and t_ok)]
        case(f"r4-gate-check-status-grid — 판정기 호출 꼴 × 인자({len(got)}칸): scripts/gate_check.py --status <원장> 만 플러그인 읽기 · 다른 인자 · "
             "인자 하나 더 · 축약 · 펼친 하위 자리 · 펼친 원장 · 경로 밖 이름 · 인터프리터 옵션 · 진짜 리다이렉트는 쓰기", not bad, bad[:3])

    @cell
    def rp_g01_gate_status():
        # 원장 자리의 펼침은 옵션 하나 또는 여럿이 될 수 있다(`$ARGS` → --set-state active …) — `--status <글자 그대로의 경로>` 만 읽기다
        g = "python3 scripts/gate_check.py --status"
        writes = [f'ARGS="--set-state active gates/plan.md"; {g} $ARGS', f'{g} "$L"', f"{g} ${{L}}", f"{g} $(ls gates/plan.md)", f"{g} `ls gates`",
                  f'{g} "$W/gates/plan.md"']
        reads = [f"{g} gates/plan.md", 'python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py" --status /w/work/gates/plan.md']
        bad = [c for c in writes if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c) != (False, [])]
        case("rp-g01-gate-status-expansion — gate_check.py --status 뒤 원장 자리의 펼침(`$ARGS` · \"$L\" · ${L} · $(…) · 백틱 · \"$W/…\")은 옵션이 될 수 "
             "있어 쓰기 · 글자 그대로의 원장만 읽기(스크립트 경로의 펼침은 그대로 받는다)", not bad, bad)

    @cell
    def rp_k01_gate_status_brace_glob():
        # 원장 자리의 따옴표 밖 중괄호 · 글롭은 셸이 여러 낱말로 편다(`{--set-state,active,gates/plan.md}` → --set-state active gates/plan.md)
        g = "python3 scripts/gate_check.py --status"
        brace = [f"{g} {{--set-state,active,gates/plan.md}}", f'{g} ""{{--set-state,active,gates/plan.md}}', f"{g} gates/{{plan,b}}.md",
                 f"{g} {{1..2}}"]
        glob = [f"{g} gates/*.md", f"{g} gates/plan.m?", f"{g} gates/[p]lan.md", f'{g} "gates/"*.md']
        reads = [f"{g} '{{--set-state,active}}'", f'{g} "{{--set-state,active}}"', f"{g} \\{{--set-state,active\\}}", f"{g} gates/plan.md",
                 f"{g} 'gates/*.md'", f"{g} gates/\\*.md"]
        bad = [c for c in brace + glob if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c) != (False, [])]
        case("rp-k01-gate-status-brace-glob — gate_check.py --status 뒤 원장 자리의 따옴표 밖 중괄호 펼침 · 글롭(일부만 따옴표인 단어 포함)은 원장이 여럿 · "
             "옵션이 될 수 있어 쓰기 · 따옴표 · 이스케이프 안 글자와 글자 그대로의 원장은 읽기", not bad, bad)

    @cell
    def rp_g04_gate_status_env():
        # gate_check.py 는 FZ_GATES_TRACE 가 가리키는 파일에 호출 기록을 덧붙인다 — 환경 대입 · env 래퍼를 앞에 둔 꼴은 읽기가 아니다
        g = "python3 scripts/gate_check.py --status gates/plan.md"
        writes = [f"FZ_GATES_TRACE=/w/work/trace.jsonl {g}", f"env FZ_GATES_TRACE=/w/work/trace.jsonl {g}", f"env {g}", f"LC_ALL=C {g}",
                  f"X=1 2>/dev/null {g}", f"echo a; FZ_GATES_TRACE=/w/work/t.jsonl {g}"]
        reads = [g, f"{g} 2>&1", f"echo a && {g}"]
        bad = [c for c in writes if bash_write(c) != (True, [])] + [c for c in reads if bash_write(c) != (False, [])]
        case("rp-g04-gate-status-env-prefix — gate_check.py --status 앞에 환경 대입(NAME=값) · env 래퍼가 있으면 대상 미상 쓰기(FZ_GATES_TRACE 가 쓸 "
             "파일을 정한다) · 맨 꼴은 읽기", not bad, bad)

    @cell
    def r4_nw173():
        s = fz("r4c")
        parts = ["grep -n 'Phase 4' skills/fz/SKILL.md", "awk '/autonomy|gpt-choice/ {print NR}' skills/fz/SKILL.md",
                 "python3 scripts/autonomy_decide.py --help", 'bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" get']
        chains = [" ; ".join(parts), " && ".join(parts), parts[0] + " 2>&1 | awk '/a|b/ {print}'; " + parts[2],
                  parts[0] + " | awk '/a|b/ {print}' && " + parts[3]]
        got = [s.pre("Bash", B(c)) for c in parts + chains]
        deny = kind(s.pre("Bash", B(parts[0] + " | awk '{print | \"sh\"}'; " + parts[2])))
        case("r4-nw173-preapproval-chain — 승인 전 창에서 부르는 조각(grep · awk 정규식 a|b · autonomy_decide · gpt-choice get)과 `;` · `&&` · `|` · "
             "`2>&1` 로 이은 묶음은 막히지 않는다 · awk 프로그램의 진짜 파이프를 이은 묶음은 막힌다", got == [None] * len(got) and deny == "deny", (got, deny))

    @cell
    def r4_p4_replay():
        # 승인 전 창이 실제로 막던 Bash 의 꼴 — 기계 경로는 /x/plugin · /w/work 로 바꿨다. 읽기 꼴만 든 명령은 풀리고 쓰기가 든 명령은 막힌다
        reads = ["grep -n 'P4' /x/plugin/mods/fz-guard/hooks/guard.py | awk -F: '/awk|print/ {print $1}'",
                 "awk '{ printf \"%s | %s\\n\", $1, $2 }' /w/work/table.tsv", "sed -n '1,40p' /w/work/index.md | awk '/^## (Plan|Gates)/ {print NR}'",
                 'print -r -- "/w/work/plan.md"', 'for f in /w/work/*.md; do case "$f" in */index.md) echo skip;; *) wc -l "$f";; esac; done',
                 "python3 /x/plugin/scripts/gate_check.py --status /w/work/gates/plan.md"]
        writes = ["python3 -c 'import json; print(json.load(open(\"/w/work/a.json\"))[\"k\"])'",
                  "python3 - <<'EOF'\nimport json\nprint(json.load(open('/w/work/a.json')))\nEOF",
                  "awk '{print $1}' /w/work/a.tsv > /w/work/b.txt", 'print -r -- "$x" > /w/work/out.md']
        s = fz("r4rp")
        with login_shell("/bin/zsh"):                # print -- 꼴은 zsh 세션에서만 읽기다
            got = [kind(s.pre("Bash", B(c))) for c in reads + writes]
        case(f"r4-p4-blocked-replay — 승인 전 창이 막던 꼴 재현: 읽기 꼴만 든 {len(reads)}개(awk 정규식 · 문자열 안 `|` · print -- · case · "
             f"gate_check --status)는 풀리고 쓰기가 든 {len(writes)}개(인터프리터 코드 · 진짜 리다이렉트)는 막힌다",
             got == [None] * len(reads) + ["deny"] * len(writes), got)

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
    def function_order():
        got = [bash_write(c, "/srv/demo") for c in ("rm -rf build; rm() { echo no; }", "touch x; touch() { :; }", "x=$(touch a); touch() { :; }",
                                                    "rm() { echo no; }; rm -rf build", "f() { g; }; g() { :; }; f",
                                                    "touch() { :; }; echo $(touch gates/plan.md)")]
        case("function-exempt-after-definition-only — 같은 이름 함수 면제는 정의 뒤의 맨 이름 호출만이다: 정의보다 앞선 호출 · 정의 앞 치환 안 호출 · "
             "본문보다 뒤에 정의된 함수의 본문 안 호출(감싼 함수를 그 정의 뒤에 불러도 — 과차단 쪽)은 외부 명령(쓰기) · 정의 뒤 호출 · 정의 뒤 치환 안 호출은 면제",
             got == [(True, ["build"]), (True, ["x"]), (True, []), (False, []), (True, []), (False, [])], got)

    @cell
    def function_body_order():
        got = [bash_write(c, "/srv/demo") for c in ("f() { rm -rf build; }; f; rm() { :; }", "f() { rm -rf build; }; rm() { :; }; f",
                                                    "f() { tee build/x; }; f; tee() { :; }", "f() { mkdir -m 700 build/y; }; f; mkdir() { :; }",
                                                    "rm() { :; }; f() { rm -rf build; }; f", "f() { helper gates/plan.md; }; helper() { :; }; f",
                                                    "f() { helper gates/plan.md; }; f; helper() { :; }")]
        case("function-body-write-command-needs-earlier-definition — 함수 본문 안 호출은 이름과 무관하게(쓰기 명령 tee · rm · touch · mkdir · cp · mv "
             "· 그 밖 이름) 본문보다 앞의 맨 바깥 같은 이름 정의만 면제한다: 뒤 정의(본문이 정의 전에 불리든 뒤에 불리든 · 표 밖 옵션 · main · helper "
             "꼴 포함)는 외부 명령(대상 미상 쓰기) · 앞 정의는 면제",
             got == [(True, [])] * 4 + [(False, [])] + [(True, [])] * 2, got)

    @cell
    def function_conditional_definition():
        miss = ("false && touch() { :; }; touch x", "true || touch() { :; }; touch x", "if false; then touch() { :; }; fi; touch x",
                "if true; then :; else touch() { :; }; fi; touch x", "while false; do touch() { :; }; done; touch x")
        over = ("true && touch() { :; }; touch x", "if true; then touch() { :; }; fi; touch x")
        keep = ("touch() { :; } && false; touch x", "touch() { :; } || true; touch x", "{ touch() { :; }; }; touch x",
                "true && false; touch() { :; }; touch x")
        got = [bash_write(c, "/srv/demo") for c in miss + over + keep]
        case("function-conditional-definition — `&&` · `||` 뒤와 if · 루프 안 정의는 조건과 무관하게 면제 근거가 아니다: 돌지 않는 조건 · 갈래 "
             "뒤의 호출은 외부 명령(쓰기) · 도는 조건도 쓰기(과차단 고정) · 목록 첫 명령 · 묶음 안 정의 · 앞 목록이 끝난 뒤 목록의 첫 정의는 면제",
             got == [(True, ["x"])] * 7 + [(False, [])] * 4, got)

    @cell
    def function_body_outside_name_order():
        got = [bash_write(c, "/srv/demo") for c in ("f() { unlink build/x; }; f; unlink() { :; }", "f() { sed -i '' s/a/b/ x; }; f; sed() { :; }",
                                                    "f() { python3 -c 'print(1)'; }; f; python3() { :; }",
                                                    "sed() { :; }; f() { sed -i '' s/a/b/ x; }; f", "helper() { :; }; f() { helper x; }; f")]
        case("function-body-outside-name-order — 쓰기 명령 밖 이름(읽기 표 밖 프로그램 · 쓰기 옵션을 든 읽기 명령 · 인터프리터)의 본문 안 호출도 "
             "본문보다 앞의 정의만 면제한다: 본문 → 감싼 함수 호출 → 같은 이름 정의 꼴은 bash 가 외부 명령을 돌린다(대상 미상 쓰기) · 앞 정의는 면제",
             got == [(True, [])] * 3 + [(False, [])] * 2, got)

    @cell
    def r4_selfcall_grid():
        spots = {"head": "{x}; {r}", "and": '{r}; [ -n "$1" ] && {x}', "or": '{r}; [ -z "$1" ] || {x}', "if": '{r}; if [ -n "$1" ]; then {x}; fi',
                 "pipe": "{r} | {x}", "subst": '{r}; echo "$({x})"', "subshell": "{r}; ( {x} )", "nested": "{r}; g() {{ {x}; }}"}
        forms = {"bare": ("f a", True), "command": ("command f a", False), "path": ("./f a", False), "quoted": ('"f" a', True)}
        rests = {"read": ("grep -r foo .", True), "redirect": ("grep -r foo . > out.txt", False), "rm": ("rm -rf build", False)}
        outers = {"after": ("{d}; f x", True), "none": ("{d}", True), "before": ("f x; {d}", False)}
        bad, n = [], 0
        for spot in spots.values():
            for x, x_ok in forms.values():
                for r, r_ok in rests.values():
                    for outer, o_ok in outers.values():
                        for un in ("none", "body", "outer"):
                            d = "f() { " + ("unset -f f; " if un == "body" else "") + spot.format(x=x, r=r) + "; }"
                            cmd = outer.format(d=d) + ("; unset -f f" if un == "outer" else "")
                            got, n = bash_write(cmd, "/srv/demo"), n + 1
                            if got[0] != (not (x_ok and r_ok and o_ok and un == "none")):
                                bad.append((cmd, got))
        case(f"r4-recursive-self-call-grid — 자기 호출 자리 × 호출 꼴 × 본문의 나머지 × 바깥 호출 × unset({n}칸): 본문 안 맨 이름(따옴표 이름 포함) 자기 "
             "호출은 함수다 — 본문이 읽기만이고 unset 이 없고 바깥 호출이 정의 뒤이거나 없으면 읽기 · command · 경로 호출 · 본문 쓰기 · unset · 정의 앞 "
             "바깥 호출은 쓰기", n == 864 and not bad, (len(bad), bad[:3]))

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
        s = fz("c24")
        o = s.pre("Agent", {"subagent_type": "fz:review-arch", "prompt": "x"})
        again = s.pre("Agent", {"subagent_type": "fz:review-arch", "prompt": "y"})       # 같은 prompt · 같은 종류 — 경고는 한 번
        other = s.pre("Agent", {"subagent_type": "general-purpose", "prompt": "x"})      # 다른 종류는 따로 알린다
        s.prompt("/fz 다른 일", "p2")
        later = s.pre("Agent", {"subagent_type": "fz:review-arch", "prompt": "x"})       # 새 prompt 는 다시 알린다
        case("f058-ad-hoc-agent-warned — fz 세션의 허용 목록 밖 에이전트는 막지 않고 알린다(Workflow 경유 규칙 · prompt · 종류마다 1회)",
             kind(o) is None and warned(o, "fz-guard AG") and warned(o, "Workflow") and again is None and warned(other, "fz-guard AG")
             and warned(later, "fz-guard AG"), (o, again, other, later))

    @cell
    def c25():
        o = fz("c25").pre("Task", {"subagent_type": "general-purpose", "prompt": "x"})
        case("task-adhoc-in-fz-warned", kind(o) is None and warned(o, "fz-guard AG"), o)

    @cell
    def c26():
        s = fz("c26")
        got = [s.pre("Agent", {"subagent_type": t}) for t in ("pr-review-toolkit:silent-failure-hunter",
                                                              "pr-review-toolkit:code-simplifier", "pr-review-toolkit:type-design-analyzer")]
        case("agent-native-allowlisted", got == [None] * 3, got)

    @cell
    def c26b():
        o = fz("c26b").pre("Agent", {"subagent_type": "deep-research-agent"})
        case("agent-outside-allowlist-warned", kind(o) is None and warned(o, "fz-guard AG"), o)

    @cell
    def c26c():
        s = fz("c26c")
        got = [s.pre("Agent", {"subagent_type": t}) for t in ("silent-failure-hunter", "other:silent-failure-hunter")]
        case("agent-allowlist-exact-prefixed-name-only", all(kind(o) is None and warned(o, "fz-guard AG") for o in got), got)

    @cell
    def c26d():
        s = fz("c26d")
        got = [s.pre("Agent", {"subagent_type": t, "model": "opus", "prompt": "x"}) for t in ("fz:review-correctness", "fz:search-pattern")]
        case("agent-fz-lead-direct-allowed", got == [None] * 2, got)

    @cell
    def rp_g07_memory_curator():
        s = fz("rpg07")
        cur = s.pre("Agent", {"subagent_type": "fz:memory-curator", "model": "sonnet", "prompt": "x"})
        other = s.pre("Agent", {"subagent_type": "fz:plan-structure", "prompt": "x"})
        case("rp-g07-memory-curator-lead-direct — 스킬이 Lead 에게 직접 띄우라고 적은 fz:memory-curator 는 알리지 않는다 · 목록 밖 fz 에이전트는 그대로 알린다",
             cur is None and kind(other) is None and warned(other, "fz-guard AG"), (cur, other))

    @cell
    def c26e():
        s = fz("c26e")
        got = [s.pre("Agent", {"subagent_type": t}) for t in ("fz:impl-correctness", "fz:plan-structure", "search-pattern", "review-correctness")]
        case("agent-fz-other-or-unprefixed-warned", [kind(o) for o in got] == [None] * 4
             and all(warned(o, "Lead 가 직접 띄우는 fz 에이전트") for o in got), got)

    adopted = ["pr-review-toolkit:silent-failure-hunter", "pr-review-toolkit:type-design-analyzer", "pr-review-toolkit:code-simplifier"]
    lead = ["fz:review-correctness", "fz:search-pattern", "fz:memory-curator"]

    def allow_check(tag, adopted_names, lead_names):
        """채택 표 · Lead 직접 표를 가진 합성 문서로 --check-allowlist 를 돈다 — 이름 목록이 None 이면 그 표가 없다."""
        def table(head, names):
            return "" if names is None else head + "".join(f"| **{n}** | x | x |\n" for n in names)
        md = (table("| 에이전트 | 고유 가치 | 스폰 방식 |\n|---|---|---|\n", adopted_names) + "\n## 다음\n\n"
              + table("| 에이전트 | Lead 가 띄우는 때 | 정하는 스킬 |\n|---|---|---|\n", lead_names))
        p = tmp / f"allow-{tag}.md"
        p.write_text(md, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = check_allowlist(str(p))
        return code, buf.getvalue().strip()

    @cell
    def c26f():
        got = [allow_check("a-" + t, a, lead) for t, a in (("ok", adopted), ("doc-only", adopted + ["pr-review-toolkit:pr-test-analyzer"]),
                                                            ("guard-only", adopted[1:]), ("missing", None))]
        case("allowlist-adopted-table-compared", [c for c, _ in got] == [0, 1, 1, 2] and all("MISMATCH" in o for _, o in got[1:3]), got)

    @cell
    def c26g():
        got = [allow_check("l-" + t, adopted, ln) for t, ln in (("doc-only", lead + ["fz:impl-correctness"]), ("guard-only", lead[1:]), ("missing", None))]
        case("allowlist-lead-table-compared", [c for c, _ in got] == [1, 1, 1] and all("MISMATCH" in o for _, o in got), got)

    @cell
    def c26h():
        d = tmp / "c26h"
        d.mkdir()
        (d / "bad.md").write_bytes(b"\xff| **pr-review-toolkit:code-simplifier** | x | x |\n")
        got = []
        for p in (d / "none.md", d, d / "bad.md"):               # 경로 없음 · 폴더 · UTF-8 아닌 파일
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    code = check_allowlist(str(p))
            except Exception as e:                  # noqa: BLE001 — 디코딩 실패가 새면 traceback · exit 1(불일치처럼 보인다)
                code = repr(e)
            got.append((code, buf.getvalue().strip()))
        case("allowlist-unreadable-unrun — 표 파일을 읽지 못하면(없음 · 폴더 · UTF-8 아님) exit 2 · `UNRUN: 표를 읽지 못했다` 다",
             all(c == 2 and "UNRUN: 표를 읽지 못했다" in o for c, o in got), got)

    @cell
    def c27():
        s = S("c27")
        s.prompt("조사해줘", "p1")
        case("agent-no-fz-allowed", s.pre("Agent", {"subagent_type": "Explore"}) is None)

    def lesson(s):
        s.post("Write", {"file_path": mem, "content": "fz-plan 교훈 — F-518 재발"})

    def fr_on(tag, **kw):                           # FR 은 FZ_FINDINGS_ROOT 가 있을 때만 돈다 — 막힘 · 면제를 재는 셀은 빈 레지스트리를 준다
        return S(tag, FZ_FINDINGS_ROOT=str(reg_root(tag)), **kw)

    @cell
    def c28():
        s = fr_on("c28")
        s.prompt("분석해줘", "p1")
        lesson(s)
        o = s.stop()
        case("f518-memory-only-lesson-blocked", blocked(o) and "F-518" in o.get("reason", ""), o)

    @cell
    def c29():
        s = fr_on("c29")
        s.prompt("분석해줘", "p1")
        lesson(s)
        s.post("Write", {"file_path": reg, "content": "x"})
        case("stop-registry-written-allowed", s.stop() is None)

    @cell
    def c30():
        s = fr_on("c30")
        s.prompt("분석해줘", "p1")
        lesson(s)
        s.pre("Write", {"file_path": reg, "content": "x"})      # 실패한 쓰기 — PostToolUse 가 오지 않는다(PostToolUseFailure)
        case("stop-registry-write-failed-blocked", blocked(s.stop()))

    @cell
    def c31():
        r = reg_root("c31")
        a, b = S("c31", sid="sa", FZ_FINDINGS_ROOT=str(r)), S("c31", sid="sb", FZ_FINDINGS_ROOT=str(r))
        a.prompt("분석해줘", "p1")
        lesson(a)
        b.prompt("다른 세션", "p1")
        case("stop-other-session-ignored", b.stop() is None)

    @cell
    def c32():
        s = fr_on("c32")
        s.prompt("분석해줘", "p1")
        lesson(s)
        first, second = s.stop(), s.stop()
        case("stop-same-fingerprint-second-passes", blocked(first) and second is None, f"{first} · {second}")

    @cell
    def c33():
        s = fr_on("c33")
        s.prompt("분석해줘", "p1")
        lesson(s)
        active = s.stop(active=True)
        case("stop-hook-active-passes", active is None and blocked(s.stop()), active)

    def reg_root(tag):                              # 디스크에 실제로 있는 레지스트리(FZ_FINDINGS_ROOT)
        r = tmp / tag / "fz-findings"
        (r / "entries").mkdir(parents=True)
        return r

    def turn_start(s):
        st = load_state(pathlib.Path(s.env["FZ_RUN_STATE"]) / "fz-guard" / f"{s.sid}.json")
        return (st["turns"].get(s.pid) or {}).get("start")

    @cell
    def c4_script():
        r = reg_root("c4a")
        s = S("c4a", FZ_FINDINGS_ROOT=str(r))
        s.prompt("분석해줘", "p1")
        lesson(s)
        (r / "entries" / "F-601-sample.md").write_text("x\n")   # 스크립트 · Bash 리다이렉트 쓰기 — 쓰기 도구 사건이 없다
        o = s.stop()
        case("c4-fr-script-entry-allowed", o is None, o)

    @cell
    def c4_stale():
        r = reg_root("c4b")
        e = r / "entries" / "F-601-sample.md"
        e.write_text("x\n")
        old = time.time() - 3600
        os.utime(e, (old, old))                     # 턴 시작 전부터 있던 항목
        s = S("c4b", FZ_FINDINGS_ROOT=str(r))
        s.prompt("분석해줘", "p1")
        lesson(s)
        o = s.stop()
        case("c4-fr-stale-entry-blocked", blocked(o), o)

    @cell
    def c4_name():
        r = reg_root("c4c")
        s = S("c4c", FZ_FINDINGS_ROOT=str(r))
        s.prompt("분석해줘", "p1")
        lesson(s)
        (r / "entries" / "README.md").write_text("x\n")   # 항목 이름(F-NNN….md)이 아닌 파일은 기록이 아니다
        o = s.stop()
        case("c4-fr-fresh-non-entry-blocked", blocked(o), o)

    @cell
    def c4_slack():
        r = reg_root("c4d")
        s = S("c4d", FZ_FINDINGS_ROOT=str(r))
        s.prompt("분석해줘", "p1")
        lesson(s)
        e = r / "entries" / "F-601-sample.md"
        e.write_text("x\n")
        t0 = turn_start(s)
        os.utime(e, (t0 - 0.5, t0 - 0.5))           # 초 단위로 잘린 파일 시각 — 턴 시작과 같은 초에 쓴 항목
        o = s.stop()
        case("c4-fr-same-second-entry-allowed", o is None, f"{o} start={t0}")

    @cell
    def c4_root():
        s = S("c4e")                                # FZ_FINDINGS_ROOT 없음 — 레지스트리를 가진 머신이 아니다(FR 꺼짐)
        s.prompt("분석해줘", "p1")
        lesson(s)
        o = s.stop()
        case("c4-fr-root-unknown-off", o is None and not s.err, f"{o} {s.err!r}")

    @cell
    def fr_off():
        got = []
        for tag, root in (("fro-none", None), ("fro-empty", ""), ("fro-on", "on")):
            s = fr_on(tag) if root == "on" else S(tag, **({} if root is None else {"FZ_FINDINGS_ROOT": root}))
            s.prompt("분석해줘", "p1")
            lesson(s)
            got.append(s.stop())
        case("fr-off-without-findings-root — FZ_FINDINGS_ROOT 가 없거나 비면 FR 은 막지도 경고하지도 않는다 · 같은 턴에 루트를 주면 막는다(대조)",
             got[0] is None and got[1] is None and blocked(got[2]) and "F-518" in got[2].get("reason", ""), got)

    @cell
    def c4_noentries():
        s = S("c4i", FZ_FINDINGS_ROOT=str(tmp / "c4i" / "no-such-registry"))   # 루트는 있으나 entries/ 가 디스크에 없다
        s.prompt("분석해줘", "p1")
        lesson(s)
        o = s.stop()
        case("c4-fr-entries-missing-blocked", blocked(o) and not s.err, f"{o} {s.err!r}")

    @cell
    def c4_nostart():
        r = reg_root("c4f")
        s = S("c4f", FZ_FINDINGS_ROOT=str(r))
        s.pid = "p9"                                # UserPromptSubmit 을 못 본 prompt — 턴 시작을 모른다
        lesson(s)
        (r / "entries" / "F-601-sample.md").write_text("x\n")
        o = s.stop()
        case("c4-fr-turn-start-unknown-blocked", blocked(o) and not s.err, f"{o} {s.err!r}")

    @cell
    def c4_other():
        r = reg_root("c4g")
        a, b = S("c4g", sid="sa", FZ_FINDINGS_ROOT=str(r)), S("c4g", sid="sb", FZ_FINDINGS_ROOT=str(r))
        a.prompt("분석해줘", "p1")
        lesson(a)
        b.prompt("다른 세션", "p1")
        e = r / "entries" / "F-602-other.md"
        e.write_text("x\n")
        b.post("Write", {"file_path": str(e), "content": "x"})
        o = a.stop()                                # ponytail: 다른 세션이 같은 때 쓴 항목도 이 턴 기록으로 센다(받아들인 거짓 통과)
        case("c4-fr-other-session-entry-allowed", o is None and b.stop() is None, o)

    @cell
    def c4_cap():
        r = reg_root("c4h")
        (r / "entries" / "F-601-sample.md").write_text("x\n")
        env, since = {"FZ_FINDINGS_ROOT": str(r)}, time.time() - 60
        case("c4-fr-scan-capped", entry_since(env, since) and not entry_since(env, since, limit=0))

    @cell
    def c4_root_direct():                           # 직접 부를 때의 방어 — 루트를 모르면 예외 없이 '기록 없음'(막는 쪽 답)
        try:
            got = entry_since({}, time.time() - 60)
        except Exception as e:                      # noqa: BLE001 — 방어가 빠지면 TypeError 가 난다 · 셀 이름으로 FAIL
            got = e
        case("c4-fr-root-unknown-blocked", got is False, got)

    @cell
    def fr_broken_entry():
        r = reg_root("frb")
        for name in ("F-001-a.md", "F-002-b.md"):
            (r / "entries" / name).symlink_to(r / "gone" / name)   # 깨진 링크 — 시각을 읽으면 OSError 다
        s = S("frb", FZ_FINDINGS_ROOT=str(r))
        s.prompt("분석해줘", "p1")
        lesson(s)
        (r / "entries" / "F-900-fresh.md").write_text("x\n")
        o = s.stop()
        case("fr-unreadable-entry-skipped-fresh-entry-allowed", o is None and not s.err, f"{o} {s.err!r}")

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
        o = s.pre("Agent", {"subagent_type": "general-purpose"})
        case("agent-adhoc-in-direct-skill-warned", kind(o) is None and warned(o, "fz-guard AG"), o)

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
        h = fr_on("c56", transcript=t_sdk)
        h.prompt("분석해줘", "p1")
        lesson(h)
        a = fr_on("c56a", FZ_AUTONOMY="autonomous")
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

    @cell
    def c64():
        # F-708 — fz 턴이 PR 코멘트를 읽고 레지스트리 쓰기도 'finding 해당 없음' 줄도 없이 끝나면 1회 막는다
        def pr_turn(tag, sid="s1", fz=True, how="bash"):
            s = fr_on(tag, sid=sid)
            s.prompt("코멘트 봐줘", "p1")
            if fz:
                s.pre("Skill", {"skill": "fz:fz-fix"})
            if how == "bash":
                s.pre("Bash", {"command": "gh api repos/o/r/pulls/12/comments --paginate"})
            else:
                s.pre("mcp__github__get_pull_request_reviews", {"pull_number": 12})
            return s
        bash, mcp = pr_turn("c64a").stop(), pr_turn("c64b", how="mcp").stop()
        said = pr_turn("c64c").stop(msg="판정 끝. finding 해당 없음 — 코멘트 6건 모두 표기 취향")
        w = pr_turn("c64d")
        w.post("Write", {"file_path": reg, "content": "x"})
        wrote = w.stop()
        plain = pr_turn("c64e", fz=False).stop()
        again = pr_turn("c64f")
        first, second = again.stop(), again.stop()
        case("f708-pr-comments-without-registry-blocked — fz 턴의 PR 코멘트 읽기(gh api · GitHub MCP)는 기록 · 해당 없음 줄이 없으면 1회 막는다",
             blocked(bash) and "F-708" in bash.get("reason", "") and blocked(mcp) and said is None and wrote is None
             and plain is None and blocked(first) and not blocked(second), f"{bash} · {mcp} · {said} · {wrote} · {plain} · {second}")
        # (세션, PR) 마다 한 번 — 같은 PR 을 다음 턴에 다시 읽으면 묻지 않고 다른 PR 이면 다시 묻는다 · 피어 리뷰 턴은 면제(F-643 표가 잰다)
        r = pr_turn("c64g")
        r.stop()
        r.prompt("또 봐줘", "p2")
        r.pre("Bash", {"command": "gh api repos/o/r/pulls/12/reviews"})
        same = r.stop()
        r.prompt("다른 PR", "p3")
        r.pre("Bash", {"command": "gh pr view 34 --comments"})
        other = r.stop()
        pr = fr_on("c64h")
        pr.prompt("<command-name>/fz:fz-peer-review</command-name>\n<command-args>12</command-args>", "p1")
        pr.pre("Bash", {"command": "gh api repos/o/r/pulls/12/comments"})
        peer = pr.stop()
        # 명령 자리의 gh 만 읽기다 — echo · grep 인자 · heredoc 본문의 언급은 읽기가 아니다(GPT 리뷰 P2)
        mention = pr_turn("c64i")
        mention.prompt("문서 봐줘", "p2")
        for c in ('echo "gh pr view 12 --comments"', "grep -n 'gh api repos/o/r/pulls/12/comments' notes.md",
                  "cat <<'EOF'\ngh api repos/o/r/pulls/77/reviews\nEOF"):
            mention.pre("Bash", {"command": c})
        quiet = mention.stop()
        forms = [pr_comment_reads(c) for c in ("gh -R o/r pr view 34 --comments", "gh api repos/o/r/issues/5/comments --paginate | jq .",
                                               'echo "gh pr view 12 --comments"', "gh pr view 9 --json title",
                                               "gh api --paginate repos/o/r/pulls/12/comments", "gh pr view 7 --json comments,reviews",
                                               "gh api repos/o/r/pulls/123/reviews -X POST --input payload.json",
                                               "gh api repos/o/r/pulls/123/comments -f body=x")]
        # /fz 가 Read 로 도는 피어 리뷰 턴도 면제(리뷰 M4)
        via = pr_turn("c64j")
        via.prompt("팀원 PR 봐줘", "p2")
        via.post("Read", {"file_path": "/x/plugins/fz/skills/fz-peer-review/SKILL.md"}, {"type": "text"})
        via.pre("Bash", {"command": "gh api repos/o/r/pulls/99/comments"})
        via_stop = via.stop()
        via.prompt("이어서 해줘", "p3")             # 같은 PR 을 다음 턴에 다시 읽어도 묻지 않는다 · 다른 PR 은 묻는다
        via.pre("Bash", {"command": "gh api repos/o/r/pulls/99/reviews"})
        via_next = via.stop()
        via.prompt("내 PR 도", "p4")
        via.pre("Bash", {"command": "gh api repos/o/r/pulls/5/comments"})
        via_other = via.stop()
        nx = fr_on("c64k")                         # 피어 리뷰 명령의 PR 을 다음 턴에 처음 읽어도 묻지 않는다
        nx.prompt("<command-name>/fz:fz-peer-review</command-name>\n<command-args>1234 light</command-args>", "p1")
        nx.stop()
        nx.prompt("진행해줘", "p2")
        nx.pre("Bash", {"command": "gh api repos/o/r/pulls/1234/comments"})
        nx_later = nx.stop()
        case("f708-command-position-only — 명령 자리 gh 만 PR 읽기 · 언급 · 게시(POST · 필드)는 아니다 · api 앞 옵션 · --json comments 도 읽기 · "
             "/fz 경유 피어 리뷰 Read 면제",
             quiet is None and forms == [["34"], ["5"], None, None, ["12"], ["7"], None, None] and via_stop is None
             and via_next is None and blocked(via_other) and nx_later is None,
             f"{quiet} · {forms} · {via_stop} · {via_next} · {via_other} · {nx_later}")
        hooks = json.loads((PLUGIN_ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]
        rx = [re.compile(h["matcher"]) for h in hooks.get("PreToolUse", []) if h.get("matcher")]
        routed = all(any(x.search(n) for x in rx) for n in ("mcp__github__get_pull_request_comments", "mcp__plugin_github_github__get_pull_request_reviews"))
        case("f708-once-per-pr-peer-exempt-mcp-routed — 같은 PR 재읽기는 통과 · 다른 PR 은 다시 막음 · 피어 리뷰 턴 면제 · hooks.json 이 MCP 이름을 들여보낸다",
             same is None and blocked(other) and peer is None and routed, f"{same} · {other} · {peer} · {[x.pattern[:80] for x in rx]}")

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
