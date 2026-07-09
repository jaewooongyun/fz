// workflows/code-pair.js — fz-code/fz-fix 구현 페어 (TEAM pair-programming 대체, Wave 3)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + Wave 0-2 실측]
//   표준 패턴 3종 적용. Step당 1회 invoke — 빌드 oracle은 Lead 전용이므로 분할 invoke 구조.
//   호출(Lead, SKILL.md 절차 — Step 루프는 Lead 소유):
//     Workflow({ scriptPath: '{plugin_root}/workflows/code-pair.js',
//       args: { mode: 'full'|'light', stepSpec: {id,title,goal,files,verify,complexity}, contextPath, buildFeedback?, changesetTarget } })
//   effort 계약: 전 agent() 호출 model+effort(=xhigh) 명시. 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   반환: { mode:'workflow', changeset, reviewVerdict, residualIssues, metrics }
//     | { mode:'fallback', reason, splitSuggested?, metrics } → Lead는 SOLO 구현 경로 수행.
//     | { mode:'split_required', reason, metrics } → Lead는 Step 분할 후 재invoke.
//   ⛔ 책임 재배분 (S0, 사용자 승인 OQ1): 에이전트는 디스크를 수정하지 않는다 — changeset JSON만 반환.
//     Lead가 적용(replace_symbol_body/Edit) + 빌드 검증 + 다음 Step invoke. 부분 적용 후 빌드 실패 시
//     되돌리기/계속은 Lead 절차 (SKILL.md). 재시도 = buildFeedback 포함 새 invoke (resume 비의존 —
//     buildFeedback이 args를 바꿔 캐시 키 불일치 [선례: ts 제거 — resume 캐시 미스 유발]).
//
// [설계 — modules/patterns/pair-programming.md 평탄화]
//   full(fz-code): Stage1 impl(opus) changeset → Stage2 review-arch(opus) 검토 →
//     Stage3 impl(opus) 이슈 반영 수정 — **조건부**: review pass면 Stage3 생략 (2-call).
//     계획 표기 '고정 3-call'은 unresolved #2가 잠정 부정확 지적 — pass 경로 dead-call 제거가 정직
//     (plan-collaborative direction 조건부화 동형). 분기 상한 고정(2-3 call) → 가변 fan-out 아님.
//   light(fz-fix): Stage1 impl(opus) → Stage2 review는 stepSpec.complexity>=3만 (1-2 call).
//     complexity 누락 시 review 포함 (안전 default) + log 명시.
//   opus 동시 ≤1 (+Lead=2): 전 호출 순차 — parallel 미사용 (Step 내 의존 사슬).
//   budget 가드: 해당 없음 — 분기 상한 고정 1-3 call (§12 단서).
//   impl-quality/review-correctness/memory-curator: Lead 경로 (S4 결정 — 미포함 기본값).

export const meta = {
  name: 'code-pair',
  description: 'fz-code/fz-fix 구현 페어 — impl changeset(JSON, 디스크 미수정) → 조건부 arch 검토 → 수정. Step당 1 invoke, Lead가 적용+빌드. 1-3 call',
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
async function callAgent(prompt, opts) {
  agentCalls += 1
  const out = await agent(prompt, opts)
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) }
  return out
}
function metrics(stagesCompleted) {
  return { agentCalls, nullCount: nullCalls, fallbackCount, stagesCompleted }
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

// ════════ Stage 2: 아키 검토 (조건부 — full: 항상 / light: complexity>=3 또는 누락) ════════
let review = null
const c = input.stepSpec.complexity
const needReview = input.mode === 'full' || (typeof c === 'number' ? c >= 3 : (log('NOTE complexity 누락 — 안전 default로 review 포함'), true))
if (needReview) {
  phase('Stage 2: 아키 검토')
  review = await callAgent(
    `${OVERRIDE}\n[역할] 아키텍처 검토자(review-arch 렌즈)\n${STEP}\n[changeset] ${JSON.stringify(changeset)}\n` +
    `[목표] changeset의 아키 위반·패턴 불일치·exact syntax 결함(의사코드 잔존 등) 검토. 이슈는 id(R1...) + 실측 인용.`,
    { label: 'stage2-review', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: ReviewSchema })
  if (!review) log('WARN stage2 null — 검토 미수행 (changeset 원안 반환, residualIssues에 명시)')
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
