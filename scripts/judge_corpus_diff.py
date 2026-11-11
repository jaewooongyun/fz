#!/usr/bin/env python3
# lint:no-root-anchor — 대조할 두 트리(--old-root · --new-root)와 표는 인자로 받는다(플러그인 루트를 추론하지 않는다)
"""실사용 입력 양성 대조 — 판정기를 고칠 때 옛 판과 새 판을 실제 입력 코퍼스에 함께 돌려, 판정이 달라진 범주를 양방향으로 센다.

적대 검토는 「통과로 뒤집히는 입력」을 찾도록 지시받아 흔한 입력의 과잉 거부를 체계적으로 찌르지 않는다. 실사용 입력을 두 판에
같이 돌리면 회귀(흔한 꼴의 오판)와 설계 공백(옛 판이 우연히 잡던 쓰기)이 함께 드러난다.

판정면 둘:
  bash   fz-guard `bash_write`(읽기 · 대상 있는 쓰기 · 대상 미상 쓰기) + `gpt_review_invoked` — Bash 명령 코퍼스
  fence  check_comment_worthy `code_idents` 의 `UNLEXED`(못 읽은 코드 표식) · 식별자 집합 — 코드 펜스 코퍼스
코퍼스는 Claude Code transcript 폴더(jsonl)에서 뽑는다. ⛔ 경로는 인자로만 받는다 — 코퍼스를 저장소에 넣지 않는다.
⛔ 원문을 파일에 쓰지 않는다. --out 표에는 범주 · 건수 · 판정한 파일의 blob sha 만 간다. 원문 표본은 --examples 로 stdout 에만 낸다.
범주 이름은 고정 어휘(명령 동사 표 · 토크나이저 Unknown 사유 · 펜스 언어 표)로만 만든다 — 프로젝트 고유 이름이 새지 않는다.

사용:
  judge_corpus_diff.py run --old-root DIR --new-root DIR --transcripts DIR [--surface bash|fence] [--last N] [--examples K]
                           [--out TSV] [--dispositions TSV]
  judge_corpus_diff.py check-reviewed TSV --root DIR   (exit 0 = 머리의 new sha 가 --root 트리와 같고 모든 행에 처분 · 근거가 있다)
  judge_corpus_diff.py --self-test
--dispositions: `범주<TAB>처분<TAB>근거` 줄 — 같은 범주의 --out 행에 채운다. 처분 = intended · old-false-positive · accepted-overblock.
"""
# lint:no-root-anchor — 판정할 두 트리는 --old-root · --new-root 인자로 받는다(파일 위치로 플러그인 루트를 추론하지 않는다)
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

SURFACES = {
    "bash": ("mods/fz-guard/hooks/guard.py", "mods/fz-guard/hooks/shell_tokens.py"),
    "fence": ("scripts/check_comment_worthy.py", "scripts/shell_tokens.py"),
}
DISPOSITIONS = ("intended", "old-false-positive", "accepted-overblock")
VERBS = frozenset(("rm", "mv", "cp", "touch", "mkdir", "ln", "chmod", "rsync", "tar", "unzip", "install", "patch", "truncate",
                   "tee", "sed", "git", "dd", "xargs", "find", "eval", "source", "cd", "pushd"))
INTERP = re.compile(r"^(?:python[0-9.]*|node|bash|sh|zsh|dash|perl|ruby)$")
LANGS = frozenset(("swift", "kotlin", "kt", "java", "js", "javascript", "ts", "typescript", "jsx", "tsx", "python", "py", "sh",
                   "bash", "zsh", "shell", "console", "objc", "c", "cpp", "go", "rust", "ruby", "json", "yaml", "diff", "text"))
QUIET = ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty")
FENCE_RE = re.compile(r"```(\w*)[^\n]*\n(.*?)```", re.S)


def blob_sha(path: pathlib.Path) -> str:
    b = path.read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


# ── 코퍼스 ──────────────────────────────────────────────────────────

