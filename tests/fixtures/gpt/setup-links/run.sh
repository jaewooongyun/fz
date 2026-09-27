#!/bin/bash
# setup-gpt-skills.sh 링크 계약 러너 (A2-02).
#
# 판정: ① GPT 스킬(SKILL.md 가진 gpt-skills/ 전부)이 현 판으로 링크된다 ② 이 플러그인 skills/ 를 가리키는
#       링크가 0 이다(구버전 캐시·이름 무관 포함) ③ 다른 플러그인 링크·실제 디렉토리는 보존된다
#       ④ 재실행은 멱등이다 ⑤ Tier 2a 디스커버리(get_gpt_skill_path)가 역할 전부를 이 폴더에서 해석한다
# ⛔ 실제 사용자 폴더를 건드리지 않는다 — HOME·FZ_SKILL_TARGET 은 임시 폴더, CODEX_HOME 은 비운다.
# ⛔ FZ_SETUP_UNDER_TEST 로 다른 판(기준 트리)의 스크립트를 같은 러너로 돌린다 — 판별력 대조용.
#    이때 기대값은 **그 스크립트의** 플러그인 루트 기준이다.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SETUP="${FZ_SETUP_UNDER_TEST:-$R/scripts/setup-gpt-skills.sh}"
P="$(cd "$(dirname "$SETUP")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
H="$T/home"; TG="$H/.codex/skills"; mkdir -p "$TG"
mname() { python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1], encoding="utf-8")).get("name", ""))
except Exception: pass' "$1/.claude-plugin/plugin.json" 2>/dev/null; }
NAME="$(mname "$P")"
[ -n "$NAME" ] || { echo "FAIL  플러그인 이름을 읽지 못했다 — $P"; exit 1; }

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

before="$(snap)"; run 2; after="$(snap)"
[ "$before" = "$after" ] && ok "재실행 멱등" || no "재실행이 상태를 바꿨다"

# ⑤ Tier 2a — 정본 함수를 modules/cross-validation.md 에서 떼어 실행한다(복사본 아님)
FN="$(awk '/^get_gpt_skill_path\(\) \{/{f=1} f{print} f&&/^\}$/{exit}' "$R/modules/cross-validation.md")"
if [ -z "$FN" ]; then
  no "get_gpt_skill_path 정의를 찾지 못했다 — 문서에서 지워졌거나 형식이 바뀌었다"
else
  roles=0 hit=0 miss=""
  for d in "$P"/gpt-skills/fz-*/; do
    [ -f "$d/SKILL.md" ] || continue
    role="$(basename "$d")"; role="${role#fz-}"; roles=$((roles + 1))
    got="$(cd "$T" && env -u FZ_PLUGIN_ROOT HOME="$H" bash -c "$FN"$'\n''get_gpt_skill_path "$1"' _ "$role")"
    [ "$got" = "$H/.codex/skills/fz-$role/SKILL.md" ] && [ -f "$got" ] && hit=$((hit + 1)) || miss="$miss $role"
  done
  [ "$roles" -gt 0 ] && [ "$hit" -eq "$roles" ] && ok "Tier 2a 디스커버리 $hit/$roles 역할" || no "Tier 2a 디스커버리 $hit/$roles — 미해석:$miss"
fi

echo
[ "$fail" -eq 0 ] && echo "setup-links: 전건 통과" || echo "setup-links: 실패 있음"
exit "$fail"
