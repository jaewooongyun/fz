#!/bin/bash
# 품질 fixture 라벨 줄 범위 경계값 (F-335 ⑱) — 대상 트리의 scripts/check_quality_fixtures.py 의 check_review 를 합성 review
#   fixture(이 러너가 임시 폴더에 만든다)에 돌려 라벨 줄 범위 판정을 본다. health-check 글롭(tests/fixtures/*/*/run.sh)에서 인자 없이 돈다.
#   valid-range    정상 라벨 6개 → 위반 0                                                   (C — 기준 · 후보 모두 통과)
#   inverted-range line_start 6 · line_end 4(anchor 는 6번 줄과 맞춘다) → '줄 범위' 위반       (F — 기준은 hunk 포함 검사를 통과시켰다)
#   non-int-range  line_end "5"(문자열) → '줄 범위' 위반 · traceback 아님                    (F — 기준은 비교에서 TypeError)
#   end-past-hunk  9-999(파일 끝 초과) → 'hunk 밖' 위반                                       (C — RIGHT hunk 가 파일 길이를 넘지 않는다)
#   start-zero     0-0 → 'hunk 밖' 위반                                                       (C)
#   live-fixtures  대상 트리의 실제 tests/fixtures/quality 감사 → exit 0 · 위반 0               (C)
# ⛔ 러너를 tests/fixtures/quality/ 아래에 두지 않는다 — 감사가 그 폴더를 fixture 로 읽는다.
# 출력: 셀마다 `CELL <이름> <F|C> PASS|FAIL [태그]` · 끝 줄 `CELLS ran=N pass=P fail=K failed=<정렬 목록|-> names=<정렬 목록>`.
#   기대 셀 집합과 실제로 돈 집합이 다르면 FAIL(F-408). 셀 안 예외는 그 셀 FAIL(태그 exception:<종류>).
# 쓰기: 임시 폴더만(대상 트리 · 이 트리 쓰기 0 — 바이트코드도 쓰지 않는다).
# exit: 0 전 셀 통과 · 1 단언 실패 · 2 UNRUN(python3 · git 부재) · 3 준비 실패(인자 · 트리 · 임시 폴더)
# usage: run.sh [--tree <플러그인 루트>] [--cells a,b]   (기본: 이 fixture 가 든 트리 · 전 셀)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$HERE/../../../.." && pwd)"
SELF="$R"
CELLS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "SETUP --cells 에 값이 없다"; exit 3; }; CELLS="$2"; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 없음"; exit 2; }
command -v git >/dev/null 2>&1 || { echo "UNRUN: git 없음"; exit 2; }
[ -f "$R/scripts/check_quality_fixtures.py" ] || { echo "SETUP 대상 검사기 없음 $R/scripts/check_quality_fixtures.py"; exit 3; }
LIB="$SELF/tests/fixtures/quality/_lib/build_repo.sh"
[ -f "$LIB" ] || { echo "SETUP 복원 도구 없음 $LIB"; exit 3; }
# ⛔ mktemp 결과를 따로 받는다 — 치환을 바로 cd 에 넘기면 실패해도 `cd ""` 가 성공한다(F-355)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-quality-range.XXXXXX")" || { echo "SETUP mktemp 실패"; exit 3; }
trap 'rm -rf "${T0:?}"' EXIT
TD="$(cd "$T0" && pwd -P)" || { echo "SETUP 임시 폴더 정규화 실패: $T0"; exit 3; }

PYTHONDONTWRITEBYTECODE=1 python3 -I -B - "$R" "$TD" "$LIB" "$CELLS" <<'PY'
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True
TREE, TD, LIB, ONLY = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3], sys.argv[4]
EXPECTED = {"valid-range": "C", "inverted-range": "F", "non-int-range": "F", "end-past-hunk": "C", "start-zero": "C",
            "live-fixtures": "C"}
AXES6 = ["idiom", "naming", "architecture", "ui_structure", "placement", "design_alternative"]
WRAPPER = ('#!/bin/bash\nexec bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../_lib/build_repo.sh" '
           '"$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" "$@"\n')
BASE_SRC = "line1\nline2\nline3\n"
HEAD_SRC = "line1\nline2\nline3\nnew-a\nnew-b\nnew-c\nnew-d\nnew-e\nnew-f\nnew-g\n"


