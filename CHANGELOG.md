# Changelog

### v3.2.2 (2026-04-05) — Agent Role Optimization

**에이전트 책임 재분배 (Codex verified)**
- review-arch: 7→5 관점 축소 (Dead Code + Source Fidelity → review-quality 이관)
- review-arch: Context-Specific Behavior 테이블 제거 (단일 책임 원칙)
- review-quality: 리팩토링 완성도 항목 흡수, 7개 관점 명확화
- plan-structure: 영향 범위 분석을 plan-impact에 명시적 위임 (SendMessage)

**팀 구성 강화**
- fz-review: review-correctness 추가 (Phase 4.5 RTM 검증 한정)
- fz-fix: review-arch 조건부 참여 (복잡도 3+)
- memory-curator: "선택적" → "기본 포함, lightweight recall" (cross-validation.md 일치)

**동기화**
- team-registry, pipelines.md, patterns/live-review.md 팀 구성 반영
- fz-gemini 참조 제거 (README)
- plan-tradeoff.md → .archived

---

### v3.2.1 (2026-04-05) — Dependency Decoupling

**로컬 경로/iOS 의존성 제거 (7-Step, 27파일)**
- Step 1: fz-excalidraw 절대 경로(`/Users/jaewoongyun`) → `os.path.expanduser("~")` 동적 경로
- Step 2: Codex 네이티브 스킬 repo 포함 (`codex-skills/` 8개) + `scripts/setup-codex-skills.sh` + `get_codex_skill()` Tier 2b 폴백
- Step 3: 9개 에이전트 iOS 도메인 지식 → CLAUDE.md 키워드 기반 조건부 적용 + XcodeBuildMCP → "빌드 MCP 도구" 일반화
- Step 4: `modules/build.md` → CLAUDE.md `## Build` 동적 추출 (xcodebuild/npm/yarn/cargo/gradle 매칭)
- Step 5: fz-pr 팀 스킬 경로 → CLAUDE.md `## Git Workflow` 동적 참조
- Step 6: `modules/plugin-refs.md` → 프로젝트 언어/프레임워크 기반 조건부 적용
- Step 7: `templates/CLAUDE.md.template` — 새 사용자용 프로젝트 설정 템플릿

**리뷰에서 발견된 기존 이슈 수정**
- fz-review `## Guidelines` dangling reference → `## Code Conventions`
- fz-code/fz-fix iOS 16 인라인 하드코딩 → CLAUDE.md `## Plugins` 동적 참조
- `agent-team-guide.md` XcodeBuildMCP → 일반화
- README 아키텍처 트리 + 카운트 최신화

**제약**: 로컬 동작 100% 동일. CLAUDE.md에 iOS/RIBs 키워드 존재 시 조건부 활성화.

---

### v3.2 (2026-04-05) — Lead Implication Gate + Harness Engineering + System Reminders

**Lead Implication Gate** (analysis → plan → code → review 전체 반영)
- modules/lead-reasoning.md 신규 (165줄) — 추론 원칙 + 카테고리 분류 + 자문 체크리스트 + Implication Register
- cross-validation.md에 Implication Scan 게이트 + origin-equivalence 게이트 추가
- fz-code 마찰 감지에 "구조적 잔존물" + "관찰 보고 의무" 항목 추가
- fz-review 검증 4-I (Implication Coverage) 추가
- fz-plan Implication Register 출력 + Anti-Pattern 가이드 강화
- fz-codex Q8 함의 커버리지 질문 추가
- fz-fix revert 감지 → origin-equivalence 게이트 라우팅
- Codex 네이티브 스킬 4개 Implication taxonomy 통일

**Harness Engineering Guide** (1035줄)
- guides/harness-engineering.md 신규 — Anthropic 공식 2편 + NLAH 논문 + OpenDev 논문 + 오픈소스 구현체 기반
- 5대 기둥, 4가지 아키텍처 패턴, 6가지 설계 원칙, Anti-Patterns, 측정 지표, fz 매핑
- 11개 고품질 참고 문헌 (공식/학술만)

**Harness 기반 fz 고도화**
- modules/system-reminders.md 신규 — Instruction fade-out 대응 (트리거 기반 + 30턴 backstop)
- MEMORY.md Ablation 프로세스 — 분기별 Gate 기여도 측정
- CLAUDE.md Tool Usage 가이드라인 — Grep/Read/Bash 최적화
- Evaluator Tuning — 피드백 검증 프로토콜 4단계 (과적합 방지)
- review-arch/review-quality에 Tuning History 섹션

