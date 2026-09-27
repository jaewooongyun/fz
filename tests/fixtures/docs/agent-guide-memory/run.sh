#!/bin/bash
# 회귀 오라클 — health-check 가 tests/fixtures/*/*/run.sh 로 자동 실행한다 (S02 문서 계약)
D="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
python3 "$D/tests/docs/check_agent_guide_memory.py" --self-test && python3 "$D/tests/docs/check_agent_guide_memory.py" "$D/guides/agent-team-guide.md"
