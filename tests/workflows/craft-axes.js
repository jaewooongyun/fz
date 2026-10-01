// craft 6축 배선 (S16) — args.craftAxes 가 켜졌을 때만 arch 렌즈에 craft 줄 · axisCoverage(6축 필수) 스키마가 들어간다.
//
// ⛔ 워크플로를 통째로 가짜 런타임(tests/lib/wf_harness.js)에서 돌려 **실제 콜 입력**을 본다.
//    하네스의 calls 는 스키마를 불리언으로만 남기므로 responder 가 opts.schema 를 직접 잡는다.
// ⛔ FZ_WF_ROOT 로 다른 트리(기준 트리)를 같은 셀로 돌린다 — 그때는 FAIL 줄이 나와야 한다(기준에는 craftAxes 가 없다).
// ⛔ craft 축 목록은 네 곳이 같아야 한다: 두 워크플로의 CRAFT_AXES · modules/review-structural-axes.md §6 표 ·
//    품질 fixture 검사기의 AXES6(SC-4 채점 축). GPT 독립 리뷰 스키마는 S13(R-C)이 만든다 — 있으면 같이 대조하고, 없으면 SKIP 을 찍는다.
// ⛔ 옵션 미지정일 때 기준과 **바이트 단위로 같은지**는 tests/workflows/default-off-regression.js 가 본다 — 여기서는 켜진 쪽을 본다.
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = { 'peer-review': path.join(ROOT, 'workflows', 'peer-review.js'), 'review-live': path.join(ROOT, 'workflows', 'review-live.js') }
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }
const ADVISOR_BAN = 'advisor 도 호출하지 않는다'
const RULES = '/tmp/project-rules.records.json'

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)

// ⛔ 파일이 없으면 null — 던지지 않는다. 기준 트리에는 이 파일들이 없을 수 있고, 그때도 항목마다 FAIL 을 찍어야 판별이 보인다
function literalList(file, name) {
  if (!fs.existsSync(file)) return null
  const src = fs.readFileSync(file, 'utf8')
  const m = src.match(new RegExp(`^(?:const )?${name} = \\[([^\\]]*)\\]`, 'm'))
  return m ? (m[1].match(/'([^']*)'|"([^"]*)"/g) || []).map(s => s.slice(1, -1)) : null
}
function moduleAxes() {
  const file = path.join(ROOT, 'modules', 'review-structural-axes.md')
  if (!fs.existsSync(file)) return null
  const src = fs.readFileSync(file, 'utf8')
  const at = src.search(/^## 6\. /m)
  if (at < 0) return null
  const sec = src.slice(at).split(/\n## /)[0]
  return [...sec.matchAll(/^\| `([a-z_]+)` \|/gm)].map(m => m[1])
}
function findEnum(node, key) {
  if (!node || typeof node !== 'object') return null
  if (node[key] && Array.isArray(node[key].enum)) return node[key].enum
  for (const v of Object.values(node)) { const hit = findEnum(v, key); if (hit) return hit }
  return null
}

const AXIS_ROWS = axes => axes.map(axis => ({ axis, status: 'none', note: '해당 없음 — 합성' }))
function responder(wf, axes, captured) {
  const pr = {
    'stage1-arch': { issues: [{ id: 'A1', file: 'a.swift', line_range: '3', severity: 'minor', perspective: 'p', discoveryAxis: 'structure',
      origin: 'improvement', description: 'd', evidence: 'e', confidence: 90, craftAxis: 'naming' }],
      strengths: [], overall_assessment: 'o', axisCoverage: AXIS_ROWS(axes) },
    'stage1-quality': { issues: [], strengths: [], overall_assessment: 'o' },
    'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
    'stage2-arch-on-peers': { adjustments: [], additions: [] },
    'stage2-quality-on-peers': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedIssues: [] },
  }
  const rl = {
    'stage1-arch': { findings: [{ id: 'A1', severity: 'minor', category: 'c', title: 't', detail: 'd', evidence: 'e', craftAxis: 'placement' }],
      okAreas: [], axisCoverage: AXIS_ROWS(axes) },
    'stage1-quality': { findings: [], okAreas: [] },
    'stage2-arch-on-quality': { adjustments: [], additions: [] },
    'stage2-quality-on-arch': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedFindings: [] },
  }
  return (prompt, opts) => {
    captured.push({ label: opts.label, prompt, schema: opts.schema || null, model: opts.model, effort: opts.effort })
    const table = wf === 'peer-review' ? pr : rl
    return table[opts.label] ? JSON.parse(JSON.stringify(table[opts.label])) : null
  }
}
async function capture(wf, args, axes) {
  const calls = []
  const r = await run(WF[wf], { args: Object.assign({}, ARGS, args), responder: responder(wf, axes || [], calls) })
  return { calls, result: r.result }
}
const byLabel = (calls, label) => calls.find(c => c.label === label) || { prompt: '', schema: null }
const has = (schema, key) => JSON.stringify(schema || {}).includes(`"${key}"`)
const labels = calls => calls.map(c => c.label).sort().join(',')

