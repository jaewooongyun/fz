# 스킬 트러블슈팅 가이드

> **Sources (last audited: 2026-11-01 — 사실 정정 5a — research/probe-report 대조 · §2.4 인용을 본문 실제와 맞춤(Claude 4.8 출처는 이력 표기 · GPT 문장은 Astra 한정) · 이전 감사 2026-09-25 — 모델 사실 축: "§2.4 인용 모델을 현행(Fable 5.1·Opus 5.5·GPT-6 Sol)으로 갱신"이라 적었으나 본문은 바뀌지 않았다(이력) · 중복 절을 prompt-optimization 보충 8a 참조로 축약):** `guides/llm-references.md` §1 정본 대조 완료. 그 외 인용은 개별 `[verified:]` 태그 참조.
>
> fz-* 스킬에서 발생하는 일반적인 문제의 진단과 해결 방법.
> Anthropic 32p Skills Guide의 Under/Over-triggering, Instructions Not Followed 패턴 기반.

---

## 1. Triggering 문제 진단

### 1.1 Undertriggering (스킬이 트리거되지 않음)

**증상:**
- 관련 쿼리에서 스킬이 자동 트리거되지 않음
- 사용자가 매번 `/fz-{name}`으로 수동 호출해야 함
- "이 스킬이 있는 줄 몰랐어요" 피드백 발생

**진단:**
1. "Ask Claude" 테스트 실행 (`guides/skill-testing.md` §3)
2. Claude가 description을 정확히 인용하는지 확인
3. 누락된 키워드 식별

**솔루션:**

| 원인 | 조치 |
|------|------|
| 키워드 부족 | description에 기술 용어 추가 (한국어+영어) |
| 트리거 구문 협소 | intent-triggers에 동의어/관련어 확대 |
| 너무 전문적 | 일반적인 표현도 포함 ("고쳐줘" + "fix") |

**Few-shot: fz-search description 개선**

```
BEFORE:
  "프로젝트 코드 구조 분석 스킬"
  → "코드 어디 있어?" 쿼리에 트리거 안 됨

AFTER:
  "프로젝트 코드 탐색 + 구조 분석 + 의존성 추적 스킬.
   Use when exploring code structure, tracing symbol dependencies,
   finding architecture relationships.
   Do NOT use for code modification (use fz-fix or fz-code)."
  → "코드 어디 있어?", "구조 분석해줘", "의존성 추적" 모두 트리거
```

### 1.2 Overtriggering (스킬이 과도하게 트리거)

**증상:**
- 무관한 쿼리에서 스킬이 활성화됨
- 사용자가 스킬을 비활성화하거나 우회함
- 다른 스킬과 충돌 (의도치 않은 스킬이 선택됨)

**진단:**
1. Triggering Test에서 should-NOT-trigger 실패율 확인
2. intent-triggers 패턴이 너무 광범위한지 검토
3. description에 과격한 표현이 있는지 확인

**솔루션:**

| 원인 | 조치 |
|------|------|
| 광범위한 키워드 | 구체적 키워드로 교체 ("코드" → "코드 탐색") |
| 부정 트리거 부재 | "Do NOT use for X (use Y)" 추가 |
| 과격한 표현 | "MUST", "ALWAYS" 제거 (원칙 8 적용) |

**Few-shot: 범위 좁히기**

```
BEFORE:
  intent-triggers:
    - "코드|개발|프로젝트"    # 모든 개발 관련 쿼리에 매칭
AFTER:
  intent-triggers:
    - "탐색|구조|의존성|심볼"  # 탐색 전용 키워드로 한정
    - "explore|structure|dependency|symbol"
```

### 1.3 intent-triggers 중복 충돌

**진단:**
```bash
/fz-manage check   # 항목 #4: intent-triggers 중복 검증
```

**해결 절차:**
1. 중복 키워드 식별 (예: "코드"가 fz-code, fz-fix, fz-search에 동시 존재)
2. 각 스킬의 핵심 키워드와 공유 키워드를 분리
3. 공유 키워드를 더 구체적인 표현으로 교체
4. description의 부정 트리거로 상호 경계 명시

---

## 2. Instructions Not Followed (지시 미준수)

### 2.1 원인 1: 지시가 너무 장황

**증상:** Claude가 SKILL.md의 일부 지시를 무시하거나 순서를 건너뜀.

