#!/bin/bash
# GPT 단계 실행 판정 러너 (B2a · F-487 · F-509) — 소비 문서가 GPT 단계 직전에 부르는 `gpt-choice.sh decide` 의 계약,
#   격리 폴더 자리 가드(gpt_independent.sh exit 11 — GPT 호출 전), 소비 스킬의 공통 판정 배선을 본다.
#   정본: modules/gpt-strategy.md § 단계 실행 판정 · § 독립 런처
#
# 케이스 — CASES 배열의 함수 하나가 케이스 하나다(B2b 가 contract-order · contract-regen 을 같은 배열에 더한다).
#   케이스마다 한 줄: `<케이스>: PASS <설명>` 또는 `<케이스>: FAIL <사유>`
#   same-input-twice          세션 상태 다섯(선택 off · 선택 있음 · 선택 없음 + 자율 · 선택 없음 + 대화 · CLI 없음)마다 decide 를 두 번 돌려
#                             같은 줄 · 같은 exit 인지, 기대 매핑(skip 18 off-user · run 0 · config 0 · ask 3 · skip 18 off-no-cli)인지 본다
#   tmpdir-claude-zero-calls  TMPDIR=<임시 홈>/.claude/x(있는 폴더)에서 정문 `gpt-call.sh independent-plan` → exit 11 · ~/.claude 메시지 ·
#                             기록 CLI 호출 0 · 격리 폴더 미생성. GPT 홈 · 인증은 갖춰 둔다(다른 11 사유로 통과하지 않게)
#   all-consumers-use-common  GPT kind 를 실제로 부르는 스킬(`gpt_kinds.py callers` 의 JSON — kinds-callers 와 같은 판독기)마다
#                             decide 또는 § 단계 실행 판정을 가리킨다 · fz-fix 에 `--gpt` opt-in 이 없다 · gpt-strategy 에 정본 절이 있다
#   contract-order            fz-plan full 순서(B2b · F-468) — skills/fz-plan/SKILL.md 에서 각 토큰이 처음 나오는 줄이 이 순서다:
#                             독립 플랜 기동(`gpt-call.sh independent-plan`) < `Workflow({ scriptPath:` < 방향 · 완주 정지(RECONSIDER · degraded 한 줄)
#                             < `plan_divergence.py` < Sprint Contract 단계(`directionVerdict` 한 줄) < 재생성(`--from-plan`) < Phase 2 절의 `verify-gates`
#                             · 그리고 tests/fixtures/plan-wiring/parallel-arms 러너가 그대로 통과한다
#   contract-regen            modules/sprint-contract.md 에 재생성 규칙 줄(`--from-plan` · plan-v · RTM · 원장)이 정확히 1개 · TEAM 발동 줄 0 ·
#                             입력 줄이 잠정 플랜 + `directionVerdict` · fz-plan 의 Sprint Contract 단계 줄이 그 모듈을 가리키고 TEAM 기준 줄이 없다 ·
#                             modules/cross-validation.md 의 방향성 검증 · 교훈 회상 · Sprint Contract 행에 TEAM 으로 시작하는 칸이 없다(그 표의 다른 행은 범위 밖)
# ⛔ 한계(all-consumers-use-common): 스킬 단위다 — SKILL.md + references 어디든 decide · § 단계 실행 판정이 한 번만 있어도 통과한다.
#    그래서 자리별 회귀(예: fz-review 5.5 의 decide 줄만 지움)와 modules/ 쪽 GPT 자리(peer-review-tiers.md Tier 1 등)는 잡지 못한다 —
#    호출 줄마다의 근접 검사는 B2b 몫이다
# ⛔ 실제 GPT CLI · 사용자 홈 · 사용자 선택을 건드리지 않는다 — PATH 에서 실제 CLI 가 든 폴더를 빼고 기록 CLI(../_shim/codex 로 위임)를
#    앞에 붙인다. HOME · CODEX_HOME · FZ_GPT_CHOICE_DIR · FZ_TELEMETRY_DIR · TMPDIR 은 임시이고 FZ_AUTONOMY · 세션 id 는 명시한다.
# ⛔ 음성 대조: 기준 트리(0e1353e — decide · 격리 폴더 자리 가드 · 공통 판정 배선 · Contract 순서가 없다)에 이 러너를 얹어 돌리면
#    `gpt-branch: FAIL` · exit 1 이어야 한다(충돌 · exit 2 아님).
# exit: 0=전건 통과(`gpt-branch: PASS`) · 1=실패 있음(`gpt-branch: FAIL`) · 2=준비 실패(UNRUN — PASS 아님)
set -u
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
{ [ -f "$ROOT/scripts/gpt-choice.sh" ] && [ -f "$ROOT/scripts/gpt-call.sh" ] && [ -f "$ROOT/scripts/gpt_independent.sh" ] \
  && [ -f "$ROOT/tests/fixtures/gpt/_shim/codex" ]; } || { echo "UNRUN  대상 트리에 scripts · 가짜 CLI 가 없다: $ROOT"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "UNRUN  python3 없음"; exit 2; }
