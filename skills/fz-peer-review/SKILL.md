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
  mcp__serena__read_memory,
  mcp__serena__write_memory,
  mcp__serena__list_memories,
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

## 참조

| 참조 | 용도 |
|------|------|
| `.claude/modules/team-core.md` + `patterns/` | TEAM 실행 프로토콜 |
| `.claude/modules/cross-validation.md` | get_codex_skill() 3-Tier 디스커버리, GIT_ROOT 추출 |
| `.claude/modules/peer-review-gates.md` | Synthesize 검증 게이트 4.5-4.8 전문 (4.7-A Deleted Logic Migration 포함) |
| `.claude/modules/plugin-refs.md` | SwiftUI Expert + Swift Concurrency 플러그인 (diff에 `@MainActor\|actor\|async` 감지 시) |
| `skills/arch-critic/SKILL.md` | 관점 1(Architecture Decision) + 관점 2(Extensibility) |
| `skills/code-auditor/SKILL.md` | 관점 4(Decomposition) + 관점 5(Modern API) + 관점 6(Dependency) + 관점 7(Refactoring) |
| Codex challenger 스킬 | 관점 3(Over-Engineering) + 관점 7 보조 + Devil's Advocate |
| `~/.claude/schemas/codex_peer_review_schema.json` | Codex 응답 JSON 구조 |

---

## Step: Gather (컨텍스트 수집)

오케스트레이터가 직접 수행. `WORK_DIR=${PROJECT_ROOT}/peer-review-{PR_NUMBER}` (현재 작업 디렉토리 기준, 쓰기 불가 시 `.claude/tmp/` 폴백).

### WORK_DIR 초기화 (Gather 첫 번째 단계)

WORK_DIR이 없으면 이후 모든 산출물 저장이 실패한다. Gather 시작 시 반드시 첫 번째로 실행.

```bash
mkdir -p ${WORK_DIR}
```

확인: `WORK_DIR` 경로를 대화 컨텍스트에 명시적으로 기록한다. 이후 모든 파일 저장은 이 경로를 사용한다.

### 0. 사전 점검

```bash
gh auth status  # 성공→gh 사용, 실패→git 폴백 (git fetch upstream + git diff)
# GIT_ROOT 추출: modules/cross-validation.md의 GIT_ROOT 공유 유틸 참조
```

### 0.5. PR 브랜치 fetch

`git show pr-{PR}:{FILE}` 직접 참조 및 Codex DA sandbox 제약 우회를 위해 필수.
```bash
git fetch upstream pull/{PR_NUMBER}/head:pr-{PR_NUMBER}
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

### Orchestrator Bias 방지 규칙

에이전트에게 작업을 위임할 때 Orchestrator 자신의 사전 판단이나 가설을 절대 포함하지 않는다.

```
금지: "ORCH-001: X가 누락된 것 같습니다. 이 관점으로 확인해주세요."
금지: "핵심 이슈로 Y를 발견했습니다. 분석 시 참고하세요."
허용: diff + symbols + base-behavior 파일만 전달. 에이전트가 독립 발견.
```

에이전트들이 동일한 가설을 공유하면 3/3 동의가 오히려 false confidence를 증폭시킨다 (homogeneous multi-agent failure). Orchestrator는 컨텍스트 데이터만 전달하고 판단은 에이전트에게 위임한다.

### ⛔ Gate 0: 팀 생성 필수 (Tier 2+)

> Tier 2 이상에서는 반드시 아래 순서를 실행한다. **standalone Agent() 호출 금지.**
>
> ```
> ⛔ 검증: TeamCreate 호출 없이 Agent(subagent_type=...) 호출 → 위반
> ⛔ 검증: Agent() 호출 시 team_name 파라미터 누락 → 위반
> ```
>
> standalone Agent는 결과가 return으로만 전달되어 에이전트 간 상호 통신(SendMessage)이 불가능하다.
> TeamCreate → Agent(team_name=...) → SendMessage 경로만 허용.

### Tier 2: Lite Team — 실행 시퀀스

```
1. TeamCreate(team_name="peer-review-{PR}")               # ⛔ 필수
2. TaskCreate × 2 (Architecture + Code quality)
3. Agent(name="review-arch", team_name=..., model="opus")  # ⛔ team_name 필수
   Agent(name="review-quality", team_name=..., model="sonnet")
4. Bash("codex exec ...")                                  # Codex challenger
5. 에이전트 완료 대기 → Lead 합성 → shutdown_request → TeamDelete
```

Task Brief (각 에이전트): skills/{arch-critic|code-auditor}/SKILL.md + ${WORK_DIR}/(diff.patch + symbols.json + requirements.md + base-behavior.md)
- [Goal] 독립 이슈 발굴 | [Constraints] 피어 참조 금지, max 10, origin 필수
- [Deliverable] ${WORK_DIR}/{arch-critic|code-auditor}-result.json

### Tier 3: Full Team (--deep) — 추가 시퀀스

Tier 2 완료 후 2.5-Turn Protocol:
```
Round 1: (Tier 2) 각 에이전트 독립 분석 → *-result.json 저장
Round 2: 교차 피드백 (SendMessage 필수) — review-arch ↔ review-quality
Round 0.5: 최종 보고 → Lead에 [합의/불합의 항목] 전달
→ review-counter 스폰 (DA 패스) → Codex DA → Lead 합성 → TeamDelete
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

