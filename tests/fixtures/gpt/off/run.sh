#!/bin/bash
# GPT 미사용(off) 폴백 러너 — 정본 modules/gpt-strategy.md § GPT 미사용 의 계약을 세 입구(정문 gpt-call.sh · 래퍼 gpt-exec.sh ·
#   런처 gpt_independent.sh)와 소비자(review_merge.py --gpt-unavailable)에서 잰다. 사용자가 GPT 를 끄거나 CLI 가 없을 때 흐름이
#   끊기지 않고(정해진 exit 18 · stderr 'GPT-OFF: <사유>') GPT 가 조용히 다시 켜지지 않는지(CLI 호출 0)를 본다.
#
# 재는 것
#   (a) 세션 선택 off              → 세 입구 + 정문 경유 런처 모두 exit 18 · 'GPT-OFF: 사용자 선택' · CLI 호출 0
#   (b) off 저장 실패 + 플래그 --model off — 선택 폴더에 쓸 수 없어 `set --model off` 가 11 인 세션(전제를 먼저 잰다)에서
#       호출마다 --model off 를 붙이면 선택 파일을 읽지 않고 18 · 'GPT-OFF: 플래그' · CLI 호출 0.
#       양성 대조: 같은 환경에서 플래그를 빼면 CLI 가 1회 불린다(기록 CLI 가 살아 있다 — 호출 0 이 공허하지 않다)
#   (c) 모델 목록 캐시 손상 + off   → options 가 degraded 로 off 를 내고 · set --model off 가 캐시 없이 0 · 세 입구 18 · CLI 호출 0
#   (d) GPT CLI 없음(실행 파일 codex 가 든 폴더를 PATH 에서 뺀다 · GPT 홈도 없다) → get 이 묻지 않고 off(0) · 세 입구 18 'GPT-OFF: CLI 없음'
#       — 런처는 GPT 홈 · 인증 게이트(11)보다 먼저 18 이다
#   런처 감사: <stem>.audit.json 의 exit 18 · gptOff · .contaminated 없음 · 격리 폴더 미생성. 병합: --gpt-unavailable 은 0, 그 감사를 --gpt 로
#       넘기면 거부(1). 정문 호출 행(gpt-calls.tsv) exit 열 18
#   비대화: FZ_AUTONOMY 미설정 + CLI 있음 + 선택 없음 — 스크립트는 질문 도구 유무를 알 수 없다(get 은 3 · 아무것도 쓰지 않는다).
#       Lead 규칙(질문 도구를 쓸 수 없으면 exit 4 처럼 config — modules/mode-gate.md § 언제 묻나 4)은 문서 토큰으로 보고,
#       스크립트 쪽 질문 0회는 래퍼가 닫힌 stdin 에서 묻지 않고 config 로 도는 것(0 · CLI 1회)과 FZ_AUTONOMY=autonomous → get 4 로 본다
#
# ⛔ 실제 GPT CLI · 사용자 홈 · 사용자 선택을 건드리지 않는다 — PATH 에서 실제 CLI 폴더를 빼고, 기록 CLI(가짜 — ../_shim/codex 로 위임)를
#    셀이 고른다. HOME · CODEX_HOME · FZ_GPT_CHOICE_DIR · FZ_TELEMETRY_DIR · TMPDIR 는 셀마다 임시이고 FZ_AUTONOMY 는 셀마다 명시한다.
# ⛔ 음성 대조(판별력): FZ_GPT_OFF_TREE_UNDER_TEST=<트리 루트> 로 다른 트리의 scripts/ 를 같은 러너로 돈다. 기준 트리(26c42d3 —
#    GPT 미사용 경로 없음)에서는 FAIL 이어야 한다:
#      D="$(mktemp -d)"; git -C <플러그인 저장소> archive 26c42d3 | tar -x -C "$D"; FZ_GPT_OFF_TREE_UNDER_TEST="$D" bash tests/fixtures/gpt/off/run.sh
#    (정문은 자기 폴더의 resolver · 레지스트리를, 런처는 자기 트리의 gpt-skills 를 읽으므로 scripts 폴더가 아니라 트리 루트를 넘긴다)
#    기준 트리로도 통과하는 셀(판별 셀 아님 — 기존 동작이 이미 맞다): 병합 세 셀 · (b) 양성 대조 · 비대화 세 셀 · (a) 격리 폴더 미잔존
#    (기준 런처도 끝나면 격리 폴더를 지운다). 나머지는 기준 트리에서 FAIL 이다(2026-10-19 실측 45 FAIL · 8 PASS · exit 1)
# exit: 0=전건 통과 · 1=실패 있음 · 2=UNRUN(준비 실패 — PASS 아님)
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
U="${FZ_GPT_OFF_TREE_UNDER_TEST:-$R}"
[ -f "$U/scripts/gpt-exec.sh" ] && [ -f "$U/scripts/gpt-call.sh" ] && [ -f "$U/scripts/gpt_independent.sh" ] \
  || { echo "UNRUN  대상 트리에 세 입구가 없다: $U/scripts"; exit 2; }
