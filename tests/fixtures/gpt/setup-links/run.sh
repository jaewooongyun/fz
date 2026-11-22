#!/bin/bash
# modes: --stale-exit caller=manual last-pass=7b89bd4 result=--stale-exit 1 · 20 PASS(2026-11-05 배선 감사)
# gpt-cli: none — health-check.sh 는 4.5b 'GPT 스킬 링크' 본문만 떼어 돌린다(§4.5 check-gpt-flags · GPT CLI 에 닿지 않는다)
# setup-gpt-skills.sh 링크 계약 러너 (A2-02).
#
# 판정: ① GPT 스킬(SKILL.md 가진 gpt-skills/ 전부)이 현 판으로 링크된다 ② 이 플러그인 skills/ 를 가리키는
#       링크가 0 이다(구버전 캐시·이름 무관 포함) ③ 다른 플러그인 링크·실제 디렉토리는 보존된다
#       ④ 재실행은 멱등이다 ⑤ Tier 2a 디스커버리(resolver `scripts/gpt_kinds.py skill-path`)가 역할 전부를 이 폴더에서 해석한다
#          (링크된 판 P 가 resolver 의 트리 R 과 다른 같은 이름 루트면 resolver 는 R 번들을 돌려준다 — 기대값도 그쪽이다)
#       ⑥ 인자 없으면 agents 폴더를 건드리지 않는다 ⑦ 셀 retired-option-gpt-agents — 걷은 옵션(역할 파일 링크 opt-in)으로 부르면
#          조용히 받지 않는다: exit 1 · 옵션 이름 · 스킬 폴더 그대로 · agents 폴더 없음
#       ⑧ --check 읽기 전용 점검(F-353) — 셀 check-stale-owned · check-preserve-unowned · check-clean-after-setup · check-missing-listed.
#          stale 이면 --stale-exit 값과 **정확한 목록**(`  stale: <이름>` 줄의 이름 집합), 정리 뒤 exit 0 · 목록 0,
#          전후 트리 해시 동일 · 스킬 폴더가 없으면 만들지 않는다 · 비소유 링크와 설치 루트가 다른 소유 GPT 링크는 목록에 없다
#          ⛔ 기준 트리는 --check 를 모르는 옵션으로 exit 1 한다 — stale exit 1 과 종료 코드로는 구별되지 않아 목록 단언이 판별한다
#          check-missing-listed — 번들 역할 스킬 가운데 스킬 폴더에 항목이 없는 이름이 `  missing: <이름>` 줄로 정확히 나온다
#          (stale 아님 · exit 무변경) · 정리 뒤 0 · 스킬 폴더가 없는 빈 홈은 전부 missing 이면서 폴더를 만들지 않는다
#          check-missing-dangling — 같은 이름의 끊긴 링크는 missing 이 아니다(unknown 그대로)
#          health-missing-note — 이 트리 health-check 4.5b 본문(record 는 대역)이 missing 건수를 비고에 싣고 record 는 0 그대로다
#       ⑨ 셀 check-removed-role-skill — 이전 판 설치의 마이그레이션: 이 판이 걷은(이 판 gpt-skills 에 없는) 역할 스킬을 가리키는
#          링크(구버전 캐시의 살아 있는 링크 · 이 루트의 끊긴 링크)를 --check 가 stale 로 내고, 정리가 지우고, 정리 뒤 --check 는 0 이다
# ⛔ 실제 사용자 폴더를 건드리지 않는다 — HOME·FZ_SKILL_TARGET 은 임시 폴더, CODEX_HOME 은 비운다.
# ⛔ FZ_SETUP_UNDER_TEST 로 다른 판(기준 트리)의 스크립트를 같은 러너로 돌린다 — 판별력 대조용.
#    이때 기대값은 **그 스크립트의** 플러그인 루트 기준이다.
# 인자: --tree <플러그인 트리>  그 트리의 scripts/setup-gpt-skills.sh 를 돌린다(FZ_SETUP_UNDER_TEST 와 같은 주입 · 둘 다 주면 --tree)
#       --stale-exit <n>       stale 일 때 기대하는 --check 종료 코드(1~255 · 기본 1 — SC-11)
# exit: 0 전건 통과 · 1 단언 실패 있음 · 3 준비 실패(인자 · 스크립트 부재 · 이름 못 읽음 · 끝까지 못 간 비정상 종료 — 1 로 새지 않는다)
set -u
FIN=0
TREE="" STALE_EXIT=1
while [ $# -gt 0 ]; do
  case "$1" in
    --tree) [ $# -ge 2 ] || { echo "PREP  --tree 값이 없다"; exit 3; }; TREE="$2"; shift 2 ;;
    --stale-exit) [ $# -ge 2 ] || { echo "PREP  --stale-exit 값이 없다"; exit 3; }; STALE_EXIT="$2"; shift 2 ;;
    *) echo "PREP  알 수 없는 인자: $1 (사용법: run.sh [--tree <dir>] [--stale-exit <n>])"; exit 3 ;;
  esac
