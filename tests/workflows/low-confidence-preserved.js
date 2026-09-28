// 발견 단계 후보 보존 (S16b) — args.preserveLowConfidence 를 켜면 peer-review 의 여섯 콜 어디에도 조기 필터가 없고,
// 확신도 낮은 후보가 반환에 값 그대로 남는다. 렌즈 스킬·모듈의 조기 필터 문장은 모두 `[후보 보존]` 조건부 절 아래 있다.
//
// ⛔ 조기 필터 문구는 원장 CHECK 의 리터럴 넷으로 본다(문구 변형은 early-exclusion-semantics.js 가 본다). 표지 문장이 있는지만 보면
//    .replace 대상이 어긋나 헛돌 때(옛 문장이 남은 채 표지만 붙는 경우)를 못 잡는다 — 옛 문구의 **부재**를 본다.
// ⛔ 하네스는 에이전트 frontmatter 가 미리 올리는 스킬 본문(review-arch → arch-critic · review-quality → code-auditor)을 볼 수 없다.
//    그래서 스킬 쪽은 문서 검사다 — 검사기가 잡은 조기 배제 문장마다 같은 절(제목과 제목 사이)에 `[후보 보존]` 조건부 절이 있어야 한다.
// ⛔ 옵션 미지정일 때 기준과 바이트 단위로 같은지는 default-off-regression.js 가 본다. 기준 트리(FZ_WF_ROOT)는 옵션을 몰라 FAIL 이다.
'use strict'
const fs = require('fs')
const path = require('path')
const { run } = require('../lib/wf_harness')
const { earlyExclusions } = require('./early-exclusion-semantics')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'peer-review.js')
const FILTER = /80 미만 미보고|confidence 80 미만은 보고하지|confidence < 80 → 보고하지|confidence 80% 미만이면 보고하지/
const MARK = '[후보 보존]'
const SCENARIOS = [
  { name: 'Tier 2 · 트리거 미발화', args: {}, fire: false },
  { name: 'Tier 2 · 트리거 발화', args: {}, fire: true },
  { name: 'Tier 3 · deep', args: { deep: true }, fire: true },
]
// 렌즈가 읽는 문서 — 미리 올라가는 스킬 둘 · Lead 절차 모듈 · 렌즈 에이전트 정의. min 은 검사기가 적어도 잡아야 하는 수(0건은 측정 실패)
const DOCS = [
  { file: 'skills/arch-critic/SKILL.md', min: 2 },
  { file: 'skills/code-auditor/SKILL.md', min: 2 },
  { file: 'modules/peer-review-workflow.md', min: 2 },
  ...['review-arch', 'review-quality', 'review-correctness', 'review-counter'].map(a => ({ file: `agents/${a}.md`, min: 0 })),
]

const LOW = { id: 'Q7', file: 'b.swift', line_range: '3-4', severity: 'minor', perspective: 'p', discoveryAxis: 'code_quality',
  origin: 'regression', description: 'd', evidence: 'e', confidence: 40 }
function responses(fire) {
  const major = { ...LOW, id: 'Q1', file: 'a.swift', line_range: '10-12', severity: 'major', confidence: 90 }   // 단독 major — Stage 2 가 돈다
  return {
    'stage1-arch': { issues: [], strengths: ['s'], overall_assessment: 'o' },
    'stage1-quality': { issues: fire ? [major, LOW] : [LOW], strengths: [], overall_assessment: 'o' },
    'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
    'stage2-arch-on-peers': { adjustments: [], additions: [] },
    'stage2-quality-on-peers': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedIssues: [] },
  }
}
async function capture(args, fire) {
  const calls = []
  const table = responses(fire)
  const { result } = await run(WF, { args: Object.assign({ diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }, args), responder: (prompt, opts) => {
    calls.push({ label: opts.label, prompt, schema: JSON.stringify(opts.schema || null) })
    return table[opts.label] ? JSON.parse(JSON.stringify(table[opts.label])) : null
  } })
  return { calls, result }
}

// 조기 배제 문장이 있는 절마다 표지 조건부 절이 함께 있는가 — 절은 제목 줄로 가른다
function scope(text) {
  let hits = 0
  const bare = []
  for (const section of text.split(/\n(?=#{1,6} )/)) {
    const h = earlyExclusions(section)
    hits += h.length
    if (h.length && !(section.includes(MARK) && section.includes('preserveLowConfidence'))) bare.push(...h)
  }
  return { hits, bare }
}

const labels = calls => calls.map(c => c.label).sort().join(',')   // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 못 본다
let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

;(async () => {
  for (const sc of SCENARIOS) {
    const on = await capture(Object.assign({ preserveLowConfidence: true }, sc.args), sc.fire)
    const tag = `${sc.name} · preserveLowConfidence`
    const leaked = on.calls.filter(c => FILTER.test(c.prompt) || FILTER.test(c.schema))
    check(`${tag}: 콜 ${on.calls.length}개 프롬프트·스키마에 조기 필터 문구가 없다`, on.calls.length > 0 && leaked.length === 0,
      leaked.map(c => c.label).join(',') || '콜 0개')
    const unmarked = on.calls.filter(c => !c.prompt.includes(MARK))
    check(`${tag}: 모든 콜 프롬프트에 ${MARK} 문장이 있다`, on.calls.length > 0 && unmarked.length === 0, unmarked.map(c => c.label).join(','))
    const kept = on.result && Array.isArray(on.result.issues) ? on.result.issues.find(f => f.id === 'Q:Q7') : null
    check(`${tag}: confidence 40 후보가 반환 issues 에 값 그대로 남는다`, !!kept && kept.confidence === 40,
      kept ? `confidence ${kept.confidence}` : '반환에 없다')

    const off = await capture(sc.args, sc.fire)
    const lost = off.calls.filter(c => !FILTER.test(c.prompt))
    check(`${sc.name} · 옵션 미지정: 모든 콜 프롬프트에 기존 조기 필터가 남아 있다(기본 경로 유지)`, off.calls.length > 0 && lost.length === 0,
      lost.map(c => c.label).join(',') || '콜 0개')
    check(`${sc.name}: 켠 실행과 끈 실행의 콜 구성(label 다중집합)이 같다`, labels(on.calls) === labels(off.calls), `켬 ${labels(on.calls)} · 끔 ${labels(off.calls)}`)
  }

  for (const d of DOCS) {
    const f = path.join(ROOT, d.file)
    if (!fs.existsSync(f)) { check(`${d.file}: 파일이 있다`, false, '없다'); continue }
    const { hits, bare } = scope(fs.readFileSync(f, 'utf8'))
    check(`${d.file}: 조기 배제 문장 ${hits}건 — ${d.min}건 이상(0건은 측정 실패)`, hits >= d.min, `${hits}건`)
    check(`${d.file}: 조기 배제 문장마다 같은 절에 ${MARK} 조건부 절이 있다`, bare.length === 0, bare.join(' | '))
  }

  console.log(`\n후보 보존 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
