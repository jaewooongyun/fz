# A/B 원장 통합 fixture (S05)

`scripts/ab_ledger.py` 를 **collect → score → judge** 로 끝까지 돌려 예상 판정과 대조한다(`tests/ab/integration.py`).

- run 8개: 유효 기준선 B1·B2 · 무효 기준선 B3(effort)·B4(미완주)·B5(시작 상태 누수)·B6(입력 해시) · smoke S1(R-A)·S2(R-Z)
- transcript 는 실측 형식을 흉내 낸 **합성**이다 — 형식이 바뀌면 이 테스트가 먼저 깨져야 한다
- 경로는 자리표시자(`@FIX@` 등)이며 러너가 임시 폴더에서 치환한다. 생성기는 플러그인 밖에 둔다

## 오라클 경계 (F-582)

계측기 계약(실패 닫힘 · 계측기 정체 · 수집 충실도 · 원천 형식 · 명령 판정 · GPT 첫 판 행 · 코퍼스 동결)은 모든 원천 꼴을 말하지만,
이 fixture 와 결함 주입(`tests/ab/faults.py`)은 fixture 가 실제로 가진 원천 · 키 경로만 변이시킨다. fixture 에 없는 꼴(외부 MCP 결과 ·
plan-lean2 폴더 · arm 홈 rollout · 규칙 fixture 행 · function_call)과 명령 본문 변형 · 같은 형 값 바꾸기는 적대 검토가 찾은 반례마다
처분 셀(`r3-s14-r4-*`)로만 덮는다 — 그 밖의 같은 꼴은 열거되지 않았다.
