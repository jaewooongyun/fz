# skill-creator 연동 가이드

> fz-skill의 optimize / eval Runtime Trigger에서 참조하는 Level 3 문서

## 적용 범위 및 한계 (실증 결과 2026-03-20)

**핵심 발견**: `run_eval.py`의 `claude -p` 기반 자동 트리거 테스트는 **슬래시 커맨드 기반 스킬에는 제한적 효과**.
- Claude는 간단한 요청을 스킬 참조 없이 직접 처리하려는 경향이 있음
- fz-* 스킬은 `/fz-fix`, `/fz` 오케스트레이터 경유로 호출되는 구조 → `claude -p` 독립 세션과 사용 패턴이 다름
- description을 "pushy"하게 바꿔도 should-trigger 성공률 변화 없음 (0% → 0%)
- should-NOT-trigger는 100% 정확 → 오트리거 방지에는 유효

**유효한 활용처**:
- 독립형 스킬 (skill-creator 자체 생태계의 스킬) → 자동 트리거가 핵심
- fz 스킬의 should-NOT-trigger 검증 → 다른 스킬과 충돌하지 않는지 확인
- `run_loop.py` description 최적화 → **ANTHROPIC_API_KEY 필수** (환경변수)

**fz 스킬에 더 유효한 검증**:
- 정적 eval (fz-skill eval 기존 Static Analysis 8항목)
- intent-registry 매칭 테스트 (/fz Phase 1 시뮬레이션)
- provides/needs 체인 정합성 (fz-manage check)

## skill-creator 경로 탐색

```
1. Glob("**/plugins/skill-creator/skills/skill-creator/scripts/run_loop.py")
2. 결과에서 scripts/ 상위 경로 추출 → SKILL_CREATOR_ROOT
3. 없으면 → "skill-creator 플러그인이 필요합니다. Claude Code plugin marketplace에서 설치하세요." 안내
4. 기존 정적 eval만 실행 (graceful fallback)
```

## Dependency Check

optimize/runtime eval 시작 전 반드시 확인:

```bash
# 1. Claude CLI 존재
which claude || echo "claude CLI가 필요합니다"

# 2. anthropic SDK (run_loop.py 의존)
python3 -c "import anthropic" 2>/dev/null || echo "pip install anthropic 필요"
```

실패 시: 해당 의존성 설치 안내 후 기존 정적 eval로 fallback.

## Eval 쿼리 자동 생성 규칙

### should-trigger 쿼리 (10개)

대상 스킬의 `intent-triggers` 정규식에서 추출:

1. 각 정규식 패턴에서 **구체적 사용자 발화** 3-4개 생성
2. **구어체 변형** 포함: "~해줘", "~좀", "~할래", 영어 혼용
3. **상황 맥락 추가**: 파일 경로, 기능명, 에러 메시지 등 디테일 포함
4. **길이 다양화**: 짧은 명령 (5단어) ~ 상세 설명 (30단어+)

```
BAD: "스킬을 만들어줘"
GOOD: "fz-test라는 이름으로 테스트 자동화 스킬 만들어줘, XCTest 결과 파싱하고 리포트 생성하는 용도야"
```

### should-not-trigger 쿼리 (10개)

대상 스킬의 `Boundaries > Will Not`에서 추출:

1. 각 "Will Not" 항목을 **near-miss 쿼리**로 변환
2. 키워드가 겹치지만 **다른 스킬이 담당**하는 요청
3. 명백히 무관한 쿼리는 제외 (테스트 가치 없음)

```
BAD: "피보나치 함수 만들어줘" (너무 먼 쿼리)
GOOD: "스킬 목록 보여줘" (keyword "스킬" 겹치지만 fz-manage 담당)
```

### skill-creator 가이드라인 준수

- 쿼리는 **실제 사용자가 입력할 법한** 구체적 문장
- 파일 경로, 개인 상황, 회사명, 약어, 오타 등 자연스러운 디테일
- should-not-trigger는 **near-miss** 중심 (키워드 겹침 + 의도 다름)
- should-trigger/should-not-trigger 비율: 약 50:50

