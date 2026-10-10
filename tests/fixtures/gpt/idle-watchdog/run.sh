#!/bin/bash
# 진행 감시(idle watchdog) 러너 — F-364(+F-147) · SC-10. 가짜 CLI(../_shim/codex)로 래퍼 scripts/gpt-exec.sh 의 진행 감시와
# 독립 런처 scripts/gpt_independent.sh 와의 맞물림을 본다.
#
# ⛔ 실제 GPT CLI · 네트워크 · 사용자 홈을 쓰지 않는다 — PATH 앞에 shim, HOME · CODEX_HOME · TMPDIR 은 셀 임시 폴더.
# ⛔ shim 은 늘 이 러너 옆의 것이다(--tree 의 것이 아니다) — 시험 장치(PRELINES · TICK · TAG)는 고정하고 대상(래퍼 · 런처)만 바꾼다.
#    기준 트리의 shim 은 TAG 를 몰라 계수기 대조가 깨지므로, 그것을 쓰면 기준 실행이 판정이 아니라 준비 실패가 된다.
# ⛔ 잔존은 이름(`sleep N`)이 아니라 셀 태그로 센다 — shim 이 FZ_SHIM_TAG 를 자기와 자식의 argv0 `fz-shim[<태그>]` 에 싣는다.
#    전역 이름 검색은 동시 실행과 충돌하고(F-407), 환경 변수는 이 macOS 의 ps 에 보이지 않는다(실측). 정리는 늘 KILL 이다 —
#    TERM 으로 치우면 TERM 무시 자손이 남아 다음 셀 계수에 섞인다(F-402).
#
# 셀(16) — 이름이 PASS/FAIL 줄의 둘째 칸이다
#   <mode>:stall        mode = exec · review · resume. 2줄 쓰고 무출력 정체 → exit 12 · GPT-IDLE · 경과 ∈ [IDLE, E] · 잔존 0
#   <mode>:tick         1초마다 1줄 × 7(총 7초 > 2 × IDLE) → exit 0 · GATE-PASS · 마지막 줄까지 · GPT-IDLE 없음
#   <mode>:term-ignore  1줄 뒤 TERM 무시 자손이 정체 → exit 12 · GPT-IDLE · 잔존 0(KILL 까지 갔다)
#   <mode>:watch-off    FZ_GPT_IDLE_SEC=0 · 1줄 뒤 6초 무출력 → exit 0 · GATE-PASS · 경과 ≥ 5초(끊지 않았다)
#   concurrent:one-stall    두 exec 호출을 동시에(준비 동기화 — 둘 다 산 채로 준비) — 정체 쪽만 12 · 지속 출력 쪽은 0 으로 끝까지
#   launcher:group-kill     런처 --timeout 2 · 감시 끔 · TERM 무시 자손 → 런처 exit 16 · 잔존 0(런처의 그룹 kill 이 CLI 까지 닿는다 —
#                           CLI 가 래퍼 그룹 밖이면 남는다)
#   launcher:idle-12        런처 --timeout 20 · IDLE=3 → 런처 exit 12(15 · 16 아님) · 래퍼 로그 GPT-IDLE · 감사 timedOut=false
#   distinguish:idle-vs-cli-fail  같은 exit 12 · 같은 CLI 종료코드 143(감시 TERM 대 CLI 스스로 143)을 메시지 토큰 GPT-IDLE 과
#                           텔레메트리 9열(idle · -)이 가른다
# 셀마다(회마다)
#   ① 실행 직전 그 셀 태그 · 이 러너 태그의 잔존 0 단언 — 아니면 준비 실패(3)
#   ② 준비 동기화 — 스트림 로그에 표지 줄이 있고 태그 프로세스 수가 기대 이상(계수기가 그 셀의 자손을 실제로 본다는 양성 대조).
#      READY_CAP 초 안에 안 되면 준비 실패(3) — 판정 없이 FAIL(1)로 새지 않게
#   ③ 외부 상한 CAP = 3 × E(그 셀의 기대 상한, 아래 상수) — 준비 시점부터 잰다. 넘으면 대상 트리를 KILL 하고 FAIL
#   ④ 끝난 뒤 2초 안에 그 태그 잔존이 0 이 안 되면 남은 수가 LEAK — KILL 로 치우고 0 을 다시 확인(안 되면 3)
#   ⑤ 2회. 첫 회가 FAIL 이면 둘째는 건너뛴다(판정이 바뀌지 않는다 · 기준 실행이 상한을 두 번 기다리지 않게)
#   3배 여유: 통과한 회의 경과(준비 → 종료)는 E 이하여야 한다(= 상한의 1/3 이하). 넘으면 그 회 FAIL · CAP3X=fail
# 출력: 회마다 `PASS|FAIL  <셀> #<회> — …` · 마지막 줄 `WATCHDOG-CELLS=<셀 수> CAP3X=ok REPEAT=2 LEAK=0` 은 전건 통과일 때만
#   (실패면 `WATCHDOG-CELLS=<통과>/<셀 수> CAP3X=… REPEAT=… LEAK=…` + `FAIL: …`)
# exit: 0 전건 통과 · 1 셀 FAIL(판정 줄을 낸 뒤) · 3 준비 실패(인자 · 도구 · 임시 폴더 · 계수기 대조 · 준비 동기화 · 잔존 정리)
#   ⛔ 판정 줄 없이 끝나는 길(set -u 사망 · 신호)은 EXIT trap 이 3 으로 바꾼다 — 1 로 새면 기준 실행의 'exit 1' 단언이 측정 없이 통과한다
# [미검증: 실 GPT CLI 의 SIGTERM 정리 · 시스템 수면 중 감시 경과 — 이 러너는 shim 결과만 본다]
# usage: run.sh [--tree <플러그인 루트>]   (기본: 이 파일이 든 트리 — health-check 글롭은 인자 없이 부른다)
set -u
VERDICT="" T="" PSF=""
S_PID=()
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || { echo "SETUP 러너 위치를 풀지 못했다"; exit 3; }
R="$(cd "$HERE/../../../.." && pwd)" || { echo "SETUP 트리 루트를 풀지 못했다"; exit 3; }
SHIM_DIR="$(cd "$HERE/../_shim" && pwd)" || { echo "SETUP shim 폴더 없음: $HERE/../_shim"; exit 3; }
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "SETUP --tree 에 경로가 없다"; exit 3; }
            R="$(cd "$2" 2>/dev/null && pwd)" || { echo "SETUP --tree 경로 없음: $2"; exit 3; }; shift 2 ;;
    *) echo "SETUP 알 수 없는 인자: $1"; exit 3 ;;
  esac
