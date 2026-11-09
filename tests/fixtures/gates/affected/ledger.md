# Gates: 영향 게이트
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 바뀐 파일이 근거인 충족 게이트 (F-349 경로 · F-552 basename)

- [ ] G1: 경로를 그대로 부르는 게이트
  CHECK: test -n "scripts/foo.py" && echo g1 ok
  EXPECT: g1 ok
  EVIDENCE: pending

- [ ] G2: 공유 스크립트를 변수로 부르는 게이트
  CHECK: S=tools; test -n "$S/bar.sh" && echo g2 ok
  EXPECT: g2 ok
  EVIDENCE: pending

- [ ] G3: 무관한 게이트
  CHECK: echo g3 ok
  EXPECT: g3 ok
  EVIDENCE: pending
