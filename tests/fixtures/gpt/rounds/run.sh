#!/bin/bash
# GPT 재검증 라운드 상한 러너 (B7 · C-S05 · G-24 · F-508) — 정본 modules/cross-validation.md § 재검증 라운드 상한 · 판정 scripts/gpt_rounds.py
#   원장 케이스는 실제 정문(scripts/gpt-call.sh <kind>)을 기록 CLI(../_shim/codex 로 위임)로 돌린다 — 재는 것은 정문의 reserve · finish
#   배선과 호출 줄의 계열 선언이다(판정기 단위 케이스는 `python3 scripts/gpt_rounds.py --self-test` 몫).
#
# 케이스 — 케이스마다 한 줄 `<케이스>: PASS <설명>` 또는 `<케이스>: FAIL <사유>` · 끝 줄 `gpt-rounds: PASS|FAIL`
#   resume-new-shell        1라운드 뒤 새 셸(env -i · 다른 cwd)이 같은 FZ_WORK_DIR 로 부르면 2라운드다 — 원장이 셸을 넘어 이어진다
#   cross-skill             core § verify 레시피(여러 스킬이 같이 쓴다)를 그대로 돌린다 — 계열 · 작업 폴더는 호출자가 env 로 준다.
#                           fz-plan Phase 2(ARTIFACT=plan) · fz-review 5.5 verify-gates(code)는 한 작업 폴더 원장의 다른 키에 들고,
#                           fz-discover --deep(ARTIFACT= 빈 값)은 세지 않는다 · 계열 미정 · 센 호출의 작업 폴더 미정은 CLI 전에 멈춘다
#                           · 작업 폴더를 빈 값으로 밝힌 센 호출(Serena fallback)은 FZ_RUN_STATE 세션 원장에 센다
#   fourth-round-rejected   3라운드 뒤 4번째 검증 → exit 19 · stderr 'GPT-ROUNDS: budget-exhausted' · CLI 0 · 그 --out 없음 ·
#                           `gpt_rounds.py status` 가 그 키를 unresolved 로 보인다(미해결 — 통과 아님)
#   normal-rounds-2-3       verify ∥ verify-gates 를 동시에 띄워 라운드 1 · 2 · 3 마다 두 슬롯이 같은 라운드에 든다 ·
#                           2라운드 사후 대조 재호출(FZ_GPT_RECALL=post-check)은 그 라운드를 잇고 라운드를 쓰지 않는다
#   code-change-new-input   같은 프롬프트 · 같은 코드 → exit 19 same-input(stderr 에 직전 판정 파일 · CLI 0 · 그 파일 보존) ·
#                           검토 대상 코드만 바꾸면 새 라운드다
#   failed-call-no-consume  CLI 실패 · 스키마 위반 · GPT 미사용(18)은 슬롯을 비운다 — 뒤의 유효 판정이 1라운드다
#   last-slot-race          마지막 슬롯을 두 호출이 동시에 다투면 하나만 돈다(다른 하나 exit 19 budget-exhausted · CLI 는 한 호출분)
#   no-workdir              FZ_WORK_DIR 없이 FZ_RUN_STATE/<pipeline_id>/ 원장 + 발견 색인 한 줄 · 새 셸 · 다른 cwd 도 같은 원장
#   modernize-path          fz-modernize 호출 줄(modernize-verify · full 독립 플랜)이 계열 guide-plan 을 달고, § GPT 호출 블록을
#                           실제로 돌리면 원장에 guide-plan/verify 1라운드가 남는다
#   prompt-no-anchor        gpt-skills/**/*.md · templates/**/* · modules/fz-gpt-*.md 에 '이전 지적' 0줄 — 반영 대조는 Lead 몫(F-508) ·
#                           양성 대조: 같은 수집 · 같은 판정 함수로 'gpt-call.sh' 1줄 이상
#   default-independent     fz-plan full 2.7 이 플래그 없이 독립 플랜을 띄운다(계열 plan · 끄기 --no-gpt-independent · opt-in 0) ·
#                           tests/fixtures/plan-wiring/parallel-arms 러너가 그대로 통과한다
# ⛔ 실제 GPT CLI · 사용자 홈 · 사용자 선택을 건드리지 않는다 — PATH 에서 실제 CLI 가 든 폴더를 빼고 기록 CLI 를 앞에 붙인다.
#    HOME · CODEX_HOME · FZ_GPT_CHOICE_DIR · FZ_RUN_STATE · FZ_WORK_DIR · FZ_TELEMETRY_DIR · TMPDIR 은 임시다. 케이스가 정하지 않은
#    FZ_GPT_ARTIFACT · FZ_GPT_RECALL · FZ_GPT_ARTIFACT_VERSION · 세션 id(레시피 케이스는 호출자 변수 ARTIFACT · WORK_DIR 도)는
#    env -u 로 지우고, 케이스가 정하면 GENV(레시피는 인자)로 준다.
# ⛔ 음성 대조: 기준 트리(0e1353e — 라운드 판정기 · 호출 줄 계열 · 독립 플랜 기본 on 이 없다)에 이 러너를 얹어 돌리면
#    `gpt-rounds: FAIL` · exit 1 이어야 한다(충돌 · exit 2 아님 — 판정기가 없어도 케이스가 FAIL 로 끝난다).
# exit: 0=전건 통과(`gpt-rounds: PASS`) · 1=실패 있음(`gpt-rounds: FAIL`) · 2=준비 실패(UNRUN — PASS 아님)
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
{ [ -f "$ROOT/scripts/gpt-call.sh" ] && [ -f "$ROOT/tests/fixtures/gpt/_shim/codex" ]; } \
  || { echo "UNRUN  대상 트리에 정문 · 가짜 CLI 가 없다: $ROOT"; exit 2; }
for tool in python3 perl git; do
  command -v "$tool" >/dev/null 2>&1 || { echo "UNRUN  $tool 없음"; exit 2; }
done
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "UNRUN  mktemp 실패"; exit 2; }
T="$(cd "$T0" && pwd -P)" || { echo "UNRUN  임시 폴더 해석 실패"; exit 2; }
trap 'rm -rf "$T"' EXIT

