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
  - candidates = [{"path", "via"}…] — absent 이고 링크 출처가 저장소 안 .md 를 가리킬 때만 있는 키(F-513)
    링크 출처: --project 상위 폴더(--ancestor-stop 까지 · 기본 $HOME)의 고정 이름 지침 + --link-source FILE
    path = 저장소 상대 경로 · via = 출처의 저장소 상대 경로(예: ../CLAUDE.md)
    ⛔ 링크 경로만 뽑는다 — 출처 본문은 sections 에 넣지 않고, 후보 문서는 열지 않는다(존재만 본다)
    ⛔ 한계: 다른 경로의 워크트리를 --project 로 주면 상위 링크가 저장소 밖으로 풀려 무시된다

exit: 0=추출(지침이 없어도 0 — absent:true) · 2=측정 실패(프로젝트 폴더 · 링크 출처를 읽을 수 없다)
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
             "vendor", "dist", ".next", "target", ".gradle", "__pycache__"}
MAX_DEPTH = 6

HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
CLOSING = re.compile(r"[ \t]+#+$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
# 지침이 문서를 가리키는 세 모양 — 마크다운 링크 · 백틱 경로 · @import
LINKS = (re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)\s]*)?\)"), re.compile(r"`([^`\s]+\.md)`"),
         re.compile(r"(?<![\w`])@([^\s`()]+\.md)"))


def guide_files(root: pathlib.Path) -> list:
    """⛔ 읽지 못한 폴더를 건너뛰지 않는다 — os.walk 는 기본값에서 오류를 삼켜, 못 읽은 지침을 '지침 없음'으로 만든다."""
    found, errors = [], []
    for cur, dirs, files in os.walk(root, onerror=errors.append):
        rel_dir = pathlib.Path(cur).relative_to(root)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS) if len(rel_dir.parts) < MAX_DEPTH else []
        for f in files:
            rel = (rel_dir / f).as_posix()
            if f in GUIDE_NAMES or rel in GUIDE_PATHS:
                found.append(rel)
    if errors:
        raise OSError(f"폴더를 읽을 수 없다 — {errors[0].filename}: {errors[0].strerror}")
    return sorted(found)


def closes(opening: str, mark: str, rest: str) -> bool:
    """닫는 펜스 — 여는 펜스와 같은 문자 · 같거나 긴 길이 · 뒤에 정보 문자열 없음(CommonMark).
    ⛔ 길이를 보지 않으면 네 백틱 펜스 안의 세 백틱 줄이 펜스를 닫아, 그 뒤 `#` 줄이 heading 이 된다."""
    return mark[0] == opening[0] and len(mark) >= len(opening) and not rest.strip()


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
                fence = mark
            elif closes(fence, mark, ln[f.end():]):
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


def ancestor_guides(root: pathlib.Path, stop) -> list:
    """root 의 상위 폴더(stop 포함)에 있는 고정 이름 지침. stop 이 root 의 상위가 아니면 찾지 않는다."""
    if stop is None or stop not in root.parents:
        return []
    out = []
    for d in root.parents:
        out += [d / n for n in sorted(GUIDE_NAMES | GUIDE_PATHS) if (d / n).is_file()]
        if d == stop:
            return out
    return out


def link_candidates(root: pathlib.Path, sources: list) -> list:
    """출처에서 링크 경로만 뽑아 root 안의 실제 .md 파일만 낸다. 후보 문서는 열지 않는다."""
    seen, out = set(), []
    for src in sources:
        text = src.read_text(encoding="utf-8", errors="replace")
        via = os.path.relpath(src, root)
        for rx in LINKS:
            for m in rx.finditer(text):
                target = (src.parent / pathlib.Path(m.group(1)).expanduser()).resolve()
                try:
                    rel = target.relative_to(root).as_posix()
                except ValueError:                 # 저장소 밖(심볼릭 링크로 나가는 경우 포함)
                    continue
                if rel not in seen and target.is_file():
                    seen.add(rel)
                    out.append({"path": rel, "via": pathlib.Path(via).as_posix()})
    return sorted(out, key=lambda c: c["path"])


def extract(root: pathlib.Path, stop=None, link_sources=()) -> dict:
    files = guide_files(root)
    sections = []
    for rel in files:
        sections += sections_of(rel, (root / rel).read_text(encoding="utf-8", errors="replace"))
    out = {"schemaVersion": 1, "absent": not files, "files": files, "sections": sections}
    if not files:                                  # ⛔ 지침이 있으면 키도 없다 — golden · 완전 일치 비교 불변
        cands = link_candidates(root, ancestor_guides(root, stop) + list(link_sources))
        if cands:
            out["candidates"] = cands
    return out


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
        def t_index():
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

        def t_cli():
            idx = extract(p)
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

        def t_fence4():
            fz = pathlib.Path(tmp) / "fence4"
            fz.mkdir()
            (fz / "CLAUDE.md").write_text("## 앞\n\n````md\n```\n## 안 — heading 아님\n```\n````\n\n## 뒤\n\n- 규칙\n", encoding="utf-8")
            got = [s["heading"] for s in extract(fz)["sections"]]
            case("⛔ 네 백틱 펜스 안의 세 백틱 줄은 펜스를 닫지 않는다(같은 문자 · 같거나 긴 길이)", got == ["앞", "뒤"], got)

        def t_locked():
            if os.geteuid() != 0:                      # root 는 권한을 무시해 이 경우를 만들 수 없다
                lk = pathlib.Path(tmp) / "locked"
                (lk / "sub").mkdir(parents=True)
                (lk / "CLAUDE.md").write_text("## 위\n", encoding="utf-8")
                (lk / "sub" / "AGENTS.md").write_text("## 아래\n", encoding="utf-8")
                try:
                    (lk / "sub").chmod(0)
                    r = subprocess.run([sys.executable, str(me), "--project", str(lk)], capture_output=True, text=True)
                    case("⛔ 하위 폴더를 읽지 못하면 exit 2 — 건너뛰고 지침 일부만 내지 않는다", r.returncode == UNRUN and r.stdout == "",
                         f"exit {r.returncode} {r.stdout[:80]}")
                    (lk / "sub").chmod(0o755)
                    lk.chmod(0)
                    r = subprocess.run([sys.executable, str(me), "--project", str(lk)], capture_output=True, text=True)
                    case("⛔ 루트를 읽지 못하면 exit 2 — absent(지침 없음)로 세지 않는다", r.returncode == UNRUN and r.stdout == "",
                         f"exit {r.returncode} {r.stdout[:80]}")
                finally:
                    lk.chmod(0o755)
                    (lk / "sub").chmod(0o755)

        def t_links():
            # F-513 원래 모양 — 저장소 본체에는 고정 이름 지침이 없고, 상위 CLAUDE.md 가 저장소 안 문서를 백틱 경로로 가리킨다
            home = pathlib.Path(tmp) / "home"
            top = home / "dev" / "T"
            repo = top / "app-iOS"
            (repo / "AI").mkdir(parents=True)
            (home / "dev" / "other").mkdir(parents=True)
            (repo / "main.swift").write_text("let x = 1\n", encoding="utf-8")
            (repo / "AI" / "review-guidelines.md").write_text("# 리뷰\n\nSENTINEL-DOC\n", encoding="utf-8")
            (repo / "AI" / "ai-guidelines.md").write_text("# 가이드\n", encoding="utf-8")
            (top / "outside.md").write_text("# 밖\n", encoding="utf-8")
            (home / "dev" / "other" / "x.md").write_text("# 밖\n", encoding="utf-8")
            (repo / "AI" / "link.md").symlink_to(home / "dev" / "other" / "x.md")
            (top / "CLAUDE.md").write_text(
                "## Architecture\n\nSENTINEL-GUIDE 규칙 본문\n- 리뷰 기준: `app-iOS/AI/review-guidelines.md` (필요 시 Read)\n"
                "- [가이드](app-iOS/AI/ai-guidelines.md#top) · `app-iOS/AI/missing.md` · `app-iOS/main.swift`\n"
                "- `outside.md` · `../other/x.md` · `app-iOS/AI/link.md`\n", encoding="utf-8")
            env = dict(os.environ, HOME=str(home))
            run = lambda *a, e=env: subprocess.run([sys.executable, str(me), *a], capture_output=True, text=True, env=e)  # noqa: E731
            want = [{"path": "AI/ai-guidelines.md", "via": "../CLAUDE.md"}, {"path": "AI/review-guidelines.md", "via": "../CLAUDE.md"}]
            absent = {"schemaVersion": 1, "absent": True, "files": [], "sections": []}
            locked = os.geteuid() != 0
            if locked:                                 # 후보 문서를 열면 exit 2 가 된다 — 본문 읽기 0 의 행동 증거
                (repo / "AI" / "review-guidelines.md").chmod(0)
            try:
                r = run("--project", str(repo))
            finally:
                (repo / "AI" / "review-guidelines.md").chmod(0o644)
            got = json.loads(r.stdout) if r.returncode == 0 else {}
            case("ancestor-guide-link-candidates 상위 지침의 저장소 안 링크 → candidates(기본 stop=$HOME)",
                 got == dict(absent, candidates=want), f"exit {r.returncode} {r.stdout[:160]} {r.stderr[-120:]}")
            case("ancestor-body-not-ingested 상위 지침 · 후보 문서 본문은 출력에 없다(후보 문서 잠금에도 exit 0)",
                 r.returncode == 0 and "SENTINEL" not in r.stdout and got.get("sections") == [],
                 f"exit {r.returncode} {r.stderr[-120:]}")
            paths = [c["path"] for c in got.get("candidates", [])]
            case("link-outside-project-ignored 저장소 밖 · 없는 파일 · .md 아님 · 밖으로 나가는 링크는 버린다",
                 paths == ["AI/ai-guidelines.md", "AI/review-guidelines.md"], paths)

            solo = pathlib.Path(tmp) / "solo"
            proj = solo / "proj"
            (proj / "docs").mkdir(parents=True)
            (proj / "docs" / "rules.md").write_text("# 규칙\n", encoding="utf-8")
            (solo / "notes.md").write_text("- [규칙](proj/docs/rules.md)\n", encoding="utf-8")
            r = run("--project", str(proj), "--ancestor-stop", str(proj), "--link-source", str(solo / "notes.md"))
            case("link-source-explicit-candidates 명시 --link-source 의 링크 → candidates",
                 r.returncode == 0 and json.loads(r.stdout) == dict(absent, candidates=[{"path": "docs/rules.md", "via": "../notes.md"}]),
                 f"exit {r.returncode} {r.stdout[:160]}")

            quiet = home / "dev" / "Q"
            (quiet / "proj").mkdir(parents=True)
            (quiet / "CLAUDE.md").write_text("- `outside.md`\n", encoding="utf-8")
            r1 = run("--project", str(proj), "--ancestor-stop", str(solo))
            r2 = run("--project", str(quiet / "proj"))
            case("no-link-source-absent-unchanged 링크 출처가 없거나 저장소 안 링크가 0이면 키 없이 옛 출력 그대로",
                 [r1.returncode, r2.returncode] == [0, 0] and json.loads(r1.stdout) == absent and json.loads(r2.stdout) == absent,
                 f"{r1.stdout[:80]} · {r2.stdout[:80]}")

            fixed = home / "dev" / "F"
            (fixed / "proj" / "docs").mkdir(parents=True)
            (fixed / "proj" / "CLAUDE.md").write_text("## 규칙\n\n- 하나\n", encoding="utf-8")
            (fixed / "proj" / "docs" / "x.md").write_text("# x\n", encoding="utf-8")
            (fixed / "CLAUDE.md").write_text("- `proj/docs/x.md`\n", encoding="utf-8")
            r = run("--project", str(fixed / "proj"), "--link-source", str(fixed / "CLAUDE.md"))
            got = json.loads(r.stdout) if r.returncode == 0 else {}
            case("fixed-name-guide-no-candidates-key 저장소에 고정 이름 지침이 있으면 candidates 키가 없다",
                 r.returncode == 0 and "candidates" not in got and got == extract((fixed / "proj").resolve()), f"exit {r.returncode} {list(got)}")
            r = run("--project", str(proj), "--link-source", str(solo / "없다.md"))
            case("link-source-missing-exit2 없는 --link-source 는 exit 2 · stdout 비움", r.returncode == UNRUN and r.stdout == "", f"exit {r.returncode}")

        for t in (t_index, t_cli, t_fence4, t_locked, t_links):
            try:
                t()
            except Exception as e:   # ⛔ 케이스 안의 예외는 FAIL 로 센다 — 크래시로 끝나면 몇 건이 안 돌았는지 모른다
                case(f"{t.__name__} — 예외", False, repr(e))

    print(f"self-test {sum(results)}/{len(results)} passed")
    return OK if all(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", help="대상 저장소 루트")
    ap.add_argument("--ancestor-stop", metavar="DIR", help="링크 출처를 찾는 상위 폴더의 끝(포함 · 기본 $HOME)")
    ap.add_argument("--link-source", metavar="FILE", action="append", default=[], help="링크를 뽑을 파일(여러 번)")
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
    stop = a.ancestor_stop or os.environ.get("HOME")
    if a.ancestor_stop and not pathlib.Path(stop).expanduser().is_dir():
        print(f"UNRUN: --ancestor-stop 폴더가 없다 — {stop}", file=sys.stderr)
        return UNRUN
    bad = [f for f in a.link_source if not pathlib.Path(f).expanduser().is_file()]
    if bad:
        print(f"UNRUN: --link-source 파일이 없다 — {bad[0]}", file=sys.stderr)
        return UNRUN
    try:
        index = extract(root.resolve(), pathlib.Path(stop).expanduser().resolve() if stop else None,
                        [pathlib.Path(f).expanduser().resolve() for f in a.link_source])
    except OSError as e:                           # 폴더 순회 · 지침 파일 읽기 실패 — 지침 없음(exit 0)이 아니다
        print(f"UNRUN: {e}", file=sys.stderr)
        return UNRUN
    sys.stdout.write(dump(index))
    return OK


if __name__ == "__main__":
    sys.exit(main())
