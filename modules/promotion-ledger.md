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

## ASD-1674 회고 후보 (P2, 관측 #1)

> 출처: `TVING/TVOD/ASD-1674/retrospective/session-mistakes-2026-05-29.md` (20 catches) + `fz-improvement-analysis.md` (분류)
> Eligible session 확인: ASD-1674 = fz-plan Phase 0.5~3 (plan v1~v5) + fz-codex verify 2건 → 기준 (a)+(b) 충족 [verified: plan/codex-verify-output.md, codex-verify-v3-output.md 존재]
> ⛔ **승격 차단**: 2026-06-01 세션 Codex 한도 초과 → P2→P1 조건의 "Codex verify → approved" 미충족. 관측 #1 등록까지만. cross-model 검증 PENDING.
>
> **⛔ 2-트랙 구분 (모순 해소 2026-06-01)**: L-1~L-3은 friction 신호를 보유 → 두 lifecycle이 분리된다.
> - **트랙 A (신호 활성·canonical)**: candidate friction 신호 → active 전환. 기준 = memory-guide line 43 **5 sessions 관측**. Codex verify = 활성 전 *권장 품질 게이트*(복구 시).
> - **트랙 B (메모리 승격)**: lesson → MEMORY.md 항목/별도 모듈. ⛔ MEMORY.md 252줄 한도초과로 **현재 비권장**.
> - L-1~L-3 1차 경로 = **트랙 A**. L-4(friction 신호 없음) = 트랙 B(ledger-only).

### L-1: figma 토큰 테이블 exhaustiveness (23차 강화)
- 관측 #1: ASD-1674 (catch #1,2,4,8,17,19,20 — figma 토큰 7건)
- 내용: figma 토큰 테이블 작성 시 변경 코드의 *모든 수치* enumerate 또는 non-exhaustive 마킹 + code 시점 per-value MCP 측정
- generalize: **narrow** (figma/UI 전용) | 과적합 위험: 中
- 근거: [verified: index.md — 23차로 figma-tokens.md 작성됐으나 §5 갭 테이블이 간격/마진 누락 → exhaustiveness 보증 부재]
- ⚡ 조치 (2026-06-01): *code 시점* 부분(개별 수치 figma 대조)을 fz-code friction-detect에 **candidate 마찰 신호 추가** (active). *plan 시점* 부분(토큰 테이블 exhaustiveness, fz-plan §F) + broad CLAUDE.md 1줄은 **보류** (narrow + 42차 frame 한계 + 23차 중복 → Codex/사용자 판단)
- 승격 목표 (트랙 A): figma 작업 세션 5회 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-2: fz-code 구현시점 reuse 게이트 (41차 enforcement plan→code 이동)
- 관측 #1: ASD-1674 (catch #3,6,7 — helper 중복 작성)
- 내용: fz-code 구현 *전* TvingCore/TvingUtil/Apps Util grep 게이트 (현재 41차는 fz-plan에만 enforce)
- generalize: **broad** (모든 helper 작성) | 과적합 위험: 低 (기존 방어 이동, 신규 규칙 아님)
- 근거: [verified: fz-code/SKILL.md friction-detect에 reuse 항목 0건 — grep "reuse|코드반복|기존 helper" 결과]
- ⚡ 조치 (2026-06-01): fz-code friction-detect에 **candidate 마찰 신호 추가**. candidate *추가*엔 Codex 불요 (41차 구조적 grep 검증 + 사용자 catch #3/#7 권위). 단 candidate→active *전환*엔 Codex verify 권장 (트랙 A). ledger=메모리 승격(트랙 B) 추적, friction 신호=code 시점 발화 (별개 레이어)
- 승격 목표 (트랙 A): 5 sessions 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-3: analysis-deferred-churning (31/33/40차 복합 신규 트리거)
- 관측 #1: ASD-1674 (catch #13 — 위치 정렬 11-iteration churn)
- 내용: 단일 UI/설계 문제 *2회+ 변경* 시 self-stop + trade-off table 먼저 + 사용자 결정 후 1회 구현
- generalize: **broad (강)** (모든 반복 수정 상황) | 과적합 위험: 低
- 근거: [verified: retrospective §7-8 — 11회 변경 기록 + 사용자 "계속 바꾸지 말고 객관 분석하라"]
- ⚡ 조치 (2026-06-01): fz-code friction-detect에 **candidate 마찰 신호 추가** (memory-guide 5-session intake 대상). 사용자 catch #13 권위. broad. ⚠️ 단 churn은 31/33/40 *파생 new-trigger*(순수 enforcement-gap 아님) — 트랙 A 활성 전 Codex 재검토 권장 (#4 교정)
- 승격 목표 (트랙 A): 5 sessions 관측 후 신호 활성 (memory-guide line 43). Codex verify = 활성 전 권장 게이트.

### L-4: skill-procedure-default (team-core 보강)
- 관측 #1: ASD-1674 (catch #9,11 — 팀 gc 스킬 미사용 + index 갱신 누락)
- 내용: 스킬 호출 시 본문 절차 따르기 + CLAUDE.md 권장 팀 스킬(gc/pr 등) 우선
- generalize: **broad** | 과적합 위험: 中
- 근거: [verified: retrospective catch #9 — fz-commit 본문 /sc:git 미사용 + Bash git commit 직접]
- 승격 목표 (트랙 B, ledger-only — friction 신호 없음): P2→P1 = 세션 1건 + Codex verify + 사용자 승인.

### REJECTED (subsumed — 등록 안 함, 재제안 방지용 기록)
- ~~codebase-helper-3area-grep~~: 41차(Reuse-First) + fz-plan/fz-review reuse가 이미 포섭. 새 규칙 = 중복. (발화 지점 결함은 L-2로 분리 등록)
- ~~asset-rename-impact-grep~~: 17차(Pre-Gate Failure 영향 범위 사전 grep)에 포섭. 별도 규칙 불요.

## 미달 조치 정책

eligible session 없이 3개월 경과 시:
- 해당 P1/P2 항목 재평가
- 사용자 문의 → DEFERRED 또는 REMOVED
- DEFERRED는 6개월 후 재평가. REMOVED는 제안 폐기.
