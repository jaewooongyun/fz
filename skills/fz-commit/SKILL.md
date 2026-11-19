---
name: fz-commit
description: >-
  Git 커밋 생성. Conventional Commit 형식 + 티켓 참조 자동 포함.
  예: 커밋해줘, 저장해줘, 변경사항 커밋 (비사용: PR 생성 →fz-pr)
user-invocable: true
disable-model-invocation: true
argument-hint: "[TICKET-ID]"
allowed-tools: >-
  Bash(git status *), Bash(git diff *), Bash(git log *), Bash(git fetch *)
metadata:
  provides: [commit]
  needs: [code-changes]
  intent-triggers:
    - "커밋"
    - "commit"
---

# Git Commit Skill

## 규칙 참조

CLAUDE.md 에 팀 커밋 스킬이 선언되어 있으면(절 제목과 무관 — 스킬 경로나 이름) 그 스킬로 위임한다. 없으면 Conventional Commits 표준을 따른다.
정본: `modules/governance.md` § 팀 스킬 위임 — 커밋은 사용자가 이 턴에 요청했을 때만 한다.

---

## 사용 도구

팀 커밋 스킬이 없을 때만 `git commit` 으로 커밋한다(위 § 규칙 참조 — 요청 없는 커밋은 하지 않는다).

`allowed-tools` 는 조회 꼴(`git status` · `git diff` · `git log` · `git fetch`)만 사전 승인한다 — 쓰기(`git add` · `git commit` · `git reset`)는 권한 프롬프트를 거친다. 패턴은 부명령을 승인할 뿐 보안 경계가 아니다 — 승인된 조회 부명령도 쓰거나 실행하는 옵션(`git diff --output=<파일>` · `git fetch --upload-pack=<명령>`)을 받고, `git fetch` 는 그 자체로 ref 를 갱신하고 네트워크를 쓴다. 프롬프트 없이 쓰려면 자기 설정의 허용 목록(`permissions.allow`)에 그 꼴을 넣는다.

---

## 커밋 단위 가이드

**원칙**: 기능 단위로 커밋하되, 작업 흐름이 끊어지지 않을 정도의 크기 유지

| 판단 | 예시 |
|------|------|
| 너무 작음 | import 한 줄 추가, 변수명 하나 변경 |
| 너무 큼 | 여러 기능 혼합, 관련 없는 파일들 묶음 |
| 적절함 | 하나의 기능/버그픽스가 완결되는 단위 |

⛔ **사용자가 분할 단위를 말하면 그 말이 기본값이다** — 예: "기능 단위로" 를 내 기본 규칙(잘게 나누기 · 묶기) 쪽으로 다시 해석하지 않는다. 말이 모호하면 묻는다 (F-239)

**좋은 커밋 단위 예시**:
- UI 컴포넌트 하나 추가 + 관련 스타일
- API 호출 로직 수정 + 에러 처리
- 버그 수정 + 관련 테스트 코드

### ⛔ 나눈 뒤 커밋마다 단독 검증 (F-310)

기능 단위 분할의 값은 커밋을 하나씩 되돌리거나 bisect 할 수 있다는 데 있다. 파일 배정만 보고 나누면 이 값이 조용히 깨진다 — 실측 10커밋 중 5개가 단독으로 저장소 검사를 통과하지 못했고, 다음 판에서 같은 원인으로 재발했다.

