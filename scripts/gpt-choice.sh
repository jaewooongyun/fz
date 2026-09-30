#!/bin/bash
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 같은 폴더의 autonomy_decide.py 만 `$(dirname "$0")` 로 부르고,
#   저장 위치·모델 목록은 환경변수(FZ_GPT_CHOICE_DIR · CODEX_HOME · HOME)로 정한다 (lint #N6 면제 형태 c).
#
# GPT 모델·effort 세션 선택 — 세션마다 한 번 받은 값을 검증해 저장하고, 래퍼(gpt-exec.sh)가 호출마다 읽는다.
#   정본: modules/gpt-strategy.md § 모델·effort 선택. 결정 순서(플래그 > 세션 선택 > config)는 래퍼 한 곳이 정한다.
#
# 왜 파일인가: export 한 값은 Bash 호출이 바뀌면 사라지고, 가짜 HOME 으로 뜨는 독립 런처에도 닿지 않는다.
#   세션 id 이름의 파일은 호출 사이에도 남고, 셸 스크립트인 래퍼가 그대로 읽을 수 있다.
#
# usage:
#   gpt-choice.sh options                                            선택지 JSON (stdout)
#   gpt-choice.sh get                                                현재 세션 선택 (stdout 'model=… effort=…')
#   gpt-choice.sh set --model <slug|config> --effort <level|config>  검증 뒤 기록 (stdout 'model=… effort=…')
#   gpt-choice.sh config                                             config.toml 최상위 값 (stdout 'model=<값|?> effort=<값|?>')
#
# 저장: ${FZ_GPT_CHOICE_DIR:-$HOME/.fz/gpt-choice}/${CLAUDE_CODE_SESSION_ID} — 'model=<slug|config>' 'effort=<level|config>' 두 줄.
#   값 config = 그 필드를 넘기지 않는다(config.toml 그대로). `set --model config --effort config` 는 "물었고 config" 센티넬이다.
# 입력: ${CODEX_HOME:-$HOME/.codex}/models_cache.json (options·set) · 같은 폴더 config.toml 의 최상위(첫 표 앞) model·model_reasoning_effort (options·set·config)
#
# exit:
#   get     0=선택 있음 · 3=없음(물어도 됨) · 4=없음 + 자율 모드(묻지 않음) · 11=선택 파일 손상(다시 묻고 set 으로 덮어쓴다)
#           5=저장할 수 없는 세션(세션 id 없음·불량 · FZ_GPT_CHOICE_DIR 가 절대 경로 아님) — 묻지 않고 config, stderr 안내
#   set     0=기록 · 10=검증 실패(fail-closed — 파일을 쓰지 않는다) · 11=사전조건(세션 id·저장 위치·모델 목록 캐시 없음 · 쓰기 실패)
#   options 0=JSON · 11=모델 목록 캐시 없음·판독 불가(묻지 않고 set config config 로 진행한다)
#   config  0=stdout 'model=<값|?> effort=<값|?>'(config.toml 이 없거나 값을 모르면 '?') · 11=python3 없음·판독 실패
#           래퍼(gpt-exec.sh)의 GPT-CHOICE 줄이 출처 config 인 필드의 값을 이것으로 읽는다 — config 판독 규칙(config_top)의 출처를 한 곳에 둔다.
#           모델 목록 캐시 · 선택 파일 · 세션 id 를 보지 않는다
#   (공통)  10=사용법
# ⛔ get 은 모델 목록 캐시를 읽지 않는다 — 독립 런처는 격리 CODEX_HOME 에서 래퍼를 띄우므로 캐시가 없을 수 있다.
#    모델별 검증은 set 한 곳에서 fail-closed 로 하고, get 은 형식·모델 문자셋·effort 화이트리스트만 본다.
set -u

die() { echo "gpt-choice: $2" >&2; exit "$1"; }
# ⛔ 값 옵션의 arity 가드 — 없으면 `set -u` 하에서 `$2` 참조가 exit 1(unbound variable)로 죽어 exit 계약(10)과 어긋난다
need() { [ "$1" -ge 2 ] || die 10 "$2 는 값이 필요하다"; }

