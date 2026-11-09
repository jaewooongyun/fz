// 워커 effort 전달 — 8개 워크플로가 args.effort(Lead 세션 effort)를 모든 콜에 싣고, 미지정이면 'xhigh' 로 기준 트리와 같다.
//   셀(워크플로마다): ① effort 'high' → 실행된 전 콜 effort 'high' · 콜 구성(label)은 미지정과 같다
//                     ② 허용값 밖('turbo') → { mode: 'fallback' } · 콜 0
//                     ③ 미지정 → 전 콜 'xhigh' · 콜 입력(label · agentType · model · effort · schema · prompt)이 기준 트리와 바이트 동일
//                        (기본 on 옵션이 있는 워크플로는 그 옵션을 모두 끈 롤백 경로로 대조하고, 기본 경로는 ③b 미지정 == 'xhigh' 명시)
// ⛔ effort 는 품질 옵션 묶음(default-off-regression.js OPTIONS)이 아니라 **별도 축**이다 — 그 레지스트리에 넣으면
//    default-arms.js 가 옵션 on/off 섞임으로 판정한다. 이 파일이 축을 본다(modules/mode-gate.md § effort) — 단 swarm.js 는 tests/workflows/swarm-budget.js 가 본다
//    (sha-missing-respawn: 미지정 xhigh · opus-concurrency: high 전달 · args-fallback: turbo → 콜 0). ③ 기준 SHA 에 swarm.js 가 없어 MIN_ARGS 에 넣으면 UNRUN 이다.
// ⛔ 콜이 실제로 effort 식별자를 쓰는지(리터럴이 남지 않았는지)는 lint-model-explicit.sh --baseline 이 정적으로 본다 — 여기서는 런타임 전달을 본다.
// 기준 소스: env FZ_EFFORT_BASE_TREE 의 workflows/ → 없으면 이 저장소 이력의 `git show ${FZ_EFFORT_BASE_SHA:-26c42d3}:workflows/<wf>.js`.
//   둘 다 없으면 ③ 의 기준 대조는 UNRUN(exit 2) 이다 — 통과가 아니다.
// ⛔ FZ_WF_ROOT 로 기준 트리를 대상으로 돌리면 ① · ② 가 FAIL 이어야 한다(기준은 effort 를 읽지 않는다).
// code-pair 스키마(S7): code-pair-schema-intended-only — 콜 스키마(키 정렬 JSON) == 기준 스키마 + 의도한 변환(spanLines · required · oldAnchor 설명).
//   대조군 schema-compare-detects-{unrelated-field,required-change,description-change} — 그 셋을 바꾼 사본은 비교에서 떨어져야 한다.
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')
const { SCENARIOS, BASE_ARGS, firstDiff, OPTIONS } = require('./default-off-regression')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const BASE_SHA = process.env.FZ_EFFORT_BASE_SHA || '26c42d3'

