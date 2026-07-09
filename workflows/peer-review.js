// workflows/peer-review.js — fz-peer-review Tier 2/3 Analyze 코어 (TEAM 대체, Wave 4)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + review-live.js 동형 선례]
//   표준 패턴 3종 적용. 대형 입력(diff/evidence)은 args가 아닌 파일 경로 전달 (§12).
//   호출(Lead, SKILL.md Analyze Step): Lead가 Gather 산출물(diff/evidence/base-behavior)을 파일로 기록 후
//     Workflow({ scriptPath: '{plugin_root}/workflows/peer-review.js',
//       args: { diffPath, intentContext, evidencePaths?, basePath?, deep? } })
//   effort 계약: 전 agent() 호출 model+effort(=xhigh) 명시. 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   deep=false → Tier 2 (Lite): Stage1 3-병렬만 (3-call). Confidence Matrix 미투표 — Lead 단순 병합.
//   deep=true  → Tier 3 (Full): +Stage2 교차(arch↔quality) +Stage3 counter DA (6-call). Lead full Matrix.
//   반환: { mode:'workflow', reviews:[...], crossAdjustments, counter, metrics } 또는 { mode:'fallback', reason, metrics }.
//   Workflow 외부(Lead 책임 유지): Confidence Matrix 계산(독립성 가중=판단) / origin severity 보정 /
//     Codex DA(스크립트 밖 — Lead가 /fz-codex, cross-provider 스폰 금지 — 마이그레이션 결정) / dedup+투표 / wall-clock.
//   base 원본은 Lead가 Gather에서 prefetch하여 basePath로 전달 (LB1 — 에이전트가 SendMessage로 요청하지 않음).
//   budget 가드: 해당 없음 — 고정 3(Tier2)/6(Tier3) call (가변 fan-out 없음). §12 거버넌스 단서.

export const meta = {
  name: 'peer-review',
  description: 'fz-peer-review Tier2/3 Analyze — arch/quality/correctness 3-병렬 → (deep) arch↔quality 교차 + counter DA. 3 or 6-call',
}

// 팀원 PR 리뷰 이슈 스키마 (fz-peer-review 출력 계약 — SKILL.md:267 + arch-critic/code-auditor)
const PeerReviewSchema = {
  type: 'object', required: ['issues', 'strengths', 'overall_assessment'],
  properties: {
    issues: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'file', 'severity', 'perspective', 'origin', 'description', 'evidence', 'confidence'],
        properties: {
          id: { type: 'string', description: '리뷰어 내 고유 id (예: A1, Q3, C2)' },
          file: { type: 'string' },
          line_range: { type: 'string' },
          perspective: { type: 'string' },
          severity: { type: 'string', enum: ['critical', 'major', 'minor', 'suggestion'] },
          origin: { type: 'string', enum: ['regression', 'pre-existing', 'improvement'], description: 'PR이 만든 문제(regression) vs 기존(pre-existing) vs 개선여지(improvement)' },
          description: { type: 'string', description: 'WHY 필수, ≤400chars' },
          evidence: { type: 'string', description: '실제 diff/파일 인용 — 추측 금지' },
          suggestion: { type: 'string', description: '≤300chars' },
          confidence: { type: 'number', description: '0-100. 80 미만 미보고' },
        },
      },
    },
    strengths: { type: 'array', items: { type: 'string' }, description: '정상/우수 판정 (max 3, counter 도전 입력)' },
    overall_assessment: { type: 'string' },
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
          id: { type: 'string', description: '상대 리뷰어의 issue id' },
          verdict: { type: 'string', enum: ['agree', 'adjust', 'false_positive'] },
          newSeverity: { type: 'string', enum: ['critical', 'major', 'minor', 'suggestion'] },
          note: { type: 'string', description: 'false_positive/adjust는 실측 인용 필수' },
        },
      },
    },
    additions: PeerReviewSchema.properties.issues,
  },
}

