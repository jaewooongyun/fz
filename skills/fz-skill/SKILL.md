---
name: fz-skill
description: >-
  This skill should be used when the user wants to create, modify, evaluate, or optimize skills and agents.
  Make sure to use this skill whenever the user says: "스킬 만들어줘", "스킬 수정해줘",
  "스킬 평가해줘", "에이전트 만들어줘", "최적화해줘", "description 개선", "create a skill",
  "update this skill", "eval the skill", "optimize skill", "new agent".
  Covers: 스킬 만들, 스킬 수정, 스킬 평가, 에이전트 생성, 최적화, CRUD, 품질 평가(eval).
  Do NOT use for document-only work (use fz-doc) or ecosystem health check (use fz-manage check/benchmark).
user-invocable: true
argument-hint: "[create|update|delete|new-agent|eval|optimize] [대상] [--from-discover|--full|--runtime]"
allowed-tools: >-
  Read, Write, Edit, Grep, Glob,
  mcp__sequential-thinking__sequentialthinking
team-agents:
  primary: null
  supporting: []
composable: false
provides: [skill-management]
needs: [none]
intent-triggers:
  - "스킬.*만들|스킬.*생성|스킬.*수정|스킬.*삭제|스킬.*평가|에이전트.*만들|에이전트.*생성"
  - "create.*skill|new.*skill|update.*skill|delete.*skill|eval.*skill|create.*agent|new.*agent|optimize.*skill|description.*최적화|트리거.*테스트"
model-strategy:
  main: opus
  verifier: null
---

# /fz-skill - 스킬/에이전트 CRUD 스킬

> **행동 원칙**: 템플릿과 가이드라인을 기반으로 생태계에 일관되고 최적화된 스킬/에이전트를 생성하고, 기존 것을 개선하며, 안전하게 제거한다. 명확하면 자동(L3), 불명확하면 대화(L2), 항상 체크리스트(L1).

## 개요

> 서브커맨드: create | update | delete | new-agent | eval | optimize

- 스킬 생성: `templates/skill-template.md` + `guides/` 기반 지능형 생성
- 에이전트 생성: `templates/agent-template.md` 기반
- 품질 평가: Static Analysis + Runtime Trigger Eval + Triggering Test + Diff Eval
- **Description 최적화**: skill-creator의 `run_loop.py` 활용, 실측 트리거율 기반 자동 개선
- 문서 작성은 /fz-doc에 위임 (내부 모듈로 활용)
- 3단계 자동화: L3(자동) → L2(대화형) → L1(템플릿+체크리스트)

## 사용 시점

```bash
/fz-skill create fz-test "테스트 자동화 스킬"       # 새 스킬 생성
/fz-skill create fz-refactor --from-discover         # fz-discover 결과 기반 생성
/fz-skill update fz-plan "description 개선"          # 기존 스킬 수정
/fz-skill delete fz-old                              # 스킬 삭제
/fz-skill new-agent test-runner "테스트 실행 에이전트" # 새 에이전트 생성
/fz-skill eval fz-plan                               # 스킬 품질 평가
/fz-skill eval fz-plan --diff                        # 수정 전/후 비교 평가
/fz-skill eval fz-plan --runtime                     # 실측 트리거율 포함 평가
/fz-skill optimize fz-plan                           # description 자동 최적화
/fz-skill optimize fz-plan --full                    # description + 전체 eval 루프
```

## 가이드/템플릿 참조

| 리소스 | 경로 | 참조 시점 |
|--------|------|----------|
| 스킬 템플릿 | `templates/skill-template.md` | create 시 |
| 에이전트 템플릿 | `templates/agent-template.md` | new-agent 시 |
| 모듈 템플릿 | `templates/module-template.md` | 모듈 생성 필요 시 |
| 프롬프트 최적화 | `guides/prompt-optimization.md` | 모든 생성/수정 시 |
| 스킬 작성법 | `guides/skill-authoring.md` | create, update 시 |
| 에이전트/팀 가이드 | `guides/agent-team-guide.md` | new-agent 시 |

## /fz-doc 연계 (내부 모듈)

