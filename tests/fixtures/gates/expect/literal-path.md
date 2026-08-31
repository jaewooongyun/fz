# Gates: 경로 리터럴 EXPECT
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: /tmp/result 같은 절대경로 문자열을 기대하는 정당한 게이트

- [ ] G1: 산출물 경로를 출력한다
  CHECK: echo "wrote /tmp/result"
  EXPECT: /tmp/result
  EVIDENCE: pending
