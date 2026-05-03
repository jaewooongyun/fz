# Phase 1: Deep Planning 본문

> 본 모듈은 fz-plan SKILL.md Phase 1의 절차 본문을 담는다. SKILL은 Gate 1 + reference만 유지 (Progressive Disclosure Level 3).
> 발동: fz-plan Phase 1 진입 시 자동 Read.

## ⛔ Phase 1 Gate는 SKILL.md에 보존 (트리밍 비저하 원칙 — single source: `guides/prompt-optimization.md` §1 보충 3a)

본 module은 **본문(절차)만** 담는다. Gate 1 체크리스트와 Why(H1)는 `skills/fz-plan/SKILL.md`에 남는다 (실행 핵심).

---

## 절차

> **프로젝트 규칙**: CLAUDE.md `## Architecture` 섹션을 따른다.

### 절차 1. 요구사항 구조 분해

- /fz-discover의 `landscape-map`이 있으면 → 경로 비교 기반으로 최적 경로를 선택하고 영향 분석으로 진입
- /fz-discover의 `open-questions`가 있으면 → 구조 분해 시 해당 질문을 우선 탐색
- /fz-discover의 `trade-off-table`이 있으면 → Direction Challenge(Phase 0.5)에서 이미 비교된 경로 활용
- 없으면 → `mcp__sequential-thinking__sequentialthinking` → 단계별 분해 (기존 절차)

### 절차 2. 코드베이스 영향 분석

- `mcp__serena__find_symbol` → 변경 대상 심볼 확인
- `mcp__serena__find_referencing_symbols` → 영향받는 심볼/파일
- `mcp__serena__search_for_pattern` → 기존 유사 구현 패턴

#### ⛔ Exhaustive Impact Scan

> TEAM 모드에서는 plan-impact 에이전트가 이 단계를 전담 수행한다 (병렬).

심볼 기반 탐색 후 반드시 아래 4단계를 수행한다:

a. **텍스트 전수 검색**: 대상 타입/클래스명으로 `Grep` 전수 검색.
   심볼 기반에서 찾은 참조와 대조하여 **빠진 참조**가 없는지 확인.
   특히 문자열 참조, 글로벌 hook, extension 내 사용을 잡는다.
b. **런타임 도달성 검증**: 발견된 각 진입점(호출부)에 대해 실제 런타임에 도달 가능한지 확인.
   코드 경로가 존재해도 UI 바인딩(gesture/button)이 없거나, feature flag로 비활성이면 "latent(잠재)" 표기.
   검증 방법: 진입점의 view layer까지 추적하여 trigger가 존재하는지 확인.
c. **사이드이펙트/순서 분석**: 리팩토링 대상의 기존 액션 패턴에서 순서 의존성 식별.
   예: `dismiss(animated:) completion → action` 패턴은 순서가 바뀌면 동작이 달라짐.
   각 액션의 전제조건(pre-condition)과 부작용(side-effect)을 나열.
d. **Dead code 감지**: 변경 대상과 관련된 파일에서 미사용 헬퍼/메서드 식별.
   `find_referencing_symbols` 결과가 0이면 dead code 후보 → 이관 대상에서 제외 + 삭제 후보로 기록.
e. **⛔ 소비자 코드 품질 스캔** (모듈화/캡슐화 작업 시 필수):
   모듈 경계를 만드는 작업에서는 경계 양쪽을 모두 분석해야 한다.
   `Grep(pattern="import {모듈명}", path=앱 소스 루트)` → 앱 측 소비자 파일 전수 수집.
   각 소비자의 사용 패턴이 모듈 설계 의도와 일치하는지 확인.
   앱 생명주기 진입점(AppDelegate, SceneDelegate, UIWindow extension 등)의 모듈 연동 코드 확인.
   계획에 소비자 코드 변경 Step을 명시적으로 포함.
f. **⛔ Import Removal Symbol Inventory** (import 제거 작업 시 필수):
   `import X`를 제거할 파일 목록에 대해, X 모듈에서 가져오던 **모든** 심볼을 추출.
   치환 패턴 테이블에 포함되지 않은 심볼 → 누락 후보로 플래그.
   특히 typealias(`Parameters`), utility 타입(`Empty`), convenience method가 빠지기 쉬움.
   방법: 대상 파일에서 대문자 시작 심볼 추출 → 제거할 모듈 소속 여부 확인.

### 절차 3. API/라이브러리 문서 확인

