#!/bin/bash
# merge-n 러너 — scripts/gpt_merge.py 를 CLI 로 본다(N 개 GPT 실행의 병합 · 다중집합 보존 · 거부 · blind 왕복 · review_merge 유입 차단). 셀은 cells.py
# exit: 0 전건 통과 · 1 셀 FAIL · 3 준비 실패
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || { echo "SETUP 러너 위치를 풀지 못했다"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 없음"; exit 3; }
python3 "$HERE/cells.py"
