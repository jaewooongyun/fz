#!/bin/bash
# GPT 독립 첫 패스 런처 계약 러너 (S13) — 가짜 CLI(../_shim/codex)로 scripts/gpt_independent.sh 의 격리 · 감사 · 종료 계약을 본다.
#
# ⛔ 실제 GPT CLI · 사용자 홈을 건드리지 않는다 — PATH 앞에 shim, HOME 은 셀마다 임시 "실제 홈"(그 아래 인증 파일 · config).
#    rollout 은 shim 이 FZ_SHIM_ROLLOUT 으로 격리 홈에 넣는다 — deny 경로는 그 임시 홈의 realpath 로 만든다.
# ⛔ 실제 샌드박스 강제는 여기서 보지 않는다(가짜 CLI 라 강제가 없다) — 실 GPT CLI 로 재는 것은 tests/fixtures/gpt/os-deny/external.sh(게이트 전용 · 모델 호출 없음)다.
# ⛔ Lead 세션의 GPT 모델·effort 선택이 argv 로 새지 않게 run() 은 env -u FZ_GPT_CHOICE_DIR · 고정 세션 id 로 돈다(CSID=… 로 셀마다 바꾼다) —
#    런처가 선택 폴더를 임시 "실제 홈" 아래(.fz/gpt-choice)로 정하고, 선택 파일은 ⑫ 선택 셀의 세션 id 에만 둔다.
# ⛔ FZ_GPT_INDEPENDENT_UNDER_TEST 로 기준 트리의 런처를 같은 러너로 돌린다 — 기준 런처(effort 기본값 · 선택 폴더 미전달 · effort 줄 미복사 ·
#    GPT-CHOICE 줄 미전달 · --model 미지원)에서 FAIL 이어야 하는 셀(판별력): ① 의 모델·effort 0 · GPT-CHOICE · 격리 config 두 줄 · model 계열 줄 수,
#    ② 의 모델·effort 0, ⑫ 의 sel argv · sel GPT-CHOICE · mdl 두 셀 · eff GPT-CHOICE · mbad · ebad 의 '거부한 쪽은 래퍼' · ebad exit.
#    기준 런처로도 통과하는 셀(판별 셀 아님): sel exit · eff 전달 · mbad exit · mbad · ebad 의 GPT-CHOICE 없음 — 기준도 --effort 를 넘기고, --model 을 모르면 스스로 exit 10 이다
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L="${FZ_GPT_INDEPENDENT_UNDER_TEST:-$R/scripts/gpt_independent.sh}"
export PATH="$R/tests/fixtures/gpt/_shim:$PATH"
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }; T="$(cd "$T0" && pwd -P)"; trap 'rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 — 기대 '$3' · 실제 '$2'"; fi; }
# 프로세스 조회 · 정리는 이 run 의 shim 태그로만 한다 — 전역 이름 검색(`sleep N`)은 동시에 도는 다른 run 의 프로세스를 보거나 죽인다(F-407)
RUNTAG="arm-$$-$RANDOM"
tagged_alive() { pgrep -f "fz-shim\[$1\]" >/dev/null; }
tagged_kill() { pkill ${2:+-$2} -f "fz-shim\[$1\]" 2>/dev/null; }
# 런처 감시자의 sleep 은 shim 이 아니라 태그가 없다 — PG=1 셀은 런처를 자기 프로세스 그룹에서 띄우고 그 그룹만 본다
pg_alive() { /bin/ps -axo pgid= | awk -v g="$1" '$1 == g { f = 1 } END { exit !f }'; }

# 임시 "실제 홈" — 인증 파일 · MCP 비밀이 든 config(격리 config 로 새면 안 된다) · 최상위 model · model_reasoning_effort(격리 config 로 옮긴다) · 표 안의 model 계열 줄(옮기지 않는다)
H="$T/realhome"; mkdir -p "$H/.codex" "$H/.claude/projects/p" "$H/dev"
echo '{"fake":"auth"}' > "$H/.codex/auth.json"
printf 'model = "m-test"\nmodel_reasoning_effort = "medium"\n\n[mcp_servers.x]\nenv = { TOKEN = "SECRET-TOKEN-XYZ" }\n\n[profiles.p]\nmodel = "m-table"\nmodel_reasoning_effort = "low"\n' > "$H/.codex/config.toml"
echo "claude log" > "$H/.claude/projects/p/notes.md"
IN="$T/in"; mkdir -p "$IN/snap-ok" "$IN/snap-bad1" "$IN/snap-bad2" "$IN/base/src" "$IN/head/src"
printf '# 요구\n주문 취소 시 알림을 끊는다 REQ-MARK-7\n' > "$IN/requirement.md"
cp "$IN/requirement.md" "$IN/code-context.md"; cp "$IN/requirement.md" "$IN/plan-v2.md"
echo x > "$IN/snap-ok/consumer.ts"; echo '{}' > "$IN/snap-bad1/workflow-result.json"; echo x > "$IN/snap-bad2/review-report.md"
printf 'diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-a\n+b\n' > "$IN/diff.patch"
echo a > "$IN/base/src/a.ts"; echo b > "$IN/head/src/a.ts"
HREAL="$(cd "$H" && pwd -P)"
mkdir -p "$H/dev/repo/src"; echo b > "$H/dev/repo/src/a.ts"   # --repo 로 여는 대상 저장소(실제 홈 아래 — macOS 저장소 모양)

roll() {   # $1=파일 · $2=deny 여부(1/0) · 나머지=도구 호출 명령들 → rollout jsonl
  local f="$1" deny="$2"; shift 2
  python3 - "$f" "$HREAL" "$deny" "$@" <<'PY'
import json, sys
f, home, deny, cmds = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4:]
ents = ([{"path": {"type": "path", "path": home}, "access": "deny"}] if deny else []) + [{"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": ents}}}}]
for c in cmds:
    if c == "SPAWN" or c.startswith("SPAWN:"):
        args = json.dumps({"agent_type": c.split(":", 1)[1]}) if ":" in c else "{}"
        rows.append({"type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "arguments": args}})
    elif c.startswith("RAWINPUT:"):   # input 그대로 — 실제 rollout 은 JS 프로그램이라 작은따옴표 문자열도 온다
        rows.append({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": c[len("RAWINPUT:"):]}})
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
roll "$T/r-repo.jsonl" 1 "rg --files $HREAL/dev/repo -g '!.git'" "find $HREAL/dev/repo -name '*.ts'" "grep -rn b $HREAL/dev/repo"
roll "$T/r-repomix.jsonl" 1 "rg b $HREAL/dev/repo ~"
roll "$T/r-quoted.jsonl" 1 'cat "work dir/review-report.md"'
roll "$T/r-pattern.jsonl" 1 "rg -n 'review-report\\.md' scripts"
roll "$T/r-sq.jsonl" 1 "RAWINPUT:const r = await tools.exec_command({cmd:'cat review-report.md',max_output_tokens:2000});"

run() {    # $1=셀 · $2=shim 출력 파일(없으면 빈 값) · $3=rollout 목록(쉼표) · 나머지=런처 인자 · CSID=세션 id(기본 = 선택 파일 없는 id) · HOMEX=임시 "실제 홈"(기본 $H)
  local name="$1" outf="$2" rolls="$3"; shift 3
  local d="$T/c-$name"; mkdir -p "$d/out"
  local body="ok"; [ -n "$outf" ] && body="$(cat "$outf")"
  local start; start=$(date +%s)
  local pg=(); [ -n "${PG:-}" ] && pg=(perl -e 'setpgrp(0, 0); open(my $f, ">", shift) or die; print $f $$; close $f; exec @ARGV' "$d/pgid")
  ${pg[@]+"${pg[@]}"} env -u CODEX_HOME -u FZ_GPT_CHOICE_DIR HOME="${HOMEX:-$H}" CLAUDE_CODE_SESSION_ID="${CSID:-arm-no-choice}" \
    FZ_TELEMETRY_DIR="$d/tel" FZ_SHIM_CAPTURE="$d/argv.json" FZ_SHIM_ENV_CAPTURE="$d/env.txt" \
    FZ_SHIM_OUTPUT="$body" FZ_SHIM_ROLLOUT="$rolls" ${SLEEP:+FZ_SHIM_SLEEP="$SLEEP"} ${SLEEP:+FZ_SHIM_TAG="$RUNTAG-$name"} ${IGNORE_TERM:+FZ_SHIM_IGNORE_TERM=1} ${TMPX:+TMPDIR="$TMPX"} \
    bash "$L" "$@" --arm A --run-id "$name" --out-dir "$d/out" > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"; echo $(( $(date +%s) - start )) > "$d/secs"
}
rc() { cat "$T/c-$1/rc" 2>/dev/null || echo "?"; }
called() { [ -s "$T/c-$1/argv.json" ] && echo 1 || echo 0; }
count() { [ -s "$T/c-$1/argv.json" ] || { echo 0; return; }
  python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1], encoding="utf-8"))).count(sys.argv[2]))' "$T/c-$1/argv.json" "$2"; }
