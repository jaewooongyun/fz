// workflows/code-pair.js — fz-code/fz-fix 구현 페어 (TEAM pair-programming 대체, Wave 3)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + Wave 0-2 실측]
//   표준 패턴 3종 적용. Step당 1회 invoke — 빌드 oracle은 Lead 전용이므로 분할 invoke 구조.
//   호출(Lead, SKILL.md 절차 — Step 루프는 Lead 소유):
//     Workflow({ scriptPath: '{plugin_root}/workflows/code-pair.js',
//   ⛔ verify 는 VerifySpec 객체다 ({kind:'command'|'manual', …} — plan-collaborative.js 정의).
//      본 스크립트는 stepSpec 을 **해석하지 않고** 프롬프트에 통째 전달하므로 형태 변경에 무관하다.
//       args: { mode: 'full'|'light', stepSpec: {id,title,goal,files,verify:VerifySpec, complexity, estimatedNewBodyLines?}, contextPath, buildFeedback?, changesetTarget } })
//       estimatedNewBodyLines?: Lead 추정 총 newBody 줄수 — SPLIT_THRESHOLD(600) 초과 시 pre-flight가 스폰 전 split_required 반환(H5). 미제공 시 가드 skip(하위호환).
//   effort 계약: 전 agent() 호출 model+effort(=xhigh) 명시. 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   반환: { mode:'workflow', changeset, reviewVerdict, residualIssues, metrics }
//     | { mode:'fallback', reason, splitSuggested?, metrics } → Lead는 실패 복구 사다리(guides/skill-authoring.md §12 L1~L4) — ⛔ 즉시 SOLO 아님, L4는 사용자 승인 후
//     | { mode:'split_required', reason, metrics } → Lead는 Step 분할 후 재invoke.
//   ⛔ 책임 재배분 (S0, 사용자 승인 OQ1): 에이전트는 디스크를 수정하지 않는다 — changeset JSON만 반환.
//     Lead가 적용(replace_symbol_body/Edit) + 빌드 검증 + 다음 Step invoke. 부분 적용 후 빌드 실패 시
//     되돌리기/계속은 Lead 절차 (SKILL.md). 재시도 = buildFeedback 포함 새 invoke (resume 비의존 —
//     buildFeedback이 args를 바꿔 캐시 키 불일치 [선례: ts 제거 — resume 캐시 미스 유발]).
//
// [설계 — modules/patterns/pair-programming.md 평탄화]
//   full(fz-code): Stage1 impl(opus) changeset → Stage2 **병렬 2렌즈**(review-arch + impl-quality, opus) →
//     Stage3 impl(opus) 이슈 반영 수정 — **조건부**: review pass면 Stage3 생략 (3-call).
//     계획 표기 '고정 3-call'은 unresolved #2가 잠정 부정확 지적 — pass 경로 dead-call 제거가 정직
//     (plan-collaborative direction 조건부화 동형). 분기 상한 고정(3-4 call) → 가변 fan-out 아님.
//   light(fz-fix): Stage1 impl(opus) → Stage2 review-arch 단독은 stepSpec.complexity>=3만 (1-2 call).
//     complexity 누락 시 review 포함 (안전 default) + log 명시. ⛔ light에 impl-quality 미추가 (비용 유지).
//   opus 동시 ≤2 (+Lead=3): Stage2 full만 parallel — Stage1↔2↔3은 의존 사슬이라 순차.
//   budget 가드: 해당 없음 — 분기 상한 고정 1-4 call (§12 단서).
//   ⚠️ **impl-quality 배선 복구 (2026-08-10)**: agent-team-guide §팀 구성이 code-* 실질 워커를
//     review-arch·impl-quality·review-correctness로 정의하나 Wave 3 전환 시 arch만 배선됐다
//     (구 주석 "S4 결정 — 미포함 기본값", 근거 문서 미추적). 대조군 plan-collaborative는 정의된 5개 전수 스폰.
//     impl-quality의 "Codebase Pattern Consistency" 부재로 형제 슬롯 비대칭이 무방비였다
//     [verified: OBS-24 R8 — promotion-ledger L-13]. review-correctness/memory-curator는 여전히 Lead 경로.

export const meta = {
  name: 'code-pair',
  description: 'fz-code/fz-fix 구현 페어 — impl changeset(JSON, 디스크 미수정) → 조건부 검토(full: arch+quality 병렬) → 수정. Step당 1 invoke, Lead가 적용+빌드. 1-4 call',
}

