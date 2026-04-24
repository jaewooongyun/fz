# fz v3.0 Release Notes

**Release Date**: 2026-03-30
**Codename**: 3-Model Triad

---

## Breaking Changes

### 1. fz-discover: 패러다임 전환 (Constraint Discovery → Landscape Exploration)

**Before**: discover가 "제약 매트릭스"를 만들어 plan에 전달 → plan은 제약 안에서만 설계
**After**: discover가 "풍경(landscape)"을 탐색하고 경로 비교표를 plan에 전달 → plan이 경로를 선택

- `provides` 변경: `[constraint-matrix, refined-requirements, decision-rationale]` → `[landscape-map, trade-off-table, open-questions]`
- Phase 2: "Iterative Constraint Discovery" → "Landscape Exploration"
- Phase 3: "Convergence" → "Path Mapping" (결론을 내리지 않음)
- 조건 불변성 구분: 🔒 hard constraint (기술적 불가능) vs 🔓 soft preference (관성/비용)
- **어떤 경로도 탈락시키지 않음** — "비용 X를 감수하면 가능"으로 유지

**Migration**: fz-plan이 discover 산출물을 "전제"가 아닌 "참고"로 해석하도록 변경됨. 🔒만 제약으로 채택, 🔓는 비용 비교 대상.

### 2. 모델 전략: 2-Tier → 3-Tier

**Before**: opus(핵심) + sonnet(나머지) + Codex(보조)
**After**: opus(핵심) + sonnet(나머지) + external(검증): Codex(GPT) + Gemini

### 3. fz-plan 팀 구성: 4-Agent → 6-Agent

**Before**: plan-structure(O) + review-arch(S) + review-direction(S) + [memory-curator]
**After**: plan-structure(O) + plan-impact(S) + review-arch(S) + review-direction(S) + [memory-curator] + Codex verify + Gemini challenge

---

## New Features

### 3-Model Triad Architecture

연구 기반 멀티모델 검증 체계. 각 모델이 다른 역할을 수행합니다.

| 모델 | 역할 | 질문 |
|------|------|------|
| Claude (Opus/Sonnet) | Primary Creator + Orchestrator | "어떻게 만들까?" |
| GPT (Codex CLI 0.111.0) | Independent Reviewer | "빠진 건 없나?" |
| Gemini (CLI 0.35.3) | Devil's Advocate | "실패할 가장 큰 위험은?" |

