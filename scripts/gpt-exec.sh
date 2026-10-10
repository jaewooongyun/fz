#!/bin/bash
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 작업 대상은 `--cd`로 받아 게이트 11에서
#   존재를 검증하고, 스키마·프롬프트도 호출자가 절대경로로 넘긴다 (lint #N6 면제 형태 c).
#
# gpt 호출 hygiene 실행체 — modules/fz-gpt-bash-hygiene.md §8의 구현
#
# 왜 스크립트인가: hygiene 규칙은 전부 binary(pass/fail)다
#   (guides/skill-authoring.md §11 "결과가 binary인가? → 스크립트").
#   산문 체크리스트는 호출자가 매번 기억해야 하고, 실측상 누락이 재발했다:
#   ① `review` + PROMPT 인자 충돌로 exit 2 (core.md:36에 문서화돼 있었음)
#   ② 래퍼 마지막 문장이 exit code를 덮어 측정 실패를 "결과 0건"으로 오독
#   본 스크립트는 ①을 구조적으로 거부하고 ②를 게이트로 차단한다.
#
# usage:
#   gpt-exec.sh review --cd DIR --out FILE (--base BR | --uncommitted | --commit SHA)
#                        [--model M] [--effort E] [--schema F] [--title T] [--ephemeral]
#                        ⛔ review 는 --add-dir 미지원 (codex exec review 가 거부) — exec 모드를 쓸 것
#                        [--expected-branch B] [--gpt-skill N] [--gpt-skill-path P]
#   gpt-exec.sh exec   --cd DIR --out FILE --prompt-file F
#                        [--model M] [--effort E] [--schema F] [--add-dir D] [--gpt-skill N] [--gpt-skill-path P] [--inject-skill F]
#   gpt-exec.sh resume --cd DIR --out FILE --prompt-file F --session-file PREV_OUT.session
#                        [--model M] [--effort E] [--schema F] [--gpt-skill N] [--gpt-skill-path P]
#                        ⛔ 이전 exec/review 가 남긴 `${OUT}.session`(UUID) 으로 **그 세션**을 잇는다.
#                           `--last` 를 쓰지 않는다 — 사이에 다른 GPT 실행이 끼면 엉뚱한 세션을 잇는다.
#   (모든 모드) 성공 시 스트림 로그의 `session id:` 를 `${OUT}.session` 에 기록한다.
#   --model · --effort: 보통 넘기지 않는다. effort 기본값 없음 — 정본 modules/gpt-strategy.md § 모델·effort 선택
#                     필드마다 플래그 > 세션 선택(같은 폴더 gpt-choice.sh get) > config.toml(넘기지 않음) 순으로 정한다. resume 도 같다 —
#                     선택을 바꾼 뒤의 resume 은 새 값으로 돈다(원래 모델로 이으려면 플래그로 고정한다). 값 config = 그 필드를 넘기지 않는다.
#                     적용값·출처는 호출 직전 stderr 한 줄 'GPT-CHOICE model=<값> (flag|session|config) effort=<값> (flag|session|config)'
#                     — 출처 config 인 필드는 config.toml 최상위 값이다(모르면 '?'). 세션 선택을 읽지 못하면 exit 11.
#   --gpt-skill-path: 계측 전용(모든 모드) — 호출부가 해석한 SKILL.md 경로다. exec·resume 는 그 본문이 최종 프롬프트에
#                     들어 있는지만 판정해 injected 열에 적고, 넣지는 않는다.
#   --inject-skill:   exec 전용 주입 — 그 SKILL.md 본문을 프롬프트 앞에 넣는다(멱등). resume 은 세션 이력에 본문이
#                     이미 있고 review 는 프롬프트가 없어 둘 다 exit 10 이다.
#   --config-permissions: sandbox_mode 를 넘기지 않고 $CODEX_HOME/config.toml 의 권한 프로필(default_permissions)을 쓴다.
#                     넘기면 프로필의 경로 deny 를 덮는다(F-348). 프로필이 `extends = ":read-only"` 가 아니면 exit 11.
#
# exit: 0=성공(결과 유효) / 10=사용법·플래그 충돌 / 11=사전조건(세션 선택 판독 실패 포함) / 12=gpt 비정상종료
#       13=출력 없음·빈 파일 / 14=출력이 계약 위반(파싱·필수키·타입·enum)
#   ⛔ 10~14는 전부 **측정 실패**다 — "이슈 0건"으로 해석하면 안 된다.
#   ⛔ 12 에는 진행 감시 종료도 든다(F-364) — 그 호출의 스트림 로그(${OUT}.stream.log) 크기가 FZ_GPT_IDLE_SEC(기본 900 · 0 = 끔)초
#      동안 그대로면 CLI 자손 트리를 TERM → KILL 하고 12 로 끝낸다. 가르는 표지는 메시지 머리 토큰 `GPT-IDLE` · 텔레메트리 9열 `idle` 이다
#      (gpt 종료코드 열은 143 같은 신호값이라 CLI 스스로의 실패와 구분되지 않는다). FZ_GPT_IDLE_SEC 형식 불량(0 이상 정수 아님)은 10
set -u

die() { echo "GATE-FAIL($1): $2" >&2; exit "$1"; }
# ⛔ 값 옵션의 arity 가드 — 없으면 `set -u` 하에서 `$2` 참조가 **exit 1(unbound variable)** 로 죽어
#    문서상 게이트 10과 어긋난다 (2026-08-09 감사 ISSUE-011: `review --cd` 가 exit 1이었다).
need() { [ "$1" -ge 2 ] || die 10 "$2 는 값이 필요하다"; }
# ⛔ gpt-choice.sh 의 MODEL_RE 와 **같은 문자열**이다 — 모델은 TOML 문자열(-c 'model="<slug>"')로 넘기므로 따옴표·역슬래시·공백·개행은
#    문자열을 깨고, '-' 로 시작하면 플래그로 읽힌다. 두 파일의 일치는 tests/fixtures/gpt/choice(--scope wrapper)가 대조한다.
MODEL_RE='^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$'
CHOICE_RE='^model=([^ ]+) effort=([^ ]+)$'   # gpt-choice.sh get · config 의 stdout 한 줄

