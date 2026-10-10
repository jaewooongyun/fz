#!/bin/bash
# diff-parse: not-a-diff — 이 러너는 diff 를 파싱하지 않는다. 합성 훅 본문을 문자열로 임시 트리에 쓰고, 트리의 훅·lint 를 실행해 exit·JSON 만 본다
# pre-commit 추가 줄 판정 · 확장자 없는 훅의 diff 파서 lint 편입 (F-380 · DG-12=approve).
#
# ⛔ 훅을 **실제로 돌린다** — 임시 git 저장소에 합성 staged 변경을 만들고, 트리의 `.githooks/pre-commit` 을 그 저장소를
#    cwd 로 실행한다. 임시 저장소에 core.hooksPath 를 걸지 않고 커밋도 훅 경유로 하지 않는다(기준선 커밋만 임시 저장소 안).
#    바깥 git 설정(전역 · 시스템)을 끊는다 — 사용자의 hooksPath · color · diff 설정이 판정을 바꾸지 않게.
#   훅 셀 (modules/ = 훅 범위 안 · 차단 패턴은 가짜 사용자 /Users/fixture-user/):
#     plus-lead      추가 줄 '+ see /Users/fixture-user/…'  (diff 줄 '++ see …')  → 차단(exit 1) — 기준 훅은 놓친다
#     plusplus-lead  추가 줄 '++ /Users/fixture-user/…'     (diff 줄 '+++ /Users/…') → 차단 — 헤더 모양이지만 hunk 안이다
#     dash-lead      추가 줄 '- see /Users/fixture-user/…'  → 차단 (대조 — 두 트리 모두)
#     clean          추가 줄 '+ ok' · 빈 줄                  → 통과 (오탐 대조)
#     header-path    새 파일 modules/Users/fixture-user/n.md(내용 깨끗) → 통과 — 헤더 '+++ b/…' 는 추가 줄이 아니다
#     deleted        기준선의 '+ old /Users/fixture-user/…' 줄 삭제 → 통과 — 지운 줄은 추가 줄이 아니다
#     out-of-scope   범위 밖 notes/x.md 의 plus-lead 줄       → 통과 — 훅 범위(SCOPED_RE)는 그대로다
#   lint 셀 (판정 확장자는 lint --json 결과의 ext 로 본다 — scan 경로를 거친 값이다. 기준 lint 는 확장자 없는 파일을 스캔하지 않아 'absent'):
#     live           트리 자신의 lint --json 결과에 .githooks/pre-commit 이 판정 확장자 .sh · hunk-state 로 ok
#     mini-bad       임시 트리(트리의 lint 사본) — 선언 없는 합성 훅 .githooks/pre-commit · 확장자 없는 셔뱅 도구 tests/…/_shim/ 5종
#                    → 전부 위반 · exit 1
#     mini-ext       같은 결과의 판정 확장자 — 훅(bash) .sh · tool(sh) .sh · pytool(python3) .py · nodetool(node) .js ·
#                    awktool(awk -f) .awk · pltool(perl, 그 밖) .sh
#     mini-jsnote    node 정상 대조 — 셔뱅 node · diff 접두사 표현이 `//` 주석에만 → 대상 아님(.sh 로 읽으면 위반)
#     mini-data      셔뱅 없는 확장자 없는 데이터 · 바이너리는 대상 아님 · UNKNOWN 0
#     mini-good      같은 임시 트리에 트리의 실제 훅을 넣고 셔뱅 도구 5종을 지우면(jsnote · 데이터 · 바이너리는 남는다) → exit 0
# exit: 0 전건 통과 · 1 단언 실패 · 2 중첩 실행(`UNRUN:`) · 3 준비 실패(인자 · 도구 · 임시 저장소)
#   ⛔ 기능 부재(훅이 놓침 · lint 가 스캔 안 함)는 단언 실패(1)다 — 준비 실패(3)와 섞으면 '기준 exit 1' 판별이 무너진다.
# ⛔ 중첩 가드: 도는 동안 FZ_PRECOMMIT_FIXTURE=1. 안에서 다시 불리면 `UNRUN:` 을 내고 exit 2.
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리 — health-check 는 인자 없이 부른다)
set -u
if [ -n "${FZ_PRECOMMIT_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 precommit-added-lines 가 도는 중"
  exit 2
fi
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
for c in git python3 awk; do command -v "$c" >/dev/null 2>&1 || { echo "SETUP $c 부재"; exit 3; }; done
HOOK="$TREE/.githooks/pre-commit" LINT="$TREE/scripts/lint_diff_parsers.py"
[ -f "$HOOK" ] && [ -f "$LINT" ] || { echo "SETUP 훅 또는 lint 없음: $TREE"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-precommit.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home" || exit 3
: > "$TMP/gitconfig" || exit 3
export HOME="$TMP/home" GIT_CONFIG_GLOBAL="$TMP/gitconfig" GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0 FZ_PRECOMMIT_FIXTURE=1
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_CEILING_DIRECTORIES
U="/Users/fixture-user"

fail=0; nh=0; nl=0
count() { case "$1" in hook\ *) nh=$((nh + 1)) ;; lint\ *) nl=$((nl + 1)) ;; esac; }
ok() { echo "PASS  $1"; count "$1"; }
no() { echo "FAIL  $1  — $2"; fail=$((fail + 1)); count "$1"; }

