# 교차 검증 주입 전략

> fz Phase 3에서 파이프라인에 검증 게이트를 자동 삽입. 모든 모드에서 최소한의 검증 보장.
> 핵심 원칙: TEAM = Claude 에이전트(N) + Codex(1). 코드/계획 생산 TEAM에 Codex CLI 필수 참여. 탐색 파이프라인은 --deep만.

## 검증 유형별 전략

| 파이프라인 카테고리 | 검증 유형 | 메커니즘 | 모드 조건 |
|-------------------|----------|---------|----------|
| code-changes 생산 | 빌드 검증 | modules/build.md 절차 | 모든 모드 |
| code-changes 생산 | simplify check (선택) | /simplify | 모든 모드 |
| code-changes 생산 | Codex check | `fz-codex check` (팀 내 병렬) | TEAM |
| code-changes 생산 (리팩토링) | enforcement 검증 | Anti-Pattern Grep + Module Boundary | 모든 모드 (Plan에 Constraints 있을 때) |
| code-changes 생산 (모듈화/캡슐화) | consumer quality 검증 | 소비자 파일 전수 수집 + 사용 패턴 + 진입점 검증 | 모든 모드 (모듈화 작업 시) |
| code-changes 생산 (시그니처 변경) | protocol conformance 검증 | find_referencing_symbols → 프로토콜 요구사항 양방향 확인 | 모든 모드 |
| code-changes 생산 (init 변경) | inheritance DI conformance | base_class_hierarchy → subclass init + 화면별 dependency 확인 (Gate 4.6.5) | 모든 모드 (init 변경 시) |
| planning 생산 전 | 방향성 검증 | review-direction 에이전트 (Phase 0.5) | TEAM (fz-plan) |
| planning 생산 전 | 교훈 회상 | memory-curator (memory-recall) | TEAM (--deep 또는 복잡도 4+) |
| code-changes 생산 전 | 교훈 회상 | memory-curator (memory-recall) | TEAM (--deep 또는 복잡도 4+) |
| review 시작 전 | 교훈 회상 | memory-curator (memory-recall) | TEAM (--deep 또는 복잡도 4+) |
| planning 생산 | 계획 검증 | `fz-codex verify` (팀 내 병렬) | TEAM |
| review 포함 | 다관점 리뷰 | review-arch + review-quality + Codex (팀 내 병렬) | TEAM |
| search 포함 | 교차 검증 | search-symbolic + search-pattern + Codex (팀 내 병렬) | TEAM(--deep) |
| commit/pr 포함 | Pre-ship gate | `fz-codex check` | TEAM |
| fix 포함 | 수정 검증 | `fz-codex check` (팀 내 병렬) | TEAM |

---

## 검증 게이트 자동 삽입 규칙

### 코드 생산 파이프라인

```
[코드 생산 스텝] → build → conformance (시그니처 변경 시) → enforcement (리팩토링 시) → consumer quality (모듈화 시) → codex check (TEAM) → [다음 스텝]

예시 (fix-ship, TEAM):
  /fz-fix → build → codex check → /fz-commit → /fz-pr

예시 (plan-to-code, 리팩토링, TEAM):
  /fz-plan → codex verify → /fz-code → build → enforcement → codex check

예시 (quick-fix, SOLO):
  /fz-fix → build → 완료 (codex check 생략)
```

> enforcement: Plan에 Anti-Pattern Constraints가 있을 때만 삽입.

### 계획 생산 파이프라인

```
memory-recall (TEAM, informational) → direction challenge (TEAM, fz-plan Phase 0.5) → [계획 스텝] → codex verify (TEAM) → [코드 스텝]
```

> direction challenge: review-direction 에이전트가 접근 방향 자체를 도전 (PROCEED/RECONSIDER/REDIRECT 판정).

### 리뷰 포함 파이프라인

fz-review가 이미 3중 검증을 수행하므로 추가 삽입 없음.
TEAM 모드에서는 review-arch/review-quality가 팀 에이전트로 독립 다관점 분석.

---

## Codex 포함 원칙 (TEAM 필수)

모든 TEAM 스킬에 Codex CLI 참여. 파이프라인 게이트(후행)가 아닌 팀 내 병렬 검증자로 참여.

| 스킬 | Codex 서브커맨드 | 역할 | Codex 스킬 (3-Tier) |
|------|----------------|------|-------------------|
| /fz-plan | `fz-codex verify` | 계획 타당성 검증 | architect 역할 |
| /fz-code | `fz-codex check` | 코드 품질 검증 | reviewer 역할 |
| /fz-review | `fz-codex validate` | 리뷰 역검증 | guardian 역할 |
| /fz-fix | `fz-codex check` | 수정 품질 검증 | reviewer 역할 |
| /fz-search | `fz-codex` | 독립 탐색 경로 | searcher 역할 |

> Codex 스킬은 3-Tier 디스커버리로 결정: CLAUDE.md `## Codex Skills` 매핑(Tier 1) → 글로벌 fz-*(Tier 2) → 인라인(Tier 3).

