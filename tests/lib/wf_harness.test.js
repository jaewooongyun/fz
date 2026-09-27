// tests/lib/wf_harness.test.js — 가짜 런타임 로더가 런타임 의미를 지키는가 + 실제 워크플로를 전부 싣는가.
//
// ⛔ 실제 워크플로 스모크는 args={} · 모든 워커 null 로 돈다. 판정은 **싣기 오류 0** 이다 — ReferenceError(hook 누락 ·
//    미정의 이름) · SyntaxError · meta 누락 · 인자 검증에서 fallback 을 돌려주지 않고 던진 오류(§12 args 방어 파싱 위반)가
//    모두 실패다. fallback 반환은 스크립트의 동작이라 판정하지 않는다. 오류 주입 사례가 이 판별력을 고정한다(v4.40.0 validate).
// ⛔ 범위: args={} 이면 워크플로가 **인자 검증에서 곧바로 fallback 을 반환**한다(실측 8/8 · 워커 호출 0).
//    그래서 이 스모크는 "싣기 + 인자 검증 프롤로그" 까지만 본다. 워커 null 분기·완주 계산은 유효한 args 를
//    만드는 워크플로별 테스트가 이 로더로 본다.
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { run } = require('./wf_harness')

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'wfh-'))
function script(name, body) {
  const f = path.join(tmp, name + '.js')
  fs.writeFileSync(f, 'export const meta = { name: "' + name + '", description: "t" }\n' + body)
  return f
}

const cases = []
function t(name, fn) { cases.push([name, fn]) }
function assert(c, msg) { if (!c) throw new Error(msg) }

t('parallel — 던진 thunk 와 죽은 워커는 null, 값은 보존', async () => {
  const f = script('par', `
    const r = await parallel([
      () => agent('a', { label: 'a', model: 'opus', effort: 'xhigh' }),
      () => { throw new Error('boom') },
      () => agent('dead', { label: 'dead' }),
    ])
    return r`)
  const { result, calls } = await run(f, { responder: p => (p === 'dead' ? null : p.toUpperCase()) })
  assert(JSON.stringify(result) === JSON.stringify(['A', null, null]), `result ${JSON.stringify(result)}`)
  assert(calls.length === 2 && calls[0].model === 'opus' && calls[0].effort === 'xhigh', `calls ${JSON.stringify(calls)}`)
})

t('pipeline — 던진 stage 는 그 item 만 null, 남은 stage 를 건너뛴다', async () => {
  const f = script('pipe', `
    let later = 0
    const r = await pipeline([1, 2, 3],
      (v, item, i) => { if (item === 2) throw new Error('x'); return v * 10 },
      (v, item, i) => { later += 1; return v + i })
    return { r, later }`)
  const { result } = await run(f, { responder: () => null })
  assert(JSON.stringify(result.r) === JSON.stringify([10, null, 32]), `r ${JSON.stringify(result.r)}`)
  assert(result.later === 2, `later ${result.later} — 실패 item 의 뒤 stage 가 돌았다`)
})

t('최상위 return 값 · args · phase · log 전달', async () => {
  const f = script('ret', `phase('P1'); log('hello ' + args.who); return { ok: true, who: args.who }`)
  const { result, phases, logs } = await run(f, { args: { who: 'w' }, responder: () => null })
  assert(result.ok === true && result.who === 'w', JSON.stringify(result))
  assert(phases[0] === 'P1' && logs[0] === 'hello w', `${phases} ${logs}`)
})

t('Date.now()·Math.random()·new Date() 는 던지고 new Date(0) 은 된다', async () => {
  for (const expr of ['Date.now()', 'Math.random()', 'new Date()']) {
    const f = script('forbid', `return ${expr}`)
    let threw = false
    try { await run(f, { responder: () => null }) } catch (e) { threw = /금지/.test(e.message) }
    assert(threw, `${expr} 가 막히지 않았다`)
  }
  const f = script('okdate', 'return new Date(0).getTime() + Math.max(1, 2)')
  const { result } = await run(f, { responder: () => null })
  assert(result === 2, `result ${result}`)
})

t('폭주 — cap 을 넘으면 watchdog 이 reject 한다', async () => {
  const f = script('loop', `while (true) { await parallel([() => agent('x')]) }`)
  let msg = ''
  try { await run(f, { responder: () => null, cap: 5, timeoutMs: 300 }) } catch (e) { msg = e.message }
  assert(/폭주/.test(msg), `msg '${msg}'`)
})

async function loadErrors(dir) {
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.js')).sort()
  const errs = []
  let fallback = 0
  for (const name of files) {
    try {
      const { result } = await run(path.join(dir, name), { args: {}, responder: () => null })
      if (result && result.mode === 'fallback') fallback += 1
    } catch (e) {
      // ⛔ ReferenceError 만 세면 문법 오류·meta 누락 같은 싣기 실패를 삼킨다(v4.40.0 리뷰)
      errs.push(`${name}: ${(e && e.name) || 'Error'}: ${e && e.message}`)
    }
  }
  return { files, errs, fallback }
}

t('싣기 오류 주입 — 문법 오류 · meta 누락 · 미정의 이름이 각각 실패로 잡힌다', async () => {
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'wfh-bad-'))
  fs.writeFileSync(path.join(d, 'a-syntax.js'), 'export const meta = { name: "a", description: "t" }\nconst x = (\n')
  fs.writeFileSync(path.join(d, 'b-nometa.js'), 'return { mode: "fallback" }\n')
  fs.writeFileSync(path.join(d, 'c-ref.js'), 'export const meta = { name: "c", description: "t" }\nnotDefinedHook()\n')
  try {
    const { errs } = await loadErrors(d)
    assert(errs.length === 3, `주입 3건 중 ${errs.length}건만 잡혔다: ${errs.join(' · ')}`)
  } finally {
    fs.rmSync(d, { recursive: true, force: true })
  }
})

t('실제 워크플로 전부 싣기 — args={} 인자 검증 프롤로그까지 싣기 오류 0', async () => {
  const dir = path.join(__dirname, '..', '..', 'workflows')
  const { files, errs: loadErr, fallback } = await loadErrors(dir)
  assert(files.length > 0, '워크플로 0건 — 경로 오류를 먼저 의심한다')
  assert(!loadErr.length, loadErr.join(' · '))
  console.log(`      (워크플로 ${files.length}개 싣기 · 인자 검증 fallback 반환 ${fallback}/${files.length})`)
})

;(async () => {
  let fail = 0
  for (const [name, fn] of cases) {
    try { await fn(); console.log(`PASS  ${name}`) } catch (e) { fail += 1; console.log(`FAIL  ${name} — ${e.message}`) }
  }
  fs.rmSync(tmp, { recursive: true, force: true })
  console.log(`\nwf_harness ${cases.length - fail}/${cases.length} 통과`)
  process.exit(fail ? 1 : 0)
})()
