// 발견 단계 조기 배제 의미 검사 (S16b) — "확신도가 낮으면 보고하지 않는다" 를 문구 변형까지 잡는다.
//
// ⛔ 원장 CHECK 의 리터럴 넷은 어순·표기 변형을 놓친다 — `confidence<80 미보고`(modules/peer-review-workflow.md 의 Synthesize 계약 줄)는
//    그 목록에 걸리지 않았다. 여기서는 문장마다 신호 셋(확신도 · 낮은 임계 · 배제 동사)이 함께 있는지 본다.
//    확신도 말은 바로 앞 문장에 있어도 된다(`confidence 는 0-100 으로 단다. 70 미만은 뺀다.`). "N 이상만 보고" 꼴도 배제다.
// ⛔ 확신도를 말하지만 배제가 아닌 문장은 잡지 않는다 — Lead 에스컬레이션(`판단 confidence < 60% 시`) · 병합 등급
//    (`80 미만 결함은 hold`) · 보존 지시(`낮다고 빼지 않는다`). 아래 음성 예시가 이것들이다.
// 이 파일이 보는 것: ① 합성 양성·음성 예시로 검사기 자체 ② peer-review 콜 입력(프롬프트·스키마) — 옵션 미지정은 모든 콜이 걸리고
//    (실데이터 양성 대조), `preserveLowConfidence:true` 는 하나도 걸리지 않는다. 기준 트리(FZ_WF_ROOT)는 옵션을 몰라 ② 둘째가 FAIL 이다.
// 검사기는 tests/workflows/low-confidence-preserved.js 가 문서 검사에 가져다 쓴다(module.exports).
'use strict'
const path = require('path')