done
case "$STALE_EXIT" in ''|*[!0-9]*) echo "PREP  --stale-exit 는 1~255 정수다: $STALE_EXIT"; exit 3 ;; esac
[ "$STALE_EXIT" -ge 1 ] && [ "$STALE_EXIT" -le 255 ] || { echo "PREP  --stale-exit 는 1~255 정수다: $STALE_EXIT"; exit 3; }
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
if [ -n "$TREE" ]; then SETUP="$TREE/scripts/setup-gpt-skills.sh"; else SETUP="${FZ_SETUP_UNDER_TEST:-$R/scripts/setup-gpt-skills.sh}"; fi
[ -f "$SETUP" ] || { echo "PREP  setup 스크립트가 없다 — $SETUP"; exit 3; }
P="$(cd "$(dirname "$SETUP")/.." && pwd)" || { echo "PREP  플러그인 루트를 풀지 못했다 — $SETUP"; exit 3; }
T="$(mktemp -d)" || { echo "PREP  임시 폴더를 만들지 못했다"; exit 3; }
trap 'rm -rf "$T"; [ "$FIN" = 1 ] || exit 3' EXIT
H="$T/home"; TG="$H/.codex/skills"; mkdir -p "$TG"
mname() { python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1], encoding="utf-8")).get("name", ""))
except Exception: pass' "$1/.claude-plugin/plugin.json" 2>/dev/null; }
NAME="$(mname "$P")"
[ -n "$NAME" ] || { echo "PREP  플러그인 이름을 읽지 못했다 — $P"; exit 3; }

fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }

# 구버전 캐시(같은 플러그인 이름) · 다른 플러그인
OLD="$T/cache/$NAME/4.30.0"
mkdir -p "$OLD/.claude-plugin" "$OLD/skills/arch-critic" "$OLD/skills/code-auditor" "$OLD/gpt-skills/fz-architect"
printf '{\n  "name": "%s",\n  "version": "4.30.0"\n}\n' "$NAME" > "$OLD/.claude-plugin/plugin.json"
for f in "$OLD/skills/arch-critic" "$OLD/skills/code-auditor" "$OLD/gpt-skills/fz-architect"; do echo x > "$f/SKILL.md"; done
OTH="$T/other"
mkdir -p "$OTH/.claude-plugin" "$OTH/skills/other-skill"
printf '{\n  "name": "other-plugin"\n}\n' > "$OTH/.claude-plugin/plugin.json"
echo x > "$OTH/skills/other-skill/SKILL.md"
mkdir -p "$OTH/gpt-skills/fz-reviewer"; echo x > "$OTH/gpt-skills/fz-reviewer/SKILL.md"
# 중첩 name 이 들여쓰기 2칸으로 먼저 나오는 다른 플러그인 매니페스트 — 줄 근사로 읽으면 이 플러그인으로 오인한다
OTH2="$T/other2"
mkdir -p "$OTH2/.claude-plugin" "$OTH2/skills/o2"
printf '{\n  "metadata": {\n  "name": "%s"\n  },\n  "name": "other-two"\n}\n' "$NAME" > "$OTH2/.claude-plugin/plugin.json"
echo x > "$OTH2/skills/o2/SKILL.md"

