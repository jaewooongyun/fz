# Changelog

### v5.0.0 (2026-11-13) — 누수 검사는 파일 내용만 봤다 — 커밋 신원 · 메시지 · 태그 · 릴리스 본문 · push 까지 한 규칙으로 본다 [MAJOR]

출하 게이트의 누수 검사는 작업 트리의 파일 내용만 봤고, 커밋 훅은 CHANGELOG · 릴리즈 노트 · 작업 로그를 예외로 건너뛰었다. 이 판은 규칙을 정본 모듈 하나(`scripts/leak_rules.py`)로 모으고 커밋 훅 · push 훅 · 출하 게이트 · 릴리스 본문 검사가 그 모듈을 함께 부른다. 예시와 fixture 는 합성 도메인 하나로 통일했고, 실행 기록은 저장소 밖에 쓰며, 옛 판 릴리즈 노트는 걷었다. 공개 저장소는 이 판의 트리로 이력을 새로 시작한다. 3건을 닫는다.

→ [릴리즈 노트](docs/releases/v5.0.0.md)

| ID | 판정 | 근거 | 검증 절차 |
|---|---|---|---|
| F-594 | 해결 — 실행 기록을 저장소 밖에 쓴다 | 추적 파일 `experiment-log.md` 는 프로토콜만 싣는다 · 실행 행을 쓰라는 지시가 `${FZ_RUN_STATE:-~/.fz/runs}/experiment-log.md` 를 가리킨다 · 식별자를 허용하던 예외 문장과 커밋 훅의 검사 예외를 지웠다 | `python3 scripts/check_ab_protocol.py experiment-log.md`(실행 행이 있으면 exit 1 · `RUN-ROW` 줄) · health-check |
| F-600 | 해결 — fixture 입력과 회귀 기준을 저장소 안에 둔다 | `tests/fixtures/modernize/ac8-links/snapshot/` · `tests/fixtures/workflow-base/`(회귀 러너 둘의 기준 원문) · 선택자는 환경 변수 트리 > 환경 변수 SHA > 고정본 | 이력 없는 사본에서 `bash tests/fixtures/modernize/ac8-links/run.sh` exit 0 · `node tests/workflows/effort-arg.js` · `node tests/workflows/default-off-regression.js` exit 0 |
| F-604 | 해결 — 태그 뒤에 새로 생긴 0644 훅을 모드 축이 잡는다 | `check_release_sync.sh` 의 모드 축이 `mode change` 줄만 읽어 새 파일(`create mode`)을 놓쳤다 · 훅(`.githooks/*`)에 한해 새로 생긴 0644 파일을 불일치로 센다 · 경계를 못 박는 시험 둘(명시 `--rules` 우선 · 허용 메일 도메인의 점 경계)을 더했다 | `bash tests/fixtures/leak-gates/release-range/run.sh`(`rel-new-hook-nonexec-exit1` · `rel-rules-empty-builtin-only`) · `python3 scripts/leak_rules.py --self-test`(`mail-content-allow-narrow`) |

### v4.56.0 (2026-11-12) — full 은 크고 복잡할 때만 묻고, 그 밖은 묻지 않고 light 로 간다 [MINOR]

### v4.55.0 (2026-11-11) — 다시 관측된 구멍을 도구로 닫고 남은 finding 을 다시 판정했다 [MINOR]

### v4.54.0 (2026-11-09) — 검사 장치의 오판을 고치고 쌓인 finding 을 모두 판정했다 [MINOR]

### v4.53.0 (2026-11-09) — 고친 finding 이 닫히지 않던 출구를 대조기로 막고 기계 강제 fz-guard 를 더했다 [MINOR]

### v4.52.0 (2026-11-07) — 식은 bg 세션을 모델 호출 없이 줄이는 fz-compact 를 더하고 비용 집계를 바로잡았다 [MINOR]

### v4.51.0 (2026-11-05) — 피어 리뷰가 코멘트할 것을 고르고, 근거 · 검사 등록 · 라우팅을 기계가 잰다 [MINOR]

### v4.50.0 (2026-11-02) — GPT 단계를 한 줄로 판정하고, 재검증 라운드에 상한을 두고, 쓰이지 않는 하네스를 걷었다 [MINOR]

### v4.49.0 (2026-11-01) — 차단 목록으로 지은 근사기는 리뷰마다 새 구멍이 났다 — Stop 훅 소유 판정을 허용 목록으로 바꾸고, 원장 · 레지스트리의 '모르면 통과' 를 닫는다 [MINOR]

### v4.48.0 (2026-10-19) — 무거운 경로 앞에서 light · full 을 묻고, Workflow 워커는 Lead 의 effort 로 돈다 [MINOR]

