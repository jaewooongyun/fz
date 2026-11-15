# Gates: 실패인데 토큰 있음
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: exit 1 인데 출력에 기대 토큰이 들어 있다

- [ ] G1: 토큰을 뱉고 실패
  CHECK: echo probe verification passed; exit 1
  EXPECT: probe verification passed
  EVIDENCE: pending