def corpus(transcripts: str, surface: str, last: int) -> list:
    """transcript 폴더의 최근 `last` 개 jsonl 에서 Bash 명령(또는 코드 펜스 (언어, 본문))을 중복 없이 모은다."""
    files = sorted(pathlib.Path(transcripts).expanduser().glob("*.jsonl"), key=lambda p: p.stat().st_mtime)[-last:]
    out, seen = [], set()

    def add(x):
        k = json.dumps(x, ensure_ascii=False)
        if k not in seen:
            seen.add(k)
            out.append(x)

    def texts(v):
        if isinstance(v, str):
            yield v
        elif isinstance(v, dict):
            for x in v.values():
                yield from texts(x)
        elif isinstance(v, list):
            for x in v:
                yield from texts(x)
    for f in files:
        with f.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if surface == "bash" and '"Bash"' not in line or surface == "fence" and "```" not in line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                for c in ((o.get("message") or {}).get("content") or []) if isinstance(o, dict) else []:
                    if not isinstance(c, dict):
                        continue
                    if surface == "bash":
                        cmd = (c.get("input") or {}).get("command") if c.get("type") == "tool_use" and c.get("name") == "Bash" else None
                        if isinstance(cmd, str) and cmd.strip():
                            add(cmd)
                    elif c.get("type") in ("text", "tool_use"):
                        for t in texts(c.get("text") if c.get("type") == "text" else c.get("input")):
                            for m in FENCE_RE.finditer(t):
                                add([m.group(1).lower(), m.group(2)])
    return out


# ── 판정(하위 프로세스 — 두 트리의 같은 이름 모듈이 섞이지 않게) ────────────────────

def _load(path: pathlib.Path, name: str):
    import importlib.util
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _features_bash(st, cmd) -> list:
    if st is None:
        return []
    toks = st.lex(cmd)
    if st.is_unknown(toks):
        return ["unknown:" + re.sub(r"[^a-z0-9-]", "", str(getattr(toks, "why", "")).split(":")[0])[:40]]
    fs = set()
    for ws, rs, depth in st.simple_commands(toks):
        names = [os.path.basename(getattr(w, "text", "")) for w in ws]
        fs.update("cmd:" + n for n in names[:1] if n in VERBS)
        if any(INTERP.match(n) for n in names):
            if any(re.fullmatch(r"-[A-Za-z]*[ce][A-Za-z]*", getattr(w, "text", "")) for w in ws):
                fs.add("interp-dash-c")
            if any(getattr(r, "heredoc", None) for r in rs):
                fs.add("interp-heredoc")
        for r in rs:
            if getattr(r, "op", "") in (">", ">>", ">|", "&>", "&>>", "<>"):
                tg = r.target
                fs.add("quiet-redirect" + ("-nested" if depth else "") if getattr(tg, "text", "") in QUIET
                       else "redirect-var" if getattr(tg, "expands", False) else "redirect-nested" if depth else "redirect")
    return sorted(fs)


# 범주의 주된 원인 — 특징 조합이 아니라 하나로 줄인다(검토할 범주 수를 줄인다). 앞이 강한 쓰기 신호다
PRIMARY = ("unknown:", "interp-heredoc", "interp-dash-c", "redirect-var", "redirect-nested", "redirect",
           "cmd:cp", "cmd:mv", "cmd:rm", "cmd:touch", "cmd:tee", "cmd:sed", "cmd:mkdir", "cmd:ln", "cmd:chmod", "cmd:rsync",
           "cmd:tar", "cmd:unzip", "cmd:install", "cmd:patch", "cmd:truncate", "cmd:dd", "quiet-redirect-nested", "quiet-redirect",
           "cmd:", "lang:")


def primary(fs) -> str:
    for p in PRIMARY:
        hit = sorted(f for f in fs if f.startswith(p))
        if hit:
            return hit[0]
    return "-"


def worker(root: str, surface: str) -> int:
    """stdin 의 코퍼스(JSON 목록)를 `root` 트리의 판정기로 판정해 stdout 에 JSON 목록을 낸다."""
    items = json.load(sys.stdin)
    rel, tok_rel = SURFACES[surface]
    r = pathlib.Path(root)
    try:
        mod = _load(r / rel, "judged_" + surface)
    except Exception as e:  # noqa: BLE001 — 판정기를 못 부르면 전 항목이 측정 실패다(통과 아님)
        print(json.dumps({"error": f"load {rel}: {type(e).__name__}"}))
        return 3
    st = sys.modules.get("shell_tokens") if (r / tok_rel).is_file() else None
    out = []
    for it in items:
        try:
            if surface == "bash":
                w, tg = mod.bash_write(it)
                gp = mod.gpt_review_invoked(it) if hasattr(mod, "gpt_review_invoked") else None
                out.append({"v": ("read" if not w else "known" if tg else "unknown") + ("|gpt" if gp else ""),
                            "f": _features_bash(st, it)})
            else:
                lang, code = it
                un = getattr(mod, "UNLEXED", None)
                got = mod.code_idents(f"```{lang}\n{code}```")   # 소비자가 실제로 부르는 입구 — 언어별 분기까지 같은 길을 탄다
                ids = sorted(got - ({un} if un else set()))
                out.append({"v": "unlexed" if un and un in got else "lexed",
                            "ids": hashlib.sha1("\n".join(ids).encode()).hexdigest()[:12],
                            "f": ["lang:" + (lang if lang in LANGS else "other" if lang else "none")]})
        except Exception as e:  # noqa: BLE001 — 한 항목의 판정 예외는 그 항목의 판정값이다(조용히 빼지 않는다)
            out.append({"v": "error:" + type(e).__name__, "f": []})
    print(json.dumps(out))
    return 0