audit() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$T/c-$1/out/A-$1.audit.json" "$2" 2>/dev/null || echo "-"; }
# 모델·effort 전달 판정 — argv 원소 단위로 센다(프롬프트 본문 안의 같은 글자는 세지 않는다)
leak() {   # $1=셀 — 모델·effort 를 넘기는 argv 원소 수('model=…' · 'model_reasoning_effort…' · '--model' · '-m'). CLI 를 부르지 않았으면 '-'
  [ -s "$T/c-$1/argv.json" ] || { echo "-"; return; }
  python3 -c 'import json,sys; print(sum(1 for x in json.load(open(sys.argv[1], encoding="utf-8")) if x.startswith(("model=", "model_reasoning_effort")) or x in ("--model", "-m")))' "$T/c-$1/argv.json"
}
argc() {   # $1=셀 · $2=값 — argv 에서 '-c' 바로 뒤에 그 값이 오는 횟수(CLI 를 부르지 않았으면 '-')
  [ -s "$T/c-$1/argv.json" ] || { echo "-"; return; }
  python3 -c 'import json,sys; a=json.load(open(sys.argv[1], encoding="utf-8")); print(sum(1 for i in range(len(a) - 1) if a[i] == "-c" and a[i + 1] == sys.argv[2]))' "$T/c-$1/argv.json" "$2"
}
gline()  { grep '^GPT-CHOICE ' "$T/c-$1/stderr" 2>/dev/null | head -1; }   # 런처 stderr 의 적용값 줄(래퍼 줄의 사본)
gcount() { grep -c '^GPT-CHOICE ' "$T/c-$1/stderr" 2>/dev/null; }
# 거부한 쪽 판정 — 런처 자신의 die 는 런처 stderr 에 INDEPENDENT-FAIL 을, 래퍼의 die 는 래퍼 로그(.wrapper.log)에 GATE-FAIL 을 찍는다
wfail() { grep -c "^GATE-FAIL(10): $2 " "$T/c-$1/out/A-$1.wrapper.log" 2>/dev/null; }   # $2=플래그 — 래퍼 로그의 그 플래그 거부 줄 수(로그가 없으면 빈 값)
lfail() { grep -c '^INDEPENDENT-FAIL' "$T/c-$1/stderr" 2>/dev/null; }                 # 런처가 스스로 멈춘 줄 수

# ① plan 정상 — 역할 본문 1회 · 격리 환경 · sandbox_mode 없음 · 산출 넷 · 잠금 · 격리 폴더 정리
run plan "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --snapshot "$IN/snap-ok" --keep-iso
check "plan: exit 0" "$(rc plan)" 0
check "plan: fz-planner 본문 1회" "$(count plan '# fz-planner — Independent Plan Generation Skill')" 1
check "plan: 주입 마커가 격리 사본 폴더를 가리킨다" "$(count plan '[fz-gpt-skill-injected] fz-planner (/')" 1
check "plan: 요구 원문이 과제에 있다" "$(count plan 'REQ-MARK-7')" 1
check "plan: sandbox_mode 안 넘김(--config-permissions)" "$(count plan 'sandbox_mode')" 0
check "plan: --effort 없음 · 선택 없음 → argv 에 모델·effort 0(런처 기본값 없음 — config 그대로)" "$(leak plan)" 0
check "plan: 런처 stderr 에 래퍼의 GPT-CHOICE 한 줄(출처 config = 격리 config 값)" "$(gcount plan)|$(gline plan)" "1|GPT-CHOICE model=m-test (config) effort=medium (config)"
ISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-plan/env.txt")"
[ -n "$ISO" ] && [ "$(sed -n 's/^HOME=//p' "$T/c-plan/env.txt")" = "$ISO/home" ] && ok "plan: CLI 는 격리 HOME · 격리 CODEX_HOME 으로 돈다" || no "plan: 격리 환경이 아니다 — $(tr '\n' ' ' < "$T/c-plan/env.txt")"
CFG="$ISO/gpt-home/config.toml"
[ "$(head -1 "$CFG" 2>/dev/null)" = 'default_permissions = "fz-iso"' ] && ok "plan: config 첫 줄 = default_permissions" || no "plan: config 첫 줄이 default_permissions 가 아니다"
grep -q "^\"$HREAL\" = \"deny\"$" "$CFG" 2>/dev/null && grep -q "^\"$ISO\" = \"read\"$" "$CFG" && ok "plan: 실제 홈 deny · 격리 폴더 read" || no "plan: 권한 프로필에 홈 deny · 격리 read 가 없다"
grep -q '^memories = false$' "$CFG" 2>/dev/null && grep -q '^model = "m-test"$' "$CFG" && grep -q '^model_reasoning_effort = "medium"$' "$CFG" \
  && ok "plan: memories 끔 · 최상위 model · model_reasoning_effort 두 줄 옮김" || no "plan: memories · model · model_reasoning_effort 줄"
check "plan: 격리 config 의 model 계열 줄은 그 두 줄뿐(표 안의 줄은 옮기지 않는다)" "$(grep -c '^model' "$CFG" 2>/dev/null)" 2
grep -q 'SECRET-TOKEN-XYZ' "$CFG" 2>/dev/null && no "plan: 실제 config 의 비밀 줄이 격리 config 로 샜다" || ok "plan: 실제 config 의 다른 줄은 옮기지 않는다"
[ -L "$ISO/gpt-home/auth.json" ] && [ ! -L "$ISO/gpt-home/skills/fz-planner" ] && [ -f "$ISO/gpt-home/skills/fz-planner/SKILL.md" ] \
  && ok "plan: 인증은 링크 · 스킬은 사본" || no "plan: 인증 링크 · 스킬 사본"
[ -f "$ISO/input/snapshot/snap-ok/consumer.ts" ] && ok "plan: 스냅샷을 격리 입력으로 복사" || no "plan: 스냅샷 복사 없음"
for s in json md audit.json; do [ -s "$T/c-plan/out/A-plan.$s" ] && ok "plan: 산출 .$s" || no "plan: 산출 .$s 없음"; done
check "plan: rollout 사본 1" "$(ls "$T/c-plan/out/A-plan.rollouts" 2>/dev/null | wc -l | tr -d ' ')" 1
check "plan: 감사 격리 적용" "$(audit plan isolationApplied)" True
check "plan: 감사 적중 0" "$(audit plan hits)" "[]"
[ ! -e "$T/c-plan/out/A-plan.json.lock" ] && ok "plan: 잠금 해제" || no "plan: 잠금이 남았다"
# resume 입력(S23) — --keep-iso 면 감사가 격리 폴더와 세션 ID 파일을 가리킨다(fz-plan Phase 2 resume 교차가 둘을 쓴다)
check "plan: 감사 iso = --keep-iso 로 남긴 격리 폴더" "$(audit plan iso)" "$ISO"
check "plan: 감사 sessionFile = 세션 ID 파일" "$(audit plan sessionFile)" "$T/c-plan/out/A-plan.json.session"
check "plan: 세션 파일 = 세션 ID" "$(tr -d '[:space:]' < "$T/c-plan/out/A-plan.json.session" 2>/dev/null)" "11111111-2222-3333-4444-555555555555"
# ⑫ 격리 폴더 정리(cleanup — resume 교차 뒤 Lead 가 부른다). 이름 · gpt-home 이 맞을 때만 지우고, 아니면 아무것도 지우지 않는다
bash "$L" cleanup --iso "$T" >/dev/null 2>&1; check "cleanup: 런처가 만든 이름이 아니면 exit 10" "$?" 10
[ -d "$T/c-plan" ] && ok "cleanup: 거부한 폴더는 그대로다" || no "cleanup: 거부한 폴더가 지워졌다"
mkdir -p "$T/fz-gpt-iso.Zz9Zz9"; bash "$L" cleanup --iso "$T/fz-gpt-iso.Zz9Zz9" >/dev/null 2>&1
check "cleanup: 이름만 같고 gpt-home 이 없으면 exit 10" "$?" 10
bash "$L" cleanup >/dev/null 2>&1; check "cleanup: --iso 가 없으면 exit 10" "$?" 10
bash "$L" cleanup --iso "$ISO" >/dev/null 2>&1; check "cleanup: --keep-iso 로 남긴 격리 폴더 exit 0" "$?" 0
[ -n "$ISO" ] && [ ! -e "$ISO" ] && ok "cleanup: 격리 폴더가 사라졌다" || no "cleanup: 격리 폴더가 남았다: $ISO"

# ② review 정상 — fz-reviewer 본문 1회 · base · head 복사 · 격리 폴더는 기본으로 지운다
run review "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --base "$IN/base" --head "$IN/head"
headsum() { python3 -c 'import json,sys; h=json.load(open(sys.argv[1]))["head"]; print(h["expected"], h["present"], ",".join(h["missing"]))' "$T/c-$1/out/A-$1.audit.json" 2>/dev/null || echo "-"; }
check "review: 감사 head — 변경 후 경로 1 · 있음 1 · 빠짐 없음" "$(headsum review)" "1 1 "
check "review: exit 0" "$(rc review)" 0
check "review: fz-reviewer 본문 1회" "$(count review '# fz-reviewer — Code Review Skill')" 1
check "review: --effort 없음 · 선택 없음 → argv 에 모델·effort 0" "$(leak review)" 0
RISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-review/env.txt")"
[ -n "$RISO" ] && [ ! -e "$RISO" ] && ok "review: 격리 폴더를 지웠다(--keep-iso 없음)" || no "review: 격리 폴더가 남았다: $RISO"

