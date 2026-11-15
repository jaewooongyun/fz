# Gates: CWD traversal
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: WORK_DIR 밖으로 탈출하는 CWD

- [ ] G1: 상위 디렉토리 지정
  CHECK: pwd
  EXPECT: /
  CWD: ../../..
  EVIDENCE: pending
