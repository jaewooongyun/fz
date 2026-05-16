# Audit Report (Phase 2 Template)

> **사용법**: 본 템플릿을 `{WORK_DIR}/audit/audit-report.md`로 복사 후 채우기.
> **트리거**: probe-report.md 완료 후 → 가이드 line-level stale 분석 시.
> **변경 정책**: Reference 추가 + 미검증 태그 해소만 (본문 재구성 X — AC1).

## 0. 변경 영향 요약

| 가이드 | 미검증 태그 | Reference 추가 | Deprecated 변경 | 인라인 강화 | 변경 LOC 예상 |
|--------|----------|------|-----|------|-----|
| (가이드명) | (개수) | (개수) | (개수) | (개수) | ~LOC |
| **합계** | | | | | |

> 본문 재구성 없음 → 모듈 참조 깨짐 위험 0 (AC1 준수).

## 1. {가이드 1} (1순위)

### 1.1 미검증 태그 처리 결정 표

| Line | 현재 표현 | 해소 자료 | 변경 결정 |
|------|---------|---------|---------|
| L{N} | `[미검증: ...]` 또는 stale 표현 | A1, B2 등 | `[verified: A1; supporting: A5]` 등 |

### 1.2 학술 표 / 공식 표 보강

| 추가 위치 | 추가 내용 | 출처 |
|---------|---------|-----|
| (line 또는 표 이름) | (표 row) | (URL) |

### 1.3 새 카테고리 신설 (필요 시)

```markdown
### {새 카테고리} (신규)

| # | 제목 | 저자 | 날짜/Status | URL |
|---|------|------|-------|-----|
| ... | | | | |
```

> AC7 경계선 — Plan v1에서 사용자 명시 합의 필요.

## 2. {가이드 2} (2순위)

(동일 형식)

## N. Anti-Pattern Constraints (Phase 3 Plan에 반영 예정)

본 audit에서 식별된 위험을 Plan v1 §1 AC1-AC9에 명시:

1. **본문 재구성 금지** — 모듈 참조 깨짐 방지
2. **기존 verified 태그 보호** — (예: `[verified: Anthropic 2026.03]`)
3. **임의 deprecation 추가 금지**
4. **출처 표기 통일성** — 한 가이드 안에서 일관성
5. **L{N} {특정사실} 미검증 유지** — (예: Korean tokenizer 실측 부재)
6. **{stable 가이드} 본문 변경 금지** — (예: clean-architecture.md는 References 1줄 추가만)
7. **새 원칙/섹션 추가 금지** — 합의 깊이 제한

## 다음 단계

→ Phase 3 (Plan): `plan/update-plan.md` 작성 (templates/update-plan-template.md 참조)
