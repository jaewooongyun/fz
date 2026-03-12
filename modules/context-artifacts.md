# Context Artifact 관리

> 아티팩트를 파일로 기록한다. 대화 컨텍스트는 compact 시 손실되지만 파일은 남는다.

## 핵심 원칙

- 아티팩트를 파일로 기록하는 이유: compact 후에도 Read로 복원할 수 있다.
- index.md를 유지하는 이유: 새 세션에서 한 파일만 읽으면 전체 맥락을 파악할 수 있다.
- 파일 크기를 제한하는 이유: 과도한 파일은 context re-explosion을 유발한다.

## 폴더 구조

```
{CWD}/ASD-xxxx/          # 또는 {CWD}/NOTASK-{YYYYMMDD}/
├── index.md              # Compact recovery 엔트리 포인트 (append-only)
├── discover/
│   └── discover-journal.md  # 누적형 저널 (Current State 상단 + Round History 하단)
├── plan/
│   ├── plan-v1.md ~ plan-vN.md
│   └── plan-final.md
├── code/
│   ├── step-1.md ~ step-N.md
│   └── progress.md       # 전체 진행 상태 (누적형 — 이전 Step 핵심 결정 한 줄씩 유지)
└── review/
    └── self-review.md
```

> `{CWD}` = 현재 작업 디렉토리. 어디서 실행하든 해당 위치에 저장.

## Work Dir 결정

우선순위: 명시적 인자 ASD-xxxx > 브랜치명 (`ASD-\d+` 추출) > AskUserQuestion(저장 여부) > Serena Memory fallback

## index.md 프로토콜

index.md는 append-only로 관리한다. Active Phase 갱신 시 기존 Phase 아티팩트를 유지한다.

```markdown
# ASD-xxxx Context Index

## Active Phase: discover

## Artifacts
- [discover] discover-journal.md — Round 3 기준, 제약 8개(C1-C8), 생존 후보 2개
```

## Compact Recovery Protocol

1. `fz:session:current`에서 `work_dir` 읽기
2. `{WORK_DIR}/index.md` 읽기
3. Active Phase의 최신 아티팩트 로드
4. 상위 Phase 핵심 산출물 로드 (discover→discover-journal.md Current State, plan→plan-final.md)
5. 컨텍스트 복원 완료 알림

## Serena Memory와의 관계

| 파이프라인 길이 | 전략 | 이유 |
|---------------|------|------|
| 1-3 스텝 | 대화 컨텍스트 | compact 전에 완료 가능 |
| 4+ 스텝 + ASD 폴더 | 파일 기반 (이 모듈) | compact 후 Read로 복원 |
| 4+ 스텝 - ASD 폴더 | Serena Memory (`modules/memory-policy.md`) | 기존 호환 |

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

## 파일 크기 제한

| 파일 유형 | 최대 크기 | 비고 |
|----------|----------|------|
| discover-journal | 2K tokens | 매 라운드 전체 덮어쓰기 (**상세** — 요약 아님). Round History 없음 |
| plan | 3K tokens | |
| step | 1.5K tokens | |

## TEAM 로깅

ASD 폴더 활성 시: `{phase}/*-team.md`에 에이전트 간 핵심 통신 요약을 기록한다.

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

### 예시 2: discover-journal.md

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

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | Work Dir Resolution + work_dir 저장 |
| /fz-discover | discover-journal.md 누적 기록 |
| /fz-plan | plan 버전 기록 |
| /fz-code | step/progress 기록 |
| /fz-review | self-review 기록 |
| /fz-peer-review | review-index.md + checkpoint 기록 (synthesized-issues.json, confidence-matrix.md) |

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
