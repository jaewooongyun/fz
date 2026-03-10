# 스킬 트러블슈팅 가이드

> fz-* 스킬에서 발생하는 일반적인 문제의 진단과 해결 방법.
> Anthropic 32p Skills Guide의 Under/Over-triggering, Instructions Not Followed 패턴 기반.

---

## 1. Triggering 문제 진단

### 1.1 Undertriggering (스킬이 트리거되지 않음)

**증상:**
- 관련 쿼리에서 스킬이 자동 트리거되지 않음
- 사용자가 매번 `/fz-{name}`으로 수동 호출해야 함
- "이 스킬이 있는 줄 몰랐어요" 피드백 발생

**진단:**
1. "Ask Claude" 테스트 실행 (`.claude/guides/skill-testing.md` §3)
2. Claude가 description을 정확히 인용하는지 확인
3. 누락된 키워드 식별

**솔루션:**

| 원인 | 조치 |
|------|------|
| 키워드 부족 | description에 기술 용어 추가 (한국어+영어) |
| 트리거 구문 협소 | intent-triggers에 동의어/관련어 확대 |
| 너무 전문적 | 일반적인 표현도 포함 ("고쳐줘" + "fix") |

**Few-shot: fz-search description 개선**

```
BEFORE:
  "프로젝트 코드 구조 분석 스킬"
  → "코드 어디 있어?" 쿼리에 트리거 안 됨

AFTER:
  "프로젝트 코드 탐색 + 구조 분석 + 의존성 추적 스킬.
   Use when exploring code structure, tracing symbol dependencies,
   finding architecture relationships.
   Do NOT use for code modification (use fz-fix or fz-code)."
  → "코드 어디 있어?", "구조 분석해줘", "의존성 추적" 모두 트리거
```

### 1.2 Overtriggering (스킬이 과도하게 트리거)

**증상:**
- 무관한 쿼리에서 스킬이 활성화됨
- 사용자가 스킬을 비활성화하거나 우회함
- 다른 스킬과 충돌 (의도치 않은 스킬이 선택됨)

**진단:**
1. Triggering Test에서 should-NOT-trigger 실패율 확인
2. intent-triggers 패턴이 너무 광범위한지 검토
3. description에 과격한 표현이 있는지 확인

**솔루션:**

| 원인 | 조치 |
|------|------|
| 광범위한 키워드 | 구체적 키워드로 교체 ("코드" → "코드 탐색") |
| 부정 트리거 부재 | "Do NOT use for X (use Y)" 추가 |
| 과격한 표현 | "MUST", "ALWAYS" 제거 (원칙 8 적용) |

**Few-shot: 범위 좁히기**

```
BEFORE:
  intent-triggers:
    - "코드|개발|프로젝트"    # 모든 개발 관련 쿼리에 매칭
AFTER:
  intent-triggers:
    - "탐색|구조|의존성|심볼"  # 탐색 전용 키워드로 한정
    - "explore|structure|dependency|symbol"
```

### 1.3 intent-triggers 중복 충돌

**진단:**
```bash
/fz-manage check   # 항목 #4: intent-triggers 중복 검증
```

**해결 절차:**
1. 중복 키워드 식별 (예: "코드"가 fz-code, fz-fix, fz-search에 동시 존재)
2. 각 스킬의 핵심 키워드와 공유 키워드를 분리
3. 공유 키워드를 더 구체적인 표현으로 교체
4. description의 부정 트리거로 상호 경계 명시

---

## 2. Instructions Not Followed (지시 미준수)

### 2.1 원인 1: 지시가 너무 장황

**증상:** Claude가 SKILL.md의 일부 지시를 무시하거나 순서를 건너뜀.

**솔루션:**
- 산문 → 불릿 포인트로 전환
- 핵심 지시만 남기고 세부는 Level 3 참조로 분리
- 500줄 이하 유지 확인

