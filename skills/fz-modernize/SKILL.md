---
name: fz-modernize
description: >-
  가이드/문서 모더나이제이션 — 외부 최신 자료(Tier 1+2)로 갱신 + stale 항목 정리 + 정량 검증 (Codex 3회 + AC8 link).
  예: 최신화, 가이드 업데이트, 모더나이제이션, 문서 갱신, stale 정리 (비사용: 코드 구현 →fz-code, 스킬 구조 →fz-skill)
user-invocable: true
argument-hint: "[probe|audit|plan|verify|execute|validate|full|light] [target]"
allowed-tools: >-
  Read, Edit, Write, Bash, Grep, Glob,
  WebSearch, WebFetch,
  mcp__serena__write_memory, mcp__serena__read_memory,
  mcp__sequential-thinking__sequentialthinking,
  Task, TaskCreate, TaskUpdate,
  Skill
composable: true
provides: [doc-modernization]
needs: [none]
intent-triggers:
  - "최신화|모더나이제이션|모더나이즈|modernize"
  - "가이드 업데이트|문서 갱신|문서 업데이트|reference 업데이트"
  - "stale 정리|deprecated 정리|구버전 정리"
  - "Opus.*4\\.\\d|GPT.*5\\.\\d|새 모델 출시|최신 모델"
model-strategy:
  main: opus
  primary-worker: opus
  team-rest: sonnet
---

# /fz-modernize - 가이드 모더나이제이션 스킬

> **행동 원칙**: 기존 가이드/문서를 외부 최신 자료(Tier 1+2)로 갱신하면서 stale 항목을 정리한다. 6-phase 파이프라인으로 Probe → Audit → Plan → Verify → Execute → Validate를 순차 실행하며, 각 phase에 정량 검증 게이트를 삽입한다.

## 개요

> Phase 0 (ASD) → Phase 1 (Probe) → Phase 2 (Audit) → Phase 3 (Plan) → Phase 4 (Verify) → Phase 5 (Execute) → Phase 6 (Validate)

- **Probe → Plan 순서 강제** (31차 교훈): 외부 자료 실측 없이 Plan 작성 금지
- **Tier 1+2 우선** (사용자 합의 시): Tier 3은 supporting only로 격하
- **Codex 3회 한도** (18차 교훈): 누적 needs_revision 3회 시 사용자 에스컬레이션
- **Cross-model 안전망** (17차/16차 교훈): 분석자가 분석 대상의 실수를 재현하는 메타 패턴 방지
- **AC1-AC9 Anti-Pattern Constraints**: 본문 재구성 금지, Tier 3 단독 verified 금지 등
- **AC8 link 자동 검증**: xargs 병렬 패턴 (sequential while loop 금지 — feedback_bash_background_redirect_capture.md)

## 사용 시점

```bash
/fz-modernize "fz 가이드 7개를 Opus 4.8 출시 후 최신화"          # → full 파이프라인
/fz-modernize light "그냥 가볍게 최신화"                       # → Phase 1+2 + Codex micro-eval (40차 simplified mode, 카운터 1 소비)
/fz-modernize probe "guides/harness-engineering.md"           # → Phase 1만
/fz-modernize audit "guides/prompt-optimization.md"           # → Phase 2만
/fz-modernize plan "audit 결과 기반 update-plan v1 작성"       # → Phase 3만
/fz-modernize verify "Plan v1 검증 (Codex)"                  # → Phase 4만
/fz-modernize execute "Plan v3.1 inline 정정 적용"            # → Phase 5만
/fz-modernize validate "AC8 link 자동 검증"                   # → Phase 6만
```

## Prerequisites

- **외부 자료 접근**: WebSearch + WebFetch + Codex CLI (cross-model verify)
- **Codex CLI 0.124.0+**: gpt-5.5 cross-model. trust_level="trusted" 설정 필요 (30차 교훈)
- **6+ 스텝 자동 ASD 폴더 생성**: `{CWD}/fz-modernize-{date}/` 또는 ASD ticket ID