- `mcp__context7__resolve-library-id` → 라이브러리 ID
- `mcp__context7__query-docs` → 최신 API 문서, 호환성
- **라이브러리 버전업 시**: Context7로 새 버전 API 확인. 동일 동작을 가장 적은 코드로 표현하는 것이 진짜 최소 변경이다 (bridge 유지보다 native 직접 호출이 코드가 적으면 전환). 단, 동작 변경(프로토콜 시그니처, 실행 순서)은 최소 변경의 범위 밖이다.

### 절차 4. Clean Architecture 원칙 확인 (새 레이어/모듈 설계 시)

- `guides/clean-architecture.md` 참조 — Dependency Rule, SOLID, Uncle Bob's Decision Rules
- 설계가 Dependency Rule을 위반하지 않는지 자문: "안쪽이 바깥을 아는가?"

### 절차 5a. SuperClaude 연계 (필요 시)

- `/sc:design` → 새 아키텍처 설계
- `/sc:brainstorm` → 요구사항 탐색
- `/sc:analyze` → 기존 코드 심층 분석
- `/sc:research` → 외부 기술 조사
- `/sc:workflow` → PRD/요구사항 → 구현 워크플로우 자동 생성 (트리거: 구현 Step이 5개 이상 예상될 때)
- `/sc:spec-panel` → 아키텍처 스펙 전문가 패널 리뷰 (트리거: 새 모듈 생성 시, --deep 옵션 시) (모드: `--mode critique --focus architecture`)

### 절차 5b. 설계 스트레스 테스트 (Design Stress Test)

계획의 핵심 설계 결정(새 타입, 패턴 변경, 추상화 도입 등)에 대해 6가지 질문으로 스트레스 테스트.
- `mcp__sequential-thinking__sequentialthinking` → 설계 결정별 순차 검증

| 질문 | 내용 | 실패 시 행동 |
|------|------|-------------|
| Q1 다중성 | 이 설계가 1개일 때와 N개일 때 동일하게 작동하는가? | 다중 시나리오에서 소비자 영향 추가 분석 |
| Q2 소비자 영향 | 변경의 소비자(상위 레이어)에 새 분기/타입/프로토콜이 필요한가? | 소비자 변경을 계획에 포함 |
| Q3 복잡도 이동 | 한 레이어의 단순화가 다른 레이어의 복잡도 증가로 이어지는가? | 이동 대상 레이어의 변경도 계획에 포함 |
| Q4 경계 케이스 | 이 추상화가 커버하지 못하는 케이스는 무엇이고, 대안은? 상태 저장이 포함된 설계라면: 이 상태가 컴포넌트 라이프사이클 밖(앱 재시작)에서도 유지되어야 하는가? RIBs Interactor/VC가 살아있는 동안 인메모리(Subject/State)로 충분하지 않은가? A/B 테스트 등 외부 시스템이 관리하는 값을 앱 로컬에 캐싱하면 실험 왜곡 위험. | 대안 패턴 제시 + 하이브리드 가능성 검토. 영속화 불필요 판정 시 인메모리 대안 제시 |
| Q5 접근 경계 | "차단/제거/캡슐화"를 의도한 접근 경로가 실제로 차단되는가? access modifier(public/internal/private)가 의도와 일치하는가? 기존 코드가 이벤트 채널을 우회하여 직접 호출하는 경로가 남아있지 않은가? **모듈화 작업 시 추가**: 모듈에 추가하는 각 public 타입에 대해 — (a) 타입의 필드/메서드가 모듈 책임 범위에 속하는가? (b) 도메인 특화 필드(비즈니스명, 하드코딩 UI 문자열)가 있는가? (c) 모듈 내부에서 실제 사용하는가, 아니면 pass-through인가? 하나라도 경계 밖이면 모듈에서 제외. | 접근 제어 변경을 계획에 포함 + Anti-Pattern Constraints에 금지 패턴 기록. 모듈화 시: Concern Classification 테이블 작성 |
| Q6 이벤트 스코프 | 이벤트/로그 전송이 포함된 설계라면: 각 이벤트가 명시된 측정 목적에 부합하는가? 모든 사용자에게 동일하게 발화하는 이벤트(impression 등)가 A/B 분류 목적에 포함되어 있지 않은가? 이벤트 발화 위치의 컨텍스트가 측정 대상과 일치하는가? (예: 전체 콘텐츠 재생 이벤트에 라이브 전용 A/B 프로퍼티 추가는 스코프 불일치) | 불필요한 이벤트 제거 + 이벤트별 측정 목적 명시 |

