---
name: fz-rebase
description: >-
  롱텀 브랜치 리베이스 최신화. tracking remote pull(ff) → base 리베이스(머지 커밋 보존) → force-push(lease).
  양방향 조용한 유실 게이트 포함 — 내 변경 소실(커밋 드롭·머지 해결 미재적용·파일 이동·삭제 되살아남) / 팀원 변경 덮어쓰기(충돌 해결 역전·무충돌 적용·force-push 파괴).
  예: 브랜치 최신화, feature 브랜치 develop 위로 리베이스, 롱텀 브랜치 동기화, 리베이스 후 변경 사라짐
  (비사용: 일반 커밋 →fz-commit / PR 생성 →fz-pr / 코드 되돌리기 →fz-fix)
user-invocable: true
disable-model-invocation: true
argument-hint: "[--onto <base>] [--branch <name>]"
allowed-tools: >-
  Bash(git *),
  Bash(bash *),
  AskUserQuestion
provides: []
needs: [none]
intent-triggers:
  - "리베이스|브랜치.*최신화|브랜치.*동기화|브랜치.*업데이트|develop.*위로|롱텀.*브랜치"
  - "리베이스.*(사라|누락|덮어)|(리베이스|force.?push).*(유실|덮어씌)"
  - "rebase|sync.*branch|refresh.*branch|update.*branch"
---

# /fz-rebase — 롱텀 브랜치 리베이스 최신화

> **행동 원칙**: fetch-first → preflight 상태 분기 → 리베이스 직전 스냅샷 → base 리베이스(머지 커밋 보존) → 형태 게이트 + 내용 게이트 → 원격 파괴 게이트 → force-push(lease).
> **개수 보존은 내용 보존을 뜻하지 않는다.** 커밋 수·머지 수가 그대로여도 내 변경이 사라지거나 팀원 변경이 덮어써질 수 있다. 되돌릴 수 없는 force-push 앞에서는 항상 사용자 확인을 받는다.

## 규칙 참조

- CLAUDE.md `## Git & PR Conventions` — fork 기반(origin=개인 fork, upstream=회사 repo). 이 스킬 호출 자체가 "git 작업 명시 요청"이지만, force-push는 그 안에서도 추가 확인을 받는다.
- 롱텀 브랜치는 소유자가 유지하는 브랜치다 — 예: `feature/tvod`는 사용자 소유 롱텀 브랜치라 `upstream`으로의 force-push가 예외적으로 허용된다. 이는 **default가 아니라 소유 브랜치 예외**다.
- 롱텀 브랜치에는 **팀원도 직접 push한다**. 즉 내 리베이스는 남의 커밋을 지날 수 있고, 내 force-push는 남의 커밋을 지울 수 있다 — 양방향 게이트가 필요한 이유.

## 사용 시점

```bash
/fz-rebase                       # 현재 브랜치를 tracking remote pull → 기본 base(develop) 리베이스 → force-push
/fz-rebase --onto release/26.31  # develop 대신 release 브랜치 위로 리베이스
/fz-rebase --branch feature/tvod # 다른 롱텀 브랜치 지정 (체크아웃 상태여야 함)
```

## 워크플로우

| Step | 설명 | 검증 |
|------|------|------|
| 0 | Preflight: fetch-first + 상태 분기 + dirty 검사 | 대상 브랜치 체크아웃 + 워킹 트리 clean |
| 1 | tracking remote의 동일 브랜치를 `merge --ff-only`로 반영 | ff 성공 (실패 = 중단 신호) |
| 1.5 | 리베이스 직전 스냅샷 + 롤백 앵커 + 위험 브리핑 (`snapshot`) | 분기점·이동/삭제·수동해결 머지 기록 |
| 2 | base 위로 `rebase --rebase-merges` | 리베이스 완료 (충돌 시 Step 3-C) |
| 3 | 형태 게이트 (`check`) | 커밋/머지 수 + base 조상 + tree clean |
| 3.5 | 내용 게이트 (`audit`) — **경로 전량 분할 판정** | 세 버킷 불변식 + 머지 건수 + 사라진 라인의 위치 후보 |
| 4 | 원격 파괴 게이트 (`prepush`) → force-push(`--force-with-lease`) | 파괴될 팀원 커밋 0건 → 확인 게이트 → 0/0 |

### 변수 해석 (Step 0 진입 시)

```bash
git fetch --all --prune                                  # fetch-first (항상)
LTB=<--branch 또는 현재 브랜치>                          # long-term branch
TRACK=$(git rev-parse --abbrev-ref "${LTB}@{upstream}")  # 예: upstream/feature/tvod → 원격=upstream
PRIMARY=<upstream 원격 존재 시 upstream, 아니면 origin>
BASE=<--onto 또는 기본 "${PRIMARY}/develop">
PUSH_REMOTE=<TRACK의 원격 부분>
```

> 표기 규약: `<FZ_ROOT>` = fz-plugin 루트 (예: `claude plugin path fz` 결과). 사용자가 본인 설치 경로로 치환.
> 스크립트 경로: `<FZ_ROOT>/skills/fz-rebase/scripts/verify-rebase.sh` (이하 `$VR`)

---

## 완전성 근거 — 경로 단위 배타 분할