**근거**:
- [X-MAS (arxiv 2505.16997)](https://arxiv.org/abs/2505.16997) — 이종 모델 조합 시 최대 47% 성능 향상
- [ICLR 2025 MAD](https://arxiv.org/abs/2502.08788) — 같은 모델 N개는 단일 모델 대비 비효과적
- [Anthropic: Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) — 3-4 specialized agents max

### Selective Consensus

Gemini는 항상 호출하지 않습니다. 비용 최적화를 위해 불일치/의심 시에만 호출:

| 트리거 | 프로바이더 |
|--------|-----------|
| code-changes (TEAM, 기본) | Codex만 |
| code-changes + Major 불일치 | Codex + Gemini |
| planning (--deep) | Codex + Gemini 병렬 |
| review + Reflection < 80% | Codex + Gemini |

### fz-gemini 스킬 (신규)

Gemini CLI 전용 독립 스킬. fz-codex와 분리하여 각 모델이 자기 스킬을 가짐.

```bash
/fz-gemini review                    # Gemini로 코드 리뷰
/fz-gemini verify "계획 검증"         # Gemini로 계획 검증
/fz-gemini challenge "설계 도전"      # Devil's Advocate 모드
```

### 6-Agent Plan Team

fz-plan TEAM 모드에서 6개 차별화된 렌즈가 병렬로 분석:

| 에이전트 | 렌즈 | 핵심 질문 |
|---------|------|----------|
| plan-structure (Opus) | 설계 + 분해 | "어떻게 나누고 만들 것인가?" |
| plan-impact (Sonnet) | 영향 범위 | "이 변경이 어디까지 퍼지는가?" |
| review-arch (Sonnet) | 아키텍처 일관성 | "기존 패턴/규칙과 맞는가?" |
| review-direction (Sonnet) | 방향성 도전 | "근본적으로 다른 접근은?" |
| Codex verify (GPT) | 독립 검증 | "이 계획에 빠진 것은?" |
| Gemini challenge | Devil's Advocate | "이 계획이 실패할 가장 큰 위험은?" |

통신 패턴: Parallel Analysis + Cross-Feedback
- Round 1: 4개 에이전트 + 2개 외부 모델이 동시 독립 분석
- Round 2: 결과를 plan-structure에 교차 피드백
- Round 0.5: 최종 합의표 작성

### plan-impact 에이전트 강화 (Impact Scanner)

기존의 영향 범위 추적에서 Exhaustive Impact Scan(a~f) 전담으로 역할 확대:
- a. 텍스트 전수 검색 (심볼 기반 누락 보완)
- b. 런타임 도달성 검증 (active/latent 구분)
- c. 사이드이펙트/순서 분석
- d. Dead code 감지
- e. 소비자 코드 품질 스캔 (모듈화 시)
- f. Import Symbol Inventory (import 제거 시)

### Native Commands 활성화

| 커맨드 | v2 | v3 |
|--------|-----|-----|
| /simplify | 선택적 게이트 | **조건부 필수**: 새 함수 3개+, 100줄+, 3회 빌드 실패 시 자동 |
| /batch | --batch 플래그만 | 독립 Step 3개+ 감지 시 **자동 제안** |
| LOOP | 암묵적 래더 | **스킬별 명시 에스컬레이션**: 1회→직접수정, 2회→troubleshoot, 3회→AskUser |

### Hooks 기반 물리적 강제

프롬프트 규칙(Claude가 스킵 가능)을 Hook 메커니즘(물리적 차단)으로 전환:

| Hook | 트리거 | 효과 |
|------|--------|------|
| PreToolUse(Bash) | `git commit` 감지 | 차단 + "/gc 스킬 사용" 안내 |
| PostToolUse(Write) | Sources/iOS/*.swift 생성 | platformFilter 자동 검사 |

### consensus-verify 파이프라인 (신규 #19)

```bash
/fz "3모델 합의 검증해줘"
/fz "멀티모델로 확인"
```
→ fz-codex + fz-gemini 병렬 실행 → Lead가 합의표 작성

---

## Improvements

### fz-fix: 4-Phase 디버깅

| v2 | v3 |
|----|-----|
| Step 1: 탐색+분석 (한 덩어리) | Step 1a: Reproduce (재현 조건 먼저) |
| | Step 1b: Isolate (최소 범위로 좁힘) |
| | Step 1c: Root-Cause (5 Whys, 증상 아닌 원인) |
| | **Step 1c 완료 전 코드 수정 금지** |
| Step 4: (선택) 리뷰 | Step 4: Verify Fix (**필수**, 재현 경로 재확인) |

### fz-code: Step 완료 조건 명시

각 Step 완료 시 다음 Step 진입 전 확인:
- 빌드 성공
- 시그니처 변경 시: conformance 보존 확인
- 타입 변경 시: caller 1개 샘플 확인
- /simplify 자동 트리거 조건 충족 시 실행

### fz-codex: --consensus 옵션

```bash
/fz-codex review --consensus    # Codex + Gemini + Claude 3모델 비교
```

### De-overfit (과적합 해소)

- 반성 출처 마커 제거 (규칙 자체는 유지, `(반성 N차 — 누락 방지)` 주석만 삭제)
- Exhaustive Impact Scan을 plan-impact 에이전트에 위임 명시
- Hook으로 이전한 규칙의 SKILL.md 삭제 가능

---

## Stats

| 지표 | v2.5 | v3.0 |
|------|------|------|
| Skills | 21 | **22** (+fz-gemini) |
| Agents | 14 | 14 (plan-impact 강화) |
| Modules | 17 | 17 |
| Pipelines | 18 | **19** (+consensus-verify) |
| Models | 2 (Claude + GPT) | **3** (+ Gemini) |
| Plan Team Agents | 4 | **6** (+plan-impact, +Gemini) |
| Plan Team Lenses | 3 | **6** |
| Files Changed | — | 15 |
| Lines Changed | — | +457 / -182 |

---

## External Dependencies Added

| 도구 | 버전 | 설치 | 용도 |
|------|------|------|------|
| Gemini CLI | 0.35.3 | `npm i -g @google/gemini-cli` | Devil's Advocate, 장문 분석, Tiebreaker |

인증: OAuth GCA (`GOOGLE_GENAI_USE_GCA=true`)

---

## Research References

| 논문/문서 | 핵심 발견 | 적용 |
|----------|----------|------|
| [X-MAS (arxiv 2505.16997)](https://arxiv.org/abs/2505.16997) | 이종 모델 조합 최대 47% 향상 | 3-Model Triad |
| [ICLR 2025 MAD](https://arxiv.org/abs/2502.08788) | 같은 모델 N개는 비효과적 | 이종 모델 필수 |
| [MAST (arxiv 2503.13657)](https://arxiv.org/abs/2503.13657) | 통신 품질 > 에이전트 수 | 2.5-Turn 유지 |
| [Anthropic Research System](https://www.anthropic.com/engineering/multi-agent-research-system) | 3-4 agents 최적 | 6-Agent (4 Claude + 2 External) |
| [Claude Code Sub-Agents](https://code.claude.com/docs/en/sub-agents) | 커뮤니티 3-4 max | 범위 내 설계 |

---

## Migration Guide

### v2.5 → v3.0

1. **Gemini CLI 설치**: `npm i -g @google/gemini-cli` + `GOOGLE_GENAI_USE_GCA=true gemini` (OAuth 인증)
2. **fz-discover 산출물 변경**: `constraint-matrix` → `landscape-map`. 기존 ASD 폴더의 discover 산출물은 호환되지 않음 (새 세션에서 재탐색 권장)
3. **settings.json Hooks**: git commit 차단 + platformFilter 검사 hook 자동 적용됨
4. **fz-codex description 변경**: Gemini 관련 키워드가 fz-gemini로 이동. "gemini"로 호출 시 fz-gemini이 매칭됨