# ②-b 감사 입력 해시 · 런처 → 병합(S22) — 병합은 감사의 diff 해시로 stale 을 가린다. 손으로 만든 감사가 아니라 런처 실제 산출로 본다
inp() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("inputs", {}).get(sys.argv[2], "-"))' "$T/c-$1/out/A-$1.audit.json" "$2" 2>/dev/null || echo "-"; }
check "review: --keep-iso 가 없으면 감사 iso 는 없다" "$(audit review iso)" None
check "review: 감사에 GPT 가 본 diff 의 sha256" "$(inp review diff.patch)" "$(shasum -a 256 "$IN/diff.patch" | cut -d' ' -f1)"
check "plan: 감사에 요구의 sha256" "$(inp plan requirement.md)" "$(shasum -a 256 "$IN/requirement.md" | cut -d' ' -f1)"
printf '{"issues": []}\n' > "$T/claude-empty.json"
python3 "$R/scripts/review_merge.py" --claude "$T/claude-empty.json" --gpt "$T/c-review/out/A-review.json" --diff "$IN/diff.patch" > /dev/null 2>&1
check "런처→병합: 같은 diff 면 병합한다" "$?" 0
cp "$IN/diff.patch" "$T/diff-changed.patch"; printf '+c\n' >> "$T/diff-changed.patch"
python3 "$R/scripts/review_merge.py" --claude "$T/claude-empty.json" --gpt "$T/c-review/out/A-review.json" --diff "$T/diff-changed.patch" > /dev/null 2>&1
check "런처→병합: diff 가 바뀌면 stale 로 거부(exit 1)" "$?" 1

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
# ~/.claude 가 링크인 실제 홈(대상은 같은 홈 아래 claude-data) — --repo 든 직접 입력 파일이든 링크 경로 · 링크 대상 경로 어느 쪽으로 적어도
#   같은 금지 입력이다(exit 15 · CLI 미호출 · ~/.claude 사유 줄 · 빈 stdout). 막지 못하면 CLI 를 부른 뒤 감사가 15 를 내므로 종료값만으로는 가르지 못한다
HL="$T/linkhome"; mkdir -p "$HL/.codex" "$HL/claude-data/projects/p"; ln -s "$HL/claude-data" "$HL/.claude"
cp "$H/.codex/auth.json" "$HL/.codex/auth.json"; echo "claude log" > "$HL/claude-data/projects/p/notes.md"
HOMEX="$HL" run claude-link-repo "" "" plan --requirement "$IN/requirement.md" --repo "$HL/.claude/projects/p"
HOMEX="$HL" run claude-link-target-repo "" "" plan --requirement "$IN/requirement.md" --repo "$HL/claude-data/projects/p"
HOMEX="$HL" run claude-link-file "" "" plan --requirement "$HL/.claude/projects/p/notes.md"
HOMEX="$HL" run claude-link-target-file "" "" review --diff "$HL/claude-data/projects/p/notes.md"
for c in claude-link-repo claude-link-target-repo claude-link-file claude-link-target-file; do
  check "금지 입력($c): exit 15 · CLI 미호출 · ~/.claude 사유 줄 · 빈 stdout" \
    "$(rc $c)|$(called $c)|$(grep -cF '~/.claude 아래(에이전트 로그 · journal)' "$T/c-$c/stderr" 2>/dev/null)|$(wc -c < "$T/c-$c/stdout" | tr -d ' ')" "15|0|1|0"
done
# ③-b --repo 의 .claude · .fz-work 아래(링크면 대상 실경로) 직접 입력 · 폴더 입력 → exit 15 · CLI 미호출 · 저장소 사유 줄 · 빈 stdout.
#      직접 입력은 격리 입력 폴더로 이름을 바꿔 복사되므로 권한 표 deny 도 rollout 감사도 보지 못한다 — 게이트가 막아야 한다.
#      그대로인 칸: self-link(.claude → 저장소 자신 · .fz-work → 저장소의 부모)면 저장소 안 정상 입력은 통과 · --repo 가 없으면 이 규칙이 없다
RD="$H/dev/rc-direct"; mkdir -p "$RD/.claude/notes" "$RD/src"; echo "claude log" > "$RD/.claude/notes/notes.md"
RL="$H/dev/rc-link"; mkdir -p "$RL/src" "$T/rc-out"; ln -s "$T/rc-out" "$RL/.claude"; echo "claude log" > "$T/rc-out/notes.md"
RF="$H/dev/rc-fz"; mkdir -p "$RF/.fz-work/T-1" "$RF/src"; echo "claude log" > "$RF/.fz-work/T-1/notes.md"
RS="$H/dev/rc-self"; mkdir -p "$RS/docs"; ln -s "$RS" "$RS/.claude"; ln -s "$H/dev" "$RS/.fz-work"; cp "$IN/requirement.md" "$RS/docs/requirement.md"
RT="$H/dev/rc-root"; mkdir -p "$RT/docs"; ln -s / "$RT/.claude"; cp "$IN/requirement.md" "$RT/docs/requirement.md"   # .claude → / — 저장소 · 홈을 품는 맨 끝 조상
run repo-claude-direct-input "" "" plan --requirement "$RD/.claude/notes/notes.md" --repo "$RD"
run repo-claude-link-input "" "" plan --requirement "$T/rc-out/notes.md" --repo "$RL"
run repo-claude-link-path-input "" "" plan --requirement "$RL/.claude/notes.md" --repo "$RL"
run repo-fzwork-input "" "" plan --requirement "$RF/.fz-work/T-1/notes.md" --repo "$RF"
run repo-claude-folder-input "" "" review --diff "$IN/diff.patch" --snapshot "$RD/.claude/notes" --repo "$RD"
for c in repo-claude-direct-input repo-claude-link-input repo-claude-link-path-input repo-fzwork-input repo-claude-folder-input; do
  want=1; [ "$c" = repo-claude-folder-input ] && want=2   # 폴더 입력은 폴더 · 그 안 파일 하나 — 사유 줄 둘
  check "$c — exit 15 · CLI 미호출 · 저장소 사유 줄 $want · 빈 stdout" \
    "$(rc $c)|$(called $c)|$(grep -cF '저장소 .claude · .fz-work 아래' "$T/c-$c/stderr" 2>/dev/null)|$(wc -c < "$T/c-$c/stdout" | tr -d ' ')" "15|0|$want|0"
done
run repo-claude-self-link "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$RS/docs/requirement.md" --repo "$RS"
check "repo-claude-self-link — .claude → 저장소 자신 · .fz-work → 저장소의 부모: 저장소 안 정상 입력 exit 0 · CLI 호출" "$(rc repo-claude-self-link)|$(called repo-claude-self-link)" "0|1"
run repo-claude-root-link "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$RT/docs/requirement.md" --repo "$RT"
check "repo-claude-root-link — .claude → /: 저장소 안 정상 입력 exit 0 · CLI 호출" "$(rc repo-claude-root-link)|$(called repo-claude-root-link)" "0|1"
run repo-claude-no-repo "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$RD/.claude/notes/notes.md"
check "repo-claude-no-repo — --repo 없이 같은 파일: 이 규칙 밖(exit 0)" "$(rc repo-claude-no-repo)|$(called repo-claude-no-repo)" "0|1"

# ④ rollout 감사 → exit 15 + 오염 표시
run aud1 "$HERE/sample-plan-ok.json" "$T/r-claude.jsonl" plan --requirement "$IN/requirement.md"
run aud2 "$HERE/sample-plan-ok.json" "$T/r-find.jsonl" plan --requirement "$IN/requirement.md"
run aud3 "$HERE/sample-plan-ok.json" "$T/r-home.jsonl" plan --requirement "$IN/requirement.md"
run aud4 "$HERE/sample-plan-ok.json" "$T/r-nodeny.jsonl" plan --requirement "$IN/requirement.md"
for c in aud1 aud2 aud3 aud4; do
  check "감사($c): exit 15" "$(rc $c)" 15
  [ -s "$T/c-$c/out/A-$c.contaminated" ] && ok "감사($c): 오염 표시 파일" || no "감사($c): 오염 표시가 없다"
  check "감사($c): 세션을 넘기지 않는다(sessionFile null · 세션 파일 삭제)" \
    "$(audit $c sessionFile)|$([ -e "$T/c-$c/out/A-$c.json.session" ] && echo 남음 || echo 없음)" "None|없음"
