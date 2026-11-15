# fz-rebase 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "feature 브랜치 최신화해줘" | trigger | 핵심 유스케이스 (description 예시) |
| "이 브랜치 develop 위로 리베이스" | trigger | intent-trigger "리베이스" + "develop.*위로" |
| "롱텀 브랜치 동기화" | trigger | intent-trigger "브랜치.*동기화" |
| "리베이스했는데 내 변경이 사라졌어" | trigger | intent-trigger "리베이스.*사라" — 유실 게이트가 이 스킬 소관 |
| "rebase my branch onto develop" | trigger | intent-trigger "rebase" |
| "커밋해줘" | NOT trigger | → fz-commit (Will Not: 커밋 생성) |
| "PR 만들어줘" | NOT trigger | → fz-pr (Will Not: PR 생성) |
| "가이드 최신화해줘" | NOT trigger | → fz-modernize (브랜치 문맥 없는 "최신화"는 문서 모더나이제이션) |
| "이 커밋 되돌려줘" | NOT trigger | → fz-fix (Will Not: 코드/커밋 되돌리기) |

### Functional

회귀 oracle: `bash <스킬 디렉토리>/scripts/test-gates.sh` (78 assertion).
구성은 유실 검출 · 오경보 방지 · **SKILL 정적 계약**(K 계열) 셋이다. 셋째는 충돌 확인 절차가
문서에서 사라지는 것을 잡는다 — 그 절차는 스크립트가 아니라 프롬프트라 동작 oracle이 없다.

| Given | When | Then |
|-------|------|------|
| behind + clean + 충돌 없음 | `/fz-rebase` | ff pull → snapshot → `--rebase-merges` → check/audit/prepush 전부 exit 0 → 확인 게이트 → push 후 0/0 |
| LTB과 TRACK이 diverged | `/fz-rebase` | Step 0에서 중단 + 상태 제시 + 사용자 판단 요청 |
| 리베이스 중 충돌 | `/fz-rebase` | 중단 → `--ours`=팀원/`--theirs`=내 커밋 명시 → 사용자와 해결 (`-X` 미사용) |
| 팀원 삭제 + 내 수정, `git rm`으로 해소 | audit | HALT — 내 변경 유실 [S1] |
| 충돌을 `--theirs`로 해소해 팀원 변경 폐기 | audit | HALT — 팀원 변경 덮어쓰기 + 귀속 커밋 [S2] |
| base가 내 패치를 흡수 (커밋 수 감소) | audit | OK 무경보 — 흡수는 유실이 아니다 [S3] |
| 팀원 rename, 내 hunk가 새 경로 착지 | audit | OK 무경보 (분할 전 rename 매핑) [S4] |
| 머지 커밋의 수동 해결 미재적용 | audit | HALT — subject 대조 [S5] |
| 내가 지운 파일 + 팀원 수정 → 파일 유지로 해소 | audit | HALT — 내 삭제 유실 [S7] |
| 팀원이 지운 파일 + 내 수정 → 파일 유지로 해소 | audit | HALT — 팀원 삭제 유실 [S8] |
| 바이너리 변경 (MINE-only) | audit | OK 무경보 / 내용 되돌려지면 HALT [S9 S10] |
| 파일 mode 변경 (MINE-only) | audit | OK 무경보 / mode 되돌려지면 HALT [S11 S11b] |
| 바이너리 OVERLAP (양쪽 변경) | audit | WARN + 목록 (auto-HALT 아님) [S12] |
| 내가 손대지 않은 팀원 파일 오염 | audit | HALT — 버킷② 위반 [S15] |
| ff-pull 이후 팀원이 원격에 push | prepush | HALT — 파괴될 커밋 지목 [S6] |
| 원격에 평범한 PR 머지 | prepush | WARN (HALT 아님) [S13] |
| 원격에 수동 해결 머지(evil) | prepush | HALT — 부모에 없는 내용 [S14] |
| 워킹 트리 dirty | `/fz-rebase` | 리베이스 전 중단 + stash/commit 확인 요청 |
