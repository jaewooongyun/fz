---
name: fz
description: >-
  유니버셜 오케스트레이터. 자연어 → 스킬 파이프라인 자동 구성 + 복잡도 기반 팀 자동 편성 + 모델 승격.
  Use for ANY complex multi-step task that requires combining multiple skills,
  or when unsure which specific skill to use.
  Examples: "계획부터 PR까지", "버그 찾아서 고쳐줘", "리뷰하고 커밋해줘".
user-invocable: true
argument-hint: >-
  [자연어 요청] [--solo] [--team] [--deep]
  예: "버그 찾아줘", "구현하고 리뷰" --team, "PR 리뷰" --deep
allowed-tools: >-
  mcp__serena__find_file,
  mcp__serena__list_dir,
  mcp__serena__write_memory,
  mcp__serena__read_memory,
  mcp__serena__edit_memory,
  mcp__serena__delete_memory,
  mcp__serena__list_memories,
  mcp__sequential-thinking__sequentialthinking,
  Read, Grep, Glob
composable: false
provides: []
needs: []
intent-triggers: []
model-strategy:
  main: opus
  verifier: null
---

# /fz - 유니버셜 오케스트레이터 (v3)

> **행동 원칙**: 자연어 요청을 분석하여 복잡도 기반으로 최적의 스킬 파이프라인 + 팀 구성 + 모델 배정을 자동 결정하고, 사용자 승인 후 실행한다.

## 개요

> Phase 0 (Session) → Phase 1 (Intent) → Phase 2 (Complexity) → Phase 3 (Pipeline+Team) → Phase 4 (Confirm) → Phase 5 (Execute)

- **6-Phase 오케스트레이션**: 세션 부트스트랩 → 의도 분석 → 복잡도 평가 → 파이프라인+팀 결정 → 확인 → 실행
- **사전 정의 파이프라인** (19개): 자주 쓰는 조합을 즉시 매칭 (빠른 경로)
- **동적 파이프라인**: `provides`/`needs` 그래프 기반 자동 구성 (폴백)
- **2-모드 시스템**: SOLO (Lead 단독) / TEAM (Lead + Primary(O) + N×Sonnet)
- **모델 승격**: 핵심 생산자(Primary Worker)를 opus로 자동 승격
- **2-Tier 모델**: opus(핵심) + sonnet(나머지). haiku 사용하지 않음
- **Codex 필수 참여**: 모든 TEAM 스킬에 Codex CLI 포함 → cross-model 상호검증
- **교차 검증 자동 삽입**: 코드/계획 생산 파이프라인에 검증 게이트 주입
- **개별 스킬 팀 강화**: 각 스킬(plan/code/review/search/fix)이 TeamCreate + SendMessage 기반 다관점 협업 + Codex 활용

## 사용 시점

```bash
/fz "ContentDetail 크래시 버그 찾아줘"         # → bug-hunt (SOLO)
/fz "새 기능 계획 세워줘" --team               # → plan-to-code (TEAM)
/fz "코드 리뷰하고 커밋해줘"                   # → review-to-ship (TEAM)
/fz "기능 구현하고 리뷰" --deep                # → code-to-review (TEAM+deep)
/fz "타임아웃 30초로 변경" --solo              # → quick-fix (강제 SOLO)
/fz "이걸 어떻게 구현하면 좋을까?"              # → discover (SOLO)
/fz "모듈 12개 용어 통일" --batch              # → BATCH (worktree 병렬)
/fz "빌드 실패 반복" --loop                    # → LOOP (자동 반복)
/fz "스킬 트리거 최적화해줘"                    # → skill-optimize (SOLO)
/fz "드리프트 체크해줘"                        # → drift-check (SOLO, fz-codex drift)
/fz "독립 플랜 만들어줘"                       # → plan-parallel (SOLO, fz-codex plan)
/fz "전체 봐줘"                               # → Medium confidence → AskUserQuestion 먼저
/fz "안됨"                                    # → Low confidence → AskUserQuestion 먼저
```

### 옵션

| 옵션 | 설명 |
|------|------|
| `--solo` | Lead 단독 실행 강제 |
| `--team` | 팀 에이전트 모드 강제 (opus Primary + N×sonnet) |
| `--deep` | --team + 교차 검증 강화 |
| `--batch` | worktree 병렬 실행 강제 (/batch) |
| `--loop` | 자동 반복 강제 (/ralph-loop) |

