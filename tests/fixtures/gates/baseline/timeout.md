# Gates: 기준선에서 TIMEOUT 을 넘는다 — 판정 불가(UNRUN)이지 '변경 전 실패'(FAIL)가 아니다
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] S1: 끝나지 않는 게이트
  CRITERION: 끝나지 않는 게이트
  CHECK: sleep 4; echo done
  EXPECT: done
  SIDE_EFFECTS: none
  TIMEOUT: 1
  EVIDENCE: pending
