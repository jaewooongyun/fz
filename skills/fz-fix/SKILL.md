---
name: fz-fix
description: >-
  This skill should be used when the user reports a bug, crash, or error that needs fixing.
  Make sure to use this skill whenever the user says: "고쳐줘", "수정해줘", "버그 있어", "크래시 나",
  "에러 떠", "안 돼", "튕겨", "동작 안 해", "fix this", "it crashes", "there's a bug",
  "getting an error", "not working", "broken".
  Covers: 버그, 수정, 크래시, 에러, 고쳐, 안 돼, 튕겨, 빠른 원인 분석과 수정 사이클.
  Do NOT use for new feature implementation (use fz-code) or code exploration (use fz-search).
user-invocable: true
argument-hint: "[버그/에러 설명]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__search_for_pattern,
  mcp__serena__replace_symbol_body,
  mcp__serena__insert_after_symbol,
  mcp__serena__find_referencing_symbols,
  mcp__serena__find_file,
  mcp__serena__read_memory,
  mcp__serena__write_memory,
  mcp__sequential-thinking__sequentialthinking,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  mcp__lsp__diagnostics_delta,
  mcp__lsp__hover,
  mcp__lsp__peek_definition,
  Edit, Read, Bash(xcodebuild *), Bash(cd *)
team-agents:
  primary: impl-correctness
  supporting: []
composable: false
provides: [code-changes]
needs: [none]
intent-triggers:
  - "수정|고쳐|버그|크래시|에러"
  - "fix|bug|crash|error|patch"
model-strategy:
  main: opus
  verifier: null
---

# /fz-fix - 버그 수정 스킬

> **행동 원칙**: 빠른 수정-빌드 사이클로 버그를 해결한다. 복잡도가 초과하면 즉시 적절한 스킬로 전환을 제안한다.

## 개요

> 탐색 → 분석 → 수정 → 빌드 (실패 시 반복) → 리뷰(선택)

- 빠른 수정-빌드 반복에 최적화
- 검증 선택적 (복잡할 때만)
- 복잡도 초과 시 자동 전환 제안
- **코드 탐색만 필요한 경우** → `/fz-search` 사용

## 사용 시점

```bash
/fz-fix "API 응답이 null일 때 크래시 발생"     # 버그 수정
/fz-fix "타임아웃을 30초로 변경해줘"            # 간단한 수정
# 코드 탐색이 필요하면 → /fz-search "PlayerRIB 구조"
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/build.md | 빌드 검증 |
| modules/execution-modes.md | LOOP 실행 모드 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/context-artifacts.md | ASD 폴더 기반 compact recovery + 산출물 전달 |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |

## Plugin 참조 (SwiftUI + Swift Concurrency)

> 참조: `modules/plugin-refs.md` — SwiftUI Expert(수정 시) + Swift Concurrency(수정 시) 섹션
> SwiftUI View 작업 시 `swiftui-expert` 플러그인 패턴 참조
> **iOS 16 최소 타겟**: `@Observable`/`@Bindable` → `#available(iOS 17, *)` 필수. 기본은 `ObservableObject`/`@StateObject`
> 자동 감지: 코드에 SwiftUI/Concurrency 패턴 발견 시 플러그인 적극 참조 (트리거 목록: `modules/plugin-refs.md`)

## sc: 활용 (SuperClaude 연계)

| Mode/상황 | sc: 명령어 | 용도 |
|----------|-----------|------|
| 버그 수정 | `/sc:troubleshoot` | 에러 원인 자동 진단 |
| 복잡한 에러 | `/sc:explain` | 프레임워크/라이브러리 깊은 에러 교육적 설명 |
| 수정 후 | `/sc:analyze` | 수정 코드 빠른 품질 체크 |
| 복잡한 수정 후 | `/sc:reflect --type task` | 근본 원인 해결 여부 자체 검증 |
| 코드 탐색 필요 | `→ /fz-search` | 전용 탐색 스킬로 전환 |
| 복잡도 초과 | `→ /fz-plan` 또는 `→ /fz-code` | 스킬 전환 |

---

## ⛔ Phase 0: ASD Pre-flight

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

### ASD 컨텍스트 로딩 (ASD 폴더 활성 시):
- `{WORK_DIR}/fix/fix-analysis.md` 읽기 → 이전 수정 분석 복원 (있으면)
- `{WORK_DIR}/search/search-result.md` 읽기 → fz-search 탐색 결과 (있으면)

---

## Mode A: 버그 수정 (Bug Fix)

빠른 수정-빌드 사이클로 버그를 해결합니다.

> **프로젝트 규칙**: CLAUDE.md `## Guidelines` 섹션을 따른다.

### Step 1a: Reproduce — 재현 조건 확인

1. **증상 파악**: 에러 메시지, 크래시 로그, 재현 경로 먼저 확인
2. 재현 가능한 정확한 경로를 식별 (UI 흐름, API 호출 순서 등)

### Step 1b: Isolate — 최소 범위로 좁히기

1. **관련 코드 탐색** (Serena):
   - `mcp__serena__search_for_pattern` → 에러 메시지/키워드 검색
   - `mcp__serena__find_symbol` → 의심 심볼 찾기
   - `mcp__serena__find_referencing_symbols` → 호출 관계 파악
2. 원인 후보를 2-3개로 좁힘

### Step 1c: Root-Cause — 증상이 아닌 원인 추적

1. **구조적 추론** (복잡한 버그):
   - `mcp__sequential-thinking__sequentialthinking` → 5 Whys 기법
   - `/sc:troubleshoot` → 자동 진단
   - `/sc:explain` → 프레임워크/라이브러리 깊은 에러의 교육적 설명
