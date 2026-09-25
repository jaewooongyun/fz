// workflows/plan-lean.js — fz-plan D1 구조: **3콜 · 2단계 직렬**.
//
// ⛔ 이 파일은 `plan-collaborative.js` 를 **대체하지 않는다** — 나란히 둔 대조군이다(롤백 경로 보존).
//    확산 판정 전까지 `skills/fz-plan/SKILL.md` 의 기본 배선은 collaborative 그대로다.
//
// [왜 이 구조인가 — 측정 근거]
//   S8-0 blind 채점(`wf_ac6e5638-9ff`, 2026-09-11): 9-agent(3,621s) vs 단일 1콜(805s).
//   · 요구 3축 **양쪽 closed** · 실행 가능 command verify **P4 / Q7**
//   · 9-agent 고유 8건(critical 0·major 5) — ⭐ **8/8 이 edgeCases 인용**.
//     impact 렌즈·arch 렌즈 **단독 기여 0건** · recheck(S5) 인용 **0건**.
//   · 단일 1콜 고유 6건 중 **critical 1 = "기전 신설 절차 전체"**.
//   → 두 팔의 강점이 서로 다른 곳에 있다. **고르지 않고 합집합을 만든다**:
//     call A(전체 플랜) ∥ call B(edge 적대) → call C(델타 병합).
//
// [가이드 근거]
//   · `guides/model-guide.md:187` Fable 5.1 공식 — *"don't force the lead agent to stop and wait for
//     each one … lowers average time to completion at similar quality"* → A·B 를 **동시**에 띄운다.
//   · `guides/harness-engineering.md` 원칙 3 — *"구조가 경로를 좁히는가"* + 역도(*"과하게 좁혀도 해롭다"*).
//     C 의 schema 를 **델타 전용**으로 좁혀 A 본문 재작성을 구조적으로 불가능하게 한다(R3 완화).
//   · `guides/harness-engineering.md` Anti-Pattern 1 — 기여 미관측 컴포넌트(impact·arch·recheck) 제거.
//
// [제거한 것과 그 대체]
//   impact 렌즈 · arch 렌즈 · CC 교차 · recheck · direction 독립 단계
//   → CC 는 call B 프롬프트의 "영향 범위 축을 스스로 훑어라"로, direction 은 call A 프롬프트로 접었다.
//   ⛔ 이 접기가 등가인지는 **미검증**이다(R1) — 확산 판정이 그것을 잰다.
//
// [예상] wall = max(A, B) + C ≈ max(805, 594) + 350 ≈ 1,155s. ⛔ C 는 [추정] — 첫 실행에서 실측한다.
// 동시 opus 2 (governance 상한 ≤3 이내).

export const meta = {
  name: 'plan-lean',
  description: 'fz-plan D1 — 전체 플랜 ∥ edge 적대 렌즈 → 델타 병합. 3콜 2단계',
  phases: [{ title: '생산+적대 (동시)' }, { title: '델타 병합' }],
}

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

// call A 는 9-agent 의 산출물 집합 전체를 혼자 낸다 — 적게 요구하면 빨라지는 게 당연해 비교가 무의미하다.
const FullSchema = {
  type: 'object',
  required: PlanSchema.required.concat(['directionVerdict', 'directionAlternatives']),
  properties: Object.assign({}, PlanSchema.properties, {
    directionVerdict: { type: 'string', enum: ['PROCEED', 'RECONSIDER', 'REDIRECT'] },
    directionAlternatives: { type: 'array', minItems: 2, items: { type: 'object', required: ['name', 'rationale'], properties: { name: { type: 'string' }, rationale: { type: 'string', description: '대안 근거 — 400자 이내' } } } },
  }),
}

