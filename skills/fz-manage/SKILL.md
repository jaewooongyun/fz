---
name: fz-manage
description: >-
  This skill should be used when the user wants to inspect or manage the fz- skill ecosystem as a whole.
  Make sure to use this skill whenever the user says: "스킬 목록 보여줘", "건강 체크해줘",
  "벤치마크 돌려줘", "의존성 확인", "스킬 관리", "전체 상태", "manage skills", "list all skills",
  "health check", "run benchmark", "check dependencies", "skill inventory".
  Covers: 스킬 목록, 건강 체크, 벤치마크, 의존성, 관리, 인벤토리, 일괄 품질 평가.
  Do NOT use for individual skill eval (use fz-skill eval) or skill CRUD (use fz-skill).
user-invocable: true
disable-model-invocation: true
argument-hint: "[list|info|deps|check|benchmark|create|edit|delete] [대상]"
allowed-tools: >-
  mcp__serena__list_memories,
  mcp__serena__read_memory,
  mcp__serena__find_file,
  mcp__serena__list_dir,
  Read, Grep, Glob
composable: false
provides: []
needs: [none]
intent-triggers:
  - "관리|스킬|의존성|체크|벤치마크|일괄.*평가"
  - "manage|skill|depend|check|benchmark|batch.*eval"
model-strategy:
  main: opus
  verifier: null
---

# /fz-manage - 스킬 시스템 관리

> **행동 원칙**: fz- 스킬 시스템의 상태를 투명하게 보여주고, 의존성 무결성을 보장한다.

## 개요

> 서브커맨드: list | info | deps | check | benchmark | create | edit | delete

- fz- 스킬 인벤토리, 의존성, 건강 체크
- 전체 스킬 일괄 품질 평가 (benchmark)
- 스킬 CRUD (생성/편집/삭제)
- 거버넌스 (`modules/governance.md`)

## 사용 시점

```bash
/fz-manage                  # 전체 인벤토리
/fz-manage list             # 전체 인벤토리 (동일)
/fz-manage info fz-plan     # fz-plan 상세 정보
/fz-manage deps             # 의존성 그래프
/fz-manage check            # 건강 체크 (fz + Agent 통합)
/fz-manage benchmark        # 전체 스킬 일괄 품질 평가
/fz-manage benchmark --top3 # 하위 3개 스킬 개선 제안
/fz-manage benchmark --with-trigger  # 하위 3개에 실측 트리거율 추가
/fz-manage create fz-test   # 새 스킬 생성
/fz-manage edit fz-plan     # 스킬 편집
/fz-manage delete fz-test   # 스킬 삭제
```

### 다른 스킬로 라우팅

| 이전 서브커맨드 | 이동처 | 설명 |
|---------------|--------|------|
| `workflow` | `/fz` | 파이프라인 조합은 compositor가 담당 |
| `team <pattern>` | `modules/team-core.md` + `modules/patterns/` | 각 스킬에서 직접 참조 |
| `governance` | `modules/governance.md` | 거버넌스 프레임워크 |

---

## list -- 전체 인벤토리

모든 fz- 스킬, sc: 명령어, 공유 모듈, 메모리를 조회합니다.

### 절차

1. `Glob("skills/*/SKILL.md")` → fz- 스킬 목록
2. 각 SKILL.md의 YAML frontmatter 파싱
3. `Glob("~/.claude/commands/sc/*.md")` → sc: 명령어 목록
4. `Glob("modules/*.md")` → 공유 모듈 목록

### 출력 형식

```markdown
## fz- 스킬 인벤토리

| 스킬 | 카테고리 | 상태 | 크기 | sc: 활용 |
|------|---------|------|------|---------|
| fz-plan | workflow | OK | 220줄 | design, analyze |
| ... | ... | ... | ... | ... |

## sc: 명령어
analyze, brainstorm, build, cleanup, ...

## 공유 모듈
build.md, governance.md, session.md, skill-template.md, team-core.md, README.md
```

---

## info <name> -- 스킬 상세

### 절차

1. `Read("skills/fz-{name}/SKILL.md")` → YAML frontmatter + 본문
2. YAML에서 `allowed-tools`, `provides`, `needs`, `intent-triggers`, `model-strategy` 추출
3. `Grep("fz-{name}", "skills/")` → 역참조 (이 스킬을 참조하는 다른 스킬)
4. 파일 크기 (줄 수) 계산

### 출력 형식

```markdown
## fz-plan 상세

| 항목 | 값 |
|------|---|
| 크기 | 220줄 |
| allowed-tools | serena(7), context7(2), sequential-thinking(1), atlassian(2) |
| provides | planning, architecture-analysis |
| needs | none |
| intent-triggers | 계획, 설계, 아키텍처, 요구사항 |
| 모델 전략 | Main: opus / Verifier: sonnet |
| 역참조 | fz-manage, fz-code |
```

