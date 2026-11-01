#!/bin/bash
# 스테이지 분류 fixture (F-462) — fz_telemetry_report.py 가 journal result 를 started 줄 라벨 줄기 → 형제
# agent-<id>.meta.json agentType → 키 서명 순으로 가르고, 못 가른 형태를 other 가 아니라 unknown 으로 보고하는지,
# 교차(review-live verdict · peer-review delta)와 counter 판정을 additions 와 따로 세는지 동작으로 본다.
#
# 이 폴더의 projects/(합성 journal 3 실행 · result 6 · meta.json)를 임시 폴더에 복사하고 journal mtime 을 기간 안으로
# 고정한 뒤 리포트를 --json --out 으로 렌더한다(없는 findings · 없는 plugin-root · 임시 telemetry-dir). 판정은 check.py.
#   stages                stage1-arch · stage2-quality-on-arch · stage2-arch-on-peers · stage3-counter ·
#                         lean2-merge:8811b9(agentType 기본값 — 라벨 줄기만으로) · 라벨 없는 형태
#                         → lens 1 · cross 2 · counter 1 · plan-merge 1 · unknown 1
#   review-live-verdicts  stage2-quality-on-arch adjustments[].verdict → agree 2 · adjust 1 · false_positive 1
#   peer-delta-verdicts   stage2-arch-on-peers reviewedIds 5 중 판정 안 된 id 3 → agree 3 · adjust 1 · false_positive 1
#   counter-verdicts      stage3-counter challenges[].verdict → uphold 2 · refute 1
#   additions             additions · missedFindings 는 판정 칸 밖 additions 로(교차 1 · counter 2 · peer 3)
#   unknown-shape         라벨 없는 미매치 result → unknown 이고 unknown_result_shapes 에 그 키 집합 하나만
#   label-drift           리포트 LABEL_STAGE 의 라벨이 전부 $ROOT/workflows/*.js 에 `label: '<라벨>'` 로 있는지 — 라벨을
#                         바꾸면 그 결과가 unknown 이 아니라 키 서명 스테이지로 조용히 빠지기 때문이다
# exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(`UNRUN:` — python3 부재 · 리포트 실패 · JSON 읽기 실패 · fixture 미검출 ·
#       workflows/*.js 못 읽음)
# ⛔ 실제 projects · findings · 텔레메트리 경로는 읽지 않는다. 저장소의 fixture 파일은 건드리지 않는다(mtime 은 사본에만).
set -u
ROOT=$(cd "$(dirname "$0")/../../../.." && pwd)
HERE="$ROOT/tests/fixtures/telemetry/stage-class"
command -v python3 >/dev/null 2>&1 || { echo "UNRUN: python3 부재"; exit 2; }
[ -f "$ROOT/scripts/fz_telemetry_report.py" ] || { echo "UNRUN: fz_telemetry_report.py 없음: $ROOT"; exit 2; }
[ -d "$HERE/projects" ] || { echo "UNRUN: fixture projects 없음: $HERE/projects"; exit 2; }
TMP=$(mktemp -d) || { echo "UNRUN: mktemp 실패"; exit 2; }
trap 'rm -rf "$TMP"' EXIT
cp -R "$HERE/projects" "$TMP/projects" || { echo "UNRUN: fixture 복사 실패"; exit 2; }
find "$TMP/projects" -name journal.jsonl -exec touch -t 202610150000 {} + || { echo "UNRUN: journal mtime 고정 실패"; exit 2; }
OUT="$TMP/report.json"
LOG=$(PYTHONDONTWRITEBYTECODE=1 python3 -B "$ROOT/scripts/fz_telemetry_report.py" \
  --projects-root "$TMP/projects" --since 2026-10-01 --until 2026-10-31 --json --out "$OUT" \
  --findings-dir "$TMP/no-findings" --plugin-root "$TMP/no-plugin" --telemetry-dir "$TMP/telemetry" 2>&1 </dev/null)
RC=$?
if [ "$RC" -ne 0 ] || [ ! -s "$OUT" ]; then
  echo "UNRUN: 리포트 실행 실패 rc=$RC"
  printf '%s\n' "$LOG" | tail -20
  exit 2
fi
PYTHONDONTWRITEBYTECODE=1 python3 -B "$HERE/check.py" "$OUT" "$ROOT"
exit $?
