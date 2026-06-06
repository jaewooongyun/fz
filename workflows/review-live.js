// workflows/review-live.js — fz-review 교차 리뷰 (TEAM live-review 대체, Wave 1)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + pilot 실측]
//   표준 패턴 3종 적용. 대형 입력(diff)은 args가 아닌 파일 경로 전달 (§12 — args 직렬화 한계 회피).
//   호출(Lead, SKILL.md 절차): Lead가 diff를 파일로 기록 후
//     Workflow({ scriptPath: '{plugin_root}/workflows/review-live.js',
//       args: { diffPath, intentContext } })
//   반환: { mode:'workflow', findings:[...{finalSeverity, crossVerdict, counterVerdict}], okAreas, metrics }
//     또는 { mode:'fallback', reason, metrics } → Lead는 SOLO 리뷰 경로 수행.
//   Workflow 외부(Lead 책임 유지): L3 통합 / review-correctness(RTM 시 Phase 4.5) / Codex validate(Phase 5.5) / wall-clock.
//
// [설계 — modules/patterns/live-review.md 평탄화]
//   Stage1 독립 병렬: review-arch(opus) + review-quality(sonnet) — Round 1 독립성 (opus 동시 1 + Lead = 2).
//   Stage2 교차: 상대 findings에 id-기반 severity 조정/FP 판정 (live-review Round 2 동형, sonnet 2).
//   Stage3 counter: DA 패스 — findings 반론 + okAreas 도전 (live-review.md L16 기존 Supporting — ablation Verifier 재판정 레이어 아님).
//   병합: 스크립트 binary 규칙 (id-기반 verdict 반영 — §11/§12 분류: 기계 작업).
//   budget 가드: 해당 없음 — 고정 5-call(가변 fan-out 없음). §12 거버넌스 단서 참조.

export const meta = {
  name: 'review-live',
  description: 'fz-review 교차 리뷰 — arch/quality 독립 병렬 → id-기반 교차 조정 → counter DA → 스크립트 병합. 5-call',
}

const ReviewFindingsSchema = {
  type: 'object', required: ['findings', 'okAreas'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'severity', 'category', 'title', 'detail', 'evidence'],
        properties: {
          id: { type: 'string', description: '리뷰어 내 고유 id (예: A1, Q3)' },
          severity: { type: 'string', enum: ['critical', 'major', 'minor'] },
          category: { type: 'string' },
          title: { type: 'string' },
          detail: { type: 'string' },
          file: { type: 'string' },
          evidence: { type: 'string', description: '실제 diff/파일 인용 — 추측 금지' },
        },
      },
    },
    okAreas: { type: 'array', items: { type: 'string' }, description: '정상 판정 영역 (counter 도전 입력)' },
  },
}

const CrossReviewSchema = {
  type: 'object', required: ['adjustments', 'additions'],
  properties: {
    adjustments: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'verdict', 'note'],
        properties: {
          id: { type: 'string', description: '상대 리뷰어의 finding id' },
          verdict: { type: 'string', enum: ['agree', 'adjust', 'false_positive'] },
          newSeverity: { type: 'string', enum: ['critical', 'major', 'minor'] },
          note: { type: 'string', description: 'false_positive/adjust는 실측 인용 필수' },
        },
      },
    },
    additions: ReviewFindingsSchema.properties.findings,
  },
}

const CounterSchema = {
  type: 'object', required: ['challenges', 'missedFindings'],
  properties: {
    challenges: {
      type: 'array',
      items: {
        type: 'object', required: ['target', 'verdict', 'note'],
        properties: {
          target: { type: 'string', description: 'finding id 또는 okArea 문구' },
          verdict: { type: 'string', enum: ['uphold', 'refute'] },
          note: { type: 'string' },
        },
      },
    },
    missedFindings: ReviewFindingsSchema.properties.findings,
  },
}

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [리뷰 대상]/[변경 의도]만이 과제의 전부다. ' +
  '무관한 작업 폴더(ASD-*, 토픽 폴더 등)를 읽지 말 것. 파일 접근은 [리뷰 대상] diff 파일과 그 안에 나열된 변경 파일만. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. 출력은 schema 준수 JSON.'