done
WRAP="$R/scripts/gpt-exec.sh"; LAUNCH="$R/scripts/gpt_independent.sh"
SAMPLE="$HERE/../independent-arm/sample-plan-ok.json"

# 상수 — 초. E = 그 셀이 통과할 때 걸릴 시간의 상한(준비 → 종료). CAP = 3 × E
IDLE=3 GRACE=2 POLL=1 SLACK=3      # GRACE = 래퍼의 TERM → KILL 간격 · POLL = 감시 루프 한 바퀴
TICK_S=1 TICK_N=7                  # 지속 출력 — 간격 × 3 ≤ IDLE(3배 여유) · 총 길이 > 2 × IDLE(임계를 넘겨 산다)
OFF_SLEEP=6                        # 감시 끔 — IDLE 보다 긴 무출력
LAUNCH_TO=2 LAUNCH_GRACE=3 LAUNCH_IDLE_TO=20
LONG=97                            # 정체 자식 sleep — 어떤 상한보다 길다
READY_CAP=6
E_STALL=$((IDLE + POLL + GRACE + SLACK))
E_TICK=$((TICK_S * TICK_N + POLL + SLACK))
E_OFF=$((OFF_SLEEP + POLL + SLACK))
E_LKILL=$((LAUNCH_TO + LAUNCH_GRACE + POLL + SLACK))
E_LIDLE=$((E_STALL + SLACK))
E_QUICK=$((POLL + SLACK))
[ $((TICK_S * 3)) -le "$IDLE" ] && [ $((TICK_S * TICK_N)) -gt $((2 * IDLE)) ] && [ "$OFF_SLEEP" -gt "$IDLE" ] \
  && [ "$LAUNCH_IDLE_TO" -gt "$E_LIDLE" ] && [ "$LAUNCH_IDLE_TO" -lt $((3 * E_LIDLE)) ] && [ "$LONG" -gt $((3 * E_TICK)) ] \
  || { echo "SETUP 상수가 3배 여유 조건을 어긴다"; exit 3; }

for v in FZ_SHIM_CAPTURE FZ_SHIM_OUTPUT FZ_SHIM_EXIT FZ_SHIM_ENV_CAPTURE FZ_SHIM_ROLLOUT FZ_SHIM_SLEEP FZ_SHIM_IGNORE_TERM \
         FZ_SHIM_PRELINES FZ_SHIM_TICK FZ_SHIM_TAG FZ_SHIM_TAGGED FZ_GPT_IDLE_SEC FZ_GPT_EXEC_UNDER_TEST; do unset "$v"; done
RUNTAG="iw$$r$RANDOM"

