// 실패 주입 A — 기존 워크플로의 렌즈별 null 이 "완주" 로 보고되지 않는다 (S24a).
//
// 대상(--scope existing): plan-lean2 · review-live · peer-review(Tier 2·3) · code-pair(full).
// 셀마다 워커 하나를 죽이고(가짜 런타임에서 null 반환) 두 가지를 본다.
//   ① 완주로 계산되지 않는다 — metrics.stagesCompleted < 그 경로의 완주 기준, 또는 mode:'fallback'
//   ② 해당 신호가 나온다 — 워크플로가 결손을 알리는 필드(degraded·missingLenses · partial·lensesCompleted · nullCount·reviews)
// 대조 셀(아무도 죽이지 않음)은 완주 기준에 도달해야 한다 — 그래야 ① 의 "미달" 이 주입 때문임을 안다.
// ⛔ 스크립트를 통째로 돌린다(tests/lib/wf_harness.js). 워커 응답은 label 로 고른 최소 객체다.
// ⛔ 런처·병합·divergence(R-B·R-C) 셀은 이 판에 없다 — 다른 scope 는 미실행(exit 2)이다.
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const argv = process.argv.slice(2)
const scope = argv[0] === '--scope' ? argv[1] : 'existing'
if (scope !== 'existing') {
  console.log(`UNRUN  scope '${scope}' 의 셀은 아직 없다 — 이 판은 existing 만 구현한다`)
  process.exit(2)
}

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const wf = name => path.join(ROOT, 'workflows', name)

const LENS = { issues: [], strengths: ['s'], overall_assessment: 'ok' }
const MAJOR = { id: 'A1', severity: 'major', file: 'a.swift', line_range: '10-12', title: 't', evidence: 'e', origin: 'introduced' }
const CROSS = { adjustments: [], additions: [] }
const RESP = {
  'lean2-full': { directionVerdict: 'PROCEED', directionAlternatives: [], steps: [{ id: 'S1', title: 't', files: [] }], readScope: [], writeScope: [], rtm: [], implicationRegister: [] },
  'lean2-edge': { edgeCases: [] },
  'lean2-impact-arch': { impactFiles: [], originBodyRequests: [] },
  'lean2-merge': { addedEdgeCases: [], addedImpact: [], stepAmendments: [], unresolved: [], implicationRegister: [] },
  'stage1-arch': { ...LENS, findings: [], okAreas: [] },
  'stage1-quality': { ...LENS, findings: [], okAreas: [] },
  'stage1-correctness': { ...LENS },
  'stage2-arch-on-quality': CROSS, 'stage2-quality-on-arch': CROSS,
  'stage2-arch-on-peers': CROSS, 'stage2-quality-on-peers': CROSS,
  'stage3-counter': { challenges: [], missedFindings: [], missedIssues: [] },
  'stage1-impl': { files: [{ path: 'a.swift', symbolEdits: [] }], summary: 's', buildExpectation: 'b' },
  'stage2-review-arch': { issues: [] }, 'stage2-review-quality': { issues: [] },
  'stage3-revise': { files: [{ path: 'a.swift', symbolEdits: [] }], summary: 's', buildExpectation: 'b' },
}
const responder = (dead, extra = {}) => (prompt, opts) =>
  (dead.includes(opts.label) ? null : JSON.parse(JSON.stringify(Object.assign({}, RESP[opts.label], extra[opts.label] || {}))))

