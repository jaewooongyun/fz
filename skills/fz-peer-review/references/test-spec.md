# 테스트 케이스 (fz-peer-review)

> 근거: `guides/skill-testing.md` §1(3단계 프레임워크)·§4(test-spec 템플릿). 트리거 어휘는 description '예:'/'비사용:' + `intent-triggers`, Functional oracle은 본 스킬의 Phase(Gather→Analyze→Challenge→Synthesize→Deliver)·Gate 5.5·Synthesize 투표/Origin 보정·CHECKPOINT·에러 대응에서 도출.

### Triggering Test

| 쿼리 | 예상 | 비고 (근거 / redirect) |
|------|------|----------------------|
| "팀원 PR 리뷰해줘" | trigger | description '예:' 핵심 유스케이스 |
| "이거 피어리뷰 좀 해줘" | trigger | description '예:' (피어리뷰) + intent-trigger `피어리뷰` |
| "이 PR 검토해줘" | trigger | description '예:' (PR 검토) |
| "동료가 올린 PR 리뷰 부탁해" | trigger | intent-trigger `팀원\|PR.*리뷰` (동료=팀원) |
| "내가 방금 작성한 코드 리뷰해줘" | NOT trigger | → fz-review (description '비사용: 자기 코드', Will Not '자기 코드 리뷰') |
| "이 PR 변경 내용 해설해줘" | NOT trigger | → fz-pr-digest (description '비사용: PR 해설') |
| "codex로 이 변경 교차검증해줘" | NOT trigger | → fz-codex (Will Not 'Codex 위임 → /fz-codex') |
| "이 PR의 버그 직접 고쳐줘" | NOT trigger | → fz-fix (Will Not '코드를 직접 수정하지 않음, 리뷰만 수행') |

### Functional Test (Given/When/Then)

| Given | When | Then (pass/fail oracle) | 유형 |
|-------|------|------------------------|------|
| PR 번호 입력, `gh auth status` 성공, 표준 규모 diff | `/fz-peer-review 123` | Gate 5.5 통과(`tier.txt` 기록) 후 Synthesize CHECKPOINT 3파일(`synthesized-issues.json`·`confidence-matrix.md`·`review-index.md`) + Deliver CHECKPOINT 2파일(`review-report.md`·`pr-comments.md`) 모두 Write 완료 = pass | normal |
| 변경 13줄 소규모 PR, `--tier` 미지정 | `/fz-peer-review 45` | Gate 5.5에서 auto Tier 0 결정 → `tier.txt == "0"` 기록 + 팀 미생성(Lead 단독 분석, TeamCreate 호출 0회) = pass | normal |
| 지적 패턴이 base 브랜치에 이미 존재(`base-behavior.md`상 pre-existing), 에이전트가 `origin=pre-existing` 보고 | `/fz-peer-review 123` | Synthesize Origin 보정으로 해당 이슈 severity가 `suggestion`으로 cap + Confidence Matrix Origin 열 `P` + 리포트 `[기존 동작 동일]` 태그 부착 = pass | edge-case |
| `gh auth status` 실패 | `/fz-peer-review 123` | git 폴백 경로(`git fetch upstream` + `git diff`)로 `${WORK_DIR}/diff.patch` 생성(비어있지 않음) → 리뷰 파이프라인 계속 진행 = pass | failure |
| Tier 2 결정, Codex challenger 호출 실패 | `/fz-peer-review 123` | 2-agent 투표 모드로 전환(review-arch + review-quality만, Codex 투표 제외) → Confidence Matrix 계산 완료 + 최종 verdict 산출(리뷰 비중단) = pass | failure |
