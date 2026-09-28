// 교차 delta arm (S19b) — args.crossOutput='delta' 에서 교차 워커가 동의를 id 로만 내도 병합 판정이 full 과 같다.
//
// ⛔ 병합 코드는 바뀌지 않는다 — PURE:cross-delta 의 expandCrossDelta 가 delta 를 full 모양으로 편다. 이 테스트는 세 층을 본다.
//    ① 펴기 함수 단위 판정(peer-review 원본 블록을 추출해 실행) ② review-live 사본이 원본과 글자까지 같다
//    ③ 두 워크플로를 harness 로 full · delta 각각 돌려 판정이 같다(peer-review Tier 2 발화 · Tier 3 deep · review-live)
// ⛔ 동치 범위: 판정 필드(finalSeverity · crossVerdict · crossSeverity · 갈린 판정 목록 · counterVerdict)와 adjust · false_positive 의 note.
//    agree 의 note 는 delta 가 버린다(출력을 줄이는 몫) — 비교하지 않는다.
// ⛔ reviewedIds 에서 빠진 id 는 agree 가 되면 안 된다 — unreviewed 로 남고 crossCoverage 에 보고된다(전수 확인 보존).
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준은 crossOutput 을 모른다).
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const BEGIN = '>>> PURE:cross-delta'
const END = '<<< PURE:cross-delta'

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

function blockOf(file) {
  const src = fs.readFileSync(file, 'utf8')
  const i = src.indexOf(BEGIN), j = src.indexOf(END)
  if (i < 0 || j < 0 || j < i) return null
  return src.slice(src.lastIndexOf('\n', i) + 1, src.indexOf('\n', j))
}

// ── ① · ② 펴기 함수와 사본 동일성 ──
const orig = blockOf(path.join(ROOT, 'workflows', 'peer-review.js'))
const copy = blockOf(path.join(ROOT, 'workflows', 'review-live.js'))
check('peer-review 에 PURE:cross-delta 블록이 있다', orig !== null, '마커 없음')
check('review-live 사본 == peer-review 원본 (마커 줄 포함 전문)', orig !== null && copy !== null && orig === copy,
  copy === null ? 'review-live 에 마커 없음' : `원본 ${orig ? orig.length : 0}자 · 사본 ${copy.length}자`)
if (orig) {
  const scope = {}
  new Function('exports', `${orig}\nexports.expandCrossDelta = expandCrossDelta`)(scope)
  const X = scope.expandCrossDelta
  const e1 = X({ reviewedIds: ['a', 'b', 'c'], adjustments: [{ id: 'b', newSeverity: 'critical', note: 'nb' }],
    rejections: [{ id: 'c', note: 'nc' }], additions: [{ id: 'n' }] }, ['a', 'b', 'c'])
  check('펴기: 동의 · 조정 · 기각 → agree · adjust · false_positive',
    JSON.stringify(e1.result.adjustments) === JSON.stringify([{ id: 'a', verdict: 'agree' },
      { id: 'b', verdict: 'adjust', newSeverity: 'critical', note: 'nb' }, { id: 'c', verdict: 'false_positive', note: 'nc' }])
    && e1.missing.length === 0 && e1.result.additions.length === 1, JSON.stringify(e1))
  const e2 = X({ reviewedIds: ['a'], adjustments: [{ id: 'b', newSeverity: 'minor', note: 'n' }], rejections: [], additions: [] }, ['a', 'b', 'd'])
  check('펴기: reviewedIds 에 없는 id 는 missing — agree 로 채우지 않는다',
    JSON.stringify(e2.missing) === '["d"]' && !e2.result.adjustments.some(x => x.id === 'd'), JSON.stringify(e2))
  check('펴기: 조정한 id 는 reviewedIds 에 없어도 확인한 것이다', !e2.missing.includes('b'), JSON.stringify(e2.missing))
  const e3 = X({ reviewedIds: ['a', 'a', 'b'], adjustments: [], rejections: [{ id: 'b', note: 'n' }], additions: [] }, ['a', 'b'])
  check('펴기: 중복 id 는 한 번 · 기각한 id 는 agree 와 겹치지 않는다',
    e3.result.adjustments.filter(x => x.id === 'a').length === 1
    && e3.result.adjustments.filter(x => x.id === 'b').map(x => x.verdict).join() === 'false_positive', JSON.stringify(e3.result.adjustments))
  const e4 = X(null, ['a'])
  check('펴기: 렌즈 결손(null) → result null · missing null', e4.result === null && e4.missing === null, JSON.stringify(e4))
  let e5
  try { e5 = X({ adjustments: [] }, ['a']) } catch (err) { e5 = { threw: err.message } }
  check('펴기: 필드가 빠져도 throw 없이 편다(전부 missing)', !!e5 && !e5.threw && JSON.stringify(e5.missing) === '["a"]', JSON.stringify(e5))
}

