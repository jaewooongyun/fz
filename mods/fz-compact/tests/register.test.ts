import type { On, SessionMessage, SessionUsage } from 'claude-code'
import { test, expect, mock } from 'claude-code/testing'
import type { Engine, MockClock } from 'claude-code/testing'
import { placeholder } from '../lib/policy.ts'
import { loadManifest } from '../lib/spill.ts'
import type { Manifest, ManifestEntry } from '../lib/spill.ts'
import { engineFs } from './enginefs.ts'
import type { EngineFs } from './enginefs.ts'

const HOME = '/h'
/** Where the plugin spills with `spillDir` empty and HOME at `/h`. */
const ROOT = '/h/.claude/fz-compact/spill'
/** A link target with nothing at it: a link to it leads nowhere. */
const NOWHERE = '/nowhere'
const START = 1_700_000_000_000
const MINUTE = 60_000
const HOUR = 60 * MINUTE
/** The idle threshold of the tests that set `FZ_COMPACT_TEST_IDLE_MS`. */
const IDLE_MS = 20_000
/** The context size `$.session.usage()` reports unless a test sets `World.usage`: over the `idleMinTokens` default of 200000. */
const CONTEXT_TOKENS = 300_000
const BIG = 'x'.repeat(5000)
const OTHER = 'o'.repeat(3000)
const FOCUS = 'keep the plan'
const RESUME = 'fz-compact:resume'
const OFF_SKIP = 'fz-compact: off (enabled is false or a setting is invalid)'
/** The skip of a marked compaction the engine runs after a main-loop turn.start and before its turn.complete. */
const UNDER_WAY_SKIP = 'fz-compact: a main-loop turn started while this compaction waited in the queue, so the cache is in use again'
/** How the engine (the test's own `session.compact` hook) answers every compaction that reaches it. */
const ENGINE_SKIP = 'engine compaction'
const GUIDANCE = [
  'fz-compact guidance (appended after any user focus, which takes priority):',
  "- Keep verbatim: the user's goal and every explicit constraint, approval or correction.",
  '- Keep: decisions with reasons, rejected alternatives, failed attempts, verification commands with outcomes, error diagnoses, open questions, the next action.',
  '- Keep exact anchors: file paths with line numbers, symbols, ticket IDs, artifact and checkpoint paths.',
  '- Summarize bulky tool output by what it established; keep any result the next action depends on.',
].join('\n')
/** Settings the transcripts below fit: one recent prompt kept, results from 100 characters, any saving enough. */
const SMALL = { enabled: true, keepRecentUserTurns: 1, minMaskChars: 100, minNetReductionPercent: 0, minNetReductionTokens: 0 } as const
/** SMALL, but a masking must save half the transcript: BIG's does under a short newest prompt, not under a long one. */
const HALF = { ...SMALL, minNetReductionPercent: 50 } as const
/** SMALL, but a masking must save 10000 tokens: no result here saves that much on its own. */
const STRICT = { ...SMALL, minNetReductionTokens: 10_000 } as const
/** SMALL, but a context under 5000 tokens is too small to mask anew on a resume: twoReads' rows are about 2020 tokens. */
const SMALL_CONTEXT = { ...SMALL, idleMinTokens: 5000 } as const

type Verdict = { decision: 'allow' | 'ask' | 'deny'; reason?: string; rule?: string }

/** The two settings a saving is weighed against. */
type Saving = { minNetReductionPercent: number; minNetReductionTokens: number }

/**
 * The engine beneath the plugin, as the test's hooks answer it, and what they saw. `commands` holds the arguments
 * of each `/compact` the plugin queued; `compacts` and `compactRows` the `instructions` and the rows (`shapeOf`) of
 * each compaction that reached the engine; `logs` each `$.ui.log` line. `rows` is what `$.session.messages()`
 * answers (a call with or without an argument object), `usage` what `$.session.usage()` answers
 * (`usageOf(CONTEXT_TOKENS)` until a test sets another), `verdict` the engine's `tool.check` answer.
 */
type World = {
  sessionId: string
  disk: EngineFs
  commands: string[]
  compacts: (string | undefined)[]
  compactRows: string[][]
  logs: string[]
  rows: SessionMessage[]
  usage: SessionUsage
  verdict: Verdict
}

/**
 * A prompt, a Read and its BIG result, then the newest prompt: with one recent prompt kept, that result is the one
 * to mask. A long `prompt` makes it a small part of the transcript.
 */
function transcript(prompt = 'now summarize it'): SessionMessage[] {
  return [
    { role: 'user', text: 'read the file', toolUses: [] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'r1', tool: 'Read', input: { file_path: '/w/a.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r1', text: BIG, isError: false }] },
    { role: 'user', text: prompt, toolUses: [] },
    { role: 'assistant', text: 'done', toolUses: [] },
  ]
}

/** Two Reads before the newest prompt: r1 with BIG at row 2, r2 with OTHER at row 4, both eligible to mask. */
function twoReads(): SessionMessage[] {
  return [
    { role: 'user', text: 'read both files', toolUses: [] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'r1', tool: 'Read', input: { file_path: '/w/a.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r1', text: BIG, isError: false }] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'r2', tool: 'Read', input: { file_path: '/w/b.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r2', text: OTHER, isError: false }] },
    { role: 'user', text: 'now compare them', toolUses: [] },
    { role: 'assistant', text: 'done', toolUses: [] },
  ]
}

function spillPathOf(sessionId: string, toolUseId: string): string {
  return `${ROOT}/${sessionId}/${toolUseId}.txt`
}

function manifestPathOf(sessionId: string): string {
  return `${ROOT}/${sessionId}.json`
}

/** A manifest file's text naming `entries` (none by default), last active at `lastActivityAt`. */
function manifestText(sessionId: string, lastActivityAt: number, entries: ManifestEntry[] = []): string {
  const manifest: Manifest = { sessionId, lastActivityAt, entries }
  return JSON.stringify(manifest)
}

/** r1's entry as an earlier process left it after spilling BIG and handing its placeholder back: confirmed. */
function knownEntry(sessionId: string): ManifestEntry {
  return { tool_use_id: 'r1', tool: 'Read', chars: BIG.length, sha256: '0', path: spillPathOf(sessionId, 'r1'), generation: 0, confirmed: true }
}

