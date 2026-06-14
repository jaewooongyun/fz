# Claude Fable 5 Model Guide

> ⛔ **사용 제한 (2026-06-14)**: Fable 5가 미국 제재로 외국인 사용 금지 → fz는 **Opus 4.8** 운용. effort는 **세션 레벨 max(기본) / ultracode(코딩·병렬 작업 — xhigh + dynamic workflow 오케스트레이션)**, **plain xhigh 미사용**. effort frontmatter 배선(4스킬)·synthesis fable pilot은 **롤백 완료** (§3 표·§5 effort 섹션·§5.8 ①④). 본 가이드 본문은 제재 해제 시 재사용 위해 **보존**.
>
> Claude Fable 5 / Claude Mythos 5의 사양 · API 동작 차이 · Claude Code 통합 · fz 생태계 적용 전략의 단일 참조.
> 모델 무관 프롬프팅 원칙은 `prompt-optimization.md`, 하네스 설계는 `harness-engineering.md` 참조.
>
> **Sources (last audited: 2026-06-12) — Tier 1 only:**
>
> - **Introducing Claude Fable 5 and Claude Mythos 5** (Anthropic, GA 2026-06-09) — platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5
> - **Prompting Claude Fable 5** (Anthropic, live) — platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5
> - **Claude Code: Model configuration** (Anthropic, live) — code.claude.com/docs/en/model-config
> - **Claude Fable 5 & Mythos 5 발표문** (Anthropic, 2026-06-09) — anthropic.com/news/claude-fable-5-mythos-5
> - **claude-api 번들 스킬** (Anthropic 공식, cached 2026-06-04) — 모델 카탈로그 + Fable 5 마이그레이션 가이드
> - **환경 실측** (Claude Code v2.1.170+, 2026-06-12) — Agent tool model enum, /model · /effort 동작

---

## 1. 모델 사양

| 항목 | 값 |
|------|-----|
| Model ID | `claude-fable-5` (alias 없음, 이 문자열 그대로) |
| 포지션 | "Anthropic's most capable widely released model" — Opus 상위 능력 tier ("sits above Claude Opus in capability" [verified: 환경 실측 2026-06-12 — Claude Code 공식 모델 공지]) |
| GA | 2026-06-09 (Claude API, Claude Platform on AWS, Bedrock, Vertex AI, Foundry) |
| Context window | **1M tokens (기본값이자 최대값)** |
| Max output | 128K tokens/request |
| 가격 | **$10 / $50 per MTok** (Opus 4.8 $5/$25의 정확히 2배) |
| Tokenizer | Opus 4.8과 동일 — Opus 4.7/4.8에서 이전 시 토큰 수 거의 불변 |
| 데이터 보존 | **30-day retention 필수** — ZDR 조직은 모든 요청 400 |
| Claude Mythos 5 | `claude-mythos-5` — 동일 능력/가격, **안전 분류기 없음**, Project Glasswing 한정 |

[verified: platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5]

⛔ **Fable 5는 기본 업그레이드 경로가 아니다**: "Migrate to Claude Fable 5 only when the user explicitly chose it. It is not the default Opus upgrade path" [verified: claude-api 번들 스킬 model-migration]. 일반 작업의 기본은 여전히 Opus 4.8.

## 2. Opus 4.8 대비 API 동작 차이

| 항목 | Fable 5 동작 | 위반 시 |
|------|-------------|--------|
| Thinking | **상시 활성** — `thinking` 파라미터 생략(또는 `{type: "adaptive"}`만 허용) | `disabled`/`budget_tokens` → 400 |
| Raw CoT | **절대 미반환** — `display: "summarized"`(요약) 또는 `"omitted"`(기본, 빈 문자열) | — |
| 깊이 제어 | `output_config.effort`: `low`/`medium`/`high`/`xhigh`/`max` | — |
| 샘플링 | `temperature`/`top_p`/`top_k` 제거 (4.7+ 동일) | 400 |
| Prefill | 마지막 assistant-turn prefill 미지원 | 400 |
| Refusal | 안전 분류기(공격적 사이버보안·생물학·reasoning 추출 대상)가 HTTP 200 + `stop_reason: "refusal"` 반환 가능. 출력 전 거부 = 과금 0 | — |
| Fallback | 서버측 `fallbacks` 파라미터(beta) / SDK 미들웨어 / fallback credit으로 Opus 4.8 재시도 | — |
| Prompt cache | 최소 캐시 prefix **2048 tokens** (Opus 4.8은 4096 — Fable이 더 짧은 프롬프트도 캐시) | — |
| Turn 길이 | 고난도 작업 단일 요청이 수 분(15분도 정상), 자율 런은 수 시간 — 타임아웃·진행 표시 설계 필요 | — |

