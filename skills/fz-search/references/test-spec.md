# fz-search 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering Test

**should-trigger** (description '예:' 트리거 어휘 + 모드 자동 판별 키워드 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "AuthRepository 어디 있어?" | trigger | description 예 "어디 있어?" — 심볼 위치 검색 |
| "ContentDetail 모듈 구조 탐색해줘" | trigger | description 예 "탐색해줘" + arch 모드 키워드(모듈/구조) |
| "PlayerInteractor 누가 쓰고 있어?" | trigger | description 예 "누가 쓰고 있어?" → impact 모드(참조/영향) |
| "싱글톤 패턴 찾아줘" | trigger | description 예 "찾아줘" + pattern 모드 키워드(패턴) |

**should-NOT-trigger** (Boundaries Will Not / description '비사용:'의 대안 스킬 기반)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 버그 고쳐줘" | NOT trigger | → /fz-fix | Boundaries Will Not "코드 수정" |
| "이 코드 리뷰해줘" | NOT trigger | → /fz-review | Boundaries Will Not "코드 리뷰" |
| "어떤 방식이 좋을지 트레이드오프 비교해줘" | NOT trigger | → /fz-discover | description 비사용 "접근 방식 탐색 →fz-discover" |
| "세션/이슈 정리해줘" | NOT trigger | → /fz-manage | Boundaries Will Not "세션/Issue Tracker 관리" |

### Functional Test (Given/When/Then)

| Type | Given | When | Then (pass/fail oracle) |
|------|-------|------|--------------------------|
| normal | 비-티켓 세션 컨텍스트, Serena 연결됨, 질의에 "모듈/구조" 키워드 | `/fz-search "ContentDetail 모듈 구조"` | arch 모드 자동 선택(모드 판별 표) + Gate: Search Complete 5/5 통과 (비-티켓 세션 분기 → `write_memory("fz:checkpoint:search", ...)` 기록 완료) |
| normal | 인자에 `[A-Z]{2,6}-\d{2,5}` 패턴, "누가 쓰는"·"전수" 키워드, Serena 연결됨 | `/fz-search "TKT-1234 AuthRepository 누가 쓰는지 전수"` | Gate 0 (Work Dir Ready) 3/3 통과 (`{CWD}/TKT-1234/` + index.md 생성) + impact depth 2 추적 + Coverage Gate 통과(전수 주장) + `{WORK_DIR}/search/search-result.md` 기록 |
| edge-case | `--deep` 플래그 + 네이티브 Workflow 도구 가용 | `/fz-search --deep "Player 모듈 구조"` | `mode:'workflow'` 반환 → 출력에 신뢰도 등급 열(★★★/★★/★) 표시 + `return.metrics`(agentCalls/nullCount/stages/fallback) → experiment-log §5.7 기록 |
| edge-case | 모드 트리거 키워드가 복수/모호한 질의 | `/fz-search "Player 관련된 거"` | AskUserQuestion으로 모드 확인 (임의 모드 선택 금지) → 사용자가 선택한 모드로 실행 |
| failure | `--deep` 플래그 + Workflow **도구 미가용**(호출 자체 거부) | `/fz-search --deep "Auth 데이터 흐름"` | 기본 순차 모드 자동 전환 + 사유 experiment-log 기록 (중단/크래시 없이 결과 반환) |
| failure | `--deep` 실행 중 실패 → `mode:'fallback'` 반환 | 동일 | ⛔ 자동 전환 아님 — `guides/skill-authoring.md` §12 판별 표로 분기 (L3 `resume` 우선). 순차 모드 강등은 L4 승인 후 |
| failure | Serena MCP 연결 실패 | `/fz-search "AuthRepository 영향 범위"` | Grep + Glob 전용 폴백(패턴 검색만 수행) + 크래시 없이 Gate: Search Complete 통과 |
