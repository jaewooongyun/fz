# Gates: 출력에 세미콜론
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 정상 출력이 ; 를 담는다 — 증거 레코드의 구분자와 충돌

- [ ] G1: 세미콜론을 담은 출력
  CHECK: echo "done; cleanup=ok; n=3"
  EXPECT: done
  EVIDENCE: pending
