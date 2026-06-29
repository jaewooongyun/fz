# 테스트 케이스 (fz-modernize)

### Triggering Test

**should-trigger (≥3)**

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "fz 가이드 7개 최신화해줘" | trigger | 핵심 유스케이스 — description '예: 최신화' |
| "프롬프트 최적화 가이드 문서 갱신해줘" | trigger | description '예: 문서 갱신' |
| "Opus 4.8 출시됐는데 가이드 모더나이제이션 해줘" | trigger | description '예: 모더나이제이션' + 새 모델 출시 어휘 |
| "harness-engineering.md stale 항목 정리해줘" | trigger | description '예: stale 정리' |

**should-NOT-trigger (≥3)**

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "최신 API로 새 기능 코드 구현해줘" | NOT trigger | fz-code | '최신' 어휘 있으나 대상이 코드 구현 (description '비사용: 코드 구현 →fz-code') |
| "이 스킬 구조 최신 템플릿으로 바꿔줘" | NOT trigger | fz-skill | '최신' 어휘 있으나 대상이 스킬 구조 (description '비사용: 스킬 구조 →fz-skill') |
| "메모리에 쌓인 stale 교훈 정리해줘" | NOT trigger | fz-memory | 'stale 정리' 어휘 있으나 대상이 메모리(가이드/문서 아님) |

### Functional Test

| Given | When | Then (pass/fail oracle) | type |
|-------|------|--------------------------|------|
| 갱신 대상 가이드 존재 + 외부 자료 접근(WebSearch/Codex) 가능 | `/fz-modernize "fz 가이드 최신화"` (full) | Phase 0→6 순차 진행, Gate 0~6 전 체크리스트 충족 + Phase 6 AC8 broken link 0건 → Gate 6 통과 | normal |
| 외부 자료 접근 가능 + 단일 가이드 지정 | `/fz-modernize probe "guides/harness-engineering.md"` | Phase 1만 실행 → `probe/probe-report.md` 생성 + Gate 1 통과(Tier 합의·5+ 자료·Status 칼럼) + Phase 2~6 미실행 | normal |
| 사용자 요청에 "그냥/가볍게" 신호 포함 | `/fz-modernize light "그냥 가볍게 최신화"` | Phase 1+2 + Codex micro-eval만 실행, Phase 3~6 미진입, Codex 카운터 1 소비 | edge-case |
| Probe 결과 특정 stale 항목 해소 자료가 Tier 3(A5) 단독 | Phase 3 Plan 작성 → Phase 5 Execute | AC9 grep VIOLATION 0건 — 해당 line이 `[verified: A5]` 단독이 아닌 `[partially-verified: A5; …]`로 기록 → Gate 5 통과 | edge-case |
| Plan v1/v2/v3 모두 Codex needs_revision (누적 3/3) | Phase 4 Verify 4회차 진입 시점 | Codex 4회차 미실행 + 사용자 에스컬레이션 발생 → Gate 4 '누적 카운터 ≤3' 충족 | failure |
| `probe/probe-report.md` 부재(Probe 미실행) | `/fz-modernize plan "update-plan v1 작성"` | `plan/update-plan.md` 미생성 + Probe(Phase 1) 선행 안내 → Plan-before-Probe 차단 | failure |
