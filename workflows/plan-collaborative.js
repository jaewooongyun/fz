// workflows/plan-collaborative.js — fz-plan 협업 설계 (TEAM collaborative 대체, Wave 2)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + Wave 0/1 실측]
//   표준 패턴 3종 적용. 대형 입력(코드 컨텍스트)은 파일 경로 전달 (§12).
//   호출(Lead, SKILL.md 절차): Lead가 codeContext 요약을 파일로 기록 후
//     Workflow({ scriptPath: '{plugin_root}/workflows/plan-collaborative.js',
//       args: { requirement, codeContextPath, constraintsKnown, archConstraints?, intentContext?, discoverJournalPath? } })
//   archConstraints = { architecturePattern, uiStack, dependencyDirection, naming, conflicts } — typed 아키텍처 객체.
//     축은 미확정 시 null. 소스 간 모순 축도 null + conflicts[]에 보존(자동 승자 선정 안 함 — 런타임 식별 불가).
//     CTX에 포함되어 Stage 0/1/2/4에 상속되고, CTX를 쓰지 않는 Stage 3·5에는 ARCH_CTX로 직접 전달된다.
//   effort 계약: 전 agent() 호출 model+effort(=xhigh) 명시. 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   반환: { mode:'workflow', plan: PlanSchema, directionVerdict, directionAlternatives, metrics }
//     | { mode:'direction_escalation', verdict, alternatives, rebuttal, metrics } → Lead가 사용자 확인 (대화는 Workflow 밖)
//     | { mode:'fallback', reason, metrics } → Lead는 실패 복구 사다리(guides/skill-authoring.md §12 L1~L4) — ⛔ 즉시 SOLO 아님, L4는 사용자 승인 후
//   Workflow 외부 Lead 책임 (이관 아님 — 회귀 확인 의무, 15차): stress-test Q1-Q6 / RTM 검증 /
//     Phase 0.7 Sprint Contract(GPT 회복 시) / GPT verify(Phase 2) / memory-curator recall /
//     plan-v{N}.md 파일 기록 / direction_escalation 사용자 대화 / wall-clock 측정.
//
// [설계 — modules/patterns/collaborative.md 평탄화]
//   Stage 0 direction(fable): 6관점 판정. PROCEED → 즉시 진행 / 비-PROCEED → 반박 왕복 1회 (+2 call).
//     조건부화 정당화: 원 패턴(L28-33)은 무조건 반박 왕복이나, PROCEED 경로의 반박은 판정 불변
//     dead-call이므로 제거 — 비-PROCEED만 판정 반전 기회 실재 (검증 승인 판정).
//   Stage 1 draft(opus) → Stage 2 병렬 3 [impact(Scan a-f)/edge/arch, opus — 동시 3
//     [verified: §5.7 #4 deep — lens 3 동시 parallel clean]] → Stage 3 CC 교차 2 (collaborative L47-55
//     보존: edge↔impact "경계 케이스가 영향 범위에서 발생" 연쇄) → Stage 4 integrate(opus, PlanSchema =
//     다운스트림 계약 전체) → Stage 5 arch 재검증 (collaborative Round 2 L57-63).
//   opus 동시 ≤3 (+Lead=fable): parallel 블록(Stage 2 3콜 / Stage 3 2콜) opus 동시 실행 — 동시 상한 준수.
//     Stage 2는 null 항목 1회 순차 재시도(parallelWithRetry — rate-limit/스폰 실패 폴백).
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

// ⛔ description 에 이스케이프 규약을 남긴다 — 실측(2026-09-11, d5d9cf9f S1): 20,117 bytes 출력이
//    `InputValidationError: could not be parsed as JSON` 으로 거부돼 **전량 재출력**했다(178s).
//    긴 출력일수록 위험이 커지므로 스키마와 프롬프트 **양쪽**에 둔다(한쪽만이면 그 한쪽이 잘릴 때 사라진다).
const DraftSchema = {
  type: 'object', required: ['steps', 'readScope', 'assumptions'],
  description: 'StructuredOutput 인자는 유효한 JSON 이어야 한다 — 문자열 안의 백슬래시·따옴표·개행을 직접 이스케이프하지 말고 값을 그대로 쓴다. 코드 조각은 백틱 없이 평문으로, 경로는 한 줄로.',
  properties: {
    steps: { type: 'array', items: { type: 'object', required: ['id', 'title', 'files', 'approach'], properties: { id: { type: 'string' }, title: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, approach: { type: 'string', description: '무엇을 어떻게 바꾸는가 — 300자 이내. 상류 입력(요구사항·코드 컨텍스트)을 재서술하지 말고 이 Step 고유의 판단만.' } } } },
    readScope: { type: 'array', items: { type: 'string' } },
    assumptions: { type: 'array', items: { type: 'string' } },
  },
}

