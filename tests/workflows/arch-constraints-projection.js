// archConstraints 호환 투영 (S15) — project-rules 레코드 → check_project_rules.py --project-arch → plan-lean2 프롬프트.
//
// ⛔ 투영은 파이썬 한 곳에만 있다 — 여기서 다시 구현하지 않고 실제 진입점(--project-arch)을 부른다.
//    두 곳에 두면 한쪽만 바뀌어도 테스트는 통과하고 워커가 받는 제약이 갈린다.
// ⛔ 워크플로를 통째로 가짜 런타임(tests/lib/wf_harness.js)에서 돌려 워커가 **실제로 받는** [아키텍처 제약] 줄을 본다.
//    워커는 전부 null(죽은 워커)로 돌려준다 — 첫 프롬프트만 있으면 되고, 그 뒤 fallback 반환은 판정 대상이 아니다.
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const { execFileSync } = require('child_process')
const { run } = require('../lib/wf_harness')

const ROOT = path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows', 'plan-lean2.js')
const CHECKER = path.join(ROOT, 'scripts', 'check_project_rules.py')
const ARGS = { requirement: '합성 요구', codeContextPath: '/tmp/code-context.md' }
const ARCH_KEYS = ['architecturePattern', 'uiStack', 'dependencyDirection', 'naming', 'conflicts']

// 6축 중 placement·conventions 는 plan 워크플로가 읽지 않는다 — 투영에서 빠져야 한다(값도, 그 축의 상충도)
const RULES = {
  schemaVersion: 1,
  axes: {
    architecturePattern: 'RIBs + Clean Architecture', uiStack: null,
    dependencyDirection: 'Interactor → UseCase → Repository → Network', naming: null,
    placement: 'PLACEMENT-ONLY-VALUE', conventions: 'CONVENTIONS-ONLY-VALUE',
  },
  rules: [],
  conflicts: [
    { axis: 'naming', claim_a: '…DTO', claim_b: '…Response', sources: [{ file: 'CLAUDE.md', line: 5, quote: '`…DTO`' }, { file: 'AGENTS.md', line: 5, quote: '`…Response`' }] },
    { axis: 'placement', claim_a: 'PLACEMENT-CONFLICT-A', claim_b: 'b', sources: [] },
  ],
  gaps: ['uiStack'],
}

let fail = 0
function check(name, cond, got) {
  console.log(`${cond ? 'PASS' : 'FAIL'}  ${name}${cond ? '' : ` — ${got}`}`)
  if (!cond) fail += 1
}

async function firstPrompt(args) {
  const prompts = {}
  await run(WF, { args, responder: (prompt, opts) => { prompts[opts.label] = prompts[opts.label] || prompt; return null } })
  return prompts['lean2-full'] || ''
}

;(async () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'fz-arch-proj-'))
  const rulesPath = path.join(tmp, 'rules.json')
  fs.writeFileSync(rulesPath, JSON.stringify(RULES))
  let arch
  try {
    arch = JSON.parse(execFileSync('python3', [CHECKER, '--project-arch', rulesPath], { encoding: 'utf8' }))
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }

  check('투영 키 = 4축 + conflicts (순서 포함)', JSON.stringify(Object.keys(arch)) === JSON.stringify(ARCH_KEYS), JSON.stringify(Object.keys(arch)))
  check('투영 conflicts 는 4축 것만(placement 상충 제외)', JSON.stringify(arch.conflicts.map(c => c.axis)) === '["naming"]', JSON.stringify(arch.conflicts))
  check('상충 축·미확인 축은 null 그대로', arch.naming === null && arch.uiStack === null, `${arch.naming} ${arch.uiStack}`)

  const withArch = await firstPrompt(Object.assign({}, ARGS, { archConstraints: arch }))
  check('워커 프롬프트에 [아키텍처 제약] 줄이 투영 그대로 들어간다', withArch.includes(`[아키텍처 제약] ${JSON.stringify(arch)}`),
    withArch.split('\n').find(l => l.startsWith('[아키텍처 제약]')) || '(줄 없음)')
  check('placement·conventions 값과 그 상충은 프롬프트에 없다',
    !/PLACEMENT-ONLY-VALUE|CONVENTIONS-ONLY-VALUE|PLACEMENT-CONFLICT-A/.test(withArch), '6축 전용 값이 새어 들어갔다')

  // ⛔ 라벨 문자열이 아니라 **제약 줄**을 본다 — OVERRIDE 지시문이 원래 "[아키텍처 제약]" 라벨 이름을 부른다
  const LINE = /^\[아키텍처 제약\] \{/m
  check('투영을 넘기면 제약 줄이 정확히 하나다', (withArch.match(new RegExp(LINE.source, 'gm')) || []).length === 1, '줄 수가 1 이 아니다')
  const without = await firstPrompt(ARGS)
  check('archConstraints 미전달 → 제약 줄 없음(워커 프롬프트 무변화)', without !== '' && !LINE.test(without),
    without === '' ? '프롬프트를 못 잡았다' : without.split('\n').find(l => LINE.test(l)))

  console.log(`\narchConstraints 투영 ${fail ? '실패 ' + fail + '건' : '전건 통과'} (대상 ${path.relative(process.cwd(), WF) || WF})`)
  process.exit(fail ? 1 : 0)
})().catch(e => { console.log(`FAIL  실행 오류 — ${e.message}`); process.exit(1) })