// ── ③ harness 동치 ──
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }
const PR_ISSUE = (id, severity, file, line_range) => ({ id, file, line_range, severity, perspective: 'p', discoveryAxis: 'structure',
  origin: 'regression', description: 'd', evidence: 'e', confidence: 90 })
const RL_FINDING = (id, severity) => ({ id, severity, category: 'c', title: 't', detail: 'd', evidence: 'e' })
const adj = (id, verdict, newSeverity, note) => ({ id, verdict, newSeverity, note })

// peer-review — 교차 입력: arch 는 Q:Q1 · Q:Q2 · C:C1, quality 는 A:A1 · C:C1 을 본다. C:C1 은 두 렌즈가 갈린다(contested)
const PR = {
  stage1: {
    'stage1-arch': { issues: [PR_ISSUE('A1', 'major', 'F.swift', '10-20')], strengths: [], overall_assessment: 'o' },
    'stage1-quality': { issues: [PR_ISSUE('Q1', 'minor', 'F.swift', '15-25'), PR_ISSUE('Q2', 'minor', 'G.swift', '5')], strengths: [], overall_assessment: 'o' },
    'stage1-correctness': { issues: [PR_ISSUE('C1', 'major', 'H.swift', '1')], strengths: [], overall_assessment: 'o' },
    'stage3-counter': { challenges: [], missedIssues: [] },
  },
  full: {
    'stage2-arch-on-peers': { adjustments: [adj('Q:Q1', 'agree', undefined, 'arch 동의'), adj('Q:Q2', 'adjust', 'major', 'arch 조정'),
      adj('C:C1', 'false_positive', undefined, 'arch 기각')], additions: [PR_ISSUE('X1', 'minor', 'K.swift', '3')] },
    'stage2-quality-on-peers': { adjustments: [adj('A:A1', 'adjust', 'critical', 'quality 조정'), adj('C:C1', 'agree', undefined, 'quality 동의')], additions: [] },
  },
  delta: {
    'stage2-arch-on-peers': { reviewedIds: ['Q:Q1', 'Q:Q2', 'C:C1'], adjustments: [{ id: 'Q:Q2', newSeverity: 'major', note: 'arch 조정' }],
      rejections: [{ id: 'C:C1', note: 'arch 기각' }], additions: [PR_ISSUE('X1', 'minor', 'K.swift', '3')] },
    'stage2-quality-on-peers': { reviewedIds: ['A:A1', 'C:C1'], adjustments: [{ id: 'A:A1', newSeverity: 'critical', note: 'quality 조정' }], rejections: [], additions: [] },
  },
}
// review-live — arch 는 Q:Q1 · Q:Q2, quality 는 A:A1 을 본다
const RL = {
  stage1: {
    'stage1-arch': { findings: [RL_FINDING('A1', 'major')], okAreas: ['ok'] },
    'stage1-quality': { findings: [RL_FINDING('Q1', 'minor'), RL_FINDING('Q2', 'minor')], okAreas: [] },
    'stage3-counter': { challenges: [], missedFindings: [] },
  },
  full: {
    'stage2-arch-on-quality': { adjustments: [adj('Q:Q1', 'agree', undefined, 'arch 동의'), adj('Q:Q2', 'false_positive', undefined, 'arch 기각')],
      additions: [RL_FINDING('X1', 'minor')] },
    'stage2-quality-on-arch': { adjustments: [adj('A:A1', 'adjust', 'critical', 'quality 조정')], additions: [] },
  },
  delta: {
    'stage2-arch-on-quality': { reviewedIds: ['Q:Q1', 'Q:Q2'], adjustments: [], rejections: [{ id: 'Q:Q2', note: 'arch 기각' }], additions: [RL_FINDING('X1', 'minor')] },
    'stage2-quality-on-arch': { reviewedIds: ['A:A1'], adjustments: [{ id: 'A:A1', newSeverity: 'critical', note: 'quality 조정' }], rejections: [], additions: [] },
  },
}