`{agent, agent_status, status_reason, issues[], strengths[], overall_assessment}` — 상세 필드는 arch-critic/code-auditor SKILL.md 참조.

**Per-Agent 제약**: max 10 issues, description ≤400chars (WHY 필수), impact major+ 필수, suggestion ≤300chars, strengths ≤3. `challenges` 키는 Codex DA 전용 (기본값 `[]`).

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

**DA 사전 검증**: 현재 브랜치 ≠ PR head이면 DA 프롬프트에 "diff 기준으로 작성" 경고 삽입. reverse 판정은 `git show pr-{PR}:{file}`로 교차 확인.

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

`ok`→정상 | `partial`→confidence×0.7 | `failed`→투표 제외(2-agent 모드) | 전체 failed→Tier 하위 전환

### 2. Origin 기반 Severity 보정

에이전트가 보고한 `origin` 필드를 기반으로 severity를 보정한다.

| origin | 처리 | 리포트 태그 |
|--------|------|------------|
| regression | severity 유지 (PR이 만든 문제) | — |
| pre-existing | severity cap → suggestion | `[기존 동작 동일]` |
| improvement | severity cap → minor | `[개선 제안]` |
| 미지정 | base-behavior.md 교차 확인 후 Orchestrator 직접 판정 | — |

핵심 원칙: **PR 리뷰는 PR이 만든 변화를 평가한다.**
기존 코드에 이미 있던 패턴을 PR의 결함으로 지적하지 않는다.
개선 가능 여지는 suggestion으로 언급하되, 수정을 강제하지 않는다.

```
BAD: Interactor에서 guard 삭제 → "연결 상태 체크 누락 (regression)" 즉단
     (UseCase에 동일 guard 이동을 확인하지 않음)
GOOD: Interactor guard 삭제 발견 → PR diff 전체 Grep("getConnectState")
     → UseCase.connect()에 동일 guard 이동 확인 → origin: relocated → 이슈 DROP
```

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

### 4.5-4.8. Verification Gates

> 참조: `modules/peer-review-gates.md` — Line Verification (4.5) + Compiler-Verifiable (4.6) + Behavior-Verifiable (4.7) + Deleted Logic Migration (4.7-A) + RxSwift Error Path (4.8) 게이트 전문
>
> 게이트 실행 전: `synthesized-issues-partial.json` 중간 저장 필수 (compact 방지)

### 5. ⛔ CHECKPOINT — 산출물 저장 (Compact Recovery)

> **⛔ Synthesize 완료 직후, Deliver 단계로 넘어가기 전에 반드시 Write 도구로 저장하세요. 저장 전 대화 출력 금지.**

Synthesize 결과를 파일로 영속화한다. 대화 컨텍스트가 compact되어도 Read로 복원 가능.

```
${WORK_DIR}/synthesized-issues.json  — 병합된 이슈 (Dedup+투표+검증 라인)
${WORK_DIR}/confidence-matrix.md     — 최종 Confidence Matrix (마크다운)
${WORK_DIR}/review-index.md          — Compact Recovery 엔트리 포인트
```

> review-index.md: Phase + Artifacts 목록 기록. Compact 감지 시 이 파일 읽어 산출물 로드 → 중단 지점 재개.

**비ASD Serena Fallback** (WORK_DIR 없을 때):
```
write_memory("fz:checkpoint:peer-review-synthesize", "PR#{number}: 이슈 {N}개 (Critical:{c}/Major:{m}/Minor:{n}). Confidence: {avg}%. 핵심: {top3_요약}")
```

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

- `${WORK_DIR}/review-report.md` — 통합 보고서. 이슈별 필수 필드: `File:line` | Origin/Confidence/Found-by | What(WHY포함,400자) | Impact(major+) | Evidence(기존↔신규 코드블록) | Suggestion | PR Comment(부드러운 톤)

- `${WORK_DIR}/pr-comments.md` — 이슈별 부드러운 톤 PR 코멘트 모음 (복사/붙여넣기용)
- `${WORK_DIR}/*-result.json` — 에이전트/Codex 원본 결과

#### --post 시

`gh pr comment {PR_NUMBER} --body "$(cat ${WORK_DIR}/review-report.md)"`

**비ASD Serena Fallback** (WORK_DIR 없을 때):
```
write_memory("fz:checkpoint:peer-review-deliver", "PR#{number}: 판정 {verdict}. Critical:{c}/Major:{m}. 핵심이슈: {top3}. --post: {Y/N}")
```

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
- ⛔ **standalone Agent() 호출 금지** — Tier 2+ 에서 team_name 없는 Agent 호출은 팀 프로토콜 위반.
  서브에이전트 결과는 return으로만 전달되어 상호 비판(Cross-Critique/SendMessage)이 불가능하다.
  반드시 TeamCreate → Agent(team_name=...) → SendMessage 경로를 사용한다.

## 에러 대응

`gh auth` 실패→git 폴백, 에이전트 spawn 실패→Tier 하위 전환, Codex 실패→2-agent 투표, Codex timeout→재시도 1회 후 skip, Serena 실패→에이전트 직접 MCP, diff >2000줄→AskUserQuestion.

## 연계 모드

- **--discover**: Major 이슈에 /fz-discover REP 프로토콜 자동 적용
- **--explain**: `/fz-pr-digest` 자동 실행 (Gather 데이터 재활용)

## Completion → Next

`--post`로 PR 게시, 수정 후 재리뷰, `--explain`으로 변경사항 해설 연계.
