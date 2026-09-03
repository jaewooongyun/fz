# Gates: 확정 도장 위치
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 실행 8 + manual 1 (파일명의 eight 는 실행 게이트 수) — 도장 삽입이 뒤쪽 게이트의 스팬을 미는지 본다

- [ ] G1: 첫째 — CWD 를 가진 5속성 블록
  CRITERION: G1 이 자기 oracle 의 도장을 갖는다
  CHECK: echo g1 ok
  EXPECT: g1 ok
  CWD: /Users/example/dev/fz-plugin/tests/fixtures/gates
  EVIDENCE: pending

- [ ] G2: 둘째
  CRITERION: G2 가 자기 oracle 의 도장을 갖는다
  CHECK: echo g2 ok
  EXPECT: g2 ok
  EVIDENCE: pending

- [ ] G3: 셋째
  CRITERION: G3 가 자기 oracle 의 도장을 갖는다
  CHECK: echo g3 ok
  EXPECT: g3 ok
  EVIDENCE: pending

- [ ] G4: 넷째
  CRITERION: G4 가 자기 oracle 의 도장을 갖는다
  CHECK: echo g4 ok
  EXPECT: g4 ok
  EVIDENCE: pending

- [ ] M1: 중간의 사람 확인 — 도장 대상이 아니다
  MANUAL: 사람이 확인
  CRITERION_HASH: 4760c4040566
  EVIDENCE: pending

- [ ] G5: 다섯째 — CWD 를 가진 5속성 블록
  CRITERION: G5 가 자기 oracle 의 도장을 갖는다
  CHECK: echo g5 ok
  EXPECT: g5 ok
  CWD: /Users/example/dev/fz-plugin/tests/fixtures/gates
  EVIDENCE: pending

- [ ] G6: 여섯째 — 여기서 밀림이 블록 폭(속성 4 + 1)을 넘어선다
  CRITERION: G6 가 자기 oracle 의 도장을 갖는다
  CHECK: echo g6 ok
  EXPECT: g6 ok
  EVIDENCE: pending

- [ ] G7: 일곱째
  CRITERION: G7 이 자기 oracle 의 도장을 갖는다
  CHECK: echo g7 ok
  EXPECT: g7 ok
  EVIDENCE: pending

- [ ] G8: 여덟째
  CRITERION: G8 이 자기 oracle 의 도장을 갖는다
  CHECK: echo g8 ok
  EXPECT: g8 ok
  EVIDENCE: pending
