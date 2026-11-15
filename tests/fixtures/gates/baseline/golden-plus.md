# Gates: 구판 골든 + SIDE_EFFECTS 선언 게이트
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

- [ ] G2: 선언 게이트
  CRITERION: 선언 게이트
  CHECK: echo g2
  EXPECT: g2
  SIDE_EFFECTS: none
  EVIDENCE: pending
