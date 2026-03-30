---
name: fz-gemini
description: >-
  This skill should be used when the user wants to verify or challenge code/plans using Gemini CLI.
  Make sure to use this skill whenever the user says: "gemini", "제미나이", "제미나이로 검증",
  "다른 관점", "대안 제시", "devil's advocate", "위험 분석", "장문 분석",
  "gemini review", "gemini verify", "제미나이 리뷰".
  Covers: Gemini CLI, Devil's Advocate, 대안 관점 리뷰, 장문 분석, 방향성 도전, 보안 리뷰.
  Do NOT use for Codex/GPT verification (use fz-codex) or direct code review (use fz-review).
user-invocable: true
argument-hint: "[review|verify|challenge] [대상]"
allowed-tools: >-
  Bash(gemini *), Read, Grep
composable: true
provides: [verification]
needs: [none]
intent-triggers:
  - "gemini|제미나이|대안|devil"
  - "gemini|devil's advocate|alternative perspective"
model-strategy:
  main: null
  verifier: sonnet
---

# /fz-gemini - Gemini CLI Devil's Advocate 스킬

> **행동 원칙**: Gemini(이종 모델)의 독립적 시각으로 Claude의 blind spot을 보완한다. "이게 실패할 가장 큰 위험은?"을 묻는 도전자 역할.

## 개요

> 서브커맨드: review | verify | challenge

- **Gemini CLI** (v0.35+, OAuth GCA 인증) 기반
- **Devil's Advocate**: Claude가 놓치는 관점을 독립적으로 제시
- **1M Context**: 대규모 diff, 장문 계획서 분석에 특화
- **근거**: X-MAS(arxiv 2505.16997) — 이종 모델 조합 시 최대 47% 성능 향상

## 사용 시점

```bash
/fz-gemini review                    # 현재 diff를 Gemini로 리뷰
/fz-gemini verify "계획 검증해줘"     # 계획서를 Gemini로 검증
/fz-gemini challenge "이 설계 도전"   # Devil's Advocate 모드
```

## 서브커맨드

### review — 코드 리뷰

```bash
cd "$GIT_ROOT" && git diff "$BASE_BRANCH"...HEAD > /tmp/fz-gemini-diff.txt
gemini -p "다음 diff를 리뷰하세요. 특히:
1. 이 접근의 근본적 대안은 무엇인가?
2. 이 코드가 실패할 가장 큰 위험은?
3. Claude(다른 AI)가 놓칠 가능성이 높은 이슈는?" < /tmp/fz-gemini-diff.txt
```

### verify — 계획 검증

```bash
gemini -p "다음 구현 계획을 검증하세요. 특히:
1. 빠진 단계는 없는가?
2. 영향 범위가 과소평가된 곳은?
3. 이 계획이 실패할 가장 큰 시나리오는?" < "$PLAN_FILE"
```

### challenge — Devil's Advocate

```bash
gemini -p "다음 설계 결정에 대해 Devil's Advocate 역할을 하세요.
1. 이 접근의 근본적 약점 3가지
2. 완전히 다른 접근법 2가지 제안
3. 6개월 후 후회할 가능성이 있는 결정은?" < "$TARGET_FILE"
```

## Gemini 특화 활용

| 상황 | 활용 | 근거 |
|------|------|------|
| 대규모 diff (>8000줄) | Gemini 1M context | Codex보다 긴 컨텍스트 처리 |
| 방향성 도전 | Devil's Advocate | Claude와 다른 학습 데이터 기반 관점 |
| 보안 리뷰 | OWASP 관점 | 독립적 보안 분석 |

## Base Branch 결정

fz-codex와 동일한 로직: `modules/codex-strategy.md` → "Base Branch 결정" 참조

## 결과 보존

- ASD 활성: `{WORK_DIR}/verify/gemini-{서브커맨드}-{날짜}.md`
- 비ASD: `write_memory("fz:gemini:last", "서브커맨드: {cmd}. 핵심 발견: {요약}")`

## Boundaries

**Will**: Gemini CLI를 활용한 독립 검증, 대안 제시, 위험 분석
**Will Not**: 코드 직접 수정 (→ fz-code), Claude 단독 리뷰 (→ fz-review)