MODE="${1:-}"; shift || true
case "$MODE" in
  review|exec|resume) ;;
  *) die 10 "mode는 review|exec|resume — 받은 값: '${MODE}'" ;;
esac

CD="" OUT="" PROMPT_FILE="" SCHEMA="" MODEL="" MODEL_SET="" EFFORT="" EFFORT_SET="" TITLE="" EPHEMERAL="" EXPECTED_BRANCH="" GPT_SKILL="" GPT_SKILL_PATH="" INJECT_SKILL="" SESSION_FILE="" CONFIG_PERMS=""
ADD_DIRS=()
SCOPE_ARGS=()          # ⛔ 문자열이 아니라 **배열** — 비인용 확장의 단어분할·glob를 차단한다
SCOPE_KIND=""          # base|uncommitted|commit — 중복 지정을 거부하기 위해 기록
SCOPE_REF=""

set_scope() {          # $1=kind  $2=ref(옵션)
  [ -z "$SCOPE_KIND" ] || die 10 "review 스코프는 하나만 — 이미 '--$SCOPE_KIND' 가 지정됐다"
  SCOPE_KIND="$1"; SCOPE_REF="${2:-}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --cd)              need $# "--cd";              CD="$2"; shift 2 ;;
    --out)             need $# "--out";             OUT="$2"; shift 2 ;;
    --prompt-file)     need $# "--prompt-file";     PROMPT_FILE="$2"; shift 2 ;;
    --schema)          need $# "--schema";          SCHEMA="$2"; shift 2 ;;
    --effort)          need $# "--effort";          EFFORT="$2"; EFFORT_SET=1; shift 2 ;;
    --model)           need $# "--model";           MODEL="$2"; MODEL_SET=1; shift 2 ;;
    --title)           need $# "--title";           TITLE="$2"; shift 2 ;;
    --add-dir)         need $# "--add-dir";         ADD_DIRS+=("$2"); shift 2 ;;
    --expected-branch) need $# "--expected-branch"; EXPECTED_BRANCH="$2"; shift 2 ;;
    # --gpt-skill = 역할 이름 · --gpt-skill-path = 호출부가 해석한 SKILL.md 경로 — 둘 다 계측 전용(gpt 에 전달하지 않는다).
    #   resolved 해석은 호출부 get_gpt_skill_path 소관. 주입은 --inject-skill 하나만 한다(F-335 — 한 플래그가 모드마다 뜻이 달랐다).
    --gpt-skill)       need $# "--gpt-skill";       GPT_SKILL="$2"; shift 2 ;;
    --gpt-skill-path)  need $# "--gpt-skill-path";  GPT_SKILL_PATH="$2"; shift 2 ;;
    --inject-skill)    need $# "--inject-skill";    INJECT_SKILL="$2"; shift 2 ;;
    --base)            need $# "--base";            set_scope base "$2"
                       SCOPE_ARGS=(--base "$2");   shift 2 ;;
    --commit)          need $# "--commit";          set_scope commit "$2"
                       SCOPE_ARGS=(--commit "$2"); shift 2 ;;
    --uncommitted)     set_scope uncommitted
                       SCOPE_ARGS=(--uncommitted); shift ;;
    --ephemeral)       EPHEMERAL="--ephemeral";     shift ;;
    --config-permissions) CONFIG_PERMS=1;            shift ;;
    --session-file)    need $# "--session-file";    SESSION_FILE="$2"; shift 2 ;;
    *) die 10 "알 수 없는 인자: $1" ;;
  esac
done

# ── 사전 게이트 0: effort 화이트리스트 (2026-09-06 신설) · 모델 형식 — **플래그 값만** 본다(순수 검사). 세션 선택 값은 게이트 2 뒤 결정에서 같은 effort_ok 로 본다
# ⛔ 왜: Codex CLI 는 무효 effort 를 **로컬에서 거부하지 않는다**. 실측 —
#    `codex exec -c model_reasoning_effort=bogus` 가 배너에 `reasoning effort: bogus` 를 찍고
#    서버까지 왕복한 뒤에야 실패한다. 오타가 조용히 통과하면 "올렸다고 믿는데 무효"가 된다.
# 값 출처 ① [verified: official, raw] OpenAI Model guidance — API 는 low/medium/high/xhigh/max (`none` 은 HTTP 400)
#          ② [verified: measured] `~/.codex/models_cache.json` (CLI 0.153.4 가 서버에서 받은 목록) —
#             `gpt-6-astra` 의 supported_reasoning_levels 에 **`ultra` 실재**
#             ("Maximum reasoning with automatic task delegation"). gpt-5.6 계열도 동일, gpt-5.5 는 xhigh 까지.
# ⛔ 최초판은 문서에 `ultra` 가 없다는 이유로 제외했으나 **캐시 실측이 그것을 뒤집었다** — 문서보다 캐시가 최신이다.
# ⚠️ 구버전 CLI 나 ultra 미지원 모델에서는 서버가 거부한다(로컬 게이트가 아니라 호출 시점에 드러남).
# ⛔ gpt-choice.sh EFFORT_WHITELIST 와 같은 집합이다 — 한쪽만 넓히면 set 이 받은 값을 래퍼가 막는다(또는 그 반대).
#    두 파일의 일치는 tests/fixtures/gpt/choice 가 아래 case 줄로 대조한다. 플래그 값(여기)과 세션 선택 값(게이트 2 뒤 결정)이 이 함수 하나를 쓴다.
effort_ok() {
  case "$1" in
    low|medium|high|xhigh|max|ultra) return 0 ;;
  esac
  return 1
}
# 값 config = 그 필드를 넘기지 않는다. ⛔ 명시적 빈 값(--effort '' · --model '')도 10 이다 — 호출부의 빈 변수를 조용히 config 로 돌리면
#    의도한 값이 빠진 것을 아무도 모른다.
if [ -n "$EFFORT_SET" ] && [ "$EFFORT" != "config" ] && ! effort_ok "$EFFORT"; then
  die 10 "--effort 는 low|medium|high|xhigh|max|ultra 중 하나 또는 config — 받은 값: '$EFFORT'"
