#!/bin/bash
# health-check 경로별 검사 선택 fixture (H2-9 · GPT H-015) — 선택 규칙과 부분 실행 표지를 동작으로 본다.
#
# 이 트리의 health-check 를 인자만 바꿔 부른다(대부분 `--select-only` — 검사를 돌리지 않아 빠르다).
#   infra-path-full    `--changed scripts/md_section.py`        → mode=full (공용 인프라) · check 줄 0
#   unknown-path-full  `--changed some/new/thing.yaml`          → mode=full (미분류 = 전체) · check 줄 0
#   doc-path-subset    `--changed <modules 의 system-reminders>` → mode=subset · 문서 lint 4종 · 그 파일 이름을 적은 러너(실행 때 grep)
#                      전부 선택 · 이 러너 자신(그 파일을 읽지 않는다)은 미선택. 이름 적은 러너가 0개면 lint 만 단언한다
#   prints-selection   선택 없이 실제 부분 실행 한 번(docs 아래 없는 경로 — 싼 러너만 걸린다) → 선택 줄 · PARTIAL 줄(선택 N개)이
#                      총평 앞에 찍히고 · 고른 검사 행만 있고 · exit 이 총평과 맞는다
#   ship-full          `--ship --changed <같은 문서>`            → mode=full (출하는 언제나 전체)
# 출력: 셀마다 `<셀>: PASS|FAIL <근거>` · 끝에 `health-select: PASS|FAIL`
# exit: 0 전건 통과 · 1 셀 FAIL · 2 준비 실패(health-check · python3 부재 — `UNRUN:` 표지)
#   ⛔ 선택기가 없는 트리(기준 트리)는 health-check 가 새 인자를 거부한다(exit 2) — 그것은 준비 실패가 아니라 셀 FAIL 이다.
#      그래서 준비 단계는 선택기 파일의 존재를 보지 않는다.
# ⛔ 문서 경로를 한 낱말로 적지 않는다(폴더 · 이름을 나눠 조립) — 적으면 선택기 규칙 ①(이름)이 이 러너를 그 문서에 기대는 러너로 읽어
#    doc-path-subset 이 자기 자신을 고르고, prints-selection 은 자기 자신을 다시 부른다.
# ⛔ 중첩 재귀 가드: 이 러너가 부르는 health-check 는 FZ_HEALTH_SELECT_FIXTURE=1 로 돈다. 그 안에서 이 러너가 다시 불리면
#    `UNRUN:` 을 내고 exit 2 로 끝낸다 — 돌지 않았으니 통과가 아니다. prints-selection 은 탐침이 health 러너를 끌어오면
#    돌리기 전에 FAIL 로 멈춘다(가드는 그 단언이 빠졌을 때의 그물이다).
set -u
if [ -n "${FZ_HEALTH_SELECT_FIXTURE:-}" ]; then
  echo "UNRUN: 중첩 실행 — 바깥 health-select fixture 가 부른 health-check 안이다"
  exit 2
fi
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
[ -f "$R/scripts/health-check.sh" ] || { echo "UNRUN: SETUP health-check 없음: $R"; exit 2; }
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: SETUP python3 없음"; exit 2; }

SELF_REL="tests/fixtures/health/select/run.sh"
D_DIR=modules D_NAME=system-reminders
DOC="$D_DIR/$D_NAME.md"
PROBE="docs/zz-health-select-probe-$$.md"   # 없는 경로 — 분류는 문자열로만 하므로 문서로 읽힌다
LINTS="lint_contracts.py lint_recurrence.py lint_doc_freshness.py check_single_source.py"

FAILN=0
ok() { echo "$1: PASS $2"; }
no() { echo "$1: FAIL $2"; FAILN=$((FAILN + 1)); }
# run_hc <인자…> → OUT · RC
run_hc() { OUT="$(cd "$R" && FZ_HEALTH_SELECT_FIXTURE=1 bash "$R/scripts/health-check.sh" "$@" 2>&1)"; RC=$?; }
mode_of() { printf '%s\n' "$OUT" | sed -n 's/^HEALTH-SELECT mode=\([a-z]*\) reason=\(.*\)$/\1 \2/p' | head -1; }
checks_of() { printf '%s\n' "$OUT" | sed -n 's/^HEALTH-SELECT check=\([^ ]*\).*/\1/p'; }
last() { printf '%s\n' "$OUT" | tail -1 | cut -c1-160; }

# full 셀 공통 — <셀> <기대 reason 접두> <인자…>
full_case() {
  local name="$1" want="$2" m
  shift 2
  run_hc "$@"
  m="$(mode_of)"
  if [ "$RC" -eq 0 ] && [ "${m%% *}" = full ] && [ -z "$(checks_of)" ]; then
    case "${m#* }" in
      "$want"*) ok "$name" "mode=full reason=${m#* } · check 줄 0" ;;
      *) no "$name" "mode=full 이지만 reason='${m#* }' (기대 ${want}…)" ;;
    esac
  else
    no "$name" "rc=$RC mode='${m:-없음}' check $(checks_of | grep -c .)줄 — $(last)"
  fi
}