const CounterSchema = {
  type: 'object', required: ['challenges', 'missedIssues'],
  properties: {
    challenges: {
      type: 'array',
      items: {
        type: 'object', required: ['target', 'verdict', 'note'],
        properties: {
          target: { type: 'string', description: 'issue id 또는 strength 문구' },
          verdict: { type: 'string', enum: ['uphold', 'refute'] },
          note: { type: 'string' },
        },
      },
    },
    missedIssues: PeerReviewSchema.properties.issues,
  },
}

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [리뷰 대상]/[변경 의도]/[증거]만이 과제의 전부다. ' +
  '무관한 작업 폴더(ASD-*, 토픽 폴더 등)를 읽지 말 것. 파일 접근은 이 프롬프트가 나열한 경로만. ' +
  '원본 동작이 필요하면 [증거]의 base 경로를 Read (Lead가 prefetch함 — SendMessage로 요청하지 말 것). ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력을 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. 실행 제안 금지: git 상태변경(commit/push 등)·raw codex exec는 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  'Convention(3+ 모듈 동일)을 위반으로 판정하지 않는다(suggestion까지). confidence 80 미만은 보고하지 않는다. ' +
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
// rate-limit/스폰 실패 폴백 (Stage 1 병렬 3콜 한정): parallel 결과의 null 항목만 동일 thunk로 1회 순차 재시도
// (parallel 경유 = barrier 실패→null 계약 재사용). 여전히 null이면 기존 all-null→fallback / 부분-null→WARN 경로 유지.
async function parallelWithRetry(thunks) {
  const out = await parallel(thunks)
  for (let i = 0; i < out.length; i += 1) {
    if (!out[i]) {
      log(`병렬 ${i}번 null — 순차 재시도 1회 (rate-limit/스폰 실패 폴백)`)
      out[i] = (await parallel([thunks[i]]))[0]
    }
  }
  return out
}

