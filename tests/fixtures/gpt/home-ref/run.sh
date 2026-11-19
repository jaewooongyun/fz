#!/bin/bash
# 독립 런처 rollout 감사의 홈 경로 판정 회귀 (F-442) — 직렬화된 명령의 이스케이프 따옴표 앞 역슬래시를 경로로 먹지 않는다.
#   홈 .claude 의 실경로(링크 대상) 판정도 본다 — 대상이 홈 밖이면 home_ref 가, --repo 아래면 허용 판정이 놓친다(아래 claude-real 셀).
#
# F-442: home_ref() 가 원문에 `home[^\s'"]*` 를 걸어, GPT 가 허용된 저장소를 `\"<repo>\"` 꼴로 넘기자 `<repo>\` 가
#   '격리 밖 홈 경로' 로 적중해 정상 run 이 오염(exit 15)으로 버려졌다. 같은 함수가 `<repo>/../..` 탈출은 정규화 없이 통과시켰다.
# ⛔ 문자열 셀은 파일을 만들지 않는다 — 감사 규칙 블록(`ROOTS = r` ~ 감사 루프 직전)을 꺼내 문자열 단위로 잰다(independent-arm ④c 와 같은 방식).
#    홈 · 저장소 · 격리 폴더는 가짜 경로 문자열이다(실제 홈을 건드리지 않는다).
# ⛔ 런처 셀(claude-real-grid-* · claude-real-env-pass)은 런처 전체를 가짜 CLI(../_shim)로 돌린다 — 실경로는 런처가 env
#    FZ_CLAUDE_REAL 로 감사에 넘기므로, 감사 함수만 부르면 그 전달이 빠져도(규칙이 조용히 꺼져도) 통과한다.
#    홈은 임시 폴더 아래 가짜 "실제 홈"이고(끝나면 지운다) 호출하는 쪽 env 의 FZ_CLAUDE_REAL 은 지우고 돈다.
# 셀:
#   home-ref-escaped-repo     `cd \"<repo>\"` (JS 문자열 안 이스케이프 따옴표) → 적중 없음
#   home-ref-escaped-outside  `cat \"<home>/notes.md\"` → 적중(대조 — 두 트리 모두)
#   home-ref-dotdot           `cat \"<repo>/../../secret\"` → 적중(정규화 뒤 저장소 밖)
#   home-ref-plain-repo       `cat <repo>/a.ts` → 적중 없음(대조 — 두 트리 모두)
#   home-ref-shell-escape-sibling  `cat <repo>\ copy/secret.txt`(셸 이스케이프 공백 = 형제 폴더) → 적중 — 역슬래시에서 끊으면 저장소로 읽는다(GPT check)
# F-617: 프로그램 인자(`python3 -c '…'`)는 셸 단어 하나라, 그 안에 적은 허용 저장소 경로 뒤의 코드까지 경로로 읽어 정상 run 을 버렸다.
#   home-ref-prog-arg-repo         `python3 -B -c '…Path("<repo>")\n…'` → 적중 없음
#   home-ref-prog-arg-e-repo       `node -e 'const p="<repo>"; …'` → 적중 없음
#   home-ref-prog-arg-outside      같은 꼴에 저장소 밖 홈 경로 → 적중(양성 대조 — 느슨해지지 않았다)
#   home-ref-prog-arg-dotdot       `sh -c 'cat "<repo>"/../../secret'` → 적중(프로그램 안의 `..` 탈출)
#   home-ref-prog-arg-unbalanced   프로그램을 낱말로 풀지 못한다(안 닫힌 따옴표) → 적중(단어 전체를 본다 — 보수적)
#   home-ref-nonprog-quoted-stays  `grep -c 'Path("<repo>")' a.py`(같은 글자 플래그지만 인터프리터가 아니다) → 적중(알려진 한계 — 다시 풀지 않는다)
#   home-ref-nonprog-flag-sibling  `tar -c '<repo> copy/secret'`(다른 명령의 -c 뒤 경로 — 다시 풀면 형제 폴더가 저장소로 읽힌다) → 적중
#   home-ref-prog-arg-after-pipe   `cat a | python3 -c '…Path("<repo>")…'`(조각이 바뀌면 명령 이름을 다시 잡는다) → 적중 없음
# 홈 .claude 실경로 — 문자열 셀은 FZ_CLAUDE_REAL=<대상>(홈 밖 가짜 경로)으로 규칙 블록을 읽고, 런처의 판정 사슬 순서
#   (forbid_hit → recurse_hit → home_ref)대로 규칙 이름을 본다: forbid = '금지 산출물 참조' · home = '격리 밖 홈 경로' · none = 적중 없음
#   claude-real-js-escaped-hit     function_call JSON 의 `\/` 이스케이프 `cat <대상>/…/a.jsonl` → forbid
#   claude-real-bare-hit           JS 작은따옴표 `find <대상> -name …`(맨 대상 — 끝 `/` 없음) → forbid
#   claude-real-prog-arg-hit       `python3 -c 'print(open("<대상>/…/a.jsonl").read())'` → forbid
#   claude-real-sibling-none       `cat <대상>2/…` · `ls <대상>.bak`(형제 이름) → none
#   claude-real-env-empty          env 가 비면 이 규칙은 꺼진다 — 홈 밖 대상 읽기 → none(옛 판정)
#   claude-real-home-dir           링크가 아닌 `<home>/.claude` 자체 · 맨 경로 `ls <home>/.claude` → forbid
# 런처 격자 claude-real-grid-<꼴>-<대상> — 꼴: cat(`cat P/…/a.jsonl`) · rec(`grep -rn … P`) · quoted(`cat "P/…"`) · rel(`cd P && cat …`)
#   대상 P: out(홈 밖 실경로) · sib(그 형제 경로 — 적중하지 않아야 한다) · in(홈 안 대상) · repo(--repo 아래 대상)
#   기대 'exit|규칙|격리 적용|세션 파일' — 적중이면 15 · 금지 산출물 참조 · True · 세션 제거, 형제(허용 경로 대조)는 0 · 적중 없음 · True · 세션 남음
#   claude-real-env-pass           같은 기록(홈 밖 대상 cat)이 ~/.claude 가 그 대상을 가리키는 홈에서만 15 · 실폴더 ~/.claude 홈에서는 0 —
#                                  런처가 실경로를 감사까지 넘긴다(전달이 빠지면 둘 다 0)
# 끝 — 판정한 셀 집합 = 기대 셀 집합(F-408)
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
# usage: run.sh [--tree <플러그인 트리>]
set -u