T0="$(mktemp -d)" || { echo "UNRUN  mktemp 실패"; exit 2; }
T="$(cd "$T0" && pwd -P)"
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 — 기대 '$3' · 실제 '$2'"; fi; }

# ── PATH — 실제 CLI 가 든 폴더를 뺀다(python3 · perl 은 남아야 한다). 'CLI 있음' 은 그 앞에 기록 CLI 폴더를 붙인다
nocli_path() { local d out="" IFS=:; for d in $PATH; do [ -n "$d" ] && [ -x "$d/codex" ] && continue; out="${out:+$out:}$d"; done; printf '%s' "$out"; }
NOCLI="$(nocli_path)"
[ -z "$(PATH="$NOCLI"; command -v codex)" ] || { echo "UNRUN  setup — CLI 없는 PATH 를 만들지 못했다"; exit 2; }
[ -n "$(PATH="$NOCLI"; command -v python3)" ] && [ -n "$(PATH="$NOCLI"; command -v perl)" ] \
  || { echo "UNRUN  setup — CLI 없는 PATH 에 python3 · perl 이 없다(같은 폴더)"; exit 2; }
mkdir -p "$T/fakebin"
# 기록 CLI — 불릴 때마다 한 줄을 남기고 표준 가짜 CLI 로 넘긴다(--version 도 센다 — off 면 그것도 불리면 안 된다)
cat > "$T/fakebin/codex" <<EOF
#!/bin/bash
printf '%s\n' "\$*" >> "\${FZ_OFF_CALLS:-$T/calls-unscoped.log}"
exec /bin/bash "$R/tests/fixtures/gpt/_shim/codex" "\$@"
EOF
chmod +x "$T/fakebin/codex"
CLIPATH="$T/fakebin:$NOCLI"
[ "$(PATH="$CLIPATH"; command -v codex)" = "$T/fakebin/codex" ] || { echo "UNRUN  setup — 기록 CLI 가 PATH 앞에 오지 않는다"; exit 2; }

# ── 입력 — 작업 저장소 · 프롬프트 · diff · 가짜 "실제 홈"(GPT 홈 + 인증 — (d) 는 GPT 홈 없는 홈)
mkdir -p "$T/repo" "$T/home/.codex" "$T/home-bare" "$T/sel" "$T/o"
git -C "$T/repo" init -q 2>/dev/null; echo a > "$T/repo/a.txt"
printf '과제 OFF-TASK-1\n' > "$T/task.txt"
printf 'diff --git a/src/a.swift b/src/a.swift\n--- a/src/a.swift\n+++ b/src/a.swift\n@@ -10,2 +10,3 @@\n let service = APIClient.shared\n-let x = 1\n+let x = 2\n+func load() { service.fetch() }\n' > "$T/diff.patch"
echo '{"fake":"auth"}' > "$T/home/.codex/auth.json"
printf 'model = "fake-cfg"\nmodel_reasoning_effort = "low"\n' > "$T/home/.codex/config.toml"
mkdir -p "$T/ch-bad"; echo 'not json {' > "$T/ch-bad/models_cache.json"; cp "$T/home/.codex/auth.json" "$T/home/.codex/config.toml" "$T/ch-bad/"
# 쓸 수 없는 선택 폴더 — 부모를 읽기 전용으로 둔다(mkdir -p 가 실패한다)
mkdir -p "$T/ro"; chmod 0555 "$T/ro"

