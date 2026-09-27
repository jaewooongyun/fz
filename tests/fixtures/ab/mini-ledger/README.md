# A/B 원장 통합 fixture (S05)

`scripts/ab_ledger.py` 를 **collect → score → judge** 로 끝까지 돌려 예상 판정과 대조한다(`tests/ab/integration.py`).

- run 8개: 유효 기준선 B1·B2 · 무효 기준선 B3(effort)·B4(미완주)·B5(시작 상태 누수)·B6(입력 해시) · smoke S1(R-A)·S2(R-Z)
- transcript 는 실측 형식을 흉내 낸 **합성**이다 — 형식이 바뀌면 이 테스트가 먼저 깨져야 한다
- 경로는 자리표시자(`@FIX@` 등)이며 러너가 임시 폴더에서 치환한다. 생성기는 플러그인 밖에 둔다
