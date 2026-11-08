# Gates: 핀 — 승인 때 부재
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 아직 없는 표 핀
  CRITERION: 아직 없는 표 핀
  CHECK: echo ok
  EXPECT: ok
  PIN: pin/later.txt
  EVIDENCE: pending
