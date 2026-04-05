---
name: fz-doc
description: >-
  This skill should be used when the user wants to write, improve, or optimize documentation files.
  Make sure to use this skill whenever the user says: "문서 작성해줘", "문서 개선해줘",
  "SKILL.md 만들어줘", "CLAUDE.md 수정", "가이드 작성", "프롬프트 개선", "document this",
  "write the SKILL.md", "improve CLAUDE.md", "optimize the description", "write guide".
  Covers: 문서, 작성, 개선, SKILL.md, CLAUDE.md, 에이전트 프롬프트, 모듈 문서, 가이드라인 기반 최적화.
  Do NOT use for code implementation (use fz-code) or code review (use fz-review).
user-invocable: true
argument-hint: "[대상 파일/스킬] [--check] [--optimize]"
allowed-tools: >-
  Read, Write, Edit, Grep, Glob,
  mcp__sequential-thinking__sequentialthinking
team-agents:
  primary: null
  supporting: []
composable: true
provides: [documentation]
needs: [none]
intent-triggers:
  - "문서|작성|개선|description|가이드|스킬.*작성|에이전트.*작성"
  - "document|write.*skill|improve.*description|optimize.*prompt"
model-strategy:
  main: opus
  verifier: null
---

# /fz-doc - 문서 작성 + 최적화 스킬

> **행동 원칙**: 가이드라인과 최적화 원칙을 참조하여 일관되고 성능 최적화된 문서를 작성한다. 명확하면 자동 생성(L3), 불명확하면 대화형(L2), 항상 체크리스트 제공(L1).

## 개요

> 대상 분석 → 가이드 참조 → 문서 생성/수정 → 최적화 검증

- 스킬 SKILL.md, 에이전트 프롬프트, CLAUDE.md, 모듈 문서 작성
- `guides/` 가이드라인 기반 품질 보장
- `/sc:document` 연계: 범용 문서 작업 위임 가능
- 3단계 자동화: L3(자동) → L2(대화형) → L1(템플릿+체크리스트)

## 사용 시점

```bash
/fz-doc "fz-search description 개선해줘"          # description 최적화
/fz-doc "새 에이전트 프롬프트 작성해줘"            # 에이전트 문서 생성
/fz-doc "CLAUDE.md에 새 규칙 추가해줘"            # CLAUDE.md 수정
/fz-doc --check fz-plan                           # 기존 스킬 문서 검증
/fz-doc --optimize fz-code                        # 기존 스킬 최적화
```

## 가이드 참조

| 가이드 | 경로 | 참조 시점 |
|--------|------|----------|
| 프롬프트 최적화 | `guides/prompt-optimization.md` | 모든 문서 작성/수정 시 |
| 스킬 작성법 | `guides/skill-authoring.md` | 스킬 문서 작성 시 |
| 에이전트/팀 가이드 | `guides/agent-team-guide.md` | 에이전트 문서 작성 시 |
| 스킬 템플릿 | `templates/skill-template.md` | 스킬 문서 생성 시 |
| 에이전트 템플릿 | `templates/agent-template.md` | 에이전트 문서 생성 시 |
| 모듈 템플릿 | `templates/module-template.md` | 모듈 문서 생성 시 |

## sc: 활용 (SuperClaude 연계)

| 상황 | sc: 명령어 | 용도 |
|------|-----------|------|
| 범용 문서 생성 | `/sc:document` | API 문서, 컴포넌트 문서 등 코드 기반 문서 |
| 분석 필요 시 | `/sc:analyze` | 기존 코드/스킬 분석 후 문서 반영 |

---

## Phase 1: 대상 분석

### 절차

1. **대상 식별**: 스킬 / 에이전트 / CLAUDE.md / 모듈 중 어느 것인지
2. **기존 내용 읽기**: `Read` → 현재 상태 파악
3. **자동화 수준 결정**:
   - **L3 (자동)**: 요청이 명확하고 템플릿 적용 가능 → 바로 생성
   - **L2 (대화형)**: 선택이 필요한 부분 → AskUserQuestion
   - **L1 (체크리스트)**: 항상 최종 체크리스트 출력

### Gate 1: Target Identified
- [ ] 대상 유형 식별 (스킬/에이전트/CLAUDE.md/모듈)?
- [ ] 기존 내용 파악 완료?
- [ ] 자동화 수준 결정?

---

## Phase 2: 가이드 참조 + 문서 생성

### 스킬 문서 작성 시

1. `Read(templates/skill-template.md)` → YAML + 본문 스켈레톤
2. `Read(guides/skill-authoring.md)` → 작성 가이드라인
3. `Read(guides/prompt-optimization.md)` → 10대 원칙
4. 문서 생성/수정:
   - description: 무엇+언제+언제아닌지+한영키워드 (원칙 2)
   - 본문 500줄 이하 (원칙 3)
   - Few-shot 예시 포함 (원칙 5)
   - Gate 체크리스트 (원칙 6)
   - Boundaries Will/Will Not (원칙 9)
   - 자연스러운 표현 (원칙 8)