"빠뜨린 유실 유형이 없다"를 **열거로 주장하지 않는다.** 세 트리(PRE=리베이스 전, BASE, POST=리베이스 후)의 경로 합집합을 배타 분할하고, 각 버킷에 불변식을 둔다.

| 버킷 | 조건 | 불변식 | 위반의 의미 |
|------|------|--------|------------|
| **① MINE-only** | 내가 변경 & base 미변경 | POST가 **PRE와 바이트 동일**(mode 포함) | 내 변경 유실·변형 |
| **② not MINE** | 내가 미변경 | POST가 **BASE와 바이트 동일** | 팀원 변경 덮어쓰기·무관 파일 오염 |
| **③ OVERLAP** | 양쪽 변경 | 텍스트: 라인 4방향 / 바이너리: 검토 WARN | 진짜 병합 — 사람 판정 필요 |

- 세 버킷이 모든 경로를 덮으므로 **텍스트·바이너리·mode·symlink·gitlink·추가·삭제·이동**이 열거 없이 판정 범위에 들어온다.
- base 측 이동(A→B)은 분할 **전에** 매핑한다. 안 하면 팀원의 정당한 rename에서 내 hunk가 새 경로에 착지한 것을 위반으로 오판한다. 매핑 후 옛 경로 A는 버킷②로 떨어져 "부재여야 함"이 되므로 **옛 경로 dead code 부활**이 자동으로 잡힌다.
- OVERLAP만이 사람 판정 대상이고, 그 크기는 작다 [실측 `feature/tvod`: 내 변경 300파일 중 OVERLAP 0~4개].
- 버킷③ 라인 4방향: ①내 추가가 트리에 없음 ②내 삭제가 되살아남 ③팀원 추가가 트리에 없음 ④팀원 삭제가 되살아남. ②는 base가 다시 추가한 라인을, ④는 내가 다시 추가한 라인을 제외한다 — 그건 상대의 결정이지 유실이 아니다.

### 커버리지 (13/15) — 비대상 2건 명시

covered: 텍스트 라인 추가/삭제(양방향) · 파일 추가 · 파일 삭제 · 파일 이동 · 바이너리 내용 · 파일 mode · symlink 대상 · gitlink(submodule) · 머지 커밋 수동 해결 · 커밋 드롭 · force-push non-merge 파괴 · force-push 머지 파괴.

⛔ **비대상 2건**: **커밋 메타데이터**(author·메시지·trailer 변형 — `--rebase-merges`가 committer를 바꾸는 것은 정상) · **워킹트리 dirty/stash 유실**(Step 0이 dirty를 중단시키지만, 사용자가 stash한 뒤 잊는 경로는 이 게이트 밖). 둘은 리베이스 *내용* 유실이 아니라 워크플로 인접 문제다.

## 조용한 유실 6종 — 왜 조용한가

분할이 판정을 담보하고, 아래는 **왜 이 유실들이 경고 없이 지나가는지**의 근거다 (git 2.50.1 원문).

| # | 조용한 유실 | 메커니즘 | 판정 |
|---|------------|---------|------|
| **L1** | 내 커밋이 통째로 사라짐 | `--empty=drop`이 기본이고, upstream과 동일 패치는 선제 드롭된다 — "commits which are clean cherry-picks ... are detected and dropped as a preliminary step". merge backend는 경고를 내지만 리베이스 로그(+githooks `tuist generate` 출력)에 묻힌다 | Step 3 개수 감소 → 버킷①②③이 흡수 vs 유실 판정 |
| **L2** | 머지 커밋의 수동 해결이 사라짐 | `--rebase-merges`는 머지를 재생성한다 — "Any resolved merge conflicts or manual amendments in these merge commits will have to be resolved/re-applied manually". **머지 개수는 보존**된다. `rerere` 미설정이면 자동 재사용도 없다 | Step 1.5가 `--remerge-diff`로 사전 목록화 → Step 3.5가 **(subject, 해결내용 해시)** 로 대조 + 버킷①. ⛔ 추가 라인 없는 해결(한쪽 선택·삭제·바이너리)은 해시로 구분되지 않아 `NOPLUS`로 표기하고 건수로만 판정한다 |
| **L3** | 내 hunk가 옛 경로에 잔존 | 팀원이 옮기거나 지웠고 rename 감지가 실패 — 유사도 미달·파일 분할·`merge.renameLimit` 기본 7000 초과 | rename 매핑 + 버킷②("옛 경로는 부재여야 함") |
| **L4** | 팀원 변경을 내가 버림 (충돌 해결) | 리베이스에서 `ours`는 base 측, `theirs`가 내 커밋 — "In other words, the sides are swapped". 직관과 반대라 해결 방향이 뒤집힌다 | Step 3-C 역전 명시 + 버킷②③ |
| **L5** | 팀원 변경을 내가 버림 (무충돌) | 3-way merge는 겹치지 않는 hunk를 조용히 병합한다 → 전체 재작성 커밋이나 생성물(xcstrings·Package.resolved·Secrets)이 base 최신을 되돌린다 | 버킷② + 귀속 커밋 제시 |
| **L6** | force-push가 팀원 커밋을 파괴 | ff-pull **이후** 팀원이 push하고, 그 사이 fetch로 tracking ref가 갱신되면 `--force-with-lease`는 **통과**한다 | Step 4 `prepush` 2단 판정 |

