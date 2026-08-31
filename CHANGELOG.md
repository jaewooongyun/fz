# Changelog

### v4.28.0 (2026-09-01) — 게이트가 헛돌고 있었다 [MINOR]

자기 규칙과 자기 코드를 검사하던 자리 여덟 곳이 통과를 인쇄하면서 실제로는 아무것도 재지
않았다. 커버리지는 분모를 파일로 고정해 파일 안의 절을 세는 주장이 1/1 = 100% 로 통과했고,
d6 오라클은 워크플로 함수를 복사해 두고 복사본을 검사해 원본을 부숴도 4/4 통과했으며, 문체
fixture 는 "오검출 0/8" 을 기대값으로 적어 두고 한 번도 실행된 적이 없었다. 셋 다 실패가
빨간불이 아니라 **초록불로 나타난다.**

Coverage Gate 에 절차 0 을 신설해 전수 주장의 **대상 단위 U** 와 읽어야 할 파일 수 F 를
분리했다. ⛔ 결과 건수("위반 0건")를 단위로 삼지 않는다 — violation 이 단위가 되어 같은 붕괴가
재발한다. 외부 채점이 `verdict: revise` 로 연동 범위를 넓혔고 지적대로 요약·전략 변수·출력
형식·체크리스트를 함께 바꿨다. ⛔ 분모 조달원 문제(원장 D-3)는 세션 1/2 미달이라 처방 문장을
건드리지 않았다.

d6 는 형제 테스트 둘이 이미 쓰던 `>>> PURE:` 마커 방식으로 바꿔 원본을 런타임 추출한다.
뮤테이션 네 종이 전부 잡히고 마커가 사라지면 예외로 죽는다.

⭐ 그 오라클들은 **어느 자동 경로에도 없었다** — 10 개 중 참조가 있는 것은 하나였다. 검사
4.6·4.7 을 신설해 전부 돌린다. 러너를 0 개 찾으면 통과가 아니라 미실행이다.

⭐ 정본 둘이 서로를 위반하고 있었다. 매핑 블록 정본은 볼드 라벨 다섯을 한 문단에 두라고
규정하는데 G8 은 볼드 셋 이상을 과잉으로 봤다. 줄머리 라벨을 강조에서 빼고
`scripts/check_g8_style.py` 를 신설했다 — 임계가 있는 2 종만 기계 판정하고 나머지는 SKIP 이다.
fixture 의 "1건이라도 나오면 게이트가 과잉" 선봉쇄도 원인 분류 3 갈래로 열었다.

감사 판정 두 건은 뒤집혔다. "파이프라인 15종 미등재" 는 실제로 선언 한 문장 문제였고 판정대로
15 행을 옮겼다면 트리거가 두 파일에 중복된다. "AC1-AC9 우회" 도 아홉 중 실체는 둘뿐이었다.

배포 가능하도록 개인 절대 경로·사내 티켓 ID·제품 조직명·도메인 어휘를 걷어냈다.

→ [릴리즈 노트](docs/releases/v4.28.0.md)

### v4.27.1 (2026-08-31) — 리베이스 스킬은 플러그인 밖에서 게이트 없이 돌고 있었다 [PATCH]

`fz-rebase` 를 단독으로 전달할 수 있는지 확인하다가, **전달해도 동작하지 않는 상태**임을 확인했다.
개인 경로도 개인 메모리 참조도 0건이었는데 정작 스크립트 경로가 풀리지 않는다.

SKILL.md 가 `<FZ_ROOT>` = `claude plugin path fz` 로 스크립트를 가리켜, 플러그인이 없으면
`snapshot`·`check`·`audit`·`prepush` **네 게이트가 통째로 무산된다.** 답은 생태계 안에 있었다 —
스킬 주입 헤더 `Base directory for this skill:` 로 자기 디렉토리를 얻는다. ⛔ 헤더가 없으면
추측하지 않고 묻는다.

개인 브랜치의 force-push 권한이 **되돌릴 수 없는 연산 옆에** 예시로 박혀 있던 것을 조건 서술로
바꿨다(3곳). 핵심은 "이 스킬은 그 승인을 확인하지 않는다" 를 명시한 것이다.

⭐ base 하드코딩을 remote HEAD 자동 해석으로 바꾸려다 **실측이 반대했다.** remote HEAD 가
배포 전용 브랜치를 가리키는 리포가 있고(develop 전용 커밋 49 / main 전용 0), 그 위로 리베이스하면
개발 커밋이 base 에서 빠진 채 게이트가 전부 통과한다 — SKILL.md 가 이미 경고하던 실패를 자동화가
스스로 만드는 꼴이다. 판별자를 **ref 존재 여부**로 바꾸고 remote HEAD 는 폴백에서도 뺐다.

`--remerge-diff` 실패를 `2>/dev/null` 이 삼켜 L2 검출이 조용히 꺼지던 것에 probe 를 넣었다.
새 계약 다섯을 K 계열로 고정해 73 → 78 assertion. ⛔ 같은 파일이 양쪽 설치로 나가므로 플러그인을
제거한 격리 복사본에서 검증했다.

→ [릴리즈 노트](docs/releases/v4.27.1.md)

### v4.27.0 (2026-08-31) — 설명이 "바뀐 부분" 만 다루던 것은 지시받은 대로였다 [MINOR]

`--explain` 이 변경분만 설명하는 원인은 모델이 아니라 규칙이었다. `fz-pr-digest` 해설 원칙에
**"diff에 포함된 변경만 해설한다"** 가 명시돼 있었다.

⛔ 고친 것은 규칙 완화가 아니라 **축 전환**이다. diff 를 출력의 축으로 두는 한 변경되지 않은
협력자(프로토콜·주입 지점·등록 코드·호출자)는 **구조적으로 등장할 수 없다.** 처음 보는 사람이
막히는 지점이 정확히 거기다. 이제 기능을 축으로 두고 diff 를 그 안의 좌표로 표시한다.

축을 뒤집으면 무한 확장이 되므로 **폐포 5축**(진입점·협력자·계약·배선·소비자)으로 끊는다.
총 40심볼 예산이고 ⛔ 절단분은 탐색 경계에 기록한다 — 조용한 절단은 "이게 전부" 로 읽힌다.

**실사용 피드백에서 결함 7건이 나왔고 여섯이 같은 유형이었다** — 낯선 심볼이 정의 없이 등장한다.
순서 축이 통과해도 어휘 축에서 막힌다는 뜻이라, 축을 셋으로 재설계했다: 구조(자체) ·
난이도(progressive learning) · 문체(외부 교정 스킬). ⛔ 참고가 알리바이가 되지 않게
**가져오는 것과 거부하는 것을 양쪽 다** 적었다 — level 옵션 체계와 persona 는 안 가져오고,
문체 패턴 35종은 복제하지 않는다(두 자산이 어긋난다).

**게이트 8종에 근거 등급을 붙였다.** H1("규칙은 모델이 스스로 못하는 것에 대한 가정")의 BAD
사례가 "실패마다 체크리스트 행 추가 → 500개 규칙 → 68% 준수율" 이다. 그래서 게이트마다 물었다 —
*이 게이트가 잡았을 구체적 실패를 댈 수 있는가?* G4·G5·G7 은 관측, G6·G8 은 사용자 요구,
**G1·G2·G3 는 `[추론]`** 이다. ⭐ 한 번은 관측이라 쓸 뻔했는데 인용하려던 초안이 **사람이 쓴 글**
이라 모델 능력의 증거가 못 됐다 — 자기 규칙(G3)을 자기 문서에 적용해 등급을 낮췄다.

**공용 모듈 `explanation-protocol.md`(438줄) + `explanation-output.md`(112줄) 신설.**
소비자는 신규 `fz-explain` 과 `fz-pr-digest` Tutor 둘이고, 분할선은 **입력 의존 여부**다 —
seed 산출·슬롯 값·경량 변형만 스킬이 정한다. `tutor-mode.md` 는 249 → 82줄로 줄었고 게이트
정의 중복이 0이다. ⭐ 문체 절을 출력 절 뒤에 둔 것은 의도적이다 — "문체는 마지막에" 를 배치로
싣는다.

**`fz-explain` 신설** — PR·diff 없이 동작한다. 입력은 심볼·기능·상황 셋이고 ⛔ 티켓·리뷰어
개념을 갖지 않는다(`fz-peer-review` 소관). 쓰기 도구와 `Skill` 을 부여하지 않는다 — 문서 저장과
외부 스킬 호출은 Lead 몫이다.

**fixture 를 양방향으로 만들었다** — positive(결함 11종으로 게이트 8종 전수) + negative(오검출 0).
⛔ 한쪽만으로는 판정이 안 선다: positive 만 있으면 과잉 검출을 못 재고 negative 만 있으면
검출력을 못 잰다.

`intent-registry` 는 추가가 아니라 **재분배**다. `과외`·`처음 보는 사람`·`전체 흐름` 은
pr-digest 가 아니라 explain 의 어휘이고 `설명` 단독도 뺐다 — 같은 행에 이미 `PR.*설명` 이 있어
그 스킬이 겨누는 것은 "PR 설명" 이지 "설명" 일반이 아니다. `설명해줘` 단독은 이제 매칭 0이 되어
되묻는데, PR 해설인지 구조 설명인지 알 수 없으니 그게 정확하다.

⭐ **Codex 교차검증이 16건을 냈고 14건을 반영했다.** 자체 검증 6종이 전부 통과시킨 것들이다 —
같은 절의 표 vs 산문 모순 · `또는` 한 글자가 만든 헐거움 · **negative fixture 가 자기 G4 를
위반** · YAML↔registry 이중 소스. ⛔ 특히 셋째는 오라클이 오라클 노릇을 못 하는 상태에서
"오검출 0/8" 을 선언한 것이다.

⚠️ **실사용 검증 0회.** 게이트 거짓 양성률과 Triggering 실측 정확도는 첫 사용에서 나온다.
측정 절차만 확정돼 있다(fixture 양방향 · `/fz-skill eval` ≥90%).

상세: [docs/releases/v4.27.0.md](docs/releases/v4.27.0.md)

### v4.26.0 (2026-08-26) — peer-review 의 병목은 fan-out 이 아니었다 [MINOR]

`/fz-peer-review` 가 오래 걸리는데 품질이 그만큼 오르지 않는 문제. 진단이 짚은 것은 예상과 달랐다 — **에이전트를 하나도 스폰하지 않은 실행도 분 단위가 걸렸다.** wall-clock 의 바닥은 병렬 구조가 아니라 Lead 의 순차 작업이었고, 한 실행(51분)을 mtime 으로 복원하니 **35분가량에 Lead 외에 일하는 주체가 없었다.**

**시간** — Gather 를 배치 스크립트로 옮겼다. 실측 약 20분 → **2초**. 렌즈는 Bash 에 접근할 수 없어(Workflow 워커는 `acceptEdits` 강제, `tools:` 제거가 유일한 방어) 병렬화가 아니라 Lead 쪽 호출 횟수를 줄이는 것이 남은 레버였다.

**품질** — 판정 규칙을 계약 3종(MergeContract · DiscoveryContract · InputHygiene)으로 세웠다. 한 실행에서 최종 14건 중 5건이 문서화되지 않은 판단에 기댔다.

⛔ **가장 값이 큰 발견**: Coverage Gate 가 `### 4. Confidence Matrix 출력` 안에 있는데 Tier 0 은 그 Matrix 를 건너뛴다 — **게이트가 경량 경로가 지나가지 않는 자리에 붙어 있었다.** `peer-review-tiers.md` 의 게이트 참조 실측: Coverage 0 · Negative-Result 0 · InputHygiene 0 · Reflection Rate 0. 형제 4스킬은 이미 "light 에서도 생략 불가" 를 쓰고 있었다 — 발명이 아니라 복사였다.

Workflow 판정 결함 넷을 고쳤다 — Stage 2 무조건 실행 · `stage2Ran` 하드코딩 `true`(0콜이어도 true 를 반환해 "조용한 off 방어" 목적을 배반) · 범위 min-max 병합 · 교차 병합의 덮어쓰기(concat 순서가 결과를 정했다).

위험 판정은 오탐 4건 전수로 이관 근거를 삼았다(`actor` 가 `Interactor` 에 걸리고 전부 hunk 헤더). net 판정으로 개명·이동을 거른다 — 코드 이동 PR 이 모든 토큰 정확히 균형인데 구 로직은 +2 승격했다.

lint 2종 신설. `#N11`(경량 경로 검증 계약 선언) 은 게이트 5건 중 지적받은 1건만 고쳐진 것(1/5)이 근거다. diff 파서 hunk 상태 선언은 같은 결함이 네 번 나서 만들었다 — ⛔ **정답은 같은 디렉터리에 이미 있었다**(`header_done`·`inhdr`).

`review-surface.md` 가 stale merge-base 로 부풀려진 diff 를 지목한다(실측 2.9배). `move_drift.py` 는 이동 리팩토링에서 **동등성이 못 보는 드리프트**를 데이터로 만든다 — 동등성 통과 후에도 3렌즈가 `origin: regression` 3건을 찾았다.

read-set: Tier 0/1 2,015 → **2,004**(계약 배선 증가분을 Tier 2/3 전용 블록 추출이 상쇄) · `SKILL.md` 500 → 451줄.

⚠️ **확산 임계는 판정 불가**다 — 사전등록이 요구하는 `3건 전수` + 경로별 최소 1건 + paired replay 를 채우지 못했다. Tier 0/1·Tier 3 실전 검증 0회, Codex 교차검증은 spend cap 으로 두 번 다 실패했다.

상세: [docs/releases/v4.26.0.md](docs/releases/v4.26.0.md)

### v4.25.1 (2026-08-25) — fixture 가 클론 위치에 묶여 있었다 [PATCH]

fixture 원장의 `ROOT:`·`CWD:` 는 **커밋한 사람의 클론 경로**다. self-test 가 sandbox 로 재작성하는데 `replace(str(FIXTURES), …)` 만 썼다. 다른 클론이나 플러그인 캐시에서는 `FIXTURES` 가 그 경로와 달라 **매칭이 0건**이 되고, ROOT 가 남의 경로를 가리켜 소유 검사에서 전부 exit 3 이 된다.

실측 — 플러그인을 4.25.0 으로 업데이트한 뒤 **캐시에서 돌리니 19/66** 이었다. 저장소를 임시 디렉토리로 복사해도 같다. 개발 모드(`--plugin-dir`)로만 쓰면 드러나지 않는 결함이었다.

경로 **모양**으로 재작성한다 — `…/tests/fixtures/gates` 로 끝나는 절대 경로를 sandbox 로 바꾼다. 어느 클론에서 커밋했든 동작한다.

⛔ 음성 대조: 옛 replace-only 로 되돌리면 복사본에서 19/66 로 떨어진다. 매니페스트 `_notes.fixture-portability` 에 회귀 확인 방법을 남겼다 — **저장소를 임의 위치로 복사해 self-test 를 돌린다.**

#### hook 설치 주의 (v4.25.0 문서 보강)

`docs/completion-gates.md` 에 설치 주의 7항을 넣었다. hook 은 fail-open 이라 **잘못 설치해도 에러가 안 난다** — 그래서 문서화하지 않으면 사용자가 차단이 도는 줄 알고 안 도는 상태로 쓴다.

- `hooks.Stop` 은 배열이다. 통째로 복사하면 기존 항목이 사라진다
- hook 은 **병렬**로 돈다(공식 문서). 여러 Stop hook 의 block 합산 규칙은 문서에 없다 `[미검증]`
- ⛔ 캐시 경로에 **버전이 들어간다**. 하드코딩하면 업데이트 후 조용히 꺼진다 → glob + `tail -1` + 빈 값 방어
- ⛔ **개발 모드(`--plugin-dir`)는 캐시 경로 형태로 절대 안 돈다** — 캐시에 새 스크립트가 없다. 소스 우선 폴백을 쓴다
- `python3` 3.9+ 부재 시 fail-open · `~/.fz/stop-hook-state.json` 생성 · 탐색 깊이 3 한계

#### README 재구성

376 → 146줄. 완료 게이트 상세·아키텍처·개발 절차를 `docs/` 로 분리했다. 사전 요구사항을 근거 없는 "필수/권장/선택" 에서 **사용처 수와 폴백 유무** 실측으로 바꿨고(`sc:` 는 15/21 스킬인데 "선택" 이었다), 가이드 표의 stale 을 정정했다(6/9 등재 · harness 1,046 대 실측 1,335줄).

#### 검증

gate self-test **66/66** (임의 위치 복사본에서도 66/66) · stop-hook **14/14** · health-check · lint 위반 0건.

### v4.25.0 (2026-08-25) — 완료 판정을 산문에서 exit code 로 [MINOR]

완료 기준이 SKILL.md 산문 1,723줄에 있었고 그것을 검사하는 코드는 0줄이었다. 모델이 "다 했습니다"라고 말하면 그게 완료였다. 이제 계획의 각 Step 이 실행 가능한 오라클을 갖고 다섯 지점에서 판정된다.

⛔ **여섯 라운드의 작업을 한 릴리즈로 발행한다.** 아래 소절이 그 라운드들이고, 각 소절은 앞 라운드가 못 본 것을 다음 라운드가 찾은 기록이다. 발행 단위는 하나이므로 버전도 하나다.

상세: `docs/releases/v4.25.0.md`

#### 완료 판정을 산문에서 exit code로

18파일(신규 4 · 수정 14) + 신규 `scripts/gate_check.py` 1018줄 · `modules/gates.md` 181줄 · fixture 원장 30개 / 매니페스트 34케이스.

fz는 완료 강제 규칙을 **문서 1,723줄**로 갖고 있으나 그 규칙이 지켜졌는지 판정하는 실행 코드가 **0줄**이었다. 모델이 "Gate 통과"라고 쓰면 그것이 통과였다. 같은 저장소가 `feedback_fail_open_safety_judgment`에 "산문 규칙은 가드 아님"이라 적어 두고도 자기 완료 판정에는 적용하지 않은 자리다.

본 릴리즈는 그 한 칸을 채운다 — **어디서나 동작하는 1차 계층**이다. 세션 종료를 기계적으로 막는 Stop hook은 사용자 설치 대상이라 2차로 분리했다(`modules/governance.md` "훅 설치·설정 변경을 명시 합의 없이 지시·실행하지 않는다" + `examples/hooks.json.example` "자동 배선 금지").

##### 판정기 — `scripts/gate_check.py` (신규)

- **exit 0 AND EXPECT 매치**를 둘 다 요구한다. exit 0만 보면 "실행됐다"만 증명하고, EXPECT만 보면 실패한 프로세스가 에러 텍스트에 성공 토큰을 담았을 때 통과한다
- **exit 4분** — `0` 충족 / `1` 미충족 / `3` invalid-ledger(차단) / `2` 인프라(통과+진단). ⛔ 판정의 fail-open은 금지하고 인프라 부재의 fail-open만 허용한다. `lint_contracts.py`의 3분 구조를 확장한 것
- **정규식 미지원** — Python `re`에 타임아웃이 없어 파멸적 백트래킹을 막을 수 없다. 원장을 fz가 생성하므로 필요가 없고, 지원하지 않으면 그 실패 유형이 통째로 사라진다
- **프로세스 그룹 종료** — 셸을 벗어난 손자가 상속 파이프를 붙잡으면 정산이 안 온다. 실측에서 `(sleep 30 &)` 형태가 **exit 1로 정상인데 30.1초**를 소모했다. pgid를 스폰 직후에 확보(종료 후엔 `getpgid`가 `ProcessLookupError`)해 killpg → **2.1초**
- **CAS writeback** — 최신 재파싱 + 원본 hash 대조 + temp/fsync/atomic replace. 경쟁 writer는 워커가 아니라 **실행 중 원장을 편집하는 사용자**다
- **`APPROVED_ORACLE_HASH`** — 승인 시점의 CHECK/EXPECT/CWD/criterion/timeout/shell/PATH를 묶는다. 없으면 실행 *사이에* CHECK를 쉬운 명령으로 바꿔 **모델이 자기 게이트를 완화**할 수 있다
- **`--confirm`** — MANUAL 게이트는 사용자 stdin 응답이 발급한 토큰이 있어야 충족이다. 비대화형(hook·워커)에서는 exit 2로 거부한다

##### 원장 — `modules/gates.md` (신규)

`{WORK_DIR}/gates/plan.md`에 Markdown으로 산다. `ROOT:`가 소유 디렉토리를, `STATE: active|ready_for_review|closed`가 수명을 표시한다.

⛔ `ready_for_review`가 없으면 fz-code가 원장을 닫아 fz-review의 강등이 영원히 발화하지 못한다. `--set-state`는 **전진만 조건부**다 — 전 게이트 충족 시에만 나아가고, 역행은 증명 없이 허용한다(막으면 재작업이 막힌다).

##### 계약 — `verify: string` → VerifySpec

`workflows/plan-collaborative.js`의 `steps[].verify`를 `oneOf(command, manual)`로 승격했다. 자유 서술 문자열은 사람만 읽을 수 있어 기계가 판정할 수 없었다.

⛔ **fz 전체에 `oneOf` 선례가 0건**이라 Workflow structured output이 수용하는지 몰랐다 — 41줄 격리 프로브로 실측 확인 후 적용했다. 구 계약 문자열은 **manual로 강등**한다(자연어에서 명령을 지어내면 제목과 무관한 oracle이 생긴다).

Stage 4 프롬프트에 oracle 의미 갭 방어 3항목을 넣었다 — `echo ok` 류 금지 · `cmd; echo ok`는 cmd 실패해도 ok가 찍히니 `&&` 사용 · 판정 불가면 억지 command 대신 manual.

##### 배선 3지점 + 검사 2개

| 지점 | 동작 |
|---|---|
| fz-plan Phase 1·2·3 | draft 생성 → 게이트별 Codex 판정 → 확정 |
| fz-code 절차 6.4 | Step 게이트 실행 + STATE 전진 |
| fz-review Phase 5.5 | `--reverify` 강등 + guardian `regressed` 차단 |

- `scripts/health-check.sh`에 self-test 배선 — 없으면 판정기가 회귀해도 `/fz-manage check`가 통과한다
- `schemas/codex_gate_verdict_schema.json` 신규 — 게이트당 판정 1행(통과분 포함)이라야 N/N 대조가 성립한다. `codex_review_schema`의 issues 배열은 문제만 담아 전수 확인이 불가능하다

##### lint 정정 2건

- **#N1이 비-issue 스키마를 오분류** — `schemas/*.json` 전부를 issue로 가정해, 게이트 처분(`accept/revise/demote_to_manual`)을 담는 새 스키마를 "severity 부재"로 잡았다. severity(문제 심각도)와 verdict(게이트 처분)는 축이 다르다. 억지 필드를 넣는 대신 검사 범위를 정정했다
- **#N3이 밀린 인용을 잡았다** — 편집으로 줄이 1줄 밀려 `promotion-ledger.md`의 `fz-plan/SKILL.md:388` 2건이 빈 줄을 가리켰다. 이 검사가 존재하는 이유 그대로다

##### 리뷰 후 수정 — critical 10건

첫 구현은 Codex 코드 리뷰에서 **rejected**(critical 10)를 받았다. 중앙 주장이 성립하지 않았다 — `CHECK: false` + 손으로 쓴 `EVIDENCE: forged`가 `ALL MET`을 받고 전진까지 성공했다.

- **증거를 oracle에 묶었다** — `EVIDENCE:`의 `sig=`가 `oracle_hash + exit + output`에 결속된다. 검사 위치를 `evaluate`(실행 경로)에서 `gate_state`(판정 함수)로 옮겨 `--status`도 도달한다. ⛔ 암호학적 위조 방지가 아니라 *우연한* false-green 차단이다
- **MANUAL 토큰 재계산** — `CRITERION_HASH`는 원장에 적힌 공개값이라 복사 가능했다
- **수명주기 가드를 실행체에 넣었다** — 문서가 선언한 `STATE: closed` no-op와 `FZ_GATES_OFF` kill-switch를 `evaluate()`가 전혀 보지 않았다
- **인접 전이 강제 + fresh 파스** — `active → closed` 직행이 fz-review를 건너뛰었고, `set_state`가 호출 전 파스로 판정했다
- **`--from-plan`을 fz-plan Phase 3.1에 배선** — 만들어 놓고 아무도 호출하지 않아 원장이 생기지 않았다. 원장이 없으면 배선 2·3이 전부 no-op이다
- **절대 경로 강제** — `python3 scripts/gate_check.py`는 설치된 플러그인에서 대상 레포에 없어 exit 2(인프라 통과)로 강제력이 조용히 사라진다
- **`--only` 게이트 선택자** — 전 게이트를 돌리면 미래 Step이 실패해 첫 Step에서 영구 정지한다
- **개행 인젝션 차단** — plan의 command에 `\nABANDON: G1 …`을 넣으면 포기된 게이트로 파싱됐다
- **`OSError` → exit 2** — 파일시스템 오류가 traceback으로 새어 "미충족(차단)"으로 오독됐다
- **`--help` exit 0** — argparse의 `SystemExit(0)`까지 인프라 오류로 변환하고 있었다

##### 검증

self-test **34/34** · health-check 전 검사 통과 · lint 위반 0건 · workflow 문법 6개 OK · `--help` exit 0.

⛔ **음성 대조를 매번 돌렸다** — 회귀를 주입해 게이트가 실제로 실패하는지 확인했다. pgid 수정 제거 → `30.0초 (한도 6초)` 검출 / `gate_check.py` 제거 → health-check exit 2 / 문자열 강등 제거 → `exit 2 (기대 0)` / issue 스키마 severity 제거 → #N1 발화.

⛔ **self-test가 놓친 것이 두 번 있었다.** ① 손자 프로세스 hang은 exit code로는 정상이었다(30.1초 소요) — `max_seconds` 추가. ② forgery fixture 4개가 음성 대조를 통과하지 못했다 — `exit`/`mutates` 두 축으로는 같은 exit을 내는 방어선이 구분되지 않는다. `expect_contains`(산출물 내용)와 `expect_stdout`(거부 사유)를 추가해 **4종 주입 → 4건 검출**로 만들었다.

게이트 도입이 게이트 품질을 보장하지 않는다. 관측 축이 없으면 게이트는 자기 대상의 실패를 못 본다.

#### 게이트가 자기 대상을 못 보던 자리

`/fz-codex verify`가 개선 플랜을 **rejected**(critical 3 · major 8 · minor 2)로 판정했다. 재분석의 두 핵심 사실은 확인됐고(gate verdict 스키마의 실행 경로 0건 · wiring 생략을 검출하는 장치 0건) **해결책이 반박됐다**.

##### 계약 보존 — `verify-gates` 신설

`verify`의 스키마를 바꿔치기하려 했는데, `codex_gate_verdict_schema`에는 `issues`·`verdict`가 없다. 교체하면 fz-plan의 Issue Tracker 기록·scope challenge·Gate 2 승인 입력이 **사라진다**. 별도 호출로 분리했다 — 계획이 옳은가(`verify`)와 게이트가 그 계획을 측정하는가(`verify-gates`)는 관심사가 다르다.

스키마 선택만으로는 N/N이 보장되지 않는다. 스키마는 `gates: []`·중복 id·원장에 없는 id·거짓 `summary` 합계를 전부 통과시킨다 → 호출자 사후 대조를 계약으로 넣었다.

##### 같은 파일의 형제를 놓쳤다

fz-plan **3.1만 고치고 4.5의 상대 경로를 남겼다.** 설치된 플러그인에서 exit 2로 떨어져 invalid-ledger 검증이 fail-open 된다. exit 0/1/2/3별 호출자 행동도 명시했다.

##### 실행 환경

- **`stdin=DEVNULL`** — 미지정이면 터미널·상위 파이프를 상속해 CHECK가 입력을 기다리면 게이트당 120초를 잡아먹는다. 직전 라운드에서 "2차 계층 의존"으로 내렸던 판단을 **철회**했다. 1차 실행 경로에서 발현한다
- **`ROOT:` 소유 판정** — 문서가 "realpath 절대경로"를 선언하는데 코드는 존재만 봤다. ⛔ realpath **일치**는 요구하지 않는다. macOS의 `/var → /private/var`처럼 정상 경로도 심볼릭을 거쳐 fixture 21건이 깨졌다 — 필요한 건 정규형 강요가 아니라 소유 판정이다
- **drain을 게이트 deadline과 공유** — 고정 1초 grace가 정상적인 지연 출력을 잘랐다. ⛔ 계획의 `min(DRAIN_GRACE_S, 잔여)`는 상수가 1.0이라 **산술적으로** 3초 출력에 도달 불가였다. 기준은 "더 기다려서 판정이 바뀔 수 있는가" 하나 — EXPECT가 이미 매칭됐으면 끊는다
- **강제 종료 기록** — exit 0 + EXPECT 매칭이어도 손자를 죽였으면 증거에 `killed=descendant`. 판정은 뒤집지 않는다(서버를 띄우는 정당한 CHECK를 실패시키면 안 된다)

##### 실패의 방향을 골랐다

`EXPECT:`의 `startswith("/")` 검사가 `/tmp/result` 같은 경로 리터럴까지 거부했다. `/var/log/`처럼 애매한 형태는 **거부가 아니라 리터럴 + 경고**다 — 정규식을 리터럴로 취급하면 게이트가 빨갛게 실패해 저자가 알아채지만, 경로를 거부하면 정당한 게이트가 원장 검증에서 통째로 막힌다.

writeback CAS도 같은 축이다. 전체 파일 해시는 **무관한 형제 편집**에도 exit 3으로 죽어 실행 결과를 잃었다 — 판정을 지키려고 판정을 버린다. 대상 게이트 블록으로 좁혔고, 제목을 범위에 넣었다(제목이 바뀌면 같은 증거가 다른 주장에 붙는다).

##### ⛔ fixture 4건이 자기 대상을 못 보고 있었다

이번 라운드에서 가장 값진 발견이다.

| fixture | 무엇을 못 봤나 |
|---|---|
| `root-relative` | 절대경로 검사를 제거해도 뒤의 `is_dir`가 같은 exit 3을 내서 통과했다 → **`expect_stderr` 축 신설** (거부 **사유**는 stderr로 나간다) |
| 소유 검사 | 어떤 fixture도 관측하지 않았다(제거해도 37/37) → `root-foreign`(ROOT=/usr) 신설 |
| `writeback-sibling-edited` | sed 패턴이 **자기 CHECK 줄에도 있어** 자기를 고쳤다. 이름은 sibling인데 `oracle-changed`와 같은 축을 봤다 → 새 형제를 append하도록 재작성 |
| `exec-late-descendant` | 지연 2초일 때 옛 코드가 **타이밍으로 통과**했다(스레드 2개 × 1초 join = 2초) → 4초로 늘려 여유 제거 |

##### 실사용 검증 + `FZ_GATES_TRACE`

SKILL.md에 적힌 명령을 그대로 뽑아 실행했다. 배선 3종 전부 발화하고 전 수명주기(draft → 확정 → Step 판정 → 강등 → ABANDON → ready_for_review → closed → no-op)가 동작했다. **001 재발이 아니다.**

⛔ 관측을 **플래그가 아니라 환경변수**로 만들었다. 플래그면 SKILL.md 호출 줄을 고쳐야 하고, 그러면 관측이 관측 대상(배선)에 의존해 순환한다.

⛔ trace가 보이는 것은 "명령이 동작한다"이고 "미래의 Lead가 산문 지시를 읽고 실행한다"가 아니다. 그 재귀를 끊는 것은 Stop hook뿐이고 사용자 설치다. health-check 배선은 WORK_DIR discovery가 미설계라 2차와 함께 정한다.