done
check "감사(aud4): 격리 미적용으로 판정" "$(audit aud4 isolationApplied)" False
# ④b 허용된 저장소(--repo) 안 재귀 검색은 오염이 아니다 — 같은 조각의 다른 뿌리(~)는 여전히 적중
#    ⛔ S27 실측: macOS 저장소(/Users 아래)를 GPT 가 절대 경로로 검색하자 옛 규칙이 exit 15 로 첫 패스를 버렸다
run audrepo "$HERE/sample-plan-ok.json" "$T/r-repo.jsonl" plan --requirement "$IN/requirement.md" --repo "$H/dev/repo"
check "감사(repo 안 재귀 검색): exit 0" "$(rc audrepo)" 0
check "감사(repo 안 재귀 검색): 적중 0" "$(audit audrepo hits)" "[]"
run audmix "$HERE/sample-plan-ok.json" "$T/r-repomix.jsonl" plan --requirement "$IN/requirement.md" --repo "$H/dev/repo"
check "감사(repo 뒤 ~ 재귀): exit 15" "$(rc audmix)" 15
run audq "$HERE/sample-plan-ok.json" "$T/r-quoted.jsonl" plan --requirement "$IN/requirement.md"
check "감사(직렬화된 큰따옴표 경로의 산출물 참조): exit 15" "$(rc audq)" 15
run audpat "$HERE/sample-plan-ok.json" "$T/r-pattern.jsonl" plan --requirement "$IN/requirement.md"
check "감사(정규식 패턴 'review-report\\.md' 검색은 참조가 아니다): exit 0" "$(rc audpat)" 0
run audsq "$HERE/sample-plan-ok.json" "$T/r-sq.jsonl" plan --requirement "$IN/requirement.md"
check "감사(JS 작은따옴표 명령의 산출물 참조): exit 15" "$(rc audsq)" 15
# ④b-2 F-596 — 허용 저장소 안에서 금지 경로 문자열을 '찾는' rg · grep 은 참조가 아니다(패턴 자리 낱말은 세 규칙에서 빠진다 · 적중 0).
#   ⛔ 경로 인자 · 실제 읽기 · 허용 밖 경로 인자 · 못 읽는 옵션(--pre) · cd 뒤 상대 경로는 그대로 15 · '금지 산출물 참조'(닫힌 쪽으로 실패)
f596() {   # $1=셀 · $2=명령 → 'exit|첫 적중 규칙'
  roll "$T/r-$1.jsonl" 1 "$2"
  run "$1" "$HERE/sample-plan-ok.json" "$T/r-$1.jsonl" plan --requirement "$IN/requirement.md" --repo "$H/dev/repo"
  printf '%s|%s' "$(rc "$1")" "$(python3 -c 'import json,sys; h=json.load(open(sys.argv[1])).get("hits") or []; print(h[0]["rule"] if h else "-")' "$T/c-$1/out/A-$1.audit.json" 2>/dev/null || echo no-audit)"
}
check "f596-search-pattern-rg — rg -e '~/(\\.claude/…)' <repo> 는 적중 0 · exit 0" "$(f596 f596-rg "rg -n --hidden -e '~/(\\.claude/(hooks|projects|agent-memory)|\\.codex/)' $HREAL/dev/repo")" "0|-"
check "f596-search-pattern-grep — grep -rnE '\\.claude/…' <repo>/src 는 적중 0 · exit 0" "$(f596 f596-grep "grep -rnE '\\.claude/(projects|hooks)' $HREAL/dev/repo/src | head -20")" "0|-"
check "f596-path-arg-hit — rg -n TODO <repo>/.claude/ (경로 인자)는 15" "$(f596 f596-path "rg -n TODO $HREAL/dev/repo/.claude/")" "15|금지 산출물 참조"
check "f596-pattern-and-forbidden-path-hit — rg '\\.claude/' <home>/.claude/projects 는 15" "$(f596 f596-patpath "rg -n '\\.claude/' $HREAL/.claude/projects")" "15|금지 산출물 참조"
check "f596-real-read-hit — 금지 경로 실제 읽기(cat <home>/.claude/…)는 15" "$(f596 f596-read "cat $HREAL/.claude/projects/p/notes.md")" "15|금지 산출물 참조"
check "f596-unknown-option-fail-closed — 표에 없는 옵션(--pre)이면 패턴을 가르지 않는다(15)" "$(f596 f596-opt "rg --pre cat -n '\\.claude/' $HREAL/dev/repo")" "15|금지 산출물 참조"
check "f596-cd-relative-fail-closed — cd 뒤 상대 경로 검색은 패턴을 가르지 않는다(15)" "$(f596 f596-cd "cd $HREAL/dev/repo && rg -n '\\.claude/' .")" "15|금지 산출물 참조"
check "f596-quoted-operator-is-a-word — 따옴표 안 '|' 는 파이프가 아니다: cat '|' rg review-report.md 는 cat 하나의 읽기(15 · GPT check 8.5 P2)" "$(f596 f596-qop "cat '|' rg review-report.md")" "15|금지 산출물 참조"
check "f596-escaped-operator-is-a-word — 역슬래시로 막은 ';' 도 낱말이다: cat \\; rg review-report.md 는 15" "$(f596 f596-eop "cat \\; rg review-report.md")" "15|금지 산출물 참조"
check "f596-real-pipe-still-splits — 따옴표 밖 파이프 뒤 rg 패턴은 그대로 면제(0)" "$(f596 f596-pipe "cat $HREAL/dev/repo/README.md | rg -n 'review-report\\.md'")" "0|-"
# ④b-3 F-595 — 과제 프롬프트에 입력 폴더 읽기 허용 줄 · 감사 inputRefs(입력 참조 관측치 — 전체 열람 증명 아님 · rollout 없으면 "unknown")
check "f595-prompt-input-allowed — 과제에 '상위 폴더가 막혀 있어도 입력 폴더 읽기 허용' 줄 1 · 읽기 제한 줄도 남는다" \
  "$(count plan '상위 폴더(임시 루트)가 막혀 있어도 읽기가 허용돼 있다')|$(count plan '읽기는 권한 프로필로 제한돼 있다')" "1|1"
check "f595-input-refs-cwd-input — 작업 폴더가 입력 폴더(plan · --repo 없음)면 상대 경로 입력 읽기(cat requirement.md)를 센다" "$(audit plan inputRefs)" 1
check "f595-input-refs-zero — 저장소만 읽은 run(--repo) 은 0" "$(audit audrepo inputRefs)" 0
roll "$T/r-headcmd.jsonl" 1 "head -1 $HREAL/dev/repo/src/a.ts"
run f595-headcmd "$HERE/sample-review-ok.json" "$T/r-headcmd.jsonl" review --diff "$IN/diff.patch" --head "$IN/head" --repo "$H/dev/repo"
check "f595-input-refs-command-name — 작업 폴더가 입력 폴더여도 명령 이름(head)은 입력 head/ 참조가 아니다(0)" "$(rc f595-headcmd)|$(audit f595-headcmd inputRefs)" "0|0"
run f595-norollout "$HERE/sample-plan-ok.json" "" plan --requirement "$IN/requirement.md"
check "f595-input-refs-unknown — rollout 이 없으면(추적 불가) \"unknown\" · exit 15(격리 미적용)" "$(rc f595-norollout)|$(audit f595-norollout inputRefs)" "15|unknown"
#   --repo 가 있으면 작업 폴더가 저장소라 입력은 절대 경로로만 닿는다 — 가짜 CLI 앞에 호출 시점의 격리 폴더(CODEX_HOME 의 부모)로 rollout 을 쓰는 래퍼를 둔다
mkdir -p "$T/isobin"; cat > "$T/isobin/codex" <<'WRAP'
#!/bin/bash
case "${1:-} ${2:-}" in "login status"*|"--version "*) exec "$F595_SHIM/codex" "$@" ;; esac
if [ -n "${CODEX_HOME:-}" ]; then
  mkdir -p "$CODEX_HOME/sessions/2026/09/28"
  python3 - "$CODEX_HOME/sessions/2026/09/28/rollout-iso.jsonl" "$F595_HOME" "cat ${CODEX_HOME%/gpt-home}/input/snapshot/snap-ok/consumer.ts" <<'PY'
import json, sys
f, home, cmd = sys.argv[1:4]
ents = [{"path": {"type": "path", "path": home}, "access": "deny"}, {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": ents}}}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": "tools.exec_command({cmd:" + json.dumps(cmd) + "})"}}]
open(f, "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in rows) + "\n")
PY
fi
exec "$F595_SHIM/codex" "$@"
WRAP
chmod +x "$T/isobin/codex"
PATH="$T/isobin:$PATH" F595_SHIM="$R/tests/fixtures/gpt/_shim" F595_HOME="$HREAL" \
  run f595-abs "$HERE/sample-plan-ok.json" "" plan --requirement "$IN/requirement.md" --snapshot "$IN/snap-ok" --repo "$H/dev/repo"
check "f595-input-refs-absolute — --repo 실행에서 격리 입력 폴더 절대 경로를 읽은 명령 1 · exit 0" "$(rc f595-abs)|$(audit f595-abs inputRefs)" "0|1"
# ④c 재귀 검색 규칙 문자열 단위 — /Users 경로(macOS 저장소 모양). ⛔ 파일을 만들지 않는다 — 실제 홈을 건드리지 않는다
#    ④b 의 가짜 홈은 /Users 밖이라 옛 결함(/Users 아래 전부 적중)을 재현하지 못한다 — 규칙 블록을 직접 꺼내 잰다
UNIT="$(python3 - "$L" <<'UPY'
import json, os, re, shlex, sys
t = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"^FZ_ART_NAMES='([^']*)'", t, re.M)
if m:
    os.environ["FZ_ART_NAMES"] = m.group(1)
env = {"re": re, "os": os, "json": json, "shlex": shlex, "repo": "/Users/u/dev/repo", "iso": "/private/tmp/iso"}
exec(t[t.index("ROOTS = r"):t.index("def home_ref(cmd):")], env)
hit = env.get("recurse_hit") or (lambda c: any(x.search(c) for x in env["RECURSE"]))
cases = [("rg --files /Users/u/dev/repo -g '!.git'", False), ("find /Users/u/dev/repo -name x", False),
         ("rg foo /Users/u/dev/repo ~", True), ("rg --files /Users/u", True), ("find / -name x", True),
         ("grep -rn x /Users/u/dev/other", True),
         # 리뷰 F6 — 공백 든 따옴표 패턴은 뿌리가 아니다 · 패턴을 지운 뒤에도 그 뒤 뿌리는 적중 · `..` 탈출은 적중
         ("rg -n 'bounds.width / 2' Sources/", False), ("grep -rn 'x ~ y' .", False),
         ("rg 'a b' /Users/someone", True), ("rg x /Users/u/dev/repo/../..", True)]
out = ["ok" if hit(c) == w else "bad:" + c.split()[0] for c, w in cases]
forbid = env.get("forbid_hit")
fcases = [("cat T-1/plan/plan-final.md", True), ("cat work/workflow-result.json", True), ("cat ~/.claude/projects/p/a.jsonl", True),
          ("cat Sources/Foo/code-context-builder.swift", False), ("cat ci/test-result.json", False), ("rg 'workflow-result' scripts", False)]
out += ["ok" if forbid and forbid(c) == w else "fbad:" + c.split()[-1] for c, w in fcases]
# 역검증 ISSUE-001 — rollout 은 명령을 JSON 문자열에 담는다: custom_tool_call input · function_call arguments
roll = lambda c: "tools.exec_command({cmd:" + json.dumps(c) + "})"
fc = lambda c: json.dumps({"cmd": c})
# 실제 0.159.2 rollout 의 exec 입력은 JS 프로그램이다(S27 저장 rollout 실측) — 여러 호출 묶음 · 경로 배열
js = lambda *cs: "const results = await Promise.allSettled([\n" + ",\n".join("  tools.exec_command({cmd:" + json.dumps(c) + ",max_output_tokens:4000})" for c in cs) + "\n]);"
arr = lambda *ps: "const paths = [\n" + ",\n".join(json.dumps(p) for p in ps) + "\n];\nfor (const p of paths) await tools.exec_command({cmd: 'cat ' + p});"
sq = lambda c: "tools.exec_command({cmd:'" + c.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n") + "'})"   # JS 작은따옴표 문자열
POS = ['cat "work dir/review-report.md"', 'cat "plan/plan-final.md"', 'cat work/code-context".md"', 'cat "T-1/plan/workflow-result.json"',
       "cat work/review-report.md\nwc -l requirement.md", "cat review-report.md", "cat work/review-report.md | head", "wc -l a.txt work/plan-final.md"]
