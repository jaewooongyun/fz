#!/bin/bash
# gather 산출물 배선 러너 (round 2 S10) — gather.sh 가 만든 것이 렌즈 · Lead 에게 닿는가.
#
# ⛔ 셀:
#   f055-evidence-path-unwired     gather.sh 가 쓰는 .md 산출물 이름 − (evidencePaths 목록 언급 ∪ 따로 넘기는 것) = 0
#                                  (F-055 — 산출물을 만들고 전달 경로에 배선하지 않았다. 따로 넘기는 것: requirements.md → intentContext ·
#                                  review-surface.md → reviewSurfacePath)
#   f123-move-drift-filtered       move_drift.py --files numstat 이 PR 밖 파일을 B · C 에서 거른다(없으면 실린다 — 대조군) ·
#                                  gather.sh 가 numstat.txt 를 --files 로 넘긴다(F-123)
#   f149-stacked-pr-ticket-mismatch  브랜치 이름 키 TKT-2 · 커밋 TKT-1(부모 몫) + TKT-2 → review-surface.md head 축에 다른 티켓 커밋 1개(F-149)
#   f149-same-ticket-no-mark       커밋이 전부 대상 키면 '다른 티켓 커밋 없음'
#   f516-gather-writes-convention-evidence  형제 클로저 둘이 가진 guard 조건을 새 클로저가 빠뜨리면 gather 가 evidence-convention.md 에 적는다
# 임시 저장소는 오프라인 · 바깥 git 설정 차단(전역 · 시스템) — 사용자 훅 · 서명 설정이 셀 결과를 바꾸지 않는다.
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패(도구 · 저장소 · 판정 줄 없이 끝남)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(cd "$HERE/../../../.." && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "PREP  --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "PREP  --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "PREP  알 수 없는 인자: $1"; exit 3 ;;
  esac
done
GATHER="$TREE/skills/fz-peer-review/scripts/gather.sh"
DRIFT="$TREE/skills/fz-peer-review/scripts/move_drift.py"
WFDOC="$TREE/modules/peer-review-workflow.md"
for f in "$GATHER" "$DRIFT" "$WFDOC"; do [ -f "$f" ] || { echo "PREP  없음: $f"; exit 3; }; done
command -v git >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1 || { echo "PREP  git · python3 필요"; exit 3; }

T="$(mktemp -d "${TMPDIR:-/tmp}/gather-wiring.XXXXXX")" || { echo "PREP  mktemp 실패"; exit 3; }
trap 'rm -rf "$T"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
G=(git -c user.email=fixture@example.com -c user.name=fixture -c commit.gpgsign=false -c init.defaultBranch=main)
fail=0 ran=0
ok() { echo "PASS  $1"; ran=$((ran + 1)); }
no() { echo "FAIL  $1 — $2"; ran=$((ran + 1)); fail=$((fail + 1)); }

# ── f055 — 정적 대조 ─────────────────────────────────────────
unwired="$(python3 - "$GATHER" "$WFDOC" <<'PY'
import re, sys
gather, doc = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
names = set(re.findall(r"\$STAGE_DIR/([A-Za-z0-9._-]+\.md)\b", gather))
passed_elsewhere = {"requirements.md", "review-surface.md"}   # intentContext · reviewSurfacePath 인자로 따로 넘긴다
lines = doc.splitlines()
i = next(k for k, l in enumerate(lines) if "`evidencePaths` 는 파일명 하나가 아니라" in l)
para = []
for l in lines[i:]:
    if para and re.match(r"^\s*-\s", l):
        break
    para.append(l)
para = "\n".join(para)
print(" ".join(sorted(n for n in names - passed_elsewhere if n not in para)))
PY
)" || { echo "PREP  f055 판독 실패"; exit 3; }
if [ -z "$unwired" ]; then ok "f055-evidence-path-unwired"; else no "f055-evidence-path-unwired" "evidencePaths 목록에 없는 gather 산출물: $unwired"; fi

# ── f123 — move_drift --files ────────────────────────────────
python3 - "$T/drift.patch" "$T/numstat.txt" <<'PY' || { echo "PREP  f123 입력 생성 실패"; exit 3; }
import sys
patch = """diff --git a/src/New.swift b/src/New.swift
new file mode 100644
--- /dev/null
+++ b/src/New.swift
@@ -0,0 +1,4 @@
+func a() {}
+func b() {}
+func c() {}
+func d() {}
diff --git a/src/Old.swift b/src/Old.swift
--- a/src/Old.swift
+++ b/src/Old.swift
@@ -1,5 +1,1 @@
-func a() {}
-func b() {}
-func c() {}
-func d() {}
 let keep = 1
diff --git a/src/Unrelated.swift b/src/Unrelated.swift
--- a/src/Unrelated.swift
+++ b/src/Unrelated.swift
@@ -1,1 +1,2 @@
 let x = 1
+let unrelatedFromBaseMerge = 2
"""
open(sys.argv[1], "w").write(patch)
open(sys.argv[2], "w").write("4\t0\tsrc/New.swift\n0\t4\tsrc/Old.swift\n")
PY
with="$(python3 "$DRIFT" "$T/drift.patch" range --files "$T/numstat.txt" 2>&1)"; wc=$?
without="$(python3 "$DRIFT" "$T/drift.patch" range 2>&1)"
if [ "$wc" -eq 0 ] && ! printf '%s' "$with" | grep -q "Unrelated.swift" && printf '%s' "$without" | grep -q "Unrelated.swift" \
   && grep -q 'move_drift.py" .*--files "$STAGE_DIR/numstat.txt"' "$GATHER"; then
  ok "f123-move-drift-filtered"