1. **개수·목록 선언을 먼저 센다** — 디렉터리의 파일 수나 목록을 문서에 적고 대조하는 검사가 있으면(fz: `lint_contracts` #N2 가 `CLAUDE.md`·`docs/architecture.md` 의 `scripts/` 개수를 본다), 그 디렉터리에 파일을 더하는 커밋마다 선언을 **같은 커밋에서** 그 시점 값으로 맞춘다
2. **검사기는 검사 대상 뒤에** — 전체 검사가 부르는 새 검사기의 배선은 검사기와 그 대상이 모두 들어간 뒤의 커밋에 둔다
3. **커밋마다 격리 clone 에서 돌린다** — clone 에도 커밋 훅(`core.hooksPath`)과 커밋 신원(`user.name` · `user.email`)을 건다. clone 은 원본 저장소의 로컬 설정을 물려받지 않아서, 빠뜨리면 전역 신원으로 커밋된다(noreply 신원 저장소 — fz: `bash "${FZ_PLUGIN_ROOT}/scripts/isolated_clone.sh" <원본> <clone 경로>` 가 태그 없이 clone 하고 원본 로컬의 커밋 신원 · 유지관리자 설정(`fz.maintainer` · `fz.neutralizeRules`) · 훅 경로를 옮기며 `user.useConfigOnly` 를 건다. exit 2 면 그 clone 을 쓰지 않고 `UNRUN:` 줄의 사유를 고친 뒤 다시 만든다). 커밋마다 저장소 전체 검사(fz: `scripts/health-check.sh`)를 실행한다. ⛔ 파일 배정 dry-run 은 단독 실패를 보지 못한다
4. **검증한 객체를 그대로 쓴다** — 1번처럼 작업 트리에 없던 중간 상태가 있으면 실제 저장소에서 같은 묶음으로 다시 커밋하지 않는다. 격리 clone 의 검증된 커밋을 `git fetch` 로 가져와 `git reset --mixed <검증한 끝 커밋>` 으로 브랜치만 앞으로 옮긴다(작업 파일 불변 · fast-forward 와 같은 방향). 옮긴 뒤 `git status` 가 비어야 하고, 가져온 커밋의 작성자·커밋터 메일이 의도한 신원이어야 한다 — 옮기기 전에 잰다. 원본에 로컬 `user.email` 이 있으면 `bash "${FZ_PLUGIN_ROOT}/scripts/isolated_clone.sh" --check-fetch <clone 경로> <원본>` 이 exit 0 · 끝 줄 `ISOLATED_CLONE_FETCH_OK` 여야 한다(1 = 어긋난 커밋과 축을 한 줄씩 · 2 = 판정 불가). 없으면 `git log --format='%h %ae %ce' <원본 브랜치>..<검증한 끝 커밋>` 으로 직접 본다
5. **외부 형식 파서를 바꾸는 커밋에는 실표본 재생 셀을 같이 넣는다** — 남이 정한 기록 형식(GPT 스트림 로그 · Claude Code transcript · Workflow journal)을 읽는 코드를 바꾸면, 스크럽한 실표본(`provenance.json` 에 CLI 버전 · 채취 시점 · 스크럽 방식 · 해시)을 바뀐 파서로 다시 읽는 셀이 같은 커밋에 있어야 한다(fz: `tests/fixtures/gpt/rollout-replay` · `tests/fixtures/wf-metrics/transcript-replay` · `journal-replay`). 합성 셀만으로는 실제 기록과 어긋난 것을 보지 못한다(F-358). 표본이 없으면 그 셀은 UNRUN 이고 통과가 아니다

---

> 테스트 케이스 · 시나리오: `references/test-spec.md` (§ SKILL.md 에서 옮긴 테스트 케이스)

## Boundaries

**Will**:
- Conventional Commits 형식으로 커밋 메시지 생성
- 트래커 티켓 ID를 커밋 prefix에 포함 — 조회는 CLAUDE.md 가 선언한 트래커 MCP(연결돼 있을 때 · 권한 프롬프트를 거친다), 없으면 인자 · 수동 입력(`modules/governance.md` § 팀 스킬 위임)
- CLAUDE.md 의 팀 커밋 규칙 · 스킬 선언 우선 적용(절 제목 무관 — `modules/governance.md` § 팀 스킬 위임)
- 커밋 단위 판단 및 분리 제안

**Will Not**:
- 코드 수정 → `/fz-code` 또는 `/fz-fix` 사용
- PR 생성 → `/fz-pr` 사용
- 브랜치 생성/전환 → `git` CLI 사용
- force push 또는 커밋 이력 변경
- **팀 공유 영역 자동 커밋 (36차)**: staged 파일에 `.swiftlint.yml` / `.github/` / `Package.swift` / `*.xcconfig` / pre-commit hook 등 보호 파일 감지 시 자동 커밋 금지. 사용자 명시 승인(ASR) 후 진행. 검증 grep:
  ```bash
  PROTECTED_PATTERN='\.swiftlint\.yml|\.github/|Package\.swift|.*\.xcconfig|.*Podfile|\.pre-commit'
  PROTECTED_FILES=$(git diff --cached --name-only | grep -E "$PROTECTED_PATTERN")
  [ -n "$PROTECTED_FILES" ] && AskUserQuestion("36차: 보호 파일 변경 — $PROTECTED_FILES 커밋 승인?")
  ```

---

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| nothing to commit | staged 파일 없음 안내 | `git status` 확인 후 스테이징 요청 |
| commit-msg hook 실패 | 훅 오류 메시지 안내 | 메시지 형식 수정 후 재시도 |
| 트래커 티켓 조회 실패 · 불가 (호출 오류 · 선언한 트래커 MCP 미연결 · 선언 없음 · 권한 거절) | 수동 입력 안내 — 트래커 도구는 사전 승인하지 않는다 | 인자로 전달받은 티켓 ID 직접 사용 |
| 커밋 단위 판단 불명확 | 변경 파일 목록 출력 후 사용자 확인 | 사용자 지시에 따라 분리 |
| 분할 커밋 단독 검증 실패 | 실패 커밋의 검사 로그 끝과 원인을 보인다 | 묶음·순서를 고쳐 격리 검증부터 다시 — 실제 저장소에는 커밋하지 않는다 |

---

## Completion → Next

- 커밋 성공 시: 커밋 해시와 메시지 요약 출력 → `/fz-pr`로 PR 생성 가능
- 커밋 단위 분리 제안 시: 분리 계획 제시 후 사용자 확인 대기
- 훅 실패 시: 오류 원인 안내 → 메시지 수정 후 재시도
