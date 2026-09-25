# vX.Y.Z (YYYY-MM-DD) — 한 줄로 무엇이 드러났나 [MAJOR|MINOR|PATCH]

> 제목은 결론이 아니라 **발견**을 적는다. 이 릴리즈에서 가장 값이 나간 것이 무엇인지가 제목이다.

Closes: F-001-some-slug, F-002-another-slug

## 1. 무엇이 문제였나

기전을 적는다 — "왜 오류가 안 났나" 가 종종 항목의 핵심이다.

## 2. 무엇을 고쳤나

| 항목 | 이전 | 이후 |
|---|---|---|

## 3. 하지 않은 것

⛔ 하지 않은 것과 그 이유를 적는다. 근거 없이 미룬 것과 측정으로 기각한 것을 구분한다.

## 새 도구

| 스크립트 | 무엇 |
|---|---|

## 검증

self-test 결과 · 회귀 오라클 건수 · health-check exit.

---

## ⛔ `Closes:` 줄 규약

배출 스크립트(`scripts/eject_findings.py`)가 이 줄을 읽어 `fz-findings/entries/` → `.archive/`
이동 + `APPLIED.md` 1행을 만든다. **이 줄이 없으면 릴리즈가 finding 을 닫아도 레지스트리는 모른다** —
`docs/releases/v4.34.0`~`v4.37.0` 네 문서에 `F-` 인용이 0건이었고 그것이 배출률 5.8%(15/258)의
직접 원인이다.

- **full slug 로 적는다**: `F-001-artifact-processing-state-assumed`
- ID 만 적어도 되지만 **같은 번호가 둘 이상이면 거부된다**(현재 중복 ID 11쌍) — 모호한 채 이동하지 않는다
- 쉼표·공백 구분, 여러 줄 허용
- 닫은 것이 없으면 **줄을 쓰지 않는다** — 빈 `Closes:` 는 UNRUN(exit 2)이며 통과가 아니다

```bash
# dry-run 으로 먼저 본다
python3 scripts/eject_findings.py --root ~/dev/TVING/fz-findings \
  --note docs/releases/vX.Y.Z.md --version X.Y.Z --dry-run
# 실제 배출
python3 scripts/eject_findings.py --root ~/dev/TVING/fz-findings \
  --note docs/releases/vX.Y.Z.md --version X.Y.Z
# 사후 대조 (manifest ↔ APPLIED ↔ .archive)
python3 scripts/eject_findings.py --audit ~/dev/TVING/fz-findings
```

⛔ 배출은 **이동과 기록만** 한다. 삭제하지 않고, 무엇을 닫았는지는 릴리즈 저자가 적는다.
