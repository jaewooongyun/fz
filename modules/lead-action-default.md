# Lead Action Default Principle (31/32/33 통합)

> **Principle**: Lead default = action with proportional verification. Verification escalation은 명시적 risk signal에서만.
>
> 학술 근거 + 사례 history는 `guides/harness-engineering.md` 참조 (hot path가 아님).

## Trigger Matrix

| Manifestation | Trigger Signal | Lead Action |
|---------------|----------------|-------------|
| 31차 (Plan-before-Probe) | Plan 차원이 primitive/CLI flag/config key/value enum/env precondition에 의존 | constraint probe 선행 (`/fz-discover` Phase 1.5 또는 `fz-plan` Phase 0c) |
| 32차 (Probe Coverage) | probe 대상 enumeration 중 (a) 존재 (b) 권한·경계 (c) 결과 contract 3축 중 누락 | 3-axes sub-checklist 적용 |
| 33차 (Recommendation Default) | implementation-ready 시점 / verify approved or conditional-minor | **권고 default = implementation** (참조: `modules/fz-pipeline-proposal.md`) — 원칙: 충분한 정보가 있으면 행동(act when you have enough info) |
| 40차 (Simplified Request) | 사용자 신호 "그냥/가볍게/단순/빠르게/확인해줘/해도 돼?/맞아?/한 번 봐줘" 키워드 + 검토 산출물 존재 + **no `--deep`/`--team`** override | 절차(TEAM/Phase/게이트 시퀀스) 차단, simplified mode 적용 (예: `/fz-modernize light`) — 단 산출물이 전수/카운트/부정 주장이면 Coverage Gate 유지, **외부 피드백 수용/기각 판정이면 External Feedback Gate 유지** (light = 절차 생략이지 검증 생략 아님 → cross-validation.md §Coverage Gate·§External Feedback Gate) |
| 40차-MUST3 (GPT precedence) | `--seq` 단독은 sequential thinking 모드이지 simplified trigger 아님. `--deep --seq` 또는 `--team --seq` 조합 시 elaborate 유지 | `--seq` 단독 keyword 매칭 금지 — 컨텍스트 조건 필수 (GPT 검증 §5 MUST 3) |
| F5/F6 (Decision-Type+Boundary) *[candidate: 2 session evidence]* | 구조/경계 포크 결단 시 | (가) 코드사실로 좁혀지는 엔지니어링 판단: 확신 권고+근거+"이의 없으면 진행"(메뉴 금지). (나) 제품·디자인·팀 컨벤션 소유: AskUserQuestion. plan 분할=판단 입력≠경계 권위. (`modules/promotion-ledger.md` **L-14**) |
| MAST FM-2.2 (Fail to ask for clarification) | 요청 모호 / 동사 없음 / 명사+키워드만 / 범위 불명확 | AskUserQuestion 발동 의무 |
| Fable 5 (Genuine-Need Pause) *[intra-pipeline runtime]* | 스텝 진행 중 재확인 또는 promise-종료 pause를 고려하는 시점 | 3조건(파괴적·비가역 행동 / 실질 scope 변경 / 사용자만 줄 수 있는 입력) 중 하나면 pause, 아니면 승인된 outcome 위임 범위 내 진행. non-overridable allowlist는 본 기준으로 우회 불가 (하단 § Genuine-Need Pause) |

> 출처: MAST (NeurIPS 2025, arXiv 2503.13657 v3) — FM-2.2 "Fail to ask for clarification" = **6.80% 오류율** [verified: v3 §4 원문 "(FM-2.2, 6.80%)"]. 모호한 요청을 그대로 진행하면 trigger (MAST-Data 7개 프레임워크 / 1642 traces).

## 교훈 번호 정의 색인 (B0-K12)

> ⛔ **왜 있는가**: 플러그인 문서가 `N차` 를 인용하는데 정의가 **Trigger Matrix 5행(31·32·33·40)뿐**이었다.
> 실측(2026-09-22): 사용 **22종/128회** 중 정의 없음 **18종/91회** — 작성자 외에는 조회할 수 없었다.
> ⛔ **Trigger Matrix 를 용어집으로 만들지 않는다.** 저 표는 *패턴 → 행동* 이고, 이 절은 *번호 → 내용* 이다.
> ⛔ 내용은 **개인 메모리 기록에서 추출**했다 — 추측으로 채우지 않았다.
>
> 술어(재현용): 두 자리 + 뒤에 `원` 아님 + `차원`·`레버`·`resume`·`재시도` 줄 제외.
> `1차 레버`·`5차원 복잡도`·`재시도 2차` 는 교훈 참조가 **아니다** — 첫 측정이 이것들을 긁어 184회로 부풀었다.

