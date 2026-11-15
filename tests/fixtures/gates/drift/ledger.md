# Gates: 기준 문장 어긋남
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 리뷰가 고친 옛 오라클 문구가 CRITERION 에 남았다 (F-568)

- [ ] G1: 옛 문구가 남은 게이트
  CRITERION: 옛 오라클 — 줄 수를 센다
  CHECK: echo g1 ok
  EXPECT: g1 ok
  EVIDENCE: pending

- [ ] G2: 고친 문구의 게이트
  CRITERION: 새 기준 — 셀 통과 줄을 센다
  CHECK: echo g2 ok
  EXPECT: g2 ok
  EVIDENCE: pending
