# 아키텍처

디렉토리 구조와 오케스트레이션 흐름, 멀티에이전트 실행 방식.

```
fz-plugin/
├── .claude-plugin/  plugin.json + marketplace.json
├── skills/          21개 — /fz, /fz-plan, /fz-code, /fz-review, /fz-fix, /fz-modernize ...
├── agents/          13개 — plan-structure, impl-correctness, review-arch ...
├── workflows/       6개 — 네이티브 Workflow 결정적 스크립트 (discover-adversarial, plan-collaborative, code-pair ...)
├── modules/         42개 — gates(완료 게이트 SSOT), team-core, pipelines, cross-validation, lead-action-default, codex-strategy, memory-guide, fz-codex-bash-hygiene, fz-codex-subcommands-core/aux ...
│   └── patterns/    5개 — adversarial, collaborative, pair-programming ...
├── guides/          9개 — prompt-optimization, skill-authoring, harness-engineering, agent-team-guide, skill-testing, fable-model-guide, llm-references ...
├── codex-skills/    8개 — Codex 네이티브 스킬 + Authority 인용 + Memory Lesson inline (fz-reviewer, fz-architect ...)
├── schemas/         6개 — Codex JSON 응답 스키마 (review, verification, gate_verdict, peer_review ...)
├── scripts/         13개 — gate_check(완료 판정기) · gate_stop_hook(종료 차단) · lint 3 · codex-exec · health-check ...
├── tests/           fixtures/gates/ — 판정기 회귀 66케이스 (16범주, 기대 exit·산출물·시간·stdout·stderr)
└── templates/       스킬/에이전트/CLAUDE.md 생성 템플릿
```

## 오케스트레이션 플로우

```
자연어 요청
    ↓
Phase 0  Session Bootstrap ─── sc:load, 인덱스, ASD 폴더
Phase 1  Intent Analysis ───── 키워드 → intent-triggers 매칭
Phase 2  Complexity ─────────── 5차원 평가 → SOLO(0-3) / TEAM(4+)
Phase 3  Pipeline + Team ────── 19개 파이프라인 매칭 + 에이전트 배정
Phase 4  User Confirmation ─── 시각화 → 승인
Phase 5  Execute ────────────── 스킬 체인 실행 + Gate 검증
    ↓
완료: GC → sc:save → 다음 행동 안내
```

## 멀티에이전트 실행 — 네이티브 Workflow

```
Lead (Fable 5) ─── Workflow({scriptPath}) 호출 + changeset 적용 + 빌드/Gate 실행
    │
    └── workflows/*.js ─── 결정적 스크립트가 stage 오케스트레이션
        agent(agentType: 'fz:plan-structure', schema) → 스키마 강제 JSON 반환
        데이터는 스크립트 경유 (P2P 통신 유실·팀 정리 실패가 구조적으로 불가능)
```

| 스킬 | 스크립트 | 구조 |
|------|---------|------|
| /fz-discover | discover-adversarial.js | lean 5-call / --deep 렌즈 3 fan-out |
| /fz-search --deep | search-cross-verify.js | 심볼/패턴 독립 병렬 → 교차 FP 제거 → 병합 (5-call) |
| /fz-review | review-live.js | arch/quality 병렬 → id-기반 교차 → counter DA (5-call) |
| /fz-plan | plan-collaborative.js | direction 도전 → 초안 → 3렌즈+CC 교차 → 통합 (9-11 call) |
| /fz-code, /fz-fix | code-pair.js | impl changeset(디스크 미수정) → 조건부 검토 → Lead 적용 (1-3 call) |
| /fz-peer-review | peer-review.js | arch/quality/correctness 3-병렬 → (deep) 교차 + counter DA (3 or 6-call) |

> TEAM(TeamCreate+SendMessage P2P) 모드는 v4.22.0에서 **일몰 완료** — 실제 TeamCreate 호출부 0건. `patterns/*.md`는 canonical 라운드 의미론으로 보존. 규약: `guides/skill-authoring.md` §12.