**피드백 신뢰도 검증 (과적합 방지)**
- 팀원 리뷰 코멘트 4단계 분류: project-rule / valid-suggestion / preference / needs-review
- preference(취향)는 에이전트 학습 절대 금지

**메모리 정리**
- MEMORY.md 205줄 → 114줄 (44% 감소). 이미 반영된 반성/교훈 제거, 인덱스만 유지.

---

### v3.1 (2026-04-02) — RTM + Teams v2 + Scope Expansion + L3 에이전트

**RTM (Requirements Traceability Matrix)**
- modules/rtm.md 신규 — plan이 Req-ID 생성 → code가 implemented 갱신 → review가 기계적 확인
- 산문 매칭 → ID 기반 추적으로 요구사항 누락 방어

**L3 네이티브 에이전트 통합**
- modules/native-agents.md 신규 — silent-failure-hunter + type-design-analyzer를 review Phase 5에 background 스폰
- L1(fz커스텀) > L3(네이티브) 원칙: L3는 보강만, TeamCreate 참여 금지

**Teams v2 — 팀 내부 통신 강화**
- L3→L1 피드백: L3 발견을 Lead가 Primary에 SendMessage → iOS 특화 재분석
- Supporting 활성화: impl-quality 매 Step 피드백, review-correctness 50%+마지막 RTM 체크
- Handoff Brief: plan→code 팀 전환 시 Key Decisions+Risks+Watch Points 구조화 전달
- plan-edge-case↔plan-impact CC: Supporting 간 교차로 연쇄 발견
- 5명+ 토폴로지: team-core.md에 Star-enhanced+CC 행 추가

**Scope Expansion — discover 시야 제한 4겹 방어**
- plan-impact: 변경 대상의 프로토콜/부모/같은 모듈까지 확장 탐색
- fz-plan Phase 0b: discover 로드 후 상위 수준 get_symbols_overview
- fz-code Phase 1.6: plan 영향 범위 < discover 범위이면 "시야 축소 위험" 마찰 신호
- cross-validation: review 시작 전 plan⊇discover 범위 확인

**네이티브 기능 강화**
- BATCH: merge 후 통합 빌드 gate 필수 + 부적합 조건 강화 (RIB/모듈 생성 금지)
- SIMPLIFY: 필수 gate 3가지 + 선택 suggestion 2가지 명확 분리 + 설계 의도 보존
- SC 조건 기반 자동 트리거: 빌드2실패→sc:troubleshoot, 3+Step 중간→sc:reflect, 복잡도4+→sc:estimate
- sc:save 모든 파이프라인 종료 시 (이전: 코드 변경만)

**정합성 개선**
- plan-edge-case: fz-plan YAML+registry+pipelines+pattern 4-way 동기화
- memory-curator: 모든 TEAM 참여 (이전: --deep/복잡도4+)
- plan-tradeoff: ARCHIVED (discover가 대체)
- 변경 파일 22개, RTM 19/19 verified, 리뷰 이슈 0건

### v3.0 (2026-03-30) — 3-Model Triad + 6-Agent Team + Landscape Discover