NEG = ["rg -n 'review-report\\.md' scripts", "cat src/review-report.md,backup", "cat src/code-context.md:backup",
       'rg -n "workflow-result" scripts', 'cat "Sources/Foo/code-context-builder.swift"']
scases = [(f(c), True) for c in POS for f in (roll, fc, js, sq)] + [(f(c), False) for c in NEG for f in (roll, fc, js, sq)]
scases += [(js("pwd", 'cat "T-1/review/triage.md"'), True), (arr("Domain/A.swift", "T-1/plan/plan-v2.md"), True),
           ("const paths = ['T-1/review/self-review.md'];", True), ('{"cmd":"cat ~\\/.claude\\/projects\\/p\\/a.jsonl"}', True),
           (arr("Domain/A.swift", "Sources/code-context-builder.swift"), False),
           ('const rx = /\\/\\//; await tools.exec_command({cmd:"cat review-report.md"});', True),
           ('const rx = /\\/*/; await tools.exec_command({cmd:"cat review-report.md"});', True),
           ("// don" + chr(39) + "t read it twice\nawait tools.exec_command({cmd:\"cat work/review-report.md\"});", True),
           ("/* don" + chr(39) + "t */ await tools.exec_command({cmd:\"cat work/review-report.md\"});", True)]
out += ["ok" if forbid and forbid(c) == w else f"sbad{i}" for i, (c, w) in enumerate(scases)]
print(f"ALL-OK n={len(out)}" if all(x == "ok" for x in out) else " ".join(out))
UPY
)"
check "감사 규칙(/Users 저장소 안 검색은 예외 · 홈 · 루트 · 저장소 밖 · 따옴표 패턴 뒤 뿌리 · \`..\` 은 적중 · 산출물 이름은 경로 성분 단위 · 직렬화 따옴표를 걷는다)" "$UNIT" "ALL-OK n=77"

# ⑤ 하위 에이전트 — rollout 둘 다 감사 · spawn 수를 적는다(가짜 CLI 라 config 의 `[agents] enabled = false` 를 따르지 않는다 — 감사 경로만 본다)
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
sleep 1; tagged_alive "$RUNTAG-hang" && no "시간 초과: CLI 의 자식이 고아로 남았다" || ok "시간 초과: CLI 의 자식까지 종료"
# ⑦b 정상 run 뒤 감시자의 sleep 이 남지 않는다 — 옛 판은 run 마다 `sleep $TIMEOUT` 을 고아로 남겼다(리뷰 F5)
PG=1 run watchok "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --timeout 1797
check "감시자 정리: exit 0" "$(rc watchok)" 0
WPG="$(cat "$T/c-watchok/pgid" 2>/dev/null)"
if [ -z "$WPG" ]; then no "감시자 정리: 런처 프로세스 그룹 id 를 얻지 못했다(판정 불가)"
else
  sleep 1; pg_alive "$WPG" && no "감시자 정리: 런처 프로세스 그룹에 고아(감시자 sleep)가 남았다" || ok "감시자 정리: 고아 sleep 없음"
  kill -- -"$WPG" 2>/dev/null   # 옛 판을 잴 때 남는 고아를 치운다 — 이 셀의 프로세스 그룹만
fi
# ⑦c TERM 을 무시하는 자손 — 시간 초과면 KILL 까지 간다. 옛 판은 TERM 에 래퍼가 죽자 감시자를 먼저 죽여 자손이 남았다(리뷰 F5 · G2)
IGNORE_TERM=1 SLEEP=29.6 run hangterm "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --timeout 2
check "TERM 무시 자손: exit 16" "$(rc hangterm)" 16
sleep 1; tagged_alive "$RUNTAG-hangterm" && no "TERM 무시 자손: KILL 되지 않고 남았다" || ok "TERM 무시 자손: KILL 로 정리"
tagged_kill "$RUNTAG-hangterm" KILL

# ⑧ planner 거부 → exit 17
printf '%s' '{"status":"rejected","reason":"claude_plan_detected","approach":"-","affectedFiles":{"new":0,"modified":0},"steps":[],"riskMatrix":[],"stressTest":[],"implicationRegister":[],"divergencePoints":[],"projectRules":{"axes":{"architecturePattern":null,"uiStack":null,"dependencyDirection":null,"naming":null,"placement":null,"conventions":null},"rules":[],"conflicts":[],"gaps":[]},"catalogHits":[]}' > "$T/rejected.json"
run rej "$T/rejected.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
check "planner 거부: exit 17" "$(rc rej)" 17
check "planner 거부: 세션을 넘기지 않는다(sessionFile null · 세션 파일 삭제)" \
  "$(audit rej sessionFile)|$([ -e "$T/c-rej/out/A-rej.json.session" ] && echo 남음 || echo 없음)" "None|없음"

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

# ⑪-a 하위 에이전트 — 격리 config 가 늘 끈다(켜는 옵션은 없다) · agents 폴더 없음 · 프롬프트 금지 문장 · 감사 spawn 0
run rolesoff "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --keep-iso
OISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-rolesoff/env.txt")"
[ ! -e "$OISO/gpt-home/agents" ] && ok "하위 에이전트 끔: agents 폴더 없음" || no "하위 에이전트 끔: agents 폴더가 있다"
check "하위 에이전트 끔: 하위 에이전트 금지" "$(count rolesoff '하위 에이전트를 만들지 않는다.')" 1
check "하위 에이전트 끔: 감사 spawn 0" "$(audit rolesoff spawnAgent)" 0
AOFF="$(sed -n '/^\[agents\]$/,/^\[/p' "$OISO/gpt-home/config.toml" 2>/dev/null | grep -c '^enabled = false$')"
# F-436 — 격리 config 가 spawn 도구를 끈다(프롬프트 금지는 경계가 아니다)
[ "$AOFF" = 1 ] && ok "f436-agents-disabled — 격리 config: [agents] enabled = false" || no "f436-agents-disabled — [agents] enabled = false 줄 $AOFF"
rm -rf "$OISO"
# ⑪-b 걷은 옵션 --gpt-agents(하위 에이전트 렌즈 opt-in) — 옛 호출을 조용히 받지 않는다. 정문은 레지스트리 removed_inputs 로
#      '걷은 입력' 사유를 내고, 런처 직접 호출은 모르는 인자로 멈춘다 — 둘 다 exit 10 · CLI 미호출
GG="$T/c-gone-gate"; mkdir -p "$GG/tel"
env -u CODEX_HOME -u FZ_GPT_CHOICE_DIR HOME="$H" FZ_TELEMETRY_DIR="$GG/tel" FZ_SHIM_CAPTURE="$GG/argv.json" \
  bash "$R/scripts/gpt-call.sh" independent-review --diff "$IN/diff.patch" --gpt-agents --arm A --run-id gone-gate --out-dir "$GG/out" > "$GG/stdout" 2> "$GG/stderr"
echo $? > "$GG/rc"
check "retired-option-gpt-agents — 정문: exit 10 · CLI 미호출 · 걷은 입력 사유 줄" \
  "$(rc gone-gate)|$(called gone-gate)|$(grep -c '^GPT-CALL-USAGE(10): --gpt-agents was removed — ' "$GG/stderr")" "10|0|1"
run gone-direct "" "" review --diff "$IN/diff.patch" --gpt-agents
check "retired-option-gpt-agents — 런처 직접: exit 10 · CLI 미호출 · 모르는 인자 줄" \
  "$(rc gone-direct)|$(called gone-direct)|$(grep -c '^INDEPENDENT-FAIL(10): 알 수 없는 인자: --gpt-agents$' "$T/c-gone-direct/stderr")" "10|0|1"

# ⑪ 사용법 → exit 10
run u1 "" "" plan
run u2 "" "" review --diff "$IN/diff.patch" --sprint-contract "$IN/requirement.md"
run u3 "" "" plan --requirement "$IN/requirement.md" --timeout 0
for c in u1 u2 u3; do check "사용법($c): exit 10" "$(rc $c)" 10; done

