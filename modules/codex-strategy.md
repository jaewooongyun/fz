# Codex 실행 전략

> fz-codex SKILL.md 서브커맨드에서 참조. 공통 설정 (Base Branch / Effort / Diff 크기 / CLI 모드).

## Base Branch 결정

review, final 서브커맨드에서 `--base` 브랜치가 필요합니다.

**자동 결정 로직**:
1. 인자로 `--base <branch>` 명시 시 → 해당 브랜치
2. 현재 브랜치가 `feature/*` → `--base develop`
3. 현재 브랜치가 `hotfix/*` → `--base main`
4. 그 외 → `AskUserQuestion`으로 사용자에게 확인

## Reasoning Effort 전략

**서브커맨드 실행 전 AskUserQuestion으로 effort 레벨을 선택한다.**

```
Q: "Reasoning effort를 선택하세요"
옵션:
  1. high — 속도-품질 균형 (기본, Recommended)
  2. xhigh — 최고 정밀도 (시간 소요 증가)
```

선택된 값을 `-c model_reasoning_effort=<선택>` 으로 모든 codex 호출에 적용.

| 상황 | Effort | 비고 |
|------|--------|------|
| 기본 (모든 서브커맨드) | **사용자 선택** | 선택 없으면 high |
| Critical 이슈 재검증 | **xhigh** | 이전 검증에서 critical 발견 시 자동 에스컬레이션 |
| final (PR 전 최종) | **xhigh** | 사용자 선택 무관, 항상 최고 정밀도 |

## Diff 크기 적응 전략

diff 크기에 따라 Codex 호출 전략을 자동 선택합니다.

**크기 측정**:
```bash
DIFF_LINES=$(cd "$GIT_ROOT" && git diff --base "$BASE_BRANCH" --stat | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+')
```

| diff 크기 | 전략 | 실행 방법 |
|-----------|------|----------|
| **Small** (<2000줄) | Full diff → `codex exec review` | gpt-5.4 1M context 활용, 구조화 전체 리뷰 (기본) |
| **Medium** (2000-8000줄) | File-split → `codex exec` xN | 변경 파일을 기능 그룹으로 분할, 그룹별 독립 리뷰 |
| **Large** (>8000줄) | Key files + summary | 핵심 파일만 상세 리뷰 + 나머지 요약 |

**Medium 전략**: 변경 파일을 기능 그룹(Architecture/Data/UI)으로 분할 → 그룹별 `codex exec` 독립 리뷰 → `jq`로 결과 합산.

**Large 전략**: 변경량 상위 10 파일만 상세 리뷰 + 나머지 요약.

**자동 전환 규칙**:
- `review`, `check`, `commit`: Small 전략 기본, Medium/Large 시 자동 전환
- `final`: 항상 최대 커버리지 (Medium→Full 시도, Large→Key files)
- `verify`, `validate`: diff 크기 무관 (프롬프트 기반)

## CLI 모드 선택 전략 (0.111.0+)

`codex exec review`가 git diff + 구조화 출력을 통합. 기존 `codex review`의 제약 해소.

| 기준 | `codex exec review` | `codex exec` |
|------|---------------------|-------------|
| **diff 입력** | Git 자동 감지 (--base/--uncommitted/--commit) | 수동 주입 (프롬프트에 인라인) |
| **출력 형식** | `--json`(JSONL) + `-o`(최종 메시지 파일) | `--output-schema` JSON 강제 |
| **모델 명시** | `-m gpt-5.4` (호출별 지정 가능) | `-m gpt-5.4` |
| **Codex 스킬** | 3-Tier 디스커버리 자동 트리거 | 스킬 내용 수동 주입 필요 |
| **모노레포 컨텍스트** | `--add-dir` (공유 모듈 접근) | `-C` + `--add-dir` |

**서브커맨드별 매핑**:

| 서브커맨드 | CLI 모드 | 이유 |
|-----------|----------|------|
| review | `codex exec review` | Git diff + `-o` 구조화 캡처 + 스킬 자동 |
| check | `codex exec review` | --uncommitted + `-o` |
| commit | `codex exec review` | --commit + `-o` |
| final | `codex exec review` | --base + xhigh + `-o` + resume 심화 |
| verify | `codex exec` | 계획 텍스트 + `--output-schema` JSON 필요 |
| validate | `codex exec` | 이슈 목록 + `--output-schema` JSON 필요 |

**심화 패턴**: `codex exec review`로 1차 리뷰 → `codex exec resume --last`로 특정 이슈 심화 검증. `final`에서 자동 적용.
