# Gates: 경계 합성으로 인한 조기 kill
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: stdout=he · stderr=llo 가 먼저 나오고 3초 뒤 진짜 hello 가 stderr 로 온다

- [ ] G1: 경계 조각 뒤에 진짜 출력이 온다
  CHECK: (printf he; printf llo >&2; sleep 3; printf hello >&2) & true
  EXPECT: hello
  TIMEOUT: 12
  EVIDENCE: pending