/** The tool_use_ids the session's manifest names, in order, read as the plugin reads it; none without one. */
async function manifestIds(w: World): Promise<string[]> {
  const manifest = await loadManifest(w.disk, ROOT, w.sessionId)
  return (manifest?.entries ?? []).map((entry) => entry.tool_use_id)
}

/** Each entry of the session's manifest as `<tool_use_id>:<confirmed>`, in order; none without one. */
async function confirmations(w: World): Promise<string[]> {
  const manifest = await loadManifest(w.disk, ROOT, w.sessionId)
  return (manifest?.entries ?? []).map((entry) => `${entry.tool_use_id}:${entry.confirmed}`)
}

/** The text of the first tool result of row `index` (2: r1's in both transcripts) in a compaction's answer. */
function maskedRowText(result: { messages?: readonly SessionMessage[] }, index = 2): string | undefined {
  return result.messages?.[index]?.toolResults?.[0]?.text
}

/** Each row as its role, text and tool results, the engine's handles left out, to compare two transcripts. */
function shapeOf(rows: readonly SessionMessage[] | undefined): string[] {
  return (rows ?? []).map((row) => [row.role, row.text, ...(row.toolResults ?? []).map((result) => `${result.tool_use_id}=${result.text}`)].join('|'))
}

/** The rows rebuilt as plain messages with no handle, to hand back to the engine as a new transcript. */
function plain(rows: readonly SessionMessage[]): SessionMessage[] {
  return rows.map((row) => {
    const toolUses = (row.toolUses ?? []).map((use) => ({ tool_use_id: use.tool_use_id, tool: use.tool, input: use.input }))
    if (row.toolResults === undefined) return { role: row.role, text: row.text, toolUses }
    return { role: row.role, text: row.text, toolUses, toolResults: row.toolResults.map((result) => ({ tool_use_id: result.tool_use_id, text: result.text, isError: result.isError })) }
  })
}

/** Every row's text, every tool call's arguments as JSON and every tool result's text, in characters: what a saving is weighed against. */
function charsOf(rows: readonly SessionMessage[]): number {
  let total = 0
  for (const row of rows) {
    total += row.text.length
    for (const use of row.toolUses ?? []) total += JSON.stringify(use.input).length
    for (const result of row.toolResults ?? []) total += result.text.length
  }
  return total
}

/**
 * Why masking one Read result, `chars` characters under `toolUseId`, saves too little in `rows` under `saving`: its
 * characters less its placeholder's, against `charsOf(rows)`.
 */
function shortfallReason(sessionId: string, rows: readonly SessionMessage[], toolUseId: string, chars: number, saving: Saving): string {
  const saved = chars - placeholder('Read', chars, spillPathOf(sessionId, toolUseId)).length
  return `masking would save ${saved} of ${charsOf(rows)} chars, under ${saving.minNetReductionPercent}% or ${saving.minNetReductionTokens} tokens`
}

/** What `$.session.usage()` answers for a context of `tokens`, or for one that reports no size when `tokens` is undefined. */
function usageOf(tokens: number | undefined): SessionUsage {
  return { startedAt: START, context: tokens === undefined ? { window: 1_000_000 } : { tokens, window: 1_000_000 }, rateLimits: [] }
}

/**
 * Stands the engine beneath the plugin: the memory file system, the session's id, rows and usage, the queued
 * commands, the log, and the bottom of every event the tests raise. Clock and environment are each test's own.
 * Call it before the test's first call on `$`.
 */
function world(on: On, sessionId: string, now: () => number): World {
  const w: World = {
    sessionId,
    disk: engineFs(on, now),
    commands: [],
    compacts: [],
    compactRows: [],
    logs: [],
    rows: [],
    usage: usageOf(CONTEXT_TOKENS),
    verdict: { decision: 'ask', reason: 'engine asks' },
  }
  on('session.id', () => ({ value: sessionId }))
  on('session.messages', (_, e) => ({ value: e?.as === 'api' ? [] : w.rows }))
  on('session.usage', () => ({ value: w.usage }))
  on('ui.log', (_, e) => {
    w.logs.push(e.text)
    return { value: undefined }
  })
  on('command.run', (_, e) => {
    w.commands.push(e.args)
    return { text: '' }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', (_, e) => ({ text: e.answer }))
  on('session.compact', (_, e) => {
    w.compacts.push(e.instructions)
    w.compactRows.push(shapeOf(e.messages))
    return { skip: ENGINE_SKIP }
  })
  on('tool.check', () => ({ ...w.verdict }))
  return w
}

/**
 * Records the wait of every `$.clock.after` the plugin asks for and hands it on. Register it before `mock.clock`:
 * it then stands above the clock's own hook, its matcher (any `ms`) letting the two share the event.
 */
function countTimers(on: On): number[] {
  const timers: number[] = []
  on('clock.after', { ms: /^/ }, (_, e, next) => {
    timers.push(e.ms)
    return next(e)
  })
  return timers
}

/** Moves the mocked clock on, then lets what that set going settle. */
async function pass(clock: MockClock, ms: number): Promise<void> {
  await clock.advance(ms)
  await clock.settle()
}

async function startSession($: Engine): Promise<void> {
  await $.session.start({ cwd: '/w', surface: null, isInteractive: false })
}

/** One main-loop turn, its start and its end: what a person's prompt raises. */
async function mainTurn($: Engine, turnId: string): Promise<void> {
  await $.turn.start({ text: 'go on', turnId })
  await $.turn.complete({ answer: 'done', durationMs: 1, isAborted: false, turnId, reason: 'answer' })
}

async function checkRead($: Engine, filePath: string): Promise<{ decision: string; reason?: string; rule?: string }> {
  return $.tool.check({ tool: 'Read', input: { file_path: filePath } })
}

/**
 * One threshold, both places it is read, after the main turn of `generation`. The timer: one millisecond short of
 * `thresholdMs` nothing is queued, and at it `/compact fz-compact:idle:<generation>` is. The recheck: that same
 * marker, run one millisecond short of the threshold, is refused, and run at it masks.
 */
async function checkThreshold($: Engine, clock: MockClock, w: World, messages: readonly SessionMessage[], thresholdMs: number, generation: number): Promise<void> {
  const marker = `fz-compact:idle:${generation}`
  const before = w.commands.length
  await mainTurn($, `t${generation}`)
  await clock.settle()
  await pass(clock, thresholdMs - 1)
  expect(w.commands.slice(before)).toEqual([])
  const early = await $.session.compact({ trigger: 'manual', instructions: marker, messages })
  expect(early.skip).toBe(`fz-compact: the session was active ${thresholdMs - 1} ms ago, under the ${thresholdMs} ms idle threshold`)
  await pass(clock, 1)
  expect(w.commands.slice(before)).toEqual([marker])
  const onTime = await $.session.compact({ trigger: 'manual', instructions: marker, messages })
  expect(onTime.skip).toBeUndefined()
  expect(maskedRowText(onTime)).toBe(placeholder('Read', BIG.length, spillPathOf(w.sessionId, 'r1')))
}

/**
 * Resumed 8000 ms short of the idle threshold, its manifest naming nothing: no remask is queued, and the idle timer of
 * generation 0 fires for the rest and queues `fz-compact:idle:0`. That compaction runs before any main turn, so a
 * resume marker can still run after it in this activation. Needs `FZ_COMPACT_TEST_IDLE_MS` at `IDLE_MS`.
 */
async function idleBeforeAnyTurn($: Engine, clock: MockClock, w: World): Promise<void> {
  const lastActive = START - (IDLE_MS - 8000)
  w.rows = transcript()
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, lastActive), lastActive)
  await startSession($)
  await clock.settle()
  await pass(clock, 8000)
  expect(w.commands).toEqual(['fz-compact:idle:0'])
}