## 모듈 참조

| 모듈/가이드 | 용도 |
|----|------|
| guides/prompt-optimization.md | Tier 1+2 인용 정책 + 헤더 갱신 패턴 |
| guides/skill-authoring.md | 본 스킬 작성 시 표준 |
| modules/cross-validation.md | Codex 3회 한도 + Reflection Rate |
| modules/context-artifacts.md | ASD 폴더 + 산출물 보존 |
| modules/memory-guide.md | feedback_* 교훈 태깅 규칙 |
| feedback_bash_background_redirect_capture.md | xargs 병렬 패턴 (AC8 enforcement) |

## 출처 표기 규약 (Tier 분류)

```
[verified: <Tier 1+2 source>]                 ← Tier 1 (공식) 또는 Tier 2 (peer-reviewed)
[verified: A1; supporting: A5]                 ← Tier 1 + Tier 3 보강 (조합 verified)
[partially-verified: A5; A1 직접 진술 없음]   ← Tier 3 only — single verified 금지 (AC9)
[arxiv preprint, YYYY-MM]                      ← preprint 명시
[ICLR 2026 Oral / peer-reviewed]              ← peer-reviewed 명시
[official framework: dspy.ai]                  ← 회사 공식 도구/SDK
[community: cobusgreyling.medium.com/...]      ← Tier 3 그대로 (verified 표기 금지)
[미검증: <구체적 사유>]                        ← 검증 불가 (예: Korean 실측 부재)
```

### Tier 매핑 (사용자 합의 후 적용)

| Tier | 출처 종류 | verified 단독 처리 |
|------|---------|---------------------|
| 1 | 공식 (Anthropic/OpenAI 등) | ✅ 단독 verified 가능 |
| 2 | peer-reviewed 학술 | ✅ 단독 verified 가능 |
| 2.5 | arxiv preprint | ⚠️ `[arxiv preprint]` Status 필수 |
| 3 | Medium / blog (커뮤니티) | ⛔ 단독 verified 금지 — supporting only |

> **컨벤션 (원칙 인용 + frozen 모델)**: ⓐ 일반 원칙(모델 무관)의 인용은 **모델-무관 출처**(공식 docs·peer-reviewed)로 앵커 — frozen/특정 모델 doc을 일반 원칙의 sole source로 쓰지 않는다. ⓑ frozen 모델(예: 제재 모델) 인용 감지 시 **Bucket 분류 선행**: A(일반원칙·frozen이 sole anchor → 재앵커) / B(그 모델 specific 또는 비-frozen 앵커 보유 → 보존) / C(registry) / D(live-framing → frozen 캐비엇 추가). A만 재앵커, canonical ref = 해당 모델 가이드 frozen 섹션.

---

## Phase 0: ASD Pre-flight

> 참조: `modules/context-artifacts.md` Work Dir Resolution

1. 인자에서 `ASD-\d+` 패턴 추출 → 있으면 `{CWD}/ASD-xxxx/` 사용
2. 패턴 없으면 → `fz-modernize-{YYYY-MM-DD}/` 자동 생성 (사용자 확인)
3. 폴더 구조 자동 생성:
   ```
   {WORK_DIR}/
   ├── index.md              ← 작업 추적 + Resume Trigger
   ├── probe/                ← Phase 1 산출물
   ├── audit/                ← Phase 2 산출물
   ├── plan/                 ← Phase 3 산출물 (v1, v2, v3 버전 별)
   ├── execute/              ← Phase 5 변경 사항 추적 (선택)
   └── verify/               ← Phase 4 + Phase 6 검증 결과
   ```

### Gate 0: Work Dir Ready
- [ ] WORK_DIR 결정?
- [ ] 5개 하위 폴더 생성?
- [ ] index.md 초기화 (Active Phase + Key Decisions + Constraints + Pending)?

---