### 왜 `range-diff`가 정본이 아닌가

`git range-diff`는 선형 패치 시리즈를 전제해 **머지 커밋을 순회에서 제외한다** [실측: 8커밋(머지 1) 범위 → 7행 출력, 머지 subject 부재]. 머지 히스토리가 내용 그 자체인 롱텀 브랜치에서 이걸 정본으로 쓰면 L2가 통째로 검증 밖에 남는다. `range-diff`는 "어느 커밋에서 바뀌었나"를 지목하는 **귀속 보조**로만 쓴다.

---

### Step 0 — Preflight 상태 머신

성공 경로는 하나가 아니다. `${LTB}`와 `${TRACK}`의 관계를 먼저 분기한다.

| 상태 (`git rev-list --left-right --count ${LTB}...${TRACK}`) | 동작 |
|------|------|
| local behind (`0  N`) | Step 1 진행 — `merge --ff-only ${TRACK}` |
| local ahead (`N  0`) | Step 1 스킵 — local이 source (pull 불필요) |
| **diverged (`N  M`, 양쪽 > 0)** | **중단 + 사용자 판단** — 자동 merge/rebase 금지 |
| 동일 (`0  0`) | Step 1 스킵 |

- 워킹 트리가 dirty이면(`git status --porcelain` 비어있지 않음) 리베이스 전 **중단** — stash/commit 여부를 사용자에게 확인.
- `${LTB}`가 실제 체크아웃돼 있는지 확인 (`git symbolic-ref --short HEAD`).

### Step 1.5 — 리베이스 직전 스냅샷 (판정의 기준선)

ff-pull **이후**·리베이스 **직전**에 실행한다. 이유: 기준선이 pull 이전이면 팀원이 같은 브랜치에 넣은 커밋이 "내 변경"에서 빠지고, 리베이스 이후면 이미 사라진 것을 알 수 없다.

```bash
bash "$VR" snapshot "${BASE}" "${LTB}"
# → COMMITS=<N> MERGES=<M> (Step 3에 전달) + 롤백 앵커 ref + 위험 브리핑
```

브리핑에서 반드시 사용자에게 전달할 것:
- **겹침 파일 수** — 사람 판정이 필요한 유일한 집합. 0이면 *경로별 내용 보존* 관점의 유실 여지가 없다 (⛔ 팀원이 같은 로직을 다른 경로에 새로 만든 경우는 이 판정 밖 — 경로 분할이 답하는 질문이 아니다).
- **팀원 이동/삭제 ∩ 내 변경** — 있으면 L3 1순위. 두 종류의 후보가 함께 나온다.
  - **이동 후보(유사도 낮아 확정 아님)**: 기본 `-M`(50%)이 놓친 이동을 `-M30%`로 한 번 더 본다.
    ⛔ 후보는 `rename-candidates.tsv`에 따로 담기고 **판정에는 쓰지 않는다** — 낮은 임계의
    오매핑이 경로 분할에 섞이면 버킷이 흔들린다.
  - **삭제된 파일의 대체 후보**: 그 파일을 지운 커밋이 함께 추가한 파일을 보여준다.
    ⛔ 같은 커밋이라는 provenance일 뿐 대체의 증거가 아니다. 삭제 커밋이 여럿이거나
    머지로 들어왔으면 후보를 내지 않는다. 표시 개수는 `FZ_REBASE_RELOCATE_SHOW`(기본 5).
- **수동 해결을 품은 머지** — 있으면 L2 대상. `--rebase-merges`가 재적용하지 않는다.
- **base 신선도** — base가 원격 추적 ref이면 `ls-remote`로 대조한다. `fetch --all`은 일부
  원격이 실패해도 exit 0일 수 있어(권한·네트워크), stale한 base 위로 리베이스하면 게이트가
  전부 통과한다. 게이트는 "base 대비 보존"을 볼 뿐 "base가 최신인지"는 보지 않는다.
  ⛔ 확인 실패는 WARN이다 — 오프라인에서 판정을 막지 않는다. `FZ_REBASE_SKIP_LSREMOTE=1`로 끌 수 있다.
  ⛔ stale의 실제 원인은 `remote.<name>.skipFetchAll`·fetch refspec 제외·호출자의 오류 무시다
  (`fetch --all`은 child 실패 시 nonzero를 반환한다).

롤백 앵커는 `refs/fz-rebase/pre/<branch>-<shorthash>` ref로 남는다. 이름에 해시가 들어가므로 **snapshot 재실행이 이전 앵커를 덮어쓰지 못하고**, ref이므로 GC 대상에서도 벗어난다(audit이 PRE 트리를 계속 읽을 수 있는 근거). 완료 후 정리: `git for-each-ref refs/fz-rebase/`로 확인 → `git update-ref -d <ref>`.

머지가 매우 많은 브랜치에서 스냅샷이 오래 걸리면 `FZ_REBASE_SKIP_REMERGE=1`로 머지 스캔만 생략할 수 있다 — 단 그 경우 L2 검출이 꺼진다는 것을 사용자에게 알린다.
`FZ_REBASE_RELOCATE_SHOW=N`은 대체 후보를 몇 개까지 나열할지 정한다(기본 5). ⛔ 표시량만
자르는 값이고 후보 특정 가능성을 판정하지 않는다 — 전체 개수와 커밋은 항상 출력된다.

