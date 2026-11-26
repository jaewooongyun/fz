# Gates: 기준선 RED — 깨진 명령과 구별되는 정상 실패(F-656 음성)
ROOT: /srv/fz-plugin/tests/fixtures/gates
STATE: active

- [ ] R1: CHECK 가 스스로 찍은 'not found' 줄
  CRITERION: 키가 아직 없다
  CHECK: grep -q zzz /dev/null || { echo "handler registry: not found"; exit 1; }; echo OK
  EXPECT: OK
  SIDE_EFFECTS: none
  TIMEOUT: 30
  EVIDENCE: pending

- [ ] R2: 아직 만들지 않은 스크립트(경로)를 부른다
  CRITERION: 새 검사 스크립트가 통과한다
  CHECK: bash fz-not-yet-created-xyz/check.sh
  EXPECT: OK
  SIDE_EFFECTS: none
  TIMEOUT: 30
  EVIDENCE: pending

- [ ] R3: 아직 만들지 않은 실행 파일(경로)을 부른다
  CRITERION: 새 도구가 판을 낸다
  CHECK: ./fz-not-yet-tool-xyz --version
  EXPECT: 1.0
  SIDE_EFFECTS: none
  TIMEOUT: 30
  EVIDENCE: pending
