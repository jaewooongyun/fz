// workflows/plan-collaborative.js — fz-plan 협업 설계 (TEAM collaborative 대체, Wave 2)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + Wave 0/1 실측]
//   표준 패턴 3종 적용. 대형 입력(코드 컨텍스트)은 파일 경로 전달 (§12).
//   호출(Lead, SKILL.md 절차): Lead가 codeContext 요약을 파일로 기록 후
//     Workflow({ scriptPath: '{plugin_root}/workflows/plan-collaborative.js',
//       args: { requirement, codeContextPath, constraintsKnown, discoverJournalPath? } })
//   반환: { mode:'workflow', plan: PlanSchema, directionVerdict, directionAlternatives, metrics }
//     | { mode:'direction_escalation', verdict, alternatives, rebuttal, metrics } → Lead가 사용자 확인 (대화는 Workflow 밖)
//     | { mode:'fallback', reason, metrics } → Lead는 SOLO plan 경로 수행.
//   Workflow 외부 Lead 책임 (이관 아님 — 회귀 확인 의무, 15차): stress-test Q1-Q6 / RTM 검증 /
//     Phase 0.7 Sprint Contract(Codex 회복 시) / Codex verify(Phase 2) / memory-curator recall /
//     plan-v{N}.md 파일 기록 / direction_escalation 사용자 대화 / wall-clock 측정.
//
// [설계 — modules/patterns/collaborative.md 평탄화]
//   Stage 0 direction(opus): 6관점 판정. PROCEED → 즉시 진행 / 비-PROCEED → 반박 왕복 1회 (+2 call).
//     조건부화 정당화: 원 패턴(L28-33)은 무조건 반박 왕복이나, PROCEED 경로의 반박은 판정 불변
//     dead-call이므로 제거 — 비-PROCEED만 판정 반전 기회 실재 (검증 승인 판정).
//   Stage 1 draft(opus) → Stage 2 병렬 3 [impact(Scan a-f)/edge/arch, sonnet — 동시 3
//     [verified: §5.7 #4 deep — lens 3 동시 parallel clean]] → Stage 3 CC 교차 2 (collaborative L47-55
//     보존: edge↔impact "경계 케이스가 영향 범위에서 발생" 연쇄) → Stage 4 integrate(opus, PlanSchema =
//     다운스트림 계약 전체) → Stage 5 arch 재검증 (collaborative Round 2 L57-63).
//   opus 동시 ≤1 (+Lead=2): 전 opus 호출 순차 — parallel 블록(Stage 2/3)은 sonnet 전용.
//   budget 가드: 해당 없음 — 9-11 call, 분기 상한 고정(비-PROCEED 시 +2)이므로 가변 fan-out 아님 (§12 단서).

export const meta = {
  name: 'plan-collaborative',
  description: 'fz-plan 협업 설계 — direction 판정(조건부 반박) → 초안 → 병렬 3렌즈 + CC 교차 → 통합(다운스트림 계약 전체) → 재검증. 9-11 call',
}

const DirectionSchema = {
  type: 'object', required: ['verdict', 'structuralFit', 'alternatives', 'concerns'],
  properties: {
    verdict: { type: 'string', enum: ['PROCEED', 'RECONSIDER', 'REDIRECT'] },
    structuralFit: { type: 'string' },
    alternatives: { type: 'array', minItems: 2, items: { type: 'object', required: ['name', 'rationale'], properties: { name: { type: 'string' }, rationale: { type: 'string' } } } },
    extensibility: { type: 'string' },
    concerns: { type: 'array', items: { type: 'string' } },
  },
}

const RebuttalSchema = {
  type: 'object', required: ['rebuttal'],
  properties: { rebuttal: { type: 'string' }, additionalConstraints: { type: 'array', items: { type: 'string' } } },
}

const DraftSchema = {
  type: 'object', required: ['steps', 'readScope', 'assumptions'],
  properties: {
    steps: { type: 'array', items: { type: 'object', required: ['id', 'title', 'files', 'approach'], properties: { id: { type: 'string' }, title: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, approach: { type: 'string' } } } },
    readScope: { type: 'array', items: { type: 'string' } },
    assumptions: { type: 'array', items: { type: 'string' } },
  },
}

