# LLM·AI 권위 자료 레퍼런스

> 목적: Claude Code로 iOS/Swift 앱 작업(요구사항·리팩토링·멀티파일·리뷰·빌드/테스트)을 **오류·누락·환각 없이 최고 성능**으로 수행하기 위한 외부 권위 자료 단일 참조점. fz 가이드·스킬 개선 시 1차 출처로 사용한다.
> **Sources (last audited: 2026-06-28):** Tier 1 공식 / Tier 2 arxiv·peer-reviewed / Tier 3 커뮤니티(supporting only).
> **모델 정책: Opus 4.8 only** — 구버전 backward-compat는 수록하지 않는다(§5).
> 인용 규약: `[verified: Tier1·2]` 단독 가능 / `[community: …]` 단독 verified 금지(supporting only).

## Tier 정책
| Tier | 출처 | 단독 verified |
|------|------|--------------|
| 1 | 공식 (Anthropic / Apple) | ✅ |
| 2 | peer-reviewed / arxiv | ✅ (preprint은 `[arxiv preprint]` 명시) |
| 3 | Medium / 블로그 / 커뮤니티 | ⛔ supporting only |

---

## 1. Tier 1 — 공식

### 1.1 Claude Code 운용 (code.claude.com/docs/en)
| 페이지 | 핵심 (verified 2026-06-28) |
|--------|---------------------------|
| /memory | CLAUDE.md/auto memory는 **"context, not enforced configuration"** — strict 준수 보장 없음. <200줄 target, bloat 시 규칙 무시. specificity(검증 가능하게)·consistency(모순 시 임의 선택). |
| /best-practices | **hooks=결정론적 보장 vs CLAUDE.md=advisory.** plan mode(explore→plan→implement→commit)는 불확실/멀티파일/낯선 코드에만, one-sentence diff은 skip. verifier(pass/fail oracle)로 루프 자율 종료. |
| /hooks | exit 2=차단(stderr→Claude 피드백), exit 1=non-blocking, exit 0=success(JSON 파싱). PreToolUse는 실행 전 차단. 30개 lifecycle 이벤트, 모델 결정과 무관히 자동 실행. |
| /sub-agents | 격리 context window + custom system prompt + 특정 tool + summary만 반환. MD+YAML(body=system prompt), `.claude/agents`(project) > `~/.claude/agents`(user) 우선순위. description으로 자동 위임, "use proactively"로 유도. |
| /skills | **progressive disclosure** — body는 invoke 시에만 로드, description만 상시. budget 설정 `skillListingBudgetFraction`·`SLASH_COMMAND_TOOL_CHAR_BUDGET`. invoke된 skill은 세션 내내 단일 메시지로 지속, 재read 안 함. |

### 1.2 모델 프롬프팅 (Opus 4.8 — platform.claude.com/docs/en)
| 페이지 | 핵심 |
|--------|------|
| prompt-engineering/prompting-claude-opus-4-8 | 코딩/agentic = **effort `xhigh`** 권장, shallow reasoning 시 프롬프팅 말고 effort↑. **`max`="prone to overthinking, diminishing returns"**. 더 literal한 instruction following → scope 명시. code-review는 "coverage 단계 + 별도 verification 단계" 분리 권장. |
| prompt-engineering/claude-4-best-practices | be explicit / parallel tool calls(`<use_parallel_tool_calls>`) / self-correction chaining(draft→review→refine). **adaptive thinking이 extended thinking보다 우수.** **공식 anti-overengineering·anti-hallucination 프롬프트 제공**(§4). |
| extended-thinking | adaptive thinking Opus 4.8/Sonnet 4.6 자동 적용 (비교 우위 근거는 위 claude-4-best-practices 행). |
| structured-outputs | JSON schema 강제 출력 (prefill 대체 경로). |

