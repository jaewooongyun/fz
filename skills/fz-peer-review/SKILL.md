---
name: fz-peer-review
description: >-
  팀원 코드 피어 리뷰. 3-Model Cross-Review로 9개 관점 독립 분석.
  Use when reviewing a TEAMMATE's pull request or branch code with multi-perspective analysis.
  Do NOT use for reviewing your own code (use fz-review).
user-invocable: true
disable-model-invocation: true
argument-hint: "[PR번호 또는 브랜치명] [--deep] [--post] [--explain]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__find_file,
  mcp__serena__activate_project,
  mcp__sequential-thinking__sequentialthinking,
  mcp__github__get_pull_request,
  mcp__github__get_pull_request_files,
  mcp__github__get_pull_request_comments,
  mcp__github__create_pull_request_review,
  mcp__github__add_issue_comment,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  Bash(git *), Bash(codex *), Read, Grep, Glob
team-agents:
  primary: review-arch
  supporting: [review-quality, review-counter]
composable: false
provides: [peer-review]
needs: [none]
intent-triggers:
  - "피어리뷰|팀원|PR.*리뷰"
  - "peer.?review|teammate|PR.*review"
model-strategy:
  main: opus
  verifier: sonnet
---

# /fz-peer-review - 팀원 코드 피어 리뷰

> **행동 원칙**: 팀원의 PR/브랜치를 3-Model Cross-Review(Opus + Sonnet + Codex)로 독립 분석하고, Confidence Matrix 투표로 객관적 이슈를 도출한다. 칭찬할 건 칭찬하고, 지적할 건 근거와 대안을 함께 제시한다.

## 개요

> Gather → Analyze → Challenge → Synthesize → Deliver

- **9개 관점**: Architecture Decision, Extensibility, Over-Engineering, Functional Decomposition, Modern API, Dependency Impact, **Refactoring Completeness**, **Concurrency Safety** (동시성 코드 포함 시), **Requirements Alignment**
- **3-Model**: Opus(review-arch) + Sonnet(review-quality) + Codex(challenger)
- **Confidence Matrix**: 에이전트 투표 + Devil's Advocate로 편향 보정
- **3-Tier Degradation**: diff 크기 기반 자동 Tier 선택 + 폴백 체인

