#!/bin/bash
# 트래커 세션 범위 러너 — modules/session.md `## 세션 자동 감지` 절의 첫 bash 블록을 문서에서 그대로 뽑아(다시 적은 사본이 아니다)
#   임시 HOME 에서 돌린다. 60분 안의 트래커 파일을 이어받는 규칙이 세션 id 로 갈리는지와 실패 경로를 본다.
#   규칙: 이번 호출의 세션 id(CLAUDE_CODE_SESSION_ID)와 파일의 claude_session_id 가 둘 다 있고 다르면 이어받지 않는다 ·
#   어느 한쪽을 모르면(옛 파일 · 빈 값 · 미설정) 나이만 본다 — scripts/run_metrics.py reusable() 과 같은 규칙이다.
#   한 시간 안에 시작한 다른 작업(다른 세션)이 앞 작업의 이슈 목록을 이어쓰지 않게 한다.
#   새 파일은 있는 파일을 덮어쓰지 않는다 — 같은 초에 시작한 두 세션은 이름(초 단위 시각)이 겹치니 뒤 세션이 1초 뒤 새 시각으로 다시 만든다.
# 셀 — 셀마다 한 줄 `<셀>: PASS <설명>` 또는 `<셀>: FAIL <사유>` · 끝에 `tracker-reuse: PASS|FAIL`
#   first-run-new-file        빈 폴더 · 세션 A → 새 파일 1개 · JSON(session_id 꼴 · 파일 이름 · claude_session_id=A · 빈 issues · iterations ·
#                             in_progress) · 내보낸 GPT_SESSION_ID = 파일의 session_id · GPT_TRACKER_FILE = 그 파일
#   other-session-new-file    1초 뒤 세션 B → 60분 안의 A 파일을 이어받지 않고 새 파일 · claude_session_id=B · A 파일 바이트 불변
#   same-session-reuses       이어서 세션 A → 더 새 B 파일을 건너뛰고 A 파일 · 세션 B → B 파일 · 파일 수 2 · 두 파일 바이트 불변
#   unknown-session-age-only  세션 id 미설정 · 빈 값 → 두 파일 중 가장 새 파일(B) · claude_session_id 가 없는 옛 꼴 파일과 빈 값 파일은
#                             세션 C 도 이어받는다
#   stale-file-new            60분 밖 파일은 같은 세션(A)도 · 세션 id 미설정도 이어받지 않는다(새 파일 · 옛 파일 바이트 불변)
#   no-hit-new-file           검색 결과 없음(트래커 폴더도 없다 — 블록이 만든다) · 현재 폴더에 package.json → 트래커 폴더 안의 새 파일.
#                             이 셀만 PATH 앞에 GNU 꼴 xargs(입력이 비어도 명령을 한 번 돈다 — `-r` 없는 기본)를 둔다: 이 머신의
#                             xargs 와 무관하게, 빈 검색 결과가 현재 폴더 나열로 바뀌어 그 폴더의 파일을 고르는 꼴을 잡는다
#   unreadable-json-skipped   60분 안의 더 새 파일이 깨진 JSON · 빈 파일이면 건너뛰고 더 오래된 같은 세션 파일을 이어받는다 ·
#                             깨진 파일뿐이면 새 파일 · 깨진 파일 바이트 불변
#   same-second-new-name      같은 초 — 세션 A 파일(이슈 1)이 있는 이름으로 세션 B 가 시작한다(PATH 앞의 시각 shim 이 파일 이름용 시각을
#                             준다) → A 파일 바이트 · 이슈 불변 · B 는 1초 뒤 다시 읽은 시각의 새 파일(claude_session_id=B) · 파일 2
#   same-second-all-taken     같은 초 · 시도마다 이름이 차 있다 → exit 1 · 변수 안 내보냄 · 시각을 2번 이상 읽었다(다시 시도) · A 파일 불변 · 파일 1
#   dir-create-failure       $HOME/.claude 가 일반 파일(트래커 폴더를 만들 수 없다) → exit 1 · 트래커 변수 둘 다 안 내보냄
#   write-failure             트래커 폴더 쓰기 금지(555) → exit 1 · 변수 안 내보냄 · 파일 0 (권한 비트가 듣지 않는 계정이면 NOTE 로 건너뛴다)
#   schema-claude-session-id  schemas/issue_tracker_schema.json 이 claude_session_id 를 선택(required 밖) 문자열 속성으로 적는다
#   셀 집합                   판정한 셀 + 건너뛴 셀 = 기대 셀(셀을 지운 사본은 FAIL)
# 블록은 `env -i` 로 PATH · HOME · (있으면) CLAUDE_CODE_SESSION_ID 만 받는다 — 사용자 HOME · 사용자 트래커를 건드리지 않는다.
#   블록 텍스트 뒤에 내보낸 변수를 printenv 로 읽는 두 줄을 붙여 한 셸에서 돈다(모델이 Bash 한 번으로 돌리는 꼴).
# ⛔ 음성 대조: 세션 id 를 보지 않던 블록(가장 새 파일을 조건 없이 · `| xargs ls -t` · 쓰기 실패를 보지 않음)과 claude_session_id 가 없는
#    스키마를 --tree 로 주면 열두 셀이 모두 FAIL · exit 1 이다.
# exit: 0 전건 통과 · 1 단언 실패(블록을 찾지 못함 포함) · 2 준비 실패(UNRUN — jq · bash · perl Time::HiRes · 임시 폴더 · 인자. PASS 아님)
# usage: run.sh [--tree <플러그인 트리>]   (기본: 이 fixture 가 든 트리)
set -u
TREE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." 2>/dev/null && pwd)"
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "UNRUN  --tree 에 경로가 없다"; exit 2; }
            TREE="$(cd "$2" 2>/dev/null && pwd)" || { echo "UNRUN  --tree 경로 없음: $2"; exit 2; }; shift 2 ;;
    *) echo "UNRUN  알 수 없는 인자: $1"; exit 2 ;;
  esac