if (!input || !input.diffPath || !input.intentContext) {
  log(`FATAL args invalid (typeof=${typeof args}) — diffPath/intentContext 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}

const deep = input.deep === true || input.deep === 'true'  // Tier 3 = full (교차+counter)
const evidenceLine = input.evidencePaths ? `\n[증거] ${input.evidencePaths}` : ''
const baseLine = input.basePath ? `\n[증거] base 원본(prefetch): ${input.basePath} (Read로 로드)` : ''
const TARGET = `[리뷰 대상] diff 파일: ${input.diffPath} (Read로 로드)\n[변경 의도] ${input.intentContext}${evidenceLine}${baseLine}`

// ════════ Stage 1: 독립 병렬 리뷰 (3-Model — Round 1 독립성) ════════
phase('Stage 1: arch/quality/correctness 독립 리뷰')
const [arch, quality, correctness] = await parallelWithRetry([
  () => callAgent(
    `${OVERRIDE}\n[역할] 아키텍처 리뷰어(review-arch 렌즈) — 설계 결정·레이어 위반·확장성\n${TARGET}\n` +
    `[목표] 아키텍처 관점 issues (id는 A1, A2...) + strengths(max3) + overall_assessment. 각 issue에 evidence 인용 + origin.`,
    { label: 'stage1-arch', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: PeerReviewSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 품질 리뷰어(review-quality 렌즈) — 코드 품질·dead code·성능·일관성\n${TARGET}\n` +
    `[목표] 품질 관점 issues (id는 Q1, Q2...) + strengths(max3) + overall_assessment. 각 issue에 evidence 인용 + origin.`,
    { label: 'stage1-quality', agentType: 'fz:review-quality', model: 'opus', effort: 'xhigh', schema: PeerReviewSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 정확성 리뷰어(review-correctness 렌즈) — 요구사항 충족·로직 정확성·엣지 케이스\n${TARGET}\n` +
    `[목표] 정확성 관점 issues (id는 C1, C2...) + strengths(max3) + overall_assessment. 각 issue에 evidence 인용 + origin. ` +
    `함수 제거/책임 이전 감지 시 base 원본(prefetch)과 대조 — 원본 책임이 어디로 이전됐는지 추적.`,
    { label: 'stage1-correctness', agentType: 'fz:review-correctness', model: 'opus', effort: 'xhigh', schema: PeerReviewSchema }),
])
if (!arch && !quality && !correctness) { fallbackCount += 1; return { mode: 'fallback', reason: 'stage1 all null', metrics: metrics(0) } }
if (!arch || !quality || !correctness) log('WARN stage1 일부 null — 단독 진행 (해당 렌즈 결측)')

// id 네임스페이스 강제 — 리뷰어 간 id 충돌 방지 (스크립트 보장)
if (arch) arch.issues = arch.issues.map(f => ({ ...f, id: `A:${f.id}` }))
if (quality) quality.issues = quality.issues.map(f => ({ ...f, id: `Q:${f.id}` }))
if (correctness) correctness.issues = correctness.issues.map(f => ({ ...f, id: `C:${f.id}` }))

const reviews = [
  arch ? { agent: 'review-arch', ...arch } : null,
  quality ? { agent: 'review-quality', ...quality } : null,
  correctness ? { agent: 'review-correctness', ...correctness } : null,
].filter(Boolean)

// ── Tier 2 (Lite): Stage1만. Confidence Matrix 미투표 — Lead 단순 병합 ──
if (!deep) {
  const allIssues = reviews.flatMap(r => r.issues)
  log(`Tier2(Lite) — reviews ${reviews.length}, issues ${allIssues.length}. Matrix 미투표(Lead 병합).`)
  return { mode: 'workflow', tier: 2, reviews, issues: allIssues, metrics: metrics(reviews.length === 3 ? 1 : 0) }
}

// ════════ Stage 2: 교차 조정 (arch↔quality — correctness 불참, 결정 C: 6-call 고정) ════════
phase('Stage 2: arch↔quality 교차 severity 조정')
let archOnQuality = null
let qualityOnArch = null
if (arch && quality) {
  const cross = await parallel([
    () => callAgent(
      `${OVERRIDE}\n[역할] 아키텍처 리뷰어 — 교차 조정\n${TARGET}\n[상대(품질) issues] ${JSON.stringify(quality.issues)}\n` +
      `[목표] 각 issue의 아키텍처 함의로 severity 조정(adjust+newSeverity)/동의(agree)/기각(false_positive — 실측 인용 필수). 놓친 아키텍처 issue는 additions(id A-X)로.`,
      { label: 'stage2-arch-on-quality', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: CrossReviewSchema }),
    () => callAgent(
      `${OVERRIDE}\n[역할] 품질 리뷰어 — 교차 보충\n${TARGET}\n[상대(아키) issues] ${JSON.stringify(arch.issues)}\n` +
      `[목표] 각 issue의 품질/성능 영향 보충으로 verdict 반환. 놓친 품질 issue는 additions(id Q-X)로.`,
      { label: 'stage2-quality-on-arch', agentType: 'fz:review-quality', model: 'opus', effort: 'xhigh', schema: CrossReviewSchema }),
  ])
  archOnQuality = cross[0]
  qualityOnArch = cross[1]
  if (archOnQuality) archOnQuality.additions = archOnQuality.additions.map(f => ({ ...f, id: `XA:${f.id}` }))
  if (qualityOnArch) qualityOnArch.additions = qualityOnArch.additions.map(f => ({ ...f, id: `XQ:${f.id}` }))
  if (!archOnQuality || !qualityOnArch) log('WARN stage2 부분 null — 해당 측 조정 미반영')
}

// ════════ Stage 3: Counter DA (strengths 도전 + issues 반론) ════════
phase('Stage 3: counter DA')
const allIssues = []
  .concat(arch ? arch.issues : [], quality ? quality.issues : [], correctness ? correctness.issues : [])
  .concat(archOnQuality ? archOnQuality.additions : [], qualityOnArch ? qualityOnArch.additions : [])
const allStrengths = [].concat(arch ? arch.strengths : [], quality ? quality.strengths : [], correctness ? correctness.strengths : [])
const counter = await callAgent(
  `${OVERRIDE}\n[역할] 반론자(review-counter 렌즈) — Devil's Advocate\n${TARGET}\n` +
  `[issues] ${JSON.stringify(allIssues)}\n[strengths(정상/우수 판정)] ${JSON.stringify(allStrengths)}\n` +
  `[목표] (1) 각 issue를 실측 재검증 — 과장/오독이면 refute + 인용. (2) strengths에 "정말 문제 없나?" 반례 탐색 — 반례 발견 시 missedIssues(id CT-X)로. 라인 인용 오류를 특히 의심.`,
  { label: 'stage3-counter', agentType: 'fz:review-counter', model: 'opus', effort: 'xhigh', schema: CounterSchema })
if (!counter) log('WARN counter null — DA 패스 미수행 (issues 원판정 유지)')

// ════════ 병합 — 스크립트 binary 규칙 (id-기반 verdict 반영. Confidence Matrix/투표는 Lead) ════════
const adjustMap = {}
for (const c of [archOnQuality, qualityOnArch].filter(Boolean)) {
  for (const a of c.adjustments) adjustMap[a.id] = a
}
const counterMap = {}
if (counter) for (const ch of counter.challenges) counterMap[ch.target] = ch

const mergedIssues = allIssues.map((f) => {
  const adj = adjustMap[f.id]
  const ctr = counterMap[f.id]
  return {
    ...f,
    finalSeverity: adj && adj.verdict === 'adjust' && adj.newSeverity ? adj.newSeverity : f.severity,
    crossVerdict: adj ? adj.verdict : 'unreviewed',
    crossNote: adj ? adj.note : undefined,
    counterVerdict: ctr ? ctr.verdict : 'unchallenged',
    counterNote: ctr ? ctr.note : undefined,
    // false_positive/refute여도 제거하지 않음 — 최종 기각은 Lead 판정
  }
}).concat(counter ? counter.missedIssues.map(f => ({ ...f, id: `CT:${f.id}`, finalSeverity: f.severity, crossVerdict: 'counter_found', counterVerdict: 'uphold' })) : [])

// strength 도전 보존 (finding id에 매칭되지 않는 challenge는 strength 도전)
const issueIds = new Set(mergedIssues.map(f => f.id))
const strengthChallenges = counter ? counter.challenges.filter(ch => !issueIds.has(ch.target)) : []

const dist = {
  critical: mergedIssues.filter(f => f.finalSeverity === 'critical').length,
  major: mergedIssues.filter(f => f.finalSeverity === 'major').length,
  minor: mergedIssues.filter(f => f.finalSeverity === 'minor').length,
  fpFlagged: mergedIssues.filter(f => f.crossVerdict === 'false_positive' || f.counterVerdict === 'refute').length,
}
log(`Tier3 issues ${mergedIssues.length}건 — critical ${dist.critical} / major ${dist.major} / minor ${dist.minor} / FP·refute 플래그 ${dist.fpFlagged} (최종 투표·Matrix는 Lead)`)

// stagesCompleted = 완전 완주 stage 수 (stage2 미완주+stage3 완주 시 오보고 방지)
const s1full = !!(arch && quality && correctness)
const s2full = !!(archOnQuality && qualityOnArch)
const s3full = !!counter
const stagesCompleted = [s1full, s2full, s3full].filter(Boolean).length
return {
  mode: 'workflow',
  tier: 3,
  reviews,          // 원본 per-agent (strengths/overall_assessment 포함)
  issues: mergedIssues,
  crossAdjustments: { archOnQuality, qualityOnArch },
  strengthChallenges,  // counter의 strength 반례 (Lead 판정 입력)
  distribution: dist,
  metrics: metrics(stagesCompleted),  // Lead가 experiment-log §5.7 fz-peer-review 테이블 기록
}
