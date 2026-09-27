// plan-lean2 완주 판정 (A3-01) — 세 팔(full·edge·impactArch)이 모두 있을 때만 Stage 1 완주다.
//
// ⛔ 스크립트를 **통째로** 가짜 런타임(tests/lib/wf_harness.js)에서 돌린다 — 마커 블록 추출로는 완주 계산과
//    반환 조립을 함께 못 본다. 워커 응답은 label 로 고른 최소 객체이고, null 은 "죽은 워커" 다.
// ⛔ FZ_WF_ROOT 로 다른 트리(기준 트리)의 workflows/plan-lean2.js 를 같은 셀로 돌린다 — 판별력 대조용.
//    그때는 FAIL 줄이 나와야 한다(이전 판은 edge 가 죽어도 완주 2/2 를 냈다).
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'plan-lean2.js')
const ARGS = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }

const OK = {
  'lean2-full': {
    directionVerdict: 'PROCEED', directionAlternatives: [{ id: 'A1' }, { id: 'A2' }],
    steps: [{ id: 'S1', title: 't', files: ['a'], verify: { kind: 'manual', criterion: 'c' } }],
    readScope: ['a'], writeScope: [{ file: 'a', why: 'w' }], rtm: [], implicationRegister: [],
  },
  'lean2-edge': { edgeCases: [{ id: 'E1', case: 'x' }], latentDefects: [] },
  'lean2-impact-arch': { impactFiles: [{ file: 'a' }], secondaryHosts: [], originBodyRequests: [{ symbol: 'f', why: 'base 호출자 수' }] },
  'lean2-merge': { addedEdgeCases: [], addedImpact: [], stepAmendments: [{ stepId: 'S1' }], unresolved: [], implicationRegister: [] },
}
function responder(dead, override = {}) {
  return (prompt, opts) => {
    if (dead.includes(opts.label)) return null
    return Object.assign({}, OK[opts.label], override[opts.label] || {})
  }
}

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)

;(async () => {
  let r = await run(WF, { args: ARGS, responder: responder([]) })
  let x = r.result
  check('전부 ok → stagesCompleted 2', x.metrics && x.metrics.stagesCompleted === 2, JSON.stringify(x.metrics))
  check('전부 ok → degraded false · missingLenses []', x.degraded === false && same(x.missingLenses, []), `${x.degraded} ${JSON.stringify(x.missingLenses)}`)
  check('전부 ok → 기존 반환 필드 보존(impactRequests·directionEscalation·delta)',
    Array.isArray(x.impactRequests) && x.impactRequests.length === 1 && x.directionEscalation === null && x.delta && Array.isArray(x.delta.stepAmendments),
    JSON.stringify({ impactRequests: x.impactRequests, directionEscalation: x.directionEscalation, delta: x.delta }))

  r = await run(WF, { args: ARGS, responder: responder([], { 'lean2-full': { directionVerdict: 'RECONSIDER' } }) })
  check('RECONSIDER → directionEscalation 보존', r.result.directionEscalation && r.result.directionEscalation.verdict === 'RECONSIDER', JSON.stringify(r.result.directionEscalation))

  r = await run(WF, { args: ARGS, responder: responder(['lean2-edge']) })
  x = r.result
  check('edge null → degraded true · missingLenses [edge]', x.degraded === true && same(x.missingLenses, ['edge']), `${x.degraded} ${JSON.stringify(x.missingLenses)}`)
  check('edge null → Stage 1 미완주로 계산(stagesCompleted 1 — 병합만)', x.metrics && x.metrics.stagesCompleted === 1, JSON.stringify(x.metrics))

  r = await run(WF, { args: ARGS, responder: responder(['lean2-edge', 'lean2-impact-arch']) })
  x = r.result
  const mergeCalls = r.calls.filter(c => c.label === 'lean2-merge').length
  check('edge·impact 모두 null → 병합 0콜', mergeCalls === 0, `merge calls ${mergeCalls}`)
  check('edge·impact 모두 null → stagesCompleted 0', x.metrics && x.metrics.stagesCompleted === 0, JSON.stringify(x.metrics))
  check('edge·impact 모두 null → missingLenses [edge, impactArch]', same(x.missingLenses, ['edge', 'impactArch']), JSON.stringify(x.missingLenses))

  r = await run(WF, { args: ARGS, responder: responder(['lean2-merge']) })
  x = r.result
  check('merge null → degraded true · missingLenses [merge] · stagesCompleted 1',
    x.degraded === true && same(x.missingLenses, ['merge']) && x.metrics && x.metrics.stagesCompleted === 1,
    `${x.degraded} ${JSON.stringify(x.missingLenses)} ${JSON.stringify(x.metrics)}`)

  r = await run(WF, { args: ARGS, responder: responder(['lean2-full']) })
  x = r.result
  check('full null → 기존 fallback(stagesCompleted 0)', x.mode === 'fallback' && x.metrics && x.metrics.stagesCompleted === 0, JSON.stringify(x))

  console.log(`\nplan-lean2 완주 판정 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), WF) || WF})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
