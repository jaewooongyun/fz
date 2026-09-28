// workflows/review-live.js — fz-review 교차 리뷰 (TEAM live-review 대체, Wave 1)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + pilot 실측]
//   표준 패턴 3종 적용. 대형 입력(diff)은 args가 아닌 파일 경로 전달 (§12 — args 직렬화 한계 회피).
//   호출(Lead, SKILL.md 절차): Lead가 diff를 파일로 기록 후
//     Workflow({ scriptPath: '{plugin_root}/workflows/review-live.js',
//       args: { diffPath, intentContext, structuralContext?, craftAxes?, projectRulesPath?, crossRequiredFields?, locatedFindings? } })
//   structuralContext: 구조 축 브리프(modules/review-structural-axes.md §3+§4를 Lead가 Read해 전달).
//     ⛔ arch 렌즈에만 주입된다 — quality는 결함 축 유지(회귀 방어) + A/B 검증 범위 일치.
//   craftAxes: craft 6축 판정 — ⛔ 기본 off(R-B). true 면 arch 렌즈에만 craft 줄 · axisCoverage(6축 필수) · craftAxis · ruleRef 가 들어간다.
//     미지정·false 면 모든 콜의 프롬프트·스키마가 이전과 바이트 단위로 같다.
//   locatedFindings: §3 병합 키 — ⛔ 기본 off(R-C S16c). true 면 Stage 1 두 렌즈 finding 에 line_range · discoveryAxis 선택 필드가 생긴다.
//     craft 와 다른 관심사라 따로 켠다 — craft 효과를 A/B 로 잴 때는 두 arm 모두 켜서 병합 키 효과를 지운다. 미지정·false 면 바이트 단위로 같다.
//   projectRulesPath: 검증을 통과한 규칙 레코드(JSON — modules/project-rules.md) 경로. craftAxes:true 일 때만 효력 · arch 렌즈에만.
//   crossRequiredFields: ⛔ 기본 off(R-B). true 면 Stage 2 교차 프롬프트에 additions 항목의 required 키(스키마에서 읽음)를 적는다(tests/workflows/cross-required-fields.js).
//   effort 계약: 전 agent() 호출 model+effort(=xhigh) 명시. 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   반환: { mode:'workflow', findings:[...{finalSeverity, crossVerdict, counterVerdict}], okAreas, metrics }
//     또는 { mode:'fallback', reason, metrics } → Lead는 실패 복구 사다리(guides/skill-authoring.md §12 L1~L4) — ⛔ 즉시 SOLO 아님, L4는 사용자 승인 후
//   Workflow 외부(Lead 책임 유지): L3 통합 / review-correctness(RTM 시 Phase 4.5) / GPT validate(Phase 5.5) / wall-clock.
//
// [설계 — TEAM live-review 패턴 평탄화]
//   Stage1 독립 병렬: review-arch(opus) + review-quality(opus) — Round 1 독립성 (opus 동시 2 + Lead=fable).
//   Stage2 교차: 상대 findings에 id-기반 severity 조정/FP 판정 (live-review Round 2 동형, opus 2).
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
          severity: { type: 'string', enum: ['critical', 'major', 'minor', 'suggestion'] },
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
          newSeverity: { type: 'string', enum: ['critical', 'major', 'minor', 'suggestion'] },
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

// craft 6축 — ⛔ tests/fixtures/quality 의 AXES6(SC-4 채점 축)과 같은 목록·순서다. peer-review.js · modules/review-structural-axes.md §6
//    과 함께 tests/workflows/craft-axes.js 가 일치를 단언한다. 한 줄 리터럴로 둔다(그 테스트가 이 줄을 추출한다).
const CRAFT_AXES = ['idiom', 'naming', 'architecture', 'ui_structure', 'placement', 'design_alternative']

