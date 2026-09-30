#!/bin/bash
# gpt-choice.sh 계약 러너 — 세션 1회 GPT 모델·effort 선택(options · get · set · config)과 래퍼(gpt-exec.sh)의 결정 순서를 합성 입력으로 본다.
#   --scope choice : get exit 0/3/4/5/11 · set 0/10/11 과 실패 시 파일 미기록 · 원자 기록(tmp+mv) · config config 센티넬 ·
#                    options JSON 모양(id·label 분리 · effort 교집합 · skip · config effort 미지원 표시) · config 엄격 판독 ·
#                    자율 판정 · 두 스크립트의 effort 화이트리스트 일치 · config(config.toml 최상위 값 · 캐시 비의존)
#   --scope wrapper: 래퍼 결정 순서 — 필드마다 플래그 > 세션 선택 > config(미전달) · exec/review/resume · --config-permissions ·
#                    stderr GPT-CHOICE 한 줄(출처 라벨 · config 실제 값 · '?') · 손상 선택 파일 · gpt-choice.sh 부재 → 11 ·
#                    get 은 stdout 만 판독 · get 값 재검증 · 사용법·플래그 오류(10)가 선택 판독(11)보다 먼저 · 빈 값 · 불량 모델 → 10 ·
#                    두 스크립트의 MODEL_RE 일치. 가짜 CLI(../_shim/codex)로 래퍼가 넘기는 argv 만 본다
#   ⛔ FZ_GPT_EXEC_UNDER_TEST 로 기준 트리의 래퍼를 같은 러너로 돌린다 — 기준 래퍼(effort 기본값 · 세션 선택 미판독)는 wrapper 가 FAIL 이어야 한다(판별력)
#   (인자 없음)    : 구현한 scope 전부 — health-check 4.6 이 인자 없이 돌린다
# ⛔ 실제 사용자 선택·모델 목록을 건드리지 않는다 — HOME · FZ_GPT_CHOICE_DIR · CODEX_HOME 은 셀마다 임시 폴더를 명시한다.
# ⛔ 셀마다 FZ_AUTONOMY 와 CLAUDE_CODE_SESSION_ID 를 명시한다 — health-check 는 Lead 세션 env(실제 세션 id · 자율 모드)를 물려받는다.
# ⛔ 대상 스크립트는 /bin/bash 로 돌린다 — macOS 기본 셸(3.2)에서 도는 것이 계약의 일부다.
# 모델 목록 캐시·config 는 **합성**이다(가짜 slug) — 실제 목록이 바뀌어도 판정이 흔들리지 않게.
set -u
ALL_SCOPES="choice wrapper"
case "${1:-}" in
  "")      SCOPES="$ALL_SCOPES" ;;
  --scope) SCOPES="${2:-}" ;;
  *)       echo "UNRUN  알 수 없는 인자 '$1' — --scope <$ALL_SCOPES> 만 받는다"; exit 2 ;;
esac
[ -n "$SCOPES" ] || { echo "UNRUN  --scope 값이 비었다 — $ALL_SCOPES 중 하나"; exit 2; }
for s in $SCOPES; do
  case " $ALL_SCOPES " in
    *" $s "*) ;;
    *) echo "UNRUN  scope '$s' 의 셀은 없다 — $ALL_SCOPES 만 구현한다"; exit 2 ;;
  esac
done

R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
CHOICE="$R/scripts/gpt-choice.sh"
WRAP="${FZ_GPT_EXEC_UNDER_TEST:-$R/scripts/gpt-exec.sh}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/cwd" "$T/home"

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 — 기대 '$3' · 실제 '$2'"; fi; }

# 셀 env 기본값 — 셀 앞에서 바꾸고 뒤에서 되돌린다. '-' 는 unset.
HOMEV="$T/home" SEL="$T/sel" CH="$T/ch-a"
cell() {   # $1=셀 · $2=FZ_AUTONOMY('-'=unset) · $3=CLAUDE_CODE_SESSION_ID('-'=unset) · 나머지=gpt-choice.sh 인자(하위 명령 먼저)
  local name="$1" auto="$2" sid="$3" d e
  shift 3
  d="$T/c-$name"; mkdir -p "$d"
  e=(env -u FZ_AUTONOMY -u CLAUDE_CODE_SESSION_ID -u FZ_GPT_CHOICE_DIR -u CODEX_HOME "HOME=$HOMEV")
  [ "$auto" = "-" ] || e+=("FZ_AUTONOMY=$auto")
  [ "$sid" = "-" ] || e+=("CLAUDE_CODE_SESSION_ID=$sid")
  [ "$SEL" = "-" ] || e+=("FZ_GPT_CHOICE_DIR=$SEL")
  [ "$CH" = "-" ] || e+=("CODEX_HOME=$CH")
  # ⛔ 임시 cwd 에서 돌린다 — 상대 경로 셀이 폴더를 만들어도 레포에 남지 않고, 만들었는지 여기서 확인한다
  ( cd "$T/cwd" && "${e[@]}" /bin/bash "$CHOICE" "$@" ) > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"
}
rc()   { cat "$T/c-$1/rc" 2>/dev/null || echo "?"; }
out()  { cat "$T/c-$1/stdout" 2>/dev/null; }
said() { if [ -s "$T/c-$1/stderr" ]; then echo 1; else echo 0; fi; }                # stderr 에 안내가 있는가
body() { if [ -f "$1" ]; then tr '\n' '|' < "$1"; else echo "<없음>"; fi; }          # 파일 내용 — 개행은 '|'(끝 개행까지 본다)
ino()  { python3 -c 'import os, sys; print(os.stat(sys.argv[1]).st_ino)' "$1" 2>/dev/null || echo "-"; }
nsel() { find "$T/sel" -type f 2>/dev/null | wc -l | tr -d ' '; }
js() {   # $1=셀 · $2=파이썬 식(d = options JSON) — 리스트는 쉼표로 잇는다. 파싱 실패는 '<parse-fail …>'
  python3 - "$T/c-$1/stdout" "$2" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    v = eval(sys.argv[2], {"d": d})
except Exception as e:  # noqa: BLE001 — 셀 결과를 FAIL 로 드러낸다
    print(f"<parse-fail {type(e).__name__}>")
    sys.exit(0)
print(",".join(map(str, v)) if isinstance(v, list) else v)
PY
}
mk_home() {   # $1=CODEX_HOME 폴더 이름 · $2=모델 목록 캐시 JSON · $3=config.toml — 빈 값이면 그 파일을 만들지 않는다
  mkdir -p "$T/$1"
  [ -z "$2" ] || printf '%s\n' "$2" > "$T/$1/models_cache.json"
  [ -z "$3" ] || printf '%s\n' "$3" > "$T/$1/config.toml"
}
s_fail() {   # $1=셀 · $2=기대 exit · $3=설명 · 나머지=set 인자 — 셀마다 새 세션 id(선택 파일 없음)에서 출발한다
  local name="$1" want="$2" what="$3"
  shift 3
  cell "$name" - "sid-$name" set "$@"
  check "set $what → $want" "$(rc "$name")" "$want"
  if [ -e "$T/sel/sid-$name" ]; then no "set $what: 파일을 썼다(fail-closed 위반)"; else ok "set $what: 파일 미기록"; fi
}
wl_parity() {   # gpt-choice.sh EFFORT_WHITELIST 와 래퍼 게이트 0(effort case 줄)이 같은 집합·순서인가
  python3 - "$CHOICE" "$WRAP" <<'PY'
import re, sys
c = open(sys.argv[1], encoding="utf-8").read()
w = open(sys.argv[2], encoding="utf-8").read()
m = re.search(r'(?m)^EFFORT_WHITELIST="([a-z ]+)"', c)
mine = m.group(1).split() if m else None
cases = [x.group(1).split("|") for x in re.finditer(r"(?m)^[ \t]*([a-z]+(?:[|][a-z]+)+)\)", w)
         if "xhigh" in x.group(1).split("|")]
print("same" if mine and cases and all(k == mine for k in cases) else f"differ: choice={mine} wrapper={cases}")
PY
}

