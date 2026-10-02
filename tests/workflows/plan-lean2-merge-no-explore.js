// plan-lean2 병합 콜 무탐색 계약 (R-D S32 · F-345) — 병합 콜이 탐색 도구 없는 fz:plan-merge 로 가고, 프롬프트가 '입력 JSON 만으로 접는다 ·
// 근거가 모자라면 unresolved' 를 말하며, 스키마는 델타 전용이다.
//
// ⛔ 에이전트의 도구 선언(agents/plan-merge.md 의 tools 가 비었다)은 S32 게이트의 frontmatter 검사와 실제 1회 프로브가 본다 —
//    여기서는 워크플로가 그 에이전트를 부르는지와 콜 입력을 본다. 기준 트리 대비 바이트 차이는 default-off-regression.js 의 변환이 본다.
// ⛔ Stage 1 콜의 agentType 은 그대로다(전체 플랜 = plan-structure · edge = plan-edge-case · impact-arch = plan-impact).
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준의 병합 콜은 plan-structure 다).
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'plan-lean2.js')
const ARGS = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }
const FULL = { directionVerdict: 'PROCEED', directionAlternatives: [], steps: [{ id: 'S1', title: 't', files: ['a'] }], readScope: [], writeScope: [] }
const EDGE = { edgeCases: [{ id: 'E1', case: 'c', failureScenario: 'f', whereItBreaks: 'w' }], impactNotes: [], latentDefects: [] }   // 신호 1건 — conditional 에서도 병합한다
const IMPACT = { impactFiles: [], hiddenDependencies: [], secondaryHosts: [], existingTestSuites: [], patternVerdicts: [], violations: [],
  deadCode: [], originBodyRequests: [], impactRequests: [] }
const MERGE = { addedEdgeCases: [], addedImpact: [], stepAmendments: [], implicationRegister: [], unresolved: [] }
const CONTRACT = ['이 콜에는 탐색 도구가 없다', '입력 JSON 만으로 접고', 'unresolved 에 적는다']
const DELTA_PROPS = 'addedEdgeCases,addedImpact,implicationRegister,stepAmendments,unresolved'

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

;(async () => {
  const table = { 'lean2-full': FULL, 'lean2-edge': EDGE, 'lean2-impact-arch': IMPACT, 'lean2-merge': MERGE }
  for (const extra of [{}, { mergeMode: 'always' }, { mergeMode: 'conditional' }]) {
    const schemas = {}
    const r = await run(WF, { args: Object.assign({}, ARGS, extra), responder: (p, opts) => {
      schemas[opts.label] = opts.schema
      const v = table[opts.label]
      return v === null || v === undefined ? null : JSON.parse(JSON.stringify(v))
    } })
    const tag = JSON.stringify(extra)
    const m = r.calls.find(c => c.label === 'lean2-merge')
    check(`${tag}: 병합 콜이 돈다(edge 신호 1건)`, !!m, r.calls.map(c => c.label).join(','))
    if (!m) continue
    check(`${tag}: 병합 agentType = fz:plan-merge`, m.agentType === 'fz:plan-merge', m.agentType)
    check(`${tag}: 병합 model · effort = opus · xhigh(명시 유지)`, m.model === 'opus' && m.effort === 'xhigh', `${m.model} ${m.effort}`)
    for (const k of CONTRACT) check(`${tag}: 병합 프롬프트에 '${k}'`, m.prompt.includes(k), '없음')
    const props = Object.keys((schemas['lean2-merge'] && schemas['lean2-merge'].properties) || {}).sort().join(',')
    check(`${tag}: 병합 schema = 델타 전용`, props === DELTA_PROPS, props)
    const st1 = Object.fromEntries(r.calls.filter(c => c.label !== 'lean2-merge').map(c => [c.label, c.agentType]))
    check(`${tag}: Stage 1 agentType 그대로`, st1['lean2-full'] === 'fz:plan-structure' && st1['lean2-edge'] === 'fz:plan-edge-case'
      && st1['lean2-impact-arch'] === 'fz:plan-impact', JSON.stringify(st1))
  }
  console.log(`\nplan-lean2 병합 무탐색 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
