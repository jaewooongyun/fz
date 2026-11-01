# guides/prompt-optimization.md — 옮긴 근거 · 이력

> 아래 줄은 2026-11-01(H2-2)에 `guides/prompt-optimization.md` 에서 글자 그대로 옮겼다. 규칙은 원문에 그대로 있다.

## 원칙 1: Claude가 모르는 것만 추가

**근거:** Anthropic — "Claude is already very smart." 일반 지식을 반복하면 토큰만 소비하고 성능은 올라가지 않는다.

## 원칙 3: 500줄 이하 + Progressive Disclosure

**근거:**
- Context Rot (Chroma) — "focused 300 tokens > unfocused 113K tokens"
- Anthropic 32p Guide — 3-level progressive disclosure

## 보충 4a: 원칙+이유로 프레이밍하라

**근거:** Anthropic Claude 4 Best Practices — "Prefer general instructions over prescriptive steps.
Claude's reasoning frequently exceeds what a human would prescribe."
+ IFScale (arXiv:2507.11538) — 규칙 수 증가 시 정확도 저하 (500규칙→68%).

## 원칙 5: Few-shot 예시 > 장문 설명

**근거:** Anthropic + academic survey consensus. 3줄의 BAD/GOOD 대비 예시가 30줄의 설명보다 효과적이다.

## 원칙 6: 피드백 루프 내장 — 외부 검증 우선

**근거**: §3b H2 참조 — "Self-evaluation is unreliable." 같은 모델이 생성하고 같은 모델이 검증하면 동일한 맹점을 공유한다.

## 원칙 7: 도구 설명에 프롬프트만큼 공 들이기

**근거:** Building Effective Agents — "Tool descriptions deserve as much prompt engineering as the prompt itself."

## 원칙 8: 과격 표현 제거 (instruction-following 일관성)

**근거:** Anthropic Claude 4 Best Practices + **Fable 5는 짧은 지시로 대부분 행동을 조향할 수 있다** — "steer most behaviors with a brief instruction rather than enumerating each behavior by name" [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5]. 과격·모호한 지시는 그대로 적용될 위험 → 자연스럽고 범위가 명시된 지시가 정확도를 높인다. (GPT-6 계열도 같은 방향 — "GPT-6 Astra is stronger at general instruction following than our previous models … It can be more sensitive to instructions contained in skills and other files, such as AGENTS.md." [verified: developers.openai.com/api/docs/guides/latest-model, 2026-09-25 재조회] — fz 교차검증 모델 `gpt-6-sol` 한정 진술은 이 페이지에 없다 [미검증: Sol 한정 문면 부재] — GPT 측 동일 가드.) (이력 — "fz 교차검증 모델 `gpt-6-sol`"은 2026-09 당시 표기. 현행: fz 의 GPT 모델은 세션 선택(없으면 `config.toml` — `modules/gpt-strategy.md` § 모델·effort 선택)이고, GPT CLI 문서의 코딩 에이전트 출발점은 `gpt-6.1-sol` 이다 — 대부분의 작업은 `gpt-6.1-sol` 에서 시작하라고 권한다(로그인 계정·워크스페이스에 접근 권한이 있을 때 — 원문 의역) [verified: learn.chatgpt.com/docs/agent-configuration/subagents]. 같은 latest-model 페이지는 스킬 감사를 강하게 권한다 — "We **strongly recommend** auditing skills and other files accessible to your model for instructions that could influence its behavior." [verified: developers.openai.com/api/docs/guides/latest-model]) Anthropic 쪽 인용의 Fable 5 는 legacy 모델이다 — 5.1 페이지는 "Your existing Claude Fable 5 prompts should perform well on Claude Fable 5.1 without changes" 라고 해 상속 근거로 둔다 [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1]. ⚠️ 2026-09-06 정정: 이전 근거였던 "Opus 4.8은 지시를 일관되게 따른다"[verified: anthropic.com/news/claude-opus-4-8]는 2세대 전 announcement라 단독 근거로 부적절 — Fable 5 인용으로 교체.

