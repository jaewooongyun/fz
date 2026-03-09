---
name: fz-code
description: >-
  코드 구현 + 빌드 검증 스킬. 계획 기반 점진적 구현과 매 Step 빌드 검증.
  Use when implementing new features, writing new code modules, or building planned functionality.
  Do NOT use for bug fixes (use fz-fix) or code review (use fz-review).
user-invocable: true
argument-hint: "[구현 대상 설명]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__replace_symbol_body,
  mcp__serena__insert_after_symbol,
  mcp__serena__insert_before_symbol,
  mcp__serena__rename_symbol,
  mcp__serena__find_file,
  mcp__serena__write_memory,
  mcp__serena__read_memory,
  mcp__serena__edit_memory,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  mcp__lsp__diagnostics_delta,
  mcp__lsp__hover,
  Edit, Write, Read, Bash(xcodebuild *), Bash(cd *)
team-agents:
  primary: impl-correctness
  supporting: [review-arch, impl-quality, memory-curator]
composable: true
provides: [code-changes]
needs: [planning]
intent-triggers:
  - "구현|코드|만들어|개발"
  - "implement|code|develop|build"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-code - 구현 + 빌드 검증 스킬

> **행동 원칙**: 검증된 계획을 기반으로 점진적으로 코드를 구현하고, 매 Step마다 빌드 검증을 수행한다. 빌드 성공을 확인한 후 다음 Step으로 진행한다.

## 개요

> Step N 구현 → 빌드 검증 → (실패: 에러 수정 → 재빌드) → Gate 3 → /fz-review

- 점진적 구현 + 매 Step 빌드 검증
- 프로젝트 빌드 검증
- 리뷰 검증은 `/fz-review`로 위임 가능

## 사용 시점

```bash
/fz-code "검증된 계획대로 구현해줘"
/fz-code "Step 1만 먼저 구현해줘"
/fz-code "빌드 에러 수정해줘"
/fz-code "Gate 3 통과 확인해줘"
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 (TeamCreate 강제 + 상호 통신) |
| modules/session.md | 세션 감지, Issue Tracker 연동 |
| modules/build.md | 빌드 검증 |
| modules/execution-modes.md | LOOP + SIMPLIFY 실행 모드 |
| modules/memory-policy.md | Serena Memory 키 네이밍 + GC 정책 |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |

## Plugin 참조 (SwiftUI + Swift Concurrency)

> 참조: `modules/plugin-refs.md` — SwiftUI Expert(구현 시) + Swift Concurrency(구현 시) 섹션
> SwiftUI View 작업 시 `swiftui-expert` 플러그인 패턴 참조
> **iOS 16 최소 타겟**: `@Observable`/`@Bindable` → `#available(iOS 17, *)` 필수. 기본은 `ObservableObject`/`@StateObject`
> 자동 감지: 코드에 SwiftUI/Concurrency 패턴 발견 시 플러그인 적극 참조 (트리거 목록: `modules/plugin-refs.md`)

## sc: 활용 (SuperClaude 연계)

| 상황 | sc: 명령어 | 용도 |
|------|-----------|------|
| 복잡한 다중 파일 구현 | `/sc:implement` | SuperClaude 위임 |
| 빌드 실패 | `/sc:troubleshoot` | 에러 원인 자동 분석/수정 |
| 빌드 프로세스 | `/sc:build` | 빌드 최적화 |
| Step 완료 후 | `/sc:analyze` | 구현 코드 즉석 품질 체크 |
| Step 완료 후 | `/sc:reflect --type task` | 요구사항 부합 자체 검증 (3+ Step 구현 시만) |
| API 불확실 | Context7 + `/sc:explain` | 문법/API 확인 |

## 팀 에이전트 모드

> 팀 모드 규칙은 `.claude/modules/team-core.md` 참조

### 팀 구성

```
TeamCreate("code-{feature}")
├── Lead (Opus): 오케스트레이션 + 빌드 검증
├── impl-correctness (★Opus): 점진적 구현 (Primary Worker)
├── review-arch (Sonnet): 구현 중 아키텍처 감시
├── impl-quality (Sonnet): 코딩 표준 + 패턴 일관성 실시간 피드백 [supporting]
├── memory-curator (Sonnet): 관련 교훈 발굴 + impl-correctness에 직접 전달 [선택적: --deep 또는 복잡도 4+]
└── Cross-model 검증 (Lead가 검증 실행)
```

> impl-quality는 각 Step 완료 시 impl-correctness에게 패턴 일관성 피드백. Lead에게 보고하지 않고 impl-correctness와 직접 통신.

> ASD 폴더 활성 시: `{WORK_DIR}/code/code-team.md`에 pair programming 핵심 통신을 기록한다.

### 통신 패턴: Pair Programming (Peer-to-Peer)

impl-correctness와 review-arch가 **직접 대화하며** 코드를 만드는 패턴.
Lead를 거치지 않고 직접 SendMessage로 소통한다.

