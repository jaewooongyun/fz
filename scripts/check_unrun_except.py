#!/usr/bin/env python3
"""check_unrun_except.py — 넓은 except 가 UNRUN(측정 실패 · exit 2)이나 성공 꼴 값을 내면 사유를 적게 한다.

왜: `except Exception` 은 결함(파싱 버그 · 오타 · 내용 이상)까지 삼킨다. 그 본문이 UNRUN 을 내면 위반이어야 할 결과가
'판정 불가' 로 바뀌어 고칠 대상이 가려진다(F-396 — 내용 이상 셋이 UNRUN 으로 새고 있었다). 환경 실패(모듈 적재 ·
실행기 예외)처럼 넓게 잡는 것이 맞는 자리도 있으므로 금지하지 않는다 — 그 자리에 사유를 적게 한다. 본문이 성공 꼴 값
하나(`pass` · `return {}` …)뿐이어도 같다 — 결함이 '통과' 로 바뀌어 아무 줄도 남지 않는다.

판정: 대상 파일의 except 절 중
  ① 넓다      — 맨 `except:` · `Exception` · `BaseException` (튜플 안에 있어도)
  ② 덮는다   — 둘 중 하나
     ②a UNRUN 을 낸다 — 본문에 `return UNRUN|2` · `sys.exit/exit/os._exit/SystemExit(UNRUN|2)` · 'UNRUN' 을 담은 문자열
     ②b 성공 꼴 하나로 끝난다 — 본문이 한 문장이고 그것이 `pass` · `continue` · 맨 `return` ·
        `return None|True|0|{}|[]|()|set()|dict()|list()` · 상수만 쓴 식 문장(`...` · 문자열)이다
  ③ 사유가 없다 — except 줄 주석에 `noqa: BLE001 — <사유>` 가 없다(표시만 있고 사유가 없으면 위반)
셋이 겹치면 위반이다. 좁은 except · 실패(FAIL)로 남기는 넓은 except 는 보지 않는다.
②b 는 본문이 두 문장 이상이면 보지 않는다 — 정리 뒤 다시 던지는 꼴(`fh.close(); raise`) · 실패를 모은 뒤 계속하는
꼴(`fails.append(e); continue`)은 결함을 삼키지 않는다. `False` · `1` · 메시지를 담은 튜플(`return {}, "실행 실패…"`)은
실패를 알리는 값이라 성공 꼴이 아니다.
한계: 핸들러 본문의 문장만 본다 — 값을 넣어 두고 핸들러 밖에서 돌려주는 꼴(`code = OK` 뒤 아래의 `return code`)과
성공 값을 담은 이름(`return OK`)은 잡지 않는다.

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
EMPTY_CALLS = {"dict", "list", "set"}
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


def _is_success_value(v) -> bool:
    """맨 return · None · True · 0 · 빈 컨테이너. ⛔ False(== 0)는 실패를 알리는 값이라 빼고, 인자가 있는 호출은 빈 것이 아니다."""
    if v is None:
        return True
    if isinstance(v, ast.Constant):
        return v.value is None or v.value is True or (type(v.value) is int and v.value == 0)
    if isinstance(v, (ast.Dict, ast.List, ast.Tuple)):
        return not (v.keys if isinstance(v, ast.Dict) else v.elts)
    if isinstance(v, ast.Call):
        return isinstance(v.func, ast.Name) and v.func.id in EMPTY_CALLS and not v.args and not v.keywords
    return False


def _success_shaped(handler: ast.ExceptHandler) -> bool:
    """본문이 성공 꼴 한 문장뿐이다. ⛔ 두 문장 이상(정리 뒤 raise · 실패를 모은 뒤 continue/return)은 보지 않는다."""
    if len(handler.body) != 1:
        return False
    s = handler.body[-1]
    if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant):
        return True   # `...` · 문자열 같은 상수 식 문장은 pass 처럼 아무것도 하지 않는다
    return isinstance(s, (ast.Pass, ast.Continue)) or (isinstance(s, ast.Return) and _is_success_value(s.value))


def scan_source(src: str, rel: str):
    """(넓은 except 수, 위반 목록). ⛔ 파싱 실패는 SyntaxError 로 올린다 — 호출자가 UNRUN 으로 낸다."""
    tree = ast.parse(src, filename=rel)
    lines = src.splitlines()
    broad, hits = 0, []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or not _is_broad(node.type):
            continue
        broad += 1
        if _yields_unrun(node):
            what = "UNRUN 을 낸다 — 내용 이상까지 '판정 불가' 로 덮는다"
            tag = " (F-396)"
        elif _success_shaped(node):
            seg = ast.get_source_segment(src, node.body[-1]) or type(node.body[-1]).__name__
            what = f"성공 꼴 `{seg}` 하나로 끝난다 — 결함까지 '통과' 로 덮는다"
            tag = ""
        else:
            continue
        line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
        if REASON_RE.search(line):
            continue
        hits.append(f"{rel}:{node.lineno}: 넓은 except 가 {what}. "
                    f"좁히거나 except 줄에 `# noqa: BLE001 — <왜 넓게 잡는가>` 를 적는다{tag}")
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
        # 성공 꼴 축 — 본문이 성공 꼴 한 문장뿐이면 결함까지 '통과' 로 덮인다
        ("success-return-empty-dict-flagged", "except Exception:", "return {}", 1),
        ("success-pass-flagged", "except Exception:", "pass", 1),
        ("success-continue-flagged", "except Exception:", "continue", 1),
        ("success-return-none-marker-only-flagged", "except Exception:  # noqa: BLE001", "return None", 1),
        ("success-bare-return-flagged", "except BaseException:", "return", 1),
        ("success-return-true-flagged", "except Exception:", "return True", 1),
        ("success-return-0-flagged", "except Exception:", "return 0", 1),
        ("success-return-empty-list-flagged", "except:", "return []", 1),
        ("success-return-empty-tuple-flagged", "except (ValueError, Exception):", "return ()", 1),
        ("success-return-set-call-flagged", "except Exception:", "return set()", 1),
        ("success-return-dict-call-flagged", "except Exception:", "return dict()", 1),
        ("success-return-list-call-flagged", "except Exception:", "return list()", 1),
        ("success-ellipsis-flagged", "except Exception:", "...", 1),
        ("success-string-flagged", "except Exception:", '"""swallow"""', 1),
        ("success-constant-expr-reason-allowed", "except Exception:  # noqa: BLE001 — 선택 기능이라 실패는 건너뛴다", "...", 0),
        ("constant-then-raise-ignored", "except Exception:", '"note"; raise', 0),
        ("success-reason-allowed", "except Exception:  # noqa: BLE001 — 탐색 실패는 통과다", "return None", 0),
        ("success-narrow-except-ignored", "except (OSError, ValueError):", "pass", 0),
        ("cleanup-reraise-ignored", "except Exception:", "fh.close(); raise", 0),
        ("collect-then-continue-ignored", "except Exception as e:", "fails.append(e); continue", 0),
        ("collect-then-return-ignored", "except Exception as e:", "fails.append(e); return", 0),
        ("return-false-not-success", "except Exception:", "return False", 0),
        ("return-message-tuple-not-success", "except Exception as e:", 'return {}, f"실행 실패: {e}"', 0),
        ("return-nonempty-dict-not-success", "except Exception:", 'return {"k": 1}', 0),
        ("return-call-with-args-not-success", "except Exception:", "return list(items)", 0),
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

    # 축별 메시지 — 성공 꼴 위반은 UNRUN 문구가 아니라 돌려준 값과 '통과' 로 읽힌다는 문구를 낸다
    try:
        _, hits = scan_source(body.format(exc="except Exception:", act="return {}"), "x.py")
        if len(hits) == 1 and "성공 꼴" in hits[0] and "`return {}`" in hits[0] and "UNRUN" not in hits[0]:
            ok("success-axis-message")
        else:
            fails.append(f"success-axis-message: {hits}")
    except Exception as e:  # ⛔ 케이스 하나의 예외가 나머지를 가리지 않게 그 케이스의 FAIL 로 남긴다
        fails.append(f"success-axis-message: 예외 {type(e).__name__}: {e}")

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
    tree({"scripts/a.py": "x = 1\n", "mods/m/hooks/b.py": body.format(exc="except Exception:", act="return {}")}, 2, VIOLATION,
         "success-shaped-tree-violation")

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