done
command -v jq >/dev/null 2>&1 || { echo "UNRUN  jq 없음 — 블록이 jq 로 트래커 파일을 읽는다"; exit 2; }
BASH_BIN="$(command -v bash)" || { echo "UNRUN  bash 없음"; exit 2; }
REAL_XARGS="$(command -v xargs)" || { echo "UNRUN  xargs 없음"; exit 2; }
DOC="$TREE/modules/session.md" SCHEMA="$TREE/schemas/issue_tracker_schema.json"
[ -f "$DOC" ] && [ -f "$SCHEMA" ] || { echo "UNRUN  modules/session.md 또는 schemas/issue_tracker_schema.json 없음: $TREE"; exit 2; }
# ⛔ mktemp 결과를 따로 받는다 — 실패한 mktemp 뒤의 cd "" 는 현재 폴더에 남는다
T0="$(mktemp -d "${TMPDIR:-/tmp}/fz-tracker-reuse.XXXXXX")" || { echo "UNRUN  임시 폴더 실패"; exit 2; }
T="$(cd "$T0" && pwd -P)" || { echo "UNRUN  임시 폴더 해석 실패"; exit 2; }
trap 'chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"' EXIT

BLOCK="$(awk '/^## 세션 자동 감지[[:space:]]*$/ { s = 1; next }
              s && /^## / { exit }
              s && !b && /^```bash[[:space:]]*$/ { b = 1; next }
              b && /^```[[:space:]]*$/ { exit }
              b { print }' "$DOC")"
if [ -z "$BLOCK" ] || ! printf '%s\n' "$BLOCK" | grep -q '^init_or_use_session[[:space:]]*$'; then
  echo "tracker-reuse: FAIL modules/session.md '## 세션 자동 감지' 절에서 init_or_use_session 을 부르는 첫 bash 블록을 찾지 못했다"
  exit 1
fi