const CONF = /confidence|신뢰도|확신/i
const LOW = /\d{2}\s*%?\s*(점\s*)?(미만|이하|보다\s*낮)|[<≤]\s*\d{2}|\b(below|under|less than)\s+\d{2}|낮(으면|은|다면|을\s*때)|\blow\b/i
const DROP = /보고하지|미보고|보고\s*않|제외|버리|버린|버려|뺀다|빼라|빼고|거른다|걸러|\b(drop|omit|skip|discard|exclude|suppress)\b|\b(do not|don't|never) (report|include|output)\b/i
const HIGH = /\d{2}\s*%?\s*(점\s*)?(이상|초과)|[>≥]=?\s*\d{2}|\b(at least|above|over)\s+\d{2}/i
const ONLY = /(이상|초과)만|만\s*(보고|낸|남긴|출력)|\bonly\b/i
const KEEP = /빼지\s*않|버리지\s*않|제외하지\s*않|거르지\s*않|낮아도|이어도\s*보고|\b(keep|preserve)\b|\b(do not|don't) drop\b/i

// 텍스트의 조기 배제 문장 목록. impliedConfidence — 스키마 confidence 필드 설명처럼 확신도가 문맥으로 주어진 경우
function earlyExclusions(text, { impliedConfidence = false } = {}) {
  const hits = []
  for (const line of String(text).split('\n')) {
    const units = line.split(/(?<=[.。!?])\s+/)
    units.forEach((u, i) => {
      const conf = impliedConfidence || CONF.test(u) || (i > 0 && CONF.test(units[i - 1]))
      if (conf && !KEEP.test(u) && ((LOW.test(u) && DROP.test(u)) || (HIGH.test(u) && ONLY.test(u)))) hits.push(u.trim())
    })
  }
  return hits
}

// 스키마의 모든 description 을 본다 — confidence 필드의 설명은 확신도가 문맥으로 주어진다
function schemaExclusions(schema) {
  const hits = []
  ;(function walk(node, key) {
    if (!node || typeof node !== 'object') return
    if (typeof node.description === 'string') hits.push(...earlyExclusions(node.description, { impliedConfidence: key === 'confidence' }))
    for (const [k, v] of Object.entries(node)) walk(v, k)
  })(schema, null)
  return hits
}

module.exports = { earlyExclusions, schemaExclusions }

if (require.main === module) {
  const { run } = require('../lib/wf_harness')
  const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
  const WF = path.join(ROOT, 'workflows', 'peer-review.js')
  let fail = 0
  const labels = calls => calls.map(c => c.label).sort().join(',')   // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 못 본다
  const check = (name, cond, got) => {
    console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
    if (!cond) fail += 1
  }

  // [문장, 확신도가 문맥으로 주어지는가]
  const POSITIVE = [
    ['confidence 80 미만은 보고하지 않는다.'],
    ['80 미만 미보고', true],
    ['자체 confidence 80% 미만이면 보고하지 않는다.'],
    ['| 자체 신뢰도 임계치 | confidence < 80 → 보고하지 않음 |'],
    ['산출물 계약(Confidence Matrix, confidence<80 미보고, dedup+투표)은 Synthesize Step에 보존'],
    ['70 미만 미보고', true],
    ['confidence 가 70 보다 낮은 항목은 버린다.'],
    ['신뢰도 80% 이하 발견은 제외한다.'],
    ['신뢰도 낮으면 제외'],
    ['확신이 낮으면 보고하지 마라.'],
    ['Do not report findings with confidence below 80.'],
    ['Drop low-confidence findings.'],
    ['Only report issues with confidence >= 80.'],
    ['confidence 80% 이상만 보고한다.'],
    ['confidence 는 0-100 으로 단다. 70 미만은 출력에서 뺀다.'],
  ]
  const NEGATIVE = [
    ['- 판단 confidence < 60% 시'],                                  // agents/review-*.md — Lead 에스컬레이션 조건
    ['craft 항목은 ruleRef 가 있고 confidence 80 이상일 때만 `post`(확신도가 낮으면 suggestion 채널), confidence 80 미만 결함은 `hold`'],   // MergeContract §10 — 병합 등급
    ['confidence 는 0-100 값으로 기록한다.'],
    ['[후보 보존] confidence 는 0-100 값으로 달되 낮다고 빼지 않는다 — 게시 여부는 병합이 정한다.'],
    ['0-100 — 낮아도 보고한다(게시 등급은 병합이 정한다)', true],
    ['판정: challenge(반박-confidence 20% 감소), reverse(역전-원래 이슈 제외 후 새 이슈 생성)'],   // gpt_peer_review_schema
    ['낮은 confidence 도 보고한다.'],
    ['confidence 80 이상이면 post 로 둔다.'],
    ['위 계약의 확신도 미달 항목을 버리지 않고 hold 로 둔다.'],
    ['이슈 confidence는 ×0.7 감쇠'],
  ]
  for (const [t, implied] of POSITIVE) {
    check(`양성: ${t}`, earlyExclusions(t, { impliedConfidence: !!implied }).length > 0, '못 잡았다')
  }
  for (const [t, implied] of NEGATIVE) {
    const h = earlyExclusions(t, { impliedConfidence: !!implied })
    check(`음성: ${t}`, h.length === 0, `잘못 잡았다 ${JSON.stringify(h)}`)
  }

  const major = { id: 'Q1', file: 'a.swift', line_range: '10-12', severity: 'major', perspective: 'p', discoveryAxis: 'code_quality',
    origin: 'regression', description: 'd', evidence: 'e', confidence: 90 }
  const table = fire => ({
    'stage1-arch': { issues: [], strengths: ['s'], overall_assessment: 'o' },
    'stage1-quality': { issues: fire ? [major] : [], strengths: [], overall_assessment: 'o' },
    'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
    'stage2-arch-on-peers': { adjustments: [], additions: [] },
    'stage2-quality-on-peers': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedIssues: [] },
  })
  const SCENARIOS = [
    { name: 'Tier 2 · 트리거 미발화', args: {}, fire: false },
    { name: 'Tier 2 · 트리거 발화', args: {}, fire: true },
    { name: 'Tier 3 · deep', args: { deep: true }, fire: true },
  ]
  const capture = async (args, fire) => {
    const calls = []
    const t = table(fire)
    await run(WF, { args: Object.assign({ diffPath: '/tmp/diff.patch', intentContext: '합성 의도' }, args), responder: (prompt, opts) => {
      calls.push({ label: opts.label, found: [...earlyExclusions(prompt), ...schemaExclusions(opts.schema || null)],
                   prompt: earlyExclusions(prompt).length > 0, schema: schemaExclusions(opts.schema || null).length > 0 })
      return t[opts.label] ? JSON.parse(JSON.stringify(t[opts.label])) : null
    } })
    return calls
  }

  ;(async () => {
    for (const sc of SCENARIOS) {
      const unset = await capture(sc.args, sc.fire)
      const missed = unset.filter(c => !c.prompt || !c.schema)
      check(`${sc.name} · 옵션 미지정: 콜 ${unset.length}개 모두 프롬프트·스키마가 걸린다(실데이터 양성 대조)`,
        unset.length > 0 && missed.length === 0, missed.map(c => `${c.label}(프롬프트 ${c.prompt} · 스키마 ${c.schema})`).join(', ') || '콜 0개')
      const on = await capture(Object.assign({ preserveLowConfidence: true }, sc.args), sc.fire)
      const leaked = on.filter(c => c.found.length)
      check(`${sc.name} · preserveLowConfidence: 콜 ${on.length}개 어디에도 조기 배제가 없다`,
        on.length > 0 && leaked.length === 0, leaked.map(c => `${c.label}: ${c.found[0]}`).join(' | ') || '콜 0개')
      check(`${sc.name}: 켠 실행과 미지정 실행의 콜 구성(label 다중집합)이 같다`, labels(on) === labels(unset), `켬 ${labels(on)} · 미지정 ${labels(unset)}`)
    }
    console.log(`\n조기 배제 의미 검사 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), ROOT) || '.'})`)
    process.exit(fail ? 1 : 0)
  })().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
}
