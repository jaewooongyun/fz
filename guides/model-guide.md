# Model Guide — Fable 5.1 (Lead) · Opus 5.5 (worker)

> ✅ **운용 상태 (2026-09-06 · 워커 모델 2026-09-25 갱신)**: Lead = **Fable 5.1**(2026-09 출시, 사용자 `/model fable` 세션 · effort **xhigh**), 실질 생산 워커 = **Opus 5.5**(`opus` alias — Claude Code 2.1.280+ 가 Opus 5.5 로 해석), 단순(retrieval·breadth) 워커 = **Sonnet 5**. 판단 지점 3곳 explicit `'fable'` 배선 유지 — `search-cross-verify.js:166` merge + `plan-collaborative.js:220`/`:167` direction (§재배선 확정 배선), `scripts/lint-model-explicit.sh` 기계 감시. ⚠️ 2026-09-06 정정 — 이전 판의 "세션 레벨 max(기본)/ultracode 운용"은 현행이 아니다(세션 = xhigh, `ultracode`는 effort arm으로 무효).
>
> Claude Fable 5.1 / Claude Mythos 5.1의 사양 · API 동작 차이 · Claude Code 통합 · fz 생태계 적용 전략의 단일 참조.
> 모델 무관 프롬프팅 원칙은 `prompt-optimization.md`, 하네스 설계는 `harness-engineering.md` 참조.
>
> **Sources (last audited: 2026-09-25 — 모델 사실 축: Opus 5.5 워커 절·가격표·effort 기본값·advisor 페어링·공식 포지셔닝 인용만 대조. Fable 5.1 절은 2026-09-06 대조 그대로) — Tier 1 only:**
>
> - **What's new in Claude Fable 5.1** (Anthropic, live) — platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1
> - **Prompting Claude Fable 5.1** (Anthropic, live) — platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1
> - **Pricing** (Anthropic, live) — platform.claude.com/docs/en/about-claude/pricing
> - **Prompting Claude Opus 5** (Anthropic, live) — platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
> - **What's new in Claude Opus 5.5** (Anthropic, live) — platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5
> - **Prompting Claude Opus 5.5** (Anthropic, live) — platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5 *(Opus 5 패턴을 상속한다고 명시 — 위 Opus 5 인용의 존치 근거)*
> - **Models overview** (Anthropic, live) — platform.claude.com/docs/en/models/overview
> - **Claude Code: advisor** (Anthropic, live) — code.claude.com/docs/en/advisor
> - **Prompting Claude Fable 5** (Anthropic, live) — platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5 *(5.1이 철회하지 않은 진술의 출처로만 유지)*
> - **Claude Code: Model configuration** (Anthropic, live) — code.claude.com/docs/en/model-config
> - **Claude Code: Best practices** (Anthropic, live) — code.claude.com/docs/en/best-practices
> - **claude.com/blog/claude-model-and-effort-level-in-claude-code** (Anthropic, live)
> - **fz 실측 2026-09-06** — 트랜스크립트 44일·379세션 usage 집계(`scripts/fz_telemetry_report.py --since 2026-07-24 --until 2026-09-06` 로 재현 가능). 원 감사 보고서는 작성자 개인 영역(배포물 아님)
> - **환경 실측** (Claude Code v2.1.170+, 2026-06-12) — Agent tool model enum, /model · /effort 동작

---

## Opus 5.5 운용 (워커 기본 모델, 2026-09-22~)

fz의 실질 생산 워커 모델. 상세 프롬프팅·anti-패턴·deprecated는 `guides/llm-references.md` §1.2·§4·§5 + `prompt-optimization.md` 참조 (중복 회피).

ℹ️ 2026-09-25 — Opus 5.5 행은 whats-new-opus-5-5·prompting-claude-opus-5-5 원문과 대조했다. **"Opus 5 기준"** 라벨이 붙은 행은 이력이며, 5.5 가 상속하므로 존치한다: "Existing Claude Opus 5 prompts should perform well without changes, and the patterns in Prompting Claude Opus 5 remain a reasonable starting point." [verified: prompting-claude-opus-5-5]. `claude-opus-5` 는 **Active**(퇴역 예정일 not sooner than 2027-07-24)이며 현행 워커 자리에서 교체됐을 뿐이다 [verified: models/overview].

| 항목 | 값 |
|------|-----|
| Model ID / Context | `claude-opus-5-5` · 1M tokens (**기본값이자 최대값**) · 128K 출력. 가격 **$4/$20**(Opus 5 는 $5/$25) — "Claude Opus 5.5 costs $4 USD per million input tokens and $20 USD per million output tokens, below Claude Opus 5's $5 and $25" [verified: platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5] |
| Thinking | **상시 ON — 끄기 불가**: "On Claude Opus 5.5, thinking is always on: a request that sets `thinking: {"type": "disabled"}`, or a manual budget with `thinking: {"type": "enabled", "budget_tokens": N}`, returns a 400 `invalid_request_error`." ⚠️ `max_tokens`는 **thinking+응답 합산** 하드캡 — "leave room in `max_tokens` for the thinking" [verified: platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5] |
| effort | **5.5 기본 `medium`** — "A request that omits `effort` runs at `medium`; on Claude Opus 5 it ran at `high`." 같은 effort 에서 사고량 증가 — "At the same effort setting the model tends to think more per turn than Claude Opus 5, most of all at `xhigh` and `max`." [verified: whats-new-opus-5-5]. *Opus 5 기준 (이력):* 출발점 **`high`(기본)**; **`low`/`medium`을 비용·지연의 1차 레버**로; demanding coding/agentic만 `xhigh`; `max`는 무제한 지출 정당화 시. ⛔ **이전 모델 effort 값 재사용 금지 → fresh sweep**: "If you carried effort defaults over from a prior model, re-run an effort sweep on your own evals." [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5] |
| thinking 비활성화 | *Opus 5 기준 (이력 — 5.5 는 불가, 위 Thinking 행):* `{"type":"disabled"}`는 **effort ≤ `high`에서만**. `xhigh`/`max`와 조합 시 **400**(요청 단위 검증) [verified: platform.claude.com/docs/en/release-notes/overview 2026-07-24] |
| 자기검증 | "Claude Opus 5 verifies its own work without being told to. If your prompt contains explicit verification instructions … remove them" + "do not use subagents to verify or double-check your own work" [verified: …/prompting-claude-opus-5]. ⛔ 단, **fresh-context 이종 검증자**는 이 권고의 대상이 아니다 (§5 T2 참조) |
| forced tool use | `tool_choice` `{"type":"any"}`·`{"type":"tool",…}` → **400** — "Claude Opus 5.5 doesn't support forced tool use." 대체는 `auto` + strict tool use 또는 structured outputs [verified: whats-new-opus-5-5] |
| 도구 호출 사이 텍스트 | thinking 블록으로 온다 — "The short notes the model writes between tool calls arrive as progress-update `thinking` blocks rather than `text` blocks, so at the default `display: \"omitted\"` an application that streams them to its users goes quiet between tool calls, with no error." [verified: whats-new-opus-5-5] |
| 5.5 프롬프팅 추가 패턴 | elapsed 시간 신호 — "give the model a time budget: have your harness add a short line at the end of each message … giving the elapsed time" · text-only 턴 종료는 보고로 — "Treat a text-only end of turn as a report rather than as proof the task is done" · continuation 상한 — "stop after two or three automatic continuations on the same task" [verified: prompting-claude-opus-5-5] |
| advisor 페어링 | "The advisor must be at least as capable as the main model." — Opus 5.5·Opus 5 main → Fable 과 Opus 5 이상 허용 / Fable 5.1 main → **Fable 5.1 만**("An Opus or Sonnet advisor is rejected") [verified: code.claude.com/docs/en/advisor, 2026-09-22 판]. 워커는 advisor 를 상속한다(`modules/governance.md` 운용 규칙 5) |
| 구버전 제거 (Fable 5.1·Opus 5.5) | manual `budget_tokens`(400)·prefill(미지원)·sampling 파라미터(400)·`interleaved-thinking-2025-05-14`(ignored) + **[신설] 검증 지시**(over-verification)·**"생각하지 마라" 규칙**(태그 누출 증가)·**carried-over effort**. 상세 `llm-references.md` §5 |

