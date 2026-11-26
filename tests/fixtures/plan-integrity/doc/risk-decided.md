# plan-v1 (F-636 위험 표 결정 완화 fixture — 경고 줄 = 7 · 11 · 18 · 24)

## 위험

| Risk | Where | Mitigation |
|---|---|---|
| Duo full screen: overlays move 24 when controls toggle (status bar shows) | player | expected by decision; capture both |
| Duo full screen: overlays move 24 when controls toggle | player | expected by decision — user: "accept the 24 move in full screen" |
| Duo full screen: overlays move 24 when controls toggle | player | decided in `impact-pages-20261116.md:15` |
| Duo full screen (impact-pages-20261116.md:15) | player | decided; capture both |
| Duo full screen (status bar shows — `ContentDetailInteractor.swift:679`) | player | expected by decision; capture both |
| Duo full screen: overlays may move 24 when controls toggle | player | NOT decided (impact note lists it as open). Measure before/after; user decides |
| 스크롤 위치 복원 | list | 결정론 검사로 막는다 — 같은 입력이면 같은 출력 |
| `decided` 플래그 이름 충돌 | model | `decided` 를 `isDecided` 로 바꾼다 |

| 리스크 | 발생 조건 | 완화 |
|---|---|---|
| 상단 여백 24 이동 | 전체화면 컨트롤 토글 | 결정에 따라 예상됨 — 캡처 둘 |
| 상단 여백 24 이동 | 전체화면 컨트롤 토글 | 미결 — 사용자 결정(수치로 묻는다) |
| 상단 여백 24 이동 | 전체화면 컨트롤 토글 | 결정됨 「24 이동을 받아들인다」 |

| 위험 | 영향 | 대응 |
|---|---|---|
| 회전 중 패널 깜빡임 | 상세 | 결정됨 — 회전 중에는 숨긴다 |
| 회전 중 패널 깜빡임 | 상세 | S0d 에서 코드 근거만으로 갈지 결정 |
| 회전 중 패널 깜빡임 | 상세 | 다르면 사용자 결정(받아들임 또는 이전 동작 유지) |
| 회전 중 패널 깜빡임 | 상세 | 결정됨 — decisions.tsv:4 |

| 결정 | 근거 |
|---|---|
| A안 decided by user | 회의 |

Alternatives are excluded by decision.

```md
| Risk | Where | Mitigation |
|---|---|---|
| x | y | expected by decision |
```