### Step 2 — 리베이스 (머지 커밋 보존)

```bash
git rebase --rebase-merges "${BASE}"
```

- `--rebase-merges`는 선택이 아니다. 기본 `git rebase`는 머지 커밋을 스킵해, PR로 머지된 내용이 통째로 사라질 수 있다 (공유 브랜치에서 패키지 삭제 사고 이력). 이유: 롱텀 브랜치의 머지 히스토리는 내용 그 자체다.
- 진행 로그의 `skipped previously applied commit` / `dropped` 경고를 흘리지 않는다 — L1의 유일한 실시간 신호다. `advice.skippedCherryPicks`가 꺼져 있으면 이 신호조차 없으니, 판정은 Step 3.5에 맡긴다.

### Step 3 — 형태 게이트 + 충돌 해결

**3-A 형태 게이트** — 개수·조상·clean만 본다 (내용 판정은 Step 3.5):

```bash
bash "$VR" check "${BASE}" "${LTB}" <snapshot의 COMMITS> <snapshot의 MERGES> [<핵심 경로> ...]
```

exit 0이 아니면 force-push하지 않는다. 커밋 수 감소는 **그 자체로 유실이 아니다** — base가 내 패치를 흡수해 드롭된 정상 케이스가 많다. Step 3.5로 판정한다.

**3-C 충돌 해결** — 사용자와 하나씩 (이 스킬의 핵심 요구):

충돌은 둘 중 하나를 고르는 문제가 아니라 두 의도를 합치는 문제다. 이유: 한쪽을 통째로 택하면 반대쪽이 조용한 유실이 되고, 그 유실은 Step 3.5에서 사후에야 드러난다.

리베이스 중 `ours`는 **내 것이 아니다** — "the side reported as ours is the so-far rebased series, starting with `<upstream>`, and theirs is the working branch. In other words, the sides are swapped" [git-rebase(1)].

```
BAD:  git checkout --ours <file>
      → "내 변경을 유지"로 읽고 실행하지만, 실제로는 내 커밋을 버리고 base(팀원) 쪽을 남긴다.

GOOD: 충돌 파일마다 **조회로** 어느 쪽이 무엇인지 확정한 뒤 제시한다.
      git ls-files --unmerged -- <file>   # stage 2·3 존재 여부 = 각 측의 수정/삭제
      git show :2:<file> · :3:<file>      # 각 측의 실제 내용
      ⛔ "--ours = 팀원"처럼 고정 라벨로 외우지 않는다 (아래 § 참조).
      그 뒤 양쪽 변경의 의미를 설명하고, 합칠 방향을 사용자와 정한다.
```

- `-X ours` / `-X theirs` 자동 해결은 하지 않는다 (같은 역전이 전 파일에 일괄 적용된다).
- 같은 충돌이 반복돼 `git rerere`를 고려한다면 `--no-rerere-autoupdate`와 함께 쓴다 — 과거 해결의 무언 재적용은 이 스킬이 막으려는 것과 같은 종류의 조용한 변경이다.

#### 귀속은 라벨로 외우지 말고 파일마다 조회한다

⛔ 위 `--ours`/`--theirs` 대응은 **설명용 근사이지 계약이 아니다.** ours는 base에 앞서
replay된 커밋이 누적된 **현재 HEAD**이고, 이 브랜치에는 팀원도 직접 push하므로(규칙 참조 3행)
지금 replay 중인 커밋이 팀원 것일 수 있다. `--rebase-merges`가 머지를 재생성하다 난 충돌은
양쪽 모두 재작성된 tip일 수도 있다. 고정 라벨을 그대로 제시하면 막으려던 L4·L5를 다시 만든다.

```bash
git ls-files --unmerged -- <file>          # stage 2 = ours 측 · stage 3 = theirs 측
git log -1 --format='%an  %s' REBASE_HEAD  # 지금 replay 중인 커밋의 author와 subject
```

stage 3이 없으면 theirs 측이 지운 것이고, stage 2가 없으면 ours 측이 지운 것이다.
내용이 필요하면 `git show :2:<file>` · `:3:<file>`로 직접 읽는다.
⛔ `REBASE_HEAD`는 **지금 replay 중인 커밋**의 정보일 뿐, 각 stage 전체의 소유자를
증명하지 않는다 — ours 측은 앞서 replay된 커밋들이 누적된 결과다.
modify/delete에서 `git add`와 `git rm`이 각각 무엇을 버리는지는 **이 조회로 확정**한다 —
삭제 주체가 어느 쪽이냐에 따라 방향이 뒤집히므로 미리 정해둘 수 없다.

#### 확인 절차 (soft gate)

⛔ **이것은 soft gate다.** `AskUserQuestion`이 실제로 호출되면 응답 전까지 진행이 멈추지만,
호출을 생략하는 것 자체는 프롬프트로 막지 못한다. 결정적 차단이 필요하면 PreToolUse hook이
필요하고 그것은 사용자 합의 사항이다. 여기서 얻는 것은 준수율과 개입 지점의 명시성이다.

