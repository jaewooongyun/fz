# CLAUDE.md — fz-compact (fz 하위 플러그인)

> 개발용 문서다. 플러그인 루트의 CLAUDE.md 는 사용자 세션에 로드되지 않는다(`plugin_validate.sh` 가 이 경고를 카나리아로 쓴다 — 지우지 않는다).

## 구조
- `hooks/register.ts` — 훅 등록(결정표 · bg 유휴 타이머 · 재개 재마스킹 · `tool.check`)
- `lib/policy.ts` — 마스킹 대상 판정(순수 함수)
- `lib/spill.ts` — 원문 보관 · manifest · 정리
- `hooks/guard.sh` — classic PreCompact 명령 훅(`hooks.json` 의 `hooks`). fz-compact 가 줄 세운 compaction(`fz-compact:idle:<숫자>` · `fz-compact:resume`)이 모듈 훅에 닿지 못하고 core 로 떨어지면 exit 2 로 막아, 엔진이 모델 요약을 하지 않게 한다
- `tests/*.test.ts` — `claude plugin test mods/fz-compact`
- `tests/guard_test.sh` — `guard.sh` 판정 시험과 표식 선언 줄 대조(sh). `plugin test` 는 이 파일을 돌리지 않고, health-check 의 `fz-compact guard` 줄이 부른다

## 설정 (`.claude-plugin/plugin.json` 의 `userConfig`)
| 키 | 기본 | 허용 값 | 뜻 |
|---|---|---|---|
| `enabled` | `false` | `true` / `false` | 켜기 전에는 타이머 · `/compact` 명령 · 지시문 덧붙이기를 하지 않는다 |
| `idleGuardMinutes` | `61` | 1 이상인 수 | bg 세션이 이만큼(분) 쉬면 유휴 마스킹을 건다 — 프롬프트 캐시 1시간이 지난 뒤 |
| `idleMinTokens` | `200000` | 1 이상인 수 | 컨텍스트 토큰이 이보다 적으면 유휴 마스킹을 걸지 않고, 재개 재마스킹도 manifest 에 확인 표시가 없는 결과는 새로 마스킹하지 않는다 |
| `keepRecentUserTurns` | `6` | 1 이상인 정수 | 최근 사람 프롬프트 이만큼은 보호 구간 — 그 안의 결과는 마스킹하지 않는다. 엔진이 넣는 행(백그라운드 작업 알림 · 로컬 명령 출력 · 슬래시 명령이 펼친 스킬 본문)은 세지 않는다 |
| `minMaskChars` | `1200` | 1 이상인 정수 | 이보다 짧은 결과는 보존 |
| `minNetReductionPercent` | `20` | 0~100 | 순절감이 대화 글자(메시지 텍스트 + 도구 호출 인자 + 도구 결과)의 이 비율보다 작으면 skip |
| `minNetReductionTokens` | `50000` | 0 이상인 수 | 순절감이 이 토큰(글자÷4)보다 작으면 skip |
| `remaskOnResume` | `true` | `true` / `false` | bg 세션을 재개하면 같은 결과를 같은 표시로 다시 마스킹 |
| `spillDir` | `""` | 절대 경로(`/` 하나는 안 됨), 또는 빈 값 | 원문 보관 위치. 빈 값이면 `<HOME>/.claude/fz-compact/spill` |
| `spillRetentionDays` | `30` | 1 이상인 수 | spill 파일 정리 기한(일) |