# ── wrapper scope 도구 — 가짜 CLI(../_shim/codex)가 FZ_SHIM_CAPTURE 에 argv 를 JSON 으로 남긴다(config-permissions 러너와 같은 사용법)
SHIM="$R/tests/fixtures/gpt/_shim" WSEL="$T/wsel" WX="$WRAP"   # WX = 셀이 부를 래퍼 — 사본 트리 셀만 잠시 바꾼다
wcell() {   # $1=셀 · $2=FZ_AUTONOMY('-'=unset) · $3=CLAUDE_CODE_SESSION_ID('-'=unset) · $4=CODEX_HOME(합성) · 나머지=래퍼 인자(모드 먼저)
  local name="$1" auto="$2" sid="$3" ch="$4" d e
  shift 4
  d="$T/w-$name"; mkdir -p "$d"
  # ⛔ 선택 폴더 · CODEX_HOME · HOME 은 늘 임시다 — Lead 세션의 실제 선택 · config 가 셀에 새지 않는다. 래퍼도 /bin/bash(3.2)로 돌린다
  e=(env -u FZ_AUTONOMY -u CLAUDE_CODE_SESSION_ID "HOME=$T/home" "PATH=$SHIM:$PATH" "FZ_GPT_CHOICE_DIR=$WSEL" "CODEX_HOME=$ch"
     "FZ_SHIM_CAPTURE=$d/argv.json" "FZ_TELEMETRY_DIR=$d/tel")
  [ "$auto" = "-" ] || e+=("FZ_AUTONOMY=$auto")
  [ "$sid" = "-" ] || e+=("CLAUDE_CODE_SESSION_ID=$sid")
  "${e[@]}" /bin/bash "$WX" "$@" --cd "$T/repo" --out "$d/out.txt" > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"
}
wrun() {   # $1=셀 · $2=모드(exec|review|resume) · $3=FZ_AUTONOMY · $4=세션 id · $5=CODEX_HOME · 나머지=추가 래퍼 인자
  local name="$1" mode="$2" auto="$3" sid="$4" ch="$5"
  shift 5
  case "$mode" in
    exec)   wcell "$name" "$auto" "$sid" "$ch" exec --prompt-file "$T/w-task.txt" ${1+"$@"} ;;
    review) wcell "$name" "$auto" "$sid" "$ch" review --uncommitted ${1+"$@"} ;;
    resume) wcell "$name" "$auto" "$sid" "$ch" resume --prompt-file "$T/w-task.txt" --session-file "$T/w-prev.session" ${1+"$@"} ;;
  esac
}
wrc()     { cat "$T/w-$1/rc" 2>/dev/null || echo "?"; }
wcalled() { if [ -s "$T/w-$1/argv.json" ]; then echo 1; else echo 0; fi; }                  # CLI 를 불렀는가
wsaid()   { if grep -qF -- "$2" "$T/w-$1/stderr" 2>/dev/null; then echo 1; else echo 0; fi; }  # 래퍼 stderr 에 그 문구가 있는가
gline()   { grep '^GPT-CHOICE ' "$T/w-$1/stderr" 2>/dev/null | head -1; }                    # 적용값 줄
gcount()  { grep -c '^GPT-CHOICE ' "$T/w-$1/stderr" 2>/dev/null; }
argc() {   # $1=셀 · $2=값 — argv 에서 '-c' 바로 뒤에 그 값이 오는 횟수(CLI 를 부르지 않았으면 '-')
  [ -s "$T/w-$1/argv.json" ] || { echo "-"; return; }
  python3 - "$T/w-$1/argv.json" "$2" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
print(sum(1 for i in range(len(a) - 1) if a[i] == "-c" and a[i + 1] == sys.argv[2]))
PY
}
argpre() {   # $1=셀 · $2=접두어 — 그 접두어로 시작하는 argv 원소 수(CLI 를 부르지 않았으면 '-')
  [ -s "$T/w-$1/argv.json" ] || { echo "-"; return; }
  python3 - "$T/w-$1/argv.json" "$2" <<'PY'
import json, sys
print(sum(1 for x in json.load(open(sys.argv[1], encoding="utf-8")) if x.startswith(sys.argv[2])))
PY
}
leak() {   # $1=셀 — 모델·effort 를 넘기는 argv 원소 수('model=…' · 'review_model=…' · 'model_reasoning_effort…' · '--model' · '-m'). CLI 를 부르지 않았으면 '-'
  [ -s "$T/w-$1/argv.json" ] || { echo "-"; return; }
  python3 - "$T/w-$1/argv.json" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
print(sum(1 for x in a if x.startswith(("model=", "review_model=", "model_reasoning_effort")) or x in ("--model", "-m")))
PY
}
fake_tree() {   # $1=트리 · $2=가짜 gpt-choice.sh 본문 — 래퍼 사본 옆에 가짜 선택 스크립트를 둔다(get 판독 규약 셀)
  mkdir -p "$T/$1/scripts"; cp "$WRAP" "$T/$1/scripts/gpt-exec.sh"
  printf '#!/bin/bash\n%s\n' "$2" > "$T/$1/scripts/gpt-choice.sh"
}
re_parity() {   # 래퍼와 gpt-choice.sh 의 MODEL_RE 줄이 같은 문자열인가
  python3 - "$CHOICE" "$WRAP" <<'PY'
import re, sys
got = []
for p in sys.argv[1:3]:
    m = re.search(r"(?m)^MODEL_RE='([^']*)'", open(p, encoding="utf-8").read())
    got.append(m.group(1) if m else None)
print("same" if got[0] and got[0] == got[1] else f"differ: choice={got[0]} wrapper={got[1]}")
PY
}

