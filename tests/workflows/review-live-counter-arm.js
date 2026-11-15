// review-live counter 측정 arm (B11 · M2) — args.counter='off' 면 Stage 3(opus counter) 콜을 빼고 counterSkipped:'arm' 을 단다.
//
// ⛔ 기본은 'opus' 다 — 미지정 · 'opus' 는 5콜(기준선 불변). 콜 입력의 바이트 동일은 default-off-regression.js 가 본다.
// ⛔ arm 생략과 counter 실패를 다르게 보고한다 — 생략은 counterSkipped:'arm' + stagesCompleted 2 / stagesExpected 2(2/2),
//    실패(counter null)는 counterSkipped 없음 + stagesCompleted 2(기대 3 중 2).
// ⛔ 병합 동치: 같은 CounterSchema 입력이면 opus 경로의 반환과 off 경로 + scripts/counter_adapter.py merge 의 결과가 같아야
//    두 arm 의 비교가 병합 규칙 차이로 오염되지 않는다.
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준은 counter 인자를 모른다).
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'review-live.js')
const ADAPTER = path.join(ROOT, 'scripts', 'counter_adapter.py')
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }

const f = (id, severity) => ({ id, severity, category: 'c', title: 't', detail: 'd', evidence: 'e' })
const COUNTER = {
  challenges: [{ target: 'A:A1', verdict: 'refute', note: '라인 오독' }, { target: 'Q:Q1', verdict: 'uphold', note: '맞다' },
    { target: 'ok-arch', verdict: 'refute', note: '반례' }],
  missedFindings: [f('C1', 'major')],
}

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

async function go(args, { counter = COUNTER, crossConflict = false } = {}) {
  const table = {
    'stage1-arch': { findings: [f('A1', crossConflict ? 'major' : 'minor')], okAreas: ['ok-arch'] },
    'stage1-quality': { findings: [f('Q1', 'minor')], okAreas: [] },
    'stage2-arch-on-quality': { adjustments: [{ id: 'Q:Q1', verdict: 'adjust', newSeverity: 'major', note: 'n' }], additions: [] },
    'stage2-quality-on-arch': { adjustments: [], additions: [] },
    'stage3-counter': counter,
  }
  const r = await run(WF, { args: Object.assign({}, ARGS, args), responder: (p, opts) => {
    const v = table[opts.label]
    return v ? JSON.parse(JSON.stringify(v)) : null
  } })
  return { labels: r.calls.map(c => c.label), result: r.result || {} }
}
const m = o => o.result.metrics || {}
const show = o => JSON.stringify({ labels: o.labels, mode: o.result.mode, reason: o.result.reason, counterSkipped: o.result.counterSkipped, metrics: o.result.metrics })
// 키 순서와 undefined 를 걷은 비교 — JS 병합의 undefined 필드(crossNote 등)는 직렬화하면 사라진다
const canon = v => JSON.stringify(v, (k, x) => (x && typeof x === 'object' && !Array.isArray(x)
  ? Object.keys(x).sort().reduce((o, key) => (x[key] === undefined ? o : Object.assign(o, { [key]: x[key] })), {}) : x))

;(async () => {
  const unset = await go({})
  check('미지정: 5콜 · stage3-counter 포함 — 기준선 불변', unset.labels.length === 5 && unset.labels.includes('stage3-counter'), show(unset))
  check('미지정: 반환에 counterSkipped · metrics.stagesExpected 가 없다(기본 반환 모양 불변)',
    !('counterSkipped' in unset.result) && !('stagesExpected' in m(unset)) && m(unset).stagesCompleted === 3, show(unset))
  const opus = await go({ counter: 'opus' })
  check("'opus': 미지정과 같은 콜 · 같은 반환", canon(opus.labels) === canon(unset.labels) && canon(opus.result) === canon(unset.result), show(opus))

  const off = await go({ counter: 'off' })
  check("'off': 4콜 · stage3-counter 없음", off.labels.length === 4 && !off.labels.includes('stage3-counter'), show(off))
  check("'off': counterSkipped 'arm' · 기대 완주 2/2", off.result.counterSkipped === 'arm' && m(off).stagesCompleted === 2 && m(off).stagesExpected === 2, show(off))
  check("'off': findings 전부 unchallenged · C: 없음 · okAreaChallenges 빔",
    (off.result.findings || []).every(x => x.counterVerdict === 'unchallenged' && !String(x.id).startsWith('C:'))
    && (off.result.okAreaChallenges || []).length === 0, JSON.stringify(off.result.findings))
  const offCond = await go({ counter: 'off', stage2: 'conditional' })
  check("'off' + stage2 'conditional'(트리거 미발화): 2콜 · 2/2", offCond.labels.length === 2 && m(offCond).stagesCompleted === 2 && m(offCond).stagesExpected === 2, show(offCond))

  const lost = await go({}, { counter: null })
  check('기본 + counter null(실패): counterSkipped 없음 · stagesCompleted 2 · stagesExpected 없음(기대 3) — arm 생략(2/2)과 다르다',
    !('counterSkipped' in lost.result) && m(lost).stagesCompleted === 2 && !('stagesExpected' in m(lost)), show(lost))

  for (const bad of ['OFF', 'sonnet', true]) {
    const r = await go({ counter: bad })
    check(`모르는 값 ${JSON.stringify(bad)} → fallback(args invalid) · 콜 0`, r.result.mode === 'fallback' && /args invalid/.test(r.result.reason || '') && r.labels.length === 0, show(r))
  }

  // 병합 동치 — 같은 counter 입력: opus 경로 반환 == off 경로 반환 + counter_adapter merge
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-counter-arm-'))
  try {
    const R = path.join(tmp, 'result.json'), C = path.join(tmp, 'counter.json'), M = path.join(tmp, 'merged.json')
    fs.writeFileSync(R, JSON.stringify(off.result))
    fs.writeFileSync(C, JSON.stringify({ armValid: true, reason: null, counter: COUNTER }))
    execFileSync('python3', [ADAPTER, 'merge', '--result', R, '--counter', C, '--out', M], { stdio: 'pipe' })
    const merged = JSON.parse(fs.readFileSync(M, 'utf8'))
    const pick = o => ({ findings: o.findings, okAreaChallenges: o.okAreaChallenges, distribution: o.distribution })
    check('adapter-merge-parity: findings · okAreaChallenges · distribution 이 opus 경로와 같다',
      canon(pick(merged)) === canon(pick(unset.result)), `merged ${canon(pick(merged)).slice(0, 160)} · opus ${canon(pick(unset.result)).slice(0, 160)}`)
  } catch (e) {
    check('adapter-merge-parity: 어댑터 병합 실행', false, (e.stdout || e.message || '').toString().split('\n')[0])
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }

  console.log(`\nreview-live-counter-arm: ${fail ? 'FAIL' : 'PASS'}${fail ? ` (실패 ${fail}건)` : ''} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); console.log('review-live-counter-arm: FAIL'); process.exit(1) })