### v4.47.0 (2026-10-15) — 질문 틀을 바꿔 GPT 를 한 번 더 부르는 것은 같은 질문을 반복한 것과 같았다 — 반증 틀 리뷰를 뺐다 [MINOR]

### v4.46.0 (2026-10-13) — GPT 호출을 정문 하나로 모으고, 여러 각도로 부르는 실험을 잴 계기를 넣었다 [MINOR]

### v4.45.0 (2026-10-10) — 원장 · Stop 훅 · 계측기가 한데 뭉쳐 읽던 상태를 나눴다 [MINOR]

### v4.44.0 (2026-10-10) — 측정 실패를 0건 · 통과 · 불일치로 읽던 자리를 고쳤다 [MINOR]

### v4.43.0 (2026-10-07) — fz-plan 병합 콜은 도구를 빼야 입력만 접었고, GPT effort 는 config 에 닿지 않았다 — 놓친 계획 항목은 렌즈 질문을 더해도 잡히지 않았다 [MINOR]

### v4.42.0 (2026-10-01) — GPT 는 Lead 가 요약한 가설을 받아 검증했고, 리뷰는 확신 없는 후보를 발견 단계에서 지웠다 [MINOR]

### v4.41.0 (2026-09-27) — 원장은 미룸을 포기로만 적을 수 있었고, 확정 원장을 고치는 길은 자기 거부 문구에 막혀 있었다 [MINOR]

### v4.40.1 (2026-09-27) — 검증이 자기 정의를 되풀이하면 빈칸을 보지 못한다 [PATCH]

### v4.40.0 (2026-09-27) — 게이트는 초록이었고, 그 아래에서 아무것도 재지 않았다 [MINOR]

### v4.39.1 (2026-09-25) — 마지막 검증이 마지막 편집보다 앞섰다 [PATCH]

### v4.39.0 (2026-09-25) — 별칭은 새 모델을 따라갔고 단가표는 따라가지 않았다 [MINOR]

### v4.38.0 (2026-09-22) — 검사기는 있었고 부르는 곳이 없었다 [MINOR]

### v4.37.0 (2026-09-15) — 참조 탐색이 프로토콜 구현체를 놓치고 있었다 [MINOR]

### v4.36.0 (2026-09-13) — 참조는 있는데 부를 이름이 없었다 [MINOR]

### v4.35.0 (2026-09-13) — 자체 검사가 전부 초록인데 통합 배선이 죽어 있었다 [MINOR]

### v4.34.0 (2026-09-13) — 사전등록 표가 비어 있었다: 재는 주체가 없었다 [MINOR]

### v4.33.1 (2026-09-11) — Stop 훅이 남의 세션 원장으로 내 종료를 막았다 [PATCH]

### v4.33.0 (2026-09-11) — 적용은 했는데 커밋하지 않았고, 같은 실패가 다시 왔다 [MINOR]

### v4.32.1 (2026-09-08) — 모델은 gpt 인데 문서는 실행 파일 이름을 부르고 있었고, 게이트는 조용히 통과했다 [PATCH]

### v4.32.0 (2026-09-07) — 배포물이 특정 티켓 접두를 알고 있었고, 자작 키는 공식 표 밖에 서 있었다 [MINOR]

### v4.31.0 (2026-09-06) — 정본이 자기 Lead 모델을 몰랐고, 하네스는 자기 무게를 재는 눈이 없었다 [MINOR]

### v4.30.0 (2026-09-06) — codex 라는 이름이 두 가지를 가리키고 있었다 [MINOR]

### v4.29.0 (2026-09-03) — 승인 도장이 남의 줄에 박혔다 [MINOR]

### v4.28.0 (2026-09-01) — 게이트가 헛돌고 있었다 [MINOR]

### v4.27.1 (2026-08-31) — 리베이스 스킬은 플러그인 밖에서 게이트 없이 돌고 있었다 [PATCH]

### v4.27.0 (2026-08-31) — 설명이 "바뀐 부분" 만 다루던 것은 지시받은 대로였다 [MINOR]

### v4.26.0 (2026-08-26) — peer-review 의 병목은 fan-out 이 아니었다 [MINOR]

### v4.25.1 (2026-08-25) — fixture 가 클론 위치에 묶여 있었다 [PATCH]

### v4.25.0 (2026-08-25) — 완료 판정을 산문에서 exit code 로 [MINOR]

### v4.24.0 (2026-08-24) — 게이트가 조용히 꺼져 있던 자리를 닫았다 [MINOR]

### v4.23.1 (2026-08-10) — 배선 복구: 정의된 팀 일부가 돌지 않고 있었다 [PATCH]

### v4.23.0 (2026-08-10) — 누적 통합: 계약 lint 결정화 · 리뷰 구조 판정 축 · llm-references §1.1b [MINOR]

### v4.22.0 (2026-08-08) — 누적 릴리즈: fz-rebase 신설 · peer-review 인라인 게시 · Opus 5 대응 · 계측 도구 [MINOR]

