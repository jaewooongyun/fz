#!/usr/bin/env python3
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 파일과 그 파일이 속한 저장소만 읽는다.
"""check_applied_escapes.py — 적용한 파일에 새로 생긴 태그 모양 이스케이프(`<\\task-notification>`)를 찾는다(F-551).

왜: code-pair 의 changeset 검사(workflows/code-pair.js `changesetDefects`)는 적용 **전** 워커 자기보고만 잰다.
Lead 가 JSON 을 풀어 파일에 쓴 **뒤** 이중 이스케이프가 그대로 남았는지는 보지 못한다 — 그 흔적이 리뷰까지 갔다(F-551).
이 스크립트는 적용 뒤 파일을 직접 읽는다(fz-code 절차 4).

센다: `<` + 역슬래시 + 영문자로 시작하는 이름 + 공백 · `>` · `/` — 태그 모양만(code-pair.js `ESCAPE_RE` 와 같은 식).
세지 않는다(F-558): 정상 소스의 `<\\/`(JS 문자열 · 정규식의 `/<\\/div>/`) · `r"<\\w+>"` · `[^<\\n` 문자 클래스 · `<<\\EOF` heredoc.

사용: check_applied_escapes.py [--base REF] FILE... | --self-test
  --base REF  파일마다 REF 판(파일 폴더에서 `git show REF:./이름`)보다 **늘어난** 수만 센다. REF 에 없는 파일은 0 으로 본다
exit: 0 새 이스케이프 없음 · 1 있음(파일:줄 출력) · 2 입력 불가(파일 없음 · git 저장소 아님 · REF 없음 — ⛔ 통과 아님)
"""
import os
import re
import subprocess
import sys
import tempfile

ESCAPE_RE = re.compile(r"(?<![<^])<\\[A-Za-z][\w-]*(?=[\s>/])")


def count(text):
    return len(ESCAPE_RE.findall(text))


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def base_text(path, ref):
    """REF 판 본문. REF 에 없는 파일은 ''. 저장소 아님 · REF 없음은 None(입력 불가)."""
    d = os.path.dirname(os.path.abspath(path))
    if git(["rev-parse", "--git-dir"], d).returncode != 0:
        return None, f"git 저장소가 아니다: {d}"
    if git(["rev-parse", "--verify", "--quiet", ref + "^{commit}"], d).returncode != 0:
        return None, f"REF 를 찾지 못했다: {ref}"
    p = git(["show", f"{ref}:./{os.path.basename(path)}"], d)
    return (p.stdout.decode("utf-8", "replace") if p.returncode == 0 else ""), ""


def scan(files, ref=None, out=sys.stdout):
    found, bad = 0, []
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as e:
            bad.append(f"{f}: 읽기 실패 {e.strerror}")
            continue
        before = 0
        if ref:
            old, why = base_text(f, ref)
            if old is None:
                bad.append(why)
                continue
            before = count(old)
        added = count(text) - before
        if added <= 0:
            continue
        found += added
        hits = [f"{n}: {line.strip()[:120]}" for n, line in enumerate(text.split("\n"), 1) if ESCAPE_RE.search(line)]
        print(f"ESCAPE {f}: 태그 앞 이스케이프 {added}개 늘었다(현재 {count(text)} · 기준 {before}) — JSON 이중 이스케이프가 파일에 풀린 흔적(F-551)", file=out)
        for h in hits:
            print(f"  {f}:{h}", file=out)
    for b in bad:
        print(f"UNRUN {b} (⛔ 통과 아님)", file=out)
    if bad:
        return 2
    return 1 if found else 0


def self_test():
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    def check(name, cond, got):
        nonlocal passed
        if cond:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(name)
            print(f"FAIL {name}: {got}")

    class Sink:
        def __init__(self):
            self.text = ""

        def write(self, s):
            self.text += s

    with tempfile.TemporaryDirectory(prefix="fz-applied-escapes-") as d:
        def put(rel, body):
            p = os.path.join(d, rel)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            return p

        # 실제 저장소 — HEAD 판에는 없던 태그 앞 이스케이프가 적용 뒤 생겼다 / 이미 있던 것은 늘지 않았다
        env = dict(os.environ, GIT_AUTHOR_NAME="fixture-user", GIT_AUTHOR_EMAIL="t@t",
                   GIT_COMMITTER_NAME="fixture-user", GIT_COMMITTER_EMAIL="t@t")
        a = put("a.md", "head\n<task-notification>\n")
        b = put("b.md", "keep <\\task-notification> as is\n")
        for args in (["init", "-q"], ["add", "a.md", "b.md"], ["commit", "-q", "-m", "base"]):
            subprocess.run(["git"] + args, cwd=d, env=env, check=True, stdout=subprocess.DEVNULL)
        put("a.md", "head\n<\\task-notification>\n")
        put("c.md", "new file <\\system-reminder>\n")   # HEAD 에 없는 파일은 기준 0
        s = Sink()
        rc = scan([a, b], "HEAD", s)
        s2 = Sink()
        rc2 = scan([b], "HEAD", s2)
        s3 = Sink()
        rc3 = scan([os.path.join(d, "c.md")], "HEAD", s3)
        check("f551-applied-escape-flagged", rc == 1 and "a.md:2:" in s.text and "b.md" not in s.text and rc2 == 0 and rc3 == 1,
              f"rc {rc}/{rc2}/{rc3} · {s.text.strip()[:200]}")

        v = put("v.js", "const re = /<\\/div>/\nconst s = '<\\/script>'\nconst p = r\"<\\w+>\"\nconst c = /[^<\\n]+/\ncat <<\\EOF\n")
        s = Sink()
        check("valid-escapes-ignored", scan([v], None, s) == 0 and not s.text, s.text.strip()[:200])

        s = Sink()
        rc = scan([os.path.join(d, "no-such.md")], None, s)
        with tempfile.TemporaryDirectory(prefix="fz-applied-escapes-norepo-") as nd:
            q = os.path.join(nd, "x.md")
            with open(q, "w", encoding="utf-8") as fh:
                fh.write("x\n")
            s2 = Sink()
            rc2 = scan([q], "HEAD", s2)
        s3 = Sink()
        rc3 = scan([a], "no-such-ref", s3)
        check("unreadable-input-unrun", rc == 2 and rc2 == 2 and rc3 == 2 and "UNRUN" in s.text + s2.text + s3.text,
              f"rc {rc}/{rc2}/{rc3}")

    total = passed + len(fails)
    print(f"self-test {passed}/{total} passed")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    ref = None
    if argv[:1] == ["--base"]:
        if len(argv) < 2:
            print("usage: check_applied_escapes.py [--base REF] FILE... | --self-test", file=sys.stderr)
            return 2
        ref, argv = argv[1], argv[2:]
    if not argv:
        print("usage: check_applied_escapes.py [--base REF] FILE... | --self-test", file=sys.stderr)
        return 2
    return scan(argv, ref)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