mkdir -p "$T/bin" "$T/cwd" || { echo "UNRUN  임시 하위 폴더 실패"; exit 2; }
# GNU 꼴 xargs — 입력이 비어도 명령을 인자 없이 한 번 돈다. 입력이 있으면 실제 xargs 에 넘긴다
cat > "$T/bin/xargs" <<EOF || { echo "UNRUN  xargs shim 실패"; exit 2; }
#!/bin/sh
in=\$(cat)
[ -n "\$in" ] || exec "\$@"
printf '%s\n' "\$in" | exec "$REAL_XARGS" "\$@"
EOF
chmod +x "$T/bin/xargs" || { echo "UNRUN  xargs shim 실행 비트 실패"; exit 2; }
# 시각 shim — 파일 이름용 시각(`date +%Y%m%d_%H%M%S`)은 $CLOCK 의 첫 줄을 내고 그 줄을 지운다(줄이 다 떨어지면 실제 시각).
#   읽을 때마다 실제 시각(초 · 소수 셋째 자리)을 $CLOCK.log 에 한 줄 적는다(다시 시도하기 전의 1초 대기를 본다).
#   다른 꼴의 호출(created_at)은 실제 date 에 넘긴다. 같은 초에 시작한 두 세션을 만든다
REAL_DATE="$(command -v date)" || { echo "UNRUN  date 없음"; exit 2; }
REAL_PERL="$(command -v perl)" && "$REAL_PERL" -MTime::HiRes=time -e 1 2>/dev/null \
  || { echo "UNRUN  perl Time::HiRes 없음 — 시각 shim 이 읽은 시각을 적는다"; exit 2; }
CLOCK="$T/clock"
mkdir -p "$T/clockbin" || { echo "UNRUN  시각 shim 폴더 실패"; exit 2; }
cat > "$T/clockbin/date" <<EOF || { echo "UNRUN  date shim 실패"; exit 2; }
#!/bin/sh
if [ "\$#" = 1 ] && [ "\$1" = "+%Y%m%d_%H%M%S" ]; then
  "$REAL_PERL" -MTime::HiRes=time -e 'printf "%.3f\n", time' >> "$CLOCK.log"
  if [ -s "$CLOCK" ]; then
    head -n 1 "$CLOCK"
    sed '1d' "$CLOCK" > "$CLOCK.tmp" && mv "$CLOCK.tmp" "$CLOCK"
    exit 0
  fi
fi
exec "$REAL_DATE" "\$@"
EOF
chmod +x "$T/clockbin/date" || { echo "UNRUN  date shim 실행 비트 실패"; exit 2; }
printf '{\n  "name": "sample-app",\n  "version": "1.0.0"\n}\n' > "$T/cwd/package.json" || { echo "UNRUN  현재 폴더 파일 실패"; exit 2; }
RUNPATH="$PATH"
PROBE='rc=$?
printf "rc=%s\nsid=%s\nfile=%s\n" "$rc" "$(printenv GPT_SESSION_ID)" "$(printenv GPT_TRACKER_FILE)"'

# 세션 id — Claude Code 세션 id 꼴(UUID)의 합성 값(scripts/leak_rules.py SYNTHETIC_SESSION_IDS 안)
CS_A=00000000-0000-7000-8000-000000000001 CS_B=00000000-0000-7000-8000-000000000002 CS_C=00000000-0000-7000-8000-000000000003
FAILS=0 RAN="" SKIPPED="" WHY=""
EXPECT_CELLS="first-run-new-file other-session-new-file same-session-reuses unknown-session-age-only stale-file-new no-hit-new-file
unreadable-json-skipped same-second-new-name same-second-all-taken dir-create-failure write-failure schema-claude-session-id"
verdict() {   # $1=셀 · $2=실패 사유(빈 값 = 통과) · $3=통과 설명
  RAN="$RAN $1"
  if [ -z "$2" ]; then echo "$1: PASS $3"; else echo "$1: FAIL $2"; FAILS=$((FAILS + 1)); fi
}
add() { WHY="${WHY:+$WHY; }$1"; }