full_case infra-path-full "infra:" --changed scripts/md_section.py --select-only
full_case unknown-path-full "unknown:" --changed some/new/thing.yaml --select-only

# ── doc-path-subset
run_hc --changed "$DOC" --select-only
m="$(mode_of)"; sel="$(checks_of)"; why=""; namers=""
[ "$RC" -eq 0 ] || why="$why rc=$RC($(last))"
[ "${m%% *}" = subset ] || why="$why mode='${m:-없음}'"
for l in $LINTS; do
  printf '%s\n' "$sel" | grep -qxF "$l" || why="$why lint 빠짐:$l"
done
for r in "$R"/tests/fixtures/*/*/run.sh "$R"/tests/workflows/*.js; do
  [ -f "$r" ] || continue
  grep -qF -- "$D_NAME.md" "$r" || continue
  rel="${r#"$R"/}"
  namers="$namers $rel"
  printf '%s\n' "$sel" | grep -qxF "$rel" || why="$why 이름 적은 러너 빠짐:$rel"
done
printf '%s\n' "$sel" | grep -qxF "$SELF_REL" && why="$why 자기 자신이 골라졌다(그 문서를 읽지 않는다)"
if [ -z "$why" ]; then
  ok doc-path-subset "mode=subset · lint 4 · 이름 적은 러너${namers:- 0개(lint 만 단언)} · 선택 $(printf '%s\n' "$sel" | grep -c .)개 · 자기 자신 제외"
else
  no doc-path-subset "${why# }"
fi

# ── prints-selection — 탐침 선택을 먼저 보고(싼가 · health 러너를 안 끄는가) 같은 탐침으로 실제 부분 실행을 한 번 돈다
run_hc --changed "$PROBE" --select-only
PRE="$OUT"; PRE_RC=$RC; PRE_MODE="$(mode_of)"; PRE_SEL="$(checks_of)"
if [ "$PRE_RC" -ne 0 ] || [ "${PRE_MODE%% *}" != subset ]; then
  no prints-selection "탐침 선택 실패 rc=$PRE_RC mode='${PRE_MODE:-없음}' — $(last)"
elif printf '%s\n' "$PRE_SEL" | grep -q '^tests/fixtures/health/'; then
  no prints-selection "탐침이 health 러너를 끌어온다 — 재귀 · 장시간 위험이라 돌리지 않는다: $(printf '%s\n' "$PRE_SEL" | grep '^tests/fixtures/health/' | tr '\n' ' ')"
else
  run_hc --changed "$PROBE"
  n="$(printf '%s\n' "$PRE_SEL" | grep -c .)"
  banner="⛔ 부분 실행(PARTIAL) — 출하 게이트 아님 · 선택 ${n}개"
  why=""
  while IFS= read -r l; do
    printf '%s\n' "$OUT" | grep -qxF -- "$l" || why="$why 선택 줄 없음:${l#HEALTH-SELECT }"
  done < <(printf '%s\n' "$PRE" | grep '^HEALTH-SELECT ')
  for row in "계약 lint" "출처 최신성" "단일 출처 계약" "재발 방지 lint"; do
    printf '%s\n' "$OUT" | grep -qE "^(✅|⛔|⏸) $row " || why="$why 행 없음:$row"
  done
  for row in "workflow 문법" "게이트 self-test" "plugin validate"; do
    printf '%s\n' "$OUT" | grep -qE "^(✅|⛔|⏸) $row " && why="$why 전체 전용 행이 돌았다:$row"
  done
  case "$RC" in
    0) verdict="✅ 전 검사 통과 (exit 0)" ;;
    1) verdict="⛔ 실패한 검사가 있다 (exit 1)" ;;
    2) verdict="⛔ 실행되지 못한 검사" ;;
    *) verdict="" ;;
  esac
  bline="$(printf '%s\n' "$OUT" | grep -nxF -- "$banner" | head -1 | cut -d: -f1)"
  vline=""
  [ -n "$verdict" ] && vline="$(printf '%s\n' "$OUT" | grep -nF -- "$verdict" | head -1 | cut -d: -f1)"
  if [ -z "$bline" ]; then why="$why PARTIAL 줄 없음('$banner')"; fi
  if [ -z "$vline" ]; then why="$why exit $RC 에 맞는 총평 없음"
  elif [ -n "$bline" ] && [ "$bline" -gt "$vline" ]; then why="$why PARTIAL 줄이 총평 뒤"; fi
  if [ -z "$why" ]; then
    ok prints-selection "선택 줄 $((n + 1))개 · '$banner' 가 총평 앞 · 고른 검사 행만 · exit $RC = 총평"
  else
    no prints-selection "${why# } · rc=$RC — $(last)"
  fi
fi

full_case ship-full "ship" --ship --changed "$DOC" --select-only

echo
if [ "$FAILN" -eq 0 ]; then echo "health-select: PASS"; exit 0; fi
echo "health-select: FAIL (${FAILN}셀)"
exit 1