ln -s "$P/skills/fz-review" "$TG/fz-review"              # 현 판 Claude 스킬 → prune
ln -s "$OLD/skills/arch-critic" "$TG/arch-critic"        # 구버전 캐시 Claude 스킬(이름 무관) → prune
ln -s "$OLD/skills/code-auditor" "$TG/code-auditor"      # → prune
ln -s "$OLD/gpt-skills/fz-architect" "$TG/fz-architect"  # 구버전 GPT 스킬 → 현 판으로 재링크
ln -s "$OTH/skills/other-skill" "$TG/other-skill"        # 다른 플러그인 → 보존
ln -s "$OTH/gpt-skills/fz-reviewer" "$TG/fz-reviewer"    # 살아 있는 남의 같은 이름 GPT 스킬 링크 → 보존(교체 안 함)
ln -s "$OTH2/skills/o2" "$TG/o2-skill"                    # 중첩 name 매니페스트의 다른 플러그인 → 보존
mkdir -p "$TG/my-real-dir"; echo x > "$TG/my-real-dir/SKILL.md"   # 실제 디렉토리 → 보존
ln -s "$T/nowhere/fz-gone" "$TG/fz-gone"                  # dangling fz-* · 소유 판정 불가(루트 없음) → 보존
ln -s "$P/gpt-skills/fz-renamed-old" "$TG/fz-renamed-old"  # dangling · 이 플러그인 gpt-skills(개명된 옛 스킬) → prune
ln -s "$OTH/skills/gone-skill" "$TG/fz-other"             # dangling · 다른 플러그인 소유 → 보존
ln -s "$P/skills/fz-plan/../fz-review" "$TG/fz-dotdot"    # `..` 가 든 Claude 스킬 링크 → 정규화 후 prune
ln -s "$P/skills/fz-review//" "$TG/fz-slash"              # 끝 슬래시 2개 → 정규화 후 prune

run() { env -u CODEX_HOME HOME="$H" FZ_SKILL_TARGET="$TG" bash "$SETUP" > "$T/out.$1" 2>&1; }
snap() { for f in "$TG"/*; do if [ -L "$f" ]; then echo "$(basename "$f") -> $(readlink "$f")"; else echo "$(basename "$f") DIR"; fi; done; }
# ⑧ --check 도구 — 종료 코드는 호출 직후 변수로 받는다. tsig = 임시 트리 전체(러너 출력 out.* 제외)의 파일 내용·링크 대상·폴더 해시
# ⛔ PYTHONDONTWRITEBYTECODE=1 — 시스템 python3 는 $HOME/Library/Caches 에 바이트코드 캐시를 쓴다(인터프리터 부작용 · 실측).
#    끄지 않으면 임시 홈 해시가 스크립트와 무관하게 바뀐다 — 재는 것은 스크립트의 쓰기다
runc() { env -u CODEX_HOME PYTHONDONTWRITEBYTECODE=1 HOME="$H" FZ_SKILL_TARGET="$TG" bash "$SETUP" --check > "$T/out.$1" 2>&1; }
stale_set() { sed -n 's/^  stale: \([^ ]*\) .*/\1/p' "$1" | LC_ALL=C sort; }
unknown_set() { sed -n 's/^  unknown: \([^ ]*\) .*/\1/p' "$1" | LC_ALL=C sort; }
missing_set() { sed -n 's/^  missing: \([^ ]*\) .*/\1/p' "$1" | LC_ALL=C sort; }
tsig() { (cd "$T" && find . ! -name 'out.*' -print | LC_ALL=C sort | while IFS= read -r p; do
  if [ -L "$p" ]; then echo "L $p -> $(readlink "$p")"; elif [ -d "$p" ]; then echo "D $p"; else echo "F $p $(shasum -a 256 < "$p")"; fi
done) | shasum -a 256; }
words() { printf '%s' "$1" | tr '\n' ' '; }

# ⑧-1 check-stale-owned — 정리 전: 소유 stale 6건(이름 무관 · 구버전 캐시 · `..` · 끝 슬래시 · 소유 dangling)이 정확히 나온다
want_missing0="$(for d in "$P"/gpt-skills/*/; do [ -f "$d/SKILL.md" ] || continue; n="$(basename "$d")"
  [ -e "$TG/$n" ] || [ -L "$TG/$n" ] || echo "$n"; done | LC_ALL=C sort)"   # 정리 전 기대 missing — 번들 이름 − 스킬 폴더에 항목이 있는 이름
