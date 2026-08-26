---
name: fz-peer-review
description: >-
  팀원 PR 코드 리뷰. 3-Model Cross-Review + 9개 관점 독립 분석.
  예: 팀원 PR 리뷰해줘, 피어리뷰, PR 검토 (비사용: 자기 코드 →fz-review, PR 해설 →fz-pr-digest)
user-invocable: true
disable-model-invocation: true
argument-hint: "[PR번호 또는 브랜치명] [--tier N] [--codex] [--deep] [--post] [--explain]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__activate_project,
  mcp__serena__read_memory,
  mcp__serena__write_memory,
  mcp__serena__list_memories,
  mcp__sequential-thinking__sequentialthinking,
  mcp__github__get_pull_request,
  mcp__github__get_pull_request_files,
  mcp__github__get_pull_request_comments,
  mcp__github__create_pull_request_review,
  mcp__github__add_issue_comment,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  Bash(git *), Bash(codex *), Bash(gh *), Read, Grep, Glob, Workflow, Write
provides: [peer-review]
needs: [none]
intent-triggers:
  - "피어리뷰|팀원|PR.*리뷰"
  - "peer.?review|teammate|PR.*review"
---

# /fz-peer-review - 팀원 코드 피어 리뷰

> **행동 원칙**: 팀원의 PR/브랜치를 3-렌즈 독립 분석 + Codex 교차검증으로 리뷰하고, Confidence Matrix 투표로 객관적 이슈를 도출한다. 칭찬할 건 칭찬하고, 지적할 건 근거와 대안을 함께 제시한다.

## 개요

> Gather → Analyze → Challenge → Synthesize → Deliver

- **9개 관점**: Architecture Decision, Extensibility, Over-Engineering, Functional Decomposition, Modern API, Dependency Impact, **Refactoring Completeness**, **Concurrency Safety** (동시성 코드 포함 시), **Requirements Alignment**
- **3-렌즈**: review-arch + review-quality + review-correctness (Tier 2/3에서 **전부 opus** — `peer-review.js`가 모델 single source) + Codex challenger(**Tier 1·2·3 상시** — SSOT는 `modules/peer-review-tiers.md` § Tier 구성 표. Tier 0은 `--codex` 시 Tier 1 전환)
- **Confidence Matrix**: 에이전트 투표 + Devil's Advocate로 편향 보정
- **4-Tier Graceful Degradation**: diff 크기 기반 자동 Tier 선택 (Tier 0/1/2/3) + 폴백 체인

```bash
/fz-peer-review 123                   # PR #123 리뷰
/fz-peer-review feature/ASD-456       # 브랜치 리뷰
/fz-peer-review 123 --deep            # Cross-Critique 활성화 (추가 ~$0.5-1.5)
/fz-peer-review 123 --post            # 인라인 라인 앵커로 리뷰 게시
/fz-peer-review 123 --tier 2          # Tier 강제 지정
/fz-peer-review 123 --explain         # 리뷰 후 변경사항 해설 (fz-pr-digest 연계)
/fz-peer-review 123 --explain --deep  # 리뷰 후 기술 해설까지 포함
```

## Prerequisites

- Tier 2/3 Analyze는 네이티브 Workflow 도구 필요 (`workflows/peer-review.js`) — 미가용 시 SOLO 리뷰 폴백(`mode:'fallback'`)
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)

## 참조

