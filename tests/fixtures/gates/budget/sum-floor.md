# Gates: 예산 기본값 — TIMEOUT 합이 960 보다 작다
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 바닥 960

- [ ] G1: 빠른 게이트
  CHECK: echo ok
  EXPECT: ok
  TIMEOUT: 10
  EVIDENCE: pending
