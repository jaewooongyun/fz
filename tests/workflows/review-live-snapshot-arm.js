// review-live 사전 수집 스냅샷 arm (S22b) — args.snapshotDir 를 주면 Stage 1 두 렌즈 프롬프트에만 경로와 '스냅샷 우선' 1줄이 한 번 들어간다.
//
// ⛔ 기본 off — 미지정 · 빈 문자열이면 표지가 없다. 콜 입력의 바이트 동일은 default-off-regression.js 가 본다.
// ⛔ 교차 · counter 는 Stage 1 산출을 보므로 스냅샷 줄을 받지 않는다(계획 S22b — Stage 1 프롬프트 한정).
// ⛔ FZ_WF_ROOT 로 기준 트리를 같은 셀로 돌리면 FAIL 줄이 나와야 한다(기준은 snapshotDir 를 모른다).
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'review-live.js')
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }
const MARK = '[사전 수집 스냅샷]'
const DIR = '/tmp/fz-snapshot-arm-7'
const TABLE = {
  'stage1-arch': { findings: [{ id: 'A1', severity: 'minor', category: 'c', title: 't', detail: 'd', evidence: 'e' }], okAreas: ['ok'] },
  'stage1-quality': { findings: [], okAreas: [] },
  'stage2-arch-on-quality': { adjustments: [], additions: [] },
  'stage2-quality-on-arch': { adjustments: [], additions: [] },
  'stage3-counter': { challenges: [], missedFindings: [] },
}

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}
async function calls(extra) {
  const out = []
  await run(WF, { args: Object.assign({}, ARGS, extra), responder: (prompt, opts) => {
    out.push({ label: opts.label, prompt })
    return TABLE[opts.label] ? JSON.parse(JSON.stringify(TABLE[opts.label])) : null
  } })
  return out
}
const count = (s, t) => s.split(t).length - 1
const labels = cs => cs.map(c => c.label).sort().join(',')

;(async () => {
  const unset = await calls({})
  check('미지정: 어느 콜에도 스냅샷 표지가 없다', unset.length === 5 && unset.every(c => !c.prompt.includes(MARK)), `콜 ${unset.length}개`)
  const blank = await calls({ snapshotDir: '  ' })
  check('빈 문자열: 미지정과 같다(표지 없음)', blank.length === 5 && blank.every(c => !c.prompt.includes(MARK)), `콜 ${blank.length}개`)
  const on = await calls({ snapshotDir: DIR })
  const s1 = on.filter(c => c.label.startsWith('stage1-'))
  check('지정: Stage 1 두 콜 프롬프트에 표지와 경로가 한 번씩', s1.length === 2 && s1.every(c => count(c.prompt, MARK) === 1 && count(c.prompt, DIR) === 1),
    s1.map(c => `${c.label}:${count(c.prompt, MARK)}/${count(c.prompt, DIR)}`).join(','))
  const rest = on.filter(c => !c.label.startsWith('stage1-'))
  check('지정: 교차 · counter 프롬프트에는 스냅샷 줄이 없다', rest.length === 3 && rest.every(c => !c.prompt.includes(MARK)), rest.map(c => c.label).join(','))
  check('지정: 콜 구성(label 다중집합)이 미지정과 같다', labels(on) === labels(unset), `켬 ${labels(on)} · 끔 ${labels(unset)}`)
  console.log(`\nreview-live 스냅샷 arm ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
