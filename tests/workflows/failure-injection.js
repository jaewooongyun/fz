// 실패 주입 A — 기존 워크플로의 렌즈별 null 이 "완주" 로 보고되지 않는다 (S24a).
//
// 대상(--scope existing): plan-lean2 · review-live · peer-review(Tier 2·3) · code-pair(full).
// 셀마다 워커 하나를 죽이고(가짜 런타임에서 null 반환) 두 가지를 본다.
//   ① 완주로 계산되지 않는다 — metrics.stagesCompleted < 그 경로의 완주 기준, 또는 mode:'fallback'
//   ② 해당 신호가 나온다 — 워크플로가 결손을 알리는 필드(degraded·missingLenses · partial·lensesCompleted · nullCount·reviews)
// 대조 셀(아무도 죽이지 않음)은 완주 기준에 도달해야 한다 — 그래야 ① 의 "미달" 이 주입 때문임을 안다.
// throw 셀: 같은 워커가 null 을 돌려주는 대신 **던진다**(스폰 예외). 워크플로는 그것을 null 워커로 접는다 —
//   run 이 reject 하지 않고 · nullCount ≥ 1(음수 아님) · 던진 사유가 로그에 남는다. 기존 묶음은 null 셀과 같은 미달 · 신호도 본다.
//   ⛔ 신호만 보면 접지 않아도 통과한다 — 하네스 parallel 이 던진 자리를 null 로 돌려줘 미달 신호는 그대로 나온다. 그래서 nullCount 를 본다.
//   discover-adversarial(lean · deep) · plan-collaborative · search-cross-verify 는 throw 셀만 둔다(throwOnly — null 셀은 이 묶음의 범위가 아니다).
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
  // search-cross-verify
  'stage1-symbolic': { findings: [] }, 'stage1-pattern': { findings: [] },
  'stage2-sym-on-pat': { verdicts: [], additions: [] }, 'stage2-pat-on-sym': { verdicts: [], additions: [] },
  'stage3-merge': { merged: [] },
  // plan-collaborative
  'stage0-direction': { verdict: 'PROCEED', alternatives: [], concerns: [] },
  'stage1-draft': { steps: [], readScope: [], assumptions: [] },
  'stage2-impact': { impactFiles: [], hiddenDependencies: [], deadCode: [] },
  'stage2-edge': { edgeCases: [] },
  'stage2-arch': { patternVerdicts: [], violations: [] },
  'stage3-impact-on-edge': { links: [], additions: [] }, 'stage3-edge-on-impact': { links: [], additions: [] },
  'stage4-integrate': { steps: [], writeScope: [], rtm: [] },
  'stage5-recheck': { remainingIssues: [], verdict: 'pass' },
  // discover-adversarial (lean · deep)
  'r1-paths': { paths: [{ id: 'P1' }] }, 'cost:r1': { costs: [] }, 'r2-paths': { paths: [{ id: 'P2' }] }, 'cost:r2': { costs: [] },
  'lens:reuse-first': { paths: [{ id: 'L1' }] }, 'lens:greenfield': { paths: [{ id: 'L2' }] }, 'lens:hybrid': { paths: [{ id: 'L3' }] },
  'merge': { paths: [{ id: 'M1' }] }, 'cost:deep-0': { costs: [] },
  'landscape': { tradeoffs: [], openQuestions: [] },
}
const THROWN = 'injected spawn failure'
const responder = (dead, extra = {}, thrown = []) => (prompt, opts) => {
  if (thrown.includes(opts.label)) throw new Error(THROWN)
  return dead.includes(opts.label) ? null : JSON.parse(JSON.stringify(Object.assign({}, RESP[opts.label], extra[opts.label] || {})))
}

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
  // throw 셀만 두는 묶음 — done 은 그 워크플로의 완주 수(대조 셀용)
  { name: 'search-cross-verify', file: 'search-cross-verify.js', full: 3, throwOnly: true,
    args: { query: 'q', codeContext: '/tmp' }, dead: ['stage1-symbolic', 'stage2-sym-on-pat', 'stage3-merge'] },
  { name: 'plan-collaborative', file: 'plan-collaborative.js', full: 5, throwOnly: true,
    args: { requirement: 'r', codeContextPath: '/tmp/c.md' },
    dead: ['stage0-direction', 'stage1-draft', 'stage2-edge', 'stage3-impact-on-edge', 'stage4-integrate', 'stage5-recheck'] },
  { name: 'discover-adversarial lean', file: 'discover-adversarial.js', full: 2, throwOnly: true, done: r => r.metrics.roundsCompleted,
    args: { problem: 'p', codeContextPath: '/tmp/c.md' }, dead: ['r1-paths', 'cost:r1', 'r2-paths', 'landscape'] },
  { name: 'discover-adversarial deep', file: 'discover-adversarial.js', full: 2, throwOnly: true, done: r => r.metrics.roundsCompleted,
    args: { problem: 'p', codeContextPath: '/tmp/c.md', deep: true }, dead: ['lens:greenfield', 'merge', 'cost:deep-0', 'landscape'] },
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
    const done = s.done || (r => r.metrics.stagesCompleted)
    const ctl = (await run(wf(s.file), { args: s.args, responder: responder([], s.extra) })).result
    check(`${s.name} · 대조(주입 없음) → 완주 ${s.full}`, ctl.mode === 'workflow' && done(ctl) === s.full, brief(ctl))
    // throw 셀 — 셀마다 따로 잡는다: run 이 reject 하면 그 셀만 FAIL 이고 나머지는 계속 돈다
    for (const lab of [...new Set(s.dead.concat(s.throwOnly ? [] : s.first))]) {
      let out = null, err = null
      try { out = await run(wf(s.file), { args: s.args, responder: responder([], s.extra, [lab]) }) } catch (e) { err = e }
      const r = out && out.result, m = (r && r.metrics) || {}
      const short = !!r && (s.throwOnly || r.mode === 'fallback' || (done(r) < s.full && s.signal(r, lab)))
      check(`${s.name} · ${lab} throw → reject 없이 반환 · nullCount ≥ 1 · 사유가 로그에${s.throwOnly ? '' : ' · null 셀과 같은 미달 · 신호'}`,
        !err && short && m.nullCount >= 1 && m.agentCalls >= 1 && out.logs.some(l => l.includes(THROWN)),
        err ? `reject — ${err.message}` : brief(r))
    }
    if (s.throwOnly) continue
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
