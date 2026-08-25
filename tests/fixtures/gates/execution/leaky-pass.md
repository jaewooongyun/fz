# Gates: 통과하면서 프로세스를 남긴다
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: exit 0 + EXPECT 매칭인데 손자가 계속 산다

- [ ] G1: 성공하지만 손자를 남긴다
  CHECK: (sleep 20 &) ; echo ready
  EXPECT: ready
  TIMEOUT: 4
  EVIDENCE: pending