;(async () => {
  // ── 1. craft 축 목록 — 네 곳(+ GPT 스키마가 있으면 다섯 곳)이 같다 ──
  const sources = {
    'peer-review.js CRAFT_AXES': literalList(WF['peer-review'], 'CRAFT_AXES'),
    'review-live.js CRAFT_AXES': literalList(WF['review-live'], 'CRAFT_AXES'),
    'review-structural-axes.md §6 표': moduleAxes(),
    'check_quality_fixtures.py AXES6': literalList(path.join(ROOT, 'scripts', 'check_quality_fixtures.py'), 'AXES6'),
  }
  const gptSchema = path.join(ROOT, 'schemas', 'gpt_independent_review_schema.json')
  if (fs.existsSync(gptSchema)) sources['gpt_independent_review_schema.json craftAxis'] = findEnum(JSON.parse(fs.readFileSync(gptSchema, 'utf8')), 'craftAxis')
  else console.log('SKIP  gpt_independent_review_schema.json 없음 — S13(R-C) 이 만든다. 생기면 이 테스트가 같이 대조한다')
  for (const [name, list] of Object.entries(sources)) check(`craft 축 목록 있음 — ${name}`, Array.isArray(list) && list.length === 6, JSON.stringify(list))
  const axes = sources['check_quality_fixtures.py AXES6'] || []
  for (const [name, list] of Object.entries(sources)) check(`craft 축 목록·순서 일치 — ${name} = AXES6`, same(list, axes), `${JSON.stringify(list)} ≠ ${JSON.stringify(axes)}`)

  for (const wf of ['peer-review', 'review-live']) {
    const extra = wf === 'peer-review' ? { deep: true } : {}
    // ── 2. 켜짐 · 규칙 없음 ──
    const on = await capture(wf, Object.assign({ craftAxes: true }, extra), axes)
    const arch = byLabel(on.calls, 'stage1-arch')
    const others = on.calls.filter(c => c.label !== 'stage1-arch')
    const archItems = wf === 'peer-review' ? arch.schema && arch.schema.properties.issues.items : arch.schema && arch.schema.properties.findings.items
    check(`${wf}: arch 스키마 required 에 axisCoverage`, !!arch.schema && arch.schema.required.includes('axisCoverage'), JSON.stringify(arch.schema && arch.schema.required))
    check(`${wf}: axisCoverage 축 enum = craft 축`, same(arch.schema && arch.schema.properties.axisCoverage && arch.schema.properties.axisCoverage.items.properties.axis.enum, axes), '축 enum 불일치')
    check(`${wf}: arch issue 에 craftAxis · ruleRef 선택 필드(required 아님)`,
      !!archItems && !!archItems.properties.craftAxis && !!archItems.properties.ruleRef && !archItems.required.includes('craftAxis') && !archItems.required.includes('ruleRef'),
      JSON.stringify(archItems && Object.keys(archItems.properties)))
    check(`${wf}: arch 밖 스키마에는 axisCoverage · craftAxis 가 없다(결함 축 회귀 방어)`, others.length > 0 && others.every(c => !has(c.schema, 'axisCoverage') && !has(c.schema, 'craftAxis')),
      others.filter(c => has(c.schema, 'axisCoverage') || has(c.schema, 'craftAxis')).map(c => c.label).join(','))
    check(`${wf}: craft 줄은 arch 프롬프트에만`, arch.prompt.includes('[craft 축 — 이 렌즈 전용]') && others.length > 0 && others.every(c => !c.prompt.includes('[craft 축')), 'craft 줄 위치')
    check(`${wf}: 규칙 레코드가 없으면 arch 에 '규칙 인용 지적 금지 — 코드 근거만'`, arch.prompt.includes('규칙 인용 지적 금지 — 코드 근거만') &&
      others.length > 0 && others.every(c => !c.prompt.includes('규칙 인용 지적 금지')), '규칙 부재 줄')
    const dist = on.result && on.result.distribution && on.result.distribution.craftAxes
    const hit = wf === 'peer-review' ? 'naming' : 'placement'
    check(`${wf}: distribution.craftAxes 집계 — ${hit} 1 · axisCoverage 6행 · 빠진 축 없음`, !!dist && dist.counts[hit] === 1 && Array.isArray(dist.axisCoverage) &&
      dist.axisCoverage.length === 6 && Array.isArray(dist.missingAxes) && dist.missingAxes.length === 0, JSON.stringify(dist))
    const dup = await capture(wf, Object.assign({ craftAxes: true }, extra), Array(6).fill(axes[0]))
    const dd = dup.result && dup.result.distribution && dup.result.distribution.craftAxes
    check(`${wf}: 같은 축 6행은 6축이 아니다 — missingAxes 가 나머지 5축`, !!dd && JSON.stringify(dd.missingAxes) === JSON.stringify(axes.slice(1)),
      JSON.stringify(dd && dd.missingAxes))
    check(`${wf}: 전 콜 opus · xhigh · advisor 금지 문구 유지`, on.calls.length > 0 && on.calls.every(c => c.model === 'opus' && c.effort === 'xhigh' && c.prompt.includes(ADVISOR_BAN)),
      on.calls.filter(c => !(c.model === 'opus' && c.effort === 'xhigh' && c.prompt.includes(ADVISOR_BAN))).map(c => c.label).join(','))
    if (wf === 'review-live') {
      const q = byLabel(on.calls, 'stage1-quality')
      const qItems = q.schema && q.schema.properties.findings.items
      check('review-live: craftAxes 만 켜면 Stage 1 에 위치 필드가 없다 — §3 병합 키는 locatedFindings 가 따로 켠다(S16c · located-findings.js)',
        !!archItems && !!qItems && [archItems, qItems].every(it => !it.properties.line_range && !it.properties.discoveryAxis),
        JSON.stringify(qItems && Object.keys(qItems.properties)))
    }
    // ── 3. 켜짐 · 규칙 레코드 있음 ──
    const rules = await capture(wf, Object.assign({ craftAxes: true, projectRulesPath: RULES }, extra), axes)
    const archR = byLabel(rules.calls, 'stage1-arch')
    check(`${wf}: projectRulesPath → arch 에만 규칙 줄 · 부재 줄은 사라진다`, archR.prompt.includes(`[프로젝트 규칙 — 이 렌즈 전용] ${RULES}`) &&
      !archR.prompt.includes('규칙 인용 지적 금지') && rules.calls.length > 1 && rules.calls.filter(c => c.label !== 'stage1-arch').every(c => !c.prompt.includes(RULES)), '규칙 줄 위치')
    // ── 4. 꺼짐 — 하위 옵션을 넘겨도 craft 가 켜지지 않는다(⛔ peer-review 는 기본 on 이라 끈 경로를 명시 false 로 부른다) ──
    const sub = await capture(wf, Object.assign({ craftAxes: false, projectRulesPath: RULES }, extra), axes)
    check(`${wf}: craftAxes:false 와 projectRulesPath → craft·규칙 줄 없음 · axisCoverage 없음`,
      sub.calls.length > 0 && sub.calls.every(c => !c.prompt.includes('[craft 축') && !c.prompt.includes('[프로젝트 규칙') && !has(c.schema, 'axisCoverage')), '하위 옵션이 새었다')
    // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 보지 못한다(빈 배열의 every 는 참이다)
    check(`${wf}: 켠 실행 · 규칙 실행 · 끈 실행의 콜 구성(label 다중집합)이 같다`, labels(on.calls) === labels(sub.calls) && labels(rules.calls) === labels(sub.calls),
      `켬 ${labels(on.calls)} · 규칙 ${labels(rules.calls)} · 끔 ${labels(sub.calls)}`)
  }

  console.log(`\ncraft 축 배선 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
