// code-pair changeset 적용 전 검사 (F-120 · F-551 · F-231) — 가짜 런타임에서 code-pair 를 통째로 돌려 본다.
//   Stage 1 결함은 검토 이슈(D…)로 Stage 3 에 들어가고(light 포함), 최종 changeset 에 남으면 fallback 'changeset-defect' 다.
// 셀:
//   span-mismatch-sent-to-revise      full · 검토 pass 인데 spanLines ≠ oldAnchor 줄 수 → Stage 3 프롬프트에 D1 · 수정본 반환
//   escape-introduced-sent-to-revise  newBody 에만 태그 앞 역슬래시('<\task-notification>') → D1(F-551) · 수정본 반환
//   defect-remaining-fallback         Stage 3 수정본에도 결함 → { mode:'fallback', reason:'changeset-defect', defects }
//   escape-already-in-anchor-ok       oldAnchor 에 같은 꼴이 같은 수 → 결함 아님 · Stage 3 없음
//   create-without-anchor-ok          create · oldAnchor 없음 · spanLines 아무 값 → span 면제
//   delete-without-anchor-ok          delete 도 면제
//   clean-changeset-unchanged         깨끗한 changeset · 검토 pass → 콜 3개(Stage 3 없음) · 원안 그대로 · residualIssues []
//   light-no-review-defect-revise     light · complexity 1(검토 생략)이어도 결함이면 Stage 3
//   missing-field-is-defect           newBody · spanLines 누락 → TypeError 없이 결함 → Stage 3
//   regex-heredoc-not-defect          '[^<\n' 문자 클래스 · '<<\EOF' heredoc 은 결함 아님
//   numstat-oracle-matches-span       적용 오라클의 산술 항등식만 — git diff --numstat 증감 = Σ(newBody 줄 − spanLines). code-pair 를 부르지 않아
//                                     되돌림 감도가 없다(Lead 절차 문서의 식이 맞는지만 본다 — 리뷰 Q-3)
//   apply-oracle-doc-contract         적용 오라클 문서 계약 — skills/*/SKILL.md 에 'oldAnchor 0회'(삽입 · 감싸기에서 틀린 지시) 0건 ·
//                                     fz-code 절차 4 에 적용 전 앵커 1회 · Step 직전 numstat · 심볼 편집 제외 · fz-fix 는 fz-code 를 가리킨다
//   f120-span-lines-mismatch          F-120 재현 모양 — 앵커 1줄 · spanLines 2 · 끝 줄바꿈 앵커 'a\nb\n' 에 spanLines 3 → 결함 · Stage 3 /
//                                     끝 줄바꿈 하나는 줄로 세지 않는다('a\nb\n' · spanLines 2 → 결함 아님)
//   f558-valid-escape-not-counted     정상 소스의 '<\/'(JS 문자열 · 정규식) · r"<\w+>" 는 이스케이프로 세지 않는다 — Stage 3 없음
// ⛔ 구판(검사 없는 code-pair)에서는 결함 셀이 FAIL 이다 — FZ_WF_ROOT 로 기준 트리를 대상으로 돌린다.
// exit: 0 전건 통과 · 1 단언 실패
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'code-pair.js')
const CELLS = ['span-mismatch-sent-to-revise', 'escape-introduced-sent-to-revise', 'defect-remaining-fallback', 'escape-already-in-anchor-ok',
  'create-without-anchor-ok', 'delete-without-anchor-ok', 'clean-changeset-unchanged', 'light-no-review-defect-revise',
  'missing-field-is-defect', 'regex-heredoc-not-defect', 'numstat-oracle-matches-span', 'apply-oracle-doc-contract',
  'f120-span-lines-mismatch', 'f558-valid-escape-not-counted']

const args = (mode, complexity) => ({ mode, stepSpec: { id: 'S1', title: 't', goal: 'g', files: ['a.js'], verify: { kind: 'manual', criterion: 'c' }, complexity },
  contextPath: '/tmp/c.md', changesetTarget: 'repo' })
const edit = o => Object.assign({ symbol: 'f', intent: 'i', newBody: 'x', spanLines: 0 }, o)
const cs = (edits, changeKind = 'modify') => ({ files: [{ path: 'a.js', changeKind, symbolEdits: edits, rationale: 'r' }], summary: 's', buildExpectation: 'b' })
const CLEAN = cs([edit({ oldAnchor: 'a\nb', newBody: 'x\ny\nz', spanLines: 2 })])
const PASS = { verdict: 'pass', issues: [] }
const responder = table => (prompt, opts) => (table[opts.label] === undefined ? null : JSON.parse(JSON.stringify(table[opts.label])))

