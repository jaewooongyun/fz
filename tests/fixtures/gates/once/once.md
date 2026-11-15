# Gates: 1회성 게이트
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: ONCE 게이트는 충족 뒤 --reverify 가 다시 돌리지 않는다 (F-235)

- [ ] G1: 동결 기준선을 쓴다
  CHECK: echo once ok
  EXPECT: once ok
  ONCE: 동결 기준선 쓰기 — 다시 돌리면 덮어쓴다
  EVIDENCE: pending
