#!/usr/bin/env python3
"""health-check 경로별 검사 선택 (H2-9 · GPT H-015) — 바뀐 경로로 돌릴 검사를 고르고, 고를 근거가 없으면 전체로 보낸다.

왜: health-check 전체는 15분쯤 걸린다. 문서 한 줄을 고칠 때마다 전체를 돌리면 사람이 안 돌리게 된다. 그렇다고
'경로 → 검사' 표를 손으로 두면, 러너가 새 경로를 읽기 시작해도 표가 그대로라 그 러너가 조용히 빠진다(의존성 계약이 낡는다).
그래서 선택은 매번 러너 원문에서 다시 계산한다 — 손으로 고치는 표는 없다.

분류
  · 전체(full) — `--ship` · 빈 경로 목록 · 공용 인프라 아래 경로(scripts/ · schemas/ · workflows/ · tests/ · hooks/ ·
    .claude-plugin/ · gpt-skills/ · templates/ · agents/ — md_section · health-check 자신 · 생성 golden · 공유 블록 · 레지스트리가
    여기 있다) · 문서가 아닌 모든 경로(미분류 = 전체 · 루트 밖 경로 포함)
  · 문서 = guides/ · modules/ · skills/ · docs/ 아래 `.md` 와 루트 CLAUDE.md · README.md · CHANGELOG.md
  · 부분(subset) — 경로가 전부 문서일 때: 문서 lint 4종(항상) + 바뀐 문서에 기대는 러너
  ⛔ 분류는 경로 **문자열**로만 한다 — 지운 파일도 바뀐 경로다(존재 여부를 보지 않는다).

러너가 문서 P(최상위 폴더 T · 파일 이름 B)에 기대는가 — 러너 원문 묶음 중 한 파일이라도
  ① 이름: P 나 B 를 적었다
  ② 글롭: 최상위 T 로 시작하고 `*` 가 든 글롭 문자열이 P 에 맞는다
  ③ 순회: 한 줄에 최상위 T 와 폴더 순회 호출(glob( · os.walk · listdir · scandir · iterdir( · readdir · find · ls)이 함께 있다,
     또는 경로 변수에 붙인 T 폴더(`$X/T` · `/ "T"` · `/ "T" / 변수`)를 넘긴다 — 받는 쪽이 폴더를 훑는다고 본다.
     존재 확인(`-d` · is_dir · exists) · mkdir · 이름 붙은 파일 하나(`/ "T" / "이름"` — ① 이 본다)는 순회가 아니다
  '최상위' = 앞이 다른 경로 조각이 아니다(`tests/docs` · `gpt-skills` 는 T 가 아니다). 루트 문서는 ① 만 본다 —
  루트 순회는 대부분의 러너에 있어 판별력이 없다. 애매하면 넣는다(과다 선택은 느릴 뿐이고 누락은 회귀를 놓친다).

러너 원문 묶음 = 러너 파일 + (fixture 러너면) 같은 폴더의 모든 파일과 묶음 폴더의 `_lib*` + 그 파일들이 경로로 부르는
코드 파일(.py · .sh · .js — python import · JS require 포함, workflows/ 제외) **한 단계**.
  ⛔ 두 단계부터는 따라가지 않는다 — health-check.sh 를 부르는 러너가 health-check 가 부르는 lint 들이 적은 문서에 전부
     걸려 선택이 전체와 같아진다. workflows/ 는 프롬프트에 문서 경로를 적을 뿐 읽지 않아서 뺀다.
  ⛔ 그 너머의 의존과 러너가 아닌 health-check 검사(census · 외부 명령 · GPT 표면 등)는 부분 실행이 보지 않는다 —
     그래서 부분 실행은 출하 게이트가 아니다. 출하는 `--ship`(= 전체)이다.

출력: 첫 줄 `HEALTH-SELECT mode=full|subset reason=<…>` · subset 이면 이어서 `HEALTH-SELECT check=<이름> by=<근거>` 줄들
  (lint 는 스크립트 파일 이름 · 러너는 루트 기준 경로 · health-check 4.6 과 같은 순서). full 이면 check 줄이 없다 — 전부다.

usage: health_select.py [--ship] [--from-file FILE] [--] [PATH ...]  ·  --self-test
  --from-file : 한 줄에 경로 하나(빈 줄 무시) — `git diff --name-only` 출력을 그대로 받는다
exit: 0 선택 출력 · 2 사용법 오류(알 수 없는 옵션 · 읽지 못한 --from-file · 플러그인 루트 아님)
"""
from __future__ import annotations

