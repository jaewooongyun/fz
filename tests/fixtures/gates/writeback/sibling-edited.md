# Gates: 실행 중 형제 게이트 편집
ROOT: /Users/example/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: G1 이 도는 동안 원장에 형제 게이트가 추가된다 — G1 블록은 그대로다

- [ ] G1: 형제를 추가하고 성공
  CHECK: printf '\n- [ ] G3: 실행 중 추가된 형제\n  CHECK: true\n  EXPECT: ok\n  EVIDENCE: pending\n' >> "/Users/example/dev/fz-plugin/tests/fixtures/gates/writeback/sibling-edited.md" && echo done
  EXPECT: done
  EVIDENCE: pending

- [ ] G2: 손대지 않는 형제
  MANUAL: 사람이 확인
  CRITERION_HASH: 4760c4040566
  EVIDENCE: pending
