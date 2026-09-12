#!/usr/bin/env node
// scripts/check_wf_text.js — 배선 검사기(정적). "그 자리에 그 계약이 있는가"만 본다.
//
// ⛔ 이 스크립트가 재는 것과 아닌 것.
//   재는 것: 지시·계약 문구가 **지정된 자리**에 있는가 · 섹션 안 순서 · 스키마 description 의
//            길이 지침 · 반환 리터럴의 키 · integrateBrief 의 id 보존과 출력 크기.
//   ⛔ 재지 못하는 것: 그 배선이 **런타임에 효과를 냈는가**(SO 재시도 0 · n_workflow=1 ·
//      프롬프트 토큰 감소). 그것은 `fz_wf_metrics.py` 가 실행 기록에서 잰다.
//   근거: plan-final S1~S5a — 게이트를 "정적 배선(command)" 과 "동작 검증(manual/지표)" 으로
//         분리한다. 이전 판은 `grep -c '문구'` 하나로 둘 다 주장했고 measurement_fit 이 partial 이었다
//         (GPT verify #8 · verify-gates revise 9/11).
//
// ⛔ 토큰은 모드·대상별로 다르다 — 한 모드가 모든 토큰을 인쇄하면 다른 게이트의 오라클을
//    대신 통과시킨다. 그래서 `--section-has` 는 섹션 제목으로 토큰을 **조회**하고, 미등록
//    섹션은 실패한다(조용한 통과 금지).
'use strict'
const fs = require('fs')

const SECTION_TOKENS = {
  'Phase 3: Feedback Integration': 'FINAL_RULE_OK',   // S9a — plan-final 완전 재생성 규칙
  'Phase 2: Plan Validation': 'PARALLEL_OK',          // S9b — verify∥verify-gates 병렬 계약
}

function die(msg) { console.error(`FAIL: ${msg}`); process.exit(1) }
function read(p) { try { return fs.readFileSync(p, 'utf8') } catch (e) { die(`읽을 수 없다: ${p} (${e.code})`) } }

