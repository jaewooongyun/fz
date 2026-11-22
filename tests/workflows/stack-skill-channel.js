// 스택 스킬 요구 사항이 워커에게 닿는 통로 — 워커 전달 스킬 다섯이 `## 스택 스킬` 절에 적은 인자가 그 워크플로의 모든 단계 프롬프트에 실린다.
//   스택 스킬(대상 코드의 언어 · 프레임워크를 다루는 스킬)은 Lead 만 부를 수 있다 — 워커에는 Skill 도구가 없다. Lead 가 그 스킬이 이 변경에
//   요구하는 것을 기존 인자에 실어야 워커가 읽는다. 인자가 어느 단계 프롬프트에서 빠지면 그 단계 워커는 요구를 모른 채 코드를 쓰거나 판정한다.
//   통로는 기존 인자다 — 이 시험은 그 인자가 단계마다 실리는지와, 스킬 절이 그 통로의 인자를 가리키는지를 함께 본다. 워크플로가 인자를 공유
//   머리(CTX)로만 싣고 그 머리를 쓰지 않는 단계가 있으면 그 단계에 따로 싣는다(plan-collaborative 의 Stage 3 · 5 · discover-adversarial 의
//   첫 경로 생성 뒤 단계 — 인자가 비면 프롬프트 무변화).
// 셀(스킬마다 — 워크플로 · 인자 · 끝까지 돈 단계 수):
//   fz-code-channel    code-pair full  · contextPath(Step 맥락 파일 경로) · 4 (impl → arch ∥ quality → revise)
//   fz-fix-channel     code-pair light · contextPath(버그 분석 요약 파일) · 3 (impl → arch → revise)
//   fz-plan-channel    plan-lean2      · constraintsKnown(알려진 제약)     · 4 (전체 ∥ 적대 ∥ 영향 → 병합)
//   fz-plan-rollback-channel  plan-collaborative(fz-plan 의 롤백 경로) · constraintsKnown · 9 (방향 → 초안 → 영향 ∥ 경계 ∥ 아키 → 교차 둘 →
//                      통합 → 재검증) — 응답 표는 failure-injection.js 의 것을 쓴다 · Stage 3 두 콜과 Stage 5 가 호출 목록에 있어야 한다
//   fz-review-channel  review-live     · intentContext(의도 맥락)          · 5 (arch ∥ quality → 교차 둘 → counter)
//   fz-discover-channel       discover-adversarial lean · constraintsKnown · 5 (경로 → 비용 → 둘째 경로 → 둘째 비용 → 합성)
//   fz-discover-deep-channel  discover-adversarial deep · constraintsKnown · 6 (렌즈 셋 → 병합 → 경로별 비용 → 합성)
//   fz-discover-lump-channel  discover-adversarial deep 예산 축소 · constraintsKnown · 6 (렌즈 셋 → 병합 → 일괄 비용 → 합성)
//                      — 셋 다 응답 표는 failure-injection.js 의 것을 쓴다(병합 응답은 경로 하나라 경로별 비용은 cost:deep-0 하나다)
//   셀마다: 그 스킬의 `## 스택 스킬` 절이 인자 이름을 적었다 · 표식을 넣은 인자로 돌린 단계 수가 기대와 같다 · 단계마다 프롬프트에 표식이 있다
// 격자: fz-discover-known-grid — constraintsKnown {미전달 · 빈 배열 · 배열 아님 · 한 항목} × {lean · deep · deep 예산 축소} 에서 단계마다
//   `[기지 제약]` 줄(줄 머리 — OVERRIDE 문장 속 낱말은 세지 않는다)이 몇 번 실리는지 센다. 첫 경로 생성(r1-paths · lens:*)은 기존 줄 그대로 늘 1 · 그 뒤 단계는 한 항목 이상일 때만 1, 아니면 0
//   (프롬프트 무변화 — 제약을 준 실행만 캐시 열쇠가 바뀐다)
// 대조: no-marker-not-found — 표식을 넣지 않고 돌리면 어느 단계 프롬프트에도 표식이 없다(검사가 헛돌지 않는다)
// exit: 0 전건 통과 · 1 단언 실패 · 2 준비 실패(워크플로 · 스킬 파일 없음)
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')
const { SCENARIOS, callsOf } = require('./default-off-regression')
const { responder } = require('./failure-injection')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const MARK = 'STACK-SKILL-REQ-7f3a'   // 합성 표식 — 실제 스킬 이름이 아니다

let fail = 0, cells = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  cells += 1
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
const collab = async extra => (await run(path.join(ROOT, 'workflows', 'plan-collaborative.js'), {
  args: Object.assign({ requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }, extra), responder: responder([]) })).calls