test('register: decision table', { options: HALF }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'decision-table', () => clock.now())
  const messages = transcript()
  const longPrompt = transcript('y'.repeat(20_000))
  const spilled = spillPathOf(w.sessionId, 'r1')
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([])

  // agentId, then precompute: handed to the engine as they came, instructions and rows alike.
  const agentMarked = await $.session.compact({ trigger: 'manual', agentId: 'a1', instructions: RESUME, messages })
  const agentAuto = await $.session.compact({ trigger: 'auto', agentId: 'a1', instructions: FOCUS, messages })
  const precomputed = await $.session.compact({ trigger: 'precompute', instructions: FOCUS, messages })
  expect([agentMarked.skip, agentAuto.skip, precomputed.skip]).toEqual([ENGINE_SKIP, ENGINE_SKIP, ENGINE_SKIP])
  expect(w.compacts).toEqual([RESUME, FOCUS, FOCUS])
  expect(w.compactRows).toEqual([shapeOf(messages), shapeOf(messages), shapeOf(messages)])
  expect(w.disk.files.has(spilled)).toBe(false)

  // manual with the marker, saving under minNetReductionPercent: skipped before any spill file is written.
  const thin = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: longPrompt })
  expect(thin.skip).toBe(`fz-compact: ${shortfallReason(w.sessionId, longPrompt, 'r1', BIG.length, HALF)}`)
  expect(w.disk.calls.some((call) => call.startsWith(`write ${spilled}`))).toBe(false)

  // manual with the marker, saving enough: masked by the plugin, BIG kept in its spill file.
  const masked = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  await clock.settle()
  expect(masked.skip).toBeUndefined()
  expect(masked.messages).toHaveLength(messages.length)
  expect(masked.messages?.[0]?.text).toBe('read the file')
  expect(maskedRowText(masked)).toBe(placeholder('Read', BIG.length, spilled))
  expect(w.disk.files.get(spilled)?.text).toBe(BIG)
  expect(w.logs.some((line) => line.startsWith('fz-compact masked:'))).toBe(true)

  // manual with a stale idle marker: skipped, and none of the marked ones reached the engine.
  const stale = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:7', messages })
  expect(stale.skip).toBe('fz-compact: generation 7 is stale; the session is at 0')
  expect(w.compacts).toHaveLength(3)

  // manual without the marker, auto and plugin: the engine's, the guidance after any focus.
  const guided = [
    await $.session.compact({ trigger: 'manual', messages }),
    await $.session.compact({ trigger: 'manual', instructions: FOCUS, messages }),
    await $.session.compact({ trigger: 'auto', messages }),
    await $.session.compact({ trigger: 'auto', instructions: RESUME, messages }),
    await $.session.compact({ trigger: 'plugin', instructions: FOCUS, messages }),
  ]
  expect(guided.map((result) => result.skip)).toEqual([ENGINE_SKIP, ENGINE_SKIP, ENGINE_SKIP, ENGINE_SKIP, ENGINE_SKIP])
  expect(w.compacts.slice(3)).toEqual([GUIDANCE, `${FOCUS}\n\n${GUIDANCE}`, GUIDANCE, `${RESUME}\n\n${GUIDANCE}`, `${FOCUS}\n\n${GUIDANCE}`])
})

test('register: disabled does nothing', { options: { enabled: false } }, async ($, on) => {
  const timers = countTimers(on)
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'disabled', () => clock.now())
  w.rows = transcript()
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START - 2 * HOUR), START)
  const messages = transcript()

  // A resumed background session, long idle, then a main turn and two more hours: all a timer or a remask waits on.
  await startSession($)
  await clock.settle()
  await mainTurn($, 't1')
  await pass(clock, 2 * HOUR)
  const marked = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  const focused = await $.session.compact({ trigger: 'manual', instructions: FOCUS, messages })
  const auto = await $.session.compact({ trigger: 'auto', messages })
  await clock.settle()

  expect(marked.skip).toBe(OFF_SKIP)
  expect([focused.skip, auto.skip]).toEqual([ENGINE_SKIP, ENGINE_SKIP])
  expect(w.compacts.map((text) => text ?? '')).toEqual([FOCUS, ''])
  expect(w.commands).toEqual([])
  expect(timers).toEqual([])
  expect(w.disk.calls.filter((call) => call.startsWith('write ') || call.startsWith('run '))).toEqual([])
  // The cleanup still reads the spill root.
  expect(w.disk.calls).toContain(`list ${ROOT}`)
})

test('register: stale generation skips', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'stale-generation', () => clock.now())
  const messages = transcript()
  const spilled = spillPathOf(w.sessionId, 'r1')
  await startSession($)
  await mainTurn($, 't1')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])

  // Another turn completes before the queue reaches that /compact, and the session idles past the threshold again.
  await mainTurn($, 't2')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1', 'fz-compact:idle:2'])

  // The idle time holds for both markers; only the current generation masks.
  const stale = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(stale.skip).toBe('fz-compact: generation 1 is stale; the session is at 2')
  expect(w.disk.files.has(spilled)).toBe(false)
  const current = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:2', messages })
  expect(current.skip).toBeUndefined()
  expect(maskedRowText(current)).toBe(placeholder('Read', BIG.length, spilled))
  expect(w.compacts).toEqual([])
})