const ChangesetSchema = {
  type: 'object', required: ['files', 'summary', 'buildExpectation'],
  properties: {
    files: {
      type: 'array', minItems: 1,
      items: {
        type: 'object', required: ['path', 'changeKind', 'symbolEdits', 'rationale'],
        properties: {
          path: { type: 'string' },
          changeKind: { type: 'string', enum: ['modify', 'create', 'delete'] },
          symbolEdits: {
            type: 'array',
            items: {
              type: 'object', required: ['symbol', 'intent', 'newBody'],
              properties: {
                symbol: { type: 'string', description: '심볼명 또는 앵커(교체 대상 식별자). create면 "FILE"' },
                intent: { type: 'string' },
                newBody: { type: 'string', description: 'Lead가 replace_symbol_body/Edit에 직접 전달 가능한 exact syntax — 의사코드/skeleton/생략(...) 금지' },
                oldAnchor: { type: 'string', description: 'modify 시 교체 시작 지점 식별 텍스트 (Edit old_string용)' },
              },
            },
          },
          rationale: { type: 'string' },
        },
      },
    },
    summary: { type: 'string' },
    buildExpectation: { type: 'string', description: 'Lead 빌드 검증 시 기대 결과 (검증 가능 형태)' },
  },
}

const ReviewSchema = {
  type: 'object', required: ['verdict', 'issues'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'issues'] },
    issues: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'severity', 'detail'],
        properties: {
          id: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
          detail: { type: 'string', description: '실측 인용 — 아키 위반/패턴 불일치/changeset 결함' },
        },
      },
    },
  },
}

const SPLIT_THRESHOLD = 600 // 총 newBody 줄수 — C1 실측(≤500 안전)+H5 실사고(~800 실패) 사이 보수값. split_required=Lead 판단 요구(하드 차단 아님). 관측 실패에서 재조정.

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [Step 명세]/[컨텍스트]만이 과제의 전부다. ' +
  '⛔ 디스크 수정 금지: Edit/Write/replace_symbol 등 어떤 파일 변경 도구도 사용하지 않는다 — changeset JSON 반환만. ' +
  '무관한 작업 폴더(ASD-*, 토픽 폴더 등)를 읽지 말 것. 파일 Read는 [Step 명세] files와 [컨텍스트] 경로만. ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력 데이터를 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. 실행 제안 금지: git 상태변경(commit/push 등)·raw codex exec는 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. 출력은 schema 준수 JSON.'

// ── args 방어 파싱 + fail-fast (§12 — 필수: mode/stepSpec/contextPath/changesetTarget) ──
const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

let agentCalls = 0
let nullCalls = 0
let fallbackCount = 0
let splitCount = 0 // H5 pre-flight split_required 발동 수 — 임계 재조정 관측용(§12 observation 축)
async function callAgent(prompt, opts) {
  agentCalls += 1
  const out = await agent(prompt, opts)
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) }
  return out
}
function metrics(stagesCompleted) {
  return { agentCalls, nullCount: nullCalls, fallbackCount, splitCount, stagesCompleted }
}

