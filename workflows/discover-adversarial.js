// workflows/discover-adversarial.js — fz-discover 비대화 다라운드 탐색 (TEAM 모드 대체 pilot)
//
// [API 계약 전제 — verified: Claude Code Workflow 도구 사양 + 2026-06-05 세션 실측 3회 (S0 스모크 포함)]
//   agent(prompt, {label, phase, schema, model, agentType}) → 서브에이전트 1개. schema 루트는 object,
//     위반 시 자동 재시도. agentType은 플러그인 네임스페이스 필수 (S0 실측: 'fz:plan-structure' O / 'plan-structure' X).
//   parallel([thunks]) → 동시 barrier. 실패 에이전트 = null (silent fail 불가) → .filter(Boolean).
//   phase(title)/log(msg) → 진행 표시. budget.{total,spent(),remaining()} — total null이면 remaining()=Infinity.
//   제약: P2P 통신 불가(데이터는 스크립트 경유) / 시각·난수 API 불가(시간 측정은 Lead 책임) /
//     에이전트 최종 텍스트 = 반환값(1-shot raw data) / 동시 캡 min(16, cores-2).
//   호출(Lead, SKILL.md 절차): Workflow({ scriptPath: '{plugin_root}/workflows/discover-adversarial.js',
//     args: { problem, codeContext, constraintsKnown, deep }  // ts 제거: 미사용 + resume 캐시 미스 유발 (리뷰 교정) })
//   명명 등록: 플러그인 workflows/*.js의 meta.name이 명명 워크플로우로 자동 등록됨(스킬 목록 등장 실측) — scriptPath 없이 이름 'discover-adversarial' 호출 가능.
//   반환 계약: { mode: 'workflow', landscape, paths, costs, metrics } 또는 { mode: 'fallback', reason }
//     → mode='fallback'이면 Lead는 SKILL.md 기존 SOLO REP 경로 수행. wall-clock 측정은 Lead 책임(스크립트는 시각 API 불가).
//
// [설계 근거 — TVING/fz-teams-workflow-migration/plan/plan-final.md]
//   default = lean 5-call (TEAM 2-agent 비용 동급). --deep = 렌즈 3 fan-out → merge(opus 언어 지시) →
//   경로별 평가 chunk ≤4 (agent-team-guide L222 거버넌스 정합) → 합성. refuter 없음 (harness-engineering
//   L623 Verifier -0.8% 존중). 산출물 계약: LandscapeSchema → discover-journal.md 4섹션 (Lead 기록, 경로 무변경).

export const meta = {
  name: 'discover-adversarial',
  description: 'fz-discover 비대화 다라운드 탐색 — lean 5-call(default) / 렌즈 fan-out(--deep). 결론 미산출, Landscape Map 반환',
}

// ── 스키마 (루트 전부 object — schema 강제) ──
const PathSetSchema = {
  type: 'object', required: ['paths'],
  properties: {
    paths: {
      type: 'array', minItems: 2, maxItems: 4,
      items: {
        type: 'object', required: ['id', 'mechanism', 'prerequisites'],
        properties: {
          id: { type: 'string' },
          mechanism: { type: 'string' },
          prerequisites: { type: 'array', items: { type: 'string' } },
          mergedFrom: { type: 'array', items: { type: 'string' }, description: '--deep 병합 출처 렌즈 (merge 단계만 기록)' },
        },
      },
    },
  },
}

const CostRiskSchema = {
  type: 'object', required: ['assessed'],
  properties: {
    assessed: {
      type: 'array',
      items: {
        type: 'object', required: ['pathId', 'cost', 'risk', 'conditions'],
        properties: {
          pathId: { type: 'string' },
          cost: { type: 'string', enum: ['low', 'mid', 'high'] },
          risk: { type: 'string', enum: ['low', 'mid', 'high'] },
          conditions: {
            type: 'array',
            items: {
              type: 'object', required: ['id', 'mutability', 'evidence', 'confidence'],
              properties: {
                id: { type: 'string' },
                mutability: { type: 'string', enum: ['locked', 'unlocked'] }, // 1회 판정 + evidence (refuter 없음)
                confidence: { type: 'string', enum: ['high', 'mid', 'low'] }, // journal '확신도' 칼럼 매핑
                evidence: { type: 'string' },
              },
            },
          },
        },
      },
    },
  },
}

