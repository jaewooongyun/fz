# Gates: 지연 손자 출력
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 부모는 즉시 끝나고 손자가 4초 뒤에 결정적 출력을 낸다

- [ ] G1: 손자가 늦게 EXPECT 를 낸다
  CHECK: (sleep 4; echo LATE_OK) & echo spawned
  EXPECT: LATE_OK
  TIMEOUT: 12
  EVIDENCE: pending
