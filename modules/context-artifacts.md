# Context Artifact 관리

> 아티팩트를 파일로 기록한다. 대화 컨텍스트는 compact 시 손실되지만 파일은 남는다.

## 핵심 원칙

- 아티팩트를 파일로 기록하는 이유: compact 후에도 Read로 복원할 수 있다.
- index.md를 유지하는 이유: 새 세션에서 한 파일만 읽으면 전체 맥락을 파악할 수 있다.
- 파일 크기를 제한하는 이유: 과도한 파일은 context re-explosion을 유발한다.

## 폴더 구조

```
{CWD}/ASD-xxxx/          # 또는 {CWD}/NOTASK-{YYYYMMDD}/
├── index.md              # Compact recovery 엔트리 포인트 (Essential Context=덮어쓰기, Artifacts=append)
├── discover/
│   ├── discover-journal.md  # plan 전 discover (canonical)
│   ├── discover-plan.md     # plan 실행 중 ad-hoc (Phase-Tagged)
│   ├── discover-code.md     # code 실행 중 ad-hoc (Phase-Tagged)
│   ├── discover-review.md   # review 실행 중 ad-hoc (Phase-Tagged)
│   └── discover-team.md     # TEAM 모드 adversarial discovery 통신 기록
├── plan/
│   ├── plan-v1.md ~ plan-vN.md
│   ├── plan-final.md
│   ├── direction-challenge.md  # Phase 0.5 방향성 도전 결과 (PROCEED/RECONSIDER/REDIRECT)
│   ├── plan-team.md            # TEAM 모드 collaborative design 통신 기록
│   └── verify-result.md        # Phase 2 검증 verdict + 이슈 요약
├── code/
│   ├── step-1.md ~ step-N.md
│   ├── progress.md       # 전체 진행 상태 (누적형 — 이전 Step 핵심 결정 한 줄씩 유지)
│   └── code-team.md      # TEAM 모드 pair programming 통신 기록
├── fix/
│   └── fix-analysis.md   # fz-fix 원인 분석 + 수정 기록
├── search/
│   └── search-result.md  # fz-search 탐색 결과
└── review/
    ├── self-review.md     # fz-review 자기 리뷰 결과
    └── review-team.md     # TEAM 모드 live review 핵심 통신 기록
```

### Standalone Work Dir (peer-review)

fz-peer-review는 ASD 폴더와 별도 WORK_DIR을 사용:

```
{PROJECT_ROOT}/peer-review-{PR_NUMBER}/
├── review-index.md
├── synthesized-issues.json
├── confidence-matrix.md
├── review-report.md
├── pr-comments.md
└── {agent}-result.json        # raw 에이전트 결과 (arch, quality, codex)
```

> ASD 트리 내 중첩하지 않는 이유: peer-review는 PR 단위로 독립 실행되며, ASD 티켓 작업과 무관할 수 있다.

> `{CWD}` = PROJECT_ROOT (CLAUDE.md가 위치한 디렉토리). GIT_ROOT(app-iOS/)와 다를 수 있음. 개인 산출물은 PROJECT_ROOT에만 생성.

## Work Dir 결정

우선순위: 명시적 인자 ASD-xxxx > 브랜치명 (`ASD-\d+` 추출) > AskUserQuestion(저장 여부) > Serena Memory fallback

## index.md 프로토콜

index.md는 두 섹션으로 구성: `## Essential Context`(덮어쓰기)와 `## Artifacts`(append-only).

```markdown
# ASD-xxxx Context Index

## Active Phase: code

## Essential Context (매 Phase 완료 시 /fz가 덮어쓰기)
- Mode: TEAM
- Key Decisions:
  - [plan] ObservableObject 채택 (iOS 16 호환)
  - [code] Step 1/3 완료, Repository 구현
- Constraints: C1(RIBs), C2(Combine), C4(iOS 16)
- Pending: Step 2 ViewModel 구현

## Artifacts (append-only — 기존 Phase 엔트리 유지)
- [discover] discover-journal.md — Round 2 기준
- [discover-code] discover-code.md — code 중 ad-hoc (Phase-Tagged)
- [plan] plan-final.md — 사용자 승인
- [code] step-1.md — Repository 완료
```

> **핵심**: `## Essential Context`는 /fz가 단독 관리하는 **덮어쓰기** 섹션. 서브스킬은 Essential 항목을 반환하고 /fz가 기록한다.

## Compact Recovery Protocol

