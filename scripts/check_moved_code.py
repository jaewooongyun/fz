#!/usr/bin/env python3
# diff-parse: hunk-state — `diff --git` 헤더 구간과 `@@` hunk 를 구분해 hunk 안 `+` 줄만 추가 줄로 센다
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 저장소 · 파일만 읽는다.
"""check_moved_code.py — 추가 hunk 의 코드가 BASE 트리에 이미 있으면 '이동 후보' 로 표시한다.

왜(F-078): 파일이 이동하면 diff 는 통째로 '신규' 로 보이고, 리뷰는 그것을 신규 코드로 읽었다. 신규성 판정 전에
'이 줄이 BASE 어딘가에 이미 있었나' 를 먼저 보면 이동 · 복사를 가를 수 있다.

판정: `git diff -U0 --no-renames BASE HEAD` 의 추가 줄 중(이름 바꾸기 감지를 끈다 — 유사도가 낮은 이동 · PR diff 는 감지가 안 걸려 '신규' 로 보인다) 코드 줄(앞뒤 공백 뗀 25자 이상 · 주석 · import 줄 제외)을 모아
BASE 트리의 줄(앞뒤 공백을 뗀 글자)과 정확히 같은지 본다. 파일마다 그런 줄이 5줄 이상이고 절반 이상이 BASE 에 있으면 MOVE-CANDIDATE.
⛔ 이동 후보 표시까지만 한다 — 신규성의 최종 판정(옮기면서 고친 줄 · 일부러 복사한 코드)은 사람이 한다.

두 축을 더 본다(같은 줄 판독 · 12자 이상 코드 줄):
- DUP-ADDED (F-172): 같은 변경의 추가 줄끼리 연속 3줄이 두 자리에 똑같이 나온다 — 방금 만든 헬퍼를 쓰지 않고 본문을 다시 적은 꼴이다.
  남의 코드 반복은 3회 임계를 쓰지만, 이번 변경이 만든 추상화는 1회 미사용도 신호다.
- COPY-BLOCK (F-706): BASE 에 없던 새 파일(이동 후보 제외)에서 추가 줄 5줄 창의 4줄 이상(0.8)이 BASE 에 있다 — 선례(테스트 대역 · helper)를 값만
  바꿔 복사한 꼴이다. 공유할지 · 차이가 실제로 읽히는지 사람이 본다.

HEAD 자리에 `WORKTREE` 를 주면 작업 트리(추적 파일의 미커밋 변경 + untracked 파일 전체)를 추가 쪽으로 본다 — fz-review 처럼
커밋 전 변경을 리뷰할 때 쓴다(커밋 둘만 비교하면 BASE=HEAD 에서 diff 가 늘 비어 검사가 꺼진다).
BASE blob 은 1MiB 이하만 요청하고 하나씩 읽는다 — 자산이 많은 저장소에서 트리 전체를 메모리에 올리지 않는다.

사용: check_moved_code.py BASE (HEAD|WORKTREE) [--repo DIR] | --self-test
출력: `MOVE-CANDIDATE <파일> <k>/<n>` · `COPY-BLOCK <파일>` · `DUP-ADDED <파일> ↔ <파일>` + 보기 줄 ·
      끝 줄 `moved-code: 파일 <m> · 후보 <c> · 복사 블록 <b> · 추가 중복 <d>`
exit: 0 셋 다 0 · 1 하나라도 있음 · 2 UNRUN(git 아님 · ref 를 못 풂 — ⛔ 통과 아님)
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

OK, MOVED, UNRUN = 0, 1, 2
MIN_LEN, MIN_LINES, RATIO = 25, 5, 0.5
BLOCK_LEN, DUP_RUN, COPY_WIN, COPY_HIT = 12, 3, 5, 4   # F-172 · F-706 — 블록 축은 짧은 코드 줄도 센다
DATA_EXT = {".json", ".jsonl", ".patch", ".diff", ".yaml", ".yml", ".csv", ".tsv", ".plist", ".xml", ".lock", ".resolved", ".pbxproj"}   # 블록 축 밖 — 데이터는 키가 반복된다
PROSE_EXT = {".md", ".markdown", ".txt", ".rst"}
WORKTREE = "WORKTREE"
NOT_CODE = re.compile(r"^(//|#|\*|/\*|--|<!--|import\b|from\s+\S+\s+import\b|@import\b|using\b|package\b)")


def git(repo: Path, *a) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *a], capture_output=True, text=True, errors="replace")


def _keep(path: str, s: str, min_len: int = BLOCK_LEN) -> bool:
    return os.path.splitext(path)[1].lower() not in PROSE_EXT and len(s) >= min_len and not NOT_CODE.match(s)


def added_code(repo: Path, base: str, head: str) -> dict[str, list[str]]:
    d = git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames", base, *([] if head == WORKTREE else [head]), "--")
    if d.returncode != 0:
        raise RuntimeError(d.stderr.strip()[:160])
    out: dict[str, list[str]] = {}
    if head == WORKTREE:                          # untracked 파일은 diff 에 없다 — 줄 전체가 추가다
        u = subprocess.run(["git", "-C", str(repo), "ls-files", "-o", "--exclude-standard", "-z"], capture_output=True)
        if u.returncode != 0:
            raise RuntimeError(u.stderr.decode("utf-8", "replace").strip()[:160])
        for rel in filter(None, u.stdout.decode("utf-8", "surrogateescape").split("\0")):
            f = repo / rel
            try:
                if f.stat().st_size > (1 << 20):
                    continue
                raw = f.read_bytes()
            except OSError:
                continue
            if b"\0" in raw[:8000]:
                continue
            for ln in raw.decode("utf-8", "replace").split("\n"):
                if _keep(rel, ln.strip()):
                    out.setdefault(rel, []).append(ln.strip())
    path, in_hunk = None, False
    for ln in d.stdout.split("\n"):
        if ln.startswith("diff --git "):
            path, in_hunk = None, False
            continue
        if not in_hunk:
            if ln.startswith("+++ "):
                tgt = ln[4:]
                path = None if tgt == "/dev/null" else (tgt[2:] if tgt.startswith("b/") else tgt)
            elif ln.startswith("@@"):
                in_hunk = True
            continue
        if ln.startswith("+") and path and _keep(path, ln[1:].strip()):
            out.setdefault(path, []).append(ln[1:].strip())
    return out


def base_lines(repo: Path, base: str) -> set[str]:
    """BASE 트리 텍스트 blob 의 줄 집합(앞뒤 공백 뗀 · BLOCK_LEN 이상). `git cat-file --batch` 한 프로세스로 읽는다.

    - Note: `git grep -F -f` 는 패턴에 `\\E` 같은 글자가 있으면 내부 PCRE 변환에서 죽는다(실측) — 그래서 쓰지 않는다.
    """
    ls = subprocess.run(["git", "-C", str(repo), "ls-tree", "-r", "-z", "-l", base], capture_output=True)
    if ls.returncode != 0:
        raise RuntimeError(ls.stderr.decode("utf-8", "replace").strip()[:160])
    shas = []
    for ent in ls.stdout.split(b"\0"):
        if not ent or b"\t" not in ent:
            continue
        meta, path = ent.split(b"\t", 1)
        parts = meta.split()                      # <mode> blob <sha> <size>
        if (len(parts) == 4 and parts[1] == b"blob" and parts[3].isdigit() and int(parts[3]) <= (1 << 20)
                and os.path.splitext(path.decode("utf-8", "replace"))[1].lower() not in PROSE_EXT):
            shas.append(parts[2])                 # 큰 파일은 요청하지 않는다 — 코드 줄 대조 대상이 아니다
    out: set[str] = set()
    if not shas:
        return out
    p = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)

    def feed():                                   # 쓰는 쪽을 따로 둔다 — 한 스레드에서 쓰고 읽으면 파이프가 차서 멈춘다
        try:
            p.stdin.write(b"\n".join(shas) + b"\n")
        finally:
            p.stdin.close()

    w = threading.Thread(target=feed, daemon=True)
    w.start()
    while True:                                   # blob 하나씩 읽는다 — 트리 전체를 메모리에 올리지 않는다
        head = p.stdout.readline()
        if not head:
            break
        parts = head.split()
        if len(parts) < 3 or parts[1] != b"blob":
            continue
        blob = p.stdout.read(int(parts[2]))
        p.stdout.read(1)
        if b"\0" in blob[:8000]:
            continue                              # 바이너리는 코드 줄 대조 대상이 아니다
        for ln in blob.decode("utf-8", "replace").split("\n"):
            s = ln.strip()
            if len(s) >= BLOCK_LEN:
                out.add(s)
    w.join()
    err = p.stderr.read()
    if p.wait() != 0:
        raise RuntimeError(err.decode("utf-8", "replace").strip()[:160])
    return out


def run(repo: Path, base: str, head: str) -> int:
    for ref in (base,) + (() if head == WORKTREE else (head,)):
        if git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
            print(f"UNRUN: git 저장소가 아니거나 ref 를 풀지 못했다 — {repo} · {ref} (⛔ 통과 아님)")
            return UNRUN
    try:
        added = added_code(repo, base, head)
    except RuntimeError as e:
        print(f"UNRUN: git diff 실패 — {e} (⛔ 통과 아님)")
        return UNRUN
    try:
        found = base_lines(repo, base) if added else set()
    except RuntimeError as e:
        print(f"UNRUN: BASE 트리를 읽지 못했다 — {e} (⛔ 통과 아님)")
        return UNRUN
    cands, moved = 0, set()
    for path, block in sorted(added.items()):
        lines = [s for s in block if len(s) >= MIN_LEN]
        k = sum(1 for s in lines if s in found)
        if lines and len(lines) >= MIN_LINES and k / len(lines) >= RATIO:
            cands += 1
            moved.add(path)
            print(f"MOVE-CANDIDATE {path} {k}/{len(lines)} — 추가 코드 줄의 대부분이 {base} 에 이미 있다(이동 · 복사 후보 · 신규로 읽기 전 출처를 본다)")
            for s in [s for s in lines if s in found][:3]:
                print(f"    = {s[:120]}")
    ls = git(repo, "ls-tree", "-r", "--name-only", "-z", base)
    if ls.returncode != 0:
        print(f"UNRUN: BASE 파일 목록을 읽지 못했다 — {ls.stderr.strip()[:160]} (⛔ 통과 아님)")
        return UNRUN
    old = set(filter(None, ls.stdout.split("\0")))
    copies = copy_blocks(added, found, moved | old)   # 고친 기존 파일은 관용구가 BASE 와 겹친다 — 새 파일만 본다
    for path, win in copies:
        print(f"COPY-BLOCK {path} — 추가 줄 {COPY_WIN}줄 창의 {COPY_HIT}줄 이상이 {base} 에 있다(선례를 값만 바꿔 복사했나 · "
              f"공유할지 · 다른 줄이 실제로 읽히는지 본다 · F-706)")
        print(f"    = {win[0][:120]}")
    dups = dup_added(added, found)
    for (pa, pb), win in dups[:5]:
        print(f"DUP-ADDED {pa} ↔ {pb} — 같은 변경의 추가 줄끼리 연속 {DUP_RUN}줄이 같다(방금 만든 헬퍼를 쓰지 않고 다시 적었나 · F-172)")
        print(f"    = {win[0][:120]}")
    print(f"moved-code: 파일 {len(added)} · 후보 {cands} · 복사 블록 {len(copies)} · 추가 중복 {len(dups)}")
    return MOVED if cands or copies or dups else OK


def _code_files(added: dict) -> list:
    return [(p, ls) for p, ls in sorted(added.items()) if os.path.splitext(p)[1].lower() not in DATA_EXT]


def copy_blocks(added: dict, found: set, skip: set) -> list:
    """F-706 — `skip`(이동 후보 · BASE 에 있던 파일) 밖 파일마다 첫 창 하나: COPY_WIN 줄 창의 COPY_HIT 줄 이상이 BASE 에 있다."""
    out = []
    for path, lines in _code_files(added):
        if path in skip:
            continue
        for i in range(len(lines) - COPY_WIN + 1):
            win = lines[i:i + COPY_WIN]
            if len(set(win)) == COPY_WIN and sum(1 for s in win if s in found) >= COPY_HIT:
                out.append((path, win))
                break
    return out


def dup_added(added: dict, found: set) -> list:
    """F-172 — 추가 줄의 연속 DUP_RUN 줄이 다른 자리(다른 파일 · 겹치지 않는 위치)에 또 나온다. BASE 에 다 있는 창은 뺀다(복사 축)."""
    seen, out, told = {}, [], set()
    for path, lines in _code_files(added):
        for i in range(len(lines) - DUP_RUN + 1):
            win = tuple(lines[i:i + DUP_RUN])
            if len(set(win)) < DUP_RUN or all(s in found for s in win):
                continue
            prev = seen.get(win)
            if prev is None:
                seen[win] = (path, i)
            elif (prev[0] != path or i - prev[1] >= DUP_RUN) and (prev[0], path) not in told:
                told.add((prev[0], path))
                out.append(((prev[0], path), win))
    return out


def self_test() -> int:
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []
    body = "".join(f"    let value{i} = computeSomethingLong(input: {i}, flag: true)\n" for i in range(8))

    def case(name, base: dict, head: dict, want: int, worktree=False, need=(), absent=()):
        nonlocal passed
        with tempfile.TemporaryDirectory(prefix="fz-moved-") as d:
            g = lambda *a: subprocess.run(["git", "-C", d, "-c", "user.email=t@t", "-c", "user.name=t", *a], capture_output=True)
            ok = g("init", "-q").returncode == 0
            for n, files in enumerate((base, head)):
                for rel in list(Path(d).rglob("*.swift")):
                    rel.unlink()
                for rel, src in files.items():
                    (Path(d) / rel).parent.mkdir(parents=True, exist_ok=True)
                    (Path(d) / rel).write_text(src, encoding="utf-8")
                if n == 0 or not worktree:            # worktree 면 head 쪽은 커밋하지 않는다(미커밋 · untracked)
                    ok = ok and g("add", "-A").returncode == 0 and g("commit", "-qm", "c", "--allow-empty").returncode == 0
            if not ok:
                fails.append(f"{name}: 픽스처 git 준비 실패")
                return
            import io
            buf = io.StringIO()
            keep, sys.stdout = sys.stdout, buf
            try:
                rc = run(Path(d), "HEAD", WORKTREE) if worktree else run(Path(d), "HEAD~1", "HEAD")
            finally:
                sys.stdout = keep
        out = buf.getvalue()
        miss = [n for n in need if n not in out] + [f"있으면 안 됨 {n}" for n in absent if n in out]
        if rc == want and not miss:
            passed += 1
            if listing:
                print(f"PASS {name}")
        else:
            fails.append(f"{name}: exit {rc} (기대 {want}) {miss}")

    case("f078-moved-code-detected", {"Old/Checkout.swift": "func a() {\n" + body + "}\n"},
         {"New/Checkout.swift": "func a() {\n" + body + "    let brandNewLine = somethingElseEntirely(x: 1)\n}\n"}, MOVED)
    case("f078-new-code-not-flagged", {"Old/Checkout.swift": "func a() {\n" + body + "}\n"},
         dict({"Old/Checkout.swift": "func a() {\n" + body + "}\n"},
              **{"New/Other.swift": "".join(f"    let freshName{i} = brandNewComputation(arg: {i * 7})\n" for i in range(8))}), OK)
    case("f078-worktree-untracked-move-detected", {"Old/Checkout.swift": "func a() {\n" + body + "}\n"},
         {"New/Checkout.swift": "func a() {\n" + body + "}\n"}, MOVED, worktree=True)
    case("f078-worktree-new-code-not-flagged", {"Old/Checkout.swift": "func a() {\n" + body + "}\n"},
         {"Old/Checkout.swift": "func a() {\n" + body + "}\n",
          "New/Other.swift": "".join(f"    let freshName{i} = brandNewComputation(arg: {i * 7})\n" for i in range(8))}, OK, worktree=True)
    helper = ("    for recognizer in [expandPanOnPlayer, expandPanOnPreview] {\n        recognizer.isEnabled = false\n"
              "        recognizer.isEnabled = true\n    }\n")
    case("f172-dup-added-detected", {"A.swift": "func a() {\n    let unrelatedValue = compute(1)\n}\n"},
         {"A.swift": "func a() {\n    let unrelatedValue = compute(1)\n}\nfunc cancelPlayerGestureRecognizers() {\n" + helper
                     + "}\nfunc cancelPlayerDescentBeforeOverlay() {\n    overlayState.prepareDescent()\n" + helper + "}\n"},
         MOVED, need=("DUP-ADDED A.swift ↔ A.swift", "추가 중복 1"), absent=("COPY-BLOCK",))
    case("f172-single-helper-not-flagged", {"A.swift": "func a() {\n    let unrelatedValue = compute(1)\n}\n"},
         {"A.swift": "func a() {\n    let unrelatedValue = compute(1)\n}\nfunc cancelPlayerGestureRecognizers() {\n" + helper
                     + "}\nfunc cancelPlayerDescentBeforeOverlay() {\n    overlayState.prepareDescent()\n    cancelPlayerGestureRecognizers()\n}\n"},
         OK, need=("추가 중복 0",))
    stub = ("private final class SpyPlayerRouter: PlayerRouting {\n    var routeCallCount = 0\n    var lastRoutedContent: Content?\n"
            "    func route(to content: Content) {\n        routeCallCount += 1\n        lastRoutedContent = content\n    }\n}\n")
    fresh = "".join(f"    func testScenario{i}() {{ XCTAssertEqual(makeSubject(seed: {i * 13}).state, .ready{i}) }}\n" for i in range(8))
    case("f706-copy-block-detected", {"Tests/LiveTests.swift": stub + "final class LiveTests {}\n"},
         {"Tests/LiveTests.swift": stub + "final class LiveTests {}\n",
          "Tests/SportsTests.swift": stub.replace("var routeCallCount = 0", "var routeCallCount = 1") + "final class SportsTests {\n" + fresh + "}\n"},
         MOVED, need=("COPY-BLOCK Tests/SportsTests.swift", "복사 블록 1"), absent=("MOVE-CANDIDATE",))
    case("f706-fresh-test-not-flagged", {"Tests/LiveTests.swift": stub + "final class LiveTests {}\n"},
         {"Tests/LiveTests.swift": stub + "final class LiveTests {}\n", "Tests/SportsTests.swift": "final class SportsTests {\n" + fresh + "}\n"},
         OK, need=("복사 블록 0",))
    with tempfile.TemporaryDirectory() as d:
        with open(os.devnull, "w") as null:
            keep, sys.stdout = sys.stdout, null
            try:
                rc = run(Path(d), "HEAD~1", "HEAD")
            finally:
                sys.stdout = keep
    if rc == UNRUN:
        passed += 1
        if listing:
            print("PASS f078-not-a-repo-unrun")
    else:
        fails.append(f"f078-not-a-repo-unrun: exit {rc}")

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base", nargs="?")
    ap.add_argument("head", nargs="?")
    ap.add_argument("--repo", type=Path, default=Path("."))
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.base or not a.head:
        print("UNRUN: BASE 와 HEAD(또는 WORKTREE) 가 필요하다 (⛔ 통과 아님)")
        return UNRUN
    return run(a.repo, a.base, a.head)


if __name__ == "__main__":
    sys.exit(main())
