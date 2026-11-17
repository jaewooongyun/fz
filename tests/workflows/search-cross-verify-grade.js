// search-cross-verify 등급 강제 — 스크립트가 병합자의 주장(sources · crossVerified)을 실행 사실로 거른다.
//
// 등급 규칙(skills/fz-search/SKILL.md § 신뢰도 등급): ★★★ 양쪽 발견 / ★★ 단독 + 교차 확인 / ★ 단독 + 교차 미확인.
// 병합 콜(stage3-merge)의 응답은 주장일 뿐이다. 렌즈가 죽었거나 교차 판정이 빠졌는데 병합자가 두 출처 · 교차 확인을 적어 오면
// 스크립트가 등급을 낮춘다:
//   · 출처는 중복을 걷어 센다                       · 렌즈 하나라도 null 이면 전 항목 ★ (로그 '등급 상한 ★' 과 같은 말)
//   · 교차 확인은 교차 판정 둘이 다 있을 때만 인정한다 · 항목은 버리지 않는다(등급만 낮춘다)
// 대조 셀(콜 전부 성공)은 ★★★ · ★★ · ★ 가 그대로 나와야 한다 — 과하게 낮추지 않는다.
// ⛔ 남는 한계: 콜이 전부 성공한 뒤 병합자가 지어낸 출처 · 교차 확인은 걸러지지 않는다(병합 스키마에 원본 finding id 연결이 없다).
// ⛔ 스크립트를 통째로 돌린다(tests/lib/wf_harness.js) — 등급 계산은 다른 러너가 실행하지 않는다.
'use strict'
const path = require('path')
const { run } = require('../lib/wf_harness')

const WF = path.join(__dirname, '..', '..', 'workflows', 'search-cross-verify.js')
const FINDINGS = { findings: [{ id: '1', kind: 'definition', file: 'a', note: 'n' }] }
const CROSS = { reviewed: [], additions: [] }
const item = (sources, crossVerified, file = 'a') => ({ file, kind: 'definition', note: 'n', sources, crossVerified })

// dead = null 을 돌려줄 label 들 · merged = 병합 콜이 주장하는 항목들
const go = (dead, merged) => run(WF, { args: { query: 'q', codeContext: '/tmp' },
  responder: (prompt, opts) => (dead.includes(opts.label) ? null
    : opts.label.startsWith('stage1') ? JSON.parse(JSON.stringify(FINDINGS))
      : opts.label.startsWith('stage2') ? CROSS : { merged: JSON.parse(JSON.stringify(merged)) }) })
const grades = r => r.result.results.map(x => x.confidence).join(',')

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

const S2 = ['stage2-sym-on-pat', 'stage2-pat-on-sym']
const CELLS = [
  ['lens-dead-claims-both — 렌즈 하나 null 인데 병합이 두 출처 · 교차 확인을 주장 → ★', ['stage1-pattern'], [item(['symbolic', 'pattern'], true)], '★'],
  ['duplicate-source — 같은 출처를 두 번 적었다 → 한 번으로 센다(★)', [], [item(['symbolic', 'symbolic'], false)], '★'],
  ['cross-both-dead — 교차 판정 둘 다 null 인데 교차 확인을 주장 → ★', S2, [item(['pattern'], true)], '★'],
  ['cross-one-dead — 교차 판정 하나 null → 교차 확인을 인정하지 않는다(★) · 양쪽 발견은 그대로 ★★★', [S2[0]],
    [item(['pattern'], true), item(['symbolic', 'pattern'], false, 'b')], '★,★★★'],
  ['control-both-sources — 대조: 양쪽 발견 → ★★★', [], [item(['symbolic', 'pattern'], false)], '★★★'],
  ['control-single-confirmed — 대조: 단독 + 교차 확인 → ★★', [], [item(['pattern'], true)], '★★'],
  ['control-single-unconfirmed — 대조: 단독 + 교차 미확인 → ★', [], [item(['symbolic'], false)], '★'],
]

;(async () => {
  for (const [name, dead, merged, want] of CELLS) {
    const r = await go(dead, merged)
    check(name, grades(r) === want, grades(r))
  }
  // 낮출 뿐 버리지 않는다 — 렌즈가 죽은 실행에서도 병합 항목 수 == 결과 수, 분포도 낮춘 등급을 센다
  const three = [item(['symbolic', 'pattern'], true), item(['pattern'], true, 'b'), item(['symbolic'], false, 'c')]
  const kept = await go(['stage1-pattern'], three)
  const dist = kept.result.gradeDistribution
  check('kept-not-dropped — 렌즈 하나 null: 항목 3개가 전부 남고 전부 ★ · 분포 0/0/3',
    grades(kept) === '★,★,★' && dist.three === 0 && dist.two === 0 && dist.one === 3, `${grades(kept)} · ${JSON.stringify(dist)}`)
  // 로그가 상한을 말하면 결과도 그 상한 안이다 — 로그와 등급이 다른 말을 하지 않는다
  check("cap-log-matches-result — 로그에 '등급 상한 ★' 이 있는 실행의 결과에 ★ 를 넘는 등급이 없다",
    kept.logs.some(l => l.includes('등급 상한 ★')) && kept.result.results.every(x => x.confidence === '★'), `${grades(kept)} · ${kept.logs.join(' / ')}`)
  console.log(`\nsearch-cross-verify 등급 ${fail ? '실패 ' + fail + '건' : '전건 통과'}`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
