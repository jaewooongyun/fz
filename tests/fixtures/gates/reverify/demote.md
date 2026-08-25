# Gates: 강등 대상
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: ready_for_review
Scope: 이미 통과 기록이 있으나 아티팩트가 깨졌다

- [x] G1: 아티팩트가 done 상태
  CHECK: grep -q '^done$' "/Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates/reverify/artifacts/broken.txt" && echo artifact ok
  EXPECT: artifact ok
  EVIDENCE: exit=0; shell=/bin/sh; output=artifact ok