# 블록 한 번 — $1=이름 · $2=HOME · $3=세션 id('-' = 미설정 · '' = 빈 값) → RC · SID · FILE (+ $T/r-<이름>.out · .err)
blk() {
  local e=(env -i "PATH=$RUNPATH" "HOME=$2")
  [ "$3" = "-" ] || e+=("CLAUDE_CODE_SESSION_ID=$3")
  (cd "$T/cwd" && "${e[@]}" "$BASH_BIN" -c "$BLOCK"$'\n'"$PROBE") > "$T/r-$1.out" 2> "$T/r-$1.err" < /dev/null
  RC="$(sed -n 's/^rc=//p' "$T/r-$1.out")" SID="$(sed -n 's/^sid=//p' "$T/r-$1.out")" FILE="$(sed -n 's/^file=//p' "$T/r-$1.out")"
}
sessions() { printf '%s' "$1/.claude/sessions"; }
count() { find "$(sessions "$1")" -name 'SESSION-*_issues.json' 2>/dev/null | grep -c .; }
sum() { { cksum < "$1"; } 2>/dev/null; }
# 새로 만든 파일 판정 — $1=HOME · $2=기대 claude_session_id · $3=라벨. 사유는 WHY 에 더한다
fresh_ok() {
  [ "$RC" = 0 ] || { add "$3: exit $RC · $(head -c 160 "$T/r-$3.err" 2>/dev/null | tr '\n' ' ')"; return; }
  [ -n "$FILE" ] && [ "$(dirname "$FILE")" = "$(sessions "$1")" ] || { add "$3: GPT_TRACKER_FILE 가 트래커 폴더 밖이다 [$FILE]"; return; }
  jq -e --arg c "$2" --arg sid "$SID" --arg base "$(basename "$FILE")" '
      (.session_id | type == "string" and test("^SESSION-[0-9]{8}_[0-9]{6}$")) and .session_id == $sid
      and ($sid + "_issues.json") == $base
      and (has("claude_session_id") and .claude_session_id == $c)
      and .issues == [] and .iterations == [] and .final_status == "in_progress"
      and (.created_at | type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"))' "$FILE" > /dev/null 2>&1 \
    || add "$3: JSON(session_id=GPT_SESSION_ID[$SID] · 파일 이름 · claude_session_id=\"$2\" · 빈 목록 · in_progress)가 맞지 않다 — $(head -c 200 "$FILE" 2>/dev/null | tr '\n' ' ')"
}
# 이어받기 판정 — $1=기대 파일 · $2=라벨
reuse_ok() {
  [ "$RC" = 0 ] || { add "$2: exit $RC"; return; }
  [ "$FILE" = "$1" ] || { add "$2: 이어받을 파일 $(basename "$1") 대신 [$(basename "$FILE")]"; return; }
  [ "$SID" = "$(jq -r '.session_id' "$1" 2>/dev/null)" ] || add "$2: GPT_SESSION_ID[$SID] 가 파일의 session_id 와 다르다"
}
make_legacy() {   # $1=파일 — claude_session_id 를 지운 옛 꼴(이 키가 없던 블록이 쓴 파일)
  jq 'del(.claude_session_id)' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}

# ── 1단계 — 첫 파일들(이 뒤에 1초를 띄운다: 파일 이름이 초 단위 시각이라 같은 초의 새 파일은 이름이 겹친다) ──
H_MAIN="$T/h-main" H_UNK_LEG="$T/h-legacy" H_UNK_EMPTY="$T/h-empty" H_STALE_A="$T/h-stale-a" H_STALE_U="$T/h-stale-u"
H_BROKEN="$T/h-broken" H_BROKEN_ONLY="$T/h-broken-only" H_NOHIT="$T/h-nohit" H_DIRFAIL="$T/h-dirfail" H_WFAIL="$T/h-wfail"
mkdir -p "$H_MAIN" "$H_UNK_LEG" "$H_UNK_EMPTY" "$H_STALE_A" "$H_STALE_U" "$H_BROKEN" "$H_BROKEN_ONLY" "$H_NOHIT" "$H_DIRFAIL" "$H_WFAIL" \
  || { echo "UNRUN  임시 HOME 실패"; exit 2; }

WHY=""
blk main-a1 "$H_MAIN" "$CS_A"; fresh_ok "$H_MAIN" "$CS_A" main-a1
FILE_A="$FILE" SID_A="$SID"
[ "$(count "$H_MAIN")" = 1 ] || add "main-a1: 파일 수 $(count "$H_MAIN") (기대 1)"
verdict first-run-new-file "$WHY" "빈 폴더 · 세션 A → 새 파일 1개 · JSON(session_id · 이름 · claude_session_id=A · 빈 목록 · in_progress) · 내보낸 두 변수 = 그 파일"

blk legacy0 "$H_UNK_LEG" -; FILE_LEG="$FILE"; [ -f "$FILE_LEG" ] && make_legacy "$FILE_LEG"
blk empty0 "$H_UNK_EMPTY" -; FILE_EMPTY="$FILE"
blk stale-a0 "$H_STALE_A" "$CS_A"; FILE_STALE_A="$FILE"; [ -f "$FILE_STALE_A" ] && touch -t 202001010000 "$FILE_STALE_A"
blk stale-u0 "$H_STALE_U" -; FILE_STALE_U="$FILE"; [ -f "$FILE_STALE_U" ] && touch -t 202001010000 "$FILE_STALE_U"
blk broken0 "$H_BROKEN" "$CS_A"; FILE_VALID="$FILE"
sleep 1

# ── 2단계 ──
WHY=""
SUM_A="$(sum "$FILE_A")"
blk main-b1 "$H_MAIN" "$CS_B"; fresh_ok "$H_MAIN" "$CS_B" main-b1
FILE_B="$FILE"
[ "$FILE_B" != "$FILE_A" ] || add "main-b1: 세션 B 가 A 파일을 이어받았다"
[ "$(count "$H_MAIN")" = 2 ] || add "main-b1: 파일 수 $(count "$H_MAIN") (기대 2)"
[ "$(sum "$FILE_A")" = "$SUM_A" ] || add "main-b1: A 파일이 바뀌었다"
verdict other-session-new-file "$WHY" "60분 안의 A 파일 · 세션 B → 새 파일(claude_session_id=B) · A 파일 바이트 불변 · 파일 2"

WHY=""
if [ "$(count "$H_MAIN")" != 2 ] || [ "$FILE_B" = "$FILE_A" ]; then
  add "전제: 두 세션의 파일이 따로 있어야 한다(파일 수 $(count "$H_MAIN"))"
else
  SUM_B="$(sum "$FILE_B")"
  blk main-a2 "$H_MAIN" "$CS_A"; reuse_ok "$FILE_A" main-a2
  [ "$SID" = "$SID_A" ] || add "main-a2: GPT_SESSION_ID[$SID] ≠ 첫 실행의 [$SID_A]"
  blk main-b2 "$H_MAIN" "$CS_B"; reuse_ok "$FILE_B" main-b2
  [ "$(count "$H_MAIN")" = 2 ] || add "파일 수 $(count "$H_MAIN") (기대 2)"
  [ "$(sum "$FILE_A")" = "$SUM_A" ] && [ "$(sum "$FILE_B")" = "$SUM_B" ] || add "이어받기가 파일을 바꿨다"
fi
verdict same-session-reuses "$WHY" "세션 A → 더 새 B 파일을 건너뛰고 A 파일 · 세션 B → B 파일 · 파일 2 · 두 파일 바이트 불변"

WHY=""
if [ "$(count "$H_MAIN")" != 2 ] || [ "$FILE_B" = "$FILE_A" ]; then
  add "전제: 두 세션의 파일이 따로 있어야 한다(파일 수 $(count "$H_MAIN"))"
else
  # 바이트도 본다 — 같은 초에 만든 새 파일이 겹친 B 파일 이름을 덮어쓰면 경로만 보면 이어받기로 보인다
  SUM_B="$(sum "$FILE_B")"
  blk main-u "$H_MAIN" -; reuse_ok "$FILE_B" "main-u(미설정)"
  blk main-e "$H_MAIN" ""; reuse_ok "$FILE_B" "main-e(빈 값)"
  [ "$(count "$H_MAIN")" = 2 ] && [ "$(sum "$FILE_A")" = "$SUM_A" ] && [ "$(sum "$FILE_B")" = "$SUM_B" ] \
    || add "main-u · main-e: 파일 수 $(count "$H_MAIN") (기대 2) 또는 파일이 바뀌었다"
fi
SUM_LEG="$(sum "$FILE_LEG")"
if [ -f "$FILE_LEG" ] && ! jq -e 'has("claude_session_id")' "$FILE_LEG" > /dev/null 2>&1; then
  blk legacy1 "$H_UNK_LEG" "$CS_C"; reuse_ok "$FILE_LEG" "legacy1(옛 꼴 파일)"
  [ "$(sum "$FILE_LEG")" = "$SUM_LEG" ] && [ "$(count "$H_UNK_LEG")" = 1 ] || add "legacy1: 옛 꼴 파일이 바뀌었거나 파일이 늘었다"
else
  add "전제: claude_session_id 가 없는 옛 꼴 파일을 만들지 못했다"
fi
if [ -f "$FILE_EMPTY" ] && [ "$(jq -r '.claude_session_id' "$FILE_EMPTY" 2>/dev/null)" = "" ]; then
  SUM_EMPTY="$(sum "$FILE_EMPTY")"
  blk empty1 "$H_UNK_EMPTY" "$CS_C"; reuse_ok "$FILE_EMPTY" "empty1(빈 값 파일)"
  [ "$(count "$H_UNK_EMPTY")" = 1 ] && [ "$(sum "$FILE_EMPTY")" = "$SUM_EMPTY" ] || add "empty1: 빈 값 파일이 바뀌었거나 파일이 늘었다"
else
  add "전제: 세션 id 미설정 실행이 claude_session_id 빈 값 파일을 쓰지 않았다"
fi
verdict unknown-session-age-only "$WHY" "세션 id 미설정 · 빈 값 → 가장 새 파일(B) · 옛 꼴 파일 · 빈 값 파일은 세션 C 도 이어받는다(나이만 본다)"

WHY=""
SUM_SA="$(sum "$FILE_STALE_A")" SUM_SU="$(sum "$FILE_STALE_U")"
blk stale-a1 "$H_STALE_A" "$CS_A"; fresh_ok "$H_STALE_A" "$CS_A" stale-a1
[ -n "$FILE_STALE_A" ] && [ "$FILE" != "$FILE_STALE_A" ] || add "stale-a1: 60분 밖 파일을 이어받았다"
[ "$(sum "$FILE_STALE_A")" = "$SUM_SA" ] || add "stale-a1: 옛 파일이 바뀌었다"
blk stale-u1 "$H_STALE_U" -; fresh_ok "$H_STALE_U" "" stale-u1
[ -n "$FILE_STALE_U" ] && [ "$FILE" != "$FILE_STALE_U" ] || add "stale-u1: 60분 밖 파일을 이어받았다"
[ "$(sum "$FILE_STALE_U")" = "$SUM_SU" ] || add "stale-u1: 옛 파일이 바뀌었다"
verdict stale-file-new "$WHY" "60분 밖 파일 → 같은 세션 · 세션 id 미설정 모두 새 파일 · 옛 파일 바이트 불변"

WHY=""
SUM_PKG="$(sum "$T/cwd/package.json")"
RUNPATH="$T/bin:$PATH"
blk nohit "$H_NOHIT" "$CS_A"; fresh_ok "$H_NOHIT" "$CS_A" nohit
RUNPATH="$PATH"
[ "$(sum "$T/cwd/package.json")" = "$SUM_PKG" ] || add "nohit: 현재 폴더 package.json 이 바뀌었다"
[ "$(count "$H_NOHIT")" = 1 ] || add "nohit: 파일 수 $(count "$H_NOHIT") (기대 1)"
verdict no-hit-new-file "$WHY" "검색 결과 없음(폴더도 없음) · GNU 꼴 xargs · 현재 폴더 package.json → 트래커 폴더 안의 새 파일"

WHY=""
D="$(sessions "$H_BROKEN")" DO="$(sessions "$H_BROKEN_ONLY")"
mkdir -p "$DO" || { echo "UNRUN  트래커 폴더 실패"; exit 2; }
for d in "$D" "$DO"; do
  printf '{\n  "session_id": "SESSION-20200101_000001",\n' > "$d/SESSION-20200101_000001_issues.json"   # 쓰다 끊긴 파일
  : > "$d/SESSION-20200101_000002_issues.json"                                                       # 빈 파일
done
SUM_BR1="$(sum "$D/SESSION-20200101_000001_issues.json")"
if [ -f "$FILE_VALID" ]; then
  blk broken1 "$H_BROKEN" "$CS_A"; reuse_ok "$FILE_VALID" "broken1(깨진 파일 뒤의 같은 세션 파일)"
else
  add "전제: 같은 세션 파일을 만들지 못했다"
fi
blk broken2 "$H_BROKEN_ONLY" "$CS_A"; fresh_ok "$H_BROKEN_ONLY" "$CS_A" broken2
[ "$(count "$H_BROKEN_ONLY")" = 3 ] || add "broken2: 파일 수 $(count "$H_BROKEN_ONLY") (기대 3 — 깨진 둘 + 새 파일)"
[ "$(sum "$D/SESSION-20200101_000001_issues.json")" = "$SUM_BR1" ] && [ ! -s "$D/SESSION-20200101_000002_issues.json" ] \
  || add "깨진 파일이 바뀌었다"
verdict unreadable-json-skipped "$WHY" "60분 안의 더 새 깨진 JSON · 빈 파일 → 건너뛰고 같은 세션 파일 · 깨진 파일뿐이면 새 파일 · 깨진 파일 불변"

# 같은 초 — 세션 A 가 고정 시각 이름으로 만든 파일에 이슈 하나를 적은 뒤 세션 B 가 같은 초에 시작한다. $1=HOME · $2=시각 → FILE_SS · SUM_SS
same_second_a() {
  printf '%s\n' "$2" > "$CLOCK"
  blk "ss-a-$2" "$1" "$CS_A"; FILE_SS="$FILE" SUM_SS=""
  [ "$RC" = 0 ] && [ "$(basename "$FILE_SS")" = "SESSION-$2_issues.json" ] \
    || { add "전제: 세션 A 가 고정 시각 이름을 쓰지 않았다 [exit $RC · $(basename "$FILE_SS")]"; return 1; }
  jq '.issues += [{"id": "ISSUE-001", "severity": "major", "category": "logic_error", "description": "sample issue",
                   "status": "open", "discovered_in": "plan"}]' "$FILE_SS" > "$FILE_SS.tmp" && mv "$FILE_SS.tmp" "$FILE_SS" \
    || { add "전제: A 파일에 이슈를 적지 못했다"; return 1; }
  SUM_SS="$(sum "$FILE_SS")"
}
# A 파일이 그대로인가 — 바이트 · 이슈 1개
a_kept() {
  [ "$(sum "$FILE_SS")" = "$SUM_SS" ] && [ "$(jq '.issues | length' "$FILE_SS" 2>/dev/null)" = 1 ] \
    || add "$1: A 파일이 바뀌었다(이슈 $(jq '.issues | length' "$FILE_SS" 2>/dev/null)개 · 기대 1)"
}
WHY=""
H_SAME="$T/h-same" H_TAKEN="$T/h-taken"
mkdir -p "$H_SAME" "$H_TAKEN" || { echo "UNRUN  임시 HOME 실패"; exit 2; }
RUNPATH="$T/clockbin:$PATH"
if same_second_a "$H_SAME" 20200101_000010; then
  printf '20200101_000010\n' > "$CLOCK"; : > "$CLOCK.log"
  blk same-b "$H_SAME" "$CS_B"; fresh_ok "$H_SAME" "$CS_B" same-b
  [ "$FILE" != "$FILE_SS" ] || add "same-b: 세션 B 가 A 파일 이름을 썼다"
  LC_ALL=C awk 'NR == 1 { a = $1 } NR == 2 { b = $1 } END { exit !(NR >= 2 && b - a >= 0.9) }' "$CLOCK.log" \
    || add "same-b: 1초를 기다린 뒤 시각을 다시 읽지 않았다(읽은 시각 [$(tr '\n' ' ' < "$CLOCK.log")])"
  a_kept same-b
  [ "$(count "$H_SAME")" = 2 ] || add "same-b: 파일 수 $(count "$H_SAME") (기대 2)"