tree_pids() {   # $1=pid — 자손부터 자기까지
  local c
  for c in $(pgrep -P "$1" 2>/dev/null); do tree_pids "$c"; done
  echo "$1"
}
# tagcount <패턴> → TC(그 문자열이 든 프로세스 수) · PSF(스냅샷). ⛔ 명령 치환 안에서 부르지 않는다 — 실패 exit 가 서브셸에서 사라진다
tagcount() {
  TC=""
  /bin/ps -axo pid=,command= > "$PSF" 2>/dev/null || return 1
  TC="$(awk -v t="$1" 'index($0, t) { n++ } END { print n + 0 }' "$PSF")" || return 1
  case "$TC" in ''|*[!0-9]*) return 1 ;; esac
}
# kill_tag <패턴> — KILL 하고 2초 안에 0 이 되는가
kill_tag() {
  local i=0
  while :; do
    tagcount "$1" || return 1
    [ "$TC" -eq 0 ] && return 0
    [ "$i" -ge 20 ] && return 1
    kill -KILL $(awk -v t="$1" 'index($0, t) { print $1 }' "$PSF") 2>/dev/null
    sleep 0.1; i=$((i + 1))
  done
}
on_exit() {
  local rc=$? p
  if [ -z "$VERDICT" ]; then   # 판정 전에 끊긴 회 — 그 대상 트리를 치운다(끝난 회의 pid 는 건드리지 않는다)
    for p in ${S_PID[@]+"${S_PID[@]}"}; do kill -KILL $(tree_pids "$p") 2>/dev/null; done
  fi
  [ -n "$PSF" ] && kill_tag "fz-shim[$RUNTAG-" >/dev/null 2>&1
  [ -n "$T" ] && rm -rf "${T:?}"
  if [ -z "$VERDICT" ]; then echo "SETUP 판정 줄 없이 끝났다(exit $rc) — 준비 실패 3"; exit 3; fi
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 3' TERM INT HUP
setup_fail() { echo "SETUP $*"; exit 3; }
# 경과 · 상한은 깨어 있는 시간으로 잰다 — CLOCK_UPTIME_RAW(Darwin) 는 시스템 수면 동안 흐르지 않는다(없으면 CLOCK_MONOTONIC — Linux 는 수면 제외).
#   ⛔ 벽시계로 재면 수면이 낀 회가 거짓 FAIL 이 된다(2026-10-09 실측: Maintenance Sleep 925초에 걸린 회가 경과 934s · 상한 초과로 찍혔다)
CLK=CLOCK_UPTIME_RAW
perl -MTime::HiRes=clock_gettime,$CLK -e 1 2>/dev/null || CLK=CLOCK_MONOTONIC
now_ms() { perl -MTime::HiRes=clock_gettime,$CLK -e "printf qq(%d\n), clock_gettime($CLK()) * 1000"; }

[ -f "$WRAP" ] || setup_fail "대상 래퍼 없음: $WRAP"
[ -f "$LAUNCH" ] || setup_fail "대상 런처 없음: $LAUNCH"
[ -s "$SAMPLE" ] || setup_fail "plan 표본 없음: $SAMPLE"
for t in perl python3 pgrep awk; do command -v "$t" >/dev/null 2>&1 || setup_fail "도구 없음: $t"; done
[ "$(now_ms)" -gt 0 ] 2>/dev/null || setup_fail "밀리초 시계(perl Time::HiRes $CLK) 실패"
PATH0="$PATH"
[ "$(PATH="$SHIM_DIR:$PATH0" command -v codex)" = "$SHIM_DIR/codex" ] || setup_fail "PATH 앞 codex 가 shim 이 아니다"
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공한다(F-355). 명시 템플릿이라 TMPDIR 을 따른다
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-idle-wd.XXXXXX")" || setup_fail "mktemp 실패"
T="$(cd "$T0" && pwd -P)" || { T="$T0"; setup_fail "임시 폴더 정규화 실패: $T0"; }
PSF="$T/ps.txt"
mkdir -p "$T/repo" "$T/home" "$T/codex-home" "$T/tmp" "$T/in" || setup_fail "임시 폴더 구성 실패"
echo "과제 IDLE-WD-TASK" > "$T/task.txt"
echo "11111111-2222-3333-4444-555555555555" > "$T/prev.session"
printf '# 요구\n주문 취소 시 알림을 끊는다 REQ-IDLE-WD\n' > "$T/in/requirement.md"
H="$T/realhome"; mkdir -p "$H/.codex" || setup_fail "임시 홈 구성 실패"
echo '{"fake":"auth"}' > "$H/.codex/auth.json"; printf 'model = "m-test"\n' > "$H/.codex/config.toml"
HREAL="$(cd "$H" && pwd -P)" || setup_fail "임시 홈 정규화 실패"
python3 - "$T/r-ok.jsonl" "$HREAL" <<'PY' || setup_fail "rollout 표본 생성 실패"
import json, sys
f, home = sys.argv[1], sys.argv[2]
ents = [{"path": {"type": "path", "path": home}, "access": "deny"}, {"path": {"type": "special", "value": {"kind": "root"}}, "access": "read"}]
rows = [{"type": "session_meta", "payload": {"id": "x"}},
        {"type": "turn_context", "payload": {"permission_profile": {"type": "managed", "file_system": {"type": "restricted", "entries": ents}}}},
        {"type": "response_item", "payload": {"type": "custom_tool_call", "name": "exec", "input": "tools.exec_command({cmd:\"cat requirement.md\"})"}}]
open(f, "w", encoding="utf-8").write("\n".join(json.dumps(r) for r in rows) + "\n")
PY

# 계수기 양성 대조 — 태그 붙은 sleep 을 직접 띄워 1 로 보이는가 · shim 이 자기와 자식을 태그하는가(2 이상) · KILL 뒤 0
# 대조 프로세스는 이중 fork 로 띄운다 — 러너의 작업이 아니라서 KILL 때 셸의 'Killed: 9' 알림이 출력에 섞이지 않는다(정리 확인은 태그 계수가 한다)
( ( exec -a "fz-shim[$RUNTAG-probe]" sleep "$LONG" ) & )
i=0; while :; do tagcount "fz-shim[$RUNTAG-probe]" || setup_fail "ps 실패"; [ "$TC" -eq 1 ] && break
  [ "$i" -ge 30 ] && setup_fail "계수기 대조 실패 — 태그 sleep 1개가 ${TC}개로 보인다(ps 의 argv 표시 확인)"; sleep 0.1; i=$((i + 1)); done
kill_tag "fz-shim[$RUNTAG-probe]" || setup_fail "계수기 대조 — KILL 뒤에도 남았다"
( env PATH="$SHIM_DIR:$PATH0" FZ_SHIM_TAG="$RUNTAG-probe2" FZ_SHIM_SLEEP="$LONG" bash "$SHIM_DIR/codex" exec -o "$T/probe2.out" -- x >/dev/null 2>&1 & )
i=0; while :; do tagcount "fz-shim[$RUNTAG-probe2]" || setup_fail "ps 실패"; [ "$TC" -ge 2 ] && break
  [ "$i" -ge 30 ] && setup_fail "계수기 대조 실패 — shim 이 자기와 자식을 태그하지 않는다(${TC}개)"; sleep 0.1; i=$((i + 1)); done
kill_tag "fz-shim[$RUNTAG-probe2]" || setup_fail "계수기 대조 — shim KILL 뒤에도 남았다"

echo "IDLE-WATCHDOG — TREE=$R · shim=$SHIM_DIR/codex · IDLE=${IDLE}s · E(정체 ${E_STALL} · 지속 ${E_TICK} · 끔 ${E_OFF} · 런처kill ${E_LKILL} · 런처idle ${E_LIDLE}) · CAP=3E · READY_CAP=${READY_CAP}s"

# ── 슬롯 — 한 회에서 감시하는 대상(1개 · 동시 셀 2개). 배열 인덱스 0..N-1
#    S_PID · S_TAG · S_LOG(표지 파일) · S_MARK(표지 줄) · S_MIN(준비 때 태그 수 하한) · S_E → S_RC · S_EL(ms) · S_CAP · S_LEAK
reset_slots() { S_PID=(); S_TAG=(); S_LOG=(); S_MARK=(); S_MIN=(); S_E=(); S_TR=(); S_TE=(); S_RC=(); S_EL=(); S_CAP=(); S_LEAK=(); NS=0; }
pre_residue() {  # $1=셀 태그 — 실행 직전 잔존 0
  tagcount "fz-shim[$1]" || setup_fail "ps 실패"; [ "$TC" -eq 0 ] || setup_fail "실행 직전 잔존 ${TC}개 — 태그 $1"
  tagcount "fz-shim[$RUNTAG-" || setup_fail "ps 실패"; [ "$TC" -eq 0 ] || setup_fail "실행 직전 이 러너의 잔존 ${TC}개 — 앞 셀 정리 실패"
}
add_slot() {     # $1=pid · $2=태그 · $3=표지 파일 · $4=표지 줄 · $5=태그 수 하한 · $6=E
  S_PID[$NS]="$1"; S_TAG[$NS]="$2"; S_LOG[$NS]="$3"; S_MARK[$NS]="$4"; S_MIN[$NS]="$5"; S_E[$NS]="$6"
  S_TR[$NS]=""; S_TE[$NS]=""; S_RC[$NS]=""; S_EL[$NS]=""; S_CAP[$NS]=0; S_LEAK[$NS]=0; NS=$((NS + 1))
}
kill_slot_tree() {  # $1=슬롯 — 상한 초과: 대상 트리(목록을 먼저 모은다)와 태그를 KILL
  local pids; pids="$(tree_pids "${S_PID[$1]}")"
  kill -KILL $pids 2>/dev/null
  kill_tag "fz-shim[${S_TAG[$1]}]" || setup_fail "상한 초과 정리 실패 — 태그 ${S_TAG[$1]}"
}
# supervise $1=동기화(1 = 모든 슬롯이 산 채로 준비돼야 한다)
supervise() {
  local sync="$1" i t0 now ready alive
  t0="$(now_ms)"
  while :; do                                   # ② 준비 동기화
    ready=1; i=0
    while [ "$i" -lt "$NS" ]; do
      if [ -z "${S_TR[$i]}" ]; then
        if grep -qxF -- "${S_MARK[$i]}" "${S_LOG[$i]}" 2>/dev/null; then
          tagcount "fz-shim[${S_TAG[$i]}]" || setup_fail "ps 실패"
          if [ "$TC" -ge "${S_MIN[$i]}" ]; then S_TR[$i]="$(now_ms)"; else ready=0; fi
        else ready=0; fi
      fi
      i=$((i + 1))
    done
    if [ "$ready" = 1 ]; then
      if [ "$sync" = 1 ]; then
        i=0; while [ "$i" -lt "$NS" ]; do kill -0 "${S_PID[$i]}" 2>/dev/null || setup_fail "동시 준비 동기화 실패 — 슬롯 $i 가 다른 슬롯 준비 전에 끝났다"; i=$((i + 1)); done
      fi
      break
    fi
    now="$(now_ms)"
    if [ $((now - t0)) -ge $((READY_CAP * 1000)) ]; then
      i=0; while [ "$i" -lt "$NS" ]; do kill_slot_tree "$i"; wait "${S_PID[$i]}" 2>/dev/null; i=$((i + 1)); done
      setup_fail "준비 동기화 실패 — ${READY_CAP}s 안에 표지 줄 · 태그 프로세스가 안 보였다(대상이 CLI 를 띄우지 않았거나 shim 태그가 깨졌다 · 셀 $CELL)"
    fi
    sleep 0.1
  done
  while :; do                                   # ③ 끝 · 외부 상한
    alive=0; now="$(now_ms)"; i=0
    while [ "$i" -lt "$NS" ]; do
      if [ -z "${S_TE[$i]}" ]; then
        if ! kill -0 "${S_PID[$i]}" 2>/dev/null; then S_TE[$i]="$now"
        elif [ $((now - S_TR[$i])) -ge $((3 * S_E[$i] * 1000)) ]; then kill_slot_tree "$i"; S_CAP[$i]=1; S_TE[$i]="$now"
        else alive=1; fi
      fi
      i=$((i + 1))
    done
    [ "$alive" = 0 ] && break
    sleep 0.1
  done
  i=0
  while [ "$i" -lt "$NS" ]; do                  # ④ 종료코드 · 잔존
    wait "${S_PID[$i]}"; S_RC[$i]=$?
    S_EL[$i]=$((S_TE[$i] - S_TR[$i]))
    if [ "${S_CAP[$i]}" = 0 ]; then
      local k=0
      while :; do
        tagcount "fz-shim[${S_TAG[$i]}]" || setup_fail "ps 실패"
        [ "$TC" -eq 0 ] && break
        [ "$k" -ge 20 ] && { S_LEAK[$i]="$TC"; break; }
        sleep 0.1; k=$((k + 1))
      done
    fi
    kill_tag "fz-shim[${S_TAG[$i]}]" || setup_fail "잔존 KILL 정리 실패 — 태그 ${S_TAG[$i]}"
    i=$((i + 1))
  done
}

# ── 대상 실행 — env 는 배열 CENV(셀마다)
start_wrap() {   # $1=셀 폴더 · 나머지=래퍼 인자 → LPID
  local d="$1"; shift
  env ${CENV[@]+"${CENV[@]}"} PATH="$SHIM_DIR:$PATH0" HOME="$T/home" CODEX_HOME="$T/codex-home" TMPDIR="$T/tmp" \
    FZ_GPT_CHOICE_DIR="$T/no-choice" FZ_TELEMETRY_DIR="$d/tel" \
    /bin/bash "$WRAP" "$@" > "$d/stdout" 2> "$d/stderr" &
  LPID=$!
}
start_launch() { # $1=셀 폴더 · $2=run-id · 나머지=런처 인자 → LPID
  local d="$1" rid="$2"; shift 2
  mkdir -p "$d/out" "$d/tel"
  env -u CODEX_HOME -u FZ_GPT_CHOICE_DIR ${CENV[@]+"${CENV[@]}"} PATH="$SHIM_DIR:$PATH0" HOME="$H" TMPDIR="$T/tmp" \
    CLAUDE_CODE_SESSION_ID=idle-wd-no-choice FZ_TELEMETRY_DIR="$d/tel" FZ_SHIM_OUTPUT="$(cat "$SAMPLE")" FZ_SHIM_ROLLOUT="$T/r-ok.jsonl" \
    /bin/bash "$LAUNCH" "$@" --arm A --run-id "$rid" --out-dir "$d/out" > "$d/stdout" 2> "$d/stderr" &
  LPID=$!
}
wrap_args() {    # $1=mode · $2=셀 폴더 → WA(래퍼 인자 배열)
  case "$1" in
    exec)   WA=(exec --cd "$T/repo" --out "$2/out.txt" --prompt-file "$T/task.txt") ;;
    review) WA=(review --cd "$T/repo" --out "$2/out.txt" --uncommitted) ;;
    resume) WA=(resume --cd "$T/repo" --out "$2/out.txt" --prompt-file "$T/task.txt" --session-file "$T/prev.session") ;;
  esac
}
has() { grep -qF -- "$2" "$1" 2>/dev/null; }
tok() { if has "$1" "$2"; then echo "$2"; else echo "$2 없음"; fi; }   # 요지 줄 — 고정 문구가 아니라 관측값
sec() { awk -v m="$1" 'BEGIN { printf "%.1f", m / 1000 }'; }
tel9() {         # $1=셀 폴더 · $2=열 — 텔레메트리 마지막 행의 그 열
  local f="$1/tel/gpt-skill-usage.tsv"
  [ -s "$f" ] || { echo ""; return; }
  tail -1 "$f" | awk -F'\t' -v c="$2" '{ print $c }'
}

