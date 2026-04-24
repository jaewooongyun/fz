# RELEASE NOTES v4.1.0 — Call-Site Deprecation Audit + Function Responsibility Audit

> Release Date: 2026-04-21
> Previous: v4.0.0 (2026-04-21)
> Bump Type: **MINOR** (backward-compatible 에이전트 확장)

---

## 🎯 핵심 요약

ASD-1111 회귀 분석에서 도출된 **"함수 이름 ≠ 함수 책임 + 호출 중단 ≠ 정의 제거"** 패턴을 fz 생태계로 반영. `plan-impact` 에이전트의 Exhaustive Impact Scan을 `a~f` → `a~g`로 확장하고, `review-correctness` 에이전트에 Function Responsibility Audit를 추가.

v1~v5 4회 needs_revision 반복 후 **18차 반성 (Scope Inflation 방어) 4 규칙** 적용으로 scope 축소하여 Codex approved 도달. v5.3 approved plan을 문자 그대로 구현.

---

## 🆕 새로운 검증 절차

### 1. `agents/plan-impact.md` §g Call-Site Deprecation Audit

기존 Exhaustive Impact Scan (a~f) 다음에 항목 g 추가:

```markdown
g. Call-Site Deprecation Audit (호출 중단 / 함수 body 제거 시 필수):
   함수 정의 자체가 아닌 호출 사이트가 제거되는 경우도 책임 silent disappearance 위험.
   1. Grep("funcName\(") → 현재 호출자 수 N
   2. 이전 호출자 수 M을 git 비교 (Lead가 git 조회 후 artifact 제공)
   3. N < M 감지 → 제거된 call-site의 원본 body 점검
   4. 대응 없는 책임 → "responsibility_gap" 플래그 (severity: Critical)
```

**발동 조건**: 계획 단계에서 함수 body 제거 또는 call-site 제거가 감지되면 자동 실행.

### 2. `agents/review-correctness.md` §2 Function Responsibility Audit

§2 Logic Correctness bullet로 추가:

```markdown
- Function Responsibility Audit (함수 제거 / 호출 중단 감지 시):
  1. Lead에게 SendMessage로 원본 body 요청 (Team agent Bash 없음 — agent-team-guide.md §1 준수)
  2. Lead가 PR base ref (`origin/{base}` 또는 `git merge-base HEAD @{upstream}`)를 resolve
     하여 `git show ${BASE_REF}:filepath` 실행 후 artifact 전달
     (⛔ `HEAD^` 하드코딩 금지 — stacked/multi-commit 리뷰에서 잘못된 baseline 위험)
  3. 원본 body를 조건 분기 1개 = 책임 1개로 분해
  4. Scalability: ≤20줄 자동, 21-100 sampling + AskUserQuestion, 100+ 에스컬레이션
  5. After diff에서 각 책임 대응 코드 추적
  6. 대응 없는 책임 → "missing_responsibility" (severity: Critical)
```

**원칙**: 함수명이 helper-like(`extractBody`, `parseHeader`)여도 body의 실질 책임 목록이 기준.

### 3. `skills/fz-plan/SKILL.md` 일관성 업데이트

TeamCreate 설명 + Round 1 병렬 분석 텍스트에서 `Impact Scan (a~f)` → `(a~g)` 2곳.

---

## 📚 배경: ASD-1111 회귀

D2(ASD-1002) fix 커밋 `ceb1666b5`에서 `extractBody` 헬퍼의 **호출을 중단**하면서, 그 함수 body 안의 `header.status 3xx-5xx` 검사 책임이 Serializer 층으로 이전되지 않음. 18+ LegacyResponse 소비자가 세션 만료(401) / 서버 에러(500)를 silent success로 처리하는 회귀 발생.

**관찰**: Claude 7개 에이전트 + self-review 모두 두 번 미발견. Codex GPT-5.4 단독 두 차례 발견.

→ v4.1에서 plan-impact / review-correctness에 책임 분해 절차 추가. `/fz-plan` + `/fz-review` 실행 시 자동 활용.

---

## 🛠 구현 노트: 18차 반성 적용

이번 릴리즈는 v1~v4 4회 `needs_revision` 반복 후 **18차 반성 (Scope Inflation 방어)** 4 규칙 등록 후 작성된 첫 계획:

| 규칙 | 적용 |
|------|------|
| 1. Complexity Drift 자동 감지 | v4 complexity 19 → v5 7 (축소) |
| 2. Self-Assessment Blindness 방어 | `[verified: 리터럴 명령어 출력]` 태그 의무 |
| 3. Additive-Only 금지 | v5에서 v4의 13개 Step DEFERRED |
| 4. Codex 3회 한도 | 4회째 사용자 에스컬레이션 경로 |

Codex verify 여정: v1~v4 needs_revision → v5 Major 2 → v5.1 Major 1 → v5.2 Major 0 → **v5.3 APPROVED (Q1-Q8 전체 pass, Issues 0)**.

---

## 📦 변경 파일

```
agents/plan-impact.md        | 13 ++++++++++++-
agents/review-correctness.md | 10 ++++++++++
skills/fz-plan/SKILL.md      |  4 ++--
3 files changed, 24 insertions(+), 3 deletions(-)
```

---

## 🚫 DEFERRED 항목 (별도 릴리즈)

v5 plan에서 명시적으로 분리한 항목 — 향후 별도 ASD 티켓으로 처리:

- Helper-A Lead-Owned Baseline Resolution 모듈
- Helper-B Codex Degraded Gate 모듈
- Plan-to-Source Verification Gate 4.5.5
- Edge Case Enforcement 5 cases (Plan-less / SOLO / 20+ 줄 / Renamed / Non-Plan-Citing)
- `/fz-manage propagate-lessons` (Lessons-to-Module 파이프라인)
- Trigger Precedence & Deduplication (T6/T7/T-new)
- Origin-Behavior Fallacy (lead-reasoning §1.5 Fallacy #5)
- Atomic Rewrite (cross-validation Reflection Rate + fz-review/fz-plan Codex gate 동시 업데이트)
- SKILL.md Module Split (500줄 제한)

**근거**: harness-engineering §7 "단일 ablation 결과로 규칙 만들지 않는다" + 18차 규칙 1 "complexity 2배+ 분할 트리거" 준수. 1건 회귀(ASD-1111) 기반 과적합 방지.

---

## 🔬 검증 이력

| 단계 | 검증자 | Verdict | 이슈 |
|------|:------:|:-------:|:---:|
| v1 plan | Codex GPT-5.4 | needs_revision | Major 4 |
| v2 plan | Codex GPT-5.4 | needs_revision | Major 5+Minor 1 |
| v3 plan | Codex GPT-5.4 | needs_revision | Major 3+Minor 2 |
| v4 plan | Codex GPT-5.4 | needs_revision | Major 4+Minor 1+Sugg 1 |
| v5 plan | Codex GPT-5.4 | needs_revision | Major 2+Minor 2 |
| v5.1 plan | Codex GPT-5.4 | needs_revision | Major 1+Minor 1 |
| v5.2 plan | Codex GPT-5.4 | needs_revision | Minor 1 |
| **v5.3 plan** | Codex GPT-5.4 | **approved** | **0** |
| 구현 check --deep | Codex xhigh | approved | P2 2 (DEFERRED 범위) |
| 구현 validate | Codex GPT-5.4 | approved | Reflection Rate 100% |

---

## 🔗 관련 분석 산출물

분석/계획/검증 문서 (외부 TVING/ASD-1111 폴더):
- `review/regression-root-cause-analysis.md` — 7 시스템 패턴 + git 실측 교정판
- `analysis/fz-ecosystem-gap-analysis.md` — Gap 매트릭스 + 4-Agent TEAM 분석
- `plan/fz-ecosystem-improvement-plan-v{1-5}.md` — 계획 5회 이터레이션
- `plan/verify-result{,-v2,-v3,-v4,-v5,-v5.1,-v5.2,-v5.3}.md` — Codex verify 8회

---

## 📌 마이그레이션

**없음** — backward-compatible. 기존 /fz-plan, /fz-review 사용자는 자동으로 새 검증 절차 활용.

---

## 👤 Credits

- **근본 원인 발견**: Codex GPT-5.4 (D3 --deep review + ASD-1111 1차 review 단독 발견)
- **메타 분석**: 4-Agent TEAM (review-direction Opus + review-counter + memory-scout + plan-structure Sonnet)
- **Scope Inflation 방어 설계**: v1~v4 실패 경험 축적 → 18차 반성
- **최종 검증**: Codex GPT-5.4 (9회 verify 라운드)
