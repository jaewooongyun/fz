#!/usr/bin/env python3
"""퇴역 slash command 참조 검사 (H1-3).

설치 · 활성화되지 않은 slash command 를 운영 문서가 실행 지시로 부르면, Lead 는 없는 명령을 찾다가 멈추거나 조용히
건너뛴다(`/ralph-loop` — 설정 · 캐시 grep 0 인데 6파일 약 12곳이 에스컬레이션을 그 명령에 맡겼다). 셸 코드 블록의 첫 토큰만
보는 `check_external_commands.py` 로는 산문 · 표에 적힌 slash command 를 못 잡는다 — 그래서 문서 전체를 본다.

대상   skills/**/*.md · modules/*.md · guides/*.md · agents/*.md · gpt-skills/**/*.md · templates/** · CLAUDE.md · README.md
       (CHANGELOG.md · docs/ 는 이력이라 대상이 아니다)
규칙   RETIRED 의 명령이 산문 · 표 · 코드 블록 어디에 나와도 위반이다 — 대체 경로는 RETIRED 값이 가리킨다

usage: check_retired_commands.py [--root R]   ·   --self-test
출력:  위반마다 `<파일>:<줄>: <명령> → <대체>` · 끝에 `retired commands: 0` 또는 `retired commands: FAIL (N)`
exit:  0 위반 0 · 1 위반 있음 · 2 대상 0개(판정 불가 — 통과 아님)
"""
from __future__ import annotations

import glob
import os
import re
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
RETIRED = {   # 명령 → 대체 경로
    "/ralph-loop": "modules/execution-modes.md 에스컬레이션 래더 · guides/skill-authoring.md §12 실패 복구 사다리",
    "/sc:sc-business-panel": "없음 — 설치 목록에 없다(H1-2)",
}
GLOBS = ("skills/**/*.md", "modules/*.md", "guides/*.md", "agents/*.md", "gpt-skills/**/*.md", "templates/**/*",
         "CLAUDE.md", "README.md")
PATTERN = re.compile("|".join(r"(?<![\w/-])" + re.escape(c) + r"(?![\w-])" for c in RETIRED))


def targets(root):
    seen = []
    for g in GLOBS:
        for p in sorted(glob.glob(os.path.join(root, g), recursive=True)):
            if os.path.isfile(p) and p not in seen:
                seen.append(p)
    return seen


def scan(root):
    files, hits = targets(root), []
    for p in files:
        for n, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            for m in PATTERN.finditer(line):
                hits.append((os.path.relpath(p, root), n, m.group(0)))
    return files, hits


def report(root):
    files, hits = scan(root)
    for rel, n, cmd in hits:
        print(f"{rel}:{n}: {cmd} → {RETIRED[cmd]}")
    if not files:
        print("UNRUN: 검사 대상 문서 0개 — 판정 불가(통과 아님)")
        return 2
    print("retired commands: 0" if not hits else f"retired commands: FAIL ({len(hits)})")
    return 0 if not hits else 1


def self_test():
    cases = {
        "prose": ("modules/a.md", "빌드가 실패하면 /ralph-loop 로 반복한다.\n", 1),
        "table": ("skills/x/SKILL.md", "| 빌드 실패 | /ralph-loop 래더 |\n", 1),
        "code-block": ("guides/g.md", "```bash\n/ralph-loop --max-iterations 3\n```\n", 1),
        "clean": ("modules/b.md", "에스컬레이션 래더(§12). ralph-loop-like 이름 · path/ralph-loop 는 명령이 아니다.\n", 0),
    }
    fails = []
    for name, (rel, text, want) in cases.items():
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(text)
            _, hits = scan(d)
            ok = len(hits) == want
            print(f"{name}: {'PASS' if ok else 'FAIL'}" + ("" if ok else f" hits {len(hits)} != {want}"))
            if not ok:
                fails.append(name)
    print(f"self-test {len(cases) - len(fails)}/{len(cases)} passed")
    print(f"check_retired_commands self-test: {'PASS' if not fails else 'FAIL'}")
    return 0 if not fails else 1


def main(argv):
    if argv[:1] == ["--self-test"]:
        return self_test()
    root = ROOT
    if argv[:1] == ["--root"] and len(argv) > 1:
        root = os.path.abspath(argv[1])
    elif argv:
        print(__doc__.strip().split("usage:")[1].split("출력:")[0].strip(), file=sys.stderr)
        return 2
    return report(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
