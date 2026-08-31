# Peer Review — Tier 2/3 Workflow 실행

> ⛔ **Tier 2/3 전용.** `peer-review-tiers.md` 가 명시하듯 Tier 0/1 은 **sub-agent · Codex 호출이 없다** —
> 여기 있는 것을 한 번도 쓰지 않는다. `SKILL.md` 에 두면 경량 경로가 매 리뷰마다 읽고 버린다.
>
> 추출 근거(2026-08-26): S8 파일럿에서 경량 경로 비용이 병목으로 지목됐고, Tier 0/1 필수 read-set 이
> 2,045줄까지 커진 상태였다. 이 파일은 **Tier 2/3 read-set 에만** 들어간다.
>
> ⚠️ **InputHygiene 계약 자체는 전 경로 적용**이다(`SKILL.md § Orchestrator Bias 방지 규칙`).
> 여기 옮긴 것은 그 계약의 **Tier 2/3 구현**(에이전트 브리프 조립)뿐이다 — 계약을 옮긴 것이 아니다.

### Tier 2/3 실행 시퀀스 (Workflow)

> TEAM(TeamCreate+SendMessage) → 네이티브 Workflow 전환 (Wave 4). Analyze 코어는 `workflows/peer-review.js`가 소유한다 (결정적 스크립트 — P2P SendMessage 없음). 규약: `guides/skill-authoring.md` §12.