test('register: user activity after queue skips', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'user-activity', () => clock.now())
  const messages = transcript()
  await startSession($)
  await mainTurn($, 't1')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])

  // The person sends a prompt while that /compact waits in the queue; the turn runs past the threshold.
  await $.turn.start({ text: 'one more thing', turnId: 't2' })
  await pass(clock, IDLE_MS)
  await $.turn.complete({ answer: 'done', durationMs: IDLE_MS, isAborted: false, turnId: 't2', reason: 'answer' })
  await clock.settle()
  const queued = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(queued.skip).toBe('fz-compact: generation 1 is stale; the session is at 2')
  expect(w.disk.files.has(spillPathOf(w.sessionId, 'r1'))).toBe(false)
  expect(w.compacts).toEqual([])

  // A prompt that arrives before the next timer is due disarms it: nothing more is queued.
  await pass(clock, IDLE_MS - 1)
  await $.turn.start({ text: 'and another', turnId: 't3' })
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])
})

test('register: compaction run before the turn ends skips', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'turn-under-way', () => clock.now())
  const messages = transcript()
  await startSession($)
  await mainTurn($, 't1')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])

  // The order a background session showed: a prompt queued just before the /compact, its turn ran, and the engine
  // ran the /compact as that turn ended, before this plugin's turn.complete moved the generation on.
  await $.turn.start({ text: 'one more thing', turnId: 't2' })
  const during = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(during.skip).toBe(UNDER_WAY_SKIP)
  expect(w.disk.files.has(spillPathOf(w.sessionId, 'r1'))).toBe(false)

  // The mark ends with its turn: the next idle period masks.
  await $.turn.complete({ answer: 'done', durationMs: 1, isAborted: false, turnId: 't2', reason: 'answer' })
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1', 'fz-compact:idle:2'])
  const idle = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:2', messages })
  expect(maskedRowText(idle)).toBe(placeholder('Read', BIG.length, spillPathOf(w.sessionId, 'r1')))
  expect(w.compacts).toEqual([])
})

test('register: repeated resume idempotent', { options: STRICT }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'repeated-resume', () => clock.now())
  const spilled = spillPathOf(w.sessionId, 'r1')
  const messages = twoReads()
  w.rows = twoReads()
  // Before the restart r1 was masked and spilled; r2 never was.
  w.disk.put(spilled, BIG, START - 2 * HOUR)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START - 2 * HOUR, [knownEntry(w.sessionId)]), START - 2 * HOUR)
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])

  const first = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  const afterFirst = await manifestIds(w)
  const second = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  const afterSecond = await manifestIds(w)

  // r1, which the manifest names, is masked again under minNetReductionTokens; r2 must pass it alone and does not.
  expect(maskedRowText(first, 2)).toBe(placeholder('Read', BIG.length, spilled))
  expect(maskedRowText(first, 4)).toBe(OTHER)
  const stays = shortfallReason(w.sessionId, messages, 'r2', OTHER.length, STRICT)
  expect(w.logs.some((line) => line.startsWith(`fz-compact masked: masked 1 rows; results not masked before stay (${stays})`))).toBe(true)
  expect(shapeOf(second.messages)).toEqual(shapeOf(first.messages))
  expect(afterFirst).toEqual(['r1'])
  expect(afterSecond).toEqual(afterFirst)
  expect(w.disk.files.get(spilled)?.text).toBe(BIG)
  expect(w.disk.files.has(spillPathOf(w.sessionId, 'r2'))).toBe(false)

  // Run over its own answer: r1 is a placeholder already, and r2 alone still saves too little.
  const own = plain(first.messages ?? [])
  const again = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: own })
  expect(again.skip).toBe(`fz-compact: ${shortfallReason(w.sessionId, own, 'r2', OTHER.length, STRICT)}`)
  expect(await manifestIds(w)).toEqual(['r1'])
  expect(w.compacts).toEqual([])
})

test('register: partial spill rechecks the saving', { options: STRICT }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'partial-spill', () => clock.now())
  // r1's result saves over minNetReductionTokens, with r2's or alone; r2's alone saves under it.
  const huge = 'h'.repeat(60_000)
  const messages = twoReads()
  messages[2] = { ...messages[2], toolResults: [{ tool_use_id: 'r1', text: huge, isError: false }] }
  await startSession($)
  await mainTurn($, 't1')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])

  // r1's spill fails and r2's lands: the saving is weighed again on r2 alone, falls short, and every original stays.
  w.disk.failWrite = (path) => path.startsWith(`${spillPathOf(w.sessionId, 'r1')}.tmp-`)
  const failed = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(failed.skip).toBe(`fz-compact: after spill failures, ${shortfallReason(w.sessionId, messages, 'r2', OTHER.length, STRICT)}`)
  expect(failed.messages).toBeUndefined()
  expect(w.disk.files.has(spillPathOf(w.sessionId, 'r1'))).toBe(false)
  // r2's spill file stays until cleanup, but no answer masked it, so its manifest entry is taken out.
  expect(w.disk.files.get(spillPathOf(w.sessionId, 'r2'))?.text).toBe(OTHER)
  expect(await manifestIds(w)).toEqual([])

  // Both spill: masked as before, and both stay in the manifest.
  w.disk.failWrite = () => false
  const masked = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(masked.skip).toBeUndefined()
  expect(maskedRowText(masked, 2)).toBe(placeholder('Read', huge.length, spillPathOf(w.sessionId, 'r1')))
  expect(maskedRowText(masked, 4)).toBe(placeholder('Read', OTHER.length, spillPathOf(w.sessionId, 'r2')))
  expect(await manifestIds(w)).toEqual(['r1', 'r2'])
  expect(w.compacts).toEqual([])
})

