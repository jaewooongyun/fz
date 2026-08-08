# 테스트 케이스 (fz-peer-review)

> 근거: `guides/skill-testing.md` §1(3단계 프레임워크)·§4(test-spec 템플릿). 트리거 어휘는 description '예:'/'비사용:' + `intent-triggers`, Functional oracle은 본 스킬의 Phase(Gather→Analyze→Challenge→Synthesize→Deliver)·Gate 5.5·Synthesize 투표/Origin 보정·CHECKPOINT·에러 대응에서 도출.

### Triggering Test

| 쿼리 | 예상 | 비고 (근거 / redirect) |
|------|------|----------------------|
| "팀원 PR 리뷰해줘" | trigger | description '예:' 핵심 유스케이스 |
| "이거 피어리뷰 좀 해줘" | trigger | description '예:' (피어리뷰) + intent-trigger `피어리뷰` |
| "이 PR 검토해줘" | trigger | description '예:' (PR 검토) |
| "동료가 올린 PR 리뷰 부탁해" | trigger | intent-trigger `팀원\|PR.*리뷰` (동료=팀원) |
| "내가 방금 작성한 코드 리뷰해줘" | NOT trigger | → fz-review (description '비사용: 자기 코드', Will Not '자기 코드 리뷰') |
| "이 PR 변경 내용 해설해줘" | NOT trigger | → fz-pr-digest (description '비사용: PR 해설') |
| "codex로 이 변경 교차검증해줘" | NOT trigger | → fz-codex (Will Not 'Codex 위임 → /fz-codex') |
| "이 PR의 버그 직접 고쳐줘" | NOT trigger | → fz-fix (Will Not '코드를 직접 수정하지 않음, 리뷰만 수행') |

### Functional Test (Given/When/Then)

| Given | When | Then (pass/fail oracle) | 유형 |
|-------|------|------------------------|------|
| PR 번호 입력, `gh auth status` 성공, 표준 규모 diff | `/fz-peer-review 123` | Gate 5.5 통과(`tier.txt` 기록) 후 Synthesize CHECKPOINT 3파일(`synthesized-issues.json`·`confidence-matrix.md`·`review-index.md`) + Deliver CHECKPOINT 2파일(`review-report.md`·`pr-comments.md`) 모두 Write 완료 = pass | normal |
| 변경 13줄 소규모 PR, `--tier` 미지정 | `/fz-peer-review 45` | Gate 5.5에서 auto Tier 0 결정 → `tier.txt == "0"` 기록 + 팀 미생성(Lead 단독 분석, TeamCreate 호출 0회) = pass | normal |
| 지적 패턴이 base 브랜치에 이미 존재(`base-behavior.md`상 pre-existing), 에이전트가 `origin=pre-existing` 보고 | `/fz-peer-review 123` | Synthesize Origin 보정으로 해당 이슈 severity가 `suggestion`으로 cap + Confidence Matrix Origin 열 `P` + 리포트 `[기존 동작 동일]` 태그 부착 = pass | edge-case |
| `gh auth status` 실패 | `/fz-peer-review 123` | git 폴백 경로(`git fetch upstream` + `git diff`)로 `${WORK_DIR}/diff.patch` 생성(비어있지 않음) → 리뷰 파이프라인 계속 진행 = pass | failure |
| Tier 2 결정, Codex challenger 호출 실패 | `/fz-peer-review 123` | 2-agent 투표 모드로 전환(review-arch + review-quality만, Codex 투표 제외) → Confidence Matrix 계산 완료 + 최종 verdict 산출(리뷰 비중단) = pass | failure |
| Tier 3 실행, suggestion 등급 이슈 존재 | `/fz-peer-review 123 --deep` | 반환 `distribution.suggestion` 이 실제 suggestion 이슈 수와 일치 + log에 표기 = pass (H24 회귀 방어) | normal |

---

## 인라인 앵커 계산 (`skills/fz-peer-review/scripts/diff_anchors.py`)

