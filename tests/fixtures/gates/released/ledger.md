# Gates: 시점 고정 원장
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 릴리스 시점 사실을 박은 CHECK — released <tag> 뒤에는 다시 돌리지 않는다 (F-344)

- [ ] G1: 릴리스 시점에만 참인 사실
  CHECK: test ! -f released/released.flag && echo rel ok
  EXPECT: rel ok
  EVIDENCE: pending
