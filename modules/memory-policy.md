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
| `fz` | `checkpoint` | `fz:checkpoint:{skill}-{phase}` | Phase 완료 또는 의미 있는 결과 시 경량 저장. ASD 미활성 시 유일한 compact recovery 수단 |
| `fz` | `decision` | `fz:decision:{topic}` | 아키텍처 결정사항 (영속) |
| `fz` | `pattern` | `fz:pattern:{name}` | 학습된 패턴 (영속) |
| `fz` | `peer` | `fz:peer:pr-{number}` | 피어 리뷰 결과 (임시) — fz-peer-review 완료 시 저장 |

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

## 스킬별 메모리 활용 패턴

| 스킬 | 읽기 | 쓰기 |
|------|------|------|
| /fz | `fz:session:current` (복원) | `fz:session:current` (초기화 + work_dir) |
| /fz-plan | `fz:session:current` | `fz:decision:{topic}` (영속) |
| /fz-code | `fz:decision:{topic}` | `fz:artifact:step{N}` (임시) |
| /fz-review | `fz:artifact:step{N}` | `fz:session:current` (이슈) |
| /fz-fix | `fz:session:current` | `fz:pattern:{bug_type}` (영속) |
| /fz-search | `fz:decision:{topic}` | `fz:artifact:search-{target}` (임시) |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz | 세션 초기화 + GC 실행 |
| /fz-memory | 전체 메모리 관리 (audit/gc/recall/organize/remind) |
| /fz-plan | decision 키 쓰기 |
| /fz-code | artifact 키 쓰기 |
| /fz-review | artifact 키 읽기 + session 이슈 쓰기 |
| /fz-fix | pattern 키 쓰기 |
| /fz-search | artifact 키 쓰기 |
| /fz-codex | session 키 읽기 |

## Context 계층 요약

| 계층 | 도구 | 상세 |
|------|------|------|
| L1 Hot | auto-memory (MEMORY.md) | `modules/memory-guide.md` 정책 준수 |
| L2 Structured | Serena Memory (`fz:*`) | 파이프라인 내 단기 전달 |
| L3 File Artifact | ASD 폴더 파일 | compact recovery + 작업 기록 |

상세: `modules/context-artifacts.md` 참조 / L1 관리: `modules/memory-guide.md` 참조

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