**Why this matters:**
- 최신 모델일수록 지시를 일관되게(consistency) 따른다 — 세대별 근거는 위 본문 `[verified:]` 참조
- 과격한 표현은 불필요한 상황에서도 해당 행동을 트리거함
- 결과: 과도한 도구 호출, 불필요한 검증 반복, 서브에이전트 남용
- 자연스럽고 구체적인 표현이 더 정확한 행동을 유도함

## 원칙 9: Boundaries 명확히 명시

**근거:** 명확한 경계 설정이 스킬 간 충돌을 방지하고 예측 가능한 행동을 보장한다.

## 원칙 10: 평가 먼저, 문서 나중

**근거:** Anthropic — "evaluation-driven development." 평가 없이 작성한 프롬프트는 실제 효과를 알 수 없다.

## 1b. TEAM 모드 추론 품질 3원칙 (2026-03-10 추가)

> Sources: MAST (NeurIPS 2025, arXiv 2503.13657), Multi-Agent Collaboration Survey (arXiv 2501.06322), CONSENSAGENT (ACL 2025), Addy Osmani: The Code Agent Orchestra (2026)
> Harness: Harness Design for Long-Running Apps (Anthropic 2026-03) — "self-evaluation is unreliable" → cross-model 검증 정당화

## 다양성 (Diversity)

- MAST (NeurIPS 2025): inter-agent misalignment(FC2) = 36.94% (FC1 41.77% / FC3 21.30%, 합 100%; 논문 명시 "단일 지배 카테고리 없음 — balanced" — 세 범주 백분율은 **v2** 원문 [arxiv preprint, 2025-03, v2], v3 에는 없다). "false consensus"가 주요 실패 모드 중 하나. 특히 **FM-2.2 "Fail to ask for clarification" = 6.80%** [verified: MAST v3 §4 원문 "(FM-2.2, 6.80%)"] — 모호한 요청을 그대로 진행하면 trigger (MAST-Data 7개 프레임워크 / 1642 traces).
- CONSENSAGENT (ACL 2025): 동적 프롬프트 정제(dynamic prompt refinement)로 sycophancy를 런타임에 완화. 정적 방어(Round 1 독립성)와 동적 방어(상호작용 중 교정)를 결합하면 효과 극대화.
- Multi-Agent Collaboration Survey (arXiv 2501.06322): 협업 구조를 peer/centralized/distributed로 분류. fz의 Peer-to-Peer 패턴은 "peer" 구조 + "role-based" 전략의 조합.

## Scope Clarification (적용 경계)

**Why**: "집중>분산" 원칙이 "전체 분석 요청에서 선별 읽기"의 정당화로 오용될 수 있다. 원칙의 적용 경계를 명시하여 thought-terminator 방지.

## 3. ACE 패턴: 진화하는 플레이북

> Source: ACE - Agentic Context Engineering v3 (Stanford, ICLR 2026, arXiv 2510.04618)
> ACE v3 성과: +10.6% agent 벤치마크, +8.6% finance 벤치마크. Context collapse와 brevity bias를 structured incremental updates로 해결.

## 3b. 하네스 엔지니어링 원칙 (2026-04-16 추가)

> Sources: Anthropic Engineering 3부작
> - Effective Harnesses for Long-Running Agents (2025-11)
> - Harness Design for Long-Running Application Development (2026-03)
> - Scaling Managed Agents: Decoupling the Brain from the Hands (2026-04)
> 추가: Inside the Scaffold (arXiv 2604.03515, 2026-04) — 13개 코딩 에이전트 스캐폴드 분석

Anthropic이 자사 에이전트 운영 경험에서 도출한 하네스 설계 원칙. fz 생태계의 아키텍처 결정을 공식 근거로 뒷받침한다.

## 원칙 H6: 5가지 루프 프리미티브

> Inside the Scaffold (arXiv 2604.03515): 13개 코딩 에이전트 분석 결과, 5가지 기본 루프 패턴.