fi
if [ -n "$MODEL_SET" ] && [ "$MODEL" != "config" ] && ! [[ "$MODEL" =~ $MODEL_RE ]]; then
  die 10 "--model 형식 불량 '$MODEL' — 첫 글자 영숫자 + [A-Za-z0-9._:/-] 128자 이하, 또는 config"
fi
# 진행 감시 임계(초) — 0 = 끔. ⛔ 형식을 여기서 막는다 — 불량 값이 감시 루프의 산술 비교까지 가면 bash 오류로 exit 1 이 되어 10~14 계약 밖이다
IDLE_SEC="${FZ_GPT_IDLE_SEC:-900}"
case "$IDLE_SEC" in
  ''|*[!0-9]*|??????????*) die 10 "FZ_GPT_IDLE_SEC 는 0 이상 정수(초 · 9자리 이하 · 0 = 감시 끔) — 받은 값: '$IDLE_SEC'" ;;
esac

# ── 사전 게이트 1: 플래그 상호 배타 (실측 근거: codex 0.144.1)
#    `codex exec review`는 flag-only — PROMPT positional과 --uncommitted/--base가 충돌한다.
if [ "$MODE" = "review" ] && [ -n "$PROMPT_FILE" ]; then
  die 10 "review 모드는 PROMPT를 받지 않는다 (flag-only). 커스텀 지시가 필요하면 mode=exec 사용 — modules/fz-gpt-subcommands-core.md §review"
fi
[ "$MODE" = "review" ] && [ -z "$SCOPE_KIND" ] && die 10 "review 모드는 --base|--uncommitted|--commit 중 하나 필수"
[ "$MODE" = "exec" ] && [ -z "$PROMPT_FILE" ] && die 10 "exec 모드는 --prompt-file 필수"
[ "$MODE" = "exec" ] && [ -n "$SCOPE_KIND" ] && die 10 "exec 모드에 review 스코프 플래그를 줄 수 없다 (diff는 프롬프트에 인라인)"
# ── resume: 이을 세션을 **명시**로만 받는다 (--last 금지 — 동시 실행 시 다른 세션을 잇는다)
if [ "$MODE" = "resume" ]; then
  [ -n "$PROMPT_FILE" ] || die 10 "resume 모드는 --prompt-file 필수"
  [ -n "$SCOPE_KIND" ] && die 10 "resume 모드에 review 스코프 플래그를 줄 수 없다"
  [ "${#ADD_DIRS[@]}" -gt 0 ] && die 10 "resume 모드는 --add-dir 미지원 (GPT CLI resume 가 받지 않는다)"
  [ -n "$SESSION_FILE" ] || die 10 "resume 모드는 --session-file 필수 (이전 exec/review 의 \${OUT}.session)"
  [ -s "$SESSION_FILE" ] || die 10 "세션 파일 없음/빈 파일: $SESSION_FILE"
  SESSION_ID="$(tr -d '[:space:]' < "$SESSION_FILE")"
  printf '%s' "$SESSION_ID" | grep -qE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' \
    || die 10 "세션 파일 내용이 UUID 가 아니다: '$SESSION_ID'"
elif [ -n "$SESSION_FILE" ]; then
  die 10 "--session-file 은 resume 모드 전용"
fi

# ── 사전 게이트 2: 경로·파일 존재
[ -n "$CD" ] || die 10 "--cd 필수"
# ⛔ review 는 `--add-dir` 를 받지 않는다 (F-015) — 조용히 무시하면 "컨텍스트 확장됨"으로 오인된다.
[ "$MODE" = "review" ] && [ "${#ADD_DIRS[@]}" -gt 0 ] \
  && die 10 "review 모드는 --add-dir 미지원 (codex exec review 가 거부). exec 모드를 쓰거나 --add-dir 를 빼라"
[ -d "$CD" ] || die 11 "--cd 디렉토리 없음: $CD"
[ -n "$OUT" ] || die 10 "--out 필수"
[ -n "$PROMPT_FILE" ] && { [ -s "$PROMPT_FILE" ] || die 11 "프롬프트 파일 없음/빈 파일: $PROMPT_FILE"; }
[ -n "$SCHEMA" ] && { [ -s "$SCHEMA" ] || die 11 "스키마 파일 없음: $SCHEMA"; }
# ⛔ 주입은 exec 전용이다 — resume 은 세션 이력에 본문이 이미 있어 다시 넣으면 두 번이 되고(리뷰 A:A9), review 는 프롬프트가 없다.
if [ -n "$INJECT_SKILL" ]; then
  [ "$MODE" = "exec" ] || die 10 "--inject-skill 은 exec 전용 — ${MODE} 는 본문을 넣을 프롬프트가 없거나(review) 세션 이력에 이미 있다(resume)"
  [ -z "$GPT_SKILL_PATH" ] || [ "$GPT_SKILL_PATH" = "$INJECT_SKILL" ] \
    || die 10 "--inject-skill 과 --gpt-skill-path 가 다른 파일을 가리킨다 — 어느 본문을 판정할지 정할 수 없다"
fi
# ⛔ exec·resume 는 본문 파일을 읽어 판정한다(넣든 확인만 하든) — 경로가 있는데 파일이 없으면 역할 없이 도는 run 을 호출 전에 막는다.
#    빈 문자열은 "해석 실패 → 일반 프롬프트 폴백" 이라 여기서 막지 않는다(fallback=1 로 기록된다).
SKILL_SRC="${INJECT_SKILL:-$GPT_SKILL_PATH}"
if [ -n "$SKILL_SRC" ] && [ "$MODE" != "review" ]; then
  # ⛔ `-s` 는 디렉터리·공백뿐 파일도 통과시킨다 — 빈 본문은 `*""*` 가 늘 참이라 주입 없이 injected=1 이 됐다(v4.40.0 리뷰)
  { [ -f "$SKILL_SRC" ] && [ -r "$SKILL_SRC" ] && grep -q '[^[:space:]]' "$SKILL_SRC"; } \
    || die 11 "스킬 본문 경로가 읽을 수 있는 본문 파일이 아니다(없음·디렉터리·공백뿐): $SKILL_SRC"
