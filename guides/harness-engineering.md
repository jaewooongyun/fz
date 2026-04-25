# Harness Engineering Guide

> "하네스의 모든 컴포넌트는 모델이 혼자 할 수 없는 것에 대한 가정을 인코딩한다.
> 그 가정은 스트레스 테스트할 가치가 있다."
> — Prithvi Rajasekaran, Anthropic Labs

AI 에이전트의 오케스트레이션 레이어를 체계적으로 설계하는 실무 가이드.
Anthropic 공식 엔지니어링 블로그, arxiv 논문, 오픈소스 구현체를 기반으로 정리했다.

---

## 1. 핵심 정의

### 1.1 Harness vs Scaffolding vs Prompt Engineering

| 개념 | 정의 | 범위 | 시점 | 예시 |
|------|------|------|------|------|
| **Prompt Engineering** | 단일 모델 호출의 입력을 최적화 | 개별 상호작용 | 호출 전 | 시스템 프롬프트 작성, few-shot 예시 |
| **Scaffolding** | 에이전트의 정적 구조 — 프롬프트 구성, 스키마, 팩토리 어셈블리 | 빌드 타임 구조 | 빌드 시 | 도구 스키마 정의, 에이전트 팩토리 |
| **Harness** | 에이전트의 런타임 오케스트레이션 — 도구 실행, 컨텍스트 관리, 안전 강제, 세션 영속화 | 런타임 전체 | 실행 중 | Gate 체크, Context Reset, 에스컬레이션 |
| **Context Engineering** | 유한한 컨텍스트 윈도우에서 최적의 정보를 선택·배치·유지하는 기법 | 컨텍스트 윈도우 | 매 턴 | Compaction, Dual-Memory, Reminders |

> 출처: OpenDev 논문 — Scaffolding은 "에이전트의 정적 구조", Harness는 "도구 실행, 컨텍스트 관리, 안전 강제, 세션 영속화를 조율하는 런타임 오케스트레이션 레이어"

비유: 말(모델) + 마구(하네스) + 마부(엔지니어). 하네스가 말의 힘을 생산적 방향으로 전환한다.

### 1.2 Harness의 구성 요소 (NLAH 형식 정의)

NLAH 논문은 하네스를 6가지 구성 요소로 형식화한다:

```
Harness H = (C, R, S, A, Σ, F) where:
  C = Contracts       — 입력/출력 스키마 + 검증 게이트 (예: "diff가 RTM의 모든 Req-ID를 커버해야 함")
  R = Roles           — 역할별 책임 분리 (예: Planner, Generator, Evaluator)
  S = Stage Structure — 워크로드 토폴로지 (예: Plan → Code → Review 순차, 또는 병렬 검증)
  A = Adapters        — 결정론적 연산 (예: Grep, git diff, 빌드 명령)
  Σ = State Semantics — 크로스스텝 영속화 (예: progress.txt, Serena Memory, ASD 폴더)
  F = Failure Taxonomy — 복구 분류 (예: 재시도, 에스컬레이션, 롤백, 중단)
```

> 출처: NLAH 논문 (청화대/HIT, arxiv 2603.25723)

이 형식의 가치: 하네스를 **분석 가능한 과학적 객체**로 만든다. 각 구성 요소를 독립적으로 교체·제거(ablation)·비교할 수 있다.

### 1.3 Infrastructure Layer vs Application Layer 구분

