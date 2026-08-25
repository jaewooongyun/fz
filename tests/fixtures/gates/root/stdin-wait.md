# Gates: stdin 대기
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: CHECK 가 stdin 을 읽으려 하면 즉시 끝나야 한다

- [ ] G1: stdin 을 읽는 CHECK
  CHECK: read -r line; echo "got:$line"
  EXPECT: never matches
  TIMEOUT: 5
  EVIDENCE: pending
