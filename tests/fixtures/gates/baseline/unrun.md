# Gates: 기준선 미실행 — 도구 · 환경 부재
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] U1: 도구 부재
  CRITERION: 도구 부재
  CHECK: echo t
  EXPECT: never-t
  SIDE_EFFECTS: none
  TOOLS: fz-no-such-tool-xyz
  EVIDENCE: pending

- [ ] U2: 환경 부재
  CRITERION: 환경 부재
  CHECK: echo e
  EXPECT: never-e
  SIDE_EFFECTS: none
  ENV: FZ_BASELINE_SURELY_UNSET
  EVIDENCE: pending