fi
verdict same-second-new-name "$WHY" "같은 초 · 세션 B → A 파일(이슈 1)을 덮어쓰지 않고 1초 뒤 새 시각의 새 이름 · A 파일 바이트 불변 · 파일 2"

WHY=""
if same_second_a "$H_TAKEN" 20200101_000020; then
  # 시도마다 같은 이름 — 블록의 시도 횟수보다 길게 줄 세운다(줄이 떨어지면 실제 시각이라 새 이름이 나 exit 0 으로 잡힌다)
  for i in 1 2 3 4 5 6 7 8; do echo 20200101_000020; done > "$CLOCK"
  blk taken-b "$H_TAKEN" "$CS_B"
  [ "$RC" = 1 ] || add "exit $RC (기대 1)"
  [ -z "$SID" ] && [ -z "$FILE" ] || add "트래커 변수를 내보냈다 [GPT_SESSION_ID=$SID · GPT_TRACKER_FILE=$FILE]"
  LEFT="$(grep -c . "$CLOCK" 2>/dev/null)"
  [ "${LEFT:-8}" -le 6 ] || add "다시 시도하지 않았다(시각을 $((8 - ${LEFT:-8}))번 읽었다 · 기대 2번 이상)"
  a_kept taken-b
  [ "$(count "$H_TAKEN")" = 1 ] || add "파일 수 $(count "$H_TAKEN") (기대 1)"
