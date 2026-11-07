/**
 * A tool result to keep verbatim. Its `tool_use_id` becomes a file name, so one that is not a single
 * path component is not spilled.
 */
export type SpillItem = {
  tool_use_id: string
  tool: string
  text: string
}

/**
 * The part of a plugin's `$` the spill functions call; the engine's `$` satisfies it as it is, and tests
 * stand a host in memory in for it. `$.fs` renames and deletes nothing, so a move is `mv -f` and a delete
 * `rm -f` through `process.run` (an argument vector, no shell).
 */
export type SpillHost = {
  fs: {
    read(path: string): Promise<string>
    write(path: string, text: string): Promise<void>
    list(path: string): Promise<{ name: string; kind: 'file' | 'dir' | 'other'; size: number; mtimeMs: number }[]>
    stat(path: string, opts?: { resolve?: boolean }): Promise<{ kind: 'file' | 'dir' | 'other'; size: number; mtimeMs: number; isLink: boolean; realPath?: string }>
    exists(path: string): Promise<boolean>
  }
  process: {
    run(argv: readonly string[], init?: { timeoutMs?: number }): Promise<{ exitCode: number; stdout: string; stderr: string }>
  }
}

/** One spilled result as its session's manifest records it. */
export type ManifestEntry = {
  tool_use_id: string
  tool: string
  /** The text's length as `MaskCandidate.chars` counts it. */
  chars: number
  /** The hex sha256 of the text's UTF-8 bytes, verified in `path`. */
  sha256: string
  path: string
  /** The generation the file was last written under. */
  generation: number
  /**
   * Whether a compaction handed this result back as a placeholder after spilling it (`settleEntries`): only a
   * confirmed entry is masked again on a resume without the saving check. A new entry is unconfirmed, and so is one
   * the manifest file records without `confirmed: true`.
   */
  confirmed: boolean
}

/** A session's record at `<root>/<sessionId>.json`, one entry per tool_use_id. */
export type Manifest = {
  sessionId: string
  /**
   * When the session was last active (ms). Only `touchActivity` moves it: `spillBatch` keeps the value
   * it found and writes 0 in a manifest it creates. 0 means no activity was recorded, not activity at
   * the epoch, so an idle check must not take it for a long idle.
   */
  lastActivityAt: number
  entries: ManifestEntry[]
}

type HostEntry = Awaited<ReturnType<SpillHost['fs']['list']>>[number]

/** A manifest as it stands. `unreadable` is a file that is there but cannot be read now: no caller takes it for `none`. */
type ManifestRead = { state: 'ok'; manifest: Manifest } | { state: 'none' } | { state: 'unreadable' }

const MIB = 1024 * 1024
/** One result's UTF-8 bytes at most: `$.fs.read` rejects a larger file, so it could not be read back and verified. */
const MAX_RESULT_BYTES = 4 * MIB
/** A session folder's bytes at most: every file in it (named, stray or temporary) plus the write about to be made. */
const MAX_SESSION_BYTES = 64 * MIB
/** The path bytes one `rm` takes at most (each path's UTF-8 and its terminator), far under any `ARG_MAX`: a longer list goes in several calls, not one that cannot start. */
const MAX_RM_ARG_BYTES = 128 * 1024
const DAY_MS = 24 * 60 * 60 * 1000
/** How long a file no manifest names is kept before it is reclaimed. */
const UNREFERENCED_GRACE_MS = DAY_MS
/** The name parts every spill, manifest, log and temporary path is spelled with; `cleanup` reads names back with these same parts. */
const SPILL_EXT = '.txt'
const MANIFEST_EXT = '.json'
const LOG_EXT = '.log.jsonl'
const TEMP_MARK = '.tmp-'

/** Per session, the settled end of the calls queued so far; an entry goes once nothing is queued behind it. */
const chains = new Map<string, Promise<void>>()

/**
 * The spill root, any trailing `/` dropped: `configured` when it is not empty, else
 * `<home>/.claude/fz-compact/spill`. Null with neither, or when the one chosen is not absolute (or is `/`
 * alone), and then nothing is spilled: a relative root would land under the session's working directory,
 * and under an absolute one every path handed to `mv` and `rm` begins with `/`, so none reads as an option.
 */
export function spillRootOf(home: string | undefined, configured: string): string | null {
  if (configured === '' && (home === undefined || home === '')) return null
  const chosen = configured !== '' ? configured : `${home ?? ''}/.claude/fz-compact/spill`
  const root = chosen.replace(/\/+$/, '')
  return root.startsWith('/') ? root : null
}

