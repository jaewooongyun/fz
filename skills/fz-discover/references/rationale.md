# fz-discover 근거 · 이력

> SKILL.md 에서 옮긴 근거 · 이력 · 사례 문단이다(B1 · 2026-11-01). 실행 규칙은 SKILL.md 에 남아 있다 — 이 파일은 왜 그 규칙인지를 설명한다.

## 루프 프리미티브 표지

> 루프 프리미티브: Tree Search (Adversarial Discovery) (H6, Inside the Scaffold)

## 사용 예시(옮김)

## 사용 시점

```bash
/fz-discover "이 기능을 어떻게 구현하면 좋을까?"         # 불명확한 요구사항 정제
/fz-discover "이 두 방법 중 어느게 나을까?"              # 트레이드오프 비교
/fz-discover "이렇게 사용해도 맞는지 확인해줘"          # 검증 요청
/fz-discover "이 방식에 놓치고 있는게 있을까?"          # 맹점 탐지
/fz-discover "A랑 B 차이점이 뭐야?"                    # 비교 질문
/fz-discover "이 설계 어떻게 생각해?"                    # 의견 요청
/fz-discover "팀원이 이런 우려를 제기했는데"              # 우려 기반 제약 발견
```

## TEAM 공식 사양 참조(실행 경로 아님)

- 참조: `guides/agent-team-guide.md` §8 (TEAM 공식 사양 — 패턴 canonical 문서용, pilot 기간 실행 경로 아님)

## TEAM → Workflow 전환(pilot)

> TEAM(TeamCreate+SendMessage) 모드를 네이티브 Workflow 결정적 스크립트로 대체한 pilot.
> Adversarial Constraint Discovery 패턴의 라운드 의미론(만들고-부수기)은 `workflows/discover-adversarial.js` 가 구현한다.

## TEAM 추론 품질 3원칙 보존 매핑

### TEAM 추론 품질 3원칙 보존 (guides/prompt-optimization.md §다양성 매핑)

| 원칙 | Workflow 보존 방식 |
|------|-------------------|
| Round 1 독립성 (sycophancy 방어) | 구조적 보장 — R1/렌즈 경로 생성 호출에 피어 데이터 미주입 (η-1 정신 계승, 정규식 검사 불필요화) |
| Task Brief 5요소 | agent() 프롬프트 = [역할][문제/컨텍스트][목표] + schema(=Deliverable) + OVERRIDE(=Constraints) |
| 합의/불합의 명시 | `conditions[].mutability`(locked/unlocked) + evidence·confidence로 표현 |

> Workflow 추가 보장: 실패 에이전트 = null 명시(silent fail 불가) · 출력 스키마 강제 · resume 캐시 · 종료 핸드셰이크 부재(자동 정리). Reflection Rate는 cross-check 포함 시만 해당(--deep GPT 후행 검증).
> 통신 기록: `discover-team.md` 미생성 — Workflow transcript(runId)가 대체. TEAM 일몰 상태는 `modules/promotion-ledger.md` § 결정 완료 — TEAM 메커니즘 일몰이 정본이다(⛔ 여기서 재서술하지 않는다).

## 옵션 나열 대신 판단 — 예시


```
BAD:  "방법 A: init 파라미터, 방법 B: Environment. 어떤 걸 선택하시겠어요?"
GOOD: "두 방법 모두 BandScope가 외부 Binding을 받는 것이므로 본질적으로 같습니다.
       기존 패턴(selectedBandItem, isVisible)은 init 파라미터를 사용하므로 일관성상 파라미터."
```

## 🔒/🔓 구분이 중요한 이유

   - 이 구분이 plan의 판단 자유도를 결정함
