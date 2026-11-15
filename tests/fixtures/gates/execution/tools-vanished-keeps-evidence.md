# Gates: 통과했던 게이트의 도구가 사라져도 증거를 지우지 않는다
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 벌어둔 증거가 있는 상태에서 도구만 사라진다 — 지워질 것이 있어야 "안 지운다"가 주장이 된다

- [x] G1: 예전에 통과한 게이트
  CHECK: printf hello
  EXPECT: hello
  TOOLS: fz-nonexistent-tool-xyz
  EVIDENCE: sig=deadbeefcafe; exit=0; cwd=/Users/example/dev/fz-plugin/tests/fixtures/gates; env=0123456789ab; output=hello
