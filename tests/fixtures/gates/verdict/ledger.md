# Gates: 판정 대조 대상
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 게이트 3개 — 응답이 전수 판정했는지 본다

- [ ] G1: 첫째
  CHECK: true
  EXPECT: ok
  EVIDENCE: pending

- [ ] G2: 둘째
  CHECK: true
  EXPECT: ok
  EVIDENCE: pending

- [ ] G3: 셋째
  MANUAL: 사람이 확인
  CRITERION_HASH: 4760c4040566
  EVIDENCE: pending
