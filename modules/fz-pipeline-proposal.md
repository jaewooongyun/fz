# fz Pipeline Proposal — 사용자 확인 시각화

> **Scope of Applicability**: `/fz` 오케스트레이터 Phase 4 (User Confirmation) 전용. 다른 스킬에서 유사한 확인 단계가 필요하면 표 컬럼(스킬/역할/실행자/모델)과 범위 확인 임계치(5 Step)가 해당 스킬에 맞는지 먼저 검토.
>
> **Purpose**: 결정된 파이프라인·팀 구성·모델 배정을 사용자에게 제시하고 승인을 받기 위한 표준 시각화 형식.

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
| 3 | ✓ codex check | 교차 검증 | Lead | codex |
| 4 | /fz-review | 아키텍처 리뷰 | review-arch | sonnet |
| 5 | /fz-review | 품질 리뷰 | review-quality | sonnet |
| 6 | /fz-commit | 커밋 | Lead | opus |

**에이전트**: Lead(O) + impl-correctness(★O) + review-arch(S) + review-quality(S)
```

> ✓ 접두사: 자동 삽입된 검증 게이트. ★: Primary Worker (opus).

---

## AskUserQuestion 선택지

> **Default 결정 알고리즘** (review-arch MUST-1 + Codex 검증 §5 MUST-1 합의):
> Phase 4가 Phase 3 결정을 *역전하지 않는다*. Phase 4는 *추가 선택지 제시*만.

### Phase 4 Default 결정 알고리즘

| 조건 | Phase 4 First Option (Default) | 비고 |
|------|------------------------------|------|
| Phase 3 결정 = TEAM (complexity ≥ 4) | **TEAM (Phase 3 추천 유지)** | SOLO는 2번 선택지 ("위험 감수 SOLO 시작") |
| Phase 3 결정 = SOLO + 40차 신호 매칭 (lead-action-default.md) | **SOLO + minimal** | TEAM은 2번 선택지 |
| 사용자 `--deep` / `--team` 명시 | **사용자 명시 선택 유지 (override)** | Lead 재권장 금지 |

### 선택지 형식 (조건별)

**단순 요청 컨텍스트** (Phase 3 SOLO + 40차 매칭):
```
1. SOLO + minimal (Default — 단순 요청)
2. TEAM (확장 검증 필요 시)
3. 커스텀 구성
```

**복잡 / 명시 컨텍스트** (Phase 3 TEAM 또는 --deep/--team override):
```
1. [Phase 3 추천] (Recommended)
2. 모드 변경 (TEAM ↔ SOLO)
3. 커스텀 구성
```

### 규칙

- ⛔ 사용자 명시 선택 후 Lead 재권장 금지 (edge-cases Failure 4-2 완화)
- ⛔ "Default = SOLO + minimal은 시작점이지 *상한 아님*" — complexity 또는 catch 누적 신호 시 TEAM 자동 전환 (Failure 4-3 완화)
- ⛔ Phase 3 TEAM 결정 시 Phase 4가 SOLO로 *역전 금지* (review-arch MUST-1)

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

> 33차 출처: `feedback_recommendation_default_bias.md` (Recommendation Default Bias)

---

## 관련 모듈

- `modules/complexity.md` — TEAM/SOLO 모드 점수 산정
- `modules/pipelines.md` — 파이프라인 프리셋
- `modules/team-registry.md` — 에이전트-역할 매핑
