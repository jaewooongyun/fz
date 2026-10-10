// stage 규칙을 실제 워크플로 파일로 시험한다 (F-335 ⑯) — `scripts/fz_wf_metrics.py` 의 STAGE_RULES(첫 일치 부분 문자열)에
// `workflows/*.js` 프롬프트의 **실제** `[역할]` 문구를 먹여, 워크플로마다 기대한 stage 라벨 집합이 정확히 나오는지 본다.
//
// ⛔ 왜 파일을 읽는가: 계측기 self-test(fz_wf_metrics.py ⑭)는 문구를 **복사해** 시험한다 — 워크플로가 역할 문구를 바꾸면
//    복사본은 그대로 통과하고 실제 run 은 stage '?' 가 되어 완주 오라클(ab_ledger.REQUIRED_STAGES)이 조용히 깨진다.
// ⛔ 계측기 밖에 둔다 — 계측기 파일을 고치면 instrument_sha 가 바뀌어 채점 행이 낡는다. 여기서는 읽기만 한다.
//
// 판정(워크플로마다):
//   ① [역할] 문구를 1개 이상 찾는다(0 = 추출 실패 또는 문구 삭제 — 통과로 읽지 않는다)
//   ② stage 워크플로(EXPECTED): 모든 문구가 라벨을 받고('?' 0), 라벨 집합이 기대 집합과 **정확히** 같다
//      — 빠짐 = 문구가 규칙에서 떨어졌다 · 더함 = 규칙 순서가 다른 라벨을 붙였다(예: 교차 콜이 Stage 1 로 읽힘)
//   ③ 라벨 없는 워크플로(UNLABELED): 모든 문구가 '?' — 라벨 공간이 섞이면 임계 경로가 이중 합산된다
//   ④ 분류되지 않은 워크플로 파일이 없다(새 워크플로는 위 두 표 중 하나에 넣는다)
//   ⑤ 완주 오라클: REQUIRED_STAGES 의 스킬마다 그 스킬 SKILL.md 가 배선한 워크플로가 필수 stage 를 모두 낸다
// 문구 추출은 계측기와 같은 규칙이다 — `[역할]` 뒤 공백을 건너 줄 끝(소스의 `\n` · `${` · 백틱)까지, 앞 60자.
// exit: 0 전건 통과 · 1 불일치 · 2 실행 불가(UNRUN — python3 · 계측기 적재 실패)
'use strict'
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')

const ROOT = path.join(__dirname, '..', '..')
const WF = path.join(ROOT, 'workflows')
const EXPECTED = {
  'plan-lean2.js': ['L1-full', 'L1-edge', 'L1-impact', 'L2-merge'],
  'plan-lean.js': ['L1-full', 'L1-edge', 'L2-merge'],
  'review-live.js': ['R1-arch', 'R1-quality', 'R2-arch', 'R2-quality', 'R3-counter'],
  'peer-review.js': ['R1-arch', 'R1-quality', 'R1-correct', 'R2-arch', 'R2-quality', 'R3-counter'],
  'plan-collaborative.js': ['S0', 'S0-reb', 'S0-fin', 'S1', 'S2-impact', 'S2-edge', 'S2-arch', 'S3-imp', 'S3-edge', 'S4', 'S5'],
}
const UNLABELED = ['code-pair.js', 'discover-adversarial.js', 'search-cross-verify.js']
// 완주 오라클의 스킬 → 그 스킬이 기본으로 부르는 워크플로(SKILL.md 에 `workflows/<파일>` 로 적혀 있어야 한다)
const SKILL_WF = { 'fz-plan': 'plan-lean2.js', 'fz-review': 'review-live.js', 'fz-peer-review': 'peer-review.js' }

let fail = 0
const ran = []
function check(cell, ok, what, got) {
  if (!ran.includes(cell)) ran.push(cell)
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${cell}: ${what}${ok ? '' : ` — ${got}`}`)
  if (!ok) fail += 1
}
function unrun(msg) { console.log(`UNRUN  ${msg}`); process.exit(2) }

function roles(file) {
  const out = []
  for (const line of fs.readFileSync(path.join(WF, file), 'utf8').split('\n')) {
    if (/^\s*(\/\/|\*)/.test(line)) continue          // 주석의 [역할] 은 프롬프트가 아니다
    const re = /\[역할\]\s*/g
    let m
    while ((m = re.exec(line))) {
      const rest = line.slice(m.index + m[0].length)
      const end = rest.search(/\\n|\$\{|`/)
      out.push((end < 0 ? rest : rest.slice(0, end)).slice(0, 60))
    }
  }
  return out
}

const files = fs.readdirSync(WF).filter(f => f.endsWith('.js')).sort()
if (!files.length) unrun(`workflows/*.js 0건 — ${WF}`)
const byFile = Object.fromEntries(files.map(f => [f, roles(f)]))

