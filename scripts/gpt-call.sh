#!/bin/bash
# gpt-call.sh — GPT 호출 정문 (bash 3.2). 호출자는 *무엇*(kind + 입력)만 말한다.
#   *어떻게*(모드 · 역할 스킬 · 스키마 · 고정 플래그 · verify-cross 의 격리 홈과 세션)는 scripts/gpt-kinds.json 이 정하고
#   scripts/gpt_kinds.py 가 푼다. 실행 메커니즘(샌드박스 · 모델/effort 결정 · 타임아웃)은 어댑터 몫이다 —
#   일반 kind 는 scripts/gpt-exec.sh, 독립 kind 는 scripts/gpt_independent.sh.
#
# usage: gpt-call.sh KIND [--experimental] [입력...]       입력 = gpt-kinds.json 의 kinds.<KIND>.inputs
#   예: gpt-call.sh verify --cd "$GIT_ROOT" --out "$OUT" --prompt-file "$P"
#       gpt-call.sh review --cd "$GIT_ROOT" --out "$F" --base "$BASE_BRANCH"
#       gpt-call.sh verify-cross --audit "$AUDIT" --cd "$GIT_ROOT" --out "$OUT" --prompt-file "$P_VERIFY" --prompt-out "$P_CROSS"
#       gpt-call.sh independent-review --diff "$D" --deny "$WORK_DIR" --arm gpt --run-id "$RUN" --out-dir "$WORK_DIR/gpt-independent"
#   ⛔ 정책 플래그(-p · --profile · --ignore-user-config · --config-permissions · -c · --schema · --inject-skill · --gpt-skill(-path) ·
#      --ephemeral · --sandbox)는 거부(10). --model · --effort 는 값 그대로 어댑터에 넘긴다(E1 — 판정은 래퍼).
#
# 잠금 · 정리 (P-17 · R-04): 일반 kind 는 정문이 OUT 잠금(`<OUT 실경로>.lock`)을 갖는다 — 독립 kind 는 런처가 갖는다.
#   잠금을 잡은 뒤에만 정리한다: 정문이 거부로 끝날 때와 어댑터를 띄우기 직전에 옛 OUT · OUT.session 을 지운다(XE-03 · IR-06 —
#   래퍼 사전 게이트가 10 · 11 로 끝나도 옛 결과를 새 판정으로 읽지 않게). verify-cross 는 어느 출구로 끝나든 격리 홈을 정리한다(E3).
#   --session-file 입력은 지우지 않는다(같은 파일 · 심볼릭 별칭 포함 — P-09). 잠금을 못 잡으면 아무것도 지우지 않는다.
#   어댑터는 exec 가 아니라 자기 프로세스 그룹의 자식으로 돈다 — TERM · INT · HUP 은 그 그룹에 TERM 으로 넘기고(배경 작업은 INT 를
#   무시한 채 시작한다) 3초 뒤 KILL 한다. 잠금은 정상 · 실패 · 신호 어느 쪽이든 EXIT 에서 푼다.
#   ⛔ 정문을 배경 작업(`&`)으로 띄우면 INT 가 무시된 채 들어와 bash 가 INT 를 trap 하지 못한다 — 그때 중단은 TERM 으로 보낸다.
#
# 라운드(정본 modules/cross-validation.md § 재검증 라운드 상한 · 판정 scripts/gpt_rounds.py): env FZ_GPT_ARTIFACT(plan · guide-plan · code)가
#   있는 호출만 센다 — 없으면 판정기를 부르지 않는다. 어댑터 직전에 reserve(원장 잠금 안에서 검사 + 슬롯 예약만 · 실행은 잠금 밖) ·
#   EXIT 에서 finish(rc) — 소비 여부는 판정기가 rc 로 정한다. 예약 전에 끝난 호출(사용법 · 레지스트리 · 같은 --out · 합성 실패)은
#   원장을 건드리지 않는다. 거부(19)도 옛 OUT 을 지우되, 판정기가 ROUND-KEEP-OUT 을 내면(같은 입력 · 이번 --out 이 직전 판정 파일)
#   남긴다 — 그 판정이 답이다. 같이 읽는 env: FZ_WORK_DIR · FZ_GPT_ARTIFACT_VERSION · FZ_GPT_RECALL=post-check
#
# exit: 어댑터의 exit 를 그대로 넘긴다(10~17 을 다시 매기지 않는다 — 측정 실패를 0건으로 만들지 않는다).
#       18 = GPT 미사용 — 어댑터가 CLI 를 부르지 않았다(세션 선택 off · 입력 --model off · GPT CLI 없음 · stderr 'GPT-OFF: <사유> — …').
#            측정 실패가 아니다 — 소비자는 그 단계를 건너뛰고 [GPT 미사용 — 사유] 를 남긴다(정본 modules/gpt-strategy.md § GPT 미사용).
#            판정은 어댑터 몫이다 — 정문은 --model 값을 그대로 넘기고(E1) 사용법 거부(10 · 11)가 그보다 먼저다
#       정문 자신: 10 사용법(모르는 kind · 입력 누락/금지/미지 · 실험 kind 에 --experimental 없음 · 같은 --out 동시 · 상위 폴더 없음)
#                  11 레지스트리 · 의존성(python3 없음 · 레지스트리 손상 · resolver 오류 · 합성 실패 · 어댑터 없음 · 라운드 원장 판정 불가) · 128+N 신호
#                  19 재검증 라운드 거부 — stderr 'GPT-ROUNDS: <budget-exhausted|same-input|recall-used> — …' · 어댑터를 띄우지 않았다.
#                     측정 실패도 통과도 아니다 — budget-exhausted 는 미해결로 보고한다(정본 modules/cross-validation.md § 재검증 라운드 상한).
#                     FZ_GPT_ARTIFACT 값 · FZ_WORK_DIR 폴더가 틀리면 10 이다
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die() { echo "GPT-CALL-FAIL($1): $2" >&2; exit "$1"; }
# 호출 행 — 어댑터(래퍼)가 쓰는 gpt-calls.tsv 에 정문 거부(어댑터를 띄우기 전 종료)는 정문이 origin=gate 행으로 남긴다(P-08).
#   어댑터가 이번 call_id 행 없이 끝나도(런처가 래퍼를 띄우기 전에 거부) 같은 행을 남긴다 — 행 = 호출 1:1.
#   어댑터에는 call_id · 라벨(= kind)을 env 로 넘긴다 — 독립 kind 는 런처를 거쳐 래퍼까지 이어진다
KIND="${1:--}" CALL_T0="$(date -u +%Y-%m-%dT%H:%M:%SZ)" CALL_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$-${RANDOM}"
LOCKP="" OWN_LOCK="" CHILD="" GOT_SIG="" PD="" ROUND_LEDGER="" ROUND_SLOT=""
on_exit() {
  local rc="$1" dir="${FZ_TELEMETRY_DIR:-${HOME:-}/.fz/telemetry}"
  if [ -n "$ROUND_SLOT" ]; then   # 라운드 끝맺음 — 소비 여부는 판정기가 rc 로 정한다
    python3 "$HERE/gpt_rounds.py" finish --ledger "$ROUND_LEDGER" --slot "$ROUND_SLOT" --rc "$rc" > /dev/null \
      || echo "GPT-CALL-WARN: 라운드 끝맺음 실패(slot $ROUND_SLOT) — 예약이 남아 다음 예약이 고아로 회수한다(이 판정은 세지 않는다)" >&2
  fi
  [ -n "$OWN_LOCK" ] && rm -rf "$LOCKP"
  [ -n "$PD" ] && rm -rf "$PD"
  if [ -d "$dir" ] && { [ -z "$CHILD" ] || ! grep -qF $'\t'"$CALL_ID"$'\t' "$dir/gpt-calls.tsv" 2>/dev/null; }; then
    printf '%s\t%s\t%s\t%s\t-\t-\t?\t?\t?\t-\t-\t%s\tgate\n' "$CALL_T0" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$CALL_ID" \
      "$(printf '%s' "$KIND" | tr '\t\n\r' '   ')" "$rc" >> "$dir/gpt-calls.tsv" 2>/dev/null || true
  fi
}
trap 'on_exit $?' EXIT
[ $# -ge 1 ] || die 10 "usage: gpt-call.sh KIND [--experimental] [inputs...]"
command -v python3 >/dev/null 2>&1 || die 11 "python3 없음 — resolver 를 돌릴 수 없다(측정 실패 · 0건 아님)"
command -v perl >/dev/null 2>&1 || die 11 "perl 없음 — 어댑터를 자기 프로세스 그룹에서 띄울 수 없다"

PD="$(mktemp -d "${TMPDIR:-/tmp}/fz-gpt-call.XXXXXX")" || die 11 "계획 폴더 생성 실패(mktemp)"

python3 "$HERE/gpt_kinds.py" resolve --plan-dir "$PD" "$@"; RC=$?
case "$RC" in 0|10|11) ;; *) echo "GPT-CALL-FAIL(11): resolver 가 계약 밖 종료 $RC 로 끝났다" >&2; RC=11 ;; esac