---

## deps -- 의존성 그래프

### 절차

1. 모든 SKILL.md의 `allowed-tools`, `provides`, `needs` 파싱
2. provides/needs 체인 그래프 + MCP 의존성 생성

### provides/needs 체인 그래프

```
[entry] ─────┬── fz-plan ──planning──▶ fz-code ──code-changes──▶ fz-review
             │                                  └──code-changes──▶ fz-commit ──commit──▶ fz-pr
             │
             ├── fz-search ──search-results──▶ (컨텍스트 제공)
             ├── fz-fix ──code-changes──▶ fz-commit / fz-review
             ├── fz-peer-review ──peer-review──▶ (완료)
             └── (외부 도구 연동) ──verification──▶ (완료)

needs=none (진입점): fz-plan, fz-search, fz-fix
needs=planning:     fz-code
needs=code-changes: fz-review, fz-commit
needs=commit:       fz-pr
```

### MCP 의존성 매트릭스

```
fz-search      → serena(7), context7(2), lsp(4)
fz-plan        → serena(7), context7(2), sequential-thinking(1), atlassian(2)
fz-code        → serena(10), context7(2), lsp(2)
fz-fix         → serena(7), sequential-thinking(1), context7(2), lsp(3)
fz-review      → serena(5), sequential-thinking(1), lsp(2)
fz-peer-review → serena(6), sequential-thinking(1), github(5), context7(2)
fz-commit      → atlassian(2)
fz-pr          → github(3), atlassian(3)
fz-manage      → serena(4)
```

---

## check -- 통합 건강 체크

fz- 스킬 + 에이전트를 일괄 검증합니다.

### 검증 항목

| # | 대상 | 검증 | 방법 |
|---|------|------|------|
| 1 | fz-* | YAML 필수 필드 | name, description, user-invocable, allowed-tools |
| 2 | fz-* | MCP 유효성 | allowed-tools의 MCP 도구가 실제 존재하는지 |
| 3 | fz-* | provides/needs 체인 | 모든 needs가 provides로 충족 가능한지 |
| 4 | fz-* | intent-triggers 중복 | 과도한 겹침 여부 |
| 5 | fz-* | 스킬 크기 <= 500줄 | Progressive Disclosure 준수 |
| 6 | fz-* | 깨진 파일 참조 | 본문 내 경로 참조 검증 |
| 7 | Agent | 에이전트 파일 유효성 | `agents/*.md`에 name, description, model 존재 |
| 8 | Agent | Team MCP 호환성 | 에이전트가 Team 불가 MCP 참조하지 않는지 |
| 9 | fz-* | 테스트 케이스 존재 | SKILL.md에 "## 테스트 케이스" 섹션 또는 참조 링크 |
| 10 | fz-* | Triggering 테스트 | should trigger + should NOT trigger 최소 3개 |
| 11 | Infra | skill-creator 설치 | Glob으로 `run_loop.py` 탐색 → 있으면 OK, 없으면 WARN |

### 출력 형식

```markdown
## 건강 체크 결과

OK YAML 필수 필드: 14/14 정상
OK MCP 유효성: 6/6 서버
OK provides/needs 체인: 완전
OK intent-triggers: 관리됨
OK 스킬 크기: 14/14 (500줄 미만)
OK 깨진 참조: 0개
OK 에이전트 파일: 6/6 정상
OK Team MCP 호환: 6/6
OK 테스트 케이스: N/N 존재
OK Triggering 테스트: N/N (3개+ 커버)

총 점수: 100%
```

---

## benchmark -- 전체 스킬 일괄 품질 평가

모든 fz-* 스킬에 대해 `/fz-skill eval`의 Static Analysis를 일괄 실행하고 종합 리포트를 생성합니다.

### 절차

1. `Glob("skills/*/SKILL.md")` → 전체 fz-* 스킬 목록
2. 각 스킬에 대해 Static Analysis 8항목 실행:

   | 검증 항목 | 기준 | 판정 |
   |----------|------|------|
   | Description 품질 | what+when+when-not+한영키워드 | PASS/FAIL |
   | YAML 완전성 | name, description, allowed-tools, provides, needs | PASS/FAIL |
   | 크기 제한 | ≤500줄 | PASS/FAIL |
   | Few-shot 예시 | ≥3개 (BAD/GOOD 쌍 포함) | PASS/WARN |
   | Gate 체크리스트 | 각 Phase에 Gate 존재 | PASS/WARN |
   | Boundaries | Will/Will Not + 대안 명시 | PASS/FAIL |
   | 과격 표현 | CRITICAL/MUST ALWAYS 등 부재 | PASS/WARN |
   | 에러 대응 | 테이블 존재 | PASS/WARN |

