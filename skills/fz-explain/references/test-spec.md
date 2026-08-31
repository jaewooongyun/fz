# 테스트 케이스 (fz-explain)

> 형식 정본: `guides/skill-testing.md` — Triggering 최소 10개 · 정확도 ≥90% · Given/When/Then

## Triggering Test

**should-trigger** (description '예:' 어휘 + intent-triggers 기반)

| 쿼리 | 예상 | 근거 |
|------|------|------|
| "이 구조 설명해줘" | trigger | description '예: 구조 설명해줘' — 핵심 유스케이스 |
| "이거 어떻게 동작해?" | trigger | description '예: 이거 어떻게 동작해?' |
| "이 클래스 어떤 역할이야?" | trigger | description '예: 어떤 역할이야?' |
| "과외하듯 설명해줘" | trigger | description '예: 과외하듯' |
| "처음 보는 사람도 알게 설명해줘" | trigger | description '예: 처음 보는 사람도 알게' |
| "결제 기능 전체 흐름 알려줘" | trigger | intent-trigger `전체.*흐름` |
| "이 코드 설명 좀" | trigger | intent-trigger `코드.*설명` |

**should-NOT-trigger** (Boundaries Will Not — 형제 스킬 경계)

| 쿼리 | 예상 | redirect | 근거 |
|------|------|----------|------|
| "이 심볼 어디 있어?" | NOT trigger | fz-search | Will Not '코드 위치만 찾기' |
| "이 PR 뭐가 바뀐거야?" | NOT trigger | fz-pr-digest | Will Not '변경사항 해설(diff 축)' |
| "이 코드 문제 없나 봐줘" | NOT trigger | fz-review | Will Not '품질 문제 지적' |
| "이 버그 원인 찾아서 고쳐줘" | NOT trigger | fz-fix | Will Not '원인 진단과 수정' |

**합계 11개** (should 7 + should-NOT 4) — 정본 최소 10개 충족.
목표 정확도: 관련 쿼리의 **90% 이상**에서 정확 트리거.

⛔ `설명|해설|이해` 단독은 판정하지 않는다 — fz-pr-digest 와 경쟁하므로 Medium confidence 가
나와 되묻는 것이 정상 동작이다.

---

## Functional Test

| Given | When | Then | type |
|-------|------|------|------|
| 심볼 이름 입력 + 심볼 조회 정상 | `/fz-explain "PaymentInteractor"` | Phase 1 (a) 경로로 seed 확정 + 폐포 R1~R5 실행 + 문서에 층 0~3 전부 존재 + 매핑 블록 전부 `file:line` 보유 | normal |
| 기능 이름 입력 (심볼 아님) | `/fz-explain "결제 플로우"` | Phase 1 (b) 경로 — Grep→overview 로 진입점 후보를 seed 로 삼고 진행. 중단 없음 | normal |
| 상황·현상 입력 | `/fz-explain "장바구니가 가끔 비는 상황"` | Phase 1 (c) 경로 — 관여 심볼 역추적. ⛔ 원인 진단이 아니라 동작 설명을 산출하고, 수정 요청이면 fz-fix 안내 | normal |
| 저장소 고유 타입이 설명에 등장 | 임의 대상 실행 | 해당 타입이 첫 등장 시 `[A]` 등급 + 선언 + 인용과 함께 정의됨 (G4) — fixture `positive-defects.md` D1~D3 대응 | normal |
| 등장 타입의 역할 접미사가 프레임워크 개념 | 임의 대상 실행 | 타입 정의(A)와 역할 개념(파생 B)이 **둘 다** 나오고, 같은 접미사 재등장 시 개념은 1회만 | normal |
| 동작 주체를 지목하는 서술 발생 | 임의 대상 실행 | 2단계 이상이면 산문 요약 대신 심볼 호출 시퀀스로 전개 (G5) — fixture D5·D6 대응 | normal |
| 게이트를 이미 만족하는 문서를 입력 | negative fixture 적용 | 게이트 8종 검출 **0건** — 과잉 검출 없음 | normal |
| `--light` 지정 | `/fz-explain "인증 모듈" --light` | 층 0~2 만 산출 + 폐포 R1·R2·R5 + 예산 15. ⛔ G1 인용·§7-E 탐색 경계는 **생략 없음** | edge-case |
| 폐포 탐색이 예산 40 초과 | 대형 모듈 대상 실행 | seed 절단 후 계속 진행 + 제외 목록과 탐색 심볼 수를 §7-E 에 기록 (조용한 절단 없음) | edge-case |
| 진입점이 5홉에서 미도달 | 하위 계층 심볼 대상 | 도달 지점부터 흐름 서술 + "진입점 미도달"을 §7-E 에 기록. 중단 없음 | edge-case |
| 탐색 축 결과 0건 (도구 오류) | 임의 대상 실행 | 0건을 사실로 확정하지 않고 성질이 다른 도구로 재확인. 재확인 후에도 0건이면 그 사실을 §7-E 에 기록 | failure |
| 문체 교정 스킬 미설치 (G8 폴백) | 임의 대상 실행 | 기계 검사 4종 + 내장 산문 3종으로 폴백 + 부분 충족임을 문서에 명시. 산출 중단 없음 | failure |
| 문체 교정 스킬 설치됨 (G8 주 경로) | 임의 대상 실행 | `Skill` 도구로 내장 모드 호출 → 최종본 반영. 인용(`file:line`)이 코드 영역에 있어 재배치되지 않음 | normal |
| 심볼 조회 실패 | 존재하지 않는 이름 입력 | Grep 후보 탐색 재시도 → 실패 시 대상 이름을 사용자에게 되묻는다 (추측으로 seed 잡지 않음) | failure |

type 분포: normal 7 · edge-case 3 · failure 3

---

## 성공 기준

### 정량

```
Triggering 정확도        ≥90%          (11개 케이스 기준)
positive fixture 검출     11/11         결함 11종 — 게이트 8종 전수 커버
negative fixture 오검출   0/8           게이트 8종 전부 통과
게이트 라벨 누락          0건            G1 인용 · G2 등급 · G3 출처
문서 층위                층 0~3 전부 존재
SKILL.md 크기            ≤500줄
```

### 정성

```
처음 보는 사람이 문서만 읽고 흐름을 따라갈 수 있는가
등장하는 이름 중 "이게 뭔가" 를 되묻게 되는 것이 없는가
"누가 하는가" 를 읽고 곧바로 코드로 찾아갈 수 있는가
확인된 사실과 짐작이 구분되는가
```

⛔ 정성 기준은 기계로 못 잰다. 실사용자 피드백으로만 판정한다 — 이것을 자동 검사로
위장하지 않는다.

---

## fixture

| 파일 | 방향 | 기대 |
|------|:----:|------|
| `fixtures/positive-defects.md` | 검출력 | 결함 7종 전부 검출 |
| `fixtures/negative-clean.md` | 과잉 검출 | 오검출 0건 |

⛔ 한쪽만으로는 판정이 서지 않는다. positive 만 있으면 과잉 검출을 못 재고,
negative 만 있으면 검출력을 못 잰다.
