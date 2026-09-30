#!/bin/bash
# 실패 주입 — GPT 호출 경로의 실패가 "완료" 로 보고되지 않는다.
#   --scope wrapper (S24a · 기본): 래퍼(gpt-exec.sh)에 CLI 비정상 종료 · 빈 출력 · 스키마 위반을 주입한다.
#     판정: 래퍼 exit 가 12 / 13 / 14 이고, 성공 표시(GATE-PASS)를 내지 않으며, stderr 에 GATE-FAIL 이 있다.
#   --scope launcher (S24b): 독립 첫 패스 런처(gpt_independent.sh)를 실제로 실패시키고 그 산출을 소비자에 넣는다 —
#     review 는 review_merge.py(시간 초과 · 오염 · 격리 미적용 · stale), plan 은 plan_divergence.py(planner 거부 · 시간 초과 · 금지 입력).
#     판정: 런처 exit 가 기대값이고 성공 줄(INDEPENDENT OK)이 없으며, 소비자가 거부(1) 또는 입력 불가(2)로 끝나고 산출 파일을 쓰지 않는다.
# 대조: 주입 없는 호출은 성공해야 한다 — 그래야 실패가 주입 때문임을 안다.
# ⛔ 실제 GPT CLI 를 부르지 않는다 — PATH 앞에 가짜 CLI(../_shim/codex) · HOME 은 임시 "실제 홈".
# ⛔ Lead 세션의 GPT 모델·effort 선택이 argv 로 새지 않게 선택 폴더를 격리한다(판정은 그대로) — wrapper 는 임시 FZ_GPT_CHOICE_DIR,
#    launcher 는 env -u FZ_GPT_CHOICE_DIR · 고정 세션 id(선택 폴더가 임시 홈 아래로 정해지고 그 id 의 선택 파일은 없다).
set -u
SCOPE="wrapper"
[ "${1:-}" = "--scope" ] && SCOPE="${2:-}"
case "$SCOPE" in
  wrapper|launcher) ;;
  *) echo "UNRUN  scope '$SCOPE' 의 셀은 없다 — wrapper · launcher 만 구현한다"; exit 2 ;;
esac

R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
WRAP="${FZ_GPT_EXEC_UNDER_TEST:-$R/scripts/gpt-exec.sh}"
export PATH="$R/tests/fixtures/gpt/_shim:$PATH"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
fail=0

