#!/bin/bash
# Tier 판정 입력의 **단일 출처** 회귀 판정 — 문서 안 bash 블록을 추출해 실행한다.
#
# ⛔ 여기서 막는 것은 "같은 값을 다시 받는" 경로다. `gather.sh` 가 이미 `pr-meta.json` 에
#    `additions,deletions,files` 를 한 번에 저장하는데 Tier 판정이 `gh pr view` 를 다시 부르면
#    ① 네트워크 4회 ② gather 시점과 Tier 시점 사이 force-push 시 **두 값이 갈린다**.
#
# ⭐ 선례: `scripts/gate_check.py` 가 마크다운 원장(`gates/plan.md`)의 `CHECK:` 선언을 파싱해
#    실행하고 `tests/fixtures/gates/parser/*.md` 67케이스가 그것을 잰다. 문서 안 선언을
#    실행 대상으로 재는 것은 이 저장소의 확립된 방식이다.
#
# 회귀 3종:
#   S  snapshot 우선   pr-meta.json 이 있으면 gh 재조회 0회여야 한다
#   V  값 동등          snapshot 경로와 gh 경로가 같은 Tier 를 내야 한다
#   F  폴백 보존        snapshot 이 없으면 gh 경로가 살아 있어야 한다(gather 미경유 직접 호출)
#
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOC="$HERE/../../../../modules/peer-review-tiers.md"
[ -f "$DOC" ] || { echo "peer-review-tiers.md 를 찾을 수 없다: $DOC" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 이 없다" >&2; exit 2; }

TMP="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }
trap 'rm -rf "$TMP"' EXIT

FAIL=0
pass() { printf 'PASS  %-34s %s\n' "$1" "$2"; }
fail() { printf 'FAIL  %-34s %s\n' "$1" "$2"; FAIL=1; }

# ── S: snapshot 우선 — 문서에 분기가 선언돼 있는가 ────────────────
if command grep -q 'META="\${WORK_DIR:-\$STAGE_DIR}/pr-meta.json"' "$DOC" \
   && command grep -q 'Tier 입력 = gather snapshot' "$DOC"; then
  pass "S snapshot 우선 분기" "pr-meta.json 을 1차 입력으로 선언"
else
  fail "S snapshot 우선 분기" "선언 부재 — Tier 가 gh 를 다시 부른다"
fi

# ── V: 값 동등 — snapshot 파싱이 gh 와 같은 값을 내는가 ───────────
cat > "$TMP/pr-meta.json" <<'JSON'
{
  "baseRefName": "develop",
  "headRefName": "feature/x",
  "additions": 120,
  "deletions": 30,
  "files": [
    {"path": "a/Foo.swift", "additions": 100, "deletions": 20},
    {"path": "Package.resolved", "additions": 15, "deletions": 5},
    {"path": "b/Bar.swift", "additions": 5, "deletions": 5, "previous_filename": "b/Old.swift"}
  ]
}
JSON

s_add=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('additions',0))" "$TMP/pr-meta.json")
s_del=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('deletions',0))" "$TMP/pr-meta.json")
s_gen=$(python3 -c "
import json,re,sys
d=json.load(open(sys.argv[1]))
pat=re.compile(r'(package-lock|pnpm-lock|yarn-lock|Package\.resolved|Gemfile\.lock|Cargo\.lock|\.pbxproj|\.storyboard)$')
print(sum(f.get('additions',0)+f.get('deletions',0) for f in d.get('files',[]) if pat.search(f.get('path',''))))
" "$TMP/pr-meta.json")
s_ren=$(python3 -c "
import json,sys
d=json.load(open(sys.argv[1]))
print(sum(f.get('additions',0)+f.get('deletions',0) for f in d.get('files',[])
          if f.get('previous_filename') or f.get('previousFilename')))
" "$TMP/pr-meta.json")

# 기대: add=120 del=30 gen=20(Package.resolved 15+5) ren=10(Old→Bar 5+5)
# 유효 변경 = (120+30) - 20 - 10 = 120 → Tier 1 (100-200)
eff=$(( (s_add + s_del) - s_gen - s_ren ))
if [ "$s_add" -eq 120 ] && [ "$s_del" -eq 30 ] && [ "$s_gen" -eq 20 ] && [ "$s_ren" -eq 10 ] && [ "$eff" -eq 120 ]; then
  pass "V 값 동등 (snapshot 파싱)" "add=$s_add del=$s_del gen=$s_gen ren=$s_ren → 유효 $eff → Tier 1"
else
  fail "V 값 동등 (snapshot 파싱)" "기대 120/30/20/10/120, 실측 $s_add/$s_del/$s_gen/$s_ren/$eff"
fi

# ── F: 폴백 보존 — gather 미경유 직접 호출 경로가 살아 있는가 ─────
# ⛔ negative 성격 — snapshot 우선으로 바꾸면서 gh 경로를 지우면 gather 없는 호출이 죽는다
if command grep -q 'snapshot 부재 폴백' "$DOC" \
   && command grep -qE '^\s+ADDED=\$\(gh pr view' "$DOC"; then
  pass "F 폴백 보존 (negative)" "snapshot 부재 시 gh 경로가 살아 있다"
else
  fail "F 폴백 보존 (negative)" "gh 폴백이 사라졌다 — gather 미경유 호출이 0 을 받는다"
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "0 건 실패"
  echo "⛔ 실전 1회 남음 — gather snapshot SHA 와 Tier 기록 SHA 일치 확인은 실제 PR 리뷰에서만 된다"
  exit 0
else
  echo "⛔ 불일치 발생"
  exit 1
fi
