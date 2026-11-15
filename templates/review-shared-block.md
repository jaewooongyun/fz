## ⛔ 분석 제약

- **init/DI 패턴 이슈 판정 전**: `evidence/caller-analysis.md`의 호출자 코드를 **반드시** 확인.
  "이 init을 호출하는 코드가 어떤 concrete 타입을 알아야 하는가?"
  수정 제안 시 caller가 더 많은 타입을 알게 되면 → 역효과. 제안 방향 재검토.
- **패턴 이슈 판정 전**: `evidence/convention-samples.md`를 **반드시** 확인.
  Convention 패턴 (3+ 모듈 동일)은 severity **suggestion 이하**로만 판정.
- **"교과서적으로 틀렸다"는 단독 근거로 major 판정 금지.**
  프로젝트에서 같은 패턴이 3+ 곳에 있으면 convention.
- **convention은 양방향 입력이다** — 억제만이 아니라 **처방**에도 쓴다.
  · 관례와 **같음** → 위 억제 규칙 적용 (severity 하향)
  · 관례와 **다름** → *"형제 N곳이 X 형태인데 이번만 Y"*를 근거로 제시한다. 규칙 위반이 아니어도 유효한 지적이다 — "형제가 다르다"가 그 자체로 근거다.
  ⛔ **N 강도 임계는 미정이다 — severity를 부여하지 않는다.** 표본 1건(PR I3, N=5)으로는 등급 근거가 없다. 형제 N곳을 세어 **근거로 제시하고 관찰 보고로 남긴다.** 임계 SSOT는 `modules/review-checks.md` 4-E (표본 3건 후 확정) — 1표본 임계는 리뷰어 간 severity 를 가르고 `fz-review` Gate 4 에서 차단으로 변한다.

---

## Per-Agent 품질 원칙

시니어 엔지니어가 PR 코멘트로 달 만한 이슈만 보고한다. **이슈 0개도 유효한 결과다.**
자체 confidence 80% 미만이면 보고하지 않는다. 이슈 수가 많으면 진짜 문제가 marginal finding에 묻힌다.
> ⊕ 워크플로 프롬프트에 `[후보 보존]` 문장(preserveLowConfidence 옵션 — `modules/peer-review-gates.md` §10)이 있으면 위 문장과 아래 `자체 신뢰도 임계치` 행을 적용하지 않는다. confidence 는 값으로 달아 그대로 보고하고, 게시 여부는 병합이 정한다. 그 문장이 없으면 원칙 그대로다.

| 항목 | 제한값 |
|------|--------|
| description | 400자 이내 (WHY 필수) |
| impact | ⛔ 스키마 필드 아님 — `description`에 영향 서술 포함 (major 이상 필수) |
| suggestion | 300자 이내 |
| strengths | 최대 3개 |
| 자체 신뢰도 임계치 | confidence < 80 → 보고하지 않음 |

## 판정 기준

| 조건 | overall_assessment |
|------|-------------------|
| Critical 0개 + Major 0개 | `excellent` 또는 `good` |
| Major 1-2개 | `needs_improvement` |
| Critical >= 1개 또는 Major >= 3개 | `major_concerns` |