# ── 셀 — 세 입구를 같은 env 로 돈다. env 는 셀 앞에서 정하고(아래 변수) 셀은 그것만 쓴다
#    C_PATH · C_HOME · C_CH(CODEX_HOME — '-' 면 unset) · C_SEL(FZ_GPT_CHOICE_DIR) · C_SID · C_AUTO('-' 면 unset)
run_in() {   # $1=셀 이름 · 나머지=명령 — stdout/stderr/rc/calls 를 $T/c-<셀>/ 에
  local name="$1" d e
  shift
  d="$T/c-$name"; mkdir -p "$d" "$d/tmp" "$d/tel"
  e=(env -u FZ_AUTONOMY -u CLAUDE_CODE_SESSION_ID -u CODEX_HOME -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL -u FZ_GPT_POLICY_ROOT
     -u FZ_GPT_IDLE_SEC "PATH=$C_PATH" "HOME=$C_HOME" "FZ_GPT_CHOICE_DIR=$C_SEL" "FZ_TELEMETRY_DIR=$d/tel" "TMPDIR=$d/tmp"
     "FZ_OFF_CALLS=$d/calls.log")
  [ "$C_CH" = "-" ] || e+=("CODEX_HOME=$C_CH")
  [ "$C_SID" = "-" ] || e+=("CLAUDE_CODE_SESSION_ID=$C_SID")
  [ "$C_AUTO" = "-" ] || e+=("FZ_AUTONOMY=$C_AUTO")
  ( cd "$T/repo" && "${e[@]}" "$@" < /dev/null ) > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"
}
rc()    { cat "$T/c-$1/rc" 2>/dev/null || echo "?"; }
calls() { if [ -f "$T/c-$1/calls.log" ]; then wc -l < "$T/c-$1/calls.log" | tr -d ' '; else echo 0; fi; }   # CLI 가 불린 횟수
offl()  { grep -m1 '^GPT-OFF: ' "$T/c-$1/stderr" 2>/dev/null | sed 's/ — .*//'; }                         # 'GPT-OFF: <사유>'
out()   { cat "$T/c-$1/stdout" 2>/dev/null; }
wrap()  { run_in "$1" /bin/bash "$U/scripts/gpt-exec.sh" exec --cd "$T/repo" --out "$T/o/$1.txt" --prompt-file "$T/task.txt" "${@:2}"; }
gate()  { run_in "$1" /bin/bash "$U/scripts/gpt-call.sh" verify --cd "$T/repo" --out "$T/o/$1.json" --prompt-file "$T/task.txt" "${@:2}"; }
lnch()  { run_in "$1" /bin/bash "$U/scripts/gpt_independent.sh" review --diff "$T/diff.patch" --arm gpt --run-id "$1" --out-dir "$T/o/$1" "${@:2}"; }
glnch() { run_in "$1" /bin/bash "$U/scripts/gpt-call.sh" independent-review --diff "$T/diff.patch" --arm gpt --run-id "$1" --out-dir "$T/o/$1" "${@:2}"; }
choice() { run_in "$1" /bin/bash "$U/scripts/gpt-choice.sh" "${@:2}"; }
four() {   # $1=접두 · $2=기대 사유 · 나머지=입구 추가 인자 — 세 입구 + 정문 경유 런처
  local p="$1" why="$2" c
  shift 2
  wrap "$p-wrap" "$@"; gate "$p-gate" "$@"; lnch "$p-lnch" "$@"; glnch "$p-glnch" "$@"
  for c in wrap gate lnch glnch; do
    check "$p $c: exit 18 · CLI 호출 0" "$(rc "$p-$c")|$(calls "$p-$c")" "18|0"
    check "$p $c: stderr 'GPT-OFF: $why'" "$(offl "$p-$c")" "GPT-OFF: $why"
  done
}
reset_env() { C_PATH="$CLIPATH" C_HOME="$T/home" C_CH="$T/home/.codex" C_SEL="$T/sel" C_SID="-" C_AUTO="-"; }

