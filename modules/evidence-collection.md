# Code Evidence Collection

> Gather Phase에서 에이전트에게 전달할 실제 코드를 수집하는 모듈.
> 에이전트는 Bash/git show 접근 불가이므로 Orchestrator가 사전 수집한다.
> PR #3639 교훈: diff만으로는 producer site, 삭제 심볼 잔존 여부를 확인할 수 없어 추론→환각→오탐 발생.

## 산출물 경로

```
${WORK_DIR}/evidence/
├── old-new-pairs.md         — 변경 함수의 before/after 코드
├── producer-consumer.md     — enum/struct의 생성-소비 매핑
├── deletion-verification.md — 삭제 심볼의 잔존 참조 확인
└── base-patterns.md         — regression 판정용 base 코드 패턴
```

## 수집 절차

```bash
mkdir -p ${WORK_DIR}/evidence
```

### a. 변경 함수의 old/new 코드 페어 → `evidence/old-new-pairs.md`

diff hunk에서 변경된 함수/메서드 식별 (최대 20개, diff 크기 비례).
각 함수에 대해:

```
git show upstream/${BASE_BRANCH}:${FILE} | 해당 함수 추출  → ## OLD
git show pr-${PR_NUMBER}:${FILE} | 해당 함수 추출           → ## NEW
```

함수당 최대 50줄, 총 최대 1000줄 제한.

### b. Producer/Consumer 매핑 → `evidence/producer-consumer.md`

diff에서 아래 패턴 감지 시 producer site 수집:
- enum case destructuring에서 `_` 사용 → throw/init site의 실제 값 수집
- 파라미터 이름 변경/제거 → 생성 site에서 해당 값의 출처 확인
- 콜백/클로저 이동 (old: cancelCallback → new: onConfirm) → 1:1 매핑 기록

형식:

| Consumer (file:line) | Pattern | Producer (file:line) | Actual Value |
|---------------------|---------|---------------------|-------------|

### c. 삭제 대상 잔존 참조 확인 → `evidence/deletion-verification.md`

diff에서 삭제된 파일/심볼 목록 추출. 각 심볼에 대해:

```bash
git grep {symbol} pr-${PR_NUMBER} -- '*.swift' '*.m' '*.h'
```

형식:

| Symbol | Deleted In | Remaining References | Count |
|--------|-----------|---------------------|-------|

Count == 0이면 "✅ 완전 제거", > 0이면 "⚠️ 잔존 {N}건"

### d. regression 이슈 base 비교용 → `evidence/base-patterns.md`

에이전트가 regression으로 판정할 가능성이 높은 변경 패턴:
- guard/validation 제거 → base에서 동일 guard 존재 여부
- void return (silent failure) → base에서도 동일 패턴 존재 여부
- withCheckedContinuation + callback → base의 동일 함수 전체 코드

형식:

| Pattern | Base Code (file:line) | PR Code (file:line) | Same? |
|---------|---------------------|--------------------|----|

---

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-peer-review | Gather Phase 2.6에서 호출 |
| modules/peer-review-gates.md | Gate 4.4, 4.7-A에서 evidence 파일 소비 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