// 워크플로별 경로 · 완주 기준 · 결손 신호
const SUITES = [
  { name: 'plan-lean2', file: 'plan-lean2.js', full: 2,
    args: { requirement: 'r', codeContextPath: '/tmp/c.md' },
    dead: ['lean2-edge', 'lean2-impact-arch', 'lean2-merge'], first: 'lean2-full',
    signal: (r, lab) => r.degraded === true && Array.isArray(r.missingLenses) && r.missingLenses.length > 0,
    signalName: 'degraded·missingLenses' },
  { name: 'review-live', file: 'review-live.js', full: 3,
    args: { diffPath: '/tmp/d.diff', intentContext: 'i' },
    dead: ['stage1-arch', 'stage1-quality', 'stage2-arch-on-quality', 'stage2-quality-on-arch', 'stage3-counter'], first: ['stage1-arch', 'stage1-quality'],
    signal: r => r.metrics && r.metrics.nullCount >= 1, signalName: 'nullCount' },
  { name: 'peer-review Tier 3', file: 'peer-review.js', full: 3,
    args: { diffPath: '/tmp/d.diff', intentContext: 'i', deep: true },
    dead: ['stage1-arch', 'stage1-quality', 'stage1-correctness', 'stage2-arch-on-peers', 'stage2-quality-on-peers', 'stage3-counter'],
    first: ['stage1-arch', 'stage1-quality', 'stage1-correctness'],
    signal: (r, lab) => r.metrics && r.metrics.nullCount >= 1 && (!lab.startsWith('stage1-') || r.reviews.length < 3), signalName: 'nullCount·reviews' },
  { name: 'peer-review Tier 2(교차 발화)', file: 'peer-review.js', full: 2,
    args: { diffPath: '/tmp/d.diff', intentContext: 'i' }, extra: { 'stage1-arch': { issues: [MAJOR] } },
    dead: ['stage1-quality', 'stage1-correctness', 'stage2-arch-on-peers', 'stage2-quality-on-peers'],
    first: ['stage1-arch', 'stage1-quality', 'stage1-correctness'],
    signal: (r, lab) => r.metrics && r.metrics.nullCount >= 1 && (!lab.startsWith('stage1-') || r.reviews.length < 3), signalName: 'nullCount·reviews' },
  { name: 'peer-review Tier 2(Lite)', file: 'peer-review.js', full: 1,
    args: { diffPath: '/tmp/d.diff', intentContext: 'i' },
    dead: ['stage1-arch', 'stage1-quality', 'stage1-correctness'], first: ['stage1-arch', 'stage1-quality', 'stage1-correctness'],
    signal: r => r.metrics && r.metrics.nullCount >= 1 && r.reviews.length < 3, signalName: 'nullCount·reviews' },
  { name: 'code-pair full', file: 'code-pair.js', full: 3,
    args: { mode: 'full', stepSpec: { id: 'S1', title: 't', goal: 'g', files: ['a.swift'], verify: { kind: 'manual', criterion: 'c' }, complexity: 3, estimatedNewBodyLines: 10 }, contextPath: '/tmp/c.md', changesetTarget: 'repo' },
    dead: ['stage2-review-arch', 'stage2-review-quality'], first: 'stage1-impl',
    signal: r => r.lensesCompleted < r.lensesExpected && !!r.residualNote && r.reviewVerdict !== 'pass', signalName: 'lensesCompleted·residualNote·verdict≠pass' },
]

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}
const brief = r => JSON.stringify({ mode: r.mode, stages: r.metrics && r.metrics.stagesCompleted, nullCount: r.metrics && r.metrics.nullCount,
  degraded: r.degraded, missingLenses: r.missingLenses, reviews: r.reviews && r.reviews.length, verdict: r.reviewVerdict, lenses: r.lensesCompleted })

;(async () => {
  for (const s of SUITES) {
    const ctl = (await run(wf(s.file), { args: s.args, responder: responder([], s.extra) })).result
    check(`${s.name} · 대조(주입 없음) → 완주 ${s.full}`, ctl.mode === 'workflow' && ctl.metrics.stagesCompleted === s.full, brief(ctl))
    for (const lab of s.dead) {
      const r = (await run(wf(s.file), { args: s.args, responder: responder([lab], s.extra) })).result
      check(`${s.name} · ${lab} null → 완주 아님(<${s.full})`, r.mode === 'fallback' || r.metrics.stagesCompleted < s.full, brief(r))
      check(`${s.name} · ${lab} null → 신호(${s.signalName})`, r.mode === 'fallback' || s.signal(r, lab), brief(r))
    }
    const firstDead = [].concat(s.first)
    const f = (await run(wf(s.file), { args: s.args, responder: responder(firstDead, s.extra) })).result
    check(`${s.name} · 첫 단계 전부 null(${firstDead.join('·')}) → fallback`, f.mode === 'fallback', brief(f))
  }
  console.log(`\n실패 주입 A(existing) ${fail ? '실패 ' + fail + '건' : '전건 통과'}`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
