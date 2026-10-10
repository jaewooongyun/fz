#!/usr/bin/env python3
# lint:no-root-anchor — 경로를 다루지 않는 순수 함수 모듈이다(형제 검사기가 import 한다).
"""md_section.py — 마크다운 절 추출 공용 함수 (F-335 ⑰).

왜: '제목을 찾고 다음 제목 전까지 자른다' 가 검사기마다 따로 있었다 — `NEXT_H` 는 세 파일에 글자 그대로
복사돼 있었고, 끝 패턴만 다른 두 벌이 더 있었다. 한 벌만 고치면 나머지가 조용히 옛 경계로 자른다.

소비자(import md_section): check_failure_table · check_host_census · check_k_cluster(기본 끝 `NEXT_H`) ·
check_ab_protocol(제목 포함 · 끝 `^##\\s`) · check_release_notes(끝 `^### v\\d`).
⛔ 모양이 다른 추출은 옮기지 않았다 — check_gpt_skill_portability 는 줄 목록 · 제목 색인을, extract_project_rules 는
여러 절 분할을, measure_constraint_load 는 절별 집계를 돌려준다(한 함수로 합치면 인자가 모양마다 자란다).

Python 3.9 stdlib 전용. 실행 진입점 없음 — 동작은 소비자 self-test 가 잰다.
"""
from __future__ import annotations

import re

# 다음 절 경계 기본값 — `#` ~ `###` 제목 줄(`####` 이하 소제목은 절 안에 둔다)
NEXT_H = re.compile(r"^#{1,3}\s", re.M)


def section(text: str, start: "re.Pattern[str]", end: "re.Pattern[str]" = NEXT_H, *, keep_heading: bool = False):
    """`start` 가 처음 맞은 곳 **뒤**부터 그 뒤에서 `end` 가 처음 맞는 곳 **앞**까지를 돌려준다. `start` 가 없으면 None.

    - Parameters: `start` · `end` 는 컴파일한 정규식이다(줄 머리 앵커면 `re.M`). `keep_heading=True` 면 `start` 가 맞은 글자를 앞에 붙인다.
    - Returns: 절 본문 문자열. `end` 가 없으면 문서 끝까지.
    - Important: `end` 는 `start` 가 맞은 끝 **이후**에서만 찾는다 — 제목 줄 자신이 `end` 에 걸려 빈 절이 되지 않게.
    """
    m = start.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = end.search(rest)
    body = rest[: nxt.start()] if nxt else rest
    return m.group(0) + body if keep_heading else body
