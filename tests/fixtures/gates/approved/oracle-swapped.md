# Gates: 승인 후 oracle 교체
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
APPROVED: yes
Scope: 도장을 받은 뒤 CHECK 를 쉬운 것으로 바꿨다

- [ ] G1: 어려운 검사를 통과한다
  CRITERION: 실제로 어려운 검사가 통과해야 한다
  CHECK: echo ok
  EXPECT: ok
  CWD: /usr
  APPROVED_ORACLE_HASH: b4236ed7863e
  EVIDENCE: pending
