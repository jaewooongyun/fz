#!/bin/bash
# check_codegraph_fresh.py 의 회귀 판정 — 진짜 sqlite 인덱스 3종으로 돌린다.
#
# ⛔ 여기서 막는 것은 "낡은 인덱스가 조용히 통과하는 것" 이다. 참조 탐색을 codegraph 로
#    옮긴 뒤에는 인덱스가 뒤처지면 영향 반경이 그만큼 비는데 산출물에는 표시가 없다.
#
# 회귀 3종:
#   N  동기 (대조)   해시가 맞으면 exit 0 — 오경보는 경고를 노이즈로 만든다
#   S  stale        파일을 바꾸면 exit 1
#   U  UNRUN        인덱스가 없으면 exit 2 — ⛔ 0(통과)으로 새면 fail-open 이다
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKER="$HERE/../../../../scripts/check_codegraph_fresh.py"
[ -f "$CHECKER" ] || { echo "checker 를 찾을 수 없다: $CHECKER" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 이 없다" >&2; exit 2; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-cg-stale.XXXXXX")" || exit 2
trap 'rm -rf "$TMP"' EXIT

REPO="$TMP/repo"
mkdir -p "$REPO/.codegraph" || exit 2
printf 'hello' > "$REPO/a.txt"

python3 - "$REPO" <<'PY' || exit 2
import hashlib, pathlib, sqlite3, sys
root = pathlib.Path(sys.argv[1])
con = sqlite3.connect(root / ".codegraph" / "codegraph.db")
con.execute("CREATE TABLE files (path TEXT, content_hash TEXT)")
con.execute("INSERT INTO files VALUES (?,?)",
            ("a.txt", hashlib.sha256((root / "a.txt").read_bytes()).hexdigest()))
con.commit(); con.close()
PY

fail=0

# N — 동기 상태는 통과해야 한다
python3 "$CHECKER" --repo "$REPO" >/dev/null
rc=$?
if [ "$rc" -ne 0 ]; then echo "  FAIL N 동기 상태가 통과하지 않는다: exit=$rc"; fail=1; fi

# S — 내용을 바꾸면 stale 로 잡혀야 한다
printf 'changed' > "$REPO/a.txt"
python3 "$CHECKER" --repo "$REPO" >/dev/null
rc=$?
if [ "$rc" -ne 1 ]; then echo "  FAIL S 변경을 stale 로 잡지 못한다: exit=$rc"; fail=1; fi

# U — 인덱스가 없으면 UNRUN(2) 이어야 한다. 0 이면 fail-open
python3 "$CHECKER" --repo "$TMP" >/dev/null
rc=$?
if [ "$rc" -ne 2 ]; then echo "  FAIL U 인덱스 부재가 UNRUN 이 아니다: exit=$rc"; fail=1; fi

# checker 자체 self-test 도 함께 돌린다
python3 "$CHECKER" --self-test >/dev/null
rc=$?
if [ "$rc" -ne 0 ]; then echo "  FAIL checker self-test 실패: exit=$rc"; fail=1; fi

if [ "$fail" -ne 0 ]; then echo "stale-gate fixture 불일치"; exit 1; fi
echo "stale-gate fixture 4/4 통과 (동기·stale·UNRUN·self-test)"
exit 0
