# Gates: 핀 — traversal
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 상위 경로 핀
  CRITERION: 상위 경로 핀
  CHECK: cat pin/table.txt
  EXPECT: row-ok
  PIN: ../outside.txt
  EVIDENCE: pending
