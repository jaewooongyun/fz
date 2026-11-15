// plan-lean2 병합 조건부 생략 arm (S18b) — args.mergeMode='conditional' 에서 Stage 1 의미 필드가 전부 비었을 때만 병합 콜을 생략한다.
//
// ⛔ 기본은 always 다 — 미지정 · 'always' 는 렌즈가 비어도 4콜 그대로(기준선 불변). 콜 입력의 바이트 동일은 default-off-regression.js 가 본다.
// ⛔ 생략 조건은 입력(Stage 1 반환)만 본다 — 필드 하나라도 차 있거나 렌즈가 하나라도 null 이면 병합한다(fail-open).
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준은 mergeMode 를 모른다).
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'plan-lean2.js')
const ARGS = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }
const FIELDS = {
  edge: ['edgeCases', 'impactNotes', 'latentDefects'],
  impactArch: ['impactFiles', 'hiddenDependencies', 'secondaryHosts', 'existingTestSuites', 'patternVerdicts', 'violations',
    'deadCode', 'originBodyRequests', 'impactRequests'],
}
const FULL = { directionVerdict: 'PROCEED', directionAlternatives: [], steps: [{ id: 'S1', title: 't', files: ['a'] }], readScope: [], writeScope: [] }
const emptyEdge = () => ({ edgeCases: [], impactNotes: [], latentDefects: [] })
const emptyImpact = () => ({ impactFiles: [], hiddenDependencies: [], secondaryHosts: [], existingTestSuites: [], patternVerdicts: [],
  violations: [], deadCode: [], originBodyRequests: [], impactRequests: [] })
const SAMPLE = {   // 필드 하나를 채울 때 쓰는 최소 항목
  edgeCases: { id: 'E1', case: 'c', failureScenario: 'f', whereItBreaks: 'w' }, impactNotes: 'n', latentDefects: 'd',
  impactFiles: { file: 'a', kind: 'direct', evidence: 'e' }, hiddenDependencies: 'h', secondaryHosts: 's', existingTestSuites: 't',
  patternVerdicts: { topic: 'p', recommendation: 'r', rationale: 'x' }, violations: 'v', deadCode: 'd', originBodyRequests: 'o', impactRequests: 'q',
}
const MERGE = { addedEdgeCases: [], addedImpact: [], stepAmendments: [], implicationRegister: [], unresolved: [] }

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

async function go(args, edge, impactArch) {
  const table = { 'lean2-full': FULL, 'lean2-edge': edge, 'lean2-impact-arch': impactArch, 'lean2-merge': MERGE }
  const r = await run(WF, { args: Object.assign({}, ARGS, args), responder: (p, opts) => {
    const v = table[opts.label]
    return v === null || v === undefined ? null : JSON.parse(JSON.stringify(v))
  } })
  return { labels: r.calls.map(c => c.label), result: r.result || {} }
}
const merged = o => o.labels.includes('lean2-merge')

;(async () => {
  const unset = await go({}, emptyEdge(), emptyImpact())
  check('미지정: 렌즈가 비어도 4콜(병합 포함) — 기준선 불변', unset.labels.length === 4 && merged(unset), unset.labels.join(','))
  check('미지정: 반환에 mergeSkipped 가 없다(기본 반환 모양 불변)', !('mergeSkipped' in unset.result), JSON.stringify(Object.keys(unset.result)))
  const always = await go({ mergeMode: 'always' }, emptyEdge(), emptyImpact())
  check("'always': 렌즈가 비어도 4콜", always.labels.length === 4 && merged(always), always.labels.join(','))

  const skip = await go({ mergeMode: 'conditional' }, emptyEdge(), emptyImpact())
  check('conditional + 전부 빈 렌즈: 병합 0콜(3콜)', skip.labels.length === 3 && !merged(skip), skip.labels.join(','))
  check('conditional + 전부 빈 렌즈: mergeSkipped.reason 기록', !!(skip.result.mergeSkipped && skip.result.mergeSkipped.reason), JSON.stringify(skip.result.mergeSkipped))
  check('conditional + 전부 빈 렌즈: lensStatus.merge = skipped · degraded 아님 · 완주 2',
    skip.result.lensStatus && skip.result.lensStatus.merge === 'skipped' && skip.result.degraded === false && skip.result.metrics && skip.result.metrics.stagesCompleted === 2,
    JSON.stringify({ lensStatus: skip.result.lensStatus, degraded: skip.result.degraded, metrics: skip.result.metrics }))

  // 의미 필드를 하나씩만 채운다 — 어느 하나라도 차 있으면 병합한다
  for (const [lens, fields] of Object.entries(FIELDS)) {
    for (const f of fields) {
      const e = emptyEdge(), i = emptyImpact()
      ;(lens === 'edge' ? e : i)[f] = [SAMPLE[f]]
      const one = await go({ mergeMode: 'conditional' }, e, i)
      check(`conditional + ${lens}.${f} 1건: 병합 1콜`, merged(one) && !(one.result.mergeSkipped), one.labels.join(','))
    }
  }

  // 렌즈 null — 필드를 알 수 없으니 생략하지 않는다(fail-open)
  const edgeNull = await go({ mergeMode: 'conditional' }, null, emptyImpact())
  check('conditional + edge null: 병합한다(fail-open)', merged(edgeNull), edgeNull.labels.join(','))
  const impactNull = await go({ mergeMode: 'conditional' }, emptyEdge(), null)
  check('conditional + impact-arch null: 병합한다(fail-open)', merged(impactNull), impactNull.labels.join(','))

  console.log(`\nplan-lean2 병합 arm ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
