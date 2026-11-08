# Gates: 기준선 요구 — 무변경 PASS
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
BASELINE: required
- [ ] P1: 구현 전 통과
  CRITERION: 구현 전 통과
  CHECK: echo already-there
  EXPECT: already-there
  SIDE_EFFECTS: none
  EVIDENCE: pending
