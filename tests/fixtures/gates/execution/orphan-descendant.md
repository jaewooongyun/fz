# Gates: 손자 프로세스 잔존
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 부모가 먼저 끝나고 손자가 파이프를 붙잡는다

- [ ] G1: 백그라운드 손자를 남기고 종료
  CHECK: (sleep 30 &) ; echo spawned
  EXPECT: never matches this
  TIMEOUT: 3
  EVIDENCE: pending
