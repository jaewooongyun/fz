# Gates: IMPL_ROOT 주입
ROOT: /srv/fz-plugin/tests/fixtures/gates
IMPL_ROOT: /srv/fz-plugin/tests/fixtures/gates/impl-root/tree
STATE: active
Scope: 원장 헤더 IMPL_ROOT 가 CHECK 의 FZ_IMPL_ROOT 로 들어간다 (F-347)

- [ ] G1: 구현 트리의 표지 파일을 본다
  CHECK: test -f "${FZ_IMPL_ROOT:?}/marker.txt" && echo impl root injected
  EXPECT: impl root injected
  ENV: FZ_IMPL_ROOT
  EVIDENCE: pending