test('register: partial spill counts only whole rows', { options: STRICT }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'partial-rows', () => clock.now())
  // ra and rb share row 2, rc has row 4 alone. Counted with rb's, rc's saving passes minNetReductionTokens; alone it falls short.
  const huge = 'h'.repeat(60_000)
  const wide = 'w'.repeat(40_000)
  const messages: SessionMessage[] = [
    { role: 'user', text: 'read the files', toolUses: [] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'ra', tool: 'Read', input: { file_path: '/w/a.txt' } }, { tool_use_id: 'rb', tool: 'Read', input: { file_path: '/w/b.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'ra', text: huge, isError: false }, { tool_use_id: 'rb', text: wide, isError: false }] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'rc', tool: 'Read', input: { file_path: '/w/c.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'rc', text: OTHER, isError: false }] },
    { role: 'user', text: 'now compare them', toolUses: [] },
    { role: 'assistant', text: 'done', toolUses: [] },
  ]
  await startSession($)
  await mainTurn($, 't1')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])

  // ra's spill fails, so row 2 keeps its originals and rb's spilled copy saves nothing: rc is weighed alone and falls short.
  w.disk.failWrite = (path) => path.startsWith(`${spillPathOf(w.sessionId, 'ra')}.tmp-`)
  const failed = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(failed.skip).toBe(`fz-compact: after spill failures, ${shortfallReason(w.sessionId, messages, 'rc', OTHER.length, STRICT)}`)
  expect(failed.messages).toBeUndefined()
  // rb and rc keep their spill files until cleanup, and neither stays in the manifest.
  expect(w.disk.files.get(spillPathOf(w.sessionId, 'rb'))?.text).toBe(wide)
  expect(w.disk.files.get(spillPathOf(w.sessionId, 'rc'))?.text).toBe(OTHER)
  expect(await manifestIds(w)).toEqual([])
  expect(w.compacts).toEqual([])
})

test('register: idle settle keeps entries named before', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'idle-named', () => clock.now())
  // r1 and rx share row 2. r1 was masked before, so the manifest names it; its original is back in the rows.
  const messages: SessionMessage[] = [
    { role: 'user', text: 'read the files', toolUses: [] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'r1', tool: 'Read', input: { file_path: '/w/a.txt' } }, { tool_use_id: 'rx', tool: 'Read', input: { file_path: '/w/x.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r1', text: BIG, isError: false }, { tool_use_id: 'rx', text: OTHER, isError: false }] },
    { role: 'user', text: 'now compare them', toolUses: [] },
    { role: 'assistant', text: 'done', toolUses: [] },
  ]
  await startSession($)
  await mainTurn($, 't1')
  await clock.settle()
  await pass(clock, IDLE_MS)
  expect(w.commands).toEqual(['fz-compact:idle:1'])
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [knownEntry(w.sessionId)]), START)

  // rx's spill fails, so row 2 keeps its originals and r1 is not carried; r1's entry predates this compaction and stays.
  w.disk.failWrite = (path) => path.startsWith(`${spillPathOf(w.sessionId, 'rx')}.tmp-`)
  const failed = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:1', messages })
  expect(failed.skip).toBe('fz-compact: no row had all its results spilled, so every original is kept')
  expect(await manifestIds(w)).toEqual(['r1'])
})

test('register: failed settle leaves the result to the saving check', { options: HALF }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'settle-unconfirmed', () => clock.now())
  const manifestPath = manifestPathOf(w.sessionId)
  // r1 and rx share row 2: masking both saves over half the transcript.
  const shared: SessionMessage[] = [
    { role: 'user', text: 'read the files', toolUses: [] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'r1', tool: 'Read', input: { file_path: '/w/a.txt' } }, { tool_use_id: 'rx', tool: 'Read', input: { file_path: '/w/x.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r1', text: BIG, isError: false }, { tool_use_id: 'rx', text: OTHER, isError: false }] },
    { role: 'user', text: 'now compare them', toolUses: [] },
    { role: 'assistant', text: 'done', toolUses: [] },
  ]
  await idleBeforeAnyTurn($, clock, w)

  // rx's spill fails, so row 2 keeps its originals and r1 is spilled but not carried. Taking r1 out of the manifest
  // fails too: the rewrite's copy cannot be read back.
  w.disk.failWrite = (path) => path.startsWith(`${spillPathOf(w.sessionId, 'rx')}.tmp-`)
  w.disk.failRead = (path) => path.startsWith(`${manifestPath}.tmp-`)
  const idle = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:0', messages: shared })
  w.disk.failWrite = () => false
  w.disk.failRead = () => false
  expect(idle.skip).toBe('fz-compact: no row had all its results spilled, so every original is kept')
  expect(w.logs.some((line) => line.startsWith('fz-compact: the manifest could not be updated for 1 spilled results'))).toBe(true)
  // r1 is still named, but no compaction confirmed handing it back.
  expect(await confirmations(w)).toEqual(['r1:false'])

  // Resumed past the threshold: r1 must pass the saving check alone, and under a long newest prompt it does not.
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual(['fz-compact:idle:0', RESUME])
  const longPrompt = transcript('y'.repeat(20_000))
  const resumed = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: longPrompt })
  expect(resumed.skip).toBe(`fz-compact: ${shortfallReason(w.sessionId, longPrompt, 'r1', BIG.length, HALF)}`)
  expect(resumed.messages).toBeUndefined()
  expect(w.compacts).toEqual([])
})

test('register: carried results are confirmed for resume', { options: HALF }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'settle-confirm', () => clock.now())
  const spilled = spillPathOf(w.sessionId, 'r1')
  await idleBeforeAnyTurn($, clock, w)

  // The idle compaction hands r1 back as its placeholder, and the manifest marks it confirmed.
  const idle = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:0', messages: transcript() })
  expect(maskedRowText(idle)).toBe(placeholder('Read', BIG.length, spilled))
  expect(await confirmations(w)).toEqual(['r1:true'])

  // Resumed past the threshold under a long newest prompt, which r1 alone would not pass: it is masked again all the same.
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual(['fz-compact:idle:0', RESUME])
  const resumed = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: transcript('y'.repeat(20_000)) })
  expect(resumed.skip).toBeUndefined()
  expect(maskedRowText(resumed)).toBe(placeholder('Read', BIG.length, spilled))
  expect(await confirmations(w)).toEqual(['r1:true'])
  expect(w.compacts).toEqual([])
})