sig0="$(tsig)"; runc c0; rc0=$?; sig1="$(tsig)"
want_stale="$(printf '%s\n' fz-review arch-critic code-auditor fz-renamed-old fz-dotdot fz-slash | LC_ALL=C sort)"
got_stale="$(stale_set "$T/out.c0")"
[ "$rc0" -eq "$STALE_EXIT" ] && [ "$got_stale" = "$want_stale" ] && grep -qE '^Check: 6 stale in ' "$T/out.c0" \
  && ok "check-stale-owned: --check exit $rc0 · 정확한 목록 6건" \
  || no "check-stale-owned: --check exit $rc0(기대 $STALE_EXIT) · 목록 [$(words "$got_stale")] · 기대 [$(words "$want_stale")] — $(tail -1 "$T/out.c0")"
# ⑧-2 check-preserve-unowned — 같은 호출의 전후 해시 동일 · 비소유(남의 링크 · 실제 폴더 · 판정 불가 dangling)와
#      설치 루트가 다른 소유 GPT 링크(fz-architect → 구버전 캐시)는 목록에 없다 · 스킬 폴더가 없는 홈에서는 만들지 않는다
listed=""
for n in fz-architect other-skill fz-reviewer o2-skill my-real-dir fz-gone fz-other; do
  printf '%s\n' "$got_stale" | grep -qx "$n" && listed="$listed $n"
done
EH="$T/empty-home"; mkdir -p "$EH"
env -u CODEX_HOME -u FZ_SKILL_TARGET PYTHONDONTWRITEBYTECODE=1 HOME="$EH" bash "$SETUP" --check > "$T/out.c-empty" 2>&1; rce=$?
want_unknown="$(printf '%s\n' fz-gone fz-other | LC_ALL=C sort)"; got_unknown="$(unknown_set "$T/out.c0")"
[ "$sig0" = "$sig1" ] && [ -z "$listed" ] && [ "$got_unknown" = "$want_unknown" ] && [ "$rce" -eq 0 ] && [ -z "$(stale_set "$T/out.c-empty")" ] && [ -z "$(ls -A "$EH")" ] \
  && ok "check-preserve-unowned: 전후 해시 동일 · 비소유·다른 설치 루트 링크 목록 0 · 판정 불가 dangling 은 unknown 으로 따로 · 빈 홈 exit 0 · 폴더 생성 0" \
  || no "check-preserve-unowned: 해시 $([ "$sig0" = "$sig1" ] && echo 동일 || echo 변경) · 잘못 나온 이름[$listed] · unknown [$(words "$got_unknown")] 기대 [$(words "$want_unknown")] · 빈 홈 exit $rce · 빈 홈 항목[$(words "$(ls -A "$EH")")]"

run 1 && ok "setup exit 0" || no "setup exit $? — $(tail -2 "$T/out.1" | tr '\n' ' ')"

