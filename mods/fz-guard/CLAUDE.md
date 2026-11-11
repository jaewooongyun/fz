# CLAUDE.md — fz-guard (fz 하위 플러그인)

> 개발용 문서다. 플러그인 루트의 CLAUDE.md 는 사용자 세션에 로드되지 않는다(`plugin_validate.sh` 가 이 경고를 카나리아로 쓴다 — 지우지 않는다).

fz 규칙 넷을 문장 대신 도구 호출 자리에서 강제한다. 모두 "규칙이 있는데 발화하지 않았다"(not-fired)로 레지스트리에 여러 번 오른 규칙이다.

| 규칙 | finding | 하는 일 |
|---|---|---|
| P4 | F-368 · F-384 · F-451 · F-119 · F-553 | `/fz` 뒤 Phase 4 승인 전 쓰기 · Workflow · 쓰는 Bash 를 deny, 승인 없이 끝나는 턴의 Stop 을 1회 block, 질문 없이 긴 답으로 끝낸 턴에 경고 |
| AG | F-058 · F-119 | fz 세션에서 native 채택 4종 밖 Agent · Task 를 ask |
| FR | F-518 · F-565 | 메모리에 fz 교훈만 쓰고 레지스트리 엔트리를 안 쓴 턴의 Stop 을 1회 block |
| GP | F-094 · F-297 | fz-review 턴이 GPT 리뷰 없이 끝나면 Stop 을 1회 block · fz 플러그인 파일에 옛 모델 호칭을 넣는 쓰기를 deny |

## 구조
- `hooks/hooks.json` — classic command 훅 넷(UserPromptSubmit · PreToolUse · PostToolUse · Stop) · 전부 `timeout` 10초. PreToolUse 는 Bash 도 받는다 — 쓰지도 GPT 리뷰를 부르지도 않는 Bash 는 상태를 열기 전에 빠져나간다(보호 경로 ask 는 상태 없이 그 앞에서 판정한다). PostToolUse 는 Read 도 받는다 — fz-review SKILL.md 가 아닌 Read 는 상태를 열기 전에 빠져나간다. 시간이 넘으면 호스트가 결정 없이 넘어간다(fail-open)
- `hooks/guard.py` — 판정 전부(표준 라이브러리만). matcher 는 거친 필터이고 판정은 guard.py 의 정확한 도구 이름 집합으로 한다
- `tests/fixtures/*.jsonl` — self-test 의 합성 transcript(entrypoint cli · sdk-cli · 없음)

## 설치 · 끄기 · 정리
- 설치는 사용자가 한다(자동 배선 없음). 한 세션만: `claude --plugin-dir <fz 저장소>/mods/fz-guard`. 늘: marketplace 의 `fz-guard` 를 설치한다
- 끄기(재시작 불필요 · 매 훅 실행에서 확인): env `FZ_GUARD_DISABLE=P4,AG,FR,GP` 또는 `all`, 또는 파일 `${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/disable`(내용 = 끌 규칙 목록 · 비우면 전부). 모르는 값(`1` · `true` 등)이나 읽지 못하는 플래그는 **전부 끄고** `fz-guard diag:` 를 낸다 — 탈출구가 조용히 실패하지 않게. ⛔ env 는 CLI 를 켤 때 값만 훅에 닿는다 — 세션 중 export 로는 끌 수 없다. 세션 중에는 파일 플래그를 쓴다
- 상태: `${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/<session_id>.json` · `.lock`. 플러그인 폴더 안을 가리키면 쓰지 않는다. 지워도 된다 — 지운 뒤 첫 입력 전까지는 STATE-INCOMPLETE 경고만 낸다. 입력마다 마지막 기록이 7일 지난 다른 세션의 상태 · 잠금을 지운다(F-564 · 한 번에 최대 200). 언인스톨해도 이 폴더는 남으니 손으로 지운다

