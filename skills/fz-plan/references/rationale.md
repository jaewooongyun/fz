# fz-plan 근거 · 이력

> SKILL.md 에서 옮긴 근거 · 이력 · 사례 문단이다(B1 · 2026-11-01). 실행 규칙은 SKILL.md 에 남아 있다 — 이 파일은 왜 그 규칙인지를 설명한다.

## 루프 프리미티브 표지

> 루프 프리미티브: Plan-Execute + Evaluator-Optimizer (H6, Inside the Scaffold)

## TEAM → Workflow 전환(Wave 2)

> TEAM(TeamCreate+SendMessage) 모드를 네이티브 Workflow 결정적 스크립트로 대체한 Wave 2 전환.
> Collaborative Design 패턴의 평탄화 구현은 `workflows/plan-collaborative.js` 로 남아 있다 — **롤백 경로**다(아래 ⛔ 배선 전환). 기본 실행은 아래 스크립트다.

## 배선 전환 근거(2026-09-12)

>
> ⛔ **2026-09-12 배선 전환 (6단계 9콜 → 2단계 4콜)** — wall · 노이즈 바닥 · 채택 판정은 `experiment-log.md` §5.9 가 정본이다. ⛔ 근거는 전부 **N=1** 이고 run-to-run 분산이 구조 간 차이보다 컸다 — 실사용 3회 관찰 후 재평가한다.
> · **롤백**: 아래 절차 2.5·3 의 스크립트명을 `plan-collaborative.js` 로 되돌리면 끝이다 — 파일은 그대로 남겨 둔다.

## 사전 복사 실측(2026-09-11)

   실측(2026-09-11, 3건 전부): 플러그인 루트 경로로 첫 호출이 거부되고 WORK_DIR 복사본으로 재호출해 성공했다 — 거부 1회가 매번 낭비된다(텔레메트리 `n_workflow=2` 의 정체).

## directionEscalation 이 필드인 이유

     ⛔ **필드다, 반환 모드가 아니다** — 현행 배선(`plan-lean2.js`)은 방향 판정을 full 콜 안에서 하므로 정상 경로와 반환 형태를 가르지 않는다.

## 차별화된 렌즈

**6개 차별화된 렌즈** (같은 질문 금지 — ICLR 2025 근거. Workflow stage에 동일 적용):

| 렌즈 | 스크립트 위치 | 핵심 질문 |
|------|--------------|----------|
| plan-structure (설계+분해) | Stage 1 전체 플랜 (Stage 2 병합은 도구 없는 plan-merge) | "어떻게 나누고 만들 것인가?" · 방향 판정도 이 콜이 함께 낸다 |
| plan-edge-case (경계) | Stage 1 적대 렌즈 | "어디서 깨지는가?" — ⭐ 측정상 고유 기여가 가장 큰 렌즈 |
| plan-impact (영향+아키) | Stage 1 통합 렌즈 | "어디까지 퍼지는가 · 기존 패턴과 맞는가?" — `secondaryHosts`·`existingTestSuites` 를 schema 로 명시 요구 |
| GPT verify (독립 검증) | Workflow 외부 — Lead가 /fz-gpt verify (Phase 2) | "이 계획에 빠진 것은?" |

## 통신 기록 · TEAM 일몰


> 통신 기록: plan-team.md 미생성 — Workflow transcript(runId)가 대체. TEAM 일몰 상태는 `modules/promotion-ledger.md` § 결정 완료 — TEAM 메커니즘 일몰이 정본이다(⛔ 여기서 재서술하지 않는다).

## Gate 1 을 SKILL 에 남기는 이유

> 각 절차 상세는 `modules/plan-deep-planning.md` 참조. 트리밍 비저하 원칙(single source: `guides/prompt-optimization.md` §1 보충 3a)으로 Gate 1 + Why(H1)는 본 SKILL에 보존.

## verify 내부 동작

검증이 수행하는 작업:
- 계획 전송 (cross-model 검증)
- 응답 파싱
- Issue Tracker에 이슈 자동 기록
- 이슈 요약 반환

## plan-final 하나만 남기는 이유

     이유: `/fz-code` Phase 0.4 는 `plan-final.md` **하나만** 복원하고 RTM 도 그 문서 안에서 갱신된다(`modules/rtm.md`). 이전 본문과 수정 delta 를 나란히 남기면 폐기된 Step·verify 가 함께 복원돼 구현이 무엇을 따라야 할지 갈린다.

## 요약만 저장하면 안 되는 이유

     (요약만 저장하면 `/fz-code` Phase 0.4의 구조 검사가 판정 불가)