---

# Fable 5.1 상세 (Lead 운용 기준 — 2026-09-06)

> Fable 5.1은 2026-09 출시로 Fable 5를 대체했다. 아래가 현행 운용 기준이며, Fable 5 진술은 5.1이 명시 철회한 것만 교체했다 — "Your existing Claude Fable 5 prompts should perform well on Claude Fable 5.1 without changes, but a handful of behavioral differences are worth knowing about." [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1]

## 1. 모델 사양

| 항목 | 값 |
|------|-----|
| Model ID | `claude-fable-5-1` (alias 없음, 이 문자열 그대로). Claude Code alias는 `fable` — "Uses the latest Fable model for your hardest and longest-running tasks" [verified: code.claude.com/docs/en/model-config] |
| 포지션 | **기본 업그레이드 경로가 아니다.** "If you're unsure which model to use, start with Claude Opus 5.5 for most workloads. Use Claude Fable 5.1 for demanding reasoning and long-horizon agentic work, or when your evals on Claude Opus 5.5 at higher effort still fall short." [verified: platform.claude.com/docs/en/models/overview, 2026-09-25] |
| Context window | **1M tokens** — "a 1M token context window (default and maximum) at standard per-token pricing across the whole window" |
| Max output | **128k max output tokens** |
| Thinking | "adaptive thinking is always on" — 끄기 불가 |
| 가격 (per MTok) | 입력 **$10** · 5m 캐시쓰기 **$12.50** · 1h 캐시쓰기 **$20** · **캐시 읽기 $0.25** · 출력 **$50**. ⚠️ 2026-09-06 정정 — "Opus 5의 정확히 2배"는 **출력·입력·캐시쓰기에만** 참이다. 캐시 읽기는 Opus 5($0.50)의 **절반**: "Cache reads (hits and refreshes) cost 0.025 times the base input price on these models, compared with 0.1 on other Claude models." |
| Tokenizer | "the same as Claude Fable 5 (introduced with Claude Opus 4.7)" — Opus 4.7/4.8/5 ↔ Fable 5/5.1 이전 시 토큰 수 거의 불변 |
| 데이터 보존 | "Claude Fable 5.1 and Claude Mythos 5.1 carry 30-day data retention and aren't available under zero data retention unless expressly authorized by Anthropic." ⚠️ 2026-09-06 정정 — 이전 판의 "ZDR 조직은 모든 요청 400"은 5.1 문서에 없는 진술이라 삭제 |
| Claude Mythos 5.1 | `claude-mythos-5-1` — "Same capabilities as Claude Fable 5.1", Project Glasswing 한정. 안전장치 수준 차이는 5.1 공식 문서가 명시하지 않는다(이전 판 "안전 분류기 없음"은 Fable 5 판 진술이라 삭제) |
| 콘텐츠 출처 표시 | content provenance — 5.1 additive 5종 중 하나 |

[verified: platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1 + platform.claude.com/docs/en/about-claude/pricing]

### 가격 비교 (per MTok, 2026-09-06 · Opus 5.5 행 2026-09-25)

| Model | Base input | 5m cache writes | 1h cache writes | Cache hits and refreshes | Output |
|---|---|---|---|---|---|
| Claude Fable 5.1 | $10 | $12.50 | $20 | **$0.25** | $50 |
| Claude Fable 5 | $10 | $12.50 | $20 | $1 | $50 |
| Claude Opus 5.5 | $4 | $5 | $8 | **$0.20** | $20 |
| Claude Opus 5 | $5 | $6.25 | $10 | $0.50 | $25 |
| Claude Sonnet 5 | $2 | $2.50 | $4 | **$0.20** | $10 |

[verified: platform.claude.com/docs/en/about-claude/pricing] — Sonnet 5의 $2/$10은 도입가가 아니라 **표준가**로 확정됐다: "The $2/$10 per million input/output token pricing for Claude Sonnet 5, announced at launch as introductory pricing through August 31, 2026, is now the standard price."

### tier 격차 — 실측 결과

⚠️ 2026-09-06 정정 — 이전 판의 "tier 격차 재검토 필요" 경고는 실측으로 해소됐다. 같은 opus-5 main 트래픽을 Fable 5.1 단가로 환산하면 **+9%**($17,137 → $18,751 — **Opus 5 단가 기준**. Opus 5.5 단가($4/$20·캐시 읽기 $0.20) 재산정은 미실시 — 선택 과제)이고, 남는 차이는 **호출당 지연 중앙값 +49%**(10.5s → 15.6s)와 **출력·캐시쓰기 단가 2배**다 [fz 실측 2026-09-06].

## 2. Opus 5·Opus 5.5 대비 API 동작 차이 (Fable 5.1 기준)

⚠️ 2026-09-06 정정 — 이 표는 Fable 5 기준 행을 **Fable 5.1 기준으로 교체**한 것이다. 5.1은 Fable 5 대비 **breaking 3 · additive 5**를 가진다: "If you already call Claude Fable 5, three changes are breaking: forced tool use returns an error, earlier models can't read its thinking blocks, and editing earlier turns invalidates thinking blocks. Five are additive: per-message effort (beta), turn-scoped system messages (beta), readable progress updates between tool calls (`display: \"updates\"`, beta), a lower cache read price, and content provenance."

