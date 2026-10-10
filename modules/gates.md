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
- [릴리스 경계](#릴리스-경계)
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

### STATE 와 전이표

`STATE:` 값은 넷이다 — 수명주기 셋(`active` → `ready_for_review` → `closed`)과 승인·미착수 `planned`(F-190). ⛔ `planned` 는 수명주기 순서에 넣지 않는다 — 순서 산술로 두면 `active → planned` 가 '역행(자유)' 이 되어 진행 기록이 있는 원장도 착수 전으로 돌아간다. 간선과 전제는 `gate_check.py` 의 `TRANSITIONS` 가 정본이고 표 밖 간선(`active → closed` · `planned → ready_for_review|closed` · `ready_for_review|closed → planned`)은 거부한다.

| 전이 | 주체 | 조건 |
|------|------|------|
| (생성) → `active` | `/fz-plan` | 원장 생성. `--finalize` 는 STATE 를 쓰지 않는다 — 확정은 승인이지 착수 판정이 아니라, 진행 기록이 있는 원장을 다시 확정해도 `planned` 가 되지 않는다 |
| `active` → `planned` | `/fz-plan` 4.5 | `APPROVED: yes` + 진행 기록 0 — 아니면 `REJECT: not-approved` · `REJECT: work-recorded` |
| `planned` → `active` | `/fz-code` Phase 0.4 | 없음 — 착수는 완료 주장이 아니다 |
| `active` → `ready_for_review` | `/fz-code` | 전 Step 게이트 충족 |
| `ready_for_review` → `closed` | `/fz-review` | reverify 통과 + guardian `regressed` 0 · 미룬 게이트 0 |
| `ready_for_review`·`closed` → `active`, `closed` → `ready_for_review` | 누구나 | 없음 — 역행은 재작업이다 |
| `ready_for_review` → `closed` (전량 `ABANDON:`) | 사용자 | 포기한 게이트는 미충족으로 세지 않아 위 전진 조건을 지난다 — `--set-state` 는 인접 전진만 받으므로 `active` 에서 닫는 길은 `ready_for_review` 를 거치거나 손으로 `STATE:` 를 고치는 것뿐이다 |

`planned` 원장은 `--status`(Stop hook · `--discover` 경로)에서만 no-op 이다 — exit 0, `--discover` 는 '착수 전' 수로 따로 센다. 실행(기본 · `--reverify`) · `--only` · `--confirm` 은 exit 3 이고 착수는 `--set-state active` 다. 전제가 깨진 `planned`(미승인이거나 진행 기록이 있는데 손으로 STATE 만 바꾼 원장)는 no-op 이 아니라 `active` 로 판정한다.

**진행 기록** = `- [x]` · 빈 값/`pending` 이 아닌 `EVIDENCE:`(위조·낡은 증거 포함 — 진위가 아니라 흔적을 본다) · `CONFIRMED:`. 진행 기록이 있던 게이트(직전 met · `- [x]` · 증거 흔적 — 재승인으로 unmet 이 된 PASS 포함)가 재실행에서 떨어지면 `EVIDENCE: pending; demoted` 로 남아(reverify 이력) 미착수와 갈린다. ⛔ **잡지 못하는 것(잔존 위험) 두 갈래**: ① 코드를 고치고도 게이트를 한 번도 안 돌렸거나 실패만 한 세션은 흔적이 0 이라 `planned` 로 갈 수 있고 Stop hook 도 통과한다 — 거부 범위를 '진행 기록이 있는 원장' 으로 정한 결과다. ② 진행 중인 원장에서 `/fz-plan` 4.5 를 다시 돌리면 산문 단계 `cp plan.draft.md plan.md` 가 기록을 판정기 밖에서 먼저 덮고, 이어지는 `--finalize` · `--set-state planned` 는 전제(승인 · 기록 0)를 갖춘 원장을 보게 된다. 훅 차단 사유가 `--set-state planned` 를 안내하므로 두 갈래 모두 닿기 쉽다(`tests/fixtures/gates/planned-state` 의 `residual-no-record` · `residual-replan` 셀이 지금 동작을 고정한다).

⛔ **하향 설치 전**: 4.44.0 이하 판정기는 `STATE: planned` 를 모른다 — exit 3 으로 읽어 Stop hook 이 '원장 계약 위반' 으로 막는다. 이전 판으로 되돌리기 전에 `planned` 원장마다 `--set-state active` 를 돌린다.

⛔ **`ready_for_review`도 미완료다.** fz-code가 끝났다고 원장을 닫으면 fz-review의 재검증이 강등을 수행할 수 없다 — 중간 상태가 그 구멍을 막는다.

⛔ **kill-switch는 영속 상태를 변경하지 않는다.** `FZ_GATES_OFF=1`은 세션 단위 bypass이므로 STATE를 건드리면 후속 세션까지 지속된다.

## 원장 문법 (요약)

```markdown
# Gates: 사용자 이력 API 재정비
ROOT: {WORK_DIR}
STATE: active
CURRENT_RELEASE: R-A
Scope: 이력 조회 API를 v2로 이관하고 기존 소비자 3곳을 무중단 전환한다

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

ABANDON: G3 서버 API 미배포 — TKT-9999로 핸드오프
DEFER: G4 R-B 소비자 전환은 다음 릴리즈에서 한다
```

- `ROOT:`는 이 원장이 속한 WORK_DIR의 **realpath 절대경로**다. 발견 키가 아니라 **검증 키**다(발견은 `cwd` 하위 glob · `FZ_GATES_LEDGER` 이고, 세션과는 transcript 소유 판정으로 묶는다 — [스킬 배선 5지점](#스킬-배선-5지점) 참조).
- 실행 게이트는 `CHECK:`와 `EXPECT:` **둘 다** 갖는다. 수동 게이트는 `MANUAL:`만 갖는다. 하나만 있으면 오류다.
- `EXPECT:`는 **부분 문자열 매칭**이다. 정규식을 지원하지 않는다 — 이유는 [설계 원칙](#설계-원칙) 참조.
- `CWD:`는 절대경로만 허용한다. `..` 포함 시 오류다.
- `TOOLS:`는 이 `CHECK:`가 필요로 하는 **외부 명령**을 쉼표로 나열한다(선택). 하나라도 PATH에 없으면 CHECK를 **돌리지 않고** 미판정으로 남긴다 — 자세한 이유는 [미판정](#미판정--도구-부재는-실패가-아니다) 참조.
- `EVIDENCE:`의 `sig=`는 **체커가 발급한 서명**이다. `oracle_hash + exit + output`에 묶여 있어 손으로 쓴 증거는 met 이 되지 않는다.
  ⛔ **암호학적 위조 방지가 아니다** — 알고리즘이 공개돼 있어 작정하면 재계산할 수 있다. 이것이 막는 것은 *우연한* false-green(CHECK 를 안 돌리고 통과 텍스트만 쓰는 경로)이다.
- `ABANDON:`도 같은 성격이다. 누구나 append 할 수 있으므로 **위조 방지가 아니라 표면화 장치**다 — 있으면 최종 보고에 반드시 찍힌다.
- `DEFER: <id> <릴리즈> <이유>`는 **포기가 아니라 예정**이다(F-328). 여러 릴리즈로 나눈 원장에서 `CURRENT_RELEASE:` 헤더와 다른 릴리즈로 미룬 게이트는 판정·차단 대상이 아니고, 출력에 `DEFER` 줄과 `deferred` 수로 남는다. 헤더를 그 릴리즈로 바꾸면 평소처럼 판정한다. 헤더는 승인 도장에 들어가지 않으므로 바꿔도 재승인이 필요 없다.

### 파서 fail-closed

| 형태 | 판정 | 이유 |
|---|---|---|
| 헤더 중복 선언 (`STATE:` 두 번) | exit 3 | ⛔ 마지막이 이기면 `STATE: closed` 를 한 줄 append 해서 원장을 **통째로 no-op** 으로 만들 수 있다. `ABANDON:` 처럼 흔적이 남는 이탈로가 아니라 조용한 무력화다 |
| 헤더 중복 (`ROOT:` 두 번) | exit 3 | 실행 디렉토리가 바뀐다. ROOT 를 상위로 두면 소유 검사도 통과한다 |
| 게이트 밖 들여쓰기 속성 | exit 3 | 오타로 게이트 줄이 빠지면 그 CHECK 가 통째로 사라지는데, 게이트 수 감소를 알아챌 오라클이 없다 |
| 게이트 뒤 헤더 재선언 | 무시 | 헤더는 첫 게이트 앞에서만 읽는다 (설계) |
| `DEFER:` 가 있는데 `CURRENT_RELEASE:` 없음 | exit 3 | 지금이 어느 릴리즈인지 모르면 미룸을 판정할 수 없다 — 전부 미룬 것으로 읽지 않는다 |
| 한 게이트에 `DEFER:` 와 `ABANDON:` | exit 3 | 예정과 포기는 다른 기록이다 |
| 릴리즈·이유가 빠진 `DEFER:` | exit 3 | 산문으로 흘러가면 미룸이 없던 일이 된다 |

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

⛔ **기본 실행은 충족 게이트를 다시 돌리지 않는다**(F-330). 그 게이트마다 `MET … 다시 돌리지 않았다` 줄을 내고, 요약에 `reran`(재실행 수)과 `stamp-only`(기록된 증거만 읽은 수)를 0 이어도 적는다. 코드를 고친 뒤 게이트를 다시 확인하려면 `--reverify`(충족 게이트도 재실행)를 쓴다 — `ALL MET` 만 보고 재실행했다고 읽지 않는다.

### `--only` — 이름을 댄 게이트는 충족이어도 다시 돈다

`--only <id,…>` 로 이름을 댄 게이트는 이미 충족이어도 CHECK 를 다시 실행하고 그 결과로 증거를 새로 찍는다(F-330). 고친 뒤 그 게이트를 지목한 호출이 옛 도장만 읽고 `ALL MET` 을 내면 '재실행 PASS' 로 읽히기 때문이다. 떨어졌을 때의 처리(exit 1 · 강등 기록)는 `--reverify` 와 같다. 선택자 없는 기본 실행은 위 문단 그대로 도장만 읽고, `--status --only` 는 실행하지 않으며, `closed` 원장은 no-op 이다(`tests/fixtures/gates/only-rerun`).

⛔ `--only` 에는 **지금 확인할 게이트만** 넣는다 — 충족 게이트를 함께 적으면 그 CHECK 가 다시 돌고(시간), 지금 트리에서 떨어지면 강등된다. 전부 다시 확인하려면 `--reverify` 를 쓴다.

### 미판정 — 도구 부재는 실패가 아니다

`TOOLS:`로 선언한 명령이 PATH에 없으면 체커는 CHECK를 실행하지 않는다. 대신 `UNRUN`을 찍고 그 게이트를 미충족으로 센다.

돌려버리면 무엇이 잘못되는지가 이 속성의 존재 이유다. CHECK는 `shell=True`로 돈다. 그래서 도구가 없으면 셸이 **exit 127**을 내고, 체커는 그것을 다른 실패와 구별하지 못한 채 `FAIL`로 기록한다. 그러면 원인이 "게이트가 깨졌다"로 오귀속되고, 사람이 할 일이 뒤바뀐다 — 고쳐야 할 것은 코드가 아니라 **없는 도구**다. 같은 오귀속의 실측 사례가 `fz-findings` F-288이다(`node` 부재를 문법 오류 8건으로 인쇄).

판정은 두 축으로 나뉜다.

| 축 | 동작 | 이유 |
|---|---|---|
| exit code | 1(미충족) | 도구가 없었다는 것은 통과가 아니다. timeout과 같은 자리다 |
| 원장 | 건드리지 않는다 | 판정을 못 했을 뿐이므로 과거 증거를 `pending`으로 지우지 않는다. 예산 소진(`BUDGET`)과 같은 처리다 |

⛔ 원장을 건드리지 않으므로 **`--status`는 이전 판정을 그대로 읽는다.** 통과했던 게이트의 도구가 사라지면 `--reverify`는 `UNMET`을 내는데 `--status`는 `ALL MET`을 낸다(실측 — `fz-findings` F-291). Stop hook이 쓰는 것은 `--status`다.

⛔ **승인 도장(`APPROVED_ORACLE_HASH`)에는 넣지 않는다.** 도장이 묶는 것은 "무엇을 어떻게 재는가"이고, `TOOLS:`는 게이트를 **통과시킬 수 없다**(부재면 미충족). 완화 레버가 되지 못하므로 재승인 대상이 아니다.

### 실행 환경

| 축 | 규칙 | 이유 |
|---|---|---|
| stdin | `DEVNULL`로 닫는다 | 미지정이면 터미널·상위 파이프를 **상속**해 CHECK가 입력을 기다리면 게이트당 기본 120초를 잡아먹는다 |
| 프로세스 그룹 | `start_new_session=True` + 스폰 직후 pgid 확보 | 셸이 먼저 죽으면 `getpgid`가 실패해 손자를 못 죽인다 |
| 손자 잔존 | 저자가 선언한 `TIMEOUT`까지 기다리고, EXPECT가 매칭되면 즉시 끊는다 | 고정 grace는 정상적인 지연 출력을 자르고, 무한 대기는 orphan daemon에 매달린다. 구분 기준은 **더 기다려서 판정이 바뀔 수 있는가** 하나다 |
| 출력 수집 | `read1(n)` 으로 지금 있는 만큼만 읽는다 | `read(n)` 은 **n 바이트가 모이거나 EOF 까지 블록**한다 — 짧은 출력이 프로세스 종료 시 한꺼번에 도착해 EXPECT 조기 매칭도 출력 상한 감지도 실행 중에 발화하지 못했다 |
| 강제 종료 | 증거에 `killed=descendant`를 남긴다. **판정은 뒤집지 않는다** | CHECK 계약은 exit + EXPECT다. 서버를 띄우는 정당한 CHECK를 실패시키면 안 되지만, 프로세스 누수는 저자가 알아채야 한다 |

### ⛔ 게이트를 쓰기 전 self-check — 이 형태가 최선인가 (F-286)

CHECK 를 쓰기 전에 **한 줄 묻는다.**

> 이 게이트가 고정하는 형태보다 **더 단순한 등가 표현**이 있는가? 있으면 **그것을** 고정한다.

⛔ 반례 역검증은 **게이트의 민감도**만 잰다 — *대상의 적절성*은 안 잰다.
실측(F-286): `.opacity` 3개의 **순서열을 계약으로 박고** 반례 10/10 통과로 "게이트 유효" 판정했다.
그런데 세 항의 논리곱은 같은 커밋에서 도입한 계산 프로퍼티 하나와 **완전 등가**였다.
검증을 통과한 게이트가 **미검토 결정을 더 단단히 굳혔다** — 통합하면 FAIL 하도록 잠근 것이다.

부수 효과도 하나 더 있었다: 그 게이트는 계약이 아니라 **표면**에 묶여 있어 base 리베이스에서 깨졌다.
⭐ **표면을 잠그면 표면이 움직일 때마다 깨진다.** 잠글 것은 *무엇이 참이어야 하는가*지
*어떤 모양으로 쓰여 있는가*가 아니다.

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

Phase 1 산출 시 `steps[].verify`를 읽어 `{WORK_DIR}/gates/plan.draft.md`를 만든다. `verify.kind`가 `command`면 `CHECK:`/`EXPECT:`, `manual`이면 `MANUAL:`+`CRITERION_HASH:`. `verify.tools`가 있으면 `TOOLS:`로 옮긴다 — ⛔ VerifySpec이 `additionalProperties: false`라 스키마에 필드가 없으면 plan 저자가 채울 수 없다(`workflows/plan-collaborative.js`가 정의, `plan-lean2.js`도 같은 필드).

Phase 2의 `verify-gates`가 **게이트마다 판정 1개**를 낸다 — "이 `CHECK:`가 제목이 말하는 것을 측정하는가" + noninteractive·rerunnable·side-effect·determinism. Phase 3에서 판정을 반영해 `plan.md`로 확정하고 `--set-state planned` 로 승인·미착수를 남긴다(계획만 하고 끝나는 세션이 Stop hook 에 막히지 않는다).

⛔ **`verify`를 대체하지 않고 추가한다.** `gpt_gate_verdict_schema`에는 `issues`·`verdict`가 없어서, 스키마를 바꿔치기하면 fz-plan의 Issue Tracker 기록·scope challenge·Gate 2 승인 입력이 사라진다. 두 호출은 관심사가 다르다 — 계획이 옳은가(`verify`)와 게이트가 그 계획을 측정하는가(`verify-gates`).

⛔ **스키마 선택만으로는 N/N이 보장되지 않는다.** 스키마는 `gates: []`(빈 배열)·중복 id·원장에 없는 id·거짓 `summary` 합계를 전부 통과시킨다.

대조는 **눈으로 하지 않는다** — `--verdict-check <응답.json>`이 게이트 수·id 집합·중복·summary 합계를 판정한다. exit 1이면 재호출 1회 후 **미판정으로 기록**한다. 이 계층이 없애려는 것이 산문 대조이므로 대조 자체를 산문에 두지 않는다.

⛔ 개수만 세면 안 되는 이유 — 중복 id가 누락을 가린다. `G1` 두 번 + `G3` 없음은 3개로 보인다.

⛔ **draft가 Phase 2보다 먼저다.** Phase 2가 Phase 3보다 앞이므로, 원장을 Phase 3에서 만들면 평가자가 볼 `CHECK:`가 없다.

ℹ️ **세션 바인딩은 만들지 않았다.** Stop hook 입력에 `session_id`가 오므로 `~/.fz/sessions/<id>.json` 바인딩이 가능하지만, 그러면 **쓰는 쪽 배선**이 필요하고 그 배선이 빠지면 hook이 원장을 못 찾아 조용히 무력화된다. `cwd` 하위 glob은 배선이 0이고 여러 원장을 전부 본다 — 배선 4 참조.
   ⛔ 단 **차단은 이 세션이 쓴 원장만** 한다(2026-09-11, F-188 2회 재관측). 발견은 glob 이지만 소유는 입력의 `transcript_path` 에서 그 원장을 `Write`/`Edit`/`--finalize`/`cp`/`>` 로 쓴 tool_use 가 있는지로 가른다 — 쓰는 쪽 배선 없이 세션 스코프가 된다. 남의 미충족 원장은 경고로만 인쇄하고, transcript 를 못 읽으면 전 원장을 판정한다(fail-closed).

light 모드는 원장을 만들지 않는다.

### 2. fz-code — Step 판정

Step 완료 선언 전 `--only {StepID}`로 **해당 Step 게이트만** 실행한다. 선택자 없이 전체를 돌리면 미래 Step 게이트가 실패해 첫 Step에서 영구 정지한다. 실패면 다음 Step으로 진행하지 않는다. 전 Step 충족 시 `--set-state ready_for_review`.

⛔ **전진은 인접 단계만** — `active → closed` 직행은 fz-review 재검증을 통째로 건너뛰므로 거부된다.

원장 부재·`STATE: closed`면 no-op이다. `STATE: planned` 면 exit 3 이다 — Phase 0.4 에서 `--set-state active` 로 연다. `ROOT:`는 **realpath 정규화 후 원장이 그 하위인지**로 판정한다 — 상대 경로·`..`·존재하지 않는 디렉토리·타 디렉토리 ROOT는 exit 3이다.

⛔ realpath **일치**를 요구하지는 않는다. macOS의 `/var → /private/var`처럼 정상 경로도 심볼릭을 거치므로, 정규형을 강요하면 정당한 원장이 거부된다(fixture 21건이 이것으로 깨졌다). 필요한 것은 정규형이 아니라 소유 판정이다.

### 3. fz-review — 재검증

Lead가 Workflow 반환을 통합할 때 워커 자기보고 대신 게이트를 재실행한다(`--reverify`). 통과 못 하면 `- [x]` → `- [ ]` + `EVIDENCE: pending`으로 **강등**한다 — 재실행 전에 진행 기록이 있던 게이트(met · `- [x]` · 증거 흔적)는 `EVIDENCE: pending; demoted` 로 남긴다(통과 기록이 사라진 게이트를 미착수와 가른다 — `planned` 전제의 진행 기록).

`/fz-gpt validate`(fz-guardian)가 각 게이트를 `resolved / partially_resolved / unresolved / regressed` 4축으로 분류한다. `regressed`가 0이 아니면 통합을 차단한다.

### 4. Stop hook — 차단 (2차 계층, 사용자 설치)

`scripts/gate_stop_hook.py`. 세션 종료 시 `cwd` 하위 확정 원장을 찾아, 그중 **이 세션의 transcript 가 쓴 원장**이 미충족이면 종료를 막는다(남의 원장은 경고만 — 병렬 세션이 같은 루트에 있어도 막지 않는다). '쓴' 은 `Write`/`Edit` · `cp`/`mv`/`tee` · `>` 와 원장을 쓰는 판정기 호출(`--finalize` · `--confirm` · `--set-state` · `--only` · `--reverify` · 플래그 없는 기본 실행)이다 — `--status`(`--only` 와 함께여도) · `--discover` 는 읽기라 소유가 아니다. 원장 인자가 변수면 같은 명령의 대입과 그 명령이 `source` 한 파일(훅이 도는 지금의 내용)로 풀고, 풀지 못한 쓰기는 '대상 미상 쓰기' 로 전 원장을 판정한다(fail-closed). 판정기 옵션은 argparse 처럼 푼다 — 축약(`--set` → `--set-state`)은 유일한 접두 일치로 펴고, 어휘 밖 옵션이 하나라도 있으면 argparse 가 거부할 호출이라 쓰기가 아니다. `source` 경로의 `~` · `$HOME` 은 훅 환경으로 펴고, 그래도 못 읽은 source 뒤에서는 파일명 자리가 변수인 명령만, 쓰기 플래그나 `plan.md` 인자가 있을 때 판정기 후보로 본다(무관한 명령이 '대상 미상' 으로 남의 원장에 막히지 않게). `python3 -` · `-c` · `-m` 뒤의 판정기 경로는 그 프로그램의 인자라 호출이 아니다. ⛔ 잔존 위험(보지 않는 꼴): 서브셸 `( cd X && … )` 의 cd 는 닫는 괄호 뒤에도 같은 명령의 다음 세그먼트에 남는다 · 괄호에 붙은 인자(`plan.md)`) · `bash -c '…'` · `xargs` 로 넘긴 판정기 호출 · `~` 로 시작하는 원장 인자(펴지 않아 남의 원장으로 본다 — `$HOME/…` 는 대상 미상으로 막힌다) · `if` · `while` · `until` 조건이나 `{ …; }` · `timeout` 같은 래퍼 뒤의 판정기 호출 · Bash 호출 사이에 이어지는 cwd · 못 읽은 source 뒤의 플래그 없는 기본 실행(`python3 "$G" "$L"`). 그래서 `/fz-code` · `/fz-review` 처럼 판정기 호출만 한 세션도 자기 원장 미충족으로 막힌다. **1차 배선 1~3은 SKILL.md 산문이라 Lead가 건너뛰어도 신호가 없다 — 그 재귀를 끊는 것은 이 hook 하나뿐이다.** `STATE: planned`(승인·미착수)는 판정기 `--status` 가 no-op 으로 보므로 막지 않는다. 차단 사유는 '충족 · `ABANDON:`' 에 셋째 선택지 '착수 전이면 ABANDON 이 아니다 — `--set-state planned`' 를 함께 준다 — 2지선다는 계획만 승인한 원장에 거짓 포기 기록을 유도한다.

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

⛔ **무한 루프 방어.** Stop을 막으면 Claude가 계속하고 다시 Stop에 도달한다. 원장 상태가 그대로면 같은 이유로 또 막혀 세션이 끝나지 않는다. 같은 상태(지문 = 막힌 원장 경로와 판정 종류 `path:unmet|invalid` — 원장 내용·사유 요약은 넣지 않는다. 옆 세션이 원장을 고쳐도 카운터가 리셋되지 않게)로 **2회**까지만 막고 이후 통과 + 진단한다. 상태를 쓸 수 없으면(디스크 오류) 즉시 통과 — 방어 없이 막으면 무한 block이 된다.

#### ⛔ 발견 한계와 탈출로

깊이는 0~3이다. `*/gates/plan.md` 하나만 보면 `{CWD}/gates/plan.md`(깊이 1)·`{CWD}/a/b/gates/plan.md`(깊이 3)를 놓치고 **조용히 통과한다** — 실측에서 4종 중 1종만 발견됐다.

⛔ **발견 수에는 상한이 없다.** 8개에서 자르던 구판은 사전순 뒤(대개 최신 티켓)의 소유 원장을 말없이 빼고 통과했다. hook 은 발견한 원장 전부에 소유 판정을 먼저 하고 소유 원장을 예산(45초) 안에서 **먼저** 판정한다. 상한(8)은 남의 원장 판정에만 두고, 넘거나 예산이 모자라 못 본 남의 원장은 수를 진단으로 남긴다. 예산이 다해 판정하지 못한 소유 원장이 남으면 통과하지 않고 '소유 원장 N개 미판정(예산 소진)' 으로 막는다(루프 방어 2회는 같다 · 시험용 `FZ_GATES_HOOK_BUDGET_S` 는 예산을 줄이기만 한다). `--discover` 도 자르지 않고 읽지 못한 원장을 `미판정 N` 으로 센다 — 종료 코드는 그대로다.

깊이 4 이상, 그리고 `cwd` **밖**은 어떤 glob으로도 찾지 못한다. 워크트리에서 작업하고 원장이 리포 루트에 있는 경우가 그렇다 — hook은 `cwd`만 받으므로 설계 한계다. `FZ_GATES_LEDGER`(경로 목록, `os.pathsep` 구분)로 명시 지정한다.

⛔ **"찾지 못함"은 조용하지 않다.** `gates/` 디렉토리가 아예 없으면 게이트 미사용 세션이므로 조용히 통과하지만, `gates/`는 있는데 확정 원장이 없으면(draft 단계이거나 `--finalize`가 빠졌으면) stderr로 남긴다. 미사용과 미발견이 같은 침묵이면 놓친 원장이 통과로 보인다.

`.git`·`node_modules`·`.venv`·`__pycache__`·`.build`는 건너뛴다.

⛔ **설치 주의 6항은 `docs/completion-gates.md`가 정본이다** — 배열 추가 · hook 병렬 실행 · 캐시 경로의 버전(하드코딩하면 업데이트 후 조용히 꺼진다) · `python3` 3.9+ 부재 시 fail-open · `~/.fz/stop-hook-state.json` 생성 · 탐색 깊이 3 한계.

검증: `python3 scripts/gate_stop_hook.py --self-test` (**37케이스** — 판정기 옵션 어휘 대조(gate-vocab — 훅의 옵션 집합 = 판정기 add_argument) · no-gates-dir · 깊이 1~4 · draft-only · skip-git · closed-passes · approved · planned-passes · planned-reason(셋째 선택지) · kill-switch · 오배선 · bad-cwd · env-missing · loop-guard ×2 · **소유 판정 17종**: foreign-ledger·foreign-heredoc-cite·foreign-py-c-read·foreign-status-only 통과 / owned-ledger·owned-redirect·owned-bash·owned-bash-cd·owned-bash-var·owned-py-heredoc·owned-py-c·owned-only·owned-default·owned-var-L·owned-sourced 차단 / transcript-missing·unknown-target fail-closed 차단 · multi-unmet 사유의 미충족 id 목록 · budget-undecided 예산 소진 차단). 동작 fixture: `tests/fixtures/gates/write-ownership`(쓰기·읽기 짝) · `tests/fixtures/gates/discover-limit`(원장 1·9·10·80 · 예산 소진). health-check 2.6에 배선돼 있다. ⛔ hook 등록 자체는 사용자 소관이므로 **계약까지가 우리가 닫을 수 있는 경계**다.

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

`DEFER:` 는 이탈이 아니다 — 수용 기준을 그대로 두고 **판정 시점만 뒤 릴리즈로 옮긴다.** 그래서 미룬 게이트가 남은 원장은 `closed` 로 전이할 수 없다(`ready_for_review` 는 된다). 닫으려면 그 릴리즈를 마치거나 `ABANDON:` 으로 포기를 기록한다.

⛔ **Stop hook 의 루프 방어는 이탈 경로가 아니다.** 같은 상태로 2회 막은 뒤 통과시키는 것(배선 4 '무한 루프 방어')은 세션 감금을 피하는 fail-open 이다 — 원장을 바꾸지 않고, 미충족은 `--discover` 와 다음 세션에 그대로 남는다. 진행 없는 블록을 **원장 상태 변경**으로 풀지는 않는다 — 우회는 사용자의 명시적 행위여야 한다. `planned` 도 이탈이 아니다 — 수용 기준을 그대로 두고 '착수 전' 을 기록할 뿐이며, 진행 기록이 있으면 판정기가 거부한다.

⛔ **MANUAL 게이트를 차단 대상에서 제외하지 않는다.** 제외하면 모델이 어려운 게이트를 MANUAL로 미는 우회로가 생긴다. MANUAL은 `--confirm`이 발급한 토큰이 있어야 충족이고, 그 명령은 사용자 stdin 응답을 요구한다.

## 릴리스 경계

판정기는 릴리스 사이의 **순서**를 모른다(F-359). `DEFER:` 는 `CURRENT_RELEASE:` 와 *다르면* 미룸으로 읽힐 뿐이라, 한 원장을 여러 판에 걸쳐 쓰면 두 곳이 깨진다. 헤더를 다음 판(R-B)으로 넘기는 순간 지난 판(R-A)으로 미뤄 두고 판정하던 게이트가 다시 `deferred` 가 되어 미충족 목록에서 빠진다(사용자 확인 대기도 가려진다). 출하 버전을 박아 둔 CHECK 는 다음 판이 버전을 올리면 `--reverify` 에서 강등된다. 그래서 규칙은 셋이다.

1. **릴리스마다 새 원장을 연다.** 한 원장은 한 릴리스만 담고 `CURRENT_RELEASE:` 를 다음 판으로 넘기지 않는다. 다음 판의 게이트는 다음 판 원장에 쓴다. [원장 문법 (요약)](#원장-문법-요약) 의 `DEFER:` 설명('헤더를 그 릴리즈로 바꾸면 평소처럼 판정한다')은 헤더를 바꿨을 때의 동작을 적은 것이고, 판을 넘길 때는 그 변경을 하지 않는다.
2. **판이 끝나면 `closed` 로 닫는다.** `closed` 원장은 `--status` · 기본 실행 · `--only` · `--reverify` 가 모두 no-op 이라, 다음 판의 변경(버전 올림 · 공유 파일 수정)이 지난 판의 증거를 강등하지 못한다. 미룬 게이트가 남으면 `closed` 가 거부되므로([이탈 경로](#이탈-경로)), 다음 판으로 넘길 게이트는 이 원장에 `ABANDON: <id> <다음 판으로 이월 — 사유>` 로 남기고 다음 판 원장에 새 게이트로 다시 쓴다.
3. **여러 판에 걸쳐 열려 있을 원장의 버전 CHECK 는 `>=` 로 쓴다.** 다음 버전이 올라간 뒤에도 닫히지 않을 원장에서 `version == "4.42.0"` · '최상단 CHANGELOG 절' 처럼 한 버전에 고정하면, 다음 버전이 올라오는 순간 `--reverify` 에서 떨어진다. '이 버전 이상' · '이 버전 절이 있다' 로 쓴다 — 버전을 올리지 않은 실수(4.44.0 그대로)는 `>=` 로도 잡힌다. ⛔ 예외: 판 하나만 담고 끝나면 `closed` 로 닫는 원장(규칙 1 · 2)의 릴리스 게이트는 그 판 버전을 환경변수로 받아 **등식**(`= "$V"`)으로 잰다 — 너무 높게 올린 버전도 잡고, 닫힌 뒤에는 규칙 2 가 다음 판의 강등을 막는다.

```markdown
- [ ] G9: 출하 버전이 4.45.0 이상이고 그 판의 CHANGELOG 절이 있다
  CHECK: python3 -c 'import json,sys;v=json.load(open(".claude-plugin/plugin.json"))["version"];sys.exit(0 if tuple(map(int,v.split(".")))>=(4,45,0) else 1)' && grep -q '^### v4\.45\.0 ' CHANGELOG.md && echo VERSION-OK
  EXPECT: VERSION-OK
```

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
| 확정 뒤 게이트를 더하거나 고침 | `--finalize --only <id,…>` — 지정한 게이트에만 도장을 찍는다. 나머지 실행 게이트의 도장이 현재 계약과 다르면 **거부**한다(F-334: 헤더를 지우고 전부 다시 찍는 우회는 다른 게이트의 변경까지 재승인했다). draft 에는 쓰지 않는다 |

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
| /fz-gpt | `verify-gates`(architect, plan 시점 — `verify`에 **추가**) · `validate`(guardian, 변경 후) — `schemas/gpt_gate_verdict_schema.json` |
| modules/context-artifacts.md | WORK_DIR 결정 — 원장 경로의 전제 |
| modules/governance.md | 이탈 경로 2종 (`ABANDON:` · `FZ_GATES_OFF`) |

## 설계 원칙

1. **협상 불가능성** — "Gate 통과"는 문장이고 exit 1은 사실이다. 모델은 산문 게이트와 협상할 수 있지만 프로세스 exit code와는 못 한다.

2. **신설이 아니라 승격** — `verify`는 이미 `workflows/plan-collaborative.js` PlanSchema의 required 필드이고 fz-code stepSpec으로 전달된다. 본 모듈은 그 자유 서술 문자열에 형식을 줄 뿐이다.

3. **정규식 미지원** — 파멸적 백트래킹은 체커 자신의 이벤트 루프를 막고 Python `re`에는 타임아웃이 없다. 원장을 fz가 생성하므로 정규식이 필요 없고, 지원하지 않으면 그 실패 유형이 통째로 사라진다.

4. **oracle 무결성** — `APPROVED_ORACLE_HASH`가 승인 시점의 `CHECK`/`EXPECT`/`CWD`/`criterion`/timeout/shell/PATH 지문을 묶는다. 실행 *사이에* `CHECK:`를 더 쉬운 명령으로 바꾸면 재승인이 필요하다. 없으면 **모델이 자기 게이트를 완화하는 경로**가 열린다.

5. **게이트가 게이트를 검증한다** — BATCH shard 재검증처럼 반복되는 절차는 절차로 두지 않고 게이트로 만든다. 절차는 건너뛸 수 있고 건너뛴 것을 아무도 모르지만, 게이트는 건너뛰면 미충족으로 남는다.

6. **범위 밖 실패는 못 잡는다** — 게이트 원장은 **잘못된 전제 위에서도 전부 초록으로 통과한다.** `feedback_negative_report_collect_observation_first`("실측 대상이 틀린 것")가 그 축이며, 본 모듈은 그것을 방어하지 않는다.
