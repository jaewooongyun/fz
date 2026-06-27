# Peer Review 4-Tier Graceful Degradation

diff 크기에 따라 팀 구성과 비용을 자동 조절하는 티어 시스템.

---

## Tier 구성

| Tier | review-arch | review-quality | Codex | Cross-Critique | 비용 상한 |
|------|------------|----------------|-------|---------------|----------|
| **0 (Solo)** | Orchestrator 직접 | — | — | None | ~$0.10 |
| **1 (Solo+Codex)** | Orchestrator 직접 | — | codex exec ×1 | None | ~$0.30 |
| **2 (Lite Team)** | Opus 팀에이전트 ★ | Sonnet 팀에이전트 | codex exec ×1 | Lite (합성만) | ~$2.00 |
| **3 (Full Team)** | Opus 팀에이전트 ★ | Sonnet 팀에이전트 | codex exec ×2 | Full (SendMessage + DA) | ~$3.50 |

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
  RISK_PATTERN='auth|token|secret|credential|authorization|permission|role|admin|session|keychain|crypto|certificate|privacy|payment|billing|refund|IAP|InAppPurchase|StoreKit|migration|schema|CoreData|database|sql|public func|public class|public protocol|deinit|removeFromSuperview|deleteAll|@MainActor|actor |async |Task \{|withCheckedContinuation|xcconfig|Package\.swift|ci_scripts'
  RISK_MATCHES=$(grep -cE "$RISK_PATTERN" "${WORK_DIR}/diff.patch" 2>/dev/null || echo 0)
  if [ "$RISK_MATCHES" -ge 2 ]; then TIER=$((TIER + 2))
  elif [ "$RISK_MATCHES" -ge 1 ]; then TIER=$((TIER + 1))
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

### 옵션 precedence
1. `--tier N` (최우선, auto 무효화). invalid 값 → auto fallback + error log
2. `--deep` (auto Tier 2/3 시 Cross-Critique 활성화. auto Tier 0/1 시 warning + Tier 2 강제)
3. `--codex` (Tier 0 → Tier 1 효과: Codex challenger 1회 추가)

---

## Tier 0 (Solo) 절차

> Orchestrator(Lead) 단독 분석. sub-agent + Codex 호출 없음. 작은 PR(<100 changed lines) 디폴트.

### Gather
- WORK_DIR 초기화 + diff 수집 (SKILL.md Gather Step 0-5 그대로)
- Tier-Adaptive evidence (3개만):
  - `${WORK_DIR}/requirements.md` (PR title/body, JIRA acceptance criteria)
  - `${WORK_DIR}/evidence/old-new-pairs.md` (변경 함수 페어)
  - `${WORK_DIR}/base-behavior.md` (base 코드, origin 판정 근거)
- 생략: producer-consumer, base-patterns, convention-samples, caller-analysis, semantic-mapping
- Fact Verification Gate 유지 (SKILL.md Gather Step 4)

### Analyze
Lead 단독으로 다음 4 perspectives 검토 (9 perspectives 중 핵심만):
1. Architecture Decision
2. Functional Decomposition
3. Modern API
4. Requirements Alignment

sub-agent spawn 없음. Codex 호출 없음 (`--codex` 옵션 시 Tier 1 절차로 자동 전환).

### Synthesize
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

---

## Tier 1 (Solo + Codex) 절차

> Tier 0 + Codex challenger 1회. 100-200 changed lines 또는 `--codex` 옵션.

### Gather
- Tier 0 + 추가 evidence 1개: `${WORK_DIR}/evidence/base-patterns.md`
- 합 4개 (requirements + old-new-pairs + base-behavior + base-patterns)

### Analyze
- Lead 단독 분석 (Tier 0와 동일 4 perspectives)
- + Codex challenger 1회 호출 (`< /dev/null` redirect 필수 — background 호출 시 stdin lock 방지):
  ```bash
  codex exec --skip-git-repo-check --sandbox read-only "$(cat /tmp/codex-challenger-prompt.txt)" \
    < /dev/null > ${WORK_DIR}/codex-challenger-raw.txt 2>&1
  ```
- Codex prompt는 압축 형태 (~5K input). evidence를 *인라인 embed* (자율 read 방지)

### Synthesize
- Lead + Codex 결과 dedup
- 2-vote Confidence Matrix (3-vote 대비 단순화)
- Independence: Codex sandbox 독립 = HIGH