3. 스킬별 점수 산출 (PASS=10점, WARN=5점, FAIL=0점 → 80점 만점)
4. 하위 3개 스킬 자동 식별 + 개선 제안 생성

### 출력 형식

```markdown
## Benchmark 결과

| 스킬 | Desc | YAML | Size | Few-shot | Gate | Bounds | Tone | Error | 점수 |
|------|------|------|------|----------|------|--------|------|-------|------|
| fz-plan | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | 80 |
| fz-code | PASS | PASS | PASS | WARN | PASS | PASS | PASS | PASS | 75 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

평균: 72/80
하위 3개: fz-X (55), fz-Y (60), fz-Z (65)

### 개선 제안
1. **fz-X** (55점): Few-shot 예시 부족 + Gate 누락 → `/fz-skill eval fz-X` 실행 권장
2. **fz-Y** (60점): Description에 when-not 누락 → `/fz-skill update fz-Y` 실행 권장
3. **fz-Z** (65점): 과격 표현 2건 → 문구 완화 필요
```

### `--top3` 옵션

하위 3개 스킬만 상세 분석 + 구체적 수정 가이드 출력.

### `--with-trigger` 옵션

하위 3개 스킬에 대해 skill-creator의 `run_eval.py` Quick Trigger Eval 추가 실행.
상세: `skills/fz-skill/references/skill-creator-integration.md` "Quick Trigger Eval" 섹션.

- 각 스킬: should-trigger 3개 + should-not-trigger 2개 자동 생성 → 1회 실행
- 출력 테이블에 "Trigger" 컬럼 추가 (해당 스킬만, 나머지는 "-")
- skill-creator 미설치 시: WARN 안내 후 Static Analysis만 실행
- 스킬당 ~30초, 하위 3개만 = ~90초

### 정기 Benchmark 사이클

| 시점 | 트리거 | 권장 행동 |
|------|--------|----------|
| L3 변경 후 | modules/, guides/, templates/ 수정 | `benchmark` 실행하여 영향 확인 |
| 스킬 3개+ 수정 후 | 일괄 업데이트 완료 | `benchmark --top3`로 품질 저하 확인 |
| 주기적 | 2주마다 또는 대규모 작업 사이클 완료 후 | `benchmark` + `check` 연속 실행 |

> /fz Completion에서 스킬/모듈 변경이 포함된 파이프라인 완료 시 `benchmark` 실행을 제안한다.

### Gate: Benchmark Complete
- [ ] 전체 fz-* 스킬 Static Analysis 실행?
- [ ] 스킬별 점수 산출 + 정렬?
- [ ] 하위 3개 개선 제안 포함?

---

## create / edit / delete — `/fz-skill`로 이관

> 스킬/에이전트 CRUD 기능은 `/fz-skill`로 이관되었습니다.
> `/fz-skill`은 `templates/` + `guides/` 기반의 지능형 생성/수정/삭제를 제공합니다.

```bash
/fz-skill create fz-test "테스트 자동화 스킬"       # 새 스킬 생성
/fz-skill update fz-plan "description 개선"          # 기존 스킬 수정
/fz-skill delete fz-old                              # 스킬 삭제
/fz-skill new-agent test-runner "테스트 실행 에이전트" # 새 에이전트 생성
```

---

## 세션 관리

세션 데이터 경로: `$HOME/.claude/sessions`

---

## Boundaries

**Will**:
- fz- 스킬 인벤토리 조회 및 CRUD
- 의존성 그래프 및 통합 건강 체크 (fz + Agent)
- 전체 스킬 일괄 품질 평가 (benchmark)
- 거버넌스 프레임워크 (`modules/governance.md`)

**Will Not**:
- 개별 스킬 품질 평가 (→ `/fz-skill eval`)
- 워크플로우 가이드 (→ `/fz`)
- 팀 에이전트 생성 (→ `modules/team-core.md` + `modules/patterns/`, 각 스킬에서 직접 참조)
- 코드 수정 (→ 각 워크플로우 스킬)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| 스킬 파일 손상 | YAML 파싱 실패 보고 | 수동 확인 |
| 모듈 누락 | check에서 경고 | 생성 안내 |

## Completion → Next

- `check` → 문제 발견 시 `/fz-skill update` 안내
- `deps` → 의존성 이상 시 `/fz-skill update` 안내
- `benchmark` → 하위 스킬에 `/fz-skill eval` + `/fz-skill optimize` 안내
- `benchmark --with-trigger` → 하위 3개에 실측 트리거율 추가, 낮으면 `/fz-skill optimize` 권장
- `create` → 생성 완료 후 `check` 권장