[verified: platform.claude.com/docs/en/about-claude/models/introducing-claude-fable-5 + claude-api 번들 스킬]

## 3. Claude Code 통합

### 선택과 기본값

- **어떤 계정 유형에서도 default 모델이 아님** — `/model fable`로 명시 선택 (선택 시 user settings에 기본값으로 저장됨). `best` alias = "조직이 Fable 5 접근 가능하면 Fable 5, 아니면 최신 Opus"
- Claude Code **v2.1.170+** 필요. ZDR 환경에서는 피커에서 숨김/비활성
- Fast mode(/fast)는 **Opus 4.8/4.7/4.6 전용** — Fable 미지원 [verified: 환경 실측 2026-06-12]

### Effort

| 레벨 | 용도 (공식) |
|------|------------|
| `high` | **Fable 5 기본값.** 대부분의 작업 — "Use `high` as the default for most tasks" |
| `xhigh` | "the most capability-sensitive workloads" |
| `max` | 가장 깊은 추론, 토큰 무제약 — **세션 한정** (`CLAUDE_CODE_EFFORT_LEVEL` 환경변수 제외), overthinking 경향 주의 |
| `medium`/`low` | 루틴 작업 — "Lower effort settings on Claude Fable 5 still perform well and often exceed `xhigh` performance on prior models" |

[verified: code.claude.com/docs/en/model-config + platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5]

- 설정 경로: `/effort` 슬라이더 · `--effort` 플래그 · `CLAUDE_CODE_EFFORT_LEVEL` · settings `effortLevel` · **스킬/서브에이전트 frontmatter `effort` 필드** (해당 스킬/에이전트 실행 동안만 override)

### 사용 시점 가이드 (fz 운용 — 2026-06-12 배선)

| 레벨 | fz 사용 시점 | 배선 상태 |
|------|------------|----------|
| `high` | 루틴 작업 기본 — 별도 설정 불요 (Fable 기본값) | 기본 (미배선) |
| `xhigh` | capability-sensitive: 아키텍처 결정·복잡 디버깅·심층 plan/review/search | **frontmatter 배선 철회 (2026-06-14)** — 4스킬 `effort: xhigh` 제거. 사용자 운용 = 세션 max/ultracode, plain xhigh 미사용 (§5.8 ① 철회) |
| `max` | 단발 최고난도 — 세션 한정(`/effort`), overthinking 경향 주의. frontmatter 값 허용 여부 [미검증] → 배선 금지 | 미배선 (세션 레벨만) |
| `ultracode` | dynamic workflow 오케스트레이션이 필요한 substantive 작업 세션 — `/effort` 메뉴에서 활성 (frontmatter/settings 불가, 세션 한정) | 배선 불가 (사용 가이드만) |
| `medium`/`low` | 루틴·경량 작업 — fz-commit·fz-pr 등 경량 스킬 후보이나 **측정 전 선제 강등 금지** (31차) | deferred 큐 |
- `ultracode`: effort 레벨이 아닌 Claude Code 설정 — xhigh + substantive task마다 dynamic workflow 오케스트레이션 (세션 한정)
- `ultrathink` 키워드: 해당 turn만 심층 추론 (effort 설정 불변). "think hard" 류는 더 이상 키워드 아님
- Thinking은 Fable 5에서 **끌 수 없음** — Option+T 토글, `alwaysThinkingEnabled`, `MAX_THINKING_TOKENS=0` 모두 무효
- ℹ️ `/model` 피커의 "max effort 저장" 메시지와 공식 docs의 "max는 세션 한정" 문구가 표면 상충 [미검증: 다음 세션에서 effort 지속 여부 실측 필요]

