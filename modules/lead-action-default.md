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

## 3 Examples (inline)

- **31차**: 사용자 "v3 작성하지 말고 implementation 진입" → constraint probe 안 했으면 probe 선행, 했으면 implementation
- **32차**: T1-D2 ISSUE-001 (allowed-tools) — Codex 단독 발견. 3축 중 "권한·경계" 축 누락이 원인
- **33차**: round 4 (review→plan→review→...) 누적 시 default = stop & implement (사용자 명시 risk signal 없을 시)

## Lesson Intake (이 원칙에 새 manifestation 추가 시)

> 참조: `modules/lesson-intake.md`. 동일 failure mode만 manifestation 추가. 다른 mode는 별도 principle 후보.