want=0 good=0
for d in "$P"/gpt-skills/*/; do
  [ -f "$d/SKILL.md" ] || continue
  n="$(basename "$d")"
  [ "$n" = "fz-reviewer" ] && continue          # 남의 같은 이름 링크를 심어 둔 이름 — 아래에서 보존을 따로 본다
  want=$((want + 1))
  [ "$(readlink "$TG/$n" 2>/dev/null)" = "${d%/}" ] && good=$((good + 1))
done
[ "$want" -gt 0 ] && [ "$good" -eq "$want" ] && ok "GPT 스킬 링크 $good/$want (현 판)" || no "GPT 스킬 링크 $good/$want"

claude_links=""
for f in "$TG"/*; do
  [ -L "$f" ] || continue
  dest="$(readlink "$f")"
  case "$dest" in */skills/*) ;; *) continue ;; esac
  root="${dest%/skills/*}"
  [ "$(mname "$root")" = "$NAME" ] && claude_links="$claude_links $(basename "$f")"
done
[ -z "$claude_links" ] && ok "이 플러그인 skills/ 를 가리키는 링크 0" || no "Claude 스킬 링크가 남았다:$claude_links"

gone=""
for n in fz-review arch-critic code-auditor fz-renamed-old fz-dotdot fz-slash; do [ -e "$TG/$n" ] || [ -L "$TG/$n" ] && gone="$gone $n"; done
[ -z "$gone" ] && ok "미리 심은 Claude 스킬(·..·끝 슬래시 포함)·소유 dangling 링크 prune" || no "prune 되지 않았다:$gone"
kept=""
for n in fz-gone fz-other; do [ -L "$TG/$n" ] || kept="$kept $n"; done
[ -z "$kept" ] && ok "소유 판정 불가·다른 플러그인의 끊어진 fz-* 보존" || no "남의 링크를 지웠다:$kept"

[ "$(readlink "$TG/other-skill")" = "$OTH/skills/other-skill" ] && ok "다른 플러그인 링크 보존" || no "다른 플러그인 링크가 바뀌었다"
[ "$(readlink "$TG/fz-reviewer")" = "$OTH/gpt-skills/fz-reviewer" ] && ok "살아 있는 남의 같은 이름 링크 보존(교체 안 함)" || no "남의 fz-reviewer 링크를 바꿨다"
[ "$(readlink "$TG/o2-skill")" = "$OTH2/skills/o2" ] && ok "중첩 name 매니페스트의 다른 플러그인 링크 보존" || no "중첩 name 을 소유로 오인해 o2-skill 을 지웠다"
[ -d "$TG/my-real-dir" ] && [ ! -L "$TG/my-real-dir" ] && [ -f "$TG/my-real-dir/SKILL.md" ] && ok "실제 디렉토리 보존" || no "실제 디렉토리가 바뀌었다"

# ⑧-3 check-clean-after-setup — 정리(run 1) 뒤 --check 는 exit 0 · 목록 0 · 전후 해시 동일, 정리 전 목록 = setup 이 지운 목록
pruned_set="$(sed -n 's/^  prune: \([^ ]*\) .*/\1/p' "$T/out.1" | LC_ALL=C sort)"
sig2="$(tsig)"; runc c2; rc2=$?; sig3="$(tsig)"
[ "$rc2" -eq 0 ] && [ -z "$(stale_set "$T/out.c2")" ] && grep -qE '^Check: 0 stale in ' "$T/out.c2" && [ "$sig2" = "$sig3" ] && [ "$pruned_set" = "$got_stale" ] \
  && ok "check-clean-after-setup: 정리 뒤 exit 0 · 목록 0 · 전후 해시 동일 · 정리 전 목록 = 지운 목록" \
  || no "check-clean-after-setup: exit $rc2 · 남은 목록[$(words "$(stale_set "$T/out.c2")")] · 해시 $([ "$sig2" = "$sig3" ] && echo 동일 || echo 변경) · 지운 목록[$(words "$pruned_set")] — $(tail -1 "$T/out.c2")"