test('register: start sweep keeps the live session spill', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'live-sweep', () => clock.now())
  w.rows = transcript()
  // This session and another, each last active and spilled 31 days ago: past spillRetentionDays (30).
  const expired = START - 31 * 24 * HOUR
  const other = 'other-sweep'
  const spilled = spillPathOf(w.sessionId, 'r1')
  const otherSpilled = spillPathOf(other, 'r1')
  w.disk.put(spilled, BIG, expired)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, expired, [knownEntry(w.sessionId)]), expired)
  w.disk.put(otherSpilled, BIG, expired)
  w.disk.put(manifestPathOf(other), manifestText(other, expired, [knownEntry(other)]), expired)
  await startSession($)
  await clock.settle()

  // The start queued the remask and swept: the other session's spill file and manifest are gone.
  expect(w.commands).toEqual([RESUME])
  expect(`${w.disk.files.has(otherSpilled)}|${w.disk.files.has(manifestPathOf(other))}`).toBe('false|false')
  // This session's, which that remask writes again, stay.
  expect(w.disk.files.get(spilled)?.text).toBe(BIG)
  expect(await manifestIds(w)).toEqual(['r1'])
})

test('register: resume drops repeated rows', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'resume-repeats', () => clock.now())
  const spilled = spillPathOf(w.sessionId, 'r1')
  const shown = placeholder('Read', BIG.length, spilled)
  w.rows = transcript()
  // Before the restart r1 was masked and spilled, and the compaction's copies were stored under the originals' ids.
  w.disk.put(spilled, BIG, START - 2 * HOUR)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START - 2 * HOUR, [knownEntry(w.sessionId)]), START - 2 * HOUR)
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])

  // The resume hands each stored row back once per copy: the Read call twice, r1's result as BIG and as its
  // placeholder, and the last answer twice.
  const rows = transcript()
  const repeated: SessionMessage[] = [
    rows[0],
    rows[1],
    ...plain([rows[1]]),
    rows[2],
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r1', text: shown, isError: false }] },
    rows[3],
    rows[4],
    ...plain([rows[4]]),
  ]
  const first = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: repeated })
  const want = transcript()
  want[2] = { ...want[2], toolResults: [{ tool_use_id: 'r1', text: shown, isError: false }] }
  expect(first.skip).toBeUndefined()
  expect(shapeOf(first.messages)).toEqual(shapeOf(want))
  expect((first.messages ?? []).flatMap((row) => (row.toolResults ?? []).filter((result) => result.tool_use_id === 'r1').map((result) => result.text))).toEqual([shown])
  expect(w.logs.some((line) => line.startsWith('fz-compact masked: masked 1 rows; dropped 3 repeated rows (') && line.includes(`tool results ${BIG.length + shown.length} -> ${shown.length} chars`))).toBe(true)

  // Its own answer resumed the same way: every result a placeholder already, only the repeats to drop.
  const own = plain(first.messages ?? [])
  const again = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: plain([own[0], own[1], own[1], own[2], own[2], own[3], own[4], own[4]]) })
  expect(again.skip).toBeUndefined()
  expect(shapeOf(again.messages)).toEqual(shapeOf(first.messages))
  expect(w.logs.some((line) => line.startsWith('fz-compact deduped: dropped 3 repeated rows; no tool result to mask (') && line.includes(`tool results ${2 * shown.length} -> ${shown.length} chars`))).toBe(true)
  expect(w.compacts).toEqual([])
})

test('register: resume after a main turn skips', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'resume-after-turn', () => clock.now())
  w.rows = transcript()
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START - 2 * HOUR), START - 2 * HOUR)
  const messages = transcript()
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])

  // A main turn starts before the queue reaches the remask, which the engine can then run as that turn ends.
  await $.turn.start({ text: 'go on', turnId: 't1' })
  const during = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  expect(during.skip).toBe(UNDER_WAY_SKIP)

  // Once that turn has completed, the generation has moved on too.
  await $.turn.complete({ answer: 'done', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer' })
  await clock.settle()
  const late = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  expect(late.skip).toBe('fz-compact: a main turn already ran in this process (generation 1), so the cache holds the originals again')
  expect(w.disk.files.has(spillPathOf(w.sessionId, 'r1'))).toBe(false)
  expect(w.compacts).toEqual([])
})

test('register: warm resume arms the idle timer', { options: SMALL }, async ($, on) => {
  const timers = countTimers(on)
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME, FZ_COMPACT_TEST_IDLE_MS: String(IDLE_MS) })
  const w = world(on, 'warm-resume', () => clock.now())
  const messages = transcript()
  w.rows = transcript()
  // Resumed 8000 ms short of the threshold, the manifest naming a spilled result: the remask is queued and the timer armed for the rest.
  const named = START - (IDLE_MS - 8000)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, named, [knownEntry(w.sessionId)]), named)
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])
  expect(timers).toEqual([8000])

  // Started again 5000 ms short, the manifest naming none: no remask, and a timer for the rest in place of the first.
  const lastActive = START - (IDLE_MS - 5000)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, lastActive), lastActive)
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])
  expect(timers).toEqual([8000, 5000])
  await pass(clock, 4999)
  expect(w.commands).toEqual([RESUME])
  await pass(clock, 1)
  expect(w.commands).toEqual([RESUME, 'fz-compact:idle:0'])
  const idle = await $.session.compact({ trigger: 'manual', instructions: 'fz-compact:idle:0', messages })
  expect(idle.skip).toBeUndefined()
  expect(maskedRowText(idle)).toBe(placeholder('Read', BIG.length, spillPathOf(w.sessionId, 'r1')))
  expect(w.compacts).toEqual([])
})

test('register: idle threshold shared by timer and recheck', { options: SMALL }, async ($, on) => {
  const timers = countTimers(on)
  const clock = mock.clock(on, { now: START })
  const env: Record<string, string> = { CLAUDE_CODE_SESSION_KIND: 'bg', HOME }
  on('env.get', (_, e) => ({ value: env[e.name] }))
  const w = world(on, 'idle-threshold', () => clock.now())
  const messages = transcript()
  await startSession($)
  await clock.settle()

  // idleGuardMinutes (61) with no override, then FZ_COMPACT_TEST_IDLE_MS.
  await checkThreshold($, clock, w, messages, 61 * MINUTE, 1)
  env.FZ_COMPACT_TEST_IDLE_MS = String(IDLE_MS)
  await checkThreshold($, clock, w, messages, IDLE_MS, 2)
  expect(timers).toEqual([61 * MINUTE, IDLE_MS])
  expect(w.commands).toEqual(['fz-compact:idle:1', 'fz-compact:idle:2'])
})