2. **⛔ Step 1c 완료 전 코드 수정 금지**. root-cause가 불명확하면 AskUserQuestion.

### Step 2: 수정

| 상황 | 도구 |
|------|------|
| 심볼 수정 | `mcp__serena__replace_symbol_body` |
| 코드 추가 | `mcp__serena__insert_after_symbol` |
| 간단 수정 | `Edit` |
| 복잡한 수정 | `/sc:troubleshoot` |

### Step 3: 빌드 검증

참조: `modules/build.md` — 빌드 검증 패턴

/ralph-loop 에스컬레이션 래더 적용 (참조: modules/execution-modes.md)

### Step 4: Verify Fix (필수)

수정이 재현 경로(Step 1a)에서 문제를 해결했는지 확인:
- `mcp__serena__find_referencing_symbols` → 참조 무결성 확인
- `/sc:analyze` → 빠른 품질 체크
- `/sc:reflect --type task` → 수정이 근본 원인을 해결했는지 자체 검증
  (트리거: 복잡한 버그 수정 완료 후, 단순 수정은 스킵)
- 또는 `/fz-review`로 전환

---

## 팀 에이전트 모드 (복잡한 버그)

> 팀 모드 규칙은 `.claude/modules/team-core.md` 참조

복잡한 버그(여러 파일 관련, 아키텍처 영향)에서 TEAM 모드 활성화.

### 팀 구성

```
TeamCreate("fix-{bug}")
├── Lead (Opus): 오케스트레이션 + 빌드 검증
├── impl-correctness (★Opus): 버그 수정 (Primary Worker)
└── Cross-model 검증 (Lead가 검증 실행)
```

### 통신 패턴: Pair Programming (경량, Peer-to-Peer)

```
impl-correctness: 원인 분석 + 수정 → SendMessage(team-lead): "수정 완료. 빌드 검증 요청"
Lead: 빌드 검증
  → 이슈 시 SendMessage(impl-correctness): "피드백: {내용}. 반영해주세요"
  → impl-correctness 수정 → 재검증
  → 완료
```

---

## 복잡도 판단 및 스킬 전환

### 자동 전환 트리거

| 신호 | 전환 대상 |
|------|----------|
| 3개+ 파일 수정 필요 | `/fz-code` |
| 아키텍처 변경 필요 | `/fz-plan` |
| 새 모듈 생성 | `/fz-plan` → `/fz-code` |
| 코드 탐색/구조 분석 | `/fz-search` |
| 리뷰 검증 원하는 경우 | `/fz-review` |
| 3회 이상 수정 반복 | /simplify 시도 → `/fz-plan` 전환 |

---

---

## Gate: Bug Fix Complete
- [ ] ⛔ ASD 패턴 또는 저장 여부 질문 완료?
- [ ] WORK_DIR 결정됨? (ASD / NOTASK / Serena fallback)
- [ ] 빌드 성공?
- [ ] 원인-수정 대응 명확?
- [ ] 아티팩트 기록 완료? (ASD: `{WORK_DIR}/fix/fix-analysis.md`, 비ASD: `write_memory("fz:checkpoint:fix-{bug}", "원인: {요약}. 수정: {파일}. 빌드: OK")`)

---

## Few-shot 예시

```
BAD (원인 분석 없이 수정):
증상: "탭 전환 시 크래시"
수정: guard let 추가
→ 근본 원인(nil 상태 도달 경로) 미분석. 증상만 숨김.

GOOD (원인 분석 → 수정 → 빌드):
증상: "탭 전환 시 크래시"
Phase 1: 크래시 로그 분석 → HomeInteractor.didBecomeActive()에서 nil
Phase 2: find_symbol → listener가 detach 후 nil인데 호출됨 → weak var 미적용
Phase 3: weak var + optional chaining 적용 → 빌드 성공
```

```
BAD (복잡 버그에 fz-fix 사용):
"5개 모듈에 걸친 상태 불일치 버그"
→ 영향 범위가 넓어 fz-fix 범위 초과. /fz-search → /fz-plan → /fz-code가 적절.

GOOD (복잡도 초과 시 전환):
Phase 1 분석 후 영향 범위 3개 모듈+ → "복잡도 초과. /fz-search로 전환 권장" 보고.
```

---

## Boundaries

/ralph-loop 한도 후에도 실패하면 근본 원인을 재분석한다. 복잡도 초과 시 즉시 전환한다.

**Will**:
- 빠른 버그 수정 + 빌드 검증
- 복잡도 초과 시 적절한 스킬 전환 제안

**Will Not**:
- 코드 탐색/구조 분석 (→ /fz-search)
- 새 기능 구현 (→ /fz-plan + /fz-code)
- 대규모 리팩토링 (→ /fz-plan)
- 풀 코드 리뷰 (→ /fz-review)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| Serena 연결 실패 | Grep + Glob 폴백 | 수동 탐색 |
| 빌드 반복 실패 | /ralph-loop 래더 (modules/execution-modes.md) | 사용자 에스컬레이션 |
| 심볼 못 찾음 | 패턴 검색 전환 | Grep 폴백 |
| 복잡도 초과 | /fz-plan 전환 | 사용자 상담 |

## Completion → Next

- 버그 수정 완료: 사용자에게 보고 + 테스트 방법 안내
- 복잡한 수정: `/fz-review` 제안
- 탐색 필요: `/fz-search` 제안
- 탐색 후 변경 필요: `/fz-plan` 또는 `/fz-code` 제안