### 1.3 iOS/Swift
| 출처 | 핵심 |
|------|------|
| anthropic.com/news/apple-xcode-claude-agent-sdk | **Apple Xcode 26.3(2026-02-03)가 Claude Agent SDK 네이티브 호스팅.** "goal을 주면 스스로 task 분해·파일 수정·iterate." explore→이해→변경위치 식별 후 코딩. Xcode Previews로 시각 검증. |
| xcodebuildmcp.com (XcodeBuildMCP) | xcodebuild/simctl/devicectl 래핑 MCP — build·test·UI automation(tap/swipe/screenshot/snapshot_ui)·LLDB·로그. **구조화 JSON이 3,000줄 빌드로그보다 토큰 효율↑.** 에이전트는 Swift 작성엔 강하나 검증엔 blind → MCP가 edit-build-verify 루프를 닫음. |

---

## 2. Tier 2 — 학술 (arxiv, 2026-06-28 export API 실증)

> ⚠️ 존재·제목·저자·날짜는 API 확인. 각 논문에 귀속된 **정량 주장**은 인용 시 abstract 재확인 권장.

| arxiv | 제목 | 1저자 | 날짜 | 핵심 / fz 적용 |
|-------|------|-------|------|---------------|
| 2502.08235 | The Danger of Overthinking | Cuadron (Berkeley) | 2025-02 | overthinking↑→성능↓; 저-overthinking 후보 선택 ~30%↑·43%↓ (k=2: 27%·43%↓ / k=3: 30%·~15%↓, 단일 operating point 동시성립 X). harness 운영점 원칙 |
| 2504.20799 | Hallucination by Code Generation LLMs: Taxonomy/Benchmarks/Mitigation | Lee | 2025-04 | 환각이 특정 실행경로서만 발현·미탐지 잔존 → verifier 루프 동기 |
| 2507.19457 | GEPA: Reflective Prompt Evolution Can Outperform RL | Agrawal/Khattab | 2025-07 (ICLR 2026 Oral) | reflective prompt opt > GRPO 6~20%·35x↓ rollout, > MIPROv2 10%+. 프롬프트 최적화 |
| 2508.11126 | AI Agentic Programming: A Survey | Wang | 2025-08 | SWE-bench가 멀티파일/빌드/iOS 과소대표; 고정 context→외부 memory |
| 2503.13657 | **Why Do Multi-Agent LLM Systems Fail? (MAST)** | Cemri (Berkeley) | 2025-03 | 14 failure modes / 3 범주(specification·inter-agent misalignment·task verification), κ=0.88. fz TEAM 실패 진단 |
| 2501.06322 | Multi-Agent Collaboration Mechanisms: A Survey | Tran | 2025-01 | 협업 유형/구조/전략/프로토콜 분류 |
| 2406.07496 | TextGrad: Automatic 'Differentiation' via Text | Yuksekgonul | 2024-06 | 텍스트 기반 자동 미분, DSPy 보완 |
| 2502.18080 | Towards Thinking-Optimal Scaling of Test-Time Compute | Yang | 2025-02 | 도메인별 optimal CoT length 상이 |
| 2507.11538 | How Many Instructions Can LLMs Follow at Once? | Jaroslawicz | 2025-07 | instruction-following 한계 — CLAUDE.md/스킬 규칙 수 설계 |
| 2603.25723 | Natural-Language Agent Harnesses | Pan | 2026-03 | 자연어 하네스 |
| 2603.05344 | Building Effective AI Coding Agents for the Terminal | Bui | 2026-03 | 터미널 코딩 에이전트 scaffolding/harness/context |
| 2603.28052 | Meta-Harness: End-to-End Optimization of Model Harnesses | Lee | 2026-03 | 하네스 설계가 모델 가중치만큼 중요 |
| 2604.21003 | The Last Harness You'll Ever Build | Seong | 2026-04 | Two-level Harness Evolution |
| 2604.20938 | HARBOR: Automated Harness Optimization | Sengupta | 2026-04 | Constrained-Noisy-BO |
| 2604.25850 | Agentic Harness Engineering | Lin | 2026-04 | observability 기반 자동 진화 |
| 2604.08224 | Externalization in LLM Agents | Zhou | 2026-04 | Memory/Skills/Protocols/Harness 통합 review |
| 2604.20801 | Synthesizing Multi-Agent Harnesses for Vulnerability Discovery | Liu | 2026-04 | 멀티에이전트 하네스 합성 |
| 2604.10739 | When More Thinking Hurts | Zhou | 2026-04 | overthinking 위험 (긴 CoT 성능 저하) |
| 2604.08216 | MemCoT: Test-Time Scaling through Memory-Driven CoT | Lei | 2026-04 | training-free memory CoT |
| 2605.13357 | AI Harness Engineering: A Runtime Substrate | Zhong | 2026-05 | 하네스 런타임 substrate |
| 2605.00663 | Affordance Agent Harness | Huang | 2026-05 | verification-gated skill orchestration |

