# fz-recording 테스트 명세

## SKILL.md 에서 옮긴 테스트 케이스

### Triggering

| 쿼리 | 예상 | 비고 |
|------|------|------|
| "회의 녹음 파일 정리해줘" | trigger | 일반 케이스 |
| "이 녹취록 회의록으로 만들어줘" | trigger | 텍스트 모드 |
| "meeting.m4a 화자 분리해줘" | trigger | 화자 분리 키워드 |
| "코드 리뷰해줘" | NOT trigger | → fz-review |
| "버그 수정해줘" | NOT trigger | → fz-fix |

### Functional

| Given | When | Then |
|-------|------|------|
| 오디오 + API 키 | `/fz-recording meeting.m4a` | AssemblyAI STT + 회의록 생성 |
| 텍스트만 | `/fz-recording --text transcript.txt` | Claude 화자 추론 + 회의록 생성 |
| API 키 없음 + 오디오 | `/fz-recording meeting.m4a` | `--setup` 가이드 출력 |
| 오디오 + 화자 이름 | `/fz-recording meeting.m4a --speakers "A,B"` | 화자 매핑된 회의록 |

---
