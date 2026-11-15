#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 diff 파일과 저장소만 읽는다.
# diff-parse: hunk-state — 파일 헤더(`---` · `+++`)는 `diff --git` 뒤 첫 `@@` 전에서만 읽는다. hunk 안의 `--- …` 는 '-- ' 로 시작하는 삭제 줄이다
"""check_review_diff.py — 리뷰에 넘길 diff 가 untracked 신규 파일을 빠뜨리지 않았는지 대조한다(F-270).

왜: `git diff` 는 추적하지 않는 신규 파일을 내지 않는다. 리뷰 diff 가 신규 파일을 빠뜨려 변경의 60% 가 검증 대상에서
누락됐다. fz-review 1단계는 신규 파일을 `git diff --no-index /dev/null {file}` 로 덧붙이라고 하지만 덧붙였는지 보는 검사가 없었다.

대조: 저장소 `git status --porcelain -z --untracked-files=all` 의 `??` 경로 집합 ⊆ diff 의 신규 파일 집합. 신규 파일은
`--- /dev/null` 다음 `+++ b/<경로>`, 또는 헤더의 `new file mode`(빈 파일 · 바이너리는 `---`/`+++` 짝이 없다)로 센다.
개수만 비교하면 다른 파일이 수를 채운다 — 경로로 본다. git 이 따옴표로 감싼 경로(`"b/\355…"` — core.quotePath)는 풀어서 비교한다.
리뷰 산출물(diff 파일 자신 · `--work-dir`)은 untracked 쪽에서 뺀다 — WORK_DIR 이 저장소 안이면 검사기가 자기 입력을 요구한다.

사용: check_review_diff.py --diff FILE --repo DIR [--work-dir DIR] | --self-test
exit: 0 신규 파일 전부 포함 · 1 빠진 신규 파일 있음(경로 출력) · 2 대조 불가(diff 를 못 읽음 · git 저장소 아님 — ⛔ 통과 아님)
"""
import argparse
import codecs
import os
import re
import subprocess
import sys
import tempfile


