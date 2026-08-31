# Peer Review 4-Tier Graceful Degradation

diff 크기에 따라 구성과 비용을 자동 조절하는 티어 시스템.

> ⛔ **TEAM 일몰 재매핑 (Wave 4)**: Tier 2/3 Analyze는 `workflows/peer-review.js` Workflow로 실행된다 (TeamCreate 아님). Tier 0/1은 이미 Lead-solo. 폴백 체인 Tier3→2→1→0은 `mode:'workflow'` → `mode:'fallback'` → Lead SOLO로 매핑. Codex는 out-of-band (Lead `/fz-codex`, 스크립트 내 스폰 금지).

---

## 목차

- [Tier 구성](#tier-구성)
- [자동 휴리스틱 (단일 진실 원천)](#자동-휴리스틱-단일-진실-원천)
- [Tier 0 (Solo) 절차](#tier-0-solo-절차)
- [Tier 1 (Solo + Codex) 절차](#tier-1-solo--codex-절차)
- [Tier-Adaptive Evidence](#tier-adaptive-evidence)
- [비용 로깅 (모든 Tier)](#비용-로깅-모든-tier)
- [Tier 2: Lite — 실행 시퀀스](#tier-2-lite--실행-시퀀스)
- [Tier 3: Full (--deep) — 추가 시퀀스](#tier-3-full---deep--추가-시퀀스)
- [Codex Analyze 호출](#codex-analyze-호출)
- [Cross-Critique Anti-Sycophancy Rule](#cross-critique-anti-sycophancy-rule)
- [타임아웃 + 폴백](#타임아웃--폴백)

---

## Tier 구성

| Tier | review-arch | review-quality/correctness | Codex | Cross-Critique | 기본 agent call |
|------|------------|----------------|-------|---------------|-----------|
| **0 (Solo)** | Orchestrator 직접 | — | — | None | 0 |
| **1 (Solo+Codex)** | Orchestrator 직접 | — | Lead /fz-codex ×1 | None | 0 (+Codex 1) |
| **2 (Lite)** | peer-review.js Stage1 (**opus**) | Stage1 (**opus** ×2) | Lead /fz-codex ×1 | 미투표 (Lead 병합) · **Stage2 조건부** | **3 또는 5** (트리거 발화 시 5) |
| **3 (Full)** | Stage1 + Stage2 (**opus**) | Stage1 (**opus** ×2) | Lead /fz-codex ×2 | Workflow Stage2 교차 + Stage3 counter DA | **6** (전부 opus) |

> ⛔ **모델은 스크립트가 single source** — `peer-review.js`의 `label: 'stage1-arch'`·`'stage1-quality'`·`'stage1-correctness'`(Stage1) · `'stage2-arch-on-quality'`·`'stage2-quality-on-arch'`(Stage2) · `'stage3-counter'`(Stage3) 전 호출이 `model:'opus'`다. 에이전트 frontmatter(`review-quality`·`review-correctness`·`review-counter` = `sonnet`)와 `skills/code-auditor/SKILL.md` `main: sonnet`은 **스크립트에 의해 override된다** — 실행 경로는 스크립트다.
> ⛔ **재시도 포함 실제 호출 수는 더 클 수 있다** — `parallelWithRetry`가 Stage1 null 항목마다 1회 재호출하므로 **Tier 2는 3~6, Tier 3는 6~9**다(`peer-review.js`의 `parallelWithRetry`). 부분 실패로 Stage2가 생략되면 Tier 3가 6보다 적을 수도 있다. **권위 있는 수치는 반환값 `metrics.agentCalls`뿐이다.**
> ⛔ **비용 상한 수치 열을 제거했다.** 기존 `~$2.00`/`~$3.50`은 "opus 1 + sonnet 1" 전제로 산정된 값이라 실제(opus 3 / opus 6)와 맞지 않았다. 추정치를 다른 추정치로 바꾸는 대신 **검증 가능한 call 수**로 대체한다 — 실제 비용은 `cost-log.json`이 invoke마다 실측으로 남긴다. [참고 실측: PR Tier 2 = 448K tokens]

## 자동 휴리스틱 (단일 진실 원천)

> ⛔ boundary 수치 변경 시 본 모듈 단일 지점 수정. SKILL.md는 *요약 인용*만.

```
CHANGED_LINES = additions + deletions  (gh pr view --json additions,deletions 또는 git diff --numstat)

CHANGED_LINES <  100  → Tier 0 (base), Tier 1 (--codex 옵션 시)
CHANGED_LINES 100-200 → Tier 1 (base), Tier 2 (--deep 옵션 시)
CHANGED_LINES 200-500 → Tier 2 (base), Tier 3 (--deep 옵션 시)
CHANGED_LINES 500-2000 → Tier 2 + 비용 경고 ($2+ 예상)
CHANGED_LINES > 2000  → AskUserQuestion ($3+ 예상)

--tier N 옵션으로 강제 지정 가능 (auto 무효화)
```

> 위 표 = 사람용 개념 요약(경계값 100/200/500은 CHANGED_LINES 기준 설명). **실제 판정 SSOT는 아래 bash** — SIGNIFICANT_LINES(= CHANGED − GENERATED, 생성파일 제외) + risk escalation 적용. ⛔ 생성파일 많은 PR(Package.resolved 등)에선 표(CHANGED)와 bash(SIGNIFICANT) 판정이 달라질 수 있어 **Tier 결정은 bash를 신뢰**. ⛔ 경계값 변경 시 표 + bash 동시 수정(자동 검증 없음 — prose 규칙).

### 자동 선택 실행 bash (Gather Step 5.5)

```bash
# 1. Changed lines 측정 (PR 또는 branch). gh CLI는 .previous_filename (snake_case) 반환
if [[ "$INPUT" =~ ^[0-9]+$ ]]; then
  ADDED=$(gh pr view "$INPUT" --json additions -q '.additions' 2>/dev/null || echo 0)
  DELETED=$(gh pr view "$INPUT" --json deletions -q '.deletions' 2>/dev/null || echo 0)
  GENERATED_LINES=$(gh pr view "$INPUT" --json files -q '[.files[] | select(.path | test("(package-lock|pnpm-lock|yarn-lock|Package\\.resolved|Gemfile\\.lock|Cargo\\.lock|\\.pbxproj|\\.storyboard)$")) | .additions + .deletions] | add // 0' 2>/dev/null || echo 0)
  # rename: gh CLI는 previous_filename (snake_case) 노출. 단, gh CLI 버전에 따라 다름 → fallback grep
  RENAMED_LINES=$(gh pr view "$INPUT" --json files 2>/dev/null | jq '[.files[] | select(.previous_filename != null or .previousFilename != null) | .additions + .deletions] | add // 0' 2>/dev/null || echo 0)
else
  # branch input — BASE 존재 검증
  case "$INPUT" in
    feature/*) BASE="${BASE:-develop}";;
    hotfix/*)  BASE="${BASE:-main}";;
    *) BASE=$(AskUserQuestion "Base branch?");;
  esac
  git rev-parse --verify "$BASE" >/dev/null 2>&1 || git fetch origin "$BASE" 2>/dev/null || { echo "⛔ BASE '$BASE' not found. Abort tier auto."; TIER=2; }
  ADDED=$(git diff --numstat "${BASE}...${INPUT}" 2>/dev/null | awk '$1!="-"{a+=$1} END{print a+0}')
  DELETED=$(git diff --numstat "${BASE}...${INPUT}" 2>/dev/null | awk '$2!="-"{d+=$2} END{print d+0}')
  GENERATED_LINES=$(git diff --numstat "${BASE}...${INPUT}" 2>/dev/null | awk '/(package-lock|Package\.resolved|\.pbxproj|\.lock)/ {g+=$1+$2} END{print g+0}')
  RENAMED_LINES=$(git diff --name-status "${BASE}...${INPUT}" 2>/dev/null | awk '/^R[0-9]/ {r++} END {print r*5+0}')  # rename 1건당 ~5줄 추정
fi
CHANGED_LINES=$((ADDED + DELETED))
SIGNIFICANT_LINES=$((CHANGED_LINES - GENERATED_LINES))  # rename은 실 편집 가능성 있어 *차감 안 함* (보수적)
[ "$SIGNIFICANT_LINES" -lt 0 ] && SIGNIFICANT_LINES=0
[ "$RENAMED_LINES" -gt 0 ] && [ "$SIGNIFICANT_LINES" -lt 10 ] && {
  AskUserQuestion "rename 위주 PR (SIGNIFICANT_LINES=$SIGNIFICANT_LINES). Tier 0 진행?"
}

# 2. --tier 옵션 최우선 (precedence: --tier > Risk escalation > auto)
if [ -n "$TIER_OPT" ]; then
  TIER=$TIER_OPT  # 사용자 명시 → 그대로. Risk escalation 적용 안 함 (precedence 모순 방지)
else
  # auto tier
  if [ $SIGNIFICANT_LINES -lt 100 ]; then TIER=0
  elif [ $SIGNIFICANT_LINES -lt 200 ]; then TIER=1
  elif [ $SIGNIFICANT_LINES -lt 500 ]; then TIER=2
  elif [ $SIGNIFICANT_LINES -lt 2000 ]; then TIER=2  # +cost warning
  else
    AskUserQuestion "diff $SIGNIFICANT_LINES줄. 진행?"
    TIER=2
  fi

  # Risk-based escalation (auto일 때만 적용. 6 카테고리 → cap=Tier 2)
  # ⛔ 인라인 grep 금지 — 오탐 실측 후 스크립트로 이관 (§ 위험 판정 참조).
  #    경로는 절대경로로 해석한다. 상대 경로는 대상 레포에 파일이 없어 조용히 통과한다.
  RISK_JSON=$(python3 "${FZ_PLUGIN_ROOT}/skills/fz-peer-review/scripts/risk_scan.py" \
                "${WORK_DIR}/diff.patch" --json)
  RISK_STATUS=$?
  if [ $RISK_STATUS -ne 0 ]; then
    echo "⚠️ risk_scan 실패 (exit $RISK_STATUS) — 승격 없이 진행. 근거 부재를 tier.txt 에 기록한다"
    RISK_MATCHES=0; TIER_DELTA=0
  else
    RISK_MATCHES=$(printf '%s' "$RISK_JSON" | jq -r '.risk')
    TIER_DELTA=$(printf '%s' "$RISK_JSON" | jq -r '.tier_delta')
    TIER=$((TIER + TIER_DELTA))
  fi
  [ "$TIER" -gt 2 ] && TIER=2  # cap (--deep 명시 시에만 Tier 3 진입)
fi

# 3. --deep 옵션 처리 (Tier 2/3에서만 Cross-Critique 활성화)
if [[ "$OPTS" == *"--deep"* ]]; then
  [ "$TIER" -ge 2 ] && TIER=3 || echo "⚠️ --deep + Tier $TIER → warning. Tier 2 강제"
  [ "$TIER" -lt 2 ] && TIER=2
fi

echo "$TIER" > ${WORK_DIR}/tier.txt
echo "rationale: SIGNIFICANT=$SIGNIFICANT_LINES (added=$ADDED+del=$DELETED-gen=$GENERATED_LINES), risk=$RISK_MATCHES, override=${TIER_OPT:-auto}, deep=${OPTS}" >> ${WORK_DIR}/tier.txt
```

### 리뷰 표면 진단 — stale merge-base

⛔ **diff 는 merge-base 기준이다.** base 가 분기 후 앞서 나가면 **이미 base 에 있는 변경**이
diff 에 다시 나타난다. 그러면 두 가지가 함께 틀린다 — Tier 판정이 위로 틀려 리뷰 예산이 낭비되고,
리뷰어는 이미 리뷰·머지된 코드를 다시 본다.

**실측 (#4766, 2026-08-25)**

| 축 | 값 |
|---|---|
| base 팁이 분기점보다 | **39커밋 앞** |
| head 커밋 | 3개 — 그중 **2개가 이미 base 에 있다**(patch-id 일치) |
| diff 가 보여준 것 | 26파일 +304/−182 |
| 실제 리뷰 표면 | **18파일 +83/−83** (2.9배 차이) |
| Tier 오판 | 486줄 → Tier 2 (실제 166줄 → Tier 1) = agent **0콜이 3콜**로 |

`gather.sh` 가 `review-surface.md` 에 `git cherry` 판정을 적는다. `-` 는 이미 base 에 있는 커밋,
`+` 는 신규다. Lead 는 `-` 커밋을 리뷰 대상에서 빼고 **Tier 를 재계산**한다.

⚠️ **`git cherry` 의 한계**: patch-id 로 판정하며 **머지 커밋을 제외**한다. 스쿼시·리베이스로
해시가 바뀐 동일 패치는 잡지만, 내용이 조금이라도 다르면 `+` 로 남는다 — **놓침이 있는 도구다.**
`-` 가 0건인 것을 "중복 없음" 의 증명으로 쓰지 않는다.

⛔ **자동 보정하지 않는 이유**: 무엇이 리뷰 대상인지는 판단이다. GitHub 은 merge-base 기준 전체를
보여주므로 다른 리뷰어는 26파일을 본다 — 스크립트가 조용히 범위를 줄이면 리뷰가 서로 어긋난다.
진단만 내고 범위 결정은 Lead 에게 남긴다.

### 위험 판정 — 카테고리 단위

판정체는 `skills/fz-peer-review/scripts/risk_scan.py` 다. 인라인 `grep -cE` 를 대체했다.

**무엇이 달라졌나**

| 축 | 기존 | 현행 |
|---|---|---|
| 대상 | diff 전체 (hunk 헤더·context·삭제 라인 포함) | **추가된 코드 라인만** |
| 경계 | 없음 | 토큰 경계 — `actor` 가 `Interactor` 에 매칭되지 않는다 |
| 단위 | 매칭 **행 수** | **카테고리 수** (같은 위험이 20줄에 걸쳐도 1) |
| 역방향 | 없음 | `static let shared` + `var` 를 같은 파일에서 보면 동시성 위험 |

⛔ **임계는 그대로다** — `≥2 → +2` · `==1 → +1`. 세는 단위만 바뀌었다.

**왜 바꿨나**: 한 리뷰에서 4건이 매칭됐는데 전부 오탐이었다. `Interactor` substring 매칭 + 전부 `` 헤더였고, Lead 가 수동으로 0 으로 내렸다. 자동 판정 그대로면 114줄 PR 이 상위 Tier 로 올라가 3~6 agent call 을 유발한다 — **시간 목표를 직접 악화시킨다.**

⛔ **실패 시 승격하지 않는다.** 스크립트가 비정상 종료하면 근거가 없는 것이므로 Tier 를 올리지 않고, 그 사실을 `tier.txt` 에 남긴다. 근거 없이 올리면 비용만 늘고, 조용히 넘어가면 판정이 있었던 것처럼 보인다.

회귀 자료: `tests/fixtures/peer-review/risk-scan/` — 음성 1(오탐 유발 형태) · 양성 2(직접 신호·역방향 신호).

### 옵션 precedence
1. `--tier N` (최우선, auto 무효화). invalid 값 → auto fallback + error log
2. `--deep` (auto Tier 2/3 시 Cross-Critique 활성화. auto Tier 0/1 시 warning + Tier 2 강제)
3. `--codex` (Tier 0 → Tier 1 효과: Codex challenger 1회 추가)

---

### effort 배정 — 왜 전 스테이지 `xhigh` 인가

⛔ **차등하지 않는다.** 계획 단계의 가정("Stage 2 는 판정 출력이라 가볍다")이 실측으로 반증됐다.

**Tier 3 실행 1건 측정**

| Stage | 출력량 | 새 발견 |
|---|---:|---|
| Stage 1 (3렌즈) | 27,033자 | issues 14건 |
| **Stage 2 (교차)** | **18,758자 — Stage1 의 69%** | **additions 5건, 최종 리포트에 전부 생존** |
| Stage 3 (counter) | 2,017자 — 7% | missedIssues 4건 |

Stage 2 는 상대 렌즈 issue 에 `agree`/`adjust`/`false_positive` 를 매기는 **판정**만 하는 것이 아니라, 교차하며 **새 발견을 만든다**. 그 5건이 최종에 `XA:`·`XQ:` 로 남았다. Stage 3 도 출력은 작지만 `missedIssues` 4건을 냈다.

⭐ **어느 스테이지도 순수 판정이 아니다.** effort 차등의 전제(일부는 판정만 하니 낮춰도 된다)가 이 워크플로에서는 성립하지 않는다.

⛔ `xhigh` 는 관성이 아니라 **결정된 값**이다 — `ultracode` 가 effort arm 으로 무효라는 실측 뒤 사용자가 유지를 택했다(CHANGELOG v4.14.0 T0). 근거 없이 되돌리지 않는다.

**언제 다시 볼 것인가**: 위 표는 **N=1** 이다. Tier 3 실행이 3건 누적되면 아래를 본다.

- Stage 2 의 `additions` 가 계속 최종에 생존하는가 → 생존하면 `xhigh` 정당
- 특정 스테이지의 출력량·기여가 일관되게 낮은가 → 그 스테이지만 `high` 로 ablation
- ⛔ 짝 비교로 잰다: 같은 입력에 `xhigh`/`high` 각 1회, **검증된 critical·major 손실 0** 이 통과 기준

### 수집 축소의 검증 계약 (ablation)

⛔ **켜짐/꺼짐만 확인하면 무엇을 잃었는지 모른다.** 게이팅이 트리거 표대로 동작해도 그 결과 발견이 줄었는지는 별개 질문이다.

**절차**: 같은 diff 를 **두 번** 돌린다 — 전량 수집 1회, 게이팅 1회. 두 산출을 짝으로 비교한다.

**사전등록 기준** (⛔ 사후 변경 금지)

| 축 | 허용 |
|---|---|
| 검증된 `critical`·`major` 고유 발견 | **손실 0** |
| `minor`·`suggestion` | 손실 허용 — 단 건수를 기록 |
| 축별 커버리지 (`discoveryAxis`) | 전량 대비 **빈 축이 늘지 않을 것** |

**위반 시**: 해당 수집 항목을 **즉시 상시로 되돌린다.** 조정이 아니라 원복이다 — 임계를 낮춰 통과시키면 기준이 사후 변경된다.

⚠️ 짝 비교는 비싸다(같은 입력 2회). 게이팅을 **랜딩하기 전에** 하고, 이후에는 `stage2Ran` 처럼 반환 필드로 관측한다.

## Tier 0 (Solo) 절차

> Orchestrator(Lead) 단독 분석. sub-agent + Codex 호출 없음. 작은 PR(<100 changed lines) 디폴트.

### Gather
- WORK_DIR 초기화 + diff 수집 (SKILL.md Gather Step 0-5 그대로)
- Tier-Adaptive evidence (3개만):
  - `${WORK_DIR}/requirements.md` (PR title/body, JIRA acceptance criteria)
  - `${WORK_DIR}/evidence/old-new-pairs.md` (변경 함수 페어)
  - `${WORK_DIR}/base-behavior.md` (base 코드, origin 판정 근거)
- 생략: producer-consumer, base-patterns, convention-samples, caller-analysis, semantic-mapping
- Fact Verification Gate **전건 유지** (SKILL.md Gather Step 4)
  > ⛔ 경로가 가볍다고 약화하지 않는다. 렌즈가 없어 배포 반경은 작지만 **틀린 Fact 를 반박할 주체도 없다** — 교정 기회가 0 이라 오히려 더 필요하다. 부담도 작다: 상시 evidence 가 3~4종이라 Fact 수 자체가 적다.

### Analyze
Lead 단독으로 아래 perspectives 를 검토한다 (9 perspectives 중 선별 — 근거는 § DiscoveryContract).

**상시 5**
1. Architecture Decision
2. Functional Decomposition
3. Modern API
4. Requirements Alignment
5. ⭐ **Concurrency Safety — Level 1(트리거 스캔)**

**조건부 2**
6. Refactoring Completeness — 리팩토링·치환·제거가 diff 에 있을 때
7. Dependency Impact — import·DI·초기화 경로가 바뀔 때

⛔ **Concurrency Safety 가 상시인 이유**: `<100줄` 이라도 `Task {}` 하나로 data race 가 생기고 크래시로 이어진다. 그런데 auto-tier 의 `RISK_PATTERN` 은 **키워드가 보일 때만** 승격시킨다 — `static let shared` + `var` 같은 **역방향 신호는 그 패턴에 없다**. 즉 키워드 없는 동시성 위험은 Tier 0 에 남고, 여기서 보지 않으면 아무도 보지 않는다.

⛔ **Level 1 과 Level 2 를 나눈다** — Level 1 은 트리거 스캔이다(공유 가변 상태·비동기 진입점·콜백 스레드를 diff 에서 훑는다). **양성일 때만** Level 2 로 올라가 `modules/safety-audit.md` 의 참조 추적·API 확인까지 수행한다. Level 2 를 상시로 두면 Lead 순차 작업이 늘어 시간 목표와 충돌한다.

⛔ **구조 축은 Lead가 직접 적용한다** — `modules/review-structural-axes.md` §3(축 5개)+§4(경계 문구)를 Read해 위 perspectives 와 **함께** 검토한다. Tier 0/1은 Workflow를 호출하지 않으므로 `args.structuralContext` 경로가 **존재하지 않는다**. 여기서 직접 적용하지 않으면 `<100줄` PR — 실무에서 가장 흔한 규모 — 은 구조 판정이 영구히 0건이다. (Tier 1도 Tier 0와 동일 perspectives 를 쓰므로 본 항목을 승계한다.)

sub-agent spawn 없음. Codex 호출 없음 (`--codex` 옵션 시 Tier 1 절차로 자동 전환).

### Synthesize
⛔ 산출물이 전수/카운트/부정 주장을 포함하면 **Coverage Gate**·**Negative-Result Gate** 는 경량 경로에서도 **생략 불가**(검증 경계) — 목록: `modules/peer-review-gates.md` § 경량 경로.

⛔ `${WORK_DIR}/evidence-move-drift.md` 가 있으면 **읽는다** — 이동 리팩토링이라는 뜻이고,
동등성 통과가 "이동 완료" 를 뜻하지 않는다(실측 #4774: 동등성 통과 후 단독 리뷰 0건 · 3렌즈 regression 3건).

⛔ **병합·판정 규칙은 `modules/peer-review-gates.md` § MergeContract 를 따른다** — Tier 0 도 예외가 아니다.
경량 경로라고 즉흥 판단을 허용하면, 렌즈가 없어 Lead 실측이 유일한 입력원인 Tier 0 에서
"무엇을 근거로 인정했는지"가 아무데도 남지 않는다. 특히 § 4 Lead 실측의 자격 · § 9 confidence(Tier 0 = 투표 없음).

Single-reviewer mode. Confidence Matrix 대신 simple checklist:

```markdown
| # | Issue | Severity | Origin | File:line | Suggestion |
|---|-------|----------|--------|-----------|------------|
```

Origin 보정(R/P/I), PR Intent Alignment Check는 그대로 적용 (SKILL.md Synthesize §2-§2.5 참조).

### Deliver
- `${WORK_DIR}/review-report.md` 작성 (의무)
- `${WORK_DIR}/pr-comments.md` 작성 (선택)
- `${WORK_DIR}/cost-log.json` 자동 작성 (아래 §비용 로깅 참조)
- ⛔ **축별 집계** — review-report.md 끝에 아래 표를 붙인다.

```markdown
## 발견 축 집계
| 축 | 건수 | 비고 |
|---|---:|---|
| code_quality | {n} | |
| structure | {n} | |
| correctness | {n} | |
| runtime_safety | {n} | |
| direction | {n} | |
| other | {n} | 어디에도 안 맞은 것 |
```

> Tier 2/3은 `PeerReviewSchema.discoveryAxis` 가 이 집계를 담지만 Tier 0/1은 스키마가 없다. **이 표가 그 자리를 대신한다** — 축 이름을 그대로 써야 경로 간 비교가 성립한다.
> ⛔ 0건인 축도 행을 지우지 않는다. **0이 관측인지 미탐색인지** 구별하려면 자리가 남아 있어야 한다.

---

## Tier 1 (Solo + Codex) 절차

> Tier 0 + Codex challenger 1회. 100-200 changed lines 또는 `--codex` 옵션.

### Gather
- Tier 0 + 추가 evidence 1개: `${WORK_DIR}/evidence/base-patterns.md`
- 합 4개 (requirements + old-new-pairs + base-behavior + base-patterns)

### Analyze
- Lead 단독 분석 (Tier 0와 동일 — 상시 5 + 조건부 2)
- + Codex challenger 1회 호출 (`< /dev/null` redirect 필수 — background 호출 시 stdin lock 방지):
  ```bash
  codex exec --skip-git-repo-check --sandbox read-only "$(cat /tmp/codex-challenger-prompt.txt)" \
    < /dev/null > ${WORK_DIR}/codex-challenger-raw.txt 2>&1
  ```
- Codex prompt는 압축 형태 (~5K input). evidence를 *인라인 embed* (자율 read 방지)

### Synthesize
⛔ **Coverage Gate**·**Negative-Result Gate** 는 경량 경로에서도 **생략 불가**(검증 경계). Codex 호출이 있으므로 **Reflection Rate** 도 산출 — ⛔ `N<10` 은 preliminary, verdict 없음. 목록: `modules/peer-review-gates.md` § 경량 경로.

⛔ **병합·판정 규칙은 `modules/peer-review-gates.md` § MergeContract 를 따른다.**
아래는 그 계약의 Tier 1 적용 요약이며, 어긋나면 계약이 이긴다.

- Lead + Codex 결과 dedup — 키는 § 3 (`파일` + `line_range` 겹침 + `discoveryAxis`)
- 2-vote Confidence Matrix (3-vote 대비 단순화) — § 9 Tier 1 행
- Codex verdict 처리는 § 6 — ⛔ `reverse` 는 제거가 아니라 `question` 전환
- Independence: Codex sandbox 독립 = HIGH

### Deliver
- review-report.md + pr-comments.md + cost-log.json
- ⛔ **축별 집계** — review-report.md 끝에 아래 표를 붙인다.

```markdown
## 발견 축 집계
| 축 | 건수 | 비고 |
|---|---:|---|
| code_quality | {n} | |
| structure | {n} | |
| correctness | {n} | |
| runtime_safety | {n} | |
| direction | {n} | |
| other | {n} | 어디에도 안 맞은 것 |
```

> Tier 2/3은 `PeerReviewSchema.discoveryAxis` 가 이 집계를 담지만 Tier 0/1은 스키마가 없다. **이 표가 그 자리를 대신한다** — 축 이름을 그대로 써야 경로 간 비교가 성립한다.
> ⛔ 0건인 축도 행을 지우지 않는다. **0이 관측인지 미탐색인지** 구별하려면 자리가 남아 있어야 한다.

---

## DiscoveryContract — 무엇을 찾는가

**보장**: 축이 **모든 경로에서 같은 이름으로** 집계된다 — 경로에 따라 이름이 바뀌거나 사라지지 않는다.

⛔ **`direction` 은 아직 배선되지 않았다.** 다섯 축 중 넷(`code_quality`·`structure`·`correctness`·`runtime_safety`)만 owner 가 있다. `direction` 은 집계 자리만 있고 발화 경로가 없으므로 **0 건이 "탐색했으나 없음"이 아니라 "탐색 안 함"** 이다. 리포트에 그렇게 표기한다 — 미탐색을 0 으로 읽으면 커버리지를 과대평가한다.

### 축 정의

| 축 | 무엇을 묻는가 | Tier 0/1 | Tier 2/3 |
|---|---|---|---|
| `code_quality` | 품질·dead code·성능 | perspectives 2·3 | review-quality |
| `structure` | 설계·레이어·확장성 | perspective 1 + 구조 축 5개 | review-arch + `structuralContext` |
| `correctness` | 로직·요구사항·엣지 | perspective 4 | review-correctness |
| `runtime_safety` | 동시성·메모리·크래시 | perspective 5 (Level 1 상시) | review-quality 역방향 트리거 + review-correctness race 검사 |
| `direction` | 접근 방향 자체의 대안 | 조건부 — 대안이 명백할 때 | 조건부 |

⛔ **`runtime_safety` 는 새 축이 아니라 배선이다.** owner 가 이미 있다 — `agents/review-quality.md` 가 *"동시성 코드 포함 시 **또는 역방향 감지 트리거 활성 시**"* 로 Concurrency Safety 를 소유하고, `agents/review-correctness.md` 도 race 를 검사한다. 부족한 것은 **발화 조건과 입력의 배선**이지 축 자체가 아니다.

⚠️ **`direction` 은 그대로 붙일 수 없다.** `agents/review-direction.md` 는 *계획·구현 전* 전용이다. 코드 리뷰에 쓰려면 입력과 판정 스키마를 따로 정의하거나 arch 렌즈의 조건부 질문으로 넣는다. **미해결로 남긴다** — 과장하지 않는다.

### 9 perspectives → 5축 매핑

⛔ `perspective` 를 이 축으로 **대체하지 않는다**. 소비 스키마가 9관점 어휘를 쓴다. 두 필드는 목적이 다르다 — `perspective` 는 어느 렌즈가 봤나, `discoveryAxis` 는 어떤 축의 발견인가.

| perspective | discoveryAxis |
|---|---|
| Architecture Decision · Extensibility · Over-Engineering | `structure` |
| Functional Decomposition · Modern API | `code_quality` |
| Dependency Impact · Refactoring Completeness | `code_quality` (구조 결정이면 `structure`) |
| Requirements Alignment | `correctness` |
| Concurrency Safety | `runtime_safety` |

한 발견이 여러 축에 걸치면 **1차 원인** 쪽을 고른다. 어디에도 안 맞으면 `other` — 억지로 맞추면 집계가 오염된다.

### 관점 선별 근거 (Tier 0/1)

9개를 다 올리면 Tier 0 이 Tier 2 가 되어 계층이 무의미해진다. 손실과 Lead 비용 두 축으로 갈랐다.

| 관점 | 판정 | 근거 |
|---|---|---|
| Concurrency Safety | **상시 (Level 1)** | 작은 diff 에서도 손실이 크고, 트리거 스캔은 비용이 낮다 |
| Refactoring Completeness | 조건부 | diff 밖을 보는 유일한 축이나 리팩토링이 아니면 무의미 |
| Dependency Impact | 조건부 | import·DI 변경 시에만 의미 |
| Extensibility · Over-Engineering | **Tier 2 유지 ⚠️ provisional** | 작은 변경에서 우선순위가 낮고 판단 비용이 높다. ⛔ 단 `modules/review-structural-axes.md` 의 구조 축(대안 ≥2·스레드 가정·public API 모양)이 이미 일부를 커버한다 — **관점 이름을 세어 '빠졌다'고 한 것이지 질문 커버리지를 분석한 것이 아니다.** N 누적까지 잠정 |

### 축이 실제로 배선됐는지 검사

각 축은 아래 6개가 **전부** 있어야 한다. 표가 채워졌는지만 보면 placeholder 도 통과한다.

`trigger`(무엇이 발화시키나) · `owner`(누가 보나) · `input`(무엇을 읽나) · `output`(어느 필드로 나오나) · `fallback`(owner 부재 시) · `fixture`(발화를 증명하는 회귀 자료)

⛔ **조건부 발화를 유지한다.** 축을 늘리면 오탐이 는다 — 내부 관측에서 한 축을 11곳에 적용해 9곳이 발화했으나 진짜 결함은 1곳이었다. Lead 에게 20건 넘게 도착하는 문제도 별도로 기록돼 있다.

## Tier-Adaptive Evidence

> ⛔ **canonical set** — 수집 항목의 정본 목록이다. 행 수가 아니라 **ID 집합**으로 대조한다. 행만 세면 빠진 항목 대신 중복이 들어가도 통과한다.

**evidence 9종**

| ID | Tier 0 | Tier 1 | Tier 2 | Tier 3 | 조건부 발화 |
|---|:---:|:---:|:---:|:---:|---|
| `requirements` | ✓ | ✓ | ✓ | ✓ | 상시 |
| `old-new-pairs` | ✓ | ✓ | ✓ | ✓ | 상시 |
| `base-behavior` | ✓ | ✓ | ✓ | ✓ | 상시 |
| `base-patterns` | — | ✓ | ✓ | ✓ | — |
| `producer-consumer` | — | — | ✓ | ✓ | — |
| `convention-samples` | — | — | ✓ | ✓ | — |
| `caller-analysis` | ⊕ | ⊕ | ⊕ | ✓ | init·DI·초기화 경로 변경 |
| `semantic-mapping` | ⊕ | ⊕ | ⊕ | ✓ | 리팩토링·치환·마이그레이션 |
| `deletion-verification` | ⊕ | ⊕ | ⊕ | ✓ | 심볼·함수 제거 |

`✓` 상시 · `⊕` 조건부 · `—` 미수집

⛔ **`deletion-verification` 은 이 표에 없었다** — `skills/fz-peer-review/SKILL.md` § Code Evidence Collection 에는 있는데 여기 열이 빠져 SSOT 가 갈라져 있었다. 두 곳의 ID 집합이 같아야 한다.

⛔ **Tier 0/1 의 상시 3종은 축소 대상이 아니다.** 이미 최소다 — 여기서 더 줄이면 origin 판정 근거가 사라진다.

⭐ **조건부는 Tier 0/1 에도 열려 있다.** C2 가 Refactoring Completeness · Dependency Impact 를 Tier 0/1 조건부 관점으로 올렸는데, 그 관점은 위 `⊕` 3종을 입력으로 요구한다. **관점만 켜고 입력을 막으면 부분 분석이 된다.**

**pre-cache 7종** — ⛔ 지금까지 Tier 차등 없이 전부 수집했다. Tier 0 Gather 가 *"SKILL.md Gather Step 0-5 그대로"* 라서 작은 PR 에서도 전량이 돈다.

| ID | 발화 조건 |
|---|---|
| `arch_layer_map` | 상시 (구조 축 입력) |
| `import_graph` | import·의존 방향 변경 |
| `protocol_conformers` | protocol 선언·conformance 변경 |
| `deprecated_symbols` | 상시 (저비용 grep) |
| `stream_paradigms` | 리액티브·비동기 패턴 등장 |
| `existing_utilities` | 신규 타입·헬퍼 추가 |
| `base_class_hierarchy` | class init·willSet 변경 |

⛔ **신호가 애매하면 켠다.** 과수집은 시간을 쓰고 누락은 판정을 망친다 — 비용이 대칭이 아니다.

⛔ **스킵은 기록한다.** 무엇을 건너뛰었는지 리포트에 남기지 않으면 "수집했는데 없었다"와 "안 봤다"를 구별할 수 없다.

> evidence 수집 절차 본문: `modules/evidence-collection.md` 참조. Tier-adaptive는 본 모듈 단일 정의.

---

## 비용 로깅 (모든 Tier)

> 측정 없이 검증 불가. Tier별 토큰/duration/이슈 발견 수를 기록하여 사용자가 before/after 비교.

### 수집 시점
Synthesize 단계 직전 (Lead가 모든 agent/Codex 응답 합류 후).

### 수집 소스
- **Agent <usage> 블록**: Agent tool 응답에 포함된 `<usage>total_tokens: N tool_uses: M duration_ms: T</usage>`
- **Codex output**: `codex exec` stdout 마지막 부분 `tokens used N`
- **Lead 추정**: tool_use 횟수 × 평균 (보수적)

### 출력 형식 1 — review-report.md 안

```markdown
## 실측 비용
- Tier: {0|1|2|3}  ·  Stage2 발화: {true|false}
- Total tokens: {N}K (Lead {a}K + Agents {b}K + Codex {c}K)
- Duration: {N}분 {M}초  ← ⛔ **구간 분해**: Gather {x}분 / Analyze {y}분 / Synthesize·Deliver {z}분
- 필수 read-set: {N}줄  (`python3 scripts/hydration_manifest.py`)
- 이슈 발견 수: Critical {n} / Major {m} / Minor {l} / Suggestion {p}
- 축별 발견: code_quality {n} / structure {n} / correctness {n} / runtime_safety {n} / direction {n} / other {n}
- cost-log.json: ${WORK_DIR}/cost-log.json
```

⛔ **구간 분해가 없으면 판정이 불가능하다.** 계약 도입으로 Lead 가 읽는 양이 늘었고(필수 read-set 증가) 동시에 교차·DA 가 워크플로로 넘어가 Lead 수동 작업이 줄었다. **두 변화가 반대 방향**이라 총 duration 하나로는 어느 쪽이 이겼는지 알 수 없다.

- Gather 가 늘었으면 → 수집 게이팅이 덜 먹혔거나 read-set 증가가 원인
- Synthesize·Deliver 가 줄었으면 → 교차·DA 이관이 먹힌 것
- ⛔ 둘 다 늘었으면 **되돌릴 후보를 지목**한다 (계약 압축 · 게이팅 강화)

⚠️ 구간 경계는 산출물 생성 시각으로 근사한다 — 정밀 계측이 아니다. 턴 사이 대기가 섞이므로 **같은 방식으로 잰 값끼리만** 비교한다.

쓰기 실패 시: 본 섹션에 `"⚠️ 비용 로깅 실패 ({reason}). 토큰 추정만 가능 (~{est}K)."` 명시 (silent skip 금지).

### 출력 형식 2 — cost-log.json

```json
{
  "$schema": "fz-plugin/cost-log-v1",
  "pr_number": 3970,
  "tier": {
    "selected": 0,
    "auto": 0,
    "override": "auto",
    "rationale": "CHANGED_LINES=13"
  },
  "changed_lines": {"added": 11, "deleted": 2, "total": 13},
  "tokens": {
    "lead": 30000,
    "agents": {},
    "codex": 0,
    "total": 30000,
    "method": "actual"
  },
  "duration_ms": 60000,
  "issues": {"critical": 0, "major": 0, "minor": 1, "suggestion": 1},
  "timestamp": "2026-05-12T08:00:00Z",
  "version": "1.0"
}
```

### Schema validation
```bash
jq -e '
  (.tier.selected | type == "number" and . >= 0 and . <= 3) and
  (.tokens.total | type == "number" and . > 0) and
  (.changed_lines.total | type == "number" and . >= 0) and
  (.timestamp | test("^[0-9]{4}-[0-9]{2}"))
' ${WORK_DIR}/cost-log.json
```

### 에러 처리
- cost-log.json 쓰기 실패 → review-report.md에 visible warning + 본문에 토큰 추정만
- tokens 파싱 실패 → `"method": "estimated"` 표시 + warning
- jq 미설치 → JSON skip + warning (review-report.md만 작성)

---

## Tier 2: Lite — 실행 시퀀스

> ⛔ **standalone Agent() 금지** — Analyze는 `workflows/peer-review.js` Workflow가 소유한다 (결정적 스크립트, P2P SendMessage 없음). `SKILL.md` Boundaries와 동일 지시.

```
1. Lead: Workflow({ scriptPath: '{플러그인 루트}/workflows/peer-review.js',
                    args: { diffPath, intentContext, evidencePaths, basePath, deep: false,
                            structuralContext } })   // ⛔ 누락 시 에러 없이 구조 축이 꺼진다
2. 스크립트: Stage1 3-병렬 (review-arch / review-quality / review-correctness — 전부 opus)
             → parallelWithRetry (null 항목 1회 순차 재시도 = rate-limit 폴백 계약)
3. Lead: /fz-codex 경유 Codex challenger ×1  (out-of-band — ⛔ 스크립트 내 cross-provider 스폰 금지)
4. 반환 { mode:'workflow', tier:2, reviews, issues, metrics } → Lead 단순 병합 (Matrix 미투표)
```

⛔ **Tier 2 반환 계약 — 트리거 발화 여부로 필드가 달라진다** (D1):

| 필드 | 미발화 (3-call) | 발화 (5-call) | Tier 3 |
|---|:---:|:---:|:---:|
| `stage2Ran` | `false` | `true` | `true`/`false` |
| `stage2Trigger` | ✓ (판정 근거) | ✓ | ✓ |
| `crossVerdict`·`crossNote` | — | ✓ | ✓ |
| `crossSeverity` | — | ✓ (조정 제안) | — |
| `crossAdjustments` | — | ✓ | ✓ |
| `finalSeverity`·`counterVerdict` | — | — | ✓ (Stage 3) |

⛔ Tier 2 는 발화해도 **`finalSeverity` 를 만들지 않는다.** 교차 조정은 `crossSeverity` 에 **제안으로** 싣고 최종 판정은 Lead 병합 계약이 한다 — Tier 2 미투표(Wave 4 확정)를 스크립트가 지키는 방식이다.
⛔ `stage2Ran` 은 **조용한 off 방어**다. 필드가 없으면 트리거가 안 걸린 것인지 스크립트가 옛 버전인지 구별할 수 없다. Confidence Matrix를 만들 때 `severity`(원본)를 쓰고, 교차·DA 열은 "미수행"으로 표기한다 — 필드를 찾다 실패하면 Matrix가 판정 불가로 멈춘다.

에이전트 브리프는 스크립트가 조립한다 (OVERRIDE 블록 + TARGET). Lead가 args로 넘길 것:
- `diffPath` / `basePath`(base 원본 prefetch — 에이전트가 요청하지 않는다) / `evidencePaths`
- `structuralContext` — `modules/review-structural-axes.md` §3(축 5개)+§4(경계 문구)를 Read해 담는다. **arch 렌즈에만 주입**되고 optional이므로, 빠뜨리면 `mode:'workflow'`가 정상 반환되면서 구조 판정만 0건이 된다
- [Mapping] `evidence/semantic-mapping.md` 존재 시 워커가 raw source + atom table을 직접 read (Lead 요약 금지, v4.4.0)

---

## Tier 3: Full (--deep) — 추가 시퀀스

같은 스크립트를 `deep: true`로 호출하면 Stage2·3이 이어진다 (총 6 call).

```
Stage 1: 3-병렬 독립 분석 (Round 1 독립성 — 피어 데이터 미주입)
Stage 2: arch ↔ quality id-기반 교차 severity 조정 (correctness 불참)
         false_positive 판정은 실측 인용 필수
Stage 3: review-counter DA — issues 반론 + strengths 도전
→ 반환 { …, crossAdjustments, strengthChallenges, distribution } → Lead가 Matrix에 반영
→ Lead: Codex DA ×1 추가 (/fz-codex)
```

> SendMessage 실시간 멀티턴 수렴은 **고정 1-pass 교차로 대체**됐다 (충실도 trade-off — 은폐하지 않고 명시). 라운드 의미론 canonical은 `patterns/live-review.md`에 보존.

---

## Codex Analyze 호출

> `get_codex_skill_path()` 3-Tier 디스커버리 + codex exec 패턴: `modules/cross-validation.md` 참조.

Codex challenger 프롬프트에 필수 포함:
- Origin Classification(regression/pre-existing/improvement)
- Inheritance Chain(base class init/willSet 변경 시 subclass 검색)
- `schemas/codex_peer_review_schema.json` 스키마 사용

결과: `${WORK_DIR}/codex-challenger-result.json`

⛔ codex exec background 호출 시 stdin lock 회피: `< /dev/null` redirect 필수.

---

## Cross-Critique Anti-Sycophancy Rule

> PR 교훈: Sonnet(QUAL-4)이 코드 증거 있는 정답을 제시했으나, Opus(ARCH-1)의 "아키텍처 원칙상" 이론적 주장에 self-reverse. 유일하게 맞는 판단이 탈락.

⛔ **코드 증거 없이 피어의 이론적 주장에 self-reverse 금지.**

- challenge/reverse 시 **코드 증거** (file:line + 실제 코드) 필수
- 자신의 finding 철회는 피어가 **caller 코드 또는 convention 증거**를 제시한 경우에만
- "아키텍처 원칙상 X" (이론) vs "호출 구조를 보면 Y" (실증) → 실증 우선

```
BAD: ARCH-1 "DIP 위반" → QUAL-4 "맞습니다, 철회합니다" (증거 없는 동조)
GOOD: ARCH-1 "DIP 위반" → QUAL-4 "caller-analysis.md를 보면 default 없는 쪽이
      오히려 ViewModel에서 더 많은 concrete 타입을 참조합니다" (증거 기반 보완)
```

### Codex Devil's Advocate (공통, 1회 추가 호출)

DA 사전 검증: 현재 브랜치 ≠ PR head이면 "diff 기준" 경고 삽입. reverse 판정은 `git show pr-{PR}:{file}`로 교차 확인.

DA 판정:
- `agree` → flagged_by 추가
- `challenge` → confidence -20%
- `supplement` → 보완
- `reverse` → ⛔ **EXCLUDE 아님.** `question` 으로 전환하고 판별 oracle 을 적는다
  (정본: `modules/peer-review-gates.md` § MergeContract § 6). 이종 검증에 삭제 권한을 주면
  코드로 결판나지 않는 사안이 조용히 사라진다. reverse 시 PR 브랜치 코드로 교차 확인.

---

## 타임아웃 + 폴백

에이전트별 타임아웃 수치(review-arch/quality 5분, Codex 3분, 전체 15분)는 **운영 목표이지 배선이 아니다** — `workflows/peer-review.js`에 timeout 구현이 없다(grep 0건). 스톨은 Lead가 관측해 판단한다.
타임아웃 항목은 `parallelWithRetry`가 1회 순차 재시도하고, 그래도 null이면 `reviews`에서 제외된다 — ⛔ `agent_status` 필드는 `PeerReviewSchema`에 없으므로 Lead 보정 대상이 아니다.
폴백 체인: Tier 3→2→1→0 자동 전환.
