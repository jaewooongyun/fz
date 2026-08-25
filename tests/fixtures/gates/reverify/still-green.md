# Gates: 재현되는 성공
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: ready_for_review
Scope: 이미 통과했고 지금도 통과한다

- [x] G1: 아티팩트가 done 상태
  CHECK: grep -q '^done$' "/Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates/reverify/artifacts/state.txt" && echo artifact ok
  EXPECT: artifact ok
  EVIDENCE: exit=0; shell=/bin/sh; output=artifact ok