> 근거: `guides/skill-authoring.md` §11 — "결과가 binary(pass/fail)인가? → 스크립트". 앵커 가능 여부는 binary이므로 언어 지시가 아닌 스크립트가 판정한다.
> fixture: `skills/fz-peer-review/references/fixtures/pr4655-sample.patch` (PR #4655 축약본 — 3파일 26 hunk). ⛔ 플러그인 **안**에 둔다 — 외부 폴더는 정리되면 테스트가 깨진다.

### I/O 계약

```
$ python3 skills/fz-peer-review/scripts/diff_anchors.py --diff <patch> --targets '<json>'

targets: [{"path": "<파일 경로 또는 basename>", "start": <int>, "end": <int>,
           "side": "RIGHT|LEFT"   // 생략 시 RIGHT
          }, ...]

stdout (JSON):
{
  "anchorable":     [{"path","side","start_line","line","hunk_start","hunk_end"}, ...],
  "non_anchorable": [{"path","start","end","side","reason"}, ...]
}
exit 0 = 계산 성공 (앵커 0건이어도 0) / exit 1 = 입력 오류
```

- **좌표계는 `side`가 결정한다** — `RIGHT`=diff 신규(`+`) 측, `LEFT`=변경 전(`-`) 측. GitHub `start_line`/`line`이 쓰는 좌표계와 동일
- **겹치는 hunk를 모두 반환한다.** 어느 hunk가 논지인지는 **의미 판단**이지 binary가 아니므로 스크립트가 고르지 않는다 (선택은 Lead)
- `path`는 정확 일치 우선, 없으면 **유일한 suffix 일치**. `a/`·`b/` prefix와 Git quoted path(`"b/dir/file name.txt"`)를 해제한다
- `reason` 4종: `outside_diff`(그 side에 hunk는 있으나 구간 밖) · `no_hunks_on_side`(그 side에 hunk 자체 없음 — 신규 파일의 LEFT 등) · `path_not_in_diff` · `ambiguous_path`
- 파싱은 **`diff --git` 경계 상태 머신**이다 — 헤더 판정만 쓰면 diff 본문에 든 `+++ b/…` 추가 라인(패치 파일을 리뷰할 때 발생)이 파일 경계를 오염시킨다

### Functional Test (fixture 기준 — 실측 검증됨)

| # | Given (targets) | Then (oracle) | 유형 |
|---|-----------------|---------------|------|
| A1 | `ShortsChainView.swift` 423–439 | `anchorable` **2건** — `423–428`(hunk 420–428) + `431–439`(hunk 431–440). ⛔ 한쪽만 반환하면 fail | normal |
| A2 | `ShortsPlayerContext.swift` 122–140 | `anchorable` 0건 + `non_anchorable` 1건(`reason=outside_diff`). 이 파일 hunk는 14–20·30–36뿐 | edge-case |
| A3 | `ShortsCore.swift` 1484–1513 | `anchorable` **1건** — `1484–1513`(hunk 1482–1521 내부에 완전 포함) | normal |
| A4 | 존재하지 않는 경로 `NoSuchFile.swift` 1–10 | `non_anchorable` 1건(`reason=path_not_in_diff`) — 예외 없이 종료(exit 0) | failure |
| A5 | `start > end` 인 입력 | exit 1 + **stdout 부분 출력 0바이트**(사유는 stderr) | failure |
| **A6** | `ShortsCore.swift` 1484–1513 (side 생략) | `anchorable[0].side == "RIGHT"` — 기본값 | normal |
| **A7** | `ShortsCore.swift` 1451–1470 `side=LEFT` | `anchorable` 1건 `LEFT:1451–1470` — 변경 전 좌표계로 계산 | normal |
| **A8** | hunk 본문에 `+++ b/fake.txt` 추가 라인이 있는 diff → `real.txt` 조회 | `real.txt`의 hunk가 유지되고 `fake.txt`는 **미등록**(`path_not_in_diff`). ⛔ 오귀속되면 엉뚱한 파일에 코멘트가 달린다 | failure |
| **A9** | `"b/dir/file name.txt"` quoted path diff → `dir/file name.txt` 조회 | `anchorable` 1건 — quote 해제 | edge-case |
| **A10** | 신규 파일(`--- /dev/null`)에 `side=LEFT` · `side` 값이 `UP` | 전자 `reason=no_hunks_on_side` / 후자 **exit 1** | failure |

### 구현 제약 (검증 가능)

| 제약 | oracle |
|------|--------|
| **Python 표준 라이브러리 전용** | `grep -E '^\s*(import\|from)' skills/fz-peer-review/scripts/diff_anchors.py` 결과가 stdlib만. 외부 패키지·외부 CLI 호출 0건 |
| 문법 유효 | `python3 -c "import ast; ast.parse(open('skills/fz-peer-review/scripts/diff_anchors.py').read())"` exit 0 |

> **⛔ 외부 의존 금지 근거**: 같은 레포의 `skills/fz-modernize/scripts/ac8-link-check.sh:29`가 `rg`(ripgrep)에 하드 의존하는데 미설치 환경에서 `exit 127`로 **실행 자체가 안 된다** (의존성 guard·폴백 부재). 같은 실패를 반복하지 않는다.