# ⛔ mktemp 결과를 따로 받는다 — `cd "$(mktemp -d)"` 는 mktemp 가 실패해도 `cd ""` 가 성공해(bash 3.2) 현재 폴더를 지운다
T0="$(mktemp -d)" || { echo "UNRUN  mktemp 실패"; exit 2; }
T="$(cd "$T0" && pwd -P)" || { echo "UNRUN  임시 폴더 해석 실패"; exit 2; }
trap 'rm -rf "$T"' EXIT

# ── PATH — 실제 CLI 가 든 폴더를 뺀다(bash · python3 · perl 은 남아야 한다). 'CLI 있음' 은 그 앞에 기록 CLI 폴더를 붙인다
nocli_path() { local d out="" IFS=:; for d in $PATH; do [ -n "$d" ] && [ -x "$d/codex" ] && continue; out="${out:+$out:}$d"; done; printf '%s' "$out"; }
NOCLI="$(nocli_path)"
[ -z "$(PATH="$NOCLI"; command -v codex)" ] || { echo "UNRUN  CLI 없는 PATH 를 만들지 못했다"; exit 2; }
{ [ -n "$(PATH="$NOCLI"; command -v bash)" ] && [ -n "$(PATH="$NOCLI"; command -v python3)" ] && [ -n "$(PATH="$NOCLI"; command -v perl)" ]; } \
  || { echo "UNRUN  CLI 없는 PATH 에 bash · python3 · perl 이 없다(같은 폴더)"; exit 2; }
# 기록 CLI — 불릴 때마다 한 줄. 기록 파일 경로를 스크립트에 박아 둔다(런처가 HOME · CODEX_HOME 을 바꿔도 같은 파일이다)
CALLS="$T/calls.log"
mkdir -p "$T/fakebin"
cat > "$T/fakebin/codex" <<EOF
#!/bin/bash
printf '%s\n' "\$*" >> "$CALLS"
exec /bin/bash "$ROOT/tests/fixtures/gpt/_shim/codex" "\$@"
EOF
chmod +x "$T/fakebin/codex"
CLIPATH="$T/fakebin:$NOCLI"
[ "$(PATH="$CLIPATH"; command -v codex)" = "$T/fakebin/codex" ] || { echo "UNRUN  기록 CLI 가 PATH 앞에 오지 않는다"; exit 2; }

FAILS=0 WHY=""
verdict() {   # $1=케이스 · $2=실패 사유(빈 값 = 통과) · $3=통과 설명
  if [ -z "$2" ]; then echo "$1: PASS $3"; else echo "$1: FAIL $2"; FAILS=$((FAILS + 1)); fi
}
add() { WHY="${WHY:+$WHY; }$1"; }   # 케이스 안의 실패 사유를 모은다 — 케이스 머리에서 WHY="" 로 비운다

