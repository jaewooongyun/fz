# Gates: 선언한 도구가 없으면 미판정이다
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: CHECK 자체는 통과할 내용이다 — 그래서 차단이 사라지면 곧바로 PASS 로 뒤집힌다

- [ ] G1: 부재 도구를 선언한 게이트
  CHECK: printf hello
  EXPECT: hello
  TOOLS: fz-nonexistent-tool-xyz
  EVIDENCE: pending
