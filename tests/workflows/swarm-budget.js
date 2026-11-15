// tests/workflows/swarm-budget.js — workflows/swarm.js 를 가짜 런타임(tests/lib/wf_harness.js)으로 통째로 돌려 예산 가드 · sha/method 규칙을 본다 (B8 · F-501)
//
// 케이스(이름 고정 — 릴리스 게이트가 grep 한다):
//   sha-missing-respawn  첫 응답이 sha 없음 · 틀린 sha · 빈 method → 정확히 1회 재스폰 → 브리프 sha 로 PASS 행. 두 번 빠지면 BLOCKED 'no-sha-method' · dropped 보고
//   opus-concurrency     지연 응답으로 동시 진행 콜을 센다 — 조각 10개(재스폰 묶음 포함 · concurrency 9 요청)에서 최대 ≤3 · 전 콜 opus · effort 전달
//   tenfold-cap          maxFragments 의 10배 조각 → 총 콜 == 상한(넘지 않는다) · 초과 조각 BLOCKED 'budget' · log 가 잘린 수를 적는다
//   low-budget-stop      budgetTotal + budgetPerCall 로 잔여 예산을 낮춘다 → 첫 시도 · 재스폰 중간에 스폰이 멈추고 끝나지 않은 조각은 BLOCKED 'budget'
//   every-fragment-row   PASS · ISSUES · BLOCKED · null 워커 · 상한 밖이 섞여도 표 = 입력 id 를 입력 순서로 1번씩 · 유효 status · 비BLOCKED 행은 sha + method.
//                        nullCount 는 잔존 null 이다(D6 — null 뒤 재스폰이 PASS 면 세지 않는다 · tests/workflows/d6-null-count-semantics.js 와 같은 의미)
//   agenttype-fallback   쓰기 가능(general-purpose · memory 필드) · 빈 tools · 이 트리 전용 · 텔레메트리 단일 스테이지 · 네임스페이스 없음 · 미지 agentType
//                        → mode 'fallback' · 콜 0 (대조: 읽기 전용 agentType 은 돈다)
//   allowlist-readonly   swarm.js READ_ONLY_AGENTS = 행동으로 받는 agentType 집합이고, 그 전부가 agents/*.md 에서 tools 가 비지 않고
//                        쓰기 도구 · memory 필드가 없다 — 목록 안 에이전트에 쓰기 도구를 더하면 여기서 깨진다
//   args-fallback        필수 인자 · id 중복 · SHA 형식 · SHA 둘 · 상대 tree · effort · 정수 인자 오류 → fallback · 콜 0 (대조: JSON 문자열 args 는 돈다)
// 출력: 케이스마다 `<case>: PASS|FAIL <why>` 한 줄 + 끝 줄 `swarm-budget: PASS|FAIL` · exit 0 전건 통과 / 1 하나라도 실패.
// ⛔ FZ_WF_ROOT 로 swarm.js 가 없는 트리를 가리키면 케이스마다 FAIL 줄과 exit 1 이다 — 조용히 죽지 않는다(review-live-stage2-arm.js 와 같은 관용).
// ⛔ 예산 임계(BUDGET_RESERVE) 값에 묶지 않는다 — low-budget-stop 은 "중간에 멈춘다 · 안 돈 조각 = BLOCKED 'budget'" 만 단언한다.
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'swarm.js')
const SHA = 'f8eb56f'
const TREE = '/tmp/fz-swarm-pinned'
const METHOD = '고정 트리 Read 1회 · 파일은 브리프 순서'
const STATUSES = ['PASS', 'ISSUES', 'BLOCKED']
// 읽기 전용 판정 — swarm.js READ_ONLY_AGENTS 주석 ① · ② 와 같은 기준(memory 정규식은 scripts/lint_contracts.py MEMORY_FIELD 와 같다)
const WRITE_TOOLS = ['Edit', 'Write', 'MultiEdit', 'NotebookEdit', 'Bash']
const WRITE_MCP = /^mcp__.+__(?:write|edit|replace|insert|rename|delete|create|execute)/i
const CASES = [
  ['sha-missing-respawn', shaMissingRespawn],
  ['opus-concurrency', opusConcurrency],
  ['tenfold-cap', tenfoldCap],
  ['low-budget-stop', lowBudgetStop],
  ['every-fragment-row', everyFragmentRow],
  ['agenttype-fallback', agentTypeFallback],
  ['allowlist-readonly', allowlistReadonly],
  ['args-fallback', argsFallback],
]

