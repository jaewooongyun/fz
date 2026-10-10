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
# 회귀 4종:
#   S  snapshot 우선   pr-meta.json 이 있으면 gh 재조회 0회여야 한다
#   V  값 동등          snapshot 경로와 gh 경로가 같은 Tier 를 내야 한다
#   F  폴백 보존        snapshot 이 없으면 gh 경로가 살아 있어야 한다(gather 미경유 직접 호출)
#   branch  브랜치 입력 diff 실패(F-385) — 문서의 브랜치 분기 블록(`# branch input` ~ `fi` + `CHANGED_LINES=` 줄)을 뽑아
#           임시 git 리포(BASE=develop 존재 · 원격 없음 · GIT_ALLOW_PROTOCOL=file · AskUserQuestion stub)에서 실행한다.
#           없는 INPUT(feature/no-such-branch)은 0줄이 아니라 '⛔ diff 실패' 표지 + TIER=2, 정상 브랜치는 실제 변경량.
#           ⛔ 기준 블록(`2>/dev/null | awk … END{print a+0}`)은 CHANGED_LINES=0 으로 진행한다 — 이 셀이 FAIL(exit 1)
#
# usage: run.sh [--tree <플러그인 트리>] [--cells S,V,F,branch]   (기본: 이 fixture 가 든 트리 · 전 셀 — health-check 는 인자 없이 부른다)
#   --tree 는 읽을 문서(modules/peer-review-tiers.md)만 바꾼다
# exit: 0 전건 통과 / 1 불일치 / 2 실행 오류
#   ⛔ 판정 줄 없이 끝나면(셸 오류 등) 1 이 아니라 2 로 낸다 — 1 은 단언 불일치만 뜻한다
set -uo pipefail

DONE=0 TMP=""
finish() {
  local rc=$?
  [ -n "$TMP" ] && rm -rf "${TMP:?}"
  if [ "$rc" -ne 0 ] && [ "$rc" -ne 2 ] && [ "$DONE" -ne 1 ]; then
    echo "판정 줄 없이 끝났다(exit $rc) — 불일치(1)가 아니라 실행 오류 2 로 낸다" >&2
    exit 2
  fi
  exit "$rc"
}
trap finish EXIT

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$HERE/../../../.."
CELLS="S,V,F,branch"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "--tree 에 경로가 없다" >&2; exit 2; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "--tree 경로 없음: $2" >&2; exit 2; }; shift 2 ;;
    --cells) [ $# -ge 2 ] || { echo "--cells 에 값이 없다" >&2; exit 2; }; CELLS="$2"; shift 2 ;;
    *) echo "알 수 없는 인자: $1" >&2; exit 2 ;;
  esac
done
for c in $(printf '%s' "$CELLS" | tr ',' ' '); do
  case "$c" in S|V|F|branch) ;; *) echo "알 수 없는 셀: $c (지원: S,V,F,branch)" >&2; exit 2 ;; esac
done
want() { case ",$CELLS," in *",$1,"*) return 0 ;; esac; return 1; }
DOC="$TREE/modules/peer-review-tiers.md"
[ -f "$DOC" ] || { echo "peer-review-tiers.md 를 찾을 수 없다: $DOC" >&2; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "python3 이 없다" >&2; exit 2; }

TMP="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }

FAIL=0
pass() { printf 'PASS  %-34s %s\n' "$1" "$2"; }
fail() { printf 'FAIL  %-34s %s\n' "$1" "$2"; FAIL=1; }

# ── S: snapshot 우선 — 문서에 분기가 선언돼 있는가 ────────────────
if ! want S; then :
elif command grep -q 'META="\${WORK_DIR:-\$STAGE_DIR}/pr-meta.json"' "$DOC" \
   && command grep -q 'Tier 입력 = gather snapshot' "$DOC"; then
  pass "S snapshot 우선 분기" "pr-meta.json 을 1차 입력으로 선언"
else
  fail "S snapshot 우선 분기" "선언 부재 — Tier 가 gh 를 다시 부른다"
fi

# ── V: 값 동등 — snapshot 파싱이 gh 와 같은 값을 내는가 ───────────
if want V; then
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
fi   # want V

# ── F: 폴백 보존 — gather 미경유 직접 호출 경로가 살아 있는가 ─────
# ⛔ negative 성격 — snapshot 우선으로 바꾸면서 gh 경로를 지우면 gather 없는 호출이 죽는다
if ! want F; then :
elif command grep -q 'snapshot 부재 폴백' "$DOC" \
   && command grep -qE '^\s+ADDED=\$\(gh pr view' "$DOC"; then
  pass "F 폴백 보존 (negative)" "snapshot 부재 시 gh 경로가 살아 있다"
else
  fail "F 폴백 보존 (negative)" "gh 폴백이 사라졌다 — gather 미경유 호출이 0 을 받는다"
fi