**솔루션:**
- 산문 → 불릿 포인트로 전환
- 핵심 지시만 남기고 세부는 Level 3 참조로 분리
- 500줄 이하 유지 확인

```
BAD:  "코드를 분석할 때는 먼저 파일 구조를 파악하고, 그 다음에 핵심 함수를
       찾아서 의존성을 추적하는데, 이때 Serena의 find_symbol을 사용하면
       효과적입니다. 그런 다음..."

GOOD: 1. 파일 구조 파악 (Glob)
      2. 핵심 함수 탐색 (mcp__plugin_fz_serena__find_symbol)
      3. 의존성 추적 (mcp__plugin_fz_serena__find_referencing_symbols)
```

### 2.2 원인 2: 핵심 지시가 묻힘

**증상:** 중요한 규칙이 문서 중간에 있어 Claude가 놓침.

**솔루션:**
- 핵심 지시를 문서 앞부분(행동 원칙) 또는 끝부분(체크리스트)에 배치
- Context Rot 근거: 중간 위치 정보에서 성능이 크게 떨어진다 — "performance is often highest when relevant information occurs at the beginning or end of the input context, and significantly degrades when models must access relevant information in the middle of long contexts" [arxiv preprint, 2023-07, v3] (Lost in the Middle, arXiv 2307.03172 · venue 자기보고: TACL · 2023년 모델 기준). 이전 판의 "검색률 30%+ 하락" 수치는 abstract 에 없어 뺐다 [미검증: 본문 미대조]

```
구조: 핵심 지시 (앞) → 세부 Phase (중간) → 체크리스트/Gate (끝)
```

### 2.3 원인 3: 모호한 언어

**증상:** Claude가 지시를 임의로 해석하여 일관성 없는 결과.

**솔루션:**
- 모호한 표현 → 구체적 동사 + 검증 가능한 조건

```
BAD:  "코드 품질을 확인하라"
GOOD: "빌드 성공 여부를 xcodebuild로 검증하라. 실패 시 에러 메시지를 분석하고 수정하라."

BAD:  "적절히 처리하라"
GOOD: "에러 시 테이블의 폴백 전략을 순서대로 실행하라."
```

### 2.4 원인 4: 모델 laziness (검증 건너뜀)

**증상:** Claude가 Gate 체크를 건너뛰거나 검증 없이 완료 보고.

**솔루션:**
- SKILL.md에 과격한 표현을 다시 넣지 않는다 (overtriggering 위험. Claude 4.8 instruction-following consistency로 과격 지시가 그대로 적용될 위험 [verified: anthropic.com/news/claude-opus-4-8] (이력 — 2026-09 당시 기준: 2세대 전 발표문이라 `guides/skill-authoring.md` § 원칙 8: 과격 표현 제거 (instruction-following 일관성) 은 2026-09-06 에 이 근거를 철회했다); GPT-6 Astra(2026-09-11 블로그 — 이전 표기 "GPT-6 계열"은 이력)도 같은 방향 — "what used to require a lot of handholding and scaffolding no longer does" [verified: developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra] (Astra 대상 글 — 현행 Sol 적용은 [미검증]) · 같은 글은 강한 경계 문구 대신 완료 기준을 먼저 정하라고 한다 — "This is where it helps to define completion before starting." [verified: https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra]; Fable 5(Legacy — still available)는 짧은 지시 조향이 공식 권장 — 과격 표현 불필요 [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5]; **Opus 5**(현행 **Opus 5.5** 가 상속)는 여기에 더해 *지시를 겹치는 것 자체*가 비용이다 — 검증 지시는 자체검증과 중복 실행되므로 **삭제**가 권장 [verified: platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5])
- **user prompt** 쪽에 격려 문구를 배치한다 — 배치 전략·문구 예시·공식 근거는 `guides/prompt-optimization.md` 보충 8a(Anti-laziness 배치 전략)가 정본이다

---

## 3. 실행 에러 카테고리

### 3.1 MCP 도구 연결 실패

**증상:** `mcp__plugin_fz_serena__find_symbol` 등 MCP 도구 호출 시 에러.

**Fallback 4-tier 전략:**

| Tier | 도구 | 조건 |
|------|------|------|
| 1 | Serena MCP (LSP 기반) | 기본 시도 |
| 2 | LSP 도구 (스킬 `allowed-tools` 에 있을 때) — 이전 판의 "Context7 MCP (문서 기반)"는 이력 | Serena 실패 시 |
| 3 | Grep/Glob (텍스트 기반) | MCP 전체 실패 시 |
| 4 | 수동 분석 (Read) | 모든 자동화 실패 시 |