| 참조 | 용도 |
|------|------|
| `guides/skill-authoring.md` §12 | Workflow 규약 + **실패 복구 사다리 L1~L4** (팀 모드 정본). ⛔ `team-core.md`·`patterns/`는 역사적 출처 — 실행 절차 아님 |
| `modules/patterns/live-review.md` | Live Review (peer-review 공유 패턴, fz-review 동일) (UC-11, v4.7.1) |
| `modules/cross-validation.md` | get_codex_skill_path() 3-Tier 디스커버리, GIT_ROOT 추출 |
| `modules/lead-reasoning.md` | Speculation-to-Fact Fallacy (§1.5) — 리뷰 주장 시 [verified] 태그 |
| `modules/uncertainty-verification.md` | Default-Deny — 증거 없는 finding 차단 |
| `modules/peer-review-gates.md` | Synthesize 검증 게이트 4.4-4.9 전문 (4.4 Factual Claim, 4.7-A Deleted Logic + Origin Verification, 4.9 Call-site & Convention 포함) |
| `modules/peer-review-inline-anchoring.md` | Deliver `--post` 인라인 앵커 게시 7단계 + 확인 게이트 + 다지점 분할(SSOT). `Bash(gh *)`·`Write` 선언이 여기서 쓰인다 |
| `modules/peer-review-finding-anatomy.md` | 발견 서술 원칙 3 + 형태 예시 4종 (필드 위에 얹는 서술 계약) |
| `modules/evidence-collection.md` | Gather 2.6-2.8 Evidence Collection 수집 절차 상세 (a~f: old-new-pairs, producer-consumer, deletion, base-patterns, caller-analysis, convention-samples) |
| `modules/plugin-refs.md` | SwiftUI Expert + Swift Concurrency 플러그인 (diff에 `@MainActor\|actor\|async` 감지 시) |
| `modules/review-structural-axes.md` | 구조 판정 5축 (fz-review 공유). ⛔ Analyze 전 **Read 후** §3+§4를 `args.structuralContext`로 전달 — arch 렌즈에만 주입 |
| `skills/arch-critic/SKILL.md` | 관점 1(Architecture Decision) + 관점 2(Extensibility) |
| `skills/code-auditor/SKILL.md` | 관점 4(Decomposition) + 관점 5(Modern API) + 관점 6(Dependency) + 관점 7(Refactoring) |
| Codex challenger 스킬 | 관점 3(Over-Engineering) + 관점 7 보조 + Devil's Advocate |
| `schemas/codex_peer_review_schema.json` | Codex 응답 JSON 구조 |

## Step: Gather (컨텍스트 수집)

오케스트레이터가 직접 수행. `WORK_DIR=${PROJECT_ROOT}/peer-review-{PR_NUMBER}` (현재 작업 디렉토리 기준, 쓰기 불가 시 `/tmp/fz-peer-review/` 폴백).

### WORK_DIR 초기화 (Gather 첫 번째 단계)

WORK_DIR이 없으면 이후 모든 산출물 저장이 실패한다. Gather 시작 시 반드시 첫 번째로 실행.

```bash
mkdir -p ${WORK_DIR}
```

확인: `WORK_DIR` 경로를 대화 컨텍스트에 명시적으로 기록한다. 이후 모든 파일 저장은 이 경로를 사용한다.

### 0. 사전 점검

```bash
gh auth status  # 성공→gh 사용, 실패→git 폴백 (git fetch upstream + git diff)
# GIT_ROOT 추출: modules/cross-validation.md의 GIT_ROOT 공유 유틸 참조
```

### 0.5. PR 브랜치 fetch

`git show pr-{PR}:{FILE}` 직접 참조 및 Codex DA sandbox 제약 우회를 위해 필수.
```bash
git fetch upstream pull/{PR_NUMBER}/head:pr-{PR_NUMBER}
```

### 1. 입력 파싱 + diff 수집 — ⛔ 스크립트 1회

```bash
bash "${FZ_PLUGIN_ROOT}/skills/fz-peer-review/scripts/gather.sh" \
  --work-dir "${WORK_DIR}" --target {PR번호|브랜치} [--base BRANCH]
```

산출: `diff.patch` · `requirements.md` · `base-behavior.md` + `base/` · `base-manifest.tsv` · **`review-surface.md`** · `numstat.txt` · `risk.json`


⛔ **손으로 나눠 호출하지 않는다.** 병목은 fan-out 이 아니라 Lead 의 순차 도구 호출이다 — 결정론 구간을 한 번에 끝낸다. exit `2` 사용법 · `3` 대상 해석 실패 · `4` 수집 실패 — 셋 다 **산출물을 남기지 않는다**(staging 경유). ⛔ exit **`5`** 는 다르다: **base 원본 전건 실패**이고 **산출물을 남긴다**(diff 는 유효하고 origin 근거만 없다). 진행 여부는 Lead 판단, 진행하면 전 issue `origin` 을 `미지정` 으로 둔다 — 2·3·4 처럼 지우지 않는다.

