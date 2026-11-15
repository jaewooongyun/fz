#!/bin/bash
# 회귀 오라클 — health-check 가 tests/fixtures/*/*/run.sh 로 자동 실행한다 (S30 문서 계약 — Workflow 먼저 기동)
# ⛔ 루트는 이 파일 위치에서 푼다 — env 를 읽지 않는다(트리 사본에 결함을 심었을 때 사본을 검사해야 한다)
D="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
python3 "$D/tests/docs/check_workflow_first.py" --self-test && python3 "$D/tests/docs/check_workflow_first.py" "$D/skills/fz-review/SKILL.md" "$D/skills/fz-plan/SKILL.md"
