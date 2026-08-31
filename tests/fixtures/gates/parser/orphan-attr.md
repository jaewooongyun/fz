# Gates: 게이트 밖 속성
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 게이트 줄이 빠져 속성만 떠 있다

  CHECK: echo 아무_게이트에도_속하지_않는다
  EXPECT: never

- [ ] G1: 진짜 게이트
  CHECK: echo ok
  EXPECT: ok
  EVIDENCE: pending
