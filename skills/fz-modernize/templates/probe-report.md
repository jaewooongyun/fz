# Probe Report (Phase 1 Template)

> **사용법**: 본 템플릿을 `{WORK_DIR}/probe/probe-report.md`로 복사 후 채우기.
> **트리거**: 외부 자료 리서치 결과 정리 시.

## 0. 메타데이터

| 항목 | 값 |
|------|-----|
| 수집 일시 | YYYY-MM-DD |
| Tier 합의 (사용자) | Tier 1 only / **Tier 1+2** / Tier 1+2+3 / 사용자 직접 제공 |
| 검색 쿼리 | (5+ 쿼리 나열) |

## A. 공식 자료 (Tier 1)

> 회사 공식 release notes / engineering 블로그 / docs.

| # | 자료 | URL | 발행일 | 핵심 인용 |
|---|------|-----|-------|---------|
| A1 | (제목) | (URL) | YYYY-MM-DD | "..." |
| A2 | | | | |
| A3 | | | | |

### Status 분류

| Source ID | Status | 비고 |
|-----------|--------|-----|
| A1 | official | 공식 release page |
| A2 | official | engineering 블로그 |

## B. 학술 논문 (Tier 2)

> peer-reviewed 또는 arxiv preprint.

| # | arxiv ID | 제목 | 저자 | Status | 핵심 |
|---|---------|------|------|--------|-----|
| B1 | | | | `[arxiv preprint, YYYY-MM]` | |
| B2 | | | | `[ICLR YYYY Oral / peer-reviewed]` | |
| B3 | | | | | |

### 학술 라인 연결성 (있을 경우)

- 같은 저자/연구소의 논문 라인 명시 (예: Stanford NLP DSPy 학파 — Khattab 주저자)
- fz 설계와의 직접 연결성

## C. 외부 도구 / SDK (Tier 1)

| # | 자료 | URL | 발행일 | 핵심 |
|---|------|-----|-------|-----|
| C1 | | | | |
| C2 | | | | |

## D. 프롬프트/하네스 엔지니어링 (학술 + 공식 외)

> 예: "프롬프트 잘 짜는 법" / "하네스 설계 패턴" / "Context Engineering 최신" 등 학술/공식 외 권위 자료.

| # | 자료 | URL | 출처 | 핵심 |
|---|------|-----|------|-----|
| D1 | | | | |

## E. 도구 / SDK 변경 (Codex CLI, Claude Code, Agent SDK 등)

> 외부 도구의 버전 변경 / 새 기능 / breaking change.

| # | 자료 | URL | 버전 | 핵심 |
|---|------|-----|------|-----|
| E1 | | | | |

## F. 멀티 에이전트 프레임워크 (LangGraph, AutoGen, CrewAI 등)

> 멀티 에이전트 시스템 패턴 / 학술 + 산업 best practices.

| # | 자료 | URL | 프레임워크 | 핵심 |
|---|------|-----|----------|-----|
| F1 | | | | |

## G. Community / Practitioner (Tier 3 — 사용자 합의 시만)

| # | 자료 | URL | 표기 |
|---|------|-----|-----|
| G1 | | | `[community: ...]` (verified 단독 금지, AC9) |

## 영향 예상 표

> 어느 가이드의 어느 line이 stale → 어느 자료로 해소.

| 가이드 | 영향 | 우선순위 | 해소 자료 |
|-------|------|--------|---------|
| (가이드명) | High/Medium/Low | 1/2/3순위 | (A1, B2 등) |

## 결정적 발견 (있을 경우)

> 단순 자료 수집 외 추가 인사이트.

1. **(인사이트 1)**: ...
2. **(인사이트 2)**: ...

## 다음 단계

→ Phase 2 (Audit): `audit/audit-report.md` 작성