충돌 파일마다 아래를 제시하고 `AskUserQuestion`으로 방향을 받는다.
⛔ 답을 받기 전에는 **충돌 경로의 워킹트리·인덱스를 어떤 도구로도 바꾸지 않는다** —
`git add`/`git rm`/`git checkout`/`git restore`/`git mergetool`/`git rebase --continue`/`--skip`,
그리고 Edit·Write·셸 리다이렉션도 같다. 명령 이름이 아니라 *상태를 바꾸는 행위*가 기준이다.

제시 항목: 파일 경로 · 충돌 종류(내용 / modify-delete, 위 조회로 판별) ·
각 측이 담은 변경과 귀속(`REBASE_HEAD` author·subject) ·
"어느 선택도 확신이 없으면 중단을 고른다. `--abort`는 리베이스 전 상태로 되돌린다."

선택지는 조회 결과에 맞춰 만든다. 내용 충돌이면 양쪽 병합 / 한쪽 채택(어느 쪽인지 명시) /
전체 리베이스 중단. modify-delete면 파일 유지 / 삭제 수용 / 전체 리베이스 중단이고,
각 라벨에 **무엇을 버리는지** 조회 결과대로 적는다.

⛔ 중단 선택지는 "이 파일만 빼기"가 아니라 **전체 리베이스 중단**이다. git에는 파일 단위
abort가 없고 `--skip`은 현재 커밋을 통째로 버린다. 라벨이 이를 오해시키면 안 된다.

#### 배치 루프

`AskUserQuestion`은 한 번에 질문 4개가 상한이므로 충돌이 그보다 많으면 나눠 묻는다 [verified: AskUserQuestion 도구 스키마 `questions` maxItems=4].

```
리베이스 진행 중인 동안 반복:
  a. RM="$(git rev-parse --git-path rebase-merge)"; RA="$(git rev-parse --git-path rebase-apply)"
     둘 다 없으면 완료 — 루프 종료
     ⛔ `.git/rebase-merge`를 리터럴로 쓰지 않는다. linked worktree에서 .git은 파일이다 [verified: `verify-rebase.sh:53` 주석이 같은 이유로 `git rev-parse --git-dir`을 쓴다]
  b. `git diff --name-only --diff-filter=U -z` — 지금 replay 중인 커밋의 미해결 충돌
  c. 목록이 비어 있으면 `git rebase --continue`
     → exit 0이면 a로 (다음 커밋 replay에서 새 충돌이 날 수 있다 — continue는 종료가 아니다)
     → exit≠0이면 루프를 멈추고 원인을 사용자에게 제시한다 (편집기 대기 · hook 실패 ·
       빈 커밋 등). ⛔ `--skip`을 자동 폴백으로 쓰지 않는다 — 커밋 전체를 버리는 일이라
       그것도 물어야 한다
  d. 4개씩 묶어 AskUserQuestion 호출 (파일 하나당 질문 하나).
     매 배치에 "이번 stop 총 N개 · 처리 M개 · 남은 K개"를 함께 보인다
  e. 답 중에 중단이 하나라도 있으면 `git rebase --abort` 후 루프 전체 종료
  f. 나머지 답대로 해당 파일만 해소 → a로
```

한 stop의 충돌이 12개를 넘으면 첫 배치 전에 한 번 묻는다 — 전수 검토를 계속할지,
`--abort` 후 리베이스 범위를 나눌지. ⛔ 일괄 자동 해결 선택지는 만들지 않는다.
같은 파일이 다음 커밋에서 다시 충돌하면 **새 replay 커밋이므로 다시 묻는다**.

- 사용자 선택을 받은 뒤에도 구체적인 병합 결과나 어느 쪽이 누구 것인지가 불확실하면
  적용·stage하지 말고 다시 묻거나 전체 중단을 제안한다. 선택을 받았다는 것이 구현
  불확실성까지 해소했다는 뜻은 아니다.

### Step 3.5 — 내용 게이트 (경로 전량 분할)

```bash
bash "$VR" audit "${BASE}" "${LTB}"
```

세 버킷 불변식을 검사하고 위반을 등급별로 보고한다. `INFO`는 정상(흡수·이동), `WARN`은 사람 확인 필요(OVERLAP 바이너리 · **사라진 라인의 위치 후보** · 머지 해결 축소), `HALT`만 유실이다. OVERLAP 라인 검사는 POST 트리 전역 라인 집합과 대조해 코드 이동을 유실로 오판하지 않으며, 확인 상한(cap) 없이 전량 판정한다.

audit은 **리베이스 후**에만 유효하다. base가 아직 POST의 조상이 아니면 base의 신규 라인이 "내가 지운 것"처럼 보여 판정이 통째로 뒤집히므로, 스크립트가 조상 조건을 먼저 확인하고 중단한다.

실규모 참고 [실측: 커밋 142 · 변경 300파일 · 추적 3,214파일]: `snapshot` 0.4s / `audit` 0.4s.

