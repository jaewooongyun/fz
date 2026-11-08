# Gates: 기준선 요구 원장 — 헤더 값 앞 공백 두 칸(파서는 strip 해 required 로 읽는다)
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
BASELINE:  required
- [ ] R1: 구현 전 실패
  CRITERION: 구현 전 실패
  CHECK: echo not-yet
  EXPECT: implemented
  SIDE_EFFECTS: none
  EVIDENCE: pending

- [ ] R2: 파일을 쓰는 게이트
  CRITERION: 파일을 쓰는 게이트
  CHECK: touch /srv/fz-plugin/tests/fixtures/gates/sentinel-r2 && echo w
  EXPECT: w
  SIDE_EFFECTS: writes — 원장 밖 파일을 쓴다
  EVIDENCE: pending

- [ ] M1: 수동 확인
  MANUAL: 기준선 프로브가 돌리지 않는 수동 확인
  CRITERION_HASH: 55c76d79df16
  EVIDENCE: pending
