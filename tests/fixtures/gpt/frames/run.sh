#!/bin/bash
# frames 러너 — 실험 frame · 런처 정책의 resolver 이관(R-06 · SC-2) · 독립 kind 명시 입력(D6). 가짜 CLI 로만 돈다(실 CLI · 네트워크 없음).
# 셀 정의와 판정은 같은 폴더 cells.py(kinds-resolve 의 캡처 장치를 재사용 — 기본 프롬프트를 게이트 argv golden 과 같은 정규화로 대조한다).
# exit: 0 전건 통과 · 1 셀 FAIL · 3 준비 실패
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || { echo "SETUP 러너 위치를 풀지 못했다"; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "SETUP python3 없음"; exit 3; }
python3 "$HERE/cells.py"
