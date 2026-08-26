// D6 카운터 시맨틱 fixture — peer-review.js parallelWithRetry 로직 추출
function makeHarness() {
//
// ⛔ 이 파일은 workflows/peer-review.js 의 로직을 **복사**한 것이다. Workflow 스크립트는
//    단독 실행이 안 되므로(agent/parallel 런타임 의존) 순수 함수만 떼어내 검증한다.
//    → 원본을 고치면 여기도 고쳐야 한다. 복사본이 stale 해지면 이 테스트는 **과거를 검증한다.**
//    값싼 대조: 원본에서 함수 본문을 grep 해 이 파일과 눈으로 맞춘다.
  let agentCalls = 0, nullCalls = 0
  const callAgent = async (out) => { agentCalls += 1; if (!out) nullCalls += 1; return out }
  const parallel = async (thunks) => Promise.all(thunks.map(t => t()))
  async function parallelWithRetry(thunks) {
    const out = await parallel(thunks)
    for (let i = 0; i < out.length; i += 1) {
      if (!out[i]) { nullCalls -= 1; out[i] = (await parallel([thunks[i]]))[0] }
    }
    return out
  }
  return { parallelWithRetry, callAgent, m: () => ({ agentCalls, nullCount: nullCalls }) }
}
const run = async () => {
  // 케이스 1: 첫 시도 null → 재시도 성공  ⇒ nullCount 0
  let h = makeHarness(); let seq = [null, 'OK']; let k = 0
  await h.parallelWithRetry([() => h.callAgent(seq[k++]), () => h.callAgent('A'), () => h.callAgent('B')])
  const c1 = h.m()
  // 케이스 2: 첫 시도 null → 재시도도 null ⇒ nullCount 1 (이중 계상 없음)
  h = makeHarness(); seq = [null, null]; k = 0
  await h.parallelWithRetry([() => h.callAgent(seq[k++]), () => h.callAgent('A'), () => h.callAgent('B')])
  const c2 = h.m()
  // 케이스 3: 무장애 ⇒ nullCount 0, agentCalls 3
  h = makeHarness()
  await h.parallelWithRetry([() => h.callAgent('A'), () => h.callAgent('B'), () => h.callAgent('C')])
  const c3 = h.m()

  const t = [
    ['재시도 성공 → nullCount 0', c1.nullCount === 0, JSON.stringify(c1)],
    ['재시도 성공 → agentCalls 4 (호출수는 유지)', c1.agentCalls === 4, JSON.stringify(c1)],
    ['재시도 실패 → nullCount 1 (이중 계상 없음)', c2.nullCount === 1, JSON.stringify(c2)],
    ['무장애 → nullCount 0 / agentCalls 3', c3.nullCount === 0 && c3.agentCalls === 3, JSON.stringify(c3)],
  ]
  let fail = 0
  for (const [name, ok, got] of t) { console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}  ${got}`); if (!ok) fail++ }
  process.exit(fail ? 1 : 0)
}
run()
