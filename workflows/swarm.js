// workflows/swarm.js — 공용 읽기 전용 조각 검사(swarm). 서로 독립인 조각 N개를 한 SHA 의 고정 트리에서 조각당 워커 1개로 판정한다
//
// [출처 규칙 — F-501 · pstack(cursor/plugins@4dd1d05) skills/swarm/SKILL.md:23 · :37]
//   "When workers verify or measure commits, each brief names the exact SHAs. A measurement brief also names the method
//    (sample count, what one sample is, order). The worker records both in its result."
//   "Drop a result that does not record the SHAs and method its brief names, and respawn that worker once."
//   ⛔ SHA 는 브리프가 **주는 입력**이고 워커는 그것을 **기록**한다 — 워커가 커밋하거나 git 을 돌리지 않는다.
//      fz 워커에는 Bash · Edit · Write 가 없다(agents/*.md tools). Lead 가 그 SHA 의 고정 트리를 준비하고 워커는 그 아래를 읽기만 한다.
//
// [API 계약 — guides/skill-authoring.md §12 표준 패턴 3종 + 산출물·거버넌스 계약]
//   호출(Lead): 정본 절차는 guides/skill-authoring.md §12 「공용 읽기 전용 swarm」 절 한 곳이다 — 0단계 준비(cp → cmp -s) →
//     고정 트리(git archive <sha> 를 {WORK_DIR} 아래에 푼다) → 복사본 호출. 그 준비 줄은 tests/fixtures/workflow-prep/copy-cmp --cells sites 가 돌린다.
//     Workflow({ scriptPath: '{WORK_DIR}/swarm.js', args: { fragments, tree, maxFragments?, maxAgents?, concurrency?, agentType?, effort? } })
//   ⛔ 순서: 주 Workflow(review-live · peer-review 등)가 반환한 뒤에 부른다 — opus 동시 ≤3 은 세션 전역이고(정본 guides/model-guide.md §5)
//     아래 CONCURRENCY_CAP 은 이 워크플로 안만 막는다. 다른 Workflow 가 도는 동안 부르면 합이 상한을 넘는다.
//   fragments — [{ id, brief, sha, method }] 필수. 네 키 모두 비지 않은 문자열 · id 고유 · sha 는 16진 7~40자 커밋 SHA.
//     tree 하나는 SHA 하나에 고정되므로 전 조각의 sha 가 같아야 한다(SHA 가 여럿이면 트리마다 따로 부른다).
//     method — 측정이면 표본 수 · 표본 1개의 정의 · 순서, 검증이면 무엇을 어떤 순서로 읽는지. 워커가 결과에 기록한다.
//   tree — 그 SHA 에 고정된 읽기 전용 트리의 절대 경로. 필수.
//   maxFragments — 기본 12. 넘는 조각은 돌리지 않고 BLOCKED reason 'budget' 이다(잘린 수를 log 에 적는다).
//   maxAgents — 기본 = 상한 = 2 × min(조각 수, maxFragments)(조각마다 첫 시도 + 재스폰 1). 더 크게 주면 상한으로 깎는다(log).
//   concurrency — 기본 3 · 상한 3(opus 동시 ≤3 — 정본 guides/model-guide.md §5). 더 크게 주면 3 으로 깎는다(log).
//   agentType — 기본 'fz:review-correctness'. 아래 READ_ONLY_AGENTS 밖이면 콜 0 으로 fallback.
//   effort 계약: 전 agent() 호출 model+effort 명시 — effort 값은 args.effort(Lead 세션 effort · 미지정 'xhigh' — modules/mode-gate.md § effort). 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   반환: { mode:'workflow', table:[{ id, status, sha, method, reason?, findings, evidence }], metrics }
//     table — 입력 조각마다 정확히 1행 · 입력 순서 · status ∈ PASS · ISSUES · BLOCKED. 스크립트가 막은 BLOCKED 행은 sha · method 가 null 이다.
//     BLOCKED reason — budget(상한 · 잔여 예산으로 돌리지 않음) · no-sha-method(재스폰 뒤에도 sha/method 미기록) · worker-null(재스폰 뒤에도 null) ·
//       bad-status(재스폰 뒤에도 status 가 셋 밖) · worker-blocked(워커가 sha/method 를 기록하고 BLOCKED 를 냈다 — 고정 트리로 판정 불가)
//     metrics — agentCalls(실제 호출 수) · nullCount(잔존 null — D6, 아래 spawn 주석) · respawns · dropped · blockedBudget · fragmentsCompleted
//     또는 { mode:'fallback', reason, metrics } → Lead 는 실패 복구 사다리(guides/skill-authoring.md §12 L1~L4) — ⛔ 즉시 SOLO 아님.
//       인자 오류는 스폰 전(콜 0)이다. 워커가 하나도 답하지 않으면(전부 null) table 을 함께 싣는다.
//
// [설계]
//   1차 첫 시도 — 돌릴 조각을 concurrency(≤3) 묶음으로 순차 실행한다(묶음 안만 병렬) → 이 워크플로의 동시 opus 는 언제나 ≤3.
//   판정(코드 — 프롬프트 지시가 아니다): 결과의 sha ≠ 브리프 sha(앞뒤 공백 · 대소문자 무시) 이거나 method 가 비면 버리고(dropped)
//     그 조각을 **한 번만** 재스폰한다. null 워커 · status 가 셋 밖인 결과도 한 번. 2차 재스폰도 같은 묶음 규칙이고, 두 번째도 빠지면 BLOCKED 다.
//   budget 가드(코드 — §12 거버넌스 · 선례 discover-adversarial.js runDeep): 1차 · 2차의 **매 묶음 앞**과 묶음 안 **콜마다** 남은 자리를 잰다 —
//     agentCalls >= maxAgents 이거나 budget.total && budget.remaining() < budget.total * BUDGET_RESERVE 이면 스폰을 멈추고
//     끝나지 않은 조각을 전부 BLOCKED 'budget' 으로 둔다. 묶음 크기도 min(concurrency, maxAgents − agentCalls) 라 상한을 넘지 않는다.
//     BUDGET_RESERVE = 0.2 — 잔여 20% 는 swarm 반환 뒤 Lead 통합 몫이다(discover-adversarial --deep 의 20% 하한과 같은 값).
//     budget.total 이 null 이면 remaining() = Infinity 라 maxAgents 상한만 남는다.

