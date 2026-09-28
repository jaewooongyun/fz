# 프로젝트 규칙 — 런타임 추출 정본

> 대상 저장소의 지침(`CLAUDE.md`·`AGENTS.md` 등)에서 규칙을 뽑아 쓰는 절차의 **정본**이다. `skills/fz-plan/SKILL.md` 절차 1.5 는 이 문서를 가리킨다.
> 도구: `scripts/extract_project_rules.py`(원문 색인) · `scripts/check_project_rules.py`(검증 · 투영 · fixture 대조)

## 목차

- [1. 원문 색인과 해석을 나눈다](#1-원문-색인과-해석을-나눈다)
- [2. 절차](#2-절차)
- [3. 규칙 레코드](#3-규칙-레코드)
- [4. 축 6개와 archConstraints 투영](#4-축-6개와-archconstraints-투영)
- [5. 예시 판별 표지 — 검증기와 같은 정의](#5-예시-판별-표지--검증기와-같은-정의)
- [6. 검증기가 거부하는 것](#6-검증기가-거부하는-것)
- [7. 한계](#7-한계)

## 1. 원문 색인과 해석을 나눈다

추출기는 해석하지 않는다. 지침 파일의 heading 마다 원문을 그대로 낸다. 축에 매핑하고 규칙 레코드를 만드는 일은 모델이 **각자** 한다.

⛔ 해석된 규칙 JSON 을 Claude 와 GPT 가 공유하지 않는다. 한쪽의 오독이 다른 쪽의 전제가 되고(오류 전파), 뒤에 읽는 쪽이 앞의 해석에 앵커링된다. 두 모델이 공유하는 것은 원문 색인뿐이다.

## 2. 절차

1. **원문 색인** — `python3 "${FZ_PLUGIN_ROOT}/scripts/extract_project_rules.py" --project {대상 저장소} > {WORK_DIR}/rules/index.json`
   - 지침 파일은 이름이 `CLAUDE.md` · `CLAUDE.local.md` · `AGENTS.md` · `GEMINI.md` 인 파일(하위 폴더 포함)과 `.github/copilot-instructions.md` 다. `.git` · `node_modules` 같은 산출물 폴더는 건너뛴다
   - 지침이 없으면 `absent: true` 로 끝난다(exit 0). ⛔ exit 2 는 폴더를 읽지 못한 것이다 — 통과가 아니다
2. **규칙 레코드** — 모델이 색인(필요하면 코드)을 읽고 §3 형식으로 쓴다
3. **검증** — `python3 "${FZ_PLUGIN_ROOT}/scripts/check_project_rules.py" --check rules.json --index index.json --project {대상 저장소}`. **exit 0 인 레코드만** 쓴다
   - ⛔ exit 2 는 통과가 아니다. 관례 레코드(코드 인용)가 있는데 `--project` 를 주지 않으면 확인할 수 없어 exit 2 다
4. **투영(fz-plan)** — `--project-arch rules.json` 의 출력이 Workflow `args.archConstraints` 다(§4)
5. **상충** — `conflicts` 는 사용자에게 **'규칙 상충'** 항목으로 1회 보고한다. 자동 승자를 고르지 않는다. 현재 런타임을 판별할 결정론적 입력이 없어서, peer 지침 사이의 우선순위를 세울 근거가 없다

## 3. 규칙 레코드

```json
{
  "schemaVersion": 1,
  "axes": {"architecturePattern": "RIBs", "uiStack": null, "dependencyDirection": null,
           "naming": null, "placement": null, "conventions": null},
  "rules": [{
    "id": "R1", "axis": "naming", "authority": "지침",
    "appliesTo": {"languages": ["swift"], "modules": ["Watchlist"], "paths": ["Data/**"]},
    "condition": "서버 응답을 파싱하는 타입", "expectedResult": "`…DTO` 접미사",
    "source": {"file": "CLAUDE.md", "line": 8, "quote": "서버 응답을 파싱하는 타입은 `…DTO` 접미사를 쓴다"},
    "appliedTo": ["Data/Watchlist/WatchlistItemDTO.swift"]
  }],
  "conflicts": [{"axis": "naming", "claim_a": "…DTO", "claim_b": "…Response",
                 "sources": [{"file": "CLAUDE.md", "line": 5, "quote": "…"}, {"file": "AGENTS.md", "line": 5, "quote": "…"}]}],
  "gaps": ["uiStack", "dependencyDirection", "placement", "conventions"]
}
```

| 필드 | 뜻 |
|---|---|
| `authority` | `지침` · `관례` · `예시` 중 하나 |
| `appliesTo` | 적용 범위. `paths` 는 glob |
| `source` | 원문 그대로의 인용과 그 줄 |
| `appliedTo` | 이 규칙을 실제로 적용한 경로 |
| `gaps` | null 인 축 중 상충이 아닌 것 |

- `authority` — `지침` 은 지침 파일의 규칙 문장이다. `관례` 는 코드에서 관찰한 것이라 코드를 인용한다. `예시` 는 지침 속 예시다(§5)
- `appliesTo.languages` 는 파일 확장자로 판정한다. `modules` 는 기록만 하고 검증기가 보지 않는다
- `source.line` 은 인용문이 걸친 줄 중 하나여야 한다 — 맞는 문장이라도 다른 줄을 가리키면 거부된다
- `gaps` 는 Probe Coverage Gap 이다. 확인하지 못한 축을 조용히 비워 두지 않는다

## 4. 축 6개와 archConstraints 투영

축은 `architecturePattern` · `uiStack` · `dependencyDirection` · `naming` · `placement` · `conventions` 다.

앞 넷이 plan 워크플로(`workflows/plan-lean2.js` 등)가 읽는 `archConstraints` 다. 투영은 그 4축 값과 **그 4축의** `conflicts` 만 담는다. 그래서 워크플로 쪽 계약(4축 + conflicts)은 바뀌지 않는다 — `tests/workflows/arch-constraints-projection.js` 가 워커 프롬프트에 들어간 줄로 확인한다.

- 미확인 축은 `null` 이고 `gaps` 에 적는다
- 상충 축은 `null` 이고 `conflicts` 에 적는다. 값을 채우지 않는다

## 5. 예시 판별 표지 — 검증기와 같은 정의

예시를 지침으로 올리면 한 번 보인 예가 규칙이 된다. 아래 구간 안의 인용은 `authority: 예시` 여야 한다.

판별은 **구간 단위**다. 줄 전체를 인용하면 지침이고, 괄호 속 예시만 인용하면 예시다.

| 표지 | 예시 구간 |
|---|---|
| heading 에 `예시` · `Example(s)` | 그 절과 하위 절 본문 전체 |
| 코드 펜스(```` ``` ```` · `~~~`) | 펜스 안 전체 |
| 괄호 표지 | `(예: …)` 등 괄호 한 쌍 |
| 줄 앞 표지 | 표지부터 줄 끝까지 |

- 괄호 표지는 괄호 안이 `예` · `예시` · `e.g.` · `eg.` · `Example` · `For example` 로 시작하는 한 쌍이다. 뒤에 `:` · `,` · `)` 가 와도 된다(`(예: …)` · `(예) …)` · `(예시: …)` · `(e.g. …)` · `(Example: …)`), 단독 `(예)` · `(예시)` 도 표지다. ⛔ `예` · `예시` 바로 뒤에 다른 한글 음절이 오면 표지가 아니다 — `(예외: …)` · `(예약 …)`
- `## Examples` 아래의 `### Good` 처럼, 조상 heading 이 예시 절이면 하위 절도 예시 구간이다
- 펜스는 여는 줄과 같은 문자로, 같거나 더 긴 표지가 홀로 선 줄에서만 닫힌다 — 네 백틱 펜스 안의 세 백틱 줄은 펜스를 닫지 않는다. 추출기가 펜스 안 `#` 줄을 heading 으로 보지 않을 때도 같은 규칙을 쓴다
- 줄 앞 표지는 `예:` · `예)` · `예시:` · `예시)` · `e.g.` · `Example:` · `For example` 이고, 목록 기호(`-` · `*` · `1.`) 뒤에 와도 된다
- ⛔ 이 목록을 고치면 `scripts/check_project_rules.py` 의 `EX_*` 정규식을 같이 고친다 — 두 모델이 다른 정의로 판별하면 같은 레코드가 한쪽에서만 통과한다

## 6. 검증기가 거부하는 것

| 코드 | 무엇 |
|---|---|
| V1 | 지어낸 인용 |
| V2 | 상충 축에 값이 있다 |
| V3 | 지침이 없는데 지침 레코드 |
| V4 | 출처가 비었다 |
| V5 | 예시를 지침으로 올렸다 |
| V6 | appliesTo 밖에 적용했다 |
| S | 스키마 위반 |

- V1 은 인용문이 인용한 파일에 없거나, 있어도 인용한 줄을 덮지 않는 경우다
- V3 은 색인이 `absent` 인데 지침·예시 레코드가 있거나, 지침·예시 레코드가 지침 파일 밖을 인용하는 경우다
- V4 는 `source` 의 file · line · quote 중 하나라도 빈 경우다
- V5 는 인용이 전부 §5 의 예시 구간 안인데 `authority: 지침` 인 경우다
- V6 은 `appliedTo` 경로가 `appliesTo.paths` 의 glob 이나 `languages` 의 확장자에 맞지 않는 경우다
- S 는 authority·axis 가 목록 밖이거나, 축 값에 근거 레코드가 없거나, null 축이 `gaps`·`conflicts` 어디에도 없는 경우다

## 7. 한계

- setext heading(`===` · `---` 밑줄)은 heading 으로 보지 않는다
- 하위 폴더의 지침 파일이 그 폴더에만 적용된다는 범위는 검증기가 보지 않는다 — 레코드의 `appliesTo.paths` 로 적는다
- 예시 표지는 §5 목록만 본다. 목록 밖 표현("…처럼", "like …")은 잡지 않는다