# ── same-input-twice ───────────────────────────────────────────────
dec() {   # $1=이름 · $2=PATH · $3=세션 id · $4=FZ_AUTONOMY('-'=unset) — decide 한 번 → $T/d-<이름>.{out,err,rc}
  local e
  e=(env -u FZ_AUTONOMY -u CLAUDE_CODE_SESSION_ID -u CODEX_HOME -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL -u FZ_GPT_POLICY_ROOT
     "PATH=$2" "HOME=$T/home" "CODEX_HOME=$T/home/.codex" "FZ_GPT_CHOICE_DIR=$T/sel" "FZ_TELEMETRY_DIR=$T/tel" "TMPDIR=$T/tmp"
     "CLAUDE_CODE_SESSION_ID=$3")
  [ "$4" = "-" ] || e+=("FZ_AUTONOMY=$4")
  "${e[@]}" /bin/bash "$ROOT/scripts/gpt-choice.sh" decide < /dev/null > "$T/d-$1.out" 2> "$T/d-$1.err"
  echo $? > "$T/d-$1.rc"
}
case_same_input_twice() {
  local sub kind sid auto want wrc p a b
  WHY=""
  mkdir -p "$T/home/.codex" "$T/sel" "$T/tel" "$T/tmp"
  printf 'model=off\neffort=off\n' > "$T/sel/br-off"
  printf 'model=m-branch\neffort=high\n' > "$T/sel/br-set"
  # 상태|PATH|세션 id|FZ_AUTONOMY|기대 stdout|기대 exit — 선택 없음 세 상태(auto · ask · nocli)는 선택 파일을 두지 않는다
  while IFS='|' read -r sub kind sid auto want wrc; do
    [ -n "$sub" ] || continue
    p="$CLIPATH"; [ "$kind" = "nocli" ] && p="$NOCLI"
    dec "$sub-1" "$p" "$sid" "$auto"; dec "$sub-2" "$p" "$sid" "$auto"
    a="$(cat "$T/d-$sub-1.out")|$(cat "$T/d-$sub-1.rc")"
    b="$(cat "$T/d-$sub-2.out")|$(cat "$T/d-$sub-2.rc")"
    [ "$a" = "$b" ] || add "$sub: 두 번이 다르다('$a' ≠ '$b')"
    [ "$a" = "$want|$wrc" ] || add "$sub: 기대 '$want|$wrc' · 실제 '$a'"
  done <<'TAB'
off|cli|br-off|-|GPT-DECIDE skip reason=off-user|18
set|cli|br-set|-|GPT-DECIDE run model=m-branch effort=high|0
auto|cli|br-auto|autonomous|GPT-DECIDE config|0
ask|cli|br-ask|-|GPT-DECIDE ask|3
nocli|nocli|br-nocli|-|GPT-DECIDE skip reason=off-no-cli|18
TAB
  verdict same-input-twice "$WHY" "다섯 상태 × 2회 같은 줄 · 같은 exit — off→skip 18 · 선택→run 0 · 자율→config 0 · 대화→ask 3 · CLI 없음→skip 18"
}

# ── tmpdir-claude-zero-calls ───────────────────────────────────────
case_tmpdir_claude_zero_calls() {
  local h="$T/th" d="$T/tc" rc n iso
  WHY=""
  mkdir -p "$h/.codex" "$h/.claude/x" "$d/out" "$d/tel" "$d/repo"
  echo '{"fake":"auth"}' > "$h/.codex/auth.json"
  printf 'model = "fake-cfg"\nmodel_reasoning_effort = "low"\n' > "$h/.codex/config.toml"
  printf '# 요구\n격리 폴더 자리 가드 BRANCH-REQ-1\n' > "$d/requirement.md"
  : > "$CALLS"
  # 선택 없음 + 자율(get 4) — GPT 미사용 사전 게이트(18)를 지나 격리 폴더 자리 판정까지 온다
  ( cd "$d/repo" && env -u FZ_AUTONOMY -u CODEX_HOME -u FZ_GPT_CHOICE_DIR -u FZ_GPT_CALL_ID -u FZ_GPT_CALL_LABEL -u FZ_GPT_POLICY_ROOT \
      -u FZ_GPT_IDLE_SEC "PATH=$CLIPATH" "HOME=$h" "CLAUDE_CODE_SESSION_ID=br-tmp" "FZ_AUTONOMY=autonomous" "FZ_TELEMETRY_DIR=$d/tel" \
      "TMPDIR=$h/.claude/x" /bin/bash "$ROOT/scripts/gpt-call.sh" independent-plan --requirement "$d/requirement.md" \
      --arm gpt --run-id br-tmp --out-dir "$d/out" < /dev/null ) > "$d/stdout" 2> "$d/stderr"
  rc=$?
  n="$(wc -l < "$CALLS" | tr -d ' ')"
  iso="$(find "$h/.claude/x" -maxdepth 1 -name 'fz-gpt-iso.*' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$rc" = 11 ] || add "exit 기대 11 · 실제 $rc"
  grep -qF '격리 폴더가 ~/.claude 아래에 생긴다' "$d/stderr" || add "~/.claude 메시지 없음 — stderr '$(head -c 240 "$d/stderr" | tr '\n' ' ')'"
  [ "$n" = 0 ] || add "기록 CLI 호출 ${n}회(0 이어야 한다)"
  [ "$iso" = 0 ] || add "격리 폴더가 ~/.claude 아래에 남았다(${iso}개)"
  verdict tmpdir-claude-zero-calls "$WHY" "exit 11 · ~/.claude 메시지 · 기록 CLI 호출 0 · 격리 폴더 미생성(GPT 홈 · 인증은 있다)"
}