const frag = id => ({ id, brief: `조각 ${id} 의 주장을 고정 트리에서 판정한다`, sha: SHA, method: METHOD })
const frags = (n, prefix) => Array.from({ length: n }, (_, i) => frag(`${prefix || 'F'}${i + 1}`))
const ok = (status, extra) => Object.assign({ status, sha: SHA, method: METHOD, findings: [], evidence: 'e' }, extra || {})
const idOf = c => String((c && c.label) || '').replace(/^swarm:/, '')
const rowsOf = r => (Array.isArray(r.res.table) ? r.res.table : [])
const byId = r => Object.fromEntries(rowsOf(r).map(x => [x.id, x]))

// plan(id, attempt, prompt) → 응답(값 · null · Promise). attempt 는 그 조각의 몇 번째 콜인지(1 · 2)
async function go(args, plan, extra) {
  const seen = {}
  const responder = (prompt, opts) => {
    const id = idOf(opts)
    seen[id] = (seen[id] || 0) + 1
    return plan(id, seen[id], prompt)
  }
  const r = await run(WF, Object.assign({ args, responder }, extra || {}))
  const per = {}
  for (const c of r.calls) per[idOf(c)] = (per[idOf(c)] || 0) + 1
  return Object.assign(r, { per, res: r.result || {} })
}

let failed = 0
async function kase(name, fn) {
  const bad = []
  const expect = (cond, msg) => { if (!cond) bad.push(msg) }
  let note = ''
  try { note = (await fn(expect)) || '' } catch (e) { bad.push(`실행 오류 — ${e && e.message}`) }
  if (bad.length) { failed += 1; console.log(`${name}: FAIL ${bad.join(' · ')}`) } else console.log(`${name}: PASS${note ? ` ${note}` : ''}`)
}

