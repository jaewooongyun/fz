# Update Plan v{N} Template (Phase 3)

> **사용법**: 본 템플릿을 `{WORK_DIR}/plan/update-plan.md` (v1) 또는 `update-plan-v{N}.md` (v2+)로 복사.
> **버전 패키징**: v1 → v2 (보강 + Codex risk 해소) → v3.1 (점 수정 inline)
> **승인 요건**: 사용자 Phase 4 합의 + Codex verify (한도 3회).

## 0. 메타데이터 + 버전 진화

| 항목 | 값 |
|------|-----|
| 계획 일시 | YYYY-MM-DD |
| 버전 | v1 / v2 / v3.1 (Codex 정정 inline 반영본) |
| 변경 trigger | (probe + audit 결과 / 보강 / Codex risk 해소) |

### v{N-1} → v{N} 변경 요약 (해당 시)

| 항목 | v{N-1} | v{N} | 차이 |
|------|----|----|----|
| Step 1 LOC | ~ | ~ | + |
| Anti-Pattern 수 | | | |
| 출처 표기 규약 | | | |
| **합계 LOC** | | | |

## 1. Anti-Pattern Constraints (AC1-AC9)

| # | 금지 패턴 | 이유 | 검증 grep/스크립트 |
|---|----------|-----|------|
| AC1 | 본문 재구성 | 모듈 참조 깨짐 | git diff LOC > 200 → 알림 |
| AC2 | 기존 verified 태그 변경 | 사실 보호 | `grep -nE "verified: <protected>"` 비교 |
| AC3 | 임의 deprecation 추가 | 사용자 명시 신호 없음 | Deprecated 목록 변경 0 |
| AC4 | 출처 표기 통일성 위반 | 가독성 | 한 가이드 안 일관성 |
| AC5 | 미검증 임의 verified 처리 | 정확성 | (예: Korean tokenizer 보호) |
| AC6 | stable 가이드 본문 변경 | (예: 도서 기반) | 본문 변경 0 |
| AC7 | 새 원칙/섹션 추가 | 합의 깊이 제한 | 모든 변경 = 기존 항목 추가/교체 |
| AC8 | broken link 미감지 | 신뢰성 | xargs 병렬 스크립트 (§AC8) |
| AC9 | Tier 3 단독 verified | A5 과승격 | rg -n -e 스크립트 (§AC9) |

## 2. 출처 표기 규약

```
[verified: <Tier 1+2 source>]                 ← 단독 verified 가능
[verified: A1; supporting: A5]                 ← Tier 1 + Tier 3 보강
[partially-verified: A5; A1 직접 진술 없음]   ← Tier 3 only
[arxiv preprint, YYYY-MM]                      ← preprint 명시
[ICLR YYYY Oral / peer-reviewed]              ← peer-reviewed 명시
[official framework: <URL>]                    ← 회사 공식 도구
[community: <URL>]                             ← Tier 3 그대로 (verified 금지)
[미검증: <구체적 사유>]                        ← 검증 불가
```

### Tier 매핑

> **Single source**: `skills/fz-modernize/SKILL.md` §출처 표기 규약 §Tier 매핑 참조.
> 본 위치는 reference만 유지 (중복 정의 방지 — G7).

## 3. 미검증 태그 처리 분류 (audit 결과 기반)

| Line | 사실 | A1 직접 입증? | A5 supporting? | v{N} 처리 |
|------|------|-------|-------|---------|
| L{N} | "..." | ✓ / ✗ | ✓ | `[verified: A1; supporting: A5]` 등 |

## 4. Step 분해

### Step 1: {가이드 1} 업데이트 (1순위, ~{LOC})

**작업**:
1. 미검증 태그 처리 (§3 표 기준)
2. 학술 표 보강 (Bx 추가)
3. 공식 표 보강 (Ax 추가)
4. 새 카테고리 신설 (필요 시)

**검증**: grep `\[미검증` → 의도된 N건만 남아야 함
**예상 LOC**: ~

### Step 2: {가이드 2} 업데이트 (1순위, ~{LOC})

(동일 형식)

### Step N: {기타 가이드}

(동일 형식)

## 5. 검증 게이트

### Gate 5c-1: Stress Test (Q1-Q5)

| Q | 질문 | 검증 |
|---|------|------|
| Q1 | 다중성 (N=1 vs N=많음 동일 동작?) | grep |
| Q2 | 소비자 영향 (모듈 깨짐?) | impact-scan |
| Q3 | 복잡도 이동 (다른 레이어 부담?) | LOC 비교 |
| Q4 | 경계 (Tier 1+2 합의 준수?) | Tier grep |
| Q5 | 접근 경계 (의도된 차단 실효성?) | enforcement grep |

### Gate 5c-2: Codex Verify

```
Plan v{N}을 GPT-5.5로 검증
누적 카운터: {현재}/3 (한도 도달 시 사용자 에스컬레이션)
```

### Gate 5d-1: Impact Scan (Phase 5d 직전)

```bash
grep -rn "guides/{filename}:L\d+" modules/ skills/ docs/ 2>&1
# line 번호 deep-link 0건이어야 안전
```

### Gate 5d-2: Build-Equivalent (link 검증)

`scripts/ac8-link-check.sh` 실행 → broken link 0건

### Gate 5d-3: 직접 근거 매트릭스

`verify/verify-evidence-matrix.md` 작성 → 25 row 자동 검증

## 6. 실행 순서 (Phase 5)

```
Phase 5d-1: Step 1 → Codex check + 사용자 검토
Phase 5d-2: Step 2 → Codex check + 사용자 검토
Phase 5d-N: Step N → 가벼운 검토
Phase 5d-final: AC8 link + Impact Scan + 최종 검토
```

## 7. 메타 안전 장치

| 장치 | 트리거 | 대응 |
|------|------|------|
| Codex 3회 한도 (18차) | needs_revision 누적 3 | 사용자 에스컬레이션 |
| Scope Inflation (18차) | LOC > Plan 예상 1.5x | 즉시 중단 |
| Speculation 감지 | "원본/기존/이전" | git show / Read 실측 |
| Reflection Gap (17차) | Plan stale | 5d 시작 전 plan 재검토 |
| Cross-model 안전망 (17차/16차) | self-review 사실 오류 | Codex 단독 발견 우선 적용 |

## 8. 다음 단계

→ Phase 4 (Codex Verify): `/fz-codex verify {plan}`
→ approved → Phase 5 (Execute)
→ needs_revision → v{N+1} 작성 (카운터 +1)
