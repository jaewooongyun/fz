// workflows/peer-review.js — fz-peer-review Tier 2/3 Analyze 코어 (TEAM 대체, Wave 4)
//
// [API 계약 — verified: guides/skill-authoring.md §12 + review-live.js 동형 선례]
//   표준 패턴 3종 적용. 대형 입력(diff/evidence)은 args가 아닌 파일 경로 전달 (§12).
//   호출(Lead, SKILL.md Analyze Step): Lead가 Gather 산출물(diff/evidence/base-behavior)을 파일로 기록 후
//     Workflow({ scriptPath: '{plugin_root}/workflows/peer-review.js',
//       args: { diffPath, intentContext, reviewSurfacePatchPath?, reviewSurfacePath?, evidencePaths?, basePath?, deep?, structuralContext?, craftAxes?, projectRulesPath?, crossRequiredFields?, crossOutput? } })
//   reviewSurfacePatchPath: gather 가 만든 `review-surface.patch`(중복 커밋 제외분). 있으면 **이것이 1차 리뷰 대상**이 되고
//     `diffPath` 는 부풀림 확인용 보조로 내려간다. ⛔ 렌즈는 Bash·git 이 없어 커밋 해시로 hunk 를 필터할 수 없다 —
//     진단 파일만 넘기면 무력하다(GPT 리뷰 지적, 2026-09-01).
//   reviewSurfacePath: `review-surface.md`(진단 산문). patch 와 함께 넘기면 렌즈가 부풀림 규모를 안다.
//   structuralContext: 구조 축 브리프(modules/review-structural-axes.md §3+§4를 Lead가 Read해 전달).
//     ⛔ arch 렌즈에만 주입된다 — quality/correctness는 결함 축 유지(회귀 방어) + A/B 검증 범위 일치.
//   ⛔ 아래 네 옵션(craftAxes · crossRequiredFields · crossOutput · preserveLowConfidence)은 **기본 on**이다(v4.42.0 — S25p peer-review
//     판정 PASS). 끄는 값(false · crossOutput 'full')을 주면 모든 콜의 프롬프트·스키마가 기준(v4.39.1)과 바이트 단위로 같다 — 롤백 경로.
//     review-live 의 같은 이름 옵션은 기본 off 다(S25 미달). 워크플로별 기본값: tests/workflows/default-off-regression.js 의 defaultOn.
//   craftAxes: craft 6축 판정. 켜지면 arch 렌즈에만 craft 줄과 axisCoverage(6축 필수) 스키마가 들어간다.
//   projectRulesPath: 검증을 통과한 규칙 레코드(JSON — modules/project-rules.md) 경로. craftAxes 가 켜져 있을 때만 효력 · arch 렌즈에만.
//   crossRequiredFields: 켜지면 Stage 2 교차 프롬프트에 additions 항목의 required 키(스키마에서 읽음)를 적는다(tests/workflows/cross-required-fields.js).
//   crossOutput: 'delta'(기본) 면 Stage 2 교차가 동의를 id 로만(reviewedIds) 내고 조정 · 기각 · 신규만 쓴다(S19b). 'full' 이면 옛 전체 응답이다.
//     PURE:cross-delta 가 full 모양으로 펴서 병합은 그대로다. 확인 목록에서 빠진 id 는 unreviewed 로 남고 crossCoverage 로 보고한다
//     (tests/workflows/cross-delta-arm.js).
//   effort 계약: 전 agent() 호출 model+effort(=xhigh) 명시. 특정 콜에서 effort 옵션 거부 회귀 시 그 콜의 effort 키만 제거(모델 유지).
//   deep=false → Tier 2 (Lite): Stage1 3-병렬만 (3-call). Confidence Matrix 미투표 — Lead 단순 병합.
//   deep=true  → Tier 3 (Full): +Stage2 교차(arch↔quality) +Stage3 counter DA (6-call). Lead full Matrix.
//   반환(Tier 3): { mode:'workflow', tier, reviews:[...], issues, crossAdjustments:{archOnPeers,qualityOnPeers},
//                  strengthChallenges, distribution, metrics }  또는 { mode:'fallback', reason, metrics }.
//     ⛔ `counter` 키는 없다 — counter DA 산출은 `strengthChallenges`로 반환된다.
//   Workflow 외부(Lead 책임 유지): Confidence Matrix 계산(독립성 가중=판단) / origin severity 보정 /
//     GPT DA(스크립트 밖 — Lead가 /fz-gpt, cross-provider 스폰 금지 — 마이그레이션 결정) / dedup+투표 / wall-clock.
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
        type: 'object', required: ['id', 'file', 'severity', 'perspective', 'discoveryAxis', 'origin', 'description', 'evidence', 'confidence'],
        properties: {
          id: { type: 'string', description: '리뷰어 내 고유 id (예: A1, Q3, C2)' },
          file: { type: 'string' },
          line_range: { type: 'string' },
          perspective: { type: 'string', description: '렌즈 고유 관점명 (자유 문자열 — owner 식별용)' },
          // 축별 집계 carrier. perspective 는 렌즈마다 표현이 달라 집계가 안 된다(실측: 24건에서 13종).
          // ⛔ perspective 를 이 enum 으로 대체하지 않는다 — 소비 스키마가 9관점 어휘를 쓴다(code-auditor 참조).
          //    두 필드는 목적이 다르다: perspective=무엇을 보는 렌즈인가 / discoveryAxis=어떤 축의 발견인가.
          discoveryAxis: {
            type: 'string',
            enum: ['code_quality', 'structure', 'correctness', 'runtime_safety', 'direction', 'other'],
            description: '발견 축. code_quality=품질·dead code·성능 / structure=설계·레이어·확장성 / correctness=로직·요구사항·엣지 / runtime_safety=동시성·메모리·크래시 / direction=접근 방향 대안 / other=위 어디에도 안 맞음',
          },
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

// 교차 delta 응답 (S19b) — ⛔ 기본 on(crossOutput 미지정 = delta · 'full' 이면 끈다). 동의는 id 만(reviewedIds) 쓰고 조정 · 기각 · 신규만 적는다.
//    additions 는 full 과 같은 스키마를 참조한다. expandCrossDelta(PURE:cross-delta)가 full 모양으로 펴서 병합에 넘긴다.
const CrossDeltaSchema = {
  type: 'object', required: ['reviewedIds', 'adjustments', 'rejections', 'additions'],
  properties: {
    reviewedIds: { type: 'array', items: { type: 'string' }, description: '확인한 상대 id 전부 — 동의는 여기에만 둔다' },
    adjustments: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'newSeverity', 'note'],
        properties: {
          id: { type: 'string' },
          newSeverity: CrossReviewSchema.properties.adjustments.items.properties.newSeverity,
          note: { type: 'string', description: '조정 근거 — 실측 인용 필수' },
        },
      },
    },
    rejections: {
      type: 'array',
      items: {
        type: 'object', required: ['id', 'note'],
        properties: { id: { type: 'string' }, note: { type: 'string', description: 'false_positive 근거 — 실측 인용 필수' } },
      },
    },
    additions: CrossReviewSchema.properties.additions,
  },
}