---

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/complexity.md | 5차원 복잡도 → 모드 결정 |
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 + 정적 팀 패턴 (TeamCreate + 3-Phase 통신 + 스킬별 패턴) |
| modules/team-registry.md | 에이전트 + 모델 자동 결정 |
| modules/cross-validation.md | 검증 게이트 자동 삽입 |
| modules/context-artifacts.md | ASD 폴더 기반 compact recovery + 산출물 전달 |
| modules/execution-modes.md | BATCH/LOOP/SIMPLIFY 실행 모드 |
| modules/governance.md | kill-switch |
| modules/pipelines.md | 19개 사전 정의 파이프라인 (트리거+체인+게이트+TEAM) |
| modules/memory-guide.md | L1 auto memory 관리 정책 + 태깅 규칙 |
| modules/plugin-refs.md | SwiftUI + Concurrency 플러그인 참조 가이드 |

---

## Phase 0: Session Bootstrap (SuperClaude 연계)

파이프라인 시작 전 세션 컨텍스트를 준비합니다. **파이프라인당 1회만 실행.**

### 절차

1. **이전 세션 복원** (새 세션일 때만):
   - `/sc:load` → Serena 메모리 + SC 체크포인트 복원
   - 조건: 이전 세션에서 `/sc:save`된 데이터가 있을 때

2. **프로젝트 인덱스 확인**:
   - `PROJECT_INDEX.md` 존재 확인 → 있으면 읽기 (3K 토큰)
   - 없고 탐색 파이프라인이면 → `/sc:index-repo` 실행 제안
   - 조건: explore, explore-plan, bug-hunt 파이프라인에서만

3. **Work Dir 초기화** (6+ 스텝 또는 context-heavy 스킬 포함 시):
   - Ticket ID 해석 (참조: `modules/context-artifacts.md`)
   - ASD 패턴 → `{CWD}/ASD-xxxx/` 자동 생성
   - 패턴 없음 → AskUserQuestion(저장 여부) → 예: `{CWD}/NOTASK-{YYYYMMDD}/` / 아니오: Serena fallback
   - `fz:session:current`에 `work_dir` 경로 저장
   - context-heavy 스킬: discover, search --deep, peer-review <!-- 기존: 4+ 스텝 -->

3b. **이전 중단 세션 감지**:
   - `read_memory("fz:checkpoint:essential")` 확인
   - 존재 시: "이전 중단된 세션이 있습니다. 복원하시겠습니까?" AskUserQuestion
     - 예 → ASD 폴더의 `index.md` Read → Active Phase + Essential Context 복원 ("Starting fresh + filesystem discovery" 패턴)
     - 아니오 → `delete_memory("fz:checkpoint:essential")` 후 새 세션 시작
   - **essential 미존재 시 폴백**: `list_memories("fz:checkpoint:*")` → phase checkpoint 존재 여부 확인
     - 존재 시: 최신 checkpoint 키를 시간순 정렬 → 마지막 키 read → 해당 phase부터 복원 제안
     - 미존재 시: 완전 새 세션 (복원 대상 없음)

4. **교훈 사전 로드** (선택):
   - SOLO: Lead가 직접 topic file 스캔 (`modules/memory-guide.md` 태깅 기반)
   - TEAM: memory-curator 에이전트 **모든 TEAM 모드**에서 포함
   - 조건: plan/code/review 파이프라인에서만

5. **핵심 모듈 선로드** (6+ 스텝 또는 TEAM):
   - `Read(modules/context-artifacts.md)` — Artifact Budget Table + 산출물 프로토콜
   - `Read(modules/memory-policy.md)` — 메모리 키 네이밍
### Gate 0: Session Ready
- [ ] 새 세션이면 이전 컨텍스트 복원 시도?
- [ ] 탐색 파이프라인이면 인덱스 확인?
- [ ] 6+ 스텝 또는 context-heavy이면 ASD 폴더 초기화?
- [ ] 6+ 스텝 또는 TEAM이면 핵심 모듈 선로드?

> **토큰 비용**: ~3,000-5,000 (세션당 1회). 개별 스킬마다 실행하지 않음.

---

## Phase 1: Intent Analysis

사용자 자연어에서 의도를 추출하고, 후보 스킬을 선별합니다.

### 절차