// 최소 유효 args — 첫 단계 콜이 나갈 만큼만. 응답이 null 이면 그 워크플로는 첫 단계에서 멈춘다(그래도 첫 단계 콜의 effort 는 보인다)
const MIN_ARGS = {
  'code-pair': { mode: 'full', stepSpec: { id: 'S1', title: 't', goal: 'g', files: ['a'], verify: { kind: 'manual', criterion: 'c' }, complexity: 3 },
    contextPath: '/tmp/context.md', changesetTarget: '/tmp/changeset.json' },
  'discover-adversarial': { problem: '합성 문제', codeContextPath: '/tmp/code-context.md' },
  'peer-review': BASE_ARGS,
  'plan-collaborative': { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' },
  'plan-lean': { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' },
  'plan-lean2': { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' },
  'review-live': BASE_ARGS,
  'search-cross-verify': { query: '합성 질의', codeContext: '/tmp' },
}
const WFS = Object.keys(MIN_ARGS)

let fail = 0, unrun = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

// 시나리오가 있는 워크플로는 default-off-regression 의 첫 시나리오 args 를 얹는다(응답 표는 쓰지 않는다 — 전 콜 null 로 첫 단계만)
// ③ 기준 대조는 그 워크플로의 기본 on 옵션을 모두 끈 **롤백 경로**에서 한다 — 기본 on 옵션이 바꾼 프롬프트(round 2 S9 judgmentSlots 등)는
//    그 옵션의 시험(default-off-regression.js · 옵션 전용 테스트)이 본다. 미지정 기본 경로는 ③b(미지정 == effort 'xhigh' 명시)가 effort 축만 본다.
//    ⛔ 기준 트리가 모르는 옵션 이름은 기준 쪽에서 무시된다 — 양쪽에 같은 인자를 넘긴다(F-559 동결 해제: 기본 경로 프롬프트를 이 SHA 에 묶지 않는다).
function rollbackArgs(wf) {
  return Object.assign({}, ...Object.values(OPTIONS).filter(o => (o.defaultOn || []).includes(wf)).map(o => o.off))
}

function argsOf(wf, extra) {
  const sc = (SCENARIOS[wf] || [])[0]
  return Object.assign({}, MIN_ARGS[wf], sc ? sc.args : {}, extra)
}

async function callsAt(file, wf, extra) {
  const r = await run(file, {
    args: argsOf(wf, extra),
    responder: () => null,
  })
  return { result: r.result, calls: r.calls.map(c => ({ label: c.label, agentType: c.agentType, model: c.model, effort: c.effort,
    schema: String(c.schema), prompt: c.prompt })) }
}

// code-pair 스키마 바이트 대조(S7) — 하네스 calls[].schema 는 불리언이라 ③ 은 스키마를 보지 않는다. responder 가 opts.schema 를 키 정렬 JSON 으로 남긴다
const sortedJSON = v => JSON.stringify(v, (k, x) => (x && typeof x === 'object' && !Array.isArray(x)
  ? Object.keys(x).sort().reduce((o, kk) => { o[kk] = x[kk]; return o }, {}) : x))
async function schemasAt(file) {
  const seen = {}
  const CS = { files: [{ path: 'a.js', changeKind: 'modify', symbolEdits: [{ symbol: 'f', intent: 'i', newBody: 'x', spanLines: 0 }], rationale: 'r' }],
    summary: 's', buildExpectation: 'b' }
  const ISSUE = { verdict: 'issues', issues: [{ id: 'R1', severity: 'minor', detail: 'd' }] }
  await run(file, { args: argsOf('code-pair', {}), responder: (p, opts) => {
    seen[opts.label] = sortedJSON(opts.schema)
    return JSON.parse(JSON.stringify(opts.label.startsWith('stage2') ? ISSUE : CS))
  } })
  return seen
}
// 의도한 변환만 — symbolEdits 항목에 spanLines(정수 · required)와 oldAnchor 설명 교정(F-120). 이 밖의 차이는 전부 FAIL 이다
const editItem = o => o.properties.files.items.properties.symbolEdits.items
function intended(baseJson) {
  const o = JSON.parse(baseJson), it = editItem(o)
  it.required.push('spanLines')
  it.properties.oldAnchor.description = '교체할 원문 전체(Edit old_string) — 시작 줄만 주면 나머지가 남는다(F-120)'
  it.properties.spanLines = { type: 'integer', description: 'oldAnchor 가 있는 교체 편집에서 oldAnchor 의 줄 수, 없으면 0' }
  return sortedJSON(o)
}
const mutated = (json, f) => { const o = JSON.parse(json); f(o); return sortedJSON(o) }

function baseFile(wf, tmp) {
  const env = process.env.FZ_EFFORT_BASE_TREE
  if (env) {
    const f = path.join(env, 'workflows', `${wf}.js`)
    return fs.existsSync(f) ? f : null
  }
  try {
    const src = execFileSync('git', ['-C', ROOT, 'show', `${BASE_SHA}:workflows/${wf}.js`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
    const f = path.join(tmp, `${wf}.base.js`)
    fs.writeFileSync(f, src)
    return f
  } catch (e) { return null }
}

;(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-effort-arg-'))
  try {
    for (const wf of WFS) {
      // plan-lean 은 노출을 거두고 tests/fixtures/workflows/ 로 옮겼다(H1-9) — 기준 SHA 쪽은 옛 경로 그대로 읽는다
      const file = wf === 'plan-lean' ? path.join(ROOT, 'tests', 'fixtures', 'workflows', 'plan-lean.js') : path.join(ROOT, 'workflows', `${wf}.js`)
      const unset = await callsAt(file, wf, {})
      const high = await callsAt(file, wf, { effort: 'high' })
      const bad = await callsAt(file, wf, { effort: 'turbo' })

      check(`${wf}: 미지정 실행이 콜을 낸다`, unset.calls.length > 0, `콜 ${unset.calls.length}`)
      check(`${wf}: ① effort 'high' → 전 콜 high`, high.calls.length > 0 && high.calls.every(c => c.effort === 'high'),
        high.calls.map(c => `${c.label}=${c.effort}`).join(','))
      check(`${wf}: ① 콜 구성은 미지정과 같다`, high.calls.map(c => c.label).join(',') === unset.calls.map(c => c.label).join(','),
        `${high.calls.map(c => c.label)} vs ${unset.calls.map(c => c.label)}`)
      check(`${wf}: ② effort 'turbo' → fallback · 콜 0`, bad.calls.length === 0 && bad.result && bad.result.mode === 'fallback',
        `콜 ${bad.calls.length} · mode ${bad.result && bad.result.mode}`)
      check(`${wf}: ③ 미지정 → 전 콜 xhigh`, unset.calls.every(c => c.effort === 'xhigh'), unset.calls.map(c => `${c.label}=${c.effort}`).join(','))

      const bf = baseFile(wf, tmp)
      if (!bf) { console.log(`UNRUN  ${wf}: ③ 기준 트리 대조 — 기준 소스 없음(FZ_EFFORT_BASE_TREE 미지정 · git show ${BASE_SHA} 실패)`); unrun += 1; continue }
      const roll = rollbackArgs(wf)
      const rolled = Object.keys(roll).length > 0
      const base = await callsAt(bf, wf, roll)
      const d = firstDiff((rolled ? await callsAt(file, wf, roll) : unset).calls, base.calls)
      check(`${wf}: ③ 미지정 콜 입력 == 기준(${process.env.FZ_EFFORT_BASE_TREE ? 'FZ_EFFORT_BASE_TREE' : BASE_SHA})${rolled ? ' — 기본 on 옵션 롤백 경로' : ''}`, d === null, d)
      if (rolled) {
        const x = await callsAt(file, wf, { effort: 'xhigh' })
        const dx = firstDiff(unset.calls, x.calls)
        check(`${wf}: ③b 기본 경로 — 미지정 콜 입력 == effort 'xhigh' 명시`, dx === null, dx)
      }
    }
    const cpBase = baseFile('code-pair', tmp)
    if (!cpBase) { console.log('UNRUN  code-pair 스키마 대조 — 기준 소스 없음'); unrun += 1 } else {
      const now = await schemasAt(path.join(ROOT, 'workflows', 'code-pair.js')), was = await schemasAt(cpBase)
      const CSL = ['stage1-impl', 'stage3-revise'], RVL = ['stage2-review-arch', 'stage2-review-quality']
      const ok = Object.keys(now).sort().join(',') === Object.keys(was).sort().join(',')
        && CSL.every(l => now[l] && now[l] === intended(was[l])) && RVL.every(l => now[l] && now[l] === was[l])
      check('code-pair-schema-intended-only', ok, `콜 ${Object.keys(now)} · 기준 ${Object.keys(was)}`)
      const want = was['stage1-impl'] ? intended(was['stage1-impl']) : ''
      const cur = now['stage1-impl'] || '{}'
      check('schema-compare-detects-unrelated-field', !!want && cur === want
        && mutated(cur, o => { o.properties.files.items.properties.extra = { type: 'string' } }) !== want, cur === want ? '무관 필드를 더해도 같다고 본다' : '전제 불성립 — 변형 전 스키마부터 의도한 변환과 다르다')
      check('schema-compare-detects-required-change', !!want && cur === want
        && mutated(cur, o => { editItem(o).required = editItem(o).required.filter(x => x !== 'spanLines') }) !== want, cur === want ? 'required 변경을 같다고 본다' : '전제 불성립 — 변형 전 스키마부터 의도한 변환과 다르다')
      check('schema-compare-detects-description-change', !!want && cur === want
        && mutated(cur, o => { editItem(o).properties.oldAnchor.description = '시작 지점' }) !== want, cur === want ? '설명 변경을 같다고 본다' : '전제 불성립 — 변형 전 스키마부터 의도한 변환과 다르다')
    }
  } finally { fs.rmSync(tmp, { recursive: true, force: true }) }
  console.log(`\neffort 인자 전달 ${fail ? '실패 ' + fail + '건' : unrun ? '미실행 ' + unrun + '건' : '전건 통과'} (워크플로 ${WFS.length} · 대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : unrun ? 2 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