# ⑬ 리뷰 반영 회귀 — 각 항목은 옛 런처에서 FAIL 한다
# ⑬a mktemp 실패 — 격리 폴더가 현재 폴더로 풀리지 않는다(bash 3.2 의 `cd ""` 는 성공한다 · 옛 판은 현재 폴더를 지웠다 — F1)
mkdir -p "$T/sandbox"; echo keep > "$T/sandbox/marker"
(cd "$T/sandbox" && TMPX=/nonexistent/fz-tmp run tmpfail "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md")
check "mktemp 실패: exit 11" "$(rc tmpfail)" 11
[ -f "$T/sandbox/marker" ] && ok "mktemp 실패: 현재 폴더가 지워지지 않는다" || no "mktemp 실패: 현재 폴더가 지워졌다"
# ⑬b 같은 stem 재실행 — 옛 .contaminated 가 남아 깨끗한 재실행을 거부하지 않는다(F2)
run rerun "$HERE/sample-plan-ok.json" "$T/r-claude.jsonl" plan --requirement "$IN/requirement.md"
check "재실행 1차(오염): exit 15" "$(rc rerun)" 15
run rerun "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
check "재실행 2차(정상): exit 0" "$(rc rerun)" 0
[ ! -e "$T/c-rerun/out/A-rerun.contaminated" ] && ok "재실행: 옛 .contaminated 가 지워졌다" || no "재실행: 옛 .contaminated 가 남았다"
# ⑬c 감사 선기록 — 래퍼가 도는 동안 감사는 'running'(exit null)이다 · 끝나면 덮인다(F2 — 중간에 멈춘 run 은 병합이 거부한다)
(SLEEP=4 run running "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md") &
RUNP=$!; sleep 2
check "감사 선기록: 실행 중 exit null" "$(audit running exit)" None
wait "$RUNP"
check "감사 선기록: 끝나면 exit 0" "$(audit running exit)" 0
# ⑬d 규칙 레코드를 원문 색인 자리에 넘기면 거부한다(F3 — Claude 해석이 GPT 첫 패스로 새는 것)
printf '%s\n' '{"schemaVersion": 1, "axes": [], "rules": [{"id": "R1", "axis": "naming", "authority": "project"}], "conflicts": [], "gaps": []}' > "$IN/records.json"
printf '%s\n' '{"schemaVersion": 1, "absent": false, "files": [], "sections": []}' > "$IN/index.json"
run rulesrec "" "" review --diff "$IN/diff.patch" --rules-index "$IN/records.json"
check "규칙 레코드 → exit 11" "$(rc rulesrec)" 11
check "규칙 레코드: CLI 미호출" "$(called rulesrec)" 0
run rulesidx "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --rules-index "$IN/index.json"
check "원문 색인 → exit 0" "$(rc rulesidx)" 0
# ⑬e --deny 는 --repo 없이도 받고 권한 프로필 deny 에 들어간다(F7 — HOME 밖 작업 폴더)
run denyonly "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --deny "$IN/snap-ok" --keep-iso
check "--deny(저장소 없이): exit 0" "$(rc denyonly)" 0
DISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-denyonly/env.txt")"
grep -qF "\"$(cd "$IN/snap-ok" && pwd -P)\" = \"deny\"" "$DISO/gpt-home/config.toml" 2>/dev/null && ok "--deny: 권한 프로필에 deny 가 있다" || no "--deny: 권한 프로필에 없다"
[ -n "$DISO" ] && bash "$L" cleanup --iso "$DISO" >/dev/null 2>&1
# ⑬j 격리 폴더의 실제 부모(TMPDIR 실경로)도 deny — 표준 임시 루트 밖 TMPDIR(Linux /tmp 포함)에서 형제 fz-gpt-iso.* 가 읽히지 않게.
#     ⛔ 부모가 이미 deny 인 경로(HOME · /private/tmp)와 같으면 한 번만 넣는다 — 같은 키가 두 번이면 CLI 가 config 를 거부한다(TOML 중복 키)
fskeys() { sed -n '/^\[permissions\.fz-iso\.filesystem\]$/,/^\[/p' "$1" 2>/dev/null | sed -n 's/^\(".*"\) = "[a-z]*"$/\1/p'; }   # $1=config — 권한 표의 경로 키
mkdir -p "$T/usertmp"
TMPX="$T/usertmp" run usertmp "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --keep-iso
UISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-usertmp/env.txt")"
[ "$(rc usertmp)" = 0 ] && [ -n "$UISO" ] && [ "${UISO%/*}" = "$T/usertmp" ] \
  && grep -qxF "\"$T/usertmp\" = \"deny\"" "$UISO/gpt-home/config.toml" && grep -qxF "\"$UISO\" = \"read\"" "$UISO/gpt-home/config.toml" \
  && ok "usertmp-parent-deny — 표준 밖 TMPDIR: 부모 실경로 deny · 격리 폴더 read" \
  || no "usertmp-parent-deny — exit $(rc usertmp) · 격리 '${UISO:-없음}' · 부모 deny 줄 $(grep -cxF "\"$T/usertmp\" = \"deny\"" "$UISO/gpt-home/config.toml" 2>/dev/null)"
[ -n "$UISO" ] && bash "$L" cleanup --iso "$UISO" >/dev/null 2>&1
TMPX="$H" run usertmpdup "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --keep-iso
VISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-usertmpdup/env.txt")"
VDUP="$(fskeys "$VISO/gpt-home/config.toml" | sort | uniq -d | tr '\n' ' ')"
[ "$(rc usertmpdup)" = 0 ] && [ "${VISO%/*}" = "$HREAL" ] && [ -z "$VDUP" ] && [ "$(grep -cxF "\"$HREAL\" = \"deny\"" "$VISO/gpt-home/config.toml" 2>/dev/null)" = 1 ] \
  && ok "usertmp-dup-key — TMPDIR = HOME: 홈 deny 한 줄 · 중복 키 없음" \
  || no "usertmp-dup-key — exit $(rc usertmpdup) · 격리 '${VISO:-없음}' · 중복 키 '${VDUP}' · 홈 deny 줄 $(grep -cxF "\"$HREAL\" = \"deny\"" "$VISO/gpt-home/config.toml" 2>/dev/null)"
[ -n "$VISO" ] && bash "$L" cleanup --iso "$VISO" >/dev/null 2>&1
#     ⛔ 부모가 --repo(read)와 같으면(TMPDIR = --repo) 부모 deny 를 넣을 수도(중복 키) 뺄 수도(형제 격리 폴더가 읽힌다) 없다 —
#        조용히 건너뛰지 않고 CLI 를 부르기 전에 exit 11 로 멈춘다. --keep-iso 로 돌려 config 가 남았다면 부모 deny 가 있는지 본다. iso 하위 명령도 같은 자리다
SR="$T/samerepo"; mkdir -p "$SR/src"; echo b > "$SR/src/a.ts"
TMPX="$SR" run usertmprepo "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --repo "$SR" --keep-iso
SOPEN=0; for c in "$SR"/fz-gpt-iso.*/gpt-home/config.toml; do [ -f "$c" ] && ! grep -qxF "\"$SR\" = \"deny\"" "$c" && SOPEN=$((SOPEN + 1)); done
SMSG="$(grep -c '^INDEPENDENT-FAIL(11): 격리 폴더의 실제 부모가 --repo 와 같다' "$T/c-usertmprepo/stderr" 2>/dev/null)"
[ "$(rc usertmprepo)" = 11 ] && [ "$(called usertmprepo)" = 0 ] && [ "$SMSG" = 1 ] && [ "$SOPEN" = 0 ] \
  && ok "usertmp-repo-conflict — TMPDIR = --repo: exit 11 · CLI 미호출 · 충돌 줄 1 · 부모를 열어 둔 config 0" \
  || no "usertmp-repo-conflict — exit $(rc usertmprepo) · CLI 호출 $(called usertmprepo) · 충돌 줄 ${SMSG:-0} · 부모를 열어 둔 config $SOPEN"
for d in "$SR"/fz-gpt-iso.??????; do [ -d "$d" ] && bash "$L" cleanup --iso "$d" >/dev/null 2>&1; done
SOUT="$(env -u CODEX_HOME HOME="$H" TMPDIR="$SR" bash "$L" iso --repo "$SR" 2> "$T/samerepo-iso.err")"; SRC=$?
SLEFT="$(ls -d "$SR"/fz-gpt-iso.* 2>/dev/null | wc -l | tr -d ' ')"
[ "$SRC" = 11 ] && [ -z "$SOUT" ] && [ "$SLEFT" = 0 ] && grep -q '^INDEPENDENT-FAIL(11): 격리 폴더의 실제 부모가 --repo 와 같다' "$T/samerepo-iso.err" \
  && ok "usertmp-repo-conflict-iso — iso 하위 명령: exit 11 · 빈 stdout · 만들던 격리 폴더 0 · 충돌 줄" \
  || no "usertmp-repo-conflict-iso — exit $SRC · stdout '${SOUT:-}' · 남은 격리 폴더 $SLEFT"
for d in "$SR"/fz-gpt-iso.??????; do [ -d "$d" ] && bash "$L" cleanup --iso "$d" >/dev/null 2>&1; done
# ⑬k 격리 폴더만 만드는 하위 명령(iso) — 런처 밖 재녹화 러너(sprint-contract-format --live)가 메인 경로와 같은 한 벌을 부른다.
#     계약: stdout = 격리 폴더 실경로 한 줄 · --repo 는 read · cwd 신뢰 · --deny 는 deny · 실패 = 0 이 아닌 종료와 빈 stdout · 정리는 부른 쪽(cleanup --iso)
KISO="$(env -u CODEX_HOME HOME="$H" bash "$L" iso --repo "$H/dev/repo" --deny "$IN/snap-ok" 2>/dev/null)"; KRC=$?
KCFG="$KISO/gpt-home/config.toml"
KNAME=0; case "${KISO##*/}" in fz-gpt-iso.??????) [ "$(printf '%s\n' "$KISO" | wc -l | tr -d ' ')" = 1 ] && KNAME=1 ;; esac
[ "$KRC" = 0 ] && [ "$KNAME" = 1 ] && [ "$(head -1 "$KCFG" 2>/dev/null)" = 'default_permissions = "fz-iso"' ] \
  && grep -qxF "\"$HREAL\" = \"deny\"" "$KCFG" && grep -qxF "\"$KISO\" = \"read\"" "$KCFG" && grep -qxF "\"$(cd "$IN/snap-ok" && pwd -P)\" = \"deny\"" "$KCFG" \
  && grep -qxF "\"$HREAL/dev/repo\" = \"read\"" "$KCFG" && grep -qxF "[projects.\"$HREAL/dev/repo\"]" "$KCFG" \
  && [ -L "$KISO/gpt-home/auth.json" ] && [ -f "$KISO/gpt-home/skills/fz-architect/SKILL.md" ] && [ -d "$KISO/home" ] \
  && ok "iso-subcommand — stdout 한 줄 = 격리 폴더 · 홈 deny · 격리 read · --deny · --repo read · 신뢰 · 인증 링크 · 스킬 사본" \
  || no "iso-subcommand — exit $KRC · stdout '${KISO:-없음}'"
