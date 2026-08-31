#!/bin/bash
# diff-parse: hunk-state — 대조용 python oracle 이 `h` 를 추적한다.
#   ⛔ oracle 이 같은 함정을 밟으면 두 구현이 같이 틀려도 통과한다.
# numstat_fallback.awk 회귀 판정 — patch 별 추가·삭제 행 수를 독립 구현과 대조한다.
#
# ⛔ 이 폴백은 PR 경로에서 **항상** 돈다(`git diff --numstat` 이 로컬 ref 부재로 실패).
#    그런데 테스트가 0건이었고, 실제로 두 가지를 잃고 있었다:
#      · 빈 추가 행 (`+` 단독)        — 6줄 변경을 5줄로 셌다
#      · `++ actor` 를 추가한 행      — diff 를 담은 diff
#    변경 규모는 auto-tier 입력이라 과소계상은 **낮은 Tier 로 기울게** 만든다 (조용한 실패).
#
# 판정자는 awk 를 다시 구현하지 않고 **다른 언어로 독립 구현**한 oracle 을 쓴다.
# exit: 0 일치 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ⛔ 저장소에 쓰지 않는다 — fixture 가 실행마다 자기 입력을 재작성하면 커밋본과 heredoc 중
#   어느 쪽이 SSOT 인지 모호해지고, 실행이 워킹트리를 더럽힌다(F-024 축).
#   커밋된 `blank-and-delete-only.patch` 는 **참조용 기록**이고 판정 입력은 tmp 에서 만든다.
TMPD="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }
trap 'rm -rf "$TMPD"' EXIT
AWKF="$HERE/../../../../skills/fz-peer-review/scripts/numstat_fallback.awk"
PATCHES="$HERE/../risk-scan"
[ -f "$AWKF" ] || { echo "numstat_fallback.awk 없음: $AWKF" >&2; exit 2; }

# 이 fixture 고유 케이스 — 빈 추가 행 + 삭제만 있는 파일
cat > "$TMPD/blank-and-delete-only.patch" <<'PATCH'
diff --git a/A.ext b/A.ext
--- a/A.ext
+++ b/A.ext
@@ -1,1 +1,4 @@
 keep
+
+added
+
diff --git a/B.ext b/B.ext
--- a/B.ext
+++ b/B.ext
@@ -1,3 +1,1 @@
 keep
-gone one
-gone two
PATCH

fail=0
for f in "$PATCHES"/*.patch "$HERE"/*.patch; do
  [ -f "$f" ] || continue
  name="$(basename "$f" .patch)"
  got="$(awk -f "$AWKF" "$f" | sort)"
  want="$(python3 - "$f" <<'PY'
import sys
h = False
add, dele, order = {}, {}, []
cur = None
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.rstrip("\n")
    if line.startswith("diff --git "):
        h = False
        continue
    if not h and line.startswith("+++ "):
        cur = line.split()[1]
        if cur not in order:
            order.append(cur)
        continue
    if line.startswith("@@"):
        h = True
        continue
    if not h or cur is None:
        continue
    if line.startswith("+"):
        add[cur] = add.get(cur, 0) + 1
    elif line.startswith("-"):
        dele[cur] = dele.get(cur, 0) + 1
for k in order:
    if k in add or k in dele:
        print("%d\t%d\t%s" % (add.get(k, 0), dele.get(k, 0), k))
PY
)"
  want="$(printf '%s\n' "$want" | sort)"
  if [ "$got" = "$want" ]; then
    echo "PASS  $(printf '%-30s' "$name") $(printf '%s' "$got" | tr '\n' ';')"
  else
    echo "FAIL  $(printf '%-30s' "$name") awk[$(printf '%s' "$got" | tr '\n' ';')] ≠ oracle[$(printf '%s' "$want" | tr '\n' ';')]"
    fail=$((fail+1))
  fi
done

# ⛔ 회귀 못박기 — 위 대조는 두 구현이 **같이** 틀리면 통과한다. 알려진 정답을 직접 고정한다.
pin() {
  local patch="$1" expect="$2"
  local got; got="$(awk -f "$AWKF" "$patch" | awk -F'\t' '{s+=$1} END{print s+0}')"
  if [ "$got" = "$expect" ]; then echo "PASS  고정: $(basename "$patch" .patch) 추가 $expect"
  else echo "FAIL  고정: $(basename "$patch" .patch) 추가 기대 $expect, 실제 $got"; fail=$((fail+1)); fi
}
pin "$PATCHES/positive-hunk-plus-no-loss.patch" 2   # `++ actor` 를 잃으면 1
pin "$PATCHES/positive-concurrency.patch" 6         # 빈 추가 행을 잃으면 5
pin "$TMPD/blank-and-delete-only.patch" 3           # 빈 행 2개 포함

echo
echo "$fail 건 실패"
exit $((fail ? 1 : 0))