## Phase 1: Probe (외부 자료 리서치)

**핵심 원칙**: Plan 작성 전 외부 자료 실측 (31차 교훈 — Plan-before-Probe Anti-Pattern 금지).

### 절차

1. **사용자 Tier 합의 확인** (AskUserQuestion) — **34차 4-axes 시각화 적용**:
   - Tier 1 only — 깊이:낮음 / 검증:최고 / 시간:빠름 / 비용:적음
   - Tier 1+2 (Recommended) — 깊이:중간 / 검증:높음 / 시간:중간 / 비용:중간
   - Tier 1+2+3 — 깊이:높음 / 검증:중간 / 시간:느림 / 비용:큼
   - 사용자 직접 제공 — 깊이:가변 / 검증:가변 / 시간:즉시 / 비용:사용자 부담
2. **WebSearch 병렬 5건 이상**:
   - 모델 release notes (예: Anthropic / OpenAI 공식)
   - 학술 논문 (arxiv, ICLR/NeurIPS/ACL 등)
   - 주요 engineering 블로그
   - 커뮤니티 가이드 (Tier 3, 사용자 합의 시)
3. **자료 분류 + 카테고리화** (probe-report.md template 따름):
   - A: 공식 모델 / B: 학술 논문 / C: 외부 도구 / D: 프롬프트·하네스 엔지니어링 / E: 도구·SDK / F: 멀티에이전트 / G: Community (Tier 3)
   - 각 자료 → URL + 발행일 + 핵심 인용
4. **`probe/probe-report.md` 작성** (template: `templates/probe-report.md`)
   - Tier별 매트릭스
   - Status 칼럼 (peer-reviewed / arxiv preprint / official / community)
   - 영향 예상 표 (어느 가이드의 어느 line이 stale인지)

### Gate 1: Probe Complete
- [ ] Tier 합의 명시?
- [ ] 5+ 자료 수집?
- [ ] 각 자료 3-axes 검증 (존재 / 권한·경계 / 결과 contract — 32차)? **Tier 1 필수 / Tier 2 권장 / Tier 3 존재만** (차등 적용)
- [ ] Status 칼럼 포함?
- [ ] 영향 예상 표 작성?

> **저비용 보강 옵션**: 사용자가 추가 카테고리 요청 시 (예: "프롬프트 잘 짜는 법") → 추가 검색 4-5건 + `probe-supplement.md` 별도 파일.

---

## Phase 2: Audit (현재 가이드 line-level stale 분석)

**핵심 원칙**: probe-report.md 자료 ↔ 현재 가이드 line 매핑.

### 절차

1. **grep으로 stale 패턴 추출**:
   ```bash
   grep -nE "\[미검증|미검증:|Deprecated|deprecated|last audited|outdated" guides/*.md
   # 모델 패턴 변수 분리 (새 모델 출시 시 1곳만 갱신)
   MODEL_PATTERN="Opus [0-9]+\.\d|GPT-[0-9]+\.\d|Sonnet [0-9]+\.\d|Claude [0-9]+\.\d|Haiku [0-9]+\.\d"
   grep -nE "$MODEL_PATTERN" guides/*.md
   grep -nE "arxiv|arXiv" guides/*.md
   ```
2. **각 stale 항목 → 해소 자료 매핑**:
   - probe-report의 어느 자료로 해소?
   - A1 직접 진술 가능? A5 해석으로 supporting? 또는 partially-verified?
3. **`audit/audit-report.md` 작성** (template: `templates/audit-report.md`)
   - 가이드별 변경 영향 표 (LOC 예상)
   - 미검증 태그 line 단위 처리 결정
   - Anti-Pattern Constraints 사전 식별

### Gate 2: Audit Complete
- [ ] 미검증 태그 전수 식별?
- [ ] 각 line별 처리 결정 (verified/partially-verified/community/유지)?
- [ ] 가이드별 LOC 예상?

---

