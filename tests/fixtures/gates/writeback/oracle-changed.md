# Gates: 실행 중 oracle 변경
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: CHECK 가 실행되는 동안 자기 CHECK 라인이 바뀐다

- [ ] G1: 실행 중 자기 oracle 을 수정
  CHECK: sed -i '' 's/echo SELF_MUTATE/echo CHANGED/' "/Users/example/dev/fz-plugin/tests/fixtures/gates/writeback/oracle-changed.md"; echo SELF_MUTATE
  EXPECT: SELF_MUTATE
  EVIDENCE: pending