git 레벨 검증은 **내용 동일성**까지다. 내 변경이 살아있으나 의미상 죽은 코드가 된 경우(예: 팀원이 호출부를 제거)는 잡지 못한다 — OVERLAP이 있거나 팀원이 구조를 바꿨다면 빌드/실행 확인을 사용자에게 권한다. ⛔ 이때 plain CLI `xcodebuild`는 쓰지 않는다 (Package.resolved churn·의존성 실패 유발) — Xcode 또는 워크트리 빌드 레시피로 안내한다.

### Step 4 — 원격 파괴 게이트 + force-push (확인 게이트)

되돌릴 수 없는 작업이다. **push 직전에 원격을 다시 실측**한다 — Step 1 이후 팀원이 push했을 수 있고, 그 경우 lease는 통과하면서 팀원 커밋만 사라진다(L6).

```bash
bash "$VR" prepush "${LTB}" "${PUSH_REMOTE}" "<원격 브랜치명>"
```

- `git ls-remote`로 원격 실측 → tracking ref가 stale이면 HALT(fetch 후 재실행). 오프라인이면 HALT — 되돌릴 수 없는 단계라 원격 상태를 모른 채 진행하지 않는다(`FZ_REBASE_SKIP_LSREMOTE=1`로 강제 우회 가능, 보호가 약해진다).
- **non-merge 커밋**: `git cherry`로 등가 패치가 없는 원격 커밋을 지목 → 1건이라도 있으면 HALT. 리베이스로 해시가 바뀌어도 패치 등가로 판정하므로 내 커밋을 오탐하지 않는다.
- **머지 커밋**: `git cherry`는 머지를 아예 보고하지 않는다 [실측: 원격 3커밋(머지 1) → `+` 2건]. 그래서 별도 2단 판정 — 수동 해결을 품은 머지(`--remerge-diff` 비어있지 않음)는 그 내용이 어느 부모에도 없으므로 **HALT**, 내용 없는 평범한 PR 머지는 부모가 non-merge 판정에서 다뤄지므로 히스토리 구조만 사라진다 → **WARN**. 평범한 PR 머지마다 HALT하면 롱텀 브랜치에서 게이트를 쓸 수 없게 된다.

게이트 통과 후 아래를 제시하고 승인받는다:
- 대상: `${PUSH_REMOTE} ${LTB}` / lease 타겟 해시와 로컬 HEAD / 덮어써지는 커밋 수(양방향)
- `${PUSH_REMOTE}`가 `upstream`(회사 repo)이면 소유 롱텀 브랜치 예외임을 명시 — 일반 브랜치라면 force-push 대상이 origin(fork)이어야 한다.

승인 후: `git push "${PUSH_REMOTE}" "${LTB}" --force-with-lease=<원격브랜치>:<실측 해시>` → 완료 시 `git rev-list --left-right --count ${LTB}...${TRACK}`이 `0  0`인지 확인. lease를 실측 해시로 명시 pin하는 이유: 기본 lease는 로컬 tracking ref를 신뢰하므로, 그 ref가 stale이면 보호가 무력하다.

## TVING/Tuist 고유 지식

- develop은 Tuist 전환됨 — githooks가 리베이스 중 구조 변경 감지 시 `tuist generate`를 자동 실행한다(정상 동작). 이 출력이 L1의 드롭 경고를 가리므로 로그를 흘려보내지 않는다.
- pbxproj는 git 미추적(Tuist 생성)이라 구브랜치 리베이스 시 modify/delete 충돌이 반복될 수 있다 → 해당 pbxproj/Package.resolved는 **삭제 수용을 권고**한다. ⛔ 다만 3-C의 확인 절차를 건너뛰지 않는다 — 그 파일의 질문에서 대가를 밝히고 사용자가 고른 뒤에 `git rm`하며, 그 stop의 U 목록이 모두 해소된 뒤에만 continue한다.
- ⚠️ 위 `git rm` 습관은 **L3/L5의 발생 경로**이기도 하다 — 생성물이 아닌 파일에 같은 해소를 적용하면 내 변경이나 팀원 변경이 조용히 사라진다. 삭제 수용은 Tuist 생성물에 한정하고, 나머지는 Step 3.5가 판정한다. xcstrings는 우리 추가와 타 기능 삭제가 라인 단위로 섞이므로 충돌 해결 후 중복 키 검사가 필요하다.

## 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "feature 브랜치 최신화해줘" | trigger | 핵심 유스케이스 (description 예시) |
| "이 브랜치 develop 위로 리베이스" | trigger | intent-trigger "리베이스" + "develop.*위로" |
| "롱텀 브랜치 동기화" | trigger | intent-trigger "브랜치.*동기화" |
| "리베이스했는데 내 변경이 사라졌어" | trigger | intent-trigger "리베이스.*사라" — 유실 게이트가 이 스킬 소관 |
| "rebase my branch onto develop" | trigger | intent-trigger "rebase" |
| "커밋해줘" | NOT trigger | → fz-commit (Will Not: 커밋 생성) |
| "PR 만들어줘" | NOT trigger | → fz-pr (Will Not: PR 생성) |
| "가이드 최신화해줘" | NOT trigger | → fz-modernize (브랜치 문맥 없는 "최신화"는 문서 모더나이제이션) |
| "이 커밋 되돌려줘" | NOT trigger | → fz-fix (Will Not: 코드/커밋 되돌리기) |

### Functional

