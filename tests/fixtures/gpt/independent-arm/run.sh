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
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "mktemp 실패" >&2; exit 2; }; T="$(cd "$T0" && pwd -P)"; trap 'rm -rf "$T"' EXIT

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
roll "$T/r-roles.jsonl" 1 "SPAWN:fz-review-arch" "SPAWN:fz-review-quality" "cat diff.patch"
roll "$T/r-repo.jsonl" 1 "rg --files $HREAL/dev/repo -g '!.git'" "find $HREAL/dev/repo -name '*.ts'" "grep -rn b $HREAL/dev/repo"
roll "$T/r-repomix.jsonl" 1 "rg b $HREAL/dev/repo ~"
roll "$T/r-quoted.jsonl" 1 'cat "work dir/review-report.md"'
roll "$T/r-pattern.jsonl" 1 "rg -n 'review-report\\.md' scripts"

run() {    # $1=셀 · $2=shim 출력 파일(없으면 빈 값) · $3=rollout 목록(쉼표) · 나머지=런처 인자
  local name="$1" outf="$2" rolls="$3"; shift 3
  local d="$T/c-$name"; mkdir -p "$d/out"
  local body="ok"; [ -n "$outf" ] && body="$(cat "$outf")"
  local start; start=$(date +%s)
  env -u CODEX_HOME HOME="$H" FZ_TELEMETRY_DIR="$d/tel" FZ_SHIM_CAPTURE="$d/argv.json" FZ_SHIM_ENV_CAPTURE="$d/env.txt" \
    FZ_SHIM_OUTPUT="$body" FZ_SHIM_ROLLOUT="$rolls" ${SLEEP:+FZ_SHIM_SLEEP="$SLEEP"} ${IGNORE_TERM:+FZ_SHIM_IGNORE_TERM=1} ${TMPX:+TMPDIR="$TMPX"} \
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
POS = ['cat "work dir/review-report.md"', 'cat "plan/plan-final.md"', 'cat work/code-context".md"', 'cat "T-1/plan/workflow-result.json"',
       "cat work/review-report.md\nwc -l requirement.md"]
NEG = ["rg -n 'review-report\\.md' scripts", "cat src/review-report.md,backup", "cat src/code-context.md:backup",
       'rg -n "workflow-result" scripts', 'cat "Sources/Foo/code-context-builder.swift"']
scases = [(f(c), True) for c in POS for f in (roll, fc, js)] + [(f(c), False) for c in NEG for f in (roll, fc, js)]
scases += [(js("pwd", 'cat "T-1/review/triage.md"'), True), (arr("Domain/A.swift", "T-1/plan/plan-v2.md"), True),
           ("const paths = ['T-1/review/self-review.md'];", True), ('{"cmd":"cat ~\\/.claude\\/projects\\/p\\/a.jsonl"}', True),
           (arr("Domain/A.swift", "Sources/code-context-builder.swift"), False)]
out += ["ok" if forbid and forbid(c) == w else f"sbad{i}" for i, (c, w) in enumerate(scases)]
print(f"ALL-OK n={len(out)}" if all(x == "ok" for x in out) else " ".join(out))
UPY
)"
check "감사 규칙(/Users 저장소 안 검색은 예외 · 홈 · 루트 · 저장소 밖 · 따옴표 패턴 뒤 뿌리 · \`..\` 은 적중 · 산출물 이름은 경로 성분 단위 · 직렬화 따옴표를 걷는다)" "$UNIT" "ALL-OK n=51"

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
# ⑦b 정상 run 뒤 감시자의 sleep 이 남지 않는다 — 옛 판은 run 마다 `sleep $TIMEOUT` 을 고아로 남겼다(리뷰 F5)
run watchok "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --timeout 1797
check "감시자 정리: exit 0" "$(rc watchok)" 0
sleep 1; pgrep -f 'sleep 1797' >/dev/null && no "감시자 정리: sleep 1797 이 고아로 남았다" || ok "감시자 정리: 고아 sleep 없음"
pkill -f 'sleep 1797' 2>/dev/null   # 옛 판을 잴 때 남는 고아를 치운다
# ⑦c TERM 을 무시하는 자손 — 시간 초과면 KILL 까지 간다. 옛 판은 TERM 에 래퍼가 죽자 감시자를 먼저 죽여 자손이 남았다(리뷰 F5 · G2)
IGNORE_TERM=1 SLEEP=29.6 run hangterm "$HERE/sample-plan-ok.json" "$T/r-ok.jsonl" plan --requirement "$IN/requirement.md" --timeout 2
check "TERM 무시 자손: exit 16" "$(rc hangterm)" 16
sleep 1; pgrep -f 'sleep 29.6' >/dev/null && no "TERM 무시 자손: KILL 되지 않고 남았다" || ok "TERM 무시 자손: KILL 로 정리"
pkill -KILL -f 'sleep 29.6' 2>/dev/null

# ⑧ planner 거부 → exit 17
printf '%s' '{"status":"rejected","reason":"claude_plan_detected","approach":"-","affectedFiles":{"new":0,"modified":0},"steps":[],"riskMatrix":[],"stressTest":[],"implicationRegister":[],"divergencePoints":[],"projectRules":{"axes":{"architecturePattern":null,"uiStack":null,"dependencyDirection":null,"naming":null,"placement":null,"conventions":null},"rules":[],"conflicts":[],"gaps":[]}}' > "$T/rejected.json"
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

# ⑪-a 역할 파일(--gpt-agents · S14) — 켜면 격리 홈에 역할 사본 · 두 역할 spawn 지시 · 감사에 역할 이름 / 끄면 agents 없음 · 하위 에이전트 금지
run roleson "$HERE/sample-review-ok.json" "$T/r-roles.jsonl" review --diff "$IN/diff.patch" --gpt-agents --keep-iso
check "역할 켬: exit 0" "$(rc roleson)" 0
AISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-roleson/env.txt")"
[ -f "$AISO/gpt-home/agents/fz-review-arch.toml" ] && [ -f "$AISO/gpt-home/agents/fz-review-quality.toml" ] && [ ! -L "$AISO/gpt-home/agents/fz-review-arch.toml" ] \
  && ok "역할 켬: 격리 홈 agents/ 에 역할 사본 2" || no "역할 켬: 역할 사본이 없다"
check "역할 켬: 두 역할 spawn 지시" "$(count roleson 'agent_type `fz-review-arch`')" 1
check "역할 켬: 감사에 spawn 역할" "$(audit roleson spawnedRoles)" "['fz-review-arch', 'fz-review-quality']"
rm -rf "$AISO"
run rolesoff "$HERE/sample-review-ok.json" "$T/r-ok.jsonl" review --diff "$IN/diff.patch" --keep-iso
OISO="$(sed -n 's/^CODEX_HOME=\(.*\)\/gpt-home$/\1/p' "$T/c-rolesoff/env.txt")"
[ ! -e "$OISO/gpt-home/agents" ] && ok "역할 끔: agents 폴더 없음" || no "역할 끔: agents 폴더가 있다"
check "역할 끔: 하위 에이전트 금지" "$(count rolesoff '하위 에이전트를 만들지 않는다.')" 1
check "역할 끔: 감사 spawn 0" "$(audit rolesoff spawnAgent)" 0
rm -rf "$OISO"
run rolesplan "" "" plan --requirement "$IN/requirement.md" --gpt-agents
check "역할 plan: exit 10(review 전용)" "$(rc rolesplan)" 10

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

echo
[ "$fail" -eq 0 ] && echo "independent-arm: 전건 통과" || echo "independent-arm: 실패 있음"
exit "$fail"
