# Gates: 양끝 슬래시 EXPECT
ROOT: /Users/jaewoongyun/dev/fz-plugin/tests/fixtures/gates
STATE: active
Scope: 디렉토리 경로와 무플래그 정규식이 같은 모양이다

- [ ] G1: 디렉토리를 출력한다
  CHECK: echo "installed to /var/log/"
  EXPECT: /var/log/
  EVIDENCE: pending