// 위치 · craft 스키마 — ⛔ ReviewFindingsSchema 를 고치지 않고 **새 객체**로 만든다. CrossReviewSchema.additions ·
//    CounterSchema.missedFindings 가 findings 하위 객체를 참조로 공유해서, 원본을 고치면 새 필드가 전 렌즈로 샌다.
//    위치 스키마는 Stage 1 finding 에 위치·발견 축 선택 필드를 둔다 — peer-review.js 와 같은 discoveryAxis 목록(MergeContract §3 dedup 키).
const LocatedFindingItems = {
  ...ReviewFindingsSchema.properties.findings.items,
  properties: {
    ...ReviewFindingsSchema.properties.findings.items.properties,
    line_range: { type: 'string' },
    discoveryAxis: {
      type: 'string',
      enum: ['code_quality', 'structure', 'correctness', 'runtime_safety', 'direction', 'other'],
      description: '발견 축. code_quality=품질·dead code·성능 / structure=설계·레이어·확장성 / correctness=로직·요구사항·엣지 / runtime_safety=동시성·메모리·크래시 / direction=접근 방향 대안 / other=위 어디에도 안 맞음',
    },
  },
}
const LocatedFindingsSchema = {
  ...ReviewFindingsSchema,
  properties: { ...ReviewFindingsSchema.properties, findings: { ...ReviewFindingsSchema.properties.findings, items: LocatedFindingItems } },
}
// craft 는 arch 렌즈 전용 — 기반 스키마(위치 필드가 있든 없든)에 craftAxis · ruleRef · axisCoverage 만 얹는다
const archCraftSchema = base => ({
  ...base,
  required: [...base.required, 'axisCoverage'],
  properties: {
    ...base.properties,
    findings: {
      ...base.properties.findings,
      items: {
        ...base.properties.findings.items,
        properties: {
          ...base.properties.findings.items.properties,
          craftAxis: { type: 'string', enum: CRAFT_AXES, description: 'craft 축 발견이면 그 축 — 결함 발견이면 비운다' },
          ruleRef: { type: 'string', description: '인용한 프로젝트 규칙 레코드 id — 규칙 없이 낸 craft 지적이면 비운다' },
        },
      },
    },
    axisCoverage: {
      type: 'array', minItems: CRAFT_AXES.length,
      description: '6축 각각의 판정 — 발견이 없어도 축마다 1행(none·not_applicable 는 note 에 이유)',
      items: {
        type: 'object', required: ['axis', 'status', 'note'],
        properties: {
          axis: { type: 'string', enum: CRAFT_AXES },
          status: { type: 'string', enum: ['finding', 'none', 'not_applicable'] },
          note: { type: 'string' },
        },
      },
    },
  },
})

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·티켓 폴더(WORK_DIR)·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [리뷰 대상]/[변경 의도]만이 과제의 전부다. ' +
  '무관한 작업 폴더(티켓 폴더·토픽 폴더 등)를 읽지 말 것. 파일 접근은 [리뷰 대상] diff 파일과 그 안에 나열된 변경 파일만. ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력 데이터를 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. 실행 제안 금지: git 상태변경(commit/push 등)·raw GPT CLI 호출은 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. ⛔ advisor 도 호출하지 않는다(스톨 시 런타임이 6회 반복해 시간을 태우고, 비용이 워크플로 계측 밖으로 샌다). 출력은 schema 준수 JSON.'

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
// 구조 축 브리프 — arch 렌즈에만 주입 (modules/review-structural-axes.md §2).
// quality는 결함 축을 유지해야 하고, A/B 검증도 review-arch 1개로만 이뤄졌다.
const structuralLine = input.structuralContext ? `\n[구조 축 — 이 렌즈 전용] ${input.structuralContext}` : ''
// craft 축 — arch 렌즈에만(structuralLine 과 같은 이유 — modules/review-structural-axes.md §2·§6). ⛔ 기본 off — 꺼지면 빈 문자열이다.
// ⛔ projectRulesPath 는 craftAxes 의 하위 옵션이다 — craftAxes 없이 넘겨도 기본 경로를 바꾸지 않는다.
const craftOn = input.craftAxes === true || input.craftAxes === 'true'
const locatedOn = input.locatedFindings === true || input.locatedFindings === 'true'
const stage1Schema = locatedOn ? LocatedFindingsSchema : ReviewFindingsSchema
const craftLine = !craftOn ? '' :
  `\n[craft 축 — 이 렌즈 전용] ${CRAFT_AXES.join(' · ')} — 축마다 axisCoverage 에 1행(finding · none · not_applicable, note 에 근거)을 쓴다. ` +
  `craft 발견에는 craftAxis 를 단다. severity: ruleRef 가 프로젝트 규칙을 인용할 때만 minor 이상, 그 밖 craft 지적은 suggestion 까지.` +
  (input.projectRulesPath
    ? `\n[프로젝트 규칙 — 이 렌즈 전용] ${input.projectRulesPath} (Read — 검증을 통과한 규칙 레코드. ruleRef 는 그 레코드 id)`
    : `\n[프로젝트 규칙] 없음 — 규칙 인용 지적 금지 — 코드 근거만`)