1. **Workflow 호출** (Lead): `Workflow({ scriptPath: '{플러그인 루트}/workflows/peer-review.js', args: { diffPath, intentContext, reviewSurfacePatchPath, reviewSurfacePath, evidencePaths, basePath, deep, structuralContext } })` — `structuralContext`는 `modules/review-structural-axes.md`를 Read해 §3 축 + §4 경계 문구를 담는다 (미전달 시 구조 축 미적용)
   - `deep=false` → **Tier 2 (Lite)**: Stage1 3-병렬(arch+quality+correctness) → **트리거 발화 시에만 Stage2 교차**. **3 또는 5-call**(null 재시도 시 최대 6/10). 발화 여부는 반환 `stage2Ran`·`stage2Trigger`. Confidence Matrix 미투표(Lead 단순 병합)
   - `deep=true` → **Tier 3 (Full)**: +Stage2 교차(arch↔quality) +Stage3 counter DA, **기본 6-call**(부분 실패로 Stage2 생략 시 5, 재시도 시 최대 9). 권위 수치는 `metrics.agentCalls`
   - ⛔ **`reviewSurfacePatchPath` 가 1차다.** `review-surface.patch`(gather 가 만드는 중복 커밋 제외분)가
     있으면 그것을 넘긴다 — 스크립트가 이를 **리뷰 대상**으로 쓰고 `diffPath` 를 부풀림 확인용 보조로 내린다.
     ⛔ **진단 파일만 넘기면 무력하다** — 렌즈는 Bash·git 이 없어 커밋 해시로 hunk 를 필터할 수 없고,
     `review-surface.md` 의 조언("`git show <+ 커밋>`")도 실행할 수 없다 [외부: codex 리뷰 2026-09-01].
   - `reviewSurfacePath`(`review-surface.md`)는 patch 와 **함께** 넘긴다 — 부풀림 규모를 렌즈가 알면
     전량 diff 에서 나온 발견을 스스로 걸러낼 수 있다. patch 없이 이것만 넘기면 스크립트가 경고를 붙이지만
     그것은 대체물이 아니다.
   - ⛔ **`evidencePaths` 는 파일명 하나가 아니라 gather 산출물 목록에서 조달한다** — 존재하는 것을 전부 넘긴다.
     최소 `evidence-move-drift.md`(이동 리팩토링에서 동등성 데이터 `old-new-pairs.md` 와 **다른 축**) ·
     `old-new-pairs.md` · `convention-samples.md` · `caller-analysis.md`.
     만들고 안 넘기면 무력하다 (실측 #4774: `evidence-brief/` 를 넘기니 렌즈들이 인용했다).
     ⚠️ 파일명을 하나만 열거하면 같은 스크립트가 만드는 **형제 산출물이 조용히 빠진다** — `review-surface.md`
     가 정확히 그렇게 누락돼 있었다.
   - base 원본은 Gather에서 prefetch하여 `basePath`로 전달 — 에이전트가 SendMessage로 요청하지 않는다 (채널 우선순위 원칙, `agent-team-guide.md` §2)
2. **반환 처리**: `mode:'workflow'` → reviews/issues를 Synthesize Step 입력으로. `mode:'fallback'` → Lead SOLO 리뷰 폴백.
3. **Codex Analyze** (out-of-band, `--codex`/Tier3): Lead가 `/fz-codex` 경유 challenger 호출 (⛔ 스크립트 내 cross-provider 스폰 금지 — 마이그레이션 결정). 결과는 Synthesize Confidence Matrix의 Codex 열로 주입.

> 산출물 계약(Confidence Matrix, origin severity 보정, confidence<80 미보고, dedup+투표)은 Synthesize Step에 보존. metrics는 Lead가 `experiment-log.md` §5.7 fz-peer-review 테이블에 기록.
> ⚠️ **§5.7에 fz-peer-review 테이블이 아직 없다** (Wave 4가 `[Unreleased]` + 실 invoke 캘리브레이션 pending). 확산 임계 사전등록과 테이블 생성은 **별건** — 실 invoke 전에 처리해야 `확증 편향 방어`가 유지된다.

### 에이전트 출력 스키마

`{issues[], strengths[], overall_assessment}` — `workflows/peer-review.js`의 `PeerReviewSchema` required와 동일. 상세 필드는 arch-critic/code-auditor SKILL.md 참조.
스크립트가 반환 시 `agent` 키를 주입하므로 Lead가 받는 형태는 `{agent, issues[], strengths[], overall_assessment}`이다.

**Per-Agent 품질 원칙**: 시니어 엔지니어가 PR 코멘트로 달 만한 이슈만 보고한다. 이슈 0개도 유효한 결과다.
자체 confidence 80% 미만이면 보고하지 않는다. description ≤400chars (WHY 필수), suggestion ≤300chars, strengths ≤3. `challenges` 키는 Codex DA 전용 (기본값 `[]`).
WHY: 이슈 수가 많으면 리뷰어 피로가 증가하고, 진짜 문제가 marginal finding에 묻힌다.

### 방법 A — 기본 (Orchestrator 합성)

```
├─ 3개 결과 JSON 로드 (review-arch + review-quality + codex-challenger)
├─ 이슈 중복 제거 (파일 + line_range overlap + perspective fuzzy match)
├─ 이슈 간 충돌 식별 ("확장성 부족" vs "오버엔지니어링")
└─ 초기 Confidence Matrix 생성
```

### 방법 B — `--deep` Cross-Critique (Tier 3 Workflow)

> ⚠️ 추가 ~$0.5-1.5, 시간 2-5분. `--deep`(=Tier 3) 시 사전 비용/시간 경고 표시.

`deep=true`로 `peer-review.js` 호출 → Stage2(arch↔quality id-기반 교차 severity 조정 — correctness 불참, false_positive는 실측 인용 필수) + Stage3(review-counter DA — issues 반론 + strengths 도전)이 실행된다. SendMessage 실시간 멀티턴 수렴은 고정 1-pass 교차로 대체됨(충실도 trade-off — 은폐 말고 명시).

**반환 소비 (Tier 3)**: `{ tier, reviews, issues, crossAdjustments, strengthChallenges, distribution, metrics }` — ⛔ `counter` 키는 **없다**(`peer-review.js` 상단 API 계약 주석). DA 산출은 `strengthChallenges`로 온다
- `crossAdjustments{archOnPeers,qualityOnPeers}` → 교차 severity 조정을 Confidence Matrix에 반영. ⛔ `crossVerdict: contested`(두 렌즈 판정 갈림) 처리는 `modules/peer-review-gates.md` § MergeContract § 9
- **`strengthChallenges`** → counter의 strengths 반례. `target`이 가리키는 "정상 판정"을 재검토 → 유효하면 신규 이슈 승격(confidence 70) 또는 해당 strength 제거. ⛔ 생략하면 `--deep`이 청구한 ~$0.5-1.5의 Stage3 산출이 버려진다

### Evidence-Only Brief (Tier 2/3 에이전트 브리핑)

**Evidence-Only Brief Template**:
```
[Goal] {관점}에서 독립 이슈 발굴
[Data] diff.patch + evidence/*.md + symbols.json + requirements.md + base-behavior.md
[Constraints]
- 피어 참조 금지, max 10, origin 필수, 추론 아닌 코드 증거 기반만
- ⛔ init/DI 이슈 시: evidence/caller-analysis.md 필수 확인 — "호출자가 어떤 타입을 알아야 하는가?"
- ⛔ 패턴 이슈 시: evidence/convention-samples.md 필수 확인 — "프로젝트 convention과 일치하는가?"
- ⛔ mapping/equivalence claim (v4.4.0): evidence/semantic-mapping.md 필수 입력 — Lead 요약 문장이 아닌 raw source + atom table을 직접 read. mapping_status가 lossy/unverified인 항목은 별도 highlight
- Convention 패턴(3+ 모듈 동일)을 위반으로 판정하지 않는다 (suggestion까지만 허용)
```