0. `fz:checkpoint:essential` 읽기 → Essential Context (Key Decisions, Constraints, Active Phase) 즉시 복원
1. `fz:session:current`에서 `work_dir` 읽기
2. `{WORK_DIR}/index.md` 읽기 → `## Essential Context` 섹션으로 상세 복원
3. Active Phase의 최신 아티팩트 로드
4. 상위 Phase 핵심 산출물 로드 (discover→discover-journal.md Current State, plan→plan-final.md)
5. 컨텍스트 복원 완료 알림

## Proactive Context Protocol

> 기존: Write(저장)만 하고 Read(로드) 없음 → compact 후 복원 불가
> 개선: Write + Read. /fz가 중앙에서 Essential Context를 관리

```
[기존] Phase A → Write(artifact) → (compact?) → Phase B → (복원 시도)
[개선] Phase A → Write(artifact) → /fz가 Essential Context 업데이트 → Phase B → /fz가 Read → 서브스킬 실행
```

### Essential vs Disposable

| Essential (보존) | Disposable (자연 소멸 OK) |
|-----------------|-------------------------|
| 사용자 결정/승인 | 탐색 중간 결과 |
| 제약 조건 | raw MCP 출력 |
| 아키텍처 선택 근거 | 에이전트 간 토론 과정 |
| Gate 통과/실패 이력 | 코드 diff 상세 |
| Active Phase + Step 진행률 | 빌드 로그 |
| mid-pipeline discover 결정 | /btw로 물어본 일회성 질문 |
| Implication Register + 관찰 함의 (implications.md) | Implication Scan 중간 로그 |
| Session Metrics (session-metrics.md) — gate/compact/reminder/turns | 개별 도구 결과 로그 |

```
Essential: "[plan] Step 3개 계획 확정. RIBs 패턴. ContentDetail{Builder,Router,Interactor,VC}."
Disposable: "Grep 결과 42개 파일 매칭. find_referencing_symbols 호출 3회."
```

## Upstream Hydration Sets

> Codex M5: 스킬별 Phase 0에서 Read해야 하는 파일 목록 표준화. Artifact drift 방지.

| 스킬 | Upstream (Read 대상) |
|------|---------------------|
| discover | (없음 — 첫 진입점) |
| discover (mid-pipeline) | `index.md` → Active Phase 판별 |
| plan | `discover/discover-journal.md` (있으면), `discover/discover-plan.md` (있으면) |
| code | `plan/plan-final.md`, `discover/discover-journal.md`, `discover/discover-code.md` (있으면), `code/progress.md`, 최신 `code/step-N.md` |
| review | `plan/plan-final.md`, `code/progress.md`, 최신 `code/step-N.md`, `discover/discover-review.md` (있으면) |
| fix | `fix/fix-analysis.md` (있으면), `search/` 결과 (있으면) |
| search | (없음 — 독립 탐색) |

> ⛔ `constraints.md` 참조 금지 — canonical은 `discover-journal.md`

## Phase-Tagged Discover

> mid-pipeline 질문 context 보존. 어느 Phase에서 발생한 질문인지 추적.

### 프로토콜

```
1. /fz-discover 호출 시:
   a. index.md 존재 확인 → 없으면 기본 모드 (discover-journal.md)
   b. 있으면 → Active Phase 읽기
   c. Active Phase가 discover 또는 없음 → discover-journal.md (기본)
   d. Active Phase가 plan/code/review → discover-{phase}.md에 저장
   e. index.md Artifacts에 [discover-{phase}] 엔트리 추가

2. Upstream 스킬이 자기 discover 파일을 Read:
   - /fz-plan → discover-plan.md (있으면)
   - /fz-code → discover-code.md (있으면)
   - /fz-review → discover-review.md (있으면)

3. 비ASD 모드:
   - fz:checkpoint:discover-{phase} 키로 Serena Memory에 저장
```

### 동일 Phase 내 다중 Discover 규칙

```
discover-journal.md (DISCOVER_TAG=journal): 전체 덮어쓰기 (매 라운드)
discover-{phase}.md (DISCOVER_TAG=plan|code|review): APPEND + topic header
- topic header로 분리: ## Topic: {질문 요약} (YYYY-MM-DD HH:MM)
- 파일 크기 1K tokens 초과 시 → 이전 topic 요약 압축 (최신 topic 상세 유지)
```

## Ephemeral vs Persistent (/btw 통합)

> Anthropic: "/btw — dismissible overlay, never enters conversation history"

