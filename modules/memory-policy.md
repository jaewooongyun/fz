# Serena Memory 관리 정책

> 모든 fz-* 스킬이 참조하는 Serena Memory 키 네이밍 + GC 정책

## 키 네이밍 컨벤션

```
{namespace}:{category}:{identifier}
```

| 네임스페이스 | 카테고리 | 예시 | 용도 |
|------------|---------|------|------|
| `fz` | `session` | `fz:session:current` | 현재 활성 세션 + ASD WORK_DIR 경로 |
| `fz` | `artifact` | `fz:artifact:step1` | 파이프라인 단계 산출물 |
| `fz` | `checkpoint` | `fz:checkpoint:{skill}-{phase}` | Phase 완료 또는 의미 있는 결과 시 경량 저장. ASD 미활성 시 유일한 compact recovery 수단. ~3,000자 <!-- 기존: 500자 --> 핵심 결정 요약 (Essential Context 포함) |
| `fz` | `checkpoint` | `fz:checkpoint:essential` | /fz가 단독 관리. 현재 Active State + Key Decisions + Constraints (~3,000자 <!-- 기존: 500자 -->). 파이프라인 완료 시 삭제 |
| `fz` | `checkpoint` | `fz:checkpoint:discover-{phase}` | mid-pipeline discover 결과. phase={plan\|code\|review}. 파이프라인 완료 시 삭제 |
| `fz` | `checkpoint` | `fz:checkpoint:discover-{phase}-final` | discover 수렴 완료 시 최종 결과. `-final` suffix는 동일 phase 키를 덮어쓰지 않고 수렴 상태를 별도 보존 |
| `fz` | `checkpoint` | `fz:checkpoint:review-issues` | fz-review Phase 5 완료 후 이슈 요약. 비ASD 모드 전용 |
| `fz` | `checkpoint` | `fz:checkpoint:implication-{skill}` | Implication Scan 결과 (비ASD 시). 실행/관찰 함의 요약. 파이프라인 완료 시 삭제 |
| `fz` | `checkpoint` | `fz:checkpoint:plan-direction` | 방향 판정 결과 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:plan-v{N}` | 계획 버전 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:plan-verify` | 검증 결과 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:plan-final` | 최종 승인 계획 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:code-step{N}` | 구현 Step 진행 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:fix-{bug}` | 버그 수정 결과 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:search` | 탐색 결과 (임시) |
| `fz` | `decision` | `fz:decision:{topic}` | 아키텍처 결정사항 (영속) |
| `fz` | `pattern` | `fz:pattern:{name}` | 학습된 패턴 (영속) |
| `fz` | `peer` | `fz:peer:pr-{number}` | 피어 리뷰 결과 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:peer-review-synthesize` | Synthesize 결과 (임시) |
| `fz` | `checkpoint` | `fz:checkpoint:peer-review-deliver` | Deliver 결과 (임시) |

## 수명 정책 (GC)

| 카테고리 | 수명 | GC 시점 |
|---------|------|---------|
| `session` | 임시 | 새 세션 시작 시 이전 세션 덮어쓰기 |
| `artifact` | 임시 | 파이프라인 완료 시 필수 삭제 |
| `checkpoint` | 임시 | 파이프라인 완료 시 필수 삭제 |
| `decision` | 영속 | `/fz-memory gc --persistent` 시 30일+ 미참조 키 목록화 → 사용자 확인 후 삭제 |
| `pattern` | 영속 | `/fz-memory gc --persistent` 시 30일+ 미참조 키 목록화 → 사용자 확인 후 삭제 |
| `peer` | 임시 | 리뷰 완료 후 7일 내 삭제 권장 |

## GC 실행 방법

```
파이프라인 완료 시 (Lead 역할):
1. list_memories() → fz:artifact:*, fz:checkpoint:* 키 수집
2. 각 키에 delete_memory() 실행
3. fz:session:current는 유지 (다음 세션 복원용)

