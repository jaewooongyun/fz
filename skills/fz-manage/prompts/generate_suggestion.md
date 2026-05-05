# Suggestion Generator Prompt Template

> **컴포넌트**: Lessons-to-Module Pipeline D+4
> **타입**: Claude prompt (LLM 기반 — Parser/Scorer 결과를 받아 구체적 diff 제안 생성)
> **목적**: parsed lesson + scored modules (≥ 0.70)을 입력받아 모듈별 *적용 가능한 변경*을 제안

## 사용법

이 프롬프트는 fz-manage `reflect-to-module` 서브커맨드 내부에서 Claude에게 전달됩니다.
Lead가 다음 변수들을 채워서 Claude에게 SendMessage로 전달:

- `{{PARSED_LESSON}}`: parse_memory.py JSON 출력
- `{{SCORED_MODULES}}`: score_relevance.py JSON 출력 (results filtered ≥ threshold)
- `{{MODULE_CONTENTS}}`: 각 selected 모듈의 *현재* 내용 (Read 결과)

## 프롬프트 본문 (LLM에게 전달)

```
당신은 Lessons-to-Module Pipeline의 Suggestion Generator입니다.

## 입력

### Parsed Lesson (메모리 추출 결과)
{{PARSED_LESSON}}

### Scored Modules (≥ 0.70)
{{SCORED_MODULES}}

### 각 모듈의 현재 내용
{{MODULE_CONTENTS}}

## 작업

각 selected 모듈에 대해 *구체적 diff*를 제안하세요. 다음 5가지 type 중 가장 적합한 하나를 선택:

### Type 1: catalog_addition
- **언제**: 모듈에 *목록/테이블*이 있고, lesson이 새 항목을 추가해야 할 때
- **예**: fz-code SKILL.md 마찰 신호 테이블에 새 항목
- **diff 형태**: 기존 마지막 항목 다음에 새 row 추가

### Type 2: section_add + procedural_call
- **언제**: 에이전트 파일에 *새 절차*가 필요하고 *기존 workflow에 호출*도 박아야 할 때
- **예**: impl-correctness.md에 "Cargo-Cult Detection" 섹션 + Implementation Workflow에 호출 단계 추가
- **diff 형태**: 두 부분 — 새 섹션 추가 + 기존 workflow 변경

### Type 3: bidirectional_extension
- **언제**: 기존 단방향 검증을 *양방향*으로 확장해야 할 때
- **예**: fz-review §검증 4-E 항목 7 "import 제거 작업 시" → "양방향 (제거 방향 + 추가 방향)"
- **diff 형태**: 기존 항목을 *2개 sub-item*으로 분리

### Type 4: perspective_addition
- **언제**: review-quality 같은 에이전트에 *새 분석 관점*이 필요할 때
- **예**: review-quality.md Analysis Perspectives section 8 추가
- **diff 형태**: 기존 마지막 perspective 다음에 새 섹션

### Type 5: file_creation
- **언제**: 신규 파일이 필요할 때 (lint config 등)
- **예**: .swiftlint.yml 신규 생성
- **diff 형태**: 전체 파일 내용 (신규)

## 출력 형식 (각 모듈마다)

```yaml
module: <모듈 경로>
type: <위 5 type 중 하나>
position: <어디에 들어가는지 정확한 위치 — line N 다음 / 섹션 X 안 등>
diff: |
  <- 또는 + 표기로 구체적 변경>
