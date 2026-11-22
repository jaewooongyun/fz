# 선택 도구 상태 — 알리는 형식

> 적용: frontmatter 의 allowed-tools 에 선택 도구(Serena · context7 · sequential-thinking)가 있는 스킬 — 첫 단계에 알린다. `## 워커 심볼 도구` 절은 워크플로를 부르거나 에이전트를 직접 띄우는 스킬 — 띄우기 전과 반환 뒤에 따른다.

- 꼬리: ` · context7 목록✓|목록✗ · sc 목록✓|목록✗ · seq 목록✓|목록✗ · pr-review 목록✓|목록✗ · 스택 스킬 <이름, …>|없음` — 앞의 넷은 fz 가 이름으로 부르는 고정 도구다. context7 · sc · pr-review 에 ✗ 가 있으면 ` — 빠지는 단계: <그 도구로 하던 단계>` 를 붙인다(✓ 뿐이면 붙이지 않는다 · seq ✗ 는 표로 대신해 넣지 않는다 · `스택 스킬 없음` 은 ✗ 가 아니다). 어느 것이 없어도 막지 않는다
- 이 스킬이 부르지 않는 도구나 대체 경로로 도는 도구가 ✗ 이면 빠지는 단계 자리에 그 사실을 적는다: ` — 빠지는 단계: 없음 — <사유>` 또는 ` — 빠지는 단계: → <대체 경로>`. 예: fz-review 의 sc ✗ 는 `→ 셋째 검증을 새 컨텍스트 에이전트로`
- `목록✓` = Lead 의 도구 목록에 그 이름이 있다 — context7 은 MCP 도구, sc 는 `sc:sc-analyze`(별칭 `sc:analyze`) 스킬이다(설명 · 조사 같은 형제 명령만 있으면 ✗ — 리뷰 셋째 검증의 경로 판정 `check_evidence_slots.py --third-path` 와 같은 기준). 연결됐다는 뜻이 아니다. 목록만 보고 적는다(확인용 호출 없음) · sc 표시는 리뷰 셋째 검증용 판정 하나다 — 조사 · 설명 같은 다른 sc 명령은 그 명령을 적은 줄이 도구 목록을 따로 본다(이 표시로 막거나 건너뛰지 않는다)
- seq = sequential-thinking MCP 도구 — ✗ 이면 그 분해를 표로 쓴다(칸: 무엇을 · 근거 · 결론). pr-review `목록✓` = 에이전트 목록에 `pr-review-toolkit:` 으로 시작하는 이름이 있다
- `스택 스킬` 의 이름은 이 세션의 스킬 목록에서 고른다. 설명에 대상 트리의 언어나 프레임워크를 다룬다고 적힌 스킬이다. 이름이 여럿이면 `, ` 로 잇는다. fz 자신의 스킬과 범용 스킬은 적지 않는다. 판단이 서지 않으면 그 스킬은 뺀다. 하나도 없으면 `없음` 이라고 적는다
- 작업 폴더 프로필(peer-review · plan · discover · fix · code · review): `evidence/tools.md` 첫 줄의 Serena 부분 뒤 **같은 줄**에 꼬리를 붙인다. 예: `[Serena 미사용 — 비 git 작업 폴더] · context7 목록✗ · sc 목록✓ · seq 목록✓ · pr-review 목록✓ · 스택 스킬 없음 — 빠지는 단계: 라이브러리 문서 조회`
- 나머지 스킬: 화면 한 줄 `[선택 도구] Serena 목록✓|목록✗` + 꼬리
- 작업 폴더가 없는 세션(plan · discover · fix · code · review 를 저장 없이 진행): 기록 파일과 검사를 건너뛰고 나머지 스킬과 같은 화면 한 줄로 알린다 — 그 줄 끝에 ` · 기록 · 검사 건너뜀(작업 폴더 없음)` 을 붙인다
- 오케스트레이터(`/fz`)는 승인(Phase 4) 전에는 화면에만 알린다(승인 전 쓰기는 가드가 막는다) — 파일 기록은 승인 뒤다

## 워커 심볼 도구 — 쓰였는지 재는 법

- 워커를 띄우기 전: 상태 기록 첫 줄이 `[Serena 미사용 — <사유>]` 면 `[symbol tools: off — <사유>]` 한 줄을 그 호출에서 워커가 받는 글의 끝에 붙인다 — 워크플로에 프롬프트 인자가 있으면 그 인자, 없으면 맥락 파일이다(워커는 첫 심볼 호출 전에 그 파일을 읽는다)
- 점검 명령 셋 — 워크플로가 반환한 뒤 · 직접 띄운 에이전트가 끝난 뒤에 돌린다(작업 폴더가 없으면 세션의 상태를 상태 기록 꼴 한 줄로 임시 파일에 적어 넘긴다 — `modules/symbol-tools-audit.md` § exit 2 일 때 볼 것):
  - 워크플로: `python3 "${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py" --mcp-audit --wf {runId 폴더명} --tools-md {WORK_DIR}/evidence/tools.md`
  - 탐색 팔(교차 탐색의 첫 탐색 단계 — 보고 모드): `python3 "${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py" --mcp-audit --wf {runId 폴더명} --only-label stage1-symbolic`
  - 직접 호출(워크플로 밖에서 띄운 에이전트): `python3 "${FZ_PLUGIN_ROOT}/scripts/fz_wf_metrics.py" --mcp-audit --direct --only-agent <종류> --session '{세션 id 앞 8자}*' --tools-md {WORK_DIR}/evidence/tools.md`
- 출력 낱말마다 할 일 · exit 1 일 때 볼 것 · exit 2 일 때 볼 것 · 재지 않는 에이전트는 점검을 돌린 뒤 `modules/symbol-tools-audit.md` 에서 읽는다
