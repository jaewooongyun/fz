#!/bin/bash
# 리뷰 배선 순서 러너 (S22) — `--gpt-independent` 경로에서 GPT 독립 첫 패스 기동이 Workflow 호출보다 **앞**, 병합이 **뒤**다.
#
# ⛔ 문서 순서 오라클이다 — 실행을 대신하지 않는다(두 패스가 실제로 동시에 도는지는 S25 가 잰다).
# ⛔ 기본 off 도 본다 — 옵션을 켜지 않은 경로(fz-review `/fz-gpt review` · peer-review Tier 1 challenger)가 그대로 남아 있어야 한다.
set -u
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
fail=0
ok() { echo "PASS  $1"; }
no() { echo "FAIL  $1"; fail=1; }
first() { /usr/bin/grep -nF -- "$2" "$R/$1" 2>/dev/null | head -1 | cut -d: -f1; }   # 첫 등장 줄 — 없으면 빈 값
order() {   # 파일 · 기동 토큰 · Workflow 토큰 · 병합 토큰
  local a b c; a="$(first "$1" "$2")"; b="$(first "$1" "$3")"; c="$(first "$1" "$4")"
  if [ -n "$a" ] && [ -n "$b" ] && [ -n "$c" ] && [ "$a" -lt "$b" ] && [ "$b" -lt "$c" ]; then
    ok "$1: 기동($a) < Workflow($b) < 병합($c)"
  else
    no "$1: 순서가 틀렸거나 토큰이 없다 — 기동 '${a:-없음}' · Workflow '${b:-없음}' · 병합 '${c:-없음}'"
  fi
}
has() { /usr/bin/grep -qF -- "$2" "$R/$1" 2>/dev/null && ok "$1: $3" || no "$1: $3 — '$2' 없음"; }

order skills/fz-review/SKILL.md 'gpt_independent.sh review' "Workflow({ scriptPath: '{플러그인 루트}/workflows/review-live.js'" 'review_merge.py'
order modules/peer-review-workflow.md 'gpt_independent.sh review' "Workflow({ scriptPath: '{플러그인 루트}/workflows/peer-review.js'" 'review_merge.py'

# 기본 off — 옵션을 켜지 않은 경로가 그대로다
has skills/fz-review/SKILL.md '/fz-gpt review "코드 리뷰"' '기본 경로의 GPT 리뷰 호출이 남아 있다'
has modules/peer-review-tiers.md 'gpt-challenger-raw.txt' 'Tier 1 기본 challenger 호출이 남아 있다'

# 권한 — 런처 · 래퍼 · 병합을 부를 수 있고, Will Not(GPT CLI 직접 호출 금지)과 모순되는 권한이 없다
for f in skills/fz-review/SKILL.md skills/fz-peer-review/SKILL.md; do
  has "$f" 'Bash(*/scripts/gpt_independent.sh*)' '런처 Bash 권한'
  has "$f" 'Bash(*/scripts/gpt-exec.sh*)' '래퍼 Bash 권한'
  has "$f" 'Bash(python3 */scripts/*)' '병합 스크립트 Bash 권한'
done
if /usr/bin/grep -qF 'Bash(codex *)' "$R/skills/fz-peer-review/SKILL.md"; then
  no "skills/fz-peer-review/SKILL.md: GPT CLI 직접 권한이 남아 있다(Will Not 과 모순)"
else
  ok "skills/fz-peer-review/SKILL.md: GPT CLI 직접 권한 없음"
fi

# 정본 절 — Tier 3 DA 는 두 패스 뒤 · 두 스킬과 Tier 표가 같은 절을 가리킨다
has modules/fz-gpt-subcommands-aux.md 'Tier 3 GPT DA 는 병합 뒤 한 번이다' 'Tier 3 DA 는 병합 뒤'
for f in skills/fz-review/SKILL.md skills/fz-peer-review/SKILL.md modules/peer-review-tiers.md modules/peer-review-workflow.md; do
  has "$f" '§ review — Lead 순서' '순서 정본 절을 가리킨다'
done

echo
[ "$fail" = 0 ] && echo "review-wiring order: 전건 통과" || echo "review-wiring order: 실패"
exit "$fail"
