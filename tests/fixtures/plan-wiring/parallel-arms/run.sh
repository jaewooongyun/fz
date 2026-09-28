#!/bin/bash
# fz-plan 배선 러너 (S23) — `--gpt-independent` 경로의 순서 · Phase 2 resume 교차 · 기본 verify 불변을 본다.
#
# ① 순서 — 독립 플랜 기동(gpt_independent.sh plan) < Workflow 호출 < 합치기(plan_divergence.py)
# ② Phase 2 절에 resume 교차(resume --session-file)와 병렬 계약 네 토큰이 있다(check_wf_text --section-has)
# ③ 기본 verify 불변 — core 모듈 § verify 의 bash 블록을 고정 입력 · 가짜 CLI 로 **실제로 돌려** CLI 인자(프롬프트 포함)를
#    verify-default.golden.json 과 바이트 단위로 대조한다. golden 은 S23 직전 모듈에서 `--capture` 로 잡았다
#    (`bash run.sh --capture <(git show <S23 직전>:modules/fz-gpt-subcommands-core.md)`). fz-discover --deep 도 같은 verify 를 쓴다.
# ⛔ 실제 GPT CLI · 사용자 홈을 건드리지 않는다 — PATH 앞에 tests/fixtures/gpt/_shim · HOME 은 임시 폴더.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
T="$(cd "$(mktemp -d)" && pwd -P)"; trap 'rm -rf "$T"' EXIT

capture() {   # $1 = core 모듈 파일 → stdout 에 정규화한 CLI 인자 JSON(실패면 빈 출력 · exit 1)
  local src="$1" w="$T/cap"; rm -rf "$w"; mkdir -p "$w/repo" "$w/home" "$w/tel"
  git -C "$w/repo" init -q 2>/dev/null
  printf '# fz-architect — 고정 본문(러너 전용)\n' > "$w/skill.md"
  { echo 'get_gpt_skill_path() { echo "$STUB_SKILL"; }'
    echo 'P_VERIFY="$W/p_verify.txt"; PLAN_CONTENT="PLAN-FIXED"; AFFECTED_SYMBOLS="SYM-FIXED"; REVIEW_FILE="$W/review.json"'
    python3 - "$src" <<'PY'
import sys
s = open(sys.argv[1], encoding="utf-8").read()
i = s.index("## verify -- 계획 검증")
j = s.index("```bash\n", i) + len("```bash\n")
print(s[j:s.index("\n```", j)])
PY
  } > "$w/verify.sh" || return 1
  local ok_json='{"schemaVersion":"1.1","review_id":"fixture","timestamp":"2026-09-29T00:00:00Z","review_type":"plan_validation","issues":[],"summary":{"total_issues":0,"by_severity":{"critical":0,"major":0,"minor":0,"suggestion":0},"by_category":""},"verdict":"approved","overall_feedback":"ok","strengths":[]}'
  env -u CODEX_HOME HOME="$w/home" PATH="$R/tests/fixtures/gpt/_shim:$PATH" W="$w" STUB_SKILL="$w/skill.md" FZ_PLUGIN_ROOT="$R" GIT_ROOT="$w/repo" \
    FZ_SHIM_CAPTURE="$w/argv.json" FZ_SHIM_OUTPUT="$ok_json" FZ_TELEMETRY_DIR="$w/tel" bash "$w/verify.sh" > "$w/log" 2>&1 || { cat "$w/log" >&2; return 1; }
  python3 - "$w/argv.json" "$w" "$R" <<'PY'
import json, sys
argv, w, r = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], sys.argv[3]
print(json.dumps([a.replace(w, "<W>").replace(r, "<R>") for a in argv], ensure_ascii=False, indent=1))
PY
}

if [ "${1:-}" = "--capture" ]; then capture "$2"; exit $?; fi

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
first() { /usr/bin/grep -nF -- "$2" "$R/$1" 2>/dev/null | head -1 | cut -d: -f1; }
P=skills/fz-plan/SKILL.md

# ① 순서
a="$(first "$P" 'gpt_independent.sh plan')"; b="$(first "$P" "Workflow({ scriptPath: '{2.5에서 정한 경로}'")"; c="$(first "$P" 'plan_divergence.py')"
if [ -n "$a" ] && [ -n "$b" ] && [ -n "$c" ] && [ "$a" -lt "$b" ] && [ "$b" -lt "$c" ]; then
  ok "$P: 독립 플랜 기동($a) < Workflow($b) < 합치기($c)"
else
  no "$P: 순서가 틀렸거나 토큰이 없다 — 기동 '${a:-없음}' · Workflow '${b:-없음}' · 합치기 '${c:-없음}'"
fi

# ② Phase 2 — resume 교차 + 병렬 계약
node "$R/scripts/check_wf_text.js" --section-has 'Phase 2: Plan Validation' 'resume --session-file' '불변 입력' '별도 출력' '양쪽 완료' 'schema' "$R/$P" > /dev/null 2>&1 \
  && ok "$P: Phase 2 에 resume 교차 · 병렬 계약 네 토큰" || no "$P: Phase 2 절에 resume 교차 또는 병렬 계약 토큰이 없다"

# ③ 기본 verify 불변 — 가짜 CLI 로 잡은 인자가 golden 과 같다
got="$(capture "$R/modules/fz-gpt-subcommands-core.md")"
if [ -z "$got" ]; then
  no "기본 verify: 가짜 CLI 로 돌리지 못했다(블록 추출 · 래퍼 실행 실패)"
elif [ "$got" = "$(cat "$HERE/verify-default.golden.json")" ]; then
  ok "기본 verify: CLI 인자(프롬프트 포함)가 golden 과 바이트 단위로 같다"
else
  no "기본 verify: CLI 인자가 golden 과 다르다 — $(diff <(printf '%s\n' "$got") "$HERE/verify-default.golden.json" | head -4 | tr '\n' ' ')"
fi

echo
[ "$fail" = 0 ] && echo "plan-wiring parallel-arms: 전건 통과" || echo "plan-wiring parallel-arms: 실패"
exit "$fail"
