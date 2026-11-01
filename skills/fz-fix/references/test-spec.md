# fz-fix 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering Test — 트리거 정확도

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "탭 전환 시 크래시 나, 고쳐줘" | trigger | 핵심 유스케이스 (크래시 수정) |
| "API 응답이 null일 때 버그 있어" | trigger | 버그 수정 |
| "빌드하면 에러 떠" | trigger | 에러 해결 |
| "로그인이 안 돼" | trigger | 증상 기반 디버깅 |
| "새 다운로드 기능 구현해줘" | NOT trigger | → /fz-code (새 기능 구현) |
| "플레이어 모듈 아키텍처 설계해줘" | NOT trigger | → /fz-plan (계획·설계) |
| "이 함수 누가 호출하는지 찾아줘" | NOT trigger | → /fz-search (코드 탐색·구조 분석) |
| "내가 짠 코드 리뷰해줘" | NOT trigger | → /fz-review (풀 코드 리뷰) |
| "codex exec로 직접 검증 돌려줘" | NOT trigger | → /fz-gpt (GPT CLI 직접 호출 금지·위임) |

### Functional Test — Given / When / Then

| Given | When | Then | type |
|-------|------|------|------|
| 크래시 재현 경로 확인됨, 단일 파일 수정 | `/fz-fix "탭 전환 시 listener nil 크래시"` | Step 1c에서 root-cause 식별 → Step 3 빌드 성공(xcodebuild exit 0) → Gate Bug Fix Complete 체크리스트 5/5 통과 | normal |
| 단순 상수 수정, `--gpt` 옵션 지정 | `/fz-fix "타임아웃 30초로 변경" --gpt` | Step 4에서 `/fz-gpt check` 호출 → verdict=pass 분기로 완료 보고 | normal |
| 분석 결과 수정 대상이 3개+ 파일 | `/fz-fix "여러 모듈 상태 불일치"` | 자동 전환 트리거 발동 → 코드 수정 0줄 + `/fz-code` 전환 제안 보고 | edge-case |
| 수정 대상이 `static let shared` + 가변 `var`, 동기화 메커니즘 부재 (동시성 키워드 없음) | `/fz-fix "공유 인스턴스 값 깨짐"` | 역방향 트리거 발동 → 수정 전 3패턴 점검 + 동시성 안전성 검증 섹션 활성 | edge-case |
| Step 1c에서 root-cause 불명확 | `/fz-fix "가끔 화면 멈춤"` | 코드 수정 0줄 + AskUserQuestion 발생 (Step 1c 완료 전 수정 금지) | failure |
| 빌드 3회 연속 실패 (LOOP 한도 도달) | 수정-빌드 사이클 반복 | 4회차 자동 재시도 중단 + `/fz-gpt check` 보조 진단 1회 → 결과 보고 → AskUser | failure |
| Serena 연결 실패 | `/fz-fix` 탐색 단계(Step 1b) | Grep + Glob 폴백으로 탐색 계속 진행 (중단 없음) | failure |