## Phase 3: Plan (변경 사항 + Anti-Pattern Constraints)

**핵심 원칙**: probe + audit 결과를 반영한 변경 plan을 작성. Plan은 v1→v2→v3로 진화 가능 (Codex verify 후 inline 정정).

### 절차

1. **`plan/update-plan.md` 초안 (v1)**:
   - Step 분해 (가이드별 1 Step)
   - Anti-Pattern Constraints 9개 (AC1-AC9, 아래 §AC 참조)
   - 출처 표기 규약 (Tier 분류 + Status)
   - 검증 게이트 정의 (5c-1 ~ 5d-3)
2. **사용자 Phase 4 합의**:
   - 범위 (전체 vs 핵심 1-2개)
   - 깊이 (Reference + 미검증 태그 해소 vs 본문 재구성 vs 새 원칙 추가)
   - Work Dir 위치
3. **Codex verify 후 v1 → v2 정정** (Phase 4 결과 반영)
4. **Codex verify 후 v2 → v3.1 정정** (마지막 사이클)

### Anti-Pattern Constraints (AC1-AC9)

| # | 금지 패턴 | 검증 grep/스크립트 |
|---|---------|------|
| AC1 | 본문 재구성 (단락 통째 교체) | git diff 변경 LOC > `min(200, 가이드 줄수 × 0.2)` → 알림 (작은 가이드 보호) |
| AC2 | 기존 verified 태그 변경 | `grep -nE "verified: <protected source>"` 변경 전후 비교 |
| AC3 | 임의 deprecation 추가 | 사용자 명시 신호 없으면 Deprecated 목록 변경 0 |
| AC4 | 출처 표기 통일성 위반 | 한 가이드 안에서 `[verified: {ID}]` 또는 `[verified: {URL}]` 일관성 |
| AC5 | 미검증 사실 임의 verified 처리 | "Korean 실측 부재" 등 정확한 미검증 사유 보호 |
| AC6 | 도서 기반 stable 가이드 본문 변경 | clean-architecture.md 같은 곳은 References 1줄 추가만 |
| AC7 | 새 원칙/섹션 추가 | 합의 깊이 제한 — 모든 변경 = 기존 표/리스트 추가/교체 |
| AC8 | broken link 미감지 | 다음 스크립트 (Rust regex 호환) |
| AC9 | Tier 3 단독 verified | A5 단독 발견 시 → `[partially-verified]` 격하 |

### AC8 스크립트 (xargs 병렬, feedback_bash_background_redirect_capture.md)

```bash
# 1. URL 추출 (Rust regex 호환, POSIX class 회피)
rg -o 'https?://[^\]\[)<>"\s]+' guides/*.md \
  | cut -d: -f2- \
  | sed 's/[.,;|]*$//' \
  | sort -u > /tmp/urls.txt

# 2. xargs -P 5 병렬 검증 (sequential while loop 금지!)
cat /tmp/urls.txt | xargs -I {} -P 5 sh -c \
  'echo "$(curl -I -s -L --max-time 15 -o /dev/null -w %{http_code} "$1") $1"' _ {} \
  2>&1 | tee /tmp/link-results.txt
```

### AC9 스크립트 (Tier 3 단독 verified 검증)

```bash
# rg -n -e 사용 (rg -nE는 encoding 옵션으로 해석되어 에러)
rg -n -e '\[verified: [^]]*A5[^]]*\]' guides/*.md | while IFS=: read -r file line content; do
  # 순서 무관: A5 존재 + Tier 1/2 supporting 존재 모두 확인
  has_a5=$(echo "$content" | grep -oE '\[verified: [^]]*\]' | grep -q 'A5' && echo yes || echo no)
  has_tier12=$(echo "$content" | grep -oE '\[verified: [^]]*\]' | grep -qE 'A[1-4]|A6|B[1-9]|C[1-9]|D[1-9]|E[1-9]|F[1-3]' && echo yes || echo no)
  if [ "$has_a5" = "yes" ] && [ "$has_tier12" = "no" ]; then
    echo "VIOLATION: $file:$line — A5 단독 verified"
  fi
done
```

