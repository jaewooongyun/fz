// S2 Stage2 조건부 실행 — 트리거 판정 + 제어 흐름
//
// ⛔ 로직을 **복사하지 않는다.** `workflows/peer-review.js` 의 `>>> PURE:stage2-trigger`
//    마커 블록을 런타임에 추출해 실행한다. 복사본을 두면 원본이 바뀔 때 이 테스트가
//    **과거를 검증한다** — 통과해도 현재 코드가 옳다는 근거가 되지 못한다.
//
//    Workflow 스크립트는 agent·parallel 런타임에 의존해 통째로는 불러올 수 없다.
//    그래서 의존이 없는 구간만 마커로 표시하고 그 부분만 떼어 검증한다.
//    ⚠️ 마커가 사라지면 이 테스트는 **에러로 죽는다** — 조용히 통과하지 않는다.
const fs = require('fs')
const path = require('path')

const SOURCE = path.join(__dirname, '..', '..', 'workflows', 'peer-review.js')
const BEGIN = '>>> PURE:stage2-trigger'
const END = '<<< PURE:stage2-trigger'

function extractPure() {
  const src = fs.readFileSync(SOURCE, 'utf8')
  const i = src.indexOf(BEGIN)
  const j = src.indexOf(END)
  if (i < 0 || j < 0 || j < i) {
    throw new Error(BEGIN + ' 마커를 찾을 수 없다 — 원본에서 지워졌거나 이름이 바뀌었다')
  }
  // 마커가 적힌 **줄 전체**를 제외한다 — 마커 문자열만 잘라내면 같은 줄의 남은
  // 주석 텍스트가 코드 자리로 흘러 들어와 SyntaxError 가 된다.
  return src.slice(src.indexOf('\n', i) + 1, src.lastIndexOf('\n', j))
}

const scope = {}
new Function('exports', extractPure() +
  '\nexports.stage2Trigger = stage2Trigger' +
  '\nexports.hasLocation = hasLocation' +
  '\nexports.lineSpans = lineSpans')(scope)
const { stage2Trigger, hasLocation, lineSpans } = scope

// 제어 흐름 — `peer-review.js` 의 shouldRunStage2 분기.
// ⚠️ 조건문이라 마커로 떼어낼 수 없다. 원본 분기를 바꾸면 여기도 바꾼다.
function flow(deep, fire) {
  const shouldRunStage2 = deep || fire
  if (!deep && !fire) return { tier: 2, stage2Ran: false, stage3: false }
  if (!deep) return { tier: 2, stage2Ran: shouldRunStage2, stage3: false }
  return { tier: 3, stage2Ran: shouldRunStage2, stage3: true }
}

const QUIET = [   // 렌즈 합의 + 단독 major 없음
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '10-20', severity: 'minor' }] },
  { agent: 'q', issues: [{ file: 'F.ext', line_range: '15-25', severity: 'minor' }] },
]
const CONFLICT = [ // 같은 자리, 다른 severity
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '10-20', severity: 'major' }] },
  { agent: 'q', issues: [{ file: 'F.ext', line_range: '15-25', severity: 'minor' }] },
]
const SOLO = [    // 단독 렌즈 major
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '10-20', severity: 'major' }] },
  { agent: 'q', issues: [{ file: 'G.ext', line_range: '99', severity: 'suggestion' }] },
]
const BROKEN = [  // 위치 미상 — file/line_range 없음 (R-I)
  { agent: 'a', issues: [{ severity: 'major' }, {}] },
  { agent: 'q', issues: [{ file: null, line_range: undefined, severity: 'minor' }] },
]
const MULTIRANGE = [ // 복수 구간 — min-max 로 뭉치면 41–295 가 되어 100 대가 "같은 자리"로 오판된다
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '41, 293-295', severity: 'major' }] },
  { agent: 'q', issues: [{ file: 'F.ext', line_range: '100-110', severity: 'minor' }] },
]

const t = []
const push = (n, ok, got) => t.push([n, ok, JSON.stringify(got)])

push('합의 → 미발화', stage2Trigger(QUIET).fire === false, stage2Trigger(QUIET))
push('severity 불일치 → 발화', stage2Trigger(CONFLICT).fire === true, stage2Trigger(CONFLICT))
push('단독 major → 발화', stage2Trigger(SOLO).fire === true, stage2Trigger(SOLO))

