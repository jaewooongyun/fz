# Design: Lessons-to-Module Pipeline

> **Status**: Draft (구현 승인 대기)
> **Author**: Claude (fz-plan / fz-code cycle, 2026-04-24)
> **Source**: MEMORY.md 17차 (Pre-Gate Failure + Reflection Gap) + 18차 (Scope Inflation Defense)
> **Scope**: 설계 전용 — 이 문서는 **구현 시작 트리거가 아님**. 사용자 명시 승인 후 별도 워크플로우 필요.

---

## 1. 문제 정의

MEMORY.md의 "반성 기록" 표(1~18차)는 각 인시던트로부터 **재발 방지 규칙**을 도출한다.
그러나 도출된 규칙이 실제로 fz-plugin의 스킬/모듈/가이드에 **반영**되었는지 검증하는 자동화 경로가 없다.

### 17차 교훈의 실증 (MEMORY.md 17차 항목)

> "패턴 1/3/4가 peer-review-learnings.md에 '즉시 반영'으로 기록됐지만 fz 모듈 미반영 — ASD-1111 자체가 이 메타 패턴의 실증 사례"

즉 **기록과 반영의 괴리**가 존재한다. 메모리 항목이 존재해도 실제 스킬 내부에 규칙이 새겨지지 않으면 게이트가 작동하지 않는다.

### 18차 교훈의 실증

> "ISSUE-016: grep 명령 `-n` 누락 + anchored regex 0건인데 '20+건' 주장 → 16차 재발"

16차 교훈(실측 의무화)이 기록되었음에도 **다음 작업에서 동일 패턴이 재현**되었다. 기록 ≠ 내재화.

---

## 2. 목표

`/fz-manage reflect-to-module` 서브커맨드를 신설하여, 반성 기록을 **스킬/모듈 수정 제안**으로 자동 변환한다.

### 성공 기준

| 기준 | 측정 |
|------|------|
| 누락 매핑 검출 | 반성 기록 N건 중 연관 SKILL.md/modules 미반영 비율 |
| 제안 정확도 | 사용자가 "적용" 선택한 제안 / 전체 제안 |
| 가짜 제안(false positive) 비율 | "무관함" 판정 수 / 전체 제안 |
| 실행 시간 | 18개 반성 기록 전수 스캔 < 60초 |

---

## 3. 입력/출력 계약

### 입력

경로는 **활성 프로젝트/플러그인 루트 기준 상대경로**로 해석한다. 절대경로 하드코딩 금지 (마켓플레이스 배포 시 이식성 훼손).

- **반성 기록 소스**: `${CLAUDE_PROJECT_MEMORY}/MEMORY.md` (기본값: Claude Code 하네스가 제공하는 활성 프로젝트의 `memory/MEMORY.md` 경로)
  - 미존재 시 `--memory-file <path>` 인자로 명시 요구
- **대상 파일 인덱스** (PLUGIN_ROOT는 `fz-plugin` 설치 경로에서 동적 해석):
  - `${PLUGIN_ROOT}/skills/*/SKILL.md`
  - `${PLUGIN_ROOT}/modules/*.md`
  - `${PLUGIN_ROOT}/guides/*.md`
- **선택 인자**:
  - `--memory-file <path>` (반성 기록 파일 명시 지정)
  - `--plugin-root <path>` (PLUGIN_ROOT 재지정, 기본: 자동 감지)
  - `--since N차` (특정 반성 기록 이후만)
  - `--topic <keyword>` (특정 주제로 필터)
  - `--dry-run` (제안만, Edit 금지)

> **경로 해석 원칙**: 구현 시 현재 fz-manage 스킬이 사용하는 경로 해석 루틴(plugin install root 감지 + 활성 project memory 경로)을 재사용. 본 설계는 단일 머신 테스트용 하드코딩을 금지한다.

### 출력

```json
{
  "lesson_id": "17차",
  "lesson_summary": "Pre-Gate Failure + Reflection Gap",
  "matched_assets": [
    {
      "path": "skills/fz-manage/SKILL.md",
      "relevance_score": 0.82,
      "reason": "fz-manage가 반성 기록 관리 역할이므로 reflect-to-module 서브커맨드가 여기 위치",
      "suggested_diff": "..."
    },
    {
      "path": "modules/lead-reasoning.md",
      "relevance_score": 0.74,
      "reason": "Pre-Gate Failure 패턴이 reasoning layer에 기록되어야 함"
    }
  ],
  "orphan_lessons": [],
  "verdict": "needs_review"
}
```

---

## 4. 하위 컴포넌트 설계

### 4.1 Memory Parser

MEMORY.md의 "반성 기록" 테이블을 구조화. 각 행을 `{id, title, core, applied_location, feedback_links}`로 변환.

**핵심 도전**: MEMORY.md 항목에 붙은 링크(`[feedback_...md](...)`)를 실제 파일 존재와 대조. 부재 링크는 `orphan_reference`로 플래그.

### 4.2 Relevance Scorer

각 반성 기록과 각 스킬/모듈 사이의 관련도를 점수화.