```bash
/fz-peer-review 123                   # PR #123 리뷰
/fz-peer-review feature/ASD-456       # 브랜치 리뷰
/fz-peer-review 123 --deep            # Cross-Critique 활성화 (추가 ~$0.5-1.5)
/fz-peer-review 123 --post            # gh pr comment로 게시
/fz-peer-review 123 --tier 2          # Tier 강제 지정
/fz-peer-review 123 --explain         # 리뷰 후 변경사항 해설 (fz-pr-digest 연계)
/fz-peer-review 123 --explain --deep  # 리뷰 후 기술 해설까지 포함
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/team-core.md + modules/patterns/ | TEAM 실행 프로토콜 |
| modules/cross-validation.md | get_codex_skill() 3-Tier 디스커버리, GIT_ROOT 추출 |
| modules/plugin-refs.md | Swift 플러그인 참조 (SwiftUI/Concurrency) |

## Plugin 참조 (SwiftUI + Swift Concurrency)

> 참조: `modules/plugin-refs.md` — SwiftUI Expert(리뷰 시) + Swift Concurrency(피어 리뷰 시) 섹션
> diff에 `@MainActor|actor|async|@Observable` 패턴 감지 시 해당 플러그인 참조

## 서브 스킬/스키마 참조

| 스킬/스키마 | 경로 | 역할 |
|------------|------|------|
| arch-critic | `skills/arch-critic/SKILL.md` (글로벌) | 관점 1(Architecture) + 관점 2(Extensibility) |
| code-auditor | `skills/code-auditor/SKILL.md` (글로벌) | 관점 4(Decomposition) + 관점 5(Modern API) + 관점 6(Dependency) + **관점 7(Refactoring Completeness)** |
| challenger 역할 | 3-Tier 디스커버리 (Codex 스킬) | 관점 3(Over-Engineering) + **관점 7 보조(Deprecated Dead Code)** + Devil's Advocate |
| peer_review_schema | `~/.claude/schemas/codex_peer_review_schema.json` | Codex 응답 JSON 구조 |

---

## Step: Gather (컨텍스트 수집)

오케스트레이터가 직접 수행. `WORK_DIR=${PROJECT_ROOT}/peer-review-{PR_NUMBER}` (현재 작업 디렉토리 기준, 쓰기 불가 시 `.claude/tmp/` 폴백).

### ⛔ WORK_DIR 초기화 (Gather 시작 시 반드시 첫 번째로 실행)

> **⛔ 아래 명령을 Gather의 다른 어떤 단계보다 먼저 실행하세요. WORK_DIR이 없으면 이후 모든 산출물 저장이 실패합니다.**

```bash
mkdir -p ${WORK_DIR}
```

확인: `WORK_DIR` 경로를 대화 컨텍스트에 명시적으로 기록한다. 이후 모든 파일 저장은 이 경로를 사용한다.

### 0. 사전 점검

```bash
gh auth status  # 성공→gh 사용, 실패→git 폴백 (git fetch upstream + git diff)
# GIT_ROOT 추출: modules/cross-validation.md의 GIT_ROOT 공유 유틸 참조
```

### 0.5. PR 브랜치 접근 준비

PR 입력 시 PR 브랜치를 로컬에 fetch하여 이후 단계에서 `git show pr-{PR_NUMBER}:{FILE}`로 실제 코드를 직접 참조할 수 있게 한다. Codex DA가 현재 워크트리만 볼 수 있는 sandbox 제약을 우회하기 위해 필수.

```bash
git fetch upstream pull/{PR_NUMBER}/head:pr-{PR_NUMBER}
# 이후: git show pr-{PR_NUMBER}:path/to/File.swift 로 PR 코드 직접 참조
```

### 1. 입력 파싱 + diff 수집

```
PR 번호 입력:
  gh pr view {PR_NUMBER} --json baseRefName,headRefName,title,body,files,additions,deletions
  gh pr diff {PR_NUMBER} > ${WORK_DIR}/diff.patch
  [gh 실패 시] git fetch upstream && git diff upstream/{base}...FETCH_HEAD > ${WORK_DIR}/diff.patch

