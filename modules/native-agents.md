# L3 네이티브 에이전트 통합 정책

> **Sources (last audited: 2026-09-25 — 모델 사실 축):** `guides/llm-references.md` §1 정본 대조 완료 (effort 값 선택 지침 Opus 5.5·Fable 5.1 반영 — :31 한 줄만 대조). 2026-11-16 — 모델 사실 축(Fable 5.2): 같은 지침 줄의 Lead 기본값 구절만 대조.
>
> 선택 플러그인 `pr-review-toolkit`(공식 마켓플레이스) 에이전트 중 fz에 없는 고유 가치를 가진 에이전트만 선별 통합. 런타임 이름은 접두 꼴(`pr-review-toolkit:<이름>`)이고, 설치돼 있지 않으면 띄우지 않는다(스폰 규칙 6).
> fz 커스텀 에이전트(L1)와 역할 중복 없이 보강 관점만 추가.

## 채택 에이전트

| 에이전트 | 고유 가치 | 배치 Phase | 스폰 방식 |
|---------|----------|-----------|----------|
| **pr-review-toolkit:silent-failure-hunter** | catch 블록 조용한 실패, 부적절한 fallback 탐지 | review Phase 5 | `Agent(subagent_type="pr-review-toolkit:silent-failure-hunter")` background |
| **pr-review-toolkit:type-design-analyzer** | 타입 캡슐화, 불변량 표현, 정량 평가 | review Phase 5 | `Agent(subagent_type="pr-review-toolkit:type-design-analyzer")` background |
| **pr-review-toolkit:code-simplifier** | 프로젝트 가이드라인 기반 코드 정리 | review Phase 6 (pre-ship) | `Agent(subagent_type="pr-review-toolkit:code-simplifier")` background |

## 불채택 에이전트 (fz가 더 우수)

| 에이전트 | fz 대체 | 불채택 이유 |
|---------|--------|-----------|
| code-reviewer | review-arch + review-quality | fz가 iOS 7관점 + 라이브러리 시맨틱 |
| pr-test-analyzer | review-correctness | fz가 요구사항-구현 매핑 |
| Plan | plan-structure + plan-impact | fz가 Exhaustive Impact Scan |
| Explore | search-symbolic + search-pattern | fz가 이중 경로 교차 검증 |

## fz 에이전트 — Lead 가 직접 띄우는 둘

위 두 표(선택 플러그인)와 별개다. 스킬이 Workflow 를 거치지 않고 Lead 에게 `Agent` 도구로 바로 띄우라고 적은 fz 에이전트이고, 둘 다 정의의 `tools:` 에 쓰기 도구가 없다(읽기 전용). 그 밖의 fz 에이전트는 Workflow 로 띄운다.

| 에이전트 | Lead 가 띄우는 때 | 정하는 스킬 |
|---------|-----------------|-----------|
| **fz:review-correctness** | GPT 검증을 부르지 못할 때 대신하는 새 컨텍스트 검증 1회 · 요구 부합 검증 | `skills/fz-review/SKILL.md` 검증 2 의 GPT 불능 분기 · Phase 4.5 · `skills/fz-code/SKILL.md` 절차 8.5 · `skills/fz-gpt/SKILL.md` · `skills/fz-plan/SKILL.md` 에러 대응 표 |
| **fz:search-pattern** | 셋째 검증의 분석 스킬(`sc:sc-analyze`)이 없을 때 대신하는 새 컨텍스트 검증 1회 | `skills/fz-review/SKILL.md` 셋째 검증의 `fresh-context` 갈래 |

## 스폰 규칙