⛔ **`review-surface.md` 를 먼저 읽는다.** base 가 분기점보다 앞서 있으면 이미 base 에 있는 커밋이 diff 에 다시 나타나 Tier 와 리뷰 표면이 함께 부풀려진다(실측 #4766: 2.9배). `git cherry` 의 `-` 커밋은 대상에서 빼고 Tier 를 재계산한다. 상세·한계: `modules/peer-review-tiers.md` § 리뷰 표면 진단

⚠️ 스크립트는 **원재료까지만** 만든다. `old-new-pairs`·`producer-consumer`·`caller-analysis`·`convention-samples`·`semantic-mapping` 은 Lead 가 채운다 (`modules/peer-review-tiers.md` § canonical set). ⛔ **패턴·일관성 이슈를 낼 때 `convention-samples` 를 건너뛰지 않는다** — 관례를 위반으로 판정하는 것도, 관례 이탈을 지적하는 것도 같은 N:M 카운트를 요구한다(실측: "형제 2곳이 다르다"로 적었는데 전수는 4:1이었다).

### 2. Serena Pre-caching → `${WORK_DIR}/symbols.json`

```
mcp__serena__get_symbols_overview       → 변경 파일 심볼 목록
mcp__serena__find_referencing_symbols   → 변경 심볼의 참조 관계
mcp__serena__find_symbol                → Protocol 정의, conformer
```

**추가 필드**: `arch_layer_map` (아키텍처 컴포넌트 매핑, CLAUDE.md ## Architecture 기반), `import_graph` (의존성 방향), `stream_paradigms` (리액티브 프레임워크 사용 패턴), `protocol_conformers`, `deprecated_symbols`

**추가 pre-cache** (관점 6-7):
- `deprecated_symbols`: `Grep` → `@available(*, deprecated)` 탐지
- `existing_utilities`: diff 신규 객체 → 기존 extension/유틸 Grep
- `base_class_hierarchy`: class init/willSet 변경 시 → `find_referencing_symbols`로 subclass 수집 (optional param default:nil → subclass silent regression 주의)

### 1.5. 요구사항 수집 → `${WORK_DIR}/requirements.md`

PR title/body에서 JIRA 티켓 ID 추출 + acceptance criteria 수집. JIRA 연동 시 Atlassian MCP 활용.

### 2.5. 판별 방법(oracle) 명시

코드로 확정할 수 없는 주장에는 "무엇을 보면 판별되는지"를 함께 적는다 — 방법을 모르면 그 지적은 판정 불가로 남는다.

- View 변경 → 시뮬레이터/실기기(+review-quality 집중 지시) · 런타임 순서·타이밍 → DEBUG 로그 캡처 지점 · 서버 계약 → curl 재현

### 2.6. Code Evidence Collection → `${WORK_DIR}/evidence/`

> 참조: `modules/evidence-collection.md` — 수집 절차 상세 (a~d)
>
> 에이전트는 Bash/git show 접근 불가. Orchestrator가 사전에 실제 코드를 수집하여 에이전트에게 데이터로 전달한다.

```bash
mkdir -p ${WORK_DIR}/evidence
```

| 수집 대상 | 산출물 | 목적 |
|----------|--------|------|
| 변경 함수 old/new 페어 | `evidence/old-new-pairs.md` | origin 판정 근거 |
| API/condition mapping atom (refactoring 시) | `evidence/semantic-mapping.md` | Mapping Layer SPOF 방어 (v4.4.0, Gate 4.4-A) |
| Producer/Consumer 매핑 | `evidence/producer-consumer.md` | `_` destructuring, 값 출처 확인 |
| 삭제 심볼 잔존 참조 | `evidence/deletion-verification.md` | compile break 주장 검증 |
| base 코드 패턴 | `evidence/base-patterns.md` | regression vs pre-existing 판별 |
| 호출자 코드 | `evidence/caller-analysis.md` | init/DI의 실제 사용처 + 참조 타입 |
| 프로젝트 convention 샘플 | `evidence/convention-samples.md` | 동일 패턴의 다른 모듈 (3+ = convention) |

### 2.7-2.8. Caller Analysis + Convention Sampling

> 참조: `modules/evidence-collection.md` — 섹션 e (Caller Analysis), 섹션 f (Convention Sampling)
>
> ⛔ init/DI 패턴 변경이 있는 PR에서 필수. "선언부만 보고 판단" 방지.
> 관측 사례: 선언부가 깔끔해도 caller 가 더러우면 의미가 없다. convention 패턴을 위반으로 지적하면 안 된다.

### 3. 원본 동작 수집 → `${WORK_DIR}/base-behavior.md`

`git show ${BASE_BRANCH}:${FILE_PATH}`로 변경 함수의 원본 코드를 추출. 에이전트가 origin(regression/pre-existing/improvement)을 판정하는 근거로 사용.
**⛔ 제네릭 설명이 아닌 실제 코드를 포함해야 한다.** 특히 enum throw site, factory method, DI 등 값의 생성 지점은 반드시 코드로 수집.

### 4. ⛔ Fact + Mapping Verification Gate (Gather 완료 검증)

Key Facts + **Mapping Facts** (v4.4.0)를 Analyze 전달 전에 **수집과 다른 도구로 교차 확인**. 도구 출력 잘림(grep -A 등) → 검증 없이 전달 시 전 에이전트 동일 오탐.

```
절차:
1. Key Facts + Mapping Facts 작성 (refactoring 시 evidence/semantic-mapping.md atom decomposition 포함, v4.4.0)
2. 각 Fact를 다른 방법으로 재확인. Mapping Fact는 ground truth source 직접 read로 atom-level 재검증 (Mapping Layer SPOF 방어)
3. 불일치 발견 시 수정
4. ⛔ Fact 중 **"0건·부재·전부·~뿐"이 결론인 것**은 `modules/cross-validation.md` §Negative-Result Gate를 **Read 후 적용** — positive control(선언이 실재하는 ref에서 같은 패턴이 non-zero를 내는가) + exit code 판정 + 다중 대상이면 라벨. **0건은 「대상 부재」와 「도구 고장」을 구별하지 못한다.**
```


> ⛔ **절차 4가 왜 별도 항목인가**: 절차 2의 "다른 방법으로 재확인"은 *매치가 있는* Fact에는 작동하나 **0건에는 발화 조건이 없었다.** 실측 — `git grep -nE '\bSym\b'` 가 ERE `\b` 미지원으로 **에러 없이 0건**을 반환했고, 그 "잔존 소비자 0건"이 evidence에 실려 세 렌즈 전원에게 배포될 뻔했다. 렌즈는 Bash 미보유라 재측정이 불가능하므로 cross-model 이 cross-data 가 아니게 된다. §Negative-Result Gate 는 2026-08-10 부터 존재했고 6곳에서 트리거되나(`lead-reasoning:183` · `system-reminders:24` · `fz-discover:231` · `fz-search:343` · `fz-manage:178,195`) **본 스킬에만 연결이 없었다** — 신설이 아니라 배선 복구다.

### 4.5. ⛔ 패턴 변환 감지 (diff에 비동기/네트워크/UI 패턴 변경 포함 시)

diff에 `async/await`, `Task {`, `@MainActor`, `catch`, PromiseKit→async 변환이 감지되면:
- `modules/code-transform-validation.md` 참조
- 변경 전 코드의 스레드/에러 특성 확인 (`git show` 또는 base branch)
- diff의 After 코드가 원본과 동등한 동작을 보장하는지 검증
- 불일치 시 리뷰 코멘트에 "transformation_deviation" 이슈 기록

### 5. diff 크기별 모드 결정

```
DIFF_LINES=$(wc -l < ${WORK_DIR}/diff.patch)
<500줄 → FULL_INLINE | 500-2000줄 → SUMMARY | >2000줄 → FILE_LIST_ONLY
```

### 5.5. Tier Determination (Auto-Tier)

> ⛔ Gather Step 5 직후 필수 실행 (미실행 시 작은 PR도 Tier 2 디폴트 → 토큰 낭비).
> **자동 선택 실행 bash** (SIGNIFICANT_LINES = CHANGED − GENERATED + risk escalation): `modules/peer-review-tiers.md` "## 자동 휴리스틱 (단일 진실 원천)" → "### 자동 선택 실행 bash" 참조 (SSOT 단일 지점, L18 규칙).

상세 절차 (Tier 0/1 분기, evidence 범위, 비용 로깅): `modules/peer-review-tiers.md` 참조.

#### Few-shot
```
BAD: 13줄 PR → Tier 2 Lite Team 디폴트 → ~375K tokens
GOOD: 13줄 PR → auto Tier 0 → Lead 단독 분석 → ~30-50K tokens
```

#### Gate 5.5: Tier Determined
- [ ] CHANGED_LINES 계산 완료? (`gh pr view --json additions,deletions` 또는 `git diff --numstat`)
- [ ] --tier 옵션 우선 적용?
- [ ] auto 결정 결과 tier.txt 기록?

## Step: Analyze (독립 리뷰, 병렬)

Tier에 따라 팀 구성이 달라진다 (Tier 상세는 "4-Tier Graceful Degradation" 섹션 참조).

### Tier 0/1 분기
- **Tier 0** → `modules/peer-review-tiers.md` §Tier 0 절차로 위임. 본 SKILL.md Analyze 후속 섹션(Gate 0 / Tier 2 / Tier 3) 모두 skip.
- **Tier 1** → `modules/peer-review-tiers.md` §Tier 1 절차로 위임 + Codex challenger 1회 (Lead Bash). Gate 0 / Tier 2 / Tier 3 시퀀스 skip.
- **Tier 2/3** → 아래 기존 시퀀스 실행.

### Orchestrator Bias 방지 규칙 (InputHygiene 계약)

**보장**: Lead의 가설이 판정 근거로 되돌아오지 않는다.

에이전트에게 **가설이 아닌 데이터만** 전달한다. Orchestrator의 해석·추측은 렌즈의 독립성을 파괴한다.

> 관측 사례: Lead가 "이 값은 서버가 준다"는 추정을 브리프에 적었고 렌즈 2/3이 그것을 사실로 받아 오탐을 냈다. 실제로는 클라이언트 하드코딩이었다.
> 다른 사례: Lead가 영향 범위 후보를 목록으로 적어 넣자 렌즈 둘이 **같은 목록을 되돌려줬다**. 3렌즈 합의처럼 보이지만 독립 확증이 아니다.

```
⛔ 금지: "이 값은 원래 서버가 주던 것" / "X가 누락된 것 같습니다" / "A·B·C가 영향받을 것"
✅ 허용: "forceUpdate 에서 `_, _` destructuring. evidence/producer-consumer.md 참조"
```

> ⛔ **경로별 구현**(Tier 2/3 브리프 검사 · Tier 0/1 탐지·표시 + 강등 결정식) + `intentContext` 허용/금지 표: `modules/evidence-collection.md` § InputHygiene 참조

**Self-Check**: 프롬프트에 "~인 것 같다" / 내 의견 / 사실 단정 포함 시 → 제거 후 데이터로 대체.

> ⛔ **Tier 2/3 실행 상세**(Workflow 시퀀스 · 에이전트 출력 스키마 · Evidence-Only Brief · 병합 방법 A/B):
> `modules/peer-review-workflow.md`. Tier 0/1 은 sub-agent·Codex 가 없어 **읽지 않는다**.

## Step: Challenge (상호 비판)

### Cross-Critique Anti-Sycophancy Rule + Codex Devil's Advocate

Anti-Sycophancy 규칙(코드 증거 없는 self-reverse 금지), reverse 판정 절차, DA 호출 패턴: `modules/peer-review-tiers.md` §Cross-Critique 참조.

---

## Step: Synthesize (종합)

sequential-thinking으로 Confidence Matrix를 계산한다.

### 1. 결측 에이전트 처리

Lead 보정 **불필요** — `peer-review.js`가 `reviews`를 `.filter(Boolean)`으로 구성해 실패 에이전트는 이미 빠져 있고, `PeerReviewSchema`에 `agent_status`가 없어 `partial`은 표현되지 않는다. Lead가 볼 것은 `reviews.length`뿐 — ⛔ 스크립트는 **전부 null일 때만** fallback을 반환하므로(`peer-review.js`의 `reason: 'stage1 all null'` 분기) 1-review 경로가 실재한다:
3 → 3-vote / 2 → 2-vote 모드(§3) / **1 → 투표 불가. 단독 렌즈 결과이므로 Confidence Matrix를 만들지 않고 `[단일 렌즈 — 교차검증 없음]` 태그와 함께 보고하며, 이슈 confidence는 ×0.7 감쇠** / 0 → `mode:'fallback'`(Tier 하위 전환)

### 2. Origin 기반 Severity 보정

에이전트가 보고한 `origin` 필드를 기반으로 severity를 보정한다.

| origin | 처리 | 리포트 태그 |
|--------|------|------------|
| regression | severity 유지 (PR이 만든 문제) | — |
| pre-existing | severity cap → suggestion | `[기존 동작 동일]` |
| improvement | **cap 없음** — 에이전트 판정 유지. `raw`(에이전트)와 `adj`(보정 후)를 **병기**하고 ⛔ **non-blocking**(verdict를 막지 않음) | `[개선 제안]` |
| 미지정 | base-behavior.md 교차 확인 후 Orchestrator 직접 판정 | — |

핵심 원칙: **PR 리뷰는 PR이 만든 변화를 평가한다.**
기존 코드에 이미 있던 패턴을 PR의 결함으로 지적하지 않는다.
개선 가능 여지는 suggestion으로 언급하되, 수정을 강제하지 않는다.

```
BAD: Interactor에서 guard 삭제 → "연결 상태 체크 누락 (regression)" 즉단
     (UseCase에 동일 guard 이동을 확인하지 않음)
GOOD: Interactor guard 삭제 발견 → PR diff 전체 Grep("getConnectState")
     → UseCase.connect()에 동일 guard 이동 확인 → origin: relocated → 이슈 DROP
```

### 2.5. PR Intent Alignment Check

PR title/body/requirements.md의 핵심 의도를 각 regression 이슈와 교차 확인한다. PR이 "기능 제거/전환"을 명시한 경우, 해당 기능의 부수효과(이벤트, 상태 초기화 등) 제거는 의도적일 수 있다.
- 의도적 제거 가능성이 있으면: severity 유지하되 `"[의도 확인 필요]"` 태그 추가
- 원칙: "삭제된 기능의 부수효과까지 PR의 결함으로 단정하지 않는다. 의도 확인이 우선."

### 3. Dedup + 투표

```
Dedup: 동일 파일 + 겹치는 line_range + 동일 perspective → 병합

투표 로직:
├─ 3/3 동의: final = avg × 0.85 → INCLUDE
│   └─ ⚠️ 3/3 동의는 신뢰를 증폭하지 않고 오히려 0.85로 할인한다.
│      동일 Gather 데이터를 공유하면 같은 오류에 전원 동의한다 → ⛔ **Fact Verification Gate 재확인.**
├─ 2/3 동의: final = avg × 0.9 → INCLUDE (소수 의견 주석)
│   └─ 소수 반박이 있으면 해당 에이전트의 근거를 우선 검토
├─ 1/3 동의: final = avg × 0.6 → ≥70 INCLUDE, <70 EXCLUDE
│   └─ 단독 발견이 직접 파일 Read 기반이면 독립성 HIGH → ×0.7로 상향
└─ 0/3: EXCLUDE
```

**독립성 원칙**: 에이전트가 Gather의 Key Facts를 기반으로 판단하면 독립성 LOW. 에이전트가 직접 파일을 Read하여 판단하면 독립성 HIGH. Codex가 sandbox에서 독립 분석하면 독립성 HIGH. 독립성 LOW 에이전트의 동의는 confidence를 증폭하지 않는다.

### 4. Confidence Matrix 출력

```markdown
| # | Issue | Origin | Sev | Arch | Auditor | Codex | DA | Votes | Basis | Final | Decision |
|---|-------|--------|-----|------|---------|-------|----|-------|-------|-------|----------|
```

> Origin 열: `R`(regression), `P`(pre-existing), `I`(improvement). pre-existing → severity cap: suggestion. **`I`는 cap 없음 — `Sev` 열에 `raw→adj` 병기(⛔ `Final` 열은 confidence이므로 어휘 구분), non-blocking**.
> Basis 열: `CV`(code-verified), `IO`(inference-only). IO + 3/3 → [correlated] 태그.
> ⛔ 이슈·리포트에 **전수·카운트·부정 주장**("N곳"·"사용처 0건"·"형제 5/5"·"나머지는")이 있으면 `modules/cross-validation.md` §Coverage Gate를 **Read 후 실행** — 전체 N / 분석 M 비율 보고. ⛔ 그중 **부정 주장(0건·부재)** 은 같은 파일 **§Negative-Result Gate**도 함께 적용한다 — Coverage Gate 는 *범위*(N 중 M)를 보고 Negative-Result Gate 가 *도구 유효성*을 본다. N 자체가 오측정이면 0/0 으로 통과한다. Codex 호출 시 같은 파일 §Reflection Rate도 산출(반영률 = Codex finding 중 최종 리포트 채택 / N · `N<10`은 preliminary·verdict 보류). same-model 교차(Stage 2 arch↔quality)는 `guides/agent-team-guide.md` §Same-model Cross-Verify Reflection Rate 정책대로 headline 제외.

### 4.4-4.9. Verification Gates

> 참조: `modules/peer-review-gates.md` — Factual Claim (4.4) + Line (4.5) + Compiler (4.6) + Behavior (4.7) + Deleted Logic (4.7-A) + RxSwift Error Path (4.8) + **Call-site & Convention (4.9)** 게이트 전문
>
> 게이트 실행 전: `synthesized-issues-partial.json` 중간 저장 필수 (compact 방지)

### 5. ⛔ CHECKPOINT — 산출물 저장 (Compact Recovery)

> **⛔ Synthesize 완료 직후, Deliver 단계로 넘어가기 전에 반드시 Write 도구로 저장하세요. 저장 전 대화 출력 금지.**

Synthesize 결과를 파일로 영속화한다. 대화 컨텍스트가 compact되어도 Read로 복원 가능.

```
${WORK_DIR}/synthesized-issues.json  — 병합된 이슈 (Dedup+투표+검증 라인)
${WORK_DIR}/confidence-matrix.md     — 최종 Confidence Matrix (마크다운)
${WORK_DIR}/review-index.md          — Compact Recovery 엔트리 포인트
```

> review-index.md: Phase + Artifacts 목록 기록. Compact 감지 시 이 파일 읽어 산출물 로드 → 중단 지점 재개.

**비ASD Serena Fallback** (WORK_DIR 없을 때):
```
write_memory("fz:checkpoint:peer-review-synthesize", "PR#{number}: 이슈 {N}개 (Critical:{c}/Major:{m}/Minor:{n}). Confidence: {avg}%. 핵심: {top3_요약}")
```

---

## Step: Deliver (전달)

### Comment Style Guide (PR 코멘트 톤)

팀원의 코드를 존중하는 건설적 톤으로 작성한다. 모든 이슈 설명과 PR 코멘트에 적용.

- "~하면 좋겠습니다" (제안형) > "~해야 합니다" (명령형)
- 문제만 지적하지 말고 "왜 중요한지" 설명 포함
- 기존 코드의 좋은 점 먼저 언급 후 개선점 제시
- 불확실한 이슈는 "확인 부탁드립니다" 형태로 질문

톤 템플릿: Major("좋은 접근인데 {기존동작}이 빠진 것 같아요"), Minor("{장점} 잘 되어 있는데 {개선점}도 함께"), Suggestion("사소한 건데 {기존유틸} 활용하면"), [의도 확인]("혹시 {동작}은 의도적으로 제거하신 건가요?")

### 출력 전략: 대화 vs 문서 분리

#### 대화 출력 (항상)

Confidence Matrix → Major 이슈(file:line + What/Impact/Evidence/Suggestion) → Minor(2-3줄) → 긍정적 측면(3-5줄) → 최종 판정 + Severity 보정 근거

#### ⛔ CHECKPOINT — 문서 출력 (Deliver 완료 전 반드시 저장)

> **⛔ 대화 출력 전에 반드시 Write 도구로 아래 파일들을 저장하세요. 저장 완료 후 사용자에게 경로를 안내합니다.**
> ```
> 📁 산출물 저장: ${WORK_DIR}/
>    ├── review-report.md
>    └── pr-comments.md
> ```

- `${WORK_DIR}/review-report.md` — 통합 보고서. 이슈별 필수 필드: `File:line` | Origin | Confidence | Found-by | What(WHY 포함) | Suggestion
  서술 형태(인과가 한 문장으로 안 끝나는 결함): `modules/peer-review-finding-anatomy.md` — 필드 나열이 아니라 원칙. 결함마다 인과의 모양이 다르다

- `${WORK_DIR}/pr-comments.md` — 이슈별 부드러운 톤 PR 코멘트 모음 (복사/붙여넣기용)
- `${WORK_DIR}/*-result.json` — 에이전트/Codex 원본 결과

#### --post 시 — 인라인 앵커 게시

발견을 PR 대화창이 아니라 **코드 라인 옆**(Files changed)에 붙인다. 7단계 절차·실패 대응·다지점 분할 전문: `modules/peer-review-inline-anchoring.md`

`앵커 계산(scripts/diff_anchors.py) → 구간 선택(Lead) → non_anchorable은 본문 인용 → payload(top-level body = **review-report.md 전문**) → ⛔확인 게이트 → gh api …/pulls/{N}/reviews → 착지 검증`

> ⛔ **확인 게이트** — 미리보기는 항상 출력하되, 차단은 셋 중 하나일 때만: (a) `event ≠ COMMENT` (b) `non_anchorable` 대체 발생 (c) 겹치는 hunk 복수로 Lead가 구간 선택.
> ⛔ `mcp__github__create_pull_request_review`로 대체 불가 — `comments[]`에 `start_line`·`side`가 없어 범위 하이라이트·LEFT 앵커가 안 된다. 이 스킬만 `Bash(gh *)`를 선언하는 이유.

**비ASD Serena Fallback** (WORK_DIR 없을 때):
```
write_memory("fz:checkpoint:peer-review-deliver", "PR#{number}: 판정 {verdict}. Critical:{c}/Major:{m}. 핵심이슈: {top3}. --post: {Y/N}")
```

---

## 4-Tier Graceful Degradation

> 참조: `modules/peer-review-tiers.md` — Tier 구성, 자동 선택, 타임아웃 + 폴백

---

## Few-shot 예시

```
BAD (작업 컨텍스트 오염):
팀원 PR 리뷰에 gh pr checkout / 브랜치 전환 → 사용자 미커밋 변경·빌드 캐시 손실.

GOOD:
git worktree add ../app-iOS-pr-<N> pr-<N> → 격리 디렉토리에서 리뷰 → 현재 컨텍스트 보존.
```

## 테스트 케이스

> 상세: `skills/fz-peer-review/references/test-spec.md` (Triggering + Functional)

## Boundaries

**Will**:
- 팀원 PR/브랜치의 9개 관점 피어 리뷰
- 3-Model Cross-Review + Confidence Matrix 투표
- Codex Devil's Advocate로 편향 보정
- 인라인 라인 앵커 리뷰 게시 (`--post` — `gh api …/pulls/{N}/reviews`)
- 4-Tier Graceful Degradation + 자동 폴백
**Will Not**:
- 코드를 직접 수정하지 않음 (리뷰만 수행)
- 자기 코드 리뷰 (→ `/fz-review`)
- Codex 위임 (→ `/fz-codex`) — codex exec 직접 호출
- Safety/메모리/동시성 심층 분석 (→ CLAUDE.md `## Code Conventions` 위임)
- ⛔ **standalone Agent() 호출 금지** — Tier 2/3 Analyze는 `workflows/peer-review.js` Workflow로 실행 (결정적 스크립트, agentType `fz:`). Lead는 reviews/issues 반환을 Synthesize로 통합.
## 에러 대응

`gh auth` 실패→git 폴백, 에이전트 spawn 실패→Tier 하위 전환, **Codex 실패→(Tier 2/3) 2-agent 투표 · ⛔(Tier 1) 렌즈가 없으므로 Lead 단독 = 실질 Tier 0 — `mode` 를 `solo (codex 실패)` 로 적고 `[단일 렌즈 — 교차검증 없음]` 태그 + confidence **×0.7** 감쇠. ⛔`GATE-FAIL`/exit≠0 은 **측정 실패**이지 "이슈 0건" 이 아니다**, Codex timeout→재시도 1회 후 skip, Serena 실패→에이전트 직접 MCP, diff >2000줄→AskUserQuestion.

## Completion → Next
`--post`로 PR 게시, `--discover`로 Major 이슈 심층 탐색, `--explain`으로 변경사항 해설 연계.
