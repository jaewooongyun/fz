#!/usr/bin/env node
// scripts/check_wf_syntax.js — 워크플로 스크립트 문법 검사 (A5-01).
//
// ⛔ `node --check` 로는 판정할 수 없다. 워크플로 파일은 `export const meta` + 최상위 `await`·`return` 을
//    가진 **async 함수 본문**이라 CJS·ESM 어느 문법으로도 유효하지 않다. 그래서 노드 버전에 따라
//    전부 실패하거나 전부 통과한다 — Node v26 실측은 심은 문법 오류까지 rc=0(100% 위음성)이었다.
//    런타임과 같은 문법 목표로 파싱한다: 첫 `export const meta` 의 `export` 만 벗기고
//    AsyncFunction 본문으로 **컴파일만** 한다(실행하지 않는다).
// ⛔ `export const meta` 는 앞쪽 주석·공백을 걷은 뒤 **첫 문장**이어야 한다(런타임: "must begin with").
//    주석 안에 든 선언은 선언이 아니다 — 정규식으로 아무 줄이나 찾으면 meta 없는 스크립트가 통과한다(GPT R-A 검토 002).
//
// usage: check_wf_syntax.js [--root DIR] | --self-test
// exit: 0=전부 통과 · 1=문법 오류·meta 누락 있음 · 2=판정 불가(워크플로 0건·읽기 실패)
'use strict'
const fs = require('fs')
const os = require('os')
const path = require('path')
const vm = require('vm')

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
// 앞쪽 공백·`//` 줄 주석·`/* */` 블록 주석을 건너뛴 첫 문장이 meta 선언이면 그 위치, 아니면 -1
function leadingMeta(src) {
  let i = 0
  for (;;) {
    const rest = src.slice(i)
    const ws = rest.match(/^\s+/)
    if (ws) { i += ws[0].length; continue }
    if (rest.startsWith('//')) { const e = src.indexOf('\n', i); i = e < 0 ? src.length : e + 1; continue }
    if (rest.startsWith('/*')) { const e = src.indexOf('*/', i + 2); if (e < 0) return -1; i = e + 2; continue }
    break
  }
  return /^export\s+const\s+meta\b/.test(src.slice(i)) ? i : -1
}

// ⛔ 줄·열을 바꾸지 않는다 — `export` 를 같은 길이 공백으로 지워 오류 위치가 원본과 맞게 한다
function body(src) {
  const i = leadingMeta(src)
  return i < 0 ? src : src.slice(0, i) + ' '.repeat('export'.length) + src.slice(i + 'export'.length)
}

// AsyncFunction 오류에는 줄 번호가 없다. 같은 본문을 함수로 감싸 vm 으로 한 번 더 파싱해 줄만 얻는다.
// 판정은 AsyncFunction 결과가 정한다 — 감싼 파싱은 본문이 `})` 로 탈출하면 통과할 수 있어 판정에 쓰지 않는다.
function where(file, src) {
  try { new vm.Script('(async function () {' + body(src) + '\n})', { filename: file }) } catch (e) {
    const m = String(e.stack || '').match(/^.*?:(\d+)/)
    if (m) return m[1]
  }
  return '?'
}

function checkFile(file) {
  const src = fs.readFileSync(file, 'utf8')
  if (leadingMeta(src) < 0) return `${path.basename(file)} — 첫 문장이 export const meta 가 아니다(주석·공백 뒤 첫 문장이어야 런타임이 싣는다)`
  try { new AsyncFunction(body(src)); return null } catch (e) {
    return `${path.basename(file)}:${where(file, src)} — ${e.name}: ${e.message}`
  }
}

function check(root) {
  const dir = path.join(root, 'workflows')
  let files
  try { files = fs.readdirSync(dir).filter(f => f.endsWith('.js')).sort().map(f => path.join(dir, f)) } catch (e) {
    console.error(`UNRUN: ${dir} 를 읽지 못했다 (${e.code})`)
    return 2
  }
  if (!files.length) { console.error(`UNRUN: 워크플로 0건 — ${dir} (측정 실패를 먼저 의심한다)`); return 2 }
  const bad = []
  for (const f of files) {
    let v
    try { v = checkFile(f) } catch (e) { console.error(`UNRUN: 읽기 실패 ${f} (${e.code || e.message})`); return 2 }
    if (v) bad.push(v)
  }
  for (const b of bad) console.log(`  FAIL ${b}`)
  console.log(bad.length ? `check_wf_syntax: 실패 ${bad.length}/${files.length}` : `check_wf_syntax: ${files.length}개 통과`)
  return bad.length ? 1 : 0
}

function selfTest() {
  const cases = [
    ['최상위 await·return 은 유효', 'export const meta = { name: "t" }\nconst r = await agent("x")\nreturn r\n', 0],
    ['문법 오류는 실패', 'export const meta = { name: "t" }\nconst x = (\n', 1],
    ['meta 없으면 실패', 'const r = await agent("x")\nreturn r\n', 1],
    ['주석 안의 meta 는 선언이 아니다', '/*\nexport const meta = {}\n*/\nreturn 1\n', 1],
    ['머리 주석 뒤 meta 는 유효', '// 설명\n/* 블록 */\nexport const meta = { name: "t" }\nreturn 1\n', 0],
    ['meta 외 export 는 실패(런타임보다 엄격할 수 있다)', 'export const meta = { name: "t" }\nexport const other = 1\n', 1],
  ]
  let pass = 0
  const fails = []
  for (const [name, src, want] of cases) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wfsyn-'))
    fs.mkdirSync(path.join(root, 'workflows'))
    fs.writeFileSync(path.join(root, 'workflows', 'w.js'), src)
    const log = console.log
    console.log = () => {}
    const got = check(root)
    console.log = log
    fs.rmSync(root, { recursive: true, force: true })
    if (got === want) pass += 1; else fails.push(`${name}: want ${want} got ${got}`)
  }
  // 줄 번호 보존 — 오류가 3번째 줄 안에서 끝나면 :3 으로 보고한다
  const loc = checkFileText('export const meta = {}\nconst a = 1\nconst b = 1 +* 2\nreturn a\n')
  if (/^w\.js:3 —/.test(loc || '')) pass += 1; else fails.push(`줄 번호: ${loc}`)
  for (const f of fails) console.log(`  FAIL ${f}`)
  console.log(`check_wf_syntax self-test ${pass}/${pass + fails.length} passed`)
  return fails.length ? 1 : 0
}

function checkFileText(src) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'wfsyn-'))
  const f = path.join(root, 'w.js')
  fs.writeFileSync(f, src)
  try { return checkFile(f) } finally { fs.rmSync(root, { recursive: true, force: true }) }
}

module.exports = { leadingMeta, body }
if (require.main !== module) return

const argv = process.argv.slice(2)
if (argv[0] === '--self-test') process.exit(selfTest())
let root = path.join(__dirname, '..')
if (argv[0] === '--root') {
  if (!argv[1]) { console.error('usage: check_wf_syntax.js [--root DIR] | --self-test'); process.exit(2) }
  root = argv[1]
} else if (argv.length) { console.error(`알 수 없는 인자: ${argv[0]}`); process.exit(2) }
process.exit(check(root))