else
  no "f123-move-drift-filtered" "--files 출력 rc=$wc · Unrelated 포함=$(printf '%s' "$with" | grep -c Unrelated.swift) · 대조군 포함=$(printf '%s' "$without" | grep -c Unrelated.swift) · gather 배선=$(grep -c 'numstat.txt"' "$GATHER")"
fi

# ── 임시 저장소 — f149 · f516 ────────────────────────────────
R="$T/repo"
mkdir -p "$R/src" && "${G[@]}" -C "$R" init -q || { echo "PREP  git init 실패"; exit 3; }
SIB='final class HomeVC {
    func a() {
        cellA.onVisible = { [weak self] in
            guard let self, !isVerticalScrolling else { return }
            self.log(1)
        }
    }
    func b() {
        cellB.onVisible = { [weak self] in
            guard let self, !isVerticalScrolling else { return }
            self.log(2)
        }
    }'
printf '%s\n}\n' "$SIB" > "$R/src/HomeVC.swift"
"${G[@]}" -C "$R" add -A && "${G[@]}" -C "$R" commit -qm "TKT-0 base" || { echo "PREP  base 커밋 실패"; exit 3; }
"${G[@]}" -C "$R" checkout -qb feature/TKT-2-stack
printf 'let parent = 1\n' > "$R/src/Parent.swift"
"${G[@]}" -C "$R" add -A && "${G[@]}" -C "$R" commit -qm "TKT-1 parent PR work" || { echo "PREP  커밋 실패"; exit 3; }
printf '%s\n    func c() {\n        cellC.onVisible = { [weak self] in\n            guard let self else { return }\n            self.log(3)\n        }\n    }\n}\n' "$SIB" > "$R/src/HomeVC.swift"
"${G[@]}" -C "$R" commit -qam "TKT-2 this PR work" || { echo "PREP  커밋 실패"; exit 3; }
"${G[@]}" -C "$R" checkout -q main && "${G[@]}" -C "$R" checkout -qb feature/TKT-2-solo
printf 'let solo = 1\n' > "$R/src/Solo.swift"
"${G[@]}" -C "$R" add -A && "${G[@]}" -C "$R" commit -qm "TKT-2 only work" || { echo "PREP  커밋 실패"; exit 3; }

(cd "$R" && bash "$GATHER" --work-dir "$T/w1" --target feature/TKT-2-stack --base main) > "$T/g1.log" 2>&1 \
  || { echo "PREP  gather(stack) 실패 — $(tail -2 "$T/g1.log")"; exit 3; }
(cd "$R" && bash "$GATHER" --work-dir "$T/w2" --target feature/TKT-2-solo --base main) > "$T/g2.log" 2>&1 \
  || { echo "PREP  gather(solo) 실패 — $(tail -2 "$T/g2.log")"; exit 3; }

s1="$(cat "$T/w1/review-surface.md" 2>/dev/null)"
if printf '%s' "$s1" | grep -q "다른 티켓 커밋 1개" && printf '%s' "$s1" | grep -q "TKT-1 parent PR work" && ! printf '%s' "$s1" | grep -q -- "- [0-9a-f]* TKT-2"; then
  ok "f149-stacked-pr-ticket-mismatch"
else
  no "f149-stacked-pr-ticket-mismatch" "review-surface.md head 축: $(printf '%s' "$s1" | grep -A3 'head 축' | tr '\n' ' ' | cut -c1-200)"
fi
s2="$(cat "$T/w2/review-surface.md" 2>/dev/null)"
if printf '%s' "$s2" | grep -q "다른 티켓 커밋 없음 — 대상 키 \`TKT-2\`"; then ok "f149-same-ticket-no-mark"; else no "f149-same-ticket-no-mark" "$(printf '%s' "$s2" | grep -A2 'head 축' | tr '\n' ' ' | cut -c1-200)"; fi

c1="$(cat "$T/w1/evidence-convention.md" 2>/dev/null)"
if printf '%s' "$c1" | grep -q "onVisible" && printf '%s' "$c1" | grep -q '`!isVerticalScrolling`'; then
  ok "f516-gather-writes-convention-evidence"
else
  no "f516-gather-writes-convention-evidence" "evidence-convention.md: $(printf '%s' "$c1" | tail -2 | tr '\n' ' ' | cut -c1-200)"
fi

[ "$ran" -eq 5 ] || { echo "PREP  판정 셀 $ran/5 — 판정 줄 없이 끝난 셀이 있다"; exit 3; }
echo "GATHER-EVIDENCE-WIRING cells=$ran FAIL=$fail"
[ "$fail" -eq 0 ] && exit 0 || exit 1