# ── 판정 — 회마다 WHY 를 모은다(빈 값 = 통과)
WHY=""
need() { [ "$1" = 1 ] || WHY="$WHY · $2"; }
common_end() {   # $1=슬롯 — 상한 · 잔존 · 3배 여유
  local i="$1"
  [ "${S_CAP[$i]}" = 0 ] || { WHY="$WHY · 외부 상한 $((3 * S_E[$i]))s 까지 안 끝났다(KILL 정리)"; return; }
  [ "${S_LEAK[$i]}" -eq 0 ] || { WHY="$WHY · 자손 잔존 ${S_LEAK[$i]}"; LEAK_TOTAL=$((LEAK_TOTAL + S_LEAK[$i])); }
  [ "${S_EL[$i]}" -le $((S_E[$i] * 1000)) ] || { WHY="$WHY · 경과 $(sec "${S_EL[$i]}")s > E ${S_E[$i]}s(3배 여유 미달)"; CAP3X_BAD=1; }
}
judge_stall() {  # $1=슬롯 · $2=셀 폴더(stdout · stderr)
  local i="$1" d="$2"
  common_end "$i"; [ "${S_CAP[$i]}" = 0 ] || return
  need "$([ "${S_RC[$i]}" = 12 ] && echo 1)" "exit ${S_RC[$i]}(기대 12)"
  need "$(has "$d/stderr" 'GATE-FAIL(12): GPT-IDLE' && echo 1)" "stderr 에 GPT-IDLE 없음"
  need "$(has "$d/stdout" 'GATE-PASS' || echo 1)" "GATE-PASS 가 찍혔다"
  need "$([ "${S_EL[$i]}" -ge $((IDLE * 1000)) ] && echo 1)" "경과 $(sec "${S_EL[$i]}")s < IDLE ${IDLE}s(너무 일찍 끊었다)"
}
judge_done() {   # $1=슬롯 · $2=셀 폴더 · $3=마지막 표지 줄(없으면 빈 값) · $4=경과 하한 ms
  local i="$1" d="$2"
  common_end "$i"; [ "${S_CAP[$i]}" = 0 ] || return
  need "$([ "${S_RC[$i]}" = 0 ] && echo 1)" "exit ${S_RC[$i]}(기대 0)"
  need "$(has "$d/stdout" 'GATE-PASS' && echo 1)" "GATE-PASS 없음"
  need "$(has "$d/stderr" 'GPT-IDLE' || echo 1)" "GPT-IDLE 이 찍혔다(끊으면 안 된다)"
  [ -z "$3" ] || need "$(grep -qxF -- "$3" "${S_LOG[$i]}" && echo 1)" "마지막 줄 '$3' 없음(끝까지 안 갔다)"
  need "$([ "${S_EL[$i]}" -ge "$4" ] && echo 1)" "경과 $(sec "${S_EL[$i]}")s < 하한 $(sec "$4")s"
}
report() {       # $1=셀 · $2=회 · $3=요지
  if [ -z "$WHY" ]; then echo "PASS  $1 #$2 — $3"; return 0; fi
  echo "FAIL  $1 #$2 — ${WHY# · } [$3]"; return 1
}

