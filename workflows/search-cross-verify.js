// workflows/search-cross-verify.js — fz-search 교차 검증 탐색 (TEAM cross-verify 대체, Wave 1)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + pilot 실측 (discover-adversarial.js)]
//   표준 패턴 3종 적용: OVERRIDE / args 방어 파싱 + fail-fast / agentType fz: prefix.
//   호출(Lead, SKILL.md 절차): Workflow({ scriptPath: '{plugin_root}/workflows/search-cross-verify.js',
//     args: { query, codeContext } })
//   반환: { mode:'workflow', results:[{file,line,symbol,kind,note,sources,confidence}], metrics }
//     또는 { mode:'fallback', reason, metrics } → Lead는 SOLO 검색 경로 수행. wall-clock은 Lead 측정.
//
// [설계 — modules/patterns/cross-verify.md 평탄화]
//   Stage1 독립 병렬: search-symbolic(심볼) + search-pattern(텍스트) — Round 1 독립성 구조 보장.
//   Stage2 교차: 각자 상대 결과를 받아 FP 판정/보완 (cross-verify Round 2 동형).
//   Stage3 병합: opus agent 언어 지시 (동일성 판정 = 해석 작업 — §11/§12 분류).
//   등급 부여: 스크립트 binary 규칙 — ★★★ 양쪽 발견 / ★★ 단독+교차확인 / ★ 단독+교차미확인
//     (cross-verify.md 신뢰도 표의 규칙은 명문 [verified] — 부여 주체는 Lead→스크립트 이관 [design: calibration 확인 대상]).
//   budget 가드: 해당 없음 — 고정 5-call(가변 fan-out 없음). §12 거버넌스 단서 참조.

export const meta = {
  name: 'search-cross-verify',
  description: 'fz-search 교차 검증 탐색 — 심볼/패턴 독립 병렬 → 교차 FP 제거 → 병합 + 신뢰도 등급. 5-call',
}

const FindingsSchema = {
  type: 'object', required: ['findings'],
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'kind', 'file', 'note'],
        properties: {
          id: { type: 'string', description: '탐색자 내 고유 id (예: S1, P3)' },
          kind: { type: 'string', enum: ['definition', 'reference', 'usage', 'config', 'doc'] },
          file: { type: 'string' },
          line: { type: 'number' },
          symbol: { type: 'string' },
          note: { type: 'string', description: '발견 근거 — 실제 Read/Grep 출력 인용' },
        },
      },
    },
  },
}

const CrossSchema = {
  type: 'object', required: ['reviewed', 'additions'],
  properties: {
    reviewed: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'verdict', 'note'],
        properties: {
          id: { type: 'string', description: '상대 탐색자의 finding id' },
          verdict: { type: 'string', enum: ['confirmed', 'false_positive'] },
          note: { type: 'string', description: '판정 근거 — false_positive는 교차 실측 인용 필수' },
        },
      },
    },
    additions: FindingsSchema.properties.findings,
  },
}

const MergeSchema = {
  type: 'object', required: ['merged'],
  properties: {
    merged: {
      type: 'array',
      items: {
        type: 'object', required: ['file', 'kind', 'note', 'sources', 'crossVerified'],
        properties: {
          file: { type: 'string' },
          line: { type: 'number' },
          symbol: { type: 'string' },
          kind: { type: 'string', enum: ['definition', 'reference', 'usage', 'config', 'doc'] },
          note: { type: 'string' },
          sources: { type: 'array', items: { type: 'string', enum: ['symbolic', 'pattern'] }, minItems: 1 },
          crossVerified: { type: 'boolean', description: '교차 단계에서 confirmed 판정을 받았는가' },
        },
      },
    },
  },
}

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·ASD 폴더·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [질의]/[탐색 범위]만이 과제의 전부다. ' +
  '무관한 작업 폴더(ASD-*, 토픽 폴더 등)를 읽지 말 것. 탐색은 [탐색 범위]가 지시한 경로만. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. 출력은 schema 준수 JSON.'

// ── args 방어 파싱 (§12 표준 패턴 2 — scriptPath 호출 시 args는 JSON 문자열 도착) ──
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

