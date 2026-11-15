# Gates: 발견 규약 밖 이름
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: gates/ 아래 plan.md 가 아닌 원장 — Stop 훅이 찾지 못한다 (F-384)

- [ ] G1: 아직 판정하지 않은 게이트
  CHECK: echo name probe
  EXPECT: name probe
  EVIDENCE: pending