fi
RUNPATH="$PATH"
verdict same-second-all-taken "$WHY" "같은 초 · 시도마다 이름이 차 있음 → exit 1 · 변수 둘 다 안 내보냄 · A 파일 바이트 불변 · 파일 1"

WHY=""
printf 'not a directory\n' > "$H_DIRFAIL/.claude" || { echo "UNRUN  일반 파일 실패"; exit 2; }
blk dirfail "$H_DIRFAIL" "$CS_A"
[ "$RC" = 1 ] || add "exit $RC (기대 1)"
[ -z "$SID" ] && [ -z "$FILE" ] || add "트래커 변수를 내보냈다 [GPT_SESSION_ID=$SID · GPT_TRACKER_FILE=$FILE]"
[ -f "$H_DIRFAIL/.claude" ] || add "\$HOME/.claude 가 일반 파일로 남지 않았다"
verdict dir-create-failure "$WHY" "트래커 폴더를 만들 수 없음 → exit 1 · 변수 둘 다 안 내보냄"

WHY=""
W="$(sessions "$H_WFAIL")"
mkdir -p "$W" && chmod 555 "$W" || { echo "UNRUN  쓰기 금지 폴더 실패"; exit 2; }
if [ -w "$W" ]; then
  echo "NOTE  write-failure 건너뜀 — 이 계정은 권한 비트 555 폴더에도 쓸 수 있다"
  SKIPPED="$SKIPPED write-failure"
