#!/bin/bash
# gpt-exec.sh 스킬 본문 주입 계약 러너 (A2-03) — 가짜 CLI(../_shim/codex)로 래퍼 계약만 본다.
#
# ⛔ 실제 GPT CLI·사용자 텔레메트리를 건드리지 않는다 — PATH 앞에 shim 폴더, FZ_TELEMETRY_DIR 은 셀마다 임시.
# ⛔ FZ_GPT_EXEC_UNDER_TEST 로 다른 판(기준 트리)의 래퍼를 같은 러너로 돌린다 — 판별력 대조용.
#    그 경우에도 죽지 않고 셀마다 FAIL 줄을 낸다(셀 결과를 읽는 함수는 빈 값을 0/빈 문자열로 돌려준다).
# 스킬 파일은 **합성**이다 — 실제 gpt-skills 내용이 바뀌어도 판정이 흔들리지 않게.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
WRAP="${FZ_GPT_EXEC_UNDER_TEST:-$R/scripts/gpt-exec.sh}"
export PATH="$R/tests/fixtures/gpt/_shim:$PATH"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else no "$1 — 기대 '$3' · 실제 '$2'"; fi; }

HEAD="# Synthetic Role Heading 7f3a"
MARK="[fz-gpt-skill-injected]"
TASK="과제 본문 XYZ-TASK-91"
mkdir -p "$T/fz-demo" "$T/repo"
printf -- '---\nname: fz-demo\ndescription: 합성 역할 스킬\n---\n\n%s\n\n역할 지시 본문 — 합성.\n' "$HEAD" > "$T/fz-demo/SKILL.md"
SK="$T/fz-demo/SKILL.md"
printf '%s\n' "$TASK" > "$T/task.txt"
# 과제 문구에 스킬 제목만 우연히 들어간 프롬프트 — 본문은 없다
printf '%s\n\n%s\n' "$HEAD 를 참고한 요청" "$TASK" > "$T/task-head-only.txt"
# 제목과 그 다음 본문 줄만 든 프롬프트 — 본문 전체는 없다(번들 스킬은 다음 줄이 모두 `## Role` 이라 이 조합은 구별되지 않는다)
printf '%s\n역할 지시 본문 — 합성.\n\n%s\n' "$HEAD" "$TASK" > "$T/task-head-next.txt"
# 호출 계약 8곳의 형태 — 본문을 `$(cat SKILL.md)` 로 먼저 넣은 프롬프트
printf '%s\n\n%s\n' "$(cat "$SK")" "$TASK" > "$T/task-with-skill.txt"
echo '11111111-2222-3333-4444-555555555555' > "$T/prev.session"
printf '{"type":"object","required":["verdict"],"properties":{"verdict":{"type":"string"}}}\n' > "$T/schema.json"

SHIM_OUT="ok" SHIM_EXIT=0
cell() {   # $1=셀 이름 · 나머지=래퍼 인자(모드 먼저). 결과 파일은 $T/c-이름/ 아래
  local name="$1"; shift
  local d="$T/c-$name"; mkdir -p "$d/tel"
  env FZ_SHIM_CAPTURE="$d/argv.json" FZ_SHIM_OUTPUT="$SHIM_OUT" FZ_SHIM_EXIT="$SHIM_EXIT" FZ_TELEMETRY_DIR="$d/tel" \
    bash "$WRAP" "$@" --cd "$T/repo" --out "$d/out.txt" > "$d/stdout" 2> "$d/stderr"
  echo $? > "$d/rc"
}
rc() { cat "$T/c-$1/rc" 2>/dev/null || echo "?"; }
count() {   # argv 전체에서 문자열 등장 횟수 (캡처 없으면 0)
  [ -s "$T/c-$1/argv.json" ] || { echo 0; return; }
  python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1], encoding="utf-8"))).count(sys.argv[2]))' "$T/c-$1/argv.json" "$2"
}
tel() {     # 텔레메트리 마지막 행의 n번째 열 (없으면 빈 값)
  local f="$T/c-$1/tel/gpt-skill-usage.tsv"
  [ -s "$f" ] || { echo ""; return; }
  tail -1 "$f" | awk -F'\t' -v c="$2" '{print $c}'
}

# ⓪ 경로가 디렉터리·공백뿐 파일이면 본문 없이 injected=1 이 되던 경로(v4.40.0 리뷰) — 호출 전에 exit 11
mkdir -p "$T/skill-dir"; printf '  \n\t\n' > "$T/blank-skill.md"
cell pdir exec --prompt-file "$T/task.txt" --gpt-skill fz-demo --gpt-skill-path "$T/skill-dir"
check "경로가 디렉터리: exit 11" "$(rc pdir)" 11
cell pblank exec --prompt-file "$T/task.txt" --gpt-skill fz-demo --gpt-skill-path "$T/blank-skill.md"
check "경로가 공백뿐 파일: exit 11" "$(rc pblank)" 11
check "공백뿐 파일: GPT 미호출" "$(count pblank "$TASK")" 0

# ① exec + 경로 → 마커·제목 정확히 1회, 과제 보존, injected=1 · fallback=0
cell exec1 exec --prompt-file "$T/task.txt" --gpt-skill fz-demo --gpt-skill-path "$SK"
check "exec 주입: exit" "$(rc exec1)" 0
check "exec 주입: 마커 1회" "$(count exec1 "$MARK")" 1
check "exec 주입: 본문 첫 제목 1회" "$(count exec1 "$HEAD")" 1
check "exec 주입: 과제 본문 보존" "$(count exec1 "$TASK")" 1
check "exec 주입: 텔레메트리 injected=1" "$(tel exec1 7)" 1
check "exec 주입: 텔레메트리 fallback=0" "$(tel exec1 5)" 0
[ -n "$(tel exec1 8)" ] && [ "$(tel exec1 8)" != "-" ] && ok "exec 주입: 텔레메트리 cli_version 기록" || no "exec 주입: cli_version 열이 비었다"

