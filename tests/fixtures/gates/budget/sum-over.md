# Gates: 예산 기본값 — TIMEOUT 합이 960 을 넘는다
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: --budget 미지정 = max(TIMEOUT 합, 960)

- [ ] G1: 빠른 게이트 하나
  CHECK: echo ok
  EXPECT: ok
  TIMEOUT: 800
  EVIDENCE: pending

- [ ] G2: 빠른 게이트 둘
  CHECK: echo ok
  EXPECT: ok
  TIMEOUT: 800
  EVIDENCE: pending
