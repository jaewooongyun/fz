#!/usr/bin/env python3
# lint:no-root-anchor — 대상 저장소를 `--project` 로 받는다(플러그인 루트의 파일을 읽지 않는다).
"""프로젝트 지침의 원문 색인 추출기 (S15 · 정본 `modules/project-rules.md`).

⛔ 해석하지 않는다. 지침 파일의 heading 마다 원문을 그대로 낸다 — 축 매핑·규칙 레코드는 모델이
   **각자** 만든다(해석된 JSON 을 Claude·GPT 가 공유하면 한쪽 오류가 다른 쪽 전제가 된다).

출력(stdout — JSON 하나. 진단은 전부 stderr):
  {"schemaVersion": 1, "absent": bool, "files": [상대경로…],
   "sections": [{"file", "line", "endLine", "level", "heading", "bodyLine", "quote"}…]}
  - line = heading 줄(머리말 절은 1, level 0, heading null) · endLine = 절의 마지막 줄
  - quote = heading 아래 본문 원문(앞뒤 빈 줄만 뺀다) · bodyLine = quote 첫 줄 번호(본문이 비면 null)
  - ⛔ 코드 펜스(``` · ~~~) 안의 `#` 줄은 heading 이 아니다 — 실제 지침 파일의 bash 예시가 절을 쪼갠다
  - 경로는 저장소 기준 상대 POSIX 경로, 파일·절은 정렬 — 같은 저장소면 어디서 돌려도 같은 출력이다

exit: 0=추출(지침이 없어도 0 — absent:true) · 2=측정 실패(프로젝트 폴더를 읽을 수 없다)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile

OK, UNRUN = 0, 2

# 이름이 정확히 같은 파일만 지침으로 본다(CONTRIBUTING·README 는 에이전트 지침이 아니다).
GUIDE_NAMES = {"CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md"}
GUIDE_PATHS = {".github/copilot-instructions.md"}
SKIP_DIRS = {".git", "node_modules", ".build", "build", "DerivedData", "Pods", "Carthage", ".venv", "venv",
             "vendor", "dist", ".next", "target", ".gradle", ".codegraph", "__pycache__"}
MAX_DEPTH = 6

HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
CLOSING = re.compile(r"[ \t]+#+$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def guide_files(root: pathlib.Path) -> list:
    found = []
    for cur, dirs, files in os.walk(root):
        rel_dir = pathlib.Path(cur).relative_to(root)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS) if len(rel_dir.parts) < MAX_DEPTH else []
        for f in files:
            rel = (rel_dir / f).as_posix()
            if f in GUIDE_NAMES or rel in GUIDE_PATHS:
                found.append(rel)
    return sorted(found)


def sections_of(rel: str, text: str) -> list:
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    heads, fence = [], None                      # heads: (index, level, heading)
    for i, ln in enumerate(lines):
        f = FENCE.match(ln)
        if f:
            mark = f.group(1)
            if fence is None:
                fence = mark[0] * 3
            elif mark.startswith(fence):
                fence = None
            continue
        if fence is None:
            m = HEADING.match(ln)
            if m:
                heads.append((i, len(m.group(1)), CLOSING.sub("", m.group(2) or "").strip()))
    starts = [(0, 0, None)] if not heads or heads[0][0] > 0 else []
    out = []
    for k, (i, level, heading) in enumerate(starts + heads):
        nxt = (starts + heads)[k + 1][0] if k + 1 < len(starts + heads) else len(lines)
        body_from = i if heading is None and level == 0 else i + 1
        body = lines[body_from:nxt]
        lead = 0
        while lead < len(body) and not body[lead].strip():
            lead += 1
        trail = len(body)
        while trail > lead and not body[trail - 1].strip():
            trail -= 1
        quote = "\n".join(body[lead:trail])
        if heading is None and level == 0 and not quote:
            continue                              # 비어 있는 머리말은 절이 아니다
        out.append({"file": rel, "line": i + 1, "endLine": nxt, "level": level, "heading": heading,
                    "bodyLine": body_from + lead + 1 if quote else None, "quote": quote})
    return out


def extract(root: pathlib.Path) -> dict:
    files = guide_files(root)
    sections = []
    for rel in files:
        sections += sections_of(rel, (root / rel).read_text(encoding="utf-8", errors="replace"))
    return {"schemaVersion": 1, "absent": not files, "files": files, "sections": sections}


def dump(index: dict) -> str:
    return json.dumps(index, ensure_ascii=False, indent=2) + "\n"


# ── self-test ──────────────────────────────────────────────────────
def self_test() -> int:
    results = []

    def case(name, ok, got=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else f' — {got}'}")

    with tempfile.TemporaryDirectory(prefix="fz-rules-extract-") as tmp:
        p = pathlib.Path(tmp) / "proj"
        (p / "sub").mkdir(parents=True)
        (p / ".git").mkdir()
        (p / "node_modules" / "x").mkdir(parents=True)
        (p / "CLAUDE.md").write_text(
            "머리말 한 줄\n\n# 제목\n\n## Architecture ##\n\n- 규칙 A\n- 규칙 B(예: `Foo`)\n\n"
            "## Build\n\n```bash\n# 이 줄은 heading 이 아니다\nmake\n```\n\n~~~\n## 이것도 아니다\n~~~\n", encoding="utf-8")
        (p / "sub" / "AGENTS.md").write_text("## Sub\n\n- 하위 규칙\n", encoding="utf-8")
        (p / ".git" / "CLAUDE.md").write_text("# 무시\n", encoding="utf-8")
        (p / "node_modules" / "x" / "CLAUDE.md").write_text("# 무시\n", encoding="utf-8")
        (p / "README.md").write_text("# 지침 아님\n", encoding="utf-8")
        idx = extract(p)
        case("지침 파일 집합 — .git·node_modules·README 제외, 하위 폴더 포함", idx["files"] == ["CLAUDE.md", "sub/AGENTS.md"], idx["files"])
        heads = [(s["file"], s["line"], s["level"], s["heading"]) for s in idx["sections"]]
        want = [("CLAUDE.md", 1, 0, None), ("CLAUDE.md", 3, 1, "제목"), ("CLAUDE.md", 5, 2, "Architecture"),
                ("CLAUDE.md", 10, 2, "Build"), ("sub/AGENTS.md", 1, 2, "Sub")]
        case("heading 분할 · 머리말 절 · 닫는 # 제거", heads == want, heads)
        build = next(s for s in idx["sections"] if s["heading"] == "Build")
        case("⛔ 펜스 안 `#` 줄은 heading 이 아니다(``` · ~~~)", "# 이 줄은 heading 이 아니다" in build["quote"] and "## 이것도 아니다" in build["quote"],
             build["quote"])
        arch = next(s for s in idx["sections"] if s["heading"] == "Architecture")
        case("본문 원문 · bodyLine · endLine", arch["quote"] == "- 규칙 A\n- 규칙 B(예: `Foo`)" and arch["bodyLine"] == 7 and arch["endLine"] == 9,
             json.dumps(arch, ensure_ascii=False))
        title = next(s for s in idx["sections"] if s["heading"] == "제목")
        case("빈 본문 절 — quote '' · bodyLine null", title["quote"] == "" and title["bodyLine"] is None, json.dumps(title, ensure_ascii=False))

        me = pathlib.Path(__file__).resolve()
        r1 = subprocess.run([sys.executable, str(me), "--project", str(p)], capture_output=True, text=True)
        r2 = subprocess.run([sys.executable, str(me), "--project", str(p)], cwd=tmp, capture_output=True, text=True)
        case("stdout 은 JSON 하나 · 두 번 돌려도 같다(cwd 무관)", r1.returncode == 0 and json.loads(r1.stdout) == idx and r1.stdout == r2.stdout,
             f"exit {r1.returncode} {r1.stderr[-120:]}")
        case("출력에 임시 경로가 없다", tmp not in r1.stdout, "임시 경로 노출")

        e = pathlib.Path(tmp) / "empty"
        e.mkdir()
        (e / "main.swift").write_text("let x = 1\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(me), "--project", str(e)], capture_output=True, text=True)
        case("지침 부재 → exit 0 · absent true · sections []", r.returncode == 0 and json.loads(r.stdout) ==
             {"schemaVersion": 1, "absent": True, "files": [], "sections": []}, f"exit {r.returncode} {r.stdout[:80]}")
        r = subprocess.run([sys.executable, str(me), "--project", str(pathlib.Path(tmp) / "없다")], capture_output=True, text=True)
        case("⛔ 폴더를 읽을 수 없으면 exit 2 · stdout 비움", r.returncode == UNRUN and r.stdout == "", f"exit {r.returncode}")

    print(f"self-test {sum(results)}/{len(results)} passed")
    return OK if all(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", help="대상 저장소 루트")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.project:
        print("UNRUN: --project 가 필요하다", file=sys.stderr)
        return UNRUN
    root = pathlib.Path(a.project).expanduser()
    if not root.is_dir():
        print(f"UNRUN: 프로젝트 폴더를 읽을 수 없다 — {root}", file=sys.stderr)
        return UNRUN
    sys.stdout.write(dump(extract(root.resolve())))
    return OK


if __name__ == "__main__":
    sys.exit(main())