# $1=이름 $2=기준선 modules/note.md 내용 — 기준선 커밋 하나(훅 경유 아님)
newrepo() {
  local r="$TMP/$1"
  git init -q "$r" && git -C "$r" config user.email f@f.f && git -C "$r" config user.name f \
    && git -C "$r" config commit.gpgsign false && mkdir -p "$r/modules" \
    && printf '%s\n' "$2" > "$r/modules/note.md" && git -C "$r" add -A && git -C "$r" commit -qm base \
    || { echo "SETUP 임시 저장소 $1 실패"; exit 3; }
  R="$r"
}
# $1=셀 $2=기대 exit $3=저장소 — 트리의 훅을 저장소 cwd 로 직접 실행한다
hook() {
  (cd "$3" && bash "$HOOK") > "$3.out" 2>&1
  local rc=$?
  if [ "$rc" -eq "$2" ]; then ok "hook $1: exit $2"; else no "hook $1: exit $2 기대" "exit $rc · $(grep -m1 -E 'pre-commit|⛔' "$3.out" | cut -c1-120)"; fi
}
# $1=셀 $2=추가할 줄 — modules/note.md 끝에 붙여 stage
appendcell() {
  newrepo "$1" "base line"
  printf '%s\n' "$2" >> "$R/modules/note.md" && git -C "$R" add modules/note.md || { echo "SETUP stage 실패 $1"; exit 3; }
}

appendcell plus-lead "+ see $U/dev/x";        hook plus-lead 1 "$R"
# 추출 단계(awk)가 죽으면 막는다 — 기준 훅은 awk 를 쓰지 않아 grep 만으로 이미 막는다(두 트리 모두 1)
appendcell awk-fail "+ see $U/dev/x"
FAKE="$TMP/fake-awk"; mkdir -p "$FAKE" && printf '%s\n' '#!/bin/sh' 'exit 2' > "$FAKE/awk" && chmod +x "$FAKE/awk" || { echo "SETUP fake awk"; exit 3; }
(cd "$R" && PATH="$FAKE:$PATH" bash "$HOOK") > "$R.out" 2>&1; rc=$?
if [ "$rc" -ne 0 ]; then ok "hook awk-fail: 추가 줄 추출이 실패하면 막는다(exit $rc)"; else no "hook awk-fail: 추가 줄 추출이 실패하면 막는다" "exit 0 — fail-open"; fi
appendcell plusplus-lead "++ $U/dev/x";       hook plusplus-lead 1 "$R"
appendcell dash-lead "- see $U/dev/x";        hook dash-lead 1 "$R"
appendcell clean "+ ok"
printf '\n' >> "$R/modules/note.md" && git -C "$R" add modules/note.md || exit 3
hook clean 0 "$R"

newrepo header-path "base line"
mkdir -p "$R/modules/Users/fixture-user" && printf 'clean\n' > "$R/modules/Users/fixture-user/n.md" \
  && git -C "$R" add -A || exit 3
hook header-path 0 "$R"

newrepo deleted "+ old $U/dev/x"
printf 'base line\n' > "$R/modules/note.md" && git -C "$R" add modules/note.md || exit 3
hook deleted 0 "$R"

newrepo out-of-scope "base line"
mkdir -p "$R/notes" && printf '%s\n' "+ see $U/dev/x" > "$R/notes/x.md" && git -C "$R" add -A || exit 3
hook out-of-scope 0 "$R"