| 질문 유형 | 도구 | 저장 | 예시 |
|----------|------|------|------|
| 일회성 지식 질문 | `/btw` | ❌ | "CurrentValueSubject와 @Published 차이?" |
| 결정/제약 발견 | `/fz-discover` | ✅ | "이 패턴을 쓸지 말지 결정해야 해" |
| 중간 확인 | `/fz-discover` | ✅ | "지금 구현 방향이 맞나 확인" |

**판별 규칙**: 답변이 향후 Phase에 영향을 미치면 persistent (/fz-discover), 아니면 ephemeral (/btw).

## Serena Memory와의 관계

| 파이프라인 길이 | 전략 | 이유 |
|---------------|------|------|
| 1-3 스텝 | Serena `fz:checkpoint:essential` (3K) | compact 대비 경량 보호 |
| 4-5 스텝 | Serena checkpoint 확장 (3K) + 선택적 ASD | compact 위험 낮음. context-heavy 스킬 포함 시 ASD 권장 |
| 6+ 스텝 또는 context-heavy | ASD 파일 기반 (이 모듈) | compact 후 Read로 복원 <!-- 기존: 4+ 스텝 --> |
| 10+ 스텝 | ASD 필수 + compact 주의 안내 | 장기 파이프라인 |

> **context-heavy 스킬**: discover, search --deep, peer-review (대량 context 생산)

## 비ASD 모드 (Serena Memory Fallback)

ASD 폴더가 없어도 핵심 산출물은 Serena Memory에 경량 저장한다.

| 항목 | 내용 |
|------|------|
| 트리거 | 각 스킬의 Phase 완료 또는 의미 있는 분석 결과 발생 |
| 키 | `fz:checkpoint:{skill}-{phase}` (예: `fz:checkpoint:plan-analysis`) |
| 내용 | ~200자 핵심 결정 요약 (discover는 ~500자 — 제약 매트릭스+생존 후보+핵심 추론 포함) |
| 복원 | `list_memories("fz:checkpoint:*")` → 최신 키 읽기 → 마지막 진행 지점 재개 |
| GC | 파이프라인 완료 시 `fz:checkpoint:*` 일괄 삭제 (기존 GC 로직) |

### Checkpoint 저장 패턴 (각 스킬의 ⛔ 기록 섹션에서 사용)

```
ASD 활성: Write("{WORK_DIR}/{phase}/{artifact}.md") + index.md 업데이트
비ASD:    write_memory("fz:checkpoint:{skill}-{phase}", "핵심 결정 ~200자 요약")
Both:     ASD 파일 + Serena Memory 동시 저장 (이중 안전망)
```

### 비ASD Compact Recovery 절차

```
1. list_memories("fz:checkpoint:*") → 키 목록
2. 키 이름에서 스킬+Phase 파싱 → 마지막 진행 지점 판별
3. 해당 키 read_memory() → 컨텍스트 복원
4. 복원 완료 알림 → 중단 지점부터 재개
```

## Artifact Token Budget

> 현재 환경: **Opus 4.7 (1M context, 2026-04-16 GA)**. 이전 환경: Opus 4.6 (1M context).
> ⚠️ **Opus 4.7 tokenizer 변경**: 1.00-1.35x 토큰 증가 (공식). Korean 대량 prompt 실측 필요 `[미검증: fz 자체 count_tokens 측정 대기]`. 측정 후 하단 테이블 크기 조정 가능.
> 원칙: 전체 artifact 로드 합계 ≤ 100K tokens. 나머지는 실행 working memory.
> Context Rot 원칙(집중 > 분산)은 context 크기와 무관하게 동일 적용.

| 파일 유형 | 최대 크기 | 비고 |
|----------|----------|------|
| Essential Context (index.md) | 3K tokens | Key Decisions + Constraints + Active State <!-- 기존: 500자 --> |
| discover-journal | 10K tokens | 매 라운드 전체 덮어쓰기 (**상세**). Round History 없음 <!-- 기존: 2K --> |
| discover-{phase} | 5K tokens | Phase별 APPEND + topic header <!-- 기존: 1K --> |
| plan-v{N} / plan-final | 10K tokens | 설계 결정 + 영향 분석 + 리스크 <!-- 기존: 3K --> |
| code/step-{N} | 3K tokens | 구현 결과 + 결정 근거 <!-- 기존: 1.5K --> |
| code/progress | 5K tokens | 전체 Step 진행 상황 <!-- 기존: 1.5K --> |
| *-team.md | 5K tokens | 요약 기본. 원본은 *-team-full.md (drill-down용, Hydration 대상 아님) |
| verify-result.md | 3K tokens | Codex 요약 (원본: verify-result-full.md) |