---

## 경량 검증 게이트

| 모드 | 코드 생산 후 검증 | 계획 생산 후 검증 |
|------|-----------------|-----------------|
| SOLO | 빌드만 | 없음 (Lead 직접 판단) |
| TEAM | 빌드 + Codex check + 에이전트 확인 | Codex verify + Lead 검토 |

---

## Reflection Rate

**계산식**: Reflection Rate = (Codex가 제기한 이슈 N개 중 Claude가 수정 반영한 수) / N × 100%

| 모드 | Reflection Rate 추적 | 기준 |
|------|---------------------|------|
| SOLO | 추적 없음 | 사용자 직접 판단 |
| TEAM | Reflection Rate >= 80% | fz-review 메커니즘 적용 |

> 예시: Codex가 이슈 5개 제기 → Claude가 4개 수정 반영 → 80% (PASS)

---

## Gate 절차적 강제

검증 게이트는 "권고"가 아닌 **절차적 강제**다. 스킵 불가 조건:

| 게이트 | 강제 수준 | 스킵 조건 |
|--------|----------|----------|
| build | **필수** (코드 변경 시) | 코드 변경 없는 문서 전용 파이프라인만 예외 |
| codex check | **필수** (TEAM 코드/계획) | SOLO 모드 또는 탐색(--deep 없음) |
| stress-test | **필수** (fz-plan) | discover 결과에서 이미 검증된 제약은 재검증 생략 |
| Reflection Rate | **필수** (TEAM review) | SOLO 모드 |

Gate 실패 시: 해당 단계를 "완료"로 표시할 수 없다. 반드시 재시도/수정/사용자 에스컬레이션 중 하나를 수행해야 한다.

## 품질 에스컬레이션

| 상황 | 모드 | 대응 |
|------|------|------|
| 빌드 실패 | 모든 모드 | /ralph-loop 에스컬레이션 래더 (modules/execution-modes.md) |
| codex check 실패 | TEAM | 에이전트에게 이슈 전달 → 수정 → 재검증 |
| 검증 실패 (반복) | SOLO | 사용자에게 `/fz-review` 제안 |
| Reflection Rate < 60% | TEAM | /ralph-loop 래더 → 한도 후 사용자 에스컬레이션 |

---

## 검증 게이트 시각화

Phase 4(User Confirmation)에서 검증 게이트도 함께 표시.

```markdown
| # | 스킬 | 역할 | 실행자 | 모델 |
|---|------|------|--------|------|
| 1 | /fz-plan | 구현 계획 | plan-structure | opus |
| 2 | codex verify | 계획 검증 | Lead | codex |
| 3 | /fz-code | 점진적 구현 | impl-correctness | opus |
| 4 | build | 빌드 검증 | Lead | — |
| 5 | codex check | 교차 검증 | Lead | codex |
| 6 | /fz-commit | 커밋 | Lead | opus |
```

---

## 공유 유틸리티

> 분리 후보: 3개+ 스킬에서 참조 시 독립 `modules/shared-utils.md`로 추출 검토 (governance.md 모듈 분리 기준 참조)

### GIT_ROOT 추출

```bash
GIT_ROOT_REL=$(grep -A 5 "^## Directory Structure" CLAUDE.md 2>/dev/null | \
  grep -i "git.root" | awk -F: '{print $2}' | xargs)
GIT_ROOT="${GIT_ROOT_REL:-.}"
```

### get_codex_skill() — 3-Tier 디스커버리

```bash
get_codex_skill() {
  local ROLE=$1
  local PROJECT_ROOT="$(pwd)"
  local SKILL=$(grep -A 20 "^## Codex Skills" "${PROJECT_ROOT}/CLAUDE.md" 2>/dev/null | \
    grep "| $ROLE " | awk -F'|' '{print $3}' | xargs)
  if [ -n "$SKILL" ] && [ -d "$HOME/.codex/skills/$SKILL" ]; then
    echo "$SKILL"; return
  fi
  if [ -d "$HOME/.codex/skills/fz-${ROLE}" ]; then
    echo "fz-${ROLE}"; return
  fi
  echo ""
}
```

Tier 1: CLAUDE.md `## Codex Skills` 테이블 → Tier 2: 글로벌 `fz-*` → Tier 3: 인라인 프롬프트.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-codex | 검증 게이트 + get_codex_skill() 3-Tier 디스커버리 |
| /fz | 파이프라인 검증 게이트 자동 삽입 |

## Codex 검증 결과 보존 정책

> 1M context 활용: 요약 + 원본 분리 (Progressive Disclosure)

- **ASD 활성**: `verify-result.md` (요약 3K, Hydration 대상) + `verify-result-full.md` (원본, drill-down용)
- **비ASD**: Serena checkpoint 요약만 (기존 동작)
- 다음 Phase 스킬은 `verify-result.md` 요약을 Read. 상세 확인 시 `-full.md` drill-down.

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