- 값은 모두 유한해야 하고 범위 안이어야 한다. `spillDir` 가 상대 경로이거나 `/` 하나인 것도 틀린 값이다. 하나라도 틀리면 기능을 끄고(`enabled` 를 false 로 본다), 그 활성화에서 처음 오는 `session.start` · `turn.complete` · `session.compact` 에서 `$.ui.log` 한 줄로 이유를 남긴다(활성화마다 한 번).
- 순절감 skip 은 두 기준 중 하나만 못 넘어도 걸리고, 파일을 쓰기 전에 판정한다. 비율을 재는 대화 글자는 메시지 텍스트, 도구 호출 인자(`input` 을 JSON 으로 쓴 길이), 도구 결과 텍스트를 모두 더한 값이다(`conversationChars`). Write · Edit 의 큰 인자도 모델이 읽는 문맥이라 함께 센다. 글자÷4 는 `register.ts` 의 `CHARS_PER_TOKEN` 이다.
- 재개 재마스킹(`fz-compact:resume`)은 manifest 에 확인 표시된 `tool_use_id` 를 순절감 검사 없이 같은 표시로 다시 마스킹한다. 그 밖의 후보(manifest 에 없거나 확인 표시가 없는 것)는 컨텍스트가 `idleMinTokens` 이상이고, 그것만으로 두 기준을 넘을 때만 함께 마스킹한다. 그렇지 않으면 원문으로 두고, 관찰 줄에 이유를 남긴다. 컨텍스트 크기는 세션이 알려 주는 컨텍스트 토큰(`usage().context.tokens`)이고, 세션이 알려 주지 않으면 대화 글자÷4 로 어림한다. 엔진은 살아 있는 창의 첫 응답 전에는 이 값을 주지 않으므로, 콜드 재개는 보통 어림값을 쓴다. 어림값에는 시스템 프롬프트나 첨부처럼 행에 없는 부분이 들지 않으므로, 재개는 같은 세션의 유휴 compaction 보다 덜 마스킹할 수 있다.
- 행은 그 행의 결과가 모두 spill 됐을 때만 통째로 바뀐다. spill 이 일부 실패하면 실제로 바뀌는 행에 든 새 결과만으로 절감을 다시 재고, 미달이면 새 결과는 모두 원문으로 둔다(유휴 · 재개 공통). 답을 돌려주기 전에, 돌려준 행에 실린 결과만 manifest 에 확인 표시를 하고, 재개는 확인된 항목만 검사 없이 다시 가린다. 이번 compaction 이 새로 spill 했지만 돌려준 행에 실리지 않은 결과는 같은 쓰기에서 manifest 에서 뺀다. 그 spill 파일은 이름 없는 파일이 되어 24시간 뒤 정리된다. 확인 쓰기가 실패하면 그 결과는 다음 재개에서 절감 검사를 다시 받는다 — 확인 표시가 없는 것이 기본이라, 쓰기가 실패해도 검사를 건너뛰는 쪽으로 새지 않는다.
- 줄 선 `/compact fz-compact:…` 는 main 턴이 진행 중이면(`turn.start` 뒤 `turn.complete` 전) skip 한다. 엔진은 줄 선 명령을 턴이 끝나는 순간, 이 플러그인의 `turn.complete` 가 세대를 넘기기 전에 꺼낼 수 있다(bg 실측).
- 훅 사슬은 [managed settings 훅, 훅 모듈들, 나머지 settings 훅(core)] 순서다. 모듈 훅이 줄 선 compaction 에 답하면(마스킹이든 skip 이든) core 가 돌지 않고 `guard.sh` 도 돌지 않는다. 모듈 훅이 우회되거나(앞 단 플러그인이 넘김) 실패해 건너뛰어지면 core 로 내려가고, 그때 `guard.sh` 가 표식을 보고 막는다. 사람이 직접 친 `/compact` 는 표식이 아니므로 통과한다(bg 실측: 마스킹 경로 안전 훅 0회 · 사용자 `/compact` 통과 · fz-compact 없이 표식 `/compact` 는 차단).
- 유휴 타이머가 울렸을 때 컨텍스트 토큰 수(`usage().context.tokens`)를 읽지 못하면 유휴 마스킹을 걸지 않고, 활성화마다 한 번 `$.ui.log` 로 남긴다.

