# 거버넌스 프레임워크 (Governance)

> fz-* 생태계의 변경 통제, 품질 게이트, 긴급 정지 정책.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | kill-switch 판단 |
| /fz-manage | 거버넌스 프레임워크 전체 참조 |

## Kill-Switch

파이프라인 실행 중 긴급 정지가 필요한 상황에서의 행동 규칙.

### 긴급 정지 조건

| 조건 | 판단 기준 | 행동 |
|------|----------|------|
| 무한 루프 감지 | 동일 Gate 3회 연속 실패 | LOOP 에스컬레이션 래더 L4 → 사용자 에스컬레이션 |
| 팀 교착 | 에이전트 간 3라운드 내 합의 불가 | Lead가 최종 판단 or 사용자 에스컬레이션 |
| 리소스 초과 | 에이전트 5개 이상 동시 실행 | 추가 스폰 차단 + 기존 작업 완료 대기 |
| 모델 비용 상한 초과 | fable 에이전트 동시 2개 이상 (Lead 세션 제외) 또는 opus 에이전트 동시 4개 이상 | 추가 스폰 차단 |
| 의도 이탈 | 실행 결과가 원래 요청과 무관 | 파이프라인 중단 + 사용자 확인 |

> 모델 비용 상한 근거: 최대 동시 = Lead(fable ≈ opus 2) + opus 3 ≈ **opus 5 equivalent**. 단가: sonnet $3/$15 · opus $5/$25 · fable $10/$50 (per MTok). fable 1 ≈ opus 2 비용 등가. canonical `guides/fable-model-guide.md` §5.
> **rate-limit 폴백 계약**: 병렬 opus 스폰이 상한 미달로 실패/429 시 순차화 재시도 1회 → 재실패 시 `mode:'fallback'` 반환. 구현은 workflows 코드(plan-collaborative stage2 · peer-review stage1의 병렬 블록).

### ⛔ 사각지대 — advisor 도구는 위 상한이 **전혀 보지 못한다**

`advisorModel`이 설정된 세션에서 advisor는 **스폰된 에이전트가 아니라 서버사이드 tool call**이다. 따라서 이 문서의 모든 상한 밖에 있다.

| 방어선 | advisor를 보는가 | 이유 |
|--------|-----------------|------|
| 위 kill-switch (에이전트 5+ 동시 · opus 4+ 동시) | ❌ | 에이전트가 아니라 tool call |
| `scripts/lint-model-explicit.sh` · Workflow 런타임 캡(동시 16·총 1000) | ❌ | 대상 아님 |
| **트랜스크립트 계측** (`usage.server_tool_use`) | ❌ | **필드 자체가 없다** |
| `/usage` (대화형) | ✅ | **유일하게 작동하는 관측 경로** |

**실측 근거 (2026-08-08)** — 이 3중 사각지대는 추정이 아니라 확인된 사실이다:
- 세션 트랜스크립트 3.1MB 전수 파싱: advisor 호출 6회 발생했으나 `usage.server_tool_use` **289개 레코드 전수가 `{"web_fetch_requests":0,"web_search_requests":0}`뿐**. `advisor_*tokens`·`advisor_usage` 류 필드 grep **0건**. 워커 트랜스크립트(`agent-*.jsonl`)에서도 동일 재현.
- 1-agent 프로브(`wf_e7136199-140`, `model:'opus'`): **Workflow `agent()`로 스폰된 opus 워커가 세션 `advisorModel`을 상속해 실제 호출에 성공**했다 — `{"advisor_tool_available":true,"call_succeeded":true}`.

⛔ **따라서 `opus 동시 ≤3` 비용 envelope은 advisor 지출을 전혀 bound하지 않는다.** 워커 3개가 각자 advisor를 호출할 수 있고, 공식 문서상 *"There is no setting to cap or force advisor calls"* 이며 *"the advisor model's own read of the conversation is **not cached**"* 다. 사후 추적 수단은 `/usage`를 사람이 보는 것뿐이다.

**운용 규칙**
1. advisor 사용량을 **늘리려는 변경 전**에는 `/usage`로 baseline을 먼저 기록한다 (사후 복원 불가).
2. ad-hoc Workflow 프로브 등 일회성 실행은 advisor 호출을 유도하는 지시를 넣지 않는다 — 계측되지 않는 지출이 된다.
3. ⚠️ 격리 워커의 advisor는 **워커 자신의 컨텍스트만** 읽는다(메인 세션 트랜스크립트 아님) → 회당 비용은 메인 세션보다 작다. 리스크는 회당 비용이 아니라 **호출 수 × 무계측**이다.
4. 끄려면 `advisorModel` **unset** 또는 `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`. ⛔ 실험 게이트류 env var를 `"0"`으로 두는 것은 끄는 게 아니다 — 공식: *"any non-empty value **including `0`** turns the behavior on"*.

### Kill-Switch 실행 절차