# ── 셀 본문 — run_<종류> <셀 이름> <회> <셀 폴더> <태그> [mode]
run_stall() {    # $5=mode · $6=TERM 무시(1/빈 값)
  local c="$1" r="$2" d="$3" tag="$4" m="$5" ig="$6" pl=2 mark="shim-line 2"
  [ -n "$ig" ] && { pl=1; mark="shim-line 1"; }
  wrap_args "$m" "$d"; CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag" FZ_SHIM_PRELINES="$pl" FZ_SHIM_SLEEP="$LONG" ${ig:+FZ_SHIM_IGNORE_TERM=1})
  reset_slots; start_wrap "$d" "${WA[@]}"; add_slot "$LPID" "$tag" "$d/out.txt.stream.log" "$mark" 2 "$E_STALL"
  supervise 0; WHY=""; judge_stall 0 "$d"
  report "$c" "$r" "exit ${S_RC[0]} · $(tok "$d/stderr" GPT-IDLE) · 준비→종료 $(sec "${S_EL[0]}")s ∈ [${IDLE}, ${E_STALL}] · 상한 $((3 * E_STALL))s · 잔존 ${S_LEAK[0]}"
}
run_tick() {
  local c="$1" r="$2" d="$3" tag="$4" m="$5"
  wrap_args "$m" "$d"; CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag" FZ_SHIM_TICK="$TICK_S:$TICK_N")
  reset_slots; start_wrap "$d" "${WA[@]}"; add_slot "$LPID" "$tag" "$d/out.txt.stream.log" "tick 1" 1 "$E_TICK"
  supervise 0; WHY=""; judge_done 0 "$d" "tick $TICK_N" 0
  report "$c" "$r" "exit ${S_RC[0]} · $(tok "$d/stdout" GATE-PASS) · tick $TICK_N 까지 · 준비→종료 $(sec "${S_EL[0]}")s ≤ ${E_TICK} · 잔존 ${S_LEAK[0]}"
}
run_off() {
  local c="$1" r="$2" d="$3" tag="$4" m="$5"
  wrap_args "$m" "$d"; CENV=(FZ_GPT_IDLE_SEC=0 FZ_SHIM_TAG="$tag" FZ_SHIM_PRELINES=1 FZ_SHIM_SLEEP="$OFF_SLEEP")
  reset_slots; start_wrap "$d" "${WA[@]}"; add_slot "$LPID" "$tag" "$d/out.txt.stream.log" "shim-line 1" 2 "$E_OFF"
  supervise 0; WHY=""; judge_done 0 "$d" "" $(((OFF_SLEEP - 1) * 1000))
  report "$c" "$r" "exit ${S_RC[0]} · $(tok "$d/stdout" GATE-PASS) · 무출력 ${OFF_SLEEP}s 를 끊지 않음 · 준비→종료 $(sec "${S_EL[0]}")s ∈ [$((OFF_SLEEP - 1)), ${E_OFF}] · 잔존 ${S_LEAK[0]}"
}
run_concurrent() {
  local c="$1" r="$2" d="$3" tag="$4"
  mkdir -p "$d/a" "$d/b"
  reset_slots
  wrap_args exec "$d/a"; CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag-a" FZ_SHIM_PRELINES=2 FZ_SHIM_SLEEP="$LONG")
  start_wrap "$d/a" "${WA[@]}"; add_slot "$LPID" "$tag-a" "$d/a/out.txt.stream.log" "shim-line 2" 2 "$E_STALL"
  wrap_args exec "$d/b"; CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag-b" FZ_SHIM_TICK="$TICK_S:$TICK_N")
  start_wrap "$d/b" "${WA[@]}"; add_slot "$LPID" "$tag-b" "$d/b/out.txt.stream.log" "tick 1" 1 "$E_TICK"
  supervise 1; WHY=""
  judge_stall 0 "$d/a"; judge_done 1 "$d/b" "tick $TICK_N" 0
  report "$c" "$r" "정체 쪽 exit ${S_RC[0]} · $(sec "${S_EL[0]}")s · 지속 쪽 exit ${S_RC[1]} · $(sec "${S_EL[1]}")s · 잔존 ${S_LEAK[0]}+${S_LEAK[1]}"
}
run_lkill() {
  local c="$1" r="$2" d="$3" tag="$4" rid="gk$2"
  CENV=(FZ_GPT_IDLE_SEC=0 FZ_SHIM_TAG="$tag" FZ_SHIM_PRELINES=1 FZ_SHIM_SLEEP="$LONG" FZ_SHIM_IGNORE_TERM=1)
  reset_slots; start_launch "$d" "$rid" plan --requirement "$T/in/requirement.md" --timeout "$LAUNCH_TO"
  add_slot "$LPID" "$tag" "$d/out/A-$rid.json.stream.log" "shim-line 1" 2 "$E_LKILL"
  supervise 0; WHY=""; common_end 0
  if [ "${S_CAP[0]}" = 0 ]; then
    need "$([ "${S_RC[0]}" = 16 ] && echo 1)" "런처 exit ${S_RC[0]}(기대 16)"
    need "$(has "$d/stdout" 'INDEPENDENT OK' || echo 1)" "INDEPENDENT OK 가 찍혔다"
    need "$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(1 if d.get("timedOut") is True else 0)' "$d/out/A-$rid.audit.json" 2>/dev/null)" "감사 timedOut 이 true 가 아니다"
  fi
  report "$c" "$r" "런처 exit ${S_RC[0]} · 그룹 kill 뒤 태그 잔존 ${S_LEAK[0]}(TERM 무시 자손 포함) · 준비→종료 $(sec "${S_EL[0]}")s ≤ ${E_LKILL}"
}
run_lidle() {
  local c="$1" r="$2" d="$3" tag="$4" rid="li$2"
  CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag" FZ_SHIM_PRELINES=1 FZ_SHIM_SLEEP="$LONG")
  reset_slots; start_launch "$d" "$rid" plan --requirement "$T/in/requirement.md" --timeout "$LAUNCH_IDLE_TO"
  add_slot "$LPID" "$tag" "$d/out/A-$rid.json.stream.log" "shim-line 1" 2 "$E_LIDLE"
  supervise 0; WHY=""; common_end 0
  if [ "${S_CAP[0]}" = 0 ]; then
    need "$([ "${S_RC[0]}" = 12 ] && echo 1)" "런처 exit ${S_RC[0]}(기대 12 — 15 오염 · 16 시간 초과가 아니다)"
    need "$(has "$d/out/A-$rid.wrapper.log" 'GATE-FAIL(12): GPT-IDLE' && echo 1)" "래퍼 로그에 GPT-IDLE 없음"
    need "$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(1 if d.get("timedOut") is False and d.get("wrapperExit") == 12 else 0)' "$d/out/A-$rid.audit.json" 2>/dev/null)" "감사 timedOut=false · wrapperExit=12 아님"
    need "$([ "${S_EL[0]}" -ge $((IDLE * 1000)) ] && echo 1)" "경과 $(sec "${S_EL[0]}")s < IDLE"
  fi
  report "$c" "$r" "런처 exit ${S_RC[0]} · 래퍼 로그 $(tok "$d/out/A-$rid.wrapper.log" GPT-IDLE) · 준비→종료 $(sec "${S_EL[0]}")s ≤ ${E_LIDLE} · 잔존 ${S_LEAK[0]}"
}
run_distinguish() {
  local c="$1" r="$2" d="$3" tag="$4" a b
  mkdir -p "$d/a/tel" "$d/b/tel"; WHY=""
  wrap_args exec "$d/a"; CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag-a" FZ_SHIM_PRELINES=2 FZ_SHIM_SLEEP="$LONG")
  reset_slots; start_wrap "$d/a" "${WA[@]}" --gpt-skill fz-idle-wd; add_slot "$LPID" "$tag-a" "$d/a/out.txt.stream.log" "shim-line 2" 2 "$E_STALL"
  supervise 0; judge_stall 0 "$d/a"; a="exit ${S_RC[0]} · $(sec "${S_EL[0]}")s · $(tok "$d/a/stderr" GPT-IDLE)"
  if [ "${S_CAP[0]}" = 0 ]; then
    pre_residue "$tag-b"
    wrap_args exec "$d/b"; CENV=(FZ_GPT_IDLE_SEC="$IDLE" FZ_SHIM_TAG="$tag-b" FZ_SHIM_PRELINES=2 FZ_SHIM_EXIT=143)
    reset_slots; start_wrap "$d/b" "${WA[@]}" --gpt-skill fz-idle-wd; add_slot "$LPID" "$tag-b" "$d/b/out.txt.stream.log" "shim-line 2" 0 "$E_QUICK"
    supervise 0; common_end 0; b="exit ${S_RC[0]} · $(tok "$d/b/stderr" GPT-IDLE)"
    if [ "${S_CAP[0]}" = 0 ]; then
      need "$([ "${S_RC[0]}" = 12 ] && echo 1)" "CLI 실패 exit ${S_RC[0]}(기대 12)"
      need "$(has "$d/b/stderr" 'GATE-FAIL(12)' && echo 1)" "CLI 실패에 GATE-FAIL(12) 없음"
      need "$(has "$d/b/stderr" 'GPT-IDLE' || echo 1)" "CLI 실패에 GPT-IDLE 이 찍혔다"
    fi
    need "$([ "$(tel9 "$d/a" 6)" = 143 ] && [ "$(tel9 "$d/b" 6)" = 143 ] && echo 1)" "텔레메트리 exit 열 '$(tel9 "$d/a" 6)' · '$(tel9 "$d/b" 6)'(둘 다 143 이어야 대조가 선다)"
    need "$([ "$(tel9 "$d/a" 9)" = idle ] && echo 1)" "정체 쪽 텔레메트리 9열 '$(tel9 "$d/a" 9)'(기대 idle)"
    need "$([ "$(tel9 "$d/b" 9)" = - ] && echo 1)" "CLI 실패 쪽 텔레메트리 9열 '$(tel9 "$d/b" 9)'(기대 -)"
  fi
  report "$c" "$r" "정체 $a · 9열 $(tel9 "$d/a" 9) ↔ CLI 실패 ${b:-미실행} · 9열 $(tel9 "$d/b" 9) · exit 열 둘 다 $(tel9 "$d/a" 6)"
}