## 환경 변수
- `CLAUDE_CODE_SESSION_KIND` — 값이 `bg` 일 때만 유휴 타이머와 재개 재마스킹이 돈다. 지시문 덧붙이기와 `tool.check`(spill 파일 Read 허용)는 이 값과 상관없다. `tool.check` 는 spill 루트 아래 `<세션 id>/<tool_use_id>.txt` 자리에 있고 그 세션의 manifest 가 이름을 댄 파일만 묻지 않고 허용한다(확인 표시 여부는 보지 않는다). 루트 아래 다른 파일이거나 manifest 를 읽지 못하면 엔진 판정이 그대로 선다. 이 허용은 `enabled` 와도 상관없다 — 끄기 전에 마스킹한 세션의 표시가 spill 파일을 가리키므로, 끈 뒤에도 그 원문을 읽을 수 있어야 한다.
- `FZ_COMPACT_TEST_IDLE_MS` — 시험용이다. 기본은 설정하지 않는다. 양의 정수(ms)를 넣으면 `idleGuardMinutes` 대신 그 값이 유휴 임계값이 된다. 타이머 · 줄 선 compact 의 재검증 · 재개 판정이 모두 `idleThresholdMs` 하나에서 값을 받으므로 함께 바뀐다. 실제 세션에서는 설정하지 않는다.

## 끄기 · 되돌리기
- `enabled` 를 `false` 로 바꾸면 설정 변경으로 플러그인이 다시 로드되면서 걸려 있던 유휴 타이머가 취소되고, 그 뒤로 타이머 · `/compact` 명령 · 지시문 덧붙이기가 없다. 이미 줄 선 `/compact fz-compact:…` 는 돌아도 skip 된다.
- 마스킹된 세션을 재개하면 엔진이 transcript 에서 원문을 되살린다. 재개 로더가 같은 API 메시지 id 를 지닌 행을 파일 전체에서 모으는데, 이 플러그인이 답한 compaction 은 원본과 같은 id 의 사본으로 저장되기 때문이다. 그래서 assistant 행과 tool_result 행이 바로 이어서 반복되어 온다(재개할 때마다 하나씩 더). 재개 재마스킹이 원문을 다시 가리고 `dropRepeatedRows` 가 반복을 걷는다. `remaskOnResume` 를 끄면 둘 다 하지 않으므로, 재개한 세션은 플러그인이 없을 때보다 커질 수 있다(bg 실측: 원문 문맥 69,913 토큰 → 재마스킹 없는 4번째 재개 82,300 토큰).
- spill 파일은 정리 기한(`spillRetentionDays`)까지 남는다. 정리는 꺼져 있어도 설정이 올바르면 `session.start` 에서 돈다 — 끄기 전에 만든 spill 도 기한이 지나면 지워진다. 한 번도 켜지 않은 설치에는 보관 위치가 없으니 지울 것도 없다. 플러그인을 지운 뒤에는 정리가 돌지 않으니 보관 위치를 직접 지운다.
- 정리는 읽을 수 있는 manifest(`<세션 id>.json`)가 옆에 있는 세션 폴더만 들여다본다. 그래서 `spillDir` 를 공유 폴더로 두어도 다른 파일은 지우지 않는다. manifest 를 끝내 쓰지 못한 세션 폴더의 잔여물(첫 spill 이 실패해 남은 임시 파일 정도)도 정리하지 않으니 필요하면 직접 지운다. 세션 폴더를 비우는 정리에서는 폴더 파일이 모두 지워진 뒤에야 manifest 와 로그를 지운다. `session.start` 의 정리는 시작한 그 세션의 폴더 · manifest 임시 파일 · manifest · 로그를 건너뛴다(같은 시작에 줄 선 재개 재마스킹이 그 파일을 다시 쓴다). 그 세션의 것은 다른 세션이 시작할 때 정리된다.

