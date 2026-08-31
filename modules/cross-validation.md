# 교차 검증 주입 전략

> **Sources (last audited: 2026-07-25 — 모델 사실 축):** `guides/llm-references.md` §1 정본 대조 완료 (Opus 5 "검증 지시 삭제" 지침 대비 게이트 존치 경계 성문화 포함).
>
> fz Phase 3에서 파이프라인에 검증 게이트를 자동 삽입. 모든 모드에서 최소한의 검증 보장.
> 핵심 원칙: TEAM = Claude 에이전트(N) + Codex(1). 코드/계획 생산 TEAM에 Codex CLI 필수 참여. 탐색 파이프라인은 --deep만.

## 목차

- [이론 근거 — Heterogeneity + Blind-spot Complementarity (T1-E)](#이론-근거--heterogeneity--blind-spot-complementarity-t1-e)
- [검증 유형별 전략](#검증-유형별-전략)
- [검증 게이트 자동 삽입 규칙](#검증-게이트-자동-삽입-규칙)
- [외부 모델 포함 원칙 (TEAM 필수)](#외부-모델-포함-원칙-team-필수)
- [Cross-Model Verification (2-Model)](#cross-model-verification-2-model)
- [경량 검증 게이트](#경량-검증-게이트)
- [Reflection Rate (Authoritative Source)](#reflection-rate-authoritative-source)
- [Gate 절차적 강제](#gate-절차적-강제)
- [품질 에스컬레이션](#품질-에스컬레이션)
- [검증 게이트 시각화](#검증-게이트-시각화)
- [공유 유틸리티](#공유-유틸리티)
- [참조 스킬](#참조-스킬)
- [Codex 검증 결과 보존 정책](#codex-검증-결과-보존-정책)
- [Implication Scan 게이트](#implication-scan-게이트)
- [Follow-up Re-audit Gate (Phase B1/B2 활성 시)](#follow-up-re-audit-gate-phase-b1b2-활성-시)
- [origin-equivalence 게이트 (revert 전용)](#origin-equivalence-게이트-revert-전용)
- [외부 피드백 검증 (External Feedback Gate)](#외부-피드백-검증-external-feedback-gate)
- [런타임 동작 주장 검증 (Runtime Claim Gate) [관찰 모드]](#런타임-동작-주장-검증-runtime-claim-gate-관찰-모드)
- [SOLO 모드 검증 게이트 요약](#solo-모드-검증-게이트-요약)
- [Coverage Gate (문서/파일 분석 전수 보장)](#coverage-gate-문서파일-분석-전수-보장)
- [Negative-Result Gate (0건·부재 주장의 도구 유효성)](#negative-result-gate-0건부재-주장의-도구-유효성)
- [설계 원칙](#설계-원칙)

---

## 이론 근거 — Heterogeneity + Blind-spot Complementarity (T1-E)

> fz의 Codex 교차 검증은 "debate / adversarial review" 프레임이 아닌 **"Self-preference bias 상쇄 + 이종 blind spot 보완 + Generator≠Evaluator 강제"** 프레임으로 이해.

### 4 메커니즘

| 메커니즘 | 출처 | fz 적용 |
|---------|------|--------|
| **Self-preference bias 상쇄** | 2025 LLM-as-Judge 연구 다수 — 같은 모델이 자기 출력을 우호적으로 평가 (메모리 23차 Self-review blind spot 메커니즘) | Generator (Claude) ≠ Evaluator (Codex) 강제. fz-codex `verify`/`check`가 이 분리의 구체화 |
| **이종 blind spot 보완** | MoA "collaborativeness" (Wang 2024, ICLR 2025 Spotlight, +7.6pp AlpacaEval) | Claude family blind spot을 GPT family가 catch (15차/23차 패턴 — Codex 단독 발견 누적 사례) |
| **Generator≠Evaluator 강제** | Anthropic Harness Engineering H2 (2026-03) — "Self-evaluation is unreliable"; fresh-context verifier > self-critique [verified: code.claude.com/docs/en/best-practices, code.claude.com/docs/en/sub-agents] | TEAM 모드에 Codex 필수 참여. SOLO에서도 결정론적 도구 호출 (Q-OBSERVE 경량). Codex 불능 시 fresh-context Claude 검증자가 self-review blind spot(23차)을 부분 보강 — 동종 한계 명시 |
| **Position bias 회피** | Order effect on judgment (LLM-Judge 연구) | T1-G ensemble: 출력 randomize + Source label anonymize (CP-1 Step 3 규칙 5/6/7) |

### "Debate 프레임" 회의론 (X-3 기각 근거)

ICLR 2025 Blogposts: Debate 효과 대부분이 **majority voting**으로 환원됨. "Adversarial debate"가 아닌 **"이종 모델 다관점 + Lead 종합"** 프레임이 학술적으로 더 정확. fz는 X-3 ("Debate 확장")을 기각하고 본 프레임 채택.

### 적용 가이드

- **fz-codex 모든 서브커맨드** = Generator≠Evaluator 분리 구현체
- **T1-G ensemble** = MoA-Lite 2-layer 구현 (cross-agent diversity 강화)
- **η-1** = Position bias 회피의 prompt-level 강화 (team-core.md Gate 1.0 Independence Verified로 구현)
- **Reflection Rate 측정** = 이종 blind spot 보완 효과 정량화 (T1-B §5.5 schema)

### 학술 참조

- LLM-as-Judge self-preference: 2025 다수 연구
- MoA collaborativeness: Wang 2024, ICLR 2025 Spotlight
- Harness Self-eval unreliability: Anthropic 2026-03 (Planner/Generator/Evaluator)
- Debate 회의론: ICLR 2025 Blogposts

---

## 검증 유형별 전략

| 파이프라인 카테고리 | 검증 유형 | 메커니즘 | 모드 조건 |
|-------------------|----------|---------|----------|
| code-changes 생산 | 빌드 검증 | modules/build.md 절차 | 모든 모드 |
| code-changes 생산 | simplify check (선택) | /simplify | 모든 모드 |
| code-changes 생산 | Codex check | `fz-codex check` (팀 내 병렬) | TEAM |
| code-changes 생산 (리팩토링) | enforcement 검증 | Anti-Pattern Grep + Module Boundary | 모든 모드 (Plan에 Constraints 있을 때) |
| code-changes 생산 (모듈화/캡슐화) | consumer quality 검증 | 소비자 파일 전수 수집 + 사용 패턴 + 진입점 검증 | 모든 모드 (모듈화 작업 시) |
| code-changes 생산 (시그니처 변경) | protocol conformance 검증 | find_referencing_symbols → 프로토콜 요구사항 양방향 확인 | 모든 모드 |
| code-changes 생산 (init 변경) | inheritance DI conformance | base_class_hierarchy → subclass init + 화면별 dependency 확인 (Gate 4.6.5) | 모든 모드 (init 변경 시) |
| code-changes 생산 (제거/리팩토링) | implication-scan | lead-reasoning.md § Implication Scan | 모든 모드 (1차/2차 트리거) |
| code-changes 생산 (모든) | Q-OBSERVE 경량 | lead-reasoning.md § 상시 경량 | 모든 모드 (상시) |
| revert 작업 | origin-equivalence | lead-reasoning.md + cross-validation.md § origin-equivalence | 모든 모드 (revert 키워드) |
| planning 생산 전 | 방향성 검증 | review-direction 에이전트 (Phase 0.5) | TEAM (fz-plan) |
| planning 생산 전 | 교훈 회상 | memory-curator (memory-recall) | 모든 TEAM |
| code-changes 생산 전 | 교훈 회상 | memory-curator (memory-recall) | 모든 TEAM |
| review 시작 전 | 교훈 회상 | memory-curator (memory-recall) | 모든 TEAM |
| planning 생산 | 계획 검증 | `fz-codex verify` (팀 내 병렬) | TEAM |
| review 포함 | 다관점 리뷰 | review-arch + review-quality + Codex (팀 내 병렬) | TEAM |
| search 포함 | 교차 검증 | search-symbolic + search-pattern + Codex (팀 내 병렬) | TEAM(--deep) |
| commit/pr 포함 | Pre-ship gate | `fz-codex check` | TEAM |
| fix 포함 | 수정 검증 | `fz-codex check` (팀 내 병렬) | TEAM |
| review 포함 | L3 에러 처리 스캔 | silent-failure-hunter (Agent background) | TEAM (diff에 에러처리 코드 포함 시) |
| review 포함 | L3 타입 설계 평가 | type-design-analyzer (Agent background) | TEAM (diff에 새 타입 정의 포함 시) |
| code-changes 생산 | SC 빌드 진단 | `/sc:troubleshoot --fix` 자동 | 빌드 2회 연속 실패 시 |
| planning 생산 | SC 공수 추정 | `/sc:estimate --breakdown` | plan + 복잡도 4+ |
| review 포함 | L3 결과 반영 | Lead가 **다음 Workflow invoke의 args/브리프에 주입** — ⛔ `SendMessage` 부재(v2.1.178~) + Workflow 워커는 1-shot이라 중간 채널 없음 | Workflow (L3 이슈 1건+, 다음 스테이지 전) |
| code 포함 | Supporting 진행도 체크 | review-correctness → impl-correctness RTM 체크 | TEAM (3+ Step 50% 시점) |
| review 시작 전 | Scope Expansion 검증 | plan 영향 범위 ⊇ discover 범위 확인. plan이 더 좁으면 warning | discover 산출물 존재 시 |
| code 시작 전 | 시야 축소 감지 | plan 영향 범위 vs discover 범위 비교 → 좁으면 마찰 신호 | discover 산출물 존재 시 |
| planning 생산 (패턴 변환) | transformation spec | code-transform-validation.md Spec 작성 + Context7 확인 | 모든 모드 (패턴 변환 시) |
| code-changes 생산 (패턴 변환) | behavioral equivalence | Spec 대비 구현 대조 (스레드/에러/추상화) | 모든 모드 (Spec 있을 때) |
| review 포함 (패턴 변환) | transformation equivalence (4-K) | Spec 대비 diff 대조 | 모든 모드 (Spec 있을 때) |
| planning 생산 (Spec v3.8) | spec-verify | Codex가 Spec의 기술적 정확성 검증 (스레드 모델, 파라미터 의미론, Default-Deny) | TEAM 필수, SOLO 권장 |
| cross-model 불일치 감지 | confident-error | Claude vs Codex 판정 불일치 → 교훈 기록 + 상세 분석 (uncertainty-verification.md) | 자동 |
| code/review (Spec v3.8) | default-deny enforcement | Spec 기술적 주장에 [verified] 없으면 fail-closed | 모든 모드 (spec-version 3.8) |
| 외부 피드백 수신 시 | external-feedback-verify | Read(시그니처) + 기존 패턴 대조 → valid/invalid 판정 | 모든 모드 |
| 런타임 동작 단정 시 | runtime-claim-verify | Bash Swift 스크립트 실행 또는 "미검증" 표기 | 모든 모드 [관찰] |

---

## 검증 게이트 자동 삽입 규칙

> ⚠️ **Opus 5 경계선 (2026-07-25) — 이 게이트들은 존치한다.** Opus 5 공식 프롬프팅 가이드는 *검증 지시를 삭제하라*고 명시한다("include a final verification step" / "use a subagent to verify" / "double-check your answer" → 제거 시 *"no loss in quality"*) [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5]. 그러나 **삭제 대상은 *모델에게 자기 작업을 재확인시키는 프롬프트 문구*** 다.
>
> 아래 게이트는 성격이 다르다 — **① 하네스가 실행하는 결정론적 oracle**(build·enforcement·implication-scan: 모델 판단이 아니라 도구 실행) **② 이종 모델 교차검증**(codex check/verify: 동종 self-eval이 못 잡는 blind-spot) **③ 다른 관점의 독립 분석**(direction challenge, review-arch/quality). 셋 다 자기재확인이 아니므로 **일괄 제거 금지**.
>
> ⛔ 반대로, 워커 프롬프트 안에 "마지막에 스스로 검증하라" 류 문구가 있다면 그건 제거 대상이다. **게이트(구조) ≠ 지시(문구)** — 이 구분을 흐리면 load-bearing 게이트가 사라진다.

### 코드 생산 파이프라인

```
[코드 생산 스텝] → build → conformance (시그니처 변경 시) → enforcement (리팩토링 시) → consumer quality (모듈화 시) → implication-scan (제거/리팩토링 시) → codex check (TEAM) → [다음 스텝]

예시 (fix-ship, TEAM):
  /fz-fix → build → codex check → /fz-commit → /fz-pr

예시 (plan-to-code, 리팩토링, TEAM):
  /fz-plan → codex verify → /fz-code → build → enforcement → codex check

예시 (quick-fix, SOLO):
  /fz-fix → build → 완료 (codex check 생략)
```

> enforcement: Plan에 Anti-Pattern Constraints가 있을 때만 삽입.

### 계획 생산 파이프라인

```
memory-recall (TEAM, informational) → direction challenge (TEAM, fz-plan Phase 0.5) → [계획 스텝] → codex verify (TEAM) → [코드 스텝]
```

> direction challenge: review-direction 에이전트가 접근 방향 자체를 도전 (PROCEED/RECONSIDER/REDIRECT 판정).

### 리뷰 포함 파이프라인

fz-review가 이미 3중 검증을 수행하므로 추가 삽입 없음.
TEAM 모드에서는 review-arch/review-quality가 팀 에이전트로 독립 다관점 분석.

---

## 외부 모델 포함 원칙 (TEAM 필수)

> 핵심: TEAM = Claude 에이전트(N) + Codex(1). 코드/계획 생산 TEAM에 Codex 필수.
> **A3 (동종 합의 ≠ 독립검증)**: 동종 모델 에이전트 N명의 합의는 독립 검증이 아니다 — 같은 맹점을 공유하고 wrong-majority에 conform한다(debate ceiling). cross-model(Codex) 체크 후에만 합의를 신뢰하고, lone correct dissent를 majority보다 우선 검토한다 [verified: arxiv 2503.13657 MAST — inter-agent misalignment]. (memory 23차 — self-review blind spot, cross-model이 마지막 안전판)
> 근거:
> - X-MAS(arxiv 2505.16997) — **이종 모델 조합이 동종보다 우수** (MATH +8.4%, AIME +47% 성능 향상). `[verified: 2차 research, 논문 abstract 확인 2026-04-21]`
> - VeriGuard(arxiv 2510.05156) — **dual-stage verification** (Pre-action Gate + Runtime Gate 이중 구조)이 단일 검증보다 우수. fz의 ✓ stress-test + ✓ codex check 2단계와 구조적 정합

| 스킬 | Codex | Codex 스킬 |
|------|-------|-----------|
| /fz-plan | `fz-codex verify` | architect |
| /fz-code | `fz-codex check` | reviewer |
| /fz-review | `fz-codex validate` | guardian |
| /fz-fix | `fz-codex check` | reviewer |
| /fz-search | `fz-codex` | searcher |

> Codex 3-Tier 디스커버리: CLAUDE.md `## Codex Skills`(Tier 1) → 글로벌 fz-*(Tier 2) → 인라인(Tier 3).

---

> 이론 근거: VeriGuard dual-stage verification + MAR (arxiv 2512.20845) 역할 분리 — generator와 verifier 모델/역할이 다를 때 false positive/negative 모두 감소.

## Cross-Model Verification (2-Model)

Claude + Codex(GPT-5.5) 교차 검증:

| 트리거 | 프로바이더 | Effort |
|--------|-----------|--------|
| code-changes (TEAM) | Codex check | high |
| planning (TEAM) | Codex verify | high |
| final / --deep | Codex | xhigh |
| 불일치 시 | AskUserQuestion | 사용자 판단 |

### Disagreement 기록
- ASD 활성: `{WORK_DIR}/verify/consensus-{YYYYMMDD_HHMMSS}.md` (timestamp suffix로 같은 날 다중 session overwrite 방지)
- 비ASD: `write_memory("fz:consensus:{YYYYMMDD_HHMMSS}", "합의/불일치 요약")` (상수 key 대신 timestamp suffix)

---

## 경량 검증 게이트

| 모드 | 코드 생산 후 검증 | 계획 생산 후 검증 |
|------|-----------------|-----------------|
| SOLO | 빌드만 | 없음 (Lead 직접 판단) |
| TEAM | 빌드 + Codex check (config 모델+high) + 에이전트 확인 | Codex verify (config 모델+high) |
| TEAM --deep | 빌드 + Codex (config 모델+xhigh) | Codex verify (xhigh) |

> Effort 정의: `modules/codex-strategy.md` 참조. 기본 high, final/--deep은 xhigh. Review Gate OFF.

---

### micro-eval 호출 트리거 (공통)

다음 조건 중 하나 충족 시 `/fz-codex micro-eval` 자동 호출 후보:

- 단일 사실 주장에 `[verified]`/`[미검증]` 태그 명시 불가 (검증 도구 즉시 사용 불가)
- Claim-Type이 factual / tool-behavior / external-state 분류 (즉, 코드/문서/외부 상태 사실 주장)
- fz-plan / fz-code / fz-review 모든 파이프라인에서 공통 활용 (특정 단계 한정 아님)

명령 형식:
```bash
/fz-codex micro-eval "주장 원문" [컨텍스트]
```

응답: `verdict: agree | disagree | partial | needs_verification` (참조: `modules/fz-codex-subcommands-aux.md § micro-eval` 섹션 — 2026-05-27 모듈 분리로 경로 갱신)

`needs_verification` 시: `modules/uncertainty-verification.md` Default-Deny 차단으로 연계.

---

## Reflection Rate (Authoritative Source)

> 본 섹션이 fz 생태계 Reflection Rate **threshold/gating 정책**의 **단일 진실 원천**(authoritative source)입니다. 계산식 정밀 정의(partially_resolved 0.5 가중치 포함)는 `schemas/codex_verification_schema.json`이 canonical. 다른 모듈/SKILL.md는 본 섹션으로 backlink만 허용 (history rewrite 금지, 기존 본문은 유지).

**계산식**: Reflection Rate = (Codex가 제기한 이슈 N개 중 Claude가 수정 반영한 수) / N × 100% (정밀 계산식 — `partially_resolved`에 0.5 가중 — 은 `schemas/codex_verification_schema.json` canonical). **N=0 (Codex가 이슈 0개 제기) 시 `N/A`로 기록** — division-by-zero 방지 + 기준 미달 판정 아님 (vacuously passes).

### Reflection Rate threshold (Sample Size Confidence Gate)

| Sample N | Status | Verdict 가능 |
|----------|--------|------------|
| N < 10 | **preliminary** | ❌ verdict 보류 — measurement only. threshold 80%는 N≥10 데이터 누적 후 재설정 |
| 10 ≤ N < 30 | provisional | ⚠️ 점수 + 95% CI 발표 |
| N ≥ 30 | stable | ✅ trend analysis 가능 |

**왜**: N=3-5 sample에서 73%-86% 변동 관측. 통계적 유의성 부재 → 작은 표본에서 threshold gating 시 false positive/negative 위험.

| 모드 | Reflection Rate 추적 | 기준 |
|------|---------------------|------|
| SOLO | 추적 없음 | 사용자 직접 판단 |
| TEAM | Reflection Rate 추적 (N<10이면 preliminary) | N≥10에서만 ≥80% gating. N=0이면 vacuous pass |

> 예시 1 (N≥10): Codex 5 이슈 / Claude 4 반영 → 80% (provisional or stable, threshold pass)
> 예시 2 (N<10, current): N=5에서 81-86% → preliminary, no verdict gating
> 예시 3: Codex 0 이슈 → N/A (vacuous pass)

---

## Gate 절차적 강제

검증 게이트는 "권고"가 아닌 **절차적 강제**다. 스킵 불가 조건:

| 게이트 | 강제 수준 | 스킵 조건 |
|--------|----------|----------|
| build | **필수** (코드 변경 시) | 코드 변경 없는 문서 전용 파이프라인만 예외 |
| codex check | **필수** (TEAM 코드/계획) | SOLO 모드 또는 탐색(--deep 없음) |
| stress-test | **필수** (fz-plan) | discover 결과에서 이미 검증된 제약은 재검증 생략 |
| Reflection Rate | **필수** (TEAM review) | SOLO 모드 |

Gate 실패 시: 해당 단계를 "완료"로 표시할 수 없다. 반드시 재시도/수정/사용자 에스컬레이션 중 하나를 수행해야 한다.

## 품질 에스컬레이션

| 상황 | 모드 | 대응 |
|------|------|------|
| 빌드 실패 | 모든 모드 | /ralph-loop 에스컬레이션 래더 (modules/execution-modes.md) |
| codex check 실패 | TEAM | 에이전트에게 이슈 전달 → 수정 → 재검증 |
| 검증 실패 (반복) | SOLO | 사용자에게 `/fz-review` 제안 |
| Reflection Rate < 60% | TEAM | /ralph-loop 래더 → 한도 후 사용자 에스컬레이션 |

---

## 검증 게이트 시각화

Phase 4(User Confirmation)에서 검증 게이트도 함께 표시.

```markdown
| # | 스킬 | 역할 | 실행자 | 모델 |
|---|------|------|--------|------|
| 1 | /fz-plan | 구현 계획 | plan-structure | opus |
| 2 | codex verify | 계획 검증 | Lead | codex |
| 3 | /fz-code | 점진적 구현 | impl-correctness | opus |
| 4 | build | 빌드 검증 | Lead | — |
| 5 | codex check | 교차 검증 | Lead | codex |
| 6 | /fz-commit | 커밋 | Lead | opus |
```

---

## 공유 유틸리티

> 분리 후보: 3개+ 스킬에서 참조 시 독립 `modules/shared-utils.md`로 추출 검토 (governance.md 모듈 분리 기준 참조)

### GIT_ROOT 추출

```bash
GIT_ROOT_REL=$(grep -A 5 "^## Directory Structure" CLAUDE.md 2>/dev/null | \
  grep -i "git.root" | awk -F: '{print $2}' | xargs)
GIT_ROOT="${GIT_ROOT_REL:-.}"
```

### get_codex_skill_path() — 3-Tier 디스커버리

> ⛔ **2026-08-09 계약 변경 — 이름이 아니라 `SKILL.md` 절대경로를 반환한다.**
> 이전 판(`get_codex_skill()`)은 Tier 2b에서 **플러그인 `codex-skills/`를 확인한 뒤 이름만** 반환했는데, 호출자 8곳은 항상 `cat ~/.codex/skills/${NAME}/SKILL.md` 를 읽었다. 심볼릭이 없으면 `[ -n "$NAME" ]`가 true라 **Tier 3 generic 폴백으로 가지 않고 존재하지 않는 경로를 `cat`** 했다 — 즉 Tier 2b가 파손 상태였다.
> 부수 정정: `BASH_SOURCE[0]` 의존 제거 — 이 함수는 **마크다운에서 인라인 복사**되어 실행되므로 `dirname "${BASH_SOURCE[0]}"`가 스크립트 위치를 가리키지 않는다. 플러그인 루트를 **인자/환경변수로 명시 전달**한다.

```bash
# usage: get_codex_skill_path <role> [plugin_root]
#   반환: SKILL.md 절대경로 (없으면 빈 문자열 → 호출자가 Tier 3 인라인 프롬프트로 폴백)
get_codex_skill_path() {
  local ROLE=$1
  local PLUGIN_ROOT="${2:-${FZ_PLUGIN_ROOT:-}}"
  local PROJECT_ROOT="$(pwd)"

  # Tier 1: 프로젝트 CLAUDE.md `## Codex Skills` 테이블
  local SKILL=$(grep -A 20 "^## Codex Skills" "${PROJECT_ROOT}/CLAUDE.md" 2>/dev/null | \
    grep "| $ROLE " | awk -F'|' '{print $3}' | xargs)
  if [ -n "$SKILL" ] && [ -f "$HOME/.codex/skills/$SKILL/SKILL.md" ]; then
    echo "$HOME/.codex/skills/$SKILL/SKILL.md"; return
  fi
  # Tier 2a: ~/.codex/skills/ (setup-codex-skills.sh 심볼릭 또는 기존 설치)
  if [ -f "$HOME/.codex/skills/fz-${ROLE}/SKILL.md" ]; then
    echo "$HOME/.codex/skills/fz-${ROLE}/SKILL.md"; return
  fi
  # Tier 2b: 플러그인 번들본 — ⛔ 경로를 반환한다 (이름만 반환하면 호출자가 못 찾는다)
  if [ -n "$PLUGIN_ROOT" ] && [ -f "$PLUGIN_ROOT/codex-skills/fz-${ROLE}/SKILL.md" ]; then
    echo "$PLUGIN_ROOT/codex-skills/fz-${ROLE}/SKILL.md"; return
  fi
  echo ""
}
```

Tier 1: CLAUDE.md `## Codex Skills` 테이블 → Tier 2a: `~/.codex/skills/` 심볼릭 → Tier 2b: 플러그인 번들 → Tier 3: 인라인 프롬프트(빈 문자열 반환).

### ⛔ `FZ_PLUGIN_ROOT` 초기화 (Tier 2b 전제 — 미설정 시 Tier 2b가 성립하지 않는다)

> **신설 근거 (2026-08-09 외부 감사 ISSUE-009)**: 위 함수와 8개 호출부가 `FZ_PLUGIN_ROOT`를 **소비**하는데 레포 어디에도 **할당이 없었다**(실측: 소비 10곳 / 할당 0곳). 전부 빈 문자열이 전달되어 `[ -n "$PLUGIN_ROOT" ]`가 false → **Tier 2b가 항상 건너뛰어졌다.** Tier 2b 파손을 고치려던 변경이 목표를 달성하지 못한 상태였다.

⛔ **`codex exec` 호출 전에 반드시 1회 실행한다.** 절차는 **2단계**다 — ①Lead가 스크립트의 절대경로를 만들고 ②스크립트가 자기 위치에서 루트를 해석한다.

⛔ **부트스트랩 순환 주의**: 셸 스니펫만으로는 해결되지 않는다. `{스킬 base directory}` 같은 토큰은 **치환되지 않는 리터럴**이라 `cd`가 실패한다 (2026-08-09 감사 ISSUE-PLAN-001). 첫 절대경로는 **Lead가 대화 컨텍스트에서** 만든다.

**① Lead 절차 (셸 아님)**: 스킬 주입 헤더 `Base directory for this skill: …/skills/fz-codex` 를 읽고 `../..` 를 적용해 **플러그인 루트 절대경로**를 얻는다. 그 값으로 아래 `<PLUGIN_ROOT_ABS>` 를 채운다.

**② 셸 (실행 가능)**:
```bash
# 자기 위치에서 루트를 해석하고 마커로 fail-closed 검증한다 (exit 2 = 루트 아님)
FZ_PLUGIN_ROOT="$(<PLUGIN_ROOT_ABS>/scripts/resolve-plugin-root.sh)" || {
  echo "WARN: FZ_PLUGIN_ROOT 해석 실패 — Tier 2b 불가, Tier 2a/3로만 동작" >&2
  FZ_PLUGIN_ROOT=""
}
export FZ_PLUGIN_ROOT
```

- ⛔ **빈 값으로 조용히 진행하지 말 것**: 위처럼 경고를 내야 "Tier 2b를 썼다"는 오해가 생기지 않는다
- ⛔ 스크립트는 `BASH_SOURCE[0]`을 쓴다 — `$0`은 `source` 시 **호출자**를 가리켜 오해석된다
- ✅ Tier 2a(심볼릭)가 있으면 Tier 2b에 닿지 않으므로 미설정이 **무증상**이다 — 그래서 실측 없이는 드러나지 않았다
- ✅ 이미 스크립트 안에서 호출하는 경우(자기 `dirname`을 아는 경우)는 ①이 불필요하다:
  `FZ_PLUGIN_ROOT="$("$(dirname "${BASH_SOURCE[0]}")/resolve-plugin-root.sh")"`

**호출 계약** (⛔ 8곳 전부 이 형태로 통일 — 할당 변수와 조건 검사 변수가 **같은 이름**이어야 한다):
```bash
SKILL_PATH=$(get_codex_skill_path "architect" "$FZ_PLUGIN_ROOT")
if [ -n "$SKILL_PATH" ]; then SKILL_PROMPT="$(cat "$SKILL_PATH")"
else SKILL_PROMPT="프로젝트 CLAUDE.md를 읽고 아키텍처/가이드라인을 파악한 후 검증하라."; fi
```

⛔ **`setup-codex-skills.sh`는 dead가 아니라 load-bearing이다** — Tier 2a를 성립시키는 심볼릭을 만드는 유일한 수단이다. 미실행 시 Tier 2b(번들 경로)로 내려가고, `PLUGIN_ROOT` 미전달이면 Tier 3로 폴백한다.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-codex | 검증 게이트 + `get_codex_skill_path()` 3-Tier 디스커버리 |
| /fz | 파이프라인 검증 게이트 자동 삽입 |
| modules/lead-reasoning.md | Implication Scan + origin-equivalence 추론 원칙 |
| modules/system-reminders.md | Instruction fade-out 대응 트리거 정책 |

## Codex 검증 결과 보존 정책

> 1M context 활용: 요약 + 원본 분리 (Progressive Disclosure)

- **ASD 활성**: `verify-result.md` (요약 3K, Hydration 대상) + `verify-result-full.md` (원본, drill-down용)
- **비ASD**: Serena checkpoint 요약만 (기존 동작)
- 다음 Phase 스킬은 `verify-result.md` 요약을 Read. 상세 확인 시 `-full.md` drill-down.

---

## Implication Scan 게이트

> 참조: `modules/lead-reasoning.md` — 추론 원칙, 카테고리 분류, 자문 체크리스트, Register 형식

### 트리거

- **1차**: 제거/삭제/이동/이관/마이그레이션/리팩토링/DI변경/revert
- **2차**: 프로토콜/access control/init·signature/모듈경계 변경
- **상시**: Q-OBSERVE (모든 코드 변경에서 경량 스캔)

### 파이프라인 위치

```
planning 후 → [implication-map] → stress-test → codex verify
code-changes 후 → build → [implication-scan] → codex check
```

### 절차

1. `lead-reasoning.md` 자문 체크리스트 실행 (Q-WHY/Q-COMPLETE/Q-EFFECT)
2. `find_referencing_symbols` → 변경 심볼의 참조자 중 "이 변경을 위해 추가된" 코드 식별
3. 실행 함의 발견 → [함의-A] 보고 + 사용자 확인
4. 관찰 함의 발견 → [함의-B] 기록 (최대 2건, 출력은 Gate 완료 시)

---

## Follow-up Re-audit Gate (Phase B1/B2 활성 시)

> 트리거: 과거 판단 아티팩트 (`follow-up-tasks.md`, `codex-review*.md`, `plan-v*.md`) 인용 시 (T7 트리거 연계)

### 절차

1. 해당 아티팩트 파일 현재 시점 Read (내용 변경 여부 diff 확인)
2. 변경 있음 → 재실측 후 최신 상태 기준 판정 (`git show`/`Read`/`grep` 실측)
3. 변경 없음 → `[verified: 재확인 YYYY-MM-DD]` 태그 부착
4. 재실측 불가 시 → `[아카이브: 재실측 불가, 작성 시점 YYYY-MM-DD]` 태그 + 보고

### 외부 memory 경로 정책 (단일 변수)

`memory/feedback_*.md` 류 외부 아티팩트 참조 시 `${CLAUDE_PROJECT_DIR}/memory/...` 변수형 절대 경로만 허용. glob (`*`) 사용 금지.

```
✅ ${CLAUDE_PROJECT_DIR}/memory/<교훈>.md
❌ ~/.claude/projects/*/memory/feedback_*.md  (glob 사용)
❌ memory/<교훈>.md  (상대 경로)
```

참조: `${CLAUDE_PROJECT_DIR}/memory/<교훈>.md` (Follow-up 재감사 교훈)

---

## origin-equivalence 게이트 (revert 전용)

> 트리거: "되돌리기", "revert", "원상복구", "undo", "롤백"

⛔ 되돌릴 대상 = "키워드"가 아닌 "원본 상태 전체"

1. 원본 커밋/상태 식별 (`git show {commit}^` 또는 기준 파일)
2. 범위 = 대상 커밋이 추가한 모든 변경 (상태 복원)
3. 완료 기준: 원본과의 동등성 확인

체크리스트:
- [ ] 원본 상태를 정확히 식별했는가?
- [ ] 키워드 기반이 아닌 상태 기반으로 범위 정의했는가?
- [ ] 원본과의 동등성(origin-equivalence) 확인했는가?

---

## 외부 피드백 검증 (External Feedback Gate)

> 하네스 원칙 4 적용: Generator≠Evaluator — 외부 피드백에 결정론적 검증 삽입

트리거: CodeRabbit, Codex, 팀원이 "파라미터 누락/타입 불일치/동작 변경/컨벤션·로컬라이즈·규칙 적용" 지적 시
⛔ diff만 보고 동의/반박 금지.

절차:
1. Read(해당 함수 시그니처) — 오버로드 구분 포함
2. 기존 동일 패턴(이전 PR, 같은 시리즈 이전 커밋) 대조
3. 판정: valid / invalid / needs-investigation + 근거 1줄

**Why:** OBS-01 세션에서 CodeRabbit이 "includeGradeCode: false 누락" 지적 → diff만 보고 수긍 → 실제로 LegacyResponse 오버로드에 해당 파라미터가 존재하지 않았음. 같은 세션에서 2건 발생.

---

## 런타임 동작 주장 검증 (Runtime Claim Gate) [관찰 모드]

> 하네스 NLAH-A: 비결정론적 추론 → 결정론적 어댑터(Bash) 교체

트리거: "~는 안전하다", "~로 변환된다", "타입 캐스팅이 ~" 등 런타임 동작 단정
조건: Swift 타입 시스템, Foundation API 동작, NSNumber 브리징 등 저수준 주장

절차:
1. 가능하면 Bash Swift 스크립트로 실제 실행하여 확인
2. 실행 불가능하면 → "미검증 (추론)" 표기 후 사용자에게 고지

> [관찰 모드]: 단일 사건(OBS-01 castToSendable)에서 도출. 하네스 과적합 방지 원칙에 따라 2건+ 재발 시 lead-reasoning.md로 강화.

**Why:** castToSendable의 Bool/Int 변환 안전성을 직관으로 "안전하다" 판단 → 취소 → Bash 테스트로 위험 확인. 실행 검증이 있었으면 1번에 끝났음.

---

## SOLO 모드 검증 게이트 요약

> 하네스 원칙 4 + Gap G-R1: SOLO에서도 **결정론적 도구 호출**로 최소 Generator≠Evaluator 분리

SOLO 모드에서는 에이전트 스폰/Codex 교차 검증 없이, 결정론적 도구만으로 검증한다.

| 상황 | 검증 방법 | 참조 |
|------|----------|------|
| 외부 피드백 판정 | ⛔ Read(함수 시그니처) + 패턴 대조 필수 | § External Feedback Gate |
| 런타임 동작 주장 | Bash 실행 가능하면 실행, 불가면 "미검증" 표기 | § Runtime Claim Gate [관찰 모드] |
| 3+ 파일 변경 후 자기 평가 | `/sc:reflect` 자동 트리거 | fz-code sc: 테이블 |
| 시그니처 변경 | `find_referencing_symbols` → conformance 확인 | 검증 유형별 전략 테이블: protocol conformance |
| "전체/모든" 키워드 분석 | ⛔ Coverage Gate: 단위 U 확정 → 전체 `N_U`, 검사 M, M/`N_U` 비율 보고 | § Coverage Gate |
| 결론 보고 전 | Q-SCOPE + Q-COVERAGE 자문 의무. "분석하지 않은 영역" 명시 | lead-reasoning.md §3 |

⛔ SOLO에서 **하지 않는 것** (AP1 과도한 구조화 방지):
- Codex 교차 검증 (TEAM 전용)
- 에이전트 스폰 (TEAM 전용)
- stress-test Q1-Q6 (fz-plan TEAM 전용)
- 주관적 평가 분리가 필요하면 → TEAM 모드 전환 제안

---

## Coverage Gate (문서/파일 분석 전수 보장)

> 트리거: 사용자 요청에 "전체", "모든", "생태계", "전수" 키워드 포함 시 — **또는 요청 어휘와 무관하게 산출물(보고)이 전수/카운트/부정 주장("~뿐", "N곳", "N개", "나머지는", "전부")을 생성할 때** (요청 어휘만 보면 "확인해줘"형 light 요청의 전수 산출물을 놓침)
> 본 트리거 정의가 **canonical** — Q-COVERAGE(lead-reasoning.md §3)·fz-search/fz-discover Gate·T8(system-reminders.md)은 이를 미러. 어휘 변경 시 4곳 동기화.
> 근거: 2026-04-16 세션에서 모델이 95개 중 25개만 읽고 "완료" 보고 / 2026-06-12 전수 주장 오판 — `rg|head -5` 잘린 출력 "2곳뿐" 단정 4턴 생존 (실제 11곳)

### 절차

0. **커버리지 단위 확정**: 조사 전에 **전수 주장의 대상 단위 U**(file / section / rule / usage-site / parameter)를 정하고, U의 전체 목록과 전체 수 `N_U`를 수집한다. ⛔ 결과 건수(예: "위반 0건")를 커버리지 단위로 삼지 않는다 — 단위는 전수 주장이 **겨누는 대상**이지 그 대상을 세어 나온 결과가 아니다. 파일 전수 주장은 `file`, 절 전수 주장은 `section`을 쓴다.
1. **대상 파일 목록**: `Glob` 또는 `find` → 읽어야 할 **대상 파일 수 F** 수집. F는 실행 비용 지표이며 `N_U`와 별개다 — U=section이면 파일 하나에 U가 여럿 들어간다.
2. **전략 선택** (F 기준):
   - F ≤ 30 → 직접 전수 읽기
   - 30 < F ≤ 100 → 병렬 에이전트 분배 (전수)
   - F > 100 → AskUserQuestion ("100개+ 파일. 전수/범위 한정 중 선택?")
3. **완료 보고에 커버리지 명시** (단위 U 기준):
   ```
   단위: {U}
   Coverage: {검사한 U 수}/{N_U} = {비율}%
   누락 {U}: {목록 또는 "없음"}
   ```
4. 비율 < 100% → 누락 사유 명시 필수
5. **명령 출력 커버리지** (파일 분석 없는 순수 grep/rg 조사는 1-4항 대신 본 항부터 적용): 근거 수집 명령에 `head`/`tail` 잘림 금지. 출력이 길면 자르지 말고 `wc -l` 총계 병기 + "잘림" 명시.
6. **집계 검산식**: 분할 합계 주장(부분합 존재)은 검산식 명시·일치 의무 (예: `80 = 58 + 6 + 14 + 2`). 단순 단일 카운트는 head 없는 재실행(`rg X | wc -l`)으로 대체. 정규식/쿼리 불완전로 인한 가짜 교차확인도 검산 불일치로 탐지 — T8 리마인더 범위 밖, 본 항이 담당.
7. **분류 완전성** *[candidate: 1 session evidence]* (scope 판정이 산출물에 포함될 때 — sweep/discovery가 항목을 in_scope/out_of_scope/migrated 분류): 기각(out_of_scope/migrated) 항목 수 명시 + 무작위 N=min(3, 전체기각수) 표본 adversarial 재검(반례 탐색 → 발견 시 재분류). **분류 단위 = 사용 site(call/usage site), file 전체 아님** — 혼재 파일(in-scope+out-scope site 공존) 허용. (BAD: 파일 통째 out 판정 → 내부 in-scope site 폐기 / GOOD: site별 분리 판정). [evidence:1 OBS-15, active:5세션(트랙 A — promotion-ledger.md canonical) — `project_fz_harness_holes.md`]

```
BAD:  rg X | head -5 → "사용처 2곳뿐"   (잘린 5줄을 전수로 단정)
GOOD: rg X | wc -l → 11 → 잘림 없이 11줄 직접 확인 후 "사용처 11곳"
```

### Gate 조건
- [ ] 커버리지 단위 U 확정? (결과 건수를 단위로 삼지 않았는가)
- [ ] 단위 U 전수 목록 생성? (`N_U`)
- [ ] 전략 선택 (F 기준 — 직접/병렬/범위 확인)?
- [ ] 완료 보고에 **단위 U** + Coverage 비율 명시?
- [ ] 근거 명령 출력 잘림 없음? (또는 head 없이 `wc -l` 병기)
- [ ] 분할 합계 주장이면 검산식 일치? (단일 카운트는 N/A)
- [ ] scope 판정 산출물이면 기각 항목 수 명시 + 표본(≤3) adversarial 재검 + 분류 단위=site? *[candidate: 1 session evidence]*

> 상시 경량 self-check Q-COVERAGE(lead-reasoning.md §3)는 본 Gate의 미러 — 어휘 변경 시 본 canonical과 동기화.

---

## Negative-Result Gate (0건·부재 주장의 도구 유효성)

> ⛔ **`system-reminders.md` T8이 위임한 수신처다.** T8은 *"정규식 불완전(가짜 교차확인)은 Coverage Gate 검산식 담당"*이라 명시하는데 그 구현이 없었다(2026-08-09 신설). Coverage Gate가 **범위**(N개 중 M개)를 보고, 본 Gate가 **도구 유효성**을 본다.
> 근거: 단일 세션에서 12 인스턴스 실측 — 그중 *0건 자체를 의심해서* 잡은 건 **0건**이다. 전부 외부 지적·우연한 재측정·도구 에러메시지로 발견됐다. 즉 자기 점검으로는 잡히지 않는다(`guides/harness-engineering.md` H1 자문 NO).

**발동**: "0건" · "부재" · "전부" · "~뿐" 을 **산출물의 결론**으로 쓸 때.
⛔ **면제**: 탐색 중 중간 grep. (범위를 좁히지 않으면 모든 grep에 붙어 IFScale 과부하가 된다 — Coverage Gate의 "산출물 기준" 트리거 규약과 동형)

### 3요소

**1. Positive control** — 동일 명령이 **반드시 매칭되는 케이스**에서 non-zero를 내는지 먼저 확인한다.
> 0건은 「대상 부재」와 「도구 고장」을 구별하지 못한다. 도구가 작동함을 먼저 증명하라.

**2. 신호 보존** — 측정 명령을 `>/dev/null 2>&1`로 감싸지 않고 **exit code를 판정에 포함**한다.
> 스크립트의 fail-closed 거부가 0건으로 오독된다. 선례: `scripts/lint_doc_freshness.py`는 잘못된 루트에서 `⛔ 플러그인 루트가 아님`을 stderr로 내고 **exit 2**로 거부한다 — stderr를 버리면 이 거부가 "0건"이 된다.

**3. 귀속 라벨** — 다중 대상 스캔 출력에 **대상 식별자**를 포함한다.
> 라벨 없는 집계는 잘못된 사이트에 귀속된다.

### 알려진 함정 (실측된 것만)

| 함정 | 증상 | 기계 검출 |
|---|---|---|
| `grep -E` 안의 `\|` | ERE에서 alternation 아님 → **항상 0건**. ⚠️ BRE(`grep` 무옵션)의 `\|`는 정당 | `lint_contracts.py` **#N4** |
| `git grep -E` 안의 `\b` | git 의 기본 정규식 엔진은 GNU grep 처럼 `\b`를 처리하지 않는다 → **에러·경고 없이 0건**. 단어 경계가 필요하면 plain 패턴으로 뽑고 눈으로 거른다 | — |
| 파일명으로 심볼 grep | `AdaptiveSheetOptions.swift` 의 *파일명*으로 타입을 찾으면 0건이 **보장**된다. 삭제 대상이 파일명인지 타입명인지 먼저 구분하고, `git show <ref>:<file> \| grep -E '^\s*(public\|open)'` 로 선언 심볼을 추출한다 | — |
| zsh unquoted `--include=*.md` | 글로빙되어 `no matches found` → 거짓 0건 | — (셸 세션) |
| macOS `timeout` 부재 | 측정 도구 부재를 대상 실패로 오독 | — |
| `awk '/A/,/B/'` 범위 | 끝 헤더에서 멈춰 **구간을 못 읽음** | — |
| 한글/영문 표기 누락 정규식 | `Gate`만 찾고 `게이트`를 놓침 | — |
| `>/dev/null 2>&1` + exit 무시 | fail-closed 거부를 0건으로 오독 | **#N5** |
| CWD 의존 상대경로 | 다른 디렉토리에서 다른 결과 | **#N6** |

### Gate 조건

- [ ] "0건/부재/전부"가 산출물 결론에 있는가? (없으면 N/A)
- [ ] 있으면 **positive control** 수행 + 결과 명시?
- [ ] 측정 명령의 **exit code**를 판정에 포함? (`2`는 PASS도 SKIP도 아님)
- [ ] 다중 대상 스캔이면 출력에 **대상 라벨** 포함?
- [ ] 위 함정 표의 해당 항목을 점검? (기계 검출 가능분은 `lint_contracts.py`가 담당)

> ⛔ **SKIP ≠ PASS**: 스크립트가 판정하지 않은 항목(THRESHOLD·SEMANTIC)은 별도 판정하고 그 사실을 보고에 남긴다.

---

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 모듈이므로 줄 수 제한 없음
