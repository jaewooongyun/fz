# Changelog

## Retired Citation Policy

릴리즈마다 인용 논문이 rotate되면 추적 신뢰도가 떨어진다. 다음 정책을 적용한다:

- **Active citations**: 현행 modules/skills/agents에서 직접 인용되는 논문 (예: NLAH 2603.25723, X-MAS 2505.16997, Drift No More 2510.07777, VeriGuard 2510.05156, MAR 2512.20845, Intelligence Degradation 2601.15300, Context Length Hurts 2510.05381, OpenDev 2603.05344)
- **Retired citations** (RELEASE_NOTES만 보존): 과거 릴리즈에서 인용했으나 현행 modules에서 인용 없음 — ICLR MAD (2502.08788, v3.0 release), MAST (2503.13657, v3.0 release)
- **정책**: retired citations는 RELEASE_NOTES에 historical reference로 보존 + CHANGELOG에 정리 사유 명시. 신규 modules에 재인용 시 active로 환원.

### v4.5.1 (2026-04-26) — docs fix: remove local work dir references [PATCH]

**핵심**: v4.5.0 README/CHANGELOG에서 plugin 사용자에게 의미 없는 local work directory 참조를 제거 — privacy(절대 경로 username 노출) + clean reference 동시 해결.

**변경**:
- `CHANGELOG.md` v4.5.0 entry — local user-specific 절대 경로 + `~/dev/...` 작업 폴더 참조 제거
- `README.md` v4.5 섹션 — local 작업 폴더 참조 제거
- `skills/fz-codex/SKILL.md` — working dir 예시(L136-140) + trust_level config 예시(L184-191)에서 user-specific 절대 경로 → `~/dev/{project}/...` 또는 placeholder로 일반화
- GitHub Release v4.5.0 notes 정정 (post-release edit)

**영향**: 동작 변경 없음. plugin install 사용자가 README에서 broken reference 못 보게 됨.

**메타 교훈**: pre-commit grep으로 `/Users/{user}/`, `~/dev/{user}/` 절대 경로 차단 검증 추가 후보 (CLAUDE.md `## Git Workflow` 또는 `modules/cross-validation.md`).

---

### v4.5.0 (2026-04-26) — Swift/iOS Quality Framework (3-Layer Evidence) [MINOR]

**핵심**: Plan/Code/Review 각 단계에서 Claude + Codex가 **evidence-based clear Swift/iOS coding**을 수행하도록 fz framework에 3-Layer Evidence 정합 통합. 사용자 redirect ("plan/code/review 시 Swift/iOS/구조 품질 안좋음 + 둘 다 근거 기반 명확한 코딩")의 직접 답.

**발견 경로**:
- 8단계 cross-model verify cycle (Claude + Codex GPT-5.5)
- 1차 분석: B+ → 2차 reframe → Sprint Contract (Codex) → Plan v1 → v2 → v2.1 → v2.2 → Round 5 verify
- 5-round 누적 Codex unique 16건 + Claude deep-review unique 5건 → 23차 메타 패턴 ("Cross-model 마지막 안전망") 5번 입증

**P0/P1 — 13 SC 적용 (3-Layer × Meta)**:

Layer 1 PLAN:
- `agents/plan-structure.md` Swift/iOS Domain Awareness 신설 — plugin-refs.md + swift-anti-pattern-preblock.md + Domain Tier 직접 참조
- `skills/fz-plan/SKILL.md` Phase 1.5 (Swift Anti-Pattern Pre-block) 신설 — Gate + module reference / iOS 16 minimum target 명시
- `codex-skills/fz-planner/SKILL.md` SwiftUI Planning Checklist + Swift Concurrency Planning Checklist + Sendable Boundary Planning 3 anchor 강화

Layer 2 CODE:
- `agents/impl-quality.md` tools에 mcp__context7 등록 (dead reference fix)
- `codex-skills/fz-fixer/SKILL.md` SwiftUI Repair Patterns + Concurrency Repair Patterns + Anti-Repair Patterns 3 anchor 추가
- `skills/fz-code/SKILL.md` Phase 0.5 (Swift Pattern Pre-detection) 신설 — Gate + module reference

Layer 3 REVIEW:
- `skills/fz-fix/SKILL.md` supporting [review-arch] → [review-arch, impl-quality, review-quality] + 역방향 트리거 가이드 (3 absence-pattern)
- `skills/fz-review/SKILL.md` iOS 16 minimum target 검증 의무 명시
- `skills/fz-codex/SKILL.md` `/fz-codex drift` 라우팅 버그 수정 (`drift-detector` → `drift`, L518 + L75 doc table)

Meta — Evidence Framework:
- `modules/uncertainty-verification.md` **Swift/iOS Domain Tier** 신설 — 7개 주장 유형 × Heavy/Light × Mandatory Sources. Heavy 정책 **additive (non-overriding)** 명시
- `experiment-log.md` §5.6 **Plugin Trigger Activation** + Load-bearing Test 절차 신설 — 원칙별 ablation schema

**신규 modules (2개)**:
- `modules/swift-anti-pattern-preblock.md` — 3 원칙 (P1 SwiftUI 결정 / P2 Concurrency isolation / P3 패턴 변환 보존) + token + Few-shot
- `modules/swift-pattern-detection.md` — 4 원칙 (D SwiftUI / E Concurrency / F 위험 패턴 / G 패턴 변환) + Phase 1.5 P3 ↔ G mirror

**fz Guide 정합 (deep review 적용)**:
- `prompt-optimization.md` 원칙 4a (원칙+이유 > if-then 테이블) 적용 — 9 if-then inventory → 7 원칙+이유 재작성
- `prompt-optimization.md` 원칙 5 (Few-shot ≥3) 적용 — 각 module BAD/GOOD 1쌍 이상
- `skill-authoring.md` "트리밍 비저하 원칙" 적용 — Gate 1.5/0.5 보존 + 본문 module 분리
- `harness-engineering.md` H1 (가정 검증) 대응 — F9 Load-bearing Test 절차 신설

**Cross-Validation 5-cycle**:
- Round 1 (analysis): Codex unique 3 (drift routing 등)
- Round 2 (verify v2): Codex unique 4 (SC-L2-1 broken 등)
- Round 3 (verify v2.1): Codex unique 2 (markdown escape 등)
- Round 4 (deep review): Codex unique 5 (575줄, SC-L1-1 등) + Claude unique 5 (fz guide deep)
- Round 5 (final verify): Codex unique 2 (untracked, 12→13 mismatch) — **Reflection Rate 90% (strict) / 95% (lenient)**

**Verification**:
- 13 SC PASS (12 verifiable + 1 partial)
- 6 AC PASS
- Plugin validate ✔ Passed
- 23차 메타 패턴 5-round 모두 입증

---

### v4.4.0 (2026-04-26) — Mapping Layer SPOF Defense [MINOR]

**핵심**: peer review 시스템에 **Mapping Layer Single-Point-of-Failure 방어** 도입. 6-Layer LLM 검증이 같은 evidence 매핑 base를 공유하면 매핑 오류는 layer 수와 무관하게 통과한다는 구조적 결함 발견 → atom-level decomposition + fail-closed pre-trigger + cross-stage severity 정렬로 차단.

**발견 경로** (외부 사례 `[미검증: 사용자 제공]`):
- TVING/app-iOS PR #3796 (ASD-1136 ReachabilityManager → NetworkMonitor) peer review에서 6-Layer 검증 (boolean equivalence + Opus + Sonnet + Codex + Lead self + Devil's Advocate) 통과 후 CodeRabbit (rule-based) 단독 발견
- Root cause: `ReachabilityManager.isReachableViaWWAN() = (Reachable AND IsWWAN)` 이중 게이트인데, evidence 매핑이 `→ isReachableViaCellular` simplify되어 reachable atom 누락
- 검증 신뢰도 = `min(매핑 정확성, layer 정확성)` — multiplicative 아님, layer N배 늘려도 매핑이 SPOF면 신뢰도 cap

