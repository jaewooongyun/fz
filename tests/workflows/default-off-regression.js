// 워크플로별 기본값 회귀 (R-B · R-C) — 옵션을 주지 않으면 워크플로의 모든 콜 입력이 그 워크플로의 기본값과 바이트 단위로 같다.
//   기본 off 워크플로: 미지정 == 기준 트리. 기본 on 워크플로(레지스트리 `defaultOn` — v4.42.0 peer-review): 미지정 == 켠 값.
//   기본 off 워크플로는 옵션마다 끄는 값(off) == 기준. 기본 on 워크플로는 **기본 on 옵션을 모두 끄면** == 기준이다 — 롤백 경로
//   (하나만 끄면 나머지가 켜져 있어 기준이 아니다 — 옵션마다는 '끔 != 켬' 으로 배선을 본다).
//   ⛔ 이 검사는 Workflow 층만 본다 — 모든 arm 에 같은 합성 structuralContext 를 넣는다. 실제 롤백은 Lead 가 브리프에서 §6 도 빼야 한다
//     (modules/review-structural-axes.md — 브리프는 Lead 가 조립해 스크립트가 거르지 못한다).
//   레지스트리는 tests/workflows/default-arms.js 가 재사용한다(require — 실행부는 직접 실행할 때만 돈다).
//
// ⛔ 비교 대상은 **콜 입력**(label · prompt · schema · model · effort · agentType)이다. 반환값은 비교하지 않는다 —
//    R-A 가 peer-review Tier 2 반환의 완주 수 계산을 고쳤다(프롬프트·스키마는 그대로). 반환까지 비교하면 그 수정이 회귀로 보인다.
//    하네스의 calls 는 스키마를 불리언으로만 남기므로 responder 가 opts.schema 를 직렬화해 잡는다.
// ⛔ 기준 소스(앞이 이긴다 — resolveBase, effort-arg.js 도 이것을 쓴다): env FZ_REGRESSION_BASE_TREE 의 workflows/<wf>.js
//    → env FZ_REGRESSION_BASE_SHA 의 이 저장소 이력 `git show <sha>:workflows/<wf>.js`(부르는 쪽 GIT_DIR 등 · 설정 주입을 지우고 부른다 —
//    늘 이 저장소의 이력이다) → 둘 다 없을 때만 저장소 고정본
//    tests/fixtures/workflow-base/default-off/workflows/<wf>.js.base(커밋 13755a6 의 workflows/*.js 와 콜 입력이 같다 — 이력 없는 사본에서도 돈다.
//    .js 가 아니어서 .js 글롭 검사가 옛 원문을 훑지 않는다 — 임시 <wf>.base.js 로 써서 넘긴다).
//    명시한 선택자(빈 값 포함)를 읽지 못하면 고정본으로 내려가지 않고 UNRUN(exit 2)이다. 고정본이 없어도 UNRUN 이다. 검사 이름의 `기준(…)` 이 출처다.
//    ⛔ 고정본은 두 가지 편집만 받는다 — 콜 입력 밖(주석)의 치환과, workflows/*.js 에 똑같이 적용한 문자열 치환. 유래 커밋과의 차이는 이 둘뿐이어야 한다.
//       의도한 기본 경로 변경은 고정본을 고쳐 맞추지 않고 아래 INTENDED 변환으로 적는다 — 고정본을 고쳐 FAIL 을 지우면 회귀가 가려진다.
//    ⛔ 고정본 16개(이 러너의 default-off/ 8개 + effort-arg.js 의 effort-arg/ 8개 — 어느 러너도 읽지 않는 사본 포함)는 해시 목록
//       tests/fixtures/workflow-base/SHA256SUMS 에 묶여 있다(verifyPinned). 기준을 고르기 전에 — 선택자를 줬어도 — 전부 대조하고, 어긋나거나
//       파일 집합이 다르거나 목록이 없으면 UNRUN(exit 2)이다. 견주는 파일 집합(pinnedFiles)은 그 폴더가 git 작업 트리 안이면 git 이 내보낼
//       파일(추적 + 무시되지 않은 미추적 — .DS_Store 같은 무시된 부산물은 빠지고 통째로 무시된 폴더는 내려가지 않는다)이고, 밖이면 폴더의
//       파일 전부다. 그 git 은 부르는 쪽의 GIT_DIR 등(훅이 내보낸다)과 설정 주입(GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT/KEY/VALUE ·
//       GIT_CONFIG_GLOBAL)을 지우고 부른다 — 답은 그 폴더가 든 작업 트리와 그 설정에서 온다.
//       위 두 가지 편집으로 고정본을 일부러 바꿨으면 같은 커밋에서 목록을 다시 쓴다(같은 집합을 고른다 — 작업 트리 밖이면 git 이 아무것도 내지 않아 전부다):
//         (cd tests/fixtures/workflow-base && shasum -a 256 $(find . -type f ! -name SHA256SUMS | sed 's#^\./##' | grep -vxF -f <(git ls-files -o -i --exclude-standard 2>/dev/null) | sort) > SHA256SUMS)
//       목록만 고쳐 UNRUN 을 지우지 않는다 — 고정본의 diff 와 목록의 diff 가 같은 커밋에 함께 보여야 한다.
//    health-check 러너는 env 를 비우지 않고 부른다 — 호출자 env 를 그대로 물려받는다. 그래서 전용 이름만 읽는다: 범용 FZ_BASE_TREE · FZ_BASE_SHA 는
//    A/B 기준 arm · 게이트 환경이 다른 뜻으로 내보낸다(F-363). 새 이름 없이 옛 이름만 있으면 WARN 줄을 내고 고정본으로 돈다.
// ⛔ 옵션마다 세 가지를 본다: 미지정 == 기준(defaultOn 이면 미지정 == 켬) · false == 기준 · true != 기준(옵션이 실제로 배선돼 있다 — 헛돌이 방어).
//    옵션이 닿지 않는 경로(예: Stage 2 가 없는 Tier 2 미발화)에서는 셋째를 true == 기준 으로 본다 — 옵션이 엉뚱한 경로로 새지 않는다.
// ⛔ `structural` 옵션(R-C 속도 arm)은 켜면 콜을 빼는 것이 목적이다 — 켠 쪽 두 검사(!= 기준 · 콜 구성 동일)를 여기서 하지 않고
//    그 값이 가리키는 전용 테스트가 본다. 미지정 == 기준 · off == 기준 은 똑같이 본다.
// 인자: --option NAME(여러 번) · --all-rb-options · 인자 없음 = 등록된 옵션 전부(health-check 러너가 인자 없이 돈다).
'use strict'
const crypto = require('crypto')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')

const ROOT = path.join(__dirname, '..', '..')
// 기준 선택자(resolveBase) — pinnedSha 는 고정본의 유래(검사 이름의 출처 표기)일 뿐 git 에서 읽지 않는다
const BASE_SEL = { tree: 'FZ_REGRESSION_BASE_TREE', sha: 'FZ_REGRESSION_BASE_SHA', gitRoot: ROOT,
  pinnedDir: path.join(__dirname, '..', 'fixtures', 'workflow-base', 'default-off', 'workflows'), pinnedSha: '13755a6' }

