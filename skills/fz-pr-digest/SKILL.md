---
name: fz-pr-digest
description: >-
  PR 변경사항 해설 + 학습. Before/After 비교, 아키텍처 맥락 설명.
  예: 설명해줘, 해설, 뭐가 바뀐, PR 이해
user-invocable: true
disable-model-invocation: true
argument-hint: "[PR번호 또는 브랜치명] [--light | --deep]"
allowed-tools: >-
  mcp__serena__find_symbol,
  mcp__serena__get_symbols_overview,
  mcp__serena__find_referencing_symbols,
  mcp__serena__search_for_pattern,
  mcp__serena__find_file,
  mcp__serena__activate_project,
  mcp__github__get_pull_request,
  mcp__github__get_pull_request_files,
  mcp__github__get_pull_request_comments,
  mcp__context7__resolve-library-id,
  mcp__context7__query-docs,
  Bash(git *), Read, Grep, Glob
composable: true
provides: [pr-digest, code-understanding]
needs: [none]
intent-triggers:
  - "설명|해설|이해|학습|알려줘|뭐가.*바뀐|어떻게.*개선"
  - "explain|digest|understand|learn|what.*changed|walkthrough"
model-strategy:
  main: opus
  verifier: null
---

# /fz-pr-digest - PR 변경사항 해설 (코드 학습용)

> **행동 원칙**: 팀원의 PR을 "비평"이 아닌 "해설"한다. 기존 코드가 무엇이었고, 왜 바뀌었고, 어떻게 바뀌었는지를 프로젝트 구조 맥락 위에서 설명하여 사용자의 코드베이스 이해를 돕는다.

## 개요

> Gather → Analyze → Narrate

```bash
/fz-pr-digest 3394              # PR #3394 표준 해설
/fz-pr-digest 3394 --light      # 요약만 (diff 기반, 빠름)
/fz-pr-digest 3394 --deep       # 기술 해설 + 학습 포인트까지
/fz-pr-digest feature/ASD-465   # 브랜치 기반
```

## peer-review와의 차이

| | fz-peer-review | fz-pr-digest |
|---|---|---|
| 목적 | 이슈 도출 (비평) | 변경 이해 (해설) |
| 질문 | "뭐가 문제야?" | "뭘 바꿨고 왜?" |
| 출력 | 이슈 목록 + Confidence Matrix | Before/After 비교 + 맥락 설명 |
| 톤 | 객관적 평가 | 교육적 해설 |
| 코드 탐색 | diff + 참조 관계 | diff + 원본 코드 + 아키텍처 위치 |

---

## Prerequisites

- TEAM 모드 사용 시 환경 변수 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정 필수 (미설정 시 TeamCreate 실패)
- 참조: `guides/agent-team-guide.md` §8 (공식 사양)

## 3-Tier 깊이

| Tier | 플래그 | 내용 | 토큰 비용 |
|------|--------|------|----------|
| Light | `--light` | 한 줄 요약 + 파일별 변경 요약 | ~2K |
| Standard | (기본) | Light + Before/After 비교 + 아키텍처 맥락 | ~5-8K |
| Deep | `--deep` | Standard + 기술 해설 + 학습 포인트 + 관련 패턴 | ~10-15K |

### 자동 Tier 선택 (플래그 미지정 시)

```
diff < 50줄   → Light (기본), Standard (--deep 없이도 가능)
diff 50-500줄 → Standard (기본)
diff > 500줄  → Standard (기본), Deep은 명시적 --deep 필요
```

---

## Step 1: Gather (컨텍스트 수집)

peer-review의 Gather와 동일한 방식으로 diff를 수집하되, 원본 코드에 더 집중한다.

`WORK_DIR=${PROJECT_ROOT}/pr-digest-{PR_NUMBER}`

### 1.1 diff 수집

```
PR 번호:
  gh pr view {PR_NUMBER} --json baseRefName,headRefName,title,body,files,additions,deletions
  gh pr diff {PR_NUMBER} > ${WORK_DIR}/diff.patch

branch:
  git diff {base}...{target} > ${WORK_DIR}/diff.patch
```