# ── PATH — 실제 CLI 가 든 폴더를 빼고(bash · python3 · perl · git 은 남아야 한다) 기록 CLI 폴더를 앞에 붙인다
nocli_path() { local d out="" IFS=:; for d in $PATH; do [ -n "$d" ] && [ -x "$d/codex" ] && continue; out="${out:+$out:}$d"; done; printf '%s' "$out"; }
NOCLI="$(nocli_path)"
[ -z "$(PATH="$NOCLI"; command -v codex)" ] || { echo "UNRUN  CLI 없는 PATH 를 만들지 못했다"; exit 2; }
for tool in bash python3 perl git; do
  [ -n "$(PATH="$NOCLI"; command -v "$tool")" ] || { echo "UNRUN  CLI 없는 PATH 에 $tool 이 없다(같은 폴더)"; exit 2; }
done
# 기록 CLI — 불릴 때마다 한 줄. 기록 파일 경로를 스크립트에 박아 둔다(env -i 로 띄운 새 셸도 같은 파일에 쓴다)
CALLS="$T/calls.log"
mkdir -p "$T/fakebin" "$T/home/.codex" "$T/sel" "$T/tel" "$T/tmp"
cat > "$T/fakebin/codex" <<EOF
#!/bin/bash
printf '%s\n' "\$*" >> "$CALLS"
exec /bin/bash "$ROOT/tests/fixtures/gpt/_shim/codex" "\$@"
EOF
chmod +x "$T/fakebin/codex"
CLIPATH="$T/fakebin:$NOCLI"
[ "$(PATH="$CLIPATH"; command -v codex)" = "$T/fakebin/codex" ] || { echo "UNRUN  기록 CLI 가 PATH 앞에 오지 않는다"; exit 2; }

# ── 입력 — 검토 대상 저장소(커밋 없는 git) · 스키마를 통과하는 가짜 응답(gpt_review_schema · gate verdict)
REPO="$T/repo"
{ mkdir -p "$REPO" && git -C "$REPO" init -q 2>/dev/null && echo a > "$REPO/a.txt"; } || { echo "UNRUN  검토 대상 저장소를 만들지 못했다"; exit 2; }
VERIFY_JSON='{"schemaVersion":"1.1","review_id":"fixture","timestamp":"2026-09-29T00:00:00Z","review_type":"plan_validation","issues":[],"summary":{"total_issues":0,"by_severity":{"critical":0,"major":0,"minor":0,"suggestion":0},"by_category":""},"verdict":"approved","overall_feedback":"ok","strengths":[]}'
GATES_JSON='{"schemaVersion":"1.0","ledger":"plan.draft.md","gates":[],"summary":{"total":0,"accept":0,"revise":0,"demote_to_manual":0}}'

# 판독기 — 원장 · status JSON · 발견 색인을 한 줄로(없으면 no-file · no-key — 빈 값이 0 으로 읽히지 않게)
cat > "$T/led.py" <<'PY'
"""Runner reader: ledger (gpt-rounds.json) / status JSON / discovery index -> one line.
usage: led.py slots|live|byround|refusals LEDGER KEY | led.py status STATUS_JSON KEY | led.py index FZ_RUN_STATE -
Missing input prints no-file / no-key (never an empty value that could pass as zero)."""
import json
import os
import sys

mode, path, key = sys.argv[1], sys.argv[2], sys.argv[3]


def tag(s):
    return str(s.get("kind")) + (":recall" if s.get("recall") else "")


