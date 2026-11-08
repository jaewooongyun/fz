# Gates: 핀 — ENV 선언 루트 변수
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] G1: 변수 루트 핀
  CRITERION: 변수 루트 핀
  CHECK: cat pin/table.txt
  EXPECT: row-ok
  ENV: FZ_PIN_FIXTURE_ROOT
  PIN: ${FZ_PIN_FIXTURE_ROOT}/pin/table.txt
  EVIDENCE: pending