---

## 3. Tier 3 — 커뮤니티 (supporting only, 단독 verified 금지)
- twocentstudios "Closing the Loop on iOS with Claude Code" / blakecrosley "Building iOS Apps with AI Agents" / bleepingswift "Xcode Agent Skills in Claude Code" — iOS 에이전트 실무.
- linas.substack "Opus 4.8 Prompting Playbook" — 프롬프팅 실무.

---

## 4. 핵심 원칙 (verified 종합) — fz 설계 정합

> 약어: O1 /memory · O2 /best-practices · O3 /hooks · O4 /sub-agents · O5 /skills · O6 prompting-opus-4-8 · O7 claude-4-best-practices · O8 extended-thinking (모두 §1 Tier 1) · P1 2502.08235 · P2 2504.20799 · P3 2507.19457 · P4 2508.11126 (§2 Tier 2).
1. **하네스 레벨 결정론적 강제**: 신뢰성 필수 동작은 advisory memory가 아니라 hooks. [Tier1 §1.1]
2. **verifier + adversarial review**: pass/fail oracle로 루프 종료 + 구현자≠채점자(fresh model 반박). [Tier1 §1.1 + P2]
3. **context 절약 + 적정 reasoning**: subagent 격리; CLAUDE.md prune; overthinking은 단조 이득 아님. [Tier1 + P1]
4. **공식 anti-패턴 프롬프트** (fz Surgical Changes/Verification Discipline 정합):
   - anti-overengineering: "Only make changes directly requested or clearly necessary… A bug fix doesn't need surrounding code cleaned up." [O7]
   - anti-hallucination: "Never speculate about code you have not opened… MUST read the file before answering." [O7]
   - subagent 과용 경계: 단일파일·순차 작업은 직접, 병렬·격리·독립 워크스트림에만 위임. [O7]

## 5. 구버전 제거 정책 (Opus 4.8 only)
fz는 항상 최신 모델(현재 **Opus 4.8**)만 타깃. 다음 구버전 backward-compat는 **수록·권장하지 않는다**:
- manual `budget_tokens` extended thinking — Opus 4.7+/Fable 5/Mythos 5에서 **400 에러**. → adaptive thinking + effort + max_tokens.
- prefilled responses (마지막 assistant turn) — **Claude 4.6+ 미지원**. → structured outputs / user turn 주입.
- `interleaved-thinking-2025-05-14` beta header — **4.6+ deprecated·ignored**.
- over-prompting / anti-laziness ("If in doubt, use [tool]") — 최신 모델서 overtrigger 유발 → dial back.

## 6. fz 가이드 적용 매핑
| 가이드 | 관련 §·출처 |
|--------|------------|
| harness-engineering | §4(원칙) · O1·O2·O3 · P1 |
| prompt-optimization | §5(구버전) · §4(anti-패턴) · P2·P3 |
| agent-team-guide | MAST(2503.13657) · O4 · P4 |
| skill-authoring · skill-troubleshooting | O5 · O4 · O3 |
| skill-testing | §4-2(verifier) · O2·O6 |
