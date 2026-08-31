# Gates: EVIDENCE 라인 부재
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: EVIDENCE 라인이 없는 게이트를 통과시켰을 때 삽입되는가

- [ ] G1: 통과할 게이트 (EVIDENCE 없음)
  CHECK: echo evidence probe ok
  EXPECT: evidence probe ok

- [ ] G2: 형제 블록 (침범 금지 확인)
  MANUAL: 사람 확인
  CRITERION_HASH: 07d179004054
