// tests/lib/wf_harness.js — 워크플로 스크립트를 **통째로** 가짜 런타임에서 돌린다.
//
// tests/workflows/*.js 는 `>>> PURE:` 마커 블록만 떼어 평가한다. 그 방식으로는 스크립트 전체의
// 제어 흐름(렌즈 null → degraded·fallback 분기, 완주 계산)을 못 본다. 이 로더는 런타임이 주는
// hook(agent·parallel·pipeline·phase·log·args·budget·workflow)을 모두 주입해 본문을 실행한다.
//
// ⛔ 런타임 의미를 맞춘다 (Workflow 도구 사양):
//    · parallel — thunk 가 던지면 그 자리는 null 이고, 호출 자체는 reject 하지 않는다
//    · pipeline — stage 가 던지면 그 item 은 null 이고 남은 stage 를 건너뛴다. stage 는 (prev, item, index)
//    · Date.now()·Math.random()·인자 없는 new Date() 는 던진다(재개 캐시를 깨서 런타임이 막는다)
// ⛔ responder 가 null 을 돌려주면 "죽은 워커"(런타임 agent() 의 null)다. 던지면 agent() 가 reject 한다.
// ⛔ 폭주 방지: agent 호출이 cap 을 넘으면 그 뒤 호출은 끝나지 않는 promise 가 되고 watchdog 이 run() 을
//    reject 한다 — 던지게 두면 parallel 이 삼켜 마이크로태스크 루프가 타이머까지 굶긴다.
// ⛔ tests/lib 는 health-check 자동 러너(tests/workflows/*.js · tests/fixtures/*/*/run.sh) 밖이다 — 라이브러리다.
// ⛔ 한계: budget.spent() 는 항상 0 이다 — 토큰 소비를 흉내 내지 않는다. budget 분기를 시험하는 소비자가 생기면 그때 넣는다.
'use strict'
const fs = require('fs')

const path = require('path')
// meta 판정·`export` 제거는 문법 검사기와 **같은 함수**를 쓴다 — 두 곳이 갈리면 검사는 통과하고 로더는 실패한다
const { leadingMeta, body } = require(path.join(__dirname, '..', '..', 'scripts', 'check_wf_syntax.js'))

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor

function load(file) {
  const src = fs.readFileSync(file, 'utf8')
  if (leadingMeta(src) < 0) throw new Error(`첫 문장이 export const meta 가 아니다: ${file}`)
  return body(src)
}

function forbidden(what) { return () => { throw new Error(`${what} 금지 — 런타임이 막는다(재개 캐시)`) } }

function fakeDate() {
  const Real = Date
  function D(...a) {
    if (!a.length) forbidden('인자 없는 new Date()')()
    return new Real(...a)
  }
  D.now = forbidden('Date.now()')
  D.UTC = Real.UTC
  D.parse = Real.parse
  return D
}

function fakeMath() {
  const m = Object.create(Math)
  m.random = forbidden('Math.random()')
  return m
}

/**
 * @param {string} file  workflows/*.js 경로
 * @param {{args?: any, responder: (prompt: string, opts: object, index: number) => any,
 *          budgetTotal?: number|null, cap?: number, timeoutMs?: number}} o
 * @returns {Promise<{result: any, calls: object[], logs: string[], phases: string[]}>}
 */
async function run(file, o) {
  const { args, responder, budgetTotal = null, cap = 500, timeoutMs = 10000 } = o
  const calls = [], logs = [], phases = []
  let runaway = false
  const agent = async (prompt, opts = {}) => {
    if (calls.length >= cap) { runaway = true; return new Promise(() => {}) }
    const i = calls.length
    calls.push({ label: opts.label, phase: opts.phase, model: opts.model, effort: opts.effort,
                 agentType: opts.agentType, schema: !!opts.schema, prompt })
    const v = await responder(prompt, opts, i)
    calls[i].result = v === null || v === undefined ? null : 'value'
    return v === undefined ? null : v
  }
  const parallel = async thunks => Promise.all(thunks.map(t => Promise.resolve().then(t).catch(() => null)))
  const pipeline = async (items, ...stages) => Promise.all(items.map(async (item, index) => {
    let v = item
    for (const s of stages) {
      try { v = await s(v, item, index) } catch (e) { return null }
    }
    return v
  }))
  const phase = t => { phases.push(t) }
  const log = m => { logs.push(String(m)) }
  const budget = { total: budgetTotal, spent: () => 0, remaining: () => (budgetTotal == null ? Infinity : budgetTotal) }
  const workflow = async () => { throw new Error('wf_harness: workflow() 중첩 호출은 지원하지 않는다') }

  const fn = new AsyncFunction('agent', 'parallel', 'pipeline', 'phase', 'log', 'args', 'budget', 'workflow',
                               'Date', 'Math', load(file))
  let timer
  const watchdog = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error(runaway ? `wf_harness: agent 호출 ${cap}회 초과(폭주)` :
                                              `wf_harness: ${timeoutMs}ms 안에 끝나지 않았다`)), timeoutMs)
  })
  try {
    const result = await Promise.race([
      fn(agent, parallel, pipeline, phase, log, args, budget, workflow, fakeDate(), fakeMath()),
      watchdog,
    ])
    return { result, calls, logs, phases }
  } finally { clearTimeout(timer) }
}

module.exports = { run, load }
