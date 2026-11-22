# CLAUDE.md — fz Plugin

> **Sources (last audited: 2026-07-25 — 모델 사실 축):** `guides/llm-references.md` §1 정본 대조 완료. 그 외 인용은 개별 `[verified:]` 태그 참조. 최신성 검사: `python3 scripts/lint_doc_freshness.py`

## Build
- 빌드 없음 (마크다운 프로젝트)
- 검증: `bash scripts/plugin_validate.sh` — 대상은 plugin.json(루트 디렉터리를 주면 marketplace 만 검증한다)

## Git Workflow

### 릴리즈 (변경사항 배포)
1. `.claude-plugin/plugin.json` version bump — **변경 성격에 따른다**
   - `[MINOR]` = 새 검사·스킬·모듈 추가 등 기능 증가 (실측: v4.15.0~v4.23.0 전부 MINOR)
   - `[PATCH]` = 배선 복구·문구 정정 등 (예: v4.23.1)
   - ⛔ 구판은 "semver patch: +0.0.1" 고정이라 적었으나 **실제 이력과 어긋났다** (2026-08-20 실측 정정)
2. `.claude-plugin/marketplace.json` version bump (동일 버전)
3. 발행 전 검사 — 릴리즈 노트를 누수 규칙 정본으로 본다: `python3 scripts/leak_rules.py --text-file docs/releases/vX.Y.Z.md --rules <비공개 규칙 파일>` 이 exit 0 이어야 한다. 1(적중) · 2(판정 불가 — 통과 아님)면 노트를 고치거나 원인을 없앤 뒤 다시 돌린다. 비공개 규칙 파일은 공개 트리 밖에 두고, 없으면 빈 파일을 준다(내장 규칙만)
4. `git commit` 뒤 출하 게이트 `bash scripts/check_release_sync.sh --release --rules <비공개 규칙 파일>` 이 exit 0 이어야 한다 — `--release` 는 비공개 규칙 파일을 명시로 요구한다(env · 유지관리자 표지로 추정하지 않는다). 그다음 `git push origin main`
5. `git tag vX.Y.Z` + `git push origin vX.Y.Z` — ⛔ 이번 판 태그 하나만 올린다. 로컬 태그를 한꺼번에 올리는 push(`--tags`)는 쓰지 않는다 — 원격에서 지운 옛 태그가 로컬에 남아 있으면 그 push 로 되살아난다
6. (선택) 발행: `gh release create vX.Y.Z --notes-file docs/releases/vX.Y.Z.md` — 본문은 3 에서 검사한 노트 파일로만 올린다
   - ⛔ 본문을 짓는 발행 옵션(`--generate-notes` · `--notes-from-tag`)은 쓰지 않는다 — 본문이 노트 파일이 아니라 커밋 메시지 · 태그 주석에서 와 3 의 검사를 거치지 않는다
7. 발행했으면 발행 뒤 검사 — 실제로 올라간 제목 · 본문을 같은 규칙으로 다시 본다: `python3 scripts/leak_rules.py --release-body vX.Y.Z --rules <비공개 규칙 파일>` 이 exit 0 이어야 한다. 1 이면 발행된 제목 · 본문을 노트 파일 내용으로 바로잡고(노트 파일을 고쳤으면 3 부터) 다시 돌린다. 2(gh 부재 · 인증 만료 · 오프라인 · 그 태그의 릴리스 없음 · 빈 본문)는 통과가 아니다 — 원인을 고쳐 다시 돌린다
8. ⛔ 릴리즈 노트·CHANGELOG 는 **마지막 게이트(`check_release_sync.sh --release` — ④ 가 health-check 전체를 안에서 돈다 · 따로 돌린 health-check 는 게이트가 아니다) 뒤에 고치지 않는다** — 고쳤으면 발행 전 검사(3)와 게이트(4)를 다시 돌린 뒤 발행한다. 노트의 검증 수치는 마지막 재실행 출력에서 옮긴다 (F-311: 게이트 뒤에 노트를 줄여 템플릿 게이트가 깨진 채 발행됐다)
   - ⛔ **finding 닫기**: 노트 `Closes:` 작성 → `python3 scripts/check_release_closes.py --findings-root <레지스트리> --note docs/releases/vX.Y.Z.md` exit 0(레지스트리 `applied: full` 전부 · partial 금지 · `applied_ref` 실재 · 원장 미등재 트랙 D 는 `Track-D-Review:` 줄) → 태그 뒤 `python3 scripts/eject_findings.py --root <레지스트리> --note … --version vX.Y.Z` → `--audit <레지스트리>`. `check_release_sync.sh --release --rules <비공개 규칙 파일>` ⑥ 은 노트 선언(Closes 또는 '닫은 finding 없음')만 본다 (F-550: 고쳤는데 Closes 를 빠뜨렸다)
   - ⛔ **재작성 전 표시**: 엔트리 머리말 `applied_ref_era: pre-rewrite` 는 `applied_ref` 가 이력을 다시 쓰기 전의 커밋이라 이 저장소에 없을 수 있다는 표시다 — 그런 엔트리에만 단다. `check_release_closes.py` 는 표시가 있고 그 SHA 객체가 이 저장소에 없을 때만 실재 · 조상 검사를 건너뛰고 엔트리마다 `NOTE` 줄을 낸다. 객체가 있으면 표시가 있어도 그대로 검사하고 hex 형식 검사는 늘 한다. 값은 `pre-rewrite` 하나다(다른 값 · 빈 값은 (g) 위반)