rationale: <이 변경이 lesson의 어느 명제와 정합하는지 — parsed의 core_lesson 또는 signal 인용>
confidence: <0.0~1.0 — Claude 자체 평가>
```

## 중요 규칙

1. **트리밍 비저하 (O6)**: 기존 항목/섹션 *전부 보존*. *추가*만.
2. **원칙+이유 프레이밍 (O7)**: if-then 테이블이 아닌 "X를 추구하라. 이유: Y" 형태.
3. **한국어 + 영어 혼용**: fz 모듈은 한국어 주를 사용. 일관성 유지.
4. **300줄 위반 시 분리**: SKILL.md가 500+ 줄 되면 modules/ 폴더 분리 제안.
5. **자체 정당화 금지**: "더 좋아진다", "improvement"같은 vague 정당화 X. parsed lesson 인용으로만.

## 검증

각 제안 출력 후 *self-check*:

- [ ] diff가 모듈의 현재 내용과 충돌하지 않는가? (위치 정확한가)
- [ ] 기존 항목 전부 보존? (트리밍 비저하)
- [ ] rationale이 parsed.core_lesson 또는 signals와 직접 매핑되는가?
- [ ] type 분류가 정확한가?
- [ ] confidence가 합리적인가? (직접 명시 → 0.9+, 추론 → 0.7)

검증 통과한 제안만 출력. 검증 실패 시 *해당 모듈 SKIP*하고 reason 보고.

## 예시 (19차 메모리 기반, 정답 참조)

Input:
- parsed.id = "import_copy_without_verification"
- parsed.applied_location_explicit = ["fz-code 마찰 신호 카탈로그"]
- parsed.signals.compiler_gap_signal = true
- selected modules: fz-code/SKILL.md, fz-review/SKILL.md, impl-correctness.md, review-quality.md, .swiftlint.yml

Output:

```yaml
module: skills/fz-code/SKILL.md
type: catalog_addition
position: 마찰 신호 카탈로그 끝 (line 270 다음)
diff: |
  + | Redundant Import | 새 파일 작성 시 추가하는 각 `import {Module}` 문에 대해 그 모듈의 알려진 심볼이 파일 내에서 grep 0건 | 형제 파일 패턴 답습 의혹 (cargo-cult). 이유: 형제 파일의 import는 형제 파일의 *사용 심볼*이 정당화한 결과이며, 새 파일은 *자신의 사용 심볼*로 자체 정당화 필요. 검증: 새 파일 작성 후 각 import에 대해 `Grep("ModuleName\\.\\w+\\|<known_typealias>")` 실행 → 0건이면 마찰 보고 (제거/유지 결정은 사용자/Codex 최종) |
rationale: parsed.applied_location_explicit 직접 명시 + parsed.core_lesson "각 import의 실제 사용 심볼을 verify"
confidence: 0.95

---

module: agents/impl-correctness.md
type: section_add + procedural_call
position: Source Fidelity 섹션 다음, Implementation Workflow 직전 / Workflow 4번 단계에 호출 추가
diff: |
  + ## Cargo-Cult Detection (새 파일 작성 시)
  + 
  + 새 파일을 형제 파일 패턴 답습으로 작성할 때 *맥락 검증* 의무.
  + 이유: 형제 파일의 import/가드/유틸 호출은 형제 파일의 *사용 심볼*이 정당화한 결과이며,
  + 새 파일은 *자신의 사용 심볼*로 자체 정당화 필요.
  + 
  + 절차 (마찰 신호 카탈로그 "Redundant Import" 항목과 정렬):
  + 1. 새 파일 작성 후 각 `import {Module}` 문에 대해 `Grep("ModuleName\\.\\w+\\|<known_typealias>")` 실행
  + 2. 0건이면 → "Redundant Import" 마찰 신호로 보고
  + 3. 제거/유지 결정은 사용자/Codex 최종 판정
  + 
  + Implementation Workflow:
  + 4. **새 파일 작성 시**: Cargo-Cult Detection 절차 실행 (위 섹션 참조)
rationale: parsed.applied_location_explicit는 fz-code인데 *작성 단계 인지 보강*은 cascade로 impl-correctness 필요. parsed.signals.fan_out_count_estimate ≥ 1 → 다층화 정합
confidence: 0.92

---

(이하 fz-review/review-quality/.swiftlint.yml 동일 형식으로...)
```

## 마지막 단계: 사용자 적용 안내

5개 제안 모두 출력 후, 각 변경을 *사용자가 직접 적용할 수 있도록* 다음 형식 첨부:

```bash
# Apply suggestions:
# 1. Read each diff above and review
# 2. Apply manually OR
# 3. Pipe to fz-manage apply: cat suggestions.yaml | fz-manage apply --review
```

⛔ **자동 적용 금지** — Codex micro-eval (D+5 Reviewer) 검증 통과 + 사용자 명시 승인 필수.

이는 메모리 23차 (self-review blind spot) 방어:
- Generator (현재): 제안만, 적용 X
- Evaluator (Codex): 외부 검증
- Final Authority (사용자): 적용 결정
```

## Codex micro-eval 입력 (D+5 Reviewer로 전달)

각 제안에 대해 다음 평가:

```
이 제안이 다음 두 출처에 부합하는가?
1. 메모리 19차: feedback_import_copy_without_verification.md (전문 첨부)
2. 모듈의 *현재 내용* (전문 첨부)

verdict: agree / disagree / partial / needs_verification
근거: <원문 인용 가능한 형태로>

추가 검증:
- 트리밍 비저하 위반 여부 (기존 항목 변경/제거 있는가?)
- 원본 메모리에 없는 *추가 정당화* 추가 여부
- 제안된 type 분류의 정확성
```