문서 본문 작성이 필요한 단계에서 /fz-doc의 워크플로우를 활용합니다:
- create → Phase 3에서 SKILL.md 본문 작성 시 /fz-doc 패턴 적용
- update → 문서 수정 시 /fz-doc의 최적화 검증 적용
- new-agent → 프롬프트 본문 작성 시 /fz-doc 패턴 적용

---

## create — 새 스킬 생성

### Phase 1: 요구사항 파악

1. **자동화 수준 판단**:
   - L3 (자동): 스킬 이름 + 목적이 명확 → 바로 생성
   - L2 (대화형): 범위/패턴 불명확 → AskUserQuestion
   - `--from-discover`: /fz-discover의 정제된 요구사항이 있으면 L3 적용

2. **기존 생태계 분석**:
   - `Glob("skills/*/SKILL.md")` → 기존 스킬 목록
   - `Grep(intent-triggers)` → 중복 트리거 사전 체크
   - provides/needs 체인에서 위치 결정

### Phase 2: 스켈레톤 생성

1. `Read(templates/skill-template.md)` → 템플릿 로드
2. YAML frontmatter 채우기:
   - `name`: fz-{name} 형식
   - `description`: 무엇+언제+언제아닌지+한영키워드
   - `provides/needs`: 기존 체인과 정합
   - `intent-triggers`: 중복 없는 한영 패턴
   - `allowed-tools`: 필요한 도구만
   - `team-agents`: 복잡도에 따라 설정 (`modules/team-registry.md` 참조)
   - `model-strategy`: 역할에 맞는 모델

3. 디렉토리 생성: `skills/fz-{name}/`

### Phase 3: 본문 작성 (/fz-doc 패턴)

1. `Read(guides/skill-authoring.md)` → 작성 가이드라인
2. `Read(guides/prompt-optimization.md)` → 10대 원칙
3. SKILL.md 본문 작성:
   - 행동 원칙 (1-2줄)
   - 개요 (프로세스 다이어그램 + 핵심 특징)
   - 사용 시점 (3-5개 예시)
   - Phase별 절차 + Gate 체크리스트
   - Boundaries (Will/Will Not + 대안)
   - 에러 대응 테이블
   - Completion → Next

### Phase 4: 검증

1. **10대 원칙 체크**: /fz-doc Phase 3 검증 체크리스트 적용
2. **생태계 정합성**:
   - provides/needs 체인 확인
   - intent-triggers 중복 없음 확인
   - 500줄 이하 확인
3. **출력**: 생성된 파일 경로 + 검증 결과

### Phase 5: Description Optimization (권장)

Gate 통과 후 실측 트리거율 기반 description 최적화를 제안한다.
- AskUserQuestion: "Description 최적화를 실행하시겠습니까? (skill-creator run_loop.py 활용, ~5분)"
- Yes → `optimize` 서브커맨드 실행
- No → 완료

### Gate: Skill Created
- [ ] YAML 13개 필드 중 필수 필드 완료?
- [ ] description에 무엇+언제+언제아닌지+한영?
- [ ] provides/needs가 기존 체인과 정합?
- [ ] intent-triggers 중복 없음?
- [ ] 본문 500줄 이하?
- [ ] Boundaries 섹션 포함?
- [ ] 10대 원칙 검증 통과?
- [ ] 아티팩트 기록 완료? (ASD 폴더 활성 시)

---

## update — 기존 스킬 수정

### 절차

1. `Read(skills/fz-{name}/SKILL.md)` → 현재 상태 파악
2. 사용자 지시 분석 → 수정 범위 결정
3. `Read(guides/prompt-optimization.md)` → 수정 시에도 원칙 적용
4. 수정 실행 (Edit 도구)
5. 검증: 10대 원칙 체크 + 생태계 정합성

### 특수 케이스

| 수정 유형 | 추가 확인 |
|----------|----------|
| description 변경 | intent-triggers와 일관성 |
| provides/needs 변경 | `modules/pipelines.md` 영향 확인 |
| allowed-tools 변경 | 에이전트 파일과 정합성 |
| intent-triggers 변경 | 다른 스킬과 중복 체크 |

---

## delete — 스킬 삭제