### Gate 3: Plan Approved
- [ ] AC1-AC9 명시?
- [ ] 사용자 Phase 4 합의 (범위/깊이/Work Dir)?
- [ ] Codex verify 통과 또는 needs_revision 후 정정?

---

## Phase 4: Verify (Codex Cross-Model 검증)

**핵심 원칙**: Plan을 GPT-5.5 (또는 사용 가능한 cross-model)로 독립 검증. **누적 한도 3회**.

### 절차

1. **Skill 호출**: `/fz-codex verify {PLAN_PATH}`
2. **5 Q 검증 관점** (Plan-specific):
   - Q1: 미검증 태그 해소 정당성 (A1 primary / A5 supporting 분류)
   - Q2: 학술 인용 정확성 (arxiv ID, 저자명, 날짜)
   - Q3: 출처 매핑 일관성 (Plan ↔ 가이드 line)
   - Q4: Anti-Pattern Constraints 누락 위험
   - Q5: 실행 순서 안전성 (impact-scan 사전 확인)
3. **결과 분기**:
   - approved → Phase 5 진행
   - needs_revision → v{N+1} 작성 (Codex 카운터 +1)
4. **누적 한도 도달 (3/3)**: 사용자 에스컬레이션 의무 (18차 교훈)

### 권장 — Codex 호출 환경

```bash
# fz-codex SKILL.md hygiene 적용
# 1. Stdin close (29차)
# 2. trust_level="trusted" 등록 (30차)
# 3. -o flag 작동 안 할 시 stdout > file redirect 사용
codex exec \
  -m gpt-5.5 \
  -c model_reasoning_effort=high \
  -c 'sandbox_permissions=["disk-full-read-access"]' \
  --skip-git-repo-check \
  -C "{WORK_DIR}" \
  "$(cat /tmp/verify-prompt.txt)" < /dev/null \
  > {WORK_DIR}/verify/codex-verify-v{N}-result.md 2>&1
```

### Gate 4: Cross-Verify Complete
- [ ] Codex verify 1+ 회 실행?
- [ ] 누적 카운터 한도 미초과 (≤3)?
- [ ] approved 또는 사용자 에스컬레이션?

---

## Phase 5: Execute (line-level Edit)

**핵심 원칙**: Plan v3.1 §3 미검증 처리 표 + AC1-AC9 enforcement에 따라 정확한 line별 Edit.

**36차 준수**: 외부 자료 reference URL 변경(broken link archive.org 대체 외)은 팀 공유 영역 — 사용자 명시 합의 의무.

### 절차

1. **Step별 순차 실행**:
   - Step 1: 1순위 가이드 (가장 영향 큰 미검증 태그 + 학술 표 보강)
   - Step 2: 2순위 가이드
   - Step 3-N: 나머지 가이드
2. **각 Edit 시 정확한 old_string 매칭**:
   - 본문 의미 변경 0 (AC1)
   - Reference 추가 + 태그 교체만
3. **Step 완료 후 검증**:
   ```bash
   grep -nE "\[미검증" guides/{filename} | wc -l
   # 의도된 미검증만 남아야 함 (예: Korean tokenizer 실측 부재)
   ```
4. **사용자 검토 체크포인트** (Step 1 완료 후 권장)
5. **⛔ 소비처 전파 확인**: 가이드 canonical 수정 후, 변경된 개념/태그를 소비처(modules/skills/agents)에 grep 전수 → stale 잔존 0 확인. 가이드만 고치고 소비처 미전파 = "guide 새 vs consumer stale" 불일치(전파 완전성).

### Gate 5: Execute Complete
- [ ] 모든 Step Edit 완료?
- [ ] AC1-AC9 grep 통과?
- [ ] git diff LOC ≤ Plan 예상 1.5x?
- [ ] 의도된 미검증 태그만 잔존?