```
BAD:  "코드를 분석할 때는 먼저 파일 구조를 파악하고, 그 다음에 핵심 함수를
       찾아서 의존성을 추적하는데, 이때 Serena의 find_symbol을 사용하면
       효과적입니다. 그런 다음..."

GOOD: 1. 파일 구조 파악 (Glob)
      2. 핵심 함수 탐색 (mcp__serena__find_symbol)
      3. 의존성 추적 (mcp__serena__find_referencing_symbols)
```

### 2.2 원인 2: 핵심 지시가 묻힘

**증상:** 중요한 규칙이 문서 중간에 있어 Claude가 놓침.

**솔루션:**
- 핵심 지시를 문서 앞부분(행동 원칙) 또는 끝부분(체크리스트)에 배치
- Context Rot 근거: 중간 위치 정보 검색률 30%+ 하락

```
구조: 핵심 지시 (앞) → 세부 Phase (중간) → 체크리스트/Gate (끝)
```

### 2.3 원인 3: 모호한 언어

**증상:** Claude가 지시를 임의로 해석하여 일관성 없는 결과.

**솔루션:**
- 모호한 표현 → 구체적 동사 + 검증 가능한 조건

```
BAD:  "코드 품질을 확인하라"
GOOD: "빌드 성공 여부를 xcodebuild로 검증하라. 실패 시 에러 메시지를 분석하고 수정하라."

BAD:  "적절히 처리하라"
GOOD: "에러 시 테이블의 폴백 전략을 순서대로 실행하라."
```

### 2.4 원인 4: 모델 laziness (검증 건너뜀)

**증상:** Claude가 Gate 체크를 건너뛰거나 검증 없이 완료 보고.

**솔루션:**
- SKILL.md에 과격한 표현을 다시 넣지 않는다 (overtriggering 위험)
- **user prompt** 쪽에 격려 문구를 배치한다

```
User prompt에 추가:
- "Take your time to do this thoroughly"
- "Quality is more important than speed"
- "Do not skip validation steps"
```

> **공식 가이드**: "Adding this to user prompts is more effective than in SKILL.md"
> SKILL.md에 anti-laziness를 넣으면 모든 호출에 오버헤드가 발생하지만,
> user prompt에 넣으면 필요한 세션에서만 적용된다.

---

## 3. 실행 에러 카테고리

### 3.1 MCP 도구 연결 실패

**증상:** `mcp__serena__find_symbol` 등 MCP 도구 호출 시 에러.

**Fallback 4-tier 전략:**

| Tier | 도구 | 조건 |
|------|------|------|
| 1 | Serena MCP (LSP 기반) | 기본 시도 |
| 2 | Context7 MCP (문서 기반) | Serena 실패 시 |
| 3 | Grep/Glob (텍스트 기반) | MCP 전체 실패 시 |
| 4 | 수동 분석 (Read) | 모든 자동화 실패 시 |

### 3.2 빌드 실패 반복

**증상:** 구현 후 빌드가 3회 이상 연속 실패.

**래더 전략:**

```
1차 실패: 에러 메시지 분석 + 자동 수정
2차 실패: 전략 변경 (다른 접근법 시도)
3차 실패: 사용자에게 에스컬레이션
```

### 3.3 Large Context Issues

**증상:** 스킬 실행 중 컨텍스트 윈도우 소진, 후반부 지시 무시.

**솔루션:**
- Progressive Disclosure 강화 (Level 3 참조 적극 활용)
- SKILL.md 줄 수 재확인 (500줄 이하)
- 스킬 수 참고: Anthropic 공식 "20-50 skills is a good range"
- 불필요한 모듈 참조 제거

### 3.4 에이전트 통신 실패

**증상:** 팀 에이전트 간 통신 타임아웃, 결과 누락.

**솔루션:**
- Context 소진 시 새 에이전트를 스폰한다 (기존 에이전트 컨텍스트 리셋)
- 메시지 크기를 줄인다 (핵심 결과만 전달)
- SendMessage의 summary 필드를 활용한다