**스코어링 입력**:
- 키워드 매칭 (반성 제목/본문 ↔ 파일 섹션 헤딩)
- 파일이 이미 해당 `feedback_*.md`를 참조하는지 (인용 가중치)
- 파일의 역할 vs 반성 주제 적합성 (예: fz-review 파일은 리뷰 관련 반성과 높음)

**스코어 임계치**:
- ≥ 0.70 → `high_relevance` (수정 제안 생성)
- 0.50 - 0.69 → `medium` (참조 제안만)
- < 0.50 → 제외

### 4.3 Suggestion Generator

관련도 높은 파일에 대해 구체적 편집 제안.

**제안 유형**:
- **Gate 추가**: `- [ ] ⛔ <반성 요지>를 체크?` 라인을 가장 가까운 Gate 섹션에 삽입
- **마찰 신호 추가**: fz-code의 "구현 마찰" 테이블에 행 추가
- **참조 링크 추가**: "참조: `memory/feedback_<lesson>.md`" 줄 삽입
- **No-op 태그**: 이미 반영된 경우 `[already_applied]` 표시

### 4.4 Scope Inflation Detector (18차 교훈 전용)

Plan v{N}에서 v{N+1}로 진화할 때 복잡도 5차원(Scope/Depth/Risk/Novelty/Verification) 점수가 2배 이상 증가하면 경고.

**동작 방식**:
- `/fz-plan` Phase 3 (Feedback Integration) hook
- 점수 계산 알고리즘: 각 차원에 대해 특정 마커 카운트
  - Scope: 영향 파일 수
  - Depth: Step 수
  - Risk: 리스크 매트릭스 행 수
  - Novelty: 신규 모듈/타입 수
  - Verification: Gate 수 + evidence 요구 수
- 2배 초과 시 AskUserQuestion: "분할/수용/포기"

---

## 5. 구현 비용 추정

| 컴포넌트 | 복잡도 | 의존성 |
|---------|-------|-------|
| Memory Parser | S | 없음 (MEMORY.md 포맷 안정) |
| Relevance Scorer | M | 임계치 튜닝 필요 (실측 기반) |
| Suggestion Generator | M | Edit 제안 포맷 표준화 |
| Scope Inflation Detector | L | Plan 구조 파싱 + 5차원 정의 명확화 |
| 통합 (서브커맨드) | S | fz-manage 스킬 확장 |

**총 추정**: M+ (약 1-2일 구현 + 1일 튜닝)
사용자가 `/sc:estimate`로 재검증 권장.

---

## 6. 리스크 & 대안

### 리스크

| 리스크 | 발생 조건 | 완화 |
|-------|----------|------|
| False positive 과다 | Relevance 임계치가 너무 낮음 | 초기 0.70 보수적 시작 → 사용자 피드백으로 튜닝 |
| 자동화가 오히려 scope 팽창 유발 | Detector가 정상 계획도 "inflation"으로 판정 | Scope Inflation Detector는 **경고만**, 자동 차단 금지 |
| MEMORY.md 포맷 변경 시 파서 붕괴 | 사용자가 수동 편집 | 파서에 frontmatter 버전 체크 + 실패 시 명확한 에러 |
| 순환: 메타 도구화 자체가 Scope Inflation | 본 설계 구현이 스킬 생태계를 다시 복잡하게 만듦 | Wave D 격리 + 사용자 명시 승인 전 구현 금지 (이 문서의 존재 이유) |

### 대안

- **대안 1**: 완전 수동 (`/fz-memory reflect` 같은 형태로 사용자가 반성→스킬 매핑을 직접 주장)
  - 장점: 자동화 복잡도 제거 / 단점: 17차 "기록-반영 괴리" 재발 가능
- **대안 2 (채택)**: 자동 제안 + 사용자 승인 필수 (본 설계)
- **대안 3**: 완전 자동 + 자동 Edit
  - 거부 사유: 실수 발생 시 되돌리기 어려움, 18차 Scope Inflation 위험

---

## 7. 다음 단계 (사용자 승인 후)

1. **Pilot 반성 1건**: 18차 교훈만 대상으로 scorer/generator 시제품 구현
2. **A/B 비교**: 수동 매핑 결과 vs 자동 제안 결과 비교 (10건 샘플)
3. **임계치 튜닝**: precision/recall 80% 이상 달성 시 전체 18건 확장
4. **서브커맨드 통합**: `/fz-manage reflect-to-module` 정식 배포
5. **회고**: 배포 후 1개월 "기록 vs 반영" 지표 측정, 17차 gap 해소 확인

---

## 8. 승인 요청

본 설계 문서는 **구현 착수 승인 요청**이다. 사용자는 다음 3가지 경로 중 선택:

| 경로 | 설명 |
|------|------|
| **A. Pilot 구현** | 18차 교훈 대상 시제품 구현 (약 1일) |
| **B. 설계 보류** | 수동 반영 프로세스 유지, 이 문서는 향후 참조 |
| **C. 대안 1** | 반성→모듈 수동 매핑 스킬만 간단히 추가 |

> 본 설계는 **자체가 Scope Inflation 위험**을 내포한다 (18차 교훈의 적용 대상). 승인 전 "이것이 진짜 필요한가?" 재검토 권장.