### 1.2 원본 코드 수집 (Standard 이상)

```
변경 파일별:
  git show ${BASE_BRANCH}:${FILE_PATH} > ${WORK_DIR}/before/${FILENAME}

수집 범위:
  - 변경된 함수/메서드의 원본 전문
  - 삭제된 타입/클래스의 원본 구조
  - 변경된 import/의존성
```

### 1.3 아키텍처 맥락 수집 (Standard 이상)

```
Serena 호출:
  get_symbols_overview  → 변경 파일의 심볼 구조
  find_symbol           → 변경된 타입의 상위/하위 관계
  find_referencing_symbols → 이 코드를 사용하는 곳

수집 결과:
  - 변경 파일이 속한 모듈/패키지
  - CLAUDE.md `## Architecture`에 정의된 아키텍처 계층에서의 위치 (해당 시)
  - 의존성 그래프에서의 위치
```

### 1.4 기술 배경 수집 (Deep만)

```
Context7 호출 (사용된 프레임워크/패턴에 대해):
  resolve-library-id → query-docs

예: Introspect 사용 시 → SwiftUIIntrospect 문서 조회
    @Observable 전환 시 → Observation 프레임워크 문서 조회
```

---

## Step 2: Analyze (분석)

수집된 데이터를 기반으로 변경의 의도와 구조를 파악한다.

### 2.1 변경 의도 추론

```
입력: PR title + body + diff 패턴
추론:
  - 리팩토링: 기능 동일, 구조 변경 (타입 교체, 패턴 전환 등)
  - 기능 추가: 새 기능/화면/로직
  - 버그 수정: 조건문 변경, 에러 처리 추가
  - 성능 개선: 알고리즘 변경, 캐싱 추가
  - 코드 정리: 미사용 코드 제거, 네이밍 변경
```

### 2.2 Before/After 구조 비교 (Standard 이상)

각 변경 단위(파일 또는 논리적 변경 그룹)에 대해:

```
Before:
  - 어떤 타입/패턴을 사용했는지
  - 데이터 흐름이 어떻게 이루어졌는지
  - 생명주기가 어떻게 관리됐는지

After:
  - 무엇으로 교체/변경됐는지
  - 데이터 흐름이 어떻게 바뀌었는지
  - 생명주기 관리가 어떻게 달라졌는지

Why:
  - 교체/변경의 동기 추론
  - 기존 방식의 한계점 (있다면)
  - 새 방식의 이점
```

### 2.3 아키텍처 위치 매핑 (Standard 이상)

프로젝트 규칙은 CLAUDE.md `## Architecture` 섹션을 따른다.

```
변경된 코드의 위치:
  ├─ 모듈: CLAUDE.md에 정의된 모듈 구조 참조
  ├─ 레이어: CLAUDE.md `## Architecture`에 정의된 레이어 기준
  ├─ 아키텍처 컴포넌트: 해당 컴포넌트 이름 + 역할
  └─ 패턴: MVVM / Coordinator / Delegate / Reactive 파이프라인 등

관계도: 이 코드를 사용하는 상위 컴포넌트 → 이 코드 → 이 코드가 의존하는 하위 컴포넌트
```

### 2.4 기술 해설 준비 (Deep만)

```
변경에 사용된 핵심 기술/패턴:
  - 동작 원리 설명
  - 이 프로젝트에서 해당 기술의 사용 현황
  - 관련 주의사항 (예: lifecycle timing, 메모리 관리)