def judge(root: str, surface: str, items: list) -> list:
    p = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "_worker", root, surface], input=json.dumps(items),
                       capture_output=True, text=True, timeout=3600)
    try:
        got = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None
    except ValueError:
        got = None
    if not isinstance(got, list) or len(got) != len(items):
        raise SystemExit(f"측정 실패 — {root} 판정기 exit={p.returncode} {(p.stdout + p.stderr).strip()[-300:]}")
    return got


# ── 대조 · 기록 ─────────────────────────────────────────────────────

def classes(items, old, new, surface):
    """(범주 → [항목 번호]) — 판정이 달라진 항목만. 범주 = 옛 판정→새 판정 + 새 판 특징(고정 어휘)."""
    out = collections.defaultdict(list)
    for k, (a, b) in enumerate(zip(old, new)):
        changed = a["v"] != b["v"] or (surface == "fence" and a.get("ids") != b.get("ids"))
        if changed:
            mark = "" if a["v"] != b["v"] else " ids-changed"
            out[f"{a['v']}->{b['v']}{mark} | {primary(b.get('f') or [])}"].append(k)
    return out


def header(surface, old_root, new_root, items):
    shas = lambda root: ",".join(f"{rel}:{blob_sha(pathlib.Path(root) / rel) if (pathlib.Path(root) / rel).is_file() else 'absent'}"
                                 for rel in SURFACES[surface])
    csha = hashlib.sha1(json.dumps(items, ensure_ascii=False).encode()).hexdigest()[:12]
    return f"# judge_corpus_diff surface={surface} new={shas(new_root)} old={shas(old_root)} corpus={len(items)} corpus_sha={csha}"


def load_dispositions(path):
    m = {}
    if path:
        for ln in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
            parts = ln.split("\t")
            if len(parts) == 3 and not ln.startswith("#"):
                m[parts[0]] = (parts[1], parts[2])
    return m