---

## Phase 6: Validate (AC8 link + Impact Scan)

**핵심 원칙**: 변경된 가이드의 모든 URL이 실제 도달 가능한지 자동 검증.

### 절차

1. **AC8 link 자동 검증** (위 §AC8 스크립트):
   - 27+ URL 5병렬 처리 → ~15초
   - HEAD 실패 시 GET fallback (`-A "Mozilla/5.0..."` UA 추가 가능)
   - 403 (bot 차단) ≠ broken link 구분
2. **Impact Scan** (line 번호 deep-link 의존 모듈 확인):
   ```bash
   grep -rn "guides/{filename}:L\d+" modules/ skills/ 2>&1 | head -20
   # line 번호 deep-link 발견 시 → 깨질 위험. path/section 참조만이 안전
   ```
3. **verify-evidence-matrix.md 업데이트**:
   - 25 row 매트릭스 (source_id, claim, required_terms, url)
   - AC8 결과 + 잔여 미완 항목

### Gate 6: Validate Complete
- [ ] AC8 link broken 0건 (또는 bot-block 식별)?
- [ ] Impact Scan: line 번호 deep-link 0건?
- [ ] verify-evidence-matrix.md 갱신?

---

## 메타 안전 장치 (본 세션 교훈 반영)

| 장치 | 트리거 | 대응 | 출처 |
|------|------|------|-----|
| Codex 3회 한도 | needs_revision 누적 3 | 사용자 에스컬레이션 의무 | 18차 |
| Self-application contract | 대상이 fz-modernize/* 자체 | Phase 4 Codex 검증 non-skippable + 사용자 ASR 의무 | 23차 (16차 meta) |
| Scope Inflation | 변경 LOC > Plan 예상 1.5x | 즉시 중단, 사용자 확인 | 18차 |
| Speculation Fallacy | "원본/기존/이전" 표현 사용 | git show / Read 실측 후 진술 | CLAUDE.md Verification Discipline |
| Reflection Gap | Plan 자체 stale 가능 | 5d 시작 전 plan 재검토 1회 | 17차 |
| Cross-model 안전망 | self-review로 발견 못한 사실 오류 | Codex 단독 발견 우선 적용 | 17차/16차 |
| Bash background redirect | while loop + redirect 시 0 bytes | xargs 병렬 패턴 | feedback_bash_background_redirect_capture.md |
| Plan-before-Probe | 외부 실측 없이 Plan 작성 | Probe → Audit → Plan 순서 강제 | 31차 |

---

## Few-shot 예시

```
예시 1 — full 파이프라인:
  /fz-modernize "fz 가이드 7개를 Opus 4.8 출시 후 최신화"
  → ASD 폴더 자동 생성
  → Phase 1 (Probe): WebSearch 5건 + Tier 1+2 분류
  → Phase 2 (Audit): grep으로 미검증 8곳 식별
  → Phase 3 (Plan v1): AC1-AC9 + Step 분해
  → Phase 4 (Codex verify v1): needs_revision (R1: A5 과승격)
  → Plan v2 작성 → Codex verify v2: needs_revision (Q4: G1 NeurIPS 2025 단독 발견)
  → Plan v3 작성 → Codex verify v3: needs_revision (F2 Khattab 공저자 정정)
  → Plan v3.1 점 수정 4건 → Phase 5d 실행
  → Phase 6: AC8 link 검증 (29 URL, 27 OK + 2 bot-block)

예시 2 — phase 단독 호출:
  /fz-modernize probe "최신 Claude 4.x docs"
  → Phase 1만 실행 → probe-report.md 작성

예시 3 — BAD vs GOOD:
  BAD:  Plan 먼저 작성 후 외부 자료 검색 (31차 위반) → Plan 재작성 사이클 폭주
  GOOD: Probe 먼저 → Audit → Plan v1 (Probe 실측 기반) → Codex verify
```

```
BAD (Tier 3 단독 근거):
커뮤니티 블로그 1건으로 가이드 항목 갱신 + [verified] 태그.
→ AC9 위반. 단일 Tier 3는 supporting-only.

GOOD:
Tier 1(공식)/Tier 2(arxiv) 교차 확인 → [verified: Tier1/2], Tier 3 단독은 [partially-verified].
```

```
BAD (링크 미검증 인용):
URL을 추론으로 작성 → resolve 실패(환각 인용).

GOOD:
Phase 6 AC8 link 검증 (WebFetch resolve, 200 OK) 후 인용.
```

---

## 테스트 케이스

> 상세: `references/test-spec.md` (Triggering + Functional)

## Boundaries

**Will**:
- 외부 자료 리서치 (Tier 1+2 우선)
- 가이드/문서의 line-level stale 식별
- Plan v1→v2→v3 진화 (Codex 3회 한도)
- AC1-AC9 enforcement
- AC8 link 자동 검증 (xargs 병렬)
- verify-evidence-matrix.md 갱신
- 사용자 합의 기반 깊이 제한
- **light 모드 (40차)**: 사용자 신호 "그냥/가볍게/단순/빠르게" 감지 시 Phase 1+2 + Codex micro-eval만 실행 (카운터 1 소비)

**Will Not**:
- 본문 단락 통째 재구성 (AC1 위반)
- Tier 3 단독 verified 처리 (AC9 위반)
- Codex 한도 초과 자율 반복 (18차 위반)
- 사용자 합의 없이 새 원칙/섹션 추가 (AC7 위반)
- Plan-before-Probe (31차 위반)

## 에러 대응

| 에러 | 대응 | 폴백 |
|------|------|------|
| Probe WebSearch 실패 | 재시도 1회 → 사용자에게 직접 자료 요청 | manual probe |
| Codex CLI 통신 실패 | 30차 trust_level 확인 → 재시도 | self-review로 폴백 (Cross-model 안전망 상실 명시) |
| Codex 누적 한도 도달 | 사용자 에스컬레이션 의무 | "최소 수정 승인" 모드 (Codex 권고 점 수정 N건만) |
| AC8 broken link 발견 | archive.org 폴백 또는 인용 제거 | 사용자 결정 |
| Impact Scan line 번호 깨짐 | 모듈에서 path/section 참조로 변경 권고 | 영향 모듈 목록 보고 |

## Completion → Next

Phase 6 통과 후:
- 코드 변경 있음 → `/fz-commit` 제안
- 가이드 변경만 → 사용자 직접 git commit
- 교훈 발견 → `/sc:save --type learnings` (feedback_*.md 저장)
- ASD 산출물 보존 → 새 세션에서 `index.md` Resume Trigger로 복원

---

## 관련 메모리 (자동 참조)

이 스킬은 다음 교훈을 핵심 작동 원리로 사용한다:

- **17차** (메타 분석 TEAM에도 Codex 교차 검증 자동 삽입 필수)
- **18차** (Codex 3회 한도, 누적 시 사용자 에스컬레이션)
- **16차** (분석자가 분석 대상의 실수를 재현하는 메타 패턴)
- **23차** (Self-review blind spot — Cross-model이 마지막 안전망)
- **31차** (Plan-before-Probe Anti-Pattern 금지)
- **32차** (Probe Coverage Gap — 3-axes sub-checklist 의무)
- **33차** (Recommendation Default Bias — implementation-ready 시점부터 implementation 우선)
- **34차** (첫 round 옵션 시각화 — 4-axes table)
- **36차** (팀 공유 영역 자동 변경 금지 — 외부 reference URL 변경 시 합의 의무)
- **40차** (단순 요청 over-engineering 방지 — simplified mode trigger)
- **feedback_bash_background_redirect_capture.md** (xargs 병렬 패턴 강제)

각 Phase의 Gate가 위 교훈을 enforcement한다.