1. **키워드 추출**: 자연어에서 핵심 키워드 + 추가 신호 분리
2. **intent-triggers 매칭**: 각 스킬 YAML의 `intent-triggers` 정규식과 대조

   ```
   스킬 YAML 위치: skills/fz-*/SKILL.md
   매칭 방법: 각 스킬의 intent-triggers 정규식을 순회하며 매칭
   ```

3. **후보 스킬 목록 생성**: 매칭된 스킬 + confidence 점수
4. **추가 신호 추출**: 복잡도 평가를 위한 부가 정보

> 스킬별 intent-triggers + 구어체 보강 패턴 + Confidence 판정 규칙: `modules/intent-registry.md`

### 추가 신호 추출

| 신호 | 추출 방법 | 용도 |
|------|----------|------|
| `scope_keywords` | "한 파일", "전체", "시스템" 등 | Complexity Scope 차원 |
| `quality_keywords` | "정확하게", "꼼꼼히", "deep" | Complexity Verification 차원 |
| `target_count` | 언급된 대상 파일/모듈 수 | Complexity Scope 차원 |
| `cross_concern` | 여러 관심사가 교차하는지 | Complexity Risk 차원 |
| `override_flags` | --solo, --team, --deep | 모드 Override |

### Gate 1: Intent Resolved
- [ ] 1개 이상의 스킬이 매칭되었는가?
- [ ] Confidence 판정 완료? (Medium/Low이면 AskUserQuestion 실행했는가?)
- [ ] 동점 파이프라인 있으면 사용자 선택 완료?
- [ ] 매칭된 스킬 간 의존성이 파악되었는가?
- [ ] 추가 신호가 추출되었는가?

---

## Phase 2: Complexity Assessment

> 참조: `modules/complexity.md`

매칭된 의도와 추가 신호를 기반으로 5차원 복잡도를 평가하고 실행 모드를 결정합니다.

### 절차

1. **5차원 점수 계산**: Scope, Depth, Risk, Novelty, Verification
2. **Override 플래그 처리**: --solo, --team, --deep, --batch, --loop
3. **모드 결정**: 점수합 → SOLO(0-3) / TEAM(4+)
4. **실행 모드 결정**: STANDARD / BATCH / LOOP (참조: modules/execution-modes.md)

| 합산 | 모드 | 실행 모드 | 실행 방식 |
|------|------|----------|----------|
| 0-3 | SOLO | STANDARD | Lead(O) 단독, 순차 실행 |
| 0-3 | SOLO | BATCH | worktree 격리 병렬 (--batch 또는 독립 3개+) |
| 4+ | TEAM | STANDARD | Lead(O) + Primary(O) + N×Sonnet |
| 4+ | TEAM | LOOP | 자동 반복 + 에스컬레이션 (--loop 또는 Gate 반복 예상) |

### Gate 2: Complexity Assessed
- [ ] 5차원 점수 계산 완료?
- [ ] Override 플래그 처리 완료?
- [ ] 모드 결정 완료?

---

## Phase 3: Pipeline + Team Resolution

### 3.1 파이프라인 해결

> 참조: `modules/pipelines.md` — 19개 사전 정의 파이프라인 (트리거 패턴 + 체인 + 게이트 + TEAM 구성)

의도 키워드와 사전 정의 파이프라인의 트리거를 대조하여 최적 매칭합니다.
매칭되지 않으면 3.2 동적 파이프라인으로 폴백.

### 3.2 동적 파이프라인 구성 (폴백)

사전 정의 파이프라인에 매칭되지 않으면 `provides`/`needs` 그래프로 자동 구성합니다.

```
알고리즘:
1. 의도 분석 → 최종 목표 스킬 결정
2. 해당 스킬의 needs 확인
3. needs를 provides하는 스킬 역추적 (재귀)
4. 토폴로지 정렬 → 선형 파이프라인
5. 끊어진 체인 → 스킬 자동 삽입 or AskUserQuestion
```

### 3.3 팀 구성 결정

> 참조: `modules/team-registry.md`

파이프라인과 모드를 기반으로 에이전트 + 모델을 자동 결정합니다.

```
1. 파이프라인 스텝 → 필요 에이전트 식별
2. Primary Worker 판별 → opus 승격
3. 나머지 에이전트 전부 sonnet으로 스폰 (제한 없음)
4. 정적 팀 패턴 매칭 → 일치 시 정적 사용
5. 미일치 시 동적 구성 적용
```

### 3.4 교차 검증 게이트 주입

> 참조: `modules/cross-validation.md`

