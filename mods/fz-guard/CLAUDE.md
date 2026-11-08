# CLAUDE.md — fz-guard (fz 하위 플러그인)

> 개발용 문서다. 플러그인 루트의 CLAUDE.md 는 사용자 세션에 로드되지 않는다(`plugin_validate.sh` 가 이 경고를 카나리아로 쓴다 — 지우지 않는다).

fz 규칙 셋을 문장 대신 도구 호출 자리에서 강제한다. 셋 다 "규칙이 있는데 발화하지 않았다"(not-fired)로 레지스트리에 여러 번 오른 규칙이다.

| 규칙 | finding | 하는 일 |
|---|---|---|
| P4 | F-368 · F-384 · F-451 | `/fz` 뒤 Phase 4 승인 전 쓰기 · Workflow 를 deny, 승인 없이 끝나는 턴의 Stop 을 1회 block |
| AG | F-058 · F-119 | fz 세션에서 native 채택 4종 밖 Agent · Task 를 ask |
| FR | F-518 | 메모리에 fz 교훈만 쓰고 레지스트리 엔트리를 안 쓴 턴의 Stop 을 1회 block |

## 구조
- `hooks/hooks.json` — classic command 훅 넷(UserPromptSubmit · PreToolUse · PostToolUse · Stop) · 전부 `timeout` 10초. 시간이 넘으면 호스트가 결정 없이 넘어간다(fail-open)
- `hooks/guard.py` — 판정 전부(표준 라이브러리만). matcher 는 거친 필터이고 판정은 guard.py 의 정확한 도구 이름 집합으로 한다
- `tests/fixtures/*.jsonl` — self-test 의 합성 transcript(entrypoint cli · sdk-cli · 없음)

## 설치 · 끄기 · 정리
- 설치는 사용자가 한다(자동 배선 없음). 한 세션만: `claude --plugin-dir <fz 저장소>/mods/fz-guard`. 늘: marketplace 의 `fz-guard` 를 설치한다
- 끄기(재시작 불필요 · 매 훅 실행에서 확인): env `FZ_GUARD_DISABLE=P4,AG,FR` 또는 `all`, 또는 파일 `${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/disable`(내용 = 끌 규칙 목록 · 비우면 전부). 모르는 값(`1` · `true` 등)이나 읽지 못하는 플래그는 **전부 끄고** `fz-guard diag:` 를 낸다 — 탈출구가 조용히 실패하지 않게. ⛔ env 는 CLI 를 켤 때 값만 훅에 닿는다 — 세션 중 export 로는 끌 수 없다. 세션 중에는 파일 플래그를 쓴다
- 상태: `${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/<session_id>.json` · `.lock`. 플러그인 폴더 안을 가리키면 쓰지 않는다. 지워도 된다 — 지운 뒤 첫 입력 전까지는 STATE-INCOMPLETE 경고만 낸다. 언인스톨해도 이 폴더는 남으니 손으로 지운다

## 판정
- **사건은 훅 입력에서 기록한다.** transcript 는 비동기로 기록돼 현재 사건이 없을 수 있다(공식 훅 문서). transcript 에서는 첫 줄들의 `entrypoint` 만 읽는다(접두 4 MiB · 400줄 하드 캡) — `cli` = interactive · `sdk-cli` = headless · 그 밖 = 불명
- **P4 창**: UserPromptSubmit 첫 토큰이 정확히 `/fz` · `/fz:fz`(또는 `<command-name>` 래퍼 안의 같은 값)이거나 Skill 이름이 `fz` · `fz:fz` 일 때 그 prompt_id 로 연다. 새 `/fz` 는 새 창이다 — 이전 창의 승인을 잇지 않는다. `/fz-code light` 같은 직접 호출은 명시 모드라 창을 열지 않는다. ⛔ 창은 **연 prompt 안에서만** 판정한다(deny · Stop 모두) — 승인 없이 접은 `/fz` 가 뒤의 평범한 요청이나 직접 호출까지 막지 않는다
- **승인**: PostToolUse(AskUserQuestion) 에서 header 가 `Phase 4` 인 질문의 답이 그 질문 선택지 라벨과 정확히 같고 커스텀 · 취소 · 거절 · 중단이 아닐 때. 답은 `tool_response` 의 `answers`(질문 본문 → 라벨)를 객체 · 직렬화 문자열 두 꼴로 읽고, 없으면 `tool_input.answers` 를 본다
  - 범위 질문(다른 header) · 커스텀 · 자유 입력 · 답 없음(거절)은 승인이 아니다 → deny 가 이어진다
  - 응답을 알아보지 못하면 `FZ-GUARD-WARN P4-UNDECIDED` 경고만 내고 막지 않는다(warn-allow). ⛔ 이것이 라이브에서 보이면 파서가 실제 모양을 못 읽은 것이다 — 고친다