if mode == "index":
    try:
        with open(os.path.join(path, "gpt-rounds-index.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except (OSError, ValueError):
        print("no-file")
        sys.exit(0)
    paths = [r.get("ledger") for r in rows if isinstance(r, dict)]
    root = os.path.realpath(path) + os.sep
    one = paths[0] if len(paths) == 1 and isinstance(paths[0], str) else ""
    good = bool(one) and os.path.isfile(one) and os.path.realpath(one).startswith(root)
    print(one if good else "bad-index " + json.dumps(paths)[:160])
    sys.exit(0)
try:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
except (OSError, ValueError):
    print("no-file")
    sys.exit(0)
k = (data.get("keys") or {}).get(key) if isinstance(data, dict) else None
if not isinstance(k, dict):
    print("no-key")
    sys.exit(0)
if mode == "status":
    print("unresolved=%s rounds_used=%s" % (k.get("unresolved"), k.get("rounds_used")))
    sys.exit(0)
slots = sorted((s for s in k.get("slots") or [] if isinstance(s, dict)), key=lambda s: s.get("reserved_seq") or 0)
if mode == "slots":
    out = ",".join("%s:%s:%s" % (s.get("round"), tag(s), s.get("state")) for s in slots)
elif mode == "live":
    live = {s.get("round") for s in slots if s.get("state") in ("reserved", "completed")}
    out = ",".join(str(r) for r in sorted(x for x in live if isinstance(x, int)))
elif mode == "byround":
    rounds = {}
    for s in slots:
        if s.get("state") == "completed" and isinstance(s.get("round"), int):
            rounds.setdefault(s["round"], []).append(tag(s))
    out = ";".join("%d=%s" % (r, "+".join(sorted(v))) for r, v in sorted(rounds.items()))
else:
    out = ",".join("%s:%s" % (r.get("reason"), r.get("kind")) for r in k.get("refusals") or [] if isinstance(r, dict))
print(out or "empty")
PY

FAILS=0 WHY="" GCWD=""
GENV=()
verdict() {   # $1=케이스 · $2=실패 사유(빈 값 = 통과) · $3=통과 설명
  if [ -z "$2" ]; then echo "$1: PASS $3"; else echo "$1: FAIL $2"; FAILS=$((FAILS + 1)); fi
}
add() { WHY="${WHY:+$WHY; }$1"; }                        # 케이스 안의 실패 사유를 모은다 — 케이스 머리에서 WHY="" 로 비운다
want() { [ "$2" = "$3" ] || add "$1 '$2'(기대 '$3')"; }   # $1=무엇 · $2=실제 · $3=기대
ncalls() { if [ -f "$CALLS" ]; then wc -l < "$CALLS" | tr -d ' '; else echo 0; fi; }
rc() { cat "$T/g-$1.rc" 2>/dev/null || echo "?"; }
ncli() { cat "$T/g-$1.n" 2>/dev/null || echo "?"; }
etail() { [ -f "$T/g-$1.err" ] && tr '\n' ' ' < "$T/g-$1.err" | tail -c 200; }
prompt() { printf '# 과제 %s\n이 계획을 검증하라 — 고정 입력 %s\n' "$1" "$1" > "$T/p-$1.md"; }
led() { PYTHONDONTWRITEBYTECODE=1 python3 -B "$T/led.py" "$@" 2>/dev/null || echo "led-error"; }

# gate <태그> <kind> [입력...] — 정문 한 번(cwd = GCWD 또는 $T). 케이스 env 는 GENV(KEY=VALUE) — 라운드 env 는 먼저 지운다
#   → $T/g-<태그>.{out,err,rc,n} (n = 이 호출 동안 기록 CLI 가 불린 횟수 — 동시 호출이면 따로 센다)
gate() {
  local tag="$1" before after
  shift
  before="$(ncalls)"
  ( cd "${GCWD:-$T}" && env -u FZ_GPT_ARTIFACT -u FZ_GPT_RECALL -u FZ_GPT_ARTIFACT_VERSION -u FZ_WORK_DIR -u FZ_RUN_STATE \
      -u CLAUDE_CODE_SESSION_ID -u FZ_AUTONOMY -u CODEX_HOME -u FZ_GPT_CHOICE_DIR -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL \
      -u FZ_GPT_POLICY_ROOT -u FZ_GPT_IDLE_SEC -u FZ_SHIM_OUTPUT -u FZ_SHIM_EXIT -u FZ_SHIM_SLEEP \
      "PATH=$CLIPATH" "HOME=$T/home" "CODEX_HOME=$T/home/.codex" "FZ_GPT_CHOICE_DIR=$T/sel" "FZ_TELEMETRY_DIR=$T/tel" \
      "TMPDIR=$T/tmp" "FZ_RUN_STATE=$T/runs" "PYTHONDONTWRITEBYTECODE=1" ${GENV[@]+"${GENV[@]}"} \
      /bin/bash "$ROOT/scripts/gpt-call.sh" "$@" < /dev/null ) > "$T/g-$tag.out" 2> "$T/g-$tag.err"
  echo $? > "$T/g-$tag.rc"
  after="$(ncalls)"
  echo $((after - before)) > "$T/g-$tag.n"
}
# fresh <태그> <cwd> [KEY=VALUE...] -- <kind> [입력...] — 새 셸: env -i 로 시작해 넘긴 env 만 갖는다(앞 셸의 변수 · cwd 가 없다)
fresh() {
  local tag="$1" dir="$2"
  local -a kv
  kv=()
  shift 2
  while [ $# -gt 0 ] && [ "$1" != "--" ]; do kv+=("$1"); shift; done
  [ $# -gt 0 ] && shift
  ( env -i "PATH=$CLIPATH" "HOME=$T/home" "CODEX_HOME=$T/home/.codex" "FZ_GPT_CHOICE_DIR=$T/sel" "FZ_TELEMETRY_DIR=$T/tel" \
      "TMPDIR=$T/tmp" "PYTHONDONTWRITEBYTECODE=1" ${kv[@]+"${kv[@]}"} \
      /bin/bash -c 'cd "$1" && shift && exec /bin/bash "$@"' _ "$dir" "$ROOT/scripts/gpt-call.sh" "$@" < /dev/null ) \
    > "$T/g-$tag.out" 2> "$T/g-$tag.err"
  echo $? > "$T/g-$tag.rc"
}
# recipe <태그> <cwd> [KEY=VALUE...] — 꺼낸 core § verify 블록을 새 bash 로 돌린다. 호출자 변수(ARTIFACT · WORK_DIR · 출력 · 프롬프트
#   파일)는 넘긴 것만 있다 — 바깥 셸의 같은 이름은 지운다. → $T/g-<태그>.{out,err,rc,n}
recipe() {
  local tag="$1" dir="$2" before after
  shift 2
  before="$(ncalls)"
  ( cd "$dir" && env -u ARTIFACT -u WORK_DIR -u REVIEW_FILE -u P_VERIFY -u FZ_GPT_ARTIFACT -u FZ_GPT_RECALL -u FZ_GPT_ARTIFACT_VERSION \
      -u FZ_WORK_DIR -u CLAUDE_CODE_SESSION_ID -u FZ_AUTONOMY -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL -u FZ_GPT_POLICY_ROOT \
      -u FZ_GPT_IDLE_SEC -u FZ_SHIM_EXIT -u FZ_SHIM_SLEEP \
      "PATH=$CLIPATH" "HOME=$T/home" "CODEX_HOME=$T/home/.codex" "FZ_GPT_CHOICE_DIR=$T/sel" "FZ_TELEMETRY_DIR=$T/tel" \
      "TMPDIR=$T/tmp" "FZ_RUN_STATE=$T/runs" "PYTHONDONTWRITEBYTECODE=1" "FZ_PLUGIN_ROOT=$ROOT" "GIT_ROOT=$REPO" \
      "PLAN_CONTENT=PLAN-$tag" "AFFECTED_SYMBOLS=SYM-$tag" "FZ_SHIM_OUTPUT=$VERIFY_JSON" "$@" \
      /bin/bash "$T/verify-block.sh" < /dev/null ) > "$T/g-$tag.out" 2> "$T/g-$tag.err"
  echo $? > "$T/g-$tag.rc"
  after="$(ncalls)"
  echo $((after - before)) > "$T/g-$tag.n"
}

# ── resume-new-shell ───────────────────────────────────────────────
case_resume_new_shell() {
  local W="$T/w-resume" O="$T/o-resume" s=""
  WHY=""
  mkdir -p "$W" "$O"
  prompt resume-1; prompt resume-2
  GCWD=""
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
  gate resume-1 verify --cd "$REPO" --out "$O/v1.json" --prompt-file "$T/p-resume-1.md"
  fresh resume-2 "$T/tmp" "FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON" -- \
    verify --cd "$REPO" --out "$O/v2.json" --prompt-file "$T/p-resume-2.md"
  want "exit(첫 셸 · 새 셸)" "$(rc resume-1) $(rc resume-2)" "0 0"
  s="$(led slots "$W/gpt-rounds.json" plan/verify)"
  want "원장 plan/verify" "$s" "1:verify:completed,2:verify:completed"
  [ -z "$WHY" ] || add "stderr: $(etail resume-2)"
  verdict resume-new-shell "$WHY" "새 셸(env -i · 다른 cwd)이 같은 FZ_WORK_DIR 원장을 이어 2라운드다 — $s"
}

# ── cross-skill ────────────────────────────────────────────────────
# core § verify 블록(여러 스킬이 같이 쓰는 레시피)을 꺼내 그대로 돌린다 — 계열(ARTIFACT) · 작업 폴더(WORK_DIR)는 호출자 몫이다
case_cross_skill() {
  local W="$T/w-cross" O="$T/o-cross" pv="" cv="" res="" ev="" eidx=""
  WHY=""
  mkdir -p "$W" "$O" "$T/cwd-plan" "$T/cwd-discover" "$T/cwd-review"
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT/modules/fz-gpt-subcommands-core.md" "$T/verify-block.sh" > "$T/vb.out" 2> "$T/vb.err" <<'PY'
import sys
try:
    s = open(sys.argv[1], encoding="utf-8").read()
    i = s.index("## verify -- 계획 검증")
    j = s.index("```bash\n", i) + len("```bash\n")
    open(sys.argv[2], "w", encoding="utf-8").write(s[j:s.index("\n```", j)] + "\n")
    print("OK")
except (OSError, ValueError) as e:
    print("FAIL core § verify 블록을 꺼내지 못했다(%s)" % type(e).__name__)
PY
  res="$(head -1 "$T/vb.out" 2>/dev/null)"
  case "$res" in
    OK)
      recipe cs-plan "$T/cwd-plan" "ARTIFACT=plan" "WORK_DIR=$W" "REVIEW_FILE=$O/plan.json" "P_VERIFY=$T/p-cs-plan.md"
      recipe cs-discover "$T/cwd-discover" "ARTIFACT=" "WORK_DIR=$W" "REVIEW_FILE=$O/discover.json" "P_VERIFY=$T/p-cs-discover.md"
      recipe cs-unset "$T/cwd-discover" "WORK_DIR=$W" "REVIEW_FILE=$O/unset.json" "P_VERIFY=$T/p-cs-unset.md"
      recipe cs-nowd "$T/cwd-plan" "ARTIFACT=plan" "REVIEW_FILE=$O/nowd.json" "P_VERIFY=$T/p-cs-nowd.md"
      recipe cs-emptywd "$T/cwd-plan" "ARTIFACT=plan" "WORK_DIR=" "REVIEW_FILE=$O/emptywd.json" "P_VERIFY=$T/p-cs-emptywd.md" \
        "FZ_RUN_STATE=$T/runs-csempty" "CLAUDE_CODE_SESSION_ID=rounds-csempty-1"
      want "레시피 exit(fz-plan · fz-discover)" "$(rc cs-plan) $(rc cs-discover)" "0 0"
      case "$(rc cs-unset)" in 0|"?") add "ARTIFACT 를 정하지 않은 레시피가 exit $(rc cs-unset) — 가드가 CLI 전에 멈춰야 한다" ;; esac
      want "ARTIFACT 미정 CLI 호출" "$(ncli cs-unset)" 0
      case "$(rc cs-nowd)" in 0|"?") add "WORK_DIR 없이 센 레시피가 exit $(rc cs-nowd) — 원장이 세션 루트로 갈리지 않게 멈춰야 한다" ;; esac
      want "WORK_DIR 미정 CLI 호출" "$(ncli cs-nowd)" 0
      # Serena fallback — WORK_DIR 를 빈 값으로 밝힌 세는 호출은 돌고 세션 원장(FZ_RUN_STATE/<pipeline_id>)에 남는다
      want "WORK_DIR= 빈 값 레시피 exit" "$(rc cs-emptywd)" 0
      case "$(ncli cs-emptywd)" in 0|"?") add "WORK_DIR= 빈 값 레시피가 CLI 를 부르지 않았다" ;; esac
      eidx="$(led index "$T/runs-csempty" -)"
      case "$eidx" in
        /*) ev="$(led slots "$eidx" plan/verify)"; want "세션 원장 plan/verify" "$ev" "1:verify:completed" ;;
        *) add "WORK_DIR= 빈 값 호출의 세션 원장 색인 '$eidx'(FZ_RUN_STATE 아래 원장 한 줄이어야 한다)" ;;
      esac
      [ ! -e "$T/cwd-plan/gpt-rounds.json" ] || add "WORK_DIR= 빈 값 호출이 cwd 에 원장을 만들었다"
      ;;
    "FAIL "*) add "${res#FAIL }" ;;
    *) add "블록 추출기가 결과를 내지 못했다 — $(head -c 200 "$T/vb.err" 2>/dev/null | tr '\n' ' ')" ;;
  esac
  prompt cross-review
  GCWD="$T/cwd-review"      # fz-review 5.5 verify-gates — 산출물 계열 code · 같은 작업 폴더
  GENV=("FZ_GPT_ARTIFACT=code" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$GATES_JSON")
  gate cross-review verify-gates --cd "$REPO" --out "$O/review-gates.json" --prompt-file "$T/p-cross-review.md"
  GCWD=""
  want "fz-review verify-gates exit" "$(rc cross-review)" 0
  pv="$(led slots "$W/gpt-rounds.json" plan/verify)"
  cv="$(led slots "$W/gpt-rounds.json" code/verify)"
  want "plan/verify" "$pv" "1:verify:completed"
  want "code/verify" "$cv" "1:verify-gates:completed"
  [ -z "$WHY" ] || add "stderr: $(etail cs-plan) | $(etail cross-review)"
  verdict cross-skill "$WHY" "한 작업 폴더 원장에 fz-plan plan/verify($pv) · fz-review code/verify($cv) — fz-discover(빈 계열)는 세지 않고 계열 · 작업 폴더 미정 레시피는 CLI 전에 멈춘다 · WORK_DIR= 빈 값은 세션 원장($ev)"
}

# ── fourth-round-rejected ──────────────────────────────────────────
case_fourth_round_rejected() {
  local W="$T/w-four" O="$T/o-four" n st=""
  WHY=""
  mkdir -p "$W" "$O"
  GCWD=""
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
  for n in 1 2 3 4; do
    prompt "four-$n"
    gate "four-$n" verify --cd "$REPO" --out "$O/v$n.json" --prompt-file "$T/p-four-$n.md"
  done
  want "1~3라운드 exit" "$(rc four-1) $(rc four-2) $(rc four-3)" "0 0 0"
  want "4번째 exit" "$(rc four-4)" 19
  grep -qF 'GPT-ROUNDS: budget-exhausted' "$T/g-four-4.err" 2>/dev/null || add "4번째 stderr 에 'GPT-ROUNDS: budget-exhausted' 없음 — $(etail four-4)"
  want "4번째 CLI 호출" "$(ncli four-4)" 0
  [ ! -e "$O/v4.json" ] || add "거부된 호출의 --out 이 남았다(옛 결과를 새 판정으로 읽는다)"
  want "원장 live 라운드" "$(led live "$W/gpt-rounds.json" plan/verify)" "1,2,3"
  ( env -u FZ_WORK_DIR -u FZ_RUN_STATE -u FZ_GPT_ARTIFACT "HOME=$T/home" PYTHONDONTWRITEBYTECODE=1 \
      python3 -B "$ROOT/scripts/gpt_rounds.py" status --work-dir "$W" < /dev/null ) > "$T/four-status.json" 2> "$T/four-status.err"
  st="$(led status "$T/four-status.json" plan/verify)"
  want "status plan/verify" "$st" "unresolved=True rounds_used=3"
  verdict fourth-round-rejected "$WHY" "1~3라운드 0 · 4번째 exit 19 budget-exhausted · CLI 0 · --out 없음 · status $st"
}

# ── normal-rounds-2-3 ──────────────────────────────────────────────
case_normal_rounds_2_3() {
  local W="$T/w-normal" O="$T/o-normal" n br="" rcs=""
  WHY=""
  mkdir -p "$W" "$O"
  GCWD=""
  for n in 1 2 3; do
    prompt "nr-v$n"; prompt "nr-g$n"
    # Phase 2 병렬 계약 — verify ∥ verify-gates 를 동시에 띄우고 둘 다 끝난 뒤 판정한다
    GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
    gate "nr-v$n" verify --cd "$REPO" --out "$O/v$n.json" --prompt-file "$T/p-nr-v$n.md" &
    GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$GATES_JSON")
    gate "nr-g$n" verify-gates --cd "$REPO" --out "$O/g$n.json" --prompt-file "$T/p-nr-g$n.md" &
    wait
    rcs="$rcs $(rc "nr-v$n")/$(rc "nr-g$n")"
    if [ "$n" = 2 ]; then   # 사후 대조(--verdict-check) 실패를 가정한 재호출 1회 — 2라운드를 잇고 라운드를 쓰지 않는다
      GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_GPT_RECALL=post-check" "FZ_SHIM_OUTPUT=$GATES_JSON")
      gate nr-recall verify-gates --cd "$REPO" --out "$O/g2.json" --prompt-file "$T/p-nr-g2.md"
      rcs="$rcs recall=$(rc nr-recall)"
    fi
  done
  want "exit(verify/verify-gates · 재호출)" "$rcs" " 0/0 0/0 recall=0 0/0"
  br="$(led byround "$W/gpt-rounds.json" plan/verify)"
  want "라운드별 완료 슬롯" "$br" "1=verify+verify-gates;2=verify+verify-gates+verify-gates:recall;3=verify+verify-gates"
  want "live 라운드" "$(led live "$W/gpt-rounds.json" plan/verify)" "1,2,3"
  verdict normal-rounds-2-3 "$WHY" "라운드 1 · 2 · 3 마다 verify ∥ verify-gates 가 같은 라운드 · 2라운드 재호출(post-check)은 라운드를 쓰지 않는다 — $br"
}

# ── code-change-new-input ──────────────────────────────────────────
case_code_change_new_input() {
  local W="$T/w-cc" O="$T/o-cc" R2="$T/repo-cc" s=""
  WHY=""
  mkdir -p "$W" "$O" "$R2"
  git -C "$R2" init -q 2>/dev/null || add "git init 실패(측정 불가)"
  echo v1 > "$R2/src.txt"
  prompt cc
  GCWD=""
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
  gate cc-a verify --cd "$R2" --out "$O/a.json" --prompt-file "$T/p-cc.md"
  gate cc-b verify --cd "$R2" --out "$O/b.json" --prompt-file "$T/p-cc.md"
  echo v2 > "$R2/src.txt"   # 검토 대상 코드만 바뀌었다 — 프롬프트 · 산출물 버전은 그대로
  gate cc-c verify --cd "$R2" --out "$O/c.json" --prompt-file "$T/p-cc.md"
  want "첫 호출 exit" "$(rc cc-a)" 0
  want "같은 입력 exit" "$(rc cc-b)" 19
  grep -qF 'GPT-ROUNDS: same-input' "$T/g-cc-b.err" 2>/dev/null || add "같은 입력 stderr 에 'GPT-ROUNDS: same-input' 없음 — $(etail cc-b)"
  grep -qF "$O/a.json" "$T/g-cc-b.err" 2>/dev/null || add "같은 입력 stderr 가 직전 판정 파일($O/a.json)을 가리키지 않는다"
  want "같은 입력 CLI 호출" "$(ncli cc-b)" 0
  [ -s "$O/a.json" ] || add "직전 판정 파일이 사라졌다(그 판정이 답이다)"
  want "코드 변경 뒤 exit" "$(rc cc-c)" 0
  s="$(led slots "$W/gpt-rounds.json" plan/verify)"
  want "원장 plan/verify" "$s" "1:verify:completed,2:verify:completed"
  want "거부 기록" "$(led refusals "$W/gpt-rounds.json" plan/verify)" "same-input:verify"
  verdict code-change-new-input "$WHY" "같은 프롬프트 · 같은 코드 → exit 19 same-input(직전 판정 파일 · CLI 0) · 코드만 바꾸면 새 라운드 — $s"
}

# ── failed-call-no-consume ─────────────────────────────────────────
case_failed_call_no_consume() {
  local W="$T/w-fail" O="$T/o-fail" s=""
  WHY=""
  mkdir -p "$W" "$O"
  prompt fc-net; prompt fc-schema; prompt fc-off; prompt fc-ok
  GCWD=""
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON" "FZ_SHIM_EXIT=1")   # CLI 실패(통신 실패 대역)
  gate fc-net verify --cd "$REPO" --out "$O/net.json" --prompt-file "$T/p-fc-net.md"
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" 'FZ_SHIM_OUTPUT={"bad":1}')                    # 스키마 위반
  gate fc-schema verify --cd "$REPO" --out "$O/schema.json" --prompt-file "$T/p-fc-schema.md"
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
  gate fc-off verify --cd "$REPO" --out "$O/off.json" --prompt-file "$T/p-fc-off.md" --model off   # GPT 미사용(18) — 실패도 아니다
  gate fc-ok verify --cd "$REPO" --out "$O/ok.json" --prompt-file "$T/p-fc-ok.md"
  case "$(rc fc-net)" in 0|18|19|"?") add "CLI 실패 exit $(rc fc-net) — 측정 실패(10~17)여야 한다" ;; esac
  case "$(rc fc-schema)" in 0|18|19|"?") add "스키마 위반 exit $(rc fc-schema) — 측정 실패(10~17)여야 한다" ;; esac
  want "GPT 미사용 exit" "$(rc fc-off)" 18
  want "유효 판정 exit" "$(rc fc-ok)" 0
  s="$(led slots "$W/gpt-rounds.json" plan/verify)"
  want "원장 plan/verify" "$s" "1:verify:failed,1:verify:failed,1:verify:aborted,1:verify:completed"
  want "live 라운드" "$(led live "$W/gpt-rounds.json" plan/verify)" "1"
  verdict failed-call-no-consume "$WHY" "CLI 실패 exit $(rc fc-net) · 스키마 위반 exit $(rc fc-schema) · GPT 미사용 18 은 슬롯을 비우고 뒤의 유효 판정이 1라운드다 — $s"
}

# ── last-slot-race ─────────────────────────────────────────────────
case_last_slot_race() {
  local W="$T/w-race" O="$T/o-race" before after one pair="" s=""
  WHY=""
  mkdir -p "$W" "$O"
  prompt lr-1; prompt lr-2; prompt lr-a; prompt lr-b
  GCWD=""
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
  gate lr-1 verify --cd "$REPO" --out "$O/v1.json" --prompt-file "$T/p-lr-1.md"
  gate lr-2 verify --cd "$REPO" --out "$O/v2.json" --prompt-file "$T/p-lr-2.md"
  one="$(ncli lr-1)"
  # 마지막(3번째) 슬롯을 둘이 동시에 — 이긴 쪽 CLI 가 2초 머물러 진 쪽이 예약하는 동안 그 슬롯은 reserved 다
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_WORK_DIR=$W" "FZ_SHIM_OUTPUT=$VERIFY_JSON" "FZ_SHIM_SLEEP=2")
  before="$(ncalls)"
  gate lr-a verify --cd "$REPO" --out "$O/va.json" --prompt-file "$T/p-lr-a.md" &
  gate lr-b verify --cd "$REPO" --out "$O/vb.json" --prompt-file "$T/p-lr-b.md" &
  wait
  after="$(ncalls)"
  pair="$(printf '%s\n%s\n' "$(rc lr-a)" "$(rc lr-b)" | sort | tr '\n' ' ')"
  want "앞 두 라운드 exit" "$(rc lr-1) $(rc lr-2)" "0 0"
  want "동시 두 호출 exit(정렬)" "$pair" "0 19 "
  cat "$T/g-lr-a.err" "$T/g-lr-b.err" 2>/dev/null | grep -qF 'GPT-ROUNDS: budget-exhausted' || add "진 쪽 stderr 에 'GPT-ROUNDS: budget-exhausted' 없음"
  want "동시 구간 CLI 호출(한 호출분)" "$((after - before))" "$one"
  s="$(led slots "$W/gpt-rounds.json" plan/verify)"
  want "원장 plan/verify" "$s" "1:verify:completed,2:verify:completed,3:verify:completed"
  want "거부 기록" "$(led refusals "$W/gpt-rounds.json" plan/verify)" "budget-exhausted:verify"
  verdict last-slot-race "$WHY" "마지막 슬롯을 둘이 다투면 하나만 돈다(exit ${pair} · CLI $((after - before))회) — $s"
}

# ── no-workdir ─────────────────────────────────────────────────────
case_no_workdir() {
  local S="$T/runs-nowd" O="$T/o-nowd" sid="rounds-nowd-1" idx="" s="" d
  WHY=""
  mkdir -p "$O" "$T/cwd-nowd-a" "$T/cwd-nowd-b"
  prompt nw-1; prompt nw-2
  GCWD="$T/cwd-nowd-a"
  GENV=("FZ_GPT_ARTIFACT=plan" "FZ_RUN_STATE=$S" "CLAUDE_CODE_SESSION_ID=$sid" "FZ_SHIM_OUTPUT=$VERIFY_JSON")
  gate nw-1 verify --cd "$REPO" --out "$O/v1.json" --prompt-file "$T/p-nw-1.md"
  GCWD=""
  fresh nw-2 "$T/cwd-nowd-b" "FZ_GPT_ARTIFACT=plan" "FZ_RUN_STATE=$S" "CLAUDE_CODE_SESSION_ID=$sid" "FZ_SHIM_OUTPUT=$VERIFY_JSON" -- \
    verify --cd "$REPO" --out "$O/v2.json" --prompt-file "$T/p-nw-2.md"
  want "exit(첫 셸 · 새 셸)" "$(rc nw-1) $(rc nw-2)" "0 0"
  idx="$(led index "$S" -)"
  case "$idx" in
    /*) s="$(led slots "$idx" plan/verify)"
        want "원장 plan/verify" "$s" "1:verify:completed,2:verify:completed" ;;
    *) add "발견 색인 '$idx'(FZ_RUN_STATE 아래 실재하는 원장 한 줄이어야 한다)" ;;
  esac
  for d in "$T/cwd-nowd-a" "$T/cwd-nowd-b" "$REPO"; do
    [ ! -e "$d/gpt-rounds.json" ] || add "작업 폴더 없이 $d 에 원장이 생겼다"
  done
  verdict no-workdir "$WHY" "FZ_WORK_DIR 없이 FZ_RUN_STATE 아래 원장 1개(색인 1줄) · 새 셸 · 다른 cwd 도 같은 원장 — $s"
}

# ── modernize-path ─────────────────────────────────────────────────
case_modernize_path() {
  local F="$ROOT/skills/fz-modernize/SKILL.md" W="$T/w-mod" s="" res=""
  WHY=""
  mkdir -p "$W"
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$F" "$T/mod-block.sh" > "$T/mod.out" 2> "$T/mod.err" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
try:
    text = open(src, encoding="utf-8").read()
except OSError as e:
    print("FAIL skills/fz-modernize/SKILL.md 를 읽지 못했다(%s)" % type(e).__name__)
    sys.exit(0)
lines = text.split("\n")
why = []


def calls(kind):
    rx = re.compile(r'gpt-call\.sh["\']?\s+' + kind + r'(?![-\w])')
    return [ln for ln in lines if rx.search(ln)]


def family(ln):
    head = ln[:ln.find("gpt-call.sh")]
    return "FZ_GPT_ARTIFACT=guide-plan" in head and "FZ_WORK_DIR=" in head


for kind in ("modernize-verify", "independent-plan"):
    got = calls(kind)
    if len(got) != 1:
        why.append("%s 호출 줄이 %d개다(1 이어야 한다)" % (kind, len(got)))
    elif not family(got[0]):
        why.append("%s 호출 줄에 FZ_GPT_ARTIFACT=guide-plan · FZ_WORK_DIR= 가 없다" % kind)
h = text.find("### GPT 호출")
b = text.find("```bash\n", h) if h >= 0 else -1
e = text.find("\n```", b + 8) if b >= 0 else -1
if b < 0 or e < 0:
    why.append("### GPT 호출 의 bash 블록이 없다")
else:
    open(dst, "w", encoding="utf-8").write(text[b + 8:e] + "\n")
print(("FAIL " + " · ".join(why)) if why else "PASS")
PY
  res="$(head -1 "$T/mod.out" 2>/dev/null)"
  case "$res" in
    PASS) ;;
    "FAIL "*) add "${res#FAIL }" ;;
    *) add "판정기가 결과를 내지 못했다 — $(head -c 200 "$T/mod.err" 2>/dev/null | tr '\n' ' ')" ;;
  esac
  if [ -s "$T/mod-block.sh" ]; then
    printf '# Plan v1\n- guides/x.md 1줄 갱신\n' > "$T/mod-plan.md"
    sed -e "s#{WORK_DIR}#$W#g" -e "s#{PLAN_PATH}#$T/mod-plan.md#g" -e "s#{N}#1#g" "$T/mod-block.sh" > "$T/mod-run.sh"
    ( cd "$T" && env -u FZ_GPT_ARTIFACT -u FZ_GPT_RECALL -u FZ_GPT_ARTIFACT_VERSION -u FZ_WORK_DIR -u FZ_RUN_STATE \
        -u CLAUDE_CODE_SESSION_ID -u FZ_AUTONOMY -u CODEX_HOME -u FZ_GPT_CHOICE_DIR -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL \
        -u FZ_GPT_POLICY_ROOT -u FZ_GPT_IDLE_SEC -u FZ_SHIM_EXIT -u FZ_SHIM_SLEEP \
        "PATH=$CLIPATH" "HOME=$T/home" "CODEX_HOME=$T/home/.codex" "FZ_GPT_CHOICE_DIR=$T/sel" "FZ_TELEMETRY_DIR=$T/tel" \
        "TMPDIR=$T/tmp" "FZ_RUN_STATE=$T/runs" "PYTHONDONTWRITEBYTECODE=1" "FZ_PLUGIN_ROOT=$ROOT" "FZ_SHIM_OUTPUT=$VERIFY_JSON" \
        /bin/bash "$T/mod-run.sh" < /dev/null ) > "$T/g-mod.out" 2> "$T/g-mod.err"
    echo $? > "$T/g-mod.rc"
    want "fz-modernize GPT 호출 블록 exit" "$(rc mod)" 0
    s="$(led slots "$W/gpt-rounds.json" guide-plan/verify)"
    want "원장 guide-plan/verify" "$s" "1:modernize-verify:completed"
    [ -z "$WHY" ] || add "stderr: $(etail mod)"
  fi
  verdict modernize-path "$WHY" "fz-modernize 호출 줄(modernize-verify · 독립 플랜)이 guide-plan 을 달고 · § GPT 호출 블록을 돌리면 원장에 $s"
}

# ── prompt-no-anchor ───────────────────────────────────────────────
# 양성 대조는 같은 수집 · 같은 판정 함수로 센다 — 손으로 쓴 문자열 대조는 수집이 틀려도 통과한다
case_prompt_no_anchor() {
  local res=""
  WHY=""
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" > "$T/anchor.out" 2> "$T/anchor.err" <<'PY'
import glob, os, sys
root = sys.argv[1]
NEEDLE = "이전 지적"
CONTROL = "gpt-call.sh"   # 대상 안에 반드시 있는 토큰(modules/fz-gpt-*.md 의 정문 호출)
groups = {
    "gpt-skills/**/*.md": glob.glob(os.path.join(root, "gpt-skills", "**", "*.md"), recursive=True),
    "templates/**/*": [p for p in glob.glob(os.path.join(root, "templates", "**", "*"), recursive=True) if os.path.isfile(p)],
    "modules/fz-gpt-*.md": glob.glob(os.path.join(root, "modules", "fz-gpt-*.md")),
}
why = ["%s 대상 0개 — 측정 실패(0 은 통과가 아니다)" % g for g, fs in groups.items() if not fs]
bodies = []
for g, fs in groups.items():
    for p in sorted(fs):
        rel = os.path.relpath(p, root)
        try:
            bodies.append((rel, open(p, encoding="utf-8", errors="replace").read().split("\n")))
        except OSError as e:
            why.append("%s 를 읽지 못했다(%s)" % (rel, type(e).__name__))