// fail-fast (§12 표준 패턴 2)
if (!input || !input.query || !input.codeContext) {
  log(`FATAL args invalid (typeof=${typeof args}) — query/codeContext 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}

// ════════ Stage 1: 독립 병렬 탐색 (Round 1 독립성 — 피어 데이터 미주입) ════════
phase('Stage 1: 심볼/패턴 독립 탐색')
const [sym, pat] = await parallel([
  () => callAgent(
    `${OVERRIDE}\n[역할] 심볼 탐색자(search-symbolic 렌즈) — 정의/참조/타입 관계 중심\n` +
    `[질의] ${input.query}\n[탐색 범위] ${input.codeContext}\n` +
    `[목표] 질의 대상의 정의·참조·사용처를 심볼 관점으로 전수 수집. 각 발견에 근거 인용.`,
    { label: 'stage1-symbolic', agentType: 'fz:search-symbolic', model: 'sonnet', schema: FindingsSchema }),
  () => callAgent(
    `${OVERRIDE}\n[역할] 패턴 탐색자(search-pattern 렌즈) — Grep/Glob 텍스트·파일 패턴 중심\n` +
    `[질의] ${input.query}\n[탐색 범위] ${input.codeContext}\n` +
    `[목표] 질의 대상을 텍스트 패턴으로 전수 수집 (주석/문서/설정 포함). 각 발견에 근거 인용.`,
    { label: 'stage1-pattern', agentType: 'fz:search-pattern', model: 'sonnet', schema: FindingsSchema }),
])
if (!sym && !pat) { fallbackCount += 1; return { mode: 'fallback', reason: 'stage1 both null', metrics: metrics(0) } }
if (!sym || !pat) log('WARN stage1 한쪽 null — 단독 진행 (등급 상한 ★)')

// id 네임스페이스 강제 (리뷰 C-3 동형 교정)
if (sym) sym.findings = sym.findings.map(f => ({ ...f, id: `S:${f.id}` }))
if (pat) pat.findings = pat.findings.map(f => ({ ...f, id: `P:${f.id}` }))

// ════════ Stage 2: 교차 검증 (상대 결과 주입 — FP 제거 + 보완) ════════
phase('Stage 2: 교차 검증')
let crossOnPattern = null // symbolic이 pattern 결과를 심볼 레벨로 검증
let crossOnSymbolic = null // pattern이 symbolic 결과를 텍스트로 보완
if (sym && pat) {
  const crossResults = await parallel([
    () => callAgent(
      `${OVERRIDE}\n[역할] 심볼 탐색자 — 교차 검증\n[상대(패턴) 발견] ${JSON.stringify(pat.findings)}\n` +
      `[목표] 각 발견을 심볼 레벨로 확인 — false_positive 판정은 교차 실측 인용 시만. 패턴이 놓친 심볼 발견은 additions로.`,
      { label: 'stage2-sym-on-pat', agentType: 'fz:search-symbolic', model: 'sonnet', schema: CrossSchema }),
    () => callAgent(
      `${OVERRIDE}\n[역할] 패턴 탐색자 — 교차 보완\n[상대(심볼) 발견] ${JSON.stringify(sym.findings)}\n` +
      `[목표] 각 발견을 텍스트 레벨로 확인 + 추가 사용처(주석/문서/설정) additions로. false_positive는 실측 인용 시만.`,
      { label: 'stage2-pat-on-sym', agentType: 'fz:search-pattern', model: 'sonnet', schema: CrossSchema }),
  ])
  crossOnPattern = crossResults[0]
  crossOnSymbolic = crossResults[1]
  if (!crossOnPattern || !crossOnSymbolic) log('WARN stage2 부분 null — 교차 미확인 항목은 등급 ★')
}

// ════════ Stage 3: 병합 (opus 언어 지시 — 동일성 판정은 해석 작업) ════════
phase('Stage 3: 병합 + 등급')
const merged = await callAgent(
  `${OVERRIDE}\n[역할] 검색 결과 병합자\n` +
  `[심볼 발견] ${JSON.stringify(sym ? sym.findings : [])}\n[패턴 발견] ${JSON.stringify(pat ? pat.findings : [])}\n` +
  `[교차 판정(패턴측에 대한)] ${JSON.stringify(crossOnPattern)}\n[교차 판정(심볼측에 대한)] ${JSON.stringify(crossOnSymbolic)}\n` +
  `[목표] 동일 발견을 병합하고 sources에 출처(symbolic/pattern) 전부 표기. ` +
  `crossVerified는 교차 단계 confirmed 판정 여부. false_positive 판정 항목만 제외(근거 인용 항목 한정) — 그 외 무근거 탈락 금지.`,
  { label: 'stage3-merge', agentType: 'fz:plan-structure', model: 'opus', schema: MergeSchema })
if (!merged) {
  fallbackCount += 1
  const doneStages = (sym && pat) ? ((crossOnPattern && crossOnSymbolic) ? 2 : 1) : 1 // 리뷰 C-2 교정: 하드코딩 제거
  return { mode: 'fallback', reason: 'merge null', metrics: metrics(doneStages) }
}

// 등급 부여 — 스크립트 binary 규칙 (cross-verify.md 명문 규칙, §12 분류)
const results = merged.merged.map((m) => ({
  ...m,
  confidence: m.sources.length === 2 ? '★★★' : (m.crossVerified ? '★★' : '★'),
}))
const dist = { three: results.filter(r => r.confidence === '★★★').length, two: results.filter(r => r.confidence === '★★').length, one: results.filter(r => r.confidence === '★').length }
log(`등급 분포: ★★★ ${dist.three} / ★★ ${dist.two} / ★ ${dist.one}`)

// stagesCompleted = 완전 완주한 stage 수 (리뷰 Q2 동형 교정)
const stagesCompleted = [!!(sym && pat), !!(crossOnPattern && crossOnSymbolic), !!merged].filter(Boolean).length
return {
  mode: 'workflow',
  query: input.query,
  results,
  gradeDistribution: dist,
  metrics: metrics(stagesCompleted), // Lead가 experiment-log §5.7 fz-search 테이블 기록
}
