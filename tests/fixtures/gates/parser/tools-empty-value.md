# Gates: 빈 TOOLS 선언
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 선언만 있고 값이 없다
  CHECK: printf hello
  EXPECT: hello
  TOOLS:
  EVIDENCE: pending