##### ⛔ 배선을 고쳐도 스키마가 로드되지 않았다

`verify-gates` 배선을 `grep -c`(언급 수 2/1/1)로 완료 판정했다. **1회 실행하니 API가 거부했다.**

```
invalid_json_schema: 'required' is required to be ... including every key in properties. Missing 'suggestion'
```

011을 유죄로 만든 기준이 **"실행 경로 0건"**인데 내 수정에는 *언급 수*라는 더 약한 오라클을 썼다. 같은 라운드의 다른 방어선 11종은 전부 개별 제거 probe로 확인했는데 이것만 오라클이 없었다.

strict 모드 관례를 형제 스키마에서 실측했다 — **전 필드 `required` + optional은 nullable + 전 객체 `additionalProperties: false`**(`codex_review_schema.json` 6/6). 수정 후 실행 성공: 3게이트 in / 3판정 out, id 집합·summary 합계 일치, MANUAL이 `noninteractive=False`로 분류.

⚠️ **`schemas/codex_verification_schema.json`이 같은 위반을 갖는다** — 실제 호출로 같은 400을 확인했다. `validate`(fz-review Phase 5.5)가 이 스키마를 쓰므로 그 경로는 구조적으로 실행 불가다. **범위 밖이라 고치지 않았다** — 어느 필드를 nullable로 둘지가 validate 계약의 의미 판단이고, lint 스키마 구조 검사 추가와 한 쌍으로 결정해야 한다(검사만 넣으면 lint가 즉시 막힌다).

##### N/N 대조를 산문에서 코드로 — `--verdict-check`

스키마는 `gates: []`·중복 id·원장에 없는 id·거짓 `summary` 합계를 전부 통과시킨다. 대조를 산문 지시로 두면 **이 계층이 없애려는 것과 같아진다** → `--verdict-check <응답.json>`이 4축을 판정한다.

⛔ 개수만 세면 안 된다 — 중복 id가 누락을 가린다(`G1` 두 번 + `G3` 없음이 3개로 보인다). fixture 6종 + 4축 개별 제거 관측.

##### ⛔ 명시한 교환 — 블록 CAS는 단일 writer를 가정한다

전체 파일 CAS는 형제 편집 위양성을 만드는 대신 *다른* 것을 막고 있었다: 게이트 A·B의 writeback이 겹치면 `write_atomic`이 파일 전체를 replace하므로 나중 쓰기가 앞 쓰기를 **덮는다**. 블록 CAS는 그 충돌을 못 본다.

설계된 흐름(Lead 순차)에서는 창이 없고, 열리는 것은 **Stop hook이 Lead 호출과 동시에 도는 경우**뿐이므로 파일 lock을 2차 계층 선행 조건으로 뒀다. 지금 안 넣은 이유 — `write_atomic`이 `os.replace`로 inode를 바꿔 대상 파일 `flock`이 옛 inode에 남는다. 별도 lock 파일의 수명·정리·stale 처리를 설계해야 한다.

##### 검증

self-test **49/49** · health-check 전 검사 통과 · lint 위반 0건 · workflow 문법 6개 OK · `--help` exit 0. 방어선 7종을 **개별 제거**해 각각 독립 관측을 확인했다. `scripts/gate_check.py`     1216줄 · `modules/gates.md`      238줄 · fixture 49케이스.

#### 검사는 있는데 발화하지 않던 계약

구현 리뷰가 **rejected**(critical 4 · major 3 · minor 2 · suggestion 1). 네 critical 전부 독립적인 false-green 경로였고, 전부 재현 확인 후 수정했다.

##### ⛔ 승인 계약이 한 번도 발화하지 않았다

`APPROVED_ORACLE_HASH` 검사는 코드 **3곳**에 있었는데 **발급하는 곳이 없었다.** 그래서 필드가 원장에 들어가지 않고, `gate_state`·`evaluate` 는 "있을 때만" 대조하므로 검사가 영원히 잠들어 있었다. 실측: 승인된 lint 실행을 `echo <기대문자열>` 로 바꿔도 PASS.

⛔ 011(스키마 실행 경로 0건)과 **같은 부류**다 — 검사가 존재하는 것과 발화하는 것은 다르다.

- `render_ledger` 가 command 게이트의 `criterion` 을 **버리고 있었다.** VerifySpec 이 요구하는 필드인데 원장에 안 남기면 승인받은 "무엇을 재는가"가 사라지고 CHECK 만 남는다 → `CRITERION:` 보존 + `oracle_hash` 에 포함(제목도 함께)
- **`--finalize`** 신설 — 실행 게이트마다 도장을 찍고 `APPROVED: yes` 를 남긴다. fz-plan 4.5가 호출한다
- 확정본에 **부분 도장은 exit 3** — 도장이 있으니 보호받는다고 읽히는데 안 찍힌 게이트는 CHECK 를 바꿔도 통과한다. 무도장보다 위험하다
- draft 는 경고만 — 도장을 요구하면 순서가 뒤집힌다(Phase 2 평가자가 볼 CHECK 가 도장보다 먼저 있어야 한다)

##### 파서와 writeback 이 문법을 공유하지 않았다