fi
# ── 사전 게이트 2.5: 모델·effort 결정 — 필드마다 플래그 > 세션 선택 > config.toml(넘기지 않음). effort 기본값 없음 — 정본 modules/gpt-strategy.md § 모델·effort 선택
# ⛔ 왜 래퍼 한 곳인가: 호출부마다 붙이면 한 곳만 빠져도 조용히 config 로 돈다. 적용값·출처는 호출 직전 stderr GPT-CHOICE 한 줄로 늘 보인다.
# ⛔ 사용법·경로 게이트(0~2) **뒤**에 둔다 — 선택 판독은 자식 프로세스(gpt-choice.sh get → autonomy_decide.py)다. 앞에 두면 선택 파일이
#    손상된 세션에서 사용법 오류(10)가 11 로 가려져, Lead 가 사용자에게 먼저 다시 묻고 진짜 호출 버그는 그 뒤에야 드러난다.
MODEL_SRC="" EFFORT_SRC=""
[ -n "$MODEL_SET" ] && MODEL_SRC="flag"
[ -n "$EFFORT_SET" ] && EFFORT_SRC="flag"
# ⛔ 세션 선택은 같은 폴더 gpt-choice.sh get 으로만 읽는다(판독·검증 규칙이 그 한 곳이다) — `bash` 로 부른다(실행 비트 비의존).
#    get exit: 0=적용 · 3/4/5=선택 없음(config) · 그 밖(11 손상 · 126/127 스크립트 부재 포함)=exit 11.
#    ⛔ 읽지 못한 선택을 config 로 넘기면 사용자가 고른 것이 아닌 모델·effort 로 조용히 돈다 — fail-closed.
#    ⛔ stdout 만 파싱한다(get 계약 = stdout 한 줄). stderr 를 섞으면 자식 셸 경고 한 줄에 정상 선택이 매 호출 11 이 되고 set 으로
#       덮어써도 풀리지 않는다. stderr 는 임시 파일로 받아 비정상 exit 일 때만 메시지에 붙인다(3/4/5 의 안내는 버린다 — 출처는
#       GPT-CHOICE 줄이 적는다). 두 필드가 모두 플래그면 읽지 않는다 — 쓰지 않을 값이다.
#    get 이 검증한 값도 여기서 다시 본다(모델 = MODEL_RE · effort = effort_ok) — 두 규칙이 어긋나면 스크립트 오류(11)로 멈춘다.
# ⛔ 11 의 처방은 원인마다 다르다 — 메시지 머리의 ASCII 태그로 가른다(문서는 한국어 문구가 아니라 태그를 인용한다):
#    CHOICE-UNREADABLE  = get exit 11(선택 파일 손상) → Lead 는 다시 묻고 set 으로 덮어쓴다
#    CHOICE-SCRIPT-ERROR = 그 밖(스크립트 부재·오류 · get 출력과 이 규칙의 불일치) → 다시 물어도 풀리지 않는다 — 묻지 않는다
CHOICE_FIX="이 세션의 GPT 호출은 --model config --effort config 로 부르거나(두 필드가 플래그면 선택을 읽지 않는다) gpt-choice.sh 를 고친다"
# ⛔ 모델 목록 캐시는 읽지 않는다 — 독립 런처는 격리 CODEX_HOME(캐시 없음)에서 래퍼를 띄운다. 모델별 검증은 gpt-choice.sh set 한 곳이 한다.
if [ -z "$MODEL_SRC" ] || [ -z "$EFFORT_SRC" ]; then
  CHOICE_ERR="$(mktemp "${TMPDIR:-/tmp}/fz-gpt-choice.XXXXXX" 2>/dev/null)" || die 11 "선택 판독용 임시 파일을 만들지 못했다(TMPDIR='${TMPDIR:-}')"
  CHOICE_OUT="$(bash "$(dirname "$0")/gpt-choice.sh" get 2> "$CHOICE_ERR")"; CHOICE_RC=$?
  CHOICE_MSG="$(head -3 "$CHOICE_ERR" 2>/dev/null | tr '\n' ' ')"; rm -f "$CHOICE_ERR"
  case "$CHOICE_RC" in
    0)
      [[ "$CHOICE_OUT" =~ $CHOICE_RE ]] \
        || die 11 "CHOICE-SCRIPT-ERROR: 선택 스크립트 오류 — 다시 묻지 않는다. $CHOICE_FIX (get 출력 형식 불량: '$CHOICE_OUT')"
      S_MODEL="${BASH_REMATCH[1]}" S_EFFORT="${BASH_REMATCH[2]}"
      [ "$S_MODEL" = "config" ] || [[ "$S_MODEL" =~ $MODEL_RE ]] \
        || die 11 "CHOICE-SCRIPT-ERROR: 선택 스크립트 오류 — 다시 묻지 않는다. $CHOICE_FIX (get 이 낸 모델이 래퍼 형식 밖: '$S_MODEL')"
      [ "$S_EFFORT" = "config" ] || effort_ok "$S_EFFORT" \
        || die 11 "CHOICE-SCRIPT-ERROR: 선택 스크립트 오류 — 다시 묻지 않는다. $CHOICE_FIX (get 이 낸 effort 가 래퍼 화이트리스트 밖: '$S_EFFORT')"
      [ -n "$MODEL_SRC" ] || { MODEL="$S_MODEL"; MODEL_SRC="session"; }
      [ -n "$EFFORT_SRC" ] || { EFFORT="$S_EFFORT"; EFFORT_SRC="session"; } ;;
    3|4|5) ;;
    11) die 11 "CHOICE-UNREADABLE: 선택 파일을 읽지 못했다 — Lead 는 다시 묻고 gpt-choice.sh set 으로 덮어쓴다 (get: ${CHOICE_MSG:-출력 없음})" ;;
    *) die 11 "CHOICE-SCRIPT-ERROR: 선택 스크립트 오류 — 다시 묻지 않는다. $CHOICE_FIX (get exit $CHOICE_RC: ${CHOICE_MSG:-출력 없음})" ;;
  esac