export const meta = {
  name: 'swarm',
  description: '공용 읽기 전용 조각 검사 — 조각마다 고정 트리(SHA 1개) 워커 1개 · sha/method 미기록 결과 폐기 후 1회 재스폰 · 동시 opus ≤3 묶음 · 코드 예산 가드 · 조각당 표 1행',
}

const STATUSES = ['PASS', 'ISSUES', 'BLOCKED']

// 워커 결과 — sha · method 는 브리프가 준 값을 **기록**한다(받을지는 아래 judge 코드가 정한다)
const SwarmResultSchema = {
  type: 'object', required: ['status', 'sha', 'method', 'findings', 'evidence'],
  properties: {
    status: { type: 'string', enum: STATUSES, description: 'PASS=브리프의 질문에 문제 없음 · ISSUES=findings 에 근거와 함께 · BLOCKED=고정 트리로 판정할 수 없음(evidence 에 이유)' },
    sha: { type: 'string', description: '브리프가 준 SHA 를 그대로 — 다르거나 비면 결과를 버린다' },
    method: { type: 'string', description: '브리프가 준 method 를 그대로 — 비면 결과를 버린다' },
    findings: {
      type: 'array',
      items: {
        type: 'object', required: ['title', 'detail', 'evidence'],
        properties: {
          severity: { type: 'string', enum: ['critical', 'major', 'minor', 'suggestion'] },
          title: { type: 'string' },
          detail: { type: 'string' },
          file: { type: 'string', description: '고정 트리 기준 상대 경로' },
          evidence: { type: 'string', description: '고정 트리 파일 인용 — 추측 금지' },
        },
      },
    },
    evidence: { type: 'string', description: '판정 근거 — 읽은 고정 트리 경로와 인용' },
  },
}

