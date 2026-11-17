// D6 카운터 시맨틱 — nullCount = **잔존 null** (시도 횟수 아님)
//
// ⛔ 로직을 **복사하지 않는다.** `workflows/peer-review.js` 의 `>>> PURE:null-count`
//    마커 블록을 런타임에 추출해 실행한다. 이전 판은 복사본을 검증했고, 그래서 원본의
//    `nullCalls -= 1` 을 부숴도 4/4 로 통과했다 — 뮤테이션으로 실증된 위음성이다.
//    형제 `s2-stage2-trigger.js` · `s2-cross-merge.js` 가 쓰는 패턴을 따른다.
//
//    Workflow 스크립트는 agent·parallel 런타임에 의존해 통째로는 못 불러온다. 마커 블록의
//    외부 의존은 agent·log·parallel 셋뿐이라 주입으로 해결한다.
//    ⚠️ 마커가 사라지면 이 테스트는 **에러로 죽는다** — 조용히 통과하지 않는다.
// ⛔ 스텁은 런타임 의미를 따른다(tests/lib/wf_harness.js 와 같다): parallel 은 던진 thunk 의 자리를 null 로 돌려주고
//    reject 하지 않는다. 스텁 agent 는 seqs 값이 Error 면 그것을 던진다 — callAgent 가 예외를 null 로 세지 않으면
//    재시도의 취소(`nullCalls -= 1`)가 세지 않은 null 을 빼서 nullCount 가 음수가 된다(케이스 4 · 5).
const fs = require('fs')
const path = require('path')

const SOURCE = path.join(__dirname, '..', '..', 'workflows', 'peer-review.js')
const BEGIN = '>>> PURE:null-count'
const END = '<<< PURE:null-count'

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

const PURE = extractPure()
if (!/nullCalls\s*-=\s*1/.test(PURE) || !/async function parallelWithRetry/.test(PURE)) {
  throw new Error('마커 블록에 검증 대상이 없다 — 범위가 어긋났다 (조용한 통과 방지)')
}

// 케이스마다 **새로** 평가한다 — 카운터가 모듈 스코프 `let` 이라 상태가 이월된다.
function freshHarness(seqs) {
  const scope = {}
  const agent = async (prompt) => {
    if (!(prompt in seqs)) throw new Error('스텁에 없는 프롬프트: ' + prompt)
    const v = seqs[prompt].shift()
    if (v instanceof Error) throw v
    return v
  }
  scope.logs = []
  const log = m => { scope.logs.push(String(m)) }
  const parallel = async (thunks) => Promise.all(thunks.map(t => Promise.resolve().then(t).catch(() => null)))
  new Function('agent', 'log', 'parallel', 'exports', PURE +
    '\nexports.callAgent = callAgent' +
    '\nexports.parallelWithRetry = parallelWithRetry' +
    '\nexports.metrics = metrics')(agent, log, parallel, scope)
  return scope
}

const run = async () => {
  // 케이스 1: 첫 시도 null → 재시도 성공  ⇒ 잔존 null 0, 호출수는 4 로 유지
  let h = freshHarness({ a: [null, 'OK'], b: ['B'], c: ['C'] })
  await h.parallelWithRetry([
    () => h.callAgent('a', { label: 'a' }),
    () => h.callAgent('b', { label: 'b' }),
    () => h.callAgent('c', { label: 'c' }),
  ])
  const c1 = h.metrics(1)

  // 케이스 2: 첫 시도 null → 재시도도 null ⇒ 잔존 null 1 (이중 계상 없음)
  h = freshHarness({ a: [null, null], b: ['B'], c: ['C'] })
  await h.parallelWithRetry([
    () => h.callAgent('a', { label: 'a' }),
    () => h.callAgent('b', { label: 'b' }),
    () => h.callAgent('c', { label: 'c' }),
  ])
  const c2 = h.metrics(1)

  // 케이스 3: 무장애 ⇒ 잔존 null 0, 호출수 3
  h = freshHarness({ a: ['A'], b: ['B'], c: ['C'] })
  await h.parallelWithRetry([
    () => h.callAgent('a', { label: 'a' }),
    () => h.callAgent('b', { label: 'b' }),
    () => h.callAgent('c', { label: 'c' }),
  ])
  const c3 = h.metrics(1)

  // 케이스 4: 첫 시도가 던짐 → 재시도 성공 ⇒ 잔존 null 0, 호출수 4 (예외도 null 워커로 센 뒤 취소된다)
  const boom = () => new Error('spawn exploded')
  h = freshHarness({ a: [boom(), 'OK'], b: ['B'], c: ['C'] })
  const out4 = await h.parallelWithRetry([
    () => h.callAgent('a', { label: 'a' }),
    () => h.callAgent('b', { label: 'b' }),
    () => h.callAgent('c', { label: 'c' }),
  ])
  const c4 = h.metrics(1), logs4 = h.logs

  // 케이스 5: 첫 시도도 재시도도 던짐 ⇒ 잔존 null 1 (음수 아님 · 이중 계상 없음)
  h = freshHarness({ a: [boom(), boom()], b: ['B'], c: ['C'] })
  await h.parallelWithRetry([
    () => h.callAgent('a', { label: 'a' }),
    () => h.callAgent('b', { label: 'b' }),
    () => h.callAgent('c', { label: 'c' }),
  ])
  const c5 = h.metrics(1)

  // 케이스 6: parallel 밖의 직접 호출이 던짐 ⇒ reject 하지 않고 null 을 돌려준다 (호출자의 null 가드가 fallback 을 낸다)
  h = freshHarness({ a: [boom()] })
  let direct = 'unset'
  try { direct = await h.callAgent('a', { label: 'a' }) } catch (e) { direct = 'REJECT ' + e.message }
  const c6 = h.metrics(0)

  const t = [
    ['재시도 성공 → nullCount 0', c1.nullCount === 0, JSON.stringify(c1)],
    ['재시도 성공 → agentCalls 4 (호출수는 유지)', c1.agentCalls === 4, JSON.stringify(c1)],
    ['재시도 실패 → nullCount 1 (이중 계상 없음)', c2.nullCount === 1, JSON.stringify(c2)],
    ['무장애 → nullCount 0 / agentCalls 3', c3.nullCount === 0 && c3.agentCalls === 3, JSON.stringify(c3)],
    ['throw → 재시도 성공 → nullCount 0 / agentCalls 4 / 결과 회수', c4.nullCount === 0 && c4.agentCalls === 4 && out4[0] === 'OK', JSON.stringify(c4)],
    ['throw → 사유가 로그에 남는다(WARN a 실패 — spawn exploded)', logs4.some(l => l.includes('a 실패') && l.includes('spawn exploded')), JSON.stringify(logs4)],
    ['throw → 재시도도 throw → nullCount 1 (음수 아님)', c5.nullCount === 1 && c5.agentCalls === 4, JSON.stringify(c5)],
    ['직접 호출 throw → reject 없이 null / nullCount 1', direct === null && c6.nullCount === 1 && c6.agentCalls === 1, JSON.stringify({ direct, c6 })],
  ]
  let fail = 0
  for (const [name, ok, got] of t) { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}  ${got}`); if (!ok) fail++ }
  console.log('')
  console.log(`${t.length - fail}/${t.length} 통과 (원본 마커 추출 — 복사본 아님)`)
  process.exit(fail ? 1 : 0)
}
run()