const LandscapeSchema = {
  type: 'object', required: ['tradeoffTable', 'openQuestions'],
  properties: {
    tradeoffTable: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          path: { type: 'string' },
          prerequisites: { type: 'string' },
          cost: { type: 'string' },
          risk: { type: 'string' },
          fitWhen: { type: 'string' },
          mergedFrom: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    openQuestions: { type: 'array', minItems: 1, items: { type: 'string' } },
    // verdict 필드 없음 — discover는 결론 미산출(SKILL.md 행동 원칙). 합의/불합의는 conditions[].mutability로 명시.
  },
}

// merge 출력 전용: 렌즈3 × maxItems4 = 원천 최대 12 — maxItems 4 강제 시 distinct 경로 silent 탈락 (리뷰 major 교정)
const MergedPathSetSchema = {
  type: 'object', required: ['paths'],
  properties: {
    paths: {
      type: 'array', minItems: 2, maxItems: 12,
      items: PathSetSchema.properties.paths.items,
    },
  },
}

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [문제]/[코드 컨텍스트]/[기지 제약]만이 과제의 전부다. ' +
  '무관한 작업 폴더(ASD-*, 토픽 폴더 등)를 읽지 말 것. 파일 탐색은 [코드 컨텍스트]가 지시한 범위만. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. 출력은 schema 준수 JSON.'

// ── args 방어 파싱 (실측: scriptPath 호출 시 args가 JSON 문자열로 도착 — wf_89418b73 probe) ──
const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

// ── callAgent 래퍼: 전 호출 단일 집계 + null 직접 카운트 ──
let agentCalls = 0
let nullCalls = 0
let fallbackCount = 0
async function callAgent(prompt, opts) {
  agentCalls += 1
  const out = await agent(prompt, opts)
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) }
  return out
}

// ── 공통: 경로 묶음 비용 평가 (default·deep 공유) ──
function evalCostThunk(pathBundle, lensLabel) {
  return () => callAgent(
    `${OVERRIDE}\n[역할] 비용/리스크 평가자(review-arch 렌즈)\n` +
    `[경로] ${JSON.stringify(pathBundle)}\n` +
    `[채점축] 각 경로 cost/risk(low/mid/high) + 조건 불변성(locked/unlocked) 1회 판정 + 근거 코드 인용(evidence) + 확신도(confidence). ` +
    `부수지 말고 비용을 밝힌다.`,
    { label: `cost-${lensLabel}`, agentType: 'fz:review-arch', model: 'sonnet', schema: CostRiskSchema })
}

