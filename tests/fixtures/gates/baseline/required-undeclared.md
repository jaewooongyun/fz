# Gates: 기준선 요구 — 전부 미선언
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
BASELINE: required
- [ ] U1: 미선언 하나
  CRITERION: 미선언 하나
  CHECK: echo u1
  EXPECT: never-u1
  EVIDENCE: pending

- [ ] U2: 미선언 둘
  CRITERION: 미선언 둘
  CHECK: echo u2
  EXPECT: never-u2
  EVIDENCE: pending
