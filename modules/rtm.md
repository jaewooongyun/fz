# Requirements Traceability Matrix (RTM)

> 요구사항 → Step → 검증의 추적성 보장. plan이 생성, code가 갱신, review가 검증.

## RTM 형식

```markdown
## Requirements Traceability Matrix

| Req-ID | 요구사항 | Step | 검증 방법 | 상태 |
|--------|---------|------|----------|------|
| R1 | {요구사항 설명} | Step {N}, {M} | {빌드/테스트/확인} | pending |
```

## 상태 흐름

```
pending → implemented → verified
  ↑                       |
  └── gap (review에서 미구현 발견 시)
```

| 상태 | 설정 주체 | 시점 |
|------|----------|------|
| `pending` | fz-plan | Phase 1 계획 출력 시 |
| `implemented` | fz-code | 해당 Step 구현 + 빌드 성공 후 |
| `verified` | fz-review | Phase 7 완료 후 (모든 검증 통과) |
| `gap` | fz-review | Phase 4.5에서 미구현 발견 시 |

## 스킬별 책임

### fz-plan (생성)

Phase 1 산출물의 "구조화된 계획 출력"에 RTM 테이블을 필수 포함한다.

규칙:
- 각 요구사항에 고유 ID 부여 (R1, R2, ...)
- discover의 정제된 요구사항이 있으면 1:1 매핑
- 하나의 요구사항이 여러 Step에 걸칠 수 있음
- 검증 방법: 빌드, 테스트, Grep, 시각 확인 등 구체적 명시

### fz-code (갱신)

각 Step 구현 + 빌드 성공 후, 해당 Step의 Req-ID 상태를 `implemented`로 갱신한다.

갱신 위치:
- ASD 활성: `{WORK_DIR}/plan/plan-final.md` 내 RTM 테이블 직접 수정
- 비ASD: `write_memory("fz:rtm:{Req-ID}", "implemented. Step {N}. 변경: {파일 요약}")`

### fz-review (검증)

Phase 4.5(Requirements Alignment)에서 RTM 기반 기계적 확인:

```
절차:
1. RTM 테이블 로드 (plan-final.md 또는 Serena memory)
2. 모든 Req-ID의 상태 확인
3. pending 잔존 → requirements_gap 이슈 생성 (category: requirements_gap)
4. implemented 전체 → Phase 5 진입
5. Phase 7 완료 시 → 모든 Req-ID를 verified로 갱신
```

## RTM 생략 조건

| 파이프라인 | RTM 생성 | 근거 |
|-----------|---------|------|
| plan 포함 (plan-only, plan-to-code, full-cycle) | **필수** | 계획이 있으므로 추적 가능 |
| code-only (plan 이미 존재) | **필수** | 기존 plan에서 RTM 참조 |
| quick-fix, bug-hunt | **생략** | 단일 수정, 추적 과잉 |
| explore, discover | **생략** | 코드 변경 없음 |
| review-only | **RTM 검증만** | 기존 RTM이 있으면 검증 |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-plan | RTM 생성 (Phase 1 산출물) |
| /fz-code | RTM 갱신 (Step 완료 시) |
| /fz-review | RTM 검증 (Phase 4.5) |

## 설계 원칙

- Progressive Disclosure Level 3 (plan/code/review에서 필요 시 로드)
- 500줄 이하 유지