ADAPTER="" LOCK="" SESSION_IN="" ADAPTER_HOME="" CLEANUP_ISO=""
if [ -f "$PD/meta" ]; then
  while IFS= read -r line; do
    case "$line" in
      ADAPTER=*) ADAPTER="${line#ADAPTER=}" ;;
      LOCK=*) LOCK="${line#LOCK=}" ;;
      SESSION_IN=*) SESSION_IN="${line#SESSION_IN=}" ;;
      CODEX_HOME=*) ADAPTER_HOME="${line#CODEX_HOME=}" ;;
      CLEANUP_ISO=*) CLEANUP_ISO="${line#CLEANUP_ISO=}" ;;
    esac
  done < "$PD/meta"
fi

# 잠금 — 경로를 정규화한 뒤 원자적으로 잡는다(같은 OUT 의 다른 표기도 한 잠금). 상위 폴더 없음은 resolver 가 이미 10 으로 거부했다
if [ -n "$LOCK" ] && [ -d "$(dirname "$LOCK")" ]; then
  LOCKP="$(cd "$(dirname "$LOCK")" && pwd -P)/$(basename "$LOCK").lock"
  if mkdir "$LOCKP" 2>/dev/null; then OWN_LOCK=1
  else
    LOCKP=""
    [ "$RC" -ne 0 ] && exit "$RC"
    die 10 "같은 --out 이 이미 실행 중이다(또는 이전 실행의 잠금이 남았다): $(cd "$(dirname "$LOCK")" && pwd -P)/$(basename "$LOCK").lock"
  fi