const ran = []
let fail = 0
function check(name, cond, got) {
  ran.push(name)
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}
const labels = r => r.calls.map(c => c.label).join(',')
const stage3Prompt = r => (r.calls.find(c => c.label === 'stage3-revise') || {}).prompt || ''
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)

;(async () => {
  let r = await run(WF, { args: args('full', 3), responder: responder({
    'stage1-impl': cs([edit({ oldAnchor: 'a\nb\nc', newBody: 'x', spanLines: 1 })]),
    'stage2-review-arch': PASS, 'stage2-review-quality': PASS, 'stage3-revise': CLEAN }) })
  check('span-mismatch-sent-to-revise', labels(r).endsWith('stage3-revise') && stage3Prompt(r).includes('"id":"D1"')
    && stage3Prompt(r).includes('spanLines 1 ≠ oldAnchor 3줄') && r.result.mode === 'workflow' && same(r.result.changeset, CLEAN),
  `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': cs([edit({ oldAnchor: 'x <task-notification>', newBody: 'x <\\task-notification>', spanLines: 1 })]), 'stage3-revise': CLEAN }) })
  check('escape-introduced-sent-to-revise', stage3Prompt(r).includes('F-551') && r.result.mode === 'workflow' && same(r.result.changeset, CLEAN),
    `${labels(r)} · mode ${r.result && r.result.mode}`)

  const BAD = cs([edit({ oldAnchor: 'a\nb\nc', newBody: 'x', spanLines: 1 })])
  r = await run(WF, { args: args('light', 1), responder: responder({ 'stage1-impl': BAD, 'stage3-revise': BAD }) })
  check('defect-remaining-fallback', r.result.mode === 'fallback' && r.result.reason === 'changeset-defect'
    && Array.isArray(r.result.defects) && r.result.defects.length === 1, JSON.stringify(r.result).slice(0, 200))

  r = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': cs([edit({ oldAnchor: 'print("a <\\n b")', newBody: 'print("c <\\n d")', spanLines: 1 })]) }) })
  check('escape-already-in-anchor-ok', labels(r) === 'stage1-impl' && r.result.mode === 'workflow', `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('light', 1), responder: responder({ 'stage1-impl': cs([edit({ symbol: 'FILE', newBody: 'l1\nl2', spanLines: 5 })], 'create') }) })
  check('create-without-anchor-ok', labels(r) === 'stage1-impl' && r.result.mode === 'workflow', `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('light', 1), responder: responder({ 'stage1-impl': cs([edit({ symbol: 'FILE', newBody: '', spanLines: 3 })], 'delete') }) })
  check('delete-without-anchor-ok', labels(r) === 'stage1-impl' && r.result.mode === 'workflow', `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('full', 3), responder: responder({ 'stage1-impl': CLEAN, 'stage2-review-arch': PASS, 'stage2-review-quality': PASS }) })
  check('clean-changeset-unchanged', labels(r) === 'stage1-impl,stage2-review-arch,stage2-review-quality' && r.result.mode === 'workflow'
    && same(r.result.changeset, CLEAN) && same(r.result.residualIssues, []), `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('light', 1), responder: responder({ 'stage1-impl': BAD, 'stage3-revise': CLEAN }) })
  check('light-no-review-defect-revise', labels(r) === 'stage1-impl,stage3-revise' && r.result.mode === 'workflow', `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': { files: [{ path: 'a.js', changeKind: 'modify', symbolEdits: [{ symbol: 'f', intent: 'i' }], rationale: 'r' }], summary: 's', buildExpectation: 'b' },
    'stage3-revise': CLEAN }) })
  check('missing-field-is-defect', stage3Prompt(r).includes('필수 필드 누락 newBody,spanLines') && r.result.mode === 'workflow',
    `${labels(r)} · mode ${r.result && r.result.mode}`)

  r = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': cs([edit({ oldAnchor: 'x', newBody: 'const re = /[^<\\n]+/\ncat <<\\EOF', spanLines: 1 })]) }) })
  check('regex-heredoc-not-defect', labels(r) === 'stage1-impl' && r.result.mode === 'workflow', `${labels(r)} · mode ${r.result && r.result.mode}`)

  // 적용 오라클(fz-code 절차 4) — 편집 두 개를 실제로 적용하고 numstat 증감을 Σ(newBody 줄 − spanLines) 와 맞춘다
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-numstat-'))
  try {
    const before = 'head\na\nb\nc\nmid\ntail\n'
    const edits = [edit({ oldAnchor: 'a\nb\nc', newBody: 'x\ny\nz\nw\nv', spanLines: 3 }), edit({ oldAnchor: 'tail', newBody: 't1\nt2', spanLines: 1 })]
    let after = before
    for (const e of edits) after = after.replace(e.oldAnchor, e.newBody)
    fs.writeFileSync(path.join(tmp, 'old.txt'), before)
    fs.writeFileSync(path.join(tmp, 'new.txt'), after)
    const p = spawnSync('git', ['diff', '--no-index', '--numstat', 'old.txt', 'new.txt'], { cwd: tmp, encoding: 'utf8' })
    const [add, del] = (p.stdout.trim().split(/\s+/) || []).map(Number)
    const lines = s => (s === '' ? 0 : s.replace(/\n$/, '').split('\n').length)
    const want = edits.reduce((s, e) => s + lines(e.newBody) - e.spanLines, 0)
    check('numstat-oracle-matches-span', p.status === 1 && add - del === want && want === 3, `numstat ${p.stdout.trim()} · Σ ${want} · status ${p.status}`)
  } finally { fs.rmSync(tmp, { recursive: true, force: true }) }

  // 적용 오라클은 Lead 가 읽고 따르는 절차라 실행 시험이 없다 — 틀린 지시가 되살아나거나 고친 조건이 빠지면 여기서 실패한다
  const skills = path.join(ROOT, 'skills')
  const stale = fs.readdirSync(skills).filter(d => fs.existsSync(path.join(skills, d, 'SKILL.md'))
    && fs.readFileSync(path.join(skills, d, 'SKILL.md'), 'utf8').includes('oldAnchor 0회'))
  const code = fs.readFileSync(path.join(skills, 'fz-code', 'SKILL.md'), 'utf8')
  const fix = fs.readFileSync(path.join(skills, 'fz-fix', 'SKILL.md'), 'utf8')
  const need = ['**적용 전** 파일에 oldAnchor 1회', '이 Step 적용 직전에 잰', 'replace_symbol_body 편집이 섞인 파일은 numstat 을 대조하지 않는다']
  const lack = need.filter(s => !code.includes(s))
  check('apply-oracle-doc-contract', stale.length === 0 && lack.length === 0 && fix.includes('fz-code 절차 4 그대로'),
    `stale ${stale.join(',') || '-'} · fz-code 누락 ${lack.join(' | ') || '-'} · fz-fix 위임 ${fix.includes('fz-code 절차 4 그대로')}`)

  // F-120 — 시작 줄만 준 앵커(1줄)로 두 줄을 바꾸겠다는 편집 · 끝 줄바꿈 변형
  r = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': cs([edit({ oldAnchor: 'L372', newBody: 'n1\nn2', spanLines: 2 }), edit({ oldAnchor: 'a\nb\n', newBody: 'x', spanLines: 3 })]),
    'stage3-revise': CLEAN }) })
  const r120 = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': cs([edit({ oldAnchor: 'a\nb\n', newBody: 'x\ny', spanLines: 2 })]) }) })
  check('f120-span-lines-mismatch', stage3Prompt(r).includes('spanLines 2 ≠ oldAnchor 1줄') && stage3Prompt(r).includes('spanLines 3 ≠ oldAnchor 2줄')
    && r.result.mode === 'workflow' && labels(r120) === 'stage1-impl' && r120.result.mode === 'workflow',
  `${labels(r)} · 끝 줄바꿈 대조 ${labels(r120)}`)

  // F-558 — 정상 소스의 '<\/' 는 JSON 이중 이스케이프가 아니다
  r = await run(WF, { args: args('light', 1), responder: responder({
    'stage1-impl': cs([edit({ symbol: 'FILE', newBody: "const re = /<\\/div>/\nconst s = '<\\/script>'\nconst p = r\"<\\w+>\"", spanLines: 0 })], 'create') }) })
  check('f558-valid-escape-not-counted', labels(r) === 'stage1-impl' && r.result.mode === 'workflow', `${labels(r)} · mode ${r.result && r.result.mode}`)

  const setOk = ran.join(',') === CELLS.join(',')
  console.log(`${setOk ? 'PASS' : 'FAIL'}  cell-set: 판정한 셀 = 기대 셀(${CELLS.length})`)
  if (!setOk) fail += 1
  console.log(`\nchangeset 검사 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