### 안전 분류기 자동 폴백 (Claude Code 고유)

- 분류기가 요청을 flag하면 → **해당 요청을 default Opus(4.8)로 자동 재실행** + transcript에 notice → 세션이 Opus로 계속됨. 복귀는 `/model fable` 재실행
- **첫 요청부터 발생 가능**: 워크스페이스 컨텍스트(CLAUDE.md, git status)만으로 트리거될 수 있음 → 진단: `claude --safe-mode`
- `/config`에서 "switch models when a message is flagged" 끄면 → flag 시마다 전환/프롬프트 수정 선택지 표시
- 공격적 보안·생물학 워크로드는 거의 모든 요청이 재라우팅됨 (계정 플래그 아닌 정상 라우팅)

[verified: code.claude.com/docs/en/model-config]

### 서브에이전트 · 워크플로

- Agent tool `model` 파라미터 enum: `sonnet` / `opus` / `haiku` / **`fable`** [verified: 환경 실측 2026-06-12 — Claude Code v2.1.170+ Agent tool 스키마]
- Workflow `agent()` `opts.model`: 생략 시 **메인 루프 모델 상속** — 세션이 Fable이면 model 미지정 워크플로 에이전트도 Fable로 실행됨 (비용 2배 주의)
- `CLAUDE_CODE_SUBAGENT_MODEL`: 모든 서브에이전트/에이전트 팀 모델을 일괄 override (per-invocation `model` 파라미터·frontmatter보다 우선)
- `ANTHROPIC_DEFAULT_FABLE_MODEL`: `fable` alias 해석 대상 지정 (서드파티 프로바이더 폴백 식별에도 사용)
- `DISABLE_PROMPT_CACHING_FABLE=1`: Fable 모델만 프롬프트 캐싱 비활성

## 4. 최고 효율 사용 원칙 (공식 권고 요약)

> 원문: Prompting Claude Fable 5 (platform.claude.com) + Claude Code Model configuration "Work with Fable 5" 섹션. 아래는 요지 + 핵심 인용.

### 무엇을 맡길까

1. **난이도 최상단부터**: "The teams seeing the best outcomes apply Claude Fable 5 to their hardest unsolved problems" — 단순 워크로드만 시키면 능력 범위를 과소평가하게 됨
2. **모호한 문제**: root-cause 조사, 장애 디버깅, 아키텍처 결정 — 추가 조사·검증이 값어치를 하는 곳
3. **단일 세션보다 큰 작업**: "give it work you would normally break into pieces. It holds long sessions without losing the thread"
4. **결과를 기술하고 경로는 위임**: "Describe the outcome, not the steps"
5. ⛔ **공격적 사이버보안·생물학은 비대상 도메인** — "Claude Fable 5 is not intended for offensive cybersecurity or biology and life sciences work" — refusal/폴백 대상

### 프롬프트 패턴 (공식 스니펫 7종)

| 패턴 | 트리거 상황 | 핵심 문구 (요지) |
|------|-----------|----------------|
| Anti-overplanning | 모호한 작업에서 과잉 계획 | "When you have enough information to act, act." |
| No-tidying | 높은 effort에서 무요청 리팩토링 | "Don't add features, refactor, or introduce abstractions beyond what the task requires." |
| Grounded progress | 장기 자율 런의 상태 보고 | "Before reporting progress, audit each claim against a tool result from this session." (조작된 상태 보고 거의 제거 — Anthropic 실측) |
| Boundaries | 무요청 인접 행동 | "When the user is describing a problem... the deliverable is your assessment. Report your findings and stop." |
| Async subagents | 병렬 위임 | "Delegate independent subtasks to subagents and keep working while they run." |
| Memory | 세션 간 학습 | "Store one lesson per file with a one-line summary at the top." |
| Readability | 장기 에이전틱 세션의 최종 요약 | "drop the working shorthand. Write complete sentences... If you have to choose between short and clear, choose clear." |