fi
# 값 config = 그 필드를 넘기지 않는다(플래그 · 세션 선택 공통) — 출처는 config 로 적는다
[ "$MODEL" = "config" ] && MODEL=""
[ "$EFFORT" = "config" ] && EFFORT=""
[ -n "$MODEL" ] || MODEL_SRC="config"
[ -n "$EFFORT" ] || EFFORT_SRC="config"
# ⛔ --config-permissions 는 쓰기 금지 강제를 config 프로필에 맡긴다 — 그 프로필이 read-only 를 확장하는지 호출 전에 본다.
#    `default_permissions` 는 첫 table 앞에 있어야 한다(뒤에 두면 앞 table 의 키가 된다 — S11 ⑦ R11).
if [ -n "$CONFIG_PERMS" ]; then
  CFG="${CODEX_HOME:-}/config.toml"
  [ -n "${CODEX_HOME:-}" ] && [ -f "$CFG" ] || die 11 "--config-permissions 는 CODEX_HOME 의 config.toml 이 필요하다: '${CODEX_HOME:-}'"
  PERMS_ERR="$(python3 - "$CFG" <<'PY'
import re, sys
t = open(sys.argv[1], encoding="utf-8").read()
head = re.split(r"(?m)^\s*\[", t, maxsplit=1)[0]
m = re.search(r'(?m)^default_permissions\s*=\s*"([^"]+)"\s*$', head)
if not m:
    sys.exit("default_permissions 가 첫 table 앞에 없다")
name = m.group(1)
sec = re.search(rf'(?ms)^\[permissions\.{re.escape(name)}\]\s*$(.*?)(?=^\s*\[|\Z)', t)
if not sec or not re.search(r'(?m)^extends\s*=\s*":read-only"\s*$', sec.group(1)):
    sys.exit(f"권한 프로필 '{name}' 이 extends = \":read-only\" 가 아니다 — 쓰기 금지가 사라진다")
PY
)" || die 11 "--config-permissions: ${PERMS_ERR:-권한 프로필 판정 실패}"
fi
command -v codex >/dev/null 2>&1 || die 11 "codex CLI 미설치"

# ── 사전 게이트 3: (폐지 2026-09-25) trust_level 경고 — 래퍼가 read-only 를 스스로 강제하므로(아래 ARGS) "read-only 로 강제될 수 있다" 는 경고는 거짓 경보였다

# ── 사전 게이트 4: git repo 판정 → skip flag (hygiene §2)
IS_REPO=1
git -C "$CD" rev-parse --git-dir >/dev/null 2>&1 || IS_REPO=0
SKIP_FLAG=""
[ "$IS_REPO" -eq 1 ] || SKIP_FLAG="--skip-git-repo-check"

# ── 사전 게이트 5: Base Verification Gate (hygiene §5.5 구현)
#    ⛔ 신설 근거(감사 ISSUE-012): 이 스크립트를 의무화하면서 §5.5를 생략하면 **의무화가 §5.5를 우회시킨다**.
#    ⛔ `merge-base A B` 는 공통 조상 존재만 증명한다 → 도달성이 필요하면 `--is-ancestor` 를 쓴다 (ISSUE-PLAN-011).
if [ "$MODE" = "review" ] && [ "$IS_REPO" -eq 1 ]; then
  CUR_BRANCH="$(git -C "$CD" branch --show-current 2>/dev/null || echo '?')"
  HEAD_SHA="$(git -C "$CD" rev-parse --short HEAD 2>/dev/null || echo '?')"
  if [ -n "$EXPECTED_BRANCH" ] && [ "$CUR_BRANCH" != "$EXPECTED_BRANCH" ]; then
    die 11 "branch mismatch: current=$CUR_BRANCH expected=$EXPECTED_BRANCH"
  fi
  # ⛔ 스코프별로 변경 파일 집합을 **분리 산출**하고 **잘리기 전에** 센다
  case "$SCOPE_KIND" in
    base)
      git -C "$CD" rev-parse --verify --quiet "$SCOPE_REF" >/dev/null \
        || die 11 "base '$SCOPE_REF' 가 존재하지 않는다"
      git -C "$CD" merge-base --is-ancestor "$SCOPE_REF" HEAD 2>/dev/null \
        || echo "WARN: base '$SCOPE_REF' 가 HEAD의 조상이 아니다 (분기된 브랜치) — diff가 예상과 다를 수 있다" >&2
      FILES="$(git -C "$CD" diff --name-only "$SCOPE_REF"...HEAD 2>/dev/null)" ;;
    commit)
      git -C "$CD" rev-parse --verify --quiet "$SCOPE_REF" >/dev/null \
        || die 11 "commit '$SCOPE_REF' 가 존재하지 않는다"
      FILES="$(git -C "$CD" show --name-only --pretty=format: "$SCOPE_REF" 2>/dev/null)" ;;
    uncommitted)
      FILES="$(
        { git -C "$CD" diff --name-only; git -C "$CD" diff --cached --name-only;
          git -C "$CD" ls-files --others --exclude-standard; } 2>/dev/null | sort -u
      )" ;;
  esac
  N_FILES="$(printf '%s\n' "$FILES" | grep -c . || true)"
  echo "▶ 분석 기준 — branch=$CUR_BRANCH HEAD=$HEAD_SHA scope=$SCOPE_KIND${SCOPE_REF:+ ref=$SCOPE_REF} changed_files=${N_FILES}개"
  [ "$N_FILES" -gt 0 ] || echo "WARN: 변경 파일 0개 — 리뷰 대상이 비어 있다" >&2
fi