run_choice() {
  echo "── scope choice"
  local c i1 i2 n0
  # 합성 모델 목록 A — 알파(config 모델) · 베타 · 감마 · 델타 · 지원 목록 없음 · 숨김.
  #   제시 모델(알파 + 베타·감마·델타)의 effort 교집합 = medium high xhigh. 베타의 none 은 화이트리스트 밖이다.
  local cache_a='{"models": [
  {"slug": "fake-alpha", "display_name": "Fake Alpha", "visibility": "list", "default_reasoning_level": "medium",
   "supported_reasoning_levels": [{"effort": "low"}, {"effort": "medium"}, {"effort": "high"}, {"effort": "xhigh"}]},
  {"slug": "fake-beta", "visibility": "list", "default_reasoning_level": "high",
   "supported_reasoning_levels": [{"effort": "medium"}, {"effort": "high"}, {"effort": "xhigh"}, {"effort": "ultra"}, {"effort": "none"}]},
  {"slug": "fake-gamma", "visibility": "list", "default_reasoning_level": "high",
   "supported_reasoning_levels": [{"effort": "low"}, {"effort": "medium"}, {"effort": "high"}, {"effort": "xhigh"}, {"effort": "max"}]},
  {"slug": "fake-delta", "visibility": "list", "default_reasoning_level": "high",
   "supported_reasoning_levels": [{"effort": "medium"}, {"effort": "high"}, {"effort": "xhigh"}]},
  {"slug": "fake-nolevels", "visibility": "list", "default_reasoning_level": "medium"},
  {"slug": "fake-hidden", "visibility": "hide", "default_reasoning_level": "low",
   "supported_reasoning_levels": [{"effort": "low"}, {"effort": "medium"}]}
]}'
  # 목록 W — 모델 1개(config 모델)가 화이트리스트 6개 + none 을 지원 · 목록 1 — 모델 1개가 high 만 지원
  local cache_w='{"models": [{"slug": "fake-wide", "visibility": "list", "default_reasoning_level": "medium",
  "supported_reasoning_levels": [{"effort": "none"}, {"effort": "low"}, {"effort": "medium"}, {"effort": "high"}, {"effort": "xhigh"}, {"effort": "max"}, {"effort": "ultra"}]}]}'
  local cache_1='{"models": [{"slug": "fake-one", "visibility": "list", "default_reasoning_level": "high",
  "supported_reasoning_levels": [{"effort": "high"}]}]}'
  mk_home ch-a "$cache_a" 'model = "fake-alpha"
model_reasoning_effort = "high"

[profiles.x]
model = "fake-beta"'
  mk_home ch-hid "$cache_a" 'model = "fake-hidden"'
  mk_home ch-prof "$cache_a" 'profile = "x"
model = "fake-alpha"
model_reasoning_effort = "high"

[profiles.x]
model = "fake-beta"'
  mk_home ch-nomodel "$cache_a" 'model_reasoning_effort = "low"

[profiles.y]
model = "fake-alpha"'
  # 줄 끝 주석 · 들여쓰기 — 독립 런처가 격리 config 로 옮기지 못하는 형태라 config 판독은 '?' 여야 한다(엄격 판독)
  mk_home ch-loose "$cache_a" 'model = "fake-alpha"  # 메모
  model_reasoning_effort = "high"'
  mk_home ch-wide "$cache_w" 'model = "fake-wide"
model_reasoning_effort = "medium"'
  mk_home ch-one "$cache_1" 'model = "fake-one"