# ⛔ 래퍼 게이트 0(gpt-exec.sh 의 effort case 줄)과 **같은 집합**이다 — 여기만 넓히면 set 은 통과하고 래퍼가 그 세션의
#    GPT 호출을 전부 exit 10 으로 막는다. 두 파일의 일치는 tests/fixtures/gpt/choice 가 대조한다.
#    캐시의 supported_reasoning_levels 는 이 집합과의 교집합으로만 쓴다(캐시에 none 같은 값이 있어도 받지 않는다).
EFFORT_WHITELIST="low medium high xhigh max ultra"
# ⛔ 모델 값은 래퍼가 TOML 문자열(-c 'model="<slug>"')로 넘긴다 — 따옴표·역슬래시·공백·개행은 문자열을 깨고,
#    '-' 로 시작하면 플래그로 읽힌다. 첫 글자 영숫자 + [A-Za-z0-9._:/-] 만 받는다(get · set · options 공통).
MODEL_RE='^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
# ⛔ 세션 id 는 파일 이름이 된다. '.'·'..' 는 [A-Za-z0-9._-] 를 통과하지만 폴더 자신·부모를 가리키므로 첫 글자를 영숫자로 한정한다.
#    '.' 로 시작하는 이름은 set 의 임시 파일 몫이라 선택 파일과 겹치지 않는다.
SID_RE='^[A-Za-z0-9][A-Za-z0-9._-]*$'

GPT_HOME="${CODEX_HOME:-${HOME:-}/.codex}"
CACHE="$GPT_HOME/models_cache.json"
CFG="$GPT_HOME/config.toml"
WHY="" CHOICE_DIR="" CHOICE_FILE="" SEL_MODEL="" SEL_EFFORT=""

is_effort() {   # 화이트리스트 원소인가
  local w
  for w in $EFFORT_WHITELIST; do [ "$1" = "$w" ] && return 0; done
  return 1
}
valid_model()  { [ "$1" = "config" ] || [[ "$1" =~ $MODEL_RE ]]; }
valid_effort() { [ "$1" = "config" ] || is_effort "$1"; }