// agents/<stem>.md 가 읽기 전용이 아니면 그 이유, 맞으면 '' — frontmatter 는 정규식 대신 startsWith/indexOf 로 자른다
function readOnlyWhy(file) {
  if (!fs.existsSync(file)) return '이 트리 agents/ 에 정의가 없다'
  const src = fs.readFileSync(file, 'utf8')
  const end = src.startsWith('---\n') ? src.indexOf('\n---', 4) : -1
  if (end < 0) return 'frontmatter 없음'
  const fm = src.slice(4, end)
  if (/^["']?memory["']?\s*:\s*\S/m.test(fm)) return '`memory:` 필드 — Read/Write/Edit 를 자동 부여한다(lint_contracts N13)'
  const t = fm.match(/^tools:[ \t]*(.*)$/m)
  if (!t || !t[1].trim()) return '`tools:` 가 없거나 비었다 — 없으면 전 도구를 받고 비면 고정 트리를 못 읽는다'
  const bad = t[1].split(',').map(s => s.trim()).filter(x => x && (WRITE_TOOLS.includes(x.replace(/\(.*$/, '').trim()) || WRITE_MCP.test(x)))
  return bad.length ? `쓰기 도구 ${bad.join(' · ')}` : ''
}

async function shaMissingRespawn(expect) {
  const noSha = () => { const v = ok('PASS'); delete v.sha; return v }
  const input = ['A', 'B', 'C', 'D', 'E', 'F'].map(frag)
  const r = await go({ fragments: input, tree: TREE }, (id, n) => {
    if (id === 'E') return ok('ISSUES', { findings: [{ severity: 'minor', title: 't', detail: 'd', evidence: 'e' }] })
    if (id === 'F') return ok('PASS', { sha: ` ${SHA.toUpperCase()} ` })   // 공백 · 대소문자만 다르다 — 같은 SHA 로 받는다
    if (id === 'D') return n === 1 ? noSha() : ok('PASS', { sha: '0000000' })   // 두 번 다 빠진다
    if (n === 2) return ok('PASS')
    return { A: noSha(), B: ok('PASS', { sha: 'deadbee' }), C: ok('PASS', { method: '  ' }) }[id]
  })
  const t = byId(r)
  const m = r.res.metrics || {}
  expect(r.res.mode === 'workflow', `mode ${r.res.mode}`)
  expect(['A', 'B', 'C', 'D'].every(id => r.per[id] === 2) && r.per.E === 1 && r.per.F === 1, `조각별 콜 ${JSON.stringify(r.per)} — A·B·C·D 2 · E·F 1 기대`)
  expect(['A', 'B', 'C', 'F'].every(id => t[id] && t[id].status === 'PASS' && t[id].sha === SHA && t[id].method === METHOD),
    `재스폰 뒤 PASS 행 ${JSON.stringify(['A', 'B', 'C', 'F'].map(id => t[id]))}`)
  expect(t.D && t.D.status === 'BLOCKED' && t.D.reason === 'no-sha-method' && t.D.sha === null, `두 번 빠진 조각 ${JSON.stringify(t.D)}`)
  expect(t.E && t.E.status === 'ISSUES' && t.E.findings.length === 1, `ISSUES 행 ${JSON.stringify(t.E)}`)
  expect(m.respawns === 4 && m.dropped === 5 && m.nullCount === 0, `metrics ${JSON.stringify(m)} — respawns 4 · dropped 5 · nullCount 0 기대`)
  expect(r.calls.every(c => c.prompt.includes(`read only under ${TREE} (pinned at ${SHA}); method: ${METHOD}`) && c.prompt.includes('record sha and method in your result')),
    '프롬프트에 고정 트리 · sha · method · 기록 의무가 없다')
  const a = r.calls.filter(c => c.label === 'swarm:A')
  expect(a.length === 2 && !a[0].prompt.includes('[재스폰]') && a[1].prompt.includes('[재스폰]'), '재스폰 프롬프트 표지가 둘째 콜에만 있어야 한다')
  expect(r.calls.every(c => c.model === 'opus' && c.effort === 'xhigh' && c.agentType === 'fz:review-correctness' && c.schema),
    `콜 opts ${JSON.stringify(r.calls.map(c => [c.model, c.effort, c.agentType]))}`)
  return `콜 ${r.calls.length} · 재스폰 ${m.respawns} · 폐기 ${m.dropped}`
}

async function opusConcurrency(expect) {
  let inFlight = 0
  let peak = 0
  const plan = async (id, n) => {
    inFlight += 1
    peak = Math.max(peak, inFlight)
    await new Promise(res => setTimeout(res, 3))
    inFlight -= 1
    return n === 1 && Number(id.slice(1)) % 2 === 0 ? ok('PASS', { sha: '' }) : ok('PASS')   // 짝수 조각은 재스폰 묶음도 지난다
  }
  const r = await go({ fragments: frags(10), tree: TREE, concurrency: 9 }, plan)
  const m = r.res.metrics || {}
  expect(r.res.mode === 'workflow', `mode ${r.res.mode}`)
  expect(r.calls.length === 15, `콜 ${r.calls.length} — 첫 시도 10 + 재스폰 5 기대`)
  expect(peak <= 3, `동시 진행 최대 ${peak} > 3`)
  expect(peak === 3, `동시 진행 최대 ${peak} — 묶음 안이 병렬이면 3 이다`)
  expect(r.calls.every(c => c.model === 'opus'), `opus 가 아닌 콜 ${r.calls.map(c => c.model)}`)
  expect(m.concurrency === 3 && r.logs.some(l => l.includes('concurrency 9')), `concurrency 9 → 3 깎기 (metrics ${m.concurrency})`)
  const high = await go({ fragments: frags(2), tree: TREE, effort: 'high' }, () => ok('PASS'))
  expect(high.calls.length === 2 && high.calls.every(c => c.effort === 'high'), `effort 'high' → ${high.calls.map(c => c.effort)}`)
  return `동시 최대 ${peak} · 콜 ${r.calls.length}`
}

async function tenfoldCap(expect) {
  const input = frags(120)   // maxFragments 기본 12 의 10배
  const dropFirst = (id, n) => (n === 1 ? ok('PASS', { sha: undefined }) : ok('PASS'))
  const a = await go({ fragments: input, tree: TREE }, dropFirst)
  const am = a.res.metrics || {}
  const at = rowsOf(a)
  expect(a.calls.length === 24 && am.maxAgents === 24, `총 콜 ${a.calls.length} · maxAgents ${am.maxAgents} — 상한 24(2 × maxFragments 12) 기대`)
  expect(at.length === 120 && at.slice(0, 12).every(x => x.status === 'PASS'), '앞 12 조각이 PASS 가 아니다')
  expect(at.slice(12).every(x => x.status === 'BLOCKED' && x.reason === 'budget') && am.blockedBudget === 108, `초과 조각 BLOCKED 'budget' ${am.blockedBudget}/108`)
  expect(a.logs.some(l => l.includes('maxFragments') && l.includes('108')), '잘린 조각 수(108)를 적은 log 없음')
  const b = await go({ fragments: input, tree: TREE, maxAgents: 1000 }, dropFirst)
  expect(b.calls.length === 24 && (b.res.metrics || {}).maxAgents === 24 && b.logs.some(l => l.includes('maxAgents 1000')),
    `maxAgents 1000 → 콜 ${b.calls.length}(상한 24 로 깎여야 한다)`)
  const c = await go({ fragments: input, tree: TREE, maxAgents: 18 }, dropFirst)
  const ct = rowsOf(c)
  const cPass = ct.filter(x => x.status === 'PASS').length
  const cBudget = ct.filter(x => x.reason === 'budget').length
  expect(c.calls.length === 18 && cPass === 6 && cBudget === 114, `maxAgents 18 → 콜 ${c.calls.length}/18 · PASS ${cPass}/6 · budget ${cBudget}/114`)
  const d = await go({ fragments: input, tree: TREE }, () => ok('PASS'))
  expect(d.calls.length === 12, `유효 응답만이면 콜 ${d.calls.length} — maxFragments 12 기대`)
  const e = await go({ fragments: frags(40), tree: TREE, maxFragments: 4 }, dropFirst)
  expect(e.calls.length === 8 && (e.res.metrics || {}).blockedBudget === 36, `maxFragments 4 × 10 → 콜 ${e.calls.length}/8 · budget ${(e.res.metrics || {}).blockedBudget}/36`)
  return `콜 ${a.calls.length}/24 · 잘린 조각 ${am.blockedBudget} · maxAgents 18 → ${c.calls.length}`
}

async function lowBudgetStop(expect) {
  const low = { budgetTotal: 100, budgetPerCall: 10 }
  const a = await go({ fragments: frags(12), tree: TREE }, () => ok('PASS'), low)
  const n = a.calls.length
  const at = rowsOf(a)
  expect(a.res.mode === 'workflow', `mode ${a.res.mode}`)
  expect(n > 0 && n < 12, `콜 ${n} — 중간에 멈춰야 한다(0 < 콜 < 12)`)
  expect(at.length === 12 && at.every(x => (a.per[x.id] ? x.status === 'PASS' : x.status === 'BLOCKED' && x.reason === 'budget')),
    `돈 조각 = PASS · 안 돈 조각 = BLOCKED budget 이 아니다 ${JSON.stringify(at.map(x => [x.id, x.status, x.reason]))}`)
  expect((a.res.metrics || {}).blockedBudget === 12 - n, `blockedBudget ${(a.res.metrics || {}).blockedBudget} ≠ ${12 - n}`)
  expect(a.logs.some(l => l.includes('budget.remaining()')), '잔여 예산 중단을 적은 log 없음')
  const free = await go({ fragments: frags(12), tree: TREE }, () => ok('PASS'))
  const rich = await go({ fragments: frags(12), tree: TREE }, () => ok('PASS'), { budgetTotal: 100000, budgetPerCall: 10 })
  expect(free.calls.length === 12 && rich.calls.length === 12, `대조 — 예산 없음 ${free.calls.length} · 넉넉한 예산 ${rich.calls.length} (12 기대)`)
  const d = await go({ fragments: frags(6), tree: TREE }, (id, k) => (k === 1 ? ok('PASS', { sha: undefined }) : ok('PASS')), low)
  const dm = d.res.metrics || {}
  expect(dm.respawns > 0 && dm.respawns < 6, `재스폰 ${dm.respawns} — 재스폰 차례 중간에 멈춰야 한다(0 < 재스폰 < 6)`)
  expect(rowsOf(d).every(x => (d.per[x.id] === 2 ? x.status === 'PASS' : x.status === 'BLOCKED' && x.reason === 'budget')),
    '재스폰 받은 조각 = PASS · 못 받은 조각 = BLOCKED budget 이 아니다')
  return `콜 ${n}/12 에서 멈춤 · 재스폰 ${dm.respawns}/6`
}

async function everyFragmentRow(expect) {
  const input = ['P1', 'I1', 'B1', 'N1', 'R1', 'M1', 'S1', 'X1'].map(frag)   // X1 은 maxFragments 7 밖 — 돌지 않는다
  const r = await go({ fragments: input, tree: TREE, maxFragments: 7 }, (id, n) => {
    if (id === 'P1') return ok('PASS')
    if (id === 'I1') return ok('ISSUES', { findings: [{ severity: 'major', title: 't', detail: 'd', evidence: 'e' }] })
    if (id === 'B1') return ok('BLOCKED', { evidence: '고정 트리에 대상 파일이 없다' })
    if (id === 'N1') return null
    if (id === 'R1') return n === 1 ? null : ok('PASS')   // null 뒤 재스폰 PASS — 잔존 null 이 아니다(D6)
    if (id === 'M1') return ok('PASS', { method: '' })
    return n === 1 ? ok('MAYBE') : ok('PASS')   // S1 — status 가 셋 밖이면 한 번 다시 띄운다
  })
  const rows = rowsOf(r)
  const t = byId(r)
  const m = r.res.metrics || {}
  expect(r.res.mode === 'workflow', `mode ${r.res.mode}`)
  expect(rows.map(x => x.id).join(',') === input.map(f => f.id).join(','), `표 id ${rows.map(x => x.id)} ≠ 입력 id(순서 · 1번씩)`)
  expect(rows.every(x => STATUSES.includes(x.status)), `status 밖 ${rows.map(x => x.status)}`)
  expect(rows.filter(x => x.status !== 'BLOCKED').every(x => x.sha === SHA && typeof x.method === 'string' && x.method.trim() !== ''), '비BLOCKED 행에 sha · method 없음')
  const reasons = { B1: 'worker-blocked', N1: 'worker-null', M1: 'no-sha-method', X1: 'budget' }
  expect(Object.entries(reasons).every(([id, why]) => t[id] && t[id].status === 'BLOCKED' && t[id].reason === why),
    `BLOCKED reason ${JSON.stringify(Object.keys(reasons).map(id => [id, t[id] && t[id].reason]))}`)
  expect(['P1', 'R1', 'S1'].every(id => t[id] && t[id].status === 'PASS') && t.I1 && t.I1.status === 'ISSUES' && t.I1.findings.length === 1,
    `PASS · ISSUES · 재스폰 PASS 행 ${JSON.stringify([t.P1, t.I1, t.R1, t.S1])}`)
  expect(t.B1 && t.B1.sha === SHA && t.B1.method === METHOD, '워커 BLOCKED 행은 기록한 sha · method 를 싣는다')
  expect(r.calls.length === 11 && m.respawns === 4 && m.dropped === 3, `콜 ${r.calls.length}/11 · metrics ${JSON.stringify(m)} — respawns 4 · dropped 3 기대`)
  expect(m.nullCount === 1, `nullCount ${m.nullCount} — 잔존 null 은 N1 하나다(R1 은 재스폰에서 회복 · D6)`)
  const z = await go({ fragments: frags(3, 'Z'), tree: TREE }, () => null)
  const zt = rowsOf(z)
  const zm = z.res.metrics || {}
  expect(z.res.mode === 'fallback' && z.calls.length === 6 && zm.nullCount === 3,
    `워커 전부 null → mode ${z.res.mode} · 콜 ${z.calls.length}/6 · nullCount ${zm.nullCount}/3`)
  expect(zt.map(x => x.id).join(',') === 'Z1,Z2,Z3' && zt.every(x => x.status === 'BLOCKED' && x.reason === 'worker-null'), 'fallback 에도 조각당 1행(worker-null)이 실려야 한다')
  return `${rows.length}행 · PASS ${rows.filter(x => x.status === 'PASS').length} · ISSUES ${rows.filter(x => x.status === 'ISSUES').length} · BLOCKED ${rows.filter(x => x.status === 'BLOCKED').length} · 잔존 null ${m.nullCount}`
}

async function agentTypeFallback(expect) {
  // general-purpose = 쓰기 가능 내장 · memory-curator = memory 필드(쓰기 자동 부여) · plan-merge = 빈 tools · review-arch = 리뷰 전용 arch-critic 사전주입(B4) ·
  // 네임스페이스 없음 · 미지 — ⬇ review-counter 는 2026-11-05 label 규약(F-531)으로 허용으로 옮겼다(아래 대조)
  const rejected = ['general-purpose', 'fz:memory-curator', 'fz:plan-merge', 'fz:review-arch', 'review-correctness', 'fz:no-such-agent']
  for (const agentType of rejected) {
    const r = await go({ fragments: frags(2), tree: TREE, agentType }, () => ok('PASS'))
    expect(r.res.mode === 'fallback' && r.calls.length === 0, `agentType ${agentType} → mode ${r.res.mode} · 콜 ${r.calls.length}`)
  }
  const ctl = await go({ fragments: frags(2), tree: TREE, agentType: 'fz:arch-lens' }, () => ok('PASS'))
  expect(ctl.res.mode === 'workflow' && ctl.calls.length === 2 && ctl.calls.every(c => c.agentType === 'fz:arch-lens'),
    `대조 fz:arch-lens → mode ${ctl.res.mode} · ${ctl.calls.map(c => c.agentType)}`)
  const rc = await go({ fragments: frags(2), tree: TREE, agentType: 'fz:review-counter' }, () => ok('PASS'))
  expect(rc.res.mode === 'workflow' && rc.calls.length === 2 && rc.calls.every(c => c.agentType === 'fz:review-counter'),
    `재허용 fz:review-counter → mode ${rc.res.mode} · ${rc.calls.map(c => c.agentType)}`)
  return `거부 ${rejected.length}종 · 대조 2종(arch-lens · review-counter 재허용)`
}

async function allowlistReadonly(expect) {
  const m = fs.readFileSync(WF, 'utf8').match(/const READ_ONLY_AGENTS = \[([\s\S]*?)\]/)
  const listed = m ? [...m[1].matchAll(/'fz:([a-z0-9-]+)'/g)].map(x => x[1]).sort() : []
  expect(listed.length > 0, 'READ_ONLY_AGENTS 목록을 찾지 못했다 — 측정 실패(통과로 읽지 않는다)')
  const dir = path.join(ROOT, 'agents')
  const stems = fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.md')).map(f => f.slice(0, -3)).sort() : []
  expect(stems.length > 0, `agents/*.md 0건 — ${dir}`)
  // 행동으로 묻는다 — 목록 추출이 빗나가도 실제로 받는 agentType 이 기준이다
  const accepted = []
  for (const stem of [...new Set([...stems, ...listed])].sort()) {
    const r = await go({ fragments: frags(1), tree: TREE, agentType: `fz:${stem}` }, () => ok('PASS'))
    if (r.res.mode === 'workflow') accepted.push(stem)
  }
  expect(accepted.join(',') === listed.join(','), `행동으로 받는 agentType [${accepted}] ≠ 목록 [${listed}]`)
  const bad = accepted.map(stem => [stem, readOnlyWhy(path.join(dir, `${stem}.md`))]).filter(([, why]) => why)
  expect(!bad.length, `읽기 전용이 아닌 허용 에이전트 ${bad.map(([s, why]) => `fz:${s} — ${why}`).join(' · ')}`)
  return `허용 ${accepted.length}종 전부 읽기 전용 · agents ${stems.length}종 대조`
}

async function argsFallback(expect) {
  const base = { fragments: frags(2), tree: TREE }
  const one = extra => [Object.assign(frag('A'), extra)]
  const cases = [
    ['args 없음', undefined],
    ['빈 객체', {}],
    ['JSON 아닌 문자열', '{not json'],
    ['fragments 빈 배열', { fragments: [], tree: TREE }],
    ['tree 없음', { fragments: frags(2) }],
    ['상대 tree', Object.assign({}, base, { tree: 'tmp/pinned' })],
    ['id 중복', { fragments: [frag('A'), frag('A')], tree: TREE }],
    ['method 비어 있음', { fragments: one({ method: ' ' }), tree: TREE }],
    ['brief 없음', { fragments: one({ brief: undefined }), tree: TREE }],
    ['SHA 가 브랜치 이름', { fragments: one({ sha: 'main' }), tree: TREE }],
    ['SHA 둘', { fragments: [frag('A'), Object.assign(frag('B'), { sha: 'abcdef1' })], tree: TREE }],
    ['effort 밖', Object.assign({}, base, { effort: 'turbo' })],
    ['maxFragments 0', Object.assign({}, base, { maxFragments: 0 })],
    ['maxAgents 소수', Object.assign({}, base, { maxAgents: 2.5 })],
    ['concurrency 문자열', Object.assign({}, base, { concurrency: '3' })],
  ]
  for (const [name, args] of cases) {
    const r = await go(args, () => ok('PASS'))
    expect(r.res.mode === 'fallback' && r.calls.length === 0, `${name} → mode ${r.res.mode} · 콜 ${r.calls.length}`)
  }
  const str = await go(JSON.stringify(base), () => ok('PASS'))
  expect(str.res.mode === 'workflow' && str.calls.length === 2, `대조 JSON 문자열 args → mode ${str.res.mode} · 콜 ${str.calls.length}`)
  return `거부 ${cases.length}종 · 대조 1종`
}

;(async () => {
  if (!fs.existsSync(WF)) {
    for (const [name] of CASES) console.log(`${name}: FAIL workflows/swarm.js 없음 — ${WF}`)
    console.log('swarm-budget: FAIL')
    process.exit(1)
  }
  for (const [name, fn] of CASES) await kase(name, fn)
  console.log(failed ? `swarm-budget: FAIL ${failed}/${CASES.length} 케이스 실패` : 'swarm-budget: PASS')
  process.exit(failed ? 1 : 0)
})().catch(e => { console.log(`swarm-budget: FAIL 실행 오류 — ${e && e.message}`); process.exit(1) })