| 번호 | 내용 (한 줄) | 근거 |
|---|---|---|
| 10차 | Fable 5 사용 재개 + B안 가동, 재배선은 보류 | 세션 기록 2026-07-05 |
| 11차 | 재배선 완료 — 생산은 `code-pair` 워커 전담, Lead 는 적용·검증 | 세션 기록 2026-07-06 (v4.18.0) |
| 13차 | thought-terminator 방어 — 결론을 닫는 문구로 탐색을 멈추지 않는다 | `[[feedback_thought_terminator_defense]]` |
| 15차 | 싱글톤 future safety — 현재 호출 1곳이라는 이유로 안전 판정 금지 | 세션 기록 |
| 16차 | Origin 함정 + 실측 누락 — 출처를 확인하지 않고 수치를 주장 | 세션 기록 |
| 17차 | fz 생태계 메타 갭 — 스킬이 자기 생태계를 점검하는 자리가 없다 | 세션 기록 |
| 18차 | Scope Inflation 방어 — 분석 범위가 요청을 넘어 부푼다 | 세션 기록 (v4 ISSUE-016) |
| 19차 | self-review blind spot family(16·17·19) — 분석은 맞는데 **적용 범위** 판단이 틀린다 | 세션 기록 |
| 23차 | GPT 단독 발견 재현 — cross-model 이 마지막 안전망 | 세션 기록 |
| 29차 | GPT CLI(`codex exec`) stdin hang — `< /dev/null` + `--skip-git-repo-check` 필요 | `modules/fz-gpt-bash-hygiene.md` §2 |
| 30차 | `[projects.<path>] trust_level = "trusted"` 없으면 profile sandbox 무효 | `modules/fz-gpt-bash-hygiene.md` §5 |
| 34차 | 리팩토링 옵션을 **첫 라운드에** 시각화한다 | 세션 기록 |
| 35차 | Calibrate-from-Real — 상상한 계획이 아니라 실물에서 보정한다 | 세션 기록 |
| 36차 | 팀 공유 영역·훅 우회는 **명시 승인** 후에만 | 세션 기록 |
| 38차 | SwiftUI `_ConditionalContent` re-mount — 정적 검증의 한계, 실기기가 안전망 | `[[feedback_swiftui_conditional_remount]]` |
| 41차 | Reuse-First — 새로 만들기 전에 기존 인프라를 찾는다 | `[[feedback_reuse_first_default]]` |
| 42차 | 디자인 frame **실측** — figma 수치를 눈대중으로 옮기지 않는다 | `[[feedback_design_spec_empirical_comparison]]` |
| 45차 | 템플릿 권위 편향 — 형제·템플릿이 근거를 대신하지 않는다 | `[[feedback_template_authority_bias]]` |

⛔ **새 번호를 인용하면 이 표에 한 줄을 함께 넣는다.** 넣지 않으면 그 인용은 작성자 외에는 조회 불가다.

## Genuine-Need Pause (Fable 5 checkpoint)

> 대상 = **intra-pipeline runtime pause**만 (스텝 진행 중 재확인 · promise-종료 시점). 아래 allowlist의 명시 승인 게이트는 별개 규율.

파이프라인 실행 중 turn을 멈추고 사용자 재확인을 구하는 것은 아래 3조건 중 하나에 해당할 때만:

1. **파괴적·비가역 행동** — 되돌릴 수 없는 상태 변경
2. **실질 scope 변경** — 승인된 outcome 범위를 벗어남
3. **사용자만 줄 수 있는 입력** — 제품·디자인·팀 컨벤션 소유 / 코드 사실로 좁혀지지 않는 결단

그 외에는 승인된 outcome 위임 범위 내에서 진행한다 (act when you have enough info). 출처: 공식 Prompting Claude Fable 5 checkpoint 스니펫 — "Pause only when [the decision] genuinely requires the user; otherwise proceed." (스니펫 원문·채택 근거: `guides/model-guide.md` § 프롬프트 패턴 / 채택 현황).

### non-overridable allowlist (본 기준으로 우회 불가)

아래 명시 승인 게이트는 genuine-need 판정과 무관하게 항상 사용자 승인을 요한다 — 본 기준을 근거로 생략·우회 금지:

- **fz Phase 4 파이프라인 착수 승인**
- **fz-plan Gate 2 사용자 승인**
- **팀 공유 영역 / 보호 파일 커밋**
- **fz-modernize 적용 합의**

## 3 Examples (inline)

- **31차**: 사용자 "v3 작성하지 말고 implementation 진입" → constraint probe 안 했으면 probe 선행, 했으면 implementation
- **32차**: T1-D2 ISSUE-001 (allowed-tools) — GPT 단독 발견. 3축 중 "권한·경계" 축 누락이 원인
- **33차**: round 4 (review→plan→review→...) 누적 시 default = stop & implement (사용자 명시 risk signal 없을 시)

## Lesson Intake (이 원칙에 새 manifestation 추가 시)

> 참조: `modules/memory-guide.md` § Lesson Intake Decision Tree. 동일 failure mode만 manifestation 추가. 다른 mode는 별도 principle 후보.
