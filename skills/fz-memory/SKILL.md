---
name: fz-memory
description: >-
  메모리 관리 + 교훈 회상 스킬. L1(Auto Memory) 정리, L2(Serena) GC, topic file 관리,
  작업 전 관련 교훈 회상. Use when auditing memory health, organizing topic files,
  recalling past learnings, or cleaning stale entries.
  Do NOT use for code implementation (use fz-code) or code review (use fz-review).
user-invocable: true
argument-hint: "[audit|gc|recall|organize|remind] [--skill fz-plan] [--deep]"
allowed-tools: >-
  Read, Write, Edit, Grep, Glob,
  mcp__serena__read_memory, mcp__serena__write_memory,
  mcp__serena__edit_memory, mcp__serena__delete_memory,
  mcp__serena__list_memories,
  mcp__serena__find_symbol, mcp__serena__search_for_pattern,
  mcp__context7__resolve-library-id, mcp__context7__query-docs,
  mcp__sequential-thinking__sequentialthinking
team-agents:
  primary: null
  supporting: [memory-curator]
composable: true
provides: [memory-management, memory-recall]
needs: [none]
intent-triggers:
  - "메모리.*정리|메모리.*관리|메모리.*감사|교훈.*회상|기억.*떠올려"
  - "memory.*audit|memory.*gc|memory.*recall|memory.*organize|cleanup.*memory"
model-strategy:
  main: opus
  verifier: null
---

# /fz-memory - 메모리 관리 + 교훈 회상 스킬

> **행동 원칙**: L1/L2/L3 메모리를 체계적으로 관리하고, 작업 전 관련 교훈을 회상하여 같은 실수를 반복하지 않는다.

## 개요

> 서브커맨드 선택 → 실행 → 결과 보고

- 5개 서브커맨드: audit, gc, recall, organize, remind
- 3-Layer 메모리 관리: L1(Auto Memory) + L2(Serena) + L3(ASD 파일)
- topic file 태그 기반 교훈 매칭
- 코드 유효성 검증 (find_symbol + search_for_pattern)

## 사용 시점

