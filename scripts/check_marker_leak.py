#!/usr/bin/env python3
# diff-parse: hunk-state — `diff --git` 헤더 구간과 `@@` hunk 를 구분해 hunk 안 `+` 줄만 추가 줄로 센다
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 저장소 · 파일만 읽는다.
"""check_marker_leak.py — 대상 저장소 diff 의 추가 주석 줄에 fz 문서 마커가 새었는지 본다.

왜(F-175): fz 문서의 마커 어휘(⛔ · ⭐ · **강조**)가 팀 코드 주석으로 새어 팀원이 21줄을 되돌렸다. 그 저장소에서
`⛔` 를 쓰는 Swift 파일은 839개 중 8개였다 — 저장소 관례가 아니었다. 처방은 주석을 줄이는 것이 아니라 어휘 경계다:
fz 마커는 fz 자산 안에서만 쓰고, 대상 저장소의 주석은 그 저장소 표기(Swift 면 `- Warning:` 같은 DocC)를 따른다.

판정: `git diff -U0 <base>` 의 추가 줄 중 코드 파일(.md · .txt 제외)의 **주석 안**에 마커가 있고, 그 마커를 쓰는
같은 확장자 추적 파일이 저장소에서 10% 미만이면 보고한다(관례면 통과). 문자열 리터럴 속 마커는 주석이 아니다.

사용: check_marker_leak.py --repo <대상 저장소> --base <ref> | --self-test
exit: 0 누출 0 · 1 누출 있음(파일:줄 · 마커 · 저장소 N/M) · 2 UNRUN(git 아님 · ref 를 못 풂 — ⛔ 통과 아님)
출력: self-test 는 케이스마다 `PASS <셀>`(FZ_SELFTEST_LIST=1)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OK, LEAK, UNRUN = 0, 1, 2
MARKERS = ("⛔", "⭐", "✅", "⚠️")
BOLD = re.compile(r"\*\*[^*\n]+\*\*")
PROSE_EXT = {".md", ".markdown", ".txt", ".rst"}
HASH_COMMENT_EXT = {".py", ".sh", ".rb", ".yaml", ".yml", ".toml", ".pl", ".r"}
CONVENTION = 0.10


def git(repo: Path, *a) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *a], capture_output=True, text=True, errors="replace")


def comment_part(line: str, ext: str) -> str | None:
    """줄의 주석 부분 — 없으면 None. 문자열 리터럴 안의 `//` · `#` 는 여는 표지로 보지 않는다(따옴표 짝 세기)."""
    openers = ("#",) if ext in HASH_COMMENT_EXT else ("//", "/*", "*")
    s = line.lstrip()
    if s.startswith(openers):
        return s
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote and line[i - 1] != "\\":
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ext in HASH_COMMENT_EXT and ch == "#":
            return line[i:]
        if ext not in HASH_COMMENT_EXT and line.startswith("//", i):
            return line[i:]
    return None


def markers_in(text: str) -> list[str]:
    out = [m for m in MARKERS if m in text]
    if BOLD.search(text):
        out.append("**강조**")
    return out


def added_lines(repo: Path, base: str):
    d = git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", base, "--")
    if d.returncode != 0:
        raise RuntimeError(d.stderr.strip()[:160])
    path, in_hunk, n = None, False, 0
    for ln in d.stdout.split("\n"):
        if ln.startswith("diff --git "):
            path, in_hunk = None, False
            continue
        if not in_hunk:
            if ln.startswith("+++ "):
                tgt = ln[4:]
                path = None if tgt == "/dev/null" else (tgt[2:] if tgt.startswith("b/") else tgt)
            elif ln.startswith("@@"):
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", ln)
                in_hunk, n = True, int(m.group(1)) if m else 0
            continue
        if ln.startswith("@@"):
            m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)", ln)
            n = int(m.group(1)) if m else 0
        elif ln.startswith("+"):
            if path:
                yield path, n, ln[1:]
            n += 1


def usage_ratio(repo: Path, ext: str, marker: str, cache: dict) -> tuple[int, int]:
    """(마커를 쓰는 같은 확장자 추적 파일 수, 같은 확장자 추적 파일 수) — base 가 아니라 지금 트리 기준(보수적: 이번 추가분도 센다)."""
    key = (ext, marker)
    if key not in cache:
        files = [f for f in git(repo, "ls-files", "-z").stdout.split("\0") if f.endswith(ext)]
        needle = "**" if marker == "**강조**" else marker
        hit = 0
        for f in files:
            try:
                if needle in (repo / f).read_text(encoding="utf-8", errors="replace"):
                    hit += 1
            except OSError:
                continue
        cache[key] = (hit, len(files))
    return cache[key]


def run(repo: Path, base: str) -> int:
    if git(repo, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode != 0:
        print(f"UNRUN: git 저장소가 아니거나 기준 ref 를 풀지 못했다 — {repo} · {base} (⛔ 통과 아님)")
        return UNRUN
    leaks, cache, seen = [], {}, 0
    try:
        for path, n, text in added_lines(repo, base):
            ext = os.path.splitext(path)[1].lower()
            if ext in PROSE_EXT or not ext:
                continue
            seen += 1
            part = comment_part(text, ext)
            if part is None:
                continue
            for mk in markers_in(part):
                hit, total = usage_ratio(repo, ext, mk, cache)
                if total and hit / total >= CONVENTION:
                    continue
                leaks.append(f"{path}:{n}: 주석에 fz 마커 {mk} — 저장소 {ext} 파일 {hit}/{total} 이 쓴다(관례 아님) · 그 저장소 표기로 바꾼다")
    except RuntimeError as e:
        print(f"UNRUN: git diff 실패 — {e} (⛔ 통과 아님)")
        return UNRUN
    for x in leaks:
        print(f"LEAK {x}")
    print(f"marker-leak: 추가 코드 줄 {seen} · 누출 {len(leaks)}")
    return LEAK if leaks else OK


def self_test() -> int:
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    def case(name, base_files: dict, add: dict, want: int):
        nonlocal passed
        with tempfile.TemporaryDirectory(prefix="fz-marker-leak-") as d:
            r = Path(d)
            g = lambda *a: subprocess.run(["git", "-C", d, "-c", "user.email=t@t", "-c", "user.name=t", *a], capture_output=True)
            for rel, body in base_files.items():
                (r / rel).parent.mkdir(parents=True, exist_ok=True)
                (r / rel).write_text(body, encoding="utf-8")
            if any(g(*a).returncode for a in (("init", "-q"), ("add", "-A"), ("commit", "-qm", "base"))):
                fails.append(f"{name}: 픽스처 git 준비 실패")
                return
            for rel, body in add.items():
                (r / rel).parent.mkdir(parents=True, exist_ok=True)
                with open(r / rel, "a", encoding="utf-8") as fh:
                    fh.write(body)
            g("add", "-A")
            with open(os.devnull, "w") as null:
                old, sys.stdout = sys.stdout, null
                try:
                    rc = run(r, "HEAD")
                finally:
                    sys.stdout = old
        if rc == want:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(f"{name}: exit {rc} (기대 {want})")

    base = {f"Sources/F{i}.swift": f"let v{i} = {i}\n" for i in range(12)}
    case("f175-marker-in-added-comment", base, {"Sources/F0.swift": "// ⛔ 이 값은 바뀌면 안 된다\n"}, LEAK)
    case("f175-trailing-comment-bold", base, {"Sources/F1.swift": "let y = 2 // **반드시** 2\n"}, LEAK)
    case("f175-docc-warning-ok", base, {"Sources/F0.swift": "/// - Warning: 이 값은 바뀌면 안 된다\n"}, OK)
    case("f175-string-literal-ok", base, {"Sources/F0.swift": 'let s = "⛔ // 표시"\n'}, OK)
    case("f175-prose-file-ok", base, {"docs/a.md": "⛔ 문서는 대상이 아니다\n"}, OK)
    conv = dict(base, **{f"Sources/F{i}.swift": f"// ⛔ 관례\nlet v{i} = {i}\n" for i in range(3)})
    case("f175-repo-convention-ok", conv, {"Sources/F5.swift": "// ⛔ 관례를 따른다\n"}, OK)
    with tempfile.TemporaryDirectory() as d:
        with open(os.devnull, "w") as null:
            old, sys.stdout = sys.stdout, null
            try:
                rc = run(Path(d), "HEAD")
            finally:
                sys.stdout = old
        if rc == UNRUN:
            passed += 1
            if listing:
                print("PASS f175-not-a-repo-unrun")
        else:
            fails.append(f"f175-not-a-repo-unrun: exit {rc} (기대 {UNRUN})")

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", type=Path)
    ap.add_argument("--base")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.repo or not a.base:
        print("UNRUN: --repo 와 --base 가 필요하다 (⛔ 통과 아님)")
        return UNRUN
    return run(a.repo, a.base)


if __name__ == "__main__":
    sys.exit(main())
