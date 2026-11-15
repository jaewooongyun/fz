#!/usr/bin/env python3
"""removal_history.py — 어떤 줄을 지운 커밋을 찾는다(F-043).

왜: "이 문구는 언제 · 왜 빠졌나" 를 기억이나 지금 트리만 보고 답했다(재관측 F-492 · F-502) — 지금 트리에 없다는 것은
    처음부터 없었다는 뜻이 아니다. `git log -S` 는 그 문자열 개수가 바뀐 커밋을 넣은 것 · 지운 것 모두 준다. 그래서 커밋마다
    부모와 개수를 비교해 줄어든 커밋만 남긴다.

사용: removal_history.py <repo> <file> --text <줄>   → 지운 커밋마다 `<sha12>\t<YYYY-MM-DD>\t<제목>` (최근 것 먼저)
        <file> 은 저장소 루트 기준 경로 · <줄> 은 글자 그대로 찾는다(정규식 아님)
      removal_history.py --self-test
exit: 0 — 이력이 없으면 빈 출력 + 0 · 2 UNRUN(저장소 아님 · git 실패 — ⛔ 통과 아님 · 빈 출력과 다르다)
⛔ 이름이 바뀐 파일은 따라가지 않는다 — 이름을 바꾼 커밋 앞은 옛 경로로 다시 묻는다.
Python 3.9 stdlib 전용.
"""
# lint:no-root-anchor — 대상 저장소는 인자로 받는다(파일 위치로 플러그인 루트를 추론하지 않는다)
from __future__ import annotations

import argparse
import contextlib
import io
import os
import subprocess
import sys
import tempfile

ISOLATE = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")   # 바깥 훅 환경이 -C 대상을 덮지 않게 한다


class Unrun(Exception):
    pass


def git(repo: str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ISOLATE}
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, env=env)


def _count(repo: str, rev: str, path: str, text: str) -> int:
    p = git(repo, "show", f"{rev}:{path}")
    return p.stdout.count(text) if p.returncode == 0 else 0   # 그 판에 파일이 없다(첫 커밋의 부모 · 삭제) = 0개


def removals(repo: str, path: str, text: str) -> list:
    """[(sha, 날짜, 제목)] — 부모보다 그 문자열이 적어진 커밋만."""
    p = git(repo, "log", "-S", text, "--format=%H%x09%ad%x09%s", "--date=short", "--", path)
    if p.returncode != 0:
        raise Unrun((p.stderr.strip().splitlines() or ["git log 실패"])[0])
    out = []
    for ln in p.stdout.splitlines():
        sha, date, subj = ln.split("\t", 2)
        if _count(repo, sha, path, text) < _count(repo, sha + "^", path, text):
            out.append((sha, date, subj))
    return out


def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(bool(ok))
        print(f"PASS {name}" if ok else f"FAIL {name} — {got}")

    with tempfile.TemporaryDirectory() as t:
        repo = os.path.join(t, "r")
        os.mkdir(repo)
        git(repo, "init", "-q")
        cfg = ("-c", "user.email=t@t", "-c", "user.name=t", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false")

        def commit(body: str, subject: str) -> None:
            with open(os.path.join(repo, "a.md"), "w", encoding="utf-8") as fh:
                fh.write(body)
            git(repo, "add", "a.md")
            git(repo, *cfg, "commit", "-qm", subject)

        commit("KEEP\nGONE line\n", "add both")
        commit("KEEP\nGONE line\nOTHER\n", "touch other")
        commit("KEEP\nOTHER\n", "drop gone line")
        got = [s for _sha, _d, s in removals(repo, "a.md", "GONE line")]
        case("r3-f043-removal-commit-listed — 그 줄을 지운 커밋만 낸다(넣은 커밋 · 무관한 커밋 제외)", got == ["drop gone line"], got)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([repo, "a.md", "--text", "NEVER THERE"])
        case("r3-f043-no-history-empty — 이력이 없으면 빈 출력 + exit 0", (rc, buf.getvalue()) == (0, ""), (rc, buf.getvalue()))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main([t, "a.md", "--text", "GONE line"])
        case("removal-history-unrun — 저장소가 아니면 exit 2 + UNRUN(빈 출력과 구별)", rc == 2 and buf.getvalue().startswith("UNRUN"),
             (rc, buf.getvalue()))
    print(f"self-test {sum(results)}/{len(results)} passed (removal_history)")
    return 0 if all(results) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo", nargs="?")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--text")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    if not (a.repo and a.file and a.text):
        ap.error("<repo> <file> --text <줄> 이 모두 필요하다")
    try:
        rows = removals(a.repo, a.file, a.text)
    except Unrun as e:
        print(f"UNRUN: {e} (⛔ 이력 없음과 다르다)")
        return 2
    for sha, date, subj in rows:
        print(f"{sha[:12]}\t{date}\t{subj}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
