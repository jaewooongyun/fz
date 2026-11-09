#!/usr/bin/env python3
# diff-parse: hunk-state — `diff --git` 헤더 구간과 `@@` hunk 를 구분해 hunk 안 `+` · `-` 줄만 바뀐 줄로 센다
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 인자로 받은 저장소 · 파일만 읽는다.
"""collect_env_axes.py — 두 ref 사이에서 런타임 · 빌드 환경을 바꾼 줄을 증상 어휘와 따로 모은다.

왜:
  F-075 증상 어휘로만 짠 회귀 sweep 이 런타임 환경을 바꾼 커밋(컴파일 가드 · 타이머)을 놓치고 '유발 변경 없음' 으로 결론냈다
  F-080 회귀 원인이 코드가 아니라 빌드 툴체인이었다 — 103커밋을 세 번 훑고도 못 찾았다
증상과 이름이 겹치지 않는 변경은 어휘 sweep 이 원리적으로 못 본다. 그래서 환경 축을 증상과 무관하게 따로 낸다.

축: compile-guard(#if · @available · canImport …) · timer(Timer · asyncAfter · Task.sleep · timeout …) ·
    network(URLSession · http(s):// · Alamofire · baseURL …) · build-setting(xcconfig · pbxproj · Package.swift · Info.plist ·
    entitlements · gradle 의 설정 줄) · toolchain(Package.resolved · .xcode-version · .swift-version · .tool-versions ·
    SDK · 배포 대상 · SWIFT_VERSION · CI 의 xcode-version 줄)
⛔ 출력은 **후보 목록**이다 — 원인 확정이 아니다. 저장소에 적히지 않은 환경(실제 링크된 SDK · 빌드 머신 · 과거 아카이브)은 범위 밖이다.

사용: collect_env_axes.py BASE HEAD [--repo DIR] | --self-test
출력: `AXIS <축>\t<파일>:<줄>\t<+|-> <내용>` · 끝 줄 `env-axes: <축>=<수> …`
exit: 0 수집(후보 0 포함) · 2 UNRUN(git 아님 · ref 를 못 풂 — ⛔ 통과 아님)
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

OK, UNRUN = 0, 2
AXES = ("compile-guard", "timer", "network", "build-setting", "toolchain")
LINE_RULES = {
    "compile-guard": re.compile(r"^\s*#\s*(if|ifdef|ifndef|elseif|elif|else|endif)\b|#available|@available|canImport\(|targetEnvironment\(|#if\s"),
    "timer": re.compile(r"\bTimer\b|asyncAfter|Task\.sleep|\bsleep\(|usleep\(|setTimeout|setInterval|\btimeout\w*\b|\bdeadline\b|DispatchTime|\.schedule\(", re.I),
    "network": re.compile(r"URLSession|URLRequest|https?://|Alamofire|\bbaseURL\b|\bendpoint\b|NWPathMonitor|Reachability|\bfetch\(|\bsocket\b", re.I),
}
BUILD_FILES = re.compile(r"(\.xcconfig|\.pbxproj|(^|/)Package\.swift|Info\.plist|\.entitlements|build\.gradle(\.kts)?|(^|/)Podfile|(^|/)Cartfile)$")
TOOLCHAIN_FILES = re.compile(r"((^|/)Package\.resolved|(^|/)\.xcode-version|(^|/)\.swift-version|(^|/)\.tool-versions|(^|/)Podfile\.lock|(^|/)Gemfile\.lock|(^|/)Cartfile\.resolved)$")
TOOLCHAIN_LINE = re.compile(r"SDKROOT|_DEPLOYMENT_TARGET|SWIFT_VERSION|xcode-version|DEVELOPER_DIR|xcode-select|\bXcode_?\d|toolchain", re.I)
SETTING_LINE = re.compile(r"^\s*[A-Z][A-Z0-9_]+(\[[^]]*\])?\s*=|^\s*<key>|swiftSettings|unsafeFlags|\bdefine\(|platforms:")


def git(repo: Path, *a) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.quotepath=off", *a], capture_output=True, text=True, errors="replace")


def changed_lines(repo: Path, base: str, head: str):
    """(파일, 줄 번호, '+' | '-', 내용) — 줄 번호는 + 면 HEAD 쪽 · - 면 BASE 쪽."""
    d = git(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--text", base, head, "--")
    if d.returncode != 0:
        raise RuntimeError(d.stderr.strip()[:160])
    old_path = new_path = None
    in_hunk, on, nn = False, 0, 0
    for ln in d.stdout.split("\n"):
        if ln.startswith("diff --git "):
            old_path = new_path = None
            in_hunk = False
            continue
        if not in_hunk:
            if ln.startswith("--- "):
                old_path = None if ln[4:] == "/dev/null" else ln[6:] if ln[4:].startswith("a/") else ln[4:]
            elif ln.startswith("+++ "):
                new_path = None if ln[4:] == "/dev/null" else ln[6:] if ln[4:].startswith("b/") else ln[4:]
            elif ln.startswith("@@"):
                m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", ln)
                in_hunk, on, nn = True, int(m.group(1)) if m else 0, int(m.group(2)) if m else 0
            continue
        if ln.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", ln)
            on, nn = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        elif ln.startswith("+"):
            yield (new_path or old_path), nn, "+", ln[1:]
            nn += 1
        elif ln.startswith("-"):
            yield (old_path or new_path), on, "-", ln[1:]
            on += 1


def classify(path: str, text: str) -> list[str]:
    axes = []
    if TOOLCHAIN_FILES.search(path) or (TOOLCHAIN_LINE.search(text) and (BUILD_FILES.search(path) or path.endswith((".yml", ".yaml", ".sh")))):
        axes.append("toolchain")
    if BUILD_FILES.search(path) and SETTING_LINE.search(text) and "toolchain" not in axes:
        axes.append("build-setting")
    for axis, rx in LINE_RULES.items():
        if rx.search(text):
            axes.append(axis)
    return axes


def collect(repo: Path, base: str, head: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {a: [] for a in AXES}
    for path, n, sign, text in changed_lines(repo, base, head):
        if not path:
            continue
        for axis in classify(path, text):
            out[axis].append(f"{path}:{n}\t{sign} {text.strip()[:160]}")
    return out


def run(repo: Path, base: str, head: str) -> int:
    for ref in (base, head):
        if git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode != 0:
            print(f"UNRUN: git 저장소가 아니거나 ref 를 풀지 못했다 — {repo} · {ref} (⛔ 통과 아님)")
            return UNRUN
    try:
        res = collect(repo, base, head)
    except RuntimeError as e:
        print(f"UNRUN: git diff 실패 — {e} (⛔ 통과 아님)")
        return UNRUN
    print(f"# 환경 축 후보 {base}..{head} — ⛔ 원인 확정 아님 · 증상 어휘 sweep 과 따로 읽는다")
    for axis in AXES:
        for row in res[axis]:
            print(f"AXIS {axis}\t{row}")
    print("env-axes: " + " ".join(f"{a}={len(res[a])}" for a in AXES))
    return OK


def self_test() -> int:
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    def repo_with(base: dict, head: dict):
        d = tempfile.mkdtemp(prefix="fz-env-axes-")
        g = lambda *a: subprocess.run(["git", "-C", d, "-c", "user.email=t@t", "-c", "user.name=t", *a], capture_output=True)
        for files in (base, head):
            for rel, body in files.items():
                (Path(d) / rel).parent.mkdir(parents=True, exist_ok=True)
                (Path(d) / rel).write_text(body, encoding="utf-8")
            if g("init", "-q").returncode or g("add", "-A").returncode or g("commit", "-qm", "c", "--allow-empty").returncode:
                raise RuntimeError("픽스처 git 준비 실패")
        return Path(d)

    def case(name, base, head, want: dict):
        nonlocal passed
        import shutil
        try:
            r = repo_with(base, head)
            got = {a: len(v) for a, v in collect(r, "HEAD~1", "HEAD").items()}
            shutil.rmtree(r, ignore_errors=True)
        except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게 그 케이스의 FAIL 로 남긴다
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")
            return
        bad = [f"{a}: {got[a]} (기대 {'≥1' if w else 0})" for a, w in want.items() if bool(got[a]) != w]
        if bad:
            fails.append(f"{name}: " + " · ".join(bad))
        else:
            passed += 1
            if listing:
                print(f"PASS {name}")

    base = {"App/Player.swift": "func play() {\n  start()\n}\n", "Config/App.xcconfig": "SWIFT_VERSION = 5.0\nOTHER_FLAG = A\n",
            "App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved": '{"pins": [{"identity": "lib", "state": {"version": "1.0.0"}}]}\n'}
    env_head = dict(base, **{"App/Player.swift": "func play() {\n#if DEBUG\n  Timer.scheduledTimer(withTimeInterval: 2, repeats: false) { _ in }\n#endif\n"
                                                    "  URLSession.shared.dataTask(with: url)\n  start()\n}\n",
                             "Config/App.xcconfig": "SWIFT_VERSION = 5.0\nOTHER_FLAG = B\n"})
    case("f075-env-axes-collected", base, env_head,
         {"compile-guard": True, "timer": True, "network": True, "build-setting": True, "toolchain": False})
    tool_head = dict(base, **{"Config/App.xcconfig": "SWIFT_VERSION = 6.0\nOTHER_FLAG = A\n",
                              "App.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved": '{"pins": [{"identity": "lib", "state": {"version": "1.1.0"}}]}\n',
                              ".xcode-version": "26.1\n"})
    case("f080-toolchain-axis", base, tool_head,
         {"compile-guard": False, "timer": False, "network": False, "build-setting": False, "toolchain": True})
    case("f075-logic-only-empty", base, dict(base, **{"App/Player.swift": "func play() {\n  start()\n  log(\"played\")\n}\n"}),
         {a: False for a in AXES})
    with tempfile.TemporaryDirectory() as d:
        with open(os.devnull, "w") as null:
            old, sys.stdout = sys.stdout, null
            try:
                rc = run(Path(d), "HEAD~1", "HEAD")
            finally:
                sys.stdout = old
    if rc == UNRUN:
        passed += 1
        if listing:
            print("PASS f075-not-a-repo-unrun")
    else:
        fails.append(f"f075-not-a-repo-unrun: exit {rc}")

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
        print("UNRUN: BASE HEAD 두 ref 가 필요하다 (⛔ 통과 아님)")
        return UNRUN
    return run(a.repo, a.base, a.head)


if __name__ == "__main__":
    sys.exit(main())