1. 조건 감지 → 현재 Step 완료 대기 (진행 중 작업 보호)
2. 팀 모드 시: 전체 에이전트에 `shutdown_request` 전송
3. 사용자에게 상황 보고 + 선택지 제시 (재시도/스킵/중단)
4. 중단 선택 시: TeamDelete + 부분 산출물 보존

## Hook 최소 강제 권고

사용자 환경 `settings.json`에 빌드 검증 Hook 설정을 권장한다. "빼먹을 수 없는" 최소 게이트:
- PostToolUse(Write/Edit) → `xcodebuild build` 자동 트리거
- PreToolUse(Bash: git push) → 커밋 전 검증 확인
> Hook은 fz 파일 밖이므로 "권고"로만 제시. 참고: Carlini "환경 설계 > 직접 감독"

> **결정론적 안전 강제 원칙** (서베이 안전 테마, 2026-07 추가 — fz 트리거 ID T8과 무관): "거버넌스 제약(누가 인가·무엇이 제한·누구 지시 우선)은 결정론적 런타임 변수이므로 LLM이 아니라 실행 훅이 강제해야 한다." [외부: harness-paper §4-H, Harness-MU arXiv 2606.21856 — 원 논문 미대조]. fz 고유 ⛔ 규칙(git 사용자 관리·팀 스킬 필수 등)은 현재 프롬프트 soft-enforcement에 의존한다. 신뢰성-필수 제약의 결정론적 훅 승격은 `settings.json` 소유자(사용자) 결정 사항이며, 훅 템플릿은 `examples/hooks.json.example` 참조. ⛔ Claude는 훅 설치·설정 변경을 명시 합의 없이 지시·실행하지 않는다(팀 공유 영역 규율).

## 변경 통제

### 변경 영향 등급

| 등급 | 대상 | 예시 | 검증 |
|------|------|------|------|
| L1 (경미) | 단일 스킬 본문 | 오타 수정, 문구 개선 | 자체 검증 |
| L2 (중간) | YAML frontmatter, 에이전트 | description 변경, 도구 추가 | `/fz-skill eval` |
| L3 (중대) | 공유 모듈, 가이드, 템플릿 | team-core.md 규칙 변경 | `/fz-manage check` + 영향 스킬 확인 |

### L3 변경 시 필수 절차

1. 영향 범위 분석: `Grep("{모듈명}", "./")` → 참조 파일 목록
2. 변경 전 상태 기록 (ASD 폴더 활성 시)
3. 변경 실행
4. `/fz-manage check` → 전체 건강 체크
5. 영향받는 스킬 개별 확인

## 품질 게이트

### 스킬 최소 기준

| 항목 | 기준 | 근거 |
|------|------|------|
| YAML 필수 필드 | name, description, allowed-tools, provides, needs | Progressive Disclosure L1 |
| Description 4요소 | what + when + when-not + 한영키워드 | 트리거 정확도 |
| 크기 제한 | ≤500줄 | Progressive Disclosure L2 |
| Boundaries | Will/Will Not + 대안 | 범위 명확화 |
| 에러 대응 | 테이블 존재 | 자율 복구 |

### Utility 스킬 예외

Query/Utility 스킬(fz-commit, fz-pr, fz-new-file 등)은 Phase/Gate/Few-shot 면제.
단, Description 4요소와 Boundaries는 필수.

## Truth-of-Source 정책

생태계 내 동일 정보가 여러 파일에 존재할 때의 우선순위:

| 정보 | Truth-of-Source | 동기화 대상 |
|------|----------------|------------|
| 팀 구성 (에이전트 목록) | 스킬 YAML `team-agents` | team-registry.md, patterns/*.md |
| 에이전트 도구 | 에이전트 YAML `tools` | 본문 설명 |
| 파이프라인 정의 | modules/pipelines.md | fz SKILL.md 인라인 |
| 평가 기준 | guides/skill-testing.md | fz-skill eval, fz-manage benchmark |

동기화 불일치 발견 시: truth-of-source를 기준으로 나머지를 수정.

## 모듈 분리 기준

스킬/모듈이 아래 조건을 만족하면 분리를 검토한다.

| 기준 | 임계값 | 분리 방법 |
|------|--------|----------|
| 크기 | 500줄 초과 | 독립 주제를 `modules/`로 추출 |
| 참조 빈도 | 3개+ 스킬에서 참조 | 공유 모듈로 승격 |
| 주제 독립성 | 스킬 본문과 다른 관심사 | 별도 모듈로 분리 |

### 분리 우선순위

1. **크기 초과 + 참조 빈도 높음** → 즉시 분리 (가장 높은 ROI)
2. **크기 초과 + 참조 빈도 낮음** → 스킬 내 섹션 축소 우선 시도
3. **크기 미초과 + 참조 빈도 높음** → 공유 모듈로 승격 검토
4. **크기 미초과 + 참조 빈도 낮음** → 현상 유지

## 설계 원칙

- Progressive Disclosure Level 3 (거버넌스 판단 시에만 로드)
- 500줄 이하 유지
