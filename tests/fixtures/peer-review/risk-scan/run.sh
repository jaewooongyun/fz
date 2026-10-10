#!/bin/bash
# risk_scan.py 회귀 판정 — expected.json 과 실제 출력을 대조한다.
#
# ⛔ 눈으로 보지 않는다. 표를 읽고 "맞네" 하는 것은 판정이 아니다 —
#    다음 사람이 같은 표를 다시 읽어야 하고, 기대값이 어디에도 고정되지 않는다.
#
# 비교 키: risk · added_lines · tier_delta · files · removed_paths — 셀의 expected 에 적힌 키만 본다.
#   removed_paths = 삭제 행이 1줄 이상 귀속된 경로(정렬). --json 출력에 없는 값이라 risk_scan.py 를 모듈로 읽어
#   added_lines_by_file 의 removed 키를 본다(F-381 — 수정 전 트리는 삭제 파일을 '/dev/null' 한 키로 모았다).
# usage: run.sh [--tree <플러그인 트리>]   그 트리의 risk_scan.py 를 이 폴더의 expected.json · patch 로 판정한다
#        (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
# exit: 0 전건 일치 / 1 불일치 / 3 준비 실패(인자 · risk_scan.py · expected.json · 셀 patch 부재 · risk_scan 비0 ·
#       JSON 아님 · 단언기 예외 · 판정 줄 없이 끝남)
#   ⛔ 준비 실패를 1 로 내면 '기준 트리 exit 1' 이 결함 재현 없이 통과한다 — 그래서 3 이다.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(cd "$HERE/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "PREP  --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "PREP  --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "PREP  알 수 없는 인자: $1 (사용법: run.sh [--tree <dir>])"; exit 3 ;;
  esac
done
SCAN="$TREE/skills/fz-peer-review/scripts/risk_scan.py"
EXPECTED="$HERE/expected.json"

command -v python3 >/dev/null 2>&1 || { echo "PREP  python3 부재"; exit 3; }
[ -f "$SCAN" ] || { echo "PREP  risk_scan.py 를 찾을 수 없다: $SCAN"; exit 3; }
[ -f "$EXPECTED" ] || { echo "PREP  expected.json 이 없다"; exit 3; }

out="$(PYTHONDONTWRITEBYTECODE=1 python3 -B - "$SCAN" "$EXPECTED" "$HERE" 2>&1 <<'PY'
import importlib.util, json, os, subprocess, sys, traceback


def _crash(*exc):   # 단언기 고장은 3 — 미처리 예외의 기본 exit 1 은 '불일치' 와 구별되지 않는다
    traceback.print_exception(*exc)
    sys.stdout.flush()
    os._exit(3)


sys.excepthook = _crash
sys.dont_write_bytecode = True
scan, expected_path, here = sys.argv[1], sys.argv[2], sys.argv[3]
cases = json.load(open(expected_path, encoding="utf-8"))["cases"]
KEYS = ("risk", "added_lines", "tier_delta", "files", "removed_paths")


class Prep(Exception):
    """fixture 자신의 준비 실패 — exit 3."""


def removed_paths(text):
    spec = importlib.util.spec_from_file_location("risk_scan_under_test", scan)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not callable(getattr(mod, "added_lines_by_file", None)):
        raise Prep("added_lines_by_file 이 없다 — removed_paths 를 잴 수 없다: %s" % scan)
    removed = mod.added_lines_by_file(text)[1]
    return sorted(k for k, v in removed.items() if v)


fail = 0
try:
    for name in sorted(cases):
        patch = os.path.join(here, name + ".patch")
        if not os.path.exists(patch):
            raise Prep("%s: fixture 파일 없음" % name)
        r = subprocess.run([sys.executable, "-B", scan, patch, "--json"], capture_output=True, text=True)
        if r.returncode != 0:
            raise Prep("%s: risk_scan exit %d — %s" % (name, r.returncode, " ⏎ ".join(r.stderr.strip().splitlines())[-200:]))
        try:
            got = json.loads(r.stdout)
        except ValueError:
            raise Prep("%s: risk_scan 출력이 JSON 이 아니다" % name)
        exp = cases[name]
        if "removed_paths" in exp:
            with open(patch, encoding="utf-8", errors="replace") as fh:
                got["removed_paths"] = removed_paths(fh.read())
        bad = [k for k in KEYS if k in exp and got.get(k) != exp[k]]
        if bad:
            detail = ", ".join("%s: %s≠%s" % (k, got.get(k), exp[k]) for k in bad)
            print("FAIL  %-32s %s" % (name, detail)); fail += 1
        else:
            print("PASS  %-32s risk=%d added=%d" % (name, got["risk"], got["added_lines"]))
except Prep as e:
    print("PREP  %s" % e)
    sys.stdout.flush()
    os._exit(3)

print()
print("%d/%d 통과" % (len(cases) - fail, len(cases)))
print("RISK-SCAN-CELLS=%d PASS=%d FAIL=%d" % (len(cases), len(cases) - fail, fail))
sys.stdout.flush()
os._exit(1 if fail else 0)
PY
)"
rc=$?
printf '%s\n' "$out"
last="$(printf '%s\n' "$out" | LC_ALL=C grep -E '^RISK-SCAN-CELLS=[0-9]+ PASS=[0-9]+ FAIL=[0-9]+$' | tail -1)"
case "$rc" in
  0) [ -n "$last" ] && [ "$last" != "${last%FAIL=0}" ] && exit 0 ;;
  1) [ -n "$last" ] && [ "$last" = "${last%FAIL=0}" ] && exit 1 ;;
  3) exit 3 ;;
esac
echo "PREP  판정 줄 없이 끝났다 — 단언기 exit $rc (신호 · 비정상 종료). 불일치(1)로 읽지 않는다"
exit 3
