# Tier 2 병합 계약 회귀 fixture

`workflows/peer-review.js` Tier 2 경로의 **Lead 병합 결과**를 고정한 회귀 자료다.

## 무엇을 고정하는가

Stage 1 3-렌즈가 낸 원본 findings 24건이 최종 14건으로 병합된 실행 하나를 담았다. 병합 계약을 바꿀 때 이 입력을 넣어 **같은 disposition이 나오는지** 확인한다.

| 파일 | 내용 |
|---|---|
| `stage1-input.json` | 3-렌즈 원본 24건 — `id` · `severity` · `perspective` · `origin` · `confidence` |
| `expected-output.json` | 병합 후 14건 — `votes` · `basis` · `found_by` · `codex_verdict` 포함 |

## 왜 판정 필드만 있는가

원본에는 결함 설명·증거 인용·수정 제안이 들어 있었다. 전부 제거했다. 병합 계약이 판정하는 것은 **어떤 findings가 어떤 근거로 살아남는가**이지 그 내용이 아니다.

파일명은 `SourceFile{N}.ext`로 치환했다. dedup 키가 `파일 + line_range 겹침`이므로 **동일 파일 여부와 범위 구조는 보존**했고 실제 경로만 지웠다.

`codex_verdict`도 자유 문장에서 종류(`agree` · `challenge` · `reverse` · `supplement`)만 남겼다.

## 이 실행이 대표하는 것

⛔ 이 fixture는 **정상 동작의 기준이 아니다.** 오히려 계약 부재를 드러낸 실행이다.

- 렌즈 하나만 찾은 findings 3건이 투표 산식상 전멸해야 했으나, Lead가 문서에 없는 예외를 즉석에서 만들어 살렸다
- 렌즈가 하나도 못 찾고 Lead가 직접 발굴한 항목이 2건 있다
- 즉 최종 14건 중 5건이 **문서화되지 않은 판단**에 의존한다

⭐ 그래서 병합 계약을 세울 때 이 다섯 건이 **정식 경로로** 살아남는지가 acceptance다. 계약을 넣었더니 이들이 탈락한다면 개선이 아니라 회귀다.

## 알려진 오염

`I1` 계열은 Lead가 분석 지시에 구체적 후보 목록을 적어 넣었고 렌즈들이 같은 목록을 돌려준 항목이다. `votes.seeded: true`로 표시했다.

⛔ **이 항목을 정답으로 굳히지 말 것.** 병합 계약은 seed와 겹치는 findings를 독립 코드 증거 없이 `include`로 올리면 안 된다. 원 실행도 이 항목의 영향 범위를 미판정으로 남겼다.

## 사용

```
입력  stage1-input.json  →  병합 계약 적용  →  expected-output.json 과 대조
```

대조 대상: 최종 건수 · 각 항목의 `id`·`severity`·`origin` · `votes.count` · `codex_verdict`.

⚠️ `confidence` 값은 Lead 판정이 반영된 결과라 계약 구현이 달라지면 바뀔 수 있다. 값 자체보다 **어떤 항목이 살아남았는가**를 먼저 본다.