DONE=0 fail=0 T=""
finish() { local rc=$?; [ -n "$T" ] && rm -rf "${T:?}"; if [ "$rc" -ne 0 ] && [ "$rc" -ne 3 ] && [ "$DONE" -ne 1 ]; then echo "SETUP 판정 줄 없이 끝났다(exit $rc)"; exit 3; fi; exit "$rc"; }
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
EXPECT_CELLS="home-ref-escaped-repo home-ref-escaped-outside home-ref-dotdot home-ref-plain-repo home-ref-shell-escape-sibling
home-ref-prog-arg-repo home-ref-prog-arg-e-repo home-ref-prog-arg-outside home-ref-prog-arg-dotdot home-ref-prog-arg-unbalanced
home-ref-nonprog-quoted-stays home-ref-nonprog-flag-sibling home-ref-prog-arg-after-pipe
claude-real-js-escaped-hit claude-real-bare-hit claude-real-prog-arg-hit claude-real-sibling-none claude-real-env-empty claude-real-home-dir
claude-real-env-pass"
for f in cat rec quoted rel; do for p in out sib in repo; do EXPECT_CELLS="$EXPECT_CELLS claude-real-grid-$f-$p"; done; done
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
PROG = 'from pathlib import Path\nrepo=Path("%s")\ns=Path("diff.patch").read_text();n={"a":0}\nfor b in s.split("x")[1:]:\n print(b)'
cases += [("home-ref-prog-arg-repo", q("/opt/homebrew/bin/python3 -B -c '" + PROG % repo + "'"), False),
          ("home-ref-prog-arg-e-repo", q("node -e 'const p=\"%s\"; console.log(p)'" % repo), False),
          ("home-ref-prog-arg-outside", q("python3 -c '" + PROG % (home + "/notes") + "'"), True),
          ("home-ref-prog-arg-dotdot", q("sh -c 'cat \"%s\"/../../secret'" % repo), True),
          ("home-ref-prog-arg-unbalanced", q("python3 -c 'p=\"%s\" # don\\'t'" % repo), True),
          ("home-ref-nonprog-quoted-stays", q("grep -c 'Path(\"%s\")' a.py" % repo), True),
          ("home-ref-nonprog-flag-sibling", q("tar -c '%s copy/secret'" % repo), True),
          ("home-ref-prog-arg-after-pipe", q("cat a.txt | python3 -c '" + PROG % repo + "'"), False)]
