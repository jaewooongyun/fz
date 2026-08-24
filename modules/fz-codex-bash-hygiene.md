# fz-codex Bash 호출 Hygiene (29차/30차 교훈)

> **Scope of Applicability**: `fz-codex` SKILL.md의 모든 Bash 예시 (review/verify/validate/check/final/commit/adversarial/drift/plan/micro-eval). 다른 스킬은 본 모듈을 직접 참조하지 않으며, fz-codex 위임을 통해 간접 적용된다.
>
> **Purpose**: `codex exec` / `codex review`를 Bash 도구로 호출할 때 무한 hang / trusted directory 에러 / sandbox 무효화 / base mismatch 등을 방지하는 표준 절차.

## 목차

- §1 Stdin 닫기 의무 (`< /dev/null`) — hang 방지
- §2 Trusted Directory 확인 + Skip Flag
- §3 `-o` 파일 출력 시 stdout buffering
- §4 Background Task 의무 영역
- §5 ⛔ Trust Level 필수 (30차, Critical)
- §5.5 Base Verification Gate (git diff 분석 호출 시)
- §6 Standard Hygiene Wrapper Template (복붙용 — ⛔ §8 스크립트로 대체됨)
- §7 프롬프트 선두 하이픈 clap 오파싱 (`--` 구분자 필수)
- §8 ⛔ **`scripts/codex-exec.sh` 경유 의무** — 사전 플래그 게이트 + 사후 측정 게이트 (본 절이 정본 호출 경로)

## 1. Stdin 닫기 의무 (`< /dev/null`)

**증상**: Codex 0.124.0이 `Reading additional input from stdin...`에서 무한 대기. 13분 hang 후에도 응답 없음.

**원인**: Bash pipe에 codex exec를 연결하면 stdin이 열린 채 전달됨 → Codex가 대화형 입력을 기대 → 무한 hang.

**필수 패턴**:
```bash
# ❌ 잘못된 호출 (hang 발생)
codex exec ... "prompt" 2>&1 | tail -20

# ✅ 올바른 호출 (stdin 명시 close)
codex exec ... "prompt" < /dev/null 2>&1 | tail -20
```

## 2. Trusted Directory 확인 + Skip Flag

**증상**: `Not inside a trusted directory and --skip-git-repo-check was not specified.` 에러로 즉시 종료.

**원인**: PROJECT_ROOT ≠ GIT_ROOT dual-root 구조에서 Codex가 git repo 외부 실행을 거부.

**필수 패턴**:
```bash
# Working dir이 git repo 밖일 때
codex exec ... --skip-git-repo-check ... "prompt" < /dev/null

# 자동 판정
if git -C "$WORK_DIR" rev-parse --git-dir > /dev/null 2>&1; then
  SKIP_FLAG=""
else
  SKIP_FLAG="--skip-git-repo-check"
fi
```

## 3. `-o` 파일 출력 시 stdout buffering 주의

**관찰**: `-o /path/to/output.md`로 결과를 파일에 쓰면 stdout에는 진행 stream만 출력. 실제 결과는 `-o` 파일에서 Read.

```bash
codex exec ... -o "$RESULT_FILE" "prompt" < /dev/null 2>&1 | tail -5
# 결과 읽기는 별도 도구로 Read("$RESULT_FILE")
```

## 4. Background Task 의무 영역

**조건**: high effort + Plan 300줄+ 입력 시 5-8분 소요(frontier 모델 실측). Bash foreground는 timeout 위험.

**패턴**: `run_in_background: true` + `ScheduleWakeup`으로 비동기 처리.

## 5. ⛔ Trust Level 필수 (30차 교훈, Critical)

**증상**: `codex exec --profile <NAME>` 호출 시 `sandbox: read-only`로 force. Profile 설계 전체 무효화.

**원인**: Codex CLI 0.124.0은 실행 path가 `trust_level = "trusted"`로 명시되지 않으면 **"untrusted directory" 취급**.

**필수 config** (`~/.codex/config.toml`):
```toml
[projects."<absolute path to GIT_ROOT>"]
trust_level = "trusted"

[projects."<absolute path to PROJECT_ROOT>"]
trust_level = "trusted"

[projects."<absolute path to fz-plugin dev>"]
trust_level = "trusted"
```

**fz-codex 호출 시 적용 범위**:
- **Profile 사용 시 (--profile)**: trust_level 없으면 sandbox 무효화
- **Profile 미사용 시 (-c 'sandbox_permissions=...')**: trust_level 없어도 inline override 가능 [미검증]
- **대안 폴백**: `-c 'projects."<path>".trust_level="trusted"'` inline override