- 각 질문에서 리스크 발견 → 리스크 매트릭스에 기록
- Q4에서 대안 패턴 최소 1개 필수 제시
- Q5는 리팩토링/캡슐화 작업에서 특히 중요 — 기존 코드의 잔존 접근 경로를 Grep으로 사전 검색
- 6가지 질문 모두 "문제없음"이면 → 그 판단 근거를 명시 (빈 리스크 = 분석 부족 의심)
- **Evaluator-Optimizer**: Q1-Q6에서 Critical 리스크 2개+ 발견 시 → 계획 자동 재작성 (최대 2회 반복)
  - 1회차: Critical 리스크를 계획에 반영하여 재작성 → 스트레스 테스트 재실행
  - 2회차: 여전히 Critical 2개+ → 사용자 에스컬레이션 (AskUserQuestion: "리스크 수용/계획 변경/중단")
  - LOOP 모드 파라미터: `completion-promise: STRESS_TEST_PASS`, `max-iterations: 2`

### 절차 6. ⛔ RTM 작성 (plan 포함 파이프라인에서 필수 — 참조: `modules/rtm.md`)

- 각 요구사항에 Req-ID 부여 → Step 매핑 → 검증 방법 명시
- discover 정제된 요구사항이 있으면 1:1 매핑

### 절차 7. 구조화된 계획 출력

- 구현 단계 목록 (Step별 변경 대상, 방법)
- 영향받는 심볼/파일 목록
- 필요한 API/라이브러리 정보
- **리스크 매트릭스**: 설계 스트레스 테스트에서 발견된 리스크
  | 리스크 | 발생 조건 | 영향 레이어 | 대응 |
  |--------|----------|-----------|------|
- **소비자 변경 요약**: Q2에서 식별된 상위 레이어 변경사항
- **대안 패턴**: Q4에서 제시된 대안 + 현재 선택의 근거
- **Anti-Pattern Constraints** (리팩토링 후 금지 패턴):
  리팩토링/캡슐화 작업에서 필수. 리팩토링 후 코드베이스에 존재하면 안 되는 패턴 목록.
  /fz-code의 잔존 패턴 검사와 /fz-review의 enforcement 검증에서 이 목록을 사용한다.
  | # | 금지 패턴 | 검증 Grep 패턴 | 위반 시 영향 |
  |---|----------|---------------|-------------|
  예시: `| 1 | proxy 외부 접근 | \.proxy\. | 식별 가능 → 목표 무력화 |`
  변경 유형별 잔존물 참조: `modules/lead-reasoning.md` §7
- **Implication Register**: `modules/lead-reasoning.md` §4 형식. 실행 함의는 Step에 명시, 관찰 함의는 별도 섹션.

### 절차 8. ⛔ Transformation Spec 작성 (비동기/네트워크/UI 패턴 변환 Step에 필수)

> 참조: `modules/code-transform-validation.md`

- 원본 코드 Read → 런타임 특성 추출 (스레드, 에러 경로, 실행 보장)
- Context7로 원본 API 동작 확인 (PromiseKit .done = main queue 등)
- Spec 테이블 작성 (실행 스레드, 에러 처리, 실행 보장, 추상화, 인스턴스, 디코딩)
- ⚠️ After 줄 수 > Before 2배 → 추상화 설계 필수 제안
- ⚠️ 언어 런타임 제약 확인 (Swift: defer+await 금지, catch if case, @MainActor 위치)
- ⛔ **Default-Deny**: 각 기술적 주장에 `[verified: source]` 태그 의무화. 태그 없으면 자동 unverified → fz-code BEC에서 차단. `modules/uncertainty-verification.md` 참조
- **요청 파라미터 키 목록**: 원본 API 호출의 파라미터 키를 열거. After에서 키 추가/삭제 시 명시적 근거 필수. nil → default value 전송은 "키 추가"에 해당
- **spec-version**: Transformation Spec에 `spec-version: 3.8` 필드 추가

### 절차 9. ⛔ 계획 파일 기록 (항상 — compact recovery 필수)

- ASD 활성: `{WORK_DIR}/plan/plan-v{N}.md` + `{WORK_DIR}/index.md` 업데이트
- 비ASD: `write_memory("fz:checkpoint:plan-v{N}", "Steps: {N}개. 핵심결정: {요약}. 리스크: {요약}")`
형식 참조: `modules/context-artifacts.md`

---

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시 Read)
- Phase 1 Gate 1은 SKILL.md에 보존 (트리밍 비저하 — single source: `guides/prompt-optimization.md` §1 보충 3a)
- 가이드 문서이므로 줄 수 제한 없음