## 판정
- **사건은 훅 입력에서 기록한다.** transcript 는 비동기로 기록돼 현재 사건이 없을 수 있다(공식 훅 문서). transcript 에서는 첫 줄들의 `entrypoint` 만 읽는다(접두 4 MiB · 400줄 하드 캡) — `cli` = interactive · `sdk-cli` = headless · 그 밖 = 불명
- **P4 창**: UserPromptSubmit 첫 토큰이 정확히 `/fz` · `/fz:fz`(또는 `<command-name>` 래퍼 안의 같은 값)이거나 Skill 이름이 `fz` · `fz:fz` 일 때 그 prompt_id 로 연다. 새 `/fz` 는 새 창이다 — 이전 창의 승인을 잇지 않는다. `/fz-code light` 같은 직접 호출은 명시 모드라 창을 열지 않는다. ⛔ 창은 **연 prompt 안에서만** 판정한다(deny · Stop 모두) — 승인 없이 접은 `/fz` 가 뒤의 평범한 요청이나 직접 호출까지 막지 않는다
- **승인**: PostToolUse(AskUserQuestion) 에서 header 가 `Phase 4` 인 질문의 답이 그 질문 선택지 라벨과 정확히 같고 커스텀 · 취소 · 거절 · 중단이 아닐 때. 답은 `tool_response` 의 `answers`(질문 본문 → 라벨)를 객체 · 직렬화 문자열 두 꼴로 읽고, 없으면 `tool_input.answers` 를 본다
  - 범위 질문(다른 header) · 커스텀 · 자유 입력 · 답 없음(거절)은 승인이 아니다 → deny 가 이어진다
  - 응답을 알아보지 못하면 `FZ-GUARD-WARN P4-UNDECIDED` 경고만 내고 막지 않는다(warn-allow). ⛔ 이것이 라이브에서 보이면 파서가 실제 모양을 못 읽은 것이다 — 고친다
