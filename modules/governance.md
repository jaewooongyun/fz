# 거버넌스 프레임워크 (Governance)

> fz-* 생태계의 변경 통제, 품질 게이트, 긴급 정지 정책.

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | kill-switch 판단 |
| /fz-manage | 거버넌스 프레임워크 전체 참조 |

## Kill-Switch

파이프라인 실행 중 긴급 정지가 필요한 상황에서의 행동 규칙.

### 긴급 정지 조건

| 조건 | 판단 기준 | 행동 |
|------|----------|------|
| 무한 루프 감지 | 동일 Gate 3회 연속 실패 | LOOP 에스컬레이션 래더 L4 → 사용자 에스컬레이션 |
| 팀 교착 | 에이전트 간 3라운드 내 합의 불가 | Lead가 최종 판단 or 사용자 에스컬레이션 |
| 리소스 초과 | 에이전트 5개 이상 동시 실행 | 추가 스폰 차단 + 기존 작업 완료 대기 |
| 의도 이탈 | 실행 결과가 원래 요청과 무관 | 파이프라인 중단 + 사용자 확인 |

### Kill-Switch 실행 절차

1. 조건 감지 → 현재 Step 완료 대기 (진행 중 작업 보호)
2. 팀 모드 시: 전체 에이전트에 `shutdown_request` 전송
3. 사용자에게 상황 보고 + 선택지 제시 (재시도/스킵/중단)
4. 중단 선택 시: TeamDelete + 부분 산출물 보존

## Hook 최소 강제 권고

사용자 환경 `settings.json`에 빌드 검증 Hook 설정을 권장한다. "빼먹을 수 없는" 최소 게이트:
- PostToolUse(Write/Edit) → `xcodebuild build` 자동 트리거
- PreToolUse(Bash: git push) → 커밋 전 검증 확인
> Hook은 fz 파일 밖이므로 "권고"로만 제시. 참고: Carlini "환경 설계 > 직접 감독"

## 변경 통제

### 변경 영향 등급

| 등급 | 대상 | 예시 | 검증 |
|------|------|------|------|
| L1 (경미) | 단일 스킬 본문 | 오타 수정, 문구 개선 | 자체 검증 |
| L2 (중간) | YAML frontmatter, 에이전트 | description 변경, 도구 추가 | `/fz-skill eval` |
| L3 (중대) | 공유 모듈, 가이드, 템플릿 | team-core.md 규칙 변경 | `/fz-manage check` + 영향 스킬 확인 |

### L3 변경 시 필수 절차

1. 영향 범위 분석: `Grep("{모듈명}", ".claude/")` → 참조 파일 목록
2. 변경 전 상태 기록 (ASD 폴더 활성 시)
3. 변경 실행
4. `/fz-manage check` → 전체 건강 체크
5. 영향받는 스킬 개별 확인

## 품질 게이트

### 스킬 최소 기준

| 항목 | 기준 | 근거 |
|------|------|------|
| YAML 필수 필드 | name, description, allowed-tools, provides, needs | Progressive Disclosure L1 |
| Description 4요소 | what + when + when-not + 한영키워드 | 트리거 정확도 |
| 크기 제한 | ≤500줄 | Progressive Disclosure L2 |
| Boundaries | Will/Will Not + 대안 | 범위 명확화 |
| 에러 대응 | 테이블 존재 | 자율 복구 |

### Utility 스킬 예외

Query/Utility 스킬(fz-commit, fz-pr, fz-new-file 등)은 Phase/Gate/Few-shot 면제.
단, Description 4요소와 Boundaries는 필수.

## Truth-of-Source 정책

생태계 내 동일 정보가 여러 파일에 존재할 때의 우선순위:

| 정보 | Truth-of-Source | 동기화 대상 |
|------|----------------|------------|
| 팀 구성 (에이전트 목록) | 스킬 YAML `team-agents` | team-registry.md, patterns/*.md |
| 에이전트 도구 | 에이전트 YAML `tools` | 본문 설명 |
| 파이프라인 정의 | modules/pipelines.md | fz SKILL.md 인라인 |
| 평가 기준 | guides/skill-testing.md | fz-skill eval, fz-manage benchmark |

동기화 불일치 발견 시: truth-of-source를 기준으로 나머지를 수정.

## 모듈 분리 기준

스킬/모듈이 아래 조건을 만족하면 분리를 검토한다.

| 기준 | 임계값 | 분리 방법 |
|------|--------|----------|
| 크기 | 500줄 초과 | 독립 주제를 `.claude/modules/`로 추출 |
| 참조 빈도 | 3개+ 스킬에서 참조 | 공유 모듈로 승격 |
| 주제 독립성 | 스킬 본문과 다른 관심사 | 별도 모듈로 분리 |

### 분리 우선순위

1. **크기 초과 + 참조 빈도 높음** → 즉시 분리 (가장 높은 ROI)
2. **크기 초과 + 참조 빈도 낮음** → 스킬 내 섹션 축소 우선 시도
3. **크기 미초과 + 참조 빈도 높음** → 공유 모듈로 승격 검토
4. **크기 미초과 + 참조 빈도 낮음** → 현상 유지

## 설계 원칙

- Progressive Disclosure Level 3 (거버넌스 판단 시에만 로드)
- 500줄 이하 유지