/** A name usable as one path component: not empty, not `.` or `..`, no separator or NUL. */
function isSafeName(name: string): boolean {
  return name !== '' && name !== '.' && name !== '..' && !/[\\/\u0000]/.test(name)
}

function spillNameOf(toolUseId: string): string {
  return `${toolUseId}${SPILL_EXT}`
}

function manifestNameOf(sessionId: string): string {
  return `${sessionId}${MANIFEST_EXT}`
}

function logNameOf(sessionId: string): string {
  return `${sessionId}${LOG_EXT}`
}

function sessionFolderOf(root: string, sessionId: string): string {
  return `${root}/${sessionId}`
}

function spillPathOf(root: string, sessionId: string, toolUseId: string): string {
  return `${sessionFolderOf(root, sessionId)}/${spillNameOf(toolUseId)}`
}

function manifestPathOf(root: string, sessionId: string): string {
  return `${root}/${manifestNameOf(sessionId)}`
}

/** Where a session's observation log goes. `cleanup` removes the log under this name along with the session's manifest, so its writer takes the path from here. */
export function logPathOf(root: string, sessionId: string): string {
  return `${root}/${logNameOf(sessionId)}`
}

/** The session id in a manifest's temporary file name (`<sessionId>.json.tmp-<tag>`), else null. */
function manifestTempOwner(name: string): string | null {
  const mark = `${MANIFEST_EXT}${TEMP_MARK}`
  const cut = name.lastIndexOf(mark)
  if (cut <= 0 || cut + mark.length === name.length) return null
  return name.slice(0, cut)
}

function hexOf(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

/**
 * A fresh temporary name beside `path`, in the same folder so the `mv` onto `path` is a rename. The tag
 * is random, so two runtimes writing one session (or one runtime reloaded) never share a temporary file.
 */
function nextTemp(path: string): string {
  return `${path}${TEMP_MARK}${hexOf(crypto.getRandomValues(new Uint8Array(8)))}`
}

function utf8Length(text: string): number {
  return new TextEncoder().encode(text).length
}

async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return hexOf(new Uint8Array(digest))
}

/**
 * Runs `work` once every earlier call queued for the same session has settled, a rejected one included,
 * so a failure never holds the next call; calls for other sessions do not wait on it. `work` is not
 * expected to reject (every host call in it is caught), so this is the guard for what is not.
 */
function inSessionOrder<T>(sessionId: string, work: () => Promise<T>): Promise<T> {
  const previous = chains.get(sessionId) ?? Promise.resolve()
  const result = previous.then(work)
  const settled = result.then(
    () => undefined,
    () => undefined,
  )
  chains.set(sessionId, settled)
  void settled.then(() => {
    if (chains.get(sessionId) === settled) chains.delete(sessionId)
  })
  return result
}

async function readText($: SpillHost, path: string): Promise<string | null> {
  try {
    return await $.fs.read(path)
  } catch {
    return null
  }
}

async function writeText($: SpillHost, path: string, text: string): Promise<boolean> {
  try {
    await $.fs.write(path, text)
    return true
  } catch {
    return false
  }
}

async function listEntries($: SpillHost, path: string): Promise<HostEntry[] | null> {
  try {
    return await $.fs.list(path)
  } catch {
    return null
  }
}

/** Whether nothing is at `path`; a failed question counts as something still there. */
async function isGone($: SpillHost, path: string): Promise<boolean> {
  try {
    return !(await $.fs.exists(path))
  } catch {
    return false
  }
}

/** Whether the command ran and exited 0: a non-zero exit and a rejected call both count as failure. */
async function runsClean($: SpillHost, argv: readonly string[]): Promise<boolean> {
  try {
    return (await $.process.run(argv)).exitCode === 0
  } catch {
    return false
  }
}

async function moveInto($: SpillHost, from: string, to: string): Promise<boolean> {
  return runsClean($, ['mv', '-f', from, to])
}

/** Whether the file at `path` reads back with sha256 `digest`; a failed read is a no. */
async function holds($: SpillHost, path: string, digest: string): Promise<boolean> {
  const back = await readText($, path)
  return back !== null && (await sha256Hex(back)) === digest
}

