// 스택 스킬 요구 사항이 워커에게 닿는 통로 — 워커 전달 스킬 넷이 `## 스택 스킬` 절에 적은 인자가 그 워크플로의 모든 단계 프롬프트에 실린다.
//   스택 스킬(대상 코드의 언어 · 프레임워크를 다루는 스킬)은 Lead 만 부를 수 있다 — 워커에는 Skill 도구가 없다. Lead 가 그 스킬이 이 변경에
//   요구하는 것을 기존 인자에 실어야 워커가 읽는다. 인자가 어느 단계 프롬프트에서 빠지면 그 단계 워커는 요구를 모른 채 코드를 쓰거나 판정한다.
//   워크플로 파일은 고치지 않는다 — 이 시험은 지금의 통로가 단계마다 실리는지와, 스킬 절이 그 통로의 인자를 가리키는지를 함께 본다.
// 셀(스킬마다 — 워크플로 · 인자 · 끝까지 돈 단계 수):
//   fz-code-channel    code-pair full  · contextPath(Step 맥락 파일 경로) · 4 (impl → arch ∥ quality → revise)
//   fz-fix-channel     code-pair light · contextPath(버그 분석 요약 파일) · 3 (impl → arch → revise)
//   fz-plan-channel    plan-lean2      · constraintsKnown(알려진 제약)     · 4 (전체 ∥ 적대 ∥ 영향 → 병합)
//   fz-review-channel  review-live     · intentContext(의도 맥락)          · 5 (arch ∥ quality → 교차 둘 → counter)
//   셀마다: 그 스킬의 `## 스택 스킬` 절이 인자 이름을 적었다 · 표식을 넣은 인자로 돌린 단계 수가 기대와 같다 · 단계마다 프롬프트에 표식이 있다
// 대조: no-marker-not-found — 표식을 넣지 않고 돌리면 어느 단계 프롬프트에도 표식이 없다(검사가 헛돌지 않는다)
// exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(워크플로 · 스킬 파일 없음)
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')
const { SCENARIOS, callsOf } = require('./default-off-regression')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const MARK = 'STACK-SKILL-REQ-7f3a'   // 합성 표식 — 실제 스킬 이름이 아니다

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

function section(skill) {
  const p = path.join(ROOT, 'skills', skill, 'SKILL.md')
  if (!fs.existsSync(p)) { console.log(`UNRUN  ${p} 없음`); process.exit(2) }
  const t = fs.readFileSync(p, 'utf8')
  const m = t.match(/^## 스택 스킬[^\n]*\n([\s\S]*?)(?=^## |$(?![\s\S]))/m)
  return m ? m[1] : ''
}

// code-pair 를 검토 뒤 수정 단계까지 돌린다 — Stage 1 changeset 의 spanLines 가 앵커 줄 수와 달라 결함이 수정 단계로 간다
const edit = o => Object.assign({ symbol: 'f', intent: 'i', newBody: 'x', spanLines: 0 }, o)
const cs = e => ({ files: [{ path: 'a.js', changeKind: 'modify', symbolEdits: [edit(e)], rationale: 'r' }], summary: 's', buildExpectation: 'b' })
const PASS = { verdict: 'pass', issues: [] }
async function codePair(mode, contextPath) {
  const table = { 'stage1-impl': cs({ oldAnchor: 'a\nb\nc', newBody: 'x', spanLines: 1 }), 'stage2-review-arch': PASS,
    'stage2-review-quality': PASS, 'stage2-review': PASS, 'stage3-revise': cs({ oldAnchor: 'a\nb', newBody: 'x\ny', spanLines: 2 }) }
  const r = await run(path.join(ROOT, 'workflows', 'code-pair.js'), {
    args: { mode, stepSpec: { id: 'S1', title: 't', goal: 'g', files: ['a.js'], verify: { kind: 'manual', criterion: 'c' }, complexity: 3 },
      contextPath, changesetTarget: 'repo' },
    responder: (p, o) => (table[o.label] === undefined ? null : JSON.parse(JSON.stringify(table[o.label]))),
  })
  return r.calls
}
const lean2 = extra => callsOf(path.join(ROOT, 'workflows', 'plan-lean2.js'), 'plan-lean2', SCENARIOS['plan-lean2'][0], extra)
const live = extra => callsOf(path.join(ROOT, 'workflows', 'review-live.js'), 'review-live', SCENARIOS['review-live'][0], extra)

const CELLS = [
  { skill: 'fz-code', arg: 'contextPath', stages: 4, calls: m => codePair('full', m ? `/tmp/${MARK}/step-context.md` : '/tmp/step-context.md') },
  { skill: 'fz-fix', arg: 'contextPath', stages: 3, calls: m => codePair('light', m ? `/tmp/${MARK}/bug-context.md` : '/tmp/bug-context.md') },
  { skill: 'fz-plan', arg: 'constraintsKnown', stages: 4, calls: m => lean2(m ? { constraintsKnown: [`${MARK} — 합성 요구`] } : {}) },
  { skill: 'fz-review', arg: 'intentContext', stages: 5, calls: m => live(m ? { intentContext: `합성 의도 · 참조 가이드: ${MARK}` } : {}) },
]

;(async () => {
  for (const c of CELLS) {
    const named = section(c.skill).includes('`' + c.arg + '`')
    const calls = await c.calls(true)
    const missing = calls.filter(k => !String(k.prompt).includes(MARK)).map(k => k.label)
    check(`${c.skill}-channel`, named && calls.length === c.stages && missing.length === 0,
      `절에 \`${c.arg}\` ${named ? '있음' : '없음'} · 단계 ${calls.length}(기대 ${c.stages}: ${calls.map(k => k.label).join(',')}) · 표식 없는 단계 ${missing.join(',') || '-'}`)
  }
  const bare = (await Promise.all(CELLS.map(c => c.calls(false)))).flat()
  check('no-marker-not-found', bare.length > 0 && bare.every(k => !String(k.prompt).includes(MARK)), `단계 ${bare.length}`)
  console.log(fail ? `STACK_SKILL_CHANNEL_FAIL fail=${fail}` : `STACK_SKILL_CHANNEL_OK cells=${CELLS.length + 1}`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`UNRUN  ${e && e.stack || e}`); process.exit(2) })