**P0 — 7 docs (신규 신설 0)**:
- `modules/evidence-collection.md` **a2. Semantic Mapping Ground Truth** 절차 신설 — atom-level mapping table + `[verified: source]` 의무 + `mapping_status` 분류 (verified/lossy/over-mapped/unverified)
- `modules/peer-review-gates.md` **Gate 4.4-A Mapping Fidelity Gate** + **fail-closed Pre-Trigger** — refactoring PR + `semantic-mapping.md` 부재 → Critical 자동 / `mapping_status=lossy` → auto-include
- `modules/uncertainty-verification.md` **Default-Deny mapping claim** 좁은 확장 — `"A는 B와 동일"`, `"X가 Y로 대체됨"` 등 mapping/equivalence claim에 한정 (전역 확대 X)
- `skills/fz-peer-review/SKILL.md` 4 위치 — Gather evidence table + Fact + Mapping Verification Gate + Brief Template + **Task Brief L260에 `evidence/*.md` 명시** (governance 500줄 정확 도달)
- `agents/review-quality.md:60-64` Source Fidelity에 mapping atom 검증 (severity: critical, Gate 4.4-A 정렬)
- `skills/code-auditor/SKILL.md:242-263` Refactoring Completeness 보강 — `lossy_atoms` 회귀 검증
- `codex-skills/fz-challenger/SKILL.md` **Mapping Assumption Challenge** — Codex DA가 lossy/unverified row를 별도 challenge 대상으로

**Layer Diversity 통합 해결**:
- "더 많은 LLM 추가 ≠ Layer Diversity" 통찰 — 같은 매핑 base를 받으면 동일 결론 수렴
- 진짜 Layer Diversity = deterministic source (`git show / Read / grep`) + LLM 판단의 조합 — fz `cross-data` 원칙과 정합

**Cross-Validation 7-cycle 정당성 입증** (본 plan 작성 자체가 prototype):
- Cycle 1: PR review (CodeRabbit 단독 발견) → 출발점
- Cycle 2: Plan v1 (Codex independent가 verify 위반 catch)
- Cycle 3: Plan v2 통합 (Claude self-review가 Q1 self-violation catch)
- Cycle 4: Plan v2 verify (Codex가 v4.1.0 stale 메모리 + `[verified]` 위반 + line citation 잘못 catch — 5건 단독 발견)
- Cycle 5: Plan v3 정정
- Cycle 6: v4.4.0 적용 (모든 Step 실행)
- Cycle 7: v4.4.0 review (Codex가 internal instruction conflict 단독 발견 P2/P3 → 즉시 fix)

**메모리 정식화** (사용자 메모리):
- `feedback_mapping_layer_spof.md` (신규) — 6-Layer 검증 SPOF 패턴 + Defense + How to apply
- `MEMORY.md` index entry 추가 — Verification Discipline 섹션

**메타 학습 — Internal Instruction Conflict는 새 종류 결함**:
- self-review (grep 기반 mechanical check) → Anti-Pattern 0 violations
- Codex review (semantic consistency 분석) → P2 (a2 trigger 정밀도) + P3 (lossy severity 불일치) 단독 발견
- 두 패러다임이 만나는 지점에서 새 결함 분류 발견 — multi-module 변경에서 같은 개념(`lossy mapping`)이 module 간 drift

**Verification**:
- `claude plugin validate .` — ✓ Validation passed
- `wc -l skills/fz-peer-review/SKILL.md` — 500 lines 정확 (governance ≤500 준수)
- 변경량: 10 files (+115/-13 lines)

### v4.3.0 (2026-04-25) — fz GPT/Codex Tier 1+2 완성 [MINOR]

**핵심**: fz GPT/Codex 고도화 프로젝트 사실상 완료. Tier 1 7/7 + Tier 2 1/1. T2-A (β-1 Gemini) 폐기 — cross-provider 비채택. α-2 BLOCKER 해소. 31차/32차/33차 메타 교훈 active defense 정식화.

**Tier 1 7/7** (본 릴리즈에 5건 추가):
- **T1-D fz-fix Codex 통합** (c4c994b, fe2ee8a, cfcaf91): `--codex` 옵션 위임 패턴 + verdict contract (pass/warn/fail) + grep severity 정정
- **T1-B Tracing 자동화** (4519f7a): experiment-log §5.5 schema + Agent Teams Hook (~/.claude/hooks.json + agent-teams.sh)
- **δ-2 Effort Routing** (9150621): Codex 서브커맨드별 effort 매핑 (medium/high/xhigh)
- **T1-E 이론 근거 보강** (058537e): cross-validation.md "Heterogeneity + Blind-spot Complementarity" 프레임 (4 메커니즘 + 학술 근거)
- **η-1 Prompt Independence Gate** (75c051b): TEAM Round 1 sycophancy 절차적 강제 + Gate 1.0

**Tier 2 1/1**:
- **T2-B Sprint Contract** (33d1363): modules/sprint-contract.md + fz-plan Phase 0.7 (Codex가 구현 전 SC 작성)

**T2-A 폐기 + stale 정정** (8f4e7ae):
- β-1 Gemini 통합 비채택 결정 — cross-provider stake 자체 미채택
- guides/harness-engineering.md L663/L1008 stale "3-Model Triad" 참조 정정

**메타 교훈 active defense 정식화**:
- **31차 Plan-before-Probe** (c4c994b): fz-plan Phase 0c + fz-discover Phase 1.5 (Constraint Probe Pre-flight)
- **32차 Probe Coverage Gap**: 3-axes sub-checklist (존재 / 권한·경계 / 결과 contract)
- **33차 Recommendation Default Bias** (5fdc4bf): modules/fz-pipeline-proposal.md 권고 default 정책 (Implementation default + v{N+1} 자동 작성 차단)

**Reflection Rate 측정 시작** (6fd93b7):
- experiment-log §5.5에 3 entries (T1-D verify v1/v2/self-dogfood)
- Sample 3/5 (CP-3 5건+ 누적 필요), Strict 73% / Lenient 86%
- 32차 dogfooding 1차 효과: patch 2건 사전 회피

**Health-Plan v2 통합 + Codex-Utilization v1** (69c78a9, 본 릴리즈에 추가):

*Health-Plan v2 (P0 — 31/32/33 consolidation, behavior-change-first)*:
- `modules/lead-action-default.md` 신규 (23 lines thin reference) — Lead default = action with proportional verification 단일 원칙
- `modules/lesson-intake.md` 신규 (16 lines decision tree) — 미래 lesson family 분기 (same mode merge / new mode separate)
- `modules/cross-validation.md`: Reflection Rate threshold authoritative source (N<10 preliminary / 10≤N<30 provisional / N≥30 stable)
- 5 backlinks (history-preserving, no rewrite): experiment-log, fz-review, feedback-verification, sprint-contract, execution-modes
- Hot-path "default = action" inline edit (3 files): fz-plan Phase 0.5 / fz-review Phase 5.5 / fz-pipeline-proposal