// ════════════════════════════════════════════════════════════════
//  DEFAULT (lean 5-call): 경로생성(opus) → 비용평가(sonnet) → R2추가 → R2비용 → 합성(opus)
// ════════════════════════════════════════════════════════════════
async function runLean() {
  phase('Round 1: 경로 생성 + 비용 탐색')
  const r1paths = await callAgent(
    `${OVERRIDE}\n[역할] 경로 생성자(plan-structure 렌즈)\n[문제] ${input.problem}\n` +
    `[코드 컨텍스트] ${input.codeContext}\n[기지 제약] ${JSON.stringify(input.constraintsKnown)}\n` +
    `[목표] 경로 2-4개 생성, 각 전제조건 명시. 탈락시키지 말 것.`,
    { label: 'r1-paths', agentType: 'fz:plan-structure', model: 'opus', schema: PathSetSchema })
  if (!r1paths) { fallbackCount += 1; return { mode: 'fallback', reason: 'r1-paths null', metrics: metrics() } }

  const r1cost = await evalCostThunk(r1paths.paths, 'r1')()
  if (!r1cost) { fallbackCount += 1; return { mode: 'fallback', reason: 'r1-cost null', metrics: metrics() } }

  phase('Round 2: 추가 경로 + 조건 도전')
  const r2paths = await callAgent(
    `${OVERRIDE}\n[역할] 경로 생성자\n[기존 경로+비용] ${JSON.stringify({ r1paths, r1cost })}\n` +
    `[목표] unlocked(🔓) 조건을 무시한 새 경로 탐색 + 기존 경로 조건 업데이트.`,
    { label: 'r2-paths', agentType: 'fz:plan-structure', model: 'opus', schema: PathSetSchema })
  const r2cost = r2paths ? await evalCostThunk(r2paths.paths, 'r2')() : null
  if (!r2paths) log('WARN r2-paths null — R2 skipped, R1만으로 Landscape (라운드 미완주)')
  else if (!r2cost) log('WARN r2-cost null — R2 비용 미산정 (부분 미완주)')

  const allPaths = [r1paths, r2paths].filter(Boolean)
  const allCost = [r1cost, r2cost].filter(Boolean)
  const roundsCompleted = (r2paths && r2cost) ? 2 : 1
  return synth(allPaths, allCost, roundsCompleted)
}

// ════════════════════════════════════════════════════════════════
//  --deep: 렌즈 3 fan-out(sonnet) → merge(opus 언어 지시) → 경로별 평가 chunk ≤4 → 합성
//  렌즈 전부 sonnet — 동시 opus ≤2 준수(Lead 포함). refuter 없음.
// ════════════════════════════════════════════════════════════════
async function runDeep() {
  // budget 가드 실배선: 예산 부족 시 lean 회귀 (total null이면 remaining()=Infinity → 가드 미발동)
  if (budget.total && budget.remaining() < budget.total * 0.4) {
    log('WARN budget<40% remaining → --deep 렌즈 fan-out 생략, lean 회귀')
    return runLean()
  }

  phase('Round 1 (deep): 렌즈 3 fan-out 경로 생성')
  const lenses = ['reuse-first', 'greenfield', 'hybrid']
  const lensThunks = lenses.map((lens) => () => callAgent(
    `${OVERRIDE}\n[역할] 경로 생성자 — 렌즈: ${lens}\n[문제] ${input.problem}\n` +
    `[코드 컨텍스트] ${input.codeContext}\n[기지 제약] ${JSON.stringify(input.constraintsKnown)}\n` +
    `[목표] ${lens} 관점에서 경로 2-4개 생성 + 전제조건. 탈락 없음.`,
    { label: `lens-${lens}`, agentType: 'fz:plan-structure', model: 'sonnet', schema: PathSetSchema }))
  const lensResults = (await parallel(lensThunks)).filter(Boolean)
  if (lensResults.length === 0) { fallbackCount += 1; return { mode: 'fallback', reason: 'all lenses null', metrics: metrics() } }
  if (lensResults.length < lenses.length) log(`WARN 렌즈 ${lenses.length - lensResults.length}개 null (부분 fan-out)`)

  // merge = opus agent 언어 지시 (해석 필요 작업 — skill-authoring §11 분류. 기계적 유사도 판정 금지)
  phase('Round 1.5 (deep): 렌즈 경로 병합')
  const merged = await callAgent(
    `${OVERRIDE}\n[역할] 경로 병합자\n[렌즈별 경로] ${JSON.stringify(lensResults)}\n` +
    `[목표] 본질이 같은 경로는 병합하되 mergedFrom에 출처 렌즈 표기. 어떤 경로도 제거하지 말 것 — ` +
    `병합은 표기이지 탈락이 아니다. 진짜 다른 축만 분리 유지(REP 규칙 2).`,
    { label: 'merge', agentType: 'fz:plan-structure', model: 'opus', schema: MergedPathSetSchema })
  if (!merged) { fallbackCount += 1; return { mode: 'fallback', reason: 'merge null', metrics: metrics() } }

  // 경로별 평가 — 구조적 유계: 렌즈3 × maxItems4 = 병합 전 ≤12, 병합은 중복 통합으로 감소만.
  phase('Round 2 (deep): 경로별 비용 평가 fan-out')
  if (budget.total && budget.remaining() < budget.total * 0.2) {
    log('WARN budget<20% → 경로별 평가를 일괄 1-call로 축소 (상한 도달)')
    const lump = await evalCostThunk(merged.paths, 'deep-lump')()
    if (!lump) { fallbackCount += 1; return { mode: 'fallback', reason: 'deep cost null', metrics: metrics() } }
    return synth([merged], [lump], lensResults.length === lenses.length ? 2 : 1)
  }
  // 거버넌스 정합(agent-team-guide L222 "5개+ 동시 실행 시 추가 스폰 차단"): 동시 ≤4 chunk 순차
  const costThunks = merged.paths.map((p, i) => evalCostThunk([p], `deep-${i}`))
  const costResults = []
  for (let c = 0; c < costThunks.length; c += 4) {
    const chunk = await parallel(costThunks.slice(c, c + 4))
    costResults.push(...chunk.filter(Boolean))
  }
  if (costThunks.length > 4) log(`경로 평가 ${Math.ceil(costThunks.length / 4)}개 chunk 순차 (동시 ≤4, 거버넌스 정합)`)
  if (costResults.length === 0) { fallbackCount += 1; return { mode: 'fallback', reason: 'deep all-cost null', metrics: metrics() } }
  if (costResults.length < merged.paths.length) log(`WARN 경로 평가 ${merged.paths.length - costResults.length}개 null`)

  const deepComplete = lensResults.length === lenses.length && costResults.length === merged.paths.length
  return synth([merged], costResults, deepComplete ? 2 : 1) // 부분 null 시 1 — rollback 트리거 '완주율<100%' 가시화 (리뷰 교정)
}

