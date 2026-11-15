// review-live 위치 필드 (S16c) — args.locatedFindings 가 켜졌을 때만 Stage 1 두 렌즈 finding 에 §3 병합 키 선택 필드가 붙는다.
//
// ⛔ craft 와 다른 관심사다 — craftAxes 만 켜면 위치 필드가 없고, 둘 다 켜면 arch 에 위치 + craft 필드가 함께 있다.
//    한 플래그가 둘을 켜면 R-C A/B 의 craft arm 에 병합 키 효과가 섞인다(R-B 리뷰 A:A2).
// ⛔ 워크플로를 가짜 런타임(tests/lib/wf_harness.js)에서 돌려 **실제 콜 입력**을 본다 — 하네스는 스키마를 불리언으로만 남기므로
//    responder 가 opts.schema 를 직접 잡는다.
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준에는 locatedFindings 가 없다).
// ⛔ 옵션 미지정일 때 기준과 바이트 단위로 같은지는 tests/workflows/default-off-regression.js 가 본다.
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'review-live.js')
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }
const AXES = ['idiom', 'naming', 'architecture', 'ui_structure', 'placement', 'design_alternative']
const TABLE = {
  'stage1-arch': { findings: [{ id: 'A1', severity: 'minor', category: 'c', title: 't', detail: 'd', evidence: 'e' }], okAreas: [],
    axisCoverage: AXES.map(axis => ({ axis, status: 'none', note: '해당 없음 — 합성' })) },
  'stage1-quality': { findings: [], okAreas: [] },
  'stage2-arch-on-quality': { adjustments: [], additions: [] },
  'stage2-quality-on-arch': { adjustments: [], additions: [] },
  'stage3-counter': { challenges: [], missedFindings: [] },
}

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

async function capture(args) {
  const calls = []
  await run(WF, { args: Object.assign({}, ARGS, args), responder: (prompt, opts) => {
    calls.push({ label: opts.label, schema: opts.schema || null })
    return TABLE[opts.label] ? JSON.parse(JSON.stringify(TABLE[opts.label])) : null
  } })
  return calls
}
const items = (calls, label) => {
  const c = calls.find(x => x.label === label)
  return c && c.schema && c.schema.properties && c.schema.properties.findings ? c.schema.properties.findings.items : null
}
const located = it => !!it && !!it.properties.line_range && !!it.properties.discoveryAxis
const optional = it => !!it && !it.required.includes('line_range') && !it.required.includes('discoveryAxis')
const craft = it => !!it && !!it.properties.craftAxis && !!it.properties.ruleRef
const labels = calls => calls.map(c => c.label).sort().join(',')

;(async () => {
  const unset = await capture({})
  const on = await capture({ locatedFindings: true })
  const craftOnly = await capture({ craftAxes: true })
  const both = await capture({ locatedFindings: true, craftAxes: true })
  const S1 = ['stage1-arch', 'stage1-quality']

  check('미지정: Stage 1 두 렌즈에 위치 필드가 없다', unset.length > 0 && S1.every(l => items(unset, l) && !located(items(unset, l))),
    S1.map(l => `${l}=${located(items(unset, l))}`).join(' '))
  check('locatedFindings: Stage 1 두 렌즈 finding 에 line_range · discoveryAxis 가 선택 필드로 붙는다',
    on.length > 0 && S1.every(l => located(items(on, l)) && optional(items(on, l))),
    S1.map(l => `${l}=${located(items(on, l))}/${optional(items(on, l))}`).join(' '))
  check('locatedFindings: Stage 2 · 3 스키마는 그대로(위치 필드는 Stage 1 전용)',
    on.filter(c => !S1.includes(c.label)).length > 0 &&
    on.filter(c => !S1.includes(c.label)).every(c => !JSON.stringify(c.schema || {}).includes('"discoveryAxis"')),
    on.filter(c => !S1.includes(c.label) && JSON.stringify(c.schema || {}).includes('"discoveryAxis"')).map(c => c.label).join(','))
  check('craftAxes 만: 위치 필드가 없다 · arch 에만 craft 필드',
    !located(items(craftOnly, 'stage1-arch')) && !located(items(craftOnly, 'stage1-quality')) &&
    craft(items(craftOnly, 'stage1-arch')) && !craft(items(craftOnly, 'stage1-quality')),
    `arch 위치 ${located(items(craftOnly, 'stage1-arch'))} · quality 위치 ${located(items(craftOnly, 'stage1-quality'))}`)
  check('둘 다: arch 에 위치 + craft 필드 · quality 에 위치 필드만',
    located(items(both, 'stage1-arch')) && craft(items(both, 'stage1-arch')) && located(items(both, 'stage1-quality')) && !craft(items(both, 'stage1-quality')),
    `arch ${located(items(both, 'stage1-arch'))}/${craft(items(both, 'stage1-arch'))} · quality ${located(items(both, 'stage1-quality'))}`)
  // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 못 본다
  check('네 조합의 콜 구성(label 다중집합)이 같다', [on, craftOnly, both].every(c => labels(c) === labels(unset)),
    [unset, on, craftOnly, both].map(labels).join(' | '))

  console.log(`\n위치 필드 분리 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
