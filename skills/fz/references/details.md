# fz 상세 — 예시 · 카탈로그 · 보고 형식

> SKILL.md 에서 옮긴 비지시 블록이다(이력 · 사용 예시 · 모듈 카탈로그 · 자동 포함 정보 · 보고 형식 · 긴 근거). 실행 규칙(Phase 0~5 · Gate · 에러 대응 · Boundaries)은 SKILL.md 에 남아 있다 — 이 파일은 그 자리의 한 줄 포인터가 가리킬 때 연다.

## 이력

- 개별 스킬 팀 강화 — Wave 4 전환 완료, P2P SendMessage 없음(plan/code/review/search/discover/peer-review 모두 `workflows/*.js` 결정적 Workflow · P2P 시절 통신 패턴: `references/rationale.md` § 스킬별 통신 패턴)

## 사용 시점 예시

```bash
/fz "OrderDetail 크래시 버그 찾아줘"         # → bug-hunt (SOLO)
/fz "새 기능 계획 세워줘" --team               # → plan-to-code (TEAM)
/fz "코드 리뷰하고 커밋해줘"                   # → review-to-ship (TEAM)
/fz "기능 구현하고 리뷰" --deep                # → code-to-review (TEAM+deep)
/fz "타임아웃 30초로 변경" --solo              # → quick-fix (강제 SOLO)
/fz "이걸 어떻게 구현하면 좋을까?"              # → discover (SOLO)
/fz "모듈 12개 용어 통일" --batch              # → BATCH (worktree 병렬)
/fz "빌드 실패 반복" --loop                    # → LOOP (자동 반복)
/fz "스킬 트리거 최적화해줘"                    # → skill-optimize (SOLO)
/fz "드리프트 체크해줘"                        # → drift-check (SOLO, fz-gpt drift)
/fz "독립 플랜 만들어줘"                       # → plan-parallel (SOLO, fz-gpt independent-plan)
/fz "전체 봐줘"                               # → 짧은 요청(10글자 미만) → AskUserQuestion 먼저
/fz "안됨"                                    # → 짧은 요청(10글자 미만) → AskUserQuestion 먼저
```

## 모듈 참조

| 모듈 | 용도 |
|------|------|
| modules/complexity.md | 5차원 복잡도 → 모드 결정 |
| modules/team-registry.md | 에이전트 + 모델 자동 결정 |
| modules/cross-validation.md | 검증 게이트 자동 삽입 |
| modules/context-artifacts.md | 티켓 폴더 기반 compact recovery + 산출물 전달 |
| modules/execution-modes.md | BATCH/LOOP/SIMPLIFY 실행 모드 |
| modules/governance.md | kill-switch |
| modules/pipelines.md | 19개 사전 정의 파이프라인 (트리거+체인+게이트+TEAM) |
| modules/memory-guide.md | L1 auto memory 관리 정책 + 태깅 규칙 |
| modules/plugin-refs.md | SwiftUI + Concurrency 플러그인 참조 가이드 |
| modules/intent-registry.md | Phase 1 이 읽는 트리거 소스 — 스킬·파이프라인 트리거 + 구어체 보강 + Confidence 판정 |
| modules/lead-action-default.md | 교훈 사전 로드 Trigger Matrix (Phase 0 Step 4) |
| modules/fz-pipeline-proposal.md | 파이프라인 시각화 + AskUserQuestion 형식 (Phase 4) |
| modules/uncertainty-verification.md | Default-Deny — 미검증 주장 차단 (Phase 5 Brief) |
| modules/lead-reasoning.md | Speculation-to-Fact Fallacy 방어 (Phase 5 Brief) |
| modules/system-reminders.md | T6/T7 트리거 리마인더 (Phase 5 Brief) |

## Verification Discipline Brief (모든 agent() spawn에 자동 포함)

Workflow agent() spawn 프롬프트(OVERRIDE 블록 일부)에 규약 ①②④가 자동 포함된다 (2026-07-09 D2 정합 — 6개 워크플로 전수):

1. 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
2. 외부 모델 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
3. T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 — **OVERRIDE 미포함(격리 워커의 파일접근 제한과 상충) → Lead 소관**
4. 진행/완료 보고 전 각 주장을 이 세션의 도구 결과와 대조 — 근거 지목 불가 항목은 `[미검증]` 명시

참조: `modules/uncertainty-verification.md` (Default-Deny), `modules/system-reminders.md` (T6/T7), `modules/lead-reasoning.md §1.5` (Speculation-to-Fact Fallacy).

## 스킬별 통신 패턴

스킬별 Workflow 스크립트 — fz-discover `workflows/discover-adversarial.js` · fz-plan `workflows/plan-lean2.js`(롤백 `workflows/plan-collaborative.js`) · fz-code `workflows/code-pair.js` · fz-review `workflows/review-live.js` · fz-search --deep `workflows/search-cross-verify.js` · fz-fix(복잡) `workflows/code-pair.js` mode=light (P2P 시절 통신 패턴 이력: `references/rationale.md` § 스킬별 통신 패턴)

### 개별 스킬 TEAM 모드 (핵심 패턴)

> 각 스킬 SKILL.md의 "팀 에이전트 모드" 섹션 참조.

## 단계 완료 보고 (각 단계)

사용자 보고에는 결과와 다음 행동만 적는다 — 실행 주체 · 모델 · 세션 · 하네스 지표는 작업 폴더 기록(`run_metrics.py` · 산출물 파일)으로 보낸다(F-744).

```markdown
**Step N 완료**: /fz-{skill}
**결과**: {요약}
**다음**: /fz-{next-skill} (Step N+1)
```

## 파이프라인 완료 보고

Phase 4 시각화와 동일 형식 + 각 스텝의 상태(OK/FAIL) + 다음 행동 제안.

## 세대 교체 sweep 행

⛔ **모델 세대가 바뀐 뒤 첫 Workflow 실행이면** `scripts/fz_wf_metrics.py --sweep-row --wf {runId}` 로 저장소 밖 로그 `${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md` §5.8 ⑥ 행을 만든다(규약: `experiment-log.md` 머리 문단) — 공식 문서가 세대 간 effort 이월을 금지하고 fresh sweep 을 요구한다. 손으로 옮기지 않는다(이 표가 두 달 비어 있던 원인이 **재는 주체 부재**였다)