### 3.4b TEAM 프로토콜 위반

**증상:** 에이전트가 동조 수렴하거나, 독립 분석 없이 합의, Gate 스킵.

| 위반 | 원인 | 대응 |
|------|------|------|
| 동조 수렴 (모든 에이전트 동일 의견) | Round 1 독립성 미준수 | Task Brief에 "Round 1: 다른 에이전트 초안 참조 금지" 명시 |
| Gate 스킵 | Lead가 Gate를 "선택"으로 인식 | cross-validation.md Gate 절차적 강제 참조 |
| 합의/불합의 미보고 | Round 0.5 규칙 누락 | Task Brief에 "[합의]/[불합의] 마커 필수" 포함 |
| Task Brief 미구조화 | 역할/목표/제약 모호 | 5요소 형식 적용: [Role] [Context] [Goal] [Constraints] [Deliverable] |

### 3.5 Codex CLI 관련 에러

**증상:** `codex review`, `codex exec` 실행 실패.

| 에러 | 대응 | 폴백 |
|------|------|------|
| Codex CLI 미설치 | 설치 안내 | sc:analyze 단독 실행 |
| `codex review` 네트워크 에러 | `codex exec` + diff 인라인 | 수동 리뷰 |
| `--output-schema` 파싱 실패 | 스키마 검증 | Claude 직접 파싱 |
| 3-Tier 스킬 디스커버리 실패 | Tier 순차 폴백 | 인라인 프롬프트 (Tier 3) |
| Codex 응답 토큰 제한 초과 | diff 분할 전략 (Medium/Large) | 핵심 파일만 리뷰 |

---

## 4. 디버깅 Quick Reference

### "Ask Claude" 기법

```
질문: "fz-{name} 스킬은 언제 쓰는 거야?"
분석: Claude가 description을 정확히 인용하는가?
조치: 누락 키워드 → description에 추가
상세: .claude/guides/skill-testing.md §3
```

### /fz-manage check 항목별 대응

| 항목 | 실패 시 조치 |
|------|------------|
| #1 YAML 필수 필드 | name, description, user-invocable, allowed-tools 확인 |
| #2 MCP 유효성 | MCP 서버 상태 확인, allowed-tools에서 무효 도구 제거 |
| #3 provides/needs 체인 | 누락된 provides 토큰 추가, needs 체인 DAG 검증 |
| #4 intent-triggers 중복 | §1.3 절차대로 키워드 분리 |
| #5 스킬 크기 | 500줄 초과 → 모듈 분리 (Level 3) |
| #6 깨진 파일 참조 | 경로 오류 수정, 삭제된 파일 참조 제거 |
| #7 에이전트 파일 | `.claude/agents/` 내 YAML 필드 확인 |
| #8 Team MCP 호환 | 팀 불가 MCP 참조 제거 |
| #9 테스트 케이스 | "## 테스트 케이스" 섹션 또는 참조 링크 추가 |
| #10 Triggering 테스트 | should + should-NOT 최소 3개 작성 |

### Serena Fallback 체인

```
1. mcp__serena__find_symbol        → 심볼 정의 탐색
2. mcp__serena__find_referencing_symbols → 참조 추적
3. mcp__serena__search_for_pattern → 패턴 기반 탐색
4. mcp__serena__get_symbols_overview → 파일 심볼 개요
   ↓ 실패 시
5. Grep → 텍스트 패턴 탐색
6. Glob → 파일 패턴 탐색
7. Read → 수동 파일 읽기
```

---

## 참조

- 테스트 방법론: `.claude/guides/skill-testing.md`
- 스킬 작성법: `.claude/guides/skill-authoring.md`
- 프롬프트 최적화: `.claude/guides/prompt-optimization.md`
- Codex 교차검증: `.claude/skills/fz-codex/SKILL.md`
- 건강 체크: `/fz-manage check`