# ⛔ 공용 ARGS에는 **review·exec 양쪽이 수용하는 플래그만** 넣는다 (F-015).
#    `-C/--cd` 와 `--add-dir` 는 `codex exec review` 가 거부한다 → exec 전용 배열로 분리.
#    검증: scripts/check-gpt-flags.sh (양 서브커맨드 --help 전수 대조)
# ⛔ read-only 강제 — fz GPT 호출은 검증 전용이다. 프롬프트 문구는 경계가 아니고, 사용자 config.toml 의 sandbox_mode 가
#    쓰기 가능이면 검증 호출이 레포를 고칠 수 있다. `-c` 는 session 층이라 사용자 config 보다 우선한다(2026-09-25 실측).
#    `sandbox_permissions` 는 CLI 0.157 이 무시한다고 출력하지만 구버전 호환을 위해 남긴다.
ARGS=(-c 'sandbox_mode="read-only"' -c "sandbox_permissions=[\"disk-full-read-access\"]")
# ⛔ --config-permissions — sandbox_mode 를 넘기면 config 권한 프로필의 경로 deny 가 지워진다(F-348 · 실측 09-28). 쓰기 금지는 위 사전 게이트가 본 프로필이 맡는다
[ -n "$CONFIG_PERMS" ] && ARGS=()
# ⛔ 모델·effort 는 값이 있을 때만 넘긴다 — 비면 config.toml 그대로다. 재대입 **뒤**에 붙여 두 경로(기본 · --config-permissions)가 같이 받는다.
#    `-c` 값은 TOML 로 읽힌다 → 모델은 큰따옴표로 감싼 TOML 문자열이다(숫자처럼 보이는 slug 오파싱 방지). 값은 MODEL_RE 를 통과한 것뿐이라
#    따옴표·역슬래시가 없다. 모델도 `-c` 층으로 넘긴다 — exec · review · resume 가 모두 받으므로 서브커맨드별 모델 플래그 지원에 기대지 않는다.
[ -n "$MODEL" ] && ARGS+=(-c "model=\"$MODEL\"")
# ⛔ review 모드는 config 의 `review_model` 이 있으면 그것을 `model` 보다 먼저 쓴다(GPT CLI 설정 키 — 2026-09-30 GPT 리뷰 지적 · 바이너리
#    설정 필드 목록 실측). 모델을 넘길 때 함께 덮지 않으면 선택이 review·check·final 에서 조용히 빠지고 GPT-CHOICE 표시와 실제가 갈린다.
[ -n "$MODEL" ] && [ "$MODE" = "review" ] && ARGS+=(-c "review_model=\"$MODEL\"")
[ -n "$EFFORT" ] && ARGS+=(-c "model_reasoning_effort=$EFFORT")
[ -n "$SKIP_FLAG" ] && ARGS+=("$SKIP_FLAG")
[ -n "$SCHEMA" ] && ARGS+=(--output-schema "$SCHEMA")
[ -n "$EPHEMERAL" ] && ARGS+=("$EPHEMERAL")
ARGS+=(-o "$OUT")

LOG="${OUT}.stream.log"
rm -f "$OUT" "${OUT}.session"   # 실패 시 이전 성공 run 의 session 이 남아 resume 이 엉뚱한 세션을 잇지 않게 (resume 의 SESSION_ID 는 위에서 이미 읽었다)

# ── 스킬 본문 판정 · 주입 (A2-03 · F-335) — exec·resume 는 판정, 주입은 --inject-skill(exec) 하나만
# ⛔ 본문을 호출부가 마커 없이 `cat` 으로 넣고 --gpt-skill-path 만 넘기는 호출(resume 교차 · 외부 호출부 — 호출 계약의 exec 는 --inject-skill)은
#    판정만 받는다. 멱등 판정은 마커가 아니라 **본문 전체**가 이미 있는가다. 제목 기반 판정은 쓰지 않는다 — 번들 스킬 8개 모두 첫 제목
#    다음 줄이 `## Role` 이라 구별되지 않고, 과제 문구에 제목이 우연히 들어가면 본문 없이 injected=1 로 집계된다(GPT R-A 검토 011·2라운드 009).
#    형식이 다른 사본이 이미 있으면 두 번 들어간다 — 역할 지시가 빠지는 것보다 낫다.
# ⛔ INJECTED = 최종 프롬프트에 본문이 들어 있는가(래퍼가 넣었든 호출부가 넣었든 1). review 는 프롬프트가 없어 항상 0.
#    ⛔ 판정을 빼면 cat 으로 넣는 호출이 injected=0 이 되어 SC-1 집계(injected=1 인 호출만 스킬 사용)가 무너진다.
# ⛔ 프롬프트는 여기서(cd **전에**) 읽는다 — 상대 경로가 서브셸 cwd 기준으로 풀리면 사전 게이트가 본 파일과 다른 파일을 읽는다.
INJECTED=0
PROMPT_TEXT=""
if [ "$MODE" != "review" ]; then
  PROMPT_TEXT="$(cat "$PROMPT_FILE")"
  if [ -n "$SKILL_SRC" ]; then
    SKILL_BODY="$(cat "$SKILL_SRC")" || die 11 "스킬 본문을 읽지 못했다: $SKILL_SRC"
    if [[ "$PROMPT_TEXT" == *"$SKILL_BODY"* ]]; then
      INJECTED=1
    elif [ -n "$INJECT_SKILL" ]; then
      SKILL_NAME="$(basename "$(dirname "$INJECT_SKILL")")"
      # ⛔ 폴더 절대경로를 싣는다 — 주입된 본문은 자기 위치를 모르므로 로더 줄의 references/… 를 풀 수 없다(S12 후속)
      SKILL_DIR="$(cd "$(dirname "$INJECT_SKILL")" && pwd -P)"
      PROMPT_TEXT="[fz-gpt-skill-injected] ${SKILL_NAME} (${SKILL_DIR}) — 아래는 역할 스킬 본문이다(래퍼 주입) · 본문의 상대 경로(references/…)는 이 폴더 기준
${SKILL_BODY}

---

${PROMPT_TEXT}"
      INJECTED=1
    fi
  fi
fi

# ── 적용값 표시 — 호출 직전 stderr 한 줄(스트림 로그 $LOG 가 아니다). 출처 config 인 필드는 config.toml 최상위 값을 같은 폴더
#    gpt-choice.sh config 로 읽는다(판독 규칙 한 곳 · 모르면 '?'). CLI 와 같은 CODEX_HOME 을 읽으므로 격리 런처에서도 실제로 쓰일 config 다.
#    get 판독과 같이 stdout 만 읽는다 — 표시용이라 실패해도 멈추지 않고 '?' 로 적는다.
# ⛔ 이 줄에 WARN · GATE-PASS · GATE-FAIL · --gpt-skill-path 를 쓰지 않고 행머리를 'model:' 로 두지 않는다 — 소비자가 그 토큰으로 판정한다
#    (예: skill-inject 의 WARN.*--gpt-skill-path · failure-injection 의 GATE-PASS/GATE-FAIL).
SHOW_MODEL="$MODEL" SHOW_EFFORT="$EFFORT"
if [ -z "$MODEL" ] || [ -z "$EFFORT" ]; then
  CFG_OUT="$(bash "$(dirname "$0")/gpt-choice.sh" config 2>/dev/null)" || CFG_OUT=""
  CFG_MODEL="?" CFG_EFFORT="?"
  if [[ "$CFG_OUT" =~ $CHOICE_RE ]]; then CFG_MODEL="${BASH_REMATCH[1]}"; CFG_EFFORT="${BASH_REMATCH[2]}"; fi
  [ -n "$SHOW_MODEL" ] || SHOW_MODEL="$CFG_MODEL"
  [ -n "$SHOW_EFFORT" ] || SHOW_EFFORT="$CFG_EFFORT"