// ── args 방어 파싱 + fail-fast (§12 표준 패턴 2) ──
const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

let agentCalls = 0
let nullCalls = 0
let fallbackCount = 0
async function callAgent(prompt, opts) {
  agentCalls += 1
  const out = await agent(prompt, opts)
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) }
  return out
}
function metrics(stagesCompleted) {
  return { agentCalls, nullCount: nullCalls, fallbackCount, stagesCompleted }
}

if (!input || !input.diffPath || !input.intentContext) {
  log(`FATAL args invalid (typeof=${typeof args}) — diffPath/intentContext 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}

const TARGET = `[리뷰 대상] diff 파일: ${input.diffPath} (Read로 로드)\n[변경 의도] ${input.intentContext}`

// ════════ Stage 1: 독립 병렬 리뷰 (Round 1 독립성) ════════
phase('Stage 1: arch/quality 독립 리뷰')
const [arch, quality] = await parallel([
  () => callAgent(
    `${OVERRIDE}\n[역할] 아키텍처 리뷰어(review-arch 렌즈) — 설계 결정·레이어 위반·확장성\n${TARGET}\n` +
    `[목표] 아키텍처 관점 findings (id는 A1, A2...) + 정상 판정 okAreas. 각 finding에 evidence 인용.`,
    { label: 'stage1-arch', agentType: 'fz:review-arch', model: 'opus', schema: ReviewFindingsSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 품질 리뷰어(review-quality 렌즈) — 코드 품질·dead code·성능·일관성\n${TARGET}\n` +
    `[목표] 품질 관점 findings (id는 Q1, Q2...) + 정상 판정 okAreas. 각 finding에 evidence 인용.`,
    { label: 'stage1-quality', agentType: 'fz:review-quality', model: 'sonnet', schema: ReviewFindingsSchema }),
])
if (!arch && !quality) { fallbackCount += 1; return { mode: 'fallback', reason: 'stage1 both null', metrics: metrics(0) } }
if (!arch || !quality) log('WARN stage1 한쪽 null — 단독 진행 (교차 조정 생략)')

// id 네임스페이스 강제 — 리뷰어 간 id 충돌 방지 (리뷰 C-3 교정: 프롬프트 지시가 아닌 스크립트 보장)
if (arch) arch.findings = arch.findings.map(f => ({ ...f, id: `A:${f.id}` }))
if (quality) quality.findings = quality.findings.map(f => ({ ...f, id: `Q:${f.id}` }))

// ════════ Stage 2: 교차 조정 (id-기반 — live-review Round 2) ════════
phase('Stage 2: 교차 severity 조정')
let archOnQuality = null
let qualityOnArch = null
if (arch && quality) {
  const cross = await parallel([
    () => callAgent(
      `${OVERRIDE}\n[역할] 아키텍처 리뷰어 — 교차 조정\n${TARGET}\n[상대(품질) findings] ${JSON.stringify(quality.findings)}\n` +
      `[목표] 각 finding의 아키텍처 함의로 severity 조정(adjust+newSeverity)/동의(agree)/기각(false_positive — 실측 인용 필수). 놓친 아키텍처 finding은 additions(id A-X)로.`,
      { label: 'stage2-arch-on-quality', agentType: 'fz:review-arch', model: 'sonnet', schema: CrossReviewSchema }),
    () => callAgent(
      `${OVERRIDE}\n[역할] 품질 리뷰어 — 교차 보충\n${TARGET}\n[상대(아키) findings] ${JSON.stringify(arch.findings)}\n` +
      `[목표] 각 finding의 품질/성능 영향 보충으로 verdict 반환. 놓친 품질 finding은 additions(id Q-X)로.`,
      { label: 'stage2-quality-on-arch', agentType: 'fz:review-quality', model: 'sonnet', schema: CrossReviewSchema }),
  ])
  archOnQuality = cross[0]
  qualityOnArch = cross[1]
  if (archOnQuality) archOnQuality.additions = archOnQuality.additions.map(f => ({ ...f, id: `XA:${f.id}` }))
  if (qualityOnArch) qualityOnArch.additions = qualityOnArch.additions.map(f => ({ ...f, id: `XQ:${f.id}` }))
  if (!archOnQuality || !qualityOnArch) log('WARN stage2 부분 null — 해당 측 조정 미반영')
}

