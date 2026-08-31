# Gates: 부분 도장
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
APPROVED: yes
Scope: 확정본인데 한 게이트만 도장이 있다

- [ ] G1: 도장 있음
  CHECK: echo ok
  EXPECT: ok
  APPROVED_ORACLE_HASH: 000000000000
  EVIDENCE: pending

- [ ] G2: 도장 없음
  CHECK: echo ok
  EXPECT: ok
  EVIDENCE: pending