// call B — 적대 렌즈. ⛔ 플랜을 쓰지 않는다(A 와 동시 실행이라 A 산출을 볼 수 없다).
//    같은 입력에서 **독립적으로** 경계를 판다 — Round 1 독립성 보존(prompt-optimization §다양성).
const EdgeSchema = {
  type: 'object', required: ['edgeCases', 'impactNotes'],
  properties: {
    edgeCases: { type: 'array', description: '경계 케이스 — ⛔ 항목 수 상한 없음. 서술만 짧게.', items: { type: 'object', required: ['id', 'case', 'failureScenario', 'whereItBreaks'], properties: { id: { type: 'string' }, case: { type: 'string' }, failureScenario: { type: 'string', description: '무엇이 언제 깨지는가 — 200자 이내' }, whereItBreaks: { type: 'string', description: '파일·심볼·줄 — 영향 범위 축을 스스로 훑어 특정한다. 200자 이내' } } } },
    impactNotes: { type: 'array', items: { type: 'string', description: '경계에서 파생된 영향 범위 관측 — 200자 이내' } },
    latentDefects: { type: 'array', items: { type: 'string', description: '이번 변경과 무관하나 기기 검증에서 오귀속될 선존 결함 — 200자 이내' } },
  },
}

// call C — ⛔ **델타 전용**. steps/readScope/rtm 을 통째로 다시 쓰지 못한다(R3 구조적 방어).
const MergeSchema = {
  type: 'object', required: ['addedEdgeCases', 'stepAmendments', 'implicationRegister', 'unresolved'],
  properties: {
    addedEdgeCases: { type: 'array', items: { type: 'object', required: ['id', 'case', 'affectedStep'], properties: { id: { type: 'string' }, case: { type: 'string', description: '300자 이내' }, affectedStep: { type: 'string', description: '기존 Step id — 새 Step 을 만들지 말 것' } } } },
    stepAmendments: { type: 'array', description: '기존 Step 의 **수정 지시**만. ⛔ 전체 재작성 금지.', items: { type: 'object', required: ['stepId', 'field', 'change', 'reason'], properties: { stepId: { type: 'string' }, field: { type: 'string', enum: ['title', 'files', 'verify', 'approach'] }, change: { type: 'string', description: '무엇을 어떻게 — 400자 이내' }, reason: { type: 'string', description: '어느 경계 케이스가 요구하는가 — 200자 이내' } } } },
    implicationRegister: { type: 'array', items: { type: 'object', required: ['id', 'type', 'trigger', 'locus', 'reason', 'policy', 'status'], properties: { id: { type: 'string' }, type: { type: 'string', enum: ['exec', 'obs'] }, trigger: { type: 'string' }, locus: { type: 'string' }, reason: { type: 'string' }, policy: { type: 'string' }, status: { type: 'string' } } } },
    unresolved: { type: 'array', items: { type: 'string', description: '플랜에 접을 수 없어 사용자 판단이 필요한 것' } },
  },
}

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·티켓 폴더(WORK_DIR)·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [요구사항]/[코드 컨텍스트]/[기지 제약]/[아키텍처 제약]만이 과제의 전부다. ' +
  '무관한 작업 폴더(티켓 폴더·토픽 폴더 등)를 읽지 말 것. 파일 접근은 명시된 경로와 그 안에 나열된 파일, 그리고 프롬프트가 허용한 모듈 문서만. ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력 데이터를 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. ' +
  '실행 제안 금지: git 상태변경(commit/push 등)·raw GPT CLI 호출은 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. ⛔ advisor 도 호출하지 않는다(스톨 시 런타임이 6회 반복해 시간을 태우고, 비용이 워크플로 계측 밖으로 샌다). 출력은 schema 준수 JSON.'

const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

let agentCalls = 0
let nullCalls = 0
async function callAgent(prompt, opts) {
  agentCalls += 1
  const out = await agent(prompt, opts)
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) }
  return out
}

