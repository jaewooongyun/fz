# fz Pipeline Proposal — 사용자 확인 시각화

> **Scope of Applicability**: `/fz` 오케스트레이터 Phase 4 (User Confirmation) 전용. 다른 스킬에서 유사한 확인 단계가 필요하면 표 컬럼(스킬/역할/실행자/모델)과 범위 확인 임계치(5 Step)가 해당 스킬에 맞는지 먼저 검토.
>
> **Purpose**: 결정된 파이프라인·팀 구성·모델 배정을 사용자에게 제시하고 승인을 받기 위한 표준 시각화 형식.

---

## 목차

- [시각화 형식](#시각화-형식)
- [AskUserQuestion 선택지](#askuserquestion-선택지)
- [적극적 확인 원칙 (Step 8)](#적극적-확인-원칙-step-8)
- [권고 Default 정책 (Lead Action Default 적용)](#권고-default-정책-lead-action-default-적용)
- [관련 모듈](#관련-모듈)

---

## 시각화 형식

```markdown
## 파이프라인 제안

**요청**: "{사용자 원문}"
**의도**: {분석된 의도 요약}
**파이프라인**: `{파이프라인 이름}`
**모드**: TEAM (점수: {점수}/10)

| # | 스킬 | 역할 | 실행자 | 모델 |
|---|------|------|--------|------|
| 1 | /fz-code | 점진적 구현 | impl-correctness ★ | opus |
| 2 | ✓ build | 빌드 검증 | Lead | — |
| 3 | ✓ gpt check | 교차 검증 | Lead | gpt |
| 4 | /fz-review | 아키텍처 리뷰 | review-arch | opus |
| 5 | /fz-review | 품질 리뷰 | review-quality | opus |
| 6 | /fz-commit | 커밋 | Lead | fable |

**에이전트**: Lead(fable) + impl-correctness(★opus) + review-arch(opus) + review-quality(opus) — 동시 opus ≤3
```

> ✓ 접두사: 자동 삽입된 검증 게이트. ★: Primary Worker (opus). 모델 열 `gpt` 는 세션 선택이 있으면(`gpt-choice.sh get` exit 0) `gpt (<slug>/<level>)` 로 선택값을 붙인다.

---

## AskUserQuestion 선택지

> **Default 결정 알고리즘** (review-arch MUST-1 + GPT 검증 §5 MUST-1 합의):
> Phase 3 결정(SOLO/TEAM)은 스킬 모드를 정하지 않는다 — 파이프라인 · 팀 구성 참고다. 모드는 각 스킬 게이트가 실측으로 정한다(추천 full 일 때만 그때 묻는다 — `modules/mode-gate.md` § 언제 묻나). Phase 4 는 사용자가 **명시로 고른** 모드만 스킬 인자(`light` · `full`)로 넘긴다(2026-11-12).

### Phase 4 Default 결정 알고리즘

| 조건 | Phase 4 선택지 | 비고 |
|------|---------------|------|
| 기본 | **파이프라인 승인** — 모드 선택지를 두지 않는다 | 모드는 스킬 게이트가 잰다 |
| 사용자 `--deep` / `--team` / `--solo` · `light` / `full` 명시 | **사용자 명시 선택 유지 (override)** — 그 모드를 인자로 넘긴다 | Lead 재권장 금지 |
| 커스텀 구성에서 사용자가 모드를 지정 | 그 모드를 인자로 넘긴다 | 명시 선택 |

### 선택지 형식

```
1. [파이프라인] (Recommended) — 모드는 각 스킬이 재서 정한다(full 추천일 때만 그때 묻는다)
2. 커스텀 구성 (스킬 · 모드 지정)
```

### 규칙

- ⛔ 사용자 명시 선택 후 Lead 재권장 금지 (edge-cases Failure 4-2 완화)
- ⛔ 실행 중 complexity 또는 catch 누적 신호로 full 이 필요해 보이면 **자동 전환하지 않고 묻는다** (Failure 4-3 완화 · 2026-10-19 사용자 결정 — `modules/mode-gate.md`)
- ⛔ Phase 4 는 사용자가 명시로 고른 모드만 스킬 인자로 넘긴다 — Phase 3 의 SOLO/TEAM 을 모드 인자로 바꿔 넘기지 않는다. 직접 호출과 `/fz` 경유가 같은 게이트로 판정된다 (2026-11-12 · 이전 규칙 'Phase 4 에서 고른 추천 모드를 인자로'와 'Phase 4 역전 불가'를 갈음)
- GPT 모델·effort 질문은 이 AskUserQuestion 에 합친다(GPT 를 부를 수 있는 파이프라인에서 `gpt-choice.sh get` 이 묻기로 나올 때) — 판정·질문 형식 정본 `modules/gpt-strategy.md` § 모델·effort 선택
- ⛔ AskUserQuestion 한 번은 **최대 4문항**이다 — 파이프라인 · 범위 확인 질문에 GPT 두 질문을 더해 넘치면 정본 규칙대로 나눈다
- ⛔ 파이프라인 승인 질문의 header 는 `Phase 4` 로 고정한다. 승인 = 제시한 선택지 중 커스텀이 아닌 것을 고른 답이다. 범위 확인 · GPT 질문은 다른 header 를 쓴다(승인이 아니다). 커스텀 구성 · 자유 입력으로 답하면 변경안을 반영해 **다시 Phase 4 질문으로** 묻는다 — 그 답은 아직 승인이 아니다
- 기계 강제 = fz-guard(설치한 머신 · `mods/fz-guard`). 설치돼 있으면 `/fz` 뒤 이 승인 전의 쓰기 · Workflow 가 deny 되고, 승인 없이 끝나는 턴의 Stop 이 1회 막힌다. 설치되지 않은 머신에서는 이 규칙이 절차로만 남는다

---

## 적극적 확인 원칙 (Step 8)

**파이프라인 제안 전 의도 재확인** — 다음 조건에서 파이프라인 제안 전에 먼저 묻는다:
- 요청 길이 < 10글자
- 동사 없음 (명사/키워드만)
- 애매한 동사 ("봐줘", "해줘" 등 대상 불명확)

**범위 확인** — TEAM 모드 + 5개+ Step 예상 시:

```
Q: "이 작업의 범위를 확인합니다"
옵션:
  1. 전체 파이프라인 ({N} Steps) 실행 (Recommended)
  2. 첫 번째 스텝만 먼저 실행
  3. 계획만 보여주고 각 Step 개별 승인
```

**중단 없이 자동 실행 금지 조건** (반드시 멈추고 질문):
- 코드 변경 범위가 예상보다 넓어질 때 (5개+ 파일 변경 감지)
- 파이프라인 외 추가 스킬이 필요할 때
- Gate 실패 시 (재시도/스킵/중단 반드시 선택)

---

## 권고 Default 정책 (Lead Action Default 적용)

> **Default = action with proportional verification** (참조: `modules/lead-action-default.md`).

**Implementation-ready 시점부터 권고 default = implementation**. verify 우선 권고는 사용자 명시 안전 우려 시에만.

### 권고 표시 규칙

| 상황 | First Option (Default) | Second Option |
|------|---------------------|---------------|
| verify `approved`/`conditional-minor` | **Implementation 진입** (v{N+1} 자동 작성 금지, 18차와 동일 강도) | 사용자 명시 추가 verify 요청 시 |
| verify `needs_revision` | Plan v{N+1} (18차 3회 한도) | 사용자 에스컬레이션 |
| 연속 메타 작업 ≥ 2회 (학습/정식화/SKILL.md 강화) | **Implementation 사이클로 복귀** | 사용자 명시 메타 작업 결정 시 |

> 33차 출처: `Recommendation Default Bias 교훈` (Recommendation Default Bias)

---

## 관련 모듈

- `modules/complexity.md` — TEAM/SOLO 모드 점수 산정
- `modules/pipelines.md` — 파이프라인 프리셋
- `modules/team-registry.md` — 에이전트-역할 매핑