| 항목 | Fable 5.1 동작 | 위반 시 |
|------|---------------|--------|
| **Forced tool use** (breaking) | `tool_choice`의 `{"type":"any"}` / `{"type":"tool","name":"..."}` 미지원 | **400 `invalid_request_error`** |
| **Thinking block 단방향** (breaking) | "Claude Fable 5.1 reads earlier models' thinking blocks, and no earlier model reads Claude Fable 5.1's." — 하위 모델로 전환하면 5.1 thinking block 은 **API 가 제거**해 추론 상태가 보존되지 않는다(요청 실패가 아니다 — 실패는 §earlier-turn 편집 조건). beta 헤더 없으면 제거는 조용히 일어난다 | 블록 드롭 (`input_transformations` 로 보고, beta) |
| **earlier-turn 편집 무효화** (breaking) | "Modifying anything before a Claude Fable 5.1 thinking block (the `system` prompt, the `tools`, or an earlier message) results in an error on the next request, or in the block being dropped if you opt into that." 강제 대상 = "new accounts created on or after August 31, 2026". ✅ "Claude Code, claude.ai, Claude Managed Agents, and the Claude Agent SDK keep that prefix intact for you." | 다음 요청 에러 또는 블록 드롭 |
| Thinking | adaptive **상시 활성 — 끄기 불가**. *Opus 5는 기본 ON이되 effort ≤ `high`에서 `disabled` 허용* — 여기서 갈린다. **Opus 5.5 도 끄기 불가**(400, §Opus 5.5 운용) | — |
| **per-message effort** (additive, beta) | "On Claude Fable 5.1 you can change the effort level mid-conversation without invalidating the prompt cache. Raise it for a hard step and lower it for routine ones." 헤더 `mid-conversation-output-config-2026-07-01`. 지원 = Fable 5.1 · Mythos 5.1 · Opus 5 · **Opus 5.5** (Claude API) — "Claude Opus 5.5 also supports changing effort mid-conversation with a per-message `output_config`, which preserves the prompt cache." [verified: platform.claude.com/docs/en/build-with-claude/effort] | — |
| **turn-scoped system messages** (additive, beta) | 헤더 `mid-conversation-system-clear-at-2026-08-21`, `clear_at: "next_user_message"` | — |
| **progress updates** (additive, beta) | 도구 호출 사이 읽을 수 있는 진행 표시 — `display: "updates"` | — |
| Refusal | 안전 분류기가 HTTP 200 + `stop_reason: "refusal"` 반환 가능. 5.1은 오탐이 줄었다 — "Claude Fable 5.1's safety classifiers produce fewer false positives than Claude Fable 5's did at launch, and finding vulnerabilities in source code is permitted." | — |
| **Fallback** | ⚠️ 2026-09-06 정정 — 허용 폴백 대상이 **Opus 4.8 · Opus 5 둘 다**로 넓어졌다: "The permitted fallback targets for Claude Fable 5.1 are Claude Opus 4.8 and Claude Opus 5." + "for Claude Fable 5.1, fallback credit refunds the prompt-cache cost of switching models." | — |
| Turn 길이 | "Individual requests on hard tasks can run for many minutes at higher effort settings … and autonomous runs can extend for hours." — 타임아웃·진행 표시 설계 필요 [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5 "Longer turns by default" — 5.1이 철회하지 않은 진술] | — |

[verified: platform.claude.com/docs/en/models/fable-5-1/whats-new-fable-5-1]

> ⛔ 이전 판의 Fable 5 한정 행(Raw CoT `display` 값 · 샘플링 400 · Prefill 400 · `fallbacks:"default"` + `server-side-fallback-2026-07-01` · 캐시 최소 prefix 512 tokens)은 **삭제**했다 — 5.1 breaking 3과 중복·상충하고, 5.1 문서에서 재확인되지 않는다. 필요 시 `llm-references.md` §5의 모델 무관 deprecated 목록을 본다.

## 3. Claude Code 통합

### 선택과 기본값

- **어떤 계정 유형에서도 default 모델이 아님** — `/model fable`로 명시 선택 (선택 시 user settings에 기본값으로 저장됨). `best` alias = "조직이 Fable 접근 가능하면 Fable, 아니면 최신 Opus"
- Claude Code **v2.1.170+** 필요. ZDR 환경에서는 피커에서 숨김/비활성 [verified: 환경 실측 2026-06-12]
- alias 3종: "`fable`: Uses the latest Fable model for your hardest and longest-running tasks" / "`opus`: … complex reasoning tasks" / "`sonnet`: … daily coding tasks" [verified: code.claude.com/docs/en/model-config]
- ⚠️ 2026-09-06 정정 — Fast mode(`/fast`) 대상: 공식 가격표에 등재된 것은 **Opus 5 / Opus 4.8** 뿐이고, "Fast mode is not available on Claude Opus 4.7 (requests with `speed: \"fast\"` return an error)" [verified: platform.claude.com/docs/en/about-claude/pricing]. 이전 판의 "Opus 4.8/4.7/4.6 전용"은 **4.7 포함이 틀렸다**. Fable은 fast mode 대상이 아니다 — 공식: "Fast mode, in research preview, provides significantly faster output for Claude Opus 5 and Claude Opus 4.8 at premium pricing." + 환경 실측 2026-06-12 미지원. **Opus 5.5 fast mode**: "Fast mode (research preview) is available for Claude Opus 5.5 on the Claude API only; it is not available on Amazon Bedrock, Claude Platform on AWS, Google Cloud, or Microsoft Foundry." [verified: whats-new-opus-5-5] — 가격 $8/$40, Claude Code 에서도 사용 가능 [verified: anthropic.com/claude-opus-5-5]

### Effort

| 레벨 | 용도 (공식) |
|------|------------|
| `high` | **기본값.** "Start at the default effort level, `high`, then test the other levels (`low`, `medium`, `xhigh`, and `max`) against your own evals." |
| `xhigh` | capability-sensitive 워크로드. ⚠️ 단 "At `xhigh` and especially `max` effort, Claude Fable 5.1 can think for longer before it starts writing its reply … The simplest approach is to run requests like these at `high`, the recommended starting point, and move to `xhigh` or `max` only where you've measured a quality gain" |
| `max` | 가장 깊은 추론, 토큰 무제약 — overthinking·장문 출력 지연 주의 |
| `medium`/`low` | "At `medium`, results roughly match Claude Fable 5 at lower cost, so step down to `medium` or `low` where your evals show quality holds. At `low`, Claude Fable 5.1 is often competitive with Claude Opus and Claude Sonnet models on cost per task while scoring higher" |