### 절차

1. **역의존성 확인**:
   - `Grep("fz-{name}", "skills/")` → 참조하는 스킬
   - `Grep("fz-{name}", "modules/")` → 참조하는 모듈
   - `Grep("fz-{name}", "agents/")` → 참조하는 에이전트

2. **영향 보고**:
   ```markdown
   ## 삭제 영향 분석: fz-{name}

   | 참조 위치 | 파일 | 영향 |
   |----------|------|------|
   | ... | ... | ... |
   ```

3. **사용자 확인**: AskUserQuestion
   - 역참조 있으면 → 경고 + 수정 대상 목록
   - 역참조 없으면 → 삭제 확인

4. **삭제 실행**: 디렉토리 전체 삭제

5. **후처리**: pipelines.md, skill-template.md 토큰 레지스트리 정리 안내

---

## new-agent — 새 에이전트 생성

### 절차

1. `Read(templates/agent-template.md)` → 템플릿 로드
2. `Read(guides/agent-team-guide.md)` → 에이전트 작성법
3. YAML frontmatter 채우기:
   - `name`: `{domain}-{specialty}` 형식 (`modules/team-registry.md` 네이밍 규칙 준수)
   - `description`: 역할+전문성+팀컨텍스트
   - `model`: 기본 sonnet (승격 조건 주석)
   - `tools`: 최소 필요 도구
4. 프롬프트 본문 작성 (/fz-doc 패턴):
   - 역할 선언 1줄
   - MCP 도구 4-tier 전략
   - Peer-to-Peer 통신 규칙
   - 워크플로우
   - 결과 보고 형식
5. 파일 생성: `agents/{name}.md`
6. **team-registry.md 업데이트**: `modules/team-registry.md`에 에이전트 1줄 추가
7. 검증: agent-team-guide 체크리스트 적용

---

## eval — 스킬 품질 평가

대상 스킬의 품질을 자동 분석하고 개선 제안을 생성한다.
테스트 프레임워크: `guides/skill-testing.md` 참조.

### 절차

1. **대상 스킬 로드**:
   - `Read(skills/fz-{name}/SKILL.md)` → YAML + 본문 파싱

2. **Static Analysis** (자동):

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

3. **Runtime Trigger Eval** (`--runtime` 옵션 또는 기본 포함):
   skill-creator의 `run_eval.py`로 실제 `claude -p` 호출하여 트리거율 실측.
   - 상세: `references/skill-creator-integration.md` 참조
   - should-trigger 5개 + should-not-trigger 5개 자동 생성
   - `run_eval.py` 실행 → 실측 trigger rate 산출
   - PASS 기준: ≥80% 정확도
   - **skill-creator 미설치 시**: SKIP (WARN) + 설치 안내, 정적 eval만 계속

4. **Triggering Test** (반자동, Runtime 미실행 시 폴백):
   - description 키워드에서 should-trigger 쿼리 5개 자동 생성
   - Boundaries Will Not에서 should-NOT-trigger 쿼리 3개 자동 생성
   - 각 쿼리에 대해 트리거 적합성 자체 판단
   - 결과를 사용자에게 확인 요청

4. **Diff Eval** (`--diff` 옵션):
   - 수정 전 스냅샷과 현재 상태 비교
   - description 키워드 커버리지 변화
   - 크기 변화 + 새로 추가/제거된 섹션

5. **리포트 출력**:

   ```markdown
   ## eval 결과: fz-{name}

   | 항목 | 결과 | 비고 |
   |------|------|------|
   | Static Analysis | 7/8 PASS | Few-shot 2개 (WARN) |
   | Runtime Trigger | 8/10 (80%) | should-not 1개 오트리거 |
   | Triggering (자체) | 7/8 (87%) | "아키텍처" 미트리거 |

   총점: 85/100 (Static 65 + Runtime 16 + Triggering 4)
   개선 제안:
   - description에 "아키텍처" 키워드 추가
   - Few-shot 예시 1개 추가 (엣지 케이스)
   ```

### Gate: Eval Complete
- [ ] Static Analysis 전체 항목 실행?
- [ ] Triggering Test 정확도 ≥90%?
- [ ] FAIL/WARN 항목에 개선 제안 포함?