> 이 절차는 /fz Completion의 **필수 Gate**다 (선택이 아님). GC 미실행 시 다음 세션에서 stale 키가 context를 오염시킨다.
```

## 읽기/쓰기 권한 가이드

| 스킬 | Read | Write | Edit | Delete | List |
|------|------|-------|------|--------|------|
| /fz (오케스트레이터) | O | O | O | O | O |
| /fz-plan | O | O | O | - | O |
| /fz-code | O | O | O | - | - |
| /fz-review | O | O | O | - | O |
| /fz-fix | O | O | - | - | - |
| /fz-search | O | O | - | - | - |
| /fz-codex | O | O | - | - | - |
| /fz-discover | O | O | O | - | O |
| /fz-memory | O | O | O | O | O |
| /fz-manage | O | - | - | - | O |

## 암묵적 결합 (Implicit Coupling)

키 간 순서 의존성이 존재한다. 이를 인지하지 못하면 복원 시 데이터 불일치가 발생한다.

| 의존 관계 | 설명 |
|----------|------|
| `session:current` → `artifact:*` | artifact 키의 work_dir 해석이 session:current에 의존 |
| `checkpoint:plan-*` → `checkpoint:code-*` | code checkpoint는 plan 결과를 전제 |
| `decision:*` → `artifact:*` | artifact가 decision을 참조할 수 있음 |

GC 시 주의: `session:current`를 먼저 삭제하면 artifact 키의 맥락이 소실된다. GC 순서: artifact → checkpoint → session(유지).

## 스킬별 메모리 활용 패턴

| 스킬 | 읽기 | 쓰기 |
|------|------|------|
| /fz | `fz:session:current` (복원) | `fz:session:current` (초기화 + work_dir), `fz:checkpoint:essential` |
| /fz-plan | `fz:session:current` | `fz:checkpoint:plan-direction`, `plan-v{N}`, `plan-verify`, `plan-final` + `fz:decision:{topic}` (영속) |
| /fz-code | `fz:decision:{topic}`, `fz:checkpoint:plan-*` | `fz:checkpoint:code-step{N}` (임시) |
| /fz-review | `fz:checkpoint:code-*` | `fz:checkpoint:review-issues` (임시) |
| /fz-fix | `fz:session:current` | `fz:checkpoint:fix-{bug}` (임시) + `fz:pattern:{bug_type}` (영속) |
| /fz-search | `fz:decision:{topic}` | `fz:checkpoint:search` (임시) |
| /fz-discover | `fz:checkpoint:discover-{tag}` | `fz:checkpoint:discover-{tag}` (journal=덮어쓰기, phase=APPEND), `discover-{tag}-final` (수렴) |
| /fz-memory | `fz:*` (전체 조회) | - (관리 전용, 직접 쓰기 없음) |
| /fz-manage | `fz:session:current` | - (읽기 전용 조회) |
| /fz-peer-review | `fz:checkpoint:peer-review-*` | `fz:checkpoint:peer-review-synthesize` (임시), `peer-review-deliver` (임시) |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | 세션 초기화 + GC 실행 + checkpoint:essential 관리 |
| /fz-memory | 전체 메모리 관리 (audit/gc/recall/organize/remind) |
| /fz-plan | checkpoint:plan-* + decision 키 쓰기 |
| /fz-code | checkpoint:code-step{N} 쓰기 |
| /fz-review | checkpoint:review-issues 쓰기 |
| /fz-fix | checkpoint:fix-{bug} + pattern 키 쓰기 |
| /fz-search | checkpoint:search 쓰기 |
| /fz-codex | session 키 읽기 |
| /fz-discover | checkpoint:discover-{tag} 쓰기 + 결정사항 영속화 |
| /fz-manage | session/checkpoint 읽기 + list (관리 조회) |
| /fz-peer-review | checkpoint:peer-review-synthesize/deliver 쓰기 |

## Context 계층 요약

| 계층 | 도구 | 상세 |
|------|------|------|
| L1 Hot | auto-memory (MEMORY.md) | 세션 간 영속. 프로젝트 수준 교훈/패턴/규칙. `modules/memory-guide.md` 정책 준수 |
| L2 Structured | Serena Memory (`fz:*`) | 세션 내 임시. 파이프라인 진행 상태/체크포인트 (~3,000자 <!-- 기존: 500자 -->). compact recovery 수단 |
| L3 File Artifact | ASD 폴더 파일 | 세션 내 상세. 무제한 크기 구조화 산출물. L3=canonical, L2=cursor |

> L1.5: Serena decision/pattern 키는 L2 임시가 아닌 영속. GC 대상 아님.

상세: `modules/context-artifacts.md` 참조 / L1 관리: `modules/memory-guide.md` 참조

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
