# Gates: 서명 위조
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 형식은 완벽하고 서명만 지어냈다 — 서명 검증을 직접 관측하는 유일한 케이스

- [x] G1: 절대 통과 못 할 게이트
  CHECK: false
  EXPECT: never
  EVIDENCE: sig=deadbeef1234; exit=0; cwd=/Users/example/dev/fz-plugin/tests/fixtures/gates; path=abc/1 entries; output=never
