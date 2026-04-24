# Feedback Verification — 역방향 피드백 검증 프로토콜

> **Scope of Applicability**: fz-review Phase 5.5 전용. 다른 스킬에서 재사용하려면 Reflection Rate 임계치와 verdict 매핑이 해당 스킬의 리뷰 단계에 부합하는지 먼저 검토해야 한다.
>
> **Purpose**: 이전 라운드의 이슈들이 실제로 해결되었는지 cross-model(Codex)로 독립 검증. Claude 자체 판단이 아닌 외부 관점으로 Reflection Rate를 산출.

---

## 절차

```bash
# 독립 스킬로 위임
/fz-codex validate "피드백 반영 검증"
```

`/fz-codex validate`가 수행하는 작업:
- 이전 이슈 목록 + Claude 수정 내용 → Codex에 전송
- 이슈별 해결 상태 검증 (`resolved` / `partially_resolved` / `unresolved` / `regressed`)
- Reflection Rate 계산 (canonical source: `schemas/codex_verification_schema.json`):
  `(resolved × 1.0 + partially_resolved × 0.5) / total_issues`
- Issue Tracker 상태 업데이트

---

## Gate 4.5: Feedback Verified

- [ ] Codex가 이전 이슈들의 해결 상태를 검증했는가?
- [ ] Feedback Reflection Rate >= 80%?
- [ ] 새로 발견된 Critical 이슈가 없는가?
- [ ] Regressed 이슈가 없는가?

---

## 판정 기준

| Reflection Rate | Verdict | 다음 단계 |
|-----------------|---------|----------|
| >= 80% | `pass` | Gate 5 통과 → Phase 7 완료 |
| 60% - 79% | `needs_work` | Phase 6 (재수정) |
| < 60% | `fail` | Phase 6 (재수정, 2회 후 에스컬레이션) |

---

## 관련 모듈

- `modules/cross-validation.md` — cross-model 검증 원칙
- `modules/peer-review-tiers.md` — 이슈 severity 티어
- `skills/fz-codex/SKILL.md` — `validate` 서브커맨드 상세