```
구현 중:
  impl-correctness → SendMessage(review-arch): "UseCase에서 두 Repo 조합, Workflow로 빼야 할까요?"
  review-arch → SendMessage(impl-correctness): "네, Workflow가 맞습니다. 기존 패턴: {참고}"
  impl-correctness → 구현 → SendMessage(review-arch): "Workflow 완료. 검토해주세요"
  review-arch → SendMessage(impl-correctness): "LGTM"
  양쪽 → SendMessage(team-lead): "Step N 완료"
  Lead: 빌드 검증 → 다음 Step
```

**핵심**: 구현 **중간에** 아키텍처 질문을 바로 해결. 다 만들고 뒤집기가 아니라 만들면서 확인.

> impl-correctness 에이전트가 이 스킬의 워크플로우를 활용합니다.

---

## 구현 도구 선택 기준

| 상황 | 도구 | 비고 |
|------|------|------|
| 기존 함수/메서드 수정 | `mcp__serena__replace_symbol_body` | 심볼 단위 정밀 수정 |
| 새 메서드/프로퍼티 추가 | `mcp__serena__insert_after_symbol` | 기존 심볼 뒤에 삽입 |
| 파일 시작에 코드 추가 | `mcp__serena__insert_before_symbol` | import 등 |
| 심볼 이름 변경 | `mcp__serena__rename_symbol` | 참조 자동 업데이트 |
| 새 파일 생성 | `Write` + `/fz-new-file` | 헤더 규칙 준수 |
| 복잡한 다중 파일 | `/sc:implement` | SuperClaude 위임 |
| 단순 텍스트 수정 | `Edit` | 간단한 인라인 수정 |

---

## 구현 절차

> **프로젝트 규칙**: CLAUDE.md `## Architecture` 섹션을 따른다.

1. **세션 감지**: 참조 `modules/session.md`

1.5. **ASD 컨텍스트 로딩** (ASD 폴더 활성 시):
   - `{WORK_DIR}/plan/plan-final.md` 읽기 → 승인된 계획 복원
   - `{WORK_DIR}/discover/constraints.md` 읽기 → 제약 조건 복원 (있으면)

2. **계획의 각 Step을 순서대로 구현**
   - 각 Step은 명확한 완료 조건을 가짐

3. **구현 마찰 감지** (Implementation Friction Detection):
   각 Step 구현 중 아래 신호 감지 시 멈추고 사용자에게 보고:

   | 마찰 신호 | 감지 기준 | 의미 |
   |----------|----------|------|
   | 분기 폭증 | 같은 대상에 대한 switch/if/enum case 3개+ | 추상화가 변형을 통합하지 못함 |
   | 코드 반복 | 유사 구조의 코드를 복사-수정 3회+ | 공통 추상화 필요 |
   | 소비자 판별 로직 | ViewModel/Listener에 "어떤 X인지" 판별 코드 발생 | 하위 복잡도가 상위로 전이됨 |
   | workaround | 계획에 없던 우회 코드 작성 | 설계와 현실의 불일치 |
   | 잔존 패턴 | Plan의 Anti-Pattern Constraints에 명시된 금지 패턴이 기존 코드에 여전히 존재 | 리팩토링 미완성 — 해당 패턴 제거/대체 필요 |
   | 불필요한 영속화 | UserDefaults/Keychain/CoreData에 저장하는 코드 작성 시, 해당 상태가 컴포넌트 라이프사이클(RIBs Interactor 생존 기간)로 충분한데 영속 저장소에 중복 저장 | 앱 재시작 후에도 유지해야 하는지 먼저 확인. A/B 테스트 배정값 등 외부 시스템 관리 값은 로컬 캐싱 금지 |
   | 파라미터 미전달 | 래퍼 함수 시그니처에 파라미터가 있지만, 내부 SDK/라이브러리 호출에 해당 파라미터를 전달하지 않음 | 파라미터가 무시되어 기능이 무효화됨 — SDK API의 해당 오버로드 존재 여부 확인 필수 |
   | 검증 유보 | TODO/FIXME로 "나중에 전환", "추후 적용" 등 검증 없이 현재 구현을 정당화하는 주석 작성 | 이미 가능한 작업을 지연시킴 — 주석 작성 전에 실제로 불가능한지 SDK/API 확인 필수 |
   | 주석-추상화 불일치 | 범용 유틸/래퍼 클래스에 특정 기능 맥락의 주석 작성 (예: 범용 A/B 테스트 래퍼에 "카드형 Default" 주석) | 주석의 추상화 수준이 코드의 추상화 수준과 일치해야 함 — 범용 코드엔 범용 주석 |

   보고 형식:
   ```
   ⚠️ 구현 마찰 감지

   **신호**: {감지된 마찰 유형}
   **위치**: {파일:심볼}
   **현상**: {구체적 현상}
   **플랜 재검토 추천**: 예/아니오
   ```

   > 사용자가 "계속"이라고 해야 진행. 마찰 감지 시 무시 강행 금지.

   **잔존 패턴 사전 검사** (Anti-Pattern Constraints가 있는 Plan에서만):
   Plan에 Anti-Pattern Constraints 테이블이 포함된 경우, 구현 시작 전 + 각 Step 완료 후에
   해당 Grep 패턴으로 코드베이스를 검사합니다.

   ```
   절차:
   1. Plan의 Anti-Pattern Constraints 테이블에서 "검증 Grep 패턴" 컬럼 추출
   2. 각 패턴에 대해 Grep 실행 (대상: 변경 파일 + 관련 모듈)
   3. 매칭 발견 시 → "잔존 패턴" 마찰 신호로 보고
   4. 모든 잔존 패턴이 제거/대체될 때까지 해당 Step 완료 불가
   ```

