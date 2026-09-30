# GPT 실행 전략

> **Sources (last audited: 2026-09-21 — **인용 정합 축**(arxiv ID 형식 56종 이상 0 · 교차 파일 주장 일치 · 레지스트리 등재)):** `learn.chatgpt.com/docs/changelog` (구 `developers.openai.com` 308 리다이렉트 명시). ⛔ **원문 재조회는 포함하지 않았다** — 외부 페이지가 바뀌었는지는 이 감사의 범위 밖이다.

> fz-gpt SKILL.md 서브커맨드에서 참조. 공통 설정 (Base Branch / 모델·effort 선택 / Diff 크기 / CLI 모드).

> **Authority Sources** (Cgap-1 보강, 2026-05-16):
> - **Cross-model 검증 근거**: Anthropic "Harness Design for Long-Running Apps" (2026-03) [verified: A2] — "Self-evaluation is unreliable" → cross-model verify
> - **Diff 크기 정책**: Context Rot (Chroma Research, 18 frontier models) [verified: empirical study] — focused 300 tokens > unfocused 113K tokens. Small (<2000) full diff / Medium (2000-8000) file-split / Large (>8000) key files + summary
> - **CLI 버전**: GPT CLI Changelog [verified: official] — gpt-5.5 (0.124.0+) · gpt-6-astra (0.153.1+, 0.153.4에서 bundled default) · gpt-6-sol (0.156.1 모델 선택기 추가 · 0.157.0 정식 추가 · bundled default, medium) · **gpt-6.1-sol (0.159.0 추가 · 0.159.1 bundled default, medium)**. ⚠️ 실제 모델은 세션 선택(없으면 `config.toml`)과 CLI 버전에 따른다 — 호출 문서는 모델을 적지 않는다(§ 모델·effort 선택)
>   출처: https://learn.chatgpt.com/docs/changelog (구 `developers.openai.com/codex/changelog` 는 여기로 308)

## 목차

