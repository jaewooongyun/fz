// 교차 판정 병합 — 한 finding 이 두 렌즈에게 판정받는 경우
//
// ⛔ 로직을 복사하지 않는다. `workflows/peer-review.js` 의 `>>> PURE:cross-merge` 블록을
//    런타임 추출해 실행한다. 마커가 사라지면 이 테스트는 **죽는다**(조용히 통과 X).
//
// 막는 회귀: `map[a.id] = a` 로 덮어쓰면 **concat 순서가 판정을 정한다.** correctness issue 는
// arch·quality 양쪽 교차 입력에 들어가므로 두 판정이 같은 id 로 온다 — 뒤에 온 것이
// 앞의 것을 조용히 지운다. 같은 입력을 순서만 바꿔 넣고 결과가 같은지 본다.
const fs = require('fs')
const path = require('path')

const SOURCE = path.join(__dirname, '..', '..', 'workflows', 'peer-review.js')
const BEGIN = '>>> PURE:cross-merge'
const END = '<<< PURE:cross-merge'

const src = fs.readFileSync(SOURCE, 'utf8')
const i = src.indexOf(BEGIN)
const j = src.indexOf(END)
if (i < 0 || j < 0 || j < i) {
  throw new Error(BEGIN + ' 마커를 찾을 수 없다 — 원본에서 지워졌거나 이름이 바뀌었다')
}
const scope = {}
new Function('exports', src.slice(src.indexOf('\n', i) + 1, src.lastIndexOf('\n', j)) +
  '\nexports.crossIndex = crossIndex\nexports.crossFields = crossFields')(scope)
const { crossIndex, crossFields } = scope

const A = (id, verdict, newSeverity, note) => ({ id, verdict, newSeverity, note })
const res = (...adjustments) => ({ adjustments })

const t = []
const push = (n, ok, got) => t.push([n, ok, JSON.stringify(got)])

// ── 단일 판정 ──
let idx = crossIndex([{ by: 'arch', result: res(A('Q:1', 'adjust', 'critical', 'n')) }, { by: 'quality', result: null }])
push('단일 adjust → crossSeverity 반영',
  crossFields(idx['Q:1']).crossVerdict === 'adjust' && crossFields(idx['Q:1']).crossSeverity === 'critical',
  crossFields(idx['Q:1']))
push('판정 없음 → unreviewed', crossFields(idx['없는id']).crossVerdict === 'unreviewed', crossFields(undefined))
push('adjust 아니면 crossSeverity 없음',
  crossFields([A('X', 'agree', 'critical')]).crossSeverity === undefined, crossFields([A('X', 'agree', 'critical')]))

// ── 두 판정: 일치 ──
const agreeIdx = crossIndex([
  { by: 'arch', result: res(A('C:1', 'adjust', 'minor', 'arch 근거')) },
  { by: 'quality', result: res(A('C:1', 'adjust', 'critical', 'quality 근거')) },
])
const agreed = crossFields(agreeIdx['C:1'])
// ⛔ 낮은 쪽을 고르면 두 렌즈가 동의했는데 결과가 완화된다
push('판정 일치 → 더 심한 severity', agreed.crossVerdict === 'adjust' && agreed.crossSeverity === 'critical', agreed)
push('판정 일치 → note 에 렌즈 둘 다', /arch/.test(agreed.crossNote) && /quality/.test(agreed.crossNote), agreed.crossNote)

// ── 두 판정: 갈림 ──
const splitIdx = crossIndex([
  { by: 'arch', result: res(A('C:2', 'false_positive', undefined, 'base 에 이미 있음')) },
  { by: 'quality', result: res(A('C:2', 'adjust', 'major', '성능 영향 있음')) },
])
const split = crossFields(splitIdx['C:2'])
push('판정 갈림 → contested', split.crossVerdict === 'contested', split.crossVerdict)
// ⛔ 갈렸을 때 severity 를 확정하면 Lead 가 못 본 사이에 조정이 굳는다
push('contested → crossSeverity 없음 (원본 유지)', split.crossSeverity === undefined, split.crossSeverity)
push('contested → 원본 판정 2건 보존',
  Array.isArray(split.crossVerdicts) && split.crossVerdicts.length === 2, split.crossVerdicts)
push('contested → 렌즈 이름이 남는다',
  split.crossVerdicts.map(v => v.by).sort().join(',') === 'arch,quality',
  split.crossVerdicts.map(v => v.by))

// ── ⛔ 핵심: 순서 무관 ──
const flipped = crossFields(crossIndex([
  { by: 'quality', result: res(A('C:2', 'adjust', 'major', '성능 영향 있음')) },
  { by: 'arch', result: res(A('C:2', 'false_positive', undefined, 'base 에 이미 있음')) },
])['C:2'])
push('⛔ 순서를 바꿔도 verdict 동일 (덮어쓰기 없음)', flipped.crossVerdict === split.crossVerdict,
  { 정순: split.crossVerdict, 역순: flipped.crossVerdict })
push('⛔ 순서를 바꿔도 판정 2건 보존', flipped.crossVerdicts.length === 2, flipped.crossVerdicts.length)

// ── 결손 입력 ──
push('result null 인 source 는 건너뛴다',
  Object.keys(crossIndex([{ by: 'arch', result: null }, null])).length === 0,
  crossIndex([{ by: 'arch', result: null }, null]))

let fail = 0
for (const [n, ok, got] of t) { console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}  ${got}`); if (!ok) fail++ }
console.log('')
console.log((t.length - fail) + '/' + t.length + ' 통과 (원본 마커 추출)')
process.exit(fail ? 1 : 0)
