# GPT 실행 전략

> **Sources (last audited: 2026-09-21 — **인용 정합 축**(arxiv ID 형식 56종 이상 0 · 교차 파일 주장 일치 · 레지스트리 등재)):** `learn.chatgpt.com/docs/changelog` (구 `developers.openai.com` 308 리다이렉트 명시). ⛔ **원문 재조회는 포함하지 않았다** — 외부 페이지가 바뀌었는지는 이 감사의 범위 밖이다.

> fz-gpt SKILL.md 서브커맨드에서 참조. 공통 설정 (Base Branch / Effort / Diff 크기 / CLI 모드).

> **Authority Sources** (Cgap-1 보강, 2026-05-16):
> - **Reasoning Effort 정책**: Anthropic "Harness Design for Long-Running Apps" (2026-03) [verified: A2] — effort 파라미터를 작업 복잡도에 매칭. "Self-evaluation is unreliable" → cross-model verify 시 effort 정밀 설정 필요
> - **Diff 크기 정책**: Context Rot (Chroma Research, 18 frontier models) [verified: empirical study] — focused 300 tokens > unfocused 113K tokens. Small (<2000) full diff / Medium (2000-8000) file-split / Large (>8000) key files + summary
> - **CLI Mode 라우팅**: GPT CLI Changelog [verified: official] — Hybrid mode (0.118.0+ Plugin + CLI fallback) · gpt-5.5 (0.124.0+) · gpt-6-astra (0.153.1+, 0.153.4에서 bundled default) · **gpt-6-sol (0.156.1 모델 선택기 추가 · 0.157.0 정식 추가 — 현 CLI 기본·bundled default, medium)**. ⚠️ 실제 모델은 CLI 버전과 `config.toml` 에 따른다 — 래퍼는 모델을 pin 하지 않는다
>   출처: https://learn.chatgpt.com/docs/changelog (구 `developers.openai.com/codex/changelog` 는 여기로 308)

## 목차

- [Base Branch 결정](#base-branch-결정)
- [Reasoning Effort 전략 (사용자 명시 호출 기반)](#reasoning-effort-전략-사용자-명시-호출-기반)
- [Diff 크기 적응 전략](#diff-크기-적응-전략)
- [장기 불능 인지 (기간 조건부)](#장기-불능-인지-기간-조건부)
- [CLI 모드 선택 전략 (Hybrid)](#cli-모드-선택-전략-hybrid)
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

## Reasoning Effort 전략 (사용자 명시 호출 기반)

GPT 교차 검증은 **사용자가 필요할 때 명시적으로 호출**한다. 자동 경량 게이트 없음.

| Tier | 맥락 | 모델 | Effort | 예상 시간 |
|------|------|------|--------|----------|
| **Standard** | 명시적 호출 (review, verify, check, validate, commit, drift) | config 기본값 | `high` | ~3-5분 |
| **Deep** | final, adversarial, plan, critical 재검증, --deep | config 기본값 | `xhigh` | ~8-10분 |
| **Light** | micro-eval (단일 주장 재평가) | config 기본값 | `medium` | ~1-2분 |

> Subcommand별 정확한 매핑은 `skills/fz-gpt/SKILL.md § Effort Routing (δ-2)` 표 참조 (authoritative). adversarial=xhigh로 정합화 (2026-04-25, codex-utilization plan v1 Step 2 inline action).

**결정 규칙**:
- 기본: 모델=`config.toml` `model`(SSOT — 값 인라인 표기 금지, 항상 최신 frontier) + effort=`high`
- `final` 또는 이전 검증에서 critical 발견 → **Deep** (자동 에스컬레이션)
- 사용자가 `--deep` 플래그 사용 → **Deep**
- **`/fz` Phase 1 `simplified_keywords` 감지 시 → Light** (Cnew-2 자동 라우팅, 2026-05-16):
  - 사용자 신호: "그냥/가볍게/단순/빠르게/light" 키워드
  - GPT 호출: `effort=medium` + micro-eval 패턴 적용
  - 적용 서브커맨드: review/verify/check (light variant)
  - Claude light 모드 (fz-plan/code/review)와 정합 — 같은 simplified signal로 양쪽 동시 라우팅

> Review Gate: OFF. 경량 모델(spark) 자동 게이트는 품질 ROI가 낮아 사용하지 않음.

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

## CLI 모드 선택 전략 (Hybrid)

래퍼 review 모드(`gpt-exec.sh review`)가 git diff + 구조화 출력을 통합. Plugin 설치 시 review/check/adversarial은 `/codex:*` 우선.
Plugin 미설치 시 모든 서브커맨드가 래퍼로 동작 (폴백 투명).

| 기준 | `gpt-exec.sh review` | `gpt-exec.sh exec` |
|------|---------------------|-------------|
| **diff 입력** | Git 자동 감지 (--base/--uncommitted/--commit) | 수동 주입 (프롬프트에 인라인) |
| **출력 형식** | `--out`(최종 메시지 파일) | `--out` + `--schema` JSON 강제 |
| **모델 명시** | 래퍼는 모델을 넘기지 않는다 → config `model` 기본값 사용(권장, 항상 최신) | 동일 |
| **GPT 스킬** | 3-Tier 디스커버리 자동 트리거 | 스킬 내용 수동 주입 필요 |
| **모노레포 컨텍스트** | read-only 가 전 디스크 읽기 허용 — 별도 플래그 불필요 | 동일 (필요한 경로는 프롬프트에 적는다) |

**서브커맨드별 매핑**:

| 서브커맨드 | CLI 모드 | 이유 |
|-----------|----------|------|
| review | `gpt-exec.sh review` | Git diff + `--out` 구조화 캡처 + 스킬 자동 |
| check | `gpt-exec.sh review` | --uncommitted + `--out` |
| commit | `gpt-exec.sh review` | --commit + `--out` |
| final | `gpt-exec.sh review` | --base + xhigh + `--out` + `resume --session-file` 심화 |
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
- GPT CLI 네이티브 스킬 (`~/.codex/skills/.system/openai-docs` 활용 가능)

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
