#!/bin/bash
# GPT 독립 첫 패스 런처 계약 러너 (S13) — 가짜 CLI(../_shim/codex)로 scripts/gpt_independent.sh 의 격리 · 감사 · 종료 계약을 본다.
#
# ⛔ 실제 GPT CLI · 사용자 홈을 건드리지 않는다 — PATH 앞에 shim, HOME 은 셀마다 임시 "실제 홈"(그 아래 인증 파일 · config).
#    rollout 은 shim 이 FZ_SHIM_ROLLOUT 으로 격리 홈에 넣는다 — deny 경로는 그 임시 홈의 realpath 로 만든다.
# ⛔ 실제 샌드박스 강제는 여기서 보지 않는다(가짜 CLI 라 강제가 없다) — probe/p2-agent-roles.md ⑦ · ⑩ 실측이 그 근거다.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L="${FZ_GPT_INDEPENDENT_UNDER_TEST:-$R/scripts/gpt_independent.sh}"
export PATH="$R/tests/fixtures/gpt/_shim:$PATH"
T="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 — 기대 '$3' · 실제 '$2'"; fi; }

# 임시 "실제 홈" — 인증 파일 · MCP 비밀이 든 config(격리 config 로 새면 안 된다)
H="$T/realhome"; mkdir -p "$H/.codex" "$H/.claude/projects/p" "$H/dev"
echo '{"fake":"auth"}' > "$H/.codex/auth.json"
printf 'model = "m-test"\n\n[mcp_servers.x]\nenv = { TOKEN = "SECRET-TOKEN-XYZ" }\n' > "$H/.codex/config.toml"
echo "claude log" > "$H/.claude/projects/p/notes.md"
IN="$T/in"; mkdir -p "$IN/snap-ok" "$IN/snap-bad1" "$IN/snap-bad2" "$IN/base/src" "$IN/head/src"
printf '# 요구\n주문 취소 시 알림을 끊는다 REQ-MARK-7\n' > "$IN/requirement.md"
cp "$IN/requirement.md" "$IN/code-context.md"; cp "$IN/requirement.md" "$IN/plan-v2.md"
echo x > "$IN/snap-ok/consumer.ts"; echo '{}' > "$IN/snap-bad1/workflow-result.json"; echo x > "$IN/snap-bad2/review-report.md"
printf 'diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-a\n+b\n' > "$IN/diff.patch"
echo a > "$IN/base/src/a.ts"; echo b > "$IN/head/src/a.ts"
HREAL="$(cd "$H" && pwd -P)"

roll() {   # $1=파일 · $2=deny 여부(1/0) · 나머지=도구 호출 명령들 → rollout jsonl
  local f="$1" deny="$2"; shift 2
  python3 - "$f" "$HREAL" "$deny" "$@" <<'PY'
import json, sys
f, home, deny, cmds = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4:]
ents = ([{"path": {"type": "path", "path": home}, "access": "deny"}] if deny else []) + [{"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": ents}}}}]
for c in cmds:
    if c == "SPAWN":
        rows.append({"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "arguments": "{}"}})
    else:
        rows.append({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": f"tools.exec_command({{cmd:{json.dumps(c)}}})"}})
open(f, "w", encoding="utf-8").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
PY
}
roll "$T/r-ok.jsonl" 1 "cat requirement.md"
roll "$T/r-sub.jsonl" 1 "cat head/src/a.ts"
roll "$T/r-parent.jsonl" 1 "SPAWN" "cat diff.patch"
roll "$T/r-claude.jsonl" 1 "cat /x/.claude/projects/p/a.jsonl"
roll "$T/r-find.jsonl" 1 "find ~ -name '*.md'"
roll "$T/r-home.jsonl" 1 "head -1 $HREAL/dev/notes.md"
roll "$T/r-nodeny.jsonl" 0 "cat requirement.md"

run() {    # $1=셀 · $2=shim 출력 파일(없으면 빈 값) · $3=rollout 목록(쉼표) · 나머지=런처 인자
  local name="$1" outf="$2" rolls="$3"; shift 3
  local d="$T/c-$name"; mkdir -p "$d/out"
  local body="ok"; [ -n "$outf" ] && body="$(cat "$outf")"
  local start; start=$(date +%s)
  env -u CODEX_HOME HOME="$H" FZ_TELEMETRY_DIR="$d/tel" FZ_SHIM_CAPTURE="$d/argv.json" FZ_SHIM_ENV_CAPTURE="$d/env.txt" \
    FZ_SHIM_OUTPUT="$body" FZ_SHIM_ROLLOUT="$rolls" ${SLEEP:+FZ_SHIM_SLEEP="$SLEEP"} \
    bash "$L" "$@" --arm A --run-id "$name" --out-dir "$d/out" > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"; echo $(( $(date +%s) - start )) > "$d/secs"
}
rc() { cat "$T/c-$1/rc" 2>/dev/null || echo "?"; }
called() { [ -s "$T/c-$1/argv.json" ] && echo 1 || echo 0; }
count() { [ -s "$T/c-$1/argv.json" ] || { echo 0; return; }
  python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1], encoding="utf-8"))).count(sys.argv[2]))' "$T/c-$1/argv.json" "$2"; }