# ── all-consumers-use-common ───────────────────────────────────────
case_all_consumers_use_common() {
  local res
  WHY=""
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" > "$T/consumers.out" 2> "$T/consumers.err" <<'PY'
import glob, json, os, re, subprocess, sys

root = sys.argv[1]
why = []


def pages(skill):
    d = os.path.join(root, "skills", skill)
    cand = [os.path.join(d, "SKILL.md")] + sorted(glob.glob(os.path.join(d, "references", "*.md")))
    return [p for p in cand if os.path.isfile(p)]


def text(skill):
    return "\n".join(open(p, encoding="utf-8", errors="replace").read() for p in pages(skill))


# 실제 호출자 — `gpt_kinds.py callers` 의 JSON({kind: [skill, ...]})을 그대로 읽는다. kinds-callers 와 같은 판독기다.
# ⛔ 판독 규칙(호출 정규식 · '명시 호출' 줄 제외 · fz-gpt 제외)을 여기 복제하지 않는다 — 판독기가 없거나 JSON 을 내지 못하면
#    다른 규칙으로 대신 세지 않고 측정 실패(FAIL)다. exit 11(선언 ≠ 배선)은 kinds-callers 몫이라 여기서는 JSON 만 쓴다
r = subprocess.run([sys.executable, os.path.join(root, "scripts", "gpt_kinds.py"), "callers", "--root", root],
                   capture_output=True, text=True)
try:
    scan = json.JSONDecoder().raw_decode(r.stdout.lstrip())[0]
    consumers = sorted({s for v in scan.values() for s in v})
except (ValueError, AttributeError, TypeError):
    scan, consumers = None, []
if scan is None or r.returncode not in (0, 11):
    tail = ((r.stdout + r.stderr).strip().splitlines() or [""])[-1]
    print(f"FAIL 호출자 판독기(gpt_kinds.py callers)가 결과를 내지 못했다(exit {r.returncode}) — 측정 실패 · {tail[:160]}")
    sys.exit(0)
if not consumers:
    why.append("GPT kind 를 부르는 스킬을 하나도 찾지 못했다(측정 실패 — 0 은 통과가 아니다)")
common = re.compile(r'gpt-choice\.sh"?\s+decide|§ 단계 실행 판정')
miss = [s for s in consumers if not common.search(text(s))]
if miss:
    why.append("공통 판정(decide · § 단계 실행 판정)을 가리키지 않는 소비 스킬: " + ", ".join(miss))
if re.search(r"--gpt(?![-\w])", text("fz-fix")):
    why.append("fz-fix 에 --gpt opt-in 문구가 남았다")
try:
    gs = open(os.path.join(root, "modules", "gpt-strategy.md"), encoding="utf-8").read()
except OSError as e:
    gs = ""
    why.append(f"modules/gpt-strategy.md 를 읽지 못했다({type(e).__name__})")
has_sec = re.search(r"(?m)^##\s+단계 실행 판정", gs)
has_dec = re.search(r'gpt-choice\.sh"?\s+decide', gs)
if gs and not (has_sec and has_dec):
    why.append("modules/gpt-strategy.md 에 § 단계 실행 판정 정본 절(decide)이 없다")
if why:
    print("FAIL " + " · ".join(why))
else:
    print(f"PASS 소비 스킬 {len(consumers)}개({', '.join(consumers)}) 모두 공통 판정 · fz-fix opt-in 없음 · 정본 절 있음")
PY
  res="$(head -1 "$T/consumers.out" 2>/dev/null)"
  case "$res" in
    "PASS "*) verdict all-consumers-use-common "" "${res#PASS }" ;;
    "FAIL "*) verdict all-consumers-use-common "${res#FAIL }" "" ;;
    *) verdict all-consumers-use-common "판정기가 결과를 내지 못했다 — $(head -c 240 "$T/consumers.err" 2>/dev/null | tr '\n' ' ')" "" ;;
  esac
}

