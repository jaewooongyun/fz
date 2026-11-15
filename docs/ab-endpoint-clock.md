# A/B 원장 — 러너 끝점 시계 (`collect --endpoint-clock`)

A/B 원장(`scripts/ab_ledger.py`)의 `wall_total` 끝점은 최종 산출물 기록 이벤트다. 시계가 없으면 그 이벤트를 Lead transcript 의 명령 문자열에서 찾는다. 해석기가 모르는 쓰기 꼴(예: `make -C … report` 가 안에서 쓰는 산출물)로 끝난 run 은 끝점이 없거나 더 이른 쓰기에 묶인다 — 파일 mtime 교차 검사가 그 run 을 무효로 만들 뿐 올바른 끝점을 주지는 못한다. 러너가 stream-json 루프에서 산출물을 직접 stat 해 남긴 기록(끝점 시계)을 `collect --endpoint-clock FILE` 로 넘기면 그 관측으로 끝점을 정한다.

**규범:** 끝점은 러너 관측 시각(t)이며, mtime 은 교차 대조에만 쓴다.

## 형식

JSONL — 한 줄이 관측 하나다. 러너는 stream-json 이벤트를 받을 때마다 산출물을 stat 하고, 크기 · mtime · 내용 해시가 바뀌었으면 한 줄을 덧붙인다.

| 키 | 형 | 뜻 |
|---|---|---|
| `t` | 시간대가 있는 ISO-8601 문자열 또는 epoch 초(숫자) | 러너가 그 변화를 본 stream-json 이벤트의 시각 |
| `path` | 절대 경로 문자열 | 산출물 — `collect --artifact` 로 넘기는 파일과 같은 파일 |
| `size` | 정수(bool 아님) | 관측 때 바이트 수 |
| `mtime` | 숫자(epoch 초 · bool 아님) | 관측 때 stat 의 mtime — 교차 대조용 |
| `sha256` | 소문자 16진 64자 | 관측 때 내용 해시 |

<!-- endpoint-clock-example -->
```jsonl
{"t": "2026-01-01T00:20:00.000Z", "path": "/runs/r1/repo/review/self-review.md", "size": 412, "mtime": 1767226800.0, "sha256": "5f2b3c0d7a9e4b1c6d8e0f2a4b6c8d0e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c"}
{"t": "2026-01-01T00:25:02.000Z", "path": "/runs/r1/repo/review/self-review.md", "size": 1630, "mtime": 1767227101.8, "sha256": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90"}
```

## 판정

- 산출물마다 그 경로의 **마지막 관측**(`t` 최대)이 기록 시각이다. transcript 해석기가 더 이른 쓰기를 찾았어도 시계가 이긴다. 끝점은 모든 `--artifact` 의 기록 시각 중 가장 늦은 것이다 — 시계에 관측이 없는 산출물이 하나라도 있으면 끝점이 없고 run 은 미완주다.
- 교차 대조: 마지막 관측의 `mtime` 과 collect 시점 파일 mtime 의 차이가 `MTIME_TOL_S`(5초)를 넘거나 `sha256` 이 다르면 마지막 관측 뒤 파일이 바뀐 것이다 — 미완주로 두고 사유를 적는다. 행의 `wall.mtime_delta_s` 는 (파일 mtime − 시계의 mtime)이다.
- 형식 위반 줄이 하나라도 있거나 시계를 읽지 못하면 시계 전체를 쓰지 않고 미완주로 둔다. transcript 해석 끝점으로 물러서지 않는다.
- 시계가 없으면 끝점은 지금처럼 transcript 해석으로 정한다. 명령 문자열 해석기는 시계와 무관하게 그대로다.
- 행의 `wall.clock` 에 관측 수 · 해석기가 찾았던 끝점(`parser_end`) · 그때의 mtime 차(`parser_mtime_delta_s`)를 남긴다 — 두 자를 나란히 볼 수 있게 한다.

## 증거와 재수집

