// 워크플로별 기본값 회귀 (R-B · R-C) — 옵션을 주지 않으면 워크플로의 모든 콜 입력이 그 워크플로의 기본값과 바이트 단위로 같다.
//   기본 off 워크플로: 미지정 == 기준 트리. 기본 on 워크플로(레지스트리 `defaultOn` — v4.42.0 peer-review): 미지정 == 켠 값.
//   기본 off 워크플로는 옵션마다 끄는 값(off) == 기준. 기본 on 워크플로는 **기본 on 옵션을 모두 끄면** == 기준이다 — 롤백 경로
//   (하나만 끄면 나머지가 켜져 있어 기준이 아니다 — 옵션마다는 '끔 != 켬' 으로 배선을 본다).
//   레지스트리는 tests/workflows/default-arms.js 가 재사용한다(require — 실행부는 직접 실행할 때만 돈다).
//
// ⛔ 비교 대상은 **콜 입력**(label · prompt · schema · model · effort · agentType)이다. 반환값은 비교하지 않는다 —
//    R-A 가 peer-review Tier 2 반환의 완주 수 계산을 고쳤다(프롬프트·스키마는 그대로). 반환까지 비교하면 그 수정이 회귀로 보인다.
//    하네스의 calls 는 스키마를 불리언으로만 남기므로 responder 가 opts.schema 를 직렬화해 잡는다.
// ⛔ 기준 소스: env FZ_BASE_TREE 의 workflows/ → 없으면 이 저장소 이력의 `git show ${FZ_BASE_SHA:-13755a6}:workflows/<wf>.js`.
//    health-check 러너는 env 없이 돈다 — 이력이 있는 클론(작업 트리 · 격리 검증 클론)이면 된다. 둘 다 없으면 UNRUN(exit 2)이다.
// ⛔ 옵션마다 세 가지를 본다: 미지정 == 기준(defaultOn 이면 미지정 == 켬) · false == 기준 · true != 기준(옵션이 실제로 배선돼 있다 — 헛돌이 방어).
//    옵션이 닿지 않는 경로(예: Stage 2 가 없는 Tier 2 미발화)에서는 셋째를 true == 기준 으로 본다 — 옵션이 엉뚱한 경로로 새지 않는다.
// ⛔ `structural` 옵션(R-C 속도 arm)은 켜면 콜을 빼는 것이 목적이다 — 켠 쪽 두 검사(!= 기준 · 콜 구성 동일)를 여기서 하지 않고
//    그 값이 가리키는 전용 테스트가 본다. 미지정 == 기준 · off == 기준 은 똑같이 본다.
// 인자: --option NAME(여러 번) · --all-rb-options · 인자 없음 = 등록된 옵션 전부(health-check 러너가 인자 없이 돈다).
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')

const ROOT = path.join(__dirname, '..', '..')
const BASE_SHA = process.env.FZ_BASE_SHA || '13755a6'

// 옵션 레지스트리 — 새 옵션(S16b · S17 …)은 여기에 한 줄 더한다. 없는 이름을 부르면 FAIL 이다.
// defaultOn: 그 옵션이 **기본으로 켜진** 워크플로(v4.42.0 — S25p 판정 PASS 인 peer-review 만). 나머지 워크플로는 기본 off 다.
//   ⛔ 바꾸려면 측정 판정이 먼저다 — tests/workflows/default-arms.js 가 원장 판정과 이 값을 대조한다.
const PEER_ON = ['peer-review']
const OPTIONS = {
  craftAxes: { workflows: ['peer-review', 'review-live'], on: { craftAxes: true }, off: { craftAxes: false }, defaultOn: PEER_ON },
  crossRequiredFields: { workflows: ['peer-review', 'review-live'], on: { crossRequiredFields: true }, off: { crossRequiredFields: false },
    defaultOn: PEER_ON, applies: sc => sc.stage2 },   // Stage 2 교차 프롬프트에만 닿는다
  // 두 워크플로 — 렌즈 에이전트가 미리 올리는 스킬(arch-critic · code-auditor)의 '자체 confidence 80% 미만이면 보고하지 않는다' 는
  //   [후보 보존] 문장에만 풀린다. peer-review 는 OVERRIDE 문장을 바꾸고, review-live(R-C S22)는 문장을 덧붙이고 스키마 사본에
  //   confidence 를 얹는다. OVERRIDE 가 모든 콜에 있어 applies 가 없다
  preserveLowConfidence: { workflows: ['peer-review', 'review-live'], on: { preserveLowConfidence: true }, off: { preserveLowConfidence: false },
    defaultOn: PEER_ON },
  // review-live 만 — peer-review 는 기본 스키마에 위치 필드가 있다. Stage 1 두 콜의 스키마만 바뀐다
  locatedFindings: { workflows: ['review-live'], on: { locatedFindings: true }, off: { locatedFindings: false } },
  // R-C 속도 arm — 켜면 병합 콜을 뺄 수 있다(structural)
  mergeMode: { workflows: ['plan-lean2'], on: { mergeMode: 'conditional' }, off: { mergeMode: 'always' },
    structural: 'tests/workflows/plan-lean2-merge-arm.js' },
  // R-C 속도 arm — 켜면 교차 2콜을 뺄 수 있다(structural)
  stage2: { workflows: ['review-live'], on: { stage2: 'conditional' }, off: { stage2: 'always' },
    structural: 'tests/workflows/review-live-stage2-arm.js' },
  // R-C 교차 delta — 콜 수는 그대로, Stage 2 교차의 스키마 · 프롬프트만 바뀐다(동치는 tests/workflows/cross-delta-arm.js)
  crossOutput: { workflows: ['peer-review', 'review-live'], on: { crossOutput: 'delta' }, off: { crossOutput: 'full' },
    defaultOn: PEER_ON, applies: sc => sc.stage2 },
  // R-C 사전 수집 스냅샷 — Stage 1 두 프롬프트에만 닿는다(콜 수 그대로). 빈 문자열은 미지정과 같다
  snapshotDir: { workflows: ['review-live'], on: { snapshotDir: '/tmp/fz-snapshot' }, off: { snapshotDir: '' } },
}

