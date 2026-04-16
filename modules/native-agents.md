# L3 네이티브 에이전트 통합 정책

> Claude Code 내장 에이전트 중 fz에 없는 고유 가치를 가진 에이전트만 선별 통합.
> fz 커스텀 에이전트(L1)와 역할 중복 없이 보강 관점만 추가.

## 채택 에이전트

| 에이전트 | 고유 가치 | 배치 Phase | 스폰 방식 |
|---------|----------|-----------|----------|
| **silent-failure-hunter** | catch 블록 조용한 실패, 부적절한 fallback 탐지 | review Phase 5 | `Agent(subagent_type="silent-failure-hunter")` background |
| **type-design-analyzer** | 타입 캡슐화, 불변량 표현, 정량 평가 | review Phase 5 | `Agent(subagent_type="type-design-analyzer")` background |
| **code-simplifier** | 프로젝트 가이드라인 기반 코드 정리 | review Phase 6 (pre-ship) | `Agent(subagent_type="code-simplifier")` background |
| **deep-research-agent** | 외부 지식 수집 (multi-hop reasoning) | discover Phase 2 | `Agent(subagent_type="deep-research-agent")` foreground |

## 불채택 에이전트 (fz가 더 우수)

| 에이전트 | fz 대체 | 불채택 이유 |
|---------|--------|-----------|
| code-reviewer | review-arch + review-quality | fz가 iOS 7관점 + 라이브러리 시맨틱 |
| pr-test-analyzer | review-correctness | fz가 요구사항-구현 매핑 |
| Plan | plan-structure + plan-impact | fz가 Exhaustive Impact Scan |
| Explore | search-symbolic + search-pattern | fz가 이중 경로 교차 검증 |

## 스폰 규칙

1. **TeamCreate와 독립**: L3 에이전트는 Agent() 도구로 스폰. fz TEAM의 2.5-Turn Protocol에 참여하지 않음
2. **Background 스폰**: review에서 fz TEAM과 병렬로 background 실행
3. **결과 통합**: Lead가 L3 결과 수신 → Issue Tracker에 merge (fz 이슈와 동일 형식)
4. **조건부 스폰**: 아래 조건 충족 시에만 스폰

### 스폰 조건

| 에이전트 | 스폰 조건 | 비용 절감 |
|---------|----------|----------|
| silent-failure-hunter | diff에 try/catch, do-catch, Result, completion handler 포함 | 에러 처리 없으면 스킵 |
| type-design-analyzer | diff에 struct/class/enum 신규 정의 포함 | 기존 타입 수정만이면 스킵 |
| code-simplifier | review Phase 6 진입 시 (반복 개선 중) | Phase 5 통과 시 불필요 |
| deep-research-agent | 외부 기술/라이브러리 탐색 필요 시 | 코드베이스 내부 작업이면 스킵 |

### 결과 형식

L3 에이전트 결과를 Issue Tracker에 통합할 때:

```markdown
| source | category | severity | description |
|--------|----------|----------|-------------|
| silent-failure-hunter | error_handling | Major | {설명} |
| type-design-analyzer | type_design | Minor | {설명} |
```

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-review | Phase 5 L3 에이전트 스폰 |
| /fz-discover | deep-research-agent 스폰 |

## 팀 피드백 프로토콜 (TEAM 모드)

L3 결과가 TEAM과 동시에 진행될 때의 피드백 흐름:

1. L3: `Agent(run_in_background=true)` 스폰
2. 결과 도착 시 Lead 수신
3. **TEAM Round 0.5 전**: Lead → Primary에게 `[L3 피드백]` SendMessage (team-core.md 참조)
   → Primary가 iOS 특화 렌즈로 재분석 → severity 조정 + 연쇄 이슈 식별
4. **TEAM Round 0.5 이후**: Lead가 직접 Issue Tracker에 merge (기존 동작)

우선순위: TEAM 피어 통신 > L3 피드백 (Round 중간에 끼어들지 않음)

### ⛔ Anti-Pattern
- L3 에이전트를 TeamCreate로 스폰 금지 (2.5-Turn에 범용 에이전트 참여 = 품질 저하)
- TEAM Round 1~2 실행 중 L3 피드백 끼어들기 금지

## 설계 원칙

- Progressive Disclosure Level 3 (review/discover에서 필요 시 로드)
- L1 fz 에이전트 품질 > L3 → L1 우선, L3는 보강만
- 500줄 이하 유지
