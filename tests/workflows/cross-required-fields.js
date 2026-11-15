// 교차 스테이지 필수 필드 재고지 (S17) — args.crossRequiredFields 가 켜지면 Stage 2 교차 프롬프트가
// additions 항목의 required 키를 **전부** 적는다. 키 목록은 워크플로가 스키마에서 읽는다(하드코딩 금지).
//
// ⛔ 기대 키를 이 테스트도 박지 않는다 — responder 가 잡은 Stage 2 콜의 opts.schema 에서 읽는다.
// ⛔ 하드코딩 금지는 출력만으로는 못 본다(오늘의 스키마와 같게 박으면 통과한다) — 소스가 스키마 경로를 참조하는지도 본다.
// ⛔ peer-review 는 deep 과 트리거 발화 두 경로, review-live 는 기본 경로를 본다. 기준 트리(FZ_WF_ROOT)는 FAIL 이 나와야 한다.
// ⛔ 옵션 미지정일 때 기준과 바이트 단위로 같은지는 tests/workflows/default-off-regression.js 가 본다.
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = { 'peer-review': path.join(ROOT, 'workflows', 'peer-review.js'), 'review-live': path.join(ROOT, 'workflows', 'review-live.js') }
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }
const LINE = /^\[필수 필드 — additions\] 새 항목마다 (.*?) 를 모두 채운다/m
const PATHS = {
  'peer-review': [{ name: 'deep', args: { deep: true } }, { name: 'Tier 2 트리거 발화', args: {} }],
  'review-live': [{ name: '기본', args: {} }],
}

const labels = calls => calls.map(c => c.label).sort().join(',')   // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 못 본다
let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

function responses(wf) {
  const major = { id: 'Q1', file: 'a.swift', line_range: '10-12', severity: 'major', perspective: 'p', discoveryAxis: 'code_quality',
    origin: 'regression', description: 'd', evidence: 'e', confidence: 90 }
  return wf === 'peer-review' ? {
    'stage1-arch': { issues: [], strengths: [], overall_assessment: 'o' },
    'stage1-quality': { issues: [major], strengths: [], overall_assessment: 'o' },   // 단독 major — Tier 2 에서도 Stage 2 가 돈다
    'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
    'stage2-arch-on-peers': { adjustments: [], additions: [] },
    'stage2-quality-on-peers': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedIssues: [] },
  } : {
    'stage1-arch': { findings: [], okAreas: [] },
    'stage1-quality': { findings: [], okAreas: [] },
    'stage2-arch-on-quality': { adjustments: [], additions: [] },
    'stage2-quality-on-arch': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedFindings: [] },
  }
}
async function capture(wf, args) {
  const calls = []
  const table = responses(wf)
  await run(WF[wf], { args: Object.assign({}, ARGS, args), responder: (prompt, opts) => {
    calls.push({ label: opts.label, prompt, schema: opts.schema || null })
    return table[opts.label] ? JSON.parse(JSON.stringify(table[opts.label])) : null
  } })
  return calls
}

;(async () => {
  for (const wf of Object.keys(WF)) {
    const src = fs.existsSync(WF[wf]) ? fs.readFileSync(WF[wf], 'utf8') : ''
    const def = src.match(/const crossRequiredLine = [\s\S]*?\n\n?(?=\S)/)
    check(`${wf}: 재고지 키를 스키마에서 읽는다(소스가 CrossReviewSchema…additions.items.required 를 참조)`,
      !!def && def[0].includes('CrossReviewSchema.properties.additions.items.required'), def ? '스키마 경로 참조 없음 — 하드코딩 의심' : 'crossRequiredLine 정의 없음')

    for (const p of PATHS[wf]) {
      const on = await capture(wf, Object.assign({ crossRequiredFields: true }, p.args))
      const stage2 = on.filter(c => c.label.startsWith('stage2-'))
      check(`${wf} · ${p.name}: Stage 2 교차 콜 2개`, stage2.length === 2, `${stage2.length}개 — ${on.map(c => c.label).join(',')}`)
      for (const c of stage2) {
        const req = c.schema && c.schema.properties.additions.items.required
        const m = c.prompt.match(LINE)
        const listed = m ? m[1].split(' · ') : null
        check(`${wf} · ${p.name} · ${c.label}: 재고지 줄이 additions required 키를 전부·같은 순서로 적는다`,
          Array.isArray(req) && req.length > 0 && JSON.stringify(listed) === JSON.stringify(req), `적힌 ${JSON.stringify(listed)} · 스키마 ${JSON.stringify(req)}`)
      }
      const others = on.filter(c => !c.label.startsWith('stage2-'))
      check(`${wf} · ${p.name}: Stage 2 밖 프롬프트에는 재고지 줄이 없다`, others.length > 0 && others.every(c => !LINE.test(c.prompt)),
        others.filter(c => LINE.test(c.prompt)).map(c => c.label).join(','))
      const offP = await capture(wf, p.args)
      check(`${wf} · ${p.name}: 켠 실행과 미지정 실행의 콜 구성(label 다중집합)이 같다`, labels(on) === labels(offP), `켬 ${labels(on)} · 미지정 ${labels(offP)}`)
    }
    const off = await capture(wf, Object.assign({ crossRequiredFields: false }, PATHS[wf][0].args))   // ⛔ peer-review 는 기본 on(v4.42.0)
    check(`${wf}: 옵션 false → 어느 프롬프트에도 재고지 줄이 없다`, off.length > 0 && off.every(c => !LINE.test(c.prompt)), off.length ? '끈 실행인데 줄이 있다' : '콜 0개')
  }

  console.log(`\n교차 필수 필드 재고지 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
