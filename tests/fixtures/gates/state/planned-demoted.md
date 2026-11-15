# Gates: 강등 기록이 남은 원장
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 통과했다가 재실행에서 떨어진 게이트가 있다 — 진행 기록(reverify 이력)이라 착수 전으로 못 간다

- [ ] G1: 첫 구현
  CRITERION: 첫 구현 게이트가 통과한다
  CHECK: echo planned g1 ok
  EXPECT: planned g1 ok
  EVIDENCE: pending; demoted

- [ ] G2: 둘째 구현
  CRITERION: 둘째 구현은 아직 없다
  CHECK: echo planned g2 missing && false
  EXPECT: planned g2 ok
  EVIDENCE: pending
