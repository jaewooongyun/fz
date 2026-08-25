# Gates: 플래그 붙은 정규식 EXPECT
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 정규식 의도가 분명한 형태는 거부한다

- [ ] G1: 판정 대상
  CHECK: echo hello
  EXPECT: /he(l+)o/i
  EVIDENCE: pending
