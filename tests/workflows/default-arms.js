// 워크플로별 기본 arm (R-C · v4.42.0) — 기본값이 측정 판정과 맞는가: 합격한 arm 만 기본 on 이다.
//
// ⛔ 실제 기본값은 **실행으로** 잰다 — default-off-regression.js 의 레지스트리 · 경로 · 하네스를 재사용해 옵션마다
//    미지정 실행이 켠 실행과 같으면 on, 끈 실행과 같으면 off 다. 어느 쪽과도 다르면 판정 불가(FAIL).
//    켬 == 끔 인 경로(applies 거짓 · 구조 옵션이 발화하지 않는 응답)는 기본값을 말하지 못해 건너뛴다 —
//    대신 옵션마다 판정한 경로가 **하나 이상** 있어야 한다(증거 없는 통과 방지).
// ⛔ 한 워크플로의 옵션은 묶음이다 — 측정 arm(S25 C)이 옵션을 한꺼번에 켰다. 묶음 안에서 on · off 가 섞이면 FAIL.
// 기대값: --expect-from <A/B 원장 jsonl> 이면 원장 판정 — ab_ledger.py judge 를 게이트와 **같은 기준**으로 불러 exit 0 이면 on,
//    1(미달)이면 off 다. 2(판정 불가)는 '판정 불가' 로 돌려줘 그 워크플로가 FAIL 한다 — off 로 읽으면 빈 원장 · 깨진 원장에서도
//    기본값 대조가 통과한다(판정 불가가 통과로 샌다). 이때 v3.5 결정 표도 원장과 같아야 한다.
//    인자가 없으면 결정 표와 대조한다(health-check 러너가 인자 없이 돈다).
//    ⛔ 기준을 바꾸면 게이트 CHECK 도 같이 바꾼다: peer-review = S25p · review-live = S25(fz-review) · plan-lean2 = S26 첫 judge.
// exit: 0 일치 · 1 불일치 · 2 실행 불가(판정기를 부를 수 없음)
'use strict'
const path = require('path')
const { execFileSync } = require('child_process')
const { OPTIONS, SCENARIOS, callsOf, firstDiff } = require('./default-off-regression')

const ROOT = path.join(__dirname, '..', '..')
const S25 = 'SC-3,SC-4,SC-6,SC-7,AC-1,AC-4,AC-5,AC-7,crossover-order,blind-labels'
// decided = 계획 v3.5 #2 결정(사용자 2026-09-30) · judge = 그 결정의 근거가 된 게이트의 판정 인자
const ARMS = {
  'peer-review': { decided: 'on', gate: 'S25p', judge: ['--workflow', 'fz-peer-review', '--require', S25] },
  'review-live': { decided: 'off', gate: 'S25', judge: ['--workflow', 'fz-review', '--require', S25] },
  'plan-lean2': { decided: 'off', gate: 'S26', judge: ['--workflow', 'fz-plan', '--require', 'SC-3,SC-5,SC-6,SC-7,AC-1,AC-5,AC-7'] },
}

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

function fromLedger(ledger, arm) {
  try {
    execFileSync('python3', [path.join(ROOT, 'scripts', 'ab_ledger.py'), 'judge', '--ledger', ledger, ...arm.judge], { stdio: 'ignore' })
    return { value: 'on', exit: 0 }
  } catch (e) {
    if (e.status === 1) return { value: 'off', exit: 1 }
    if (e.status === 2) return { value: '판정 불가', exit: 2 }
    throw Object.assign(new Error(`판정기를 부르지 못했다 — ${e.message.split('\n')[0]}`), { unrun: true })
  }
}

async function actual(wf) {
  const file = path.join(ROOT, 'workflows', `${wf}.js`)
  const byOption = {}
  for (const [name, opt] of Object.entries(OPTIONS)) {
    if (!opt.workflows.includes(wf)) continue
    const seen = new Set()
    for (const sc of SCENARIOS[wf]) {
      if (opt.applies && !opt.applies(sc)) continue
      const [unset, on, off] = [await callsOf(file, wf, sc, {}), await callsOf(file, wf, sc, opt.on), await callsOf(file, wf, sc, opt.off)]
      if (firstDiff(on, off) === null) continue   // 이 경로에는 옵션이 닿지 않는다
      seen.add(firstDiff(unset, on) === null ? 'on' : firstDiff(unset, off) === null ? 'off' : '판정 불가')
    }
    byOption[name] = [...seen]
  }
  return byOption
}

;(async () => {
  const argv = process.argv.slice(2)
  const i = argv.indexOf('--expect-from')
  const ledger = i >= 0 ? argv[i + 1] : null
  if (i >= 0 && !ledger) { console.log('UNRUN  --expect-from 은 원장 경로가 필요하다'); process.exit(2) }
  for (const [wf, arm] of Object.entries(ARMS)) {
    const byOption = await actual(wf)
    const names = Object.keys(byOption)
    const values = [...new Set(names.flatMap(n => byOption[n]))]
    const got = values.length === 1 ? values[0] : `섞임 ${JSON.stringify(byOption)}`
    const unjudged = names.filter(n => byOption[n].length === 0)
    check(`${wf}: 옵션 ${names.length}개가 판정한 경로마다 한 가지 기본값이다`,
      names.length > 0 && !unjudged.length && values.length === 1 && values[0] !== '판정 불가',
      !names.length ? '레지스트리에 옵션이 없다' : unjudged.length ? `판정할 경로가 없는 옵션 ${unjudged.join(', ')}` : JSON.stringify(byOption))
    if (ledger) {
      const ex = fromLedger(ledger, arm)
      check(`${wf}: 실제 기본 ${got} == 원장 판정(${arm.gate} judge exit ${ex.exit}) ${ex.value}`, got === ex.value, `실제 ${got}`)
      check(`${wf}: 결정 표(v3.5) ${arm.decided} == 원장 판정 ${ex.value}`, arm.decided === ex.value, `결정 ${arm.decided}`)
    } else {
      check(`${wf}: 실제 기본 ${got} == 결정 표(v3.5) ${arm.decided}`, got === arm.decided, `실제 ${got}`)
    }
  }
  console.log(`\n기본 arm ${fail ? '불일치 ' + fail + '건' : '전건 일치'}${ledger ? ' (원장 대조)' : ' (결정 표 대조)'}`)
  process.exit(fail ? 1 : 0)
// ⛔ exit 2 는 머리말 계약(판정기를 부를 수 없음)일 때만이다 — 워크플로 실행 중 예외까지 UNRUN 으로 내보내면
//    health-check 3분 판정(UNRUN 표지 exit 2 = 미실행)이 crash 를 미실행으로 센다
})().catch(e => {
  if (e.unrun) { console.log(`UNRUN  ${e.message}`); process.exit(2) }
  console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1)
})