4. **API 문법 확인** (불확실할 때 + SDK 래퍼 작성 시 필수):
   - `mcp__context7__query-docs` → 정확한 문법/시그니처
   - `/sc:explain` → API 사용법 설명
   - **SDK 래퍼 원칙**: 래퍼 함수의 모든 파라미터가 내부 SDK 호출에 전달되는지 확인. SDK에 해당 파라미터를 받는 오버로드가 있는지 반드시 검증

5. **(선택) /simplify 게이트**: 코드 변경이 있을 때 `/simplify focus on {step-context}` (참조: modules/execution-modes.md)

6. **매 Step 완료 후 빌드 검증**: 참조 `modules/build.md`

6.5. **⛔ 아티팩트 기록** (항상 — compact recovery 필수):
   각 구현 Step 완료 후 진행 상태를 기록한다.
   - ASD 활성: `{WORK_DIR}/code/step-{N}.md` + `progress.md` + `index.md` 업데이트
   - 비ASD: `write_memory("fz:checkpoint:code-step{N}", "Step {N}/{M}: {변경 파일}. 빌드: OK/FAIL. 결정: {요약}")`
   형식 참조: `modules/context-artifacts.md`

7. **요구사항 부합 검증** (3+ Step 구현에서만):
   - `/sc:reflect --type task` → 현재까지의 구현이 계획에 부합하는지 확인
   - 조건: 전체 Step이 3개 이상인 구현의 중간 지점에서 실행
   - 목적: 방향 이탈 조기 발견 → 토큰 낭비 방지

8. **Issue Tracker에 빌드 이슈 기록** (실패 시)

8.5. **⛔ Codex 교차 검증** (TEAM 모드 — 생략 금지):
   모든 Step 구현 완료 후, Gate 3 진입 전에 Lead가 실행한다.
   ```bash
   /fz-codex check "구현 코드 교차 검증"
   ```
   - 에이전트 구현 결과를 cross-model로 검증
   - 실패 시: 재시도 1회 → 실패 사실 기록 후 /sc:analyze 폴백
   - SOLO 모드에서는 선택 (TEAM에서는 필수)

### 빌드 실패 대응

참조: `modules/build.md` — 에러 유형별 대응표, 빌드-수정 반복 패턴

/ralph-loop 에스컬레이션 래더 적용 (참조: modules/execution-modes.md)

---

## Gate 3: Implementation Complete

- [ ] 모든 Step 구현 완료?
- [ ] 빌드 성공? (프로젝트 빌드 검증 통과)
- [ ] 빌드 경고 최소화?
- [ ] 아키텍처 패턴 준수?
- [ ] ⛔ 아티팩트 기록 완료? (ASD: 파일, 비ASD: Serena checkpoint)
- [ ] ⛔ Codex 교차 검증 완료? (TEAM 모드 — Lead가 /fz-codex check 실행)

---

## Few-shot 예시

```
BAD (마찰 무시):
Step 3 완료. if-else 5개 추가.
→ 분기 폭증 감지 안 함

GOOD:
Step 3 마찰 감지: ContentType 분기 5개 → Strategy 패턴 검토 필요
- 현재: switch contentType { case .movie: ... case .series: ... case .live: ... }
- 원인: ContentDetailInteractor가 모든 타입을 직접 처리
- 제안: ContentDetailStrategy 프로토콜 + 타입별 구현 분리
- 판단: Step 4에서 분리 진행 (3개 이상 분기는 전략 패턴)
```

## Boundaries

빌드 성공을 확인한 후 다음 Step으로 진행한다.

**Will**:
- 검증된 계획 기반 점진적 코드 구현
- Serena 심볼 도구 활용 정밀 편집
- 프로젝트 빌드 검증
- 빌드 에러 자동 수정

**Will Not**:
- 계획 없이 대규모 코드 생성 (→ /fz-plan)
- 코드 리뷰/검증 (→ /fz-review)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| XcodeBuildMCP 실패 | Bash로 xcodebuild 직접 | 수동 빌드 |
| Serena 연결 실패 | Edit + Write 직접 수정 | 수동 편집 |
| 빌드 반복 실패 | /ralph-loop 래더 (modules/execution-modes.md) | 사용자 에스컬레이션 |

## Completion → Next

Gate 3 통과 후:
```bash
/fz-review "구현한 코드 리뷰해줘"
```