model_reasoning_effort = "high"'
  mk_home ch-cacheonly "$cache_a" ''
  mk_home ch-none '' ''
  mk_home ch-bad 'not json {' 'model = "fake-alpha"'
  mkdir -p "$T/home2/.codex"; cp "$T/ch-a/models_cache.json" "$T/ch-a/config.toml" "$T/home2/.codex/"

  # ── get: 선택 없음 — 자율 판정은 autonomy_decide.py 가 한다(원문 비교면 ' Autonomous ' 에서 헤드리스가 질문을 시도한다)
  cell g-unset - sid-none get
  check "get 선택 없음 · FZ_AUTONOMY 미설정 → 3(물어도 됨)" "$(rc g-unset)" 3
  check "get 선택 없음: stdout 없음" "$(out g-unset)" ""
  cell g-auto autonomous sid-none get
  check "get 선택 없음 · autonomous → 4(묻지 않음)" "$(rc g-auto)" 4
  cell g-auto-norm " Autonomous " sid-none get
  check "get 선택 없음 · ' Autonomous '(공백·대소문자) → 4" "$(rc g-auto-norm)" 4
  cell g-inter interactive sid-none get
  check "get 선택 없음 · interactive → 3" "$(rc g-inter)" 3
  cell g-typo autonomus sid-none get
  check "get 선택 없음 · 모르는 모드 'autonomus' → 3(fail-closed 로 묻는다)" "$(rc g-typo)" 3

  # ── get: 저장할 수 없는 세션 → 5 + stderr 안내(묻지 않고 config)
  cell g-nosid - - get
  check "get 세션 id 없음 → 5" "$(rc g-nosid)" 5
  check "get 세션 id 없음: stderr 안내" "$(said g-nosid)" 1
  cell g-nosid-auto autonomous - get
  check "get 세션 id 없음 · autonomous → 5" "$(rc g-nosid-auto)" 5
  cell g-dots - ".." get
  check "get 세션 id '..'(부모 폴더) → 5" "$(rc g-dots)" 5
  cell g-slash - "a/b" get
  check "get 세션 id 'a/b'(경로 구분자) → 5" "$(rc g-slash)" 5
  cell g-dotfirst - ".tmp.x" get
  check "get 세션 id '.' 시작(임시 파일 몫) → 5" "$(rc g-dotfirst)" 5
  SEL="rel/sel"; cell g-rel - s1 get; SEL="$T/sel"
  check "get FZ_GPT_CHOICE_DIR 상대 경로 → 5" "$(rc g-rel)" 5
  check "get 상대 경로: stderr 안내" "$(said g-rel)" 1
  SEL='~/sel'; cell g-tilde - s1 get; SEL="$T/sel"
  check "get FZ_GPT_CHOICE_DIR 미확장 ~ → 5" "$(rc g-tilde)" 5
  HOMEV="" SEL="-"; cell g-nohome - s1 get; HOMEV="$T/home" SEL="$T/sel"
  check "get HOME·FZ_GPT_CHOICE_DIR 둘 다 없음 → 5" "$(rc g-nohome)" 5

  # ── set 성공 → 두 줄 기록 → get 0
  cell s-ok - s-ok set --model fake-beta --effort xhigh
  check "set 목록 모델 + 지원 effort → 0" "$(rc s-ok)" 0
  check "set 기록: 두 줄 'model=…' 'effort=…'" "$(body "$T/sel/s-ok")" "model=fake-beta|effort=xhigh|"
  check "set stdout" "$(out s-ok)" "model=fake-beta effort=xhigh"
  cell g-ok - s-ok get
  check "get 선택 있음 → 0" "$(rc g-ok)" 0
  check "get 선택 있음: stdout" "$(out g-ok)" "model=fake-beta effort=xhigh"
  cell g-ok-auto autonomous s-ok get
  check "get 선택 있음 · autonomous → 0(선택이 있으면 자율이어도 적용)" "$(rc g-ok-auto)" 0
  # get 은 모델 목록 캐시를 읽지 않는다 — 격리 CODEX_HOME 에는 캐시가 없을 수 있다
  CH="$T/ch-none"; cell g-nocache - s-ok get; CH="$T/ch-bad"; cell g-badcache - s-ok get; CH="$T/ch-a"
  check "get 캐시 없음 → 여전히 0" "$(rc g-nocache)" 0
  check "get 캐시 손상 → 여전히 0" "$(rc g-badcache)" 0

  # ── 원자 기록 — 같은 폴더 임시 파일 + mv(rename) 이면 덮어쓸 때 inode 가 바뀐다(제자리 쓰기면 그대로다)
  i1="$(ino "$T/sel/s-ok")"
  cell s-over - s-ok set --model fake-gamma --effort max
  i2="$(ino "$T/sel/s-ok")"
  check "set 덮어쓰기 → 0" "$(rc s-over)" 0
  check "set 덮어쓰기: 새 값" "$(body "$T/sel/s-ok")" "model=fake-gamma|effort=max|"
  if [ "$i1" != "-" ] && [ "$i1" != "$i2" ]; then ok "set 덮어쓰기: 새 inode(tmp+mv)"; else no "set 덮어쓰기: inode 가 그대로다($i1 → $i2) — 제자리 쓰기면 읽는 쪽이 반쯤 쓴 파일을 본다"; fi

  # ── config config 센티넬 — 캐시·config 를 읽지 않고 성공한다(세션 id 만 필요)
  CH="-"; cell s-cc - s-cc set --model config --effort config; CH="$T/ch-a"
  check "set config config · 캐시 없음(기본 CODEX_HOME) → 0" "$(rc s-cc)" 0
  check "set config config: 기록" "$(body "$T/sel/s-cc")" "model=config|effort=config|"
  CH="$T/ch-bad"; cell s-cc-bad - s-cc-bad set --model config --effort config; CH="$T/ch-a"
  check "set config config · 캐시 손상 → 0(캐시를 읽지 않는다)" "$(rc s-cc-bad)" 0
  cell g-cc - s-cc get
  check "get config config → 0" "$(rc g-cc)" 0
  check "get config config: stdout" "$(out g-cc)" "model=config effort=config"
  # 기본 저장 위치 = HOME/.fz/gpt-choice
  SEL="-"; cell s-def - s-def set --model config --effort config; cell g-def - s-def get; SEL="$T/sel"
  check "set 기본 저장 위치 → 0" "$(rc s-def)" 0
  check "set 기본 저장 위치: HOME/.fz/gpt-choice/<세션 id>" "$(body "$T/home/.fz/gpt-choice/s-def")" "model=config|effort=config|"
  check "get 기본 저장 위치 → 0" "$(rc g-def)" 0

  # ── set 실패는 fail-closed — exit 10(검증) · 11(사전조건), 파일을 쓰지 않는다
  n0="$(nsel)"
  s_fail s-hidden 10 "숨김 모델(목록 밖 · config 모델 아님)" --model fake-hidden --effort low
  s_fail s-nope 10 "목록에 없는 모델" --model fake-nope --effort high
  s_fail s-unsup 10 "모델이 지원하지 않는 effort" --model fake-delta --effort low
  s_fail s-none 10 "화이트리스트 밖 effort(캐시에는 있음)" --model fake-beta --effort none
  s_fail s-nolv 10 "지원 목록 모르는 모델 + effort" --model fake-nolevels --effort high
  s_fail s-cfgmax 10 "config 모델이 지원하지 않는 effort" --model config --effort max
  CH="$T/ch-nomodel"; s_fail s-cfgunk 10 "config 모델 모름(최상위 model 없음) + effort" --model config --effort high
  s_fail s-cfgeff 10 "목록 모델 + effort config · 그 모델이 config effort(low)를 지원하지 않음" --model fake-beta --effort config
  CH="$T/ch-loose"; s_fail s-loose 10 "config 모델 모름(줄 끝 주석 — 엄격 판독) + effort" --model config --effort high
  CH="$T/ch-prof"; s_fail s-prof 10 "config 모델 모름(profile) + effort" --model config --effort high
  CH="$T/ch-none"; s_fail s-nocache 11 "모델 목록 캐시 없음" --model fake-beta --effort high
  CH="$T/ch-bad"; s_fail s-badcache 11 "모델 목록 캐시 손상" --model fake-beta --effort high
  CH="$T/ch-a"
  s_fail s-dash 10 "'-' 로 시작하는 모델 값" --model -x --effort high
  s_fail s-quote 10 "따옴표 든 모델 값" --model 'a"b' --effort high
  s_fail s-upper 10 "대문자 effort" --model fake-beta --effort HIGH
  s_fail s-empty 10 "빈 effort" --model fake-beta --effort ""
  s_fail s-noeff 10 "--effort 누락" --model fake-beta
  s_fail s-noval 10 "--model 값 누락" --model
  s_fail s-extra 10 "알 수 없는 인자" --model config --effort config --bogus
  cell s-nosid - - set --model config --effort config
  check "set 세션 id 없음 → 11" "$(rc s-nosid)" 11
  SEL="rel/sel"; cell s-rel - s-rel set --model config --effort config; SEL="$T/sel"
  check "set FZ_GPT_CHOICE_DIR 상대 경로 → 11" "$(rc s-rel)" 11
  if [ -e "$T/cwd/rel" ]; then no "set 상대 경로: cwd 에 폴더를 만들었다"; else ok "set 상대 경로: 아무것도 만들지 않음"; fi
  check "set 실패 전부: 선택 폴더 파일 수 불변" "$(nsel)" "$n0"
  cell s-keep - s-ok set --model fake-nope --effort high
  check "set 실패 → 10" "$(rc s-keep)" 10
  check "set 실패: 이전 선택을 그대로 둔다" "$(body "$T/sel/s-ok")" "model=fake-gamma|effort=max|"

  # ── set 성공 변형
  cell s-nolv-cfg - s-nolv-cfg set --model fake-nolevels --effort config
  check "set 지원 목록 모르는 모델 + effort config → 0(검증할 effort 가 없다)" "$(rc s-nolv-cfg)" 0
  cell s-cfgx - s-cfgx set --model config --effort xhigh
  check "set config 모델 + 그 모델이 지원하는 effort → 0" "$(rc s-cfgx)" 0
  check "set config 모델: 기록" "$(body "$T/sel/s-cfgx")" "model=config|effort=xhigh|"
  cell s-slugcfg - s-slugcfg set --model fake-gamma --effort config
  check "set 목록 모델 + effort config → 0" "$(rc s-slugcfg)" 0
  CH="$T/ch-hid"; cell s-cfghid - s-cfghid set --model fake-hidden --effort low; CH="$T/ch-a"
  check "set config 최상위 model 은 목록 밖(숨김)이어도 받는다 → 0" "$(rc s-cfghid)" 0
  CH="$T/ch-nomodel"; cell s-cfgeff-ok - s-cfgeff-ok set --model fake-gamma --effort config; CH="$T/ch-a"
  check "set 목록 모델 + effort config · 그 모델이 config effort(low)를 지원 → 0" "$(rc s-cfgeff-ok)" 0
  CH="$T/ch-prof"; cell s-cfgeff-unk - s-cfgeff-unk set --model fake-beta --effort config; CH="$T/ch-a"
  check "set 목록 모델 + effort config · config effort 모름(profile) → 0(막을 근거가 없다)" "$(rc s-cfgeff-unk)" 0
  check "set 뒤 임시 파일이 남지 않는다" "$(find "$T/sel" -type f -name '.*' | wc -l | tr -d ' ')" 0

  # ── get: 선택 파일 손상 → 11(다시 묻고 set 으로 덮어쓴다) — 자율 모드여도 11
  mkdir -p "$T/sel/bad-dir"
  printf 'model=fake-beta\n' > "$T/sel/bad-1line"
  printf 'effort=high\nmodel=fake-beta\n' > "$T/sel/bad-order"
  printf 'model=fake-beta\neffort=high\nextra=1\n' > "$T/sel/bad-extra"
  printf 'model=-x\neffort=high\n' > "$T/sel/bad-dash"
  printf 'model=fake beta\neffort=high\n' > "$T/sel/bad-space"
  printf 'model=fake-beta\neffort=none\n' > "$T/sel/bad-effort"
  printf 'model=fake-beta\r\neffort=high\r\n' > "$T/sel/bad-crlf"
  : > "$T/sel/bad-empty"
  for c in bad-1line bad-order bad-extra bad-dash bad-space bad-effort bad-crlf bad-empty bad-dir; do
    cell "g-$c" - "$c" get
    check "get 손상($c) → 11" "$(rc "g-$c")" 11
    check "get 손상($c): stdout 없음" "$(out "g-$c")" ""
  done
  check "get 손상: stderr 안내" "$(said g-bad-order)" 1
  cell g-bad-auto autonomous bad-order get
  check "get 손상 · autonomous → 11" "$(rc g-bad-auto)" 11
  cell s-ondir - bad-dir set --model config --effort config
  check "set 저장 자리가 폴더 → 11" "$(rc s-ondir)" 11
  check "set 저장 자리가 폴더: 그 안에 쓰지 않는다" "$(find "$T/sel/bad-dir" -type f | wc -l | tr -d ' ')" 0

  # ── options: id(slug|config)·label 분리 · effort 선택지 = 제시 모델 지원 수준 교집합 ∩ 화이트리스트 · 선택지 2개 미만이면 skip
  cell o-a - - options
  check "options → 0" "$(rc o-a)" 0
  check "options: config 최상위 model(표 안의 model 은 무시)" "$(js o-a 'd["config"]["model"]')" fake-alpha
  check "options: config 최상위 effort" "$(js o-a 'd["config"]["effort"]')" high
  check "options: 목록 모델 = visibility=list(숨김 제외 · 캐시 순서)" "$(js o-a '[m["id"] for m in d["models"]]')" "fake-alpha,fake-beta,fake-gamma,fake-delta,fake-nolevels"
  check "options: label = display_name, 없으면 slug" "$(js o-a '[m["label"] for m in d["models"][:2]]')" "Fake Alpha,fake-beta"
  check "options: 모델 기본 effort" "$(js o-a 'd["models"][1]["default_effort"]')" high
  check "options: 지원 effort ∩ 화이트리스트(none 제외)" "$(js o-a 'd["models"][1]["efforts"]')" "medium,high,xhigh,ultra"
  check "options: 지원 목록 모름 = null" "$(js o-a 'd["models"][4]["efforts"]')" None
  check "options: 모델 질문 = config + 목록 앞 3개(config 모델 중복 없음)" "$(js o-a '[c["id"] for c in d["questions"]["model"]["choices"]]')" "config,fake-beta,fake-gamma,fake-delta"
  check "options: 모델 질문 나머지(more)" "$(js o-a 'd["questions"]["model"]["more"]')" fake-nolevels
  check "options: config 선택지 label 에 config 값" "$(js o-a 'd["questions"]["model"]["choices"][0]["label"]')" "config 기본 (fake-alpha)"
  check "options: 선택지마다 id·label 두 키" "$(js o-a 'all(sorted(c) == ["id", "label"] for q in d["questions"].values() for c in q["choices"])')" True
  check "options: effort 질문 = 제시 모델(알파·베타·감마·델타) 교집합 − config 값" "$(js o-a '[c["id"] for c in d["questions"]["effort"]["choices"]]')" "config,medium,xhigh"
  check "options: 제시 모델이 모두 config effort 를 지원하면 config 선택지 표시 없음" "$(js o-a 'd["questions"]["effort"]["choices"][0]["label"]')" "config 기본 (high)"
  check "options: 선택지 2개 이상이면 skip 아님" "$(js o-a '[d["questions"][q]["skip"] for q in ("model", "effort")]')" "False,False"
  check "options: effort 화이트리스트" "$(js o-a 'd["effort_whitelist"]')" "low,medium,high,xhigh,max,ultra"
  CH="$T/ch-wide"; cell o-wide - - options
  CH="$T/ch-one"; cell o-one - - options
  CH="$T/ch-prof"; cell o-prof - - options
  CH="$T/ch-nomodel"; cell o-nomodel - - options
  CH="$T/ch-loose"; cell o-loose - - options
  CH="$T/ch-cacheonly"; cell o-conly - - options
  CH="$T/ch-none"; cell o-nocache - - options
  CH="$T/ch-bad"; cell o-bad - - options
  CH="-" HOMEV="$T/home2"; cell o-def - - options; CH="$T/ch-a" HOMEV="$T/home"
  check "options 목록 모델 1개(config 모델): 모델 질문 skip" "$(js o-wide '[d["questions"]["model"]["skip"], len(d["questions"]["model"]["choices"])]')" "True,1"
  check "options effort 6개: config 값(medium)에 가까운 3개 · 화이트리스트 순" "$(js o-wide '[c["id"] for c in d["questions"]["effort"]["choices"]]')" "config,low,high,xhigh"
  check "options effort 6개: 나머지는 more" "$(js o-wide 'd["questions"]["effort"]["more"]')" "max,ultra"
  check "options effort 후보가 config 값뿐: effort 질문 skip" "$(js o-one '[d["questions"]["effort"]["skip"], len(d["questions"]["effort"]["choices"])]')" "True,1"
  check "options profile 사용: config 기본 '?'" "$(js o-prof '[d["config"]["model"], d["config"]["effort"]]')" "?,?"
  check "options profile 사용: 모델 질문 = config + 목록 앞 3개" "$(js o-prof '[c["id"] for c in d["questions"]["model"]["choices"]]')" "config,fake-alpha,fake-beta,fake-gamma"
  check "options profile 사용: effort 질문(알파·베타·감마 교집합)" "$(js o-prof '[c["id"] for c in d["questions"]["effort"]["choices"]]')" "config,medium,high,xhigh"
  check "options 최상위 model 없음: config 모델 '?'(표 안의 model 은 무시)" "$(js o-nomodel '[d["config"]["model"], d["config"]["effort"]]')" "?,low"
  # ⛔ config 모델의 지원 effort 를 모르면 set 이 '--model config --effort <명시>' 를 exit 10 으로 거부한다 — 선택지 label 이 미리 알린다
  check "options config 모델 모름(profile): config 선택지 label 에 'effort 는 config 만'" "$(js o-prof 'd["questions"]["model"]["choices"][0]["label"]')" "config 기본 (? · effort 는 config 만)"
  check "options config 모델 모름(최상위 model 없음): config 선택지 label 에 'effort 는 config 만'" "$(js o-nomodel 'd["questions"]["model"]["choices"][0]["label"]')" "config 기본 (? · effort 는 config 만)"
  check "options 지원 목록을 아는 모델: 'effort 는 config 만' 표시 없음" "$(js o-a 'any("effort 는 config 만" in c["label"] for c in d["questions"]["model"]["choices"])')" False
  check "options config effort(low)를 제시 모델 일부가 지원하지 않음: effort 선택지는 교집합 그대로" "$(js o-nomodel '[c["id"] for c in d["questions"]["effort"]["choices"]]')" "config,medium,high,xhigh"
  check "options config effort 미지원 제시 모델: config 선택지 label 에 표시" "$(js o-nomodel 'd["questions"]["effort"]["choices"][0]["label"]')" "config 기본 (low · fake-beta 미지원)"
  check "options config 줄 끝 주석·들여쓰기: 엄격 판독이라 config 기본 '?'" "$(js o-loose '[d["config"]["model"], d["config"]["effort"]]')" "?,?"
  check "options config.toml 없음: config 기본 '?'" "$(js o-conly '[d["config"]["model"], d["config"]["effort"]]')" "?,?"
  check "options 모델 목록 캐시 없음 → 11" "$(rc o-nocache)" 11
  check "options 캐시 없음: stdout 없음" "$(out o-nocache)" ""
  check "options 모델 목록 캐시 손상 → 11" "$(rc o-bad)" 11
  check "options 기본 CODEX_HOME(HOME/.codex) 판독" "$(js o-def 'd["config"]["model"]')" fake-alpha

  # ── config: config.toml 최상위 값 — 래퍼 GPT-CHOICE 표시용. options · set 과 같은 엄격 판독이고 캐시 · 선택 파일을 읽지 않는다
  cell k-a - - config
  check "config → 0" "$(rc k-a)" 0
  check "config: 최상위 model · effort(표 안의 model 은 무시)" "$(out k-a)" "model=fake-alpha effort=high"
  CH="$T/ch-bad"; cell k-badcache - - config
  CH="$T/ch-prof"; cell k-prof - - config
  CH="$T/ch-loose"; cell k-loose - - config
  CH="$T/ch-nomodel"; cell k-nomodel - - config
  CH="$T/ch-cacheonly"; cell k-nocfg - - config
  CH="$T/ch-a"
  check "config 캐시 손상 → 0(캐시를 읽지 않는다)" "$(rc k-badcache)|$(out k-badcache)" "0|model=fake-alpha effort=?"
  check "config profile 사용 → '?'" "$(out k-prof)" "model=? effort=?"
  check "config 줄 끝 주석·들여쓰기 → '?'(엄격 판독)" "$(out k-loose)" "model=? effort=?"
  check "config 최상위 model 없음 → model '?'(표 안의 model 은 무시)" "$(out k-nomodel)" "model=? effort=low"
  check "config config.toml 없음 → '?' 두 개 · exit 0" "$(rc k-nocfg)|$(out k-nocfg)" "0|model=? effort=?"
  cell k-arg - - config extra
  check "config 인자 → 10" "$(rc k-arg)" 10

  # ── 사용법 · 화이트리스트 대조
  cell u-sub - s1 bogus
  check "알 수 없는 하위 명령 → 10" "$(rc u-sub)" 10
  cell u-get - s1 get extra
  check "get 인자 → 10" "$(rc u-get)" 10
  check "effort 화이트리스트: gpt-choice.sh = 래퍼 게이트 0" "$(wl_parity)" same
}

