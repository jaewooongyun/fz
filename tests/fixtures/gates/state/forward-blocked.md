# Gates: 전진 차단
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 실행 게이트는 통과했으나 MANUAL 이 미확인이다

- [x] G1: 실행 게이트 통과
  CHECK: echo state probe passed
  EXPECT: state probe passed
  EVIDENCE: exit=0; shell=/bin/sh; output=state probe passed

- [ ] G2: 사람 확인 필요
  MANUAL: 눈으로 확인
  CRITERION_HASH: bbb3e2992754
  EVIDENCE: pending