function craftSummary(findingList, archResult) {
  const rows = archResult && Array.isArray(archResult.axisCoverage) ? archResult.axisCoverage : null
  const seen = new Set((rows || []).map(r => r && r.axis))
  return {
    counts: Object.fromEntries(CRAFT_AXES.map(ax => [ax, findingList.filter(f => f.craftAxis === ax).length])),
    axisCoverage: rows,
    // ⛔ 행 수가 아니라 축으로 센다 — 같은 축을 여섯 번 적어도 스키마 minItems 6 은 통과한다
    missingAxes: CRAFT_AXES.filter(ax => !seen.has(ax)),
  }
}
// 교차 스테이지 필수 필드 재고지 (S17) — ⛔ 기본 off. 켜면 Stage 2 프롬프트에 additions 항목의 required 키를 **스키마에서 읽어** 적는다.
//    키 목록을 여기 박지 않는다 — 스키마가 바뀌면 재고지 문구가 저절로 따라간다. 교차 워커가 additions 에 required 필드를
//    빠뜨려 스키마 재출력이 났다(4/18 run). 효과(so_retries 0)는 R-C 의 S25 가 fz_wf_metrics 로 잰다.
const crossRequiredOn = input.crossRequiredFields === true || input.crossRequiredFields === 'true'
const crossRequiredLine = !crossRequiredOn ? '' :
  `\n[필수 필드 — additions] 새 항목마다 ${CrossReviewSchema.properties.additions.items.required.join(' · ')} 를 모두 채운다(스키마 required — 하나라도 빠지면 출력이 거부돼 다시 쓰게 된다)`

// ════════ Stage 1: 독립 병렬 리뷰 (Round 1 독립성) ════════
phase('Stage 1: arch/quality 독립 리뷰')
const [arch, quality] = await parallel([
  () => callAgent(
    `${OVERRIDE}\n[역할] 아키텍처 리뷰어(review-arch 렌즈) — 설계 결정·레이어 위반·확장성\n${TARGET}${structuralLine}${craftLine}\n` +
    `[목표] 아키텍처 관점 findings (id는 A1, A2...) + 정상 판정 okAreas. 각 finding에 evidence 인용.`,
    { label: 'stage1-arch', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: craftOn ? archCraftSchema(stage1Schema) : stage1Schema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 품질 리뷰어(review-quality 렌즈) — 코드 품질·dead code·성능·일관성\n${TARGET}\n` +
    `[목표] 품질 관점 findings (id는 Q1, Q2...) + 정상 판정 okAreas. 각 finding에 evidence 인용.`,
    { label: 'stage1-quality', agentType: 'fz:review-quality', model: 'opus', effort: 'xhigh', schema: stage1Schema }),
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
      `[목표] 각 finding의 아키텍처 함의로 severity 조정(adjust+newSeverity)/동의(agree)/기각(false_positive — 실측 인용 필수). 놓친 아키텍처 finding은 additions(id A-X)로.${crossRequiredLine}`,
      { label: 'stage2-arch-on-quality', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: CrossReviewSchema }),
    () => callAgent(
      `${OVERRIDE}\n[역할] 품질 리뷰어 — 교차 보충\n${TARGET}\n[상대(아키) findings] ${JSON.stringify(arch.findings)}\n` +
      `[목표] 각 finding의 품질/성능 영향 보충으로 verdict 반환. 놓친 품질 finding은 additions(id Q-X)로.${crossRequiredLine}`,
      { label: 'stage2-quality-on-arch', agentType: 'fz:review-quality', model: 'opus', effort: 'xhigh', schema: CrossReviewSchema }),
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
  { label: 'stage3-counter', agentType: 'fz:review-counter', model: 'opus', effort: 'xhigh', schema: CounterSchema })
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
  suggestion: findings.filter(f => f.finalSeverity === 'suggestion').length,
  fpFlagged: findings.filter(f => f.crossVerdict === 'false_positive' || f.counterVerdict === 'refute').length,
  // 구조 축 주입 여부 — structuralContext는 optional이라 누락 시 에러 없이 꺼진다. 반환값으로 판별 가능하게 남긴다.
  structuralAxes: !!input.structuralContext,
}
if (craftOn) {
  dist.craftAxes = craftSummary(findings, arch)
  log(`craft 축 — ${CRAFT_AXES.map(ax => `${ax} ${dist.craftAxes.counts[ax]}`).join(' / ')} · axisCoverage ${dist.craftAxes.axisCoverage ? dist.craftAxes.axisCoverage.length + '행' : '⛔없음'}${dist.craftAxes.missingAxes.length ? ` · ⛔빠진 축 ${dist.craftAxes.missingAxes.join('·')}` : ''}`)
}
log(`findings ${findings.length}건 — critical ${dist.critical} / major ${dist.major} / minor ${dist.minor} / suggestion ${dist.suggestion} / FP·refute 플래그 ${dist.fpFlagged} / 구조축 ${dist.structuralAxes ? 'ON' : '⛔OFF'} (최종 기각은 Lead)`)

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