**Eviction 우선순위** (budget 100K 초과 시):
1. 가장 오래된 discover-{phase}.md (journal은 보존)
2. 완료된 step-{N}.md (progress.md 요약으로 대체)
3. *-team.md (요약만 보존)

## TEAM 로깅

ASD 폴더 활성 시: `{phase}/*-team.md`에 에이전트 간 핵심 통신 요약 (5K). 원본 전문은 `*-team-full.md`에 별도 보존 (drill-down용).

## Few-shot 예시

### 예시 1: index.md

```markdown
# ASD-1234 Context Index

## Active Phase: code

## Artifacts
- [discover] discover-journal.md — Round 2 기준, 제약 5개(C1-C5), 생존 후보 1개
- [plan] plan-v1.md — 3-Step 계획 초안
- [plan] plan-final.md — 사용자 승인 계획
- [code] step-1.md — Repository 구현 완료, 빌드 성공
- [code] progress.md — Step 1/3 완료
```

### 예시 2: discover-journal.md (discover-journal 형식)

```markdown
# Discover Journal — 상태 관리 패턴 선택

## Current State (Round 3 기준)

### 제약 매트릭스
| # | 제약 | 출처 | 확신도 |
|---|------|------|--------|
| C1 | RIBs Interactor가 비즈니스 로직 담당 | 아키텍처 원칙 | 높음 |
| C2 | 기존 Combine 기반 (@Published + sink) | 코드 탐색 | 높음 |
| C3 | 보일러플레이트 최소화 (caller 부담 적게) | 사용자 | 중간 |
| C4 | iOS 16 호환 필요 (@Observable 사용 불가) | 사용자 | 높음 |
| C5 | 기존 RIBs Router와 동일 패턴 유지 | 코드 탐색 | 높음 |

### 생존 후보
| 후보 | 모든 제약 | 비고 |
|------|----------|------|
| D: ObservableObject + @StateObject | O | Combine 친화, iOS 16 호환 |

### 탈락 후보 (사유)
- A: @Observable 직접 사용 — C4 위반 (iOS 16 미지원)
- B: Interactor→ViewModel 브릿지 — C3 위반 (브릿지 보일러플레이트 과다)
- C: 직접 @State — C1 위반 (비즈니스 로직이 View에 노출)

### 정제된 요구사항
1. ObservableObject 프로토콜 채택 + @Published 프로퍼티
2. View에서 @StateObject로 소유, init 파라미터로 주입
3. Interactor는 Combine sink로 ViewModel 구독
```

### 최종 산출물 확장 (Phase 3 수렴 시)

기본 discover-journal 형식에 아래 섹션을 추가:
- `### 채택된 해` — 최종 선택 + 한 줄 설명
- `### 수용한 트레이드오프` — 있다면
- `### 정제된 요구사항` — 구현 가능한 구체적 항목 목록
- `### 결정 근거` — 채택 이유 + 코드 참조

### 예시 3: compact recovery

```
[Compact 감지] 대화 컨텍스트 손실됨.
1. fz:session:current → work_dir: "{CWD}/ASD-1234"
2. ASD-1234/index.md 읽기 → Active Phase: code, Step 1/3 완료
3. code/progress.md 로드 → Step 1-2 완료 이력 + Step 3 진행 중
4. plan/plan-final.md 로드 → 3-Step 계획 확인
5. 컨텍스트 복원 완료. Step 2부터 재개.
```

## Edge Case 대응

| 상황 | 대응 |
|------|------|
| 세션 전환 | `fz:session:current`에 `work_dir` 저장하여 다음 세션에서 복원 |
| /fz 없이 직접 스킬 호출 | ⛔ Work Dir Resolution 실행: ASD 패턴 → 자동 생성, 없으면 → 사용자 질문 |
| 단일 티켓 제약 | 동시 작업은 1개 티켓만 허용 |
| Compact 중 파일 쓰기 | Write 완료 후 index.md 업데이트 (atomic ordering) |
| GC 누락 | /fz Completion에서 `list_memories → fz:artifact:*` 확인 → 있으면 삭제 |
| 다중 세션 키 충돌 | `fz:session:current`는 단일 값만 유지. 이전 세션 work_dir가 덮어쓰기됨. 복원 필요 시 index.md를 직접 검색 (`Glob("**/ASD-*/index.md")` 또는 `Glob("**/NOTASK-*/index.md")`) |
| Orphan checkpoint | Session Bootstrap 시 `fz:checkpoint:essential` 존재 확인 → 이전 중단 세션 감지 → 복원/삭제 선택 제안 |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | Work Dir Resolution + work_dir 저장 |
| /fz-discover | discover-journal.md 누적 기록 |
| /fz-plan | plan 버전 기록 |
| /fz-code | step/progress 기록 |
| /fz-review | self-review 기록 |
| /fz-peer-review | review-index.md + 파일 산출물 (synthesized-issues.json, confidence-matrix.md, pr-comments.md) — Serena checkpoint 미사용 |