`gate_block_hash`·`apply_result` 가 **자체 스캐너**로 라인을 다시 찾아, 파서가 건너뛰는 **펜스(```) 내부**를 몰랐다. 실측: 문서 예시의 `- [ ] G1:` 이 `- [x]` 로 고쳐지고 **증거까지 박혔다** — 같은 서명이 두 주장에 붙었다.

→ 파서가 게이트별 라인 스팬을 기록하고 hashing·editing 이 그것만 쓴다. **파서가 SSOT다.** CRLF 정규화도 한 곳으로 모였다. 쓴 결과를 디스크에서 다시 읽어 met 을 판정한다.

##### ROOT 를 검증한 경로와 실행한 경로가 달랐다

검증은 realpath 로 하고 실행은 헤더 **원문**을 썼다. 그 사이 심볼릭을 다른 디렉토리로 돌리면 CHECK 가 딴 곳에서 돌고, 증거 서명은 바뀌지 않은 *표기*에만 묶여 나중 `--status` 는 met 으로 읽는다(TOCTOU). → 검증된 정규 경로를 저장해 실행·해시·증거 전부 그것을 쓴다.

##### `--verdict-check` 가 거짓 응답을 통과시켰다

id 집합·개수·합계만 봤다. 필수 필드·enum 미확인, `summary` 를 배열과 대조하지 않아 음수 상쇄가 가능했고, **제목이 바뀌어도 id 는 같으므로 stale 응답이 통과**했다.

→ 필수 10필드 + verdict enum 확인 · `(id, title, kind)` 삼중 결속 · `summary` 를 배열에서 **재계산**해 비교 · 음이 아닌 정수 요구.

##### ⛔ "streaming capture" 가 사실이 아니었다

`stream.read(8192)` 은 **8192바이트가 모이거나 EOF 까지 블록**한다. docstring 이 실행 중 capture 라 썼지만 짧은 출력은 프로세스 종료 시 한꺼번에 도착했다 — EXPECT 조기 매칭(v4.25.1 의 S6)도 출력 상한 감지도 실행 중에 발화하지 못했다.

**음성 대조가 이걸 잡았다.** 경계 fixture 를 주입 전후로 돌렸는데 둘 다 3.1초로 동일했다. `read1` 로 고치자 비로소 판별됐다.

- `_matched()` 가 stdout·stderr 를 **개행 없이** 이어 붙여 경계에서 needle 을 합성했다 — stdout=`he` + stderr=`llo` 가 EXPECT=`hello` 에 걸려 조기 kill 을 유발하고 뒤에 오는 진짜 출력을 잃는다. EXPECT 는 개행을 담을 수 없으므로 **스트림별 검색**이 최종 판정과 정확히 같은 의미다
- decode 도 없애 bytes 로 찾는다(1MiB 를 50ms 마다 디코딩하면 120초 대기에서 누적 2.4GiB)

##### 증거가 왕복하지 않았다

정상 출력에 `;` 가 있으면(`echo "done; cleanup=ok"`) `parse_evidence` 의 분해가 잘려 재계산 서명이 어긋나고 **통과한 게이트가 unmet 으로 읽혔다**(fail-red). `ev_enc`/`ev_dec` 역함수 쌍으로 `%`·`;` 를 escape 하고 서명을 escape 된 값 위에서 계산한다.

##### 나머지

- `verify-gates` 절이 `plan.draft.md` 를 하드코딩해 fz-review(확정 원장 대상)가 쓸 수 없었다 → 원장을 호출자 파라미터로. fz-review 에 `--verdict-check` 후속도 명시
- EXPECT 판별에 메타문자 경고 추가(`/foo/g`·`/^ok$/`). **알려진 오거부**(`/tmp/i`)를 문서화 — 완전한 판별자는 존재하지 않는다
- lint `#N1` 이 파일명 목록으로 non-issue 스키마를 걸렀다(주석이 거부한 바로 그 결합) → `issues` 배열 유무로 **의미 판정**. 새 스키마를 넣어도 린터를 안 고친다
- `guides/skill-authoring.md` §11 에 **공유 스크립트 예외** 추가 — 소비자가 2개 이상이면 리포 루트 `scripts/`

##### 검증

self-test **61/61** · health-check · lint 위반 0건 · workflow 6개 · `--help` exit 0.

방어선 9종을 개별 제거해 **8종 관측**을 확인했다. 미관측 1종(`evaluate` 사후 재확인)은 재현 입력이 없어 매니페스트 `_notes` 에 **미관측임을 명시**했다 — "통과했다"가 "관측됐다"를 뜻하지 않는다.

⛔ `oracle_hash` 민감도는 원장 fixture 로 볼 수 없다(`path_fingerprint`·`SHELL` 이 머신마다 다르다) → `--oracle-fields` 순수 함수 매트릭스로 관측한다.

`scripts/gate_check.py` 1461줄 · `modules/gates.md` 265줄 · fixture 61케이스.

#### 스키마가 API 에 로드되지 않던 자리

##### `validate` 경로가 구조적으로 실행 불가였다

`schemas/codex_verification_schema.json` 이 structured output strict 모드를 위반해 `invalid_json_schema` 400 을 받는다 — **스키마가 로드조차 되지 않는다.** 이 스키마는 `validate`(fz-review Phase 5.5 역방향 검증)가 쓰므로 그 경로 전체가 죽어 있었다. 파일이 존재하고 JSON 으로 파싱되면 통과했으므로 어느 검사도 잡지 못했다.

전 스키마를 스캔했다 — 6개 중 `--output-schema` 로 **실제 전달되는** 것은 4개이고, 그중 1개가 위반이었다. `issue_tracker_schema.json` 은 Issue Tracker 산출물 형식(`modules/session.md:126`)이고 codex 응답이 아니라 대상이 아니다. `codex_base_issue_schema.json` 은 `$defs` 참조용이다.

변환은 기계적이다 — `required` 에 없던 필드(작성자가 optional 로 의도한 것)를 **nullable 타입 + required** 로 바꾼다. `codex_review_schema.json`(6/6 준수)의 선례이고 의미가 보존된다. 소비처가 읽는 `resolution_status` 4축은 이미 required 였고, `validate-codex-output.py` 가 `"null"` 타입을 지원한다.

⛔ **실행으로 확인했다** — `GATE-PASS`, nullable 필드가 `null` 로 정상 반환. F-040("선언된 산출물은 1회 실행이 완료 조건")을 적용했다.

##### ⛔ 수정 스크립트가 자기 blind spot 을 재검산과 공유했다

`location` 을 nullable 로 만들면 `type` 이 `"object"` → `["object","null"]` 이 된다. 그러면 `type == "object"` 조건에서 빠지는데, **재검산도 같은 조건을 써서 함께 놓쳤다.** "위반 0건"을 보고했지만 한 객체가 남아 있었다.

`type` 리스트를 포함하도록 고치고, 고정점까지 반복하게 만들었다(한 라운드가 새 nullable 객체를 만들면 다음 라운드 대상이 된다).

##### lint `#N10` — structured-output strict 준수

⛔ **대상은 사용처가 정한다.** 파일명 목록(#N1 의 과거 결합)도, top-level `properties` 유무도 기준이 아니다 — `--output-schema`/`--schema` 로 전달되는 것만 검사하고, 미배선 스키마는 위반이 아니라 정보로 알린다. 새 스키마를 추가하면 **배선하는 순간** 검사에 들어온다.

음성 대조 3축: required 누락 · `additionalProperties` 누락 · **nullable object 안쪽**(type 리스트 blind spot) 각각 검출.

##### 원장 파서 fail-closed

- **헤더 중복 선언 거부** — ⛔ 실질 false-green 이었다. 마지막이 이기는 규칙이라 `STATE: closed` 를 한 줄 append 하면 원장 전체가 no-op 이 된다. `ABANDON:` 처럼 흔적이 남는 이탈로가 아니라 **조용한 무력화**다. `ROOT:` 중복은 실행 디렉토리를 바꾼다
- **게이트 밖 들여쓰기 속성 거부** — 오타로 게이트 줄이 빠지면 그 CHECK 가 통째로 사라지는데 파서가 아무 말도 하지 않았다. 게이트 수 감소를 알아챌 오라클이 없다


##### ⛔ 승인 도장이 환경에 흔들려 cross-session 파이프라인을 막았다

외부 검토가 잡았다. `oracle_hash` 에 `SHELL` 과 `path_fingerprint()` 가 들어 있고, 그 해시가 **승인 도장의 비교 대상**이었다.

```
fz-plan  세션 A: --finalize → APPROVED_ORACLE_HASH = sha(… | PATH_A | SHELL_A)
fz-code  세션 B: --only S1  → oracle_hash          = sha(… | PATH_B | SHELL_B)   → exit 3
```

실측 — PATH 만 바꿔도, SHELL 만 바꿔도 각각 **exit 3(차단)**. 메시지는 "승인 후 oracle 이 바뀌었다. 재승인이 필요하다"라며 원인을 잘못 지목한다. oracle 은 안 바뀌었고 환경이 바뀐 것이다.

⛔ **추가 발견** — 증거 서명도 같은 병이었다. `--status` 를 다른 PATH 로 돌리면 통과한 게이트가 **UNMET** 으로 읽혔다.

fz-plan → fz-code 가 별 세션인 것은 예외가 아니라 설계된 흐름이다(compact · 다음 날 · 다른 터미널 · direnv/nvm shim). 같은 세션 안에서만 검증했기 때문에 probe 가 통과했다 — **cross-session 을 건드리는 검증이 하나도 없었다.**

두 해시의 목적을 분리했다.

| 해시 | 무엇을 묶나 | 환경 |
|---|---|:---:|
| 승인 도장 | 사람·Codex 가 승인한 oracle | ⛔ 제외 |
| 증거 서명 | 이 결과가 어느 환경에서 나왔나 | ✅ 포함 (**기록된** 값으로 재계산) |

증거 필드 `path=` 를 `env=` 로 바꾸고 **서명에 묶었다.** 이전엔 기록만 되고 서명 밖이라 provenance 가 실제로 보호되지 않았다.

⭐ **부수 이득** — 승인 해시가 머신 독립이 되어 `CWD:` 고정 시 결정론적이다. `approved-oracle-swapped` fixture 의 도장을 더미 `000000000000` 에서 **실제 계산값**으로 바꿨다. 이전엔 "불일치"가 아니라 "아무 값과도 불일치"를 보고 있었다 — 대조 로직을 실제로 관측하지 못했다.

`--cross-session` 하네스 모드 신설 — 한 프로세스 안에서 환경을 바꿔야 하므로 원장 fixture 로는 볼 수 없다.

##### `--finalize` 가 CAS 규율 밖에 있었다

다른 모든 쓰기 경로가 블록 해시를 대조하는데 확정만 baseline 비교가 없었다. 단일 writer 가정으로 덮이지만 "가정으로 보호된다"와 "규율 밖에 있다"는 다르다.

##### `#N10` 스캔 범위 한정

전 트리를 훑으면 `docs/releases/`·`CHANGELOG.md` 의 **산문**이 배선으로 오인된다 — "`--schema schemas/foo.json` 이 깨져 있었다" 같은 문장 하나로 은퇴한 스키마가 검사 대상에 편입된다. `MIN_HITS` 는 축소만 잡고 확대는 못 잡는다. 배선 디렉토리(`modules`·`skills`·`scripts`·`workflows`·`agents`·`codex-skills`)로 한정했다.

##### 검증

self-test **65/65** · health-check · lint 위반 0건(`#N10` 검사 대상 17객체) · workflow 6개 · `--help` exit 0. `scripts/gate_check.py` 1554줄 · `modules/gates.md` 274줄.

##### 보류 (이유 명시)

- **파일 lock** — 블록 CAS 의 단일 writer 가정. 창이 열리는 것은 Stop hook 이 Lead 호출과 동시에 도는 경우뿐이므로 **소비자(2차 계층)와 함께** 만든다. 지금 만들면 소비자 없는 방어다
- **2차 계층(Stop hook)** — 차단 형식 probe 가 live 세션을 필요로 하고(백그라운드에서 세션 종료를 관측할 수단이 없다) hook 설치는 사용자 합의 사항이다. probe 없이 hook 을 쓰면 "검증 안 된 산출물"이 되어 이번에 세 번 만난 실패 모드의 재발이다

#### 2차 계층: 산문 배선의 재귀를 끊는다

1차 계층(fz-plan·fz-code·fz-review 배선)은 **SKILL.md 산문**이다. Lead가 건너뛰어도 아무 신호가 없다 — 이 도구가 대체하려던 것이 산문 강제인데, 그 도구를 부르는 것 자체가 산문이었다. 재귀가 한 층 위로 올라갔을 뿐이다.

`scripts/gate_stop_hook.py` (324줄)가 그 재귀를 끊는다. 세션 종료 시 `cwd` 하위 확정 원장을 찾아 미충족이면 종료를 막는다.

##### ⛔ probe 없이 차단 계약을 확정했다

"live 세션이 필요하다"고 판단해 보류했던 항목이다. 실제로는 **공식 문서가 답을 갖고 있었다** — `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/hook-development/`.

```
입력 (stdin JSON): {"session_id":…, "transcript_path":…, "cwd":…, "hook_event_name":"Stop"}
차단:              stderr ← {"decision":"block","reason":"…"}  +  exit 2
```

⛔ 세 후보 중 `hookSpecificOutput.decision` 도 `{"continue": false}` 도 아니고 **top-level `decision`** 이다. 세션 감금 위험도, hook 등록도 필요하지 않았다.

부수 확인 — 사용자 환경에 이미 Stop hook 17종이 배선돼 있었다. `guides/harness-engineering.md:1159` 의 "Claude Code lifecycle hook 0건"이 stale이었고 정정했다.

##### 설계 결정 3가지

| 결정 | 이유 |
|---|---|
| 원장 발견 = `cwd` 하위 glob | `session_id`가 오므로 세션 바인딩도 가능하지만 **쓰는 쪽 배선**이 필요하고, 그 배선이 빠지면 hook이 원장을 못 찾아 조용히 무력화된다 — 이번 작업에서 다섯 번 만난 축이다. glob은 배선이 0이고 여러 원장을 전부 본다 |
| 판정 = `--status` (재실행 없음) | 재실행은 게이트당 기본 120초여서 hook에 부적합. 기록된 증거는 서명으로 oracle에 묶여 있다 |
| 전면 fail-open | "세션 감금이 게이트 누락보다 나쁘다"가 가장 날카롭게 적용되는 자리다 |

⛔ **무한 루프 방어** — Stop을 막으면 Claude가 계속하고 다시 Stop에 도달한다. 원장 상태가 그대로면 같은 이유로 또 막혀 세션이 끝나지 않는다. 같은 상태(원장 해시)로 **2회**까지만 막는다. 상태를 못 쓰면 즉시 통과 — 방어 없이 막으면 무한 block이다. 공식 문서에 `stop_hook_active` 같은 필드가 없어(grep 0건) 스크립트가 직접 방어한다.

##### ⛔ 차단이 영원히 발화하지 않던 버그

첫 격리 테스트에서 `decision=block` JSON은 stderr로 나갔는데 **exit이 0**이었다.

```python
try:
    sys.exit(main())              # SystemExit 을 던진다
except BaseException as exc:      # ⛔ SystemExit 도 BaseException 이다
    sys.exit(EXIT_PASS)           # → 항상 0
```

최후 방어가 자기 exit을 삼켰다. **차단 코드가 있는데 발화하지 않는 것** — 이 작업에서 다섯 번째로 만난 축이다(011 스키마 · verification 스키마 · 승인 도장 발급 · N10 부재 · 이번). `sys.exit()`을 try 밖으로 빼고 `except Exception`으로 좁혔다.

##### 검증 — 등록 없이 계약까지

`--self-test` 6케이스를 내장하고 health-check 2.6에 배선했다. hook 등록은 사용자 소관이므로 **계약까지가 우리가 닫을 수 있는 경계**다.

```
no-gates-dir · depth1~4 · draft-only · skip-git · closed-passes
approved-unmet · kill-switch · wrong-event · bad-cwd · env-missing · loop-guard
```

린터가 새 스크립트의 두 계약 위반을 즉시 잡았다 — `#N2`(인벤토리 12≠13)와 `#N6`(루트 앵커 화이트리스트). 형제 `gate_check.py`와 동일한 앵커 형태로 맞췄다.


##### ⛔ 원장 발견 glob이 실사용 경로를 놓쳤다

외부 검토가 잡았다. `*/gates/plan.md` — 깊이 정확히 2다. 실측하니 4종 중 **1종만** 발견됐다.

```
{CWD}/gates/plan.md          깊이 1  → ⛔ 미발견 (조용히 통과)
{CWD}/ASD-1/gates/plan.md    깊이 2  → ✅ 발견
{CWD}/a/b/gates/plan.md      깊이 3  → ⛔ 미발견
{CWD}/a/b/c/gates/plan.md    깊이 4  → ⛔ 미발견
```

self-test fixture가 **정확히 깊이 2로만** 원장을 만들었기 때문에 관측되지 않았다 — 이 작업에서 여덟 번 만난 "fixture가 자기 이름의 축을 못 본다"의 아홉 번째다.

깊이 0~3 명시 목록으로 넓혔다(`rglob`은 큰 트리에서 hook을 늘어지게 만든다). `.git`·`node_modules` 등은 건너뛴다.

⛔ **`cwd` 밖은 설계 한계다.** 워크트리에서 작업하고 원장이 리포 루트에 있으면 어떤 glob으로도 못 찾는다 — hook은 `cwd`만 받는다. `FZ_GATES_LEDGER`로 명시 지정하는 탈출로를 뒀다.

⛔ **"찾지 못함"이 조용했다.** 게이트 미사용 세션과 미발견이 둘 다 침묵이라 놓친 원장이 통과로 보였다. `gates/`가 아예 없으면 조용히 통과하고, `gates/`는 있는데 확정 원장이 없으면 stderr로 남긴다.

self-test를 6 → **14케이스**로 늘렸다. 방어 7종을 개별 제거해 **7종 전부 관측**했다 — 깊이·미발견 진단·SKIP_DIRS·탈출로·`SystemExit` 포획·차단 자체·**무한 루프 방어**.

⚠️ `loop-guard`는 처음에 미관측이었다. 방어를 제거해도 통과했다 — 같은 상태로 **반복 발사**하는 케이스가 없었기 때문이다. `REPEAT_CASES`를 추가해 `MAX_BLOCKS+1`회 쏜 뒤 마지막을 본다.

⚠️ `approved` fixture를 만들 때 닭-달걀을 만났다 — 도장을 계산하려면 파싱해야 하는데 `APPROVED: yes`면 파싱이 전수 도장을 요구한다. draft로 쓰고 `--finalize`에 맡기는 것이 정답이었다.

##### 검증 (전체)

gate self-test **65/65** · stop-hook self-test **14/14** · health-check 전 검사 통과 · lint 위반 0건 · workflow 6개 · `--help` exit 0.

`scripts/gate_check.py` 1554줄 · `scripts/gate_stop_hook.py` 435줄 · `modules/gates.md` 306줄.

##### 남은 것

**파일 lock** — 블록 CAS의 단일 writer 가정. 2차 계층이 생겼으므로 이제 창이 열린다(hook이 Lead 호출과 동시에 돌 수 있다). 다만 hook은 `--status`만 쓰고 **쓰기를 하지 않으므로** 실제 경합은 여전히 없다 — 판정기 두 프로세스가 동시에 쓰는 경우만 남는다.

#### hook 미설치 머신의 노출 경로

##### S16(`--merge` + BATCH manifest) 폐기

원 플랜의 마지막 미결 항목이었다. 실측하니 전제가 바뀌어 있었다.

```
execution-modes.md BATCH 절     10건
experiment-log BATCH 기록         0건   ← 실사용 흔적 없음
/batch 스킬                       0개
BATCH 경로의 게이트 배선           0건
```

⛔ **소비자가 없다.** hook 은 각 worktree 에서 그 안의 원장을 이미 찾으므로(깊이 0~3) 병합 없이도 독립 판정된다. `--merge` 는 종합 보고 편의이지 기능 요건이 아니고, BATCH 자체가 안 쓰이므로 거기에 배선을 넣으면 **미사용 위에 미사용을 얹는다.**

이 작업이 15회 만난 지배 축이 "선언·구현했는데 소비자·발화가 없다"였다. 그 축의 16번째가 되지 않게 폐기한다.

##### 대신 — health-check 원장 노출 (배선 5지점)

`plan-v5` 에서 이 사유로 보류했던 항목이다.

> `health-check.sh` 는 자기 위치에서 **plugin ROOT만** 안다. 외부 WORK_DIR 을 찾는 기전이 없다

⭐ **그 기전이 2차 계층에서 생겼다.** `find_ledgers()`(깊이 0~3 + `SKIP_DIRS` + `FZ_GATES_LEDGER`). 보류의 전제가 사라졌다.

이것이 **hook 미설치 머신의 유일한 노출 경로**다 — 배선 1~3은 산문이고 `FZ_GATES_TRACE` 는 환경변수 opt-in 이다.

| 상태 | exit | 이유 |
|---|:---:|---|
| 미충족 | **0** | 작업 중 정상 상태. exit 에 반영하면 사람이 health-check 를 안 돌린다 (`lint_doc_freshness` 선례) |
| 계약 위반 | **3** | plugin 자산 결함 — health-check 의 관심사 |

##### ⛔ discovery 를 판정기로 옮겼다 — 두 구현이 갈리지 않게

`find_ledgers` 가 hook 에만 있었다. health-check 가 자체 구현을 가지면 한쪽이 놓치는 배치가 생긴다 — **깊이 2만 보던 결함이 정확히 그것이었다.** 판정기로 옮기고 hook 이 `importlib` 로 빌려 쓴다. 린터의 선례와 같은 원칙이다(`lint_contracts.py:804` "chk_N6 와 self-test 가 **같은 함수**를 쓴다").

⛔ 이동 중 `LEDGER_ENV` 정의를 hook 에 남기지 않아 `NameError` 가 났고, hook 의 전면 fail-open 이 그것을 **조용한 통과**로 바꿨다 — self-test 가 14 → 6/14 로 잡았다. fail-open 의 대가이고, 그래서 self-test 가 필요하다.

##### 검증

gate self-test **66/66** · stop-hook self-test **14/14** · health-check 전 검사 통과 · lint 위반 0건.

discover 방어 3종 개별 제거 → **3종 전부 관측**: 계약위반 exit 반영 · 미충족 상세 보고 · **discovery 함수 공유**(hook 이 자체 구현을 쓰면 hook FAIL 6건).

⚠️ `미충족` 기대 문자열 하나로는 상세 줄 제거를 관측하지 못했다 — 요약줄에도 `미충족 0` 이 나오기 때문이다. 상세 줄 형태(`  미충족 <경로> — ['G1']`)와 요약 수치(`미충족 1`)를 나눠서 본다.

⚠️ fixture 원장을 sandbox 전체에서 찾으려던 첫 시도가 0건이었다 — 다른 fixture 는 파일명이 `plan.md` 가 아니다(`pass.md`·`ledger.md` …). `discover/` 하위에 충족·미충족·계약위반 세 트리를 `<sub>/gates/plan.md` 배치로 새로 만들었다.

`tests` 를 탐색에서 제외했다 — fixture 원장은 테스트 자산이고 작업 원장이 아니다.

`scripts/gate_check.py` 1689줄 · `modules/gates.md` 316줄 · fixture 66케이스.

### v4.24.0 (2026-08-24) — 게이트가 조용히 꺼져 있던 자리를 닫았다 [MINOR]

18커밋 · 23파일 `+1,215 −112`. 직전 릴리즈 v4.23.1(2026-08-10) 이후 14일치를 한 번에 발행한다.
여덟 갈래지만 축은 하나 — **게이트가 존재하는데 발화하지 않거나, 발화해도 결과가 틀린 자리**를 닫았다.

#### 교차검증·게이트 복구

- **codex review 경로 복구** — 공용 `ARGS`의 `-C`·`--add-dir`를 `codex exec review`가 거부해 **review·check·final·commit 네 경로가 exit 2**였다. 비정상 종료라 "이슈 0건"으로 오독될 위험이 상시였다. exec 전용 배열 분리 + 서브셸 `cd` + 사전 게이트. 신규 `scripts/check-codex-flags.sh`가 **플래그 집합**을 검사한다(`-C`만 고치면 `--add-dir`가 남는다). 오라클: 실호출 exit 0
- **fail-open 카운터 5곳** — `grep -c … || echo 0`이 0매치에서 두 줄을 만들어 정수 비교를 죽였다. `peer-review-tiers.md:102`에서 risk escalation 무발화. `|| true`로 치환. 정답은 저장소 4곳에 이미 있었다
- **Negative-Result Gate 배선** — ⛔ 원 진단이 틀렸다. 게이트는 `8a3b576`(08-10)부터 존재하며 **6곳에서 트리거**되고 fz-peer-review에만 연결이 없었다. Gather §4에 항목 4 신설(0건 결론이면 positive control) + Deliver 병기 + 함정 표 2행
- **cwd 오염 게이트** — `--cd` 디렉토리는 위임 프로세스의 쓰기 대상이기도 하다(팀 워크트리에 17파일 유출 실측). §8 사후 게이트 4행
- **MCP 비ASCII** — `\uXXXX` 수동 이스케이프가 **200 성공 + 본문 11곳 손상**을 만들었다. 이 층엔 빌드도 린트도 없다. §12 규약을 외부 시스템 전송 축으로 확장

#### 승격 원장

- **findings ↔ ledger 진입 절차 신설** — 상호 참조가 **0건**이었다(같은 파일이 다른 자산은 17회 참조). 엔트리 성격 A~E 판별 + 귀속 정의
- **트랙 D 신설** — E 성격(하네스 결함·측정 실패·판정 오류·게이트 위음성)이 기존 4트랙 어디에도 안 맞았다. 조건 = 별개 세션 2건 + **회귀 fixture 1개** + 외부 채점 1회. fixture를 넣은 근거는 실측상 **활성 차단 사유 1위가 fixture 부재(3건)**. ⚠️ 임계값 잠정 — 승격 3건 누적 시 재검토
- **P-track 6 → 1** — 재평가에서 **5건 중 3건이 이미 구현돼 있었다**. 승격 절차와 구현 경로가 분리돼 원장이 현실을 반영하지 못했다. 구현 3 종결 · 미구현 2 REMOVED

#### fz-rebase — 넷 중 둘이 게이트 자신의 무음 실패

- `merge-base` 실패 시 출력 없이 종료 → 내용 게이트 통째 비활성화. `die` 전환
- OVERLAP 검사가 `-h`로 파일명을 버려 유실이 통과. 경로 인덱스 + 2단 판정
- 머지 해결 대조를 subject·줄수 → **해결 내용 해시** (서로 다른 evil merge가 subject·줄수 동일한 실측)
- base 신선도 `ls-remote` 대조 · prepush 롤백 앵커 경고 · ref 인젝션 차단(`source` 제거)
- 오라클 20 → 65. `assert()`가 exit code만 봐서 WARN 경로가 기존 20건에 invisible이었다

#### 가이드 전수 감사

`guides/` 9개 4,627줄. `llm-references.md:7`이 규정한 stale 모델 검출이 **파일 단위 all-or-nothing**이라 구세대 잔존이 전부 면제됐다 — `stale-model-heading` 룰 신설. `lint_contracts.py` `#N3`·`#N9` 추가. 죽은 참조 13곳 · 모순 4건 · TEAM 일몰 잔재 24곳.

#### ⛔ 발행 이력 정정

로컬에만 있던 **v4.24.0·v4.25.0 발행 커밋 2개를 걷어내고 하나로 합쳤다.** 둘 다 push된 적이 없고 태그도 없어 외부 참조가 0이었다. v4.25.0이 5산출물 중 3개만 갖춘 채 멈춰 있었고, 그 위에 새 버전을 올리면 문서 없이 건너뛰어진 채 남는다 — v4.23.0 서두가 기록한 *"bump 후 발행이 뒤따르지 않는 구조"*의 세 번째 재현이었다. 재작성 후 발행 파일 제외 작업 트리가 **완전 동일**함을 확인했다(유실 0).

## Retired Citation Policy

릴리즈마다 인용 논문이 rotate되면 추적 신뢰도가 떨어진다. 다음 정책을 적용한다:

- **Active citations**: 현행 modules/skills/agents에서 직접 인용되는 논문 (예: NLAH 2603.25723, X-MAS 2505.16997, Drift No More 2510.07777, VeriGuard 2510.05156, MAR 2512.20845, Intelligence Degradation 2601.15300, Context Length Hurts 2510.05381, OpenDev 2603.05344, MAST 2503.13657)
- **Retired citations** (RELEASE_NOTES만 보존): 과거 릴리즈에서 인용했으나 현행 modules에서 인용 없음 — ICLR MAD (2502.08788, v3.0 release). MAST (2503.13657)는 v4.17.0에서 modules 재인용으로 active 환원
- **정책**: retired citations는 RELEASE_NOTES에 historical reference로 보존 + CHANGELOG에 정리 사유 명시. 신규 modules에 재인용 시 active로 환원.

### v4.23.1 (2026-08-10) — 배선 복구: 정의된 팀의 2/3이 안 돌고 있었다 [PATCH]

> **사건**: Swift `enum` 계산 프로퍼티 `switch`에서 형제 절은 `Metric` 상수인데 한 절만 리터럴로 되돌아갔다. 외부 리뷰의 *"계획서 Descope 위반"* 지적을 Lead가 수용하며 발생. **빌드 통과 · 값 동일 · 테스트 0건**이라 자동 oracle이 전부 침묵했고 사용자가 육안으로 잡았다.

- ⭐ **`code-pair` impl-quality 배선 복구 (본체)**: `agent-team-guide`가 `code-*` 실질 워커를 review-arch·**impl-quality**·review-correctness로 정의하나 Wave 3 전환에서 **arch만 배선**됐다. 대조군 `plan-collaborative`는 정의된 5개를 전수 스폰 [verified: `grep -oE "agentType: 'fz:[a-z-]+'" workflows/*.js`]. `impl-quality`의 "Codebase Pattern Consistency"가 **사건이 정확히 그 렌즈가 봤어야 할 결함**인데 스폰되지 않고 있었다. ⇒ Stage 2를 full 모드에서 **arch + quality 병렬 2렌즈**로 확장, 두 결과를 단일 `review` 객체로 병합해 하류 계약(`s2`·Stage3 조건·`residualIssues`) 보존. light는 arch 단독 유지
- **검증 4-P 신설 (candidate)** — *"편집 라인이 놓인 자리가 일관적인가"*. 오탐 실측(peer slot 11곳 → emit 9곳 중 **진짜 1곳**)이 절차를 바꿨다: **형제 균일성 게이트**(불균일이면 중단) · **소비처 의존 축 제외**(접근수준·소유권은 정의상 소비처가 결정 → in-block 판정 불가) · 의미 비대칭 면제 · **provenance tie-break**(없으면 사건 당시와 같은 결론에 도달)
- ⛔ **"축 부재" 진단 철회 — 자기 재현**: 초판은 §5 "원칙 8"로 신설하며 *"형제 관계를 보는 렌즈가 어디에도 없다"* 고 단정했으나 **6개 실재**했다 — 그중 `skill-authoring` §1 **Sibling-Convention Check**는 **동일 실패 모드**로 이미 candidate 등재. 조사 대상을 3개로 스스로 한정하고 커버리지 실측 없이 홀을 선언한 것 자체가 그 관찰이 겨냥한 실패 모드다. 정확한 진단 = **입도 부족 + 소유자 미배선**
- **§5 원칙 8 → §12 R8-A 강등**: 문서가 *"공식/학술/고품질 출처만 인용"* 을 자기 정책으로 명시하는데 원칙 1~7은 전부 외부 권위, 원칙 8만 **자체 관측 1건**이었다. 번호 점유가 하류의 동급 권위 인용을 유발 → "하네스 홀 candidate" 표로 이동(외부 근거 = **미대조**), 하류 참조 8곳 갱신. 부수: "세 축" → **스코프 × 질문 격자**(직교하지 않음)
- **ledger 집행 결함 5건**: L-11 동축 판정 **미집행** → 관측 #3 등재(evidence 2→3) · L-1 관측번호 충돌(#2 중복 → **#4**) · L-13에 **회귀 fixture 2개**(TP/FP=0, §5.5 규율 1) · 4-P candidate 문구 누락(⛔ **Sibling-Convention Check 위반**) · 목차/heading/역참조 정합
- 상세: [docs/releases/v4.23.1.md](docs/releases/v4.23.1.md)

> ⛔ **철회한 자기 주장 2건**: *"in-block 비용 0"* → 접근수준 판정에 타 파일 Read(`BandCell.swift` 프로토콜)·리포 grep 4회가 실제로 필요했다. *"기계 검증 원리적 불가"* → magic-number lint가 잡는 부류이며 **lint 대안 검토가 선행 과제**로 남는다.
> ⛔ **동종 검증**: Codex probe 실패(`out of credits` — 산출 0 + exit 0이라 규약상 미성립)로 3렌즈 전부 Claude. **cross-model 안전망 부재** — 회복 시 교차 채점 필요(§5.5 규율 2 미충족).
> ⛔ **미해결 3건**: 이중 등재(`fz-code` 신호 + 4-P + 배선 복구로 **세 겹**) · `fz-review` 검증 4 원문 모순 · `code-pair` S4 결정 근거 미추적.

### v4.23.0 (2026-08-10) — 누적 통합: 계약 lint 결정화 · 리뷰 구조 판정 축 · llm-references §1.1b [MINOR]

> **누적 통합 릴리즈.** v4.22.0(2026-08-08) 발행 이후 CHANGELOG에 초안 번호 `4.23.0`·`4.24.0`·`4.25.0` 세 섹션이 쌓였고 **셋 다 태그·GitHub Release 어디에도 없다** [verified: `git ls-remote --tags origin | grep -E 'refs/tags/v4\.2[0-9]'` → v4.20.0·v4.21.0·**v4.22.0**뿐 · `gh release list` Latest = **v4.22.0**]. 구간에 `[MAJOR]` 0건이므로 **누적분 전체를 v4.23.0 하나로 발행**하는 것이 semver 정합이다(`4.22.0 → 4.23.0`). 세 초안은 아래 **§A·§B·§C**로 보존한다(최신 먼저 — 본문 삭제 0줄). 매니페스트는 `4.25.0 → 4.23.0` 하향이나 **발행된 적 없는 번호**라 관측하는 소비자가 없다.
>
> ⛔ **이 정리는 v4.22.0에 이어 두 번째다.** 반복 원인은 릴리즈 절차가 아니라 **커밋 시점에 매니페스트를 먼저 bump하고 발행이 뒤따르지 않는 구조** — bump가 "발행 예약"으로 읽히지만 태그·Release가 없으면 그 번호는 존재하지 않는다. 상세: [docs/releases/v4.23.0.md](docs/releases/v4.23.0.md)

#### A. 계약 lint 결정화 + inert frontmatter 51선언 제거 + Negative-Result Gate 신설 (초안 4.25.0, 2026-08-09)

> 전수 감사(138자산 · `~/dev/TVING/fz-plugin-audit-2026-08-09/`)에서 확정한 F-0~F-25 중 **W0~W3b 범위**를 반영한다. 방향은 **C(정본) → B(기계화) → A(baseline 소비)** — `plan/direction-challenge.md`. Codex verify `needs_revision` 13이슈 **전량 수용**(`plan/verify-result.md`).

**1. `scripts/lint_contracts.py` 신설 — `fz-manage check` 17항목의 결정화 (F-2)**
- 문제: 17항목이 **전부 언어 지시**였고 check용 스크립트가 0개였다 → 정의된 검사(#6 깨진 참조·#14 모듈 목차)가 있는데도 위반이 생존했다. `guides/skill-authoring.md` §11("결과가 binary → 스크립트")의 미이행.
- ⛔ **스크립트가 항목 SSOT** — SKILL.md는 표를 재정의하지 않고 `--list`에 위임한다(이중 정의가 F-5·F-19의 원인이었다).
- **24항목 / DETERMINISTIC 15 · THRESHOLD 3 · SEMANTIC 6** (⛔ 손으로 세지 말고 `lint_contracts.py --list` 출력을 전사한다 — 2026-08-09 감사 ISSUE-014에서 23/15/3/5로 stale했고, **2026-08-10 `#15` 삭제 후 25/16 으로 또 stale했다**. ⚠️ `#N2` 는 디렉토리 파일 수만 보므로 이 카운트는 **기계 검사 사각지대**다 — 항목 추가·삭제 시 수동 전사 의무).
- ⛔ **exit 3분**: `0`=위반 없음 / `1`=위반 / `2`=**configuration·parse error**. 루트는 `Path(__file__)` 앵커(CWD 비의존). stdlib 전용.
- `fz-manage check`가 `lint_contracts.py` + **기존 `lint-model-explicit.sh` + `lint_doc_freshness.py`** 를 함께 호출한다 — v1 초안은 새 lint만 만들고 기존 lint 배선을 빼먹어 F-2를 남겼다(Codex 단독 발견).
- ⛔ **"차단"→"검출(요청 시)" 정직화**: 훅 미설치 상태에서 lint는 차단하지 않는다. 실제 차단은 `settings.json`(사용자 소관).
- 첫 실행 129건 → 탐지기 4회 교정 → **위반 0건**. 교정 근거는 전부 *히트를 열어본 것*이다: #13은 `agents/*.md`의 `CLAUDE.md ## Architecture`가 **소비 프로젝트**를 뜻해 89건 오탐 → SEMANTIC 강등 · #N4는 마크다운 표의 `\|`(파이프 이스케이프)와 자기 설명 문구 제외 · #N6은 `$0`·`git rev-parse --show-toplevel` 앵커도 유효 · #15는 BAD/GOOD few-shot 제외.

**2. inert frontmatter 3종 51선언 제거 (F-5·F-20)**
- `team-agents`(9) · `composable`(21) · `model-strategy`(21) — 전부 **fz 자작 필드로 런타임 효과 0**. 실효 결정자는 팀 구성·모델 = `workflows/*.js`, 파이프라인 = `provides`/`needs`. `arch-critic: main:opus` ↔ `code-auditor: main:sonnet` 형제 불일치가 stale 위험을 실증했다.
- 소비처 8곳 동반 갱신 + `governance.md §Truth-of-Source`에 **4항목 정본 지정**(모델 배정·팀 구성·opus 상한·YAML 필수 필드).
- YAML 필수 필드를 **2층 분리**: L1 Claude Code 공식 4 / L2 fz 정책 2(`provides`·`needs` — `/fz` §3.2가 실제 소비). 3판본 충돌 해소.
- opus 동시 상한 **≤3 통일**(정본 `fable-model-guide.md` §5) — `skill-authoring.md` §12만 ≤2로 이탈했고 `plan-collaborative.js`는 Stage 2에서 opus 3 병렬이라 참조 구현이 규약을 위반하고 있었다.

**3. `modules/cross-validation.md` §Negative-Result Gate 신설 (F-25)**
- ⛔ **신규 규칙이 아니다** — `system-reminders.md` T8이 *"정규식 불완전은 Coverage Gate 담당"*으로 이미 위임했으나 **수신처에 구현이 없었다**. Coverage Gate가 *범위*(N/M)를, 본 Gate가 *도구 유효성*을 본다.
- 3요소: **positive control**(0건 결론 전 동일 명령이 반드시 매칭되는 케이스에서 non-zero 확인) · **신호 보존**(`>/dev/null 2>&1` 금지 + exit code 판정 포함) · **귀속 라벨**(다중 대상 스캔에 식별자).
- 근거: 단일 세션 **12 인스턴스** 실측 — 그중 *0건 자체를 의심해서* 잡은 건 **0건**(전부 외부 지적·우연한 재측정·도구 에러메시지). `harness-engineering.md` H1 자문 NO.
- 기계 검출 3항목: **N4** ERE alternation 오용(⚠️ BRE의 `\|`는 정당 → `grep -E` 동일 줄 한정) · **N5** 신호 폐기 · **N6** 루트 앵커.

**4. 링크·인벤토리·목차 (F-7·F-11·F-21·F-23)**
- 모듈 목차 **24개 추가**(100줄+ 30개 중 미보유분). 형식 선례 `review-structural-axes.md`·`harness-engineering.md`.
- `fz-modernize` 자기 자산 참조 4곳 루트 기준 정정.
- ⛔ **선재 버그**: `fz-peer-review/references/test-spec.md:80`의 `grep -E '^\s*(import\|from)'`은 ERE에서 alternation이 아니라 **항상 0건** → 그 stdlib 검사가 지금까지 통과로 오인돼 왔다(실증: 잘못된 패턴 0건 / 올바른 패턴 3건).
- `CLAUDE.md` 인벤토리 정정(modules 20→**46** · guides 7→**9**) + lint **N2**가 실측 대조. 감사 진입 문서가 stale했다.

**5. TEAM 일몰 완결 + 계약 정합 (F-1·F-6·F-12·F-19·F-22)**
- **SSOT 동기화**: Coverage Gate canonical 어휘 **9개를 미러 4곳 전부에** 동기(Q-COVERAGE·T8·fz-search·fz-discover) — "생태계"·"전부"가 4곳 전부 누락돼 **동일 요청에 발동이 갈리던** 상태였다. 승격 임계 **canonical 순환 해소**(`memory-guide` ↔ `promotion-ledger`가 서로를 정본으로 지목 + 줄번호 2~4행 어긋남) → Track A 단일 정본 + heading anchor.
- **에이전트 stale**: `agent-team-guide.md:219`가 2026-08-08에 정정한 *"TeamCreate 기반 팀"* 문구가 **5 에이전트에 잔존**하던 것 제거. 승격 주석 5곳 제거(그중 `review-counter` "미승격·sonnet 유지" ↔ 실제 opus / `review-direction` "opus" ↔ 실제 fable). `impl-correctness`·`memory-curator`의 미전환 P2P 블록 전환(후자는 같은 파일 내 자기모순이었다). **동반**: `agent-team-guide §7` 체크리스트가 지운 주석을 요구하던 것 재작성.
- ⛔ **`get_codex_skill()` → `get_codex_skill_path()`** (**F-22 파손 수정**): 이전 함수는 Tier 2b에서 플러그인 `codex-skills/`를 확인한 뒤 **이름만** 반환했는데 호출자 8곳은 항상 `cat ~/.codex/skills/${NAME}/SKILL.md` 를 읽었다 → 심볼릭 부재 시 **Tier 3 폴백으로 가지 않고 존재하지 않는 경로를 읽었다**. 경로 반환으로 계약 통일 + `BASH_SOURCE` 의존 제거(마크다운 인라인 함수라 불안정). ⛔ **`setup-codex-skills.sh`는 dead가 아니라 load-bearing**임이 확정됐다.
- **kill-switch**: 부재 도구(`TeamDelete`·`shutdown_request`) 지시 제거 — **비상 경로가 v2.1.178부터 없는 도구에 의존**하던 상태였다. Workflow 중단 절차로 교체(최종 형태는 OQ3 대기).
- **Agent-Payload 스킬 범주 신설**: `user-invocable: false` + `skills:` 사전주입 스킬(arch-critic·code-auditor)이 어느 범주에도 없어 6게이트를 영구 미충족한 것이 T9c(2026-06-28 지적)가 1년 미해결된 근본 원인. ⛔ 면제가 아니라 **대체 게이트 3**((b) 출력 필드 정합은 **소비 스키마 집합 전체** 대상 — arch-critic은 2 계약 동시 지원).
- **요청 채널**: (a) 도구 제약 서술 8곳의 채널 함의 제거 / (b) 실행 불가 지시 2곳(`plan-edge-case` sequential-thinking 요청 · `plan-impact` git artifact 요청)을 **반환 필드 패턴**으로 재작성(선례 `review-correctness` `originBodyRequest`).
- **`§5.7` fz-peer-review 테이블 신설**: SKILL.md가 기록하라 지시한 테이블이 **존재하지 않았다**. 열 10개 — `tier`·`mode`·**fallback 사유**(`invalid-args` ≠ runtime-null)·wall-clock·`structuralAxes`. 단순 null률만으로는 신뢰성 실패와 입력 오류를 구별할 수 없다.

**6. 실패 복구 사다리 정본화 — OQ3 해소로 B1·B2·B4 동시 해제 (F-1 b·F-13)**
- ⛔ **문제**: 5개 스킬이 `mode:'fallback'` 절차로 `modules/team-core.md`+`patterns/`(679줄)를 지목했으나 내용은 `TeamCreate`·`SendMessage` P2P였다 — 이 도구들은 v2.1.178부터 **부재**하고 SOLO에는 에이전트도 없다. **가장 필요한 순간의 지침이 실행 불가**였다.
- ⭐ **실측이 처방을 바꿨다**: 워크플로 실패는 **2회 실제 발생**했고(§5.7 fz-code #1 args 오류 · fz-review #8 초회 7287s 스톨) **두 번 다 재invoke·resume으로 복구**됐다. `team-core` 사용 이력은 **0건**. → 679줄 재작성이 아니라 **이미 작동한 경로를 성문화**하는 작업이었다.
- **`guides/skill-authoring.md` §12 실패 복구 사다리 신설**: **L1** 분할 재invoke(H5) · **L2** 입력 오류 → 수정 재invoke(⛔ 워크플로 실패가 아니라 **설계된 fail-fast**) · **L3** 스톨·일시장애 → **`resume` 우선**(동일 세션 한정) · **L4** 사용자 에스컬레이션(⛔ Lead 단독 SOLO는 승인 후에만). 각 단계에 실측 선례 명기.
- `team-core.md` **강등**("실행 절차로 참조하지 않는다") — 679줄은 **설계 출처**로 존치, 재작성 0줄. 소비처 5곳 + `fz`/`fz-code` 절차를 §12 위임으로.
- `governance.md` Kill-Switch = **사다리 L4에서 '중단' 선택 시의 절차**로 위치 확정(OQ3 대기 주석 제거).
- **B4**: `agents/impl-correctness.md` `tools:`에서 **쓰기 7종 제거**(`Edit`·`Write`·`Bash`·`replace_symbol_body`·`insert_*`·`rename_symbol`) — 유일 소비자 `code-pair.js`가 changeset JSON만 요구하고 Lead가 적용하므로 vestigial이었다. 이전에는 **프롬프트 금지만이 방어**였고 capability는 남아 있었다 → 이제 **시도 자체가 불가**(`harness-engineering` "스키마 수준 필터링" + "capability ≠ authorization").

**7. 자기 리뷰 → 외부 감사 15이슈 전량 수정 (verdict rejected → 해소)**

구현 후 `/fz-codex` 교차검증(`codex_review_schema.json`, effort high)이 **verdict=rejected**(critical 3 / major 11 / minor 1)를 냈다. Lead가 15건 전수 실측 → **오탐 0**. ⛔ 가장 중요한 발견은 **이 릴리스의 enforcement 계측기 자신이 vacuous했다**는 것 — "위반 0건 exit 0"이 깨끗함의 증거가 아니었다.

**7-a. 계측기 신뢰성 (`scripts/lint_contracts.py`) — 통과가 곧 발화 가능성이 되도록**
- ⛔ **양성 대조 하네스 신설 (fixture 23건, 매 실행 선행)**: `hits`는 *본 후보 수*라 패턴이 고장나도 0이 아니다 → `OK [검사 대상 13]`이 찍혔다. 이제 fixture 실패는 **exit 2(configuration error)** 이고 "위반 0건"으로 읽히지 않는다. `--self-test`로 단독 실행 가능. ⛔ 범위는 **정규식이 판정의 전부인 항목(#15·N4·N5·N6·N8)에 한정** — 구조 순회형은 파싱 실패가 이미 ParseError로 드러난다(`harness-engineering` §6 AP1 과도한 구조화 회피)
- **#15 `TRUNC` 정정**: `-\w*\d`는 숫자가 플래그 토큰에 **붙은** 형태만 잡아 `head -5`·`head -n5`는 매칭하고 **가장 관용적인 `head -n 5`·`tail -n 20`을 놓쳤다** — 이 검사의 존재 이유가 통과하고 있었다
- **#N6 정정**: 파일 전체 문자열 검색이라 ①`__file__`이 **주석에만** 있어도 앵커로 인정 ②무관한 `exit 2`가 fail-closed 가드로 인정 ③검사기 자신이 **자기 정규식 정의줄**로 통과. ⛔ **본 릴리스가 추가한 `codex-exec.sh`가 7번째 줄 주석의 "exit 2"로 통과하며 자기증명했다.** 이제 주석 제거 코드에서만 앵커를 찾고, 허용 3형태를 명시((a) 자기위치 앵커 (b) 마커 검사+비0 종료 (c) **사유 있는** 면제 선언). `chk_N6`와 fixture가 **동일 함수 `n6_ok`**를 쓴다(판정 드리프트 차단)
- **#N1 정정**: `critical` 포함 enum을 정규식으로 찾고 못 찾으면 `continue` → **consumer에서 critical을 삭제하는 변경**(가장 중요한 양성 대조군)이 위반이 아니었다. 구조 순회(`find_severity_enums`)로 바꾸고 **정의 부재도 위반**으로
- **`--only` 검증**: 알 수 없는 id → **exit 2**. 이전엔 `--only DOES_NOT_EXIST`가 검사 0개를 돌리고 "위반 0건 exit 0"을 냈다 — 오타 하나로 enforcement 전체가 조용히 무력
- **#N3 항목 설명 축소**: "그 줄의 실제 내용 병기"를 주장했으나 구현은 행 범위만 검사 → 하는 일로 정정
- **#N2 확장**: `scripts`·`agents`·`workflows` 카운트 등재 → 즉시 `scripts/ 선언 6 ≠ 실측 7` 검출(**한 세션 안에 만든 stale**)

**7-b. lint 신규 2항목 — 사람 검사로 두 번 놓친 것을 기계화**
- **#N7 셸 변수 정의-사용 불일치**: `get_codex_skill()` → `get_codex_skill_path()` 전환에서 **할당은 `_SKILL_PATH`, 조건문은 옛 `_SKILL`** 인 스니펫이 3곳 남아 `[ -n "$미정의" ]`=false → **searcher 보조·fixer 보조·final DA가 조용히 실행되지 않았다**(`subcommands-core.md:123,172` · `aux.md:49`). CHANGELOG의 "호출자 8곳 통일"은 **거짓이었다**
- **#N8 목차 앵커 해소**: 본 릴리스가 24개 모듈에 추가한 목차의 앵커가 실제 heading과 불일치(8곳). ⛔ **그걸 고치려 쓴 첫 스크립트가 `\s+ → -`로 공백 연속을 합쳐 14곳을 새로 깨뜨렸다** — GitHub slugger는 구두점 제거 후 **공백 하나당 하이픈 하나**다(`A + B` → `a--b`). 총 **22개 앵커 정정**(대부분 선재 파손), 미해소 **0**

**7-c. 기능 파손 2건 — 목표 미달이었던 것**
- **`FZ_PLUGIN_ROOT` 초기화 절차 신설**: 소비 10곳 / **할당 0곳** — 8호출부가 전부 빈 값을 넘겨 **Tier 2b가 항상 건너뛰어졌다.** Tier 2b 파손을 고치려던 변경이 목표를 달성하지 못한 상태였다. 이제 스킬 base directory에서 유도 + **마커 디렉토리 fail-closed 검증** + 무효 시 경고(⛔ 조용한 빈 값 금지). ✅ Tier 2a 심볼릭이 있으면 무증상이라 실측 없이는 드러나지 않았다
- 위 #N7 3곳 변수명 정정

**7-d. 문서 모순 5건**
- `CLAUDE.md` **Agent Teams Environment Flag** — "`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 설정 필수"를 지시하는 동안 같은 리포가 `TeamCreate` 부재(v2.1.178~)를 선언했다. **런타임 진입 문서가 없는 실행 경로를 활성화하라 지시**하는 모순 → 역사적 기록으로 전환 + §12 위임
- `templates/agent-template.md` — `Code agent | Read, Grep, Glob, **Edit, Write, Bash** | impl-correctness` 행이 남아 **본 템플릿으로 에이전트를 만들면 6절의 capability 축소가 되살아났다** → `Changeset producer`(쓰기 없음)로 정정 + 근거 명시
- `agents/impl-correctness.md` Cargo-Cult 절차 — "**새 파일 작성 후** Grep"은 쓰기 도구 제거 후 **수행 불가**(changeset만 반환하므로 파일이 디스크에 없다) → 자기 `newBody` 분석 + 디스크 대조는 Lead 소관으로 책임 재배치
- 워크플로 헤더 5곳 — `mode:'fallback' → Lead는 SOLO 경로 수행`이 §12 L4("사용자 승인 후에만")와 충돌 → 사다리 참조로 정렬. ⛔ **"워크플로 무변경" 불변식 이탈**이나 **주석 전용**(비주석 변경 0라인, `node --check` 6/6)
- 폴백 지목 잔존 7곳 + 부재 도구 `SendMessage` 처방 4곳 — 6절 강등의 미완 부분(아래 8절)

**7-e. 미수정 1건 (판정: 현재 피해 0)**
- **#1 필수 필드 값 검증** — 키 *존재*만 보므로 빈 값이 통과한다. 다만 21개 스킬 전부 필수 키를 유지하고 있어 **현재 결함 0**이고, YAML 파서 도입은 비례적이지 않다. 계약 불완전성으로 기록만.

**8. 6절 강등의 미완 — 폴백 지목 잔존 11곳 (전수 재조사)**

⛔ 6절 적용 후 "폴백을 team-core/patterns로 지목: 0건"이라 보고했으나 **편집한 5곳만 검사한 결과**였다(Coverage Gate 위반). `team-core`/`patterns/` 지목 **111줄을 100% 분류**(사료 32 / 정당 17 / 잔존 62) → 실행·폴백 절차 지목 **11곳 정정**:
- 스킬 7곳: `fz-peer-review:65`·`fz-discover:67`("TEAM 실행 프로토콜") · `fz:314`("SOLO 폴백 시 참조") · `fz-code:100`·`fz-plan:88`·`fz-review:86`("팀 모드 규칙은 team-core 참조") · **`templates/skill-template.md:115`**("팀 프로토콜" — 생성 템플릿이라 미래 스킬에 전파)
- 부재 도구 처방 4곳: `cross-validation.md:95`·`native-agents.md:67`(`SendMessage` — v2.1.178~ 부재) · `system-reminders.md:20,44`(T4 근거) · `fz-manage:56,435`("각 스킬에서 직접 참조" — 이제 거짓)

**9. `scripts/codex-exec.sh` 신설 — codex 호출 hygiene의 실행체 (`fz-codex-bash-hygiene.md` §8 정본)**

⛔ **실측 실패 2건이 신설을 유발했다**: ① `codex exec review --uncommitted "<prompt>"` → **exit 2**(`subcommands-core.md:36`이 "인자 충돌"을 **이미 문서화**하고 있었다 — 산문 경고는 호출 시점에 읽혀야 작동한다) ② 래퍼 마지막 문장(`wc || echo`)의 exit이 태스크 exit으로 올라가 **codex exit 2를 0으로 보고**했다.
- **사전 게이트**: 플래그 상호 배타(`review`+PROMPT → exit 10) · 필수 인자 · 경로 실재 · trust_level 경고 · git repo 판정
- **사후 게이트(신설)**: exit≠0 → **12** / 빈 출력 → **13** / JSON 파싱 실패 → **14**. ⛔ **10~14는 전부 측정 실패**이며 "이슈 0건"이 아니다. 통과 시 `GATE-PASS json_ok issues=N verdict=V`를 stdout에 명시
- 검증: 사전 게이트 **8종 전부 발화**(exit 10×6 / 11×2) + 성공 경로 `GATE-PASS` exit 0 — ⛔ 통과만 확인한 게이트는 무용하므로 발화 가능성을 함께 실측
- §6 복붙 템플릿은 **참조로 강등**(붙이지 않으면 작동하지 않고, 실측상 누락이 재발했다). `guides/skill-authoring.md` §11 "binary → 스크립트"의 적용

**10. 자기 감사 4라운드 → ⛔ NOT CONVERGING 판정 후 **감산 전환** (일반성 포기)**

구현 diff를 `/fz-codex` 로 4회 교차검증했다. R1=15(critical 3) → R2=15(critical 3, **11건이 R1 수정에서 발생**) → plan 검증=11 → R3=14(critical 1) → R4=10(critical 0). R4에서 외부 판정이 **NOT CONVERGING** 이었다 [외부: codex]:

> "The structural cause is **reactive expansion of bespoke partial interpreters**, followed by **self-tests derived from the same assumptions**. Each counterexample adds another regex, merge rule, waiver, or fixture **without an independent semantic oracle**."

⛔ **그래서 패치 루프를 멈추고 감산했다.** 이하가 §A의 최종 형태이며, v4.23.0으로 출하되는 형태다.

**10-a. `#15` 삭제 (외부 C4 권고 수용) — `-112줄`**
- 근거: 후보 15건에 **현재 위반 0** · 역사적 결함 2건은 이미 **구조적으로 수정**됨(`hygiene:125` 는 전체 집합에서 세고 표시만 자름 / `fz-modernize:345` 는 총계를 먼저 산출) · 항목 설명이 스스로 오탐을 인정 · R3/R4에서 문맥창·waiver 3종·heading 교차를 얹고도 H1·setext 경계를 놓쳤다
- 부수: R4-ISSUE-007(heading 경계)이 **삭제와 함께 소멸**. `pred_15`·`TRUNC`·`COUNT_CLAIM`·`DIRECTIVE`·`EXAMPLE`·`NARRATIVE`·`DISPLAY_ONLY`·`CTX_MAX` 전부 제거

**10-b. `validate-codex-output.py` 전면 재작성 — 범용 JSON Schema 자작 폐기 (`-20줄`)**
- ⭐ **실측이 방향을 뒤집었다**: `schemas/*.json` 전수에서 **`$ref` 0건** · 반면 `pattern` **7건**. 나는 4라운드에 걸쳐 **`$ref` 해소·JSON Pointer·`%인코딩`·형제 병합**(가장 어려운 부분)을 자작했고 — **존재하지 않는 요구사항**이었다. 그 코드가 R4-ISSUE-003의 원인이다(`dict.update` 로 병합 → draft2020-12 는 **독립 적용**인데 로컬 `minimum:-5` 가 참조 `0` 을 지워 `-2` 통과)
- 반대로 **실제 7번 쓰이는 `pattern` 은 무시**했다 → R4-ISSUE-002
- ⇒ 지원 키워드를 **실측 빈도로 재정의**(type 162·description 107·enum 24·properties 22·items 21·required 17·additionalProperties 11·pattern 7·minimum 6·maximum 4·maxItems 1). **미지 키워드는 exit 2** (침묵 금지) · `format` 은 **주석 취급임을 명시**
- ⛔ **범용 검증기가 아님을 docstring 에 선언**한다 — fz 스키마 구조만 해석한다

**10-c. `#N6` 를 줄 화이트리스트로 — `ast` 일반 분석 폐기**
- R4 실측: `from evil import Path as P` → `P(__file__)` 통과(ImportFrom.module 미검증) · `X().resolve(__file__)` 통과(임의 attr)
- ⇒ 대상은 우리 스크립트 **10개**(.py 4 · .sh 6)뿐이므로 **실제 쓰는 줄을 정확히 열거**(`ANCHOR_LINES`)하고 **미지 형태는 거부**. 새 형태는 여기 추가하는 것이 명시 승인
- heredoc: POSIX 종료 규칙(정확 일치 / `<<-` 탭만 / `<<\EOF` / 다중) 재구현을 폐기하고 **첫 `<<` 이후 전체를 데이터로 취급**(fail-closed). R4-ISSUE-006 3방향 동시 소멸
- ⛔ **Lead 자체 발견 (2026-08-10)**: 전환 중 내가 넣은 범용 패턴 `[A-Z_]*="$(cd "…" && pwd)"` 가 **경로 무관**하게 허용돼 `cd "/tmp"`·`$HOME` 도 앵커로 인정했다 — fail-closed 화이트리스트에 **내가 구멍을 냈다**. 자기 위치 유도 경로(`BASH_SOURCE`/`$0`/`*DIR*`/`*ROOT*`)로 제한

**10-d. 정정 4건**
- `codex_review_schema.json` `confidence` 에 `minimum/maximum` **인라인**(`peer_review` 는 이미 정상, `review` 만 누락 → `confidence: 101` 통과) + **`#N1` 을 경계 정합까지 확장**
- `health-check.sh`: 사전조건 검사(`python3`·`git`·lint 스크립트 실재) · **3상태 표기 ✅/⛔/⏸(UNRUN)** · **UNRUN 을 FAILED 보다 먼저 판정**(이전엔 `exit 1` 이 먼저 반환돼 미실행 총평이 보고되지 않았다)
- `PARAGRAPH_LINE` 축소 — 마커는 **뒤에 공백이 있을 때만** 리스트/heading. `-foo`·`*emphasis*`·`#hashtag` 는 단락이므로 setext 밑줄을 받는다
- 통합 fixture: `#N4`·`#N5` **계열별 파일**(파이썬 계열 순회 소실 탐지) · 위치 단정을 `startswith` → **경계 요구**(`:3` 이 `:30` 에 매칭됐다)
- 레지스트리 불변식: `kind` **enum 검증**(`"DETERMINSTIC"` 오타 → 조용히 SKIP) · **`MIN_HITS ≥ 1`**(0·음수가 하한 무력화)

**10-e. 결과 — 순감 `-132줄`**
`lint_contracts.py` 1341→1229 · `validate-codex-output.py` 188→168. ⛔ **`plan-final.md` §변경 예산 초과(+418줄·스크립트 3개)를 실제로 되돌렸다** — 외부 검증이 그 초과를 독립 확인했고(+511/−94 net +417), 감산이 그 지적의 처방이었다.

⛔ **기계 검사 사각지대 (candidate)**: CHANGELOG 의 **레지스트리 항목 카운트**는 어떤 lint 도 보지 않는다(`#N2` 는 디렉토리 *파일 수*만 본다). 2026-08-09 에 23/15/3/5 로 stale 했고 **`#15` 삭제 후 25/16 으로 또 stale** 했다. 항목 추가·삭제 시 `--list` 수동 전사 의무. ⚠️ 검사 신설은 **검증 라운드 직전에 새 표면을 만들지 않기 위해** 보류했다 — 다음 사이클 후보.

**⛔ 미처리 (실측 기반 판정)**
- **OQ5 `description` 400자 cap → 수정 불필요.** `schemas/*.json`·`workflows/*.js`에 `maxLength` **0건** — `peer-review.js:41`의 `≤400chars`는 필드 설명 문자열 안의 **권고**일 뿐이고 초과 시 에러·잘림·거부가 없다. 리스크로 등록했던 것이 **오판**이었다.
- **OQ9 리뷰 이슈 3중 계약 → 위생, 미처리.** 실측(`/fz-codex verify` 실행 결과): 지시 없던 required 4필드가 `scope_disposition` 13/13 · `code_snippet` 13/13 · `alternatives`/`recommended` **8/13 substantive**(대안 2개+trade-off), 잔여 5는 `null`이고 스키마가 `type:["array","null"]`이라 **정당**. 실제 피해 0 → (b) 계약 수렴은 "지금 잘 되는 것을 건드림". 필요 시 (a) 경로 태그 ~8곳이 저비용 진입점.

#### B. 리뷰 스킬 구조 판정 축 신설 + peer/fz-review 계약 정합화 (초안 4.24.0, 2026-08-09)

> 리뷰가 결함(요구사항·버그·영향범위)은 잘 찾고 **더 나은 구조는 못 찾는** 문제를 배선으로 해결한다. 근거는 **통제 A/B 1건**: 스키마·cap·에이전트·모델을 전부 고정하고 브리프만 결함축→구조축으로 바꿨더니 `review-arch` 1콜(116K)이 대안 **9/10** · 삭제라인 정량 **10/10** · 기존 3-렌즈 24건(533K) 미포착 **신규 6건** · 삭제가능 **95줄(변경량 29%)** 을 냈다. 능력 부족이 아니라 **하네스가 묻지 않았다**(`prompt-optimization.md` §3b H1). 산출물: `~/dev/TVING/fz-peer-review-upgrade/`(plan-v4 · Codex verify 10/10 채택 · 홀 인벤토리 H1~H24·R1~R11).
>
> - ⭐ **`modules/review-structural-axes.md` 신설** — 구조 판정 5축(A 메서드 책임 밀도 / B 구조 대안 ≥2 / C 삭제>추가 / D 구조결정 3축[DI 출처·스레드 가정·public API 모양] / E 코드 형태). **fz-peer-review ↔ fz-review 공유.** 보충 4a대로 if-then이 아닌 **원칙+이유** 형태. ⛔ **경계 문구가 필수 구성요소**("버그는 다른 리뷰어 담당 — 너는 더 나은 구조만 본다") — A/B B군이 이 문장으로 major 0을 냈다(결함 판정 안 함).
> - ⭐ **`structuralContext` args 신설 (양쪽 워크플로)** — ⛔ **arch 렌즈에만 주입.** 이유 둘: quality/correctness가 결함 축을 유지해야 하는 **회귀 방어**, A/B가 `review-arch` 1개로만 측정된 **검증 범위 일치**. 비용 실측 Tier 2 총량의 **약 0.2%**(3콜 주입 시 0.6%).
> - ⭐ **H24 — `dist`가 `suggestion`을 집계하지 않던 결함 수정** (`peer-review.js` · `review-live.js`). peer-review는 `severity` enum에 `suggestion`이 **있는데** distribution·log에서 누락됐다 → **구조 개선 제안이 정확히 그 등급**이므로 개선 조치가 집계에서 사라지는 구조였다. Phase 0c Constraint Probe에서 발견.
> - **fz-review `severity`/`newSeverity` enum 4단화** — `critical/major/minor` → `+suggestion`. 개선 제안을 담을 등급이 없어 minor 이상으로 올리거나 보고를 포기해야 했다.
> - **`improvement → severity cap: minor` 삭제 3곳 동시** (`fz-peer-review/SKILL.md` · `arch-critic` · `code-auditor`) — 구조 개선은 정의상 `improvement`인데 cap이 minor로 깎고, `arch-critic`의 "major 이상에만 `alternatives` 필수" 의무를 **구조적으로 무력화**했다(더 나은 구조를 찾을수록 제안이 약해지는 역인센티브). 실측 부작용: severity를 얻으려 `regression` 태깅 → 3 표본 38건 중 `improvement` **1건**. 대체 = severity 축과 표기 축 분리(`[개선 제안]` 태그 + **non-blocking** + `raw`/`final` 병기).
> - ⭐ **convention을 양방향 입력으로** (`arch-critic` · `code-auditor` · `review-checks.md` 4-E) — 기존엔 *"관례와 같으면 하향"* 억제 방향만 있고 **처방이 없었다**. 실증: PR #4679에서 형제 5/5가 init 주입인데 이번만 직접 생성 — 규칙 위반이 아니라 "형제가 다르다"가 유일 근거였고 처방 기준이 없어 severity가 3렌즈에서 갈렸다(minor/major/minor). N 강도 임계는 *[candidate: 표본 1건]* 잠정표. fz-review는 convention 수집 자체가 0건 → 4-E Grep 패스에 형제 샘플 수집 병합.
> - ⛔ **stale 사실 제거 — `fz-review/SKILL.md` codex spend cap** — *"현재: spend cap 2026-07-16~, 해제 미상 → 재시도 생략"*이 **3중 검증을 2중 + 동종 fresh-context Claude로 강등**시키는 지시로 살아 있었다(문서 스스로 `:217`에서 "이종 안전망 상실"이라 적어둔 손실). `codex exec` 2회 성공으로 반증 + 메모리 규칙("매번 probe, 기록 기반 생략 금지")과 정면 충돌. → **probe 기반** 교체 + oracle 명시(`codex exec` non-empty + exit 0 — ⛔ `--version` 성공은 quota를 증명하지 않는다).
> - ⭐⭐ **자기 리뷰 반영 (같은 릴리즈 — 미출하 상태에서 접합)**: 위 항목들을 구현한 뒤 `/fz-review`로 자기 검증했고 **verdict `needs_revision`** 이 나와 9건을 수정했다. Codex 이종 검증이 **major 5건을 단독 발견** — 자기 리뷰만으로는 major 7건 중 4건을 놓쳤다.
>   - **정본 호출 미배선** — `peer-review-tiers.md:264`(Tier 2/3 정본 시퀀스) args에 `structuralContext`가 없었다. `SKILL.md:271`만 갱신 → 호출 지점 2곳 중 1곳. Lead가 정본을 따르면 `structuralLine=''` → **에러 0·로그 0·구조 축 0**으로 정상 반환. → 정본 args + "Lead가 넘길 것" 목록에 추가.
>   - **모드 커버리지 0** — `structuralContext`는 Workflow args이므로 **Workflow를 호출하지 않는 Tier 0(`<100줄`)·Tier 1·fz-review light에는 도달 경로가 없었다.** `<100줄`이 실무 최다 규모다. → Tier 0 Analyze + light 모드에 "**Lead가 §3+§4를 직접 적용**" 명시(Tier 1은 Tier 0 승계).
>   - **fz-review에서 개선이 차단으로 변함** — Gate 4가 `Critical/Major 이슈 없음`이고 `ReviewFindingsSchema`에 `origin`이 **없어** 개선/결함 구별이 불가했다. cap 제거로 개선이 major에 도달 가능해지자 **"제안"이 강제 수정**이 된다(peer-review에서 non-blocking으로 막은 실패의 재발). → Gate 4를 `Critical 0 + Major는 결함에 한해 차단, 구조 개선은 non-blocking(Lead 판정)`으로.
>   - **H17이 실효하지 않았음** — §Alternative Design **예시 JSON에 `alternatives` 배열이 그대로 남아** 산문(`:271` "필드 없음")과 12줄 간격으로 모순했다. JSON 블록이 2개인데 1개만 정리한 것이고, 모델은 산문보다 예시를 모방한다. 게다가 **`ReviewFindingsSchema`에는 `description`이 아예 없다**(`detail`) — `arch-critic`은 양쪽이 공유하므로 지시가 없는 필드를 가리켰다. → 예시를 본문 인코딩 형태로 교체 + **워크플로별 본문 필드 매핑표**(peer=`description` / live=`detail`) + 대안 요구를 `major 이상` 조건에서 **전 severity**로(A/B 분포상 구조 이슈는 minor·suggestion으로도 판정된다).
>   - **컨벤션 임계 상충** — `review-checks.md:35`("임계 미정 → 관찰만, severity 부여 금지")와 에이전트 2곳(`N≥5 → major`)이 **정면 충돌**했고, 그 major가 위 Gate에서 차단으로 변했다 — **1표본 미정 규칙이 verdict를 바꾸는 경로**. → 에이전트 2곳에서 숫자 처방 제거, SSOT를 `review-checks.md` 4-E로 고정(표본 3건 후 확정).
>   - **candidate가 `major`를 발행** — 신설 §Session-added Assets Application이 *"활성 강제 X"* 라고 선언하면서 `missed_session_asset: major`를 생성했다. "게이트 신설 0"을 원칙으로 걸고 **절차 항목이라는 형식으로 우회**한 것이고 실질은 게이트다(`prompt-optimization.md §4` 체크리스트 행 추가 반사). → severity 제거, 관찰 기록으로.
>   - ⛔ **트리밍 비저하 위반 1건 (자기 위반)** — 삭제 34줄 전수 분류 결과, `fz-peer-review/SKILL.md` 투표 로직에서 `→ "3/3 동의" 시 Fact Verification Gate 재확인 권장.` 1줄이 **대체 없이 순삭**됐다. **진단(3/3 동의는 공유 오류일 수 있다)은 남고 조치만 사라진** 상태였고, 지운 동기는 **500줄 아래 자리 확보** — plan-v4가 "순증 0"을 해법으로 세웠는데 이 줄에서 삭제로 벌었다. → 위 줄에 **병합 복원**(줄 수 증가 0, 499 유지).
>   - **참조 깊이 2단계** — 신규 모듈 §5가 표기 형식을 `review-checks.md` 4-N에 위임해 `SKILL.md → module → module`이 됐다. "dependency edge 아님"이라는 방어는 **준수하려면 읽어야 하므로** 성립하지 않았다. → 필요한 형식 2줄을 **인라인**하고 위임 제거.
>   - **required 필드 누락 예시 + 스키마 미정의 필드 2계열** — 두 에이전트 출력 형식 JSON이 스키마 `required`인 **`evidence`를 빼고** `evidence_trace`(미정의)를 제시했고, **`impact`(미정의)** 도 `major 이상 필수`로 요구했다. tool 레이어 스키마 강제 덕에 지금은 터지지 않는 **latent trap**. → 예시에 `evidence` 추가 + `evidence_trace`·`impact` **양쪽에 매핑 선언**("스키마 필드가 아니다 — 작성 규칙은 유지하되 본문 서술 필드에 담는다"). 개명 10곳은 하지 않음(H2′ 범위).
>   - ⭐ **관측 1줄 — 조용한 off 방어** (`peer-review.js` · `review-live.js`): `dist.structuralAxes = !!input.structuralContext` + log `구조축 ON/⛔OFF`. R1의 진단이 *"에러 0, 로그 0, 구조 축 0"* 이었는데 수정이 **문서 8곳**뿐이었다 — 첫 실패의 원인이 문서였으므로 문서 지점을 늘리는 건 같은 계열의 방어다. `suggestion` 카운트를 enum·dist·log 3지점 동시에 고친 것과 같은 형태로, 이제 반환값만 봐도 구조 축이 켜졌는지 판별된다.
> - ⛔ **초안 CHANGELOG의 허위 주장 3건 정정** (Codex 지적, 전부 수용): ① *"두 스킬이 같은 축을 쓴다"* → Tier 0/1·light·arg 누락 시 **미적용**이었다(위 2건 수정으로 해소) ② *"출력 형식 JSON에서 두 필드 삭제"* → few-shot이 여전히 둘 다 emit했다 ③ *"계약 드리프트 정합화"* → **구조 경로에는 거짓**이었다. enum 격차 1개만 좁혔고 `ReviewFindingsSchema`는 origin 기반 non-blocking도 지시된 대안 인코딩도 표현하지 못했다(②③ 해소, `origin` 필드 부재는 Lead 판정으로 우회 — 스키마 정합은 미완).
> - **계약 드리프트 정합화** — `review-arch.md` `tools:`에 본문이 Primary로 지정한 `find_referencing_symbols` 추가(선언↔본문 불일치) · `review-counter.md` 활성 배정 `Tier 1` → **Tier 3 Stage 3** 정정 · `fz-review` Phase 6의 `SendMessage(impl-correctness)` 삭제(**채널·에이전트 둘 다 부재**, Wave 1 일몰 잔존) · `plan-v3.2 §4.3` dangling 제거 · `team-agents.supporting`에 스폰 대상 아님 주석.
> - **입력 전제 부재 검출** — `symbols.json` 미생성 시 **관점 6(Dependency Impact) + Gate 4.6.5가 조용히 무력화**되던 것을 `peer-review-gates.md`·`code-auditor`에 "부분 수행 명시 + Grep 폴백 + confidence ceiling 70"으로 표면화.
> - **측정 장치 연결** — peer-review Synthesize §4에 `cross-validation.md` §Coverage Gate(전수·카운트·부정 주장 시 N/M 보고) + §Reflection Rate를 **실행 지시로 배선**(참조표 문구는 Read를 유발하지 않는다 — Codex ISSUE-009). same-model 교차 headline 제외 규칙 동반.
> - **Tier 2 반환 계약 명시** — Tier 2 `issues`에는 `finalSeverity`·`crossVerdict`·`counterVerdict`가 **없다**(Tier 3 전용). Matrix 작성 시 필드를 찾다 실패하면 판정 불가로 멈추던 갭.
> - **O2 이식** — fz-review 검증 4-O(Session-added Assets Application)를 peer-review Checkpoint 절차로. ⛔ 게이트 신설 아님. *[candidate]*
> - **test-spec 갱신** — stale oracle 2건 정정(`TeamCreate 호출 0회` → Workflow 미호출 · `Tier 2 = 2-agent` → **3-렌즈**) + **신규 oracle 2건**(Coverage Gate N/M 보고 · H24 회귀 방어).
> - **줄 수 규약 준수** — 모든 추가를 기존 모듈로 라우팅해 SKILL.md 본문 상한 유지: peer **498→499** · fz-review **468→469** (`prompt-optimization.md:180` MERGE 경로).
> - ⭐ **H17 — cap 삭제와 짝인 편집 (같은 릴리즈 필수)**: cap이 있던 동안 구조 개선은 major에 **도달하지 못해** `arch-critic` §Alternative Design의 *"major 이상엔 `alternatives` 배열 필수"* 가 발화하지 않았다. cap을 지우면 발화하는데 **`PeerReviewSchema`에 그 필드가 없다** → 대안이 조용히 버려지거나 재시도를 태운다(H3 사슬의 역방향 재생산). 수정: `alternatives`/`recommended` 요구를 **`description` 내 인코딩**으로 전환(A/B 실측 근거 — 에이전트가 필드 없이 자체 인코딩해 9/10) · `arch-critic` 출력 형식 JSON에서 두 필드 삭제 · `code-auditor:289`의 **Codex 전용 스키마 오참조** 삭제 · `finding-anatomy:22`에 "서술은 Lead, 대안 발굴은 에이전트" 2층 소유 명시.
> - **`structuralContext` oracle 추가** — `structuralLine`이 조건부(`input.structuralContext ? … : ''`)라 Lead가 args를 빠뜨리면 **에러 없이 구조 축이 꺼진다**. test-spec에 "arch 프롬프트에만 포함 / quality·correctness에 포함되면 fail" oracle 1행.
> - Matrix 어휘 충돌 정정 — `Sev` 열 병기를 `raw→final`에서 **`raw→adj`** 로(같은 표의 `Final` 열은 confidence다).
> - ⚠️ **미완 (다음 릴리즈)**: H2′ `evidence_trace` **개명 10곳**(이번엔 매핑 선언으로 함정만 닫았다. ⛔ 초안이 *"작성 규칙 5개 유실"* 이라 적은 것은 **부정확** — `additionalProperties` 미지정 + `{...f}` spread로 필드는 Lead까지 **도달한다**. 실제 손실은 규칙이 `evidence_trace`라는 이름에 붙어 Basis 열(`evidence`)과 연결되지 않는 **이름 분리**다) · H20 `CounterSchema.verdict` 2종→4종(`fpFlagged`가 `'refute'` 문자열 의존 — 런타임 커플링) · S1 계약 lint 스크립트 · S10 fz-review Gate 4 22항목 3층 계층화 · S9 Promotion Eval(N=3 실 invoke).
> - ⛔ **의도적 보류 2건 (수정하지 않음 — 근거)**:
>   - **`confidence 80` 하한** (`peer-review.js:97` OVERRIDE) — A/B에서 이 하한을 **고정 변수로 유지**한 상태로 B군이 confidence 82~95, 대안 9/10을 냈다(전면 봉쇄 아님). 다만 B군이 I13을 `confidence<80`으로 자체 배제한 실측 1건이 있다(그 I13은 사람이 PR에 게시할 값이 있다고 판단한 항목). **OVERRIDE는 3개 렌즈 전부에 주입되므로 하한 완화는 결함 탐지 정밀도까지 건드린다** — evidence 1건으로 전 렌즈 공통 제약을 바꾸지 않는다. 관찰 유지(R7 `P5`).
>   - **`fz-codex-subcommands-core.md:156-158` verdict 계약** — `pass/warn/fail`이 `critical/major` 기준이고 `suggestion`이 미정의다. Coverage 재측정 결과 severity로 차단·verdict를 정하는 지점 **6곳 중 이번 변경이 다룬 곳은 2곳**(`workflows/*.js`)뿐이다. 그러나 이 계약의 소비자는 **`/fz-codex check` → `fz-fix`** 이므로 리뷰 스킬 범위 밖이다 — 리뷰 고도화 PR에서 다른 스킬의 verdict 계약을 바꾸지 않는다(Surgical Changes). **다음 티켓 분리.**
> - **버전 유지 (초안 4.24.0, bump 없음)** — 작성 시점에 4.24.0은 아직 **커밋·출하되지 않은 상태**였다. 리뷰 수정은 같은 미출하 초안에 접합하는 것이 맞고, bump하면 릴리즈된 것처럼 읽힌다. ⛔ **그 판단은 맞았고, 그 초안 번호는 결국 발행되지 않았다** — 위 수정은 v4.23.0(§B)으로 출하된다.
> - ⚠️ **관찰 (조치 안 함)**: ① `ReviewFindingsSchema`에 `origin` 필드가 없어, `arch-critic`이 fz-review arch에도 로드되는 구조상 origin 표 지시가 **없는 필드를 가리킨다** — 이번 변경 전에도 그랬으므로 회귀는 아니나 cap 삭제로 지시의 하중이 커졌다. ② `arch-critic` 출력 형식 JSON의 `evidence_trace`도 스키마 필드명(`evidence`)과 불일치 — H2′ 소관.

#### C. llm-references §1.1b 신설: fz 의존 기능 7문서 색인 + 스폰 캡 stale 정정 (초안 4.23.0, 2026-08-08)

> 감사 결과 **fz가 실행 경로에서 의존하는 Claude Code 기능 7종의 공식문서 행이 §1.1에 없었다.** 특히 `/model-config`은 `fable-model-guide.md`·`skill-testing.md:422`·`harness-engineering.md:1227`·CHANGELOG 등 **12개 지점에서 이미 1차 출처로 인용**되면서 색인 행만 없어 참조점이 분산돼 있었다. 산출물: `~/dev/TVING/claude-paradigm-scan/`(감사서·리스트).
>
> - **`guides/llm-references.md` §1.1b 신설 (7행)** — O11 `/model-config` · O12 `/workflows` · O13 `/worktrees` · O14 `/plugins-reference` · O15 `/settings` · O16 `/env-vars` · O17 `/commands`. ⛔ **DELETE/MERGE-default 충족 근거 = 순수 additive가 아니라 산재 인용의 통합**(§1.1b 헤더에 명시). 7개 전부 **원문 fetch 후 작성** — 미대조 내용은 넣지 않았다.
> - ⭐ **fz 규약에 직접 영향 2건 발견**:
>   - `CLAUDE_CODE_SUBAGENT_MODEL`이 subagent·agent team·**workflow agent** 전부에 적용되고 **per-invocation `model` 파라미터와 frontmatter `model`을 override**한다 → `skill-authoring §12`의 "model 명시 의무"를 무력화할 수 있는 유일한 변수. 진단 1순위.
>   - `/env-vars`: *"any non-empty value **including `0`** turns the behavior on"* — **`=0`은 끄는 값이 아니다.** 실험 게이트를 `0`으로 껐다고 믿는 설정은 전부 재검증 대상.
> - ⛔ **stale 정정 — 세션 생애 200 스폰 캡 제거**(v2.1.224): `llm-references.md:28,§4-4` · `harness-engineering.md:1090,1105` · `agent-team-guide.md:291` **5지점**. 남은 하네스 상한은 **동시 20 + depth 3**뿐. fz governance(opus 동시 ≤2~3)는 여전히 훨씬 보수적이라 **거버넌스 재설계 불필요** — 순수 사실 정정이다.
> - **`/changelog (v2.1.220~226)` 행 추가** — ultraplan 제거 · workflow `import()` 샌드박스 탈출 픽스 · worktree 격리 전 세션 타입 확대 · `prompt-audit` 신설.
> - **감사 축 명시** — `last audited` 2026-07-25 → **2026-08-08**, 단 *"§1.1·§1.1b만 전수 대조. §1.2는 07-25 그대로, §2·§3은 미대조"* 를 헤더에 병기(하지 않은 감사 주장 금지).
> - **§6 가이드 매핑 확장** — fable-model-guide(O11) · governance/execution-modes(O12·O13·O17) 행 신설.
>
> **advisor 실증 2건 → 규약 반영** (2026-08-08, 동일 릴리즈):
> - ⭐ **A2: Workflow `agent()`가 세션 `advisorModel`을 상속한다** [verified: 1-agent 프로브 `wf_e7136199-140`, `model:'opus'`] — `{"advisor_tool_available":true,"call_attempted":true,"call_succeeded":true}`. v2.1.223 changelog가 "workflow agents"를 별도 스폰 클래스로 열거한 것은 **모델 제한 경고 범위**에 한정되며 advisor 상속과 무관함이 확인됐다.
> - ⭐ **A1: advisor 사용량은 트랜스크립트에 기록되지 않는다** [verified: 세션 트랜스크립트 3.1MB 전수] — advisor 6회 호출에도 `usage.server_tool_use` **289개 레코드 전수가 `{"web_fetch_requests":0,"web_search_requests":0}`뿐**. `advisor_*tokens` 류 필드 grep 0건. 워커 `agent-*.jsonl`에서도 재현.
> - **`modules/governance.md` §사각지대 신설** — advisor가 ①kill-switch ②lint/런타임 캡 ③트랜스크립트 계측 **3중으로 안 잡힌다**는 것을 근거와 함께 명시. `/usage`(대화형)가 유일 관측 경로. ⛔ **`opus 동시 ≤3` envelope이 advisor 지출을 bound하지 않는다.** 운용 규칙 4항(baseline 선기록·ad-hoc 프로브 금지·워커 회당 비용 규모·끄는 법) 추가.
> - **`guides/skill-authoring.md` §12에 「resume 계약 + advisor 상속」 신설** — `resumeFromRunId` 재생 순서 규칙(*"every agent that started after that one runs again, even if it completed"*) · **다수의 작은 에이전트가 진행을 더 보존**한다는 공식 결론과 fz의 소수-큰-에이전트 구조가 반대 방향임을 미측정 재검토 대상으로 명시 · resume은 동일 세션 한정 · `journal.jsonl` 진단 · ⛔ **`CLAUDE_CODE_SUBAGENT_MODEL`이 `opts.model`을 override**하므로 §12의 model 명시 의무를 무력화할 수 있음(진단 1순위).
> - **`guides/agent-team-guide.md:218` stale 정정** — *"Workflow 미보유 팀(예: fz-peer-review)"* 은 사실이 아니다(`workflows/peer-review.js` 실재, `SKILL.md:65,270`이 Workflow 필수 명시). **Workflow 미보유 팀은 현재 없다.** `TeamCreate` 실행 경로 호출부도 **0건**임을 병기.
> - **`modules/execution-modes.md` §SIMPLIFY 헤더 노트** — `/simplify`는 v2.1.154부터 **cleanup-only**(버그 헌팅은 `/code-review --fix`). fz의 게이트 3종(과잉 추상화·복잡도·패치 누적)은 cleanup 범위 안이라 **재배선 불필요**. ⚠️ `focus` 파라미터 사양은 공식 표에 행이 없어 **[미검증]**.
>
> ⛔ **미반영 (후속)**: `harness-engineering.md:1227` 참고문헌 행의 §1.1b 리다이렉트 · Tier 3 문서(`/permissions`·`/costs`·`/tools-reference`) 미수록 · **워크플로 스테이지 세분화**(resume 진행 보존 개선) 미측정 · effort sweep(P3) 미실행 — 3층 전부 `xhigh` 유지가 사용자 결정.

### v4.22.0 (2026-08-08) — 누적 릴리즈: fz-rebase 신설 · peer-review 인라인 게시 · Opus 5 대응 · 계측 도구 [MINOR]

> v4.21.0 이후 약 한 달간 발행 없이 커밋만 누적됐다(28커밋 / 59파일 / +3,293 −222). 초안 번호 `4.23.0`~`4.25.0`은 origin·태그·Release 어디에도 존재한 적이 없어 **폐기하고 누적분 전체를 v4.22.0 하나로 발행**한다 — 구간에 `[MAJOR]` 0건이므로 `4.21.0 → 4.22.0`이 semver 정합. 상세: [docs/releases/v4.22.0.md](docs/releases/v4.22.0.md)
>
> - **fz-rebase 스킬 신설** — 리베이스 조용한 유실 게이트. 1차안(유실 유형 L1~L6 열거)은 **열거가 빠뜨린 유형을 증명하지 못해** 폐기하고, 세 트리(PRE·BASE·POST) 경로 합집합을 **경로 단위 배타 분할**(MINE-only / not MINE / OVERLAP)로 재설계. 텍스트·바이너리·mode·symlink·gitlink·추가·삭제·이동이 열거 없이 판정 범위에 든다(커버리지 13/15). `verify-rebase.sh`(snapshot/audit/prepush) + 회귀 20/20 PASS. 성능 `audit` 10.4s → **0.4s**
>   - ⛔ 발견 3종: `git cherry`는 머지 커밋을 보고하지 않는다 · 바이너리 **268/3,214(8.3%)** 가 라인 검사 밖이었다 · awk `NR==FNR`은 첫 파일이 비면 출력이 통째로 사라진다(자체 결함, 회귀 스위트가 검출)
> - **fz-peer-review 인라인 라인 앵커 게시** — `--post`가 대화창 단일 코멘트만 달아 리뷰어가 파일을 직접 찾아가야 했다. `scripts/diff_anchors.py`(Python stdlib 전용) + `peer-review-inline-anchoring.md`(게시 7단계 SSOT) + PR #4655 픽스처. 겹치는 hunk는 **모두 반환하고 선택은 Lead에게** — 어느 hunk가 논지인지는 의미 판단
> - **발견 서술 원칙 모듈 신설** — 부정 주장은 후보를 소진해야 증명되고 순서 의존 결함은 경우를 전개해야 한다. 고정 필드에 안 들어간다. `peer-review-finding-anatomy.md` 원칙 3 + 형태 4종, 리포트 필수 필드 9 → 6
> - **peer-review 문서↔코드 계약 정합** — `counter` 키 부재로 `--deep`의 Stage3 산출이 **버려지고 있었다** · `agent_status` 보정은 도달 불가한 죽은 절 · Tier 표 모델 열 sonnet ↔ 실제 opus 3 · Tier 2/3 본문이 SKILL Boundaries와 정면 충돌(TeamCreate 필수 지시)
> - **Opus 5 출시 대응** — 1차 소스 8종 실측 후 15파일 갱신. ⛔ 코드(`workflows/*.js` effort 36곳)는 **미변경**(공식이 fresh sweep 요구). ⚠️ "검증 지시 삭제" 권고 오독 방어 = **게이트(구조) ≠ 지시(문구)** 경계 성문화. subagent 위임 방향 역전(4.8 under-reach → 5 over-reach = 캡 필요)
>   - **T0 실측**: `ultracode`는 effort arm 값이 **아니다** — env·settings 양 층에서 무효값과 구별 불가하게 조용히 무시(기준선을 medium으로 바꾸니 medium 반환). 무효 effort는 에러를 내지 않으므로 arm 적용 검증이 필수 방어. **사용자 결정: `xhigh` 유지**
>   - **effort 우선순위 확정**: env var > frontmatter > `settings.json`(*"a starting default, not enforcement"*) > 모델 기본. ⚠️ per-call `opts.effort`는 여전히 `[미검증]`
> - **문서 최신성 lint 신설** (`scripts/lint_doc_freshness.py`) — `last audited` 보유가 105개 중 4개뿐이라 fz가 자기 stale을 탐지할 수단이 없었다. SSOT = `llm-references.md`의 모델 정책 한 줄. 결과 audit 날짜 **4 → 12/22**, `stale-model-ref` **1 → 0**
> - **제약 부하 floor/ceiling 분리 계측** — 참조를 `catalog`/`citation`/`load` 3버킷으로 분류. `fz-plan` **45,808 → floor 13,694**(3.3배, 26,291이 로드가 아니었음). 단 **`fz` 자신이 floor 31,259로 최고** → 총량 우려는 기각이 아니라 **대상 이동**. ⛔ COST ≠ REMOVAL-SAFETY
> - **아키텍처 제약 배달 11/11** (`plan-collaborative.js`, 종전 8/11) — 누락 3곳 중 Stage 5는 역할이 *아키텍처 검증자*인데 제약을 못 받았다. ⛔ `OVERRIDE` 허용 입력에 라벨 열거가 **필수**(없으면 바이트가 도달해도 행동 계약상 무시 허용). 신설 모듈 0개(`project-arch-adapter.md` 폐기 — 기존 스킬이 이미 지시)
> - **fz-code plan 핸드오프 순서 버그 수정** — `Phase 0.5` 게이트가 자기 입력(plan 로드, 절차 1.5)보다 **38줄 먼저 평가**되고 있었다 → `Phase 0.4 Preflight` 신설
> - **Wave 4 TEAM 전면 일몰** — `workflows/peer-review.js` 신규로 TeamCreate+SendMessage 실행 경로 전면 제거(**실제 호출부 0건**). 채널 우선순위 원칙(브리프 > 에이전트 기본 지시) 성문화
> - **Codex 모델 pin de-version** — 실행 `-m` 13곳/4파일 제거 → config `model` SSOT 위임(항상 최신 frontier). CLI 버전 플로어는 호환 사실이라 유지
> - **figma 대조 3축 분리(원칙 H)** — 회고 R5의 "기준 부재" 진단은 **오진**(기준도 표도 이미 존재). direct property / 실효 거리 합성 / raw 미표현 축으로 분리. 실증: `gap 12 + padding 24 = 36`인데 코드 24 — **개별 노드값이 옳아도 합성을 안 하면 틀린다**
> - **인프라·문서 fix** — pre-commit 위반 출력 크래시(`${FILE}` 중괄호) · skill-testing §8 Task-Outcome Benchmark canonical · 다각도 리뷰 반영 3회분 · 관측/ledger 등재 9건
> - ⛔ **미충족 게이트 2건을 명시하고 출하**(사용자 결정): ① Wave 4가 요구한 `peer-review.js` 실 invoke 캘리브레이션 — `experiment-log.md` §5.7에 fz-peer-review 테이블 자체가 부재 ② 원칙 H가 요구한 회귀 fixture — 현재 oracle 0개. 둘 다 *기능 결함*이 아니라 *약속한 검증 미이행*이며 candidate/pending 표시라 기본 경로를 차단하지 않는다. 후속 릴리즈에서 해소

### v4.21.0 (2026-07-09) — 하네스 서베이 Wave C: code-pair pre-flight 크기 가드 (H5 scaffold collapse) [MINOR]

> plan-final Wave C — 유일 미구현 하네스 홀 H5 조치. 과거 실사고(~800줄 changeset → StructuredOutput 5회 재시도→null·27분·206K 토큰·디스크 무변경)의 재발 방지. 서베이 scaffold collapse(2605.12129) 강한 유사 구조 + retry budget(2605.21516). D1 사용자 승인, 코드 생산=opus Workflow, Lead(fable)=적용·게이트.
>
> - **C1 캘리브레이션**: changeset newBody 크기별 StructuredOutput 성공률 실측(sonnet ×4). 100/200/300/500줄 **전부 성공(null 0·의사코드 0)** → **임계 SPLIT_THRESHOLD=600 확정**(실증 안전 500 · 실증 실패 800 사이). ⚠️ 계획 초기 추정 150줄은 과도 — 실측이 교정(150이면 정상 500줄 Step 분할 강제 = over-decomposition, 2605.21516 반대 실패모드). 산출물 `~/dev/TVING/harness-paper/code/c1-calibration.md`
> - **C2 가드 (code-pair.js)**: ① pre-flight — `stepSpec.estimatedNewBodyLines`(Lead 추정) > 600 시 스폰 전 `mode:'split_required'` 반환(27분 낭비 회피) ② Stage1 null 경로 재정의 — `splitSuggested` 힌트(files≥4 OR complexity=5) + "일시 장애(세션/rate limit)는 재시도, Lead=fable SOLO는 사용자 승인" (H5 우려② 해소) ③ post-Stage-1 soft 경고(위험 구간 근접) ④ 소비처 4곳(헤더 계약 + fz-code/fz-fix/fz SKILL 반환 사다리)
> - **C3 검증**: node --check EXIT=0 · lint PASS(fable=3) · 격리 스모크 10/10(over-decomposition 방지·하위호환·null≠과대 구분 포함) · Codex check P2 2건 반영 — (a) arg 문서에 estimatedNewBodyLines 누락 시 가드 dead → fz-code/fz-fix arg 조립에 명문화 (b) null 경로 `est !== null` 프록시가 작은 Step 일시장애 오분류 → 제거(est>임계는 pre-flight가 이미 조기 반환)
> - **split_required는 하드 차단 아닌 Lead 판단 요구** — 경계 오판도 Lead 오버라이드 가능. 임계는 상수 노출(관측 실패에서 재조정)
> - ⛔ **자기참조 blind spot 방어**: code-pair.js 자기수정이라 Codex 교차검증 필수(2 P2 실측 확인 후 반영). **하네스 홀 H1~H5/F5/F6 중 유일 미구현이던 H5 조치 완료**

### v4.20.0 (2026-07-09) — 하네스 서베이 Wave B: 메커니즘/모듈 정합 + Governance Decay 실측 [MINOR]

> plan-final Wave B — 서베이 발견을 fz 메커니즘에 반영. B1(Governance Decay)은 실측 gate: 워커 OVERRIDE 경로(CLAUDE.md 미로딩)에서 ⛔ 규칙 유실 여부를 sonnet ×4 대조쌍으로 측정 → **unpinned 2/2 위반 → pinned 0/2**(서베이 2606.22528 구조 재현) → 강도=OVERRIDE 1문장(D5, over-engineering 회피). 생산 문안은 opus Workflow, Lead(fable)=적용·게이트.
>
> - **B2 Constraint Pinning**: 6개 워크플로 OVERRIDE에 거버넌스 방어 1문장(git 상태변경·raw codex exec 실행 제안 금지 → 사용자/스킬 경유). 실측 `~/dev/TVING/harness-paper/code/b1-measurement.md`
> - **B5 OVERRIDE 검증 규약 정합**: 6워크플로에 규약②(외부 모델 재포장 금지) 균일 삽입 + fz SKILL:326 "①②④ 포함, ③(git show)=격리 워커 미적용·Lead 소관"으로 문서-코드 불일치(G-2-03) 해소
> - **B6 승격 임계 canonical 통일(D3)**: `active:≥3세션`(cross-validation:455·fz-plan:246) → **5세션(promotion-ledger Track A)** + memory-guide에 canonical 참조. `≥3`=모듈 분리 자격이지 active 임계 아님을 명문화. 잔존 `active:≥3` 0
> - **B3/B7 서베이 근거 정성 반영**: complexity coupling modifier에 정보병목(C_min) 1행 + fz SKILL 오케스트레이션 프롬프팅 취약성 노트 · experiment-log Load-bearing에 컴포넌트 slice 분리 추적(집계 마스킹 방어)
> - **B4 memory-guide GC 망각축**: recall이 아니라 forgetting(intent-aware deletion·contradiction persistence, ForgetEval 2606.15903). fz-memory audit "모순 탐지" 권고
> - **B8 hygiene §7**: codex exec 프롬프트 선두 하이픈 clap 오파싱 → `--` 구분자 필수(이 세션 실측). §6 canonical wrapper도 `--` 반영(Codex check P2)
> - **검증**: lint PASS(36콜·fable=3) · JS 문법 전수 OK · Codex check P2 1건 반영(wrapper `--`). 참고문헌 8ad/8ae(2606.22953·29914)는 v4.19.0에서 추가 완료
> - ⛔ **Deferred → Wave C**: code-pair pre-flight 크기 가드(H5, C1 다축 캘리브레이션 선행). A5 push+gh release는 사용자 실행 대기

### v4.19.0 (2026-07-09) — 하네스 서베이 2026 반영 Wave A: 가이드 개정 + 워커 3-tier 재배선 확정 [MINOR]

> "하네스 엔지니어링 2026" 서베이(revfactory.github.io/harness-paper — arXiv 86편 에이전트 생성 메타분석)를 3층 검증(추출 인용 81건 환각 0 · fz사실 45/47 · Codex ×4)으로 분석 → 13주제 proposal → plan-final Wave A 실행. 전 편집 추가/각주만(+137줄, 삭제 0), 서베이 인용은 `[외부: … 원 논문 미대조]` 태그 + census-아님 단서 의무.
>
> - **harness-engineering.md 18편집**: §5.5 자기진화+회귀 게이트 신설(T2 최대 클러스터 — SEAGym 빈도 균형추, "현행 candidate 규율 유지가 정답") · 기둥3 서브시스템7 Constraint Pinning(Governance Decay 0%→30% — 압축=안전-critical 계층) + AP3 caveat · 기둥2 결정론적 안전 강제 원칙+capability≠authorization · §8/§10 멀티에이전트 근본 한계+역방향 게이트(C_min 정보병목·PerspectiveGap 14.9%) · §2.2 정량 앵커 최신화(19.1%→73.4%, 6배 격차) · §12 6책임 자기점검 격자+하네스 홀↔외부 수렴 근거 표(승격 아님 명시) · 참고문헌 2026-06 wave 21편
> - **skill-authoring.md**: 트리밍 비저하 3원칙에 "모델 전이 강건성" 외부 근거(절차적 체크리스트 > prose — 2604.25850, 근거 등급 낮음 명시) · **governance.md**: 결정론적 안전 강제 원칙 문단(훅 승격=settings.json 소유자 결정, 설치 지시 금지 불변)
> - **워커 3-tier 재배선 확정(fdcfe56)**: 실질 분석·생산 워커 opus 승격(동시 ≤3) · lint ①-b effort 명시 검사 신설 · governance 비용 envelope(≈opus 5 equivalent) · setup-codex-skills 플러그인 스킬 링크 확장
> - **검증 사슬**: 편집 문안 생산=Workflow(compose opus+review opus, pass) · 앵커 21/21 · AC1(137≤200)/AC8(200 OK) · Codex check 2이슈 반영(T8 식별자 충돌 해소 — fz 트리거 ID와 분리 표기 · 참고문헌 누락 2편 추가)
> - ⛔ **Deferred (plan-final Wave B/C)**: B1 Governance Decay 실측 gate → Constraint Pinning 메커니즘(D5) · OVERRIDE 정합(D2) · 승격 임계 promotion-ledger canonical 동기화(D3) · memory-guide GC 망각축 · hygiene §7(clap `--`) · code-pair pre-flight 크기 가드(H5, C1 캘리브레이션 선행). 산출물: `~/dev/TVING/harness-paper/`

### v4.18.0 (2026-07-06) — Fable 5 재배선: 판단=Fable / 수행=Opus·Sonnet [MINOR]

> 제재 해제(2026-07-05) 후 Lead=`/model fable`(B안 가동) + workflow **판단 지점 3곳**만 explicit `'fable'` 승격. 배선=가설/측정=검증(§5.8 사전등록) + lint 기계 감시. 구현 자체도 동일 구조로 수행(생산=code-pair 워커, Lead(fable)=적용·oracle·판정만).
>
> - **판단 지점 승격 3곳**: `search-cross-verify.js:166` stage3-merge(④ pilot 복원 — 기승인·측정 데이터 보유) · `plan-collaborative.js:154`/`:167` stage0-direction/final(⑤ 신설 — 판정문 출력이라 비용 할증 최소). 생산 스테이지(rebuttal/draft/integrate)는 opus 유지(AC-1)
> - **측정 사전등록**: §5.8 ④ 동결→재개 · ⑤ direction verdict 신설(N=3, control=retro-baseline fz-plan #1-2 — fable 세션 #3 제외로 대조군 오염 방지, 12필드 row schema)
> - **lint 신설**: `scripts/lint-model-explicit.sh` — agent 호출 model 명시 전수(36 calls) + fable=3 고정 양방향 + `CLAUDE_CODE_SUBAGENT_MODEL` 경고. AC-1/2/6이 문서 규약→**기계 검증**으로 승격 (negative test 2종)
> - **문서 동기화 8파일**: fable-model-guide(제목·배너·§5 B 가동/C 부분적용/운용 패턴 3종/Appendix→본문 표제) · team-registry:13 · context-artifacts:240 · governance(모델 동시 상한 행 신설: fable 1·opus 2) · fz SKILL(2-Tier→3-Tier, frontmatter `main: fable`, Lead(F)) · skill-authoring(:509 워커 기준·§8 Lead=fable·§12 model 명시 의무+lint)
> - **검증 사슬**: code-pair 검토 스테이지 실이슈 11건 캐치·반영 · Codex check **clean** · 세션한도+인터넷 중단 2회를 journal resume 캐시로 복구(stage 손실 0, §5.7 fz-code #2)
> - ⛔ **Deferred**: C안 확산(plan integrate·recheck / discover merge·landscape / review arch — ④⑤ N=3 임계 게이트) · 워커 effort layering · Wave 4 TEAM 일몰은 [Unreleased] 유지(캘리브레이션 대기). 상세: [docs/releases/v4.18.0.md](docs/releases/v4.18.0.md)

### v4.17.0 (2026-06-29) — 가이드 모더나이제이션 + 가이드 준수 remediation [MINOR]

> 외부 최신 권위 자료로 가이드 모더나이제이션 → 갱신 가이드 기준 플러그인 전체 감사 → remediation ①②③④ → 다각도 리뷰. 검증 사슬 각 단계가 직전을 교정.
>
> - **모더나이제이션(guides)**: `llm-references.md` 신규(Tier1/2/3 + arxiv 16 실증 + anti-pattern + deprecated 정책) · MAST(2503.13657) active 환원 · Opus 4.8 단일화(이전 버전 제거, fable frozen) · skill-testing §6.4 + §4 표 허용.
> - **remediation ①②③④**: ① Fable frozen 전파(modules) · ② when-not 라우팅 17 스킬 · ③ Workflow 전환 일관성(fz·agent-team·agents 5·build) · ④ test-spec 17/17(Option A 10 + references 7) + eval §6.4(coverage recall≥90/verification precision≥80) + Few-shot 5스킬 ≥3쌍 + `examples/hooks.json.example`(opt-in, active 배선 0).
> - **다각도 리뷰(--team --deep)**: 22 agent / 5차원 + adversarial verify → 16 findings 중 확정 8(전부 minor/nit, critical/major 0)·반증 8. CAL-1(Option B 7 버퍼 복원)·D1-4(precision 용어)·CAL-6(§9 비면제) 반영.
> - ⛔ Codex cross-model 미수행(quota ~6/30) — 동종 fresh-context Claude Workflow 대체(이종 안전망 상실). 회복 시 후행. 상세: [docs/releases/v4.17.0.md](docs/releases/v4.17.0.md)

### v4.16.0 (2026-06-27) — SKILL.md 분리 + visual oracle 강화 [MINOR]

> TVG-1219(유튜브식 플레이어 제스처) 작업 교훈을 fz에 환류. fz 자기참조 검증의 구조적 한계(동종 self-review)를 `/fz-manage check` + 사용자 catch로 보완. C(§1분리)는 가이드 위반으로 revert.
>
> - **fz-review visual oracle 강화 (검증5/Gate)**: UI/제스처/애니메이션 동작 변경 시 빌드통과 ≠ 완료, visual oracle(시뮬+스크린샷/실기기) 미충족 시 "완료" 지양 — fz 런타임 정적검증 불가 = 사람 영역. evidence 3 sessions(38차·user_spec·TVG-1219).
> - **SKILL.md 500↓ 분리 (Progressive Disclosure)**: fz-review 560→436(검증 4-D~H·4-N/O → `modules/review-checks.md` MOVE), fz-peer-review 523→463(Auto-Tier bash → `modules/peer-review-tiers.md` SSOT 일원화 + 판정 변수 명확화). 전체 SKILL.md ≤500.
> - **candidate 2종** (evidence 1 session): P1 Sibling-Convention Check(skill-authoring) + L-5 대칭/짝 경로(promotion-ledger).
> - **fz-memory L1 audit 강화**: entry 200자 초과 + MEMORY.md↔topic 양방향 정합(orphan) + organize 제안.
> - **Reverted**: C(§1 → skill-lifecycle.md 분리) + M4(헤더) — `feedback_guide_line_limit`(guides/ 500 면제·분리 금지) 위반을 `/fz-manage check`가 전제 catch → revert(P1 보존).
> - ⛔ Codex cross-model verify 미수행 (quota ~6/30) — 동종 Workflow 3-lens + Lead 실측 대체(false positive 2건 차단, 23차 실증). 회복 시 후행. 상세: [docs/releases/v4.16.0.md](docs/releases/v4.16.0.md)

### v4.15.0 (2026-06-18) — 외부 리뷰어 catch 환류 회로 (promotion-ledger 트랙 C) [MINOR]

> CodeRabbit 등 외부 이종 리뷰어가 fz-review 미탐 이슈를 잡았을 때 fz 자기개선 회로로 환류시키는 인프라. ASD-1793 PR에서 CodeRabbit이 fz가 놓친 retain cycle을 catch한 사례 분석(4-lens Workflow) 결과 — fz는 *능력*이 아니라 *환류 회로*가 단절돼 있었음(입구 pr-comment-review #19는 존재, 출구 4모듈 단절).
>
> - **promotion-ledger 트랙 C 신설**: 외부 도구가 `/fz-review --deep` 이후 actionable Major+ 발견 시 ledger 관측 진입 (4-classify project-rule/valid-suggestion만 카운트 → precision ~55% FP 차단). 관측 형식에 `finding-source` 필드 + P2-C(general closure-capture retain cycle lens) 관측 #0 등록.
> - **pr-comment-review #19 펜**: user-confirm 후 `import-to-ledger` 절차 추가 → 외부 fz-miss를 Issue Tracker + 트랙 C에 자동 기록. 트랙 C를 작동시키는 트리거(펜).
> - **fz-review Codex 불능 폴백 보강**: fresh-context Claude 검증자가 fz-reviewer Memory Management(retain cycle) 체크리스트 명시 적용 → Codex 부재 시 이종 parity 복원 (이번 miss 직접 처방). PR open 시 CodeRabbit 보조 이종 소스 안내.
> - additive only (행 삭제 0) · 검출 Grep rule 신설 0 (safety-audit Grep lens는 트랙 C 3세션+ 후 deferred — memory-guide:45). breaking change 0.
> - ⛔ Codex cross-model verify 미수행 (quota ~6/23) — 가이드 grounded(memory-guide:45 · prompt-opt:153-167 트리밍 비저하) + anchor probe 전수 검증 대체, 회복 시 후행. 상세: [docs/releases/v4.15.0.md](docs/releases/v4.15.0.md)

### v4.14.2 (2026-06-16) — fz-code 구조 평가 convention 면제 [PATCH]

> fz-code `관찰 보고 의무`가 Clean Architecture 위반 보고 시 코드베이스 컨벤션(동일 패턴 3곳+)을 위반으로 오보고하지 않도록 convention 면제 + same-RIB DI 중복 예외 추가. 구조 평가 modality 비대칭 분석(3소스: 증거에이전트 3 + adversarial challenger + Codex gpt-5.5) 결과 — 하드룰=과적합이라 flag-only로 calibrate. breaking change 0 · 신규 row 0(기존 row MERGE).

#### 개선 (동작 정밀화)
- **convention 면제 + same-RIB 예외** (`skills/fz-code/SKILL.md:233`): "동일 패턴 코드베이스 3곳+ → convention 간주 보고 생략(예: 로컬 UseCase 생성, 56 Interactor 중 27%)" + "같은 RIB scope에서 Component 주입 dependency를 Interactor가 동일 재생성 시 convention 무관 보고". 구조 위반 포착은 유지 + 코드베이스 관행 false-positive 차단.
- skill-authoring §3 DELETE/MERGE-default 준수 — 신규 row 0, 기존 row MERGE.

> ✅ Codex cross-model verify **수행** (quota 차단 ~6/28 해제 확인) — needs_revision → 3보완 반영(same-RIB wording 한정 + behavioral probe SC5/SC6 + 잔여리스크). 상세: [docs/releases/v4.14.2.md](docs/releases/v4.14.2.md)

### v4.14.1 (2026-06-14) — Fable 5 제재 대응 롤백 [PATCH]

> Fable 5가 미국 제재로 외국인 사용 금지 → 세션 모델 Opus 4.8 운용. v4.14.0 Part A에서 배선한 fable 의존부를 롤백. 가이드 본문은 제재 해제 시 재사용 위해 보존(상태 표기만). breaking change 0 · 행 삭제 0(코드 5줄 변경 + 문서 freeze 표기).

#### 롤백 (동작 변경)
- **synthesis 모델 opus 복귀**: `workflows/search-cross-verify.js` stage3-merge `model: 'fable'` → `'opus'`. `model` 생략(세션 상속)은 `fz:plan-structure`의 `model: sonnet` 정의 때문에 sonnet 강등 위험 → explicit opus(검색 에이전트 sonnet 대비 synthesis 우위 유지). 3개 synthesis 지점(search/plan/discover) opus 통일. fable 해제 시 `'opus'→'fable'` 1줄 전환.
- **effort frontmatter 제거**: fz-plan·fz-review·fz-discover·fz-search 4스킬 `effort: xhigh` 제거. effort 우선순위(env var > frontmatter > 세션)상 frontmatter가 세션 max/ultracode를 xhigh로 하향시키므로 세션 레벨 운용으로 전환 [verified: code.claude.com/docs/en/model-config].

#### 측정/문서
- §5.8 측정 큐: ④synthesis(fable) **동결**(제재 해제 시 재개 — 사전등록 임계 보존) / ①effort(frontmatter) **철회**(측정 대상 소멸) / ②③ 유지.
- `fable-model-guide.md`: 상단 제재 배너 + §3 표·§5 effort 섹션 상태 표기 (사양 본문 보존 — 재사용 대비).

> ⛔ Codex cross-model 미수행(quota ~6/28) — fz-discover Constraint Probe(A2 sonnet 강등 위험 실측 차단, 31차) + node --check + grep 전수 검증 대체, 회복 시 후행 check. 상세: [docs/releases/v4.14.1.md](docs/releases/v4.14.1.md)

### v4.14.0 (2026-06-13) — Claude Fable 5 대응 + 전수 주장 오판 방어 [MINOR]

> 통합 릴리즈 — **Part A**: Claude Fable 5 대응 (Fable 세션) / **Part B**: 전수 주장 오판 방어 (별도 세션, 2026-06-12). 두 작업이 발행 전 로컬에서 합류하여 단일 MINOR로 통합.

#### Part A — Claude Fable 5 대응: 모델 가이드 신설 + 효율 배선 + TEAM 레거시 정리

**핵심**: Claude Fable 5(2026-06-09 GA, Opus 상위 tier·$10/$50) 대응 풀 사이클 — 공식 문서(Tier 1) 기반 신규 모델 가이드 + 기존 가이드 6파일 갱신 + effort/프롬프팅 적재적소 배선 + Workflow 전환 잔재 정리. 모든 배선은 §5.8 측정 큐 사전등록 동반(배선=가설/측정=검증, 31/35차). 플랜: plan Workflow(9 agents, 5/5 stages) + fresh-context 검증 2회(v1·v3 needs_revision → v2·v3.1 정정 — Workflow `[verified]` 오측·승계 Step 교차 모순 등 M2+L4 catch). breaking change 0.

**F1 — Fable 모델 가이드 (docs)**: `guides/fable-model-guide.md` 신설 — 사양/API 동작 차이/Claude Code 통합(effort frontmatter·자동 폴백·서브에이전트 fable enum)/공식 효율 권고/fz 적용 전략(모델 4-axes 옵션)/스니펫 채택 현황 표. + prompt-optimization Sources(last audited 2026-06-12)·harness-engineering 모델 세대표·agent-team-guide §4·skill-authoring·skill-troubleshooting·team-registry·context-artifacts 환경 표기 Fable 갱신.

**F2 — Codex 장기 불능 플래그 (feat)**: fz-review 에러 표 + codex-strategy.md — 기간이 알려진 quota 차단(예: ~2026-06-28) 시 재시도 생략·불능 분기 직행. ⛔ 무기한 표기 금지 + 만료 시 원복 명시 (MEMORY.md 동기화 단일 포인트).

**F3 — fresh-context 검증자 배선 (feat)**: fz-review Phase 5 검증 2(Codex 필수)에 불능 분기 — fresh-context Agent 1-spawn(model 명시 의무 — Fable 세션 자동상속 비용 2배 방지), `[fresh-context: claude]` 태그로 이종 안전망 상실 명시. Workflow 폴백과 직교 조건. 근거: Fable 공식 "fresh-context verifier > self-critique" + 본 사이클 3연속 catch 실증.

**F4 — effort 적재적소 배선 (feat)**: fz-plan·fz-review·fz-discover + fz-search(사용자 피드백 추가) frontmatter `effort: xhigh` (capability-sensitive **4스킬** — max는 frontmatter [미검증]으로 미배선, medium 강등 측정 전 금지) + fable-model-guide §3 사용 시점 가이드(high/xhigh/max/ultracode).

**F5 — grounded progress 채택 (feat)**: Fable 공식 스니펫 7종 실측 선별(채택 1/보강 1/비채택 5 — 근거 표 기록). 채택분: fz SKILL VD Brief 4번 + team-core 트리거 주입 + workflows 5파일 OVERRIDE("주장은 도구 결과/입력 데이터 근거 지목 가능해야") — `[verified]` 오측(16/18차 + 본 사이클 Workflow 에이전트 실증)의 구조 방어.

**F6 — TEAM 레거시 STALE 교정 (chore)**: Workflow 전환 완료 4스킬(fz-plan/code/review/search)의 "TeamCreate 강제" 문구 → "Workflow 미가용 시 SOLO 폴백 협업 프로토콜 (canonical 패턴 출처)" — 행 삭제 0(canonical 출처 보존), STALE 외 보존 참조(fz-discover·fz-fix 포함) 전부 무변경.

**+ §5.8 측정 큐 (chore)**: experiment-log §5.8 신설 — ①effort 효과 ②fresh-context catch ③절차밀도 A/B(R8 확산 게이트, fz-search pilot) ④synthesis fable vs opus(**활성** — 2026-06-12 사용자 합의, 06-13 pilot 적용 완료: search-cross-verify stage3-merge `model: 'fable'`). 사전등록 임계 변경 금지 + session_model 필드 의무.

**검증**: node --check 5/5 + verify grep 전수(STALE 0건·OVERRIDE 5건·effort 4건·workflows `model:` 필드 무변경) + reasoning_extraction 전수 grep 0건 + review Workflow(5 agents — findings 7: major 2/minor 5, FP 0, 전건 수용 반영). ⛔ Codex cross-model 할당량 차단(~6/28) — F3 fresh-context 분기가 본 사이클의 폴백 실증. 회복 시 후속 재검증.

#### Part B — 전수 주장 오판(Exhaustive-Claim) 방어 + light 모드 검증 경계

**핵심**: api.tving.com 토큰 조사 세션에서 `rg|head -5` 잘린 출력을 "사용처 2곳뿐"으로 단정(실제 11곳)한 오판이 가짜 교차확인을 거쳐 4턴 생존한 사고의 재발 방지 최소 세트. 기존 방어(Coverage Gate·T6/T7·Cross-Verify)가 전부 존재했으나 **light 경로가 전량 우회** — "방어 부재"가 아닌 "방어 우회"가 근본 원인(RC1 라우팅 어휘 기반 / RC2 출력 커버리지 미정의 / RC3 멀티턴 캐싱 무방비 / RC4 교훈 키잉 과소 일반화). 신규 모듈/Phase/Gate 0건, 23파일 전부 기존 구조 내부 확장. breaking change 0.

**F1 — light 모드 검증 경계 (feat)**: `lead-action-default.md` 40차 row + `fz/SKILL.md` simplified_keywords·abbreviated recall(:136) — "light = 절차 생략이지 검증 생략 아님". 산출물이 전수/카운트/부정 주장이면 `Read(cross-validation.md §Coverage Gate)` 후 적용 (인라인 Read 명령으로 텍스트→로드 다리 확보). [미검증: light 라우팅의 Step 4 실행 범위 — LLM 해석 의존, 후속 ③]

**F2 — Coverage Gate 확장 (feat)**: 트리거 **기준** 확장(요청 어휘 OR **산출물 타입** — "확인해줘"형 light 요청의 전수 산출물 포착) + **canonical 선언**(Q-COVERAGE·fz-search/fz-discover Gate·T8 4곳 미러 동기화) + 절차 5항(명령 출력 커버리지: head/tail 잘림 금지 + `wc -l` 병기) + 6항(분할 합계 검산식 — 정규식 불완전 가짜 교차확인도 검산 불일치로 탐지) + Gate 조건 2항 + BAD/GOOD.

**F3 — T8 리마인더 신설 (feat)**: `system-reminders.md` — 전수/카운트 주장 + event signal(측정 도구 미호출 재인용/원 측정 부재/잘림 흔적, T6 형제 AND 패턴) 감지 시 재실측 요구. Backstop 5턴 예외 비상속. 에이전트 12파일은 **포인터 레이블 행만** `(T6/T7/T8)` 동기화 — 행동 규율 행은 멀티턴 전용 T8 부적용으로 유지(dead rule 방지, 리뷰 A:A1).

**F4 — 교훈 키잉 규칙 (feat)**: `memory-guide.md` Write Policy — 교훈은 도구·맥락 한정이 아닌 **실패 클래스**로 서술 ("Codex 출력 head 금지" ✕ → "전수 주장 근거 수집 시 출력 잘림 금지" ○).

**+ OQ1 — 4 스킬 light/Gate 동기화 (feat)**: fz-plan/fz-review/fz-code light 섹션 + fz-discover Gate 1 — 산출물 타입 조건 1줄씩.

**검증**: plan Workflow(9 agents·5 stages — 실측 신규 발견 4건: :136 사문화 위험/Q-COVERAGE 이중 진입점/에이전트 dead rule/memory-guide :30 충돌) + review Workflow(findings 18: major 8/minor 10, FP 0 — **적용 전 리뷰**가 plan 구조 결함 2건 포착, 전원 수용 → plan-v2) + 기계 verify 스위트(줄 수/카운트/과잉 교체/canonical 동기화 전수 통과). ⛔ Codex cross-model은 할당량 차단(~6/28)으로 미수행 — 회복 시 후속 재검증 5항.

### v4.13.0 (2026-06-11) — Template Authority Bias 방어 + 구조 결정 옵션 사용자 배선 [MINOR]

**핵심**: ASD-1802에서 fz 풀 파이프라인이 외부 인간 리뷰어 지적 3건(Component의 UseCase 직접 생성 / didBecomeActive `MainActor.assumeIsolated` / boolean trap)을 **0건 선행 포착**한 실패 분석(RC 5개)의 최소 수정 세트. 층위 분리 설계 — 원칙층(45차 메모리+개방 단서) / 발화층(token·트리거·few-shot) / 전달층(사용자 배선) / 분류층. 6 커밋, 11파일. breaking change 0.

**F1~F4 — 파이프라인이 잡게 (feat)**:
- `agents/review-direction.md`: Structural Fit에 **구조 결정 3축 Quick-Check**(DI 출처·스레드 가정·public API 모양) — 템플릿/형제 미러링 계획이라도 3축은 "이미 결정됨"이 아닌 결정 대상, 축별 대안 ≥2 + 1줄 trade-off. 개방 단서(표에 없는 구조 결정도 동일 원칙) 포함
- `modules/swift-pattern-detection.md`: 원칙 E token에 `MainActor.assumeIsolated`·`nonisolated`(생명주기 콜백 맥락)
- `modules/plugin-refs.md`: Level 2 역방향 트리거에 프레임워크 생명주기 콜백 행 — bridge 3택(assumeIsolated=crash 덫 / Task hop=보장 / `Task.immediate` iOS 26+ [verified]=동기) trade-off 1회 제시 의무
- `agents/review-quality.md`: boolean trap BAD/GOOD few-shot (`fetch(reset:)` → 의도별 분리)

**G1·G3 — 사용자에게 보이게 (feat)**: PROCEED 경로에서 옵션이 생산돼도 사용자에게 도달하지 않던 배선 결손 해소 — `plan-collaborative.js` workflow 반환에 `directionAlternatives` 패스스루(PlanSchema·에이전트 프롬프트 무변경) + fz-plan 반환 처리 별도 병합 지시 + Gate 0.5(SOLO 조기)·Gate 1(병합 확인) 체크 + plan-deep-planning 절차 7 "구조 결정 옵션 테이블"(PROCEED여도 **사용자 보고 시 표로 제시**). G3: 발동 조건 분류 정정 — 미러링으로 신규 화면·컴포넌트 생성은 '단순 수정' 아님(스킵 불가).

**fix**: swift-pattern-detection 내장 self-test 자기참조 매칭(카운트 7≠4 상시 실패) → `^### 원칙 [DEFG]` anchoring, PASS(4/4).

**검증**: counter 에이전트 2회 approve(핸드오프 충실도 16/16 + delta 0이슈) + Review Squad 2회(plan 문서 리뷰 findings 15 처분 / 적용 diff 리뷰 findings 11 — critical/major 0, 발화 체인 정적 도달 전부 확인) + 결정론 oracle 전수(grep baseline 0→1 + 내장 self-test + §12 래핑 check·스모크 invoke). ⛔ Codex cross-model은 할당량 차단(~6/28)으로 미수행 — Claude 단독 한계(RC4) 명시, 회복 시 후행 check.

**알려진 제약**: `directionAlternatives` full-path 실반환은 다음 fz-plan TEAM 실사용에서 확인 / 3축 실발화는 ASD-1889 실측이 최종 oracle / escalation `alternatives` 키 비대칭·Stage 4 직접 통합·Output Format 3축 행은 실측 후 후속(O7).

### v4.12.1 (2026-06-08) — Serena MCP 플러그인 번들 + 미노출 도구 참조 정리 [PATCH]

**핵심**: Serena MCP를 `.mcp.json`으로 플러그인에 번들 — `claude plugin install fz` 시 자동 등록(수동 `claude mcp add` 불필요). 동시에 serena 1.5.4 `claude-code` 컨텍스트가 노출하지 않는 3개 도구 참조를 전 스킬·에이전트에서 정리. 4 커밋, 27파일. breaking change 0.

**`.mcp.json` 번들 (feat)**:
- `{ "serena": { "command": "uvx", "args": ["--from","git+https://github.com/oraios/serena","serena","start-mcp-server","--context","claude-code","--project-from-cwd"] } }`
- 공식 serena 플러그인 포맷 + `--context claude-code`(공식판은 desktop-app default라 Claude Code 비최적) + `--project-from-cwd`. repo root = 플러그인 root(marketplace `source: "./"`). 런타임 `uv` 필수.

**미노출 도구 참조 정리 (refactor)**: serena `claude-code` 컨텍스트 미노출 3종 — `search_for_pattern`→`Grep`, `find_file`/`list_dir`→`Glob`/`Read`. skill allowed-tools 10 + agent tools 7(+fz-memory 공유줄) + 본문/prose 지시 + fz-search 예시블록·에러표 + skill-troubleshooting 폴백체인 재번호. 24파일 60 edit, frontmatter 무결성 검증, 전 범위 0 잔여. 심볼·메모리 도구는 노출되므로 핵심 기능 무손상.

**문서 (docs)**: README prerequisite 교정 — `AbanteAI/serena`(stale, repo 이전)→`oraios/serena`, "settings.json 수동 등록"→"자동 번들 + 런타임 `uv` 필수".

**활성화**: push 후 `claude plugin update fz` → `/reload-plugins`(또는 재시작) → serena 서버 승인. 설치본은 별도 클론이라 version bump 필수(누락 시 update 스킵).

### v4.12.0 (2026-06-06) — TEAM → 네이티브 Workflow 전환 (Wave 0-3) [MINOR]

**핵심**: TEAM(TeamCreate+SendMessage P2P) 멀티에이전트 실행을 네이티브 Workflow 결정적 스크립트로 전환 — 5개 스킬(discover/search/review/plan/code·fix) 전부. 통신 유실·팀 정리 실패 2대 오류 클래스가 구조적으로 제거(전 invoke 0건). 10 커밋, 17파일 +1336/-273. breaking change 0.

**workflows/ 신설 (5 스크립트, 1094줄)**:
- `discover-adversarial.js` (pilot) — lean 5-call / --deep 렌즈 3 fan-out → merge(MergedPathSetSchema 12) → 경로별 평가 chunk ≤4
- `search-cross-verify.js` — 심볼/패턴 독립 병렬 → 교차 FP 제거 → 병합 + 신뢰도 등급(스크립트 binary rule)
- `review-live.js` — arch(opus)+quality(sonnet) 병렬 → id-기반 교차 severity 조정 → counter DA(okAreas 도전) → 스크립트 병합
- `plan-collaborative.js` — direction 판정(조건부 반박 왕복) → 초안 → 병렬 3렌즈 → CC 교차 2 → 통합(§X/§Y/§Z + RTM + implicationRegister) → 재검증 (9-11 call)
- `code-pair.js` — impl changeset JSON(에이전트 디스크 미수정, exact syntax + oldAnchor) → 조건부 arch 검토(pass 시 Stage3 생략) → Lead 적용+빌드 (Step당 1 invoke, 책임 재배분)

**표준 패턴 3종** (`guides/skill-authoring.md` §12 신설): ① OVERRIDE 블록(P2P + 에이전트 정의 컨텍스트 로딩 무효화 + 무관 폴더 금지) ② args 방어 파싱(scriptPath 호출 시 args가 JSON 문자열 도착 — probe 실측) + fail-fast ③ agentType `fz:` namespace 필수. 명명 워크플로우 자동 등록(meta.name → 스킬 목록) 실측 반영.

**SKILL 5종 교체** (순감소 + 트리밍 비저하): fz-discover / fz-search(402→387) / fz-review(583→555) / fz-plan(483→452, 6렌즈 표 보존) / fz-code(435→405) / fz-fix(341→320). Gate·Few-shot·마찰 신호 표 전체 보존 + Lead 잔류 책임(Codex validate·RTM·memory recall) 명시.

**calibration 게이트 사전 등록** (`experiment-log.md` §5.7): 스킬별 임계(discover 5건 / search·review·plan 3건 / code·fix 3세션) + G1(패턴별)/G2(품질 — 기계 지표 한계 실증 2건)/G3(일몰). TEAM 모듈은 legacy 보존, Wave 4 일몰은 게이트 통과 후.

**검증**: 실 invoke 10회(§5.7) — null 0 / fallback 0 / 통신·정리 오류 0. changeset 적용 2회(oldAnchor 5/5). ⛔ Codex cross-model 미수행(할당량 부재, 다각도 Claude 리뷰 대체) — 후행 check 4건 누적.

### v4.11.0 (2026-06-04) — Opus 4.8 정합 + 인용 위생 + 하네스 구조 개선 [MINOR]

**핵심**: fz 가이드를 Opus 4.8 공식 사양에 정합화 + arXiv 원문 대조 인용 수치 정정 + 하네스 구조 개선. 3 기능단위 커밋, 16파일 +80/-51. breaking change 0.

**Opus 4.8 정합** (`anthropic.com/news/claude-opus-4-8` verbatim):
- effort 기본 high(xhigh/max 선택) / 자기 코드 결함 통과 ~4x↓(self-eval 개선) / tool-calling 효율↑(required-call skip↓) / 단일 세션 수백 parallel subagents — fz 적용 4-bullet (harness §10).
- 4.7 내용 제거: length-limit(04-16 적용→04-20 철회, ~3% 성능저하)·Cobus "harness release"·partially-verified 태그. §8 "literal"(4.7 community)→"instruction-following consistency"(4.8 공식). 모델 참조 claude-opus-4-8.
- ⛔ 제거된 미검증 주장(공식과 배치): "fewer subagents"·"SWE-Pro 69.2%"·"literal" (이전 세션 [미검증: wp0rdknnz]였으나 공식 fetch가 배치 확인).

**인용 위생** (arXiv v3 원문 대조):
- MAST: FC2 inter-agent 67%→**36.94%** (FC1 41.77/FC3 21.30, 논문 명시 "단일 지배 카테고리 없음"), FM-2.2 **6.80%** + MAST-Data 7개 프레임워크/1642 traces. MAST active 인용(4곳).
- OpenDev: 도구 카테고리 7→8(§2.4)·서브시스템 6→7(§2.3)·"instruction fade-out" 턴수치 제거(논문 미명시).
- NLAH IHR ~74%에 benchmark subset caveat / Context Rot "64K 전모델"→"보편 임계값 없음(Chroma)".
- codex-skills/fz-challenger의 "67% 가장 치명적"(verified 태그) 모순 해소.

**하네스 구조 개선**:
- harness §5 **원칙7(운영점)**: effort(추론깊이)≠SOLO/TEAM(에이전트수) 레버 구분 + max+ultracode 운영점 함의.
- skill-authoring **WS4 DELETE/MERGE-default** 편집 operating rule (additive-only 방어, IFScale 근거).
- complexity **parallelizable modifier**(coupled→single-thread, 별도 게이트 아님) + cross-validation **A3**(동종 합의 ≠ 독립검증).
- harness Index §7/§11 ref 정정 (Module Ablation 방법론은 §11).

**Cross-model 제약**: Codex(GPT) 할당량 초과로 본 릴리즈는 동종 Claude 다관점 검증 + 공식 docs verbatim 대조로 진행. cross-model 재검증은 복구 시 권장.

상세: `docs/releases/v4.11.0.md`.

### v4.10.1 (2026-06-02) — 하네스 self-maintenance + figma candidate 신호 [PATCH]

**핵심**: v4.10.0 이후 누적된 8 커밋의 하네스 유지보수 배치. ASD-1674/1718 figma 회고 기반 candidate 마찰 신호(비활성) + hot-path 슬림화 + 모델 세대 갱신(4.7→4.8) + ablation 측정 도구. **active 기능 0 → PATCH** — 모든 feat 커밋은 `5-session 관측 후 활성` gate 뒤 비활성 candidate이거나(figma 신호) 0-참조 dev 도구(측정 스크립트)라 플러그인 사용자가 관찰하는 동작 변화 없음. breaking change 0. 8 commits (TEAM plan+review로 검증, `TVOD/ASD-1718/fz-enhancement/`).

**candidate 마찰 신호 (비활성 — 5-session 관측 후 활성 결정)**:
- `feat(fz-code)` figma 신호 강화 (ASD-1718, `f3f6a5a`): `figma 수치 미측정` 신호에 **색/정렬(alignItems/justifyContent)/텍스트 style-run/z-order(childOrder)** 차원 + **data>render override 금지** 확장 + **`figma 텍스트 미대조`** 신규 candidate (2-session 재발 1674#2+1718#5). 42차 caveat는 *구조 데이터 부재(flattened IMAGE)* 한정으로 재범위화.
- `feat(fz-code)` candidate 신호 3건 (ASD-1674, `f9dc847`): 기존 인프라 미확인 helper / 표면 churn / figma 수치 미측정.
- `promotion-ledger` L-1~L-4 관측 #1(ASD-1674) + L-1 관측 #2(ASD-1718, 트랙 A 2/5). ⚠️ Codex verify PENDING — candidate→active 승격 게이트일 뿐 **릴리즈 무관**(candidate 추가엔 Codex 불요).

**hot-path 슬림화 / cleanup** (⚠️ destructive — behavior-preserving 검증 완료):
- `refactor(agent-team-guide)` (`f0a63ee`, **−103줄**): §3 5패턴 pseudocode 중복을 매핑 표 + `patterns/` 포인터로 압축 (550→457줄). operative pseudocode는 `modules/patterns/` 5파일에 보존 (검증: 5파일 모두 선존·더 풍부, f0a63ee가 patterns/ 미변경).
- `chore(cleanup)` (`25b5e0e`, **−50줄**): `plan-tradeoff.md.archived`(이미 아카이브) + team-registry 취소선 행 제거. active 참조 0건 (검증: 전 repo grep — 잔존은 역사적 CHANGELOG 인용뿐).

**maintenance**:
- `fix(cross-validation)` (`0a9c3b0`): Reflection Rate 계산식 schema 일원화 (schema=계산식 canonical, cross-validation=threshold/gating canonical). 계산식 `(resolved×1.0 + partially_resolved×0.5)/total` 불변 — 권한 분리 문서 정정.
- `docs(opus48)` (`20bc442`): Opus 4.7→4.8 stale 참조 갱신 (모든 미검증 주장 `[미검증]` 태그 보존, 역사적 citation 보존).
- `feat(scripts)` (`fa73cf2`): `measure_constraint_load.py` 신규 (COST 축 hot-path ablation 측정 도구, inbound 참조 0건 — dev-only, 사용자 미노출).
- `chore(gitignore)` (`3c73fc9`): `.fz-work/` 런타임 work dir + `experiment-log-traces.jsonl` 원시 텔레메트리 무시.

### v4.10.0 (2026-05-27) — Sycophancy 방어 + Active Recall + Reflection Pipeline Active [MINOR]

**핵심**: 사용자 self-diagnosis (`fz-meta-improvement-2026-05-26.md` — ASD-1137 PR 작업 중 22개 사용자 catch: Sycophancy 동의 편향 + Over-engineering 패턴) 기반 **6 Priority 개선**. Active Recall 강제화 + Sycophancy 방어 4원칙 + Reflection Pipeline Active 전환 + Phase 4 Default 역전 + fz-codex 모듈 분리 (757→268줄, skill-authoring 500줄 한도 준수) + fz-doc·fz-excalidraw 제거. 8 commits (+ 이전 세션 README 정리 2). 28 files / +1032/-2289 LOC.

**6 Priority 개선**:
- **P1 Active Recall 강제화**: `skills/fz/SKILL.md` Phase 0 Step 4 교훈 사전 로드 (선택)→(강제) + Gate 0 차단 (미회상 시 진행 불가)
- **P2 Sycophancy 방어 4원칙**: 무비판 동의·과잉 엔지니어링·근거 없는 칭찬·맥락 무시 차단 + 정정 의무 (TVING CLAUDE.md — 본 repo 외 + fz 전반)
- **P3 Base Verification Gate**: `modules/fz-codex-bash-hygiene.md` §5.5 (git diff 분석 전 base 상태 검증)
- **P4 Phase 4 Default 역전**: `modules/fz-pipeline-proposal.md` — implementation-ready 시 권고 기본값 = 구현 (verify-forever 방어, 메모리 33차)
- **P5 Scope Drift + 41차 Reuse-First**: `skills/fz-plan/SKILL.md` Phase 0.5 — universal/extensible 인프라 + 5+ 사용처 시 신규 작성 default 금지
- **P6 Reflection Pipeline Active**: `parse_memory.py` (한국어 cross-ref/meta-pattern + markdown link + originSessionId) + `score_relevance.py` (context-anchored 클러스터링 5a-5d, false positive 차단). Status Draft→Active(Partial)

**fz-codex 모듈 분리** (`skills/fz-codex/SKILL.md` 757→268줄):
- `modules/fz-codex-bash-hygiene.md` 신규 — §1-6 hygiene + §5.5 Base Verification Gate
- `modules/fz-codex-subcommands-{core,aux}.md` 신규 — 11개 서브커맨드 분리
- `cross-validation.md`·`feedback-verification.md` cross-ref 새 모듈 경로로 갱신

**스킬 제거**:
- `skills/fz-doc/` 제거 → `fz-skill` write 서브커맨드로 흡수
- `skills/fz-excalidraw/` 제거 (references 7파일)
- `intent-registry.md` 두 스킬 트리거 행 삭제

**스킬 품질 가드 (candidate)**:
- `fz-code`·`fz-review` 자산 추가/수정 시 가이드 명시 참조 의무
- `fz-review` 검증 4-N (Swift Naming) + 4-O (Session-added Assets) candidate — ASD-1366, 5 sessions 관측 후 활성 결정

**Cross-Model 검증**: fz-review 세션에서 Codex가 Claude self-review blind spot 3건 단독 발견 (module bash hygiene 미적용 / "자동 로드" 오기 / stale cross-ref) — 메모리 23차 재실증.

**Breaking changes**: 없음 (모두 additive). fz-doc/fz-excalidraw 사용자는 `/fz-skill write` + 외부 다이어그램 도구로 이전.

### v4.9.0 (2026-05-17) — Authority Network + Codex Ecosystem Hardening + fz-modernize 신규 [MINOR]

**핵심**: fz-plugin 가이드/스킬 + Codex 네이티브 스킬 + schemas에 외부 권위 자료 (Anthropic 공식 + arXiv 학술 + OpenAI Cookbook) 인용 네트워크 통합 + Codex self-reflexive 검증으로 발견된 plugin 감지 로직 critical bug fix. `/fz-modernize` 신규 메타-스킬 추가 (913 lines). Cross-Model 정량 효과 4회 누적 실증.

**Active Citation 추가**:
- Anthropic Multi-Agent Research System (2025-06): Token 80% performance variance — harness-engineering.md
- Anthropic Scaling Managed Agents (2026-04): emitEvent API contract — context-artifacts.md
- AgentFlow (arXiv 2604.20801): typed graph DSL — harness 참고문헌 + fz-planner
- MAST FM-2.2 (NeurIPS 2025, arXiv 2503.13657): "Fail to ask for clarification" 6.8% — lead-action-default.md, prompt-optimization.md (active 환원)
- Chain-of-Verification (arXiv 2309.11495): fz-fixer / fz-guardian / codex_verification_schema
- VeriGuard (arXiv 2510.05156): dual-stage verification (이미 active, codex_verification_schema 명시 추가)

**Stage 3 가이드 외부 권위 인용**:
- `guides/harness-engineering.md` — Token 80% + AgentFlow + 학술 자료 3건 보강 (#8h/8i/8j)
- `guides/prompt-optimization.md` — §1b TEAM 다양성 MAST FM-2.2 6.8% 정량 인용
- `modules/context-artifacts.md` — Anthropic A3 emitEvent API contract reference
- `modules/lead-action-default.md` — MAST FM-2.2 + 메모리 40차 trigger row 추가
- `modules/cross-validation.md` — 메모리 23차 (Self-review blind spot) explicit reference

**Tier 1+2 Claude 스킬 강화** (light 모드 + 36차 가드):
- `/fz` Phase 1 `simplified_keywords` 신호 (메모리 40차 자동 라우팅)
- `/fz-plan`, `/fz-code`, `/fz-review` `light` 모드 추가
- `/fz-code`, `/fz-fix`, `/fz-commit` 36차 팀 공유 영역 가드
- `/fz-commit` `PROTECTED_PATTERN` grep + ASR 의무

**Codex 8 네이티브 스킬 Authority + Memory Lesson inline**:
- 8 스킬 각 1건 Authority 인용 (Building Effective Agents / MAST / DSPy / CoVe / VeriGuard / AgentFlow / Three-Agent / Multi-Agent Research)
- Memory Lesson inline: fz-fixer (36차), fz-reviewer (23차), fz-architect (32차), fz-planner (31차)

**[CRITICAL] Codex Plugin 감지 로직 fix (Cbug-1)**:
- Codex self-reflexive verify 단독 발견 — `codex mcp list` ≠ plugin (계층 다름)
- 수정: `grep -q '^[plugins.' ~/.codex/config.toml && ls ~/.codex/plugins/cache/*/`

**Codex Strategy + GPT-5.5 Preamble + Simplified Mode** (Cgap-1/Cnew-2/Cnew-3):
- `modules/codex-strategy.md` 권위 인용 (Anthropic A2 + Context Rot + Codex CLI 0.124.0)
- GPT-5 Prompting Guide "Rephrase → Outline → Narrate" 3-step preamble 표준
- `/fz` simplified_keywords ↔ Codex `effort=medium` 자동 라우팅

**fz-codex Hybrid Routing + Codex System Skills** (Cgap-2/Cnew-4):
- OpenAI Codex CLI + GPT-5 Prompting Guide + ICLR Debate + CoVe 4건 권위 인용
- `~/.codex/skills/.system/` 5개 system skill 활용 매트릭스

**Codex Output Schemas 권위 출처** (Cgap-3):
- 3 schemas description 필드에 MAST / LLM-PeerReview / VeriGuard / CoVe 권위 출처 명시

**`/fz-modernize` 신규 메타-스킬** (913 lines, 6 files):
- 6-phase 파이프라인 (Probe → Audit → Plan → Verify → Execute → Validate)
- 10 메모리 교훈 통합 + AC1-AC11 (AC10 friendly bias / AC11 Self-Application 신설 금지)
- light 모드 + self-application contract + 4-axes 옵션 시각화

**fz-peer-review 4-Tier Graceful Degradation 확장**:
- Tier 0 (Solo, <100 changed lines) 신규 + 자동 휴리스틱 (gh CLI 기반)
- 옵션: `--tier N` (강제) / `--deep` (Cross-Critique) / `--codex` (challenger 추가)

**Cross-Model 정량 효과 4회 누적 실증**:
- Codex self-reflexive verify가 Claude self-review 대비 ~5배 발견 효과
- 회당 평균 5건 단독 발견 (analysis / plan / ecosystem / final-review 각각 needs_revision)
- Claude family blind spot: 권위 인용 누락 ~17%, systemic blind spot ~50%

상세: `docs/releases/v4.9.0.md`.

### v4.8.0 (2026-05-06) — Cargo-Cult Defense + Lessons-to-Module Pipeline 도구화 [MINOR]

**핵심**: ASD-1260 redundant import 사례를 트리거로 cargo-cult 패턴 *작성/리뷰/컴파일* 3중 다층 가드 + 누적 메모리 교훈을 fz 모듈에 반자동 반영하는 `/fz-manage reflect-to-module` 도구화. 메모리 17차(Reflection Gap)에 부분 응답.

**5 메모리 e2e 검증** (precision 100% 유지):
- 19차 (Pilot): 100% recall (5 modules)
- 18차 (Sanity): 80% recall — overfit 검증
- 15+16차: 67% recall (mixed file 한계 인정)
- 17차: N/A (system-level, 자동화 범위 밖)
- 33차: 50% recall
- 34차: 60% recall
- **평균 71.4% recall / 100% precision** (Gate 4 PASS at 70% threshold)

**3중 다층 가드** (Phase 1):
- 작성 시점: `impl-correctness` Cargo-Cult Detection 섹션 + Workflow 4번 호출
- 리뷰 시점: `fz-review` 검증 4-E 항목 7 양방향 + `review-quality` Perspective 8
- 컴파일 시점: TVING `.swiftlint.yml` `unused_import` rule (사용자 brew install 후)
- `fz-code/SKILL.md` 마찰 신호 카탈로그 31번째 "Redundant Import" 추가

**Lessons-to-Module Pipeline 도구화** (Phase 3):
- `skills/fz-manage/scripts/parse_memory.py` (280줄) — Memory Parser (12 필드 추출)
- `skills/fz-manage/scripts/score_relevance.py` v2.1 (270줄) — Relevance Scorer (5 component 점수, threshold 0.70)
- `skills/fz-manage/prompts/generate_suggestion.md` (170줄) — Suggestion Generator (5 type 분류)
- `fz-manage/SKILL.md` `reflect-to-module` 서브커맨드 통합 + Codex micro-eval 의무

**Day-by-Day Calibration 9 fix 누적** (Phase 4):
- Parser 5: SKILL_TAG / SELF_ID / hyphenated review / applies-to / split [공백,쉼표]
- Scorer 4: cluster 3 (scope 유의어) / cluster 4 (silent disappearance) / auto trigger symmetry / v2.1 calibration

**메모리 35차 신규**: "Calibrate-from-Real, not Plan-from-Imagination" — Multi-case 알고리즘은 1 사례 calibration → 다른 사례 일반화 검증 의무. 31차(Plan-before-Probe)의 algorithm-layer 대칭. Pilot 19차 100%/100% 직후 18차 0/0 발견 → Sanity Check가 2주 P4 매몰비용 차단.

**잔여 6 갭 deferred** (실제 메모리 발생 시 fix, 35차 원칙):
- 갭 8: SKILL_TO_AGENTS에 fz-codex 등 누락
- 갭 14: "fz" cascade (precision 저하 위험)
- 갭 18: 34차 cascade agents 약화
- 갭 9: Generator "이미 적용됨" 검출
- 갭 13: 17차 system-level 매핑
- 갭 19: Mixed file id 분리

**Files Changed**:
- 변경 5: `fz-code/SKILL.md`, `fz-review/SKILL.md`, `fz-manage/SKILL.md`, `agents/impl-correctness.md`, `agents/review-quality.md`
- 신규 3: `fz-manage/scripts/parse_memory.py`, `fz-manage/scripts/score_relevance.py`, `fz-manage/prompts/generate_suggestion.md`

**참조**:
- 작업 폴더: `~/dev/TVING/fz-cargo-cult-defense/` (Master plan + 7 artifact)
- 트리거: ASD-1260 IAPDebugItems.swift `import TvingCore` redundant
- Release note: `docs/releases/v4.8.0.md`

---

### v4.7.1 (2026-05-04) — Implicit→Explicit Enforce: 11 actual fix UC + 5 verified-clean (3-Phase 통합) [MINOR]

**핵심**: v4.6.0 deep analysis (skills 22 + agents 13 + modules 41 + guides 7 + codex-skills 8) → 24 update candidates → 4-Phase 분할 → STC-1 발화 후 Lead inline fix → v4.7.1 통합 release. **가이드 본문(docs)에 implicit하게 있던 규칙을 explicit reference + verification command로 enforce**.

**3 메타 안전망 실전 검증**: 18차 Scope Inflation + STC-1 + Verification Discipline 모두 작동.

**11 actual fix UC + 5 verified-clean**:

**Phase 1 (Low Risk)**:
- **UC-7** Trimming 비저하 Single Source 명확화 — `prompt-optimization §1 보충 3a`를 single source로 명시, skill-authoring §3는 reference link만 (16줄→8줄, 핵심 3 bullet 보존). plan-deep-planning + fz-plan/SKILL reference 추가
- **UC-10** lesson-intake.md (17줄 fragment) → `memory-guide § Lesson Intake Decision Tree` 흡수. modules 26→25
- **UC-17** experiment-log § "Phase B 시작점 정의 (cross-experiment 통합 표)" 신설 — 4종 표현 단일 source 통합
- **UC-16/18/20 verified-clean** (probe로 already-addressed 확인)

**Phase 2 (Medium Risk)**:
- **UC-9** swift-anti-pattern-preblock § Catch Rate Threshold (>30% 강화 / <5% 비활성화) + experiment-log §5.6 P1/P2/P3 catch_rate 컬럼
- **UC-11** 6 SKILL `## 모듈 참조`에 specific patterns/* 명시 (D6 reference accounting). dependency-graph "거짓 dangling" 정정
- **UC-12** evidence-collection (Producer) + peer-review-gates (Consumer) Module Role 명시 — acyclic 보장, 합병 회피
- **UC-14** fz-review review-counter `[선택]` → `[항상 실행]` (Sycophancy 방어)
- **UC-8/15 verified-clean**

**Phase 3 (High Risk — Codex 2 verify cycle)**:
- **UC-4** harness-engineering §1.2.1 NLAH 6요소 ↔ H1-H6 매핑표 신설 — `[verified: harness L33-L38 + prompt-opt L598-L673]` (C↔H1+H2 / R↔H2+H5 / S↔H5+H6 / A↔H1 / Σ↔H3+H4 / F↔H6 partial)
- **UC-5** agent-team-guide § Same-model Cross-Verify 정책 — Canonical: exclusion + Auxiliary: weighted_rate_pct 별도 보고
- **UC-6 + ISSUE-016** 4 SKILL Lead Spawn Override (`Agent(name="...", model="opus")`) + fz-plan Round 0.5 → Round 1 Sequential Operating Contract (`shutdown_request → 종료 확인 → TeamDelete`). frontmatter mutation 회피 (governance "동시 opus ≤ 2" 보장)
- **UC-13** harness-engineering ## Index (heading-based anchor only, ≤30 budget)

**ISSUE 정밀 처리**:
- **ISSUE-017** sprint-contract amendments 6 위치 — N≥5 → N≥10 (cross-validation 정합) + auto-trigger 표현 제거
- **ISSUE-020** AC-9 portable awk script (per-hunk + same/adjacent line + governance 키워드 narrow)
- **UC-6 cost_blast** experiment-log §5.5 cost_proxy schema deterministic formula — 1주 baseline 모니터링 의무
- **UC-5 Reflection Rate** experiment-log §5.5 schema headline_rate_pct + weighted_rate_pct (legacy rate_pct 호환 유지)

**Cross-validation 정합 (의도 외 변경)**:
- clean-architecture.md OpenAI Codex CLI 참조 추가
- skill-troubleshooting Opus 4.7/GPT-5.5 verified citation

**3 메타 패턴 (F1/F3/F4)**:
- F1 entity 누락 (1차 분석 fz-modernize 누락) — Codex 2차 verify catch
- F3 state 누락 (already-addressed UC) — Phase 2/3 probe-first 효과 검증
- F4 외부 정의 추정 (UC-4 NLAH 매핑) — Codex Phase 3 v1 Critical → v2 verified evidence

**STC-1 정상 작동**: Phase 1 plan v1→v2 (66.7%) → v3 (16.7% regression) → STC-1 발화 → 분할. Phase 3 plan v1 (Critical 1) → v2 (77.8%, Critical 0) → Lead inline fix.

**파일 변경**: 21 modified + 1 deleted (lesson-intake.md). +281 / -57.

**가이드 root cause 매핑**: prompt-optimization §1 보충 3a (UC-7), skill-authoring §3 (UC-10), harness §7 Ablation (UC-9/UC-17), prompt-optimization §3 (UC-11/UC-13), skill-troubleshooting §3.4b (UC-14/UC-5), harness §1.2 + prompt-opt §H1-H6 (UC-4), team-registry L10-12 + agent-team-guide L93/L282 (UC-6).

**상세 release notes**: [docs/releases/v4.7.1.md](docs/releases/v4.7.1.md)

---

### v4.6.0 (2026-04-26) — Cleanup: fz-plan slim + plugin-refs 정정 + pre-commit hook [MINOR]

**핵심**: v4.5.0/v4.5.1 후속 cleanup 3건 통합. (1) fz-plan SKILL 555 → 452줄 (Phase 1 본문 module 분리), (2) plugin-refs 임베딩 테이블 v4.5.0 강화 반영, (3) user-specific 절대 경로 차단 pre-commit hook 신설.

**3 작업**:

A1. **fz-plan SKILL slim**: Phase 1 본문(L280-432, 153줄) → `modules/plan-deep-planning.md` 신설로 이동. SKILL은 Gate 1 + Why(H1) + 절차 요약만 보존 (트리밍 비저하). Progressive Disclosure Level 3 완전 준수.

A3. **plugin-refs.md 임베딩 테이블 정정**:
- `fz-planner` ✅✅✅ → "v4.5.0+ Planning Checklist 3 anchor" 명시
- `fz-fixer` —/부분 → ✅✅ "v4.5.0+ Repair Checklist 3 anchor" 명시
- `fz-challenger` over-engineering 관점 명시 (SwiftUI/RIBs/Concurrency 모두)
- `fz-searcher` 추가 (검색 전용 — 임베딩 불필요)
- 7 row → 8 row

C1. **Pre-commit hook (`.githooks/pre-commit`)**: H1 원칙 (deterministic check) 구현.
- 차단 패턴: `/Users/{user}/`, `~/dev/{user}/` (in-scope: README/CLAUDE/skills/agents/modules/codex-skills/schemas/templates/guides/.claude-plugin)
- 예외: CHANGELOG.md, docs/releases/ (historical reference)
- **staged diff 추가 라인만 검사** (Codex Round 2 finding 반영 — 기존 잔존 정당 reference self-block 차단)
- 등록: `bash scripts/setup-hooks.sh` (clone 후 1회)
- 근거: v4.5.0 release 시 user-specific 절대 경로 노출 incident 재발 방지

**Cross-Validation 3-cycle**:
- Round 1 (Sprint Contract): Codex 10 SC + 6 AC + 2 CUF
- Round 2 (verify v2): needs_revision (Reflection Rate 56%) — 3 unique findings (false positive, RTM swap, stale plan-v1)
- Round 3 (verify v3): needs_revision (Reflection Rate 78%) — 4 unique findings (whole-repo grep, AC-5 self-conflict, README scope, destructive test)
- Implementation: 33차 default 적용 — U2/U3 critical fix만 plan에 반영 후 implementation 진입

**fz Guide 정합 (plan 작성 자체에 적용)**:
- 원칙 4a: Step "원칙+이유" 형태
- 원칙 5: 각 Step BAD/GOOD Few-shot
- 트리밍 비저하: A1이 모범 사례
- H1: C1이 정확한 구현

---

### v4.5.1 (2026-04-26) — docs fix: remove local work dir references [PATCH]

**핵심**: v4.5.0 README/CHANGELOG에서 plugin 사용자에게 의미 없는 local work directory 참조를 제거 — privacy(절대 경로 username 노출) + clean reference 동시 해결.

**변경**:
- `CHANGELOG.md` v4.5.0 entry — local user-specific 절대 경로 + `~/dev/...` 작업 폴더 참조 제거
- `README.md` v4.5 섹션 — local 작업 폴더 참조 제거
- `skills/fz-codex/SKILL.md` — working dir 예시(L136-140) + trust_level config 예시(L184-191)에서 user-specific 절대 경로 → `~/dev/{project}/...` 또는 placeholder로 일반화
- GitHub Release v4.5.0 notes 정정 (post-release edit)

**영향**: 동작 변경 없음. plugin install 사용자가 README에서 broken reference 못 보게 됨.

**메타 교훈**: pre-commit grep으로 `/Users/{user}/`, `~/dev/{user}/` 절대 경로 차단 검증 추가 후보 (CLAUDE.md `## Git Workflow` 또는 `modules/cross-validation.md`).

---

### v4.5.0 (2026-04-26) — Swift/iOS Quality Framework (3-Layer Evidence) [MINOR]

**핵심**: Plan/Code/Review 각 단계에서 Claude + Codex가 **evidence-based clear Swift/iOS coding**을 수행하도록 fz framework에 3-Layer Evidence 정합 통합. 사용자 redirect ("plan/code/review 시 Swift/iOS/구조 품질 안좋음 + 둘 다 근거 기반 명확한 코딩")의 직접 답.

**발견 경로**:
- 8단계 cross-model verify cycle (Claude + Codex GPT-5.5)
- 1차 분석: B+ → 2차 reframe → Sprint Contract (Codex) → Plan v1 → v2 → v2.1 → v2.2 → Round 5 verify
- 5-round 누적 Codex unique 16건 + Claude deep-review unique 5건 → 23차 메타 패턴 ("Cross-model 마지막 안전망") 5번 입증

**P0/P1 — 13 SC 적용 (3-Layer × Meta)**:

Layer 1 PLAN:
- `agents/plan-structure.md` Swift/iOS Domain Awareness 신설 — plugin-refs.md + swift-anti-pattern-preblock.md + Domain Tier 직접 참조
- `skills/fz-plan/SKILL.md` Phase 1.5 (Swift Anti-Pattern Pre-block) 신설 — Gate + module reference / iOS 16 minimum target 명시
- `codex-skills/fz-planner/SKILL.md` SwiftUI Planning Checklist + Swift Concurrency Planning Checklist + Sendable Boundary Planning 3 anchor 강화

Layer 2 CODE:
- `agents/impl-quality.md` tools에 mcp__context7 등록 (dead reference fix)
- `codex-skills/fz-fixer/SKILL.md` SwiftUI Repair Patterns + Concurrency Repair Patterns + Anti-Repair Patterns 3 anchor 추가
- `skills/fz-code/SKILL.md` Phase 0.5 (Swift Pattern Pre-detection) 신설 — Gate + module reference

Layer 3 REVIEW:
- `skills/fz-fix/SKILL.md` supporting [review-arch] → [review-arch, impl-quality, review-quality] + 역방향 트리거 가이드 (3 absence-pattern)
- `skills/fz-review/SKILL.md` iOS 16 minimum target 검증 의무 명시
- `skills/fz-codex/SKILL.md` `/fz-codex drift` 라우팅 버그 수정 (`drift-detector` → `drift`, L518 + L75 doc table)

Meta — Evidence Framework:
- `modules/uncertainty-verification.md` **Swift/iOS Domain Tier** 신설 — 7개 주장 유형 × Heavy/Light × Mandatory Sources. Heavy 정책 **additive (non-overriding)** 명시
- `experiment-log.md` §5.6 **Plugin Trigger Activation** + Load-bearing Test 절차 신설 — 원칙별 ablation schema

**신규 modules (2개)**:
- `modules/swift-anti-pattern-preblock.md` — 3 원칙 (P1 SwiftUI 결정 / P2 Concurrency isolation / P3 패턴 변환 보존) + token + Few-shot
- `modules/swift-pattern-detection.md` — 4 원칙 (D SwiftUI / E Concurrency / F 위험 패턴 / G 패턴 변환) + Phase 1.5 P3 ↔ G mirror

**fz Guide 정합 (deep review 적용)**:
- `prompt-optimization.md` 원칙 4a (원칙+이유 > if-then 테이블) 적용 — 9 if-then inventory → 7 원칙+이유 재작성
- `prompt-optimization.md` 원칙 5 (Few-shot ≥3) 적용 — 각 module BAD/GOOD 1쌍 이상
- `skill-authoring.md` "트리밍 비저하 원칙" 적용 — Gate 1.5/0.5 보존 + 본문 module 분리
- `harness-engineering.md` H1 (가정 검증) 대응 — F9 Load-bearing Test 절차 신설

**Cross-Validation 5-cycle**:
- Round 1 (analysis): Codex unique 3 (drift routing 등)
- Round 2 (verify v2): Codex unique 4 (SC-L2-1 broken 등)
- Round 3 (verify v2.1): Codex unique 2 (markdown escape 등)
- Round 4 (deep review): Codex unique 5 (575줄, SC-L1-1 등) + Claude unique 5 (fz guide deep)
- Round 5 (final verify): Codex unique 2 (untracked, 12→13 mismatch) — **Reflection Rate 90% (strict) / 95% (lenient)**

**Verification**:
- 13 SC PASS (12 verifiable + 1 partial)
- 6 AC PASS
- Plugin validate ✔ Passed
- 23차 메타 패턴 5-round 모두 입증

---

### v4.4.0 (2026-04-26) — Mapping Layer SPOF Defense [MINOR]

**핵심**: peer review 시스템에 **Mapping Layer Single-Point-of-Failure 방어** 도입. 6-Layer LLM 검증이 같은 evidence 매핑 base를 공유하면 매핑 오류는 layer 수와 무관하게 통과한다는 구조적 결함 발견 → atom-level decomposition + fail-closed pre-trigger + cross-stage severity 정렬로 차단.

**발견 경로** (외부 사례 `[미검증: 사용자 제공]`):
- TVING/app-iOS PR #3796 (ASD-1136 ReachabilityManager → NetworkMonitor) peer review에서 6-Layer 검증 (boolean equivalence + Opus + Sonnet + Codex + Lead self + Devil's Advocate) 통과 후 CodeRabbit (rule-based) 단독 발견
- Root cause: `ReachabilityManager.isReachableViaWWAN() = (Reachable AND IsWWAN)` 이중 게이트인데, evidence 매핑이 `→ isReachableViaCellular` simplify되어 reachable atom 누락
- 검증 신뢰도 = `min(매핑 정확성, layer 정확성)` — multiplicative 아님, layer N배 늘려도 매핑이 SPOF면 신뢰도 cap

**P0 — 7 docs (신규 신설 0)**:
- `modules/evidence-collection.md` **a2. Semantic Mapping Ground Truth** 절차 신설 — atom-level mapping table + `[verified: source]` 의무 + `mapping_status` 분류 (verified/lossy/over-mapped/unverified)
- `modules/peer-review-gates.md` **Gate 4.4-A Mapping Fidelity Gate** + **fail-closed Pre-Trigger** — refactoring PR + `semantic-mapping.md` 부재 → Critical 자동 / `mapping_status=lossy` → auto-include
- `modules/uncertainty-verification.md` **Default-Deny mapping claim** 좁은 확장 — `"A는 B와 동일"`, `"X가 Y로 대체됨"` 등 mapping/equivalence claim에 한정 (전역 확대 X)
- `skills/fz-peer-review/SKILL.md` 4 위치 — Gather evidence table + Fact + Mapping Verification Gate + Brief Template + **Task Brief L260에 `evidence/*.md` 명시** (governance 500줄 정확 도달)
- `agents/review-quality.md:60-64` Source Fidelity에 mapping atom 검증 (severity: critical, Gate 4.4-A 정렬)
- `skills/code-auditor/SKILL.md:242-263` Refactoring Completeness 보강 — `lossy_atoms` 회귀 검증
- `codex-skills/fz-challenger/SKILL.md` **Mapping Assumption Challenge** — Codex DA가 lossy/unverified row를 별도 challenge 대상으로

**Layer Diversity 통합 해결**:
- "더 많은 LLM 추가 ≠ Layer Diversity" 통찰 — 같은 매핑 base를 받으면 동일 결론 수렴
- 진짜 Layer Diversity = deterministic source (`git show / Read / grep`) + LLM 판단의 조합 — fz `cross-data` 원칙과 정합

**Cross-Validation 7-cycle 정당성 입증** (본 plan 작성 자체가 prototype):
- Cycle 1: PR review (CodeRabbit 단독 발견) → 출발점
- Cycle 2: Plan v1 (Codex independent가 verify 위반 catch)
- Cycle 3: Plan v2 통합 (Claude self-review가 Q1 self-violation catch)
- Cycle 4: Plan v2 verify (Codex가 v4.1.0 stale 메모리 + `[verified]` 위반 + line citation 잘못 catch — 5건 단독 발견)
- Cycle 5: Plan v3 정정
- Cycle 6: v4.4.0 적용 (모든 Step 실행)
- Cycle 7: v4.4.0 review (Codex가 internal instruction conflict 단독 발견 P2/P3 → 즉시 fix)

**메모리 정식화** (사용자 메모리):
- `feedback_mapping_layer_spof.md` (신규) — 6-Layer 검증 SPOF 패턴 + Defense + How to apply
- `MEMORY.md` index entry 추가 — Verification Discipline 섹션

**메타 학습 — Internal Instruction Conflict는 새 종류 결함**:
- self-review (grep 기반 mechanical check) → Anti-Pattern 0 violations
- Codex review (semantic consistency 분석) → P2 (a2 trigger 정밀도) + P3 (lossy severity 불일치) 단독 발견
- 두 패러다임이 만나는 지점에서 새 결함 분류 발견 — multi-module 변경에서 같은 개념(`lossy mapping`)이 module 간 drift

**Verification**:
- `claude plugin validate .` — ✓ Validation passed
- `wc -l skills/fz-peer-review/SKILL.md` — 500 lines 정확 (governance ≤500 준수)
- 변경량: 10 files (+115/-13 lines)

### v4.3.0 (2026-04-25) — fz GPT/Codex Tier 1+2 완성 [MINOR]

**핵심**: fz GPT/Codex 고도화 프로젝트 사실상 완료. Tier 1 7/7 + Tier 2 1/1. T2-A (β-1 Gemini) 폐기 — cross-provider 비채택. α-2 BLOCKER 해소. 31차/32차/33차 메타 교훈 active defense 정식화.

**Tier 1 7/7** (본 릴리즈에 5건 추가):
- **T1-D fz-fix Codex 통합** (c4c994b, fe2ee8a, cfcaf91): `--codex` 옵션 위임 패턴 + verdict contract (pass/warn/fail) + grep severity 정정
- **T1-B Tracing 자동화** (4519f7a): experiment-log §5.5 schema + Agent Teams Hook (~/.claude/hooks.json + agent-teams.sh)
- **δ-2 Effort Routing** (9150621): Codex 서브커맨드별 effort 매핑 (medium/high/xhigh)
- **T1-E 이론 근거 보강** (058537e): cross-validation.md "Heterogeneity + Blind-spot Complementarity" 프레임 (4 메커니즘 + 학술 근거)
- **η-1 Prompt Independence Gate** (75c051b): TEAM Round 1 sycophancy 절차적 강제 + Gate 1.0

**Tier 2 1/1**:
- **T2-B Sprint Contract** (33d1363): modules/sprint-contract.md + fz-plan Phase 0.7 (Codex가 구현 전 SC 작성)

**T2-A 폐기 + stale 정정** (8f4e7ae):
- β-1 Gemini 통합 비채택 결정 — cross-provider stake 자체 미채택
- guides/harness-engineering.md L663/L1008 stale "3-Model Triad" 참조 정정

**메타 교훈 active defense 정식화**:
- **31차 Plan-before-Probe** (c4c994b): fz-plan Phase 0c + fz-discover Phase 1.5 (Constraint Probe Pre-flight)
- **32차 Probe Coverage Gap**: 3-axes sub-checklist (존재 / 권한·경계 / 결과 contract)
- **33차 Recommendation Default Bias** (5fdc4bf): modules/fz-pipeline-proposal.md 권고 default 정책 (Implementation default + v{N+1} 자동 작성 차단)

**Reflection Rate 측정 시작** (6fd93b7):
- experiment-log §5.5에 3 entries (T1-D verify v1/v2/self-dogfood)
- Sample 3/5 (CP-3 5건+ 누적 필요), Strict 73% / Lenient 86%
- 32차 dogfooding 1차 효과: patch 2건 사전 회피

**Health-Plan v2 통합 + Codex-Utilization v1** (69c78a9, 본 릴리즈에 추가):

*Health-Plan v2 (P0 — 31/32/33 consolidation, behavior-change-first)*:
- `modules/lead-action-default.md` 신규 (23 lines thin reference) — Lead default = action with proportional verification 단일 원칙
- `modules/lesson-intake.md` 신규 (16 lines decision tree) — 미래 lesson family 분기 (same mode merge / new mode separate)
- `modules/cross-validation.md`: Reflection Rate threshold authoritative source (N<10 preliminary / 10≤N<30 provisional / N≥30 stable)
- 5 backlinks (history-preserving, no rewrite): experiment-log, fz-review, feedback-verification, sprint-contract, execution-modes
- Hot-path "default = action" inline edit (3 files): fz-plan Phase 0.5 / fz-review Phase 5.5 / fz-pipeline-proposal

*Codex-Utilization v1 (P0 — friction reduction + T2-B first dogfooding)*:
- `skills/fz-codex/SKILL.md`: Standard Hygiene Wrapper Template (### 6) — 5 hygiene rules + zsh glob 회피 + output readback + heredoc 권고
- `modules/codex-strategy.md`: adversarial high→xhigh 정합화 + Light tier (cross-reference inconsistency 해소)
- `skills/fz-plan/SKILL.md` Phase 0c: Codex Micro-Eval optional assist (조건: 핵심 가정 + [verified] 부재 + primitive 비용 높음)
- `experiment-log.md §5.4`: Codex Unique Findings tracking schema (cross-model 가치 정량 evidence 누적)

*Cross-model verification 결과*:
- Health-plan v2 (Codex GPT-5.5): APPROVED_WITH_NOTES — Codex unique 4건 (Q1/Q2/Q5/Q6 critical, Claude self-review blind spots)
- Codex-utilization v1: APPROVED_WITH_NOTES — Codex unique 1건 (codex-strategy.md adversarial 충돌 line-level factual catch)
- **T2-B Sprint Contract pattern 첫 dogfooding 실증** — Codex pre-commit SC → Lead plan v1 → Codex verify → 1 round 압축 (vs 일반 cross-model 2-3 cycles)
- Reflection Rate N=6 (preliminary, gating 보류 — self-rule applied)

### v4.2.0 (2026-04-24) — Scope Challenge + fz Guide Compliance [MINOR]

**핵심**: 두 축 결합. (A) ASD-1136 Scope Challenge — fz-plan Phase 3에서 Codex verify 이슈를 `scope_disposition`으로 분류, "발견된 것 = 고쳐야 할 것" 자동 번역 차단. Read/Write Scope 분리 + `§X/§Y/§Z` handoff 계약. (B) `/fz-manage` 전체 리뷰로 도출된 5개 가이드 위반(500줄 초과 2건 + 과격 표현 1건 + Few-shot 부족 3건 + YAML 컨벤션 불일치 2건)을 4-Wave로 해소. 21/21 스킬이 skill-authoring.md + prompt-optimization.md + skill-template.md 전 축을 준수.

**Feature Set A — Scope Challenge (ASD-1136)**:
- `modules/scope-challenge.md` 신규 (117줄): Q-S1~S4 체크포인트 + Lead 독립 분류(Generator≠Evaluator) + 5개 disposition 매핑(scope-in/out/invariant-risk/parent-reopen/improvement) + Thought-terminator 감지 + Q-S5 Appendix (Decision Re-open Gate).
- `modules/promotion-ledger.md` 신규 (69줄): P1/P2 eligible session 관측 ledger (학습 승격 금지 원칙, 2회 관측 후 P0).
- `agents/plan-impact.md`: 출력을 Read Scope(넓게 탐색) + Write Scope(binary 판정 최소) + Acceptance Criteria 3-섹션으로 분리. write-in 3조건 명시.
- `agents/plan-structure.md`: plan-final.md §X/§Y/§Z handoff 계약. fz-code는 §Y+§Z, fz-review는 §Y.
- `schemas/codex_review_schema.json` + `codex_peer_review_schema.json`: `schemaVersion` v1.1 required + `issues[].scope_disposition` nullable (v1.0 backward-compat).
- `skills/fz-plan/SKILL.md`: intent-triggers refactor 패턴 추가 + Phase 3 §1b Q-S1~S4 의무화 + Phase 3 §5 Refactoring Mode AskUserQuestion.
- `skills/fz-review/SKILL.md`: Phase 4.5에 §Y Write Scope 정의 시 diff ⊆ §Y 검증 필수.
- `skills/fz-codex/SKILL.md`: response schemaVersion version-aware 파싱 (v1.1이면 disposition read, 미존재/v1.0이면 Lead 수동).

**Feature Set B — fz Guide Compliance Audit**:
- YAML 통일: `arch-critic`/`code-auditor`의 `mcp-servers: []` → `allowed-tools: []` (fz-new-file 선례, 21/21 스킬 일관). 권한 변경 없음 — 실제 도구는 agents/review-arch.md/review-quality.md가 선언.
- 과격 표현 완화: `skills/fz-search/SKILL.md:371` `**CRITICAL**: 코드 수정 절대 금지` → `**Read-Only**: 이 스킬은 코드를 수정하지 않습니다` (Opus 4.7 literal interpretation 대응, Will Not 섹션이 이미 동일 제약).
- 500줄 준수: `skills/fz-review/SKILL.md` 508→487 (Phase 5.5 → `modules/feedback-verification.md` 48줄 신규), `skills/fz/SKILL.md` 515→463 (Phase 4 시각화+AskUserQuestion+적극적 확인 원칙 → `modules/fz-pipeline-proposal.md` 74줄 신규). Gate 4는 SKILL.md에 유지(트리밍 비저하 원칙). 두 신규 모듈 상단에 "Scope of Applicability" 명시.
- Few-shot ≥3쌍: `code-auditor`(Convention/Dead code/레이어 위반), `fz-codex`(review/verify/validate), `fz-review`(리뷰 보고/Anti-Pattern 잔존/Source Fidelity). 본문 실제 시나리오 기반(원본 미존재 추가 금지 원칙).
- `docs/design/lessons-to-module-pipeline.md` 신규 (195줄, 설계만): 17차+18차 교훈 도구화 경로 `/fz-manage reflect-to-module` 서브커맨드 설계. 4개 컴포넌트(Memory Parser + Relevance Scorer + Suggestion Generator + Scope Inflation Detector). **⛔ 구현 승인 전 실행 금지** — 본 설계 자체가 Scope Inflation 위험 내포. 경로 하드코딩 금지(`${PLUGIN_ROOT}`, `${CLAUDE_PROJECT_MEMORY}` 변수화 + CLI 인자).

**Codex Cross-Validation (fz Guide Compliance 검증 중, 3회 수렴)**:
- [P2] `modules/feedback-verification.md:19` Reflection Rate 공식이 canonical schema와 divergence → 스키마 정렬 수정 (fz-code "원본 미존재 추가" 마찰 신호 재발 사례).
- [P2] `docs/design/lessons-to-module-pipeline.md:48-52` 하드코딩 경로 → 변수화 + CLI 인자화 (마켓플레이스 배포 이식성).

두 이슈 모두 Claude 단독 리뷰 blind spot. 18차 교훈 "Codex 3회 한도" 내 수렴.

**변경 파일** (+610/-99):
- Feature Set A: 9 파일 (agents 2 + modules 3 + schemas 2 + skills 3)
- Feature Set B: 9 파일 (skills 6 + modules 2 + docs 1)

**마이그레이션**: 없음 (backward-compatible). Schema v1.1은 v1.0 응답 null 수용. YAML `allowed-tools: []`는 권한 불변.

**Plugin Metadata**:
- `.claude-plugin/plugin.json`: 4.1.0 → 4.2.0
- `.claude-plugin/marketplace.json`: 4.0.0 → 4.2.0 (v4.1.0 릴리즈 시 bump 누락 수정 포함)

---

### v4.1.0 (2026-04-21) — Call-Site Deprecation Audit + Function Responsibility Audit [MINOR]

**핵심**: ASD-1111 회귀 ("함수 이름 ≠ 함수 책임" + "호출 중단 ≠ 정의 제거" 패턴)를 fz 생태계로 반영. plan-impact의 Exhaustive Impact Scan을 `a~f` → `a~g`로 확장하고 review-correctness에 Function Responsibility Audit 절차 추가. v1~v4 needs_revision 반복 후 **18차 반성 (Scope Inflation 방어) 4 규칙** 등록 + v5.3 Codex approved 후 구현.

**신규 검증 절차**:
- `agents/plan-impact.md` §Exhaustive Impact Scan 항목 g "Call-Site Deprecation Audit" — 함수 호출자 수 변화 감지 + 책임 분해. severity: Critical `responsibility_gap` 플래그.
- `agents/review-correctness.md` §2 Logic Correctness "Function Responsibility Audit" bullet — Lead가 base ref resolve 후 artifact 전달. agent는 Bash 금지 (guides/agent-team-guide.md §1 준수). severity: Critical `missing_responsibility` 플래그. ⛔ `HEAD^` 하드코딩 금지 (merge-base 우선).
- `skills/fz-plan/SKILL.md` `Impact Scan (a~f)` → `(a~g)` 2곳 일관성 업데이트.

**18차 반성 적용 (Scope Inflation 방어)**:
- 규칙 1 (Complexity Drift): v4 complexity 19 → v5 7 축소
- 규칙 2 (Self-Assessment Blindness): `[verified: 리터럴 명령어 출력]` 태그 의무
- 규칙 3 (Additive-Only 금지): v5에서 v4의 13개 Step DEFERRED
- 규칙 4 (Codex 3회 한도): 4회째 needs_revision 후 사용자 에스컬레이션

**DEFERRED (v5 plan 명시)**:
Helper-A Baseline Resolution 모듈, Helper-B Codex Degraded Gate, Plan-to-Source Gate 4.5.5, Edge Case Enforcement 5 cases, `/fz-manage propagate-lessons`, Trigger Precedence, Origin-Behavior Fallacy, Atomic Rewrite, SKILL.md Module Split — 별도 ASD 티켓 처리.

**검증 이력**: v1~v4 Codex needs_revision (Major 4→5→3→4) → v5 Major 2 → v5.1 Major 1 → v5.2 Major 0 → v5.3 approved (Q1-Q8 전체 pass, Issues 0) → 구현 Codex check --deep (Major 0, P2 2건 DEFERRED 범위) → validate approved (Reflection Rate 100%).

**변경 파일** (+24/-3):
- `agents/plan-impact.md` (+13/-1)
- `agents/review-correctness.md` (+10)
- `skills/fz-plan/SKILL.md` (+2/-2)

**마이그레이션**: 없음 (backward-compatible).

**관련 분석 산출물** (외부 TVING/ASD-1111 폴더):
- `review/regression-root-cause-analysis.md` — 7 시스템 패턴 (git 실측 교정판)
- `analysis/fz-ecosystem-gap-analysis.md` — Gap 매트릭스
- `plan/fz-ecosystem-improvement-plan-v{1-5}.md` + `verify-result*.md` — 8회 Codex verify 이력

---

### v4.0.0 (2026-04-21) — V.D. 4-way Chain 아키텍처 + 생태계 정합성 [MAJOR]

**핵심**: v3.11.0의 Verification Discipline 초안을 **4-way Chain 아키텍처**로 구조화 + 생태계 전체 정합성 감사로 22 Gap 해소. 단순 기능 추가가 아닌 **생태계 아키텍처 전환**으로 메이저 bump.

**Breaking Changes**:
- **레이어 경계 정정**: `modules/team-core.md` + `guides/prompt-optimization.md` H4의 "Brain = Lead / Hands = Primary/Supporting" 1:1 매핑 테이블 **제거**. Brain/Hands는 infrastructure layer (Anthropic), Lead/Teammate는 application layer (fz) — 혼용 금지 경고 박스 추가.
- **agents/ 12개 파일 구조 변경**: 모든 에이전트 하단에 `## Verification` 섹션 자동 추가.
- **templates/ 자동 상속**: `agent-template.md` + `skill-template.md`에 `## Verification` 섹션 + skill-template의 `## If TeamCreate is used` 조건부 체크리스트. 신규 에이전트/스킬 생성 시 VD 규약 자동 상속 (재발 방지).
- **9 skills Prerequisites 필수**: TeamCreate 사용 skills (fz, fz-plan, fz-code, fz-discover, fz-fix, fz-review, fz-peer-review, fz-search, fz-pr-digest) 모두 `## Prerequisites` 섹션 필수 — `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 전제조건 명시.

**V.D. 4-way Chain 아키텍처**:
- ① 기본 fail-closed: `uncertainty-verification.md` → fz-plan / fz-code (기존 유지)
- ② 보조 micro-eval: `fz-codex micro-eval` → needs_verification → Default-Deny 차단 (의미론적 결합 신설)
- ③ TEAM 주입: `system-reminders.md` → `team-core.md` → fz/SKILL.md Task Brief → agents (templates/ 상속)
- ④ 운영 피드백: Phase 4.5 측정 → `experiment-log.md §5.4` canonical sink → B1/B2 판정

**생태계 정합성 감사 (22 Gap 해소)**:
- Critical 5: G1(레이어 경계) / G2a(agents VD 주입 경로) / G2b(오케스트레이터 Task Brief) / G18(team-core↔system-reminders) / G22(템플릿 상속)
- High 7: G3(CLAUDE.md 3 섹션) / G4(plan-tradeoff ARCHIVED) / G5-G8(가이드 4.6/4.7 병기) / G21(fz-discover/peer-review VD 모듈)
- Medium 7: G9(MAR 교차 참조) / G10(NLAH 위치) / G11(tokenizer Deferred) / G16(micro-eval 트리거) / G19(canonical sink) / G20(needs_verification 결합) / G23(fz-codex 500줄 이하)
- Low 3: G12-G13 / G24(Follow-up Re-audit Gate + `${CLAUDE_PROJECT_DIR}` 경로)

**신규 모듈 섹션**:
- `modules/cross-validation.md` "Follow-up Re-audit Gate" (Phase B1/B2 활성)
- `modules/cross-validation.md` "micro-eval 호출 트리거 (공통)" (Claim-Type 라우팅 확장)
- `modules/memory-guide.md` "Claude Memory tool과의 관계" (fz L1 vs Anthropic client-side)
- `CLAUDE.md` (root) "Verification Discipline" / "Opus 4.7 Adaptation" / "Agent Teams Environment Flag" 3섹션

**검증 방법 강화**:
- v3 패치에서 "키워드 grep" → "구조적 검증 (헤더 + bullet exact-match + 인접성)"로 전환
- `^## Verification` 헤더 + bullet 3개 exact-match
- TeamCreate 라인 ±20줄 내 VD Brief 매치
- 팀 생성 절차 ±10줄 내 system-reminders + T6 + T7 동시 매치

**audit 방법론**:
- 3-Model 수렴: Claude Discover(4명) + Codex verify ×4 + Claude meta-analysis → 9 검증 라운드
- memory-curator 3-E "Claude blind spot" 실증: G22(템플릿) + fz-search/fz-pr-digest env flag drift + 카운트 regression 모두 Codex가 발견
- Plan v1 → v2 → v3 → 구현 → Codex final-v2 approved (0/0/0)

**경로/버전**:
- plugin.json: 3.10.0 → 4.0.0 (v3.11 변경도 plugin.json 미반영이었음 — 함께 통합)
- marketplace.json: 3.10.0 → 4.0.0

**검증 상태**: Codex final v2 **approved** (Critical 0 / Major 0 / Minor 0). audit 산출물은 `TVING/NOTASK-20260421-fz-audit/` 하위 16개 파일 보관.

### v3.11.0 (2026-04-21) — Opus 4.7 Adaptation + Verification Discipline

**핵심**: Claude Opus 4.7 (2026-04-16 GA) 출시에 따른 가이드 전면 업데이트. 2차 Codex cross-validation 기반 팩트 오류 정정 + 논문 근거 보강 + 공식 자료 정합성 확보.

**검증 상태**: Phase 1/2 Codex **approved**. Phase 3 (N1/N3/CHANGELOG) Codex 3라운드 iterate 후 approved.

**배경 research**:
- 1차 research: `claudedocs/research_fz_guide_updates_2026-04-21.md` (504줄)
- 2차 refined research: `claudedocs/research_fz_guide_refined_2026-04-21.md` (593줄) — 1차의 hallucination 3건 catch
- 통합 Gap Matrix: `claudedocs/fz_guide_update_gap_matrix_2026-04-21.md`

**Phase 1 — Critical 팩트 정정** (2건 실제 수정, 3건 hallucination 판명)
- `modules/cross-validation.md` L85: X-MAS(arxiv 2505.16997) 주장 완화 — 논문 abstract 재확인 결과 "2-model isolation" 실험 부재, "heterogeneous > homogeneous, MATH +8.4%, AIME +47%"로 정정
- `modules/context-artifacts.md` L228-230: Opus 4.6 → **Opus 4.7 (1M context, 2026-04-16 GA)** + tokenizer 1.00-1.35x 변경 주의 + Korean [미검증] 태그

**Phase 2 — Opus 4.7 하드코딩 정리 + 논문 근거 보강** (13 edits)
- `guides/harness-engineering.md`: 7곳 Opus 4.7 반영 (모델 세대 테이블 4-column 확장, tokenizer 경고, shallow long-context 주의)
- `guides/prompt-optimization.md` L276-278: Opus 4.7 "more literal instruction following" 경고 추가
- `guides/agent-team-guide.md` L406-411: 공식 사양 명시 (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, hard limit 명시 없음/3-5 권장, TeammateIdle/TaskCreated/TaskCompleted hooks)
- `modules/system-reminders.md`: Drift No More (arxiv 2510.07777) reminder injection 효과 근거 추가
- `modules/cross-validation.md`: VeriGuard (arxiv 2510.05156) dual-stage verification 근거 추가
- `skills/fz-review/SKILL.md`: MAR — Multi-Agent Reflexion (arxiv 2512.20845) 3중 검증 이론 근거
- `modules/memory-policy.md`: Intelligence Degradation (arxiv 2601.15300) + Context Length Hurts (arxiv 2510.05381) "1M = safety net not strategy" 근거

**Phase 3 — Infrastructure 구분 + Memory tool 관계** (2 additions)
- `guides/harness-engineering.md §1.3` 신규: Anthropic Scaling Managed Agents (2026-04-08) Brain/Hands 인프라 레이어와 fz Lead/Teammate 애플리케이션 레이어 구분 테이블
- `modules/memory-policy.md`: Opus 4.7 공식 Memory tool (file-system-based)과 fz 자체 L1/L2/L3의 중복 가능성 + 미래 전환 판단 기준

**Deferred**
- M5 (NLAH 13 agent list 갱신): Open Question — 논문 전문 확인 후 별도 업데이트
- N2 (Task Budgets beta): Messages API only, Codex CLI 미지원으로 fz 적용 불가

**Verification Discipline 적용 사례 (메타 교훈)**
- 1차 research의 hallucination 3건(`CLAUDE.md 40% 채택률`, `fz에 'ICLR 2025 Inside the Scaffold' 오인용 존재`, `Agent Skills OpenAI/MS 채택`)을 2차 research와 실측 grep으로 모두 catch → 잘못된 수정 방지
- Gap Matrix의 "Critical 4건" 중 3건이 fz 가이드에 존재하지 않는 이슈로 판명 → 실제 수정은 C3 + H1 2건만
- `[verified: source]` / `[미검증: 이유]` 태그 원칙 전파 — 공식 부재 부분 명시적 표시

**근거 논문 인용 재정렬**
- X-MAS (2505.16997) — 이종 조합 근거, abstract 기반 보수적 해석
- Drift No More (2510.07777) — reminder 효과
- MAR (2512.20845) — 역할 분리 이론
- VeriGuard (2510.05156) — dual-stage verification
- Intelligence Degradation (2601.15300) + Context Length Hurts (2510.05381) — 1M context 원칙
- NLAH (2603.25723) — 하네스 formalism (인용 유지, 13 agent list deferred)

---

### v3.10.0 (2026-04-15) — Scope Minimality

**핵심**: 코드 패턴 변환 시 기계적 1:1 래핑을 방지하는 "의미 판단" 체크포인트를 파이프라인 3단계(Plan→Code→Review)에 추가.
근거: PR #3694 (ASD-1002)에서 PromiseKit `.done` → `async/await` 전환 시, 클로저 전체를 `MainActor.run`으로 기계적 래핑하여 순수 연산까지 main thread에 묶는 실수 발생. hyundongyang 코멘트로 발견.

**Zero-Exception Thread Rule 범위 한정** (`modules/code-transform-validation.md`)
- 기존: "원본 main queue → After @MainActor 무조건" (기계적 전체 래핑 정당화)
- 변경: @MainActor **보장**은 필수이나 블록 **범위**는 실제로 main thread가 필요한 문장에만 한정
- Scope Minimality 단서 신규 추가 (Zero-Exception Rule 섹션 내)

**BEC step 3.5: Wrapper Scope Minimality** (`modules/code-transform-validation.md`)
- Behavioral Equivalence Check에 래퍼 범위 최소성 검증 단계 추가
- "이 문장이 해당 컨텍스트를 필요로 하는가?" 개별 판단 의무화
- 패턴 변환 시 Swift Concurrency 플러그인 필수 참조 지시 (BEC step 6)

**마찰 신호: "래퍼 범위 과잉"** (`skills/fz-code/SKILL.md`, `modules/code-transform-validation.md`)
- fz-code 25번째 마찰 패턴: @MainActor/do-catch/Task 블록 내 불필요 문장 포함 감지
- code-transform-validation 5번째 마찰 신호: 동일 패턴
- "스레드 컨텍스트 불일치"(too little)와 보완 쌍(too much)

**fz-review 4-K: wrapper_overscope** (`skills/fz-review/SKILL.md`)
- Transformation Equivalence 검증에 Wrapper Scope Minimality 체크 추가 (severity: Major)
- Gate 4 체크리스트 + Harness Metrics 테이블 확장

**plugin-refs.md actors 확장** (`modules/plugin-refs.md`)
- 구현 시: actors 행에 "패턴 변환 시 래퍼 범위 최소성 판단" 추가
- 리뷰 시: "@MainActor 블록 범위가 최소인가?" 체크 추가

**버그 수정**
- `code-transform-validation.md`: "Review(4-J)" → "Review(4-K)" 오표기 수정
- `plugin.json`: 3.8.0 → 3.10.0 (v3.9.0 릴리즈 시 bump 누락 수정)
- `marketplace.json`: 3.4.0 → 3.10.0 (동일)

**ablation 관측**
- 전체 새 항목에 `[ablation: scope-min-v1]` 태그 (4개 파일 8곳)
- 3회 패턴 변환 작업 후 이슈 발견 >= 1이면 Load-bearing 승격, 0이면 제거 검토

변경: 4개 파일, +14줄 -3줄. TEAM --deep (4 agents, 2 rounds) + 3중 리뷰 (3 agents) 검증.

---

### v3.9.0 (2026-04-14) — Harness Engineering Enhancement

**핵심**: SOLO 모드에서 Generator≠Evaluator 분리 불가능한 구조적 Gap 해소 + PR 코멘트 학습 파이프라인 설계.
근거: harness-engineering.md 작성 과정에서 발견한 NLAH Gap 5건 중 상위 2건.

---

### v3.8.0 (2026-04-12) — Uncertainty-Aware Harness

**핵심**: LLM이 모르는 것을 인정하고, 검증 도구로 확인하고, 실패에서 학습하는 하네스 시스템.
근거: PR-D1 리뷰에서 Codex(GPT-5.4)가 Claude blind spot 2건 발견. Codex Adversarial 6건 반영.

**신규 모듈: `modules/uncertainty-verification.md`**
- Default-Deny: [verified: source] 태그 없는 기술적 주장은 자동 unverified
- Verification Cost Tiers: Heavy(스레드/API계약) / Light(일반) / Skip(코드 확인)
- Evidence Source Priority: 코드 > 테스트 > 공식 문서 > 훈련 데이터
- Memory Feedback Loop: 검증 실패 → 교훈 기록 → 규칙 승격
- Pilot-first: v3.8은 Transformation Spec 경로만. 효과 확인 후 확장

**모듈 개선: `modules/code-transform-validation.md`**
- Zero-Exception Thread Rule: 원본 main queue → After @MainActor 무조건 (기본값)
- Transformation Spec v3.8: spec-version 필드 + 7번째 항목(요청 파라미터) + [verified] 태그
- 마찰 신호 4번째: 파라미터 키 불일치 (omit ≠ explicit default)
- BEC/4-K fail-closed: [verified] 없는 주장 → 구현 전 검증 강제

**스킬 개선 (4개)**
- fz-plan: Default-Deny [verified] 의무화 + Gate 1 체크리스트 3항목 (+7줄)
- fz-code: BEC fail-closed + 파라미터 키 마찰 신호 (+5줄)
- fz-review: 4-K enforcement + Gate 4 체크리스트 + Harness Metrics 보고 형식 (+22줄)
- fz-fix: uncertainty-verification 모듈 참조 (+1줄)

**Codex 스킬 개선 (2개)**
- fz-reviewer: Zero-Exception + Default-Deny + Parameter Presence (+9줄)
- fz-architect: 동일 규칙 요약 (+3줄)

**모듈 개선: `modules/cross-validation.md`**
- spec-verify: Codex가 Spec 기술적 정확성 검증 (TEAM 필수)
- confident-error: cross-model 불일치 → 교훈 기록
- default-deny enforcement: [verified] 없으면 fail-closed

**Harness Metrics (신규)**
- fz-review 완료 보고에 Gate별 이슈 수 기록 형식 추가
- 분기별 ablation 분석의 전제 데이터 수집 인프라

---

### v3.7.0 (2026-04-12) — Code Transformation Validation

**신규 모듈: `modules/code-transform-validation.md`**
- 코드 변환(Before→After) 동작 동등성 + 구조 품질 검증 공유 모듈
- Transformation Spec 형식 + 검증 체크리스트 + Swift 변환 규칙 + Context7 활용
- 3중 검증: Plan(Spec 작성) → Code(BEC 대조) → Review(4-K 준수)
- 트리거: 비동기/네트워크/UI 패턴 변환 시에만 활성 (단순 치환 제외)

**스킬 개선 (6개)**
- fz-plan: Transformation Spec 작성 절차 + Gate 1 체크리스트 (+10줄)
- fz-code: 마찰 신호 3개 + Behavioral Equivalence Check (+11줄)
- fz-review: 검증 4-K Transformation Equivalence (+15줄)
- fz-fix: 패턴 변환 감지 + 모듈 참조 (+5줄)
- fz-peer-review: Gather 4.5 패턴 변환 감지 (+8줄)
- fz-codex reviewer/architect: Swift 변환 규칙 임베딩 (+17줄)

**모듈 개선**: cross-validation.md 게이트 테이블 transformation 3행 추가

근거: PR-D1 플랜 7개 이슈 미탐지 사후 분석 (반성 11차)

### v3.6.0 (2026-04-11) — iOS/Swift Reverse Diagnostic Triggers

**역방향 감지 트리거 (plugin-refs.md)**
- 기존: 패턴 존재(e.g. `@MainActor`)만 트리거 → 패턴 부재 시 플러그인 비활성
- 신규: **패턴 부재** 시에도 안전성 관점 활성화 (Swift Concurrency 플러그인 활성 여부와 무관)
- Level 1 (구문): 싱글톤+가변상태 동기화 누락, 싱글톤 deinit dead code
- Level 2 (의미론): 콜백 스레드 불일치, @Published background 쓰기, 비동기 기본값 소비자 영향

**Concurrency Safety Audit — 검증 4-J (modules/safety-audit.md)**
- fz-review Phase 5에 항상 실행되는 안전성 감사 단계 추가
- 싱글톤 가변 상태 동기화 (L1 필수) + 콜백 스레드/@Published/기본값/API retention (L2 권장)
- Progressive Disclosure Level 3: 별도 모듈로 분리 (fz-review 500줄 한도 대응)

**에이전트 iOS/Swift 시맨틱 보강**
- review-quality: Concurrency Safety 활성 조건에 "역방향 트리거" 추가 + Library Semantics 4항목
- review-arch: State Lifecycle에 싱글톤 스레드 접근성 + Library Semantics 2항목
- impl-quality: Memory Safety에 싱글톤 가변 상태 동기화 누락 감지

**fz-code Implementation Friction 3행 추가**
- 동기화 부재 (singleton + var + 보호 없음)
- 싱글톤 deinit (static let shared + deinit)
- 기본값 소비자 영향 (비동기 property + 기본값)

**System Reminders T5 추가**
- 싱글톤 가변 상태 변경 감지 시 자동 리마인더 (동기화/deinit/기본값 확인)

**배경**: PR #3665 (NetworkMonitor) 리뷰에서 팀원이 발견한 4가지 이슈를 fz가 하나도 선제 감지 못함.
근본 원인: 트리거가 패턴 존재만 감지 → 가장 위험한 코드(보호 필요하나 없는 코드)가 가장 적은 검토를 받는 구조적 맹점.
82행 추가로 구조적 맹점 해소 (8파일: 7수정 + safety-audit.md 신규).

---

### v3.2.2 (2026-04-05) — Agent Role Optimization

**에이전트 책임 재분배 (Codex verified)**
- review-arch: 7→5 관점 축소 (Dead Code + Source Fidelity → review-quality 이관)
- review-arch: Context-Specific Behavior 테이블 제거 (단일 책임 원칙)
- review-quality: 리팩토링 완성도 항목 흡수, 7개 관점 명확화
- plan-structure: 영향 범위 분석을 plan-impact에 명시적 위임 (SendMessage)

**팀 구성 강화**
- fz-review: review-correctness 추가 (Phase 4.5 RTM 검증 한정)
- fz-fix: review-arch 조건부 참여 (복잡도 3+)
- memory-curator: "선택적" → "기본 포함, lightweight recall" (cross-validation.md 일치)

**동기화**
- team-registry, pipelines.md, patterns/live-review.md 팀 구성 반영
- fz-gemini 참조 제거 (README)
- plan-tradeoff.md → .archived

---

### v3.2.1 (2026-04-05) — Dependency Decoupling

**로컬 경로/iOS 의존성 제거 (7-Step, 27파일)**
- Step 1: fz-excalidraw 절대 경로(`/Users/jaewoongyun`) → `os.path.expanduser("~")` 동적 경로
- Step 2: Codex 네이티브 스킬 repo 포함 (`codex-skills/` 8개) + `scripts/setup-codex-skills.sh` + `get_codex_skill()` Tier 2b 폴백
- Step 3: 9개 에이전트 iOS 도메인 지식 → CLAUDE.md 키워드 기반 조건부 적용 + XcodeBuildMCP → "빌드 MCP 도구" 일반화
- Step 4: `modules/build.md` → CLAUDE.md `## Build` 동적 추출 (xcodebuild/npm/yarn/cargo/gradle 매칭)
- Step 5: fz-pr 팀 스킬 경로 → CLAUDE.md `## Git Workflow` 동적 참조
- Step 6: `modules/plugin-refs.md` → 프로젝트 언어/프레임워크 기반 조건부 적용
- Step 7: `templates/CLAUDE.md.template` — 새 사용자용 프로젝트 설정 템플릿

**리뷰에서 발견된 기존 이슈 수정**
- fz-review `## Guidelines` dangling reference → `## Code Conventions`
- fz-code/fz-fix iOS 16 인라인 하드코딩 → CLAUDE.md `## Plugins` 동적 참조
- `agent-team-guide.md` XcodeBuildMCP → 일반화
- README 아키텍처 트리 + 카운트 최신화

**제약**: 로컬 동작 100% 동일. CLAUDE.md에 iOS/RIBs 키워드 존재 시 조건부 활성화.

---

### v3.2 (2026-04-05) — Lead Implication Gate + Harness Engineering + System Reminders

**Lead Implication Gate** (analysis → plan → code → review 전체 반영)
- modules/lead-reasoning.md 신규 (165줄) — 추론 원칙 + 카테고리 분류 + 자문 체크리스트 + Implication Register
- cross-validation.md에 Implication Scan 게이트 + origin-equivalence 게이트 추가
- fz-code 마찰 감지에 "구조적 잔존물" + "관찰 보고 의무" 항목 추가
- fz-review 검증 4-I (Implication Coverage) 추가
- fz-plan Implication Register 출력 + Anti-Pattern 가이드 강화
- fz-codex Q8 함의 커버리지 질문 추가
- fz-fix revert 감지 → origin-equivalence 게이트 라우팅
- Codex 네이티브 스킬 4개 Implication taxonomy 통일

**Harness Engineering Guide** (1035줄)
- guides/harness-engineering.md 신규 — Anthropic 공식 2편 + NLAH 논문 + OpenDev 논문 + 오픈소스 구현체 기반
- 5대 기둥, 4가지 아키텍처 패턴, 6가지 설계 원칙, Anti-Patterns, 측정 지표, fz 매핑
- 11개 고품질 참고 문헌 (공식/학술만)

**Harness 기반 fz 고도화**
- modules/system-reminders.md 신규 — Instruction fade-out 대응 (트리거 기반 + 30턴 backstop)
- MEMORY.md Ablation 프로세스 — 분기별 Gate 기여도 측정
- CLAUDE.md Tool Usage 가이드라인 — Grep/Read/Bash 최적화
- Evaluator Tuning — 피드백 검증 프로토콜 4단계 (과적합 방지)
- review-arch/review-quality에 Tuning History 섹션

**피드백 신뢰도 검증 (과적합 방지)**
- 팀원 리뷰 코멘트 4단계 분류: project-rule / valid-suggestion / preference / needs-review
- preference(취향)는 에이전트 학습 절대 금지

**메모리 정리**
- MEMORY.md 205줄 → 114줄 (44% 감소). 이미 반영된 반성/교훈 제거, 인덱스만 유지.

---

### v3.1 (2026-04-02) — RTM + Teams v2 + Scope Expansion + L3 에이전트

**RTM (Requirements Traceability Matrix)**
- modules/rtm.md 신규 — plan이 Req-ID 생성 → code가 implemented 갱신 → review가 기계적 확인
- 산문 매칭 → ID 기반 추적으로 요구사항 누락 방어

**L3 네이티브 에이전트 통합**
- modules/native-agents.md 신규 — silent-failure-hunter + type-design-analyzer를 review Phase 5에 background 스폰
- L1(fz커스텀) > L3(네이티브) 원칙: L3는 보강만, TeamCreate 참여 금지

**Teams v2 — 팀 내부 통신 강화**
- L3→L1 피드백: L3 발견을 Lead가 Primary에 SendMessage → iOS 특화 재분석
- Supporting 활성화: impl-quality 매 Step 피드백, review-correctness 50%+마지막 RTM 체크
- Handoff Brief: plan→code 팀 전환 시 Key Decisions+Risks+Watch Points 구조화 전달
- plan-edge-case↔plan-impact CC: Supporting 간 교차로 연쇄 발견
- 5명+ 토폴로지: team-core.md에 Star-enhanced+CC 행 추가

**Scope Expansion — discover 시야 제한 4겹 방어**
- plan-impact: 변경 대상의 프로토콜/부모/같은 모듈까지 확장 탐색
- fz-plan Phase 0b: discover 로드 후 상위 수준 get_symbols_overview
- fz-code Phase 1.6: plan 영향 범위 < discover 범위이면 "시야 축소 위험" 마찰 신호
- cross-validation: review 시작 전 plan⊇discover 범위 확인

**네이티브 기능 강화**
- BATCH: merge 후 통합 빌드 gate 필수 + 부적합 조건 강화 (RIB/모듈 생성 금지)
- SIMPLIFY: 필수 gate 3가지 + 선택 suggestion 2가지 명확 분리 + 설계 의도 보존
- SC 조건 기반 자동 트리거: 빌드2실패→sc:troubleshoot, 3+Step 중간→sc:reflect, 복잡도4+→sc:estimate
- sc:save 모든 파이프라인 종료 시 (이전: 코드 변경만)

**정합성 개선**
- plan-edge-case: fz-plan YAML+registry+pipelines+pattern 4-way 동기화
- memory-curator: 모든 TEAM 참여 (이전: --deep/복잡도4+)
- plan-tradeoff: ARCHIVED (discover가 대체)
- 변경 파일 22개, RTM 19/19 verified, 리뷰 이슈 0건

### v3.0 (2026-03-30) — 3-Model Triad + 6-Agent Team + Landscape Discover

**3-Model Triad Architecture (연구 기반: X-MAS 47% 향상, ICLR 2025)**
- Claude(생산) + GPT/Codex(검증) + Gemini(Devil's Advocate) 3모델 체계
- fz-gemini 스킬 신규 생성 — Gemini CLI 전용 (review, verify, challenge)
- fz-codex에 --consensus 옵션 — 3모델 합의 모드
- cross-validation.md: Selective Consensus (불일치 시에만 Gemini 호출)
- team-core.md: 2-Tier → 3-Tier 모델 전략 (opus/sonnet/external)
- consensus-verify 파이프라인 신규 (#19)

**6-Agent Plan Team**
- fz-plan: 4 Claude + 1 GPT + 1 Gemini = 6개 차별화된 렌즈
- plan-impact 에이전트를 Impact Scanner로 강화 (Exhaustive Impact Scan 전담)
- Parallel Analysis + Cross-Feedback 통신 패턴
- 각 에이전트가 다른 질문을 던짐 (같은 질문 금지)

**Landscape Discover (discover 패러다임 전환)**
- "제약 발견 + 수렴" → "풍경 탐색 + 경로 매핑"
- provides: constraint-matrix → landscape-map + trade-off-table + open-questions
- 조건 불변성 구분: 🔒 hard constraint vs 🔓 soft preference
- discover는 결론을 내리지 않음 — plan이 경로를 선택
- adversarial 패턴: "부수기" → "비용/리스크 밝히기"

**Native Commands 활성화**
- /simplify: 선택 → 조건부 필수 (새 함수 3개+, 100줄+, 3회 빌드 실패)
- /batch: 독립 Step 3개+ 감지 시 자동 제안
- LOOP: 스킬별 에스컬레이션 래더 구체화

**Skill Refinement**
- fz-fix: 4-Phase 디버깅 (Reproduce → Isolate → Root-Cause → Verify Fix)
- fz-code: Step 완료 조건 3개 명시 (빌드 + conformance + caller 확인)
- Hooks 기반 물리적 강제: git commit 차단, platformFilter 자동 검사

**De-overfit**
- 반성 마커 제거 (규칙 유지, 출처만 삭제)
- Gate 체크리스트 경량화 (공통/조건부 분리)

### v2.5 (2026-03-20) — skill-creator Integration + Description Overhaul + Clean Architecture

**skill-creator 통합 (Runtime Trigger Eval + Description Optimization)**
- fz-skill에 `optimize` 서브커맨드 추가 — skill-creator `run_loop.py` 활용, train/test split 기반 description 자동 최적화
- fz-skill eval에 `Runtime Trigger Eval` phase 추가 — `run_eval.py`로 실제 `claude -p` 호출하여 트리거율 실측
- fz-skill create에 Phase 5 (Description Optimization 제안) 추가
- fz-manage benchmark에 `--with-trigger` 옵션 — 하위 3개 스킬 Quick Trigger Eval
- fz-manage check에 #11 skill-creator 설치 확인 항목 추가
- 신규 파일: `skills/fz-skill/references/skill-creator-integration.md` (L3 연동 가이드 + 실증 결과)
- 신규 파이프라인: #18 `skill-optimize` (pipelines.md)
- intent-registry.md에 fz-skill/fz-manage 자연어 트리거 보강

**실증 테스트 결과 및 교훈**
- 13개 스킬 전체 Runtime Trigger Eval 실행: 35/81 (43%)
- 핵심 발견: `claude -p` 자동 트리거는 슬래시 커맨드 스킬에 제한적 — should-NOT-trigger 100% 정확, should-trigger 0%
- description을 pushy 패턴으로 변경해도 트리거율 변화 없음 (43%→44%)
- 근본 원인: Claude가 간단한 요청을 스킬 참조 없이 직접 처리하는 경향
- 교훈 메모리 저장: `feedback_skill_creator_trigger_eval.md`

**전체 스킬 Description 고도화 (18/18)**
- skill-creator best practice 패턴 전면 적용:
  - Third-person: "This skill should be used when..."
  - Pushy triggers: "Make sure to use this skill whenever the user says: ..."
  - Keyword coverage: "Covers: ..." (Korean + English)
  - Boundary: "Do NOT use for..."
- 누락 5개 스킬 추가 적용: fz-codex, fz-new-file, fz-pr-digest, fz-pr, fz-recording

**500줄 제한 준수**
- fz-review: 513 → 492줄 (redundant separators 제거)
- fz-peer-review: 503 → 497줄 (redundant separators 제거)

**Clean Architecture 가이드 (Uncle Bob 페르소나)**
- 신규 파일: `guides/clean-architecture.md`
- 내용: Dependency Rule, SOLID 5원칙, 4 Layers 정의, Boundary Crossing 규칙, Architecture Smells, Uncle Bob's Decision Rules, Pragmatic 균형
- review-arch 에이전트: Architecture Decision에 Dependency Rule + SOLID 위반 감지 연결
- impl-quality 에이전트: Architecture Consistency에 DIP 위반 감지 연결
- fz-plan 스킬: 영향 분석 Step 4 "Clean Architecture 원칙 확인" 추가

**생태계 건강 체크**
- 전체 13개 항목 건강 체크 실행: 12.5/13 PASSING
- YAML 필수 필드 100%, provides/needs 체인 완전, 깨진 참조 0개
- 에이전트 14개 전부 유효, 모듈 17개 전부 존재

### v2.4 (2026-03-18) — Remove GitButler + Git Workflow Simplification

**GitButler 제거**
- GitButler 스킬 삭제 (`skills/gitbutler/` — SKILL.md + 3 reference files, -1,551줄)
- README.md 스킬 목록, CLI 도구, Infrastructure 다이어그램에서 제거 (22→21 스킬)
- 이유: Claude Code와 함께 사용 시 이점 없음 — 단일 working directory 공유로 Agent 병렬 작업 시 상호 오염 발생

**Git 워크플로우 전환**
- GitButler CLI(`but`) → 표준 `git` 명령으로 전환
- 병렬 브랜치 작업: `git worktree`로 독립 디렉토리 생성 권장
- 세션 시작: `but pull` → `git pull upstream develop`

### v2.3 (2026-03-15) — 1M Context Optimization + Ecosystem Health Fix

**1M Context Infrastructure (Opus 4.6 1M)**
- Artifact Token Budget 신설 — 100K cap + eviction 우선순위 (context-artifacts.md)
- ASD 임계값 hybrid: `6+ step 또는 context-heavy` (기존 4+)
- Essential Context 500자→3,000자 (memory-policy.md, fz/SKILL.md)
- Proactive Module Loading — /fz Phase 0에서 핵심 모듈 선로드
- Compact 경고 6+→12+ step, 4-tier 파이프라인 전략
- prompt-optimization.md: 200K 하드코딩 → 상대 서술

**Ecosystem Health Check Fix (86→95점)**
- fz-plan: `needs: [refined-requirements]` → `[none]` (standalone 실행)
- Phase 0 index.md 생성 — 5개 스킬에 compact recovery 추가
- Discover 프로토콜: DISCOVER_TAG 기반 journal=덮어쓰기, phase=APPEND
- fz-peer-review: Serena memory 도구 추가 + 2개 CHECKPOINT fallback
- fz-excalidraw: 에러 대응 섹션 (18/18 일관성)
- memory-policy.md: 4개 테이블 전면 수정 (stale → actual write_memory)
- context-artifacts.md: CWD=PROJECT_ROOT 정의, standalone peer-review workdir

**Agent Tier-1 Enrichment**
- BAD/GOOD 예시: review-direction, review-arch, review-quality, memory-curator
- Escalation Criteria: 5개 review 에이전트
- Input Format (Task Brief): review-direction, memory-curator
- Cross-skill wiring: fz-code direction-challenge, fz-review step files hydration

**Cross-skill Context**
- team-core.md: 통신 기록 요약 기본 + 원본 drill-down (*-team-full.md)
- cross-validation.md: Codex transcript 요약/원본 분리 정책

### v2.2 (2026-03-12) — Agent Teams + Context Budget + Peer Review Gate

**Agent Teams Frontmatter 적용 (Phase 1-4)**
- `memory: project|user` — 5개 에이전트에 세션 간 영속 학습 적용 (review-arch, impl-correctness, plan-structure, review-quality, memory-curator)
- `skills: [name]` — review-arch(arch-critic), review-quality(code-auditor)에 스킬 사전 주입
- `isolation: worktree` — impl-correctness에 코드 수정 격리
- `TaskCompleted` hook — 에이전트 완료 시 산출물 존재 검증 (settings.json 팀 레벨)
- team-registry.md 모델 컬럼을 `default`/`promoted`로 분리 (거버넌스 명확화)
- agent-team-guide.md §8 전체 문서화

**Context Budget 관리**
- prompt-optimization.md §2.5 — MCP 출력 격리, 도구 정의 최소화, 서브에이전트 효율
- 트리밍 비저하 원칙 — Gate/Few-shot/Step 삭제 금지 (prompt-optimization.md + skill-authoring.md)
- context-artifacts.md — 사전 예방적 Context 관리 섹션 추가

**Peer Review Deleted Logic Migration Gate**
- Gate 4.7-A — 모듈화/리팩토링 PR에서 "삭제 = 누락" 오탐 방지
- arch-critic, code-auditor, review-quality에 "삭제 vs 이동 판별" 원칙 추가
- fz-peer-review, fz-review 토큰 최적화 (-230줄, 정보 보존)
