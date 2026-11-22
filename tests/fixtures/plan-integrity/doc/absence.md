# plan-v1 (F-611 · F-726 부재 주장 fixture — 경고 줄 = 5 · 6 · 7 · 15 ~ 19)

## S1 범위

옛 이름 호출처는 0건이다 [verified: git grep -c old_name scripts]
새 플래그를 읽는 곳이 없다 [verified: git grep -n new_flag]
남은 사본은 미발견이다.
옛 이름 호출처는 0건이다 [verified: git grep -c old_name] [대조: 같은 grep 이 new_name 을 scripts 에서 3건 찾는다]
범위 밖 적중은 0건이다 — scope_census 저장소 전체 12건 · 범위 안 0건 [verified: scope_census.sh]
양성 대조: 같은 명령이 fixture 에서 2건 · 실제 대상은 0건 [verified: git grep -c x]
바꿀 파일은 10건이다 [verified: git diff --stat]
이 값은 잴 수 없다 — 기록이 남지 않는다.
여기에는 새 테스트가 필요 없다.
명령은 `echo 0건` 을 쓴다.
호출처는 0건이다 [verified: git grep -c x] [대조:]
저장소 전체에서 호출처는 0건이다 [verified: git grep -c x]
남은 사본은 0건이다 [verified: git grep -c x] [대조: 없음]
호출처는 0건이다 [verified: git grep -c x] [대조: F-726 문서 확인 · 실제 적중 0건]
호출처는 0건이다 [verified: git grep -c x] [대조: a.py:12 · 적중 없음]

```bash
git grep -c foo   # 0건
```