audit() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$T/c-$1/out/A-$1.audit.json" "$2" 2>/dev/null || echo "-"; }

# ① plan 정상 — 역할 본문 1회 · 격리 환경 · sandbox_mode 없음 · 산출 넷 · 잠금 · 격리 폴더 정리
run plan "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --snapshot "$IN/snap-ok" --keep-iso
check "plan: exit 0" "$(rc plan)" 0
check "plan: fz-planner 본문 1회" "$(count plan '# fz-planner — Independent Plan Generation Skill')" 1
check "plan: 주입 마커가 격리 사본 폴더를 가리킨다" "$(count plan '[fz-gpt-skill-injected] fz-planner (/')" 1
check "plan: 요구 원문이 과제에 있다" "$(count plan 'REQ-MARK-7')" 1
check "plan: sandbox_mode 안 넘김(--config-permissions)" "$(count plan 'sandbox_mode')" 0
ISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-plan/env.txt")"
[ -n "$ISO" ] && [ "$(sed -n 's/^HOME=//p' "$T/c-plan/env.txt")" = "$ISO/home" ] && ok "plan: CLI 는 격리 HOME · 격리 CODEX_HOME 으로 돈다" || no "plan: 격리 환경이 아니다 — $(tr '\n' ' ' < "$T/c-plan/env.txt")"
CFG="$ISO/gpt-home/config.toml"
[ "$(head -1 "$CFG" 2>/dev/null)" = 'default_permissions = "fz-iso"' ] && ok "plan: config 첫 줄 = default_permissions" || no "plan: config 첫 줄이 default_permissions 가 아니다"
grep -q "^\"$HREAL\" = \"deny\"$" "$CFG" 2>/dev/null && grep -q "^\"$ISO\" = \"read\"$" "$CFG" && ok "plan: 실제 홈 deny · 격리 폴더 read" || no "plan: 권한 프로필에 홈 deny · 격리 read 가 없다"
grep -q '^memories = false$' "$CFG" 2>/dev/null && grep -q '^model = "m-test"$' "$CFG" && ok "plan: memories 끔 · model 한 줄만 옮김" || no "plan: memories · model 줄"
grep -q 'SECRET-TOKEN-XYZ' "$CFG" 2>/dev/null && no "plan: 실제 config 의 비밀 줄이 격리 config 로 샜다" || ok "plan: 실제 config 의 다른 줄은 옮기지 않는다"
[ -L "$ISO/gpt-home/auth.json" ] && [ ! -L "$ISO/gpt-home/skills/fz-planner" ] && [ -f "$ISO/gpt-home/skills/fz-planner/SKILL.md" ] \
  && ok "plan: 인증은 링크 · 스킬은 사본" || no "plan: 인증 링크 · 스킬 사본"
[ -f "$ISO/input/snapshot/snap-ok/consumer.ts" ] && ok "plan: 스냅샷을 격리 입력으로 복사" || no "plan: 스냅샷 복사 없음"
for s in json md audit.json; do [ -s "$T/c-plan/out/A-plan.$s" ] && ok "plan: 산출 .$s" || no "plan: 산출 .$s 없음"; done
check "plan: rollout 사본 1" "$(ls "$T/c-plan/out/A-plan.rollouts" 2>/dev/null | wc -l | tr -d ' ')" 1
check "plan: 감사 격리 적용" "$(audit plan isolationApplied)" True
check "plan: 감사 적중 0" "$(audit plan hits)" "[]"
[ ! -e "$T/c-plan/out/A-plan.json.lock" ] && ok "plan: 잠금 해제" || no "plan: 잠금이 남았다"
rm -rf "$ISO"

# ② review 정상 — fz-reviewer 본문 1회 · base · head 복사 · 격리 폴더는 기본으로 지운다
run review "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --base "$IN/base" --head "$IN/head"
check "review: exit 0" "$(rc review)" 0
check "review: fz-reviewer 본문 1회" "$(count review '# fz-reviewer — Code Review Skill')" 1
RISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-review/env.txt")"
[ -n "$RISO" ] && [ ! -e "$RISO" ] && ok "review: 격리 폴더를 지웠다(--keep-iso 없음)" || no "review: 격리 폴더가 남았다: $RISO"