// 옵션 레지스트리 — 새 옵션(S16b · S17 …)은 여기에 한 줄 더한다. 없는 이름을 부르면 FAIL 이다.
// defaultOn: 그 옵션이 **기본으로 켜진** 워크플로(v4.42.0 — S25p 판정 PASS 인 peer-review 만). 나머지 워크플로는 기본 off 다.
//   ⛔ 바꾸려면 측정 판정이 먼저다 — tests/workflows/default-arms.js 가 원장 판정과 이 값을 대조한다.
const PEER_ON = ['peer-review']
const OPTIONS = {
  craftAxes: { workflows: ['peer-review', 'review-live'], on: { craftAxes: true }, off: { craftAxes: false }, defaultOn: PEER_ON },
  crossRequiredFields: { workflows: ['peer-review', 'review-live'], on: { crossRequiredFields: true }, off: { crossRequiredFields: false },
    defaultOn: PEER_ON, applies: sc => sc.stage2 },   // Stage 2 교차 프롬프트에만 닿는다
  // 두 워크플로 — 렌즈 에이전트가 미리 올리는 스킬(arch-critic · code-auditor)의 '자체 confidence 80% 미만이면 보고하지 않는다' 는
  //   [후보 보존] 문장에만 풀린다. peer-review 는 OVERRIDE 문장을 바꾸고, review-live(R-C S22)는 문장을 덧붙이고 스키마 사본에
  //   confidence 를 얹는다. OVERRIDE 가 모든 콜에 있어 applies 가 없다
  preserveLowConfidence: { workflows: ['peer-review', 'review-live'], on: { preserveLowConfidence: true }, off: { preserveLowConfidence: false },
    defaultOn: PEER_ON },
  // peer-review 만 — 이슈 항목 스키마에 oracle(판별 방법) 필수 필드(F-072). 프롬프트는 그대로, 스키마 사본만 바뀐다
  oracleField: { workflows: ['peer-review'], on: { oracleField: true }, off: { oracleField: false }, defaultOn: PEER_ON },
  // 두 워크플로 — 판정 한계 칸(axisCoverage gap · unverifiedPremises · limits · 동적 축 질문 · F-559 · F-448 · F-178 · F-117).
  //   Stage 1 프롬프트 · 렌즈 스키마 사본이 바뀐다. review-live 는 기본 off(S25 판정 전 · default-arms.js decided off)
  judgmentSlots: { workflows: ['peer-review', 'review-live'], on: { judgmentSlots: true }, off: { judgmentSlots: false }, defaultOn: PEER_ON },
  // review-live 만 — peer-review 는 기본 스키마에 위치 필드가 있다. Stage 1 두 콜의 스키마만 바뀐다
  locatedFindings: { workflows: ['review-live'], on: { locatedFindings: true }, off: { locatedFindings: false } },
  // R-C 속도 arm — 켜면 병합 콜을 뺄 수 있다(structural)
  mergeMode: { workflows: ['plan-lean2'], on: { mergeMode: 'conditional' }, off: { mergeMode: 'always' },
    structural: 'tests/workflows/plan-lean2-merge-arm.js' },
  // R-C 속도 arm — 켜면 교차 2콜을 뺄 수 있다(structural)
  stage2: { workflows: ['review-live'], on: { stage2: 'conditional' }, off: { stage2: 'always' },
    structural: 'tests/workflows/review-live-stage2-arm.js' },
  // R-C 교차 delta — 콜 수는 그대로, Stage 2 교차의 스키마 · 프롬프트만 바뀐다(동치는 tests/workflows/cross-delta-arm.js)
  crossOutput: { workflows: ['peer-review', 'review-live'], on: { crossOutput: 'delta' }, off: { crossOutput: 'full' },
    defaultOn: PEER_ON, applies: sc => sc.stage2 },
  // S13 — plan-lean2 적대 렌즈의 필수 축을 과제에서 받는다(F-383). 빈 배열은 미지정과 같다(기본 UI 축)
  edgeAxes: { workflows: ['plan-lean2'], on: { edgeAxes: ['스크립트 종료 코드', '부분 입력'] }, off: { edgeAxes: [] } },
  // S13 — 방어 항목 failurePath(F-438). 켜면 edge 스키마 사본과 프롬프트 한 줄이 바뀐다
  defenseFailurePath: { workflows: ['plan-lean2'], on: { defenseFailurePath: true }, off: { defenseFailurePath: false } },
  // S13 — 렌즈 재독 억제 문장(F-362 · 효과 측정 전). 켜면 네 콜의 코드 컨텍스트 줄이 바뀐다
  noRereadContext: { workflows: ['plan-lean2'], on: { noRereadContext: true }, off: { noRereadContext: false } },
  // R-C 사전 수집 스냅샷 — Stage 1 두 프롬프트에만 닿는다(콜 수 그대로). 빈 문자열은 미지정과 같다
  snapshotDir: { workflows: ['review-live'], on: { snapshotDir: '/tmp/fz-snapshot' }, off: { snapshotDir: '' } },
  // B11 측정 arm — '켬' 은 counter 를 끈 arm 이다(이름과 반대). 켜면 Stage 3 콜을 뺀다(structural)
  counter: { workflows: ['review-live'], on: { counter: 'off' }, off: { counter: 'opus' },
    structural: 'tests/workflows/review-live-counter-arm.js' },
  // S19 — 렌즈 에이전트 정의의 점검 카탈로그 적용 결과 칸. counter(review-live · peer-review Tier 3) · 적대 렌즈(plan-lean2)에만 닿는다
  catalogHits: { workflows: ['peer-review', 'review-live', 'plan-lean2'], on: { catalogHits: true }, off: { catalogHits: false },
    defaultOn: PEER_ON, applies: sc => !sc.name.startsWith('Tier 2') },
  // F-587 — lean2-full 스키마 사본의 Step 칸 complexity · 프롬프트 Step 칸 나열. 끄면 기준과 같다
  stepComplexity: { workflows: ['plan-lean2'], on: { stepComplexity: true }, off: { stepComplexity: false } },
}

const BASE_ARGS = { diffPath: '/tmp/diff.patch', intentContext: '합성 의도', structuralContext: '합성 구조 축 브리프' }
// 경로가 다른 시나리오 — peer-review 는 Tier 2(트리거 미발화 · 발화)와 Tier 3 을 다 탄다
const SCENARIOS = {
  'peer-review': [
    { name: 'Tier 2 · 트리거 미발화', args: {}, fire: false, stage2: false },
    { name: 'Tier 2 · 트리거 발화', args: {}, fire: true, stage2: true },
    { name: 'Tier 3 · deep', args: { deep: true }, fire: true, stage2: true },
  ],
  'review-live': [{ name: '기본', args: {}, fire: false, stage2: true }],
  // 둘째 경로 = Stage 1 의미 필드가 전부 빈 응답 — mergeMode 'conditional' 이 병합을 실제로 빼는 경로다(없으면 켬 == 끔 이라
  //   default-arms.js 가 plan-lean2 의 기본값을 판정하지 못한다)
  'plan-lean2': [{ name: '기본', args: { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }, fire: false, stage2: false },
    { name: 'Stage 1 의미 필드 빔', args: { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }, fire: false, stage2: false, quiet: true }],
}

function responses(wf, fire, quiet) {
  const major = { id: 'Q1', file: 'a.swift', line_range: '10-12', severity: 'major', perspective: 'p', discoveryAxis: 'code_quality',
    origin: 'regression', description: 'd', evidence: 'e', confidence: 90 }
  if (wf === 'peer-review') {
    return {
      'stage1-arch': { issues: [], strengths: ['s'], overall_assessment: 'o' },
      'stage1-quality': { issues: fire ? [major] : [], strengths: [], overall_assessment: 'o' },
      'stage1-correctness': { issues: [], strengths: [], overall_assessment: 'o' },
      'stage2-arch-on-peers': { adjustments: [], additions: [] },
      'stage2-quality-on-peers': { adjustments: [], additions: [] },
      'stage3-counter': { challenges: [], missedIssues: [] },
    }
  }
  if (wf === 'plan-lean2') {
    return {
      'lean2-full': { directionVerdict: 'PROCEED', directionAlternatives: [], steps: [{ id: 'S1', title: 't', files: ['a'] }], readScope: [], writeScope: [] },
      'lean2-edge': { edgeCases: quiet ? [] : [{ id: 'E1', case: 'c', failureScenario: 'f', whereItBreaks: 'w' }], impactNotes: [], latentDefects: [] },
      'lean2-impact-arch': { impactFiles: [], patternVerdicts: [] },
      'lean2-merge': { addedEdgeCases: [], addedImpact: [], stepAmendments: [], implicationRegister: [], unresolved: [] },
    }
  }
  return {
    'stage1-arch': { findings: [{ id: 'A1', severity: 'minor', category: 'c', title: 't', detail: 'd', evidence: 'e' }], okAreas: ['ok'] },
    'stage1-quality': { findings: [], okAreas: [] },
    'stage2-arch-on-quality': { adjustments: [], additions: [] },
    'stage2-quality-on-arch': { adjustments: [], additions: [] },
    'stage3-counter': { challenges: [], missedFindings: [] },
  }
}

async function callsOf(file, wf, scenario, extraArgs) {
  const calls = []
  const table = responses(wf, scenario.fire, scenario.quiet)
  await run(file, {
    args: Object.assign({}, BASE_ARGS, scenario.args, extraArgs),
    responder: (prompt, opts) => {
      calls.push({ label: opts.label, agentType: opts.agentType, model: opts.model, effort: opts.effort,
                   schema: JSON.stringify(opts.schema || null), prompt })
      return table[opts.label] ? JSON.parse(JSON.stringify(table[opts.label])) : null
    },
  })
  return calls
}