### Deliver
- review-report.md + pr-comments.md + cost-log.json

---

## Tier-Adaptive Evidence

| Tier | requirements | old-new-pairs | base-behavior | producer-consumer | base-patterns | convention-samples | caller-analysis | semantic-mapping |
|------|:------------:|:-------------:|:-------------:|:-----------------:|:-------------:|:------------------:|:---------------:|:----------------:|
| 0    | ✓            | ✓             | ✓             | —                 | —             | —                  | —               | —                |
| 1    | ✓            | ✓             | ✓             | —                 | ✓             | —                  | —               | —                |
| 2    | ✓            | ✓             | ✓             | ✓                 | ✓             | ✓                  | (init 변경 시) | (refactoring 시) |
| 3    | ✓            | ✓             | ✓             | ✓                 | ✓             | ✓                  | ✓               | ✓                |

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
- Tier: {0|1|2|3}
- Total tokens: {N}K (Lead {a}K + Agents {b}K + Codex {c}K)
- Duration: {N}분 {M}초
- 이슈 발견 수: Critical {n} / Major {m} / Minor {l} / Suggestion {p}
- cost-log.json: ${WORK_DIR}/cost-log.json
```

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

## Tier 2: Lite Team — 실행 시퀀스

> ⛔ Gate 0: 팀 생성 필수. **standalone Agent() 금지** — TeamCreate 호출 없이 Agent(subagent_type=...) 호출 또는 Agent() 호출 시 team_name 누락은 위반. standalone Agent는 결과가 return으로만 전달되어 에이전트 간 SendMessage 통신 불가.

```
1. TeamCreate(team_name="peer-review-{PR}")               # ⛔ 필수
2. TaskCreate × 2 (Architecture + Code quality)
3. Agent(name="review-arch", team_name=..., model="opus")  # ⛔ team_name 필수
   Agent(name="review-quality", team_name=..., model="sonnet")
4. Bash("codex exec ...")                                  # Codex challenger
5. 에이전트 완료 대기 → Lead 합성 → shutdown_request → TeamDelete
```

Task Brief (각 에이전트): `skills/{arch-critic|code-auditor}/SKILL.md` + `${WORK_DIR}/(diff.patch + symbols.json + requirements.md + base-behavior.md + evidence/*.md)`
- [Goal] 독립 이슈 발굴 | [Constraints] 피어 참조 금지, origin 필수
- [Mapping] `evidence/semantic-mapping.md` 존재 시 raw source + atom table 직접 read (Lead 요약 금지, v4.4.0)
- [Deliverable] `${WORK_DIR}/{arch-critic|code-auditor}-result.json`

---

## Tier 3: Full Team (--deep) — 추가 시퀀스

Tier 2 완료 후 2.5-Turn Protocol:
```
Round 1: (Tier 2) 각 에이전트 독립 분석 → *-result.json 저장
Round 2: 교차 피드백 (SendMessage 필수) — review-arch ↔ review-quality
Round 0.5: 최종 보고 → Lead에 [합의/불합의 항목] 전달
→ review-counter 스폰 (DA 패스) → Codex DA → Lead 합성 → TeamDelete
```

---

## Codex Analyze 호출

> `get_codex_skill()` 3-Tier 디스커버리 + codex exec 패턴: `modules/cross-validation.md` 참조.

Codex challenger 프롬프트에 필수 포함:
- Origin Classification(regression/pre-existing/improvement)
- Inheritance Chain(base class init/willSet 변경 시 subclass 검색)
- `schemas/codex_peer_review_schema.json` 스키마 사용

결과: `${WORK_DIR}/codex-challenger-result.json`

⛔ codex exec background 호출 시 stdin lock 회피: `< /dev/null` redirect 필수.

---

## Cross-Critique Anti-Sycophancy Rule

> PR #3646 교훈: Sonnet(QUAL-4)이 코드 증거 있는 정답을 제시했으나, Opus(ARCH-1)의 "아키텍처 원칙상" 이론적 주장에 self-reverse. 유일하게 맞는 판단이 탈락.

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
- `reverse` → EXCLUDE + 새 이슈(confidence 70). reverse 시 PR 브랜치 코드로 교차 확인.

---

## 타임아웃 + 폴백

에이전트별 타임아웃: review-arch/quality 5분, Codex 3분, 전체 15분.
타임아웃 시 `agent_status: "timeout"` + confidence ×0.5.
폴백 체인: Tier 3→2→1→0 자동 전환.