// 계측기 판정을 그대로 쓴다 — 규칙을 여기 복사하면 이 시험이 지키려는 동기화가 다시 끊긴다
const PY = [
  'import json, sys',
  'sys.dont_write_bytecode = True',
  'sys.path.insert(0, sys.argv[1])',
  'import fz_wf_metrics as m, ab_ledger as a',
  'roles = json.load(sys.stdin)',
  'print(json.dumps({"labels": {f: [m._stage_of(r) for r in rs] for f, rs in roles.items()},',
  '                  "required": {k: list(v) for k, v in a.REQUIRED_STAGES.items()}}))',
].join('\n')
let judged
try {
  judged = JSON.parse(execFileSync('python3', ['-B', '-c', PY, path.join(ROOT, 'scripts')], {
    input: JSON.stringify(byFile), env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }, encoding: 'utf8',
  }))
} catch (e) {
  unrun(`계측기 판정을 부르지 못했다 — ${String(e.message).split('\n')[0]}`)
}

for (const f of files) {
  const rs = byFile[f]
  const labels = judged.labels[f]
  check(f, rs.length > 0, '[역할] 문구 1개 이상', '0개 — 추출 규칙 또는 워크플로 문구가 바뀌었다')
  if (EXPECTED[f]) {
    const lost = rs.filter((r, i) => labels[i] === '?')
    check(f, !lost.length, `모든 [역할] 이 stage 라벨을 받는다(${rs.length}개)`, `'?' ${lost.map(r => JSON.stringify(r)).join(' · ')}`)
    const got = [...new Set(labels.filter(l => l !== '?'))].sort()
    const want = [...EXPECTED[f]].sort()
    const miss = want.filter(l => !got.includes(l))
    const extra = got.filter(l => !want.includes(l))
    check(f, !miss.length && !extra.length, `라벨 집합 = {${want.join(', ')}}`, `빠짐 [${miss}] · 더함 [${extra}] · 문구→라벨 ${rs.map((r, i) => `${r.slice(0, 16)}…→${labels[i]}`).join(' | ')}`)
  } else if (UNLABELED.includes(f)) {
    const leaked = rs.map((r, i) => [r, labels[i]]).filter(([, l]) => l !== '?')
    check(f, !leaked.length, `모든 [역할] 이 '?'(stage 라벨 공간 밖)`, leaked.map(([r, l]) => `${r.slice(0, 16)}…→${l}`).join(' | '))
  } else {
    check(f, false, '분류됨', 'EXPECTED · UNLABELED 어디에도 없다 — 새 워크플로면 둘 중 하나에 넣는다')
  }
}
for (const f of [...Object.keys(EXPECTED), ...UNLABELED]) {
  if (!files.includes(f)) check(f, false, '분류표의 워크플로가 실재한다', `workflows/${f} 없음 — 분류표를 고친다`)
}

const required = judged.required
check('required-stages', Object.keys(required).length > 0, 'REQUIRED_STAGES 를 읽었다', '0개')
for (const [skill, need] of Object.entries(required)) {
  const wf = SKILL_WF[skill]
  if (!wf) { check(`required:${skill}`, false, '스킬 → 워크플로 대응이 있다', 'SKILL_WF 에 없다'); continue }
  const skillMd = path.join(ROOT, 'skills', skill, 'SKILL.md')
  const wired = fs.existsSync(skillMd) && fs.readFileSync(skillMd, 'utf8').includes(`workflows/${wf}`)
  check(`required:${skill}`, wired, `skills/${skill}/SKILL.md 가 workflows/${wf} 를 부른다`, '배선 문자열 없음')
  const have = new Set((judged.labels[wf] || []).filter(l => l !== '?'))
  const miss = need.filter(l => !have.has(l))
  check(`required:${skill}`, !miss.length, `${wf} 가 필수 stage {${need.join(', ')}} 를 모두 낸다`, `빠짐 [${miss}]`)
}

// 기대 셀(F-408) — 워크플로 파일 전부 + REQUIRED_STAGES 스킬마다 1셀 + 읽기 셀. check 를 거치지 않는다(거치면 그 이름이 ran 에 들어간다)
const expCells = [...new Set([...files, ...Object.keys(EXPECTED), ...UNLABELED, 'required-stages', ...Object.keys(required).map(s => `required:${s}`)])]
const missCells = expCells.filter(c => !ran.includes(c))
const extraCells = ran.filter(c => !expCells.includes(c))
if (missCells.length || extraCells.length) {
  console.log(`FAIL  기대 셀 집합 — 빠짐 [${missCells}] · 더함 [${extraCells}]`)
  fail += 1
}
console.log()
if (fail) {
  console.log(`STAGE_RULES_REAL_FAIL fail=${fail} ran=${ran.length}(${ran.join(' ')})`)
  process.exit(1)
}
console.log(`STAGE_RULES_REAL_OK ran=${ran.length}(${ran.join(' ')})`)
