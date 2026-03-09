# Intent Registry

> /fz Phase 1에서 참조. 스킬별 트리거 패턴 + Confidence 판정 규칙.
> Progressive Disclosure Level 3 (/fz Phase 1에서만 로드).

## 스킬별 intent-triggers 레지스트리

| 스킬 | 한국어 패턴 | 영문 패턴 |
|------|-----------|----------|
| fz-discover | `어떻게.*좋을까\|어디에.*좋을까\|뭐가.*맞을까\|괜찮을까\|트레이드오프\|맞는지\|차이점\|놓치고\|어떻게.*생각\|이렇게.*해도` | `how.*should\|where.*should\|what.*best\|trade.?off\|difference\|missing\|what.*think` |
| fz-plan | `계획\|설계\|아키텍처\|요구사항` | `plan\|design\|architect` |
| fz-code | `구현\|코드\|만들어\|개발` | `implement\|code\|develop` |
| fz-review | `리뷰\|검증\|품질\|검토` | `review\|validate\|quality` |
| fz-fix | `수정\|고쳐\|버그\|크래시\|에러` | `fix\|bug\|crash\|error` |
| fz-search | `찾아\|탐색\|구조\|영향\|의존성` | `search\|explore\|structure` |
| fz-codex | `codex\|교차검증` | `codex\|cross-validate` |
| fz-commit | `커밋` | `commit` |
| fz-pr | `PR\|풀리퀘스트` | `PR\|pull.?request` |
| fz-peer-review | `피어리뷰\|팀원\|PR.*리뷰` | `peer.?review\|teammate` |
| fz-pr-digest | `설명\|해설\|이해\|학습\|뭐가.*바뀐\|어떻게.*개선` | `explain\|digest\|understand\|what.*changed` |
| fz-skill | `스킬.*만들\|스킬.*생성\|스킬.*수정\|스킬.*삭제\|에이전트.*만들\|에이전트.*생성` | `create.*skill\|new.*skill\|update.*skill\|delete.*skill\|create.*agent\|new.*agent` |
| fz-doc | `문서\|작성\|개선\|description\|가이드\|스킬.*작성\|에이전트.*작성` | `document\|write.*skill\|improve.*description\|optimize.*prompt` |
| fz-excalidraw | `다이어그램\|그려줘\|시각화\|구조도\|플로우차트\|흐름도\|도식화` | `diagram\|excalidraw\|visualize\|draw\|flowchart` |
| fz-codex (drift) | `드리프트\|아키텍처.*점검\|레이어.*위반\|전체.*스캔\|점검해줘\|훑어봐\|전체.*봐줘\|전체.*확인해줘` | `drift\|arch.*check\|full.*scan` |
| fz-codex (plan) | `독립.*플랜\|GPT.*계획\|교차.*플랜\|플랜.*검증\|병렬.*플랜\|독립.*계획` | `independent.*plan\|parallel.*plan\|cross.*plan` |
| fz-memory | `메모리.*정리\|메모리.*관리\|메모리.*감사\|교훈.*회상\|기억.*떠올려` | `memory.*audit\|memory.*gc\|memory.*recall\|memory.*organize\|cleanup.*memory` |

## 구어체 보강 트리거

기존 스킬 트리거에 구어체/복합 표현을 보강합니다:

| 스킬 | 추가 패턴 (구어체) |
|------|-----------------|
| fz-plan | `뭐부터.*시작\|어디서.*시작\|순서.*알려줘\|뭘.*해야\|어떻게.*만들면` |
| fz-code | `짜줘\|작성해줘\|만들어봐\|코딩해줘\|개발해줘` |
| fz-fix | `안 돼\|안됨\|이상해\|왜 이래\|문제있어\|오류남` |
| fz-review | `괜찮아?\|문제없어?\|이거 어때\|잘 된 거야?\|맞게 했어?` |
| fz-search | `어디 있어\|어디에 있\|어디서 쓰이\|누가 쓰는` |
| fz-discover | `어떻게 하면\|어떤 방식\|어떤 게 나아\|뭐가 좋아\|고민인데` |

## Confidence 판정 규칙

매칭 후 신뢰도를 평가하여 애매하면 반드시 묻는다.

| Confidence | 조건 | 행동 |
|-----------|------|------|
| High (≥80) | 트리거 2개+ 매칭, 단일 파이프라인 | Phase 2로 자동 진행 |
| Medium (50-79) | 트리거 1개 매칭 or 복수 파이프라인 경쟁 | AskUserQuestion 필수 |
| Low (<50) | 부분 매칭 or 키워드 1개 | AskUserQuestion 필수 |
| Zero | 매칭 없음 | `/sc:recommend` → 재매핑 → 여전히 없으면 AskUserQuestion |

**동점 처리**: 파이프라인 점수 차 < 15점 → 동점으로 간주 → AskUserQuestion.

**짧은 요청 규칙**: 요청 길이 < 10글자 or 동사 없음 → 의도 재확인 AskUserQuestion 먼저.

### Medium/Low confidence 질문 형식

```
Q: "다음 중 어떤 작업을 원하시나요?"
옵션:
  1. {파이프라인 A} — {한 줄 설명} (Recommended: confidence {N})
  2. {파이프라인 B} — {한 줄 설명} (confidence {N})
  3. 직접 설명해주세요
```

### 짧은 요청 의도 재확인 형식

```
Q: "'{요청 원문}' — 어떤 게 필요하신가요?"
옵션:
  1. {가장 likely한 해석}
  2. {두 번째 해석}
  3. 직접 설명
```