// craft 6축 — ⛔ tests/fixtures/quality 의 AXES6(SC-4 채점 축)과 같은 목록·순서다. review-live.js · modules/review-structural-axes.md §6
//    과 함께 tests/workflows/craft-axes.js 가 일치를 단언한다. 한 줄 리터럴로 둔다(그 테스트가 이 줄을 추출한다).
const CRAFT_AXES = ['idiom', 'naming', 'architecture', 'ui_structure', 'placement', 'design_alternative']

// arch 전용 craft 스키마 — ⛔ PeerReviewSchema 를 고치지 않고 **새 객체**로 만든다. CrossReviewSchema.additions ·
//    CounterSchema.missedIssues 가 issues 하위 객체를 참조로 공유해서, 원본을 고치면 craft 필드가 전 렌즈로 샌다.
const ArchCraftSchema = {
  ...PeerReviewSchema,
  required: [...PeerReviewSchema.required, 'axisCoverage'],
  properties: {
    ...PeerReviewSchema.properties,
    issues: {
      ...PeerReviewSchema.properties.issues,
      items: {
        ...PeerReviewSchema.properties.issues.items,
        properties: {
          ...PeerReviewSchema.properties.issues.items.properties,
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
  '에이전트 정의의 Phase 절차·티켓 폴더(WORK_DIR)·이전 세션·메모리 컨텍스트 로딩도 적용하지 않는다 — ' +
  '이 프롬프트의 [리뷰 대상]/[변경 의도]/[증거]만이 과제의 전부다. ' +
  '무관한 작업 폴더(티켓 폴더·토픽 폴더 등)를 읽지 말 것. 파일 접근은 이 프롬프트가 나열한 경로만. ' +
  '원본 동작이 필요하면 [증거]의 base 경로를 Read (Lead가 prefetch함 — SendMessage로 요청하지 말 것). ' +
  '보고하는 모든 주장은 이 세션의 도구 결과 또는 프롬프트가 제공한 입력을 근거로 지목할 수 있어야 한다. [verified:] 태그는 해당 출력/입력을 확인한 경우에만. 외부 모델 판정 인용 시 원문 그대로 + [외부: name] 태그 — 재포장·재수치화 금지. 실행 제안 금지: git 상태변경(commit/push 등)·raw GPT CLI 호출은 직접 명령으로 제안하지 말고 사용자/스킬 경유로만 안내한다. ' +
  'Convention(3+ 모듈 동일)을 위반으로 판정하지 않는다(suggestion까지). confidence 80 미만은 보고하지 않는다. ' +
  'issue 마다 discoveryAxis 를 판정한다 — 네 렌즈 이름이 아니라 발견의 성격으로 고른다. 품질·dead code·성능=code_quality / 설계·레이어·확장성=structure / 로직·요구사항·엣지=correctness / 동시성·메모리·크래시 위험=runtime_safety / 접근 방향 자체의 대안=direction. ⛔ 억지로 맞추지 말 것 — 어디에도 안 맞으면 other 다. 한 issue 가 여러 축에 걸치면 결함의 1차 원인 쪽을 고른다. ' +
  '최종 텍스트가 반환값. 멀티턴 없음 — 1-shot raw data. ⛔ advisor 도 호출하지 않는다(스톨 시 런타임이 6회 반복해 시간을 태우고, 비용이 워크플로 계측 밖으로 샌다). 출력은 schema 준수 JSON.'

// ── args 방어 파싱 + fail-fast (§12 표준 패턴 2) ──
const input = (() => {
  if (args && typeof args === 'object') return args
  if (typeof args === 'string') { try { return JSON.parse(args) } catch (e) { return null } }
  return null
})()

// >>> PURE:null-count — 아래 블록은 `tests/workflows/d6-null-count-semantics.js` 가 런타임 추출한다.
//     외부 의존은 주입 가능한 agent·log·parallel 셋뿐이다. 마커를 지우면 그 테스트가 죽는다.
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
//
// ⛔ nullCount 의미 = **잔존 null** (재시도 후에도 남은 것). 시도 횟수가 아니다.
//   재시도 직전에 첫 시도분을 취소한다 — 취소하지 않으면 회복해도 카운터가 남아
//   사전등록 임계 `nullCount 0`(experiment-log.md §5.7)을 정상 복구가 위반한다.
//   재시도도 실패하면 callAgent 가 다시 +1 하므로 최종값은 1 (이중 계상 없음).
//   ⛔ agentCalls 는 취소하지 않는다 — 그쪽은 실제 호출 수다.
async function parallelWithRetry(thunks) {
  const out = await parallel(thunks)
  for (let i = 0; i < out.length; i += 1) {
    if (!out[i]) {
      log(`병렬 ${i}번 null — 순차 재시도 1회 (rate-limit/스폰 실패 폴백)`)
      nullCalls -= 1  // 첫 시도분 취소 — 재시도 결과가 최종 상태를 정한다
      out[i] = (await parallel([thunks[i]]))[0]
      if (out[i]) log(`병렬 ${i}번 재시도 성공 — 잔존 null 아님`)
    }
  }
  return out
}
// <<< PURE:null-count

// ── Stage 2 트리거 (D1 조건부 실행) ─────────────────────────────────────
// ⛔ 스키마를 늘리지 않는다. 렌즈는 자기 관점만 보므로 "전체 verdict" 를 요구하는 것은
//    역할과 맞지 않는다. 이미 있는 severity + 위치로 **이견을 계산**한다.
//
// 발화 조건 (둘 중 하나):
//   (a) 같은 자리를 본 서로 다른 렌즈가 severity 를 다르게 매겼다  → 조정할 것이 있다
//   (b) 한 렌즈만 critical/major 를 냈다                          → 확증도 반증도 없다
//
// ⛔ 임계 1 은 **사전등록 값**이다. 표본 1건에서 역산했고(불일치 3쌍·단독 major 2건),
//    발화율은 반환 `stage2Ran` 으로 관측한다. 잦으면 올리고, 놓치면 내린다.
//    ⛔ 놓치는 쪽이 더 비싸다 — 교차가 필요한데 안 하면 품질이 조용히 깎인다.
// >>> PURE:stage2-trigger — ⛔ 이 마커 사이는 **순수 함수**다(런타임 의존 없음).
//     tests/workflows/s2-stage2-trigger.js 가 이 블록을 **추출해 실행**한다 —
//     복사본을 두면 원본이 바뀔 때 테스트가 과거를 검증한다. 마커를 지우지 말 것.
const SEVERITY_RANK = { critical: 3, major: 2, minor: 1, suggestion: 0 }

// ⛔ 범위를 min-max 로 뭉치지 않는다. `41, 293-295` 를 41–295 로 만들면
//    사이의 무관한 finding 이 전부 "같은 자리"가 되어 교차 조정이 오발화한다.
//    (진단에서 같은 방식이 과대 병합을 낳는 것을 이미 관측했다.)
//    구간 **목록**으로 파싱하고 하나라도 겹치면 같은 자리로 본다.
function lineSpans(range) {
  const text = String(range || '')
  if (!text.trim()) return []
  const spans = []
  for (const part of text.split(/[,;]/)) {
    const nums = part.match(/\d+/g)
    if (!nums) continue
    const ints = nums.map(Number)
    spans.push([Math.min(...ints), Math.max(...ints)])
  }
  return spans
}

function spansOverlap(a, b) {
  for (const x of a) for (const y of b) if (x[0] <= y[1] && y[0] <= x[1]) return true
  return false
}

// ⛔ `line_range` 는 스키마상 **optional** 이다(required 에 없음). 위치를 모르는 finding 을
//    "짝 없음"으로 처리하면 major 하나가 무조건 Stage 2 를 발화시켜 opus 2콜을 부른다.
//    위치 미상은 **판단 불가**이지 단독이 아니다 — 아래 sameSite 는 false 를 주되
//    unpairedMajor 집계에서는 별도로 제외한다.
function hasLocation(x) {
  return !!x.file && lineSpans(x.line_range).length > 0
}

// ⛔ `sameAxis` 는 **severityConflicts 에만** 쓴다. `MergeContract § 3` 이 dedup 키를
//    `파일 + line_range 겹침 + discoveryAxis` 로 규정하고 **"축이 다르면 같은 자리라도 별건"** 이라
//    못박는데, 트리거가 축을 안 보면 같은 세션의 두 규칙이 모순이 된다.
//    실측(PR): severityConflicts 7건 중 **5건(71%)이 축이 다른 별건**이었다 —
//    세 렌즈가 신규 파일 **헤더 라인(23-27)** 에 서로 다른 주제를 앵커해 위치만 겹쳤다.
// ⚠️ 축이 **없으면** 비교를 건너뛴다(= 현행 동작). fail-close 하면 "덜 발화" 쪽이고,
//    아래 임계 주석대로 놓치는 쪽이 더 비싸다. 스키마상 required 지만 방어적으로 둔다.
// ⛔ `unpairedMajor` 에는 쓰지 않는다 — 단독 major 는 축과 무관하게 교차가 필요하다.
function sameAxis(x, y) {
  if (!x.discoveryAxis || !y.discoveryAxis) return true
  return x.discoveryAxis === y.discoveryAxis
}

function sameSite(x, y) {
  if (!hasLocation(x) || !hasLocation(y) || x.file !== y.file) return false
  return spansOverlap(lineSpans(x.line_range), lineSpans(y.line_range))
}

function stage2Trigger(reviewList) {
  const flat = []
  for (const r of reviewList) for (const i of r.issues) flat.push({ agent: r.agent, i })

  let severityConflicts = 0
  for (let a = 0; a < flat.length; a += 1) {
    for (let b = a + 1; b < flat.length; b += 1) {
      if (flat[a].agent === flat[b].agent) continue
      if (!sameSite(flat[a].i, flat[b].i)) continue
      if (!sameAxis(flat[a].i, flat[b].i)) continue   // 축이 다르면 별건 — MergeContract § 3
      if (flat[a].i.severity !== flat[b].i.severity) severityConflicts += 1
    }
  }

  let unpairedMajor = 0
  let unlocatedMajor = 0
  for (let a = 0; a < flat.length; a += 1) {
    if ((SEVERITY_RANK[flat[a].i.severity] || 0) < 2) continue
    if (!hasLocation(flat[a].i)) { unlocatedMajor += 1; continue }   // 판단 불가 — 발화시키지 않는다
    const paired = flat.some((o, b) => b !== a && o.agent !== flat[a].agent && sameSite(flat[a].i, o.i))
    if (!paired) unpairedMajor += 1
  }

  return {
    fire: severityConflicts >= 1 || unpairedMajor >= 1,
    severityConflicts,   // ⛔ 같은 자리 **+ 같은 축** 만 센다 (교차축 공존은 별건)
    unpairedMajor,       //    축 무관 — 단독 major 는 축과 상관없이 교차 대상
    unlocatedMajor,   // 위치 미상이라 판정에서 뺀 수 — 0 이 아니면 리포트에 남긴다
  }
}
// <<< PURE:stage2-trigger

// >>> PURE:cross-merge — ⛔ 이 마커 사이도 **순수 함수**다.
//     tests/workflows/s2-cross-merge.js 가 이 블록을 추출해 실행한다. 마커를 지우지 말 것.
//     ⚠️ severity 순위표를 위 블록과 공유하지 않고 다시 적는다 — 블록마다 **독립 추출**이
//        가능해야 하고, 위 블록을 참조하면 이 블록만 떼어냈을 때 죽는다.
const CROSS_SEVERITY_RANK = { critical: 3, major: 2, minor: 1, suggestion: 0 }

// ⛔ 한 finding 이 **두 렌즈에게** 판정받을 수 있다: correctness issue 는 arch·quality
//    양쪽 교차 입력에 들어간다(발화 원인이 검증을 받게 하려고). id 로 덮어쓰면
//    **뒤에 온 렌즈가 앞의 판정을 조용히 지운다** — concat 순서가 판정을 정하게 된다.
//    (correctness 를 넣기 전에는 두 렌즈가 서로 다른 id 만 봐서 충돌이 없었다.)
function crossIndex(sources) {
  const byId = {}
  for (const src of sources) {
    if (!src || !src.result) continue
    for (const a of src.result.adjustments) {
      if (!byId[a.id]) byId[a.id] = []
      byId[a.id].push({ by: src.by, verdict: a.verdict, newSeverity: a.newSeverity, note: a.note })
    }
  }
  return byId
}

// ⛔ 갈리면 **고르지 않는다.** Tier 2 는 투표하지 않으므로(modules/peer-review-gates.md § MergeContract § 9)
//    여기서 승자를 정하면 계약 밖에서 투표하는 셈이다 — `contested` 로 표시해 Lead 에 넘긴다.
function crossFields(entries) {
  if (!entries || entries.length === 0) return { crossVerdict: 'unreviewed' }
  if (entries.length === 1) {
    const e = entries[0]
    return {
      crossVerdict: e.verdict,
      crossNote: e.note,
      crossSeverity: e.verdict === 'adjust' && e.newSeverity ? e.newSeverity : undefined,
    }
  }
  const verdicts = entries.map(e => e.verdict)
  const note = entries.map(e => `[${e.by}] ${e.verdict}${e.note ? ': ' + e.note : ''}`).join(' / ')
  if (verdicts.every(v => v === verdicts[0])) {
    // 판정이 같으면 제안 severity 중 **더 심한 쪽**을 싣는다. 낮은 쪽을 고르면
    // 두 렌즈가 동의했는데 결과가 완화되는 모순이 생긴다.
    const sev = entries.map(e => e.newSeverity).filter(Boolean)
      .sort((a, b) => (CROSS_SEVERITY_RANK[b] || 0) - (CROSS_SEVERITY_RANK[a] || 0))[0]
    return {
      crossVerdict: verdicts[0],
      crossNote: note,
      crossSeverity: verdicts[0] === 'adjust' && sev ? sev : undefined,
    }
  }
  return {
    crossVerdict: 'contested',
    crossNote: note,
    // ⛔ 원본 판정을 버리지 않는다. Lead 가 무엇과 무엇이 갈렸는지 봐야 판정할 수 있다.
    crossVerdicts: entries,
  }
}
// <<< PURE:cross-merge

// >>> PURE:cross-delta — ⛔ 이 마커 사이는 **순수 함수**다. peer-review.js 와 review-live.js 에 **같은 글자로** 있다 —
//     tests/workflows/cross-delta-arm.js 가 추출해 실행하고 두 사본이 같은지 단언한다. 한쪽만 고치지 말 것.
//     delta 응답(동의는 reviewedIds 에만 둔다)을 기존 병합이 읽는 full 모양 { adjustments, additions } 로 편다 — 병합 코드는 그대로다.
//     ⛔ 확인 목록(expectedIds)에 있는데 reviewedIds · adjustments · rejections 어디에도 없는 id 를 agree 로 채우지 않는다 —
//        full 모드에서 판정이 빠진 id 와 같이 unreviewed 로 남고 missing 으로 보고된다(전수 확인 보존).
//     ⛔ agree 에는 note 가 없다 — 출력을 줄이는 몫이 이것이다. 판정 필드와 adjust · false_positive 의 note 는 full 과 같다.
function expandCrossDelta(delta, expectedIds) {
  if (!delta) return { result: null, missing: null }
  const list = k => (Array.isArray(delta[k]) ? delta[k] : [])
  const judged = new Set(list('adjustments').concat(list('rejections')).map(e => e.id))
  const agreed = [...new Set(list('reviewedIds'))].filter(id => !judged.has(id))
  const reviewed = new Set(agreed.concat([...judged]))
  return {
    result: {
      adjustments: agreed.map(id => ({ id, verdict: 'agree' }))
        .concat(list('adjustments').map(a => ({ id: a.id, verdict: 'adjust', newSeverity: a.newSeverity, note: a.note })))
        .concat(list('rejections').map(r => ({ id: r.id, verdict: 'false_positive', note: r.note }))),
      additions: list('additions'),
    },
    missing: (expectedIds || []).filter(id => !reviewed.has(id)),
  }
}
// <<< PURE:cross-delta

  // ⛔ 내용 게이트는 **의도적으로 없다** (2026-08-25 사용자 결정). C3 InputHygiene 는
  //    문서 규율(`SKILL.md § Orchestrator Bias 방지 규칙`)로만 지킨다 — 대상이 자연어라
  //    패턴 검사는 오탐이 나면 경고가 노이즈가 되고, 구조화 필드는 소비처 전부를 바꾼다.
  //    ⚠️ 잔여 위험: Lead 가설이 판정 근거로 되돌아오는 에코 챔버는 재현 가능하다.
  //    재발 관측 시 `intentContext` 구조화(title·body·acceptance·replaces)를 재검토한다.
if (!input || !input.diffPath || !input.intentContext) {
  log(`FATAL args invalid (typeof=${typeof args}) — diffPath/intentContext 필수. fallback`)
  fallbackCount += 1
  return { mode: 'fallback', reason: `args invalid: typeof=${typeof args}`, metrics: metrics(0) }
}

const deep = input.deep === true || input.deep === 'true'  // Tier 3 = full (교차+counter)
const evidenceLine = input.evidencePaths ? `\n[증거] ${input.evidencePaths}` : ''
const baseLine = input.basePath ? `\n[증거] base 원본(prefetch): ${input.basePath} (Read로 로드)` : ''
// 리뷰 범위 — ⛔ **판정이 아니라 필터된 patch 를 넘긴다.**
// base 가 분기점보다 앞서면 이미 머지된 커밋이 diff 에 다시 나타난다(실측 2.9배).
// ⛔ `review-surface.md`(진단)만 넘기면 무력하다 — 렌즈는 Bash·git 이 없어(아래 OVERRIDE)
//   커밋 해시로 hunk 를 필터할 수 없고, 그 파일의 조언("git show <+ 커밋>")도 실행 불가다.
//   그래서 gather 가 만든 `review-surface.patch`(중복 커밋 제외분)를 **1차 리뷰 대상**으로 쓴다.
// ⛔ diff.patch 를 버리지 않는다 — 부풀림 판정 자체가 정보이므로 보조로 병기한다.
const surfacePatch = input.reviewSurfacePatchPath
const primaryDiff = surfacePatch || input.diffPath
const surfaceLine = surfacePatch
  ? `\n[⛔ 리뷰 대상은 위 patch 다] 중복 커밋을 제외한 리뷰 표면이다. 전량 diff: ${input.diffPath} (부풀림 확인용 — 여기서 나온 발견은 이미 머지된 변경일 수 있다)`
    + (input.reviewSurfacePath ? `\n[리뷰 범위 진단] ${input.reviewSurfacePath}` : '')
  : input.reviewSurfacePath
    ? `\n[리뷰 범위 진단] ${input.reviewSurfacePath} (Read로 로드 — 중복 커밋 판정)`
      + '\n⚠️ 필터된 patch 가 없다 — 진단은 있으나 diff 는 전량이다. 이미 머지된 변경이 섞일 수 있다.'
    : '\n[리뷰 범위] ⚠️ 미제공 — diff 전체를 리뷰 대상으로 가정한다. base 가 stale 하면 이미 머지된 변경이 섞인다.'
const TARGET = `[리뷰 대상] diff 파일: ${primaryDiff} (Read로 로드)\n[변경 의도] ${input.intentContext}${surfaceLine}${evidenceLine}${baseLine}`
// 구조 축 브리프 — arch 렌즈에만 주입 (modules/review-structural-axes.md §2).
// quality/correctness는 결함 축을 유지해야 하고, A/B 검증도 review-arch 1개로만 이뤄졌다.
const structuralLine = input.structuralContext ? `\n[구조 축 — 이 렌즈 전용] ${input.structuralContext}` : ''
// craft 축 — arch 렌즈에만(structuralLine 과 같은 이유 — modules/review-structural-axes.md §2·§6). ⛔ 기본 on — false 로 끄면 빈 문자열이다.
// ⛔ projectRulesPath 는 craftAxes 의 하위 옵션이다 — craftAxes:false 와 함께 넘겨도 경로를 바꾸지 않는다.
const craftOn = !(input.craftAxes === false || input.craftAxes === 'false')
const craftLine = !craftOn ? '' :
  `\n[craft 축 — 이 렌즈 전용] ${CRAFT_AXES.join(' · ')} — 축마다 axisCoverage 에 1행(finding · none · not_applicable, note 에 근거)을 쓴다. ` +
  `craft 발견에는 craftAxis 를 단다. severity: ruleRef 가 프로젝트 규칙을 인용할 때만 minor 이상, 그 밖 craft 지적은 suggestion 까지.` +
  (input.projectRulesPath
    ? `\n[프로젝트 규칙 — 이 렌즈 전용] ${input.projectRulesPath} (Read — 검증을 통과한 규칙 레코드. ruleRef 는 그 레코드 id)`
    : `\n[프로젝트 규칙] 없음 — 규칙 인용 지적 금지 — 코드 근거만`)
function craftSummary(issueList, archResult) {
  const rows = archResult && Array.isArray(archResult.axisCoverage) ? archResult.axisCoverage : null
  const seen = new Set((rows || []).map(r => r && r.axis))
  return {
    counts: Object.fromEntries(CRAFT_AXES.map(ax => [ax, issueList.filter(f => f.craftAxis === ax).length])),
    axisCoverage: rows,
    // ⛔ 행 수가 아니라 축으로 센다 — 같은 축을 여섯 번 적어도 스키마 minItems 6 은 통과한다
    missingAxes: CRAFT_AXES.filter(ax => !seen.has(ax)),
  }
}
// 교차 스테이지 필수 필드 재고지 (S17) — ⛔ 기본 on(false 로 끈다). 켜면 Stage 2 프롬프트에 additions 항목의 required 키를 **스키마에서 읽어** 적는다.
//    키 목록을 여기 박지 않는다 — 스키마가 바뀌면 재고지 문구가 저절로 따라간다. 교차 워커가 additions 에 required 필드를
//    빠뜨려 스키마 재출력이 났다(4/18 run).
const crossRequiredOn = !(input.crossRequiredFields === false || input.crossRequiredFields === 'false')
const crossRequiredLine = !crossRequiredOn ? '' :
  `\n[필수 필드 — additions] 새 항목마다 ${CrossReviewSchema.properties.additions.items.required.join(' · ')} 를 모두 채운다(스키마 required — 하나라도 빠지면 출력이 거부돼 다시 쓰게 된다)`
// 교차 delta 응답 (S19b) — ⛔ 기본 on('full' 이면 끈다). 켜면 교차 스키마를 CrossDeltaSchema 로 바꾸고 응답 모양을 한 줄로 알린다.
const crossDeltaOn = input.crossOutput !== 'full'
const crossSchema = crossDeltaOn ? CrossDeltaSchema : CrossReviewSchema
const crossDeltaLine = !crossDeltaOn ? '' :
  `\n[응답 모양 — delta] 위 목록에서 확인한 id 를 전부 reviewedIds 에 적는다. 동의는 reviewedIds 에만 두고 따로 쓰지 않는다. ` +
  `조정은 adjustments(id · newSeverity · note), 기각(false_positive)은 rejections(id · note — 실측 인용 필수)에 쓴다. 동의한 항목을 다시 서술하지 않는다.`
// 발견 단계 후보 보존 (S16b) — ⛔ 기본 on(false 로 끈다). 켜면 OVERRIDE 의 조기 필터 문장과 이슈 스키마의 confidence 설명을 **사본에서만** 바꾼다.
//    원본 상수는 그대로라 꺼지면 여섯 콜 모두 기준과 바이트 단위로 같다. 스키마 쪽 문구는 스키마에서 읽는다(두 번 박지 않는다).
//    그 설명은 참조로 네 스키마(Stage 1 · ArchCraft · 교차 additions · counter missedIssues)에 퍼져 있어 콜마다 사본을 만든다.
//    낮은 확신도 후보의 게시 여부는 병합이 정한다 — scripts/review_merge.py (MergeContract §10 게시 등급).
const lowConfOn = !(input.preserveLowConfidence === false || input.preserveLowConfidence === 'false')
const EARLY_FILTER_DESC = PeerReviewSchema.properties.issues.items.properties.confidence.description
const LENS_OVERRIDE = !lowConfOn ? OVERRIDE : OVERRIDE.replace('confidence 80 미만은 보고하지 않는다. ',
  '[후보 보존] confidence 는 0-100 값으로 달되 낮다고 빼지 않는다 — 게시 여부는 병합이 정한다. ')
const lensSchema = schema => !lowConfOn ? schema :
  JSON.parse(JSON.stringify(schema).split(EARLY_FILTER_DESC).join('0-100 — 낮아도 보고한다(게시 등급은 병합이 정한다)'))

// ════════ Stage 1: 독립 병렬 리뷰 (3-Model — Round 1 독립성) ════════
phase('Stage 1: arch/quality/correctness 독립 리뷰')
const [arch, quality, correctness] = await parallelWithRetry([
  () => callAgent(
    `${LENS_OVERRIDE}\n[역할] 아키텍처 리뷰어(review-arch 렌즈) — 설계 결정·레이어 위반·확장성\n${TARGET}${structuralLine}${craftLine}\n` +
    `[목표] 아키텍처 관점 issues (id는 A1, A2...) + strengths(max3) + overall_assessment. 각 issue에 evidence 인용 + origin.`,
    { label: 'stage1-arch', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: lensSchema(craftOn ? ArchCraftSchema : PeerReviewSchema) }),
  () => callAgent(
    `${LENS_OVERRIDE}\n[역할] 품질 리뷰어(review-quality 렌즈) — 코드 품질·dead code·성능·일관성\n${TARGET}\n` +
    `[목표] 품질 관점 issues (id는 Q1, Q2...) + strengths(max3) + overall_assessment. 각 issue에 evidence 인용 + origin.`,
    { label: 'stage1-quality', agentType: 'fz:review-quality', model: 'opus', effort: 'xhigh', schema: lensSchema(PeerReviewSchema) }),
  () => callAgent(
    `${LENS_OVERRIDE}\n[역할] 정확성 리뷰어(review-correctness 렌즈) — 요구사항 충족·로직 정확성·엣지 케이스\n${TARGET}\n` +
    `[목표] 정확성 관점 issues (id는 C1, C2...) + strengths(max3) + overall_assessment. 각 issue에 evidence 인용 + origin. ` +
    `함수 제거/책임 이전 감지 시 base 원본(prefetch)과 대조 — 원본 책임이 어디로 이전됐는지 추적.`,
    { label: 'stage1-correctness', agentType: 'fz:review-correctness', model: 'opus', effort: 'xhigh', schema: lensSchema(PeerReviewSchema) }),
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

// ── Stage 2 실행 여부 (D1) ──
// ⛔ `if (!deep)` 조기 반환은 Stage 2 **와 Stage 3 둘 다** 막고 있었다. 조건부로 바꾸되
//    !deep 이 Stage 3 까지 내려가면 Tier 2 가 tier:3 을 반환한다 — 아래에서 명시적으로 끊는다.
const trigger = stage2Trigger(reviews)
const shouldRunStage2 = deep || trigger.fire

if (!deep && !trigger.fire) {
  const allIssues = reviews.flatMap(r => r.issues)
  log(`Tier2(Lite) — reviews ${reviews.length}, issues ${allIssues.length}. 트리거 미발화(불일치 ${trigger.severityConflicts}·단독major ${trigger.unpairedMajor}) → Stage2 생략. Matrix 미투표(Lead 병합).`)
  return {
    mode: 'workflow', tier: 2, reviews, issues: allIssues,
    stage2Ran: false, stage2Trigger: trigger,
    ...(craftOn ? { craftAxes: craftSummary(allIssues, arch) } : {}),
    metrics: metrics(reviews.length === 3 ? 1 : 0),
  }
}
if (!deep) log(`Tier2 — 트리거 발화(불일치 ${trigger.severityConflicts}·단독major ${trigger.unpairedMajor}) → Stage2 실행`)

// ════════ Stage 2: 교차 조정 ════════
// ⛔ correctness 는 교차 **입력**에 포함된다(리뷰어로는 불참 — 6-call 고정).
//    트리거는 correctness 를 포함해 계산하므로, 빼면 **발화 원인이 검증을 못 받는다** —
//    correctness 의 단독 major 가 opus 2콜을 유발하고도 `crossVerdict: unreviewed` 로 남았다.
//    Tier 2 는 counter 이전에 반환하므로 Stage 3 도 그 자리를 메우지 못한다.
//    입력만 늘리므로 call 수는 그대로다.
phase('Stage 2: 교차 severity 조정 (arch·quality 가 서로 + correctness 를 본다)')
let archOnPeers = null
let qualityOnPeers = null
let crossCoverage = null   // crossOutput='delta' 일 때만 — 렌즈별 reviewedIds 누락 id(null = 렌즈 결손)
if (shouldRunStage2 && arch && quality) {
  const correctnessIssues = correctness ? correctness.issues : []
  const peersOf = (own) => [].concat(own === 'arch' ? quality.issues : arch.issues, correctnessIssues)
  const peerFor = (own) => JSON.stringify(peersOf(own))
  const cnote = correctnessIssues.length
    ? `\n⛔ 위 목록에는 정확성 렌즈(id \`C:\`) issue 가 포함돼 있다 — 그것도 같은 기준으로 판정한다.`
    : ''
  const cross = await parallel([
    () => callAgent(
      `${LENS_OVERRIDE}\n[역할] 아키텍처 리뷰어 — 교차 조정\n${TARGET}\n[상대 issues] ${peerFor('arch')}${cnote}\n` +
      `[목표] 각 issue의 아키텍처 함의로 severity 조정(adjust+newSeverity)/동의(agree)/기각(false_positive — 실측 인용 필수). 놓친 아키텍처 issue는 additions(id A-X)로.${crossRequiredLine}${crossDeltaLine}`,
      { label: 'stage2-arch-on-peers', agentType: 'fz:review-arch', model: 'opus', effort: 'xhigh', schema: lensSchema(crossSchema) }),
    () => callAgent(
      `${LENS_OVERRIDE}\n[역할] 품질 리뷰어 — 교차 보충\n${TARGET}\n[상대 issues] ${peerFor('quality')}${cnote}\n` +
      `[목표] 각 issue의 품질/성능 영향 보충으로 verdict 반환. 놓친 품질 issue는 additions(id Q-X)로.${crossRequiredLine}${crossDeltaLine}`,
      { label: 'stage2-quality-on-peers', agentType: 'fz:review-quality', model: 'opus', effort: 'xhigh', schema: lensSchema(crossSchema) }),
  ])
  archOnPeers = cross[0]
  qualityOnPeers = cross[1]
  if (crossDeltaOn) {
    const a = expandCrossDelta(archOnPeers, peersOf('arch').map(f => f.id))
    const q = expandCrossDelta(qualityOnPeers, peersOf('quality').map(f => f.id))
    archOnPeers = a.result
    qualityOnPeers = q.result
    crossCoverage = { arch: a.missing, quality: q.missing }
    const lost = [a.missing, q.missing].filter(Boolean).reduce((n, m) => n + m.length, 0)
    if (lost) log(`WARN 교차 delta — reviewedIds 에 없는 상대 id ${lost}건 (unreviewed 로 남긴다)`)
  }
  if (archOnPeers) archOnPeers.additions = archOnPeers.additions.map(f => ({ ...f, id: `XA:${f.id}` }))
  if (qualityOnPeers) qualityOnPeers.additions = qualityOnPeers.additions.map(f => ({ ...f, id: `XQ:${f.id}` }))
  if (!archOnPeers || !qualityOnPeers) log('WARN stage2 부분 null — 해당 측 조정 미반영')
}

// ⛔ Tier 2 는 여기서 끝난다. Stage 3(counter DA)은 --deep 전용이다.
//    이 반환이 없으면 트리거 발화한 Tier 2 가 Stage 3 까지 내려가 tier:3 을 반환한다.
if (!deep) {
  const crossByIdT2 = crossIndex([
    { by: 'arch', result: archOnPeers }, { by: 'quality', result: qualityOnPeers },
  ])
  const adjustments = []
    .concat(archOnPeers ? archOnPeers.adjustments : [], qualityOnPeers ? qualityOnPeers.adjustments : [])

  const tier2Issues = []
    .concat(arch ? arch.issues : [], quality ? quality.issues : [], correctness ? correctness.issues : [])
    .concat(archOnPeers ? archOnPeers.additions : [], qualityOnPeers ? qualityOnPeers.additions : [])
    // ⛔ Tier 2 는 투표하지 않는다(Wave 4 확정). 교차 조정 결과는 **정보로** 싣고
    //    최종 판정은 Lead 병합 계약이 한다 — peer-review-gates.md § MergeContract
    .map((f) => ({ ...f, ...crossFields(crossByIdT2[f.id]) }))

  // ⛔ stage2Ran 은 **실제 응답 존재**로 계산한다. 트리거가 발화해도 렌즈가 null 이면
  //    `shouldRunStage2 && arch && quality` 가드에 걸려 Stage 2 는 0콜이다.
  //    true 를 하드코딩하면 이 필드의 목적(조용한 off 방어)을 정면으로 배반한다.
  //    Tier 3 반환과 같은 식을 써서 의미도 통일한다.
  const stage2Actually = !!(archOnPeers || qualityOnPeers)
  log(`Tier2 — Stage2 ${stage2Actually ? '완주' : '미실행(렌즈 결측)'}. issues ${tier2Issues.length}, 교차 조정 ${adjustments.length}건. Matrix 미투표(Lead 병합).`)
  return {
    mode: 'workflow', tier: 2, reviews, issues: tier2Issues,
    crossAdjustments: { archOnPeers, qualityOnPeers },
    stage2Ran: stage2Actually, stage2Trigger: trigger,
    ...(crossDeltaOn ? { crossCoverage } : {}),   // ⛔ 기본 반환 모양 불변
    ...(craftOn ? { craftAxes: craftSummary(tier2Issues, arch) } : {}),
    // ⛔ 완주 = 완전 완주 stage 수(Tier 3 의 s1full 과 같은 식) — Stage 1 은 세 렌즈가 모두 있을 때만 완주다.
    //    이전 판은 Stage 1 을 항상 1 로 셌다 — correctness 가 죽어도 교차가 돌면 "완주 2/2" 를 냈다(S24a 실패 주입 재현).
    metrics: metrics((reviews.length === 3 ? 1 : 0) + (archOnPeers && qualityOnPeers ? 1 : 0)),
  }
}

// ════════ Stage 3: Counter DA (strengths 도전 + issues 반론) ════════
phase('Stage 3: counter DA')
const allIssues = []
  .concat(arch ? arch.issues : [], quality ? quality.issues : [], correctness ? correctness.issues : [])
  .concat(archOnPeers ? archOnPeers.additions : [], qualityOnPeers ? qualityOnPeers.additions : [])
const allStrengths = [].concat(arch ? arch.strengths : [], quality ? quality.strengths : [], correctness ? correctness.strengths : [])
const counter = await callAgent(
  `${LENS_OVERRIDE}\n[역할] 반론자(review-counter 렌즈) — Devil's Advocate\n${TARGET}\n` +
  `[issues] ${JSON.stringify(allIssues)}\n[strengths(정상/우수 판정)] ${JSON.stringify(allStrengths)}\n` +
  `[목표] (1) 각 issue를 실측 재검증 — 과장/오독이면 refute + 인용. (2) strengths에 "정말 문제 없나?" 반례 탐색 — 반례 발견 시 missedIssues(id CT-X)로. 라인 인용 오류를 특히 의심.`,
  { label: 'stage3-counter', agentType: 'fz:review-counter', model: 'opus', effort: 'xhigh', schema: lensSchema(CounterSchema) })
if (!counter) log('WARN counter null — DA 패스 미수행 (issues 원판정 유지)')

// ════════ 병합 — 스크립트 binary 규칙 (id-기반 verdict 반영. Confidence Matrix/투표는 Lead) ════════
const crossById = crossIndex([
  { by: 'arch', result: archOnPeers }, { by: 'quality', result: qualityOnPeers },
])
const counterMap = {}
if (counter) for (const ch of counter.challenges) counterMap[ch.target] = ch

const mergedIssues = allIssues.map((f) => {
  const cross = crossFields(crossById[f.id])
  const ctr = counterMap[f.id]
  return {
    ...f,
    ...cross,
    // ⛔ `contested` 는 crossSeverity 가 없다 → 원본 severity 를 유지한다. 갈린 판정을
    //    조정으로 접으면 Lead 가 못 본 사이에 완화·강화가 확정된다.
    finalSeverity: cross.crossSeverity || f.severity,
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
  suggestion: mergedIssues.filter(f => f.finalSeverity === 'suggestion').length,
  fpFlagged: mergedIssues.filter(f => f.crossVerdict === 'false_positive' || f.counterVerdict === 'refute').length,
  // ⛔ `contested` 는 fpFlagged 에 안 들어간다 — 한 렌즈가 false_positive 라 해도 다른
  //    렌즈가 갈렸으면 깨끗한 오탐이 아니다. 대신 별도로 세어 **보이게** 한다.
  //    (이 수치가 0 이 아니면 Lead 가 crossVerdicts 를 읽어야 한다.)
  contested: mergedIssues.filter(f => f.crossVerdict === 'contested').length,
  // 구조 축 주입 여부 — structuralContext는 optional이라 누락 시 에러 없이 꺼진다. 반환값으로 판별 가능하게 남긴다.
  structuralAxes: !!input.structuralContext,
}
if (craftOn) {
  dist.craftAxes = craftSummary(mergedIssues, arch)
  log(`craft 축 — ${CRAFT_AXES.map(ax => `${ax} ${dist.craftAxes.counts[ax]}`).join(' / ')} · axisCoverage ${dist.craftAxes.axisCoverage ? dist.craftAxes.axisCoverage.length + '행' : '⛔없음'}${dist.craftAxes.missingAxes.length ? ` · ⛔빠진 축 ${dist.craftAxes.missingAxes.join('·')}` : ''}`)
}
log(`Tier3 issues ${mergedIssues.length}건 — critical ${dist.critical} / major ${dist.major} / minor ${dist.minor} / suggestion ${dist.suggestion} / FP·refute 플래그 ${dist.fpFlagged} / 판정갈림 ${dist.contested} / 구조축 ${dist.structuralAxes ? 'ON' : '⛔OFF'} (최종 투표·Matrix는 Lead)`)

// stagesCompleted = 완전 완주 stage 수 (stage2 미완주+stage3 완주 시 오보고 방지)
const s1full = !!(arch && quality && correctness)
const s2full = !!(archOnPeers && qualityOnPeers)
const s3full = !!counter
const stagesCompleted = [s1full, s2full, s3full].filter(Boolean).length
return {
  mode: 'workflow',
  tier: 3,
  stage2Ran: !!(archOnPeers || qualityOnPeers),
  stage2Trigger: trigger,
  reviews,          // 원본 per-agent (strengths/overall_assessment 포함)
  issues: mergedIssues,
  crossAdjustments: { archOnPeers, qualityOnPeers },
  ...(crossDeltaOn ? { crossCoverage } : {}),   // ⛔ 기본 반환 모양 불변
  strengthChallenges,  // counter의 strength 반례 (Lead 판정 입력)
  distribution: dist,
  metrics: metrics(stagesCompleted),  // Lead가 experiment-log §5.7 fz-peer-review 테이블 기록
}