**`--skip-git-repo-check` vs trust_level**:
- `--skip-git-repo-check`: git repo check 우회만
- `trust_level = "trusted"`: Codex sandbox 정책에 직접 영향

**판정 logic**:
```bash
if ! grep -qE "\[projects\." ~/.codex/config.toml; then
  echo "WARNING: trust_level 미설정"
fi
```

## 5.5 Base Verification Gate (pre-flight, git diff 분석 포함 호출 시)

> Codex 메타 분석 발견: branch/HEAD 출력만으로 부족, 변경 파일 목록까지 포함 필수.

```bash
# Pre-flight: branch / HEAD / base 확인
CURRENT_BRANCH=$(git -C "$WORK_DIR" branch --show-current 2>/dev/null || echo "?")
HEAD_COMMIT=$(git -C "$WORK_DIR" rev-parse --short HEAD 2>/dev/null || echo "?")
EXPECTED_BRANCH="${EXPECTED_BRANCH:-$CURRENT_BRANCH}"

if [ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ] && [ -n "$EXPECTED_BRANCH" ]; then
  echo "⛔ Branch mismatch: current=$CURRENT_BRANCH, expected=$EXPECTED_BRANCH"
  exit 1
fi

if echo "$@" | grep -q -- "--base"; then
  BASE=$(echo "$@" | sed -n 's/.*--base \([^ ]*\).*/\1/p')
  git -C "$WORK_DIR" merge-base "$BASE" HEAD >/dev/null 2>&1 || {
    echo "⛔ Base '$BASE' invalid or unreachable from HEAD"
    exit 1
  }
fi

# ⛔ 카운트는 **잘리지 않은 전체 집합**에서 센다. 표시만 자른다 (자른 목록으로 세면 카운트가 틀린다)
CHANGED_FILES=$(git -C "$WORK_DIR" diff --name-only "${BASE:-HEAD~1}"..HEAD 2>/dev/null)
CHANGED_COUNT=$(printf '%s\n' "$CHANGED_FILES" | grep -c . || true)

echo "▶ Codex 분석 대상 — branch=$CURRENT_BRANCH commit=$HEAD_COMMIT base=${BASE:-HEAD~1}"
echo "▶ 변경 파일 ${CHANGED_COUNT}개 (앞 10개만 표시):"
printf '%s\n' "$CHANGED_FILES" | head -10
```

**규칙**:
- ⛔ 위 Gate 통과 후에만 `codex exec` 호출
- ⛔ Codex 결과 인용 시 `[분석 기준: branch=X, HEAD=Y, base=Z, changed_files=N개]` 태그 의무
- ⛔ EXPECTED_BRANCH 주입: 호출자가 *명시 환경변수 설정 필수*
- ⛔ 단순 파일 분석 (git diff 미포함) 호출에는 Gate 적용 **제외**

## 6. Standard Hygiene Wrapper Template

> ⛔ **본 절은 §8 `scripts/codex-exec.sh`로 대체됐다** — 아래 템플릿은 스크립트가 무엇을 하는지 읽기 위한 **참조**로 남긴다. 호출은 §8을 경유한다 (복붙 템플릿은 호출자가 붙이지 않으면 작동하지 않고, 실측상 누락이 재발했다).
>
> 6 hygiene rules (1-5 + 7: `--` 구분자) + zsh glob 회피 + output readback 통합.

```bash
# 0. 프롬프트 파일화 (zsh glob 회피)
cat > /tmp/codex-prompt.txt << 'EOF'
...your prompt with regex/quotes/multiline...
EOF

# 1. Trust check (rule 5)
if ! grep -qE "\[projects\." ~/.codex/config.toml; then
  echo "WARNING: trust_level 미설정"
fi

# 2. Skip flag 결정 (rule 2)
if git -C "$WORK_DIR" rev-parse --git-dir > /dev/null 2>&1; then
  SKIP_FLAG=""
else
  SKIP_FLAG="--skip-git-repo-check"
fi

# 3. 표준 호출 (rule 1: stdin close + rule 3: -o output + rule 7: -- 구분자)
codex exec \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  $SKIP_FLAG \
  -o "$RESULT_FILE" \
  -C "$WORK_DIR" \
  -- "$(cat /tmp/codex-prompt.txt)" < /dev/null

# 4. 결과 읽기: Read tool로 $RESULT_FILE
# 5. Background mode (rule 4): high effort + 300줄+ 시 run_in_background=true
```

