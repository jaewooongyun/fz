#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import(fz_wf_metrics·freeze_baseline)와
#   계측기 해시에 이 파일의 디렉토리만 쓴다. 원장·transcript·fixture 경로는 전부 호출자가 넘긴다.
# diff-parse: not-a-diff — `startswith("-")` 는 셸 명령 토큰의 플래그 판별이다(sed -i · --out-dir · --out= · 스크립트 argv).
#   `startswith("--------")` 는 GPT 스트림 로그 배너의 구분선이다. diff 줄 접두를 판정하는 곳은 없다.
"""ab_ledger.py — A/B 원장: 수집(collect)·채점(score)·판정(judge) (S05).

왜: 속도 개선을 주장하려면 **같은 입력·같은 모델/effort·완주한 run** 끼리만 비교해야 한다. 손으로 옮긴
   수치는 이 조건을 검사하지 않고, 잘린 run 은 오류 없이 그럴듯한 wall 을 낸다(F-203). 이 도구는 값을
   원천(Lead transcript · Workflow 폴더 · 상태 스냅샷)에서 읽고, judge 는 `--verify-sources` 로 **다시** 읽는다.

원장 = JSONL, append-only. 같은 run_id 는 **마지막 행**이 이긴다(recollect·재채점은 새 행을 쓴다).
  {"type":"run",   run_id, workflow, arm, run, order, phase, release, fixture,
                   lead{model, models, effort, efforts, cli_versions, out_tok, messages, tool_errors, retries,
                        bash_arg_chars, heredoc_targets, inline_python, followup_prompts, advisor},
                   plugin{root, roots, sha, dirty, tree_hash}, injected{User, Project, AutoMem}, instrument_sha,
                   input{hash, fixture, commits, prompt_sha},
                   wall{total_s, start, end, mtime_delta_s, workflows[{run_id, wf_s, lead_s, delta_pct}], gpt_s},
                   wf{runs[…], agents, out_tok, turns, advisor, models, efforts, stages, stage2_ran,
                      stages_completed, rejections},
                   gpt{calls, models, efforts, versions}, state{start_hash, pristine_hash, end_hash, leak, writes},
                   complete{ok, why}, sources{…}, collect_args{…}}
  {"type":"score", run_id, kind(review|plan), by_severity, by_axis, …, fixture_sha}

측정 규약 (⛔ 전부 실측으로 정했다 — 2026-09-26)
  · Lead·워커 transcript 는 응답 1건을 content block 마다 한 줄로 쓰고 **같은 id 에 같은 usage 를 반복**한다.
    usage 는 message id 별로 한 번만 센다(줄 합산은 1.35~1.6배 과대).
  · effort 는 assistant 이벤트 최상위 `effort`, model 은 `message.model` 이다(`<synthetic>` 제외).
  · 완료 시각은 task-notification 의 가장 이른 기록이다(queue-operation enqueue ≤ user 메시지).
  · wall_total = 첫 사람 발화 → 최종 산출물 기록 이벤트(Write·Edit·Bash 리다이렉트)의 결과 시각.
    파일 mtime 은 **교차 검사에만** 쓴다(mtime 자는 -36% 편향 — 판정에 쓰지 않는다).
  · wall_workflow 는 두 자 — 에이전트 timestamp(fz_wf_metrics) 와 Lead 의 Workflow 기동→완료 알림 — 끼리만
    교차하고 5% 를 넘으면 그 run 은 무효다. 두 값과 차이를 함께 인쇄한다.
  · 입력 해시 = sha256(fixture 이름 · fixture 저장소 main/feature 커밋 · 첫 사람 발화). build-repo.sh 가 커밋
    신원·시각을 고정하므로 같은 fixture 는 같은 SHA 를 낸다. 플러그인 트리 해시는 freeze_baseline 헬퍼로 따로 잰다.

exit: 0=PASS · 1=FAIL · 2=UNRUN(측정 불가·미구현 기준 — ⛔ 통과로 읽지 않는다)

Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import collections
import glob
import hashlib
import json
import math
import os
import pathlib
import re
import shlex
import shutil
import statistics
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
import freeze_baseline as fb  # noqa: E402 — 형제 모듈(트리 파일 목록·해시)
import fz_wf_metrics as wfm   # noqa: E402 — 형제 모듈(Workflow 폴더 집계)

PASS, FAIL, UNRUN = 0, 1, 2
SCHEMA = "ab-ledger/1"
STATE_SCHEMA = "ab-state/1"
SEVERITIES = ("critical", "major", "minor", "suggestion")
GATED = ("critical", "major")
AXES6 = ("idiom", "naming", "architecture", "ui_structure", "placement", "design_alternative")
AXES_ALLOWED = AXES6 + ("correctness",)
DEFAULT_MODEL, DEFAULT_EFFORT = "claude-opus-5-5", "xhigh"   # Sprint Contract 제약 — 워커는 Opus 5.5 xhigh
LINE_TOL = 3            # 인용 줄이 라벨 범위에서 이만큼 벗어나도 같은 지적으로 본다
WALL_XCHECK_PCT = 5.0   # wall_workflow 두 자의 허용 차이
MTIME_TOL_S = 5.0       # 최종 산출물 기록 이벤트 ↔ 파일 mtime 허용 차이
PHASES = ("baseline", "release-smoke", "change")
INSTRUMENTS = ("ab_ledger.py", "fz_wf_metrics.py", "freeze_baseline.py")
# ⛔ 구현한 기준만 판정한다. 나머지(SC-1·SC-2·SC-8·AC-2·AC-3·AC-6)는 **exit 2** — 받고 무시하면 그것이 AC-5 의
#    '빠른 성공'이다. S25 · S26 에서 SC-5 · AC-4 · blind-labels · gpt-wf-wall · critical-path 를 더했다. 남은 구현 스텝: S27.
IMPLEMENTED = ("SC-3", "SC-3-smoke", "SC-4", "SC-5", "SC-6", "SC-7", "AC-1", "AC-4", "AC-5", "AC-7", "crossover-order", "input-hash",
               "blind-labels", "gpt-wf-wall", "critical-path")
SOURCE_KINDS = ("transcript", "wf-metrics", "start-state", "input-hash", "instrument-sha")


# ── 공통 ────────────────────────────────────────────────────────────────
def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha_obj(o) -> str:
    return sha_text(json.dumps(o, ensure_ascii=False, sort_keys=True))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def iso(t):
    return t.isoformat() if t else None


def secs(a, b):
    return round((b - a).total_seconds(), 3) if a and b else None


def norm_model(m):
    """`claude-opus-5-5[1m]` 과 `claude-opus-5-5` 는 같은 모델이다(컨텍스트 창 표기만 다르다)."""
    return re.sub(r"\[[^\]]*\]$", "", m) if isinstance(m, str) else m


def iter_jsonl(path):
    evs, bad = [], 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                bad += 1
                continue
            if isinstance(ev, dict):
                evs.append(ev)
            else:
                bad += 1
    return evs, bad


def instrument_sha() -> str:
    h = hashlib.sha256()
    for n in INSTRUMENTS:
        with open(os.path.join(SCRIPT_DIR, n), "rb") as fh:
            h.update(n.encode("utf-8") + b"\0" + fh.read())
    return h.hexdigest()[:16]


# ── Lead transcript ─────────────────────────────────────────────────────
BASE_DIR_RE = re.compile(r"Base directory for this skill: ([^\s\"\\]+)")
NOTIF_RE = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
INLINE_PY_RE = re.compile(r"\bpython3?\s+(?:-\s*<<|-c\s)")
REDIRECT_RE = re.compile(r"(?:(?<![<>0-9&])>>?|\btee(?:\s+-a)?)\s*(['\"]?)([^\s'\";|&<>()]+)\1")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# ⛔ 스크립트를 **실행 위치에서** 부르는 명령만 호출로 센다 — `sed -n … gpt-exec.sh`·`rg 'gpt-exec.sh exec'` 같은
#    읽기·검색을 세면 호출 수가 부푼다(실측). heredoc 본문은 보지 않는다.
#    머리 대안: 줄 머리(들여쓰기 포함) · 구분자 뒤 · then/do/else 뒤 · bash/sh/exec 뒤. 그 뒤 `VAR=x`·`timeout N` 접두와
#    `bash`/`sh` 를 건너뛴다 — 템플릿이 `if …; then` 안 들여쓴 호출과 `FZ_PLUGIN_ROOT=… bash …` 로 부른다(v4.40.0 리뷰).
GPT_CALL_RE = re.compile(r"(?:^[ \t]*|[;&|(]\s*|\b(?:then|do|else)\s+|\b(?:bash|sh|exec)\s+)"
                         r"(?:(?:[A-Za-z_]\w*=\S*|timeout\s+\S+)\s+)*(?:(?:bash|sh)\s+)?"
                         r"[\"']?(?:[^\s\"';&|]*/)?gpt-exec\.sh[\"']?\s+(?:review|exec|resume)\b", re.M)
# Bash 가 산출물을 **썼다**는 근거 — 경로 문자열만 있는 읽기(cat·grep)는 끝점 후보가 아니다
WRITE_HINT_RE = re.compile(r"write_text|write_bytes|open\([^)]*['\"][wax]\+?['\"]|json\.dump\(|shutil\.copy")
# ⛔ 원본 인자에 셸 연산자를 넣지 않는다 — `\S+` 는 `&&` 도 단어로 읽어 다음 명령까지 삼켰다(실측: plan B1
#    `… gen_plan.py 3 && cp A plan-final.md && R=…; … head -1` 에서 대상이 `-1` 로 잡혀 완주 run 이 미완주가 됐다)
CPMV_RE = re.compile(r"(?:^|[;&|]\s*)(?:cp|mv|install)\s+(?:-\S+\s+)*(?:[^\s;&|]+\s+)+(['\"]?)([^\s'\";|&]+)\1\s*(?:$|[;&|])", re.M)
GPT_OUT_RE = re.compile(r"--out\s+(['\"]?)([^\s'\"]+)\1")
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
# 반환·하네스 계수가 없을 때의 대체 완주 오라클 — 건강한 run 에서 **항상** 도는 stage (base 트리 실측)
#   fz-peer-review 의 Stage 2 는 트리거·--deep, Stage 3 은 --deep 에서만 돈다 — 필수에 넣지 않는다
REQUIRED_STAGES = {
    "fz-plan": ("L1-full", "L1-edge", "L1-impact", "L2-merge"),
    "fz-review": ("R1-arch", "R1-quality", "R2-arch", "R2-quality", "R3-counter"),
    "fz-peer-review": ("R1-arch", "R1-quality", "R1-correct"),
}


def _tag(body, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", body, re.S)
    return m.group(1).strip() if m else None


def _strings(ev):
    """사람 발화·완료 알림이 실릴 수 있는 문자열 칸 — user 메시지 · 큐 적재 · queued_command 첨부."""
    out = []
    if isinstance(ev.get("content"), str):
        out.append(ev["content"])
    msg = ev.get("message")
    if isinstance(msg, dict):
        c = msg.get("content")
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            out += [b["text"] for b in c if isinstance(b, dict) and isinstance(b.get("text"), str)]
    a = ev.get("attachment")
    if isinstance(a, dict):
        out += [a[k] for k in ("prompt", "content") if isinstance(a.get(k), str)]
    return out


def _shell_part(cmd: str) -> str:
    """heredoc 본문을 뺀 셸 줄 — 본문(파이썬 f-string 의 `>` 등)을 리다이렉트로 읽지 않는다."""
    out, delim = [], None
    for line in cmd.split("\n"):
        if delim is not None:
            if line.strip() == delim:
                delim = None
            continue
        out.append(line)
        m = HEREDOC_RE.search(line)
        if m:
            delim = m.group(2)
    return "\n".join(out)


def _redirect_targets(cmd: str):
    """셸 부분의 쓰기 대상 — 경로처럼 생긴 것(`/` 또는 `.` 포함)만."""
    return [t for t in (m.group(2) for m in REDIRECT_RE.finditer(_shell_part(cmd)))
            if t != "/dev/null" and ("/" in t or "." in t) and re.fullmatch(r"[\w@%+=:,./~$-]+", t)]


def _call_segment(cmd, call):
    """래퍼 호출 하나의 인자 구간 — 따옴표 **밖**의 첫 명령 구분자(줄바꿈·`;`·`&`·`|`) 앞까지.
    ⛔ 명령 끝까지 보면 뒤 명령의 `--effort`·`--out` 이 앞 호출 것으로 읽힌다(v4.40.0 리뷰). ⛔ 따옴표 안의 `;` 는 경계가 아니다 —
       정규식으로 끊으면 `"one;two"` 에서 잘려 명시 effort 를 놓친다(v4.40.0 validate 2차). `\` 줄 잇기와 `2>&1`·`&>` 리다이렉트는 잇는다."""
    i, n, q = call.end(), len(cmd), None
    while i < n:
        c = cmd[i]
        if q:
            if c == "\\" and q == '"':
                i += 2
                continue
            if c == q:
                q = None
        elif c in "'\"":
            q = c
        elif c == "\\":
            i += 2
            continue
        elif c in "\n;|" or (c == "&" and cmd[i - 1] not in "<>" and cmd[i + 1: i + 2] != ">"):
            break
        i += 1
    return cmd[call.start(): min(i, n)]


def _resolved_output(of, tasks_dirs):
    """하네스 산출 경로 — `/tmp` 원본이 지워졌으면 러너가 run 직후 복사해 둔 폴더에서 같은 이름을 찾는다."""
    if of and not os.path.isfile(of):
        for d in tasks_dirs:
            c = os.path.join(d, os.path.basename(of))
            if os.path.isfile(c):
                return c
    return of


def _load_return(nt, tasks_dirs=()):
    """Workflow 반환 → (반환 dict, 하네스 래퍼 dict, 출처). 알림 `<result>` 는 8,000자에서 잘린다(실측) —
    잘렸으면 `<output-file>`(하네스 래퍼 JSON: agentCount·result·totalTokens …)을 읽는다."""
    note = None
    r = nt.get("result")
    if r and "... (truncated" not in r:
        try:
            v = json.loads(r)
            note = v if isinstance(v, dict) else None
        except ValueError:
            note = None
    of = _resolved_output(nt.get("output_file"), tasks_dirs)
    wrap = None
    if of and os.path.isfile(of):
        try:
            w = read_json(of)
            wrap = w if isinstance(w, dict) else None
        except (OSError, ValueError):
            wrap = None
    # ⛔ 알림 결과가 짧아 온전해도 하네스 래퍼(agentCount)가 있으면 반드시 함께 읽는다 — 두 계수를 대조해야 한다
    res = (wrap or {}).get("result")
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except ValueError:
            res = None
    if note is not None:
        if isinstance(res, dict) and (res.get("metrics") != note.get("metrics") or res.get("mode") != note.get("mode")):
            note = dict(note, _conflict=True)   # ⛔ 두 원천의 반환이 다르면 어느 쪽도 믿지 않는다(build_row 가 미완주 처리)
        return note, wrap, "notification" + ("+output-file" if wrap else "")
    if wrap is not None:
        return (res if isinstance(res, dict) else None), wrap, "output-file"
    return None, None, None


def _writes_path(cmd, base):
    """쓰기 표현의 **대상**에 산출물 이름이 들어 있는가 — 같은 명령에 이름과 무관한 쓰기 동사가 따로 있는 것은 아니다.
    ponytail: 셸 변수·`for` 값·argv 로 넘긴 경로는 `_bash_writes` 가 펴서 본다. 그 밖의 형태(glob · `Path(sys.argv[1])` ·
    함수 인자)는 끝점이 없거나 mtime 교차 실패로 run 이 미완주가 된다(안전 쪽) — 새 형태가 나오면 실측 명령으로 더한다."""
    b = re.escape(base)
    pats = (rf"open\(\s*[^,)\n]*{b}[^,)\n]*,\s*['\"][wax]",
            rf"Path\([^)\n]*{b}[^)\n]*\)\s*\.\s*write_(?:text|bytes)\(",
            rf"{b}['\"]\s*\)\s*\.\s*write_(?:text|bytes)\(",
            rf"json\.dump\([^\n]*open\([^)\n]*{b}[^)\n]*['\"]w")
    if any(re.search(x, cmd) for x in pats):
        return True
    # 변수에 담은 산출물 경로가 **실제로 쓰기에 쓰일 때만** — `p='…/report.md'; open(p,'w')` (실측: review B1 끝점 +1433s 누락).
    #   ⛔ 다른 변수·다른 파일의 쓰기는 세지 않는다(ISSUE-011 계약 유지)
    return any(_var_written(cmd, v) for v in set(re.findall(rf"\b(\w+)\s*=\s*(?:Path\(\s*)?['\"][^'\"\n]*{b}['\"]", cmd)))


def _var_written(text, v):
    """변수 `v` 가 가리키는 파일을 **쓰는** 표현이 있는가 — `open(v,'w')` · `v.write_text(` · `Path(v).write_text(`."""
    e = re.escape(v)
    return bool(re.search(rf"open\(\s*{e}\s*,\s*['\"][wax]", text) or re.search(rf"\b{e}\s*\.\s*write_(?:text|bytes)\(", text)
                or re.search(rf"Path\(\s*{e}\s*\)\s*\.\s*write_(?:text|bytes)\(", text))


CD_RE = re.compile(r"(?:^|[;&|]\s*)cd\s+(['\"]?)([^\s'\";|&]+)\1", re.M)


def _cd_bases(cmd, cwd):
    """상대 경로를 풀 기준 — 이벤트 cwd 와, 명령 안에서 `cd X` 로 옮긴 곳(실측: `cd /repo && cat >> rel` 쓰기를 놓쳤다)."""
    out = [cwd] if cwd else []
    for m in CD_RE.finditer(_shell_part(cmd)):
        c = m.group(2)
        out.append(c if os.path.isabs(c) else os.path.join(cwd or "", c))
    return out


def _same_path(a, b):
    return bool(a and b) and os.path.realpath(a) == os.path.realpath(b)


ASSIGN_RE = re.compile(r"(?:^|[;&|(]\s*|\s)([A-Za-z_]\w*)=(\"[^\"\n]*\"|'[^'\n]*'|[^\s;&|'\"()]*)", re.M)
FOR_RE = re.compile(r"\bfor\s+([A-Za-z_]\w*)\s+in\s+([^;\n]+?)\s*;\s*do\b")
VAR_RE = re.compile(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)")
PY_ARGV_RE = re.compile(r"\bpython3?\s+-\s+([^<\n;&|]*?)\s*<<-?\s*(['\"]?)([A-Za-z_]\w*)\2")
ARGV_BIND_RE = re.compile(r"(?:^|;)\s*(\w+(?:\s*,\s*\w+)*)\s*=\s*(sys\.argv\[\d+\](?:\s*,\s*sys\.argv\[\d+\])*)", re.M)


def _expand_vars(cmd):
    """원 명령 + 셸 변수를 같은 명령 안의 대입값으로 편 명령들 — `for V in a b; do` 는 값마다 한 벌.
    실측(F-331): `W=…; cat >> $W/plan/plan-final.md` · `for f in plan-final.md …; do python3 - "$W/plan/$f"` 를 놓쳤다.
    ⛔ 대입은 heredoc 밖에서만 읽는다(본문의 `p=sys.argv[1]` 은 셸 변수가 아니다) · 모르는 변수는 그대로 둔다."""
    sh = _shell_part(cmd)
    sub = lambda s, env: VAR_RE.sub(lambda m: env.get(m.group(1) or m.group(2), m.group(0)), s)
    env = {}
    for m in ASSIGN_RE.finditer(sh):
        v = m.group(2)
        env[m.group(1)] = v[1:-1] if v[:1] == "'" else sub(v.strip('"'), env)
    envs = [env]
    for m in FOR_RE.finditer(sh):
        try:
            words = shlex.split(sub(m.group(2), env))
        except ValueError:
            continue
        envs = [dict(e, **{m.group(1): w}) for e in envs for w in words][:64]   # ponytail: 루프 조합 64 벌 상한
    return [cmd] + [sub(cmd, e) for e in envs if e]


ARGV_DIRECT_RE = re.compile(r"open\(\s*sys\.argv\[(\d+)\]\s*,\s*['\"][wax]|Path\(\s*sys\.argv\[(\d+)\]\s*\)\s*\.\s*write_(?:text|bytes)\(")
PY_SCRIPT_RE = re.compile(r"(?:^|[;&|(]\s*|\s)python3?(?:\.\d+)?\s+(?:-[uBO]+\s+)*([^\s;&|<>'\"-][^\s;&|<>]*\.py)\s+([^\n;&|<>]*)", re.M)


def _argv_written(body):
    """본문이 **쓰는** argv 인덱스 — `x = sys.argv[N]` 뒤 open(x,'w') 류(튜플 풀기 포함) · 직접 `open(sys.argv[N],'w')`."""
    idx = set()
    for names, vals in ARGV_BIND_RE.findall(body):
        for v, n in zip(re.split(r"\s*,\s*", names), re.findall(r"\[(\d+)\]", vals)):
            if _var_written(body, v):
                idx.add(int(n))
    for m in ARGV_DIRECT_RE.finditer(body):
        idx.add(int(m.group(1) or m.group(2)))
    return idx


def _script_argv_writes(cmd, a, bases, scripts):
    """`python3 스크립트.py ARG…` — 스크립트 본문(transcript 의 Write 입력 → 없으면 디스크)이 쓰는 argv 가 산출물 `a` 인가.
    실측(plan B1-feature 재측정): Lead 가 Write 로 make_plan_final.py 를 만들어 `python3 $W/make_plan_final.py v3.md plan-final.md`
    로 쓰고 곧 지웠다 — heredoc 만 보던 판정이 끝점을 놓쳐 완주 run 이 미완주가 됐다."""
    for m in PY_SCRIPT_RE.finditer(_shell_part(cmd)):
        try:
            args = shlex.split(m.group(2))
        except ValueError:
            continue
        sp = m.group(1)
        cands = [sp] if os.path.isabs(sp) else [os.path.join(b, sp) for b in bases]
        body = None
        for c_ in cands:
            body = (scripts or {}).get(os.path.normpath(c_))
            if body is None and os.path.isfile(c_):
                try:
                    body = open(c_, encoding="utf-8", errors="replace").read()
                except OSError:
                    body = None
            if body is not None:
                break
        if body is None:
            continue
        # ⛔ 경로를 스크립트 **안에서** 만들어 쓰는 경우(실측 plan-feature C1 — render_plan.py 가 `OUT = f"{W}/plan/plan-final.md"`
        #    로 썼다): 본문이 산출물 이름과 쓰기 호출을 함께 담으면 후보다. 여러 후보 가운데 선택은 파일 mtime 최근접이 한다
        if os.path.basename(a) in body and re.search(r"open\([^)\n]*['\"][wax]|write_(?:text|bytes)\(", body):
            return True
        for n in _argv_written(body):
            p_ = args[n - 1] if 1 <= n <= len(args) else None
            if p_ and any(_same_path(x, a) for x in ([p_] if os.path.isabs(p_) else [os.path.join(b, p_) for b in bases])):
                return True
    return False


def _argv_writes(cmd, a, bases):
    """`python3 - ARG… <<DELIM` 본문이 `x = sys.argv[N]`(튜플 풀기 포함)로 받은 경로를 쓰고, N 번째 ARG 가 산출물 `a` 인가.
    ⛔ 위치를 맞춘다 — `python3 - "$A" "$F"` 에서 argv[1] 만 쓰고 argv[2] 는 읽기만 하면 `F` 쓰기가 아니다."""
    for m in PY_ARGV_RE.finditer(cmd):
        try:
            args = shlex.split(m.group(1))
        except ValueError:
            continue
        rest = cmd[m.end():]
        end = re.search(rf"^{re.escape(m.group(3))}\s*$", rest, re.M)
        body = rest[:end.start()] if end else rest
        for n in _argv_written(body):
            p = args[n - 1] if 1 <= n <= len(args) else None
            cands = ([p] if os.path.isabs(p) else [os.path.join(b, p) for b in bases]) if p else []
            if cands and any(_same_path(x, a) for x in cands):
                return True
    return False


RENDER_OUTPUTS = ("review-report.md", "pr-comments.md", "render-preview.json", "payload.json")   # scripts/render_review.py OUTPUTS


def _segments(sh):
    """heredoc 을 뺀 셸 줄 → 명령마다 토큰 목록. 따옴표를 지키며 `;` `&&` `||` `|` `&` 로 끊는다
    (sed 의 `s|a|b|` 처럼 따옴표 안 구분자는 끊지 않는다). 못 읽는 줄은 건너뛴다."""
    def toks_of(text):
        lx = shlex.shlex(text, posix=True, punctuation_chars="();<>|&\n")
        lx.whitespace = " \t\r"
        lx.whitespace_split = True
        return list(lx)

    # ⛔ 줄마다 끊으면 여러 줄 따옴표(`python3 -c "…⏎…"`)가 있는 줄의 앞 명령까지 버린다(실측 peer C1 — 병합 명령 누락).
    #    전체를 한 번에 읽고, 따옴표가 끝내 안 맞을 때만 줄마다로 물러선다
    try:
        chunks = [toks_of(sh)]
    except ValueError:
        chunks = []
        for line in sh.split("\n"):
            try:
                chunks.append(toks_of(line))
            except ValueError:
                continue
    out = []
    for toks in chunks:
        cur = []
        for t in toks:
            if t and set(t) <= set(";&|\n"):
                if cur:
                    out.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            out.append(cur)
    return out


def _sed_inplace_files(seg):
    """`sed -i` 가 제자리에서 고치는 파일들(BSD `-i ''` · `-i .bak` · GNU `-i` · `-i.bak`). -i 가 없으면 빈 목록."""
    if not seg or os.path.basename(seg[0]) not in ("sed", "gsed"):
        return []
    files, script, inplace, i = [], False, False, 1
    while i < len(seg):
        t = seg[i]
        if t and set(t) <= set("<>&0123456789") and ("<" in t or ">" in t):
            break                                   # 리다이렉트부터는 파일 인자가 아니다
        if t == "-i":
            inplace = True
            if i + 1 < len(seg) and (seg[i + 1] == "" or seg[i + 1].startswith(".")):
                i += 1                              # BSD 백업 접미 인자
        elif t.startswith("-i") or t.startswith("--in-place"):
            inplace = True
        elif t in ("-e", "-f", "--expression", "--file"):
            script, i = True, i + 1
        elif t.startswith("-") and not script:
            pass
        elif not script:
            script = True
        else:
            files.append(t)
        i += 1
    return files if inplace else []


def _render_outputs(seg):
    """`render_review.py … --out-dir D` 가 쓰는 산출물들 — 렌더러가 스크립트 안에서 쓰므로 명령 모양으로만 안다."""
    if not any(os.path.basename(t) == "render_review.py" for t in seg):
        return []
    for i, t in enumerate(seg):
        d = seg[i + 1] if t == "--out-dir" and i + 1 < len(seg) else (t.split("=", 1)[1] if t.startswith("--out-dir=") else None)
        if d:
            return [os.path.join(d, x) for x in RENDER_OUTPUTS]
    return []


def _resolve_vars(s, cmd, cwd):
    """같은 명령의 대입(`W=$PWD/…` · `export R=…`)과 이벤트 cwd(`$PWD`)로 문자열의 셸 변수를 푼다 — 못 풀면 그대로 둔다."""
    env = {"PWD": cwd} if cwd else {}
    sub_ = lambda x: VAR_RE.sub(lambda m: env.get(m.group(1) or m.group(2), m.group(0)), x)
    sh = _shell_part(cmd)
    # ⛔ 대입과 `cd` 를 **나온 순서대로** 편다 — `cd /repo && R="$PWD"` 의 R 은 이벤트 cwd 가 아니라 /repo 다(실측 review B2)
    evs = sorted([(m.start(1), "a", m) for m in ASSIGN_RE.finditer(sh)] + [(m.start(), "c", m) for m in CD_RE.finditer(sh)],
                 key=lambda x: x[0])
    for _, k, m in evs:
        if k == "a":
            v = m.group(2)
            env[m.group(1)] = v[1:-1] if v[:1] == "'" else sub_(v.strip('"'))
        else:
            t = sub_(m.group(2))
            if "$" not in t:
                env["PWD"] = t if os.path.isabs(t) else os.path.join(env.get("PWD") or "", t)
    return sub_(s)


PY_EXE_RE = re.compile(r"^python(?:3(?:\.\d+)?)?$")


def _exec_of(seg, name):
    """명령 토큰이 스크립트 `name` 을 **실행**하는가 — `python3 [-u] …/name …` · `…/name …`. 읽기(`wc -l …/name`)는 아니다."""
    if not seg:
        return False
    if os.path.basename(seg[0]) == name:
        return True
    if PY_EXE_RE.match(os.path.basename(seg[0])):
        rest = [t for t in seg[1:] if not t.startswith("-")]
        return bool(rest) and os.path.basename(rest[0]) == name
    return False


def _merge_summaries(tool_uses, results):
    """결정론 병합(review_merge.py) 실행마다 후보 수 — AC-4(입력 = 출력). `--out F` 면 그 파일의 summary, 아니면 표준출력의 JSON.
    병합이 거부했으면(후보 보존 위반) violations 에 센다. ⛔ 파일은 수집 시점 내용이다 — 같은 경로에 여러 번 쓰면 마지막 결과다."""
    out = {"summaries": [], "violations": 0}
    for u in tool_uses:
        if u["name"] != "Bash":
            continue
        cmd = str(u["input"].get("command") or "")
        segs = [x for body in [cmd] + _shell_heredoc_bodies(cmd) for x in _segments(_shell_part(body))
                if _exec_of(x, "review_merge.py") and not any(t in ("--self-test", "--check-fixture") for t in x)]
        if not segs:
            continue
        text = (results.get(u["id"]) or {}).get("text") or ""
        if "후보 보존 위반" in text:
            out["violations"] += 1
        for x in segs:
            o = next((t.split("=", 1)[1] for t in x if t.startswith("--out=")), None)
            if o is None and "--out" in x and x.index("--out") + 1 < len(x):
                o = x[x.index("--out") + 1]
            summ, src = None, None
            if o:
                f = _resolve_vars(o, cmd, u["cwd"])
                if "$" not in f:
                    # ⛔ 상대 경로는 명령 안 `cd` 목적지 기준일 수 있다(실측 review C2 — `cd …/review && … --out merged-r1.json`)
                    for base in ([""] if os.path.isabs(f) else list(reversed(_cd_bases(_expand_vars(cmd)[-1], u["cwd"]))) or [u["cwd"] or ""]):
                        ff = f if os.path.isabs(f) else os.path.join(base, f)
                        try:
                            summ, src = (read_json(ff) or {}).get("summary"), ff
                        except (OSError, ValueError):
                            summ = None
                        if isinstance(summ, dict):
                            break
            if summ is None:
                mi, mo = re.search(r'"candidatesIn":\s*(\d+)', text), re.search(r'"candidatesOut":\s*(\d+)', text)
                mt = re.search(r"MERGE OK\s*—\s*후보\s+(\d+)\s*→\s*(\d+)", text)   # 표준출력 한 줄 요약(review_merge.py)
                if mi and mo:
                    summ, src = {"candidatesIn": int(mi.group(1)), "candidatesOut": int(mo.group(1))}, "stdout"
                elif mt:
                    summ, src = {"candidatesIn": int(mt.group(1)), "candidatesOut": int(mt.group(2))}, "stdout-line"
            if isinstance(summ, dict) and isinstance(summ.get("candidatesIn"), int):
                out["summaries"].append({"in": summ["candidatesIn"], "out": summ.get("candidatesOut"), "src": src})
    return out


# 실제 GPT 홈의 스킬을 직접 가리키는 경로 — `$CODEX_HOME` 격리를 우회한다(실측 peer B2 8회 · C1 1회)
REAL_HOME_SKILL_RE = re.compile(r"(?:\$HOME|\$\{HOME\}|~|/Users/[^/\s'\"]+)/\.codex/skills/")


SH_HEREDOC_RE = re.compile(r"(?:^|[;&|(]\s*|\s)(?:bash|sh|zsh)(?:\s+-[A-Za-z]+)*\s*<<-?\s*(['\"]?)([A-Za-z_]\w*)\1[^\n]*\n", re.M)


def _shell_heredoc_bodies(cmd):
    """셸에 먹이는 heredoc(`bash <<'BASH' … BASH`)의 본문 — 데이터가 아니라 **셸 명령**이다.
    실측(plan-removal B1): 명령 전체를 bash heredoc 으로 감싸 `python3 $W/plan/make_final.py … plan-final.md` 를 실행했는데,
    heredoc 본문을 지우는 _shell_part 가 그 명령을 통째로 버려 끝점을 놓쳤다."""
    out = []
    for m in SH_HEREDOC_RE.finditer(cmd):
        rest = cmd[m.end():]
        end = re.search(rf"^{re.escape(m.group(2))}\s*$", rest, re.M)
        out.append(rest[:end.start()] if end else rest)
    return out


def _cmd_views(cmd):
    """판정용 명령 모양들 — 원 명령 · `\\⏎` 줄 이어쓰기를 합친 명령 · 같은 명령의 대입으로 셸 변수를 편 명령.
    실측(plan B2-removal): `X=".../gpt-exec.sh"; ( "$X" exec … )` 로 부른 GPT 가 호출로 안 잡혀 GPT 0건 · Phase 2 없음이 됐다.
    실측(plan C2-removal): `gpt-exec.sh exec … \\⏎ --schema …gpt_review_schema` 가 한 줄 판정에서 빠졌다."""
    out = []
    for base in [cmd] + _shell_heredoc_bodies(cmd):
        joined = re.sub(r"\\\n[ \t]*", " ", base)
        for c in (base, joined) + tuple(_expand_vars(joined)):
            if c not in out:
                out.append(c)
    return out


PHASE2_RE = re.compile(r"gpt-exec\.sh[\"']?\s+(?:exec\b[^\n]*gpt_review_schema|resume\b)")


def queued_followups(evs, first_prompt):
    """후속 턴이 모델 작업 중에 도착해 대기열에서 **턴 한가운데** 끼어든 횟수 — `attachment.type == queued_command` 이면서
    첫 프롬프트가 아닌 사람 프롬프트. 실측(2026-09-29): 후속 턴이 있는 7 run 전부가 도구 결과 바로 뒤에 끼어들었고,
    plan 2건은 그 '승인' 을 받고 Phase 2 를 건너뛰었다. ⛔ 러너의 유휴 판정과 독립된 원천(transcript)으로 센다."""
    n = 0
    for ev in evs:
        a = ev.get("attachment") if ev.get("type") == "attachment" else None
        if isinstance(a, dict) and a.get("type") == "queued_command":
            pr = str(a.get("prompt") or "").strip()
            # ⛔ 하네스 내부 메시지(작업 알림 · 하위 에이전트 보고 — isMeta · origin · `<…>` 태그로 시작)는 사람 프롬프트가 아니다
            if a.get("isMeta") or a.get("origin") or pr.startswith("<"):
                continue
            if pr and pr != (first_prompt or "").strip():
                n += 1
    return n


LAUNCHER_RE = re.compile(r"gpt_independent\.sh[\"']?\s+(plan|review)\b")


def _launcher_calls(bash, notifs, results):
    """GPT 독립 첫 패스 런처 호출마다 {mode, launch, done, wall_s} — 시작 = 도구 호출 시각, 끝 = 완료 알림(백그라운드) 또는
    도구 결과(포그라운드). ⛔ 읽기(`sed -n … gpt_independent.sh`)는 모드 인자가 없어 걸리지 않는다."""
    out = []
    for u in bash:
        m = None
        for v in _cmd_views(str(u["input"].get("command") or "")):
            m = LAUNCHER_RE.search(_shell_part(v))
            if m:
                break
        if not m:
            continue
        nt, res = notifs.get(u["id"]) or {}, results.get(u["id"]) or {}
        done = nt.get("ts") or res.get("ts")
        out.append({"mode": m.group(1), "launch": iso(u["ts"]), "done": iso(done), "wall_s": secs(u["ts"], done)})
    return out


def _plan_phase2(tool_uses, results):
    """fz-plan Phase 2 GPT 검증을 실행했는가 — B 는 verify(gpt_review_schema), C 는 resume 교차. 실패한 호출은 세지 않는다."""
    for u in tool_uses:
        if u["name"] == "Bash" and not (results.get(u["id"]) or {}).get("is_error") \
                and any(PHASE2_RE.search(_shell_part(v)) for v in _cmd_views(str(u["input"].get("command") or ""))):
            return True
    return False


def _launcher_ok(audit):
    """런처 감사 파일 → 성공 여부. `exit == 0` 은 gpt_independent.sh 가 격리 적용 · 오염 적중 없음 · 시한 안 ·
    래퍼 exit 0 · 출력 읽힘 · 후검사 통과를 모두 확인한 뒤에만 쓴다. ⛔ 읽기 실패 · 다른 값은 성공이 아니다(fail-closed)."""
    try:
        with open(audit, encoding="utf-8") as fh:
            return json.load(fh).get("exit") == 0
    except (OSError, ValueError, AttributeError):
        return False


def gpt_home_sessions(home):
    """arm 별 GPT 홈의 세션(rollout) → [{model, effort, version, session}] · 홈이 없으면 None(옛 run — 배너 연결로만 판정).
    ⛔ turn_context 가 없는 세션(첫 턴 전에 끝난 것)은 GPT 호출로 세지 않는다."""
    if not home or not os.path.isdir(home):
        return None
    d = os.path.join(home, "sessions")
    if not os.path.isdir(d):
        return []
    out = []
    for f in sorted(pathlib.Path(d).rglob("*.jsonl")):
        m = e = v = sid = None
        with open(f, encoding="utf-8", errors="replace") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                pl = r.get("payload") or {}
                if r.get("type") == "session_meta":
                    # ⛔ review 모드는 부모(배너의 session id) · 자식(모델 턴) 두 세션이다 — 자식의 session_id 가 부모를 가리킨다
                    v, sid = pl.get("cli_version"), pl.get("session_id") or pl.get("id")
                elif r.get("type") == "turn_context" and m is None:
                    m, e = pl.get("model"), pl.get("effort")
        if m and e:
            out.append({"model": m, "effort": e, "version": v, "session": sid})
    return out


def _bash_writes(cmd, a, cwd, scripts=None):
    """완료된 Bash 한 번이 산출물 `a` 를 썼는가 — 원 명령과, 셸 변수·`for` 값을 편 명령마다
    리다이렉트·cp/mv 대상 · 파이썬 쓰기 표현 · argv 로 넘긴 경로의 쓰기를 본다."""
    base = os.path.basename(a)
    for c in [v for x in [cmd] + _shell_heredoc_bodies(cmd) for v in _expand_vars(x)]:
        bases = _cd_bases(c, cwd) or [""]
        dests = _redirect_targets(c) + [m.group(2) for m in CPMV_RE.finditer(_shell_part(c))]
        for seg in _segments(_shell_part(c)):
            dests += _sed_inplace_files(seg) + _render_outputs(seg)   # 실측(C1): sed -i '' … self-review.md · 렌더러 --out-dir
        if any(_same_path(x if os.path.isabs(x) else os.path.join(b, x), a) for x in dests for b in bases) \
                or _writes_path(c, base) or _argv_writes(c, a, bases) or _script_argv_writes(c, a, bases, scripts):
            return True
    return False


def parse_transcript(path, artifacts=(), tasks_dirs=()):
    """Lead transcript 1개 → Lead 층 지표. I/O 는 파일 읽기뿐이다."""
    evs, bad = iter_jsonl(path)
    per_id, usage_by_id, advisor_ids, versions = {}, {}, set(), set()
    tool_uses, results = [], {}
    roots, skills = set(), set()
    injected, injected_paths = {}, {}
    prompts = []
    notifs = {}
    cwds = collections.Counter()
    start_cwd = None
    for n, ev in enumerate(evs):
        if ev.get("type") in ("user", "assistant") and ev.get("cwd"):
            cwds[ev["cwd"]] += 1
            start_cwd = start_cwd or ev["cwd"]
        t = wfm._ts(ev.get("timestamp"))
        if ev.get("version"):
            versions.add(ev["version"])
        raw = json.dumps(ev, ensure_ascii=False)
        for m in BASE_DIR_RE.finditer(raw):
            p = m.group(1)
            if "/skills/" in p:
                r, _, sk = p.rpartition("/skills/")
                # ⛔ 실재하는 경로만 — 문서가 인용한 헤더 형식(`…/skills/fz-gpt` · `{플러그인 루트}/skills/…`)을 로드로 세지 않는다.
                #    실측 2026-09-26: peer-review 가 읽은 cross-validation.md 의 인용 한 줄이 루트 '…' 를 더해 "경로 2개"·"코드 변경" 거짓 판정
                if not os.path.isdir(r):
                    continue
                roots.add(r)
                skills.add(sk.split("/")[0])
        for s in _strings(ev):
            for m in NOTIF_RE.finditer(s):
                tid = _tag(m.group(1), "tool-use-id")
                if not tid:
                    continue
                rec = {"ts": t, "status": _tag(m.group(1), "status"), "result": _tag(m.group(1), "result"),
                       "output_file": _tag(m.group(1), "output-file"), "summary": _tag(m.group(1), "summary")}
                old = notifs.get(tid)
                if old is None or (t and old["ts"] and t < old["ts"]):
                    # 가장 이른 기록이 완료 시각에 가장 가깝다(큐 적재 시각)
                    if old and not rec["result"]:
                        rec["result"] = old["result"]
                    notifs[tid] = rec
                elif not old["result"] and rec["result"]:
                    old["result"] = rec["result"]
        att = ev.get("attachment") if isinstance(ev.get("attachment"), dict) else {}
        if att.get("type") == "instructions" and not injected:
            for f in att.get("files") or []:
                k = f.get("type") or "?"
                injected.setdefault(k, sha_text(f.get("content") or ""))
                injected_paths.setdefault(k, f.get("path"))
        msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
        content = msg.get("content")
        if ev.get("type") == "assistant":
            mid = msg.get("id") or f"anon-{n}"
            per_id[mid] = (msg.get("model"), ev.get("effort"))
            if msg.get("stop_reason"):
                usage_by_id[mid] = msg.get("usage") or {}
            for b in content or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "advisor_tool_result":
                    advisor_ids.add(b.get("tool_use_id") or f"anon-{n}")
                elif b.get("type") == "tool_use":
                    tool_uses.append({"ts": t, "id": b.get("id"), "name": b.get("name"),
                                      "input": b.get("input") or {}, "cwd": ev.get("cwd") or ""})
        text = None
        if ev.get("type") == "user" and not ev.get("isMeta"):
            if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        c = b.get("content")
                        body = c if isinstance(c, str) else " ".join(
                            x.get("text") or "" for x in (c or []) if isinstance(x, dict))
                        results[b.get("tool_use_id")] = {"ts": t, "is_error": bool(b.get("is_error")),
                                                         "tur": ev.get("toolUseResult"), "text": body}
            elif isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "\n".join(b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text")
        elif att.get("type") == "queued_command" and att.get("humanTurn") and isinstance(att.get("prompt"), str):
            text = att["prompt"]
        if text and text.strip() and "<task-notification>" not in text and "Base directory for this skill" not in text \
                and not text.lstrip().startswith("<system-reminder>"):
            if not prompts or prompts[-1][1] != text:
                prompts.append((t, text))

    models = collections.Counter(norm_model(m) for m, _ in per_id.values() if m and m != "<synthetic>")
    efforts = collections.Counter(e for m, e in per_id.values() if e and m != "<synthetic>")
    bash = [u for u in tool_uses if u["name"] == "Bash"]
    heredoc_targets, inline_py = [], 0
    for u in bash:
        cmd = str(u["input"].get("command") or "")
        inline_py += len(INLINE_PY_RE.findall(cmd))
        if "<<" in cmd:
            heredoc_targets += [os.path.basename(x) for x in _redirect_targets(cmd)]
    tool_errors = sum(1 for r in results.values() if r["is_error"])

    workflows = []
    for u in tool_uses:
        if u["name"] != "Workflow":
            continue
        r = results.get(u["id"]) or {}
        tur = r.get("tur") if isinstance(r.get("tur"), dict) else {}
        nt = notifs.get(u["id"]) or {}
        ret, wrapper, src = _load_return(nt, tasks_dirs)
        workflows.append({
            "tool_use_id": u["id"], "launch": iso(u["ts"]), "rejected": bool(r.get("is_error")),
            "run_id": tur.get("runId"), "dir": tur.get("transcriptDir"), "name": tur.get("workflowName"),
            "done": iso(nt.get("ts")), "status": nt.get("status"), "lead_s": secs(u["ts"], nt.get("ts")),
            "return_mode": ret.get("mode") if ret else None, "tier": ret.get("tier") if ret else None,
            "return_conflict": bool(ret and ret.get("_conflict")),
            "metrics": ret.get("metrics") if ret and isinstance(ret.get("metrics"), dict) else None,
            "stage2_ran": ret.get("stage2Ran") if ret else None,
            "return_source": src, "output_file": _resolved_output(nt.get("output_file"), tasks_dirs),
            "agent_count": wrapper.get("agentCount") if wrapper else None,
        })

    gpt = []
    for u in bash:
        call = None
        for view in _cmd_views(str(u["input"].get("command") or "")):   # ⛔ 변수로 부른 래퍼(`"$X" exec`)도 호출이다
            cmd = _shell_part(view)
            call = GPT_CALL_RE.search(cmd)
            if call:
                break
        if not call:
            continue
        seg = _call_segment(cmd, call)
        m = GPT_OUT_RE.search(seg)
        out = m.group(2) if m else None
        if out and "$" in out:
            # ⛔ 변수 경로는 같은 명령의 대입 · cd · $PWD 로 푼다 — 병렬 호출이 시간창 후보 2개로 미연결되던 것(plan B1 배너 1/5).
            #    풀린 경로(또는 그 스트림 로그)가 **실재할 때만** 쓴다 — 틀리게 풀면 성공 호출이 '빈 출력' 실패가 된다(review B2 실측)
            r_ = _resolve_vars(out, str(u["input"].get("command") or ""), u["cwd"])
            if "$" not in r_:
                r_ = r_ if os.path.isabs(r_) else os.path.join(u["cwd"] or "", r_)
                if os.path.exists(r_) or os.path.exists(r_ + ".stream.log"):
                    out = r_
        if out and not os.path.isabs(out) and "$" not in out:
            out = os.path.join(u["cwd"], out)
        nt, res = notifs.get(u["id"]) or {}, results.get(u["id"]) or {}
        done = nt.get("ts") or res.get("ts")
        if nt:   # 백그라운드 — 완료 알림의 상태·종료 코드 + 작업 출력의 GATE-PASS(래퍼는 비지 않은 출력 확인 뒤에만 찍는다)
            of = nt.get("output_file")
            if not of:
                m2 = re.search(r"Output is being written to: (\S+)", res.get("text") or "")
                of = m2.group(1).rstrip(".") if m2 else None
            of = _resolved_output(of, tasks_dirs)
            try:
                with open(of, encoding="utf-8", errors="replace") as fh:
                    task_out = fh.read()
            except (OSError, TypeError):
                task_out = ""
            ok = (nt.get("status") == "completed" and not re.search(r"exit code [1-9]", nt.get("summary") or "")
                  and "GATE-PASS" in task_out)
        else:    # 포그라운드 — 도구 결과가 오류가 아니고 래퍼의 사후 게이트 통과 표시가 있다
            ok = bool(res) and not res.get("is_error") and "GATE-PASS" in (res.get("text") or "")
        if not ok and (nt.get("status") == "completed" and not re.search(r"exit code [1-9]", nt.get("summary") or "")
                       if nt else (bool(res) and not res.get("is_error"))):
            # ⛔ 래퍼 출력을 로그 파일로 돌린 호출(`… gpt-exec.sh … > $W/gpt-da.log 2>&1`)은 GATE-PASS 가 그 파일에 있다(실측 peer C1)
            full = str(u["input"].get("command") or "")
            for tgt in _redirect_targets(seg):
                f = _resolve_vars(tgt, full, u["cwd"])
                if "$" in f:
                    continue
                f = f if os.path.isabs(f) else os.path.join(u["cwd"] or "", f)
                try:
                    with open(f, encoding="utf-8", errors="replace") as fh:
                        if "GATE-PASS" in fh.read():
                            ok = True
                            break
                except OSError:
                    continue
        if ok and out and "$" not in out:
            try:   # ⛔ 출력 파일이 비었으면 성공이 아니다(래퍼 게이트 13 과 같은 조건)
                ok = os.path.getsize(out) > 0
            except OSError:
                ok = False
        real_home = bool(REAL_HOME_SKILL_RE.search(str(u["input"].get("command") or "")))
        gpt.append({"out": out, "launch": iso(u["ts"]), "done": iso(done), "wall_s": secs(u["ts"], done), "ok": ok,
                    "real_home_skill": real_home,
                    "t0": u["ts"].timestamp() if u["ts"] else None, "t1": done.timestamp() if done else None,
                    "explicit_effort": bool(re.search(r"--effort\b", seg))})

    # 최종 산출물 기록 이벤트 — 산출물을 가리키는 도구 호출 중 **파일 mtime 에 가장 가까운** 결과 시각.
    #   ⛔ '마지막으로 가리킨 호출' 을 쓰면 쓰기 뒤의 읽기(cat·Read)가 끝점이 된다. 경로를 변수로 쓴
    #      파이썬 heredoc 도 잡으려고 basename 까지 후보로 보고, mtime 으로 쓰기를 고른다(wall 은 transcript 시계).
    py_scripts = {}   # Lead 가 Write 로 만든 .py 본문 — 곧 지워도 transcript 에 남는다
    for u in tool_uses:
        fp = str(u["input"].get("file_path") or "") if u["name"] == "Write" else ""
        if fp.endswith(".py"):
            py_scripts[os.path.normpath(fp if os.path.isabs(fp) else os.path.join(u["cwd"] or "", fp))] = str(u["input"].get("content") or "")
    art = []
    for a in artifacts:
        mtime = None
        try:
            mtime = os.path.getmtime(a)
        except OSError:
            pass
        cands = []
        for u in tool_uses:
            res = results.get(u["id"])
            if not res or res["is_error"] or not res["ts"]:
                continue      # ⛔ 완료되지 않았거나 실패한 호출은 '기록' 이 아니다
            hit = False
            if u["name"] in WRITE_TOOLS:
                fp = u["input"].get("file_path") or u["input"].get("notebook_path")
                hit = bool(fp) and _same_path(fp if os.path.isabs(fp) else os.path.join(u["cwd"], fp), a)
            elif u["name"] == "Bash":
                hit = _bash_writes(str(u["input"].get("command") or ""), a, u["cwd"], py_scripts)
            if hit:
                cands.append(res["ts"])
        if not cands:
            write = None
        elif mtime is None:
            write = max(cands)
        else:
            write = min(cands, key=lambda d: abs(d.timestamp() - mtime))
        try:
            with open(a, "rb") as fh:
                data = fh.read()
            sha, size, blank = hashlib.sha256(data).hexdigest(), len(data), not data.strip()
        except OSError:
            sha, size, blank = None, None, None
        art.append({"path": a, "write": write, "mtime": mtime, "sha256": sha, "bytes": size, "blank": blank})

    start = prompts[0][0] if prompts else None
    writes = [x["write"] for x in art if x["write"]]
    end = max(writes) if len(writes) == len(art) and art else None
    deltas = [x["mtime"] - x["write"].timestamp() for x in art if x["write"] and x["mtime"] is not None]
    return {
        "bad_lines": bad,
        "lead": {
            "model": models.most_common(1)[0][0] if len(models) == 1 else (None if not models else "mixed"),
            "models": dict(models), "effort": efforts.most_common(1)[0][0] if len(efforts) == 1 else
            (None if not efforts else "mixed"), "efforts": dict(efforts), "cli_versions": sorted(versions),
            "out_tok": sum((u.get("output_tokens") or 0) for u in usage_by_id.values()) if usage_by_id else None,
            "messages": len(per_id), "tool_calls": len(tool_uses), "tool_errors": tool_errors,
            "retries": tool_errors, "bash_arg_chars": sum(len(str(u["input"].get("command") or "")) for u in bash),
            "heredoc_targets": heredoc_targets, "inline_python": inline_py,
            "followup_prompts": max(0, len({p for _, p in prompts}) - 1), "advisor": len(advisor_ids),
        },
        "roots": sorted(roots), "skills": sorted(skills),
        "injected": injected, "injected_paths": injected_paths,
        "prompt_sha": sha_text(prompts[0][1]) if prompts else None,
        "start": start, "end": end,
        "mtime_delta_s": round(max(deltas, key=abs), 3) if deltas and len(deltas) == len(art) else None,
        "artifacts": [dict(x, write=iso(x["write"])) for x in art],
        "workflows": workflows, "gpt": gpt, "cwd": start_cwd, "launcher": _launcher_calls(bash, notifs, results),
        "merge": _merge_summaries(tool_uses, results), "plan_phase2": _plan_phase2(tool_uses, results),
        "queued_followups": queued_followups(evs, prompts[0][1] if prompts else None),
        # ⛔ Lead 작업 폴더 = **세션 시작** cwd(러너가 claude -p 를 띄운 곳). 최빈 cwd 는 잡음이다 — Lead 는 --add-dir 로 받은
        #    플러그인 폴더에 들어가 모듈 · 스크립트를 읽고 부른다(실측 review B1 repo 70:plugin 53 통과 · B2 125:128 무효 ·
        #    C1 11:129 무효). 스크립트를 더 부르는 C 가 구조적으로 무효가 되는 편향이었다. 폴더별 이벤트 수는 cwds 로 남긴다
        "cwds": dict(cwds),
    }


# ── Workflow 폴더 · 상태 · 입력 · 플러그인 · GPT 로그 ─────────────────────────
REQUIRED_WATCH = ("user_agent_memory", "repo_agent_memory", "user_sessions")   # 프로토콜 §2 — 없으면 AC-7 판정 불가
# 이름별 정본 경로 — 이름만 맞고 엉뚱한 곳을 보면 감시가 아니다(repo_agent_memory 는 그 run 의 입력 저장소 안)
CANON_WATCH = {"user_agent_memory": "~/.claude/agent-memory", "user_sessions": "~/.claude/sessions"}
# 폴더에 다른 주체의 파일이 섞인 감시 이름은 파일 패턴도 정본이어야 한다(세션 등록·키 파일은 run 마다 바뀐다)
CANON_PATTERN = {"user_sessions": "SESSION-*_issues.json"}
ALLOWED_PLUGIN_WRITES = ("experiment-log.md",)   # 스킬이 플러그인 루트에 쓰는 지표 파일(RV:103 · PL:139) — 코드 아님


def _required_stages(workflow, stage2_ran, tier=None):
    """건강한 run 에서 반드시 돈 stage — 반환이 알려 준 실행 모드(tier·Stage 2)를 따른다."""
    need = list(REQUIRED_STAGES.get(workflow, ()))
    if workflow == "fz-review" and stage2_ran is False:   # 조건부 Stage 2 arm 이 '안 돌렸다' 고 반환한 경우만 뺀다
        need = [x for x in need if not x.startswith("R2-")]
    if workflow == "fz-peer-review":
        if stage2_ran:
            need += ["R2-arch", "R2-quality"]
        if tier == 3:
            need += ["R3-counter"]
    return need


def _expected_stages_completed(workflow, stage2_ran, tier=None):
    """반환 metrics.stagesCompleted 의 기대값(base 트리 실측 — plan-lean2:231 · review-live:220 · peer-review:385·449·511)."""
    if workflow == "fz-plan":
        return 2
    if workflow == "fz-review":
        return 2 if stage2_ran is False else 3
    if workflow == "fz-peer-review":
        if tier == 3:
            return 3
        if tier == 2:
            return 2 if stage2_ran else 1
    return None


def wf_summary(folder):
    if not folder or not os.path.isdir(folder):
        return None
    w = wfm.read_wf(folder)
    started = empty = 0
    jp = os.path.join(folder, "journal.jsonl")
    if os.path.isfile(jp):
        for ev in iter_jsonl(jp)[0]:
            if ev.get("type") == "started":
                started += 1
            elif ev.get("type") == "result":
                r = ev.get("result")
                if isinstance(r, str) and r.strip().startswith("{"):
                    try:   # JSON 문자열로 기록된 결과도 구조로 본다(오류 필드를 놓치지 않게)
                        r = json.loads(r)
                    except ValueError:
                        pass
                # ⛔ 건수만 세면 빈 결과·오류 결과도 완주로 읽힌다
                if r in (None, "", {}, []) or (isinstance(r, dict) and (
                        set(r) <= {"error"} or r.get("ok") is False or r.get("error") or r.get("isError"))):
                    empty += 1
    models, efforts = collections.Counter(), collections.Counter()
    for f in sorted(glob.glob(os.path.join(folder, "agent-*.jsonl"))):
        per_id = {}
        evs, _ = iter_jsonl(f)
        for n, ev in enumerate(evs):
            if ev.get("type") == "assistant" and isinstance(ev.get("message"), dict):
                msg = ev["message"]
                per_id[msg.get("id") or f"anon-{n}"] = (msg.get("model"), ev.get("effort"))
        for m, e in per_id.values():
            if m and m != "<synthetic>":
                models[norm_model(m)] += 1
                if e:
                    efforts[e] += 1
    return {
        "run_id": w["wf"], "dir": folder, "n_agents": w["n_agents"], "journal_results": w["journal_results"],
        "journal_started": started, "journal_empty_results": empty,
        "wall_s": w["wall"], "critical_path_s": w["critical_path"], "advisor": w["advisor"],
        "out_tok": w["out_tok"], "thinking": w["thinking"], "turns": sum(a["turns"] for a in w["agents"]),
        "so_retries": w["so_retries"], "so_errors": w["so_errors"], "stages": w["stages_seen"],
        "tokens_partial": w["tokens_partial"], "errors": w["errors"],
        "bad_lines": sum(a["bad_lines"] for a in w["agents"]),
        "workers": [{"stage": a["stage"], "out_tok": a["out_tok"], "turns": a["turns"], "tools": a["tools"],
                     "dur_s": a["dur"]} for a in w["agents"]],
        "models": dict(models), "efforts": dict(efforts),
    }


def snapshot(watch: dict) -> dict:
    """{이름: 경로[::파일 패턴]} → 존재 여부 + 파일별 sha256. 해시는 **이름·존재·상대 경로·내용**만 본다 — run 마다
    저장소 경로가 달라도 같다(경로는 기록만 한다). `::패턴` 은 폴더 안에서 그 패턴(fnmatch)에 맞는 파일만 본다 —
    `~/.claude/sessions` 처럼 다른 주체의 파일(세션 등록·키)이 섞인 폴더에서 fz 트래커만 감시할 때 쓴다."""
    import fnmatch
    out = {}
    for name, spec in sorted(watch.items()):
        path, _, pattern = spec.partition("::")
        p = pathlib.Path(os.path.expanduser(path))
        files = {}
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                rel = str(f.relative_to(p))
                if f.is_file() and (not pattern or fnmatch.fnmatch(rel, pattern)):
                    files[rel] = fb.hash_file(f)
        elif p.is_file():
            files[p.name] = fb.hash_file(p)
        out[name] = {"path": str(p), "pattern": pattern or None, "exists": p.exists(), "files": files}
    return {"schema": STATE_SCHEMA, "watch": out, "hash": state_hash(out)}


def _state_key(v):
    return [bool((v or {}).get("exists")), (v or {}).get("files", {})]


def state_hash(watch) -> str:
    return sha_obj({k: _state_key(v) for k, v in watch.items()})


def state_diff(a, b):
    """두 스냅샷에서 존재·파일 집합·내용이 다른 이름. 한쪽에만 있는 이름은 '없음' 과 비교한다."""
    return [n for n in sorted(set(a) | set(b)) if _state_key(a.get(n)) != _state_key(b.get(n))]


def state_info(pristine, start, end, input_root=None):
    """→ 해시 · leak(시작 ≠ 기준) · writes(종료 − 시작) · problems(감시 누락·경로 불일치 — AC-7 판정 불가)."""
    try:
        p, s = read_json(pristine), read_json(start)
    except (OSError, ValueError, TypeError):
        return {"start_hash": None, "pristine_hash": None, "end_hash": None, "leak": None, "writes": None,
                "problems": ["스냅샷을 읽지 못했다"]}
    e = None
    try:
        e = read_json(end) if end else None
    except (OSError, ValueError):
        e = None
    snaps = [("pristine", p), ("start", s)] + ([("end", e)] if e else [])
    problems = [f"{which} 에 감시 이름 {n} 없음" for which, snap in snaps
                for n in REQUIRED_WATCH if n not in (snap.get("watch") or {})]
    if not e:
        problems.append("종료 스냅샷 없음")
    for which, snap in snaps:
        for n, canon in CANON_WATCH.items():
            w = (snap.get("watch") or {}).get(n) or {}
            got = w.get("path")
            if got and os.path.expanduser(got) != os.path.expanduser(canon):
                problems.append(f"{which} 의 {n} 경로가 정본({canon})이 아니다: {got}")
            if n in CANON_PATTERN and w and w.get("pattern") != CANON_PATTERN[n]:
                problems.append(f"{which} 의 {n} 파일 패턴이 정본({CANON_PATTERN[n]})이 아니다: {w.get('pattern')}")
    rp = ((s.get("watch") or {}).get("repo_agent_memory") or {}).get("path")
    want = os.path.join(os.path.realpath(input_root), ".claude", "agent-memory") if input_root else None
    if not rp:
        problems.append("start 의 repo_agent_memory 경로가 비었다")
    elif want and os.path.realpath(rp) != want:
        problems.append(f"repo_agent_memory 감시 경로가 입력 저장소의 .claude/agent-memory 가 아니다: {rp}")
    # ⛔ 종료 쪽도 같은 곳을 봐야 한다 — 경로는 해시 키가 아니라서, 둘 다 빈 다른 폴더면 '쓰기 없음' 으로 같게 읽힌다(v4.40.0 리뷰)
    ep = ((e.get("watch") or {}).get("repo_agent_memory") or {}).get("path") if e else None
    if e and rp and (not ep or os.path.realpath(ep) != os.path.realpath(rp)):
        problems.append(f"end 의 repo_agent_memory 경로가 start 와 다르다: {ep}")
    writes = None
    if e:
        writes = {}
        for n in state_diff(s["watch"], e["watch"]):
            a = (s["watch"].get(n) or {}).get("files", {})
            b = (e["watch"].get(n) or {}).get("files", {})
            writes[n] = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    return {"start_hash": state_hash(s["watch"]), "pristine_hash": state_hash(p["watch"]),
            "end_hash": state_hash(e["watch"]) if e else None,
            "leak": state_diff(p["watch"], s["watch"]), "writes": writes, "problems": problems}


def input_commits(root):
    commits = {}
    if root and os.path.isdir(root):
        for ref in ("main", "feature"):
            out = fb.git(pathlib.Path(root), "rev-parse", "--verify", "--quiet", ref + "^{commit}")
            if out and out.strip():
                commits[ref] = out.strip()
        if not commits:
            out = fb.git(pathlib.Path(root), "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
            if out and out.strip():
                commits["HEAD"] = out.strip()
    return commits


def tree_digest(root, exclude=()):
    """git 이 보는 작업 트리 파일(추적 + 미추적 비무시)의 내용 해시 — freeze_baseline 헬퍼. exclude 는 루트 상대 경로."""
    files = fb.tree_files(pathlib.Path(root), exclude=exclude) if root and os.path.isdir(root) else None
    if not files:
        return None
    got, unread = fb.collect_hashes(pathlib.Path(root), files)
    return None if unread else sha_obj(got)


def input_hash(fixture, commits, prompt_sha, tree=None):
    if not commits or not prompt_sha:
        return None
    return sha_obj({"fixture": fixture, "commits": commits, "prompt_sha": prompt_sha, "tree": tree})


def plugin_info(root):
    if not root or not os.path.isdir(root):
        return {"root": root, "sha": None, "dirty": None, "tree_hash": None}
    p = pathlib.Path(root)
    sha = (fb.git(p, "rev-parse", "HEAD") or "").strip() or None
    st = fb.git(p, "status", "--porcelain", "--untracked-files=all")
    return {"root": root, "sha": sha, "dirty": (bool(st.strip()) if st is not None else None), "tree_hash": tree_digest(root),
            "code_hash": tree_digest(root, exclude=ALLOWED_PLUGIN_WRITES)}


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def parse_gpt_log(path):
    """GPT 스트림 로그 배너 → model·reasoning effort·CLI 버전·session id. 둘째 구분선 전까지만 본다."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = ANSI_RE.sub("", fh.read()).splitlines()
    except (OSError, TypeError):
        return None
    info = {"model": None, "effort": None, "version": None, "session": None}
    seps = 0
    for line in lines[:60]:
        if line.startswith("--------"):
            seps += 1
            if seps >= 2:
                break
            continue
        m = re.match(r"^model:\s*(\S+)", line)
        if m:
            info["model"] = m.group(1)
        m = re.match(r"^reasoning effort:\s*(\S+)", line)
        if m:
            info["effort"] = m.group(1)
        m = re.match(r"^session id:\s*([0-9a-f-]{36})", line)
        if m:
            info["session"] = m.group(1)
        m = re.search(r"\bv(\d+\.\d+\.\d+)\s*$", line)
        if m and seps == 0 and not info["version"]:
            info["version"] = m.group(1)
    return info


# ── collect ────────────────────────────────────────────────────────────
def _evidence_dir(a):
    return a.evidence_dir or os.path.join(os.path.dirname(os.path.abspath(a.ledger)), "evidence")


def build_row(a, dry=False) -> dict:
    """원천 → 원장 행. dry=True 는 원천 대조용 재구성이다(증거 사본을 쓰지 않는다)."""
    evdir = _evidence_dir(a)
    tp = parse_transcript(a.transcript, a.artifact or [], list(a.tasks_dir or []) + [evdir])
    why = []
    if tp["bad_lines"]:
        why.append(f"transcript 파싱 불가 줄 {tp['bad_lines']}")
    if not tp["start"]:
        why.append("첫 사람 발화 없음")
    wf_runs, walls = [], []
    for w in tp["workflows"]:
        if w["rejected"]:
            continue
        s = wf_summary(w["dir"])
        entry = {k: w[k] for k in ("run_id", "name", "launch", "done", "status", "lead_s", "return_mode",
                                   "metrics", "stage2_ran", "return_source", "agent_count")}
        entry["summary"] = s
        if w["return_source"] == "output-file":
            # ⛔ /tmp 의 하네스 산출은 지워질 수 있다 — 같은 파일명으로 사본을 남겨 재구성 대조가 찾게 한다
            entry["return_file"] = os.path.join(evdir, os.path.basename(w["output_file"]))
            if not dry and not _same_path(w["output_file"], entry["return_file"]):
                os.makedirs(evdir, exist_ok=True)
                shutil.copyfile(w["output_file"], entry["return_file"])
        wf_runs.append(entry)
        if w["status"] != "completed":
            why.append(f"{w['run_id']}: 완료 알림 없음·상태 {w['status']}")
        if s is None:
            why.append(f"{w['run_id']}: Workflow 폴더 없음 ({w['dir']})")
            walls.append({"run_id": w["run_id"], "wf_s": None, "lead_s": w["lead_s"], "delta_pct": None})
            continue
        if s["bad_lines"] or s["errors"]:
            why.append(f"{w['run_id']}: 폴더 오류 {s['errors'][:2]}")
        if s["journal_empty_results"]:
            why.append(f"{w['run_id']}: 빈·오류 결과 {s['journal_empty_results']}건")
        lost = [x for x in _required_stages(a.workflow, w["stage2_ran"], w["tier"]) if x not in s["stages"]]
        if lost or a.workflow not in REQUIRED_STAGES:
            why.append(f"{w['run_id']}: 필수 stage 누락 {lost or '(필수 stage 표 없음)'}")
        exp_sc = _expected_stages_completed(a.workflow, w["stage2_ran"], w["tier"])
        got_sc = (w["metrics"] or {}).get("stagesCompleted")
        if w["metrics"] is not None and (exp_sc is None or got_sc != exp_sc):
            why.append(f"{w['run_id']}: stagesCompleted={got_sc} ≠ 기대 {exp_sc} (tier={w['tier']} stage2={w['stage2_ran']})")
        mt = w["metrics"]
        if w.get("return_conflict"):
            why.append(f"{w['run_id']}: 알림의 반환과 하네스 래퍼의 반환이 다르다(metrics·mode)")
        if mt is not None:
            # 주 오라클 — 스크립트 자기 계수 · 하네스 계수 · 폴더 계수가 모두 같아야 한다
            entry["oracle"] = "return-metrics" + ("+harness" if w["agent_count"] is not None else "")
            if w["return_mode"] != "workflow":
                why.append(f"{w['run_id']}: 반환 mode={w['return_mode']}")
            miss = [k for k in ("agentCalls", "nullCount", "fallbackCount") if not isinstance(mt.get(k), int)]
            if miss:
                why.append(f"{w['run_id']}: 반환 metrics 필드 누락 {miss} — 0 으로 읽지 않는다")
            elif mt["nullCount"] > 0 or mt["fallbackCount"] > 0:
                why.append(f"{w['run_id']}: nullCount={mt['nullCount']} fallbackCount={mt['fallbackCount']}")
            exp = mt.get("agentCalls")
            if not (s["n_agents"] == s["journal_results"] == s["journal_started"] == exp) or \
                    (w["agent_count"] is not None and w["agent_count"] != exp):
                why.append(f"{w['run_id']}: agents={s['n_agents']} started={s['journal_started']} "
                           f"results={s['journal_results']} agentCalls={exp} harness={w['agent_count']} — 완주 오라클 불일치")
        else:
            # 대체 오라클 — 반환을 못 읽었다(알림 잘림 + output-file 소실). 시작=결과=폴더 + 필수 stage(위)
            entry["oracle"] = "journal+stages"
            if a.workflow == "fz-peer-review":
                why.append(f"{w['run_id']}: 반환 없이는 실행 모드(tier·Stage 2)를 확인할 수 없다 — peer-review 는 대체 오라클 불가")
            if not (s["journal_started"] == s["journal_results"] == s["n_agents"]) or not s["n_agents"]:
                why.append(f"{w['run_id']}: 반환 없음 · started={s['journal_started']} results={s['journal_results']} "
                           f"agents={s['n_agents']} — 대체 오라클 불충족")
        wf_s, lead_s = s["wall_s"], w["lead_s"]
        delta = round(abs(wf_s - lead_s) / max(wf_s, lead_s) * 100, 2) if wf_s and lead_s else None
        walls.append({"run_id": w["run_id"], "wf_s": wf_s, "lead_s": lead_s, "delta_pct": delta})
    if not wf_runs:
        why.append("Workflow 미기동")
    if not a.artifact:
        why.append("--artifact 없음")
    elif not tp["end"]:
        why.append("최종 산출물 기록 이벤트 없음")
    for x in tp["artifacts"]:
        if x["sha256"] is None:
            why.append(f"산출물 없음 {x['path']}")
        elif x["blank"]:
            why.append(f"빈 산출물(공백뿐) {x['path']}")
    roots = tp["roots"]
    plugin = plugin_info(roots[0] if len(roots) == 1 else None)
    plugin["roots"] = roots
    if len(roots) != 1:
        why.append(f"플러그인 경로 {len(roots)}개(1개여야 한다): {roots}")
    inp = read_json(a.input_json) if a.input_json and os.path.isfile(a.input_json) else None
    if inp is None:
        # ⛔ 증거 부재 = 위반 — run 전 입력 신원(clean·트리 해시·플러그인)이 없으면 입력을 증명하지 못한다
        why.append(f"입력 기록 없음 {a.input_json}")
    root = os.path.realpath((inp or {}).get("root") or a.input_root) if ((inp or {}).get("root") or a.input_root) else None
    commits = (inp or {}).get("commits") if inp else input_commits(a.input_root)
    if inp:
        if inp.get("fixture") != a.fixture:
            why.append(f"입력 기록의 fixture {inp.get('fixture')} ≠ {a.fixture}")
        if inp.get("clean") is not True:
            why.append("입력 저장소가 run 전에 깨끗하지 않았다(미커밋·미추적 파일)")
        if not inp.get("tree_hash"):
            why.append("입력 트리 해시 없음 — 입력 신원을 증명하지 못한다")
    if root and tp["cwd"] and not (os.path.realpath(tp["cwd"]) + os.sep).startswith(root + os.sep):
        why.append(f"Lead 작업 폴더 {tp['cwd']} 가 입력 저장소 {root} 밖이다")
    pstart = (inp or {}).get("plugin")
    if not pstart:
        why.append("run 전 플러그인 신원 없음(input --plugin-root) — 실행 중 코드 변경을 판정하지 못한다")
    elif not pstart.get("source_tree_hash"):
        why.append("플러그인 원본 해시 없음(input --plugin-source) — 사본의 원본을 증명하지 못한다")
    if not a.state_end or not os.path.isfile(a.state_end):
        why.append("종료 스냅샷 없음 — run 중 상태 변화 기록이 없다")
    if pstart:
        # run 전에 잰 신원을 쓴다. 이 run 이 사본에 쓴 흔적(experiment-log 등)은 changed_during_run 으로만 남긴다
        if len(roots) == 1 and not _same_path(pstart.get("root"), roots[0]):
            why.append(f"transcript 의 플러그인 경로 {roots[0]} ≠ run 전 기록 {pstart.get('root')}")
        plugin = dict(pstart, roots=roots, changed_during_run=plugin.get("tree_hash") != pstart.get("tree_hash"),
                      code_changed_during_run=plugin.get("code_hash") != pstart.get("code_hash"))
        if plugin["code_changed_during_run"]:
            why.append("실행 중 플러그인 코드가 바뀌었다(허용 출력 " + ",".join(ALLOWED_PLUGIN_WRITES) + " 제외) — 측정 대상이 바뀐 run")
    else:
        plugin["at"] = "collect"
    gpt_logs = list(a.gpt_log or []) + [g["out"] + ".stream.log" for g in tp["gpt"]
                                        if g["out"] and os.path.isfile(g["out"] + ".stream.log")]
    # `--out "$W/…"` 처럼 변수로 쓴 호출은 경로를 풀 수 없다 — 지정 폴더에서 run 구간에 쓰인 로그를 찾는다
    lo = tp["start"].timestamp() - 5 if tp["start"] else None
    hi = tp["end"].timestamp() + 60 if tp["end"] else None
    for d in a.gpt_log_dir or []:
        for p in sorted(pathlib.Path(d).rglob("*.stream.log")):
            mt = p.stat().st_mtime
            if (lo is None or mt >= lo) and (hi is None or mt <= hi):
                gpt_logs.append(str(p))
    # ⛔ 호출마다 **자기** 배너를 1:1 로 붙인다 — 폴더의 로그 수만 세면 다른 run 의 로그가 빈자리를 채운다
    logs = []
    for pth in dict.fromkeys(gpt_logs):
        b = parse_gpt_log(pth)
        try:
            mt = os.path.getmtime(pth)
        except OSError:
            mt = None
        if b and b["model"] and b["effort"]:
            logs.append((pth, mt, b))
    used, banners, unlinked = set(), [], 0
    for g in tp["gpt"]:
        if not g["ok"]:
            continue
        direct = g["out"] + ".stream.log" if g["out"] and "$" not in g["out"] else None
        in_win = lambda x: x[1] is not None and g["t0"] is not None and g["t1"] is not None and g["t0"] - 2 <= x[1] <= g["t1"] + 30
        # ⛔ 직접 경로도 시간창 안이어야 한다(같은 경로에 남은 이전 run 로그) · 변수 경로는 후보가 **하나**일 때만
        cand = [x for x in logs if x[0] not in used and in_win(x) and (x[0] == direct if direct else True)]
        if len(cand) != 1:
            unlinked += 1
            continue
        used.add(cand[0][0])
        banners.append(dict(cand[0][2], explicit=g.get("explicit_effort", False)))
    # ② 런처(gpt_independent.sh) — 격리 폴더에서 돌아 arm 홈에 rollout 이 없다. 감사 옆 스트림 로그 배너로 model · effort 를 본다.
    #    effort 는 런처가 정한다(명시) — F-333 의 환경 기본값 비교에 넣지 않는다
    launched = launched_ok = 0
    for d in a.gpt_log_dir or []:
        for au in sorted(pathlib.Path(d).rglob("*.audit.json")):
            mt = au.stat().st_mtime
            if (lo is None or mt >= lo) and (hi is None or mt <= hi):
                b = parse_gpt_log(str(au)[:-len(".audit.json")] + ".json.stream.log")
                if b and b["model"] and b["effort"]:
                    banners.append(dict(b, explicit=True, launcher=True))
                    launched += 1
                    if _launcher_ok(au):
                        launched_ok += 1
    # ③ arm 별 GPT 홈 rollout 과 대조 — 명령과 연결되지 않은 세션(nohup 으로 떼어 띄운 호출)은 model · 버전만 비교에 넣고 수를 남긴다
    run_dir = os.path.dirname(os.path.realpath(a.input_json)) if a.input_json else None
    sessions = gpt_home_sessions(os.path.join(run_dir, "gpt-home")) if run_dir else None
    linked = {b.get("session") for b in banners if b.get("session")}
    invisible = [x for x in (sessions or []) if x["session"] not in linked]
    gw = [g["wall_s"] for g in tp["gpt"] if g["wall_s"] is not None]
    wsum = [s for s in (r["summary"] for r in wf_runs) if s]
    stages_completed = [(r["metrics"] or {}).get("stagesCompleted") for r in wf_runs]
    row = {
        "type": "run", "schema": SCHEMA, "run_id": a.run_id or f"{a.workflow}:{a.arm}:{a.run}:{a.phase}",
        "workflow": a.workflow, "arm": a.arm, "run": a.run, "order": a.order, "phase": a.phase,
        "release": a.release, "fixture": a.fixture,
        "lead": tp["lead"], "plugin": plugin, "injected": tp["injected"], "instrument_sha": instrument_sha(),
        "input": {"hash": input_hash(a.fixture, commits, tp["prompt_sha"], (inp or {}).get("tree_hash")),
                  "fixture": a.fixture, "root": root, "commits": commits, "prompt_sha": tp["prompt_sha"],
                  "tree_hash": (inp or {}).get("tree_hash")},
        "wall": {"total_s": secs(tp["start"], tp["end"]), "start": iso(tp["start"]), "end": iso(tp["end"]),
                 "mtime_delta_s": tp["mtime_delta_s"], "workflows": walls, "gpt_s": round(sum(gw), 3) if gw else None},
        "artifacts": [{"path": x["path"], "sha256": x["sha256"], "bytes": x["bytes"]} for x in tp["artifacts"]],
        "wf": {"runs": wf_runs, "agents": sum(s["n_agents"] for s in wsum),
               "out_tok": sum(s["out_tok"] for s in wsum) if wsum else None,
               "turns": sum(s["turns"] for s in wsum) if wsum else None,
               "so_retries": sum(s["so_retries"] for s in wsum) if wsum else None,
               "so_errors": sum(s["so_errors"] for s in wsum) if wsum else None,
               "advisor": sum(s["advisor"] for s in wsum),
               "models": dict(sum((collections.Counter(s["models"]) for s in wsum), collections.Counter())),
               "efforts": dict(sum((collections.Counter(s["efforts"]) for s in wsum), collections.Counter())),
               "stages": sorted({st for s in wsum for st in s["stages"]}),
               "stage2_ran": next((r["stage2_ran"] for r in wf_runs if r["stage2_ran"] is not None),
                                  any(st.startswith("R2-") for s in wsum for st in s["stages"]) if wsum else None),
               "stages_completed": (min(stages_completed) if stages_completed and None not in stages_completed else None),
               "rejections": sum(1 for w in tp["workflows"] if w["rejected"])},
        "gpt": {"calls": len(tp["gpt"]), "ok": sum(1 for g in tp["gpt"] if g["ok"]),
                "failed": sum(1 for g in tp["gpt"] if not g["ok"]), "banners": len(banners), "unlinked": unlinked,
                "models": sorted({b["model"] for b in banners} | {x["model"] for x in invisible}),
                "efforts": sorted({b["effort"] for b in banners}),
                "efforts_default": sorted({b["effort"] for b in banners if not b.get("explicit")}),
                "versions": sorted({b["version"] for b in banners if b["version"]} | {x["version"] for x in invisible if x["version"]}),
                "logs": sorted(set(gpt_logs)), "launcher": launched, "launcher_ok": launched_ok,
                "real_home_skill_refs": sum(1 for g in tp["gpt"] if g.get("real_home_skill")),
                "sessions": None if sessions is None else len(sessions), "invisible": len(invisible)},
        "state": state_info(a.state_pristine, a.state_start, a.state_end, root),
        "sources": {"transcript": os.path.abspath(a.transcript), "artifacts": [os.path.abspath(x) for x in a.artifact or []],
                    "wf_dirs": [w["dir"] for w in tp["workflows"] if not w["rejected"]],
                    "state_pristine": a.state_pristine, "state_start": a.state_start, "state_end": a.state_end,
                    "input_root": a.input_root, "input_json": a.input_json, "tasks_dirs": list(a.tasks_dir or [])},
        "collect_args": {k: v for k, v in vars(a).items() if k not in ("func", "cmd")},
    }
    row["merge"] = tp.get("merge")
    # S26 — GPT 독립 플랜 wall 이 Workflow wall 을 넘으면 임계 경로가 GPT 로 바뀐 것이다(계획 S26: 기록형 판정)
    lp = [x["wall_s"] for x in tp.get("launcher") or [] if x["mode"] == "plan" and x["wall_s"] is not None]
    ws = [w["lead_s"] for w in tp.get("workflows") or [] if w.get("lead_s") is not None and not w.get("rejected")]
    row["critical"] = {"gpt_plan_s": round(max(lp), 1) if lp else None, "wf_s": round(max(ws), 1) if ws else None,
                       "launchers": tp.get("launcher") or [],
                       "path": None if not (lp and ws) else ("gpt" if max(lp) > max(ws) else "workflow")}
    row["lead"]["queued_followups"] = tp.get("queued_followups", 0)
    if tp.get("queued_followups"):
        why.append(f"후속 턴이 모델 작업 중에 끼어들었다 {tp['queued_followups']}회(queued_command) — 표준 후속 턴 계약 위반")
    if a.workflow == "fz-plan" and not tp.get("plan_phase2"):
        why.append("plan Phase 2 GPT 검증 흔적 없음(verify · resume 교차 미실행) — 절차 미완주")
    row["complete"] = {"ok": not why, "why": why}
    return row


import contextlib   # noqa: E402 — 원장 쓰기 잠금에만 쓴다


@contextlib.contextmanager
def _ledger_lock(ledger):
    """원장 쓰기 잠금 — `원장.lock` 에 배타 flock. ⛔ append_many 는 읽고 바꿔 끼우므로, 잠그지 않으면 그 사이 다른 프로세스의
    append 행이 사라진다(v4.40.0 validate 2차). 모든 쓰기 경로가 이 잠금을 거친다.
    ⛔ POSIX 전용(`fcntl`) — 이 원장은 macOS·Linux 에서만 쓴다. import 를 여기 두어 쓰기가 아닌 판정·수집은 다른 환경에서도 싣는다."""
    import fcntl
    os.makedirs(os.path.dirname(os.path.abspath(ledger)), exist_ok=True)
    with open(ledger + ".lock", "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def append(ledger, rec):
    line = json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"   # 잠그기 전에 직렬화한다 — 실패가 잠금 안에서 나지 않게
    with _ledger_lock(ledger), open(ledger, "a", encoding="utf-8") as fh:
        fh.write(line)


def append_many(ledger, recs):
    """여러 행을 한 번에 덧붙인다 — 기존 내용 + 새 행을 임시 파일에 쓰고 원자적으로 바꾼다(중간 실패로 일부만 남지 않게).
    ⛔ 읽기부터 바꿔 끼우기까지 `_ledger_lock` 안에서 한다 — 다른 쓰기(append)가 그 사이에 끼면 그 행을 잃는다."""
    d = os.path.dirname(os.path.abspath(ledger))
    body = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in recs).encode("utf-8")   # 직렬화 실패는 원장을 건드리기 전에
    with _ledger_lock(ledger):
        old = b""
        if os.path.exists(ledger):
            with open(ledger, "rb") as fh:
                old = fh.read()
        if old and not old.endswith(b"\n"):
            old += b"\n"
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".ledger-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(old + body)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, ledger)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise


def load(ledger):
    """→ (run 행, score 행) — run_id 마다 마지막 행."""
    runs, scores = {}, {}
    evs, bad = iter_jsonl(ledger)
    if bad:
        raise ValueError(f"원장 파싱 불가 줄 {bad}")
    for r in evs:
        if r.get("type") == "run":
            runs[r["run_id"]] = r
        elif r.get("type") == "score":
            scores[r["run_id"]] = r
    return runs, scores


# ── score (순수) — ⛔ 진성 여부는 가린 검증자가 정한다. 위치 매칭은 검증자에게 주는 힌트뿐이다 ──────────────
# `path:12` · `path:L12-20` 에 더해 실제 산출물이 쓰는 `` `path` L52–65 `` · `path L4-10` · `path#L4` 도 후보다
#   (v4.40.0 리뷰: peer-review C1 인용 5곳이 후보에서 빠진 채 점수는 verified=True 였다)
CITE_RE = re.compile(r"`?([A-Za-z0-9_./-]+\.[A-Za-z]{1,6})`?(?::L?|\s+L|#L)(\d+)(?:\s*[-–~]\s*L?(\d+))?")
PATH_SCRUB_RE = re.compile(r"(?:/Users|/home|/private|/tmp|/var)/[^\s`'\")\]]+")


BLOCK_START_RE = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|#{1,6}\s|\|)")


def _blocks(text):
    """글머리·번호·제목·표 행 또는 빈 줄에서 끊은 문단들 — 한 지적의 근거 문장이 이어지는 단위."""
    out, cur = [], []
    for line in text.splitlines():
        if not line.strip() or (BLOCK_START_RE.match(line) and cur):
            if cur:
                out.append("\n".join(cur))
            cur = [line] if line.strip() else []
        else:
            cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def cite_spans(texts):
    """→ [(파일, 시작, 끝, 인용이 든 문단)] — 후보 추출. 문단 전체를 남겨 검증자가 **주장과 근거**를 함께 보게 한다."""
    seen, out = set(), []
    for t in texts:
        for blk in _blocks(t):
            for m in CITE_RE.finditer(blk):
                f = m.group(1)[2:] if m.group(1).startswith("./") else m.group(1)
                s, e = int(m.group(2)), int(m.group(3) or m.group(2))
                k = (f, min(s, e), max(s, e))
                if k not in seen:
                    seen.add(k)
                    out.append(k + (blk.strip()[:800],))
    return sorted(out)


def cand_id(sp):
    return f"{sp[0]}:{sp[1]}" + (f"-{sp[2]}" if sp[2] != sp[1] else "")


def _same_file(cited, label_file):
    return cited == label_file or label_file.endswith("/" + cited) or cited.endswith("/" + label_file)


def near_labels(sp, labels):
    return [lab["id"] for lab in labels["issues"] if _same_file(sp[0], lab["file"])
            and sp[1] - LINE_TOL <= lab["line_end"] and lab["line_start"] <= sp[2] + LINE_TOL]


def score_review(labels, texts, verdicts=None):
    """후보(인용) 마다 가린 검증자 판정 {real, label_ids, severity, axis} 로 센다. 라벨로 매핑된 발견은 **라벨의**
    severity·axis 로, 라벨 밖 진성 발견은 판정의 값으로 센다. 한 라벨은 한 번만 센다. 판정이 빠진 후보가 있으면 verified=False."""
    spans = cite_spans(texts)
    base = {"kind": "review", "candidates": len(spans), "labels_total": len(labels["issues"]),
            "empty": not any(t.strip() for t in texts)}
    if verdicts is None:
        return dict(base, verified=False, unverified=len(spans), by_severity=None, by_axis=None, labels_found=[],
                    verified_true=None, verified_ratio=None, mapping_errors=[])
    lab = {x["id"]: x for x in labels["issues"]}
    found, extras, unverified, real_n, bad = set(), [], 0, 0, []
    for sp in spans:
        v = verdicts.get(cand_id(sp))
        if not isinstance(v, dict) or not isinstance(v.get("real"), bool):
            unverified += 1      # ⛔ "false" 같은 문자열은 판정이 아니다 — 참으로 읽히지 않게 미검증으로
            continue
        if not v["real"]:
            continue
        raw_ids = v.get("label_ids") or []
        ids = [i for i in raw_ids if i in lab and _same_file(sp[0], lab[i]["file"])]
        if len(ids) != len(raw_ids):
            # ⛔ 없는 라벨·다른 파일의 라벨로 매핑 — 판정 형식 오류다. 무시하고 넘어가면 발견이 사라진다(미검증)
            bad.append(f"{cand_id(sp)}→{[i for i in raw_ids if i not in ids]}")
            unverified += 1
            continue
        if not ids and not (v.get("severity") in SEVERITIES and v.get("axis") in AXES_ALLOWED):
            # ⛔ real=true 인데 라벨도 severity·axis 도 없으면 어디에도 안 세진다 — B=C=0 으로 SC-3 이 통과한다(미검증)
            bad.append(f"{cand_id(sp)}: real 인데 라벨·severity·axis 없음")
            unverified += 1
            continue
        real_n += 1
        if ids:
            found.update(ids)
        else:
            extras.append(v)
    by_sev = {s: 0 for s in SEVERITIES}
    by_axis = {x: 0 for x in AXES_ALLOWED}
    for i in found:
        by_sev[lab[i]["severity"]] += 1
        by_axis[lab[i]["axis"]] += 1
    for v in extras:
        by_sev[v["severity"]] += 1
        by_axis[v["axis"]] += 1
    ok = unverified == 0
    return dict(base, verified=ok, unverified=unverified, by_severity=by_sev, by_axis=by_axis,
                labels_found=sorted(found), verified_true=real_n,
                verified_ratio=round(real_n / len(spans), 4) if spans and ok else None, mapping_errors=bad)


def _items(v):
    return v if isinstance(v, list) else ([v] if isinstance(v, dict) else [])


def plan_items(rubric):
    """채점표 → [(id, severity, 판정 기준, 힌트 키워드)]. 절·질문·10배 부하·의존성 장애·롤백 = major, 잔재·소비자 = critical."""
    out = [(it["id"], "major", it.get("criterion", ""), it.get("keywords") or [])
           for k in ("sections", "questions") for v in (rubric.get(k) or {}).values() for it in _items(v)]
    out += [(it["id"], "major", it.get("criterion", ""), it.get("keywords") or [])
            for k in ("load_10x", "dependency_failure", "rollback") for it in _items(rubric.get(k))]
    out += [(it["id"], "critical", f"잔재 `{it.get('symbol')}`({it.get('file')}) 의 제거·처리를 계획이 명시한다", [it.get("symbol")])
            for it in rubric.get("residues") or []]
    out += [(it["id"], "critical", f"소비자 `{it.get('symbol')}`({it.get('file')}) 에 대한 영향과 수정을 계획이 명시한다",
             [it.get("symbol")]) for it in rubric.get("consumers") or []]
    return out


def score_plan(rubric, text, verdicts=None):
    """항목마다 가린 검증자 판정 {covered} 로 센다. ⛔ 키워드 적중만으로는 세지 않는다(부정문·다른 절의 용어도 맞는다)."""
    items = plan_items(rubric)
    base = {"kind": "plan", "items_total": len(items), "empty": not text.strip(), "items": [i[0] for i in items],
            "items_by_severity": {s: sum(1 for i in items if i[1] == s) for s in SEVERITIES}}
    if verdicts is None:
        return dict(base, verified=False, unverified=len(items), by_severity=None, covered=[])
    by_sev = {s: 0 for s in SEVERITIES}
    covered, unverified = [], 0
    for iid, sev, _, _ in items:
        v = verdicts.get(iid)
        if not isinstance(v, dict) or not isinstance(v.get("covered"), bool):
            unverified += 1
        elif v["covered"]:
            covered.append(iid)
            by_sev[sev] += 1
    return dict(base, verified=unverified == 0, unverified=unverified, by_severity=by_sev, covered=covered)


BLIND_INSTRUCTIONS = (
    "너는 가린 검증자다. items 의 산출물이 어느 실험 조건에서 나왔는지 모른다(anon id 만 있다). 판정 값은 JSON boolean 이다. "
    "review 항목: candidates 마다 context(그 지적 문단)를 읽고, fixtures[fixture].source 의 diff·파일로 **직접 확인**한 뒤 "
    "{real, label_ids, severity, axis, reason} 을 낸다. real=true 는 지적이 **코드로 확인되는 실제 결함·개선점**일 때만이다 — "
    "주장만 있고 코드와 맞지 않거나, 줄·파일이 틀렸거나, 정상 판정·단순 언급이면 false. label_ids=라벨 중 그 지적이 **내용으로** "
    "가리키는 것(near_labels 는 위치 힌트일 뿐). 라벨이 요구하는 조건(예: 대안 제시)을 충족할 때만 매핑한다. 라벨 밖 진성 지적이면 "
    "label_ids=[] 에 severity·axis 를 네가 정한다. reason 에 확인한 코드 위치를 적는다. "
    "plan 항목: fixtures[fixture].requirement 와 rubric 을 보고 각 항목에 {covered, reason} — 계획 본문이 그 기준을 **명시적으로 "
    "판정·이행**하면 true(부정문·용어 나열·다른 맥락의 언급은 false). 출력 = {anon: {cid 또는 항목 id: 판정}} JSON 하나.")


def _fixture_source(fxdir, cited):
    """fixture 의 base/·head/ → 검증자가 볼 diff 와 파일 본문(인용된 파일 + 변경 파일). git 없이 difflib 로 만든다."""
    import difflib
    b, h = os.path.join(fxdir, "base"), os.path.join(fxdir, "head")
    if not os.path.isdir(b):
        return None

    def read_tree(d):
        out = {}
        for dp, _, fn in os.walk(d):
            for f in fn:
                full = os.path.join(dp, f)
                rel = os.path.relpath(full, d)
                rel = rel[:-len(".fixture")] if rel.endswith(".fixture") else rel
                try:
                    with open(full, encoding="utf-8") as fh:
                        out[rel] = fh.read()
                except (OSError, UnicodeDecodeError):
                    continue
        return out
    base = read_tree(b)
    head = dict(base, **(read_tree(h) if os.path.isdir(h) else {}))
    changed = sorted(k for k in head if base.get(k) != head.get(k))
    diff = "".join("".join(difflib.unified_diff(base.get(k, "").splitlines(True), head[k].splitlines(True),
                                                fromfile=f"a/{k}", tofile=f"b/{k}")) for k in changed)
    want = set(changed) | {k for k in head for c in cited if _same_file(c, k)}
    return {"diff": diff, "files": {k: head[k] for k in sorted(want)}}


def blind_pack(rows, fixtures_root, salt):
    """→ (검증자에게 줄 꾸러미, 열쇠). 꾸러미에는 run_id·arm·순서·경로가 없다 — 열쇠는 검증자에게 주지 않는다."""
    items, key, fixtures, cited = [], {}, {}, {}
    for r in rows:
        anon = "X" + sha_text(salt + r["run_id"])[:8]
        key[anon] = r["run_id"]
        texts = []
        for pth in (r.get("sources") or {}).get("artifacts") or []:
            try:
                with open(pth, encoding="utf-8", errors="replace") as fh:
                    texts.append(fh.read())
            except OSError:
                texts.append("")
        fxdir = os.path.join(fixtures_root, r.get("fixture") or "")
        if os.path.isfile(os.path.join(fxdir, "labels.json")):
            labels = read_json(os.path.join(fxdir, "labels.json"))
            fixtures[r["fixture"]] = {"kind": "review", "labels": [
                {k: x.get(k) for k in ("id", "axis", "severity", "file", "line_start", "line_end", "summary")}
                for x in labels["issues"]]}
            spans = cite_spans(texts)
            cited.setdefault(r["fixture"], (fxdir, set()))[1].update(sp[0] for sp in spans)
            items.append({"anon": anon, "kind": "review", "fixture": r["fixture"],
                          "artifacts_sha": [x.get("sha256") for x in r.get("artifacts") or []], "candidates": [
                {"cid": cand_id(sp), "file": sp[0], "lines": [sp[1], sp[2]], "context": PATH_SCRUB_RE.sub("<path>", sp[3]),
                 "near_labels": near_labels(sp, labels)} for sp in spans]})
        elif os.path.isfile(os.path.join(fxdir, "rubric.json")):
            rubric = read_json(os.path.join(fxdir, "rubric.json"))
            req = os.path.join(fxdir, rubric.get("requirement") or "requirement.md")
            fixtures[r["fixture"]] = {"kind": "plan", "requirement": open(req, encoding="utf-8").read() if os.path.isfile(req) else None,
                                      "rubric": [{"id": i, "severity": s, "criterion": c, "hints": h}
                                                 for i, s, c, h in plan_items(rubric)]}
            items.append({"anon": anon, "kind": "plan", "fixture": r["fixture"],
                          "artifacts_sha": [x.get("sha256") for x in r.get("artifacts") or []],
                          "text": PATH_SCRUB_RE.sub("<path>", "\n\n".join(texts))})
        else:
            raise ValueError(f"채점표 없음 — {fxdir}")
    # ⛔ fixture 의 **모든** run 이 인용한 파일을 모은 뒤 source 를 한 번 만든다(run 마다 덮어쓰면 앞 run 의 근거가 빠진다)
    for fx, (fxdir, files) in cited.items():
        fixtures[fx]["source"] = _fixture_source(fxdir, sorted(files))
    items.sort(key=lambda x: x["anon"])
    pack = {"schema": "ab-blind/1", "instructions": BLIND_INSTRUCTIONS, "fixtures": fixtures, "items": items,
            "instrument_sha": instrument_sha()}
    return pack, key


def blind_unpack(pack, key, verdicts_anon):
    """검증자 판정(anon 기준) → run_id 기준. 빠진 후보·항목은 missing 으로 돌려준다(⛔ 조용히 채우지 않는다)."""
    runs, arts, missing = {}, {}, []
    for it in pack["items"]:
        v = verdicts_anon.get(it["anon"]) or {}
        need = [c["cid"] for c in it.get("candidates", [])] if it["kind"] == "review" else \
            [x["id"] for x in pack["fixtures"][it["fixture"]]["rubric"]]
        missing += [f"{it['anon']}:{n}" for n in need if n not in v]
        runs[key[it["anon"]]] = {n: v[n] for n in need if n in v}
        arts[key[it["anon"]]] = it.get("artifacts_sha")     # ⛔ 판정은 **이 산출물 버전**에 대한 것이다
    return runs, arts, missing


# ── judge (순수) ─────────────────────────────────────────────────────────
def row_invalid(row, score, opts):
    """run 1개의 무효 사유. ⛔ 무효 run 은 0건으로 세지 않고 비교에서 뺀다(AC-5)."""
    why = []
    lead, wf, g = row.get("lead") or {}, row.get("wf") or {}, row.get("gpt") or {}
    if "AC-4" in (opts.get("require") or []) and row.get("phase") not in ("baseline", None) \
            and row.get("workflow") in ("fz-review", "fz-peer-review"):
        # ⛔ AC-4 — 병합을 기본으로 둔 변경안(R-C S25)의 리뷰는 결정론 병합을 거친다. 후보 수가 줄었거나 병합 흔적이 없으면
        #    후보 보존을 확인하지 못한다. 판정이 AC-4 를 요구할 때만 본다 — 병합이 없는 변경안 · 기준선 판정은 이 계약 밖이다
        mg = row.get("merge") or {}
        sm = mg.get("summaries") or []
        if mg.get("violations"):
            why.append(f"AC-4 후보 보존 위반(병합 거부) {mg['violations']}회")
        bad = [(x.get("in"), x.get("out")) for x in sm if x.get("in") != x.get("out")]
        if bad:
            why.append(f"AC-4 입력 후보 수 ≠ 출력 {bad}")
        if not sm and not mg.get("violations"):
            why.append("AC-4 병합 흔적 없음 — 후보 보존을 확인하지 못한다")
    if norm_model(lead.get("model")) != opts["model"]:
        why.append(f"AC-1 Lead model {lead.get('model')}≠{opts['model']}")
    if lead.get("effort") != opts["effort"]:
        why.append(f"AC-1 Lead effort {lead.get('effort')}≠{opts['effort']}")
    wm = sorted({norm_model(m) for m in wf.get("models") or {}})
    we = sorted(wf.get("efforts") or {})
    if wm != [opts["model"]]:
        why.append(f"AC-1 워커 model {wm or 'unavailable'}")
    if we != [opts["effort"]]:
        why.append(f"AC-1 워커 effort {we or 'unavailable'}")
    if (g.get("ok") or 0) > (g.get("banners") or 0) or (g.get("unlinked") or 0) > 0:
        why.append(f"AC-1 GPT 배너 {g.get('banners')}/{g.get('ok')} (미연결 {g.get('unlinked')}) — 성공 호출의 model·effort 판정 불가")
    if (g.get("failed") or 0) > 0:
        why.append(f"AC-5 GPT 호출 실패 {g.get('failed')}건 — 실패가 섞인 run 은 대표값이 아니다")
    pl = row.get("plugin") or {}
    if not pl.get("tree_hash"):
        why.append("플러그인 트리 해시 없음 — arm 의 트리를 증명하지 못한다")
    elif not pl.get("source") or not pl.get("source_tree_hash"):
        why.append("플러그인 원본 선언 없음 — 사본이 무엇의 복제인지 증명하지 못한다")
    elif pl.get("source_tree_hash") != pl.get("tree_hash"):
        why.append(f"플러그인 사본이 선언된 원본({pl.get('source')})과 다르다")
    comp = row.get("complete") or {}
    if not comp.get("ok"):
        why.append("AC-5 미완주 — " + "; ".join((comp.get("why") or ["사유 없음"])[:3]))
    if score is not None and score.get("empty"):
        why.append("AC-5 빈 산출물 — 0건으로 세지 않는다")
    st = row.get("state") or {}
    if not st.get("start_hash") or not st.get("pristine_hash") or st.get("leak") is None:
        why.append("AC-7 시작 상태 미기록")
    elif st.get("problems"):
        why.append(f"AC-7 감시 불완전: {st['problems'][:2]}")
    elif st["leak"]:
        why.append(f"AC-7 시작 상태가 기준과 다르다: {st['leak']}")
    if not (row.get("input") or {}).get("hash") or not (row.get("input") or {}).get("tree_hash"):
        why.append("input-hash 없음(또는 입력 트리 해시 없음)")
    if (wf.get("advisor") or 0) > 0:
        why.append(f"워커 advisor {wf['advisor']}회 (0 이어야 한다)")
    wall = row.get("wall") or {}
    for w in wall.get("workflows") or []:
        if w.get("delta_pct") is None:
            why.append(f"wall_workflow 교차 불가 {w.get('run_id')} (에이전트 {w.get('wf_s')}s · Lead {w.get('lead_s')}s)")
        elif w["delta_pct"] > WALL_XCHECK_PCT:
            why.append(f"wall_workflow 두 자 차이 {w['delta_pct']}% > {WALL_XCHECK_PCT}% "
                       f"({w.get('run_id')}: 에이전트 {w.get('wf_s')}s · Lead {w.get('lead_s')}s)")
    md = wall.get("mtime_delta_s")
    if md is None or abs(md) > MTIME_TOL_S:
        why.append(f"최종 산출물 mtime 교차 실패 Δ={md}s (허용 {MTIME_TOL_S}s)")
    if opts.get("plugin_sha"):
        p = row.get("plugin") or {}
        if not str(p.get("sha") or "").startswith(opts["plugin_sha"]):
            why.append(f"plugin SHA {str(p.get('sha'))[:12]}≠{opts['plugin_sha']}")
        if p.get("dirty") is not False:
            why.append(f"plugin 트리 미커밋 변경(dirty={p.get('dirty')} · 기록 시점 {p.get('at')})")
    return why


def _key_fields(row, score):
    lead, inj, g = row.get("lead") or {}, row.get("injected") or {}, row.get("gpt") or {}
    k = {"input-hash": (row.get("input") or {}).get("hash"), "instrument": row.get("instrument_sha"),
         "injected": (inj.get("User"), inj.get("Project"), inj.get("AutoMem")),
         "cli": tuple(lead.get("cli_versions") or ()),
         # arm 마다 트리가 하나여야 한다 — 키 이름에 arm 을 넣어 B·C 풀을 나눈다
         f"plugin-tree:{row.get('arm')}": (row.get("plugin") or {}).get("tree_hash")}
    # ⛔ GPT 배너는 **배너가 있는 run 끼리만** 비교한다 — 호출 유무 자체는 변경안이 바꿀 수 있는 대상이다
    if g.get("models") or g.get("efforts"):
        k["gpt"] = (tuple(g.get("models") or ()), tuple(g.get("versions") or ()))
    # ⛔ Lead 가 `--effort` 를 명시한 호출은 측정 대상의 행동이다 — 기본값으로 간 호출의 effort 만 환경으로 비교한다(F-333)
    dflt = g.get("efforts_default", g.get("efforts"))
    if dflt:
        k["gpt-effort"] = tuple(dflt)
    if score is not None:
        k["labels"] = score.get("fixture_sha")
    return k


def _ordered_json(v):
    return json.dumps(v, sort_keys=True)


def group_invalid(rows, scores, roots_first=None):
    """비교 묶음 안에서 입력·계측기·주입 지침·CLI·GPT 배너·채점표·arm 별 플러그인 트리가 같아야 한다(다수와 다르면 무효).
    C 트리가 B 트리와 같으면 C 무효(같은 트리끼리 비교) · 입력 저장소 경로가 겹치면 뒤 run 무효(재사용)."""
    out = {r["run_id"]: [] for r in rows}
    keys = {r["run_id"]: _key_fields(r, scores.get(r["run_id"])) for r in rows}
    for f in sorted({f for k in keys.values() for f in k}):
        pool = [r for r in rows if f in keys[r["run_id"]]]
        vals = collections.Counter(_ordered_json(keys[r["run_id"]][f]) for r in pool)
        if len(vals) <= 1:
            continue
        first = {}
        for r in sorted(pool, key=lambda r: r.get("order") or 0):
            first.setdefault(_ordered_json(keys[r["run_id"]][f]), r.get("order") or 0)
        ref = sorted(vals.items(), key=lambda kv: (-kv[1], first[kv[0]]))[0][0]
        for r in pool:
            if _ordered_json(keys[r["run_id"]][f]) != ref:
                tag = "input-hash" if f == "input-hash" else f"{f} 불일치"
                out[r["run_id"]].append(f"{tag} — 묶음 다수와 다르다" + (" (recollect 필요)" if f == "instrument" else ""))
    btrees = collections.Counter((r.get("plugin") or {}).get("tree_hash") for r in rows if r.get("arm") == "B")
    bref = btrees.most_common(1)[0][0] if btrees else None
    for r in rows:
        if r.get("arm") != "B" and bref and (r.get("plugin") or {}).get("tree_hash") == bref:
            out[r["run_id"]].append("C 가 B 와 같은 플러그인 트리다 — 같은 트리끼리 비교가 된다")
    for r in rows:   # ⛔ 재사용은 원장 **전체**에서 본다(다른 워크플로가 같은 저장소를 써도 오염이다)
        root = (r.get("input") or {}).get("root")
        first = (roots_first or {}).get(root)
        if root and first and first != r["run_id"]:
            out[r["run_id"]].append(f"fixture 저장소 재사용 — {first} 과 같은 경로")
    return out


def _mean(xs):
    return sum(xs) / len(xs)


def _sev(score, sev):
    return (score.get("by_severity") or {}).get(sev, 0)


def _exact(B, C, nb=2, nc=2):
    """정식 비교는 arm 별 유효 run 이 **정확히** 정해진 수여야 한다 — 부족은 무효 run 재실행, 초과는 골라 쓰지 않는다."""
    if len(B) != nb or len(C) != nc:
        return f"유효 run B={len(B)}(정확히 {nb}) C={len(C)}(정확히 {nc}) — 부족이면 무효 run 을 다시 재고, 초과면 비교 run 을 고정하라"
    return None


def crit_sc3(B, C, scores, c_runs=2):
    """critical·major 각각 max(0, mean(B) − mean(C)) ≤ N, N = |B1 − B2|."""
    bad = _exact(B, C, 2, c_runs)
    if bad:
        return False, [bad + " · 미완주는 0건이 아니라 무효"]
    lines, ok = [], True
    for sev in GATED:
        b = [_sev(scores[r["run_id"]], sev) for r in B]
        c = [_sev(scores[r["run_id"]], sev) for r in C]
        n = abs(b[0] - b[1])
        loss = max(0.0, _mean(b) - _mean(c))
        good = loss <= n
        ok &= good
        lines.append(f"{sev} B={b} C={c} N={n} loss={loss:g} {'≤' if good else '>'} N")
    return ok, lines


def crit_sc4(B, C, scores):
    """C run 마다 6축 각 1건 이상 + 검증 비율이 mean(B) − |B1 − B2| 이상."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    ok, lines = True, []
    for r in C:
        ax = scores[r["run_id"]].get("by_axis") or {}
        miss = [a for a in AXES6 if (ax.get(a) or 0) < 1]
        if miss:
            ok = False
            lines.append(f"{r['run_id']} 축 누락 {miss}")
    br = [scores[r["run_id"]].get("verified_ratio") for r in B]
    cr = [scores[r["run_id"]].get("verified_ratio") for r in C]
    if None in br or None in cr:
        return False, lines + [f"검증 비율 미판정 B={br} C={cr} — 후보 0 이거나 가린 검증자 판정이 빠졌다"]
    floor = _mean(br) - abs(br[0] - br[1])
    good = _mean(cr) >= floor
    ok &= good
    lines.append(f"검증 비율 B={br} C={cr} 하한={floor:.4f} {'통과' if good else '미달'}")
    return ok, lines


def crit_sc6(B, C):
    """median(B) − median(C) > max(|B1 − B2|, |C1 − C2|) — wall_total 기준."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    b = [r["wall"]["total_s"] for r in B]
    c = [r["wall"]["total_s"] for r in C]
    if None in b or None in c:
        return False, [f"wall_total 없음 B={b} C={c}"]
    gain, noise = statistics.median(b) - statistics.median(c), max(abs(b[0] - b[1]), abs(c[0] - c[1]))
    return gain > noise, [f"wall B={b} C={c} 감소={gain:g}s {'>' if gain > noise else '≤'} 잡음={noise:g}s"]


SC7_FIELDS = (("lead", "out_tok"), ("lead", "messages"), ("lead", "retries"), ("lead", "followup_prompts"),
              ("wf", "out_tok"), ("wf", "turns"), ("wf", "so_retries"))


def crit_sc7(B, C):
    """Lead·워커 출력·메시지·재시도·후속 요청 필드 필수 + 필수 검증(B 공통 stage · 성공한 GPT 호출 수) 보존.
    성공한 GPT 호출 = 직접 호출(`gpt.ok`) + 런처 호출(`gpt.launcher_ok` — 감사 exit 0). ⛔ 런처를 빼면 GPT 리뷰를
    런처로 옮긴 후보가 검증을 잃은 것처럼 보인다(실측 review C 4 run: 직접 0 · 런처 1)."""
    ok, lines = True, []
    for r in B + C:
        miss = [f"{a}.{b}" for a, b in SC7_FIELDS if (r.get(a) or {}).get(b) is None]
        if miss:
            ok = False
            lines.append(f"{r['run_id']} 필드 없음 {miss}")
    bad = _exact(B, C)
    if bad:
        return False, lines + [bad]
    need = set.intersection(*[set(r["wf"].get("stages") or ()) for r in B])
    direct = lambda r: r["gpt"].get("ok") or 0
    launch = lambda r: r["gpt"].get("launcher_ok") or 0
    said = lambda r: f"{direct(r) + launch(r)}(직접 {direct(r)} + 런처 {launch(r)})"
    gmin = min(direct(r) + launch(r) for r in B)
    for r in C:
        lost = sorted(need - set(r["wf"].get("stages") or ()))
        if lost:
            ok = False
            lines.append(f"{r['run_id']} 필수 stage 누락 {lost}")
        if direct(r) + launch(r) < gmin:
            ok = False
            lines.append(f"{r['run_id']} 성공한 GPT 호출 {said(r)} < 기준 {gmin}")
    if ok:
        lines.append(f"필드 존재 · 필수 stage {sorted(need)} 보존 · 성공한 GPT 호출 ≥ {gmin} — "
                     + " | ".join(f"{r['run_id']} {said(r)}" for r in C))
    return ok, lines


def crit_crossover(B, C):
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    seq = sorted(B + C, key=lambda r: r["order"])
    orders, arms = [r["order"] for r in seq], [r["arm"] for r in seq]
    good = len(set(orders)) == len(orders) and all(x != y for x, y in zip(arms, arms[1:]))
    return good, [f"순서 {list(zip(orders, arms))} {'교차' if good else '⛔ 교차 아님'}"]


def crit_sc5(B, C, scores):
    """계획 완결성(SC-5) — 유효한 C run 마다 채점표 항목을 **전부** 덮는다: 절 6 · Q1~Q8 · 10배 부하 · 의존성 장애 · 롤백,
    제거 fixture 는 잔재 · 소비자까지(누락 0). 두 채점표 모두 절 · 질문마다 항목이 1개라 '각각' = '전부'다.
    기준선 대비가 아니라 절대 조건이다 — B 는 비교 묶음 확인(_exact)에만 쓴다."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    good, lines = True, []
    for r in C:
        s = scores.get(r["run_id"]) or {}
        if s.get("kind") != "plan" or not isinstance(s.get("items"), list):
            return False, [f"⛔ {r['run_id']}: 항목 목록이 있는 계획 점수가 아니다 — score 를 다시"]
        miss = sorted(set(s["items"]) - set(s.get("covered") or []))
        good &= not miss
        lines.append(f"{r['run_id']} {len(s['items']) - len(miss)}/{len(s['items'])}" + (f" ⛔누락 {miss}" if miss else ""))
    return good, lines


def crit_gpt_wf_wall(B, C):
    """S26 — 유효한 C run 마다 GPT 독립 플랜 wall 과 Workflow wall 이 둘 다 재졌는가(값을 줄에 남긴다).
    ⛔ 기준선(B)은 독립 플랜이 없는 트리라 비교 묶음 확인(_exact)에만 쓴다."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    good, lines = True, []
    for r in C:
        cp = r.get("critical") or {}
        ok = cp.get("gpt_plan_s") is not None and cp.get("wf_s") is not None
        good &= ok
        lines.append(f"{r['run_id']} GPT {cp.get('gpt_plan_s')}s · Workflow {cp.get('wf_s')}s" + ("" if ok else " ⛔ 측정 없음"))
    return good, lines


def crit_critical_path(B, C):
    """S26 — C run 마다 임계 경로(workflow · gpt)를 기록했는가. GPT 가 더 길면 '임계 경로 전환' 으로 적는다(통과 · 실패와 무관한 기록)."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    good, lines = True, []
    for r in C:
        pth = (r.get("critical") or {}).get("path")
        good &= pth in ("gpt", "workflow")
        lines.append(f"{r['run_id']} 임계 경로 {pth or '⛔ 미상'}" + (" ← 전환(GPT 독립 플랜이 Workflow 보다 길다)" if pth == "gpt" else ""))
    return good, lines


def crit_blind_labels(B, C, scores):
    """가린 검증 — 비교에 쓴 run 의 점수가 전부 blind-unpack 판정에서 왔고(blind_pack_sha), B · C 가 **한 꾸러미**에서
    판정됐다. arm 별로 따로 싼 꾸러미는 묶음 자체가 arm 을 드러낸다(experiment-log §5.10 §7 — 검증자는 어느 arm 의
    산출물인지 알 수 없어야 한다). 판정 전 · 미완 · 낡은 점수는 judge_rows 가 먼저 UNRUN 으로 거른다."""
    bad = _exact(B, C)
    if bad:
        return False, [bad]
    packs = {r["run_id"]: (scores.get(r["run_id"]) or {}).get("blind_pack_sha") for r in B + C}
    none = sorted(rid for rid, p in packs.items() if not p)
    if none:
        return False, [f"⛔ 가린 판정이 아닌 점수 {none}"]
    uniq = sorted(set(packs.values()))
    good = len(uniq) == 1
    return good, [f"꾸러미 {len(uniq)}개" + ("" if good else f" — ⛔ B · C 가 다른 꾸러미에서 판정됐다 {uniq}")]


def select(runs, workflow, fixture, arm, phase, release=None):
    rows = [r for r in runs.values() if r.get("workflow") == workflow and r.get("fixture") == fixture
            and r.get("arm") == arm and r.get("phase") == phase and (release is None or r.get("release") == release)]
    return sorted(rows, key=lambda r: (r.get("order") or 0, r["run_id"]))


def judge_rows(runs, scores, opts, source_check=None):
    """→ (exit, 출력 줄). source_check(row) → 원천 대조 무효 사유(없으면 생략)."""
    out = []
    req = opts["require"]
    unknown = [x for x in req if x not in IMPLEMENTED and x != "baseline-runs"]
    if unknown:
        return UNRUN, [f"UNRUN: 미구현 기준 {unknown} — 구현 스텝(S25~S27)에서 추가한다. ⛔ 받고 무시하지 않는다"]
    if opts["phase"] == "baseline" and set(req) - {"baseline-runs"}:
        return UNRUN, [f"UNRUN: baseline phase 는 baseline-runs 만 판정한다 — 받은 기준 {req}. ⛔ 받고 무시하지 않는다"]
    for flag in ("envs", "options_on", "require_passed"):
        if opts.get(flag):
            return UNRUN, [f"UNRUN: --{flag.replace('_', '-')} 미구현 — ⛔ 받고 무시하지 않는다"]
    if not runs:
        return UNRUN, ["UNRUN: 원장에 run 행이 없다 — 측정 실패를 먼저 의심한다"]
    # ⛔ 기준선 행이 있는 워크플로만 보면 C 행만 있는 워크플로가 조용히 빠진다 — 전체 행에서 도출한다(v4.40.0 리뷰)
    wfs = opts["workflows"] or sorted({r["workflow"] for r in runs.values()})
    if not wfs:
        return UNRUN, ["UNRUN: 판정할 워크플로가 없다(baseline 행 0)"]
    worst = PASS
    removal_seen = False      # SC-5 — 제거 · 리팩터링 fixture(critical 항목이 있는 채점표)를 판정했는가
    roots_first = {}
    for r in sorted(runs.values(), key=lambda r: (r.get("order") or 0, r["run_id"])):
        root = (r.get("input") or {}).get("root")
        if root:
            roots_first.setdefault(root, r["run_id"])
    cphase = "release-smoke" if opts["phase"] == "release-smoke" else "change"
    # ⛔ 비교 묶음 = (워크플로, fixture). 워크플로만으로 묶으면 fixture 가 둘인 워크플로(fz-plan: feature·removal)의
    #    소수 쪽이 '입력 해시 불일치' 로 무효가 된다.
    groups = []
    for wf in wfs:
        fxs = sorted({r.get("fixture") for r in runs.values() if r.get("workflow") == wf and (
            r.get("phase") == "baseline" or (opts["phase"] != "baseline" and r.get("phase") == cphase))}, key=str)
        if not fxs:
            out.append(f"FAIL {wf}: 이 워크플로의 run 이 원장에 없다")
            worst = FAIL
        groups += [(wf, fx) for fx in fxs]
    for wf, fx in groups:
        label = f"{wf}[{fx}]"
        B = select(runs, wf, fx, "B", "baseline")
        C = [] if opts["phase"] == "baseline" else select(runs, wf, fx, opts["arm"], cphase, opts.get("release"))
        inv = {r["run_id"]: row_invalid(r, scores.get(r["run_id"]), dict(opts, plugin_sha=opts.get("plugin_sha") if r in B else None))
               for r in B + C}
        for rid, why in group_invalid(B + C, scores, roots_first).items():
            inv[rid] += why
        if source_check:
            for r in B + C:
                inv[r["run_id"]] += source_check(r)
        for r in B + C:
            if inv[r["run_id"]]:
                out.append(f"  INVALID {r['run_id']} — " + " · ".join(inv[r["run_id"]]))
        vB = [r for r in B if not inv[r["run_id"]]]
        vC = [r for r in C if not inv[r["run_id"]]]
        if opts["phase"] == "baseline":
            good = len(vB) >= opts["min_runs"]
            out.append(f"{'PASS' if good else 'FAIL'} baseline-runs {label}: 유효 {len(vB)}/{len(B)} (필요 {opts['min_runs']})"
                       + (" — " + ", ".join(r["run_id"] for r in vB) if vB else ""))
            worst = max(worst, PASS if good else FAIL)
            continue
        if {"SC-3", "SC-3-smoke", "SC-4", "SC-5", "blind-labels"} & set(req):
            cur_i = opts.get("instrument") or instrument_sha()
            unv = [r["run_id"] for r in vB + vC if not (scores.get(r["run_id"]) or {}).get("verified")
                   or (scores.get(r["run_id"]) or {}).get("artifacts_sha") != _artifact_shas(r)
                   or (scores.get(r["run_id"]) or {}).get("instrument_sha") != cur_i]
            if unv:
                out.append(f"UNRUN {label}: 가린 검증자 판정 없음·미완·낡음 {unv} — blind-pack → 검증자 → blind-unpack → score --verdicts")
                worst = UNRUN
                continue
        for c in req:
            if c == "SC-3":
                good, lines = crit_sc3(vB, vC, scores)
            elif c == "SC-3-smoke":
                good, lines = crit_sc3(vB, vC, scores, c_runs=opts["runs"])
            elif c == "SC-4":
                good, lines = crit_sc4(vB, vC, scores)
            elif c == "SC-6":
                good, lines = crit_sc6(vB, vC)
            elif c == "SC-7":
                good, lines = crit_sc7(vB, vC)
            elif c == "crossover-order":
                good, lines = crit_crossover(vB, vC)
            elif c == "gpt-wf-wall":
                good, lines = crit_gpt_wf_wall(vB, vC)
            elif c == "critical-path":
                good, lines = crit_critical_path(vB, vC)
            elif c == "blind-labels":
                good, lines = crit_blind_labels(vB, vC, scores)
            elif c == "SC-5":
                good, lines = crit_sc5(vB, vC, scores)
                removal_seen |= any(((scores.get(r["run_id"]) or {}).get("items_by_severity") or {}).get("critical", 0) > 0
                                    for r in vC)
            elif c in ("AC-1", "AC-4", "AC-5", "AC-7", "input-hash"):
                hit = [rid for rid, why in inv.items() if any(w.startswith(c) for w in why)]
                bad = _exact(vB, vC, 2, opts["runs"] if opts["phase"] == "release-smoke" else 2)
                good = bad is None
                lines = [f"비교에 쓴 run 의 {c} 무효 0 · 제외 {hit or '없음'}" + ("" if good else f" — ⛔ {bad}")]
            else:
                good, lines = False, [f"판정기 없음 {c}"]
            out.append(f"{'PASS' if good else 'FAIL'} {c} {label}: " + " | ".join(lines))
            worst = max(worst, PASS if good else FAIL)
    if "SC-5" in req and not removal_seen and opts["phase"] != "baseline":
        # ⛔ feature fixture 만으로 SC-5 를 통과시키지 않는다 — 기준의 '제거 · 리팩터링 fixture 잔재 · 소비자 누락 0' 이 조용히 빠진다
        out.append("UNRUN SC-5: 제거 · 리팩터링 fixture(잔재 · 소비자 항목이 있는 채점표)를 판정한 C run 이 없다")
        worst = max(worst, UNRUN)
    return worst, out


# ── 원천 대조 (I/O) — ⛔ 기록된 collect 인자로 행을 **다시 만들어** 판정 필드 전체를 대조한다 ───────────────
VERIFY_FIELDS = {
    "transcript": ("lead.model", "lead.effort", "lead.out_tok", "lead.messages", "lead.cli_versions", "lead.retries",
                   "lead.followup_prompts", "plugin.roots", "plugin.sha", "plugin.tree_hash", "injected",
                   "wall.total_s", "wall.start", "wall.end", "wall.mtime_delta_s", "artifacts", "gpt.calls", "gpt.ok",
                   "gpt.failed", "gpt.unlinked", "gpt.banners", "gpt.models", "gpt.efforts", "gpt.efforts_default", "gpt.versions",
                   "plugin.dirty", "plugin.source", "plugin.source_tree_hash", "input.prompt_sha"),
    "wf-metrics": ("wf.agents", "wf.out_tok", "wf.turns", "wf.so_retries", "wf.advisor", "wf.models", "wf.efforts",
                   "wf.stages", "wf.stage2_ran", "wall.workflows", "complete.ok"),
    "start-state": ("state.start_hash", "state.pristine_hash", "state.leak", "state.problems"),
    "input-hash": ("input.hash", "input.commits", "input.root", "input.tree_hash"),
}


def _dig(o, dotted):
    for k in dotted.split("."):
        o = o.get(k) if isinstance(o, dict) else None
    return o


def verify_sources(row, kinds):
    args = row.get("collect_args")
    if not args:
        return ["원천 대조 불가 — collect_args 없음"]
    try:
        fresh = build_row(argparse.Namespace(**args), dry=True)
    except Exception as e:  # noqa: BLE001 — 재구성 실패는 무효 사유로 기록한다(통과 아님)
        return [f"원천 재구성 실패 {type(e).__name__}: {e}"]
    why = []
    for k in kinds:
        for f in VERIFY_FIELDS.get(k, ()):
            a, b = _dig(row, f), _dig(fresh, f)
            if a != b:
                why.append(f"원천 불일치 {f}: 행 {str(a)[:60]} · 원천 {str(b)[:60]}")
    if "instrument-sha" in kinds and row.get("instrument_sha") != instrument_sha():
        why.append(f"계측기 변경 — 행 {row.get('instrument_sha')} · 현재 {instrument_sha()} (recollect 필요)")
    return why


# ── CLI ────────────────────────────────────────────────────────────────
def cmd_snapshot(a):
    if not a.watch:
        print("UNRUN: --watch 가 없다 — 감시 대상 없는 스냅샷은 AC-7 을 판정하지 못한다")
        return UNRUN
    watch = {}
    for w in a.watch:
        if "=" not in w:
            print(f"UNRUN: --watch 는 이름=경로 형식 — {w}")
            return UNRUN
        k, v = w.split("=", 1)
        watch[k] = v
    snap = snapshot(watch)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"snapshot {a.out}: " + " · ".join(f"{k}={len(v['files'])}" for k, v in snap["watch"].items())
          + f" · hash {snap['hash'][:12]}")
    return PASS


def cmd_input(a):
    """run **전**에 입력 신원을 남긴다 — 커밋 · 깨끗한 작업 트리 · 트리 내용 해시 · 저장소 경로."""
    commits = input_commits(a.root)
    if not commits:
        print(f"UNRUN: 커밋을 읽지 못했다 — {a.root}")
        return UNRUN
    st = fb.git(pathlib.Path(a.root), "status", "--porcelain", "--untracked-files=all")
    rec = {"fixture": a.fixture, "commits": commits, "root": os.path.realpath(a.root),
           "clean": st is not None and not st.strip(), "tree_hash": tree_digest(a.root)}
    if not rec["tree_hash"]:
        print(f"UNRUN: 입력 트리 해시를 잴 수 없다(git 목록·읽기 실패) — {a.root}")
        return UNRUN
    if a.plugin_root:
        # ⛔ run 이 플러그인 사본에 experiment-log 를 쓴다 — 신원은 run **전**에 잰다(collect 시점엔 dirty)
        rec["plugin"] = dict(plugin_info(os.path.realpath(a.plugin_root)), at="start")
        if a.plugin_source:
            # 사본이 선언된 원본의 충실한 복제인가(B = 기준 트리 · C = 작업 트리)
            rec["plugin"]["source"] = os.path.realpath(a.plugin_source)
            rec["plugin"]["source_tree_hash"] = tree_digest(a.plugin_source)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(f"input {a.fixture}: " + " · ".join(f"{k}={v[:10]}" for k, v in commits.items())
          + f" · clean={rec['clean']} · tree {str(rec['tree_hash'])[:12]}")
    return PASS if rec["clean"] else FAIL


def cmd_collect(a):
    if a.phase not in PHASES:
        print(f"UNRUN: --phase 는 {PHASES} 중 하나")
        return UNRUN
    if not os.path.isfile(a.transcript):
        print(f"UNRUN: transcript 없음 — {a.transcript}")
        return UNRUN
    row = build_row(a)
    append(a.ledger, row)
    c = row["complete"]
    print(f"collect {row['run_id']}: complete={c['ok']} wall_total={row['wall']['total_s']}s "
          f"lead_out={row['lead']['out_tok']} wf_agents={row['wf']['agents']} input={str(row['input']['hash'])[:12]}")
    for w in c["why"]:
        print(f"  ⚠️ {w}")
    return PASS


def cmd_recollect(a):
    try:
        runs, _ = load(a.ledger)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 원장을 읽지 못했다 — {e}")
        return UNRUN
    if a.run_id and a.run_id not in runs:
        print(f"UNRUN: 원장에 run {a.run_id} 이 없다")
        return UNRUN
    targets = [runs[a.run_id]] if a.run_id else list(runs.values())
    if not targets:
        print("UNRUN: 다시 수집할 run 이 없다")
        return UNRUN
    # ⛔ 전부 다시 만든 뒤 한 번에 덧붙인다 — 중간 실패로 계측기 버전이 섞인 원장이 남지 않게(v4.40.0 리뷰)
    news = []
    for row in targets:
        try:
            new = build_row(argparse.Namespace(**row["collect_args"]))
        except Exception as e:   # noqa: BLE001 — 원천 부재·옛 인자 모양 모두 판정 불가다
            print(f"UNRUN: {row.get('run_id')} 재구성 실패 {type(e).__name__}: {e} — 원장에 아무것도 덧붙이지 않았다")
            return UNRUN
        new["recollected_from"] = row.get("instrument_sha")
        news.append((row, new))
    try:
        append_many(a.ledger, [new for _, new in news])
    except (OSError, TypeError, ValueError) as e:
        print(f"UNRUN: 원장에 쓰지 못했다 — {type(e).__name__}: {e} (원장은 그대로다)")
        return UNRUN
    for row, new in news:
        print(f"recollect {new['run_id']}: complete={new['complete']['ok']} instrument {row.get('instrument_sha')}→{new['instrument_sha']}")
    return PASS


def _artifact_shas(row):
    return [x.get("sha256") for x in row.get("artifacts") or []]


def _read_texts(row):
    texts = []
    for pth in (row.get("sources") or {}).get("artifacts") or []:
        try:
            with open(pth, encoding="utf-8", errors="replace") as fh:
                texts.append(fh.read())
        except OSError:
            texts.append("")
    return texts


def cmd_score(a):
    """채점 — 가린 검증자 판정(`blind-unpack` 출력)이 있으면 그것으로 센다. 없으면 **미검증** 점수만 남는다
    (SC-3·SC-4 는 미검증 점수를 판정하지 않는다)."""
    runs, _ = load(a.ledger)
    targets = [runs[a.run_id]] if a.run_id else list(runs.values())
    vdoc = read_json(a.verdicts) if a.verdicts else {}
    if vdoc and not vdoc.get("blinded"):
        print("UNRUN: --verdicts 는 blind-unpack 출력이어야 한다(blinded=true) — arm 을 아는 판정은 받지 않는다")
        return UNRUN
    verdicts, varts = vdoc.get("runs") or {}, vdoc.get("artifacts") or {}
    rc = PASS
    for row in targets:
        fx = os.path.join(a.fixtures_root, row["fixture"] or "")
        texts = _read_texts(row)
        cur = _artifact_shas(row)
        v = verdicts.get(row["run_id"]) if vdoc else None
        if v is not None and varts.get(row["run_id"]) != cur:
            # ⛔ 판정은 꾸러미를 만들 때의 산출물 버전에 대한 것이다 — 산출물이 바뀌었으면 옛 판정을 쓰지 않는다
            print(f"  ⚠️ {row['run_id']}: 판정의 산출물 해시 ≠ 현재 산출물 — 미검증으로 채점한다(blind-pack 을 다시)")
            v = None
        if os.path.isfile(os.path.join(fx, "labels.json")):
            lp = os.path.join(fx, "labels.json")
            s = score_review(read_json(lp), texts, v)
        elif os.path.isfile(os.path.join(fx, "rubric.json")):
            lp = os.path.join(fx, "rubric.json")
            s = score_plan(read_json(lp), "\n".join(texts), v)
        else:
            print(f"UNRUN {row['run_id']}: 채점표 없음 — {fx}")
            rc = UNRUN
            continue
        s.update({"type": "score", "run_id": row["run_id"], "fixture_sha": fb.hash_file(pathlib.Path(lp)),
                  "blind_pack_sha": vdoc.get("pack_sha") if v is not None else None, "artifacts_sha": cur,
                  "instrument_sha": instrument_sha()})
        append(a.ledger, s)
        sev = s["by_severity"] or {}
        print(f"score {row['run_id']}: verified={s['verified']} " + " ".join(f"{k}={v}" for k, v in sev.items())
              + (f" ratio={s.get('verified_ratio')}" if s["kind"] == "review" else f" covered={len(s['covered'])}/{s['items_total']}")
              + (f" · 미판정 {s['unverified']}" if s.get("unverified") else ""))
    return rc


def cmd_blind_pack(a):
    runs, _ = load(a.ledger)
    ids = a.run_id or [r["run_id"] for r in runs.values() if (r.get("complete") or {}).get("ok")]
    rows = [runs[i] for i in ids if i in runs]
    if not rows:
        print("UNRUN: 꾸러미에 넣을 run 이 없다(완주 run 0)")
        return UNRUN
    salt = a.salt or os.urandom(8).hex()
    try:
        pack, key = blind_pack(rows, a.fixtures_root, salt)
    except (OSError, ValueError) as e:
        print(f"UNRUN: {e}")
        return UNRUN
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "pack.json"), "w", encoding="utf-8") as fh:
        json.dump(pack, fh, ensure_ascii=False, indent=1, sort_keys=True)
    with open(os.path.join(a.out, "key.json"), "w", encoding="utf-8") as fh:
        json.dump({"key": key, "pack_sha": fb.hash_file(pathlib.Path(a.out, "pack.json"))}, fh, ensure_ascii=False, indent=1)
    n = sum(len(it.get("candidates", [])) for it in pack["items"])
    print(f"blind-pack {a.out}: 항목 {len(pack['items'])} · 리뷰 후보 {n} — ⛔ 검증자에게는 pack.json 만 준다(key.json 금지)")
    return PASS


def cmd_blind_unpack(a):
    try:
        pack = read_json(os.path.join(a.pack, "pack.json"))
        kd = read_json(os.path.join(a.pack, "key.json"))
        va = read_json(a.verdicts)
    except (OSError, ValueError) as e:
        print(f"UNRUN: {e}")
        return UNRUN
    sha = fb.hash_file(pathlib.Path(a.pack, "pack.json"))
    if sha != kd.get("pack_sha"):
        print("UNRUN: pack.json 이 꾸러미 생성 뒤 바뀌었다 — 판정 대상이 다르다")
        return UNRUN
    runs, arts, missing = blind_unpack(pack, kd["key"], va)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"schema": "ab-verdicts/1", "blinded": True, "pack_sha": sha, "runs": runs, "artifacts": arts,
                   "missing": missing},
                  fh, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"blind-unpack → {a.out}: run {len(runs)} · 빠진 판정 {len(missing)}" + (f" {missing[:4]}" if missing else ""))
    return PASS if not missing else FAIL


def cmd_judge(a):
    if a.min_runs < 1 or a.runs < 1:
        print(f"UNRUN: --min-runs·--runs 는 1 이상이어야 한다(받은 값 {a.min_runs}·{a.runs}) — 0 이면 유효 run 0건으로 통과한다")
        return UNRUN
    try:
        runs, scores = load(a.ledger)
    except (OSError, ValueError) as e:
        print(f"UNRUN: 원장을 읽지 못했다 — {e}")
        return UNRUN
    kinds = [k for k in (a.verify_sources or "").split(",") if k]
    bad = [k for k in kinds if k not in SOURCE_KINDS]
    if bad:
        print(f"UNRUN: 모르는 --verify-sources {bad} (허용 {SOURCE_KINDS})")
        return UNRUN
    wfs = [w for w in ((a.workflows or "") + "," + (a.workflow or "")).split(",") if w]
    req = [x for x in (a.require or "").split(",") if x]
    if a.phase == "baseline":
        req = req or ["baseline-runs"]
    elif not req:
        print("UNRUN: --require 없음 — 무엇을 판정할지 정하지 않았다")
        return UNRUN
    opts = {"model": a.model, "effort": a.effort, "phase": a.phase, "arm": a.arm, "release": a.release,
            "workflows": wfs, "min_runs": a.min_runs, "runs": a.runs, "plugin_sha": a.plugin_sha,
            "require": req, "envs": a.envs, "options_on": a.options_on, "require_passed": a.require_passed}
    rc, lines = judge_rows(runs, scores, opts, (lambda r: verify_sources(r, kinds)) if kinds else None)
    for x in lines:
        print(x)
    print(f"judge: {('PASS', 'FAIL', 'UNRUN')[rc]} (phase={a.phase or 'change'} · require={','.join(req)}"
          + (f" · verify-sources={','.join(kinds)}" if kinds else "") + ")")
    return rc


def cmd_show(a):
    runs, scores = load(a.ledger)
    for r in sorted(runs.values(), key=lambda r: (r["workflow"], r.get("order") or 0)):
        s = scores.get(r["run_id"]) or {}
        sev = s.get("by_severity") or {}
        d = [w["delta_pct"] for w in r["wall"]["workflows"] if w.get("delta_pct") is not None]
        g = r.get("gpt") or {}
        print(f"{r['run_id']:34} order={r.get('order')} complete={r['complete']['ok']} "
              f"wall={r['wall']['total_s']} Δmt={r['wall'].get('mtime_delta_s')} lead_out={r['lead']['out_tok']} msgs={r['lead']['messages']} "
              f"wf_out={r['wf']['out_tok']} turns={r['wf']['turns']} crit={sev.get('critical')} major={sev.get('major')} "
              f"gpt={g.get('calls')}({'/'.join(g.get('models') or [])}:{'/'.join(g.get('efforts') or [])}) "
              f"Δwf={max(d) if d else None}%")
    return PASS


def cmd_verify_evidence(a):
    print("UNRUN: verify-evidence 미구현 — S27(독립성·이식성 판정)에서 구현한다. ⛔ 통과로 읽지 않는다")
    return UNRUN


# ── self-test ──────────────────────────────────────────────────────────
INSTR_NOW = instrument_sha()


def _mk(run_id, arm, order, crit=1, major=2, wall=1000.0, **kw):
    """판정기용 최소 유효 run + score."""
    row = {"type": "run", "run_id": run_id, "workflow": kw.get("workflow", "fz-review"), "arm": arm,
           "run": kw.get("run", 1), "order": order, "phase": kw.get("phase", "baseline" if arm == "B" else "change"),
           "release": kw.get("release"), "fixture": kw.get("fixture", "fx"),
           "lead": {"model": kw.get("model", DEFAULT_MODEL), "effort": kw.get("effort", DEFAULT_EFFORT),
                    "cli_versions": ["2.1.282"], "out_tok": kw.get("out_tok", 5000), "messages": 40, "retries": 1,
                    "followup_prompts": 0},
           "wf": {"models": {kw.get("wmodel", DEFAULT_MODEL): 10}, "efforts": {kw.get("weffort", DEFAULT_EFFORT): 10},
                  "advisor": 0, "stages": kw.get("stages", ["R1-arch", "R1-quality", "R3-counter"]),
                  "out_tok": 9000, "turns": 30, "so_retries": 0},
           "gpt": {"calls": kw.get("gpt_calls", 1), "ok": kw.get("gpt_ok", 1), "failed": kw.get("gpt_failed", 0),
                   "launcher_ok": kw.get("gpt_launcher_ok", 0),
                   "banners": kw.get("banners", 1), "unlinked": kw.get("unlinked", 0),
                   "models": ["gpt-6-sol"], "efforts": ["xhigh"], "versions": ["0.157.0"]},
           "plugin": {"sha": "10197a0aaaa", "dirty": False, "tree_hash": kw.get("tree", "tB" if arm == "B" else "tC"),
                      "source": kw.get("psource", f"/src/{arm}"),
                      "source_tree_hash": kw.get("psource_tree", kw.get("tree", "tB" if arm == "B" else "tC"))},
           "artifacts": [{"path": f"/runs/{run_id}/a.md", "sha256": f"a-{run_id}"}],
           "injected": {"User": "u", "Project": "p", "AutoMem": None}, "instrument_sha": "i1",
           "input": {"hash": kw.get("input", "h1"), "root": kw.get("root", f"/runs/{run_id}/repo"), "tree_hash": "it1"},
           "wall": {"total_s": wall, "mtime_delta_s": 0.4, "workflows": [{"run_id": "w", "wf_s": 600, "lead_s": 610,
                                                                          "delta_pct": 1.64}]},
           "state": {"start_hash": "s", "pristine_hash": "s", "end_hash": "e", "leak": kw.get("leak", []),
                     "problems": kw.get("problems", [])},
           "complete": {"ok": kw.get("complete", True), "why": [] if kw.get("complete", True) else ["완료 알림 없음"]}}
    axes = kw.get("axes", {a: 1 for a in AXES6})
    score = {"type": "score", "run_id": run_id, "kind": "review", "fixture_sha": "L",
             "by_severity": {"critical": crit, "major": major, "minor": 0, "suggestion": 0},
             "by_axis": axes, "verified_ratio": kw.get("ratio", 0.8), "empty": False,
             "verified": kw.get("verified", True), "artifacts_sha": kw.get("score_arts", [f"a-{run_id}"]),
             "instrument_sha": kw.get("score_instr", INSTR_NOW), "blind_pack_sha": kw.get("pack", "P1")}
    return row, score


def _judge(rows_scores, **opt):
    runs = {r["run_id"]: r for r, _ in rows_scores}
    scores = {s["run_id"]: s for _, s in rows_scores}
    opts = {"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT, "phase": opt.get("phase"), "arm": opt.get("arm", "C"),
            "release": opt.get("release"), "workflows": ["fz-review"], "min_runs": opt.get("min_runs", 2),
            "runs": opt.get("runs", 1), "plugin_sha": opt.get("plugin_sha"), "require": opt.get("require", []),
            "envs": opt.get("envs"), "options_on": False, "require_passed": None}
    return judge_rows(runs, scores, opts)


def _write_lines(path, rows):
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def self_test(case=None):
    cases = {}

    def reg(fn):
        cases[fn.__name__.replace("_", "-")] = fn
        return fn

    base = lambda **kw: [_mk("B1", "B", 1, major=3, **kw.get("b1", {})), _mk("B2", "B", 3, major=2, **kw.get("b2", {}))]

    @reg
    def sc3_pass():
        rc, out = _judge(base() + [_mk("C1", "C", 2, major=2), _mk("C2", "C", 4, major=3)], require=["SC-3"])
        return rc == PASS, out

    @reg
    def sc3_fail():
        rc, out = _judge(base() + [_mk("C1", "C", 2, major=1), _mk("C2", "C", 4, major=1)], require=["SC-3"])
        return rc == FAIL and any("major" in x and "> N" in x for x in out), out

    @reg
    def sc3_smoke():
        ok_rc, a = _judge(base() + [_mk("S1", "C", 5, major=2, phase="release-smoke", release="R-A")],
                          phase="release-smoke", release="R-A", require=["SC-3-smoke"], runs=1)
        bad_rc, b = _judge(base() + [_mk("S1", "C", 5, major=1, phase="release-smoke", release="R-A")],
                           phase="release-smoke", release="R-A", require=["SC-3-smoke"], runs=1)
        two_rc, c = _judge(base() + [_mk("S1", "C", 5, phase="release-smoke", release="R-A"),
                                     _mk("S2", "C", 6, phase="release-smoke", release="R-A")],
                           phase="release-smoke", release="R-A", require=["SC-3-smoke"], runs=1)
        return (ok_rc, bad_rc, two_rc) == (PASS, FAIL, FAIL), a + b + c

    @reg
    def sc6_pass_fail():
        good_rc, a = _judge([_mk("B1", "B", 1, wall=1000), _mk("B2", "B", 3, wall=1100),
                             _mk("C1", "C", 2, wall=700), _mk("C2", "C", 4, wall=760)], require=["SC-6"])
        bad_rc, b = _judge([_mk("B1", "B", 1, wall=1000), _mk("B2", "B", 3, wall=1100),
                            _mk("C1", "C", 2, wall=1000), _mk("C2", "C", 4, wall=1020)], require=["SC-6"])
        return (good_rc, bad_rc) == (PASS, FAIL), a + b

    @reg
    def crossover_violation():
        bad_rc, a = _judge([_mk("B1", "B", 1), _mk("B2", "B", 2), _mk("C1", "C", 3), _mk("C2", "C", 4)],
                           require=["crossover-order"])
        good_rc, b = _judge([_mk("B1", "B", 1), _mk("C1", "C", 2), _mk("B2", "B", 3), _mk("C2", "C", 4)],
                            require=["crossover-order"])
        return (bad_rc, good_rc) == (FAIL, PASS), a + b

    @reg
    def sc5_negative():
        # 계획 채점표 항목을 전부 덮으면 PASS · 잔재 1건 누락이면 FAIL · feature fixture 만 있으면 UNRUN(제거 조항 미판정)
        FEAT, REM = ["RC1", "Q1a", "L1"], ["RC1", "Q1a", "L1", "RZ1", "CU1"]

        def plan(run_id, arm, order, fx, items, covered):
            row, score = _mk(run_id, arm, order, workflow="fz-plan", fixture=fx)
            crit = sum(1 for i in items if i.startswith(("RZ", "CU")))
            score = dict(score, kind="plan", items=items, covered=covered, items_total=len(items),
                         items_by_severity={"critical": crit, "major": len(items) - crit, "minor": 0, "suggestion": 0})
            return row, score

        def grp(fx, items, c2_cov):
            return [plan(f"{fx}-B1", "B", 1, fx, items, items), plan(f"{fx}-B2", "B", 3, fx, items, items),
                    plan(f"{fx}-C1", "C", 2, fx, items, items), plan(f"{fx}-C2", "C", 4, fx, items, c2_cov)]

        def j(rs):
            return judge_rows({r["run_id"]: r for r, _ in rs}, {s["run_id"]: s for _, s in rs},
                              dict(model=DEFAULT_MODEL, effort=DEFAULT_EFFORT, phase=None, arm="C", release=None,
                                   workflows=["fz-plan"], min_runs=2, runs=1, plugin_sha=None, require=["SC-5"],
                                   envs=None, options_on=False, require_passed=None))
        ok_rc, a = j(grp("feat", FEAT, FEAT) + grp("rem", REM, REM))
        miss_rc, b = j(grp("feat", FEAT, FEAT) + grp("rem", REM, ["RC1", "Q1a", "L1", "CU1"]))
        only_rc, c = j(grp("feat", FEAT, FEAT))
        return ((ok_rc, miss_rc, only_rc) == (PASS, FAIL, UNRUN) and any("⛔누락 ['RZ1']" in x for x in b)), a + b + c

    @reg
    def cp_dest_stops_at_operator():
        # 실측 명령 모양 — heredoc 뒤 `&& cp A B && … head -1`. 대상은 B 여야 하고 `-1` 이 아니다
        cmd = ("python3 - <<'EOF'\nx = 1\nEOF\npython3 gen.py 3 && cp P/plan-v3.md P/plan-final.md && R=/r; W=$PWD/P; "
               "python3 $R/g.py --out $W/g.md && cp $W/g.md $W/plan.md; echo \"E=$?\"; grep -c H $W/x | head -1")
        dests = [m.group(2) for m in CPMV_RE.finditer(_shell_part(cmd))]
        hit = _bash_writes(cmd, "/repo/P/plan-final.md", "/repo")
        miss = _bash_writes("cp P/a.md P/b.md && echo done", "/repo/P/plan-final.md", "/repo")
        return (dests[:1] == ["P/plan-final.md"] and "-1" not in dests and hit and not miss), [str(dests), hit, miss]

    @reg
    def writes_sed_inplace_and_renderer():
        # 실측(C1 마지막 명령) — 렌더러 --out-dir 가 review-report.md 를, sed -i '' 가 self-review.md 를 고쳤다
        cmd = ("WD=/r/ABT-1001; PR=/r/plugin\npython3 - \"$WD/review/review.json\" <<'PY'\nx=1\nPY\n"
               "rm -f $WD/review/review-report.md $WD/review/pr-comments.md\n"
               "python3 $PR/scripts/render_review.py --review $WD/review/review.json --diff $WD/review/diff.patch --out-dir $WD/review | head -2; echo x\n"
               "sed -i '' 's/suggestion 3/suggestion 4/' $WD/review/self-review.md $WD/index.md\n"
               "grep -n 's|a|b|' $WD/review/self-review.md | head")
        rep = _bash_writes(cmd, "/r/ABT-1001/review/review-report.md", "/r/plugin")
        sr = _bash_writes(cmd, "/r/ABT-1001/review/self-review.md", "/r/plugin")
        idx = _bash_writes(cmd, "/r/ABT-1001/index.md", "/r/plugin")
        # 음성 대조 — 읽기만(grep · cat · sed 출력) · rm · 렌더러 self-test · sed -n 은 쓰기가 아니다
        neg = [_bash_writes(x, "/r/ABT-1001/review/self-review.md", "/r")
               for x in ("grep -n x /r/ABT-1001/review/self-review.md", "sed -n 1,5p /r/ABT-1001/review/self-review.md",
                         "sed 's/a/b/' /r/ABT-1001/review/self-review.md > /tmp/o", "rm -f /r/ABT-1001/review/self-review.md",
                         "python3 /r/plugin/scripts/render_review.py --self-test")]
        gnu = _bash_writes("sed -i -e 's/a/b/' /r/f.md", "/r/f.md", "/r")
        return (rep and sr and idx and gnu and not any(neg)), [rep, sr, idx, gnu, neg]

    @reg
    def lead_cwd_is_session_start():
        # Lead 가 플러그인 폴더에 오래 머물러도(최빈 cwd = plugin) 작업 폴더는 세션 시작 cwd(repo)다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            evs = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "cwd": "/runs/x/repo", "message": {"content": "/fz:fz-review"}}]
            evs += [{"type": "assistant", "timestamp": f"2026-01-01T00:00:0{i}Z", "cwd": "/runs/x/plugin", "version": "2.1.282",
                     "message": {"id": f"m{i}", "model": "claude-opus-5-5", "stop_reason": "end_turn", "usage": {"output_tokens": 1},
                                 "content": [{"type": "text", "text": "t"}]}} for i in range(1, 6)]
            p = os.path.join(td, "t.jsonl")
            _write_lines(p, evs)
            tp = parse_transcript(p)
            return (tp["cwd"] == "/runs/x/repo" and tp["cwds"].get("/runs/x/plugin") == 5), [tp["cwd"], tp["cwds"]]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def gpt_out_var_resolved():
        # 실측(plan B1) — `W=$PWD/ABT-2001; …; "$R/scripts/gpt-exec.sh" exec --cd "$PWD" --out "$W/plan/gpt-verify.json"`
        cmd = 'W=$PWD/ABT-2001; R=/r/plugin; export FZ_PLUGIN_ROOT=$R; "$R/scripts/gpt-exec.sh" exec --cd "$PWD" --out "$W/plan/g.json"'
        a_ = _resolve_vars("$W/plan/g.json", cmd, "/runs/x/repo")
        b_ = _resolve_vars("$Q/plan/g.json", cmd, "/runs/x/repo")
        # 실측(review B2) — cwd=plugin 에서 `cd /runs/x/repo && R="$PWD" && …gpt-exec.sh review --out "$R/…"`
        c_ = _resolve_vars("$R/ABT-1001/review/gpt-review.md", 'cd /runs/x/repo && R="$PWD" && /p/gpt-exec.sh review --out "$R/o"', "/runs/x/plugin")
        d_ = _resolve_vars("$PWD/$W/o", "cd sub && W=a/b; x", "/runs/x")
        return (a_ == "/runs/x/repo/ABT-2001/plan/g.json" and b_ == "$Q/plan/g.json"
                and c_ == "/runs/x/repo/ABT-1001/review/gpt-review.md" and d_ == "/runs/x/sub/a/b/o"), [a_, b_, c_, d_]

    @reg
    def merge_summary_and_ac4():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            f = os.path.join(td, "merged.json")
            with open(f, "w", encoding="utf-8") as fh:
                json.dump({"summary": {"candidatesIn": 5, "candidatesOut": 5}}, fh)
            uses = [{"name": "Bash", "id": "1", "cwd": td, "input": {"command": f"WD={td}; python3 /p/scripts/review_merge.py --claude a --gpt b --diff d --out $WD/merged.json"}},
                    {"name": "Bash", "id": "2", "cwd": td, "input": {"command": "python3 scripts/review_merge.py --claude a --gpt-unavailable x --diff d"}},
                    {"name": "Bash", "id": "3", "cwd": td, "input": {"command": "wc -l scripts/review_merge.py; sed -n 1,5p scripts/review_merge.py"}},
                    {"name": "Bash", "id": "4", "cwd": td, "input": {"command": "python3 scripts/review_merge.py --self-test"}}]
            res = {"2": {"text": '{"summary": {"candidatesIn": 7, "candidatesOut": 7}}'}}
            m_ = _merge_summaries(uses, res)
            ok_sum = [(x["in"], x["out"]) for x in m_["summaries"]] == [(5, 5), (7, 7)] and m_["violations"] == 0
            rej = _merge_summaries([{"name": "Bash", "id": "5", "cwd": td, "input": {"command": "python3 scripts/review_merge.py --claude a --gpt b --diff d"}}],
                                   {"5": {"is_error": True, "text": "REJECT 후보 보존 위반 — 입력 3 ≠ 출력 2(AC-4)"}})
            rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
            for r_, _ in rows[2:]:
                r_["merge"] = {"summaries": [{"in": 5, "out": 5}], "violations": 0}
            good_rc, a_ = _judge(rows, require=["AC-4"])
            rows[3][0]["merge"] = {"summaries": [{"in": 5, "out": 4}], "violations": 0}
            bad_rc, b_ = _judge(rows, require=["AC-4"])
            rows[3][0]["merge"] = None
            none_rc, c_ = _judge(rows, require=["AC-4"])
            return (ok_sum and rej["violations"] == 1 and (good_rc, bad_rc, none_rc) == (PASS, FAIL, FAIL)), [m_, rej, a_, b_, c_]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def plan_phase2_evidence():
        mk = lambda c, err=False: ([{"name": "Bash", "id": "1", "cwd": "/r", "input": {"command": c}}], {"1": {"is_error": err}})
        v = _plan_phase2(*mk('"$R/scripts/gpt-exec.sh" exec --out "$W/plan/gpt-verify.json" --schema "$R/schemas/gpt_review_schema.json"'))
        r_ = _plan_phase2(*mk('"$R/scripts/gpt-exec.sh" resume --session-file "$S" --out o.json'))
        sprint = _plan_phase2(*mk('nohup "$R/scripts/gpt-exec.sh" exec --out "$W/plan/sprint-contract-gpt.md" --prompt-file p &'))
        doc = _plan_phase2(*mk("python3 - <<'EOF'\nx = 'gpt-exec.sh exec --schema gpt_review_schema'\nEOF"))
        fail = _plan_phase2(*mk('"$R/scripts/gpt-exec.sh" resume --session-file s', err=True))
        return (v and r_ and not sprint and not doc and not fail), [v, r_, sprint, doc, fail]

    @reg
    def gpt_home_sessions_count():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            d = os.path.join(td, "sessions", "2026", "09", "29")
            os.makedirs(d)
            _write_lines(os.path.join(d, "a.jsonl"), [{"type": "session_meta", "payload": {"id": "s1", "cli_version": "0.157.0"}},
                                                      {"type": "turn_context", "payload": {"model": "gpt-6-sol", "effort": "high"}}])
            _write_lines(os.path.join(d, "b.jsonl"), [{"type": "session_meta", "payload": {"id": "s2"}}])
            # review 모드 자식 — id 는 다르고 session_id 가 부모를 가리킨다
            _write_lines(os.path.join(d, "c.jsonl"), [{"type": "session_meta", "payload": {"id": "c1", "session_id": "s2", "cli_version": "0.157.0"}},
                                                      {"type": "turn_context", "payload": {"model": "gpt-6-sol", "effort": "high"}}])
            got = gpt_home_sessions(td)
            empty = tempfile.mkdtemp(prefix="abl-")
            try:
                none_sessions = gpt_home_sessions(empty)
            finally:
                shutil.rmtree(empty, ignore_errors=True)
            return (sorted(x["session"] for x in got) == ["s1", "s2"] and len(got) == 2
                    and gpt_home_sessions(os.path.join(td, "none")) is None and none_sessions == []), [got, none_sessions]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def segments_multiline_quote():
        # 실측(peer C1) — 병합 뒤 같은 줄에서 여는 여러 줄 `python3 -c "…"` 가 병합 명령까지 버리게 했다
        cmd = 'W=/w; P=/p; python3 $P/scripts/review_merge.py --claude a --gpt b --diff d --out $W/m.json; echo "e=$?"; python3 -c "\nimport json\nprint(1)\n"'
        segs = _segments(_shell_part(cmd))
        merged = [x for x in segs if _exec_of(x, "review_merge.py")]
        bad = _segments("echo 'unclosed\necho ok")    # 따옴표가 끝내 안 맞으면 줄마다로 물러선다
        return (len(merged) == 1 and merged[0][-2:] == ["--out", "$W/m.json"] and ["echo", "ok"] in bad), [segs, bad]

    @reg
    def gate_pass_in_redirect_target():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            with open(os.path.join(td, "da.log"), "w") as fh:
                fh.write("…\nGATE-PASS contract_ok issues=0\n")
            seg = f'bash /p/scripts/gpt-exec.sh exec --cd /r --out "$W/r.json" --prompt-file p > $W/da.log 2>&1'
            tg = _redirect_targets(seg)
            f = _resolve_vars(tg[0], f"W={td}; " + seg, td) if tg else None
            real = bool(REAL_HOME_SKILL_RE.search('SK=$HOME/.codex/skills/fz-challenger/SKILL.md; gpt-exec.sh exec --gpt-skill-path "$SK"'))
            iso_ = bool(REAL_HOME_SKILL_RE.search('SK=${CODEX_HOME:-$HOME/.codex}/skills/fz-challenger/SKILL.md'))
            return (f == os.path.join(td, "da.log") and real and not iso_), [tg, f, real, iso_]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def queued_followup_detected():
        first = "/fz:fz-plan ABT-2001 …"
        mk = lambda pr: {"type": "attachment", "attachment": {"type": "queued_command", "prompt": pr}}
        evs = [mk(first), {"type": "user", "message": {"content": "x"}}, mk("Gate 2 승인·확정 — 추가 질문 없이 plan-final.md 를 기록해줘"),
               mk("<task-notification>\n<task-id>b1</task-id>…"), {"type": "attachment", "attachment": {"type": "hook_success"}},
               {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "<agent-message from=\"a1\">…", "isMeta": True, "origin": "x"}}]
        return (queued_followups(evs, first) == 1 and queued_followups(evs[:2], first) == 0), [queued_followups(evs, first)]

    @reg
    def script_file_argv_write():
        scripts = {"/r/W/plan/mk.py": "import sys\nsrc = open(sys.argv[1]).read()\nopen(sys.argv[2], 'w', encoding='utf-8').write(src)\n"}
        cmd = "W=/r/W/plan; python3 $W/mk.py $W/plan-v3.md $W/plan-final.md && echo ok"
        final = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r", scripts)
        src = _bash_writes(cmd, "/r/W/plan/plan-v3.md", "/r", scripts)          # argv[1] 은 읽기
        unknown = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r", {})        # 본문을 모르면 쓰기로 치지 않는다
        here = _bash_writes("python3 - /r/a.md /r/f.md <<'EOF'\nimport sys\nopen(sys.argv[2], 'w').write('x')\nEOF", "/r/f.md", "/r")
        here_read = _bash_writes("python3 - /r/a.md /r/f.md <<'EOF'\nimport sys\nopen(sys.argv[2], 'w').write('x')\nEOF", "/r/a.md", "/r")
        return (final and not src and not unknown and here and not here_read), [final, src, unknown, here, here_read]

    @reg
    def gpt_call_via_variable_and_continuation():
        c1 = 'R=/r; X="/p/scripts/gpt-exec.sh"; ( "$X" exec --cd "$R" --out $R/v.json --prompt-file p --schema /p/schemas/gpt_review_schema.json ) > l 2>&1'
        c2 = '( "/p/scripts/gpt-exec.sh" exec --cd "$R" --out "$W/v.json" --prompt-file p \\\n    --effort high --schema /p/schemas/gpt_review_schema.json )'
        found1 = any(GPT_CALL_RE.search(_shell_part(v)) for v in _cmd_views(c1))
        ph1 = any(PHASE2_RE.search(_shell_part(v)) for v in _cmd_views(c1))
        ph2 = any(PHASE2_RE.search(_shell_part(v)) for v in _cmd_views(c2))
        neg = any(GPT_CALL_RE.search(_shell_part(v)) for v in _cmd_views('X="/p/scripts/gpt-exec.sh"; sed -n 1,5p "$X"'))
        return (found1 and ph1 and ph2 and not neg), [found1, ph1, ph2, neg]

    @reg
    def script_internal_output_path():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            sp = os.path.join(td, "render_plan.py")
            with open(sp, "w") as fh:
                fh.write('import sys\nW="/r/W"\nOUT = f"{W}/plan/plan-final.md" if sys.argv[1] == "final" else "x"\nopen(OUT, "w").write("x")\n')
            hit = _bash_writes(f"python3 {sp} final a.md b.json", "/r/W/plan/plan-final.md", "/r")
            other = _bash_writes(f"python3 {sp} final a.md b.json", "/r/W/plan/other.md", "/r")
            return (hit and not other), [hit, other]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def merge_summary_cd_relative_and_text():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            os.makedirs(os.path.join(td, "review"))
            with open(os.path.join(td, "review", "m.json"), "w") as fh:
                json.dump({"summary": {"candidatesIn": 56, "candidatesOut": 56}}, fh)
            u1 = {"name": "Bash", "id": "1", "cwd": td, "input": {"command": f"cd {td}/review && P=/p && python3 \"$P/scripts/review_merge.py\" --claude c.json --gpt g.json --diff d --out m.json"}}
            u2 = {"name": "Bash", "id": "2", "cwd": td, "input": {"command": "python3 /p/scripts/review_merge.py --claude c --gpt g --diff d"}}
            got = _merge_summaries([u1, u2], {"2": {"text": "MERGE OK — 후보 12→12 · 그룹 9"}})
            return ([(x["in"], x["out"]) for x in got["summaries"]] == [(56, 56), (12, 12)]), [got]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def shell_heredoc_body_is_command():
        scripts = {"/r/W/plan/mk.py": "import sys\nsrc, dst = sys.argv[1], sys.argv[2]\nopen(dst, 'w').write(open(src).read())\n"}
        cmd = "bash <<'BASH'\nset -u\nW=/r/W\npython3 $W/plan/mk.py $W/plan/v3.md $W/plan/plan-final.md || exit 1\nBASH"
        w = _bash_writes(cmd, "/r/W/plan/plan-final.md", "/r", scripts)
        r = _bash_writes(cmd, "/r/W/plan/v3.md", "/r", scripts)
        data = _bash_writes("cat > /r/n.txt <<'EOF'\npython3 /r/W/plan/mk.py a /r/W/plan/plan-final.md\nEOF", "/r/W/plan/plan-final.md", "/r", scripts)
        g = any(GPT_CALL_RE.search(_shell_part(v)) for v in _cmd_views("bash <<'X'\n/p/scripts/gpt-exec.sh exec --out o --prompt-file p\nX"))
        return (w and not r and not data and g), [w, r, data, g]

    @reg
    def critical_path_recorded():
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
        rows[2][0]["critical"] = {"gpt_plan_s": 900.0, "wf_s": 1200.0, "path": "workflow"}
        rows[3][0]["critical"] = {"gpt_plan_s": 1500.0, "wf_s": 1200.0, "path": "gpt"}
        ok_w, a = _judge(rows, require=["gpt-wf-wall"])
        ok_p, b = _judge(rows, require=["critical-path"])
        switched = any("전환" in x for x in b)
        rows[3][0]["critical"] = {"gpt_plan_s": None, "wf_s": 1200.0, "path": None}
        miss_w, c = _judge(rows, require=["gpt-wf-wall"])
        miss_p, d = _judge(rows, require=["critical-path"])
        calls = _launcher_calls([{"id": "1", "ts": None, "input": {"command": 'bash "$P/scripts/gpt_independent.sh" plan --requirement r'}},
                                 {"id": "2", "ts": None, "input": {"command": "sed -n 1,80p $P/scripts/gpt_independent.sh"}}], {}, {})
        return ((ok_w, ok_p, miss_w, miss_p) == (PASS, PASS, FAIL, FAIL) and switched
                and [x["mode"] for x in calls] == ["plan"]), a + b + c + d + [str(calls)]

    @reg
    def blind_labels_one_pack():
        # 한 꾸러미 → PASS · arm 별 꾸러미 → FAIL · 판정 전(미검증) → UNRUN · 검증됐다는데 꾸러미가 없음 → FAIL
        one_rc, a = _judge(base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)], require=["blind-labels"])
        split_rc, b = _judge(base() + [_mk("C1", "C", 2, pack="P2"), _mk("C2", "C", 4, pack="P2")], require=["blind-labels"])
        unv_rc, c = _judge(base() + [_mk("C1", "C", 2, verified=False), _mk("C2", "C", 4)], require=["blind-labels"])
        nopack_rc, d = _judge(base() + [_mk("C1", "C", 2, pack=None), _mk("C2", "C", 4)], require=["blind-labels"])
        return (one_rc, split_rc, unv_rc, nopack_rc) == (PASS, FAIL, UNRUN, FAIL), a + b + c + d

    @reg
    def ac1_mismatch_invalid():
        rc, out = _judge(base() + [_mk("C1", "C", 2, effort="high"), _mk("C2", "C", 4, wmodel="claude-sonnet-5"),
                                   _mk("C3", "C", 6), _mk("C4", "C", 8)], require=["SC-3"])
        inval = [x for x in out if x.startswith("  INVALID")]
        return (any("C1" in x and "AC-1 Lead effort" in x for x in inval) and
                any("C2" in x and "AC-1 워커 model" in x for x in inval) and rc == PASS), out

    @reg
    def ac5_incomplete_not_zero():
        # 미완주 C 2개는 0건이 아니라 무효 → 유효 run 부족 FAIL (0건으로 세면 'loss' 계산이 돌았을 것이다)
        rc, out = _judge(base() + [_mk("C1", "C", 2, complete=False, major=0), _mk("C2", "C", 4, complete=False, major=0)],
                         require=["SC-3"])
        return rc == FAIL and any("정확히" in x for x in out) and not any("loss=" in x for x in out), out

    @reg
    def ac7_memory_diff_invalid():
        rc, out = _judge(base(b2={"leak": ["user_agent_memory"]}), phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "AC-7" in x for x in out), out

    @reg
    def sc4_axis_and_ratio():
        # B 비율 0.8·0.76 → 잡음 0.04 · 하한 0.74. (B 가 같은 값이면 잡음 0 이라 어떤 감소도 미달이다)
        nb = lambda: base(b1={"ratio": 0.8}, b2={"ratio": 0.76})
        miss_rc, a = _judge(nb() + [_mk("C1", "C", 2, axes={x: 1 for x in AXES6 if x != "placement"}),
                                    _mk("C2", "C", 4)], require=["SC-4"])
        low_rc, b = _judge(nb() + [_mk("C1", "C", 2, ratio=0.5), _mk("C2", "C", 4, ratio=0.5)], require=["SC-4"])
        ok_rc, c = _judge(nb() + [_mk("C1", "C", 2, ratio=0.8), _mk("C2", "C", 4, ratio=0.78)], require=["SC-4"])
        return (miss_rc, low_rc, ok_rc) == (FAIL, FAIL, PASS) and any("placement" in x for x in a), a + b + c

    @reg
    def sc7_fields_required():
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)]
        rows[2][0]["lead"]["out_tok"] = None
        bad_rc, a = _judge(rows, require=["SC-7"])
        ok_rc, b = _judge(base() + [_mk("C1", "C", 2), _mk("C2", "C", 4)], require=["SC-7"])
        return (bad_rc, ok_rc) == (FAIL, PASS) and any("out_tok" in x for x in a), a + b

    @reg
    def sc7_launcher_counts():
        # 실측 review C: 직접 호출 0 · 런처 1(감사 exit 0) — 런처를 세지 않으면 GPT 리뷰를 옮긴 후보가 '검증 누락' 으로 떨어졌다
        lrow = lambda n, o, lo: _mk(n, "C", o, gpt_calls=0, gpt_ok=0, gpt_launcher_ok=lo)
        ok_rc, a = _judge(base() + [lrow("C1", 2, 1), lrow("C2", 4, 1)], require=["SC-7"])
        bad_rc, b = _judge(base() + [lrow("C1", 2, 0), lrow("C2", 4, 1)], require=["SC-7"])
        return ((ok_rc, bad_rc) == (PASS, FAIL) and any("직접 0 + 런처 1" in x for x in a)
                and any("C1" in x and "직접 0 + 런처 0" in x for x in b)), a + b

    @reg
    def launcher_audit_ok():
        # ⛔ 성공은 감사 exit 0 뿐 — 실패 코드 · 깨진 JSON · 객체가 아닌 JSON · 없는 파일은 성공이 아니다
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            got = []
            for name, body in [("a", '{"exit": 0, "note": "ok"}'), ("b", '{"exit": 15, "note": "격리 미적용"}'),
                               ("c", '{"exit": 0'), ("d", "[0]")]:
                pth = os.path.join(td, name + ".audit.json")
                with open(pth, "w", encoding="utf-8") as fh:
                    fh.write(body)
                got.append(_launcher_ok(pth))
            got.append(_launcher_ok(os.path.join(td, "none.audit.json")))
            return got == [True, False, False, False, False], got
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def input_hash_mismatch_invalid():
        rc, out = _judge(base() + [_mk("B3", "B", 5, input="h2")], phase="baseline", min_runs=2)
        return rc == PASS and any("B3" in x and "input-hash" in x for x in out), out

    @reg
    def two_fixture_groups():
        # fz-plan 은 feature·removal 두 fixture 에서 기준선을 잰다 — 입력 해시가 달라도 서로를 무효로 만들면 안 된다
        rows = [_mk("F1", "B", 1, fixture="plan-feature", input="hf"), _mk("F2", "B", 3, fixture="plan-feature", input="hf"),
                _mk("R1", "B", 5, fixture="plan-removal", input="hr"), _mk("R2", "B", 7, fixture="plan-removal", input="hr")]
        rc, out = _judge(rows, phase="baseline", min_runs=2)
        return (rc == PASS and not any("INVALID" in x for x in out)
                and any("[plan-feature]" in x for x in out) and any("[plan-removal]" in x for x in out)), out

    @reg
    def unimplemented_is_unrun():
        # ⛔ 아직 구현하지 않은 기준으로 잰다 — 구현된 기준은 입력 부족으로도 UNRUN 이 나와 이 사례를 헛되이 통과시킨다
        a_rc, a = _judge(base(), require=["SC-1"])
        b_rc, b = _judge(base(), require=["SC-3"], envs="isolated,installed")
        return (a_rc, b_rc) == (UNRUN, UNRUN) and any("미구현 기준 ['SC-1']" in x for x in a), a + b

    @reg
    def plugin_sha_baseline():
        rc, out = _judge(base(b1={}) + [_mk("B3", "B", 5)], phase="baseline", min_runs=3, plugin_sha="10197a0")
        rows = base()
        rows[1][0]["plugin"]["sha"] = "757afe2bbbb"
        rc2, out2 = _judge(rows, phase="baseline", min_runs=2, plugin_sha="10197a0")
        return (rc, rc2) == (PASS, FAIL), out + out2

    @reg
    def transcript_usage_dedupe():
        td = tempfile.mkdtemp(prefix="abl-")
        try:
            u = {"output_tokens": 100}
            evs = [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "/fz:fz-review"}}]
            evs += [{"type": "assistant", "timestamp": f"2026-01-01T00:00:0{i}Z", "effort": "xhigh", "version": "2.1.282",
                     "message": {"id": "m1", "model": "claude-opus-5-5", "stop_reason": "tool_use", "usage": u,
                                 "content": [{"type": k}]}} for i, k in enumerate(("thinking", "text"), 1)]
            p = os.path.join(td, "t.jsonl")
            _write_lines(p, evs)
            lead = parse_transcript(p)["lead"]
            return (lead["out_tok"], lead["messages"], lead["effort"]) == (100, 1, "xhigh"), [str(lead)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    labels2 = {"issues": [{"id": "I1", "axis": "naming", "severity": "major", "file": "App/A.swift",
                           "line_start": 10, "line_end": 12},
                          {"id": "I2", "axis": "idiom", "severity": "critical", "file": "App/B.swift",
                           "line_start": 40, "line_end": 40}]}

    @reg
    def cite_and_score():
        texts = ["- `A.swift:13` 이름이 반환 의미를 말하지 않는다\n- `App/B.swift:L55` 무관\n- `C.swift:1-3` 위치가 틀렸다"]
        v = {"A.swift:13": {"real": True, "label_ids": ["I1"]}, "App/B.swift:55": {"real": False},
             "C.swift:1-3": {"real": True, "label_ids": [], "severity": "minor", "axis": "placement"}}
        s = score_review(labels2, texts, v)
        ok = (s["verified"] and s["labels_found"] == ["I1"] and s["by_severity"]["major"] == 1
              and s["by_severity"]["critical"] == 0 and s["by_axis"]["placement"] == 1 and s["verified_ratio"] == round(2 / 3, 4))
        part = score_review(labels2, texts, {"A.swift:13": {"real": True, "label_ids": ["I1"]}})
        ok &= part["verified"] is False and part["unverified"] == 2 and part["verified_ratio"] is None
        rub = {"sections": {"Contracts": [{"id": "PC1", "criterion": "c", "keywords": ["DTO"]}]}, "questions": {},
               "residues": [{"id": "RZ1", "symbol": "LegacyX", "file": "a.swift"}]}
        p = score_plan(rub, "DTO 를 정의하지 않는다 · LegacyX 제거", {"PC1": {"covered": False}, "RZ1": {"covered": True}})
        ok &= p["verified"] and p["covered"] == ["RZ1"] and p["by_severity"]["critical"] == 1 and p["by_severity"]["major"] == 0
        ok &= score_plan(rub, "DTO", None)["verified"] is False
        return ok, [str(s), str(part), str(p)]

    @reg
    def ok_mention_not_counted():
        # ⛔ GPT ISSUE-001 — 라벨 위치를 '정상' 이라고 인용해도 발견이 아니다. 판정 없으면 SC-3 은 UNRUN
        texts = ["- `App/A.swift:11` 정상 — 문제 없음"]
        s = score_review(labels2, texts, {"App/A.swift:11": {"real": False}})
        rows = base() + [_mk("C1", "C", 2), _mk("C2", "C", 4, verified=False)]
        rc, out = _judge(rows, require=["SC-3"])
        return (s["by_severity"]["major"] == 0 and s["labels_found"] == [] and rc == UNRUN
                and any("가린 검증자" in x for x in out)), out + [str(s)]

    @reg
    def c_same_tree_invalid():
        rc, out = _judge(base() + [_mk("C1", "C", 2, tree="tB"), _mk("C2", "C", 4, tree="tB")], require=["SC-3"])
        return rc == FAIL and any("같은 플러그인 트리" in x for x in out), out

    @reg
    def input_root_reuse_invalid():
        rc, out = _judge([_mk("B1", "B", 1, root="/r/x"), _mk("B2", "B", 3, root="/r/x")], phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "재사용" in x for x in out), out

    @reg
    def extra_valid_run_fails():
        rc, out = _judge(base() + [_mk("C1", "C", 2), _mk("C2", "C", 4), _mk("C3", "C", 6)], require=["SC-6"])
        return rc == FAIL and any("정확히" in x for x in out), out

    @reg
    def baseline_rejects_other_require():
        rc, out = _judge(base(), phase="baseline", require=["SC-3"])
        return rc == UNRUN and any("baseline-runs 만" in x for x in out), out

    @reg
    def state_problems_invalid():
        rc, out = _judge(base(b2={"problems": ["start 에 감시 이름 repo_agent_memory 없음"]}), phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "AC-7 감시 불완전" in x for x in out), out

    @reg
    def gpt_banner_missing_invalid():
        rc, out = _judge(base(b2={"gpt_ok": 2, "banners": 1}), phase="baseline", min_runs=2)
        return rc == FAIL and any("B2" in x and "GPT 배너" in x for x in out), out

    @reg
    def bool_verdict_rejected():
        # ⛔ GPT ISSUE-025 — "false" 문자열은 참으로 읽히면 안 된다(미검증)
        s = score_review(labels2, ["- `A.swift:13` 이름"], {"A.swift:13": {"real": "false", "label_ids": ["I1"]}})
        pl = score_plan({"sections": {"C": [{"id": "PC1", "criterion": "c"}]}, "questions": {}}, "x", {"PC1": {"covered": "false"}})
        return (s["verified"] is False and s["unverified"] == 1 and pl["verified"] is False and pl["covered"] == []), [str(s), str(pl)]

    @reg
    def stale_score_unrun():
        # ⛔ GPT ISSUE-024 — 점수의 산출물 해시가 현재 행과 다르면 낡은 판정이다
        rows = base() + [_mk("C1", "C", 2, score_arts=["old"]), _mk("C2", "C", 4)]
        rc, out = _judge(rows, require=["SC-3"])
        return rc == UNRUN and any("C1" in x and "낡음" in x for x in out), out

    @reg
    def plugin_tree_and_source_invalid():
        # ⛔ GPT ISSUE-003 — 트리 해시 없음 · 선언 원본과 다른 사본은 무효
        rc, out = _judge(base(b2={"tree": None}), phase="baseline", min_runs=2)
        rc2, out2 = _judge(base(b2={"psource": "/src/B", "psource_tree": "other"}), phase="baseline", min_runs=2)
        return (rc, rc2) == (FAIL, FAIL) and any("트리 해시 없음" in x for x in out) and any("원본" in x for x in out2), out + out2

    @reg
    def gpt_failed_or_unlinked_invalid():
        # ⛔ GPT ISSUE-013·014 — 실패한 GPT 호출 · 배너가 연결되지 않은 성공 호출
        rc, out = _judge(base(b2={"gpt_failed": 1}), phase="baseline", min_runs=2)
        rc2, out2 = _judge(base(b2={"unlinked": 1}), phase="baseline", min_runs=2)
        return (rc, rc2) == (FAIL, FAIL) and any("GPT 호출 실패" in x for x in out) and any("미연결" in x for x in out2), out + out2

    @reg
    def root_reuse_across_workflows():
        # ⛔ GPT ISSUE-007 잔여 — 다른 워크플로가 같은 저장소 경로를 써도 재사용이다
        rows = [_mk("B1", "B", 1, root="/r/shared"), _mk("B2", "B", 3),
                _mk("P1", "B", 5, workflow="fz-plan", root="/r/shared"), _mk("P2", "B", 7, workflow="fz-plan")]
        runs = {r["run_id"]: r for r, _ in rows}
        scores = {s["run_id"]: s for _, s in rows}
        opts = {"model": DEFAULT_MODEL, "effort": DEFAULT_EFFORT, "phase": "baseline", "arm": "C", "release": None,
                "workflows": ["fz-review", "fz-plan"], "min_runs": 2, "runs": 1, "plugin_sha": None,
                "require": [], "envs": None, "options_on": False, "require_passed": None}
        rc, out = judge_rows(runs, scores, opts)
        return rc == FAIL and any("P1" in x and "재사용" in x for x in out), out

    @reg
    def stage_expectations():
        ok = (_required_stages("fz-peer-review", True, 3) == ["R1-arch", "R1-quality", "R1-correct", "R2-arch", "R2-quality",
                                                              "R3-counter"]
              and _required_stages("fz-peer-review", False, 2) == ["R1-arch", "R1-quality", "R1-correct"]
              and _expected_stages_completed("fz-peer-review", True, 3) == 3
              and _expected_stages_completed("fz-peer-review", False, 2) == 1
              and _expected_stages_completed("fz-review", None, None) == 3
              and _expected_stages_completed("fz-plan", None, None) == 2)
        blk = cite_spans(["- `A.swift:3` 이름이 틀렸다\n  근거: 반환값이 있는데 동사형\n- `B.swift:9` 다른 지적"])
        ok &= len(blk) == 2 and "근거" in blk[0][3] and "다른 지적" not in blk[0][3]
        return ok, [str(blk)]

    @reg
    def real_without_mapping_unverified():
        # ⛔ GPT ISSUE-027 — real=true 인데 라벨·severity·axis 가 없거나, 다른 파일의 라벨로 매핑하면 미검증
        a = score_review(labels2, ["- `A.swift:13` 이름"], {"A.swift:13": {"real": True, "label_ids": []}})
        b = score_review(labels2, ["- `A.swift:13` 이름"], {"A.swift:13": {"real": True, "label_ids": ["I2"]}})
        return (a["verified"] is False and b["verified"] is False and a["unverified"] == 1 and b["unverified"] == 1), [str(a), str(b)]

    @reg
    def stale_scorer_unrun():
        # ⛔ GPT ISSUE-024 — 채점기(계측기) 버전이 바뀐 뒤의 옛 점수는 쓰지 않는다
        rc, out = _judge(base() + [_mk("C1", "C", 2, score_instr="old"), _mk("C2", "C", 4)], require=["SC-3"])
        return rc == UNRUN and any("C1" in x and "낡음" in x for x in out), out

    @reg
    def string_json_error_result():
        # ⛔ GPT ISSUE-005 — journal 결과가 JSON 문자열로 된 오류여도 실패로 센다
        td = tempfile.mkdtemp(prefix="abl-wf-")
        try:
            _write_lines(os.path.join(td, "agent-x1.jsonl"), [
                {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"content": "[역할] 통합자 — x"}},
                {"type": "assistant", "timestamp": "2026-01-01T00:00:05Z",
                 "message": {"id": "m", "model": "claude-opus-5-5", "stop_reason": "end_turn", "usage": {"output_tokens": 1},
                             "content": []}}])
            _write_lines(os.path.join(td, "journal.jsonl"), [{"type": "started", "agentId": "x1"},
                                                             {"type": "result", "agentId": "x1",
                                                              "result": "{\"ok\": false, \"error\": \"worker failed\"}"}])
            s = wf_summary(td)
            return s["journal_empty_results"] == 1, [str(s["journal_empty_results"])]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def write_target_must_be_artifact():
        # ⛔ GPT ISSUE-011 — 같은 명령의 무관한 쓰기 동사는 산출물 쓰기가 아니다
        unrelated = "cat report.md; python3 -c \"from pathlib import Path; Path('other.md').write_text('x')\""
        real = "python3 -c \"from pathlib import Path; Path('out/report.md').write_text('x')\""
        return (not _writes_path(unrelated, "report.md") and _writes_path(real, "report.md")), []

    @reg
    def variable_path_and_cd_writes():
        # 실측 2026-09-26 — review B1 끝점이 +472s 로 잡혔다(실제 마지막 쓰기 +1433s)
        var_w = "python3 - <<'EOF'\np='ABT/review/self-review.md'\ns=open(p).read()\nopen(p,'w').write(s)\nEOF"
        var_r = "python3 - <<'EOF'\np='ABT/review/self-review.md'\nprint(open(p).read())\nq='x.md'\nopen(q,'w').write('')\nEOF"
        other = "python3 - <<'EOF'\np='other.md'\nopen(p,'w').write('')\nEOF"
        bases = _cd_bases("cd /r/repo && cat >> ABT/review/self-review.md <<'EOF'\nx\nEOF", "/x")
        ok = _writes_path(var_w, "self-review.md") and not _writes_path(var_r, "self-review.md") \
            and not _writes_path(other, "self-review.md") and bases == ["/x", "/r/repo"]
        return ok, [str(bases)]

    @reg
    def append_many_is_all_or_nothing():
        # v4.40.0 validate — recollect 가 행마다 덧붙이다 중간에 실패하면 일부만 남았다
        td = tempfile.mkdtemp(prefix="abl-app-")
        try:
            p = os.path.join(td, "l.jsonl")
            append(p, {"type": "run", "run_id": "a"})
            append_many(p, [{"type": "run", "run_id": "b"}, {"type": "run", "run_id": "c"}])
            ok1 = [json.loads(l)["run_id"] for l in open(p, encoding="utf-8")] == ["a", "b", "c"]
            try:
                append_many(p, [{"type": "run", "run_id": "d"}, {"bad": object()}])   # 직렬화 실패 → 아무것도 안 바뀐다
            except TypeError:
                pass
            ok2 = [json.loads(l)["run_id"] for l in open(p, encoding="utf-8")] == ["a", "b", "c"] and not glob.glob(os.path.join(td, ".ledger-*"))
            return ok1 and ok2, [str(ok1), str(ok2)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def end_snapshot_repo_path_checked():
        # v4.40.0 리뷰 — 종료 스냅샷이 다른(빈) repo_agent_memory 를 보면 AC-7 판정 불가다
        td = tempfile.mkdtemp(prefix="abl-state-")
        try:
            def snap(repo_mem):
                w = {"user_agent_memory": {"path": os.path.expanduser(CANON_WATCH["user_agent_memory"]), "pattern": None, "exists": True, "files": {}},
                     "repo_agent_memory": {"path": repo_mem, "pattern": None, "exists": False, "files": {}},
                     "user_sessions": {"path": os.path.expanduser(CANON_WATCH["user_sessions"]), "pattern": CANON_PATTERN["user_sessions"],
                                       "exists": True, "files": {}}}
                return {"schema": STATE_SCHEMA, "watch": w, "hash": state_hash(w)}
            paths = {}
            for k, repo_mem in (("p", "/nonexistent"), ("s", "/r/repo/.claude/agent-memory"), ("e_ok", "/r/repo/.claude/agent-memory"),
                                ("e_bad", "/other/.claude/agent-memory")):
                paths[k] = os.path.join(td, k + ".json")
                json.dump(snap(repo_mem), open(paths[k], "w", encoding="utf-8"))
            ok = state_info(paths["p"], paths["s"], paths["e_ok"], "/r/repo")["problems"]
            bad = state_info(paths["p"], paths["s"], paths["e_bad"], "/r/repo")["problems"]
            return (not any("end 의 repo_agent_memory" in x for x in ok) and any("end 의 repo_agent_memory" in x for x in bad)), ok + bad
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def cite_formats_from_real_artifacts():
        # v4.40.0 리뷰 — 실제 C1 산출물은 `path` L52–65 형식을 쓴다(후보에서 빠진 채 verified=True)
        t = ("- `App/Watchlist/WatchlistInteractor.swift` L52–65 삭제 경로\n- App/Foo.swift#L10-L20 참고\n"
             "- Bar.swift L3-6 · Baz.swift:7\n- 버전 4.40.0 L2 는 인용이 아니다")
        got = [(f, s, e) for f, s, e, _ in cite_spans([t])]
        want = sorted([("App/Foo.swift", 10, 20), ("App/Watchlist/WatchlistInteractor.swift", 52, 65), ("Bar.swift", 3, 6), ("Baz.swift", 7, 7)])
        return got == want, [str(got)]

    @reg
    def gpt_call_heads_and_segment():
        # v4.40.0 리뷰 — 템플릿의 들여쓴·then 뒤·접두 호출을 못 잡았고, 뒤 호출의 --effort 가 앞 호출을 '명시' 로 바꿨다
        pos = ["if true; then\n  \"$P/scripts/gpt-exec.sh\" exec --cd . --out o.md --prompt-file p.md\nfi",
               "then \"$P/scripts/gpt-exec.sh\" review --cd . --out r.md --uncommitted",
               "FZ_PLUGIN_ROOT=$P bash \"$P/scripts/gpt-exec.sh\" exec --cd . --out o.md --prompt-file p",
               "timeout 600 $P/scripts/gpt-exec.sh exec --cd . --out o.md --prompt-file p"]
        neg = ["sed -n 1,60p $P/scripts/gpt-exec.sh | grep usage", "rg 'gpt-exec.sh exec' modules"]
        heads = [bool(GPT_CALL_RE.search(_shell_part(c))) for c in pos + neg]
        two = ("\"$P/scripts/gpt-exec.sh\" exec --cd . --out a.md --prompt-file p\n"
               "\"$P/scripts/gpt-exec.sh\" exec --cd . --out b.md --prompt-file q --effort high")
        seg = _call_segment(two, GPT_CALL_RE.search(two))
        tight = "$P/scripts/gpt-exec.sh exec --cd . --out a.md; echo --effort high"
        seg2 = _call_segment(tight, GPT_CALL_RE.search(tight))
        quoted = '$P/scripts/gpt-exec.sh exec --cd "a;b && c" --out o.md > "$W/l;og" 2>&1 --effort high; echo x'
        seg3 = _call_segment(quoted, GPT_CALL_RE.search(quoted))
        cont = "$P/scripts/gpt-exec.sh exec --cd . \\\n  --out c.md --effort xhigh\necho --effort low"
        seg4 = _call_segment(cont, GPT_CALL_RE.search(cont))
        ok = heads == [True] * len(pos) + [False] * len(neg) and "--effort" not in seg and "a.md" in seg and "b.md" not in seg \
            and "--effort" not in seg2 and "a.md" in seg2 and "--effort high" in seg3 and "echo" not in seg3 \
            and "--effort xhigh" in seg4 and "low" not in seg4
        return ok, [str(heads), seg, seg2, seg3, seg4]

    @reg
    def verify_fields_cover_judged_gpt_and_plugin():
        # hunter M1 — 판정이 읽는 필드가 원천 대조 밖이면 행을 고쳐 무효 사유를 지울 수 있다(실측 FAIL→PASS)
        need = {"gpt.failed", "gpt.unlinked", "plugin.dirty", "plugin.source", "plugin.source_tree_hash"}
        return need <= set(VERIFY_FIELDS["transcript"]), [str(sorted(need - set(VERIFY_FIELDS["transcript"])))]

    @reg
    def argv_and_shell_var_writes():
        # 실측 2026-09-27(F-331) — B 4/6 run 의 마지막 쓰기(셸 변수 리다이렉트 · argv 로 넘긴 경로 · for 값)를 놓쳤다
        art = "/r/ABT/review/self-review.md"
        pos = ["F=/r/ABT/review/self-review.md; python3 - \"$F\" <<'EOF'\nimport sys\np=sys.argv[1]; t=open(p).read()\n"
               "open(p,'w').write(t); print(\"ok\")\nEOF",
               "W=/r/ABT/review; cp /tmp/x.txt $W/integrity-check.txt; cat >> $W/self-review.md <<'EOF'\n- x\nEOF",
               "W=/r/ABT; for f in self-review.md other.md; do python3 - \"$W/review/$f\" <<'EOF'\nimport sys\n"
               "p=sys.argv[1]; s=open(p,encoding='utf-8').read()\nopen(p,\"w\",encoding='utf-8').write(s)\nEOF\ndone",
               "P=/r/log.md; W=/r/ABT/review; python3 - \"$P\" \"$W/self-review.md\" <<'PY'\nimport sys\n"
               "p,sr=sys.argv[1],sys.argv[2]\nopen(sr,'w').write('x')\nPY"]
        neg = ["F=/r/ABT/review/self-review.md; python3 - \"$F\" <<'EOF'\nimport sys\np=sys.argv[1]\nprint(open(p).read())\nEOF",
               "A=/r/log.md; F=/r/ABT/review/self-review.md; python3 - \"$A\" \"$F\" <<'EOF'\nimport sys\n"
               "p,sr=sys.argv[1],sys.argv[2]\nt=open(sr).read()\nopen(p,'w').write(t)\nEOF",
               "W=/r/ABT/review; cat $W/self-review.md 2>&1 | head"]
        got = [_bash_writes(c, art, "/x") for c in pos + neg]
        return got == [True] * len(pos) + [False] * len(neg), [str(got)]

    def _effort_rows(e1, e2, d1, d2):
        rs = base()
        for (r, _), e, d in zip(rs, (e1, e2), (d1, d2)):
            r["gpt"]["efforts"], r["gpt"]["efforts_default"] = e, d
        return rs

    @reg
    def gpt_explicit_effort_not_compared():
        # F-333 — Lead 가 `--effort` 를 명시한 호출은 run 마다 달라도 무효가 아니다(측정 대상의 행동)
        rc, out = _judge(_effort_rows(["xhigh"], ["high"], [], []), phase="baseline", min_runs=2)
        return rc == PASS and not any("불일치" in x for x in out), out

    @reg
    def gpt_default_effort_still_compared():
        # F-333 — 기본값으로 간 호출의 effort 가 다르면 환경 차이다 — 여전히 무효
        rc, out = _judge(_effort_rows(["xhigh"], ["high"], ["xhigh"], ["high"]), phase="baseline", min_runs=2)
        return rc == FAIL and any("gpt-effort 불일치" in x for x in out), out

    @reg
    def blind_source_accumulates():
        # ⛔ GPT ISSUE-023 — 꾸러미 source 는 fixture 의 모든 run 이 인용한 파일을 담는다
        td = tempfile.mkdtemp(prefix="abl-src-")
        try:
            fxr = os.path.join(td, "fx")
            for sub, body in (("base", "x\n"), ("head", "y\n")):
                for f in ("App/A.swift", "App/B.swift"):
                    os.makedirs(os.path.dirname(os.path.join(fxr, "r", sub, f)), exist_ok=True)
                    open(os.path.join(fxr, "r", sub, f), "w").write(body if f.endswith("A.swift") else "same\n")
            json.dump(labels2, open(os.path.join(fxr, "r", "labels.json"), "w"))
            rows = []
            for rid, cite in (("RA", "App/A.swift:1"), ("RB", "App/B.swift:1")):
                ap_ = os.path.join(td, f"{rid}.md")
                open(ap_, "w").write(f"- `{cite}` 지적\n")
                rows.append({"run_id": rid, "fixture": "r", "sources": {"artifacts": [ap_]}, "artifacts": []})
            pack, _ = blind_pack(rows, fxr, "s")
            files = sorted(pack["fixtures"]["r"]["source"]["files"])
            return files == ["App/A.swift", "App/B.swift"], [str(files)]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    @reg
    def blind_roundtrip():
        td = tempfile.mkdtemp(prefix="abl-blind-")
        try:
            fxr = os.path.join(td, "fx")
            os.makedirs(os.path.join(fxr, "r"))
            with open(os.path.join(fxr, "r", "labels.json"), "w", encoding="utf-8") as fh:
                json.dump(labels2, fh)
            rows = []
            for rid in ("RUNID-ALPHA", "RUNID-BETA"):
                ap_ = os.path.join(td, f"{rid}.md")
                with open(ap_, "w", encoding="utf-8") as fh:
                    fh.write(f"- `App/A.swift:11` 이름 문제 (/Users/someone/{rid}/x)\n")
                rows.append({"run_id": rid, "arm": "B", "fixture": "r", "sources": {"artifacts": [ap_]}})
            pack, key = blind_pack(rows, fxr, "salt")
            blob = json.dumps(pack, ensure_ascii=False)
            leak = [s for s in ("RUNID-ALPHA", "RUNID-BETA", "/Users/", '"arm"') if s in blob]
            va = {it["anon"]: {c["cid"]: {"real": True, "label_ids": ["I1"]} for c in it["candidates"]} for it in pack["items"]}
            got, _arts, missing = blind_unpack(pack, key, va)
            va2 = dict(va)
            va2.pop(pack["items"][0]["anon"])
            _, _, missing2 = blind_unpack(pack, key, va2)
            ok = not leak and sorted(got) == ["RUNID-ALPHA", "RUNID-BETA"] and not missing and len(missing2) == 1
            return ok, [f"leak={leak} got={sorted(got)} missing={missing} missing2={missing2}"]
        finally:
            shutil.rmtree(td, ignore_errors=True)

    names = [case] if case else sorted(cases)
    if case and case not in cases:
        print(f"UNRUN: 모르는 case {case} (있는 것: {', '.join(sorted(cases))})")
        return UNRUN
    passed, fails = 0, []
    for n in names:
        try:
            ok, out = cases[n]()
        except Exception as e:  # noqa: BLE001 — self-test 는 예외도 실패로 센다
            ok, out = False, [f"예외 {type(e).__name__}: {e}"]
        if ok:
            passed += 1
        else:
            fails.append(n)
            print(f"  FAIL {n}")
            for x in out[:6]:
                print(f"       {x[:220]}")
    print(f"self-test {passed}/{len(names)} passed")
    return PASS if not fails else FAIL


def main() -> int:
    ap = argparse.ArgumentParser(description="A/B 원장 — 수집·채점·판정 (exit 0 PASS · 1 FAIL · 2 UNRUN)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--case", help="self-test 사례 하나만")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("snapshot", help="메모리·세션 상태 스냅샷 (arm×run 시작·종료, 기준 1회)")
    p.add_argument("--out", required=True)
    p.add_argument("--watch", action="append", default=[], help="이름=경로 (반복)")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("input", help="run 시작 전 fixture 저장소 커밋 기록")
    p.add_argument("--root", required=True)
    p.add_argument("--fixture", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--plugin-root", required=True, help="이 run 이 --plugin-dir 로 쓸 플러그인 사본 — 시작 신원을 남긴다")
    p.add_argument("--plugin-source", required=True, help="사본의 원본 트리(B=FZ_BASE_TREE · C=FZ_TREE) — 사본 충실도를 대조한다")
    p.set_defaults(func=cmd_input)

    p = sub.add_parser("collect", help="run 1건을 원천에서 읽어 원장에 한 행 추가")
    p.add_argument("--ledger", required=True)
    p.add_argument("--workflow", required=True, choices=("fz-plan", "fz-review", "fz-peer-review"))
    p.add_argument("--arm", required=True)
    p.add_argument("--run", type=int, required=True)
    p.add_argument("--order", type=int, required=True, help="전역 실행 순서 — 교차 순서 판정 입력")
    p.add_argument("--phase", required=True)
    p.add_argument("--release")
    p.add_argument("--run-id")
    p.add_argument("--fixture", required=True)
    p.add_argument("--transcript", required=True, help="Lead transcript (.jsonl)")
    p.add_argument("--artifact", action="append", help="최종 산출물 (반복) — wall 끝점")
    p.add_argument("--input-root", help="fixture 저장소 (run 뒤 커밋을 읽는다)")
    p.add_argument("--input-json", required=True, help="`input` 이 run 전에 쓴 입력 신원(필수 — 없으면 입력을 증명 못 한다)")
    p.add_argument("--state-pristine", required=True)
    p.add_argument("--state-start", required=True)
    p.add_argument("--state-end", required=True)
    p.add_argument("--gpt-log", action="append", help="GPT 스트림 로그 (자동 탐지 외 추가)")
    p.add_argument("--gpt-log-dir", action="append", help="run 구간에 쓰인 *.stream.log 를 찾을 폴더 (반복)")
    p.add_argument("--evidence-dir", help="하네스 반환 사본 폴더 (기본: 원장 옆 evidence/)")
    p.add_argument("--tasks-dir", action="append", help="run 직후 복사한 하네스 tasks/*.output 폴더 (반복)")
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("recollect", help="기록된 원천에서 다시 수집 (계측기 버전이 바뀐 뒤)")
    p.add_argument("--ledger", required=True)
    p.add_argument("--run-id")
    p.set_defaults(func=cmd_recollect)

    p = sub.add_parser("score", help="산출물을 라벨·채점표로 채점")
    p.add_argument("--ledger", required=True)
    p.add_argument("--fixtures-root", default=os.path.join(os.path.dirname(SCRIPT_DIR), "tests", "fixtures", "quality"))
    p.add_argument("--run-id")
    p.add_argument("--verdicts", help="blind-unpack 출력 (blinded=true)")
    p.set_defaults(func=cmd_score)

    p = sub.add_parser("blind-pack", help="가린 검증자 꾸러미 — run_id·arm·경로를 지운 후보·계획 본문")
    p.add_argument("--ledger", required=True)
    p.add_argument("--fixtures-root", default=os.path.join(os.path.dirname(SCRIPT_DIR), "tests", "fixtures", "quality"))
    p.add_argument("--out", required=True)
    p.add_argument("--run-id", action="append")
    p.add_argument("--salt", help="anon id 소금(기본 무작위 — 재현 테스트에만 고정)")
    p.set_defaults(func=cmd_blind_pack)

    p = sub.add_parser("blind-unpack", help="검증자 판정(anon) → run_id 기준 판정 파일")
    p.add_argument("--pack", required=True)
    p.add_argument("--verdicts", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_blind_unpack)

    p = sub.add_parser("judge", help="판정")
    p.add_argument("--ledger", required=True)
    p.add_argument("--phase", choices=PHASES)
    p.add_argument("--workflows")
    p.add_argument("--workflow")
    p.add_argument("--arm", default="C")
    p.add_argument("--release")
    p.add_argument("--min-runs", type=int, default=2)
    p.add_argument("--runs", type=int, default=1, help="release-smoke 의 C run 수")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--effort", default=DEFAULT_EFFORT)
    p.add_argument("--require-complete", action="store_true", help="(항상 적용 — 명시용. 미완주 run 은 언제나 무효)")
    p.add_argument("--plugin-sha")
    p.add_argument("--verify-sources", help=",".join(SOURCE_KINDS))
    p.add_argument("--require", help=",".join(IMPLEMENTED))
    p.add_argument("--envs", help="(미구현 — S27)")
    p.add_argument("--options-on", action="store_true", help="(미구현 — S28b)")
    p.add_argument("--require-passed", help="(미구현 — S28c)")
    p.set_defaults(func=cmd_judge)

    p = sub.add_parser("show", help="원장 요약")
    p.add_argument("--ledger", required=True)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("verify-evidence", help="(미구현 — S27)")
    p.set_defaults(func=cmd_verify_evidence)

    a, extra = ap.parse_known_args()
    if extra and getattr(a, "func", None) is not cmd_verify_evidence:
        ap.error(f"모르는 인자 {extra}")
    if a.self_test:
        return self_test(a.case)
    if not getattr(a, "func", None):
        ap.print_help()
        return UNRUN
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
