---
name: fz-search
description: >-
  This skill should be used when the user wants to find, explore, or trace code in the project.
  Make sure to use this skill whenever the user says: "찾아줘", "탐색해줘", "구조 알려줘",
  "의존성 추적", "어디 있어?", "누가 쓰고 있어?", "호출 관계", "search for", "find where",
  "explore the structure", "trace dependencies", "who uses this?", "where is it defined?".
  Covers: 찾아, 탐색, 구조, 의존성, 어디, 호출 관계, 코드 패턴 검색, 아키텍처 분석.
  Do NOT use for code modification (use fz-fix or fz-code) or code review (use fz-review).
user-invocable: true
argument-hint: "[검색 대상] [--mode arch|layer|impact|pattern] [--deep]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__find_file,
  mcp__serena__list_dir,
  mcp__serena__activate_project,
  mcp__serena__read_memory,
  mcp__serena__write_memory,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  mcp__lsp__definition,
  mcp__lsp__references,
  mcp__lsp__hover,
  mcp__lsp__peek_definition,
  Read, Grep, Glob
team-agents:
  primary: null
  supporting: [search-symbolic, search-pattern]
composable: true
provides: [search-results, architecture-analysis]
needs: [none]
intent-triggers:
  - "찾아|탐색|구조|영향|의존성"
  - "search|explore|structure|impact|dependency"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-search - 코드 탐색 & 구조 분석 스킬

> **행동 원칙**: Read-Only 탐색으로 코드 구조를 정확하게 파악한다. 병렬 교차 검증(`--deep`)으로 신뢰도를 높이고, 구조화된 결과로 다음 행동을 안내한다.

## 개요

> ⛔ Phase 0 (ASD Pre-flight) → 4가지 모드: arch | layer | impact | pattern
> 2가지 실행 방식: 순차(기본) | 병렬 교차 검증(--deep)

- CLAUDE.md `## Directory Structure`의 git-root 기준으로 탐색
- 프로젝트 아키텍처 구조를 이해하는 전용 탐색
- Symbolic(Serena) + Pattern(Grep/Glob) 이중 경로
- **코드 수정 절대 금지** (Read-Only)

## 사용 시점

