# Gates: 승인·미착수
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 계획만 승인하고 구현은 시작하지 않은 원장 — planned 전이표(F-190)

- [ ] G1: 첫 구현
  CRITERION: 첫 구현 게이트가 통과한다
  CHECK: echo planned g1 ok
  EXPECT: planned g1 ok
  EVIDENCE: pending

- [ ] G2: 둘째 구현
  CRITERION: 둘째 구현은 아직 없다
  CHECK: echo planned g2 missing && false
  EXPECT: planned g2 ok
  EVIDENCE: pending

- [ ] G3: 사람 확인
  MANUAL: 화면을 눈으로 확인
  CRITERION_HASH: eea190179d02
  EVIDENCE: pending
