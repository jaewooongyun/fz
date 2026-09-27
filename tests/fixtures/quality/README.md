# 합성 품질 fixture (S04)

리뷰·계획 스킬의 **품질을 재는 고정 입력**이다. A/B 원장(S05)과 규칙 추출 검증(R-B)이
이 폴더를 읽는다. 계약 검사기는
`scripts/check_quality_fixtures.py` 이고 health-check 가 돌린다.

⛔ 전부 **합성**이다(가상 앱 SampleTV·가상 주문 서비스). 실제 제품 코드를 넣지 않는다.

## 구성

| fixture | 종류 | 용도 |
|---|---|---|
| `review-ios-ribs` | review · ios | 6축(idiom·naming·architecture·ui_structure·placement·design_alternative) + critical·major 결함 |
| `review-nonios` | review · 비 iOS | 다른 아키텍처 규칙(헥사고날)에서 규칙 적용이 바뀌는가 |
| `rules-absent` | review · 지침 없음 | 지침 부재 시 규칙을 **지어내 적용하지 않는가**(AC-3) |
| `rules-conflict` | review · 지침 상충 | 상충 규칙을 **임의로 고르지 않고 드러내는가** |
| `plan-feature` | plan · 신규 기능 | Contracts·Roles·Stage·Adapters·State·Failure · Q1~Q8 · 10배 부하 · 의존성 장애 · 롤백 채점표 |
| `plan-removal` | plan · 제거 | 구조적 잔재·소비자 누락 채점표 |

## 규약

- `base/` = `main` 브랜치 전체 트리, `head/` = `feature` 브랜치에서 **바뀐 파일만**(덮어쓰기), `deleted.txt` = feature 에서 지울 경로
- 지침 파일(`CLAUDE.md`·`AGENTS.md` 등)은 **`*.fixture` 접미사로만** 둔다 — 이 플러그인 폴더에서 작업하는 세션이 fixture 지침을 자기 지침으로 자동 로드하지 않게 한다. `build-repo.sh DEST` 가 임시 저장소에 원래 이름으로 복원한다
- `labels.json`(review) — 정답 결함. 줄 번호는 `anchor` 코드 조각으로 생성기가 계산했고, 검사기는 그 줄이 **실제 diff hunk 안**에 있고 `anchor` 가 그 줄에 있는지 본다
- `rubric.json`(plan) — 채점 항목. 제거 fixture 는 잔재(`residues`)·소비자(`consumers`)가 base 에 실재하는지 검사한다
- `expected-index.json`(review 4종) — 지침 원문 색인 golden(S15). `check_project_rules.py --fixtures` 가 저장소를 복원해 `extract_project_rules.py` 출력과 구조로 비교한다. ⛔ 추출기 출력을 그대로 믿지 않고 heading 수(`grep`)와 quote 원문 포함을 따로 대조해 만들었다 — 고칠 때도 같은 대조를 다시 한다
- ⛔ 홈 절대경로·이메일 금지. 커밋 신원·날짜는 `_lib/build_repo.sh` 가 고정한다(같은 입력 → 같은 커밋 해시)