```bash
/fz-search "ContentDetail 모듈 구조"                 # arch 모드 자동
/fz-search "Auth 데이터 흐름"                         # layer 모드 자동
/fz-search "AuthRepository 영향 범위"                 # impact 모드 자동
/fz-search "싱글톤 패턴 찾아줘"                       # pattern 모드 자동
/fz-search --mode arch "Player"                       # 모드 명시
/fz-search --deep "ContentDetail 모듈 구조"           # 병렬 교차 검증
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |

## Plugin 참조 (SwiftUI)

> 참조: `modules/plugin-refs.md` — SwiftUI Expert 섹션 (탐색 시 View 구조/패턴 판단 기준)

## sc: 활용 (SuperClaude 연계)

| 모드/상황 | sc: 명령어 | 용도 |
|----------|-----------|------|
| 탐색 시작 전 | `/sc:index-repo` | 프로젝트 구조 빠른 파악 (3K 토큰, 최초 1회) |
| 구조 분석 | `/sc:analyze` | 탐색 결과의 아키텍처 품질 분석 |
| 설명 요청 | `/sc:explain` | 탐색된 코드/구조 교육적 설명 |
| 복잡한 탐색 후 | `→ /fz-fix` | 수정이 필요한 경우 전환 |
| 설계 필요 시 | `→ /fz-plan` | 구조 변경 계획 수립 |

---

## ⛔ Phase 0: ASD Pre-flight (반성 4차 — 누락 방지)

> 참조: `modules/context-artifacts.md` → "Work Dir Resolution" 섹션

**Phase 1 시작 전에 반드시 실행:**

1. 인자에서 `ASD-\d+` 패턴 추출
2. 패턴 있으면 → `{CWD}/ASD-xxxx/` 폴더 + index.md 생성 (없으면) + WORK_DIR 설정
3. 패턴 없으면 → 브랜치명 확인 → 없으면 AskUserQuestion(저장 여부) → 예: `{CWD}/NOTASK-{YYYYMMDD}/` + index.md 생성 / 아니오: Serena fallback

### Gate 0: Work Dir Ready
- [ ] ⛔ ASD 패턴 또는 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD / NOTASK / Serena fallback)
- [ ] index.md 존재 확인 완료? (없으면 생성)

---

## 탐색 시작 전: 프로젝트 인덱스 활용

모드 실행 전, 프로젝트 전체 구조를 빠르게 파악합니다.

### 절차

1. **PROJECT_INDEX.md 확인**:
   - 존재 → 읽기 (3K 토큰으로 프로젝트 전체 구조 파악)
   - 미존재 → `/sc:index-repo` 실행 제안 (사용자 승인 시 생성)
2. **인덱스 기반 탐색 범위 결정**:
   - 모듈/디렉토리 구조를 미리 파악 → 불필요한 전체 탐색 방지
   - 대상 모듈 위치를 빠르게 특정

> **토큰 절감**: 인덱스 없이 탐색 시 58K+ 토큰 vs 인덱스 활용 시 3K + 집중 탐색

---

## 4가지 탐색 모드

### 모드 자동 판별

| 모드 | 트리거 키워드 | 목적 |
|------|-------------|------|
| **arch** | 모듈, Component, 구조, 동작, 화면, Router, Interactor, Builder | 기능별 아키텍처 구조 전체 탐색 |
| **layer** | "데이터 흐름", "레이어", API, Repository, UseCase, Workflow | 레이어 간 데이터 흐름 추적 |
| **impact** | "영향", "변경", "참조", "누가 쓰는", "사이드이펙트" | 심볼 변경 시 영향 범위 분석 (depth 2) |
| **pattern** | "패턴", "찾아", "검색", "안티패턴", "컨벤션" | 코드 패턴/컨벤션 프로젝트 전체 검색 |

> 모드 판별이 모호할 경우 → `AskUserQuestion`으로 확인

---

## Mode: arch -- 아키텍처 구조 탐색

기능별 아키텍처의 전체 구조와 하위 컴포넌트 관계를 탐색합니다.
CLAUDE.md `## Architecture` 섹션에 정의된 프로젝트 아키텍처 패턴에 따라 탐색합니다.

### Serena 도구 호출 (Symbolic)

```
1. find_symbol({Feature}*)                 → 주요 컴포넌트 구조 확인
2. find_referencing_symbols({Feature}*)     → 하위 컴포넌트 연결 파악
3. get_symbols_overview({Feature}*.swift)   → 전체 심볼 개요
```

### Grep/Glob 도구 호출 (Pattern)

```
1. Glob(**/{Feature}*.swift)              → 관련 파일 디스커버리
2. Grep({Feature} protocol)               → 프로토콜 사용처
3. Grep(관련 attach/detach/register 패턴)  → 연결/해제 호출 위치
```

### 출력 항목

- 아키텍처 트리 구조 (ASCII)
- 컴포넌트별 역할 요약
- 하위 컴포넌트 목록 및 연결 방식
- 프로토콜/인터페이스 구조

---

## Mode: layer -- 데이터 흐름 추적

레이어 간 데이터 흐름을 추적합니다. CLAUDE.md `## Architecture`에 정의된 레이어 구조를 따릅니다.

### Serena 도구 호출 (Symbolic)

```
1. search_for_pattern({Target}API)                → API 엔드포인트 검색
2. find_symbol({Target}Repository)                → Repository 구현체
3. find_referencing_symbols({Target}Repository)    → Repository 소비자
4. find_symbol({Target}UseCase)                   → UseCase 구현체
5. find_referencing_symbols({Target}UseCase)       → UseCase 소비자
```

### Grep/Glob 도구 호출 (Pattern)

