# Gates: 선언한 도구가 있으면 평소대로 판정한다
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: TOOLS 선언이 존재하는 도구를 가리키면 CHECK 가 그대로 돌아야 한다

- [ ] G1: 존재하는 도구를 선언한 게이트
  CHECK: printf hello
  EXPECT: hello
  TOOLS: git, python3
  EVIDENCE: pending