fi
echo "GPT-CHOICE model=$SHOW_MODEL ($MODEL_SRC) effort=$SHOW_EFFORT ($EFFORT_SRC)" >&2

# ── 진행 감시 (F-364 · F-147) — CLI 를 백그라운드로 띄우고 그 호출의 스트림 로그($LOG) 크기를 1초마다 잰다(guard_wait).
#    크기가 IDLE_SEC 번 연속 그대로면 CLI 자손 트리를 TERM → 2초 → KILL 하고 사후 게이트가 exit 12(사유 토큰 GPT-IDLE)로 끝낸다.
#    ⛔ 생존 신호는 이 호출의 $LOG 크기(wc -c) 하나다 — GPT 세션 기록 파일의 성장은 어느 호출의 것인지 가를 수 없어 쓰지 않는다
#       (동시 호출이 같은 세션 폴더에 쓴다). ${OUT}.session 은 위에서 지웠고 성공 뒤에만 쓴다.
#    ⛔ CLI 는 래퍼 프로세스 그룹 안에 둔다 — setpgrp · `kill -- -$$` 금지. 독립 런처의 시간 초과는 래퍼 그룹째 죽인다
#       (gpt_independent.sh 감시자 — CLI 를 새 그룹에 두면 닿지 않는다). `kill -- -$$` 는 Lead 가 Bash 도구로 직접 부를 때 도구의 그룹까지 죽인다.
#       그래서 그룹이 아니라 pid 트리를 걷는다.
#    ⛔ 목록은 TERM **전에** 모은다 — TERM 으로 부모가 죽으면 TERM 을 무시한 자손이 pid 1 아래로 옮겨가 다시 걸어도 보이지 않는다.
#       KILL 은 그 목록 ∪ 남은 pid 의 새 자손이다.
#    ⛔ 경과는 벽시계가 아니라 `sleep 1` 반복 횟수다 — 부하로 루프가 늦으면 늦게 끊는 쪽이다(일찍 끊지 않는다).
#       [미검증: 실 CLI 가 SIGTERM 에 세션을 정리하는지 · 시스템 수면 중 sleep 이 흐르는지 — shim 으로만 쟀다]
#    기본 900초 근거: 정상 종료 run 의 같은 턴 무출력 최장 456초(스트림에 보이는 사건 기준) · 600초 초과 0 [미검증: 꼬리 정체 · stream.log 성장 간격]
#      반례(같은 측정 M3): 09-25 한 쌍이 1029 · 973 · 912 · 910초 무출력 간격 뒤 task_complete 없이 끝났다 — 900 이면 첫 간격에서 끊긴다.
#      그것이 정체였는지 정상이었는지는 [미검증](수면 · API 지연 · 모델 정체 구분 불가). 'reasoning summaries: none' 이라 추론 중에는
#      로그가 늘지 않는다 — 긴 추론이 예상되는 호출은 그 호출만 FZ_GPT_IDLE_SEC 를 올린다(modules/gpt-strategy.md GPT-IDLE 행)
IDLE_KILLED=""
tree_pids() {   # $1=pid — 자손부터 자기까지
  local c
  for c in $(pgrep -P "$1" 2>/dev/null); do tree_pids "$c"; done
  echo "$1"
}
guard_wait() {  # $1=백그라운드 CLI pid — 끝날 때까지 기다리고 그 종료코드를 돌려준다
  local pid="$1" last="" cur idle=0 pids more p rc
  while kill -0 "$pid" 2>/dev/null; do
    sleep 1
    cur="$(wc -c < "$LOG" 2>/dev/null | tr -d ' ')"
    if [ "$cur" != "$last" ]; then last="$cur"; idle=0; else idle=$((idle + 1)); fi
    if [ "$IDLE_SEC" -gt 0 ] && [ "$idle" -ge "$IDLE_SEC" ] && kill -0 "$pid" 2>/dev/null; then
      IDLE_KILLED="$idle"; pids="$(tree_pids "$pid")"
      kill -TERM $pids 2>/dev/null; sleep 2
      more=""; for p in $pids; do more="$more $(tree_pids "$p")"; done
      kill -KILL $pids $more 2>/dev/null
      break
    fi
  done
  wait "$pid"; rc=$?
  return "$rc"
}

# ── 호출 (hygiene §1 stdin close · §3 -o · §7 `--` 구분자) — 세 경로 모두 백그라운드 + guard_wait
if [ "$MODE" = "review" ]; then
  [ -n "$TITLE" ] && ARGS+=(--title "$TITLE")
  # ⛔ review 는 `-C` 를 받지 않는다 → 서브셸 cwd 전환으로 작업 디렉토리를 확보한다.
  #    ( ) 안에서만 cd 하므로 호출자 cwd 는 불변이다.
  ( cd "$CD" && codex exec review "${ARGS[@]}" "${SCOPE_ARGS[@]}" < /dev/null ) > "$LOG" 2>&1 &
  guard_wait $!
elif [ "$MODE" = "resume" ]; then
  # ⛔ resume 는 `-C`·`--add-dir` 를 받지 않는다 → review 와 같이 서브셸 cwd 전환. 프롬프트는 위 주입 단계에서 cd 전에 읽었다.
  ( cd "$CD" && codex exec resume "${ARGS[@]}" -- "$SESSION_ID" "$PROMPT_TEXT" < /dev/null ) > "$LOG" 2>&1 &
  guard_wait $!
