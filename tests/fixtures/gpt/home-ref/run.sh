#!/bin/bash
# 독립 런처 rollout 감사 home_ref 회귀 판정 (F-442) — 직렬화된 명령의 이스케이프 따옴표 앞 역슬래시를 경로로 먹지 않는다.
#
# F-442: home_ref() 가 원문에 `home[^\s'"]*` 를 걸어, GPT 가 허용된 저장소를 `\"<repo>\"` 꼴로 넘기자 `<repo>\` 가
#   '격리 밖 홈 경로' 로 적중해 정상 run 이 오염(exit 15)으로 버려졌다. 같은 함수가 `<repo>/../..` 탈출은 정규화 없이 통과시켰다.
# ⛔ 파일을 만들지 않는다 — 감사 규칙 블록(`ROOTS = r` ~ 감사 루프 직전)을 꺼내 문자열 단위로 잰다(independent-arm ④c 와 같은 방식).
#    홈 · 저장소 · 격리 폴더는 가짜 경로 문자열이다(실제 홈을 건드리지 않는다).
# 셀:
#   home-ref-escaped-repo     `cd \"<repo>\"` (JS 문자열 안 이스케이프 따옴표) → 적중 없음
#   home-ref-escaped-outside  `cat \"<home>/notes.md\"` → 적중(대조 — 두 트리 모두)
#   home-ref-dotdot           `cat \"<repo>/../../secret\"` → 적중(정규화 뒤 저장소 밖)
#   home-ref-plain-repo       `cat <repo>/a.ts` → 적중 없음(대조 — 두 트리 모두)
#   home-ref-shell-escape-sibling  `cat <repo>\ copy/secret.txt`(셸 이스케이프 공백 = 형제 폴더) → 적중 — 역슬래시에서 끊으면 저장소로 읽는다(GPT check)
# 끝 — 판정한 셀 집합 = 기대 셀 집합(F-408)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
# usage: run.sh [--tree <플러그인 트리>]
set -u

DONE=0 fail=0
finish() { local rc=$?; if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ] && [ "$DONE" -ne 1 ]; then echo "SETUP 판정 줄 없이 끝났다(exit $rc)"; exit 3; fi; exit "$rc"; }
trap finish EXIT
setup_fail() { echo "SETUP $*"; exit 3; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || setup_fail "fixture 경로 해석 실패"
TREE="$(cd "$HERE/../../../.." && pwd)" || setup_fail "기본 트리 해석 실패"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || setup_fail "--tree 에 경로가 없다"; TREE="$(cd "$2" 2>/dev/null && pwd)" || setup_fail "--tree 경로 없음: $2"; shift 2 ;;
    *) setup_fail "알 수 없는 인자: $1" ;;
  esac
done
EXPECT_CELLS="home-ref-escaped-repo home-ref-escaped-outside home-ref-dotdot home-ref-plain-repo home-ref-shell-escape-sibling"
L="$TREE/scripts/gpt_independent.sh"
[ -f "$L" ] || setup_fail "gpt_independent.sh 없음: $L"

OUT="$(python3 - "$L" <<'PY'
import json, os, re, shlex, sys
t = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^FZ_ART_NAMES='([^']*)'", t, re.M)
if not m or "ROOTS = r" not in t or "def home_ref(cmd):" not in t or "\ntcs, spawn" not in t:
    print("SETUP 감사 규칙 블록 경계를 찾지 못했다"); sys.exit(3)
os.environ["FZ_ART_NAMES"] = m.group(1)
home, repo, iso = "/Users/u", "/Users/u/dev/repo", "/private/tmp/iso"
env = {"re": re, "os": os, "json": json, "shlex": shlex, "home": home, "repo": repo, "iso": iso}
exec(t[t.index("ROOTS = r"):t.index("\ntcs, spawn")], env)
ref = env["home_ref"]
q = lambda c: "tools.exec_command({cmd:" + json.dumps(c) + "})"   # JS 문자열 리터럴 — 안쪽 큰따옴표가 \" 로 직렬화된다
cases = [("home-ref-escaped-repo", q('cd "%s" && ls' % repo), False),
         ("home-ref-escaped-outside", q('cat "%s/notes.md"' % home), True),
         ("home-ref-dotdot", q('cat "%s/../../secret"' % repo), True),
         ("home-ref-plain-repo", q("cat %s/a.ts" % repo), False),
         ("home-ref-shell-escape-sibling", q("cat %s\\ copy/secret.txt" % repo), True)]
for name, cmd, want in cases:
    got = ref(cmd)
    print("%s\t%s\t%s" % (name, "hit" if got else "none", got or "-"))
PY
)"; rc=$?
[ "$rc" -eq 0 ] || { printf '%s\n' "$OUT"; exit 3; }

RAN=""
ran() { case " $RAN " in *" $1 "*) ;; *) RAN="${RAN:+$RAN }$1" ;; esac; }
judge() {   # $1=셀 $2=기대(hit|none) $3=설명
  local row got path
  row=$(printf '%s\n' "$OUT" | awk -F'\t' -v c="$1" '$1==c')
  got=$(printf '%s' "$row" | cut -f2); path=$(printf '%s' "$row" | cut -f3)
  ran "$1"
  if [ "$got" = "$2" ]; then echo "PASS  $1: $3"; else echo "FAIL  $1: $3  — 기대 $2 · 실제 ${got:-없음} ($path)"; fail=$((fail + 1)); fi
}
judge home-ref-escaped-repo none "이스케이프 따옴표 안의 허용 저장소는 홈 경로 적중이 아니다"
judge home-ref-escaped-outside hit "이스케이프 따옴표 안의 저장소 밖 홈 경로는 적중"
judge home-ref-dotdot hit "\`<repo>/../..\` 탈출은 정규화 뒤 적중"
judge home-ref-plain-repo none "따옴표 없는 저장소 경로는 적중이 아니다"
judge home-ref-shell-escape-sibling hit "셸 이스케이프 공백으로 이어진 형제 폴더(\`<repo>\\ copy\`)는 적중"

want=$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u); got=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want" = "$got" ]; then echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "HOME_REF_OK ran=$(printf '%s\n' $RAN | grep -c .)"