**3-Model Triad Architecture (연구 기반: X-MAS 47% 향상, ICLR 2025)**
- Claude(생산) + GPT/Codex(검증) + Gemini(Devil's Advocate) 3모델 체계
- fz-gemini 스킬 신규 생성 — Gemini CLI 전용 (review, verify, challenge)
- fz-codex에 --consensus 옵션 — 3모델 합의 모드
- cross-validation.md: Selective Consensus (불일치 시에만 Gemini 호출)
- team-core.md: 2-Tier → 3-Tier 모델 전략 (opus/sonnet/external)
- consensus-verify 파이프라인 신규 (#19)

**6-Agent Plan Team**
- fz-plan: 4 Claude + 1 GPT + 1 Gemini = 6개 차별화된 렌즈
- plan-impact 에이전트를 Impact Scanner로 강화 (Exhaustive Impact Scan 전담)
- Parallel Analysis + Cross-Feedback 통신 패턴
- 각 에이전트가 다른 질문을 던짐 (같은 질문 금지)

**Landscape Discover (discover 패러다임 전환)**
- "제약 발견 + 수렴" → "풍경 탐색 + 경로 매핑"
- provides: constraint-matrix → landscape-map + trade-off-table + open-questions
- 조건 불변성 구분: 🔒 hard constraint vs 🔓 soft preference
- discover는 결론을 내리지 않음 — plan이 경로를 선택
- adversarial 패턴: "부수기" → "비용/리스크 밝히기"

**Native Commands 활성화**
- /simplify: 선택 → 조건부 필수 (새 함수 3개+, 100줄+, 3회 빌드 실패)
- /batch: 독립 Step 3개+ 감지 시 자동 제안
- LOOP: 스킬별 에스컬레이션 래더 구체화

**Skill Refinement**
- fz-fix: 4-Phase 디버깅 (Reproduce → Isolate → Root-Cause → Verify Fix)
- fz-code: Step 완료 조건 3개 명시 (빌드 + conformance + caller 확인)
- Hooks 기반 물리적 강제: git commit 차단, platformFilter 자동 검사

**De-overfit**
- 반성 마커 제거 (규칙 유지, 출처만 삭제)
- Gate 체크리스트 경량화 (공통/조건부 분리)

### v2.5 (2026-03-20) — skill-creator Integration + Description Overhaul + Clean Architecture

**skill-creator 통합 (Runtime Trigger Eval + Description Optimization)**
- fz-skill에 `optimize` 서브커맨드 추가 — skill-creator `run_loop.py` 활용, train/test split 기반 description 자동 최적화
- fz-skill eval에 `Runtime Trigger Eval` phase 추가 — `run_eval.py`로 실제 `claude -p` 호출하여 트리거율 실측
- fz-skill create에 Phase 5 (Description Optimization 제안) 추가
- fz-manage benchmark에 `--with-trigger` 옵션 — 하위 3개 스킬 Quick Trigger Eval
- fz-manage check에 #11 skill-creator 설치 확인 항목 추가
- 신규 파일: `skills/fz-skill/references/skill-creator-integration.md` (L3 연동 가이드 + 실증 결과)
- 신규 파이프라인: #18 `skill-optimize` (pipelines.md)
- intent-registry.md에 fz-skill/fz-manage 자연어 트리거 보강

**실증 테스트 결과 및 교훈**
- 13개 스킬 전체 Runtime Trigger Eval 실행: 35/81 (43%)
- 핵심 발견: `claude -p` 자동 트리거는 슬래시 커맨드 스킬에 제한적 — should-NOT-trigger 100% 정확, should-trigger 0%
- description을 pushy 패턴으로 변경해도 트리거율 변화 없음 (43%→44%)
- 근본 원인: Claude가 간단한 요청을 스킬 참조 없이 직접 처리하는 경향
- 교훈 메모리 저장: `feedback_skill_creator_trigger_eval.md`

**전체 스킬 Description 고도화 (18/18)**
- skill-creator best practice 패턴 전면 적용:
  - Third-person: "This skill should be used when..."
  - Pushy triggers: "Make sure to use this skill whenever the user says: ..."
  - Keyword coverage: "Covers: ..." (Korean + English)
  - Boundary: "Do NOT use for..."
- 누락 5개 스킬 추가 적용: fz-codex, fz-new-file, fz-pr-digest, fz-pr, fz-recording

**500줄 제한 준수**
- fz-review: 513 → 492줄 (redundant separators 제거)
- fz-peer-review: 503 → 497줄 (redundant separators 제거)

**Clean Architecture 가이드 (Uncle Bob 페르소나)**
- 신규 파일: `guides/clean-architecture.md`
- 내용: Dependency Rule, SOLID 5원칙, 4 Layers 정의, Boundary Crossing 규칙, Architecture Smells, Uncle Bob's Decision Rules, Pragmatic 균형
- review-arch 에이전트: Architecture Decision에 Dependency Rule + SOLID 위반 감지 연결
- impl-quality 에이전트: Architecture Consistency에 DIP 위반 감지 연결
- fz-plan 스킬: 영향 분석 Step 4 "Clean Architecture 원칙 확인" 추가

**생태계 건강 체크**
- 전체 13개 항목 건강 체크 실행: 12.5/13 PASSING
- YAML 필수 필드 100%, provides/needs 체인 완전, 깨진 참조 0개
- 에이전트 14개 전부 유효, 모듈 17개 전부 존재

### v2.4 (2026-03-18) — Remove GitButler + Git Workflow Simplification

**GitButler 제거**
- GitButler 스킬 삭제 (`skills/gitbutler/` — SKILL.md + 3 reference files, -1,551줄)
- README.md 스킬 목록, CLI 도구, Infrastructure 다이어그램에서 제거 (22→21 스킬)
- 이유: Claude Code와 함께 사용 시 이점 없음 — 단일 working directory 공유로 Agent 병렬 작업 시 상호 오염 발생

**Git 워크플로우 전환**
- GitButler CLI(`but`) → 표준 `git` 명령으로 전환
- 병렬 브랜치 작업: `git worktree`로 독립 디렉토리 생성 권장
- 세션 시작: `but pull` → `git pull upstream develop`

### v2.3 (2026-03-15) — 1M Context Optimization + Ecosystem Health Fix

**1M Context Infrastructure (Opus 4.6 1M)**
- Artifact Token Budget 신설 — 100K cap + eviction 우선순위 (context-artifacts.md)
- ASD 임계값 hybrid: `6+ step 또는 context-heavy` (기존 4+)
- Essential Context 500자→3,000자 (memory-policy.md, fz/SKILL.md)
- Proactive Module Loading — /fz Phase 0에서 핵심 모듈 선로드
- Compact 경고 6+→12+ step, 4-tier 파이프라인 전략
- prompt-optimization.md: 200K 하드코딩 → 상대 서술

**Ecosystem Health Check Fix (86→95점)**
- fz-plan: `needs: [refined-requirements]` → `[none]` (standalone 실행)
- Phase 0 index.md 생성 — 5개 스킬에 compact recovery 추가
- Discover 프로토콜: DISCOVER_TAG 기반 journal=덮어쓰기, phase=APPEND
- fz-peer-review: Serena memory 도구 추가 + 2개 CHECKPOINT fallback
- fz-excalidraw: 에러 대응 섹션 (18/18 일관성)
- memory-policy.md: 4개 테이블 전면 수정 (stale → actual write_memory)
- context-artifacts.md: CWD=PROJECT_ROOT 정의, standalone peer-review workdir

**Agent Tier-1 Enrichment**
- BAD/GOOD 예시: review-direction, review-arch, review-quality, memory-curator
- Escalation Criteria: 5개 review 에이전트
- Input Format (Task Brief): review-direction, memory-curator
- Cross-skill wiring: fz-code direction-challenge, fz-review step files hydration

**Cross-skill Context**
- team-core.md: 통신 기록 요약 기본 + 원본 drill-down (*-team-full.md)
- cross-validation.md: Codex transcript 요약/원본 분리 정책

### v2.2 (2026-03-12) — Agent Teams + Context Budget + Peer Review Gate

**Agent Teams Frontmatter 적용 (Phase 1-4)**
- `memory: project|user` — 5개 에이전트에 세션 간 영속 학습 적용 (review-arch, impl-correctness, plan-structure, review-quality, memory-curator)
- `skills: [name]` — review-arch(arch-critic), review-quality(code-auditor)에 스킬 사전 주입
- `isolation: worktree` — impl-correctness에 코드 수정 격리
- `TaskCompleted` hook — 에이전트 완료 시 산출물 존재 검증 (settings.json 팀 레벨)
- team-registry.md 모델 컬럼을 `default`/`promoted`로 분리 (거버넌스 명확화)
- agent-team-guide.md §8 전체 문서화

**Context Budget 관리**
- prompt-optimization.md §2.5 — MCP 출력 격리, 도구 정의 최소화, 서브에이전트 효율
- 트리밍 비저하 원칙 — Gate/Few-shot/Step 삭제 금지 (prompt-optimization.md + skill-authoring.md)
- context-artifacts.md — 사전 예방적 Context 관리 섹션 추가

**Peer Review Deleted Logic Migration Gate**
- Gate 4.7-A — 모듈화/리팩토링 PR에서 "삭제 = 누락" 오탐 방지
- arch-critic, code-auditor, review-quality에 "삭제 vs 이동 판별" 원칙 추가
- fz-peer-review, fz-review 토큰 최적화 (-230줄, 정보 보존)
