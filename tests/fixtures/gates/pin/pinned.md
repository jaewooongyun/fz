# Gates: 핀 — 기대 표를 승인에 묶는다
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 기대 표 핀 게이트
  CRITERION: 기대 표 핀 게이트
  CHECK: cat pin/table.txt
  EXPECT: row-ok
  PIN: pin/table.txt
  EVIDENCE: pending

- [ ] G2: 핀 없는 대조군
  CRITERION: 핀 없는 대조군
  CHECK: cat pin/table.txt
  EXPECT: row-ok
  EVIDENCE: pending