def grep(needle):
    return ["%s:%d" % (rel, i) for rel, body in bodies for i, ln in enumerate(body, 1) if needle in ln]


control = grep(CONTROL)
if not control:
    why.append("양성 대조 '%s' 0줄 — 같은 수집 · 같은 판정이 아는 토큰도 못 찾는다(측정 실패)" % CONTROL)
hits = grep(NEEDLE)
if hits:
    why.append("'%s' %d줄: %s" % (NEEDLE, len(hits), ", ".join(hits[:5])))
n_lines = sum(len(body) for _, body in bodies)
if why:
    print("FAIL " + " · ".join(why))
else:
    print("PASS 파일 %d개 · %d줄에서 '%s' 0줄 · 대조 '%s' %d줄" % (len(bodies), n_lines, NEEDLE, CONTROL, len(control)))
PY
  res="$(head -1 "$T/anchor.out" 2>/dev/null)"
  case "$res" in
    "PASS "*) verdict prompt-no-anchor "" "${res#PASS }" ;;
    "FAIL "*) verdict prompt-no-anchor "${res#FAIL }" "" ;;
    *) verdict prompt-no-anchor "판정기가 결과를 내지 못했다 — $(head -c 200 "$T/anchor.err" 2>/dev/null | tr '\n' ' ')" "" ;;
  esac
}