```

---

## Step 3: Narrate (해설 출력)

분석 결과를 교육적 문체로 구성한다.

### 출력 전략: 대화 vs 문서 분리

대화에서는 핵심 요약만 전달하고, 상세 해설은 파일로 저장한다.

#### 대화 출력 (항상)

사용자가 바로 읽고 이해할 수 있는 핵심 정보만:

```
1. 한 줄 요약
2. 변경 의도 (2-3줄)
3. 핵심 Before/After (가장 중요한 변경 1-2개만, 각 3줄 이내)
4. 학습 포인트 (Deep일 때, 제목 + 한 줄 설명만)
5. 주의할 점 (peer-review 이슈 참조 시, 한 줄씩)
```

> 대화에서 전체 Before/After, 아키텍처 트리, 기술 해설 본문, 파일 상세 테이블은 출력하지 않는다.
> "상세는 ${WORK_DIR}/pr-digest-{tier}.md 참조" 안내만 한다.

#### 문서 출력 (항상, WORK_DIR)

```
${WORK_DIR}/pr-digest-{light|standard|deep}.md  <- 전체 해설 문서
  Light:
  - 한 줄 요약 + 파일별 변경 테이블

  Standard:
  - 한 줄 요약 + 변경 의도
  - Before/After 전체 (모든 변경 그룹, 코드 블록 포함)
  - 아키텍처 맥락 (트리 구조, 관계도)
  - 변경 파일 상세 테이블

  Deep:
  - Standard 전체
  - 기술 해설 (동작 원리, 프로젝트 내 사용 현황)
  - 학습 포인트 (상세 설명)
  - 주의할 점 (peer-review 연계)
  - 관련 코드 목록
```

peer-review 연계 시:
```
${WORK_DIR} = peer-review-{PR_NUMBER}/  <- peer-review WORK_DIR 재사용
  → pr-digest-deep.md 추가 저장
```

---

### Light 출력

```markdown
# PR #{NUMBER}: {TITLE}

## 한 줄 요약
{변경의 핵심을 한 문장으로}

## 변경 파일

| 파일 | 변경 | 요약 |
|------|------|------|
| {파일명} | +{추가}/-{삭제} | {이 파일에서 뭐가 바뀌었는지 한 줄} |
```

### Standard 출력

```markdown
# PR #{NUMBER}: {TITLE}

## 한 줄 요약
{변경의 핵심을 한 문장으로}

## 변경 의도
{왜 이 변경이 필요했는지 2-3줄}

## Before / After

### {변경 그룹 1: 예) ScrollView 접근 방식 변경}

Before:
  {기존 코드가 어떤 구조였고 어떻게 동작했는지}

After:
  {새 코드가 어떤 구조이고 어떻게 동작하는지}

Why:
  {왜 이렇게 바꿨는지, 기존 방식의 한계}

### {변경 그룹 2: ...}
...

## 아키텍처 맥락

{이 코드가 프로젝트 전체에서 어디에 위치하는지}
{관련 모듈/컴포넌트/레이어와의 관계}
{이 변경이 다른 부분에 미치는 영향}

## 변경 파일 상세

| 파일 | 역할 | 주요 변경 |
|------|------|----------|
| {파일명} | {이 파일의 역할} | {구체적 변경 내용} |
```

### Deep 출력

```markdown
{Standard 전체 내용}

## 기술 해설

### {기술/패턴 1: 예) SwiftUI Introspect}
{이 기술이 무엇이고, 어떻게 동작하는지}
{이 PR에서 어떻게 사용됐는지}
{이 프로젝트에서의 사용 현황}

### {기술/패턴 2: ...}
...

## 학습 포인트

1. {이 PR에서 배울 수 있는 패턴/기술 1}
   {왜 이것이 중요한지, 어떤 상황에서 적용할 수 있는지}

2. {패턴/기술 2}
   ...

## 주의할 점

{이 변경에서 발생할 수 있는 잠재적 문제나 알아두면 좋은 제약사항}
{peer-review 결과가 있다면 핵심 이슈 요약 참조}

## 관련 코드

{이 변경과 관련된 다른 파일/모듈 중 함께 읽으면 좋은 것}
```

---

## peer-review 연계

fz-peer-review에서 `--explain` 옵션으로 호출 시, 리뷰 완료 후 자동으로 이 스킬이 실행된다.

```bash
/fz-peer-review 3394 --explain        # 리뷰 + 해설 (Standard)
/fz-peer-review 3394 --explain --deep # 리뷰 + 해설 (Deep)
```

이 경우 Gather 단계의 diff/원본 코드를 peer-review의 WORK_DIR에서 재사용한다:
```
peer-review WORK_DIR: ${PROJECT_ROOT}/peer-review-{PR_NUMBER}/
  → diff.patch, base-behavior.md, symbols.json 재활용