> ⚠️ Context7 은 코드 탐색 폴백이 아니다 — 외부 라이브러리·API 의 버전별 문서를 가져오는 도구다: "Context7 pulls up-to-date, version-specific documentation and code examples straight from the source" [verified: https://github.com/upstash/context7]. 라이브러리·플랫폼 API 시그니처를 확인할 때 쓰고, 프로젝트 코드 위치를 찾는 데는 쓰지 않는다. 스킬별 실제 폴백은 그 스킬의 에러 표를 따른다(예: `skills/fz-search/SKILL.md` — Serena 연결 실패 → Grep + Glob).

### 3.2 빌드 실패 반복

**증상:** 구현 후 빌드가 3회 이상 연속 실패.

**래더 전략:**

```
1차 실패: 에러 메시지 분석 + 자동 수정
2차 실패: 전략 변경 (다른 접근법 시도)
3차 실패: 사용자에게 에스컬레이션
```

### 3.3 Large Context Issues

**증상:** 스킬 실행 중 컨텍스트 윈도우 소진, 후반부 지시 무시.

**솔루션:**
- Progressive Disclosure 강화 (Level 3 참조 적극 활용)
- SKILL.md 줄 수 재확인 (500줄 이하)
- 스킬 수 참고: 개수보다 **리스팅 예산**을 본다 — 예산은 모델 컨텍스트의 1%이고 넘치면 가장 덜 호출한 스킬의 description 부터 빠진다(`guides/skill-authoring.md` § Level 1: YAML Frontmatter (항상 로드)) [verified: https://code.claude.com/docs/en/skills]. 스킬별 컨텍스트 비용·호출 빈도는 `/skill-doctor` 로 본다 — "Run `/skill-doctor` to see what each of your skills costs and how often it gets used, so you can decide which ones to turn off" [verified: https://code.claude.com/docs/en/skills]. ⚠️ 2026-11-01 정정: 이전 판의 Anthropic 공식 "20-50 skills is a good range" 인용은 출처를 찾지 못해 뺐다 — 2026 공식 글의 '20-50' 은 eval 과제 수다: "In reality, 20-50 simple tasks drawn from real failures is a great start." [verified: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents]
- 불필요한 모듈 참조 제거
- invoke된 skill은 세션 내내 단일 메시지로 잔존(재read 안 함), compaction 시 token budget 내 재첨부 — 오래된 skill은 compaction 후 누락 가능 [verified: code.claude.com/docs/en/skills]

### 3.4 에이전트 통신 실패

**증상:** Workflow 워커의 반환 누락·스톨, 렌즈 결과 부재.

⛔ **2026-09-18 정정**: 이전 판은 `SendMessage` 의 summary 필드를 처방했다 — 그 도구는 v2.1.178부터
**존재하지 않는다**(`modules/governance.md` § Kill-Switch). 부재 도구를 지시하는 트러블슈팅은
독자를 막다른 길로 보낸다.

⛔ **2026-11-01 정정** — 위 '존재하지 않는다'는 이력(2026-09-18 당시 판단)이고 틀렸다. v2.1.178 에서 없어진 것은
`TeamCreate`/`TeamDelete` 다(Claude Code CHANGELOG 2.1.178 "removed the `TeamCreate` and `TeamDelete` tools").
`SendMessage`·`ListAgents` 는 현존한다 — "Sends a message to another agent: an agent team teammate, a subagent it resumes
by agent ID or name, or one of your other Claude Code sessions" [verified: https://code.claude.com/docs/en/tools-reference]
(세션 간 메시지는 v2.1.224+). 결론은 같다: fz 의 Workflow 워커는 이 도구로 소통하지 않고(OVERRIDE 블록 — P2P 통신 없음)
반환 JSON 으로만 말하므로, 아래 Workflow 경로로 진단한다. `modules/governance.md` § Kill-Switch 에는 SendMessage 서술이 없다.

**솔루션 (Workflow 경로):**
- ⛔ **추측 금지 — `<transcriptDir>/journal.jsonl` 을 먼저 Read** 한다. agent 별 실제 반환값이 1줄씩 기록된다
- 렌즈 회계를 본다: `lensesCompleted` < `lensesExpected` 면 `reviewVerdict` 가 `'partial'` 이고 그 관점은 **적용되지 않았다**
- 대형 입력은 args 가 아니라 **파일 경로**로 전달한다 (`guides/skill-authoring.md` §12 배치·호출 규약)
- 스톨·일시 장애는 **`resume` 우선** — 실패 분기는 §12 판별 표 7종을 따른다

### 3.4b 다관점 검토 프로토콜 위반 (Workflow 경로)

**증상:** 에이전트가 동조 수렴하거나, 독립 분석 없이 합의, Gate 스킵.

| 위반 | 원인 | 대응 |
|------|------|------|
| 동조 수렴 (모든 렌즈 동일 의견) | 초기 생성 호출에 피어 데이터가 주입됨 | ⛔ Workflow 는 **구조적으로 보장**한다 — 초기 생성 호출에 피어 산출을 넣지 않는다(`skill-authoring.md` §12 § TEAM 추론 품질 3원칙). 주입됐다면 스크립트 결함이다 |
| **동종 모델 맹점** (3/3 동일 모델이 동일 이슈 미탐지) | 같은 모델은 같은 지식 갭 공유 | GPT(이종 모델) cross-validation 필수. "diff에 부재가 나타나지 않는" 패턴(상속 체인, optional DI, willSet 연쇄)에서 발생. 사내 앱 PR 교훈 참조 |
| Gate 스킵 | Lead가 Gate를 "선택"으로 인식 | cross-validation.md Gate 절차적 강제 참조 |
| 합의/불합의 미보고 | 반환 schema 에 표현 필드 부재 | **schema 필드로 표현**한다(mutability/severity + evidence) — 프롬프트 요청이 아니라 스키마가 강제한다 |
| 프롬프트 미구조화 | 역할/목표/제약 모호 | OVERRIDE 블록 + schema(=Deliverable) 로 5요소를 채운다 (`skill-authoring.md` §12 § 표준 패턴 3종) |

### 3.5 GPT CLI 관련 에러

**증상:** `scripts/gpt-call.sh review`·`verify` 등 GPT 호출 실패(정문 아래 래퍼 `scripts/gpt-exec.sh` 의 exit 10~14 · 런처 15~17). exit 18(`GPT-OFF`)은 실패가 아니다 — `modules/gpt-strategy.md` § GPT 미사용.

| 에러 | 대응 | 폴백 |
|------|------|------|
| GPT CLI 미설치 | 정문 · 래퍼 · 런처가 exit 18 `GPT-OFF`(CLI 없음) — 실패가 아니다. 쓰려면 설치 안내 | `[GPT 미사용 — CLI 없음]` 표기만 — 대체 검증 없음(`modules/gpt-strategy.md` § GPT 미사용) |
| `gpt-call.sh review` 네트워크 에러 | 래퍼 exit 12(CLI 비정상 종료 · `GPT-IDLE` 포함)는 **측정 실패**다 — 이슈 0건으로 읽지 않는다. 호출부의 GPT 실패 규칙 · `modules/gpt-strategy.md` § 장기 불능 인지 (기간 조건부)를 따른다(정본 `modules/gpt-strategy.md` § 켰는데 실패 — 기존 경로) | 호출부 GPT 실패 규칙 (이전 판의 "exec 모드 kind + diff 인라인 → 수동 리뷰" 대체 경로는 이력 — 정본에 없다) |
| `--output-schema` 파싱 실패 | 래퍼 exit 14(출력이 계약 위반 — 파싱·필수키·타입·enum)는 **측정 실패**다 | 호출부 GPT 실패 규칙 — 실패는 실패로 표기한다 (이전 판의 "Claude 직접 파싱"은 이력 — 정본에 없는 대체 경로) |
| 3-Tier 스킬 디스커버리 실패 | Tier 순차 폴백 | 인라인 프롬프트 (Tier 3) |
| GPT 응답 토큰 제한 초과 | diff 분할 전략 (Medium/Large) | 핵심 파일만 리뷰 |

---

## 4. 디버깅 Quick Reference

### "Ask Claude" 기법

```
질문: "fz-{name} 스킬은 언제 쓰는 거야?"
분석: Claude가 description을 정확히 인용하는가?
조치: 누락 키워드 → description에 추가
상세: guides/skill-testing.md §3
```

### /fz-manage check 항목별 대응

| 항목 | 실패 시 조치 |
|------|------------|
| #1 YAML 필수 필드 | 정본 `modules/governance.md` § 스킬 최소 기준 확인 — L1 공식(`name`·`description`·`allowed-tools`·`user-invocable`) + L2 fz 정책(`metadata.provides`·`metadata.needs`). ⛔ 여기서 목록 재정의 금지 |
| #2 MCP 유효성 | MCP 서버 상태 확인, allowed-tools에서 무효 도구 제거 |
| #3 metadata.provides/metadata.needs 체인 | 누락된 metadata.provides 토큰 추가, metadata.needs 체인 DAG 검증 |
| #4 intent-triggers 중복 | §1.3 절차대로 키워드 분리 |
| #5 스킬 크기 | 500줄 초과 → 모듈 분리 (Level 3) |
| #6 깨진 파일 참조 | 경로 오류 수정, 삭제된 파일 참조 제거 |
| #7 에이전트 파일 | `agents/` 내 YAML 필드 확인 |
| #8 Team MCP 호환 | ⏸ SEMANTIC(런타임 지식 필요) — 팀 불가 MCP 참조 제거 |
| #9 테스트 케이스 | "## 테스트 케이스" 섹션 또는 참조 링크 추가 |
| #10 Triggering 테스트 | should + should-NOT 최소 3개 작성 |
| #11 skill-creator 설치 | ⏸ SEMANTIC(외부 환경) — `run_loop.py` 존재 확인, 미설치는 WARN이지 FAIL 아님 |
| #12 MCP 도구명 (agents) | DETERMINISTIC 4축 — 2형식 문법 · retired 접두 재등장 · 인벤토리 선언 정합 · 본문 Primary ↔ frontmatter 서버 정합 위반을 고친다. 서버가 실제로 떠 있는가는 #2 소관 (이전 판의 "⏸ THRESHOLD(도구명 grammar 미정) — 사람이 대조"는 이력) |
| #13 CLAUDE.md 섹션 참조 | ⏸ SEMANTIC — 참조 대상이 **소비 프로젝트**의 CLAUDE.md인지 플러그인 자신의 것인지 정적 구별 불가(2026-08-09 강등, 오탐 89건 실측) |
| #14 모듈 목차 | 100줄+ 모듈에 `## 목차` 추가. 형식 선례 `modules/review-structural-axes.md`·`guides/harness-engineering.md` |
| #15 금지 패턴 | (이력 — 현행 `--list` 에 #15 가 없다) 측정 파이프의 `head`/`tail` 잘림 제거 → `wc -l` 재실행. ⛔ BAD/GOOD few-shot 예시는 대상 아님 |
| #16 registry ↔ agents | `modules/team-registry.md` Capabilities 표와 `agents/*.md` 양방향 일치 |
| #17 Gate Evidence 패턴 | ⏸ THRESHOLD(정규식 미정) — Gate 체크리스트에 `Evidence:` 행 존재 여부를 사람이 확인 |
| #N1~N14 (lint 신설 — 이전 표기 N1~N6 은 이력) | `--list`로 항목 확인. N1=스키마 $defs 정합 · N2=인벤토리 동기 · N3=줄번호 인용 · N4=ERE alternation · N5=신호 폐기 · N6=루트 앵커 · N7=셸 변수 정의-사용 · N8=목차 앵커 · N9=cross-file § 앵커 · N10=structured-output strict · N11=경량 경로 검증 계약 · N12=`/sc:` 네임스페이스 · N13=memory 필드 재도입 금지 · N14=빈 mktemp 치환 cd |

> ⛔ **항목 목록의 SSOT는 `scripts/lint_contracts.py --list`다.** 위 표는 *실패 시 조치*만 담고 항목 정의를 재정의하지 않는다.

### Serena Fallback 체인

```
1. mcp__plugin_fz_serena__find_symbol        → 심볼 정의 탐색
2. mcp__plugin_fz_serena__find_referencing_symbols → 참조 추적
3. mcp__plugin_fz_serena__get_symbols_overview → 파일 심볼 개요
   ↓ 실패 시
4. Grep → 텍스트 패턴 탐색
5. Glob → 파일 패턴 탐색
6. Read → 수동 파일 읽기
```

---

## 참조

- 테스트 방법론: `guides/skill-testing.md`
- 스킬 작성법: `guides/skill-authoring.md`
- 프롬프트 최적화: `guides/prompt-optimization.md`
- GPT 교차검증: `skills/fz-gpt/SKILL.md`
- 건강 체크: `/fz-manage check`