let broken
try { broken = stage2Trigger(BROKEN) } catch (e) { broken = { threw: e.message } }
push('결손 입력 → throw 없이 판정 (R-I)', !!broken && !broken.threw, broken)
// ⛔ 위치 미상 major 는 "판단 불가"이지 "단독"이 아니다 — 발화시키면 opus 2콜이 낭비된다
push('위치 미상 major → 미발화 + 별도 집계',
  broken.fire === false && broken.unlocatedMajor === 1, broken)

// ⛔ 복수 구간 병합 금지 — 41 과 293-295 사이의 100-110 은 어느 구간과도 겹치지 않는다
const multi = stage2Trigger(MULTIRANGE)
push('복수 구간을 뭉치지 않는다 → severity 불일치 0', multi.severityConflicts === 0, multi)
push('lineSpans 가 구간 목록을 낸다',
  JSON.stringify(lineSpans('41, 293-295')) === '[[41,41],[293,295]]', lineSpans('41, 293-295'))
push('hasLocation — file·line_range 둘 다 필요',
  hasLocation({ file: 'F', line_range: '1' }) === true
  && hasLocation({ file: 'F' }) === false
  && hasLocation({ line_range: '1' }) === false, 'ok')

// ⛔ 축 비교 회귀 — 실전 데이터(PR)에서 역산했다.
//    세 렌즈가 같은 자리에 **다른 축**으로 앵커하면 위치만 겹칠 뿐 의견 충돌이 아니다.
//    이 케이스가 없으면 트리거가 교차축 공존을 "불일치" 로 세어 opus 2콜을 낭비한다.
const CROSS_AXIS = [
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '23-27', severity: 'suggestion', discoveryAxis: 'structure' }] },
  { agent: 'q', issues: [{ file: 'F.ext', line_range: '23-27', severity: 'minor', discoveryAxis: 'code_quality' }] },
]
const SAME_AXIS = [
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '23-27', severity: 'suggestion', discoveryAxis: 'structure' }] },
  { agent: 'q', issues: [{ file: 'F.ext', line_range: '23-27', severity: 'minor', discoveryAxis: 'structure' }] },
]
// ⛔ unpairedMajor 는 축 무관이어야 한다 — 단독 major 는 축과 상관없이 교차가 필요하다
const CROSS_AXIS_SOLO_MAJOR = [
  { agent: 'a', issues: [{ file: 'F.ext', line_range: '10-20', severity: 'major', discoveryAxis: 'structure' }] },
  { agent: 'q', issues: [{ file: 'G.ext', line_range: '99', severity: 'suggestion', discoveryAxis: 'code_quality' }] },
]

const xa = stage2Trigger(CROSS_AXIS)
push('교차축 공존 → 불일치 0 (별건)', xa.severityConflicts === 0 && xa.fire === false, xa)
const sa = stage2Trigger(SAME_AXIS)
push('같은 축 severity 불일치 → 발화', sa.severityConflicts === 1 && sa.fire === true, sa)
const sm = stage2Trigger(CROSS_AXIS_SOLO_MAJOR)
push('⛔ 단독 major 는 축 무관하게 발화', sm.unpairedMajor === 1 && sm.fire === true, sm)
// 축이 없으면 현행 동작(겹침만 판정) — 기존 12건이 이 경로를 탄다
push('축 누락 → 겹침만 판정 (현행 유지)',
  stage2Trigger([
    { agent: 'a', issues: [{ file: 'F.ext', line_range: '1-9', severity: 'major' }] },
    { agent: 'q', issues: [{ file: 'F.ext', line_range: '5-9', severity: 'minor' }] },
  ]).severityConflicts === 1, 'ok')

const c1 = flow(false, false), c2 = flow(false, true), c3 = flow(true, false), c4 = flow(true, true)
push('케이스1 deep=F trig=F → tier2·ran F·S3 X', c1.tier === 2 && !c1.stage2Ran && !c1.stage3, c1)
push('케이스2 deep=F trig=T → tier2·ran T·S3 X', c2.tier === 2 && c2.stage2Ran && !c2.stage3, c2)
push('케이스3 deep=T trig=F → tier3·ran T·S3 O', c3.tier === 3 && c3.stage2Ran && c3.stage3, c3)
push('케이스4 deep=T trig=T → tier3·ran T·S3 O', c4.tier === 3 && c4.stage2Ran && c4.stage3, c4)

let fail = 0
for (const [n, ok, got] of t) { console.log(`${ok ? 'PASS' : 'FAIL'}  ${n}  ${got}`); if (!ok) fail++ }
console.log('')
console.log((t.length - fail) + '/' + t.length + ' 통과 (원본 마커 추출 — 복사본 아님)')
process.exit(fail ? 1 : 0)
