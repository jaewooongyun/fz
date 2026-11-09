#!/usr/bin/env python3
"""check_unrun_except.py — 넓은 except 가 UNRUN(측정 실패 · exit 2)을 내면 사유를 적게 한다.

왜: `except Exception` 은 결함(파싱 버그 · 오타 · 내용 이상)까지 삼킨다. 그 본문이 UNRUN 을 내면 위반이어야 할 결과가
'판정 불가' 로 바뀌어 고칠 대상이 가려진다(F-396 — 내용 이상 셋이 UNRUN 으로 새고 있었다). 환경 실패(모듈 적재 ·
실행기 예외)처럼 넓게 잡는 것이 맞는 자리도 있으므로 금지하지 않는다 — 그 자리에 사유를 적게 한다.

판정: 대상 파일의 except 절 중
  ① 넓다      — 맨 `except:` · `Exception` · `BaseException` (튜플 안에 있어도)
  ② UNRUN 을 낸다 — 본문에 `return UNRUN|2` · `sys.exit/exit/os._exit/SystemExit(UNRUN|2)` · 'UNRUN' 을 담은 문자열
  ③ 사유가 없다 — except 줄 주석에 `noqa: BLE001 — <사유>` 가 없다(표시만 있고 사유가 없으면 위반)
셋이 겹치면 위반이다. 좁은 except · 실패(FAIL)로 남기는 넓은 except 는 보지 않는다.

대상: scripts/*.py · skills/*/scripts/*.py · mods/*/hooks/*.py (tests/fixtures 는 일부러 결함을 담으므로 뺀다)

사용: check_unrun_except.py [--root DIR] | --self-test
exit: 0 충족 · 1 위반 · 2 UNRUN(대상 파일이 하한 미만 · 파싱 실패 — ⛔ 통과 아님)
출력: 위반마다 `VIOLATION <파일>:<줄>: …` · 요약 `unrun-except: files=N broad=M violations=K` · self-test 는 케이스마다 `PASS <셀>`
Python 3.9 stdlib 전용.
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
import tempfile
from pathlib import Path

OK, VIOLATION, UNRUN = 0, 1, 2
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBS = ("scripts/*.py", "skills/*/scripts/*.py", "mods/*/hooks/*.py")
MIN_FILES = 40      # 실측 90여 개 — 순회가 죽어 '위반 0' 으로 통과하는 것을 막는 하한
BROAD = {"Exception", "BaseException"}
EXIT_FUNCS = {"exit", "_exit", "SystemExit"}
REASON_RE = re.compile(r"#.*noqa:\s*BLE001\s*(?:—|--|-|:)\s*\S")


def _is_broad(t) -> bool:
    if t is None:
        return True
    if isinstance(t, ast.Tuple):
        return any(_is_broad(e) for e in t.elts)
    name = t.attr if isinstance(t, ast.Attribute) else getattr(t, "id", None)
    return name in BROAD


def _is_unrun_value(v) -> bool:
    return (isinstance(v, ast.Constant) and v.value == 2 and not isinstance(v.value, bool)) or \
           (isinstance(v, ast.Name) and v.id == "UNRUN")


def _yields_unrun(handler: ast.ExceptHandler) -> bool:
    for node in (n for stmt in handler.body for n in ast.walk(stmt)):
        if isinstance(node, ast.Return) and node.value is not None and _is_unrun_value(node.value):
            return True
        if isinstance(node, ast.Call) and node.args and _is_unrun_value(node.args[0]):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if name in EXIT_FUNCS:
                return True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "UNRUN" in node.value:
            return True
    return False


def scan_source(src: str, rel: str):
    """(넓은 except 수, 위반 목록). ⛔ 파싱 실패는 SyntaxError 로 올린다 — 호출자가 UNRUN 으로 낸다."""
    tree = ast.parse(src, filename=rel)
    lines = src.splitlines()
    broad, hits = 0, []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not _is_broad(node.type):
            continue
        broad += 1
        if not _yields_unrun(node):
            continue
        line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
        if REASON_RE.search(line):
            continue
        hits.append(f"{rel}:{node.lineno}: 넓은 except 가 UNRUN 을 낸다 — 내용 이상까지 '판정 불가' 로 덮는다. "
                    f"좁히거나 except 줄에 `# noqa: BLE001 — <왜 넓게 잡는가>` 를 적는다 (F-396)")
    return broad, hits


def scan_root(root: Path):
    files = sorted({p for g in GLOBS for p in root.glob(g) if p.is_file()})
    broad, hits = 0, []
    for p in files:
        rel = p.relative_to(root).as_posix()
        b, h = scan_source(p.read_text(encoding="utf-8"), rel)
        broad += b
        hits += h
    return len(files), broad, hits


def run(root: Path, min_files: int = MIN_FILES) -> int:
    try:
        n, broad, hits = scan_root(root)
    except (OSError, SyntaxError, UnicodeDecodeError) as e:
        print(f"UNRUN: 대상 파일을 읽거나 파싱하지 못했다 — {type(e).__name__}: {e} (⛔ 통과 아님)")
        return UNRUN
    if n < min_files:
        print(f"UNRUN: 대상 파일 {n}개 < 하한 {min_files} — {root} (경로 확인 · ⛔ 통과 아님)")
        return UNRUN
    for h in hits:
        print(f"VIOLATION {h}")
    print(f"unrun-except: files={n} broad={broad} violations={len(hits)}")
    return VIOLATION if hits else OK


def self_test() -> int:
    listing = bool(os.environ.get("FZ_SELFTEST_LIST"))
    passed, fails = 0, []

    def ok(name):
        nonlocal passed
        passed += 1
        if listing:
            print(f"PASS {name}")

    body = "def f():\n    try:\n        g()\n    {exc}\n        {act}\n"
    cases = [
        # (셀, except 줄, 본문, 기대 위반 수)
        ("f396-broad-except-unrun-lint", "except Exception as e:", 'print(f"UNRUN: {e}"); return UNRUN', 1),
        ("reason-marker-allowed", "except Exception as e:  # noqa: BLE001 — 모듈 적재 실패는 판정 불가다", "return UNRUN", 0),
        ("marker-without-reason-flagged", "except Exception as e:  # noqa: BLE001", "return 2", 1),
        ("narrow-except-ignored", "except (OSError, ValueError) as e:", "return UNRUN", 0),
        ("broad-except-fail-ignored", "except Exception as e:", 'fails.append(f"x: {e}")', 0),
        ("bare-except-exit2-flagged", "except:", "sys.exit(2)", 1),
        ("tuple-with-exception-flagged", "except (ValueError, Exception):", "raise SystemExit(UNRUN)", 1),
        ("return-1-not-unrun", "except Exception:", "return 1", 0),
    ]
    for name, exc, act, want in cases:
        try:
            _, hits = scan_source(body.format(exc=exc, act=act), "x.py")
            if len(hits) == want:
                ok(name)
            else:
                fails.append(f"{name}: 위반 {len(hits)} (기대 {want}) {hits[:1]}")
        except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게 그 케이스의 FAIL 로 남긴다
            fails.append(f"{name}: 예외 {type(e).__name__}: {e}")

    # 트리 수준 — 하한 미만 = UNRUN · 파싱 실패 = UNRUN · 위반 파일 하나 = VIOLATION
    def tree(files: dict, min_files: int, want: int, name: str):
        with tempfile.TemporaryDirectory(prefix="fz-unrun-except-") as d:
            for rel, src in files.items():
                q = Path(d) / rel
                q.parent.mkdir(parents=True, exist_ok=True)
                q.write_text(src, encoding="utf-8")
            with open(os.devnull, "w") as null:
                old, sys.stdout = sys.stdout, null
                try:
                    rc = run(Path(d), min_files)
                finally:
                    sys.stdout = old
        if rc == want:
            ok(name)
        else:
            fails.append(f"{name}: exit {rc} (기대 {want})")

    bad = body.format(exc="except Exception:", act="return UNRUN")
    tree({}, 1, UNRUN, "empty-tree-unrun")
    tree({"scripts/a.py": "def f(:\n"}, 1, UNRUN, "syntax-error-unrun")
    tree({"scripts/a.py": "x = 1\n", "skills/s/scripts/b.py": bad}, 2, VIOLATION, "skill-script-scanned")
    tree({"scripts/a.py": "x = 1\n", "tests/fixtures/c.py": bad}, 1, OK, "fixtures-excluded")

    for f in fails:
        print(f"  FAIL {f}")
    print(f"self-test {passed}/{passed + len(fails)} passed")
    return 0 if not fails else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", type=Path, default=Path(SCRIPT_DIR).parent)
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    return self_test() if a.self_test else run(a.root)


if __name__ == "__main__":
    sys.exit(main())
