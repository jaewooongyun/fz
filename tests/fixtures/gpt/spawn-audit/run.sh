#!/bin/bash
# spawn 감사 러너 — 래퍼 scripts/gpt-exec.sh 가 호출마다 gpt-calls.tsv 에 남기는 행(관측 전용)을 가짜 CLI(../_shim/codex)로 본다.
# rollout 은 CLI 0.159.2 형식으로 만든다(R-G1 S1 실측): spawn = function_call spawn_agent · 자식 결과 = 수신자 /root 의 agent_message ·
# 토큰 = token_count 누적값 · 자식 rollout = session_meta.parent_thread_id 가 부모 세션인 별도 파일 · resume 은 부모 파일에 이어 쓴다.
#
# ⛔ 실제 GPT CLI · 네트워크 · 사용자 홈을 쓰지 않는다 — PATH 앞에 shim, HOME · CODEX_HOME · 텔레메트리 폴더는 임시 폴더.
# ⛔ '?' 는 측정 불가다 — rollout 이 없거나 모양을 모르는 호출을 0 으로 쓰면 '하위 에이전트 없음' 으로 읽힌다(AC-4 · XE-20).
#
# 셀 — 줄 형식 `PASS|FAIL  [<id>] <설명>` (게이트가 id 마다 PASS 정확히 1줄을 센다)
#   spawn-2             exec · spawn 2 · 자식 결과 2 · 자식 rollout 2 → spawn=2 · child_results=2 · tokens = 부모 + 자식 합
#   spawn-0             exec · turn_context 만 · spawn 없음 → spawn=0 · child_results=0 · tokens = 부모
#   no-rollout          exec 성공 · rollout 없음 → '?' 셋
#   corrupt-rollout     exec 성공 · rollout 이 JSON 이 아니다 → '?' 셋
#   exit-10             사용법 거부(exec 에 --prompt-file 없음) → 행 있음 · exit 10 · '?' 셋
#   exit-12             CLI 실패 → 행 있음 · exit 12 · '?' 셋
#   ephemeral           --ephemeral → rollout 이 있어도 '?' 셋
#   resume-incremental  부모 exec(spawn 2 · 토큰 1000) → resume 이 같은 파일에 spawn 0 · 누적 1600 을 이어 씀 → resume 행 spawn=0 · tokens=600
#   gate-attempt-row    정문이 정책 플래그로 거부(10) → origin=gate 행 · label = kind · exit 10
#   call-id-unique      모든 행에 call_id 가 있고 서로 다르다
#   label-from-gate     정문 경유 verify → 래퍼 행 label=verify · origin=wrapper · 정문 행 없음
#   idle-source         FZ_GPT_IDLE_SEC=7 → 7 · env / 미설정 → 900 · default
#   tsv9-unchanged      gpt-skill-usage.tsv 행은 9열 그대로(새 행은 별도 파일)
#   exit-unchanged      셀들의 래퍼 exit 이 계약 그대로(0 · 10 · 12)
# exit: 0 전건 통과 · 1 셀 FAIL · 3 준비 실패
# usage: run.sh [--tree <플러그인 루트>]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || { echo "SETUP 러너 위치를 풀지 못했다"; exit 3; }
R="$(cd "$HERE/../../../.." && pwd)" || { echo "SETUP 트리 루트를 풀지 못했다"; exit 3; }
SHIM_DIR="$(cd "$HERE/../_shim" && pwd)" || { echo "SETUP shim 폴더 없음"; exit 3; }
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
WRAP="$R/scripts/gpt-exec.sh" GATE="$R/scripts/gpt-call.sh"
[ -f "$WRAP" ] && [ -f "$GATE" ] || { echo "SETUP 래퍼 · 정문 없음: $R"; exit 3; }
T="$(mktemp -d "${TMPDIR:-/tmp}/fz-spawn-audit.XXXXXX")" || { echo "SETUP 임시 폴더"; exit 3; }
[ -d "$T" ] || { echo "SETUP 임시 폴더"; exit 3; }
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/repo" "$T/home" "$T/rolls" && git -C "$T/repo" init -q && echo "task" > "$T/p.txt" || { echo "SETUP 작업 폴더"; exit 3; }
fail=0
ok() { echo "PASS  [$1] $2"; }
no() { echo "FAIL  [$1] $2"; fail=1; }

