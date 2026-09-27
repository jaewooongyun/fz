// fz-plan 소비 계약 — plan-lean2 의 degraded 반환이 SKILL.md 절차 4 의 분기로 이어지는가 (A3-01).
//
// 소비처는 산문 절차라 실행할 수 없다. 그래서 두 쪽을 **결합**해서 본다:
//   ① 실제 반환 — 가짜 런타임에서 edge 를 죽이면 degraded·missingLenses 가 오고, 전부 ok 면 분기가 발동하지 않는다
//   ② 분기 문구 — 절차 4 의 degraded 항목이 완주 보류 · L3(resumeFromRunId) · L4 를 지시한다
//   ③ 결합 — 분기가 가리키는 반환 필드(degraded · missingLenses · metrics.stagesCompleted)가 ① 의 반환에 실제로 있다
// ⛔ ③ 이 없으면 필드 이름이 한쪽에서만 바뀌어도 분기가 조용히 no-op 이 된다(F-215: 소비처가 없는 필드를 읽어 영구 no-op 이었다).
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'plan-lean2.js')
const SKILL = path.join(ROOT, 'skills', 'fz-plan', 'SKILL.md')
const ARGS = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }
const FIELDS = ['degraded', 'missingLenses', 'metrics.stagesCompleted']

const responder = dead => (prompt, opts) => (dead.includes(opts.label) ? null : {
  directionVerdict: 'PROCEED', directionAlternatives: [], steps: [{ id: 'S1', title: 't', files: [] }],
  readScope: [], writeScope: [], rtm: [], implicationRegister: [],
  edgeCases: [], impactFiles: [], originBodyRequests: [], addedEdgeCases: [], addedImpact: [], stepAmendments: [], unresolved: [],
})
const dig = (o, p) => p.split('.').reduce((v, k) => (v && Object.prototype.hasOwnProperty.call(v, k) ? v[k] : undefined), o)

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

;(async () => {
  const bad = (await run(WF, { args: ARGS, responder: responder(['lean2-edge']) })).result
  const good = (await run(WF, { args: ARGS, responder: responder([]) })).result
  check('① edge 결손 → degraded true · missingLenses 에 edge', bad.degraded === true && (bad.missingLenses || []).includes('edge'), JSON.stringify({ degraded: bad.degraded, missingLenses: bad.missingLenses }))
  check('① 전부 ok → 분기 미발동(degraded false)', good.degraded === false, String(good.degraded))

  const text = fs.readFileSync(SKILL, 'utf8')
  const i = text.indexOf('4. **반환 처리**')
  const j = text.indexOf('5. **Workflow 외부', i)
  const sec = i >= 0 && j > i ? text.slice(i, j) : ''
  check('② 절차 4(반환 처리) 구간을 찾았다', sec.length > 0, 'SKILL.md 에서 절차 4~5 경계를 못 찾음')
  const lines = sec.split('\n')
  const k = lines.findIndex(l => l.includes('`degraded: true`'))
  const branch = k >= 0 ? lines.slice(k, k + 3).filter((l, n) => n === 0 || /^\s{5,}/.test(l)).join('\n') : ''
  check('② degraded 분기 항목이 있다', branch.length > 0, '절차 4 에 `degraded: true` 항목이 없다')
  for (const w of ['완주 보류', 'L3', 'resumeFromRunId', 'L4']) {
    check(`② 분기가 '${w}' 를 지시한다`, branch.includes(w), '분기 문구에 없음')
  }
  for (const f of FIELDS) {
    const name = f.split('.').pop()
    check(`③ 분기가 가리키는 반환 필드 '${f}' — 문구에 있고 실제 반환에도 있다`, branch.includes(name) && dig(bad, f) !== undefined,
      `문구 ${branch.includes(name)} · 반환 ${JSON.stringify(dig(bad, f))}`)
  }
  console.log(`\nfz-plan 소비 계약(degraded) ${fail ? '실패 ' + fail + '건' : '전건 통과'}`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
