# Team Registry

> Capability 기반 동적 팀 구성. 스킬이 도메인을 지정하면 에이전트가 자동 수집된다.
> 새 에이전트 추가 시 이 레지스트리에 1줄 추가만으로 반영.

---

## 에이전트 Capabilities

> **model 컬럼 해석**: `default` = frontmatter 기본값, `promoted` = Lead가 스폰 시 승격하는 모델.
> Primary 에이전트의 frontmatter는 `model: sonnet`이지만, TEAM 스폰 시 Lead가 `model: "opus"`를 명시적으로 전달한다.
> 이 설계는 "동시 opus 최대 2개" 거버넌스를 Lead가 직접 제어하기 위함이다.

| 에이전트 | domain | lens | default | promoted | memory | skills | isolation | 비고 |
|---------|--------|------|---------|----------|--------|--------|-----------|------|
| search-symbolic | search | 심볼 정밀 탐색 (정의/참조/타입) | sonnet | — | — | — | — | Serena 도구 |
| search-pattern | search | 텍스트 패턴 넓은 범위 탐색 | sonnet | — | — | — | — | Grep/Glob 도구 |
| plan-structure | plan | 구현 구조 + Step 순서 설계 | sonnet | opus | project | — | — | Primary |
| plan-tradeoff | plan | 트레이드오프 + 대안 비교 평가 | sonnet | — | — | — | — | |
| plan-edge-case | plan | 엣지 케이스 + 실패 시나리오 발굴 | sonnet | — | — | — | — | |
| plan-impact | plan | 영향 범위 + 소비자 변경 추적 | sonnet | — | — | — | — | |
| impl-correctness | implement | 구현 정확성 + 테스트 작성 | sonnet | opus | project | — | worktree | Primary |
| impl-quality | implement | 코딩 표준 + 패턴 일관성 감시 | sonnet | — | — | — | — | |
| review-arch | review | 아키텍처 결정 + 레이어 위반 | sonnet | opus | project | arch-critic | — | Primary |
| review-quality | review | 코드 품질 + Dead Code + 성능 | sonnet | — | project | code-auditor | — | |
| review-correctness | review, implement | 기능 정확성 + 요구사항 충족 | sonnet | — | — | — | — | fz-code TEAM 배정 |
| review-direction | review | 방향성 적합성 + 대안 제시 + 비판적 평가 | sonnet | opus | — | — | — | direction-challenge 시 승격 |
| review-counter | review | 반론 + Devil's Advocate | sonnet | — | — | — | — | |
| memory-curator | memory | 교훈 발굴 + 컨텍스트 매칭 | sonnet | — | user | — | — | |

---

## 매칭 알고리즘

```
1. 스킬이 도메인을 지정 (예: fz-plan → domain: plan)
2. 레지스트리에서 해당 domain의 모든 에이전트 수집
3. promoted=opus인 에이전트 = Primary Worker (Lead가 스폰 시 model:"opus" 전달)
4. 나머지 = Supporting
5. 팀 크기에 따라 토폴로지 결정:
   - 2명 → Mesh
   - 3명+ → Star-enhanced (Supporting → Primary 경유)
```

## 스킬 → 도메인 매핑

| 스킬 | Primary | Supporting | 패턴 |
|------|---------|-----------|------|
| /fz-discover | plan-structure (O) | review-arch (S) | adversarial |
| /fz-plan | plan-structure (O) | review-arch (S), review-direction (S) | collaborative |
| /fz-code | impl-correctness (O) | review-arch (S), impl-quality (S), review-correctness (S) | pair-programming |
| /fz-fix | impl-correctness (O) | — (SOLO) | N/A |
| /fz-review | review-arch (O) | review-quality (S), review-counter (S) | live-review |
| /fz-peer-review | review-arch (O) | review-quality (S), review-counter (S) | live-review |
| /fz-search | — | search-symbolic (S), search-pattern (S) | cross-verify |
| /fz-memory | — | memory-curator (S) | solo/team |

## Truth-of-Source

스킬 YAML의 `team-agents` 필드가 팀 구성의 단일 진실 원천이다.
이 레지스트리와 `patterns/*.md`는 YAML과 동기화를 유지해야 한다.
불일치 발견 시 YAML 기준으로 나머지를 수정한다.

> 참조: `modules/governance.md` — Truth-of-Source 정책

## 확장 가이드

새 에이전트 추가:
1. `.claude/agents/{name}.md` 에이전트 파일 생성
2. 이 레지스트리의 Capabilities 테이블에 1줄 추가
3. 해당 도메인의 스킬에서 자동 수집됨 (서브셋 지정 시 추가 필요)

새 도메인 추가:
1. 에이전트 파일 + 레지스트리 등록
2. `patterns/` 디렉토리에 통신 패턴 파일 추가
3. 스킬의 team-agents에 도메인 또는 에이전트 지정

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-plan | plan 도메인 에이전트 수집 |
| /fz-code | implement 도메인 에이전트 수집 |
| /fz-review | review 도메인 에이전트 수집 |
| /fz-peer-review | review 도메인 에이전트 수집 |
| /fz-search | search 도메인 에이전트 수집 |
| /fz-discover | plan 도메인 서브셋 에이전트 수집 |
| /fz-memory | memory 도메인 에이전트 수집 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