test('register: saving check counts tool call arguments', { options: HALF }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'tool-arguments', () => clock.now())
  const spilled = spillPathOf(w.sessionId, 'r1')
  // A Write whose content is twice BIG, then a Read and its BIG result: BIG is most of the text and tool results, not of the conversation.
  const messages: SessionMessage[] = [
    { role: 'user', text: 'write the file, then read the other', toolUses: [] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'w1', tool: 'Write', input: { file_path: '/w/b.txt', content: 'c'.repeat(2 * BIG.length) } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'w1', text: 'wrote /w/b.txt', isError: false }] },
    { role: 'assistant', text: '', toolUses: [{ tool_use_id: 'r1', tool: 'Read', input: { file_path: '/w/a.txt' } }] },
    { role: 'user', text: '', toolUses: [], toolResults: [{ tool_use_id: 'r1', text: BIG, isError: false }] },
    { role: 'user', text: 'now summarize it', toolUses: [] },
    { role: 'assistant', text: 'done', toolUses: [] },
  ]
  await startSession($)
  await clock.settle()

  // Against the text and tool results alone, masking BIG would save over half (HALF's 50%); the Write's arguments make it fall short.
  let textAndResults = 0
  for (const row of messages) {
    textAndResults += row.text.length
    for (const result of row.toolResults ?? []) textAndResults += result.text.length
  }
  const saved = BIG.length - placeholder('Read', BIG.length, spilled).length
  expect(saved * 100 >= textAndResults * HALF.minNetReductionPercent).toBe(true)
  const thin = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  expect(thin.skip).toBe(`fz-compact: ${shortfallReason(w.sessionId, messages, 'r1', BIG.length, HALF)}`)
  expect(w.disk.calls.some((call) => call.startsWith(`write ${spilled}`))).toBe(false)
  expect(w.compacts).toEqual([])
})

test('register: resume masks results not named before only at idleMinTokens', { options: SMALL }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'resume-min-tokens', () => clock.now())
  const spilled = spillPathOf(w.sessionId, 'r1')
  const messages = twoReads()
  w.rows = twoReads()
  // Before the restart r1 was masked and spilled; r2 never was. The session reports 1000 tokens, under idleMinTokens (200000).
  w.disk.put(spilled, BIG, START - 2 * HOUR)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START - 2 * HOUR, [knownEntry(w.sessionId)]), START - 2 * HOUR)
  w.usage = usageOf(1000)
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])

  // r1, which the manifest names, is masked again; r2 stays original, and the line says why.
  const small = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  expect(maskedRowText(small, 2)).toBe(placeholder('Read', BIG.length, spilled))
  expect(maskedRowText(small, 4)).toBe(OTHER)
  expect(w.logs.some((line) => line.startsWith('fz-compact masked: masked 1 rows; results not masked before stay (the context holds 1000 tokens, under idleMinTokens 200000)'))).toBe(true)
  expect(w.disk.files.has(spillPathOf(w.sessionId, 'r2'))).toBe(false)
  expect(await manifestIds(w)).toEqual(['r1'])

  // At idleMinTokens, the size the session reports (not the rows' estimate, far under it) lets r2 be masked too.
  w.usage = usageOf(200_000)
  const large = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  expect(maskedRowText(large, 2)).toBe(placeholder('Read', BIG.length, spilled))
  expect(maskedRowText(large, 4)).toBe(placeholder('Read', OTHER.length, spillPathOf(w.sessionId, 'r2')))
  expect(await manifestIds(w)).toEqual(['r1', 'r2'])
  expect(w.compacts).toEqual([])
})

test('register: resume without a reported context size estimates it from the rows', { options: SMALL_CONTEXT }, async ($, on) => {
  const clock = mock.clock(on, { now: START })
  mock.env(on, { CLAUDE_CODE_SESSION_KIND: 'bg', HOME })
  const w = world(on, 'resume-estimated-tokens', () => clock.now())
  const spilled = spillPathOf(w.sessionId, 'r1')
  const messages = twoReads()
  w.rows = twoReads()
  w.disk.put(spilled, BIG, START - 2 * HOUR)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START - 2 * HOUR, [knownEntry(w.sessionId)]), START - 2 * HOUR)
  // The usage reports no context size, as before a resumed session's first response: the rows' characters at four a token stand in for it.
  w.usage = usageOf(undefined)
  await startSession($)
  await clock.settle()
  expect(w.commands).toEqual([RESUME])

  // About 2020 tokens, under idleMinTokens: r2 stays original.
  const chars = charsOf(messages)
  expect(chars / 4 < SMALL_CONTEXT.idleMinTokens).toBe(true)
  const small = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages })
  expect(maskedRowText(small, 2)).toBe(placeholder('Read', BIG.length, spilled))
  expect(maskedRowText(small, 4)).toBe(OTHER)
  const stays = `the context holds about ${Math.floor(chars / 4)} tokens (${chars} chars; no context size was reported), under idleMinTokens ${SMALL_CONTEXT.idleMinTokens}`
  expect(w.logs.some((line) => line.startsWith(`fz-compact masked: masked 1 rows; results not masked before stay (${stays})`))).toBe(true)
  expect(await manifestIds(w)).toEqual(['r1'])

  // A long newest prompt brings the estimate to idleMinTokens or over: r2 is masked too.
  const longer = twoReads()
  longer[5] = { role: 'user', text: 'y'.repeat(20_000), toolUses: [] }
  expect(charsOf(longer) / 4 >= SMALL_CONTEXT.idleMinTokens).toBe(true)
  const large = await $.session.compact({ trigger: 'manual', instructions: RESUME, messages: longer })
  expect(maskedRowText(large, 4)).toBe(placeholder('Read', OTHER.length, spillPathOf(w.sessionId, 'r2')))
  expect(await manifestIds(w)).toEqual(['r1', 'r2'])
  expect(w.compacts).toEqual([])
})

