# Gates: 셸 오류 흔적 — 디렉토리
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 통과했는데 출력에 Is a directory — 다른 것을 재고 EXPECT 를 냈다 (F-229)

- [ ] G1: 디렉토리를 파일로 읽고도 통과 토큰을 낸다
  CHECK: cat . 2>&1; echo dir probe ok
  EXPECT: dir probe ok
  EVIDENCE: pending