// 읽기 전용 워커 허용 목록 — 아래 조건을 모두 만족하는 에이전트만 둔다(2026-11-01 대조):
//   ① agents/*.md frontmatter `tools:` 가 비어 있지 않다 — 비면 고정 트리를 못 읽는다(plan-merge 제외)
//   ② `tools:` 에 Edit · Write · MultiEdit · NotebookEdit · Bash · 쓰기 MCP 가 없고 `memory:` 필드도 없다 — memory 필드는
//      Read/Write/Edit 를 자동 부여한다(scripts/lint_contracts.py N13 — memory-curator 제외)
//   ③ 텔레메트리가 swarm 결과를 label 줄기로 가른다 — label 은 `swarm:<조각 id>` 이고 scripts/fz_telemetry_report.py LABEL_STAGE 의
//      `swarm` 이 agentType 판정(AGENT_TYPE_STAGE)보다 먼저 걸린다. 예전 `swarm-<id>` 는 줄기가 조각마다 달라 review-counter 를 주면
//      counter 판정 칸으로 세어졌다(F-531) — 그래서 review-counter 를 뺐던 것을 되돌렸다
//   ④ 리뷰 전용 사전주입이 없다 — review-arch 는 arch-critic 을 미리 싣는 리뷰 렌즈라 빼고 같은 본문의 arch-lens 를 둔다(F-459 · B4).
//      arch-lens 는 v4.50.0 에 생긴 에이전트라, 그 전 판을 불러온 세션은 기본값(review-correctness)으로 부른다
//   ⛔ 에이전트의 tools · memory 를 바꾸거나 에이전트를 더하면 이 목록을 다시 대조한다 — tests/workflows/swarm-budget.js allowlist-readonly 가
//      이 목록 = 실제로 받는 agentType 집합이고 그 전부가 ① · ② 를 지키는지 본다. 목록 밖은 콜 0 으로 fallback 이다.
const READ_ONLY_AGENTS = [
  'fz:impl-correctness', 'fz:impl-quality', 'fz:plan-edge-case', 'fz:plan-impact', 'fz:plan-structure',
  'fz:arch-lens', 'fz:review-correctness', 'fz:review-counter', 'fz:review-direction', 'fz:review-quality',
  'fz:search-pattern', 'fz:search-symbolic',
]
const DEFAULT_AGENT = 'fz:review-correctness'
const DEFAULT_MAX_FRAGMENTS = 12
const CONCURRENCY_CAP = 3        // opus 동시 ≤3 — 정본 guides/model-guide.md §5 (이 워크플로 안만 막는다 · 세션 전역은 Lead 순서 규칙)
const BUDGET_RESERVE = 0.2       // 잔여 예산이 total 의 20% 아래면 스폰을 멈춘다 — Lead 통합 몫(discover-adversarial --deep 과 같은 하한)
const SHA_RE = /^[0-9a-f]{7,40}$/

const OVERRIDE =
  '[Workflow 모드 오버라이드] P2P 통신 없음. SendMessage/피어 회신/Lead 보고 지시는 적용하지 않는다. ' +
  '에이전트 정의의 Phase 절차·티켓 폴더(WORK_DIR)·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [브리프]/[고정 트리]/[기록 의무]만이 과제의 전부다. ' +
  '무관한 작업 폴더(티켓 폴더·토픽 폴더 등)를 읽지 말 것. 파일 접근은 [고정 트리] 경로 아래만 — 읽기 전용이다. ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력 데이터를 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. 실행 제안 금지: git 상태변경(commit/push 등)·raw GPT CLI 호출은 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. ⛔ advisor 도 호출하지 않는다(스톨 시 런타임이 6회 반복해 시간을 태우고, 비용이 워크플로 계측 밖으로 샌다). 출력은 schema 준수 JSON.'

// ── args 방어 파싱 + fail-fast (§12 표준 패턴 2) ──
const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

// ── 콜 집계 — 형제 워크플로와 같은 callAgent 래퍼(호출 수 · null 을 한 곳에서 센다) ──
let agentCalls = 0
let nullCalls = 0
let answered = 0
let fallbackCount = 0
let respawns = 0
let dropped = 0
// ⛔ agent() 가 던져도 null 워커로 센다 — 런타임 parallel 은 그 자리를 null 로 돌려주는데 여기서 세지 않으면
//    아래 spawn 의 D6 취소(nullCalls -= 1)가 세지 않은 null 을 빼서 nullCount 가 음수로 갈 수 있다
async function callAgent(prompt, opts) {
  agentCalls += 1
  let out = null
  try { out = await agent(prompt, opts) } catch (e) { log(`WARN ${opts.label} 실패 — ${e && e.message}`) }
  if (!out) { nullCalls += 1; log(`WARN ${opts.label} null`) } else answered += 1
  return out
}
function metrics(extra) {
  return Object.assign({ agentCalls, nullCount: nullCalls, fallbackCount, respawns, dropped, blockedBudget: 0, fragmentsCompleted: 0 }, extra || {})
}
function argsInvalid(why) {
  log(`FATAL args invalid — ${why}. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: ${why}`, metrics: metrics() }
}
const text = v => typeof v === 'string' && v.trim() !== ''
const normSha = v => String(v).trim().toLowerCase()
function intArg(name, dflt) {
  const v = input[name]
  if (v === undefined) return dflt
  return Number.isInteger(v) && v >= 1 ? v : null
}