const live = extra => callsOf(path.join(ROOT, 'workflows', 'review-live.js'), 'review-live', SCENARIOS['review-live'][0], extra)
// discover-adversarial 세 경로 — [args, 하너스 예산]. 렌즈 3 + 병합 4콜 × 21 = 84 를 쓰면 잔여 16 < 20% 라 경로별 평가가 일괄 1콜
//   (cost:deep-lump)로 준다 — 시작 때 잔여 100 ≥ 40% 라 deep 은 돈다(failure-injection.js 의 예산 변형과 같은 값)
const DISCOVER = { lean: [{}, {}], deep: [{ deep: true }, {}], lump: [{ deep: true }, { budgetTotal: 100, budgetPerCall: 21 }] }
const discover = async (mode, extra) => (await run(path.join(ROOT, 'workflows', 'discover-adversarial.js'), Object.assign({
  args: Object.assign({ problem: '합성 문제', codeContextPath: '/tmp/code-context.md' }, DISCOVER[mode][0], extra), responder: responder([]) },
  DISCOVER[mode][1]))).calls
const KNOWN_FORMS = { '미전달': {}, '빈 배열': { constraintsKnown: [] }, '배열 아님': { constraintsKnown: '합성 제약' }, '한 항목': { constraintsKnown: ['합성 제약'] } }
const firstGen = label => label === 'r1-paths' || String(label).startsWith('lens:')

const CELLS = [
  { skill: 'fz-code', arg: 'contextPath', stages: 4, calls: m => codePair('full', m ? `/tmp/${MARK}/step-context.md` : '/tmp/step-context.md') },
  { skill: 'fz-fix', arg: 'contextPath', stages: 3, calls: m => codePair('light', m ? `/tmp/${MARK}/bug-context.md` : '/tmp/bug-context.md') },
  { skill: 'fz-plan', arg: 'constraintsKnown', stages: 4, calls: m => lean2(m ? { constraintsKnown: [`${MARK} — 합성 요구`] } : {}) },
  { skill: 'fz-plan', name: 'fz-plan-rollback', arg: 'constraintsKnown', stages: 9, need: ['stage3-impact-on-edge', 'stage3-edge-on-impact', 'stage5-recheck'],
    calls: m => collab(m ? { constraintsKnown: [`${MARK} — 합성 요구`] } : {}) },
  { skill: 'fz-review', arg: 'intentContext', stages: 5, calls: m => live(m ? { intentContext: `합성 의도 · 참조 가이드: ${MARK}` } : {}) },
  { skill: 'fz-discover', arg: 'constraintsKnown', stages: 5, calls: m => discover('lean', m ? { constraintsKnown: [`${MARK} — 합성 요구`] } : {}) },
  { skill: 'fz-discover', name: 'fz-discover-deep', arg: 'constraintsKnown', stages: 6, need: ['merge', 'cost:deep-0', 'landscape'],
    calls: m => discover('deep', m ? { constraintsKnown: [`${MARK} — 합성 요구`] } : {}) },
  { skill: 'fz-discover', name: 'fz-discover-lump', arg: 'constraintsKnown', stages: 6, need: ['merge', 'cost:deep-lump', 'landscape'],
    calls: m => discover('lump', m ? { constraintsKnown: [`${MARK} — 합성 요구`] } : {}) },
]
const GRID_STAGES = { lean: 5, deep: 6, lump: 6 }

;(async () => {
  for (const c of CELLS) {
    const named = section(c.skill).includes('`' + c.arg + '`')
    const calls = await c.calls(true)
    const missing = calls.filter(k => !String(k.prompt).includes(MARK)).map(k => k.label)
    const unreached = (c.need || []).filter(l => !calls.some(k => k.label === l))
    check(`${c.name || c.skill}-channel`, named && calls.length === c.stages && missing.length === 0 && unreached.length === 0,
      `절에 \`${c.arg}\` ${named ? '있음' : '없음'} · 단계 ${calls.length}(기대 ${c.stages}: ${calls.map(k => k.label).join(',')}) · 표식 없는 단계 ${missing.join(',') || '-'}` +
      (unreached.length ? ` · 닿지 않은 단계 ${unreached.join(',')}` : ''))
  }
  const grid = []
  for (const mode of Object.keys(DISCOVER)) {
    for (const [form, extra] of Object.entries(KNOWN_FORMS)) {
      const calls = await discover(mode, extra)
      if (calls.length !== GRID_STAGES[mode]) grid.push(`${mode}·${form} 단계 ${calls.length}(기대 ${GRID_STAGES[mode]})`)
      for (const k of calls) {
        const n = String(k.prompt).split('\n[기지 제약] ').length - 1, want = firstGen(k.label) || form === '한 항목' ? 1 : 0
        if (n !== want) grid.push(`${mode}·${form}·${k.label} ${n}(기대 ${want})`)
      }
    }
  }
  check('fz-discover-known-grid', grid.length === 0, grid.slice(0, 4).join(' · ') + (grid.length > 4 ? ` 외 ${grid.length - 4}` : ''))
  const bare = (await Promise.all(CELLS.map(c => c.calls(false)))).flat()
  check('no-marker-not-found', bare.length > 0 && bare.every(k => !String(k.prompt).includes(MARK)), `단계 ${bare.length}`)
  console.log(fail ? `STACK_SKILL_CHANNEL_FAIL fail=${fail}` : `STACK_SKILL_CHANNEL_OK cells=${cells}`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`UNRUN  ${e && e.stack || e}`); process.exit(2) })