/** `paths` in order, cut into lists of at most `MAX_RM_ARG_BYTES` each; a path longer than that alone is a list of its own. */
function rmBatches(paths: readonly string[]): string[][] {
  const batches: string[][] = []
  let batch: string[] = []
  let bytes = 0
  for (const path of paths) {
    const size = utf8Length(path) + 1
    if (batch.length > 0 && bytes + size > MAX_RM_ARG_BYTES) {
      batches.push(batch)
      batch = []
      bytes = 0
    }
    batch.push(path)
    bytes += size
  }
  if (batch.length > 0) batches.push(batch)
  return batches
}

/**
 * Removes `paths` with one `rm -f` per batch of `rmBatches` (one call while they fit) and answers the ones
 * gone after: all of a batch whose call exited 0, else those of it `exists` no longer finds. A failed
 * batch does not stop the next one.
 */
async function removeAll($: SpillHost, paths: readonly string[]): Promise<string[]> {
  const removed: string[] = []
  for (const batch of rmBatches(paths)) {
    if (await runsClean($, ['rm', '-f', ...batch])) {
      removed.push(...batch)
      continue
    }
    for (const path of batch) if (await isGone($, path)) removed.push(path)
  }
  return removed
}

/** The `size` of every file in a session folder, by name: none when the folder is not there, null when it is but cannot be listed. */
async function folderSizes($: SpillHost, folder: string): Promise<Map<string, number> | null> {
  const entries = await listEntries($, folder)
  if (entries === null) return (await isGone($, folder)) ? new Map<string, number>() : null
  const sizes = new Map<string, number>()
  for (const entry of entries) if (entry.kind === 'file') sizes.set(entry.name, entry.size)
  return sizes
}

/**
 * Whether a file is older than `limitMs`: by its listed mtime first, then by `stat` read again right
 * before it would be removed, so a file rewritten since the listing stays. A file gone by then, or a
 * limit that compares false (NaN), keeps it.
 */
async function isExpired($: SpillHost, path: string, listedMtimeMs: number, nowMs: number, limitMs: number): Promise<boolean> {
  if (!(nowMs - listedMtimeMs > limitMs)) return false
  try {
    const stat = await $.fs.stat(path)
    return stat.kind === 'file' && nowMs - stat.mtimeMs > limitMs
  } catch {
    return false
  }
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function asEntry(value: unknown): ManifestEntry | null {
  if (typeof value !== 'object' || value === null) return null
  const { tool_use_id, tool, chars, sha256, path, generation, confirmed } = value as Record<string, unknown>
  if (typeof tool_use_id !== 'string' || !isSafeName(tool_use_id) || typeof tool !== 'string') return null
  if (typeof sha256 !== 'string' || typeof path !== 'string' || !isFiniteNumber(chars) || !isFiniteNumber(generation)) return null
  return { tool_use_id, tool, chars, sha256, path, generation, confirmed: confirmed === true }
}

/** The manifest in `text` when it is one for `sessionId`, else null: one malformed entry makes the whole file unreadable. */
function parseManifest(text: string, sessionId: string): Manifest | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null) return null
  const record = value as Record<string, unknown>
  const lastActivityAt = record.lastActivityAt
  const raw = record.entries
  if (record.sessionId !== sessionId || !isFiniteNumber(lastActivityAt) || !Array.isArray(raw)) return null
  const entries: ManifestEntry[] = []
  for (const item of raw) {
    const entry = asEntry(item)
    if (entry === null) return null
    entries.push(entry)
  }
  return { sessionId, lastActivityAt, entries }
}

/**
 * The session's manifest as it stands: `none` when no file is there or the one there is not this
 * session's manifest (malformed, another session's), `unreadable` when one is there but its read fails.
 */
async function readManifest($: SpillHost, root: string, sessionId: string): Promise<ManifestRead> {
  const path = manifestPathOf(root, sessionId)
  const text = await readText($, path)
  if (text === null) return (await isGone($, path)) ? { state: 'none' } : { state: 'unreadable' }
  const manifest = parseManifest(text, sessionId)
  return manifest === null ? { state: 'none' } : { state: 'ok', manifest }
}

/** The session's manifest, or null when it is missing, malformed, another session's, or cannot be read now. */
export async function loadManifest($: SpillHost, root: string, sessionId: string): Promise<Manifest | null> {
  if (!isSafeName(sessionId)) return null
  const read = await readManifest($, root, sessionId)
  return read.state === 'ok' ? read.manifest : null
}

