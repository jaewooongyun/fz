# Team Core Protocol

> 모든 팀 스킬이 로드하는 공통 모듈. 2.5-Turn Protocol + 절대 규칙 + 모델 전략.
> 각 스킬은 이 모듈 + 자기 패턴 파일 1개만 로드한다.

---

## 절대 규칙

1. TEAM 모드 = 반드시 `TeamCreate` 사용. standalone Task(팀 외부 에이전트 단독 실행) 금지.
   - SOLO 모드(Lead가 에이전트 1명만 운용)는 허용 (예: /fz-fix → impl-correctness만).
   - BATCH 모드 = worktree 격리. TeamCreate 미사용. 독립 SOLO 병렬. (참조: modules/execution-modes.md)
2. 모든 파일 경로는 절대 경로 사용 (에이전트는 홈 디렉토리에서 시작).
3. 완료 시: `shutdown_request` → 프로세스 종료 확인 → `TeamDelete`.
4. Lead는 별도 에이전트 파일이 아닌 역할 모드 (스킬별 전환).
5. ASD 폴더 활성 시: `{phase}/*-team.md`에 에이전트 간 핵심 통신 요약을 기록한다. 참조: `modules/context-artifacts.md`
6. **⛔ Lead Checkpoint Protocol**: 에이전트 완료 보고 수신 후, Lead는 반드시 아래 순서를 실행한다. 순서 건너뛰기 금지.
   ```
   에이전트 "Step N 완료" 보고 수신
   → ⛔ 체크포인트 기록 (ASD: 파일, 비ASD: write_memory)
   → ⛔ Codex 교차 검증 (/fz-codex check — TEAM 모드 필수)
   → 빌드 검증 (modules/build.md)
   → 다음 Step 배정 또는 Gate 판정
   ```
   - Codex 실패 시: 재시도 1회 → 실패 사실 기록 후 /sc:analyze 폴백
   - compact 전에 체크포인트가 없으면 복원 불가 — **기록이 검증보다 선행**

---

## 2.5-Turn Protocol

모든 팀 통신의 기본 프로토콜. 진짜 상호 피드백을 보장하면서 비용을 제한한다.

### Round 1: 분석 + 공유
- 모든 에이전트: 자기 Lens로 독립 분석 수행
- 분석 완료 → 피어에게 `SendMessage` (초안 공유)

### Round 2: 피드백 + 수정
- 피어의 분석을 읽고 피드백 작성
- 자기 분석을 피드백 반영하여 수정
- 수정안 + 피드백을 피어에게 `SendMessage`

### Round 0.5: 최종 보고
- 피어 피드백까지 반영한 최종안 작성
- Lead에게 `SendMessage` (최종 보고)

### 토폴로지

| 팀 크기 | 토폴로지 | R1 | R2 | R0.5 | 합계 |
|---------|---------|-----|-----|------|------|
| 2명 | Mesh (직접 통신) | 2 | 2 | 2 | 6 |
| 3명 | Star-enhanced (Supporting→Primary) | 4 | 4 | 3 | 11 |
| 4명 | Star-enhanced | 6 | 6 | 4 | 16 |

- 2명: Mesh — 직접 통신
- 3명+: Star-enhanced — Supporting은 Primary를 경유
- `--deep`: Full Mesh 허용 (3.5-Turn 확장, Round 3 추가)

### --deep 확장 (3.5-Turn)
```
[Round 3] Supporting 간 직접 교차 토론 1회
[Round 0.5] 최종 보고 갱신
```
--deep 4명: ~20 메시지 (Star 16 + Round 3 추가분)

### 교착 처리
- Round 2에서 합의 불가 → Round 0.5에서 각자 의견 + 불일치 사항을 Lead에게 보고
- Lead가 즉시 판정 (에이전트 간 추가 토론 안 함)
- Primary 통합에서 충돌 해소 불가 → Lead에게 "선택지 A/B" 에스컬레이션

---

## 모델 전략

2-Tier: opus(핵심) + sonnet(나머지). haiku 사용하지 않음.

| 역할 | 모델 | 조건 |
|------|------|------|
| Lead | opus | 항상 |
| Primary Worker | opus | 팀 내 핵심 산출물 생산자 (도메인당 1명) |
| Supporting | sonnet | 나머지 전부 |
| Codex CLI | gpt-계열 | cross-model 다양성 (Lead가 직접 실행) |

승격 원칙: Lead(O) + Primary(O) = 최대 opus 2개. 나머지 전부 sonnet.

---

## MCP 접근성

| 도구 | Team agent | Lead 전용 |
|------|:---------:|:---------:|
| serena, context7, sequential-thinking | O | O |
| github, atlassian, xcodebuild, ToolSearch | X | O |

Lead 전용 도구가 필요한 경우: Lead가 조회 후 `SendMessage`로 결과 전달.

---

## 팀 생성 절차

```
1. TeamCreate(team_name, description)
2. Agent 스폰 — team-registry.md 참조하여 도메인별 에이전트 수집
   - Primary → model: opus
   - Supporting → model: sonnet
3. TaskCreate로 작업 목록 생성
4. 각 에이전트에 SendMessage로 분석 대상/컨텍스트 전달
5. 2.5-Turn Protocol 실행 (패턴 파일 참조)
6. Lead: 최종 보고 수신 → 통합 판단
7. 완료: shutdown_request → TeamDelete
```

---

## 패턴 파일 참조

각 스킬은 자기 도메인에 맞는 패턴 파일 1개만 로드:

| 스킬 | 패턴 파일 |
|------|----------|
| /fz-discover | patterns/adversarial.md |
| /fz-plan | patterns/collaborative.md |
| /fz-code | patterns/pair-programming.md |
| /fz-review, /fz-peer-review | patterns/live-review.md |
| /fz-search | patterns/cross-verify.md |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-plan | 팀 프로토콜 + 모델 전략 |
| /fz-code | 팀 프로토콜 + 모델 전략 |
| /fz-review | 팀 프로토콜 + 모델 전략 |
| /fz-peer-review | 팀 프로토콜 + 모델 전략 |
| /fz-search | 팀 프로토콜 + 모델 전략 |
| /fz-discover | 팀 프로토콜 + 모델 전략 |

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