def cmd_run(a) -> int:
    items = corpus(a.transcripts, a.surface, a.last)
    if not items:
        print("측정 실패 — 코퍼스 0건(transcript 폴더 · --last 확인)")
        return 3
    old, new = judge(a.old_root, a.surface, items), judge(a.new_root, a.surface, items)
    cl = classes(items, old, new, a.surface)
    tot = lambda vs: collections.Counter(v["v"] for v in vs)
    print(f"surface={a.surface} corpus={len(items)} changed={sum(len(v) for v in cl.values())}")
    print("old", dict(tot(old)))
    print("new", dict(tot(new)))
    for key, ks in sorted(cl.items(), key=lambda kv: -len(kv[1])):
        print(f"{len(ks):6}  {key}")
        for k in ks[:a.examples]:
            x = items[k] if a.surface == "bash" else items[k][1]
            print("        e.g. " + x.replace("\n", "⏎")[:160])
    if a.out:
        disp = load_dispositions(a.dispositions)
        rows = [header(a.surface, a.old_root, a.new_root, items), "class\tcount\tdisposition\tnote"]
        rows += [f"{key}\t{len(ks)}\t{disp.get(key, ('', ''))[0]}\t{disp.get(key, ('', ''))[1]}"
                 for key, ks in sorted(cl.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
        pathlib.Path(a.out).write_text("\n".join(rows) + "\n", encoding="utf-8")
        miss = [r for r in rows[2:] if not r.split("\t")[2]]
        print(f"--out {a.out} — 범주 {len(rows) - 2} · 처분 빈칸 {len(miss)}")
    return 0


def check_reviewed(path, root) -> list:
    """거부 사유 목록 — 비면 통과. 머리의 new sha 가 지금 트리와 같고, 모든 행의 처분이 표 안 값이며 근거가 비지 않는다."""
    try:
        lines = pathlib.Path(path).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        return [f"표를 읽지 못했다: {type(e).__name__}"]
    m = re.match(r"^# judge_corpus_diff surface=(\w+) new=(\S+) old=\S+ corpus=(\d+) corpus_sha=\w+$", lines[0] if lines else "")
    if not m or len(lines) < 2 or lines[1] != "class\tcount\tdisposition\tnote":
        return ["머리 두 줄이 judge_corpus_diff --out 형식이 아니다"]
    probs = []
    if m.group(1) not in SURFACES or int(m.group(3)) == 0:
        probs.append("판정면 · 코퍼스 수가 잘못됐다")
    for ent in m.group(2).split(","):
        rel, _, sha = ent.rpartition(":")
        f = pathlib.Path(root) / rel
        if rel not in SURFACES.get(m.group(1), ()) or (blob_sha(f) if f.is_file() else "absent") != sha:
            probs.append(f"{rel} sha 가 지금 트리와 다르다 — 판정기가 바뀐 뒤 다시 대조하지 않았다")
    for ln in lines[2:]:
        p = ln.split("\t")
        if len(p) != 4 or p[2] not in DISPOSITIONS or not p[3].strip():
            probs.append(f"처분 · 근거 없음: {p[0][:80]}")
    return probs


# ── self-test ──────────────────────────────────────────────────────

def self_test() -> int:
    res = []

    def case(name, ok, got=""):
        res.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        for side, body in (("old", "def bash_write(c):\n    return ('>' in c, [])\n"
                                   "def gpt_review_invoked(c):\n    return False\n"),
                           ("new", "def bash_write(c):\n    return ('rm ' in c or ('>' in c and '/dev/null' not in c), ['x'] if 'rm ' in c else [])\n"
                                   "def gpt_review_invoked(c):\n    return 'review' in c\n")):
            g = t / side / "mods/fz-guard/hooks/guard.py"
            g.parent.mkdir(parents=True)
            g.write_text(body, encoding="utf-8")
        tr = t / "tr"
        tr.mkdir()
        cmds = ["ls a", "secretproj-tool > /dev/null", "rm secretproj.txt", "gpt review", "cat x > y"]
        with (tr / "s.jsonl").open("w", encoding="utf-8") as fh:
            for c in cmds + ["ls a"]:
                fh.write(json.dumps({"message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": c}}]}}) + "\n")
        items = corpus(str(tr), "bash", 5)
        old, new = judge(str(t / "old"), "bash", items), judge(str(t / "new"), "bash", items)
        cl = classes(items, old, new, "bash")
        got = {k: len(v) for k, v in cl.items()}
        case("r3-corpus-diff-both-directions — 쓰기→읽기 · 읽기→쓰기 · GPT 판정 변화를 모두 범주로 센다(중복 명령은 한 번)",
             len(items) == 5 and got == {"unknown->read | -": 1, "read->known | -": 1, "read->read|gpt | -": 1}, got)
        out, dsp = t / "o.tsv", t / "d.tsv"
        ns = argparse.Namespace(transcripts=str(tr), surface="bash", last=5, old_root=str(t / "old"), new_root=str(t / "new"),
                                examples=0, out=str(out), dispositions=None)
        cmd_run(ns)
        text = out.read_text(encoding="utf-8")
        case("r3-corpus-diff-out-has-no-raw-text — --out 표에 명령 원문(코퍼스 고유 낱말)이 없다",
             "secretproj" not in text and "class\tcount\tdisposition\tnote" in text, text[:200])
        empty = check_reviewed(out, t / "new")
        dsp.write_text("".join(f"{k}\tintended\t확인함\n" for k in got), encoding="utf-8")
        ns.dispositions = str(dsp)
        cmd_run(ns)
        filled = check_reviewed(out, t / "new")
        (t / "new/mods/fz-guard/hooks/guard.py").write_text("def bash_write(c):\n    return (False, [])\n", encoding="utf-8")
        stale = check_reviewed(out, t / "new")
        case("r3-corpus-diff-reviewed-binds-sha — 처분 빈칸은 거부 · 채우면 통과 · 판정기가 바뀌면(sha) 거부",
             bool(empty) and filled == [] and any("sha" in p for p in stale), (empty, filled, stale))
    print(f"self-test {sum(res)}/{len(res)} passed (judge_corpus_diff)")
    return 0 if all(res) else 1


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["_worker"]:
        return worker(argv[1], argv[2])
    if argv[:1] == ["--self-test"]:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--old-root", required=True)
    r.add_argument("--new-root", required=True)
    r.add_argument("--transcripts", required=True)
    r.add_argument("--surface", choices=sorted(SURFACES), default="bash")
    r.add_argument("--last", type=int, default=40)
    r.add_argument("--examples", type=int, default=0)
    r.add_argument("--out")
    r.add_argument("--dispositions")
    c = sub.add_parser("check-reviewed")
    c.add_argument("table")
    c.add_argument("--root", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return cmd_run(a)
    probs = check_reviewed(a.table, a.root)
    for p in probs:
        print("REJECT " + p)
    if not probs:
        print("OK 실사용 대조 표 — sha 일치 · 모든 범주 처분됨")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
