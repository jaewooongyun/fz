# Gates: 실행 cwd 가 정규 경로인가
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 검증은 realpath 로 하고 실행은 헤더 원문으로 하면 그 사이 심볼릭을 돌릴 수 있다

- [ ] G1: cwd 를 증거에 남긴다
  CHECK: echo ok
  EXPECT: ok
  EVIDENCE: pending