for name, cmd, want in cases:
    got = ref(cmd)
    print("%s\t%s\t%s" % (name, "hit" if got else "none", got or "-"))
# 홈 .claude 실경로(링크 대상) — 런처가 FZ_CLAUDE_REAL 로 넘기는 값을 env 로 주고 규칙 블록을 다시 읽는다(정의가 읽을 때 env 를 본다).
#   규칙 이름은 런처 판정 사슬 순서(forbid_hit → recurse_hit → home_ref)를 따른다
CR = "/Volumes/x/claude-data"
def rule_of(cr):
    if cr is None:
        os.environ.pop("FZ_CLAUDE_REAL", None)
    else:
        os.environ["FZ_CLAUDE_REAL"] = cr
    e = {"re": re, "os": os, "json": json, "shlex": shlex, "home": home, "repo": repo, "iso": iso}
    exec(t[t.index("ROOTS = r"):t.index("\ntcs, spawn")], e)
    return lambda c: "forbid" if e["forbid_hit"](c) else "recurse" if e["recurse_hit"](c) else "home" if e["home_ref"](c) else "none"
why, why_empty, why_home = rule_of(CR), rule_of(None), rule_of(home + "/.claude")
sq = lambda c: "tools.exec_command({cmd:'" + c.replace("\\", "\\\\").replace("'", "\\'") + "'})"   # JS 작은따옴표 문자열
rcases = [("claude-real-js-escaped-hit", why, '{"cmd":"cat ' + (CR + "/projects/p/a.jsonl").replace("/", "\\/") + '"}'),
          ("claude-real-bare-hit", why, sq('find %s -name "*.jsonl"' % CR)),
          ("claude-real-prog-arg-hit", why, q("python3 -c 'print(open(\"%s/projects/p/a.jsonl\").read())'" % CR)),
          ("claude-real-sibling-none", why, q("cat %s2/projects/p/a.jsonl && ls %s.bak" % (CR, CR))),
          ("claude-real-env-empty", why_empty, q("cat %s/projects/p/a.jsonl" % CR)),
          ("claude-real-home-dir", why_home, q("ls %s/.claude" % home))]
for name, f, cmd in rcases:
    print("%s\t%s\t%s" % (name, f(cmd), cmd))
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
judge home-ref-prog-arg-repo none "프로그램 인자(-c) 안에 적은 허용 저장소 경로는 적중이 아니다(F-617)"
judge home-ref-prog-arg-e-repo none "프로그램 인자(-e) 안에 적은 허용 저장소 경로는 적중이 아니다"
judge home-ref-prog-arg-outside hit "프로그램 인자 안의 저장소 밖 홈 경로는 적중(양성 대조)"
judge home-ref-prog-arg-dotdot hit "프로그램 인자 안의 \`..\` 탈출은 적중"
judge home-ref-prog-arg-unbalanced hit "낱말로 풀지 못한 프로그램 인자는 단어 전체를 본다(적중)"
judge home-ref-nonprog-quoted-stays hit "프로그램 인자가 아닌 따옴표 단어는 다시 풀지 않는다(적중 — 알려진 한계)"
judge home-ref-nonprog-flag-sibling hit "다른 명령의 -c 뒤 경로는 다시 풀지 않는다(형제 폴더 적중)"
judge home-ref-prog-arg-after-pipe none "파이프 뒤 인터프리터의 프로그램 인자도 다시 푼다"
judge claude-real-js-escaped-hit forbid "function_call JSON 의 \`\\/\` 이스케이프 경로도 홈 .claude 실경로 아래면 금지 산출물 참조"
judge claude-real-bare-hit forbid "끝 \`/\` 없는 맨 대상(JS 작은따옴표 \`find <대상>\`)도 금지 산출물 참조"
judge claude-real-prog-arg-hit forbid "프로그램 인자 안의 대상 아래 경로도 금지 산출물 참조"
judge claude-real-sibling-none none "이름이 대상으로 시작하는 형제(\`<대상>2/…\` · \`<대상>.bak\`)는 적중이 아니다"
judge claude-real-env-empty none "env 가 비면 이 규칙은 꺼진다(옛 판정 — 홈 밖 대상 읽기는 적중 없음)"
judge claude-real-home-dir forbid "링크가 아닌 \`<home>/.claude\` 맨 경로도 금지 산출물 참조"

