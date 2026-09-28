// review-live Stage 2 조건부 arm (S19) — args.stage2='conditional' 에서 D1 트리거가 미발화이고 위치 미상 major 가 없을 때만 교차 2콜을 생략한다.
//
// ⛔ 기본은 always 다 — 미지정 · 'always' 는 트리거와 무관하게 5콜(기준선 불변). 콜 입력의 바이트 동일은 default-off-regression.js 가 본다.
// ⛔ 위치 미상 major 는 발화시킨다(fail-open) — 기본 스키마 finding 에는 line_range 가 없다.
// ⛔ 트리거 생략과 교차 콜 결손은 다르게 보고한다 — 생략은 stage2Skipped + 완주 3, 결손은 stage2Skipped null + 완주 2.
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준은 stage2 를 모른다).
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'review-live.js')
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }
const S2 = ['stage2-arch-on-quality', 'stage2-quality-on-arch']

const f = (id, severity, loc) => Object.assign({ id, severity, category: 'c', title: 't', detail: 'd', evidence: 'e' }, loc || {})
const at = (file, line_range, discoveryAxis) => ({ file, line_range, discoveryAxis })
const QUIET = [[f('A1', 'minor', at('F.swift', '10-20', 'structure'))], [f('Q1', 'minor', at('F.swift', '15-25', 'structure'))]]
const CONFLICT = [[f('A1', 'major', at('F.swift', '10-20', 'structure'))], [f('Q1', 'minor', at('F.swift', '15-25', 'structure'))]]
const SOLO = [[f('A1', 'major', at('F.swift', '10-20', 'structure'))], [f('Q1', 'suggestion', at('G.swift', '99', 'code_quality'))]]
const UNLOCATED = [[f('A1', 'major')], []]                 // 기본 스키마 — line_range 없는 major 1건
const PLAIN_MINOR = [[f('A1', 'minor')], [f('Q1', 'suggestion')]]   // 기본 스키마 · major 없음

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

async function go(args, [a, q], { crossNull = false } = {}) {
  const table = {
    'stage1-arch': a && { findings: a, okAreas: ['ok'] },
    'stage1-quality': q && { findings: q, okAreas: [] },
    'stage2-arch-on-quality': crossNull ? null : { adjustments: [], additions: [] },
    'stage2-quality-on-arch': crossNull ? null : { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedFindings: [] },
  }
  const r = await run(WF, { args: Object.assign({}, ARGS, args), responder: (p, opts) => {
    const v = table[opts.label]
    return v ? JSON.parse(JSON.stringify(v)) : null
  } })
  return { labels: r.calls.map(c => c.label), result: r.result || {} }
}
const crossed = o => S2.every(l => o.labels.includes(l))
const noCross = o => !S2.some(l => o.labels.includes(l))
const countered = o => o.labels.includes('stage3-counter')
const done = o => o.result.metrics && o.result.metrics.stagesCompleted
const show = o => JSON.stringify({ labels: o.labels, stage2Ran: o.result.stage2Ran, trigger: o.result.stage2Trigger, skipped: o.result.stage2Skipped, done: done(o) })

;(async () => {
  const unset = await go({}, QUIET)
  check('미지정: 트리거 미발화여도 5콜 — 기준선 불변', unset.labels.length === 5 && crossed(unset) && countered(unset), show(unset))
  check('미지정: 반환에 stage2Ran · stage2Trigger · stage2Skipped 가 없다(기본 반환 모양 불변)',
    ['stage2Ran', 'stage2Trigger', 'stage2Skipped'].every(k => !(k in unset.result)), JSON.stringify(Object.keys(unset.result)))
  const always = await go({ stage2: 'always' }, QUIET)
  check("'always': 트리거 미발화여도 5콜", always.labels.length === 5 && crossed(always), show(always))

  const quiet = await go({ stage2: 'conditional' }, QUIET)
  check('conditional + QUIET: 교차 0콜 · counter 는 돈다(3콜)', quiet.labels.length === 3 && noCross(quiet) && countered(quiet), show(quiet))
  check('conditional + QUIET: stage2Ran false · stage2Trigger.fire false · stage2Skipped.reason',
    quiet.result.stage2Ran === false && quiet.result.stage2Trigger && quiet.result.stage2Trigger.fire === false
    && !!(quiet.result.stage2Skipped && quiet.result.stage2Skipped.reason), show(quiet))
  check('conditional + QUIET: 생략은 완주로 센다(3)', done(quiet) === 3, show(quiet))

  const conflict = await go({ stage2: 'conditional' }, CONFLICT)
  check('conditional + 같은 자리·같은 축 severity 이견: 교차 실행', crossed(conflict) && conflict.result.stage2Trigger.severityConflicts === 1
    && conflict.result.stage2Skipped === null && conflict.result.stage2Ran === true, show(conflict))
  const solo = await go({ stage2: 'conditional' }, SOLO)
  check('conditional + 단독 major: 교차 실행', crossed(solo) && solo.result.stage2Trigger.unpairedMajor === 1, show(solo))
  const unloc = await go({ stage2: 'conditional' }, UNLOCATED)
  check('conditional + line_range 없는 major 1건: 트리거는 미발화지만 교차 실행(fail-open)',
    crossed(unloc) && unloc.result.stage2Trigger.fire === false && unloc.result.stage2Trigger.unlocatedMajor === 1
    && unloc.result.stage2Skipped === null, show(unloc))
  const plain = await go({ stage2: 'conditional' }, PLAIN_MINOR)
  check('conditional + 기본 스키마 · major 없음: 생략', noCross(plain) && countered(plain) && !!plain.result.stage2Skipped, show(plain))

  // 결손과 생략을 가른다 — 교차를 돌렸는데 둘 다 null 이면 stage2Ran false(응답 기준 — peer-review 와 같은 식) · stage2Skipped null · 완주 2
  const lost = await go({ stage2: 'conditional' }, CONFLICT, { crossNull: true })
  check('conditional + 교차 콜 결손: stage2Ran false(응답 없음) · stage2Skipped null · 완주 2 — 생략(stage2Skipped · 완주 3)과 다르다',
    crossed(lost) && lost.result.stage2Ran === false && lost.result.stage2Skipped === null && done(lost) === 2, show(lost))
  // 렌즈 하나가 죽으면 기준과 같이 교차 없이 간다 — 트리거는 판정하지 않는다
  const half = await go({ stage2: 'conditional' }, [null, QUIET[1]])
  check('conditional + arch null: 교차 없음 · stage2Trigger null · stage2Skipped null · counter 는 돈다',
    noCross(half) && countered(half) && half.result.stage2Trigger === null && half.result.stage2Skipped === null && half.result.stage2Ran === false, show(half))

  console.log(`\nreview-live Stage 2 arm ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