const ImpactSchema = {
  type: 'object', required: ['impactFiles', 'hiddenDependencies', 'deadCode'],
  properties: {
    impactFiles: { type: 'array', items: { type: 'object', required: ['file', 'kind', 'evidence'], properties: { file: { type: 'string' }, kind: { type: 'string', enum: ['direct', 'consumer', 'config', 'doc', 'latent'] }, evidence: { type: 'string', description: '이 파일이 영향받는 근거 — 200자 이내. 심볼명·줄번호·grep 건수로 짧게. 파일 내용 인용 금지.' } } } },
    hiddenDependencies: { type: 'array', items: { type: 'string' } },
    deadCode: { type: 'array', items: { type: 'string' } },
    // ⛔ 렌즈는 Bash 가 없어 git 비교를 못 한다(`agents/plan-impact.md` — 1-shot, 중간 요청 채널 없음).
    //   필요를 반환 필드로 명시하면 Lead 가 resolve 한다. 슬롯이 없으면 그 지시가 갈 곳이 없다.
    originBodyRequests: { type: 'array', items: { type: 'string' }, description: '렌즈가 직접 못 얻은 base 원본·호출자 수 등의 요청. Lead 가 resolve' },
  },
}

const EdgeSchema = {
  type: 'object', required: ['edgeCases'],
  properties: {
    edgeCases: { type: 'array', description: '경계 케이스 배열 — ⛔ 항목 수 상한 없음(필수 케이스를 자르지 않는다). 서술만 짧게.', items: { type: 'object', required: ['id', 'case', 'failureScenario', 'affectedStep'], properties: { id: { type: 'string' }, case: { type: 'string' }, failureScenario: { type: 'string', description: '무엇이 언제 깨지는가 — 200자 이내. 재현 조건 + 관측 결과만.' }, affectedStep: { type: 'string' } } } },
  },
}

const ArchSchema = {
  type: 'object', required: ['patternVerdicts', 'violations'],
  properties: {
    patternVerdicts: { type: 'array', items: { type: 'object', required: ['topic', 'recommendation', 'rationale'], properties: { topic: { type: 'string' }, recommendation: { type: 'string' }, rationale: { type: 'string', description: '추천 근거 — 300자 이내. 프로젝트 규약 인용 1개 + 왜 대안보다 나은가.' } } } },
    violations: { type: 'array', items: { type: 'string' } },
  },
}

const CrossSchema = {
  type: 'object', required: ['links', 'additions'],
  properties: {
    links: { type: 'array', items: { type: 'object', required: ['sourceId', 'finding'], properties: { sourceId: { type: 'string' }, finding: { type: 'string', description: '연쇄 발견 — 200자 이내. 어느 파일에서 어떻게 발생하는가. 입력 재서술 금지.' } } } },
    additions: { type: 'array', items: { type: 'string' } },
  },
}

// VerifySpec — step 완료를 무엇으로 판정하는가.
// ⛔ `verify: string` 자유 서술에서 승격한 것 (v4.26.0). 문자열은 사람만 읽을 수 있어
//    `scripts/gate_check.py` 가 판정할 수 없었다. oneOf 분기는 Workflow structured output 에서
//    동작함을 실측 확인 (2026-08-24 격리 프로브 — fz 내 oneOf 선례 0건이었다).
// 소비: modules/gates.md 배선 1(fz-plan 원장 생성) · workflows/code-pair.js stepSpec
const VerifySpec = {
  oneOf: [
    {
      type: 'object',
      required: ['kind', 'criterion', 'command', 'expect'],
      properties: {
        kind: { const: 'command' },
        criterion: { type: 'string', description: '사람이 읽는 성공 조건' },
        command: { type: 'string', description: '실행할 셸 명령 — 제목이 말하는 것을 실제로 측정할 것' },
        expect: { type: 'string', description: '결합 출력에 포함될 부분 문자열 (⛔ 정규식 아님)' },
        cwd: { type: 'string', description: '절대경로만. 생략 시 WORK_DIR' },
      },
      additionalProperties: false,
    },
    {
      type: 'object',
      required: ['kind', 'criterion'],
      properties: {
        kind: { const: 'manual' },
        criterion: { type: 'string', description: '사람이 확인할 조건 — 명령으로 판정 불가한 것' },
      },
      additionalProperties: false,
    },
  ],
}