// ⛔ R-D 의도된 기본 경로 변경 — 기준 트리의 콜 입력을 이 변환으로 옮긴 뒤 비교한다. 그 밖의 차이는 여전히 회귀다.
//    변환은 정확한 치환이다 — 기준 콜이 전제(옛 agentType · 앵커 문장 있음 · 새 줄 없음)와 다르면 던져서 실패한다(변환이 헛돌면 회귀를 가린다).
//    S32(plan-lean2 병합 콜 무탐색 · F-345): agentType plan-structure → plan-merge · 계약 한 줄. 새 모양은 plan-lean2-merge-no-explore.js 가 본다.
const MERGE_CONTRACT = '⛔ 이 콜에는 탐색 도구가 없다 — 위 코드 컨텍스트 파일도 읽지 않는다. 입력 JSON 만으로 접고, 근거가 입력에 없어 접을 수 없으면 unresolved 에 적는다.\n'
const MERGE_AT = '⛔ 출력 형식: StructuredOutput 인자는 유효한 JSON.'
// R-F4 F4-2(F-342): VerifySpec 에 env — 기준 lean2-full 스키마의 VerifySpec `tools` 바로 뒤에 `env` 를 넣는다. 새 모양의 정본은
//   workflows/plan-lean2.js VerifySpec 이다(설명 문구가 어긋나면 이 비교가 실패한다 — 그것이 맞다). 기준에 tools 가 없거나 env 가 이미 있으면 던진다.
const ENV_PROP = { type: 'array', items: { type: 'string' },
  description: 'command 가 ${NAME:?} 등으로 요구하는 환경 변수 이름 (예: ["FZ_IMPL_ROOT"]). 없거나 비면 게이트를 돌리지 않고 미판정으로 남긴다 — 통과 증거를 강등하지 않기 위함(F-342)' }
function addEnv(node, hit) {
  if (Array.isArray(node)) return node.map(n => addEnv(n, hit))
  if (!node || typeof node !== 'object') return node
  const out = {}
  for (const [k, v] of Object.entries(node)) {
    out[k] = addEnv(v, hit)
    if (k === 'tools' && v && v.type === 'array' && String(v.description || '').startsWith('command 가 필요로 하는 외부 명령')) {
      if ('env' in node) throw new Error('기준 VerifySpec 에 이미 env 가 있다 — 기준 트리가 R-F4 이후인지 본다')
      out.env = ENV_PROP
      hit.n++
    }
  }
  return out
}
const INTENDED = {
  'plan-lean2': {
    'lean2-full': c => {
      const hit = { n: 0 }
      const schema = addEnv(JSON.parse(c.schema), hit)
      if (hit.n < 1) throw new Error('기준 lean2-full 스키마에 VerifySpec tools 가 없다 — F4-2 변환 전제와 다르다')
      return Object.assign({}, c, { schema: JSON.stringify(schema) })
    },
    'lean2-merge': c => {
      if (c.agentType !== 'fz:plan-structure' || c.prompt.split(MERGE_AT).length !== 2 || c.prompt.includes(MERGE_CONTRACT)) {
        throw new Error(`기준 lean2-merge 콜이 S32 변환 전제와 다르다(agentType ${c.agentType}) — 기준 트리가 S32 이전인지 본다`)
      }
      return Object.assign({}, c, { agentType: 'fz:plan-merge', prompt: c.prompt.replace(MERGE_AT, MERGE_CONTRACT + MERGE_AT) })
    },
  },
}
const intended = (wf, calls) => calls.map(c => ((INTENDED[wf] || {})[c.label] ? INTENDED[wf][c.label](c) : c))

// 고정본 해시 목록 대조 — root(기본: 저장소의 tests/fixtures/workflow-base) 아래 파일(pinnedFiles)을 SHA256SUMS 와 견준다. 반환 = 대조한 파일 수.
//   목록 줄 = `<sha256 64자><공백 2><root 기준 상대 경로>`(`shasum -a 256` 출력 꼴). 목록 ↔ 폴더의 파일 집합이 같아야 하고 해시가 전부 같아야 한다.
//   ⛔ 어긋나면 던진다(사유에 목록 파일 이름) — 호출자가 UNRUN(exit 2)으로 끝낸다. 통과시키면 변조된 기준으로 '회귀 없음' 이 나온다.
const PINNED_ROOT = path.join(__dirname, '..', 'fixtures', 'workflow-base')
const SUMS_NAME = 'SHA256SUMS'
// 저장소를 바꾸는 git 환경 변수 — 훅이나 다른 도구가 내보낸다. 남기면 git 이 root 가 든 작업 트리가 아니라 그 저장소로 답한다
const GIT_REPO_ENV = ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR',
  'GIT_NAMESPACE', 'GIT_PREFIX']
