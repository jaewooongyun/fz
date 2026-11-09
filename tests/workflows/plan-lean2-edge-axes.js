// plan-lean2 적대 렌즈 축 · 부분 제출 · 방어 항목 (round 2 S13) — 가짜 런타임에서 plan-lean2 를 통째로 돌린다.
// 셀:
//   f383-edge-axes-from-args          기본(미지정)은 UI 축 그대로 · edgeAxes 를 주면 그 축만 들어가고 UI 축(좌표계 · 애니메이션)이 없다 ·
//                                     문자열이 아닌 원소는 fallback(args invalid) · 콜 0
//   f146-item-count-short             minSteps 3 · full steps 1 → fallback 'partial-submit' · 병합 콜 없음 / minSteps 1 → 정상 / 'x' → args invalid
//   f438-defense-without-failurepath  defenseFailurePath — failurePath 없는 방어는 demoted:'suggestion'(반환 · 병합 입력) · 병합 프롬프트에 한 줄 ·
//                                     failurePath 있는 방어는 그대로 · edge 스키마 사본에 failurePath / 끄면 스키마 · 프롬프트 그대로
// exit: 0 전건 통과 · 1 단언 실패
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'plan-lean2.js')
const BASE = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }
const STEP = { id: 'S1', title: 't', files: ['a'] }
const table = (edgeCases, steps = [STEP]) => ({
  'lean2-full': { directionVerdict: 'PROCEED', directionAlternatives: [], steps, readScope: [], writeScope: [] },
  'lean2-edge': { edgeCases, impactNotes: [], latentDefects: [] },
  'lean2-impact-arch': { impactFiles: [], patternVerdicts: [] },
  'lean2-merge': { addedEdgeCases: [], addedImpact: [], stepAmendments: [], implicationRegister: [], unresolved: [] },
})
const seen = {}   // 하네스 calls 는 schema 를 boolean 으로만 남긴다 — 실제 스키마는 응답기에서 붙잡는다
const responder = (t, key) => (prompt, opts) => {
  if (key) seen[`${key}:${opts.label}`] = opts.schema
  return t[opts.label] === undefined ? null : JSON.parse(JSON.stringify(t[opts.label]))
}
const itemKeys = s => Object.keys((((s || {}).properties || {}).edgeCases || {}).items?.properties || {})
const call = (r, label) => r.calls.find(c => c.label === label) || {}
const E1 = { id: 'E1', case: 'c', failureScenario: 'f', whereItBreaks: 'w' }

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

;(async () => {
  // F-383
  const d = await run(WF, { args: BASE, responder: responder(table([E1])) })
  const a = await run(WF, { args: Object.assign({}, BASE, { edgeAxes: ['스크립트 종료 코드', '부분 입력'] }), responder: responder(table([E1])) })
  const bad = await run(WF, { args: Object.assign({}, BASE, { edgeAxes: [1] }), responder: responder(table([E1])) })
  const dp = call(d, 'lean2-edge').prompt || '', ap = call(a, 'lean2-edge').prompt || ''
  check('f383-edge-axes-from-args — 미지정은 기본 축 · 받은 축만 · UI 축 없음 · 불량 원소 fallback',
    dp.includes('필수 축: 좌표계') && ap.includes('필수 축: 스크립트 종료 코드 · 부분 입력.') && !ap.includes('좌표계') && !ap.includes('애니메이션')
      && bad.result.mode === 'fallback' && /edgeAxes/.test(bad.result.reason || '') && bad.calls.length === 0,
    `기본 좌표계=${dp.includes('좌표계')} · 받은 축=${ap.includes('스크립트 종료 코드')} · 받은 쪽 좌표계=${ap.includes('좌표계')} · 불량 ${bad.result.mode}/${bad.calls.length}`)

  // F-146
  const short = await run(WF, { args: Object.assign({}, BASE, { minSteps: 3 }), responder: responder(table([E1])) })
  const enough = await run(WF, { args: Object.assign({}, BASE, { minSteps: 1 }), responder: responder(table([E1])) })
  const badN = await run(WF, { args: Object.assign({}, BASE, { minSteps: 'x' }), responder: responder(table([E1])) })
  check('f146-item-count-short — steps 1 < minSteps 3 → partial-submit · 병합 없음 / 충분하면 정상 / 불량 값 fallback',
    short.result.mode === 'fallback' && /^partial-submit: steps 1 < minSteps 3/.test(short.result.reason || '') && !short.calls.some(c => c.label === 'lean2-merge')
      && enough.result.mode === 'workflow' && badN.result.mode === 'fallback' && /minSteps/.test(badN.result.reason || '') && badN.calls.length === 0,
    `short ${short.result.mode}/${short.result.reason} · enough ${enough.result.mode} · bad ${badN.result.mode}`)

  // F-438
  const DEF = [Object.assign({}, E1, { defense: true }), Object.assign({}, E1, { id: 'E2', defense: true, failurePath: 'a() 뒤 b() — 호출처 X.swift:12' })]
  const on = await run(WF, { args: Object.assign({}, BASE, { defenseFailurePath: true }), responder: responder(table(DEF), 'on') })
  const off = await run(WF, { args: BASE, responder: responder(table(DEF), 'off') })
  const ec = ((on.result.lensOutputs || {}).edge || {}).edgeCases || []
  const mp = call(on, 'lean2-merge').prompt || ''
  const onKeys = itemKeys(seen['on:lean2-edge']), offKeys = itemKeys(seen['off:lean2-edge'])
  check('f438-defense-without-failurepath — failurePath 없는 방어 demoted · 병합 지시 · 근거 있는 방어 유지 · 끄면 그대로',
    ec.length === 2 && ec[0].demoted === 'suggestion' && !('demoted' in ec[1]) && on.result.demotedDefenses === 1
      && mp.includes('"demoted":"suggestion"') && mp.includes('unresolved 에 "선택 사항"') && (call(on, 'lean2-edge').prompt || '').includes('failurePath')
      && onKeys.includes('failurePath') && onKeys.includes('defense') && offKeys.length > 0 && !offKeys.includes('failurePath')
      && !('demotedDefenses' in off.result) && !(call(off, 'lean2-merge').prompt || '').includes('demoted') && !(call(off, 'lean2-edge').prompt || '').includes('failurePath'),
    `demoted ${JSON.stringify(ec.map(e => e.demoted || '-'))} · 수 ${on.result.demotedDefenses} · 병합 지시 ${mp.includes('선택 사항')} · 스키마 on ${onKeys} / off ${offKeys}`)

  console.log(`\nplan-lean2 옵션 ${fail ? '실패 ' + fail + '건' : '전건 통과'}`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