const ImpactSchema = {
  type: 'object', required: ['impactFiles', 'hiddenDependencies', 'deadCode'],
  properties: {
    impactFiles: { type: 'array', items: { type: 'object', required: ['file', 'kind', 'evidence'], properties: { file: { type: 'string' }, kind: { type: 'string', enum: ['direct', 'consumer', 'config', 'doc', 'latent'] }, evidence: { type: 'string' } } } },
    hiddenDependencies: { type: 'array', items: { type: 'string' } },
    deadCode: { type: 'array', items: { type: 'string' } },
  },
}

const EdgeSchema = {
  type: 'object', required: ['edgeCases'],
  properties: {
    edgeCases: { type: 'array', items: { type: 'object', required: ['id', 'case', 'failureScenario', 'affectedStep'], properties: { id: { type: 'string' }, case: { type: 'string' }, failureScenario: { type: 'string' }, affectedStep: { type: 'string' } } } },
  },
}

const ArchSchema = {
  type: 'object', required: ['patternVerdicts', 'violations'],
  properties: {
    patternVerdicts: { type: 'array', items: { type: 'object', required: ['topic', 'recommendation', 'rationale'], properties: { topic: { type: 'string' }, recommendation: { type: 'string' }, rationale: { type: 'string' } } } },
    violations: { type: 'array', items: { type: 'string' } },
  },
}

const CrossSchema = {
  type: 'object', required: ['links', 'additions'],
  properties: {
    links: { type: 'array', items: { type: 'object', required: ['sourceId', 'finding'], properties: { sourceId: { type: 'string' }, finding: { type: 'string' } } } },
    additions: { type: 'array', items: { type: 'string' } },
  },
}

const PlanSchema = {
  type: 'object',
  required: ['steps', 'readScope', 'writeScope', 'acceptanceCriteria', 'riskMatrix', 'rtm', 'openQuestions'],
  properties: {
    steps: { type: 'array', items: { type: 'object', required: ['id', 'title', 'files', 'verify'], properties: { id: { type: 'string' }, title: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, verify: { type: 'string' } } } },
    readScope: { type: 'array', items: { type: 'string' }, description: '§X — 영향 스캔 전체' },
    writeScope: { type: 'array', items: { type: 'object', required: ['file', 'rationale'], properties: { file: { type: 'string' }, rationale: { type: 'string' } } }, description: '§Y — 실제 변경 + 근거 (Read→Write 자동 번역 금지)' },
    acceptanceCriteria: { type: 'array', items: { type: 'string' }, description: '§Z — Step 완료 기준' },
    riskMatrix: { type: 'array', items: { type: 'object', required: ['risk', 'mitigation'], properties: { risk: { type: 'string' }, mitigation: { type: 'string' } } } },
    rtm: { type: 'array', items: { type: 'object', required: ['reqId', 'requirement', 'stepId', 'verify', 'status'], properties: { reqId: { type: 'string' }, requirement: { type: 'string' }, stepId: { type: 'string' }, verify: { type: 'string' }, status: { type: 'string', enum: ['pending'] } } } },
    antiPatternConstraints: { type: 'array', items: { type: 'object', required: ['pattern', 'grepPattern'], properties: { pattern: { type: 'string' }, grepPattern: { type: 'string' } } } },
    implicationRegister: { type: 'array', items: { type: 'object', required: ['id', 'type', 'trigger', 'locus', 'reason', 'policy', 'status'], properties: { id: { type: 'string' }, type: { type: 'string', enum: ['exec', 'obs'] }, trigger: { type: 'string' }, locus: { type: 'string' }, reason: { type: 'string' }, policy: { type: 'string' }, status: { type: 'string' } } }, description: 'plan-deep-planning 절차 7 — cross-phase artifact' },
    openQuestions: { type: 'array', items: { type: 'string' } },
  },
}

