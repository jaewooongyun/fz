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
| code-changes 생산 (제거/리팩토링) | implication-scan | lead-reasoning.md § Implication Scan | 모든 모드 (1차/2차 트리거) |
| code-changes 생산 (모든) | Q-OBSERVE 경량 | lead-reasoning.md § 상시 경량 | 모든 모드 (상시) |
| revert 작업 | origin-equivalence | lead-reasoning.md + cross-validation.md § origin-equivalence | 모든 모드 (revert 키워드) |
| planning 생산 전 | 방향성 검증 | review-direction 에이전트 (Phase 0.5) | TEAM (fz-plan) |
| planning 생산 전 | 교훈 회상 | memory-curator (memory-recall) | 모든 TEAM |
| code-changes 생산 전 | 교훈 회상 | memory-curator (memory-recall) | 모든 TEAM |
| review 시작 전 | 교훈 회상 | memory-curator (memory-recall) | 모든 TEAM |
| planning 생산 | 계획 검증 | `fz-codex verify` (팀 내 병렬) | TEAM |
| review 포함 | 다관점 리뷰 | review-arch + review-quality + Codex (팀 내 병렬) | TEAM |
| search 포함 | 교차 검증 | search-symbolic + search-pattern + Codex (팀 내 병렬) | TEAM(--deep) |
| commit/pr 포함 | Pre-ship gate | `fz-codex check` | TEAM |
| fix 포함 | 수정 검증 | `fz-codex check` (팀 내 병렬) | TEAM |
| review 포함 | L3 에러 처리 스캔 | silent-failure-hunter (Agent background) | TEAM (diff에 에러처리 코드 포함 시) |
| review 포함 | L3 타입 설계 평가 | type-design-analyzer (Agent background) | TEAM (diff에 새 타입 정의 포함 시) |
| code-changes 생산 | SC 빌드 진단 | `/sc:troubleshoot --fix` 자동 | 빌드 2회 연속 실패 시 |
| planning 생산 | SC 공수 추정 | `/sc:estimate --breakdown` | plan + 복잡도 4+ |
| review 포함 | L3 결과 팀 피드백 | Lead → Primary SendMessage (team-core.md L3-to-L1) | TEAM (L3 이슈 1건+ AND Round 0.5 전) |
| code 포함 | Supporting 진행도 체크 | review-correctness → impl-correctness RTM 체크 | TEAM (3+ Step 50% 시점) |
| review 시작 전 | Scope Expansion 검증 | plan 영향 범위 ⊇ discover 범위 확인. plan이 더 좁으면 warning | discover 산출물 존재 시 |
| code 시작 전 | 시야 축소 감지 | plan 영향 범위 vs discover 범위 비교 → 좁으면 마찰 신호 | discover 산출물 존재 시 |

---

## 검증 게이트 자동 삽입 규칙

### 코드 생산 파이프라인

```
[코드 생산 스텝] → build → conformance (시그니처 변경 시) → enforcement (리팩토링 시) → consumer quality (모듈화 시) → implication-scan (제거/리팩토링 시) → codex check (TEAM) → [다음 스텝]

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

## 외부 모델 포함 원칙 (TEAM 필수)

> 핵심: TEAM = Claude 에이전트(N) + Codex(1). 코드/계획 생산 TEAM에 Codex 필수.
> 근거: X-MAS(arxiv 2505.16997) — 이종 모델 2개 조합으로 대부분의 이득 달성.

| 스킬 | Codex | Codex 스킬 |
|------|-------|-----------|
| /fz-plan | `fz-codex verify` | architect |
| /fz-code | `fz-codex check` | reviewer |
| /fz-review | `fz-codex validate` | guardian |
| /fz-fix | `fz-codex check` | reviewer |
| /fz-search | `fz-codex` | searcher |

> Codex 3-Tier 디스커버리: CLAUDE.md `## Codex Skills`(Tier 1) → 글로벌 fz-*(Tier 2) → 인라인(Tier 3).

---

## Cross-Model Verification (2-Model)

Claude + Codex(GPT-5.4) 교차 검증:

| 트리거 | 프로바이더 | Effort |
|--------|-----------|--------|
| code-changes (TEAM) | Codex check | high |
| planning (TEAM) | Codex verify | high |
| final / --deep | Codex | xhigh |
| 불일치 시 | AskUserQuestion | 사용자 판단 |

### Disagreement 기록
- ASD 활성: `{WORK_DIR}/verify/consensus-{날짜}.md`
- 비ASD: `write_memory("fz:consensus:result", "합의/불일치 요약")`

---

## 경량 검증 게이트

| 모드 | 코드 생산 후 검증 | 계획 생산 후 검증 |
|------|-----------------|-----------------|
| SOLO | 빌드만 | 없음 (Lead 직접 판단) |
| TEAM | 빌드 + Codex check (gpt-5.4+high) + 에이전트 확인 | Codex verify (gpt-5.4+high) |
| TEAM --deep | 빌드 + Codex (gpt-5.4+xhigh) | Codex verify (xhigh) |

> Effort 정의: `modules/codex-strategy.md` 참조. 기본 high, final/--deep은 xhigh. Review Gate OFF.

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
  # Tier 2a: ~/.codex/skills/ (기존 설치 또는 심볼릭 링크)
  if [ -d "$HOME/.codex/skills/fz-${ROLE}" ]; then
    echo "fz-${ROLE}"; return
  fi
  # Tier 2b: ~/.claude/codex-skills/ (repo 포함본 — 폴백)
  if [ -d "$HOME/.claude/codex-skills/fz-${ROLE}" ]; then
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
| modules/lead-reasoning.md | Implication Scan + origin-equivalence 추론 원칙 |
| modules/system-reminders.md | Instruction fade-out 대응 트리거 정책 |

## Codex 검증 결과 보존 정책

> 1M context 활용: 요약 + 원본 분리 (Progressive Disclosure)

- **ASD 활성**: `verify-result.md` (요약 3K, Hydration 대상) + `verify-result-full.md` (원본, drill-down용)
- **비ASD**: Serena checkpoint 요약만 (기존 동작)
- 다음 Phase 스킬은 `verify-result.md` 요약을 Read. 상세 확인 시 `-full.md` drill-down.

---

## Implication Scan 게이트

> 참조: `modules/lead-reasoning.md` — 추론 원칙, 카테고리 분류, 자문 체크리스트, Register 형식

### 트리거

- **1차**: 제거/삭제/이동/이관/마이그레이션/리팩토링/DI변경/revert
- **2차**: 프로토콜/access control/init·signature/모듈경계 변경
- **상시**: Q-OBSERVE (모든 코드 변경에서 경량 스캔)

### 파이프라인 위치

```
planning 후 → [implication-map] → stress-test → codex verify
code-changes 후 → build → [implication-scan] → codex check
```

### 절차

1. `lead-reasoning.md` 자문 체크리스트 실행 (Q-WHY/Q-COMPLETE/Q-EFFECT)
2. `find_referencing_symbols` → 변경 심볼의 참조자 중 "이 변경을 위해 추가된" 코드 식별
3. 실행 함의 발견 → [함의-A] 보고 + 사용자 확인
4. 관찰 함의 발견 → [함의-B] 기록 (최대 2건, 출력은 Gate 완료 시)

---

## origin-equivalence 게이트 (revert 전용)

> 트리거: "되돌리기", "revert", "원상복구", "undo", "롤백"

⛔ 되돌릴 대상 = "키워드"가 아닌 "원본 상태 전체"

1. 원본 커밋/상태 식별 (`git show {commit}^` 또는 기준 파일)
2. 범위 = 대상 커밋이 추가한 모든 변경 (상태 복원)
3. 완료 기준: 원본과의 동등성 확인

체크리스트:
- [ ] 원본 상태를 정확히 식별했는가?
- [ ] 키워드 기반이 아닌 상태 기반으로 범위 정의했는가?
- [ ] 원본과의 동등성(origin-equivalence) 확인했는가?

---

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 모듈이므로 줄 수 제한 없음
