// workflows/plan-lean2.js — fz-plan **D1b**: 4콜 · 2단계. D1 의 실측 손실을 출처별로 복원한다.
//
// ⛔ `plan-lean.js`(D1)를 **수정하지 않고** 별도 파일로 둔다 — D1 측정(2026-09-11, 2트리)의 재현성을 지킨다.
//    기본 배선은 여전히 `plan-collaborative.js` 다. 확산 판정 전까지 셋 다 공존한다.
//
// [D1 이 떨어진 이유 — 실측]
//   사전등록 임계 "검증된 critical·major 손실 0" 대비 **신규구현 major 5 · 감사형 major 3**.
//   wall 은 양 트리 충족(1,203s · 1,191s ≤ 1,400s). 판정: 신규구현 P-superior / 감사형 **equivalent**.
//   ⭐ 손실 출처 역추적(신규구현 5건): **impact 렌즈 2 · arch 렌즈 1 · integrate 3**.
//      감사형에서 "인용 0건"이라 D1 이 제거한 impact·arch 가 신규구현에서는 major 3건을 낸다
//      — N=1 제거 판단이 뒤집혔다.
//
// [D1b 가 바꾼 것]
//   ① **call C 신설** — impact + arch 를 **한 콜**에 합쳐 **3번째 병렬 팔**로 띄운다.
//      ⛔ 단계를 늘리는 게 아니라 **같은 단계에 팔을 하나 더** 붙인다. wall 은 max() 안에 들어가므로
//      예상 불변: max(701, 577, ~600) + 492 ≈ 1,200s. 병렬은 시간이 아니라 토큰을 쓴다.
//      동시 opus 3 = `guides/model-guide.md` §5 상한(≤3) 내.
//   ② **call A 프롬프트 보강** — integrate 출처 손실 2건을 겨냥:
//      · "수정 전 오라클 Step 을 첫 Step 으로" (변경 전 상태를 기록하지 않으면 '현행 유지' 요구를 비교할 대상이 없다)
//      · "회귀 축은 변경이 **공유하는 코드 경로 전부**를 훑는다" (같은 인식기·같은 정책을 쓰는 다른 기능)
//   ③ **병합 콜 확장** — edge 뿐 아니라 impact/arch 발견도 델타로 접는다.
//
// ⛔ 여전히 **델타 전용 schema** 다 — 병합 콜은 본문을 다시 쓸 수 없다(D1 의 R3 방어 유지).