# rollout 조각 — 줄 단위 jsonl
python3 - "$T/rolls" <<'PY' || { echo "SETUP rollout 조각"; exit 3; }
import json, os, sys
d = sys.argv[1]
J = lambda rows: "".join(json.dumps(r) + "\n" for r in rows)
meta = lambda sid, **kw: {"type": "session_meta", "payload": dict({"id": sid}, **kw)}
tc = {"type": "turn_context", "payload": {"multi_agent_version": "v2"}}
spawn = {"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "arguments": "{}"}}
kid_msg = {"type": "response_item", "payload": {"type": "agent_message", "recipient": "/root", "author": "/root/agent-1"}}
tok = lambda n: {"type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"total_tokens": n}}}}
S2, S0, SR, SE = ("aaaaaaaa-0000-0000-0000-00000000000%d" % i for i in (2, 3, 4, 5))
files = {
    "spawn2.jsonl": [meta(S2), tc, spawn, spawn, kid_msg, kid_msg, tok(1000)],
    "spawn2-kid1.jsonl": [meta("bbbbbbbb-0000-0000-0000-000000000001", parent_thread_id=S2, source={"subagent": {"thread_spawn": {}}}), tok(300)],
    "spawn2-kid2.jsonl": [meta("bbbbbbbb-0000-0000-0000-000000000002", parent_thread_id=S2, source={"subagent": {"thread_spawn": {}}}), tok(200)],
    "spawn0.jsonl": [meta(S0), tc, tok(500)],
    "parent.jsonl": [meta(SR), tc, spawn, spawn, kid_msg, kid_msg, tok(1000)],
    "resume-part.jsonl": [tc, tok(1600)],
    "eph.jsonl": [meta(SE), tc, spawn, tok(10)],
}
SK, KK = "aaaaaaaa-0000-0000-0000-000000000006", "bbbbbbbb-0000-0000-0000-000000000006"
kmeta = meta(KK, parent_thread_id=SK, source={"subagent": {"thread_spawn": {}}})
at = lambda r, ts: dict(r, timestamp=ts)
files.update({
    "pk-parent.jsonl": [meta(SK), tc, spawn, kid_msg, tok(1000)],
    "pk-kid-v1.jsonl": [kmeta, tok(300)],
    "pk-kid-v2.jsonl": [at(kmeta, "2000-01-01T00:00:00.000Z"), at(tok(300), "2000-01-01T00:00:01.000Z"), at(tok(450), "2099-01-01T00:00:00.000Z")],
    "pk-resume.jsonl": [tc, tok(1600)],
})
for n, rows in files.items():
    open(os.path.join(d, n), "w").write(J(rows))
open(os.path.join(d, "corrupt.jsonl"), "w").write("not json\n{\"type\": \n")
PY

ENVB=(env -u CODEX_HOME -u FZ_GPT_IDLE_SEC -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL "PATH=$SHIM_DIR:$PATH" "HOME=$T/home" "FZ_GPT_CHOICE_DIR=$T/no-choice")
run() {   # $1 = cell dir name, rest = env assignments then -- then wrapper args → prints exit
  local c="$1"; shift; local envs=()
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done; shift
  mkdir -p "$T/c/$c/tel" "$T/c/$c/ch"
  "${ENVB[@]}" "CODEX_HOME=$T/c/$c/ch" "FZ_TELEMETRY_DIR=$T/c/$c/tel" ${envs[@]+"${envs[@]}"} bash "$@" > "$T/c/$c/out" 2> "$T/c/$c/err"
  echo $?
}
row() {   # $1 = cell → the gpt-calls.tsv rows (13 columns)
  cat "$T/c/$1/tel/gpt-calls.tsv" 2>/dev/null
}
col() { printf '%s\n' "$1" | awk -F'\t' -v n="$2" '{print $n}'; }   # $1 = one row · $2 = column number
spec() {   # $1 = id · $2 = row · $3 = want "spawn kids tokens" · $4 = want exit
  local s; s="$(col "$2" 7) $(col "$2" 8) $(col "$2" 9)"
  if [ "$(printf '%s\n' "$2" | grep -c .)" = "1" ] && [ "$(printf '%s' "$2" | awk -F'\t' '{print NF}')" = "13" ] && [ "$s" = "$3" ] && [ "$(col "$2" 12)" = "$4" ]; then
    ok "$1" "spawn · child_results · tokens = $s · exit $4"
  else
    no "$1" "기대 '$3' exit $4 — 행: $(printf '%s' "$2" | tr '\t' '|')"
  fi
}
EX=()   # exit 기록 — exit-unchanged

rc=$(run s2 "FZ_SHIM_SESSION_ID=aaaaaaaa-0000-0000-0000-000000000002" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/spawn2.jsonl" \
       "FZ_SHIM_CHILD_ROLLOUTS=$T/rolls/spawn2-kid1.jsonl,$T/rolls/spawn2-kid2.jsonl" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/s2/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:0")
spec spawn-2 "$(row s2)" "2 2 1500" 0
rc=$(run s0 "FZ_SHIM_SESSION_ID=aaaaaaaa-0000-0000-0000-000000000003" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/spawn0.jsonl" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/s0/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:0")
spec spawn-0 "$(row s0)" "0 0 500" 0
rc=$(run nr -- "$WRAP" exec --cd "$T/repo" --out "$T/c/nr/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:0")
spec no-rollout "$(row nr)" "? ? ?" 0
rc=$(run cr "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/corrupt.jsonl" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/cr/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:0")
spec corrupt-rollout "$(row cr)" "? ? ?" 0
rc=$(run e10 -- "$WRAP" exec --cd "$T/repo" --out "$T/c/e10/o.txt"); EX+=("$rc:10")
spec exit-10 "$(row e10)" "? ? ?" 10
rc=$(run e12 "FZ_SHIM_EXIT=1" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/e12/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:12")
spec exit-12 "$(row e12)" "? ? ?" 12
rc=$(run eph "FZ_SHIM_SESSION_ID=aaaaaaaa-0000-0000-0000-000000000005" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/eph.jsonl" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/eph/o.txt" --prompt-file "$T/p.txt" --ephemeral); EX+=("$rc:0")
spec ephemeral "$(row eph)" "? ? ?" 0

# resume — 같은 CODEX_HOME · 같은 텔레메트리 폴더에서 부모 exec 뒤 resume
SR=aaaaaaaa-0000-0000-0000-000000000004
rc=$(run rs "FZ_SHIM_SESSION_ID=$SR" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/parent.jsonl" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/rs/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:0")
rc=$(run rs "FZ_SHIM_SESSION_ID=$SR" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/resume-part.jsonl" -- "$WRAP" resume --cd "$T/repo" --out "$T/c/rs/o2.txt" --prompt-file "$T/p.txt" --session-file "$T/c/rs/o.txt.session"); EX+=("$rc:0")
r_rows="$(row rs)"
spec resume-incremental "$(printf '%s\n' "$r_rows" | awk -F'\t' '$5=="resume"')" "0 0 600" 0
# 부모 exec 는 spawn 2 인데 자식 rollout 이 없다 — 토큰은 '?' 다(부모만 적으면 합을 과소 집계한다)
[ "$(printf '%s\n' "$r_rows" | awk -F'\t' '$5=="exec"{print $7" "$9}')" = "2 ?" ] || no resume-incremental "부모 행이 spawn 2 · tokens ? 가 아니다"
# 앞 exec 가 만든 자식이 resume 중에 300 → 450 — 자식은 증분 150 만 (누적 450 이 아니다) · 부모 증분 600 과 합쳐 750
SK=aaaaaaaa-0000-0000-0000-000000000006
rc=$(run pk "FZ_SHIM_SESSION_ID=$SK" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/pk-parent.jsonl" "FZ_SHIM_CHILD_ROLLOUTS=$T/rolls/pk-kid-v1.jsonl" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/pk/o.txt" --prompt-file "$T/p.txt"); EX+=("$rc:0")
rc=$(run pk "FZ_SHIM_SESSION_ID=$SK" "FZ_SHIM_SESSION_ROLLOUT=$T/rolls/pk-resume.jsonl" "FZ_SHIM_CHILD_ROLLOUTS=$T/rolls/pk-kid-v2.jsonl" -- "$WRAP" resume --cd "$T/repo" --out "$T/c/pk/o2.txt" --prompt-file "$T/p.txt" --session-file "$T/c/pk/o.txt.session"); EX+=("$rc:0")
spec resume-child-increment "$(row pk | awk -F'\t' '$5=="resume"')" "0 0 750" 0

# 정문 — 거부(정책 플래그)와 정상 경유
rc=$(run ga -- "$GATE" verify --cd "$T/repo" --out "$T/c/ga/o.json" --prompt-file "$T/p.txt" --schema x.json)
g="$(row ga)"
if [ "$rc" = "10" ] && [ "$(printf '%s\n' "$g" | grep -c .)" = "1" ] && [ "$(col "$g" 13)" = "gate" ] && [ "$(col "$g" 4)" = "verify" ] && [ "$(col "$g" 12)" = "10" ]; then
  ok gate-attempt-row "정문 거부 → origin=gate · label=verify · exit 10"
else no gate-attempt-row "rc=$rc 행: $(printf '%s' "$g" | tr '\t' '|')"; fi
rc=$(run gl "FZ_SHIM_OUTPUT={\"schemaVersion\":\"1.1\",\"verdict\":\"approved\",\"issues\":[]}" -- "$GATE" verify --cd "$T/repo" --out "$T/c/gl/o.json" --prompt-file "$T/p.txt")
g="$(row gl)"
if [ "$(printf '%s\n' "$g" | grep -c .)" = "1" ] && [ "$(col "$g" 4)" = "verify" ] && [ "$(col "$g" 13)" = "wrapper" ]; then
  ok label-from-gate "정문 경유 → 래퍼 행 하나 · label=verify (exit $rc)"
else no label-from-gate "rc=$rc 행: $(printf '%s' "$g" | tr '\t' '|')"; fi
# 정문을 지난 독립 kind 를 런처가 래퍼 전에 거부(규칙 레코드를 원문 색인 자리에) — 래퍼 행이 없으니 정문이 행을 남긴다
printf 'diff --git a/x b/x\n' > "$T/d.patch"; printf '{"rules": [], "axes": {}}\n' > "$T/rules.json"
rc=$(run lr -- "$GATE" independent-review --diff "$T/d.patch" --arm gpt --run-id r1 --out-dir "$T/c/lr/od" --rules-index "$T/rules.json")
g="$(row lr)"
if [ "$rc" = "11" ] && [ "$(printf '%s\n' "$g" | grep -c .)" = "1" ] && [ "$(col "$g" 13)" = "gate" ] && [ "$(col "$g" 4)" = "independent-review" ] && [ "$(col "$g" 12)" = "11" ]; then
  ok launcher-refusal-row "런처 거부(래퍼 전) → 정문 행 하나 · label=independent-review · exit 11"
else no launcher-refusal-row "rc=$rc 행: $(printf '%s' "$g" | tr '\t' '|') · err: $(tail -c 200 "$T/c/lr/err")"; fi

# idle 출처
run ie "FZ_GPT_IDLE_SEC=7" -- "$WRAP" exec --cd "$T/repo" --out "$T/c/ie/o.txt" --prompt-file "$T/p.txt" > /dev/null
run idf -- "$WRAP" exec --cd "$T/repo" --out "$T/c/idf/o.txt" --prompt-file "$T/p.txt" > /dev/null
a="$(row ie)"; b="$(row idf)"
if [ "$(col "$a" 10) $(col "$a" 11)" = "7 env" ] && [ "$(col "$b" 10) $(col "$b" 11)" = "900 default" ]; then ok idle-source "env 7 · default 900"
else no idle-source "env='$(col "$a" 10) $(col "$a" 11)' default='$(col "$b" 10) $(col "$b" 11)'"; fi

# 9열 텔레메트리 — 역할 라벨이 있는 호출만 쓴다
run t9 -- "$WRAP" exec --cd "$T/repo" --out "$T/c/t9/o.txt" --prompt-file "$T/p.txt" --gpt-skill reviewer > /dev/null
n9="$(awk -F'\t' '{print NF}' "$T/c/t9/tel/gpt-skill-usage.tsv" 2>/dev/null | sort -u | tr '\n' ' ')"
if [ "$n9" = "9 " ] && [ "$(grep -c . "$T/c/t9/tel/gpt-skill-usage.tsv")" = "1" ] && [ "$(row t9 | grep -c .)" = "1" ]; then ok tsv9-unchanged "gpt-skill-usage.tsv 9열 1행 · 새 행은 gpt-calls.tsv"
else no tsv9-unchanged "열 수='$n9'"; fi

# call_id — 모든 셀의 행
ids="$(cat "$T"/c/*/tel/gpt-calls.tsv | awk -F'\t' '{print $3}')"
if [ -n "$ids" ] && ! printf '%s\n' "$ids" | grep -qx '' && [ "$(printf '%s\n' "$ids" | sort | uniq -d | grep -c .)" = "0" ]; then
  ok call-id-unique "$(printf '%s\n' "$ids" | grep -c .) 행 · 중복 0"
else no call-id-unique "빈 값 또는 중복"; fi

bad=""; for e in "${EX[@]}"; do [ "${e%%:*}" = "${e##*:}" ] || bad="$bad $e"; done
[ -z "$bad" ] && ok exit-unchanged "래퍼 exit ${#EX[@]}건 계약 그대로" || no exit-unchanged "실제:기대 =$bad"

[ "$fail" = 0 ] && { echo "spawn-audit: 전건 통과"; exit 0; }
echo "spawn-audit: FAIL"; exit 1
