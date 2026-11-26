# Gates: 기준선 미실행 — 도구 · 환경 부재
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] U1: 도구 부재
  CRITERION: 도구 부재
  CHECK: echo t
  EXPECT: never-t
  SIDE_EFFECTS: none
  TOOLS: fz-no-such-tool-xyz
  EVIDENCE: pending

- [ ] U2: 환경 부재
  CRITERION: 환경 부재
  CHECK: echo e
  EXPECT: never-e
  SIDE_EFFECTS: none
  ENV: FZ_BASELINE_SURELY_UNSET
  EVIDENCE: pending

- [ ] U3: 명령이 깨진 CHECK — 실패가 RED 증명이 아니다(F-656)
  CRITERION: 명령 부재로 실패한다
  CHECK: fz-no-such-cmd-xyz --version
  EXPECT: never-u3
  SIDE_EFFECTS: none
  EVIDENCE: pending

- [ ] U4: ENV 를 선언하지 않은 변수 미설정 — 실패가 RED 증명이 아니다(F-656)
  CRITERION: 변수가 없어 셸이 멈춘다
  CHECK: echo "${FZ_BASELINE_U4_SURELY_UNSET:?}"
  EXPECT: never-u4
  SIDE_EFFECTS: none
  EVIDENCE: pending