**적용 권고**: fz-codex/SKILL.md의 모든 서브커맨드 예시는 본 wrapper 패턴을 따른다.

## 7. 프롬프트 선두 하이픈 clap 오파싱 (`--` 구분자)

**증상**: `codex exec`의 positional 프롬프트가 하이픈으로 시작하면(예: SKILL.md YAML frontmatter의 `---` 3연속) clap이 이를 플래그로 오해석 → usage 에러로 즉시 종료.

**원인**: clap은 end-of-options(`--`) 미지정 시 하이픈 선두 인자를 옵션으로 파싱.

**필수 패턴**: `codex exec [flags]` 뒤에 `--`를 넣고 그 뒤에 프롬프트 인자.

```bash
codex exec ... -- "$(cat /tmp/codex-prompt.txt)" < /dev/null
```

**관찰**: 에러 캡처 시 `tail` 파이프 금지(clap 에러 본문 잘림 → 진단 지연), 전체 리다이렉트(`> log 2>&1`) 사용. (2026-07-09 harness-paper 세션 실측 — SKILL.md 주입 시 재현)

## 8. ⛔ `scripts/codex-exec.sh` 경유 의무 (2026-08-09 — **본 절이 정본 호출 경로**)

> §1~§7을 손으로 조립하지 않는다. `guides/skill-authoring.md` §11 판정("결과가 binary(pass/fail)인가? → 스크립트")이 본 모듈 전체에 적용된다 — hygiene 규칙은 전부 binary다.

**신설 근거 (실측 2건, 2026-08-09 세션)**:

| 실패 | 지식은 어디 있었나 | 왜 안 막혔나 |
|---|---|---|
`codex exec review --uncommitted "<prompt>"` → **exit 2** | `modules/fz-codex-subcommands-core.md:36`이 "함께 주면 인자 충돌"을 이미 명시 | 산문 경고는 **호출 시점에 읽혀야** 작동한다. 호출자가 §6 템플릿을 붙이지 않고 손으로 조립했다 |
래퍼가 `codex exit=2`를 **0으로 보고** | — (규칙 자체가 없었다) | 마지막 문장(`wc \|\| echo`)의 exit이 태스크 exit으로 올라갔다. §1~§7에 **사후 검증 규칙이 없다** |

⛔ 두 번째가 더 위험하다: **측정 실패가 "이슈 0건"으로 읽힌다.** exit≠0 / 빈 출력은 *깨끗한 리뷰*가 아니라 *리뷰 부재*다.

### 인터페이스

```bash
# review: 대상 선택은 플래그로만 (PROMPT 불가 — 스크립트가 거부한다)
scripts/codex-exec.sh review --cd "$GIT_ROOT" --out "$F" --uncommitted [--effort high] [--schema S] [--title T] [--ephemeral]
scripts/codex-exec.sh review --cd "$GIT_ROOT" --out "$F" --base develop [--add-dir D]

# exec: 커스텀 지시가 필요할 때 (diff는 프롬프트에 인라인 — 스코프 플래그 금지)
scripts/codex-exec.sh exec   --cd "$GIT_ROOT" --out "$F" --prompt-file P [--effort xhigh] [--schema S]
```

### 사전 게이트 (호출 전 거부)

1. **플래그 상호 배타** — `review` + `--prompt-file` → exit 10. `exec` + `--base/--uncommitted/--commit` → exit 10
2. **필수 인자** — `review`는 스코프 1개 필수 · `exec`는 `--prompt-file` 필수 · 양쪽 `--cd`/`--out` 필수
3. **경로 실재** — `--cd` 디렉토리 · 프롬프트·스키마 파일 비어있지 않음 · `codex` 설치 (exit 11)
4. **trust_level** — 미설정 시 경고(§5). ⛔ 차단은 아니다 — inline override 경로가 있다
5. **git repo 판정** → `--skip-git-repo-check` 자동 부착(§2)
6. **값 옵션 arity** — 값 없는 `--cd`/`--out`/… → exit 10 (⛔ 없으면 `set -u`가 exit **1**로 죽어 문서와 어긋난다)
7. **스코프 단일성** — `--base`/`--uncommitted`/`--commit` 중복 지정 → exit 10 (배열로 보관해 단어분할·glob 차단)
8. **§5.5 Base Verification Gate 내장** — ⛔ **`review` 모드 + git repo 일 때만 발동한다.** `exec` 모드는 diff를 프롬프트에 인라인하므로 게이트가 적용되지 않는다 → **호출자가 분석 기준(branch·HEAD·대상 집합)을 프롬프트에 직접 명시할 의무**가 있다 (3라운드 감사 ISSUE-011). ⛔ `--expected-branch` 는 **옵션**이다 — 정본 모듈이 주입을 요구하므로 호출자가 명시해야 하며, 미지정 시 브랜치 검증은 수행되지 않는다. ⛔ `--commit` 의 merge 커밋은 `show --name-only`가 부모 선택에 따라 달라진다 — 정확한 대상이 필요하면 `--base` 를 쓴다.
   나머지 보장: — `review` + git repo일 때: branch·HEAD 출력 · `--expected-branch` 불일치 → exit 11 · `--base`는 `rev-parse --verify` + **`merge-base --is-ancestor`**(⛔ `merge-base A B`는 공통조상 존재만 증명) · 스코프별 변경 파일 집합 **분리 산출** + ⛔ **잘리기 전에 카운트**

