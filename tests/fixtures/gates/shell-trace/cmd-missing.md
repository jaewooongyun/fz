# Gates: 셸 오류 흔적 — 미선언 도구 부재
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: TOOLS 미선언 도구가 없어 카운터 0 으로 거짓 통과 (F-409)

- [ ] G1: 없는 도구의 결과를 0 으로 센다
  CHECK: fz_absent_tool_q9 --count x; echo count 0 ok
  EXPECT: count 0 ok
  EVIDENCE: pending