if (!input || !Array.isArray(input.fragments) || !input.fragments.length || !text(input.tree)) {
  return argsInvalid(`typeof=${typeof args} — fragments(비지 않은 배열) · tree 필수`)
}
const FRAGS = input.fragments
const badAt = FRAGS.findIndex(f => !f || typeof f !== 'object' || !text(f.id) || !text(f.brief) || !text(f.sha) || !text(f.method))
if (badAt >= 0) return argsInvalid(`fragments[${badAt}] — id · brief · sha · method 는 비지 않은 문자열`)
const shaAt = FRAGS.findIndex(f => !SHA_RE.test(normSha(f.sha)))
if (shaAt >= 0) return argsInvalid(`fragments[${shaAt}].sha=${JSON.stringify(FRAGS[shaAt].sha)} — 16진 7~40자 커밋 SHA 만(브랜치 이름은 고정이 아니다)`)
const ids = FRAGS.map(f => f.id)
const dupAt = ids.findIndex((id, i) => ids.indexOf(id) !== i)
if (dupAt >= 0) return argsInvalid(`fragments id 중복 ${JSON.stringify(ids[dupAt])} — 표는 id 마다 1행이다`)
const SHAS = [...new Set(FRAGS.map(f => normSha(f.sha)))]
if (SHAS.length !== 1) return argsInvalid(`sha ${SHAS.length}종(${SHAS.join(' · ')}) — tree 하나는 SHA 하나에 고정된다. 트리마다 따로 부른다`)
if (!input.tree.startsWith('/')) return argsInvalid(`tree=${JSON.stringify(input.tree)} — 고정 트리의 절대 경로`)
const TREE = input.tree
// effort = Lead 세션 effort(args.effort — modules/mode-gate.md § effort). 미지정이면 'xhigh', 허용값 밖이면 fallback
const EFFORT = input.effort === undefined ? 'xhigh' : input.effort
if (!['low', 'medium', 'high', 'xhigh', 'max'].includes(EFFORT)) return argsInvalid(`effort=${JSON.stringify(input.effort)}: low · medium · high · xhigh · max`)
const AGENT_TYPE = input.agentType === undefined ? DEFAULT_AGENT : input.agentType
if (!READ_ONLY_AGENTS.includes(AGENT_TYPE)) return argsInvalid(`agentType=${JSON.stringify(input.agentType)} — 읽기 전용 fz 에이전트만(READ_ONLY_AGENTS)`)
const MAX_FRAGMENTS = intArg('maxFragments', DEFAULT_MAX_FRAGMENTS)
if (MAX_FRAGMENTS === null) return argsInvalid(`maxFragments=${JSON.stringify(input.maxFragments)} — 1 이상 정수`)
const RUN = FRAGS.slice(0, MAX_FRAGMENTS)
const AGENT_CAP = 2 * RUN.length
const askedAgents = intArg('maxAgents', AGENT_CAP)
if (askedAgents === null) return argsInvalid(`maxAgents=${JSON.stringify(input.maxAgents)} — 1 이상 정수`)
const askedConcurrency = intArg('concurrency', CONCURRENCY_CAP)
if (askedConcurrency === null) return argsInvalid(`concurrency=${JSON.stringify(input.concurrency)} — 1 이상 정수`)
const MAX_AGENTS = Math.min(askedAgents, AGENT_CAP)
const CONCURRENCY = Math.min(askedConcurrency, CONCURRENCY_CAP)
if (askedAgents > AGENT_CAP) log(`WARN maxAgents ${askedAgents} → ${AGENT_CAP} — 상한은 2 × 돌릴 조각 ${RUN.length}(첫 시도 + 재스폰 1)`)
if (askedConcurrency > CONCURRENCY_CAP) log(`WARN concurrency ${askedConcurrency} → ${CONCURRENCY_CAP} — opus 동시 ≤3`)
if (FRAGS.length > RUN.length) log(`WARN 조각 ${FRAGS.length}개 중 ${FRAGS.length - RUN.length}개 미실행 — maxFragments ${MAX_FRAGMENTS} 초과분은 BLOCKED 'budget'`)