### 사후 게이트 (결과 해석 전 — 신설분)

| 순서 | 검사 | 실패 시 exit | 의미 |
|:--:|---|:--:|---|
| 1 | `codex` 종료코드 == 0 | **12** | 측정 실패 |
| 2 | `-o` 파일 존재 + 비어있지 않음 | **13** | 측정 실패 |
| 3 | `--schema` 지정 시 **스키마 계약** 충족 (`scripts/validate-codex-output.py`) | **14** | 측정 실패 |
| 4 | **cwd 오염 없음** — 호출 전후 `git status --porcelain` 동일 | 경고 | 위임 프로세스가 대상 repo에 파일을 남겼다 |

⛔ **게이트 4의 근거**: `--cd`로 지정한 디렉토리는 위임 프로세스의 **쓰기 대상**이기도 하다. 팀 레포를 `--cd`로 준 호출이 산출물 17개를 그 안에 남긴 실측이 있다(gitignore 미적용). 읽기 전용이라는 가정은 **호출자의 것이지 도구의 계약이 아니다**.

```bash
BEFORE="$(git -C "$CD" status --porcelain 2>/dev/null)"
scripts/codex-exec.sh ... ; RC=$?
AFTER="$(git -C "$CD" status --porcelain 2>/dev/null)"
[ "$BEFORE" = "$AFTER" ] || echo "WARN: cwd 오염 — 새 파일을 개인 경로로 옮겨라: $(diff <(printf '%s' "$BEFORE") <(printf '%s' "$AFTER") | grep '^>')" >&2
```

⛔ 게이트 3은 **문법이 아니라 계약**을 본다 — required·type·enum·`additionalProperties`·`$ref`를 재귀 검사한다. 1차 구현은 `json.load` 성공만 봐서 **`{}` 가 `GATE-PASS issues=0` 으로 통과**했다(감사 ISSUE-013). ⛔ `jsonschema` 부재(실측)로 표준 라이브러리 부분집합 구현 — 미지원 키워드(oneOf/allOf/pattern 등)는 검사하지 않고 통과시키며 그 범위를 스크립트 docstring에 명시한다.

- 통과 시 `GATE-PASS json_ok issues=N verdict=V` (또는 `text_ok bytes=N`)를 **stdout에 출력**한다 — 호출자가 결과 유효성을 눈으로 확인할 수 있다
- ⛔ **exit 10~14는 전부 측정 실패다** — "이슈 0건"·"승인"으로 해석 금지. 실패 시 `${OUT}.stream.log`를 Read
- ⛔ 호출자는 스크립트 exit을 **마지막 문장으로 두거나 변수에 담아라** — 뒤에 `wc`/`echo`를 붙이면 그 exit이 덮는다 (본 절 신설을 유발한 실패)

### 검증 상태 (양성 대조 — 2026-08-09 실측)

사전 게이트 8종 전부 발화(exit 10×6 / 11×2) + 성공 경로 `GATE-PASS text_ok` exit 0. ⛔ 통과만 확인한 게이트는 무용하므로 **발화 가능성**을 함께 실측했다 (`modules/cross-validation.md` §Negative-Result Gate).

---

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-codex | 본 모듈의 직접 소비자 — 모든 서브커맨드가 본 hygiene 준수 |
| /fz | Codex 호출 게이트 주입 시 본 hygiene 인용 |
| /fz-plan | TEAM 모드 Codex verify 호출 시 본 hygiene 준수 |
| /fz-review | TEAM 모드 Codex check 호출 시 본 hygiene 준수 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시 *명시 Read* — 자동 로드 X. Codex 검증 §추가 발견 정정)
- 200줄 한도 — 본 모듈은 *실용 wrapper 포함*으로 약간 초과 가능
