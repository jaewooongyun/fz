#!/bin/bash
# 회귀 오라클 — health-check 가 tests/fixtures/*/*/run.sh 로 자동 실행한다
D="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$D/../../../ab/integration.py" --fixture "$D" --expect-verdicts "$D/expected.json"