9. ⛔ 다른 워크트리에서 출하했으면 **세션이 읽는 로드 체크아웃**(`--plugin-dir` 대상)을 태그로 옮기고 대조한다 — `git -C <로드 체크아웃> merge --ff-only vX.Y.Z` 다음 `python3 scripts/check_loaded_version.py --loaded-root <로드 체크아웃>` 이 `LOADED_OK` 여야 한다 (F-507: 로드 체크아웃을 안 옮겨 4일간 옛 판이 돌았다)

> **version bump 누락 시 `plugin update`가 "already at latest"로 스킵됨. 반드시 올릴 것.**

### 사용자 업데이트
```bash
claude plugin update fz@fz-orchestrator
```

### Pre-commit Hooks (H1 원칙 — deterministic check)

본 repo는 `.githooks/pre-commit`으로 공개 저장소에 두면 안 되는 식별자(개인 경로 · 메일 · 티켓 키 · PR 번호 · 비공개 이름)의 commit을 차단한다. 판정은 누수 규칙 정본 `scripts/leak_rules.py --staged --hook-policy` 가 하고, 훅은 정본을 훅 위치 기준(`.githooks/` 의 상위 트리)으로 찾아 한 번 부른다 — 정본이나 python3 가 없으면 배선이 끊긴 것이라 막는다. 버전 선언 3곳 동기(`scripts/check_release_sync.sh --staged`)도 함께 본다.

**최초 1회 등록**:
```bash
bash scripts/setup-hooks.sh
```

이 명령은 `git config core.hooksPath .githooks`를 설정하여 hook이 활성화된다. clone 후 사용자마다 1회 실행 필요.
격리 clone(커밋을 나눠 하나씩 검증하는 별도 작업 사본)은 `scripts/isolated_clone.sh <원본> <대상>` 으로 만든다 — 태그 없이 clone 하고 원본 로컬의 커밋 신원 · 유지관리자 설정(아래 **비공개 규칙 파일** 의 두 키 `fz.maintainer` · `fz.neutralizeRules`)을 옮기고 훅 경로(`core.hooksPath`)를 걸어 위 1회 등록을 대신하며, 원본 로컬 메일이 없거나 신원 정책(메일은 noreply 만 통과)을 통과하지 못하면 만들지 않는다(exit 2).