test('tool.check: allows spill child', { options: { enabled: true } }, async ($, on) => {
  mock.env(on, { HOME })
  const w = world(on, 'check-child', () => START)
  const child = spillPathOf(w.sessionId, 'r1')
  w.disk.put(child, BIG, START)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [knownEntry(w.sessionId)]), START)

  // The engine asks, or denies, with no settings rule: a spill file the session's manifest names is allowed.
  const asked = await checkRead($, child)
  expect(asked.decision).toBe('allow')
  expect(asked.reason).toBe('fz-compact spill file')
  w.verdict = { decision: 'deny', reason: 'engine denies' }
  expect((await checkRead($, child)).decision).toBe('allow')

  // A settings rule the person wrote stands, a deny or an ask.
  w.verdict = { decision: 'deny', reason: 'denied by a settings rule', rule: 'Read(/h/notes.txt)' }
  const ruled = await checkRead($, child)
  expect(ruled.decision).toBe('deny')
  expect(ruled.rule).toBe('Read(/h/notes.txt)')
  w.verdict = { decision: 'ask', reason: 'asked by a settings rule', rule: 'Read' }
  expect((await checkRead($, child)).decision).toBe('ask')
})

test('tool.check: denies sibling prefix', { options: { enabled: true } }, async ($, on) => {
  mock.env(on, { HOME })
  const w = world(on, 'check-sibling', () => START)
  const sibling = '/h/.claude/fz-compact/spill-other/a'
  const child = spillPathOf(w.sessionId, 'r1')
  w.disk.put(sibling, 'not a spill file', START)
  w.disk.put(child, BIG, START)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [knownEntry(w.sessionId)]), START)

  const outside = await checkRead($, sibling)
  expect(outside.decision).toBe('ask')
  expect(outside.reason).toBe('engine asks')
  // The root itself is not under it; a spill file beneath it that the manifest names, resolved the same way, is.
  expect((await checkRead($, ROOT)).decision).toBe('ask')
  expect((await checkRead($, child)).decision).toBe('allow')
})

test('tool.check: denies symlink outside', { options: { enabled: true } }, async ($, on) => {
  mock.env(on, { HOME })
  const w = world(on, 'check-symlink', () => START)
  const child = spillPathOf(w.sessionId, 'r1')
  const escape = spillPathOf(w.sessionId, 'escape')
  const inner = spillPathOf(w.sessionId, 'inner')
  w.disk.put(child, BIG, START)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [knownEntry(w.sessionId)]), START)
  w.disk.put('/etc/secret', 'secret', START)
  w.disk.realPaths.set(escape, '/etc/secret')
  w.disk.realPaths.set(inner, child)

  // Spelled under the root, it lands outside: the engine's ask stands.
  const out = await checkRead($, escape)
  expect(out.decision).toBe('ask')
  expect(out.reason).toBe('engine asks')
  // A link that lands under the root is judged by where it lands.
  expect((await checkRead($, inner)).decision).toBe('allow')
})

test('tool.check: denies unresolvable path', { options: { enabled: true } }, async ($, on) => {
  mock.env(on, { HOME })
  const w = world(on, 'check-unresolvable', () => START)
  const child = spillPathOf(w.sessionId, 'r1')
  const missing = spillPathOf(w.sessionId, 'missing')
  const dangling = spillPathOf(w.sessionId, 'dangling')
  w.disk.put(child, BIG, START)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [knownEntry(w.sessionId)]), START)

  // A path with nothing at it, and a link that leads nowhere, have no realPath: the engine's ask stands.
  const absent = await checkRead($, missing)
  expect(absent.decision).toBe('ask')
  expect(absent.reason).toBe('engine asks')
  w.disk.realPaths.set(dangling, NOWHERE)
  expect((await checkRead($, dangling)).decision).toBe('ask')
  expect(w.disk.calls).toContain(`stat ${missing}`)
  expect(w.disk.calls).toContain(`stat ${dangling}`)

  // A root that does not resolve allows nothing, not even a file that does; once it resolves, that file is allowed.
  w.disk.realPaths.set(ROOT, NOWHERE)
  expect((await checkRead($, child)).decision).toBe('ask')
  w.disk.realPaths.delete(ROOT)
  expect((await checkRead($, child)).decision).toBe('allow')
})

test('tool.check: allows only files a manifest names', { options: { enabled: true } }, async ($, on) => {
  mock.env(on, { HOME })
  const w = world(on, 'check-named', () => START)
  const child = spillPathOf(w.sessionId, 'r1')
  // Under the root but not a spill file a manifest names: another result's file in the session folder, the named
  // file's name a folder deeper, the session folder a folder deeper, a file of a session with no manifest, a file
  // beside the session folders, a file under a folder spelled as the named file, and the manifest itself.
  const unnamed = spillPathOf(w.sessionId, 'r9')
  const nested = `${ROOT}/${w.sessionId}/nested/r1.txt`
  const deeper = `${ROOT}/nested/${w.sessionId}/r1.txt`
  const unowned = spillPathOf('check-unowned', 'r1')
  const beside = `${ROOT}/notes.txt`
  const inner = `${child}/inner`
  w.disk.put(child, BIG, START)
  for (const path of [unnamed, nested, deeper, unowned, beside, inner]) w.disk.put(path, 'not a spill file', START)
  // The manifest names r1 unconfirmed: a placeholder may point at its file all the same.
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [{ ...knownEntry(w.sessionId), confirmed: false }]), START)

  expect((await checkRead($, child)).decision).toBe('allow')
  for (const path of [unnamed, nested, deeper, unowned, beside, inner, manifestPathOf(w.sessionId)]) {
    const verdict = await checkRead($, path)
    expect(`${path}: ${verdict.decision} ${verdict.reason}`).toBe(`${path}: ask engine asks`)
  }

  // A manifest that cannot be read now names nothing: the engine's ask stands until it can be.
  w.disk.failRead = (path) => path === manifestPathOf(w.sessionId)
  expect((await checkRead($, child)).decision).toBe('ask')
  w.disk.failRead = () => false
  expect((await checkRead($, child)).decision).toBe('allow')
})

test('tool.check: allows named spill files while disabled', { options: { enabled: false } }, async ($, on) => {
  mock.env(on, { HOME })
  const w = world(on, 'check-disabled', () => START)
  const child = spillPathOf(w.sessionId, 'r1')
  w.disk.put(child, BIG, START)
  w.disk.put(manifestPathOf(w.sessionId), manifestText(w.sessionId, START, [knownEntry(w.sessionId)]), START)

  // A session masked before the plugin was turned off still holds placeholders that point at its spill files.
  const verdict = await checkRead($, child)
  expect(verdict.decision).toBe('allow')
  expect(verdict.reason).toBe('fz-compact spill file')
})