파이프라인에 검증 게이트를 자동 삽입합니다.

```
planning 생산 전 → ✓ direction-challenge (review-direction, TEAM fz-plan Phase 0.5)
planning 생산 후 → ✓ stress-test(Q1-Q5) + ✓ codex verify (TEAM)
code-changes 생산 중 → ✓ friction-detect (매 Step, fz-code 내장)
code-changes 생산 후 → ✓ build + ✓ enforcement (리팩토링 시) + ✓ implication-scan (제거/리팩 시) + ✓ codex check (TEAM)
commit/pr 전 → ✓ codex check (TEAM)
```

> **direction-challenge**: review-direction 에이전트가 접근 방향 자체를 도전 (PROCEED/RECONSIDER/REDIRECT 판정). fz-plan TEAM Phase 0.5.
> **stress-test**: fz-plan의 설계 스트레스 테스트(다중성/소비자/복잡도이동/경계/접근경계).
> **friction-detect**: fz-code의 구현 마찰 감지(분기폭증/코드반복/소비자판별/workaround/잔존패턴).
> **enforcement**: Plan의 Anti-Pattern Constraints 기반 금지 패턴 Grep + Module Boundary 검증. 리팩토링 파이프라인에서만 삽입.

### Gate 3: Pipeline + Team Resolved
- [ ] 파이프라인 확정?
- [ ] 에이전트 + 모델 배정 완료?
- [ ] 검증 게이트 삽입 완료?

---

## Phase 4: User Confirmation

결정된 파이프라인, 팀 구성, 모델 배정을 시각화하고 사용자 승인을 받습니다.

### 시각화 형식

```markdown
## 파이프라인 제안

**요청**: "{사용자 원문}"
**의도**: {분석된 의도 요약}
**파이프라인**: `{파이프라인 이름}`
**모드**: TEAM (점수: {점수}/10)

| # | 스킬 | 역할 | 실행자 | 모델 |
|---|------|------|--------|------|
| 1 | /fz-code | 점진적 구현 | impl-correctness ★ | opus |
| 2 | ✓ build | 빌드 검증 | Lead | — |
| 3 | ✓ codex check | 교차 검증 | Lead | codex |
| 4 | /fz-review | 아키텍처 리뷰 | review-arch | sonnet |
| 5 | /fz-review | 품질 리뷰 | review-quality | sonnet |
| 6 | /fz-commit | 커밋 | Lead | opus |

**에이전트**: Lead(O) + impl-correctness(★O) + review-arch(S) + review-quality(S)
```

> ✓ 접두사: 자동 삽입된 검증 게이트. ★: Primary Worker (opus).

### AskUserQuestion 선택지

```
1. 이대로 실행 (Recommended)
2. 모드 변경 (TEAM ↔ SOLO)
3. 단계 추가/축소
4. 커스텀 구성
```

### 적극적 확인 원칙 (Step 8)

**파이프라인 제안 전 의도 재확인** — 다음 조건에서 파이프라인 제안 전에 먼저 묻는다:
- 요청 길이 < 10글자
- 동사 없음 (명사/키워드만)
- 애매한 동사 ("봐줘", "해줘" 등 대상 불명확)

**범위 확인** — TEAM 모드 + 5개+ Step 예상 시:
```
Q: "이 작업의 범위를 확인합니다"
옵션:
  1. 전체 파이프라인 ({N} Steps) 실행 (Recommended)
  2. 첫 번째 스텝만 먼저 실행
  3. 계획만 보여주고 각 Step 개별 승인
```

**중단 없이 자동 실행 금지 조건** (반드시 멈추고 질문):
- 코드 변경 범위가 예상보다 넓어질 때 (5개+ 파일 변경 감지)
- 파이프라인 외 추가 스킬이 필요할 때
- Gate 실패 시 (재시도/스킵/중단 반드시 선택)

### Gate 4: Pipeline Approved
- [ ] 파이프라인 + 팀 구성 시각화 출력 완료?
- [ ] 사용자가 승인했는가?
- [ ] 적극적 확인 원칙 적용 완료? (짧은 요청/범위 확인)

---

## Phase 5: Orchestrated Execution

승인된 파이프라인을 모드에 따라 실행합니다.

### 5.1 SOLO Execution (기존 v1 호환)

