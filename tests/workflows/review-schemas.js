// 리뷰 워크플로 스키마 시험 기반 (round 2 S8 · S9) — 워크플로를 통째로 돌려 각 콜에 실제로 넘어간 opts.schema · 프롬프트 · 반환을 잡아 본다.
//   PURE 블록 · 소스 문자열 grep 이 아니라 런타임이 받는 스키마 그대로다(사본 · 옵션 분기를 지난 값).
// ⛔ 셀:
//   review-schemas-loaded      peer-review 의 Stage 1 세 콜 스키마를 잡았다(0 이면 아래 셀이 공허하게 통과한다)
//   f072-oracle-required       기본 args — Stage 1 세 콜 · craft 사본의 이슈 항목 required 에 oracle 이 있고 properties.oracle 이 문자열이다
//   f072-oracle-off-absent     oracleField:false — 이슈 항목에 oracle 이 없다(롤백 경로 · 기준 바이트 동일은 default-off-regression.js)
//   f072-oracle-deep-all-calls deep — 교차 additions · counter missedIssues 의 이슈 항목에도 oracle 이 필수다(사본이 네 곳에 퍼져 있다)
//   f559-gap-in-enum           peer-review 기본 · review-live(craftAxes+judgmentSlots) 의 arch axisCoverage status 에 gap 이 있고 craft 줄이 gap 을
//                              설명한다 · judgmentSlots:false 면 gap 이 없다(롤백)
//   f559-vocab-union-handled   Claude enum(두 워크플로가 실제로 보낸 값) ∪ GPT axis_coverage enum ⊆ review_merge.AXIS_RANK 키
//                              (어휘는 통일하지 않는다 — 병합기가 둘 다 이름으로 안다. 모르는 값의 gap 대체로 통과하지 않는다)
//   f448-premises-peer-review  peer-review 기본 — Stage 1 세 콜 루트 required 에 unverifiedPremises(claim · why · howToMeasure) · 교차 · counter 루트엔 없다
//   f448-premises-review-live  review-live judgmentSlots — Stage 1 두 콜 루트에 unverifiedPremises · 반환 unverifiedPremises 에 렌즈 출처와 함께
//                              모인다 · 기본(off)은 스키마 · 반환 모두 없다
//   f178-limits-slot-in-schema 두 워크플로 이슈 항목(Stage 1 · 교차 additions · counter)에 limits(kind 세 값) — review_merge 가 그 kind 로 cap 한다
//   f117-dynamic-axis-prompt   Stage 1 렌즈 프롬프트에 동적 축(상태 × 이벤트) · 설계 대안 질문 블록 — 교차 · counter 프롬프트엔 없다 · review-live 기본은 없다
//   judgment-block-identical   판정 한계 블록이 두 워크플로에서 글자까지 같다(복제 드리프트 방어)
//   catalog-hits-counter-schema  (S19) counter 콜 — review-live catalogHits:true · peer-review 기본(deep) 에서 스키마 사본에 catalogHits(catalogId ·
//                              target · verdict — severity · evidence 없음) · 프롬프트 [점검 카탈로그] · 반환 catalogHits. 끄면(review-live 기본 · peer false) 셋 다 없다 · Stage 1 · 교차엔 없다
//   catalog-hits-edge-schema   (S19) plan-lean2 적대 렌즈 — catalogHits:true 면 스키마 · 프롬프트에 칸 · 방어 스키마와 함께 켜도 둘 다 남는다 · 기본엔 없다 · 다른 콜엔 없다
//   r3-catalog-code-pair-switch-off-default  (round 3 S3) code-pair 기본 — Stage 1 스키마 · 프롬프트 · 반환 어디에도 catalogHits 가 없다
//   r3-catalog-code-pair-switch-on-recorded  catalogHits:true — Stage 1 스키마 필수 칸 · 프롬프트 [점검 카탈로그] · 반환 catalogHits(구현 콜 값) · 검토 · 수정 콜엔 없다
'use strict'
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')

const ROOT = process.env.FZ_WF_ROOT || path.join(__dirname, '..', '..')
const WF = name => path.join(ROOT, 'workflows', `${name}.js`)
const ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도', structuralContext: '합성 구조 축 브리프' }
const S1P = ['stage1-arch', 'stage1-quality', 'stage1-correctness']
const S1L = ['stage1-arch', 'stage1-quality']
const LATER_P = ['stage2-arch-on-peers', 'stage2-quality-on-peers', 'stage3-counter']
const LATER_L = ['stage2-arch-on-quality', 'stage2-quality-on-arch', 'stage3-counter']
let fail = 0
let total = 0
function check(name, cond, got) {
  total += 1
  if (cond) console.log(`PASS ${name}`)
  else { console.log(`FAIL ${name} — ${got}`); fail += 1 }
}