const BASE_ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도', structuralContext: '합성 구조 축 브리프' }
// 경로가 다른 시나리오 — peer-review 는 Tier 2(트리거 미발화 · 발화)와 Tier 3 을 다 탄다
const SCENARIOS = {
  'peer-review': [
    { name: 'Tier 2 · 트리거 미발화', args: {}, fire: false, stage2: false },
    { name: 'Tier 2 · 트리거 발화', args: {}, fire: true, stage2: true },
    { name: 'Tier 3 · deep', args: { deep: true }, fire: true, stage2: true },
  ],
  'review-live': [{ name: '기본', args: {}, fire: false, stage2: true }],
  'plan-lean2': [{ name: '기본', args: { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }, fire: false, stage2: false }],
}

function responses(wf, fire) {
  const major = { id: 'Q1', file: 'a.swift', line_range: '10-12', severity: 'major', perspective: 'p', discoveryAxis: 'code_quality',
    origin: 'regression', description: 'd', evidence: 'e', confidence: 90 }
  if (wf === 'peer-review') {
    return {
      'stage1-arch': { issues: [], strengths: ['s'], overall_assessment: 'o' },
      'stage1-quality': { issues: fire ? [major] : [], strengths: [], overall_assessment: 'o' },
      'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
      'stage2-arch-on-peers': { adjustments: [], additions: [] },
      'stage2-quality-on-peers': { adjustments: [], additions: [] },
      'stage3-counter': { challenges: [], missedIssues: [] },
    }
  }
  if (wf === 'plan-lean2') {
    return {
      'lean2-full': { directionVerdict: 'PROCEED', directionAlternatives: [], steps: [{ id: 'S1', title: 't', files: ['a'] }], readScope: [], writeScope: [] },
      'lean2-edge': { edgeCases: [{ id: 'E1', case: 'c', failureScenario: 'f', whereItBreaks: 'w' }], impactNotes: [], latentDefects: [] },
      'lean2-impact-arch': { impactFiles: [], patternVerdicts: [] },
      'lean2-merge': { addedEdgeCases: [], addedImpact: [], stepAmendments: [], implicationRegister: [], unresolved: [] },
    }
  }
  return {
    'stage1-arch': { findings: [{ id: 'A1', severity: 'minor', category: 'c', title: 't', detail: 'd', evidence: 'e' }], okAreas: ['ok'] },
    'stage1-quality': { findings: [], okAreas: [] },
    'stage2-arch-on-quality': { adjustments: [], additions: [] },
    'stage2-quality-on-arch': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedFindings: [] },
  }
}

async function callsOf(file, wf, scenario, extraArgs) {
  const calls = []
  const table = responses(wf, scenario.fire)
  await run(file, {
    args: Object.assign({}, BASE_ARGS, scenario.args, extraArgs),
    responder: (prompt, opts) => {
      calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, effort: opts.effort,
                   schema: JSON.stringify(opts.schema || null), prompt })
      return table[opts.label] ? JSON.parse(JSON.stringify(table[opts.label])) : null
    },
  })
  return calls
}