# ── default-independent ────────────────────────────────────────────
case_default_independent() {
  local res="" arc arms="$ROOT/tests/fixtures/plan-wiring/parallel-arms/run.sh"
  WHY=""
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" > "$T/indep.out" 2> "$T/indep.err" <<'PY'
import glob, os, re, sys
root = sys.argv[1]
d = os.path.join(root, "skills", "fz-plan")
pages = [os.path.join(d, "SKILL.md")] + sorted(glob.glob(os.path.join(d, "references", "*.md")))
why, text = [], {}
for p in pages:
    try:
        text[p] = open(p, encoding="utf-8").read()
    except OSError as e:
        why.append("%s 를 읽지 못했다(%s)" % (os.path.relpath(p, root), type(e).__name__))
lines = text.get(pages[0], "").split("\n")
OPTIN = re.compile(r"(?<!no-)--gpt-independent")
launch = [ln for ln in lines if re.search(r"gpt-call\.sh[\"']?\s+independent-plan\s+--", ln)]
if len(launch) != 1:
    why.append("2.7 독립 플랜 기동 줄이 %d개다(1 이어야 한다)" % len(launch))
else:
    ln = launch[0]
    if "FZ_GPT_ARTIFACT=plan" not in ln[:ln.find("gpt-call.sh")]:
        why.append("기동 줄에 FZ_GPT_ARTIFACT=plan 이 없다")
    if "기본 off" in ln or OPTIN.search(ln):
        why.append("기동 줄이 아직 opt-in 이다")
    if "--no-gpt-independent" not in ln:
        why.append("기동 줄에 끄는 플래그(--no-gpt-independent)가 없다")
optin = ["%s:%d" % (os.path.relpath(p, root), i) for p, t in text.items()
         for i, ln in enumerate(t.split("\n"), 1) if OPTIN.search(ln)]
if optin:
    why.append("opt-in 플래그 --gpt-independent 가 남았다: " + ", ".join(optin[:4]))
hint = next((ln for ln in lines if ln.startswith("argument-hint:")), "")
if "--no-gpt-independent" not in hint:
    why.append("argument-hint 에 --no-gpt-independent 가 없다")
print(("FAIL " + " · ".join(why)) if why else "PASS")
PY
  res="$(head -1 "$T/indep.out" 2>/dev/null)"
  case "$res" in
    PASS) ;;
    "FAIL "*) add "${res#FAIL }" ;;
    *) add "판정기가 결과를 내지 못했다 — $(head -c 200 "$T/indep.err" 2>/dev/null | tr '\n' ' ')" ;;
  esac
  if [ -f "$arms" ]; then
    env -u FZ_GPT_ARTIFACT -u FZ_GPT_RECALL -u FZ_GPT_ARTIFACT_VERSION -u FZ_WORK_DIR -u FZ_RUN_STATE bash "$arms" < /dev/null > "$T/arms.out" 2>&1
    arc=$?
    [ "$arc" = 0 ] || add "parallel-arms 회귀(exit $arc) — $(grep -m1 '^FAIL' "$T/arms.out" 2>/dev/null | head -c 200)"
  else
    add "parallel-arms 러너가 없다(tests/fixtures/plan-wiring/parallel-arms/run.sh)"
  fi
  verdict default-independent "$WHY" "fz-plan full 2.7 이 플래그 없이 독립 플랜을 띄운다(계열 plan · 끄기 --no-gpt-independent · opt-in 문구 0) · parallel-arms 통과"
}

# ── 실행 — 케이스는 CASES 의 순서대로 돈다(이름은 릴리즈 게이트가 grep 한다)
CASES=(case_resume_new_shell case_cross_skill case_fourth_round_rejected case_normal_rounds_2_3 case_code_change_new_input
       case_failed_call_no_consume case_last_slot_race case_no_workdir case_modernize_path case_prompt_no_anchor case_default_independent)
for c in "${CASES[@]}"; do "$c"; done
echo
if [ "$FAILS" -eq 0 ]; then
  echo "gpt-rounds: PASS"
  exit 0
fi
echo "gpt-rounds: FAIL"
exit 1