import fnmatch
import functools
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # scripts/ → 플러그인 루트

LINTS = ("lint_contracts.py", "lint_recurrence.py", "lint_doc_freshness.py", "check_single_source.py")
INFRA_DIRS = ("scripts", "schemas", "workflows", "tests", "hooks", ".claude-plugin", "gpt-skills", "templates", "agents")
DOC_DIRS = ("guides", "modules", "skills", "docs")
ROOT_DOCS = ("CLAUDE.md", "README.md", "CHANGELOG.md")
# health-check 4.6 이 도는 러너 집합 · 순서와 같다 — 다르면 선택된 러너를 health-check 가 모른다
RUNNER_GLOBS = ("tests/workflows/*.js", "tests/lib/*.test.js", "tests/fixtures/*/*/run.sh")
CODE_EXT = (".py", ".sh", ".js", ".mjs", ".cjs")
NO_HOP_TOP = ("workflows",)
SOURCE_CAP = 2_000_000   # 바이트 — 이보다 큰 파일은 데이터로 보고 원문 묶음에서 뺀다

CODE_TOKEN = re.compile(r"[^\s\"'`()<>|;,=\[\]]+\.(?:py|sh|js|mjs|cjs)\b")
PY_IMPORT = re.compile(r"^\s*(?:from\s+([A-Za-z_]\w*)[\w.]*\s+import\b|import\s+([A-Za-z_][\w ,]*))", re.M)
JS_REQUIRE = re.compile(r"""require\(\s*['"](\.{1,2}/[^'"]+)['"]\s*\)""")
SCAN_CALL = re.compile(r"glob\(|os\.walk\(|listdir\(|scandir\(|iterdir\(|readdirSync\(|readdir\(|\bfind\s|\bls\s")
GLOB_TAIL = re.compile(r"/[^\s\"'`()<>|;,]*")
PATH_END = re.compile(r"""^(?:["'\s)]|$)""")
DIR_SHELL = re.compile(r"(?:\$\w+|\$\{\w+\})\"?/$")      # `$X/T` · `${X}/T` · `"$X"/T`
DIR_PY = re.compile(r"/\s*[\"']$")                        # `X / "T"`
# 폴더를 넘기지만 훑지 않는 꼴 — 존재 확인(`-d "$X/T"` · `(X / "T").is_dir()`) · 만들기(mkdir) · 이름 붙은 파일 하나(`X / "T" / "이름"`)
NOT_SCAN_BEFORE = re.compile(r"-[def]\s+\"?(?:\$\w+|\$\{\w+\})\"?/$|\bmkdir\b")
NOT_SCAN_AFTER = re.compile(r"""^["']\s*(?:\)\s*\.(?:is_dir|exists)\(|/\s*["'])""")


@functools.lru_cache(maxsize=None)
def _read(p: Path) -> str:
    try:
        if p.stat().st_size > SOURCE_CAP:
            return ""
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def norm(raw: str, root: Path):
    """루트 기준 POSIX 상대 경로. 루트 밖이거나 빈 값이면 None(미분류 → 전체)."""
    p = raw.strip()
    if not p:
        return None
    if os.path.isabs(p):
        p = os.path.relpath(p, str(root))
    p = os.path.normpath(p).replace(os.sep, "/")
    if p in (".", "..") or p.startswith("../"):
        return None
    return p


def kind(rel) -> str:
    """'doc' · 'infra' · 'unknown'."""
    if rel is None:
        return "unknown"
    top, _, rest = rel.partition("/")
    if not rest:
        return "doc" if rel in ROOT_DOCS else "unknown"
    if top in INFRA_DIRS:
        return "infra"
    if top in DOC_DIRS and rel.endswith(".md"):
        return "doc"
    return "unknown"


def runners(root: Path) -> list[str]:
    out = []
    for g in RUNNER_GLOBS:
        out += [p.relative_to(root).as_posix() for p in sorted(root.glob(g)) if p.is_file()]
    return out


def _within(root: Path, p: Path):
    q = Path(os.path.normpath(str(p)))
    try:
        q.relative_to(root)
    except ValueError:
        return None
    return q if q.is_file() else None


def level0(root: Path, rel: str) -> list[Path]:
    """러너 자신의 원문 — 러너 파일 + fixture 폴더 전체 + 묶음 폴더의 `_lib*`(파일 · 폴더)."""
    p = root / rel
    files = [p]
    if p.name == "run.sh" and rel.split("/")[:2] == ["tests", "fixtures"]:
        files += [q for q in sorted(p.parent.rglob("*")) if q.is_file() and q != p]
        for lib in sorted(p.parent.parent.glob("_lib*")):
            files += [lib] if lib.is_file() else [q for q in sorted(lib.rglob("*")) if q.is_file()]
    return files