- **막지 않는 경우**(P4 · AG · FR 공통): `FZ_AUTONOMY=autonomous`(CLI 프로세스 env · `scripts/autonomy_decide.py` 와 같이 공백 · 대소문자 정규화) · headless · 레지스트리 `fz-findings/entries/` 쓰기(Phase 0~3 의 발견 등재 · F-518). 모드 불명은 `P4-UNDECIDED`, 이 입력의 시작을 못 본 상태(설치 전 시작한 세션 등)는 `STATE-INCOMPLETE` 경고만 낸다. 경고는 `systemMessage` 라 사용자에게 보인다
- **Stop**: `stop_hook_active` 면 통과. 차단은 (세션 · 규칙 · prompt_id) 지문당 1회
- **AG**: fz 세션 표지(첫 토큰 `/fz` · `/fz-*` · `/fz:*` · Skill `fz*`)는 세션 단위로 남는다. `subagent_type` 의 `:` 앞 접두를 벗겨 채택 4종과 대조한다(`--check-allowlist modules/native-agents.md` 가 표와 상수를 대조)
- **FR**: 같은 prompt_id 에서 PostToolUse(쓰기 성공)로 `.claude/projects/*/memory/*.md` 에 fz 교훈 토큰(`fz-` · `F-NNN` · `fz-findings`)이 든 쓰기가 있고, `fz-findings/entries/F-*.md` 성공 쓰기가 없을 때. 실패한 쓰기는 PostToolUseFailure 라 기록되지 않는다
- 병렬 도구 호출의 PostToolUse 는 동시에 돈다 — 세션별 `flock` 으로 읽기 · 병합 · 판정 · 저장을 직렬화하고 mkstemp + `os.replace` 로 바꾼다. 잠금을 3초(`FZ_GUARD_LOCK_TIMEOUT`) 안에 못 잡으면 진단만 내고 통과한다

## 한계
- Bash 로 쓰는 경로(리다이렉트 · `sed -i` 등)는 보지 않는다 — Phase 0~3 의 읽기 탐색까지 막게 되기 때문이다(로드맵 R4)
- `/fz` Phase 0 의 WORK_DIR 산출물 Write 도 승인 전이면 deny 된다 — Phase 4 를 먼저 묻거나 승인 뒤에 쓴다
- Workflow 스크립트 안 `agent()` 스폰이 PreToolUse(Agent) 를 발화하는지는 라이브 관측 대상이다(발화하면 `fz:*` 타입이 채택 목록 밖이라 ask 가 뜬다)
- 조직 managed settings 가 사용자 tier 하위 플러그인 훅을 건너뛰면 fz-guard 는 없는 것과 같다 — 라이브에서 훅 발화부터 확인한다

## 시험
- `python3 hooks/guard.py --self-test` — 합성 입력 63 케이스(`PASS <case>`) · HOME · FZ_RUN_STATE 를 임시 폴더로 새로 짓는다
- `python3 hooks/guard.py --check-allowlist ../../modules/native-agents.md`
- `python3 hooks/guard.py --make-synthetic BYTES OUT --with-marker|--no-marker` · `--bench OUT` — 큰 transcript 에서 entrypoint 판정 소요
- health-check 5.2 가 validate · self-test · allowlist 를 돈다
