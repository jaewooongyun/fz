# Gates: 기준선 프로브 — 선언별 실행 여부
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] B1: 구현 전 실패
  CRITERION: 구현 전 실패
  CHECK: echo not-yet
  EXPECT: implemented
  SIDE_EFFECTS: none
  EVIDENCE: pending

- [ ] B2: 구현 전 통과
  CRITERION: 구현 전 통과
  CHECK: echo already-there
  EXPECT: already-there
  SIDE_EFFECTS: none
  EVIDENCE: pending

- [ ] B3: 파일을 쓰는 게이트
  CRITERION: 파일을 쓰는 게이트
  CHECK: touch /srv/fz-plugin/tests/fixtures/gates/sentinel-writes && echo w
  EXPECT: w
  SIDE_EFFECTS: writes — sentinel 파일을 쓴다
  EVIDENCE: pending

- [ ] B4: 선언 없는 게이트
  CRITERION: 선언 없는 게이트
  CHECK: touch /srv/fz-plugin/tests/fixtures/gates/sentinel-undeclared && echo u
  EXPECT: u
  EVIDENCE: pending

- [ ] B5: 임시 파일만 쓰는 게이트
  CRITERION: 임시 파일만 쓰는 게이트
  CHECK: T="$(mktemp)" && rm -f "$T" && touch /srv/fz-plugin/tests/fixtures/gates/sentinel-tmp-ran && echo tmp-ran
  EXPECT: never-tmp
  SIDE_EFFECTS: tmp
  EVIDENCE: pending

- [ ] M1: 수동 확인
  MANUAL: 기준선 프로브가 돌리지 않는 수동 확인
  CRITERION_HASH: 55c76d79df16
  EVIDENCE: pending