- collect 는 시계를 증거 폴더(`--evidence-dir`, 기본 원장 옆 `evidence/`)에 내용 해시 이름 `endpoint-clock.<sha256 앞 16자>.jsonl` 로 복사하고 **사본을** 읽는다.
- 행에는 `collect_args.endpoint_clock`(사본) · `collect_args.endpoint_clock_source`(원본) · `sources.endpoint_clock`(사본 경로 · 원본 경로 · sha256)이 남는다(collect_args 는 CollectSpec `collect/1` 필드다).
- `recollect` 와 `judge --verify-sources` 는 사본을 읽는다 — 원본 시계를 고치거나 지워도 같은 끝점을 다시 만든다. 사본이 없어지면 그 run 은 미완주가 된다(재수집 악화로 드러난다).

## 수면 기록 (`collect --sleep-log`)

덮개를 닫아 생긴 수면은 wall 을 부풀리고 서브프로세스 타임아웃(단조 시계)을 멈춘다. 러너가 run 이 끝난 뒤 `pmset -g log` 출력을 파일로 남겨 `collect --sleep-log FILE` 로 넘기면, collect 는 run 구간(첫 사람 발화 ~ 끝점)의 `Entering Sleep` 줄을 센다.

- 행의 `sleep{count, source, sha256, note}` 에 남는다. 사본은 증거 폴더에 `sleep-log.<sha256 앞 16자>.txt` 로 두고 recollect 는 사본을 읽는다.
- judge 는 기록을 넘긴 run 에만 0 을 요구한다. 수면 진입이 1회 이상이면 그 run 을 뺀다. 기록을 읽지 못했거나 기록의 첫 시각이 run 시작보다 늦거나 마지막 시각(캡처 시각 — `pmset -g log` 은 캡처 시각 줄로 끝난다)이 run 끝보다 일러 구간을 덮지 못하면 0 으로 읽지 않고 `수면 판정 불가` 로 뺀다.
- 기록을 넘기지 않은 run 은 `count` 가 비어 있고(미측정) 이 검사를 받지 않는다. 그래서 정식 비교는 기록을 요구한다(아래).

## 정식 비교 절차 (`judge --formal`)

기본값을 바꾸거나(KEEP · 승격) 되돌리는(ROLLBACK) 결정의 근거, 그리고 릴리스 노트에 A/B 결과로 싣는 판정은 정식 비교로 낸다. 탐색 · 스모크 · 계측기 디버깅 판정은 `--formal` 없이 돌려도 되지만, `--formal` 없이 낸 판정은 결론으로 인용하지 않는다.

1. 수집 — 각 run 을 러너 끝점 시계(`--endpoint-clock`)와 수면 기록(`--sleep-log`)을 넘겨 collect 한다.
2. 계측기가 바뀌었으면(`instrument_sha`) 판정 전에 recollect 한다. recollect 는 run 마다 원천 범위(보관 사본 · 원래 자리 · 사라짐)를 먼저 찍는다. 원래 자리 원천(transcript · Workflow 폴더 · run 폴더)은 보존 기한이 지나면 사라지므로 그 전에 돌린다.
3. 판정 — `judge --formal --verify-sources <종류…>` 로 원천을 다시 읽어 대조하고, 원장에 기준선(B) 행이 있으면 `--plugin-sha <기준선 SHA>` 를 함께 준다. 둘 중 하나가 빠지면 UNRUN exit 2(`FORMAL-SOURCES-MISSING` · `FORMAL-PLUGIN-SHA-MISSING`)다.
4. 조건부 arm(review-live `stage2:'conditional'` · plan-lean2 `mergeMode:'conditional'`)은 처치 발동 수(`조건부 생략 N/M`)를 결과와 함께 적는다. 생략이 0회면 judge 가 `처치 미발동 — 판정 불가` UNRUN 을 낸다 — 그 arm 의 차이를 처치의 효과로 읽지 않는다. 릴리스 노트에 실을 때는 judge 출력을 파일로 남기고 `python3 scripts/check_release_notes.py --judge-summary <judge 출력> --notes docs/releases/v<버전>.md` 로 대조한다 — 노트가 arm 라벨과 같은 줄에 judge 와 같은 `생략 N/M` 을 적었고, 0/M arm 은 `판정 불가` 로만 적었는지 본다(F-506).

## 러너 쪽

시계 파일과 수면 기록을 쓰는 것은 A/B 러너(플러그인 밖)다. 이 문서는 플러그인이 읽는 형식과 판정만 정한다 — 러너가 시계를 남기지 않으면 collect 는 `--endpoint-clock` 없이 지금처럼 돈다.
