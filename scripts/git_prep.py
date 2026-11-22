#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 저장소 · 폴더만 다룬다.
# diff-parse: not-a-diff — `startswith("-")` · `startswith("+")` 는 인자 값이 옵션 · 강제 refspec 꼴인지 가리는 데만 쓴다. diff 를 파싱하지 않는다
"""git_prep.py — 워크플로 준비 단계의 git 호출 셋(고정 트리 · 원격 가져오기 · 종료 전 상태 조회)을 인자를 검사한 뒤 돈다.

왜: 소비자 스킬이 이 호출들을 `Bash(git -C * archive *)` · `Bash(tar -xf - -C *)` · `Bash(git fetch *)` 로 사전 승인했다.
`*` 는 공백을 넘어 맞아서 앞 와일드카드는 인자에 `archive` 가 든 다른 부명령(쓰기 포함)을, 끝 와일드카드는 `--output=<경로>` ·
`--upload-pack=<명령>` 같은 쓰기 · 실행 옵션을 함께 사전 승인했다. 종료 전 `git -C <경로> status --porcelain` 은 맞출 패턴이 쓰기
부명령에도 맞아 사전 승인하지 않았고, 그래서 호출마다 묻고 비대화형 세션에서는 돌지 못했다. 이 스크립트는 세 호출을 정해진 꼴로만
돌리고 다른 인자는 실행 전에 거부한다 — 소비자는 이미 가진 `Bash(python3 */scripts/*)` 로 부른다.

부명령 (값은 `--이름 값` 두 토큰 꼴만 받는다 — `--이름=값` · 줄임 · `--` · 여분 인자는 거부):
  tree   --repo <절대 git 루트> --sha <16진 7~64자> --into <절대 기존 폴더>
         `git -C <repo> archive --prefix=swarm-tree-<sha>/ <sha> | tar -xf - -C …` 를 두 프로세스 종료 코드를 모두 보며 돈다 —
         셸 파이프의 종료 코드는 tar 의 것이라 git 실패(없는 sha)를 가린다(빈 입력에 tar 는 0 이다). into 안 임시 폴더에 다 푼
         뒤에만 `<into>/swarm-tree-<sha>` 로 옮기고 그 경로를 한 줄 낸다 — 그래서 그 경로가 이미 있으면 다 풀린 트리다(다시 풀지
         않고 경로를 낸다). 하위 폴더에서 돈 archive 는 그 폴더만 담으므로 repo 는 git 루트여야 한다.
  fetch  --repo <절대 경로> --remote <등록된 원격 이름> [--ref <이름>]…
         `git -C <repo> fetch -- <remote> [<ref>…]` 를 GIT_TERMINAL_PROMPT=0 으로 돈다 — 인증을 물을 수 없는 세션에서 멈추지 않는다.
         ref 는 `git check-ref-format --allow-onelevel` 을 통과하고 `+` 로 시작하지 않는 이름만 받는다(refspec · 리비전 식은 거부).
  status --repo <절대 경로>
         `git -C <repo> status --porcelain` 의 출력과 종료 코드를 그대로 낸다 — 비0 은 clean 이 아니라 측정 실패다.
  --self-test  세 부명령을 옛 명령(스킬 · 가이드가 적던 꼴)과 같은 임시 저장소 · 로컬 원격에서 나란히 돌려 종료 코드 · 진단 · 결과를 대조한다

exit: 0 성공 · 10 인자 거부('-' 로 시작하거나 빈 값 · 모르는 인자 · 상대 경로 · 꼴이 틀린 sha · ref) · 11 사전조건 실패(git 저장소 ·
      루트 아님 · into 없음 · 등록 안 된 원격) · 12 실행 실패(git · tar 비0 — git 의 진단은 그대로 stderr 에 남는다) · status 는 git 의
      종료 코드 그대로. 10~12 는 git 자신의 종료 코드(1 · 128 · 129)와 겹치지 않게 골랐다
      --self-test: 0 전건 통과 · 1 실패 · 2 미실행(git · tar · bash 부재 · 임시 저장소 준비 실패 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

OK, REJECT, PRECONDITION, FAILED = 0, 10, 11, 12
SHA_RE = re.compile(r"[0-9a-f]{7,64}")   # SHA-1(40) · SHA-256(64) 저장소 둘 다 · 리비전 식(HEAD~1)은 받지 않는다
# 부명령 → (꼭 줄 인자, 여러 번 줄 수 있는 인자)
SPEC = {
    "tree": (("--repo", "--sha", "--into"), ()),
    "fetch": (("--repo", "--remote"), ("--ref",)),
    "status": (("--repo",), ()),
}
PATH_ARGS = ("--repo", "--into")


def say(msg: str) -> None:
    print(f"git_prep: {msg}", file=sys.stderr)


def parse(argv: list[str]):
    """(부명령, {인자: 값 | [값…]}) 또는 거부 사유(str)."""
    if not argv or argv[0] not in SPEC:
        return f"부명령은 {' · '.join(SPEC)} 중 하나다: {argv[0] if argv else '(없음)'}"
    need, many = SPEC[argv[0]]
    opts: dict = {}
    rest = argv[1:]
    for i in range(0, len(rest), 2):
        key = rest[i]
        if key not in need and key not in many:
            return f"모르는 인자: {key}"
        if i + 1 >= len(rest):
            return f"{key} 에 값이 없다"
        val = rest[i + 1]
        if not val or val.startswith("-"):
            return f"{key} 값이 비었거나 '-' 로 시작한다: {val!r}"
        if key in many:
            opts.setdefault(key, []).append(val)
        elif key in opts:
            return f"{key} 를 두 번 줬다"
        else:
            opts[key] = val
    missing = [k for k in need if k not in opts]
    if missing:
        return f"빠진 인자: {' '.join(missing)}"
    for k in PATH_ARGS:
        if k in opts and not os.path.isabs(opts[k]):
            return f"{k} 는 절대 경로여야 한다: {opts[k]}"
    return argv[0], opts


def tree(repo: str, sha: str, into: str) -> int:
    if not SHA_RE.fullmatch(sha):
        say(f"거부 — --sha 는 16진 7~64자다(리비전 식 · 옵션 꼴 아님): {sha!r}")
        return REJECT
    top = subprocess.run(["git", "-C", repo, "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE, universal_newlines=True)
    if top.returncode != 0:   # git 의 진단은 stderr 로 그대로 흐른다
        say(f"사전조건 — git 저장소가 아니다: {repo}")
        return PRECONDITION
    if os.path.realpath(top.stdout.strip()) != os.path.realpath(repo):
        say(f"사전조건 — git 루트가 아니다(루트: {top.stdout.strip()})")
        return PRECONDITION
    if not os.path.isdir(into):
        say(f"사전조건 — --into 폴더가 없다: {into}")
        return PRECONDITION
    name = f"swarm-tree-{sha}"
    dest = os.path.join(into, name)
    if os.path.lexists(dest):
        if os.path.isdir(dest) and not os.path.islink(dest):
            print(dest)
            return OK
        say(f"사전조건 — {dest} 가 있는데 폴더가 아니다")
        return PRECONDITION
    tmp = tempfile.mkdtemp(prefix=".swarm-tree-", dir=into)
    try:
        arc = subprocess.Popen(["git", "-C", repo, "archive", f"--prefix={name}/", sha], stdout=subprocess.PIPE)
        try:
            ext = subprocess.run(["tar", "-xf", "-", "-C", tmp], stdin=arc.stdout)
        finally:
            arc.stdout.close()
            arc_rc = arc.wait()
        if arc_rc != 0 or ext.returncode != 0:
            say(f"실행 실패 — git archive exit {arc_rc} · tar exit {ext.returncode}")
            return FAILED
        os.rename(os.path.join(tmp, name), dest)
    except OSError as e:
        say(f"실행 실패 — {e}")
        return FAILED
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(dest)
    return OK


def fetch(repo: str, remote: str, refs: list[str]) -> int:
    for ref in refs:   # 앞 `+` 는 ref 이름에 허용되지만 fetch 인자로는 강제 refspec 이다
        if ref.startswith("+") or subprocess.run(["git", "check-ref-format", "--allow-onelevel", ref]).returncode != 0:
            say(f"거부 — --ref 는 ref 이름이다(refspec · 리비전 식 아님): {ref!r}")
            return REJECT
    known = subprocess.run(["git", "-C", repo, "remote"], stdout=subprocess.PIPE, universal_newlines=True)
    if known.returncode != 0:
        say(f"사전조건 — git 저장소가 아니다: {repo}")
        return PRECONDITION
    names = known.stdout.split()
    if remote not in names:
        say(f"사전조건 — 등록된 원격이 아니다: {remote} (등록된 원격: {' · '.join(names) or '없음'})")
        return PRECONDITION
    rc = subprocess.run(["git", "-C", repo, "fetch", "--", remote, *refs], env=dict(os.environ, GIT_TERMINAL_PROMPT="0")).returncode
    if rc != 0:
        say(f"실행 실패 — git fetch exit {rc}")
        return FAILED
    return OK


def status(repo: str) -> int:
    return subprocess.run(["git", "-C", repo, "status", "--porcelain"]).returncode


def self_test() -> int:
    tools = {t: shutil.which(t) for t in ("git", "tar", "bash")}
    if not all(tools.values()):
        print(f"self-test 미실행 — 없는 명령: {' · '.join(t for t, p in tools.items() if not p)} (⛔ 통과 아님)")
        return 2
    me = [sys.executable, os.path.abspath(__file__)]
    q = shlex.quote
    results: list[bool] = []

    def cell(name, ok, detail):   # 셀 줄은 이름만 — 대조 내용은 다음 줄에 들여 쓴다
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}\n    {detail}")

    with tempfile.TemporaryDirectory(prefix="fz-git-prep-") as tmp_root:
        d = os.path.realpath(tmp_root)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=os.path.join(d, "home"), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
                   GIT_ALLOW_PROTOCOL="file", GIT_CEILING_DIRECTORIES=os.path.dirname(d),
                   GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid")

        def run(argv, e=None):
            p = subprocess.run(argv, cwd=d, env=e or env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
            return p.returncode, p.stdout, p.stderr

        def new(*args, e=None):   # 래퍼
            return run(me + list(args), e)

        def old(cmd):             # 옛 명령 — 스킬 · 가이드가 적던 꼴 그대로(셸 파이프 포함)
            return run(["bash", "-c", cmd])

        def git(*args):
            rc, out, err = run(["git", *args])
            if rc != 0:
                raise RuntimeError(f"git {' '.join(args)} — {err.strip()}")
            return out.strip()

        def mk(name):
            p = os.path.join(d, name)
            os.makedirs(p)
            return p

        def write(path, text, mode=None):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            if mode:
                os.chmod(path, mode)

        def fatal(err):           # git 진단의 첫 `fatal:` 줄 — 래퍼가 옛 명령과 같은 진단을 남기는지 본다
            return next((ln for ln in err.splitlines() if ln.startswith("fatal:")), "")

        def files(root):
            got = {}
            for dp, _, fn in os.walk(root):
                for f in fn:
                    with open(os.path.join(dp, f), "rb") as fh:
                        got[os.path.relpath(os.path.join(dp, f), root)] = fh.read()
            return got

        try:
            os.mkdir(env["HOME"])
            src, bare, cl1, cl2, plain = (os.path.join(d, n) for n in ("src", "up.git", "cl1", "cl2", "plain"))
            os.mkdir(plain)
            git("init", "-q", src)
            git("-C", src, "symbolic-ref", "HEAD", "refs/heads/main")
            os.mkdir(os.path.join(src, "dir"))
            write(os.path.join(src, "a.txt"), "alpha\n")
            write(os.path.join(src, "dir", "b c.txt"), "beta\n")
            for n, text in (("c1", None), ("c2", "alpha 2\n")):
                if text:
                    write(os.path.join(src, "a.txt"), text)
                git("-C", src, "add", "-A")
                git("-C", src, "commit", "-qm", n)
            git("clone", "-q", "--bare", src, bare)
            for c in (cl1, cl2):
                git("clone", "-q", "-o", "upstream", bare, c)
            sha = git("-C", cl1, "rev-parse", "HEAD")
            shim, log = mk("shim"), os.path.join(d, "shim.log")
            # shim — git 은 호출마다 GIT_TERMINAL_PROMPT 와 인자를 적고, SHIM_ARCHIVE_EXIT 가 있으면 archive 가 다 쓴 뒤 그 값으로 끝난다.
            #        tar 는 SHIM_TAR_EXIT 가 있으면 다 푼 뒤 그 값으로 끝난다 — 출력이 멀쩡해도 종료 코드만이 실패를 알리는 경우다
            write(os.path.join(shim, "git"), f'#!/bin/sh\nprintf "%s|%s\\n" "${{GIT_TERMINAL_PROMPT-unset}}" "$*" >> {q(log)}\n'
                  f'{q(tools["git"])} "$@"; rc=$?\nif [ "$3" = archive ] && [ -n "${{SHIM_ARCHIVE_EXIT-}}" ]; then exit "$SHIM_ARCHIVE_EXIT"; fi\nexit $rc\n', 0o755)
            write(os.path.join(shim, "tar"), f'#!/bin/sh\n{q(tools["tar"])} "$@"; rc=$?\n'
                  'if [ -n "${SHIM_TAR_EXIT-}" ]; then exit "$SHIM_TAR_EXIT"; fi\nexit $rc\n', 0o755)
        except (OSError, RuntimeError) as e:
            print(f"self-test 미실행 — 임시 저장소 준비 실패: {e} (⛔ 통과 아님)")
            return 2

        def shim_env(**kw):
            return dict(env, PATH=shim + os.pathsep + env.get("PATH", ""), **kw)

        name = f"swarm-tree-{sha}"

        def old_tree(repo, s, into):
            return old(f"git -C {q(repo)} archive --prefix=swarm-tree-{q(s)}/ {q(s)} | tar -xf - -C {q(into)}")

        # ── tree ──────────────────────────────────────────────────────────────
        ia, ib = mk("ia"), mk("ib")
        dest = os.path.join(ib, name)
        orc, _, _ = old_tree(cl1, sha, ia)
        nrc, nout, _ = new("tree", "--repo", cl1, "--sha", sha, "--into", ib)
        line_ok, same = nout == dest + "\n", os.path.isdir(dest) and bool(files(dest)) and files(os.path.join(ia, name)) == files(dest)
        cell("tree-ok", orc == 0 and nrc == 0 and line_ok and same and os.listdir(ib) == [name],
             f"옛 명령 exit {orc} · 래퍼 exit {nrc} · 경로 한 줄 {line_ok} · 옛 명령 트리와 바이트 일치 {same} · 임시 폴더 남김 없음")
        rc2, out2, _ = new("tree", "--repo", cl1, "--sha", sha, "--into", ib)
        cell("tree-existing-reused", rc2 == 0 and out2 == nout and os.listdir(ib) == [name] and files(dest) == files(os.path.join(ia, name)),
             f"다 풀린 트리가 이미 있다 → exit {rc2} · 같은 경로 · 다시 풀지 않는다")

        ic, xfile = mk("ic"), os.path.join(d, "x.tar")
        bad = (f"--output={xfile}", "-x", "HEAD~1")
        nrcs = [new("tree", "--repo", cl1, "--sha", v, "--into", ic)[0] for v in bad]
        clean = not os.path.exists(xfile) and os.listdir(ic) == []
        orcs = [old_tree(cl1, v, mk(f"ic-old-{i}"))[0] for i, v in enumerate(bad)]
        cell("tree-rejects-option-sha", nrcs == [REJECT] * 3 and clean,
             f"`--output=…` · `-x` · `HEAD~1` → 래퍼 exit {nrcs} · 만든 파일 없음 {clean} (옛 명령 exit {orcs})")

        rel = mk("rel")
        rc, _, _ = new("tree", "--repo", cl1, "--sha", sha, "--into", "rel")
        cell("tree-rejects-relative-into", rc == REJECT and os.listdir(rel) == [], f"--into rel → exit {rc} · cwd 아래에 풀지 않는다")

        iw = mk("iw")
        orc, _, oerr = old_tree(plain, sha, mk("iw-old"))
        nrc, _, nerr = new("tree", "--repo", plain, "--sha", sha, "--into", iw)
        f = fatal(oerr)
        cell("tree-wrong-repo", nrc == PRECONDITION and bool(f) and f in nerr and os.listdir(iw) == [],
             f"git 저장소 아님 — 옛 명령 exit {orc} · 래퍼 exit {nrc} · git 진단 그대로 {bool(f) and f in nerr}")

        isd = mk("isd")
        rc, _, _ = new("tree", "--repo", os.path.join(cl1, "dir"), "--sha", sha, "--into", isd)
        cell("tree-rejects-subdir-repo", rc == PRECONDITION and os.listdir(isd) == [], f"git 루트의 하위 폴더 → exit {rc}")

        ig, ig2, ghost = mk("ig"), mk("ig2"), "deadbeef" * 5
        orc, _, oerr = old_tree(cl1, ghost, mk("ig-old"))
        nrc, _, nerr = new("tree", "--repo", cl1, "--sha", ghost, "--into", ig)
        f = fatal(oerr)
        rc2, _, _ = new("tree", "--repo", cl1, "--sha", sha, "--into", ig2, e=shim_env(SHIM_ARCHIVE_EXIT="1"))
        cell("tree-git-fail-detected", nrc == FAILED and bool(f) and f in nerr and os.listdir(ig) == [] and rc2 == FAILED and os.listdir(ig2) == [],
             f"없는 sha — 옛 파이프 exit {orc}(tar 의 것) · 래퍼 exit {nrc} · git 진단 그대로 {bool(f) and f in nerr} · "
             f"트리를 다 쓰고 비0 으로 끝난 git → 래퍼 exit {rc2} · 남긴 것 없음")

        it = mk("it")
        rc, _, _ = new("tree", "--repo", cl1, "--sha", sha, "--into", it, e=shim_env(SHIM_TAR_EXIT="2"))
        cell("tree-tar-fail-detected", rc == FAILED and os.listdir(it) == [], f"다 풀고 비0 으로 끝난 tar → exit {rc} · 남긴 것 없음")

        gone = os.path.join(d, "no-such-dir")
        rc, _, _ = new("tree", "--repo", cl1, "--sha", sha, "--into", gone)
        cell("tree-into-missing", rc == PRECONDITION and not os.path.exists(gone), f"없는 --into → exit {rc}")

        # ── fetch (로컬 원격 · GIT_TERMINAL_PROMPT=0) ─────────────────────────────
        try:
            write(os.path.join(src, "a.txt"), "alpha 3\n")
            git("-C", src, "commit", "-qam", "c3")
            git("-C", bare, "fetch", "-q", src, "+refs/heads/main:refs/heads/main")
            want = git("-C", bare, "rev-parse", "main")
        except (OSError, RuntimeError) as e:
            print(f"self-test 미실행 — 원격 갱신 실패: {e} (⛔ 통과 아님)")
            return 2
        orc, _, _ = old(f"git -C {q(cl1)} fetch upstream")
        nrc, _, _ = new("fetch", "--repo", cl2, "--remote", "upstream")
        got = [run(["git", "-C", c, "rev-parse", "upstream/main"])[1].strip() for c in (cl1, cl2)]
        cell("fetch-ok", orc == 0 and nrc == 0 and got == [want, want], f"옛 명령 exit {orc} · 래퍼 exit {nrc} · 두 clone 의 upstream/main = 원격 main {got == [want, want]}")

        orc, _, _ = old(f"git -C {q(cl1)} fetch upstream main")
        nrc, _, _ = new("fetch", "--repo", cl2, "--remote", "upstream", "--ref", "main")
        got = [run(["git", "-C", c, "rev-parse", "FETCH_HEAD"])[1].strip() for c in (cl1, cl2)]
        cell("fetch-ref-ok", orc == 0 and nrc == 0 and got == [want, want], f"--ref main — 옛 명령 exit {orc} · 래퍼 exit {nrc} · FETCH_HEAD 같음 {got == [want, want]}")

        orc, _, oerr = old(f"git -C {q(cl1)} fetch upstream nosuch")
        nrc, _, nerr = new("fetch", "--repo", cl2, "--remote", "upstream", "--ref", "nosuch")
        f = fatal(oerr)
        cell("fetch-unknown-ref", orc != 0 and nrc == FAILED and bool(f) and f in nerr,
             f"원격에 없는 ref — 옛 명령 exit {orc} · 래퍼 exit {nrc} · git 진단 그대로 {bool(f) and f in nerr}")

        mark = os.path.join(d, "upload-pack-ran")
        rc, _, _ = new("fetch", "--repo", cl2, "--remote", f"--upload-pack=touch {mark}; git-upload-pack")
        cell("fetch-rejects-option-remote", rc == REJECT and not os.path.exists(mark), f"--remote --upload-pack=… → exit {rc} · 실행된 명령 없음")

        refs0 = run(["git", "-C", cl2, "for-each-ref"])[1]
        rcs = [new("fetch", "--repo", cl2, "--remote", "upstream", "--ref", r)[0] for r in ("-x", "HEAD~1", "main:evil", "+main")]
        same_refs = run(["git", "-C", cl2, "for-each-ref"])[1] == refs0
        cell("fetch-rejects-bad-ref", rcs == [REJECT] * 4 and same_refs, f"`-x` · `HEAD~1` · `main:evil` · `+main` → exit {rcs} · ref 불변 {same_refs}")

        orc, _, _ = old(f"git -C {q(cl1)} fetch nosuch")
        rcs = [new("fetch", "--repo", cl2, "--remote", r)[0] for r in ("nosuch", bare)]
        cell("fetch-unknown-remote", orc != 0 and rcs == [PRECONDITION] * 2, f"등록 안 된 이름 · 저장소 경로 → 래퍼 exit {rcs} (옛 명령 exit {orc})")

        orc, _, oerr = old(f"git -C {q(plain)} fetch upstream")
        nrc, _, nerr = new("fetch", "--repo", plain, "--remote", "upstream")
        f = fatal(oerr)
        cell("fetch-wrong-repo", nrc == PRECONDITION and bool(f) and f in nerr,
             f"git 저장소 아님 — 옛 명령 exit {orc} · 래퍼 exit {nrc} · git 진단 그대로 {bool(f) and f in nerr}")

        e = shim_env()
        e.pop("GIT_TERMINAL_PROMPT", None)
        write(log, "")
        rc, _, _ = new("fetch", "--repo", cl2, "--remote", "upstream", e=e)
        with open(log, encoding="utf-8") as fh:
            seen = [ln.split("|", 1)[0] for ln in fh.read().splitlines() if " fetch -- " in ln]
        cell("fetch-no-terminal-prompt", rc == OK and seen == ["0"], f"호출자 env 에 값이 없어도 git fetch 는 GIT_TERMINAL_PROMPT={seen}")

        # ── status ────────────────────────────────────────────────────────────
        write(os.path.join(cl1, "a.txt"), "changed\n")
        write(os.path.join(cl1, "new file.txt"), "n\n")
        orc, oout, _ = old(f"git -C {q(cl1)} status --porcelain")
        nrc, nout, _ = new("status", "--repo", cl1)
        cell("status-ok", orc == 0 and nrc == 0 and nout == oout and nout.strip() != "", f"옛 명령과 exit · 출력 같음 ({len(nout.splitlines())}줄)")
        orc, oout, oerr = old(f"git -C {q(plain)} status --porcelain")
        nrc, nout, nerr = new("status", "--repo", plain)
        cell("status-not-repo-nonzero", orc != 0 and nrc == orc and nerr == oerr and nout == oout,
             f"git 저장소 아님 — 옛 명령 exit {orc} · 래퍼 exit {nrc} · 진단 같음 {nerr == oerr}")

        # ── 인자 꼴 ───────────────────────────────────────────────────────────
        ie = mk("ie")
        rcs = [new(*a)[0] for a in (["status", "--repo", cl1, "extra"], ["status", "--repo", cl1, "--"], ["status", "--repo", cl1, "--repo", cl1],
                                     ["status", f"--repo={cl1}"], ["tree", "--repo", cl1, "--sha", sha, "--into", ie, "--force"],
                                     ["fetch", "--repo", cl2, "--remote", "upstream", "--prune"], ["fetch", "--repo", cl2, "--remote", "upstream", "--ref"],
                                     ["fetch", "--repo", cl2, "--remote", "upstream", "--upload-pack", "x"], ["status", "--repo", cl1, "--porcelain", "v2"])]
        cell("extra-arg-rejected", rcs == [REJECT] * 9 and os.listdir(ie) == [], f"여분 인자 · `--` · 중복 · `--이름=값` · 끝 옵션 · 값 없음 · 값 든 모르는 인자 → exit {rcs}")
        rcs = [new(*a)[0] for a in (["status"], ["tree", "--repo", cl1, "--sha", sha], ["fetch", "--repo", cl2])]
        cell("missing-arg-rejected", rcs == [REJECT] * 3 and os.listdir(ie) == [], f"꼭 줄 인자 없음 → exit {rcs}")
        rcs = [new(*a)[0] for a in ([], ["clean", "-fd"], ["archive", "--repo", cl1], ["--self-test", "x"])]
        cell("unknown-subcommand-rejected", rcs == [REJECT] * 4, f"부명령 없음 · 모르는 부명령 → exit {rcs}")
        rcs = [new(*a)[0] for a in (["status", "--repo", "cl1"], ["status", "--repo", "-C"], ["tree", "--repo", "cl1", "--sha", sha, "--into", ie],
                                     ["fetch", "--repo", "-x", "--remote", "upstream"])]
        cell("repo-rejects-option-or-relative", rcs == [REJECT] * 4 and os.listdir(ie) == [], f"상대 · '-' 로 시작하는 --repo → exit {rcs}")

    passed = sum(results)
    print(f"self-test {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


def main(argv: list[str]) -> int:
    if argv == ["--self-test"]:
        return self_test()
    got = parse(argv)
    if isinstance(got, str):
        say(f"거부 — {got}")
        return REJECT
    cmd, o = got
    try:
        if cmd == "tree":
            return tree(o["--repo"], o["--sha"], o["--into"])
        if cmd == "fetch":
            return fetch(o["--repo"], o["--remote"], o.get("--ref", []))
        return status(o["--repo"])
    except OSError as e:   # git · tar 실행 파일 부재 등
        say(f"실행 실패 — {e}")
        return FAILED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
