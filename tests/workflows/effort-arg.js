// 워커 effort 전달 — 8개 워크플로가 args.effort(Lead 세션 effort)를 모든 콜에 싣고, 미지정이면 'xhigh' 로 기준 트리와 같다.
//   셀(워크플로마다): ① effort 'high' → 실행된 전 콜 effort 'high' · 콜 구성(label)은 미지정과 같다
//                     ② 허용값 밖('turbo') → { mode: 'fallback' } · 콜 0
//                     ③ 미지정 → 전 콜 'xhigh' · 콜 입력(label · agentType · model · effort · schema · prompt)이 기준 트리와 바이트 동일
// ⛔ effort 는 품질 옵션 묶음(default-off-regression.js OPTIONS)이 아니라 **별도 축**이다 — 그 레지스트리에 넣으면
//    default-arms.js 가 옵션 on/off 섞임으로 판정한다. 이 파일이 축 전체를 본다(modules/mode-gate.md § effort).
// ⛔ 콜이 실제로 effort 식별자를 쓰는지(리터럴이 남지 않았는지)는 lint-model-explicit.sh --baseline 이 정적으로 본다 — 여기서는 런타임 전달을 본다.
// 기준 소스: env FZ_EFFORT_BASE_TREE 의 workflows/ → 없으면 이 저장소 이력의 `git show ${FZ_EFFORT_BASE_SHA:-26c42d3}:workflows/<wf>.js`.
//   둘 다 없으면 ③ 의 기준 대조는 UNRUN(exit 2) 이다 — 통과가 아니다.
// ⛔ FZ_WF_ROOT 로 기준 트리를 대상으로 돌리면 ① · ② 가 FAIL 이어야 한다(기준은 effort 를 읽지 않는다).
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')
const { SCENARIOS, BASE_ARGS, firstDiff } = require('./default-off-regression')

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
      const file = path.join(ROOT, 'workflows', `${wf}.js`)
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
      const base = await callsAt(bf, wf, {})
      const d = firstDiff(unset.calls, base.calls)
      check(`${wf}: ③ 미지정 콜 입력 == 기준(${process.env.FZ_EFFORT_BASE_TREE ? 'FZ_EFFORT_BASE_TREE' : BASE_SHA})`, d === null, d)
    }
  } finally { fs.rmSync(tmp, { recursive: true, force: true }) }
  console.log(`\neffort 인자 전달 ${fail ? '실패 ' + fail + '건' : unrun ? '미실행 ' + unrun + '건' : '전건 통과'} (워크플로 ${WFS.length} · 대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : unrun ? 2 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
