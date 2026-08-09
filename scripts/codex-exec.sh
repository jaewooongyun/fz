#!/bin/bash
# lint:no-root-anchor — 플러그인 루트를 참조하지 않는다. 작업 대상은 `--cd`로 받아 게이트 11에서
#   존재를 검증하고, 스키마·프롬프트도 호출자가 절대경로로 넘긴다 (lint #N6 면제 형태 c).
#
# codex 호출 hygiene 실행체 — modules/fz-codex-bash-hygiene.md §8의 구현
#
# 왜 스크립트인가: hygiene 규칙은 전부 binary(pass/fail)다
#   (guides/skill-authoring.md §11 "결과가 binary인가? → 스크립트").
#   산문 체크리스트는 호출자가 매번 기억해야 하고, 실측상 누락이 재발했다:
#   ① `review` + PROMPT 인자 충돌로 exit 2 (core.md:36에 문서화돼 있었음)
#   ② 래퍼 마지막 문장이 exit code를 덮어 측정 실패를 "결과 0건"으로 오독
#   본 스크립트는 ①을 구조적으로 거부하고 ②를 게이트로 차단한다.
#
# usage:
#   codex-exec.sh review --cd DIR --out FILE (--base BR | --uncommitted | --commit SHA)
#                        [--effort E] [--schema F] [--title T] [--add-dir D] [--ephemeral]
#                        [--expected-branch B]
#   codex-exec.sh exec   --cd DIR --out FILE --prompt-file F
#                        [--effort E] [--schema F] [--add-dir D]
#
# exit: 0=성공(결과 유효) / 10=사용법·플래그 충돌 / 11=사전조건 / 12=codex 비정상종료
#       13=출력 없음·빈 파일 / 14=출력이 계약 위반(파싱·필수키·타입·enum)
#   ⛔ 10~14는 전부 **측정 실패**다 — "이슈 0건"으로 해석하면 안 된다.
set -u

die() { echo "GATE-FAIL($1): $2" >&2; exit "$1"; }
# ⛔ 값 옵션의 arity 가드 — 없으면 `set -u` 하에서 `$2` 참조가 **exit 1(unbound variable)** 로 죽어
#    문서상 게이트 10과 어긋난다 (2026-08-09 감사 ISSUE-011: `review --cd` 가 exit 1이었다).
need() { [ "$1" -ge 2 ] || die 10 "$2 는 값이 필요하다"; }

MODE="${1:-}"; shift || true
case "$MODE" in
  review|exec) ;;
  *) die 10 "mode는 review|exec — 받은 값: '${MODE}'" ;;
esac

CD="" OUT="" PROMPT_FILE="" SCHEMA="" EFFORT="high" TITLE="" EPHEMERAL="" EXPECTED_BRANCH=""
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
    --effort)          need $# "--effort";          EFFORT="$2"; shift 2 ;;
    --title)           need $# "--title";           TITLE="$2"; shift 2 ;;
    --add-dir)         need $# "--add-dir";         ADD_DIRS+=("$2"); shift 2 ;;
    --expected-branch) need $# "--expected-branch"; EXPECTED_BRANCH="$2"; shift 2 ;;
    --base)            need $# "--base";            set_scope base "$2"
                       SCOPE_ARGS=(--base "$2");   shift 2 ;;
    --commit)          need $# "--commit";          set_scope commit "$2"
                       SCOPE_ARGS=(--commit "$2"); shift 2 ;;
    --uncommitted)     set_scope uncommitted
                       SCOPE_ARGS=(--uncommitted); shift ;;
    --ephemeral)       EPHEMERAL="--ephemeral";     shift ;;
    *) die 10 "알 수 없는 인자: $1" ;;
  esac
done

# ── 사전 게이트 1: 플래그 상호 배타 (실측 근거: codex 0.144.1)
#    `codex exec review`는 flag-only — PROMPT positional과 --uncommitted/--base가 충돌한다.
if [ "$MODE" = "review" ] && [ -n "$PROMPT_FILE" ]; then
  die 10 "review 모드는 PROMPT를 받지 않는다 (flag-only). 커스텀 지시가 필요하면 mode=exec 사용 — modules/fz-codex-subcommands-core.md §review"