function baseFile(wf, tmp) {
  const env = process.env.FZ_BASE_TREE
  if (env) {
    const f = path.join(env, 'workflows', `${wf}.js`)
    if (!fs.existsSync(f)) throw new Error(`FZ_BASE_TREE 에 ${wf}.js 가 없다 — ${f}`)
    return { file: f, from: `FZ_BASE_TREE` }
  }
  const src = execFileSync('git', ['-C', ROOT, 'show', `${BASE_SHA}:workflows/${wf}.js`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
  const f = path.join(tmp, `${wf}.base.js`)
  fs.writeFileSync(f, src)
  return { file: f, from: `git ${BASE_SHA}` }
}

function firstDiff(a, b) {
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const x = a[i], y = b[i]
    if (!x || !y) return `콜 수 ${a.length} ≠ ${b.length}`
    for (const k of ['label', 'agentType', 'model', 'effort', 'schema', 'prompt']) if (x[k] !== y[k]) return `${i}번 콜(${x.label}) ${k} 다름`
  }
  return null
}

const labels = calls => calls.map(c => c.label).sort().join(',')   // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 못 본다
let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

module.exports = { OPTIONS, SCENARIOS, BASE_ARGS, callsOf, firstDiff }

if (require.main === module) (async () => {
  const argv = process.argv.slice(2)
  const asked = argv.flatMap((a, i) => (a === '--option' ? [argv[i + 1]] : []))
  const names = argv.includes('--all-rb-options') || asked.length === 0 ? Object.keys(OPTIONS) : asked
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-default-off-'))
  const rolledBack = new Set()   // 롤백 검사는 (워크플로 · 경로)마다 한 번
  let bases
  try {
    const wfs = [...new Set(names.flatMap(n => (OPTIONS[n] ? OPTIONS[n].workflows : [])))]
    try {
      bases = Object.fromEntries(wfs.map(wf => [wf, baseFile(wf, tmp)]))
    } catch (e) {
      console.log(`UNRUN  기준 소스를 얻지 못했다 — ${e.message.split('\n')[0]} (⛔ 통과 아님)`)
      process.exit(2)
    }
    for (const name of names) {
      const opt = OPTIONS[name]
      if (!opt) { check(`옵션 ${name} 이 레지스트리에 있다`, false, `등록된 옵션: ${Object.keys(OPTIONS).join(', ')}`); continue }
      for (const wf of opt.workflows) {
        const work = path.join(ROOT, 'workflows', `${wf}.js`)
        for (const sc of SCENARIOS[wf]) {
          const base = await callsOf(bases[wf].file, wf, sc, {})
          const unset = await callsOf(work, wf, sc, {})
          const off = await callsOf(work, wf, sc, opt.off)
          const on = await callsOf(work, wf, sc, opt.on)
          const tag = `${name} · ${wf} · ${sc.name}`
          const reaches = !opt.applies || opt.applies(sc)
          if ((opt.defaultOn || []).includes(wf)) {
            // 기본 on — 같은 워크플로의 다른 기본 on 옵션도 켜져 있어, 이 옵션 하나만 끈 결과는 기준이 아니다.
            //   그래서 옵션마다는 '미지정 == 켬' 과 '끔 != 켬'(배선)을 보고, 롤백(기본 on 을 전부 끔 == 기준)은 경로마다 1회 아래에서 본다
            check(`${tag}: 미지정 == ${JSON.stringify(opt.on)}(기본 on) — 콜 ${on.length}개`, on.length > 0 && firstDiff(unset, on) === null, firstDiff(unset, on) || '콜 0개')
            if (reaches) check(`${tag}: ${JSON.stringify(opt.off)} != 켬(옵션이 배선돼 있다)`, firstDiff(off, on) !== null, '꺼도 콜 입력이 같다 — 헛돌이')
            else check(`${tag}: ${JSON.stringify(opt.off)} == 켬(이 경로에는 옵션이 닿지 않는다)`, firstDiff(off, on) === null, firstDiff(off, on))
            const key = `${wf}|${sc.name}`
            if (!rolledBack.has(key)) {
              rolledBack.add(key)
              const allOff = Object.assign({}, ...Object.values(OPTIONS).filter(o => (o.defaultOn || []).includes(wf)).map(o => o.off))
              const back = await callsOf(work, wf, sc, allOff)
              check(`${wf} · ${sc.name}: 기본 on 옵션을 모두 끔 ${JSON.stringify(allOff)} == 기준(롤백 경로)`, firstDiff(back, base) === null, firstDiff(back, base))
            }
          } else {
            check(`${tag}: 미지정 == 기준(${bases[wf].from}) — 콜 ${base.length}개`, base.length > 0 && firstDiff(unset, base) === null, firstDiff(unset, base) || '콜 0개')
            check(`${tag}: ${JSON.stringify(opt.off)} == 기준`, firstDiff(off, base) === null, firstDiff(off, base))
            if (opt.structural) {
              check(`${tag}: ${JSON.stringify(opt.on)} 은 콜 구성을 바꿀 수 있다 — 켠 동작은 ${opt.structural} 가 본다(여기서는 실행만)`, on.length > 0, '켜니 콜 0개')
              continue
            }
            if (reaches) check(`${tag}: ${JSON.stringify(opt.on)} != 기준(옵션이 배선돼 있다)`, firstDiff(on, base) !== null, '켜도 콜 입력이 같다 — 헛돌이')
            else check(`${tag}: ${JSON.stringify(opt.on)} == 기준(이 경로에는 옵션이 닿지 않는다)`, firstDiff(on, base) === null, firstDiff(on, base))
          }
          check(`${tag}: ${JSON.stringify(opt.on)} 의 콜 구성(label 다중집합) == 기준`, on.length > 0 && labels(on) === labels(base), `켬 ${labels(on)} · 기준 ${labels(base)}`)
        }
      }
    }
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
  console.log(`\n기본값 회귀 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (옵션 ${names.join(', ')})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
