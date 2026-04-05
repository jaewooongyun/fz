# System Reminders Policy

> Instruction fade-out 대응. 20-30턴 후 시스템 프롬프트 지침이 약해지는 현상을 완화한다.
> 출처: OpenDev 논문 (arxiv 2603.05344), Anthropic Harness Design (2026.03)
> 참조: `guides/harness-engineering.md` §3 기둥 3

## 원칙

- **이벤트 기반 우선**: 불필요한 노이즈 방지. 조건 충족 시에만 리마인더 주입.
- **Low-frequency backstop**: 트리거가 전혀 안 걸리는 "조용한 장기 세션"에서도 최소 리마인더 보장.
- **default + exception**: 강제 규칙이 아닌 기본 휴리스틱. urgency 등 예외 시 비활성 가능.

## 트리거 기반 리마인더

| # | 트리거 조건 | 리마인더 내용 | 근거 |
|---|-----------|-------------|------|
| T1 | 파일 수정 **5개+** 도달 | "CLAUDE.md Architecture 규칙: 상위→하위만 참조. 현재 변경 범위가 넓어지고 있습니다." | 반성 5차: 영향 분석 불완전 |
| T2 | Gate 실패 **1회+** | "Gate 체크리스트 전체 재확인. 실패 항목: {항목명}" | 반성 4차: Gate 바이패스 |
| T3 | 제거/리팩토링 작업 중 **10턴+** | "Implication Scan 수행했는가? Q-WHY: 이 코드가 존재하게 된 이유가 해소됐는가?" | lead-reasoning.md |
| T4 | TEAM 에이전트 완료 보고 수신 | "Lead Checkpoint Protocol 순서: 체크포인트 → Codex → [Implication] → 빌드 → 다음" | team-core.md Rule 6 |

## Low-frequency Backstop

```
DEFAULT: 30턴마다 1회 핵심 규칙 리마인더
  내용: "현재 {N}턴 진행 중. 핵심 규칙 확인:
         - weak var는 optional chaining 사용 (Code Conventions)
         - 파일 수정 전 반드시 Read (구현 도구 원칙)
         - 빌드 검증 후 다음 Step (Gate 3 전제조건)"

EXCEPTION: urgency 모드 ("빠르게", "급해") → backstop 비활성
EXCEPTION: SOLO + 5턴 이하 세션 → backstop 불필요
```

## 참조 스킬

| 스킬/모듈 | 참조 이유 |
|----------|----------|
| fz-code | 구현 절차에서 T1/T3 트리거 감지 |
| team-core.md | T4 Lead Checkpoint에서 참조 |
| cross-validation.md | Gate 삽입 규칙에서 참조 |
| lead-reasoning.md | T3에서 Implication Scan 연결 |

## 측정

- 리마인더 발동 횟수 → session-metrics.md에 기록
- 발동 후 Gate 통과율 변화 → Ablation 데이터로 활용
