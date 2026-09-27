# Gates: 확정 원장 보강 — 새 게이트만 도장
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: draft 를 확정한 뒤 게이트를 더해 그 게이트만 도장 찍는다

- [ ] G1: 첫째
  CRITERION: G1 이 통과한다
  CHECK: echo g1 ok
  EXPECT: g1 ok
  EVIDENCE: pending

- [ ] G2: 둘째
  CRITERION: G2 가 통과한다
  CHECK: echo g2 ok
  EXPECT: g2 ok
  EVIDENCE: pending