// 이슈 항목 = required 에 discoveryAxis 가 있고 properties.evidence 가 있는 객체(peer-review)
function issueItems(schema, out = []) {
  if (!schema || typeof schema !== 'object') return out
  if (Array.isArray(schema.required) && schema.required.includes('discoveryAxis') && schema.properties && schema.properties.evidence) out.push(schema)
  for (const v of Object.values(schema)) issueItems(v, out)
  return out
}
// 발견 항목(두 워크플로 공통) = properties 에 severity · evidence 가 있는 객체
function findingItems(schema, out = []) {
  if (!schema || typeof schema !== 'object') return out
  if (schema.properties && schema.properties.severity && schema.properties.evidence) out.push(schema)
  for (const v of Object.values(schema)) findingItems(v, out)
  return out
}
function statusEnums(schema, out = []) {
  if (!schema || typeof schema !== 'object') return out
  const p = schema.properties
  if (p && p.axis && p.status && Array.isArray(p.status.enum)) out.push(p.status.enum)
  for (const v of Object.values(schema)) statusEnums(v, out)
  return out
}
const hasOracle = it => it.required.includes('oracle') && it.properties.oracle && it.properties.oracle.type === 'string'
const hasPremises = s => !!s && s.required.includes('unverifiedPremises') && s.properties.unverifiedPremises &&
  ['claim', 'why', 'howToMeasure'].every(k => s.properties.unverifiedPremises.items.required.includes(k))
const noPremises = s => !!s && !s.required.includes('unverifiedPremises') && !s.properties.unverifiedPremises
const hasLimits = it => it.properties.limits && it.properties.limits.items.properties.kind.enum.join() === 'final-state-ok,premise-island,weak-evidence'
const DYN = ['[동적 축 질문]', '설계 대안']
const hasDyn = p => typeof p === 'string' && DYN.every(m => p.includes(m))

const major = { id: 'Q1', file: 'a.swift', line_range: '10-12', severity: 'major', perspective: 'p', discoveryAxis: 'code_quality',
  origin: 'regression', description: 'd', evidence: 'e', confidence: 90, oracle: 'code: a.swift:10' }
const PEER_RESP = {
  'stage1-arch': { issues: [], strengths: [], overall_assessment: 'o', axisCoverage: [] },
  'stage1-quality': { issues: [major], strengths: [], overall_assessment: 'o' },
  'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
  'stage2-arch-on-peers': { reviewedIds: [], adjustments: [], rejections: [], additions: [] },
  'stage2-quality-on-peers': { reviewedIds: [], adjustments: [], rejections: [], additions: [] },
  'stage3-counter': { challenges: [], missedIssues: [] },
}
const PREMISE = { claim: '27.1 SDK 에서도 같은 알림이 온다', why: '27.0 코드만 읽었다', howToMeasure: '27.1 시뮬 로그' }
const LIVE_RESP = {
  'stage1-arch': { findings: [], okAreas: ['ok'], unverifiedPremises: [PREMISE] },
  'stage1-quality': { findings: [], okAreas: [], unverifiedPremises: [] },
  'stage2-arch-on-quality': { adjustments: [], additions: [] },
  'stage2-quality-on-arch': { adjustments: [], additions: [] },
  'stage3-counter': { challenges: [], missedFindings: [] },
}

async function capture(wf, extra, resp) {
  const schemas = {}
  const prompts = {}
  const r = await run(WF(wf), { args: { ...ARGS, ...extra },
    responder: (p, opts) => { schemas[opts.label] = opts.schema; prompts[opts.label] = p; return resp[opts.label] || null } })
  return { schemas, prompts, result: r.result }
}

