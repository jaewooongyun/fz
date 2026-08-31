# 테스트 케이스 (fz-pr-digest)

### Triggering Test

**should-trigger** (description '예:' 트리거 어휘 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "이 PR 뭐가 바뀐 거야?" | trigger | description '예: 뭐가 바뀐' — 핵심 유스케이스 |
| "PR #3394 설명해줘" | trigger | description '예: 설명해줘' |
| "이 변경사항 해설해줘" | trigger | description '예: 해설' |
| "이 PR 이해하고 싶어, 알려줘" | trigger | description '예: PR 이해' + intent-trigger '알려줘' |
| "처음 보는 사람도 알게 과외하듯 설명해줘" | trigger | description '예: 과외하듯, 처음 보는 사람도' — Tutor 유스케이스 |
| "이 기능 전체 흐름 알려줘" | trigger | intent-trigger '전체.*흐름' |

**should-NOT-trigger** (Boundaries Will Not / description '비사용:' 대안 스킬, redirect 명시)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 PR 문제점 찾아서 평가해줘" | NOT trigger | /fz-peer-review | description '비사용: 평가·지적' + Will Not '이슈 도출/severity 안 함' |
| "이 PR대로 코드 고쳐줘" | NOT trigger | /fz-fix | Will Not '코드를 수정하지 않음' |
| "이 PR 기능 그대로 구현해줘" | NOT trigger | /fz-code | Will Not '코드를 수정하지 않음' |
| "해설 끝났으니 커밋하고 PR 올려줘" | NOT trigger | /fz-commit, /fz-pr | Will Not '커밋/PR 생성하지 않음' |

### Functional Test

| Given | When | Then | type |
|-------|------|------|------|
| PR #3394 존재, diff 50–500줄, gh 인증 정상 | `/fz-pr-digest 3394` | 자동 Tier=Standard 선택 + `pr-digest-standard.md` 생성 + 대화 출력에 [한 줄 요약·변경 의도·핵심 Before/After] 3요소 모두 존재 | normal |
| `--deep` 명시, gh 인증 정상 | `/fz-pr-digest 3394 --deep` | `pr-digest-deep.md`에 '기술 해설'·'학습 포인트' 섹션 존재 + Context7 query-docs 1회 이상 호출(Step 1.4) | normal |
| diff < 50줄 PR, 플래그 미지정 | `/fz-pr-digest 3394` | 자동 Tier=Light 선택 + `pr-digest-light.md` 생성(한 줄 요약 + 파일별 변경 테이블), Before/After 섹션 부재 | edge-case |
| 신규 추가 파일(BASE에 원본 미존재) | `/fz-pr-digest 3394` | 해당 파일 Before가 "(신규 파일)"로 표기 + After만 해설(중단 없음) | edge-case |
| gh 인증 실패(gh CLI unauthenticated) | `/fz-pr-digest 3394` | git 폴백(git fetch + git diff)으로 diff 수집 성공, 해설 정상 생성(중단 없음) | failure |
| Serena 심볼 탐색 실패(activate/find_symbol 에러) | `/fz-pr-digest 3394` | diff 기반 Light 수준 해설로 폴백 + 아키텍처 맥락 섹션 생략(중단 없음) | failure |
| `--tutor` 명시, Serena 정상 | `/fz-pr-digest 3394 --tutor` | `pr-digest-tutor.md`에 A~D 4섹션 모두 존재 + 모든 매핑 블록에 `file:line` 인용 존재(G1) + 모든 "없으면"에 [기계적]\|[추론] 태그 존재(G2) | normal |
| 변경 심볼이 protocol 채택 타입 | `/fz-pr-digest 3394 --tutor` | §7-D 구조 근거에 채택자 수가 [실측: 채택자 N] 형태로 기재(G3) + 주입 지점 `file:line` 명시 | normal |
| 폐포 탐색이 40심볼 초과 | `/fz-pr-digest 3394 --tutor` | seed 절단 후 계속 진행 + §7-E 탐색 경계에 제외 목록·탐색 심볼 수 기재(⛔조용한 절단 없음) | edge-case |
| R1 역참조 5홉까지 진입점 미도달 | `/fz-pr-digest 3394 --tutor` | §7-A 흐름을 도달 지점부터 서술 + §7-E에 "진입점 미도달" 기록(중단 없음) | edge-case |
| 탐색 축 결과 0건(도구 오류로 인한 위음성) | `/fz-pr-digest 3394 --tutor` | 0건을 사실로 확정하지 않고 다른 도구로 재확인 수행, 재확인 후에도 0건이면 그 사실을 §7-E에 기록 | failure |
| peer-review 연계, 플래그 미지정 | `/fz-peer-review 3394 --explain` | Tutor 티어 진입(Standard 아님) + peer-review WORK_DIR에 `pr-digest-tutor.md` 저장 | normal |
| peer-review 연계, `--light` 병기 | `/fz-peer-review 3394 --explain --light` | Standard 티어 진입 + `pr-digest-standard.md` 생성(기존 동작 보존) | normal |
