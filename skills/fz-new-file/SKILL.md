---
name: fz-new-file
description: >-
  새 파일 생성 시 헤더 서명 규칙 (파일 생성, 새 파일, file header).
  Use when creating new Swift/source files to apply correct header format.
  Do NOT use for existing file editing (use fz-code or fz-fix).
user-invocable: false
composable: false
provides: [file-header]
needs: [none]
intent-triggers: []
allowed-tools: []
model-strategy:
  main: null
  verifier: null
---

# 파일 헤더 서명 규칙

> **행동 원칙**: 새 파일 생성 시 CLAUDE.md `## File Header` 규칙을 우선 적용하고, 없으면 언어별 표준 헤더를 사용한다.

## 개요

새 파일 생성 시 프로젝트 가이드라인에 맞는 헤더를 사용합니다.

---

## 헤더 결정

CLAUDE.md `## File Header` 섹션에 헤더 템플릿이 정의되어 있으면 해당 템플릿을 따른다.
해당 섹션이 없으면 언어별 표준 헤더를 사용한다.

---

## 주의사항

- `id -F` 명령어가 시스템 계정명을 반환할 경우, CLAUDE.md의 Author 값을 사용
- 날짜는 leading zero 없이 작성 (`01/29/26` → `1/29/26`)
- 모든 새 파일 생성 시 이 규칙 적용

---

## Boundaries

**Will**:
- CLAUDE.md `## File Header` 섹션의 템플릿을 파일 최상단에 삽입
- 파일명, 연도, 프로젝트명 자동 치환
- Swift, Kotlin, TypeScript 등 언어별 표준 헤더 적용

**Will Not**:
- 파일 내용(로직) 작성 → `/fz-code` 또는 `/fz-new-file` 이후 작업
- 기존 파일 헤더 수정 → 수동 편집 또는 사용자 판단에 맡김
- 헤더 없는 파일 강제 생성

---

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| CLAUDE.md `## File Header` 섹션 없음 | 언어별 표준 헤더 사용 | 사용자에게 헤더 템플릿 입력 요청 |
| `id -F` 시스템 계정명 반환 | CLAUDE.md Author 값 사용 | 사용자에게 Author 직접 확인 요청 |
| 날짜 형식 오류 | leading zero 없이 수동 작성 | `date` 명령어로 현재 날짜 확인 |

---

## Completion → Next

- 헤더 삽입 성공 시: 파일 생성 완료 → 파일 내용 작성으로 진행
- CLAUDE.md 규칙 없을 시: 언어 표준 헤더 적용 후 사용자에게 확인 요청
- 적용 실패 시: 헤더 템플릿을 텍스트로 출력하여 수동 삽입 안내