/** Writes the manifest to a temporary file and moves it into place; `temp` is that file, left behind on failure for the caller to remove. */
async function saveManifest($: SpillHost, root: string, manifest: Manifest): Promise<{ ok: boolean; temp: string }> {
  const path = manifestPathOf(root, manifest.sessionId)
  const temp = nextTemp(path)
  const ok = (await writeText($, temp, JSON.stringify(manifest))) && (await moveInto($, temp, path))
  return { ok, temp }
}

/**
 * `saveManifest` with the check a spill file's copy gets: the temporary file is read back and moved into place only
 * when its sha256 matches. `temp` is left behind on failure for the caller to remove, as there.
 */
async function saveManifestVerified($: SpillHost, root: string, manifest: Manifest): Promise<{ ok: boolean; temp: string }> {
  const path = manifestPathOf(root, manifest.sessionId)
  const temp = nextTemp(path)
  const text = JSON.stringify(manifest)
  const ok = (await writeText($, temp, text)) && (await holds($, temp, await sha256Hex(text))) && (await moveInto($, temp, path))
  return { ok, temp }
}

/** `previous` with each fresh entry in place of the one of its id, or after them when its id is new. */
function mergeEntries(previous: readonly ManifestEntry[], fresh: readonly ManifestEntry[]): ManifestEntry[] {
  const byId = new Map<string, ManifestEntry>()
  for (const entry of previous) byId.set(entry.tool_use_id, entry)
  for (const entry of fresh) byId.set(entry.tool_use_id, entry)
  return [...byId.values()]
}

async function writeBatch($: SpillHost, root: string, sessionId: string, generation: number, items: readonly SpillItem[]): Promise<Map<string, string>> {
  const spilled = new Map<string, string>()
  if (!isSafeName(sessionId) || items.length === 0) return spilled
  const previous = await readManifest($, root, sessionId)
  if (previous.state === 'unreadable') return spilled
  const sizes = await folderSizes($, sessionFolderOf(root, sessionId))
  if (sizes === null) return spilled
  let used = 0
  for (const size of sizes.values()) used += size
  const known = previous.state === 'ok' ? previous.manifest : null
  const named = new Set((known?.entries ?? []).map((entry) => entry.tool_use_id))
  const confirmed = new Set((known?.entries ?? []).filter((entry) => entry.confirmed).map((entry) => entry.tool_use_id))
  const fresh: ManifestEntry[] = []
  const discard: string[] = []
  for (const item of items) {
    if (!isSafeName(item.tool_use_id)) continue
    const bytes = utf8Length(item.text)
    if (bytes > MAX_RESULT_BYTES || used + bytes > MAX_SESSION_BYTES) continue
    used += bytes
    const digest = await sha256Hex(item.text)
    const path = spillPathOf(root, sessionId, item.tool_use_id)
    const temp = nextTemp(path)
    if (!(await writeText($, temp, item.text)) || !(await holds($, temp, digest)) || !(await moveInto($, temp, path))) {
      discard.push(temp)
      continue
    }
    const name = spillNameOf(item.tool_use_id)
    used -= sizes.get(name) ?? 0
    sizes.set(name, bytes)
    if (!(await holds($, path, digest))) {
      if (!named.has(item.tool_use_id)) discard.push(path)
      continue
    }
    fresh.push({ tool_use_id: item.tool_use_id, tool: item.tool, chars: item.text.length, sha256: digest, path, generation, confirmed: confirmed.has(item.tool_use_id) })
  }
  if (fresh.length > 0) {
    const manifest: Manifest = { sessionId, lastActivityAt: known?.lastActivityAt ?? 0, entries: mergeEntries(known?.entries ?? [], fresh) }
    const saved = await saveManifest($, root, manifest)
    if (!saved.ok) {
      const created = fresh.filter((entry) => !named.has(entry.tool_use_id)).map((entry) => entry.path)
      await removeAll($, [...discard, ...created, saved.temp])
      return spilled
    }
  }
  await removeAll($, discard)
  for (const entry of fresh) spilled.set(entry.tool_use_id, entry.path)
  return spilled
}

