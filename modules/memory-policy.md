# Serena Memory 키 정책 (영속 · 임시)

> **Sources (last audited: 2026-09-21 — **인용 정합 축**(arxiv ID 형식 56종 이상 0 · 교차 파일 주장 일치 · 레지스트리 등재)):** arxiv 2601.15300 · 2510.05381(EMNLP 2025 Findings) · `platform.claude.com` memory-tool. ⚠️ 이 감사에서 **레지스트리 미등재 4종** 발견 — `2510.05381` · `2510.07777` · `2512.20845` · `2601.15300` (`guides/llm-references.md` · `guides/harness-engineering.md` §참고문헌 둘 다에 없다). ⛔ **원문 재조회는 포함하지 않았다** — 외부 페이지가 바뀌었는지는 이 감사의 범위 밖이다.

> Serena Memory 키(영속 decision · pattern · 임시 peer) 네이밍 + GC 정책. 세션 상태(checkpoint · session · artifact · rtm · consensus)는 키로 두지 않는다 — 복원은 티켓 폴더 파일로 한다(`modules/context-artifacts.md`). 옛 판이 쓴 그 계열 키는 `/fz-memory gc` 가 사용자 확인 뒤 지운다(그 스킬의 한 번 하는 정리 단계)

## 목차

- [키 네이밍 컨벤션](#키-네이밍-컨벤션)
- [수명 정책 (GC)](#수명-정책-gc)
- [참조 스킬](#참조-스킬)
- [Context 계층 요약](#context-계층-요약)
- [설계 원칙](#설계-원칙)

---

## 키 네이밍 컨벤션

```
{namespace}:{category}:{identifier}
```

| 네임스페이스 | 카테고리 | 예시 | 용도 |
|------------|---------|------|------|
| `fz` | `decision` | `fz:decision:{topic}` | 아키텍처 결정사항 (영속) · 생산자 `/fz-discover` |
| `fz` | `pattern` | `fz:pattern:{name}` | 학습된 패턴 (영속) · ⛔ 생산자 없음(쓰는 절차 0 — memory-curator 읽기만 남았다) |
| `fz` | `peer` | `fz:peer:pr-{number}` | 피어 리뷰 결과 (임시) · ⛔ 생산자 없음(쓰는 절차 0) |

## 수명 정책 (GC)

| 카테고리 | 수명 | GC 시점 |
|---------|------|---------|
| `decision` | 영속 | `/fz-memory gc --persistent` 시 30일+ 미참조 키 목록화 → 사용자 확인 후 삭제 |
| `pattern` | 영속 | `/fz-memory gc --persistent` 시 30일+ 미참조 키 목록화 → 사용자 확인 후 삭제 |
| `peer` | 임시 | 리뷰 완료 후 7일 내 삭제 권장 |

## 참조 스킬

| 스킬 | 참조 이유 |
|------|----------|
| /fz-memory | 전체 메모리 관리 (audit/gc/recall/organize/remind) |
| /fz-discover | 결정사항 영속화 |

## Context 계층 요약

> **근거 — 왜 계층화가 필요한가**: 1M context window는 **safety net이지 strategy가 아니다**. Intelligence Degradation in Long-Context LLMs (arxiv 2601.15300) + Context Length Alone Hurts (arxiv 2510.05381, EMNLP 2025 Findings) — 컨텍스트 확대 자체가 모델 성능을 저하시킴. 따라서 L1/L3 분리는 "용량 부족 대응"이 아니라 "집중 > 분산" 원칙의 구조적 강제.

| 계층 | 도구 | 상세 |
|------|------|------|
| L1 Hot | auto-memory (MEMORY.md) | 세션 간 영속. 프로젝트 수준 교훈/패턴/규칙. `modules/memory-guide.md` 정책 준수 |
| L3 File Artifact | 티켓 폴더 파일 | 세션 내 상세. 무제한 크기 구조화 산출물. L3=canonical |

> L2: Serena decision/pattern 키는 영속. 기본 GC 는 건드리지 않는다 — `/fz-memory gc --persistent` 만 사용자 확인 뒤 정리한다.

### Claude Memory tool과의 관계

> 참조: Anthropic 공식 Memory tool (file-system-based memory, https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool). 이전 세대 Opus 모델을 두고 적은 관찰: file-system 기반 메모리 활용도가 높음 — 도구를 새로 추가한 것이 아니라 **활용**이 강함.

공식 Memory tool은 **client-side 도구** — 저장 backend/위치는 **사용자/애플리케이션이 제어**. "across conversations"/"persist between sessions" 지원. 기능적으로 fz의 L3 (티켓 폴더 + `.claude/projects/.../memory/`)와 **중복 가능성** 존재:

| 관점 | fz 자체 구현 (L1/L3) | Claude Memory tool |
|------|----------------------|---------------------|
| 저장소 | `MEMORY.md` + 티켓 폴더 + Serena | 클라이언트/애플리케이션 관리 backend |
| 관리 | fz 파이프라인 + memory-guide.md 정책 | 도구 구성 + 모델 사용 패턴 |
| 세션 | cross-session (파일 기반) | cross-session 가능 (backend 구성에 따름) |
| 이식성 | Claude Code 독립 | Claude API/Code 공통 |

**현재 정책**: fz는 자체 L1/L3 (+ L2 영속 키) 유지. 이유 — (a) 명시적 정책/태깅 제어, (b) 영속 키는 Serena MCP와 직접 연동, (c) fz 파이프라인 Gate 연계. **미래 전환 판단 기준**: Memory tool을 fz L2 수준 정책(태깅/GC/읽기 권한)으로 감싸는 어댑터를 만들 가치가 생기면 재검토. [미검증: 2026-04 시점 공식 문서 기반, 실사용 실측 부재]

상세: `modules/context-artifacts.md` 참조 / L1 관리: `modules/memory-guide.md` 참조

## 설계 원칙

- Progressive Disclosure Level 3 (필요 시에만 로드)
- 500줄 이하 유지