1. **직접 스폰**: L3 에이전트는 Agent() 도구로 직접 스폰한다
2. **Background 스폰**: review에서 fz Workflow 와 병렬로 background 실행
3. **결과 통합**: Lead가 L3 결과 수신 → Issue Tracker에 merge (fz 이슈와 동일 형식)
4. **조건부 스폰**: 아래 조건 충족 시에만 스폰
5. **모델·effort 명시**: L3 및 직접 Agent 스폰도 model 명시 의무 — 실질 분석·생산 관점은 `opus`, retrieval·breadth 성격은 `sonnet`, **effort 명시 필수** (미지정 시 모델은 부모 세션 모델 상속 · effort 는 메인 대화와 다른 모델이면 세션 값이 아니라 그 모델의 저장값 또는 기본값 — "use that model's saved effort level or its default, instead of the session's effort level" [verified: code.claude.com/docs/en/changelog, 2026-11-16]). Workflow 워커는 Lead 세션 effort 를 args 로 명시 전달한다(2026-10-19 — `modules/mode-gate.md` § effort). 값 선택: Opus 5.5 공식 기본은 `medium`(Opus 5 는 `high`), 탐색·retrieval 성격은 `low`/`medium`, demanding coding/agentic만 `xhigh` — ⛔ 이전 모델 값 재사용 말고 sweep 후 결정 [verified: platform.claude.com/docs/en/build-with-claude/effort]. 미측정 상태의 기본값은 현행(`xhigh`) 유지. Lead(`fable` alias → Claude Code v2.1.321 부터 Fable 5.2) 공식 출발점은 API 기본 `high`(Claude Code 모델 기본은 `medium`) [verified: platform.claude.com/docs/en/models/fable-5-2/whats-new-fable-5-2 + code.claude.com/docs/en/model-config] · 워커 Opus 5.5 공식 기본은 `medium`(Opus 5 는 `high`) [verified: platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5] — effort 이름이 모델마다 같은 사고량을 뜻하지 않으므로 승격 시 별도 sweep [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1].
6. **설치 확인**: 스폰 직전 Agent 도구가 광고하는 agentType 목록에 접두 포함 이름(`pr-review-toolkit:<이름>`)이 그대로 있는지 본다. 없으면 그 다리를 건너뛰고 보고에 `[L3 생략 — pr-review-toolkit 없음]` 한 줄을 남긴다. fz-guard AG 는 채택 표와 「fz 에이전트 — Lead 가 직접 띄우는 둘」 표의 접두 포함 이름만 허용한다(접두 없는 같은 이름 · 다른 접두 · 그 밖의 `fz:` 에이전트는 경고)

### 스폰 조건

| 에이전트 | 스폰 조건 | 비용 절감 |
|---------|----------|----------|
| pr-review-toolkit:silent-failure-hunter | diff에 try/catch, do-catch, Result, completion handler 포함 | 에러 처리 없으면 스킵 |
| pr-review-toolkit:type-design-analyzer | diff에 struct/class/enum 신규 정의 포함 | 기존 타입 수정만이면 스킵 |
| pr-review-toolkit:code-simplifier | review Phase 6 진입 시 (반복 개선 중) | Phase 5 통과 시 불필요 |

### 결과 형식

L3 에이전트 결과를 Issue Tracker에 통합할 때:

```markdown
| source | category | severity | description |
|--------|----------|----------|-------------|
| pr-review-toolkit:silent-failure-hunter | error_handling | Major | {설명} |
| pr-review-toolkit:type-design-analyzer | type_design | Minor | {설명} |
```

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-review | Phase 5 L3 에이전트 스폰 |

## 팀 피드백 프로토콜 (Workflow 모드)

L3 결과가 Workflow와 동시에 진행될 때의 피드백 흐름:

1. L3: `Agent(run_in_background=true)` 스폰
2. 결과 도착 시 Lead 수신
3. **다음 스테이지 invoke 전**: Lead가 `[L3 피드백]`을 **args/브리프에 주입**
   → 해당 렌즈 워커가 재분석 → severity 조정 + 연쇄 이슈 식별
4. **이미 진행 중인 invoke**: Lead가 직접 Issue Tracker에 merge (반환 후 통합)

⛔ **P2P 채널 없음**: Workflow 워커는 `SendMessage` 를 쓰지 않는 1-shot이다(OVERRIDE 블록 — P2P 통신 없음) — 실행 중 워커에게 끼어들 수 없다. 피드백 전달 단위는 **invoke 경계**다.

## 설계 원칙

- Progressive Disclosure Level 3 (review에서 필요 시 로드)
- L1 fz 에이전트 품질 > L3 → L1 우선, L3는 보강만
- 500줄 이하 유지