회귀 oracle: `bash <FZ_ROOT>/skills/fz-rebase/scripts/test-gates.sh` (65 assertion).
구성은 유실 검출 · 오경보 방지 · **SKILL 정적 계약**(K1~K8) 셋이다. 셋째는 충돌 확인 절차가
문서에서 사라지는 것을 잡는다 — 그 절차는 스크립트가 아니라 프롬프트라 동작 oracle이 없다.

| Given | When | Then |
|-------|------|------|
| behind + clean + 충돌 없음 | `/fz-rebase` | ff pull → snapshot → `--rebase-merges` → check/audit/prepush 전부 exit 0 → 확인 게이트 → push 후 0/0 |
| LTB과 TRACK이 diverged | `/fz-rebase` | Step 0에서 중단 + 상태 제시 + 사용자 판단 요청 |
| 리베이스 중 충돌 | `/fz-rebase` | 중단 → `--ours`=팀원/`--theirs`=내 커밋 명시 → 사용자와 해결 (`-X` 미사용) |
| 팀원 삭제 + 내 수정, `git rm`으로 해소 | audit | HALT — 내 변경 유실 [S1] |
| 충돌을 `--theirs`로 해소해 팀원 변경 폐기 | audit | HALT — 팀원 변경 덮어쓰기 + 귀속 커밋 [S2] |
| base가 내 패치를 흡수 (커밋 수 감소) | audit | OK 무경보 — 흡수는 유실이 아니다 [S3] |
| 팀원 rename, 내 hunk가 새 경로 착지 | audit | OK 무경보 (분할 전 rename 매핑) [S4] |
| 머지 커밋의 수동 해결 미재적용 | audit | HALT — subject 대조 [S5] |
| 내가 지운 파일 + 팀원 수정 → 파일 유지로 해소 | audit | HALT — 내 삭제 유실 [S7] |
| 팀원이 지운 파일 + 내 수정 → 파일 유지로 해소 | audit | HALT — 팀원 삭제 유실 [S8] |
| 바이너리 변경 (MINE-only) | audit | OK 무경보 / 내용 되돌려지면 HALT [S9 S10] |
| 파일 mode 변경 (MINE-only) | audit | OK 무경보 / mode 되돌려지면 HALT [S11 S11b] |
| 바이너리 OVERLAP (양쪽 변경) | audit | WARN + 목록 (auto-HALT 아님) [S12] |
| 내가 손대지 않은 팀원 파일 오염 | audit | HALT — 버킷② 위반 [S15] |
| ff-pull 이후 팀원이 원격에 push | prepush | HALT — 파괴될 커밋 지목 [S6] |
| 원격에 평범한 PR 머지 | prepush | WARN (HALT 아님) [S13] |
| 원격에 수동 해결 머지(evil) | prepush | HALT — 부모에 없는 내용 [S14] |
| 워킹 트리 dirty | `/fz-rebase` | 리베이스 전 중단 + stash/commit 확인 요청 |

## Boundaries

**Will**:
- fetch-first 후 preflight 상태 분기 (behind/ahead/diverged)
- 리베이스 직전 스냅샷 + 롤백 앵커 ref + 위험 브리핑
- base 위로 `--rebase-merges` 리베이스 (머지 커밋 보존)
- 형태 게이트 + 경로 전량 분할 내용 게이트 + 원격 파괴 게이트
- 충돌을 파일마다 `AskUserQuestion`으로 확인하며 해결 — 귀속은 `git ls-files --unmerged`로 매번 조회 (soft gate)
- 확인 게이트 후 실측 해시로 pin한 `--force-with-lease` push