⛔ **이전 모델 effort 값 재사용 금지**: "Re-run the sweep even if you already ran one on Claude Fable 5: effort level names don't correspond to the same amount of thinking across models." [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1]

**우선순위** [verified: code.claude.com/docs/en/model-config]:

1. 명시 선택 — `CLAUDE_CODE_EFFORT_LEVEL` 환경변수 · `--effort` 실행 플래그 · 세션 내 `/effort`
2. 모델 고유 default hold — Fable 5 · Opus 4.8 · Opus 4.7에만 존재. "Opus 5 and Fable 5.1 have no such hold"
3. 저장 설정 — 모델별 저장값 또는 `effortLevel` 키
4. 모델 default — "high on every model that supports effort, except that Opus 5.5 defaults to medium, Opus 4.7 defaults to xhigh" [verified: code.claude.com/docs/en/model-config, 2026-09-25 재조회]

- 설정 경로: `/effort` 슬라이더 · `--effort` 플래그 · `CLAUDE_CODE_EFFORT_LEVEL` · settings `effortLevel` · **스킬/서브에이전트 frontmatter `effort` 필드** (해당 스킬/에이전트 실행 동안만 override)
- ✅ **5.1 신규**: 세션 중간 effort 변경이 프롬프트 캐시를 무효화하지 않는다 (§2 per-message effort). "Re-tune effort from the default (`high`), and consider changing it mid-conversation instead of holding one level for the whole session."

### 현행 운용 (2026-09-06)

⚠️ 2026-09-06 정정 — 이전 판의 "사용 시점 가이드 (2026-06-12 배선)" 표는 **배선 상태 열이 전부 철회/미배선**이라 삭제했다. 현행은 3줄이다.

- **세션 effort = `xhigh`** (사용자 `/model` 실측). frontmatter `effort` 배선은 없다 (§effort frontmatter 배선 철회 유지).
- **워크플로 36콜 = `effort: 'xhigh'` 명시** — 생략하면 세션 값이 아니라 워커 모델 기본(Opus 5.5 `medium`)으로 돌아서(2026-09-25 실측) `xhigh` 를 보장하는 유일한 콜 단위 값. 공식 default는 Fable 5.1 `high` · Opus 5.5 `medium`이며, 변경 여부는 **fresh sweep 후 결정**한다 (사용자 결정 2026-09-25: `xhigh` 유지·하향 sweep 종결 · 재개 시 판정 절차: `modules/peer-review-tiers.md:225-227` — 같은 입력에 `xhigh`/`high` 각 1회, 검증된 critical·major 손실 0이 통과 기준).
- **`ultracode`는 effort arm으로 무효** (T0 실측) — 사용 가이드·배선 모두 대상 아님. `ultrathink` 키워드는 해당 turn만 심층 추론(effort 설정 불변)이며 "think hard" 류는 더 이상 키워드가 아니다.

> **T1 긴장 (공식 default vs fz 세션 운용)**: 공식 문서는 `high`를 출발점으로 두고(Opus 5.5 는 `medium`) `xhigh`/`max`는 "measured a quality gain" 이후로 미룬다. fz 세션·워크플로의 `xhigh` 상시 운용은 이 기본에서의 **의식적 이탈**로, 다중 파이프라인 오케스트레이션 난이도에 대한 사용자 결정이다 (공식 default를 몰라서가 아님 — `modules/peer-review-tiers.md`: "`xhigh`는 관성이 아니라 결정된 값이다"). 재판정은 위 짝 비교로만 한다.

### 안전 분류기 자동 폴백 (Claude Code 고유)

- 분류기가 요청을 flag하면 → **해당 요청을 폴백 Opus로 자동 재실행** + transcript에 notice → 세션이 Opus로 계속됨. 복귀는 `/model fable` 재실행. ⚠️ 2026-09-06 정정 — 폴백 대상은 **Opus 4.8 · Opus 5** 둘 다이며(§2 Fallback), 5.1은 폴백 시 프롬프트 캐시 전환 비용을 fallback credit으로 환급한다
- **첫 요청부터 발생 가능**: 워크스페이스 컨텍스트(CLAUDE.md, git status)만으로 트리거될 수 있음 → 진단: `claude --safe-mode`
- `/config`에서 "switch models when a message is flagged" 끄면 → flag 시마다 전환/프롬프트 수정 선택지 표시
- ℹ️ 5.1은 오탐이 줄었고 소스코드 취약점 탐색이 허용된다(§2 Refusal) → 폴백 빈도 재관측 대상

[verified: code.claude.com/docs/en/model-config]

### 서브에이전트 · 워크플로

- Agent tool `model` 파라미터 enum: `sonnet` / `opus` / `haiku` / **`fable`** [verified: 환경 실측 2026-06-12 — Claude Code v2.1.170+ Agent tool 스키마]
- Workflow `agent()` `opts.model`: 생략 시 **메인 루프 모델 상속** — 세션이 Fable이면 model 미지정 워크플로 에이전트도 Fable로 실행됨. ⚠️ 2026-09-06 정정 — 이 함정의 비용 영향은 "2배"가 아니다: 캐시 읽기가 지배하는 세션에서는 **+9%**, 출력·캐시쓰기 단가는 2배, 호출당 지연은 +49% [fz 실측 2026-09-06 — Opus 5 기준]. **함정 자체는 그대로 유효**하다(model 명시 의무 불변)
- `CLAUDE_CODE_SUBAGENT_MODEL`: 모든 서브에이전트/에이전트 팀 모델을 일괄 override (per-invocation `model` 파라미터·frontmatter보다 우선)
- `ANTHROPIC_DEFAULT_FABLE_MODEL`: `fable` alias 해석 대상 지정 (서드파티 프로바이더 폴백 식별에도 사용)
- `DISABLE_PROMPT_CACHING_FABLE=1`: Fable 모델만 프롬프트 캐싱 비활성 — ⚠️ 5.1에서는 캐시 읽기가 $0.25이므로 이 플래그의 비용 효과가 역전된다(끄면 비싸진다)

## 4. 최고 효율 사용 원칙 (공식 권고 요약)

> 원문: Prompting Claude Fable 5.1 · Claude Code Model configuration "Work with Fable 5.1 and Fable 5" 섹션. 아래는 요지 + 핵심 인용.

### 무엇을 맡길까

