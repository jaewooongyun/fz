# Gates: 핀 — 디렉토리
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 디렉토리 핀
  CRITERION: 디렉토리 핀
  CHECK: cat pin/table.txt
  EXPECT: row-ok
  PIN: pin
  EVIDENCE: pending