- **막지 않는 경우**(P4 · AG · FR · GP 의 Stop 공통): `FZ_AUTONOMY=autonomous`(CLI 프로세스 env · `scripts/autonomy_decide.py` 와 같이 공백 · 대소문자 정규화) · headless · 레지스트리 `fz-findings/entries/` 쓰기(Phase 0~3 의 발견 등재 · F-518) · Phase 0 의 WORK_DIR 초기화 `{cwd}/{티켓 · NOTASK-YYYYMMDD}/index.md` 와 그 폴더의 `mkdir`(F-553 — `..` 를 접은 뒤 판정 · 폴더는 mkdir 대상으로만 면제한다 — 지우기는 면제가 아니다). 모드 불명은 `P4-UNDECIDED`, 이 입력의 시작을 못 본 상태(설치 전 시작한 세션 등)는 `STATE-INCOMPLETE` 경고만 낸다. 경고는 `systemMessage` 라 사용자에게 보인다
- **Stop**: `stop_hook_active` 면 통과. 차단은 (세션 · 규칙 · prompt_id) 지문당 1회
- **AG**: fz 세션 표지(첫 토큰 `/fz` · `/fz-*` · `/fz:*` · Skill `fz*`)는 세션 단위로 남는다. `subagent_type` 의 `:` 앞 접두를 벗겨 채택 4종과 대조한다(`--check-allowlist modules/native-agents.md` 가 표와 상수를 대조)
- **Bash 쓰기**(F-119 · F-368 · F-458): 계약은 「읽기 표 밖 이름 = 대상 미상 쓰기」다. 명령 자리는 공용 해석기(`hooks/shell_tokens.py` 의 `commands` — 예약어 · 루프 머리 · 대입 · 래퍼와 옵션 · 함수 본문 지연)가 정한다. `READ` 표(항상 읽기) · 쓰기 모드가 있는 명령의 읽기 꼴 판정(sed · awk · find · sort · uniq · git · gh · rg · date · base64) · `PLUGIN_READ`(승인 전 창에서 /fz 가 부르는 플러그인 스크립트)만 읽기다. 리다이렉트(`>` · `>>` · `&>` — fd 복제와 `/dev/null` 류 제외)와 tee · rm · touch · mkdir · cp · mv 는 대상을 뽑고, 그 밖 이름(인터프리터 포함)은 대상 미상 쓰기다. 대상을 아는 쓰기만 면제 판정(레지스트리 · WORK_DIR index.md · WORK_DIR 폴더 mkdir)을 받는다 — 명령 어딘가에서 폴더를 옮기면(cd · pushd · popd · `-C`) 상대 대상은 미상이다. 같은 쓰기 자리 판정(`write_sites`)을 플러그인의 `scripts/gate_stop_hook.py` 가 원장 소유 판정에 빌려 쓴다
- **승인 전 긴 답**(F-451): 창이 열린 prompt 에서 AskUserQuestion 을 한 번도 내지 않고 `last_assistant_message` 가 1500자 이상이면 Stop 에 `FZ-GUARD-WARN P4-LONG-ANSWER` 를 싣는다(차단은 P4 가 따로 한다 · 이어진 Stop 에서도 1회)
- **FR**: 같은 prompt_id 에서 PostToolUse(쓰기 성공)로 `.claude/projects/*/memory/*.md` 에 fz 교훈 토큰(`fz-` · `F-NNN`)이 든 쓰기가 있고 — 토큰은 마크다운 링크 · 백틱을 지운 본문에서 찾는다(F-565: 링크만 든 MEMORY.md 는 교훈이 아니다) — `fz-findings/entries/F-*.md` 성공 쓰기가 없을 때. 실패한 쓰기는 PostToolUseFailure 라 기록되지 않는다
- **GP**: `/fz-review` · `/fz:fz-review` · Skill `fz-review` 를 부른 prompt(또는 /fz 창이 연 prompt 에서 `skills/fz-review/SKILL.md` 를 Read 한 prompt — F-094 잔여) 가 `gpt-call.sh review`(Bash) 호출도, 답의 `[외부: GPT]` · `[GPT 미사용 — 사유]` 줄도 없이 끝나면 Stop 을 1회 막는다(interactive 한정 — 자율 · headless 는 면제). Write · Edit 류가 `.claude-plugin/plugin.json` 이름이 `fz` 인 폴더 아래 파일에 옛 모델 호칭을 넣으면 모드와 무관하게 deny 한다 — 판별식 · 제외 · 경계 · 보존 행은 그 저장소의 `scripts/check_gpt_surface.py` 를 불러 그대로 쓰고, 못 부르면 이 판정만 건너뛴다
- **보호 경로**(F-024): env `FZ_GUARD_PROTECTED`(os.pathsep 구분) · `<상태 폴더>/protected`(줄마다 경로) 가 있으면 그 아래에서 도는 Bash(cwd · `git -C` · 경로 인자 — 앞선 cd · pushd 를 차례로 반영한 위치로도 푼다)와 대상을 모르는 Bash(못 읽는 명령 · 확장이 든 cd · pushd · git -C 대상)를 ask 한다(사유 표시 · P4 deny 를 덮지 않는다). 기본은 비어 있어 아무 일도 없다 · `FZ_GUARD_DISABLE=all` 이면 함께 꺼진다
- 병렬 도구 호출의 PostToolUse 는 동시에 돈다 — 세션별 `flock` 으로 읽기 · 병합 · 판정 · 저장을 직렬화하고 mkstemp + `os.replace` 로 바꾼다. 잠금을 3초(`FZ_GUARD_LOCK_TIMEOUT`) 안에 못 잡으면 진단만 내고 통과한다