# ⑧-4 check-missing-listed — 정리 전(c0) missing 집합 = 번들 이름 − 스킬 폴더에 항목이 있는 이름 · 정리 뒤(c2) 0 · 빈 홈은 번들 전부
want_missing_e="$(for d in "$P"/gpt-skills/*/; do [ -f "$d/SKILL.md" ] && basename "$d"; done | LC_ALL=C sort)"
got_missing0="$(missing_set "$T/out.c0")"; got_missing2="$(missing_set "$T/out.c2")"; got_missing_e="$(missing_set "$T/out.c-empty")"
[ -n "$want_missing0" ] && [ "$got_missing0" = "$want_missing0" ] && [ -z "$got_missing2" ] && [ "$got_missing_e" = "$want_missing_e" ] && [ -z "$(ls -A "$EH")" ] \
  && ok "check-missing-listed: 정리 전 missing $(printf '%s\n' "$got_missing0" | grep -c .)건 정확 · 정리 뒤 0 · 빈 홈 $(printf '%s\n' "$got_missing_e" | grep -c .)건 · 폴더 생성 0" \
  || no "check-missing-listed: 정리 전 [$(words "$got_missing0")] 기대 [$(words "$want_missing0")] · 정리 뒤 [$(words "$got_missing2")] · 빈 홈 [$(words "$got_missing_e")] 기대 [$(words "$want_missing_e")] · 빈 홈 항목[$(words "$(ls -A "$EH")")]"
# ⑧-4b check-missing-dangling — 같은 이름의 끊긴 링크(소유 판정 불가)는 unknown 으로만 나오고 missing 에는 없다
DH="$T/dangling-home"; mkdir -p "$DH/skills"; dn="$(printf '%s\n' "$want_missing_e" | head -1)"; ln -s "$T/nowhere/$dn" "$DH/skills/$dn"
env -u CODEX_HOME PYTHONDONTWRITEBYTECODE=1 HOME="$DH" FZ_SKILL_TARGET="$DH/skills" bash "$SETUP" --check > "$T/out.c-dangling" 2>&1
want_missing_d="$(printf '%s\n' "$want_missing_e" | grep -vx "$dn")"
[ -n "$dn" ] && [ "$(missing_set "$T/out.c-dangling")" = "$want_missing_d" ] && [ "$(unknown_set "$T/out.c-dangling")" = "$dn" ] \
  && ok "check-missing-dangling: 같은 이름의 끊긴 링크($dn)는 unknown 으로만 · missing 에 없다" \
  || no "check-missing-dangling: 끊긴 링크 $dn — missing [$(words "$(missing_set "$T/out.c-dangling")")] · unknown [$(words "$(unknown_set "$T/out.c-dangling")")]"
# ⑧-5 health-missing-note — health-check 4.5b 'GPT 스킬 링크' 본문만 떼어 돌린다(record 는 대역 · 대상은 이 트리 R 의 setup).
#      스킬 폴더가 없는 홈 → record 0 · 비고에 '역할 링크 없음 <R 번들 수>건' / 정리한 홈 → record 0 · 그 말이 없다
HB="$T/hc-45b.sh"; HE="$T/hc-empty-home"; mkdir -p "$HE"
{ echo 'record() { printf "RECORD|%s|%s|%s\n" "$1" "$2" "$3"; }'; printf 'ROOT=%q\n' "$R"; sed -n '/^SL_OUT=/,/^fi$/p' "$R/scripts/health-check.sh"; } > "$HB"
hn="$(ls "$R"/gpt-skills/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')"
he="$(env -u CODEX_HOME -u FZ_SKILL_TARGET HOME="$HE" bash "$HB" 2>&1)"; hl="$(env -u CODEX_HOME -u FZ_SKILL_TARGET HOME="$H" bash "$HB" 2>&1)"
case "$he" in "RECORD|GPT 스킬 링크|0|"*"역할 링크 없음 ${hn}건"*) he_ok=1 ;; *) he_ok=0 ;; esac
case "$hl" in "RECORD|GPT 스킬 링크|0|"*"역할 링크 없음"*) hl_ok=0 ;; "RECORD|GPT 스킬 링크|0|"*) hl_ok=1 ;; *) hl_ok=0 ;; esac
[ "$hn" -gt 0 ] && [ "$he_ok" = 1 ] && [ "$hl_ok" = 1 ] \
  && ok "health-missing-note: 빈 홈 비고에 역할 링크 없음 ${hn}건 · 정리한 홈은 그 말 없음 · record 0" \
  || no "health-missing-note: 빈 홈 [$he] · 정리한 홈 [$hl] · 번들 $hn"