// 설정을 바꾸는 git 환경 변수 — 명령 범위 설정(GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT 와 그 GIT_CONFIG_KEY_<n> · GIT_CONFIG_VALUE_<n> 묶음 —
//   묶음은 접두로 지운다)은 저장소 로컬 core.excludesFile 을 이기고, 전역 설정 경로(GIT_CONFIG_GLOBAL)는 로컬 값이 없을 때 무시 규칙을 정한다
const GIT_CONFIG_ENV = ['GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_CONFIG_GLOBAL']
const GIT_CONFIG_PREFIX = ['GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_']
// git 에 넘길 env — 부르는 쪽 env 에서 GIT_REPO_ENV · GIT_CONFIG_ENV · 설정 키/값 묶음을 지운 사본. 무시 조회(gitIgnored)와 기준 SHA 의
//   git show(resolveBase)가 함께 쓴다 — 답은 늘 그 git 이 가리킨 작업 트리 · 저장소와 그 설정에서 온다
function repoFreeEnv() {
  const env = Object.assign({}, process.env)
  for (const k of Object.keys(env)) {
    if (GIT_REPO_ENV.includes(k) || GIT_CONFIG_ENV.includes(k) || GIT_CONFIG_PREFIX.some(p => k.startsWith(p))) delete env[k]
  }
  return env
}
// root 가 git 작업 트리 안이면 그 아래의 무시된 미추적 파일과 통째로 무시된 폴더(git 이 내보내지 않는 것 — root 기준 상대 경로). 폴더는
//   `<경로>/` 한 줄이다(--directory — 추적 파일이 없고 안이 전부 무시된 폴더. git 은 그 안을 읽지 않는다). 작업 트리 밖 · git 부재 ·
//   git 실패면 빈 집합이다 — 그때는 폴더 전부를 견준다(대조를 줄이는 쪽으로 틀리지 않는다)
//   ⛔ git 은 repoFreeEnv() 로 부른다 — 부르는 쪽의 저장소 환경 변수와 설정 주입을 지운다. 남기면 다른 저장소나 주입한 설정의
//      (더 넓을 수 있는) 무시 규칙으로 목록 밖 파일이 대조에서 빠진다
function gitIgnored(root) {
  const env = repoFreeEnv()
  try {
    return new Set(execFileSync('git', ['-C', root, 'ls-files', '-z', '--others', '--ignored', '--exclude-standard', '--directory'],
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'], env }).split('\0').filter(Boolean))
  } catch (e) { return new Set() }
}
// 목록과 견줄 파일 — root 아래 파일(목록 파일 제외) → root 기준 상대 경로(`/` 구분). 자기 시험의 사본도 이 집합만 옮긴다.
//   root 가 git 작업 트리 안이면 git 이 내보낼 파일(추적 + 무시되지 않은 미추적)만 — 폴더를 열면 OS 가 만드는 .DS_Store 같은 무시된
//   부산물이 두 러너를 UNRUN 으로 만들지 않는다. 무시 규칙에 걸려도 추적하는 파일 · 무시되지 않은 새 파일은 남는다(목록에 없으면 UNRUN)
//   통째로 무시된 폴더(gitIgnored 의 `<경로>/`)는 내려가지 않는다 — 읽을 수 없어도 UNRUN 이 아니다. 무시되지 않은 폴더를 읽지 못하면 던진다
function pinnedFiles(root) {
  const have = [], ignored = gitIgnored(root)
  const walk = rel => {
    for (const e of fs.readdirSync(path.join(root, rel), { withFileTypes: true })) {
      const r = rel ? `${rel}/${e.name}` : e.name
      if (e.isDirectory()) { if (!ignored.has(`${r}/`)) walk(r) }
      else if (r !== SUMS_NAME && !ignored.has(r)) have.push(r)
    }
  }
  walk('')
  return have
}
function verifyPinned(root = PINNED_ROOT) {
  let text
  try { text = fs.readFileSync(path.join(root, SUMS_NAME), 'utf8') } catch (e) {
    throw new Error(`고정본 해시 목록 ${SUMS_NAME} 을 읽지 못했다 — ${path.join(root, SUMS_NAME)}: ${e.code || e.message}`)
  }
  const listed = new Map()
  for (const line of text.split('\n').filter(Boolean)) {
    const m = /^([0-9a-f]{64}) {2}(\S.*)$/.exec(line)
    if (!m || listed.has(m[2])) throw new Error(`${SUMS_NAME} 의 줄을 읽지 못했다(형식 · 중복) — ${line.slice(0, 80)}`)
    listed.set(m[2], m[1])
  }
  const have = pinnedFiles(root)
  const extra = have.filter(p => !listed.has(p)), gone = [...listed.keys()].filter(p => !have.includes(p))
  if (extra.length || gone.length) {
    throw new Error(`${SUMS_NAME} 와 고정본 폴더의 파일 집합이 다르다 — 목록에 없는 파일 ${extra.length}(${extra[0] || '-'}) · 폴더에 없는 파일 ${gone.length}(${gone[0] || '-'})`)
  }
  for (const [rel, want] of listed) {
    const got = crypto.createHash('sha256').update(fs.readFileSync(path.join(root, rel))).digest('hex')
    if (got !== want) throw new Error(`${SUMS_NAME} 와 고정본이 다르다 — ${rel} (목록 ${want.slice(0, 12)} · 실제 ${got.slice(0, 12)})`)
  }
  return listed.size
}

// 기준 원문 하나를 고른다 — 머리말의 순서(트리 > SHA > 고정본)와 '명시한 선택자는 고정본으로 내려가지 않는다' 의 유일한 구현이다.
//   effort-arg.js 도 자기 sel 로 이것을 부른다 — 이력에 묶인 러너가 늘면 이 본문을 복사하지 않고 이것을 부른다.
//   sel = { tree · sha: 선택자 env 이름, gitRoot: git show 를 돌릴 저장소, pinnedDir: 고정본 폴더, pinnedSha: 고정본의 유래(출처 표기),
//           pinnedRoot?: 해시 목록을 대조할 루트(시험용 — 없으면 저장소 고정본 루트) }
//   git show 도 repoFreeEnv() 로 부른다 — 부르는 쪽 GIT_DIR 등이 다른 저장소를 가리켜도 gitRoot 의 이력만 읽는다
//   반환 { file, from } — SHA · 고정본 원문은 tmp/<wf>.base.js 로 써서 넘긴다(하네스는 .js 를 읽는다).
//   ⛔ 읽지 못하면 던진다 — 호출자가 UNRUN(exit 2)으로 끝낸다. 빈 값도 명시다: 미지정으로 읽으면 조용히 고정본으로 가고,
//      빈 트리 값을 경로로 쓰면 path.join('', 'workflows') 가 cwd 의 workflows/ 를 기준으로 읽는다.
//   ⛔ 기준을 고르기 전에 고정본 전부를 해시 목록과 대조한다 — 선택자를 줘서 고정본을 읽지 않는 실행도 같다(변조된 고정본을 둔 채 통과하지 않는다).
function resolveBase(wf, tmp, sel) {
  verifyPinned(sel.pinnedRoot)
  const tree = process.env[sel.tree], sha = process.env[sel.sha]
  const noFallback = '명시한 선택자는 고정본으로 내려가지 않는다'
  if (tree !== undefined) {
    if (!tree) throw new Error(`${sel.tree} 가 빈 값이다 — ${noFallback}`)
    const f = path.join(tree, 'workflows', `${wf}.js`)
    if (!fs.existsSync(f)) throw new Error(`${sel.tree} 에 ${wf}.js 가 없다 — ${f} (${noFallback})`)
    // 있는 것과 읽히는 것은 다르다 — 그 자리가 폴더이거나 권한이 없으면 하네스가 UNRUN 갈래 밖에서 읽다 던져 exit 1(회귀)로 읽힌다
    try { fs.readFileSync(f, 'utf8') } catch (e) { throw new Error(`${sel.tree} 의 ${wf}.js 를 읽지 못했다 — ${f}: ${e.code || e.message} (${noFallback})`) }
    return { file: f, from: sel.tree }
  }
  let src
  if (sha !== undefined) {
    if (!sha) throw new Error(`${sel.sha} 가 빈 값이다 — ${noFallback}`)
    try {
      src = execFileSync('git', ['-C', sel.gitRoot, 'show', `${sha}:workflows/${wf}.js`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], env: repoFreeEnv() })
    } catch (e) {
      throw new Error(`git show ${sha}:workflows/${wf}.js 실패(${sel.sha}) — ${String(e.stderr || e.message).trim().split('\n')[0]} (${noFallback})`)
    }
  } else {
    const p = path.join(sel.pinnedDir, `${wf}.js.base`)
    if (!fs.existsSync(p)) throw new Error(`저장소 고정본이 없다 — ${p}`)
    src = fs.readFileSync(p, 'utf8')
  }
  const f = path.join(tmp, `${wf}.base.js`)
  fs.writeFileSync(f, src)
  return { file: f, from: sha !== undefined ? `git ${sha}(${sel.sha})` : `고정본 ${sel.pinnedSha}` }
}

function baseFile(wf, tmp) { return resolveBase(wf, tmp, BASE_SEL) }

function firstDiff(a, b) {
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const x = a[i], y = b[i]
    if (!x || !y) return `콜 수 ${a.length} ≠ ${b.length}`
    for (const k of ['label', 'agentType', 'model', 'effort', 'schema', 'prompt']) if (x[k] !== y[k]) return `${i}번 콜(${x.label}) ${k} 다름`
  }
  return null
}

const labels = calls => calls.map(c => c.label).sort().join(',')   // ⛔ 옵션은 콜을 더하거나 빼지 않는다 — 콜별 검사는 빠진 콜을 못 본다
let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

module.exports = { OPTIONS, SCENARIOS, BASE_ARGS, callsOf, firstDiff, resolveBase }