1. **결과를 기술하고 경로는 위임**: "Describe the outcome, not the steps"
2. **모호한 문제**: "Hand it ambiguous problems" — root-cause 조사, 장애 디버깅, 아키텍처 결정
3. **단일 세션보다 큰 작업**: "Size up larger tasks: give it work you would normally break into pieces."
4. **검증 리마인더 제거**: "Skip the verification reminders: it verifies its own work with less prompting, so reminders to test or check are usually unnecessary."
5. **long-horizon 자율 실행**: "Claude Fable 5.1 can execute very long tasks without much guidance on methodology, especially when the goal is clear."
6. ⛔ **공격적 사이버보안·생물학은 비대상 도메인** — "Claude Fable 5 is not intended for offensive cybersecurity or biology and life sciences work; requests in those domains can return `stop_reason: "refusal"`." [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5]. 5.1도 같은 분류 범주를 유지한다 — "Claude Fable 5.1 includes safety classifiers covering the same `stop_details` categories as Claude Fable 5" — 단 오탐은 줄었다: "Claude Fable 5.1's safety classifiers produce fewer false positives than Claude Fable 5's did at launch, and finding vulnerabilities in source code is permitted." [verified: whats-new-fable-5-1 + prompting-claude-fable-5-1]

[verified: code.claude.com/docs/en/model-config + platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1]

### Fable 5.1 신규 행동 (Fable 5 대비)

| 행동 | 공식 진술 | fz 함의 |
|------|----------|--------|
| 진행 보고 감소 | "Claude Fable 5.1's default behavior is to write fewer user-facing updates during long tool-calling turns than Claude Fable 5 does. This becomes more pronounced at higher effort and in longer tool chains." | ⛔ "hold all findings for the final response" 류 억제 문장은 제거 대상 — "Some earlier models were eager to give updates while working, which led to system prompt lines such as 'hold all findings for the final response.' Remove lines like that before adding anything." |
| 코딩 루프 배칭 저하 | "The exception is coding and computer-use loops where the next independent calls are implied by the task rather than explicitly requested … there it may issue them one per turn instead. This doesn't affect answer quality, but each extra turn costs tokens, a round trip, and wall-clock time." | ⛔ **fz 추가 금지** — 아래 스니펫 표 참조 |
| low effort 검색 감소 | "At `low` effort, Claude Fable 5.1 is less likely than Claude Fable 5 to call a search or retrieval tool, and more likely to answer from memory." | 탐색형 스킬(fz-search·fz-discover)의 sonnet/low 강등 시 회수율 확인 필요 |
| 전체 파일 재작성 경향 | "Claude Fable 5.1 is more likely than Claude Fable 5 to rewrite an entire text file rather than make a targeted edit. The resulting file is usually the same, but unless the file is short or most of it is changing, a rewrite costs more output tokens and time." | 출력 단가 $50 × 전체 재작성 = 시간·비용 동시 손실. changeset 반환형(code-pair)이 이 경향의 방어면 |
| xhigh/max 장문 지연 | "At `xhigh` and especially `max` effort, Claude Fable 5.1 can think for longer before it starts writing its reply … it may draft much of that deliverable in its thinking and then write it out again as the reply" | 장문 산출물 요청은 `high` 출발 — 단, 36콜 xhigh 재판정은 짝 비교 절차로만(§3 현행 운용) |
| Lead 비차단 위임 | "If your coding agent lets Claude Fable 5.1 delegate work to subagents, don't force the lead agent to stop and wait for each one. On coding tasks, letting the lead continue while subagents run lowers average time to completion at similar quality, token usage, and cost." … "The model still often chooses to wait. The time savings come from the runs where it carries on with other work." | §5 T2 긴장(one-shot Workflow 전환)의 재검토 입력 |

### 프롬프트 패턴 (공식 스니펫 — Fable 5 13종 + Fable 5.1 4종)

| 패턴 | 트리거 상황 | 핵심 문구 (요지) |
|------|-----------|----------------|
| Anti-overplanning | 모호한 작업에서 과잉 계획 | "When you have enough information to act, act." |
| No-tidying | 높은 effort에서 무요청 리팩토링 | "Don't add features, refactor, or introduce abstractions beyond what the task requires." |
| Grounded progress | 장기 자율 런의 상태 보고 | "Before reporting progress, audit each claim against a tool result from this session." (조작된 상태 보고 거의 제거 — Anthropic 실측) |
| Boundaries | 무요청 인접 행동 | "When the user is describing a problem... the deliverable is your assessment. Report your findings and stop." |
| Async subagents | 병렬 위임 | "Delegate independent subtasks to subagents and keep working while they run." |
| Memory | 세션 간 학습 | "Store one lesson per file with a one-line summary at the top." |
| Readability | 장기 에이전틱 세션의 최종 요약 | "drop the working shorthand. Write complete sentences... If you have to choose between short and clear, choose clear." |
| Brevity | 최종 응답의 장황함 | "Lead with the outcome" — 결론을 먼저, 근거는 뒤에 |
| Checkpoint | 자율 런 중 확인 요청 빈도 | "Pause only when [the decision] genuinely requires the user; otherwise proceed." |
| Memory bootstrap | 세션 시작 시 과거 학습 회상 | "Reflect on previous sessions [before you begin]." |
| Autonomous reminder | 장기 자율 실행 프레이밍 | "You are operating autonomously" — 완료까지 계속 진행 |
| Context reassurance | 컨텍스트 소진 불안으로 조기 압축/종료 | "You have ample context remaining" — 조기 요약·보존 불요 |
| Intent context | 요청에 이유(why)가 빠짐 | "Give the reason, not only the request" — why를 주면 how를 위임 가능 |
| **Batching nudge** (5.1) | 코딩 루프에서 독립 도구 호출이 turn당 1개로 쪼개짐 | "First privately list what you need next; then request every item that doesn't depend on another's result in this one response." |
| **Finish the whole task** (5.1) | 복잡한 비동기 워크로드에서 조기 turn 종료 | "On complex asynchronous workloads, though, nudge it not to end its turn before the work is done." |
| **Compaction preserve** (5.1) | 비용 절감 목적의 조기 압축 | "Because cache reads are now cheaper (see Pricing), compacting early to save cost may no longer be the right cost-intelligence tradeoff on Claude Fable 5.1, so experiment with later compaction points." |
| **Keep changes to the task** (5.1) | 요청 범위 밖 수정·테스트 파일 과다 커밋 | "When asked to implement an open-ended feature, Claude Fable 5.1 delivers what's asked for and sometimes more: it may fix nearby code, extend behavior the task didn't mention, or commit more test files than the change warrants. It responds well to explicit instructions about what to leave out." |

### Scaffolding 변경 권고 (이전 모델 대비)