def load():
    sp = importlib.util.spec_from_file_location("cqf_target", os.path.join(TREE, "scripts", "check_quality_fixtures.py"))
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def fixture(name, patch=None):
    """6축 라벨(줄 4~9 · anchor new-a~new-f)인 합성 review fixture — patch 가 있으면 라벨 X0 을 그 값으로 바꾼다."""
    q = TD / name / "tests" / "fixtures" / "quality"
    (q / "_lib").mkdir(parents=True)
    shutil.copy(LIB, q / "_lib" / "build_repo.sh")
    fx = q / "r"
    (fx / "base").mkdir(parents=True)
    (fx / "head").mkdir()
    (fx / "build-repo.sh").write_text(WRAPPER)
    (fx / "base" / "a.txt").write_text(BASE_SRC)
    (fx / "head" / "a.txt").write_text(HEAD_SRC)
    (fx / "base" / "CLAUDE.md.fixture").write_text("# G\n\n## Rules\n\n- 규칙 하나\n")
    issues = [{"id": f"X{n}", "axis": ax, "severity": "major" if n < 2 else "minor", "file": "a.txt",
               "line_start": 4 + n, "line_end": 4 + n, "anchor": f"new-{'abcdef'[n]}", "rule_ref": "CLAUDE.md#Rules",
               "summary": "s"} for n, ax in enumerate(AXES6)]
    issues[0].update(patch or {})
    (fx / "labels.json").write_text(json.dumps({
        "fixture": "r", "kind": "review", "platform": "ios", "base_branch": "main", "head_branch": "feature",
        "guidelines": ["CLAUDE.md"], "axes_required": AXES6, "not_applicable_axes": [], "issues": issues,
        "conflicts": [], "forbidden_rule_citations": []}))
    return fx


def violations(m, name, patch=None):
    fx = fixture(name, patch)
    work = TD / name / "work"
    work.mkdir()
    return m.scan_common(fx) + m.check_review(fx, work)[0]


def x0(vs, needle):
    return [v for v in vs if v.startswith("X0:") and needle in v]


def cell_valid_range(m):
    vs = violations(m, "valid")
    return not vs, f"위반 {vs[:2]}"


def cell_inverted_range(m):
    vs = violations(m, "inverted", {"line_start": 6, "line_end": 4, "anchor": "new-c"})
    return bool(x0(vs, "줄 범위")), f"위반 {vs[:3]} (기대: X0 '줄 범위')"


def cell_non_int_range(m):
    vs = violations(m, "nonint", {"line_end": "5"})
    return bool(x0(vs, "줄 범위")), f"위반 {vs[:3]} (기대: X0 '줄 범위' · traceback 아님)"


def cell_end_past_hunk(m):
    vs = violations(m, "pastend", {"line_start": 9, "line_end": 999, "anchor": "new-f"})
    return bool(x0(vs, "hunk 밖")), f"위반 {vs[:3]} (기대: X0 'hunk 밖')"


def cell_start_zero(m):
    vs = violations(m, "zero", {"line_start": 0, "line_end": 0})
    return bool(x0(vs, "hunk 밖")), f"위반 {vs[:3]} (기대: X0 'hunk 밖')"


def cell_live_fixtures(m):
    r = subprocess.run([sys.executable, "-I", "-B", os.path.join(TREE, "scripts", "check_quality_fixtures.py"), "--root", TREE],
                       capture_output=True, text=True, timeout=300, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    last = (r.stdout.strip().splitlines() or [""])[-1]
    return r.returncode == 0 and "violations=0" in last, f"exit {r.returncode} · {last[:160]}"


CELLS = {"valid-range": cell_valid_range, "inverted-range": cell_inverted_range, "non-int-range": cell_non_int_range,
         "end-past-hunk": cell_end_past_hunk, "start-zero": cell_start_zero, "live-fixtures": cell_live_fixtures}


def main():
    try:
        m = load()
    except Exception as e:  # noqa: BLE001 — 대상 검사기를 싣지 못하면 준비 실패다
        print(f"SETUP 대상 검사기 적재 실패 {type(e).__name__}: {e}")
        return 3
    want = [c for c in ONLY.split(",") if c] or sorted(EXPECTED)
    unknown = [c for c in want if c not in EXPECTED]
    if unknown:
        print(f"SETUP 모르는 셀 {unknown}")
        return 3
    ran, fails = [], []
    for name in want:
        tag = ""
        try:
            ok, detail = CELLS[name](m)
        except Exception as e:  # noqa: BLE001 — 셀 안 예외는 그 셀 FAIL(traceback 은 결함 재현의 한 모양이다)
            ok, detail, tag = False, traceback.format_exc().strip().splitlines()[-1][:200], f" [exception:{type(e).__name__}]"
        ran.append(name)
        if not ok:
            fails.append(name)
        print(f"CELL {name} {EXPECTED[name]} {'PASS' if ok else 'FAIL'}{tag} — {detail}")
    if not ONLY and sorted(ran) != sorted(EXPECTED):
        print(f"FAIL 기대 셀 집합 — 빠짐 {sorted(set(EXPECTED) - set(ran))} · 더함 {sorted(set(ran) - set(EXPECTED))}")
        fails.append("cell-set")
    print(f"CELLS ran={len(ran)} pass={len(ran) - len([f for f in fails if f in ran])} fail={len([f for f in fails if f in ran])} "
          f"failed={','.join(sorted(f for f in fails if f in ran)) or '-'} names={','.join(sorted(ran))}")
    return 1 if fails else 0


sys.exit(main())
PY