if [ "$SCOPE" = "launcher" ]; then
  L="${FZ_GPT_INDEPENDENT_UNDER_TEST:-$R/scripts/gpt_independent.sh}"
  S="$R/tests/fixtures/gpt/independent-arm"   # 정상 표본(review · plan)
  H="$T/realhome"; mkdir -p "$H/.codex" "$H/.claude/projects/p"
  echo '{"fake":"auth"}' > "$H/.codex/auth.json"; printf 'model = "m-test"\n' > "$H/.codex/config.toml"
  HREAL="$(cd "$H" && pwd -P)"
  IN="$T/in"; mkdir -p "$IN/base/src" "$IN/head/src"
  printf '# 요구\n주문 취소 시 알림을 끊는다 REQ-MARK-9\n' > "$IN/requirement.md"; cp "$IN/requirement.md" "$IN/plan-v2.md"
  printf 'diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-a\n+b\n' > "$IN/diff.patch"
  echo a > "$IN/base/src/a.ts"; echo b > "$IN/head/src/a.ts"
  roll() {   # $1=파일 · $2=홈 deny 여부(1/0) · $3=도구 호출 명령 → rollout jsonl
    python3 - "$1" "$HREAL" "$2" "$3" <<'PY'
import json, sys
f, home, deny, cmd = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4]
ents = ([{"path": {"type": "path", "path": home}, "access": "deny"}] if deny else []) + [{"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": ents}}}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": f"tools.exec_command({{cmd:{json.dumps(cmd)}}})"}}]
open(f, "w", encoding="utf-8").write("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
PY
  }
  roll "$T/r-ok.jsonl" 1 "cat requirement.md"
  roll "$T/r-claude.jsonl" 1 "cat /x/.claude/projects/p/a.jsonl"
  roll "$T/r-nodeny.jsonl" 0 "cat requirement.md"
  printf '%s' '{"status":"rejected","reason":"claude_plan_detected","approach":"-","affectedFiles":{"new":0,"modified":0},"steps":[],"riskMatrix":[],"stressTest":[],"implicationRegister":[],"divergencePoints":[],"projectRules":{"axes":{"architecturePattern":null,"uiStack":null,"dependencyDirection":null,"naming":null,"placement":null,"conventions":null},"rules":[],"conflicts":[],"gaps":[]}}' > "$T/rejected.json"
  printf '{"issues": []}\n' > "$T/claude.json"
  printf '{"plan": {"steps": [{"id": "S1", "title": "t", "files": ["src/orders/order_service.ts"]}], "rtm": [], "riskMatrix": []}}\n' > "$T/claude-plan.json"

  arm() {    # $1=셀 · $2=가짜 CLI 출력 파일(없으면 빈 값) · $3=rollout · 나머지=런처 인자
    local name="$1" outf="$2" rolls="$3"; shift 3
    local d="$T/l-$name"; mkdir -p "$d/out"
    local body="ok"; [ -n "$outf" ] && body="$(cat "$outf")"
    env -u CODEX_HOME -u FZ_GPT_CHOICE_DIR HOME="$H" CLAUDE_CODE_SESSION_ID=fi-launcher-no-choice FZ_TELEMETRY_DIR="$d/tel" \
      FZ_SHIM_OUTPUT="$body" FZ_SHIM_ROLLOUT="$rolls" ${SLEEP:+FZ_SHIM_SLEEP="$SLEEP"} \
      bash "$L" "$@" --arm A --run-id "$name" --out-dir "$d/out" > "$d/stdout" 2> "$d/stderr"
    echo $? > "$d/rc"
  }
  judge() {  # $1=셀 · $2=기대 런처 exit · $3=소비자(merge|diverge) · $4=소비자 기대 exit · [$5=병합 diff]
    local name="$1" want="$2" who="$3" cwant="$4" diff="${5:-$IN/diff.patch}" d="$T/l-$1"
    local rc; rc="$(cat "$d/rc")"
    local okline=0; grep -q "INDEPENDENT OK" "$d/stdout" && okline=1
    local out cr
    if [ "$who" = merge ]; then
      out="$d/merged-$(basename "$diff").json"
      python3 "$R/scripts/review_merge.py" --claude "$T/claude.json" --gpt "$d/out/A-$name.json" --diff "$diff" --out "$out" > /dev/null 2>&1; cr=$?
    else
      out="$d/divergence.md"
      python3 "$R/scripts/plan_divergence.py" --claude "$T/claude-plan.json" --gpt "$d/out/A-$name.json" --out "$out" > /dev/null 2>&1; cr=$?
    fi
    local made=없음; [ -e "$out" ] && made=있음
    if [ "$want" -eq 0 ] && [ "$cwant" -eq 0 ]; then
      [ "$rc" -eq 0 ] && [ "$okline" -eq 1 ] && [ "$cr" -eq 0 ] && [ "$made" = 있음 ] \
        && echo "PASS  $name(대조) → 런처 0 · 성공 줄 · $who 0 · 산출 있음" \
        || { echo "FAIL  $name(대조) — 런처 $rc · 성공 줄 $okline · $who $cr · 산출 $made"; fail=1; }
    else
      [ "$rc" -eq "$want" ] && { [ "$want" -eq 0 ] || [ "$okline" -eq 0 ]; } && [ "$cr" -eq "$cwant" ] && [ "$made" = 없음 ] \
        && echo "PASS  $name → 런처 exit $want · $who exit $cwant · 산출 없음(완료 보고 0)" \
        || { echo "FAIL  $name — 런처 $rc(기대 $want) · 성공 줄 $okline · $who $cr(기대 $cwant) · 산출 $made"; fail=1; }
    fi
  }

  arm rev-ok "$S/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --base "$IN/base" --head "$IN/head"
  judge rev-ok 0 merge 0
  SLEEP=29.7 arm rev-hang "$S/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --timeout 2
  judge rev-hang 16 merge 1
  arm rev-dirty "$S/sample-review-ok.json" "$T/r-claude.jsonl" review --diff "$IN/diff.patch"
  judge rev-dirty 15 merge 1
  arm rev-noiso "$S/sample-review-ok.json" "$T/r-nodeny.jsonl" review --diff "$IN/diff.patch"
  judge rev-noiso 15 merge 1
  cp "$IN/diff.patch" "$T/diff-changed.patch"; printf '+c\n' >> "$T/diff-changed.patch"
  judge rev-ok 0 merge 1 "$T/diff-changed.patch"   # stale — 성공한 산출도 GPT 가 본 diff 와 병합 diff 가 다르면 거부

  arm plan-ok "$S/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
  judge plan-ok 0 diverge 0
  arm plan-rej "$T/rejected.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
  judge plan-rej 17 diverge 1
  SLEEP=29.7 arm plan-hang "$S/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --timeout 2
  judge plan-hang 16 diverge 1
  arm plan-bad "" "" plan --requirement "$IN/plan-v2.md"
  judge plan-bad 15 diverge 2   # 금지 입력 — 런처가 CLI 전에 멈춰 산출이 없다(소비자는 입력 불가)

  echo
  [ "$fail" -eq 0 ] && echo "실패 주입 B(launcher) 전건 통과" || echo "실패 주입 B(launcher) 실패 있음"
  exit "$fail"