# 저장 위치 — 성공하면 CHOICE_DIR·CHOICE_FILE 을 채우고, 실패하면 WHY 에 사유를 두고 1
# ⛔ 상대 경로·따옴표 안의 ~ 를 받으면 set(Lead cwd)·래퍼(호출 cwd)·런처(자기 cwd)가 서로 다른 폴더를 읽고 쓴다
resolve_file() {
  local sid="${CLAUDE_CODE_SESSION_ID:-}" dir="${FZ_GPT_CHOICE_DIR:-}"
  [ -n "$dir" ] || dir="${HOME:+$HOME/.fz/gpt-choice}"
  if [ -z "$sid" ]; then
    WHY="CLAUDE_CODE_SESSION_ID 가 없다"; return 1
  fi
  if ! [[ "$sid" =~ $SID_RE ]]; then
    WHY="세션 id 형식 불량('$sid') — [A-Za-z0-9._-] 만 받고 첫 글자는 영숫자다"; return 1
  fi
  case "$dir" in
    /*) ;;
    "") WHY="저장 위치를 정할 수 없다 — FZ_GPT_CHOICE_DIR 와 HOME 이 둘 다 비었다"; return 1 ;;
    *)  WHY="FZ_GPT_CHOICE_DIR 가 절대 경로가 아니다('$dir')"; return 1 ;;
  esac
  CHOICE_DIR="$dir"; CHOICE_FILE="$dir/$sid"
}

# 선택 파일 판독 — 정확히 두 줄 'model=…' 'effort=…'(이 순서)와 값 검증. 위반이면 1(손상)
read_choice() {
  local f="$1" n=0 line
  SEL_MODEL="" SEL_EFFORT=""
  { [ -f "$f" ] && [ -r "$f" ]; } || return 1
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    case "$n:$line" in
      1:model=*)  SEL_MODEL="${line#model=}" ;;
      2:effort=*) SEL_EFFORT="${line#effort=}" ;;
      *) return 1 ;;
    esac
  done < "$f"
  [ "$n" -eq 2 ] || return 1
  valid_model "$SEL_MODEL" && valid_effort "$SEL_EFFORT"
}

# ⛔ tmp+mv — 같은 폴더 안 rename 이라 읽는 쪽(래퍼)은 옛 파일이나 새 파일만 본다. 제자리 쓰기면 반쯤 쓴 파일을 읽고 exit 11 이 난다.
write_choice() {   # $1=모델 · $2=effort
  local tmp
  mkdir -p "$CHOICE_DIR" 2>/dev/null || return 1
  # ⛔ 저장 자리가 폴더(또는 폴더 링크)면 mv 가 그 안으로 옮기고 성공을 돌려준다 — 기록했다고 알리지만 get 은 계속 11 이다
  [ -d "$CHOICE_FILE" ] && return 1
  tmp="$(mktemp "$CHOICE_DIR/.tmp.XXXXXX" 2>/dev/null)" || return 1
  if printf 'model=%s\neffort=%s\n' "$1" "$2" > "$tmp" && mv -f "$tmp" "$CHOICE_FILE"; then
    return 0
  fi
  rm -f "$tmp"
  return 1
}

# 모델 목록 캐시 판독 — options(JSON 출력)와 set(검증)이 같은 판독을 쓴다. exit: 0 · 10(set 검증 실패) · 11(캐시 판독 불가)
#   config 모드는 config.toml 최상위 값(config_top — options · set 과 같은 판독)만 내고 캐시를 열기 전에 끝난다(exit 0)
choice_py() {   # $1=모드(options|set|config) · $2=모델 · $3=effort (options · config 는 빈 값)
  python3 - "$1" "$CACHE" "$CFG" "$EFFORT_WHITELIST" "$MODEL_RE" "$2" "$3" <<'PY'
import json
import re
import sys

mode, cache, cfg, wl, model_re, want_model, want_effort = sys.argv[1:8]
WL = wl.split()


def fail(code, msg):
    print(f"gpt-choice: {msg}", file=sys.stderr)
    sys.exit(code)


def config_top(path):
    # config.toml 최상위(첫 표 앞)의 model · model_reasoning_effort — 모르면 '?'.
    # ⛔ 줄 판독은 독립 런처(gpt_independent.sh)가 격리 config 로 model 줄을 옮길 때 · 래퍼가 default_permissions 를 읽을 때와
    #    같은 엄격한 형태다 — 줄 머리에서 key 로 시작하고 큰따옴표 값 하나로 끝나는 줄만 읽는다(들여쓰기 · 작은따옴표 · 줄 끝
    #    주석이면 '?'). 여기만 관대하면 격리 팔이 옮기지 못한 줄을 config 모델로 보고 검증해, 검증한 모델과 실제로 도는 모델이 갈린다.
    # ⛔ 표 안의 model 은 최상위 값이 아니다 — [profiles.x] 의 model 을 config 기본으로 내면 틀린 추천이 된다.
    # ⛔ profile 을 쓰면 그 프로필 값이 최상위를 덮으므로 둘 다 '?' 다 — 틀린 'config 기본' 표시보다 '모름'이 낫다.
    #    profile 줄 탐지만은 들여쓰기를 받는다 — 놓치면 틀린 값을 내고, 넓게 잡으면 '?' 일 뿐이다.
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, ValueError):
        return "?", "?"
    head = re.split(r"(?m)^\s*\[", text, maxsplit=1)[0]
    if re.search(r"(?m)^[ \t]*profile[ \t]*=", head):
        return "?", "?"

    def val(key):
        m = re.search(r'(?m)^' + key + r'\s*=\s*"([^"\n]*)"\s*$', head)
        return m.group(1) if m and m.group(1) else "?"

    return val("model"), val("model_reasoning_effort")


if mode == "config":
    # ⛔ 캐시를 열기 전에 끝낸다 — 래퍼는 격리 CODEX_HOME(캐시 없음)에서도 GPT-CHOICE 줄에 config 값을 적는다
    top_model, top_effort = config_top(cfg)
    print(f"model={top_model} effort={top_effort}")
    sys.exit(0)


try:
    with open(cache, encoding="utf-8") as fh:
        doc = json.load(fh)
except (OSError, ValueError) as e:
    fail(11, f"모델 목록 캐시를 읽지 못했다({type(e).__name__}): {cache}")
raw = doc.get("models") if isinstance(doc, dict) else None
if not isinstance(raw, list):
    fail(11, f"모델 목록 캐시에 models[] 가 없다: {cache}")


def levels(m):
    # 지원 effort ∩ 화이트리스트(화이트리스트 순). 캐시에 목록이 없으면 None — '모름'은 '없음'([])과 다르다.
    lv = m.get("supported_reasoning_levels") if isinstance(m, dict) else None
    if not isinstance(lv, list) or not lv:
        return None
    got = set()
    for x in lv:
        v = x.get("effort") if isinstance(x, dict) else x
        if isinstance(v, str):
            got.add(v)
    return [w for w in WL if w in got]


def label(m):
    d = m.get("display_name")
    return d.strip() if isinstance(d, str) and d.strip() else m["slug"]


by_slug, listed = {}, []
for m in raw:
    if not isinstance(m, dict) or not isinstance(m.get("slug"), str) or m["slug"] in by_slug:
        continue
    by_slug[m["slug"]] = m
    # ⛔ 저장할 수 없는 slug(문자셋 밖)는 선택지로 내지 않는다 — 고른 뒤 set 이 거부하면 한 번 더 묻게 된다
    if m.get("visibility") == "list" and re.fullmatch(model_re, m["slug"]):
        listed.append(m)

cfg_model, cfg_effort = config_top(cfg)
cm = by_slug.get(cfg_model) if cfg_model != "?" else None

if mode == "set":
    # 모델: 목록(visibility=list) 모델이거나 config 최상위 model 이어야 한다 — 숨김 모델도 config 가 쓰고 있으면 받는다
    if want_model not in ("config", cfg_model) and not any(m["slug"] == want_model for m in listed):
        fail(10, f"모델 거부 — '{want_model}' 는 목록(visibility=list)에도 config 최상위 model({cfg_model})에도 없다")
    # effort: 그 모델의 supported_reasoning_levels ∩ 화이트리스트. 지원 목록을 모르면 fail-closed
    if want_effort != "config":
        target = cfg_model if want_model == "config" else want_model
        sup = levels(by_slug.get(target)) if target != "?" else None
        if sup is None:
            fail(10, f"effort 거부 — 모델 '{target}' 의 지원 effort 를 모른다. effort 를 config 로 두거나 목록 모델을 고른다")
        if want_effort not in sup:
            fail(10, f"effort 거부 — '{want_effort}' 는 모델 '{target}' 에서 쓸 수 없다. 쓸 수 있는 값: {' '.join(sup) or '(없음)'}")
    elif want_model != "config" and cfg_effort in WL:
        # ⛔ effort=config 는 '넘기지 않음'이라 config 최상위 effort 가 고른 모델과 함께 쓰인다 — 그 모델이 지원하지 않는 것이
        #    캐시로 확인되면 여기서 막는다. 통과시키면 첫 GPT 호출에서 서버 거부로 늦게 드러난다(background 런처면 더 늦다).
        #    config effort 를 모르거나('?' · 화이트리스트 밖) 그 모델의 지원 목록을 모르면 막을 근거가 없어 받는다.
        sup = levels(by_slug.get(want_model))
        if sup is not None and cfg_effort not in sup:
            fail(10, f"effort 거부 — config effort '{cfg_effort}' 는 모델 '{want_model}' 에서 쓸 수 없다. effort 를 고르거나 모델을 config 로 둔다. 쓸 수 있는 값: {' '.join(sup) or '(없음)'}")
    sys.exit(0)

# 모델 질문: config 기본 + 목록 앞 3개(config 모델은 config 선택지와 겹치므로 뺀다). 나머지는 more — Other 로 입력할 수 있다.
others = [m for m in listed if m["slug"] != cfg_model]
top, more = others[:3], others[3:]
# ⛔ 지원 effort 를 모르는 모델(config 모델을 모름 · 캐시에 목록 없음)은 set 이 명시 effort 와의 짝을 exit 10 으로 거부한다 —
#    label 에 적어 두지 않으면 사용자가 '기본 모델 + effort 올리기'를 고르고, 같은 선택지로 다시 물어도 또 실패한다
ONLY_CFG = " · effort 는 config 만"
model_choices = [{"id": "config", "label": f"config 기본 ({cfg_model}{'' if levels(cm) is not None else ONLY_CFG})"}]
model_choices += [{"id": m["slug"], "label": label(m) + ("" if levels(m) is not None else ONLY_CFG)} for m in top]

# effort 질문: 모델과 한 번에 물으므로 명시 수준은 지원 목록을 아는 제시 모델(config 모델 + 위 3개) 모두가 지원하는 값만 낸다 —
#   교집합 ∩ 화이트리스트. 지원 목록을 모르는 모델은 교집합에서 빼고 모델 label 에 'effort 는 config 만' 을 붙인다.
#   config 값과 같은 수준은 config 선택지와 겹치므로 빼고, 3개를 넘으면 config 값(모르면 config 모델 기본값)에 가까운 순 — 동률이면 높은 쪽.
known = [k for k in (levels(m) for m in ([cm] if cm else []) + top) if k is not None]
common = [w for w in WL if known and all(w in k for k in known)]
cands = [w for w in common if w != cfg_effort]
center = cfg_effort if cfg_effort in WL else (cm or {}).get("default_reasoning_level")
if center not in WL:
    center = cands[len(cands) // 2] if cands else WL[0]
near = sorted(cands, key=lambda w: (abs(WL.index(w) - WL.index(center)), -WL.index(w)))
pick, rest = near[:3], near[3:]
# ⛔ config 선택지는 늘 낸다("물었고 config" 의 기본 경로 — 모델도 config 면 set 이 캐시를 읽지 않아 언제나 통한다). 다만 config
#    effort 를 지원하지 않는 제시 모델(위 3개)이 캐시로 확인되면 label 에 적는다 — 그 모델과 짝지으면 set 이 exit 10 이다.
#    명시 수준처럼 교집합으로 거를 수 없는 선택지라 빼지 않고 알린다.
cfg_bad = [label(m) for m in top if cfg_effort in WL and levels(m) is not None and cfg_effort not in levels(m)]
note = f" · {', '.join(cfg_bad)} 미지원" if cfg_bad else ""
effort_choices = [{"id": "config", "label": f"config 기본 ({cfg_effort}{note})"}]
effort_choices += [{"id": w, "label": w} for w in WL if w in pick]

out = {
    "config": {"model": cfg_model, "effort": cfg_effort},
    "models": [{"id": m["slug"], "label": label(m),
                "default_effort": m["default_reasoning_level"] if isinstance(m.get("default_reasoning_level"), str) else "?",
                "efforts": levels(m)} for m in listed],
    # skip = 선택지 2개 미만 — 고를 것이 없는 질문은 묻지 않는다
    "questions": {
        "model": {"skip": len(model_choices) < 2, "choices": model_choices, "more": [m["slug"] for m in more]},
        "effort": {"skip": len(effort_choices) < 2, "choices": effort_choices, "more": [w for w in WL if w in rest]},
    },
    "effort_whitelist": WL,
}
print(json.dumps(out, ensure_ascii=False, indent=2))
PY
}

cmd_options() {
  local rc
  [ $# -eq 0 ] || die 10 "options 는 인자를 받지 않는다: $1"
  command -v python3 >/dev/null 2>&1 || die 11 "python3 이 없어 모델 목록을 읽지 못한다"
  [ -f "$CACHE" ] || die 11 "모델 목록 캐시가 없다: $CACHE"
  choice_py options "" ""; rc=$?
  case "$rc" in
    0|11) exit "$rc" ;;
    *) die 11 "선택지를 만들지 못했다(python3 exit $rc)" ;;
  esac
}

# config.toml 최상위 model · model_reasoning_effort — 래퍼 GPT-CHOICE 표시용. 캐시 · 선택 파일 · 세션 id 를 보지 않는다
cmd_config() {
  local rc
  [ $# -eq 0 ] || die 10 "config 는 인자를 받지 않는다: $1"
  command -v python3 >/dev/null 2>&1 || die 11 "python3 이 없어 config.toml 을 읽지 못한다"
  choice_py config "" ""; rc=$?
  [ "$rc" -eq 0 ] || die 11 "config.toml 을 읽지 못했다(python3 exit $rc)"
}

cmd_get() {
  local rc
  [ $# -eq 0 ] || die 10 "get 은 인자를 받지 않는다: $1"
  resolve_file || die 5 "선택을 저장할 수 없는 세션이다 — ${WHY}. 묻지 않고 config 로 진행한다"
  if [ ! -e "$CHOICE_FILE" ] && [ ! -L "$CHOICE_FILE" ]; then
    # ⛔ 자율 판정은 원문 비교가 아니라 판정기(autonomy_decide.py)에 맡긴다 — ' Autonomous ' 같은 값을 원문으로 비교하면
    #    헤드리스 run 이 질문을 시도한다. 판정기는 공백·대소문자를 정규화하고 모르는 값은 묻기(ASK)로 본다.
    #    PROCEED(0) 만 4 이고 ASK·BLOCK·측정 실패·python3 부재는 전부 3 이다.
    python3 "$(dirname "$0")/autonomy_decide.py" --action gpt_model_choice --in-scope --reversible >/dev/null 2>&1; rc=$?
    [ "$rc" -eq 0 ] && exit 4
    exit 3
  fi
  read_choice "$CHOICE_FILE" \
    || die 11 "선택 파일 손상: $CHOICE_FILE — 'model=<slug|config>' 'effort=<level|config>' 두 줄이어야 한다. 다시 묻고 set 으로 덮어쓴다"
  printf 'model=%s effort=%s\n' "$SEL_MODEL" "$SEL_EFFORT"
}

cmd_set() {
  local m="" e="" has_m="" has_e="" rc
  while [ $# -gt 0 ]; do
    case "$1" in
      --model)  need $# "--model";  m="$2"; has_m=1; shift 2 ;;
      --effort) need $# "--effort"; e="$2"; has_e=1; shift 2 ;;
      *) die 10 "알 수 없는 인자: $1" ;;
    esac
  done
  { [ -n "$has_m" ] && [ -n "$has_e" ]; } || die 10 "set 은 --model 과 --effort 가 모두 필요하다 (값 config = 그 필드를 넘기지 않음)"
  resolve_file || die 11 "선택을 저장할 수 없다 — $WHY"
  # ⛔ config config 는 캐시·config 를 읽지 않는다 — 신규 설치·격리 CODEX_HOME 처럼 캐시가 없어도 "물었고 config" 를 남겨야
  #    스킬마다 다시 묻지 않는다. options 가 exit 11 일 때와 set 이 거듭 exit 10 일 때의 fallback 도 이것이다.
  if [ "$m" != "config" ] || [ "$e" != "config" ]; then
    valid_model "$m" || die 10 "모델 거부 — 형식 불량 '$m' (첫 글자 영숫자 + [A-Za-z0-9._:/-], 또는 config)"
    valid_effort "$e" || die 10 "effort 거부 — '$e' 는 ${EFFORT_WHITELIST// /|}|config 가 아니다"
    command -v python3 >/dev/null 2>&1 || die 11 "python3 이 없어 모델 목록으로 검증하지 못한다 — 기록하지 않는다"
    [ -f "$CACHE" ] || die 11 "모델 목록 캐시가 없다: $CACHE — 캐시 없이 저장할 수 있는 것은 config config 뿐이다"
    choice_py set "$m" "$e"; rc=$?
    case "$rc" in
      0) ;;
      10|11) exit "$rc" ;;
      *) die 11 "모델 목록 검증을 끝내지 못했다(python3 exit $rc) — 기록하지 않는다" ;;
    esac
  fi
  write_choice "$m" "$e" || die 11 "선택 파일을 쓰지 못했다: $CHOICE_FILE"
  printf 'model=%s effort=%s\n' "$m" "$e"
}

SUB="${1:-}"
[ $# -gt 0 ] && shift
# ⛔ `${1+"$@"}` — 인자가 없을 때 set -u 아래에서 "$@" 확장을 피하는 관용구(구버전 bash 호환)
case "$SUB" in
  options) cmd_options ${1+"$@"} ;;
  get)     cmd_get ${1+"$@"} ;;
  set)     cmd_set ${1+"$@"} ;;
  config)  cmd_config ${1+"$@"} ;;
  *)       die 10 "하위 명령은 options|get|set|config — 받은 값: '$SUB'" ;;
esac