# ── lint 셀 ──────────────────────────────────────────────────
# $1=lint 스크립트 $2=--json 출력 파일 — exit 를 돌려준다
# ⛔ lint 의 traceback 은 위반(exit 1)이 아니라 측정 불가 — 3 으로 끝낸다(오류 없는 비정상 종료가 1 로 새지 않게)
lintjson() {
  python3 "$1" --json > "$2" 2> "$2.err"; local r=$?
  if grep -q "Traceback (most recent call last)" "$2.err"; then echo "SETUP lint traceback — $(tail -n 1 "$2.err")"; exit 3; fi
  return $r
}
# $1=JSON $2=파일 상대경로 — 그 파일의 "verdict ext mode" 를 한 줄로(없으면 'absent').
#   ext = lint 가 정한 판정 확장자(scan 경로의 --json 결과 · 키가 없는 lint 는 '-')
verdict() {
  python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));r=[x for x in d["results"] if x["file"]==sys.argv[2]];print(("%s %s %s"%(r[0]["verdict"],r[0].get("ext") or "-",r[0]["mode"] or "-")) if r else "absent")' "$1" "$2" \
    || { echo "SETUP lint --json 파싱 실패"; exit 3; }
}

lintjson "$LINT" "$TMP/live.json"; rc=$?
[ "$rc" -le 1 ] || { echo "SETUP 트리 lint exit $rc (UNKNOWN)"; exit 3; }
v=$(verdict "$TMP/live.json" ".githooks/pre-commit") || { echo "$v"; exit 3; }
case "$v" in
  "ok .sh hunk-state"*) ok "lint live: .githooks/pre-commit 이 스캔되고 판정 확장자 .sh · hunk-state 로 ok" ;;
  *) no "lint live: .githooks/pre-commit 이 스캔되고 판정 확장자 .sh · hunk-state 로 ok" "$v" ;;
esac

M="$TMP/mini" X="$TMP/mini/tests/fixtures/x"
mkdir -p "$M/scripts" "$M/.githooks" "$X/_shim" || exit 3
cp "$LINT" "$M/scripts/lint_diff_parsers.py" || exit 3
printf '%s\n' '#!/usr/bin/env bash' 'git diff --cached -U0 | grep -E "^\+[^+]"' > "$M/.githooks/pre-commit" || exit 3
# 확장자 없는 셔뱅 도구 5종 — 전부 선언 없는 diff 접두사 판정 코드(→ 위반). 셔뱅 인터프리터별 기대 판정 확장자는 아래 표
printf '%s\n' '#!/bin/sh' "grep '^+' \"\$1\"" > "$X/_shim/tool" || exit 3
printf '%s\n' '#!/usr/bin/env python3' 'import sys' 'for l in sys.stdin:' '    if l.startswith("+"):' '        print(l)' > "$X/_shim/pytool" || exit 3
printf '%s\n' '#!/usr/bin/env node' 'for (const l of require("fs").readFileSync(0, "utf8").split("\n")) if (l.startsWith("+")) console.log(l);' > "$X/_shim/nodetool" || exit 3
printf '%s\n' '#!/usr/bin/awk -f' '/^\+/ { print }' > "$X/_shim/awktool" || exit 3
printf '%s\n' '#!/usr/bin/perl' 'while (<>) { print if /^\+/ }' > "$X/_shim/pltool" || exit 3
# node 정상 대조 — diff 접두사 표현이 `//` 주석 줄에만 있다. .js 로 읽으면 주석이 걷혀 파서 아님(결과에 없음),
#   .sh 로 읽으면 `//` 줄이 코드로 남아 위반이다 — 셔뱅 판정을 전부 .sh 로 내는 lint 를 행동으로 거부한다
printf '%s\n' '#!/usr/bin/env node' '// if (l.startsWith("+")) — 설명 속 예시다. 이 도구는 diff 를 읽지 않는다' 'console.log("ok");' > "$X/jsnote" || exit 3
printf '%s\n' "grep '^+' 셔뱅 없는 데이터" > "$X/data" || exit 3
printf '\377\376\000\001\n' > "$X/blob" || exit 3
lintjson "$M/scripts/lint_diff_parsers.py" "$TMP/mini.json"; rc=$?
[ "$rc" -le 2 ] || { echo "SETUP mini lint exit $rc"; exit 3; }
vh=$(verdict "$TMP/mini.json" ".githooks/pre-commit") || { echo "$vh"; exit 3; }; vj=$(verdict "$TMP/mini.json" "tests/fixtures/x/jsnote") || { echo "$vj"; exit 3; }
vd=$(verdict "$TMP/mini.json" "tests/fixtures/x/data") || { echo "$vd"; exit 3; }; vb=$(verdict "$TMP/mini.json" "tests/fixtures/x/blob") || { echo "$vb"; exit 3; }
nu=$(python3 -c 'import json,sys;print(len(json.load(open(sys.argv[1]))["unknown"]))' "$TMP/mini.json") || exit 3
bad_v="" bad_e=""
eh="${vh#* }"; eh="${eh%% *}"
[ "$vh" != absent ] && [ "$eh" = .sh ] || bad_e="$bad_e hook=${eh}(기대 .sh)"
for t in tool:.sh pytool:.py nodetool:.js awktool:.awk pltool:.sh; do
  n="${t%%:*}" want="${t#*:}"
  v=$(verdict "$TMP/mini.json" "tests/fixtures/x/_shim/$n") || { echo "$v"; exit 3; }
  [ "${v%% *}" = violation ] || bad_v="$bad_v $n=$v"
  e="${v#* }"; e="${e%% *}"
  [ "$v" != absent ] && [ "$e" = "$want" ] || bad_e="$bad_e $n=${e}(기대 $want)"
