// 실패 주입 A — 기존 워크플로의 렌즈별 null 이 "완주" 로 보고되지 않는다 (S24a).
//
// 대상(--scope existing): plan-lean2 · review-live · peer-review(Tier 2·3) · code-pair(full).
// 셀마다 워커 하나를 죽이고(가짜 런타임에서 null 반환) 두 가지를 본다.
//   ① 완주로 계산되지 않는다 — metrics.stagesCompleted < 그 경로의 완주 기준, 또는 mode:'fallback'
//   ② 해당 신호가 나온다 — 워크플로가 결손을 알리는 필드(degraded·missingLenses · partial·lensesCompleted · nullCount·reviews)
// 대조 셀(아무도 죽이지 않음)은 완주 기준에 도달해야 한다 — 그래야 ① 의 "미달" 이 주입 때문임을 안다.
// ⛔ 스크립트를 통째로 돌린다(tests/lib/wf_harness.js). 워커 응답은 label 로 고른 최소 객체다.
// 대상(--scope independent · S24b): R-C 속도 arm 에서 '생략' 과 '결손' 이 같은 완주로 보고되지 않는다 —
//   review-live stage2 conditional(생략 = 완주 3 · 교차 null = 완주 아님) · plan-lean2 mergeMode(생략 = degraded 아님 · 병합 null = degraded)
//   · 교차 delta(id 누락 = unreviewed · crossCoverage 보고 — agree 로 채우지 않는다).
//   런처 · 병합 · divergence 가 실패한 GPT 산출로 판정을 만들지 않는지는 tests/fixtures/gpt/failure-injection/run.sh --scope launcher 가 본다.
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const argv = process.argv.slice(2)
const scope = argv[0] === '--scope' ? argv[1] : 'existing'
if (!['existing', 'independent'].includes(scope)) {
  console.log(`UNRUN  scope '${scope}' 의 셀은 없다 — existing · independent 만 구현한다`)
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

// ── 실패 주입 B(independent) — 생략(할 일이 없어 끝남)과 결손(워커가 죽음)을 가른다 ──
async function independent() {
  const RL = wf('review-live.js'), PL = wf('plan-lean2.js')
  const f = (id, severity, line_range) => ({ id, severity, category: 'c', title: 't', detail: 'd', evidence: 'e', file: 'F.swift', line_range, discoveryAxis: 'structure' })
  const quiet = { 'stage1-arch': { findings: [f('A1', 'minor', '10-20')] }, 'stage1-quality': { findings: [f('Q1', 'minor', '15-25')] } }
  const conflict = { 'stage1-arch': { findings: [f('A1', 'major', '10-20')] }, 'stage1-quality': { findings: [f('Q1', 'minor', '15-25')] } }
  const S2 = ['stage2-arch-on-quality', 'stage2-quality-on-arch']
  const live = { diffPath: '/tmp/d.diff', intentContext: 'i', stage2: 'conditional' }

  const skip = (await run(RL, { args: live, responder: responder([], quiet) })).result
  check('review-live · conditional 트리거 생략 → stage2Skipped · 완주 3 · null 0', !!skip.stage2Skipped && skip.metrics.stagesCompleted === 3 && skip.metrics.nullCount === 0, brief(skip))
  const lost = (await run(RL, { args: live, responder: responder(S2, conflict) })).result
  check('review-live · conditional 교차 두 콜 null → stage2Skipped 없음 · 완주 아님(<3) · null 2', lost.stage2Skipped === null && lost.metrics.stagesCompleted < 3 && lost.metrics.nullCount === 2, brief(lost))
  const half = (await run(RL, { args: live, responder: responder([S2[0]], conflict) })).result
  check('review-live · conditional 교차 한 콜 null → 완주 아님(<3) · null 1', half.stage2Skipped === null && half.metrics.stagesCompleted < 3 && half.metrics.nullCount === 1, brief(half))

  const plan = { requirement: 'r', codeContextPath: '/tmp/c.md', mergeMode: 'conditional' }
  const pskip = (await run(PL, { args: plan, responder: responder([]) })).result
  check('plan-lean2 · conditional 의미 필드 전부 빔 → mergeSkipped · 완주 2 · degraded 아님', !!pskip.mergeSkipped && pskip.metrics.stagesCompleted === 2 && pskip.degraded === false, brief(pskip))
  const edge = { 'lean2-edge': { edgeCases: [{ id: 'E1', case: 'c', failureScenario: 'f', whereItBreaks: 'w' }] } }
  const pnull = (await run(PL, { args: plan, responder: responder(['lean2-merge'], edge) })).result
  check('plan-lean2 · conditional 신호 있음 + 병합 null → degraded · 완주 아님 · mergeSkipped 없음', pnull.degraded === true && pnull.metrics.stagesCompleted < 2 && !pnull.mergeSkipped, brief(pnull))

  const blank = { reviewedIds: [], adjustments: [], rejections: [], additions: [] }
  const d = (await run(RL, { args: { diffPath: '/tmp/d.diff', intentContext: 'i', crossOutput: 'delta' },
    responder: responder([], Object.assign({}, conflict, { [S2[0]]: blank, [S2[1]]: blank })) })).result
  const two = (d.findings || []).filter(x => x.id === 'A:A1' || x.id === 'Q:Q1')
  check('review-live · delta 교차가 id 를 전부 빠뜨림 → agree 아님(unreviewed) · crossCoverage 누락 보고',
    two.length === 2 && two.every(x => x.crossVerdict === 'unreviewed') && !!d.crossCoverage && d.crossCoverage.arch.length === 1 && d.crossCoverage.quality.length === 1,
    JSON.stringify({ verdicts: two.map(x => x.crossVerdict), coverage: d.crossCoverage }))
}

;(async () => {
  if (scope === 'independent') {
    await independent()
    console.log(`\n실패 주입 B(independent) ${fail ? '실패 ' + fail + '건' : '전건 통과'}`)
    process.exit(fail ? 1 : 0)
  }
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