```
각 단계:
1. Read(skills/{스킬}/SKILL.md) → 해당 스킬의 지침 로드
2. 스킬 지침에 따라 실행 (도구 호출, MCP 사용 등)
3. 대화 컨텍스트에 산출물 축적 → 다음 단계가 자연 참조
4. Gate 체크 → 통과 시 다음 단계, 실패 시 중단/계속 선택
```

**컨텍스트 패싱**: 대화 기반 (기존 v1과 동일). 4스텝+ 시 /compact 안내.

### 5.2 TEAM Execution

> TEAM 모드에서 TeamCreate를 사용한다. standalone Task 단독 사용 시 에이전트 간 Peer-to-Peer 직접 통신이 불가능해 협업 가치가 사라진다.
> 참조: `modules/team-core.md` — 공통 실행 프로토콜 (3-Phase 통신) + `modules/patterns/` — 스킬별 패턴

TeamCreate의 핵심 가치는 **에이전트 간 Peer-to-Peer 직접 통신**이다.
Lead를 중계자로 쓰지 않는다. 에이전트들이 **만들면서 직접 토론**하여 고도화한다.
Lead는 퍼실리테이터 (모니터링 + 교착 해소 + 게이트 실행).

```
1. TeamCreate("{pipeline}-{feature}")
2. Task(에이전트 N명) — 피어 목록 + 통신 규칙 포함하여 전달
3. Collaborative Iteration (에이전트 간 직접 대화):
   Round 1: 초안 → 피어에게 직접 SendMessage로 공유
   Round 2: 피드백 → 피어에게 직접 반박/보완
   Round 3+: 합의까지 반복 (최대 3라운드)
4. 합의 → Lead 보고 → Lead 게이트 실행 (빌드/Codex)
5. 완료 → shutdown_request → TeamDelete
```

### 스킬별 통신 패턴

| 스킬 | 통신 패턴 | 핵심: 에이전트 간 직접 대화 |
|------|----------|--------------------------|
| fz-discover | Adversarial Constraint Discovery | plan-structure ↔ review-arch 만들고 부수며 제약 발견 |
| fz-plan | Collaborative Design | review-direction → plan-structure 방향 도전 (Phase 0.5) + plan-structure ↔ peers 만들면서 토론 |
| fz-code | Pair Programming | impl-correctness ↔ review-arch 구현 중 실시간 질문/검토 |
| fz-review | Live Review | review-arch ↔ review-quality 분석하면서 발견 공유 |
| fz-search --deep | Cross-Verify | search-symbolic ↔ search-pattern 발견 즉시 교차 확인 |
| fz-fix (복잡) | Pair Programming (경량) | impl-correctness ↔ Lead 수정/검증 |

### 개별 스킬 TEAM 모드 (핵심 패턴)

> 각 스킬 SKILL.md의 "팀 에이전트 모드" 섹션 참조.

실사용에서는 풀 사이클보다 **개별 스킬을 반복 실행**하는 것이 일반적입니다.

### 5.3 BATCH Execution

> 참조: `modules/execution-modes.md` — BATCH 모드 상세

/batch --no-pr로 실행. 각 worktree 독립 SOLO. PR은 fz-pr로.

### Context Artifact 관리

> 참조: `modules/context-artifacts.md`

| 파이프라인 길이 | 전략 | 이유 |
|---------------|------|------|
| 1-3 스텝 | Serena `fz:checkpoint:essential` (3K) | compact 대비 경량 보호 |
| 4-5 스텝 | Serena checkpoint 확장 (3K) + 선택적 ASD | compact 위험 낮음 |
| 6+ 스텝 또는 context-heavy | ASD 파일 기반 (`modules/context-artifacts.md`) | compact 후 Read로 복원 |
| 10+ 스텝 | ASD 필수 + compact 주의 안내 | 장기 파이프라인 |

### Essential Context 업데이트 (각 스킬 실행 후)

각 스킬 완료 후 /fz가 중앙 관리:
- **ASD 활성**: `index.md`의 `## Essential Context` 섹션 **덮어쓰기** (Active Phase + Key Decisions + Constraints + Pending)
- **비ASD / 1-5 스텝**: `write_memory("fz:checkpoint:essential", "[{skill}] {핵심결정}. Constraints: {C목록}. Pending: {다음}.")` (~3,000자) <!-- 기존: ~500자 -->
- **mid-pipeline /fz-discover 호출 시**: index.md Active Phase를 discover에 전달 → Phase-Tagged 저장 지원

### 단계 완료 보고 (각 단계)