if (!input || !input.requirement || !input.codeContextPath) {
  log(`FATAL args invalid (typeof=${typeof args}) — requirement/codeContextPath 필수`)
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: { agentCalls: 0, nullCount: 0, fallbackCount: 1, stagesCompleted: 0 } }
}

const AC = input.archConstraints || null
const ARCH_CTX = AC ? `\n[아키텍처 제약] ${JSON.stringify({
  architecturePattern: AC.architecturePattern, uiStack: AC.uiStack,
  dependencyDirection: AC.dependencyDirection, naming: AC.naming, conflicts: AC.conflicts,
})}` : ''
const CTX = `[요구사항] ${input.requirement}\n[코드 컨텍스트] 요약 파일: ${input.codeContextPath} (Read로 로드)\n[기지 제약] ${JSON.stringify(input.constraintsKnown || [])}` + ARCH_CTX +
  (input.intentContext ? `\n[과제 목적] ${input.intentContext}` : '') +
  (input.discoverJournalPath ? `\n[discover 산출물] ${input.discoverJournalPath} (참고 — 전제 아님, 🔒불변 조건만 제약 채택)` : '')

// ════════ Stage 1: 생산 ∥ 적대 (동시 — 배리어 1개) ════════
phase('생산+적대 (동시)')
const [full, edge] = await parallel([
  () => callAgent(
    `${OVERRIDE}\n[역할] 설계자 — 이 과제의 계획을 **혼자** 끝낸다. 방향 판정·영향 범위·아키텍처 정합을 스스로 수행하고 최종 계획까지 산출한다.\n${CTX}\n` +
    `[목표] 한 번에 전부:\n` +
    `1. directionVerdict(PROCEED/RECONSIDER/REDIRECT) + directionAlternatives 2개 이상 — 근거 인용. ⛔ 기각된 대안을 1안으로 되살리지 말 것.\n` +
    `2. §X readScope(영향 스캔 전체 — 텍스트 전수 검색 + 소비자 + 숨은 의존성) / §Y writeScope(실제 변경 + 각 근거 — readScope 자동 복사 금지) / §Z acceptanceCriteria 3-섹션 분리\n` +
    `3. steps: Step 분해(id/title/files/verify)\n` +
    `4. rtm: 요구사항 분해 각 행 {reqId, requirement 원문, stepId, verify, status:'pending'}\n` +
    `5. riskMatrix · antiPatternConstraints(기각 대안의 재도입을 막는 grep 포함) · openQuestions(사용자 결정 필요만)\n` +
    `6. 각 step 의 verify 는 판정 방식을 고른다 — {kind:'command', criterion, command, expect} 또는 {kind:'manual', criterion}.\n` +
    `   ⛔ command 는 제목이 말하는 것을 **실제로 측정**해야 한다. \`echo ok\` 류 금지. expect 는 모든 단언 통과 후에만 나오는 성공 토큰(\`&&\` 사용).\n` +
    `   ⛔ **현재 트리 상태에서 이미 통과하는 command 는 델타를 재지 못한다** — 변경 전에는 FAIL 하고 변경 후에만 PASS 해야 한다. 그럴 수 없으면 manual 이 정직하다.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 **유효한 JSON** — 문자열 값 안의 백슬래시·따옴표를 손으로 이스케이프하지 말 것.`,
    { label: 'lean-full', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: FullSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 경계 케이스 적대자 — 이 접근이 **어디서 깨지는가**만 판다. 계획을 쓰지 않는다.\n${CTX}\n` +
    `[목표] 경계 케이스와 실패 시나리오. ⛔ 일반론 금지 — 각 항목이 **어느 파일·심볼·줄에서** 깨지는지 코드로 특정한다.\n` +
    `필수 축: 좌표계·공간 정렬 · 상태 최신성(등록/해제 누락) · 회전·기기별 차이(iPad 포함) · 대상이 뷰 트리에서 빠진 뒤 · 가시성과 조작 가능성의 불일치 · 타이밍(터치다운 vs 이동 임계) · 기존 소비자와의 상호작용.\n` +
    `⛔ **영향 범위 축도 스스로 훑는다** — 경계를 판 자리의 소비자·형제 구현·숨은 의존성을 impactNotes 로 남긴다(별도 렌즈가 없다).\n` +
    `⛔ **선존 결함**을 만나면 latentDefects 로 분리한다 — 이번 변경의 회귀로 오귀속되면 기기 검증이 틀린 결론을 낸다.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 유효한 JSON — 이스케이프를 손으로 하지 말 것.`,
    { label: 'lean-edge', agentType: 'fz:plan-edge-case', model: 'opus', effort: 'xhigh', schema: EdgeSchema }),
])

if (!full) {
  return { mode: 'fallback', reason: 'full plan null', metrics: { agentCalls, nullCount: nullCalls, fallbackCount: 1, stagesCompleted: 0 } }
}
if (!edge) log('WARN edge null — 적대 렌즈 결손 상태로 병합 생략')

// ════════ Stage 2: 델타 병합 (edge 가 있을 때만) ════════
let merge = null
if (edge) {
  phase('델타 병합')
  const stepIds = (full.steps || []).map(s => s.id)
  merge = await callAgent(
    `${OVERRIDE}\n[역할] 통합자 — 적대 렌즈의 발견을 기존 계획에 **접는다**.\n${CTX}\n` +
    `[기존 계획 Step] ${JSON.stringify((full.steps || []).map(s => ({ id: s.id, title: s.title, files: s.files })))}\n` +
    `[기존 writeScope] ${JSON.stringify(full.writeScope || [])}\n` +
    `[적대 렌즈 발견] ${JSON.stringify(edge)}\n` +
    `[목표] ⛔ **계획을 다시 쓰지 않는다.** 기존 Step(${stepIds.join(', ')})에 대한 **델타만** 낸다:\n` +
    `1. addedEdgeCases — 계획이 놓친 경계를 기존 Step 에 귀속. ⛔ 새 Step 을 만들지 말 것.\n` +
    `2. stepAmendments — 기존 Step 의 title·files·verify·approach 중 **무엇을 어떻게** 고칠지. 각 항목에 어느 경계가 요구하는지 명시.\n` +
    `3. implicationRegister — 제거/리팩토링 함의 {type: exec|obs}. 없으면 빈 배열.\n` +
    `4. unresolved — 계획에 접을 수 없어 사용자 판단이 필요한 것.\n` +
    `⛔ 이미 계획에 있는 내용을 다시 적지 말 것 — 델타가 아니면 값이 0이다.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 유효한 JSON.`,
    { label: 'lean-merge', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: MergeSchema })
}

const stagesCompleted = (full ? 1 : 0) + (merge ? 1 : 0)
log(`lean 완주 ${stagesCompleted}/2 — steps ${(full.steps || []).length} · edge ${(edge && edge.edgeCases || []).length} · 델타 ${(merge && merge.stepAmendments || []).length} amendments / ${(merge && merge.addedEdgeCases || []).length} cases`)

return {
  mode: 'workflow',
  arm: 'lean-3call',
  directionVerdict: full.directionVerdict,
  directionAlternatives: full.directionAlternatives || [],
  plan: Object.assign({}, full, {
    implicationRegister: (merge && merge.implicationRegister) || full.implicationRegister || [],
  }),
  // ⛔ 델타를 plan 에 섞어 넣지 않는다 — Lead 가 적용 판정을 한다(병합 콜이 본문을 쓰지 못하게 한 것과 같은 이유).
  delta: merge ? { addedEdgeCases: merge.addedEdgeCases, stepAmendments: merge.stepAmendments, unresolved: merge.unresolved } : null,
  lensOutputs: { edge },
  metrics: { agentCalls, nullCount: nullCalls, fallbackCount: 0, stagesCompleted },
}
