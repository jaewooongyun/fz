# fz 근거 · 이력

> SKILL.md 에서 옮긴 근거 · 이력 · 사례 문단이다(B1 · 2026-11-01). 실행 규칙은 SKILL.md 에 남아 있다 — 이 파일은 왜 그 규칙인지를 설명한다.

## 출처 · 감사 기록

> **Sources (last audited: 2026-09-21 — **인용 정합 축**(arxiv ID 형식 56종 이상 0 · 교차 파일 주장 일치 · 레지스트리 등재)):** `platform.claude.com` prompting-claude-fable-5-1 · arxiv 2606.08878 — 본문에 `[verified: …]` 인라인 표기 승계. ⛔ **원문 재조회는 포함하지 않았다** — 외부 페이지가 바뀌었는지는 이 감사의 범위 밖이다.

## effort 이력과 공식 출발점

  > ℹ️ **effort (2026-07-25, Opus 5 / 2026-09-06 Fable 5.1 갱신)**: 현행 배선은 전 호출 `effort: EFFORT` — Lead 세션 effort 를 args 로 전달(미지정 `xhigh` · 2026-10-19 · `modules/mode-gate.md` § effort). 공식 출발점: **Fable 5.1 `high` · Opus 5.5 `medium`(Opus 5 는 `high`)** 이고 `low`/`medium`이 비용·지연의 1차 레버 — `xhigh`는 여전히 유효 범위지만 **더 이상 문서상 출발점이 아니다**. Fable 5.1은 세대가 바뀌어도 sweep을 이월하지 말라고 명시한다 — "Re-run the sweep even if you already ran one on Claude Fable 5" [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1]. ⛔ 상수 일괄 교체 금지, **fresh sweep 후** 스테이지별 차등 배정 (`guides/skill-authoring.md` § 배치·호출 규약).

## 트리거 소스

> ⛔ **Phase 1 이 읽는 트리거 소스는 `modules/intent-registry.md` 다.** 스킬 YAML 의
> `intent-triggers` 는 스킬 자체 문서이며 `fz-skill` eval 이 소비한다 — 두 곳이 어긋나면
> `/fz` 는 registry 만 보므로, **스킬을 추가·수정할 때 registry 도 함께 고쳐야 한다**.
> 담긴 것: 스킬 트리거 · 파이프라인 전용 트리거 · 구어체 보강 · Confidence 판정.
> ⛔ 현재 이 동기화를 강제하는 기계 검사는 없다 (2026-08-25 시도했으나 오라클이 부정확해 철회).

## total-miss 에서 3.2 로 내려가지 않는 이유

⛔ **total-miss 에서 3.2 로 내려가지 않는다.** 목표 스킬 없이 `provides`/`needs` 역추적을
시작하면 임의 파이프라인이 구성된다 — `references/test-spec.md` 가 그것을 0건으로 못 박는다.

## 오케스트레이션 프롬프팅 취약성

> 워커 컨텍스트 전달 명세(무엇을 워커에 알릴지)를 팀 확정 시 재검토 — 오케스트레이션 프롬프팅은 코딩과 별개의 취약 능력 [외부: harness-paper §4-F, PerspectiveGap 2606.08878 — 평균 pass 14.9%, 원 논문 미대조]. ⚠️ 2026-11-01 정정(M7): 14.9% 는 v1 abstract 수치다(이력) [arxiv preprint, 2026-06, v1]. 현행 v2 abstract 는 *"average combined pass rate of only 17.2%"* 다 [arxiv preprint, 2026-06, v2].

## 검증 게이트 용어

> **direction-challenge**: review-direction 에이전트가 접근 방향 자체를 도전 (PROCEED/RECONSIDER/REDIRECT 판정). fz-plan TEAM Phase 0.5.
> **stress-test**: fz-plan의 설계 스트레스 테스트(다중성/소비자/복잡도이동/경계/접근경계).
> **friction-detect**: fz-code의 구현 마찰 감지(분기폭증/코드반복/소비자판별/workaround/잔존패턴).
> **enforcement**: Plan의 Anti-Pattern Constraints 기반 금지 패턴 Grep + Module Boundary 검증. 리팩토링 파이프라인에서만 삽입.

## TEAM 일몰 뒤 실행 주체

> 멀티에이전트 실행은 네이티브 Workflow 결정적 스크립트가 소유한다 (TEAM 일몰, Wave 4). 스크립트가 fan-out/수렴/라운드를 구현 — P2P SendMessage 없음.

## 스킬별 통신 패턴

| 스킬 | 통신 패턴 | 핵심: 에이전트 간 직접 대화 |
|------|----------|--------------------------|
| fz-discover | Adversarial Constraint Discovery — (pilot: `workflows/discover-adversarial.js` Workflow 대체, P2P 아님) | plan-structure ↔ review-arch 만들고 부수며 제약 발견 |
| fz-plan | Collaborative Design — (기본 `workflows/plan-lean2.js` · 롤백 `workflows/plan-collaborative.js` Workflow 대체, P2P 아님) | review-direction → plan-structure 방향 도전 (Phase 0.5) + plan-structure ↔ peers 만들면서 토론 |
| fz-code | Pair Programming — (Wave 3: `workflows/code-pair.js` Workflow 대체, P2P 아님) | impl-correctness ↔ review-arch 구현 중 실시간 질문/검토 |
| fz-review | Live Review — (Wave 1: `workflows/review-live.js` Workflow 대체, P2P 아님) | review-arch ↔ review-quality 분석하면서 발견 공유 |
| fz-search --deep | Cross-Verify — (Wave 1: `workflows/search-cross-verify.js` Workflow 대체, P2P 아님) | search-symbolic ↔ search-pattern 발견 즉시 교차 확인 |
| fz-fix (복잡) | Pair Programming (경량) — (`workflows/code-pair.js` mode=light) | impl-correctness ↔ Lead 수정/검증 |

## 실사용 관찰 — 개별 스킬 반복

실사용에서는 풀 사이클보다 **개별 스킬을 반복 실행**하는 것이 일반적입니다.
