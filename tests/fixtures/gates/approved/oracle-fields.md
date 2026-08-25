# Gates: oracle_hash 민감도
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 승인 계약이 커버해야 하는 필드가 전부 해시에 들어가는지

- [ ] G1: 모든 계약 필드를 담은 게이트
  CRITERION: 사람이 읽는 합격 조건
  CHECK: echo ok
  EXPECT: ok
  TIMEOUT: 30
  EVIDENCE: pending