// ── 표 — 조각 id 마다 정확히 1행 ──
const rows = new Map()
const blocked = (f, reason) => ({ id: f.id, status: 'BLOCKED', sha: null, method: null, reason, findings: [], evidence: '' })
for (const f of FRAGS.slice(MAX_FRAGMENTS)) rows.set(f.id, blocked(f, 'budget'))

// 판정 — 빈 문자열이면 받는다. 순서: null → sha/method(출처 규칙) → status
function judge(f, out) {
  if (!out || typeof out !== 'object') return 'worker-null'
  if (typeof out.sha !== 'string' || normSha(out.sha) !== normSha(f.sha) || typeof out.method !== 'string' || !out.method.trim()) return 'no-sha-method'
  if (!STATUSES.includes(out.status)) return 'bad-status'
  return ''
}
function accepted(f, out) {
  return {
    id: f.id, status: out.status, sha: f.sha, method: out.method.trim(),
    ...(out.status === 'BLOCKED' ? { reason: 'worker-blocked' } : {}),
    findings: Array.isArray(out.findings) ? out.findings : [],
    evidence: typeof out.evidence === 'string' ? out.evidence : '',
  }
}

const RETRY_NOTE = {
  'worker-null': '앞 워커가 결과 없이 끝났다',
  'no-sha-method': '앞 결과가 브리프의 sha 또는 method 를 기록하지 않아 버렸다',
  'bad-status': '앞 결과의 status 가 PASS · ISSUES · BLOCKED 밖이라 버렸다',
}
function workerPrompt(f, retryWhy) {
  return `${OVERRIDE}\n[역할] swarm 조각 워커 — 고정 트리 읽기 전용 · 조각 1개\n` +
    `[조각] ${f.id}\n[브리프] ${f.brief}\n` +
    `[고정 트리] read only under ${TREE} (pinned at ${f.sha}); method: ${f.method}\n` +
    `[기록 의무] record sha and method in your result — sha 에 ${f.sha} 를, method 에 위 method 를 그대로 적는다. 빠지거나 다르면 결과를 버리고 이 조각을 한 번 다시 띄운다.\n` +
    (retryWhy ? `[재스폰] ${RETRY_NOTE[retryWhy]} — 이번이 마지막 시도다.\n` : '') +
    `[목표] 브리프의 질문을 [고정 트리] 아래 파일만 읽어 판정한다 — PASS(문제 없음) · ISSUES(findings 마다 고정 트리 인용) · BLOCKED(고정 트리로 판정할 수 없음 — evidence 에 이유). 파일을 만들거나 고치지 않는다.`
}

// 남은 자리 — 상한과 잔여 예산을 함께 잰다(§12 거버넌스: budget 가드는 코드다)
function room() {
  if (agentCalls >= MAX_AGENTS) return { n: 0, why: `콜 ${agentCalls} ≥ maxAgents ${MAX_AGENTS}` }
  if (budget.total && budget.remaining() < budget.total * BUDGET_RESERVE) {
    return { n: 0, why: `budget.remaining() ${budget.remaining()} < budget.total ${budget.total} × ${BUDGET_RESERVE}` }
  }
  return { n: Math.min(CONCURRENCY, MAX_AGENTS - agentCalls), why: '' }
}

const DENIED = { denied: true }
// 콜 하나 — 묶음 안에서도 콜마다 다시 잰다(앞 콜이 쓴 자리 · 예산을 본다 · 재스폰 포함). 거부는 DENIED 다(null 워커와 다르다)
// ⛔ nullCount 의미 = **잔존 null**(D6 — workflows/peer-review.js 재시도 래퍼 · tests/workflows/d6-null-count-semantics.js 와 같다).
//   null 이었던 조각을 실제로 다시 띄우기 직전에 첫 시도분을 취소한다 — 재스폰도 null 이면 callAgent 가 다시 +1 해 최종 1 이다.
//   재스폰이 예산으로 거부되면 취소하지 않는다(그 null 은 남는다). agentCalls 는 취소하지 않는다 — 실제 호출 수다.
async function spawn(f, retryWhy) {
  if (!room().n) return DENIED
  if (retryWhy) respawns += 1
  if (retryWhy === 'worker-null') nullCalls -= 1
  return callAgent(workerPrompt(f, retryWhy),
    { label: `swarm:${f.id}`, agentType: AGENT_TYPE, model: 'opus', effort: EFFORT, schema: SwarmResultSchema })
}