## 알려진 한계 (bg 실측 11-06 · 11-07)
- managed settings 가 있거나 Team · Enterprise 조직 계정이면 내장 `cc-plugin-sec-default` 가 앉아서 user tier 모듈의 `session.compact` 를 건너뛰게 한다(개인 Max 계정은 앉지 않는다 — debug.log `not seated: …`). 그런 환경에서 fz-compact 는 마스킹을 하지 못한다. 줄 선 compaction 은 `guard.sh` 가 막아 엔진 요약은 일어나지 않지만, 유휴 기간마다 skip 알림이 한 줄씩 남는다. 앉음을 미리 알아내 줄 세우기를 멈추는 장치는 없다(필요해지면 첫 차단을 표시 파일로 남겨 다음 줄 세우기를 거르는 방식). `sh` 가 없는 환경이나 managed 정책이 플러그인 훅을 막는 환경에서는 `guard.sh` 도 돌지 않는다.
- compaction 한 번마다 엔진이 `SessionStart:compact` 훅을 돌리고, 그 출력은 첨부 행으로 붙는다. 이 플러그인은 메시지를 요약하지 않으므로 앞선 첨부도 남는다. 첨부는 `session.compact` 가 받는 메시지에 없어서 걷을 수 없다. 측정한 환경에서는 compaction 마다 약 8.8K 자(약 4.5K 토큰)씩 늘었다. 늘어나는 양은 설치된 SessionStart 훅에 달렸다.
- 실행 중인 세션에서 플러그인이 다시 적재되면(설정 변경 · worker 재시작 · 활성화) 새 활성화는 앞선 턴을 모르는 채 `session.start` 를 받는다. manifest 에 항목이 있으면 재개 재마스킹을 줄 세운다. 그때 아직 마스킹되지 않은 결과는 컨텍스트가 `idleMinTokens` 이상이고 순절감 기준을 넘어야 마스킹되므로, 손해는 캐시 재작성 한 번으로 묶인다. 턴 진행 중에 다시 적재되면 새 활성화는 그 턴의 `turn.start` 를 보지 못해 `turnUnderWay` 보호가 없다.
- 재개 직후 사람 프롬프트가 큐에서 재마스킹보다 앞서면 재마스킹은 skip 되고, 다음 유휴 마스킹까지 원문과 반복 행이 문맥에 남는다. bg 재개에서는 재마스킹이 `session.start` 0.3초쯤 뒤에 돌아서 드물다.
- 마지막 활동이 유휴 임계값 안일 때 재개하면 남은 시간 뒤에 유휴 타이머를 다시 건다. 이 복원은 재개 판정 안에 있어서 `remaskOnResume` 가 꺼져 있으면 일어나지 않고, 그 세션은 다음 턴이 끝날 때까지 유휴 마스킹이 걸리지 않는다.
- 정리는 쓰기와 같은 줄에 서지 않는다. 그래서 다른 프로세스(다른 bg 세션)의 시작 정리가 이 세션이 막 다시 쓴 기한 넘은 spill 파일을 `stat` 재확인과 `rm` 사이에 지울 수 있다. 30일 넘게 쉰 세션을 재개하는 순간 다른 세션도 시작해야 닿는다.
- `claude --bg --resume <id>` 에 플래그를 하나라도 주면 새 세션 id 의 사본이 뜬다. manifest 는 세션 id 별이라 사본에서는 재개 재마스킹이 돌지 않는다. 플래그 없이 재개해야 같은 세션이 이어진다.
- 보호 구간(`keepRecentUserTurns`)을 셀 때 엔진이 넣은 user 행(백그라운드 작업 알림 · 로컬 명령 출력 · 스킬 본문)은 행 텍스트 머리의 마커 5종(`lib/policy.ts` 의 `ENGINE_ROW_PREFIXES`)으로 거른다. `$.session.messages()` 의 행에는 출처 표시가 없어서, 이 마커는 엔진 계약이 아니라 transcript 실측이다. 엔진이 형식을 바꾸거나 목록에 없는 행을 넣으면 그 행을 다시 사람 프롬프트로 세어 보호 구간이 좁아진다(더 일찍 마스킹). isMeta 행(로컬 명령 안내 · 스킬 본문)이 `$.session.messages()` 에 실제로 오는지는 확인하지 않았고, 온다고 보고 거른다.

## 검증
- `bash scripts/plugin_validate.sh mods/fz-compact` (fz 루트에서)
- `claude plugin test mods/fz-compact`
- `sh mods/fz-compact/tests/guard_test.sh`
