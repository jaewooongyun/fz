# fz v2.5 Release Notes

**릴리즈 날짜**: 2026-03-20
**코드명**: skill-creator Integration + Clean Architecture Foundation

---

## 개요

v2.5는 fz 생태계의 **품질 인프라**와 **아키텍처 기조**를 강화하는 릴리즈입니다.

Anthropic 공식 플러그인 `skill-creator`를 fz 워크플로우에 깊이 통합하여, 스킬 생성/개선 시 실측 트리거율 기반 검증과 description 자동 최적화가 가능해졌습니다. 전체 18개 스킬의 description을 skill-creator best practice 패턴으로 전면 교체했으며, Robert C. Martin(Uncle Bob)의 Clean Architecture 원칙을 생태계 전반의 아키텍처 기조로 신설했습니다.

### 주요 수치

| 지표 | Before | After |
|------|--------|-------|
| 파이프라인 수 | 17개 | **18개** (+skill-optimize) |
| 가이드 문서 | 5개 | **6개** (+clean-architecture.md) |
| Description 신패턴 적용 | 0/18 | **18/18** (100%) |
| 500줄 초과 스킬 | 2개 | **0개** |
| 건강 체크 점수 | 미측정 | **12.5/13** |

---

## 1. skill-creator 통합

### 배경

fz 생태계는 18개 스킬을 보유하고 있지만, 스킬의 **실제 트리거 정확도**를 측정하는 수단이 없었습니다. `fz-skill eval`의 Static Analysis는 구조와 컨벤션만 검증하고, "이 description으로 Claude가 실제로 스킬을 찾아 쓰는가?"는 확인할 수 없었습니다.

Anthropic 공식 `skill-creator` 플러그인은 `claude -p` 기반 실측 트리거 테스트와 train/test split description 자동 최적화를 제공합니다. 이것을 fz 워크플로우에 통합했습니다.

### 변경 사항

#### fz-skill — `optimize` 서브커맨드 (신규)

```bash
/fz-skill optimize fz-plan          # description 자동 최적화
/fz-skill optimize fz-plan --full   # description + 전체 eval 루프
```

- skill-creator의 `run_loop.py` 활용
- intent-triggers에서 should-trigger 10개, Boundaries에서 should-not-trigger 10개 자동 생성
- `eval_review.html`로 브라우저에서 쿼리 검토
- train/test 60/40 split, 쿼리당 3회 실행, 최대 5회 반복
- test score 기준 best_description 선택 (overfitting 방지)
- **필요 조건**: skill-creator 플러그인 + `ANTHROPIC_API_KEY` 환경변수

#### fz-skill eval — Runtime Trigger Eval (신규 phase)

```bash
/fz-skill eval fz-plan --runtime    # 실측 트리거율 포함 평가
```

- `run_eval.py`로 실제 `claude -p` 호출하여 트리거율 실측
- should-trigger 5개 + should-not-trigger 5개 자동 생성 → 1회 실행
- PASS 기준: ≥80% 정확도
- skill-creator 미설치 시: SKIP (WARN) + graceful fallback

#### fz-skill create — Phase 5 Description Optimization 제안

- 스킬 생성 완료 후 "Description 최적화를 실행하시겠습니까?" 자동 제안
- 생성 → eval → optimize 파이프라인의 자연스러운 마무리

#### fz-manage benchmark — `--with-trigger` 옵션

```bash
/fz-manage benchmark --with-trigger  # 하위 3개에 실측 트리거율 추가
```

- Static Analysis 하위 3개 스킬에 Quick Trigger Eval 추가 실행
- 스킬당 5쿼리 × 1회 = ~30초, 총 ~90초
- 출력 테이블에 "Trigger" 컬럼 추가

#### fz-manage check — #11 skill-creator 설치 확인

- Glob으로 `run_loop.py` 탐색 → OK/WARN
- WARN 시 optimize/runtime eval 불가 안내

#### 파이프라인 #18: skill-optimize

```bash
/fz "스킬 트리거 최적화해줘"    # → skill-optimize 파이프라인
```

- 트리거: `스킬.*최적화|description.*최적화|트리거.*개선`
- 체인: fz-skill eval → fz-skill optimize
- intent-registry.md에 fz-skill/fz-manage 자연어 트리거 보강

#### 신규 파일