# ② 호출 계약 8곳(cat) + --gpt-skill-path 동시 → 본문은 여전히 1회(멱등), injected=1
cell exec2 exec --prompt-file "$T/task-with-skill.txt" --gpt-skill fz-demo --gpt-skill-path "$SK"
check "멱등: 본문 첫 제목 1회" "$(count exec2 "$HEAD")" 1
check "멱등: 마커 0회(이미 들어 있어 주입 생략)" "$(count exec2 "$MARK")" 0
check "멱등: 텔레메트리 injected=1" "$(tel exec2 7)" 1

# ②-b 제목만 우연히 포함 → 본문이 없으므로 주입한다(생략하면 역할 없이 injected=1 로 집계된다)
cell headonly exec --prompt-file "$T/task-head-only.txt" --gpt-skill fz-demo --gpt-skill-path "$SK"
check "제목만 우연히 포함: 마커 1회(주입함)" "$(count headonly "$MARK")" 1
check "제목만 우연히 포함: 본문 줄 1회" "$(count headonly "역할 지시 본문 — 합성.")" 1

# ②-c 제목 + 다음 줄만 포함 → 본문 전체가 아니므로 주입한다
cell headnext exec --prompt-file "$T/task-head-next.txt" --gpt-skill fz-demo --gpt-skill-path "$SK"
check "제목+다음 줄만 포함: 마커 1회(주입함)" "$(count headnext "$MARK")" 1

# ③ resume + 경로 → 주입 (--gpt-skill 없이도 행을 쓴다 · requested='-')
cell resume1 resume --prompt-file "$T/task.txt" --session-file "$T/prev.session" --gpt-skill-path "$SK"
check "resume 주입: exit" "$(rc resume1)" 0
check "resume 주입: 마커 1회" "$(count resume1 "$MARK")" 1
check "resume 주입: 본문 첫 제목 1회" "$(count resume1 "$HEAD")" 1
check "resume 주입: 텔레메트리 requested='-'" "$(tel resume1 3)" "-"
check "resume 주입: 텔레메트리 injected=1" "$(tel resume1 7)" 1

# ④ review + 경로 → 프롬프트 없음 + WARN, injected=0
cell review1 review --uncommitted --gpt-skill fz-demo --gpt-skill-path "$SK"
check "review: exit" "$(rc review1)" 0
check "review: 본문 주입 0회" "$(count review1 "$HEAD")" 0
grep -q "WARN" "$T/c-review1/stderr" 2>/dev/null && grep -q -- "--gpt-skill-path" "$T/c-review1/stderr" 2>/dev/null \
  && ok "review: WARN(주입 불가) 출력" || no "review: --gpt-skill-path WARN 이 없다"
check "review: 텔레메트리 injected=0" "$(tel review1 7)" 0

# ⑤ 빈 경로 → 주입 없음, fallback=1 · injected=0
cell empty1 exec --prompt-file "$T/task.txt" --gpt-skill fz-demo --gpt-skill-path ""
check "빈 경로: exit" "$(rc empty1)" 0
check "빈 경로: 마커 0회" "$(count empty1 "$MARK")" 0
check "빈 경로: 텔레메트리 fallback=1" "$(tel empty1 5)" 1
check "빈 경로: 텔레메트리 injected=0" "$(tel empty1 7)" 0

# ⑥ 경로가 있는데 파일이 없다 → exit 11 (호출 전 사전조건)
cell missing1 exec --prompt-file "$T/task.txt" --gpt-skill-path "$T/nope/SKILL.md"
check "없는 스킬 파일: exit 11" "$(rc missing1)" 11

# 회귀 셀 — 기존 계약 유지
cell rvp review --uncommitted --prompt-file "$T/task.txt"
check "회귀: review + --prompt-file → exit 10" "$(rc rvp)" 10
SHIM_OUT=""; cell emptyout exec --prompt-file "$T/task.txt"; SHIM_OUT="ok"
check "회귀: 빈 출력 → exit 13" "$(rc emptyout)" 13
SHIM_OUT="{}"; cell schema exec --prompt-file "$T/task.txt" --schema "$T/schema.json"; SHIM_OUT="ok"
check "회귀: 스키마 위반 → exit 14" "$(rc schema)" 14
SHIM_EXIT=1; cell gptfail exec --prompt-file "$T/task.txt"; SHIM_EXIT=0
check "회귀: CLI 비정상 종료 → exit 12" "$(rc gptfail)" 12

# 플래그 검사기(check-gpt-flags.sh:46-47)의 awk 범위가 비지 않는다 — 비면 그 검사기가 조용히 통과한다
A1="$(awk '/^ARGS=\(/,/^ARGS\+=\(-o/' "$WRAP")"
A2="$(awk '/^if \[ "\$MODE" = "review" \]; then$/,/^else$/' "$WRAP" | grep 'ARGS+=')"
[ -n "$A1" ] && [ -n "$A2" ] && ok "플래그 검사기 awk 범위 2개 비어 있지 않음" || no "플래그 검사기 awk 범위가 비었다 (ARGS 블록 $(printf '%s' "$A1" | grep -c .)줄 · review 분기 ARGS+= $(printf '%s' "$A2" | grep -c .)줄)"

echo
[ "$fail" -eq 0 ] && echo "skill-inject: 전건 통과" || echo "skill-inject: 실패 있음"
exit "$fail"