### v4.21.0 (2026-07-09) — 하네스 서베이 Wave C: code-pair pre-flight 크기 가드 (H5 scaffold collapse) [MINOR]

### v4.20.0 (2026-07-09) — 하네스 서베이 Wave B: 메커니즘/모듈 정합 + Governance Decay 실측 [MINOR]

### v4.19.0 (2026-07-09) — 하네스 서베이 2026 반영 Wave A: 가이드 개정 + 워커 3-tier 재배선 확정 [MINOR]

### v4.18.0 (2026-07-06) — Fable 5 재배선: 판단=Fable / 수행=Opus·Sonnet [MINOR]

### v4.17.0 (2026-06-29) — 가이드 모더나이제이션 + 가이드 준수 remediation [MINOR]

### v4.16.0 (2026-06-27) — SKILL.md 분리 + visual oracle 강화 [MINOR]

### v4.15.0 (2026-06-18) — 외부 리뷰어 catch 환류 회로 (promotion-ledger 트랙 C) [MINOR]

### v4.14.2 (2026-06-16) — fz-code 구조 평가 convention 면제 [PATCH]

### v4.14.1 (2026-06-14) — Fable 5 제재 대응 롤백 [PATCH]

### v4.14.0 (2026-06-13) — Claude Fable 5 대응 + 전수 주장 오판 방어 [MINOR]

### v4.13.0 (2026-06-11) — Template Authority Bias 방어 + 구조 결정 옵션 사용자 배선 [MINOR]

### v4.12.1 (2026-06-08) — Serena MCP 플러그인 번들 + 미노출 도구 참조 정리 [PATCH]

### v4.12.0 (2026-06-06) — TEAM → 네이티브 Workflow 전환 (Wave 0-3) [MINOR]

### v4.11.0 (2026-06-04) — Opus 4.8 정합 + 인용 위생 + 하네스 구조 개선 [MINOR]

### v4.10.1 (2026-06-02) — 하네스 self-maintenance + figma candidate 신호 [PATCH]

### v4.10.0 (2026-05-27) — Sycophancy 방어 + Active Recall + Reflection Pipeline Active [MINOR]

### v4.9.0 (2026-05-17) — Authority Network + Codex Ecosystem Hardening + fz-modernize 신규 [MINOR]

### v4.8.0 (2026-05-06) — Cargo-Cult Defense + Lessons-to-Module Pipeline 도구화 [MINOR]

### v4.7.1 (2026-05-04) — Implicit→Explicit Enforce (3-Phase 통합) [MINOR]

### v4.6.0 (2026-04-26) — Cleanup: fz-plan slim + plugin-refs 정정 + pre-commit hook [MINOR]

### v4.5.1 (2026-04-26) — docs fix: remove local work dir references [PATCH]

### v4.5.0 (2026-04-26) — Swift/iOS Quality Framework (3-Layer Evidence) [MINOR]

### v4.4.0 (2026-04-26) — Mapping Layer SPOF Defense [MINOR]

### v4.3.0 (2026-04-25) — fz GPT/Codex Tier 1+2 완성 [MINOR]

### v4.2.0 (2026-04-24) — Scope Challenge + fz Guide Compliance [MINOR]

### v4.1.0 (2026-04-21) — Call-Site Deprecation Audit + Function Responsibility Audit [MINOR]

### v4.0.0 (2026-04-21) — V.D. 4-way Chain 아키텍처 + 생태계 정합성 [MAJOR]

### v3.11.0 (2026-04-21) — Opus 4.7 Adaptation + Verification Discipline

### v3.10.0 (2026-04-15) — Scope Minimality

### v3.9.0 (2026-04-14) — Harness Engineering Enhancement

### v3.8.0 (2026-04-12) — Uncertainty-Aware Harness

### v3.7.0 (2026-04-12) — Code Transformation Validation

### v3.6.0 (2026-04-11) — iOS/Swift Reverse Diagnostic Triggers

### v3.2.2 (2026-04-05) — Agent Role Optimization

### v3.2.1 (2026-04-05) — Dependency Decoupling

### v3.2 (2026-04-05) — Lead Implication Gate + Harness Engineering + System Reminders

### v3.1 (2026-04-02) — RTM + Teams v2 + Scope Expansion + L3 에이전트

### v3.0 (2026-03-30) — 3-Model Triad + 6-Agent Team + Landscape Discover

### v2.5 (2026-03-20) — skill-creator Integration + Description Overhaul + Clean Architecture

### v2.4 (2026-03-18) — Remove GitButler + Git Workflow Simplification

### v2.3 (2026-03-15) — 1M Context Optimization + Ecosystem Health Fix

### v2.2 (2026-03-12) — Agent Teams + Context Budget + Peer Review Gate