**검사 범위**: 모든 파일 — 예외 없음(CHANGELOG.md · docs/releases/ · `experiment-log.md` · 승격 원장도 검사한다). 인덱스가 HEAD 에 더한 줄과 새로 생긴 파일의 경로 이름(윗폴더 포함)만 본다 — 기존 잔존 reference 와 작업 트리에만 있는 줄은 보지 않고, 개명은 옛 경로와 짝지어 실제로 더한 줄과 새 이름만 본다
**검사 축**: 개인 홈 경로 · 개인 작업 폴더 경로 · 허용 밖 메일 · 티켓 키 꼴 · PR 번호 꼴 · 예약 번호 밖 자리표시자 · 합성 목록 밖 워크플로 실행 ID · 비공개 규칙. 자리표시 경로(정본의 `DOC_HOME_NAMES` · `DOC_DEV_NAMES`) · 예약 번호(0 으로 시작하는 3~5자리)를 쓴 자리표시자 · 합성 실행 ID(정본의 `SYNTHETIC_RUN_IDS`)는 통과한다 — 실제 실행 ID 는 줄여 적은 것도 그 목록의 값으로 바꾼다
**비공개 규칙 파일**: env `FZ_NEUTRALIZE_RULES` > git 설정 `fz.neutralizeRules` 순으로 찾는다. 없을 때(규칙 파일이 비어 규칙이 0개일 때도) 유지관리자 표지(git 설정 `fz.maintainer=true`)가 있으면 미판정으로 막고, 표지가 없으면(공개 기여자) 내장 규칙만 보고 안내 한 줄을 낸다. 경로를 줬는데 읽지 못하면 미판정이다. 표지 값이 참 거짓으로 읽히지 않을 때도 미판정이다 — 표지는 읽어야 할 때만 읽는다(규칙 파일을 찾지 못했거나 규칙이 0개일 때 · push 훅의 신원 검사). 두 키는 git 설정의 어느 범위에서든 읽는다 — 저장소 로컬 설정은 그 체크아웃에만 있으므로, 다른 체크아웃 · clone 에서 커밋하면 그곳에도 두 키가 있어야 한다(`git config --global` 또는 그 clone 의 로컬 설정)
**미판정은 막는다**: 바이너리 파일(추가 · 수정 · 삭제 모두 — git 이 바이너리로 본 변경) · UTF-8 이 아닌 줄 · git 실패(변경 목록 · 추가 줄 추출)는 텍스트 규칙으로 판정할 수 없어 커밋을 막는다 — 필요하면 아래 우회를 쓴다

**Bypass** (정당 사유 시): `git commit --no-verify` (권장 안 함, commit message에 사유 명시). 커밋 훅 전체(누수 검사 · 버전 동기)를 건너뛴다 — 그 커밋은 push 훅이 내보낼 때, 출하 게이트(`scripts/check_release_sync.sh --release`)가 출하 범위(직전 출하 태그 뒤 HEAD 까지)에 들 때 같은 정본으로 다시 본다. 두 관문을 모두 지나지 않는 경로(훅 없는 push)에서는 다시 보지 않는다

**근거**: v4.5.0 release 시 README/CHANGELOG/SKILL에 user-specific 절대 경로 노출 → v4.5.1로 retroactive cleanup 후 재발 방지 mechanism 추가 (v4.6.0).

**push 훅**(`.githooks/pre-push` — 위 `bash scripts/setup-hooks.sh` 등록으로 함께 켜진다): 갱신하는 ref 마다 원격에 없는 커밋 하나하나의 신원(author · committer) · 메시지 · 그 밖의 머리 · 추가 줄(첫 부모 대비)을, 태그 ref 면 tagger · 주석 · 태그 이름도, 그리고 목적지 ref 이름을 같은 정본(`scripts/leak_rules.py --commits --hook-policy`)으로 본다. 범위는 로컬 sha 에서 닿는 커밋에서, push 가 가는 URL 에 `git ls-remote` 로 얻은 원격 tip 가운데 로컬에서 커밋으로 풀리는 것에서 닿는 커밋을 뺀 것이다 — 낡을 수 있는 추적 ref(`origin/*`)는 쓰지 않고, 풀리지 않는 tip 은 빼지 않는다(그 ref 는 닿는 커밋 전부를 본다). 삭제는 건너뛰고, ls-remote · git 실패와 정본의 판정 불가(graft 파일이 있는 저장소 포함)는 막는다. replace ref 는 따르지 않는다(원본 객체를 읽는다). 신원 메일 규칙(noreply 만 통과)은 유지관리자 표지(`fz.maintainer=true`)가 있을 때만 켠다 — 공개 기여자의 개인 메일은 막지 않는다. 비공개 규칙은 표지와 무관하게 신원 칸(author · committer · tagger 의 이름 · 메일)에도 걸고, 메시지 · 머리 · 추가 줄 · 태그 주석은 누구에게나 본다. 비공개 규칙 파일을 찾는 순서와 표지가 있는데 규칙 파일이 없을 때 막는 것은 커밋 훅과 같다 — 표지가 없는 다른 체크아웃 · clone 에서 push 하면 신원 메일 규칙이 꺼진다(안내 한 줄이 나온다 · 그곳에도 두 키를 둔다). 우회(`git push --no-verify`)하면 이 검사는 다시 돌지 않는다 — 출하 게이트(`scripts/check_release_sync.sh --release` — 신원 축은 표지와 무관하게 언제나 엄격하다)는 출하 범위(직전 출하 태그 뒤 HEAD 까지의 커밋)와 로컬 태그만 다시 본다. 출하하지 않는 브랜치를 우회해 밀면 어느 검사도 보지 않는다

