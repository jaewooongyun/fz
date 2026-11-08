# Gates: 기준선 소요가 TIMEOUT 절반을 넘는다
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] S1: 느린 게이트
  CRITERION: 느린 게이트
  CHECK: sleep 1.2; echo slow
  EXPECT: never-slow
  SIDE_EFFECTS: none
  TIMEOUT: 2
  EVIDENCE: pending
