#!/bin/bash
# scripts/check_release_sync.sh — 릴리즈 산출물이 서로를 가리키는지 본다 (plan-final S10).
#
# ⛔ 왜 신설인가: `health-check.sh` 는 계약·문법·회귀를 보지만 **이번 변경의 문서 동기와 버전
#    갱신은 증명하지 않는다**(verify-gates S10 revise 지적). 버전이 세 곳에 흩어져 있어
#    한 곳만 올리는 실패가 실제로 있었다(v4.33.0 CHANGELOG "적용은 했는데 커밋하지 않았다").
#
# 검사: ① plugin.json == marketplace.json ② CHANGELOG 최상단 == plugin.json
#       ③ 가이드가 sweep 기록 위치(§5.8 ⑥)를 가리키는가 ④ health-check exit 0
# exit: 0=전부 충족(DOCS_SYNC_OK) / 1=불일치 / 2=대상 부재(측정 실패)
set -uo pipefail
#   루트는 **자기 위치**에서 해석한다 (`BASH_SOURCE[0]` — `$0` 는 source 시 호출자를 가리킨다)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SELF_DIR/.." && pwd)"
cd "$ROOT_DIR" || { echo "❌ 플러그인 루트로 이동 실패: $ROOT_DIR"; exit 2; }

fail=0
note() { echo "  ❌ $1"; fail=$((fail + 1)); }

for f in .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md \
         guides/skill-authoring.md guides/model-guide.md scripts/health-check.sh; do
  [ -f "$f" ] || { echo "❌ 대상 부재: $f (측정 실패)"; exit 2; }
done

PV=$(python3 -c 'import json;print(json.load(open(".claude-plugin/plugin.json"))["version"])' 2>/dev/null)
MV=$(python3 -c 'import json,sys;d=json.load(open(".claude-plugin/marketplace.json"));p=d["plugins"][0] if isinstance(d.get("plugins"),list) and d["plugins"] else d;print(p.get("version",""))' 2>/dev/null)
CV=$(grep -m1 -oE '^### v[0-9]+\.[0-9]+\.[0-9]+' CHANGELOG.md | sed 's/^### v//')
[ -n "$PV" ] || { echo "❌ plugin.json version 을 읽지 못했다 (측정 실패)"; exit 2; }
[ -n "$CV" ] || { echo "❌ CHANGELOG 최상단 버전 헤딩을 찾지 못했다 (측정 실패)"; exit 2; }

echo "버전: plugin=$PV · marketplace=$MV · CHANGELOG=$CV"
[ "$PV" = "$MV" ] || note "plugin.json($PV) ≠ marketplace.json($MV)"
[ "$PV" = "$CV" ] || note "plugin.json($PV) ≠ CHANGELOG 최상단($CV) — 항목 없이 버전만 올리거나 그 반대"

# ③ sweep 결과가 어디로 가는지 가이드가 가리키는가 — 사전등록만 하고 참조가 없으면 표가 미아가 된다
grep -q '§5.8 ⑥' guides/skill-authoring.md || note "skill-authoring.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '§5.8 ⑥' guides/model-guide.md || note "model-guide.md 가 sweep 기록 위치(§5.8 ⑥)를 가리키지 않는다"
grep -q '### ⑥ 세션 effort sweep' experiment-log.md || note "experiment-log.md 에 §5.8 ⑥ 표가 없다 (가이드가 없는 곳을 가리킨다)"
grep -q '## §5.9 구조 ablation' experiment-log.md || note "experiment-log.md 에 §5.9 표가 없다"

# ④ health-check — 이번 변경이 기존 계약을 깨지 않았는가
if bash scripts/health-check.sh >/tmp/fz-release-hc.log 2>&1; then
  echo "  ✅ health-check exit 0"
else
  note "health-check 실패 (로그: /tmp/fz-release-hc.log)"
fi

if [ "$fail" -gt 0 ]; then
  echo "릴리즈 동기 불일치 ${fail}건"
  exit 1
fi
echo "DOCS_SYNC_OK (버전 3곳 일치 · 가이드→표 참조 4건 · health-check exit 0)"