---

## Few-shot 예시

```
BAD (템플릿 무시 생성):
/fz-skill create fz-test
→ 빈 파일에 자유 형식으로 작성. YAML 필수 필드 누락, 기존 체인 미확인.

GOOD (L3 자동 생성):
/fz-skill create fz-test "테스트 자동화 스킬"
Phase 1: 기존 스킬 Glob → 중복 트리거 체크 → provides/needs 위치 결정
Phase 2: skill-template.md 로드 → YAML 13필드 채우기 → 디렉토리 생성
Phase 3: skill-authoring.md + prompt-optimization.md 참조 → 본문 작성
Phase 4: 10대 원칙 체크 + 생태계 정합성 검증
```

```
BAD (역의존성 미확인 삭제):
/fz-skill delete fz-old → 바로 삭제
→ pipelines.md, 다른 스킬의 needs에서 참조 중이면 체인 끊김.

GOOD (역의존성 분석 후 삭제):
/fz-skill delete fz-old
Phase 1: Grep("fz-old") → skills/, modules/, agents/ 역참조 확인
Phase 2: 영향 보고 + 사용자 확인 → 삭제 + 후처리 안내
```

---

## optimize — Description 최적화

skill-creator의 `run_loop.py`를 활용하여 description의 실측 트리거 정확도를 자동 최적화한다.
상세: `references/skill-creator-integration.md`

### 절차 (요약)

1. **경로 탐색 + Dependency Check**: skill-creator 플러그인 Glob 탐색, claude CLI + anthropic SDK 확인
2. **Eval 쿼리 생성 + 사용자 검토**: intent-triggers → should-trigger 10개, Boundaries → should-not-trigger 10개 자동 생성 → eval_review.html로 브라우저 검토
3. **최적화 루프**: `run_loop.py --max-iterations 5` 백그라운드 실행 (train/test 60/40 split, 쿼리당 3회)
4. **결과 적용**: best_description 전후 비교 → 사용자 승인 → SKILL.md 반영

`--full` 옵션: description 최적화 + 전체 eval 루프 (with-skill vs baseline 비교, grading, benchmark viewer)

### Gate: Optimize Complete
- [ ] skill-creator 경로 탐색 성공?
- [ ] Eval 쿼리 20개 생성 + 사용자 검토 완료?
- [ ] run_loop.py 실행 완료?
- [ ] best_description 사용자 승인?

---

## Boundaries

**Will**:
- 새 스킬 생성 (templates + guides 기반)
- 기존 스킬 수정 (최적화 원칙 적용)
- 스킬 삭제 (역의존성 분석 포함)
- 새 에이전트 생성 (template + guide 기반)
- 스킬 품질 평가 (eval — Static + Runtime Trigger)
- Description 자동 최적화 (optimize — skill-creator 연동)
- /fz-doc 패턴으로 문서 품질 보장
- 생태계 정합성 검증

**Will Not**:
- 문서만 작성/수정 (→ /fz-doc)
- 스킬 목록/의존성 조회 (→ fz-manage list/deps)
- 전체 스킬 일괄 평가 (→ fz-manage benchmark)
- 코드 수정 (→ fz-code, fz-fix)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| 템플릿 없음 | 기존 스킬 패턴에서 추출 | 사용자에게 안내 |
| 가이드 없음 | 내장 원칙 기반 | 사용자에게 안내 |
| intent-triggers 중복 | 대안 패턴 제안 | 사용자 선택 |
| provides/needs 체인 끊김 | 연결 스킬 제안 | AskUserQuestion |
| 500줄 초과 | 모듈 분리 제안 | 사용자 판단 |
| eval 대상 스킬 없음 | 스킬 목록 출력 | AskUserQuestion |

## Completion → Next

```bash
/fz-skill eval fz-{name}       # 품질 평가 (Static + Runtime Trigger)
/fz-skill optimize fz-{name}   # description 자동 최적화 (생성/수정 후 권장)
/fz-manage check                # 생태계 건강 체크
/fz-manage benchmark            # 전체 스킬 일괄 평가
```
