# Promotion Ledger — P1/P2 조치 관측 기록

> 참조: `modules/scope-challenge.md`, ASD-1136 v2.2 Patch-4
> 목적: P1 → P0 및 P2 → P1 승격을 위한 eligible session 관측 누적
> 원칙: 학습 승격 (자동 확장) 금지. AskUserQuestion + 기록만

## Eligible Session 정의

다음 두 조건을 모두 충족하는 ASD-{번호} 세션:

(a) `/fz-plan` Phase 0.5 ~ Phase 3 중 하나 이상 실행
(b) `/fz-codex verify` 또는 `/fz-review --deep` 실행

## 관측 기록 형식

각 eligible session 종료 시 해당 P1/P2 항목에 1건 append:

```markdown
### {P-ID}: {조치 이름} — 관측 #{N}
- Session: ASD-{번호}
- Date: YYYY-MM-DD
- 관측 내용: {발동 여부 + 상황}
- disposition 결과: {채택된 disposition}
- 근거: [verified: {file}:{line}] 인용
- Lead/Codex 일치 여부: agreed | user_decided
```

## P1 → P0 승격 조건

1. Eligible session 2건 누적 (동일 P-ID)
2. 2건 모두 [verified] 근거 첨부
3. 2건 누적 후 `/fz-codex adversarial` 실행 → approved
4. 사용자 최종 승인 → v{N+1} 릴리스에 P0 반영

## P2 → P1 승격 조건

1. Eligible session 1건 누적 (동일 P-ID)
2. [verified] 근거 첨부
3. `/fz-codex verify` 실행 → approved
4. 사용자 최종 승인 → v{N+1} 릴리스에 P1 반영

## 현재 관측 대상 (v2.2 기준)

### P1-B: Generator≠Evaluator Lead 독립 절차
- 관측 #0: ASD-1136 (원본, 3차 설계 반영)
- 승격 목표: ASD-1137+ 2건

### P1-C: Drift telemetry (AskUserQuestion)
- 관측 #0: ASD-1136 (원본)
- 승격 목표: ASD-1137+ 2건

### P1-D: Q4 재구성 + rule 11차 컴파일 가능 기준
- 관측 #0: ASD-1136 (원본)
- 승격 목표: ASD-1137+ 2건

### P2-A: Q-S5 Decision Re-open Gate
- 관측 #0: ASD-1136 (Decision-Lock 패턴 단독 관측)
- 승격 목표: ASD-1137+ 1건 (P1 승격), 이후 1건 추가 (P0 승격)

### P2-B: fz-fix 자동 전환 + complexity.md 보정
- 관측 #0: ASD-1136 (plan-impact 단독 지적)
- 승격 목표: ASD-1137+ 1건 (P1 승격)

## 미달 조치 정책

eligible session 없이 3개월 경과 시:
- 해당 P1/P2 항목 재평가
- 사용자 문의 → DEFERRED 또는 REMOVED
- DEFERRED는 6개월 후 재평가. REMOVED는 제안 폐기.