# ── 홈 .claude 실경로 — 런처 전체(가짜 CLI). 런처가 실경로(입력 게이트가 정한 CLAUDE_DIR_REAL)를 env 로 감사에 넘기는 배선까지 본다
judge_eq() {   # $1=셀 $2=실제 $3=기대 $4=설명
  ran "$1"
  if [ "$2" = "$3" ]; then echo "PASS  $1: $4"; else echo "FAIL  $1: $4  — 기대 '$3' · 실제 '$2'"; fail=$((fail + 1)); fi
}
SHIM="$(cd "$HERE/../_shim" && pwd)" || setup_fail "가짜 CLI 폴더 없음: $HERE/../_shim"
SAMPLE="$HERE/../independent-arm/sample-plan-ok.json"
[ -s "$SAMPLE" ] || setup_fail "plan 표본 없음: $SAMPLE"
for s in "$SHIM"/*; do   # ⛔ 실제 CLI 에 닿지 않게 — 가짜 CLI 폴더의 파일마다 PATH 앞에서 그 이름을 가린다(빈 폴더면 글롭이 남아 실패)
  [ "$(PATH="$SHIM:$PATH" command -v "${s##*/}")" = "$s" ] || setup_fail "PATH 앞 ${s##*/} 가 가짜 CLI 가 아니다"