export const meta = {
  name: 'plan-lean2',
  description: 'fz-plan D1b — 전체 플랜 ∥ edge 적대 ∥ impact+arch → 델타 병합. 4콜 2단계',
  phases: [{ title: '생산+적대+영향 (동시 3)' }, { title: '델타 병합' }],
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
        // ⛔ additionalProperties:false 라 여기 없는 필드는 **거부된다** — 원장 쪽에
        //    TOOLS: 를 읽는 코드가 있어도 생산 경로가 막혀 영원히 비어 온다.
        tools: { type: 'array', items: { type: 'string' },
                 description: 'command 가 필요로 하는 외부 명령 (예: ["xcodebuild"]). 부재 시 게이트를 돌리지 않고 미판정으로 남긴다 — 셸 exit 127 을 일반 실패로 오귀속하지 않기 위함' },
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

// call C — impact + arch 를 한 콜에. ⛔ D1 이 제거했다가 신규구현에서 major 3건을 잃은 자리다.
const ImpactArchSchema = {
  type: 'object', required: ['impactFiles', 'patternVerdicts'],
  properties: {
    impactFiles: { type: 'array', description: '영향 파일 — 텍스트 전수 검색 + 소비자 + 숨은 의존성. 항목 수 상한 없음.', items: { type: 'object', required: ['file', 'kind', 'evidence'], properties: { file: { type: 'string' }, kind: { type: 'string', enum: ['direct', 'consumer', 'config', 'doc', 'latent'] }, evidence: { type: 'string', description: '근거 — 심볼·줄번호·grep 건수. 200자 이내' } } } },
    hiddenDependencies: { type: 'array', items: { type: 'string', description: '200자 이내' } },
    secondaryHosts: { type: 'array', description: '⛔ 같은 타입·뷰를 쓰는 **두 번째 소비자**(다른 화면·다른 진입점). D1 이 이걸 놓쳐 major 를 잃었다.', items: { type: 'string', description: '파일:심볼 + 왜 영향받는가 — 200자 이내' } },
    existingTestSuites: { type: 'array', description: '⛔ 이 변경이 깨뜨릴 수 있는 **기존 자동 테스트** — 회귀 축의 유일한 비수동 oracle 이다.', items: { type: 'string', description: '파일 + 무엇을 지키는가 — 200자 이내' } },
    patternVerdicts: { type: 'array', description: '패턴 선택지 검증 — A vs B + 추천 + 근거. ⛔ **미검증 전제를 설계로 제거할 수 있는지**를 우선 본다(측정으로 미루지 말고).', items: { type: 'object', required: ['topic', 'recommendation', 'rationale'], properties: { topic: { type: 'string' }, recommendation: { type: 'string' }, rationale: { type: 'string', description: '규약 인용 + 대안 대비 우위 — 300자 이내' } } } },
    deadCode: { type: 'array', description: '⛔ 이 변경으로 **도달 불가**가 되는 코드 — 제거 대상 후보. 빈 배열 허용.', items: { type: 'string', description: '파일:심볼 + 왜 도달 불가인가 — 200자 이내' } },
    originBodyRequests: { type: 'array', description: '⛔ 이 렌즈가 **직접 못 얻은 것**(Bash 부재 — base 원본 본문·이전 호출자 수 등). Lead 가 resolve 한다. 추측으로 채우지 말고 요청으로 남긴다.', items: { type: 'string', description: '무엇을 알아야 하는가 — 200자 이내' } },
    violations: { type: 'array', items: { type: 'string', description: '기존 규약 위반 — 200자 이내' } },
  },
}

// call D — ⛔ **델타 전용**. steps/readScope/rtm 을 통째로 다시 쓰지 못한다.
const MergeSchema = {
  type: 'object', required: ['addedEdgeCases', 'stepAmendments', 'implicationRegister', 'unresolved'],
  properties: {
    addedEdgeCases: { type: 'array', items: { type: 'object', required: ['id', 'case', 'affectedStep'], properties: { id: { type: 'string' }, case: { type: 'string', description: '300자 이내' }, affectedStep: { type: 'string', description: '기존 Step id — 새 Step 을 만들지 말 것' } } } },
    addedImpact: { type: 'array', description: '계획의 readScope·writeScope 에 빠진 영향 대상', items: { type: 'object', required: ['file', 'why'], properties: { file: { type: 'string' }, why: { type: 'string', description: '200자 이내' } } } },
    stepAmendments: { type: 'array', description: '기존 Step 의 **수정 지시**만. ⛔ 전체 재작성 금지.', items: { type: 'object', required: ['stepId', 'field', 'change', 'reason'], properties: { stepId: { type: 'string' }, field: { type: 'string', enum: ['title', 'files', 'verify', 'approach'] }, change: { type: 'string', description: '400자 이내' }, reason: { type: 'string', description: '어느 발견이 요구하는가 — 200자 이내' } } } },
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

// ════════ Stage 1: 생산 ∥ 적대 ∥ 영향 (동시 3 — 배리어 1개) ════════
phase('생산+적대+영향 (동시 3)')
const [full, edge, impactArch] = await parallel([
  () => callAgent(
    `${OVERRIDE}\n[역할] 설계자 — 이 과제의 계획을 **혼자** 끝낸다. 방향 판정·영향 범위·아키텍처 정합을 스스로 수행하고 최종 계획까지 산출한다.\n${CTX}\n` +
    `[목표] 한 번에 전부:\n` +
    `1. directionVerdict(PROCEED/RECONSIDER/REDIRECT) + directionAlternatives 2개 이상 — 근거 인용. ⛔ 기각된 대안을 1안으로 되살리지 말 것.\n` +
    `2. §X readScope(영향 스캔 전체) / §Y writeScope(실제 변경 + 각 근거 — readScope 자동 복사 금지) / §Z acceptanceCriteria 3-섹션 분리\n` +
    `3. steps: Step 분해(id/title/files/verify).\n` +
    `   ⛔ **첫 Step 은 "수정 전 오라클"** 이다 — 변경 전 상태(재현 여부·현재 동작·기준 수치)를 기록한다. 그것이 없으면 "현행 유지" 요구를 무엇과 비교할지 없다.\n` +
    `4. rtm: 요구사항 분해 각 행 {reqId, requirement 원문, stepId, verify, status:'pending'}\n` +
    `5. riskMatrix · antiPatternConstraints(기각 대안 재도입 차단 grep) · openQuestions(사용자 결정 필요만)\n` +
    `6. 각 step 의 verify — {kind:'command', criterion, command, expect} 또는 {kind:'manual', criterion}.\n` +
    `   ⛔ command 는 제목이 말하는 것을 **실제로 측정**해야 한다. expect 는 모든 단언 통과 후에만 나오는 성공 토큰(\`&&\`).\n` +
    `   ⛔ **현재 트리에서 이미 통과하는 command 는 델타를 재지 못한다** — 변경 전 FAIL·변경 후 PASS 여야 한다. 불가하면 manual 이 정직하다.\n` +
    `   ⛔ 경로를 하드코딩하지 말 것 — 구현 트리 루트를 파라미터로 받아 쓴다(다른 트리에서 실행 불가가 되면 게이트가 죽는다).\n` +
    `7. ⛔ **회귀 축(기존 동작 보존)은 변경이 공유하는 코드 경로를 전부 훑는다** — 같은 인식기·같은 정책·같은 진입점을 쓰는 **다른 기능**이 무엇인지 찾아 검증 셀에 넣는다. 요구에 적힌 것만 보지 말 것.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 **유효한 JSON** — 문자열 값 안의 백슬래시·따옴표를 손으로 이스케이프하지 말 것.`,
    { label: 'lean2-full', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: FullSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 경계 케이스 적대자 — 이 접근이 **어디서 깨지는가**만 판다. 계획을 쓰지 않는다.\n${CTX}\n` +
    `[목표] 경계 케이스와 실패 시나리오. ⛔ 일반론 금지 — 각 항목이 **어느 파일·심볼·줄에서** 깨지는지 코드로 특정한다.\n` +
    `필수 축: 좌표계·공간 정렬 · 상태 최신성(등록/해제 누락) · 회전·기기별 차이 · 대상이 트리에서 빠진 뒤 · 가시성과 조작 가능성의 불일치 · 타이밍(시작 임계) · 애니메이션 진행 중의 중간 상태 · 기존 소비자와의 상호작용.\n` +
    `⛔ **선존 결함**을 만나면 latentDefects 로 분리한다 — 이번 변경의 회귀로 오귀속되면 검증이 틀린 결론을 낸다.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 유효한 JSON.`,
    { label: 'lean2-edge', agentType: 'fz:plan-edge-case', model: 'opus', effort: 'xhigh', schema: EdgeSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 영향 범위 + 아키텍처 검증자 — **이 변경이 어디까지 퍼지는가**와 **기존 패턴과 맞는가**를 함께 본다. 계획을 쓰지 않는다.\n${CTX}\n` +
    `[목표]\n` +
    `1. impactFiles — 텍스트 전수 검색(Grep) + 심볼 참조 + 소비자 체인. 각 항목 evidence 인용.\n` +
    `2. ⛔ **secondaryHosts** — 변경 대상 타입·뷰를 쓰는 **두 번째 소비자**를 찾는다. 다른 화면·다른 진입점·다른 컨테이너가 같은 것을 쓰고 있는지 전수로 본다. 이것을 놓치면 한 화면만 고치고 끝난다.\n` +
    `3. ⛔ **existingTestSuites** — 이 변경이 깨뜨릴 수 있는 기존 자동 테스트. 회귀 축의 유일한 비수동 oracle 이다.\n` +
    `4. patternVerdicts — 패턴 선택지(A vs B) + 추천 + 근거. ⛔ **미검증 전제가 있으면 "측정 후 판단" 으로 미루지 말고, 그 전제를 설계로 제거할 수 있는지 먼저 본다**(예: 두 좌표계를 비교하는 대신 같은 기준으로 환산). 제거 가능하면 그 방법을 recommendation 으로.\n` +
    `5. hiddenDependencies — 호출 그래프에 안 보이는 의존(문자열 키·리플렉션·설정값·빌드 조건).\n` +
    `6. deadCode — 이 변경으로 도달 불가가 되는 코드. 없으면 빈 배열.\n` +
    `7. ⛔ **originBodyRequests** — 네가 직접 못 얻은 것을 여기에 적는다. 너는 Bash 가 없어 base 원본 본문·이전 호출자 수를 못 본다. **추측으로 채우지 말고 요청으로 남긴다** — Lead 가 resolve 한다.\n` +
    `8. violations — 기존 규약 위반.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 유효한 JSON.`,
    { label: 'lean2-impact-arch', agentType: 'fz:plan-impact', model: 'opus', effort: 'xhigh', schema: ImpactArchSchema }),
])

if (!full) {
  return { mode: 'fallback', reason: 'full plan null', metrics: { agentCalls, nullCount: nullCalls, fallbackCount: 1, stagesCompleted: 0 } }
}
if (!edge) log('WARN edge null')
if (!impactArch) log('WARN impact-arch null')

// ════════ Stage 2: 델타 병합 ════════
let merge = null
if (edge || impactArch) {
  phase('델타 병합')
  const stepIds = (full.steps || []).map(s => s.id)
  merge = await callAgent(
    `${OVERRIDE}\n[역할] 통합자 — 적대 렌즈와 영향·아키 렌즈의 발견을 기존 계획에 **접는다**.\n${CTX}\n` +
    `[기존 계획 Step] ${JSON.stringify((full.steps || []).map(s => ({ id: s.id, title: s.title, files: s.files })))}\n` +
    `[기존 readScope] ${JSON.stringify(full.readScope || [])}\n[기존 writeScope] ${JSON.stringify(full.writeScope || [])}\n` +
    `[적대 렌즈] ${JSON.stringify(edge)}\n[영향·아키 렌즈] ${JSON.stringify(impactArch)}\n` +
    `[목표] ⛔ **계획을 다시 쓰지 않는다.** 기존 Step(${stepIds.join(', ')})에 대한 **델타만**:\n` +
    `1. addedEdgeCases — 계획이 놓친 경계를 기존 Step 에 귀속. ⛔ 새 Step 금지.\n` +
    `2. addedImpact — 계획의 readScope·writeScope 에 빠진 영향 대상(특히 secondaryHosts·existingTestSuites).\n` +
    `3. stepAmendments — 기존 Step 의 title·files·verify·approach 중 **무엇을 어떻게**. 각 항목에 어느 발견이 요구하는지 명시. ⛔ patternVerdicts 가 미검증 전제를 설계로 제거하는 방법을 냈으면 그것을 해당 Step 의 amendment 로 반영한다.\n` +
    `4. implicationRegister — 제거/리팩토링 함의 {type: exec|obs}. 없으면 빈 배열.\n` +
    `5. unresolved — 접을 수 없어 사용자 판단이 필요한 것.\n` +
    `⛔ 이미 계획에 있는 내용을 다시 적지 말 것 — 델타가 아니면 값이 0이다.\n` +
    `⛔ 출력 형식: StructuredOutput 인자는 유효한 JSON.`,
    { label: 'lean2-merge', agentType: 'fz:plan-structure', model: 'opus', effort: 'xhigh', schema: MergeSchema })
}

const stagesCompleted = (full ? 1 : 0) + (merge ? 1 : 0)
log(`lean2 완주 ${stagesCompleted}/2 — steps ${(full.steps || []).length} · edge ${(edge && edge.edgeCases || []).length} · impact ${(impactArch && impactArch.impactFiles || []).length} · 2차호스트 ${(impactArch && impactArch.secondaryHosts || []).length} · arch ${(impactArch && impactArch.patternVerdicts || []).length} · 델타 ${(merge && merge.stepAmendments || []).length} amendments`)

return {
  mode: 'workflow',
  arm: 'lean2-4call',
  directionVerdict: full.directionVerdict,
  directionAlternatives: full.directionAlternatives || [],
  plan: Object.assign({}, full, {
    implicationRegister: (merge && merge.implicationRegister) || full.implicationRegister || [],
  }),
  delta: merge ? { addedEdgeCases: merge.addedEdgeCases, addedImpact: merge.addedImpact, stepAmendments: merge.stepAmendments, unresolved: merge.unresolved } : null,
  // ⛔ 계약 복구 (F-215): collaborative 가 반환하던 것을 lean2 가 빠뜨려 소비처가 영구 no-op 이었다.
  //    impactRequests → scripts/plan_resolve_impact_requests.py · fz-plan SKILL.md 절차 4 가 소비한다.
  impactRequests: (impactArch && impactArch.originBodyRequests) || [],
  //    directionEscalation → SKILL.md 의 RECONSIDER/REDIRECT 분기 신호. ⛔ 반환 모드를 바꾸지 않고 필드로 싣는다.
  directionEscalation: (full.directionVerdict === 'RECONSIDER' || full.directionVerdict === 'REDIRECT')
    ? { verdict: full.directionVerdict, alternatives: full.directionAlternatives || [] }
    : null,
  lensOutputs: { edge, impactArch },
  metrics: { agentCalls, nullCount: nullCalls, fallbackCount: 0, stagesCompleted },
}