## 한계
- 읽기 표 밖 이름은 읽기만 해도 막힌다 — 승인 전 창에서 읽기용 `python3 -c` · `bash 스크립트` · `xcrun` 도 막힌다. 쓰기 꼴을 나열하던 차단 목록은 라운드마다 새 꼴이 샜다(F-458 · r5) — 과차단 쪽을 골랐다. 실측(최근 transcript 40개의 승인 전 창 Bash 3785건): 옛 판정보다 820건이 더 막히고(python3 448 · bash 89 · claude 58 · mkdir 57 · xcrun 52 …) 풀린 것은 0건이다. 본문이 시키는 필수 명령 단독 꼴은 막히지 않는다
- 펼쳐지는 인자(`"$W/a"` · `$SHA`)는 값으로 본다 — 펼친 값이 옵션이 되는 꼴(`X=--output=f; git diff $X`)은 보지 않는다(find · sort · git · rg · gh 에서 따옴표 없는 펼침까지 미상으로 두면 승인 전 창 3785건 중 막힘이 1746 → 1995~2106 으로 는다 — 실측). 프로그램 · 하위 명령 자리의 펼침(`awk "$P"` · `git "$SUB"`)과 따옴표 없이 갈라지는 uniq 피연산자는 미상이다. 읽기 꼴 판정은 허용 목록이라 표 밖 옵션은 미상이다(awk 프로그램의 정규식 안 `|` 도 파이프로 본다)
- 토크나이저가 bash 와 같게 읽는다고 보증하지 못하는 꼴(산술 치환 안 명령 치환 · `case` 를 품은 치환 · 배열 대입 · 이스케이프가 든 `$'…'` · `$"…"` 등 — 정본 `scripts/shell_tokens.py` 의 `OUTSIDE`)은 Unknown 이다. Unknown 은 대상 미상 쓰기로 읽으므로 P4 창 안에서는 읽기 명령이어도 막힌다(과차단 · 놓침 0 쪽으로 기운다)
- GPT 리뷰 증거(GP)는 명령 이름이 따옴표 밖에서 펼쳐져도(`$P/scripts/gpt-call.sh review`) basename 으로 호출을 인정한다 — 값에 공백이 있으면 셸이 필드를 나눠 다른 명령을 실행한다(`X='printf ignored'; $X/gpt-call.sh review` · r6 ISSUE-011). 가장 좁은 규칙(이름의 따옴표 밖 펼침 거절)도 실제 호출을 막는다 — 실측(transcript 117개 · 판정기가 인정한 review 호출 122건): 따옴표 밖 펼침 35 · 큰따옴표로 감싼 펼침 59 · 펼침 없음 28
- 오라클 경계(F-582): 계약(렉싱 · 명령 자리 · 읽기 표 · 대상 · 원장 소유 · GPT 호출 증거 · JS 렉심)은 bash · JS 의 동작 전체를 말하지만 오라클은 표본이다 — 토크나이저 규칙마다 셀 하나(`--list-rules` · 제거 probe)와 지적마다 처분 셀. 표본 밖 입력이 실제 동작과 갈리는 꼴은 적대 검토가 찾을 때마다 처분 셀 또는 이 절의 한계로 닫는다
- 같은 이름 함수 면제는 정의 순서를 보지 않는다 — 정의보다 앞선 맨 이름 호출(`touch x; touch() { :; }`)도 함수로 읽는다(만든 꼴 · r6 ISSUE-002 의 남은 꼴). `command` · 래퍼 · 경로로 부른 호출은 외부 명령으로 판정한다
- `/fz` 파이프라인 안에서 SKILL.md 를 읽어 도는 fz-review 는 표지가 없어 GP Stop 이 보지 못한다
- Phase 0 은 WORK_DIR 폴더 mkdir 과 `index.md` 만 허용한다 — 다른 산출물은 승인 뒤에 쓴다
- Workflow 스크립트 안 `agent()` 스폰이 PreToolUse(Agent) 를 발화하는지는 라이브 관측 대상이다(발화하면 `fz:*` 타입이 채택 목록 밖이라 ask 가 뜬다)
- 조직 managed settings 가 사용자 tier 하위 플러그인 훅을 건너뛰면 fz-guard 는 없는 것과 같다 — 라이브에서 훅 발화부터 확인한다

## 시험
- `python3 hooks/guard.py --self-test` — 합성 입력 109 케이스(`PASS <case>`) · HOME · FZ_RUN_STATE 를 임시 폴더로 새로 짓는다
- `python3 hooks/guard.py --check-allowlist ../../modules/native-agents.md`
- `python3 hooks/guard.py --make-synthetic BYTES OUT --with-marker|--no-marker` · `--bench OUT` — 큰 transcript 에서 entrypoint 판정 소요
- health-check 5.2 가 validate · self-test · allowlist 를 돈다