def _resolve_token(root: Path, src: Path, tok: str):
    """경로 토큰 → 루트 안 실재 코드 파일. `$X/` · `${X}/` · `{X}/` 같은 앞 조각은 뒤쪽 조각부터 맞춰 본다."""
    parts = tok.split("/")
    for k in range(len(parts)):
        tail = "/".join(parts[k:])
        if not tail or "$" in tail or "{" in tail:
            continue
        for base in (src.parent, root):
            q = _within(root, base / tail)
            if q is not None:
                return q
    return None


def hops(root: Path, srcs: list[Path]) -> list[Path]:
    """원문 묶음이 경로로 부르는 코드 파일(한 단계). workflows/ 와 이미 묶음에 든 파일은 뺀다."""
    seen = set(srcs)
    out = []

    def add(q):
        if q is None or q in seen:
            return
        if q.relative_to(root).as_posix().split("/")[0] in NO_HOP_TOP or not q.name.endswith(CODE_EXT):
            return
        seen.add(q)
        out.append(q)

    for s in srcs:
        text = _read(s)
        for tok in CODE_TOKEN.findall(text):
            add(_resolve_token(root, s, tok))
        if s.suffix == ".py":
            for m in PY_IMPORT.finditer(text):
                names = [m.group(1)] if m.group(1) else [n.strip().split(" ")[0] for n in m.group(2).split(",")]
                for n in names:
                    for base in (s.parent, root / "scripts", root / "tests" / "lib"):
                        q = _within(root, base / f"{n}.py")
                        if q is not None:
                            add(q)
                            break
        if s.suffix in (".js", ".mjs", ".cjs"):
            for r in JS_REQUIRE.findall(text):
                for cand in (r, r + ".js"):
                    q = _within(root, s.parent / cand)
                    if q is not None:
                        add(q)
                        break
    return out


def _top_hits(line: str, top: str):
    """한 줄에서 '최상위' T 가 나온 자리들 — 앞이 다른 경로 조각(`tests/docs`)이거나 더 긴 이름의 일부(`gpt-skills`)면 뺀다."""
    for m in re.finditer(r"(?<![\w.-])" + re.escape(top) + r"(?![\w.-])", line):
        before = line[:m.start()]
        if before.endswith("/"):
            seg = re.search(r"(?:^|[^\w$.-])([\w.-]+)/$", before)
            if seg and seg.group(1) not in (".", ".."):
                continue   # 리터럴 폴더 아래 같은 이름 — 최상위가 아니다(`$X/` · `"$X"/` · `${X}/` · `../` 는 통과)
        yield m


def depends(text: str, doc: str):
    """원문 하나가 문서 doc 에 기대는가 → 규칙 이름('name' · 'glob' · 'scan') 또는 None."""
    base = doc.rsplit("/", 1)[-1]
    if doc in text or re.search(r"(?<![\w.-])" + re.escape(base) + r"(?![\w-])", text):
        return "name"
    if "/" not in doc:
        return None   # 루트 문서는 이름만 본다
    top = doc.split("/", 1)[0]
    if top not in text:
        return None
    for line in text.split("\n"):
        hits = list(_top_hits(line, top))
        if not hits:
            continue
        for m in hits:
            rest = line[m.end():]
            tail = GLOB_TAIL.match(rest)
            if tail and "*" in tail.group(0) and fnmatch.fnmatchcase(doc, top + tail.group(0)):
                return "glob"
        if SCAN_CALL.search(line):
            return "scan"
        for m in hits:
            before, rest = line[:m.start()], line[m.end():]
            if not (DIR_SHELL.search(before) or DIR_PY.search(before)) or not PATH_END.match(rest):
                continue
            if NOT_SCAN_BEFORE.search(before) or NOT_SCAN_AFTER.match(rest):
                continue
            return "scan"
    return None


def decide(paths: list[str], ship: bool, root: Path):
    """-> (mode, reason, [(check, by)])."""
    if ship:
        return "full", "ship", []
    if not paths:
        return "full", "empty", []
    rels = [norm(p, root) for p in paths]
    other = [(p, kind(r)) for p, r in zip(paths, rels) if kind(r) != "doc"]
    if other:
        p, k = other[0]
        return "full", f"{k}:{p.strip()}" + (f" (+{len(other) - 1})" if len(other) > 1 else ""), []
    docs = sorted(set(rels))
    checks = [(lint, "always") for lint in LINTS]
    for rel in runners(root):
        srcs = level0(root, rel)
        bundle = srcs + hops(root, srcs)
        texts = [(s, _read(s)) for s in bundle]
        by = None
        for d in docs:
            for s, t in texts:
                rule = depends(t, d)
                if rule:
                    by = f"{rule}:{d}@{s.relative_to(root).as_posix()}"
                    break
            if by:
                break
        if by:
            checks.append((rel, by))
    return "subset", f"doc-only:{len(docs)}", checks