**Will Not**:
- diverged 상태 자동 병합/리베이스 → 사용자 판단
- 충돌 자동 해결(`-X ours/theirs`) → 사용자와 해결
- 사용자 응답 전 충돌 경로의 워킹트리·인덱스 변경 → 확인 후에만 (도구 종류 무관)
- `git rebase --skip` 자동 폴백 → 커밋 전체를 버리는 일이라 이것도 확인 대상
- 내용 게이트·원격 게이트를 건너뛴 force-push → 항상 게이트
- 개수만 보고 "유실 없음" 판정 → 분할 불변식이 정본
- 커밋 메타데이터·stash 유실 검증 → 비대상(위 커버리지 참조)
- CLI `xcodebuild`로 빌드 검증 → Xcode/워크트리 레시피 안내만
- 일반 브랜치를 `upstream`(회사 repo)에 force-push → origin(fork) 대상 (upstream은 소유 롱텀 브랜치 예외)
- 커밋 생성 → `/fz-commit` · PR 생성 → `/fz-pr` · 코드/커밋 되돌리기 → `/fz-fix`

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| `merge --ff-only` 실패 | ff 불가 = 조용한 merge 아님, 중단 신호 → 상태 재확인 | diverged면 Step 0 분기로 |
| 리베이스 충돌 | 배치 루프 — 파일별 귀속 조회 → AskUserQuestion → 해소 → U 목록 빌 때만 continue | `git rebase --abort` |
| `rebase --continue` 실패 | 루프 중단 + 원인 제시 (편집기 대기·hook 실패·빈 커밋) | `--skip`은 자동 금지 — 확인 후 |
| check HALT: 커밋/머지 감소 | **audit으로 판정** — 버킷 불변식 통과면 base 흡수(진행 가능, 사용자 승인), 위반이면 유실(롤백) | `git reset --hard refs/fz-rebase/pre/<branch>-<hash>` |
| check HALT: key path 부재 | coarse smoke test — 팀원의 정당한 이동일 수 있다 | audit의 분할 판정으로 결론 |
| audit HALT: 버킷① 위반 | base가 손대지 않은 파일이 변형됨 → 충돌 해결이 무관 파일로 번졌는지 확인 | 롤백 후 재리베이스 |
| audit HALT: 버킷② 위반 | 팀원 변경 덮어쓰기 — 제시된 귀속 커밋 확인 후 내 의도인지 사용자 판정 | 실수면 해당 파일을 base 내용으로 복원 |
| audit HALT: OVERLAP 라인 위반 | 4방향 중 어느 것인지 확인 → `range-diff`로 커밋 귀속 → 해당 hunk 재적용 | 롤백 후 충돌 재해결 |
| audit HALT: 머지 해결 유실 | `git log -1 --remerge-diff <원래 머지 해시>`로 해결 내용 확인 → 수동 재적용 | 롤백 후 별도 커밋으로 분리 |
| 브리핑: 이동 후보 / 대체 후보 | 확정이 아니라 참고다 — 충돌 해결 시 그 파일을 함께 열어 판단 | 후보가 틀리면 무시. 커밋을 직접 확인 |
| audit WARN: 동일 라인 위치 후보 | 내 라인이 이 파일에 없고 다른 경로에 같은 문자열 존재 — 팀원의 이동/리팩토링인지 확인 | 의도된 이동이면 진행, 아니면 해당 hunk 재적용 |
| audit HALT: base 이동 | snapshot 이후 base가 움직여 기준선이 둘 — 판정 불가 | 재-snapshot 후 리베이스 재수행 |
| audit WARN: 머지 해결 축소 | 건수는 유지됐으나 remerge 줄 수 감소 — 재생성 변동일 수 있음 | `--remerge-diff`로 내용 대조 |
| audit WARN: OVERLAP 바이너리 | 라인 판정 불가 — 해당 파일을 사람이 열어 확인 | 확인 결과를 사용자에게 보고 후 진행 여부 결정 |
| audit HALT: 리베이스 미완료 | 실행 시점 오류 — 리베이스 완료 후 재실행 | 중단 상태면 3-C 해결 또는 `--abort` |
| audit: snapshot 상태 없음 | 내용 검증 불가 — 형태 게이트만 유효함을 명시 | 다음 리베이스부터 Step 1.5 선행 |
| prepush HALT: tracking stale | 팀원 push 발생 → fetch 후 그 커밋을 먼저 반영 | 반영 후 재검사 |
| prepush HALT: 파괴될 커밋/머지 | push 금지 → ff-merge 또는 리베이스로 반영 | 반영 후 재검사 |
| prepush WARN: 평범한 머지 소실 | 내용은 부모에 보존 — 히스토리 구조 소실을 사용자에게 알리고 진행 판단 | 구조 보존이 필요하면 머지 방식 재검토 |
| `--force-with-lease` 거부 | remote가 lease 기대 해시와 다름(타인 push) → 재fetch | 변경 검토 후 재시도 판단 |
| pbxproj modify/delete 충돌 | 삭제 수용 권고 — 단 3-C 확인 후 `git rm`, U 목록 해소 후 continue | 생성물이 아니면 삭제 수용 금지 |
| dirty 워킹 트리 | 리베이스 전 중단 | stash 또는 commit 후 재실행 |

## Completion → Next

- 성공 시: 로컬=remote 동기화(0/0) + 리베이스된 커밋 수·base + audit/prepush 요약(분할 수치·INFO/WARN 포함) 출력. 롤백 앵커 정리 안내.
- diverged/충돌 중단 시: 현재 상태와 다음 선택지 제시, 사용자 판단 대기.
- HALT 시: 사유 + 롤백 경로(앵커 ref) 안내, force-push 미실행 상태 유지.

---

## Verification Discipline

- 커밋 수·버킷 판정·경로 착지 등 사실 주장 전 `verify-rebase.sh` 또는 `git` 실측 결과를 근거로 제시한다. 스냅샷 없이 "유실 없음"을 말하지 않는다 — 기준선이 없으면 판정 자체가 불가하다.
- "누락 없음"은 분할이 경로 합집합을 덮는다는 **구조**로 말하고, 커버리지는 13/15 + 비대상 2건 명시로 말한다. 열거식 "다 확인했다"는 쓰지 않는다.
- force-push 완료를 보고하기 전 `git rev-list --left-right --count`로 동기화(0/0)를 확인한다.
- 게이트 자체의 회귀 검증: `bash <FZ_ROOT>/skills/fz-rebase/scripts/test-gates.sh` (스크립트 **또는 SKILL.md** 수정 시 실행). 유실 검출과 **오경보 방지**를 동등하게 검사한다 — 후자가 깨지면 게이트는 노이즈가 되어 무시된다. ⛔ `assert()`는 exit code만 보므로 새 WARN 경로는 `assert_no_warn`으로 따로 검사해야 한다.
- 참조: `modules/uncertainty-verification.md` (Default-Deny).