- [Base Branch 결정](#base-branch-결정)
- [모델·effort 선택 (세션 1회)](#모델effort-선택-세션-1회)
- [Diff 크기 적응 전략](#diff-크기-적응-전략)
- [장기 불능 인지 (기간 조건부)](#장기-불능-인지-기간-조건부)
- [CLI 모드 선택 전략](#cli-모드-선택-전략)
- [Sandbox Permissions](#sandbox-permissions)
- [GPT Preamble 표준 (Cnew-3, 2026-05-16)](#gpt-preamble-표준-cnew-3-2026-05-16)

---

## Base Branch 결정

review, final 서브커맨드에서 `--base` 브랜치가 필요합니다.

**자동 결정 로직**:
1. 인자로 `--base <branch>` 명시 시 → 해당 브랜치
2. 현재 브랜치가 `feature/*` → `--base develop`
3. 현재 브랜치가 `hotfix/*` → `--base main`
4. 그 외 → `AskUserQuestion`으로 사용자에게 확인

## 모델·effort 선택 (세션 1회)

> 이 절이 정본이다 — 호출 문서(스킬 · 모듈 스니펫)는 모델·effort 를 적지 않고 이 절을 가리킨다. 구현: `scripts/gpt-choice.sh`(options · get · set · config) · `scripts/gpt-exec.sh`(사전 게이트 2.5 — 결정) · `scripts/gpt_independent.sh`(런처 전달).

**원칙**: 세션에서 GPT 를 처음 부르기 전에 모델과 effort 를 **한 번** 묻고, 그 값이 그 세션의 모든 GPT 호출(래퍼 · 독립 런처 · resume)에 적용된다. ⛔ 서브커맨드별 effort 는 없다 — 호출 종류에 따라 effort 를 올리거나 내리지 않는다. 묻지 않았으면 `config.toml` 그대로다(래퍼가 모델·effort 를 넘기지 않는다).

GPT 교차 검증 자체는 **명시 호출**이다 — 자동 경량 게이트는 없다(Review Gate OFF — 품질 ROI 가 낮다).

### 결정 순서 (래퍼 한 곳)

필드(모델 · effort)마다 **호출 플래그(`--model` · `--effort`) > 세션 선택(`gpt-choice.sh get`) > `config.toml`** 이다. 값 `config` 는 그 필드를 넘기지 않는다는 뜻이다. 넘길 때는 exec · review · resume 모두 `-c 'model="<slug>"'` · `-c model_reasoning_effort=<level>` 이다. review 모드는 `-c 'review_model="<slug>"'` 도 함께 넘긴다 — CLI 는 config 에 `review_model` 이 있으면 review 에서 그것을 `model` 보다 먼저 쓴다(선택이 없으면 그 config 값 그대로다 — `GPT-CHOICE` 는 `model` 값을 보인다).

적용값과 출처는 CLI 호출 직전 stderr 한 줄로 늘 보인다.

```
GPT-CHOICE model=<값> (flag|session|config) effort=<값> (flag|session|config)
```

- 출처가 `config` 인 필드의 값은 `config.toml` 최상위(첫 표 앞) 값이다 — `gpt-choice.sh config` 로 읽고, 모르면 `?` 다. 래퍼는 CLI 와 같은 `CODEX_HOME` 을 읽으므로 격리 런처에서도 실제로 쓰일 config 다
- 독립 런처는 래퍼의 이 줄을 자기 stderr 로 한 줄 옮긴다 — 래퍼가 그 줄 전에 멈추면 없다
- ⛔ 래퍼가 세션 선택을 읽지 못하면 config 로 가지 않고 exit 11 로 멈춘다. 처방은 메시지 머리의 태그로 가른다(문서는 태그를 인용한다)
  - `CHOICE-UNREADABLE` — 선택 파일 손상(`get` exit 11): Lead 는 다시 묻고 `gpt-choice.sh set` 으로 덮어쓴다
  - `CHOICE-SCRIPT-ERROR` — 스크립트 부재·오류 · `get` 출력과 래퍼 규칙의 불일치: 다시 물어도 풀리지 않는다 — 묻지 않는다
  - **우회**: 덮어쓰기가 안 되거나(`set` 실패) 스크립트 오류면 이 세션의 GPT 호출에 `--model config --effort config` 를 붙이고 알린다 — 두 필드가 모두 플래그면 래퍼는 선택 파일을 읽지 않고 config 로 돈다

### 묻는 시점

- **`/fz`**: Phase 4 AskUserQuestion 에 합친다 — `skills/fz/SKILL.md` Phase 4 가 이 절을 가리킨다. 확정 파이프라인에 GPT 를 부를 수 있는 스킬이 하나라도 있으면 묻는다. 모르면 묻는다 — 놓쳐도 최악은 스킬 단계에서 한 번 더 묻는 것이다
- **개별 스킬 직접 호출**: 그 세션의 **가장 이른 GPT 호출** 직전에 선택이 있는지 본다 — background 독립 런처 · sprint contract 도 GPT 호출이다

```bash
bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" get   # exit 로 분기한다 — 아래 표
```

| `get` 결과 | 뜻 | Lead |
|---|---|---|
| exit 0 | 선택 있음 — stdout `model=… effort=…` | 묻지 않는다(이미 선택 — 래퍼가 적용한다) |
| exit 3 | 선택 없음 | AskUserQuestion(아래 질문 형식) 후 `set` |
| exit 4 | 선택 없음 + 자율 모드(`FZ_AUTONOMY`) | 묻지 않는다 — config |
| exit 5 | 저장할 수 없는 세션 — 세션 id 없음·불량 · 저장 위치를 정할 수 없음 · `FZ_GPT_CHOICE_DIR` 가 절대 경로가 아님(stderr 안내) | 묻지 않는다 — config |
| exit 11 | 선택 파일 손상 | 다시 묻고 `set` 으로 덮어쓴다 |
| 도구 호출 거부(권한 — exit 없음) · 그 밖의 exit(1 · 126 · 127 등 — `FZ_PLUGIN_ROOT` 경로 오류일 수 있다) | 판독 불가 | 묻지 않고 진행하며 알린다 — 래퍼는 자기 위치로 따로 판독한다(선택이 없으면 config). 래퍼가 `CHOICE-SCRIPT-ERROR` 로 멈추면 위 **우회**를 따른다 |

### 질문 형식

```bash
bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" options
```

`gpt-choice.sh options` 의 stdout JSON 에서 `questions.model` · `questions.effort` 로 AskUserQuestion 을 만든다 — 각각 `choices[]`(`id` · `label`) · `skip` · `more[]` 다. `choices[].id` 가 `set` 에 넘길 값이다.

- **모델 질문**: `config 기본 (<config 모델>)` (Recommended) + 목록 모델 최대 3 — `choices` 그대로다
- **effort 질문**: `config 기본 (<config effort>)` + 최대 3 — `choices` 그대로다. 명시 수준은 지원 목록을 아는 제시 모델 모두가 지원하는 수준만 나온다. 모델 선택지 label 에 `effort 는 config 만` 이 붙은 모델(지원 effort 를 모름 — config 모델을 모르는 경우 포함)을 고르면 effort 는 `config` 로 `set` 한다(명시 effort 와 짝지으면 `set` 이 exit 10). max · ultra 는 독립 런처 1800초 상한(exit 16)에 걸릴 수 있다고 설명에 적는다
- `skip` 이 참인 질문(선택지 2개 미만)은 뺀다. 뺀 질문의 필드는 `config` 로 `set` 한다 — `set` 은 `--model` · `--effort` 가 모두 필요하고, 하나만 넘기면 사용법 오류(exit 10)라 아래 '다시 묻기' 대상이 아니다. 두 질문이 모두 빠지면 묻지 않고 `set --model config --effort config`
- `more` 는 질문 설명에 적는다 — 사용자는 Other 로 입력할 수 있고, Other 입력은 `set` 이 검증한다
- ⛔ 호출 문서 · 질문 예시에 모델 이름을 적지 않는다 — 자리표시자 `<slug>` · `<level>` 만 쓴다(Authority 의 CLI 버전 이력은 예외)
- `/fz` Phase 4 에 합칠 때 질문 합계가 4(AskUserQuestion 한 번의 상한)를 넘으면 GPT 두 질문을 바로 다음 AskUserQuestion 한 번으로 나눈다 — 왕복이 1 늘어난다

### 기록

```bash
bash "${FZ_PLUGIN_ROOT}/scripts/gpt-choice.sh" set --model "$MODEL_ID" --effort "$EFFORT_ID"   # 각각 options 의 choices[].id(<slug> · <level>) 또는 config
```

| 결과 | Lead |
|---|---|
| `set` exit 0 — 기록됨(stdout `model=… effort=…`) | 이후 GPT 호출에서 다시 묻지 않는다 |
| `set` exit 10 — 목록 밖 모델 · 그 모델이 지원하지 않는 effort(effort 가 config 면 config effort) · 지원 목록을 모름(파일을 쓰지 않는다) | 그 질문만 1회 다시 묻는다. 또 실패하면 `set --model config --effort config` 후 "config 로 진행" 을 알린다 |
| `set` exit 11 — 사전조건(세션 id · 저장 위치 · 모델 목록 캐시 없음 · 쓰기 실패) | 기록되지 않는다 — 이전 선택 파일이 있으면 그대로 남아 래퍼가 계속 읽는다(손상이면 계속 exit 11). 결정 순서의 **우회**(이 세션의 GPT 호출에 `--model config --effort config`)로 진행하고, 이 세션에서는 다시 묻지 않는다 · 알린다 |
| `set` · `options` 그 밖의 exit(1 · 126 · 127 등 — 스크립트 오류·경로 오류) | 같은 **우회**로 진행하고 알린다 |
| `options` exit 11 — 모델 목록 캐시 없음·판독 불가 | 묻지 않고 `set --model config --effort config` 후 "모델 목록을 읽지 못해 config 로 진행" 을 알린다 |
| 저장 선택으로 부른 GPT 호출(`GPT-CHOICE` 출처 session)이 exit 12 이고 스트림 로그(`<out>.stream.log`)에 모델·effort 거부 흔적이 있다 | 선택을 다시 묻는다. 그 밖의 exit 12(quota · 네트워크 · 인증)는 선택 탓이 아니다 — 호출부의 GPT 실패 규칙을 따른다(§ 장기 불능 인지) |

`set --model config --effort config` 는 모델 목록 캐시와 config 를 읽지 않아 캐시가 없어도 기록된다 — "물었고 config" 를 남겨 스킬마다 다시 묻지 않게 한다.

### 저장

`${FZ_GPT_CHOICE_DIR:-$HOME/.fz/gpt-choice}/${CLAUDE_CODE_SESSION_ID}` — 두 줄(`model=<slug|config>` · `effort=<level|config>`)이다. `set` 이 tmp+mv 로 원자 기록한다.

- Claude Code `--resume` 은 같은 세션 id 를 유지한다(2026-09-30 실측: transcript `sessionId` 동일) → 선택이 유지된다
- `/clear` 뒤 id 가 바뀌는지는 [미검증] — 바뀌면 다시 묻는 것이 정상이다
- 파일은 정리하지 않는다(세션당 수십 바이트)

### 세션 중 변경

사용자가 GPT 모델·effort 를 바꾸자고 하면 다시 묻고(위 질문 형식) `set` 으로 덮어쓴다. 다음 GPT 호출부터 새 값이다.

### 자율 모드

`FZ_AUTONOMY=autonomous` 면 `get` 이 선택 없음을 exit 4 로 알린다 — 묻지 않고 config 다. 판정은 `scripts/autonomy_decide.py` 가 한다(공백·대소문자를 정규화하고 모르는 값은 묻기로 본다). ⛔ 선택 파일이 있으면 자율이어도 적용된다(exit 0) — A/B 러너는 run 마다 새 세션 id 라 파일이 없다.

### resume

같은 결정 순서다 — 선택을 바꾼 뒤의 resume 은 새 값으로 돈다. 원래 모델로 이으려면 `--model` · `--effort` 플래그로 고정한다. 다른 모델로의 resume 을 CLI 가 거부하면 exit 12 로 드러난다 [미검증: 실제 CLI 스모크 전]. 독립 플래너 세션을 잇는 resume 교차(`modules/fz-gpt-subcommands-core.md` § verify)는 `CODEX_HOME` 만 격리 홈으로 바꾸므로 실제 홈의 세션 선택을 읽는다.

### 독립 런처

`gpt_independent.sh` 도 기본값 없이 같은 규칙이다 — `--model` · `--effort` 는 주어졌을 때만 래퍼로 넘긴다(보통 넘기지 않는다). 래퍼는 가짜 HOME 으로 뜬다.

- `FZ_GPT_CHOICE_DIR` 를 실제 홈 기준(미설정이면 `<실제 홈>/.fz/gpt-choice`)으로 넘긴다 — Lead 세션 선택이 격리 팔에도 닿는다. 세션 id 는 env 가 물려준다. 상대 경로 값은 바꾸지 않고 넘긴다(`get` exit 5 → config)
- 격리 config 에 실제 config 최상위 `model` · `model_reasoning_effort` 두 줄을 옮긴다 — 선택이 없으면 격리 팔도 사용자 config 로 돈다
- 런처 exit 10 · 11 · 12 는 래퍼 exit 를 그대로 낸 것일 수 있다 — 사유는 `<out-dir>/<arm>-<run-id>.wrapper.log` 에 있다. 세션 선택 판독 실패(11)면 런처 stderr 에 `GPT-CHOICE` 줄이 없고 `.wrapper.log` 에 `CHOICE-UNREADABLE` 또는 `CHOICE-SCRIPT-ERROR` 가 있다 — 위 결정 순서의 exit 11 규칙을 따른다. 12 는 기록 표의 exit 12 행을 따른다
- max · ultra 를 고르면 런처 `--timeout` 기본 1800초(exit 16)에 걸릴 수 있다 — 필요하면 `--timeout` 을 준다

### light 모드

fz-plan · fz-code · fz-review 의 light 모드는 GPT 를 부르지 않는다 — 질문도 없다.

### 긴 호출의 background 기준

effort 가 아니라 **입력 크기 · 호출 종류**로 정한다. 큰 입력(계획 300줄 이상 · 큰 diff)이나 독립 런처 · 심화 resume 처럼 오래 도는 호출은 `run_in_background` 로 띄운다(`modules/fz-gpt-bash-hygiene.md` §4). 세션 effort 가 높으면(max · ultra) 가벼운 호출도 길어질 수 있다.

## Diff 크기 적응 전략

diff 크기에 따라 GPT 호출 전략을 자동 선택합니다.

**크기 측정**:
```bash
# ⛔ 이전 판의 두 결함(F-216 N6): ① `--base` 는 git diff 의 유효 옵션이 아니다(명령이 실패하는데 $() 가 삼켰다)
#    ② `insertion` 만 추출해 **삭제 전용 diff 에서 빈 문자열**이 됐다 — "추가 1줄·삭제 9,000줄" 이 Small 로 분류됐다.
# ⛔ git 을 먼저 돌려 **종료 상태를 잡는다**. awk 로 파이프하면 END 가 입력이 비어도 0 을 찍어
#    git 실패가 "변경 0줄"(=Small)로 번역된다 — 가드가 구조적으로 발화하지 못한다.
DIFF_RAW=$(cd "$GIT_ROOT" && git diff --numstat "$BASE_BRANCH"...) \
  || { echo "⛔ git diff 실패 — base 브랜치·저장소 확인"; exit 1; }
[ -n "$DIFF_RAW" ] || { echo "⛔ diff 가 비었다 — 정말 변경 0건인지 base 를 확인한다"; exit 1; }
DIFF_LINES=$(printf '%s\n' "$DIFF_RAW" \
  | awk '{ a += ($1 == "-" ? 0 : $1); d += ($2 == "-" ? 0 : $2) } END { print a + d }')
```

| diff 크기 | 전략 | 실행 방법 |
|-----------|------|----------|
| **Small** (<2000줄) | Full diff → `gpt-exec.sh review` | config 모델의 대형 컨텍스트 활용, 구조화 전체 리뷰 (기본) |
| **Medium** (2000-8000줄) | File-split → `gpt-exec.sh exec` xN | 변경 파일을 기능 그룹으로 분할, 그룹별 독립 리뷰 |
| **Large** (>8000줄) | Key files + summary | 핵심 파일만 상세 리뷰 + 나머지 요약 |

**Medium 전략**: 변경 파일을 기능 그룹(Architecture/Data/UI)으로 분할 → 그룹별 `gpt-exec.sh exec` 독립 리뷰 → `jq`로 결과 합산.

**Large 전략**: 변경량 상위 10 파일만 상세 리뷰 + 나머지 요약.

**자동 전환 규칙**:
- `review`, `check`, `commit`: Small 전략 기본, Medium/Large 시 자동 전환
- `final`: 항상 최대 커버리지 (Medium→Full 시도, Large→Key files)
- `verify`, `validate`: diff 크기 무관 (프롬프트 기반)

## 장기 불능 인지 (기간 조건부)

> GPT가 **장기 불능** 상태(예: quota·spend cap — 표기할 때는 시작일과 원복 트리거를 함께 적는다)일 때: 서브커맨드 호출 전 재시도를 생략하고 각 스킬의 GPT 불능 분기(fz-review Phase 5 검증 2 불능 분기 등)로 직행한다 — 매 호출 재시도 1회 오버헤드 방지. ⛔ 상태 표기에는 시작일 + 원복 트리거 명시 의무(만료일 미상이면 "해제 확인 시 원복"으로) — 정리 주체 없는 무기한 잔존 방지. **해제 확인 시 이 노트의 "현재:" 상태 제거 + 원경로 복원** (동기화 단일 포인트: MEMORY.md GPT 줄). 이종 blind-spot 안전망 상실은 폴백 산출물에 명시 의무 (15/23차).

## CLI 모드 선택 전략

래퍼 review 모드(`gpt-exec.sh review`)가 git diff + 구조화 출력을 통합. 모든 서브커맨드가 래퍼(`scripts/gpt-exec.sh`) 한 경로로 동작한다.

| 기준 | `gpt-exec.sh review` | `gpt-exec.sh exec` |
|------|---------------------|-------------|
| **diff 입력** | Git 자동 감지 (--base/--uncommitted/--commit) | 수동 주입 (프롬프트에 인라인) |
| **출력 형식** | `--out`(최종 메시지 파일) | `--out` + `--schema` JSON 강제 |
| **모델·effort** | 세션 선택이 있으면 넘기고, 없으면 넘기지 않는다(config 그대로) — § 모델·effort 선택 | 동일 |
| **GPT 스킬** | 3-Tier 디스커버리 자동 트리거 | 스킬 내용 수동 주입 필요 |
| **모노레포 컨텍스트** | read-only 가 전 디스크 읽기 허용 — 별도 플래그 불필요 | 동일 (필요한 경로는 프롬프트에 적는다) |

**서브커맨드별 매핑**:

| 서브커맨드 | CLI 모드 | 이유 |
|-----------|----------|------|
| review | `gpt-exec.sh review` | Git diff + `--out` 구조화 캡처 + 스킬 자동 |
| check | `gpt-exec.sh review` | --uncommitted + `--out` |
| commit | `gpt-exec.sh review` | --commit + `--out` |
| final | `gpt-exec.sh review` | --base + `--out` + `resume --session-file` 심화 |
| verify | `gpt-exec.sh exec` | 계획 텍스트 + `--schema` JSON 필요 |
| validate | `gpt-exec.sh exec` | 이슈 목록 + `--schema` JSON 필요 |

**심화 패턴**: `gpt-exec.sh review`·`exec` 로 1차 리뷰 → `gpt-exec.sh resume --session-file {1차 --out}.session` 으로 특정 이슈 심화 검증. `final`에서 자동 적용. (세션 지정 이유: `modules/fz-gpt-bash-hygiene.md` §8)

## Sandbox Permissions

GPT CLI의 `sandbox_permissions` 설정 (역할별 의도):

| 권한 | 용도 | 사용 스킬 |
|------|------|----------|
| `disk-full-read-access` | 전체 코드베이스 읽기 (drift 스캔, 독립 플랜) | fz-drift, fz-planner |
| `read-only` (기본) | 변경 없이 읽기만 | fz-challenger, fz-searcher |
| (미지정) | GPT 기본 샌드박스 | fz-reviewer, fz-guardian, fz-fixer |

설정 위치: 래퍼 `scripts/gpt-exec.sh` 가 **모든** 호출에 `-c sandbox_mode="read-only"` 를 강제한다(session 층 — 사용자 `config.toml` 보다 우선). 위 표는 역할별 옛 설계 의도이며, 현행은 역할과 무관하게 전부 read-only 다. `sandbox_permissions=["disk-full-read-access"]` 도 함께 넘기지만 CLI 0.157 은 이 키를 **무시**한다고 출력한다(2026-09-25 실측).

> `disk-full-read-access`는 GPT가 프로젝트 디렉토리 전체를 읽을 수 있게 허용한다.
> 쓰기 권한은 부여하지 않으므로 코드 수정 위험 없음.

---

## GPT Preamble 표준 (Cnew-3, 2026-05-16)

> ⚠️ 이 표준은 GPT-5.5 시절(2026-05-16)에 세웠다. 현행 GPT-6 Sol 에서의 유효성은 미측정이다 [미검증: GPT-6 Sol 재측정 없음].

> **Authority**: GPT-5 Prompting Guide (OpenAI Cookbook 2026) [verified: official] — "rephrase goal → outline plan → narrate" preamble 패턴 권장.

GPT 호출 시 prompt 시작부에 다음 3단계 preamble을 포함하면 reasoning 품질 + 일관성 향상:

```
1. Rephrase Goal: 작업 목표를 자기 언어로 1-2문장 재기술
2. Outline Plan: 검증 단계 3-5개를 bullet로 outline
3. Narrate: 각 단계 실행 시 결과 narrate (verdict + reasoning)
```

**적용 위치**:
- `fz-gpt` SKILL.md verify/validate/plan 서브커맨드 prompt template
- GPT CLI 네이티브 스킬 (`${CODEX_HOME:-~/.codex}/skills/.system/openai-docs` 활용 가능)

**Few-shot 예시**:
```
BAD (preamble 없음):
"이 plan을 검증하라."

GOOD (3-step preamble):
"
[Rephrase] Plan v1을 GPT(현행 모델)로 cross-model verify. 5 Q 평가 + verdict.
[Outline] (a) 6 가설 grep 재현 (b) Tier 우선순위 평가 (c) false positive 식별 (d) GPT 단독 발견 (e) 최종 verdict.
[Narrate] 각 Q마다 verdict (pass/warn/fail) + reasoning + 파일:line 인용.
"
```

> GPT CLI 네이티브 `openai-docs` system skill로 OpenAI 공식 권장 패턴 추가 확인 가능.