const RecheckSchema = {
  type: 'object', required: ['verdict', 'remainingIssues'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'issues'] },
    remainingIssues: { type: 'array', items: { type: 'object', required: ['issue', 'severity', 'archVerdict'], properties: { issue: { type: 'string' }, severity: { type: 'string', enum: ['critical', 'major', 'minor'] }, archVerdict: { type: 'string', enum: ['must-fix', 'optional', 'disagree'] } } } },
  },
}

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [요구사항]/[코드 컨텍스트]/[기지 제약]만이 과제의 전부다. ' +
  '무관한 작업 폴더(ASD-*, 토픽 폴더 등)를 읽지 말 것. 파일 접근은 명시된 경로와 그 안에 나열된 파일, 그리고 프롬프트가 허용한 모듈 문서만. ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력 데이터를 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. 출력은 schema 준수 JSON.'

// ── args 방어 파싱 + fail-fast (§12 표준 패턴 2 — 필수 키 2개: requirement + codeContextPath) ──
const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

let agentCalls = 0
let nullCalls = 0
let fallbackCount = 0
async function callAgent(prompt, opts) {
  agentCalls += 1
  const out = await agent(prompt, opts)
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) }
  return out
}
function metrics(stagesCompleted) {
  return { agentCalls, nullCount: nullCalls, fallbackCount, stagesCompleted }
}

