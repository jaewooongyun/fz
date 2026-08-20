# LLM·AI 권위 자료 레퍼런스

> 목적: Claude Code로 iOS/Swift 앱 작업(요구사항·리팩토링·멀티파일·리뷰·빌드/테스트)을 **오류·누락·환각 없이 최고 성능**으로 수행하기 위한 외부 권위 자료 단일 참조점. fz 가이드·스킬 개선 시 1차 출처로 사용한다.
> **Sources (last audited: 2026-08-08):** Tier 1 공식 / Tier 2 arxiv·peer-reviewed / Tier 3 커뮤니티(supporting only).
> ⛔ **감사 축 명시**: 2026-08-08 감사는 **§1.1·§1.1b(code.claude.com 운용 문서)** 전수 대조다. §1.2(platform.claude.com 프롬프팅)는 **2026-07-25 대조 그대로**이고, §2 arxiv·§3 커뮤니티는 **미대조**다 — 하지 않은 감사를 주장하지 않는다.
> **모델 정책: Opus 5 only** (`claude-opus-5`, 2026-07-24 출시) — 구버전 backward-compat는 수록하지 않는다(§5).
> ⚙️ **이 줄이 SSOT다** — `scripts/lint_doc_freshness.py`가 `모델 정책: <X> only` 를 파싱해 "현행 모델"을 결정한다. 새 모델 출시 시 **이 한 줄을 먼저 갱신**하면 lint가 나머지 문서의 stale 모델 참조를 자동 검출한다.
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
| /changelog (v2.1.219, 2026-07-24) | **Opus 5 = 기본 Opus 모델**, `/fast` 대상 = Opus 5 + 4.8. **nested subagent depth 1→3** (`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1`로 비활성). 동시 스폰 캡 **20**(`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, v2.1.217 신설), `/clear`로 리셋. dynamic workflow 기본 **medium(<15 agents)**. |
| /changelog (v2.1.198~218) | subagent **기본 백그라운드** 실행(`/fork`=새 백그라운드 세션, `/subtask`=기존 in-session). permission 기본 `default`→**`manual`**(v2.1.200). **`/verify`·`/code-review` 자동 실행 중단**(v2.1.215, 수동 호출) — 모델측 over-verification(§1.2)에 대한 **하네스측 대응**. 트랜스크립트에 assistant 메시지별 **reasoning effort 기록**(v2.1.212). |
| /changelog (v2.1.220~226, 2026-08-08) | **세션 생애 200 스폰 캡 제거**(v2.1.224) — *"Removed the 200-subagent-per-session spawn cap … **concurrency and depth limits still apply**"*. 동시 20·depth 3은 유지. **ultraplan 기능 제거**(v2.1.222). workflow 스크립트의 dynamic `import()` 샌드박스 탈출 픽스(v2.1.223). `/review`→`/code-review` 별칭 + 레벨 기억(v2.1.223). worktree 격리를 **파일 편집·Bash 전 세션 타입**에 적용(v2.1.222). `claude-api` 스킬에 `prompt-audit` 신설 — *"patterns written for older models"* 감사(v2.1.221). |

### 1.1b Claude Code 운용 — fz 의존 기능 (verified 2026-08-08)

> 신설 정당화 (DELETE/MERGE-default): **순수 additive가 아니라 산재 인용의 통합**이다. `/model-config`은 이미 `fable-model-guide.md`·`skill-testing.md:422`·`harness-engineering.md` §참고 문헌·`CHANGELOG` 등 **12개 지점에서 1차 출처로 인용**되는데 색인 행이 없어 참조점이 분산돼 있었다. 나머지 6개도 fz가 실행 경로에서 의존하는 기능인데 근거 행이 0이었다. ⛔ 후속: `harness-engineering.md` §참고 문헌 참고문헌 행을 본 표로 리다이렉트 (별건).

| 페이지 | 핵심 (verified 2026-08-08) |
|--------|---------------------------|
| /model-config | ⛔ **`CLAUDE_CODE_SUBAGENT_MODEL`은 subagent·agent team·workflow agent 전부에 적용되고, per-invocation `model` 파라미터와 subagent frontmatter `model`을 override한다** — `inherit`로 정상 해석 복귀. **fz §12의 "model 명시 의무"를 무력화할 수 있는 유일한 변수** → 진단 시 1순위 확인. `opusplan`=plan mode는 opus, 실행은 sonnet. `availableModels` 제한 시 family alias는 **허용된 최신 버전으로 치환**되고 요청·치환 모델을 명시한 notice가 뜬다(v2.1.205+). |
| /workflows (v2.1.154+) | 워크플로는 **subagent를 오케스트레이션하는 JS 스크립트**다. ⛔ **resume 재생 규칙**: *"Cached results stop at the first agent that didn't finish, and **every agent that started after that one runs again, even if it completed**"* → *"**다수의 작은 에이전트가 하나의 큰 에이전트보다 진행을 더 보존한다**"* (fz의 소수-큰-에이전트+배리어 구조와 **반대 방향** — 설계 재검토 입력). resume은 **동일 세션 내에서만**(CC 종료 시 다음 세션은 처음부터). size guideline `unrestricted`/`small(<5)`/`medium(<15)`/`large(<50)`, 기본 medium — **advice이지 cap 아님**. Large workflow 경고 = 25 agents 초과 또는 예상 1.5M 토큰(v2.1.203+, **advisory·중단 안 함**). ⛔ **워크플로 서브에이전트는 세션 permission mode와 무관하게 `acceptEdits`로 실행되고 파일 편집이 자동 승인**된다. 런타임 캡: 동시 ≤16(코어 적으면 감소)·총 1000·`import()` 포함 스크립트는 시작 전 실패. |
| /worktrees | `--worktree`/`-w` → `.claude/worktrees/<name>/`, 브랜치 `worktree-<name>`. `worktree.baseRef`=`fresh`(기본, remote 기본 브랜치)/`head`(로컬 HEAD) — ⛔ **브랜치명 지정 불가**. `.worktreeinclude`는 **gitignored 파일만** 복사(추적 파일 미복제), ⛔ `WorktreeCreate` 훅 사용 시 **미처리**. **격리 3중 체크**(파일 편집·명령 cwd·**git 리다이렉트** `git -C`/`--git-dir`/`GIT_DIR`/`cd` 후 git)가 **세션이 스폰한 모든 subagent에 동일 적용**. `isolation: worktree` frontmatter → subagent 전용 워크트리(base는 `--worktree`와 동일). ⭐ **메인과 공유 3종**: `.git` · **project scope 플러그인**(v2.1.200+) · **permission 승인**(v2.1.211+ — worktree의 "don't ask again"이 메인 `.claude/settings.local.json`에 저장). ⛔ `.claude`·`worktrees`·대상이 **symlink면 생성 거부**(v2.1.212+). cleanup: `--worktree` 생성분은 **자동 제거 안 함**, subagent 워크트리만 `cleanupPeriodDays` sweep. |
| /plugins-reference | `plugin.json`은 `.claude-plugin/`에, 나머지 디렉토리(`commands/`·`agents/`·`skills/`·`workflows/`)는 **플러그인 루트**에 둔다. 매니페스트 포함 시 **`name`만 필수**이고 이 `name`이 **네임스페이스를 결정**한다(fz의 `fz:` agentType prefix 근거). ⛔ 경로 필드(`commands`·`agents`·`workflows`·`outputStyles`)는 **기본 디렉토리를 대체**한다 — 명시하면 기본 `workflows/`는 **스캔되지 않는다**. 유지하려면 명시적으로 함께 나열. 설치 스코프: user(기본)/project(팀 공유). |
| /settings | precedence **Managed > CLI > Local > Project > User**. `advisorModel`=`"opus"`/`"sonnet"`/full ID, **unset이 비활성화**, ⛔ `"fable"` 저장 시 *"attaches no advisor and **raises no error**"*. `effortLevel`=`low`/`medium`/`high`/`xhigh` — `--effort`·`CLAUDE_CODE_EFFORT_LEVEL`이 1세션 override. `disableWorkflows`(기본 false) · `cleanupPeriodDays`(기본 30일·최소 1, worktree sweep 주기와 공유). |
| /env-vars | ⛔⭐ **"설정 여부만 읽는" 변수군이 있다** — *"any non-empty value **including `0`** turns the behavior on, and you turn the behavior off by **unsetting** the variable or setting it to an **empty** value."* 해당 확인: `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`·`DISABLE_TELEMETRY`. **`=0`은 끄는 값이 아니다** → 실험 게이트를 `0`으로 껐다고 믿는 설정은 전부 재검증 대상. `CLAUDE_CODE_EFFORT_LEVEL`=*"overrides `/effort`"*. ⚠️ **이 페이지 미등재 실측**: `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`·`MAX_SUBAGENT_SPAWN_DEPTH`·`MAX_SUBAGENTS_PER_SESSION`·`CLAUDE_CODE_SUBAGENT_MODEL` — 출처는 각각 /changelog·/model-config. |
| /commands | `/batch`=**번들 스킬**. 5~30 독립 유닛 분해 → **유닛당 background subagent 1개 × 격리 worktree** → 각자 테스트 후 **PR 개설**. git 저장소 필요. ⚠️ **별도 세션이 아니라 subagent**이므로 세션 내 통신 대상이다. `/code-review`=번들 스킬(`--fix`/`--comment`/`ultra`, 레벨 미지정 시 **마지막 입력 레벨 재사용**, 로컬은 백그라운드 subagent, `/review`가 별칭). `/deep-research`=**번들 워크플로**. ⚠️ `/simplify`는 이 표에 **없다** — v2.1.154부터 **cleanup-only**이고 버그 헌팅은 `/code-review --fix`로 분리됐다 [출처: /code-review]. |

### 1.2 모델 프롬프팅 (Opus 5 — platform.claude.com/docs/en)

> ⚠️ **모델별 프롬프팅이 1급 문서로 승격됐다.** `prompt-engineering/prompting-claude-{fable-5|sonnet-5|opus-5|opus-4-8}` 가 각각 독립 페이지. "프롬프트 한 벌을 전 모델 재사용"은 더 이상 기본 가정이 아니며, **방향이 반대로 뒤집히는 항목이 실재**한다(subagent 위임 — 아래). 세대 간 프롬프트 복사 전 해당 모델 페이지 확인.

| 페이지 | 핵심 (verified 2026-07-25) |
|--------|---------------------------|
| about-claude/models/whats-new-opus-5 | `claude-opus-5`(2026-07-24). **$5/$25 = 4.8과 동일** · 1M ctx(기본=최대) · 128k out. **Breaking 2**: ① **thinking 기본 ON** (4.8은 미설정 시 OFF) — `max_tokens`는 **thinking+응답 합산** 하드캡이라 4.8 기준으로 타이트하게 잡은 경로는 **응답 절단** 위험 ② **`thinking:{"type":"disabled"}`는 effort ≤ `high`에서만**, `xhigh`/`max`와 조합 시 **400**(요청 단위 검증). 신규: mid-conversation tool changes(캐시 보존, `mid-conversation-tool-changes-2026-07-01`) · `fallbacks:"default"` · 프롬프트 캐시 최소 **512**(4.8=1024) · fast mode $10/$50 **Claude API 전용**. |
| prompt-engineering/prompting-claude-opus-5 | **① 검증 지시를 삭제하라** — 자체검증 내장. *"removing them reduces wasted tokens **with no loss in quality**"*. ② **subagent 위임에 캡** — 4.8의 "더 위임하게 유도" 권고와 **역방향**. ③ 응답·산출물 **장문화** → **프롬프트로 길이 통제**(effort로는 안 됨). ④ 스코프 확장·자기정정 서술 과다 → 명시 제약. ⑤ thinking OFF 시 **tool call이 평문으로 새어 에러 없이 미실행** + `<thinking>` 태그 누출 → **thinking ON + `low` effort**가 "thinking OFF at similar cost"보다 우수. |
| build-with-claude/effort | 출발점 **`high`(기본)**, **`low`/`medium`을 primary control**로 사용. demanding coding/agentic만 `xhigh`, 무제한 지출 정당화 시 `max`. ⛔ *"If you carried effort settings over from an earlier model, **run a fresh effort sweep** on your evals rather than reusing them."* `xhigh`/`max` 시 `max_tokens` 64k 출발. **effort 변경 = 프롬프트 캐시 무효화** → 캐시 의존 세션 내에서는 고정. |
| build-with-claude/thinking | adaptive만 유효 (`budget_tokens`는 400). `display` 기본 **`"omitted"`** — 요약 필요 시 `"summarized"` 명시. |
| prompt-engineering/claude-prompting-best-practices | 전 모델 공통(명료성·예시·XML 구조화·thinking·agentic) + **모델별 페이지 분기**. be explicit / parallel tool calls(`<use_parallel_tool_calls>`) / **공식 anti-overengineering·anti-hallucination 프롬프트**(§4). |
| structured-outputs | JSON schema 강제 출력 (prefill 대체 경로 — prefill은 4.6+ **400**). |

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
- linas.substack "Opus 4.8 Prompting Playbook" — 프롬프팅 실무. ⚠️ Opus 4.8 기준 — subagent 위임·검증 지시 항목은 Opus 5에서 **역방향**이므로 그대로 적용 금지(§1.2 O6 우선).

---

## 4. 핵심 원칙 (verified 종합) — fz 설계 정합

> 약어: O1 /memory · O2 /best-practices · O3 /hooks · O4 /sub-agents · O5 /skills · O6 **prompting-opus-5** · O7 **claude-prompting-best-practices** · O8 thinking · O9 **effort** · O10 **/changelog** · **O11 /model-config · O12 /workflows · O13 /worktrees · O14 /plugins-reference · O15 /settings · O16 /env-vars · O17 /commands** (모두 §1 Tier 1) · P1 2502.08235 · P2 2504.20799 · P3 2507.19457 · P4 2508.11126 (§2 Tier 2).
1. **하네스 레벨 결정론적 강제**: 신뢰성 필수 동작은 advisory memory가 아니라 hooks. [Tier1 §1.1]
2. **verifier + adversarial review**: pass/fail oracle로 루프 종료 + 구현자≠채점자(fresh model 반박). [Tier1 §1.1 + P2]
   - ⚠️ **Opus 5 경계선 — 혼동 금지**: 이 원칙이 말하는 건 *하네스가 실행하는 외부 verifier*(빌드/테스트 oracle)와 *다른 관점의 교차검증*(구현자≠채점자)이다. 반면 **모델에게 "스스로 검증하라"고 지시하는 프롬프트**는 Opus 5에서 over-verification을 유발하므로 §5 제거 대상. **원칙은 유지, 자기재확인 지시만 제거.** [O6]
3. **context 절약 + 적정 reasoning**: subagent 격리; CLAUDE.md prune; overthinking은 단조 이득 아님. [Tier1 + P1]
   - Opus 5 보강: `low`/`medium` effort가 "a fraction of the tokens and latency"로 강한 품질 유지 → P1(overthinking 위험)과 공식 권장이 **같은 방향으로 수렴**. [O9 + P1]
4. **공식 anti-패턴 프롬프트** (fz Surgical Changes/Verification Discipline 정합):
   - anti-overengineering: "Only make changes directly requested or clearly necessary… A bug fix doesn't need surrounding code cleaned up." [O7]
   - anti-hallucination: "Never speculate about code you have not opened… MUST read the file before answering." [O7]
   - subagent 과용 경계: 단일파일·순차 작업은 직접, 병렬·격리·독립 워크스트림에만 위임. [O7] — **Opus 5에서 중요도 상승**: 모델이 위임을 과다 시도하므로 하네스측 캡(O10: **동시 20·depth 3** — 세션 생애 200 캡은 v2.1.224에서 제거됨)과 프롬프트측 제약(O6)을 **함께** 건다.

## 5. 구버전 제거 정책 (Opus 5 only)
fz는 항상 최신 모델(현재 **Opus 5**, `claude-opus-5`, 2026-07-24)만 타깃. 다음은 **수록·권장하지 않는다**:

**API 레벨 (400 에러)**
- manual `budget_tokens` extended thinking — Opus 4.7+/5/Fable 5/Mythos 5에서 **400**. → adaptive thinking + effort + max_tokens.
- prefilled responses (마지막 assistant turn) — **Claude 4.6+ 미지원**. → structured outputs / user turn 주입.
- sampling 파라미터 `temperature`/`top_p`/`top_k` — **Opus 4.7+/5에서 400**. → 프롬프팅으로 대체.
- `interleaved-thinking-2025-05-14` beta header — **4.6+ deprecated·ignored**.
- **[신설] `thinking:{"type":"disabled"}` + effort `xhigh`/`max`** — Opus 5에서 **400**. thinking을 끄려면 effort를 `high` 이하로.

**프롬프트 레벨 (에러는 아니나 역효과)**
- over-prompting / anti-laziness ("If in doubt, use [tool]") — 최신 모델서 overtrigger 유발 → dial back.
- **[신설] 검증 지시** — "include a final verification step" / "use a subagent to verify" / "double-check your answer" / "re-verify before responding". Opus 5는 자체검증 내장이라 **over-verification**이 된다. 공식: 제거해도 *"with no loss in quality"*. ⚠️ **§4-2의 verifier 원칙(외부 oracle·교차검증)은 유지** — 자기재확인 지시만 제거. [O6]
- **[신설] "생각하지 마라 / 추론하지 마라" 류 규칙** — thinking OFF 상태에서 `<thinking>` 태그 누출을 오히려 **증가**시킨다. 태그를 이름으로 지목하는 것도 일반형(`Do not include internal or system XML tags`)보다 **비효과적**. [O6]
- **[신설] carried-over effort 값** — 이전 모델 기준으로 정한 effort를 그대로 옮기지 말 것. 공식이 **fresh sweep**을 요구(§1.2 O9). 상수 교체가 아니라 **측정**이 답.
- **[신설] "응답을 줄이려고 effort를 낮추는" 패턴** — Opus 5에서 effort는 **사고량**을 조절할 뿐 **가시 응답 길이를 신뢰성 있게 줄이지 못한다**. 길이는 프롬프트로. [O9]

**제거된 기능 (사용 중이면 즉시 깨짐)**
- **Opus 4.7 fast mode** — 2026-07-24자로 삭제. `speed:"fast"` 요청은 **에러 반환** (4.6식 조용한 폴백 아님).

## 6. fz 가이드 적용 매핑
| 가이드 | 관련 §·출처 |
|--------|------------|
| harness-engineering | §4(원칙) · O1·O2·O3 · P1 |
| prompt-optimization | §5(구버전) · §4(anti-패턴) · P2·P3 |
| agent-team-guide | MAST(2503.13657) · O4 · P4 |
| skill-authoring · skill-troubleshooting | O5 · O4 · O3 · **O12(§12 Workflow 규약) · O14(`fz:` 네임스페이스)** |
| skill-testing | §4-2(verifier) · O2·O6 · **O11·O15·O16(effort 우선순위 arm 검증)** |
| **fable-model-guide** | **O11**(모델 별칭·치환) · O9 |
| **governance / execution-modes** | **O12**(워크플로 캡·acceptEdits 강제) · **O13**(worktree 격리) · **O17**(`/batch`·`/simplify` 실체) |
