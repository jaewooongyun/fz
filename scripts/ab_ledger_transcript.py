# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 형제 모듈 import 와 계측기 해시에 이 파일의 디렉토리만 쓴다.
# diff-parse: not-a-diff — `startswith("-")` 는 셸 명령 토큰의 플래그 판별이다(sed -i · --out-dir · --out= · 스크립트 argv).
#   `startswith("--------")` 는 GPT 스트림 로그 배너의 구분선이다. diff 줄 접두를 판정하는 곳은 없다.
"""ab_ledger_transcript.py — A/B 원장 계측기의 한 부분: Lead transcript 해석 — 끝점(최종 산출물 기록 이벤트) · GPT 호출 · Workflow 반환.

진입점 · 설계 · 측정 규약은 ab_ledger.py 머리말에 있다(이 파일은 그 실행 코드를 나눠 담는다).
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import pathlib
import re
import shlex

import fz_wf_metrics as wfm   # noqa: E402 — 형제 모듈(Workflow 폴더 집계)
from ab_ledger_base import (iso, iter_jsonl, norm_model, read_json, secs, sha_text)


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


FSTR_WRITE_RE = re.compile(r"""open\(\s*f(['"])(.*?)\1\s*,\s*['"][wax]|Path\(\s*f(['"])(.*?)\3\s*\)\s*\.\s*write_(?:text|bytes)\(""")


def _fstring_argv_targets(body, args):
    """쓰기 호출의 f-string 경로를 argv 값으로 채운 경로들 — 자리가 **모두** `x = sys.argv[N]`(튜플 풀기 포함)에 묶인 이름일 때만.
    실측(R-D S36 run 1): `W, ver = sys.argv[1], sys.argv[2]` 뒤 `open(f'{W}/plan-{ver}.md', 'w')` 를 `render_plan.py $W final` 로 불렀다 —
    명령 · 본문 어디에도 산출물 이름 글자가 없어 끝점을 놓쳤다. ⛔ 자리 하나라도 argv 밖(다른 변수 · 식 · 형식 지정)이면 풀지 않는다."""
    bind = {}
    for names, vals in ARGV_BIND_RE.findall(body):
        for v, n in zip(re.split(r"\s*,\s*", names), re.findall(r"\[(\d+)\]", vals)):
            bind[v] = int(n)
    out = []
    for m in FSTR_WRITE_RE.finditer(body):
        tpl = m.group(2) if m.group(2) is not None else m.group(4)
        slots = re.findall(r"\{([^{}]*)\}", tpl)
        if not slots or any(s not in bind or not 1 <= bind[s] <= len(args) for s in slots):
            continue
        out.append(re.sub(r"\{(\w+)\}", lambda x: args[bind[x.group(1)] - 1], tpl))
    return out


def _mv_pairs(cmd, cwd):
    """`mv [-옵션] 원본 대상` 쌍 — 셸 변수 · for 값을 편 명령마다 본다. 피연산자가 정확히 둘이고 변수가 다 풀린 것만."""
    out = []
    for c in _expand_vars(cmd):
        bases = _cd_bases(c, cwd) or [""]
        for seg in _segments(_shell_part(c)):
            while seg and seg[0] in ("do", "then", "else", "{"):
                seg = seg[1:]
            if not seg or os.path.basename(seg[0]) != "mv":
                continue
            ops = [t for t in seg[1:] if not t.startswith("-")]
            if len(ops) == 2 and "$" not in "".join(ops):
                out.append(tuple(x if os.path.isabs(x) else os.path.join(bases[0], x) for x in ops))
    return list(dict.fromkeys(out))


def _follow_moves(path, t, moves):
    """시각 t 뒤(결과 시각 ≥ t)에 `path` 를 옮긴 mv 를 차례로 따라간 마지막 경로. moves = [(결과 시각, 원본, 대상)]."""
    for ts, s, d in sorted(moves):
        if ts >= t and _same_path(s, path):
            path, t = d, ts
    return path


def _heredoc_scripts(cmd, cwd):
    """Bash heredoc 으로 만든 `.py` 스크립트 → [(정규화 경로, 본문)] — `cat > X.py <<'D'` · `cat <<'D' > X.py` · `tee X.py <<D`.
    실측(R-C C2 plan-feature): `cat > /tmp/abt2001_fix_final2.py <<'EOF' … EOF` 를 같은 명령에서 바로 불렀고, 그 스크립트가
    재수집 전에 디스크에서 사라져 끝점을 놓쳤다(wall 3949→3765s · mtime Δ 184s). 대상 경로는 같은 명령의 대입·cd 로 푼다 — 못 풀면 뺀다."""
    out, lines, i = [], cmd.split("\n"), 0
    while i < len(lines):
        line, i = lines[i], i + 1
        m = HEREDOC_RE.search(line)
        if not m:
            continue
        body = []
        while i < len(lines) and lines[i].strip() != m.group(2):   # _shell_part 와 같은 끝 판정
            body.append(lines[i])
            i += 1
        i += 1
        for t in (x.group(2) for x in REDIRECT_RE.finditer(line)):
            p = _resolve_vars(t, cmd, cwd) if t.endswith(".py") else "$"
            if "$" in p:
                continue
            for b in ([""] if os.path.isabs(p) else _cd_bases(cmd, cwd) or [""]):
                out.append((os.path.normpath(os.path.join(b, p)), "\n".join(body)))
    return out


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
        for p_ in _fstring_argv_targets(body, args):
            if any(_same_path(x, a) for x in ([p_] if os.path.isabs(p_) else [os.path.join(b, p_) for b in bases])):
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
        for p in [args[n - 1] for n in _argv_written(body) if 1 <= n <= len(args)] + _fstring_argv_targets(body, args):
            cands = [p] if os.path.isabs(p) else [os.path.join(b, p) for b in bases]
            if any(_same_path(x, a) for x in cands):
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
        calls = []
        for view in _cmd_views(str(u["input"].get("command") or "")):   # ⛔ 변수로 부른 래퍼(`"$X" exec`)도 호출이다
            cmd = _shell_part(view)
            # ⛔ 한 명령의 호출을 **모두** 센다(F-335 ⑪) — 첫 매치만 보면 `( A … ) & ( B … ) & wait` 의 B 가 계수 · 배너 대조에서 빠진다.
            #    완료 판정(알림 · 도구 결과)은 Bash 단위라 같은 명령의 호출들이 나눠 쓴다
            calls = list(GPT_CALL_RE.finditer(cmd))
            if calls:
                break
        for call in calls:
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

    # ⛔ 호출이 끝난 뒤 로그를 옮겼으면 옮긴 곳을 따라간다 — 실측(R-D S36 run 1): 2라운드 전에
    #    `for f in gpt-verify gpt-verify-gates; do mv $W/$f.json.stream.log $W/$f.r1.json.stream.log; done` 로 옮겨 직접 경로엔
    #    2라운드 로그만 남았고, 1라운드 두 호출이 미연결됐다. 끝난 뒤(결과 시각 ≥ t1)의 mv 만 본다 — 쓰는 중에 옮긴 것은 따라가지 않는다
    moves = [(res["ts"].timestamp(), s, d) for u in tool_uses if u["name"] == "Bash"
             for res in [results.get(u["id"])] if res and not res["is_error"] and res["ts"]
             for s, d in _mv_pairs(str(u["input"].get("command") or ""), u["cwd"])]
    for g in gpt:
        if moves and g["out"] and "$" not in g["out"] and g["t1"] is not None:
            g["log"] = _follow_moves(g["out"] + ".stream.log", g["t1"], moves)

    # 최종 산출물 기록 이벤트 — 산출물을 가리키는 도구 호출 중 **파일 mtime 에 가장 가까운** 결과 시각.
    #   ⛔ '마지막으로 가리킨 호출' 을 쓰면 쓰기 뒤의 읽기(cat·Read)가 끝점이 된다. 경로를 변수로 쓴
    #      파이썬 heredoc 도 잡으려고 basename 까지 후보로 보고, mtime 으로 쓰기를 고른다(wall 은 transcript 시계).
    py_scripts = {}   # Lead 가 Write 로 만든 .py 본문 — 곧 지워도 transcript 에 남는다
    for u in tool_uses:
        fp = str(u["input"].get("file_path") or "") if u["name"] == "Write" else ""
        if fp.endswith(".py"):
            py_scripts[os.path.normpath(fp if os.path.isabs(fp) else os.path.join(u["cwd"] or "", fp))] = str(u["input"].get("content") or "")
    # Bash heredoc 으로 만든 스크립트 — ⛔ 디스크에 **없을 때만** 대체 본문으로 쓴다(있으면 디스크가 정본) · Write 본문이 먼저다.
    #   같은 경로를 여러 번 만들었으면 호출 시각(tool_use) **이전**의 가장 최근 본문에 묶는다 — 같은 명령에서 만들고 바로 부른 것 포함
    py_heredocs = collections.defaultdict(list)
    for i, u in enumerate(tool_uses):
        if u["name"] == "Bash":
            for p, body in _heredoc_scripts(str(u["input"].get("command") or ""), u["cwd"]):
                if not os.path.isfile(p):
                    py_heredocs[p].append((u["ts"], i, body))

    def scripts_at(i, ts):
        hd = {}
        for p, xs in py_heredocs.items():
            prior = [x for x in xs if x[1] <= i and (x[0] is None or ts is None or x[0] <= ts)]
            if prior:
                hd[p] = max(prior, key=lambda x: (x[0].timestamp() if x[0] else float("-inf"), x[1]))[2]
        return {**hd, **py_scripts} if hd else py_scripts
    art = []
    for a in artifacts:
        mtime = None
        try:
            mtime = os.path.getmtime(a)
        except OSError:
            pass
        cands = []
        for i, u in enumerate(tool_uses):
            res = results.get(u["id"])
            if not res or res["is_error"] or not res["ts"]:
                continue      # ⛔ 완료되지 않았거나 실패한 호출은 '기록' 이 아니다
            hit = False
            if u["name"] in WRITE_TOOLS:
                fp = u["input"].get("file_path") or u["input"].get("notebook_path")
                hit = bool(fp) and _same_path(fp if os.path.isabs(fp) else os.path.join(u["cwd"], fp), a)
            elif u["name"] == "Bash":
                hit = _bash_writes(str(u["input"].get("command") or ""), a, u["cwd"], scripts_at(i, u["ts"]))
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
            "bash_arg_chars": sum(len(str(u["input"].get("command") or "")) for u in bash),
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