if (!input || !input.requirement || !input.codeContextPath) {
  log(`FATAL args invalid (typeof=${typeof args}) — requirement/codeContextPath 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}

const CTX = `[요구사항] ${input.requirement}\n[코드 컨텍스트] 요약 파일: ${input.codeContextPath} (Read로 로드)\n[기지 제약] ${JSON.stringify(input.constraintsKnown || [])}` +
  (input.discoverJournalPath ? `\n[discover 산출물] ${input.discoverJournalPath} (참고 — 전제 아님, 🔒불변 조건만 제약 채택)` : '')

// ════════ Stage 0: Direction Challenge (collaborative L21-38 — PROCEED 경로는 dead-call 제거) ════════
phase('Stage 0: 방향성 도전')
let direction = await callAgent(
  `${OVERRIDE}\n[역할] 방향성 도전자(review-direction 렌즈) — 6관점: Structural Fit / Alternative Paths(2개+) / Extensibility / Reuse-First / Maintenance / Over-Engineering\n${CTX}\n` +
  `[목표] 접근 방향을 비판적으로 판정 (PROCEED/RECONSIDER/REDIRECT) + 대안 2개 이상 + 우려 사항. 근거 인용.`,
  { label: 'stage0-direction', agentType: 'fz:review-direction', model: 'opus', schema: DirectionSchema })
if (!direction) { fallbackCount += 1; return { mode: 'fallback', reason: 'direction null', metrics: metrics(0) } }

if (direction.verdict !== 'PROCEED') {
  // 반박 왕복 1회 — 비-PROCEED만 판정 반전 기회 실재
  log(`direction ${direction.verdict} — 반박 왕복 진입 (+2 call)`)
  const rebuttal = await callAgent(
    `${OVERRIDE}\n[역할] 설계자(plan-structure 렌즈) — 방향 반박\n${CTX}\n[방향 판정] ${JSON.stringify(direction)}\n` +
    `[목표] 현재 방향의 근거로 반박하거나, 대안 수용 사유를 명시. 추가 제약 발견 시 포함.`,
    { label: 'stage0-rebuttal', agentType: 'fz:plan-structure', model: 'opus', schema: RebuttalSchema })
  const finalDirection = rebuttal ? await callAgent(
    `${OVERRIDE}\n[역할] 방향성 도전자 — 최종 판정\n${CTX}\n[1차 판정] ${JSON.stringify(direction)}\n[설계자 반박] ${JSON.stringify(rebuttal)}\n` +
    `[목표] 반박을 평가해 최종 판정. 반박이 타당하면 PROCEED 전환 가능.`,
    { label: 'stage0-final', agentType: 'fz:review-direction', model: 'opus', schema: DirectionSchema }) : null
  if (finalDirection) direction = finalDirection
  if (direction.verdict !== 'PROCEED') {
    log(`direction 최종 ${direction.verdict} — 사용자 에스컬레이션 반환`)
    return { mode: 'direction_escalation', verdict: direction.verdict, alternatives: direction.alternatives, concerns: direction.concerns, rebuttal: rebuttal ? rebuttal.rebuttal : null, metrics: metrics(0) }
  }
}

// ════════ Stage 1: 구조 초안 (opus — direction 피드백 주입) ════════
phase('Stage 1: 구조 초안')
const draft = await callAgent(
  `${OVERRIDE}\n[역할] 설계자(plan-structure 렌즈) — 구조 분해 + Step 순서\n${CTX}\n[방향 판정·우려] ${JSON.stringify({ concerns: direction.concerns, alternatives: direction.alternatives })}\n` +
  `[목표] 구현 계획 초안: Step 분해(id/title/files/approach) + readScope(탐색 범위) + 가정 목록.`,
  { label: 'stage1-draft', agentType: 'fz:plan-structure', model: 'opus', schema: DraftSchema })
if (!draft) { fallbackCount += 1; return { mode: 'fallback', reason: 'draft null', metrics: metrics(1) } }

// ════════ Stage 2: 병렬 3렌즈 (sonnet — 동시 3 [verified: §5.7 #4 deep lens 3 동시]) ════════
phase('Stage 2: 영향/경계/아키 병렬 분석')
const DRAFT_CTX = `${CTX}\n[계획 초안] ${JSON.stringify(draft)}`
const [impact, edge, arch] = await parallel([
  () => callAgent(
    `${OVERRIDE}\n[역할] 영향 범위 분석가(plan-impact 렌즈) — Exhaustive Impact Scan a-f\n` +
    `(참조 허용: /Users/jaewoongyun/dev/fz-plugin/modules/plan-deep-planning.md — Scan 절차 정의)\n${DRAFT_CTX}\n` +
    `[목표] 텍스트 전수 검색 + 소비자 + dead code + 숨은 의존성. 각 항목 evidence 인용.`,
    { label: 'stage2-impact', agentType: 'fz:plan-impact', model: 'sonnet', schema: ImpactSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 경계 케이스 발굴자(plan-edge-case 렌즈)\n${DRAFT_CTX}\n` +
    `[목표] 경계 케이스 + 실패 시나리오 (id는 E1, E2...) + 영향 Step 매핑.`,
    { label: 'stage2-edge', agentType: 'fz:plan-edge-case', model: 'sonnet', schema: EdgeSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 아키텍처 검증자(review-arch 렌즈)\n${DRAFT_CTX}\n` +
    `[목표] 패턴 선택지 검증(A vs B + 추천 + 근거) + 기존 규약 위반 식별.`,
    { label: 'stage2-arch', agentType: 'fz:review-arch', model: 'sonnet', schema: ArchSchema }),
])
if (!impact && !edge && !arch) { fallbackCount += 1; return { mode: 'fallback', reason: 'stage2 all null', metrics: metrics(1) } }
if (!impact || !edge || !arch) log('WARN stage2 부분 null — 해당 렌즈 결손 상태로 진행')

// id 네임스페이스 강제 (W1 교정판 패턴)
if (edge) edge.edgeCases = edge.edgeCases.map(e => ({ ...e, id: `E:${e.id}` }))

// ════════ Stage 3: CC 교차 (collaborative L47-55 — edge↔impact 연쇄. edge는 impact 데이터 입력 기반, 독립 Serena 탐색 비기대) ════════
phase('Stage 3: CC 교차 (edge↔impact)')
let impactOnEdge = null
let edgeOnImpact = null
if (impact && edge) {
  const cc = await parallel([
    () => callAgent(
      `${OVERRIDE}\n[역할] 영향 범위 분석가 — CC 교차\n[경계 케이스] ${JSON.stringify(edge.edgeCases)}\n[기존 영향 범위] ${JSON.stringify(impact.impactFiles)}\n` +
      `[목표] 각 경계 케이스가 영향 범위 내 어느 파일에서 발생하는지 연쇄 발견 (links: sourceId=E:id) + 영향 범위 추가분.`,
      { label: 'stage3-impact-on-edge', agentType: 'fz:plan-impact', model: 'sonnet', schema: CrossSchema }),
    () => callAgent(
      `${OVERRIDE}\n[역할] 경계 케이스 발굴자 — CC 교차 (입력 기반 — 제공된 영향 범위 데이터에서만 추론)\n[영향 범위] ${JSON.stringify(impact.impactFiles)}\n[숨은 의존성] ${JSON.stringify(impact.hiddenDependencies)}\n[기존 케이스] ${JSON.stringify(edge.edgeCases)}\n` +
      `[목표] 영향 범위에서 파생되는 추가 경계 케이스 (additions — 기존 미포함만).`,
      { label: 'stage3-edge-on-impact', agentType: 'fz:plan-edge-case', model: 'sonnet', schema: CrossSchema }),
  ])
  impactOnEdge = cc[0]
  edgeOnImpact = cc[1]
  if (!impactOnEdge || !edgeOnImpact) log('WARN stage3 부분 null — CC 결손 상태로 통합')
}

// ════════ Stage 4: 통합 (opus — 다운스트림 계약 전체 생산) ════════
phase('Stage 4: 통합 (PlanSchema)')
const plan = await callAgent(
  `${OVERRIDE}\n[역할] 설계자(plan-structure 렌즈) — 최종 통합\n${CTX}\n` +
  `[초안] ${JSON.stringify(draft)}\n[영향] ${JSON.stringify(impact)}\n[경계] ${JSON.stringify(edge)}\n[아키] ${JSON.stringify(arch)}\n[CC 교차] ${JSON.stringify({ impactOnEdge, edgeOnImpact })}\n` +
  `[목표] 전 피드백 반영 최종 계획. 의무 사항:\n` +
  `1. §X readScope(영향 스캔 전체) / §Y writeScope(실제 변경 파일 + 각 근거 — readScope에서 자동 복사 금지, 변경 정당화 있는 파일만) / §Z acceptanceCriteria 3-섹션 분리\n` +
  `2. rtm: 요구사항을 분해해 각 행 {reqId, requirement 원문, stepId, verify, status:'pending'}\n` +
  `3. implicationRegister: 제거/리팩토링 함의 발견 시 {type: exec(계획 내 실행)|obs(관찰 보고)} — 없으면 빈 배열\n` +
  `4. 각 step에 검증 가능한 verify. 리스크 매트릭스 + openQuestions(사용자 결정 필요만).`,
  { label: 'stage4-integrate', agentType: 'fz:plan-structure', model: 'opus', schema: PlanSchema })
if (!plan) { fallbackCount += 1; return { mode: 'fallback', reason: 'integrate null', metrics: metrics(3) } }

// ════════ Stage 5: 재검증 (collaborative Round 2 — 잔여는 반환, 수정 루프는 Lead 층) ════════
phase('Stage 5: 아키 재검증')
const recheck = await callAgent(
  `${OVERRIDE}\n[역할] 아키텍처 검증자 — 재검증\n[1차 검증 결과] ${JSON.stringify(arch)}\n[최종 계획] ${JSON.stringify(plan)}\n` +
  `[목표] 1차 피드백 반영 여부 + 잔여 이슈. 각 잔여에 archVerdict(must-fix/optional/disagree) 마커 — 합의/불합의 명시.`,
  { label: 'stage5-recheck', agentType: 'fz:review-arch', model: 'sonnet', schema: RecheckSchema })
if (!recheck) log('WARN stage5 null — 재검증 미수행 (unresolvedPeerIssues 빈 채 반환)')

const s1 = !!draft
const s2 = !!(impact && edge && arch)
const s3 = !!(impactOnEdge && edgeOnImpact)
const s4 = !!plan
const s5 = !!recheck
const stagesCompleted = [s1, s2, s3, s4, s5].filter(Boolean).length
log(`완주 ${stagesCompleted}/5 stages — plan steps ${plan.steps.length} / writeScope ${plan.writeScope.length} / rtm ${plan.rtm.length}`)

return {
  mode: 'workflow',
  directionVerdict: direction.verdict,
  directionAlternatives: direction.alternatives,
  plan: { ...plan, unresolvedPeerIssues: recheck ? recheck.remainingIssues : [] },
  recheckVerdict: recheck ? recheck.verdict : 'skipped',
  metrics: metrics(stagesCompleted), // Lead가 experiment-log §5.7 fz-plan 테이블 기록 + stress-test/RTM 검증/plan-v{N}.md 기록 실수행 (회귀 확인 의무)
}