// 마크다운 섹션 추출 — 헤딩 줄부터 같은 레벨 이상의 다음 헤딩 직전까지.
function mdSection(text, title) {
  const lines = text.split('\n')
  let start = -1, level = 0
  for (let i = 0; i < lines.length; i += 1) {
    const m = lines[i].match(/^(#{1,6})\s+(.*)$/)
    if (m && m[2].trim().includes(title)) { start = i; level = m[1].length; break }
  }
  if (start < 0) return null
  let end = lines.length
  for (let i = start + 1; i < lines.length; i += 1) {
    const m = lines[i].match(/^(#{1,6})\s+/)
    if (m && m[1].length <= level) { end = i; break }
  }
  return lines.slice(start, end).join('\n')
}

// 번호 절차 블록 추출 — `N. ` 로 시작하는 줄부터 다음 최상위 번호 직전까지 (하위 들여쓰기 포함).
function numberedItem(text, startsWith) {
  const lines = text.split('\n')
  let start = -1
  for (let i = 0; i < lines.length; i += 1) {
    if (lines[i].startsWith(startsWith)) { start = i; break }
  }
  if (start < 0) return null
  let end = lines.length
  for (let i = start + 1; i < lines.length; i += 1) {
    if (/^\d+(\.\d+)?\. /.test(lines[i]) || /^#{1,6}\s/.test(lines[i])) { end = i; break }
  }
  return lines.slice(start, end).join('\n')
}

// 중괄호 균형으로 함수 본문을 잘라낸다 — 정규식만으로는 중첩을 못 센다.
function extractFunction(src, name) {
  const sig = src.indexOf(`function ${name}(`)
  if (sig < 0) return null
  let i = src.indexOf('{', sig)
  if (i < 0) return null
  let depth = 0, inStr = null, prev = ''
  for (let j = i; j < src.length; j += 1) {
    const c = src[j]
    if (inStr) {
      if (c === inStr && prev !== '\\') inStr = null
    } else if (c === '"' || c === "'" || c === '`') {
      inStr = c
    } else if (c === '{') depth += 1
    else if (c === '}') { depth -= 1; if (depth === 0) return src.slice(sig, j + 1) }
    prev = c
  }
  return null
}

const argv = process.argv.slice(2)
const mode = argv[0]

if (mode === '--both-sites') {
  // usage: --both-sites escape <file>
  //   ⛔ 두 자리를 **따로** 본다 — 파일 어딘가에 한 번 있는 것으로는 통과하지 않는다.
  const [, kind, file] = argv
  if (kind !== 'escape') die(`알 수 없는 kind: ${kind}`)
  const src = read(file)
  const prompt = src.slice(src.indexOf('phase(\'Stage 1'), src.indexOf('schema: DraftSchema'))
  const schema = extractObjectLiteral(src, 'DraftSchema')
  if (!prompt || prompt.length < 50) die('Stage 1 프롬프트 블록을 찾지 못했다 (측정 실패)')
  if (!schema) die('DraftSchema 리터럴을 찾지 못했다 (측정 실패)')
  const RX = /이스케이프|escape/
  const sites = []
  if (!RX.test(prompt)) sites.push('Stage 1 프롬프트')
  if (!RX.test(schema)) sites.push('DraftSchema description')
  if (sites.length) die(`이스케이프 지시 누락: ${sites.join(' · ')}`)
  console.log('S1_ESCAPE_OK (Stage1 프롬프트 + DraftSchema 양쪽)')
  process.exit(0)
}

function extractObjectLiteral(src, name) {
  const sig = src.indexOf(`const ${name} = `)
  if (sig < 0) return null
  let i = src.indexOf('{', sig)
  let depth = 0, inStr = null, prev = ''
  for (let j = i; j < src.length; j += 1) {
    const c = src[j]
    if (inStr) { if (c === inStr && prev !== '\\') inStr = null }
    else if (c === '"' || c === "'" || c === '`') inStr = c
    else if (c === '{') depth += 1
    else if (c === '}') { depth -= 1; if (depth === 0) return src.slice(sig, j + 1) }
    prev = c
  }
  return null
}

if (mode === '--order-in-section') {
  // usage: --order-in-section '<섹션 제목>' '<먼저>' '<나중>' <file>
  const [, title, first, second, file] = argv
  const sec = mdSection(read(file), title)
  if (!sec) die(`섹션을 찾지 못했다: ${title}`)
  const a = sec.indexOf(first), b = sec.indexOf(second)
  if (a < 0) die(`'${first}' 가 섹션 '${title}' 에 없다`)
  if (b < 0) die(`'${second}' 가 섹션 '${title}' 에 없다`)
  if (!(a < b)) die(`순서 위반: '${first}'(${a}) 가 '${second}'(${b}) 보다 뒤에 있다`)
  console.log(`PRECOPY_OK ('${first}' → '${second}' 순서 확인)`)
  process.exit(0)
}

if (mode === '--schema-len') {
  // usage: --schema-len <file> <field>...
  //   각 필드의 description 에 **글자 수 상한**이 명시돼 있는가 (숫자 + 자/chars).
  const file = argv[1]
  const fields = argv.slice(2)
  if (!fields.length) die('검사할 필드가 없다')
  const src = read(file)
  const missing = []
  for (const f of fields) {
    // `f: { ... description: '...' }` 에서 그 필드 블록만 좁혀 본다
    const rx = new RegExp(`${f}\\s*:\\s*\\{[^}]*description\\s*:\\s*['"\`]([^'"\`]*)['"\`]`, 's')
    const m = src.match(rx)
    if (!m) { missing.push(`${f}(description 없음)`); continue }
    if (!/\d+\s*(자|chars|characters)/.test(m[1])) missing.push(`${f}(길이 상한 없음)`)
  }
  if (missing.length) die(`길이 지침 누락: ${missing.join(' · ')}`)
  console.log(`SCHEMA_LEN_OK (${fields.length}필드 길이 상한 명시)`)
  process.exit(0)
}

if (mode === '--return-has') {
  // usage: --return-has <key> <file>  — 최종 return 리터럴에 그 키가 있는가
  const [, key, file] = argv
  const src = read(file)
  const idx = src.lastIndexOf('\nreturn {')
  if (idx < 0) die('최종 return 리터럴을 찾지 못했다')
  const tail = src.slice(idx)
  if (!new RegExp(`\\n\\s*${key}\\s*:`).test(tail)) die(`반환 리터럴에 '${key}' 키가 없다`)
  console.log(`RETURN_OK (반환에 ${key} 포함)`)
  process.exit(0)
}

if (mode === '--brief-test') {
  // usage: --brief-test <file> <fixture.json>
  //   integrateBrief 를 추출해 실제로 호출한다 — 이름 존재가 아니라 **동작**을 본다:
  //   ① 렌즈 산출의 모든 id 가 brief 에 남아 있는가(정보 유실 0)
  //   ② 출력이 40k자 이하인가(축약이 실제로 일어났는가)
  const [, file, fixture] = argv
  const src = read(file)
  const fnSrc = extractFunction(src, 'integrateBrief')
  if (!fnSrc) die('integrateBrief 함수를 찾지 못했다')
  let fn
  try { fn = new Function(`${fnSrc}; return integrateBrief`)() } catch (e) { die(`integrateBrief 평가 실패: ${e.message}`) }
  const fx = JSON.parse(read(fixture))
  let out
  try { out = fn(fx.impact, fx.edge, fx.arch, fx.impactOnEdge, fx.edgeOnImpact) } catch (e) { die(`integrateBrief 호출 실패: ${e.message}`) }
  const text = typeof out === 'string' ? out : JSON.stringify(out)
  const ids = []
  for (const f of (fx.impact && fx.impact.impactFiles) || []) ids.push(f.file)
  for (const e of (fx.edge && fx.edge.edgeCases) || []) ids.push(e.id)
  for (const l of ((fx.impactOnEdge && fx.impactOnEdge.links) || [])) ids.push(l.sourceId)
  const lost = ids.filter(id => !text.includes(id))
  if (lost.length) die(`brief 에서 id 유실 ${lost.length}건: ${lost.slice(0, 5).join(', ')}`)
  if (text.length > 40000) die(`brief 길이 ${text.length}자 > 40000자 상한`)
  console.log(`BRIEF_OK (id ${ids.length}건 보존 · ${text.length}자 ≤ 40000)`)
  process.exit(0)
}

if (mode === '--section-has') {
  // usage: --section-has '<섹션 제목>' <needle>... <file>
  const title = argv[1]
  const file = argv[argv.length - 1]
  const needles = argv.slice(2, argv.length - 1)
  if (!needles.length) die('검사할 문구가 없다')
  const token = SECTION_TOKENS[title]
  if (!token) die(`토큰 미등록 섹션: '${title}' — SECTION_TOKENS 에 추가하라 (조용한 통과 금지)`)
  const sec = mdSection(read(file), title)
  if (!sec) die(`섹션을 찾지 못했다: ${title}`)
  const missing = needles.filter(n => !sec.includes(n))
  if (missing.length) die(`섹션 '${title}' 에 누락: ${missing.join(' · ')}`)
  console.log(`${token} (${needles.length}문구 확인)`)
  process.exit(0)
}

if (mode === '--self-test') {
  // 양성·음성 self-test — 검사기 자신이 통과/실패를 실제로 가르는지 본다.
  const os = require('os'), path = require('path')
  const d = fs.mkdtempSync(path.join(os.tmpdir(), 'cwt-'))
  const { execFileSync } = require('child_process')
  const me = __filename
  let pass = 0; const fails = []
  const run = (args, wantExit) => {
    let code = 0
    try { execFileSync(process.execPath, [me, ...args], { stdio: 'pipe' }) } catch (e) { code = e.status }
    if (code === wantExit) pass += 1; else fails.push(`${args.slice(0, 2).join(' ')} → exit ${code} (기대 ${wantExit})`)
  }
  // --section-has: 양성 / 음성(문구 누락) / 미등록 섹션
  const md = path.join(d, 'a.md')
  fs.writeFileSync(md, '## Phase 2: Plan Validation\n불변 입력 · 별도 출력 · 양쪽 완료 · schema 검증\n\n## Other\nx\n')
  run(['--section-has', 'Phase 2: Plan Validation', '불변 입력', '별도 출력', '양쪽 완료', 'schema', md], 0)
  run(['--section-has', 'Phase 2: Plan Validation', '없는문구', md], 1)
  run(['--section-has', 'Unregistered Section', 'x', md], 1)
  // --order-in-section: 양성 / 역순
  const md2 = path.join(d, 'b.md')
  fs.writeFileSync(md2, '### 실행 절차 (Lead)\n3. cp foo bar\n4. Workflow(x)\n')
  run(['--order-in-section', '실행 절차 (Lead)', 'cp ', 'Workflow(', md2], 0)
  const md3 = path.join(d, 'c.md')
  fs.writeFileSync(md3, '### 실행 절차 (Lead)\n3. Workflow(x)\n4. cp foo bar\n')
  run(['--order-in-section', '실행 절차 (Lead)', 'cp ', 'Workflow(', md3], 1)
  // --schema-len: 상한 있음 / 없음
  const js1 = path.join(d, 'd.js')
  fs.writeFileSync(js1, "const S = { properties: { evidence: { type: 'string', description: '근거 — 200자 이내' } } }\n")
  run(['--schema-len', js1, 'evidence'], 0)
  const js2 = path.join(d, 'e.js')
  fs.writeFileSync(js2, "const S = { properties: { evidence: { type: 'string', description: '근거' } } }\n")
  run(['--schema-len', js2, 'evidence'], 1)
  // --return-has: 있음 / 없음
  const js3 = path.join(d, 'f.js')
  fs.writeFileSync(js3, "x\nreturn {\n  mode: 'workflow',\n  lensOutputs: {},\n}\n")
  run(['--return-has', 'lensOutputs', js3], 0)
  run(['--return-has', 'missingKey', js3], 1)
  // 파일 부재 = 측정 실패
  run(['--return-has', 'x', path.join(d, 'nope.js')], 1)
  fs.rmSync(d, { recursive: true, force: true })
  for (const f of fails) console.error(`  FAIL ${f}`)
  console.log(`check_wf_text self-test ${pass}/${pass + fails.length} passed`)
  process.exit(fails.length ? 1 : 0)
}

die(`모드는 --both-sites|--order-in-section|--schema-len|--return-has|--brief-test|--section-has|--self-test — 받은 값: '${mode}'`)