fi
[ "$MODE" = "review" ] && [ -z "$SCOPE_KIND" ] && die 10 "review 모드는 --base|--uncommitted|--commit 중 하나 필수"
[ "$MODE" = "exec" ] && [ -z "$PROMPT_FILE" ] && die 10 "exec 모드는 --prompt-file 필수"
[ "$MODE" = "exec" ] && [ -n "$SCOPE_KIND" ] && die 10 "exec 모드에 review 스코프 플래그를 줄 수 없다 (diff는 프롬프트에 인라인)"

# ── 사전 게이트 2: 경로·파일 존재
[ -n "$CD" ] || die 10 "--cd 필수"
[ -d "$CD" ] || die 11 "--cd 디렉토리 없음: $CD"
[ -n "$OUT" ] || die 10 "--out 필수"
[ -n "$PROMPT_FILE" ] && { [ -s "$PROMPT_FILE" ] || die 11 "프롬프트 파일 없음/빈 파일: $PROMPT_FILE"; }
[ -n "$SCHEMA" ] && { [ -s "$SCHEMA" ] || die 11 "스키마 파일 없음: $SCHEMA"; }
command -v codex >/dev/null 2>&1 || die 11 "codex CLI 미설치"

# ── 사전 게이트 3: trust_level (hygiene §5) — 경고만, 차단 아님
grep -qE '^\[projects\.' "${CODEX_HOME:-$HOME/.codex}/config.toml" 2>/dev/null \
  || echo "WARN: trust_level 미설정 — sandbox가 read-only로 강제될 수 있다 (hygiene §5)" >&2

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

ARGS=(-C "$CD" -c "sandbox_permissions=[\"disk-full-read-access\"]" -c "model_reasoning_effort=$EFFORT")
[ -n "$SKIP_FLAG" ] && ARGS+=("$SKIP_FLAG")
[ -n "$SCHEMA" ] && ARGS+=(--output-schema "$SCHEMA")
[ -n "$EPHEMERAL" ] && ARGS+=("$EPHEMERAL")
for d in "${ADD_DIRS[@]+"${ADD_DIRS[@]}"}"; do ARGS+=(--add-dir "$d"); done
ARGS+=(-o "$OUT")

LOG="${OUT}.stream.log"
rm -f "$OUT"

# ── 호출 (hygiene §1 stdin close · §3 -o · §7 `--` 구분자)
if [ "$MODE" = "review" ]; then
  [ -n "$TITLE" ] && ARGS+=(--title "$TITLE")
  codex exec review "${ARGS[@]}" "${SCOPE_ARGS[@]}" < /dev/null > "$LOG" 2>&1
else
  codex exec "${ARGS[@]}" -- "$(cat "$PROMPT_FILE")" < /dev/null > "$LOG" 2>&1
fi
CODEX_EXIT=$?

# ── 사후 게이트: exit → 파일 → **계약**. 어느 하나라도 실패면 측정 실패.
[ "$CODEX_EXIT" -eq 0 ] || { tail -20 "$LOG" >&2; die 12 "codex exit=$CODEX_EXIT (측정 실패 — 리뷰 결과 아님). log: $LOG"; }
[ -s "$OUT" ] || { tail -20 "$LOG" >&2; die 13 "출력 파일 없음/빈 파일 (측정 실패). log: $LOG"; }
if [ -n "$SCHEMA" ]; then
  # ⛔ 문법만 보면 `{}` 가 `issues=0 verdict=None` 으로 GATE-PASS 된다 (감사 ISSUE-013).
  #    `jsonschema` 는 부재하므로(표준 라이브러리 전용) required·타입·enum을 **직접** 검사한다.
  # ⛔ validator 의 exit 1(출력 계약 위반) 과 2(스키마·사용법 실패)를 **구별**한다 (ISSUE-014).
  #    합치면 스키마가 깨진 것을 "출력이 나쁘다"로 오귀속한다.
  python3 "$(dirname "$0")/validate-codex-output.py" "$OUT" "$SCHEMA"; VAL_RC=$?
  case "$VAL_RC" in
    0) ;;
    1) die 14 "출력이 스키마 계약 위반 (측정 실패)" ;;
    *) die 11 "스키마 로드·사용법 실패 (validator exit=$VAL_RC) — 출력 문제가 아니다" ;;
  esac
else
  echo "GATE-PASS text_ok bytes=$(wc -c < "$OUT" | tr -d ' ')"
fi
exit 0
