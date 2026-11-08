# Gates: 구판 골든 — 1ed8415 판정기가 계산한 도장 · 서명
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
APPROVED: yes
- [x] G1: 구판 골든 게이트
  CRITERION: 구판 판정기가 찍은 도장과 서명이 신판에서도 유효하다
  CHECK: echo GOLDEN_OK
  EXPECT: GOLDEN_OK
  CWD: /
  TIMEOUT: 30
  ENV: HOME
  APPROVED_ORACLE_HASH: a5f3c2e9f6f5
  EVIDENCE: sig=e270624cffb0; exit=0; cwd=/; env=0123456789ab; output=GOLDEN_OK
