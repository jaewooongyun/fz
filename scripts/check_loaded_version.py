#!/usr/bin/env python3
"""로드 체크아웃 대조 — Claude Code 가 실제로 읽는 fz 체크아웃이 출하본보다 뒤처졌는가.

출하는 한 워크트리에서 하고 세션은 다른 체크아웃(`--plugin-dir`)을 읽으면, 로드 체크아웃을
앞으로 옮기지 않는 한 세션은 옛 fz 로 돈다(F-507: 4일간 옛 판이 모드 질문 없이 Workflow 를 띄웠다).
출하 저장소의 최신 `v*` 태그(또는 `--release-ref`)와 로드 체크아웃 HEAD 를 git 조상 관계로 비교한다.

판정
  LOADED_OK        같은 커밋
  LOADED_AHEAD     로드 쪽이 출하 커밋을 포함하고 더 나아갔다(개발 체크아웃) — 경고 아님
  LOADED_BEHIND    로드 쪽이 출하 커밋의 조상이다 — ff 필요
  LOADED_DIVERGED  서로 조상이 아니다 — 사람이 판단
  LOADED_UNKNOWN   로드 루트 미지정·부재·git 아님·출하 ref 없음 — ⛔ 통과로 읽지 않는다

exit 0  경고 전용(기본) — 판정은 출력 첫 줄에 있다
exit 1  --strict 이고 BEHIND · DIVERGED · UNKNOWN
exit 2  인자 오류
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE_REPO = os.path.dirname(SCRIPT_DIR)   # 이 스크립트가 든 저장소 = 출하 저장소


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def latest_tag(repo):
    rc, out, _ = git(repo, "tag", "--list", "v*", "--sort=-v:refname")
    return out.splitlines()[0] if rc == 0 and out else None


def version_of(root):
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return json.load(f).get("version")
    except (OSError, ValueError):
        return None


def judge(loaded_root, release_repo, release_ref=None):
    """(판정, 설명) — 조상 관계는 로드 체크아웃의 객체 저장소에서 본다(워크트리면 같은 저장소)."""
    if not loaded_root:
        return "LOADED_UNKNOWN", "로드 루트 미지정 — --loaded-root 또는 FZ_LOADED_ROOT"
    if not os.path.isdir(loaded_root):
        return "LOADED_UNKNOWN", f"로드 루트 없음: {loaded_root}"
    rc, head, _ = git(loaded_root, "rev-parse", "HEAD")
    if rc != 0:
        return "LOADED_UNKNOWN", f"git 체크아웃이 아니다: {loaded_root}"
    ref = release_ref or latest_tag(release_repo)
    if not ref:
        return "LOADED_UNKNOWN", f"출하 ref 없음 — {release_repo} 에 v* 태그가 없고 --release-ref 도 없다"
    rc, rel, _ = git(release_repo, "rev-parse", f"{ref}^{{commit}}")
    if rc != 0:
        return "LOADED_UNKNOWN", f"출하 ref 해석 실패: {ref}"
    note = f"loaded {head[:7]} ({version_of(loaded_root)}) · release {ref} {rel[:7]} ({version_of(release_repo)})"
    if head == rel:
        return "LOADED_OK", note
    if git(loaded_root, "cat-file", "-e", f"{rel}^{{commit}}")[0] != 0:
        return "LOADED_UNKNOWN", f"로드 저장소에 출하 커밋이 없다(다른 clone · fetch 필요) — {note}"
    if git(loaded_root, "merge-base", "--is-ancestor", head, rel)[0] == 0:
        n = git(loaded_root, "rev-list", "--count", f"{head}..{rel}")[1]
        return "LOADED_BEHIND", f"{n} 커밋 뒤 — `git -C {loaded_root} merge --ff-only {ref}` · {note}"
    if git(loaded_root, "merge-base", "--is-ancestor", rel, head)[0] == 0:
        return "LOADED_AHEAD", note
    return "LOADED_DIVERGED", f"서로 조상이 아니다 — {note}"


def self_test():
    """임시 저장소 하나 — 커밋 2개 · 태그 · 갈래 · 워크트리로 다섯 판정을 재현한다."""
    fails, cases = [], []

    def case(name, got, want):
        ok = got == want
        cases.append(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" got {got} want {want}"))
        if not ok:
            fails.append(name)

    with tempfile.TemporaryDirectory() as d:
        repo, wt = os.path.join(d, "repo"), os.path.join(d, "loaded")
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)

        def run(*a, cwd=repo):
            subprocess.run(list(a), cwd=cwd, env=env, check=True, capture_output=True)

        os.makedirs(repo)
        run("git", "init", "-q", "-b", "main")
        run("git", "commit", "-q", "--allow-empty", "-m", "c1")
        c1 = git(repo, "rev-parse", "HEAD")[1]
        run("git", "commit", "-q", "--allow-empty", "-m", "c2")
        run("git", "tag", "v1.1.0")
        run("git", "worktree", "add", "-q", "--detach", wt, c1)
        case("behind", judge(wt, repo)[0], "LOADED_BEHIND")
        run("git", "checkout", "-q", "--detach", "v1.1.0", cwd=wt)
        case("equal", judge(wt, repo)[0], "LOADED_OK")
        run("git", "commit", "-q", "--allow-empty", "-m", "dev", cwd=wt)
        case("ahead", judge(wt, repo)[0], "LOADED_AHEAD")
        run("git", "checkout", "-q", "--detach", c1, cwd=wt)
        run("git", "commit", "-q", "--allow-empty", "-m", "side", cwd=wt)
        case("diverged", judge(wt, repo)[0], "LOADED_DIVERGED")
        case("missing-root", judge(os.path.join(d, "nope"), repo)[0], "LOADED_UNKNOWN")
        case("unset-root", judge(None, repo)[0], "LOADED_UNKNOWN")
    print("\n".join(cases))
    print(f"check_loaded_version self-test: {'PASS' if not fails else 'FAIL'} ({len(cases) - len(fails)}/{len(cases)})")
    return 0 if not fails else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="로드 체크아웃이 출하본보다 뒤처졌는지 대조 (경고 전용)")
    ap.add_argument("--loaded-root", default=os.environ.get("FZ_LOADED_ROOT"),
                    help="Claude Code 가 읽는 fz 체크아웃 (기본: env FZ_LOADED_ROOT)")
    ap.add_argument("--release-repo", default=RELEASE_REPO, help="출하 저장소 (기본: 이 스크립트의 저장소)")
    ap.add_argument("--release-ref", default=None, help="출하 ref (기본: 출하 저장소의 최신 v* 태그)")
    ap.add_argument("--strict", action="store_true", help="BEHIND · DIVERGED · UNKNOWN 이면 exit 1")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    verdict, note = judge(a.loaded_root, a.release_repo, a.release_ref)
    print(f"{verdict} — {note}")
    if a.strict and verdict in ("LOADED_BEHIND", "LOADED_DIVERGED", "LOADED_UNKNOWN"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