# ── (a) 세션 선택 off — Lead 가 options 의 off 를 골라 set 한 세션
reset_env; C_SID="sid-a"
choice a-set set --model off
check "(a) set --model off → 0" "$(rc a-set)|$(out a-set)" "0|model=off effort=off"
four a "사용자 선택"
# 런처 감사 — exit 18 · gptOff · 오염 · 격리 폴더 없음
A="$T/o/a-lnch/gpt-a-lnch"
check "(a) 런처 감사: exit 18 · gptOff '사용자 선택'" "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("exit"), d.get("gptOff"))' "$A.audit.json" 2>/dev/null)" "18 사용자 선택"
check "(a) 런처: .contaminated 없음 · 결과 JSON 없음" "$([ -e "$A.contaminated" ] && echo 1 || echo 0)|$([ -e "$A.json" ] && echo 1 || echo 0)" "0|0"
check "(a) 런처: 격리 폴더(fz-gpt-iso.*)를 만들지 않았다" "$(find "$T/c-a-lnch/tmp" -maxdepth 1 -name 'fz-gpt-iso.*' 2>/dev/null | wc -l | tr -d ' ')" 0
check "(a) 정문: 호출 행 exit 열 18(행 = 호출 1:1)" "$(awk -F'\t' '{print $12}' "$T/c-a-gate/tel/gpt-calls.tsv" 2>/dev/null | tr '\n' ' ')" "18 "

# ── 병합 — GPT 미사용은 --gpt-unavailable 로 부른다. off 감사를 --gpt 로 넘기면 거부한다
printf '{"issues": [{"id": "A1", "severity": "major", "file": "src/a.swift", "line_range": "10-12", "discoveryAxis": "structure", "title": "t", "evidence": "`APIClient.shared`", "confidence": 90}]}\n' > "$T/claude.json"
reset_env
run_in merge-off python3 "$U/scripts/review_merge.py" --claude "$T/claude.json" --gpt-unavailable "GPT 미사용 — 사용자 선택" --diff "$T/diff.patch"
check "병합 --gpt-unavailable 'GPT 미사용 — 사용자 선택' → 0" "$(rc merge-off)" 0
check "병합 결과: inputs.gptUnavailable 에 사유" "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["inputs"]["gptUnavailable"])' "$T/c-merge-off/stdout" 2>/dev/null)" "GPT 미사용 — 사용자 선택"
run_in merge-gpt python3 "$U/scripts/review_merge.py" --claude "$T/claude.json" --gpt "$A.json" --diff "$T/diff.patch"
check "병합 --gpt <off 감사 stem> → 거부 1(소비자는 --gpt-unavailable 을 쓴다)" "$(rc merge-gpt)" 1

# ── (b) off 저장 실패 → 호출마다 --model off. 전제: 선택 폴더에 쓸 수 없어 set --model off 가 11
reset_env; C_SID="sid-b"; C_SEL="$T/ro/sel"
choice b-set set --model off
check "(b) 전제: 쓸 수 없는 선택 폴더 → set --model off 11 · --model off 우회 안내" "$(rc b-set)|$(grep -c -- '--model off' "$T/c-b-set/stderr" 2>/dev/null)" "11|1"
four b "플래그" --model off
# 양성 대조 — 같은 환경에서 플래그가 없으면 선택이 없어(get 3) config 로 GPT 가 돈다. 기록 CLI 가 살아 있다는 증거
wrap b-ctl
check "(b) 양성 대조: 플래그 없으면 래퍼가 CLI 를 부른다(호출 1 · exit 0)" "$(rc b-ctl)|$(calls b-ctl)" "0|1"
# 손상 선택 파일이 있어도 플래그 off 는 선택을 읽지 않는다(11 이 off 를 가리지 않는다)
mkdir -p "$T/sel-bad"; printf 'effort=high\nmodel=x\n' > "$T/sel-bad/sid-b2"
reset_env; C_SID="sid-b2"; C_SEL="$T/sel-bad"
wrap b-badsel --model off
check "(b) 손상 선택 파일 + --model off: 18 · CLI 호출 0" "$(rc b-badsel)|$(calls b-badsel)" "18|0"

