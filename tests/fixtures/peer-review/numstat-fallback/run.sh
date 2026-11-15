#!/bin/bash
# diff-parse: hunk-state — 대조용 python oracle 이 `h` 를 추적한다.
#   ⛔ oracle 이 같은 함정을 밟으면 두 구현이 같이 틀려도 통과한다.
# numstat_fallback.awk 회귀 판정 — patch 별 추가·삭제 행 수를 독립 구현과 대조한다.
#
# ⛔ 이 awk 는 gather.sh 의 **유일한 numstat 출처**다(PR · 브랜치 모두 diff.patch 에서 센다 — F-135 · F-350).
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


def header_b(rest):
    # awk 와 다른 방식으로 푼다 — 가운데 산술 대신 모든 공백 자리를 시도해 양쪽이 같은 경로인 자리를 찾는다.
    for i, ch in enumerate(rest):
        if ch != " ":
            continue
        a, b = rest[:i], rest[i + 1:]
        if a == b:
            return b
        for pa, pb in (("a/", "b/"), ('"a/', '"b/')):
            if a.startswith(pa) and b.startswith(pb) and a[len(pa):] == b[len(pb):]:
                return b
    return None


h = False
add, dele, order = {}, {}, []
cur = hb = None
for line in open(sys.argv[1], encoding="utf-8", errors="replace"):
    line = line.rstrip("\n")
    if line.startswith("diff --git "):
        h = False
        hb = header_b(line[len("diff --git "):])
        continue
    if not h and line.startswith("+++ "):
        # ⛔ 삭제 파일은 `+++ /dev/null` — 경로는 `diff --git` 헤더에만 남는다(F-381). 공백 경로는 `split()` 이 자르므로 줄 끝 탭만 뗀다
        cur = line[4:-1] if line.endswith("\t") else line[4:]
        if cur == "/dev/null" and hb:
            cur = hb
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

# ⛔ 경로 못박기 — 삭제 파일 행이 **실제 경로**로 귀속되는가(F-381 · E1-17 이 risk-scan 에 넣은 삭제 patch).
#    awk 와 oracle 이 같이 '/dev/null' 로 키잉하면 위 대조는 합계만 맞은 채 통과한다 — 정답 출력을 통째로 고정한다.
pin_rows() {
  local patch="$1" expect="$2"
  local got; got="$(awk -f "$AWKF" "$patch" | LC_ALL=C sort | tr '\n' ';')"
  if [ "$got" = "$expect" ]; then echo "PASS  경로: $(basename "$patch" .patch) [$got]"
  else echo "FAIL  경로: $(basename "$patch" .patch) 기대 [$expect], 실제 [$got]"; fail=$((fail+1)); fi
}
T=$'\t'
pin_rows "$PATCHES/negative-deleted-file-path.patch" "0${T}5${T}b/Sources/Legacy Cache.swift;"
pin_rows "$PATCHES/negative-deleted-files-and-doc.patch" "0${T}1${T}b/Sources/OldA.swift;0${T}1${T}b/Sources/OldB.swift;0${T}2${T}b/CHANGELOG-old.md;1${T}1${T}b/Sources/Keep.swift;"
pin_rows "$PATCHES/positive-deleted-doc-unmasks-netnew.patch" "0${T}2${T}b/docs/auth-notes.md;3${T}0${T}b/Sources/Login.swift;"
pin_rows "$PATCHES/negative-rename-file-pair.patch" "1${T}1${T}b/Sources/NewName.swift;"
pin_rows "$PATCHES/negative-binary-delete-add.patch" ""      # 바이너리는 hunk 행이 없다 — 0줄(git --numstat 은 `-` 행, 합계는 같다)
# '/dev/null' 키는 어느 patch 에서도 나오지 않아야 한다(헤더를 못 푸는 patch 가 생기면 여기서 드러난다)
dn=""
for f in "$PATCHES"/*.patch "$HERE"/*.patch "$TMPD"/*.patch; do
  [ -f "$f" ] || continue
  awk -f "$AWKF" "$f" | awk -F'\t' '$3=="/dev/null"{found=1} END{exit !found}' && dn="$dn $(basename "$f" .patch)"
done
if [ -z "$dn" ]; then echo "PASS  경로: '/dev/null' 키 0건 (전 patch)"
else echo "FAIL  경로: '/dev/null' 키가 남았다 —$dn"; fail=$((fail+1)); fi

echo
echo "$fail 건 실패"
exit $((fail ? 1 : 0))