fi

stale_cleanup() {   # 잠금 소유자만 — 옛 출력이 새 판정으로 읽히지 않게. --session-file 입력은 남긴다
  [ -n "$OWN_LOCK" ] || return 0
  rm -f "$LOCK"
  if [ -n "$SESSION_IN" ] && [ "$LOCK.session" -ef "$SESSION_IN" ]; then :; else rm -f "$LOCK.session"; fi
}
iso_cleanup() {     # E3 — verify-cross 가 이어 받은 격리 홈을 런처가 확인하고 지운다
  [ -n "$CLEANUP_ISO" ] || return 0
  bash "$HERE/gpt_independent.sh" cleanup --iso "$CLEANUP_ISO" >&2 || echo "GPT-CALL-WARN: 격리 홈 정리 실패: $CLEANUP_ISO" >&2
}

if [ "$RC" -ne 0 ]; then
  stale_cleanup; iso_cleanup
  exit "$RC"
fi
[ -f "$HERE/$ADAPTER" ] || { stale_cleanup; iso_cleanup; die 11 "어댑터 없음: $HERE/$ADAPTER"; }
if [ -f "$PD/compose.json" ]; then
  python3 "$HERE/gpt_kinds.py" compose --plan-dir "$PD" || { stale_cleanup; iso_cleanup; die 11 "프롬프트 합성 실패"; }
