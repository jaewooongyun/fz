# fz-gpt 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering Test

should-trigger (description '예:' 어휘 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "이 변경분 codex로 리뷰해줘" | trigger | '예: codex' + review 서브커맨드 (정문 `gpt-call.sh review --base`) |
| "코드 교차검증 돌려줘" | trigger | '예: 교차검증' — 핵심 유스케이스 (독립 모델 상호 검증) |
| "GPT로 한 번 더 확인해줘" | trigger | '예: GPT로 확인' |
| "이 계획 상호검증해줘" | trigger | '예: 상호검증' + verify 서브커맨드 (계획 검증) |
| "PR 올리기 전 최종 검증해줘" | trigger | final 서브커맨드 (argument-hint, resume 심화) |

should-NOT-trigger (Boundaries Will Not / '비사용:' 대안 스킬)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 버그 직접 고쳐줘" | NOT trigger | fz-fix | '비사용: 직접 수정 →fz-fix' + Will Not "코드를 직접 수정하지 않음 (검증만 수행)" |
| "이 컴파일 에러 수정해줘" | NOT trigger | fz-fix | Will Not "코드 직접 수정 안 함" — GPT는 검증 전용 |
| "내 코드 자체적으로 검증해줘" | NOT trigger | fz-review | '비사용: 자기 리뷰 →fz-review' (gpt/교차검증 미언급 = 자기 3중 검증) |

### Functional Test (Given/When/Then)

| Given | When | Then (pass/fail oracle) | type |
|-------|------|--------------------------|------|
| Git diff 존재, GPT CLI 설치 | `/fz-gpt review` | 정문(`gpt-call.sh review --out`) 실행 → 구조화 이슈 캡처 + verdict(approved/rejected/conditional) 판정 → Gate "GPT Verification Complete" 3항목 전부 통과 | normal |
| Claude 계획 초안 존재 | `/fz-gpt verify` | gpt가 plan을 `--output-schema`로 독립 재작성 → Claude 계획과 diff → divergence 기록 + verdict 판정 후 /fz-plan으로 반환 (Gate 3/3 통과) | normal |
| base branch 후보 불확실(자동 결정 불가) | `/fz-gpt review` | Will Not "Base branch를 추측하지 않음" — 추측 base 실행 0건, 사용자에게 질문 → 확정 후 실행 | edge-case |
| CLAUDE.md `## GPT Skills` 테이블(Tier 1) 부재 | `/fz-gpt verify` | Tier 2(글로벌 fz-*) → Tier 3(인라인 프롬프트) 순차 폴백으로 서브커맨드 실행 완료 (Gate "서브커맨드 실행 완료" 통과) | edge-case |
| GPT CLI 통신 실패 | `/fz-gpt review` | 컨텍스트 축소 후 재시도 → 실패 시 Issue Tracker에 기록 + /sc:sc-analyze 단독 폴백 실행 (3회 연속 실패 시 사용자 에스컬레이션) | failure |