[ "$KNAME" = 1 ] && [ -d "$KISO" ] && bash "$L" cleanup --iso "$KISO" >/dev/null 2>&1
KOUT="$(env -u CODEX_HOME HOME="$H" bash "$L" iso --deny "$T/no-such-dir" 2>/dev/null)"; KRC=$?
[ "$KRC" != 0 ] && [ -z "$KOUT" ] && ok "iso-subcommand-fail — 없는 --deny: 0 이 아닌 종료 · 빈 stdout" || no "iso-subcommand-fail — exit $KRC · stdout '${KOUT:-}'"
# ⑬l claude-link-grid — ~/.claude · 저장소 .claude · .fz-work 가 링크면 권한 표에 대상 실경로 deny 가 든다(저장소 쪽 링크 경로 키는 그대로).
#     홈 밖 대상은 홈 deny 가, 저장소 아래 대상은 저장소 read 가 열어 둔다. 링크 키만으로 대상이 막히는지는 실 CLI 측정 몫이다(os-deny external.sh).
#     ⛔ 새 키는 --deny · 임시 루트 · 홈 · 다른 자리의 같은 대상과 겹칠 수 있다 — 같은 키가 두 번이면 실제 CLI 가 config 를 거부하는데
#        가짜 CLI 는 config 를 읽지 않아 종료값으로 못 본다. 셀마다 같은 키 두 번 0 을 직접 단언한다(iso 하위 명령 · fskeys 재사용).
#     꼴: dir 실폴더 · out 홈 · 저장소 밖 · in-home 홈 안 · under-repo 저장소 아래 · self 자기 자리(홈이면 홈 · 저장소면 저장소) · broken 없는 대상
#         게이트 꼴 — 새 deny 가 저장소 read · 격리 부모와 겹치는 자리는 make_iso 전에 멈춘다: repo 홈 .claude → --repo(15) · tmp 홈 .claude → TMPDIR(11)
#     자리: home · repo · fz(저장소 .fz-work) · both(홈 · 저장소 .claude 가 같은 대상) × --deny: none · same(대상 폴더를 --deny 로도 준다)
#     ⛔ self 저장소 × same(--deny = --repo)은 넣지 않는다 — .claude 와 무관하게 입력끼리 read · deny 가 부딪는 꼴이다
#     기대 'exit|대상 실경로 deny 줄|저장소 링크 키 줄|홈 deny 줄|같은 키|stdout' — config 가 없으면 '-'
GL="$T/glink"
glink() {
  local form="$1" place="$2" dny="$3" c="$GL/$1-$2-$3"
  local h="$c/home" r="$c/repo" tmp="$c/tmp" tgt="" rl="$c/repo/.claude" links=() args=() out rc cfg tp nt="-" nl="-" nh="-" dup="" so=""
  mkdir -p "$h/.codex" "$r/src" "$tmp"; echo '{}' > "$h/.codex/auth.json"
  case "$place" in home) links=("$h/.claude") ;; repo) links=("$rl") ;; fz) rl="$r/.fz-work"; links=("$rl") ;; both) links=("$h/.claude" "$rl") ;; esac
  case "$form" in
    dir) tgt="${links[0]}" ;;
    out) tgt="$c/out" ;;
    in-home) tgt="$h/claude-data" ;;
    under-repo) tgt="$r/claude-data" ;;
    self) tgt="$h"; [ "$place" = home ] || tgt="$r" ;;
    broken) tgt="$c/missing" ;;
    repo) tgt="$r" ;;
    tmp) tgt="$c/out"; tmp="$tgt" ;;
  esac
  [ "$form" = broken ] || mkdir -p "$tgt"
  [ "$form" = dir ] || for l in "${links[@]}"; do ln -s "$tgt" "$l"; done
  [ "$dny" = same ] && args=(--deny "$tgt")
  out="$(env -u CODEX_HOME HOME="$h" TMPDIR="$tmp" bash "$L" iso --repo "$r" ${args[@]+"${args[@]}"} 2> "$c/err")"; rc=$?
  cfg="$out/gpt-home/config.toml"
  if [ -n "$out" ] && [ -f "$cfg" ]; then
    tp="$(cd "$tgt" 2>/dev/null && pwd -P)" || tp="$tgt"; nt="$(grep -cxF "\"$tp\" = \"deny\"" "$cfg")"   # 없는 대상은 적은 경로 그대로(GL 은 실경로)
    nl="$(grep -cxF "\"$rl\" = \"deny\"" "$cfg")"; nh="$(grep -cxF "\"$h\" = \"deny\"" "$cfg")"
    dup="$(fskeys "$cfg" | sort | uniq -d | tr '\n' ' ')"
  fi
  [ -n "$out" ] && so="bad"; case "$out" in "$tmp"/fz-gpt-iso.??????) [ -f "$cfg" ] && so="iso" ;; esac
  check "claude-link-grid $form@$place/$dny" "$rc|$nt|$nl|$nh|$dup|$so" "$4"
}
#     꼴         자리  --deny 기대
glink dir        home none "0|0|0|1||iso"     # 실폴더 ~/.claude — 홈 deny 가 덮는다(제 줄 없음)
glink dir        home same "0|1|0|1||iso"
glink dir        repo none "0|1|1|1||iso"     # 저장소 실폴더 — 링크 키가 곧 대상 키(한 줄)
glink dir        repo same "0|1|1|1||iso"     # --deny 가 같은 키 — 한 번
glink out        home none "0|1|0|1||iso"
glink out        home same "0|1|0|1||iso"
glink out        repo none "0|1|1|1||iso"
glink out        repo same "0|1|1|1||iso"
glink in-home    home none "0|1|0|1||iso"
glink in-home    home same "0|1|0|1||iso"
glink in-home    repo none "0|1|1|1||iso"
glink in-home    repo same "0|1|1|1||iso"
glink under-repo home none "0|1|0|1||iso"     # 저장소 read 가 홈 deny 보다 구체적이다 — 대상 키가 없으면 열린다
glink under-repo home same "0|1|0|1||iso"
glink under-repo repo none "0|1|1|1||iso"
glink under-repo repo same "0|1|1|1||iso"
glink self       home none "0|1|0|1||iso"     # ~/.claude → ~ — 대상 줄 = 홈 deny 한 줄
glink self       home same "0|1|0|1||iso"     # --deny ~ 도 한 번
glink self       repo none "0|0|1|1||iso"     # .claude → 저장소 — 대상은 저장소 read 다. deny 를 넣으면 값이 다른 같은 키라 넣지 않는다
glink broken     home none "0|0|0|1||iso"     # 없는 대상에는 deny 를 넣지 않는다
glink broken     home same "11|-|-|-||"       # 없는 --deny — 격리 폴더를 만들기 전에 11
glink broken     repo none "0|0|0|1||iso"
glink broken     repo same "11|-|-|-||"
glink out        fz   none "0|1|1|1||iso"     # 저장소 .fz-work 도 같은 규칙
glink out        both none "0|1|1|1||iso"     # 두 자리가 같은 대상 — 키 한 줄
glink out        both same "0|1|1|1||iso"
glink repo       home none "15|-|-|-||"       # 금지 입력 게이트가 먼저다
glink tmp        home none "11|-|-|-||"       # 격리 폴더 자리 게이트가 먼저다
# ⑬f head/ 결손 표시 — 변경 후 파일이 head/ 에 없으면 감사가 빠진 경로를 적는다(F14 · fail-visible)
mkdir -p "$IN/head-empty"
run headmiss "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --base "$IN/base" --head "$IN/head-empty"
check "head 결손: 감사 head — 1 · 0 · src/a.ts" "$(headsum headmiss)" "1 0 src/a.ts"
# ⑬i head 수집 — hunk 안의 `+++ b/phantom.ts` 는 추가 행이다 · 따옴표 8진 경로 · 순수 rename · 바이너리는 센다 · 삭제는 빼다(역검증 ISSUE-002)
printf '%s\n' 'diff --git a/src/a.ts b/src/a.ts' '--- a/src/a.ts' '+++ b/src/a.ts' '@@ -1 +1,2 @@' '-a' '+b' '+++ b/phantom.ts' \
  'diff --git "a/src/\355\225\234.ts" "b/src/\355\225\234.ts"' '--- "a/src/\355\225\234.ts"' '+++ "b/src/\355\225\234.ts"' '@@ -1 +1 @@' '-x' '+y' \
  'diff --git a/old.ts b/new.ts' 'similarity index 100%' 'rename from old.ts' 'rename to new.ts' \
  'diff --git a/img.png b/img.png' 'index 1111111..2222222 100644' 'Binary files a/img.png and b/img.png differ' \
  'diff --git a/gone.ts b/gone.ts' 'deleted file mode 100644' '--- a/gone.ts' '+++ /dev/null' '@@ -1 +0,0 @@' '-z' > "$IN/diff-mixed.patch"
printf 'diff --git a/end sp.ts  b/end sp.ts \n--- a/end sp.ts \t\n+++ b/end sp.ts \t\n@@ -1 +1 @@\n-p\n+q\n' >> "$IN/diff-mixed.patch"   # 끝 공백 경로(git 은 탭 꼬리를 붙인다)
mkdir -p "$IN/head-mixed/src"; echo b > "$IN/head-mixed/src/a.ts"; echo y > "$IN/head-mixed/src/한.ts"; echo n > "$IN/head-mixed/new.ts"; echo q > "$IN/head-mixed/end sp.ts "
run headmix "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff-mixed.patch" --head "$IN/head-mixed"
check "head 수집(혼합 diff · 끝 공백 경로): 감사 head — 기대 5 · 있음 4 · 빠짐 img.png" "$(headsum headmix)" "5 4 img.png"
printf '%s\n' '--- a/src/a.ts' '+++ b/src/a.ts' '@@ -1 +1 @@' '-a' '+b' > "$IN/diff-plain.patch"
run headplain "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff-plain.patch" --head "$IN/head"
check "head 수집(git 헤더 없는 diff): 0 으로 세지 않고 error 로 드러낸다" \
  "$(python3 -c 'import json,sys; h=json.load(open(sys.argv[1]))["head"]; print("error" if h.get("expected") is None and h.get("error") else h)' "$T/c-headplain/out/A-headplain.audit.json" 2>/dev/null || echo -)" "error"
