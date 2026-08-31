# Gates: 출력 상한 초과
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 앞부분에 실패 진단이 있고 뒤로 대량 출력이 이어진다

- [ ] G1: 앞에 진단 후 대량 출력
  CHECK: echo FIRST_FAILURE_MARKER; python3 -c "print('x'*2000000)"
  EXPECT: never matches this
  EVIDENCE: pending
