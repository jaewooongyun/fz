# Gates: DEFER — 뒤 릴리즈 게이트는 지금 판정하지 않는다
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
CURRENT_RELEASE: R-A
Scope: G1 은 이번 릴리즈, G2 는 R-B 로 미뤘다 — 지금 돌면 실패하는 CHECK 다

- [ ] G1: 이번 릴리즈 게이트
  CHECK: echo g1 ok
  EXPECT: g1 ok
  EVIDENCE: pending

- [ ] G2: 다음 릴리즈 게이트
  CHECK: echo not-yet
  EXPECT: shipped
  EVIDENCE: pending

DEFER: G2 R-B 다음 릴리즈에서 구현한다