;(async () => {
  // ── S8 · F-072 ──
  const def = (await capture('peer-review', {}, PEER_RESP)).schemas
  const s1 = S1P.filter(k => def[k])
  check('review-schemas-loaded', s1.length === 3 && s1.every(k => issueItems(def[k]).length > 0), `Stage 1 스키마 ${s1.length}/3`)
  check('f072-oracle-required', s1.length === 3 && s1.every(k => issueItems(def[k]).every(hasOracle)),
    s1.map(k => `${k}:${issueItems(def[k]).map(hasOracle)}`).join(' '))
  const off = (await capture('peer-review', { oracleField: false }, PEER_RESP)).schemas
  check('f072-oracle-off-absent', S1P.every(k => off[k] && issueItems(off[k]).every(it => !it.required.includes('oracle') && !it.properties.oracle)),
    'oracleField:false 인데 oracle 이 남았다')
  const deep = (await capture('peer-review', { deep: true }, PEER_RESP)).schemas
  const later = LATER_P.filter(k => deep[k])
  check('f072-oracle-deep-all-calls', later.length === 3 && later.every(k => issueItems(deep[k]).length > 0 && issueItems(deep[k]).every(hasOracle)),
    later.map(k => `${k}:${issueItems(deep[k]).map(hasOracle)}`).join(' ') || '교차 · counter 콜 0')

  // ── S9 · 판정 한계 칸 ──
  const peerDef = await capture('peer-review', {}, PEER_RESP)
  const peerOff = await capture('peer-review', { judgmentSlots: false }, PEER_RESP)
  const peerDeep = await capture('peer-review', { deep: true }, PEER_RESP)
  const liveOn = await capture('review-live', { craftAxes: true, judgmentSlots: true }, LIVE_RESP)
  const liveDef = await capture('review-live', {}, LIVE_RESP)
  const gapIn = c => statusEnums(c.schemas['stage1-arch']).some(e => e.includes('gap'))
  const gapLine = c => (c.prompts['stage1-arch'] || '').includes('finding · none · gap · not_applicable') && c.prompts['stage1-arch'].includes('gap=판정 못 함')
  check('f559-gap-in-enum', gapIn(peerDef) && gapLine(peerDef) && gapIn(liveOn) && gapLine(liveOn) && !gapIn(peerOff) && !gapLine(peerOff),
    `peer 기본 ${gapIn(peerDef)}/${gapLine(peerDef)} · live 켬 ${gapIn(liveOn)}/${gapLine(liveOn)} · peer 끔 ${gapIn(peerOff)}/${gapLine(peerOff)}`)

  let rankKeys = null
  try {
    rankKeys = JSON.parse(execFileSync('python3', ['-c',
      'import json, sys; sys.path.insert(0, sys.argv[1]); import review_merge as m; print(json.dumps(sorted(m.AXIS_RANK)))',
      path.join(ROOT, 'scripts')], { encoding: 'utf8' }))
  } catch (e) { console.log(`UNRUN: review_merge.AXIS_RANK 를 읽지 못했다 — ${e.message}`); process.exit(2) }
  const gptEnum = JSON.parse(fs.readFileSync(path.join(ROOT, 'schemas', 'gpt_independent_review_schema.json'), 'utf8'))
    .properties.axis_coverage.items.properties.status.enum
  const claudeEnum = [...new Set([peerDef, liveOn].flatMap(c => statusEnums(c.schemas['stage1-arch']).flat()))]
  const union = [...new Set([...claudeEnum, ...gptEnum])]
  const missing = union.filter(v => !rankKeys.includes(v))
  check('f559-vocab-union-handled', claudeEnum.length > 0 && gptEnum.length > 0 && missing.length === 0,
    `Claude ${claudeEnum} ∪ GPT ${gptEnum} 중 AXIS_RANK(${rankKeys}) 밖: ${missing}`)

  check('f448-premises-peer-review', S1P.every(k => hasPremises(peerDef.schemas[k])) && LATER_P.every(k => noPremises(peerDeep.schemas[k]))
    && S1P.every(k => noPremises(peerOff.schemas[k])),
    `기본 ${S1P.map(k => hasPremises(peerDef.schemas[k]))} · 뒤 콜 ${LATER_P.map(k => noPremises(peerDeep.schemas[k]))} · 끔 ${S1P.map(k => noPremises(peerOff.schemas[k]))}`)
  const up = liveOn.result && liveOn.result.unverifiedPremises
  check('f448-premises-review-live', S1L.every(k => hasPremises(liveOn.schemas[k])) && LATER_L.every(k => noPremises(liveOn.schemas[k]))
    && Array.isArray(up) && up.length === 1 && up[0].lens === 'arch' && up[0].claim === PREMISE.claim
    && S1L.every(k => noPremises(liveDef.schemas[k])) && !!liveDef.result && !('unverifiedPremises' in liveDef.result),
    `켬 ${S1L.map(k => hasPremises(liveOn.schemas[k]))} · 반환 ${JSON.stringify(up)} · 기본 ${S1L.map(k => noPremises(liveDef.schemas[k]))}/${liveDef.result && Object.keys(liveDef.result)}`)

  const peerItems = [...S1P.flatMap(k => findingItems(peerDef.schemas[k])), ...LATER_P.flatMap(k => findingItems(peerDeep.schemas[k]))]
  const liveItems = [...S1L, ...LATER_L].flatMap(k => findingItems(liveOn.schemas[k]))
  const liveDefItems = [...S1L, ...LATER_L].flatMap(k => findingItems(liveDef.schemas[k]))
  check('f178-limits-slot-in-schema', peerItems.length >= 6 && peerItems.every(hasLimits) && liveItems.length >= 5 && liveItems.every(hasLimits)
    && liveDefItems.length >= 5 && liveDefItems.every(it => !it.properties.limits),
    `peer ${peerItems.map(hasLimits)} · live ${liveItems.map(hasLimits)} · live 기본 ${liveDefItems.map(it => !it.properties.limits)}`)

  check('f117-dynamic-axis-prompt', S1P.every(k => hasDyn(peerDef.prompts[k])) && LATER_P.every(k => !hasDyn(peerDeep.prompts[k]))
    && S1L.every(k => hasDyn(liveOn.prompts[k])) && LATER_L.every(k => !hasDyn(liveOn.prompts[k]))
    && S1L.every(k => !hasDyn(liveDef.prompts[k])) && S1P.every(k => !hasDyn(peerOff.prompts[k])),
    `peer ${S1P.map(k => hasDyn(peerDef.prompts[k]))} · live 켬 ${S1L.map(k => hasDyn(liveOn.prompts[k]))} · live 기본 ${S1L.map(k => hasDyn(liveDef.prompts[k]))}`)

  const block = name => {
    const src = fs.readFileSync(WF(name), 'utf8')
    const a = src.indexOf('// 판정 한계 칸 (round 2 S9')
    const b = src.indexOf('suggestion 에 적는다.`', a)
    return a >= 0 && b > a ? src.slice(a, b) : null
  }
  const bp = block('peer-review')
  const bl = block('review-live')
  check('judgment-block-identical', bp !== null && bp === bl, bp === null || bl === null ? '블록 표지를 못 찾았다' : '두 워크플로의 블록 글자가 다르다')

  // ── S19 · 점검 카탈로그 적용 결과 칸 ──
  const hasCatalog = s => !!s && s.required.includes('catalogHits') && !!s.properties.catalogHits &&
    ['catalogId', 'target', 'verdict'].every(k => s.properties.catalogHits.items.required.includes(k)) &&
    s.properties.catalogHits.items.properties.verdict.enum.join() === 'hit,clear,unchecked' &&
    !s.properties.catalogHits.items.properties.severity && !s.properties.catalogHits.items.properties.evidence
  const noCatalog = s => !!s && !s.required.includes('catalogHits') && !s.properties.catalogHits
  const MARK = '[점검 카탈로그]'
  const HIT = { catalogId: 'F-556', target: 'a.swift:10', verdict: 'hit' }
  const liveCat = await capture('review-live', { catalogHits: true }, { ...LIVE_RESP, 'stage3-counter': { challenges: [], missedFindings: [], catalogHits: [HIT] } })
  const peerCat = await capture('peer-review', { deep: true }, { ...PEER_RESP, 'stage3-counter': { challenges: [], missedIssues: [], catalogHits: [HIT] } })
  const peerCatOff = await capture('peer-review', { deep: true, catalogHits: false }, PEER_RESP)
  const ctr = c => c.schemas['stage3-counter']
  const ctrP = c => c.prompts['stage3-counter'] || ''
  check('catalog-hits-counter-schema',
    hasCatalog(ctr(liveCat)) && ctrP(liveCat).includes(MARK) && JSON.stringify(liveCat.result.catalogHits) === JSON.stringify([HIT])
    && noCatalog(ctr(liveDef)) && !ctrP(liveDef).includes(MARK) && !('catalogHits' in liveDef.result)
    && hasCatalog(ctr(peerCat)) && ctrP(peerCat).includes(MARK) && JSON.stringify(peerCat.result.catalogHits) === JSON.stringify([HIT])
    && noCatalog(ctr(peerCatOff)) && !ctrP(peerCatOff).includes(MARK) && !('catalogHits' in peerCatOff.result)
    && S1L.every(k => noCatalog(liveCat.schemas[k])) && [...S1P, ...LATER_P.slice(0, 2)].every(k => noCatalog(peerCat.schemas[k])),
    `live 켬 ${hasCatalog(ctr(liveCat))}/${JSON.stringify(liveCat.result && liveCat.result.catalogHits)} · live 기본 ${noCatalog(ctr(liveDef))} · ` +
    `peer deep ${hasCatalog(ctr(peerCat))}/${JSON.stringify(peerCat.result && peerCat.result.catalogHits)} · peer 끔 ${noCatalog(ctr(peerCatOff))}`)
  const LEAN = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }
  const leanOn = await capture('plan-lean2', { ...LEAN, catalogHits: true }, {})
  const leanBoth = await capture('plan-lean2', { ...LEAN, catalogHits: true, defenseFailurePath: true }, {})
  const leanDef = await capture('plan-lean2', LEAN, {})
  const edgeS = c => c.schemas['lean2-edge']
  const edgeP = c => c.prompts['lean2-edge'] || ''
  const others = c => Object.keys(c.schemas).filter(k => k !== 'lean2-edge')
  check('catalog-hits-edge-schema',
    hasCatalog(edgeS(leanOn)) && edgeP(leanOn).includes(MARK)
    && hasCatalog(edgeS(leanBoth)) && !!edgeS(leanBoth).properties.edgeCases.items.properties.failurePath
    && noCatalog(edgeS(leanDef)) && !edgeP(leanDef).includes(MARK)
    && others(leanOn).length > 0 && others(leanOn).every(k => noCatalog(leanOn.schemas[k])),
    `켬 ${hasCatalog(edgeS(leanOn))} · 방어와 함께 ${hasCatalog(edgeS(leanBoth))} · 기본 ${noCatalog(edgeS(leanDef))} · 다른 콜 ${others(leanOn)}`)

  // ── round 3 S3 · code-pair 카탈로그 스위치 ──
  const CP = { mode: 'full', stepSpec: { id: 'S1', title: 't', goal: 'g', files: ['a'], verify: { kind: 'manual', criterion: 'c' }, complexity: 3 },
    contextPath: '/tmp/context.md', changesetTarget: '/tmp/changeset.json' }
  const CS = { files: [{ path: 'a.swift', changeKind: 'modify', symbolEdits: [{ symbol: 'f', intent: 'i', oldAnchor: 'func f() { old() }', newBody: 'func f() {}', spanLines: 1 }], rationale: 'r' }],
    summary: 's', buildExpectation: 'b' }
  const CP_RESP = { 'stage1-impl': { ...CS, catalogHits: [HIT] }, 'stage2-review-arch': { verdict: 'issues', issues: [{ id: 'I1', severity: 'minor', detail: 'd' }] },
    'stage2-review-quality': { verdict: 'pass', issues: [] }, 'stage3-revise': CS }
  const cpOff = await capture('code-pair', CP, CP_RESP)
  const cpOn = await capture('code-pair', { ...CP, catalogHits: true }, CP_RESP)
  const cpLater = c => Object.keys(c.schemas).filter(k => k !== 'stage1-impl')
  check('r3-catalog-code-pair-switch-off-default',
    noCatalog(cpOff.schemas['stage1-impl']) && !(cpOff.prompts['stage1-impl'] || '').includes(MARK) && !!cpOff.result && !('catalogHits' in cpOff.result),
    `스키마 ${noCatalog(cpOff.schemas['stage1-impl'])} · 반환 ${cpOff.result && Object.keys(cpOff.result)}`)
  check('r3-catalog-code-pair-switch-on-recorded',
    hasCatalog(cpOn.schemas['stage1-impl']) && (cpOn.prompts['stage1-impl'] || '').includes(MARK)
    && !!cpOn.result && JSON.stringify(cpOn.result.catalogHits) === JSON.stringify([HIT])
    && cpLater(cpOn).length > 0 && cpLater(cpOn).every(k => noCatalog(cpOn.schemas[k])),
    `스키마 ${hasCatalog(cpOn.schemas['stage1-impl'])} · 반환 ${JSON.stringify(cpOn.result && cpOn.result.catalogHits)} · 다른 콜 ${cpLater(cpOn)}`)

  console.log(`review-schemas: ${fail ? 'FAIL' : 'OK'} (${total - fail}/${total})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`UNRUN: 워크플로 실행 실패 — ${e && e.message}`); process.exit(2) })
