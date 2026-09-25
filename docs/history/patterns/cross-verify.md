# Cross-Verify Search

> fz-search 전용 패턴. 두 탐색 전략으로 독립 검색 후 교차 검증한다.
> 전제: team-core.md 로드 완료.

---

## 역할 배분

| 역할 | 에이전트 | 전략 |
|------|---------|------|
| Supporting | search-symbolic (S) | LSP 심볼 탐색 (정의/참조/타입) |
| Supporting | search-pattern (S) | Grep/Glob 패턴 매칭 (텍스트/파일) |

Primary 없음: 두 탐색자 동등. Lead가 결과 합성.

## 2.5-Turn 적용 (Mesh, 2명)

### Round 1: 독립 탐색 + 결과 공유
```
search-symbolic: LSP 도구로 심볼 레벨 탐색
  → SendMessage(search-pattern): "심볼 탐색 결과: {발견 목록}"

search-pattern: Grep/Glob으로 텍스트 패턴 탐색
  → SendMessage(search-symbolic): "패턴 탐색 결과: {발견 목록}"
```

### Round 2: 교차 검증
```
search-symbolic: 패턴 결과를 심볼 레벨에서 확인
  → SendMessage(search-pattern):
    "패턴 결과 중 P3은 false positive (심볼 정의와 불일치). 나머지 확인됨."

search-pattern: 심볼 결과를 텍스트 패턴으로 보완
  → SendMessage(search-symbolic):
    "심볼 결과 S2에 추가 사용처 발견 (Grep으로 문자열 참조 2건 추가)."
```

### Round 0.5: 최종 보고
```
search-symbolic → SendMessage(Lead):
  "심볼 탐색 최종: {N}건. 교차 검증으로 {M}건 false positive 제거."

search-pattern → SendMessage(Lead):
  "패턴 탐색 최종: {N}건. 심볼 탐색에서 누락된 {K}건 추가 발견."
```

## Lead 역할

- 쿼리 분석 → 두 탐색자에 적절한 검색 지시 전달
- 최종 결과 Merge + Dedup + Rank
- 신뢰도 등급 부여:
  - ★★★: 양쪽 모두 확인
  - ★★: 한쪽만 발견, 교차 검증 통과
  - ★: 한쪽만 발견, 교차 검증 미수행

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-search | 전용 통신 패턴 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