/**
 * Keeps each item verbatim at `<root>/<sessionId>/<tool_use_id>.txt` and answers `tool_use_id → path`
 * for the items that are on disk and in the manifest; an item left out keeps its original text.
 *
 * Per item: refused over 4 MiB of UTF-8, or when the session folder's files (every one: named, stray or
 * temporary) plus this item would pass 64 MiB; else written to a temporary file, read back there and
 * moved into place with `mv -f` only when that copy's sha256 matches (so a torn copy never replaces a
 * file the manifest names), then read back again and kept only when it still matches. A file already
 * there is written again, its mtime refreshed; from its move on, the 64 MiB counts its new bytes and no
 * longer those of the file it replaced. The kept items then go into the manifest with one
 * temporary write and one move, each as an unconfirmed entry unless it replaces one of its id, whose
 * `confirmed` it keeps. When that fails the answer is empty, and the spill files this call
 * created (not ones the manifest already named) and its temporary files are removed, the old manifest
 * left as it was. A manifest that is there but cannot be read makes the call write nothing; one that does
 * not parse is taken for none.
 *
 * Calls for one session run one at a time, `touchActivity`'s and `settleEntries`'s among them. The answer never rejects.
 */
export async function spillBatch($: SpillHost, root: string, sessionId: string, generation: number, items: readonly SpillItem[]): Promise<Map<string, string>> {
  return inSessionOrder(sessionId, () => writeBatch($, root, sessionId, generation, items)).catch(() => new Map<string, string>())
}

async function writeActivity($: SpillHost, root: string, sessionId: string, nowMs: number): Promise<void> {
  if (!isSafeName(sessionId)) return
  const previous = await readManifest($, root, sessionId)
  if (previous.state === 'unreadable') return
  const entries = previous.state === 'ok' ? previous.manifest.entries : []
  const saved = await saveManifest($, root, { sessionId, lastActivityAt: nowMs, entries })
  if (!saved.ok) await removeAll($, [saved.temp])
}

/**
 * Sets the session manifest's `lastActivityAt` to `nowMs`, its entries kept; writes one with no entries
 * when there is none, or none that parses. A manifest that is there but cannot be read is left alone.
 * Queued with the session's `spillBatch` and `settleEntries` calls. A failure leaves the manifest as it was and
 * does not reject.
 */
export async function touchActivity($: SpillHost, root: string, sessionId: string, nowMs: number): Promise<void> {
  await inSessionOrder(sessionId, () => writeActivity($, root, sessionId, nowMs)).catch(() => undefined)
}

async function rewriteEntries($: SpillHost, root: string, sessionId: string, confirm: readonly string[], drop: readonly string[]): Promise<boolean> {
  if (!isSafeName(sessionId)) return false
  const previous = await readManifest($, root, sessionId)
  if (previous.state !== 'ok') return false
  const confirming = new Set(confirm)
  const dropping = new Set(drop)
  const entries: ManifestEntry[] = []
  let changes = 0
  for (const entry of previous.manifest.entries) {
    if (dropping.has(entry.tool_use_id)) {
      changes += 1
      continue
    }
    const confirms = !entry.confirmed && confirming.has(entry.tool_use_id)
    if (confirms) changes += 1
    entries.push(confirms ? { ...entry, confirmed: true } : entry)
  }
  if (changes === 0) return true
  const saved = await saveManifestVerified($, root, { sessionId, lastActivityAt: previous.manifest.lastActivityAt, entries })
  if (!saved.ok) await removeAll($, [saved.temp])
  return saved.ok
}

/**
 * Records in one rewrite of the session's manifest what a compaction did with the results it spilled: the entries of
 * `drop` are taken out and those of `confirm` marked `confirmed` (an id in both is taken out), `lastActivityAt` and
 * every other entry kept as they were. The spill files stay: one named by no manifest is reclaimed by `cleanup` once
 * past 24 hours. Unlike the manifest writes of `spillBatch` and `touchActivity`, this one checks its copy: the new
 * manifest is written to a temporary file, read back there and moved into place with `mv -f` only when that copy's
 * sha256 matches; a failure removes the temporary file, leaves the manifest as it was and answers false. With nothing
 * to change (each id of `confirm` confirmed already or not named, none of `drop` named), nothing is written and the
 * answer is true; with no manifest, or one that does not parse or cannot be read now, nothing is written and the
 * answer is false.
 *
 * Queued with the session's `spillBatch` and `touchActivity` calls. The answer never rejects.
 */
export async function settleEntries($: SpillHost, root: string, sessionId: string, confirm: readonly string[], drop: readonly string[]): Promise<boolean> {
  return inSessionOrder(sessionId, () => rewriteEntries($, root, sessionId, confirm, drop)).catch(() => false)
}