```bash
/fz-memory audit                    # 3-Layer 헬스체크
/fz-memory gc                       # stale 키/항목 정리
/fz-memory recall --skill fz-plan   # fz-plan 관련 교훈 회상
/fz-memory organize                 # MEMORY.md 재구성 + topic file 정리
/fz-memory remind                   # 미반영 교훈 알림
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/memory-guide.md | L1 auto memory 관리 정책 + 태깅 규칙 |
| modules/memory-policy.md | L2 Serena Memory 키 네이밍 + GC 정책 |
| modules/context-artifacts.md | L3 ASD 폴더 관리 |

## sc: 활용 (SuperClaude 연계)

| 서브커맨드 | sc: 명령어 | 용도 |
|-----------|-----------|------|
| audit | `sc:analyze` | L1/L2/L3 건강도 정량 분석 |
| recall | `sc:explain` | 회상된 교훈의 관련성 설명 |
| organize | `sc:reflect` | 재구성 후 자체 검증 (200줄 한도, 중복 없음) |
| remind | `sc:reflect` | 미개선 항목의 현재 적용 여부 재검증 |

---

## 서브커맨드 1: audit

3-Layer 메모리 헬스체크. 건강도를 정량 보고.

### 절차

**L1 검사**:
1. MEMORY.md 줄수 확인 (200줄 한도 vs 현재)
2. topic file 목록 + 각 줄수 + 최종 수정일
3. MEMORY.md ↔ topic file 링크 정합성 (끊어진 링크)
4. 태그 통계: `[status: pending/applied/deferred]` 분포

**L2 검사 (Serena)**:
1. `list_memories()` → 전체 키 수집
2. 키별 수명 정책과 대조 (`modules/memory-policy.md`)
3. orphan 키 (정의에 없는 패턴) 감지
4. stale persistent 키 (30일+ 미참조) 목록

**L3 검사**:
1. ASD-*/index.md 존재 + 정합성 확인
2. 완료된 파이프라인의 잔존 ASD 폴더 감지

보고: `sc:analyze` 활용하여 정량 보고서 생성.

### Gate: Audit Complete
- [ ] L1/L2/L3 각 레이어 검사 완료?
- [ ] 보고서에 조치 필요 항목 명시?

---

## 서브커맨드 2: gc

L2 임시키 삭제 + L1 stale 항목 정리 제안 + L3 잔존 ASD 정리.

### 절차

1. **L2 임시키 GC**:
   - `list_memories()` → `fz:artifact:*`, `fz:checkpoint:*` 수집
   - 각 키에 `delete_memory()` 실행
   - `fz:session:current`는 유지

2. **L2 persistent 키 GC** (`--persistent` 옵션 시):
   - `fz:decision:*`, `fz:pattern:*` 중 30일+ 미참조 키 목록화
   - 사용자 확인 후 삭제

3. **L1 stale 항목 정리 제안**:
   - `[status: applied]` + 6개월+ → 아카이브 후보 표시
   - 끊어진 링크 보고
   - 삭제/아카이브는 사용자 확인 필수

4. **L3 잔존 ASD 정리**:
   - 완료된 파이프라인의 ASD 폴더 목록
   - 사용자 확인 후 삭제

### Gate: GC Complete
- [ ] L2 임시키 삭제 완료?
- [ ] 사용자 확인 항목 처리?

---

## 서브커맨드 3: recall

현재 작업에 관련된 교훈 회상 + 코드 유효성 검증.

### 절차

1. **현재 컨텍스트 분석**: 어떤 스킬이 실행될 예정인지 파악
2. **MEMORY.md 스캔**: topic file 링크 수집
3. **topic file에서 태그 매칭**: `[skill: fz-{current}]` 패턴 Grep
4. **매칭된 교훈의 유효성 검증**:
   a. `find_symbol` → 교훈에 언급된 심볼이 아직 존재하는지
   b. `search_for_pattern` → 교훈에 언급된 패턴이 유효한지
   c. 라이브러리 관련 → Context7로 최신 API 확인
5. **유효한 교훈만 요약** (3-5줄) + stale 교훈 표시
6. **결과 주입**: SOLO → 대화 컨텍스트, TEAM → `SendMessage(Primary Worker)`

### Gate: Recall Complete
- [ ] 관련 교훈 검색 완료?
- [ ] 유효성 검증 완료?
- [ ] 결과 전달 완료?

---

## 서브커맨드 4: organize

MEMORY.md 재구성 + topic file 분리/병합.

### 절차

1. `sequential-thinking` → 현재 구조 분석 + 재구성 계획
2. MEMORY.md 200줄 한도 확인 → 초과 시 상세 내용을 topic file로 분리
3. topic file 간 중복 검사 → 병합 대상 식별
4. 태그 정합성 검사 → 누락 태그 추가
5. `sc:reflect` → 재구성 결과 자체 검증

### Gate: Organize Complete
- [ ] MEMORY.md 200줄 이하?
- [ ] 모든 topic file에 MEMORY.md 링크?
- [ ] 태그 정합성 확인?

---

## 서브커맨드 5: remind

이전 교훈 중 미개선 항목을 사용자에게 알림.

### 절차

1. **topic file 전체 스캔**: Grep으로 `[status: pending]` 검색
2. **현재 상태 검증**:
   a. `find_symbol` / `search_for_pattern` → 이미 수정되었는지 확인
   b. 이미 적용됨 → `[status: applied]`로 자동 업데이트
   c. 미적용 → 유지
3. **미적용 항목 스킬별 그룹핑**
4. **사용자에게 AskUserQuestion으로 보고**:
   ```
   이전 교훈에서 발견된 미반영 개선점 N건:
   - fz-plan: {설명} (peer-review-learnings.md)
   - fz-code: {설명} (peer-review-learnings.md)
   처리하시겠습니까?
   ```
5. `sc:reflect` → 판단 자체를 재검증

### Gate: Remind Complete
- [ ] pending 항목 전수 검색?
- [ ] 자동 업데이트 완료 (이미 적용된 항목)?
- [ ] 사용자에게 미반영 항목 보고?

---

## 팀 에이전트 모드

### memory-curator (선택적 — TEAM 모드에서)

- 스킬 자체는 기본 SOLO로 실행
- recall 서브커맨드 TEAM 모드 시 memory-curator spawn
- memory-curator가 topic file + Serena Memory를 병렬 탐색하여 교훈 전달

---

## 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "메모리 정리해줘" | trigger | audit 또는 gc |
| "교훈 떠올려줘" | trigger | recall |
| "memory audit" | trigger | audit |
| "코드 리뷰해줘" | NOT trigger | → fz-review |
| "버그 고쳐줘" | NOT trigger | → fz-fix |

### Functional

| Given | When | Then |
|-------|------|------|
| topic file에 [status: pending] 2건 | /fz-memory remind | 미반영 2건 보고 |
| MEMORY.md 250줄 | /fz-memory audit | 200줄 초과 경고 |
| L2에 stale artifact 키 3개 | /fz-memory gc | 3개 삭제 |

## Boundaries

**Will**:
- L1/L2/L3 메모리 헬스체크 및 정리
- topic file 태그 기반 교훈 회상
- 코드 유효성 검증 (심볼/패턴)
- MEMORY.md 재구성 + topic file 정리

**Will Not**:
- 코드 구현 (→ /fz-code)
- 코드 리뷰 (→ /fz-review)
- 계획 수립 (→ /fz-plan)
- Serena Memory 스키마 변경 (→ memory-policy.md 수정)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| Serena 연결 실패 | L1만 검사 (L2 건너뛰기) | 수동 관리 안내 |
| topic file 없음 | MEMORY.md만 검사 | organize 제안 |
| find_symbol 실패 | 유효성 검증 스킵 (교훈 그대로 전달) | 사용자에게 검증 요청 |

## Completion -> Next

- audit → gc 제안 (stale 항목 발견 시)
- gc → 완료 보고
- recall → 현재 파이프라인 계속 진행
- organize → audit 제안 (결과 검증)
- remind → 개선 작업 제안 (fz-plan/fz-code)