async function go(wf, fx, mode, extraArgs, patch) {
  const table = Object.assign({}, fx.stage1, mode === 'delta' ? fx.delta : fx.full, patch || {})
  const cross = []
  const r = await run(path.join(ROOT, 'workflows', `${wf}.js`), {
    args: Object.assign({}, ARGS, extraArgs, mode === 'delta' ? { crossOutput: 'delta' } : {}),
    responder: (prompt, opts) => {
      if (/^stage2-/.test(opts.label)) cross.push({ prompt, schema: opts.schema })
      return table[opts.label] ? JSON.parse(JSON.stringify(table[opts.label])) : null
    },
  })
  const result = r.result || {}
  return { result, cross, items: result.issues || result.findings || [] }
}
const decide = items => JSON.stringify(items.map(f => ({
  id: f.id, severity: f.severity, finalSeverity: f.finalSeverity, crossVerdict: f.crossVerdict, crossSeverity: f.crossSeverity,
  crossVerdicts: f.crossVerdicts && f.crossVerdicts.map(v => `${v.by}:${v.verdict}:${v.newSeverity || ''}`),
  counterVerdict: f.counterVerdict,
  note: f.crossVerdict === 'adjust' || f.crossVerdict === 'false_positive' ? f.crossNote : undefined,
})).sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)))
const verdictOf = (o, id) => (o.items.find(f => f.id === id) || {}).crossVerdict
const usesDelta = o => o.cross.length === 2 && o.cross.every(c => c.schema && c.schema.properties && c.schema.properties.reviewedIds && /\[응답 모양 — delta\]/.test(c.prompt))

const CASES = [
  { name: 'peer-review Tier 2 · 트리거 발화', wf: 'peer-review', fx: PR, args: {}, expect: ['adjust', 'agree', 'contested', 'unreviewed'], omit: ['stage2-arch-on-peers', 'Q:Q1'] },
  { name: 'peer-review Tier 3 · deep', wf: 'peer-review', fx: PR, args: { deep: true }, expect: ['adjust', 'agree', 'contested', 'unreviewed'], omit: ['stage2-arch-on-peers', 'Q:Q1'] },
  { name: 'review-live', wf: 'review-live', fx: RL, args: {}, expect: ['adjust', 'agree', 'false_positive', 'unreviewed'], omit: ['stage2-arch-on-quality', 'Q:Q1'] },
]

;(async () => {
  for (const c of CASES) {
    const full = await go(c.wf, c.fx, 'full', c.args)
    const delta = await go(c.wf, c.fx, 'delta', c.args)
    const seen = [...new Set(full.items.map(f => f.crossVerdict))].sort()
    check(`${c.name}: full 결과에 판정 종류가 다 있다(동치가 공허하지 않다) — ${c.expect.join('·')}`,
      JSON.stringify(seen) === JSON.stringify(c.expect), JSON.stringify(seen))
    check(`${c.name}: 미지정은 full — delta 스키마 · 응답 모양 줄이 없고 crossCoverage 키도 없다`,
      full.cross.length === 2 && !full.cross.some(x => x.schema && x.schema.properties && x.schema.properties.reviewedIds)
      && !('crossCoverage' in full.result), JSON.stringify({ cross: full.cross.length, keys: Object.keys(full.result) }))
    check(`${c.name}: delta 는 교차 두 콜에 delta 스키마 · 응답 모양 줄을 쓴다`, usesDelta(delta), `교차 ${delta.cross.length}콜`)
    check(`${c.name}: delta 병합 판정 == full`, decide(delta.items) === decide(full.items), `\n    full  ${decide(full.items)}\n    delta ${decide(delta.items)}`)
    check(`${c.name}: delta crossCoverage 누락 0`, !!delta.result.crossCoverage && delta.result.crossCoverage.arch.length === 0
      && delta.result.crossCoverage.quality.length === 0, JSON.stringify(delta.result.crossCoverage))

    // 전수 확인 보존 — arch 가 reviewedIds 에서 id 하나를 빠뜨린다
    const [label, gone] = c.omit
    const dropped = JSON.parse(JSON.stringify(c.fx.delta[label]))
    dropped.reviewedIds = dropped.reviewedIds.filter(id => id !== gone)
    const miss = await go(c.wf, c.fx, 'delta', c.args, { [label]: dropped })
    check(`${c.name}: reviewedIds 에서 빠진 ${gone} 은 agree 가 아니라 unreviewed · crossCoverage 에 보고`,
      verdictOf(miss, gone) === 'unreviewed' && !!miss.result.crossCoverage && JSON.stringify(miss.result.crossCoverage.arch) === JSON.stringify([gone]),
      JSON.stringify({ verdict: verdictOf(miss, gone), coverage: miss.result.crossCoverage }))
  }
  console.log(`\n교차 delta arm ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
