# Gates: 기준선 요구 — 선언 하나 · 미선언 하나
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
BASELINE: required
- [ ] D1: 선언한 게이트
  CRITERION: 선언한 게이트
  CHECK: echo d1
  EXPECT: never-d1
  SIDE_EFFECTS: none
  EVIDENCE: pending

- [ ] U1: 미선언 게이트
  CRITERION: 미선언 게이트
  CHECK: echo u1
  EXPECT: never-u1
  EVIDENCE: pending
