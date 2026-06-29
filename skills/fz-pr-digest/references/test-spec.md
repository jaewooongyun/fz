# 테스트 케이스 (fz-pr-digest)

### Triggering Test

**should-trigger** (description '예:' 트리거 어휘 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "이 PR 뭐가 바뀐 거야?" | trigger | description '예: 뭐가 바뀐' — 핵심 유스케이스 |
| "PR #3394 설명해줘" | trigger | description '예: 설명해줘' |
| "이 변경사항 해설해줘" | trigger | description '예: 해설' |
| "이 PR 이해하고 싶어, 알려줘" | trigger | description '예: PR 이해' + intent-trigger '알려줘' |

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