```
1. Grep(class.*{Target}.*Repository)    → Repository 구현 검색
2. Grep(class.*{Target}.*UseCase)       → UseCase 구현 검색
3. Grep({Target}.*Workflow|{Target}.*Interactor) → 상위 소비자 검색
```

### 출력 항목

- 레이어 흐름도 (ASCII): 프로젝트 아키텍처 레이어 순서대로
- 각 레이어의 구현체와 프로토콜
- DTO → Entity 변환 위치
- 의존성 주입 경로

---

## Mode: impact -- 영향 범위 분석

심볼 변경 시 영향받는 파일과 심볼을 depth 2까지 추적합니다.

### Serena 도구 호출 (Symbolic)

```
1. find_symbol({Symbol})                            → 대상 심볼 확인
2. find_referencing_symbols({Symbol})                → 1차 참조자
3. find_referencing_symbols({1차 참조 심볼들})        → 2차 참조자 (depth 2)
4. get_symbols_overview({Symbol이 있는 파일})         → 파일 컨텍스트
```

### Grep/Glob 도구 호출 (Pattern)

```
1. Grep({Symbol}, files_with_matches)              → 텍스트 레벨 참조
2. Grep(protocol.*{Symbol}|extension.*{Symbol})     → 프로토콜/익스텐션
3. Grep({Symbol}.*\(|{Symbol}\.)                    → 호출/접근 패턴
```

### 출력 항목

- 영향 범위 그래프 (ASCII): 대상 → 1차 → 2차
- 직접 참조 파일 목록 (1차)
- 간접 참조 파일 목록 (2차)
- 변경 시 주의 사항

---

## Mode: pattern -- 코드 패턴 검색

정규식 기반으로 프로젝트 전체에서 코드 패턴/컨벤션을 검색합니다.

### Serena 도구 호출 (Symbolic)

```
1. search_for_pattern({regex})                     → 심볼릭 패턴 검색
2. get_symbols_overview({결과 파일들})               → 결과 파일의 심볼 컨텍스트
```

### Grep/Glob 도구 호출 (Pattern)

```
1. Grep({regex}, output_mode: content, -C: 3)      → 컨텍스트 포함 검색
2. Grep({regex}, output_mode: count)                → 발생 빈도 통계
```

### 출력 항목

- 매칭 결과 목록 (파일, 라인, 컨텍스트)
- 발생 빈도 통계
- 패턴 분포 (모듈/디렉토리별)
- 안티패턴 시 개선 제안

---

## 병렬 교차 검증 (`--deep` 모드)

> 팀 모드 규칙은 `.claude/modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("search-{target}")
├── Lead (Opus): 쿼리 분석 + 결과 합성
├── search-symbolic (Sonnet): Serena MCP 탐색
└── search-pattern (Sonnet): Grep/Glob 탐색
```

### 통신 패턴: Cross-Verify Search (Peer-to-Peer)

탐색자들이 **발견 즉시 서로에게 직접 확인**을 요청하는 패턴.
Lead를 거치지 않고 직접 SendMessage로 대화한다.

```
탐색 중:
  search-symbolic → SendMessage(search-pattern): "Router 찾았어요. attach/detach 호출 위치 찾아주세요"
  search-pattern → SendMessage(search-symbolic): "AuthModule에서도 참조 발견. 심볼 레벨 확인해주세요"
  search-symbolic → SendMessage(search-pattern): "deprecated import만 있어요. false positive."
  양쪽 → SendMessage(team-lead): "탐색 완료. 통합 결과: {결과}"
```

신뢰도: 양쪽 발견 = ★★★, Symbolic only = ★★, Pattern only = ★

**핵심**: 한쪽의 발견이 즉시 다른 쪽의 탐색 방향을 안내. false positive 실시간 제거.

### 신뢰도 등급

| 등급 | 조건 | 의미 |
|------|------|------|
| ★★★ | Symbolic + Pattern 모두 발견 | 교차 확인 완료 (최고 신뢰) |
| ★★ | Symbolic only | 구조적으로 정확 |
| ★ | Pattern only | 넓은 범위, 노이즈 가능 |