branch 입력: 베이스 자동 결정
  ├─ feature/* → develop │ hotfix/* → main │ else → AskUserQuestion
  └─ git diff {base}...{target} > ${WORK_DIR}/diff.patch
```

### 2. Serena Pre-caching → `${WORK_DIR}/symbols.json`

```
mcp__serena__get_symbols_overview       → 변경 파일 심볼 목록
mcp__serena__find_referencing_symbols   → 변경 심볼의 참조 관계
mcp__serena__find_symbol                → Protocol 정의, conformer
```

**추가 필드**: `arch_layer_map` (아키텍처 컴포넌트 매핑, CLAUDE.md ## Architecture 기반), `import_graph` (의존성 방향), `stream_paradigms` (리액티브 프레임워크 사용 패턴), `protocol_conformers`, `deprecated_symbols`

**deprecated 심볼 탐지** (관점 7 pre-cache):
```
mcp__serena__search_for_pattern  → @available(*, deprecated) 코드 검색
→ deprecated_symbols: [{symbol, file, reference_count}]
```

**기존 유틸리티 탐색**: diff에서 새로 생성하는 객체(DateFormatter, JSONEncoder 등) 감지 → 동일 패키지/프로젝트의 기존 extension/유틸 Grep 검색. `existing_utilities: [{pattern, existing_file, existing_method}]`로 symbols.json에 포함. 에이전트가 "새 구현 제안" 대신 "기존 유틸 활용 제안"을 할 수 있게 한다.

### 1.5. 요구사항 수집 → `${WORK_DIR}/requirements.md`

PR title/body에서 JIRA 티켓 ID 추출 + acceptance criteria 수집. JIRA 연동 시 Atlassian MCP 활용.

### 2.5. View 변경 감지

View 파일 변경 감지 시 리포트에 "UI 변경 감지 — 시뮬레이터 확인 권고" 삽입 + review-quality에 집중 지시.

### 3. 원본 동작 수집 → `${WORK_DIR}/base-behavior.md`

`git show ${BASE_BRANCH}:${FILE_PATH}`로 변경 함수의 원본 코드를 추출. 에이전트가 origin(regression/pre-existing/improvement)을 판정하는 근거로 사용.

### 4. diff 크기별 모드 결정

```
DIFF_LINES=$(wc -l < ${WORK_DIR}/diff.patch)
<500줄 → FULL_INLINE | 500-2000줄 → SUMMARY | >2000줄 → FILE_LIST_ONLY
```

---

## Step: Analyze (독립 리뷰, 병렬)

Tier에 따라 팀 구성이 달라진다 (Tier 상세는 "3-Tier Graceful Degradation" 섹션 참조).

### ⛔ Orchestrator Bias 방지 규칙

에이전트에게 작업을 위임할 때 Orchestrator 자신의 사전 판단이나 가설을 절대 포함하지 않는다.

```
금지: "ORCH-001: X가 누락된 것 같습니다. 이 관점으로 확인해주세요."
금지: "핵심 이슈로 Y를 발견했습니다. 분석 시 참고하세요."
허용: diff + symbols + base-behavior 파일만 전달. 에이전트가 독립 발견.
```

에이전트들이 동일한 가설을 공유하면 3/3 동의가 오히려 false confidence를 증폭시킨다 (homogeneous multi-agent failure). Orchestrator는 컨텍스트 데이터만 전달하고 판단은 에이전트에게 위임한다.

### Tier 1: Full Team (TeamCreate)

```
TeamCreate("peer-review-{PR_NUMBER}")

├─ Teammate 배치: review-arch (opus ★, Task(team_name="peer-review-{PR}", subagent_type: general-purpose))
│   Read: skills/arch-critic/SKILL.md (글로벌) + ${WORK_DIR}/diff.patch + symbols.json + requirements.md + base-behavior.md
│   분석: 관점 1(Architecture Decision) + 관점 2(Extensibility)
│   MCP: 필요 시 Serena 직접 호출 (pre-cache 보완)
│   출력: ${WORK_DIR}/arch-critic-result.json
│
├─ Teammate 배치: review-quality (sonnet, Task(team_name="peer-review-{PR}", subagent_type: general-purpose))
│   Read: skills/code-auditor/SKILL.md (글로벌) + ${WORK_DIR}/diff.patch + symbols.json + requirements.md + base-behavior.md
│   분석: 관점 4(Decomposition) + 관점 5(Modern API) + 관점 6(Dependency) + 관점 7(Refactoring Completeness)
│   MCP: 필요 시 Serena/Context7 직접 호출
│   출력: ${WORK_DIR}/code-auditor-result.json
│
├─ Teammate 배치: review-counter (sonnet, Task(team_name="peer-review-{PR}", subagent_type: general-purpose)) [Challenge 단계 후 실행]
│   Read: ${WORK_DIR}/arch-critic-result.json + code-auditor-result.json + codex-challenger-result.json
│   역할: 관점 8(Requirements Alignment 보조) — 3개 에이전트 "OK" 판정 영역 집중 반론
│   출력: ${WORK_DIR}/counter-result.json → Challenge 단계 Confidence Matrix 보정 입력
│
└─ Bash (병렬): codex exec — 팀 외부, 독립 실행
```

### Codex 호출 (Analyze)

> `get_codex_skill()` 3-Tier 디스커버리: modules/cross-validation.md 참조.
> Codex 모델: `~/.codex/config.toml`에서 설정된 모델 사용.

```bash
SCHEMA_PATH="${HOME}/.claude/schemas/codex_peer_review_schema.json"
CHALLENGER=$(get_codex_skill "challenger")  # cross-validation.md 3-Tier 디스커버리

codex exec \
  --sandbox read-only \
  --output-schema "$SCHEMA_PATH" \
  -o "${WORK_DIR}/codex-challenger-result.json" \
  -C "$GIT_ROOT" \
  "${CHALLENGER_PROMPT}
   ## Origin Classification (필수)
   - regression: PR이 새로 만든 문제 (severity 유지)
   - pre-existing: 원본에도 동일한 패턴 (severity cap: suggestion)
   - improvement: 개선 여지 (severity cap: minor)
   ## Diff
   $(cat ${WORK_DIR}/diff.patch | head -c 50000)"
```

### 에이전트 출력 스키마

```json
{
  "agent": "review-arch | review-quality",
  "agent_status": "ok | partial | failed",
  "status_reason": "정상 | pre-cache 부분 실패 등",
  "issues": [{
    "id": "ARCH-001",
    "perspective": "architecture | extensibility | ...",
    "file": "SomeRouter.swift", "line_range": "45-60",
    "severity": "critical | major | minor | suggestion",
    "confidence": 85,
    "origin": "regression | pre-existing | improvement",
    "description": "문제 설명 (400자). WHY 포함: 기존 동작과의 차이 + 발생 조건 + 결과",
    "impact": "실제 사용자/시스템 영향 (major 이상 필수, minor null)",
    "suggestion": "수정 제안 (300자 이내)",
    "evidence_trace": "// Step 1: file:line ...\n// Step 2: ... (major+ 필수, minor null)"
  }],
  "strengths": ["최대 3개"],
  "overall_assessment": "excellent | good | needs_improvement | major_concerns"
}
```

**Per-Agent 제약**: max 10 issues, description ≤400chars (WHY 필수), impact 필드 major+ 필수, suggestion ≤300chars, strengths ≤3, ~3K tokens.

> **파싱 참고**: review-arch/review-quality 결과에는 `challenges` 키가 없음(Codex DA 전용). Orchestrator는 `challenges` 기본값 `[]`로 처리.

---

## Step: Challenge (상호 비판)

### 방법 A — 기본 (Orchestrator 합성)

```
├─ 3개 결과 JSON 로드 (review-arch + review-quality + codex-challenger)
├─ 이슈 중복 제거 (파일 + line_range overlap + perspective fuzzy match)
├─ 이슈 간 충돌 식별 ("확장성 부족" vs "오버엔지니어링")
└─ 초기 Confidence Matrix 생성
```

### 방법 B — `--deep` Cross-Critique

> ⚠️ 추가 ~$0.5-1.5, 시간 2-5분. `--deep` 사용 시 사전 비용/시간 경고 표시.

```
├─ 각 팀 에이전트가 다른 에이전트 결과를 Read
├─ SendMessage로 동의/반박/보완 교환
│   └─ diff/결과는 <review-data> 블록으로 감싸기
├─ 합의 수렴 후 Orchestrator 종합
└─ 최종 Confidence Matrix 업데이트
```

### Codex Devil's Advocate (공통, 1회 추가 호출)

**DA 사전 검증 (브랜치 일치 확인)**: DA는 `--sandbox read-only`로 현재 워크트리만 접근 가능. 현재 브랜치가 PR head와 다르면 DA의 reverse 판정이 무효가 될 수 있다.
1. `git branch --show-current` vs PR headRefName 비교
2. 불일치 시: DA 프롬프트에 `"현재 워크트리({branch})가 PR 브랜치({pr_branch})와 다름. git show pr-{PR}:file 참조 불가. reverse 판정 시 근거를 현 스냅샷이 아닌 diff 기준으로 작성할 것"` 경고 삽입
3. DA 결과의 reverse 판정은 Orchestrator가 `git show pr-{PR}:{file}`로 반드시 교차 확인

```bash
codex exec \
  --sandbox read-only \
  --output-schema "$SCHEMA_PATH" \
  -o "${WORK_DIR}/codex-da-result.json" \
  -C "$GIT_ROOT" \
  "이슈 목록을 비판적으로 검토. Devil's Advocate 역할.
   각 이슈: agree/challenge/supplement/reverse 판정.
   Origin 검증: 원본에도 동일한 패턴이면 challenge + pre-existing 명시.
   ${BRANCH_WARNING}
   ## 합성된 이슈 목록
   $(cat ${WORK_DIR}/synthesized-issues.json)"
```

**DA 판정 반영**: `agree`→flagged_by 추가, `challenge`→confidence -20%, `supplement`→보완 추가, `reverse`→EXCLUDE + 새 이슈(confidence 70). **reverse 시**: Orchestrator가 PR 브랜치 코드로 교차 확인 후 유효성 최종 판정.

---

## Step: Synthesize (종합)

sequential-thinking으로 Confidence Matrix를 계산한다.

### 1. agent_status 보정

| Status | 처리 |
|--------|------|
| ok | 정상 가중치 |
| partial | confidence × 0.7 |
| failed | 투표 제외 (2-agent 모드) |
| 전체 failed | Tier 하위 전환 (폴백 체인) |

### 2. Origin 기반 Severity 보정

에이전트가 보고한 `origin` 필드를 기반으로 severity를 보정한다.

```
origin 보정 규칙:
├─ regression: severity 유지 (PR이 만든 문제)
├─ pre-existing: severity cap → suggestion (기존과 동일한 동작)
│   └─ 리포트 표기: "[기존 동작 동일]" 태그 추가
├─ improvement: severity cap → minor (개선 여지, 강제 아님)
│   └─ 리포트 표기: "[개선 제안]" 태그 추가
└─ origin 미지정: base-behavior.md 교차 확인 후 Orchestrator가 직접 판정
```

핵심 원칙: **PR 리뷰는 PR이 만든 변화를 평가한다.**
기존 코드에 이미 있던 패턴을 PR의 결함으로 지적하지 않는다.
개선 가능 여지는 suggestion으로 언급하되, 수정을 강제하지 않는다.

### 2.5. PR Intent Alignment Check

PR title/body/requirements.md의 핵심 의도를 각 regression 이슈와 교차 확인한다. PR이 "기능 제거/전환"을 명시한 경우, 해당 기능의 부수효과(이벤트, 상태 초기화 등) 제거는 의도적일 수 있다.
- 의도적 제거 가능성이 있으면: severity 유지하되 `"[의도 확인 필요]"` 태그 추가
- 원칙: "삭제된 기능의 부수효과까지 PR의 결함으로 단정하지 않는다. 의도 확인이 우선."

### 3. Dedup + 투표

```
Dedup: 동일 파일 + 겹치는 line_range + 동일 perspective → 병합

투표 로직:
├─ 3/3 동의: final = avg → INCLUDE
│   └─ ⚠️ 동의 수는 신뢰를 증폭시키지 않는다. 에이전트들이 동일 지식 갭을 공유하면
│      3/3 동의가 오히려 false confidence를 만든다. avg 그대로 사용.
├─ 2/3 동의: final = avg × 0.9 → INCLUDE (소수 의견 주석)
├─ 1/3 동의: final = avg × 0.6 → ≥70 INCLUDE, <70 EXCLUDE
└─ 0/3: EXCLUDE
```

### 4. Confidence Matrix 출력

```markdown
| # | Issue | Origin | Sev | Arch | Auditor | Codex | DA | Votes | Final | Decision |
|---|-------|--------|-----|------|---------|-------|----|-------|-------|----------|
```

> Origin 열 추가: `R`(regression), `P`(pre-existing), `I`(improvement). pre-existing은 severity가 suggestion으로 cap됨.

### 4.5. Line Verification Gate (Major 이슈만)

Major 이상 이슈의 line_range를 실제 PR 브랜치 코드로 검증:
1. `git show pr-{PR_NUMBER}:{FILE}` 로 실제 코드 확인
2. 에이전트가 보고한 line_range와 실제 위치 대조
3. 불일치 시 실제 라인 번호로 업데이트 → `verified_line_range` 필드 추가
4. 검증된 evidence_trace의 코드 블록에 `file:line` 주석 보강

### 4.6. ⛔ Claim Verification Gate (Compiler-Verifiable 이슈)

> **⛔ 4.6 gate 실행 전에 현재 Synthesize 중간 상태를 먼저 파일로 저장하라.**
> gate는 컴파일러 실행 + 결과 해석으로 시간이 걸린다. 저장 전 compact가 발생하면 이전 분석이 사라진다.
> 저장 순서: `synthesized-issues-partial.json` → gate 실행 → 결과 반영 → `confidence-matrix.md` 최종 저장.

> **핵심 원칙**: "컴파일러 경고/에러가 발생한다/발생하지 않는다"는 클레임은 에이전트가 추론할 수 없는 empirical fact다. 컴파일러가 final judge다.
>
> PR #3434 MINOR-001 교훈: 3/3 에이전트가 "UITabBarItem Sendable 경고 발생" 주장 → 실제 빌드 결과: 현재 코드 경고 없음, 제안 코드(@MainActor 추가) 오히려 경고 발생. Swift 5.10 `sending` semantics를 아무도 컴파일러로 확인하지 않았음.

**Compiler-Verifiable 이슈 감지 조건** (하나라도 해당하면):
- perspective: `concurrency` 또는 `sendable`
- 이슈 설명에 `경고`, `warning`, `Sendable`, `sending`, `actor isolation`, `@MainActor` 포함
- 클레임이 "이 코드가 컴파일러 경고를 발생시킨다/않는다"

**처리 절차**:
```
1. INCLUDE 판정된 이슈 중 Compiler-Verifiable 이슈 식별
2. `swiftc -strict-concurrency=complete -swift-version 5 minimal_repro.swift` 실행
   - minimal_repro: git show pr-{PR}:{FILE}에서 해당 함수/클로저 추출
   - swiftc 경로: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/swiftc
3. 결과 해석:
   ├─ 에이전트가 "경고 발생한다" 주장 + 실제 경고 없음 → EXCLUDE (이슈 DROP)
   ├─ 에이전트가 "경고 발생한다" 주장 + 실제 경고 있음 → INCLUDE 유지
   └─ Swift 6 모드도 추가 확인: -strict-concurrency=complete -swift-version 6
4. 검증 결과를 confidence-matrix.md에 기록: compiler_verified: true/false + result
```

**컴파일러 검증 불가 시** (XcodeBuildMCP 없음, SDK 경로 미확인 등):
- 해당 이슈의 confidence ceiling을 65로 제한 (검증 없이 INCLUDE 불가)
- 이슈에 `[컴파일러 검증 필요]` 태그 추가하여 Deliver에서 명시

### 4.7. ⛔ Behavior-Verifiable Claim Gate (Runtime State 이슈)

> **핵심 원칙**: "이 상태가 런타임에 실제로 발생할 수 있다"는 클레임은 에이전트가 패턴으로 추론할 수 없는 empirical fact다. 상태 할당 경로를 추적해야 한다.
>
> PR #3449 MAJOR-1 교훈: 3/3 에이전트가 `isTimeMachineAvailable` guard 누락을 major로 판정 (confidence 90). 실제 확인 결과: `isAtLiveEdge = false`는 `setTimeShift()` 안에서만 할당되고, 모든 `setTimeShift()` 호출부는 `isTimeMachineAvailable` 가드를 이미 갖고 있음 → 불변식: `isAtLiveEdge = false ⟹ isTimeMachineAvailable = true`. Guard가 redundant하므로 진짜 regression이 아님. 3/3 high-confidence 동의가 오히려 false positive를 증폭.

**Behavior-Verifiable 이슈 감지 조건** (하나라도 해당하면):
- 이슈 유형: "missing guard condition" (`guard`, `if X &&` 패턴 누락)
- 이슈 유형: "기존 패턴 X가 있는데 새 코드에 없음" (Pattern-Consistency)
- 이슈 설명에 `guard 누락`, `조건 없음`, `체크하지 않음`, `발생할 수 있다`, `될 수 있다` 포함
- perspective: `architecture`, `state-management`, `guard`

**처리 절차**:
```
1. INCLUDE 판정된 이슈 중 Behavior-Verifiable 이슈 식별
2. 핵심 상태 변수(guarded variable) 식별 (예: `isAtLiveEdge`)
3. 해당 변수의 ALL assignment 위치를 추적:
   git show pr-{PR}:{FILE} 또는 Grep으로 "{variable} = " 검색
4. 각 setter 호출부에서 논쟁 중인 guard가 이미 상위에서 적용되는지 확인
5. 결과 해석:
   ├─ 모든 setter가 이미 guard X에 의해 보호됨 → 불변식 성립
   │   → confidence ceiling 65 + "[불변식 확인 필요]" 태그 + severity 하향 검토
   ├─ setter 중 guard 없는 경로 존재 → 불변식 불성립
   │   → INCLUDE 유지, evidence_trace에 "unguarded setter path" 명시
   └─ 추적 불가 (외부 모듈, indirect 할당) → confidence ceiling 70 + "[런타임 검증 필요]" 태그
6. 결과를 confidence-matrix.md에 기록: behavior_verified: true/false + trace
```

**Pattern-Consistency 이슈 처리**:
- 순수하게 "기존 패턴 X가 있는데 새 코드에 없음" 근거만인 이슈 → `[패턴 일관성]` 태그 추가
- 패턴 불일치가 functional difference를 만드는지 반드시 확인 (위 절차 적용)
- 만들지 않는다면: confidence ceiling 75 → DA "challenge" 유도

### 5. ⛔ CHECKPOINT — 산출물 저장 (Compact Recovery)

> **⛔ Synthesize 완료 직후, Deliver 단계로 넘어가기 전에 반드시 Write 도구로 저장하세요. 저장 전 대화 출력 금지.**

Synthesize 결과를 파일로 영속화한다. 대화 컨텍스트가 compact되어도 Read로 복원 가능.

```
${WORK_DIR}/synthesized-issues.json  — 병합된 이슈 (Dedup+투표+검증 라인)
${WORK_DIR}/confidence-matrix.md     — 최종 Confidence Matrix (마크다운)
${WORK_DIR}/review-index.md          — Compact Recovery 엔트리 포인트
```

review-index.md 형식:
```markdown
# Peer Review #{PR_NUMBER} — Context Index
## Phase: {Synthesize|Deliver}
## Artifacts
- diff.patch, symbols.json, requirements.md, base-behavior.md
- arch-critic-result.json, code-auditor-result.json, codex-*-result.json
- synthesized-issues.json — {N}개 이슈 (Major {M}, Minor {m})
- confidence-matrix.md
```

> Compact 감지 시: `${WORK_DIR}/review-index.md` 읽기 → Phase 확인 → 해당 산출물 로드 → 중단 지점 재개.

---

## Step: Deliver (전달)

### Comment Style Guide (PR 코멘트 톤)

팀원의 코드를 존중하는 건설적 톤으로 작성한다. 모든 이슈 설명과 PR 코멘트에 적용.

- "~하면 좋겠습니다" (제안형) > "~해야 합니다" (명령형)
- 문제만 지적하지 말고 "왜 중요한지" 설명 포함
- 기존 코드의 좋은 점 먼저 언급 후 개선점 제시
- 불확실한 이슈는 "확인 부탁드립니다" 형태로 질문

톤 템플릿:
- **Major**: "좋은 접근인데, {기존동작}이 새 경로에서 빠진 것 같아요. {영향} 때문에 {제안}하면 어떨까요?"
- **Minor**: "{장점} 잘 되어 있는데, {개선점}도 함께 고려해 주시면 좋겠습니다."
- **Suggestion**: "사소한 건데, {기존유틸}이 있어서 활용하면 더 깔끔할 것 같아요."
- **[의도 확인 필요]**: "혹시 {동작}은 의도적으로 제거하신 건가요? {이유}라면 괜찮은데, 아니라면 {제안} 부탁드려요."

### 출력 전략: 대화 vs 문서 분리

#### 대화 출력 (항상)

```
1. Confidence Matrix (테이블)
2. 머지 전 필수 확인 (Major) — 이슈당:
   - `file:verified_line_range` 위치
   - What: 문제 설명 (WHY 포함, 400자)
   - Impact: 실제 영향
   - Evidence: 기존 vs 신규 코드 블록 (file:line 주석)
   - Suggestion + PR Comment (부드러운 톤)
3. 머지 전 권장 수정 (Minor, 2-3줄씩 — WHY 포함)
4. 긍정적 측면 (3-5줄)
5. 최종 판정 + Severity 보정 근거
```

#### ⛔ CHECKPOINT — 문서 출력 (Deliver 완료 전 반드시 저장)

> **⛔ 대화 출력 전에 반드시 Write 도구로 아래 파일들을 저장하세요. 저장 완료 후 사용자에게 경로를 안내합니다.**
> ```
> 📁 산출물 저장: ${WORK_DIR}/
>    ├── review-report.md
>    └── pr-comments.md
> ```

- `${WORK_DIR}/review-report.md` — 통합 보고서. 이슈별 형식:

```markdown
### MAJOR-N: {제목}
**File**: `{file}:{verified_line_range}`
**Origin**: {origin} | **Confidence**: {N} | **Found by**: {agents}

**What**: {description — WHY 포함}
**Impact**: {impact}

**Evidence**:
  // [기존] {base_file}:{line} — {코드}
  // [신규] {pr_file}:{line} — {코드} ← {문제 표시}

**Suggestion**: {제안}

> **PR Comment**: {부드러운 톤 코멘트, 복사 가능}
```

- `${WORK_DIR}/pr-comments.md` — 이슈별 부드러운 톤 PR 코멘트 모음 (복사/붙여넣기용)
- `${WORK_DIR}/*-result.json` — 에이전트/Codex 원본 결과

#### --post 시

`gh pr comment {PR_NUMBER} --body "$(cat ${WORK_DIR}/review-report.md)"`

---

## 3-Tier Graceful Degradation

### Tier 구성

| Tier | review-arch | review-quality | Codex | Cross-Critique | 비용 상한 |
|------|------------|----------------|-------|---------------|----------|
| **0 (Solo)** | Orchestrator 직접 | — | — | None | ~$0.10 |
| **1 (Solo+Codex)** | Orchestrator 직접 | — | codex exec ×1 | None | ~$0.30 |
| **2 (Lite Team)** | Opus 팀에이전트 ★ | Sonnet 팀에이전트 | codex exec ×1 | Lite (합성만) | ~$2.00 |
| **3 (Full Team)** | Opus 팀에이전트 ★ | Sonnet 팀에이전트 | codex exec ×2 | Full (SendMessage + DA) | ~$3.50 |

### 자동 Tier 선택

```
diff < 100줄  → Tier 0 (기본), Tier 1 (--codex)
diff 100-200줄 → Tier 1 (기본), Tier 2 (--deep)
diff 200-500줄 → Tier 2 (기본), Tier 3 (--deep)
diff > 500줄  → Tier 2 + 비용 경고, Tier 3 (--deep)
diff > 2000줄 → AskUserQuestion 필수 ($3+ 예상)

--tier N 옵션으로 강제 지정 가능
```

### 타임아웃 + 폴백

에이전트별 타임아웃: review-arch/quality 5분, Codex 3분, 전체 15분. 타임아웃 시 `agent_status: "timeout"` + confidence ×0.5. 폴백: Tier 3→2→1→0 자동 전환.

---

## Boundaries

**Will**:
- 팀원 PR/브랜치의 9개 관점 피어 리뷰
- 3-Model Cross-Review + Confidence Matrix 투표
- Codex Devil's Advocate로 편향 보정
- gh pr comment로 리뷰 게시 (`--post`)
- 3-Tier Graceful Degradation + 자동 폴백

**Will Not**:
- 코드를 직접 수정하지 않음 (리뷰만 수행)
- 자기 코드 리뷰 (→ `/fz-review`)
- Codex 위임 (→ `/fz-codex`) — codex exec 직접 호출
- Safety/메모리/동시성 심층 분석 (→ CLAUDE.md `## Guidelines` 위임)

## 에러 대응

`gh auth` 실패→git 폴백, 에이전트 spawn 실패→Tier 하위 전환, Codex 실패→2-agent 투표, Codex timeout→재시도 1회 후 skip, Serena 실패→에이전트 직접 MCP, diff >2000줄→AskUserQuestion.

## 연계 모드

- **--discover**: Major 이슈에 /fz-discover REP 프로토콜 자동 적용
- **--explain**: `/fz-pr-digest` 자동 실행 (Gather 데이터 재활용)

## Completion → Next

`--post`로 PR 게시, 수정 후 재리뷰, `--explain`으로 변경사항 해설 연계.