### Scaffolding 변경 권고 (이전 모델 대비)

- **De-prescribe**: "Skills developed for prior models are often too prescriptive for Claude Fable 5 and can degrade output quality. Review and consider removing older instructions if default performance is better."
- **검증 리마인더 축소**: "it verifies its own work with less prompting, so reminders to test or check are usually unnecessary" [verified: code.claude.com/docs/en/model-config]
- **자기검증은 fresh-context 검증자로**: "Separate, fresh-context verifier subagents tend to outperform self-critique"
- ⛔ **reasoning 재현 지시 금지**: 내부 추론을 응답 텍스트로 echo/transcribe하라는 지시는 `reasoning_extraction` refusal 트리거 → Opus 폴백 증가. 기존 스킬의 "사고 과정을 보여라" 류 지시 감사 필요
- **send_to_user 도구**: 장기 비동기 에이전트가 turn 종료 없이 verbatim 메시지 전달 (도구 정의만으로 부족 — 시스템 프롬프트에 호출 지시 필요)

## 5. fz 생태계 적용 전략

> ⛔ 이 섹션은 **권고**다. model-strategy frontmatter · workflows/*.js 모델 변경 등 동작 변경은 비용 영향(2배)이 있으므로 별도 합의 후 적용한다.

### 모델 전략 옵션 (4-axes)

| 옵션 | 품질 | 비용 | 변경 범위 | 판정 |
|------|------|------|----------|------|
| A. 현행 유지 (Lead=세션 모델, Primary=opus, rest=sonnet) | 기준 | 기준 | 0 | Fable 미사용 시 |
| **B. Lead만 Fable** (사용자가 `/model fable` — 설정 변경 불요) | Lead 추론·오케스트레이션 ↑ | Lead 토큰만 2배 | 0 (이미 가능) | **현재 권장 기본** |
| C. Primary 선택 승격 (capability-sensitive 단일 호출만 `model: 'fable'`) | 병목 단계 ↑ | 해당 호출만 2배 | 워크플로/스킬 일부 | 측정 후 선별 도입 |
| D. 전면 Fable | 최대 | 전체 2배+ | 전체 | ⛔ 비권장 — "not the default upgrade path" |

- **B가 공식 포지셔닝과 정합**: Fable의 강점(long-horizon 자율성, 모호성 처리, 위임 관리)은 Lead 역할 그 자체. Supporting 에이전트의 좁은 lens 작업은 sonnet으로 충분
- **C 후보** (도입 시 우선순위): ① 워크플로 merge/synthesis 단계 (예: plan-collaborative의 통합 단계) ② fz-review Primary (Fable의 "Bug-finding recall noticeably higher" 공식 진술) ③ fz-discover landscape 합성. 도입 방법: Workflow `agent()` `opts.model: 'fable'` 또는 Agent tool `model: "fable"` [verified: 환경 실측]
- ⛔ **동시 실행 상한**: fable 에이전트는 **동시 1개** (Lead 세션 제외) — "동시 opus 최대 2개" 거버넌스의 비용 등가(fable 1 ≈ opus 2, $10/$50 vs $5/$25). pilot 측정(§5.8 ④) 누적 후 재조정
- ⚠️ **Workflow model 생략 함정**: `opts.model` 생략 시 메인 루프 모델 상속 — Fable 세션에서는 모든 미지정 에이전트가 Fable로 실행됨. fz workflows는 현재 전 호출에 opus/sonnet 명시되어 있어 안전 (2026-06-12 실측: workflows/*.js 5파일 전수 명시)

### effort frontmatter 배선 — **2026-06-14 철회 (세션 운용 전환)** · 잔여 후보 기록

스킬/서브에이전트 frontmatter `effort` 필드로 실행 중 override 가능 [verified: code.claude.com/docs/en/model-config]:
- ~~적용: fz-plan·fz-review·fz-discover·fz-search `effort: xhigh` (4스킬)~~ → **철회 (2026-06-14)**: frontmatter 4건 제거. 사용자 effort 운용 = 세션 max(기본)/ultracode 확정 → frontmatter 배선 불요 (§5.8 ① 철회, §3 표 참조)
- 잔여 후보: fz-commit·fz-pr 등 경량 스킬 `effort: medium` — 공식 기본값(high)이 대부분 작업에 적정이므로 **측정 없이 선제 강등 금지** (31차 Plan-before-Probe / 35차 Calibrate-from-Real)

### De-prescription 긴장 — fz Gate 체계와의 관계

공식 권고("too prescriptive → degrade output quality")와 fz의 **트리밍 비저하 원칙**(Gate 체크리스트·Few-shot·절차적 Step 삭제 금지)은 표면 충돌하나:

1. `skill-authoring.md`의 **DELETE/MERGE-default 규칙이 이미 같은 방향** — 추가 충동마다 "무엇을 지울 수 있나" 선검토
2. Gate 체크리스트는 *행동 가드레일*(사고 방지)이고, 공식 권고의 대상은 *절차 밀도*(step-by-step 지시) — 재평가 대상은 후자
3. 적용 절차: 개별 스킬에서 절차 지시 제거 A/B → 품질 비저하 확인 후 반영 (Phase 5 실험 프레임 `experiment-log.md` 활용). **일괄 트리밍 금지**

### Fable 프롬프팅 스니펫 채택 현황 (2026-06-12 실측 선별)

> ⛔ 7종 일괄 주입 금지 (DELETE/MERGE-default) — 기존 규약 중복을 실측한 후 빈 곳만 채택. 비채택 근거를 남겨 재논의 시 추적 가능하게.

| 공식 스니펫 | 판정 | 근거 |
|------------|------|------|
| Grounded progress | **채택** | 기존 진행 보고 grounding 0건 [verified: rg 무매치 2026-06-12] → fz SKILL VD Brief 4번 + team-core 트리거 주입 + workflows 5파일 OVERRIDE 배선. 16/18차(태그≠검증)·Workflow [verified] 오측의 직접 방어 |
| Anti-overplanning | **보강** | lead-action-default 33차 row가 동등 기능 기존재 — Fable 공식 출처 1구만 추가 |
| Boundaries | 비채택 | lead-action-default 40차 row + MAST FM-2.2(AskUserQuestion 의무) 기존재 |
| No-tidying | 비채택 | fz-code "관찰 보고 의무"(범위 외 발견 → 기록만, 실행 금지) + Scope Minimality 기존재 |
| Memory | 비채택 | memory-curator + L1 topic file 체계 기존재 |
| Readability | 비채택 | Claude Code 하네스 시스템 프롬프트 내장 영역 — 플러그인 중복 주입 회피 |
| Async subagents | 비채택(이관) | 구조 트랙(오케스트레이션 레이어 background 위임) — 별도 사이클 |

### 점검 항목 (후속 작업 후보)

- [x] fz 스킬/모듈 중 "사고 과정·추론을 출력하라" 류 지시 전수 grep → `reasoning_extraction` refusal 위험 평가 — **실측 0건** (2026-06-12, skills/·modules/·agents/·workflows/ 전수. `reasoning`/`사고` 매치는 전부 추론 품질·모듈명 등 정상 용법)
- [ ] Fable 세션에서 fz-review self-review 품질 재측정 → Codex cross-model 의존도 재조정 (단, 이종 blind-spot 안전망 자체는 유지 — 15차/23차)
- [ ] `/model` max effort 세션 지속성 실측 (위 [미검증] 해소)
- [ ] TEAM(SendMessage) 패턴에 Fable의 "async subagent communication" 권고 반영 검토

## 설계 원칙

- Progressive Disclosure: 이 가이드는 Fable 관련 결정 시에만 로드
- 500줄 이하 유지 · Tier 1 인용 원칙 (`prompt-optimization.md` 출처 표기 규약 준수)
