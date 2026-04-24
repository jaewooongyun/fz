# Scope Challenge — Phase 3 Codex 이슈 분류 + Lead 독립 판정

> 참조: `skills/fz-plan/SKILL.md` Phase 3, `skills/fz-codex/SKILL.md` verify 응답, `schemas/codex_review_schema.json`
> 원본 근거: ASD-1136 plan iteration 4회 (26시간, 40% 롤백) — 과잉 확장 방지
> **1단계 깊이 원칙**: 본 모듈은 자체 완결. 다른 `modules/` 재참조 금지 (skill-authoring §3)

## 목적

Codex verify 응답의 각 이슈를 `scope_disposition`으로 분류하여 fz-plan Phase 3에서 additive 자동 번역을 차단한다. Claude(Lead)와 Codex는 독립적으로 분류하며 불일치 시 사용자에게 에스컬레이션한다.

## Q-S1 ~ Q-S4 체크포인트

각 Codex 이슈를 fz-plan Phase 3에서 처리하기 전 필수 실행:

### Q-S1: 요구사항 최소 집합 속하는가?
- Yes → scope-in 후보
- No → scope-out 후보

### Q-S2: develop 원본에 이미 존재했는가?
- 실측 필수: `git show {base}:{path}` 또는 `git blame` 결과 첨부
- 없으면 판정 불가 → "judgment_blocked"

### Q-S3: 원본 observable behavior 변화를 요구하는가?
- (a) 함수 반환값/타입/에러 경로
- (b) 실행 타이밍 (동기↔비동기, immediate↔deferred)
- (c) 콜백/클로저 실행 스레드 (미래 호출자 포함)
- (d) 사이드이펙트 순서
- (e) 재시도/재귀 경로
- **Thought-terminator 어구 감지**: "보장해야", "반드시 처리", "invariant 위반", "graceful degradation" 등이 판정을 주도하면 자동 AskUserQuestion

### Q-S4: 별도 ticket 분리 비용이 수용보다 큰가?
- 큰 경우: scope-in 후보 (무리해서라도 현재 PR에서 처리)
- 작은 경우: scope-out 후보 (후속 ticket)

## scope_disposition 분류

Q-S1~S4 결과를 다음 5개 중 하나로 매핑:

| disposition | 조건 | Phase 3 조치 |
|-------------|------|-------------|
| `scope-in` | Q-S1=Yes + Q-S2=No + Q-S3 Required + Q-S4=큰 | 플랜에 반영 |
| `scope-out` | Q-S2=Yes 또는 Q-S4=작은 | 후속 ticket 생성, 플랜 제외 |
| `invariant-risk` | Q-S3 Required이나 behavior 변화 수반 | AskUserQuestion |
| `parent-reopen` | Q-S5 발동 (P2-A, Appendix 참조) | AskUserQuestion + Phase 0.5 재진입 제안 |
| `improvement` | Q-S1=No이지만 Q-S2=No (개선 기회) | 보류 또는 후속 ticket |

## origin ↔ scope_disposition 매핑

기존 `codex_peer_review_schema.json`의 `origin` 필드와 매핑:

| origin | scope_disposition | 근거 |
|--------|-------------------|------|
| regression | scope-in | 이 PR이 만든 새 이슈, 수정 필수 |
| pre-existing | scope-out | develop에 이미 존재, 후속 분리 |
| improvement | improvement | 품질 개선 기회, scope-in 강제 금지 |
| (신규) — | invariant-risk | behavior 변화 — 사용자 판단 |
| (신규) — | parent-reopen | 부모 결정 무효화 — 사용자 판단 |

`pre-existing` 판정 시 `git show` 실측 결과 schema 필드에 첨부 의무 (rule 16차).

## Lead 독립 scope_disposition 절차 (P1-B Generator≠Evaluator)

Codex(Generator) 판정을 Lead가 단순 수용하지 않도록 독립 판정 의무:

```
Phase 3.2 Lead 독립 판정:

1. Codex verify 응답 수신. Codex_disposition 값을 **읽기 전** 다음 실행:

2. Lead 자체 Q-S1~S4 실행:
   - 이 이슈의 원문 및 위치만 참조
   - Codex 분류 결과를 참조하지 않음 (독립성 보장)
   - Lead_disposition 결정

3. 비교:
   - Lead_disposition == Codex_disposition → 채택
   - 불일치 → AskUserQuestion (사용자 판정 + 근거)

4. 기록: schema에 disposition 값 + 메타데이터:
   {
     "scope_disposition": "<채택된 값>",
     "meta": {
       "codex_verdict": "<Codex 분류>",
       "lead_verdict": "<Lead 분류>",
       "resolution": "agreed | user_decided"
     }
   }
```

**근거**: Generator≠Evaluator 원칙. Claude가 Codex 결과를 자동 수용하면 분류 자체가 single-model bias. 독립 판정 후 비교로 bias 차단.

## Appendix: Q-S5 Decision Re-open Gate (P2-A, 관측 중)

> **현 상태**: P2 (Decision-Lock 패턴 1회 관측, ASD-1136 유일). 본 Phase 3 체크리스트에는 **미포함**.
> **승격 조건**: ASD-1137+ eligible session 1건에서 재현 시 P1 승격. 자동 자동 확장 없음.

### Q-S5: 이 Codex 이슈가 **부모 결정 자체**를 재검토할 근거인가?

- Yes → scope_disposition = `parent-reopen` + AskUserQuestion
- No → Q-S1~S4 통상 진행

### 발동 예시 (ASD-1136)

v3 "SCNetworkReachability bootstrap" 결정 후 v3.1에서 Codex가 "flag 정확 복제" 이슈 제기. 이 이슈가 bootstrap **자체**를 재평가할 근거라면 Q-S5 발동 → 사용자 확인 → Q0 Required 기준 재평가.

### 승격 조건 (P2 → P1)

1. ASD-1137+ eligible session 1건에서 parent-reopen disposition 발동
2. 발동 결과는 승격 관리 정책에 따라 기록 (본 모듈 범위 밖)
3. 누적 후 Codex adversarial 검증 → approved 시 P1 승격

## Acceptance Criteria (P0-C 구현 완료 기준)

- [ ] `fz-plan/SKILL.md` Phase 3에 본 모듈 참조 1줄 추가
- [ ] 본 모듈이 자체 완결 (다른 `modules/` 재참조 없음)
- [ ] Q-S1~S4 + Lead 독립 절차 + disposition 매핑 전부 포함
- [ ] Q-S5는 Appendix (P2-A 상태)로만 표기
