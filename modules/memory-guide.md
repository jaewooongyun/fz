# L1 Auto Memory 관리 정책

> MEMORY.md + topic file 관리 정책. 모든 fz-* 스킬이 교훈 저장/회상 시 참조.

## MEMORY.md 구조 규칙

- **역할**: 인덱스 + 핵심 사실 요약 (상세는 topic file로 분리)
- **한도**: 200줄 이하 (truncation 방지)
- **형식**: 섹션별 2-3줄 요약 + `[topic-file.md](topic-file.md)` 링크
- **금지**: 세션별 임시 상태, 미검증 추론, CLAUDE.md와 중복 정보

## Topic File 네이밍 컨벤션

```
{domain}.md — 예: peer-review-learnings.md, codex-learnings.md
{domain}-{sub}.md — 예: prompt-optimization.md, skill-changelog.md
```

- 파일 위치: `~/.claude/projects/{project}/memory/`
- 하나의 도메인에 하나의 파일. 날짜별 분리 금지.
- MEMORY.md에서 반드시 링크 참조.

## Write Policy

| 써야 할 것 | 쓰지 말아야 할 것 |
|-----------|----------------|
| 여러 세션에서 확인된 안정된 패턴 | 한 번의 관찰에서 나온 추측 |
| 아키텍처 결정과 그 근거 | 진행 중인 작업의 임시 상태 |
| 실전에서 검증된 교훈 (PR 리뷰 등) | CLAUDE.md에 이미 있는 정보 |
| 도구/CLI 버전 및 설정 | 일반적 프로그래밍 지식 |
| 사용자가 명시적으로 기억하라고 한 것 | 코드 스니펫 (파일 경로로 참조) |

## Tagging Convention

topic file의 각 교훈 항목에 태그를 삽입하여 recall 시 매칭에 활용.

```markdown
## 1. 교훈 제목
[skill: fz-plan, fz-code] [status: pending] [priority: P1]

교훈 내용...
```

| 태그 | 값 | 용도 |
|------|---|------|
| `[skill: ...]` | fz-plan, fz-code, fz-review 등 | recall 시 현재 스킬과 매칭 |
| `[status: ...]` | applied, pending, deferred | 개선 반영 여부 추적 |
| `[priority: ...]` | P0, P1, P2 | 우선순위 |

## Staleness Policy

- 30일+ 미참조 항목: `/fz-memory audit` 시 감사 대상으로 표시
- `[status: applied]` 항목: 적용 확인 후 6개월 지나면 아카이브 후보
- 아카이브/삭제는 사용자 확인 필수

## L1 ↔ L2 ↔ L3 경계

| 계층 | 도구 | 저장 대상 | 수명 |
|------|------|----------|------|
| L1 (Auto Memory) | MEMORY.md + topic files | 영속적 사실, 교훈, 패턴 | 영구 (사용자 관리) |
| L1.5 (Serena Persistent) | `fz:decision:*`, `fz:pattern:*` | 아키텍처 결정, 학습 패턴 | 영속 (GC 미대상) |
| L2 (Serena Memory) | `fz:checkpoint:*`, `fz:artifact:*` | 파이프라인 내 단기 전달 | 임시 (GC로 정리) |
| L3 (File Artifact) | ASD 폴더 파일 | 구조화된 상세 산출물 | 세션 내 (Read로 복원) |

- L1은 **세션을 넘어 유지**되는 지식 (교훈, 패턴, 결정)
- L2는 **파이프라인 내에서만** 유효한 상태 (artifact, checkpoint)
- L3는 **무제한 크기** 구조화 산출물 — L3=canonical, L2=cursor (위치 표시)
- L1.5 persistent 키는 L1 승격 후보 (30일+ 유지 시 topic file로 승격 고려)
- 상세: `modules/context-artifacts.md` (L3 구조), `modules/memory-policy.md` (L1.5/L2 키)

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-memory | 전체 메모리 관리 (audit/gc/recall/organize/remind) |
| /fz | Completion에서 L1 저장 판단 |

## Claude Memory tool과의 관계

**Claude Memory tool**은 client-side file-system-based memory로 cross-session 유지를 지원한다 (Anthropic release notes: "better at writing and using file-system-based memory" + "across conversations").

**fz의 L1 (auto memory)와의 차이**:
- **Claude Memory tool**: Anthropic 클라이언트 단의 메모리 (CLI/Web 등 진입점에서 관리)
- **fz L1 (auto memory)**: `~/.claude/projects/*/memory/` 파일 시스템 + topic 태깅 + 세션 GC 정책 (fz 특화)
- 두 시스템은 **독립적으로 작동**하며, fz는 자체 메모리 정책을 우선한다
- 향후 Claude Memory tool 연계 어댑터 옵션 검토 가능 (현재는 별도 운영)

상세: `modules/memory-policy.md` "Claude Memory tool과의 관계" 섹션 참조

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
