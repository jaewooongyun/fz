# Gates: 핀 — 미선언 변수
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 미선언 변수 핀
  CRITERION: 미선언 변수 핀
  CHECK: cat pin/table.txt
  EXPECT: row-ok
  PIN: ${FZ_NOT_DECLARED}/pin/table.txt
  EVIDENCE: pending