run_wrapper() {
  echo "── scope wrapper"
  local c m
  mkdir -p "$T/repo" "$WSEL" "$T/wh-cfg" "$T/wh-prof" "$T/wh-perm" "$T/wh-none"
  printf '과제 본문 WCH-TASK-3\n' > "$T/w-task.txt"
  printf '# Synthetic W Skill\n\n합성 역할 본문.\n' > "$T/w-skill.md"
  echo '11111111-2222-3333-4444-555555555555' > "$T/w-prev.session"
  # 합성 config(가짜 slug) — 최상위 model · effort(출처 config 표시 대상) · profile 사용(→ '?') · 권한 프로필(--config-permissions) · 없음(→ '?')
  printf 'model = "fake-cfg"\nmodel_reasoning_effort = "low"\n' > "$T/wh-cfg/config.toml"
  printf 'profile = "x"\nmodel = "fake-cfg"\nmodel_reasoning_effort = "low"\n\n[profiles.x]\nmodel = "fake-beta"\n' > "$T/wh-prof/config.toml"
  printf 'default_permissions = "iso"\nmodel = "fake-cfg"\nmodel_reasoning_effort = "low"\n\n[permissions.iso]\nextends = ":read-only"\n' > "$T/wh-perm/config.toml"
  # 세션 선택 파일(get 이 읽는 두 줄) — 선택 · config/config · 모델만 · 손상(순서 뒤바뀜). 세션 w-none 은 파일이 없다
  printf 'model=fake-beta\neffort=xhigh\n' > "$WSEL/w-sel"
  printf 'model=config\neffort=config\n' > "$WSEL/w-cc"
  printf 'model=fake-beta\neffort=config\n' > "$WSEL/w-half"
  printf 'effort=high\nmodel=fake-beta\n' > "$WSEL/w-bad"

  # ── 선택 없음(파일 없음 · FZ_AUTONOMY=autonomous · 세션 id 없음) → 세 모드 모두 모델·effort 미전달 · 출처 config · config.toml 실제 값
  for m in exec review resume; do
    wrun "none-$m" "$m" - w-none "$T/wh-cfg"
    wrun "auto-$m" "$m" autonomous w-none "$T/wh-cfg"
    wrun "nosid-$m" "$m" - - "$T/wh-cfg"
    for c in none auto nosid; do
      check "선택 없음($c) $m: exit 0" "$(wrc "$c-$m")" 0
      check "선택 없음($c) $m: argv 에 모델·effort 0(config.toml 그대로)" "$(leak "$c-$m")" 0
      check "선택 없음($c) $m: GPT-CHOICE = config.toml 실제 값 (config)" "$(gline "$c-$m")" "GPT-CHOICE model=fake-cfg (config) effort=low (config)"
    done
  done
  check "선택 없음(세션 id 없음): get 안내(exit 5)는 래퍼 stderr 로 새지 않는다" "$(wsaid nosid-exec '저장할 수 없는 세션')" 0

  # ── 세션 선택 → 세 모드 모두 반영 — resume 도 같은 결정 순서다(원 세션의 모델로 고정하지 않는다)
  for m in exec review resume; do
    wrun "sel-$m" "$m" - w-sel "$T/wh-cfg"
    check "세션 선택 $m: exit 0" "$(wrc "sel-$m")" 0
    check "세션 선택 $m: 모델(-c 뒤 TOML 문자열)" "$(argc "sel-$m" 'model="fake-beta"')" 1
    check "세션 선택 $m: effort(-c 뒤)" "$(argc "sel-$m" 'model_reasoning_effort=xhigh')" 1
    # review 는 config review_model 이 model 보다 먼저라 모델을 review_model 로도 덮는다 — 원소가 하나 더 있다
    check "세션 선택 $m: 모델·effort 원소 수(review 는 review_model 포함 3)" "$(leak "sel-$m")" "$([ "$m" = review ] && echo 3 || echo 2)"
    check "세션 선택 $m: review_model 은 review 모드에만" "$(argc "sel-$m" 'review_model="fake-beta"')" "$([ "$m" = review ] && echo 1 || echo 0)"
    check "세션 선택 $m: GPT-CHOICE (session)" "$(gline "sel-$m")" "GPT-CHOICE model=fake-beta (session) effort=xhigh (session)"
  done
  wrun sel-auto exec autonomous w-sel "$T/wh-cfg"
  check "세션 선택 · autonomous: 선택이 있으면 자율이어도 적용" "$(argc sel-auto 'model="fake-beta"')|$(argc sel-auto 'model_reasoning_effort=xhigh')" "1|1"

  # ── 플래그가 필드별로 세션 선택을 이긴다
  wrun flag-m exec - w-sel "$T/wh-cfg" --model fake-flag
  check "--model 플래그: 모델 = 플래그 · 세션 모델 0" "$(argc flag-m 'model="fake-flag"')|$(argc flag-m 'model="fake-beta"')" "1|0"
  check "--model 플래그: effort = 세션" "$(argc flag-m 'model_reasoning_effort=xhigh')" 1
  check "--model 플래그: GPT-CHOICE (flag · session)" "$(gline flag-m)" "GPT-CHOICE model=fake-flag (flag) effort=xhigh (session)"
  wrun flag-e review - w-sel "$T/wh-cfg" --effort medium
  check "--effort 플래그 · review: effort = 플래그 · 세션 effort 0" "$(argc flag-e 'model_reasoning_effort=medium')|$(argc flag-e 'model_reasoning_effort=xhigh')" "1|0"
  check "--effort 플래그 · review: 모델 = 세션" "$(argc flag-e 'model="fake-beta"')" 1
  check "--effort 플래그 · review: GPT-CHOICE (session · flag)" "$(gline flag-e)" "GPT-CHOICE model=fake-beta (session) effort=medium (flag)"
  wrun flag-both resume - w-sel "$T/wh-cfg" --model fake-flag --effort high
  check "플래그 둘 다 · resume: 모델 · effort 모두 플래그(원래 모델로 이을 때 고정하는 길)" "$(argc flag-both 'model="fake-flag"')|$(argc flag-both 'model_reasoning_effort=high')|$(leak flag-both)" "1|1|2"
  check "플래그 둘 다 · resume: GPT-CHOICE (flag · flag)" "$(gline flag-both)" "GPT-CHOICE model=fake-flag (flag) effort=high (flag)"
  wrun flag-num exec - w-none "$T/wh-cfg" --model 123
  check "숫자형 모델 값도 TOML 문자열로 넘긴다" "$(argc flag-num 'model="123"')" 1
  check "숫자형 모델 · 선택 없음: GPT-CHOICE (flag · config 실제 값)" "$(gline flag-num)" "GPT-CHOICE model=123 (flag) effort=low (config)"

  # ── 값 config = 그 필드를 넘기지 않는다(세션 선택 · 플래그 공통)
  wrun cc exec - w-cc "$T/wh-cfg"
  check "선택 config/config: exit 0 · argv 에 모델·effort 0" "$(wrc cc)|$(leak cc)" "0|0"
  check "선택 config/config: GPT-CHOICE (config)" "$(gline cc)" "GPT-CHOICE model=fake-cfg (config) effort=low (config)"
  wrun half exec - w-half "$T/wh-cfg"
  check "선택 모델만(effort=config): 모델만 넘긴다" "$(argc half 'model="fake-beta"')|$(leak half)" "1|1"
  check "선택 모델만: GPT-CHOICE (session · config)" "$(gline half)" "GPT-CHOICE model=fake-beta (session) effort=low (config)"
  wrun flag-cc exec - w-sel "$T/wh-cfg" --model config --effort config
  check "플래그 config/config: 세션 선택이 있어도 모델·effort 0" "$(wrc flag-cc)|$(leak flag-cc)" "0|0"
  check "플래그 config/config: GPT-CHOICE (config)" "$(gline flag-cc)" "GPT-CHOICE model=fake-cfg (config) effort=low (config)"

  # ── 출처 config 인데 config.toml 값을 모른다 → '?'
  wrun prof exec - w-none "$T/wh-prof"
  check "profile 을 쓰는 config: GPT-CHOICE '?'" "$(gline prof)" "GPT-CHOICE model=? (config) effort=? (config)"
  wrun nocfg exec - w-none "$T/wh-none"
  check "config.toml 없음: GPT-CHOICE '?'" "$(gline nocfg)" "GPT-CHOICE model=? (config) effort=? (config)"

  # ── --config-permissions(격리 런처 경로) — ARGS 재대입 뒤에도 모델·effort 가 붙는다
  wrun perm exec - w-sel "$T/wh-perm" --config-permissions
  check "--config-permissions · 세션 선택: exit 0 · sandbox_mode 0" "$(wrc perm)|$(argpre perm 'sandbox_mode')" "0|0"
  check "--config-permissions · 세션 선택: 모델 · effort" "$(argc perm 'model="fake-beta"')|$(argc perm 'model_reasoning_effort=xhigh')" "1|1"
  wrun perm-none exec - w-none "$T/wh-perm" --config-permissions
  check "--config-permissions · 선택 없음: exit 0 · 모델·effort 0" "$(wrc perm-none)|$(leak perm-none)" "0|0"
  check "--config-permissions · 선택 없음: GPT-CHOICE = 그 CODEX_HOME 의 config 값" "$(gline perm-none)" "GPT-CHOICE model=fake-cfg (config) effort=low (config)"
  wrun perm-flag exec - w-none "$T/wh-perm" --config-permissions --effort high
  check "--config-permissions · --effort: 준 effort 전달" "$(argc perm-flag 'model_reasoning_effort=high')" 1

  # ── 실패 계약 — 손상 선택 파일 · gpt-choice.sh 부재 → exit 11(조용히 config 로 가지 않는다) · CLI 미호출
  wrun bad exec - w-bad "$T/wh-cfg"
  check "손상 선택 파일: exit 11 · CLI 미호출" "$(wrc bad)|$(wcalled bad)" "11|0"
  check "손상 선택 파일: 다시 묻고 set 으로 덮어쓰라는 안내" "$(wsaid bad '선택 파일을 읽지 못했다 — Lead 는 다시 묻고 gpt-choice.sh set 으로 덮어쓴다')" 1
  check "손상 선택 파일: 태그 CHOICE-UNREADABLE(문서가 인용하는 신호) · SCRIPT-ERROR 아님" "$(wsaid bad 'CHOICE-UNREADABLE:')|$(wsaid bad 'CHOICE-SCRIPT-ERROR')" "1|0"
  check "손상 선택 파일: get 의 사유를 붙인다(비정상 exit 일 때만)" "$(wsaid bad '선택 파일 손상')" 1
  wrun bad-auto review autonomous w-bad "$T/wh-cfg"
  check "손상 선택 파일 · autonomous · review: exit 11" "$(wrc bad-auto)" 11
  mkdir -p "$T/tree-a/scripts"; cp "$WRAP" "$T/tree-a/scripts/gpt-exec.sh"
  WX="$T/tree-a/scripts/gpt-exec.sh"; wrun absent exec - w-sel "$T/wh-cfg"; WX="$WRAP"
  check "gpt-choice.sh 부재(래퍼만 있는 트리): exit 11 · CLI 미호출" "$(wrc absent)|$(wcalled absent)" "11|0"
  # ⛔ 스크립트 오류는 다시 물어도 풀리지 않는다 — '다시 묻고 set' 처방을 내지 않고 플래그 우회를 알린다
  check "gpt-choice.sh 부재: 태그 CHOICE-SCRIPT-ERROR · 재질문 처방 없음 · 플래그 우회 안내" "$(wsaid absent 'CHOICE-SCRIPT-ERROR:')|$(wsaid absent '다시 묻고')|$(wsaid absent '--model config --effort config')" "1|0|1"
  mkdir -p "$T/tree-x/scripts"; cp "$WRAP" "$T/tree-x/scripts/gpt-exec.sh"; cp "$CHOICE" "$T/tree-x/scripts/gpt-choice.sh"
  chmod a-x "$T/tree-x/scripts/gpt-choice.sh"
  WX="$T/tree-x/scripts/gpt-exec.sh"; wrun noexec exec - w-sel "$T/wh-cfg"; WX="$WRAP"
  check "gpt-choice.sh 실행 비트 없음: 그래도 세션 선택 적용(bash 로 부른다)" "$(wrc noexec)|$(argc noexec 'model="fake-beta"')" "0|1"

  # ── get 판독 규약 — stdout 한 줄만 파싱한다 · get 이 낸 값도 다시 검증한다(두 규칙이 어긋나면 11)
  fake_tree tree-n "echo '잡음 한 줄' >&2; exec bash '$CHOICE' \"\$@\""
  WX="$T/tree-n/scripts/gpt-exec.sh"; wrun noise exec - w-sel "$T/wh-cfg"; WX="$WRAP"
  check "get 성공 + stderr 잡음: 선택 그대로 적용(stdout 만 파싱)" "$(wrc noise)|$(argc noise 'model="fake-beta"')|$(argc noise 'model_reasoning_effort=xhigh')" "0|1|1"
  fake_tree tree-fe 'echo "model=fake-beta effort=bogus"'
  WX="$T/tree-fe/scripts/gpt-exec.sh"; wrun fe exec - w-sel "$T/wh-cfg"; WX="$WRAP"
  check "get 이 화이트리스트 밖 effort 를 내면: exit 11 · CLI 미호출" "$(wrc fe)|$(wcalled fe)" "11|0"
  check "get 이 화이트리스트 밖 effort 를 내면: 태그 CHOICE-SCRIPT-ERROR(규칙 불일치 — 파일 손상 아님)" "$(wsaid fe 'CHOICE-SCRIPT-ERROR:')|$(wsaid fe 'CHOICE-UNREADABLE')" "1|0"
  fake_tree tree-fm 'echo "model=-x effort=high"'
  WX="$T/tree-fm/scripts/gpt-exec.sh"; wrun fm exec - w-sel "$T/wh-cfg"; WX="$WRAP"
  check "get 이 형식 밖 모델을 내면: exit 11 · CLI 미호출" "$(wrc fm)|$(wcalled fm)" "11|0"
  check "get 이 형식 밖 모델을 내면: 태그 CHOICE-SCRIPT-ERROR" "$(wsaid fm 'CHOICE-SCRIPT-ERROR:')" 1
  wrun flag-escape exec - w-bad "$T/wh-cfg" --model config --effort config
  check "손상 선택 + 플래그 config/config: 선택을 읽지 않아 exit 0 · 모델·effort 0(set 실패 뒤 우회로)" "$(wrc flag-escape)|$(leak flag-escape)" "0|0"

  # ── 게이트 순서 — 사용법·플래그 오류(10)가 선택 판독 실패(11)보다 먼저다(선택 판독은 게이트 2 뒤)
  wcell ord-usage - w-bad "$T/wh-cfg" exec
  check "손상 선택 + exec 에 --prompt-file 없음: exit 10" "$(wrc ord-usage)" 10
  wrun ord-effort exec - w-bad "$T/wh-cfg" --effort bogus
  check "손상 선택 + 불량 --effort: exit 10" "$(wrc ord-effort)" 10
  wrun ord-model exec - w-bad "$T/wh-cfg" --model -x
  check "손상 선택 + 불량 --model: exit 10" "$(wrc ord-model)" 10

  # ── 명시적 빈 값 · 불량 값 → exit 10 · CLI 미호출
  wrun e-empty exec - w-sel "$T/wh-cfg" --effort ''
  wrun e-bogus exec - w-none "$T/wh-cfg" --effort bogus
  wrun m-empty exec - w-sel "$T/wh-cfg" --model ''
  wrun m-dash exec - w-sel "$T/wh-cfg" --model -x
  wrun m-space exec - w-sel "$T/wh-cfg" --model 'fake beta'
  wrun m-quote exec - w-sel "$T/wh-cfg" --model 'a"b'
  for c in e-empty e-bogus m-empty m-dash m-space m-quote; do
    check "플래그 불량($c): exit 10 · CLI 미호출" "$(wrc "$c")|$(wcalled "$c")" "10|0"
  done

  # ── GPT-CHOICE 줄 — 호출마다 정확히 1줄 · stderr 에만(스트림 로그 아님) · WARN · GATE · --gpt-skill-path · 행머리 'model:' 없음
  wrun skp exec - w-sel "$T/wh-cfg" --gpt-skill demo --gpt-skill-path "$T/w-skill.md"
  check "GPT-CHOICE: 1줄(스킬 경로를 넘겨도 줄 모양 불변)" "$(gcount skp)|$(gline skp)" "1|GPT-CHOICE model=fake-beta (session) effort=xhigh (session)"
  check "GPT-CHOICE: 스트림 로그에는 없다" "$(grep -c 'GPT-CHOICE' "$T/w-skp/out.txt.stream.log" 2>/dev/null)" 0
  if grep -qE '^GPT-CHOICE .*(WARN|GATE|--gpt-skill-path)|^model:' "$T"/w-*/stderr 2>/dev/null; then
    no "GPT-CHOICE: 금지 토큰(WARN · GATE · --gpt-skill-path) 또는 행머리 'model:' 이 stderr 에 있다"
  else
    ok "GPT-CHOICE: 금지 토큰 · 행머리 'model:' 없음"
  fi

  # ── 두 스크립트의 MODEL_RE 가 같은 문자열 — 한쪽만 넓히면 set 이 거부하는 값을 래퍼가 받는다(또는 그 반대)
  check "MODEL_RE: 래퍼 = gpt-choice.sh" "$(re_parity)" same
}

for s in $SCOPES; do "run_$s"; done

echo
[ "$fail" -eq 0 ] && echo "choice: 전건 통과" || echo "choice: 실패 있음"
exit "$fail"