done
if [ "$rc" -eq 1 ] && [ "${vh%% *}" = violation ] && [ -z "$bad_v" ]; then
  ok "lint mini-bad: 선언 없는 .githooks 훅 · 확장자 없는 셔뱅 도구 5종(sh · python3 · node · awk · perl)이 위반 (exit 1)"
else
  no "lint mini-bad: 선언 없는 .githooks 훅 · 확장자 없는 셔뱅 도구 5종이 위반 (exit 1)" "exit $rc · hook=$vh ·$bad_v"
fi
if [ -z "$bad_e" ]; then
  ok "lint mini-bad: 셔뱅 판정 확장자 python→.py · node→.js · awk→.awk · sh·perl→.sh · 훅 bash→.sh"
else
  no "lint mini-bad: 셔뱅 판정 확장자 python→.py · node→.js · awk→.awk · sh·perl→.sh · 훅 bash→.sh" "$bad_e"
fi
if [ "$vj" = absent ]; then
  ok "lint mini-bad: node 정상 대조 — '//' 주석에만 접두사 표현 → 대상 아님(.js 주석 규칙으로 읽힌다)"
else
  no "lint mini-bad: node 정상 대조 — '//' 주석에만 접두사 표현 → 대상 아님" "jsnote=$vj ('//' 주석 줄을 코드로 읽었다 — .js 주석 규칙 미적용)"
fi
if [ "$vd" = absent ] && [ "$vb" = absent ] && [ "$nu" = 0 ]; then
  ok "lint mini-bad: 셔뱅 없는 확장자 없는 파일(데이터 · 바이너리)은 대상 아님 · UNKNOWN 0"
else
  no "lint mini-bad: 셔뱅 없는 확장자 없는 파일은 대상 아님 · UNKNOWN 0" "data=$vd · blob=$vb · unknown=$nu"
fi

cp "$HOOK" "$M/.githooks/pre-commit" \
  && rm -f "$X/_shim/tool" "$X/_shim/pytool" "$X/_shim/nodetool" "$X/_shim/awktool" "$X/_shim/pltool" || exit 3
lintjson "$M/scripts/lint_diff_parsers.py" "$TMP/mini2.json"; rc=$?
if [ "$rc" -eq 0 ]; then ok "lint mini-good: 트리의 실제 훅 · node 정상 대조 · 데이터 · 바이너리만 있으면 exit 0"
else no "lint mini-good: 트리의 실제 훅 · node 정상 대조 · 데이터 · 바이너리만 있으면 exit 0" "exit $rc · hook=$(verdict "$TMP/mini2.json" .githooks/pre-commit) · jsnote=$(verdict "$TMP/mini2.json" tests/fixtures/x/jsnote)"; fi

echo
echo "$fail 건 실패"
[ "$fail" -eq 0 ] || exit 1
echo "PRECOMMIT_ADDED_LINES_OK 훅 ${nh}셀 · lint ${nl}셀"
