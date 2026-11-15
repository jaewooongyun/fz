# fz-review 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

> 근거: `guides/skill-testing.md` §1(테스트 3단계) + §4(테스트 스펙 템플릿). Then은 객관 pass/fail oracle로 기술.

### Triggering Test

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "구현한 코드 리뷰해줘" | trigger | 핵심 유스케이스 ('예: 리뷰해줘') |
| "내가 짠 코드 검증해줘" | trigger | 자기 코드 검증 ('예: 검증해줘') |
| "이 코드 품질 확인해줘" | trigger | 품질 분석 ('예: 품질 확인') |
| "내 코드 괜찮아?" | trigger | 품질 자문 ('예: 괜찮아?') |
| "내 코드 좀 봐줘" | trigger | 자기 코드 리뷰 ('예: 내 코드 봐줘') |
| "팀원 PR 리뷰해줘" | NOT trigger | → fz-peer-review ('리뷰' 겹쳐도 팀원 PR은 범위 밖, '비사용:') |
| "이 버그 직접 고쳐줘" | NOT trigger | → fz-fix (직접 수정, '비사용:') |
| "이 기능 새로 구현해줘" | NOT trigger | → fz-code (대규모 구현, Will Not) |
| "codex로 검증해줘" | NOT trigger | → fz-gpt ('검증' 겹쳐도 GPT 직접 호출은 Will Not) |
| "아키텍처 계획 세워줘" | NOT trigger | → fz-plan (계획 수립, Will Not) |

### Functional Test

| Given | When | Then | type |
|-------|------|------|------|
| 구현된 코드 diff 존재 + GPT CLI 가용 + 소규모 아님(리팩토링 포함) | `/fz-review "구현한 코드 리뷰해줘"` | 검증 1/2/3(Serena 참조 무결성 + `/fz-gpt review` + `/sc:sc-analyze`) 모두 실행(GPT 리뷰 생략 0건) → Gate 4(Review Passed) 체크리스트 통과 → Phase 5.5 역방향 검증 후 Gate 5(Reflection Rate ≥ 80%) 통과; 완료 보고에 총이슈→해결/보류 + Reflection Rate 명시 | normal |
| 모드 게이트에서 light 선택(또는 `light` 인자 · 신호어) | `/fz-review light "가볍게 봐줘"` | review-live 미기동 + Phase 5 Lead 3중 검증(`/fz-gpt review` 포함 — 끈 세션이면 `[GPT 미사용]`) + Phase 5.5 · Reflection Rate 그대로; 산출물에 전수/카운트/부정 주장 포함 시 Coverage Gate 적용(light에서도 생략 불가) | edge-case |
| 인자에 `[A-Z]{2,6}-\d{2,5}` 패턴 없음 + 브랜치명 없음 | `/fz-review "내 코드 봐줘"` | Phase 0에서 저장 여부 AskUserQuestion 발생 → '예' 시 `NOTASK-{YYYYMMDD}/` + index.md 생성 / '아니오' 시 Serena fallback → WORK_DIR 결정 → Gate 0(Work Dir Ready) 3개 항목 통과 | edge-case |
| 코드 diff 존재 + 검증 2에서 fz-gpt 통신 실패 | `/fz-review "리뷰해줘"` | 재시도 1회 후 fresh-context Agent(review-correctness 관점)로 검증 2 대체 + 인용 태그 `[fresh-context: claude]` + 이종 안전망 상실 명시 (Agent 미가용 시 `/sc:sc-analyze` 폴백); 검증 2 미생략 상태로 Gate 4 진행 | failure |