# ── (c) 모델 목록 캐시 손상 — options 는 degraded 로 off 를 낸다 · set --model off 는 캐시를 보지 않는다
reset_env; C_SID="sid-c"; C_CH="$T/ch-bad"
choice c-opt options
check "(c) options 캐시 손상 → 0 · degraded · 모델 선택지 config/off" "$(rc c-opt)|$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("degraded"), ",".join(c["id"] for c in d["questions"]["model"]["choices"]))' "$T/c-c-opt/stdout" 2>/dev/null)" "0|cache-unreadable config,off"
choice c-set set --model off
check "(c) set --model off · 캐시 손상 → 0" "$(rc c-set)" 0
four c "사용자 선택"

# ── (d) GPT CLI 없음 — 선택 없음 · GPT 홈 없음(GPT 를 한 번도 쓰지 않은 사용자)
reset_env; C_SID="sid-d"; C_PATH="$NOCLI"; C_HOME="$T/home-bare"; C_CH="-"
choice d-get get
check "(d) get · CLI 없음 · 선택 없음 → 묻지 않고 0 · model=off" "$(rc d-get)|$(out d-get)" "0|model=off effort=off"
check "(d) get: off 를 기록" "$(tr '\n' '|' < "$T/sel/sid-d" 2>/dev/null)" "model=off|effort=off|"
four d "CLI 없음"
check "(d) 런처: GPT 홈 · 인증 게이트(11)보다 먼저 18" "$(grep -c 'INDEPENDENT-FAIL(11)' "$T/c-d-lnch/stderr" 2>/dev/null)" 0
# 선택이 없어도(저장 전) CLI 없음은 입구에서 바로 18 이다
reset_env; C_SID="sid-d2"; C_PATH="$NOCLI"
wrap d-nosel
check "(d) CLI 없음 · 선택 없음 · 래퍼 직접: 18 'GPT-OFF: CLI 없음'" "$(rc d-nosel)|$(offl d-nosel)" "18|GPT-OFF: CLI 없음"

# ── 비대화 — FZ_AUTONOMY 미설정 + CLI 있음 + 선택 없음: 스크립트는 묻지 않는다(질문은 Lead 몫)
reset_env; C_SID="sid-n"
choice n-get get
check "비대화: get → 3(물어도 됨 — 스크립트는 질문 도구 유무를 모른다) · 아무것도 쓰지 않는다" "$(rc n-get)|$([ -e "$T/sel/sid-n" ] && echo 1 || echo 0)" "3|0"
wrap n-wrap
check "비대화: 래퍼는 닫힌 stdin 에서 묻지 않고 config 로 돈다 — exit 0 · CLI 1회 · GPT-CHOICE config" "$(rc n-wrap)|$(calls n-wrap)|$(grep -c '^GPT-CHOICE model=fake-cfg (config) effort=low (config)' "$T/c-n-wrap/stderr")" "0|1|1"
reset_env; C_SID="sid-n2"; C_AUTO="autonomous"
choice n-auto get
check "비대화: FZ_AUTONOMY=autonomous → get 4(묻지 않음 — config)" "$(rc n-auto)" 4
# Lead 규칙(질문 도구를 쓸 수 없으면 exit 4 처럼) — 스크립트가 잴 수 없는 절반이라 정본 문구로 본다
n_rule="$(grep -c '질문 도구를 쓸 수 없는 실행.*exit 4' "$U/modules/gpt-strategy.md" 2>/dev/null)"
check "비대화: gpt-strategy 정본에 '질문 도구를 쓸 수 없는 실행 … exit 4' 규칙(1줄 이상)" "$([ "${n_rule:-0}" -ge 1 ] && echo yes || echo "no(${n_rule:-0})")" yes

echo
[ "$fail" -eq 0 ] && echo "off: 전건 통과" || echo "off: 실패 있음"
exit "$fail"