# ⑬g 미러 안 범용 이름은 저장소 파일이다 — base/head 의 payload.json 은 거부하지 않는다 · fz 고유 이름은 거부한다(F6)
mkdir -p "$IN/base-gen" "$IN/head-gen" "$IN/head-fz/T-1/plan"; echo '{}' > "$IN/base-gen/payload.json"; echo '{}' > "$IN/head-gen/payload.json"
echo x > "$IN/head-fz/T-1/plan/plan-final.md"
run mirrorgen "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --base "$IN/base-gen" --head "$IN/head-gen"
check "미러 범용 이름(payload.json): exit 0" "$(rc mirrorgen)" 0
run mirrorfz "" "" review --diff "$IN/diff.patch" --base "$IN/base" --head "$IN/head-fz"
check "미러 fz 고유 이름(plan-final.md): exit 15" "$(rc mirrorfz)" 15
# ⑬h 감사 블록이 예외로 죽으면 exit 11 · 감사는 running 그대로(F2 — 옛 판은 exit 1 · 감사 없음이라 병합이 '런처 밖 입력'으로 받았다)
#     .md 자리에 폴더를 두면 감사 블록의 렌더 쓰기가 IsADirectoryError 로 죽는다(결정적 주입)
mkdir -p "$T/c-auditcrash/out/A-auditcrash.md"
run auditcrash "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
check "감사 블록 예외: exit 11" "$(rc auditcrash)" 11
check "감사 블록 예외: 감사 exit null(running)" "$(audit auditcrash exit)" None
# ⑭ 모델·effort — 런처는 기본값이 없고 주어진 --model · --effort 만 그대로 넘긴다. 안 주면 래퍼가 Lead 세션 선택(실제 홈 선택 폴더) > 격리 config 로 정한다
mkdir -p "$H/.fz/gpt-choice"; printf 'model=m-sel\neffort=low\n' > "$H/.fz/gpt-choice/arm-sel"
CSID=arm-sel run sel "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md"
check "세션 선택(임시 실제 홈 .fz/gpt-choice): exit 0" "$(rc sel)" 0
check "세션 선택: argv 에 선택 모델 · effort(-c 뒤) · 그 둘뿐" "$(argc sel 'model="m-sel"')|$(argc sel 'model_reasoning_effort=low')|$(leak sel)" "1|1|2"
check "세션 선택: 런처 stderr GPT-CHOICE (session)" "$(gline sel)" "GPT-CHOICE model=m-sel (session) effort=low (session)"
# ⑭b 이전 선택(.last) × 선택 폴더 쓰기 불가 — 래퍼의 get 은 세션 파일을 쓰지 못해도 .last 를 내지만 그 모델이 모델 목록 캐시에 있을 때만이다.
#     래퍼는 격리 CODEX_HOME 에서 돈다 — 실제 CLI 홈의 캐시가 격리 홈에 사본으로 있어야 .last 가 이어진다. 실제 CLI 홈에 캐시가 없으면 지금처럼 config 다.
#     셀마다 실제 홈을 따로 둔다(공유 홈 $H 에 .last 를 두면 뒤 셀의 config 가 바뀐다) · 자율 판정(FZ_AUTONOMY)은 셀 안에서 지운다(자율이면 .last 를 보지 않는다)
lastrun() {   # $1=셀 · $2=실제 CLI 홈의 모델 목록 캐시(1 = m-last 를 싣는다 · 0 = 없음) → 실제 홈 $T/home-<셀>(인증 · config m-test · medium · .last m-last · high)
  local h="$T/home-$1"; mkdir -p "$h/.codex" "$h/.fz/gpt-choice"
  cp "$H/.codex/auth.json" "$H/.codex/config.toml" "$h/.codex/"
  [ "$2" = 0 ] || printf '%s\n' '{"models": [{"slug": "m-last", "visibility": "list", "default_reasoning_level": "high", "supported_reasoning_levels": [{"effort": "high"}]}]}' > "$h/.codex/models_cache.json"
  printf 'model=m-last\neffort=high\n' > "$h/.fz/gpt-choice/.last"
  ( HREAL="$(cd "$h" && pwd -P)"; roll "$T/r-$1.jsonl" 1 "cat requirement.md" )   # 감사의 홈 deny 는 그 셀의 실제 홈 기준이다
  chmod 0555 "$h/.fz/gpt-choice"
  ( unset FZ_AUTONOMY; CSID="arm-$1" HOMEX="$h" run "$1" "$HERE/sample-plan-ok.json" "$T/r-$1.jsonl" plan --requirement "$IN/requirement.md" --keep-iso )
  chmod 0755 "$h/.fz/gpt-choice"
}
isocache() {   # $1=격리 폴더 · $2=실제 홈 — 격리 홈의 캐시: copy(링크 아닌 파일 · 내용 같음) · none · link · differ · no-iso(격리 폴더가 없다)
  local f="$1/gpt-home/models_cache.json"
  if [ -z "$1" ] || [ ! -d "$1/gpt-home" ]; then echo no-iso; elif [ -L "$f" ]; then echo link; elif [ ! -e "$f" ]; then echo none; elif cmp -s "$f" "$2/.codex/models_cache.json"; then echo copy; else echo differ; fi
}
lastrun last 1
LISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-last/env.txt")"
check "last-choice-iso-cache — 실제 CLI 홈 캐시에 .last 모델 · 선택 폴더 쓰기 불가 → exit 0 · argv 에 .last 모델 · effort · GPT-CHOICE (session) · 격리 홈 캐시 사본 · 세션 파일 없음" \
  "$(rc last)|$(argc last 'model="m-last"')|$(argc last 'model_reasoning_effort=high')|$(gline last)|$(isocache "$LISO" "$T/home-last")|$(ls "$T/home-last/.fz/gpt-choice")" \
  "0|1|1|GPT-CHOICE model=m-last (session) effort=high (session)|copy|"
[ -n "$LISO" ] && bash "$L" cleanup --iso "$LISO" >/dev/null 2>&1
lastrun lastnc 0
LISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-lastnc/env.txt")"
check "last-choice-iso-nocache — 실제 CLI 홈에 캐시 없음 · .last · 선택 폴더 쓰기 불가 → 지금처럼 config(argv 에 모델 · effort 0 · GPT-CHOICE config) · 격리 홈 캐시 없음" \
  "$(rc lastnc)|$(leak lastnc)|$(gline lastnc)|$(isocache "$LISO" "$T/home-lastnc")" "0|0|GPT-CHOICE model=m-test (config) effort=medium (config)|none"
[ -n "$LISO" ] && bash "$L" cleanup --iso "$LISO" >/dev/null 2>&1
# iso 하위 명령도 같은 make_iso 다 — 캐시가 있는 실제 CLI 홈이면 사본 · 없으면 없음
KISO="$(env -u CODEX_HOME HOME="$T/home-last" bash "$L" iso 2>/dev/null)"; KISO_NC="$(env -u CODEX_HOME HOME="$T/home-lastnc" bash "$L" iso 2>/dev/null)"
check "last-choice-iso-subcommand-cache — iso 하위 명령: 실제 CLI 홈 캐시 → 격리 홈 사본 · 캐시 없음 → 없음" \
  "$(isocache "$KISO" "$T/home-last")|$(isocache "$KISO_NC" "$T/home-lastnc")" "copy|none"
for d in "$KISO" "$KISO_NC"; do [ -n "$d" ] && bash "$L" cleanup --iso "$d" >/dev/null 2>&1; done
run eff "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --effort max
check "--effort 명시 · review: exit 0 · 그대로 전달 · 모델 0" "$(rc eff)|$(argc eff 'model_reasoning_effort=max')|$(leak eff)" "0|1|1"
check "--effort 명시: GPT-CHOICE (config · flag)" "$(gline eff)" "GPT-CHOICE model=m-test (config) effort=max (flag)"
run mdl "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --model m-flag
check "--model 명시 · plan: exit 0 · 그대로 전달 · effort 0" "$(rc mdl)|$(argc mdl 'model="m-flag"')|$(leak mdl)" "0|1|1"
check "--model 명시: GPT-CHOICE (flag · config)" "$(gline mdl)" "GPT-CHOICE model=m-flag (flag) effort=medium (config)"
# 형식 검증은 래퍼 몫 — 런처는 불량 값 · 빈 값도 그대로 넘기고 래퍼 exit 10 을 그대로 낸다(빈 --effort 를 조용히 빼 config 로 돌리지 않는다)
run mbad "" "" plan --requirement "$IN/requirement.md" --model -x
run ebad "" "" review --diff "$IN/diff.patch" --effort ''
for c in mbad ebad; do
  flg=--model; [ "$c" = ebad ] && flg=--effort
  check "플래그 불량($c): exit 10 · CLI 미호출" "$(rc $c)|$(called $c)" "10|0"
  check "플래그 불량($c): 런처 stderr 에 GPT-CHOICE 줄 없음(래퍼가 그 줄 전에 멈춘다)" "$(gcount $c)" 0
  # ⛔ 위 두 셀은 런처가 스스로 die 10 해도 같다(⑪ 사용법 셀과 구별되지 않는다) — 거부한 쪽이 래퍼인지 따로 본다
  check "플래그 불량($c): 거부한 쪽은 래퍼(감사 wrapperExit 10 · 래퍼 로그에 $flg 거부 줄 1 · 런처 INDEPENDENT-FAIL 0)" \
    "$(audit $c wrapperExit)|$(wfail $c "$flg")|$(lfail $c)" "10|1|0"
done

echo
[ "$fail" -eq 0 ] && echo "independent-arm: 전건 통과" || echo "independent-arm: 실패 있음"
exit "$fail"
