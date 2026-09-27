#!/bin/bash
# health-check 실모드 배선 fixture (A5-03) — 배선이 장식이 아님을 **동작으로** 본다.
#
# 트리 사본 한 벌에 `health-check.sh --realmode-only` 를 두 번 돌린다.
#   1) 깨끗한 사본: 여섯 record 가 전부 ✅ · exit 2 (부분 실행은 PASS 가 아니다)
#   2) 같은 사본에 검사마다 회귀를 하나씩 심은 뒤: 여섯 record 가 전부 ⛔ · 각 비고가 **자기 plant** 를 가리킨다 · exit 1
# ⛔ plant 는 다른 검사로 번지지 않게 고른다 — 새 워크플로 파일은 census 고아가 되므로 기존 파일 끝에 덧붙인다.
# ⛔ 부분 실행은 회귀 러너 구간 전에 멈춘다 — 이 fixture 가 자기 자신을 다시 부르는 재귀는 없다.
# ⛔ 사본에서 `.git` 을 뺀다 — 워크트리의 `.git` 파일을 복사하면 사본 안 git 명령이 원 저장소를 가리킨다.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
command -v rsync >/dev/null 2>&1 || { echo "FAIL  rsync 부재 — 사본을 만들 수 없다"; exit 1; }
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
C="$T/copy"
rsync -a --exclude .git "$R/" "$C/" || { echo "FAIL  사본 생성 실패"; exit 1; }

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
NAMES=("workflow 문법" "문구 배선" "모델·effort 기준선" "동시 스폰 예산" "자산 census" "외부 명령 실존")

out="$(bash "$C/scripts/health-check.sh" --realmode-only 2>&1)"; rc=$?
[ "$rc" -eq 2 ] && ok "깨끗한 사본 exit 2 (부분 실행은 PASS 아님)" || no "깨끗한 사본 exit $rc (기대 2)"
for n in "${NAMES[@]}"; do
  printf '%s\n' "$out" | grep -qF "✅ $n | 0 |" && ok "깨끗한 사본 ✅ $n" || no "깨끗한 사본에서 $n 가 ✅ 가 아니다"
done

python3 - "$C" <<'PY' || { echo "FAIL  plant 실패"; exit 1; }
import pathlib, sys
c = pathlib.Path(sys.argv[1])

def edit(rel, fn):
    p = c / rel
    t = p.read_text(encoding="utf-8")
    n = fn(t)
    assert n != t, f"plant 가 바뀌지 않았다: {rel}"
    p.write_text(n, encoding="utf-8")

def one(t, a, b):
    assert t.count(a) >= 1, a
    return t.replace(a, b)

def downgrade(t):
    lines = t.split("\n")
    idx = [i for i, l in enumerate(lines) if "label:" in l and "agentType:" in l and "effort: 'xhigh'" in l]
    assert idx, "effort 를 낮출 호출 줄이 없다"
    lines[idx[0]] = lines[idx[0]].replace("effort: 'xhigh'", "effort: 'high'", 1)
    return "\n".join(lines)

edit("workflows/search-cross-verify.js", lambda t: t + "\nconst plantedSyntax = (\n")                       # 문법
edit("skills/fz-plan/SKILL.md", lambda t: one(t, "불변 입력", "입력 PLANTED"))                               # 문구 배선
edit("workflows/plan-lean2.js", downgrade)                                                                  # 모델·effort 기준선
edit("workflows/review-live.js",                                                                            # 동시 스폰 예산
     lambda t: t + "\nawait parallelWithRetry([\n" + "  a({ model: 'opus' }),\n" * 4 + "])\n")
(c / "modules" / "zz-planted-orphan.md").write_text("# 어디서도 경로로 불리지 않는 자산\n", encoding="utf-8")  # 자산 census
edit("modules/build.md", lambda t: t + "\n```bash\nfzplanted-tool --probe\n```\n")                          # 외부 명령 실존
PY

out="$(bash "$C/scripts/health-check.sh" --realmode-only 2>&1)"; rc=$?
[ "$rc" -eq 1 ] && ok "회귀 사본 exit 1" || no "회귀 사본 exit $rc (기대 1)"
PLANTS="search-cross-verify.js
불변 입력
plan-lean2.js::
review-live.js
zz-planted-orphan.md
fzplanted-tool"
# ⛔ 행은 exit 1(위반)이어야 한다 — 판정 불가(exit 2)도 ⛔ 로 찍히므로 표지만 보면 측정 실패를 통과로 읽는다.
# ⛔ 비고에 **다른** plant 표지가 섞이면 실패다 — 한 사본에 여섯을 심었으니 번진 실패가 우연히 맞아떨어질 수 있다.
bad() {
  local line leak="" nd
  line="$(printf '%s\n' "$out" | grep -F "⛔ $1 | 1 |")"
  while IFS= read -r nd; do
    [ "$nd" = "$2" ] && continue
    printf '%s' "$line" | grep -qF -- "$nd" && leak="$leak [$nd]"
  done <<EOF
$PLANTS
EOF
  if [ -n "$line" ] && printf '%s' "$line" | grep -qF -- "$2" && [ -z "$leak" ]; then
    ok "⛔ $1 ← $2 (exit 1 · 다른 plant 없음)"
  else
    no "$1 — 자기 plant($2)로 exit 1 이 아니거나 다른 plant 가 섞였다:${leak} ${line:-행 없음}"
  fi
}
bad "workflow 문법" "search-cross-verify.js"
bad "문구 배선" "불변 입력"
bad "모델·effort 기준선" "plan-lean2.js::"
bad "동시 스폰 예산" "review-live.js"
bad "자산 census" "zz-planted-orphan.md"
bad "외부 명령 실존" "fzplanted-tool"

echo
[ "$fail" -eq 0 ] && echo "wiring-failure: 전건 통과" || echo "wiring-failure: 실패 있음"
exit "$fail"
