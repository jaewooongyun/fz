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
- §6 Standard Hygiene Wrapper Template (복붙용)

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

**조건**: gpt-5.5 high effort + Plan 300줄+ 입력 시 5-8분 소요. Bash foreground는 timeout 위험.

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

CHANGED_FILES=$(git -C "$WORK_DIR" diff --name-only "${BASE:-HEAD~1}"..HEAD 2>/dev/null | head -10)

echo "▶ Codex 분석 대상 — branch=$CURRENT_BRANCH commit=$HEAD_COMMIT base=${BASE:-HEAD~1}"
echo "▶ 변경 파일 ($(echo "$CHANGED_FILES" | wc -l)개): $CHANGED_FILES"
```

**규칙**:
- ⛔ 위 Gate 통과 후에만 `codex exec` 호출
- ⛔ Codex 결과 인용 시 `[분석 기준: branch=X, HEAD=Y, base=Z, changed_files=N개]` 태그 의무
- ⛔ EXPECTED_BRANCH 주입: 호출자가 *명시 환경변수 설정 필수*
- ⛔ 단순 파일 분석 (git diff 미포함) 호출에는 Gate 적용 **제외**

## 6. Standard Hygiene Wrapper Template

> 5 hygiene rules (1-5) + zsh glob 회피 + output readback 통합.

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

# 3. 표준 호출 (rule 1: stdin close + rule 3: -o output)
codex exec \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  $SKIP_FLAG \
  -o "$RESULT_FILE" \
  -C "$WORK_DIR" \
  "$(cat /tmp/codex-prompt.txt)" < /dev/null

# 4. 결과 읽기: Read tool로 $RESULT_FILE
# 5. Background mode (rule 4): high effort + 300줄+ 시 run_in_background=true
```

**적용 권고**: fz-codex/SKILL.md의 모든 서브커맨드 예시는 본 wrapper 패턴을 따른다.

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
