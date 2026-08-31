# Gates: 승인 후 oracle 변조
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 문법은 유효하나 APPROVED_ORACLE_HASH 가 현재 oracle 과 어긋난다

- [x] G1: 원래는 빌드였는데 쉬운 명령으로 바뀌었다
  CHECK: echo trivially true
  EXPECT: trivially true
  APPROVED_ORACLE_HASH: 000000000000
  EVIDENCE: exit=0; shell=/bin/sh; output=BUILD SUCCEEDED