// 한 차례(1차 첫 시도 · 2차 재스폰) — 묶음(≤ room().n)마다 병렬로 돌리고 묶음 앞에서 멈출지 잰다.
//   1차는 버린 조각을 돌려주고(2차 입력), 2차는 버린 조각을 BLOCKED 로 닫는다
async function runPass(queue, retry, lastWhy) {
  const again = []
  for (let i = 0; i < queue.length;) {
    const r = room()
    if (!r.n) {
      const left = queue.slice(i)
      for (const f of left) rows.set(f.id, blocked(f, 'budget'))
      log(`WARN 스폰 중단(${retry ? '재스폰' : '첫 시도'}) — ${r.why} · 끝나지 않은 조각 ${left.length}개 BLOCKED 'budget'`)
      return again
    }
    const batch = queue.slice(i, i + r.n)
    i += batch.length
    const outs = await parallel(batch.map(f => () => spawn(f, retry ? lastWhy.get(f.id) : '')))
    let denied = 0
    batch.forEach((f, k) => {
      const out = outs[k]
      if (out === DENIED) { denied += 1; rows.set(f.id, blocked(f, 'budget')); return }
      const why = judge(f, out)
      if (!why) { rows.set(f.id, accepted(f, out)); return }
      if (out) { dropped += 1; log(`WARN swarm:${f.id} 결과 폐기 — ${why}${retry ? ' · 재스폰 뒤라 BLOCKED' : ' → 재스폰 1회'}`) }
      if (retry) rows.set(f.id, blocked(f, why))
      else { lastWhy.set(f.id, why); again.push(f) }
    })
    if (denied) log(`WARN 묶음 안 스폰 거부 ${denied}개 — ${room().why} · BLOCKED 'budget'`)
  }
  return again
}

phase('swarm 1차: 조각 첫 시도')
const lastWhy = new Map()
const again = await runPass(RUN, false, lastWhy)
if (again.length) {
  phase('swarm 2차: 재스폰 1회')
  await runPass(again, true, lastWhy)
}

const table = FRAGS.map(f => rows.get(f.id))
const count = s => table.filter(r => r.status === s).length
const blockedBudget = table.filter(r => r.reason === 'budget').length
const fragmentsCompleted = table.filter(r => r.status !== 'BLOCKED' || r.reason === 'worker-blocked').length
log(`swarm 표 ${table.length}행 — PASS ${count('PASS')} / ISSUES ${count('ISSUES')} / BLOCKED ${count('BLOCKED')}(budget ${blockedBudget}) · 콜 ${agentCalls}/${MAX_AGENTS} · 재스폰 ${respawns} · 폐기 ${dropped} · 잔존 null ${nullCalls}`)
// 워커가 하나도 답하지 않으면 실행 실패다(§12 사다리 입력) — 표는 함께 싣는다(조각당 1행 계약 유지).
// ⛔ nullCount 로 판정하지 않는다 — 잔존 null(D6)은 재스폰이 예산으로 거부된 조각을 빼고 세지 않으므로 '전부 null' 과 같지 않다
const allNull = agentCalls > 0 && answered === 0
if (allNull) {
  fallbackCount += 1
  log('WARN 워커 전부 null — fallback')
}
const runMetrics = metrics({ blockedBudget, fragmentsCompleted, fragments: FRAGS.length, maxFragments: MAX_FRAGMENTS, maxAgents: MAX_AGENTS, concurrency: CONCURRENCY, worker: AGENT_TYPE })
if (allNull) return { mode: 'fallback', reason: 'all workers null', table, metrics: runMetrics }
return {
  mode: 'workflow',
  table,
  metrics: runMetrics,   // 완주 지표 = fragmentsCompleted / fragments (wall-clock 은 Lead 측정 — 스크립트는 시각 API 불가)
}