// ════════════════════════════════════════════════════════════════
//  합성 (결론 미산출) — default·deep 공유
// ════════════════════════════════════════════════════════════════
function metrics() {
  return { agentCalls, nullCount: nullCalls, fallbackCount, roundsCompleted: 0 } // fallback = 미완주
}

async function synth(allPaths, allCost, roundsCompleted) {
  phase('합성: Landscape Map')
  const map = await callAgent(
    `${OVERRIDE}\n[역할] Landscape 통합자\n[경로] ${JSON.stringify(allPaths)}\n` +
    `[비용/조건] ${JSON.stringify(allCost)}\n` +
    `[목표] Trade-off Table + Open Questions 3개 이상. 병합 경로는 mergedFrom 유지. ` +
    `결론을 내리지 말 것 — 경로 선택은 plan의 몫.`,
    { label: 'landscape', agentType: 'fz:plan-structure', model: 'opus', schema: LandscapeSchema })
  if (!map) { fallbackCount += 1; return { mode: 'fallback', reason: 'landscape null', metrics: metrics() } }

  return {
    mode: 'workflow',
    landscape: map,
    paths: allPaths,
    costs: allCost,
    metrics: { nullCount: nullCalls, roundsCompleted, agentCalls, fallbackCount }, // Lead가 experiment-log §5.7 기록
  }
}

// ── 진입점 (top-level await — 세션 실증 형식: return이 Lead 수신값) ──
// fail-fast: args 미바인딩/필수 키 누락 시 에이전트 스폰 전 즉시 fallback (fabrication 방지)
if (!input || !input.problem || !input.codeContext) {
  log(`FATAL args invalid (typeof=${typeof args}) — problem/codeContext 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}, problem=${!!(input && input.problem)}`, metrics: metrics() }
}
return input.deep ? await runDeep() : await runLean()