if (require.main === module) (async () => {
  const argv = process.argv.slice(2)
  // 고정본이 목록과 다르면 아래 자기 시험도 돌리지 않는다 — 자식들이 같은 사유로 UNRUN 이 되어 무관한 셀이 FAIL 로 찍힌다
  try { verifyPinned() } catch (e) {
    console.log(`UNRUN  고정본을 믿을 수 없다 — ${e.message.split('\n')[0]} (⛔ 통과 아님)`)
    process.exit(2)
  }
  // F-406 — UNRUN 경로가 임시 폴더를 남기지 않는다: 전용 TMPDIR 에서 기준 소스가 없는 자식을 돌려 남은 fz-default-off-* 를 센다
  let selfUnrun = ''   // 자기 시험을 준비하지 못한 사유 — 임시 폴더를 지운 뒤 UNRUN(exit 2)으로 끝낸다
  if (!process.env.FZ_DEFAULT_OFF_CHILD) {
    const box = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-f406-'))
    try {
      // 해시 목록 대조(verifyPinned) — 고정본 루트의 사본을 한 군데씩 건드리면 resolveBase 가 기준을 고르기 전에 던진다
      const copyTree = (src, dst) => {
        fs.mkdirSync(dst, { recursive: true })
        for (const e of fs.readdirSync(src, { withFileTypes: true })) {
          if (e.isDirectory()) copyTree(path.join(src, e.name), path.join(dst, e.name))
          else fs.copyFileSync(path.join(src, e.name), path.join(dst, e.name))
        }
      }
      // 사본에는 목록과 견주는 파일과 목록만 옮긴다 — 고정본 폴더의 무시된 부산물까지 옮기면 아래 셀이 변조가 아니라 그 파일 때문에 던진다
      const copyPinned = dst => {
        for (const rel of [...pinnedFiles(PINNED_ROOT), SUMS_NAME]) {
          fs.mkdirSync(path.dirname(path.join(dst, rel)), { recursive: true })
          fs.copyFileSync(path.join(PINNED_ROOT, rel), path.join(dst, rel))
        }
      }
      check(`pinned-sums-clean — 저장소 고정본이 ${SUMS_NAME} 와 같다`, verifyPinned() > 0, '대조한 파일 0')
      const refused = (name, what, mutate, sel = BASE_SEL) => {
        const root = path.join(box, `pin-${name}`)
        copyPinned(root)
        mutate(root)
        let msg = ''
        try { resolveBase('plan-lean2', box, Object.assign({}, sel, { pinnedRoot: root })) } catch (e) { msg = e.message }
        check(`pinned-sums-${name} — ${what}: resolveBase 가 던진다(사유에 ${SUMS_NAME})`, msg.includes(SUMS_NAME), msg || '던지지 않았다')
      }
      const unread = path.join('default-off', 'workflows', 'code-pair.js.base')   // 이 러너가 읽지 않는 사본
      refused('tampered-unread-copy', '어느 러너도 읽지 않는 사본을 고쳤다', r => fs.appendFileSync(path.join(r, unread), '\n// tamper\n'))
      refused('extra-file', '목록에 없는 사본이 생겼다', r => fs.writeFileSync(path.join(r, 'default-off', 'workflows', 'extra.js.base'), '// x\n'))
      refused('missing-file', '목록의 사본이 없다', r => fs.rmSync(path.join(r, 'effort-arg', 'workflows', 'plan-lean.js.base')))
      refused('missing-list', '목록 파일이 없다', r => fs.rmSync(path.join(r, SUMS_NAME)))
      // 선택자를 준 실행도 대조를 건너뛰지 않는다 — 트리 선택자가 가리키는 기준은 멀쩡하고 고정본만 변조된 경우
      process.env.FZ_PINNED_SELFTEST_TREE = ROOT
      try {
        refused('checked-before-selector', '트리 선택자를 줬고 고정본이 변조됐다', r => fs.appendFileSync(path.join(r, unread), '\n// tamper\n'),
          Object.assign({}, BASE_SEL, { tree: 'FZ_PINNED_SELFTEST_TREE' }))
      } finally { delete process.env.FZ_PINNED_SELFTEST_TREE }
      const { spawnSync } = require('child_process')
      const r = spawnSync(process.execPath, [__filename, '--option', 'mergeMode'], { encoding: 'utf8',
        env: Object.assign({}, process.env, { FZ_DEFAULT_OFF_CHILD: '1', TMPDIR: box, FZ_REGRESSION_BASE_TREE: path.join(box, 'no-such-tree') }) })
      const left = fs.readdirSync(box).filter(n => n.startsWith('fz-default-off-'))
      check('f406-unrun-leaves-no-tmp — 기준 소스 없음(UNRUN exit 2) 뒤 임시 폴더 0', r.status === 2 && /UNRUN/.test(r.stdout || '') && left.length === 0,
        `exit ${r.status} · 남은 폴더 ${left.length}`)
      // 빈 값도 명시한 선택자다 — 미지정으로 읽어 고정본으로 내려가면 자식이 끝까지 돌아 exit 0 이다
      const emptyEnv = Object.assign({}, process.env, { FZ_DEFAULT_OFF_CHILD: '1', TMPDIR: box, FZ_REGRESSION_BASE_SHA: '' })
      delete emptyEnv.FZ_REGRESSION_BASE_TREE
      const em = spawnSync(process.execPath, [__filename, '--option', 'mergeMode'], { encoding: 'utf8', env: emptyEnv })
      check('empty-selector-unrun — FZ_REGRESSION_BASE_SHA 빈 값은 고정본으로 내려가지 않는다(UNRUN exit 2)', em.status === 2 && /^UNRUN .*빈 값/m.test(em.stdout || ''),
        `exit ${em.status}`)
      // 읽지 못하는 SHA 도 명시한 선택자다 — 고정본으로 내려가면 자식이 끝까지 돌아 exit 0 이다
      const bad = spawnSync(process.execPath, [__filename, '--option', 'mergeMode'], { encoding: 'utf8',
        env: Object.assign({}, emptyEnv, { FZ_REGRESSION_BASE_SHA: '0000000' }) })
      check('unreadable-selector-unrun — 읽지 못하는 FZ_REGRESSION_BASE_SHA 는 고정본으로 내려가지 않는다(UNRUN exit 2)', bad.status === 2 && /^UNRUN /m.test(bad.stdout || ''),
        `exit ${bad.status}`)
      // 있지만 읽지 못하는 기준(워크플로 자리에 폴더) — 없는 것과 같은 UNRUN 이다. 하네스가 읽다 던지면 exit 1(회귀)로 읽힌다
      const dirTree = path.join(box, 'dir-tree')
      for (const wf of OPTIONS.mergeMode.workflows) fs.mkdirSync(path.join(dirTree, 'workflows', `${wf}.js`), { recursive: true })
      const ur = spawnSync(process.execPath, [__filename, '--option', 'mergeMode'], { encoding: 'utf8',
        env: Object.assign({}, process.env, { FZ_DEFAULT_OFF_CHILD: '1', TMPDIR: box, FZ_REGRESSION_BASE_TREE: dirTree }) })
      check('unreadable-tree-file-unrun — 기준 트리의 워크플로 자리가 폴더면 고정본으로 내려가지 않는다(UNRUN exit 2)',
        ur.status === 2 && /^UNRUN .*읽지 못했다/m.test(ur.stdout || ''), `exit ${ur.status}`)
      // git 작업 트리 안에서는 git 이 내보낼 파일만 목록과 견준다 — 임시 git 작업 트리에 두 러너가 읽는 파일과 고정본을 옮겨 두고 자식으로 돌린다.
      //   무시 규칙은 그 저장소의 info/exclude(`.DS_Store`)에만 두고 사용자 전역 무시 파일을 끊는다(core.excludesFile — 사람마다 갈리지 않게).
      //   바깥 git 환경(훅이 건 GIT_DIR 등)과 기준 선택자 · 대상 트리 env 는 넘기지 않는다 — 자식은 고정본으로 돈다
      const gitTree = path.join(box, 'git-tree'), kidTmp = path.join(box, 'git-kid-tmp')
      const gitEnv = Object.assign({}, process.env)
      for (const k of [...GIT_REPO_ENV, 'FZ_REGRESSION_BASE_TREE', 'FZ_REGRESSION_BASE_SHA', 'FZ_EFFORT_BASE_TREE', 'FZ_EFFORT_BASE_SHA', 'FZ_WF_ROOT']) delete gitEnv[k]
      const git = (...a) => spawnSync('git', ['-C', gitTree, ...a], { encoding: 'utf8', env: gitEnv })
      for (const rel of [['workflows'], ['tests', 'lib'], ['tests', 'workflows'], ['tests', 'fixtures', 'workflows']]) {
        copyTree(path.join(ROOT, ...rel), path.join(gitTree, ...rel))
      }
      fs.mkdirSync(path.join(gitTree, 'scripts'))
      fs.copyFileSync(path.join(ROOT, 'scripts', 'check_wf_syntax.js'), path.join(gitTree, 'scripts', 'check_wf_syntax.js'))
      const wb = path.join(gitTree, 'tests', 'fixtures', 'workflow-base')
      copyPinned(wb)
      fs.mkdirSync(kidTmp)
      const prep = [git('init', '-q'), git('config', 'core.excludesFile', os.devnull)]
      if (prep.every(p => p.status === 0)) {
        fs.mkdirSync(path.join(gitTree, '.git', 'info'), { recursive: true })
        fs.writeFileSync(path.join(gitTree, '.git', 'info', 'exclude'), '.DS_Store\n')
        prep.push(git('add', '-A'))
      }
      const drop = Buffer.from([0, 0, 0, 1, 0x42, 0x75, 0x64, 0x31])   // 폴더를 열면 OS 가 남기는 .DS_Store 꼴(NUL 바이트)
      const drops = [['.DS_Store'], ['effort-arg', '.DS_Store']]
      for (const d of drops) fs.writeFileSync(path.join(wb, ...d), drop)
      // 전제 — 놓은 부산물은 무시되고(check-ignore 0) 아래 메모 파일은 무시되지 않는다(1)
      const ign = rel => git('check-ignore', '-q', path.posix.join('tests/fixtures/workflow-base', rel)).status
      const pre = [...drops.map(d => ign(d.join('/'))), ign('notes.txt')]
      if (prep.some(p => p.status !== 0) || pre.join(',') !== '0,0,1') {
        selfUnrun = `임시 git 작업 트리를 준비하지 못했다 — git exit ${prep.map(p => p.status).join(',')} · check-ignore ${pre.join(',')}(기대 0,0,1)`
      } else {
        const kids = () => [['default-off-regression.js', '--option', 'mergeMode'], ['effort-arg.js']].map(([f, ...a]) =>
          spawnSync(process.execPath, [path.join(gitTree, 'tests', 'workflows', f), ...a], { cwd: gitTree, encoding: 'utf8',
            env: Object.assign({}, gitEnv, { FZ_DEFAULT_OFF_CHILD: '1', TMPDIR: kidTmp }) }))
        const said = ks => ks.map(k => `exit ${k.status} ${String(k.stdout || '').trim().split('\n').pop().slice(0, 140)}`).join(' · ')
        // 부산물은 끝까지 둔다 — 아래 두 셀은 UNRUN 의 사유가 부산물이 아니라 그 파일 하나인지까지 본다
        const onlyExtra = (ks, rel) => ks.every(k => k.status === 2 && String(k.stdout).includes(`${SUMS_NAME} 와 고정본 폴더의 파일 집합이 다르다 — 목록에 없는 파일 1(${rel})`))
        // 셀 안에서만 process.env 를 바꾼다(값 undefined = 지움) — 끝나면 되돌린다(뒤 셀 · 본 회귀가 다른 저장소 · 설정을 보지 않게)
        const withEnv = (vars, fn) => {
          const set = v => { for (const [k, x] of Object.entries(v)) { if (x === undefined) delete process.env[k]; else process.env[k] = x } }
          const before = Object.fromEntries(Object.keys(vars).map(k => [k, process.env[k]]))
          set(vars)
          try { return fn() } finally { set(before) }
        }
        const lsIgnored = (cwd, env, ...more) => spawnSync('git', ['-C', cwd, 'ls-files', '-z', '-o', '-i', '--exclude-standard', ...more], { encoding: 'utf8', env })
        const lists = (p, rel) => p.status === 0 && String(p.stdout).split('\0').includes(rel)
        let ks = kids()
        check('pinned-sums-git-ignored-dropping — git 이 무시하는 미추적 파일(.DS_Store)이 고정본 폴더에 있어도 두 러너가 돈다(exit 0)',
          ks.every(k => k.status === 0), said(ks))
        fs.writeFileSync(path.join(wb, 'notes.txt'), '메모\n')
        ks = kids()
        check(`pinned-sums-git-untracked-extra — 무시되지 않은 미추적 파일은 목록에 없는 파일이다: 두 러너 UNRUN(exit 2 · 사유 = ${SUMS_NAME} 에 없는 notes.txt 하나)`,
          onlyExtra(ks, 'notes.txt'), said(ks))
        // 부르는 쪽의 GIT_DIR 이 무시 규칙이 더 넓은 다른 저장소(.DS_Store 에 notes.txt 도 무시)를 가리켜도 견주는 집합은 고정본 폴더가 든
        //   작업 트리의 git 이 정한다 — 그 저장소의 규칙으로 답하면 notes.txt 가 빠져 목록 밖 파일을 둔 채 대조가 통과한다.
        //   GIT_DIR 은 이 셀 안에서만 걸고 되돌린다
        const other = path.join(box, 'git-other'), otherEnv = Object.assign({}, gitEnv, { GIT_DIR: path.join(box, 'git-other', '.git') })
        fs.mkdirSync(other)
        const oprep = [['init', '-q'], ['config', 'core.excludesFile', os.devnull]].map(a => spawnSync('git', ['-C', other, ...a], { encoding: 'utf8', env: gitEnv }))
        if (oprep.every(p => p.status === 0)) {
          fs.mkdirSync(path.join(other, '.git', 'info'), { recursive: true })
          fs.writeFileSync(path.join(other, '.git', 'info', 'exclude'), '.DS_Store\nnotes.txt\n')
        }
        // 전제 — 이 환경을 그대로 물려받은 git 은 다른 저장소의 규칙으로 답한다(notes.txt 를 무시된 파일로 낸다)
        const probe = spawnSync('git', ['-C', wb, 'ls-files', '-z', '-o', '-i', '--exclude-standard'], { encoding: 'utf8', env: otherEnv })
        if (oprep.some(p => p.status !== 0) || probe.status !== 0 || !String(probe.stdout).split('\0').includes('notes.txt')) {
          selfUnrun = `다른 저장소를 가리키는 GIT_DIR 이 git 의 답을 바꾸지 않는다 — git exit ${[...oprep, probe].map(p => p.status).join(',')}`
        } else {
          const before = process.env.GIT_DIR
          let have = [], msg = ''
          process.env.GIT_DIR = otherEnv.GIT_DIR
          try {
            have = pinnedFiles(wb)
            try { verifyPinned(wb) } catch (e) { msg = e.message }
          } finally { if (before === undefined) delete process.env.GIT_DIR; else process.env.GIT_DIR = before }
          check(`pinned-sums-git-env-other-repo — 부르는 쪽 GIT_DIR 이 다른 저장소를 가리켜도 그 저장소만 무시하는 notes.txt 를 견준다(${SUMS_NAME} 에 없는 파일 하나)`,
            have.includes('notes.txt') && msg.includes(`${SUMS_NAME} 와 고정본 폴더의 파일 집합이 다르다 — 목록에 없는 파일 1(notes.txt)`),
            `견준 파일에 notes.txt ${have.includes('notes.txt')} · ${msg || '던지지 않았다'}`)
          // 기준 SHA 선택자의 git show 도 같다 — 부르는 쪽 GIT_DIR 이 다른 저장소를 가리켜도 gitRoot 의 이력에서 읽는다. 선택자는 이 작업 트리
          //   인덱스의 트리 SHA(write-tree — 커밋 · 신원 · 서명 · 훅이 필요 없다)다. 전제: gitEnv 로는 그 트리에서 읽히고 다른 저장소로는 읽히지 않는다
          const wt = git('write-tree'), treeSha = String(wt.stdout || '').trim()
          const shows = env => spawnSync('git', ['-C', gitTree, 'show', `${treeSha}:workflows/plan-lean2.js`], { encoding: 'utf8', env }).status
          const pre2 = [wt.status, shows(gitEnv), shows(otherEnv)]
          if (!treeSha || pre2[0] !== 0 || pre2[1] !== 0 || pre2[2] === 0) {
            selfUnrun = `다른 저장소를 가리키는 GIT_DIR 이 기준 SHA 의 git show 를 바꾸지 않는다 — write-tree · show · 다른 저장소 show exit ${pre2.join(',')}(기대 0,0,≠0)`
          } else {
            let got = null, err = ''
            withEnv({ GIT_DIR: otherEnv.GIT_DIR, FZ_PINNED_SELFTEST_SHA: treeSha }, () => {
              try {
                got = resolveBase('plan-lean2', box, Object.assign({}, BASE_SEL, { tree: 'FZ_PINNED_SELFTEST_NO_TREE', sha: 'FZ_PINNED_SELFTEST_SHA', gitRoot: gitTree }))
              } catch (e) { err = e.message.split('\n')[0] }
            })
            const same = !!got && fs.readFileSync(got.file, 'utf8') === fs.readFileSync(path.join(gitTree, 'workflows', 'plan-lean2.js'), 'utf8')
            check('pinned-sums-git-env-sha-selector — 부르는 쪽 GIT_DIR 이 다른 저장소를 가리켜도 기준 SHA 선택자의 git show 는 gitRoot 의 이력에서 읽는다',
              !!got && got.from === `git ${treeSha}(FZ_PINNED_SELFTEST_SHA)` && same, got ? `출처 ${got.from} · 원문 같음 ${same}` : err)
          }
        }
        // 명령 범위 설정(GIT_CONFIG_PARAMETERS · GIT_CONFIG_COUNT/KEY/VALUE)은 저장소 로컬 core.excludesFile(여기서는 /dev/null)을 이긴다 —
        //   그 설정으로 무시 규칙을 넓혀 notes.txt 를 무시하게 해도 견주는 집합은 그대로다. 전제: 그 env 를 물려받은 git 은 notes.txt 를 무시된 파일로 낸다
        const injIgnore = path.join(box, 'inject-ignore')
        fs.writeFileSync(injIgnore, 'notes.txt\n')
        const injected = {
          parameters: { GIT_CONFIG_PARAMETERS: `'core.excludesFile=${injIgnore}'` },
          count: { GIT_CONFIG_COUNT: '1', GIT_CONFIG_KEY_0: 'core.excludesFile', GIT_CONFIG_VALUE_0: injIgnore },
        }
        for (const [axis, vars] of Object.entries(injected)) {
          const probe = lsIgnored(wb, Object.assign({}, gitEnv, vars))
          if (!lists(probe, 'notes.txt')) {
            selfUnrun = `명령 범위 설정(${axis})이 git 의 답을 바꾸지 않는다 — git exit ${probe.status}`
            continue
          }
          let have = [], msg = ''
          withEnv(vars, () => {
            have = pinnedFiles(wb)
            try { verifyPinned(wb) } catch (e) { msg = e.message }
          })
          check(`pinned-sums-git-config-inject-${axis} — 부르는 쪽 명령 범위 설정(${Object.keys(vars).join(' · ')})이 무시 규칙을 넓혀도 notes.txt 를 견준다(${SUMS_NAME} 에 없는 파일 하나)`,
            have.includes('notes.txt') && msg.includes(`${SUMS_NAME} 와 고정본 폴더의 파일 집합이 다르다 — 목록에 없는 파일 1(notes.txt)`),
            `견준 파일에 notes.txt ${have.includes('notes.txt')} · ${msg || '던지지 않았다'}`)
        }
        // 전역 설정 경로(GIT_CONFIG_GLOBAL)는 로컬 core.excludesFile 이 없는 저장소에서 무시 규칙을 넓힌다 — 위 작업 트리는 로컬 값이 이겨 전제가
        //   서지 않으므로, 작은 저장소(로컬 값 없음 · HOME · XDG_CONFIG_HOME = 빈 폴더 · 시스템 설정 끔 — 사용자 설정이 셀을 가르지 않게)에서
        //   pinnedFiles 만 본다. 전제: 그 이름을 건 git 은 notes.txt 를 무시하고 뺀 git 은 무시하지 않는다
        const gTop = path.join(box, 'git-global'), gPin = path.join(gTop, 'pin'), gHome = path.join(box, 'git-global-home'), gCfg = path.join(box, 'global.cfg')
        fs.mkdirSync(gPin, { recursive: true })
        fs.mkdirSync(gHome)
        for (const f of ['keep.txt', 'notes.txt']) fs.writeFileSync(path.join(gPin, f), '메모\n')
        fs.writeFileSync(gCfg, `[core]\n\texcludesFile = ${injIgnore}\n`)
        const quiet = { HOME: gHome, XDG_CONFIG_HOME: gHome, GIT_CONFIG_NOSYSTEM: '1' }
        const gPlain = Object.assign({}, gitEnv, quiet)
        delete gPlain.GIT_CONFIG_GLOBAL
        const gInit = spawnSync('git', ['-C', gTop, 'init', '-q'], { encoding: 'utf8', env: gPlain })
        const gOn = lsIgnored(gPin, Object.assign({}, gPlain, { GIT_CONFIG_GLOBAL: gCfg })), gOff = lsIgnored(gPin, gPlain)
        if (gInit.status !== 0 || !lists(gOn, 'notes.txt') || gOff.status !== 0 || lists(gOff, 'notes.txt')) {
          selfUnrun = `전역 설정 경로가 git 의 답을 바꾸지 않는다 — git exit ${[gInit, gOn, gOff].map(p => p.status).join(',')} · notes.txt 무시 ${lists(gOn, 'notes.txt')},${lists(gOff, 'notes.txt')}(기대 true,false)`
        } else {
          const have = withEnv(Object.assign({}, quiet, { GIT_CONFIG_GLOBAL: gCfg }), () => pinnedFiles(gPin))
          check('pinned-sums-git-config-inject-global — 부르는 쪽 GIT_CONFIG_GLOBAL 이 로컬 무시 설정이 없는 저장소의 무시 규칙을 넓혀도 notes.txt 를 견준다',
            have.includes('notes.txt'), `견준 파일 ${JSON.stringify(have)}`)
        }
        fs.rmSync(path.join(wb, 'notes.txt'))
        // 격자(git-env-grid · JS 헬퍼 × 무시 조회 · 기준 SHA git show) — 받은 env 의 이름만 적는 가짜 git 을 PATH 앞에 두고 아래 이름을 하나씩
        //   걸면 두 호출 모두 그 이름을 git 에 넘기지 않는다. 저장소 위치 env 몇은 git 의 답을 바꾸지 않아 답으로는 가를 수 없다 — 그래서 git 이
        //   받은 env 를 본다. 이름은 GIT_REPO_ENV 를 읽지 않고 따로 적는다(상수가 줄면 이 격자가 잡는다).
        //   전제: 칸마다 가짜 git 이 무시 조회(ls-files)와 git show 를 받고 모든 호출에 지우지 않는 대조 변수가 닿는다
        const gridNames = ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR',
          'GIT_NAMESPACE', 'GIT_PREFIX', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0', 'GIT_CONFIG_GLOBAL']
        const fakeDir = path.join(box, 'git-env-grid'), callLog = path.join(fakeDir, 'calls.log'), gridProbe = 'FZ_GIT_ENV_GRID_PROBE'
        const shq = s => `'${s.replace(/'/g, `'\\''`)}'`
        fs.mkdirSync(fakeDir)
        fs.writeFileSync(path.join(fakeDir, 'git'), '#!/bin/sh\nseen="$3"\n'
          + [...gridNames, gridProbe].map(n => `[ -z "\${${n}+x}" ] || seen="$seen ${n}"\n`).join('') + `echo "$seen" >> ${shq(callLog)}\n`, { mode: 0o755 })
        const gridPin = path.join(box, 'pin-grid')
        copyPinned(gridPin)   // 가짜 git 은 무시 집합을 비운다 — 무시된 부산물이 없는 사본을 견주고, PATH 를 바꾸기 전에 만든다
        const leaked = [], gridBad = []
        withEnv({ PATH: `${fakeDir}${path.delimiter}${process.env.PATH || ''}`, [gridProbe]: '1', FZ_PINNED_SELFTEST_SHA: 'grid' }, () => {
          for (const name of gridNames) {
            fs.writeFileSync(callLog, '')
            let err = ''
            withEnv({ [name]: path.join(box, 'git-elsewhere') }, () => {
              try {
                pinnedFiles(gridPin)
                resolveBase('plan-lean2', box, Object.assign({}, BASE_SEL, { tree: 'FZ_PINNED_SELFTEST_NO_TREE', sha: 'FZ_PINNED_SELFTEST_SHA', gitRoot: gitTree, pinnedRoot: gridPin }))
              } catch (e) { err = e.message.split('\n')[0] }
            })
            const calls = fs.readFileSync(callLog, 'utf8').split('\n').filter(Boolean).map(l => l.split(' ')), kinds = calls.map(c => c[0])
            if (err || !kinds.includes('ls-files') || !kinds.includes('show') || !calls.every(c => c.includes(gridProbe))) {
              gridBad.push(`${name} 칸 — ${err || calls.map(c => c[0]).join(',')}`)
              continue
            }
            for (const c of calls) if (c.includes(name)) leaked.push(`${c[0]}:${name}`)
          }
        })
        if (gridBad.length) selfUnrun = `가짜 git 이 두 호출과 대조 변수를 받지 못했다(${gridBad[0]}) — 격자가 env 전달을 가를 수 없다`
        else {
          check(`pinned-sums-git-env-grid — 저장소 위치 env 여덟 · 명령 범위 설정 · 개수/키/값 묶음 · 전역 설정 경로를 하나씩 걸어도 무시 조회 · 기준 SHA git show 가 그 이름을 git 에 넘기지 않는다(${gridNames.length * 2}칸)`,
            leaked.length === 0, `git 에 닿은 이름 ${leaked.join(' · ')}`)
        }
        // 통째로 무시된 폴더는 읽을 수 없어도 내려가지 않는다 — 고정본 폴더 안 cache/ 를 info/exclude 로 무시하고 권한을 0 으로 두어도 두 러너가
        //   돈다. 대조: 무시되지 않은 폴더(locked/)를 읽을 수 없으면 두 러너 UNRUN(exit 2)이다. 전제: check-ignore(0 · 1) · 실제로 읽을 수 없다(root 면
        //   읽힌다) · ls-files --directory 가 무시된 폴더만 `<이름>/` 한 줄로 낸다. 권한 · 폴더 · exclude 줄은 셀 끝에 되돌린다(뒤 셀과 바깥
        //   fs.rmSync 가 권한 0 폴더에서 깨지지 않게)
        const excl = path.join(gitTree, '.git', 'info', 'exclude')
        const unreadableDir = (name, ignored) => {
          const dir = path.join(wb, name)
          fs.mkdirSync(dir)
          fs.writeFileSync(path.join(dir, 'blob'), 'x\n')
          if (ignored) fs.appendFileSync(excl, `tests/fixtures/workflow-base/${name}/\n`)
          fs.chmodSync(dir, 0)
          try {
            const ig = git('check-ignore', '-q', `tests/fixtures/workflow-base/${name}/`).status
            let denied = ''
            try { fs.readdirSync(dir) } catch (e) { denied = e.code || 'error' }
            const folded = lists(lsIgnored(wb, gitEnv, '--directory'), `${name}/`)
            if (ig !== (ignored ? 0 : 1) || denied !== 'EACCES' || folded !== ignored) {
              return { pre: `check-ignore ${ig}(기대 ${ignored ? 0 : 1}) · readdir ${denied || '읽힘'}(기대 EACCES — root 면 읽힌다) · --directory 의 ${name}/ ${folded}(기대 ${ignored})` }
            }
            return { ks: kids() }
          } finally {
            fs.chmodSync(dir, 0o755)
            fs.rmSync(dir, { recursive: true, force: true })
            fs.writeFileSync(excl, '.DS_Store\n')
          }
        }
        const ud = unreadableDir('cache', true)
        if (ud.pre) selfUnrun = `무시된 읽을 수 없는 폴더 셀의 전제가 서지 않는다 — ${ud.pre}`
        else {
          check('pinned-sums-git-ignored-unreadable-dir — 통째로 무시된 폴더(cache/)는 읽을 수 없어도 내려가지 않는다: 두 러너가 돈다(exit 0)',
            ud.ks.every(k => k.status === 0), said(ud.ks))
        }
        const ul = unreadableDir('locked', false)
        if (ul.pre) selfUnrun = `무시되지 않은 읽을 수 없는 폴더 셀의 전제가 서지 않는다 — ${ul.pre}`
        else {
          check('pinned-sums-git-unignored-unreadable-dir — 무시되지 않은 폴더(locked/)를 읽을 수 없으면 두 러너 UNRUN(exit 2)',
            ul.ks.every(k => k.status === 2 && /^UNRUN /m.test(String(k.stdout || ''))), said(ul.ks))
        }
        const forced = git('add', '-f', 'tests/fixtures/workflow-base/effort-arg/.DS_Store')
        ks = kids()
        check(`pinned-sums-git-tracked-ignored — 무시 규칙에 걸려도 추적하는 파일은 목록에 없는 파일이다: 두 러너 UNRUN(exit 2 · 사유 = ${SUMS_NAME} 에 없는 effort-arg/.DS_Store 하나)`,
          forced.status === 0 && onlyExtra(ks, 'effort-arg/.DS_Store'), `git add -f exit ${forced.status} · ${said(ks)}`)
      }
    } finally { fs.rmSync(box, { recursive: true, force: true }) }
  }
  if (selfUnrun) {
    console.log(`UNRUN  ${selfUnrun} (⛔ 통과 아님)`)
    process.exit(2)
  }
  const asked = argv.flatMap((a, i) => (a === '--option' ? [argv[i + 1]] : []))
  const names = argv.includes('--all-rb-options') || asked.length === 0 ? Object.keys(OPTIONS) : asked
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-default-off-'))
  const rolledBack = new Set()   // 롤백 검사는 (워크플로 · 경로)마다 한 번
  const typoChecked = new Set()  // 값 검증은 (옵션 · 워크플로)마다 한 번
  let bases
  const env = process.env   // 옛 이름은 있는지만 본다 — 그 값은 기준에 쓰지 않는다(조용한 기본값 복귀만 알린다)
  if (!env.FZ_REGRESSION_BASE_SHA && !env.FZ_REGRESSION_BASE_TREE && (env.FZ_BASE_SHA || env.FZ_BASE_TREE)) console.log('WARN: FZ_BASE_* 는 무시된다 — FZ_REGRESSION_BASE_*')
  try {
    const wfs = [...new Set(names.flatMap(n => (OPTIONS[n] ? OPTIONS[n].workflows : [])))]
    try {
      bases = Object.fromEntries(wfs.map(wf => [wf, baseFile(wf, tmp)]))
    } catch (e) {
      console.log(`UNRUN  기준 소스를 얻지 못했다 — ${e.message.split('\n')[0]} (⛔ 통과 아님)`)
      process.exitCode = 2   // ⛔ process.exit 는 바깥 finally(임시 폴더 정리)를 건너뛴다(F-406) — 돌아가서 정리한 뒤 2 로 끝난다
      return
    }
    for (const name of names) {
      const opt = OPTIONS[name]
      if (!opt) { check(`옵션 ${name} 이 레지스트리에 있다`, false, `등록된 옵션: ${Object.keys(OPTIONS).join(', ')}`); continue }
      for (const wf of opt.workflows) {
        const work = path.join(ROOT, 'workflows', `${wf}.js`)
        for (const sc of SCENARIOS[wf]) {
          const base = intended(wf, await callsOf(bases[wf].file, wf, sc, {}))
          const unset = await callsOf(work, wf, sc, {})
          const off = await callsOf(work, wf, sc, opt.off)
          const on = await callsOf(work, wf, sc, opt.on)
          const tag = `${name} · ${wf} · ${sc.name}`
          const reaches = !opt.applies || opt.applies(sc)
          if ((opt.defaultOn || []).includes(wf)) {
            // 기본 on — 같은 워크플로의 다른 기본 on 옵션도 켜져 있어, 이 옵션 하나만 끈 결과는 기준이 아니다.
            //   그래서 옵션마다는 '미지정 == 켬' 과 '끔 != 켬'(배선)을 보고, 롤백(기본 on 을 전부 끔 == 기준)은 경로마다 1회 아래에서 본다
            check(`${tag}: 미지정 == ${JSON.stringify(opt.on)}(기본 on) — 콜 ${on.length}개`, on.length > 0 && firstDiff(unset, on) === null, firstDiff(unset, on) || '콜 0개')
            if (reaches) check(`${tag}: ${JSON.stringify(opt.off)} != 켬(옵션이 배선돼 있다)`, firstDiff(off, on) !== null, '꺼도 콜 입력이 같다 — 헛돌이')
            else check(`${tag}: ${JSON.stringify(opt.off)} == 켬(이 경로에는 옵션이 닿지 않는다)`, firstDiff(off, on) === null, firstDiff(off, on))
            const key = `${wf}|${sc.name}`
            if (!rolledBack.has(key)) {
              rolledBack.add(key)
              const allOff = Object.assign({}, ...Object.values(OPTIONS).filter(o => (o.defaultOn || []).includes(wf)).map(o => o.off))
              const back = await callsOf(work, wf, sc, allOff)
              check(`${wf} · ${sc.name}: 기본 on 옵션을 모두 끔 ${JSON.stringify(allOff)} == 기준(${bases[wf].from} · 롤백 경로)`, firstDiff(back, base) === null, firstDiff(back, base))
            }
            if (!typoChecked.has(`${name}|${wf}`)) {
              typoChecked.add(`${name}|${wf}`)
              // 끄는 값을 잘못 쓰면 조용히 기본(on)으로 읽히지 않는다 — fallback(args invalid) · 콜 0 (리뷰 F8 — 옛 판은 오타를 on 으로 읽었다)
              const v = Object.values(opt.on)[0]
              const typo = { [name]: typeof v === 'boolean' ? 'off' : String(v).toUpperCase() }
              const table = responses(wf, sc.fire, sc.quiet), seen = []
              const r = (await run(work, { args: Object.assign({}, BASE_ARGS, sc.args, typo),
                responder: (p, o) => { seen.push(o.label); return table[o.label] ? JSON.parse(JSON.stringify(table[o.label])) : null } })).result
              check(`${name} · ${wf}: 모르는 값 ${JSON.stringify(typo)} → fallback(args invalid) · 콜 0`,
                r.mode === 'fallback' && /args invalid/.test(r.reason || '') && seen.length === 0, JSON.stringify({ mode: r.mode, reason: r.reason, calls: seen.length }))
              if (typeof v === 'boolean') {
                const strOff = await callsOf(work, wf, sc, { [name]: 'false' })
                check(`${name} · ${wf}: 문자열 'false' == false(값 검증이 문자열 형식을 막지 않는다)`, strOff.length > 0 && firstDiff(strOff, off) === null, firstDiff(strOff, off) || '콜 0개')
              }
            }
          } else {
            check(`${tag}: 미지정 == 기준(${bases[wf].from}) — 콜 ${base.length}개`, base.length > 0 && firstDiff(unset, base) === null, firstDiff(unset, base) || '콜 0개')
            check(`${tag}: ${JSON.stringify(opt.off)} == 기준`, firstDiff(off, base) === null, firstDiff(off, base))
            if (opt.structural) {
              check(`${tag}: ${JSON.stringify(opt.on)} 은 콜 구성을 바꿀 수 있다 — 켠 동작은 ${opt.structural} 가 본다(여기서는 실행만)`, on.length > 0, '켜니 콜 0개')
              continue
            }
            if (reaches) check(`${tag}: ${JSON.stringify(opt.on)} != 기준(옵션이 배선돼 있다)`, firstDiff(on, base) !== null, '켜도 콜 입력이 같다 — 헛돌이')
            else check(`${tag}: ${JSON.stringify(opt.on)} == 기준(이 경로에는 옵션이 닿지 않는다)`, firstDiff(on, base) === null, firstDiff(on, base))
          }
          check(`${tag}: ${JSON.stringify(opt.on)} 의 콜 구성(label 다중집합) == 기준`, on.length > 0 && labels(on) === labels(base), `켬 ${labels(on)} · 기준 ${labels(base)}`)
        }
      }
    }
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }
  console.log(`\n기본값 회귀 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (옵션 ${names.join(', ')})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