else
  EXEC_ARGS=(-C "$CD")
  for d in "${ADD_DIRS[@]+"${ADD_DIRS[@]}"}"; do EXEC_ARGS+=(--add-dir "$d"); done
  codex exec "${EXEC_ARGS[@]}" "${ARGS[@]}" -- "$PROMPT_TEXT" < /dev/null > "$LOG" 2>&1 &
  guard_wait $!
fi
GPT_EXIT=$?

# ── gpt-skill 실사용 계측 (기록 전용) — 열: ts / mode / requested / resolved / fallback / exit / injected / cli_version (헤더 없음)
#    requested = --gpt-skill(없으면 -). resolved = SKILL.md 경로(--gpt-skill-path, 없으면 --inject-skill). 빈 값이면 일반 프롬프트
#    폴백이므로 fallback=1. ⛔ review 는 fallback='-' — 프롬프트가 없어 폴백 개념이 없고 스킬은 CLI 암묵 호출로만 뜬다(XA:A-5).
#    injected = 최종 프롬프트에 스킬 본문이 들어 있는가 — SC-1 은 이 열이 1 인 호출만 "스킬 사용" 으로 센다. review 는 항상 0.
#    ⛔ 열은 **뒤에만** 붙인다(헤더 없는 TSV — 앞 열 위치를 바꾸면 옛 행과 섞인다). cli_version 조회 실패는 `-`.
#    ⛔ exit 열은 **gpt 종료코드**다 — 사후 게이트 12~14(측정 실패)는 반영되지 않는다.
#    9열 end = 진행 감시가 CLI 를 끝냈으면 `idle`, 아니면 `-` — exit 열(143 · 137 같은 신호값)만으로는 CLI 스스로의 실패와 가를 수 없다.
#    ⛔ 로그 실패는 exit 계약(10~14)을 바꾸지 않는다. 디렉토리 부재 시 조용히 건너뛴다.
TELEMETRY_DIR="${FZ_TELEMETRY_DIR:-${HOME:-}/.fz/telemetry}"   # 기본값 출처: scripts/fz_stop_telemetry.py:32
if { [ -n "$GPT_SKILL" ] || [ -n "$SKILL_SRC" ]; } && [ -d "$TELEMETRY_DIR" ]; then
  # ⛔ 필드 안의 탭·개행은 공백으로 — 한 호출이 9열이 아니게 되거나 여러 행으로 갈라지지 않게(검토 012)
  tsv() { printf '%s' "$1" | tr '\t\n\r' '   '; }
  CLI_VERSION="$(codex --version 2>/dev/null | head -1)"
  if [ "$MODE" = "review" ]; then FALLBACK="-"; elif [ -n "$SKILL_SRC" ]; then FALLBACK=0; else FALLBACK=1; fi
  END_REASON="-"; [ -n "$IDLE_KILLED" ] && END_REASON="idle"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$(tsv "${GPT_SKILL:--}")" \
    "$(tsv "${SKILL_SRC:--}")" "$FALLBACK" "$GPT_EXIT" "$INJECTED" "$(tsv "${CLI_VERSION:--}")" "$END_REASON" \
    2>/dev/null >> "$TELEMETRY_DIR/gpt-skill-usage.tsv" || true
fi

# ── 사후 게이트: exit → 파일 → **계약**. 어느 하나라도 실패면 측정 실패.
# ⛔ 진행 감시 종료를 일반 12 보다 먼저 본다 — 메시지 머리 토큰 GPT-IDLE 이 CLI 스스로의 실패(같은 12 · 같은 신호값 exit)와 가른다
[ -z "$IDLE_KILLED" ] || { tail -20 "$LOG" >&2; die 12 "GPT-IDLE: 스트림 로그가 ${IDLE_KILLED}초 동안 자라지 않아 진행 감시가 CLI 를 종료했다(FZ_GPT_IDLE_SEC=${IDLE_SEC} · CLI exit=${GPT_EXIT} · 측정 실패 — 리뷰 결과 아님). log: $LOG"; }
[ "$GPT_EXIT" -eq 0 ] || { tail -20 "$LOG" >&2; die 12 "codex exit=$GPT_EXIT (측정 실패 — 리뷰 결과 아님). log: $LOG"; }
[ -s "$OUT" ] || { tail -20 "$LOG" >&2; die 13 "출력 파일 없음/빈 파일 (측정 실패). log: $LOG"; }
if [ -n "$SCHEMA" ]; then
  # ⛔ 문법만 보면 `{}` 가 `issues=0 verdict=None` 으로 GATE-PASS 된다 (감사 ISSUE-013).
  #    `jsonschema` 는 부재하므로(표준 라이브러리 전용) required·타입·enum을 **직접** 검사한다.
  # ⛔ validator 의 exit 1(출력 계약 위반) 과 2(스키마·사용법 실패)를 **구별**한다 (ISSUE-014).
  #    합치면 스키마가 깨진 것을 "출력이 나쁘다"로 오귀속한다.
  python3 "$(dirname "$0")/validate-gpt-output.py" "$OUT" "$SCHEMA"; VAL_RC=$?
  case "$VAL_RC" in
    0) ;;
    1) die 14 "출력이 스키마 계약 위반 (측정 실패)" ;;
    *) die 11 "스키마 로드·사용법 실패 (validator exit=$VAL_RC) — 출력 문제가 아니다" ;;
  esac
else
  echo "GATE-PASS text_ok bytes=$(wc -c < "$OUT" | tr -d ' ')"
fi
# ── 세션 ID 기록 (resume 입력) — ⛔ 사후 게이트(exit·파일·스키마) **전부 통과 뒤**에만 쓴다. 실패 run 의 세션을 resume 에 넘기지 않는다 — 배너의 ANSI 색 코드를 벗긴 뒤 첫 `session id:` 만 쓴다
SID="$(sed $'s/\x1b\\[[0-9;]*m//g' "$LOG" | grep -m1 -oE 'session id: *[0-9a-f-]{36}' | grep -oE '[0-9a-f-]{36}' || true)"
if [ -n "$SID" ]; then printf '%s\n' "$SID" > "${OUT}.session"; else rm -f "${OUT}.session"; echo "WARN: 스트림 로그에서 session id 를 찾지 못했다 — resume 불가" >&2; fi
exit 0