- **De-prescribe**: "Skills developed for prior models are often too prescriptive for Claude Fable 5 and can degrade output quality. Review and consider removing older instructions if default performance is better." — 5.1이 철회하지 않았다(§Fable 5.1 상세 서문)
- **검증 리마인더 축소**: "Skip the verification reminders: it verifies its own work with less prompting, so reminders to test or check are usually unnecessary" [verified: code.claude.com/docs/en/model-config]
- **자기검증은 fresh-context 검증자로**: "Separate, fresh-context verifier subagents tend to outperform self-critique" — 제거 대상은 *자기재확인 지시*, 존치 대상은 *이종·fresh-context 검증자*
- ⛔ **reasoning 재현 지시 금지**: 내부 추론을 응답 텍스트로 echo/transcribe하라는 지시는 `reasoning_extraction` refusal 트리거 → Opus 폴백 증가. 기존 스킬의 "사고 과정을 보여라" 류 지시 감사 필요 (fz 전수 grep 실측 0건 — §점검 항목). **Opus 5.5 에도 적용** — "Requests that push the model to reproduce its internal reasoning in the response text can be declined with the `reasoning_extraction` category, which is new if you're coming from Claude Opus 5." [verified: prompting-claude-opus-5-5]
- **send_to_user 도구**: "When running long, asynchronous agents, give the agent a way to surface a message the user must see exactly as written, without ending its turn" — 도구 정의만으로 부족: "Defining the tool is not sufficient on its own; without an instruction in the system prompt, Claude Fable 5 rarely calls it." [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5 "Create a send-to-user tool" — 5.1이 철회하지 않은 진술]

## 5. fz 생태계 적용 전략

> ⛔ 이 섹션은 **권고**다. `workflows/*.js` `opts.model` 변경 등 동작 변경은 비용·지연 영향이 있으므로 별도 합의 후 적용한다.
> ⛔ **본 §5가 opus 동시 상한의 정본이다** (`modules/governance.md` § Truth-of-Source 지정). 모델 배정 정본은 `workflows/*.js` `opts.model` — 스킬 YAML `model-strategy`는 2026-08-09 제거(런타임 효과 0).

### 모델 전략 옵션 (4-axes)

| 옵션 | 품질 | 비용·시간 | 변경 범위 | 판정 |
|------|------|----------|----------|------|
| A. 재배선 이전 baseline (Lead=세션 모델, 워커 전반 sonnet) | 기준 | 기준 | 0 | 현행 아님 (재배선 확정으로 대체) |
| **B. Lead만 Fable** (사용자가 `/model fable` — 설정 변경 불요) | Lead 추론·오케스트레이션 ↑ | Lead 호출만 Fable 단가 — 캐시 지배 세션 **+9%**(Opus 5 기준), 출력·캐시쓰기 단가 2배, 호출당 지연 **+49%** [fz 실측 2026-09-06] | 0 (이미 가능) | **가동 중** |
| C. Primary 선택 승격 (capability-sensitive 단일 호출만 `model: 'fable'`) | 병목 단계 ↑ | 해당 호출만 Fable 단가 | 워크플로/스킬 일부 | **적용 확정** (판단 3지점 fable 고정: merge + direction ×2, lint `EXPECTED_FABLE=3`) — 추가 fable 승격(②③)은 측정 후 deferred |
| D. 전면 Fable | 최대 | 시간 **+49%** · 출력·캐시쓰기 단가 2배 (비용 총액은 캐시 지배 시 +9% — Opus 5 기준) | 전체 | ⛔ 비권장 — 공식이 "start with Claude Opus 5.5 for most workloads"이고, 이득 근거가 시간 손실을 넘지 못한다 |

