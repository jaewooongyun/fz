import { test, expect } from 'claude-code/testing'
import { cleanup, loadManifest, logPathOf, settleEntries, spillBatch, touchActivity } from '../lib/spill.ts'
import type { Manifest, SpillItem } from '../lib/spill.ts'
import { fakeHost } from './fakehost.ts'
import type { FakeHost } from './fakehost.ts'

const ROOT = '/spill'
const MIB = 1024 * 1024
const HOUR = 60 * 60 * 1000
const DAY = 24 * HOUR

function spillItem(tool_use_id: string, text: string, tool = 'Read'): SpillItem {
  return { tool_use_id, tool, text }
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

function keysOf(spilled: ReadonlyMap<string, string>): string {
  return [...spilled.keys()].sort().join(',')
}

function idsOf(manifest: Manifest | null): string {
  return (manifest?.entries ?? []).map((entry) => entry.tool_use_id).sort().join(',')
}

/** Each entry of `manifest` as `<tool_use_id>:<confirmed>`, in its order; '' without one. */
function confirmedOf(manifest: Manifest | null): string {
  return (manifest?.entries ?? []).map((entry) => `${entry.tool_use_id}:${entry.confirmed}`).join(',')
}

function filesUnder(host: FakeHost, folder: string): string {
  return [...host.files.keys()].filter((path) => path.startsWith(`${folder}/`)).sort().join(',')
}

function tempsOf(host: FakeHost): string {
  return [...host.files.keys()].filter((path) => path.includes('.tmp-')).sort().join(',')
}

/** A manifest file's text naming `ids` in `sessionId`'s folder. */
function manifestText(sessionId: string, lastActivityAt: number, ids: readonly string[]): string {
  const manifest: Manifest = {
    sessionId,
    lastActivityAt,
    entries: ids.map((id) => ({ tool_use_id: id, tool: 'Read', chars: 1, sha256: '0', path: `${ROOT}/${sessionId}/${id}.txt`, generation: 1, confirmed: false })),
  }
  return JSON.stringify(manifest)
}

/** `sessionId`'s manifest and log, its `named.txt` and `stray.txt`, and its manifest's temporary file `.json.tmp-7`, as sorted paths under `ROOT`. */
function sessionFiles(sessionId: string): string[] {
  return [`${ROOT}/${sessionId}.json`, logPathOf(ROOT, sessionId), `${ROOT}/${sessionId}/named.txt`, `${ROOT}/${sessionId}/stray.txt`, `${ROOT}/${sessionId}.json.tmp-7`].sort()
}

test('spill: verifies hash before mask', async () => {
  const host = fakeHost(1_000)
  const sid = 'hash-session'
  const dir = `${ROOT}/${sid}`
  const good = 'beta '.repeat(400)
  host.readAs = (path) => (path === `${dir}/t1.txt` ? 'tampered on the way back' : undefined)
  const spilled = await spillBatch(host, ROOT, sid, 1, [spillItem('t1', 'alpha '.repeat(400)), spillItem('t2', good, 'Bash')])
  expect(keysOf(spilled)).toBe('t2')
  expect(spilled.get('t2')).toBe(`${dir}/t2.txt`)

  const manifest = await loadManifest(host, ROOT, sid)
  expect((manifest?.entries ?? []).map((e) => `${e.tool_use_id}:${e.tool}:${e.chars}:${e.generation}:${e.path}`).join(',')).toBe(`t2:Bash:${good.length}:1:${dir}/t2.txt`)
  expect(manifest?.entries[0]?.sha256).toBe(await sha256Hex(good))

  const tempRead = host.calls.findIndex((call) => call.startsWith(`read ${dir}/t2.txt.tmp-`))
  const moved = host.calls.findIndex((call) => call.startsWith(`run mv -f ${dir}/t2.txt.tmp-`) && call.endsWith(` ${dir}/t2.txt`))
  const readBack = host.calls.indexOf(`read ${dir}/t2.txt`)
  expect(tempRead >= 0 && moved > tempRead && readBack > moved).toBe(true)
  expect(host.calls.indexOf(`read ${dir}/t1.txt`) >= 0).toBe(true)
  expect(host.files.has(`${dir}/t1.txt`)).toBe(false)
  expect(host.files.get(`${dir}/t2.txt`)?.text).toBe(good)

  host.readAs = (path) => (path.startsWith(`${dir}/t2.txt.tmp-`) ? 'torn on the way down' : undefined)
  const seen = host.calls.length
  const again = await spillBatch(host, ROOT, sid, 2, [spillItem('t2', 'gamma '.repeat(400), 'Bash')])
  expect(again.size).toBe(0)
  expect(host.calls.slice(seen).some((call) => call.startsWith('run mv '))).toBe(false)
  expect(host.files.get(`${dir}/t2.txt`)?.text).toBe(good)
  expect((await loadManifest(host, ROOT, sid))?.entries[0]?.sha256).toBe(await sha256Hex(good))
  expect(tempsOf(host)).toBe('')
})

test('spill: manifest written before mask', async () => {
  const host = fakeHost(2_000)
  const sid = 'order-session'
  const dir = `${ROOT}/${sid}`
  const manifestPath = `${ROOT}/${sid}.json`
  const spilled = await spillBatch(host, ROOT, sid, 3, [spillItem('t1', 'one '.repeat(300)), spillItem('t2', 'two '.repeat(300), 'Grep')]).then((map) => {
    host.mark('resolved')
    return map
  })
  expect(keysOf(spilled)).toBe('t1,t2')

  const manifestMove = host.calls.findIndex((call) => call.startsWith(`run mv -f ${manifestPath}.tmp-`) && call.endsWith(` ${manifestPath}`))
  expect(manifestMove >= 0).toBe(true)
  expect(host.calls.indexOf('mark resolved')).toBe(manifestMove + 1)
  for (const id of ['t1', 't2']) {
    const verified = host.calls.indexOf(`read ${dir}/${id}.txt`)
    expect(`${id}:${verified >= 0 && verified < manifestMove}`).toBe(`${id}:true`)
  }
  expect(host.calls.filter((call) => call.startsWith(`write ${manifestPath}.tmp-`)).length).toBe(1)

  const manifest = await loadManifest(host, ROOT, sid)
  expect(`${manifest?.sessionId}|${manifest?.lastActivityAt}`).toBe(`${sid}|0`)
  expect((manifest?.entries ?? []).map((e) => `${e.tool_use_id}=${e.path}:${e.generation}`).join(',')).toBe([...spilled].map(([id, path]) => `${id}=${path}:3`).join(','))
})

test('spill: write failure keeps original', async () => {
  const host = fakeHost(3_000)
  const sid = 'write-session'
  const dir = `${ROOT}/${sid}`
  host.failWrite = (path) => path.startsWith(`${dir}/t1.txt.tmp-`)
  const first = await spillBatch(host, ROOT, sid, 1, [spillItem('t1', 'lost '.repeat(300)), spillItem('t2', 'kept '.repeat(300))])
  expect(keysOf(first)).toBe('t2')
  expect(host.calls.some((call) => call.startsWith('run mv') && call.includes(`${dir}/t1.txt`))).toBe(false)
  expect(filesUnder(host, dir)).toBe(`${dir}/t2.txt`)

  host.failWrite = () => false
  host.failRun = (argv) => {
    if (argv[0] !== 'mv') return undefined
    if (argv[3] === `${dir}/t3.txt`) return 'exit'
    if (argv[3] === `${dir}/t4.txt`) return 'reject'
    return undefined
  }
  const second = await spillBatch(host, ROOT, sid, 2, [spillItem('t3', 'three '.repeat(300)), spillItem('t4', 'four '.repeat(300))])
  expect(second.size).toBe(0)
  expect(filesUnder(host, dir)).toBe(`${dir}/t2.txt`)
  expect(idsOf(await loadManifest(host, ROOT, sid))).toBe('t2')
  expect(host.calls.filter((call) => call.startsWith(`write ${ROOT}/${sid}.json.tmp-`)).length).toBe(1)
})

test('spill: manifest failure removes new spill', async () => {
  const host = fakeHost(4_000)
  const sid = 'manifest-session'
  const dir = `${ROOT}/${sid}`
  const manifestPath = `${ROOT}/${sid}.json`
  const zero = 'zero '.repeat(300)
  const one = 'one '.repeat(300)
  expect(keysOf(await spillBatch(host, ROOT, sid, 1, [spillItem('t0', zero)]))).toBe('t0')
  const before = host.files.get(manifestPath)?.text ?? ''
  expect(before.includes('"t0"')).toBe(true)

  for (const failure of ['exit', 'reject'] as const) {
    host.failRun = (argv) => (argv[0] === 'mv' && argv[3] === manifestPath ? failure : undefined)
    const failed = await spillBatch(host, ROOT, sid, 2, [spillItem('t0', zero), spillItem('t1', one)])
    expect(`${failure}:${failed.size}`).toBe(`${failure}:0`)
    expect(`${failure}:${filesUnder(host, dir)}`).toBe(`${failure}:${dir}/t0.txt`)
    expect(`${failure}:${tempsOf(host)}`).toBe(`${failure}:`)
    expect(host.files.get(manifestPath)?.text).toBe(before)
    expect(host.files.get(`${dir}/t0.txt`)?.text).toBe(zero)
  }

  host.failRun = () => undefined
  host.failRead = (path) => path === manifestPath
  const blocked = await spillBatch(host, ROOT, sid, 3, [spillItem('t1', one)])
  await touchActivity(host, ROOT, sid, 9_000)
  host.failRead = () => false
  expect(blocked.size).toBe(0)
  expect(host.files.get(manifestPath)?.text).toBe(before)
  expect(filesUnder(host, dir)).toBe(`${dir}/t0.txt`)

  const retried = await spillBatch(host, ROOT, sid, 4, [spillItem('t1', one)])
  expect(keysOf(retried)).toBe('t1')
  expect(idsOf(await loadManifest(host, ROOT, sid))).toBe('t0,t1')
})

test('spill: idempotent rewrite refreshes mtime', async () => {
  const host = fakeHost(10_000)
  const sid = 'rewrite-session'
  const path = `${ROOT}/${sid}/t1.txt`
  const text = 'same '.repeat(300)
  const first = await spillBatch(host, ROOT, sid, 1, [spillItem('t1', text)])
  const firstMtime = host.files.get(path)?.mtimeMs
  host.nowMs = 20_000
  const seen = host.calls.length
  const second = await spillBatch(host, ROOT, sid, 2, [spillItem('t1', text)])
  const secondMtime = host.files.get(path)?.mtimeMs
  expect(`${firstMtime} -> ${secondMtime}`).toBe('10000 -> 20000')
  expect(host.calls.slice(seen).some((call) => call.startsWith(`write ${path}.tmp-`))).toBe(true)
  expect(`${first.get('t1')}|${second.get('t1')}`).toBe(`${path}|${path}`)
  expect(host.files.get(path)?.text).toBe(text)

  const manifest = await loadManifest(host, ROOT, sid)
  const digest = await sha256Hex(text)
  expect((manifest?.entries ?? []).map((e) => `${e.tool_use_id}:${e.generation}:${e.sha256 === digest}`).join(',')).toBe('t1:2:true')
})

test('spill: serializes same-session writes', async () => {
  const host = fakeHost(7_000)
  const sid = 'serial-session'
  const [a, b] = await Promise.all([
    spillBatch(host, ROOT, sid, 1, [spillItem('a1', 'first '.repeat(300))]),
    spillBatch(host, ROOT, sid, 1, [spillItem('b1', 'second '.repeat(300))]),
    touchActivity(host, ROOT, sid, 7_000),
  ])
  expect(`${keysOf(a)}|${keysOf(b)}`).toBe('a1|b1')
  const manifest = await loadManifest(host, ROOT, sid)
  expect(idsOf(manifest)).toBe('a1,b1')
  expect(manifest?.lastActivityAt).toBe(7_000)

  const other = 'serial-after-failure'
  let failOnce = true
  host.failRun = (argv) => {
    if (!failOnce || argv[0] !== 'mv' || argv[3] !== `${ROOT}/${other}.json`) return undefined
    failOnce = false
    return 'reject'
  }
  const [c, d] = await Promise.all([
    spillBatch(host, ROOT, other, 1, [spillItem('c1', 'third '.repeat(300))]),
    spillBatch(host, ROOT, other, 1, [spillItem('d1', 'fourth '.repeat(300))]),
  ])
  expect(`${c.size}|${keysOf(d)}`).toBe('0|d1')
  expect(idsOf(await loadManifest(host, ROOT, other))).toBe('d1')

  const third = 'serial-after-throw'
  const throwing: SpillItem = {
    tool_use_id: 'e1',
    tool: 'Read',
    get text(): string {
      throw new Error('injected item failure')
    },
  }
  const [e, f] = await Promise.all([
    spillBatch(host, ROOT, third, 1, [throwing]),
    spillBatch(host, ROOT, third, 1, [spillItem('f1', 'fifth '.repeat(300))]),
  ])
  expect(`${e.size}|${keysOf(f)}`).toBe('0|f1')
  expect(idsOf(await loadManifest(host, ROOT, third))).toBe('f1')
})

test('spill: keeps result over 4MiB', async () => {
  const host = fakeHost(5_000)
  const sid = 'big-session'
  const dir = `${ROOT}/${sid}`
  const refused = await spillBatch(host, ROOT, sid, 1, [spillItem('over', 'a'.repeat(4 * MIB + 1))])
  expect(refused.size).toBe(0)
  expect(host.calls.some((call) => call.startsWith('write ') || call.startsWith('run '))).toBe(false)

  const wide = 'é'.repeat(2 * MIB + 1)
  expect(wide.length < 4 * MIB).toBe(true)
  const mixed = await spillBatch(host, ROOT, sid, 2, [spillItem('wide', wide), spillItem('small', 'small '.repeat(300))])
  expect(keysOf(mixed)).toBe('small')
  expect(host.calls.some((call) => call.startsWith(`write ${dir}/wide.txt`))).toBe(false)

  const exact = await spillBatch(host, ROOT, sid, 3, [spillItem('exact', 'b'.repeat(4 * MIB))])
  expect(keysOf(exact)).toBe('exact')
  expect(idsOf(await loadManifest(host, ROOT, sid))).toBe('exact,small')
})

test('spill: session cap counts every file', async () => {
  const host = fakeHost(6_000)
  const sid = 'cap-session'
  const dir = `${ROOT}/${sid}`
  // 30 MiB named + 30 MiB stray + (4 MiB - 10) temporary: 11 more bytes pass 64 MiB by one, 10 reach it exactly, and leaving any one file out of the sum would let 11 through.
  host.put(`${ROOT}/${sid}.json`, manifestText(sid, 0, ['named']), 1_000)
  host.put(`${dir}/named.txt`, 'n', 1_000, 30 * MIB)
  host.put(`${dir}/stray.txt`, 's', 1_000, 30 * MIB)
  host.put(`${dir}/named.txt.tmp-9`, 't', 1_000, 4 * MIB - 10)
  const over = await spillBatch(host, ROOT, sid, 1, [spillItem('over', 'x'.repeat(11))])
  expect(over.size).toBe(0)
  expect(host.calls.some((call) => call.startsWith('write '))).toBe(false)

  const fits = await spillBatch(host, ROOT, sid, 1, [spillItem('fits', 'y'.repeat(10))])
  expect(keysOf(fits)).toBe('fits')
  expect(idsOf(await loadManifest(host, ROOT, sid))).toBe('fits,named')
})

test('spill: rewrite releases the replaced bytes', async () => {
  const host = fakeHost(8_000)
  const sid = 'release-session'
  const dir = `${ROOT}/${sid}`
  // (64 MiB - 30) stray + two named 10-byte results: 10 bytes under the cap, room for one rewrite's temporary copy while the file it replaces is still there.
  host.put(`${ROOT}/${sid}.json`, manifestText(sid, 0, ['a', 'b']), 1_000)
  host.put(`${dir}/stray.txt`, 's', 1_000, 64 * MIB - 30)
  host.put(`${dir}/a.txt`, 'a'.repeat(10), 1_000)
  host.put(`${dir}/b.txt`, 'b'.repeat(10), 1_000)
  const spilled = await spillBatch(host, ROOT, sid, 2, [spillItem('a', 'a'.repeat(10)), spillItem('b', 'b'.repeat(10)), spillItem('c', 'c'.repeat(11))])
  // Both rewrites fit, each move giving back the bytes of the file it replaced; a new 11-byte result still passes the cap by one.
  expect(keysOf(spilled)).toBe('a,b')
  expect(host.calls.some((call) => call.startsWith(`write ${dir}/c.txt`))).toBe(false)
  const manifest = await loadManifest(host, ROOT, sid)
  expect((manifest?.entries ?? []).map((e) => `${e.tool_use_id}:${e.generation}`).join(',')).toBe('a:2,b:2')
  expect(host.files.get(`${dir}/a.txt`)?.text).toBe('a'.repeat(10))
})

test('spill: cleanup rechecks mtime before delete', async () => {
  const now = 100 * DAY
  const host = fakeHost(now)
  const sid = 'aaaaaaaa-0000-4000-8000-000000000009'
  const dir = `${ROOT}/${sid}`
  host.put(`${ROOT}/${sid}.json`, manifestText(sid, now, ['named']), now)
  host.put(`${dir}/named.txt`, 'n', now - 31 * DAY)
  host.put(`${dir}/touched.txt`, 't', now - 25 * HOUR)
  host.put(`${dir}/stale.txt`, 's', now - 25 * HOUR)
  host.statMtime.set(`${dir}/named.txt`, now - HOUR)
  host.statMtime.set(`${dir}/touched.txt`, now - HOUR)
  const { removed } = await cleanup(host, ROOT, now, 30)
  expect(removed.join(',')).toBe(`${dir}/stale.txt`)
  expect(filesUnder(host, dir)).toBe(`${dir}/named.txt,${dir}/touched.txt`)

  const rms = host.calls.filter((call) => call.startsWith('run rm -f '))
  expect(rms.length).toBe(1)
  const rm = host.calls.indexOf(rms[0] ?? '')
  for (const name of ['named.txt', 'touched.txt', 'stale.txt']) {
    const stat = host.calls.indexOf(`stat ${dir}/${name}`)
    expect(`${name}:${stat >= 0 && stat < rm}`).toBe(`${name}:true`)
  }
})

test('spill: cleanup reclaims unreferenced files', async () => {
  const now = 100 * DAY
  const host = fakeHost(now)
  const sid = 'aaaaaaaa-0000-4000-8000-000000000010'
  const idle = 'aaaaaaaa-0000-4000-8000-000000000011'
  const locked = 'aaaaaaaa-0000-4000-8000-000000000012'
  const dir = `${ROOT}/${sid}`
  host.put(`${ROOT}/${sid}.json`, manifestText(sid, now - HOUR, ['named', 'old']), now - HOUR)
  host.put(`${dir}/named.txt`, 'n', now - 25 * HOUR)
  host.put(`${dir}/old.txt`, 'o', now - 31 * DAY)
  host.put(`${dir}/stray.txt`, 's', now - 25 * HOUR)
  host.put(`${dir}/named.txt.tmp-3`, 't', now - 25 * HOUR)
  host.put(`${dir}/fresh.txt`, 'f', now - 23 * HOUR)
  host.put(`${ROOT}/${sid}.json.tmp-4`, '{', now - 25 * HOUR)
  host.put(`${ROOT}/${idle}.json`, manifestText(idle, now - 31 * DAY, []), now - 31 * DAY)
  host.put(logPathOf(ROOT, idle), '{}\n', now - 31 * DAY)
  host.put(`${ROOT}/notes/keep.txt`, 'k', now - 40 * DAY)
  host.put(`${ROOT}/${locked}.json`, manifestText(locked, now - 31 * DAY, ['held']), now - 31 * DAY)
  host.put(`${ROOT}/${locked}/held.txt`, 'h', now - 25 * HOUR)
  host.failRead = (path) => path === `${ROOT}/${locked}.json`
  const { removed } = await cleanup(host, ROOT, now, 30)

  const want = [`${dir}/old.txt`, `${dir}/stray.txt`, `${dir}/named.txt.tmp-3`, `${ROOT}/${sid}.json.tmp-4`, `${ROOT}/${idle}.json`, logPathOf(ROOT, idle)].sort()
  expect([...removed].sort().join(',')).toBe(want.join(','))
  expect(filesUnder(host, dir)).toBe(`${dir}/fresh.txt,${dir}/named.txt`)
  expect(host.files.has(`${ROOT}/${sid}.json`)).toBe(true)
  expect(host.files.has(`${ROOT}/notes/keep.txt`)).toBe(true)
  expect(filesUnder(host, `${ROOT}/${locked}`)).toBe(`${ROOT}/${locked}/held.txt`)
  expect(host.files.has(`${ROOT}/${locked}.json`)).toBe(true)

  const rms = host.calls.filter((call) => call.startsWith('run rm -f '))
  expect(rms.length).toBe(1)
  const argv = (rms[0] ?? '').split(' ')
  expect(want.every((path) => argv.includes(path))).toBe(true)

  const bulk = fakeHost(now)
  const many = 'aaaaaaaa-0000-4000-8000-000000000013'
  // Its manifest is what makes the folder the plugin's.
  bulk.put(`${ROOT}/${many}.json`, manifestText(many, now, []), now)
  for (let i = 0; i < 2000; i += 1) bulk.put(`${ROOT}/${many}/stray-${String(i).padStart(4, '0')}-${'x'.repeat(40)}.txt`, 's', now - 25 * HOUR)
  const swept = await cleanup(bulk, ROOT, now, 30)
  expect(swept.removed.length).toBe(2000)
  expect(filesUnder(bulk, `${ROOT}/${many}`)).toBe('')
  const bulkRms = bulk.calls.filter((call) => call.startsWith('run rm -f '))
  expect(`${bulkRms.length > 1}|${bulkRms.length < 10}`).toBe('true|true')
  expect(bulkRms.every((call) => call.length < 256 * 1024)).toBe(true)
})

test('spill: cleanup leaves folders without a manifest', async () => {
  const now = 100 * DAY
  const host = fakeHost(now)
  const orphan = 'aaaaaaaa-0000-4000-8000-000000000014'
  const sid = 'aaaaaaaa-0000-4000-8000-000000000015'
  const lone = `${ROOT}/${orphan}`
  // A folder named like a session id with no manifest beside it, its manifest-shaped temporary file, and a folder not named so: someone else's.
  const kept = [`${lone}/old.txt`, `${lone}/old.txt.tmp-5`, `${lone}/stray.txt`, `${ROOT}/${orphan}.json.tmp-6`, `${ROOT}/build/out.log`]
  host.put(`${lone}/old.txt`, 'o', now - 31 * DAY)
  host.put(`${lone}/old.txt.tmp-5`, 't', now - 25 * HOUR)
  host.put(`${lone}/stray.txt`, 's', now - 25 * HOUR)
  host.put(`${ROOT}/${orphan}.json.tmp-6`, '{', now - 25 * HOUR)
  host.put(`${ROOT}/build/out.log`, 'b', now - 31 * DAY)
  // The same root's session with a manifest is swept as before.
  host.put(`${ROOT}/${sid}.json`, manifestText(sid, now - HOUR, []), now - HOUR)
  host.put(`${ROOT}/${sid}/stray.txt`, 's', now - 25 * HOUR)
  const { removed } = await cleanup(host, ROOT, now, 30)

  expect(removed.join(',')).toBe(`${ROOT}/${sid}/stray.txt`)
  expect(kept.filter((path) => host.files.has(path)).join(',')).toBe(kept.join(','))
  expect(host.calls.includes(`list ${lone}`)).toBe(false)
  const rms = host.calls.filter((call) => call.startsWith('run rm -f '))
  expect(rms.length).toBe(1)
  expect(rms.some((call) => call.includes(orphan) || call.includes(`${ROOT}/build/`))).toBe(false)
})

test('spill: cleanup keeps a manifest until its folder is emptied', async () => {
  const now = 100 * DAY
  const host = fakeHost(now)
  const sid = 'aaaaaaaa-0000-4000-8000-000000000016'
  const dir = `${ROOT}/${sid}`
  const manifestPath = `${ROOT}/${sid}.json`
  const logPath = logPathOf(ROOT, sid)
  // Past its keep, with 2000 stray files the sweep takes in several rm calls; the first of those calls fails.
  host.put(manifestPath, manifestText(sid, now - 31 * DAY, []), now - 31 * DAY)
  host.put(logPath, '{}\n', now - 31 * DAY)
  for (let i = 0; i < 2000; i += 1) host.put(`${dir}/stray-${String(i).padStart(4, '0')}-${'x'.repeat(40)}.txt`, 's', now - 25 * HOUR)
  let failOnce = true
  host.failRun = (argv) => {
    if (!failOnce || argv[0] !== 'rm') return undefined
    failOnce = false
    return 'exit'
  }
  const first = await cleanup(host, ROOT, now, 30)
  const left = [...host.files.keys()].filter((path) => path.startsWith(`${dir}/`)).length
  // Some of the folder's files are still there, so the manifest that has the folder looked into stays, its log with it.
  expect(`${left > 0}|${left < 2000}`).toBe('true|true')
  expect(first.removed.length).toBe(2000 - left)
  expect(`${host.files.has(manifestPath)}|${host.files.has(logPath)}`).toBe('true|true')

  // The next sweep still finds the folder by that manifest: the rest go, then the manifest and log in a call of their own.
  const seen = host.calls.length
  const second = await cleanup(host, ROOT, now, 30)
  expect(second.removed.length).toBe(left + 2)
  expect(filesUnder(host, dir)).toBe('')
  expect(`${host.files.has(manifestPath)}|${host.files.has(logPath)}`).toBe('false|false')
  const rms = host.calls.slice(seen).filter((call) => call.startsWith('run rm -f '))
  expect(rms[rms.length - 1]).toBe(`run rm -f ${manifestPath} ${logPath}`)
})

test('spill: cleanup leaves the live session alone', async () => {
  const now = 100 * DAY
  const host = fakeHost(now)
  const live = 'aaaaaaaa-0000-4000-8000-000000000017'
  const other = 'aaaaaaaa-0000-4000-8000-000000000018'
  // Both past every keep: the manifest and log 31 days old, the named file past 30 days, the unnamed one and the manifest's temporary file past 24 hours.
  for (const sid of [live, other]) {
    host.put(`${ROOT}/${sid}.json`, manifestText(sid, now - 31 * DAY, ['named']), now - 31 * DAY)
    host.put(logPathOf(ROOT, sid), '{}\n', now - 31 * DAY)
    host.put(`${ROOT}/${sid}/named.txt`, 'n', now - 31 * DAY)
    host.put(`${ROOT}/${sid}/stray.txt`, 's', now - 25 * HOUR)
    host.put(`${ROOT}/${sid}.json.tmp-7`, '{', now - 25 * HOUR)
  }
  const { removed } = await cleanup(host, ROOT, now, 30, live)
  // The other session goes as before; the live one is not looked into, nothing of it removed.
  expect([...removed].sort().join(',')).toBe(sessionFiles(other).join(','))
  expect(sessionFiles(live).filter((path) => host.files.has(path)).join(',')).toBe(sessionFiles(live).join(','))
  expect(host.calls.includes(`list ${ROOT}/${live}`)).toBe(false)
  expect(host.calls.some((call) => call.startsWith('run rm -f ') && call.includes(live))).toBe(false)

  // A sweep that names no live session takes it as any other.
  const again = await cleanup(host, ROOT, now, 30)
  expect([...again.removed].sort().join(',')).toBe(sessionFiles(live).join(','))
})

test('spill: settle drops and confirms in one write', async () => {
  const host = fakeHost(11_000)
  const sid = 'settle-session'
  const dir = `${ROOT}/${sid}`
  const manifestPath = `${ROOT}/${sid}.json`
  const a = 'alpha '.repeat(300)
  const b = 'beta '.repeat(300)
  expect(keysOf(await spillBatch(host, ROOT, sid, 1, [spillItem('a', a), spillItem('b', b), spillItem('c', 'gamma '.repeat(300))]))).toBe('a,b,c')
  await touchActivity(host, ROOT, sid, 12_345)
  const listed = await loadManifest(host, ROOT, sid)
  expect(confirmedOf(listed)).toBe('a:false,b:false,c:false')
  const kept = listed?.entries.find((entry) => entry.tool_use_id === 'c')
  const seen = host.calls.length
  expect(await settleEntries(host, ROOT, sid, ['a'], ['b'])).toBe(true)
  const manifest = await loadManifest(host, ROOT, sid)
  expect(confirmedOf(manifest)).toBe('a:true,c:false')
  expect(manifest?.lastActivityAt).toBe(12_345)
  expect(JSON.stringify(manifest?.entries.find((entry) => entry.tool_use_id === 'c'))).toBe(JSON.stringify(kept))
  expect(host.files.get(`${dir}/b.txt`)?.text).toBe(b)
  // One new manifest for both changes: written to a temporary file, read back there, then moved into place.
  const calls = host.calls.slice(seen)
  expect(calls.filter((call) => call.startsWith(`write ${manifestPath}.tmp-`)).length).toBe(1)
  const written = calls.findIndex((call) => call.startsWith(`write ${manifestPath}.tmp-`))
  const verified = calls.findIndex((call) => call.startsWith(`read ${manifestPath}.tmp-`))
  const moved = calls.findIndex((call) => call.startsWith(`run mv -f ${manifestPath}.tmp-`) && call.endsWith(` ${manifestPath}`))
  expect(written >= 0 && verified > written && moved > verified).toBe(true)
  expect(tempsOf(host)).toBe('')

  // Nothing to change (a confirmed already, an id the manifest does not name): nothing is written.
  const quiet = host.calls.length
  expect(await settleEntries(host, ROOT, sid, ['a'], ['zz'])).toBe(true)
  expect(host.calls.slice(quiet).some((call) => call.startsWith('write ') || call.startsWith('run '))).toBe(false)

  // Called between two spills of the session, it runs between them: it confirms the first spill's entry, and the second's stays unconfirmed.
  const [d, settled, e] = await Promise.all([
    spillBatch(host, ROOT, sid, 2, [spillItem('d', 'delta '.repeat(300))]),
    settleEntries(host, ROOT, sid, ['d'], ['a']),
    spillBatch(host, ROOT, sid, 2, [spillItem('e', 'epsilon '.repeat(300))]),
  ])
  expect(`${keysOf(d)}|${settled}|${keysOf(e)}`).toBe('d|true|e')
  expect(confirmedOf(await loadManifest(host, ROOT, sid))).toBe('c:false,d:true,e:false')
  expect(host.files.get(`${dir}/a.txt`)?.text).toBe(a)

  // A manifest that cannot be read now, or none at all: nothing is written.
  host.failRead = (path) => path === manifestPath
  const before = host.calls.length
  expect(await settleEntries(host, ROOT, sid, ['c'], [])).toBe(false)
  expect(await settleEntries(host, ROOT, 'settle-none', ['x'], ['y'])).toBe(false)
  expect(host.calls.slice(before).some((call) => call.startsWith('write ') || call.startsWith('run '))).toBe(false)
  host.failRead = () => false
  expect(confirmedOf(await loadManifest(host, ROOT, sid))).toBe('c:false,d:true,e:false')
})

test('spill: entry without confirmed reads as unconfirmed', async () => {
  const host = fakeHost(13_000)
  const sid = 'unconfirmed-session'
  const entry = (id: string): Record<string, unknown> => ({ tool_use_id: id, tool: 'Read', chars: 1, sha256: '0', path: `${ROOT}/${sid}/${id}.txt`, generation: 1 })
  // An entry with no `confirmed`, one with `confirmed: true`, and one whose `confirmed` is not a boolean.
  const entries = [entry('bare'), { ...entry('yes'), confirmed: true }, { ...entry('odd'), confirmed: 'true' }]
  host.put(`${ROOT}/${sid}.json`, JSON.stringify({ sessionId: sid, lastActivityAt: 0, entries }), 13_000)
  expect(confirmedOf(await loadManifest(host, ROOT, sid))).toBe('bare:false,yes:true,odd:false')
})

test('spill: rewrite keeps confirmed', async () => {
  const host = fakeHost(14_000)
  const sid = 'keep-confirmed'
  const a = 'alpha '.repeat(300)
  const b = 'beta '.repeat(300)
  expect(keysOf(await spillBatch(host, ROOT, sid, 1, [spillItem('a', a), spillItem('b', b)]))).toBe('a,b')
  expect(await settleEntries(host, ROOT, sid, ['a'], [])).toBe(true)
  // Spilled again under a later generation, with a new result: each entry written afresh, a's confirmation kept, b and c unconfirmed.
  expect(keysOf(await spillBatch(host, ROOT, sid, 2, [spillItem('a', a), spillItem('b', b), spillItem('c', 'gamma '.repeat(300))]))).toBe('a,b,c')
  const manifest = await loadManifest(host, ROOT, sid)
  expect((manifest?.entries ?? []).map((entry) => `${entry.tool_use_id}:${entry.generation}:${entry.confirmed}`).join(',')).toBe('a:2:true,b:2:false,c:2:false')
})

test('spill: failed settle leaves the manifest as it was', async () => {
  const host = fakeHost(15_000)
  const sid = 'settle-failure'
  const dir = `${ROOT}/${sid}`
  const manifestPath = `${ROOT}/${sid}.json`
  expect(keysOf(await spillBatch(host, ROOT, sid, 1, [spillItem('a', 'alpha '.repeat(300)), spillItem('b', 'beta '.repeat(300))]))).toBe('a,b')
  const before = host.files.get(manifestPath)?.text ?? ''
  // Settles with the failure `label` names set, checks that nothing changed, then clears every failure.
  const failsWith = async (label: string): Promise<void> => {
    expect(`${label}:${await settleEntries(host, ROOT, sid, ['a'], ['b'])}`).toBe(`${label}:false`)
    expect(`${label}:${host.files.get(manifestPath)?.text === before}`).toBe(`${label}:true`)
    expect(`${label}:${tempsOf(host)}`).toBe(`${label}:`)
    host.failWrite = () => false
    host.readAs = () => undefined
    host.failRun = () => undefined
  }
  // The new manifest's copy torn on its way down, read back torn, or not moved into place (a non-zero exit, a rejected call).
  host.failWrite = (path) => path.startsWith(`${manifestPath}.tmp-`)
  await failsWith('torn write')
  host.readAs = (path) => (path.startsWith(`${manifestPath}.tmp-`) ? 'torn on the way back' : undefined)
  await failsWith('torn read back')
  for (const failure of ['exit', 'reject'] as const) {
    host.failRun = (argv) => (argv[0] === 'mv' && argv[3] === manifestPath ? failure : undefined)
    await failsWith(failure)
  }
  expect(filesUnder(host, dir)).toBe(`${dir}/a.txt,${dir}/b.txt`)
  expect(confirmedOf(await loadManifest(host, ROOT, sid))).toBe('a:false,b:false')

  // With nothing failing, the same call goes through.
  expect(await settleEntries(host, ROOT, sid, ['a'], ['b'])).toBe(true)
  expect(confirmedOf(await loadManifest(host, ROOT, sid))).toBe('a:true')
})
