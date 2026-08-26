# Completion Gates (실행 가능한 완료 원장)

> 완료 판정을 모델의 선언이 아니라 **프로세스 exit code**로 옮기는 모듈.
> fz는 완료 강제 규칙을 산문으로 갖고 있으나(`cross-validation.md` Coverage Gate 등) 그 규칙이 지켜졌는지 판정하는 실행 코드가 없었다 — 모델이 "통과"라고 쓰면 그것이 통과였다.
> 근거: `feedback_fail_open_safety_judgment` "산문 규칙은 가드 아님" · Coverage Gate 근거 기록 "95개 중 25개만 읽고 완료 보고"(2026-04-16) · "잘린 출력 '2곳뿐' 단정 4턴 생존, 실제 11곳"(2026-06-12).

## 목차

- [Module Role](#module-role)
- [원장 위치와 수명](#원장-위치와-수명)
- [원장 문법 (요약)](#원장-문법-요약)
- [판정 계약](#판정-계약)
- [스킬 배선 5지점](#스킬-배선-5지점)
- [이탈 경로](#이탈-경로)
- [승인 계약 (APPROVED_ORACLE_HASH)](#승인-계약-approved_oracle_hash)
- [관측 (FZ_GATES_TRACE)](#관측-fz_gates_trace)
- [참조 스킬](#참조-스킬)
- [설계 원칙](#설계-원칙)

---

## Module Role

- **Role**: **Producer** (게이트 수명주기 + 스킬 배선 정책)
- **Consumed by**: `skills/fz-plan/SKILL.md`(생성) · `skills/fz-code/SKILL.md`(Step 판정) · `skills/fz-review/SKILL.md`(재검증)
- **Direction**: producer → consumer
- **책임 경계** (⛔ 3분 — 같은 사실을 두 곳에 두지 않는다):

| 대상 | SSOT | 담는 것 |
|------|------|--------|
| 실행 문법·exit·한계값 | `scripts/gate_check.py --help` + 모듈 docstring | 파싱 규칙, exit code 의미, timeout·출력 상한 값 |
| 수명주기·배선 | **본 모듈** | STATE 전이, 어느 스킬이 언제 무엇을 하는가 |
| 원장 경로 | `modules/context-artifacts.md` | `{WORK_DIR}/gates/` 위치와 backlink |

> ⛔ **호출은 절대 경로로** — `python3 "${FZ_PLUGIN_ROOT}/scripts/gate_check.py"`. `FZ_PLUGIN_ROOT`는 `scripts/resolve-plugin-root.sh`로 해석한다. 상대 경로는 설치된 플러그인에서 대상 레포에 파일이 없어 exit 2(인프라 통과)로 떨어지고 **강제력이 조용히 사라진다**.

> 아래 [원장 문법 (요약)](#원장-문법-요약)은 **참조 편의용 요약이며 권위가 아니다.** 문법이 어긋나면 `gate_check.py`가 정답이다.

## 원장 위치와 수명

```
{WORK_DIR}/gates/
├── plan.md              canonical (fz-plan이 생성, Lead 소유)
└── shards/<worker>.md   BATCH worker별 (append-only, 2차 계층)
```

WORK_DIR 결정은 `modules/context-artifacts.md` Work Dir Resolution을 따른다. **Serena fallback(disk WORK_DIR 없음)은 명시적 비지원** — 원장을 만들지 않는다.

### STATE 3상태

| 전이 | 주체 | 조건 |
|------|------|------|
| (생성) → `active` | `/fz-plan` | 원장 생성 |
| `active` → `ready_for_review` | `/fz-code` | 전 Step 게이트 충족 |
| `ready_for_review` → `closed` | `/fz-review` | reverify 통과 + guardian `regressed` 0 |
| 임의 → `closed` | 사용자 | 전량 `ABANDON:` |

⛔ **`ready_for_review`도 미완료다.** fz-code가 끝났다고 원장을 닫으면 fz-review의 재검증이 강등을 수행할 수 없다 — 중간 상태가 그 구멍을 막는다.

⛔ **kill-switch는 영속 상태를 변경하지 않는다.** `FZ_GATES_OFF=1`은 세션 단위 bypass이므로 STATE를 건드리면 후속 세션까지 지속된다.

## 원장 문법 (요약)

```markdown
# Gates: 시청내역 서버 재정비
ROOT: {WORK_DIR}
STATE: active
Scope: 시청내역 API를 v4로 이관하고 기존 소비자 3곳을 무중단 전환한다

- [x] G1: 빌드 성공
  CHECK: xcodebuild -workspace app.xcworkspace -scheme app build
  EXPECT: BUILD SUCCEEDED
  CWD: {GIT_ROOT}
  APPROVED_ORACLE_HASH: 3f9a1c2b8e04
  EVIDENCE: sig=7b2e91c4f0a3; exit=0; cwd={GIT_ROOT}; env=a41c9e02b7d5; output=BUILD SUCCEEDED

- [ ] G2: 디자인 QA 반영 확인
  MANUAL: 시뮬레이터에서 셀 마진이 48pt인지 육안 확인
  CRITERION_HASH: 9c1e7f2a4b8d
  EVIDENCE: pending

ABANDON: G3 서버 API 미배포 — TVG-9999로 핸드오프
```

- `ROOT:`는 이 원장이 속한 WORK_DIR의 **realpath 절대경로**다. 발견 키가 아니라 **검증 키**다(발견은 세션 바인딩 — [스킬 배선 4지점](#스킬-배선-4지점) 참조).
- 실행 게이트는 `CHECK:`와 `EXPECT:` **둘 다** 갖는다. 수동 게이트는 `MANUAL:`만 갖는다. 하나만 있으면 오류다.
- `EXPECT:`는 **부분 문자열 매칭**이다. 정규식을 지원하지 않는다 — 이유는 [설계 원칙](#설계-원칙) 참조.
- `CWD:`는 절대경로만 허용한다. `..` 포함 시 오류다.
- `EVIDENCE:`의 `sig=`는 **체커가 발급한 서명**이다. `oracle_hash + exit + output`에 묶여 있어 손으로 쓴 증거는 met 이 되지 않는다.
  ⛔ **암호학적 위조 방지가 아니다** — 알고리즘이 공개돼 있어 작정하면 재계산할 수 있다. 이것이 막는 것은 *우연한* false-green(CHECK 를 안 돌리고 통과 텍스트만 쓰는 경로)이다.
- `ABANDON:`도 같은 성격이다. 누구나 append 할 수 있으므로 **위조 방지가 아니라 표면화 장치**다 — 있으면 최종 보고에 반드시 찍힌다.

### 파서 fail-closed

| 형태 | 판정 | 이유 |
|---|---|---|
| 헤더 중복 선언 (`STATE:` 두 번) | exit 3 | ⛔ 마지막이 이기면 `STATE: closed` 를 한 줄 append 해서 원장을 **통째로 no-op** 으로 만들 수 있다. `ABANDON:` 처럼 흔적이 남는 이탈로가 아니라 조용한 무력화다 |
| 헤더 중복 (`ROOT:` 두 번) | exit 3 | 실행 디렉토리가 바뀐다. ROOT 를 상위로 두면 소유 검사도 통과한다 |
| 게이트 밖 들여쓰기 속성 | exit 3 | 오타로 게이트 줄이 빠지면 그 CHECK 가 통째로 사라지는데, 게이트 수 감소를 알아챌 오라클이 없다 |
| 게이트 뒤 헤더 재선언 | 무시 | 헤더는 첫 게이트 앞에서만 읽는다 (설계) |

## 판정 계약

실행 게이트는 **프로세스 exit 0 그리고 `EXPECT:` 매치**일 때만 통과한다. 하나만 만족하면 미통과다.

> exit 0만 보면 "실행됐다"만 증명한다. `EXPECT:`만 보면 실패한 프로세스가 에러 텍스트에 성공 토큰을 담고 있을 때 통과한다.

### exit code 4상태

| exit | 의미 | Stop hook 동작 | 근거 |
|-----:|------|---------------|------|
| 0 | satisfied | 통과 | 게이트 충족 |
| 1 | unmet | **차단** | 판정 결과. timeout·출력 초과 포함 |
| 3 | invalid-ledger | **차단** | fz가 만든 원장의 계약 위반. 평가 불가는 통과가 아니다 |
| 2 | infrastructure | 통과 + 진단 | python 부재·스크립트 손상·파일시스템 오류(`OSError`). 세션 감금이 게이트 누락보다 나쁘다 |

⛔ **판정의 fail-open은 금지, 인프라 부재의 fail-open은 허용.** 이 구분이 exit 1·3과 exit 2를 가른다. `scripts/lint_contracts.py`가 이미 같은 3분 구조를 쓰고(`2 = configuration/parse error ⛔ PASS도 SKIP도 아니다`) 게이트는 파싱 오류를 차단 쪽에 두므로 3을 추가한다.

⛔ **timeout·출력 초과는 exit 1(미충족)이다.** 인프라가 아니라 판정이다 — 시간이 없었다는 것은 통과가 아니다.

### 실행 환경

| 축 | 규칙 | 이유 |
|---|---|---|
| stdin | `DEVNULL`로 닫는다 | 미지정이면 터미널·상위 파이프를 **상속**해 CHECK가 입력을 기다리면 게이트당 기본 120초를 잡아먹는다 |
| 프로세스 그룹 | `start_new_session=True` + 스폰 직후 pgid 확보 | 셸이 먼저 죽으면 `getpgid`가 실패해 손자를 못 죽인다 |
| 손자 잔존 | 저자가 선언한 `TIMEOUT`까지 기다리고, EXPECT가 매칭되면 즉시 끊는다 | 고정 grace는 정상적인 지연 출력을 자르고, 무한 대기는 orphan daemon에 매달린다. 구분 기준은 **더 기다려서 판정이 바뀔 수 있는가** 하나다 |
| 출력 수집 | `read1(n)` 으로 지금 있는 만큼만 읽는다 | `read(n)` 은 **n 바이트가 모이거나 EOF 까지 블록**한다 — 짧은 출력이 프로세스 종료 시 한꺼번에 도착해 EXPECT 조기 매칭도 출력 상한 감지도 실행 중에 발화하지 못했다 |
| 강제 종료 | 증거에 `killed=descendant`를 남긴다. **판정은 뒤집지 않는다** | CHECK 계약은 exit + EXPECT다. 서버를 띄우는 정당한 CHECK를 실패시키면 안 되지만, 프로세스 누수는 저자가 알아채야 한다 |

### `EXPECT:` 문법

부분 문자열 매칭이다. 정규식을 지원하지 않는다 — Python `re`에 타임아웃이 없어 백트래킹을 막을 수 없다.

| 형태 | 판정 | 이유 |
|---|---|---|
| `/tmp/result` | 리터럴 (통과) | 경로다. 닫는 슬래시가 없다 |
| `/var/log/` | 리터럴 + 경고 | 디렉토리 경로와 무플래그 정규식이 **같은 모양**이다. 판정 근거가 없다 |
| `/he(l+)o/i` | exit 3 | 플래그 문자만 뒤따라 정규식 의도가 분명하다 |

⛔ **알려진 오거부** — `/tmp/i` 처럼 마지막 구성요소가 플래그 문자만인 정당한 경로는 거부된다. `CWD:` 를 쓰거나 `EXPECT` 를 더 긴 문맥으로 잡는다. 완전한 경로/정규식 판별자는 존재하지 않으므로, 본문에 메타문자가 있으면 **경고**만 낸다(`/foo/g`·`/^ok$/`).

⛔ 애매하면 **거부가 아니라 리터럴 + 경고**다. 두 실패의 방향이 다르다 — 정규식을 리터럴로 취급하면 게이트가 빨갛게 실패해 저자가 알아채지만, 경로를 정규식으로 오인해 거부하면 정당한 게이트가 원장 검증 단계에서 통째로 막힌다. 드러나는 실패 쪽으로 기운다.

`EXPECT:`는 원장 한 줄이라 개행을 담을 수 없다. 그래서 stdout·stderr를 이어 붙일 때 경계에서 needle이 합성되거나 잘리지 않는다.

### 증거 레코드

`sig=…; exit=…; cwd=…; env=…; output=…` 형태다. `cwd` 와 `output` 은 `%`→`%25`, `;`→`%3B` 로 escape 한다.

`env=` 는 실행 환경 지문(`SHELL` + `PATH`)이고 **서명에 묶인다.** 재계산은 현재 환경이 아니라 **기록된** 값을 쓴다 — 현재 환경을 쓰면 통과한 게이트가 다른 세션에서 unmet 으로 읽힌다(실측).

⛔ 정상 출력이 `;` 를 담으면(예: `echo "done; cleanup=ok"`) 파싱이 잘려 재계산 서명이 어긋나고 **통과한 게이트가 나중에 unmet 으로 읽힌다**(fail-red, 2026-08-25 실측). 서명은 escape 된 값 위에서 계산하므로 양쪽이 같은 문자열을 본다.

## writeback CAS 범위

**대상 게이트 블록**만 본다 — 그 게이트의 `- [ ] id: 제목` 줄, 속성 전부, 그 게이트를 지목한 `ABANDON:`.

⛔ 전체 파일 해시를 쓰면 CHECK가 도는 동안 사용자가 **무관한 형제 게이트**를 편집하면 writeback이 exit 3으로 죽는다. 실행 결과를 잃는 것은 게이트가 만들려던 것과 반대다.

제목을 범위에 넣는 이유 — 제목이 바뀌면 **같은 증거가 다른 주장에 붙는다**. `oracle_hash`에는 제목이 없지만 게이트 판정의 `measurement_fit`은 CHECK를 제목 대비 평가한다.

⛔ **이 좁히기는 교환이다 — 단일 writer를 가정한다.** 전체 파일 CAS는 위양성(형제 편집)을 만드는 대신 *다른* 것을 막고 있었다: 게이트 A와 B의 writeback이 겹치면 `write_atomic`이 파일 전체를 replace하므로 나중 쓰기가 앞 쓰기를 **덮는다**(lost update). 블록 CAS는 그 충돌을 보지 못한다.

설계된 흐름에서는 창이 없다 — `evaluate()`는 한 프로세스의 순차 루프이고 배선 1~3은 Lead가 차례로 호출한다. 창이 열리는 것은 **Stop hook이 Lead 호출과 동시에 도는 경우**뿐이므로, 파일 lock은 2차 계층의 선행 조건으로 둔다.

lock을 지금 넣지 않는 이유는 설계가 필요하기 때문이다. `write_atomic`이 `os.replace`로 inode를 바꾸므로 대상 파일에 `flock`을 걸면 replace 후 lock이 옛 inode에 남는다 — 별도 lock 파일이 필요하고, 그 수명·정리·stale 처리를 정해야 한다. 2차 계층에서 hook과 함께 정한다.

## 스킬 배선 5지점

### 1. fz-plan — 생성

Phase 1 산출 시 `steps[].verify`를 읽어 `{WORK_DIR}/gates/plan.draft.md`를 만든다. `verify.kind`가 `command`면 `CHECK:`/`EXPECT:`, `manual`이면 `MANUAL:`+`CRITERION_HASH:`.

Phase 2의 `verify-gates`가 **게이트마다 판정 1개**를 낸다 — "이 `CHECK:`가 제목이 말하는 것을 측정하는가" + noninteractive·rerunnable·side-effect·determinism. Phase 3에서 판정을 반영해 `plan.md`로 확정한다.

⛔ **`verify`를 대체하지 않고 추가한다.** `codex_gate_verdict_schema`에는 `issues`·`verdict`가 없어서, 스키마를 바꿔치기하면 fz-plan의 Issue Tracker 기록·scope challenge·Gate 2 승인 입력이 사라진다. 두 호출은 관심사가 다르다 — 계획이 옳은가(`verify`)와 게이트가 그 계획을 측정하는가(`verify-gates`).

⛔ **스키마 선택만으로는 N/N이 보장되지 않는다.** 스키마는 `gates: []`(빈 배열)·중복 id·원장에 없는 id·거짓 `summary` 합계를 전부 통과시킨다.

대조는 **눈으로 하지 않는다** — `--verdict-check <응답.json>`이 게이트 수·id 집합·중복·summary 합계를 판정한다. exit 1이면 재호출 1회 후 **미판정으로 기록**한다. 이 계층이 없애려는 것이 산문 대조이므로 대조 자체를 산문에 두지 않는다.

⛔ 개수만 세면 안 되는 이유 — 중복 id가 누락을 가린다. `G1` 두 번 + `G3` 없음은 3개로 보인다.

⛔ **draft가 Phase 2보다 먼저다.** Phase 2가 Phase 3보다 앞이므로, 원장을 Phase 3에서 만들면 평가자가 볼 `CHECK:`가 없다.

ℹ️ **세션 바인딩은 만들지 않았다.** Stop hook 입력에 `session_id`가 오므로 `~/.fz/sessions/<id>.json` 바인딩이 가능하지만, 그러면 **쓰는 쪽 배선**이 필요하고 그 배선이 빠지면 hook이 원장을 못 찾아 조용히 무력화된다. `cwd` 하위 glob은 배선이 0이고 여러 원장을 전부 본다 — 배선 4 참조.

light 모드는 원장을 만들지 않는다.

### 2. fz-code — Step 판정

Step 완료 선언 전 `--only {StepID}`로 **해당 Step 게이트만** 실행한다. 선택자 없이 전체를 돌리면 미래 Step 게이트가 실패해 첫 Step에서 영구 정지한다. 실패면 다음 Step으로 진행하지 않는다. 전 Step 충족 시 `--set-state ready_for_review`.

⛔ **전진은 인접 단계만** — `active → closed` 직행은 fz-review 재검증을 통째로 건너뛰므로 거부된다.

원장 부재·`STATE: closed`면 no-op이다. `ROOT:`는 **realpath 정규화 후 원장이 그 하위인지**로 판정한다 — 상대 경로·`..`·존재하지 않는 디렉토리·타 디렉토리 ROOT는 exit 3이다.

⛔ realpath **일치**를 요구하지는 않는다. macOS의 `/var → /private/var`처럼 정상 경로도 심볼릭을 거치므로, 정규형을 강요하면 정당한 원장이 거부된다(fixture 21건이 이것으로 깨졌다). 필요한 것은 정규형이 아니라 소유 판정이다.

### 3. fz-review — 재검증

Lead가 Workflow 반환을 통합할 때 워커 자기보고 대신 게이트를 재실행한다(`--reverify`). 통과 못 하면 `- [x]` → `- [ ]` + `EVIDENCE: pending`으로 **강등**한다.

`/fz-codex validate`(fz-guardian)가 각 게이트를 `resolved / partially_resolved / unresolved / regressed` 4축으로 분류한다. `regressed`가 0이 아니면 통합을 차단한다.

### 4. Stop hook — 차단 (2차 계층, 사용자 설치)

`scripts/gate_stop_hook.py`. 세션 종료 시 `cwd` 하위 확정 원장을 찾아 미충족이면 종료를 막는다. **1차 배선 1~3은 SKILL.md 산문이라 Lead가 건너뛰어도 신호가 없다 — 그 재귀를 끊는 것은 이 hook 하나뿐이다.**

⛔ **자동 배선하지 않는다.** `examples/hooks.json.example`에 템플릿만 두고 사용자가 `.claude/settings.json`의 `hooks.Stop` **배열에 추가**한다 (통째 복사하면 기존 항목이 사라진다) — `modules/governance.md` "Claude는 훅 설치·설정 변경을 명시 합의 없이 지시·실행하지 않는다"와 같은 파일 `_note`의 "자동 배선 금지". 따라서 **기계적 차단은 설치한 머신에만 존재한다.** 원장·판정기·1~3번 배선은 어디서나 동작한다.

#### 차단 계약 (실측 출처)

`~/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/hook-development/` — 공식 plugin-dev 스킬. `references/advanced.md:262`의 command 타입 예시.

```
입력 (stdin JSON): {"session_id":…, "transcript_path":…, "cwd":…, "hook_event_name":"Stop"}
차단:              stderr ← {"decision":"block","reason":"…"}  +  exit 2
```

⛔ `hookSpecificOutput.decision` 도 `{"continue": false}` 도 아니다 — **top-level `decision`** 이다. 세 후보 중 어느 것인지 문서로 확정했으므로 live 세션 probe가 필요하지 않았다.

#### 설계 결정 3가지

| 결정 | 이유 |
|---|---|
| 원장 발견 = `cwd` 하위 glob (깊이 0~3) | `session_id`가 입력에 오므로 세션 바인딩도 가능하지만 **쓰는 쪽 배선**이 필요하고, 그 배선이 빠지면 hook이 원장을 못 찾아 조용히 무력화된다. glob은 배선이 0이고 여러 원장을 전부 보므로 다른 미완 작업을 놓치지 않는다 |
| 판정 = `--status` (CHECK 재실행 없음) | 재실행은 게이트당 기본 120초여서 hook에 부적합하다. 기록된 증거는 서명으로 oracle에 묶여 있어 "안 돌리고 통과 텍스트만 쓴" 경로를 이미 막는다 |
| 전면 fail-open | exit 계약의 "세션 감금이 게이트 누락보다 나쁘다"가 가장 날카롭게 적용되는 자리다 — 여기서 실수하면 사용자가 세션을 끝낼 수 없다 |

⛔ **무한 루프 방어.** Stop을 막으면 Claude가 계속하고 다시 Stop에 도달한다. 원장 상태가 그대로면 같은 이유로 또 막혀 세션이 끝나지 않는다. 같은 상태(원장 해시)로 **2회**까지만 막고 이후 통과 + 진단한다. 상태를 쓸 수 없으면(디스크 오류) 즉시 통과 — 방어 없이 막으면 무한 block이 된다.

#### ⛔ 발견 한계와 탈출로

깊이는 0~3이다. `*/gates/plan.md` 하나만 보면 `{CWD}/gates/plan.md`(깊이 1)·`{CWD}/a/b/gates/plan.md`(깊이 3)를 놓치고 **조용히 통과한다** — 실측에서 4종 중 1종만 발견됐다.

깊이 4 이상, 그리고 `cwd` **밖**은 어떤 glob으로도 찾지 못한다. 워크트리에서 작업하고 원장이 리포 루트에 있는 경우가 그렇다 — hook은 `cwd`만 받으므로 설계 한계다. `FZ_GATES_LEDGER`(경로 목록, `os.pathsep` 구분)로 명시 지정한다.

⛔ **"찾지 못함"은 조용하지 않다.** `gates/` 디렉토리가 아예 없으면 게이트 미사용 세션이므로 조용히 통과하지만, `gates/`는 있는데 확정 원장이 없으면(draft 단계이거나 `--finalize`가 빠졌으면) stderr로 남긴다. 미사용과 미발견이 같은 침묵이면 놓친 원장이 통과로 보인다.

`.git`·`node_modules`·`.venv`·`__pycache__`·`.build`는 건너뛴다.

⛔ **설치 주의 6항은 `docs/completion-gates.md`가 정본이다** — 배열 추가 · hook 병렬 실행 · 캐시 경로의 버전(하드코딩하면 업데이트 후 조용히 꺼진다) · `python3` 3.9+ 부재 시 fail-open · `~/.fz/stop-hook-state.json` 생성 · 탐색 깊이 3 한계.

검증: `python3 scripts/gate_stop_hook.py --self-test` (**14케이스** — 깊이 1~4 · draft-only · skip-git · approved · kill-switch · 오배선 · bad-cwd · env-missing · loop-guard). health-check 2.6에 배선돼 있다. ⛔ hook 등록 자체는 사용자 소관이므로 **계약까지가 우리가 닫을 수 있는 경계**다.

### 5. health-check — 노출 (hook 미설치 머신)

`gate_check.py --discover <DIR>`. `/fz-manage check` 가 호출 CWD 하위 확정 원장을 찾아 상태를 요약한다.

⛔ **이것이 hook 미설치 머신의 유일한 노출 경로다.** 배선 1~3은 SKILL.md 산문이라 건너뛰어도 신호가 없고, `FZ_GATES_TRACE` 는 환경변수 opt-in 이다.

| 상태 | exit | 이유 |
|---|:---:|---|
| 미충족 있음 | **0** | 작업 중 원장이 미충족인 것은 **정상 상태**다. exit 에 반영하면 원장 있는 모든 세션에서 검사가 빨개져 사람이 health-check 를 안 돌리게 된다(`lint_doc_freshness` 선례 — findings 가 있어도 exit 0, 건수만 보고) |
| 원장 계약 위반 | **3** | fz 가 만든 원장이 자기 계약을 어긴 것은 plugin 자산 결함이고, 그것이 health-check 의 관심사다 |

⛔ **원장 발견은 판정기가 소유한다** — `find_ledgers()`. hook 과 health-check 가 **같은 함수**를 쓴다. 두 곳이 각자 찾으면 한쪽이 놓치는 배치가 생긴다(깊이 2만 보던 결함이 정확히 그것이었다). 린터의 선례와 같은 원칙이다(`lint_contracts.py` 의 `n6_ok()` — chk_N6 와 self-test 가 같은 함수를 쓴다).

`tests` 는 탐색에서 제외한다 — fixture 원장은 테스트 자산이고 작업 원장이 아니다.

## 이탈 경로

정당한 이탈은 둘뿐이고 **둘 다 흔적이 남는다.**

| 경로 | 범위 | 흔적 |
|------|------|------|
| `ABANDON: <id> <비어 있지 않은 이유>` | 게이트 1개 | 원장에 보존 + 최종 보고에 표면화 |
| `FZ_GATES_OFF=1` | 세션 전체 | 환경변수 (원장 불변) |

⛔ **진행 없는 블록 N회 후 자동 해제는 두지 않는다.** 그것은 판정 fail-open이며 위 두 경로 밖의 세 번째 우회로다. 우회는 사용자의 명시적 행위여야 한다.

⛔ **MANUAL 게이트를 차단 대상에서 제외하지 않는다.** 제외하면 모델이 어려운 게이트를 MANUAL로 미는 우회로가 생긴다. MANUAL은 `--confirm`이 발급한 토큰이 있어야 충족이고, 그 명령은 사용자 stdin 응답을 요구한다.

## 승인 계약 (APPROVED_ORACLE_HASH)

`verify-gates` 판정을 반영한 뒤 `--finalize` 로 확정한다. 확정은 실행 게이트마다 `APPROVED_ORACLE_HASH` 를 찍고 헤더에 `APPROVED: yes` 를 남긴다.

도장이 커버하는 것 — `CHECK` · `EXPECT` · `CWD` · `TIMEOUT` · **`CRITERION`** · **제목**. 하나라도 바뀌면 실행이 exit 3 으로 거부된다(재승인 필요).

⛔ **환경(`SHELL`·`PATH`)은 도장에 넣지 않는다.** 승인 대상은 "무엇을 어떻게 재는가"이고 PATH 는 사람이 승인한 것이 아니다. 넣으면 fz-plan 이 세션 A 에서 찍고 fz-code 가 세션 B 에서 실행할 때 exit 3(차단)이 되고, 메시지는 "승인 후 oracle 이 바뀌었다"라며 원인을 잘못 지목한다. 별 세션인 것은 예외가 아니라 **설계된 흐름**이다(compact · 다음 날 · 다른 터미널 · direnv/nvm shim).

| 해시 | 무엇을 묶나 | 환경 |
|---|---|:---:|
| 승인 도장 | 승인한 oracle | ⛔ 제외 |
| 증거 서명 | 이 결과가 **어느 환경에서** 나왔나 | ✅ 포함 (단 **기록된** 값으로 재계산) |

⛔ **`CRITERION:` 을 원장에 남긴다.** VerifySpec 이 요구하는 필드인데 이전에는 command 게이트에서 버렸다. 그러면 승인받은 "무엇을 재는가"가 사라지고 `CHECK` 만 남아, CHECK 를 쉬운 것으로 바꿔도 대조할 원본이 없다. 실측(2026-08-25): 승인된 lint 실행을 `echo <기대문자열>` 로 바꿔도 PASS 였다.

⛔ **이 계약은 한 번도 발화하지 않았다.** 검사 코드는 3곳에 있었는데 **발급하는 곳이 없어** 필드가 원장에 들어가지 않았다. `verify-gates` 스키마가 실행 경로 0건이었던 것(011)과 같은 부류다 — 검사가 존재하는 것과 발화하는 것은 다르다.

| 상태 | 판정 |
|---|---|
| `APPROVED:` 헤더 없음 | draft — 경고만. 도장을 요구하면 순서가 뒤집힌다(Phase 2 평가자가 볼 CHECK 가 도장보다 먼저 있어야 한다) |
| `APPROVED: yes` + 전수 도장 | 확정본 — oracle 변경 시 exit 3 |
| `APPROVED: yes` + 일부 도장 | **exit 3** — 부분 도장은 무도장보다 위험하다. 도장이 있으니 보호받는다고 읽히는데 안 찍힌 게이트는 CHECK 를 바꿔도 통과한다 |

## 관측 (FZ_GATES_TRACE)

`FZ_GATES_TRACE`가 파일 경로를 가리키면 호출마다 `{argv, cwd, exit, stamp}` 한 줄을 append한다.

⛔ **플래그가 아니라 환경변수인 이유.** 이 기록의 목적은 "스킬이 판정기를 **실제로 부르는가**"를 관측하는 것이다. 플래그로 만들면 SKILL.md의 호출 줄을 고쳐야 하고, 그러면 관측이 관측 대상(배선)에 의존해 순환한다.

기록 실패는 판정에 영향을 주지 않는다(`OSError` 무시). 관측 장치가 판정을 바꾸면 안 된다.

⛔ **이것이 확인해 주는 것과 아닌 것.** trace는 "명령이 불렸고 동작했다"를 보인다. "미래의 Lead가 그 산문 지시를 읽고 실행한다"는 보이지 못한다 — 배선 1~3은 여전히 SKILL.md 산문이고 건너뛰어도 신호가 없다. 그 재귀를 끊는 것은 4번(Stop hook)뿐이고, 그것은 사용자 설치다.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-plan | Phase 1 draft 생성 · Phase 2 게이트별 판정 · Phase 3 확정 (배선 1) |
| /fz-code | 절차 6.4에서 Step 게이트 실행 + STATE 전진 (배선 2) |
| /fz-review | Phase 5.5에서 `--reverify` 강등 + guardian 4축 (배선 3) |
| /fz-codex | `verify-gates`(architect, plan 시점 — `verify`에 **추가**) · `validate`(guardian, 변경 후) — `schemas/codex_gate_verdict_schema.json` |
| modules/context-artifacts.md | WORK_DIR 결정 — 원장 경로의 전제 |
| modules/governance.md | 이탈 경로 2종 (`ABANDON:` · `FZ_GATES_OFF`) |

## 설계 원칙

1. **협상 불가능성** — "Gate 통과"는 문장이고 exit 1은 사실이다. 모델은 산문 게이트와 협상할 수 있지만 프로세스 exit code와는 못 한다.

2. **신설이 아니라 승격** — `verify`는 이미 `workflows/plan-collaborative.js` PlanSchema의 required 필드이고 fz-code stepSpec으로 전달된다. 본 모듈은 그 자유 서술 문자열에 형식을 줄 뿐이다.

3. **정규식 미지원** — 파멸적 백트래킹은 체커 자신의 이벤트 루프를 막고 Python `re`에는 타임아웃이 없다. 원장을 fz가 생성하므로 정규식이 필요 없고, 지원하지 않으면 그 실패 유형이 통째로 사라진다.

4. **oracle 무결성** — `APPROVED_ORACLE_HASH`가 승인 시점의 `CHECK`/`EXPECT`/`CWD`/`criterion`/timeout/shell/PATH 지문을 묶는다. 실행 *사이에* `CHECK:`를 더 쉬운 명령으로 바꾸면 재승인이 필요하다. 없으면 **모델이 자기 게이트를 완화하는 경로**가 열린다.

5. **게이트가 게이트를 검증한다** — BATCH shard 재검증처럼 반복되는 절차는 절차로 두지 않고 게이트로 만든다. 절차는 건너뛸 수 있고 건너뛴 것을 아무도 모르지만, 게이트는 건너뛰면 미충족으로 남는다.

6. **범위 밖 실패는 못 잡는다** — 게이트 원장은 **잘못된 전제 위에서도 전부 초록으로 통과한다.** `feedback_negative_report_collect_observation_first`("실측 대상이 틀린 것")가 그 축이며, 본 모듈은 그것을 방어하지 않는다.