## ⛔ Work Dir Resolution (모든 fz-* 스킬 필수)

> 반성 4차 교훈 + 5차 교훈: 직접 호출 시에도 폴더가 초기화되어야 하며, 비ASD에서도 파일 저장이 가능해야 한다.

**모든 fz-* 스킬은 Phase 1 시작 전에 이 체크를 실행한다:**

```
1. 인자에서 ASD-\d+ 패턴 추출
2. 패턴 있으면 → 무조건 자동 저장:
   a. {CWD}/ASD-xxxx/ 폴더 존재 확인
   b. 없으면 즉시 mkdir -p + index.md 생성
   c. WORK_DIR = {CWD}/ASD-xxxx/
3. 패턴 없으면:
   a. 브랜치명에서 ASD-\d+ 추출 시도 → 있으면 2번과 동일
   b. 없으면 → AskUserQuestion: "이 작업의 산출물을 파일로 저장할까요?"
      - 예 → {CWD}/NOTASK-{YYYYMMDD}/ 폴더 생성 + index.md + WORK_DIR 설정
      - 아니오 → Serena Memory fallback (경량)
```

**Gate 0 (Work Dir Resolution):**
- [ ] 인자/브랜치에서 ASD 패턴 체크 완료?
- [ ] ASD 패턴 있으면 폴더 자동 생성 완료?
- [ ] 패턴 없으면 사용자에게 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD 경로 / NOTASK 경로 / Serena fallback)

## 사전 예방적 Context 관리

> compact recovery는 사후 대응이다. 아래는 compact를 **지연/방지**하기 위한 사전 전략.

### 원칙: Context 여유 = 실행 품질

auto-compact는 맥락 손실을 수반한다. compact 발동을 최대한 늦추면 실행 품질이 유지된다.

### Filesystem Discovery > Compaction (Anthropic 공식)

> "Claude is effective at discovering state from filesystem. Sometimes better than relying on compacted context."
> — Anthropic Claude Code Best Practices (2026)

compact 후 복원은 context summary보다 **파일 Read가 더 정확**하다. 따라서:
- L3(파일)가 canonical, L2(Serena)는 cursor(위치 표시)
- compact 발생 시: L2 읽기 → L3 파일 경로 파악 → L3 Read로 상세 복원

### Context Decay 방어 (4유형 — 프로젝트 자체 분류)

| 유형 | 설명 | 방어 |
|------|------|------|
| Poisoning | 잘못된 정보가 context에 잔류 | 결정 변경 시 Essential Context 즉시 덮어쓰기 |
| Distraction | 불필요한 정보가 주의 분산 | MCP 출력 격리, Disposable 정보 미축적 |
| Confusion | 상충하는 정보 공존 | Essential Context가 single source of truth |
| Clash | 지시 간 충돌 | /fz 중앙 관리로 일관성 유지 |

### 적용 규칙

1. **MCP 출력 격리**: 대용량 결과(Grep, 심볼 분석, Codex)는 파일로 저장 후 Read 참조. context에 raw 출력 남기지 않음
2. **중간 산출물 즉시 기록**: 분석 결과가 나오면 대화에 축적하지 말고 ASD 파일/Serena에 즉시 기록 → compact 시 Read로 복원
3. **에이전트 스폰 최소화**: 스폰마다 ~50K 토큰 재주입. 단순 작업은 직접 실행
4. **참조 파일 선택적 로드**: 전체 파일 Read 대신 필요 섹션만 (offset/limit). 500줄+ 파일은 분할 읽기

> 상세: `guides/prompt-optimization.md` §2.5 (Context Budget 관리)

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
- Context 여유 = 실행 품질 (사전 예방 > 사후 복구)