def untracked(repo):
    p = subprocess.run(["git", "-C", repo, "status", "--porcelain", "-z", "--untracked-files=all"],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        return None
    return {e[3:] for e in p.stdout.decode("utf-8", "surrogateescape").split("\0") if e.startswith("?? ")}


def _unquote(p):
    """git C-quote 를 푼다 — core.quotePath=true 면 비ASCII 경로가 `"b/\\355…"` 로 나온다(status -z 는 날 경로다)."""
    if len(p) >= 2 and p[0] == p[-1] == '"':
        return codecs.escape_decode(p[1:-1].encode("utf-8"))[0].decode("utf-8", "surrogateescape")
    return p


def _norm(path, top):
    """diff 헤더 경로 → 저장소 상대 경로. 절대경로(--no-index 에 절대경로를 준 경우)는 저장소 상대로 편다."""
    path = _unquote(path.strip())
    path = path[2:] if path.startswith("b/") else path
    if not path.startswith("/") and not os.path.lexists(os.path.join(top, path)) and os.path.lexists("/" + path):
        path = "/" + path                       # `diff --git` 줄은 절대경로의 첫 / 를 뺀다
    if path.startswith("/"):
        path = os.path.relpath(os.path.realpath(path), top)
    return os.path.normpath(path[2:] if path.startswith("./") else path)


def _git_b(rest):
    """`diff --git a/X b/X` 의 b 쪽 — 신규 파일은 a 와 b 가 같아 공백이 든 경로도 반으로 가른다. 못 가르면 None."""
    if rest.startswith('"'):
        m = re.match(r'("(?:\\.|[^"\\])*") ("(?:\\.|[^"\\])*")$', rest)
        return m.group(2) if m else None
    n = (len(rest) - 1) // 2
    return rest[n + 1:] if len(rest) % 2 == 1 and rest[n] == " " and rest[2:n] == rest[n + 3:] else None


BINARY_NEW = re.compile(r"^Binary files /dev/null and (.+) differ$")


def new_in_diff(text, repo):
    """신규 파일 경로 집합 — `--- /dev/null` 뒤 `+++ b/<경로>` · 헤더 `new file mode` · `Binary files /dev/null and …`."""
    out, prev_null, header, cur, newmode = set(), False, False, None, False
    top = os.path.realpath(repo)

    def flush():
        if newmode and cur:
            out.add(_norm(cur, top))

    for line in text.split("\n"):
        if line.startswith("diff --git "):
            flush()
            header, prev_null, newmode = True, False, False
            cur = _git_b(line[len("diff --git "):].rstrip("\t"))
            continue
        if line.startswith("@@"):
            header = False
        if not header:
            continue
        if line.startswith("new file mode "):
            newmode = True
            continue
        m = BINARY_NEW.match(line)
        if m:
            out.add(_norm(m.group(1), top))
            continue
        if line.startswith("--- "):
            prev_null = line[4:].strip() == "/dev/null"
            continue
        if line.startswith("+++ ") and prev_null:
            out.add(_norm(line[4:], top))
        prev_null = False
    flush()
    return out


def run(diff, repo, out=sys.stdout, work_dir=None):
    try:
        with open(diff, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError as e:
        print(f"UNRUN: diff 를 읽지 못했다 — {e} (⛔ 통과 아님)", file=out)
        return 2
    want = untracked(repo)
    if want is None:
        print(f"UNRUN: git 저장소가 아니다 — {repo} (⛔ 통과 아님)", file=out)
        return 2
    top = os.path.realpath(repo)
    skip = [os.path.realpath(diff)] + ([os.path.realpath(work_dir)] if work_dir else [])
    generated = {w for w in want if any(q == s or q.startswith(s + os.sep)
                                        for q in [os.path.realpath(os.path.join(top, w))] for s in skip)}
    want -= generated
    have = new_in_diff(text, repo)
    missing = sorted(want - have)
    for m in missing:
        print(f"MISSING {m} — untracked 신규 파일이 diff 에 없다(`git diff --no-index /dev/null {m}` 를 덧붙인다)", file=out)
    print(f"review-diff: untracked={len(want)} diff-new={len(have)} missing={len(missing)} generated-excluded={len(generated)}", file=out)
    return 1 if missing else 0


def self_test():
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    class Sink:
        def __init__(self):
            self.text = ""

        def write(self, s):
            self.text += s

    def check(name, cond, got):
        nonlocal passed
        if cond:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(name)
            print(f"FAIL {name}: {got}")

    env = dict(os.environ, GIT_AUTHOR_NAME="fixture-user", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="fixture-user", GIT_COMMITTER_EMAIL="t@t")
    with tempfile.TemporaryDirectory(prefix="fz-review-diff-") as d:
        repo = os.path.join(d, "repo")
        os.makedirs(os.path.join(repo, "c"))
        with open(os.path.join(repo, "a.txt"), "w") as fh:
            fh.write("a\n")
        for args in (["init", "-q"], ["add", "a.txt"], ["commit", "-q", "-m", "base"]):
            subprocess.run(["git"] + args, cwd=repo, env=env, check=True, stdout=subprocess.DEVNULL)
        for rel in ("b.txt", "c/d.txt"):
            with open(os.path.join(repo, rel), "w") as fh:
                fh.write("new\n")
        with open(os.path.join(repo, "a.txt"), "w") as fh:
            fh.write("a2\n")

        def diff_of(*news):
            parts = [subprocess.run(["git", "-C", repo, "diff"], stdout=subprocess.PIPE).stdout.decode()]
            for n in news:
                parts.append(subprocess.run(["git", "-C", repo, "diff", "--no-index", "/dev/null", n],
                                            stdout=subprocess.PIPE).stdout.decode())
            p = os.path.join(d, "diff-%d.patch" % len(news))
            with open(p, "w") as fh:
                fh.write("".join(parts))
            return p

        s1, s2, s3 = Sink(), Sink(), Sink()
        rc1 = run(diff_of("b.txt"), repo, s1)
        rc2 = run(diff_of("b.txt", "c/d.txt"), repo, s2)
        rc3 = run(diff_of(), d, s3)
        check("f270-untracked-missing", rc1 == 1 and "MISSING c/d.txt" in s1.text and "MISSING b.txt" not in s1.text and rc2 == 0,
              f"{rc1} {rc2} {s1.text.strip()}")
        fake = os.path.join(d, "hunk.patch")
        with open(fake, "w") as fh:
            fh.write("diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ b/a.txt\n@@ -1,2 +1,2 @@\n--- /dev/null\n+++ b/c/d.txt\n")
        check("hunk-lines-not-headers", new_in_diff(open(fake).read(), repo) == set(), new_in_diff(open(fake).read(), repo))
        # 빈 파일 · 바이너리(---/+++ 짝 없음) · 따옴표 경로(비ASCII) · 공백 경로 — 덧붙였으면 MISSING 이 아니다
        with open(os.path.join(repo, "empty.txt"), "w"):
            pass
        with open(os.path.join(repo, "img.png"), "wb") as fh:
            fh.write(b"\x89PNG\x00\x01")
        for rel in ("\ud55c\uae00.txt", "c/a b.txt"):
            with open(os.path.join(repo, rel), "w") as fh:
                fh.write("x\n")
        news = ("b.txt", "c/d.txt", "empty.txt", "img.png", "\ud55c\uae00.txt", "c/a b.txt")
        s5 = Sink()
        rc5 = run(diff_of(*news), repo, s5)
        check("f270-headerless-new-files", rc5 == 0 and "MISSING" not in s5.text, f"{rc5} {s5.text.strip()}")
        # WORK_DIR 이 저장소 안 — 검사기 입력(diff 파일)과 리뷰 산출물을 신규 소스로 요구하지 않는다
        wd = os.path.join(repo, "TICKET-1")
        os.makedirs(os.path.join(wd, "review"))
        os.makedirs(os.path.join(wd, "plan"))
        with open(os.path.join(wd, "plan", "plan-final.md"), "w") as fh:
            fh.write("plan\n")
        inside = os.path.join(wd, "review", "diff.patch")
        with open(diff_of(*news)) as src, open(inside, "w") as dst:
            dst.write(src.read())
        s6, s7 = Sink(), Sink()
        rc6 = run(inside, repo, s6, work_dir=wd)
        rc7 = run(inside, repo, s7)
        check("f270-workdir-artifacts-excluded", rc6 == 0 and "generated-excluded=2" in s6.text
              and rc7 == 1 and "MISSING TICKET-1/plan/plan-final.md" in s7.text and "review/diff.patch" not in s7.text,
              f"{rc6} {s6.text.strip()} / {rc7} {s7.text.strip()}")
        s4 = Sink()
        check("unreadable-or-not-repo-unrun", rc3 == 2 and run(os.path.join(d, "none.patch"), repo, s4) == 2, f"{rc3} {s3.text}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--diff", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--work-dir", help="리뷰 산출물 폴더 — 저장소 안이면 untracked 대조에서 뺀다")
    a = ap.parse_args(argv)
    return run(a.diff, a.repo, work_dir=a.work_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