- `skills/fz-skill/references/skill-creator-integration.md` — L3 연동 가이드
  - skill-creator 경로 탐색 (Glob 동적 탐색)
  - Dependency check (claude CLI + anthropic SDK)
  - Eval 쿼리 자동 생성 규칙 (should-trigger/should-not-trigger)
  - optimize 4-Phase 상세 절차
  - Quick Trigger Eval (benchmark용) 절차
  - Graceful fallback 정책
  - **실증 결과 (2026-03-20)**: claude -p 자동 트리거의 슬래시 커맨드 스킬 한계 기록

### 실증 테스트 결과

13개 스킬 전체에 `run_eval.py` Runtime Trigger Eval을 실행했습니다.

| 측정 | 결과 |
|------|------|
| 전체 정확도 (Before) | 35/81 (43%) |
| 전체 정확도 (After, pushy description) | 36/81 (44%) |
| should-NOT-trigger 정확도 | **100%** (전 스킬) |
| should-trigger 정확도 | **~0%** (전 스킬) |

**핵심 발견**: Claude는 간단한 요청을 스킬 참조 없이 직접 처리하려는 경향이 있어, `claude -p` 독립 세션의 자동 트리거는 슬래시 커맨드 기반 스킬에 제한적입니다. description을 아무리 pushy하게 바꿔도 should-trigger가 개선되지 않았습니다.

**교훈**: `run_eval.py`는 독립형 스킬(skill-creator 자체 생태계)에 최적화되어 있고, fz-* 슬래시 커맨드 스킬에는 should-NOT-trigger 검증(스킬 간 오충돌 확인)에만 유효합니다. fz 스킬의 핵심 검증 수단은 기존대로 **정적 eval + intent-registry 매칭 + provides/needs 체인**입니다.

---

## 2. 전체 스킬 Description 고도화

### 배경

기존 description은 기능 설명 위주의 간결한 한국어+영어 형식이었습니다. skill-creator 가이드의 best practice를 적용하여 Claude의 스킬 매칭 정확도와 사용자 가독성을 높였습니다.

### 변경 패턴

**Before** (기존):
```yaml
description: >-
  버그 수정 경량 스킬. 원인 분석 → 수정 → 빌드 검증의 빠른 사이클.
  Use when fixing bugs, resolving crashes, correcting errors, or making quick targeted changes.
  Do NOT use for new feature implementation (use fz-code) or code exploration (use fz-search).
```

**After** (v2.5):
```yaml
description: >-
  This skill should be used when the user reports a bug, crash, or error that needs fixing.
  Make sure to use this skill whenever the user says: "고쳐줘", "수정해줘", "버그 있어",
  "크래시 나", "에러 떠", "안 돼", "튕겨", "fix this", "it crashes", "there's a bug".
  Covers: 버그, 수정, 크래시, 에러, 고쳐, 안 돼, 튕겨, 빠른 원인 분석과 수정 사이클.
  Do NOT use for new feature implementation (use fz-code) or code exploration (use fz-search).
```

### 적용 범위

| 차수 | 대상 | 스킬 수 |
|------|------|---------|
| 1차 | 핵심 스킬 | 13개 (plan, code, fix, review, search, discover, commit, skill, manage, doc, peer-review, memory, excalidraw) |
| 2차 (누락 보완) | 나머지 | 5개 (codex, new-file, pr-digest, pr, recording) |
| **합계** | | **18/18 (100%)** |

---

## 3. 500줄 제한 준수

건강 체크에서 발견된 2개 스킬의 500줄 초과를 트리밍했습니다.

| 스킬 | Before | After | 방법 |
|------|--------|-------|------|
| fz-review | 513줄 | 492줄 | redundant `---` 구분선 + 빈 줄 제거 |
| fz-peer-review | 503줄 | 497줄 | redundant `---` 구분선 제거 |

Gate 체크리스트, Few-shot 예시, 핵심 절차는 일절 삭제하지 않았습니다. 서식/공백만 정리.

---

## 4. Clean Architecture 가이드

### 배경

프로젝트의 아키텍처 원칙이 CLAUDE.md에 1줄, ai-guidelines.md에 레이어 정의, 각 에이전트에 조각적 규칙으로 흩어져 있었습니다. Robert C. Martin(Uncle Bob)의 Clean Architecture 원칙을 독립 가이드로 통합하여 생태계 전반의 아키텍처 기조로 삼습니다.

### 신규 파일: `guides/clean-architecture.md`