## Directory Structure
> ⛔ 아래 카운트는 `scripts/lint_contracts.py` **#N2가 실측과 대조**한다 — 손으로 세지 말고 lint를 돌려라 (2026-08-09까지 modules 20/guides 7로 stale했다).
> ⛔ **형식 고정**: `` - `dir/` — 설명 (N개) `` — #N2는 백틱 경로 뒤의 `(N개` 를 찾는다. 형식이 다르면 **그 카테고리가 조용히 검사에서 빠진다** (2026-08-09 감사 ISSUE-002: `agents/`는 괄호 없어 미검사, `workflows/`는 선언 자체가 없었다).
- `skills/` — fz 스킬 SKILL.md (22개)
- `agents/` — fz 에이전트 (15개)
- `modules/` — 공유 모듈 (50개). ⛔ **실행 절차만** 둔다 — 라운드 의미론의 *역사적 출처*(TEAM 사료 6종)는 2026-09-21 `docs/history/` 로 옮겼다가(B9/S13) 2026-09-25 삭제했다(결정: `modules/promotion-ledger.md` § TEAM 일몰). 사료를 실행 절차와 같은 자리에 두면 읽는 사람이 절차로 오독한다
- `guides/` — 가이드 문서 (9개)
- `workflows/` — 결정적 멀티에이전트 스크립트 (8개)
- `templates/` — 스킬/에이전트/모듈/CLAUDE.md 템플릿
- `gpt-skills/` — GPT 네이티브 스킬 (8개)
- `schemas/` — JSON 스키마 (8개 — GPT 응답 7 · Issue Tracker 1) + `tool-inventory.json`
- `scripts/` — lint·설치·호출·검증·계측 스크립트 (110개). ⛔ diff 라인 접두사(`+`/`-`)로 판정하는 새 파일은 `# diff-parse: hunk-state | not-a-diff | waived` 선언 1줄이 없으면 `health-check` 가 막는다 (`lint_diff_parsers.py` — hunk 안팎에서 접두사 뜻이 달라 같은 결함이 4회 재발했다). ⛔ `setup-gpt-skills.sh` 는 `${CODEX_HOME:-~/.codex}/skills/` 에 GPT 역할 스킬 심볼릭(Tier 2a)을 만든다 — 디스커버리의 필수 조건은 아니다(미실행이어도 resolver `gpt_kinds.py` 가 자기 위치의 번들 본문(Tier 2b)을 돌려준다 · `modules/cross-validation.md` § 역할 스킬 경로). ⛔ gpt 호출은 정문 `scripts/gpt-call.sh <kind>` 경유 의무 — 래퍼 `gpt-exec.sh` · 런처 `gpt_independent.sh` 는 그 어댑터다(`modules/fz-gpt-bash-hygiene.md` §8 · 레지스트리 `scripts/gpt-kinds.json`) · `FZ_PLUGIN_ROOT`는 `resolve-plugin-root.sh`로 해석 (호출부가 정문을 찾는 경로)
- `.claude-plugin/` — plugin.json + marketplace.json
- `mods/` — 선택형 하위 플러그인 둘. 설치는 각각 따로 한다(marketplace 둘째 · 셋째 항목). 루트 `hooks/hooks.json` 은 command 훅만 싣는다 — 최상위 키는 `hooks` 하나이고, 지금 항목은 본체의 감사 전용 Stop 하나(`gate_stop_hook.py --audit-only`)다. `modules` 키와 hooks 모듈은 루트에 두지 않고 `mods/` 하위 플러그인에 둔다(`gate_stop_hook.py --self-test` 의 `plugin-hook-registration` 셀이 최상위 키를 본다). 근거: Claude Code CHANGELOG 에서 플러그인의 command 훅은 플러그인이 처음 나온 2.0.12 부터 있고, hooks 모듈은 2.1.287 에 처음 나온다(외부 문서 — `anthropics/claude-code` 저장소의 `CHANGELOG.md`, 2026-11-18 읽음). 루트 `hooks/` 를 통째로 금하던 옛 문장('옛 CLI 가 fz 본체까지 거부할 수 있다')은 `modules` 키를 가진 `mods/fz-compact` 를 들일 때 함께 들어왔고 저장소에 다른 사유는 적혀 있지 않다 — 그 경고가 `modules` 키를 가진 파일을 두고 한 말이라는 것은 추론이다. 옛 CLI 에서 실제로 돌려 보지는 않았다 `[미검증]`. health-check 5.1 · 5.2 가 검증하고, `mods/*/` 이름이 모두 health-check 에 있는지도 본다
  - `fz-compact` — bg 세션의 로컬 마스킹 압축 · 기본 꺼짐. `/plugin install fz-compact@fz-orchestrator`. 검증: `bash scripts/plugin_validate.sh mods/fz-compact` · `claude plugin test mods/fz-compact`
  - `fz-guard` — Phase 4 승인 전 쓰기 · 쓰는 Bash deny(P4) · fz 세션의 ad-hoc Agent 경고(AG) · 메모리에만 쓴 fz 교훈의 Stop block(FR — `FZ_FINDINGS_ROOT` 설정 시) · GPT 리뷰 없는 fz-review 턴의 Stop block과 옛 모델 호칭 쓰기 deny(GP). classic command 훅 넷 · 오류는 전부 fail-open. 설치: `/plugin install fz-guard@fz-orchestrator` 또는 `claude --plugin-dir mods/fz-guard`. 상태 `${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/<session_id>.json`(언인스톨해도 남는다 — 손으로 지운다). 끄기: env `FZ_GUARD_DISABLE=P4,AG,FR|all` 또는 파일 `${FZ_RUN_STATE:-~/.fz/runs}/fz-guard/disable`(재시작 불필요). 검증: `python3 mods/fz-guard/hooks/guard.py --self-test` · 상세 `mods/fz-guard/CLAUDE.md`