# ── contract-order ─────────────────────────────────────────────────
# fz-plan full 순서(B2b · F-468) — 자리마다 그 토큰이 처음 나오는 줄이다. verify-gates 만 Phase 2 절 머리 뒤에서 찾는다
#   (Prerequisites 줄이 GPT 단계 목록으로 verify-gates 를 먼저 적는다). 이어서 parallel-arms 러너가 그대로 통과하는지 본다
case_contract_order() {
  local res rc arms="$ROOT/tests/fixtures/plan-wiring/parallel-arms/run.sh"
  WHY=""
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT/skills/fz-plan/SKILL.md" > "$T/order.out" 2> "$T/order.err" <<'PY'
import sys

try:
    lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
except OSError as e:
    print(f"FAIL skills/fz-plan/SKILL.md 를 읽지 못했다({type(e).__name__})")
    sys.exit(0)


def first(*tokens, start=1):
    """tokens 가 모두 든 첫 줄 번호(1부터 · start 줄부터 찾는다) — 없으면 None"""
    for i in range(start - 1, len(lines)):
        if all(t in lines[i] for t in tokens):
            return i + 1
    return None


p2 = first("## Phase 2: Plan Validation")
marks = [
    ("독립 플랜 기동", first("gpt-call.sh independent-plan")),
    ("Workflow 호출", first("Workflow({ scriptPath:")),
    ("방향 · 완주 정지", first("RECONSIDER", "degraded")),
    ("합치기", first("plan_divergence.py")),
    ("Sprint Contract", first("Sprint Contract", "directionVerdict")),
    ("재생성", first("--from-plan")),
    ("Phase 2 verify-gates", first("verify-gates", start=p2) if p2 else None),
]
why = [f"{name} 자리 없음" for name, at in marks if at is None]
if not why:
    why = [f"{n1}({a}) 가 {n2}({b}) 앞이 아니다" for (n1, a), (n2, b) in zip(marks, marks[1:]) if not a < b]
print(("FAIL " + " · ".join(why)) if why else ("PASS " + " < ".join(f"{name}({at})" for name, at in marks)))
PY
  res="$(head -1 "$T/order.out" 2>/dev/null)"
  case "$res" in
    "PASS "*) ;;
    "FAIL "*) add "${res#FAIL }" ;;
    *) add "순서 판정기가 결과를 내지 못했다 — $(head -c 240 "$T/order.err" 2>/dev/null | tr '\n' ' ')" ;;
  esac
  if [ -f "$arms" ]; then
    bash "$arms" < /dev/null > "$T/arms.out" 2>&1
    rc=$?
    [ "$rc" = 0 ] || add "parallel-arms 회귀(exit $rc) — $(grep -m1 '^FAIL' "$T/arms.out" 2>/dev/null | head -c 200)"
  else
    add "parallel-arms 러너가 없다(tests/fixtures/plan-wiring/parallel-arms/run.sh)"
  fi
  verdict contract-order "$WHY" "${res#PASS } · parallel-arms 통과"
}