before="$(snap)"; run 2; after="$(snap)"
[ "$before" = "$after" ] && ok "재실행 멱등" || no "재실행이 상태를 바꿨다"

# ⑤ Tier 2a — 정본 구현(resolver scripts/gpt_kinds.py skill_path — R-G1 에서 문서 인라인 함수를 옮겼다)을 실행한다.
#    resolver 는 Tier 2a 가 없으면 플러그인 번들(Tier 2b)을 돌려준다 — 기대값이 Tier 2a 경로라 링크가 깨지면 그대로 miss 다.
#    P == R(실경로)이면 Tier 2a 경로다. P ≠ R 이고 매니페스트 name 이 같으면(--tree · FZ_SETUP_UNDER_TEST 로 다른 판을 링크했다)
#    resolver 는 P 를 가리키는 링크 대신 자기 트리 R 의 번들을 돌려준다 — 그 역할의 R 번들이 있을 때만이고, 없거나 링크가 P 가 아닌
#    곳(남의 플러그인 fz-reviewer)을 가리키면 Tier 2a 경로다
if [ ! -f "$R/scripts/gpt_kinds.py" ]; then
  no "resolver scripts/gpt_kinds.py 가 없다"
else
  roles=0 hit=0 miss=""
  other_root=0; [ "$(cd "$P" && pwd -P)" != "$(cd "$R" && pwd -P)" ] && [ "$(mname "$R")" = "$NAME" ] && other_root=1
  for d in "$P"/gpt-skills/fz-*/; do
    [ -f "$d/SKILL.md" ] || continue
    role="$(basename "$d")"; role="${role#fz-}"; roles=$((roles + 1))
    got="$(cd "$T" && env -u FZ_PLUGIN_ROOT HOME="$H" python3 "$R/scripts/gpt_kinds.py" skill-path "$role")"
    want_sp="$H/.codex/skills/fz-$role/SKILL.md"
    [ "$other_root" = 1 ] && [ "$(readlink "$H/.codex/skills/fz-$role")" = "${d%/}" ] && [ -f "$R/gpt-skills/fz-$role/SKILL.md" ] \
      && want_sp="$R/gpt-skills/fz-$role/SKILL.md"
    [ "$got" = "$want_sp" ] && [ -f "$got" ] && hit=$((hit + 1)) || miss="$miss $role"
  done
  [ "$roles" -gt 0 ] && [ "$hit" -eq "$roles" ] && ok "Tier 2a 디스커버리 $hit/$roles 역할" || no "Tier 2a 디스커버리 $hit/$roles — 미해석:$miss"
fi

# ⑥ 인자 없는 두 번의 실행 뒤에도 agents 폴더가 없다 — setup 은 스킬 폴더만 다룬다
[ -e "$H/.codex/agents" ] && no "인자 없이 agents 폴더가 생겼다" || ok "인자 없으면 agents 폴더를 건드리지 않는다"