## Verification Discipline (v3.11+)

모든 스킬/에이전트는 다음 규약을 따른다 — 셋째 줄(T6/T7)은 Lead 가 세션에서 따르는 규약이라 에이전트 본문과 두 템플릿에는 싣지 않는다:

- 사실 주장 전 `[verified: source]` 또는 `[미검증: 이유]` 태그 필수
- 외부 모델 판정 인용 시 원문 + `[외부: name]` 태그 (재포장·재수치화 금지)
- T6/T7 트리거 발동 시 `git show`/`Read`/`grep` 실측 후 계속

상세: `modules/uncertainty-verification.md` (Default-Deny), `modules/system-reminders.md` (T6/T7), `modules/lead-reasoning.md §1.5` (Speculation-to-Fact Fallacy), `templates/agent-template.md` + `templates/skill-template.md` (자동 상속 섹션 — 앞 두 줄).

## Opus 5.5 Adaptation (현행 기본 모델)

- **GA**: 2026-09-22, `claude-opus-5-5`. **$4/$20**(캐시 읽기 $0.20) — Opus 5($5/$25)보다 낮다 [verified: platform.claude.com/docs/en/models/opus-5-5/whats-new-opus-5-5]
- **Tokenizer**: Opus 4.7 도입분을 Opus 5.5 도 쓴다 — *"Claude Opus 4.7 introduced a new tokenizer, which later Opus models, including Claude Opus 5.5, also use."* [verified: platform.claude.com/docs/en/models/opus-5-5/migration-guide 2026-11-16] → 4.7/4.8 대비 토큰 수 거의 불변. (pre-4.7 대비 1.00-1.35x 증가는 유지, fz 자체 실측 미완료)
- **Breaking 4** (정본 `guides/llm-references.md` whats-new-opus-5-5 행): ① **thinking 상시 ON — 끄기 불가**: `thinking:{"type":"disabled"}`·manual `budget_tokens` 는 effort 와 무관하게 **400** (Opus 5 는 effort ≤ `high` 에서 끌 수 있었다) — `max_tokens`는 thinking+응답 **합산** 하드캡이라 타이트한 값은 **응답 절단** 위험 ② forced `tool_choice`(`any`·`tool`) → **400** — `auto` + strict tool use 또는 structured outputs 로 대체 ③ thinking block 이 모델·대화 prefix 에 묶인다(prefix 를 바꿔 재생하면 400) ④ `computer_20251124` 거부. 동작 변화: 도구 호출 사이 진행 텍스트가 `text` 가 아니라 **progress-update `thinking` 블록**으로 온다 — 기본 `display: "omitted"` 에서는 스트리밍 UI 가 조용해진다 [verified: whats-new-opus-5-5]
- **effort**: 기본 **`medium`**(Opus 5 는 `high`) + **같은 effort 에서 사고량 증가**(`xhigh`·`max` 에서 가장 크다) [verified: whats-new-opus-5-5]. 공식은 이전 모델 값 재사용 대신 **fresh sweep** 을 권한다 — fz 는 워커 effort = Lead 세션 effort 를 워크플로 args 로 명시 전달한다(사용자 결정 2026-10-19 · 미지정이면 `xhigh` — `modules/mode-gate.md` § effort · 이전: 2026-09-25 `xhigh` 고정) [verified: platform.claude.com/docs/en/build-with-claude/effort]
- **Behavior** [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5]: **자체검증 내장 → 검증 지시 삭제**(over-verification) / **subagent 위임 과다 → 캡**(4.8과 역방향) / 응답·산출물 장문화 → **길이는 프롬프트로**(effort로 안 됨) / 스코프 확장·자기정정 서술 과다 → 명시 제약
- **Behavior (5.5 — 위 Opus 5 패턴 상속)**: "Existing Claude Opus 5 prompts should perform well without changes, and the patterns in Prompting Claude Opus 5 remain a reasonable starting point." 보강 3가지: **elapsed 시간 신호**(매 메시지 끝에 경과 시간 1줄) / text-only 턴 종료는 완료 증거가 아니라 **보고** / **premature stopping** 대응 자동 continuation 은 같은 작업에 **2~3회 상한** [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5]. ⛔ 5.5 페이지에 subagent 캡 절이 없는 것은 위 캡의 폐기 근거가 아니다(상속)
- **Context window**: 1M 유지 (기본값이자 최대값). safety net 원칙, Intelligence Degradation + Context Length Hurts 논문 근거

