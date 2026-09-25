# 거버넌스 프레임워크 (Governance)

> fz-* 생태계의 변경 통제, 품질 게이트, 긴급 정지 정책.

## 목차

- [참조 스킬](#참조-스킬)
- [Kill-Switch](#kill-switch)
- [자율 모드 (S18)](#자율-모드-s18)
- [적용 경로 (D2)](#적용-경로-d2)
- [Hook 최소 강제 권고](#hook-최소-강제-권고)
- [변경 통제](#변경-통제)
- [품질 게이트](#품질-게이트)
- [Truth-of-Source 정책](#truth-of-source-정책)
- [모듈 분리 기준](#모듈-분리-기준)
- [설계 원칙](#설계-원칙)

---

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | kill-switch 판단 |
| /fz-manage | 거버넌스 프레임워크 전체 참조 |

## Kill-Switch

파이프라인 실행 중 긴급 정지가 필요한 상황에서의 행동 규칙.

### 게이트 원장 이탈 (`modules/gates.md`)

완료 게이트가 활성인 상태에서 정당하게 빠져나오는 경로는 **둘뿐이고 둘 다 흔적이 남는다.**

| 경로 | 범위 | 흔적 |
|------|------|------|
| `ABANDON: <id> <비어 있지 않은 이유>` | 게이트 1개 | 원장에 보존 + 최종 보고에 표면화 |
| `FZ_GATES_OFF=1` | 세션 전체 | 환경변수 (⛔ 원장의 `STATE:`는 불변 — 세션 bypass가 후속 세션까지 지속되면 안 된다) |

⛔ **진행 없는 블록 N회 후 자동 해제를 두지 않는다.** 그것은 판정 fail-open이며 위 두 경로 밖의 세 번째 우회로다. 우회는 사용자의 명시적 행위여야 한다.

### 긴급 정지 조건

| 조건 | 판단 기준 | 행동 |
|------|----------|------|
| 무한 루프 감지 | 동일 Gate 3회 연속 실패 | LOOP 에스컬레이션 래더 L4 → 사용자 에스컬레이션 |
| 팀 교착 | 에이전트 간 3라운드 내 합의 불가 | Lead가 최종 판단 or 사용자 에스컬레이션 |
| 리소스 초과 | 에이전트 5개 이상 동시 실행 | 추가 스폰 차단 + 기존 작업 완료 대기 |
| 모델 비용 상한 초과 | fable 에이전트 동시 2개 이상 (Lead 세션 제외) 또는 opus 에이전트 동시 4개 이상 | 추가 스폰 차단 |
| 의도 이탈 | 실행 결과가 원래 요청과 무관 | 파이프라인 중단 + 사용자 확인 |

> 모델 비용 상한 근거: **정본 = `guides/model-guide.md` §5** — 동시 상한 수치(opus ≤3 · fable 1 · 총 ≤4)와 그 근거를 모두 그곳에서 읽는다. ⚠️ 2026-09-06 정정 — 이전에 여기 적혀 있던 "fable 1 ≈ opus 2 비용 등가 → opus 5 equivalent" 산식은 정본이 폐기했다(Fable 5.1 캐시 읽기 $0.25 < Opus 5 $0.50, 남는 차이는 출력·캐시쓰기 단가 2배 + 지연 +49%). 값을 여기 복사하지 않는다. 워커가 Opus 5.5($4/$20·캐시 읽기 $0.20)로 바뀐 뒤의 재산정은 미실시(선택 과제 — `guides/model-guide.md` §5 가격 비교).
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
5. 워크플로 실행 뒤 `python3 "${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py" --wf <runId>` 의 advisor 카운트를 확인하고, **advisor > 0 이면 결과 보고에 적는다**. 워커 쪽을 끄는 네이티브 수단은 없다 — 공식: *"Subagents inherit the configured advisor and apply the same pairing check against their own model"*(code.claude.com/docs/en/advisor, 2026-09-22 대조). `advisorModel: "fable"` 이면 opus·sonnet 워커가 페어링을 통과해 상속하므로, 억제는 각 워크플로 `OVERRIDE` 상수의 "advisor 도 호출하지 않는다" 문구뿐이다(`scripts/check_wf_advisor_ban.py` 는 문구 **누락**만 막는다). 효과 관측(2026-09-25, `fz_wf_metrics.py` 로 워크플로 125회 전수): 문구가 실린 실행 20회·워커 87개 → advisor **0회** / 문구 없는 실행 102회(워커 기록 없는 3회는 측정 불가로 제외)·워커 519개 → advisor 403회(64회 실행, 63%). 비교한 것은 호출 수뿐이다 — 완료 시간·결과 품질은 비교하지 않았다. ⚠️ 무작위 대조가 아니다 — 워크플로 종류·advisor 설정 시점이 섞여 있다. 문구 실린 실행에서 advisor 가 다시 보이면 이 규칙의 보고 대상이다.

### Kill-Switch 실행 절차

⛔ **`TeamCreate`/`TeamDelete`/`shutdown_request`는 v2.1.178부터 존재하지 않는다** (`guides/agent-team-guide.md` §3 실측). 이전 판이 이 도구들을 비상 절차로 지시하고 있었다 — **비상 경로가 부재 도구에 의존**하던 상태다(2026-08-09 격리).

1. 조건 감지 → 현재 Step 완료 대기 (진행 중 작업 보호)
2. **Workflow 모드**: 실행 중 스크립트는 Lead가 중단 신호를 보낼 채널이 없다(1-shot 스테이지) → **현재 스테이지 완주를 기다리고 반환값을 받은 뒤 다음 invoke를 하지 않는다**. 강제 종료가 필요하면 `TaskStop`(harness 도구)이 유일 수단이다
3. 사용자에게 상황 보고 + 선택지 제시 (재시도/스킵/중단)
4. 중단 선택 시: **부분 산출물 보존**(티켓 폴더 기록 확인) + 다음 invoke 차단. 정리할 팀 리소스는 없다 — Workflow는 종료 핸드셰이크가 없고 자동 정리된다
   > ✅ **폴백 분기 확정 (2026-08-09)**: 중단이 아니라 *복구*를 시도할 때는 `guides/skill-authoring.md` §12 **실패 복구 사다리**(L1 분할 → L2 입력 수정 → L3 `resume` → L4 사용자 에스컬레이션)를 따른다. Kill-Switch는 **L4에서 사용자가 "중단"을 선택한 경우**의 절차다

## 자율 모드 (S18)

`FZ_AUTONOMY` 로 세션 모드를 받는다. 판정기는 `scripts/autonomy_decide.py` 다.

⛔ **플래그가 아니라 환경변수인 이유**: 모드는 **워커까지 전파돼야** 한다. 플래그는 `/fz` 호출 1회에만 붙고 하위 실행에 전달되지 않는다. kill-switch(`FZ_GATES_OFF`)가 이미 같은 이유로 환경변수다.

| 축 | 값 | 이유 |
|---|---|---|
| 아는 값 | `autonomous` · `interactive` | 그 외는 전부 미지로 다룬다 |
| 기본값(미설정·빈 값) | **`interactive`** | ⛔ 자율이 기본이면 **설정 누락이 승인을 없앤다** |
| 미지 값 | **묻는다** (fail-closed) | ⛔ 오타 하나가 승인을 없애지 않도록 |
| 전파 | 세션 전체 · 워커 상속 | 원장 `STATE:` 는 건드리지 않는다 (kill-switch 와 동일) |

판정은 세 값이다 — `PROCEED`(자동 진행) · `ASK`(묻는다) · `BLOCK`(모드 무관 차단).

⛔ **자율 모드가 금지 행동을 풀지 않는다.** `commit`·`push`·`external_send`·`delete`·`pr_create`·`pr_edit` 는 모드와 무관하게 `BLOCK` 이다 — 이름으로 고른 집합이 아니라 **되돌리는 비용**으로 고른 집합이다. 외부로 나간 것과 지운 것은 돌아오지 않는다.

⛔ *"자율이면 진행"* 만으로는 판정이 안 된다. 자율은 **범위 내 + 가역**까지만이다. 범위 밖이거나 비가역이면 자율에서도 묻는다 — 원래 요청 범위 안인지, 기존 승인과 충돌하는지는 모드가 답해주지 않는다.

복합 작업은 **가장 보수적인 판정이 이긴다**(`BLOCK` > `ASK` > `PROCEED`). 평균도 다수결도 아니다 — 한 부분이 금지면 묶음 전체가 금지다.

### 적용 경로 (D2)

⛔ **정책은 선언만으로 적용되지 않는다.** 실측(2026-09-22): `FZ_AUTONOMY` 보유 파일 **2개**(이 문서 + 판정기)이고 스킬·워크플로 **0건**이었다. 같은 성격의 kill-switch(`FZ_GATES_OFF`)는 **7파일**에 배선돼 있다 — 그 차이가 *적용되는 정책*과 *적어둔 정책*의 차이다.

| 진입 경로 | 적용 지점 | 상태 |
|---|---|---|
| `/fz` 오케스트레이터 | **Phase 4** 사용자 확인 — 모드를 먼저 판정하고, 범위 내 가역만 자동 진행 | **배선됨** |
| 개별 스킬 직접 진입 (`/fz-review` 등) | 각 스킬의 승인 지점 | ⛔ **미배선** — 아래 참조 |
| 워커 실행 (Workflow agent) | `agent()` OVERRIDE 프롬프트 | ⛔ **미배선** — 환경변수는 모델 호출에 전달되지 않는다. 주입이 필요하다 |

⛔ **개별 스킬 경로의 배선은 열려 있다.** 승인 지점을 세려면 `AskUserQuestion` 호출부를 분류해야 하는데, 실측 **90건/31파일** 중 키워드 분류로 판정된 것이 37건뿐이다(unknown 42 · 복합 11). ⇒ 분류는 **기계로 닫히지 않는다**. 사람이 지점을 지목하기 전에는 이 경로를 자동 적용 대상으로 선언하지 않는다 — 잘못 적용하면 승인이 사라진다.

⛔ **워커 경로는 환경변수로 닿지 않는다.** `agent()` 는 모델 호출이고 프로세스가 아니다. 적용하려면 8개 워크플로의 OVERRIDE 블록에 모드를 실어야 하며, 그 전까지 워커는 **대화형으로 취급**한다(기본값이 그렇다 — fail-closed).

⚠️ **강제 지점의 한계**: 이 판정기는 도구 호출을 **가로채지 못한다**. 플러그인에 PreToolUse 표면이 없고(`scripts/setup-hooks.sh` 는 git 훅만 등록한다), 따라서 강제는 절차적이다 — Lead 가 금지 행동 전에 판정기를 부르는 규율에 의존한다. 기계 강제가 필요하면 호스트 쪽 훅 설정이 선행돼야 한다.

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
| L3 (중대) | 공유 모듈, 가이드, 템플릿 | gates.md 규칙 변경 | `/fz-manage check` + 영향 스킬 확인 |

### L3 변경 시 필수 절차

1. 영향 범위 분석: `Grep("{모듈명}", "./")` → 참조 파일 목록
2. 변경 전 상태 기록 (티켓 폴더(WORK_DIR) 활성 시)
3. 변경 실행
4. `/fz-manage check` → 전체 건강 체크
5. 영향받는 스킬 개별 확인

## 품질 게이트

### 스킬 최소 기준

| 항목 | 기준 | 근거 |
|------|------|------|
| YAML 필수 필드 (**정본** — 2층) | **L1 Claude Code 공식**(최상위): `name` · `description` · `allowed-tools` · `user-invocable` / **L2 fz 정책**(`metadata:` 하위): `metadata.provides` · `metadata.needs` | L1은 Progressive Disclosure L1, L2는 `/fz` 동적 파이프라인(`skills/fz/SKILL.md` §3.2)이 실제 소비 |
| Description 4요소 | what + when + when-not + 한영키워드 | 트리거 정확도 |
| 크기 제한 | ≤500줄 | Progressive Disclosure L2 |
| Boundaries | Will/Will Not + 대안 | 범위 명확화 |
| 에러 대응 | 테이블 존재 | 자율 복구 |

### Utility 스킬 예외

Query/Utility 스킬(fz-commit, fz-pr, fz-new-file 등)은 Phase/Gate/Few-shot 면제.
단, Description 4요소와 Boundaries는 필수.

### Agent-Payload 스킬 범주 (2026-08-09 신설)

**정의**: `user-invocable: false` + 에이전트 frontmatter `skills:` 로 **사전주입**되는 스킬. 현재 `arch-critic`(review-arch) · `code-auditor`(review-quality).

⛔ **면제가 아니라 대체 게이트다.** 이 스킬은 사용자가 선택하지 않으므로(선택 시점에 description·Boundaries가 노출되지 않는다) Utility 예외와 성격이 다르다. 범주가 없어 두 스킬이 6개 게이트를 **영구 미충족**했고, 2026-06-28 감사의 T9c(에러 대응표)가 1년 가까이 미해결로 남은 근본 원인이다.

| 항목 | 판정 |
|---|---|
| Phase · Gate · 에러 대응표 · 테스트 케이스 · description when-not · 한영 키워드 | **면제** — 선택 시점에 노출되지 않는다 |
| **(a) 관점 커버리지** | 선언한 관점 수 = 본문 관점 섹션 수 |
| **(b) 출력 필드 정합** | ⛔ **소비 스키마 집합 전체**와 정합. 단수 아님 — `arch-critic`은 `review-live.js`(`ReviewFindingsSchema.detail`) + `peer-review.js`(`PeerReviewSchema.description`) **2 계약**을 동시 지원한다 |
| **(c) 사전주입 실재** | 대상 에이전트 frontmatter `skills:` 에 실제 선언 |

- (a)(c)는 binary → `scripts/lint_contracts.py` 후속 항목
- ⚠️ **(b)는 OQ9(리뷰 이슈 3중 계약) 미해소 시 기준 확정 불가** → 그때까지 **관찰 기록**, 게이트는 (a)(c)만

> 근거: 2026-08-09 플러그인 자기 감사 F-6·F-17 (⛔ 개인 아티팩트 경로는 팀 코드에 남기지 않는다 — pre-commit 훅이 차단)

## Truth-of-Source 정책

생태계 내 동일 정보가 여러 파일에 존재할 때의 우선순위:

| 정보 | Truth-of-Source | 동기화 대상 |
|------|----------------|------------|
| **팀 구성 (에이전트 목록)** | **`workflows/*.js`의 `agentType` 인자** | team-registry.md, patterns/*.md — ⛔ 스킬 YAML `team-agents`는 **2026-08-09 제거**(런타임 효과 0이었다) |
| **모델 배정** | **`workflows/*.js`의 `opts.model`** | agents/*.md(기본값 표기만), team-registry.md `promoted` 열. 감시 = `scripts/lint-model-explicit.sh` · ⛔ 스킬 YAML `model-strategy`는 **제거** |
| **opus 동시 상한** | **`guides/model-guide.md` §5** | governance.md kill-switch 행, agent-team-guide.md, skill-authoring.md §12 |
| **YAML 필수 필드** | **본 문서 § 스킬 최소 기준** (L1 공식 4 + L2 fz 정책 2) | fz-manage check #1, skill-troubleshooting.md #1, templates/skill-template.md |
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
