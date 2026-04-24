# Release Notes — v3.9.0

**Harness Engineering Enhancement**
2026-04-14

---

## Summary

하네스 엔지니어링 가이드(NLAH 프레임워크)를 fz 생태계와 체계적으로 대조하여
6개 Gap을 식별하고, 3개 Phase의 개선을 구현한 릴리즈.

핵심 원칙: **새 모듈 0개, 기존 모듈 확장만, SOLO에서는 결정론적 도구만.**

---

## New Features

### 1. SOLO 모드 Generator≠Evaluator 강화 (Gap G-R1)

SOLO 모드에서도 최소한의 Generator≠Evaluator 분리를 보장합니다.

- **cross-validation.md**: "SOLO 모드 검증 게이트 요약" 섹션 추가
  - 외부 피드백 → Read(시그니처) 필수
  - 런타임 주장 → Bash 실행 또는 "미검증" 표기
  - 3+ 파일 변경 → `/sc:reflect` 자동 트리거
  - 시그니처 변경 → `find_referencing_symbols` 필수
- **fz-code/SKILL.md**: sc: 테이블에 `SOLO + 3+ 파일 변경 → /sc:reflect --type correctness` 자동 트리거 추가 + Gate 3 체크리스트 항목

> 하네스 원칙 4: "자기 작업을 평가하면 자신있게 칭찬한다" — SOLO에서도 결정론적 도구로 최소 분리

### 2. PR 코멘트 대응 파이프라인 (Gap G-S1)

외부 이벤트(CodeRabbit, 팀원 리뷰 코멘트)에 대한 체계적 대응 파이프라인.

- **pipelines.md**: 19번째 파이프라인 `pr-comment-review` 추가
  - 하이브리드 경량 3단계: classify-all → verify-each → user-confirm
  - External Feedback Gate 의무 적용
  - 심각도 4단계 (critical/major/minor/nitpick) + 피드백 신뢰도 4단계
- **intent-registry.md**: 트리거 패턴 추가 (코드레빗, PR 코멘트 등)

> 하네스 NLAH-S: 외부 이벤트 진입점이 없으면 파이프라인 밖에서 즉흥 처리 → 일관성 보장 불가

### 3. NLAH Gap 분석 (가이드 문서 강화)

- **harness-engineering.md**: §12에 Gap 분석 테이블 추가
  - G-R1: SOLO Generator≠Evaluator 무효화 → 해결
  - G-S1: 외부 이벤트 진입점 없음 → 해결
  - G-F1: 추론 실패 자동 감지/복구 없음 → 관찰 모드
  - G-Σ1: 컨텍스트 비용 높음 → 현재 전략(모듈 분리) 유지

---

## Bug Fixes

- **pipelines.md**: 헤더 "17개" → "19개" 수정 (실제 18개 + 신규 1개)
- **fz/SKILL.md**: "18개" → "19개" Truth-of-Source 동기화

---

## Changed Files

| 파일 | 변경 | 줄 수 |
|------|------|-------|
| `modules/cross-validation.md` | SOLO 검증 게이트 섹션 추가 | 318→339 |
| `modules/pipelines.md` | 헤더 수정 + #19 파이프라인 추가 | 213→228 |
| `modules/intent-registry.md` | pr-comment-review 트리거 추가 | 77→78 |
| `skills/fz-code/SKILL.md` | SOLO reflect 트리거 + Gate 3 | 370→372 |
| `skills/fz/SKILL.md` | 파이프라인 개수 동기화 | 500→500 |
| `guides/harness-engineering.md` | §12 Gap 분석 테이블 | 1035→1046 |
| `README.md` | Changelog + 가이드 설명 업데이트 | 249→251 |

---

## Design Decisions

1. **새 모듈 0개**: 하네스 원칙 1 "가장 단순한 해결책부터" 준수. 모든 변경은 기존 모듈/스킬 확장
2. **SOLO에서 결정론적 도구만**: AP1(과도한 구조화) 방어. 에이전트 스폰/Codex는 TEAM 전용 유지
3. **관찰 모드**: 추론 실패 감지(G-F1)는 단일 사건이므로 즉시 규칙화하지 않음 (과적합 방지)
4. **하이브리드 파이프라인**: PR 코멘트 대응을 풀 파이프라인이 아닌 3단계 경량 구조로 설계 (컨텍스트 비용 절감)

---

## Migration

**하위 호환**: 모든 변경이 additive. 기존 스킬/파이프라인/에이전트에 영향 없음.
**별도 조치 불필요**: 플러그인 업데이트만으로 자동 적용.

---

## Known Issues

- `fz-peer-review`: 508줄 (500줄 제한 초과, 이번 릴리즈와 무관)
- `arch-critic`, `code-auditor`: allowed-tools YAML 누락 (에이전트 전용, 독립 호출 안 함)

---

## Next (v4.0 후보)

- Phase 4: 분기별 Ablation 프로토콜 운영화
- 추론 실패 감지 관찰 모드 → 3건+ 누적 시 정식 Gate 승격
- 관찰 지표 경량 도입 (Gate First-Pass Rate, Escalation Frequency)