if (!input || !input.mode || !input.stepSpec || !input.contextPath || !input.changesetTarget) {
  log(`FATAL args invalid (typeof=${typeof args}) — mode/stepSpec/contextPath/changesetTarget 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}
// buildFeedback type guard: 빈 문자열('')은 "피드백 없음"이 아닌 유효 입력과 구분 (E:E15 계열)
const buildFeedback = (typeof input.buildFeedback === 'string' && input.buildFeedback.length > 0) ? input.buildFeedback : null

const STEP = `[Step 명세] ${JSON.stringify(input.stepSpec)}\n[컨텍스트] 요약 파일: ${input.contextPath} (Read로 로드)\n[변경 대상 레포] ${input.changesetTarget}` +
  (buildFeedback ? `\n[이전 적용 빌드 피드백] ${buildFeedback}` : '')

// ── H5 pre-flight 크기 가드 (스폰 전): Lead 제공 estimatedNewBodyLines가 임계 초과면 즉시 반환 ──
// estimatedNewBodyLines 미제공(null)이면 스킵 — 전량 진행(하위호환). split_required는 Lead 판단 요구(하드 차단 아님).
const est = (typeof input.stepSpec.estimatedNewBodyLines === 'number') ? input.stepSpec.estimatedNewBodyLines : null
if (est !== null && est > SPLIT_THRESHOLD) {
  splitCount += 1
  log(`split_required — 예상 ${est}줄 > 임계 ${SPLIT_THRESHOLD} (스폰 전 차단)`)
  return { mode: 'split_required', reason: `예상 changeset ~${est}줄 > 임계 ${SPLIT_THRESHOLD} — Step 분할 후 재invoke 권고 (scaffold collapse 방지)`, metrics: metrics(0) }
}

// ════════ Stage 1: 구현 changeset (opus) ════════
phase('Stage 1: 구현 changeset')
const changeset = await callAgent(
  `${OVERRIDE}\n[역할] 구현자(impl-correctness 렌즈)\n${STEP}\n` +
  `[목표] Step 목표를 달성하는 changeset 생산. 각 symbolEdit의 newBody는 Lead가 그대로 적용 가능한 exact syntax ` +
  `(의사코드·생략 금지). 대상 파일을 Read해 현재 상태 기준으로 작성. buildExpectation은 검증 가능 형태로.` +
  (buildFeedback ? ' 이전 빌드 피드백의 오류를 우선 해소.' : ''),
  { label: 'stage1-impl', agentType: 'fz:impl-correctness', model: 'opus', effort: 'xhigh', schema: ChangesetSchema })
if (!changeset) {
  fallbackCount += 1
  // 크기 프록시(files>=4 OR complexity===5)면 split 힌트. ⚠️ null=무조건 split 아님 —
  // B1 프로브 null은 세션한도(일시 장애)였음. Lead가 일시 장애 vs 과대 changeset 구분 (SKILL 사다리).
  // ⚠️ est는 프록시에서 제외: est>임계면 pre-flight가 이미 조기 반환하므로 여기 도달한 est는 항상 ≤임계(작은 Step) —
  //   est 존재만으로 split 제안하면 작은 Step의 일시 장애를 오분류(Codex C3 지적).
  const splitSuggested = (Array.isArray(input.stepSpec.files) && input.stepSpec.files.length >= 4) || input.stepSpec.complexity === 5
  return {
    mode: 'fallback',
    reason: 'impl null — changeset 없이는 적용 불가. 재시도 소진 — 과대 changeset 의심 시 Step 분할 우선(H5), 일시 장애(세션/rate limit)면 재시도. ⛔ Lead=fable SOLO 직접 구현은 사용자 승인 후',
    splitSuggested,
    metrics: metrics(0),
  }
}

// ── H5 post-Stage-1 soft 경고: 실제 changeset 크기가 위험 구간 근접 시 경고 (반환 불변, 성공 유지) ──
const actualNewBodyLines = (Array.isArray(changeset.files) ? changeset.files : []).reduce((sum, f) =>
  sum + (Array.isArray(f.symbolEdits)
    ? f.symbolEdits.reduce((s, e) => s + (typeof e.newBody === 'string' ? e.newBody.split('\n').length : 0), 0)
    : 0), 0)
if (actualNewBodyLines > SPLIT_THRESHOLD) log(`WARN changeset ~${actualNewBodyLines}줄 > ${SPLIT_THRESHOLD} — 위험 구간 근접, 차기 Step 분할 고려`)

// ════════ Stage 2: 검토 (조건부 — full: arch+quality 병렬 2렌즈 / light: complexity>=3일 때 arch 단독) ════════
// ⚠️ 배선 복구 (2026-08-10): agent-team-guide §팀 구성이 code-* 실질 워커를 review-arch·impl-quality·review-correctness로
//   정의하나 Wave 3 전환 시 arch만 배선됐다("S4 결정 — 미포함 기본값", 근거 문서 미추적). 대조군 plan-collaborative는
//   정의된 5개를 전수 스폰. impl-quality의 "Codebase Pattern Consistency"(기존 구현과 비교·패턴 충돌 확인)가
//   부재해 형제 슬롯 비대칭이 무방비였다 [verified: OBS-24 R8 — promotion-ledger L-13].
//   full만 추가(light는 비용 유지). opus 동시 ≤2 (+Lead=3) — governance 상한 내.
let review = null
const c = input.stepSpec.complexity
const needReview = input.mode === 'full' || (typeof c === 'number' ? c >= 3 : (log('NOTE complexity 누락 — 안전 default로 review 포함'), true))
if (needReview) {
  phase('Stage 2: 검토')
  const archPrompt =
    `${OVERRIDE}\n[역할] 아키텍처 검토자(review-arch 렌즈)\n${STEP}\n[changeset] ${JSON.stringify(changeset)}\n` +
    `[목표] changeset의 아키 위반·패턴 불일치·exact syntax 결함(의사코드 잔존 등) 검토. 이슈는 id(R1...) + 실측 인용.`

  if (input.mode === 'full') {
    // 병렬 2렌즈 — 서로 다른 질문(아키 적합성 vs 코드베이스 패턴 일관성). 같은 질문 중복 금지.
    const [archReview, qualityReview] = await parallel([
      () => callAgent(archPrompt,
        { label: 'stage2-review-arch', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: ReviewSchema }),
      () => callAgent(
        `${OVERRIDE}\n[역할] 구현 품질 검토자(impl-quality 렌즈)\n${STEP}\n[changeset] ${JSON.stringify(changeset)}\n` +
        `[목표] Codebase Pattern Consistency — 이 편집이 **놓인 자리**가 일관적인지 본다.\n` +
        ` (a) 편집 라인이 동종 슬롯(같은 switch case 절·리터럴 컬렉션·연속 동종 프로퍼티)에 속하면 형제를 읽고 표현 방식 대조\n` +
        `     — 상수 vs 리터럴 / 헬퍼 vs 인라인 / 네이밍. ⛔ 형제가 애초에 불균일하면 보고 금지(오탐).\n` +
        `     ⛔ 접근수준·소유권은 소비처가 결정 → 이 렌즈에서 제외.\n` +
        ` (b) 기존 코드베이스의 유사 구현과 비교, 새 패턴 도입 시 기존 패턴과의 충돌.\n` +
        `이슈는 id(Q1...) + 실측 인용. 표현 차이가 **의미 차이**를 반영하면 이슈 아님.`,
        { label: 'stage2-review-quality', agentType: 'fz:impl-quality', model: 'opus', effort: 'xhigh', schema: ReviewSchema }),
    ])
    // 하류 계약 보존: review는 단일 객체로 병합 (s2 완주 판정 / Stage3 조건 / residualIssues가 참조)
    if (archReview || qualityReview) {
      const issues = [...(archReview?.issues ?? []), ...(qualityReview?.issues ?? [])]
      review = { verdict: issues.length > 0 ? 'issues' : 'pass', issues }
      if (!archReview) log('WARN stage2 arch null — quality 단독 결과로 진행')
      if (!qualityReview) log('WARN stage2 quality null — arch 단독 결과로 진행')
    } else {
      log('WARN stage2 양 렌즈 null — 검토 미수행 (changeset 원안 반환, residualIssues에 명시)')
    }
  } else {
    review = await callAgent(archPrompt,
      { label: 'stage2-review', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: ReviewSchema })
    if (!review) log('WARN stage2 null — 검토 미수행 (changeset 원안 반환, residualIssues에 명시)')
  }
} else {
  log(`light + complexity ${c} < 3 — review 생략`)
}

// ════════ Stage 3: 이슈 반영 수정 (조건부 — issues일 때만. pass면 dead-call 제거) ════════
let finalChangeset = changeset
if (review && review.verdict === 'issues' && review.issues.length > 0) {
  phase('Stage 3: 이슈 반영 수정')
  const revised = await callAgent(
    `${OVERRIDE}\n[역할] 구현자 — 검토 반영\n${STEP}\n[원 changeset] ${JSON.stringify(changeset)}\n[검토 이슈] ${JSON.stringify(review.issues)}\n` +
    `[목표] 이슈를 반영한 수정 changeset. 동의하지 않는 이슈는 그대로 두되 summary에 사유 명시.`,
    { label: 'stage3-revise', agentType: 'fz:impl-correctness', model: 'opus', effort: 'xhigh', schema: ChangesetSchema })
  if (revised) finalChangeset = revised
  else log('WARN stage3 null — 원 changeset 반환 (이슈 미반영, residualIssues 유지)')
}

const s1 = !!changeset
const s2 = needReview ? !!review : true // 의도적 생략은 완주로 간주 (light 저복잡도)
const s3 = (review && review.verdict === 'issues') ? (finalChangeset !== changeset) : true // pass/생략 = 해당 없음 완주
const stagesCompleted = [s1, s2, s3].filter(Boolean).length
log(`완주 ${stagesCompleted}/3 — changeset 파일 ${finalChangeset.files.length}개 / 검토 ${review ? review.verdict : 'skipped'}`)

return {
  mode: 'workflow',
  changeset: finalChangeset,
  reviewVerdict: review ? review.verdict : 'skipped',
  residualIssues: review ? review.issues.filter(i => review.verdict === 'issues' && finalChangeset === changeset) : [], // stage3 실패/미동의 시 잔존 — Lead 판정
  metrics: metrics(stagesCompleted), // Lead: 적용 → 빌드 → §5.7 세션당 1행 집계 (invoke당 N행 발산 방지)
}