## optimize 실행 절차 (상세)

### Phase 1: 경로 탐색 + Dependency Check

```
1. Glob → SKILL_CREATOR_ROOT 확보
2. which claude + python3 -c "import anthropic" 확인
3. 실패 시 안내 + 중단
```

### Phase 2: Eval 쿼리 생성 + 사용자 검토

```
1. 대상 스킬 SKILL.md 읽기 → intent-triggers + Boundaries 추출
2. 위 규칙으로 should-trigger 10개 + should-not-trigger 10개 생성
3. JSON 배열 작성:
   [{"query": "...", "should_trigger": true}, ...]

4. eval_review.html로 브라우저 UI 생성:
   a. Read("{SKILL_CREATOR_ROOT}/assets/eval_review.html")
   b. __EVAL_DATA_PLACEHOLDER__ → JSON 배열
   c. __SKILL_NAME_PLACEHOLDER__ → 스킬명
   d. __SKILL_DESCRIPTION_PLACEHOLDER__ → 현재 description
   e. Write("/tmp/eval_review_{skill-name}.html")
   f. open "/tmp/eval_review_{skill-name}.html"

5. 사용자가 편집/토글 후 "Export Eval Set" → ~/Downloads/eval_set.json
6. eval_set.json 읽기 (~/Downloads에서 최신 버전 확인)
```

### Phase 3: 최적화 루프 실행

```bash
# 백그라운드 실행
python3 -m scripts.run_loop \
  --eval-set <eval_set.json 경로> \
  --skill-path <대상 스킬 경로> \
  --model <현재 세션 모델 ID> \
  --max-iterations 5 \
  --verbose

# 실행 위치: SKILL_CREATOR_ROOT에서 실행 (scripts가 상대 import 사용)
```

동작:
- train/test 60/40 split (stratified by should_trigger)
- 각 쿼리 3회 실행 → trigger rate 산출
- Claude extended thinking으로 description 개선안 생성
- 최대 5회 반복
- **test score 기준**으로 best_description 선택 (overfitting 방지)

### Phase 4: 결과 적용

```
1. run_loop.py 출력에서 best_description 추출
2. 전후 비교 출력:
   BEFORE: {기존 description}
   AFTER:  {best_description}
   Train score: X% → Y%
   Test score:  A% → B%
3. 사용자 승인 → SKILL.md frontmatter의 description 교체
4. 거부 → 변경 없음
```

### --full 옵션 (전체 eval 루프)

optimize에 `--full`을 추가하면 description 최적화에 더해 전체 eval 루프 실행:

1. evals.json 생성 (test prompts + assertions)
2. 서브에이전트로 with-skill vs without-skill 병렬 실행
3. grader.md로 채점
4. aggregate_benchmark.py로 benchmark.json 생성
5. generate_review.py로 HTML 뷰어 제공
6. 사용자 피드백 → 스킬 개선 → 반복

> --full은 시간이 많이 소요되므로 주요 스킬 대규모 변경 시에만 권장.

## Quick Trigger Eval (benchmark용)

fz-manage benchmark --with-trigger에서 사용하는 경량 모드:

```
1. 대상 스킬에서 should-trigger 3개 + should-not-trigger 2개 자동 생성
2. run_eval.py로 각 1회만 실행 (3x 반복 없음)
3. trigger rate 산출: 정확히 트리거된 수 / 전체 5개
4. 결과: 0% ~ 100%
```

실행 시간: 스킬당 ~30초 (5회 claude -p 호출)

## Graceful Fallback 정책

| 상황 | 동작 | 대체 |
|------|------|------|
| skill-creator 미설치 | Glob 실패 → WARN 안내 | 정적 eval만 실행 |
| claude CLI 없음 | which 실패 → 설치 안내 | 정적 eval만 실행 |
| anthropic SDK 없음 | import 실패 → pip 안내 | 정적 eval만 실행 |
| run_loop.py 실행 에러 | stderr 출력 → 사용자 보고 | 정적 eval 결과만 출력 |
| eval_review.html 미존재 | JSON 직접 출력으로 대체 | 터미널에서 쿼리 확인 |