const PlanSchema = {
  type: 'object',
  required: ['steps', 'readScope', 'writeScope', 'acceptanceCriteria', 'riskMatrix', 'rtm', 'openQuestions'],
  properties: {
    steps: { type: 'array', items: { type: 'object', required: ['id', 'title', 'files', 'verify'], properties: { id: { type: 'string' }, title: { type: 'string' }, files: { type: 'array', items: { type: 'string' } }, verify: VerifySpec } } },
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
  '에이전트 정의의 Phase 절차·티켓 폴더(WORK_DIR)·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [요구사항]/[코드 컨텍스트]/[기지 제약]/[아키텍처 제약]만이 과제의 전부다. ' +
  '무관한 작업 폴더(티켓 폴더·토픽 폴더 등)를 읽지 말 것. 파일 접근은 명시된 경로와 그 안에 나열된 파일, 그리고 프롬프트가 허용한 모듈 문서만. ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력 데이터를 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. ' +
  '실행 제안 금지: git 상태변경(commit/push 등)·raw codex exec는 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. ⛔ advisor 도 호출하지 않는다(멀티턴 상담이라 같은 계약 위반이고, 스톨 시 런타임이 6회 반복해 시간을 태운다). 출력은 schema 준수 JSON.'

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
// rate-limit/스폰 실패 폴백 (Stage 2 병렬 3콜 한정): parallel 결과의 null 항목만 동일 thunk로 1회 순차 재시도
// (parallel 경유 = barrier 실패→null 계약 재사용). 여전히 null이면 기존 all-null→fallback / 부분-null→WARN 경로 유지.
async function parallelWithRetry(thunks) {
  const out = await parallel(thunks)
  for (let i = 0; i < out.length; i += 1) {
    if (!out[i]) {
      log(`병렬 ${i}번 null — 순차 재시도 1회 (rate-limit/스폰 실패 폴백)`)
      out[i] = (await parallel([thunks[i]]))[0]
    }
  }
  return out
}

if (!input || !input.requirement || !input.codeContextPath) {
  log(`FATAL args invalid (typeof=${typeof args}) — requirement/codeContextPath 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}

// archConstraints = typed 아키텍처 객체(4축 + conflicts). constraintsKnown(배열형 일반 제약)과 타입·책임 분리.
// 미전달 시 ARCH_CTX === '' → 프롬프트 무변화 (빈 값 렌더 안 함).
const AC = input.archConstraints || null
const ARCH_CTX = AC ? `\n[아키텍처 제약] ${JSON.stringify({
  architecturePattern: AC.architecturePattern, uiStack: AC.uiStack,
  dependencyDirection: AC.dependencyDirection, naming: AC.naming,
  conflicts: AC.conflicts,
})}` : ''

const CTX = `[요구사항] ${input.requirement}\n[코드 컨텍스트] 요약 파일: ${input.codeContextPath} (Read로 로드)\n[기지 제약] ${JSON.stringify(input.constraintsKnown || [])}` + ARCH_CTX +
  (input.intentContext ? `\n[과제 목적] ${input.intentContext}` : '') +
  (input.discoverJournalPath ? `\n[discover 산출물] ${input.discoverJournalPath} (참고 — 전제 아님, 🔒불변 조건만 제약 채택)` : '')

// ════════ Stage 0: Direction Challenge (collaborative L21-38 — PROCEED 경로는 dead-call 제거) ════════
phase('Stage 0: 방향성 도전')
let direction = await callAgent(
  `${OVERRIDE}\n[역할] 방향성 도전자(review-direction 렌즈) — 6관점: Structural Fit / Alternative Paths(2개+) / Extensibility / Reuse-First / Maintenance / Over-Engineering\n${CTX}\n` +
  `[목표] 접근 방향을 비판적으로 판정 (PROCEED/RECONSIDER/REDIRECT) + 대안 2개 이상 + 우려 사항. 근거 인용.`,
  { label: 'stage0-direction', agentType: 'fz:review-direction', model: 'fable', effort: 'xhigh', schema: DirectionSchema }) // §5.8 ⑤ 측정: 판단 지점 → fable, model explicit(생략 시 sonnet 강등)
if (!direction) { fallbackCount += 1; return { mode: 'fallback', reason: 'direction null', metrics: metrics(0) } }

if (direction.verdict !== 'PROCEED') {
  // 반박 왕복 1회 — 비-PROCEED만 판정 반전 기회 실재
  log(`direction ${direction.verdict} — 반박 왕복 진입 (+2 call)`)
  const rebuttal = await callAgent(
    `${OVERRIDE}\n[역할] 설계자(plan-structure 렌즈) — 방향 반박\n${CTX}\n[방향 판정] ${JSON.stringify(direction)}\n` +
    `[목표] 현재 방향의 근거로 반박하거나, 대안 수용 사유를 명시. 추가 제약 발견 시 포함.`,
    { label: 'stage0-rebuttal', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: RebuttalSchema })
  const finalDirection = rebuttal ? await callAgent(
    `${OVERRIDE}\n[역할] 방향성 도전자 — 최종 판정\n${CTX}\n[1차 판정] ${JSON.stringify(direction)}\n[설계자 반박] ${JSON.stringify(rebuttal)}\n` +
    `[목표] 반박을 평가해 최종 판정. 반박이 타당하면 PROCEED 전환 가능.`,
    { label: 'stage0-final', agentType: 'fz:review-direction', model: 'fable', effort: 'xhigh', schema: DirectionSchema }) : null // §5.8 ⑤ 측정: 판단 지점 → fable, model explicit(생략 시 sonnet 강등)
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
  `[목표] 구현 계획 초안: Step 분해(id/title/files/approach) + readScope(탐색 범위) + 가정 목록.\n` +
  `⛔ 출력 형식: StructuredOutput 인자는 **유효한 JSON** 이어야 한다 — 문자열 값 안의 백슬래시·따옴표를 손으로 이스케이프하지 말 것(실측: 20k 출력이 파싱 거부돼 전량 재출력됐다). 코드·명령은 백틱 없는 평문으로 쓴다.`,
  { label: 'stage1-draft', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: DraftSchema })
if (!draft) { fallbackCount += 1; return { mode: 'fallback', reason: 'draft null', metrics: metrics(1) } }

// ════════ Stage 2: 병렬 3렌즈 (opus — 동시 3 [verified: §5.7 #4 deep lens 3 동시]) ════════
phase('Stage 2: 영향/경계/아키 병렬 분석')
const DRAFT_CTX = `${CTX}\n[계획 초안] ${JSON.stringify(draft)}`
const [impact, edge, arch] = await parallelWithRetry([
  () => callAgent(
    `${OVERRIDE}\n[역할] 영향 범위 분석가(plan-impact 렌즈) — Exhaustive Impact Scan a-f\n` +
    `(참조 허용: {플러그인 루트}/modules/plan-deep-planning.md — Scan 절차 정의)\n${DRAFT_CTX}\n` +
    `[목표] 텍스트 전수 검색 + 소비자 + dead code + 숨은 의존성. 각 항목 evidence 인용.`,
    { label: 'stage2-impact', agentType: 'fz:plan-impact', model: 'opus', effort: 'xhigh', schema: ImpactSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 경계 케이스 발굴자(plan-edge-case 렌즈)\n${DRAFT_CTX}\n` +
    `[목표] 경계 케이스 + 실패 시나리오 (id는 E1, E2...) + 영향 Step 매핑.`,
    { label: 'stage2-edge', agentType: 'fz:plan-edge-case', model: 'opus', effort: 'xhigh', schema: EdgeSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 아키텍처 검증자(review-arch 렌즈)\n${DRAFT_CTX}\n` +
    `[목표] 패턴 선택지 검증(A vs B + 추천 + 근거) + 기존 규약 위반 식별.`,
    { label: 'stage2-arch', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: ArchSchema }),
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
      `${OVERRIDE}\n[역할] 영향 범위 분석가 — CC 교차\n[경계 케이스] ${JSON.stringify(edge.edgeCases)}\n[기존 영향 범위] ${JSON.stringify(impact.impactFiles)}${ARCH_CTX}\n` +
      `[목표] 각 경계 케이스가 영향 범위 내 어느 파일에서 발생하는지 연쇄 발견 (links: sourceId=E:id) + 영향 범위 추가분.`,
      { label: 'stage3-impact-on-edge', agentType: 'fz:plan-impact', model: 'opus', effort: 'xhigh', schema: CrossSchema }),
    () => callAgent(
      `${OVERRIDE}\n[역할] 경계 케이스 발굴자 — CC 교차 (입력 기반 — 제공된 영향 범위 데이터와 아키텍처 제약에서만 추론; 코드 컨텍스트 Read·독립 탐색 금지)\n[영향 범위] ${JSON.stringify(impact.impactFiles)}\n[숨은 의존성] ${JSON.stringify(impact.hiddenDependencies)}\n[기존 케이스] ${JSON.stringify(edge.edgeCases)}${ARCH_CTX}\n` +
      `[목표] 영향 범위에서 파생되는 추가 경계 케이스 (additions — 기존 미포함만).`,
      { label: 'stage3-edge-on-impact', agentType: 'fz:plan-edge-case', model: 'opus', effort: 'xhigh', schema: CrossSchema }),
  ])
  impactOnEdge = cc[0]
  edgeOnImpact = cc[1]
  if (!impactOnEdge || !edgeOnImpact) log('WARN stage3 부분 null — CC 결손 상태로 통합')
}

// ⛔ 상류 산출물을 S4 에 그대로 `JSON.stringify` 하면 입력이 11만 자까지 커진다(실측 d5d9cf9f).
//    입력이 크면 S4 가 그것을 **재서술**하며 출력도 함께 커진다(출력 토큰 = 시간).
//    그래서 **id 는 전건 보존**하고 서술만 줄인 brief 를 넘긴다 — 원문은 반환 `lensOutputs` 로
//    Lead 에게 가므로 유실이 아니다(S5a). ⛔ 생략이 생기면 텍스트에 건수를 남긴다(silent cap 금지).
function integrateBrief(impact, edge, arch, impactOnEdge, edgeOnImpact) {
  const LINE = 200          // 줄당 서술 상한
  const TOTAL = 40000       // 전체 상한 — 넘으면 뒤를 자르고 건수를 남긴다
  const cut = (v, n) => {
    const t = (v === undefined || v === null) ? '' : String(v).replace(/\s+/g, ' ').trim()
    return t.length > n ? `${t.slice(0, n)}…` : t
  }
  const lines = []
  let omitted = 0
  const push = (s) => { lines.push(s) }
  if (impact) {
    for (const f of impact.impactFiles || []) push(`  IMP ${f.file} [${f.kind}] ${cut(f.evidence, LINE)}`)
    for (const d of impact.hiddenDependencies || []) push(`  HID ${cut(d, LINE)}`)
    for (const d of impact.deadCode || []) push(`  DEAD ${cut(d, LINE)}`)
  }
  if (edge) for (const e of edge.edgeCases || []) push(`  EDGE ${e.id} ${cut(e.case, LINE)} → step ${cut(e.affectedStep, 40)} | ${cut(e.failureScenario, LINE)}`)
  if (arch) {
    for (const v of arch.patternVerdicts || []) push(`  ARCH ${cut(v.topic, 60)} ⇒ ${cut(v.recommendation, 80)} | ${cut(v.rationale, LINE)}`)
    for (const v of arch.violations || []) push(`  VIOL ${cut(v, LINE)}`)
  }
  for (const [tag, cc] of [['CC-IMP', impactOnEdge], ['CC-EDGE', edgeOnImpact]]) {
    if (!cc) continue
    for (const l of cc.links || []) push(`  ${tag} ${l.sourceId} → ${cut(l.finding, LINE)}`)
    for (const a of cc.additions || []) push(`  ${tag}+ ${cut(a, LINE)}`)
  }
  let text = lines.join('\n')
  if (text.length > TOTAL) {
    const kept = []
    let size = 0
    for (const l of lines) {
      if (size + l.length + 1 > TOTAL) { omitted += 1; continue }
      kept.push(l); size += l.length + 1
    }
    text = `${kept.join('\n')}\n  ⛔ 상한(${TOTAL}자) 초과로 ${omitted}줄 생략 — 원문은 Lead 의 lensOutputs 에 있다`
  }
  return { text, omitted, lineCount: lines.length }
}

// ════════ Stage 4: 통합 (opus — 다운스트림 계약 전체 생산) ════════
phase('Stage 4: 통합 (PlanSchema)')
const brief = integrateBrief(impact, edge, arch, impactOnEdge, edgeOnImpact)
log(`integrateBrief: ${brief.lineCount}줄 → ${brief.text.length}자${brief.omitted ? ` (⛔ ${brief.omitted}줄 생략)` : ''}`)
const plan = await callAgent(
  `${OVERRIDE}\n[역할] 설계자(plan-structure 렌즈) — 최종 통합\n${CTX}\n` +
  `[초안] ${JSON.stringify(draft)}\n[렌즈 산출 요약 — id 는 전건 보존, 서술만 축약]\n${brief.text}\n` +
  `[목표] 전 피드백 반영 최종 계획. 의무 사항:\n` +
  `1. §X readScope(영향 스캔 전체) / §Y writeScope(실제 변경 파일 + 각 근거 — readScope에서 자동 복사 금지, 변경 정당화 있는 파일만) / §Z acceptanceCriteria 3-섹션 분리\n` +
  `2. rtm: 요구사항을 분해해 각 행 {reqId, requirement 원문, stepId, verify, status:'pending'}\n` +
  `3. implicationRegister: 제거/리팩토링 함의 발견 시 {type: exec(계획 내 실행)|obs(관찰 보고)} — 없으면 빈 배열\n` +
  `4. 각 step의 verify는 **판정 방식을 고른다** — 명령으로 판정 가능하면 {kind:'command', criterion, command, expect}, 사람 확인만 가능하면 {kind:'manual', criterion}.\n` +
  `   ⛔ command 는 제목이 말하는 것을 **실제로 측정**해야 한다. \`echo ok\` 류의 무의미한 통과 명령 금지.\n` +
  `   ⛔ expect 는 **모든 단언이 통과한 뒤에만** 나오는 성공 토큰이어야 한다 (\`cmd; echo ok\` 는 cmd 실패해도 ok 가 찍힌다 — \`&&\` 를 쓸 것). 정규식 아닌 부분 문자열.\n` +
  `   ⛔ 판정 불가한 것을 억지로 command 로 만들지 말 것 — manual 이 정직하다.\n` +
  `5. 리스크 매트릭스 + openQuestions(사용자 결정 필요만).`,
  { label: 'stage4-integrate', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: PlanSchema })
if (!plan) { fallbackCount += 1; return { mode: 'fallback', reason: 'integrate null', metrics: metrics(3) } }

// ════════ Stage 5: 재검증 (collaborative Round 2 — 잔여는 반환, 수정 루프는 Lead 층) ════════
phase('Stage 5: 아키 재검증')
const recheck = await callAgent(
  `${OVERRIDE}\n[역할] 아키텍처 검증자 — 재검증\n[1차 검증 결과] ${JSON.stringify(arch)}\n[최종 계획] ${JSON.stringify(plan)}${ARCH_CTX}\n` +
  `[목표] 1차 피드백 반영 여부 + 잔여 이슈. [아키텍처 제약]이 있으면 그것이 프로젝트 준수 재검증의 직접 근거다. 각 잔여에 archVerdict(must-fix/optional/disagree) 마커 — 합의/불합의 명시.`,
  { label: 'stage5-recheck', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: RecheckSchema })
if (!recheck) log('WARN stage5 null — 재검증 미수행 (unresolvedPeerIssues 빈 채 반환)')

const s1 = !!draft
const impactRequests = (impact && impact.originBodyRequests) || []
if (impactRequests.length) log(`impact 렌즈 요청 ${impactRequests.length}건 — Lead resolve 대상`)
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
  impactRequests, // ⛔ impact 렌즈가 Bash 부재로 못 얻은 것 — Lead 가 resolve 후 plan 에 반영한다
  // ⛔ 렌즈 원문 — `scripts/plan_integrity_check.py` 가 rtm/CC 참조를 대조할 입력이다.
  //    이전 반환에는 plan 만 있어 `links.sourceId ∈ edgeCases.id` 를 **확인할 수단이 없었다**(GPT verify #7).
  //    S4 brief 가 서술을 줄이므로 원문 보존은 여기서 담당한다(유실 0).
  lensOutputs: { impact, edge, arch, impactOnEdge, edgeOnImpact, brief: { chars: brief.text.length, lines: brief.lineCount, omitted: brief.omitted } },
  metrics: metrics(stagesCompleted), // Lead가 experiment-log §5.7 fz-plan 테이블 기록 + stress-test/RTM 검증/plan-v{N}.md 기록 실수행 (회귀 확인 의무)
}
