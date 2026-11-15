# Gates: 타임아웃
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: deadline 을 넘긴다

- [ ] G1: 오래 잔다
  CHECK: sleep 30; echo ok
  EXPECT: ok
  TIMEOUT: 2
  EVIDENCE: pending
