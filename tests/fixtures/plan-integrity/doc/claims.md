# plan-v1 (F-185 산문 주장 fixture — 경고 줄 = 5 · 8)

## S1 범위

바꿀 스크립트는 12개다.
호출처는 4곳이다 [verified: git grep -c foo → 4]
소비자는 code-context.md:12 행 기준 3곳이다.
옛 분기는 `lib/a.py:30` 에 있다.
게이트는 `--ids F-102:1` 과 `count=2` 를 쓴다.
이 작업은 3개월 전 결정이다 — S2 는 F-145 를 닫는다.

```bash
git grep -c foo   # 30건
```