- **B가 공식 포지셔닝과 정합**: Fable의 강점(long-horizon 자율성, 모호성 처리, 위임 관리)은 Lead 역할 그 자체 — "Use Claude Fable 5.1 for demanding reasoning and long-horizon agentic work". 워커 중 단순(retrieval·breadth) lens 작업은 Sonnet 5로 충분하고, 실질 분석·생산은 Opus 5.5가 담당
- **C (판단 3지점 확정 · ②③ deferred)**: ① 워크플로 merge/synthesis 단계 — **적용됨** (search-cross-verify stage3-merge; plan-collaborative 통합/integrate 단계는 생산 스테이지라 opus 유지 — AC-1) ② fz-review Primary — **Deferred** (AC-5) ③ fz-discover landscape 합성 — **Deferred** (AC-5). 도입 방법(②③): Workflow `agent()` `opts.model: 'fable'` 또는 Agent tool `model: "fable"` [verified: 환경 실측]
- ⛔ **동시 실행 상한 (불변)**: opus 동시 ≤3 · fable 에이전트 **동시 1개**(Lead 세션 제외) · 총 ≤4. ⚠️ 2026-09-06 정정 — 이전 판의 근거였던 "fable 1 ≈ opus 2 비용 등가 → 최대 동시 ≈ opus 5 equivalent"는 **캐시 읽기가 지배하는 세션에서 성립하지 않는다**(Fable 5.1 캐시 읽기 $0.25 < Opus 5 $0.50). 상한 **수치는 유지**하되 근거는 **출력·캐시쓰기 단가 2배 + 호출당 지연 +49%**로 교체한다(Opus 5 기준 수치). 비용 등가 산식 재산정은 P1 sweep 이후 [fz 실측 2026-09-06]
- ⚠️ **Workflow model 생략 함정**: `opts.model` 생략 시 메인 루프 모델 상속 — Fable 세션에서는 모든 미지정 에이전트가 Fable로 실행됨. fz workflows는 현재 전 호출에 model + `effort: 'xhigh'` 명시(opus/sonnet + 판단 3지점 fable)되어 있어 안전 (workflows/*.js 6파일 전수 명시). `scripts/lint-model-explicit.sh`가 기계 검증 (전 호출 model + effort 명시 + fable=3 고정)

### 재배선 확정 배선 (정적 45콜) — 현행

판단 3지점 fable 배선에 이어 비-Lead 워커의 opus/sonnet 분할이 확정됐다. 정적 콜사이트 36개 기준이 현행이다:

- **판단 = fable 3** (불변, Fable 5.1) — search-cross-verify merge + plan-collaborative direction ×2. lint `EXPECTED_FABLE=3` 고정
- **실질 분석·생산 워커 = opus 36** (`opus` alias = Opus 5.5 — Claude Code 2.1.280+) — plan/peer-review/review-live/code-pair의 impact·edge·arch·quality·correctness·cross-critique(CC)·counter·recheck·review 등 capability-sensitive 스테이지 (4-axes A의 "워커 전반 sonnet" baseline을 대체)
- ⛔ **2026-09-12 fz-plan 배선 전환**: 기본 워크플로가 `plan-collaborative.js`(6단계 9콜) → **`plan-lean2.js`(2단계 4콜)**. wall 3,492s→1,344s(-61.5%). ⭐ 근거의 핵심은 **노이즈 바닥 교정** — 같은 9콜 구조를 동일 입력·트리로 2회 실행하니 상호 고유 major 5건·`Q-superior`(동등 아님)였다. run-to-run 분산이 구조 간 차이보다 크므로 "손실 0" 임계는 도달 불가능했고, 새 배선의 발산(3)은 그 바닥(5) 이하다. ⛔ N=1 — 실사용 3회 후 재평가(`experiment-log.md` §5.9). 롤백은 `skills/fz-plan/SKILL.md` 절차 2.5·3 의 스크립트명 원복
- **단순(retrieval·breadth) = sonnet 6** (Sonnet 5) — search stage1·2 + discover lens fan-out·cost-lens
- 전 45콜 `effort: 'xhigh'` 명시 — 생략하면 워커 모델 기본(Opus 5.5 `medium`)으로 도는 콜 단위 값(2026-09-25 실측). ⛔ 값 변동은 `scripts/lint-model-explicit.sh --baseline tests/fixtures/model-effort-baseline.json` 이 **label 별로** 대조한다(줄 수 세기는 콜별 변경을 못 잡는다). sweep 결과는 `experiment-log.md` §5.8 ⑥ · 구조 ablation 은 §5.9. **공식 default는 Fable 5.1 `high` · Opus 5.5 `medium`**이며, 변경 여부는 fresh sweep 후 결정한다(사용자 결정 2026-09-25: `xhigh` 유지·sweep 종결) (짝 비교 절차: `modules/peer-review-tiers.md:225-227` — 같은 입력에 `xhigh`/`high` 각 1회, 검증된 critical·major 손실 0). ⛔ 이 문서는 하향을 권고하지 않는다 — `xhigh`는 사용자가 유지를 택한 결정된 값이다
- opus 동시 실행 ≤3 (Lead=fable 제외, 총 ≤4)
- **runtime fan-out**: discover lens 등 정적 1콜이 런타임 N인스턴스로 전개 — 동시성·비용은 런타임 기준 별도 계산

> **T2 긴장 (long-lived subagents vs one-shot Workflow)**: 공식 §4 "Async subagents" 권고는 long-lived subagent가 read를 캐시해 토큰을 절감한다고 본다. fz의 one-shot Workflow `agent()` 전환은 그 캐시 절감을 **결정성**(재현 가능한 model·effort·스폰 순서)과 TEAM 스톨 회피(실측)와 맞바꾼 의식적 이탈이다. 상실한 캐시 절감분은 `experiment-log.md` 관측 컬럼(정적 콜 비용·캐시 히트)에서 상쇄 가설로 추적한다. ℹ️ 5.1은 여기에 **시간 축 근거**를 추가했다 — "letting the lead continue while subagents run lowers average time to completion at similar quality, token usage, and cost" — Lead 비차단 위임은 재검토 입력이다.

### 운용 패턴 (Lead=Fable 5.1 세션 — 2026-09-06)

> B안 가동 상태에서 fable 강점을 실제로 끌어내는 3패턴. 새 주장 없이 §4 공식 권고를 fz 운용에 대응시킨 것.

- **ⓐ 에스컬레이션 종점**: Gate 반복 실패·디버깅 막다른 길(워커 2사이클 루프)에서만 fable 단발 root-cause 에이전트를 스폰 — 동시 1 상한(위 4-axes C) 내 단발로만, 상시 승격 아님. 공식 "when your evals on Claude Opus 5.5 at higher effort still fall short"에 정합.
- **ⓑ long-horizon 세션**: 평소 쪼개던 다중 파이프라인을 한 세션에서 처리 — 공식 §4 "Size up larger tasks: give it work you would normally break into pieces" + 1M 컨텍스트 + 티켓 폴더 아티팩트 누적의 시너지. 단, 단일 요청이 수 분 소요(§2 Turn 길이)이므로 진행 표시·타임아웃 설계 병행. ℹ️ 5.1은 진행 보고를 **덜** 쓴다(§4 신규 행동) — 진행 표시 설계는 도구·훅 층으로 옮기는 편이 안전하다.
- **ⓒ outcome-delegation**: 승인 후 실행 경로는 Lead 재량에 위임 — 공식 §4 "Describe the outcome, not the steps". 승인 게이트 이후 step 단위 지시 대신 성공 기준만 전달.

### effort frontmatter 배선 — **2026-06-14 철회 (세션 운용 전환)** · 잔여 후보 기록

스킬/서브에이전트 frontmatter `effort` 필드로 실행 중 override 가능 [verified: code.claude.com/docs/en/model-config]:
- ~~적용: fz-plan·fz-review·fz-discover·fz-search `effort: xhigh` (4스킬)~~ → **철회 (2026-06-14)**: frontmatter 4건 제거. ⚠️ 2026-09-06 정정 — 당시 근거였던 "사용자 effort 운용 = 세션 max(기본)/ultracode 확정"은 현행이 아니다. **현행 세션 effort = `xhigh`**이고 `ultracode`는 effort arm으로 무효(T0 실측)다. 철회 결론(frontmatter 배선 불요)은 유지된다 (§3 현행 운용)
- 잔여 후보: fz-commit·fz-pr 등 경량 스킬 `effort: medium` — 공식 기본값(high)이 대부분 작업에 적정이므로 **측정 없이 선제 강등 금지** (31차 Plan-before-Probe / 35차 Calibrate-from-Real). ℹ️ 5.1은 `medium`에서 "results roughly match Claude Fable 5 at lower cost"라고 명시 — sweep 대상 우선순위 상향 근거

### De-prescription 긴장 — fz Gate 체계와의 관계

공식 권고("too prescriptive → degrade output quality")와 fz의 **트리밍 비저하 원칙**(Gate 체크리스트·Few-shot·절차적 Step 삭제 금지)은 표면 충돌하나:

1. `skill-authoring.md`의 **DELETE/MERGE-default 규칙이 이미 같은 방향** — 추가 충동마다 "무엇을 지울 수 있나" 선검토
2. Gate 체크리스트는 *행동 가드레일*(사고 방지)이고, 공식 권고의 대상은 *절차 밀도*(step-by-step 지시) — 재평가 대상은 후자
3. 적용 절차: 개별 스킬에서 절차 지시 제거 A/B → 품질 비저하 확인 후 반영 (Phase 5 실험 프레임 `experiment-log.md` 활용). **일괄 트리밍 금지**

ℹ️ 5.1은 이 긴장을 바꾸지 않는다 — "Your existing Claude Fable 5 prompts should perform well on Claude Fable 5.1 without changes". 다만 §4 신규 행동 중 "fewer user-facing updates"는 **삭제 방향의 신규 대상**을 하나 지정한다("hold all findings for the final response" 류 억제 문장).

### 프롬프팅 스니펫 채택 현황 (Fable 5 13종 실측 2026-06-12 · Fable 5.1 4종 2026-09-06)

> ⛔ 일괄 주입 금지 (DELETE/MERGE-default) — 기존 규약 중복을 실측한 후 빈 곳만 채택. 비채택 근거를 남겨 재논의 시 추적 가능하게.

| 공식 스니펫 | 판정 | 근거 |
|------------|------|------|
| Grounded progress | **채택** | 기존 진행 보고 grounding 0건 [verified: rg 무매치 2026-06-12] → fz SKILL VD Brief 4번 + team-core 트리거 주입 + workflows 5파일 OVERRIDE 배선. 16/18차(태그≠검증)·Workflow [verified] 오측의 직접 방어 |
| Anti-overplanning | **보강** | lead-action-default 33차 row가 동등 기능 기존재 — Fable 공식 출처 1구만 추가 |
| Boundaries | 비채택 | lead-action-default 40차 row + MAST FM-2.2(AskUserQuestion 의무) 기존재 |
| No-tidying | 비채택 | fz-code "관찰 보고 의무"(범위 외 발견 → 기록만, 실행 금지) + Scope Minimality 기존재 |
| Memory | 비채택 | memory-curator + L1 topic file 체계 기존재 |
| Readability | 비채택 | Claude Code 하네스 시스템 프롬프트 내장 영역 — 플러그인 중복 주입 회피 |
| Async subagents | 비채택(이관) | 구조 트랙(오케스트레이션 레이어 background 위임) — 별도 사이클. 5.1 "lead 비차단" 진술로 재검토 입력 추가(T2) |
| Brevity | 비채택 | Claude Code 하네스 output style 내장 영역 — 플러그인 중복 주입 회피 (Readability와 동일 근거) |
| Checkpoint | **채택** | lead-action-default genuine-need Gate가 동등 판단 기준 — "genuinely requires"를 승인 게이트 판정선으로 성문화. 단 Phase 4 최상위 승인 등 non-overridable 게이트는 제외 |
| Memory bootstrap | 비채택 | memory-curator + L1 topic file 회상 체계 기존재 |
| Autonomous reminder | **채택** | execution-modes LOOP 모드 한정 배선 — 자율 반복 실행 프레이밍(상시 주입 아님) |
| Context reassurance | **채택** | fz SKILL `/compact` 안내 문구를 "충분한 컨텍스트 잔량" 프레이밍으로 재구성 반영 — 조기 압축·종료 방어 |
| Intent context | **채택** | skill-authoring §12 규약 성문화(agent 스폰 시 intentContext 3요소) + plan CTX 목적 축 |
| **Batching nudge** (5.1) | ⛔ **비채택 — fz 추가 금지** | Claude Code가 이 문장을 **turn-scoped 시스템 메시지로 이미 주입**한다 [fz 실측 2026-09-06 — report.md §3]. fz가 다시 넣으면 중복 주입 |
| **Finish the whole task** (5.1) | 비채택(기존재) | `modules/execution-modes.md` § autonomous-reminder(LOOP 한정)가 동등 — "마지막 문단이 계획·의도·다음 단계 선언이면 해당 tool call을 실제로 실행하고, 종료는 작업 완료 또는 사용자만 줄 수 있는 입력 대기 시에만" [verified: 코드 실측 2026-09-06] |
| **Compaction preserve** (5.1) | **미판정 (보강 후보)** | 접점은 Context reassurance 채택 행과 `skills/fz/SKILL.md:339` "4스텝+ 시 /compact 안내". 그 트리거는 **스텝 수 기반**이지 비용 기반이 아니므로 5.1의 "later compaction points"와 직접 충돌하지는 않는다. 4스텝+ 임계가 캐시 읽기 $0.25 하에서 여전히 적정인지는 **미측정** → P1 sweep 항목 |
| **Keep changes to the task** (5.1) | 비채택(기존재) | No-tidying 행과 동일 근거 — `skills/fz-code/SKILL.md:268` 관찰 보고 의무("실행 금지, 범위 외 정리 금지") + `modules/code-transform-validation.md` Scope Minimality [verified: 코드 실측 2026-09-06] |

### 점검 항목 (후속 작업 후보)

- [x] fz 스킬/모듈 중 "사고 과정·추론을 출력하라" 류 지시 전수 grep → `reasoning_extraction` refusal 위험 평가 — **실측 0건** (2026-06-12, skills/·modules/·agents/·workflows/ 전수. `reasoning`/`사고` 매치는 전부 추론 품질·모듈명 등 정상 용법)
- [ ] Fable 세션에서 fz-review self-review 품질 재측정 → GPT cross-model 의존도 재조정 (단, 이종 blind-spot 안전망 자체는 유지 — 15차/23차). **→ 본 감사의 P1 sweep에 연결**: 짝 비교 절차는 `modules/peer-review-tiers.md:225-227`
- [ ] **P1 effort sweep (신설)** — 36콜 `xhigh` ↔ `high` 짝 비교. 공식 근거 "Re-run the sweep even if you already ran one on Claude Fable 5". ⛔ 결과 전까지 하향 금지
- [ ] **Compaction 임계 재측정 (신설)** — `skills/fz/SKILL.md:339` 4스텝+ `/compact` 안내가 캐시 읽기 $0.25 하에서 적정한지
- [x] `/model` effort 세션 지속성 실측 — **해소** (2026-07-05 `/model` 피커 stdout 실측). ⚠️ 현행 값은 `xhigh` (2026-09-06)
- [x] async subagent 권고 반영 — one-shot Workflow `agent()` 전환으로 대체 결정 (T2 긴장 참조). TEAM(SendMessage) async 패턴 배선은 미채택

## 설계 원칙

- Progressive Disclosure: 이 가이드는 **모델 운용 결정 시에만** 로드
- Tier 1 인용 원칙 (`prompt-optimization.md` 출처 표기 규약 준수)
  - ⛔ **줄 수 제한 없음** — 500줄 한도는 SKILL.md 본문 전용이다. 가이드·모듈은 대상 아님
    (정본: `prompt-optimization.md` §2 Scope Clarification · `harness-engineering.md` §설계 원칙)