# ③ 금지 입력 → exit 15 · CLI 미호출
run bad1 "" "" plan --requirement "$IN/code-context.md"
run bad2 "" "" plan --requirement "$IN/plan-v2.md"
run bad3 "" "" plan --requirement "$IN/requirement.md" --snapshot "$IN/snap-bad1"
run bad4 "" "" review --diff "$IN/diff.patch" --snapshot "$IN/snap-bad2"
run bad5 "" "" plan --requirement "$H/.claude/projects/p/notes.md"
for c in bad1 bad2 bad3 bad4 bad5; do
  check "금지 입력($c): exit 15" "$(rc $c)" 15
  check "금지 입력($c): CLI 미호출" "$(called $c)" 0
done

# ④ rollout 감사 → exit 15 + 오염 표시
run aud1 "$HERE/sample-plan-ok.json" "$T/r-claude.jsonl" plan --requirement "$IN/requirement.md"
run aud2 "$HERE/sample-plan-ok.json" "$T/r-find.jsonl" plan --requirement "$IN/requirement.md"
run aud3 "$HERE/sample-plan-ok.json" "$T/r-home.jsonl" plan --requirement "$IN/requirement.md"
run aud4 "$HERE/sample-plan-ok.json" "$T/r-nodeny.jsonl" plan --requirement "$IN/requirement.md"
for c in aud1 aud2 aud3 aud4; do
  check "감사($c): exit 15" "$(rc $c)" 15
  [ -s "$T/c-$c/out/A-$c.contaminated" ] && ok "감사($c): 오염 표시 파일" || no "감사($c): 오염 표시가 없다"
done
check "감사(aud4): 격리 미적용으로 판정" "$(audit aud4 isolationApplied)" False

# ⑤ 하위 에이전트 — rollout 둘 다 감사 · spawn 수를 적는다(끌 수 없다 — S11 ⑤)
run sub "$HERE/sample-review-ok.json" "$T/r-parent.jsonl,$T/r-sub.jsonl" review --diff "$IN/diff.patch"
check "하위 에이전트: exit 0" "$(rc sub)" 0
check "하위 에이전트: rollout 2 감사" "$(audit sub rollouts)" 2
check "하위 에이전트: spawn 1" "$(audit sub spawnAgent)" 1

# ⑥ 같은 --out 동시 실행 → exit 10 · CLI 미호출
mkdir -p "$T/c-lock/out/A-lock.json.lock"
run lock "" "" plan --requirement "$IN/requirement.md"
check "잠금: exit 10" "$(rc lock)" 10
check "잠금: CLI 미호출" "$(called lock)" 0

# ⑦ 멈춘 CLI → 시간 초과 exit 16 · 프로세스 그룹째 종료(CLI 의 자식 sleep 도 죽는다)
SLEEP=29.7 run hang "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --timeout 2
check "시간 초과: exit 16" "$(rc hang)" 16
[ "$(cat "$T/c-hang/secs")" -lt 15 ] && ok "시간 초과: 타이머 뒤 곧 끝난다($(cat "$T/c-hang/secs")s)" || no "시간 초과: $(cat "$T/c-hang/secs")s 걸렸다"
sleep 1; pgrep -f 'sleep 29.7' >/dev/null && no "시간 초과: CLI 의 자식이 고아로 남았다" || ok "시간 초과: CLI 의 자식까지 종료"

# ⑧ planner 거부 → exit 17
printf '%s' '{"status":"rejected","reason":"claude_plan_detected","approach":"-","affectedFiles":{"new":0,"modified":0},"steps":[],"riskMatrix":[],"stressTest":[],"implicationRegister":[],"divergencePoints":[],"projectRules":{"axes":{"architecturePattern":null,"uiStack":null,"dependencyDirection":null,"naming":null,"placement":null,"conventions":null},"rules":[],"conflicts":[],"gaps":[]}}' > "$T/rejected.json"
run rej "$T/rejected.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
check "planner 거부: exit 17" "$(rc rej)" 17

# ⑨ 6축 중복(스키마는 행 수만 본다) → 후검사 exit 14
python3 - "$HERE/sample-review-ok.json" "$T/dup.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); d["axis_coverage"][1]["axis"] = d["axis_coverage"][0]["axis"]
json.dump(d, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False)
PY
run dup "$T/dup.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch"
check "6축 중복: exit 14" "$(rc dup)" 14

# ⑩ 스키마 위반(axis_coverage 누락) → 래퍼 exit 14 그대로
run nocov "$HERE/sample-review-no-coverage.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch"
check "스키마 위반: exit 14" "$(rc nocov)" 14

# ⑪ 사용법 → exit 10
run u1 "" "" plan
run u2 "" "" review --diff "$IN/diff.patch" --sprint-contract "$IN/requirement.md"
run u3 "" "" plan --requirement "$IN/requirement.md" --deny "$IN"
for c in u1 u2 u3; do check "사용법($c): exit 10" "$(rc $c)" 10; done

echo
[ "$fail" -eq 0 ] && echo "independent-arm: 전건 통과" || echo "independent-arm: 실패 있음"
exit "$fail"