fi

mkdir -p "$T/repo"
echo "과제" > "$T/task.txt"
printf '{"type":"object","required":["verdict"],"properties":{"verdict":{"type":"string"}}}\n' > "$T/schema.json"

cell() {   # $1=이름 · $2=기대 exit · $3=FZ_SHIM_OUTPUT · $4=FZ_SHIM_EXIT · 나머지=추가 래퍼 인자
  local name="$1" want="$2" out="$3" ex="$4"; shift 4
  local d="$T/$name"; mkdir -p "$d"
  env FZ_SHIM_OUTPUT="$out" FZ_SHIM_EXIT="$ex" FZ_TELEMETRY_DIR="$d" FZ_GPT_CHOICE_DIR="$T/no-choice" \
    bash "$WRAP" exec --cd "$T/repo" --out "$d/out.txt" --prompt-file "$T/task.txt" "$@" > "$d/stdout" 2> "$d/stderr"
  local rc=$?
  local pass_shown=0 fail_shown=0
  grep -q "GATE-PASS" "$d/stdout" && pass_shown=1
  grep -q "GATE-FAIL" "$d/stderr" && fail_shown=1
  if [ "$want" -eq 0 ]; then
    [ "$rc" -eq 0 ] && [ "$pass_shown" -eq 1 ] && echo "PASS  $name → exit 0 + GATE-PASS" \
      || { echo "FAIL  $name — exit $rc · GATE-PASS $pass_shown"; fail=1; }
  else
    [ "$rc" -eq "$want" ] && [ "$pass_shown" -eq 0 ] && [ "$fail_shown" -eq 1 ] \
      && echo "PASS  $name → exit $want · GATE-PASS 없음 · GATE-FAIL 있음" \
      || { echo "FAIL  $name — exit $rc(기대 $want) · GATE-PASS $pass_shown · GATE-FAIL $fail_shown"; fail=1; }
  fi
}

cell "대조(주입 없음)"          0  "ok" 0
cell "CLI 비정상 종료(exit 1)"  12 "ok" 1
cell "빈 출력"                  13 ""   0
cell "스키마 위반"              14 "{}" 0 --schema "$T/schema.json"

echo
[ "$fail" -eq 0 ] && echo "실패 주입 A(wrapper) 전건 통과" || echo "실패 주입 A(wrapper) 실패 있음"
exit "$fail"
