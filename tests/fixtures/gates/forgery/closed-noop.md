# Gates: closed 원장
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: closed
Scope: 닫힌 원장은 실행되지 않는다

- [ ] G1: 실행 금지
  CHECK: echo SHOULD_NOT_RUN
  EXPECT: SHOULD_NOT_RUN
  EVIDENCE: pending
