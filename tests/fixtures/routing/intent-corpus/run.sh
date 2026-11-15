#!/bin/bash
# 라우팅 합성 corpus 러너 (F-528) — cases.tsv 의 문장마다 반드시 걸릴 라벨 · 걸리면 안 될 라벨을 scripts/intent_route_probe.py 로 본다.
#   이어 하기 · Curate · 메타 묶음과 부분 문자열 함정(prompt 의 pr · PRD) · `코드` 단독 약화 · 파이프라인 전용(스킬 0) 대조가 들어 있다
# exit: 0 전건 통과 · 1 단언 실패 · 2 판정 불가(표 파싱 · 정규식 오류 · 케이스 0)
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$HERE/../../../.." && pwd)"
PYTHONDONTWRITEBYTECODE=1 python3 "$R/scripts/intent_route_probe.py" --root "$R" --cases "$HERE/cases.tsv"
