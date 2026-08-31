# Gates: 단계 건너뛰기
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 전 게이트 충족 상태에서 active → closed 직행을 시도한다

- [x] G1: 충족될 게이트
  CHECK: echo transition probe
  EXPECT: transition probe
  EVIDENCE: sig=03b76a7c2a5b; exit=0; cwd=/Users/example/dev/fz-plugin/tests/fixtures/gates; path=f88de71baeb2/29 entries; output=transition probe