### 에이전트 문서 작성 시

1. `Read(templates/agent-template.md)` → YAML + 프롬프트 스켈레톤
2. `Read(guides/agent-team-guide.md)` → 에이전트 작성법
3. 문서 생성/수정:
   - 역할 선언 1줄
   - MCP 도구 4-tier 전략
   - Peer-to-Peer 통신 규칙
   - 결과 보고 형식

### CLAUDE.md 수정 시

1. `Read(guides/prompt-optimization.md)` → Context Rot 대응
2. 핵심 지시를 앞부분에 배치
3. 400줄 이내 유지 (기존 규칙)

### 모듈 문서 작성 시

1. `Read(templates/module-template.md)` → 모듈 스켈레톤
2. 참조 스킬 테이블 작성
3. 500줄 이하, 100줄+ 시 목차

### Gate 2: Document Ready
- [ ] 관련 가이드를 참조했는가?
- [ ] 템플릿 구조를 따랐는가?
- [ ] 10대 원칙 적용했는가?

---

## Phase 3: 최적화 검증

생성/수정된 문서를 `prompt-optimization.md`의 10대 원칙으로 검증합니다.

### 검증 체크리스트

```markdown
## 최적화 검증 결과

### 10대 원칙 체크
- [ ] 원칙 1: Claude가 모르는 것만 포함?
- [ ] 원칙 2: Description에 무엇+언제+언제아닌지+한영?
- [ ] 원칙 3: 500줄 이하 + Progressive Disclosure?
- [ ] 원칙 4: 자유도가 위험도에 맞는가?
- [ ] 원칙 5: Few-shot 예시 포함?
- [ ] 원칙 6: 피드백 루프(Gate) 내장?
- [ ] 원칙 7: 도구 설명 충분?
- [ ] 원칙 8: 과격 표현 없음?
- [ ] 원칙 9: Boundaries 명확?
- [ ] 원칙 10: 평가 시나리오 고려?

### Anti-Pattern 체크
- [ ] 깊은 참조 중첩 없음?
- [ ] 비일관적 용어 없음?
- [ ] 시간 의존 정보 없음?
```

### --check 모드

기존 문서를 읽고 위 체크리스트로 진단만 수행. 수정하지 않음.

```bash
/fz-doc --check fz-plan    # 진단 결과 + 개선 제안 출력
```

### --optimize 모드

진단 + 자동 수정까지 수행.

```bash
/fz-doc --optimize fz-code  # 진단 → 수정 → 재검증
```

---

## Few-shot 예시

```
BAD (원칙 미적용 문서):
## 역할
이 스킬은 코드를 리뷰합니다. 코드를 분석하고 문제를 찾습니다.
→ 행동 원칙 누락, 중복 서술, Phase/Gate 구조 없음.

GOOD (10대 원칙 적용):
> **행동 원칙**: 코드 변경의 아키텍처 적합성을 검증하고 품질 이슈를 식별한다.
## 개요
> Phase 1 (Analysis) → Phase 2 (Review) → Gate → 보고
→ 행동 원칙 1줄, 프로세스 다이어그램, 명확한 Gate 체크리스트.
```

```
BAD (Boundaries 불명확):
이 스킬은 다양한 작업을 수행합니다.

GOOD (Will/Will Not + 대안):
**Will**: 스킬 문서 작성/수정/최적화, 검증(--check)
**Will Not**: 코드 수정 (→ /fz-code), 생태계 점검 (→ /fz-manage)
```

---

## Boundaries

**Will**:
- 스킬 SKILL.md 작성/수정/최적화
- 에이전트 프롬프트 작성/수정
- CLAUDE.md 수정
- 모듈 문서 작성
- 가이드라인 기반 검증 (--check)
- 자동 최적화 (--optimize)
- `/sc:document` 연계 (범용 문서)

**Will Not**:
- 코드 직접 수정 (→ /fz-code, /fz-fix)
- 스킬 디렉토리 CRUD (→ /fz-skill)
- 빌드 실행 (→ /fz-code)
- provides/needs 체인 검증 (→ /fz-manage check)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| 가이드 파일 없음 | 내장 원칙 기반 작성 | 사용자에게 가이드 생성 안내 |
| 템플릿 파일 없음 | 기존 스킬 패턴 참조 | 사용자에게 템플릿 생성 안내 |
| 500줄 초과 | 분리 제안 (modules/ 활용) | 사용자 판단 |
| description 품질 낮음 | 구체적 개선안 제시 | Few-shot 예시 제공 |

## Completion → Next

```bash
/fz-skill create "새 스킬"   # 스킬 전체 생성 (CRUD)
/fz-manage check             # 생태계 건강 체크
/fz-doc --check fz-plan      # 다른 스킬 문서 검증
```