# ⑦ retired-option-gpt-agents — 역할 파일 링크 opt-in 을 걷었다. 옛 옵션으로 부르면 조용히 받지 않는다:
#    모르는 옵션으로 exit 1 · 그 옵션 이름 · 스킬 폴더 그대로 · agents 폴더 없음(그 옵션을 아는 판은 링크를 걸고 exit 0 이라 이 셀이 실패한다)
before="$(snap)"
env -u CODEX_HOME HOME="$H" FZ_SKILL_TARGET="$TG" bash "$SETUP" --gpt-agents > "$T/out.retired" 2>&1; rcr=$?
after="$(snap)"
[ "$rcr" -eq 1 ] && grep -qF 'unknown option: --gpt-agents' "$T/out.retired" && [ "$before" = "$after" ] && [ ! -e "$H/.codex/agents" ] \
  && ok "retired-option-gpt-agents: 걷은 옵션 → exit 1 · 옵션 이름 · 스킬 폴더 그대로 · agents 폴더 없음" \
  || no "retired-option-gpt-agents: exit $rcr · $(tail -1 "$T/out.retired") · 스킬 폴더 $([ "$before" = "$after" ] && echo 그대로 || echo 바뀜) · agents 폴더 $([ -e "$H/.codex/agents" ] && echo 있음 || echo 없음)"

# ⑨ check-removed-role-skill — 이 판이 걷은 역할 스킬을 가리키는 옛 링크만 든 홈(위 셀들과 섞이지 않게 따로 둔다).
#    구버전 캐시가 아직 남아 링크가 살아 있는 fz-retired-live 와 이 루트에서 폴더가 사라져 끊긴 fz-retired-gone 둘 다 stale 이다.
#    살아 있는 쪽은 prune ③ 이 없는 판(걷은 스킬 판정 없음)에서 다른 판 링크로 보여 목록에 없고 지워지지도 않아 이 셀이 실패한다
MH="$T/migrate-home"; MT="$MH/skills"; mkdir -p "$MT" "$OLD/gpt-skills/fz-retired-live"
echo x > "$OLD/gpt-skills/fz-retired-live/SKILL.md"
ln -s "$OLD/gpt-skills/fz-retired-live" "$MT/fz-retired-live"   # 구버전 캐시 — 살아 있다
ln -s "$P/gpt-skills/fz-retired-gone" "$MT/fz-retired-gone"     # 이 루트 — 걷은 스킬이라 끊겼다
H0="$H" TG0="$TG"; H="$MH" TG="$MT"                             # run · runc 를 이 홈에 돌린다
runc m0; rcm0=$?; run m1; rcm1=$?; runc m2; rcm2=$?
H="$H0" TG="$TG0"
want_m="$(printf '%s\n' fz-retired-gone fz-retired-live | LC_ALL=C sort)"; got_m="$(stale_set "$T/out.m0")"
pruned_m="$(sed -n 's/^  prune: \([^ ]*\) .*/\1/p' "$T/out.m1" | LC_ALL=C sort)"; left_m="$(stale_set "$T/out.m2")"
[ "$rcm0" -eq "$STALE_EXIT" ] && [ "$got_m" = "$want_m" ] && [ "$rcm1" -eq 0 ] && [ "$pruned_m" = "$want_m" ] \
  && [ ! -L "$MT/fz-retired-live" ] && [ ! -L "$MT/fz-retired-gone" ] && [ "$rcm2" -eq 0 ] && [ -z "$left_m" ] \
  && ok "check-removed-role-skill: 걷은 역할 스킬 링크(구버전 캐시 · 끊긴 현 루트) --check exit $rcm0 · 목록 2 · 정리가 지우고 정리 뒤 0" \
  || no "check-removed-role-skill: --check exit $rcm0(기대 $STALE_EXIT) · 목록 [$(words "$got_m")] 기대 [$(words "$want_m")] · setup exit $rcm1 · 지운 목록 [$(words "$pruned_m")] · 정리 뒤 exit $rcm2 · 남은 목록 [$(words "$left_m")]"

echo
[ "$fail" -eq 0 ] && echo "setup-links: 전건 통과" || echo "setup-links: 실패 있음"
FIN=1
exit "$fail"
