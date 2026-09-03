# Peer Review — 인라인 앵커 게시

> `skills/fz-peer-review/SKILL.md` Deliver 단계에서 참조. `--post` 시 발동.
> 발견을 PR 대화창이 아니라 **코드 라인 옆**(Files changed 탭)에 붙여, 리뷰어가 코드를 보면서 지적을 읽게 한다.

## 목차

- [1. 왜 인라인인가](#1-왜-인라인인가)
- [2. 사전 조건](#2-사전-조건)
- [3. 게시 7단계](#3-게시-7단계)
- [4. 게시 전 확인 게이트](#4-게시-전-확인-게이트)
- [5. 앵커 불가 항목 처리](#5-앵커-불가-항목-처리)
- [6. 다지점 결함 분할](#6-다지점-결함-분할-ssot)
- [7. 실패 대응](#7-실패-대응)
- [8. Few-shot](#8-few-shot)

---

## 1. 왜 인라인인가

GitHub에는 코멘트를 다는 자리가 둘이다.

```
① PR 대화창 (Conversation)     — gh pr comment. 한 덩어리. 코드가 안 보인다
② 코드 라인 옆 (Files changed) — 그 줄이 하이라이트되고 코드와 나란히 보인다
```

①만 쓰면 리포트에 `PlayerCore.swift:1484-1513`이라 적어도 리뷰어가 **직접 파일을 열어 그 줄을 찾아가야** 한다. 지적의 근거가 코드인데 코드에서 멀어지면 확인 비용이 리뷰어에게 전가된다.

## 2. 사전 조건

| 항목 | 확인 |
|------|------|
| `gh auth status` | 실패 시 게시 불가 — 리포트 파일 산출까지만 하고 사용자에게 안내 |
| PR head SHA | `gh pr view {N} --json headRefOid -q .headRefOid` → payload `commit_id` |
| diff 파일 | Gather에서 만든 `${WORK_DIR}/diff.patch` |

## 3. 게시 7단계

```
1. 앵커 계산   skills/fz-peer-review/scripts/diff_anchors.py 실행
2. 구간 선택   겹치는 hunk가 복수면 Lead가 논지 구간을 고른다 (의미 판단)
3. 대체 처리   non_anchorable → 본문 코드 인용 (5절)
4. payload 조립
5. 확인 게이트 (4절 — 조건 해당 시에만 차단)
6. 게시 실행
7. 착지 검증
```

### 1) 앵커 계산

```bash
python3 skills/fz-peer-review/scripts/diff_anchors.py \
  --diff "${WORK_DIR}/diff.patch" \
  --targets '[{"path":"PlayerCore.swift","start":1484,"end":1513,"side":"RIGHT"},
              {"path":"Old.swift","start":40,"end":52,"side":"LEFT"}]'
```

반환은 `anchorable[]`(각 항목에 `side` 포함) + `non_anchorable[]`.

- `side`는 target마다 지정한다. **생략 시 `RIGHT`**(변경 후 코드). 삭제된 코드를 지적하려면 `LEFT`
- `non_anchorable[].reason`: `outside_diff`(해당 side에 hunk는 있으나 구간이 밖) · `no_hunks_on_side`(그 side에 hunk 자체가 없음 — 예: 신규 파일의 LEFT) · `path_not_in_diff` · `ambiguous_path`

계약과 테스트 케이스: `skills/fz-peer-review/references/test-spec.md` "인라인 앵커 계산"

### 2) 구간 선택 — 스크립트가 고르지 않는 이유

GitHub는 `start_line`~`line`이 **같은 hunk 안**일 것을 요구한다. 지적 구간이 hunk 경계를 넘으면 스크립트는 겹치는 후보를 **모두** 돌려준다.

```
지적:  ChainView.swift 423-439
hunk:  420-428 / 431-440        ← 429-430이 미변경이라 갈라짐
반환:  [423-428, 431-439]        ← 둘 다
```

어느 쪽이 논지인지는 코드 의미 판단이라 Lead가 고른다. 스크립트가 임의로 첫 구간을 고르면 논지와 다른 줄에 코멘트가 달린다.

### 4) payload 조립

```json
{
  "commit_id": "<PR head SHA>",
  "event": "COMMENT",
  "body": "<review-report.md 전문>",
  "comments": [
    { "path": "Packages/.../PlayerCore.swift",
      "start_line": 1484, "start_side": "RIGHT",
      "line": 1513,       "side": "RIGHT",
      "body": "<이슈 본문 — pr-comments.md 톤>" },

    { "path": "Packages/.../PlayerCore.swift",
      "line": 83, "side": "RIGHT",
      "body": "<단일 줄은 start_* 생략>" }
  ]
}
```

⛔ **다중 라인은 `start_side`가 짝으로 필요하다.** `start_line`만 넣고 `start_side`를 빠뜨리면 HTTP 422로 **리뷰 전체가 게시되지 않는다**.

| 형태 | 넣을 필드 |
|------|----------|
| 다중 라인 | `start_line` + `start_side` + `line` + `side` (**4개 모두**) |
| 단일 줄 | `line` + `side` (⛔ `start_line`·`start_side` **생략**) |

- `side`/`start_side`: `RIGHT`=변경 후 / `LEFT`=변경 전(삭제된 코드 지적)
- 스크립트가 `side`를 그대로 돌려주므로 `anchorable[].side`를 두 필드에 함께 넣는다 (한 구간이 side를 섞을 수는 없다)

> ⛔ **top-level `body`에는 `review-report.md` 전문을 넣는다** — 요약이 아니다. 인라인 전환 이전의 `--post`는 `gh pr comment`로 리포트 전문을 대화창에 올렸다. 인라인만 달고 `body`를 요약으로 줄이면 **Confidence Matrix(생성 경로는 `modules/peer-review-gates.md` § MergeContract § 9)·origin 보정 근거·긍정적 측면이 PR에서 사라지는 회귀**가 된다. 리뷰 body는 리뷰 헤더로 남으므로 전문을 담기에 적절하다(GitHub 상한 65,536자 — 초과 시에만 Matrix(있는 경로에 한한다)를 남기고 이슈 상세를 인라인에 위임).

### 6) 게시 실행

```bash
gh api repos/{owner}/{repo}/pulls/{N}/reviews -X POST --input payload.json
```

> ⛔ `SKILL.md` frontmatter `allowed-tools`에 **`Bash(gh *)`가 필요**하다. 플러그인 내 다른 스킬은 이를 선언하지 않지만, 이 경로는 `mcp__github__create_pull_request_review`로 대체 불가하다 — 그 MCP 도구의 `comments[]`는 `{path,line,body}` / `{path,position,body}` 두 형태뿐이라 **`start_line`·`side`가 없어 범위 하이라이트와 LEFT 앵커가 불가능**하다.

### 7) 착지 검증 — ⛔ **방금 만든 리뷰만** 대조한다

게시했다고 원하는 줄에 달린 것은 아니다. 재조회해서 대조하되, **PR 전체 코멘트를 조회하면 안 된다** — 기존 코멘트를 새 것으로 오인하고, 실패 시 삭제 대상도 특정할 수 없다(PR는 이미 39건이 있었다).

```bash
# 6단계 POST 응답에서 review id를 잡아 둔다
REVIEW_ID=$(gh api repos/{owner}/{repo}/pulls/{N}/reviews -X POST \
              --input payload.json --jq '.id')

# 그 리뷰에 속한 코멘트만 조회 (pagination 명시)
gh api --paginate "repos/{owner}/{repo}/pulls/{N}/reviews/${REVIEW_ID}/comments" \
  --jq '.[] | {id, path, start_line, start_side, line, side, body}'
```

대조 항목: payload의 각 항목과 **`path`·`start_line`·`start_side`·`line`·`side`가 정확히 일치**하는지, 개수가 같은지. 불일치한 코멘트는 조회로 얻은 `id`로 삭제한다(`gh api -X DELETE repos/{o}/{r}/pulls/comments/{id}`).

## 4. 게시 전 확인 게이트

**미리보기는 항상 출력한다** — 어느 파일 어느 줄에 몇 건이 달릴지, event 종류, 본문 인용으로 대체된 항목. 여기에는 승인 요구가 붙지 않는다.

**아래 셋 중 하나라도 해당하면 AskUserQuestion으로 승인받은 뒤 게시한다.**

| # | 조건 | 이유 |
|---|------|------|
| (a) | `event ≠ COMMENT` | `REQUEST_CHANGES`는 **머지 블로킹**, `APPROVE`는 승인 행위. `--post`가 위임한 범위를 넘는다 |
| (b) | `non_anchorable`이 있어 본문 인용으로 대체됨 | 지적이 사용자가 기대한 위치에 안 달린다 |
| (c) | 겹치는 hunk가 복수여서 Lead가 구간을 골랐음 | 선택이 논지와 다를 수 있다. 어느 구간을 왜 골랐는지 보여준다 |

원칙: `--post`는 **"COMMENT를 단다"는 승인**이다. 그 범위 안이면 확인 없이 진행하고, 넘어서는 결과만 되묻는다.

| event | 결과 |
|-------|------|
| `COMMENT` | 의견만. 머지를 막지 않음 |
| `REQUEST_CHANGES` | 변경 요청. **머지 블로킹** |
| `APPROVE` | 승인 |

## 5. 앵커 불가 항목 처리

diff 밖(변경되지 않은 줄)은 인라인이 **불가능**하다. 그 지적은 **관련 코멘트 본문에 코드블록으로 인용**하고 출처를 `file:line`으로 밝힌다.

````markdown
관련 코드가 이 PR의 diff 밖이라 인라인으로 달지 못해 인용합니다.

`PlayerContext.swift:122-140`
```swift
// 해당 코드
```
````

> **파일 단위 코멘트를 쓰지 않는 이유**: `subject_type: "file"`은 `POST /pulls/{N}/comments`(개별 코멘트 생성) 전용이고, 우리가 쓰는 `POST /pulls/{N}/reviews`의 `comments[]`에는 **없다**. 별도 엔드포인트로 2차 호출하면 PR 타임라인이 "리뷰 1건 + 독립 코멘트 N건"으로 갈라지고, 부분 실패 시 절반만 게시된 상태가 남는다. 리뷰는 한 건으로 유지한다.

## 6. 다지점 결함 분할 (SSOT)

> 결함 하나가 여러 파일에 걸칠 때의 분할 규칙은 **이 절이 단일 출처**다. 서술 형태 문서는 이 절을 가리키기만 한다.

결함 하나가 N개 지점에 걸치면 `[1/N]…[N/N]`으로 나눠 **각 지점에 따로 앵커**하고, 본문에서 서로를 참조한다.

```
[1/4] PlayerCore.swift:1484        — 자동 전환 트리거. → [2/4]에서 취소됨
[2/4] ShortFormPlayerTemp.swift:349 — 취소 지점
[3/4] ChainView.swift:423    — 복구 경로 부재 ①
[4/4] ShortFormPlayerControllerTemp.swift:353 — 복구 경로 부재 ②
```

- 번호는 **인과 순서**를 따른다(발생 → 전파 → 결과). 파일 알파벳 순이 아니다
- 각 조각이 자기 지점의 코드만으로 읽히게 쓰되, 전체 논지는 `[1/N]`에 둔다
- 지점이 2개면 분할하지 않고 한 코멘트에 다른 지점을 인용한다 — 분할 자체가 비용이다

## 7. 실패 대응

| 증상 | 원인 | 대응 |
|------|------|------|
| HTTP 422 `line must be part of the diff` | 앵커 대상이 diff 밖 | 스크립트가 사전에 걸러야 한다. 발생 시 해당 항목을 `non_anchorable`로 되돌리고 5절 처리 |
| HTTP 422 `start_line must be part of the same hunk` | 구간이 hunk 경계를 넘음 | 2절 재수행 — 후보 중 하나를 고른다 |
| HTTP 404 | `commit_id`가 PR head와 불일치 | head SHA 재조회 후 재시도 |
| `gh: command not found` | gh CLI 미설치 | 게시 중단. 리포트 파일 경로만 안내 |

## 8. Few-shot

```
BAD: 지적 구간 423-439를 그대로 payload에 넣는다
     → 429-430이 미변경이라 hunk가 갈라져 있음 → HTTP 422 → 게시 전체 실패

GOOD: diff_anchors.py → [423-428, 431-439] 두 후보 확인
     → 논지(조기 return 3종)는 423-428 → 그 구간으로 앵커
     → 겹치는 hunk 복수였으므로 확인 게이트 (c) 발동 → 선택 근거와 함께 사용자 확인
```

```
BAD: 게시 후 "달렸습니다" 보고
     → 엉뚱한 줄에 달렸어도 모른다

GOOD: POST 응답의 review id 캡처 → /pulls/{N}/reviews/{id}/comments 조회 → payload와 필드 대조
     (⛔ /pulls/{N}/comments 전체 조회 금지 — 기존 코멘트와 구분 불가)
     → 불일치 발견 시 해당 코멘트 삭제 후 재게시
```

```
BAD: diff 밖 지적을 인라인으로 시도 → 422 → 리뷰 전체 게시 실패
GOOD: non_anchorable로 분류 → 관련 코멘트 본문에 코드블록 인용 + 출처 명시
     → 확인 게이트 (b) 발동 → 대체 처리된 항목을 사용자에게 보여준 뒤 게시
```