상세: `guides/llm-references.md` §1.2·§5 (정본), `modules/context-artifacts.md` (1M context 정책), `guides/harness-engineering.md` §1.3 (세대 전환 테이블), `guides/prompt-optimization.md` 원칙 8 (literal interpretation 대응), `guides/model-guide.md` (Fable 5 대비).

## Agent Teams Environment Flag — ⛔ 현행 경로에 불필요 (역사적 기록)

⛔ **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`을 설정하지 말 것.** 이 플래그는 `TeamCreate` 경로 전용이고, **`TeamCreate`는 Claude Code v2.1.178부터 부재**하다. 멀티에이전트 실행은 v4.22.0(Wave 4)에서 `workflows/*.js` 결정적 Workflow로 전면 이관됐다 — Workflow 도구는 이 플래그를 요구하지 않는다.

- 팀 모드 정본: `guides/skill-authoring.md` §12 (Workflow 규약 + 실패 복구 사다리 L1~L4)
- 역사적 사양(TEAM P2P 시절): `guides/agent-team-guide.md` §8 — ⛔ 실행 절차로 참조하지 않는다

> 정정 근거(2026-08-09 외부 감사 ISSUE-011): 본 절이 "설정 필수"라 지시하는 동안 같은 리포가 `TeamCreate` 부재를 선언하고 있었다 — **런타임 진입 문서가 존재하지 않는 실행 경로를 활성화하라고 지시**하는 모순이었다.
