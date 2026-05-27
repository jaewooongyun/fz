# Lead Action Default Principle (31/32/33 통합)

> **Principle**: Lead default = action with proportional verification. Verification escalation은 명시적 risk signal에서만.
>
> 학술 근거 + 사례 history는 `guides/harness-engineering.md` 참조 (hot path가 아님).

## Trigger Matrix

| Manifestation | Trigger Signal | Lead Action |
|---------------|----------------|-------------|
| 31차 (Plan-before-Probe) | Plan 차원이 primitive/CLI flag/config key/value enum/env precondition에 의존 | constraint probe 선행 (`/fz-discover` Phase 1.5 또는 `fz-plan` Phase 0c) |
| 32차 (Probe Coverage) | probe 대상 enumeration 중 (a) 존재 (b) 권한·경계 (c) 결과 contract 3축 중 누락 | 3-axes sub-checklist 적용 |
| 33차 (Recommendation Default) | implementation-ready 시점 / verify approved or conditional-minor | **권고 default = implementation** (참조: `modules/fz-pipeline-proposal.md`) |
| 40차 (Simplified Request) | 사용자 신호 "그냥/가볍게/단순/빠르게/확인해줘/해도 돼?/맞아?/한 번 봐줘" 키워드 + 검토 산출물 존재 + **no `--deep`/`--team`** override | full 파이프라인 차단, simplified mode 적용 (예: `/fz-modernize light`) |
| 40차-MUST3 (Codex precedence) | `--seq` 단독은 sequential thinking 모드이지 simplified trigger 아님. `--deep --seq` 또는 `--team --seq` 조합 시 elaborate 유지 | `--seq` 단독 keyword 매칭 금지 — 컨텍스트 조건 필수 (Codex 검증 §5 MUST 3) |
| MAST FM-2.2 (Fail to ask for clarification) | 요청 모호 / 동사 없음 / 명사+키워드만 / 범위 불명확 | AskUserQuestion 발동 의무 |

> 출처: MAST (NeurIPS 2025, arXiv 2503.13657) — FM-2.2 "Fail to ask for clarification" = **6.8% 오류율** [verified: L4]. 모호한 요청을 그대로 진행하면 28개 시스템 평균 6.8%의 실패 모드 trigger.

## 3 Examples (inline)

- **31차**: 사용자 "v3 작성하지 말고 implementation 진입" → constraint probe 안 했으면 probe 선행, 했으면 implementation
- **32차**: T1-D2 ISSUE-001 (allowed-tools) — Codex 단독 발견. 3축 중 "권한·경계" 축 누락이 원인
- **33차**: round 4 (review→plan→review→...) 누적 시 default = stop & implement (사용자 명시 risk signal 없을 시)

## Lesson Intake (이 원칙에 새 manifestation 추가 시)

> 참조: `modules/memory-guide.md` § Lesson Intake Decision Tree. 동일 failure mode만 manifestation 추가. 다른 mode는 별도 principle 후보.