# ── contract-regen ─────────────────────────────────────────────────
# 재생성 규칙(⑤)은 modules/sprint-contract.md 한 곳 — 그 줄이 plan-v · RTM · 원장 · --from-plan 을 함께 말한다. TEAM 발동 줄은 없고
#   입력 줄은 잠정 플랜 + directionVerdict 다. fz-plan 의 Sprint Contract 단계 줄(directionVerdict)은 그 모듈을 가리킨다.
#   cross-validation.md 는 이 Step 이 다시 쓴 행(방향성 검증 · 교훈 회상 · Sprint Contract)만 본다
case_contract_regen() {
  local res
  WHY=""
  PYTHONDONTWRITEBYTECODE=1 python3 -B - "$ROOT" > "$T/regen.out" 2> "$T/regen.err" <<'PY'
import os, re, sys

root = sys.argv[1]
why = []


def read(rel):
    try:
        return open(os.path.join(root, rel), encoding="utf-8").read().split("\n")
    except OSError as e:
        why.append(f"{rel} 를 읽지 못했다({type(e).__name__})")
        return []


sc = read("modules/sprint-contract.md")
plan = read("skills/fz-plan/SKILL.md")
cv = read("modules/cross-validation.md")
if sc:
    regen = [ln for ln in sc if "--from-plan" in ln]
    if len(regen) != 1:
        why.append(f"sprint-contract.md 의 재생성 규칙(--from-plan) 줄이 {len(regen)}개다 — 한 곳이어야 한다")
    elif not all(t in regen[0] for t in ("plan-v", "RTM", "원장")):
        why.append("sprint-contract.md 의 재생성 줄이 plan · RTM · 원장을 함께 말하지 않는다")
    team = [ln.strip() for ln in sc if "TEAM" in ln and (ln.lstrip().startswith("|") or re.search(r"발동|모드|mode|Step", ln))]
    if team:
        why.append("sprint-contract.md 에 TEAM 발동 줄이 남았다: " + team[0][:60])
    if not any("directionVerdict" in ln and "잠정 플랜" in ln for ln in sc):
        why.append("sprint-contract.md 입력 줄이 잠정 플랜 + directionVerdict 를 말하지 않는다")
if plan:
    step = next((ln for ln in plan if "Sprint Contract" in ln and "directionVerdict" in ln), "")
    if not step:
        why.append("fz-plan 에 Sprint Contract 단계(directionVerdict) 줄이 없다")
    elif "modules/sprint-contract.md" not in step:
        why.append("fz-plan 의 Sprint Contract 단계 줄이 modules/sprint-contract.md 를 가리키지 않는다")
    old = [ln.strip() for ln in plan if "Sprint Contract" in ln and "TEAM" in ln]
    if old:
        why.append("fz-plan 에 TEAM 기준 Sprint Contract 줄이 남았다: " + old[0][:60])
if cv:
    # 이 Step 이 다시 쓴 행만 본다 — 같은 표의 다른 TEAM 칸(review · search · code)은 범위 밖이다
    kinds = ("방향성 검증", "교훈 회상", "Sprint Contract")
    rows = [ln.strip() for ln in cv if ln.lstrip().startswith("|") and any(k in ln for k in kinds)]
    miss = [k for k in kinds if not any(k in row for row in rows)]
    if miss:
        why.append("cross-validation.md 표에 행이 없다: " + ", ".join(miss))
    lead = re.compile(r"(모든\s+)?TEAM")
    bad = [row for row in rows if any(lead.match(c.strip()) for c in row.strip("|").split("|"))]
    if bad:
        why.append("cross-validation.md 행에 TEAM 으로 시작하는 칸이 남았다: " + bad[0][:60])
if why:
    print("FAIL " + " · ".join(why))
else:
    msg = ["sprint-contract.md 재생성 규칙 1곳(plan-v · RTM · 원장 · --from-plan)", "TEAM 발동 줄 0",
           "입력 = 잠정 플랜 + directionVerdict", "fz-plan Sprint Contract 단계가 그 모듈을 가리킨다",
           "cross-validation 방향 · 회상 · Contract 행에 TEAM 칸 0"]
    print("PASS " + " · ".join(msg))
PY
  res="$(head -1 "$T/regen.out" 2>/dev/null)"
  case "$res" in
    "PASS "*) verdict contract-regen "" "${res#PASS }" ;;
    "FAIL "*) verdict contract-regen "${res#FAIL }" "" ;;
    *) verdict contract-regen "판정기가 결과를 내지 못했다 — $(head -c 240 "$T/regen.err" 2>/dev/null | tr '\n' ' ')" "" ;;
  esac
}

# ── 실행 — 케이스는 CASES 의 순서대로 돈다(B2b 는 이 배열에 함수를 더한다)
CASES=(case_same_input_twice case_tmpdir_claude_zero_calls case_all_consumers_use_common case_contract_order case_contract_regen)
for c in "${CASES[@]}"; do "$c"; done
echo
if [ "$FAILS" -eq 0 ]; then
  echo "gpt-branch: PASS"
  exit 0
fi
echo "gpt-branch: FAIL"
exit 1
