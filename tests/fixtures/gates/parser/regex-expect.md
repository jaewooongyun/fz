# Gates: 정규식 기대값
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 지원하지 않는 정규식 문법

- [ ] G1: 정규식으로 매칭 시도
  CHECK: echo hello
  EXPECT: /he(l+)o/i
  EVIDENCE: pending