*Codex-Utilization v1 (P0 — friction reduction + T2-B first dogfooding)*:
- `skills/fz-codex/SKILL.md`: Standard Hygiene Wrapper Template (### 6) — 5 hygiene rules + zsh glob 회피 + output readback + heredoc 권고
- `modules/codex-strategy.md`: adversarial high→xhigh 정합화 + Light tier (cross-reference inconsistency 해소)
- `skills/fz-plan/SKILL.md` Phase 0c: Codex Micro-Eval optional assist (조건: 핵심 가정 + [verified] 부재 + primitive 비용 높음)
- `experiment-log.md §5.4`: Codex Unique Findings tracking schema (cross-model 가치 정량 evidence 누적)

*Cross-model verification 결과*:
- Health-plan v2 (Codex GPT-5.5): APPROVED_WITH_NOTES — Codex unique 4건 (Q1/Q2/Q5/Q6 critical, Claude self-review blind spots)
- Codex-utilization v1: APPROVED_WITH_NOTES — Codex unique 1건 (codex-strategy.md adversarial 충돌 line-level factual catch)
- **T2-B Sprint Contract pattern 첫 dogfooding 실증** — Codex pre-commit SC → Lead plan v1 → Codex verify → 1 round 압축 (vs 일반 cross-model 2-3 cycles)
- Reflection Rate N=6 (preliminary, gating 보류 — self-rule applied)

### v4.2.0 (2026-04-24) — Scope Challenge + fz Guide Compliance [MINOR]

**핵심**: 두 축 결합. (A) ASD-1136 Scope Challenge — fz-plan Phase 3에서 Codex verify 이슈를 `scope_disposition`으로 분류, "발견된 것 = 고쳐야 할 것" 자동 번역 차단. Read/Write Scope 분리 + `§X/§Y/§Z` handoff 계약. (B) `/fz-manage` 전체 리뷰로 도출된 5개 가이드 위반(500줄 초과 2건 + 과격 표현 1건 + Few-shot 부족 3건 + YAML 컨벤션 불일치 2건)을 4-Wave로 해소. 21/21 스킬이 skill-authoring.md + prompt-optimization.md + skill-template.md 전 축을 준수.

**Feature Set A — Scope Challenge (ASD-1136)**:
- `modules/scope-challenge.md` 신규 (117줄): Q-S1~S4 체크포인트 + Lead 독립 분류(Generator≠Evaluator) + 5개 disposition 매핑(scope-in/out/invariant-risk/parent-reopen/improvement) + Thought-terminator 감지 + Q-S5 Appendix (Decision Re-open Gate).
- `modules/promotion-ledger.md` 신규 (69줄): P1/P2 eligible session 관측 ledger (학습 승격 금지 원칙, 2회 관측 후 P0).
- `agents/plan-impact.md`: 출력을 Read Scope(넓게 탐색) + Write Scope(binary 판정 최소) + Acceptance Criteria 3-섹션으로 분리. write-in 3조건 명시.
- `agents/plan-structure.md`: plan-final.md §X/§Y/§Z handoff 계약. fz-code는 §Y+§Z, fz-review는 §Y.
- `schemas/codex_review_schema.json` + `codex_peer_review_schema.json`: `schemaVersion` v1.1 required + `issues[].scope_disposition` nullable (v1.0 backward-compat).
- `skills/fz-plan/SKILL.md`: intent-triggers refactor 패턴 추가 + Phase 3 §1b Q-S1~S4 의무화 + Phase 3 §5 Refactoring Mode AskUserQuestion.
- `skills/fz-review/SKILL.md`: Phase 4.5에 §Y Write Scope 정의 시 diff ⊆ §Y 검증 필수.
- `skills/fz-codex/SKILL.md`: response schemaVersion version-aware 파싱 (v1.1이면 disposition read, 미존재/v1.0이면 Lead 수동).

**Feature Set B — fz Guide Compliance Audit**:
- YAML 통일: `arch-critic`/`code-auditor`의 `mcp-servers: []` → `allowed-tools: []` (fz-new-file 선례, 21/21 스킬 일관). 권한 변경 없음 — 실제 도구는 agents/review-arch.md/review-quality.md가 선언.
- 과격 표현 완화: `skills/fz-search/SKILL.md:371` `**CRITICAL**: 코드 수정 절대 금지` → `**Read-Only**: 이 스킬은 코드를 수정하지 않습니다` (Opus 4.7 literal interpretation 대응, Will Not 섹션이 이미 동일 제약).
- 500줄 준수: `skills/fz-review/SKILL.md` 508→487 (Phase 5.5 → `modules/feedback-verification.md` 48줄 신규), `skills/fz/SKILL.md` 515→463 (Phase 4 시각화+AskUserQuestion+적극적 확인 원칙 → `modules/fz-pipeline-proposal.md` 74줄 신규). Gate 4는 SKILL.md에 유지(트리밍 비저하 원칙). 두 신규 모듈 상단에 "Scope of Applicability" 명시.
- Few-shot ≥3쌍: `code-auditor`(Convention/Dead code/레이어 위반), `fz-codex`(review/verify/validate), `fz-review`(리뷰 보고/Anti-Pattern 잔존/Source Fidelity). 본문 실제 시나리오 기반(원본 미존재 추가 금지 원칙).
- `docs/design/lessons-to-module-pipeline.md` 신규 (195줄, 설계만): 17차+18차 교훈 도구화 경로 `/fz-manage reflect-to-module` 서브커맨드 설계. 4개 컴포넌트(Memory Parser + Relevance Scorer + Suggestion Generator + Scope Inflation Detector). **⛔ 구현 승인 전 실행 금지** — 본 설계 자체가 Scope Inflation 위험 내포. 경로 하드코딩 금지(`${PLUGIN_ROOT}`, `${CLAUDE_PROJECT_MEMORY}` 변수화 + CLI 인자).

**Codex Cross-Validation (fz Guide Compliance 검증 중, 3회 수렴)**:
- [P2] `modules/feedback-verification.md:19` Reflection Rate 공식이 canonical schema와 divergence → 스키마 정렬 수정 (fz-code "원본 미존재 추가" 마찰 신호 재발 사례).
- [P2] `docs/design/lessons-to-module-pipeline.md:48-52` 하드코딩 경로 → 변수화 + CLI 인자화 (마켓플레이스 배포 이식성).

두 이슈 모두 Claude 단독 리뷰 blind spot. 18차 교훈 "Codex 3회 한도" 내 수렴.

**변경 파일** (+610/-99):
- Feature Set A: 9 파일 (agents 2 + modules 3 + schemas 2 + skills 3)
- Feature Set B: 9 파일 (skills 6 + modules 2 + docs 1)

**마이그레이션**: 없음 (backward-compatible). Schema v1.1은 v1.0 응답 null 수용. YAML `allowed-tools: []`는 권한 불변.

**Plugin Metadata**:
- `.claude-plugin/plugin.json`: 4.1.0 → 4.2.0
- `.claude-plugin/marketplace.json`: 4.0.0 → 4.2.0 (v4.1.0 릴리즈 시 bump 누락 수정 포함)

---

### v4.1.0 (2026-04-21) — Call-Site Deprecation Audit + Function Responsibility Audit [MINOR]

**핵심**: ASD-1111 회귀 ("함수 이름 ≠ 함수 책임" + "호출 중단 ≠ 정의 제거" 패턴)를 fz 생태계로 반영. plan-impact의 Exhaustive Impact Scan을 `a~f` → `a~g`로 확장하고 review-correctness에 Function Responsibility Audit 절차 추가. v1~v4 needs_revision 반복 후 **18차 반성 (Scope Inflation 방어) 4 규칙** 등록 + v5.3 Codex approved 후 구현.

**신규 검증 절차**:
- `agents/plan-impact.md` §Exhaustive Impact Scan 항목 g "Call-Site Deprecation Audit" — 함수 호출자 수 변화 감지 + 책임 분해. severity: Critical `responsibility_gap` 플래그.
- `agents/review-correctness.md` §2 Logic Correctness "Function Responsibility Audit" bullet — Lead가 base ref resolve 후 artifact 전달. agent는 Bash 금지 (guides/agent-team-guide.md §1 준수). severity: Critical `missing_responsibility` 플래그. ⛔ `HEAD^` 하드코딩 금지 (merge-base 우선).
- `skills/fz-plan/SKILL.md` `Impact Scan (a~f)` → `(a~g)` 2곳 일관성 업데이트.

**18차 반성 적용 (Scope Inflation 방어)**:
- 규칙 1 (Complexity Drift): v4 complexity 19 → v5 7 축소
- 규칙 2 (Self-Assessment Blindness): `[verified: 리터럴 명령어 출력]` 태그 의무
- 규칙 3 (Additive-Only 금지): v5에서 v4의 13개 Step DEFERRED
- 규칙 4 (Codex 3회 한도): 4회째 needs_revision 후 사용자 에스컬레이션

**DEFERRED (v5 plan 명시)**:
Helper-A Baseline Resolution 모듈, Helper-B Codex Degraded Gate, Plan-to-Source Gate 4.5.5, Edge Case Enforcement 5 cases, `/fz-manage propagate-lessons`, Trigger Precedence, Origin-Behavior Fallacy, Atomic Rewrite, SKILL.md Module Split — 별도 ASD 티켓 처리.

**검증 이력**: v1~v4 Codex needs_revision (Major 4→5→3→4) → v5 Major 2 → v5.1 Major 1 → v5.2 Major 0 → v5.3 approved (Q1-Q8 전체 pass, Issues 0) → 구현 Codex check --deep (Major 0, P2 2건 DEFERRED 범위) → validate approved (Reflection Rate 100%).

**변경 파일** (+24/-3):
- `agents/plan-impact.md` (+13/-1)
- `agents/review-correctness.md` (+10)
- `skills/fz-plan/SKILL.md` (+2/-2)

**마이그레이션**: 없음 (backward-compatible).

**관련 분석 산출물** (외부 TVING/ASD-1111 폴더):
- `review/regression-root-cause-analysis.md` — 7 시스템 패턴 (git 실측 교정판)
- `analysis/fz-ecosystem-gap-analysis.md` — Gap 매트릭스
- `plan/fz-ecosystem-improvement-plan-v{1-5}.md` + `verify-result*.md` — 8회 Codex verify 이력

---

### v4.0.0 (2026-04-21) — V.D. 4-way Chain 아키텍처 + 생태계 정합성 [MAJOR]

**핵심**: v3.11.0의 Verification Discipline 초안을 **4-way Chain 아키텍처**로 구조화 + 생태계 전체 정합성 감사로 22 Gap 해소. 단순 기능 추가가 아닌 **생태계 아키텍처 전환**으로 메이저 bump.

**Breaking Changes**:
- **레이어 경계 정정**: `modules/team-core.md` + `guides/prompt-optimization.md` H4의 "Brain = Lead / Hands = Primary/Supporting" 1:1 매핑 테이블 **제거**. Brain/Hands는 infrastructure layer (Anthropic), Lead/Teammate는 application layer (fz) — 혼용 금지 경고 박스 추가.
- **agents/ 12개 파일 구조 변경**: 모든 에이전트 하단에 `## Verification` 섹션 자동 추가.
- **templates/ 자동 상속**: `agent-template.md` + `skill-template.md`에 `## Verification` 섹션 + skill-template의 `## If TeamCreate is used` 조건부 체크리스트. 신규 에이전트/스킬 생성 시 VD 규약 자동 상속 (재발 방지).
- **9 skills Prerequisites 필수**: TeamCreate 사용 skills (fz, fz-plan, fz-code, fz-discover, fz-fix, fz-review, fz-peer-review, fz-search, fz-pr-digest) 모두 `## Prerequisites` 섹션 필수 — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 전제조건 명시.

**V.D. 4-way Chain 아키텍처**:
- ① 기본 fail-closed: `uncertainty-verification.md` → fz-plan / fz-code (기존 유지)
- ② 보조 micro-eval: `fz-codex micro-eval` → needs_verification → Default-Deny 차단 (의미론적 결합 신설)
- ③ TEAM 주입: `system-reminders.md` → `team-core.md` → fz/SKILL.md Task Brief → agents (templates/ 상속)
- ④ 운영 피드백: Phase 4.5 측정 → `experiment-log.md §5.4` canonical sink → B1/B2 판정

**생태계 정합성 감사 (22 Gap 해소)**:
- Critical 5: G1(레이어 경계) / G2a(agents VD 주입 경로) / G2b(오케스트레이터 Task Brief) / G18(team-core↔system-reminders) / G22(템플릿 상속)
- High 7: G3(CLAUDE.md 3 섹션) / G4(plan-tradeoff ARCHIVED) / G5-G8(가이드 4.6/4.7 병기) / G21(fz-discover/peer-review VD 모듈)
- Medium 7: G9(MAR 교차 참조) / G10(NLAH 위치) / G11(tokenizer Deferred) / G16(micro-eval 트리거) / G19(canonical sink) / G20(needs_verification 결합) / G23(fz-codex 500줄 이하)
- Low 3: G12-G13 / G24(Follow-up Re-audit Gate + `${CLAUDE_PROJECT_DIR}` 경로)

**신규 모듈 섹션**:
- `modules/cross-validation.md` "Follow-up Re-audit Gate" (Phase B1/B2 활성)
- `modules/cross-validation.md` "micro-eval 호출 트리거 (공통)" (Claim-Type 라우팅 확장)
- `modules/memory-guide.md` "Claude Memory tool과의 관계" (fz L1 vs Anthropic client-side)
- `CLAUDE.md` (root) "Verification Discipline" / "Opus 4.7 Adaptation" / "Agent Teams Environment Flag" 3섹션

**검증 방법 강화**:
- v3 패치에서 "키워드 grep" → "구조적 검증 (헤더 + bullet exact-match + 인접성)"로 전환
- `^## Verification` 헤더 + bullet 3개 exact-match
- TeamCreate 라인 ±20줄 내 VD Brief 매치
- 팀 생성 절차 ±10줄 내 system-reminders + T6 + T7 동시 매치

**audit 방법론**:
- 3-Model 수렴: Claude Discover(4명) + Codex verify ×4 + Claude meta-analysis → 9 검증 라운드
- memory-curator 3-E "Claude blind spot" 실증: G22(템플릿) + fz-search/fz-pr-digest env flag drift + 카운트 regression 모두 Codex가 발견
- Plan v1 → v2 → v3 → 구현 → Codex final-v2 approved (0/0/0)

**경로/버전**:
- plugin.json: 3.10.0 → 4.0.0 (v3.11 변경도 plugin.json 미반영이었음 — 함께 통합)
- marketplace.json: 3.10.0 → 4.0.0

**검증 상태**: Codex final v2 **approved** (Critical 0 / Major 0 / Minor 0). audit 산출물은 `TVING/NOTASK-20260421-fz-audit/` 하위 16개 파일 보관.

### v3.11.0 (2026-04-21) — Opus 4.7 Adaptation + Verification Discipline

**핵심**: Claude Opus 4.7 (2026-04-16 GA) 출시에 따른 가이드 전면 업데이트. 2차 Codex cross-validation 기반 팩트 오류 정정 + 논문 근거 보강 + 공식 자료 정합성 확보.

**검증 상태**: Phase 1/2 Codex **approved**. Phase 3 (N1/N3/CHANGELOG) Codex 3라운드 iterate 후 approved.

**배경 research**:
- 1차 research: `claudedocs/research_fz_guide_updates_2026-04-21.md` (504줄)
- 2차 refined research: `claudedocs/research_fz_guide_refined_2026-04-21.md` (593줄) — 1차의 hallucination 3건 catch
- 통합 Gap Matrix: `claudedocs/fz_guide_update_gap_matrix_2026-04-21.md`

**Phase 1 — Critical 팩트 정정** (2건 실제 수정, 3건 hallucination 판명)
- `modules/cross-validation.md` L85: X-MAS(arxiv 2505.16997) 주장 완화 — 논문 abstract 재확인 결과 "2-model isolation" 실험 부재, "heterogeneous > homogeneous, MATH +8.4%, AIME +47%"로 정정
- `modules/context-artifacts.md` L228-230: Opus 4.6 → **Opus 4.7 (1M context, 2026-04-16 GA)** + tokenizer 1.00-1.35x 변경 주의 + Korean [미검증] 태그

**Phase 2 — Opus 4.7 하드코딩 정리 + 논문 근거 보강** (13 edits)
- `guides/harness-engineering.md`: 7곳 Opus 4.7 반영 (모델 세대 테이블 4-column 확장, tokenizer 경고, shallow long-context 주의)
- `guides/prompt-optimization.md` L276-278: Opus 4.7 "more literal instruction following" 경고 추가
- `guides/agent-team-guide.md` L406-411: 공식 사양 명시 (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, hard limit 명시 없음/3-5 권장, TeammateIdle/TaskCreated/TaskCompleted hooks)
- `modules/system-reminders.md`: Drift No More (arxiv 2510.07777) reminder injection 효과 근거 추가
- `modules/cross-validation.md`: VeriGuard (arxiv 2510.05156) dual-stage verification 근거 추가
- `skills/fz-review/SKILL.md`: MAR — Multi-Agent Reflexion (arxiv 2512.20845) 3중 검증 이론 근거
- `modules/memory-policy.md`: Intelligence Degradation (arxiv 2601.15300) + Context Length Hurts (arxiv 2510.05381) "1M = safety net not strategy" 근거

**Phase 3 — Infrastructure 구분 + Memory tool 관계** (2 additions)
- `guides/harness-engineering.md §1.3` 신규: Anthropic Scaling Managed Agents (2026-04-08) Brain/Hands 인프라 레이어와 fz Lead/Teammate 애플리케이션 레이어 구분 테이블
- `modules/memory-policy.md`: Opus 4.7 공식 Memory tool (file-system-based)과 fz 자체 L1/L2/L3의 중복 가능성 + 미래 전환 판단 기준

**Deferred**
- M5 (NLAH 13 agent list 갱신): Open Question — 논문 전문 확인 후 별도 업데이트
- N2 (Task Budgets beta): Messages API only, Codex CLI 미지원으로 fz 적용 불가

**Verification Discipline 적용 사례 (메타 교훈)**
- 1차 research의 hallucination 3건(`CLAUDE.md 40% 채택률`, `fz에 'ICLR 2025 Inside the Scaffold' 오인용 존재`, `Agent Skills OpenAI/MS 채택`)을 2차 research와 실측 grep으로 모두 catch → 잘못된 수정 방지
- Gap Matrix의 "Critical 4건" 중 3건이 fz 가이드에 존재하지 않는 이슈로 판명 → 실제 수정은 C3 + H1 2건만
- `[verified: source]` / `[미검증: 이유]` 태그 원칙 전파 — 공식 부재 부분 명시적 표시

**근거 논문 인용 재정렬**
- X-MAS (2505.16997) — 이종 조합 근거, abstract 기반 보수적 해석
- Drift No More (2510.07777) — reminder 효과
- MAR (2512.20845) — 역할 분리 이론
- VeriGuard (2510.05156) — dual-stage verification
- Intelligence Degradation (2601.15300) + Context Length Hurts (2510.05381) — 1M context 원칙
- NLAH (2603.25723) — 하네스 formalism (인용 유지, 13 agent list deferred)

---

### v3.10.0 (2026-04-15) — Scope Minimality

**핵심**: 코드 패턴 변환 시 기계적 1:1 래핑을 방지하는 "의미 판단" 체크포인트를 파이프라인 3단계(Plan→Code→Review)에 추가.
근거: PR #3694 (ASD-1002)에서 PromiseKit `.done` → `async/await` 전환 시, 클로저 전체를 `MainActor.run`으로 기계적 래핑하여 순수 연산까지 main thread에 묶는 실수 발생. hyundongyang 코멘트로 발견.

**Zero-Exception Thread Rule 범위 한정** (`modules/code-transform-validation.md`)
- 기존: "원본 main queue → After @MainActor 무조건" (기계적 전체 래핑 정당화)
- 변경: @MainActor **보장**은 필수이나 블록 **범위**는 실제로 main thread가 필요한 문장에만 한정
- Scope Minimality 단서 신규 추가 (Zero-Exception Rule 섹션 내)

**BEC step 3.5: Wrapper Scope Minimality** (`modules/code-transform-validation.md`)
- Behavioral Equivalence Check에 래퍼 범위 최소성 검증 단계 추가
- "이 문장이 해당 컨텍스트를 필요로 하는가?" 개별 판단 의무화
- 패턴 변환 시 Swift Concurrency 플러그인 필수 참조 지시 (BEC step 6)

**마찰 신호: "래퍼 범위 과잉"** (`skills/fz-code/SKILL.md`, `modules/code-transform-validation.md`)
- fz-code 25번째 마찰 패턴: @MainActor/do-catch/Task 블록 내 불필요 문장 포함 감지
- code-transform-validation 5번째 마찰 신호: 동일 패턴
- "스레드 컨텍스트 불일치"(too little)와 보완 쌍(too much)

**fz-review 4-K: wrapper_overscope** (`skills/fz-review/SKILL.md`)
- Transformation Equivalence 검증에 Wrapper Scope Minimality 체크 추가 (severity: Major)
- Gate 4 체크리스트 + Harness Metrics 테이블 확장

**plugin-refs.md actors 확장** (`modules/plugin-refs.md`)
- 구현 시: actors 행에 "패턴 변환 시 래퍼 범위 최소성 판단" 추가
- 리뷰 시: "@MainActor 블록 범위가 최소인가?" 체크 추가

**버그 수정**
- `code-transform-validation.md`: "Review(4-J)" → "Review(4-K)" 오표기 수정
- `plugin.json`: 3.8.0 → 3.10.0 (v3.9.0 릴리즈 시 bump 누락 수정)
- `marketplace.json`: 3.4.0 → 3.10.0 (동일)

**ablation 관측**
- 전체 새 항목에 `[ablation: scope-min-v1]` 태그 (4개 파일 8곳)
- 3회 패턴 변환 작업 후 이슈 발견 >= 1이면 Load-bearing 승격, 0이면 제거 검토

변경: 4개 파일, +14줄 -3줄. TEAM --deep (4 agents, 2 rounds) + 3중 리뷰 (3 agents) 검증.

---

### v3.9.0 (2026-04-14) — Harness Engineering Enhancement

**핵심**: SOLO 모드에서 Generator≠Evaluator 분리 불가능한 구조적 Gap 해소 + PR 코멘트 학습 파이프라인 설계.
근거: harness-engineering.md 작성 과정에서 발견한 NLAH Gap 5건 중 상위 2건.

---

### v3.8.0 (2026-04-12) — Uncertainty-Aware Harness

**핵심**: LLM이 모르는 것을 인정하고, 검증 도구로 확인하고, 실패에서 학습하는 하네스 시스템.
근거: PR-D1 리뷰에서 Codex(GPT-5.4)가 Claude blind spot 2건 발견. Codex Adversarial 6건 반영.

**신규 모듈: `modules/uncertainty-verification.md`**
- Default-Deny: [verified: source] 태그 없는 기술적 주장은 자동 unverified
- Verification Cost Tiers: Heavy(스레드/API계약) / Light(일반) / Skip(코드 확인)
- Evidence Source Priority: 코드 > 테스트 > 공식 문서 > 훈련 데이터
- Memory Feedback Loop: 검증 실패 → 교훈 기록 → 규칙 승격
- Pilot-first: v3.8은 Transformation Spec 경로만. 효과 확인 후 확장

**모듈 개선: `modules/code-transform-validation.md`**
- Zero-Exception Thread Rule: 원본 main queue → After @MainActor 무조건 (기본값)
- Transformation Spec v3.8: spec-version 필드 + 7번째 항목(요청 파라미터) + [verified] 태그
- 마찰 신호 4번째: 파라미터 키 불일치 (omit ≠ explicit default)
- BEC/4-K fail-closed: [verified] 없는 주장 → 구현 전 검증 강제

**스킬 개선 (4개)**
- fz-plan: Default-Deny [verified] 의무화 + Gate 1 체크리스트 3항목 (+7줄)
- fz-code: BEC fail-closed + 파라미터 키 마찰 신호 (+5줄)
- fz-review: 4-K enforcement + Gate 4 체크리스트 + Harness Metrics 보고 형식 (+22줄)
- fz-fix: uncertainty-verification 모듈 참조 (+1줄)

**Codex 스킬 개선 (2개)**
- fz-reviewer: Zero-Exception + Default-Deny + Parameter Presence (+9줄)
- fz-architect: 동일 규칙 요약 (+3줄)

**모듈 개선: `modules/cross-validation.md`**
- spec-verify: Codex가 Spec 기술적 정확성 검증 (TEAM 필수)
- confident-error: cross-model 불일치 → 교훈 기록
- default-deny enforcement: [verified] 없으면 fail-closed

**Harness Metrics (신규)**
- fz-review 완료 보고에 Gate별 이슈 수 기록 형식 추가
- 분기별 ablation 분석의 전제 데이터 수집 인프라

---

### v3.7.0 (2026-04-12) — Code Transformation Validation

**신규 모듈: `modules/code-transform-validation.md`**
- 코드 변환(Before→After) 동작 동등성 + 구조 품질 검증 공유 모듈
- Transformation Spec 형식 + 검증 체크리스트 + Swift 변환 규칙 + Context7 활용
- 3중 검증: Plan(Spec 작성) → Code(BEC 대조) → Review(4-K 준수)
- 트리거: 비동기/네트워크/UI 패턴 변환 시에만 활성 (단순 치환 제외)

**스킬 개선 (6개)**
- fz-plan: Transformation Spec 작성 절차 + Gate 1 체크리스트 (+10줄)
- fz-code: 마찰 신호 3개 + Behavioral Equivalence Check (+11줄)
- fz-review: 검증 4-K Transformation Equivalence (+15줄)
- fz-fix: 패턴 변환 감지 + 모듈 참조 (+5줄)
- fz-peer-review: Gather 4.5 패턴 변환 감지 (+8줄)
- fz-codex reviewer/architect: Swift 변환 규칙 임베딩 (+17줄)

**모듈 개선**: cross-validation.md 게이트 테이블 transformation 3행 추가

근거: PR-D1 플랜 7개 이슈 미탐지 사후 분석 (반성 11차)

### v3.6.0 (2026-04-11) — iOS/Swift Reverse Diagnostic Triggers

**역방향 감지 트리거 (plugin-refs.md)**
- 기존: 패턴 존재(e.g. `@MainActor`)만 트리거 → 패턴 부재 시 플러그인 비활성
- 신규: **패턴 부재** 시에도 안전성 관점 활성화 (Swift Concurrency 플러그인 활성 여부와 무관)
- Level 1 (구문): 싱글톤+가변상태 동기화 누락, 싱글톤 deinit dead code
- Level 2 (의미론): 콜백 스레드 불일치, @Published background 쓰기, 비동기 기본값 소비자 영향

**Concurrency Safety Audit — 검증 4-J (modules/safety-audit.md)**
- fz-review Phase 5에 항상 실행되는 안전성 감사 단계 추가
- 싱글톤 가변 상태 동기화 (L1 필수) + 콜백 스레드/@Published/기본값/API retention (L2 권장)
- Progressive Disclosure Level 3: 별도 모듈로 분리 (fz-review 500줄 한도 대응)

**에이전트 iOS/Swift 시맨틱 보강**
- review-quality: Concurrency Safety 활성 조건에 "역방향 트리거" 추가 + Library Semantics 4항목
- review-arch: State Lifecycle에 싱글톤 스레드 접근성 + Library Semantics 2항목
- impl-quality: Memory Safety에 싱글톤 가변 상태 동기화 누락 감지

**fz-code Implementation Friction 3행 추가**
- 동기화 부재 (singleton + var + 보호 없음)
- 싱글톤 deinit (static let shared + deinit)
- 기본값 소비자 영향 (비동기 property + 기본값)

**System Reminders T5 추가**
- 싱글톤 가변 상태 변경 감지 시 자동 리마인더 (동기화/deinit/기본값 확인)

**배경**: PR #3665 (NetworkMonitor) 리뷰에서 팀원이 발견한 4가지 이슈를 fz가 하나도 선제 감지 못함.
근본 원인: 트리거가 패턴 존재만 감지 → 가장 위험한 코드(보호 필요하나 없는 코드)가 가장 적은 검토를 받는 구조적 맹점.
82행 추가로 구조적 맹점 해소 (8파일: 7수정 + safety-audit.md 신규).

---

### v3.2.2 (2026-04-05) — Agent Role Optimization

**에이전트 책임 재분배 (Codex verified)**
- review-arch: 7→5 관점 축소 (Dead Code + Source Fidelity → review-quality 이관)
- review-arch: Context-Specific Behavior 테이블 제거 (단일 책임 원칙)
- review-quality: 리팩토링 완성도 항목 흡수, 7개 관점 명확화
- plan-structure: 영향 범위 분석을 plan-impact에 명시적 위임 (SendMessage)

**팀 구성 강화**
- fz-review: review-correctness 추가 (Phase 4.5 RTM 검증 한정)
- fz-fix: review-arch 조건부 참여 (복잡도 3+)
- memory-curator: "선택적" → "기본 포함, lightweight recall" (cross-validation.md 일치)

**동기화**
- team-registry, pipelines.md, patterns/live-review.md 팀 구성 반영
- fz-gemini 참조 제거 (README)
- plan-tradeoff.md → .archived

---

### v3.2.1 (2026-04-05) — Dependency Decoupling

**로컬 경로/iOS 의존성 제거 (7-Step, 27파일)**
- Step 1: fz-excalidraw 절대 경로(`/Users/jaewoongyun`) → `os.path.expanduser("~")` 동적 경로
- Step 2: Codex 네이티브 스킬 repo 포함 (`codex-skills/` 8개) + `scripts/setup-codex-skills.sh` + `get_codex_skill()` Tier 2b 폴백
- Step 3: 9개 에이전트 iOS 도메인 지식 → CLAUDE.md 키워드 기반 조건부 적용 + XcodeBuildMCP → "빌드 MCP 도구" 일반화
- Step 4: `modules/build.md` → CLAUDE.md `## Build` 동적 추출 (xcodebuild/npm/yarn/cargo/gradle 매칭)
- Step 5: fz-pr 팀 스킬 경로 → CLAUDE.md `## Git Workflow` 동적 참조
- Step 6: `modules/plugin-refs.md` → 프로젝트 언어/프레임워크 기반 조건부 적용
- Step 7: `templates/CLAUDE.md.template` — 새 사용자용 프로젝트 설정 템플릿

**리뷰에서 발견된 기존 이슈 수정**
- fz-review `## Guidelines` dangling reference → `## Code Conventions`
- fz-code/fz-fix iOS 16 인라인 하드코딩 → CLAUDE.md `## Plugins` 동적 참조
- `agent-team-guide.md` XcodeBuildMCP → 일반화
- README 아키텍처 트리 + 카운트 최신화

**제약**: 로컬 동작 100% 동일. CLAUDE.md에 iOS/RIBs 키워드 존재 시 조건부 활성화.

---

### v3.2 (2026-04-05) — Lead Implication Gate + Harness Engineering + System Reminders

**Lead Implication Gate** (analysis → plan → code → review 전체 반영)
- modules/lead-reasoning.md 신규 (165줄) — 추론 원칙 + 카테고리 분류 + 자문 체크리스트 + Implication Register
- cross-validation.md에 Implication Scan 게이트 + origin-equivalence 게이트 추가
- fz-code 마찰 감지에 "구조적 잔존물" + "관찰 보고 의무" 항목 추가
- fz-review 검증 4-I (Implication Coverage) 추가
- fz-plan Implication Register 출력 + Anti-Pattern 가이드 강화
- fz-codex Q8 함의 커버리지 질문 추가
- fz-fix revert 감지 → origin-equivalence 게이트 라우팅
- Codex 네이티브 스킬 4개 Implication taxonomy 통일

**Harness Engineering Guide** (1035줄)
- guides/harness-engineering.md 신규 — Anthropic 공식 2편 + NLAH 논문 + OpenDev 논문 + 오픈소스 구현체 기반
- 5대 기둥, 4가지 아키텍처 패턴, 6가지 설계 원칙, Anti-Patterns, 측정 지표, fz 매핑
- 11개 고품질 참고 문헌 (공식/학술만)

**Harness 기반 fz 고도화**
- modules/system-reminders.md 신규 — Instruction fade-out 대응 (트리거 기반 + 30턴 backstop)
- MEMORY.md Ablation 프로세스 — 분기별 Gate 기여도 측정
- CLAUDE.md Tool Usage 가이드라인 — Grep/Read/Bash 최적화
- Evaluator Tuning — 피드백 검증 프로토콜 4단계 (과적합 방지)
- review-arch/review-quality에 Tuning History 섹션

**피드백 신뢰도 검증 (과적합 방지)**
- 팀원 리뷰 코멘트 4단계 분류: project-rule / valid-suggestion / preference / needs-review
- preference(취향)는 에이전트 학습 절대 금지

**메모리 정리**
- MEMORY.md 205줄 → 114줄 (44% 감소). 이미 반영된 반성/교훈 제거, 인덱스만 유지.

---

### v3.1 (2026-04-02) — RTM + Teams v2 + Scope Expansion + L3 에이전트

**RTM (Requirements Traceability Matrix)**
- modules/rtm.md 신규 — plan이 Req-ID 생성 → code가 implemented 갱신 → review가 기계적 확인
- 산문 매칭 → ID 기반 추적으로 요구사항 누락 방어

**L3 네이티브 에이전트 통합**
- modules/native-agents.md 신규 — silent-failure-hunter + type-design-analyzer를 review Phase 5에 background 스폰
- L1(fz커스텀) > L3(네이티브) 원칙: L3는 보강만, TeamCreate 참여 금지

**Teams v2 — 팀 내부 통신 강화**
- L3→L1 피드백: L3 발견을 Lead가 Primary에 SendMessage → iOS 특화 재분석
- Supporting 활성화: impl-quality 매 Step 피드백, review-correctness 50%+마지막 RTM 체크
- Handoff Brief: plan→code 팀 전환 시 Key Decisions+Risks+Watch Points 구조화 전달
- plan-edge-case↔plan-impact CC: Supporting 간 교차로 연쇄 발견
- 5명+ 토폴로지: team-core.md에 Star-enhanced+CC 행 추가

**Scope Expansion — discover 시야 제한 4겹 방어**
- plan-impact: 변경 대상의 프로토콜/부모/같은 모듈까지 확장 탐색
- fz-plan Phase 0b: discover 로드 후 상위 수준 get_symbols_overview
- fz-code Phase 1.6: plan 영향 범위 < discover 범위이면 "시야 축소 위험" 마찰 신호
- cross-validation: review 시작 전 plan⊇discover 범위 확인

**네이티브 기능 강화**
- BATCH: merge 후 통합 빌드 gate 필수 + 부적합 조건 강화 (RIB/모듈 생성 금지)
- SIMPLIFY: 필수 gate 3가지 + 선택 suggestion 2가지 명확 분리 + 설계 의도 보존
- SC 조건 기반 자동 트리거: 빌드2실패→sc:troubleshoot, 3+Step 중간→sc:reflect, 복잡도4+→sc:estimate
- sc:save 모든 파이프라인 종료 시 (이전: 코드 변경만)

**정합성 개선**
- plan-edge-case: fz-plan YAML+registry+pipelines+pattern 4-way 동기화
- memory-curator: 모든 TEAM 참여 (이전: --deep/복잡도4+)
- plan-tradeoff: ARCHIVED (discover가 대체)
- 변경 파일 22개, RTM 19/19 verified, 리뷰 이슈 0건

### v3.0 (2026-03-30) — 3-Model Triad + 6-Agent Team + Landscape Discover

**3-Model Triad Architecture (연구 기반: X-MAS 47% 향상, ICLR 2025)**
- Claude(생산) + GPT/Codex(검증) + Gemini(Devil's Advocate) 3모델 체계
- fz-gemini 스킬 신규 생성 — Gemini CLI 전용 (review, verify, challenge)
- fz-codex에 --consensus 옵션 — 3모델 합의 모드
- cross-validation.md: Selective Consensus (불일치 시에만 Gemini 호출)
- team-core.md: 2-Tier → 3-Tier 모델 전략 (opus/sonnet/external)
- consensus-verify 파이프라인 신규 (#19)

**6-Agent Plan Team**
- fz-plan: 4 Claude + 1 GPT + 1 Gemini = 6개 차별화된 렌즈
- plan-impact 에이전트를 Impact Scanner로 강화 (Exhaustive Impact Scan 전담)
- Parallel Analysis + Cross-Feedback 통신 패턴
- 각 에이전트가 다른 질문을 던짐 (같은 질문 금지)

**Landscape Discover (discover 패러다임 전환)**
- "제약 발견 + 수렴" → "풍경 탐색 + 경로 매핑"
- provides: constraint-matrix → landscape-map + trade-off-table + open-questions
- 조건 불변성 구분: 🔒 hard constraint vs 🔓 soft preference
- discover는 결론을 내리지 않음 — plan이 경로를 선택
- adversarial 패턴: "부수기" → "비용/리스크 밝히기"

**Native Commands 활성화**
- /simplify: 선택 → 조건부 필수 (새 함수 3개+, 100줄+, 3회 빌드 실패)
- /batch: 독립 Step 3개+ 감지 시 자동 제안
- LOOP: 스킬별 에스컬레이션 래더 구체화

**Skill Refinement**
- fz-fix: 4-Phase 디버깅 (Reproduce → Isolate → Root-Cause → Verify Fix)
- fz-code: Step 완료 조건 3개 명시 (빌드 + conformance + caller 확인)
- Hooks 기반 물리적 강제: git commit 차단, platformFilter 자동 검사

**De-overfit**
- 반성 마커 제거 (규칙 유지, 출처만 삭제)
- Gate 체크리스트 경량화 (공통/조건부 분리)

### v2.5 (2026-03-20) — skill-creator Integration + Description Overhaul + Clean Architecture

**skill-creator 통합 (Runtime Trigger Eval + Description Optimization)**
- fz-skill에 `optimize` 서브커맨드 추가 — skill-creator `run_loop.py` 활용, train/test split 기반 description 자동 최적화
- fz-skill eval에 `Runtime Trigger Eval` phase 추가 — `run_eval.py`로 실제 `claude -p` 호출하여 트리거율 실측
- fz-skill create에 Phase 5 (Description Optimization 제안) 추가
- fz-manage benchmark에 `--with-trigger` 옵션 — 하위 3개 스킬 Quick Trigger Eval
- fz-manage check에 #11 skill-creator 설치 확인 항목 추가
- 신규 파일: `skills/fz-skill/references/skill-creator-integration.md` (L3 연동 가이드 + 실증 결과)
- 신규 파이프라인: #18 `skill-optimize` (pipelines.md)
- intent-registry.md에 fz-skill/fz-manage 자연어 트리거 보강

**실증 테스트 결과 및 교훈**
- 13개 스킬 전체 Runtime Trigger Eval 실행: 35/81 (43%)
- 핵심 발견: `claude -p` 자동 트리거는 슬래시 커맨드 스킬에 제한적 — should-NOT-trigger 100% 정확, should-trigger 0%
- description을 pushy 패턴으로 변경해도 트리거율 변화 없음 (43%→44%)
- 근본 원인: Claude가 간단한 요청을 스킬 참조 없이 직접 처리하는 경향
- 교훈 메모리 저장: `feedback_skill_creator_trigger_eval.md`

**전체 스킬 Description 고도화 (18/18)**
- skill-creator best practice 패턴 전면 적용:
  - Third-person: "This skill should be used when..."
  - Pushy triggers: "Make sure to use this skill whenever the user says: ..."
  - Keyword coverage: "Covers: ..." (Korean + English)
  - Boundary: "Do NOT use for..."
- 누락 5개 스킬 추가 적용: fz-codex, fz-new-file, fz-pr-digest, fz-pr, fz-recording

**500줄 제한 준수**
- fz-review: 513 → 492줄 (redundant separators 제거)
- fz-peer-review: 503 → 497줄 (redundant separators 제거)

**Clean Architecture 가이드 (Uncle Bob 페르소나)**
- 신규 파일: `guides/clean-architecture.md`
- 내용: Dependency Rule, SOLID 5원칙, 4 Layers 정의, Boundary Crossing 규칙, Architecture Smells, Uncle Bob's Decision Rules, Pragmatic 균형
- review-arch 에이전트: Architecture Decision에 Dependency Rule + SOLID 위반 감지 연결
- impl-quality 에이전트: Architecture Consistency에 DIP 위반 감지 연결
- fz-plan 스킬: 영향 분석 Step 4 "Clean Architecture 원칙 확인" 추가

**생태계 건강 체크**
- 전체 13개 항목 건강 체크 실행: 12.5/13 PASSING
- YAML 필수 필드 100%, provides/needs 체인 완전, 깨진 참조 0개
- 에이전트 14개 전부 유효, 모듈 17개 전부 존재

### v2.4 (2026-03-18) — Remove GitButler + Git Workflow Simplification

**GitButler 제거**
- GitButler 스킬 삭제 (`skills/gitbutler/` — SKILL.md + 3 reference files, -1,551줄)
- README.md 스킬 목록, CLI 도구, Infrastructure 다이어그램에서 제거 (22→21 스킬)
- 이유: Claude Code와 함께 사용 시 이점 없음 — 단일 working directory 공유로 Agent 병렬 작업 시 상호 오염 발생

**Git 워크플로우 전환**
- GitButler CLI(`but`) → 표준 `git` 명령으로 전환
- 병렬 브랜치 작업: `git worktree`로 독립 디렉토리 생성 권장
- 세션 시작: `but pull` → `git pull upstream develop`

### v2.3 (2026-03-15) — 1M Context Optimization + Ecosystem Health Fix

**1M Context Infrastructure (Opus 4.6 1M)**
- Artifact Token Budget 신설 — 100K cap + eviction 우선순위 (context-artifacts.md)
- ASD 임계값 hybrid: `6+ step 또는 context-heavy` (기존 4+)
- Essential Context 500자→3,000자 (memory-policy.md, fz/SKILL.md)
- Proactive Module Loading — /fz Phase 0에서 핵심 모듈 선로드
- Compact 경고 6+→12+ step, 4-tier 파이프라인 전략
- prompt-optimization.md: 200K 하드코딩 → 상대 서술

**Ecosystem Health Check Fix (86→95점)**
- fz-plan: `needs: [refined-requirements]` → `[none]` (standalone 실행)
- Phase 0 index.md 생성 — 5개 스킬에 compact recovery 추가
- Discover 프로토콜: DISCOVER_TAG 기반 journal=덮어쓰기, phase=APPEND
- fz-peer-review: Serena memory 도구 추가 + 2개 CHECKPOINT fallback
- fz-excalidraw: 에러 대응 섹션 (18/18 일관성)
- memory-policy.md: 4개 테이블 전면 수정 (stale → actual write_memory)
- context-artifacts.md: CWD=PROJECT_ROOT 정의, standalone peer-review workdir

**Agent Tier-1 Enrichment**
- BAD/GOOD 예시: review-direction, review-arch, review-quality, memory-curator
- Escalation Criteria: 5개 review 에이전트
- Input Format (Task Brief): review-direction, memory-curator
- Cross-skill wiring: fz-code direction-challenge, fz-review step files hydration

**Cross-skill Context**
- team-core.md: 통신 기록 요약 기본 + 원본 drill-down (*-team-full.md)
- cross-validation.md: Codex transcript 요약/원본 분리 정책

### v2.2 (2026-03-12) — Agent Teams + Context Budget + Peer Review Gate

**Agent Teams Frontmatter 적용 (Phase 1-4)**
- `memory: project|user` — 5개 에이전트에 세션 간 영속 학습 적용 (review-arch, impl-correctness, plan-structure, review-quality, memory-curator)
- `skills: [name]` — review-arch(arch-critic), review-quality(code-auditor)에 스킬 사전 주입
- `isolation: worktree` — impl-correctness에 코드 수정 격리
- `TaskCompleted` hook — 에이전트 완료 시 산출물 존재 검증 (settings.json 팀 레벨)
- team-registry.md 모델 컬럼을 `default`/`promoted`로 분리 (거버넌스 명확화)
- agent-team-guide.md §8 전체 문서화

**Context Budget 관리**
- prompt-optimization.md §2.5 — MCP 출력 격리, 도구 정의 최소화, 서브에이전트 효율
- 트리밍 비저하 원칙 — Gate/Few-shot/Step 삭제 금지 (prompt-optimization.md + skill-authoring.md)
- context-artifacts.md — 사전 예방적 Context 관리 섹션 추가

**Peer Review Deleted Logic Migration Gate**
- Gate 4.7-A — 모듈화/리팩토링 PR에서 "삭제 = 누락" 오탐 방지
- arch-critic, code-auditor, review-quality에 "삭제 vs 이동 판별" 원칙 추가
- fz-peer-review, fz-review 토큰 최적화 (-230줄, 정보 보존)