# ── branch: 브랜치 입력의 diff 실패를 변경량 0 으로 읽지 않는가 (F-385) ─────
# ⛔ 문서 블록을 **그대로** 실행한다 — 문서와 실행체가 어긋나면 여기서 드러난다.
#    추출: `# branch input` 줄부터 그 뒤 첫 `fi`(0열) 앞까지 + 그 뒤 첫 `CHANGED_LINES=` 줄. 어느 쪽이든 못 찾으면 실행 오류(2)
if want branch; then
  BLOCK=$(awk 'index($0, "# branch input") {s = 1} s && /^fi$/ {exit} s' "$DOC")
  CL_LINE=$(awk 's && /^CHANGED_LINES=/ {print; exit} index($0, "# branch input") {s = 1}' "$DOC")
  # Tier 단락: CHANGED_LINES= 줄 다음부터 `# 2. --tier` 블록의 0열 `fi` 까지 — 판정 불가 TIER=2 를 auto 가 덮지 않는지(끝까지) 본다
  TAIL=$(awk 'c && /^fi$/ && t {print; exit} c {print} c && index($0, "# 2. --tier") {t = 1} s && /^CHANGED_LINES=/ {c = 1} index($0, "# branch input") {s = 1}' "$DOC")
  [ -n "$BLOCK" ] && [ -n "$CL_LINE" ] && [ -n "$TAIL" ] || { echo "브랜치 분기 블록 추출 실패: $DOC" >&2; exit 2; }
  R="$TMP/repo"
  mkdir -p "$TMP/home" && : > "$TMP/gitconfig" || exit 2
  export HOME="$TMP/home" GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 GIT_ALLOW_PROTOCOL=file
  unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE
  { git init -q -b develop "$R" && git -C "$R" config user.email t@t.t && git -C "$R" config user.name t \
    && for i in 1 2 3 4 5 6 7 8 9 10; do printf 'line %d\n' "$i"; done > "$R/a.txt" \
    && printf 'moved body\n' > "$R/old.txt" \
    && git -C "$R" add -A && git -C "$R" commit -qm base \
    && git -C "$R" checkout -q -b feature/ok \
    && sed -e '/^line 3$/d' -e '/^line 4$/d' "$R/a.txt" > "$R/a.tmp" && mv "$R/a.tmp" "$R/a.txt" \
    && for i in 1 2 3 4 5; do printf 'new %d\n' "$i"; done >> "$R/a.txt" \
    && git -C "$R" mv old.txt new.txt && git -C "$R" add -A && git -C "$R" commit -qm feature \
    && git -C "$R" checkout -q develop; } >/dev/null 2>&1 || { echo "임시 git 리포 준비 실패" >&2; exit 2; }
  [ -z "$(git -C "$R" remote)" ] || { echo "전제 불성립 — 원격이 있다" >&2; exit 2; }
  ! git -C "$R" rev-parse -q --verify feature/no-such-branch >/dev/null || { echo "전제 불성립 — 없는 브랜치가 있다" >&2; exit 2; }
  # $1=INPUT [$2=full — Tier 단락까지] — 블록을 실행하고 RESULT 줄을 낸다. AskUserQuestion 은 stub(호출을 기록하고 빈 답)
  run_block() {
    local tail_=""; [ "${2:-}" = full ] && tail_="$TAIL"
    (cd "$R" && env -u BASE -u TIER -u TIER_OPT INPUT="$1" ASK_LOG="$TMP/ask.log" bash -c '
AskUserQuestion() { printf "%s\n" "$*" >> "$ASK_LOG"; }
'"$BLOCK"'
'"$CL_LINE"'
'"$tail_"'
printf "RESULT TIER=%s CHANGED_LINES=%s ADDED=%s DELETED=%s RENAMED_LINES=%s\n" "${TIER:-unset}" "$CHANGED_LINES" "$ADDED" "$DELETED" "$RENAMED_LINES"
' 2>&1)
  }
  : > "$TMP/ask.log"
  out_bad=$(run_block feature/no-such-branch)
  res_bad=$(printf '%s\n' "$out_bad" | command grep -m1 '^RESULT ')
  if printf '%s\n' "$out_bad" | command grep -qF '⛔ diff 실패 — Tier 자동 판정 불가'; then
    pass "branch 없는 INPUT: diff 실패 표지" "feature/no-such-branch → '⛔ diff 실패 — Tier 자동 판정 불가'"
  else
    fail "branch 없는 INPUT: diff 실패 표지" "표지 없음 — ${res_bad:-RESULT 없음} (0줄로 진행)"
  fi
  case "$res_bad" in
    *"TIER=2 "*) pass "branch 없는 INPUT: TIER=2" "$res_bad" ;;
    *) fail "branch 없는 INPUT: TIER=2" "${res_bad:-RESULT 없음}" ;;
  esac
  out_full=$(run_block feature/no-such-branch full)
  res_full=$(printf '%s\n' "$out_full" | command grep -m1 '^RESULT ')
  case "$res_full" in
    *"TIER=2 "*) pass "branch 없는 INPUT: Tier 단락 뒤에도 TIER=2" "$res_full" ;;
    *) fail "branch 없는 INPUT: Tier 단락 뒤에도 TIER=2" "auto 가 덮었다 — ${res_full:-RESULT 없음}" ;;
  esac
  out_ok=$(run_block feature/ok)
  res_ok=$(printf '%s\n' "$out_ok" | command grep -m1 '^RESULT ')
  if [ "$res_ok" = "RESULT TIER=unset CHANGED_LINES=7 ADDED=5 DELETED=2 RENAMED_LINES=5" ] \
     && ! printf '%s\n' "$out_ok" | command grep -qF '⛔ diff 실패'; then
    pass "branch 정상 브랜치: 실제 변경량" "$res_ok"
  else
    fail "branch 정상 브랜치: 실제 변경량" "기대 TIER=unset CHANGED_LINES=7 ADDED=5 DELETED=2 RENAMED_LINES=5 · 실측 ${res_ok:-RESULT 없음}"
  fi
  [ ! -s "$TMP/ask.log" ] && pass "branch AskUserQuestion 호출 0" "feature/* → BASE=develop (stub 미호출)" \
    || fail "branch AskUserQuestion 호출 0" "$(head -1 "$TMP/ask.log")"
fi

echo ""
DONE=1
if [ "$FAIL" -eq 0 ]; then
  echo "0 건 실패"
  echo "⛔ 실전 1회 남음 — gather snapshot SHA 와 Tier 기록 SHA 일치 확인은 실제 PR 리뷰에서만 된다"
  exit 0
else
  echo "⛔ 불일치 발생"
  exit 1
fi
