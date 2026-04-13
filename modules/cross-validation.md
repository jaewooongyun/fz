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
| planning 생산 (패턴 변환) | transformation spec | code-transform-validation.md Spec 작성 + Context7 확인 | 모든 모드 (패턴 변환 시) |
| code-changes 생산 (패턴 변환) | behavioral equivalence | Spec 대비 구현 대조 (스레드/에러/추상화) | 모든 모드 (Spec 있을 때) |
| review 포함 (패턴 변환) | transformation equivalence (4-K) | Spec 대비 diff 대조 | 모든 모드 (Spec 있을 때) |
| planning 생산 (Spec v3.8) | spec-verify | Codex가 Spec의 기술적 정확성 검증 (스레드 모델, 파라미터 의미론, Default-Deny) | TEAM 필수, SOLO 권장 |
| cross-model 불일치 감지 | confident-error | Claude vs Codex 판정 불일치 → 교훈 기록 + 상세 분석 (uncertainty-verification.md) | 자동 |
| code/review (Spec v3.8) | default-deny enforcement | Spec 기술적 주장에 [verified] 없으면 fail-closed | 모든 모드 (spec-version 3.8) |
| 외부 피드백 수신 시 | external-feedback-verify | Read(시그니처) + 기존 패턴 대조 → valid/invalid 판정 | 모든 모드 |
| 런타임 동작 단정 시 | runtime-claim-verify | Bash Swift 스크립트 실행 또는 "미검증" 표기 | 모든 모드 [관찰] |

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
  # Tier 2b: codex-skills/ (플러그인 포함본 — 폴백, 심볼릭 링크 설치 시 Tier 2a에서 해결)
  local PLUGIN_CODEX="$(cd "$(dirname "${BASH_SOURCE[0]}")/../codex-skills" 2>/dev/null && pwd)"
  if [ -n "$PLUGIN_CODEX" ] && [ -d "$PLUGIN_CODEX/fz-${ROLE}" ]; then
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

## 외부 피드백 검증 (External Feedback Gate)

> 하네스 원칙 4 적용: Generator≠Evaluator — 외부 피드백에 결정론적 검증 삽입

트리거: CodeRabbit, Codex, 팀원이 "파라미터 누락/타입 불일치/동작 변경" 지적 시
⛔ diff만 보고 동의/반박 금지.

절차:
1. Read(해당 함수 시그니처) — 오버로드 구분 포함
2. 기존 동일 패턴(이전 PR, 같은 시리즈 이전 커밋) 대조
3. 판정: valid / invalid / needs-investigation + 근거 1줄

**Why:** ASD-1002 세션에서 CodeRabbit이 "includeGradeCode: false 누락" 지적 → diff만 보고 수긍 → 실제로 LegacyResponse 오버로드에 해당 파라미터가 존재하지 않았음. 같은 세션에서 2건 발생.

---

## 런타임 동작 주장 검증 (Runtime Claim Gate) [관찰 모드]

> 하네스 NLAH-A: 비결정론적 추론 → 결정론적 어댑터(Bash) 교체

트리거: "~는 안전하다", "~로 변환된다", "타입 캐스팅이 ~" 등 런타임 동작 단정
조건: Swift 타입 시스템, Foundation API 동작, NSNumber 브리징 등 저수준 주장

절차:
1. 가능하면 Bash Swift 스크립트로 실제 실행하여 확인
2. 실행 불가능하면 → "미검증 (추론)" 표기 후 사용자에게 고지

> [관찰 모드]: 단일 사건(ASD-1002 castToSendable)에서 도출. 하네스 과적합 방지 원칙에 따라 2건+ 재발 시 lead-reasoning.md §8로 강화.

**Why:** castToSendable의 Bool/Int 변환 안전성을 직관으로 "안전하다" 판단 → 취소 → Bash 테스트로 위험 확인. 실행 검증이 있었으면 1번에 끝났음.

---

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 모듈이므로 줄 수 제한 없음