fi
# 재검증 라운드 상한(정본 modules/cross-validation.md § 재검증 라운드 상한 · 판정 scripts/gpt_rounds.py) — FZ_GPT_ARTIFACT 를 밝힌 호출만 센다.
#   여기서 예약하고(원장 잠금 안에서 검사 + 예약만) 어댑터는 잠금 밖에서 돈다. 끝맺음은 on_exit 다.
#   거부(19)는 다른 거부처럼 옛 OUT 을 지우되 ROUND-KEEP-OUT(같은 입력 · 이번 --out 이 직전 판정 파일)이면 남긴다 — 판정은 판정기 몫이다
if [ -n "${FZ_GPT_ARTIFACT:-}" ]; then
  ROUND_OUT="$(python3 "$HERE/gpt_rounds.py" reserve --owner-pid "$$" --call-id "$CALL_ID" -- "$@")"; ROUND_RC=$?
  ROUND_UNTRACKED="" ROUND_KEEP_OUT=""
  while IFS= read -r line; do
    case "$line" in
      ROUND-LEDGER=*) ROUND_LEDGER="${line#ROUND-LEDGER=}" ;;
      ROUND-SLOT=*) ROUND_SLOT="${line#ROUND-SLOT=}" ;;
      ROUND-UNTRACKED=*) ROUND_UNTRACKED=1 ;;
      ROUND-KEEP-OUT=1) ROUND_KEEP_OUT=1 ;;
    esac
  done <<< "$ROUND_OUT"
  case "$ROUND_RC" in
    0) { [ -n "$ROUND_SLOT" ] && [ -n "$ROUND_LEDGER" ]; } || [ -n "$ROUND_UNTRACKED" ] \
         || { ROUND_SLOT=""; stale_cleanup; iso_cleanup; die 11 "라운드 예약 결과가 비었다(판정기 exit 0): $ROUND_OUT"; } ;;
    19) [ -n "$ROUND_KEEP_OUT" ] || stale_cleanup; iso_cleanup; exit 19 ;;   # 거부 — 사유는 판정기가 stderr 에 남겼다
    10) stale_cleanup; iso_cleanup; exit 10 ;;                                # 사용법(FZ_GPT_ARTIFACT 값 · FZ_WORK_DIR 폴더 등)
    *) ROUND_SLOT=""; stale_cleanup; iso_cleanup; die 11 "라운드 원장 판정 실패(판정기 exit $ROUND_RC) — 측정 실패 · 0건 아님" ;;
  esac
fi
stale_cleanup

ARGV=()
while IFS= read -r -d '' a; do ARGV+=("$a"); done < "$PD/argv"
ENVP=()
[ -n "$ADAPTER_HOME" ] && ENVP=(env CODEX_HOME="$ADAPTER_HOME")

SELF_PG="$(/bin/ps -o pgid= -p $$ | tr -d ' ')"
desc_pgids() {   # $1 = 어댑터 pid → 그 자손 전체가 속한 프로세스 그룹(중복 없이). 런처는 래퍼를 자기 그룹 밖에 띄우므로
  #                 어댑터 그룹 하나만 죽이면 CLI 가 고아로 남는다 — 신호 전에 프로세스 표를 한 번 찍어 자손을 고른다
  /bin/ps -axo pid=,ppid=,pgid= | awk -v r="$1" -v self="$SELF_PG" '
    { pp[$1] = $2; pg[$1] = $3 }
    END { for (p in pp) { q = p; while ((q in pp) && q != r && q > 1) q = pp[q]; if (q == r && pg[p] != self) print pg[p] } }' | sort -u
}
PGS=""
fwd() {   # 신호를 어댑터 자손의 모든 프로세스 그룹에 TERM 으로 — 배경 작업은 INT 를 무시한 채 시작하므로 INT 를 그대로 넘기면 듣지 않는다
  GOT_SIG="$1"
  [ -n "$CHILD" ] || return 0
  PGS="$(desc_pgids "$CHILD")"
  for g in $PGS; do kill -TERM -- "-$g" 2>/dev/null; done
  ( sleep 3; for g in $PGS; do kill -KILL -- "-$g" 2>/dev/null; done ) >&- 2>&- &   # 호출자의 파이프를 붙잡지 않는다
}
trap 'fwd TERM' TERM; trap 'fwd INT' INT; trap 'fwd HUP' HUP

export FZ_GPT_CALL_ID="$CALL_ID" FZ_GPT_CALL_LABEL="$KIND"
# 런처 정책(R-06)의 env 채널 — 런처가 이 정문과 같은 resolver · 레지스트리에 묻게 한다(argv 는 그대로 · S0 golden)
export FZ_GPT_POLICY_ROOT="$(cd "$HERE/.." && pwd)"
perl -e 'setpgrp(0, 0); exec @ARGV or exit 11' ${ENVP[@]+"${ENVP[@]}"} bash "$HERE/$ADAPTER" "${ARGV[@]}" &
CHILD=$!
while :; do
  wait "$CHILD"; RC=$?
  kill -0 "$CHILD" 2>/dev/null || break       # 신호로 wait 가 먼저 돌아왔으면 자식이 끝날 때까지 다시 기다린다
done

if [ -n "$GOT_SIG" ]; then
  for g in $PGS; do kill -KILL -- "-$g" 2>/dev/null; done   # TERM 을 무시한 자손까지
  iso_cleanup
  case "$GOT_SIG" in TERM) exit 143 ;; INT) exit 130 ;; *) exit 129 ;; esac
fi
iso_cleanup
exit "$RC"
