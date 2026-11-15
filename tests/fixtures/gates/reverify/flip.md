# Gates: 통과 뒤 강등
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 첫 실행은 통과하고 재실행은 떨어지는 게이트 — 강등 기록

- [ ] G1: 한 번만 통과
  CRITERION: 첫 실행만 통과한다
  CHECK: if [ -e flip.ran ]; then echo again; else touch flip.ran && echo flip ok; fi
  EXPECT: flip ok
  EVIDENCE: pending
