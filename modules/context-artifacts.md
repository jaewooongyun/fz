# Context Artifact 관리

> 아티팩트를 파일로 기록한다. 대화 컨텍스트는 compact 시 손실되지만 파일은 남는다.

## 핵심 원칙

- 아티팩트를 파일로 기록하는 이유: compact 후에도 Read로 복원할 수 있다.
- index.md를 유지하는 이유: 새 세션에서 한 파일만 읽으면 전체 맥락을 파악할 수 있다.
- 파일 크기를 제한하는 이유: 과도한 파일은 context re-explosion을 유발한다.

## 폴더 구조

```
TVING/ASD-xxxx/
├── index.md              # Compact recovery 엔트리 포인트 (append-only)
├── discover/
│   ├── round-1.md ~ round-N.md
│   └── constraints.md    # 최종 제약 매트릭스 (rolling overwrite)
├── plan/
│   ├── plan-v1.md ~ plan-vN.md
│   └── plan-final.md
├── code/
│   ├── step-1.md ~ step-N.md
│   └── progress.md       # 전체 진행 상태 (누적형 — 이전 Step 핵심 결정 한 줄씩 유지)
└── review/
    └── self-review.md
```

## Ticket ID 해석

우선순위: 명시적 인자 > 브랜치명 (`ASD-\d+` 추출) > AskUserQuestion > `NOTASK-{YYYYMMDD}`

## index.md 프로토콜

index.md는 append-only로 관리한다. Active Phase 갱신 시 기존 Phase 아티팩트를 유지한다.

```markdown
# ASD-xxxx Context Index

## Active Phase: discover

## Artifacts
- [discover] round-1.md — 초기 제약 5개 발견 (C1-C5)
- [discover] round-2.md — 사용자 피드백 반영, C6-C8 추가
- [discover] constraints.md — 최종 14개 제약 매트릭스
```

## Compact Recovery Protocol

1. `fz:session:current`에서 `work_dir` 읽기
2. `{WORK_DIR}/index.md` 읽기
3. Active Phase의 최신 아티팩트 로드
4. 상위 Phase 핵심 산출물 로드 (discover→constraints.md, plan→plan-final.md)
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
| 내용 | ~200자 핵심 결정 요약 |
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

| 파일 유형 | 최대 크기 |
|----------|----------|
| round | 2K tokens |
| plan | 3K tokens |
| step | 1.5K tokens |

## TEAM 로깅

ASD 폴더 활성 시: `{phase}/*-team.md`에 에이전트 간 핵심 통신 요약을 기록한다.

## Few-shot 예시

### 예시 1: index.md

```markdown
# ASD-1234 Context Index

## Active Phase: code

## Artifacts
- [discover] round-1.md — RIBs 의존성 3개 발견 (C1-C3)
- [discover] round-2.md — 동시성 제약 추가 (C4-C5)
- [discover] constraints.md — 최종 5개 제약 매트릭스
- [plan] plan-v1.md — 3-Step 계획 초안
- [plan] plan-final.md — 사용자 승인 계획
- [code] step-1.md — Repository 구현 완료, 빌드 성공
- [code] progress.md — Step 1/3 완료
```

### 예시 2: round 파일

```markdown
# Round 2 — 사용자 피드백 반영

## 새로 발견된 제약
- C6: iOS 16 호환 필요 (@Observable 사용 불가)
- C7: weak var는 optional chaining 사용
- C8: 기존 RIBs Router와 동일 패턴 유지

## 후보 평가
| 접근법 | C6 | C7 | C8 | 채택 |
|--------|----|----|-----|------|
| ObservableObject | O | O | O | 채택 |
| @Observable | X | O | O | 탈락 |

## 결정
ObservableObject + @StateObject 조합 채택.
```

### 예시 3: compact recovery

```
[Compact 감지] 대화 컨텍스트 손실됨.
1. fz:session:current → work_dir: "TVING/ASD-1234"
2. ASD-1234/index.md 읽기 → Active Phase: code, Step 1/3 완료
3. code/progress.md 로드 → Step 1-2 완료 이력 + Step 3 진행 중
4. plan/plan-final.md 로드 → 3-Step 계획 확인
5. 컨텍스트 복원 완료. Step 2부터 재개.
```

## Edge Case 대응

| 상황 | 대응 |
|------|------|
| 세션 전환 | `fz:session:current`에 `work_dir` 저장하여 다음 세션에서 복원 |
| /fz 없이 직접 스킬 호출 | 각 스킬이 WORK_DIR 환경 확인 → 없으면 아티팩트 기록 스킵 |
| 단일 티켓 제약 | 동시 작업은 1개 티켓만 허용 |
| Compact 중 파일 쓰기 | Write 완료 후 index.md 업데이트 (atomic ordering) |
| GC 누락 | /fz Completion에서 `list_memories → fz:artifact:*` 확인 → 있으면 삭제 |
| 다중 세션 키 충돌 | `fz:session:current`는 단일 값만 유지. 이전 세션 work_dir가 덮어쓰기됨. 복원 필요 시 ASD 폴더의 index.md를 직접 검색 (`Glob("TVING/ASD-*/index.md")`) |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | ASD 폴더 초기화 + work_dir 저장 |
| /fz-discover | round/constraints 기록 |
| /fz-plan | plan 버전 기록 |
| /fz-code | step/progress 기록 |
| /fz-review | self-review 기록 |
| /fz-peer-review | review-index.md + checkpoint 기록 (synthesized-issues.json, confidence-matrix.md) |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