### 기본 모드 (--deep 없이)

Orchestrator가 Serena → Grep 순차 실행합니다.
- 빠르지만 교차 검증 없음
- 신뢰도 등급 미표시
- 대부분의 탐색에 충분

---

## 출력 형식 (모든 모드 공통)

```markdown
## {대상} {모드} 탐색 결과

### 파일 목록
| # | 파일 | 역할 | 신뢰도 |
|---|------|------|--------|
| 1 | Feature/Router.swift | 네비게이션 | ★★★ |
| 2 | Feature/Interactor.swift | 비즈니스 로직 | ★★★ |

### 의존성/흐름 그래프
(모드별 ASCII 다이어그램)

### 핵심 발견
- 발견1: ...
- 발견2: ...

### 다음 행동 제안
-> /fz-fix, /fz-plan, /fz-code (상황에 따라)
```

> `--deep` 모드에서만 신뢰도 열이 표시됩니다.

---

## Few-shot 예시

```
BAD (불충분한 결과):
PlayerInteractor 찾음. 3개 파일에서 사용됨.
→ 의존성 방향, 영향 범위 분석 없음

GOOD:
## 탐색: PlayerInteractor 의존성 분석
### 심볼
- 정의: app-iOS/Player/PlayerInteractor.swift:15
- 프로토콜: PlayerInteractable (Router listener)
### 의존성 체인
PlayerBuilder → PlayerInteractor → VideoUseCase → VideoRepository → NetworkService
### 영향 범위 (PlayerInteractor 수정 시)
- 직접: PlayerBuilder.swift (DI 변경), PlayerInteractorTests.swift
- 간접: HomeRouter.swift (child RIB 인터페이스 변경 시)
- 테스트: PlayerInteractorTests.swift (Mock 업데이트 필요)
```

### ⛔ 아티팩트 기록 (항상)

탐색 완료 후 결과를 기록한다.
- ASD 활성: `{WORK_DIR}/search/search-result.md` + `index.md` 업데이트
- 비ASD: `write_memory("fz:checkpoint:search", "모드: {mode}. 발견: {N}개 심볼. 핵심: {요약}")`

## Gate: Search Complete
- [ ] ⛔ Gate 0 (ASD Pre-flight) 통과했는가?
- [ ] 대상 심볼/패턴 파악 완료?
- [ ] 영향 범위 식별?
- [ ] ⛔ 아티팩트 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)

---

## Boundaries

**CRITICAL**: 코드 수정 절대 금지 (Read-Only)

**Will**:
- 4가지 모드의 코드 탐색 (arch, layer, impact, pattern)
- 병렬 교차 검증 (--deep 모드)
- 구조화된 출력 (테이블, ASCII 그래프)
- 다음 행동 제안 (/fz-fix, /fz-plan, /fz-code)

**Will Not**:
- 코드 수정 (→ /fz-fix 또는 /fz-code)
- 빌드 실행 (→ /fz-fix 또는 /fz-code)
- 코드 리뷰 (→ /fz-review)
- 세션/Issue Tracker 관리 (→ /fz-manage)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| find_symbol 실패 | search_for_pattern 전환 | Grep + Glob 폴백 |
| --deep 팀 생성 실패 | 순차 모드 자동 전환 | 단일 에이전트 실행 |
| 결과 과다 (>200건) | head_limit + 파일 필터 | 모듈/디렉토리 필터 안내 |
| 모드 판별 모호 | AskUserQuestion | 사용자 선택 |
| Serena 연결 실패 | Grep + Glob 전용 | 패턴 검색만 수행 |

## Completion → Next

- 구조 파악 완료 → 사용자에게 결과 보고
- 수정 필요 발견 → `/fz-fix` 제안 (간단) 또는 `/fz-plan` 제안 (복잡)
- 구현 필요 → `/fz-code` 제안
- 리뷰 필요 → `/fz-review` 제안
- 탐색 심화 필요 → `/fz-search --deep` 제안