> 참조: Anthropic "Scaling Managed Agents: Decoupling the Brain from the Hands" (2026-04-08, https://www.anthropic.com/engineering/managed-agents)

Anthropic은 **managed agents**를 `Brain (model reasoning)` + `Hands (tool execution)`로 분리하는 **인프라 레이어** 패턴을 제시. 구성: `Session` + `Harness` + `Sandbox`. 이 3-component는 OS/infrastructure 수준의 관심사.

fz의 `Lead + Teammate` (TeamCreate + SendMessage)는 **애플리케이션 레이어**의 다관점 협업 패턴. Brain/Hands의 subset이 아니라 다른 계층.

| 계층 | Anthropic Brain/Hands | fz Lead/Teammate |
|------|----------------------|------------------|
| 목적 | 모델 실행 격리 + 보안 + 스케일링 | 다관점 검토 + 역할 분리 |
| 범위 | 인프라 (Session/Harness/Sandbox) | 애플리케이션 (에이전트 협업) |
| 중복 여부 | fz는 Brain/Hands **위에서** 작동 — 상호 대체 아님 |

**독자 주의**: Anthropic "Scaling Managed Agents" 글의 핵심 표현은 **"many brains, many hands"** — 이는 인프라 수준의 모델 실행/도구 격리 패턴. fz Lead/Teammate는 애플리케이션 수준의 역할 협업 패턴이므로 혼용 금지.

---

## 2. 왜 Harness인가

### 2.1 모델만으로는 해결되지 않는 4가지 문제

| 문제 | 현상 | 구체적 예시 | 하네스 해결 |
|------|------|-----------|-----------|
| **무상태** | 세션 간 기억 없음 | "교대 근무 엔지니어가 이전 기억 없이 출근" | 세션 영속화 + 핸드오프 아티팩트 |
| **자신감 있는 오류** | 자기 평가 시 과대 평가 | "명백히 깨진 게임을 '모든 기능이 작동합니다'로 평가" | Generator≠Evaluator 분리 |
| **컨텍스트 불안** | 긴 작업에서 일관성 상실 | Sonnet 4.5/4.6가 윈도우 한도 근처에서 조기 마무리 (Opus 4.6/4.7에서 개선, 다만 "shallow long-context adaptation" [미검증: Claude 실측 부재]) | Context Reset + 구조화된 핸드오프 |
| **무제한 접근** | 통제 없는 도구 접근 | `rm -rf /`, force push, 비밀 파일 읽기 | 권한 계층 + 스키마 필터링 |

> 출처: Anthropic 공식 — "자기 작업을 평가하라고 하면, 에이전트는 품질이 명백히 떨어져도 자신있게 칭찬하는 경향"

### 2.2 핵심 근거: 프레임워크 변경만으로 성능 향상

| 출처 | 변경 | 모델 변경 | 결과 |
|------|------|----------|------|
| LangChain 벤치마크 | 하네스 설계만 수정 | 없음 | 52.8% → 66.5% (**+13.7%p**) |
| NLAH 논문 | 코드 하네스 → 자연어 하네스 | 없음 | 30.4% → 47.2% (**+16.8%p**) |
| Anthropic Solo vs Harness | Solo → 3-Agent | 동일 모델 | $9/깨진 게임 → $200/완전한 앱 |

> 하네스 설계가 모델 능력보다 더 큰 병목이다. 모델을 바꾸기 전에 하네스를 먼저 개선하라.

---

## 3. 5대 기둥 (Five Pillars)

### 기둥 1: Tool Orchestration (도구 오케스트레이션)

도구의 접근 범위, 호출 방법, 권한 체계를 정의한다.

**3가지 접근 수준**:

| 수준 | 설명 | 구현 예시 |
|------|------|----------|
| **스키마 수준 필터링** | 허용되지 않은 도구가 아예 보이지 않음 | OpenDev: Plan 모드에서 쓰기 도구 스키마 제거 |
| **런타임 승인** | 도구 호출 시 승인 요청 | Claude Code: Manual/Semi-Auto/Auto 3단계 |
| **결과 수준 검증** | 도구 실행 후 결과 검증 | Stale-read 감지, 출력 크기 제한 |

```
원칙: 에이전트가 시도할 수 없는 것은 실패할 수 없다.
방법: 런타임 체크가 아닌 스키마 수준 필터링 (도구 자체가 보이지 않음)

BAD:  도구 호출 → 런타임에서 "권한 없음" 에러 반환 → 에이전트가 우회 시도
GOOD: 도구 자체가 스키마에 없음 → 에이전트가 존재를 모르므로 시도 불가
```

> 출처: OpenDev 논문 — "스키마 수준 도구 필터링이 런타임 체크보다 효과적"

**도구 카테고리 분류** (OpenDev 7개 카테고리):

| 카테고리 | 도구 예시 | 위험도 |
|----------|---------|--------|
| 파일 읽기 | read_file, list_files, search | Low |
| 파일 쓰기 | write_file, edit_file | Medium |
| 셸 실행 | run_command, kill_process | High |
| 코드 분석 | find_symbol, find_referencing_symbols | Low |
| 웹 상호작용 | browser automation, API 호출 | Medium |
| 서브에이전트 위임 | spawn_agent, send_message | Medium |
| 외부 도구 발견 | MCP tool discovery | Low |

**Lazy Tool Discovery**: MCP 도구를 사전에 모두 로드하지 않고 필요할 때만 발견한다. 프롬프트 버짓 절약 + 불필요한 도구 노출 방지.

### 기둥 2: Guardrails & Safety (안전 제약)

결정론적 규칙이 여러 계층에서 동작한다.

**Defense-in-Depth (깊이 방어) — 5계층 모델**:

```
Layer 1: Prompt-Level Guardrails
  ├── 보안 정책 (비밀 파일 접근 금지)
  ├── 행동 안전 (파괴적 명령 금지)
  ├── 읽기 우선 (수정 전 반드시 읽기)
  └── Git 워크플로우 (force push 금지)

Layer 2: Schema-Level Restrictions
  ├── Plan 모드: 읽기 도구만 화이트리스트
  ├── 서브에이전트별 도구 필터링
  └── MCP 게이팅 (신뢰되지 않은 MCP 차단)

Layer 3: Runtime Approval
  ├── Manual: 모든 도구 호출에 사용자 승인
  ├── Semi-Auto: 패턴 기반 자동 승인 (git status → auto, rm -rf → manual)
  └── Auto: 신뢰된 도구 자동 실행

Layer 4: Tool-Level Validation
  ├── 위험 명령 블록리스트 (sudo, rm -rf /)
  ├── Stale-read 감지 (오래된 파일 스냅샷 방지)
  ├── 출력 크기 제한 + 자동 요약
  └── 실행 타임아웃

Layer 5: Lifecycle Hooks
  ├── Pre-hook: 도구 실행 전 사용자 스크립트
  ├── Post-hook: 실행 후 검증 스크립트
  └── Session hooks: 시작/종료 시 정리
```

> "단일 실패 지점이 시스템을 위험에 빠뜨리지 않는다." — OpenDev 논문

**claude-code-harness의 13개 가드레일 규칙 상세**:

| Rule | 보호 대상 | 동작 | 근거 |
|------|----------|------|------|
| R01 | `sudo` 명령 | **Deny** | 권한 상승 방지 |
| R02 | `.git/`, `.env`, 비밀 파일 | **Deny** (쓰기) | 보안 자격 증명 보호 |
| R03 | 보호 파일에 셸 쓰기 | **Deny** | 간접 우회 방지 |
| R04 | 프로젝트 외부 쓰기 | **Ask** | 범위 벗어남 경고 |
| R05 | `rm -rf` | **Ask** | 파괴적 삭제 확인 |
| R06 | `git push --force` | **Deny** | 이력 파괴 방지 |
| R07-R09 | 모드별 + 비밀 읽기 | 컨텍스트 인식 | 상황별 판단 |
| R10 | `--no-verify`, `--no-gpg-sign` | **Deny** | 안전 우회 방지 |
| R11 | `git reset --hard main` | **Deny** | 작업 손실 방지 |
| R12 | main/master 직접 push | **Warn** | 브랜치 정책 |
| R13 | 보호 파일 편집 | **Warn** | 설정 파일 변경 인지 |
| Post | `it.skip`, assertion 조작 | **Warning** | 테스트 무력화 방지 |
| Perm | `git status`, `npm test` | **Auto-allow** | 안전한 읽기 명령 |

**핵심 교훈**: "제약이 많을수록 오히려 안정성이 높아진다." — 승인 피로를 줄이려면 패턴 기반 자동 승인(Semi-Auto)을 활용한다.

### 기둥 3: Context Engineering (컨텍스트 관리)

컨텍스트 윈도우가 하네스 설계의 **핵심 병목**.

> "컨텍스트 압력은 중심 제약이다. 유한한 윈도우 안에서 가장 유용한 정보를 배치하는 것이 핵심." — OpenDev 논문

**6개 서브시스템** (OpenDev 논문) — 각각 상세:

#### 서브시스템 1: Dynamic System Prompt

시스템 프롬프트를 우선순위 기반 조건부 섹션으로 구성한다.

```
섹션 구조 (priority 기반):
  Priority 10-30: Core Identity (에이전트 역할, 기본 행동)
  Priority 40-50: Tool Guidance (도구 사용 규칙)
  Priority 55-65: Code Quality (코딩 표준, 아키텍처)
  Priority 70-80: Conditional Sections (모드별, 프로바이더별)
  Priority 85-95: Context Awareness (프로젝트별 설정)

장점: 각 섹션을 독립적으로 로드/언로드 가능. 토큰 예산 초과 시 낮은 우선순위부터 제거.
```

**프롬프트 캐싱**: 고정 섹션(Priority 10-50)을 프로바이더 수준에서 캐싱하여 매 호출마다 재전송하지 않음. 토큰 비용 절감 + 지연 감소.

#### 서브시스템 2: Tool Result Optimization

도구 실행 결과가 컨텍스트를 빠르게 소진한다. 최적화 전략:

```
도구별 요약:
  read_file (1000줄) → 요청된 범위만 표시 + "나머지 N줄 생략" 힌트
  run_command (긴 출력) → 마지막 50줄 + "전체 N줄, 처음 M줄 생략" 힌트
  search (100+ 매치) → 상위 20개 + "추가 N개 매치 존재" 힌트

대형 출력 오프로딩:
  결과 > 임계값 → 임시 파일에 저장 → "결과가 /tmp/result.txt에 저장됨" 참조만 유지
```

#### 서브시스템 3: Dual-Memory Architecture

```
Episodic Memory (크로스 세션 — 느리지만 영속적)
├── CLAUDE.md / AGENTS.md — 프로젝트 지침
├── Memory files — 과거 교훈, 결정 이력
├── Progress files — 이전 세션 진행 상태
└── Git history — 코드 변경 이력

Working Memory (현재 대화 — 빠르지만 휘발적)
├── 현재 작업 상태 + 활성 목표
├── 최근 도구 결과 (요약된)
├── 활성 컨텍스트 (열린 파일, 진행 중 편집)
└── 시스템 리마인더

→ 결합 주입: Episodic에서 관련 항목만 선택 → Working에 주입
→ 토큰 폭발 방지: Episodic 전체를 로드하지 않고 관련성 기반 필터링
```

**fz 생태계 대응**: Episodic = ASD 폴더 + Serena Memory, Working = 대화 컨텍스트 + 스킬 로드

#### 서브시스템 4: System Reminders (Instruction Fade-out 대응)

> "20-30턴 후 시스템 프롬프트의 지침이 약해진다." — OpenDev 논문

```
문제: 시스템 프롬프트에 "파일 수정 전 반드시 읽어라"고 명시해도,
      30턴 후에는 읽지 않고 수정하는 경향이 나타남.

해결: 이벤트 기반 리마인더를 조건부로 주입

트리거 예시:
  - 안전 지표 위반 감지 시 → 안전 리마인더 주입
  - 도구 호출 패턴 이상 시 → 행동 리마인더 주입
  - N턴마다 주기적 → 핵심 규칙 리마인더
  - 특정 도구 사용 후 → 관련 가이던스 주입

형식: 변수 치환 + 가드레일 카운터 포함 템플릿
  예: "현재까지 {N}개 파일을 수정했습니다. 각 수정 전 Read를 실행했는지 확인하세요."
```

**fz 생태계 대응**: `modules/execution-modes.md`의 LOOP 에스컬레이션, 마찰 감지의 조건부 보고

#### 서브시스템 5: Adaptive Compaction

토큰 예산이 고갈되면 5단계로 점진 압축:

```
Stage 1: 오래된 도구 결과 요약 (90% → 10%)
Stage 2: 중간 추론 단계 제거 (결론만 유지)
Stage 3: 초기 대화 턴 요약 (핵심 결정만)
Stage 4: 시스템 프롬프트 저우선순위 섹션 제거
Stage 5: Emergency — 최소 컨텍스트만 유지 (현재 목표 + 최근 3턴)
```

#### 서브시스템 6: Context Retrieval Pipeline

새 작업 시작 시 관련 컨텍스트를 4계층으로 수집:

```
Layer 1: Anchor Selection — 사용자 요청에서 핵심 키워드/심볼 추출
Layer 2: Agentic Search — Code Explorer 서브에이전트로 의미적 탐색
Layer 3: Context Assembly — 발견된 파일/심볼을 우선순위로 조립
Layer 4: Optimization — 토큰 예산에 맞춰 압축/선택
```

### 기둥 4: Error Recovery & Feedback Loops (에러 복구)

| 메커니즘 | 역할 | 구현 예시 | 에스컬레이션 |
|----------|------|----------|-------------|
| **자동 재시도** | 일시적 실패 복구 | API 타임아웃 → 3회 재시도 | 3회 실패 → 다음 단계 |
| **자기 검증 루프** | 커밋 전 작업 검증 | 빌드 실행 → 테스트 → 린트 | 실패 → 수정 → 재시도 |
| **롤백** | 상태 복원 | git stash/reset, 스냅샷 복원 | 롤백 실패 → 사용자 개입 |
| **Doom-loop 감지** | 무한 반복 방지 | 같은 에러 3회 반복 → 자동 중단 | 중단 → 사용자 에스컬레이션 |
| **에스컬레이션 래더** | 단계별 상승 | Retry → Simplify → Replan → User | 최종 → 사용자 결정 |

**에스컬레이션 래더 상세** (fz의 /ralph-loop 패턴):

```
Level 1: 동일 전략으로 재시도 (최대 2회)
Level 2: 전략 변경 (다른 도구, 다른 접근)
Level 3: 범위 축소 (부분 구현, 단순화)
Level 4: 계획 재수립 (원인 분석 → 새 계획)
Level 5: 사용자 에스컬레이션 (선택지 제시)
```

### 기둥 5: Observability & Human-in-the-Loop (관찰 + 인간 개입)

**관찰**:

| 관찰 대상 | 기록 형식 | 용도 |
|----------|----------|------|
| 모든 에이전트 액션 | agent-trace.jsonl | 디버깅, 감사 |
| 토큰 사용량 | 턴별 집계 | 비용 관리 |
| 결정 지점 | 선택지 + 선택 이유 | 행동 분석 |
| Gate 통과/실패 | 체크리스트 상태 | 품질 추적 |
| 에러 + 재시도 | 에러 유형 + 횟수 | 패턴 식별 |

**Human-in-the-Loop 전략적 배치**:

```
BAD:  모든 액션에 승인 요청 → 사용자 피로 → 무의식적 승인 → 안전 무력화
GOOD: 고레버리지 지점에만 승인 → 파괴적 변경, 범위 확장, Gate 실패 시

고레버리지 지점:
  1. 파이프라인 제안 승인 (fz Phase 4)
  2. 파괴적 명령 실행 (rm, force push)
  3. 범위 외 변경 감지 (scope creep)
  4. Gate 실패 시 재시도/스킵/중단 결정
  5. 비용 임계값 초과 (토큰/API 비용)
```

---

## 4. 에이전트 아키텍처 패턴 (상세)

### 패턴 A: Initializer + Coding Agent (Anthropic Phase 1, 2025.11)

**문제**: 에이전트가 세션 간 기억이 없어 매번 처음부터 시작.

**해결**: Initializer가 한 번 환경을 설정하면, 이후 Coding Agent가 N번 반복.

```
Initializer Agent (1회, 15-30분)
├── init.sh 생성
│   ├── 의존성 설치 명령
│   ├── 개발 서버 시작 명령
│   └── 환경 변수 설정
├── feature_list.json 생성 (200+ 기능)
│   ├── 각 기능: category + description + steps + passes(false)
│   └── 에이전트가 편집/삭제 금지 (테스트만 pass로 변경 가능)
├── claude-progress.txt 생성 (빈 파일)
└── git init + 초기 커밋
```

**Feature List JSON 형식** (Anthropic 공식):

```json
{
  "category": "functional",
  "description": "New chat button creates a fresh conversation",
  "steps": [
    "Navigate to main interface",
    "Click the 'New Chat' button",
    "Verify a new conversation is created",
    "Check that chat area shows welcome state",
    "Verify conversation appears in sidebar"
  ],
  "passes": false
}
```

> "에이전트에게 지시: '테스트를 제거하거나 편집하는 것은 허용되지 않는다. 이는 기능 누락이나 버그로 이어질 수 있다.'"
> 출처: Anthropic 공식 (2025.11)

**Coding Agent 세션 프로토콜** (매 세션 시작):

```
1. pwd           → 작업 디렉토리 확인
2. progress.txt  → 최근 작업 내용 파악
3. feature_list  → 미완료 기능 중 최우선순위 선택
4. git log       → 최근 커밋 이력 확인
5. init.sh       → 개발 서버 시작
6. 기본 테스트    → 기존 기능 동작 확인
7. 구현 시작     → 선택한 1개 기능만
8. 브라우저 테스트 → Puppeteer/Playwright로 사용자 동작 재현
9. git commit    → 진행 상태 저장
10. progress.txt → 이번 세션 작업 내용 기록
```

**실패 모드와 대응**:

| 실패 모드 | 현상 | Initializer 대응 | Coding Agent 대응 |
|----------|------|-----------------|-------------------|
| 조기 완료 선언 | "모든 기능 완료" (실제로 미완) | 200+ 기능 목록 (전부 failing) | 세션 시작 시 feature_list 읽기 |
| 버그 투성이 코드 | 테스트 안 된 코드 방치 | git repo + progress.txt | 시작 시 검증 테스트 실행 |
| 기능 완료 표시 오류 | 테스트 없이 "passing" | feature_list 편집 금지 규칙 | 브라우저 자동화로 실제 테스트 |
| 환경 설정 반복 | 매 세션마다 설정 | init.sh 스크립트 | init.sh 실행으로 즉시 시작 |

**적합**: 중규모 웹 앱, 단일 에이전트 반복 작업, 10-50 세션 장기 프로젝트

### 패턴 B: Three-Agent GAN-Inspired (Anthropic Phase 2, 2026.03)

**문제**: 단일 에이전트의 자기 평가가 신뢰할 수 없고, 품질 천장에 부딪힘.

**해결**: GAN에서 영감받아 Generator와 Evaluator를 분리. Planner가 스펙을 확장.

```
Planner Agent ($0.46, 5분)
├── 입력: 1-4문장 사용자 프롬프트
├── 출력: 종합 제품 스펙
│   ├── 기능 목록 + 우선순위
│   ├── 기술 스택 결정 (React+Vite+FastAPI+SQLite)
│   ├── AI 기능 통합 기회 식별
│   └── 고수준 아키텍처 (상세 구현 X)
└── 핵심: 구현 세부사항이 아닌 "무엇을 만들 것인가"에 집중. 스펙 오류는 하류로 전파됨.

Generator Agent ($71, 2-3시간)
├── 스프린트 단위 구현
├── React + Vite + FastAPI + SQLite/PostgreSQL
├── 자기 평가 (스프린트 끝) — 단, 이것만으로는 불충분
├── Git 버전 관리
└── 전략적 결정: 현재 방향 개선 or 미학적 방향 전환

Evaluator Agent ($10, 30분)
├── Playwright MCP로 실제 사용자처럼 앱 조작
│   ├── 인터페이스 클릭
│   ├── API 엔드포인트 테스트
│   ├── 데이터베이스 상태 검증
│   └── 스크린샷 촬영 + 시각적 검증
├── 4가지 기준으로 채점 (아래 상세)
└── "Sprint Contract" — 구현 시작 전 성공 기준 정의
```

**에이전트 간 통신**: 파일 기반

```
Planner → product-spec.md → Generator가 읽기
Generator → sprint-progress.md → Evaluator가 읽기
Evaluator → evaluation-feedback.md → Generator가 읽기
Generator → 개선 후 → sprint-progress.md 업데이트
→ 5-15 반복 (최대 4시간)
```

**채점 기준 프레임워크 (프론트엔드 디자인)**:

| 기준 | 가중치 | 설명 | 왜 이 가중치인가 |
|------|--------|------|----------------|
| **Design Quality** | 높음 | 색상·타이포·레이아웃·이미지로 고유한 분위기 창출 | Claude가 자연적으로 약한 영역 |
| **Originality** | 높음 | 템플릿/기본값이 아닌 커스텀 결정의 증거 | Claude가 기본값에 안주하는 경향 |
| **Craft** | 보통 | 타이포 위계, 간격, 색상 조화, 대비 | Claude가 자연적으로 잘하는 영역 |
| **Functionality** | 보통 | 미학과 무관한 사용성 | Claude가 자연적으로 잘하는 영역 |

> "채점 기준의 문구 자체가 모델 출력을 조향한다. 평가자 피드백 이전에도."
> 예: "최고의 디자인은 박물관 수준"이라는 문구 → Generator가 갤러리 미학을 향해 수렴

**Evaluator 튜닝 과정** (Anthropic 실전 경험):

```
초기 문제: Evaluator가 이슈를 발견하고도 "그렇게 나쁘지 않다"로 자기 설득
  → 인간이 보면 명백한 결함을 놓침

튜닝 프로세스:
  1. Evaluator 로그를 체계적으로 읽기
  2. 인간 판단과 Evaluator 판단의 괴리 식별
  3. 프롬프트를 반복 수정
     - "문제를 발견하면 심각도를 낮추지 마라"
     - "레이아웃 깨짐은 Major, 작은 간격 문제는 Minor"
     - 구체적 few-shot: "이 스크린샷은 D등급이다. 이유: ..."
  4. 여러 개발 사이클 후 "합리적" 수준 도달

남은 한계:
  - 미묘한 레이아웃 차이 감지 어려움
  - 직관적이지 않은 인터랙션 놓침
  - 중첩된 기능의 버그 미발견
```

**Retro Game Maker 사례 비교**:

| 측면 | Solo Run ($9, 20분) | Full Harness ($200, 6시간) |
|------|---------------------|--------------------------|
| 엔티티 시스템 | 동작 안 함 | 완전 작동 + 행동 템플릿 |
| 스프라이트 편집 | 기본 그리기만 | 애니메이션 + 프레임 편집 |
| AI 기능 | 없음 | AI 기반 스프라이트/레벨 생성 |
| 공유 | 없음 | 내보내기 + 공유 URL |
| 게임플레이 | 비기능적 | 완전한 플레이 모드 |

**DAW (디지털 오디오 워크스테이션) 사례** (Opus 4.6 시점, 2025-11):

```
비용 분석:
  Planner:          $0.46 (1분)
  Build Round 1:    $71.08 (2시간)
  QA Rounds:        $10.39 (30분)
  Build Rounds 2-3: $42.77 (1시간 20분)
  총:               $124.70 (3시간 50분)

완성된 기능:
  ✓ Arrangement View (트랙 배치)
  ✓ Mixer (볼륨/팬/뮤트)
  ✓ Transport Controls (재생/정지/녹음)
  ✓ 자율 에이전트 기반 작곡 (도구 호출로 트랙 조작)

QA가 발견한 개선 사항:
  - 오디오 녹음 미구현 → Build 2에서 추가
  - 클립 조작 미흡 → Build 2에서 개선
  - 이펙트 시각화 부재 → Build 3에서 추가
```

**적합**: 프론트엔드 디자인, 풀스택 앱 자율 개발, 4-8시간 자율 세션

### 패턴 C: Plan→Work→Review→Release (claude-code-harness)

실무 워크플로우를 4단계 동사로 구조화. **TypeScript 런타임 가드레일**이 핵심 차별점.

```
/harness-plan     → Plans.md 생성
                    ├── 태스크 분해
                    ├── 수용 기준 (Acceptance Criteria)
                    └── 의존성 그래프

/harness-work     → 병렬 구현
                    ├── Preflight Check (Plans.md 존재 확인)
                    ├── V1-V5 Task Validation
                    ├── Progressive Batching (병렬 워커)
                    └── Hook-driven Signals (진행 추적)

/harness-review   → 4관점 리뷰
                    ├── Security: 보안 취약점
                    ├── Performance: 성능 이슈
                    ├── Quality: 코드 품질
                    └── Accessibility: 접근성

/harness-release  → 릴리스
                    ├── CHANGELOG 자동 생성
                    ├── 시맨틱 버전 태깅
                    └── GitHub Release 핸드오프
```

**Breezing 모드 (에이전트 팀 자율 실행)**:

```bash
/harness-work breezing all                    # 계획 리뷰 + 병렬 구현
/harness-work breezing --no-discuss all       # 계획 리뷰 스킵, 바로 구현
/harness-work breezing --codex all            # Codex 엔진에 위임
```

**2-Agent 모드 (Cursor 연동)**:

```
Cursor (PM 역할) → Plans.md 작성/수정
Claude Code (구현자) → Plans.md 기반 구현
  → /harness-release handoff → Cursor에게 리포트
```

**적합**: 팀 프로젝트, CI/CD 통합, 프로덕션 안전, 가드레일이 중요한 환경

### 패턴 D: NLAH — Natural-Language Agent Harness (학술)

하네스 로직을 실행 가능한 자연어 아티팩트로 외부화.

```
NLAH 구성:
├── Contracts: "Planner는 requirements.md를 입력받아 plan.md를 출력해야 한다.
│              plan.md는 최소 3개 Step을 포함해야 한다."
├── Roles: "Planner: 요구사항 분해 전담. Coder: 구현 전담. Reviewer: 검증 전담."
├── Stage Structure: "Plan → [Code, Test] (병렬) → Review → Fix → Review"
├── Adapters: "빌드 검증은 `npm test` 실행 결과로 판단한다."
├── State Semantics: "plan.md는 모든 Stage에서 읽기 가능. code-output/는 Coder만 쓰기 가능."
└── Failure Taxonomy: "빌드 실패 → 재시도(2회) → Coder에게 에러 전달 → 3회 실패 → 중단"

Intelligent Harness Runtime (IHR):
├── in-loop LLM: 위 자연어 하네스를 직접 해석하여 실행 흐름 결정
├── Backend: 터미널 실행 + 멀티에이전트 인터페이스
└── Runtime Charter: 계약 + 상태 + 오케스트레이션 규칙
```

**핵심 실험 결과** (SWE-bench Verified, GPT-5.4):

| 조건 | Resolution | 차이 |
|------|-----------|------|
| Baseline (단순 루프) | ~65% | — |
| + Self-evolution | ~70% | **+4.8%** |
| + File-backed state | ~67% | **+1.6%** |
| + Evidence-backed answering | ~67% | **+1.6%** |
| + Verifier | ~64% | **-0.8%** (오히려 하락) |
| + Multi-candidate search | ~63% | **-2.4%** (오버헤드) |
| Full IHR | ~74% | — |

> "구조는 중간 행동에서 평가자 수용까지의 경로를 좁힐 때 도움이 되지만, 오버헤드가 큰 레이어는 오히려 해롭다."

**코드 → 자연어 마이그레이션 결과** (OS-Symphony):

| 구현 | 성공률 | 행동 변화 |
|------|--------|----------|
| 네이티브 코드 | 30.4% | GUI 복구 중심 |
| NLAH (자연어) | **47.2%** | 파일 아티팩트 + 지속 상태 중심 |

> "자연어 하네스가 안정성 메커니즘을 화면 복구 루프에서 지속 가능한 상태 검증으로 재배치했다."

**적합**: 학술 연구, 하네스 패턴 비교/ablation, 이식 가능한 에이전트 설계

---

## 5. 실전 설계 원칙

### 원칙 1: 가장 단순한 해결책을 먼저 찾아라

> "필요한 경우에만 복잡도를 높여라." — Anthropic 공식 (2026.03)

```
결정 체계:
  단일 프롬프트 → 멀티턴 → 단일 에이전트 + 도구 → 멀티세션 → 멀티에이전트

각 단계에서 "이것으로 충분한가?"를 먼저 확인한 후에만 다음 단계로 이동.
Sprint 구조, 멀티에이전트 평가 등은 모델이 혼자 못 할 때만 가치가 있다.
```

### 원칙 2: 새 모델이 나오면 하네스를 재검토하라

> "모든 하네스 컴포넌트는 모델이 혼자 못 하는 것에 대한 가정. 그 가정을 스트레스 테스트하라."

**Anthropic의 실제 재검토 사례** (Opus 4.6 전환 시점 [미검증: Opus 4.7 공식 하네스 재검토 포스트 부재]):

| 컴포넌트 | Sonnet 4.5 시절 | Opus 4.6 이후 | Opus 4.7 (2026-04-16 GA) | 변경 이유 |
|----------|---------------|-------------|--------------------------|----------|
| Sprint 분해 | 필수 (세분화 없으면 혼란) | **제거** | [미검증: 공식 재검토 포스트 부재. 잠정 4.6 동일] | 계획 능력 향상으로 불필요 |
| 스프린트별 평가 | 매 스프린트마다 | **최종 1회만** | [미검증: 동일] | 장문 컨텍스트 능력으로 중간 점검 불필요 |
| Context Reset | 필수 (Compaction 불충분) | **선택** | [미검증: 동일. tokenizer 1.00-1.35x 영향 자체 실측 필요] | Compaction 품질 향상 |
| Evaluator | 항상 실행 | **조건부** | [미검증: 동일] | 단순 작업은 혼자 충분 |

> "평가자는 고정된 예/아니오 결정이 아니다. 현재 모델이 혼자서 안정적으로 못 하는 작업에서만 비용 대비 가치가 있다."

### 원칙 3: 구조가 도움이 되려면 경로를 좁혀야 한다

> "구조는 중간 행동에서 평가자 수용까지의 경로를 좁힐 때 도움이 되지만, 오버헤드가 큰 레이어는 오히려 해롭다." — NLAH 논문

```
GOOD: Self-evolution (+4.8%) — 풀이 루프를 좁혀서 시행착오 줄임
GOOD: File-backed state (+1.6%) — 프로세스 구조화 + 감사 가능성
BAD:  Multi-candidate search (-2.4%) — 탐색 공간이 넓어져 오히려 수렴 지연
BAD:  Verifier (-0.8%) — 평가자와의 정렬 충돌

교훈: "구조를 추가하기 전에 — 이 구조가 경로를 좁히는가, 넓히는가?"
```

### 원칙 4: 자기 평가를 믿지 마라 — Generator≠Evaluator

> "자기 작업을 평가하라고 하면 자신있게 칭찬한다 — 품질이 떨어져도."

**분리 전략**:

```
Level 1 (기본): Generator가 구현 → 다른 LLM 호출이 평가
  장점: 단순. 단점: 같은 blind spot 공유 가능.

Level 2 (권장): Generator ≠ Evaluator (별도 프롬프트 + 채점 기준)
  장점: 외부 피드백 루프. 단점: 비용 2배.

Level 3 (강력): Generator ≠ Evaluator + 다른 모델
  장점: 이종 모델 blind spot 보완. 단점: 비용 + 통합 복잡도.
  예: fz의 Cross-model Verification (Claude + Codex). cross-provider 확장 (Gemini 등)은 측정 데이터 누적 후 결정 (현재 비채택).
```

### 원칙 5: 점진적 진행이 일발 완성보다 낫다

> "한 번에 복잡한 앱을 만들려는 시도는 일관되게 실패한다." — Anthropic 공식 (2025.11)

```
BAD:  "전체 앱을 한 세션에 만들어라" → 일관성 상실, 조기 마무리, 미완성
GOOD: "세션당 1개 기능만. 매 세션 끝에 깨끗한 상태 인계."

핵심 메커니즘:
  1. Feature List (200+) — "완료" 선언 불가 (failing 기능이 항상 남아있음)
  2. Git Commit — 매 세션 끝 커밋 (롤백 가능)
  3. Progress File — 다음 세션이 이전 작업을 이해
  4. 단일 기능 집중 — 스코프 크리프 방지
```

### 원칙 6: 명시적 테스트가 조기 종료를 방지한다

> "브라우저 자동화 도구를 제공하면 에이전트가 코드만으로는 발견 못 하는 버그를 식별하고 수정한다." — Anthropic 공식 (2025.11)

```
도구 없이: "구현 완료했습니다" (실제로 동작 안 함)
도구 있을 때: "클릭 테스트에서 에러 발견 → 수정 → 재테스트 → 통과 확인"

권장 테스트 도구:
  - Playwright MCP: 브라우저 자동화 + 스크린샷 + 인터랙션
  - Puppeteer MCP: 유사 기능, Node.js 기반
  - XcodeBuildMCP: iOS 빌드 + 시뮬레이터 + 스크린샷

한계:
  - 브라우저 네이티브 alert 모달 감지 어려움
  - 비전 한계로 미묘한 레이아웃 차이 놓침
  - 복잡한 드래그앤드롭 인터랙션 재현 어려움
```

---

## 6. Anti-Patterns (하지 말아야 할 것)

### Anti-Pattern 1: 과도한 구조화 (Over-Engineering)

```
증상: 모든 작업에 3-Agent + Sprint + Evaluator 적용
결과: Multi-candidate search처럼 오버헤드가 성능 저하 (-2.4%)
대응: 원칙 1 — 단순한 것부터. 모델이 혼자 못 할 때만 구조 추가

진단 질문: "이 컴포넌트를 제거하면 성능이 떨어지는가?"
  → YES → 유지 (load-bearing)
  → NO → 제거
```

### Anti-Pattern 2: 자기 평가 의존

```
증상: Generator에게 "잘했는지 자체 평가해봐" 요청
결과: "모든 기능이 완벽하게 작동합니다" (실제로 깨져있음)
대응: 원칙 4 — Generator≠Evaluator 분리

예외: 자기 검증이 유효한 경우
  - 빌드 성공/실패 (객관적 판단)
  - 테스트 통과/실패 (도구 기반)
  - 린트 경고 존재 (자동 검출)
  → 주관적 판단(디자인 품질, 코드 품질)에서만 분리 필수
```

### Anti-Pattern 3: Compaction만으로 장기 세션 운영

```
증상: 50+ 턴을 Compaction만으로 유지
결과: 초기 결정의 근거 손실, 컨텍스트 불안, 조기 마무리
대응: Context Reset + 핸드오프 아티팩트

예외: Opus 4.6+ 1M context는 Compaction 충분 [verified: Anthropic 2026.03 재검토 포스트].
     Opus 4.7에서도 동등 동작은 [미검증: 공식 재검토 포스트 부재, 잠정 4.6 패턴 유지].
     tokenizer 1.00-1.35x 증가 [미검증: Korean 실측 부재] — L1/L2 크기 영향 자체 측정 필요.
```

### Anti-Pattern 4: 모든 액션에 승인 요청

```
증상: read_file, git status에도 승인 요청
결과: 사용자 피로 → 무의식적 "승인" 클릭 → 위험한 명령도 그냥 통과
대응: Semi-Auto 승인 (안전한 패턴 자동 허용) + 고레버리지 지점에만 수동

규칙: "승인 피로는 안전의 적이다. 적게 물을수록 진지하게 답한다."
```

### Anti-Pattern 5: 하네스 고정 (Model-Agnostic Harness)

```
증상: 모델이 바뀌어도 동일 하네스 유지
결과: 새 모델 능력 활용 못함, 불필요한 오버헤드 유지
대응: 원칙 2 — 새 모델마다 하네스 재검토

Anthropic 실제 사례:
  Sonnet 4.5: Sprint 분해 필수 → Opus 4.6: Sprint 제거 (2025-11)
  Opus 4.7 (2026-04-16 GA): [미검증 — 공식 재검토 포스트 부재. 자체 실측 필요]
  이렇게 제거된 컴포넌트가 "모델이 성장한 증거"
```

### Anti-Pattern 6: 채점 기준 없는 평가

```
증상: Evaluator에게 "이 코드가 좋은지 평가해" (기준 없음)
결과: 매번 다른 기준으로 평가 → 일관성 없음
대응: 명시적 채점 기준 + 가중치 + few-shot 예시

BAD:  "이 디자인을 평가하세요"
GOOD: "Design Quality(40%), Originality(30%), Craft(20%), Functionality(10%)로 평가하세요.
       A: 박물관 수준, B: 전문 에이전시, C: 보통, D: 초보, F: 미완성"
```

---

## 7. 실전 구현 체크리스트

### 처음 하네스를 만들 때 (6단계)

```
Step 1: 범위 정의
  □ 에이전트가 할 수 있는 것 / 할 수 없는 것 명시
  □ 접근 가능한 도구 목록
  □ 금지 행동 목록

Step 2: 설정 파일 생성
  □ CLAUDE.md / AGENTS.md 작성 (프로젝트 규칙)
  □ 아키텍처 패턴 + 코딩 컨벤션 문서화
  □ 디렉토리 구조 가이드

Step 3: 피드백 루프 수립
  □ 최소 루프: 구현 → 빌드/테스트 → 수정
  □ 중급 루프: 구현 → 빌드 → 리뷰 → 수정
  □ 고급 루프: 계획 → 구현 → 빌드 → 리뷰 → 검증 → 수정

Step 4: 가드레일 추가
  □ 파괴적 명령 차단 (rm -rf, force push)
  □ 보호 파일 경고 (.env, credentials)
  □ 범위 외 변경 감지
  □ 린트/타입 체크 강제

Step 5: 관찰 장치 설치
  □ 에이전트 액션 로깅
  □ 토큰 사용 추적
  □ Gate 통과/실패 기록

Step 6: 인간 개입 지점 설계
  □ 파이프라인 승인 (시작 전)
  □ 파괴적 변경 승인
  □ Gate 실패 시 결정
  □ 비용 임계값 경고
```

### 하네스 스트레스 테스트 질문

```
Q1: 이 컴포넌트를 제거하면 성능이 떨어지는가? (load-bearing 테스트)
Q2: 현재 모델이 혼자서 이 작업을 안정적으로 할 수 있는가? (모델 의존성)
Q3: 이 구조가 경로를 좁히는가, 넓히는가? (효율성)
Q4: 사용자 승인 지점이 너무 많지 않은가? (승인 피로)
Q5: 장기 세션(50+ 턴)에서도 컨텍스트가 유지되는가? (내구성)
Q6: 에이전트가 실패했을 때 복구 경로가 있는가? (회복력)
```

---

## 8. Multi-Agent 통신 패턴 (상세)

### 패턴 비교표

| 측면 | 파일 기반 (Anthropic) | P2P SendMessage (fz) | Contract 기반 (NLAH) |
|------|---------------------|---------------------|---------------------|
| **지연** | 높음 (파일 I/O) | 낮음 (메모리) | 중간 |
| **실시간 대화** | 불가 | 가능 | 불가 |
| **디버깅** | 쉬움 (파일 검사) | 어려움 (로그 필요) | 쉬움 (계약 검증) |
| **이식성** | 높음 (파일 시스템) | 낮음 (프레임워크 종속) | 높음 (자연어) |
| **형식 검증** | 없음 | 없음 | 있음 (계약 충족) |
| **적합한 경우** | 비동기 장기 작업 | 실시간 협업 | 학술/이식 |

### 파일 기반 통신의 구체적 구현 (Anthropic)

```
통신 프로토콜:
  1. 에이전트 A가 output.md 작성
  2. 오케스트레이터가 에이전트 B 시작 시 output.md 경로 전달
  3. 에이전트 B가 output.md 읽기 → 작업 → response.md 작성
  4. 오케스트레이터가 에이전트 A에게 response.md 전달

장점:
  - 에이전트 간 직접 의존성 없음 (느슨한 결합)
  - 각 에이전트를 독립적으로 교체/업그레이드 가능
  - 통신 내용이 파일로 남아 감사 가능

단점:
  - 실시간 질문/답변 불가 ("이 방향 맞나요?" → 대기 → 응답 → 대기)
  - 파일 형식 규약이 암묵적 (스키마 없음)
```

### P2P SendMessage의 구체적 구현 (fz 생태계)

```
통신 프로토콜:
  1. TeamCreate("code-feature") → 에이전트 N명 스폰
  2. 각 에이전트에게 피어 목록 + 통신 규칙 전달
  3. impl-correctness: "UseCase에서 두 Repo 조합, Workflow로 빼야 할까요?"
     → SendMessage(review-arch, 질문)
  4. review-arch: "네, Workflow 맞습니다. 기존 패턴: {참고}"
     → SendMessage(impl-correctness, 답변)
  5. 합의 → 양쪽 SendMessage(team-lead, "Step N 완료")

장점:
  - 구현 중간에 아키텍처 질문 즉시 해결
  - "다 만들고 뒤집기"가 아닌 "만들면서 확인"

단점:
  - idle 종료 위험 (에이전트가 오래 대기하면 종료됨)
  - Lead가 중계해야 하는 경우 병목
```

---

## 9. 비용-품질 트레이드오프

### Anthropic 실측 데이터

| 프로젝트 | Solo | Full Harness | 비용 배수 | 품질 차이 |
|----------|------|-------------|----------|----------|
| Retro Game Maker | $9 (20분) | $200 (6시간) | 22x | 동작 안 함 → 완전한 앱 |
| Browser DAW | — | $124.70 (3h50m) | — | 실제 작동하는 DAW |

**비용 구조 분석** (DAW 사례):

```
Planner:    $0.46 (0.4%)  — 스펙 확장은 저렴
Build R1:   $71.08 (57%)  — 초기 구현이 가장 비쌈
QA:         $10.39 (8%)   — 평가는 상대적으로 저렴
Build R2-3: $42.77 (34%)  — 피드백 반영은 초기 구현의 60%
```

> Evaluator 비용은 전체의 8%에 불과하지만 품질 향상 효과는 압도적.

### 비용 최적화 전략

| 전략 | 설명 | 예상 절감 |
|------|------|----------|
| **모델 라우팅** | 주요 추론은 Opus, 경량 작업은 Sonnet | 30-50% |
| **조건부 컴포넌트** | Evaluator는 모델이 혼자 못 할 때만 | 20-40% |
| **프롬프트 캐싱** | 시스템 프롬프트 고정 부분 캐싱 | 10-20% |
| **적응형 깊이** | 단순 작업 → SOLO, 복잡 → TEAM | 작업별 |
| **Early Exit** | 품질 충분 시 추가 반복 중단 | 10-30% |

### ROI 판단 기준

```
하네스 비용이 정당화되는 경우:
  - Solo로 할 수 없는 작업 (multi-feature 앱)
  - 품질이 비즈니스 가치에 직접 영향 (고객 대면 앱)
  - 에이전트 실수 비용이 높은 환경 (프로덕션 배포)

하네스 비용이 과도한 경우:
  - 단순 수정 (한 파일 변경)
  - 탐색/분석 (코드 변경 없음)
  - 잘 알려진 패턴의 반복 작업
```

---

## 10. 적용 결정 프레임워크

### 결정 트리

```
단일 프롬프트로 해결?          → YES → 하네스 불필요
  ↓ NO
멀티턴 대화로 해결?            → YES → 기본 도구 루프 충분
  ↓ NO
세션 간 연속성 필요?            → YES → Initializer 패턴 (A)
  ↓
품질 검증 필요?                → YES → Generator≠Evaluator (B)
  ↓
실시간 에이전트 협업 필요?      → YES → P2P 통신 (fz 패턴)
  ↓
프로덕션 안전 필요?            → YES → TypeScript 가드레일 (C)
  ↓
학술/이식 필요?                → YES → NLAH (D)
```

### 모델 세대별 하네스 조정

| 모델 세대 | 필요한 하네스 | 불필요해진 하네스 |
|-----------|-------------|-----------------|
| Sonnet 4.5 | Context Reset 필수, Sprint 분해 필수, Evaluator 필수 | — |
| Opus 4.6 | Context Reset 선택, Compaction 충분, Evaluator 조건부 | Sprint 분해, 스프린트별 평가 |
| **Opus 4.7 (2026-04-16 GA)** | **[미검증: 공식 재검토 포스트 부재]. 잠정 Opus 4.6 패턴 유지 + tokenizer 1.00-1.35x 증가 주의** | **[미검증]. 자체 실측 후 결정** |
| 미래 모델 | ? | Evaluator? 컨텍스트 관리? |

> "하네스 설계자의 일은 '다음 신기한 조합을 계속 찾는 것'이다." — Anthropic

---

## 11. 측정 지표 (Metrics)

### 하네스 효과 측정

| 지표 | 측정 방법 | 목표 |
|------|----------|------|
| **Task Completion Rate** | 요구된 기능 중 실제 작동하는 비율 | > 90% |
| **Iteration Count** | 목표 달성까지 반복 횟수 | 모델별 기준선 대비 |
| **Cost per Feature** | 기능당 토큰/API 비용 | 지속적 감소 |
| **Evaluator Agreement** | Evaluator 판단과 인간 판단의 일치율 | > 80% |
| **Gate Pass Rate** | 첫 시도에 Gate 통과하는 비율 | > 70% |
| **Recovery Rate** | 실패 후 자동 복구 성공률 | > 60% |
| **Context Utilization** | 컨텍스트 윈도우 중 유용한 정보 비율 | 측정 어려움 |

### NLAH의 Module Ablation 방법론

```
방법: 하네스 모듈을 하나씩 제거하고 성능 변화를 측정

1. Full harness 기준선 측정 (N=125)
2. 모듈 A 제거 → 성능 측정 → 차이 = 모듈 A의 기여도
3. 모듈 B 제거 → 성능 측정 → 차이 = 모듈 B의 기여도
4. 기여도가 음수인 모듈 → 제거 후보

주의: 모듈 간 상호작용이 있어 개별 제거로는 결합 효과를 파악 못함
→ 보완: 2개씩 조합 제거하여 상호작용 효과 측정
```

---

## 12. fz 생태계와의 매핑

| 하네스 패턴 | fz 대응 | 상세 |
|-----------|---------|------|
| Initializer 패턴 | ASD 폴더 + index.md + Serena Memory | 세션 간 상태 영속화 |
| Three-Agent | /fz-plan → /fz-code → /fz-review | 파이프라인 체인 |
| Generator≠Evaluator | impl-correctness(생산) ↔ review-arch(평가) | TEAM Pair Programming |
| 파일 기반 핸드오프 | context-artifacts.md + plan-final.md | ASD 산출물 프로토콜 |
| Context Reset | compact 후 ASD 폴더 Read로 복원 | Essential Context 패턴 |
| Guardrail Rules | Gate 체크리스트 + cross-validation.md + 마찰 감지 | Gate 절차적 강제 |
| Feature List | RTM (Requirements Traceability Matrix) | Req-ID 추적 |
| Sprint Contract | Plan의 Anti-Pattern Constraints | 금지 패턴 + Grep 자동 검증 |
| Evaluator Tuning | 반성 기록 (1-10차) + 교훈 topic file | 실패에서 학습 |
| Implication Reasoning | lead-reasoning.md (2026.04 추가) | 표면→의미론 추론 |
| Cross-model Verification | fz-codex (Claude + Codex; cross-provider 확장 비채택) | 이종 family blind spot 보완 |
| Lazy Tool Discovery | modules/ Progressive Disclosure Level 3 | 필요 시에만 로드 |
| System Reminders | modules/execution-modes.md + 마찰 감지 | Instruction fade-out 대응 |
| Defense-in-Depth | 5계층: SKILL Gate + cross-validation + Team + Codex + Hooks | 다중 검증 레이어 |

### Gap 분석 (NLAH 기반, 2026-04-14)

위 매핑에서 커버되지 않는 하네스 구성요소:

| NLAH 차원 | Gap ID | 내용 | 대응 |
|----------|--------|------|------|
| R (Roles) | G-R1 | SOLO에서 Generator≠Evaluator 무효화 | SOLO 결정론적 검증 삽입 (cross-validation.md § SOLO 모드) |
| S (Stage) | G-S1 | 외부 이벤트(PR 코멘트) 진입점 없음 | pr-comment-review 파이프라인 (pipelines.md #19) |
| F (Failure) | G-F1 | 추론 실패 자동 감지/복구 없음 | Runtime Claim Gate [관찰 모드] (cross-validation.md) |
| Σ (State) | G-Σ1 | 컨텍스트 비용 높음 (스킬 1회 ~5K 토큰) | 인프라 제약 — 현재 전략(모듈 분리 + 500줄 제한) 유지 |

---

## 참고 문헌 (공식/학술/고품질만)

### Anthropic 공식

| # | 제목 | 저자 | 날짜 | URL |
|---|------|------|------|-----|
| 1 | Effective Harnesses for Long-Running Agents | Justin Young | 2025.11.26 | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| 2 | Harness Design for Long-Running Application Development | Prithvi Rajasekaran | 2026.03.24 | https://www.anthropic.com/engineering/harness-design-long-running-apps |
| 3 | Building Effective Agents | Anthropic | 2024 | https://www.anthropic.com/research/building-effective-agents |
| 4 | Claude Agent SDK | Anthropic | 2026 | https://docs.anthropic.com/en/docs/agents-and-tools/claude-agent-sdk |
| 5 | How Claude Code Works | Anthropic | 2026 | https://code.claude.com/docs/en/how-claude-code-works |

### 학술 논문

| # | 제목 | 저자 | 출처 | URL |
|---|------|------|------|-----|
| 6 | Natural-Language Agent Harnesses | Pan et al. (Tsinghua/HIT) | arxiv 2603.25723 | https://arxiv.org/html/2603.25723v1 |
| 7 | Building AI Coding Agents for the Terminal | Bui (OpenDev) | arxiv 2603.05344 | https://arxiv.org/html/2603.05344v1 |

### 고품질 가이드/분석

| # | 제목 | 출처 | URL |
|---|------|------|-----|
| 8 | What Is Harness Engineering? Complete Guide 2026 | NxCode | https://www.nxcode.io/resources/news/what-is-harness-engineering-complete-guide-2026 |
| 9 | Anthropic's Three-Agent Harness (InfoQ) | InfoQ | https://www.infoq.com/news/2026/04/anthropic-three-agent-harness-ai/ |

### 오픈소스 구현체

| # | 프로젝트 | 설명 | URL |
|---|---------|------|-----|
| 10 | claude-code-harness | Plan→Work→Review→Release + 13 Guardrail Rules | https://github.com/Chachamaru127/claude-code-harness |
| 11 | awesome-claude-code-toolkit | 135 agents + 35 skills + 150+ plugins | https://github.com/rohitg00/awesome-claude-code-toolkit |

---

## 설계 원칙

- Level 3 참조 문서 (필요 시에만 Read로 로드)
- 공식/학술/고품질 출처만 인용 (블로그 의견, 비공식 해석 제외)
- fz 생태계와의 매핑으로 실무 적용 연결
- 가이드 문서이므로 줄 수 제한 없음 (자세함이 우선)