// ════════ Stage 3: Counter DA (okAreas 도전 + findings 반론) ════════
phase('Stage 3: counter DA')
const allFindings = []
  .concat(arch ? arch.findings : [], quality ? quality.findings : [])
  .concat(archOnQuality ? archOnQuality.additions : [], qualityOnArch ? qualityOnArch.additions : [])
const allOkAreas = [].concat(arch ? arch.okAreas : [], quality ? quality.okAreas : [])
const counter = await callAgent(
  `${OVERRIDE}\n[역할] 반론자(review-counter 렌즈) — Devil's Advocate\n${TARGET}\n` +
  `[findings] ${JSON.stringify(allFindings)}\n[okAreas(정상 판정)] ${JSON.stringify(allOkAreas)}\n` +
  `[목표] (1) 각 finding을 실측 재검증 — 과장/오독이면 refute + 인용. (2) okAreas에 "정말 OK인가?" 반례 탐색 — 반례 발견 시 missedFindings(id C-X)로. 라인 인용 오류를 특히 의심.`,
  { label: 'stage3-counter', agentType: 'fz:review-counter', model: 'sonnet', schema: CounterSchema })
if (!counter) log('WARN counter null — DA 패스 미수행 (findings 원판정 유지)')

// ════════ 병합 — 스크립트 binary 규칙 (id-기반 verdict 반영) ════════
const adjustMap = {}
for (const c of [archOnQuality, qualityOnArch].filter(Boolean)) {
  for (const a of c.adjustments) adjustMap[a.id] = a
}
const counterMap = {}
if (counter) for (const ch of counter.challenges) counterMap[ch.target] = ch

const findings = allFindings.map((f) => {
  const adj = adjustMap[f.id]
  const ctr = counterMap[f.id]
  return {
    ...f,
    finalSeverity: adj && adj.verdict === 'adjust' && adj.newSeverity ? adj.newSeverity : f.severity,
    crossVerdict: adj ? adj.verdict : 'unreviewed',
    crossNote: adj ? adj.note : undefined,
    counterVerdict: ctr ? ctr.verdict : 'unchallenged',
    counterNote: ctr ? ctr.note : undefined,
    // false_positive/refute여도 제거하지 않음 — 최종 기각은 Lead 판정 (live-review.md Lead 역할 보존)
  }
}).concat(counter ? counter.missedFindings.map(f => ({ ...f, id: `C:${f.id}`, finalSeverity: f.severity, crossVerdict: 'counter_found', counterVerdict: 'uphold' })) : [])

// okArea 도전 보존 (리뷰 C-1 교정 — finding id에 매칭되지 않는 challenge는 okArea 도전)
const findingIds = new Set(findings.map(f => f.id))
const okAreaChallenges = counter ? counter.challenges.filter(ch => !findingIds.has(ch.target)) : []

const dist = {
  critical: findings.filter(f => f.finalSeverity === 'critical').length,
  major: findings.filter(f => f.finalSeverity === 'major').length,
  minor: findings.filter(f => f.finalSeverity === 'minor').length,
  fpFlagged: findings.filter(f => f.crossVerdict === 'false_positive' || f.counterVerdict === 'refute').length,
}
log(`findings ${findings.length}건 — critical ${dist.critical} / major ${dist.major} / minor ${dist.minor} / FP·refute 플래그 ${dist.fpFlagged} (최종 기각은 Lead)`)

// stagesCompleted = 완전 완주한 stage 수 (리뷰 Q2 교정 — stage2 미완주+stage3 완주 시 오보고 방지)
const s1full = !!(arch && quality)
const s2full = !!(archOnQuality && qualityOnArch)
const s3full = !!counter
const stagesCompleted = [s1full, s2full, s3full].filter(Boolean).length
return {
  mode: 'workflow',
  findings,
  okAreas: allOkAreas,
  okAreaChallenges, // counter의 okArea 반례 (Lead 판정 입력)
  distribution: dist,
  metrics: metrics(stagesCompleted), // Lead가 experiment-log §5.7 fz-review 테이블 기록
}
