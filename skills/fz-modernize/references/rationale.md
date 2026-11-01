# fz-modernize 근거 · 이력

> SKILL.md 에서 옮긴 근거 · 이력 · 사례 문단이다(B1 · 2026-11-01). 실행 규칙은 SKILL.md 에 남아 있다 — 이 파일은 왜 그 규칙인지를 설명한다.

## freshness lint 가 대체한 수동 grep

   > 본 lint가 기존 `last audited` grep + `MODEL_PATTERN` grep을 대체한다 (수동 2건 → 결정론적 1건).

## AC9

# ⛔ 프로세스 치환을 쓴다 — `rg | while` 는 루프가 서브셸이라 카운터가 밖으로 전파되지 않는다.
#    이전 판은 VIOLATION 을 **인쇄만 하고 exit 0** 이었다(F-216 N5): 위반을 찾고도 게이트가 통과했다.
# ⛔ `rg` 를 쓰지 않는다 — 이 환경의 rg 는 **zsh 셸 함수**라 bash 에서 command not found 다.
#    그러면 while 이 빈 입력을 읽어 violations=0 → 통과. 측정 실패와 위반 0 이 같은 출력이 된다.
# ⛔ positive control 필수: 검사 대상이 0건인지 도구가 죽은 것인지 구별한다.

## 관련 메모리

---

## 관련 메모리 (자동 참조)

이 스킬은 다음 교훈을 핵심 작동 원리로 사용한다:

- **17차** (메타 분석 TEAM에도 GPT 교차 검증 자동 삽입 필수)
- **18차** (GPT 3회 한도, 누적 시 사용자 에스컬레이션)
- **16차** (분석자가 분석 대상의 실수를 재현하는 메타 패턴)
- **23차** (Self-review blind spot — Cross-model이 마지막 안전망)
- **31차** (Plan-before-Probe Anti-Pattern 금지)
- **32차** (Probe Coverage Gap — 3-axes sub-checklist 의무)
- **33차** (Recommendation Default Bias — implementation-ready 시점부터 implementation 우선)
- **34차** (첫 round 옵션 시각화 — 4-axes table)
- **36차** (팀 공유 영역 자동 변경 금지 — 외부 reference URL 변경 시 합의 의무)
- **40차** (단순 요청 over-engineering 방지 — simplified mode trigger)
- **Bash background+redirect 교훈** (xargs 병렬 패턴 강제)

각 Phase의 Gate가 위 교훈을 enforcement한다.
