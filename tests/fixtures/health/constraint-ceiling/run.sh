#!/bin/bash
# 제약 부하 상한 판정 (F-139) — floor 를 잰 뒤 6주 만에 +19~89% 자랐는데 측정만 하는 도구라 아무 게이트도 울리지 않았다.
#
# measure_constraint_load.py --ceiling 이 스킬 floor · agents 본문 · 워크플로 직접 프롬프트를 동결값과 대조한다.
# 트리 사본에서 지금 값을 동결하고, 범위마다 하나씩 부풀려 그 범위가 FAIL 하는지 본다.
# 셀:
#   f139-load-within-ceiling-ok     바꾸지 않은 사본 → exit 0 (짝 — 늘 FAIL 하면 아래 셀이 헛돈다)
#   f139-load-over-ceiling-fails    스킬이 무조건 읽는 모듈을 20% 부풀림 → exit 1 · FAIL skills_floor/<스킬>
#   f139-agents-scope-measured      agents/<첫 파일>.md 를 20% 부풀림 → FAIL agents/<이름>
#   f139-workflow-prompt-measured   workflows/<첫 파일>.js 에 긴 문자열 리터럴 → FAIL workflows/<이름>
#   f139-new-agent-unfrozen-fails   동결값에 없는 agent 파일 → FAIL '동결값에 없는 항목'
#   f139-real-tree-within-ceiling   실제 트리 × tests/fixtures/constraint-ceiling.json → exit 0
# exit: 0 전건 통과 · 1 단언 실패 · 3 준비 실패
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="$(cd "$HERE/../../../.." && pwd)"
MCL="$TREE/scripts/measure_constraint_load.py"
CEIL="$TREE/tests/fixtures/constraint-ceiling.json"
[ -f "$MCL" ] && [ -f "$CEIL" ] || { echo "SETUP 측정기 또는 동결 파일 없음"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 부재"; exit 3; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/fz-ceiling.XXXXXX")" || { echo "SETUP 임시 폴더 실패"; exit 3; }
trap 'rm -rf "$TMP"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=$((fail + 1)); }

mk() {   # $1=사본 폴더 — 측정에 쓰는 폴더만 복사하고 지금 값으로 동결한다
  mkdir -p "$1/scripts" || return 1
  for d in skills modules guides agents workflows; do cp -R "$TREE/$d" "$1/$d" || return 1; done
  cp "$MCL" "$1/scripts/" && python3 "$1/scripts/measure_constraint_load.py" --freeze "$1/ceil.json" >/dev/null
}
check() { python3 "$1/scripts/measure_constraint_load.py" --ceiling "$1/ceil.json" 2>&1; }

mk "$TMP/a" || { echo "SETUP 사본 준비 실패"; exit 3; }
out="$(check "$TMP/a")"; rc=$?
[ "$rc" -eq 0 ] && ok "f139-load-within-ceiling-ok" || no "f139-load-within-ceiling-ok — exit $rc · $(printf '%s' "$out" | tail -1)"

# 스킬 floor — 무조건 로드 참조가 있는 첫 스킬의 그 모듈을 floor 의 20% 만큼 부풀린다
SK="$(python3 - "$TMP/a" <<'PY'
import json, subprocess, sys
root = sys.argv[1]
d = json.loads(subprocess.run([sys.executable, f"{root}/scripts/measure_constraint_load.py", "--json"], capture_output=True, text=True).stdout)
for name, s in sorted(d["skills"].items()):
    refs = [r for r, m in s["refs_detail"].items() if m["bucket"] == "load" and not m["conditional"] and r in d["docs"]]
    if s["uncond_tokens"] and refs:
        with open(f"{root}/{refs[0]}", "a", encoding="utf-8") as fh:
            fh.write("\n" + "가" * (s["uncond_tokens"] * 4 // 5) + "\n")
        print(name)
        break
PY
)"
out="$(check "$TMP/a")"; rc=$?
if [ -n "$SK" ] && [ "$rc" -eq 1 ] && printf '%s\n' "$out" | grep -q "^FAIL skills_floor/$SK:"; then ok "f139-load-over-ceiling-fails"
else no "f139-load-over-ceiling-fails — 스킬 '${SK}' · exit $rc · $(printf '%s' "$out" | tail -1)"; fi

mk "$TMP/b" || { echo "SETUP 사본 준비 실패"; exit 3; }
AG="$(ls "$TMP/b/agents" | head -1)"; AG="${AG%.md}"
python3 -c 'import sys; p=sys.argv[1]; t=open(p,encoding="utf-8").read(); open(p,"a",encoding="utf-8").write("\n"+"x"*(len(t)//5+40)+"\n")' "$TMP/b/agents/$AG.md"
out="$(check "$TMP/b")"; rc=$?
if [ "$rc" -eq 1 ] && printf '%s\n' "$out" | grep -q "^FAIL agents/$AG:"; then ok "f139-agents-scope-measured"
else no "f139-agents-scope-measured — '$AG' · exit $rc · $(printf '%s' "$out" | tail -1)"; fi

mk "$TMP/c" || { echo "SETUP 사본 준비 실패"; exit 3; }
WF="$(ls "$TMP/c/workflows" | head -1)"; WF="${WF%.js}"
python3 -c 'import sys; p=sys.argv[1]; t=open(p,encoding="utf-8").read(); open(p,"a",encoding="utf-8").write("\nconst EXTRA = `"+"y"*(len(t)//3)+"`\n")' "$TMP/c/workflows/$WF.js"
out="$(check "$TMP/c")"; rc=$?
if [ "$rc" -eq 1 ] && printf '%s\n' "$out" | grep -q "^FAIL workflows/$WF:"; then ok "f139-workflow-prompt-measured"
else no "f139-workflow-prompt-measured — '$WF' · exit $rc · $(printf '%s' "$out" | tail -1)"; fi

printf '# new agent\n' > "$TMP/c/agents/zz-new-agent.md"
out="$(check "$TMP/c")"; rc=$?
if [ "$rc" -eq 1 ] && printf '%s\n' "$out" | grep -q '^FAIL agents/zz-new-agent: 동결값에 없는 항목'; then ok "f139-new-agent-unfrozen-fails"
else no "f139-new-agent-unfrozen-fails — exit $rc · $(printf '%s' "$out" | tail -1)"; fi

out="$(python3 "$MCL" --ceiling "$CEIL" 2>&1)"; rc=$?
[ "$rc" -eq 0 ] && ok "f139-real-tree-within-ceiling" || no "f139-real-tree-within-ceiling — exit $rc · $(printf '%s\n' "$out" | grep '^FAIL' | head -3 | tr '\n' '|')"

echo "$fail 건 실패"
[ "$fail" -eq 0 ] || exit 1
echo "CONSTRAINT_CEILING_OK"