/**
 * Removes spill files past their keep, file by file: a file its session's manifest names once older than
 * `retentionDays`, any other (temporary ones included) once older than 24 hours, each age read again with
 * `stat` right before. A manifest and its `<sessionId>.log.jsonl` go only when the session folder is left
 * empty and both its `lastActivityAt` and its mtime are past `retentionDays`; when this sweep's own removals
 * are what empty the folder, the two go in an `rm` after theirs, once every one of those files is gone, since
 * the manifest is what has a later sweep look into the folder again. The paths go to `rm -f` together, in
 * calls of at most 128 KiB of paths so a long backlog never makes one call that cannot start; `removed` is
 * what is gone after.
 *
 * Only what a readable manifest vouches for is looked into: the session folder beside it and that manifest's
 * temporary files. A name alone, one shaped like a session id included, proves nothing, so a spill root set
 * to a shared folder loses nothing of anyone else's; what a session left before its manifest ever landed (the
 * temporary files of a first spill that failed and could not be removed, say) stays, never reclaimed. A folder
 * whose manifest is there but cannot be read is left whole, its files not taken for unnamed ones. `retentionDays` is
 * taken as given (NaN keeps every named file). The session `liveSessionId` names (the caller's own, whose writes may
 * be under way) is passed over whole, as one with no manifest is: its folder, its manifest's temporary files, its
 * manifest and its log. Not queued with the writes: a file rewritten between its `stat` and the `rm` can still go,
 * and nothing keeps another process's sweep off the files a live session is rewriting.
 */
export async function cleanup($: SpillHost, root: string, nowMs: number, retentionDays: number, liveSessionId?: string): Promise<{ removed: string[] }> {
  const top = await listEntries($, root)
  if (top === null) return { removed: [] }
  const retentionMs = retentionDays * DAY_MS
  const manifests = new Map<string, { manifest: Manifest; mtimeMs: number }>()
  for (const entry of top) {
    if (entry.kind !== 'file' || !entry.name.endsWith(MANIFEST_EXT)) continue
    const sessionId = entry.name.slice(0, -MANIFEST_EXT.length)
    if (!isSafeName(sessionId) || sessionId === liveSessionId) continue
    const read = await readManifest($, root, sessionId)
    if (read.state === 'ok') manifests.set(sessionId, { manifest: read.manifest, mtimeMs: entry.mtimeMs })
  }
  const owned = (name: string): boolean => manifests.has(name)
  const doomed: string[] = []
  const occupied = new Set<string>()
  const emptied = new Map<string, string[]>()
  for (const entry of top) {
    if (entry.kind !== 'dir' || !owned(entry.name)) continue
    const folder = sessionFolderOf(root, entry.name)
    const files = await listEntries($, folder)
    if (files === null) {
      occupied.add(entry.name)
      continue
    }
    const named = new Set((manifests.get(entry.name)?.manifest.entries ?? []).map((item) => spillNameOf(item.tool_use_id)))
    const from = doomed.length
    let left = files.length
    for (const file of files) {
      const path = `${folder}/${file.name}`
      const limitMs = named.has(file.name) ? retentionMs : UNREFERENCED_GRACE_MS
      if (file.kind === 'file' && (await isExpired($, path, file.mtimeMs, nowMs, limitMs))) {
        doomed.push(path)
        left -= 1
      }
    }
    if (left > 0) occupied.add(entry.name)
    else if (doomed.length > from) emptied.set(entry.name, doomed.slice(from))
  }
  for (const entry of top) {
    const owner = manifestTempOwner(entry.name)
    if (entry.kind !== 'file' || owner === null || !owned(owner)) continue
    const path = `${root}/${entry.name}`
    if (await isExpired($, path, entry.mtimeMs, nowMs, UNREFERENCED_GRACE_MS)) doomed.push(path)
  }
  const names = new Set(top.map((entry) => entry.name))
  const waiting = new Map<string, string[]>()
  for (const [sessionId, { manifest, mtimeMs }] of manifests) {
    if (occupied.has(sessionId) || !(nowMs - manifest.lastActivityAt > retentionMs)) continue
    const path = manifestPathOf(root, sessionId)
    if (!(await isExpired($, path, mtimeMs, nowMs, retentionMs))) continue
    const paths = names.has(logNameOf(sessionId)) ? [path, logPathOf(root, sessionId)] : [path]
    if (emptied.has(sessionId)) waiting.set(sessionId, paths)
    else doomed.push(...paths)
  }
  const removed = await removeAll($, doomed)
  const gone = new Set(removed)
  const after: string[] = []
  for (const [sessionId, paths] of waiting) if ((emptied.get(sessionId) ?? []).every((path) => gone.has(path))) after.push(...paths)
  return { removed: [...removed, ...(await removeAll($, after))] }
}