else
  blk wfail "$H_WFAIL" "$CS_A"
  [ "$RC" = 1 ] || add "exit $RC (기대 1)"
  [ -z "$SID" ] && [ -z "$FILE" ] || add "트래커 변수를 내보냈다 [GPT_SESSION_ID=$SID · GPT_TRACKER_FILE=$FILE]"
  [ "$(count "$H_WFAIL")" = 0 ] || add "파일이 생겼다"
  verdict write-failure "$WHY" "트래커 파일을 쓸 수 없음 → exit 1 · 변수 둘 다 안 내보냄 · 파일 0"
fi
chmod 755 "$W" 2>/dev/null

WHY=""
jq -e '(.properties.claude_session_id.type == "string") and (((.required // []) | index("claude_session_id")) == null)' "$SCHEMA" > /dev/null 2>&1 \
  || add "properties.claude_session_id(type string · required 밖)가 없다"
verdict schema-claude-session-id "$WHY" "스키마가 claude_session_id 를 선택 문자열 속성으로 적는다"

want="$(printf '%s\n' $EXPECT_CELLS | LC_ALL=C sort -u)" got="$(printf '%s\n' $RAN $SKIPPED | LC_ALL=C sort -u)"
if [ "$want" = "$got" ]; then echo "셀 집합: PASS 판정한 셀 + 건너뛴 셀 = 기대 셀 ($(printf '%s\n' "$want" | grep -c .)개)"
else echo "셀 집합: FAIL 빠짐 [$(comm -23 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | tr '\n' ' ')]"; FAILS=$((FAILS + 1)); fi
echo
if [ "$FAILS" -eq 0 ]; then
  echo "tracker-reuse: PASS"
  exit 0
fi
echo "tracker-reuse: FAIL ($FAILS 건)"
exit 1