done
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공한다(bash 3.2)
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-home-ref.XXXXXX")" || setup_fail "mktemp 실패"
T="$(cd "$T0" && pwd -P)" || { T="$T0"; setup_fail "임시 폴더 정규화 실패: $T0"; }
#    명령은 경로를 따옴표 없이 적는다(공백 금지) · /Users 아래면 재귀 검색 규칙이 그 뿌리를 따로 잡아 형제 대조가 흐려진다
case "$T" in *[[:space:]]*|/Users/*) setup_fail "임시 폴더가 이 러너의 전제(공백 없음 · /Users 밖)에 맞지 않는다: $T" ;; esac
printf '# 요구\n주문 취소 시 알림을 끊는다\n' > "$T/requirement.md" || setup_fail "요구 파일 작성 실패"
mkhome() {   # $1=홈 $2=~/.claude 링크 대상(빈 값이면 링크 아닌 실폴더) — 인증 파일 · --repo 로 여는 저장소를 둔다
  mkdir -p "$1/.codex" "$1/dev/repo/src" && echo '{"fake":"auth"}' > "$1/.codex/auth.json" && echo b > "$1/dev/repo/src/a.ts" || return 1
  if [ -n "$2" ]; then mkdir -p "$2/projects/p" && ln -s "$2" "$1/.claude"; else mkdir -p "$1/.claude/projects/p"; fi
}
HO="$T/h-out" HI="$T/h-in" HR="$T/h-repo" HP="$T/h-plain"
mkhome "$HO" "$T/claude-out" && mkhome "$HI" "$HI/claude-data" && mkhome "$HR" "$HR/dev/repo/claude-data" && mkhome "$HP" "" \
  || setup_fail "가짜 홈 구성 실패"
roll() {   # $1=rollout 파일 $2=홈 $3=명령 — turn_context 에 그 홈 deny(격리 적용) · JS 큰따옴표 문자열 도구 호출 하나
  python3 - "$@" <<'PY'
import json, sys
f, home, cmd = sys.argv[1:4]
ents = [{"path": {"type": "path", "path": home}, "access": "deny"}, {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": ents}}}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": "tools.exec_command({cmd:" + json.dumps(cmd) + "})"}}]
open(f, "w", encoding="utf-8").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
PY
}
launch() {   # $1=이름 $2=홈 $3=명령 → $T/c-<이름>/. 호출하는 쪽 env 의 FZ_CLAUDE_REAL · 선택 폴더는 지운다(런처가 넘기는 값만 감사에 닿는다)
  local d="$T/c-$1"
  mkdir -p "$d/out" && roll "$d/rollout.jsonl" "$2" "$3" || setup_fail "rollout 생성 실패: $1"
  env -u CODEX_HOME -u FZ_GPT_CHOICE_DIR -u FZ_CLAUDE_REAL PATH="$SHIM:$PATH" HOME="$2" CLAUDE_CODE_SESSION_ID=home-ref-no-choice \
    FZ_TELEMETRY_DIR="$d/tel" FZ_SHIM_OUTPUT="$(cat "$SAMPLE")" FZ_SHIM_ROLLOUT="$d/rollout.jsonl" \
    bash "$L" plan --requirement "$T/requirement.md" --repo "$2/dev/repo" --arm A --run-id "$1" --out-dir "$d/out" > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"
}
verdict() {   # $1=이름 → 'exit|첫 적중 규칙(없으면 -)|격리 적용|세션 파일(감사 sessionFile 과 파일이 함께 있으면 있음 · 함께 없으면 없음)'
  python3 - "$T/c-$1" "A-$1" <<'PY'
import json, os, sys
d, stem = sys.argv[1], sys.argv[2]
rc = open(os.path.join(d, "rc"), encoding="utf-8").read().strip()
try:
    a = json.load(open(os.path.join(d, "out", stem + ".audit.json"), encoding="utf-8"))
except (OSError, ValueError):
    print(rc + "|감사 없음|-|-"); sys.exit(0)
hits = a.get("hits") or []
sess = os.path.join(d, "out", stem + ".json.session")
on = os.path.isfile(sess)
st = "있음" if on and a.get("sessionFile") == sess else "없음" if not on and a.get("sessionFile") is None else "어긋남"
print("%s|%s|%s|%s" % (rc, hits[0]["rule"] if hits else "-", a.get("isolationApplied"), st))
PY
}
grid() {   # $1=꼴 $2=대상 $3=기대
  local h p cmd
  case "$2" in out) h="$HO" p="$T/claude-out" ;; sib) h="$HO" p="$T/claude-out2" ;; in) h="$HI" p="$HI/claude-data" ;; repo) h="$HR" p="$HR/dev/repo/claude-data" ;; esac
  case "$1" in
    cat) cmd="cat $p/projects/p/a.jsonl" ;;
    rec) cmd="grep -rn sessionId $p" ;;
    quoted) cmd="cat \"$p/projects/p/a.jsonl\"" ;;
    rel) cmd="cd $p && cat projects/p/a.jsonl" ;;
  esac
  launch "grid-$1-$2" "$h" "$cmd"
  judge_eq "claude-real-grid-$1-$2" "$(verdict "grid-$1-$2")" "$3" "${cmd//"$T"/<T>}"
}
HIT="15|금지 산출물 참조|True|없음" MISS="0|-|True|있음"
#    꼴     대상  기대
grid cat    out  "$HIT"
grid cat    sib  "$MISS"
grid cat    in   "$HIT"
grid cat    repo "$HIT"
grid rec    out  "$HIT"
grid rec    sib  "$MISS"
grid rec    in   "$HIT"
grid rec    repo "$HIT"
grid quoted out  "$HIT"
grid quoted sib  "$MISS"
grid quoted in   "$HIT"
grid quoted repo "$HIT"
grid rel    out  "$HIT"
grid rel    sib  "$MISS"
grid rel    in   "$HIT"
grid rel    repo "$HIT"
launch envpass-link "$HO" "cat $T/claude-out/projects/p/a.jsonl"
launch envpass-plain "$HP" "cat $T/claude-out/projects/p/a.jsonl"
judge_eq claude-real-env-pass "$(verdict envpass-link) / $(verdict envpass-plain)" "$HIT / $MISS" \
  "같은 기록(홈 밖 대상 cat)이 ~/.claude 가 그 대상을 가리키는 홈에서만 적중한다 — 런처가 실경로를 감사까지 넘긴다"

want=$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u); got=$(printf '%s\n' $RAN | LC_ALL=C sort -u)
if [ "$want" = "$got" ]; then echo "PASS  셀 집합: 판정한 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "FAIL  셀 집합  — 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; fail=$((fail + 1)); fi
echo
echo "$fail 건 실패"
DONE=1
[ "$fail" -eq 0 ] || exit 1
echo "HOME_REF_OK ran=$(printf '%s\n' $RAN | grep -c .)"