# ── 셀 목록 · 실행
CELLS="exec:stall exec:tick exec:term-ignore exec:watch-off review:stall review:tick review:term-ignore review:watch-off resume:stall resume:tick resume:term-ignore resume:watch-off concurrent:one-stall launcher:group-kill launcher:idle-12 distinguish:idle-vs-cli-fail"
NCELL=0 NPASS=0 LEAK_TOTAL=0 CAP3X_BAD=0 BAD="" REPS_OK=1
for CELL in $CELLS; do
  NCELL=$((NCELL + 1)); cell_ok=1
  for rep in 1 2; do
    tag="$RUNTAG-$NCELL-$rep"; d="$T/c$NCELL-$rep"; mkdir -p "$d" || setup_fail "셀 폴더 생성 실패"
    pre_residue "$tag"; pre_residue "$tag-a"; pre_residue "$tag-b"
    case "$CELL" in
      *:stall)       run_stall "$CELL" "$rep" "$d" "$tag" "${CELL%%:*}" "" ;;
      *:term-ignore) run_stall "$CELL" "$rep" "$d" "$tag" "${CELL%%:*}" 1 ;;
      *:tick)        run_tick "$CELL" "$rep" "$d" "$tag" "${CELL%%:*}" ;;
      *:watch-off)   run_off "$CELL" "$rep" "$d" "$tag" "${CELL%%:*}" ;;
      concurrent:one-stall)          run_concurrent "$CELL" "$rep" "$d" "$tag" ;;
      launcher:group-kill)           run_lkill "$CELL" "$rep" "$d" "$tag" ;;
      launcher:idle-12)              run_lidle "$CELL" "$rep" "$d" "$tag" ;;
      distinguish:idle-vs-cli-fail)  run_distinguish "$CELL" "$rep" "$d" "$tag" ;;
      *) setup_fail "셀 목록 오류: $CELL" ;;
    esac
    if [ $? -ne 0 ]; then
      cell_ok=0; BAD="$BAD $CELL"
      [ "$rep" = 1 ] && { echo "SKIP  $CELL #2 — 첫 회 FAIL(판정 불변)"; REPS_OK=0; }
      break
    fi
  done
  [ "$cell_ok" = 1 ] && NPASS=$((NPASS + 1))
done

CAP3X=ok; [ "$CAP3X_BAD" = 0 ] || CAP3X=fail
VERDICT=1
if [ "$NPASS" -eq "$NCELL" ] && [ "$LEAK_TOTAL" -eq 0 ] && [ "$CAP3X" = ok ] && [ "$REPS_OK" = 1 ]; then
  echo "WATCHDOG-CELLS=$NCELL CAP3X=ok REPEAT=2 LEAK=0"
  exit 0
fi
echo "WATCHDOG-CELLS=$NPASS/$NCELL CAP3X=$CAP3X REPEAT=$([ "$REPS_OK" = 1 ] && echo 2 || echo partial) LEAK=$LEAK_TOTAL"
echo "FAIL:$BAD"
exit 1
