# fz-peer-review 근거 · 이력

> SKILL.md 에서 옮긴 근거 · 이력 · 사례 문단이다(B1 · 2026-11-01). 실행 규칙은 SKILL.md 에 남아 있다 — 이 파일은 왜 그 규칙인지를 설명한다.

## --deep 이 두 축을 켜는 이력

`--deep`은 두 축을 동시에 켠다(리뷰 Cross-Critique + 해설 Deep). 기존 배선이며 변경하지 않았다.

## WORK_DIR 을 먼저 정하는 이유

WORK_DIR이 없으면 이후 모든 산출물 저장이 실패한다. Gather 시작 시 반드시 첫 번째로 실행.

## 이동 드리프트

산출: `diff.patch` · `requirements.md` · `base-behavior.md` + `base/` · `head/`(GPT 독립 첫 패스 입력) · `base-manifest.tsv` · **`review-surface.md`** · `numstat.txt` · `risk.json`

⭐ 이동 리팩토링(신규 파일 + 그만큼의 삭제)이면 **`evidence-move-drift.md`** 가 함께 나온다 — ⛔ **동등성과 별개 축**이다. 다중집합 차가 "값 표현식 변화 0" 을 보여도 이동이 만든 문서·구조 드리프트는 거기 없다(실측 #4774: 동등성 통과 후 단독 리뷰 0건 · 3렌즈가 regression 3건).

## 리뷰 표면 진단

⛔ **`review-surface.md` 를 먼저 읽는다.** base 가 분기점보다 앞서 있으면 이미 base 에 있는 커밋이 diff 에 다시 나타나 Tier 와 리뷰 표면이 함께 부풀려진다(실측 #4766: 2.9배). `git cherry` 의 `-` 커밋은 대상에서 빼고 Tier 를 재계산한다. 상세·한계: `modules/peer-review-tiers.md` § 리뷰 표면 진단

⛔ **읽고 끝내지 않는다 — `review-surface.patch` 를 `reviewSurfacePatchPath` 로 넘긴다.** 진단 파일(`review-surface.md`)만 넘기면 무력하다: 렌즈는 Bash·git 이 없어 커밋 해시로 hunk 를 필터할 수 없다. gather 가 중복 커밋을 제외한 patch 를 함께 만들므로 그것이 1차 리뷰 대상이고 전량 `diffPath` 는 부풀림 확인용 보조다 (`modules/peer-review-workflow.md` 절차 1).

## 증상 미확정

⛔ **"코드로 확정할 수 없다" 는 두 가지다** [F-285 — `major` 6건 전부 철회]. ①배선 미확정(`A→B→C` 를 grep 으로 못 잡음)은 이 규칙이 잡지만, ②**증상 미확정**(배선은 확정되는데 그 귀결이 사용자에게 **무엇으로 보이는지**가 코드에 없음)은 통째로 게이트 밖이다. 배선을 끝까지 따라가면 주장 전체가 확정된 느낌이 들어 oracle 을 적을 필요를 못 느낀다 — 실측 6건이 전부 ②였고, 배선 4단계가 모두 사실인데 **그 값을 그리는 화면이 그 시점에 계층에 없었다**.

⛔ 따라서 `severity` 가 `minor` 이상이면 **증상 관측 지점** 두 칸을 채운다. 비면 `suggestion` 강등 (Gate 4.7-S 가 기계 판정): `symptom_screen` = 증상이 보이는 구체 화면·뷰 이름 / `symptom_reach` = 그 화면이 그 상태로 떠 있게 되는 사용자 동작. ⛔ `화면` 칸은 "값이 흐른다" 가 아니라 **"그 값을 그리는 뷰가 그 시점에 계층에 있는가"** 를 묻는다.

## Orchestrator 가 코드를 수집하는 이유

>
> 에이전트는 Bash/git show 접근 불가. Orchestrator가 사전에 실제 코드를 수집하여 에이전트에게 데이터로 전달한다.

## 선언부만 보고 판단한 관측 사례

>
> ⛔ init/DI 패턴 변경이 있는 PR에서 필수. "선언부만 보고 판단" 방지.
> 관측 사례: 선언부가 깔끔해도 caller 가 더러우면 의미가 없다. convention 패턴을 위반으로 지적하면 안 된다.

## 브리프 추정이 사실로 굳은 관측 사례

> 관측 사례: Lead가 "이 값은 서버가 준다"는 추정을 브리프에 적었고 렌즈 2/3이 그것을 사실로 받아 오탐을 냈다. 실제로는 클라이언트 하드코딩이었다.
> 다른 사례: Lead가 영향 범위 후보를 목록으로 적어 넣자 렌즈 둘이 **같은 목록을 되돌려줬다**. 3렌즈 합의처럼 보이지만 독립 확증이 아니다.

## 결측 에이전트

Lead 보정 **불필요** — `peer-review.js`가 `reviews`를 `.filter(Boolean)`으로 구성해 실패 에이전트는 이미 빠져 있고, `PeerReviewSchema`에 `agent_status`가 없어 `partial`은 표현되지 않는다. Lead가 볼 것은 `reviews.length`뿐 — ⛔ 스크립트는 **전부 null일 때만** fallback을 반환하므로(`peer-review.js`의 `reason: 'stage1 all null'` 분기) 1-review 경로가 실재한다:
3 → 3-vote / 2 → 2-vote 모드(§3) / **1 → 투표 불가. 단독 렌즈 결과이므로 Confidence Matrix를 만들지 않고 `[단일 렌즈 — 교차검증 없음]` 태그와 함께 보고하며, 이슈 confidence는 ×0.7 감쇠** / 0 → `mode:'fallback'`(Tier 하위 전환) — ⛔ 이 투표 산식은 Tier 3 기준이다(`modules/peer-review-gates.md` § MergeContract § 9)

## 파일로 영속화하는 이유

Synthesize 결과를 파일로 영속화한다. 대화 컨텍스트가 compact되어도 Read로 복원 가능.