def self_test() -> int:
    """임시 트리만 쓴다 — 트리 사본에서 러너를 지우고 health-check 를 도는 fixture(unrun-classification)에서도 같은 결과여야 한다."""
    T = "modules"   # 문서 폴더 이름은 실행 중에만 조립한다 — 이 파일 원문이 실제 러너의 의존으로 읽히지 않게
    files = {
        "guides/g.md": "x\n",
        "skills/s/SKILL.md": "x\n",
        "scripts/chk.py": f'print(open("{T}/a.md").read())\n',
        "scripts/outer.py": 'import subprocess\nsubprocess.run(["python3", "scripts/inner.py"])\n',
        "scripts/inner.py": f'open("{T}/a.md")\n',
        "tests/lib/h.js": f"module.exports = '{T}/a.md'\n",
        "tests/fixtures/g/names/run.sh": f'cat "$R/{T}/a.md"\n',
        "tests/fixtures/g/basename/run.sh": 'cat "$X/a.md"\n',
        "tests/fixtures/g/globpat/run.sh": f'for f in "$R"/{T}/plan-*.md; do :; done\n',
        "tests/fixtures/g/walk/run.sh": 'python3 "$HERE/cells.py"\n',
        "tests/fixtures/g/walk/cells.py": f'for p in sorted((root / "{T}").glob("*.md")):\n    pass\n',
        "tests/fixtures/g/dirarg/run.sh": f'python3 tool.py --dir "$ROOT/{T}"\n',
        "tests/fixtures/g/dyncell/run.sh": f'python3 - <<PY\nprint((tree / "{T}" / name).read_text())\nPY\n',
        "tests/fixtures/g/notscan/run.sh": (f'[ -d "$ROOT/{T}" ] || exit 2\nmkdir -p "$SEED/{T}"\n'
                                            f'python3 -c \'(tree / "{T}" / "other.md").read_text(); (tree / "{T}").is_dir()\'\n'),
        "tests/fixtures/g/hop/run.sh": 'python3 "$D/scripts/chk.py" --root "$D"\n',
        "tests/fixtures/g/twohop/run.sh": 'python3 "$D/scripts/outer.py"\n',
        "tests/fixtures/g/nested/run.sh": 'for f in "$R"/tests/docs/*.md; do :; done\n',
        "tests/fixtures/g/gptskills/run.sh": 'for f in "$R"/gpt-skills/*/notes-*.md; do :; done\n',
        "tests/fixtures/g/rootdoc/run.sh": 'grep -c x "$R/CLAUDE.md"\n',
        "tests/fixtures/g/rootwalk/run.sh": 'python3 -c "import os; list(os.walk(\'.\'))"\n',
        "tests/fixtures/g/unrelated/run.sh": "echo ok\n",
        "tests/fixtures/h/_lib.sh": 'python3 "$D/scripts/libchk.py"\n',   # 묶음 lib 가 부르는 스크립트도 한 단계 안이다
        "scripts/libchk.py": 'open("guides/z.md")\n',
        "tests/fixtures/h/uselib/run.sh": '. "$(dirname "$0")/../_lib.sh"\n',
        "tests/workflows/w.js": "const h = require('../lib/h')\n",
        "tests/workflows/plain.js": "console.log(1)\n",
    }
    lints = set(LINTS)
    cases = [
        # (이름, 경로, --ship, 기대 mode, reason 접두, 반드시 선택, 선택되면 안 됨)
        ("ship", [f"{T}/a.md"], True, "full", "ship", set(), set()),
        ("empty", [], False, "full", "empty", set(), set()),
        ("infra-md_section", ["scripts/md_section.py"], False, "full", "infra:", set(), set()),
        ("infra-health-check", ["scripts/health-check.sh"], False, "full", "infra:", set(), set()),
        ("unknown-yaml", ["some/new/thing.yaml"], False, "full", "unknown:", set(), set()),
        ("unknown-non-md-in-doc-dir", [f"{T}/x.txt"], False, "full", "unknown:", set(), set()),
        ("unknown-other-top", ["examples/x.md"], False, "full", "unknown:", set(), set()),
        ("unknown-outside-root", ["../outside.md"], False, "full", "unknown:", set(), set()),
        ("doc-plus-infra", [f"{T}/a.md", "schemas/x.json"], False, "full", "infra:", set(), set()),
        ("doc-subset", [f"./{T}/a.md"], False, "subset", "doc-only:1",
         lints | {"tests/fixtures/g/names/run.sh", "tests/fixtures/g/basename/run.sh", "tests/fixtures/g/walk/run.sh",
                  "tests/fixtures/g/dirarg/run.sh", "tests/fixtures/g/dyncell/run.sh", "tests/fixtures/g/hop/run.sh",
                  "tests/workflows/w.js"},
         {"tests/fixtures/g/globpat/run.sh", "tests/fixtures/g/twohop/run.sh", "tests/fixtures/g/unrelated/run.sh",
          "tests/fixtures/g/rootwalk/run.sh", "tests/workflows/plain.js", "tests/fixtures/h/uselib/run.sh",
          "tests/fixtures/g/notscan/run.sh"}),
        ("glob-pattern", [f"{T}/plan-x.md"], False, "subset", "doc-only:1",
         lints | {"tests/fixtures/g/globpat/run.sh", "tests/fixtures/g/walk/run.sh"},
         {"tests/fixtures/g/names/run.sh", "tests/fixtures/g/unrelated/run.sh"}),
        ("nested-and-prefixed-names-are-not-top", ["docs/notes-a.md", "skills/s/notes-b.md"], False, "subset", "doc-only:2",
         lints, {"tests/fixtures/g/nested/run.sh", "tests/fixtures/g/gptskills/run.sh"}),
        ("root-doc-by-name-only", ["CLAUDE.md"], False, "subset", "doc-only:1",
         lints | {"tests/fixtures/g/rootdoc/run.sh"}, {"tests/fixtures/g/rootwalk/run.sh", "tests/fixtures/g/unrelated/run.sh"}),
        ("group-lib-is-runner-source", ["guides/z.md"], False, "subset", "doc-only:1",
         lints | {"tests/fixtures/h/uselib/run.sh"}, {"tests/fixtures/g/unrelated/run.sh"}),
        ("deleted-doc-still-doc", [f"{T}/gone.md"], False, "subset", "doc-only:1", lints, {"tests/fixtures/g/names/run.sh"}),
    ]
    fails = []
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        for rel, body in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body, encoding="utf-8")
        for name, paths, ship, want_mode, want_reason, must, must_not in cases:
            mode, reason, checks = decide(paths, ship, root)
            got = {c for c, _ in checks}
            bad = []
            if mode != want_mode:
                bad.append(f"mode {mode} (want {want_mode})")
            if not reason.startswith(want_reason):
                bad.append(f"reason {reason!r} (want {want_reason!r}…)")
            if mode == "full" and checks:
                bad.append("full 인데 check 줄이 있다")
            if must - got:
                bad.append(f"빠짐 {sorted(must - got)}")
            if must_not & got:
                bad.append(f"잘못 선택 {sorted(must_not & got)}")
            if bad:
                fails.append(f"{name}: " + " · ".join(bad))
    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {len(cases) - len(fails)}/{len(cases)} passed")
    return 0 if not fails else 1


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return self_test()
    ship, paths, i = False, [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            paths += argv[i + 1:]
            break
        if a == "--ship":
            ship = True
        elif a == "--from-file":
            if i + 1 >= len(argv):
                print("health-select: --from-file 에 파일이 없다", file=sys.stderr)
                return 2
            try:
                with open(argv[i + 1], encoding="utf-8") as fh:
                    paths += [ln.strip() for ln in fh.read().splitlines() if ln.strip()]
            except OSError as e:
                print(f"health-select: --from-file 읽기 실패 — {e}", file=sys.stderr)
                return 2
            i += 1
        elif a[:1] == "-" and a != "-":
            print(f"health-select: 알 수 없는 옵션 {a} (사용법: health_select.py [--ship] [--from-file FILE] [--] [PATH ...] · --self-test)",
                  file=sys.stderr)
            return 2
        else:
            paths.append(a)
        i += 1
    if not (ROOT / "guides").is_dir():
        print(f"health-select: 플러그인 루트가 아님 — {ROOT}", file=sys.stderr)
        return 2
    mode, reason, checks = decide(paths, ship, ROOT)
    print(f"HEALTH-SELECT mode={mode} reason={reason}")
    for name, by in checks:
        print(f"HEALTH-SELECT check={name} by={by}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