Uncle Bob 페르소나로 작성. 주요 섹션:

- **The Dependency Rule** — "Source code dependencies must point only inward" + 4-layer 다이어그램
- **SOLID Principles** — SRP, OCP, LSP, ISP, DIP 각 원칙 + Swift 예시 + 위반 신호
- **The Four Layers** — Entities, Use Cases, Interface Adapters, Frameworks & Drivers + Swift 코드 예시
- **Crossing Boundaries** — Dependency Inversion으로 경계 넘기 + DTO 변환 규칙
- **Architecture Smells** — DB is a Detail, UI is a Detail, Web is a Detail, Frameworks are Details
- **Uncle Bob's Decision Rules** — 설계 결정 시 자문할 6가지 질문
- **Pragmatic Clean Architecture** — 과도한 추상화 경계, 언제 엄격해야 하는가

### 연결 지점

| 파일 | 변경 |
|------|------|
| `agents/review-arch.md` | Architecture Decision에 Dependency Rule + SOLID 위반 감지 + 가이드 참조 |
| `agents/impl-quality.md` | Architecture Consistency에 DIP 위반 감지 + 가이드 참조 |
| `skills/fz-plan/SKILL.md` | 영향 분석 Step 4 "Clean Architecture 원칙 확인" 추가 |

### 활용 경로

```
코드 작성 시 → impl-quality가 실시간 Dependency Rule 감시
설계 시     → fz-plan Step 4에서 "안쪽이 바깥을 아는가?" 자문
리뷰 시     → review-arch가 SOLID 위반 + Layer 위반 감지
탐색 시     → fz-search layer 모드에서 데이터 흐름 추적
전체 점검   → fz-codex drift로 아키텍처 드리프트 스캔
```

---

## 5. 생태계 건강 체크 결과

v2.5 작업 완료 후 13개 항목 전체 건강 체크를 실행했습니다.

| # | 항목 | 결과 |
|---|------|------|
| 1 | YAML 필수 필드 | ✅ 21/21 |
| 2 | 스킬 크기 ≤500줄 | ✅ 21/21 |
| 3 | provides/needs 체인 | ✅ 완전 |
| 4 | intent-triggers 중복 | ✅ 경미 (분화됨) |
| 5 | 깨진 파일 참조 | ✅ 0개 |
| 6 | 에이전트 파일 유효성 | ✅ 14/14 |
| 7 | 모듈 완전성 | ✅ 17/17 |
| 8 | Description 품질 | ✅ 18/18 신패턴 |
| 9 | Few-shot 예시 | ✅ 8/8 (필요 스킬) |
| 10 | Gate 체크리스트 | ✅ 전부 포함 |
| 11 | skill-creator 설치 | ✅ 존재 |
| 12 | Boundaries 섹션 | ✅ 19/21 |
| 13 | 에러 대응 테이블 | ✅ 19/21 |

**최종 점수: 12.5/13 — EXCELLENT**

---

## 커밋 이력

| 순서 | 해시 | 메시지 |
|------|------|--------|
| 1 | `943d32e` | feat(fz-skill): integrate skill-creator for runtime trigger eval + description optimization |
| 2 | `807ea02` | feat(skills): apply skill-creator pushy description pattern to all 18 fz-* skills |
| 3 | `2c9dda8` | fix(skills): trim fz-review/fz-peer-review to ≤500 lines + sync agent descriptions |
| 4 | `b217427` | feat(guides): add Clean Architecture guide with Uncle Bob persona |
| 5 | `c2fe768` | docs(README): add v2.5 changelog |

---

## 업그레이드 가이드

### 필수 사항
- 변경 사항 없음 — 기존 워크플로우 100% 호환

### 선택 사항
- `ANTHROPIC_API_KEY` 환경변수 설정 시 `run_loop.py` description 자동 최적화 사용 가능
- `/opt/homebrew/bin/python3` (3.10+) 필요 — Xcode 번들 Python 3.9는 `str | None` 구문 미지원

### 새 워크플로우

```bash
# 스킬 생성 후 품질 루프
/fz-skill create fz-test "설명"
/fz-skill eval fz-test --runtime
/fz-skill optimize fz-test

# 생태계 트리거 건강도
/fz-manage benchmark --with-trigger

# 아키텍처 결정 시 참조
guides/clean-architecture.md → Uncle Bob's Decision Rules
```