```

---

## 해설 원칙

### 톤

- 교육적이되 과하지 않게. "강의"가 아니라 "시니어 동료의 설명".
- 기존 코드를 폄하하지 않는다. "나쁜 코드"가 아니라 "다른 접근 방식".
- 추측은 추측임을 명시한다. "~로 추정됩니다" vs "~입니다".

### 범위

- diff에 포함된 변경만 해설한다. 관련 없는 코드까지 확장하지 않는다.
- 단, 아키텍처 맥락 설명 시 변경 범위 밖의 구조를 참조하는 것은 허용.

### 정확성

- 원본 코드를 반드시 확인한 후 Before를 작성한다. 추측으로 Before를 쓰지 않는다.
- 기술 해설은 Context7로 검증한다. 문서 없이 API 동작을 단정하지 않는다.

### 가이드라인 참조

- PR 분석 시 프로젝트 규칙은 CLAUDE.md `## Code Conventions` 섹션을 참조한다.
- 아키텍처 평가 기준은 CLAUDE.md `## Architecture` 섹션을 따른다.

---

## TEAM 모드 (Deep Tier)

Deep Tier에서 팀 에이전트를 사용할 수 있다.

### 절대 규칙
> 팀 모드 규칙은 modules/team-core.md 참조 (TeamCreate 필수, 에이전트 간 SendMessage 통신)

### 팀 구성 (Deep)

```
TeamCreate("pr-digest-{PR_NUMBER}")

에이전트:
  - search-symbolic (opus): 심볼 탐색 + Before/After 구조 분석 (Serena 활용)
  - search-pattern (sonnet): 아키텍처 패턴 + 기술 배경 조사

통신 패턴:
  search-symbolic → search-pattern: "이 변경의 상위 컴포넌트 관계 확인해줘"
  search-pattern → search-symbolic: "Root → Settings → FloatingWebView 구조야"
  → 합의 후 team-lead에 보고
```

### peer-review 연계 시 TEAM 구성

fz-peer-review Tier 3 + --explain --deep 시, peer-review 팀에 digest 역할을 추가:

```
TeamCreate("peer-review-{PR_NUMBER}")

에이전트:
  - review-arch (opus): 아키텍처 리뷰 (3-Tier 디스커버리)
  - review-quality (sonnet): 코드 품질 리뷰 (3-Tier 디스커버리)
  - 리뷰 완료 후 Lead가 pr-digest Deep 실행
```

---

## Boundaries

**Will**:
- PR/브랜치의 변경사항을 교육적으로 해설
- Before/After 비교로 변경의 맥락 제공
- 아키텍처 위치 매핑으로 프로젝트 구조 학습 지원
- 기술/패턴 해설로 코드 이해도 향상
- peer-review 결과와 연계하여 이슈 맥락 제공

**Will Not**:
- 이슈를 찾거나 severity를 매기지 않음 (→ /fz-peer-review)
- 코드를 수정하지 않음 (→ /fz-fix, /fz-code)
- 커밋/PR 생성하지 않음 (→ /fz-commit, /fz-pr)
- 기존 코드를 비판하지 않음 (해설만)

## 에러 대응

| 에러 | 대응 |
|------|------|
| gh 인증 실패 | git 폴백 (fetch + diff) |
| 원본 파일 미존재 (신규 파일) | Before를 "(신규 파일)" 표기, After만 해설 |
| Serena 심볼 탐색 실패 | diff 기반 해설로 폴백 (Light 수준) |
| diff > 2000줄 | 파일별 요약으로 전환 + 핵심 변경 그룹만 상세 해설 |

## Completion → Next

```bash
/fz-pr-digest {PR_NUMBER} --deep     # 더 깊은 해설
/fz-peer-review {PR_NUMBER}          # 이슈 리뷰로 전환
/fz-search "관련 모듈 구조"            # 관련 코드 더 탐색
```