```markdown
**Step N 완료**: /fz-{skill}
**실행자**: {에이전트명} ({모델})
**결과**: {요약}
**다음**: /fz-{next-skill} (Step N+1)
```

### Gate 실패 처리

```
Gate 실패 시:
├─ SOLO → AskUserQuestion (재시도/스킵/중단)
├─ TEAM → 에이전트에게 이슈 전달 → /ralph-loop 에스컬레이션 래더
├─ BATCH → 실패 worktree만 재실행
└─ 모든 모드 → /ralph-loop 한도 후 사용자 에스컬레이션
```

### 파이프라인 완료 보고

Phase 4 시각화와 동일 형식 + 각 스텝의 상태(OK/FAIL) + 다음 행동 제안.

---

## Boundaries

사용자 승인 없이 파이프라인을 실행하지 않는다 (Phase 4 필수).

**Will**:
- 자연어 의도 분석 + 스킬 자동 조합
- 사전 정의 파이프라인 빠른 매칭
- provides/needs 기반 동적 파이프라인 구성
- 복잡도 기반 자동 모드 결정 (SOLO/TEAM)
- 모델 승격 전략 (Primary Worker → opus)
- 동적 팀 에이전트 구성 (sonnet 제한 없음)
- 교차 검증 게이트 자동 주입
- 구조화된 Artifact 기반 컨텍스트 관리
- 개별 스킬 TEAM 모드 지원
- 파이프라인 시각화 + 사용자 확인
- BATCH worktree 병렬 실행 (--no-pr, fz-pr로 위임)
- /ralph-loop 자동 반복 + 에스컬레이션 래더

**Will Not**:
- 스킬 자체 로직 수행 (스킬 SKILL.md 지침에 위임)
- 사용자 승인 없이 실행 (Phase 4 필수)
- 코드를 직접 수정 (각 스킬에 위임)
- opus 과다 사용 (Lead + Primary 최대 2개 원칙. full-cycle/plan-to-code은 예외: plan-structure+impl-correctness 각 단계 Primary)
- haiku 모델 사용

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| intent-triggers 매칭 0개 | AskUserQuestion | 사용자에게 스킬 직접 선택 요청 |
| 스킬 SKILL.md 누락 | 해당 단계 스킵 제안 | 남은 파이프라인 계속 |
| Gate 실패 (SOLO) | 재시도/스킵/중단 선택 | 사용자 에스컬레이션 |
| Gate 실패 (TEAM) | 서브 에이전트에게 이슈 전달 | SOLO 폴백 |
| 팀 에이전트 스폰 실패 | SOLO 폴백 | 사용자 에스컬레이션 |
| provides/needs 체인 끊김 | 중간 스킬 자동 제안 | AskUserQuestion |
| 파이프라인 12스텝+ | Artifact + 체크포인트 | compact 주의 안내 <!-- 기존: 6스텝+ --> |

## Completion → Next

파이프라인 완료 후:

0. **GC 실행** (필수):
   - L2: `list_memories()` → `fz:artifact:*`, `fz:checkpoint:*` 키 수집 → 각 `delete_memory()` 실행
   - `fz:checkpoint:essential` 명시적 삭제: `delete_memory("fz:checkpoint:essential")`
   - L1: 새 교훈 발생 여부 판단 → 있으면 topic file에 태깅하여 저장
   - L1 저장 시 `modules/memory-guide.md` 정책 준수: `[skill: X]` `[status: Y]` `[priority: Z]` 태깅
   - 참조: `modules/memory-policy.md`

1. **세션 저장** (모든 파이프라인):
   - `/sc:save --type learnings` → 작업 결과 + 결정사항 영속화
   - 다음 세션에서 `/sc:load`로 복원 가능

2. **상황별 안내**:
   - 코드 변경 있음 → `/fz-commit` 제안
   - 리뷰 완료 → `/fz-commit` → `/fz-pr` 제안
   - 탐색만 완료 → `/fz-fix` 또는 `/fz-plan` 제안
   - 풍경 탐색 완료 → `/fz-plan` 제안 (landscape-map + trade-off table 기반)
   - 스킬 생성/수정 완료 → `/fz-skill eval` + `/fz-skill optimize` 제안
   - 생태계 점검 필요 → `/fz-manage benchmark` 제안
   - 전체 사이클 완료 → 완료 보고서 출력
> 모듈 참조: 상단 "모듈 참조" 섹션 참조
